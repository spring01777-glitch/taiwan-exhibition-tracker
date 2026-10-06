"""Offline reviewed-source adapters, snapshots and session-aware reconciliation.

This module performs no HTTP requests. Catalog access is deliberately separate
from permission to automate a provider, and from measured catalog completeness.
"""
import copy
import hashlib
import json
import re
import unicodedata
from datetime import datetime
from urllib.parse import urlsplit

KINDS=('concerts','comedy')

def normalized(value):
    return re.sub(r'[^\w]', '',unicodedata.normalize('NFKC',str(value or '')).replace('台','臺')).casefold()

def classify(kind, evidence):
    """Return included/excluded/pending and an inspectable, fixed reason."""
    fields=('title','format','categories','description','performers','showUnit','descriptionFilterHtml')
    text=' '.join(str(evidence.get(k,'') or '') for k in fields)
    if re.search(r'課程|工作坊|研習|研討會|講座|音樂劇|音樂喜劇|musical|workshop|masterclass|\bcourse\b|\bclass\b',text,re.I):
        return 'excluded','COURSE_OR_MUSICAL'
    if re.search(r'fan.?meeting|粉絲見面|見面會|票券升級|\bupgrade\b',text,re.I):
        return 'excluded','FAN_MEETING_OR_UPGRADE'
    if kind=='comedy' and re.search(r'相聲|漫才|魔術|親子劇|即興劇|即興喜劇|喜劇小品|\bimprov\b|\bsketch\b|\btheat(?:re|er)\b',text,re.I):
        return 'excluded','OTHER_PERFORMANCE_FORMAT'
    reviewed=evidence.get('reviewedKind')
    if reviewed in KINDS:
        return ('included','OFFICIAL_REVIEWED_FORMAT') if reviewed==kind else ('excluded','OTHER_REVIEWED_FORMAT')
    if kind=='comedy':
        if re.search(r'脫口秀|單口喜劇|站立喜劇|stand[ -]?up|\bcomedy\b',text,re.I):
            return 'included','MULTIFIELD_STANDUP_EVIDENCE'
        return 'pending','INSUFFICIENT_STANDUP_EVIDENCE'
    if re.search(r'演唱會|音樂會|演唱|\bconcert\b|\blive\b',text,re.I) or str(evidence.get('category'))=='17':
        return 'included','CONCERT_EVIDENCE'
    return 'pending','INSUFFICIENT_CONCERT_EVIDENCE'

def read(path,fallback):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else copy.deepcopy(fallback)

def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    temp.replace(path)

def load_registry(root):
    registry=read(root/'data/live-source-registry.json',{'schemaVersion':1,'sources':[]})
    seen=set()
    for entry in registry['sources']:
        sid=entry['id']
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}',sid) or sid in seen:
            raise ValueError('invalid or duplicate source id')
        seen.add(sid)
    return registry['sources']

def snapshot_path(root,kind,sid):
    if kind not in KINDS or not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}',sid):
        raise ValueError('invalid snapshot key')
    return root/'data/live-sources'/kind/(sid+'.json')

def checked_url(value):
    p=urlsplit(str(value or ''))
    if p.scheme!='https' or not p.hostname or p.username or p.password:
        raise ValueError('unsafe URL')
    return str(value)

def validate_event(raw,sid,now):
    e=copy.deepcopy(raw)
    uid=str(e.get('sourceUid') or '')
    if not uid or not e.get('title') or not e.get('region') or not e.get('venue') or not e.get('sessions'):
        raise ValueError('missing event identity or facts')
    e['region']=e['region'].replace('台','臺')
    e['source']=sid
    e['sourceUrl']=checked_url(e['sourceUrl'])
    e['id']=hashlib.sha256('|'.join((sid,uid,normalized(e['region']),normalized(e['venue']))).encode()).hexdigest()[:20]
    sessions={}
    for s in e['sessions']:
        datetime.strptime(s['date'],'%Y-%m-%d')
        if s.get('time'):datetime.strptime(s['time'],'%H:%M')
        if s.get('status') and s['status'] not in ('scheduled','changed','unconfirmed','cancelled','rescheduled'):
            raise ValueError('invalid session status')
        sessions[(s['date'],s.get('time') or '')]={k:v for k,v in s.items() if k in ('date','time','status')}
    e['sessions']=[sessions[k] for k in sorted(sessions)]
    e.setdefault('summary','官方活動基本資料；詳細規定請見來源。')
    if len(e['summary'])>180:raise ValueError('summary must be independently brief')
    e.setdefault('performers',None);e.setdefault('price',None)
    e.setdefault('saleAt',None);e.setdefault('saleNote','一般開賣時間未提供，請見官方。')
    e.setdefault('ticketStatus','非即時票況');e.setdefault('ticketUrl',None);e.setdefault('ticketVerifiedAt',None)
    e.setdefault('tickets',[]);e.setdefault('status','scheduled');e.setdefault('revisions',[])
    e['verifiedAt']=now[:10]
    if e['status'] not in ('scheduled','changed','unconfirmed','cancelled','rescheduled'):raise ValueError('invalid event status')
    allowed={'id','source','sourceUid','title','performers','region','venue','address','sessions','price','saleAt','saleNote','ticketStatus','ticketUrl','ticketVerifiedAt','tickets','status','statusNote','summary','verifiedAt','revisions'}
    # Classification evidence and provider prose never enter the public snapshot.
    if set(e)-allowed-{'sourceUrl'}:raise ValueError('unsupported public fact field')
    for t in e['tickets']:
        if set(t)-{'platform','url','checkedAt','sessions','price','saleAt'}:raise ValueError('unsupported ticket field')
        checked_url(t['url'])
        if urlsplit(t['url']).path in ('','/') or not t.get('platform') or not t.get('checkedAt'):
            raise ValueError('ticket lacks reviewed detail link')
        if not isinstance(t['platform'],str) or len(t['platform'])>80 or '<' in t['platform']:raise ValueError('invalid platform label')
        datetime.strptime(t['checkedAt'],'%Y-%m-%d')
        if not t.get('sessions') or any((s['date'],s.get('time') or '') not in sessions for s in t['sessions']):
            raise ValueError('ticket scope differs from event sessions')
    return e

def retain_missing(previous,incoming,complete=False):
    """No disappearance is interpreted as cancellation, nor as deletion."""
    by_id={e['id']:copy.deepcopy(e) for e in previous}
    for raw in incoming:
        e=copy.deepcopy(raw);before=by_id.get(e['id'])
        if before:
            e['revisions']=copy.deepcopy(before.get('revisions',[]))
            if before['sessions']!=e['sessions']:
                e['revisions'].append({'at':e['verifiedAt'],'note':'已核對來源場次異動。','previousSessions':before['sessions']})
                if e['status']=='scheduled':e['status']='changed'
        by_id[e['id']]=e
    if complete:
        incoming_ids={e['id'] for e in incoming}
        for eid,e in by_id.items():
            if eid not in incoming_ids and e.get('status')!='cancelled':
                e.update(status='unconfirmed',statusNote='本次已核對範圍未列出；保留資料，不據此認定取消。')
    return list(by_id.values())

def import_reviewed(root,kind,sid,payload,now):
    """Adapter contract for cloud reviewed catalog pages; not a web crawler."""
    entry=next((s for s in load_registry(root) if s['id']==sid),None)
    if not entry or entry.get('adapter')!='reviewed-json' or kind not in entry['kinds']:
        raise ValueError('source is not registered for reviewed imports')
    path=snapshot_path(root,kind,sid)
    old=read(path,{'events':[],'status':{}})
    status={**old['status'],'id':sid,'name':entry['name'],'url':entry['url'],'checkedAt':now,
            'mode':'reviewed-import','discovered':0,'included':0,'excluded':0,'pending':0,'failed':0,
            'reasons':{},'coverageComplete':False,'scope':None,'pagesVisited':0,'expectedPages':None}
    records=[];events=[]
    try:
        if not isinstance(payload,dict):raise ValueError('reviewed envelope must be an object')
        if payload.get('sourceId')!=sid or payload.get('kind')!=kind:
            raise ValueError('source or kind mismatch')
        reviewed_at=datetime.strptime(payload['reviewedAt'],'%Y-%m-%d').date().isoformat()
        if reviewed_at>now[:10]:raise ValueError('future review date')
        status['reviewedAt']=reviewed_at
        traversal=payload['traversal'];pages=payload['pages']
        if not isinstance(traversal,dict) or not isinstance(pages,list):raise ValueError('invalid traversal')
        status['scope']=str(traversal['scope'])[:250]
        expected=traversal.get('expectedPageIds')
        if not isinstance(expected,list) or not expected or len(set(expected))!=len(expected):
            raise ValueError('expected page IDs required')
        visited=[p['id'] for p in pages]
        if len(set(visited))!=len(visited) or not set(visited)<=set(expected):raise ValueError('invalid visited pages')
        status.update(pagesVisited=len(visited),expectedPages=len(expected))
        # A caller's complete flag alone is never proof that page two was read.
        status['coverageComplete']=bool(traversal.get('complete') and set(visited)==set(expected))
        for page in pages:
            checked_url(page['url'])
            if not isinstance(page['items'],list):raise ValueError('invalid page items')
            for item in page['items']:
                status['discovered']+=1
                uid=str(item.get('sourceUid') or '')
                decision,reason=classify(kind,item.get('evidence',{}))
                if decision=='included' and not item.get('officialFactsReviewed'):
                    decision,reason='pending','DETAIL_FACTS_NOT_REVIEWED'
                if decision=='included':
                    try:
                        event=validate_event({**item['event'],'sourceUid':uid},sid,reviewed_at)
                        events.append(event)
                    except (KeyError,ValueError,TypeError):decision,reason='failed','INVALID_REVIEWED_FACTS'
                status[decision]+=1
                status['reasons'][reason]=status['reasons'].get(reason,0)+1
                records.append({'sourceUid':uid,'pageId':page['id'],'decision':decision,'reason':reason})
        if not status['discovered']:raise ValueError('empty discovery response')
        if status['failed']:raise ValueError('invalid reviewed facts')
        status.update(status='ok',lastSuccess=now,lastSuccessfulIncluded=status['included'],
                      message='本次核對匯入完成；零符合、部分範圍或完整範圍分開記錄，非全平台每日掃描。')
        events=retain_missing(old['events'],events,status['coverageComplete'])
        success=True
    except (KeyError,ValueError,TypeError,AttributeError):
        status.update(status='error',reasonCode='REVIEWED_IMPORT_INVALID',coverageComplete=False,message='來源核對匯入失敗；保留最後成功資料。')
        status['failed']=max(status['failed'],1)
        events=old['events'];success=False
    status['retainedEventCount']=len(events)
    write(path,{'schemaVersion':1,'sourceId':sid,'kind':kind,'events':events,'status':status,'records':records})
    return success

def source_snapshots(root,kind,legacy_events=(),legacy_sources=()):
    events=[];statuses=[];registered=set()
    for entry in load_registry(root):
        if kind not in entry['kinds'] or entry.get('adapter')!='reviewed-json':continue
        sid=entry['id'];registered.add(sid)
        saved=read(snapshot_path(root,kind,sid),None)
        if saved:
            events.extend(saved['events']);statuses.append(saved['status'])
        else:
            prior=[e for e in legacy_events if e.get('source')==sid]
            events.extend(prior)
            statuses.append({'id':sid,'name':entry['name'],'url':entry['url'],'status':'pending','mode':'reviewed-import',
                             'lastSuccess':None,'coverageComplete':False,'discovered':None,'included':None,
                             'excluded':None,'pending':None,'failed':None,'scope':None,'pagesVisited':0,'expectedPages':None,
                             'message':'尚無獨立來源核對快照；未啟用自動抓取，不能視為已完整涵蓋。'})
    # Preserve already-published independent sources even before registration.
    unknown={e['source'] for e in legacy_events if e.get('source') not in registered|{'moc','manual'}}
    for sid in sorted(unknown):
        events.extend(e for e in legacy_events if e['source']==sid)
        statuses.append(next((s for s in legacy_sources if s.get('id')==sid),
                            {'id':sid,'name':sid,'status':'pending','message':'既有來源保留；尚待清冊登記及核對。','url':'','coverageComplete':False}))
    return events,statuses

def reconcile(events):
    """Keep source identity and merge only same-place, corroborated sessions."""
    result=[]
    for raw in events:
        e=copy.deepcopy(raw);e['region']=e['region'].replace('台','臺')
        refs=e.setdefault('sourceRefs',[{'source':e['source'],'sourceUid':e.get('sourceUid'),'id':e['id']}])
        scope=lambda x:{(s['date'],s.get('time') or '') for s in x['sessions']}
        urls=lambda x:{t['url'] for t in x.get('tickets',[]) if t.get('url')}|({x['sourceUrl']} if x.get('sourceUrl') and 'data.gov.tw/dataset/' not in x['sourceUrl'] else set())
        before=None
        for candidate in result:
            if (normalized(e['region']),normalized(e['venue']))!=(normalized(candidate['region']),normalized(candidate['venue'])):continue
            stable=bool(e.get('sourceUid') and any(r['source']==e['source'] and r.get('sourceUid')==e['sourceUid'] for r in candidate['sourceRefs']))
            corroborated=normalized(e['title'])==normalized(candidate['title']) or bool(urls(e)&urls(candidate))
            if stable or (corroborated and scope(e)&scope(candidate) and normalized(e['venue']) not in ('場館未提供','unknown','')):
                before=candidate;break
        if before is None:result.append(e);continue
        for s in e['sessions']:
            if (s['date'],s.get('time') or '') not in scope(before):before['sessions'].append(s)
        for r in refs:
            if r not in before['sourceRefs']:before['sourceRefs'].append(r)
        before.setdefault('tickets',[]).extend(e.get('tickets',[]))
    for e in result:e['sessions'].sort(key=lambda s:(s['date'],s.get('time') or ''))
    return result

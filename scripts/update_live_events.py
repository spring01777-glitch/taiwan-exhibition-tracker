"""Daily licensed metadata only; never crawls ticket platforms. Standard library."""
import argparse
import copy
import hashlib
import html
import json
import re
import ssl
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
sys.path.insert(0,str(Path(__file__).resolve().parent))
from live_sources import classify,source_snapshots,snapshot_path,reconcile,import_reviewed
from live_sources import read as source_read, write as source_write

ROOT = Path(__file__).resolve().parents[1]
TW = timezone(timedelta(hours=8))
API = 'https://cloud.culture.tw/frontsite/trans/SearchShowAction.do?method=doFindTypeJ&category='
CITIES = ['臺北市','新北市','基隆市','桃園市','新竹市','新竹縣','苗栗縣','臺中市','彰化縣','南投縣','雲林縣','嘉義市','嘉義縣','臺南市','高雄市','屏東縣','宜蘭縣','花蓮縣','臺東縣','澎湖縣','金門縣','連江縣']

def clean(v):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]*>', '', str(v or '')))).strip()

def safe_url(v):
    p = urlsplit(str(v or ''))
    return str(v) if p.scheme == 'https' and p.hostname and not p.username and not p.password else ''

def platform(url):
    host = (urlsplit(url).hostname or '').lower()
    if host.endswith('.kktix.cc') or host in ('kktix.com','www.kktix.com'): return 'KKTIX'
    return {'tixcraft.com':'拓元 tixCraft','ticket.com.tw':'年代 ERA','kham.com.tw':'寬宏 KHAM','ticket.ibon.com.tw':'ibon','www.opentix.life':'OPENTIX','opentix.life':'OPENTIX'}.get(host)

def normalize_tickets(event):
    """Explicit session scopes only. Never turn a platform homepage into a ticket."""
    tickets = copy.deepcopy(event.get('tickets', []))
    if 'tickets' not in event and event.get('ticketVerifiedAt') and safe_url(event.get('ticketUrl')):
        tickets = [dict(url=event['ticketUrl'],platform=platform(event['ticketUrl']),checkedAt=event['ticketVerifiedAt'],sessions=copy.deepcopy(event['sessions']))]
    valid = {(s['date'],s.get('time')) for s in event['sessions']}
    merged = {}
    for t in tickets:
        url = safe_url(t.get('url'))
        label=platform(url) or clean(t.get('platform'))
        if not url or not label or not t.get('checkedAt') or urlsplit(url).path in ('','/'):
            continue
        try:datetime.strptime(t['checkedAt'],'%Y-%m-%d')
        except (TypeError,ValueError):continue
        scoped = [dict(date=s['date'],time=s.get('time')) for s in t.get('sessions',[]) if (s.get('date'),s.get('time')) in valid]
        if not scoped: continue
        key=(url,t.get('price'),t.get('saleAt'))
        if key not in merged:
            merged[key]=dict(t,url=url,platform=label,sessions=[])
        for s in scoped:
            if s not in merged[key]['sessions']:merged[key]['sessions'].append(s)
    return list(merged.values())

def stamp():
    return datetime.now(TW).isoformat(timespec='seconds')

def session(v):
    text = clean(v).replace('/', '-').replace('T', ' ')
    day = datetime.strptime(text[:10], '%Y-%m-%d').date().isoformat()
    clock = text[11:16] if len(text) >= 16 else None
    if clock:
        datetime.strptime(clock, '%H:%M')
    return {'date': day, 'time': clock}

def normalize(rows, kind, now, diagnostics=None):
    counts=diagnostics if diagnostics is not None else {}
    counts.update(discovered=len(rows) if isinstance(rows,list) else None,included=0,excluded=0,pending=0,failed=0,reasons={})
    if not isinstance(rows, list) or not rows:
        raise ValueError('empty or malformed provider response')
    events = {}
    bad = 0
    category = '17' if kind == 'concerts' else '11'
    if not any(isinstance(r, dict) and str(r.get('category')) == category for r in rows):
        raise ValueError('unexpected provider category')
    for row in rows:
        decision=None
        try:
            if str(row.get('category')) != category:
                counts['excluded']+=1
                counts['reasons']['OTHER_CATEGORY']=counts['reasons'].get('OTHER_CATEGORY',0)+1
                continue
            title = clean(row['title'])
            if not title or '\ufffd' in title:
                raise ValueError('bad title encoding')
            decision,reason=classify(kind,row)
            counts[decision]+=1
            counts['reasons'][reason]=counts['reasons'].get(reason,0)+1
            if decision!='included':continue
            shows = row.get('showInfo') or row.get('showinfo')
            if not isinstance(shows, list) or not shows:
                raise ValueError('missing sessions')
            for show in shows:
                venue = clean(show.get('locationName')) or '場館未公布'
                address = clean(show.get('location')).replace('台', '臺')
                region = next((c for c in CITIES if c in address), '地區未公布')
                uid = clean(row.get('UID'))
                if not uid:
                    raise ValueError('missing stable UID')
                key = hashlib.sha256((uid+'|'+venue).encode()).hexdigest()[:20]
                s = session(show.get('time') or row['startDate'])
                price = clean(show.get('price') or show.get('Price')) or None
                if key not in events:
                    events[key] = dict(id=key,source='moc',sourceUid=uid,title=title,performers=clean(row.get('showUnit')),region=region,venue=venue,address=address,sessions=[],price=price,saleAt=None,saleNote='開賣時間來源未提供；請至官方確認。',ticketStatus='來源未提供即時售票狀態',ticketUrl=None,ticketVerifiedAt=None,sourceUrl='https://data.gov.tw/dataset/6013' if kind=='concerts' else 'https://data.gov.tw/dataset/6009',status='scheduled',summary=f'{region}的'+('演唱會' if kind=='concerts' else '單口喜劇')+f'，演出地點為{venue}。',verifiedAt=now[:10],revisions=[])
                if s not in events[key]['sessions']:
                    events[key]['sessions'].append(s)
                if price and price != events[key]['price']:
                    events[key]['price'] = '各場次票價不同，請見官方資訊'
        except (ValueError, KeyError, TypeError, AttributeError):
            bad += 1
            if decision=='included':counts['included']-=1;counts['reasons'][reason]-=1
            counts['failed']+=1
            counts['reasons']['INVALID_PROVIDER_FACTS']=counts['reasons'].get('INVALID_PROVIDER_FACTS',0)+1
    counts['eventCount']=len(events)
    if bad > max(0, len(rows) * .2):
        raise ValueError(f'malformed records: {bad}/{len(rows)}')
    if kind == 'concerts' and not events:
        raise ValueError('no valid concert records')
    for event in events.values():
        event['sessions'].sort(key=lambda s:(s['date'],s['time'] or ''))
    return list(events.values())

def merge(previous, incoming, now):
    old = {e['id']:e for e in previous if e['source']=='moc'}
    result = []
    for event in incoming:
        before = old.pop(event['id'], None)
        if before:
            event['revisions'] = list(before.get('revisions', []))
            if before['sessions'] != event['sessions']:
                event['revisions'].append({'at':now,'note':'來源場次日期或時間異動，請確認官方公告。','previousSessions':before['sessions']})
                event['status'] = 'changed'
                event['statusNote'] = '來源日期／時間已變更，是否正式改期請確認官方公告。'
            elif before.get('status') in ('rescheduled','changed'):
                event['status']=before['status']
                event['statusNote']=before.get('statusNote','')
        result.append(event)
    for event in old.values():
        e = copy.deepcopy(event)
        if any(s['date'] >= now[:10] for s in e['sessions']):
            e['status']='unconfirmed'
            e['statusNote']='來源本次未列出，保留原資料；不代表取消，請向官方確認。'
        result.append(e)
    return result

def read(path, fallback):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else fallback

def write(path, data):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    temp.replace(path)

def build(kind, fetch, root=ROOT, now=None, manual_only=False):
    now = now or stamp()
    path = root/'data'/f'{kind}.json'
    previous = read(path, {'events':[], 'sources':[]})
    manual = read(root/'data'/f'{kind}-manual.json', {'events':[], 'sources':[]})
    category = '17' if kind=='concerts' else '11'
    source = {'name':'文化部・演唱會' if kind=='concerts' else '文化部・綜藝（僅明確單口／脫口秀）','url':'https://data.gov.tw/dataset/6013' if kind=='concerts' else 'https://data.gov.tw/dataset/6009','checkedAt':now,'lastSuccess':next((s.get('lastSuccess') for s in previous['sources'] if s.get('id')=='moc'),None),'id':'moc'}
    success = True
    saved=source_read(snapshot_path(root,kind,'moc'),None)
    previous_moc=saved['events'] if saved else [e for e in previous['events'] if e['source']=='moc']
    if saved:source=copy.deepcopy(saved['status'])
    if manual_only:
        moc=previous_moc
        if not saved:source=copy.deepcopy(next((s for s in previous['sources'] if s.get('id')=='moc'),dict(source,status='error',checkedAt=None,message='No previous MOC data')))
    else:
        counts={'discovered':None,'included':None,'excluded':None,'pending':None,'failed':None,'reasons':{}}
        try:
            incoming=normalize(fetch(category),kind,now,counts)
            moc=merge(previous_moc,incoming,now)
            source.update(status='ok',lastSuccess=now,checkedAt=now,**counts,coverageComplete=False,
                          scope=f'文化部 category {category} 單次授權 JSON；不代表全台完整目錄',pagesVisited=1,expectedPages=None,
                          message=f'授權 JSON 解析完成；納入 {len(incoming)} 個活動／場館，待分類 {counts["pending"]} 筆；不是全平台完整涵蓋。')
        except Exception as error:
            success=False
            moc=previous_moc
            source.update(status='error',checkedAt=now,**counts,coverageComplete=False,message='更新失敗，保留最後成功資料。'+type(error).__name__)
        source_write(snapshot_path(root,kind,'moc'),{'schemaVersion':1,'sourceId':'moc','kind':kind,'events':moc,'status':source})
    events=copy.deepcopy(manual['events'])
    independent,source_statuses=source_snapshots(root,kind,previous['events'],previous['sources'])
    success=success and not any(s.get('status')=='error' for s in source_statuses)
    events.extend(independent)
    events.extend(moc)
    reviewed = read(root/'data'/'live-event-links.json', {})
    for e in events:
        e['region']=e['region'].replace('台','臺')
        review = reviewed.get(e.get('sourceUid'))
        if review and review['title'] == e['title'] and safe_url(review['url']):
            e.update(sourceUrl=review['url'],ticketUrl=review['url'],ticketVerifiedAt=review['checkedAt'])
            # A later provider add/change cannot inherit an old ticket check.
            if 'sessions' in review:
                scoped=[dict(date=s['date'],time=s.get('time')) for s in review['sessions'] if s.get('venue')==e['venue']]
                e['tickets']=[dict(url=review['url'],checkedAt=review['checkedAt'],sessions=scoped)]
            for field in ('region','performers','saleAt','saleNote','price'):
                if field in review.get('facts', {}):
                    e[field] = review['facts'][field]
            if review.get('facts', {}).get('region'):
                e['summary'] = e['region']+'的演唱會，演出地點為'+e['venue']+'。'
        e['tickets']=normalize_tickets(e)
    events=reconcile(events)
    for e in events:e['tickets']=normalize_tickets(e)
    coverage=read(root/'data'/'live-platform-coverage.json', {'sources':[]})
    independent_ids={s['id'] for s in source_statuses}
    sources=[source]+manual['sources']+source_statuses
    for item in coverage['sources']:
        if item['id'] in independent_ids:continue
        s=copy.deepcopy(item)
        covered=[e for e in events if any(t['platform']==s.get('platform') for t in e['tickets'])] if s.get('platform') else []
        s['eventCount']=len(covered)
        s['sessionCount']=sum(sum(any(any(q['date']==v['date'] and q.get('time')==v.get('time') for q in t['sessions']) for t in e['tickets'] if t['platform']==s['platform']) for v in e['sessions']) for e in covered)
        sources.append(s)
    output = dict(schemaVersion=2,timezone='Asia/Taipei',updatedAt=now,events=events,sources=sources)
    write(path,output)
    return success

def fetch(category):
    request = Request(API+category,headers={'User-Agent':'TaiwanLiveEventsTracker/1.0 (daily licensed open-data metadata)'})
    try:
        with urlopen(request,timeout=30) as response:
            raw = response.read(8_000_001)
    except Exception as error:
        certificate_error=isinstance(error,ssl.SSLCertVerificationError) or isinstance(getattr(error,'reason',None),ssl.SSLCertVerificationError)
        if not certificate_error:raise
        # Same official URL, system TLS verification; no --insecure, trust-store
        # edits, external proxies or inherited curl config.
        result=subprocess.run(['curl','--disable','--fail','--silent','--show-error','--max-time','30','--max-filesize','8000000',API+category],capture_output=True,timeout=35,check=True)
        raw=result.stdout
    if len(raw)>8_000_000:
        raise ValueError('oversized response')
    return json.loads(raw.decode('utf-8-sig'))

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--concert-input',type=Path)
    parser.add_argument('--comedy-input',type=Path)
    parser.add_argument('--manual-only',action='store_true',help='Offline rebuild; retains MOC source timestamps')
    parser.add_argument('--reviewed-input',type=Path,help='Offline cloud-reviewed adapter JSON')
    parser.add_argument('--source-id')
    parser.add_argument('--kind',choices=('concerts','comedy'))
    args=parser.parse_args()
    if args.reviewed_input:
        if not args.source_id or not args.kind:parser.error('reviewed input requires source-id and kind')
        okay=import_reviewed(ROOT,args.kind,args.source_id,read(args.reviewed_input,{}),stamp())
        build(args.kind,lambda _:None,manual_only=True)
        sys.exit(0 if okay else 1)
    def provider(category):
        path=args.concert_input if category=='17' else args.comedy_input
        return read(path,[]) if path else fetch(category)
    results=[build(kind,provider,manual_only=args.manual_only) for kind in ('concerts','comedy')]
    sys.exit(0 if all(results) else 1)

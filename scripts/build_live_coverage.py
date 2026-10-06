"""Describe verified import scope without inferring catalog completeness."""
from pathlib import Path
from live_sources import read,write,load_registry

def build(root):
    sources=[]
    old={s['id']:s for s in read(root/'data/live-platform-coverage.json',{'sources':[]})['sources']}
    for entry in load_registry(root):
        scopes=[]
        for kind in entry['kinds']:
            snap=read(root/f'data/live-sources/{kind}/{entry["id"]}.json',None)
            if not snap:continue
            events=snap['events'];dates=[s['date'] for e in events for s in e['sessions']]
            records=snap.get('records',[]);status=snap['status']
            scopes.append({'kind':kind,'scope':status.get('scope'),'reviewedAt':status.get('reviewedAt'),
                'lastSuccess':status.get('lastSuccess'),'status':status['status'],
                'reviewedDetailUrls':sorted({e['sourceUrl'] for e in events}),
                'dateRange':{'from':min(dates),'through':max(dates)} if dates else None,
                'reviewedInputItems':len(records) if records else None,
                'storedVenueRecords':len(events),'storedSessions':sum(len(e['sessions']) for e in events),
                'decisions':{k:status.get(k) for k in ('discovered','included','excluded','pending','failed')},
                'pagesVisited':status.get('pagesVisited'),'expectedPages':status.get('expectedPages'),
                'pageGrain':'輸入資料包；不代表平台目錄分頁','coverageComplete':False})
        item={**old.get(entry['id'],{}),'id':entry['id'],'name':entry['name'],'url':entry['url'],
            'status':'manual' if entry['adapter']=='reviewed-json' else 'licensed-api',
            'automationPermission':entry['permission'],'checkedAt':max((s['reviewedAt'] or '' for s in scopes),default=None),
            'lastSuccess':max((s['lastSuccess'] or '' for s in scopes),default=None),
            'verifiedScopes':scopes,'coverageComplete':False,'catalogTotal':None,'unreviewedCatalogItems':None,
            'unknowns':['全目錄總數','未核對項目数量','完整排除矩陣','實際目錄分頁覆蓋'],
            'message':('已保存下列官方詳情頁、實際場次與核對日期；輸入資料包不等於完整目錄。' if scopes else '尚無獨立核對快照；目錄範圍與項目數未知。')}
        if entry['adapter']=='moc-json':
            item['message']='每日授權 API 僅處理文化部 category 17/11 回傳；不代表全台售票活動。'
        sources.append(item)
    write(root/'data/live-platform-coverage.json',{'schemaVersion':2,'sources':sources})

if __name__=='__main__':build(Path(__file__).resolve().parents[1])

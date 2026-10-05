"""One daily licensed Jolpica request. Never crawl Formula1.com."""
import argparse,json,re
from datetime import datetime,timezone
from pathlib import Path
from urllib.request import Request,urlopen
ROOT=Path(__file__).resolve().parents[1]
HOST='https://www.formula1.com'
API='https://api.jolpi.ca/ergast/f1/2026.json'
LICENSE='https://creativecommons.org/licenses/by-nc-sa/4.0/'
TERMS='https://github.com/jolpica/jolpica-f1/blob/main/TERMS.md'
SLUGS=dict(zip(['Australian','Chinese','Japanese','Miami','Canadian','Monaco','Barcelona','Austrian','British','Belgian','Hungarian','Dutch','Italian','Spanish','Azerbaijan','Bahrain Grand Prix in Malaysia','Singapore','United States','Mexico City','Brazilian','Las Vegas','Qatar','Abu Dhabi'],['australia','china','japan','miami','canada','monaco','barcelona-catalunya','austria','great-britain','belgium','hungary','netherlands','italy','spain','azerbaijan','bahrain','singapore','united-states','mexico','brazil','las-vegas','qatar','united-arab-emirates']))
SESSIONS=[('FirstPractice','Practice 1'),('SecondPractice','Practice 2'),('ThirdPractice','Practice 3'),('SprintQualifying','Sprint Qualifying'),('Sprint','Sprint'),('Qualifying','Qualifying')]
def fetch(url):
    if url!=API:raise ValueError('Unexpected API')
    with urlopen(Request(url,headers={'User-Agent':'TaiwanExhibitionTracker/1.1'}),timeout=25) as response:
        if response.url!=API:raise ValueError('Unexpected redirect')
        raw=response.read(2_000_001)
        if len(raw)>2_000_000:raise ValueError('Oversized source')
        return json.loads(raw)
def timestamp(date,time):
    datetime.strptime(date,'%Y-%m-%d')
    if not re.fullmatch(r'\d{2}:\d{2}:\d{2}Z',time):raise ValueError('Missing UTC time')
    return datetime.fromisoformat(date+'T'+time.replace('Z','+00:00')).isoformat()
def parse_race(r):
    if r['season']!='2026' or not r['raceName'] or not r['Circuit']['circuitId']:raise ValueError('Invalid race')
    date=r['date'];datetime.strptime(date,'%Y-%m-%d')
    name=r['raceName'];slug=SLUGS.get(name.removesuffix(' Grand Prix'));sessions=[];missing=[]
    for field,label in SESSIONS+[('Race','Race')]:
        item=r if field=='Race' else r.get(field)
        if item is None:continue
        if not item.get('time'):missing.append(label);continue
        sessions.append({'name':label+' - '+name,'start':timestamp(item['date'],item['time']),'end':None})
    sessions.sort(key=lambda s:s['start'])
    return {'id':slug or r['Circuit']['circuitId'],'name':name,'weekendStart':min([date]+[s['start'][:10] for s in sessions]),'weekendEnd':date,'source':HOST+'/en/racing/2026'+('/'+slug if slug else ''),'dataSource':API,'sourceTimezone':'UTC (Jolpica date/time)','sessions':sessions,'missingTimes':missing}
def atomic(path,data):
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8');tmp.replace(path)
def update(path,getter=fetch):
    previous=json.loads(path.read_text(encoding='utf8')) if path.exists() else {'seasons':{},'sources':{}}
    now=datetime.now(timezone.utc).isoformat();source=previous['sources'].get('2026',{})
    try:
        response=getter(API)['MRData'];raw=response['RaceTable']['Races']
        if response['RaceTable']['season']!='2026' or len(raw)!=int(response['total']):raise ValueError('Incomplete calendar')
        rows=[parse_race(r) for r in raw];old=previous['seasons'].get('2026',[])
        if len(rows)<max(15,int(len(old)*.8)) or len({r['id'] for r in rows})!=len(rows):raise ValueError('Empty, duplicate or diminished calendar')
        for r in rows:r.update(lastSuccess=now,status='ok')
        ids={r['id'] for r in rows}
        for r in old:
            if r['id'] not in ids:r['status']='unconfirmed';rows.append(r)
        previous['seasons']={'2026':sorted(rows,key=lambda r:r['weekendStart'])}
        previous['sources']={'2026':{'status':'ok','lastSuccess':now,'lastAttempt':now,'url':API,'name':'Jolpica 社群賽程 API（非 F1 官方）'}};errors=[]
    except Exception as exc:
        reason=type(exc).__name__;source.update(status='error',lastAttempt=now,error=reason,url=API,name='Jolpica 社群賽程 API（非 F1 官方）')
        previous['sources']={'2026':source};errors=[reason]
    previous.update(lastAttempt=now,errors=errors,attribution={'name':'Jolpica-F1','license':'CC BY-NC-SA 4.0','licenseUrl':LICENSE,'termsUrl':TERMS,'changes':'2026 calendar only; normalized sessions, Taiwan time displayed; no results or media.'})
    atomic(path,previous);return errors
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--path',type=Path,default=ROOT/'data/f1.json');args=parser.parse_args()
    errors=update(args.path);print('F1 update: '+('; '.join(errors) if errors else 'success'));raise SystemExit(bool(errors))

"""Daily, low-rate reads of three official public exhibition pages.

No direct internal APIs, query pagination, images, posters or full prose are
stored. Failures preserve each source's complete last successful fact snapshot.
"""
import argparse,hashlib,json,re,time
from datetime import datetime,timedelta,timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urljoin,urlsplit,quote,urlunsplit,unquote
from urllib.request import Request,urlopen
from urllib.robotparser import RobotFileParser
from bs4 import BeautifulSoup
from update import atomic,clean,date,merge
from recover_source_links import installed_browser

ROOT=Path(__file__).resolve().parents[1]
UA='TaiwanExhibitionTracker/0.4 (+https://github.com/spring01777-glitch/taiwan-exhibition-tracker)'
SOURCES={
    'songshan':{'base':'https://www.songshanculturalpark.org','list':'/exhibition','privacy':'/privacy','name':'松山文創園區','region':'臺北市','address':'臺北市信義區光復南路133號','prefix':'/exhibition/activity/'},
    'huashan':{'base':'https://www.huashan1914.com','list':'/exhibition','privacy':'/privacy','name':'華山1914','region':'臺北市','address':'臺北市中正區八德路一段1號','prefix':'/exhibition/'},
    'pier2':{'base':'https://pier2.org','list':'/exhibition/','privacy':'/privacy/','name':'駁二藝術特區','region':'高雄市','address':'高雄市鹽埕區大勇路1號','prefix':'/exhibition/info/'},
}
MAX_DETAILS=24

def soup_of(body):return BeautifulSoup(body,'html.parser')
def text(node):return clean(node.get_text(' ',strip=True)) if node else ''
def canonical_public_url(url):
    p=urlsplit(url)
    return urlunsplit((p.scheme,p.netloc,quote(unquote(p.path),safe='/'),p.query,p.fragment))
def policy_digest(body):
    soup=soup_of(body)
    for n in soup(['script','style','header','footer','nav','svg']):n.decompose()
    value=text(soup)
    if '隱私' not in value:raise ValueError('privacy policy not found')
    return hashlib.sha256(value.encode()).hexdigest()

def safe_path(config,url):
    p=urlsplit(url);base=urlsplit(config['base'])
    return p.scheme=='https' and p.netloc==base.netloc and not p.query and not p.fragment and p.path.startswith(config['prefix']) and not p.username and not p.password

class PublicReader:
    def __init__(self,config):self.config=config;self.last=0;self.robot=None
    def get(self,url,robots=False):
        p=urlsplit(url)
        if p.scheme!='https' or p.netloc!=urlsplit(self.config['base']).netloc or p.query:raise ValueError('non-public or query URL rejected')
        if not robots and (self.robot is None or not self.robot.can_fetch(UA,url)):raise PermissionError('robots disallows URL')
        time.sleep(max(0,1.2-(time.monotonic()-self.last)));self.last=time.monotonic()
        encoded=urlunsplit((p.scheme,p.netloc,quote(p.path,safe='/%'),'', ''))
        with urlopen(Request(encoded,headers={'User-Agent':UA}),timeout=12) as r:
            if urlsplit(r.url).netloc!=p.netloc:raise ValueError('unexpected redirect host')
            raw=r.read(3_000_001)
            if len(raw)>3_000_000:raise ValueError('response too large')
            return raw.decode('utf-8')
    def prepare(self,approved):
        robot_url=self.config['base']+'/robots.txt'
        try:rules=self.get(robot_url,robots=True)
        except HTTPError as e:
            if e.code not in (404,410):raise
            rules='' # Standard missing-robots response; no API permission inferred.
        self.robot=RobotFileParser();self.robot.set_url(robot_url);self.robot.parse(rules.splitlines())
        if not self.robot.can_fetch(UA,self.config['base']+self.config['list']):raise PermissionError('robots disallows public list')
        if policy_digest(self.get(self.config['base']+self.config['privacy']))!=approved['policyDigest']:
            raise PermissionError('official policy changed; manual review required')

def discover(source,body):
    c=SOURCES[source];soup=soup_of(body);items={}
    selectors={'songshan':'#top_sliders .sliderscon > a','huashan':'a.exhi-card__link','pier2':'a[href*="/exhibition/info/"]'}
    for a in soup.select(selectors[source]):
        url=canonical_public_url(urljoin(c['base'],a.get('href','')))
        if not safe_path(c,url):continue
        title=text(a.select_one('.title' if source=='songshan' else 'h3' if source=='huashan' else '.thename'))
        if not title:continue
        if source=='songshan' and '展演攻略' in title:continue
        badge='free' if '[ 免票 ]' in title else 'paid' if '[ 售票 ]' in title else ''
        title=re.sub(r'^\[\s*(?:免票|售票)\s*\]\s*','',title)
        venue=text(a.select_one('.exhi-card__content-venue-text' if source=='huashan' else '.theplace'))
        items[url]={'title':title,'venue':venue,'badge':badge}
    if not items:raise ValueError('empty public list or changed structure')
    return items

def bounds(values):
    if len(values)!=2:raise ValueError('two explicit dates required')
    start,end=[date(x.replace('.','-')) for x in values]
    if end<start:raise ValueError('reversed dates')
    return start,end

def parse_detail(source,body,url,hint,prior):
    soup=soup_of(body);c=SOURCES[source]
    if source=='songshan':
        title=text(soup.select_one('p.inner_title'))
        dates=re.findall(r'\d{4}-\d{2}-\d{2}',text(soup.select_one('.under p.date')))
        venue=text(soup.select_one('.under p.place'))
    elif source=='huashan':
        title=text(soup.select_one('h1.news-title__title'))
        years=[text(n) for n in soup.select('.exhi-sidebar__date-years span') if re.fullmatch(r'\d{4}',text(n))]
        md=[text(n) for n in soup.select('.exhi-sidebar__date-md')]
        dates=[f'{years[0]}.{md[0]}',f'{years[-1]}.{md[-1]}'] if years and len(md)==2 else []
        section=next((n for n in soup.select('.exhi-sidebar__section') if text(n.select_one('h3')).startswith('地點')),None)
        venue=re.sub(r'^地點\s*[:：]\s*','',text(section))
    else:
        title=text(soup.select_one('h1'))
        dates=[]
        for selector in ['.datearea .starttime','.datearea .endtime']:
            n=soup.select_one(selector)
            if n:dates.append(text(n.select_one('.y'))+'.'+text(n.select_one('.d')))
        venue=hint.get('venue') or prior.get('venue','').removeprefix(c['name']+' · ')
    if not title or not venue:raise ValueError('missing title or venue')
    start,end=bounds(dates)
    # Price is a basic fact, not a snippet of the provider's prose. A missing
    # structured amount is not interpreted as free. Pier-2 list badges are clear.
    price='免費（仍請確認官方參加條件）' if hint.get('badge')=='free' else '付費，詳細票價請查官方' if hint.get('badge')=='paid' else '官網未提供結構化票價，請查官方'
    if not hint.get('badge') and prior.get('price'):
        price=prior['price'] if prior['price'].startswith('票價未逐日確認；') else '票價未逐日確認；前次人工核對：'+prior['price']
    category=prior.get('category') or '展演'
    full_venue=c['name']+' · '+venue.removeprefix(c['name']+' · ')
    summary=f'於{venue}舉辦的{category}活動，日期為{start}至{end}。開放時段與入場條件請查官方。'
    result={k:v for k,v in prior.items() if k in ('id','sourceUid','verificationNote')}
    address='高雄市鼓山區蓬萊路99號' if source=='pier2' and '蓬萊' in venue else c['address']
    result.update(id=prior.get('id') or source+'-'+hashlib.sha256(url.encode()).hexdigest()[:16],title=title,start=start,end=end,region=c['region'],venue=full_venue,address=address,park=source,price=price[:180],category=category,summary=summary[:180],url=url,source=source,sourceVersion='official-public-daily')
    return result

class RenderedReader:
    def __init__(self,browser,reader):
        from playwright.sync_api import sync_playwright
        self.p=sync_playwright().start()
        self.browser=self.p.chromium.launch(executable_path=browser,chromium_sandbox=True)
        self.page=self.browser.new_page(user_agent=UA)
        self.reader=reader
        self.page.route('**/*',self.route)
    def route(self,route):
        request=route.request;p=urlsplit(request.url)
        if request.resource_type in ('image','font','media') or '/upload/' in p.path or '/gallery/' in p.path:return route.abort()
        if p.netloc==urlsplit(self.reader.config['base']).netloc and not self.reader.robot.can_fetch(UA,request.url):return route.abort()
        return route.continue_()
    def get(self,url):
        if not self.reader.robot.can_fetch(UA,url):raise PermissionError('robots disallows rendered page')
        time.sleep(max(0,1.2-(time.monotonic()-self.reader.last)));self.reader.last=time.monotonic()
        response=self.page.goto(url,wait_until='networkidle',timeout=18000)
        if not response or response.status!=200 or urlsplit(self.page.url).netloc!=urlsplit(url).netloc:raise ValueError('public page unavailable')
        return self.page.content()
    def close(self):self.browser.close();self.p.stop()

def keep_source(previous,incoming,now):
    if not incoming:raise ValueError('empty facts; preserve last success')
    active=sum(e['end']>=now[:10] for e in previous)
    if active>=8 and len(incoming)<active*.5:raise ValueError('more than 50% source loss; preserve last success')
    return merge(previous,incoming,now)

def run(browser=None,source_names=None):
    path=ROOT/'data/curated.json';seeds=json.loads(path.read_text(encoding='utf-8'))
    status_path=ROOT/'data/venue-source-status.json'
    status=json.loads(status_path.read_text(encoding='utf-8')) if status_path.exists() else {}
    policies=json.loads((ROOT/'data/venue-policy.json').read_text(encoding='utf-8'))
    now=datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds');failures=0
    for source,c in SOURCES.items():
        if source_names and source not in source_names:continue
        now=datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
        previous=[e for e in seeds if e['source']==source];rendered=None
        try:
            reader=PublicReader(c);reader.prepare(policies[source])
            if source=='pier2':
                executable=browser or installed_browser()
                if not executable:raise RuntimeError('existing browser unavailable')
                rendered=RenderedReader(executable,reader);get=rendered.get
            else:get=reader.get
            found=discover(source,get(c['base']+c['list']))
            by_url={canonical_public_url(e['url']):e for e in previous}
            # Prefer the exact href actually observed on the official list.
            # Some official slugs include a trailing encoded space; do not trim
            # it or turn the same activity into an unverified guessed URL.
            for url,hint in found.items():
                matching=[e for e in previous if clean(e['title'])==hint['title']]
                if url not in by_url and len(matching)==1:by_url[url]=matching[0]
            targets=dict(found)
            found_ids={by_url[url]['id'] for url in found if url in by_url}
            for e in previous:
                url=canonical_public_url(e['url'])
                if e['id'] not in found_ids and e['end']>=now[:10] and safe_path(c,url):targets.setdefault(url,{'title':e['title'],'venue':e['venue'],'badge':''})
            if len(targets)>MAX_DETAILS:raise ValueError('public list exceeds daily detail cap; review required')
            incoming=[]
            for url,hint in targets.items():
                print(json.dumps({'source':source,'readingUrl':url},ensure_ascii=True),flush=True)
                event=parse_detail(source,get(url),url,hint,by_url.get(url,{}))
                if event['end']>=now[:10] or url in by_url:incoming.append(event)
                print(json.dumps({'source':source,'checkedId':event['id']},ensure_ascii=True),flush=True)
            succeeded_at=datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
            updated=keep_source(previous,incoming,succeeded_at)
            seeds=[e for e in seeds if e['source']!=source]+updated
            uncertain=sum(bool(e.get('verificationNote')) for e in updated)
            scope='公開首頁及已收錄的無查詢參數詳情；分頁受 robots 限制，未保證完整' if source=='huashan' else '公開展演清單及已收錄活動；不保證全場館活動完整'
            status[source]={'state':'ok','lastAttempt':now,'lastSuccess':succeeded_at,'count':len(updated),'checkedCount':len(targets),'message':f'每日官網基本事實更新成功；{scope}'+(f'；{uncertain}筆狀態仍待確認' if uncertain else '')}
        except Exception as e:
            failures+=1
            safe_reasons={'privacy policy not found','non-public or query URL rejected','robots disallows URL','robots disallows public list','official policy changed; manual review required','empty public list or changed structure','two explicit dates required','reversed dates','missing title or venue','empty facts; preserve last success','more than 50% source loss; preserve last success','existing browser unavailable','public list exceeds daily detail cap; review required','public page unavailable','unexpected redirect host','response too large'}
            reason=str(e) if str(e) in safe_reasons else f'HTTP {e.code}' if isinstance(e,HTTPError) else type(e).__name__
            status[source]={**status.get(source,{}),'state':'error','lastAttempt':now,'lastSuccess':status.get(source,{}).get('lastSuccess',max((x.get('lastSeen','') for x in previous),default='')),'count':len(previous),'message':f'每日官網更新未完成，保留最後成功資料（{reason}）；請查官方','reason':reason}
        finally:
            if rendered:rendered.close()
        print(json.dumps({'source':source,**status[source]},ensure_ascii=True),flush=True)
    atomic(path,seeds);atomic(status_path,status)
    return 1 if failures else 0

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--browser');parser.add_argument('--source',action='append',choices=list(SOURCES));args=parser.parse_args()
    raise SystemExit(run(args.browser,args.source))

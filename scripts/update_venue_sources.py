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
from update import atomic,clean,date,merge,safe_error_code
from recover_source_links import installed_browser

ROOT=Path(__file__).resolve().parents[1]
UA='TaiwanExhibitionTracker/0.4 (+https://github.com/spring01777-glitch/taiwan-exhibition-tracker)'
SOURCES={
    'songshan':{'base':'https://www.songshanculturalpark.org','list':'/exhibition','privacy':'/privacy','name':'松山文創園區','region':'臺北市','address':'臺北市信義區光復南路133號','prefix':'/exhibition/activity/'},
    'huashan':{'base':'https://www.huashan1914.com','list':'/exhibition','privacy':'/privacy','name':'華山1914','region':'臺北市','address':'臺北市中正區八德路一段1號','prefix':'/exhibition/'},
    'pier2':{'base':'https://pier2.org','list':'/exhibition/','privacy':'/privacy/','name':'駁二藝術特區','region':'高雄市','address':'高雄市鹽埕區大勇路1號','prefix':'/exhibition/info/'},
}
MAX_DETAILS=100
MAX_SKIP_RATIO=.2
ITEM_REASONS={'two explicit dates required','reversed dates','missing title or venue'}

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
    def __init__(self,config):self.config=config;self.last=0;self.robot=None;self.stage='robots-fetch'
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
        self.stage='robots-fetch'
        robot_url=self.config['base']+'/robots.txt'
        try:rules=self.get(robot_url,robots=True)
        except HTTPError as e:
            if e.code not in (404,410):raise
            rules='' # Standard missing-robots response; no API permission inferred.
        self.stage='robots-check'
        self.robot=RobotFileParser();self.robot.set_url(robot_url);self.robot.parse(rules.splitlines())
        if not self.robot.can_fetch(UA,self.config['base']+self.config['list']):raise PermissionError('robots disallows public list')
        self.stage='policy-fetch'
        policy=self.get(self.config['base']+self.config['privacy'])
        self.stage='policy-check'
        if policy_digest(policy)!=approved['policyDigest']:
            raise PermissionError('official policy changed; manual review required')

def discover(source,body):
    c=SOURCES[source];soup=soup_of(body);items={}
    selectors={'songshan':'#top_sliders .sliderscon > a','huashan':'a.exhi-card__link','pier2':'#event_list a[href*="/exhibition/info/"]'}
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
    # A single explicit official date is a one-day event, not a guessed range.
    if len(values)==1:values=values*2
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
        dates=([f'{years[0]}.{md[0]}',f'{years[-1]}.{md[-1]}'] if len(md)==2 else [f'{years[0]}.{md[0]}'] if len(md)==1 else []) if years else []
        section=next((n for n in soup.select('.exhi-sidebar__section') if text(n.select_one('h2, h3')).startswith('地點')),None)
        venue=re.sub(r'^地點\s*[:：]\s*','',text(section))
    else:
        title=text(soup.select_one('h1'))
        dates=[]
        for selector in ['.datearea .starttime','.datearea .endtime']:
            n=soup.select_one(selector)
            if n and text(n.select_one('.y')) and text(n.select_one('.d')):
                dates.append(text(n.select_one('.y'))+'.'+text(n.select_one('.d')))
        venue=hint.get('venue') or prior.get('venue','').removeprefix(c['name']+' · ')
    if not title or not venue:raise ValueError('missing title or venue')
    if not dates:
        start,end=None,None
    elif len(dates)==1 and (source!='songshan' or re.search(r'起|常設|長期|未定|持續|迄今',text(soup.select_one('.under p.date')))):
        start,end=date(dates[0].replace('.','-')),None
    else:
        start,end=bounds(dates)
    # Price is a basic fact, not a snippet of the provider's prose. A missing
    # structured amount is not interpreted as free. Pier-2 list badges are clear.
    price='免費（仍請確認官方參加條件）' if hint.get('badge')=='free' else '付費，詳細票價請查官方' if hint.get('badge')=='paid' else '官網未提供結構化票價，請查官方'
    if not hint.get('badge') and prior.get('price'):
        price=prior['price'] if prior['price'].startswith('票價未逐日確認；') else '票價未逐日確認；前次人工核對：'+prior['price']
    category=prior.get('category') or '展演'
    full_venue=c['name']+' · '+venue.removeprefix(c['name']+' · ')
    period=f'{start}至{end}' if start and end else f'{start}起，結束日期未明' if start else '日期待官方確認'
    summary=f'於{venue}舉辦的{category}活動，日期為{period}。開放時段與入場條件請查官方。'
    result={k:v for k,v in prior.items() if k in ('id','sourceUid','verificationNote')}
    address='高雄市鼓山區蓬萊路99號' if source=='pier2' and '蓬萊' in venue else c['address']
    result.update(id=prior.get('id') or source+'-'+hashlib.sha256(url.encode()).hexdigest()[:16],title=title,start=start,end=end,region=c['region'],venue=full_venue,address=address,park=source,price=price[:180],category=category,summary=summary[:180],url=url,source=source,sourceVersion='official-public-incremental')
    if end is None:
        result['verificationNote']=(result.get('verificationNote','')+'；結束日期未明，保留展示，請查官方。').lstrip('；')[:180]
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
        response=self.page.goto(url,wait_until='domcontentloaded',timeout=18000)
        if not response or response.status!=200 or urlsplit(self.page.url).netloc!=urlsplit(url).netloc:raise ValueError('public page unavailable')
        # The required facts load through the normal page's own JavaScript.
        # Analytics/social requests need not become idle for those facts to be
        # complete. Wait for actual fields instead of unrelated network traffic.
        if '/exhibition/info/' in urlsplit(url).path:
            self.page.wait_for_function("() => !!document.querySelector('h1')?.textContent.trim()",timeout=18000)
        else:
            self.page.wait_for_function("() => [...document.querySelectorAll('#event_list a[href*=\"/exhibition/info/\"] .thename')].some(n=>n.textContent.trim())",timeout=18000)
        return self.page.content()
    def close(self):self.browser.close();self.p.stop()

def keep_source(previous,incoming,now):
    if not incoming:raise ValueError('empty facts; preserve last success')
    active=sum(e['end']>=now[:10] for e in previous)
    if active>=8 and len(incoming)<active*.5:raise ValueError('more than 50% source loss; preserve last success')
    return merge(previous,incoming,now)

def incremental_merge(previous,incoming,now):
    """An incremental batch says nothing about omissions; preserve old facts verbatim."""
    fresh=list(incoming)
    ids={e['id'] for e in fresh}
    return [e for e in previous if e['id'] not in ids]+fresh


def run(browser=None,source_names=None,root=None,now=None,reader_factory=None,render_factory=None):
    root=root or ROOT;reader_factory=reader_factory or PublicReader;render_factory=render_factory or RenderedReader
    path=root/'data/curated.json';seeds=json.loads(path.read_text(encoding='utf-8'))
    status_path=root/'data/venue-source-status.json'
    status=json.loads(status_path.read_text(encoding='utf-8')) if status_path.exists() else {}
    state_path=root/'data/venue-crawl-state.json'
    states=json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else {}
    policies=json.loads((root/'data/venue-policy.json').read_text(encoding='utf-8'))
    now=now or datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
    today=now[:10];failures=0
    for source,c in SOURCES.items():
        if source_names and source not in source_names:continue
        previous=[e for e in seeds if e['source']==source]
        state=states.setdefault(source,{})
        # Successful existing snapshots are the migration baseline. Unknown-date
        # entries are retained too; never infer expiry from a missing end date.
        known=state.setdefault('known',{})
        for e in previous:
            if not e.get('url'):continue
            url=canonical_public_url(e['url'])
            known.setdefault(url,{'id':e['id'],'readAt':e.get('lastSeen',now)})
        budget=state.get('dailyBudget')
        if not budget or budget.get('date')!=today:
            reserved=MAX_DETAILS if budget is None and previous else 0
            budget=state['dailyBudget']={'date':today,'attempted':[],'reserved':reserved}
        state.setdefault('pending',{})
        state.setdefault('completed',{})
        rendered=None;reader=None;stage='prepare';checked=0;skipped=[];attempted=0
        def checkpoint():atomic(state_path,states)
        def progress():
            return dict(mode='new-only',dailyLimit=MAX_DETAILS,budgetDate=today,
                        dailyBudgetUsed=budget.get('reserved',0)+len(budget['attempted']),
                        dailyReserved=budget.get('reserved',0),pendingPages=len(state['pending']),
                        listReadAt=state.get('listReadAt'),listedPages=state.get('listedPages'),
                        coverageComplete=False)
        checkpoint()
        try:
            reader=reader_factory(c);reader.prepare(policies[source])
            def get(url):
                nonlocal rendered
                if source!='pier2':return reader.get(url)
                if rendered is None:
                    executable=browser or installed_browser()
                    if not executable:raise RuntimeError('existing browser unavailable')
                    rendered=render_factory(executable,reader)
                return rendered.get(url)
            if state.get('listReadAt')!=today:
                stage='list-fetch';body=get(c['base']+c['list'])
                stage='list-parse';found=discover(source,body)
                # Canonical URLs are the identity, not title or list position.
                # A new URL with a repeated title may be a genuinely new edition.
                old={u:h for u,h in state['pending'].items() if u in found and u not in known}
                new={u:h for u,h in found.items() if u not in known and u not in old}
                # First observed official-list order is not a proven newest sort.
                # Alternate new discoveries and backlog so neither starves.
                pending={}
                n,o=list(new.items()),list(old.items())
                for i in range(max(len(n),len(o))):
                    if i<len(n):pending[n[i][0]]=n[i][1]
                    if i<len(o):pending[o[i][0]]=o[i][1]
                state.update(pending=pending,listReadAt=today,listedPages=len(found),
                             ordering='new discoveries and backlog; official publication order unverified')
                checkpoint()
            remaining=max(0,MAX_DETAILS-progress()['dailyBudgetUsed'])
            targets=[(u,h) for u,h in state['pending'].items() if u not in budget['attempted']][:remaining]
            for url,hint in targets:
                stage='detail-fetch';budget['attempted'].append(url);attempted+=1
                # Reserve before I/O and rotate failures behind the backlog.
                state['pending'].pop(url);state['pending'][url]=hint;checkpoint()
                print(json.dumps({'source':source,'readingUrl':url},ensure_ascii=True),flush=True)
                body=get(url);stage='detail-parse'
                try:event=parse_detail(source,body,url,hint,{})
                except ValueError as item_error:
                    skipped.append({'url':url,'reason':str(item_error) if str(item_error) in ITEM_REASONS else 'VALIDATION_ERROR'})
                    if len(skipped)>max(1,len(targets)*MAX_SKIP_RATIO):raise ValueError('too many incomplete detail pages')
                    continue
                event.update(firstSeen=now,lastSeen=now,missingFromSource=False,revisions=[])
                state['completed'][url]=event
                known[url]={'id':event['id'],'readAt':now}
                state['pending'].pop(url);checked+=1;checkpoint()
            # Completed pages survive a prior failed run, without rereading them.
            incoming=list(state['completed'].values())
            updated=incremental_merge(previous,incoming,now)
            seeds=[e for e in seeds if e['source']!=source]+updated
            # Persist facts before dropping the completed-page recovery buffer.
            atomic(path,seeds)
            state['completed']={}
            checkpoint()
            scope='只涵蓋公開可見清單，不翻受限分頁，不保證全站最新100筆'
            status[source]={'state':'ok','lastAttempt':now,'lastSuccess':now,'count':len(updated),
                            'checkedCount':checked,'attemptedCount':attempted,'lastSuccessfulCheckedCount':checked,
                            'skipped':skipped,**progress(),
                            'message':f'僅新增活動增量收錄；本輪新讀{checked}筆，待讀{len(state["pending"])}筆；{scope}；已讀活動不重查'}
        except Exception as e:
            failures+=1
            prior=status.get(source,{})
            stage=getattr(reader,'stage',stage) if stage=='prepare' else stage
            reason=str(e) if isinstance(e,(ValueError,PermissionError,RuntimeError)) else f'HTTP {e.code}' if isinstance(e,HTTPError) else type(e).__name__
            status[source]={**prior,**progress(),'state':'error','lastAttempt':now,
                            'lastSuccess':prior.get('lastSuccess'),'count':len(previous),
                            'checkedCount':checked,'attemptedCount':attempted,
                            'lastSuccessfulCheckedCount':prior.get('lastSuccessfulCheckedCount',prior.get('checkedCount')),
                            'failureStage':stage,
                            'reasonCode':safe_error_code(e),'reason':reason,
                            'message':'增量更新未完成；保留最後成功資料與已讀進度，未完成項目之後續抓。'}
            checkpoint()
        finally:
            if rendered:rendered.close()
        print(json.dumps({'source':source,**status[source]},ensure_ascii=True),flush=True)
    atomic(path,seeds);atomic(status_path,status);checkpoint()
    return 1 if failures else 0

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--browser');parser.add_argument('--source',action='append',choices=list(SOURCES));args=parser.parse_args()
    raise SystemExit(run(args.browser,args.source))

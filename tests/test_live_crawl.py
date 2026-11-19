import json,sys,tempfile,unittest
from pathlib import Path
from urllib.error import HTTPError
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import crawl_live_sources as crawl
import live_sources as sources

TODAY='2026-10-10'
NOW=TODAY+'T09:00:00+08:00'

def arena_row(title,content,s='A1'):
    return {'Source':f'https://www.arena.taipei/News_Content.aspx?n=X&s={s}','title':title,'內容':content}

ARENA_ROWS=[
    arena_row('2026/10/17《XG世界巡迴演唱會《THE CORE》台北站》','XG 演唱會活動日期/時間：2026/10/17(六)19:30(18:30開放入場 / 預計21:10活動結束)主辦單位：寬宏聯絡電話：07票 &nbsp; 價：7,990 / 800售票系統：寬宏售票系統'),
    arena_row('2026/10/09《舊演唱會》','演唱會活動日期/時間：2026/10/09(五)17:00主辦單位：某','A2'),
    arena_row('2026/12/26、12/27《Mr. Children Tour 2026》','演唱會活動日期/時間：2026/12月26日(六) 15:30開場 / 17:00開演 2026/12月27日(日) 14:30開場 / 16:00開演主辦單位：雅慕斯','A3'),
]

class FakeFetcher:
    """Serves fixed bodies per URL; robots rules optional; no network."""
    routes={}
    calls=[]
    def __init__(self,base):
        self.base=base.rstrip('/')
    def get(self,url):
        FakeFetcher.calls.append(url)
        robots=FakeFetcher.routes.get(self.base+'/robots.txt','')
        if 'Disallow: /' in robots:raise crawl.SourceError('robots disallows URL')
        body=FakeFetcher.routes[url]
        if isinstance(body,Exception):raise body
        return body if isinstance(body,bytes) else body.encode()
    def text(self,url):return self.get(url).decode()
    def json(self,url):return json.loads(self.text(url))

class CrawlParsingTests(unittest.TestCase):
    def test_kktix_feed_filters_past_parent_listings_and_unclear_formats(self):
        feed={'entry':[
            {'url':'https://club.kktix.cc/events/a','title':'某某脫口秀專場','summary':'','content':'時間：2026/12/04 19:30(+0800)~21:00\n地點：Comedy Plus 卡米地＋ / 北市中山區復興北路480號'},
            {'url':'https://club.kktix.cc/events/b','title':'喜劇節 單口喜劇總覽','summary':'','content':'時間：2026/12/01 19:50(+0800) ~ 2026/12/03 21:30(+0800)\n地點：卡米地 / 台北市中山區'},
            {'url':'https://club.kktix.cc/events/c','title':'舊脫口秀','summary':'','content':'時間：2024/09/15 19:00(+0800)\n地點：Zepp New Taipei / 新北市新莊區'},
            {'url':'https://club.kktix.cc/events/d','title':'Live Podcast 同樂會','summary':'','content':'時間：2026/12/27 13:30(+0800)~15:30\n地點：群島藝術園區 / 臺中市西屯區'},
            {'url':'https://club.kktix.cc/events/e','title':'相聲失控','summary':'','content':'時間：2026/11/29 14:00(+0800)\n地點：西門紅樓 / 台北市萬華區'},
        ]}
        counter=crawl.Counter()
        events=crawl.parse_kktix('comedy',feed,TODAY,counter)
        self.assertEqual([e['sourceUid'] for e in events],['https://club.kktix.cc/events/a'])
        e=events[0]
        self.assertEqual((e['region'],e['venue'],e['sessions']),('臺北市','Comedy Plus 卡米地＋',[{'date':'2026-12-04','time':'19:30'}]))
        self.assertEqual(e['tickets'][0]['platform'],'KKTIX')
        reasons=counter.stats['reasons']
        self.assertEqual((reasons['MULTI_DAY_PARENT_LISTING'],reasons['PAST_EVENT'],reasons['INSUFFICIENT_STANDUP_EVIDENCE'],reasons['OTHER_PERFORMANCE_FORMAT']),(1,1,1,1))
        with self.assertRaises(crawl.SourceError):crawl.parse_kktix('comedy',{'entry':[]},TODAY,crawl.Counter())

    def test_arena_sessions_use_start_time_not_doors_or_end(self):
        content=crawl.clean(ARENA_ROWS[0]['內容'])
        self.assertEqual(crawl.arena_sessions(content),[{'date':'2026-10-17','time':'19:30'}])
        self.assertEqual(crawl.arena_sessions(crawl.clean(ARENA_ROWS[2]['內容'])),[{'date':'2026-12-26','time':'17:00'},{'date':'2026-12-27','time':'16:00'}])
        counter=crawl.Counter()
        events=crawl.parse_arena('concerts',ARENA_ROWS,TODAY,counter)
        self.assertEqual([e['title'] for e in events],['XG世界巡迴演唱會《THE CORE》台北站','Mr. Children Tour 2026'])
        self.assertIn('7,990',events[0]['price']);self.assertIn('寬宏售票系統',events[0]['saleNote'])
        self.assertEqual(counter.stats['reasons']['PAST_EVENT'],1)

    def test_tmc_dates_never_invent_sessions_inside_long_ranges(self):
        self.assertEqual(crawl.tmc_sessions('2026.11.21 19:30 (六) - 2026.11.21 21:30 (六)'),[{'date':'2026-11-21','time':'19:30'}])
        self.assertEqual(crawl.tmc_sessions('2026.11.13 19:00 (五) - 2026.11.14 18:00 (六)'),[{'date':'2026-11-13','time':'19:00'},{'date':'2026-11-14','time':'18:00'}])
        self.assertEqual(crawl.tmc_sessions('2026.10.10 (六)'),[{'date':'2026-10-10','time':None}])
        self.assertIsNone(crawl.tmc_sessions('2026.09.04 (五) ~ 2026.10.11 (日)'))

    def test_tmc_list_and_detail(self):
        base='https://www.tmc.taipei'
        listing=('<a class="c-card-clip-wrap" href="https://www.tmc.taipei/tw/blog/show/A"><span class="c-tag">演唱會</span><h3 class="c-card-clip__title">A 演唱會</h3></a>'
                 '<a class="c-card-clip-wrap" href="https://www.tmc.taipei/tw/blog/show/B"><span class="c-tag">展覽</span><h3 class="c-card-clip__title">B</h3></a>'
                 '<a class="c-card-clip-wrap" href="https://www.tmc.taipei/tw/blog/show/C?x=1"><span class="c-tag">演唱會</span><h3 class="c-card-clip__title">C</h3></a>')
        cards=crawl.parse_tmc_list(listing,base)
        self.assertEqual({u:c['tag'] for u,c in cards.items()},{base+'/tw/blog/show/A':'演唱會',base+'/tw/blog/show/B':'展覽'})
        detail=('<h2 class="event-title">A 演唱會</h2><aside class="event-detail detail-lg"><div class="date">2026.11.07 19:30 (六)</div>'
                '<div class="each-info"><h3 class="title">活動地點</h3><p class="content">臺北流行音樂中心 表演廳</p></div>'
                '<div class="each-info"><h3 class="title">票價</h3><p class="content">NT$ 4,280 / 2,480</p></div>'
                '<div class="each-info"><h3 class="title">購票連結</h3><p class="content"><a href="https://tixcraft.com/activity/detail/26x">售票</a><a href="https://evil.example/x">x</a></p></div></aside>')
        title,sessions,venue,price,tickets=crawl.parse_tmc_detail('concerts',detail,base+'/tw/blog/show/A',TODAY)
        self.assertEqual((title,venue,sessions),('A 演唱會','臺北流行音樂中心 表演廳',[{'date':'2026-11-07','time':'19:30'}]))
        self.assertEqual([t['platform'] for t in tickets],['拓元 tixCraft'])

    def test_opentix_schema_sessions_and_both_kind_decisions(self):
        block=lambda start,status='https://schema.org/EventScheduled':json.dumps({'@type':'Event','name':'《戀戀40》新年音樂會','description':'音樂會',
            'startDate':start,'eventStatus':status,'location':{'name':'衛武營音樂廳','address':{'addressLocality':'高雄市','streetAddress':'鳳山區'}},
            'offers':{'lowPrice':600,'highPrice':2800,'availabilityStarts':'2026-09-10T12:00:00'}},ensure_ascii=False)
        body=''.join(f'<script type="application/ld+json">{b}</script>' for b in (block('2027-01-01T14:30:00'),block('2027-01-02T14:30:00'),block('2027-01-03T14:30:00','https://schema.org/EventCancelled')))
        facts=crawl.parse_opentix(body,'https://www.opentix.life/event/1',TODAY)
        self.assertEqual(facts['sessions'],[{'date':'2027-01-01','time':'14:30'},{'date':'2027-01-02','time':'14:30'}])
        self.assertEqual((facts['region'],facts['price'],facts['saleAt']),('高雄市','NT$600–2,800','2026-09-10T12:00:00+08:00'))
        self.assertEqual(facts['decisions']['concerts'][0],'included');self.assertEqual(facts['decisions']['comedy'][0],'pending')
        self.assertNotIn('description',facts)
        with self.assertRaises(ValueError):crawl.parse_opentix('<html></html>','u',TODAY)

    def test_region_prefers_full_city_names(self):
        self.assertEqual(crawl.region_of('新北市新莊區'),'新北市')
        self.assertEqual(crawl.region_of('北市林森北路286號'),'臺北市')
        self.assertIsNone(crawl.region_of('NTUT Activity Center'))

class CrawlRunTests(unittest.TestCase):
    def root(self,tmp):
        root=Path(tmp)
        sources.write(root/'data/live-source-registry.json',{'schemaVersion':1,'sources':[
            {'id':'taipei-arena','name':'小巨蛋','url':'https://www.arena.taipei/','kinds':['concerts'],'adapter':'reviewed-json',
             'crawler':{'adapter':'arena-opendata','kinds':['concerts'],'base':'https://www.arena.taipei','feed':'/OpenData.aspx?SN=J','scope':'測試'}},
            {'id':'tixcraft','name':'拓元','url':'https://tixcraft.com/','kinds':['concerts'],'adapter':'reviewed-json'}]})
        FakeFetcher.calls=[]
        FakeFetcher.routes={'https://www.arena.taipei/robots.txt':'','https://www.arena.taipei/OpenData.aspx?SN=J':json.dumps(ARENA_ROWS,ensure_ascii=False)}
        return root

    def snapshot(self,root):
        return sources.read(sources.snapshot_path(root,'concerts','taipei-arena'),{})

    def test_success_keeps_reviewed_facts_and_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=self.root(tmp)
            reviewed=sources.validate_event({'sourceUid':'https://www.arena.taipei/News_Content.aspx?n=X&s=A1&sms=Y','title':'XG世界巡迴演唱會 THE CORE 台北站',
                'region':'臺北市','venue':'臺北小巨蛋','sessions':[{'date':'2026-10-17','time':'19:30'}],'price':'人工核對票價','saleAt':'2026-05-01T12:00:00+08:00',
                'sourceUrl':'https://www.arena.taipei/News_Content.aspx?n=X&s=A1&sms=Y'},'taipei-arena','2026-10-06')
            sources.write(sources.snapshot_path(root,'concerts','taipei-arena'),{'schemaVersion':1,'events':[reviewed],'status':{'status':'ok'}})
            self.assertTrue(crawl.run(root,fetch=FakeFetcher,now=NOW))
            snap=self.snapshot(root)
            self.assertEqual(len(snap['events']),2)
            xg=next(e for e in snap['events'] if 'XG' in e['title'])
            self.assertEqual((xg['id'],xg['price'],xg['saleAt'],xg['title']),(reviewed['id'],'人工核對票價','2026-05-01T12:00:00+08:00',reviewed['title']))
            self.assertEqual(snap['status']['mode'],'daily-crawl');self.assertEqual(snap['status']['status'],'ok')
            self.assertFalse(snap['status']['coverageComplete'])
            # Platforms without crawler config are never requested.
            self.assertFalse(any('tixcraft' in u for u in FakeFetcher.calls))

    def test_filled_sale_time_replaces_not_provided_note(self):
        url='https://www.opentix.life/event/9'
        old=sources.validate_event({'sourceUid':url,'title':'音樂會','region':'高雄市','venue':'衛武營','sessions':[{'date':'2027-01-01','time':'14:30'}],
            'sourceUrl':url,'saleNote':'一般開賣時間未提供，請見官方。'},'opentix','2026-10-06')
        raw=crawl.base_event('concerts',url,'音樂會','高雄市','衛武營',None,[{'date':'2027-01-01','time':'14:30'}],url,TODAY)
        raw.update(saleAt='2026-09-10T12:00:00+08:00',saleNote='開賣時間取自 OPENTIX 結構化資料；請以官方頁面為準。')
        merged=crawl.overlay({old['id']:old},raw,'opentix',TODAY)
        self.assertEqual(merged['saleAt'],'2026-09-10T12:00:00+08:00');self.assertNotIn('未提供',merged['saleNote'])

    def test_robots_http_and_mass_loss_failures_preserve_last_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=self.root(tmp)
            self.assertTrue(crawl.run(root,fetch=FakeFetcher,now=NOW))
            kept=self.snapshot(root)['events']
            FakeFetcher.routes['https://www.arena.taipei/robots.txt']='User-agent: *\nDisallow: /'
            self.assertFalse(crawl.run(root,fetch=FakeFetcher,now=NOW))
            snap=self.snapshot(root)
            self.assertEqual((snap['events'],snap['status']['status'],snap['status']['reason']),(kept,'error','robots disallows URL'))
            FakeFetcher.routes['https://www.arena.taipei/robots.txt']=''
            FakeFetcher.routes['https://www.arena.taipei/OpenData.aspx?SN=J']=HTTPError('u',503,'x',None,None)
            self.assertFalse(crawl.run(root,fetch=FakeFetcher,now=NOW))
            self.assertEqual(self.snapshot(root)['status']['reason'],'HTTP 503')
            self.assertEqual(self.snapshot(root)['events'],kept)

    def test_mass_loss_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=self.root(tmp)
            many=[arena_row(f'2026/11/{d:02d}《演唱會{d}》',f'演唱會活動日期/時間：2026/11/{d:02d}(六)19:30主辦單位：x',f'S{d}') for d in range(1,9)]
            FakeFetcher.routes['https://www.arena.taipei/OpenData.aspx?SN=J']=json.dumps(many,ensure_ascii=False)
            self.assertTrue(crawl.run(root,fetch=FakeFetcher,now=NOW))
            FakeFetcher.routes['https://www.arena.taipei/OpenData.aspx?SN=J']=json.dumps(many[:2],ensure_ascii=False)
            self.assertFalse(crawl.run(root,fetch=FakeFetcher,now=NOW))
            snap=self.snapshot(root)
            self.assertEqual((len(snap['events']),snap['status']['reason']),(8,'more than 50% source loss; preserve last success'))

    def test_fetcher_enforces_host_robots_and_size(self):
        served={'https://a.example/robots.txt':b'User-agent: *\nDisallow: /private','https://a.example/ok':b'{}','https://a.example/private/x':b'no'}
        f=crawl.Fetcher('https://a.example',opener=lambda u:served[u],delay=0)
        self.assertEqual(f.json('https://a.example/ok'),{})
        with self.assertRaises(crawl.SourceError):f.get('https://a.example/private/x')
        with self.assertRaises(crawl.SourceError):f.get('https://b.example/ok')
        with self.assertRaises(crawl.SourceError):f.get('http://a.example/ok')
        missing=crawl.Fetcher('https://c.example',opener=lambda u:(_ for _ in ()).throw(HTTPError(u,404,'x',None,None)) if u.endswith('robots.txt') else b'1',delay=0)
        self.assertEqual(missing.get('https://c.example/any'),b'1')

class ArenaFormatRegressionTests(unittest.TestCase):
    def test_spaced_dates_fullwidth_clocks_do_not_take_door_times(self):
        content='活動日期/時間：2027 / 4 / 17（六）19：00（17：00開放入場）2027 / 4 / 18（日）16：30（15：00開放入場）實際開演時間以現場為主票價：4500'
        self.assertEqual(crawl.arena_sessions(content),[
            {'date':'2027-04-17','time':'19:00'}, {'date':'2027-04-18','time':'16:30'}])
        counter=crawl.Counter()
        rows=[arena_row('2027/4/17、4/18《張震嶽 跟著感覺走 2027 台北演唱會》',content)]
        events=crawl.parse_arena('concerts',rows,'2026-11-19',counter)
        self.assertEqual(len(events),1)
        self.assertEqual(counter.stats['failed'],0)
        self.assertEqual(events[0]['sessions'][1]['time'],'16:30')

    def test_date_validation_and_legacy_month_format_survive(self):
        for bad in ['2027 / 2 / 29（六）19：00','2028 / 13 / 1（六）19：00','2028 / 2 / 29（六）25：00']:
            with self.assertRaises(ValueError):crawl.arena_sessions('活動日期：'+bad)
        self.assertEqual(crawl.arena_sessions('活動日期：2028 / 2 / 29（六）19：00'),[{'date':'2028-02-29','time':'19:00'}])
        self.assertEqual(crawl.arena_sessions('活動日期：2026/12月31日（四）23:30 2027/1/1（五）00:30'),[
            {'date':'2026-12-31','time':'23:30'}, {'date':'2027-01-01','time':'00:30'}])

class OpentixScheduleTests(unittest.TestCase):
    base = 'https://www.opentix.life'

    def setup_feed(self, ids):
        FakeFetcher.calls = []
        FakeFetcher.routes = {self.base + '/robots.txt': ''}
        self.feed(ids)
        for i in ids:
            FakeFetcher.routes[self.url(i)] = '<script type="application/ld+json">' + json.dumps({
                '@type': 'Event', 'name': f'演唱會{i}', 'startDate': '2027-12-01T19:30:00',
                'location': {'name': '臺北演出廳', 'address': {'addressLocality': '臺北市'}}}) + '</script>'
        return {'id': 'opentix', 'name': 'OPENTIX', 'url': self.base,
                'kinds': ['concerts', 'comedy'], 'adapter': 'reviewed-json',
                'crawler': {'adapter': 'opentix-sitemap', 'kinds': ['concerts', 'comedy'],
                            'base': self.base, 'sitemap': '/otWebSitemap.xml',
                            'maxPagesPerDay': 100, 'scope': 'test'}}

    def url(self, i):
        return f'{self.base}/event/{i}'

    def feed(self, ids):
        # Deliberately not publication ordered; lastmod is not a creation date.
        FakeFetcher.routes[self.base + '/otWebSitemap.xml'] = (
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' +
            ''.join(f'<url><loc>{self.url(i)}</loc><lastmod>2026-10-10</lastmod></url>' for i in ids) + '</urlset>')

    def reads(self):
        return [u for u in FakeFetcher.calls if '/event/' in u]

    def test_daily_cap_shared_across_runs_and_next_day_resume(self):
        entry = self.setup_feed(range(1, 252))
        entry['crawler']['maxPagesPerDay'] = 1000  # hard safety ceiling remains 100
        state = {}
        crawl.refresh_opentix(entry, FakeFetcher, TODAY, state)
        self.assertEqual((len(self.reads()), state['pendingPages']), (100, 151))
        state = json.loads(json.dumps(state))  # restart from durable JSON
        crawl.refresh_opentix(entry, FakeFetcher, TODAY, state)
        self.assertEqual(len(self.reads()), 100)
        self.assertEqual(FakeFetcher.calls.count(self.base + '/otWebSitemap.xml'), 1)
        crawl.refresh_opentix(entry, FakeFetcher, '2026-10-11', state)
        self.assertEqual((len(self.reads()), state['pendingPages']), (200, 51))
        crawl.refresh_opentix(entry, FakeFetcher, '2026-10-12', state)
        self.assertEqual((len(self.reads()), len(set(self.reads())), state['pendingPages']), (251, 251, 0))
        crawl.refresh_opentix(entry, FakeFetcher, '2026-10-13', state)
        self.assertEqual(len(self.reads()), 251)

    def test_reordering_new_urls_and_disappearing_known_url(self):
        entry = self.setup_feed(range(1, 152))
        state = {}
        crawl.refresh_opentix(entry, FakeFetcher, TODAY, state)
        known = next(iter(state['pages']))
        known_id = int(known.rsplit('/', 1)[1])
        body = FakeFetcher.routes[self.url(1)]
        # New item has a smaller ID and appears at the end; no ID cutoff or offset.
        FakeFetcher.routes[self.url(0)] = body
        self.feed(list(reversed([i for i in range(1, 152) if i != known_id])) + [0])
        crawl.refresh_opentix(entry, FakeFetcher, '2026-10-11', state)
        self.assertEqual(self.reads()[100], self.url(0))
        self.assertIn(known, state['pages'])
        self.feed(range(0, 152))
        crawl.refresh_opentix(entry, FakeFetcher, '2026-10-12', state)
        self.assertEqual(len(self.reads()), 152)
        self.assertEqual(len(set(self.reads())), 152)

    def test_failed_attempt_counts_and_is_retried_next_day_without_losing_progress(self):
        entry = self.setup_feed(range(1, 105))
        state = {}
        saved = []
        bad = self.url(10)  # lexicographic second URL after /1
        body = FakeFetcher.routes[bad]
        FakeFetcher.routes[bad] = HTTPError(bad, 502, 'bad gateway', None, None)
        with self.assertRaises(HTTPError):
            crawl.refresh_opentix(entry, FakeFetcher, TODAY, state,
                                  checkpoint=lambda: saved.append(json.loads(json.dumps(state))))
        self.assertEqual((state['dailyBudgetUsed'], len(state['pages'])), (2, 1))
        self.assertIn(bad, saved[-1]['dailyBudget']['attempted'])
        self.assertIn(bad, state['pendingUrls'])
        crawl.refresh_opentix(entry, FakeFetcher, TODAY, state)
        self.assertEqual(len(self.reads()), 100)
        self.assertEqual(self.reads().count(bad), 1)
        FakeFetcher.routes[bad] = body
        crawl.refresh_opentix(entry, FakeFetcher, '2026-10-11', state)
        self.assertEqual((len(state['pages']), state['pendingPages']), (104, 0))
        self.assertEqual(self.reads().count(bad), 2)

    def test_new_discoveries_get_priority_without_starving_backlog(self):
        entry = self.setup_feed(range(1, 301))
        state = {}
        crawl.refresh_opentix(entry, FakeFetcher, TODAY, state)
        old_pending = set(state['pendingUrls'])
        for i in range(301, 401):
            FakeFetcher.routes[self.url(i)] = FakeFetcher.routes[self.url(1)]
        self.feed(range(1, 401))
        crawl.refresh_opentix(entry, FakeFetcher, '2026-10-11', state)
        today_reads = self.reads()[100:]
        self.assertEqual(len(set(today_reads) & old_pending), 50)
        self.assertEqual(sum(int(u.rsplit('/', 1)[1]) >= 301 for u in today_reads), 50)

    def test_sitemap_failure_does_not_erase_queue_or_spend_detail_budget(self):
        entry = self.setup_feed([1, 2])
        state = {'dailyBudget': {'date': TODAY, 'attempted': [], 'reserved': 0},
                 'pendingUrls': [self.url(1)]}
        FakeFetcher.routes[self.base + '/otWebSitemap.xml'] = HTTPError('u', 502, 'x', None, None)
        with self.assertRaises(HTTPError):
            crawl.refresh_opentix(entry, FakeFetcher, TODAY, state)
        self.assertEqual(state['pendingUrls'], [self.url(1)])
        self.assertEqual(state['dailyBudgetUsed'], 0)
        self.assertEqual(self.reads(), [])

    def test_known_pages_never_refetched_after_many_days_or_changed_details(self):
        entry = self.setup_feed([1, 2])
        state = {}
        crawl.refresh_opentix(entry, FakeFetcher, TODAY, state)
        previous = json.loads(json.dumps(state['pages']))
        FakeFetcher.calls = []
        FakeFetcher.routes[self.url(1)] = HTTPError('u', 502, 'would fail if refetched', None, None)
        FakeFetcher.routes[self.url(2)] = FakeFetcher.routes[self.url(2)].replace('2027-12-01', '2028-12-01')
        entry['crawler']['refreshDays'] = 1  # even stale configuration cannot enable rotation
        for day in ('2026-10-24', '2027-01-01', '2028-01-01'):
            crawl.refresh_opentix(entry, FakeFetcher, day, state)
        self.assertEqual(self.reads(), [])
        self.assertEqual(state['pages'], previous)
        self.assertEqual(state['dailyBudgetUsed'], 0)

    def test_old_rotation_queue_is_dropped_without_resetting_same_day_budget(self):
        entry = self.setup_feed([1, 2, 3])
        state = {}
        entry['crawler']['maxPagesPerDay'] = 1
        crawl.refresh_opentix(entry, FakeFetcher, TODAY, state)
        state['recheckUrls'] = [self.url(1)]
        state['pendingUrls'].insert(0, self.url(1))  # malformed legacy duplicate
        state['dailyBudget']['refreshAttempted'] = [self.url(1)]
        FakeFetcher.calls = []
        state = json.loads(json.dumps(state))
        crawl.refresh_opentix(entry, FakeFetcher, TODAY, state)
        self.assertEqual(self.reads(), [])
        self.assertNotIn('recheckUrls', state)
        self.assertNotIn(self.url(1), state['pendingUrls'])
        self.assertEqual(state['dailyBudgetUsed'], 1)
        crawl.refresh_opentix(entry, FakeFetcher, '2026-10-24', state)
        self.assertEqual(self.reads(), [self.url(2)])
        self.assertEqual(state['dailyRefreshAttempts'], 0)

    def test_initial_explicit_cancellation_is_still_recorded(self):
        entry = self.setup_feed([1])
        FakeFetcher.routes[self.url(1)] = FakeFetcher.routes[self.url(1)].replace(
            '"@type": "Event"', '"@type": "Event", "eventStatus": "https://schema.org/EventCancelled"')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sources.write(root / 'data/live-source-registry.json', {'schemaVersion': 1, 'sources': [entry]})
            self.assertTrue(crawl.run(root, fetch=FakeFetcher, now=NOW))
            path = sources.snapshot_path(root, 'concerts', 'opentix')
            event = sources.read(path, {})['events'][0]
            self.assertEqual(event['status'], 'cancelled')
            self.assertEqual(event['sessions'][0]['date'], '2027-12-01')

    def test_legacy_budget_is_conservative_and_cache_is_not_refetched(self):
        entry = self.setup_feed([1, 2])
        state = {'pages': {self.url(1): {'readAt': TODAY, 'facts': None}}}
        crawl.refresh_opentix(entry, FakeFetcher, TODAY, state)
        self.assertEqual(self.reads(), [])
        self.assertEqual(state['dailyBudget']['reserved'], 100)
        crawl.refresh_opentix(entry, FakeFetcher, '2026-10-11', state)
        self.assertEqual(self.reads(), [self.url(2)])

    def test_run_persists_failure_progress_and_preserves_both_snapshots(self):
        entry = self.setup_feed([1, 2, 3])
        entry['crawler']['maxPagesPerDay'] = 1
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sources.write(root / 'data/live-source-registry.json', {'schemaVersion': 1, 'sources': [entry]})
            self.assertTrue(crawl.run(root, fetch=FakeFetcher, now=NOW))
            paths = [sources.snapshot_path(root, kind, 'opentix') for kind in ('concerts', 'comedy')]
            before = [sources.read(p, {})['events'] for p in paths]
            FakeFetcher.routes[self.url(2)] = HTTPError(self.url(2), 502, 'bad gateway', None, None)
            self.assertFalse(crawl.run(root, fetch=FakeFetcher, now='2026-10-11T09:00:00+08:00'))
            for p, events in zip(paths, before):
                snapshot = sources.read(p, {})
                self.assertEqual(snapshot['events'], events)
                self.assertEqual(snapshot['status']['dailyBudgetUsed'], 1)
                self.assertEqual(snapshot['status']['status'], 'error')
            state = sources.read(root / 'data/live-sources/crawl-state.json', {})['opentix']
            self.assertEqual(state['dailyBudget']['attempted'], [self.url(2)])
            self.assertIn(self.url(1), state['pages'])
            self.assertIn(self.url(2), state['pendingUrls'])

class CrossSourceMergeTests(unittest.TestCase):
    def ev(self,source,title,venue,date,time,url):
        return sources.validate_event({'sourceUid':url,'title':title,'region':'屏東縣','venue':venue,'sessions':[{'date':date,'time':time}],'sourceUrl':url,
            'tickets':[{'platform':'KKTIX','url':url,'checkedAt':'2026-10-06','sessions':[{'date':date,'time':time}],'saleAt':'2026-10-01T12:00:00+08:00'}]},source,'2026-10-06')
    def test_listing_prefix_and_venue_label_do_not_duplicate_a_show(self):
        manual=self.ev('manual','2026 佳諭單口喜劇專場《Get 婚》','打舖2號店','2026-11-14','20:00','https://club.kktix.cc/events/a')
        crawled=self.ev('comedyclub','【11/14 屏東場】2026 佳諭單口喜劇專場《Get 婚》','屏東 打舖2號店','2026-11-14','20:00','https://club.kktix.cc/events/a')
        merged=sources.reconcile([manual,crawled])
        self.assertEqual(len(merged),1)
        self.assertEqual([t.get('saleAt') for t in merged[0]['tickets']],['2026-10-01T12:00:00+08:00'])
    def test_different_time_or_title_stays_separate(self):
        a=self.ev('manual','佳諭單口喜劇專場','打舖2號店','2026-11-14','20:00','https://club.kktix.cc/events/a')
        b=self.ev('comedyclub','佳諭單口喜劇專場','屏東 打舖2號店','2026-11-14','16:00','https://club.kktix.cc/events/b')
        c=self.ev('comedyclub','另一個節目','屏東 打舖2號店','2026-11-14','20:00','https://club.kktix.cc/events/c')
        self.assertEqual(len(sources.reconcile([a,b,c])),3)

class ConcertGenreTests(unittest.TestCase):
    def test_genre_rules(self):
        g=lambda t:sources.concert_genre({'title':t})
        cases={'Stray Kids World Tour ＜RUN IT TAIPEI＞':'流行／搖滾演唱會','郭子＆浮花樂隊 原來的那首歌 Live':'流行／搖滾演唱會',
               '【2026 TSO 大師系列】殷巴爾與TSO之馬勒第九號':'古典／室內樂','2026鍾家瑋鋼琴獨奏會':'古典／室內樂','WJSO新年音樂會':'古典／室內樂',
               '【TCO】音緣－吳大江作品音樂會':'國樂／傳統','返聞—黃意棻古琴碩士畢業音樂會':'國樂／傳統',
               '木樓合唱團《人聲旅歌》':'合唱／聲樂','2026臺北爵士大樂隊《感爵臺灣》':'爵士','大漢天聲-陸軍樂隊訓練成果發表音樂會':'管樂',
               '《好年》新年音樂會':'其他音樂會','JOJI SOLARIS':'流行／搖滾演唱會','臺中國家歌劇院 also 演唱會':'流行／搖滾演唱會'}
        for title,label in cases.items():self.assertEqual(g(title),label,title)

if __name__=='__main__':
    unittest.main()

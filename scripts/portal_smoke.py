"""Sequential desktop/mobile integration QA, using installed Playwright."""
import argparse,json,re
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--url',default='http://127.0.0.1:8765/');parser.add_argument('--external',action='store_true');args=parser.parse_args()
report={'viewports':[],'modules':[],'external':[]};errors=[]
key=lambda s:re.sub(r'\W','',s).casefold()
with sync_playwright() as p:
    browser=p.chromium.launch();page=browser.new_page()
    page.on('pageerror',lambda e:errors.append(str(e)))
    for width in [1440,390]:
        page.set_viewport_size({'width':width,'height':900})
        page.goto(args.url,wait_until='networkidle')
        for label,name in [('演唱會','concerts.html'),('脫口秀','comedy.html')]:
            assert page.get_by_role('navigation').get_by_role('link',name=label,exact=True).get_attribute('href')==name
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        for kind in ['concerts','comedy']:
            page.goto(args.url+kind+'.html',wait_until='networkidle');page.wait_for_selector('.card')
            data=page.evaluate('fetch(document.body.dataset.events || "data/concerts.json").then(r=>r.json())')['events']
            today=page.evaluate('ConcertFilters.todayTW()')
            count=0
            for city in sorted({e['region'] for e in data}):
                page.locator('#region').select_option(city)
                options=page.locator('#venue option').evaluate_all('(os)=>os.map(o=>o.value).filter(Boolean)')
                assert set(options)=={e['venue'] for e in data if e['region']==city}
                for venue in options:
                    page.locator('#venue').select_option(venue)
                    expected=sum(e['region']==city and e['venue']==venue and e['status']!='cancelled' and any(s['date']>=today and s.get('status')!='cancelled' for s in e['sessions']) for e in data)
                    assert page.locator('.card').count()==expected
                    count+=1
            page.locator('button[type=reset]').click();page.wait_for_timeout(100)
            page.locator('#view').select_option('all');sample=data[0]
            page.locator('#query').fill(sample['title']);page.locator('#date').fill(sample['sessions'][0]['date'])
            assert page.locator('.card').count()>=1
            page.locator('#date').fill('1900-01-01');assert page.locator('.card').count()==0
            page.locator('button[type=reset]').click();page.wait_for_timeout(100)
            unverified=next((e for e in data if e['sourceUrl'].startswith('https://data.gov.tw/dataset/')),None)
            if unverified:
                page.locator('#view').select_option('all');page.locator('#query').fill(unverified['title'])
                card=page.locator('.card').first
                assert card.get_by_role('link',name='資料集來源（非活動詳情）').count()==1
                assert card.get_by_role('link',name='官方售票活動頁').count()==0
                assert unverified['sourceUid'] in card.inner_text()
                page.locator('button[type=reset]').click();page.wait_for_timeout(100)
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            report['modules'].append({'module':kind,'width':width,'records':len(data),'regionVenuePairs':count,'dateQueryReset':'passed'})
            if width==390:
                out=ROOT/'output/portal';out.mkdir(parents=True,exist_ok=True)
                page.screenshot(path=str(out/(kind+'-mobile.png')),full_page=True)
        report['viewports'].append(width)
    if args.external:
        # One verified concert and one verified comedy link; no ticket purchase.
        # Tixcraft returned 403 in the prior diagnostic; do not retry/bypass it.
        for kind,token,expected in [('concerts','Paul Gilbert','Paul Gilbert'),('comedy','藍恩','藍恩')]:
            page.goto(args.url+kind+'.html',wait_until='networkidle')
            page.locator('#query').fill(token)
            card=page.locator('.card').first
            with page.expect_popup() as opened:card.get_by_role('link',name='官方售票活動頁').click()
            popup=opened.value
            try:
                popup.wait_for_load_state('domcontentloaded',timeout=20000);popup.wait_for_timeout(1000)
                body=popup.inner_text('body')
                evidence={'module':kind,'url':popup.url,'pageTitle':popup.title(),'headings':popup.locator('h1,h2').all_text_contents()[:3],'expected':expected,'matched':key(expected) in key(body),'status':popup.evaluate('performance.getEntriesByType("navigation")[0]?.responseStatus')}
                print(json.dumps(evidence,ensure_ascii=True),flush=True)
                (ROOT/'output/portal/external-diagnostic.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
                assert key(expected) in key(body)
                report['external'].append({'module':kind,'url':popup.url,'expectedArtistMatched':True})
            finally:popup.close()
    assert not errors,errors
    browser.close()
out=ROOT/'output/portal';out.mkdir(parents=True,exist_ok=True)
(out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=True))

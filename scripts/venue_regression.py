"""Every region/venue combination, long mobile selection and incompatible changes."""
import argparse,json
from collections import Counter
from pathlib import Path
from playwright.sync_api import sync_playwright
p=argparse.ArgumentParser();p.add_argument('--url',default='http://127.0.0.1:8765/');args=p.parse_args()
out=Path(__file__).resolve().parents[1]/'output/venue-regression';out.mkdir(parents=True,exist_ok=True)
checks=[];errors=[];combinations=0
with sync_playwright() as pw:
    browser=pw.chromium.launch();page=browser.new_page(viewport={'width':390,'height':844})
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.on('console',lambda m:errors.append(m.text) if m.type=='error' else None)
    page.goto(args.url,wait_until='networkidle');page.wait_for_selector('.card')
    data=page.request.get(args.url+'data/exhibitions.json').json()
    today=page.evaluate("new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Taipei',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date())")
    regions=page.locator('#region option').evaluate_all('(a)=>a.map(e=>e.value)')
    def match(e,r):return not r or (e['region'] in ('臺北市','新北市') if r=='north' else e['region']==r)
    def options():return set(page.locator('#park option').evaluate_all('(a)=>a.map(e=>e.value)'))
    def verify(expected):
        assert page.locator('#result-count').inner_text().startswith(f'找到 {len(expected)} 場展覽')
        while page.locator('#more').is_visible():page.locator('#more').click()
        assert sorted(page.locator('.card h3').all_text_contents())==sorted(e['title'] for e in expected)
        assert page.locator('.empty').count()==int(not expected)
    for r in regions:
        page.locator('#region').select_option(r);page.locator('#park').select_option('')
        local=[e for e in data['events'] if match(e,r)]
        available={v['id'] for e in local for v in e['locations']}
        assert options()==available|{''}
        active=[e for e in local if e['end']>=today];verify(active)
        for vid in sorted(available):
            page.locator('#park').select_option(vid)
            verify([e for e in active if any(v['id']==vid for v in e['locations'])]);combinations+=1
        checks.append({'region':r,'events':len(active),'venueOptions':len(available),'status':'passed'})
    locations={v['id']:v for e in data['events'] for v in e['locations']}
    for vid,location in locations.items():
        page.locator('#region').select_option('');page.locator('#park').select_option(vid)
        target='高雄市' if location['region']!='高雄市' else '臺北市'
        page.locator('#region').select_option(target)
        assert page.locator('#park').input_value()=='' and vid not in options()
        verify([e for e in data['events'] if e['region']==target and e['end']>=today])
    page.locator('#region').select_option('');page.locator('#park').select_option(next(iter(locations)))
    page.get_by_role('button',name='清除篩選').click();page.wait_for_timeout(100)
    assert page.locator('#region').input_value()=='' and page.locator('#park').input_value()==''
    assert options()==set(locations)|{''} and page.locator('.card').count()==24
    page.locator('#region').select_option('高雄市');page.locator('#filters').scroll_into_view_if_needed()
    assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
    page.screenshot(path=str(out/'all-venues-mobile.png'))
    assert not errors,errors
    browser.close()
report={'url':args.url,'events':len(data['events']),'venueOptions':len(locations),'venueStatusEvents':dict(Counter(e['venueStatus'] for e in data['events'])),'regionOptions':len(regions),'regionVenueCombinations':combinations,'everyVenueCrossRegion':len(locations),'checks':checks,'errors':errors}
(out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,ensure_ascii=True))

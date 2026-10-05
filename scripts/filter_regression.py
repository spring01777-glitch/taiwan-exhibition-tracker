"""Browser regression for region/venue linkage against local or deployed real data."""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

parser=argparse.ArgumentParser()
parser.add_argument('--url',default='http://127.0.0.1:8765/')
parser.add_argument('--observe-before',action='store_true')
args=parser.parse_args()
root=Path(__file__).resolve().parents[1]
out=root/'output/filter-regression'
out.mkdir(parents=True,exist_ok=True)
checks=[]
errors=[]
with sync_playwright() as p:
    browser=p.chromium.launch()
    page=browser.new_page()
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.on('console',lambda m:errors.append(m.text) if m.type=='error' else None)
    page.goto(args.url,wait_until='networkidle')
    page.wait_for_selector('.card')
    def options():
        return page.locator('#park option').evaluate_all('(a)=>a.map(x=>x.value)')
    def only_region(region):
        assert page.locator('.card').count()>0
        assert all(x.startswith(region+' ·') for x in page.locator('.card-top > span:first-child').all_text_contents())
    if args.observe_before:
        page.locator('#park').select_option('pier2')
        page.locator('#region').select_option('臺北市')
        print(json.dumps({'url':args.url,'parkOptions':options(),'selectedPark':page.locator('#park').input_value(),'cards':page.locator('.card').count(),'empty':page.locator('.empty').count()},ensure_ascii=True))
    else:
        for width in (1440,390):
            page.set_viewport_size({'width':width,'height':844})
            page.locator('#filters').evaluate('(f)=>f.reset()')
            page.wait_for_timeout(100)
            assert set(options())=={'','songshan','huashan','pier2'}
            page.locator('#park').select_option('pier2')
            only_region('高雄市')
            page.locator('#region').select_option('臺北市')
            assert options()==['','songshan','huashan']
            assert page.locator('#park').input_value()==''
            only_region('臺北市')
            assert '已清除' in page.locator('#result-count').inner_text()
            checks.append(f'{width}px: Pier-2 then Taipei clears venue; no Kaohsiung option or cards')
            page.locator('#park').select_option('songshan')
            only_region('臺北市')
            assert all('松山文創' in x for x in page.locator('.card dd:nth-of-type(2)').all_text_contents())
            page.locator('#date').fill('2026-10-10')
            assert page.locator('.card').count()>0
            page.locator('#region').select_option('高雄市')
            assert options()==['','pier2']
            assert page.locator('#park').input_value()==''
            assert page.locator('#date').input_value()=='2026-10-10'
            only_region('高雄市')
            checks.append(f'{width}px: Taipei then Songshan; switch to Kaohsiung keeps date and clears incompatible venue')
            page.locator('#park').select_option('pier2')
            only_region('高雄市')
            page.locator('#query').fill('DigiWave')
            assert page.locator('.card').count()==1
            page.locator('#region').select_option('')
            assert set(options())=={'','songshan','huashan','pier2'}
            assert page.locator('#park').input_value()=='pier2'
            assert page.locator('#query').input_value()=='DigiWave'
            assert page.locator('.card').count()==1
            checks.append(f'{width}px: region, venue, date and search intersect; all regions restores venues')
            page.get_by_role('button',name='清除篩選').click()
            page.wait_for_timeout(100)
            assert page.locator('#region').input_value()==''
            assert page.locator('#park').input_value()==''
            assert page.locator('#date').input_value()==''
            assert page.locator('#query').input_value()==''
            assert set(options())=={'','songshan','huashan','pier2'}
            assert page.locator('.card').count()==24
            page.locator('#region').select_option('新北市')
            assert options()==['']
            only_region('新北市')
            page.locator('#region').select_option('north')
            assert options()==['','songshan','huashan']
            page.locator('#park').select_option('huashan')
            only_region('臺北市')
            assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
            checks.append(f'{width}px: reset, New Taipei without venues, northern grouping and no overflow')
            page.locator('#region').select_option('高雄市')
            page.locator('#filters').scroll_into_view_if_needed()
            page.screenshot(path=str(out/f'linked-{width}.png'))
        assert not errors,errors
        result={'url':args.url,'checks':checks,'errors':errors}
        (out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(result,ensure_ascii=True))
    browser.close()

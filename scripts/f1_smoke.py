"""One-browser desktop/mobile acceptance, optional real outbound clicks."""
import argparse,json
from pathlib import Path
from playwright.sync_api import sync_playwright
parser=argparse.ArgumentParser();parser.add_argument('--url',default='http://127.0.0.1:8781/');parser.add_argument('--external',action='store_true');args=parser.parse_args()
report={'viewports':[],'external':[]};out=Path('output/f1-qa');out.mkdir(parents=True,exist_ok=True)
with sync_playwright() as p:
    browser=p.chromium.launch();context=browser.new_context(timezone_id='America/New_York');page=context.new_page();errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
    for width in (1440,390):
        page.set_viewport_size({'width':width,'height':844});page.goto(args.url+'f1.html',wait_until='networkidle');page.wait_for_selector('#race-grid .card')
        assert page.locator('#season option').count()==1
        assert '新加坡' in page.locator('#next-race').inner_text()
        assert '2026-10-11 20:00 台灣' in page.locator('#next-race').inner_text()
        assert page.locator('#next-race li').count()==5
        assert '衝刺排位' in page.locator('#next-race').inner_text()
        assert 'Jolpica' in page.locator('#f1-source-status').inner_text()
        upcoming=page.locator('#race-grid .card').count();assert upcoming==7
        page.locator('#range').select_option('all');assert page.locator('#race-grid .card').count()==23
        text=page.locator('#race-grid').inner_text();assert '台灣跨日 +1 天' not in text # collapsed details are not presented as open
        mexico=page.locator('#race-grid .card').filter(has=page.get_by_role('heading',name='墨西哥',exact=True));mexico.locator('summary').click();assert '台灣跨日 +1 天' in mexico.inner_text()
        page.locator('#range').select_option('future');assert page.locator('#race-grid .card').count()==upcoming
        assert '非 F1 官方' in page.locator('.sources').inner_text()
        assert '台灣不適用' in page.locator('#free-live').inner_text()
        assert '並非整場完整正賽直播' in page.locator('#highlights').inner_text()
        assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
        for target in ('./','concerts.html','comedy.html','f1.html'):assert page.locator('header nav a[href="'+target+'"]').count()==1
        page.screenshot(path=str(out/f'f1-{width}.png'),full_page=True)
        report['viewports'].append({'width':width,'upcoming':upcoming,'all':23,'TaiwanTime':'passed','navigation':'passed','overflow':False})
    if args.external:
        for selector,expected in [('#next-race','SINGAPORE'),('#paid','F1'),('#free-live','SRF')]:
            anchor=page.locator(selector+' a').first
            with page.expect_popup() as popup:anchor.click()
            other=popup.value;response=other.wait_for_load_state('domcontentloaded');other.wait_for_timeout(600)
            title=other.title();body=other.locator('body').inner_text(timeout=10000)
            assert expected.casefold() in (title+' '+body).casefold(),title
            report['external'].append({'url':other.url,'title':title,'expected':expected,'matched':True});other.close()
    assert not errors,errors
    browser.close()
(out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(report,ensure_ascii=False))

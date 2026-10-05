"""Browser QA for source labels, fallback and real source-page navigation."""
import argparse,json,re
from pathlib import Path
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--url',default='http://127.0.0.1:8765/');parser.add_argument('--external',action='store_true');args=parser.parse_args()
events=json.loads((root/'data/exhibitions.json').read_text(encoding='utf-8'))['events']
cache=json.loads((root/'data/source-links.json').read_text(encoding='utf-8'))
moc=[e for e in events if e['source']=='moc']
assert len(moc)==299
for e in moc:
    assert re.fullmatch('[0-9a-f]{24}',e['sourceUid'])
    assert 'method=showEvent&' not in e['url']
    if e['sourceLinkState']=='verified':
        assert cache[e['sourceUid']]['title']==e['title']
        assert e['url']==cache[e['sourceUid']]['url']==e['promoteUrl']
    else: assert e['url']=='https://data.gov.tw/dataset/6012'
report={'snapshotEvents':len(moc),'verified':sum(e['sourceLinkState']=='verified' for e in moc),'fallback':sum(e['sourceLinkState']!='verified' for e in moc),'viewports':[],'external':[]}
errors=[]
key=lambda x:re.sub(r'[^\w]','',x).casefold()
with sync_playwright() as p:
    browser=p.chromium.launch();page=browser.new_page()
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(args.url,wait_until='networkidle')
    page.locator('[data-view="all"]').click()
    verified=next(e for e in moc if e['sourceLinkState']=='verified')
    fallback=next(e for e in moc if e['sourceLinkState']!='verified')
    for width in [1440,390]:
        page.set_viewport_size({'width':width,'height':900})
        for e in [verified,fallback]:
            page.locator('#query').fill(e['title'])
            card=page.locator('.card').filter(has=page.get_by_role('heading',name=e['title'],exact=True)).first
            label='活動資訊／來源網站' if e['sourceLinkState']=='verified' else '文化部資料集來源'
            link=card.get_by_role('link',name=label)
            assert link.get_attribute('href')==e['url']
            if e['sourceLinkState']!='verified':
                assert e['sourceUid'] in card.inner_text()
                assert '並非活動詳情' in card.inner_text()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        report['viewports'].append(width)
    page.goto(args.url+'sources.html',wait_until='networkidle')
    assert '活動來源連結' in page.inner_text('main')
    assert page.get_by_role('link',name='官方資料集',exact=True).get_attribute('href')=='https://data.gov.tw/dataset/6012'
    if args.external:
        sample=json.loads((root/'output/promote-browser-samples.json').read_text(encoding='utf-8'))
        for s in [r for r in sample if r.get('matchesTitle')]:
            e=next(e for e in moc if e['sourceUid']==s['uid'])
            page.goto(args.url,wait_until='networkidle');page.locator('[data-view="all"]').click();page.locator('#query').fill(e['title'])
            card=page.locator('.card').filter(has=page.get_by_role('heading',name=e['title'],exact=True)).first
            with page.expect_popup() as opened: card.get_by_role('link',name='活動資訊／來源網站').click()
            popup=opened.value
            try:
                response=popup.wait_for_load_state('domcontentloaded',timeout=20000)
                popup.wait_for_timeout(1000)
                assert key(e['title']) in key(popup.inner_text('body')),e['title']
                report['external'].append({'region':e['region'],'uid':e['sourceUid'],'titleMatched':True})
            finally: popup.close()
    assert not errors,errors
    browser.close()
out=root/'output/source-regression';out.mkdir(parents=True,exist_ok=True)
(out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=True))

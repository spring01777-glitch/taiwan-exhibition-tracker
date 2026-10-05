"""Local browser QA using the already installed Playwright runtime. Not a site dependency."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parents[1]
out = root/'output/playwright'
out.mkdir(parents=True, exist_ok=True)
errors = []
checks = []
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width':1440,'height':1000}, device_scale_factor=1)
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
    page.goto('http://127.0.0.1:8765/', wait_until='networkidle')
    page.wait_for_selector('.card')
    assert page.locator('.card').count() == 24
    checks.append('initial real data, 24 cards')
    page.screenshot(path=str(out/'desktop.png'), full_page=True)
    page.locator('#region').select_option('north')
    assert page.locator('.card').count() > 0
    assert all('臺北市' in x or '新北市' in x for x in page.locator('.card-top').all_text_contents())
    checks.append('Taipei/New Taipei filter')
    page.locator('#park').select_option('songshan')
    assert page.locator('.card').count() >= 2
    checks.append('Songshan filter')
    page.locator('#date').fill('2026-10-10')
    assert page.locator('.card').count() >= 2
    checks.append('date overlap filter')
    page.locator('#query').fill('不會出現的展覽查詢')
    assert page.locator('.empty').count() == 1
    checks.append('empty state')
    page.get_by_role('button',name='清除篩選').click()
    page.wait_for_timeout(100)
    assert page.locator('#region').input_value() == ''
    assert page.locator('.card').count() == 24
    page.get_by_role('button',name='顯示更多展覽').click()
    assert page.locator('.card').count() == 48
    checks.append('reset and pagination')
    for name in ['今日新增','近期推薦','即將結束','歷史紀錄','所有展覽']:
        page.get_by_role('button',name=name,exact=True).click()
        assert page.get_by_role('button',name=name,exact=True).get_attribute('aria-pressed') == 'true'
    checks.append('all five tabs')
    page.set_viewport_size({'width':390,'height':844})
    page.locator('#park').select_option('huashan')
    assert page.locator('.card').count() >= 2
    assert page.locator('.verification').count() == 8
    page.locator('[data-view="recommended"]').click()
    assert page.locator('.verification').count() == 0
    checks.append('8 Huashan uncertainties displayed and excluded from recommendations')
    page.locator('[data-view="all"]').click()
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
    page.screenshot(path=str(out/'mobile.png'),full_page=True)
    checks.append('390px mobile, Huashan filter, no horizontal overflow')
    assert all(x.startswith(('https://','http://')) for x in page.locator('.card a').evaluate_all('(a)=>a.map(x=>x.href)'))
    checks.append('safe source links')
    page.locator('#park').select_option('pier2')
    assert page.locator('.card').count() == 13
    assert any('2027-03-01' in x for x in page.locator('.card').all_text_contents())
    assert sum('還是先躺一下再說' in x for x in page.locator('.card h3').all_text_contents()) == 1
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
    page.screenshot(path=str(out/'pier2-mobile.png'),full_page=True)
    checks.append('13 Pier-2 entries, corrected date, no duplicate, mobile filter')
    # Exercise the user-facing failure state while retaining the real snapshot.
    payload=json.loads((root/'data/exhibitions.json').read_text(encoding='utf-8-sig'))
    payload['sources']['moc']['state']='error'
    payload['sources']['moc']['message']='測試來源逾時；保留資料'
    page.route('**/data/exhibitions.json',lambda route:route.fulfill(json=payload))
    page.reload(wait_until='networkidle')
    assert '更新失敗' in page.locator('#updated').inner_text()
    assert page.locator('.card').count()==24
    checks.append('failure banner plus retained cards')
    assert not errors, errors
    browser.close()
report={'checks':checks,'consoleAndPageErrors':errors,'browser':'Chromium','screenshots':['desktop.png','mobile.png']}
(out/'smoke.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=True))

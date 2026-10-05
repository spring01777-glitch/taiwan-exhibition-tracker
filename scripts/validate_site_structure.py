"""Static interaction/accessibility contracts, no browser or network."""
from pathlib import Path
from urllib.parse import urlsplit
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[1]
PAGES={'index.html':('region','park','date','query','more','results','updated','source-status','view-note','active-count','new-count'), 'concerts.html':('region','venue','platform','date','query','view','results','updated','source-status','active-count'), 'comedy.html':('region','venue','platform','date','query','view','results','updated','source-status','active-count'), 'f1.html':('season','range','next-race','race-grid','race-count','updated','f1-source-status','paid','free-live','highlights')}
for name,ids in PAGES.items():
    soup=BeautifulSoup((ROOT/name).read_text(encoding='utf8'),'html.parser')
    assert soup.html['lang']=='zh-Hant-TW' and soup.select_one('meta[name=viewport]')
    assert len(soup.select('h1'))==1
    all_ids=[n['id'] for n in soup.select('[id]')];assert len(all_ids)==len(set(all_ids))
    for node_id in ids:assert soup.find(id=node_id), (name,node_id)
    for control in soup.select('input,select'):
        assert control.get('id') and soup.find('label',attrs={'for':control['id']}),(name,control)
    nav=soup.select('header nav a');assert [a.text for a in nav]==['展覽','演唱會','脫口秀','F1']
    assert len(soup.select('header nav a[aria-current=page]'))==1
    for a in soup.select('a[href]'):
        uri=urlsplit(a['href']);assert uri.scheme not in ('javascript','data')
        if a.get('target')=='_blank':assert 'noopener' in a.get('rel',[]) and 'noreferrer' in a.get('rel',[])
        if not uri.scheme and not uri.netloc and uri.path and not uri.path.startswith('/'):
            assert (ROOT/uri.path).exists(),(name,uri.path)
    for asset in soup.select('script[src],link[rel=stylesheet]'):
        uri=urlsplit(asset.get('src') or asset['href'])
        assert not uri.scheme and not uri.netloc and (ROOT/uri.path).is_file()
    assert not soup.select('img'), 'No unlicensed imagery added'
print('PASS four-page static contracts: IDs, labels, one active shared navigation, local assets, safe links, no imagery.')

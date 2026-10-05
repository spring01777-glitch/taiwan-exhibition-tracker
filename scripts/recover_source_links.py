"""Bounded browser rechecks of previously title-matched official detail pages.

Uses an existing Chrome/Chromium executable; never installs a browser or changes
TLS/sandbox settings. At most three pages per invocation, no retries.
"""
import argparse,json,re,shutil,subprocess,tempfile,unicodedata
from datetime import datetime,timedelta,timezone
from html.parser import HTMLParser
from pathlib import Path
from source_links import resolve_source_link

ROOT=Path(__file__).resolve().parents[1]
LIMIT=3

class Titles(HTMLParser):
    def __init__(self):
        super().__init__();self.tag=None;self.title='';self.headings=''
    def handle_starttag(self,tag,attrs):
        if tag in ('title','h1','h2'):self.tag=tag
    def handle_endtag(self,tag):
        if tag==self.tag:self.tag=None
    def handle_data(self,text):
        if self.tag=='title':self.title+=text
        elif self.tag:self.headings+=text

def key(text):return re.sub(r'\W','',unicodedata.normalize('NFKC',text)).casefold()

def title_matches(dom,title):
    parsed=Titles();parsed.feed(dom)
    expected=key(title)
    return bool(expected and expected in key(parsed.title) and expected in key(parsed.headings))

def installed_browser():
    return next((p for name in ('google-chrome','google-chrome-stable','chromium','chromium-browser') if (p:=shutil.which(name))),None)

def browser_check(browser,url,title):
    with tempfile.TemporaryDirectory(prefix='exhibition-link-check-') as profile:
        result=subprocess.run([browser,'--headless','--disable-gpu','--no-first-run',f'--user-data-dir={profile}','--dump-dom',url],capture_output=True,timeout=12)
        if result.returncode!=0 or len(result.stdout)>2_000_000:return False
        return title_matches(result.stdout.decode('utf-8',errors='replace'),title)

def recover(candidates,checked,events,now,checker,limit=LIMIT):
    current={e['sourceUid']:e for e in events if e['source']=='moc' and not e.get('missingFromSource')}
    pending=[]
    for uid,c in candidates.items():
        e=current.get(uid)
        if not e or e['title']!=c['title']:continue
        # Already usable promotion links do not need this official-detail check.
        if resolve_source_link(uid,e['title'],checked,e.get('promoteUrl','')).get('sourceLinkState')=='verified':continue
        probe={uid:{**c,'state':'verified'}}
        if resolve_source_link(uid,c['title'],probe)['sourceLinkType']!='culture':continue
        pending.append((uid,c))
    pending.sort(key=lambda x:(candidates[x[0]].get('lastAttempt',''),x[0]))
    attempted=restored=0
    for uid,c in pending[:min(limit,LIMIT)]:
        attempted+=1;c['lastAttempt']=now
        try:ok=checker(c['url'],c['title'])
        except (OSError,subprocess.SubprocessError,ValueError):ok=False
        c['lastResult']='verified' if ok else 'unavailable'
        if ok:
            checked[uid]={'title':c['title'],'url':c['url'],'state':'verified','checkedAt':now}
            restored+=1
        # One failure ends this invocation: no broad crawling of a failing host.
        else:break
    return {'attempted':attempted,'restored':restored,'pendingBefore':len(pending),'limit':LIMIT}

def atomic(path,data):
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');temp.replace(path)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--browser');args=parser.parse_args()
    browser=args.browser or installed_browser()
    if not browser:
        print(json.dumps({'state':'browser-unavailable','attempted':0,'restored':0,'message':'Existing Chrome/Chromium required; cache preserved, no installation attempted.'}));return
    candidates=json.loads((ROOT/'data/source-link-candidates.json').read_text(encoding='utf-8'))
    checked=json.loads((ROOT/'data/source-links.json').read_text(encoding='utf-8'))
    events=json.loads((ROOT/'data/exhibitions.json').read_text(encoding='utf-8'))['events']
    now=datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
    result=recover(candidates,checked,events,now,lambda url,title:browser_check(browser,url,title))
    atomic(ROOT/'data/source-links.json',checked);atomic(ROOT/'data/source-link-candidates.json',candidates)
    print(json.dumps({'state':'ok',**result}))

if __name__=='__main__':main()

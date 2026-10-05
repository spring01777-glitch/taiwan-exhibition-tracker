"""Inspect all public F1 facts and outbound URLs before deployment."""
import json,re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
ROOT=Path(__file__).resolve().parents[1]
def validate():
    data=json.loads((ROOT/'data/f1.json').read_text(encoding='utf8'))
    assert set(data)=={'seasons','sources','lastAttempt','errors','attribution'}
    assert set(data['seasons'])==set(data['sources'])=={'2026'}
    assert data['attribution']['license']=='CC BY-NC-SA 4.0'
    rows=data['seasons']['2026'];assert len(rows)>=15 and len({r['id'] for r in rows})==len(rows)
    fields={'id','name','weekendStart','weekendEnd','source','dataSource','sourceTimezone','sessions','missingTimes','lastSuccess','status'}
    for race in rows:
        assert set(race)==fields and race['status'] in ('ok','unconfirmed')
        assert re.fullmatch('[a-z0-9-]+',race['id'])
        datetime.strptime(race['weekendStart'],'%Y-%m-%d');datetime.strptime(race['weekendEnd'],'%Y-%m-%d')
        assert race['weekendStart']<=race['weekendEnd']
        assert race['dataSource']=='https://api.jolpi.ca/ergast/f1/2026.json'
        assert race['source'].startswith('https://www.formula1.com/en/racing/2026')
        for session in race['sessions']:
            assert set(session)=={'name','start','end'} and session['end'] is None
            assert datetime.fromisoformat(session['start']).utcoffset().total_seconds()==0
    platforms=json.loads((ROOT/'data/f1-platforms.json').read_text(encoding='utf8'))
    assert set(platforms)=={'checkedAt','paid','free-live','highlights'}
    for group in ('paid','free-live','highlights'):
        for entry in platforms[group]:
            assert set(entry)=={'name','region','kind','description','conditions','verified','links'}
            for link in entry['links']:
                p=urlsplit(link['url']);assert p.scheme=='https' and not p.username and not p.password
                assert p.hostname in {'eltaott.tv','www.srf.ch','www.formula1.com','on.orf.at','www.rtl.lu','www.youtube.com'}
    serialized=json.dumps([data,platforms],ensure_ascii=False)
    assert not re.search(r'(?i)(C:[\\/]+Users|github_pat_|gh[pousr]_[a-z0-9]{20,}|sk-proj-|PRIVATE KEY|imageURL|descriptionFilterHtml)',serialized)
    assert not re.search(r'[\w.+-]+@[\w.-]+\.[a-z]{2,}',serialized,re.I)
    print(f'F1 public schema: {len(rows)} races, {sum(len(r["sessions"]) for r in rows)} published sessions; licensed attribution and official platform URLs passed.')
if __name__=='__main__':validate()

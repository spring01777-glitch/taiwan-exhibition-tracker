"""Strict publication schema: no original prose, images, credentials or local paths."""
import json
import re
from pathlib import Path
from urllib.parse import urlparse

ROOT=Path(__file__).resolve().parents[1]
FIELDS={'id','title','start','end','region','venue','address','park','price','category','summary','url','source','sourceUid','sourceVersion','firstSeen','lastSeen','missingFromSource','revisions','verificationNote'}
REVISION={'title','start','end','price','lastSeen'}

def validate(path):
    data=json.loads(path.read_text(encoding='utf-8'))
    assert set(data)=={'schemaVersion','generatedAt','sources','events'}
    assert data['schemaVersion']==1 and data['events']
    for e in data['events']:
        assert not (set(e)-(FIELDS|{'venueName','venueStatus','locations'})), set(e)-FIELDS
        assert e['locations']
        for location in e['locations']:
            assert set(location)=={'id','name','region','status'}
            assert location['region']==e['region'] and location['name']
            assert location['status'] in ('named','address','missing','uncertain','online')
        assert len(e['summary'])<=180 and len(e['price'])<=180 and len(e.get('verificationNote',''))<=180
        assert not re.search(r'<[^>]+>',e['summary'])
        p=urlparse(e['url'])
        assert p.scheme in ('http','https') and p.hostname and not p.username and not p.password
        for r in e.get('revisions',[]): assert set(r)<=REVISION
    text=json.dumps(data,ensure_ascii=False)
    assert not re.search(r'(?i)(?:gh[pousr]_[a-z0-9]{20,}|github_pat_|sk-proj-|-----BEGIN .*PRIVATE KEY|[a-z]:\\\\Users\\\\|descriptionFilterHtml|imageURL)',text)
    assert not re.search(r'[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}',text,re.I), 'Email address excluded from public metadata'
    print(f'Public schema passed: {len(data["events"])} events; no raw descriptions/images, email, token patterns or local user paths.')

if __name__=='__main__': validate(ROOT/'data/exhibitions.json')

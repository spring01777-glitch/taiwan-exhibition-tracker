"""Validate the only two live-event snapshots included in the Pages artifact."""
import json,re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
ROOT=Path(__file__).resolve().parents[1]
FIELDS={'id','title','performers','region','venue','address','sessions','price','saleAt','saleNote','ticketStatus','ticketUrl','ticketVerifiedAt','sourceUrl','source','sourceUid','status','statusNote','summary','verifiedAt','revisions'}
def validate():
    for kind in ('concerts','comedy'):
        data=json.loads((ROOT/f'data/{kind}.json').read_text(encoding='utf-8'))
        assert set(data)=={'schemaVersion','timezone','updatedAt','events','sources'}
        assert data['schemaVersion']==1 and data['timezone']=='Asia/Taipei' and data['events']
        assert len({e['id'] for e in data['events']})==len(data['events'])
        for e in data['events']:
            assert not set(e)-FIELDS
            assert e['title'] and e['venue'] and e['sessions'] and len(e['summary'])<=180
            assert isinstance(e['sourceUrl'],str) and e['sourceUrl']
            assert e['status'] in ('scheduled','changed','unconfirmed','cancelled','rescheduled')
            for s in e['sessions']:
                assert set(s)<={'date','time','status'}
                datetime.strptime(s['date'],'%Y-%m-%d')
                if s.get('time'):datetime.strptime(s['time'],'%H:%M')
            for field in ('sourceUrl','ticketUrl'):
                if not e.get(field):continue
                p=urlsplit(e[field]);assert p.scheme=='https' and p.hostname and not p.username and not p.password
            if e.get('ticketUrl'):assert e.get('ticketVerifiedAt'),'unverified ticket button'
        serialized=json.dumps(data,ensure_ascii=False)
        assert not re.search(r'(?i)(descriptionFilterHtml|imageURL|posterURL|github_pat_|gh[pousr]_[a-z0-9]{20,}|sk-proj-|-----BEGIN .*PRIVATE KEY)',serialized)
        assert not re.search(r'[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}',serialized,re.I)
        assert 'C:\\Users\\' not in serialized and 'C:/Users/' not in serialized
        print(f'{kind}: {len(data["events"])} event/venue records, {sum(len(e["sessions"]) for e in data["events"])} sessions; public schema passed.')
if __name__=='__main__':validate()

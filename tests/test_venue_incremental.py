import json,sys,tempfile,unittest
from pathlib import Path
from urllib.error import HTTPError
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import update_venue_sources as venues
from update import atomic

BASE=venues.SOURCES['songshan']['base']
TODAY='2026-11-17T09:00:00+08:00'

def url(i):return f'{BASE}/exhibition/activity/{i}'
def page(i,dates='2026-11-17 - 2026-12-17'):
    return f'<p class="inner_title">展覽{i}</p><div class="under"><p class="date">{dates}</p><p class="place">一號倉庫</p></div>'
def listing(ids):
    return '<div id="top_sliders"><div class="sliderscon">'+''.join(f'<a href="{url(i)}"><p class="title">展覽{i}</p></a>' for i in ids)+'</div></div>'

class Reader:
    routes={};calls=[];policy_error=None
    def __init__(self,c):self.config=c
    def prepare(self,p):
        if self.policy_error:raise self.policy_error
    def get(self,u):
        self.calls.append(u);body=self.routes[u]
        if isinstance(body,Exception):raise body
        return body

class VenueIncrementalTests(unittest.TestCase):
    def setup_root(self,tmp,ids,previous=None):
        root=Path(tmp);(root/'data').mkdir()
        atomic(root/'data/curated.json',previous or [])
        atomic(root/'data/venue-policy.json',{'songshan':{}})
        Reader.routes={BASE+'/exhibition':listing(ids),**{url(i):page(i) for i in ids}}
        Reader.calls=[];Reader.policy_error=None
        return root
    def run_source(self,root,now=TODAY):
        return venues.run(root=root,now=now,source_names=['songshan'],reader_factory=Reader)
    def state(self,root):return json.loads((root/'data/venue-crawl-state.json').read_text())['songshan']
    def events(self,root):return json.loads((root/'data/curated.json').read_text())
    def reads(self):return [u for u in Reader.calls if '/activity/' in u]
    def test_hundred_limit_restarts_and_cross_day_no_duplicate_reads(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=self.setup_root(tmp,range(1,252))
            self.assertEqual(self.run_source(root),0)
            self.assertEqual((len(self.reads()),self.state(root)['dailyBudget']['date']),(100,'2026-11-17'))
            self.assertEqual(len(self.state(root)['pending']),151)
            self.assertEqual(self.run_source(root),0)
            self.assertEqual(len(self.reads()),100)
            self.assertEqual(Reader.calls.count(BASE+'/exhibition'),1)
            Reader.routes[BASE+'/exhibition']=listing(reversed(range(1,252)))
            self.assertEqual(self.run_source(root,'2026-11-18T09:00:00+08:00'),0)
            self.assertEqual(len(self.reads()),200)
            self.assertEqual(self.run_source(root,'2026-11-19T09:00:00+08:00'),0)
            self.assertEqual((len(self.reads()),len(set(self.reads())),len(self.events(root))),(251,251,251))
            self.assertEqual(self.run_source(root,'2026-12-19T09:00:00+08:00'),0)
            self.assertEqual(len(self.reads()),251)  # expired history retained, not re-read
            self.assertEqual(len(self.events(root)),251)
    def test_new_activity_after_reorder_and_returning_known_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=self.setup_root(tmp,[1,2]);self.run_source(root)
            Reader.routes[BASE+'/exhibition']=listing([2,0]);Reader.routes[url(0)]=page(0)
            self.run_source(root,'2026-11-18T09:00:00+08:00')
            self.assertEqual(self.reads(),[url(1),url(2),url(0)])
            Reader.routes[BASE+'/exhibition']=listing([0,2,1])
            self.run_source(root,'2026-11-19T09:00:00+08:00')
            self.assertEqual(self.reads(),[url(1),url(2),url(0)])
            self.assertFalse(any(e.get('missingFromSource') for e in self.events(root)))
    def test_failure_progress_survives_without_replacing_previous_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=self.setup_root(tmp,[1]);self.run_source(root);before=self.events(root)
            Reader.routes[BASE+'/exhibition']=listing([1,2,3]);Reader.routes[url(2)]=page(2)
            Reader.routes[url(3)]=HTTPError(url(3),502,'x',None,None)
            self.assertEqual(self.run_source(root,'2026-11-18T09:00:00+08:00'),1)
            self.assertEqual(self.events(root),before)
            state=self.state(root)
            self.assertEqual(len(state['dailyBudget']['attempted']),2)
            self.assertIn(url(2),state['completed'])
            self.run_source(root,'2026-11-18T10:00:00+08:00')
            self.assertEqual(self.reads().count(url(3)),1)
            self.assertEqual(self.reads().count(url(2)),1)
            self.assertEqual(len(self.events(root)),2)
            Reader.routes[url(3)]=page(3)
            self.assertEqual(self.run_source(root,'2026-11-19T09:00:00+08:00'),0)
            self.assertEqual(len(self.events(root)),3)
            self.assertEqual(self.reads().count(url(3)),2)
    def test_existing_baseline_preserved_and_migration_day_reserved(self):
        old=venues.parse_detail('songshan',page(1),url(1),{},{});old['lastSeen']='2026-11-16'
        with tempfile.TemporaryDirectory() as tmp:
            root=self.setup_root(tmp,[1,2],[old]);self.run_source(root)
            self.assertEqual(self.events(root),[old]);self.assertEqual(self.reads(),[])
            self.assertEqual(self.state(root)['dailyBudget']['reserved'],100)
            self.run_source(root,'2026-11-18T09:00:00+08:00')
            self.assertEqual(self.reads(),[url(2)])
    def test_unknown_end_is_kept_but_invalid_reversed_dates_are_not_admitted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=self.setup_root(tmp,[1,2,3])
            Reader.routes[url(1)]=page(1,'2026-11-17起，結束未定')
            Reader.routes[url(2)]=page(2,'長期常設')
            Reader.routes[url(3)]=page(3,'2026-12-01 - 2026-11-01')
            self.run_source(root)
            self.assertEqual(len(self.events(root)),2)
            self.assertTrue(all(e['end'] is None for e in self.events(root)))
            self.assertIn(url(3),self.state(root)['pending'])
            self.run_source(root,'2027-12-01T09:00:00+08:00')
            self.assertEqual(len(self.events(root)),2)
    def test_new_url_with_reused_title_is_not_assumed_to_be_old_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=self.setup_root(tmp,[1]);self.run_source(root)
            Reader.routes[BASE+'/exhibition']=listing([1,2]).replace('展覽2','展覽1')
            Reader.routes[url(2)]=page(1,'2027-01-01 - 2027-01-03')
            self.run_source(root,'2026-11-18T09:00:00+08:00')
            self.assertEqual(self.reads(),[url(1),url(2)])
            self.assertEqual(len(self.events(root)),2)

    def test_unknown_dates_survive_public_build_and_schema(self):
        from unittest.mock import patch
        import update
        from validate_public import validate
        from test_update import row
        with tempfile.TemporaryDirectory() as tmp:
            root=self.setup_root(tmp,[1]);Reader.routes[url(1)]=page(1,'長期常設')
            self.run_source(root)
            with patch.object(update,'ROOT',root):
                self.assertEqual(update.run(root/'data',rows=[row()]),0)
            validate(root/'data/exhibitions.json')
            published=json.loads((root/'data/exhibitions.json').read_text())['events']
            event=next(e for e in published if e['source']=='songshan')
            self.assertIsNone(event['end'])
            self.assertIsNone(event['start'])
            self.assertIn('結束日期未明',event['verificationNote'])

    def test_huashan_and_pier_unknown_end_remain_unknown(self):
        huashan='<h1 class="news-title__title">常設展</h1><section class="exhi-sidebar__section"><h2>地點：</h2><p>西館</p></section>'
        h=venues.parse_detail('huashan',huashan,'https://www.huashan1914.com/exhibition/a',{}, {})
        self.assertIsNone(h['end'])
        pier='<h1>長期展</h1><div class="datearea"><div class="starttime"><span class="y">2026</span><span class="d">11.17</span></div></div>'
        p=venues.parse_detail('pier2',pier,'https://pier2.org/exhibition/info/1/',{'venue':'P2倉庫'}, {})
        self.assertEqual(p['start'],'2026-11-17')
        self.assertIsNone(p['end'])

    def test_policy_error_preserves_baseline_and_does_not_fetch_details(self):
        old=venues.parse_detail('songshan',page(1),url(1),{},{});old['lastSeen']='2026-11-16'
        with tempfile.TemporaryDirectory() as tmp:
            root=self.setup_root(tmp,[1],[old]);Reader.policy_error=PermissionError('official policy changed; manual review required')
            self.assertEqual(self.run_source(root),1)
            self.assertEqual(self.events(root),[old]);self.assertEqual(Reader.calls,[])

if __name__=='__main__':unittest.main()

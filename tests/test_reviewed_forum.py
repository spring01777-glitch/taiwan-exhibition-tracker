import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import update_venue_sources as venues
from update import atomic

ROOT=Path(__file__).resolve().parents[1]
URL='https://pier2.org/exhibition/info/2000/'

class ReviewedForumTests(unittest.TestCase):
    def event(self):
        return next(e for e in json.loads((ROOT/'data/curated.json').read_text()) if e['id']=='pier2-solid-tides-2026-11-21')

    def test_verified_november_program_does_not_inherit_october_dates_or_venue(self):
        e=self.event()
        self.assertEqual((e['start'],e['end']),('2026-11-21','2026-11-21'))
        self.assertIn('B3',e['venue'])
        self.assertNotIn('正港',e['venue'])
        self.assertIn('10:30–11:30',e['summary'])
        self.assertIn('14:00–15:00',e['summary'])
        self.assertEqual(e['url'],URL)

    def test_reviewed_pending_url_is_not_refetched_and_clears_on_next_day(self):
        e=self.event();calls=[]
        class Reader:
            def __init__(self,c):pass
            def prepare(self,p):pass
            def get(self,u):
                calls.append(u)
                if u!='https://pier2.org/exhibition/':raise AssertionError('Known forum detail must not be fetched')
                return '<div id="event_list"><a href="/exhibition/info/2000/"><div class="thename">剛質潮汐</div></a></div>'
            def close(self):pass
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);(root/'data').mkdir()
            atomic(root/'data/curated.json',[e]);atomic(root/'data/venue-policy.json',{'pier2':{}})
            atomic(root/'data/venue-crawl-state.json',{'pier2':{
                'dailyBudget':{'date':'2026-11-19','attempted':[URL],'reserved':0},
                'pending':{URL:{'title':'剛質潮汐','venue':''}},'listReadAt':'2026-11-19'}})
            self.assertEqual(venues.run(root=root,now='2026-11-20T09:00:00+08:00',source_names=['pier2'],browser='fake',
                reader_factory=Reader,render_factory=lambda executable,reader:reader),0)
            state=json.loads((root/'data/venue-crawl-state.json').read_text())['pier2']
            self.assertEqual(state['pending'],{})
            self.assertEqual(state['dailyBudget']['attempted'],[])
            self.assertEqual(json.loads((root/'data/curated.json').read_text()),[e])

if __name__=='__main__':unittest.main()

import importlib.util,json,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('update_f1',ROOT/'scripts/update_f1.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class F1Tests(unittest.TestCase):
    def test_explicit_utc_and_unknown_time(self):
        race={'season':'2026','raceName':'Singapore Grand Prix','Circuit':{'circuitId':'marina_bay'},'date':'2026-10-11','time':'12:00:00Z','SprintQualifying':{'date':'2026-10-09','time':'12:30:00Z'},'FirstPractice':{'date':'2026-10-09'}}
        parsed=m.parse_race(race);self.assertEqual(parsed['sessions'][0]['start'],'2026-10-09T12:30:00+00:00');self.assertEqual(parsed['missingTimes'],['Practice 1'])
        race['time']='12:00:00'
        with self.assertRaises(ValueError):m.parse_race(race)
    def test_failure_and_empty_preserve_snapshot(self):
        (ROOT/'output').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT/'output') as temp:
            path=Path(temp)/'data.json';old={'seasons':{'2026':[{'id':'keep'}]},'sources':{'2026':{'lastSuccess':'2026-10-01T00:00:00Z'}}}
            for get in (lambda _:(_ for _ in ()).throw(TimeoutError()),lambda _:{'MRData':{'total':'0','RaceTable':{'season':'2026','Races':[]}}}):
                path.write_text(json.dumps(old),encoding='utf8');self.assertTrue(m.update(path,get));new=json.loads(path.read_text(encoding='utf8'))
                self.assertEqual(new['seasons'],old['seasons']);self.assertEqual(new['sources']['2026']['lastSuccess'],old['sources']['2026']['lastSuccess']);self.assertEqual(new['sources']['2026']['status'],'error')
    def test_licensed_snapshot(self):
        data=json.loads((ROOT/'data/f1.json').read_text(encoding='utf8'));self.assertEqual(set(data['seasons']),{'2026'});self.assertEqual(data['attribution']['license'],'CC BY-NC-SA 4.0')
        rows=data['seasons']['2026'];self.assertGreaterEqual(len(rows),15);sg=next(r for r in rows if r['id']=='singapore');self.assertEqual(sg['sessions'][-1]['start'],'2026-10-11T12:00:00+00:00')
        for r in rows:
            self.assertEqual(r['dataSource'],m.API)
            for s in r['sessions']:self.assertIsNotNone(m.datetime.fromisoformat(s['start']).tzinfo)
    def test_platform_restrictions_and_streaming_claims(self):
        data=json.loads((ROOT/'data/f1-platforms.json').read_text(encoding='utf8'))
        hami=next(p for p in data['paid'] if p['name'].startswith('Hami'))
        self.assertIn('自動續租',hami['conditions']);self.assertIn('天數尚未核實',hami['conditions'])
        self.assertFalse(any(p['name'].startswith('Hami') for p in data['free-live']))
        mod=next(p for p in data['paid'] if p['name'].endswith('MOD'));self.assertIn('非一般網頁直播',mod['conditions'])
        tv=next(p for p in data['paid'] if p['name']=='F1 TV');self.assertIn('Access 不等於',tv['description']);self.assertIn('未確認',tv['region'])

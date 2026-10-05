import subprocess,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from recover_source_links import recover,title_matches

class RecoveryTests(unittest.TestCase):
    def fixtures(self,count=5):
        candidates={f'{i:024x}':{'title':f'展覽{i}','url':f'https://cloud.culture.tw/frontsite/inquiry/eventInquiryAction.do?method=showEventDetail&uid={i:024x}'} for i in range(count)}
        events=[{'source':'moc','sourceUid':uid,'title':c['title']} for uid,c in candidates.items()]
        return candidates,{},events
    def test_browser_error_and_wrong_title_cannot_restore(self):
        self.assertFalse(title_matches('<title>502 Bad Gateway</title><h1>502 Bad Gateway</h1>','展覽'))
        self.assertFalse(title_matches('<title>展覽</title><h1>其他活動</h1>','展覽'))
        self.assertTrue(title_matches('<title>文化活動 展覽｜文化部</title><h1>展覽</h1>','展覽'))
    def test_cap_and_restore_require_matching_current_title(self):
        c,checked,events=self.fixtures();events[0]['title']='已改名'
        result=recover(c,checked,events,'day1',lambda url,title:True,limit=999)
        self.assertEqual(result['attempted'],3);self.assertEqual(result['restored'],3)
        self.assertNotIn(events[0]['sourceUid'],checked)
    def test_failure_preserves_verified_cache_and_rotates_next_day(self):
        c,checked,events=self.fixtures();uid=events[0]['sourceUid']
        checked[uid]={'title':events[0]['title'],'state':'verified','url':'https://museum.example/exhibition'}
        before=checked.copy();first=[];second=[]
        recover(c,checked,events,'day1',lambda url,title:first.append(url) or False)
        recover(c,checked,events,'day2',lambda url,title:second.append(url) or False)
        self.assertEqual(checked,before);self.assertEqual(len(first),1);self.assertNotEqual(first,second)
    def test_timeout_never_overwrites_cache(self):
        c,checked,events=self.fixtures()
        def timed_out(url,title):raise subprocess.TimeoutExpired('browser',12)
        result=recover(c,checked,events,'day1',timed_out)
        self.assertEqual(result['attempted'],1);self.assertEqual(result['restored'],0);self.assertEqual(checked,{})

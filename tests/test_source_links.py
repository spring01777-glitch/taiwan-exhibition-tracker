import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from source_links import resolve_source_link,DATASET
class SourceLinkTests(unittest.TestCase):
    uid='67d8874426b32408680bed6f'
    def record(self,method='showEventDetail',state='verified',title='活動'):
        return {self.uid:{'title':title,'url':f'https://cloud.culture.tw/frontsite/inquiry/eventInquiryAction.do?method={method}&uid={self.uid}','state':state,'checkedAt':'2026-10-05T23:00:00+08:00'}}
    def test_verified_official_title_and_uid_match(self):
        self.assertIn('showEventDetail',resolve_source_link(self.uid,'活動',self.record())['url'])
    def test_old_route_and_wrong_id_or_title_are_not_details(self):
        self.assertEqual(resolve_source_link(self.uid,'活動',self.record(method='showEvent'))['url'],DATASET)
        self.assertEqual(resolve_source_link(self.uid,'別的活動',self.record())['url'],DATASET)
        self.assertEqual(resolve_source_link('abc123','活動',self.record())['url'],DATASET)
    def test_error_empty_and_new_uid_have_explicit_fallback(self):
        for cache in ({},self.record(state='unavailable'),self.record(state='title-mismatch')):
            r=resolve_source_link(self.uid,'活動',cache)
            self.assertEqual(r['url'],DATASET);self.assertNotEqual(r['sourceLinkState'],'verified')
    def test_promote_requires_exact_source_provided_url(self):
        url='https://www.nmns.edu.tw/exhibition/'
        cache={self.uid:{'title':'活動','url':url,'state':'verified'}}
        self.assertEqual(resolve_source_link(self.uid,'活動',cache,url)['sourceLinkType'],'promote')
        self.assertEqual(resolve_source_link(self.uid,'活動',cache,'https://example.com/')['url'],'https://example.com/')
    def test_provided_url_is_used_without_claiming_verification(self):
        url='https://www.nmns.edu.tw/ch/exhibitions/galleries/life-science-hall/fantastic/'
        for cache in ({},self.record(state='unavailable'),self.record(title='別的活動')):
            r=resolve_source_link(self.uid,'活動',cache,url)
            self.assertEqual(r['url'],url)
            self.assertEqual(r['sourceLinkState'],'source-provided')
            self.assertEqual(r['sourceLinkCheckedAt'],'')
    def test_provided_url_rejects_unsafe_or_dataset_values(self):
        for url in ['javascript:alert(1)','https://user:secret@example.com',DATASET,'']:
            self.assertEqual(resolve_source_link(self.uid,'活動',{},url)['url'],DATASET)
    def test_invalid_uid_does_not_enable_provided_link(self):
        self.assertEqual(resolve_source_link('invalid','活動',{},'https://example.com/')['url'],DATASET)

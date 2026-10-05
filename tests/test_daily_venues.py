import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from update_venue_sources import SOURCES,discover,parse_detail,keep_source,safe_path,canonical_public_url

class DailyVenueTests(unittest.TestCase):
    def test_encoded_and_unicode_official_slugs_share_identity(self):
        self.assertEqual(canonical_public_url('https://www.huashan1914.com/exhibition/華山 '),canonical_public_url('https://www.huashan1914.com/exhibition/%E8%8F%AF%E5%B1%B1%20'))
    def test_discovery_rejects_query_offsite_and_overview(self):
        body='<div id="top_sliders"><div class="sliderscon"><a href="/exhibition/activity/1"><p class="title">松山文創園區-10月展演攻略</p></a><a href="/exhibition/activity/2?x=1"><p class="title">query</p></a><a href="https://example.com/exhibition/activity/3"><p class="title">offsite</p></a><a href="/exhibition/activity/4"><p class="title">真實活動</p></a></div></div>'
        self.assertEqual(len(discover('songshan',body)),1)
        self.assertFalse(safe_path(SOURCES['huashan'],'https://www.huashan1914.com/exhibition?page=2'))
    def test_songshan_dates_identity_and_missing_price(self):
        body='<p class="inner_title">展覽</p><div class="under"><p class="date">2026-10-01 - 2026-10-30</p><p class="place">一號倉庫</p></div>'
        e=parse_detail('songshan',body,'https://www.songshanculturalpark.org/exhibition/activity/a',{}, {'id':'stable','sourceUid':'123'})
        self.assertEqual(e['id'],'stable');self.assertEqual(e['sourceUid'],'123');self.assertIn('未提供',e['price']);self.assertNotIn('免費',e['price'])
        with self.assertRaises(ValueError):parse_detail('songshan',body.replace('2026-10-30','2026-09-01'),'url',{}, {})
    def test_huashan_cross_year_and_prior_warning_kept(self):
        body='<h1 class="news-title__title">跨年展</h1><div class="exhi-sidebar__date-years"><span>2026</span><span>2027</span></div><span class="exhi-sidebar__date-md">12.01</span><span class="exhi-sidebar__date-md">01.20</span><section class="exhi-sidebar__section"><h3>地點：</h3><div>東館</div></section>'
        e=parse_detail('huashan',body,'url',{}, {'verificationNote':'狀態待確認'})
        self.assertEqual(e['end'],'2027-01-20');self.assertEqual(e['verificationNote'],'狀態待確認')
    def test_pier_dates_and_clear_ticket_badge(self):
        body='<h1>展覽</h1><div class="datearea"><div class="starttime"><div class="y">2026</div><div class="d">10.01</div></div><div class="endtime"><div class="y">2026</div><div class="d">11.01</div></div></div>'
        e=parse_detail('pier2',body,'url',{'venue':'蓬萊區B4倉庫','badge':'paid'}, {})
        self.assertIn('付費',e['price']);self.assertIn('鼓山區',e['address']);self.assertNotIn('免費',e['price'])
    def test_empty_and_mass_loss_never_replace_source(self):
        previous=[{'id':str(i),'end':'2026-12-30'} for i in range(10)]
        for incoming in [[],[{'id':'a'}]]:
            with self.assertRaises(ValueError):keep_source(previous,incoming,'2026-10-06T09:00:00+08:00')
    def test_merge_preserves_first_seen_history_and_revisions(self):
        old={'id':'a','title':'展覽','start':'2026-10-01','end':'2026-10-20','price':'免費','firstSeen':'2026-10-01','lastSeen':'2026-10-05'}
        incoming={**old,'end':'2026-10-25'}
        result=keep_source([old], [incoming], '2026-10-06')
        self.assertEqual(result[0]['firstSeen'],'2026-10-01');self.assertEqual(result[0]['revisions'][0]['end'],'2026-10-20')

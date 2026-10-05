import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from venues import classify

class VenueTests(unittest.TestCase):
    def event(self,name='',address='',region='臺北市',**extra):
        return dict(title='測試活動',venue=name,address=address,region=region,park='',**extra)
    def test_same_name_different_city_or_branch_stays_separate(self):
        a=classify(self.event('藝術中心','臺北市一路1號'))
        b=classify(self.event('藝術中心','高雄市一路1號','高雄市'))
        c=classify(self.event('藝術中心','臺北市二路2號'))
        self.assertEqual(len({e['locations'][0]['id'] for e in (a,b,c)}),3)
    def test_explicit_alias_and_whitespace(self):
        a=classify(self.event('金車文藝中心_承德館','大同區承德路三段131號','地區未提供'))
        b=classify(self.event('金車文藝中心　承德館','承德路三段131號','地區未提供'))
        self.assertEqual(a['locations'],b['locations'])
    def test_rooms_group_but_detail_is_retained(self):
        a=classify(self.event('府中15 3F展覽室','新北市府中路15號3樓','新北市'))
        b=classify(self.event('府中15 5F展覽室','新北市府中路15號5樓','新北市'))
        self.assertEqual(a['locations'],b['locations'])
        self.assertIn('3F',a['venue'])
    def test_missing_admin_and_event_title_are_not_invented_venues(self):
        self.assertEqual(classify(self.event())['venueStatus'],'missing')
        self.assertEqual(classify(self.event('鼓山區（高雄市）=','高雄市鼓山區','高雄市'))['venueStatus'],'uncertain')
        self.assertEqual(classify(self.event('測試活動','一街1號'))['venueStatus'],'address')
    def test_multi_room_park_keeps_all_places(self):
        e=self.event('華山1914・東2館 / 中2館','臺北市八德路1號');e['park']='huashan'
        r=classify(e)
        self.assertEqual(r['locations'][0]['id'],'huashan')
        self.assertIn('東2館 / 中2館',r['venue'])
    def test_online_exhibition_is_not_its_organizer_address(self):
        r=classify(self.event('《定格微光》線上攝影展','新北市文化路266號','新北市'))
        self.assertEqual(r['venueStatus'],'online')
        self.assertIn('無實體',r['venueName'])

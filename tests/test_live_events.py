import copy
import importlib.util
import json
import tempfile
import unittest
import ssl
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('live',ROOT/'scripts/update_live_events.py')
live=importlib.util.module_from_spec(spec); spec.loader.exec_module(live)
NOW='2026-10-06T09:00:00+08:00'

def row():
    return dict(UID='x',category='17',title='測試演唱會',showInfo=[dict(time='2026/11/01 19:00:00',location='台北市信義區',locationName='A',price='')])

class LiveEventsTests(unittest.TestCase):
    def test_certificate_compatibility_keeps_default_tls_verification(self):
        response=SimpleNamespace(stdout=json.dumps([row()]).encode())
        with patch.object(live,'urlopen',side_effect=ssl.SSLCertVerificationError('strict chain check')),patch.object(live.subprocess,'run',return_value=response) as curl:
            self.assertEqual(live.fetch('17')[0]['UID'],'x')
            args=curl.call_args.args[0]
            self.assertEqual(args[:2],['curl','--disable']);self.assertNotIn('--insecure',args)
            self.assertEqual(args[-1],live.API+'17')
    def test_multi_session_and_dedup(self):
        r=row(); r['showInfo'].append(copy.deepcopy(r['showInfo'][0])); s=copy.deepcopy(r['showInfo'][0]);s['time']='2026/11/02 19:00:00'; r['showInfo'].append(s)
        out=live.normalize([r,r],'concerts',NOW)
        self.assertEqual(len(out),1); self.assertEqual(len(out[0]['sessions']),2)
        self.assertEqual(out[0]['region'],'臺北市'); self.assertIsNone(out[0]['price']); self.assertIsNone(out[0]['saleAt'])
        self.assertIsNone(out[0]['ticketUrl'])
    def test_venue_and_date_change(self):
        r=row(); before=live.normalize([r],'concerts',NOW)
        r['showInfo'][0]['time']='2026/11/02 20:00:00'
        out=live.merge(before,live.normalize([r],'concerts',NOW),NOW)
        self.assertEqual(out[0]['id'],before[0]['id']); self.assertEqual(out[0]['status'],'changed')
        self.assertEqual(out[0]['revisions'][0]['previousSessions'],before[0]['sessions'])
        r['showInfo'][0]['locationName']='B'
        moved=live.merge(before,live.normalize([r],'concerts',NOW),NOW)
        self.assertEqual(len(moved),2); self.assertEqual(moved[1]['status'],'unconfirmed')
    def test_disappearance_is_not_cancelled(self):
        out=live.merge(live.normalize([row()],'concerts',NOW),[],NOW)
        self.assertEqual(out[0]['status'],'unconfirmed')
    def test_wrong_category_courses_and_fanmeet(self):
        r=row(); r['category']='11'; r['title']='脫口秀工作坊'
        self.assertEqual(live.normalize([r],'comedy',NOW),[])
        r['title']='單口喜劇專場';self.assertEqual(len(live.normalize([r],'comedy',NOW)),1)
        r['category']='17';r['title']='Fan Meeting'
        with self.assertRaises(ValueError):live.normalize([r],'concerts',NOW)
    def test_failed_fetch_preserves_and_manual_cancelled(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            root=Path(tmp); (root/'data').mkdir()
            e=live.normalize([row()],'concerts',NOW)[0]
            live.write(root/'data/concerts.json',dict(events=[e],sources=[dict(id='moc',lastSuccess=NOW)]))
            manual=copy.deepcopy(e);manual.update(id='manual',source='manual',status='cancelled',statusNote='官方取消公告')
            live.write(root/'data/concerts-manual.json',dict(events=[manual],sources=[]))
            def failure(_):raise TimeoutError()
            self.assertFalse(live.build('concerts',failure,root,NOW))
            result=live.read(root/'data/concerts.json',{})
            self.assertEqual(result['events'][0]['status'],'cancelled')
            self.assertEqual(result['sources'][0]['lastSuccess'],NOW)
            self.assertEqual(result['sources'][0]['status'],'error')
    def test_corruption_and_safe_urls(self):
        with self.assertRaises(ValueError):live.normalize([], 'concerts',NOW)
        r=row();r['title']='\ufffd'
        with self.assertRaises(ValueError):live.normalize([r],'concerts',NOW)
        self.assertEqual(live.safe_url('javascript:alert(1)'), '')
        self.assertEqual(live.safe_url('https://a:b@example.com'), '')

if __name__=='__main__':unittest.main()

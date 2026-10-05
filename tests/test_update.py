import contextlib
import importlib.util
import io
import json
import uuid
import unittest
import ssl
from urllib.error import URLError
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('update', Path(__file__).resolve().parents[1]/'scripts/update.py')
u = importlib.util.module_from_spec(spec)
spec.loader.exec_module(u)
TEST_ROOT = Path(__file__).resolve().parents[1]/'output'
TEST_ROOT.mkdir(exist_ok=True)

@contextlib.contextmanager
def test_directory():
    p = (TEST_ROOT / ('test-' + uuid.uuid4().hex)).resolve()
    assert p.parent == TEST_ROOT.resolve()
    p.mkdir()
    try:
        yield p
    finally:
        for f in p.iterdir():
            if f.is_file():
                f.unlink()
        p.rmdir()

def row(title='測試資料（僅單元測試）', start='2026/10/01', end='2026/10/20'):
    return {'UID':'abc123','version':'1.4','title':title,'category':'6','showInfo':[{'time':start+' 10:00:00','endTime':end+' 18:00:00','location':'台北市中正區','locationName':'測試館','onSales':'N'}]}

class UpdateTests(unittest.TestCase):
    def test_certificate_compatibility_uses_verified_curl(self):
        reason=ssl.SSLCertVerificationError('Missing Subject Key Identifier')
        process=unittest.mock.Mock(stdout=json.dumps([row()]).encode())
        with patch.object(u,'urlopen',side_effect=URLError(reason)), patch.object(u.subprocess,'run',return_value=process) as call, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(u.fetch(),[row()])
            args=call.call_args.args[0]
            self.assertNotIn('--insecure',args)
            self.assertIn('--proto',args)
            self.assertIn('=https',args)
            self.assertEqual(args[-1],u.API)
    def test_normalizes_and_deduplicates(self):
        events, rejected=u.normalize([row(),row()])
        self.assertEqual(len(events),1)
        self.assertEqual(rejected,0)
        self.assertEqual(events[0]['region'],'臺北市')
        self.assertEqual(events[0]['price'],'免費')

    def test_rejects_empty_malformed_and_reversed(self):
        for rows in ([],{},[row(end='2026/09/01')],[{}]):
            with self.assertRaises(ValueError): u.normalize(rows)

    def test_missing_price_not_assumed_free(self):
        r=row();r['showInfo'][0]['onSales']='Y'
        self.assertIn('未提供',u.normalize([r])[0][0]['price'])

    def test_unsafe_urls(self):
        for url in ['javascript:alert(1)','https://user:secret@example.com','data:text/html,hi']:
            self.assertEqual(u.safe_url(url),'')
        self.assertEqual(u.safe_url('https://example.com/a'),'https://example.com/a')

    def test_history_first_seen_and_disappearance(self):
        event=u.normalize([row()])[0][0]
        first=u.merge([], [event], '2026-10-01T00:00:00+08:00')
        again=u.merge(first,[event],'2026-10-02T00:00:00+08:00')
        self.assertEqual(first[0]['firstSeen'],again[0]['firstSeen'])
        missing=u.merge(again,[],'2026-10-03T00:00:00+08:00')
        self.assertTrue(missing[0]['missingFromSource'])
        self.assertEqual(len(missing),1)

    def test_failure_and_empty_preserve_last_success(self):
        with test_directory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            p=Path(tmp)
            self.assertEqual(u.run(p,[row()]),0)
            before=json.loads((p/'exhibitions.json').read_text(encoding='utf-8'))
            with patch.object(u,'fetch',side_effect=TimeoutError('test timeout')):
                self.assertEqual(u.run(p),1)
            after=json.loads((p/'exhibitions.json').read_text(encoding='utf-8'))
            self.assertEqual(before['events'],after['events'])
            self.assertEqual(before['sources']['moc']['lastSuccess'],after['sources']['moc']['lastSuccess'])
            self.assertEqual(after['sources']['moc']['state'],'error')
            self.assertEqual(u.run(p,[]),1)
            self.assertEqual(after['events'],json.loads((p/'exhibitions.json').read_text(encoding='utf-8'))['events'])

    def test_mass_loss_guard(self):
        with test_directory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            p=Path(tmp)
            rows=[row(str(i),end='2099/01/01') for i in range(30)]
            for i, r in enumerate(rows): r['UID']=str(i)
            self.assertEqual(u.run(p,rows),0)
            self.assertEqual(u.run(p,rows[:2]),1)
            state=json.loads((p/'exhibitions.json').read_text(encoding='utf-8'))
            self.assertEqual(len([e for e in state['events'] if e['source']=='moc']),30)

    def test_change_keeps_first_seen_and_previous_period(self):
        a=u.normalize([row()])[0]
        b=u.normalize([row(end='2026/11/01')])[0]
        history=u.merge(u.merge([],a,'2026-10-01T00:00:00+08:00'),b,'2026-10-02T00:00:00+08:00')
        self.assertEqual(len(history),1)
        self.assertEqual(history[0]['firstSeen'],'2026-10-01T00:00:00+08:00')
        self.assertEqual(history[0]['revisions'][0]['end'],'2026-10-20')
        self.assertEqual(history[0]['end'],'2026-11-01')

if __name__=='__main__': unittest.main()

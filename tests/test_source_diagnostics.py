"""Offline regression checks for failure diagnostics and retained snapshots."""
import contextlib
import io
import json
import socket
import ssl
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
from urllib.error import HTTPError,URLError

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import update as u
import update_venue_sources as v
import validate_live_events as live
from test_update import row,test_directory

class SourceDiagnosticsTests(unittest.TestCase):
    def test_safe_network_codes_do_not_embed_messages(self):
        for error,code in [(URLError(ssl.SSLCertVerificationError('private')), 'TLS_CERTIFICATE_VERIFICATION'),
                           (URLError(socket.gaierror('private')), 'DNS_FAILURE'),
                           (URLError(TimeoutError('private')), 'TIMEOUT'),
                           (HTTPError('https://private.example/',503,'private',None,None),'HTTP_503'),
                           (URLError('private'),'NETWORK_ERROR')]:
            self.assertEqual(u.safe_error_code(error),code)

    def test_counts_and_thresholds_are_preserved(self):
        counts={}
        events,rejected=u.normalize([row(),row()],counts)
        self.assertEqual((counts['inputCount'],counts['validCount'],counts['rejectedCount'],counts['eventCount']),(2,2,0,1))
        self.assertEqual(len(events),1)
        # Exactly 20% remains permitted; more than 20% is still rejected.
        u.normalize([row(),row(),row(),row(),{}],counts)
        with self.assertRaises(u.SourceUpdateError) as caught:
            u.normalize([row(),row(),row(),{},{}],counts)
        self.assertEqual(caught.exception.code,'REJECTION_RATE_OVER_20_PERCENT')
        self.assertEqual((counts['inputCount'],counts['validCount'],counts['rejectedCount']),(5,3,2))
        self.assertEqual(counts['rejectedReasons'],{'MISSING_REQUIRED_FIELD':2})
        for incoming,code in [([], 'EMPTY_INPUT'),({},'INPUT_NOT_LIST'),([{}],'NO_VALID_EVENTS')]:
            with self.assertRaises(u.SourceUpdateError) as caught:u.normalize(incoming)
            self.assertEqual(caught.exception.code,code)

    def test_curl_decode_failure_keeps_actual_reason_and_verified_tls(self):
        log=io.StringIO()
        with patch.object(u,'urlopen',side_effect=URLError(ssl.SSLCertVerificationError('private URL'))), \
             patch.object(u.subprocess,'run',return_value=Mock(stdout=b'not json')) as curl, \
             patch.object(u.time,'sleep'),contextlib.redirect_stderr(log):
            with self.assertRaises(json.JSONDecodeError):u.fetch()
        self.assertEqual(curl.call_count,3)
        args=curl.call_args.args[0]
        self.assertEqual(args[:2],['curl','--disable'])
        self.assertNotIn('--insecure',args)
        self.assertIn('INVALID_JSON',log.getvalue())
        self.assertNotIn('private',log.getvalue())

    def test_loss_guard_retains_last_success_and_current_counts(self):
        with test_directory() as tmp,contextlib.redirect_stdout(io.StringIO()):
            events,_=u.normalize([row()])
            previous=[{**events[0],'id':f'prior-{i}','title':f'Exhibition {i}','end':'2099-12-31','firstSeen':'2026-01-01','lastSeen':'2026-10-01'} for i in range(21)]
            old={'events':previous,'sources':{'moc':{'state':'ok','lastSuccess':'2026-10-01','count':21}}}
            (tmp/'exhibitions.json').write_text(json.dumps(old),encoding='utf-8')
            self.assertEqual(u.run(tmp,[row()]),1)
            result=json.loads((tmp/'exhibitions.json').read_text(encoding='utf-8'))
            status=result['sources']['moc']
            self.assertEqual(status['lastSuccess'],'2026-10-01')
            self.assertEqual(status['failureStage'],'loss-guard')
            self.assertEqual(status['reasonCode'],'SOURCE_LOSS_OVER_50_PERCENT')
            self.assertEqual(status['attemptCounts']['previousActiveCount'],21)
            self.assertEqual(status['attemptCounts']['inputCount'],1)
            self.assertEqual({e['id'] for e in result['events'] if e['source']=='moc'},{e['id'] for e in previous})

    def test_robots_and_policy_failure_stages(self):
        for replies,stage in [([URLError(TimeoutError())],'robots-fetch'),
                               (['User-agent: *\nAllow: /',URLError(socket.gaierror())],'policy-fetch')]:
            reader=v.PublicReader(v.SOURCES['pier2'])
            with patch.object(reader,'get',side_effect=replies):
                with self.assertRaises(URLError):reader.prepare({'policyDigest':'unused'})
            self.assertEqual(reader.stage,stage)
        reader=v.PublicReader(v.SOURCES['pier2'])
        with patch.object(reader,'get',return_value='User-agent: *\nDisallow: /'):
            with self.assertRaises(PermissionError):reader.prepare({'policyDigest':'unused'})
        self.assertEqual(reader.stage,'robots-check')
        reader=v.PublicReader(v.SOURCES['pier2'])
        with patch.object(reader,'get',side_effect=['User-agent: *\nAllow: /','policy']),patch.object(v,'policy_digest',return_value='changed'):
            with self.assertRaises(PermissionError):reader.prepare({'policyDigest':'approved'})
        self.assertEqual(reader.stage,'policy-check')

    def test_failed_venue_attempt_does_not_reuse_old_checked_count(self):
        with test_directory() as tmp:
            (tmp/'data').mkdir()
            previous=[{'id':'p','source':'pier2','lastSeen':'2026-10-01','end':'2099-12-31'}]
            (tmp/'data/curated.json').write_text(json.dumps(previous),encoding='utf-8')
            (tmp/'data/venue-source-status.json').write_text(json.dumps({'pier2':{'state':'ok','lastSuccess':'2026-10-01','checkedCount':12}}),encoding='utf-8')
            (tmp/'data/venue-policy.json').write_text(json.dumps({'pier2':{}}),encoding='utf-8')
            with patch.object(v,'ROOT',tmp),patch.object(v.PublicReader,'get',side_effect=URLError(TimeoutError('private'))), \
                 patch.object(v,'RenderedReader') as browser,contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(v.run(source_names=['pier2']),1)
            browser.assert_not_called()
            status=json.loads((tmp/'data/venue-source-status.json').read_text(encoding='utf-8'))['pier2']
            self.assertEqual((status['checkedCount'],status['attemptedCount'],status['lastSuccessfulCheckedCount']),(0,0,12))
            self.assertEqual((status['failureStage'],status['reasonCode']),('robots-fetch','TIMEOUT'))
            self.assertEqual(status['lastSuccess'],'2026-10-01')
            self.assertEqual(json.loads((tmp/'data/curated.json').read_text(encoding='utf-8')),previous)
            for p in (tmp/'data').iterdir():p.unlink()
            (tmp/'data').rmdir()

    def test_partial_venue_failure_retains_whole_previous_snapshot(self):
        with test_directory() as tmp:
            (tmp/'data').mkdir()
            previous=[{'id':'s','source':'songshan','url':v.SOURCES['songshan']['base']+'/exhibition/activity/1',
                       'title':'One','venue':'Hall','lastSeen':'2026-10-01','end':'2099-12-31'}]
            for name,data in [('curated.json',previous),('venue-source-status.json',{'songshan':{'lastSuccess':'2026-10-01','checkedCount':8}}),('venue-policy.json',{'songshan':{}})]:
                (tmp/'data'/name).write_text(json.dumps(data),encoding='utf-8')
            found={previous[0]['url']:{'title':'One'},v.SOURCES['songshan']['base']+'/exhibition/activity/2':{'title':'Two'}}
            with patch.object(v,'ROOT',tmp),patch.object(v.PublicReader,'prepare'), \
                 patch.object(v.PublicReader,'get',side_effect=['list','detail',URLError(TimeoutError())]), \
                 patch.object(v,'discover',return_value=found),patch.object(v,'parse_detail',return_value={**previous[0],'title':'Changed'}), \
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(v.run(source_names=['songshan']),1)
            status=json.loads((tmp/'data/venue-source-status.json').read_text(encoding='utf-8'))['songshan']
            self.assertEqual((status['checkedCount'],status['attemptedCount'],status['lastSuccessfulCheckedCount']),(1,2,8))
            self.assertEqual(status['failureStage'],'detail-fetch')
            self.assertEqual(json.loads((tmp/'data/curated.json').read_text(encoding='utf-8')),previous)
            for p in (tmp/'data').iterdir():p.unlink()
            (tmp/'data').rmdir()

    def test_sale_time_conflicts_are_reported_without_rewriting_claims(self):
        event={'id':'x','saleAt':'2026-10-04T12:30:00+08:00','saleNote':'一般開賣時間未公布／來源未提供。','tickets':[]}
        self.assertEqual(live.sale_time_conflicts({'events':[event]}),['x'])
        self.assertEqual(event['saleAt'],'2026-10-04T12:30:00+08:00')
        self.assertEqual(live.sale_time_conflicts({'events':[{**event,'saleAt':None}]}),[])

    def test_cloud_reviewed_manual_and_generated_sale_claims_agree(self):
        expected={'manual-taipei-live':'2026-01-05T00:00:00+08:00',
                  'manual-coldn':'2026-10-04T12:30:00+08:00',
                  'manual-creepy':'2026-10-01T00:00:00+08:00',
                  'manual-taichung-live':None,'manual-john':None}
        root=Path(__file__).resolve().parents[1]
        manual=json.loads((root/'data/comedy-manual.json').read_text(encoding='utf-8'))
        generated=json.loads((root/'data/comedy.json').read_text(encoding='utf-8'))
        self.assertEqual(live.sale_time_conflicts(manual),[])
        self.assertEqual(live.sale_time_conflicts(generated),[])
        snapshots=[{e['id']:e for e in data['events']} for data in (manual,generated)]
        for eid,value in expected.items():
            for records in snapshots:
                event=records[eid]
                self.assertEqual(event['saleAt'],value)
                self.assertEqual(event['verifiedAt'],'2026-10-06')
                self.assertTrue(all(t['saleAt']==value and t['checkedAt']=='2026-10-06' for t in event['tickets']))
            self.assertEqual(snapshots[0][eid]['saleNote'],snapshots[1][eid]['saleNote'])
        for records in snapshots:
            self.assertIn('2026/09/24 00:00',records['manual-taichung-live']['saleNote'])
            self.assertIn('早鳥 NT$450',records['manual-taichung-live']['price'])
            self.assertIn('一般票開賣時間來源未提供',records['manual-taichung-live']['saleNote'])
            self.assertIn('2026/10/04 12:30',records['manual-john']['saleNote'])
            self.assertIn('2026/10/30 12:30',records['manual-john']['saleNote'])
            self.assertIn('不能據早鳥截止時間推定',records['manual-john']['saleNote'])

if __name__=='__main__':unittest.main()

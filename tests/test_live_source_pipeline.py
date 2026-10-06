"""Only synthetic fixtures: pagination, classification, retention and identity."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import live_sources as sources
import update_live_events as live

NOW='2026-10-06T09:00:00+08:00'

def event(uid='one',region='台北市',venue='Hall A',date='2026-11-01',title='Test Comedy Night'):
    return {'sourceUid':uid,'title':title,'region':region,'venue':venue,
            'sessions':[{'date':date,'time':'19:00'}],'sourceUrl':'https://example.com/events/'+uid,
            'tickets':[{'platform':'Verified Local Organizer','url':'https://example.com/tickets/'+uid,
                        'checkedAt':'2026-10-06','sessions':[{'date':date,'time':'19:00'}]}]}

def item(uid='one',**kwargs):
    return {'sourceUid':uid,'officialFactsReviewed':True,'evidence':{'title':'English Comedy Night'},'event':event(uid,**kwargs)}

def envelope(items=None,second=None):
    pages=[{'id':'1','url':'https://example.com/catalog','items':items if items is not None else [item()]}]
    if second is not None:pages.append({'id':'2','url':'https://example.com/catalog?page=2','items':second})
    return {'sourceId':'test-source','kind':'comedy','reviewedAt':'2026-10-06',
            'traversal':{'scope':'Synthetic catalog, pages 1–2','expectedPageIds':['1','2'],'complete':True},'pages':pages}

class PipelineTests(unittest.TestCase):
    def root(self,tmp):
        root=Path(tmp)
        sources.write(root/'data/live-source-registry.json',{'schemaVersion':1,'sources':[
            {'id':'test-source','name':'Synthetic source','url':'https://example.com','kinds':['comedy'],'adapter':'reviewed-json'}]})
        sources.write(root/'data/comedy-manual.json',{'events':[],'sources':[]})
        sources.write(root/'data/comedy.json',{'events':[],'sources':[{'id':'moc','status':'ok','lastSuccess':NOW}]})
        return root

    def test_multifield_classification_english_and_unlabelled_special(self):
        for evidence in [{'title':'English Comedy Night'}, {'title':'My Life','description':'A stand-up special'},
                         {'title':'No genre in the name','reviewedKind':'comedy'}]:
            self.assertEqual(sources.classify('comedy',evidence)[0],'included')
        for evidence in [{'title':'Stand-up workshop'},{'title':'Comedy Musical'},{'title':'單口喜劇課程'}]:
            self.assertEqual(sources.classify('comedy',evidence)[0],'excluded')
        self.assertEqual(sources.classify('comedy',{'title':'A generic show'})[0],'pending')
        row={'category':'11','UID':'u','title':'My Life','descriptionFilterHtml':'A stand-up special',
             'showInfo':[{'time':'2026/11/01 19:00','location':'台北市','locationName':'Hall'}]}
        counts={};self.assertEqual(len(live.normalize([row],'comedy',NOW,counts)),1)
        self.assertEqual((counts['discovered'],counts['included']),(1,1))

    def test_second_page_completeness_and_all_decisions_are_audited(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=self.root(tmp)
            pending=item('pending');pending['officialFactsReviewed']=False
            excluded=item('course');excluded['evidence']={'title':'Stand-up workshop'}
            self.assertTrue(sources.import_reviewed(root,'comedy','test-source',envelope([item(),pending,excluded]),NOW))
            snap=sources.read(sources.snapshot_path(root,'comedy','test-source'),{})
            self.assertFalse(snap['status']['coverageComplete'])
            self.assertEqual([snap['status'][k] for k in ('discovered','included','excluded','pending','failed')],[3,1,1,1,0])
            self.assertEqual(len(snap['records']),3)
            self.assertTrue(sources.import_reviewed(root,'comedy','test-source',envelope([item()], [item('two',date='2027-01-01')]),NOW))
            snap=sources.read(sources.snapshot_path(root,'comedy','test-source'),{})
            self.assertTrue(snap['status']['coverageComplete']);self.assertEqual(snap['status']['pagesVisited'],2)
            self.assertIn('2027-01-01',[s['date'] for e in snap['events'] for s in e['sessions']])

    def test_second_rebuild_retains_independent_snapshot_and_verified_unknown_platform(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=self.root(tmp)
            sources.import_reviewed(root,'comedy','test-source',envelope(),NOW)
            for day in (NOW,'2026-10-07T09:00:00+08:00'):
                self.assertTrue(live.build('comedy',lambda _:self.fail('network call'),root,day,manual_only=True))
                output=sources.read(root/'data/comedy.json',{})
                self.assertEqual(len(output['events']),1)
                self.assertEqual(output['events'][0]['tickets'][0]['platform'],'Verified Local Organizer')
            self.assertEqual(live.platform('https://www.kktix.com/events/a'),'KKTIX')
            unsafe=event();unsafe['tickets'][0]['url']='https://user:password@example.com/events/a'
            with self.assertRaises(ValueError):sources.validate_event(unsafe,'test-source',NOW)

    def test_source_failure_keeps_last_success_and_entire_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=self.root(tmp);sources.import_reviewed(root,'comedy','test-source',envelope(),NOW)
            path=sources.snapshot_path(root,'comedy','test-source');before=sources.read(path,{})
            bad=envelope();bad['pages'][0]['items'][0]['event']['sessions'][0]['date']='invalid'
            self.assertFalse(sources.import_reviewed(root,'comedy','test-source',bad,'2026-10-06T10:00:00+08:00'))
            after=sources.read(path,{})
            self.assertEqual(after['events'],before['events']);self.assertEqual(after['status']['lastSuccess'],NOW)
            self.assertEqual(after['status']['failed'],1)
            self.assertFalse(live.build('comedy',lambda _:None,root,NOW,manual_only=True))
            self.assertEqual(len(sources.read(root/'data/comedy.json',{})['events']),1)

    def test_zero_matches_is_not_zero_discovery_or_full_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=self.root(tmp);excluded=item();excluded['evidence']={'title':'Workshop'}
            self.assertTrue(sources.import_reviewed(root,'comedy','test-source',envelope([excluded]),NOW))
            state=sources.read(sources.snapshot_path(root,'comedy','test-source'),{})['status']
            self.assertEqual((state['discovered'],state['included'],state['excluded']),(1,0,1))
            self.assertFalse(state['coverageComplete']);self.assertEqual(state['status'],'ok')
            self.assertFalse(sources.import_reviewed(root,'comedy','test-source',envelope([]),NOW))
        with tempfile.TemporaryDirectory() as tmp:
            root=self.root(tmp)
            row={'UID':'u','category':'11','title':'Generic unknown show'}
            self.assertTrue(live.build('comedy',lambda _:[row],root,NOW))
            state=sources.read(root/'data/comedy.json',{})['sources'][0]
            self.assertEqual((state['discovered'],state['included'],state['pending']),(1,0,1))
            self.assertFalse(state['coverageComplete'])

    def test_city_additions_order_and_session_overlap_deduplicate(self):
        a=sources.validate_event(event(), 'test-source',NOW)
        b=copy.deepcopy(a);b.update(id='manual',source='manual',region='臺北市',venue='Hall　A')
        b['sessions']=[{'date':'2026-11-02','time':'19:00'},*b['sessions']]
        c=sources.validate_event(event('one',region='臺中市',venue='Hall A'), 'test-source',NOW)
        out=sources.reconcile([b,a,c])
        self.assertEqual(len(out),2);self.assertEqual(len(out[0]['sessions']),2)
        self.assertEqual(out[0]['id'],'manual');self.assertEqual(len(out[0]['sourceRefs']),2)
        self.assertEqual(out,sources.reconcile([b,{**a,'sessions':list(reversed(a['sessions']))},c]))
        later=sources.validate_event(event('another',date='2026-12-01'), 'test-source',NOW)
        self.assertEqual(len(sources.reconcile([a,later])),2)

    def test_preexisting_unregistered_source_is_not_washed_out(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=self.root(tmp);e=sources.validate_event(event(),'old-independent-source',NOW)
            sources.write(root/'data/comedy.json',{'events':[e],'sources':[{'id':'moc','status':'ok','lastSuccess':NOW}]})
            live.build('comedy',lambda _:None,root,NOW,manual_only=True)
            self.assertEqual(sources.read(root/'data/comedy.json',{})['events'][0]['source'],'old-independent-source')

    def test_moc_failure_retains_snapshot_and_does_not_inherit_attempt_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=self.root(tmp)
            row={'category':'11','UID':'u','title':'Stand-up special',
                 'showInfo':[{'time':'2026/11/01 19:00','location':'臺北市','locationName':'Hall'}]}
            self.assertTrue(live.build('comedy',lambda _:[row],root,NOW))
            before=sources.read(sources.snapshot_path(root,'comedy','moc'),{})
            def fail(_):raise TimeoutError('must not become source prose')
            self.assertFalse(live.build('comedy',fail,root,'2026-10-07T09:00:00+08:00'))
            after=sources.read(sources.snapshot_path(root,'comedy','moc'),{})
            self.assertEqual(after['events'],before['events'])
            self.assertEqual(after['status']['lastSuccess'],NOW)
            self.assertIsNone(after['status']['discovered'])
            self.assertNotIn('must not',after['status']['message'])

    def test_cancelled_record_is_not_scheduled_and_changed_date_replaces_stable_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=self.root(tmp)
            cancelled=item('cancelled');cancelled['event']['status']='cancelled'
            payload=envelope([item(),cancelled])
            self.assertTrue(sources.import_reviewed(root,'comedy','test-source',payload,NOW))
            changed=item(date='2026-11-03')
            self.assertTrue(sources.import_reviewed(root,'comedy','test-source',envelope([changed,cancelled],[]),NOW))
            events=sources.read(sources.snapshot_path(root,'comedy','test-source'),{})['events']
            self.assertEqual(len(events),2)
            one=next(e for e in events if e['sourceUid']=='one')
            self.assertEqual(one['sessions'][0]['date'],'2026-11-03')
            self.assertEqual(one['status'],'changed')
            self.assertEqual(one['revisions'][0]['previousSessions'][0]['date'],'2026-11-01')
            self.assertEqual(next(e for e in events if e['sourceUid']=='cancelled')['status'],'cancelled')

    def test_review_date_is_distinct_from_later_import_attempt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=self.root(tmp)
            self.assertTrue(sources.import_reviewed(root,'comedy','test-source',envelope(),'2026-10-07T09:00:00+08:00'))
            snapshot=sources.read(sources.snapshot_path(root,'comedy','test-source'),{})
            self.assertEqual(snapshot['status']['reviewedAt'],'2026-10-06')
            self.assertEqual(snapshot['events'][0]['verifiedAt'],'2026-10-06')
            future=envelope();future['reviewedAt']='2026-10-08'
            self.assertFalse(sources.import_reviewed(root,'comedy','test-source',future,'2026-10-07T09:00:00+08:00'))

if __name__=='__main__':unittest.main()

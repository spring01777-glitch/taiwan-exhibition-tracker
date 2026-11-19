"""Reviewed link applies only to the two officially confirmed sessions."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from test_live_events import live, ROOT

UID='https://www.arena.taipei/News_Content.aspx?n=2E1489AFE4B1BEA1&s=877C12B2A508D887'

class ReviewedAyalTickets(unittest.TestCase):
    def test_offline_rebuild_preserves_exact_ticket_scope_and_general_sale(self):
        review=json.loads((ROOT/'data/live-event-links.json').read_text())[UID]
        event=next(e for e in json.loads((ROOT/'data/live-sources/concerts/taipei-arena.json').read_text())['events'] if e['sourceUid']==UID)
        event=copy.deepcopy(event)
        event['sessions'].append({'date':'2027-04-16','time':'19:00'})
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'data').mkdir()
            live.write(root/'data/concerts-manual.json',{'events':[event],'sources':[]})
            live.write(root/'data/live-event-links.json',{UID:review})
            with patch.object(live,'fetch',side_effect=AssertionError('offline only')):
                self.assertTrue(live.build('concerts',live.fetch,root,'2026-11-20T04:50:00+08:00',manual_only=True))
            out=live.read(root/'data/concerts.json',{})['events'][0]
            self.assertEqual(out['saleAt'],'2026-11-21T14:00:00+08:00')
            self.assertEqual(len(out['tickets']),1)
            ticket=out['tickets'][0]
            self.assertEqual(ticket['url'],'https://tixcraft.com/activity/detail/27_ayalkomod')
            self.assertEqual(ticket['sessions'],[{'date':'2027-04-17','time':'19:00'},{'date':'2027-04-18','time':'16:30'}])
            self.assertIn('12:00–14:00',out['saleNote'])
            self.assertIn('15:00–17:00',out['saleNote'])
            self.assertIn('須專屬購票碼',out['saleNote'])
            self.assertIn('未列此階段結束時刻',out['saleNote'])

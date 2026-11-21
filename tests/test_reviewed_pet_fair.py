"""One manually verified TaiNEX pet fair, without a new crawler."""
import json
from pathlib import Path
import unittest
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import update

class ReviewedPetFairTests(unittest.TestCase):
    def test_reviewed_pet_fair_identity_and_display_facts(self):
        rows=json.loads((ROOT/'data/curated.json').read_text())
        url='https://www.tainex.com.tw/event/738'
        matches=[e for e in rows if e['id']=='tainex-pet-fair-2026-11' or e['url']==url]
        self.assertEqual(len(matches),1)
        e,=update.classify_all(matches)
        self.assertEqual((e['start'],e['end']),('2026-11-27','2026-11-30'))
        self.assertEqual(e['source'],'tainex')
        self.assertEqual(e['url'],url)
        self.assertIn('2 館 1 樓',e['venue'])
        self.assertIn('10:00–18:00',e['summary'])
        self.assertEqual(e['locations'][0]['status'],'named')

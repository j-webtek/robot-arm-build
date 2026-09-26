import hashlib,json
from pathlib import Path
import unittest
AI=Path(__file__).resolve().parents[1]

class DevelopmentTailsEvidence(unittest.TestCase):
    def test_strata_recount_and_frozen_data(self):
        path=AI/'eval/development_tails_v0.manifest.json';m=json.loads(path.read_text())
        r=json.loads((AI/'eval/development_tails_v0_scorecard.json').read_text())
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),r['manifest_sha256'])
        for f,h in m['file_sha256'].items():self.assertEqual(hashlib.sha256((AI.parents[1]/f).read_bytes()).hexdigest(),h)
        self.assertEqual(len(r['cases']),600)
        self.assertEqual({c['seed'] for c in r['cases']},set(range(15000000,15000200)))
        for c in r['cases']:self.assertEqual(c['large_error'],c['maximum_key_error_mm']>3.0)
        for field,strata in r['strata'].items():
            self.assertEqual(sum(s['images'] for s in strata.values()),600)
            for name,s in strata.items():
                rows=[c for c in r['cases'] if c[field]==name]
                self.assertEqual(s['large_error_images'],sum(c['large_error'] for c in rows))
        self.assertFalse(r['qualification_installed'])

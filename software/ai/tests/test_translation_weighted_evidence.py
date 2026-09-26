import hashlib
import json
from pathlib import Path
import unittest
AI=Path(__file__).resolve().parents[1]

class TranslationWeightedEvidence(unittest.TestCase):
    def test_paired_budget_selection_and_sources(self):
        path=AI/'train/translation_weighted_v0_plan.json'
        plan=json.loads(path.read_text())
        report=json.loads((AI/'eval/translation_weighted_v0_scorecard.json').read_text())
        self.assertEqual(report['plan_sha256'],hashlib.sha256(path.read_bytes()).hexdigest())
        for f,h in plan['file_sha256'].items():
            self.assertEqual(hashlib.sha256((AI.parents[1]/f).read_bytes()).hexdigest(),h)
        a,b=report['results']
        self.assertEqual(a['training_pixels_sha256'],b['training_pixels_sha256'])
        self.assertEqual(a['development_pixels_sha256'],b['development_pixels_sha256'])
        self.assertEqual([a['loss_weights'],b['loss_weights']],[[1,1,1],[4,4,1]])
        for r in (a,b):
            self.assertEqual(r['selected_epoch'],min(r['history'],key=lambda e:e['development_mse'])['epoch'])
            self.assertEqual(len(r['history']),12)
            self.assertFalse(r['qualification_installed'])
    def test_candidate_rule(self):
        r=json.loads((AI/'eval/translation_weighted_v0_scorecard.json').read_text())
        a,b=r['results']
        self.assertLess(b['mean_mm'],a['mean_mm'])
        self.assertLess(b['center_mean_mm'],a['center_mean_mm'])
        self.assertLessEqual(b['yaw_p95_degrees'],1.1*a['yaw_p95_degrees'])

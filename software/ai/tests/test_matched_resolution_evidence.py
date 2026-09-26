import hashlib
import json
from pathlib import Path
import unittest
AI=Path(__file__).resolve().parents[1]


class MatchedResolutionEvidence(unittest.TestCase):
    def test_frozen_sources_and_selection(self):
        path=AI/'train/matched_resolution_v0_plan.json'
        plan=json.loads(path.read_text())
        report=json.loads((AI/'eval/matched_resolution_v0_scorecard.json').read_text())
        self.assertEqual(report['plan_sha256'],hashlib.sha256(path.read_bytes()).hexdigest())
        for relative,digest in plan['file_sha256'].items():
            self.assertEqual(hashlib.sha256((AI.parents[1]/relative).read_bytes()).hexdigest(),digest)
        self.assertNotIn('evaluation_groups',plan)
        self.assertNotIn('calibration_groups',plan)
        self.assertEqual([r['input_size'] for r in report['results']],plan['sizes'])
        for r in report['results']:
            self.assertEqual(r['selected_epoch'],min(r['history'],key=lambda e:e['development_mse'])['epoch'])
            self.assertEqual(len(r['history']),12)
            self.assertEqual(r['training_images'],3600)
            self.assertEqual(r['development_images'],600)
            self.assertEqual(r['target_view_count'],27600)
            self.assertEqual(r['hardware_writes'],0)
            self.assertFalse(r['qualification_installed'])

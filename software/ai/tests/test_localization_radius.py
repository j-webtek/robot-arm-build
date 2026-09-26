"""Frozen calibration/evaluation separation and uncertainty score evidence."""
import hashlib
import json
import math
from pathlib import Path
import sys
import unittest
AI_DIR=Path(__file__).resolve().parents[1];ROOT=AI_DIR.parents[1]
sys.path[:0]=[str(AI_DIR),str(AI_DIR.parent/'src')]
from vision.evaluate_localization_radius import empirical_radius
from rocell_ai.scene_observation import canonical_hash


class LocalizationRadiusTests(unittest.TestCase):
    def test_empirical_radius_boundary_and_invalid_inputs(self):
        self.assertEqual(empirical_radius(list(range(1,101)),0.95),95)
        for values in ([],[float('nan')],[-1],[True]):
            with self.assertRaises(ValueError): empirical_radius(values,0.95)

    def test_frozen_split_sources_and_scorecard_are_consistent(self):
        path=AI_DIR/'eval/localization_radius_v0.manifest.json'
        manifest=json.loads(path.read_text());report=json.loads((AI_DIR/'eval/localization_radius_v0_scorecard.json').read_text())
        self.assertFalse(set(manifest['calibration_seeds'])&set(manifest['evaluation_seeds']))
        for relative,digest in manifest['file_sha256'].items():
            self.assertEqual(hashlib.sha256((ROOT/relative).read_bytes()).hexdigest(),digest)
        self.assertEqual(report['manifest_sha256'],hashlib.sha256(path.read_bytes()).hexdigest())
        for split in ('calibration','evaluation'):
            groups=report[split+'_groups']
            self.assertEqual([g['seed'] for g in groups],manifest[split+'_seeds'])
            self.assertEqual(report[split+'_data_sha256'],canonical_hash(groups))
            for group in groups:
                self.assertEqual(len(group['cases']),3)
                self.assertEqual(group['maximum_error_mm'],max(c['maximum_key_error_mm'] for c in group['cases']))
        radius=empirical_radius([g['maximum_error_mm'] for g in report['calibration_groups']],0.95)
        self.assertEqual(report['empirical_radius_mm'],radius)
        self.assertEqual(report['evaluation_covered_groups'],sum(g['maximum_error_mm']<=radius for g in report['evaluation_groups']))
        self.assertIsNone(report['qualification'])
        self.assertFalse(report['qualification_installed'])
        self.assertEqual(report['study_sha256'],canonical_hash({k:v for k,v in report.items() if k!='study_sha256'}))

if __name__=='__main__': unittest.main()

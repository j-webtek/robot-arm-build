import hashlib
import json
import math
from pathlib import Path
import sys
import unittest
AI=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(AI))
from vision.evaluate_prediction_margin import margin, ROOT, canonical_hash


class PredictionMarginTests(unittest.TestCase):
    def test_rotated_rectangle(self):
        self.assertAlmostEqual(margin((0,3),(0,0),math.pi/2,(5,2),1),1)
        self.assertLess(margin((3,0),(0,0),math.pi/2,(5,2),1),0)

    def test_edge_and_radius(self):
        self.assertEqual(margin((6,0),(0,0),0,(7,7),1),0)
        self.assertLess(margin((6.01,0),(0,0),0,(7,7),1),0)

    def test_invalid_geometry(self):
        for radius in (-1,float('nan'),float('inf'),True):
            with self.assertRaises(ValueError):
                margin((0,0),(0,0),0,(7,7),radius)

    def test_frozen_evidence(self):
        path=AI/'eval/prediction_margin_v0.manifest.json'
        m=json.loads(path.read_text())
        self.assertEqual(m['evaluation_seeds'],list(range(13000000,13000100)))
        for f,digest in m['file_sha256'].items():
            self.assertEqual(hashlib.sha256((ROOT/f).read_bytes()).hexdigest(),digest)
        r=json.loads((AI/'eval/prediction_margin_v0_scorecard.json').read_text())
        digest=r.pop('report_sha256')
        self.assertEqual(canonical_hash(r),digest)
        self.assertEqual(r['manifest_sha256'],hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(r['radius_mm'],m['radius_mm'])
        self.assertEqual(len(r['cases']),300)
        for prefix in ('oracle','nominal'):
            self.assertEqual(r[prefix+'_fitting_predictions'],sum(len(c[prefix+'_fitting_keys']) for c in r['cases']))
        self.assertFalse(r['qualification_installed'])
        self.assertEqual(r['hardware_writes'],0)

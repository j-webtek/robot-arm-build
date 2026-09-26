import hashlib
import json
from pathlib import Path
import unittest
AI=Path(__file__).resolve().parents[1]

class PoseDecompositionEvidence(unittest.TestCase):
    def test_same_baseline_and_images(self):
        r=json.loads((AI/'eval/pose_decomposition_v0_scorecard.json').read_text())
        old=json.loads((AI/'eval/local_refinement_v0_scorecard.json').read_text())
        self.assertEqual(r['image_data_sha256'],old['image_data_sha256'])
        self.assertEqual(r['results']['baseline'],old['results']['baseline'])
        for condition,pose in r['pose_components'].items():
            self.assertAlmostEqual(pose['translation_mean_mm'],r['results']['translation_only']['conditions'][condition]['mean_mm'],places=10)
        self.assertFalse(r['qualification_installed'])
    def test_source_pins(self):
        path=AI/'eval/pose_decomposition_v0.manifest.json'
        m=json.loads(path.read_text())
        r=json.loads((AI/'eval/pose_decomposition_v0_scorecard.json').read_text())
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),r['manifest_sha256'])
        for f,digest in m['file_sha256'].items():
            self.assertEqual(hashlib.sha256((AI.parents[1]/f).read_bytes()).hexdigest(),digest)

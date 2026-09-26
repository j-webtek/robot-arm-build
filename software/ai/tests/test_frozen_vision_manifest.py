"""Frozen evaluation seeds and source pins must remain consistent."""
import hashlib
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[3]


class FrozenVisionManifestTests(unittest.TestCase):
    def test_frozen_sources_and_seed_groups(self):
        manifest=json.loads((ROOT/'software/ai/eval/frozen_vision_v0.manifest.json').read_text())
        cases=manifest['cases']
        self.assertEqual(len(cases),24)
        self.assertEqual(len({case['case_id'] for case in cases}),24)
        self.assertEqual({case['seed'] for case in cases},set(range(4000000,4000008)))
        for seed in range(4000000,4000008):
            self.assertEqual({c['condition'] for c in cases if c['seed']==seed}, {'standard','appearance_shift','challenge'})
        for relative,digest in manifest['file_sha256'].items():
            self.assertEqual(hashlib.sha256((ROOT/relative).read_bytes()).hexdigest(),digest,relative)
        self.assertEqual(manifest['diagnostic_error_budget_mm'],5.0)
        self.assertFalse(manifest['physical_execution_authorized'])


if __name__=='__main__':
    unittest.main()

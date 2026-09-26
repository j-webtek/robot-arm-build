"""Frozen conservative study lineage and independent coverage recount."""
import hashlib,json,math
from pathlib import Path
import sys
import unittest
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1]
sys.path[:0]=[str(AI),str(AI.parent/'src')]
from rocell_ai.scene_observation import canonical_hash

class ConservativeRadiusTests(unittest.TestCase):
    def test_fresh_split_and_source_pins(self):
        manifest=json.loads((AI/'eval/conservative_radius_v0.manifest.json').read_text())
        calibration=set(manifest['calibration_seeds']);evaluation=set(manifest['evaluation_seeds'])
        self.assertEqual(len(calibration),1000);self.assertEqual(len(evaluation),500)
        self.assertFalse(calibration&evaluation)
        plan=json.loads((AI/'train/robust_pose_v0_plan.json').read_text())
        for key in ('training_groups','development_groups','calibration_groups','evaluation_groups'):
            start,count=plan[key];prior=set(range(start,start+count))
            self.assertFalse((calibration|evaluation)&prior)
        for path,digest in manifest['file_sha256'].items():
            self.assertEqual(hashlib.sha256((ROOT/path).read_bytes()).hexdigest(),digest)

    def test_recorded_bound_comes_only_from_calibration_and_never_installs_trust(self):
        path=AI/'eval/conservative_radius_v0.manifest.json';m=json.loads(path.read_text())
        r=json.loads((AI/'eval/conservative_radius_v0_scorecard.json').read_text())
        self.assertEqual(r['manifest_sha256'],hashlib.sha256(path.read_bytes()).hexdigest())
        calibration=sorted(s['maximum_error_mm'] for s in r['calibration_scores'])
        radius=calibration[math.ceil(len(calibration)*m['empirical_coverage_target'])-1]
        self.assertEqual(radius,r['empirical_radius_mm'])
        covered=sum(s['maximum_error_mm']<=radius for s in r['evaluation_scores'])
        self.assertEqual(covered,r['evaluation_covered_groups'])
        self.assertEqual(r['coverage_criterion_passed'],covered/500>=m['minimum_evaluation_coverage'])
        self.assertIsNone(r['qualification']);self.assertFalse(r['qualification_installed'])
        self.assertFalse(r['physical_execution_authorized'])
        self.assertEqual(r['report_sha256'],canonical_hash({k:v for k,v in r.items() if k!='report_sha256'}))

if __name__=='__main__': unittest.main()

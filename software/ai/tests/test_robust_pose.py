"""Development-only selection and fresh split integrity for robustness training."""
import hashlib,json
from pathlib import Path
import sys
import unittest
AI=Path(__file__).resolve().parents[1];ROOT=AI.parents[1]
sys.path[:0]=[str(AI),str(AI.parent/'src')]
from rocell_ai.scene_observation import canonical_hash

class RobustPoseTests(unittest.TestCase):
    def test_sources_splits_and_development_selection(self):
        plan=json.loads((AI/'train/robust_pose_v0_plan.json').read_text())
        result=json.loads((AI/'train/robust_pose_v0_result.json').read_text())
        sets=[]
        for name in ['training_groups','development_groups','calibration_groups','evaluation_groups']:
            start,count=plan[name];sets.append(set(range(start,start+count)))
        for index,group in enumerate(sets):
            for other in sets[index+1:]: self.assertFalse(group&other)
        for path,digest in plan['file_sha256'].items():
            self.assertEqual(hashlib.sha256((ROOT/path).read_bytes()).hexdigest(),digest)
        best=min(result['history'],key=lambda row:row['development_mse'])
        self.assertEqual(result['selected_epoch'],best['epoch'])
        self.assertFalse(result['calibration_or_evaluation_used_for_selection'])
        self.assertEqual(result['plan_sha256'],hashlib.sha256((AI/'train/robust_pose_v0_plan.json').read_bytes()).hexdigest())

    def test_comparison_uses_same_images_and_preserves_failed_qualification(self):
        candidate=json.loads((AI/'eval/robust_pose_v0_scorecard.json').read_text())
        reference=json.loads((AI/'eval/robust_pose_v0_reference_scorecard.json').read_text())
        for r in [candidate,reference]:
            self.assertEqual(r['study_sha256'],canonical_hash({k:v for k,v in r.items() if k!='study_sha256'}))
            self.assertIsNone(r['qualification'])
            self.assertFalse(r['qualification_installed'])
        for split in ['calibration_groups','evaluation_groups']:
            self.assertEqual([[c['image_sha256'] for c in g['cases']] for g in candidate[split]],
                             [[c['image_sha256'] for c in g['cases']] for g in reference[split]])

if __name__=='__main__': unittest.main()

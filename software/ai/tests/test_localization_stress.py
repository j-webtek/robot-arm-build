"""Rejected archived quality and coordinates must not produce a simulated route."""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

AI_DIR=Path(__file__).resolve().parents[1]
WORKSPACE=AI_DIR.parents[1]
sys.path[:0]=[str(AI_DIR),str(AI_DIR.parent/'src')]
from rocell_ai.localization_stress import probe, replay_quality
from rocell_ai.scene_observation import canonical_hash
from run_keyboard_route_coverage import proposals


class LocalizationStressTests(unittest.TestCase):
    def setUp(self):
        self.rows=json.loads((AI_DIR/'eval/gemma3_4b_scene_stress_v0.json').read_text())['rows']
        catalog={p['target_id']:p for p in proposals(WORKSPACE)}
        self.sequence=[catalog['H'],catalog['I']]

    def test_all_five_adverse_conditions_skip_simulation(self):
        simulate=Mock(side_effect=AssertionError('Simulation must not run'))
        for row in self.rows[1:]:
            result=probe(row,self.sequence,workspace=WORKSPACE,dx=0,dy=0,simulate=simulate)
            self.assertEqual(result['status'],'ARCHIVED_QUALITY_REJECTED')
            self.assertFalse(result['route_run'])
        simulate.assert_not_called()

    def test_outside_target_and_low_confidence_stop_at_bridge(self):
        for dx,confidence in [(8,1.0),(0,0.5)]:
            result=probe(self.rows[0],self.sequence,workspace=WORKSPACE,dx=dx,dy=0,confidence=confidence)
            self.assertEqual(result['status'],'COORDINATE_BRIDGE_REJECTED')
            self.assertFalse(result['route_run'])

    def test_archived_evidence_tampering_and_cross_frame_pairing_fail(self):
        row=copy.deepcopy(self.rows[0]);row['pixel_quality']['accepted']=False
        with self.assertRaisesRegex(ValueError,'hash mismatch'):
            replay_quality(row)
        row=copy.deepcopy(self.rows[0]);pixel=row['pixel_quality'];pixel['frame_id']='different'
        pixel['assessment_sha256']=canonical_hash({k:v for k,v in pixel.items() if k!='assessment_sha256'})
        with self.assertRaisesRegex(ValueError,'frame binding mismatch'):
            replay_quality(row)


if __name__=='__main__':
    unittest.main()

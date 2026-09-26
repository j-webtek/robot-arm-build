"""Sequence order, repeated presses, and scope boundaries."""
import copy
from pathlib import Path
import sys
import unittest

AI_DIR = Path(__file__).resolve().parents[1]
WORKSPACE = AI_DIR.parents[1]
sys.path[:0] = [str(AI_DIR), str(AI_DIR.parent / 'src')]
from run_keyboard_route_coverage import proposals
from run_sequence_clearance_study import summarize
from rocell_ai.motion_sequence_simulation import run
from rocell_ai.scene_observation import canonical_hash


class MotionSequenceTests(unittest.TestCase):
    def setUp(self):
        self.proposal = next(p for p in proposals(WORKSPACE) if p['target_id'] == 'H')

    def test_repeated_presses_preserve_order_and_cadence_is_only_hypothetical(self):
        result = run([self.proposal, copy.deepcopy(self.proposal)], workspace=WORKSPACE)
        self.assertEqual(result['requested_targets'], ['H', 'H'])
        events = result['cadence_hypothesis']['contact_events']
        self.assertEqual([e['action_index'] for e in events], [0, 1])
        self.assertGreater(events[1]['planned_contact_time_s'], events[0]['planned_contact_time_s'])
        self.assertFalse(result['cadence_hypothesis']['dynamics_verified'])
        self.assertTrue(result['dense_route']['all_waypoints_accepted'])
        summary = summarize(result)
        self.assertEqual(summary['source_sequence_sha256'], result['sequence_sha256'])
        self.assertEqual(summary['dense_route_sha256'], canonical_hash(result['dense_route']))
        self.assertEqual(summary['cadence_hypothesis']['contact_events'], events)
        self.assertFalse(result['physical_execution_authorized'])
        self.assertEqual(result['hardware_writes'], 0)
        self.assertEqual(result['sequence_sha256'], canonical_hash({k:v for k,v in result.items() if k!='sequence_sha256'}))

    def test_empty_oversized_and_mixed_clearance_sequences_rejected(self):
        for values in ([], [self.proposal] * 9):
            with self.assertRaisesRegex(ValueError, 'one to eight'):
                run(values, workspace=WORKSPACE)
        changed = copy.deepcopy(self.proposal)
        changed['approach_clearance_mm'] = 12.0
        with self.assertRaisesRegex(ValueError, 'common study clearance'):
            run([self.proposal, changed], workspace=WORKSPACE)

    def test_repeated_target_cannot_silently_replace_earlier_coordinate(self):
        changed = copy.deepcopy(self.proposal)
        changed['target_mm']['x'] += 0.1
        with self.assertRaisesRegex(ValueError, 'coordinates must agree'):
            run([self.proposal, changed], workspace=WORKSPACE)


if __name__ == '__main__':
    unittest.main()

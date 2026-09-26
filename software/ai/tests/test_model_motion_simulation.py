"""Tests for zero-hardware model-coordinate trajectory rehearsal."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import unittest


AI_DIR = Path(__file__).resolve().parents[1]
WORKSPACE = AI_DIR.parents[1]
sys.path.insert(0, str(AI_DIR))
sys.path.insert(0, str(AI_DIR.parent / "src"))

from rocell_ai.model_motion_simulation import run, validate  # noqa: E402


class ModelMotionSimulationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.proposal = json.loads(
            (AI_DIR / "examples" / "model_motion_proposal_keyboard_h_contact.json").read_text(
                encoding="utf-8"
            )
        )

    def test_contact_proposal_is_rehearsed_and_remains_non_executable(self) -> None:
        report = run(self.proposal, workspace=WORKSPACE)
        self.assertEqual(report["simulation_status"], "SIMULATION_BLOCKED")
        self.assertTrue(report["geometry_all_checks_pass"])
        self.assertFalse(report["sampled_ik_all_converged"])
        self.assertEqual(report["first_failure"]["reason"], "IK_NO_CONVERGED_SOLUTION")
        self.assertFalse(report["physical_execution_authorized"])
        self.assertEqual(report["hardware_commands"], [])
        self.assertEqual(report["hardware_writes"], 0)
        self.assertIs(validate(report), report)

    def test_hover_proposal_is_outside_contact_rehearsal_scope(self) -> None:
        changed = copy.deepcopy(self.proposal)
        changed["interaction"] = "HOVER"
        with self.assertRaisesRegex(ValueError, "keyboard CONTACT only"):
            run(changed, workspace=WORKSPACE)

    def test_tampered_hash_bound_report_is_rejected(self) -> None:
        report = run(self.proposal, workspace=WORKSPACE)
        changed = copy.deepcopy(report)
        changed["simulation_target_overlay"]["center_board_mm"][0] += 1
        with self.assertRaisesRegex(ValueError, "overlay hash mismatch"):
            validate(changed)
        changed = copy.deepcopy(report)
        changed["physical_execution_authorized"] = True
        with self.assertRaisesRegex(ValueError, "cannot assert"):
            validate(changed)


if __name__ == "__main__":
    unittest.main()

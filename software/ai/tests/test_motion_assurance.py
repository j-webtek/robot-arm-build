"""Tests for model-coordinate translation assurance."""

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

from rocell_ai.motion_assurance import build, validate  # noqa: E402


class MotionAssuranceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.proposal = json.loads(
            (AI_DIR / "examples" / "model_motion_proposal_keyboard_h.json").read_text(encoding="utf-8")
        )

    def test_model_coordinate_reaches_calibration_block_with_zero_effects(self) -> None:
        bundle = build(self.proposal, workspace=WORKSPACE)
        stages = bundle["assurance"]["stages"]
        self.assertEqual([row["status"] for row in stages[:4]], ["passed", "passed", "passed", "blocked"])
        self.assertTrue(all(row["status"] == "not_run" for row in stages[4:]))
        self.assertEqual(bundle["candidate"]["controller_commands"], [])
        self.assertTrue(all(count == 0 for count in bundle["assurance"]["counts"].values()))

    def test_tampered_candidate_or_downstream_pass_is_rejected(self) -> None:
        bundle = build(self.proposal, workspace=WORKSPACE)
        changed = copy.deepcopy(bundle)
        changed["candidate"]["proposed_surface_target_board_mm"]["x"] += 1
        with self.assertRaisesRegex(ValueError, "candidate hash mismatch"):
            validate(changed)
        changed = copy.deepcopy(bundle)
        changed["assurance"]["stages"][4] = {
            "stage": "inverse_kinematics", "status": "passed",
            "artifact_sha256": "f" * 64, "reason": None,
        }
        with self.assertRaisesRegex(ValueError, "crossed its first blocker"):
            validate(changed)


if __name__ == "__main__":
    unittest.main()

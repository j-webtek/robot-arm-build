"""Joint intent/visual-coordinate simulation checks."""

from __future__ import annotations

from pathlib import Path
import copy
import hashlib
import json
import sys
import unittest


AI_DIR = Path(__file__).resolve().parents[1]
WORKSPACE = AI_DIR.parents[1]
sys.path.insert(0, str(AI_DIR))
sys.path.insert(0, str(AI_DIR.parent / "src"))

from rocell_ai.coordinate_preview import preview  # noqa: E402
from rocell_ai.visual_observation import simulate  # noqa: E402
from rocell_ai.visual_observation import MODEL_SCHEMA  # noqa: E402
from rocell.targets.nominal import load_nominal_target_catalog  # noqa: E402
from vision.synthetic_keyboard import render, transform_target  # noqa: E402


class VisualCoordinateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.observation = {"ref": "frame-1", "fresh": True, "phone_state": "UNKNOWN"}

    def test_visual_displacement_reaches_selected_targets(self) -> None:
        visual = simulate(WORKSPACE, device="keyboard", frame_id="frame-1", offset_x_mm=2, offset_y_mm=-3)
        result = preview('Type "hi" on the keyboard', self.observation, request_id="r1",
                         workspace=WORKSPACE, visual_observation=visual)
        self.assertEqual(result["status"], "coordinate_preview")
        self.assertFalse(result["execution_authorized"])
        self.assertEqual(result["controller_commands"], [])
        self.assertEqual([row["target_id"] for row in result["targets"]], ["H", "I"])
        for row in result["targets"]:
            self.assertAlmostEqual(row["center_board_mm"][0] - row["nominal_center_board_mm"][0], 2)
            self.assertAlmostEqual(row["center_board_mm"][1] - row["nominal_center_board_mm"][1], -3)

    def test_frame_device_and_hash_mismatch_fail(self) -> None:
        visual = simulate(WORKSPACE, device="keyboard", frame_id="frame-1")
        for changed in (
            {**visual, "frame_id": "other"},
            {**visual, "device": "phone"},
            {**visual, "observation_sha256": "0" * 64},
        ):
            with self.assertRaises(ValueError):
                preview('Type "hi" on the keyboard', self.observation, request_id="r2",
                        workspace=WORKSPACE, visual_observation=changed)

    def test_missing_target_and_large_shift_fail_even_with_valid_hash(self) -> None:
        visual = simulate(WORKSPACE, device="keyboard", frame_id="frame-1")
        for alteration in ("missing", "shifted"):
            changed = copy.deepcopy(visual)
            if alteration == "missing":
                del changed["targets"]["H"]
            else:
                changed["targets"]["H"]["center_board_mm"][0] += 40
            core = {key: value for key, value in changed.items() if key != "observation_sha256"}
            changed["observation_sha256"] = hashlib.sha256(
                json.dumps(core, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
            ).hexdigest()
            with self.assertRaises(ValueError):
                preview('Type "hi" on the keyboard', self.observation, request_id="r3",
                        workspace=WORKSPACE, visual_observation=changed)

    def test_stale_and_unknown_phone_state_remain_blocked(self) -> None:
        visual = simulate(WORKSPACE, device="phone", frame_id="frame-1")
        blocked = preview('Type "hi" on the phone', self.observation, request_id="r4",
                          workspace=WORKSPACE, visual_observation=visual)
        self.assertEqual(blocked["status"], "blocked")
        self.assertEqual(blocked["reason"], "phone_state_unverified")
        stale = preview('Type "hi" on the keyboard', {**self.observation, "fresh": False},
                        request_id="r5", workspace=WORKSPACE)
        self.assertEqual(stale["reason"], "stale_observation")

    def test_phone_visual_targets_preserve_state_verification(self) -> None:
        visual = simulate(WORKSPACE, device="phone", frame_id="frame-1", offset_y_mm=1)
        observation = {**self.observation, "phone_state": "KEYBOARD_LOWER"}
        result = preview('Type "a" on the phone', observation, request_id="r6",
                         workspace=WORKSPACE, visual_observation=visual)
        self.assertEqual(result["status"], "coordinate_preview")
        self.assertEqual(result["targets"][0]["action"], "verify_phone_state")
        self.assertIsNone(result["targets"][0]["center_board_mm"])
        self.assertEqual(result["targets"][1]["target_id"], "key_a")
        self.assertEqual(result["targets"][1]["center_board_mm"][1],
                         result["targets"][1]["nominal_center_board_mm"][1] + 1)

    def test_synthetic_pixels_and_pose_are_seed_reproducible(self) -> None:
        catalog = load_nominal_target_catalog(WORKSPACE)
        first_image, first_pose = render(123, catalog)
        second_image, second_pose = render(123, catalog)
        self.assertEqual(first_pose, second_pose)
        self.assertEqual(first_image.tobytes(), second_image.tobytes())

    def test_image_model_observation_binds_selected_key_coordinates(self) -> None:
        catalog = load_nominal_target_catalog(WORKSPACE)
        center, angle = (235.0, 154.0), 3.141592653589793
        targets = {}
        for target_id, region in catalog.keyboard_targets.items():
            x, y = transform_target(region.center.x, region.center.y, center, angle)
            targets[target_id] = {"center_board_mm": [x, y, region.center.z]}
        core = {
            "schema": MODEL_SCHEMA, "frame_id": "frame-1", "device": "keyboard",
            "coordinate_frame": "board", "coordinate_unit": "mm",
            "source": "SYNTHETIC_IMAGE_MODEL_PREDICTION",
            "target_catalog_sha256": catalog.content_sha256,
            "image_sha256": "a" * 64, "model_sha256": "b" * 64,
            "targets": targets,
        }
        visual = {**core, "observation_sha256": hashlib.sha256(
            json.dumps(core, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        ).hexdigest()}
        result = preview('Type "a" on the keyboard', self.observation, request_id="r7",
                         workspace=WORKSPACE, visual_observation=visual)
        self.assertEqual(result["status"], "coordinate_preview")
        self.assertEqual(result["coordinate_source"], "SYNTHETIC_IMAGE_MODEL_PREDICTION")
        self.assertEqual(result["image_sha256"], "a" * 64)
        self.assertNotEqual(result["targets"][0]["center_board_mm"],
                            result["targets"][0]["nominal_center_board_mm"])
        visual["model_sha256"] = "c" * 64
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            preview('Type "a" on the keyboard', self.observation, request_id="r7",
                    workspace=WORKSPACE, visual_observation=visual)


if __name__ == "__main__":
    unittest.main()

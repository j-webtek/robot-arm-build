"""Check hidden virtual key outcomes and model-pose overlay boundaries."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest
from unittest.mock import patch

AI_DIR = Path(__file__).resolve().parents[1]
ROOT = AI_DIR.parents[1]
sys.path.insert(0, str(AI_DIR))
sys.path.insert(0, str(AI_DIR.parent / "src"))

from rocell.application.keyboard_placement_overlay import synthetic_model_keyboard  # noqa: E402
from rocell.application.robot_layout_overlay import promoted_rank1_robot_layout  # noqa: E402
from rocell.application.static_simulation_context import load_static_simulation_context  # noqa: E402
from rocell.application.static_task_rehearsal import run_static_task_rehearsal  # noqa: E402
from vision.run_keyboard_rehearsal import evaluate_virtual_typing  # noqa: E402
from vision.run_keyboard_campaign import run as run_campaign  # noqa: E402
from vision.synthetic_keyboard import transform_target  # noqa: E402


class KeyboardRehearsalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.context = load_static_simulation_context(ROOT)

    def test_virtual_key_hit_wrong_key_and_empty_space(self) -> None:
        catalog = self.context.targets
        pose = (235.0, 154.0, 3.141592653589793)
        a = catalog.keyboard_targets["A"].center
        s = catalog.keyboard_targets["S"].center
        ax, ay = transform_target(a.x, a.y, pose[:2], pose[2])
        sx, sy = transform_target(s.x, s.y, pose[:2], pose[2])
        targets = [{"action": "press_key", "target_id": "A", "center_board_mm": [x, y, a.z]}
                   for x, y in ((ax, ay), (sx, sy), (0, 0))]
        result = evaluate_virtual_typing(targets, catalog, pose, "aaa")
        self.assertEqual([row["virtual_hit_key"] for row in result["events"]], ["A", "S", None])
        self.assertEqual(result["virtual_text_if_all_contacts_reached"], "as")
        self.assertFalse(result["all_intended_keys_hit"])

    def test_model_overlay_is_offline_and_changes_key_centers(self) -> None:
        context = self.context
        estimate = {"schema": "rocell.synthetic_model_keyboard_estimate.v1",
                    "source": "SYNTHETIC_IMAGE_MODEL_PREDICTION", "motion_authorized": False,
                    "target_catalog_sha256": context.targets.content_sha256,
                    "image_sha256": "a" * 64, "model_sha256": "b" * 64,
                    "center_board_xy_mm": [235.0, 154.0], "yaw_rad": 3.141592653589793}
        scene, targets, overlay = synthetic_model_keyboard(context.scene, context.targets, estimate)
        self.assertNotEqual(targets.keyboard_targets["A"].center,
                            context.targets.keyboard_targets["A"].center)
        self.assertFalse(overlay["motion_authorized"])
        self.assertEqual(scene.devices["keyboard"].envelope, scene.obstacles[
            next(i for i, box in enumerate(scene.obstacles) if box.obstacle_id == "keyboard")])
        with self.assertRaises(ValueError):
            synthetic_model_keyboard(context.scene, context.targets,
                                     {**estimate, "motion_authorized": True})
        with self.assertRaises(ValueError):
            synthetic_model_keyboard(context.scene, context.targets,
                                     {**estimate, "target_catalog_sha256": "0" * 64})

    def test_documented_layout_screens_multikey_model_route(self) -> None:
        context = self.context
        profile = ROOT / "software" / "config" / "virtual_commissioning_profile.json"
        scenario, layout = promoted_rank1_robot_layout(context, profile)
        self.assertEqual(layout["study_input_id"], "reach-944d7463f4c67905")
        self.assertEqual(scenario.hand_tcp_to_tip_z_mm, -120.0)
        self.assertFalse(layout["motion_authorized"])
        estimate = {"schema": "rocell.synthetic_model_keyboard_estimate.v1",
                    "source": "SYNTHETIC_IMAGE_MODEL_PREDICTION", "motion_authorized": False,
                    "target_catalog_sha256": context.targets.content_sha256,
                    "image_sha256": "a" * 64, "model_sha256": "b" * 64,
                    "center_board_xy_mm": [214.89658415317535, 158.46930480003357],
                    "yaw_rad": 3.306870778399058}
        report = run_static_task_rehearsal(
            context, device="keyboard", text="hi", dense=True,
            park_xy_board_mm=(290.0, 10.0), keyboard_model_estimate=estimate,
            robot_layout_profile=profile)
        self.assertEqual(report["status"], "DENSE_SAMPLES_PASS_NOT_EXECUTABLE")
        self.assertTrue(report["dense_route"]["all_waypoints_accepted"])
        self.assertEqual(report["task_summary"]["evaluated_waypoint_count"], 45)
        self.assertEqual(report["task_summary"]["requested_targets"], ["H", "I"])
        self.assertFalse(report["physical_authority"])

    def test_campaign_keeps_key_and_route_failures_separate(self) -> None:
        def fake_rehearsal(**kwargs):
            text = kwargs["request"].split('"')[1]
            passed = kwargs["seed"] == 1
            failure = None if passed else {"phase": "HOVER", "reason": "IK_NO_CONVERGED_SOLUTION"}
            return {
                "seed": kwargs["seed"], "synthetic_domain": kwargs["domain"],
                "requested_text": text, "status": (
                    "VIRTUAL_SUCCESS_ROUTE_SCREENED" if passed else "ROUTE_BLOCKED"),
                "image_sha256": str(kwargs["seed"]) * 64,
                "model_sha256": "c" * 64,
                "vision": {"truth_pose_board": [1, 2, 3], "predicted_pose_board": [1, 2, 3],
                           "center_error_mm": float(kwargs["seed"]), "yaw_error_deg": 0.1},
                "virtual_typing": {"events": [{"intended_key": text.upper(),
                                                  "virtual_hit_key": text.upper()}],
                                   "virtual_text_if_all_contacts_reached": text,
                                   "all_intended_keys_hit": True},
                "rocell_route": {"dense_route_all_waypoints_accepted": passed,
                                 "task_summary": {"first_failure": failure,
                                                  "evaluated_waypoint_count": 2,
                                                  "planned_waypoint_count": 3},
                                 "rehearsal_sha256": "d" * 64},
                "virtual_text_after_screened_route": text if passed else None,
            }
        cases = ((1, "a", "standard"), (2, "b", "appearance_shift"))
        with patch("vision.run_keyboard_campaign.run_rehearsal", side_effect=fake_rehearsal):
            report = run_campaign(Path("unused-checkpoint.pt"), cases)
        self.assertEqual(report["metrics"]["all_intended_keys_hit_rate"], 1.0)
        self.assertEqual(report["metrics"]["dense_route_pass_rate"], 0.5)
        self.assertEqual(report["metrics"]["end_to_end_success_rate"], 0.5)
        self.assertEqual(report["metrics"]["route_failure_reasons"],
                         {"IK_NO_CONVERGED_SOLUTION": 1})
        self.assertFalse(report["physical_execution_authorized"])


if __name__ == "__main__":
    unittest.main()

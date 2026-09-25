"""Fail-closed tests for multimodal observation and precision fusion."""

from __future__ import annotations

import copy
from io import BytesIO
import hashlib
import json
from pathlib import Path
import sys
import unittest

from PIL import Image, ImageDraw


AI_DIR = Path(__file__).resolve().parents[1]
WORKSPACE = AI_DIR.parents[1]
sys.path.insert(0, str(AI_DIR))
sys.path.insert(0, str(AI_DIR.parent / "src"))

from rocell.targets.nominal import load_nominal_target_catalog  # noqa: E402
from rocell_ai.multimodal_preview import guarded_preview  # noqa: E402
from rocell_ai.scene_observation import (  # noqa: E402
    FixtureVisionObserver, FrameEvidence, build_observation, canonical_hash, validate_observation,
)
from rocell_ai.vision_fusion import fuse  # noqa: E402
from rocell_ai.visual_observation import MODEL_SCHEMA  # noqa: E402


def good_output() -> dict:
    return {
        "device_presence": "keyboard",
        "keyboard_layout": "us_qwerty",
        "phone_state": "not_visible",
        "lighting": "acceptable",
        "blur": "none",
        "glare": "none",
        "occlusion_source": "none",
        "occlusion_fraction": 0.0,
        "critical_targets_visible": True,
        "confidence": 0.97,
    }


class VisionFusionTests(unittest.TestCase):
    def setUp(self) -> None:
        image = Image.new("RGB", (256, 192), (170, 160, 150))
        draw = ImageDraw.Draw(image)
        for y in range(20, 170, 20):
            for x in range(20, 235, 20):
                draw.rectangle((x, y, x + 12, y + 12), fill=(40 + x % 80, 50, 80))
        stream = BytesIO()
        image.save(stream, format="PNG")
        self.frame = FrameEvidence("frame-1", "2026-09-25T12:00:00Z", stream.getvalue())
        self.scene = FixtureVisionObserver(good_output()).observe(self.frame)
        catalog = load_nominal_target_catalog(WORKSPACE)
        self.catalog = catalog
        targets = {
            name: {"center_board_mm": [region.center.x, region.center.y, region.center.z]}
            for name, region in catalog.keyboard_targets.items()
        }
        core = {
            "schema": MODEL_SCHEMA,
            "frame_id": self.frame.frame_id,
            "device": "keyboard",
            "coordinate_frame": "board",
            "coordinate_unit": "mm",
            "source": "SYNTHETIC_IMAGE_MODEL_PREDICTION",
            "target_catalog_sha256": catalog.content_sha256,
            "image_sha256": self.frame.image_sha256,
            "model_sha256": "b" * 64,
            "targets": targets,
        }
        self.precision = {**core, "observation_sha256": hashlib.sha256(
            json.dumps(core, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        ).hexdigest()}

    def test_valid_same_frame_observations_accept_without_authorizing_execution(self) -> None:
        decision = fuse(
            frame=self.frame, scene_observation=self.scene, precision_observation=self.precision,
            device="keyboard", required_targets=["H", "I"],
            target_catalog_sha256=self.catalog.content_sha256,
            evaluated_at_utc="2026-09-25T12:00:01Z",
        )
        self.assertTrue(decision["accepted"])
        self.assertFalse(decision["execution_authorized"])
        self.assertEqual(decision["reasons"], [])

    def test_scene_hash_and_frame_binding_reject_tampering(self) -> None:
        changed = copy.deepcopy(self.scene)
        changed["confidence"] = 1.0
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            validate_observation(changed, frame=self.frame)
        other = FrameEvidence("frame-2", self.frame.captured_at_utc, self.frame.image_bytes)
        with self.assertRaisesRegex(ValueError, "supplied frame"):
            validate_observation(self.scene, frame=other)

    def test_rehashed_record_cannot_suppress_derived_abstention(self) -> None:
        scene = build_observation(
            frame=self.frame, runtime="fixture", model="dark", model_identity="dark-v1",
            model_output={**good_output(), "lighting": "dark"},
        )
        scene["abstain"] = False
        scene["abstain_reasons"] = []
        scene["observation_sha256"] = canonical_hash({
            key: value for key, value in scene.items() if key != "observation_sha256"
        })
        with self.assertRaisesRegex(ValueError, "do not match classifications"):
            validate_observation(scene, frame=self.frame)

    def test_precision_image_mismatch_is_a_fusion_rejection(self) -> None:
        changed = copy.deepcopy(self.precision)
        changed["image_sha256"] = "a" * 64
        core = {key: value for key, value in changed.items() if key != "observation_sha256"}
        changed["observation_sha256"] = hashlib.sha256(
            json.dumps(core, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        ).hexdigest()
        decision = fuse(
            frame=self.frame, scene_observation=self.scene, precision_observation=changed,
            device="keyboard", required_targets=["A"],
            target_catalog_sha256=self.catalog.content_sha256,
            evaluated_at_utc="2026-09-25T12:00:01Z",
        )
        self.assertFalse(decision["accepted"])
        self.assertIn("precision_image_mismatch", decision["reasons"])

    def test_adverse_scene_conditions_fail_closed(self) -> None:
        cases = (
            ({"lighting": "dark"}, "lighting_adverse"),
            ({"blur": "high"}, "blur_adverse"),
            ({"glare": "high"}, "glare_adverse"),
            ({"occlusion_source": "arm", "occlusion_fraction": 0.4}, "excessive_occlusion"),
            ({"critical_targets_visible": False}, "critical_targets_hidden"),
            ({"confidence": 0.4}, "low_scene_confidence"),
        )
        for changes, expected in cases:
            with self.subTest(expected=expected):
                scene = build_observation(
                    frame=self.frame, runtime="fixture", model="case", model_identity="case-v1",
                    model_output={**good_output(), **changes},
                )
                decision = fuse(
                    frame=self.frame, scene_observation=scene, precision_observation=self.precision,
                    device="keyboard", required_targets=["A"],
                    target_catalog_sha256=self.catalog.content_sha256,
                    evaluated_at_utc="2026-09-25T12:00:01Z",
                )
                self.assertFalse(decision["accepted"])
                self.assertIn(expected, decision["reasons"])

    def test_stale_and_missing_target_fail_closed(self) -> None:
        decision = fuse(
            frame=self.frame, scene_observation=self.scene, precision_observation=self.precision,
            device="keyboard", required_targets=["NOT_A_KEY"],
            target_catalog_sha256=self.catalog.content_sha256,
            evaluated_at_utc="2026-09-25T12:00:10Z",
        )
        self.assertEqual(decision["accepted"], False)
        self.assertIn("stale_frame", decision["reasons"])
        self.assertIn("missing_precision_target", decision["reasons"])

    def test_guarded_preview_only_exposes_coordinates_after_fusion(self) -> None:
        observation = {"ref": "frame-1", "fresh": True, "phone_state": "UNKNOWN"}
        accepted = guarded_preview(
            'Type "hi" on the keyboard', observation, request_id="r1", workspace=WORKSPACE,
            frame=self.frame, scene_observation=self.scene, precision_observation=self.precision,
            evaluated_at_utc="2026-09-25T12:00:01Z",
        )
        self.assertEqual(accepted["status"], "coordinate_preview")
        self.assertEqual([row["target_id"] for row in accepted["targets"]], ["H", "I"])
        self.assertFalse(accepted["execution_authorized"])
        blocked_scene = build_observation(
            frame=self.frame, runtime="fixture", model="blocked", model_identity="blocked-v1",
            model_output={**good_output(), "occlusion_source": "arm", "occlusion_fraction": 0.8,
                          "critical_targets_visible": False},
        )
        blocked = guarded_preview(
            'Type "hi" on the keyboard', observation, request_id="r2", workspace=WORKSPACE,
            frame=self.frame, scene_observation=blocked_scene, precision_observation=self.precision,
            evaluated_at_utc="2026-09-25T12:00:01Z",
        )
        self.assertEqual(blocked["status"], "blocked")
        self.assertEqual(blocked["targets"], [])
        self.assertIn("observer_abstained", blocked["fusion"]["reasons"])


if __name__ == "__main__":
    unittest.main()

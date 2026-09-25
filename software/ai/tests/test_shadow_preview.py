"""End-to-end tests for the zero-write multimodal shadow record."""

from __future__ import annotations

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
from rocell_ai.scene_observation import FixtureVisionObserver, FrameEvidence  # noqa: E402
from rocell_ai.shadow_preview import build, validate  # noqa: E402
from rocell_ai.visual_observation import MODEL_SCHEMA  # noqa: E402


class ShadowPreviewTests(unittest.TestCase):
    def test_record_binds_inputs_and_cannot_authorize_or_write(self) -> None:
        image = Image.new("RGB", (256, 192), (170, 160, 150))
        draw = ImageDraw.Draw(image)
        for y in range(20, 170, 20):
            for x in range(20, 235, 20):
                draw.rectangle((x, y, x + 12, y + 12), fill=(50, 60, 90))
        stream = BytesIO()
        image.save(stream, format="PNG")
        frame = FrameEvidence("shadow-frame", "2026-09-25T20:00:00Z", stream.getvalue())
        scene = FixtureVisionObserver({
            "device_presence": "keyboard", "keyboard_layout": "us_qwerty",
            "phone_state": "not_visible", "lighting": "acceptable", "blur": "none",
            "glare": "none", "occlusion_source": "none", "occlusion_fraction": 0,
            "critical_targets_visible": True, "confidence": 0.98,
        }).observe(frame)
        catalog = load_nominal_target_catalog(WORKSPACE)
        core = {
            "schema": MODEL_SCHEMA, "frame_id": frame.frame_id, "device": "keyboard",
            "coordinate_frame": "board", "coordinate_unit": "mm",
            "source": "SYNTHETIC_IMAGE_MODEL_PREDICTION",
            "target_catalog_sha256": catalog.content_sha256,
            "image_sha256": frame.image_sha256, "model_sha256": "a" * 64,
            "targets": {name: {"center_board_mm": [region.center.x, region.center.y, region.center.z]}
                        for name, region in catalog.keyboard_targets.items()},
        }
        precision = {**core, "observation_sha256": hashlib.sha256(
            json.dumps(core, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        ).hexdigest()}
        record = build(
            request='Type "hi" on the keyboard', request_id="shadow-1", workspace=WORKSPACE,
            frame=frame, scene_observation=scene, precision_observation=precision,
            evaluated_at_utc="2026-09-25T20:00:01Z",
        )
        self.assertEqual(record["result"]["status"], "coordinate_preview")
        self.assertEqual([item["target_id"] for item in record["result"]["targets"]], ["H", "I"])
        self.assertEqual(record["hardware_writes"], 0)
        self.assertFalse(record["execution_permit_created"])
        self.assertFalse(record["execution_authorized"])
        self.assertEqual(record["image_sha256"], frame.image_sha256)
        changed = dict(record)
        changed["hardware_writes"] = 1
        with self.assertRaisesRegex(ValueError, "cannot authorize"):
            validate(changed)

    def test_missing_precision_produces_hashed_blocked_record(self) -> None:
        image = Image.effect_noise((128, 96), 60).convert("RGB")
        stream = BytesIO()
        image.save(stream, format="PNG")
        frame = FrameEvidence("no-precision", "2026-09-25T20:00:00Z", stream.getvalue())
        scene = FixtureVisionObserver({
            "device_presence": "keyboard", "keyboard_layout": "us_qwerty",
            "phone_state": "not_visible", "lighting": "acceptable", "blur": "none",
            "glare": "none", "occlusion_source": "none", "occlusion_fraction": 0,
            "critical_targets_visible": True, "confidence": 0.98,
        }).observe(frame)
        record = build(
            request='Type "hi" on the keyboard', request_id="shadow-missing", workspace=WORKSPACE,
            frame=frame, scene_observation=scene, precision_observation=None,
            evaluated_at_utc="2026-09-25T20:00:01Z",
        )
        self.assertEqual(record["result"]["reason"], "precision_observation_missing")
        self.assertEqual(record["result"]["targets"], [])
        self.assertIsNone(record["precision_observation_sha256"])
        validate(record)


if __name__ == "__main__":
    unittest.main()

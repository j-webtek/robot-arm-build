"""Tests for the provenance-bound scene observer evaluation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest


AI_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_DIR))

from rocell_ai.scene_evaluation import evaluate_photo_seed  # noqa: E402
from rocell_ai.scene_observation import FixtureVisionObserver  # noqa: E402


class SceneEvaluationTests(unittest.TestCase):
    def test_evaluation_checks_sources_and_records_limitations(self) -> None:
        output = {
            "device_presence": "keyboard", "keyboard_layout": "us_qwerty",
            "phone_state": "not_visible", "lighting": "acceptable", "blur": "none",
            "glare": "none", "occlusion_source": "none", "occlusion_fraction": 0,
            "critical_targets_visible": True, "confidence": 0.9,
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = b"image-one"
            (root / "one.jpg").write_bytes(image)
            manifest = {
                "schema": "rocell.ai_real_photo_seed_manifest.v0", "capture_group": "fixture",
                "photos": [{"id": "one", "file": "one.jpg", "sha256": hashlib.sha256(image).hexdigest(),
                            "bytes": len(image), "width_px": 1, "height_px": 1}],
            }
            labels = {
                "schema": "rocell.ai_real_photo_seed_labels.v0", "manifest": "manifest.json",
                "human_reviewed": False, "coordinates_labeled": False,
                "rows": [{"id": "one", "view": "fixture", "visible": ["keyboard"], "use": "test"}],
            }
            (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            (root / "labels.json").write_text(json.dumps(labels), encoding="utf-8")
            result = evaluate_photo_seed(
                observer=FixtureVisionObserver(output), manifest_path=root / "manifest.json",
                labels_path=root / "labels.json", raw_directory=root,
                captured_at_utc="2026-09-25T16:00:00Z",
            )
            self.assertEqual(result["keyboard_detection_rate"], 1.0)
            self.assertEqual(result["abstention_count"], 0)
            self.assertFalse(result["deployment_camera_evaluation"])
            self.assertFalse(result["physical_execution_authorized"])

    def test_evaluation_rejects_changed_photo_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "one.jpg").write_bytes(b"changed")
            manifest = {"schema": "rocell.ai_real_photo_seed_manifest.v0", "capture_group": "fixture",
                        "photos": [{"id": "one", "file": "one.jpg", "sha256": "0" * 64,
                                    "bytes": 7, "width_px": 1, "height_px": 1}]}
            labels = {"schema": "rocell.ai_real_photo_seed_labels.v0", "manifest": "manifest.json",
                      "human_reviewed": False, "coordinates_labeled": False,
                      "rows": [{"id": "one", "view": "fixture", "visible": ["keyboard"], "use": "test"}]}
            (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            (root / "labels.json").write_text(json.dumps(labels), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "photo source mismatch"):
                evaluate_photo_seed(
                    observer=object(), manifest_path=root / "manifest.json",  # type: ignore[arg-type]
                    labels_path=root / "labels.json", raw_directory=root,
                )


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "software_helpers"))

import capture_camera_frames as capture  # noqa: E402


class FakeFrame:
    def __init__(self, width: int, height: int) -> None:
        self.shape = (height, width, 3)


class CaptureCameraFramesTests(unittest.TestCase):
    @staticmethod
    def valid_argv(output_dir: Path) -> list[str]:
        return [
            "--camera-index",
            "0",
            "--width",
            "1920",
            "--height",
            "1080",
            "--count",
            "20",
            "--prefix",
            "charuco",
            "--output-dir",
            str(output_dir),
        ]

    def test_valid_arguments_are_explicit_and_typed(self) -> None:
        args = capture.parse_args(
            self.valid_argv(Path("captures"))
            + ["--focus", "17.5", "--exposure", "-6", "--warmup-frames", "12"]
        )
        self.assertEqual(args.camera_index, 0)
        self.assertEqual((args.width, args.height, args.count), (1920, 1080, 20))
        self.assertEqual(args.prefix, "charuco")
        self.assertEqual(args.output_dir, Path("captures"))
        self.assertEqual((args.focus, args.exposure, args.warmup_frames), (17.5, -6.0, 12))

    def test_argument_validation_rejects_unsafe_or_nonsensical_values(self) -> None:
        cases = {
            "negative camera": ("--camera-index", "-1"),
            "zero width": ("--width", "0"),
            "negative height": ("--height", "-1"),
            "zero count": ("--count", "0"),
            "negative warmup": ("--warmup-frames", "-1"),
            "path prefix": ("--prefix", "../escape"),
            "reserved prefix": ("--prefix", "CON"),
            "nonfinite focus": ("--focus", "nan"),
            "nonfinite exposure": ("--exposure", "inf"),
        }
        with tempfile.TemporaryDirectory() as temporary:
            base = self.valid_argv(Path(temporary))
            for label, (option, invalid_value) in cases.items():
                argv = list(base)
                if option in argv:
                    argv[argv.index(option) + 1] = invalid_value
                else:
                    argv.extend([option, invalid_value])
                with self.subTest(label=label), contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit) as raised:
                        capture.parse_args(argv)
                    self.assertNotEqual(raised.exception.code, 0)

    def test_help_exits_before_loading_optional_vision_dependencies(self) -> None:
        with mock.patch.object(capture, "load_vision_dependencies") as loader:
            with contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    capture.main(["--help"])
        self.assertEqual(raised.exception.code, 0)
        loader.assert_not_called()

    def test_deterministic_capture_names_and_exact_resolution(self) -> None:
        self.assertEqual(capture.capture_filename("charuco", 1, 20), "charuco_001.png")
        self.assertEqual(capture.capture_filename("charuco", 20, 20), "charuco_020.png")
        self.assertEqual(capture.capture_filename("fov", 1000, 1000), "fov_1000.png")
        self.assertEqual(capture.require_resolution(FakeFrame(1920, 1080), 1920, 1080), (1920, 1080))
        with self.assertRaisesRegex(capture.CaptureError, "requested 1920x1080"):
            capture.require_resolution(FakeFrame(1280, 720), 1920, 1080)

    def test_output_preflight_and_writes_never_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary) / "session"
            manifest, paths = capture.prepare_output_directory(output_dir, "charuco", 2)
            self.assertEqual(manifest, output_dir / capture.MANIFEST_NAME)
            self.assertEqual([path.name for path in paths], ["charuco_001.png", "charuco_002.png"])
            capture.write_bytes_exclusive(paths[0], b"png payload")
            with self.assertRaises(FileExistsError):
                capture.write_bytes_exclusive(paths[0], b"replacement")
            self.assertEqual(paths[0].read_bytes(), b"png payload")
            with self.assertRaisesRegex(FileExistsError, "existing capture output"):
                capture.prepare_output_directory(output_dir, "charuco", 2)

        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary) / "session"
            output_dir.mkdir()
            manifest = output_dir / capture.MANIFEST_NAME
            capture.write_json_exclusive(manifest, {"status": "original"})
            with self.assertRaises(FileExistsError):
                capture.write_json_exclusive(manifest, {"status": "replacement"})
            self.assertEqual(json.loads(manifest.read_text(encoding="utf-8")), {"status": "original"})
            with self.assertRaisesRegex(FileExistsError, capture.MANIFEST_NAME):
                capture.prepare_output_directory(output_dir, "fov", 1)

    def test_output_preflight_allows_non_capture_support_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary)
            (output_dir / "README.md").write_text("capture guidance\n", encoding="utf-8")
            manifest, paths = capture.prepare_output_directory(output_dir, "fov", 1)
            self.assertFalse(manifest.exists())
            self.assertEqual(paths[0].name, "fov_001.png")

    def test_manifest_helpers_are_deterministic_and_complete(self) -> None:
        payload = b"deterministic PNG"
        record = capture.build_capture_record(
            sequence=1,
            filename="charuco_001.png",
            captured_at_utc="2026-08-31T12:00:01.000Z",
            width_px=1920,
            height_px=1080,
            laplacian_sharpness_score=123.5,
            sha256=capture.sha256_bytes(payload),
            size_bytes=len(payload),
        )
        arguments = {
            "completion_status": "COMPLETE",
            "started_at_utc": "2026-08-31T12:00:00.000Z",
            "finished_at_utc": "2026-08-31T12:00:02.000Z",
            "requested_camera_settings": {
                "camera_index": 0,
                "width_px": 1920,
                "height_px": 1080,
                "focus": None,
                "exposure": -6.0,
            },
            "actual_camera_settings": {
                "camera_index": 0,
                "width_px": 1920,
                "height_px": 1080,
                "focus": 18.0,
                "exposure": -6.0,
            },
            "requested_count": 1,
            "prefix": "charuco",
            "output_directory": "captures/charuco",
            "warmup_frames": 30,
            "captures": [record],
            "software_versions": {"python": "3.x", "opencv": "4.x", "numpy": "2.x"},
        }
        first = capture.build_session_manifest(**arguments)
        second = capture.build_session_manifest(**arguments)
        self.assertEqual(first, second)
        self.assertEqual(first["completion_status"], "COMPLETE")
        self.assertEqual(first["camera_settings"]["requested"]["width_px"], 1920)
        self.assertEqual(first["camera_settings"]["actual"]["height_px"], 1080)
        self.assertEqual(first["captures"][0]["laplacian_sharpness_score"], 123.5)
        self.assertEqual(first["captures"][0]["sha256"], capture.sha256_bytes(payload))
        self.assertEqual(first["software_versions"]["numpy"], "2.x")
        json.dumps(first, allow_nan=False)

        with self.assertRaisesRegex(ValueError, "every requested capture"):
            capture.build_session_manifest(**{**arguments, "requested_count": 2})


if __name__ == "__main__":
    unittest.main()

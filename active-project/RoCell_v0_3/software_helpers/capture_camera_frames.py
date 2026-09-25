#!/usr/bin/env python3
"""Interactively capture traceable Step-13 camera frames without overwriting files.

Example:
  python software_helpers/capture_camera_frames.py \
      --camera-index 0 --width 1920 --height 1080 --count 20 \
      --prefix charuco \
      --output-dir "BUILD_BY_STEP/13 - Mount and Calibrate Camera/06 - SAVE MEASUREMENTS AND PHOTOS/BUILD_ID/photos/charuco"

Press SPACE to save the displayed frame. Press Q or Escape to end the session.
OpenCV and NumPy are loaded only after command-line parsing, so ``--help`` and
the camera-free helper tests do not require the optional vision environment.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


MANIFEST_NAME = "capture_session.json"
WINDOW_NAME = "RoCell Step 13 Camera Capture"
DEFAULT_WARMUP_FRAMES = 30
VALID_COMPLETION_STATUSES = {"COMPLETE", "STOPPED_BY_OPERATOR", "ERROR"}
PREFIX_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


class CaptureError(RuntimeError):
    """A runtime capture failure that should be recorded in the manifest."""


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def nonnegative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be a non-negative integer")
    return parsed


def finite_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise argparse.ArgumentTypeError("must be a finite number")
    return parsed


def portable_prefix(value: str) -> str:
    if not PREFIX_PATTERN.fullmatch(value):
        raise argparse.ArgumentTypeError(
            "must be 1-64 characters, start with a letter or number, and use only "
            "letters, numbers, underscores, or hyphens"
        )
    if value.upper() in WINDOWS_RESERVED_NAMES:
        raise argparse.ArgumentTypeError("is a reserved Windows file name")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Capture repeatable Step-13 PNG frames with exact-resolution checks, "
            "sharpness scores, hashes, and a non-overwriting session manifest."
        )
    )
    parser.add_argument("--camera-index", required=True, type=nonnegative_int)
    parser.add_argument("--width", required=True, type=positive_int, help="Required frame width in pixels")
    parser.add_argument("--height", required=True, type=positive_int, help="Required frame height in pixels")
    parser.add_argument("--count", required=True, type=positive_int, help="Number of frames to save")
    parser.add_argument("--prefix", required=True, type=portable_prefix, help="Portable PNG filename prefix")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--focus", type=finite_float, default=None, help="Optional manual focus request")
    parser.add_argument("--exposure", type=finite_float, default=None, help="Optional exposure request")
    parser.add_argument(
        "--warmup-frames",
        type=nonnegative_int,
        default=DEFAULT_WARMUP_FRAMES,
        help=f"Frames to discard before capture (default: {DEFAULT_WARMUP_FRAMES})",
    )
    return parser


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    return build_parser().parse_args(argv)


def load_vision_dependencies() -> tuple[Any, Any]:
    """Import optional binary vision packages only when capture actually runs."""
    try:
        import cv2
        import numpy
    except Exception as exc:
        raise SystemExit(
            "OpenCV is unavailable or binary-incompatible with NumPy. Create an "
            "isolated environment and install requirements-vision.txt before capture. "
            f"Original error: {exc}"
        ) from None
    return cv2, numpy


def capture_filename(prefix: str, sequence: int, count: int) -> str:
    """Return the deterministic one-based name for a planned capture."""
    portable_prefix(prefix)
    if count <= 0:
        raise ValueError("count must be positive")
    if sequence <= 0 or sequence > count:
        raise ValueError(f"sequence must be between 1 and {count}")
    digits = max(3, len(str(count)))
    return f"{prefix}_{sequence:0{digits}d}.png"


def planned_capture_paths(output_dir: Path, prefix: str, count: int) -> tuple[Path, ...]:
    return tuple(output_dir / capture_filename(prefix, index, count) for index in range(1, count + 1))


def _path_exists(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def existing_output_conflicts(output_dir: Path) -> tuple[Path, ...]:
    """Return existing session outputs that make a new capture ambiguous."""
    if not _path_exists(output_dir):
        return ()
    if not output_dir.is_dir():
        return (output_dir,)
    conflicts: list[Path] = []
    manifest = output_dir / MANIFEST_NAME
    if _path_exists(manifest):
        conflicts.append(manifest)
    conflicts.extend(
        child
        for child in output_dir.iterdir()
        if child.suffix.lower() == ".png" and _path_exists(child)
    )
    return tuple(sorted(set(conflicts), key=lambda item: item.name.lower()))


def prepare_output_directory(output_dir: Path, prefix: str, count: int) -> tuple[Path, tuple[Path, ...]]:
    """Create an output directory only when it contains no prior capture outputs."""
    portable_prefix(prefix)
    if count <= 0:
        raise ValueError("count must be positive")
    if _path_exists(output_dir) and not output_dir.is_dir():
        raise FileExistsError(f"Output path is not a directory: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    conflicts = existing_output_conflicts(output_dir)
    if conflicts:
        names = ", ".join(path.name for path in conflicts)
        raise FileExistsError(
            f"Refusing to mix with or overwrite existing capture output in {output_dir}: {names}"
        )
    manifest_path = output_dir / MANIFEST_NAME
    paths = planned_capture_paths(output_dir, prefix, count)
    if len(set(paths)) != count:
        raise ValueError("Capture plan produced duplicate filenames")
    return manifest_path, paths


def write_bytes_exclusive(path: Path, payload: bytes) -> None:
    """Write a new file and remove a partial file if this write itself fails."""
    created = False
    try:
        with path.open("xb") as handle:
            created = True
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        if created:
            path.unlink(missing_ok=True)
        raise


def write_json_exclusive(path: Path, document: Mapping[str, Any]) -> None:
    payload = (json.dumps(document, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    write_bytes_exclusive(path, payload)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def frame_dimensions(frame: Any) -> tuple[int, int]:
    shape = getattr(frame, "shape", None)
    if not isinstance(shape, tuple) or len(shape) < 2:
        raise CaptureError("Camera returned a frame without valid dimensions")
    return int(shape[1]), int(shape[0])


def require_resolution(frame: Any, requested_width: int, requested_height: int) -> tuple[int, int]:
    actual_width, actual_height = frame_dimensions(frame)
    if (actual_width, actual_height) != (requested_width, requested_height):
        raise CaptureError(
            "Runtime frame resolution does not match the request: "
            f"requested {requested_width}x{requested_height}, received {actual_width}x{actual_height}"
        )
    return actual_width, actual_height


def json_safe_number(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def build_capture_record(
    *,
    sequence: int,
    filename: str,
    captured_at_utc: str,
    width_px: int,
    height_px: int,
    laplacian_sharpness_score: float,
    sha256: str,
    size_bytes: int,
) -> dict[str, Any]:
    if sequence <= 0:
        raise ValueError("sequence must be positive")
    if width_px <= 0 or height_px <= 0 or size_bytes <= 0:
        raise ValueError("dimensions and size_bytes must be positive")
    if not math.isfinite(laplacian_sharpness_score) or laplacian_sharpness_score < 0:
        raise ValueError("laplacian_sharpness_score must be finite and non-negative")
    if not re.fullmatch(r"[0-9a-f]{64}", sha256):
        raise ValueError("sha256 must be a lowercase 64-character digest")
    return {
        "sequence": sequence,
        "filename": filename,
        "captured_at_utc": captured_at_utc,
        "width_px": width_px,
        "height_px": height_px,
        "laplacian_sharpness_score": laplacian_sharpness_score,
        "size_bytes": size_bytes,
        "sha256": sha256,
    }


def build_session_manifest(
    *,
    completion_status: str,
    started_at_utc: str,
    finished_at_utc: str,
    requested_camera_settings: Mapping[str, Any],
    actual_camera_settings: Mapping[str, Any],
    requested_count: int,
    prefix: str,
    output_directory: str,
    warmup_frames: int,
    captures: Sequence[Mapping[str, Any]],
    software_versions: Mapping[str, str],
    error: str | None = None,
) -> dict[str, Any]:
    if completion_status not in VALID_COMPLETION_STATUSES:
        raise ValueError(f"Unknown completion status: {completion_status}")
    if requested_count <= 0:
        raise ValueError("requested_count must be positive")
    portable_prefix(prefix)
    capture_rows = [dict(row) for row in captures]
    if completion_status == "COMPLETE" and len(capture_rows) != requested_count:
        raise ValueError("A COMPLETE manifest must contain every requested capture")
    return {
        "schema_version": 1,
        "tool": "capture_camera_frames.py",
        "completion_status": completion_status,
        "timestamps": {
            "started_at_utc": started_at_utc,
            "finished_at_utc": finished_at_utc,
        },
        "capture_request": {
            "count": requested_count,
            "prefix": prefix,
            "output_directory": output_directory,
            "warmup_frames": warmup_frames,
        },
        "camera_settings": {
            "requested": dict(requested_camera_settings),
            "actual": dict(actual_camera_settings),
        },
        "captured_count": len(capture_rows),
        "captures": capture_rows,
        "software_versions": dict(software_versions),
        "error": error,
    }


def _camera_property(capture: Any, cv2_module: Any, name: str) -> float | None:
    property_id = getattr(cv2_module, name, None)
    if property_id is None:
        return None
    return json_safe_number(capture.get(property_id))


def _set_camera_property(capture: Any, cv2_module: Any, name: str, value: float) -> bool | None:
    property_id = getattr(cv2_module, name, None)
    if property_id is None:
        return None
    return bool(capture.set(property_id, value))


def _camera_backend_name(capture: Any) -> str | None:
    getter = getattr(capture, "getBackendName", None)
    if getter is None:
        return None
    try:
        return str(getter())
    except Exception:
        return None


def _read_frame(capture: Any) -> Any:
    ok, frame = capture.read()
    if not ok or frame is None:
        raise CaptureError("Camera frame read failed")
    return frame


def _encode_png(cv2_module: Any, frame: Any) -> bytes:
    ok, encoded = cv2_module.imencode(".png", frame)
    if not ok:
        raise CaptureError("OpenCV could not encode the frame as PNG")
    return bytes(encoded)


def _sharpness_score(cv2_module: Any, frame: Any) -> float:
    gray = cv2_module.cvtColor(frame, cv2_module.COLOR_BGR2GRAY)
    score = float(cv2_module.Laplacian(gray, cv2_module.CV_64F).var())
    if not math.isfinite(score) or score < 0:
        raise CaptureError("OpenCV returned an invalid Laplacian sharpness score")
    return score


def _display_frame(cv2_module: Any, frame: Any, saved: int, requested: int) -> None:
    preview = frame.copy()
    message = f"SPACE save ({saved}/{requested})   Q or Esc stop"
    cv2_module.putText(
        preview,
        message,
        (20, 35),
        cv2_module.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 255, 0),
        2,
        cv2_module.LINE_AA,
    )
    cv2_module.imshow(WINDOW_NAME, preview)


def run_capture(args: argparse.Namespace, cv2_module: Any, numpy_module: Any) -> int:
    manifest_path, capture_paths = prepare_output_directory(args.output_dir, args.prefix, args.count)
    started_at = utc_timestamp()
    captures: list[dict[str, Any]] = []
    actual_settings: dict[str, Any] = {}
    completion_status = "ERROR"
    error_message: str | None = None
    capture = None
    window_created = False

    requested_settings = {
        "camera_index": args.camera_index,
        "width_px": args.width,
        "height_px": args.height,
        "focus": args.focus,
        "exposure": args.exposure,
    }
    versions = {
        "python": platform.python_version(),
        "opencv": str(getattr(cv2_module, "__version__", "unknown")),
        "numpy": str(getattr(numpy_module, "__version__", "unknown")),
    }

    try:
        capture = cv2_module.VideoCapture(args.camera_index)
        if not capture.isOpened():
            raise CaptureError(f"Could not open camera index {args.camera_index}")

        setting_acceptance = {
            "width": _set_camera_property(capture, cv2_module, "CAP_PROP_FRAME_WIDTH", args.width),
            "height": _set_camera_property(capture, cv2_module, "CAP_PROP_FRAME_HEIGHT", args.height),
            "focus": None,
            "exposure": None,
        }
        if args.focus is not None:
            _set_camera_property(capture, cv2_module, "CAP_PROP_AUTOFOCUS", 0.0)
            setting_acceptance["focus"] = _set_camera_property(
                capture, cv2_module, "CAP_PROP_FOCUS", args.focus
            )
        if args.exposure is not None:
            setting_acceptance["exposure"] = _set_camera_property(
                capture, cv2_module, "CAP_PROP_EXPOSURE", args.exposure
            )

        for _ in range(args.warmup_frames):
            _read_frame(capture)
        frame = _read_frame(capture)
        actual_width, actual_height = frame_dimensions(frame)
        actual_settings = {
            "camera_index": args.camera_index,
            "width_px": actual_width,
            "height_px": actual_height,
            "driver_reported_width_px": _camera_property(capture, cv2_module, "CAP_PROP_FRAME_WIDTH"),
            "driver_reported_height_px": _camera_property(capture, cv2_module, "CAP_PROP_FRAME_HEIGHT"),
            "focus": _camera_property(capture, cv2_module, "CAP_PROP_FOCUS"),
            "exposure": _camera_property(capture, cv2_module, "CAP_PROP_EXPOSURE"),
            "fps": _camera_property(capture, cv2_module, "CAP_PROP_FPS"),
            "backend": _camera_backend_name(capture),
            "set_request_accepted_by_driver": setting_acceptance,
        }
        require_resolution(frame, args.width, args.height)

        cv2_module.namedWindow(WINDOW_NAME, cv2_module.WINDOW_NORMAL)
        window_created = True
        while True:
            require_resolution(frame, args.width, args.height)
            _display_frame(cv2_module, frame, len(captures), args.count)
            key = cv2_module.waitKey(10) & 0xFF
            if key in (ord("q"), ord("Q"), 27):
                completion_status = "STOPPED_BY_OPERATOR"
                break
            if key == ord(" "):
                sequence = len(captures) + 1
                target = capture_paths[sequence - 1]
                captured_at = utc_timestamp()
                sharpness = _sharpness_score(cv2_module, frame)
                png_bytes = _encode_png(cv2_module, frame)
                write_bytes_exclusive(target, png_bytes)
                width_px, height_px = frame_dimensions(frame)
                captures.append(
                    build_capture_record(
                        sequence=sequence,
                        filename=target.name,
                        captured_at_utc=captured_at,
                        width_px=width_px,
                        height_px=height_px,
                        laplacian_sharpness_score=sharpness,
                        sha256=sha256_bytes(png_bytes),
                        size_bytes=len(png_bytes),
                    )
                )
                print(f"Saved {target.name} ({sequence}/{args.count}), sharpness={sharpness:.3f}")
                if sequence == args.count:
                    completion_status = "COMPLETE"
                    break

            visible_property = getattr(cv2_module, "WND_PROP_VISIBLE", None)
            if visible_property is not None:
                try:
                    if cv2_module.getWindowProperty(WINDOW_NAME, visible_property) < 1:
                        completion_status = "STOPPED_BY_OPERATOR"
                        break
                except Exception:
                    pass
            frame = _read_frame(capture)
    except KeyboardInterrupt:
        completion_status = "STOPPED_BY_OPERATOR"
    except Exception as exc:
        completion_status = "ERROR"
        error_message = f"{type(exc).__name__}: {exc}"
    finally:
        if capture is not None:
            try:
                capture.release()
            except Exception:
                pass
        if window_created:
            try:
                cv2_module.destroyWindow(WINDOW_NAME)
            except Exception:
                pass

    manifest = build_session_manifest(
        completion_status=completion_status,
        started_at_utc=started_at,
        finished_at_utc=utc_timestamp(),
        requested_camera_settings=requested_settings,
        actual_camera_settings=actual_settings,
        requested_count=args.count,
        prefix=args.prefix,
        output_directory=str(args.output_dir.resolve()),
        warmup_frames=args.warmup_frames,
        captures=captures,
        software_versions=versions,
        error=error_message,
    )
    write_json_exclusive(manifest_path, manifest)
    print(f"Session manifest: {manifest_path}")
    print(f"Completion status: {completion_status}; captured {len(captures)}/{args.count}")
    if error_message is not None:
        raise SystemExit(f"Capture failed: {error_message}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    cv2_module, numpy_module = load_vision_dependencies()
    return run_capture(args, cv2_module, numpy_module)


if __name__ == "__main__":
    raise SystemExit(main())

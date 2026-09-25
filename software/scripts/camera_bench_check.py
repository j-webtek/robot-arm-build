"""Explicit, camera-only received-unit bench tests; no commissioning authority.

Uses an existing FFmpeg install and the exact observed DirectShow symbolic path.
Every child has a wall timeout. Files go to a NEW workspace export subdirectory.
No arm API, control write, driver install, firmware update or wizard gate change.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import time


NAME = "Arducam B0477 (USB3 20MP)"
ROOT = Path(__file__).resolve().parents[2]
EXPORTS = ROOT / "software/runs/wizard-exports"


def assess_sample_visibility(path: Path) -> dict:
    """Offline gross-exposure screen; a non-dark image is NOT calibrated vision.

    Use the whole-frame histogram so isolated hot pixels cannot hide an almost
    black capture. Thresholds are screening heuristics, not target-detection or
    optical qualification criteria. No device controls are read or changed here.
    """
    from PIL import Image

    with Image.open(path) as image:
        width, height = image.size
        if width * height > 30_000_000 or width * height < 1:
            raise ValueError("Sample dimensions exceed bench assessment bounds")
        histogram = image.convert("L").histogram()
    pixels = width * height
    mean = sum(level * count for level, count in enumerate(histogram)) / pixels
    dark = sum(histogram[:9]) / pixels
    bright = sum(histogram[247:]) / pixels
    status = ("NEAR_BLACK" if dark >= .99 else
              "NEAR_WHITE" if bright >= .99 else "SCENE_REVIEW_REQUIRED")
    return dict(schema="rocell.bench_sample_visibility.v1", sample=path.name,
        width=width, height=height, mean_luma_8bit=mean,
        fraction_luma_le_8=dark, fraction_luma_ge_247=bright, status=status,
        thresholds=dict(dark_max=8, bright_min=247, fraction=.99),
        arm_visible_verified=False, calibration_verified=False,
        physical_authority=False)


def write_json(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def run_child(folder: Path, label: str, argv: list[str], timeout: int = 30) -> dict:
    """Own only this child; capture logs even on errors and timeouts."""
    started = time.monotonic()
    timed_out = False
    with (folder / f"{label}.stdout.log").open("xb") as stdout, (
        folder / f"{label}.stderr.log"
    ).open("xb") as stderr:
        child = subprocess.Popen(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        try:
            try:
                child.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                child.kill()
                child.wait(timeout=10)
        finally:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=10)
    result = dict(
        label=label,
        argv=argv,
        exit_code=child.returncode,
        timed_out=timed_out,
        wall_seconds=time.monotonic() - started,
    )
    stderr_text = (folder / f"{label}.stderr.log").read_text(errors="replace")
    result["reported_frame_drop_warnings"] = stderr_text.lower().count("frame dropped!")
    write_json(folder / f"{label}.command.json", result)
    print(
        json.dumps(
            {k: result[k] for k in ("label", "exit_code", "timed_out", "wall_seconds")}
        ),
        flush=True,
    )
    return result


def exact_inventory(folder: Path, ffmpeg: str, alias: str, label: str) -> dict:
    result = run_child(
        folder,
        label,
        [ffmpeg, "-hide_banner", "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
        15,
    )
    text = (folder / f"{label}.stderr.log").read_text(errors="replace")
    # Listing intentionally exits without input; its exit code is not a stream failure.
    if (
        result["timed_out"]
        or text.count(f'"{NAME}" (video)') != 1
        or f'Alternative name "{alias}"' not in text
    ):
        raise RuntimeError(
            "Exact B0477 name/path is missing or ambiguous; no capture attempted."
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device-alias", required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--confirm-camera-only-tests", action="store_true")
    parser.add_argument("--full-resolution-seconds", type=int, default=5)
    parser.add_argument("--sample-warmup-seconds", type=int, default=0,
                        help="Optional 0–5 seconds of nominal frames before each sample; no control writes.")
    parser.add_argument(
        "--samples-only",
        action="store_true",
        help="Inventory, read controls and capture samples; skip throughput/catalog tests.",
    )
    args = parser.parse_args()
    if not args.confirm_camera_only_tests:
        parser.error("Explicit camera-only test confirmation required.")
    if not 5 <= args.full_resolution_seconds <= 60:
        parser.error("Full-resolution observation must be between 5 and 60 seconds.")
    if not 0 <= args.sample_warmup_seconds <= 5:
        parser.error("Sample warm-up must be between 0 and 5 seconds.")
    alias = args.device_alias
    if not alias.lower().startswith(
        "@device_pnp_\\\\?\\usb#vid_04b4&pid_0477&mi_00#"
    ) or any(c in alias for c in '\r\n"'):
        parser.error("Use the exact observed B0477 DirectShow alias.")
    folder = args.output_directory.resolve()
    if folder.parent != EXPORTS.resolve() or folder.exists():
        parser.error(
            "Output must be a new direct child of the workspace export folder."
        )
    ffmpeg = shutil.which("ffmpeg")
    powershell = shutil.which("pwsh")
    if not ffmpeg or not powershell:
        parser.error(
            "Existing FFmpeg and PowerShell are required; nothing is installed."
        )
    folder.mkdir()
    report = dict(
        schema="rocell.camera_bench_observation.v1",
        started_utc=datetime.now(timezone.utc).isoformat(),
        camera=NAME,
        device_alias=alias,
        observations=[],
        status="INCOMPLETE",
        arm_access=False,
        control_set_calls=0,
        driver_or_firmware_updates=False,
        camera_streams_explicitly_requested=True,
        calibration_or_stage_pass=False,
        usb_operating_speed="NOT_INDEPENDENTLY_MEASURED",
        reconnect_test="NOT_PERFORMED",
        test_scope="DIRECTSHOW_RECEIVED_CAMERA_BENCH_ONLY_NOT_WIZARD_COMMISSIONING",
        samples_only=args.samples_only,
        sample_warmup_seconds=args.sample_warmup_seconds,
    )
    report["bench_utility_sha256"] = {
        name: hashlib.sha256((Path(__file__).parent / name).read_bytes()).hexdigest()
        for name in (
            "camera_bench_check.py",
            "CameraBenchControls.cs",
            "read_camera_bench_controls.ps1",
        )
    }
    try:
        report["observations"].append(
            exact_inventory(folder, ffmpeg, alias, "inventory-before")
        )
        options = run_child(
            folder,
            "reported-modes",
            [
                ffmpeg,
                "-hide_banner",
                "-list_options",
                "true",
                "-f",
                "dshow",
                "-i",
                f"video={alias}",
            ],
        )
        report["observations"].append(options)
        text = (folder / "reported-modes.stderr.log").read_text(errors="replace")
        modes = sorted(
            set(
                re.findall(
                    r"pixel_format=(\w+)\s+min s=(\d+x\d+) fps=([\d.]+) max s=(\d+x\d+) fps=([\d.]+)",
                    text,
                )
            )
        )
        report["advertised_modes"] = [
            dict(
                pixel_format=p,
                minimum_size=lo,
                minimum_fps=float(lf),
                maximum_size=hi,
                maximum_fps=float(hf),
            )
            for p, lo, lf, hi, hf in modes
        ]
        if options["timed_out"] or not modes:
            raise RuntimeError(
                "No trustworthy reported mode list; stop before capture."
            )
        device_path = alias.removeprefix("@device_pnp_")
        controls = [
            powershell,
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(ROOT / "software/scripts/read_camera_bench_controls.ps1"),
            "-DevicePath",
            device_path,
        ]
        report["observations"].append(run_child(folder, "controls-before", controls))
        # All ordinary tests must fit the just-observed mode limits. 9 fps at
        # full resolution is a separate, explicit catalog-compatibility check.
        cases = [
            (1280, 720, 120),
            (1920, 1080, 60),
            (2720, 1536, 30),
            (3840, 2160, 20),
            (5472, 3648, 8),
        ]
        for width, height, fps in ([] if args.samples_only else cases):
            size = f"{width}x{height}"
            seconds = args.full_resolution_seconds if width == 5472 else 5
            available = any(
                m["pixel_format"] == "yuyv422"
                and m["minimum_size"] == m["maximum_size"] == size
                and m["minimum_fps"] <= fps <= m["maximum_fps"]
                for m in report["advertised_modes"]
            )
            if not available:
                report["observations"].append(
                    dict(label=f"stream-{size}-{fps}", status="SKIPPED_NOT_ADVERTISED")
                )
                continue
            label = f"stream-{size}-{fps}"
            # Copy packets into the null muxer: no encoder throughput is being benchmarked.
            argv = [
                ffmpeg,
                "-hide_banner",
                "-nostdin",
                "-nostats",
                "-progress",
                "pipe:1",
                "-rtbufsize",
                "256M",
                "-f",
                "dshow",
                "-pixel_format",
                "yuyv422",
                "-video_size",
                size,
                "-framerate",
                str(fps),
                "-i",
                f"video={alias}",
                "-map",
                "0:v:0",
                "-an",
                "-frames:v",
                str(fps * seconds),
                "-c:v",
                "copy",
                "-f",
                "null",
                "NUL",
            ]
            observed = run_child(folder, label, argv, timeout=seconds + 20)
            observed.update(
                requested_width=width,
                requested_height=height,
                requested_fps=fps,
                requested_frames=fps * seconds,
                requested_duration_seconds=seconds,
            )
            progress = (folder / f"{label}.stdout.log").read_text(errors="replace")
            frames = re.findall(r"^frame=(\d+)$", progress, re.MULTILINE)
            observed["output_frames"] = int(frames[-1]) if frames else None
            rates = re.findall(r"^fps=([\d.]+)$", progress, re.MULTILINE)
            observed["ffmpeg_reported_fps"] = float(rates[-1]) if rates else None
            observed["completed_requested_frames"] = (
                not observed["timed_out"]
                and observed["exit_code"] == 0
                and observed["output_frames"] == fps * seconds
            )
            report["observations"].append(observed)
        # Capture after at least five frames. An explicit longer warm-up tests
        # auto-exposure settling without changing electronic controls. Frame
        # counts represent nominal time only; the child still has a wall timeout.
        # PNG conversion happens in a separate OFFLINE process. Encoding a
        # 20MP PNG while still streaming can otherwise fill the capture queue.
        # These local originals are bench samples, NOT wizard/calibration evidence.
        for width, height, fps in [(1920, 1080, 30), (5472, 3648, 8)]:
            size = f"{width}x{height}"
            label = f"sample-{size}"
            raw_path = folder / f"{label}.yuy2"
            capture = run_child(
                folder,
                f"{label}-capture",
                [
                    ffmpeg,
                    "-hide_banner",
                    "-nostdin",
                    "-nostats",
                    "-n",
                    "-rtbufsize",
                    "256M",
                    "-f",
                    "dshow",
                    "-pixel_format",
                    "yuyv422",
                    "-video_size",
                    size,
                    "-framerate",
                    str(fps),
                    "-i",
                    f"video={alias}",
                    "-an",
                    "-vf",
                    rf"select=gte(n\,{max(5, fps * args.sample_warmup_seconds)})",
                    "-fps_mode",
                    "passthrough",
                    "-frames:v",
                    "1",
                    "-threads:v",
                    "1",
                    "-c:v",
                    "rawvideo",
                    "-pix_fmt",
                    "yuyv422",
                    "-f",
                    "rawvideo",
                    str(raw_path),
                ],
            )
            capture["expected_raw_bytes"] = width * height * 2
            capture["actual_raw_bytes"] = (
                raw_path.stat().st_size if raw_path.is_file() else None
            )
            capture["exact_frame_bytes"] = (
                capture["actual_raw_bytes"] == capture["expected_raw_bytes"]
            )
            report["observations"].append(capture)
            if (
                capture["timed_out"]
                or capture["exit_code"] != 0
                or not capture["exact_frame_bytes"]
            ):
                continue
            report["observations"].append(
                run_child(
                    folder,
                    f"{label}-encode-offline",
                    [
                        ffmpeg,
                        "-hide_banner",
                        "-nostdin",
                        "-nostats",
                        "-n",
                        "-f",
                        "rawvideo",
                        "-pixel_format",
                        "yuyv422",
                        "-video_size",
                        size,
                        "-i",
                        str(raw_path),
                        "-frames:v",
                        "1",
                        "-update",
                        "1",
                        str(folder / f"{label}.png"),
                    ],
                )
            )
        if not args.samples_only:
            report["observations"].append(
                run_child(
                    folder,
                    "catalog-full-9fps",
                    [
                        ffmpeg,
                        "-hide_banner",
                        "-nostdin",
                        "-nostats",
                        "-f",
                        "dshow",
                        "-pixel_format",
                        "yuyv422",
                        "-video_size",
                        "5472x3648",
                        "-framerate",
                        "9",
                        "-i",
                        f"video={alias}",
                        "-an",
                        "-frames:v",
                        "9",
                        "-c:v",
                        "copy",
                        "-f",
                        "null",
                        "NUL",
                    ],
                    15,
                )
            )
        report["observations"].append(run_child(folder, "controls-after", controls))
        # Successful transport is independent of whether the scene can be seen.
        report["sample_visibility"] = [
            assess_sample_visibility(path) for path in sorted(folder.glob("sample-*.png"))
        ]
        report["scene_visibility_status"] = (
            "NO_SAMPLES" if not report["sample_visibility"] else
            "UNUSABLE_EXPOSURE_DETECTED" if any(
                item["status"] in ("NEAR_BLACK", "NEAR_WHITE")
                for item in report["sample_visibility"]
            ) else "SCENE_REVIEW_REQUIRED"
        )
        report["observations"].append(
            exact_inventory(folder, ffmpeg, alias, "inventory-after")
        )
        report["status"] = "BENCH_SEQUENCE_FINISHED_REVIEW_INDIVIDUAL_RESULTS"
    except BaseException as error:
        report["error"] = dict(type=type(error).__name__, message=str(error))
        raise
    finally:
        report["finished_utc"] = datetime.now(timezone.utc).isoformat()
        write_json(folder / "bench-report.json", report)
        manifest = {}
        for path in sorted(folder.iterdir()):
            if path.is_file():
                digest = hashlib.sha256()
                with path.open("rb") as stream:
                    for block in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(block)
                manifest[path.name] = dict(
                    bytes=path.stat().st_size, sha256=digest.hexdigest()
                )
        write_json(
            folder / "bench-file-hashes.json",
            dict(
                schema="rocell.bench_file_hashes.v1",
                original_commissioning_export=False,
                files=manifest,
            ),
        )
        print(str(folder), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

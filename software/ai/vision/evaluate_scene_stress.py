"""Build and evaluate deterministic adverse-scene variants; no camera or arm access."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from io import BytesIO
import json
from pathlib import Path
import sys
from time import perf_counter

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter


AI_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_DIR))

from rocell_ai.scene_observation import FrameEvidence, canonical_hash  # noqa: E402
from rocell_ai.pixel_quality import assess as assess_pixel_quality  # noqa: E402
from rocell_ai.vision_runtime import OllamaVisionObserver  # noqa: E402


def variants(source: Image.Image) -> list[tuple[str, Image.Image, bool, str]]:
    source = source.convert("RGB")
    width, height = source.size
    dark = ImageEnhance.Brightness(source).enhance(0.08)
    blurred = source.filter(ImageFilter.GaussianBlur(radius=22))
    glare = source.copy()
    overlay = Image.new("RGBA", source.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.ellipse((width * .16, height * .20, width * .88, height * .78), fill=(255, 255, 255, 242))
    glare = Image.alpha_composite(glare.convert("RGBA"), overlay).convert("RGB")
    occluded = source.copy()
    draw = ImageDraw.Draw(occluded)
    draw.rectangle((width * .15, height * .25, width * .85, height * .75), fill=(20, 20, 20))
    absent = Image.new("RGB", source.size, (210, 205, 195))
    return [
        ("control", source, True, "unchanged_source"),
        ("dark", dark, False, "brightness_0p08"),
        ("blur", blurred, False, "gaussian_radius_22"),
        ("glare", glare, False, "opaque_white_ellipse_over_center"),
        ("occluded", occluded, False, "dark_rectangle_over_center_70x50_percent"),
        ("absent", absent, False, "uniform_background_no_device"),
    ]


def run(*, source_path: Path, observer: OllamaVisionObserver) -> dict:
    source_bytes = source_path.read_bytes()
    source = Image.open(BytesIO(source_bytes))
    captured_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    rows = []
    for name, image, expected_usable, transform in variants(source):
        stream = BytesIO()
        image.save(stream, format="JPEG", quality=92, optimize=True)
        frame = FrameEvidence(f"scene-stress-v0-{name}", captured_at, stream.getvalue())
        started = perf_counter()
        observation = observer.observe(frame)
        latency_ms = (perf_counter() - started) * 1000
        pixel_quality = assess_pixel_quality(frame)
        usable = not observation["abstain"] and pixel_quality["accepted"]
        rows.append({
            "case": name,
            "transform": transform,
            "expected_usable": expected_usable,
            "observed_usable": usable,
            "expectation_match": usable == expected_usable,
            "latency_ms": round(latency_ms, 3),
            "observation": observation,
            "pixel_quality": pixel_quality,
        })
    core = {
        "schema": "rocell.ai_scene_stress_evaluation.v0",
        "source_file": source_path.name,
        "source_sha256": __import__("hashlib").sha256(source_bytes).hexdigest(),
        "case_count": len(rows),
        "expectation_matches": sum(row["expectation_match"] for row in rows),
        "unsafe_accept_count": sum(
            not row["expected_usable"] and row["observed_usable"] for row in rows
        ),
        "control_accept_count": sum(
            row["expected_usable"] and row["observed_usable"] for row in rows
        ),
        "rows": rows,
        "synthetic_perturbations": True,
        "deployment_camera_evaluation": False,
        "physical_execution_authorized": False,
        "hardware_commands": 0,
        "limitations": [
            "The adverse cases are deterministic image edits, not new physical captures",
            "The edits are intentionally severe and do not define deployment thresholds",
            "The single source belongs to one handheld development capture group",
        ],
    }
    return {**core, "report_sha256": canonical_hash(core)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline local scene-observer stress evaluation")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434")
    parser.add_argument("--model", required=True)
    parser.add_argument("--model-identity", required=True)
    parser.add_argument("--context-tokens", type=int, default=8192)
    parser.add_argument("--timeout-seconds", type=float, default=120)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    observer = OllamaVisionObserver(
        endpoint=args.endpoint, model=args.model, model_identity=args.model_identity,
        context_tokens=args.context_tokens, timeout_seconds=args.timeout_seconds,
    )
    result = run(source_path=args.source, observer=observer)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

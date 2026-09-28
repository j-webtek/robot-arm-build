"""Read-only preflight for a final-camera localization campaign.

The command reads retained files and emits a receipt. It never opens a camera,
loads a model, starts a controller, or authorizes movement.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


AI_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = AI_ROOT / "schemas" / "physical_camera_localization_campaign_v1.schema.json"
REQUIRED_CONDITIONS = {
    "nominal", "low_light", "high_light", "glare", "blur",
    "arm_occlusion", "tool_occlusion", "cable_occlusion",
    "placement_translation", "placement_yaw", "device_absent",
}
MAX_FILE_BYTES = 128 * 1024 * 1024


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def _reject_nonfinite(value: str) -> None:
    raise ValueError(f"non-finite JSON number: {value}")


def load_strict_json(path: Path) -> dict[str, Any]:
    value = json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=_reject_duplicates,
        parse_constant=_reject_nonfinite,
    )
    if not isinstance(value, dict):
        raise ValueError("campaign must be a JSON object")
    return value


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _resolve_retained(root: Path, relative_path: str) -> Path:
    candidate = Path(relative_path)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"retained path must be relative and contained: {relative_path}")
    root = root.resolve(strict=True)
    resolved = (root / candidate).resolve(strict=True)
    if resolved == root or root not in resolved.parents or not resolved.is_file():
        raise ValueError(f"retained path is not a regular contained file: {relative_path}")
    return resolved


def _verify_file(root: Path, record: dict[str, Any]) -> None:
    path = _resolve_retained(root, record["relative_path"])
    size = path.stat().st_size
    if size <= 0 or size > MAX_FILE_BYTES or size != record["size_bytes"]:
        raise ValueError(f"retained size mismatch: {record['relative_path']}")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != record["sha256"]:
        raise ValueError(f"retained SHA-256 mismatch: {record['relative_path']}")


def preflight(campaign_path: Path, evidence_root: Path) -> dict[str, Any]:
    campaign = load_strict_json(campaign_path)
    schema = load_strict_json(SCHEMA_PATH)
    errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(campaign),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        first = errors[0]
        where = ".".join(str(part) for part in first.absolute_path) or "$"
        raise ValueError(f"schema validation failed at {where}: {first.message}")

    core = {key: value for key, value in campaign.items() if key != "campaign_sha256"}
    if canonical_hash(core) != campaign["campaign_sha256"]:
        raise ValueError("campaign SHA-256 mismatch")

    calibration = campaign["calibration_captures"]
    evaluation = campaign["evaluation_captures"]
    all_captures = calibration + evaluation
    capture_ids = [row["capture_id"] for row in all_captures]
    if len(capture_ids) != len(set(capture_ids)):
        raise ValueError("capture IDs must be unique across both splits")
    calibration_sessions = {row["session_id"] for row in calibration}
    evaluation_sessions = {row["session_id"] for row in evaluation}
    if calibration_sessions & evaluation_sessions:
        raise ValueError("calibration and evaluation sessions must be disjoint")

    image_hashes = [row["image"]["sha256"] for row in all_captures]
    if len(image_hashes) != len(set(image_hashes)):
        raise ValueError("image SHA-256 values must be unique across both splits")
    truth_hashes = [row["ground_truth"]["sha256"] for row in all_captures]
    if len(truth_hashes) != len(set(truth_hashes)):
        raise ValueError("ground-truth SHA-256 values must be unique across both splits")

    expected_camera = campaign["camera_identity_sha256"]
    expected_mode = campaign["camera_mode_controls_sha256"]
    expected_epoch = campaign["configuration_epoch_sha256"]
    for row in all_captures:
        if row["camera_identity_sha256"] != expected_camera:
            raise ValueError(f"camera identity drift: {row['capture_id']}")
        if row["camera_mode_controls_sha256"] != expected_mode:
            raise ValueError(f"camera mode drift: {row['capture_id']}")
        if row["configuration_epoch_sha256"] != expected_epoch:
            raise ValueError(f"configuration epoch drift: {row['capture_id']}")
        _verify_file(evidence_root, row["image"])
        _verify_file(evidence_root, row["ground_truth"])

    condition_counts = {condition: 0 for condition in sorted(REQUIRED_CONDITIONS)}
    for row in evaluation:
        for condition in row["conditions"]:
            condition_counts[condition] += 1
    minimum = campaign["requirements"]["minimum_evaluation_captures_per_condition"]
    insufficient = [name for name, count in condition_counts.items() if count < minimum]
    if insufficient:
        raise ValueError("insufficient evaluation condition coverage: " + ", ".join(insufficient))

    receipt_core = {
        "schema": "rocell.physical_camera_localization_campaign_preflight.v1",
        "status": "READY_FOR_OFFLINE_EVALUATION",
        "campaign_id": campaign["campaign_id"],
        "campaign_sha256": campaign["campaign_sha256"],
        "calibration_capture_count": len(calibration),
        "evaluation_capture_count": len(evaluation),
        "calibration_session_count": len(calibration_sessions),
        "evaluation_session_count": len(evaluation_sessions),
        "evaluation_condition_counts": condition_counts,
        "verified_retained_file_count": len(all_captures) * 2,
        "camera_opened": False,
        "model_loaded": False,
        "controller_started": False,
        "hardware_writes": 0,
        "physical_movements": 0,
        "qualification_installed": False,
        "limitations": [
            "Preflight verifies identities, separation, and coverage only.",
            "Model accuracy, calibration accuracy, safe-region fit, and physical contact remain unevaluated."
        ]
    }
    return {**receipt_core, "receipt_sha256": canonical_hash(receipt_core)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    receipt = preflight(args.campaign, args.evidence_root)
    rendered = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

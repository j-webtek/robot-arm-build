"""Amend the physical pilot with post-isolation pose and escrow scope."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


AI_ROOT = Path(__file__).resolve().parents[1]
SCHEMA = AI_ROOT / "schemas" / "residual_obstruction_physical_pilot_v1_1.schema.json"


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicates)
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(pilot_path: Path, source_commit: str) -> dict[str, Any]:
    pilot = load_json(pilot_path)
    if pilot["status"] != "READY_FOR_DEENERGIZED_CAPTURE":
        raise ValueError("source pilot is not ready for de-energized capture")
    if not pilot["capture_safety"]["arm_deenergized_during_every_capture"]:
        raise ValueError("source pilot does not require de-energized capture")
    if pilot["data_use"]["escrow_pixels_opened"]:
        raise ValueError("source pilot escrow was opened")
    if pilot["physical_movements"] or pilot["hardware_writes"]:
        raise ValueError("source pilot reports physical effects")

    core = {
        "schema": "tactevra.ai_residual_obstruction_physical_pilot.v1_1",
        "scope": "DEENERGIZED_REAL_CAMERA_MEASUREMENT_AND_ESCROW_PLAN_NO_QUALIFICATION",
        "status": "READY_FOR_DEENERGIZED_CAPTURE_WITH_POST_ISOLATION_POSE_CHECK",
        "source_commit": source_commit,
        "v1_file_sha256": file_hash(pilot_path),
        "v1_report_sha256": pilot["report_sha256"],
        "preserved_v1": {
            "coverage_contract": pilot["coverage_contract"],
            "boundary_scoring": pilot["boundary_scoring"],
            "coverage_measurement": pilot["coverage_measurement"],
            "capture_matrix": pilot["capture_matrix"],
            "v4_2_rejected": True,
            "v5_selected": False,
            "lighting_limit_guessed": False,
            "evaluation_opened": False,
        },
        "post_isolation_pose_binding": {
            "required": True,
            "performed_after_servo_power_isolation": True,
            "primary_method": "PARK_SILHOUETTE_MATCH_AFTER_ISOLATION",
            "optional_secondary_method": "PASSIVE_MEASURED_JOINT_FEEDBACK_AFTER_ISOLATION",
            "commanded_joint_state_prohibited": True,
            "minimum_stable_frame_count": 2,
            "silhouette_tolerance_source": "COMMISSIONED_PARK_PROFILE",
            "silhouette_tolerance_value": None,
            "evidence_required_before_each_capture_group": True,
            "end_of_session_bracket_required": True,
            "every_image_binds_pose_evidence_sha256": True,
            "failure_decision": "INVALID_RETAIN_AND_REPORT_DO_NOT_USE",
        },
        "sag_interpretation": {
            "power_off_sag_is_possible": True,
            "pre_isolation_pose_evidence_is_insufficient": True,
            "post_isolation_pose_is_the_capture_pose": True,
            "manual_reposition_during_capture_phase_prohibited": True,
            "capture_phase_robot_movement_count": 0,
            "capture_phase_hardware_write_count": 0,
        },
        "escrow_scope": {
            "session_id": "physical_pilot_escrow_01",
            "target_count": 9,
            "purpose": "REAL_WORLD_SANITY_CHECK_ONLY",
            "statistical_gate": False,
            "two_percent_miss_rate_claim_permitted": False,
            "deployment_qualification_permitted": False,
            "pixels_opened": False,
            "open_rule": "ONLY_AFTER_CANDIDATE_REPRESENTATION_CHECKPOINT_AND_THRESHOLD_ARE_FROZEN",
            "powered_real_evaluation_is_separate_future_capture": True,
            "powered_real_evaluation_authorized": False,
            "reuse_as_powered_evaluation_prohibited": True,
        },
        "capture_safety": pilot["capture_safety"],
        "hardware_writes": 0,
        "physical_movements": 0,
        "physical_authority": False,
        "limitations": [
            "No post-isolation silhouette, passive joint feedback, or physical image exists in this predeclaration.",
            "The one-session escrow is a real-world sanity check and cannot estimate a two-percent miss rate.",
            "A powered real evaluation requires a separately authorized, powered, and statistically planned capture campaign.",
            "No camera, model, deployment, or execution qualification is created.",
        ],
    }
    result = {**core, "report_sha256": canonical_hash(core)}
    schema = load_json(SCHEMA)
    errors = sorted(Draft202012Validator(schema).iter_errors(result), key=lambda e: list(e.path))
    if errors:
        first = errors[0]
        raise ValueError(f"schema validation failed at {list(first.path)}: {first.message}")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilot-v1", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build(args.pilot_v1, args.source_commit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

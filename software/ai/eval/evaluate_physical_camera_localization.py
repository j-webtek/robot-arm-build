"""Evaluate retained final-camera predictions without granting runtime authority."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from statistics import fmean
import sys
from typing import Any

from jsonschema import Draft202012Validator


AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT))

from eval.preflight_physical_camera_campaign import (
    canonical_hash,
    load_strict_json,
    preflight,
)


PLAN_SCHEMA_PATH = AI_ROOT / "schemas" / "physical_camera_localization_evaluation_plan_v1.schema.json"
RESULT_SCHEMA_PATH = AI_ROOT / "schemas" / "physical_camera_localization_evaluation_result_v1.schema.json"
TRUTH_SCHEMA_PATH = AI_ROOT / "schemas" / "physical_camera_localization_ground_truth_v1.schema.json"


def _validate(document: dict[str, Any], schema_path: Path, label: str) -> None:
    errors = sorted(
        Draft202012Validator(load_strict_json(schema_path)).iter_errors(document),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        first = errors[0]
        where = ".".join(str(part) for part in first.absolute_path) or "$"
        raise ValueError(f"{label} schema validation failed at {where}: {first.message}")


def _verify_self_hash(document: dict[str, Any], field: str, label: str) -> None:
    core = {key: value for key, value in document.items() if key != field}
    if canonical_hash(core) != document[field]:
        raise ValueError(f"{label} SHA-256 mismatch")


def _resolve_retained(root: Path, relative: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"ground-truth path must be relative and contained: {relative}")
    root = root.resolve(strict=True)
    resolved = (root / candidate).resolve(strict=True)
    if root not in resolved.parents or not resolved.is_file():
        raise ValueError(f"ground-truth path is not a contained file: {relative}")
    return resolved


def _nearest_rank(values: list[float], probability: float) -> float:
    if not values:
        raise ValueError("cannot summarize an empty error series")
    ordered = sorted(values)
    rank = max(1, math.ceil(probability * len(ordered)))
    return ordered[rank - 1]


def _summary(values: list[float]) -> dict[str, float | int]:
    return {
        "sample_count": len(values),
        "mean_error_mm": fmean(values),
        "p95_error_mm": _nearest_rank(values, 0.95),
        "p99_error_mm": _nearest_rank(values, 0.99),
        "maximum_error_mm": max(values),
    }


def _prediction_index(
    records: list[dict[str, Any]], captures: list[dict[str, Any]], split: str,
    *, model_sha256: str, preprocessing_sha256: str,
) -> dict[str, dict[str, Any]]:
    expected = {row["capture_id"]: row for row in captures}
    result: dict[str, dict[str, Any]] = {}
    for record in records:
        capture_id = record["capture_id"]
        if capture_id in result:
            raise ValueError(f"duplicate {split} prediction: {capture_id}")
        if capture_id in expected:
            if record["image_sha256"] != expected[capture_id]["image"]["sha256"]:
                raise ValueError(f"{split} prediction image mismatch: {capture_id}")
            if record["model_sha256"] != model_sha256:
                raise ValueError(f"{split} prediction model mismatch: {capture_id}")
            if record["preprocessing_sha256"] != preprocessing_sha256:
                raise ValueError(f"{split} prediction preprocessing mismatch: {capture_id}")
        result[capture_id] = record
    missing = sorted(set(expected) - set(result))
    extra = sorted(set(result) - set(expected))
    if missing or extra:
        raise ValueError(f"{split} prediction coverage mismatch; missing={missing}; extra={extra}")
    return result


def _load_truth(root: Path, capture: dict[str, Any], target_ids: set[str]) -> dict[str, Any]:
    record = load_strict_json(_resolve_retained(root, capture["ground_truth"]["relative_path"]))
    _validate(record, TRUTH_SCHEMA_PATH, "ground truth")
    if record["capture_id"] != capture["capture_id"]:
        raise ValueError(f"ground-truth capture mismatch: {capture['capture_id']}")
    points = set(record["target_points_mm"])
    expected = target_ids if record["device_present"] else set()
    if points != expected:
        raise ValueError(f"ground-truth target coverage mismatch: {capture['capture_id']}")
    return record


def _errors(
    truth: dict[str, Any], prediction: dict[str, Any], target_ids: set[str], capture_id: str,
) -> dict[str, float]:
    if prediction["abstained"]:
        if prediction["target_points_mm"] or not prediction["abstain_reasons"]:
            raise ValueError(f"inconsistent abstention: {capture_id}")
        return {}
    if prediction["abstain_reasons"]:
        raise ValueError(f"accepted prediction contains abstention reasons: {capture_id}")
    if set(prediction["target_points_mm"]) != target_ids:
        raise ValueError(f"prediction target coverage mismatch: {capture_id}")
    if not truth["device_present"]:
        return {}
    return {
        target_id: math.dist(
            truth["target_points_mm"][target_id],
            prediction["target_points_mm"][target_id],
        )
        for target_id in sorted(target_ids)
    }


def evaluate(
    campaign_path: Path,
    preflight_path: Path,
    plan_path: Path,
    evidence_root: Path,
) -> dict[str, Any]:
    campaign = load_strict_json(campaign_path)
    receipt = load_strict_json(preflight_path)
    plan = load_strict_json(plan_path)
    _validate(plan, PLAN_SCHEMA_PATH, "evaluation plan")
    _verify_self_hash(plan, "plan_sha256", "evaluation plan")
    _verify_self_hash(receipt, "receipt_sha256", "preflight receipt")

    actual_receipt = preflight(campaign_path, evidence_root)
    if receipt != actual_receipt:
        raise ValueError("preflight receipt does not match current retained campaign")
    if plan["campaign_sha256"] != campaign["campaign_sha256"]:
        raise ValueError("plan campaign identity mismatch")
    if plan["preflight_receipt_sha256"] != receipt["receipt_sha256"]:
        raise ValueError("plan preflight identity mismatch")
    if plan["model_artifact_manifest_sha256"] != campaign["model_artifact_manifest_sha256"]:
        raise ValueError("plan model artifact identity mismatch")
    if plan["keyboard_target_map_sha256"] != campaign["keyboard_target_map_sha256"]:
        raise ValueError("plan target-map identity mismatch")
    if plan["declared_coverage_probability"] != campaign["requirements"]["declared_coverage_probability"]:
        raise ValueError("plan coverage probability mismatch")

    target_map = plan["keyboard_target_map"]
    target_map_core = {key: value for key, value in target_map.items() if key != "target_map_sha256"}
    if canonical_hash(target_map_core) != target_map["target_map_sha256"]:
        raise ValueError("keyboard target-map SHA-256 mismatch")
    if target_map["target_map_sha256"] != plan["keyboard_target_map_sha256"]:
        raise ValueError("embedded target-map identity mismatch")
    target_ids = set(target_map["targets"])
    safe_radii = {
        target_id: record["safe_radius_mm"] for target_id, record in target_map["targets"].items()
    }
    unsafe = set(plan["unsafe_conditions"])
    calibration_rows = campaign["calibration_captures"]
    evaluation_rows = campaign["evaluation_captures"]
    prediction_args = {
        "model_sha256": plan["model_sha256"],
        "preprocessing_sha256": plan["preprocessing_sha256"],
    }
    calibration_predictions = _prediction_index(
        plan["calibration_predictions"], calibration_rows, "calibration", **prediction_args
    )
    evaluation_predictions = _prediction_index(
        plan["evaluation_predictions"], evaluation_rows, "evaluation", **prediction_args
    )

    calibration_errors: list[float] = []
    calibration_abstentions: list[str] = []
    unsafe_false_accept_ids: set[str] = set()
    for capture in calibration_rows:
        capture_id = capture["capture_id"]
        conditions = set(capture["conditions"])
        unsafe_capture = bool(conditions & unsafe)
        truth = _load_truth(evidence_root, capture, target_ids)
        if ("device_absent" in conditions) == truth["device_present"]:
            raise ValueError(f"device-presence truth conflicts with conditions: {capture_id}")
        prediction = calibration_predictions[capture_id]
        errors = _errors(truth, prediction, target_ids, capture_id)
        if unsafe_capture and not prediction["abstained"]:
            unsafe_false_accept_ids.add(capture_id)
        elif prediction["abstained"] and truth["device_present"] and not unsafe_capture:
            calibration_abstentions.append(capture_id)
        elif truth["device_present"] and not unsafe_capture:
            calibration_errors.extend(errors.values())
    if not calibration_errors:
        raise ValueError("calibration produced no eligible target errors")
    localization_bound = max(calibration_errors)
    additional_uncertainty = sum(
        record["bound_mm"] for record in plan["additional_uncertainty"].values()
    )
    composed_bound = localization_bound + additional_uncertainty

    per_target_errors = {target_id: [] for target_id in sorted(target_ids)}
    per_target_eligible = {target_id: 0 for target_id in sorted(target_ids)}
    per_target_covered = {target_id: 0 for target_id in sorted(target_ids)}
    per_target_abstentions = {target_id: 0 for target_id in sorted(target_ids)}
    per_condition = {
        condition: {
            "capture_count": 0,
            "abstention_count": 0,
            "false_accept_count": 0,
            "errors": [],
        }
        for condition in campaign["requirements"]["required_conditions"]
    }
    eligible_events = 0
    covered_events = 0
    evaluation_abstentions: list[str] = []
    uncovered_case_ids: set[str] = set()
    for capture in evaluation_rows:
        capture_id = capture["capture_id"]
        conditions = set(capture["conditions"])
        unsafe_capture = bool(conditions & unsafe)
        truth = _load_truth(evidence_root, capture, target_ids)
        if ("device_absent" in conditions) == truth["device_present"]:
            raise ValueError(f"device-presence truth conflicts with conditions: {capture_id}")
        prediction = evaluation_predictions[capture_id]
        errors = _errors(truth, prediction, target_ids, capture_id)
        for condition in conditions:
            per_condition[condition]["capture_count"] += 1
            if prediction["abstained"]:
                per_condition[condition]["abstention_count"] += 1
        if unsafe_capture or not truth["device_present"]:
            if not prediction["abstained"]:
                unsafe_false_accept_ids.add(capture_id)
                for condition in conditions:
                    per_condition[condition]["false_accept_count"] += 1
            continue
        eligible_events += len(target_ids)
        for target_id in target_ids:
            per_target_eligible[target_id] += 1
        if prediction["abstained"]:
            evaluation_abstentions.append(capture_id)
            uncovered_case_ids.add(capture_id)
            for target_id in target_ids:
                per_target_abstentions[target_id] += 1
            continue
        for target_id, error in errors.items():
            per_target_errors[target_id].append(error)
            for condition in conditions:
                per_condition[condition]["errors"].append(error)
            if error <= localization_bound:
                covered_events += 1
                per_target_covered[target_id] += 1
            else:
                uncovered_case_ids.add(capture_id)

    if eligible_events == 0:
        raise ValueError("evaluation produced no eligible target events")
    measured_coverage = covered_events / eligible_events
    per_target = {}
    for target_id, values in per_target_errors.items():
        if values:
            per_target[target_id] = {
                **_summary(values),
                "eligible_event_count": per_target_eligible[target_id],
                "covered_event_count": per_target_covered[target_id],
                "abstention_count": per_target_abstentions[target_id],
                "coverage_probability": (
                    per_target_covered[target_id] / per_target_eligible[target_id]
                ),
            }
    condition_results = {}
    for condition, metrics in per_condition.items():
        errors = metrics.pop("errors")
        condition_results[condition] = {
            **metrics,
            "target_error_count": len(errors),
            "error_summary": _summary(errors) if errors else None,
        }
    missing_target_metrics = sorted(target_ids - set(per_target))
    safe_region_failures = sorted(
        target_id for target_id, radius in safe_radii.items()
        if composed_bound > radius
    )
    criteria = {
        "calibration_has_zero_abstentions": not calibration_abstentions,
        "held_out_coverage_met": measured_coverage >= plan["declared_coverage_probability"],
        "unsafe_false_accepts_zero": not unsafe_false_accept_ids,
        "all_targets_have_metrics": not missing_target_metrics,
        "composed_bound_fits_all_safe_regions": not safe_region_failures,
    }
    recommendation = all(criteria.values())
    result_core = {
        "schema": "rocell.physical_camera_localization_evaluation_result.v1",
        "status": "QUALIFICATION_RECOMMENDED" if recommendation else "QUALIFICATION_BLOCKED",
        "campaign_id": campaign["campaign_id"],
        "campaign_sha256": campaign["campaign_sha256"],
        "preflight_receipt_sha256": receipt["receipt_sha256"],
        "plan_sha256": plan["plan_sha256"],
        "evaluator_source_commit": plan["source_commit"],
        "model_id": plan["model_id"],
        "model_sha256": plan["model_sha256"],
        "preprocessing_sha256": plan["preprocessing_sha256"],
        "model_artifact_manifest_sha256": plan["model_artifact_manifest_sha256"],
        "keyboard_target_map_sha256": plan["keyboard_target_map_sha256"],
        "calibration_capture_count": len(calibration_rows),
        "evaluation_capture_count": len(evaluation_rows),
        "calibration_target_error_count": len(calibration_errors),
        "eligible_evaluation_target_event_count": eligible_events,
        "covered_evaluation_target_event_count": covered_events,
        "declared_coverage_probability": plan["declared_coverage_probability"],
        "measured_coverage_probability": measured_coverage,
        "calibration_localization_bound_mm": localization_bound,
        "additional_uncertainty": plan["additional_uncertainty"],
        "uncertainty_composition": "CONSERVATIVE_LINEAR_SUM",
        "composed_error_bound_mm": composed_bound,
        "calibration_abstention_count": len(calibration_abstentions),
        "evaluation_abstention_count": len(evaluation_abstentions),
        "unsafe_false_accept_count": len(unsafe_false_accept_ids),
        "uncovered_case_ids": sorted(uncovered_case_ids),
        "unsafe_false_accept_case_ids": sorted(unsafe_false_accept_ids),
        "missing_target_metric_ids": missing_target_metrics,
        "safe_region_failure_target_ids": safe_region_failures,
        "per_condition": condition_results,
        "per_target": per_target,
        "criteria": criteria,
        "qualification_recommended": recommendation,
        "qualification_installed": False,
        "physical_deployment_qualified": False,
        "model_motion_batch_emitted": False,
        "controller_started": False,
        "hardware_writes": 0,
        "physical_movements": 0,
        "limitations": [
            "A recommendation requires separate review and trusted-registry installation.",
            "Offline coordinate accuracy does not establish robot tracking, key contact, or device-effect success.",
            "The calibration maximum is an empirical bound over this retained campaign, not a universal guarantee.",
            "Prediction provenance depends on the separately frozen inference producer; this evaluator does not load model weights.",
        ],
    }
    result = {**result_core, "result_sha256": canonical_hash(result_core)}
    _validate(result, RESULT_SCHEMA_PATH, "evaluation result")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign", type=Path, required=True)
    parser.add_argument("--preflight", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(args.campaign, args.preflight, args.plan, args.evidence_root)
    rendered = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(rendered.encode("utf-8"))
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

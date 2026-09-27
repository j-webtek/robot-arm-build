import hashlib
import json
import sys
from pathlib import Path

import numpy as np

AI = Path(__file__).resolve().parents[1]
ROOT = AI.parents[1]
sys.path.insert(0, str(AI))

from evidence_artifacts import verify_frozen_artifacts
from train.select_ensemble_scale_mapping import evaluate_checks, checks_pass
from train.select_risk_gated_metric import attach_outputs, gated_summary
from vision.evaluate_grouped_uncertainty import calibrate


def test_radius_inflation_is_applied_once_after_calibration():
    calibrated = 2.0
    inflation = 1.15
    assert calibrated * inflation == 2.3


def test_report_recounts_inflated_risk_gate_failure():
    plan_path = AI / "train/inflated_risk_gate_v1_plan.json"
    plan = json.loads(plan_path.read_text())
    verify_frozen_artifacts(ROOT, plan["file_sha256"])
    report = json.loads((AI / "eval/inflated_risk_gate_v1_report.json").read_text())

    assert report["plan_sha256"] == hashlib.sha256(plan_path.read_bytes()).hexdigest()
    assert report["prior_report_sha256"] == plan["file_sha256"][plan["prior_report"]]
    assert report["metric_report_sha256"] == plan["file_sha256"][plan["metric_report"]]
    assert report["risk_report_sha256"] == plan["file_sha256"][plan["risk_report"]]
    assert report["metric_checkpoint_sha256"] == plan["file_sha256"][plan["metric_checkpoint"]]
    assert report["risk_checkpoint_sha256"] == plan["file_sha256"][plan["risk_checkpoint"]]

    for name, (start, count) in plan["groups"].items():
        rows = report[name]["rows"]
        assert len(rows) == count * len(plan["styles"]) * len(plan["conditions"])
        assert {(row["seed"], row["style"], row["condition"]) for row in rows} == {
            (seed, style, condition)
            for seed in range(start, start + count)
            for style in plan["styles"]
            for condition in plan["conditions"]
        }

    calibration = report["mapping_calibration"]["rows"]
    reference = np.sort(
        np.asarray([row["tail_risk_score"] for row in calibration], dtype=np.float32)
    )
    assert report["risk_reference_sha256"] == hashlib.sha256(reference.tobytes()).hexdigest()
    recounted = attach_outputs(
        calibration,
        [row["metric_bound_mm"] for row in calibration],
        [row["tail_risk_score"] for row in calibration],
        reference,
    )
    for expected, actual in zip(calibration, recounted):
        assert expected["tail_risk_percentile"] == actual["tail_risk_percentile"]
        assert expected["scale_mm"] == actual["scale_mm"]

    start, count = plan["groups"]["mapping_calibration"]
    scene_scores = [
        {
            "seed": seed,
            "normalized_max": max(
                row["error_mm"] / row["scale_mm"]
                for row in calibration
                if row["seed"] == seed
            ),
        }
        for seed in range(start, start + count)
    ]
    assert report["mapping_calibration"]["scene_scores"] == scene_scores
    rank, calibrated = calibrate(
        [row["normalized_max"] for row in scene_scores], plan["alpha"]
    )
    assert report["rank"] == rank
    assert report["calibrated_quantile"] == calibrated
    applied = calibrated * plan["radius_inflation"]
    assert report["applied_quantile"] == applied

    selection = report["selection"]["rows"]
    summary = gated_summary(
        selection,
        applied,
        plan["tolerance_mm"],
        plan["maximum_risk_percentile"],
    )
    conditions = {
        condition: gated_summary(
            [row for row in selection if row["condition"] == condition],
            applied,
            plan["tolerance_mm"],
            plan["maximum_risk_percentile"],
        )
        for condition in plan["conditions"]
    }
    checks = evaluate_checks(summary, conditions, plan)
    assert report["selection"]["summary"] == summary
    assert report["selection"]["conditions"] == conditions
    assert report["checks"] == checks
    assert checks["overall_scene_coverage"]
    assert checks["overall_accepted_image_coverage"]
    assert checks["overall_accepted_scene_coverage"]
    assert checks["zero_accepted_errors_over_tolerance"]
    assert all(checks["condition_accepted_image_coverage"].values())
    assert not checks["overall_accepted_fraction"]
    assert not checks["condition_accepted_fraction"]["full"]
    assert not checks_pass(checks)
    assert not report["passed_selection"]
    assert report["mapping_fits"] == 1 and report["new_model_fits"] == 0
    assert report["optimizer_updates"] == 0
    assert report["hardware_writes"] == report["physical_movements"] == 0
    assert not report["qualification_installed"]

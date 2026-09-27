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


def test_report_recounts_frozen_independent_confirmation_near_miss():
    plan_path = AI / "train/obstruction_weighted_risk_gate_confirmation_v1_plan.json"
    plan = json.loads(plan_path.read_text())
    verify_frozen_artifacts(ROOT, plan["file_sha256"])
    source = json.loads((ROOT / plan["selection_report"]).read_text())
    report = json.loads(
        (
            AI / "eval/obstruction_weighted_risk_gate_confirmation_v1_report.json"
        ).read_text()
    )

    assert report["plan_sha256"] == hashlib.sha256(plan_path.read_bytes()).hexdigest()
    assert report["selection_report_sha256"] == plan["file_sha256"][plan["selection_report"]]
    assert report["metric_checkpoint_sha256"] == plan["file_sha256"][plan["metric_checkpoint"]]
    assert report["risk_checkpoint_sha256"] == plan["file_sha256"][plan["risk_checkpoint"]]
    assert source["normalized_quantile"] == report["normalized_quantile"] == plan["normalized_quantile"]

    reference = np.sort(
        np.asarray(
            [row["tail_risk_score"] for row in source["mapping_calibration"]["rows"]],
            dtype=np.float32,
        )
    )
    assert report["risk_reference_sha256"] == plan["risk_reference_sha256"]
    assert hashlib.sha256(reference.tobytes()).hexdigest() == plan["risk_reference_sha256"]

    start, count = plan["groups"]["confirmation"]
    rows = report["confirmation"]["rows"]
    assert len(rows) == count * len(plan["styles"]) * len(plan["conditions"])
    assert {(row["seed"], row["style"], row["condition"]) for row in rows} == {
        (seed, style, condition)
        for seed in range(start, start + count)
        for style in plan["styles"]
        for condition in plan["conditions"]
    }
    recounted = attach_outputs(
        rows,
        [row["metric_bound_mm"] for row in rows],
        [row["tail_risk_score"] for row in rows],
        reference,
    )
    for expected, actual in zip(rows, recounted):
        assert expected["tail_risk_percentile"] == actual["tail_risk_percentile"]
        assert expected["scale_mm"] == actual["scale_mm"]

    summary = gated_summary(
        rows,
        plan["normalized_quantile"],
        plan["tolerance_mm"],
        plan["maximum_risk_percentile"],
    )
    conditions = {
        condition: gated_summary(
            [row for row in rows if row["condition"] == condition],
            plan["normalized_quantile"],
            plan["tolerance_mm"],
            plan["maximum_risk_percentile"],
        )
        for condition in plan["conditions"]
    }
    checks = evaluate_checks(summary, conditions, plan)
    assert report["confirmation"]["summary"] == summary
    assert report["confirmation"]["conditions"] == conditions
    assert report["checks"] == checks
    assert not checks["overall_accepted_fraction"]
    assert summary["accepted_fraction"] == 0.0495
    assert summary["accepted_bound_violations"] == 0
    assert summary["accepted_errors_over_tolerance"] == 0
    assert all(checks["condition_accepted_fraction"].values())
    assert all(checks["condition_accepted_image_coverage"].values())
    assert not checks_pass(checks)
    assert not report["independent_confirmation_passed"]
    assert report["mapping_fits"] == report["new_model_fits"] == 0
    assert report["optimizer_updates"] == 0
    assert report["hardware_writes"] == report["physical_movements"] == 0
    assert not report["qualification_installed"]

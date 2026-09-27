import hashlib
import json
import sys
from pathlib import Path

import torch

AI = Path(__file__).resolve().parents[1]
ROOT = AI.parents[1]
sys.path.insert(0, str(AI))

from evidence_artifacts import verify_frozen_artifacts
from train.train_bounded_upper_tail_head import bounded_metric
from train.train_upper_tail_error_head import (
    checks_pass,
    decision_checks,
    metric_summary,
)
from vision.evaluate_localized_geometric_risk import ranking


def test_bounded_metric_respects_frozen_interval():
    raw = torch.tensor([-100.0, 0.0, 100.0], dtype=torch.float32)
    values = bounded_metric(raw, 0.25, 10.0)
    assert float(values[0]) == 0.25
    assert float(values[1]) == 5.125
    assert float(values[2]) == 10.0


def test_report_recounts_bounded_selection_and_near_miss():
    plan_path = AI / "train/bounded_upper_tail_head_v1_plan.json"
    plan = json.loads(plan_path.read_text())
    verify_frozen_artifacts(ROOT, plan["file_sha256"])
    report_path = AI / "eval/bounded_upper_tail_head_v1_report.json"
    report = json.loads(report_path.read_text())
    checkpoint = AI / "results/bounded_upper_tail_head_v1/model.pt"

    assert report["plan_sha256"] == hashlib.sha256(plan_path.read_bytes()).hexdigest()
    assert report["prior_report_sha256"] == plan["file_sha256"][plan["prior_report"]]
    assert report["checkpoint_sha256"] == hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    assert report["model_parameters"] == 52481
    assert len(report["history"]) == plan["epochs"] == 20
    for name, (start, count) in plan["groups"].items():
        rows = report["training_rows"] if name == "training" else report["selection_rows"]
        assert len(rows) == count * len(plan["styles"]) * len(plan["conditions"])
        assert {(row["seed"], row["style"], row["condition"]) for row in rows} == {
            (seed, style, condition)
            for seed in range(start, start + count)
            for style in plan["styles"]
            for condition in plan["conditions"]
        }

    rows = report["selection_rows"]
    candidate = metric_summary(rows, "bounded_upper_tail_mm", plan["quantile"])
    candidate["conditions"] = {
        condition: metric_summary(
            [row for row in rows if row["condition"] == condition],
            "bounded_upper_tail_mm",
            plan["quantile"],
        )
        for condition in plan["conditions"]
    }
    baseline = metric_summary(rows, "constant_bound_mm", plan["quantile"])
    ranks = ranking(rows, "bounded_upper_tail_mm", plan["conditions"], plan["tolerance_mm"])
    checks = decision_checks(candidate, baseline, ranks, plan)
    checks["finite_bound"] = (
        candidate["maximum_bound_mm"] <= plan["maximum_bound_mm"]
        and min(row["bounded_upper_tail_mm"] for row in rows)
        >= plan["minimum_bound_mm"]
    )
    assert report["candidate_summary"] == candidate
    assert report["constant_summary"] == baseline
    assert report["ranking"] == ranks
    assert report["checks"] == checks
    assert checks["minimum_coverage"] and checks["maximum_coverage"]
    assert all(checks["condition_coverage"].values())
    assert all(checks["condition_image_auc"].values())
    assert checks["finite_bound"]
    assert not checks["minimum_scene_auc"]
    assert not checks_pass(checks)
    assert not report["passed_selection"]
    assert report["model_fits"] == 1 and report["calibration_fits"] == 0
    assert report["optimizer_updates"] == 2500
    assert report["hardware_writes"] == report["physical_movements"] == 0
    assert not report["qualification_installed"]

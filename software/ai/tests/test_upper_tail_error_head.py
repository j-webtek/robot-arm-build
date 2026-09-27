import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import torch

AI = Path(__file__).resolve().parents[1]
ROOT = AI.parents[1]
sys.path.insert(0, str(AI))

from evidence_artifacts import verify_frozen_artifacts
from train.train_upper_tail_error_head import (
    checks_pass,
    decision_checks,
    metric_summary,
    pinball_loss,
)
from vision.evaluate_localized_geometric_risk import ranking


def test_pinball_loss_and_metric_summary_are_directional():
    truth = torch.tensor([1.0, 3.0], dtype=torch.float32)
    prediction = torch.tensor([2.0, 2.0], dtype=torch.float32)
    assert float(pinball_loss(prediction, truth, 0.95)) == np.float32(0.5)
    rows = [
        {"error_mm": 1.0, "bound": 2.0},
        {"error_mm": 3.0, "bound": 2.0},
    ]
    summary = metric_summary(rows, "bound", 0.95)
    assert summary["coverage"] == 0.5
    assert summary["mean_pinball_loss"] == 0.5
    assert summary["median_bound_mm"] == 2.0


def test_report_recounts_upper_tail_selection_and_failure():
    plan_path = AI / "train/upper_tail_error_head_v1_plan.json"
    plan = json.loads(plan_path.read_text())
    verify_frozen_artifacts(ROOT, plan["file_sha256"])
    report_path = AI / "eval/upper_tail_error_head_v1_report.json"
    report = json.loads(report_path.read_text())
    checkpoint = AI / "results/upper_tail_error_head_v1/model.pt"

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
    candidate = metric_summary(rows, "upper_tail_bound_mm", plan["quantile"])
    candidate["conditions"] = {
        condition: metric_summary(
            [row for row in rows if row["condition"] == condition],
            "upper_tail_bound_mm",
            plan["quantile"],
        )
        for condition in plan["conditions"]
    }
    baseline = metric_summary(rows, "constant_bound_mm", plan["quantile"])
    ranks = ranking(rows, "upper_tail_bound_mm", plan["conditions"], plan["tolerance_mm"])
    checks = decision_checks(candidate, baseline, ranks, plan)
    assert report["candidate_summary"] == candidate
    assert report["constant_summary"] == baseline
    assert report["ranking"] == ranks
    assert report["checks"] == checks
    assert not checks["minimum_coverage"]
    assert not checks["condition_coverage"]["full"]
    assert all(checks["condition_image_auc"].values())
    assert not checks_pass(checks)
    assert not report["passed_selection"]
    assert report["model_fits"] == 1 and report["calibration_fits"] == 0
    assert report["optimizer_updates"] == 2500
    assert report["hardware_writes"] == report["physical_movements"] == 0
    assert not report["qualification_installed"]

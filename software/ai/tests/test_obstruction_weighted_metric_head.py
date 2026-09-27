import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pytest
import torch

AI = Path(__file__).resolve().parents[1]
ROOT = AI.parents[1]
sys.path.insert(0, str(AI))

from evidence_artifacts import verify_frozen_artifacts
from train.train_obstruction_weighted_metric_head import (
    obstruction_weights,
    weighted_pinball_loss,
)
from train.train_upper_tail_error_head import (
    checks_pass,
    decision_checks,
    metric_summary,
)
from vision.evaluate_localized_geometric_risk import ranking


def test_obstruction_weights_and_weighted_pinball_are_explicit():
    rows = [
        {"condition": "standard"},
        {"condition": "appearance_shift"},
        {"condition": "partial"},
        {"condition": "full"},
    ]
    schedule = {"standard": 1, "appearance_shift": 1, "partial": 2, "full": 4}
    weights = obstruction_weights(rows, schedule)
    assert weights.tolist() == [1.0, 1.0, 2.0, 4.0]
    prediction = torch.tensor([1.0, 1.0], dtype=torch.float32)
    truth = torch.tensor([2.0, 0.0], dtype=torch.float32)
    value = weighted_pinball_loss(
        prediction,
        truth,
        torch.tensor([1.0, 3.0], dtype=torch.float32),
        0.75,
    )
    assert float(value) == pytest.approx((0.75 + 3.0 * 0.25) / 4.0)


def test_report_recounts_obstruction_weighted_selection():
    plan_path = AI / "train/obstruction_weighted_metric_head_v1_plan.json"
    plan = json.loads(plan_path.read_text())
    verify_frozen_artifacts(ROOT, plan["file_sha256"])
    report_path = AI / "eval/obstruction_weighted_metric_head_v1_report.json"
    report = json.loads(report_path.read_text())
    checkpoint = AI / "results/obstruction_weighted_metric_head_v1/model.pt"

    assert report["plan_sha256"] == hashlib.sha256(plan_path.read_bytes()).hexdigest()
    assert report["prior_report_sha256"] == plan["file_sha256"][plan["prior_report"]]
    assert report["prior_checkpoint_sha256"] == plan["file_sha256"][plan["prior_checkpoint"]]
    assert report["trigger_report_sha256"] == plan["file_sha256"][plan["trigger_report"]]
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

    training_weights = obstruction_weights(
        report["training_rows"], plan["condition_weights"]
    )
    assert report["training_condition_weight_sum"] == float(training_weights.sum())
    repeated_errors = np.repeat(
        [row["error_mm"] for row in report["training_rows"]],
        training_weights.astype(np.int64),
    )
    assert report["training_constant_bound_mm"] == float(
        np.quantile(repeated_errors, plan["quantile"], method="higher")
    )

    rows = report["selection_rows"]
    candidate = metric_summary(
        rows, "obstruction_weighted_bound_mm", plan["quantile"]
    )
    prior = metric_summary(rows, "prior_bounded_upper_tail_mm", plan["quantile"])
    for summary, key in (
        (candidate, "obstruction_weighted_bound_mm"),
        (prior, "prior_bounded_upper_tail_mm"),
    ):
        summary["conditions"] = {
            condition: metric_summary(
                [row for row in rows if row["condition"] == condition],
                key,
                plan["quantile"],
            )
            for condition in plan["conditions"]
        }
    baseline = metric_summary(rows, "constant_bound_mm", plan["quantile"])
    ranks = ranking(
        rows,
        "obstruction_weighted_bound_mm",
        plan["conditions"],
        plan["tolerance_mm"],
    )
    checks = decision_checks(candidate, baseline, ranks, plan)
    checks.update(
        {
            "finite_bound": candidate["maximum_bound_mm"] <= plan["maximum_bound_mm"]
            and min(row["obstruction_weighted_bound_mm"] for row in rows)
            >= plan["minimum_bound_mm"],
            "prior_pinball_noninferiority": candidate["mean_pinball_loss"]
            <= prior["mean_pinball_loss"] * plan["maximum_prior_pinball_ratio"],
            "prior_median_bound_limit": candidate["median_bound_mm"]
            <= prior["median_bound_mm"] * plan["maximum_prior_median_ratio"],
            "partial_coverage_improvement": candidate["conditions"]["partial"]["coverage"]
            >= prior["conditions"]["partial"]["coverage"]
            + plan["minimum_partial_coverage_improvement"],
            "full_coverage_improvement": candidate["conditions"]["full"]["coverage"]
            >= prior["conditions"]["full"]["coverage"]
            + plan["minimum_full_coverage_improvement"],
        }
    )
    assert report["candidate_summary"] == candidate
    assert report["prior_summary"] == prior
    assert report["constant_summary"] == baseline
    assert report["ranking"] == ranks
    assert report["checks"] == checks
    assert checks_pass(checks)
    assert report["passed_selection"]
    assert report["model_fits"] == 1 and report["calibration_fits"] == 0
    assert report["optimizer_updates"] == 2500
    assert report["hardware_writes"] == report["physical_movements"] == 0
    assert not report["qualification_installed"]

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
from train.train_obstruction_weighted_metric_head import obstruction_weights
from train.train_upper_tail_error_head import (
    checks_pass,
    decision_checks,
    metric_summary,
)
from vision.evaluate_localized_geometric_risk import ranking
from vision.residual_metric_head import ResidualMetricHead, bounded_multiplier


def test_residual_head_and_multiplier_are_bounded():
    head = ResidualMetricHead()
    assert sum(parameter.numel() for parameter in head.parameters()) == 52577
    output = head(torch.zeros((2, 514), dtype=torch.float32))
    assert output.shape == (2,)
    values = bounded_multiplier(
        torch.tensor([-100.0, 0.0, 100.0], dtype=torch.float32), 0.5, 2.0
    )
    assert values.tolist() == [0.5, 1.25, 2.0]


def test_report_recounts_residual_metric_tradeoff():
    plan_path = AI / "train/residual_metric_head_v1_plan.json"
    plan = json.loads(plan_path.read_text())
    verify_frozen_artifacts(ROOT, plan["file_sha256"])
    report_path = AI / "eval/residual_metric_head_v1_report.json"
    report = json.loads(report_path.read_text())
    checkpoint = AI / "results/residual_metric_head_v1/model.pt"

    assert report["plan_sha256"] == hashlib.sha256(plan_path.read_bytes()).hexdigest()
    assert report["base_report_sha256"] == plan["file_sha256"][plan["base_report"]]
    assert report["base_checkpoint_sha256"] == plan["file_sha256"][plan["base_checkpoint"]]
    assert report["risk_report_sha256"] == plan["file_sha256"][plan["risk_report"]]
    assert report["risk_checkpoint_sha256"] == plan["file_sha256"][plan["risk_checkpoint"]]
    assert report["trigger_report_sha256"] == plan["file_sha256"][plan["trigger_report"]]
    assert report["checkpoint_sha256"] == hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    assert report["model_parameters"] == 52577
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
    candidate = metric_summary(rows, "residual_metric_bound_mm", plan["quantile"])
    prior = metric_summary(rows, "base_metric_bound_mm", plan["quantile"])
    for summary, key in (
        (candidate, "residual_metric_bound_mm"),
        (prior, "base_metric_bound_mm"),
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
        rows, "residual_metric_bound_mm", plan["conditions"], plan["tolerance_mm"]
    )
    proxy = report["utility_proxy"]
    assert proxy["candidate"]["accepted"] == sum(
        item["accepted"] for item in proxy["candidate_conditions"].values()
    )
    for values in [proxy["candidate"], proxy["prior"], *proxy["candidate_conditions"].values()]:
        assert values["fraction"] == values["accepted"] / values["images"]

    checks = decision_checks(candidate, baseline, ranks, plan)
    checks.update(
        {
            "finite_bound": candidate["maximum_bound_mm"] <= plan["maximum_bound_mm"]
            and min(row["residual_metric_bound_mm"] for row in rows)
            >= plan["minimum_bound_mm"],
            "prior_pinball_improvement": candidate["mean_pinball_loss"]
            <= prior["mean_pinball_loss"] * plan["maximum_prior_pinball_ratio"],
            "prior_median_bound_limit": candidate["median_bound_mm"]
            <= prior["median_bound_mm"] * plan["maximum_prior_median_ratio"],
            "partial_coverage_noninferiority": candidate["conditions"]["partial"]["coverage"]
            >= prior["conditions"]["partial"]["coverage"],
            "full_coverage_noninferiority": candidate["conditions"]["full"]["coverage"]
            >= prior["conditions"]["full"]["coverage"],
            "proxy_utility": proxy["candidate"]["fraction"]
            >= plan["minimum_proxy_accepted_fraction"],
            "proxy_utility_improvement": proxy["candidate"]["fraction"]
            >= proxy["prior"]["fraction"] + plan["minimum_proxy_improvement"],
            "proxy_condition_utility": {
                condition: proxy["candidate_conditions"][condition]["fraction"]
                >= plan["minimum_proxy_condition_fraction"][condition]
                for condition in plan["conditions"]
            },
        }
    )
    checks["proxy_condition_utility_pass"] = all(
        checks["proxy_condition_utility"].values()
    )
    assert report["candidate_summary"] == candidate
    assert report["prior_summary"] == prior
    assert report["constant_summary"] == baseline
    assert report["ranking"] == ranks
    assert report["checks"] == checks
    assert not checks["prior_pinball_improvement"]
    assert all(
        value
        for key, value in checks.items()
        if isinstance(value, bool) and key != "prior_pinball_improvement"
    )
    assert all(checks["condition_coverage"].values())
    assert all(checks["condition_image_auc"].values())
    assert all(checks["proxy_condition_utility"].values())
    assert not checks_pass(checks)
    assert not report["passed_selection"]
    assert report["model_fits"] == 1 and report["calibration_fits"] == 0
    assert report["optimizer_updates"] == 2500
    assert report["hardware_writes"] == report["physical_movements"] == 0
    assert not report["qualification_installed"]

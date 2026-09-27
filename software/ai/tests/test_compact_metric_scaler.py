import hashlib
import json
import sys
from pathlib import Path

import numpy as np

AI = Path(__file__).resolve().parents[1]
ROOT = AI.parents[1]
sys.path.insert(0, str(AI))

from evidence_artifacts import verify_frozen_artifacts
from train.train_compact_metric_scaler import balanced_weights
from train.train_upper_tail_error_head import (
    checks_pass,
    decision_checks,
    metric_summary,
)
from vision.evaluate_localized_geometric_risk import ranking


def test_report_recounts_compact_scaler_tradeoff():
    plan_path = AI / "train/compact_metric_scaler_v1_plan.json"
    plan = json.loads(plan_path.read_text())
    verify_frozen_artifacts(ROOT, plan["file_sha256"])
    report_path = AI / "eval/compact_metric_scaler_v1_report.json"
    report = json.loads(report_path.read_text())
    checkpoint = AI / "results/compact_metric_scaler_v1/model.pt"

    assert report["plan_sha256"] == hashlib.sha256(plan_path.read_bytes()).hexdigest()
    for report_key, plan_key in (
        ("base_report_sha256", "base_report"),
        ("base_checkpoint_sha256", "base_checkpoint"),
        ("risk_report_sha256", "risk_report"),
        ("risk_checkpoint_sha256", "risk_checkpoint"),
        ("trigger_report_sha256", "trigger_report"),
        ("predecessor_report_sha256", "predecessor_report"),
    ):
        assert report[report_key] == plan["file_sha256"][plan[plan_key]]
    assert report["checkpoint_sha256"] == hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    assert report["model_parameters"] == 3
    assert len(report["history"]) == plan["epochs"] == 50

    for name, (start, count) in plan["groups"].items():
        rows = report["training_rows"] if name == "training" else report["selection_rows"]
        assert len(rows) == count * len(plan["styles"]) * len(plan["conditions"])
        assert {(row["seed"], row["style"], row["condition"]) for row in rows} == {
            (seed, style, condition)
            for seed in range(start, start + count)
            for style in plan["styles"]
            for condition in plan["conditions"]
        }

    weights = balanced_weights(
        report["training_rows"],
        plan["condition_weights"],
        plan["tail_loss_fraction"],
    )
    assert report["training_balanced_weight_sum"] == float(weights.sum())
    errors = [row["error_mm"] for row in report["training_rows"]]
    assert report["training_constant_bound_mm"] == float(
        np.quantile(errors, plan["quantile"], method="higher")
    )

    rows = report["selection_rows"]
    candidate = metric_summary(rows, "compact_metric_bound_mm", plan["quantile"])
    prior = metric_summary(rows, "base_metric_bound_mm", plan["quantile"])
    for summary, key in (
        (candidate, "compact_metric_bound_mm"),
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
        rows, "compact_metric_bound_mm", plan["conditions"], plan["tolerance_mm"]
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
            and min(row["compact_metric_bound_mm"] for row in rows)
            >= plan["minimum_bound_mm"],
            "prior_pinball_noninferiority": candidate["mean_pinball_loss"]
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
    assert checks["prior_pinball_noninferiority"]
    assert not checks["prior_median_bound_limit"]
    assert not checks["proxy_utility"]
    assert not checks["proxy_utility_improvement"]
    assert not checks["proxy_condition_utility"]["appearance_shift"]
    assert not checks["proxy_condition_utility_pass"]
    assert not checks_pass(checks)
    assert not report["passed_selection"]
    assert report["model_fits"] == 1 and report["calibration_fits"] == 0
    assert report["optimizer_updates"] == 6250
    assert report["hardware_writes"] == report["physical_movements"] == 0
    assert not report["qualification_installed"]

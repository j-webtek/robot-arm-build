import hashlib
import json
import sys
from pathlib import Path

import torch

AI = Path(__file__).resolve().parents[1]
ROOT = AI.parents[1]
sys.path.insert(0, str(AI))

from evidence_artifacts import verify_frozen_artifacts
from train.train_multitask_upper_tail_head import checks_pass
from train.train_upper_tail_error_head import decision_checks, metric_summary
from vision.evaluate_localized_geometric_risk import ranking
from vision.multitask_error_head import MultiTaskErrorHead


def test_multitask_head_shapes_and_parameter_count():
    head = MultiTaskErrorHead()
    metric, tail = head(torch.zeros((3, 513), dtype=torch.float32))
    assert metric.shape == tail.shape == (3,)
    assert sum(parameter.numel() for parameter in head.parameters()) == 52514


def test_report_recounts_multitask_selection_and_failure():
    plan_path = AI / "train/multitask_upper_tail_head_v1_plan.json"
    plan = json.loads(plan_path.read_text())
    verify_frozen_artifacts(ROOT, plan["file_sha256"])
    report = json.loads((AI / "eval/multitask_upper_tail_head_v1_report.json").read_text())
    checkpoint = AI / "results/multitask_upper_tail_head_v1/model.pt"

    assert report["plan_sha256"] == hashlib.sha256(plan_path.read_bytes()).hexdigest()
    assert report["prior_report_sha256"] == plan["file_sha256"][plan["prior_report"]]
    assert report["checkpoint_sha256"] == hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    assert report["model_parameters"] == 52514
    assert len(report["history"]) == plan["epochs"] == 20
    assert report["positive_weight"] == report["training_negative_images"] / report["training_positive_images"]
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
    candidate = metric_summary(rows, "multitask_bound_mm", plan["quantile"])
    candidate["conditions"] = {
        condition: metric_summary(
            [row for row in rows if row["condition"] == condition],
            "multitask_bound_mm",
            plan["quantile"],
        )
        for condition in plan["conditions"]
    }
    baseline = metric_summary(rows, "constant_bound_mm", plan["quantile"])
    metric_ranking = ranking(
        rows, "multitask_bound_mm", plan["conditions"], plan["tolerance_mm"]
    )
    auxiliary_ranking = ranking(
        rows, "tail_risk_logit", plan["conditions"], plan["tolerance_mm"]
    )
    checks = decision_checks(candidate, baseline, metric_ranking, plan)
    checks.update(
        {
            "finite_bound": candidate["maximum_bound_mm"] <= plan["maximum_bound_mm"]
            and min(row["multitask_bound_mm"] for row in rows)
            >= plan["minimum_bound_mm"],
            "auxiliary_minimum_scene_auc": auxiliary_ranking["scene_auc"]
            >= plan["auxiliary_minimum_scene_auc"],
            "auxiliary_condition_image_auc": {
                condition: value >= plan["auxiliary_minimum_condition_image_auc"]
                for condition, value in auxiliary_ranking["condition_image_auc"].items()
            },
        }
    )
    assert report["candidate_summary"] == candidate
    assert report["constant_summary"] == baseline
    assert report["metric_ranking"] == metric_ranking
    assert report["auxiliary_ranking"] == auxiliary_ranking
    assert report["checks"] == checks
    assert not checks["minimum_scene_auc"]
    assert not checks["auxiliary_minimum_scene_auc"]
    assert not checks["auxiliary_condition_image_auc"]["full"]
    assert not checks_pass(checks)
    assert not report["passed_selection"]
    assert report["model_fits"] == 1 and report["calibration_fits"] == 0
    assert report["optimizer_updates"] == 2500
    assert report["hardware_writes"] == report["physical_movements"] == 0
    assert not report["qualification_installed"]

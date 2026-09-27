import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pytest

AI = Path(__file__).resolve().parents[1]
ROOT = AI.parents[1]
sys.path.insert(0, str(AI))

from evidence_artifacts import verify_frozen_artifacts
from train.compare_backbone_uncertainty import scene_metrics


def test_plan_has_disjoint_grouped_populations_and_fixed_appearance_weight():
    plan = json.loads((AI / "train/appearance_robust_ensemble_v1_plan.json").read_text())
    verify_frozen_artifacts(ROOT, plan["file_sha256"])
    train_start, train_count = plan["training_groups"]
    selection_start, selection_count = plan["selection_groups"]
    assert train_start + train_count <= selection_start
    assert train_count == 2400
    assert selection_count == 400
    assert plan["condition_loss_weights"] == {
        "standard": 1.0,
        "appearance_shift": 2.0,
        "partial": 1.0,
        "full": 1.0,
    }
    assert plan["scope"] == "training_and_selection_only"


def test_report_lineage_population_recount_and_passed_selection():
    plan_path = AI / "train/appearance_robust_ensemble_v1_plan.json"
    plan = json.loads(plan_path.read_text())
    report = json.loads((AI / "eval/appearance_robust_ensemble_v1_report.json").read_text())
    assert report["plan_sha256"] == hashlib.sha256(plan_path.read_bytes()).hexdigest()
    assert report["previous_report_sha256"] == plan["file_sha256"][plan["previous_report"]]
    assert report["training_images"] == 2400 * 2 * 4
    assert report["selection_images"] == 400 * 2 * 4
    assert report["model_parameters"] == {"silu": 172331, "separable": 82763}
    assert set(report["checkpoint_sha256"]) == set(plan["models"])
    assert all(len(value) == 64 for value in report["checkpoint_sha256"].values())
    assert all(len(report["histories"][name]) == plan["epochs"] for name in plan["models"])
    assert report["optimizer_updates"] == 2 * 24 * 150

    rows = report["candidate_rows"]
    expected = {
        (seed, style, condition)
        for seed in range(37002400, 37002800)
        for style in plan["styles"]
        for condition in plan["conditions"]
    }
    assert len(rows) == 3200
    assert {(row["seed"], row["style"], row["condition"]) for row in rows} == expected
    for condition in plan["conditions"]:
        group = [row for row in rows if row["condition"] == condition]
        score = report["scores"]["candidate"][condition]
        assert score["images"] == len(group) == 800
        assert score["mean_mm"] == pytest.approx(np.mean([row["mean_mm"] for row in group]))
        assert score["tail"] == sum(row["maximum_mm"] > 3 for row in group)
        assert score["yaw_p95"] == pytest.approx(np.percentile([row["yaw_degrees"] for row in group], 95))

    disagreement = report["disagreement_rows"]
    ranking = scene_metrics(disagreement, "ensemble_disagreement_mm", plan["retention_fractions"])
    assert report["scene_ranking"] == ranking
    curve = {point["requested_fraction"]: point for point in ranking["retention_curve"]}
    expected_checks = {
        "scene_tail_auc": ranking["tail_auc"] >= plan["minimum_scene_tail_auc"],
        "retention_0_25_relative": curve[0.25]["tail_rate"]
        <= plan["retention_0_25_max_relative"] * ranking["tail_rate"],
        "retention_0_5_relative": curve[0.5]["tail_rate"]
        <= plan["retention_0_5_max_relative"] * ranking["tail_rate"],
        "member_mean_error": {
            name: {
                condition: report["scores"][name][condition]["mean_mm"]
                <= plan["member_max_mean_ratio"]
                * report["scores"]["candidate"][condition]["mean_mm"]
                for condition in plan["conditions"]
            }
            for name in plan["models"]
        },
        "member_appearance_error": {
            name: report["scores"][name]["appearance_shift"]["mean_mm"]
            <= plan["member_appearance_max_mean_ratio"]
            * report["scores"]["candidate"]["appearance_shift"]["mean_mm"]
            for name in plan["models"]
        },
    }
    assert report["checks"] == expected_checks
    assert all(
        value if isinstance(value, bool) else all(value.values())
        for key, value in expected_checks.items()
        if key != "member_mean_error"
    )
    assert all(all(values.values()) for values in expected_checks["member_mean_error"].values())
    assert report["passed_selection"]
    assert report["pose_fits"] == 2
    assert report["calibration_fits"] == 0
    assert report["hardware_writes"] == report["physical_movements"] == 0
    assert not report["qualification_installed"]

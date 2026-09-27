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


def test_plan_freezes_selected_checkpoints_and_fresh_development_only():
    plan = json.loads(
        (AI / "eval/appearance_robust_ensemble_development_v1_plan.json").read_text()
    )
    verify_frozen_artifacts(ROOT, plan["file_sha256"])
    assert plan["scope"] == "development_only"
    assert plan["development_groups"] == [38000000, 1000]
    assert plan["minimum_scene_tail_auc"] == 0.7
    assert set(plan["selected_checkpoints"]) == {"silu", "separable"}
    for checkpoint in plan["selected_checkpoints"].values():
        assert plan["file_sha256"][checkpoint] == hashlib.sha256(
            (ROOT / checkpoint).read_bytes()
        ).hexdigest()


def test_report_population_recount_and_passed_development_rule():
    plan_path = AI / "eval/appearance_robust_ensemble_development_v1_plan.json"
    plan = json.loads(plan_path.read_text())
    report = json.loads(
        (AI / "eval/appearance_robust_ensemble_development_v1_report.json").read_text()
    )
    assert report["plan_sha256"] == hashlib.sha256(plan_path.read_bytes()).hexdigest()
    assert report["selection_report_sha256"] == plan["file_sha256"][plan["selection_report"]]
    assert report["development_images"] == 1000 * 2 * 4
    rows = report["candidate_rows"]
    expected = {
        (seed, style, condition)
        for seed in range(38000000, 38001000)
        for style in plan["styles"]
        for condition in plan["conditions"]
    }
    assert len(rows) == 8000
    assert {(row["seed"], row["style"], row["condition"]) for row in rows} == expected
    for condition in plan["conditions"]:
        group = [row for row in rows if row["condition"] == condition]
        score = report["scores"]["candidate"][condition]
        assert score["images"] == len(group) == 2000
        assert score["mean_mm"] == pytest.approx(np.mean([row["mean_mm"] for row in group]))
        assert score["tail"] == sum(row["maximum_mm"] > 3 for row in group)
        assert score["yaw_p95"] == pytest.approx(np.percentile([row["yaw_degrees"] for row in group], 95))

    disagreement = report["disagreement_rows"]
    assert len(disagreement) == 8000
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
            for name in plan["selected_checkpoints"]
        },
        "member_appearance_error": {
            name: report["scores"][name]["appearance_shift"]["mean_mm"]
            <= plan["member_appearance_max_mean_ratio"]
            * report["scores"]["candidate"]["appearance_shift"]["mean_mm"]
            for name in plan["selected_checkpoints"]
        },
    }
    assert report["checks"] == expected_checks
    assert all(
        [
            expected_checks["scene_tail_auc"],
            expected_checks["retention_0_25_relative"],
            expected_checks["retention_0_5_relative"],
            all(all(values.values()) for values in expected_checks["member_mean_error"].values()),
            all(expected_checks["member_appearance_error"].values()),
        ]
    )
    assert report["passed_development"]
    assert report["new_fits"] == report["optimizer_updates"] == report["calibration_fits"] == 0
    assert report["hardware_writes"] == report["physical_movements"] == 0
    assert not report["qualification_installed"]

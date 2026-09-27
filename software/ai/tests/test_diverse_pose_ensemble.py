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
from train.compare_backbone_uncertainty import scene_metrics
from train.train_diverse_pose_ensemble import pairwise_disagreement
from vision.diverse_pose_models import MODELS
from vision.synthetic_keyboard import catalog_for_workspace


def test_diverse_models_are_compact_and_reject_invalid_inputs():
    expected_parameters = {"silu": 172331, "separable": 82763}
    valid = torch.zeros((2, 3, 96, 128), dtype=torch.float32)
    for name, constructor in MODELS.items():
        model = constructor()
        assert sum(parameter.numel() for parameter in model.parameters()) == expected_parameters[name]
        assert model(valid).shape == (2, 3)
        with pytest.raises(ValueError):
            model(torch.zeros((2, 3, 95, 128), dtype=torch.float32))
        with pytest.raises(ValueError):
            model(valid.double())


def test_pairwise_disagreement_is_zero_and_tracks_translation():
    targets = list(catalog_for_workspace(ROOT).keyboard_targets.values())
    equal = {
        "candidate": np.zeros((1, 3), dtype=np.float64),
        "silu": np.zeros((1, 3), dtype=np.float64),
        "separable": np.zeros((1, 3), dtype=np.float64),
    }
    assert pairwise_disagreement(equal, 0, targets) == pytest.approx(0.0, abs=1e-12)
    shifted = dict(equal)
    shifted["separable"] = np.asarray([[1 / 30, 0.0, 0.0]], dtype=np.float64)
    assert pairwise_disagreement(shifted, 0, targets) == pytest.approx(1.0, abs=1e-12)


def test_report_lineage_population_recount_and_failed_rule():
    plan_path = AI / "train/diverse_pose_ensemble_v1_plan.json"
    plan = json.loads(plan_path.read_text())
    verify_frozen_artifacts(ROOT, plan["file_sha256"])
    report = json.loads((AI / "eval/diverse_pose_ensemble_v1_report.json").read_text())
    assert report["plan_sha256"] == hashlib.sha256(plan_path.read_bytes()).hexdigest()
    assert report["training_images"] == 1600 * 2 * 4
    assert report["development_images"] == 400 * 2 * 4
    assert report["model_parameters"] == {"silu": 172331, "separable": 82763}
    assert set(report["checkpoint_sha256"]) == set(plan["models"])
    assert all(len(value) == 64 for value in report["checkpoint_sha256"].values())
    assert all(len(report["histories"][name]) == plan["epochs"] for name in plan["models"])
    assert report["optimizer_updates"] == 2 * 12 * 100

    rows = report["candidate_rows"]
    expected = {
        (seed, style, condition)
        for seed in range(36001600, 36002000)
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
    assert len(disagreement) == 3200
    assert all(row["ensemble_disagreement_mm"] >= 0 for row in disagreement)
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
    }
    assert report["checks"] == expected_checks
    assert not report["passed"]
    assert report["pose_fits"] == 2
    assert report["calibration_fits"] == 0
    assert report["hardware_writes"] == report["physical_movements"] == 0
    assert not report["qualification_installed"]

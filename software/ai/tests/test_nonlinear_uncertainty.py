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
from vision.nonlinear_uncertainty import (
    NonlinearUncertaintyHead,
    fit_head,
    predict_head,
)


def test_head_shape_parameter_count_and_input_validation():
    import torch

    head = NonlinearUncertaintyHead()
    assert sum(parameter.numel() for parameter in head.parameters()) == 16689
    assert head(torch.zeros((3, 512), dtype=torch.float32)).shape == (3,)
    with pytest.raises(ValueError):
        head(torch.zeros((3, 56), dtype=torch.float32))
    with pytest.raises(ValueError):
        head(torch.zeros((3, 512), dtype=torch.float64))


def test_small_fit_is_deterministic_and_training_only():
    rng = np.random.default_rng(27)
    features = rng.normal(size=(96, 512))
    errors = np.abs(rng.normal(size=96))
    options = dict(
        seed=42,
        epochs=2,
        batch_size=32,
        learning_rate=0.001,
        weight_decay=0.0001,
    )
    first = fit_head(features[:80], errors[:80], **options)
    features[80:] = 1e6
    errors[80:] = 1e6
    second = fit_head(features[:80], errors[:80], **options)
    assert first == second
    assert first["optimizer_updates"] == 6
    prediction = predict_head(first, features[80:])
    assert np.all(prediction >= 0.1) and np.all(prediction <= 20.0)
    with pytest.raises(ValueError):
        fit_head(features[:, :56], errors, **options)
    with pytest.raises(ValueError):
        predict_head(first, np.full((1, 512), np.nan))


def test_report_population_folds_metrics_and_failed_decision():
    path = AI / "train/nonlinear_uncertainty_v1_plan.json"
    plan = json.loads(path.read_text())
    verify_frozen_artifacts(ROOT, plan["file_sha256"])
    report = json.loads((AI / "eval/nonlinear_uncertainty_v1_report.json").read_text())
    source = json.loads((ROOT / plan["source_report"]).read_text())
    assert report["plan_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert report["source_report_sha256"] == plan["file_sha256"][plan["source_report"]]
    assert report["pixels_sha256"] == source["pixel_sha256"]
    assert report["head_parameters"] == 16689
    rows = report["rows"]
    expected = {
        (seed, style, condition)
        for seed in range(33000000, 33000600)
        for style in plan["styles"]
        for condition in plan["conditions"]
    }
    assert len(rows) == 4800
    assert {(row["seed"], row["style"], row["condition"]) for row in rows} == expected
    validation_seeds = []
    for fold, fit_record in enumerate(report["fold_fits"]):
        validation_seeds.extend(fit_record["validation_seeds"])
        assert fit_record["training_rows"] == 3840
        assert fit_record["validation_rows"] == 960
        assert len(fit_record["validation_seeds"]) == 120
        fit = fit_record["fit"]
        assert fit["seed"] == plan["seed"] + fold
        assert fit["epochs"] == plan["epochs"]
        assert fit["optimizer_updates"] == 1800
        assert len(fit["mean"]) == len(fit["scale"]) == 512
        assert min(fit["scale"]) > 0
    assert sorted(validation_seeds) == list(range(33000000, 33000600))
    for condition in plan["conditions"]:
        group = [row for row in rows if row["condition"] == condition]
        target = np.log([row["error_mm"] + 0.1 for row in group])
        expected_summary = {
            "images": 1200,
            "nonlinear_log_mse": float(
                np.mean((np.log([row["nonlinear_scale_mm"] for row in group]) - target) ** 2)
            ),
            "image_statistic_log_mse": float(
                np.mean((np.log([row["scale_mm"] for row in group]) - target) ** 2)
            ),
        }
        assert report["summaries"][condition] == expected_summary
    fractions = plan["retention_fractions"]
    assert report["scene_ranking"]["nonlinear"] == scene_metrics(
        rows, "nonlinear_scale_mm", fractions
    )
    assert report["scene_ranking"]["image_statistic"] == scene_metrics(
        rows, "scale_mm", fractions
    )
    checks = {
        "condition_mse": {
            condition: values["nonlinear_log_mse"] < values["image_statistic_log_mse"]
            for condition, values in report["summaries"].items()
        },
        "scene_tail_auc": report["scene_ranking"]["nonlinear"]["tail_auc"]
        > report["scene_ranking"]["image_statistic"]["tail_auc"],
    }
    assert report["checks"] == checks
    assert report["passed"] == (all(checks["condition_mse"].values()) and checks["scene_tail_auc"])
    assert not report["passed"]
    assert report["uncertainty_fits"] == 5
    assert report["pose_fits"] == report["calibration_fits"] == report["new_images"] == 0
    assert report["hardware_writes"] == report["physical_movements"] == 0
    assert not report["qualification_installed"]

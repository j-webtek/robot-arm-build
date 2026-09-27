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
from train.compare_backbone_uncertainty import fit_scale, predict_scale, scene_metrics


def test_fit_uses_only_supplied_rows_and_rejects_bad_inputs():
    rng = np.random.default_rng(17)
    features = rng.normal(size=(20, 512))
    errors = np.linspace(0, 4, 20)
    fit = fit_scale(features[:16], errors[:16], 1.0)
    features[16:] = 1e6
    errors[16:] = 1e6
    assert fit == fit_scale(features[:16], errors[:16], 1.0)
    assert np.allclose(fit["mean"], features[:16].mean(0))
    assert fit["normal_equation_max_residual"] < 1e-10
    prediction = predict_scale(fit, features[16:])
    assert np.all(prediction >= 0.1) and np.all(prediction <= 20.0)
    with pytest.raises(ValueError):
        fit_scale(features[:, :56], errors, 1.0)
    with pytest.raises(ValueError):
        predict_scale(fit, np.full((1, 512), np.nan))


def test_scene_metric_uses_maximum_score_and_error_per_scene():
    rows = [
        {"seed": 1, "score": 1.0, "error_mm": 5.0},
        {"seed": 1, "score": 4.0, "error_mm": 1.0},
        {"seed": 2, "score": 2.0, "error_mm": 2.0},
    ]
    summary = scene_metrics(rows, "score", [0.5, 1.0])
    assert summary["rows"] == 2
    assert summary["tail_count"] == 1
    assert summary["tail_auc"] == 1.0


def test_report_lineage_folds_and_acceptance_recount():
    path = AI / "train/backbone_uncertainty_v1_plan.json"
    plan = json.loads(path.read_text())
    verify_frozen_artifacts(ROOT, plan["file_sha256"])
    report = json.loads((AI / "eval/backbone_uncertainty_v1_report.json").read_text())
    assert report["plan_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    source = json.loads((ROOT / plan["source_report"]).read_text())
    assert report["source_report_sha256"] == plan["file_sha256"][plan["source_report"]]
    assert report["pixels_sha256"] == source["pixel_sha256"]
    rows = report["rows"]
    assert len(rows) == 4800
    expected = {
        (seed, style, condition)
        for seed in range(33000000, 33000600)
        for style in plan["styles"]
        for condition in plan["conditions"]
    }
    assert {(r["seed"], r["style"], r["condition"]) for r in rows} == expected
    validations = []
    for fold in report["fold_fits"]:
        validations.extend(fold["validation_seeds"])
        assert fold["training_rows"] == 3840
        assert fold["validation_rows"] == 960
        assert len(fold["validation_seeds"]) == 120
        assert fold["fit"]["alpha"] == 1.0
        assert len(fold["fit"]["weights"]) == 512
        assert min(fold["fit"]["scale"]) > 0
        assert fold["fit"]["normal_equation_max_residual"] < 1e-10
    assert sorted(validations) == list(range(33000000, 33000600))
    for condition in plan["conditions"]:
        group = [r for r in rows if r["condition"] == condition]
        target = np.log([r["error_mm"] + 0.1 for r in group])
        expected_summary = {
            "images": 1200,
            "backbone_log_mse": float(
                np.mean((np.log([r["backbone_scale_mm"] for r in group]) - target) ** 2)
            ),
            "image_statistic_log_mse": float(
                np.mean((np.log([r["scale_mm"] for r in group]) - target) ** 2)
            ),
        }
        assert report["summaries"][condition] == expected_summary
    fractions = plan["retention_fractions"]
    assert report["scene_ranking"]["backbone"] == scene_metrics(
        rows, "backbone_scale_mm", fractions
    )
    assert report["scene_ranking"]["image_statistic"] == scene_metrics(
        rows, "scale_mm", fractions
    )
    checks = {
        "condition_mse": {
            condition: values["backbone_log_mse"] < values["image_statistic_log_mse"]
            for condition, values in report["summaries"].items()
        },
        "scene_tail_auc": report["scene_ranking"]["backbone"]["tail_auc"]
        > report["scene_ranking"]["image_statistic"]["tail_auc"],
    }
    assert report["checks"] == checks
    assert report["passed"] == (all(checks["condition_mse"].values()) and checks["scene_tail_auc"])
    assert not report["passed"]
    assert report["uncertainty_fits"] == 5
    assert report["pose_fits"] == report["calibration_fits"] == report["new_images"] == 0
    assert report["hardware_writes"] == report["physical_movements"] == 0
    assert not report["qualification_installed"]

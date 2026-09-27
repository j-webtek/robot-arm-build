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
from vision.tail_risk_classifier import TailRiskClassifier, fit_classifier, predict_risk


def test_classifier_shape_parameter_count_and_inputs():
    import torch

    model = TailRiskClassifier()
    assert sum(parameter.numel() for parameter in model.parameters()) == 16689
    assert model(torch.zeros((2, 512), dtype=torch.float32)).shape == (2,)
    with pytest.raises(ValueError):
        model(torch.zeros((2, 56), dtype=torch.float32))
    with pytest.raises(ValueError):
        model(torch.zeros((2, 512), dtype=torch.float64))


def test_small_classifier_fit_is_deterministic_and_bounded():
    rng = np.random.default_rng(31)
    features = rng.normal(size=(96, 512))
    labels = np.asarray([0, 1] * 48, dtype=float)
    options = dict(seed=7, epochs=2, batch_size=32, learning_rate=0.001, weight_decay=0.0001)
    first = fit_classifier(features[:80], labels[:80], **options)
    features[80:] = 1e6
    labels[80:] = 1
    assert first == fit_classifier(features[:80], labels[:80], **options)
    assert first["positive_weight"] == 1.0
    assert first["optimizer_updates"] == 6
    prediction = predict_risk(first, features[80:])
    assert np.all(prediction >= 0) and np.all(prediction <= 1)
    with pytest.raises(ValueError):
        fit_classifier(features[:, :56], labels, **options)
    with pytest.raises(ValueError):
        fit_classifier(features, np.zeros(96), **options)


def test_report_grouping_metrics_and_failed_rule():
    path = AI / "train/tail_risk_classifier_v1_plan.json"
    plan = json.loads(path.read_text())
    verify_frozen_artifacts(ROOT, plan["file_sha256"])
    report = json.loads((AI / "eval/tail_risk_classifier_v1_report.json").read_text())
    source = json.loads((ROOT / plan["source_report"]).read_text())
    assert report["plan_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert report["source_report_sha256"] == plan["file_sha256"][plan["source_report"]]
    assert report["pixels_sha256"] == source["pixels_sha256"]
    assert report["descriptors_sha256"] == source["descriptors_sha256"]
    assert report["head_parameters"] == 16689
    assert report["scene_positive_count"] == 49
    assert report["scene_negative_count"] == 551
    rows = report["rows"]
    assert len(rows) == 4800
    validation = []
    positive_validation = 0
    for fold, record in enumerate(report["fold_fits"]):
        validation.extend(record["validation_seeds"])
        positive_validation += record["validation_positive_scenes"]
        assert record["training_rows"] == 3840
        assert record["validation_rows"] == 960
        assert record["training_positive_scenes"] + record["validation_positive_scenes"] == 49
        fit = record["fit"]
        assert fit["seed"] == plan["seed"] + fold
        assert fit["optimizer_updates"] == 1800
        assert fit["positive_weight"] == pytest.approx(
            (480 - record["training_positive_scenes"]) / record["training_positive_scenes"]
        )
    assert sorted(validation) == list(range(33000000, 33000600))
    assert positive_validation == 49
    fractions = plan["retention_fractions"]
    assert report["scene_ranking"]["classifier"] == scene_metrics(rows, "tail_risk", fractions)
    assert report["scene_ranking"]["nonlinear_regression"] == scene_metrics(
        rows, "nonlinear_scale_mm", fractions
    )
    classifier = {p["requested_fraction"]: p for p in report["scene_ranking"]["classifier"]["retention_curve"]}
    reference = {p["requested_fraction"]: p for p in report["scene_ranking"]["nonlinear_regression"]["retention_curve"]}
    checks = {
        "scene_tail_auc": report["scene_ranking"]["classifier"]["tail_auc"]
        > report["scene_ranking"]["nonlinear_regression"]["tail_auc"],
        "retention_tail_rate_0_25": classifier[0.25]["tail_rate"] < reference[0.25]["tail_rate"],
        "retention_tail_rate_0_5": classifier[0.5]["tail_rate"] < reference[0.5]["tail_rate"],
    }
    assert report["checks"] == checks
    assert report["passed"] == all(checks.values())
    assert not report["passed"]
    assert report["classifier_fits"] == 5
    assert report["pose_fits"] == report["calibration_fits"] == report["new_images"] == 0
    assert report["hardware_writes"] == report["physical_movements"] == 0
    assert not report["qualification_installed"]

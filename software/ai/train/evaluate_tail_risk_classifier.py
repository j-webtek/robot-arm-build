"""Fixed grouped scene-tail classification feasibility study."""

import hashlib
import json
import sys
from pathlib import Path

AI = Path(__file__).resolve().parents[1]
ROOT = AI.parents[1]
sys.path[:0] = [str(AI), str(AI.parent / "src")]

import numpy as np
import torch
from torch.nn import functional as F

from train.compare_backbone_uncertainty import scene_metrics
from vision.audit_scene_splits import group_folds
from vision.evaluate_dark_only_normalization import normalize
from vision.landmark_occlusions import render_controlled
from vision.linear_residual_pose import LinearResidualPoseNet
from vision.synthetic_keyboard import catalog_for_workspace
from vision.tail_risk_classifier import TailRiskClassifier, fit_classifier, predict_risk


def run():
    path = AI / "train/tail_risk_classifier_v1_plan.json"
    plan = json.loads(path.read_text())
    for name, digest in plan["file_sha256"].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise ValueError("source mismatch: " + name)
    out = AI / "eval/tail_risk_classifier_v1_report.json"
    if out.exists():
        raise FileExistsError(out)

    source = json.loads((ROOT / plan["source_report"]).read_text())
    rows = source["rows"]
    if len(rows) != 4800:
        raise ValueError("unexpected source population")
    start, count = plan["groups"]
    scene_labels = {
        seed: float(max(row["error_mm"] for row in rows if row["seed"] == seed) > plan["tail_mm"])
        for seed in range(start, start + count)
    }
    if sum(scene_labels.values()) != 49:
        raise ValueError("unexpected positive-scene count")
    labels = np.asarray([scene_labels[row["seed"]] for row in rows])

    pose = LinearResidualPoseNet.from_export(
        torch.load(ROOT / plan["artifact"], weights_only=True, map_location="cpu")
    )
    torch.set_num_threads(4)
    catalog = catalog_for_workspace(ROOT)
    pixels = []
    ordered = []
    for seed in range(start, start + count):
        for style in plan["styles"]:
            for condition in plan["conditions"]:
                image, _, _ = render_controlled(seed, catalog, condition, style)
                image, _ = normalize(image)
                pixels.append(np.asarray(image.resize((128, 96))).transpose(2, 0, 1).copy())
                ordered.append((seed, style, condition))
    if ordered != [(row["seed"], row["style"], row["condition"]) for row in rows]:
        raise ValueError("source row order mismatch")
    pixels = np.stack(pixels)
    if hashlib.sha256(pixels.tobytes()).hexdigest() != source["pixels_sha256"]:
        raise ValueError("rendered pixels differ from source evidence")
    descriptors = []
    with torch.no_grad():
        for batch in torch.from_numpy(pixels).split(64):
            feature = pose.backbone.features[:4](batch.float() / 255)
            descriptors.append(F.adaptive_avg_pool2d(feature, (4, 4)).flatten(1))
    descriptors = torch.cat(descriptors).numpy()
    if hashlib.sha256(descriptors.tobytes()).hexdigest() != source["descriptors_sha256"]:
        raise ValueError("descriptors differ from frozen nonlinear evidence")

    predictions = np.empty(len(rows))
    seen = np.zeros(len(rows), dtype=int)
    fits = []
    folds = group_folds(range(start, start + count))
    for fold, validation_seeds in enumerate(folds):
        validation = np.asarray([row["seed"] in validation_seeds for row in rows])
        fit = fit_classifier(
            descriptors[~validation],
            labels[~validation],
            seed=plan["seed"] + fold,
            epochs=plan["epochs"],
            batch_size=plan["batch_size"],
            learning_rate=plan["learning_rate"],
            weight_decay=plan["weight_decay"],
        )
        predictions[validation] = predict_risk(fit, descriptors[validation])
        seen[validation] += 1
        fits.append(
            {
                "fold": fold,
                "training_rows": int((~validation).sum()),
                "validation_rows": int(validation.sum()),
                "training_positive_scenes": int(sum(scene_labels[seed] for seed in scene_labels if seed not in validation_seeds)),
                "validation_positive_scenes": int(sum(scene_labels[seed] for seed in validation_seeds)),
                "validation_seeds": validation_seeds,
                "fit": fit,
            }
        )
        print("fold", fold, "training weighted BCE", fit["training_weighted_bce"], flush=True)
    if not np.all(seen == 1):
        raise ValueError("incomplete out-of-fold predictions")

    result_rows = [dict(row, tail_risk=float(value)) for row, value in zip(rows, predictions)]
    ranking = {
        "classifier": scene_metrics(result_rows, "tail_risk", plan["retention_fractions"]),
        "nonlinear_regression": scene_metrics(result_rows, "nonlinear_scale_mm", plan["retention_fractions"]),
    }
    classifier_curve = {point["requested_fraction"]: point for point in ranking["classifier"]["retention_curve"]}
    reference_curve = {point["requested_fraction"]: point for point in ranking["nonlinear_regression"]["retention_curve"]}
    checks = {
        "scene_tail_auc": ranking["classifier"]["tail_auc"] > ranking["nonlinear_regression"]["tail_auc"],
        "retention_tail_rate_0_25": classifier_curve[0.25]["tail_rate"] < reference_curve[0.25]["tail_rate"],
        "retention_tail_rate_0_5": classifier_curve[0.5]["tail_rate"] < reference_curve[0.5]["tail_rate"],
    }
    passed = all(checks.values())
    result = {
        "plan_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "source_report_sha256": plan["file_sha256"][plan["source_report"]],
        "pixels_sha256": source["pixels_sha256"],
        "descriptors_sha256": source["descriptors_sha256"],
        "predictions_sha256": hashlib.sha256(predictions.tobytes()).hexdigest(),
        "head_parameters": sum(parameter.numel() for parameter in TailRiskClassifier().parameters()),
        "scene_positive_count": int(sum(scene_labels.values())),
        "scene_negative_count": count - int(sum(scene_labels.values())),
        "fold_fits": fits,
        "rows": result_rows,
        "scene_ranking": ranking,
        "checks": checks,
        "passed": passed,
        "classifier_fits": 5,
        "pose_fits": 0,
        "calibration_fits": 0,
        "new_images": 0,
        "hardware_writes": 0,
        "physical_movements": 0,
        "qualification_installed": False,
        "limitations": [
            "Scene label is copied to all eight variants for class-balanced training; variants are correlated.",
            "One fixed architecture and schedule, no sweep, early stopping, or threshold selection.",
            "Out-of-fold uncertainty-training evidence only; no independent confirmation or calibration.",
            "Classifier probabilities are uncalibrated risk ranks, not error bounds or physical confidence.",
            "Passing would permit only a separately specified calibration and fresh confirmation chain.",
        ],
    }
    out.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"scene_ranking": ranking, "checks": checks, "passed": passed}, indent=2))


if __name__ == "__main__":
    run()

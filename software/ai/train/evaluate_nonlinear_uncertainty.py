"""Fixed nonlinear uncertainty feasibility on grouped training-only scenes."""

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
from vision.nonlinear_uncertainty import fit_head, predict_head
from vision.synthetic_keyboard import catalog_for_workspace


def run():
    path = AI / "train/nonlinear_uncertainty_v1_plan.json"
    plan = json.loads(path.read_text())
    for name, digest in plan["file_sha256"].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise ValueError("source mismatch: " + name)
    out = AI / "eval/nonlinear_uncertainty_v1_report.json"
    if out.exists():
        raise FileExistsError(out)

    source = json.loads((ROOT / plan["source_report"]).read_text())
    rows = source["rows"]
    if len(rows) != 4800:
        raise ValueError("unexpected source population")
    pose = LinearResidualPoseNet.from_export(
        torch.load(ROOT / plan["artifact"], weights_only=True, map_location="cpu")
    )
    torch.set_num_threads(4)
    catalog = catalog_for_workspace(ROOT)
    pixels = []
    ordered = []
    start, count = plan["groups"]
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
    if hashlib.sha256(pixels.tobytes()).hexdigest() != source["pixel_sha256"]:
        raise ValueError("rendered pixels differ from source evidence")

    descriptors = []
    with torch.no_grad():
        for batch in torch.from_numpy(pixels).split(64):
            feature = pose.backbone.features[:4](batch.float() / 255)
            descriptors.append(F.adaptive_avg_pool2d(feature, (4, 4)).flatten(1))
    descriptors = torch.cat(descriptors).numpy()
    errors = np.asarray([row["error_mm"] for row in rows])
    predictions = np.empty(len(rows))
    seen = np.zeros(len(rows), dtype=int)
    fits = []
    folds = group_folds(range(start, start + count))
    for fold, validation_seeds in enumerate(folds):
        validation = np.asarray([row["seed"] in validation_seeds for row in rows])
        fit = fit_head(
            descriptors[~validation],
            errors[~validation],
            seed=plan["seed"] + fold,
            epochs=plan["epochs"],
            batch_size=plan["batch_size"],
            learning_rate=plan["learning_rate"],
            weight_decay=plan["weight_decay"],
        )
        predictions[validation] = predict_head(fit, descriptors[validation])
        seen[validation] += 1
        fits.append(
            {
                "fold": fold,
                "training_rows": int((~validation).sum()),
                "validation_rows": int(validation.sum()),
                "validation_seeds": validation_seeds,
                "fit": fit,
            }
        )
        print("fold", fold, "training loss", fit["training_log_mse"], flush=True)
    if not np.all(seen == 1):
        raise ValueError("incomplete out-of-fold predictions")

    result_rows = [dict(row, nonlinear_scale_mm=float(value)) for row, value in zip(rows, predictions)]
    summaries = {}
    for condition in plan["conditions"]:
        group = [row for row in result_rows if row["condition"] == condition]
        target = np.log([row["error_mm"] + 0.1 for row in group])
        summaries[condition] = {
            "images": len(group),
            "nonlinear_log_mse": float(
                np.mean((np.log([row["nonlinear_scale_mm"] for row in group]) - target) ** 2)
            ),
            "image_statistic_log_mse": float(
                np.mean((np.log([row["scale_mm"] for row in group]) - target) ** 2)
            ),
        }
    ranking = {
        "nonlinear": scene_metrics(result_rows, "nonlinear_scale_mm", plan["retention_fractions"]),
        "image_statistic": scene_metrics(result_rows, "scale_mm", plan["retention_fractions"]),
    }
    checks = {
        "condition_mse": {
            name: summary["nonlinear_log_mse"] < summary["image_statistic_log_mse"]
            for name, summary in summaries.items()
        },
        "scene_tail_auc": ranking["nonlinear"]["tail_auc"] > ranking["image_statistic"]["tail_auc"],
    }
    passed = all(checks["condition_mse"].values()) and checks["scene_tail_auc"]
    result = {
        "plan_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "source_report_sha256": plan["file_sha256"][plan["source_report"]],
        "pixels_sha256": source["pixel_sha256"],
        "descriptors_sha256": hashlib.sha256(descriptors.tobytes()).hexdigest(),
        "predictions_sha256": hashlib.sha256(predictions.tobytes()).hexdigest(),
        "head_parameters": sum(parameter.numel() for parameter in __import__("vision.nonlinear_uncertainty", fromlist=["NonlinearUncertaintyHead"]).NonlinearUncertaintyHead().parameters()),
        "fold_fits": fits,
        "rows": result_rows,
        "summaries": summaries,
        "scene_ranking": ranking,
        "checks": checks,
        "passed": passed,
        "uncertainty_fits": 5,
        "pose_fits": 0,
        "calibration_fits": 0,
        "new_images": 0,
        "hardware_writes": 0,
        "physical_movements": 0,
        "qualification_installed": False,
        "limitations": [
            "One fixed nonlinear architecture and optimizer schedule; no sweep or early stopping.",
            "Reuses grouped 33M uncertainty-training evidence; no fresh confirmation claim.",
            "Pose model is frozen, but uncertainty labels use synthetic truth.",
            "Passing would permit only a later full fit and separately frozen calibration experiment.",
            "No threshold selection, runtime installation, or physical-camera qualification.",
        ],
    }
    out.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"summaries": summaries, "scene_auc": {name: value["tail_auc"] for name, value in ranking.items()}, "checks": checks, "passed": passed}, indent=2))


if __name__ == "__main__":
    run()

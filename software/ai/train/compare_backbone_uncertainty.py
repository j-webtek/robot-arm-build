"""Grouped training-only comparison of frozen backbone and image statistics."""

import hashlib
import json
import math
import sys
from pathlib import Path

AI = Path(__file__).resolve().parents[1]
ROOT = AI.parents[1]
sys.path[:0] = [str(AI), str(AI.parent / "src")]

import numpy as np
import torch
from torch.nn import functional as F

from vision.audit_scale_ranking import metrics
from vision.audit_scene_splits import group_folds
from vision.evaluate_dark_only_normalization import normalize
from vision.landmark_occlusions import render_controlled
from vision.linear_residual_pose import LinearResidualPoseNet
from vision.synthetic_keyboard import catalog_for_workspace


def fit_scale(features, errors, alpha):
    x = np.asarray(features, dtype=np.float64)
    error = np.asarray(errors, dtype=np.float64)
    if (
        x.ndim != 2
        or x.shape[1] != 512
        or error.shape != (len(x),)
        or len(x) < 2
        or not np.isfinite(x).all()
        or not np.isfinite(error).all()
        or np.any(error < 0)
        or not math.isfinite(alpha)
        or alpha <= 0
    ):
        raise ValueError("invalid scale-fit inputs")
    mean = x.mean(0)
    std = x.std(0)
    scale = np.where(std < 1e-8, 1.0, std)
    z = (x - mean) / scale
    target = np.log(error + 0.1)
    intercept = float(target.mean())
    matrix = z.T @ z / len(z) + alpha * np.eye(x.shape[1])
    rhs = z.T @ (target - intercept) / len(z)
    weights = np.linalg.solve(matrix, rhs)
    return {
        "mean": mean.tolist(),
        "scale": scale.tolist(),
        "weights": weights.tolist(),
        "intercept": intercept,
        "alpha": alpha,
        "normal_equation_max_residual": float(np.max(np.abs(matrix @ weights - rhs))),
    }


def predict_scale(fit, features):
    x = np.asarray(features, dtype=np.float64)
    if x.ndim != 2 or x.shape[1] != 512 or not np.isfinite(x).all():
        raise ValueError("invalid inference features")
    value = (
        (x - np.asarray(fit["mean"])) / np.asarray(fit["scale"])
    ) @ np.asarray(fit["weights"]) + fit["intercept"]
    return np.exp(np.clip(value, np.log(0.1), np.log(20.0)))


def scene_metrics(rows, score_key, fractions):
    scenes = []
    for seed in sorted({row["seed"] for row in rows}):
        group = [row for row in rows if row["seed"] == seed]
        scenes.append(
            (
                max(row[score_key] for row in group),
                max(row["error_mm"] for row in group),
            )
        )
    return metrics(
        [value[0] for value in scenes],
        [value[1] for value in scenes],
        fractions,
    )


def run():
    path = AI / "train/backbone_uncertainty_v1_plan.json"
    plan = json.loads(path.read_text())
    for name, digest in plan["file_sha256"].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise ValueError("source mismatch: " + name)
    out = AI / "eval/backbone_uncertainty_v1_report.json"
    if out.exists():
        raise FileExistsError(out)

    source = json.loads((ROOT / plan["source_report"]).read_text())
    rows = source["rows"]
    if len(rows) != 4800:
        raise ValueError("unexpected source population")
    model = LinearResidualPoseNet.from_export(
        torch.load(ROOT / plan["artifact"], weights_only=True, map_location="cpu")
    )
    torch.set_num_threads(4)
    catalog = catalog_for_workspace(ROOT)
    pixels = []
    ordered = []
    for seed in range(plan["groups"][0], plan["groups"][0] + plan["groups"][1]):
        for style in plan["styles"]:
            for condition in plan["conditions"]:
                image, _, _ = render_controlled(seed, catalog, condition, style)
                image, _ = normalize(image)
                pixels.append(
                    np.asarray(image.resize((128, 96)))
                    .transpose(2, 0, 1)
                    .copy()
                )
                ordered.append((seed, style, condition))
    if ordered != [(r["seed"], r["style"], r["condition"]) for r in rows]:
        raise ValueError("source row order mismatch")
    pixels = np.stack(pixels)
    if hashlib.sha256(pixels.tobytes()).hexdigest() != source["pixel_sha256"]:
        raise ValueError("rendered pixels differ from source evidence")

    descriptors = []
    with torch.no_grad():
        for batch in torch.from_numpy(pixels).split(64):
            feature = model.backbone.features[:4](batch.float() / 255)
            descriptors.append(F.adaptive_avg_pool2d(feature, (4, 4)).flatten(1))
    descriptors = torch.cat(descriptors).numpy()
    errors = np.asarray([row["error_mm"] for row in rows])
    predictions = np.empty(len(rows))
    seen = np.zeros(len(rows), dtype=int)
    fits = []
    folds = group_folds(range(plan["groups"][0], plan["groups"][0] + plan["groups"][1]))
    for index, validation_seeds in enumerate(folds):
        validation = np.asarray([row["seed"] in validation_seeds for row in rows])
        fit = fit_scale(descriptors[~validation], errors[~validation], plan["alpha"])
        predictions[validation] = predict_scale(fit, descriptors[validation])
        seen[validation] += 1
        fits.append(
            {
                "fold": index,
                "training_rows": int((~validation).sum()),
                "validation_rows": int(validation.sum()),
                "validation_seeds": validation_seeds,
                "fit": fit,
            }
        )
    if not np.all(seen == 1):
        raise ValueError("incomplete out-of-fold predictions")

    result_rows = [dict(row, backbone_scale_mm=float(value)) for row, value in zip(rows, predictions)]
    summaries = {}
    for condition in plan["conditions"]:
        group = [row for row in result_rows if row["condition"] == condition]
        target = np.log([row["error_mm"] + 0.1 for row in group])
        summaries[condition] = {
            "images": len(group),
            "backbone_log_mse": float(
                np.mean((np.log([row["backbone_scale_mm"] for row in group]) - target) ** 2)
            ),
            "image_statistic_log_mse": float(
                np.mean((np.log([row["scale_mm"] for row in group]) - target) ** 2)
            ),
        }
    ranking = {
        "backbone": scene_metrics(result_rows, "backbone_scale_mm", plan["retention_fractions"]),
        "image_statistic": scene_metrics(result_rows, "scale_mm", plan["retention_fractions"]),
    }
    checks = {
        "condition_mse": {
            name: summary["backbone_log_mse"] < summary["image_statistic_log_mse"]
            for name, summary in summaries.items()
        },
        "scene_tail_auc": ranking["backbone"]["tail_auc"] > ranking["image_statistic"]["tail_auc"],
    }
    passed = all(checks["condition_mse"].values()) and checks["scene_tail_auc"]
    result = {
        "plan_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "source_report_sha256": plan["file_sha256"][plan["source_report"]],
        "pixels_sha256": source["pixel_sha256"],
        "descriptors_sha256": hashlib.sha256(descriptors.tobytes()).hexdigest(),
        "predictions_sha256": hashlib.sha256(predictions.tobytes()).hexdigest(),
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
            "Re-renders the same 33M uncertainty-training scenes; no new confirmation claim.",
            "Frozen pose-backbone descriptors may encode synthetic shortcuts.",
            "Fixed alpha 1.0 and comparison rule; no calibration or threshold selection.",
            "Out-of-fold variants are correlated within each grouped scene.",
            "Passing permits only a later full fit and separately frozen calibration experiment.",
        ],
    }
    out.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps(
            {
                "summaries": summaries,
                "scene_auc": {
                    name: value["tail_auc"] for name, value in ranking.items()
                },
                "checks": checks,
                "passed": passed,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    run()

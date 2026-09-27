"""Fresh ranking study for frozen local visual support features."""

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

from train.train_diverse_pose_ensemble import (
    pairwise_disagreement,
    predict,
    score_predictions,
)
from vision.audit_scale_ranking import auc
from vision.diverse_pose_models import MODELS
from vision.evaluate_dark_only_normalization import normalize
from vision.geometry_candidate_decoder import LOCAL
from vision.landmark_occlusions import render_controlled
from vision.linear_residual_pose import LinearResidualPoseNet
from vision.synthetic_keyboard import catalog_for_workspace
from vision.temperature_visibility_model import TemperatureVisibilityNet
from vision.train_pose import _pose_from_prediction


def corner_features(candidate_prediction, heatmap_logits, visibility_logits):
    if heatmap_logits.shape != (4, 48, 64) or visibility_logits.shape != (4,):
        raise ValueError("expected four landmark heatmaps and visibility logits")
    pose = _pose_from_prediction(candidate_prediction)
    cosine, sine = math.cos(pose[2]), math.sin(pose[2])
    expected = LOCAL @ np.asarray([[cosine, sine], [-sine, cosine]]) + pose[:2]
    flat = heatmap_logits.reshape(4, -1)
    peak = flat.argmax(1)
    observed = np.stack(
        ((peak % 64) * 4 * 610 / 256, (peak // 64) * 4 * 457 / 192), axis=1
    )
    residuals = np.linalg.norm(observed - expected, axis=1)
    visibility = 1 / (1 + np.exp(-visibility_logits))
    top = np.partition(flat, -2, axis=1)[:, -2:]
    margins = top[:, 1] - top[:, 0]
    weighted = residuals * (2 - visibility)
    return {
        "corner_residuals_mm": residuals.tolist(),
        "visibility_probabilities": visibility.tolist(),
        "heatmap_logit_margins": margins.tolist(),
        "corner_residual_max": float(residuals.max()),
        "visibility_weighted_residual": float(weighted.max()),
    }


def ranking(rows, score_name, conditions, tolerance):
    scene_ids = sorted({row["seed"] for row in rows})
    scenes = [
        {
            "seed": seed,
            "score": max(row["scores"][score_name] for row in rows if row["seed"] == seed),
            "failed": any(row["error_mm"] > tolerance for row in rows if row["seed"] == seed),
        }
        for seed in scene_ids
    ]
    labels = np.asarray([scene["failed"] for scene in scenes], dtype=np.int64)
    scores = np.asarray([scene["score"] for scene in scenes], dtype=np.float64)
    ordered = sorted(scenes, key=lambda row: (row["score"], row["seed"]))
    result = {
        "scene_auc": auc(scores, labels * 4),
        "failed_scenes": int(labels.sum()),
        "scene_failure_rate": float(labels.mean()),
        "lowest_25_failure_rate": sum(row["failed"] for row in ordered[: len(ordered) // 4]) / (len(ordered) // 4),
        "lowest_50_failure_rate": sum(row["failed"] for row in ordered[: len(ordered) // 2]) / (len(ordered) // 2),
        "condition_image_auc": {},
    }
    for condition in conditions:
        selected = [row for row in rows if row["condition"] == condition]
        condition_labels = np.asarray(
            [row["error_mm"] > tolerance for row in selected], dtype=np.int64
        )
        condition_scores = np.asarray(
            [row["scores"][score_name] for row in selected], dtype=np.float64
        )
        result["condition_image_auc"][condition] = auc(
            condition_scores, condition_labels * 4
        )
    return result


def run():
    path = AI / "eval/localized_geometric_risk_v1_plan.json"
    plan = json.loads(path.read_text())
    for name, digest in plan["file_sha256"].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise ValueError("source mismatch: " + name)
    output = AI / "eval/localized_geometric_risk_v1_report.json"
    if output.exists():
        raise FileExistsError(output)

    torch.set_num_threads(4)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    catalog = catalog_for_workspace(ROOT)
    targets = list(catalog.keyboard_targets.values())
    pose_models = {
        "candidate": LinearResidualPoseNet.from_export(
            torch.load(
                ROOT / plan["candidate_artifact"],
                weights_only=True,
                map_location="cpu",
            )
        ).to(device)
    }
    for name, checkpoint in plan["selected_checkpoints"].items():
        model = MODELS[name]().to(device)
        model.load_state_dict(
            torch.load(ROOT / checkpoint, weights_only=True, map_location=device)
        )
        pose_models[name] = model
    landmark = TemperatureVisibilityNet("t05").to(device)
    landmark.load_state_dict(
        torch.load(
            ROOT / plan["landmark_checkpoint"],
            weights_only=True,
            map_location=device,
        )
    )
    landmark.eval()

    raw_hash = hashlib.sha256()
    small_hash = hashlib.sha256()
    prediction_hashes = {name: hashlib.sha256() for name in pose_models}
    landmark_hash = hashlib.sha256()
    rows = []
    start, count = plan["development_group"]
    for chunk_start in range(start, start + count, plan["seed_chunk"]):
        metadata = []
        raw_pixels = []
        small_pixels = []
        for seed in range(chunk_start, min(chunk_start + plan["seed_chunk"], start + count)):
            for style in plan["styles"]:
                for condition in plan["conditions"]:
                    image, label, _ = render_controlled(seed, catalog, condition, style)
                    image, _ = normalize(image)
                    raw = np.asarray(image, dtype=np.uint8).transpose(2, 0, 1).copy()
                    small = np.asarray(image.resize((128, 96)), dtype=np.uint8).transpose(2, 0, 1).copy()
                    raw_pixels.append(raw)
                    small_pixels.append(small)
                    metadata.append((seed, style, condition, label["pose"]))
        raw_pixels = np.stack(raw_pixels)
        small_pixels = np.stack(small_pixels)
        raw_hash.update(raw_pixels.tobytes())
        small_hash.update(small_pixels.tobytes())
        predictions = {
            name: predict(model, small_pixels, device, plan["batch_size"])
            for name, model in pose_models.items()
        }
        for name, values in predictions.items():
            prediction_hashes[name].update(values.tobytes())
        with torch.no_grad():
            landmark_output = landmark(
                torch.from_numpy(raw_pixels).to(device).float() / 255
            )
        heatmaps = landmark_output["heatmap_logits"].cpu().numpy()
        visibility = landmark_output["visibility_logits"].cpu().numpy()
        landmark_hash.update(heatmaps.tobytes())
        landmark_hash.update(visibility.tobytes())
        errors, _ = score_predictions(
            predictions["candidate"], metadata, targets, plan["conditions"]
        )
        for index, ((seed, style, condition, _), error) in enumerate(zip(metadata, errors)):
            local = corner_features(
                predictions["candidate"][index], heatmaps[index], visibility[index]
            )
            disagreement = pairwise_disagreement(predictions, index, targets)
            local["scores"] = {
                "ensemble_disagreement": disagreement,
                "corner_residual_max": local["corner_residual_max"],
                "visibility_weighted_residual": local["visibility_weighted_residual"],
                "fused_local": disagreement
                + plan["fused_residual_weight"]
                * local["visibility_weighted_residual"],
            }
            rows.append(
                {
                    "seed": seed,
                    "style": style,
                    "condition": condition,
                    "error_mm": error["maximum_mm"],
                    **local,
                }
            )
        print("processed through seed", metadata[-1][0], flush=True)

    rankings = {
        name: ranking(rows, name, plan["conditions"], plan["tolerance_mm"])
        for name in plan["score_names"]
    }
    baseline = rankings["ensemble_disagreement"]
    checks = {}
    passing = []
    for name in plan["localized_score_names"]:
        value = rankings[name]
        decision = {
            "minimum_scene_auc": value["scene_auc"] >= plan["minimum_scene_auc"],
            "scene_auc_improvement": value["scene_auc"]
            >= baseline["scene_auc"] + plan["minimum_scene_auc_improvement"],
            "lowest_25_reduction": value["lowest_25_failure_rate"]
            <= baseline["lowest_25_failure_rate"] * plan["maximum_low_25_ratio"],
            "lowest_50_reduction": value["lowest_50_failure_rate"]
            <= baseline["lowest_50_failure_rate"] * plan["maximum_low_50_ratio"],
            "partial_auc": value["condition_image_auc"]["partial"]
            >= plan["minimum_obstructed_image_auc"],
            "full_auc": value["condition_image_auc"]["full"]
            >= plan["minimum_obstructed_image_auc"],
        }
        checks[name] = decision
        if all(decision.values()):
            passing.append(name)
    selected = max(passing, key=lambda name: rankings[name]["scene_auc"]) if passing else None
    report = {
        "plan_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "device": device,
        "rows": rows,
        "raw_pixels_sha256": raw_hash.hexdigest(),
        "small_pixels_sha256": small_hash.hexdigest(),
        "pose_prediction_sha256": {
            name: digest.hexdigest() for name, digest in prediction_hashes.items()
        },
        "landmark_prediction_sha256": landmark_hash.hexdigest(),
        "rankings": rankings,
        "checks": checks,
        "selected_feature": selected,
        "passed_selection": selected is not None,
        "new_model_fits": 0,
        "calibration_fits": 0,
        "optimizer_updates": 0,
        "hardware_writes": 0,
        "physical_movements": 0,
        "qualification_installed": False,
        "limitations": [
            "Fresh grouped synthetic ranking evidence; no metric calibration or physical-camera claim.",
            "Landmark heatmaps and visibility are frozen synthetic research outputs, not calibrated confidence.",
            "Three millimetres is a research failure label, not a contact or execution margin.",
            "No runtime installation, physical qualification, or motion authority.",
        ],
    }
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({key: report[key] for key in ("rankings", "checks", "selected_feature", "passed_selection")}, indent=2))


if __name__ == "__main__":
    run()

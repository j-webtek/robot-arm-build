"""Fixed diverse-pose ensemble study on broader grouped synthetic scenes."""

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

from train.compare_backbone_uncertainty import scene_metrics
from vision.diagnose_pose_tail import decompose
from vision.diverse_pose_models import MODELS
from vision.evaluate_dark_only_normalization import normalize
from vision.landmark_occlusions import render_controlled
from vision.linear_residual_pose import LinearResidualPoseNet
from vision.synthetic_keyboard import catalog_for_workspace
from vision.train_pose import _pose_from_prediction


def render_set(start, count, plan, catalog):
    pixels = []
    labels = []
    metadata = []
    for seed in range(start, start + count):
        for style in plan["styles"]:
            for condition in plan["conditions"]:
                image, label, _ = render_controlled(seed, catalog, condition, style)
                image, _ = normalize(image)
                pose = label["pose"]
                pixels.append(np.asarray(image.resize((128, 96))).transpose(2, 0, 1).copy())
                labels.append(
                    [(pose[0] - 235) / 30, (pose[1] - 154) / 24, (pose[2] - math.pi) / 0.2]
                )
                metadata.append((seed, style, condition, pose))
    return np.stack(pixels), np.asarray(labels, dtype=np.float32), metadata


def predict(model, pixels, device, batch_size):
    model.eval()
    values = []
    with torch.no_grad():
        for batch in torch.from_numpy(pixels).split(batch_size):
            values.append(model(batch.to(device).float() / 255).cpu().numpy())
    return np.concatenate(values)


def score_predictions(predictions, metadata, targets, conditions):
    rows = [
        dict(seed=seed, style=style, condition=condition, **decompose(_pose_from_prediction(value), truth, targets))
        for value, (seed, style, condition, truth) in zip(predictions, metadata)
    ]
    summary = {}
    for condition in conditions:
        group = [row for row in rows if row["condition"] == condition]
        summary[condition] = {
            "images": len(group),
            "mean_mm": float(np.mean([row["mean_mm"] for row in group])),
            "tail": sum(row["maximum_mm"] > 3 for row in group),
            "yaw_p95": float(np.percentile([row["yaw_degrees"] for row in group], 95)),
        }
    return rows, summary


def pairwise_disagreement(predictions, index, targets):
    poses = [_pose_from_prediction(values[index]) for values in predictions.values()]
    return max(
        decompose(poses[left], poses[right], targets)["maximum_mm"]
        for left in range(len(poses))
        for right in range(left + 1, len(poses))
    )


def run():
    path = AI / "train/diverse_pose_ensemble_v1_plan.json"
    plan = json.loads(path.read_text())
    for name, digest in plan["file_sha256"].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise ValueError("source mismatch: " + name)
    out = AI / "eval/diverse_pose_ensemble_v1_report.json"
    directories = {name: AI / "results" / f"diverse_pose_ensemble_v1_{name}" for name in plan["models"]}
    if out.exists() or any(directory.exists() for directory in directories.values()):
        raise FileExistsError("existing ensemble evidence")

    torch.set_num_threads(4)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    catalog = catalog_for_workspace(ROOT)
    targets = list(catalog.keyboard_targets.values())
    train_pixels, train_labels, _ = render_set(*plan["training_groups"], plan, catalog)
    dev_pixels, _, dev_metadata = render_set(*plan["development_groups"], plan, catalog)
    train_tensor = torch.from_numpy(train_pixels)
    label_tensor = torch.from_numpy(train_labels)
    trained = {}
    histories = {}
    checkpoint_hashes = {}
    for name, spec in plan["models"].items():
        torch.manual_seed(spec["seed"])
        model = MODELS[name]().to(device)
        generator = torch.Generator().manual_seed(spec["seed"])
        loader = torch.utils.data.DataLoader(
            torch.utils.data.TensorDataset(train_tensor, label_tensor),
            batch_size=plan["batch_size"],
            shuffle=True,
            generator=generator,
        )
        optimizer = torch.optim.AdamW(
            model.parameters(),
            lr=plan["learning_rate"],
            weight_decay=plan["weight_decay"],
        )
        history = []
        weights = torch.tensor([4.0, 4.0, 1.0], device=device)
        for epoch in range(plan["epochs"]):
            model.train()
            total = 0.0
            for images, truth in loader:
                optimizer.zero_grad(set_to_none=True)
                residual = model(images.to(device).float() / 255) - truth.to(device)
                loss = (residual.square() * weights).sum(1).mean() / 9
                loss.backward()
                optimizer.step()
                total += float(loss.detach()) * len(images)
            history.append({"epoch": epoch + 1, "training_loss": total / len(train_tensor)})
            print(name, history[-1], flush=True)
        directories[name].mkdir()
        checkpoint = directories[name] / "pose_model.pt"
        torch.save({key: value.detach().cpu() for key, value in model.state_dict().items()}, checkpoint)
        checkpoint_hashes[name] = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
        histories[name] = history
        trained[name] = predict(model, dev_pixels, device, plan["batch_size"])

    candidate_model = LinearResidualPoseNet.from_export(
        torch.load(ROOT / plan["candidate_artifact"], weights_only=True, map_location="cpu")
    ).to(device)
    predictions = {"candidate": predict(candidate_model, dev_pixels, device, plan["batch_size"]), **trained}
    scores = {}
    rows_by_model = {}
    for name, values in predictions.items():
        rows_by_model[name], scores[name] = score_predictions(
            values, dev_metadata, targets, plan["conditions"]
        )
    disagreement_rows = [
        dict(
            seed=seed,
            style=style,
            condition=condition,
            error_mm=rows_by_model["candidate"][index]["maximum_mm"],
            ensemble_disagreement_mm=pairwise_disagreement(predictions, index, targets),
        )
        for index, (seed, style, condition, _) in enumerate(dev_metadata)
    ]
    ranking = scene_metrics(
        disagreement_rows,
        "ensemble_disagreement_mm",
        plan["retention_fractions"],
    )
    curve = {point["requested_fraction"]: point for point in ranking["retention_curve"]}
    checks = {
        "scene_tail_auc": ranking["tail_auc"] >= plan["minimum_scene_tail_auc"],
        "retention_0_25_relative": curve[0.25]["tail_rate"]
        <= plan["retention_0_25_max_relative"] * ranking["tail_rate"],
        "retention_0_5_relative": curve[0.5]["tail_rate"]
        <= plan["retention_0_5_max_relative"] * ranking["tail_rate"],
        "member_mean_error": {
            name: {
                condition: scores[name][condition]["mean_mm"]
                <= plan["member_max_mean_ratio"] * scores["candidate"][condition]["mean_mm"]
                for condition in plan["conditions"]
            }
            for name in plan["models"]
        },
    }
    passed = (
        checks["scene_tail_auc"]
        and checks["retention_0_25_relative"]
        and checks["retention_0_5_relative"]
        and all(all(values.values()) for values in checks["member_mean_error"].values())
    )
    result = {
        "plan_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "device": device,
        "training_images": len(train_pixels),
        "development_images": len(dev_pixels),
        "training_pixels_sha256": hashlib.sha256(train_pixels.tobytes()).hexdigest(),
        "development_pixels_sha256": hashlib.sha256(dev_pixels.tobytes()).hexdigest(),
        "model_parameters": {name: sum(parameter.numel() for parameter in MODELS[name]().parameters()) for name in plan["models"]},
        "checkpoint_sha256": checkpoint_hashes,
        "histories": histories,
        "prediction_sha256": {name: hashlib.sha256(values.tobytes()).hexdigest() for name, values in predictions.items()},
        "scores": scores,
        "candidate_rows": rows_by_model["candidate"],
        "disagreement_rows": disagreement_rows,
        "scene_ranking": ranking,
        "checks": checks,
        "passed": passed,
        "pose_fits": len(plan["models"]),
        "optimizer_updates": len(plan["models"]) * plan["epochs"] * math.ceil(len(train_pixels) / plan["batch_size"]),
        "calibration_fits": 0,
        "hardware_writes": 0,
        "physical_movements": 0,
        "qualification_installed": False,
        "limitations": [
            "New synthetic training/development cohort from the same renderer; no physical-camera evidence.",
            "One fixed seed per architecture and GPU training; nondeterminism may remain.",
            "Development evaluates a frozen plan without epoch selection but is not calibration or confirmation.",
            "Ensemble dispersion is uncalibrated and cannot authorize motion.",
            "Passing would permit only a separate frozen calibration and confirmation chain.",
        ],
    }
    out.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"scores": scores, "scene_ranking": ranking, "checks": checks, "passed": passed}, indent=2))


if __name__ == "__main__":
    run()

"""Fixed appearance-weighted compact-pose ensemble selection study."""

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
from train.train_diverse_pose_ensemble import (
    pairwise_disagreement,
    predict,
    render_set,
    score_predictions,
)
from vision.diverse_pose_models import MODELS
from vision.linear_residual_pose import LinearResidualPoseNet
from vision.synthetic_keyboard import catalog_for_workspace


def run():
    path = AI / "train/appearance_robust_ensemble_v1_plan.json"
    plan = json.loads(path.read_text())
    for name, digest in plan["file_sha256"].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise ValueError("source mismatch: " + name)
    output = AI / "eval/appearance_robust_ensemble_v1_report.json"
    directories = {
        name: AI / "results" / f"appearance_robust_ensemble_v1_{name}"
        for name in plan["models"]
    }
    if output.exists() or any(directory.exists() for directory in directories.values()):
        raise FileExistsError("existing appearance-robust ensemble evidence")

    torch.set_num_threads(4)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    catalog = catalog_for_workspace(ROOT)
    targets = list(catalog.keyboard_targets.values())
    train_pixels, train_labels, train_metadata = render_set(
        *plan["training_groups"], plan, catalog
    )
    selection_pixels, _, selection_metadata = render_set(
        *plan["selection_groups"], plan, catalog
    )
    train_weights = np.asarray(
        [plan["condition_loss_weights"][condition] for _, _, condition, _ in train_metadata],
        dtype=np.float32,
    )
    train_tensor = torch.from_numpy(train_pixels)
    label_tensor = torch.from_numpy(train_labels)
    weight_tensor = torch.from_numpy(train_weights)
    trained = {}
    histories = {}
    checkpoint_hashes = {}
    for name, spec in plan["models"].items():
        torch.manual_seed(spec["seed"])
        model = MODELS[name]().to(device)
        generator = torch.Generator().manual_seed(spec["seed"])
        loader = torch.utils.data.DataLoader(
            torch.utils.data.TensorDataset(train_tensor, label_tensor, weight_tensor),
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
        pose_weights = torch.tensor([4.0, 4.0, 1.0], device=device)
        for epoch in range(plan["epochs"]):
            model.train()
            total_loss = 0.0
            total_weight = 0.0
            for images, truth, sample_weights in loader:
                optimizer.zero_grad(set_to_none=True)
                residual = model(images.to(device).float() / 255) - truth.to(device)
                per_sample = (residual.square() * pose_weights).sum(1) / 9
                sample_weights = sample_weights.to(device)
                loss = (per_sample * sample_weights).sum() / sample_weights.sum()
                loss.backward()
                optimizer.step()
                total_loss += float((per_sample.detach() * sample_weights).sum())
                total_weight += float(sample_weights.sum())
            history.append(
                {"epoch": epoch + 1, "weighted_training_loss": total_loss / total_weight}
            )
            print(name, history[-1], flush=True)
        directories[name].mkdir()
        checkpoint = directories[name] / "pose_model.pt"
        torch.save(
            {key: value.detach().cpu() for key, value in model.state_dict().items()},
            checkpoint,
        )
        checkpoint_hashes[name] = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
        histories[name] = history
        trained[name] = predict(model, selection_pixels, device, plan["batch_size"])

    candidate_model = LinearResidualPoseNet.from_export(
        torch.load(ROOT / plan["candidate_artifact"], weights_only=True, map_location="cpu")
    ).to(device)
    predictions = {
        "candidate": predict(candidate_model, selection_pixels, device, plan["batch_size"]),
        **trained,
    }
    scores = {}
    rows_by_model = {}
    for name, values in predictions.items():
        rows_by_model[name], scores[name] = score_predictions(
            values, selection_metadata, targets, plan["conditions"]
        )
    disagreement_rows = [
        dict(
            seed=seed,
            style=style,
            condition=condition,
            error_mm=rows_by_model["candidate"][index]["maximum_mm"],
            ensemble_disagreement_mm=pairwise_disagreement(predictions, index, targets),
        )
        for index, (seed, style, condition, _) in enumerate(selection_metadata)
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
        "member_appearance_error": {
            name: scores[name]["appearance_shift"]["mean_mm"]
            <= plan["member_appearance_max_mean_ratio"]
            * scores["candidate"]["appearance_shift"]["mean_mm"]
            for name in plan["models"]
        },
    }
    passed = (
        checks["scene_tail_auc"]
        and checks["retention_0_25_relative"]
        and checks["retention_0_5_relative"]
        and all(all(values.values()) for values in checks["member_mean_error"].values())
        and all(checks["member_appearance_error"].values())
    )
    result = {
        "plan_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "previous_report_sha256": plan["file_sha256"][plan["previous_report"]],
        "device": device,
        "training_images": len(train_pixels),
        "selection_images": len(selection_pixels),
        "training_pixels_sha256": hashlib.sha256(train_pixels.tobytes()).hexdigest(),
        "selection_pixels_sha256": hashlib.sha256(selection_pixels.tobytes()).hexdigest(),
        "training_weight_sha256": hashlib.sha256(train_weights.tobytes()).hexdigest(),
        "model_parameters": {
            name: sum(parameter.numel() for parameter in MODELS[name]().parameters())
            for name in plan["models"]
        },
        "checkpoint_sha256": checkpoint_hashes,
        "histories": histories,
        "prediction_sha256": {
            name: hashlib.sha256(values.tobytes()).hexdigest()
            for name, values in predictions.items()
        },
        "scores": scores,
        "candidate_rows": rows_by_model["candidate"],
        "disagreement_rows": disagreement_rows,
        "scene_ranking": ranking,
        "checks": checks,
        "passed_selection": passed,
        "pose_fits": len(plan["models"]),
        "optimizer_updates": len(plan["models"])
        * plan["epochs"]
        * math.ceil(len(train_pixels) / plan["batch_size"]),
        "calibration_fits": 0,
        "hardware_writes": 0,
        "physical_movements": 0,
        "qualification_installed": False,
        "limitations": [
            "New synthetic training and selection cohorts from the same renderer; no physical-camera evidence.",
            "One fixed seed per architecture and GPU training; nondeterminism may remain.",
            "Selection is a go/no-go decision for a separate frozen development study, not confirmation.",
            "Appearance weighting was fixed before training and has no runtime meaning.",
            "Ensemble dispersion is uncalibrated and cannot authorize motion.",
        ],
    }
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps(
            {
                "scores": scores,
                "scene_ranking": ranking,
                "checks": checks,
                "passed_selection": passed,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    run()

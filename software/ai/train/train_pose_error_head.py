"""Train one compact head against frozen pose residuals and test fresh ranking."""

import hashlib
import json
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
    render_set,
    score_predictions,
)
from vision.diverse_pose_models import MODELS
from vision.evaluate_localized_geometric_risk import ranking
from vision.linear_residual_pose import LinearResidualPoseNet
from vision.pose_error_head import PoseErrorHead
from vision.synthetic_keyboard import catalog_for_workspace


def descriptor(model, pixels, device, batch_size):
    model.eval()
    values = []
    with torch.no_grad():
        for batch in torch.from_numpy(pixels).split(batch_size):
            feature = model.backbone.features[:4](batch.to(device).float() / 255)
            values.append(
                torch.nn.functional.adaptive_avg_pool2d(feature, (4, 4))
                .flatten(1)
                .cpu()
                .numpy()
            )
    return np.concatenate(values).astype(np.float32)


def build_cohort(plan, group, models, catalog, targets, device):
    pixels, _, metadata = render_set(*group, plan, catalog)
    predictions = {
        name: predict(model, pixels, device, plan["batch_size"])
        for name, model in models.items()
    }
    candidate_rows, _ = score_predictions(
        predictions["candidate"], metadata, targets, plan["conditions"]
    )
    disagreements = np.asarray(
        [pairwise_disagreement(predictions, index, targets) for index in range(len(metadata))],
        dtype=np.float32,
    )
    descriptors = descriptor(models["candidate"], pixels, device, plan["batch_size"])
    features = np.concatenate((descriptors, disagreements[:, None]), axis=1)
    errors = np.asarray([row["maximum_mm"] for row in candidate_rows], dtype=np.float32)
    rows = [
        {
            "seed": seed,
            "style": style,
            "condition": condition,
            "error_mm": float(error),
            "ensemble_disagreement": float(disagreement),
        }
        for (seed, style, condition, _), error, disagreement in zip(metadata, errors, disagreements)
    ]
    return {
        "features": features,
        "errors": errors,
        "rows": rows,
        "pixels_sha256": hashlib.sha256(pixels.tobytes()).hexdigest(),
        "features_sha256": hashlib.sha256(features.tobytes()).hexdigest(),
        "targets_sha256": hashlib.sha256(errors.tobytes()).hexdigest(),
        "prediction_sha256": {
            name: hashlib.sha256(values.tobytes()).hexdigest()
            for name, values in predictions.items()
        },
    }


def run():
    path = AI / "train/pose_error_head_v1_plan.json"
    plan = json.loads(path.read_text())
    for name, digest in plan["file_sha256"].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise ValueError("source mismatch: " + name)
    output = AI / "eval/pose_error_head_v1_report.json"
    directory = AI / "results/pose_error_head_v1"
    if output.exists() or directory.exists():
        raise FileExistsError("existing pose-error evidence")

    torch.manual_seed(plan["seed"])
    torch.set_num_threads(4)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    catalog = catalog_for_workspace(ROOT)
    targets = list(catalog.keyboard_targets.values())
    models = {
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
        models[name] = model

    training = build_cohort(
        plan, plan["groups"]["training"], models, catalog, targets, device
    )
    mean = training["features"].mean(0)
    scale = training["features"].std(0)
    scale[scale < plan["minimum_feature_scale"]] = plan["minimum_feature_scale"]
    head = PoseErrorHead(mean, scale).to(device)
    optimizer = torch.optim.AdamW(
        head.parameters(), lr=plan["learning_rate"], weight_decay=plan["weight_decay"]
    )
    target = np.log1p(training["errors"]).astype(np.float32)
    loader = torch.utils.data.DataLoader(
        torch.utils.data.TensorDataset(
            torch.from_numpy(training["features"]), torch.from_numpy(target)
        ),
        batch_size=plan["batch_size"],
        shuffle=True,
        generator=torch.Generator().manual_seed(plan["seed"]),
    )
    history = []
    for epoch in range(plan["epochs"]):
        head.train()
        total = 0.0
        for features, truth in loader:
            optimizer.zero_grad(set_to_none=True)
            value = torch.nn.functional.smooth_l1_loss(
                head(features.to(device)), truth.to(device), beta=plan["huber_beta"]
            )
            value.backward()
            optimizer.step()
            total += float(value.detach()) * len(features)
        history.append({"epoch": epoch + 1, "training_loss": total / len(target)})
        print(history[-1], flush=True)

    directory.mkdir()
    checkpoint = directory / "model.pt"
    torch.save({key: value.detach().cpu() for key, value in head.state_dict().items()}, checkpoint)
    del training["features"], training["errors"]
    selection = build_cohort(
        plan, plan["groups"]["selection"], models, catalog, targets, device
    )
    head.eval()
    with torch.no_grad():
        risk = np.concatenate(
            [
                head(batch.to(device)).cpu().numpy()
                for batch in torch.from_numpy(selection["features"]).split(plan["batch_size"])
            ]
        )
    rows = [
        {
            **row,
            "scores": {
                "ensemble_disagreement": row["ensemble_disagreement"],
                "pose_error_head": float(value),
            },
        }
        for row, value in zip(selection["rows"], risk)
    ]
    rankings = {
        name: ranking(rows, name, plan["conditions"], plan["tolerance_mm"])
        for name in ("ensemble_disagreement", "pose_error_head")
    }
    baseline = rankings["ensemble_disagreement"]
    candidate = rankings["pose_error_head"]
    checks = {
        "minimum_scene_auc": candidate["scene_auc"] >= plan["minimum_scene_auc"],
        "scene_auc_improvement": candidate["scene_auc"]
        >= baseline["scene_auc"] + plan["minimum_scene_auc_improvement"],
        "lowest_25_reduction": candidate["lowest_25_failure_rate"]
        <= baseline["lowest_25_failure_rate"] * plan["maximum_low_25_ratio"],
        "lowest_50_reduction": candidate["lowest_50_failure_rate"]
        <= baseline["lowest_50_failure_rate"] * plan["maximum_low_50_ratio"],
        "condition_image_auc": {
            condition: value >= plan["minimum_condition_image_auc"]
            for condition, value in candidate["condition_image_auc"].items()
        },
    }
    passed = (
        all(value for value in checks.values() if isinstance(value, bool))
        and all(checks["condition_image_auc"].values())
    )
    report = {
        "plan_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "device": device,
        "model_parameters": sum(parameter.numel() for parameter in head.parameters()),
        "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        "normalization_sha256": hashlib.sha256(
            np.concatenate((mean, scale)).astype(np.float32).tobytes()
        ).hexdigest(),
        "training": {key: value for key, value in training.items() if key != "rows"},
        "training_rows": training["rows"],
        "history": history,
        "selection": {key: value for key, value in selection.items() if key not in ("features", "errors", "rows")},
        "selection_rows": rows,
        "risk_prediction_sha256": hashlib.sha256(risk.tobytes()).hexdigest(),
        "rankings": rankings,
        "checks": checks,
        "passed_selection": passed,
        "model_fits": 1,
        "calibration_fits": 0,
        "optimizer_updates": plan["epochs"] * int(np.ceil(len(target) / plan["batch_size"])),
        "hardware_writes": 0,
        "physical_movements": 0,
        "qualification_installed": False,
        "limitations": [
            "Synthetic training-selection evidence; no metric calibration or physical-camera claim.",
            "The risk head is supervised by errors from one frozen pose candidate and may inherit renderer bias.",
            "Three millimetres is a research failure label, not a contact or execution margin.",
            "No runtime installation, physical qualification, or motion authority.",
        ],
    }
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({key: report[key] for key in ("rankings", "checks", "passed_selection")}, indent=2))


if __name__ == "__main__":
    run()

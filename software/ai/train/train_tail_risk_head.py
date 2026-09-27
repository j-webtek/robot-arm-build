"""Train one balanced tail classifier over frozen pose features."""

import hashlib
import json
import sys
from pathlib import Path

AI = Path(__file__).resolve().parents[1]
ROOT = AI.parents[1]
sys.path[:0] = [str(AI), str(AI.parent / "src")]

import numpy as np
import torch

from train.train_pose_error_head import build_cohort
from train.train_diverse_pose_ensemble import predict
from vision.diverse_pose_models import MODELS
from vision.evaluate_localized_geometric_risk import ranking
from vision.linear_residual_pose import LinearResidualPoseNet
from vision.pose_error_head import PoseErrorHead
from vision.synthetic_keyboard import catalog_for_workspace


def decision_checks(candidate, baseline, plan):
    return {
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


def checks_pass(checks):
    return (
        all(value for value in checks.values() if isinstance(value, bool))
        and all(checks["condition_image_auc"].values())
    )


def run():
    path = AI / "train/tail_risk_head_v1_plan.json"
    plan = json.loads(path.read_text())
    for name, digest in plan["file_sha256"].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise ValueError("source mismatch: " + name)
    output = AI / "eval/tail_risk_head_v1_report.json"
    directory = AI / "results/tail_risk_head_v1"
    if output.exists() or directory.exists():
        raise FileExistsError("existing tail-risk evidence")

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
    labels = (training["errors"] > plan["tolerance_mm"]).astype(np.float32)
    positives = int(labels.sum())
    negatives = len(labels) - positives
    positive_weight = negatives / positives
    head = PoseErrorHead(mean, scale).to(device)
    optimizer = torch.optim.AdamW(
        head.parameters(), lr=plan["learning_rate"], weight_decay=plan["weight_decay"]
    )
    loader = torch.utils.data.DataLoader(
        torch.utils.data.TensorDataset(
            torch.from_numpy(training["features"]), torch.from_numpy(labels)
        ),
        batch_size=plan["batch_size"],
        shuffle=True,
        generator=torch.Generator().manual_seed(plan["seed"]),
    )
    history = []
    weight = torch.tensor(positive_weight, dtype=torch.float32, device=device)
    for epoch in range(plan["epochs"]):
        head.train()
        total = 0.0
        for features, truth in loader:
            optimizer.zero_grad(set_to_none=True)
            value = torch.nn.functional.binary_cross_entropy_with_logits(
                head(features.to(device)), truth.to(device), pos_weight=weight
            )
            value.backward()
            optimizer.step()
            total += float(value.detach()) * len(features)
        history.append({"epoch": epoch + 1, "training_loss": total / len(labels)})
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
                "tail_risk_head": float(value),
            },
        }
        for row, value in zip(selection["rows"], risk)
    ]
    rankings = {
        name: ranking(rows, name, plan["conditions"], plan["tolerance_mm"])
        for name in ("ensemble_disagreement", "tail_risk_head")
    }
    checks = decision_checks(
        rankings["tail_risk_head"], rankings["ensemble_disagreement"], plan
    )
    passed = checks_pass(checks)
    report = {
        "plan_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "prior_report_sha256": plan["file_sha256"][plan["prior_report"]],
        "device": device,
        "model_parameters": sum(parameter.numel() for parameter in head.parameters()),
        "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        "normalization_sha256": hashlib.sha256(
            np.concatenate((mean, scale)).astype(np.float32).tobytes()
        ).hexdigest(),
        "training_positive_images": positives,
        "training_negative_images": negatives,
        "positive_weight": positive_weight,
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
        "optimizer_updates": plan["epochs"] * int(np.ceil(len(labels) / plan["batch_size"])),
        "hardware_writes": 0,
        "physical_movements": 0,
        "qualification_installed": False,
        "limitations": [
            "Synthetic training-selection evidence; no metric calibration or physical-camera claim.",
            "The binary failure label and class weight are specific to one frozen pose candidate and 3 mm research threshold.",
            "Passing permits only a separately frozen mapping/calibration and confirmation chain.",
            "No runtime installation, physical qualification, or motion authority.",
        ],
    }
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({key: report[key] for key in ("training_positive_images", "positive_weight", "rankings", "checks", "passed_selection")}, indent=2))


if __name__ == "__main__":
    run()

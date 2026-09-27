"""Train one metric upper-tail error head over frozen pose features."""

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
from vision.diverse_pose_models import MODELS
from vision.evaluate_localized_geometric_risk import ranking
from vision.linear_residual_pose import LinearResidualPoseNet
from vision.pose_error_head import PoseErrorHead
from vision.synthetic_keyboard import catalog_for_workspace


def pinball_loss(prediction, truth, quantile):
    residual = truth - prediction
    return torch.maximum(quantile * residual, (quantile - 1.0) * residual).mean()


def metric_summary(rows, key, quantile):
    errors = np.asarray([row["error_mm"] for row in rows], dtype=np.float64)
    bounds = np.asarray([row[key] for row in rows], dtype=np.float64)
    losses = np.maximum(quantile * (errors - bounds), (quantile - 1.0) * (errors - bounds))
    return {
        "images": len(rows),
        "coverage": float(np.mean(errors <= bounds)),
        "mean_pinball_loss": float(np.mean(losses)),
        "median_bound_mm": float(np.median(bounds)),
        "mean_bound_mm": float(np.mean(bounds)),
        "maximum_bound_mm": float(np.max(bounds)),
    }


def decision_checks(candidate, baseline, rankings, plan):
    return {
        "pinball_improvement": candidate["mean_pinball_loss"]
        <= baseline["mean_pinball_loss"] * plan["maximum_pinball_loss_ratio"],
        "minimum_coverage": candidate["coverage"] >= plan["minimum_image_coverage"],
        "maximum_coverage": candidate["coverage"] <= plan["maximum_image_coverage"],
        "median_bound_utility": candidate["median_bound_mm"]
        <= baseline["median_bound_mm"] * plan["maximum_median_bound_ratio"],
        "minimum_scene_auc": rankings["scene_auc"] >= plan["minimum_scene_auc"],
        "condition_coverage": {
            condition: summary["coverage"] >= plan["minimum_condition_coverage"]
            for condition, summary in candidate["conditions"].items()
        },
        "condition_image_auc": {
            condition: value >= plan["minimum_condition_image_auc"]
            for condition, value in rankings["condition_image_auc"].items()
        },
    }


def checks_pass(checks):
    return (
        all(value for value in checks.values() if isinstance(value, bool))
        and all(checks["condition_coverage"].values())
        and all(checks["condition_image_auc"].values())
    )


def infer_metric(head, features, device, batch_size):
    head.eval()
    with torch.no_grad():
        return np.concatenate(
            [
                torch.nn.functional.softplus(head(batch.to(device))).cpu().numpy()
                for batch in torch.from_numpy(features).split(batch_size)
            ]
        )


def run():
    path = AI / "train/upper_tail_error_head_v1_plan.json"
    plan = json.loads(path.read_text())
    for name, digest in plan["file_sha256"].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise ValueError("source mismatch: " + name)
    output = AI / "eval/upper_tail_error_head_v1_report.json"
    directory = AI / "results/upper_tail_error_head_v1"
    if output.exists() or directory.exists():
        raise FileExistsError("existing upper-tail evidence")

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
    loader = torch.utils.data.DataLoader(
        torch.utils.data.TensorDataset(
            torch.from_numpy(training["features"]),
            torch.from_numpy(training["errors"].astype(np.float32)),
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
            prediction = torch.nn.functional.softplus(head(features.to(device)))
            value = pinball_loss(prediction, truth.to(device), plan["quantile"])
            value.backward()
            optimizer.step()
            total += float(value.detach()) * len(features)
        history.append({"epoch": epoch + 1, "training_loss": total / len(training["errors"])})
        print(history[-1], flush=True)

    directory.mkdir()
    checkpoint = directory / "model.pt"
    torch.save({key: value.detach().cpu() for key, value in head.state_dict().items()}, checkpoint)
    constant_bound = float(
        np.quantile(training["errors"], plan["quantile"], method="higher")
    )
    del training["features"], training["errors"]
    selection = build_cohort(
        plan, plan["groups"]["selection"], models, catalog, targets, device
    )
    prediction = infer_metric(head, selection["features"], device, plan["batch_size"])
    rows = [
        {
            **row,
            "upper_tail_bound_mm": float(value),
            "constant_bound_mm": constant_bound,
            "scores": {"upper_tail_bound_mm": float(value)},
        }
        for row, value in zip(selection["rows"], prediction)
    ]
    candidate = metric_summary(rows, "upper_tail_bound_mm", plan["quantile"])
    candidate["conditions"] = {
        condition: metric_summary(
            [row for row in rows if row["condition"] == condition],
            "upper_tail_bound_mm",
            plan["quantile"],
        )
        for condition in plan["conditions"]
    }
    baseline = metric_summary(rows, "constant_bound_mm", plan["quantile"])
    rankings = ranking(
        rows, "upper_tail_bound_mm", plan["conditions"], plan["tolerance_mm"]
    )
    checks = decision_checks(candidate, baseline, rankings, plan)
    report = {
        "plan_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "prior_report_sha256": plan["file_sha256"][plan["prior_report"]],
        "device": device,
        "model_parameters": sum(parameter.numel() for parameter in head.parameters()),
        "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        "normalization_sha256": hashlib.sha256(
            np.concatenate((mean, scale)).astype(np.float32).tobytes()
        ).hexdigest(),
        "training_constant_bound_mm": constant_bound,
        "training": {key: value for key, value in training.items() if key != "rows"},
        "training_rows": training["rows"],
        "history": history,
        "selection": {
            key: value
            for key, value in selection.items()
            if key not in ("features", "errors", "rows")
        },
        "selection_rows": rows,
        "prediction_sha256": hashlib.sha256(prediction.tobytes()).hexdigest(),
        "candidate_summary": candidate,
        "constant_summary": baseline,
        "ranking": rankings,
        "checks": checks,
        "passed_selection": checks_pass(checks),
        "model_fits": 1,
        "calibration_fits": 0,
        "optimizer_updates": plan["epochs"]
        * int(np.ceil(len(training["rows"]) / plan["batch_size"])),
        "hardware_writes": 0,
        "physical_movements": 0,
        "qualification_installed": False,
        "limitations": [
            "Synthetic training-selection evidence; no independent calibration or physical-camera claim.",
            "The 95th-percentile objective is specific to one frozen pose candidate and synthetic generator.",
            "Passing permits only a separately frozen mapping-calibration and selection study.",
            "No runtime installation, physical qualification, or motion authority.",
        ],
    }
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "training_constant_bound_mm",
                    "candidate_summary",
                    "constant_summary",
                    "ranking",
                    "checks",
                    "passed_selection",
                )
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    run()

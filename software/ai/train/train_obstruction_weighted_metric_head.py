"""Train one obstruction-weighted bounded metric uncertainty head."""

import hashlib
import json
import sys
from pathlib import Path

AI = Path(__file__).resolve().parents[1]
ROOT = AI.parents[1]
sys.path[:0] = [str(AI), str(AI.parent / "src")]

import numpy as np
import torch

from train.train_bounded_upper_tail_head import bounded_metric, infer_metric
from train.train_pose_error_head import build_cohort
from train.train_upper_tail_error_head import (
    checks_pass,
    decision_checks,
    metric_summary,
)
from vision.diverse_pose_models import MODELS
from vision.evaluate_localized_geometric_risk import ranking
from vision.linear_residual_pose import LinearResidualPoseNet
from vision.pose_error_head import PoseErrorHead
from vision.synthetic_keyboard import catalog_for_workspace


def weighted_pinball_loss(prediction, truth, weights, quantile):
    residual = truth - prediction
    losses = torch.maximum(quantile * residual, (quantile - 1.0) * residual)
    return torch.sum(losses * weights) / torch.sum(weights)


def obstruction_weights(rows, weights_by_condition):
    return np.asarray(
        [weights_by_condition[row["condition"]] for row in rows],
        dtype=np.float32,
    )


def run():
    path = AI / "train/obstruction_weighted_metric_head_v1_plan.json"
    plan = json.loads(path.read_text())
    for name, digest in plan["file_sha256"].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise ValueError("source mismatch: " + name)
    output = AI / "eval/obstruction_weighted_metric_head_v1_report.json"
    directory = AI / "results/obstruction_weighted_metric_head_v1"
    if output.exists() or directory.exists():
        raise FileExistsError("existing obstruction-weighted evidence")

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
    weights = obstruction_weights(training["rows"], plan["condition_weights"])
    loader = torch.utils.data.DataLoader(
        torch.utils.data.TensorDataset(
            torch.from_numpy(training["features"]),
            torch.from_numpy(training["errors"].astype(np.float32)),
            torch.from_numpy(weights),
        ),
        batch_size=plan["batch_size"],
        shuffle=True,
        generator=torch.Generator().manual_seed(plan["seed"]),
    )
    history = []
    for epoch in range(plan["epochs"]):
        head.train()
        weighted_total = 0.0
        weight_total = 0.0
        for features, truth, batch_weights in loader:
            optimizer.zero_grad(set_to_none=True)
            prediction = bounded_metric(
                head(features.to(device)),
                plan["minimum_bound_mm"],
                plan["maximum_bound_mm"],
            )
            device_weights = batch_weights.to(device)
            value = weighted_pinball_loss(
                prediction, truth.to(device), device_weights, plan["quantile"]
            )
            value.backward()
            optimizer.step()
            batch_weight = float(device_weights.sum())
            weighted_total += float(value.detach()) * batch_weight
            weight_total += batch_weight
        history.append(
            {"epoch": epoch + 1, "weighted_training_loss": weighted_total / weight_total}
        )
        print(history[-1], flush=True)

    directory.mkdir()
    checkpoint = directory / "model.pt"
    torch.save(
        {key: value.detach().cpu() for key, value in head.state_dict().items()}, checkpoint
    )
    repeated_errors = np.repeat(
        training["errors"], weights.astype(np.int64)
    )
    constant_bound = float(
        np.quantile(repeated_errors, plan["quantile"], method="higher")
    )
    del training["features"], training["errors"]

    selection = build_cohort(
        plan, plan["groups"]["selection"], models, catalog, targets, device
    )
    prediction = infer_metric(
        head,
        selection["features"],
        device,
        plan["batch_size"],
        plan["minimum_bound_mm"],
        plan["maximum_bound_mm"],
    )
    prior_head = PoseErrorHead().to(device)
    prior_head.load_state_dict(
        torch.load(
            ROOT / plan["prior_checkpoint"], weights_only=True, map_location=device
        )
    )
    prior_prediction = infer_metric(
        prior_head,
        selection["features"],
        device,
        plan["batch_size"],
        plan["minimum_bound_mm"],
        plan["maximum_bound_mm"],
    )
    rows = [
        {
            **row,
            "obstruction_weighted_bound_mm": float(value),
            "prior_bounded_upper_tail_mm": float(prior),
            "constant_bound_mm": constant_bound,
            "scores": {"obstruction_weighted_bound_mm": float(value)},
        }
        for row, value, prior in zip(selection["rows"], prediction, prior_prediction)
    ]
    candidate = metric_summary(rows, "obstruction_weighted_bound_mm", plan["quantile"])
    prior = metric_summary(rows, "prior_bounded_upper_tail_mm", plan["quantile"])
    for summary, key in (
        (candidate, "obstruction_weighted_bound_mm"),
        (prior, "prior_bounded_upper_tail_mm"),
    ):
        summary["conditions"] = {
            condition: metric_summary(
                [row for row in rows if row["condition"] == condition],
                key,
                plan["quantile"],
            )
            for condition in plan["conditions"]
        }
    baseline = metric_summary(rows, "constant_bound_mm", plan["quantile"])
    rankings = ranking(
        rows,
        "obstruction_weighted_bound_mm",
        plan["conditions"],
        plan["tolerance_mm"],
    )
    checks = decision_checks(candidate, baseline, rankings, plan)
    checks.update(
        {
            "finite_bound": candidate["maximum_bound_mm"] <= plan["maximum_bound_mm"]
            and min(row["obstruction_weighted_bound_mm"] for row in rows)
            >= plan["minimum_bound_mm"],
            "prior_pinball_noninferiority": candidate["mean_pinball_loss"]
            <= prior["mean_pinball_loss"] * plan["maximum_prior_pinball_ratio"],
            "prior_median_bound_limit": candidate["median_bound_mm"]
            <= prior["median_bound_mm"] * plan["maximum_prior_median_ratio"],
            "partial_coverage_improvement": candidate["conditions"]["partial"]["coverage"]
            >= prior["conditions"]["partial"]["coverage"]
            + plan["minimum_partial_coverage_improvement"],
            "full_coverage_improvement": candidate["conditions"]["full"]["coverage"]
            >= prior["conditions"]["full"]["coverage"]
            + plan["minimum_full_coverage_improvement"],
        }
    )
    report = {
        "plan_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "prior_report_sha256": plan["file_sha256"][plan["prior_report"]],
        "prior_checkpoint_sha256": plan["file_sha256"][plan["prior_checkpoint"]],
        "trigger_report_sha256": plan["file_sha256"][plan["trigger_report"]],
        "device": device,
        "model_parameters": sum(parameter.numel() for parameter in head.parameters()),
        "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        "normalization_sha256": hashlib.sha256(
            np.concatenate((mean, scale)).astype(np.float32).tobytes()
        ).hexdigest(),
        "training_constant_bound_mm": constant_bound,
        "training_condition_weight_sum": float(weights.sum()),
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
        "prior_prediction_sha256": hashlib.sha256(prior_prediction.tobytes()).hexdigest(),
        "candidate_summary": candidate,
        "prior_summary": prior,
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
            "One frozen condition-weight schedule was evaluated without a weight, architecture, or quantile sweep.",
            "Synthetic condition labels supply training weights but are not model inputs.",
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
                    "training_condition_weight_sum",
                    "candidate_summary",
                    "prior_summary",
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

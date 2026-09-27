"""Train a bounded metric head with a fixed tail-ranking auxiliary loss."""

import hashlib
import json
import sys
from pathlib import Path

AI = Path(__file__).resolve().parents[1]
ROOT = AI.parents[1]
sys.path[:0] = [str(AI), str(AI.parent / "src")]

import numpy as np
import torch

from train.train_bounded_upper_tail_head import bounded_metric
from train.train_pose_error_head import build_cohort
from train.train_upper_tail_error_head import decision_checks, metric_summary, pinball_loss
from vision.diverse_pose_models import MODELS
from vision.evaluate_localized_geometric_risk import ranking
from vision.linear_residual_pose import LinearResidualPoseNet
from vision.multitask_error_head import MultiTaskErrorHead
from vision.synthetic_keyboard import catalog_for_workspace


def checks_pass(checks):
    return (
        all(value for value in checks.values() if isinstance(value, bool))
        and all(checks["condition_coverage"].values())
        and all(checks["condition_image_auc"].values())
        and all(checks["auxiliary_condition_image_auc"].values())
    )


def infer(head, features, device, plan):
    head.eval()
    metric, risk = [], []
    with torch.no_grad():
        for batch in torch.from_numpy(features).split(plan["batch_size"]):
            raw_metric, logits = head(batch.to(device))
            metric.append(
                bounded_metric(
                    raw_metric, plan["minimum_bound_mm"], plan["maximum_bound_mm"]
                )
                .cpu()
                .numpy()
            )
            risk.append(logits.cpu().numpy())
    return np.concatenate(metric), np.concatenate(risk)


def run():
    path = AI / "train/multitask_upper_tail_head_v1_plan.json"
    plan = json.loads(path.read_text())
    for name, digest in plan["file_sha256"].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise ValueError("source mismatch: " + name)
    output = AI / "eval/multitask_upper_tail_head_v1_report.json"
    directory = AI / "results/multitask_upper_tail_head_v1"
    if output.exists() or directory.exists():
        raise FileExistsError("existing multitask upper-tail evidence")

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
    head = MultiTaskErrorHead(mean, scale).to(device)
    optimizer = torch.optim.AdamW(
        head.parameters(), lr=plan["learning_rate"], weight_decay=plan["weight_decay"]
    )
    loader = torch.utils.data.DataLoader(
        torch.utils.data.TensorDataset(
            torch.from_numpy(training["features"]),
            torch.from_numpy(training["errors"].astype(np.float32)),
            torch.from_numpy(labels),
        ),
        batch_size=plan["batch_size"],
        shuffle=True,
        generator=torch.Generator().manual_seed(plan["seed"]),
    )
    history = []
    weight = torch.tensor(positive_weight, dtype=torch.float32, device=device)
    for epoch in range(plan["epochs"]):
        head.train()
        metric_total = tail_total = combined_total = 0.0
        for features, truth, tail_truth in loader:
            optimizer.zero_grad(set_to_none=True)
            raw_metric, tail_logits = head(features.to(device))
            prediction = bounded_metric(
                raw_metric, plan["minimum_bound_mm"], plan["maximum_bound_mm"]
            )
            metric_loss = pinball_loss(prediction, truth.to(device), plan["quantile"])
            tail_loss = torch.nn.functional.binary_cross_entropy_with_logits(
                tail_logits, tail_truth.to(device), pos_weight=weight
            )
            combined = metric_loss + plan["tail_loss_weight"] * tail_loss
            combined.backward()
            optimizer.step()
            metric_total += float(metric_loss.detach()) * len(features)
            tail_total += float(tail_loss.detach()) * len(features)
            combined_total += float(combined.detach()) * len(features)
        history.append(
            {
                "epoch": epoch + 1,
                "metric_loss": metric_total / len(labels),
                "tail_loss": tail_total / len(labels),
                "combined_loss": combined_total / len(labels),
            }
        )
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
    metric_prediction, risk_prediction = infer(head, selection["features"], device, plan)
    rows = [
        {
            **row,
            "multitask_bound_mm": float(bound),
            "tail_risk_logit": float(risk),
            "constant_bound_mm": constant_bound,
            "scores": {
                "multitask_bound_mm": float(bound),
                "tail_risk_logit": float(risk),
            },
        }
        for row, bound, risk in zip(selection["rows"], metric_prediction, risk_prediction)
    ]
    candidate = metric_summary(rows, "multitask_bound_mm", plan["quantile"])
    candidate["conditions"] = {
        condition: metric_summary(
            [row for row in rows if row["condition"] == condition],
            "multitask_bound_mm",
            plan["quantile"],
        )
        for condition in plan["conditions"]
    }
    baseline = metric_summary(rows, "constant_bound_mm", plan["quantile"])
    metric_ranking = ranking(
        rows, "multitask_bound_mm", plan["conditions"], plan["tolerance_mm"]
    )
    auxiliary_ranking = ranking(
        rows, "tail_risk_logit", plan["conditions"], plan["tolerance_mm"]
    )
    checks = decision_checks(candidate, baseline, metric_ranking, plan)
    checks.update(
        {
            "finite_bound": candidate["maximum_bound_mm"] <= plan["maximum_bound_mm"]
            and min(row["multitask_bound_mm"] for row in rows)
            >= plan["minimum_bound_mm"],
            "auxiliary_minimum_scene_auc": auxiliary_ranking["scene_auc"]
            >= plan["auxiliary_minimum_scene_auc"],
            "auxiliary_condition_image_auc": {
                condition: value >= plan["auxiliary_minimum_condition_image_auc"]
                for condition, value in auxiliary_ranking["condition_image_auc"].items()
            },
        }
    )
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
        "metric_prediction_sha256": hashlib.sha256(metric_prediction.tobytes()).hexdigest(),
        "risk_prediction_sha256": hashlib.sha256(risk_prediction.tobytes()).hexdigest(),
        "candidate_summary": candidate,
        "constant_summary": baseline,
        "metric_ranking": metric_ranking,
        "auxiliary_ranking": auxiliary_ranking,
        "checks": checks,
        "passed_selection": checks_pass(checks),
        "model_fits": 1,
        "calibration_fits": 0,
        "optimizer_updates": plan["epochs"] * int(np.ceil(len(labels) / plan["batch_size"])),
        "hardware_writes": 0,
        "physical_movements": 0,
        "qualification_installed": False,
        "limitations": [
            "Synthetic training-selection evidence; no independent calibration or physical-camera claim.",
            "The fixed multitask objective is specific to one frozen pose candidate and synthetic generator.",
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
                    "training_positive_images",
                    "positive_weight",
                    "candidate_summary",
                    "constant_summary",
                    "metric_ranking",
                    "auxiliary_ranking",
                    "checks",
                    "passed_selection",
                )
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    run()

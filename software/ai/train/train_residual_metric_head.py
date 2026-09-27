"""Train one residual corrector over the frozen obstruction-aware metric head."""

import hashlib
import json
import sys
from pathlib import Path

AI = Path(__file__).resolve().parents[1]
ROOT = AI.parents[1]
sys.path[:0] = [str(AI), str(AI.parent / "src")]

import numpy as np
import torch

from train.select_late_fusion_mapping import empirical_percentile, infer
from train.train_bounded_upper_tail_head import bounded_metric
from train.train_obstruction_weighted_metric_head import (
    obstruction_weights,
    weighted_pinball_loss,
)
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
from vision.residual_metric_head import ResidualMetricHead, bounded_multiplier
from vision.synthetic_keyboard import catalog_for_workspace


def corrected_metric(base, raw, minimum_multiplier, maximum_multiplier, minimum, maximum):
    multiplier = bounded_multiplier(raw, minimum_multiplier, maximum_multiplier)
    return torch.clamp(base * multiplier, min=minimum, max=maximum)


def infer_corrected(
    head,
    residual_features,
    base,
    device,
    batch_size,
    minimum_multiplier,
    maximum_multiplier,
    minimum,
    maximum,
):
    head.eval()
    feature_batches = torch.from_numpy(residual_features).split(batch_size)
    base_batches = torch.from_numpy(base).split(batch_size)
    with torch.no_grad():
        return np.concatenate(
            [
                corrected_metric(
                    batch_base.to(device),
                    head(batch_features.to(device)),
                    minimum_multiplier,
                    maximum_multiplier,
                    minimum,
                    maximum,
                )
                .cpu()
                .numpy()
                for batch_features, batch_base in zip(feature_batches, base_batches)
            ]
        )


def utility_proxy(rows, key, risk_reference, maximum_metric, maximum_risk):
    accepted = [
        row
        for row in rows
        if row[key] <= maximum_metric
        and empirical_percentile(risk_reference, row["tail_risk_score"])
        <= maximum_risk
    ]
    return {"images": len(rows), "accepted": len(accepted), "fraction": len(accepted) / len(rows)}


def run():
    path = AI / "train/residual_metric_head_v1_plan.json"
    plan = json.loads(path.read_text())
    for name, digest in plan["file_sha256"].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise ValueError("source mismatch: " + name)
    output = AI / "eval/residual_metric_head_v1_report.json"
    directory = AI / "results/residual_metric_head_v1"
    if output.exists() or directory.exists():
        raise FileExistsError("existing residual metric evidence")

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
    base_head = PoseErrorHead().to(device)
    base_head.load_state_dict(
        torch.load(ROOT / plan["base_checkpoint"], weights_only=True, map_location=device)
    )
    risk_head = PoseErrorHead().to(device)
    risk_head.load_state_dict(
        torch.load(ROOT / plan["risk_checkpoint"], weights_only=True, map_location=device)
    )

    training = build_cohort(
        plan, plan["groups"]["training"], models, catalog, targets, device
    )
    training_base_raw = infer(
        base_head, training["features"], device, plan["batch_size"]
    )
    training_base = bounded_metric(
        torch.from_numpy(training_base_raw),
        plan["minimum_bound_mm"],
        plan["maximum_bound_mm"],
    ).numpy()
    training_risk = infer(
        risk_head, training["features"], device, plan["batch_size"]
    )
    risk_reference = np.sort(training_risk)
    residual_features = np.concatenate(
        (training["features"], training_base[:, None]), axis=1
    ).astype(np.float32)
    mean = residual_features.mean(0)
    scale = residual_features.std(0)
    scale[scale < plan["minimum_feature_scale"]] = plan["minimum_feature_scale"]
    head = ResidualMetricHead(mean, scale).to(device)
    optimizer = torch.optim.AdamW(
        head.parameters(), lr=plan["learning_rate"], weight_decay=plan["weight_decay"]
    )
    weights = obstruction_weights(training["rows"], plan["condition_weights"])
    loader = torch.utils.data.DataLoader(
        torch.utils.data.TensorDataset(
            torch.from_numpy(residual_features),
            torch.from_numpy(training_base.astype(np.float32)),
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
        for features, base, truth, batch_weights in loader:
            optimizer.zero_grad(set_to_none=True)
            prediction = corrected_metric(
                base.to(device),
                head(features.to(device)),
                plan["minimum_multiplier"],
                plan["maximum_multiplier"],
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
    repeated_errors = np.repeat(training["errors"], weights.astype(np.int64))
    constant_bound = float(
        np.quantile(repeated_errors, plan["quantile"], method="higher")
    )
    training_hashes = {
        key: value for key, value in training.items() if key not in ("features", "errors", "rows")
    }
    training_rows = training["rows"]
    del training

    selection = build_cohort(
        plan, plan["groups"]["selection"], models, catalog, targets, device
    )
    selection_base_raw = infer(
        base_head, selection["features"], device, plan["batch_size"]
    )
    selection_base = bounded_metric(
        torch.from_numpy(selection_base_raw),
        plan["minimum_bound_mm"],
        plan["maximum_bound_mm"],
    ).numpy()
    selection_risk = infer(
        risk_head, selection["features"], device, plan["batch_size"]
    )
    selection_residual_features = np.concatenate(
        (selection["features"], selection_base[:, None]), axis=1
    ).astype(np.float32)
    prediction = infer_corrected(
        head,
        selection_residual_features,
        selection_base,
        device,
        plan["batch_size"],
        plan["minimum_multiplier"],
        plan["maximum_multiplier"],
        plan["minimum_bound_mm"],
        plan["maximum_bound_mm"],
    )
    rows = [
        {
            **row,
            "residual_metric_bound_mm": float(value),
            "base_metric_bound_mm": float(base),
            "constant_bound_mm": constant_bound,
            "tail_risk_score": float(risk),
            "scores": {"residual_metric_bound_mm": float(value)},
        }
        for row, value, base, risk in zip(
            selection["rows"], prediction, selection_base, selection_risk
        )
    ]
    candidate = metric_summary(rows, "residual_metric_bound_mm", plan["quantile"])
    prior = metric_summary(rows, "base_metric_bound_mm", plan["quantile"])
    for summary, key in (
        (candidate, "residual_metric_bound_mm"),
        (prior, "base_metric_bound_mm"),
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
        rows, "residual_metric_bound_mm", plan["conditions"], plan["tolerance_mm"]
    )
    proxy = {
        "candidate": utility_proxy(
            rows,
            "residual_metric_bound_mm",
            risk_reference,
            plan["proxy_maximum_metric_mm"],
            plan["maximum_risk_percentile"],
        ),
        "prior": utility_proxy(
            rows,
            "base_metric_bound_mm",
            risk_reference,
            plan["proxy_maximum_metric_mm"],
            plan["maximum_risk_percentile"],
        ),
    }
    proxy["candidate_conditions"] = {
        condition: utility_proxy(
            [row for row in rows if row["condition"] == condition],
            "residual_metric_bound_mm",
            risk_reference,
            plan["proxy_maximum_metric_mm"],
            plan["maximum_risk_percentile"],
        )
        for condition in plan["conditions"]
    }
    checks = decision_checks(candidate, baseline, rankings, plan)
    checks.update(
        {
            "finite_bound": candidate["maximum_bound_mm"] <= plan["maximum_bound_mm"]
            and min(row["residual_metric_bound_mm"] for row in rows)
            >= plan["minimum_bound_mm"],
            "prior_pinball_improvement": candidate["mean_pinball_loss"]
            <= prior["mean_pinball_loss"] * plan["maximum_prior_pinball_ratio"],
            "prior_median_bound_limit": candidate["median_bound_mm"]
            <= prior["median_bound_mm"] * plan["maximum_prior_median_ratio"],
            "partial_coverage_noninferiority": candidate["conditions"]["partial"]["coverage"]
            >= prior["conditions"]["partial"]["coverage"],
            "full_coverage_noninferiority": candidate["conditions"]["full"]["coverage"]
            >= prior["conditions"]["full"]["coverage"],
            "proxy_utility": proxy["candidate"]["fraction"]
            >= plan["minimum_proxy_accepted_fraction"],
            "proxy_utility_improvement": proxy["candidate"]["fraction"]
            >= proxy["prior"]["fraction"] + plan["minimum_proxy_improvement"],
            "proxy_condition_utility": {
                condition: proxy["candidate_conditions"][condition]["fraction"]
                >= plan["minimum_proxy_condition_fraction"][condition]
                for condition in plan["conditions"]
            },
        }
    )
    checks["proxy_condition_utility_pass"] = all(
        checks["proxy_condition_utility"].values()
    )
    report = {
        "plan_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "base_report_sha256": plan["file_sha256"][plan["base_report"]],
        "base_checkpoint_sha256": plan["file_sha256"][plan["base_checkpoint"]],
        "risk_report_sha256": plan["file_sha256"][plan["risk_report"]],
        "risk_checkpoint_sha256": plan["file_sha256"][plan["risk_checkpoint"]],
        "trigger_report_sha256": plan["file_sha256"][plan["trigger_report"]],
        "device": device,
        "model_parameters": sum(parameter.numel() for parameter in head.parameters()),
        "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        "normalization_sha256": hashlib.sha256(
            np.concatenate((mean, scale)).astype(np.float32).tobytes()
        ).hexdigest(),
        "risk_reference_sha256": hashlib.sha256(risk_reference.tobytes()).hexdigest(),
        "training_constant_bound_mm": constant_bound,
        "training_condition_weight_sum": float(weights.sum()),
        "training": training_hashes,
        "training_rows": training_rows,
        "training_base_prediction_sha256": hashlib.sha256(training_base.tobytes()).hexdigest(),
        "training_risk_prediction_sha256": hashlib.sha256(training_risk.tobytes()).hexdigest(),
        "history": history,
        "selection": {
            key: value
            for key, value in selection.items()
            if key not in ("features", "errors", "rows")
        },
        "selection_rows": rows,
        "prediction_sha256": hashlib.sha256(prediction.tobytes()).hexdigest(),
        "base_prediction_sha256": hashlib.sha256(selection_base.tobytes()).hexdigest(),
        "risk_prediction_sha256": hashlib.sha256(selection_risk.tobytes()).hexdigest(),
        "candidate_summary": candidate,
        "prior_summary": prior,
        "constant_summary": baseline,
        "ranking": rankings,
        "utility_proxy": proxy,
        "checks": checks,
        "passed_selection": checks_pass(checks),
        "model_fits": 1,
        "calibration_fits": 0,
        "optimizer_updates": plan["epochs"]
        * int(np.ceil(len(training_rows) / plan["batch_size"])),
        "hardware_writes": 0,
        "physical_movements": 0,
        "qualification_installed": False,
        "limitations": [
            "Synthetic training-selection evidence; no independent calibration or physical-camera claim.",
            "One residual architecture and fixed multiplier interval were evaluated without a sweep.",
            "The training-only risk CDF and low-bound proxy are development metrics, not calibration.",
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
                    "candidate_summary",
                    "prior_summary",
                    "ranking",
                    "utility_proxy",
                    "checks",
                    "passed_selection",
                )
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    run()

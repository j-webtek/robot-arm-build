"""Calibrate one late fusion of frozen metric and tail-risk specialists."""

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

from train.select_ensemble_scale_mapping import evaluate_checks, checks_pass
from train.train_bounded_upper_tail_head import bounded_metric
from train.train_pose_error_head import build_cohort
from vision.diverse_pose_models import MODELS
from vision.evaluate_ensemble_scaled_uncertainty import summarize
from vision.evaluate_grouped_uncertainty import calibrate
from vision.linear_residual_pose import LinearResidualPoseNet
from vision.pose_error_head import PoseErrorHead
from vision.synthetic_keyboard import catalog_for_workspace


def infer(head, features, device, batch_size):
    head.eval()
    with torch.no_grad():
        return np.concatenate(
            [
                head(batch.to(device)).cpu().numpy()
                for batch in torch.from_numpy(features).split(batch_size)
            ]
        )


def empirical_percentile(sorted_reference, value):
    return float(np.searchsorted(sorted_reference, value, side="right") / len(sorted_reference))


def fuse_rows(rows, metric, risk, sorted_reference, gain):
    fused = []
    for row, metric_value, risk_value in zip(rows, metric, risk):
        percentile = empirical_percentile(sorted_reference, risk_value)
        multiplier = math.exp(gain * (2.0 * percentile - 1.0))
        fused.append(
            {
                **row,
                "metric_bound_mm": float(metric_value),
                "tail_risk_score": float(risk_value),
                "tail_risk_percentile": percentile,
                "risk_multiplier": multiplier,
                "scale_mm": float(metric_value) * multiplier,
            }
        )
    return fused


def run():
    path = AI / "train/late_fusion_mapping_v1_plan.json"
    plan = json.loads(path.read_text())
    for name, digest in plan["file_sha256"].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise ValueError("source mismatch: " + name)
    output = AI / "eval/late_fusion_mapping_v1_report.json"
    if output.exists():
        raise FileExistsError(output)

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
    metric_head = PoseErrorHead().to(device)
    metric_head.load_state_dict(
        torch.load(ROOT / plan["metric_checkpoint"], weights_only=True, map_location=device)
    )
    risk_head = PoseErrorHead().to(device)
    risk_head.load_state_dict(
        torch.load(ROOT / plan["risk_checkpoint"], weights_only=True, map_location=device)
    )

    raw = {}
    for name in ("mapping_calibration", "selection"):
        cohort = build_cohort(
            plan, plan["groups"][name], models, catalog, targets, device
        )
        metric_raw = infer(metric_head, cohort["features"], device, plan["batch_size"])
        metric = (
            bounded_metric(
                torch.from_numpy(metric_raw),
                plan["minimum_bound_mm"],
                plan["maximum_bound_mm"],
            )
            .numpy()
        )
        risk = infer(risk_head, cohort["features"], device, plan["batch_size"])
        raw[name] = {
            "rows": cohort["rows"],
            "metric": metric,
            "risk": risk,
            "pixels_sha256": cohort["pixels_sha256"],
            "features_sha256": cohort["features_sha256"],
            "targets_sha256": cohort["targets_sha256"],
            "prediction_sha256": cohort["prediction_sha256"],
            "metric_prediction_sha256": hashlib.sha256(metric.tobytes()).hexdigest(),
            "risk_prediction_sha256": hashlib.sha256(risk.tobytes()).hexdigest(),
        }

    sorted_reference = np.sort(raw["mapping_calibration"]["risk"])
    calibration_rows = fuse_rows(
        raw["mapping_calibration"]["rows"],
        raw["mapping_calibration"]["metric"],
        raw["mapping_calibration"]["risk"],
        sorted_reference,
        plan["risk_gain"],
    )
    start, count = plan["groups"]["mapping_calibration"]
    scene_scores = [
        {
            "seed": seed,
            "normalized_max": max(
                row["error_mm"] / row["scale_mm"]
                for row in calibration_rows
                if row["seed"] == seed
            ),
        }
        for seed in range(start, start + count)
    ]
    rank, quantile = calibrate(
        [row["normalized_max"] for row in scene_scores], plan["alpha"]
    )
    selection_rows = fuse_rows(
        raw["selection"]["rows"],
        raw["selection"]["metric"],
        raw["selection"]["risk"],
        sorted_reference,
        plan["risk_gain"],
    )
    summary = summarize(selection_rows, quantile, plan["tolerance_mm"])
    conditions = {
        condition: summarize(
            [row for row in selection_rows if row["condition"] == condition],
            quantile,
            plan["tolerance_mm"],
        )
        for condition in plan["conditions"]
    }
    checks = evaluate_checks(summary, conditions, plan)
    report = {
        "plan_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "metric_report_sha256": plan["file_sha256"][plan["metric_report"]],
        "risk_report_sha256": plan["file_sha256"][plan["risk_report"]],
        "metric_checkpoint_sha256": plan["file_sha256"][plan["metric_checkpoint"]],
        "risk_checkpoint_sha256": plan["file_sha256"][plan["risk_checkpoint"]],
        "device": device,
        "risk_reference_sha256": hashlib.sha256(sorted_reference.tobytes()).hexdigest(),
        "rank": rank,
        "normalized_quantile": quantile,
        "mapping_calibration": {
            **{key: value for key, value in raw["mapping_calibration"].items() if key not in ("rows", "metric", "risk")},
            "rows": calibration_rows,
            "scene_scores": scene_scores,
        },
        "selection": {
            **{key: value for key, value in raw["selection"].items() if key not in ("rows", "metric", "risk")},
            "rows": selection_rows,
            "summary": summary,
            "conditions": conditions,
        },
        "checks": checks,
        "passed_selection": checks_pass(checks),
        "mapping_fits": 1,
        "new_model_fits": 0,
        "optimizer_updates": 0,
        "hardware_writes": 0,
        "physical_movements": 0,
        "qualification_installed": False,
        "limitations": [
            "Synthetic mapping-calibration and selection evidence; no independent confirmation or physical-camera claim.",
            "One frozen empirical risk-CDF fusion was evaluated without a gain or formula sweep.",
            "Passing permits only a separately frozen independent confirmation study.",
            "No runtime installation, physical qualification, or motion authority.",
        ],
    }
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps(
            {
                "rank": rank,
                "normalized_quantile": quantile,
                "summary": summary,
                "conditions": conditions,
                "checks": checks,
                "passed_selection": report["passed_selection"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    run()

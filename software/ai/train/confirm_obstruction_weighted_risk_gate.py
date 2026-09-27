"""Independently confirm one frozen obstruction-aware acceptance mapping."""

import hashlib
import json
import sys
from pathlib import Path

AI = Path(__file__).resolve().parents[1]
ROOT = AI.parents[1]
sys.path[:0] = [str(AI), str(AI.parent / "src")]

import numpy as np
import torch

from train.select_ensemble_scale_mapping import evaluate_checks, checks_pass
from train.select_late_fusion_mapping import infer
from train.select_risk_gated_metric import attach_outputs, gated_summary
from train.train_bounded_upper_tail_head import bounded_metric
from train.train_pose_error_head import build_cohort
from vision.diverse_pose_models import MODELS
from vision.linear_residual_pose import LinearResidualPoseNet
from vision.pose_error_head import PoseErrorHead
from vision.synthetic_keyboard import catalog_for_workspace


def run():
    path = AI / "train/obstruction_weighted_risk_gate_confirmation_v1_plan.json"
    plan = json.loads(path.read_text())
    for name, digest in plan["file_sha256"].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise ValueError("source mismatch: " + name)
    output = AI / "eval/obstruction_weighted_risk_gate_confirmation_v1_report.json"
    if output.exists():
        raise FileExistsError(output)

    selection_report = json.loads((ROOT / plan["selection_report"]).read_text())
    if selection_report["normalized_quantile"] != plan["normalized_quantile"]:
        raise ValueError("frozen quantile mismatch")
    reference = np.sort(
        np.asarray(
            [
                row["tail_risk_score"]
                for row in selection_report["mapping_calibration"]["rows"]
            ],
            dtype=np.float32,
        )
    )
    reference_sha256 = hashlib.sha256(reference.tobytes()).hexdigest()
    if reference_sha256 != plan["risk_reference_sha256"]:
        raise ValueError("frozen risk reference mismatch")

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

    cohort = build_cohort(
        plan, plan["groups"]["confirmation"], models, catalog, targets, device
    )
    metric_raw = infer(metric_head, cohort["features"], device, plan["batch_size"])
    metric = bounded_metric(
        torch.from_numpy(metric_raw),
        plan["minimum_bound_mm"],
        plan["maximum_bound_mm"],
    ).numpy()
    risk = infer(risk_head, cohort["features"], device, plan["batch_size"])
    rows = attach_outputs(cohort["rows"], metric, risk, reference)
    summary = gated_summary(
        rows,
        plan["normalized_quantile"],
        plan["tolerance_mm"],
        plan["maximum_risk_percentile"],
    )
    conditions = {
        condition: gated_summary(
            [row for row in rows if row["condition"] == condition],
            plan["normalized_quantile"],
            plan["tolerance_mm"],
            plan["maximum_risk_percentile"],
        )
        for condition in plan["conditions"]
    }
    checks = evaluate_checks(summary, conditions, plan)
    report = {
        "plan_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "selection_report_sha256": plan["file_sha256"][plan["selection_report"]],
        "metric_checkpoint_sha256": plan["file_sha256"][plan["metric_checkpoint"]],
        "risk_checkpoint_sha256": plan["file_sha256"][plan["risk_checkpoint"]],
        "device": device,
        "risk_reference_sha256": reference_sha256,
        "normalized_quantile": plan["normalized_quantile"],
        "confirmation": {
            "pixels_sha256": cohort["pixels_sha256"],
            "features_sha256": cohort["features_sha256"],
            "targets_sha256": cohort["targets_sha256"],
            "prediction_sha256": cohort["prediction_sha256"],
            "metric_prediction_sha256": hashlib.sha256(metric.tobytes()).hexdigest(),
            "risk_prediction_sha256": hashlib.sha256(risk.tobytes()).hexdigest(),
            "rows": rows,
            "summary": summary,
            "conditions": conditions,
        },
        "checks": checks,
        "independent_confirmation_passed": checks_pass(checks),
        "mapping_fits": 0,
        "new_model_fits": 0,
        "optimizer_updates": 0,
        "hardware_writes": 0,
        "physical_movements": 0,
        "qualification_installed": False,
        "limitations": [
            "Synthetic independent confirmation; no physical-camera or hardware evidence.",
            "The exact selected mapping was applied once without recalibration or threshold adjustment.",
            "Passing confirms only this synthetic population and does not install runtime authority.",
            "No physical qualification, integration-gate change, or motion authority.",
        ],
    }
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps(
            {
                "summary": summary,
                "conditions": conditions,
                "checks": checks,
                "independent_confirmation_passed": report[
                    "independent_confirmation_passed"
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    run()

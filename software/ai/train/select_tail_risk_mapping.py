"""Select a two-level metric scale for the frozen tail-risk head."""

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
from train.train_pose_error_head import build_cohort
from vision.diverse_pose_models import MODELS
from vision.evaluate_ensemble_scaled_uncertainty import summarize
from vision.evaluate_grouped_uncertainty import calibrate
from vision.linear_residual_pose import LinearResidualPoseNet
from vision.pose_error_head import PoseErrorHead
from vision.synthetic_keyboard import catalog_for_workspace


def scaled_rows(rows, threshold, high_scale_mm):
    return [
        {
            **row,
            "scale_mm": 1.0
            if row["tail_risk_score"] <= threshold
            else high_scale_mm,
        }
        for row in rows
    ]


def infer_risk(head, features, device, batch_size):
    head.eval()
    with torch.no_grad():
        return np.concatenate(
            [
                head(batch.to(device)).cpu().numpy()
                for batch in torch.from_numpy(features).split(batch_size)
            ]
        )


def run():
    path = AI / "train/tail_risk_mapping_v1_plan.json"
    plan = json.loads(path.read_text())
    for name, digest in plan["file_sha256"].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise ValueError("source mismatch: " + name)
    output = AI / "eval/tail_risk_mapping_v1_report.json"
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
    head = PoseErrorHead().to(device)
    head.load_state_dict(
        torch.load(
            ROOT / plan["risk_checkpoint"],
            weights_only=True,
            map_location=device,
        )
    )

    cohorts = {}
    for name in ("mapping_calibration", "selection"):
        cohort = build_cohort(
            plan, plan["groups"][name], models, catalog, targets, device
        )
        risk = infer_risk(head, cohort["features"], device, plan["batch_size"])
        cohorts[name] = {
            "rows": [
                {**row, "tail_risk_score": float(value)}
                for row, value in zip(cohort["rows"], risk)
            ],
            "pixels_sha256": cohort["pixels_sha256"],
            "features_sha256": cohort["features_sha256"],
            "targets_sha256": cohort["targets_sha256"],
            "prediction_sha256": cohort["prediction_sha256"],
            "risk_prediction_sha256": hashlib.sha256(risk.tobytes()).hexdigest(),
        }

    calibration = cohorts["mapping_calibration"]["rows"]
    selection = cohorts["selection"]["rows"]
    start, count = plan["groups"]["mapping_calibration"]
    results = {}
    for fraction in plan["low_risk_fractions"]:
        name = f"fraction_{fraction:g}"
        threshold = float(
            np.quantile(
                [row["tail_risk_score"] for row in calibration],
                fraction,
                method="higher",
            )
        )
        mapped_calibration = scaled_rows(
            calibration, threshold, plan["high_scale_mm"]
        )
        scene_scores = [
            {
                "seed": seed,
                "normalized_max": max(
                    row["error_mm"] / row["scale_mm"]
                    for row in mapped_calibration
                    if row["seed"] == seed
                ),
            }
            for seed in range(start, start + count)
        ]
        rank, quantile = calibrate(
            [row["normalized_max"] for row in scene_scores], plan["alpha"]
        )
        mapped_selection = scaled_rows(
            selection, threshold, plan["high_scale_mm"]
        )
        summary = summarize(mapped_selection, quantile, plan["tolerance_mm"])
        conditions = {
            condition: summarize(
                [row for row in mapped_selection if row["condition"] == condition],
                quantile,
                plan["tolerance_mm"],
            )
            for condition in plan["conditions"]
        }
        checks = evaluate_checks(summary, conditions, plan)
        results[name] = {
            "low_risk_fraction": fraction,
            "risk_threshold": threshold,
            "rank": rank,
            "normalized_quantile": quantile,
            "mapping_calibration_scene_scores": scene_scores,
            "selection_summary": summary,
            "selection_conditions": conditions,
            "checks": checks,
            "passed": checks_pass(checks),
        }
        print(name, summary, checks, flush=True)

    passing = [name for name, result in results.items() if result["passed"]]
    selected = (
        max(
            passing,
            key=lambda name: (
                results[name]["selection_summary"]["accepted_fraction"],
                -results[name]["low_risk_fraction"],
            ),
        )
        if passing
        else None
    )
    report = {
        "plan_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "risk_checkpoint_sha256": plan["file_sha256"][plan["risk_checkpoint"]],
        "device": device,
        "cohorts": cohorts,
        "results": results,
        "selected_mapping": selected,
        "passed_selection": selected is not None,
        "mapping_fits": len(plan["low_risk_fractions"]),
        "new_model_fits": 0,
        "optimizer_updates": 0,
        "hardware_writes": 0,
        "physical_movements": 0,
        "qualification_installed": False,
        "limitations": [
            "Synthetic mapping-selection evidence; no independent confirmation or physical-camera claim.",
            "Four thresholds share one mapping-calibration and one selection population.",
            "Passing permits only a separately frozen independent confirmation study.",
            "No runtime installation, physical qualification, or motion authority.",
        ],
    }
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({key: report[key] for key in ("results", "selected_mapping", "passed_selection")}, indent=2))


if __name__ == "__main__":
    run()

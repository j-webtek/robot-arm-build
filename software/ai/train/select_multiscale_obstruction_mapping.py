"""Select a low-gain mapping for frozen obstruction probability and disagreement."""

import hashlib
import json
import sys
from pathlib import Path

AI = Path(__file__).resolve().parents[1]
ROOT = AI.parents[1]
sys.path[:0] = [str(AI), str(AI.parent / "src")]

import torch

from train.select_ensemble_scale_mapping import evaluate_checks, checks_pass
from train.train_obstruction_risk_scale import probabilities, raw_set
from vision.diverse_pose_models import MODELS
from vision.evaluate_ensemble_scaled_uncertainty import infer_cohort, summarize
from vision.evaluate_grouped_uncertainty import calibrate
from vision.linear_residual_pose import LinearResidualPoseNet
from vision.multiscale_obstruction_model import MultiScaleObstructionNet
from vision.synthetic_keyboard import catalog_for_workspace


def scaled_rows(rows, gain, floor_mm):
    return [
        {
            **row,
            "scale_mm": max(row["disagreement_mm"], floor_mm)
            * (1.0 + gain * row["obstruction_probability"]),
        }
        for row in rows
    ]


def run():
    path = AI / "train/multiscale_obstruction_mapping_v1_plan.json"
    plan = json.loads(path.read_text())
    for name, digest in plan["file_sha256"].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise ValueError("source mismatch: " + name)
    output = AI / "eval/multiscale_obstruction_mapping_v1_report.json"
    if output.exists():
        raise FileExistsError(output)

    torch.set_num_threads(4)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    catalog = catalog_for_workspace(ROOT)
    targets = list(catalog.keyboard_targets.values())
    pose_models = {
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
        pose_models[name] = model
    obstruction_model = MultiScaleObstructionNet().to(device)
    obstruction_model.load_state_dict(
        torch.load(
            ROOT / plan["classifier_checkpoint"],
            weights_only=True,
            map_location=device,
        )
    )

    cohorts = {}
    for cohort_name in ("mapping_calibration", "selection"):
        group = plan["groups"][cohort_name]
        base = infer_cohort(plan, group, pose_models, catalog, targets, device)
        raw, labels, order = raw_set(*group, plan, catalog)
        probability = probabilities(
            obstruction_model, raw, device, plan["batch_size"]
        )
        if order != [
            (row["seed"], row["style"], row["condition"])
            for row in base["rows"]
        ]:
            raise ValueError("row order mismatch")
        cohorts[cohort_name] = {
            "rows": [
                {**row, "obstruction_probability": float(value)}
                for row, value in zip(base["rows"], probability)
            ],
            "raw_pixels_sha256": hashlib.sha256(raw.tobytes()).hexdigest(),
            "normalized_pixels_sha256": base["pixels_sha256"],
            "prediction_sha256": base["prediction_sha256"],
            "obstruction_prediction_sha256": hashlib.sha256(
                probability.tobytes()
            ).hexdigest(),
            "labels_sha256": hashlib.sha256(labels.tobytes()).hexdigest(),
        }

    start, count = plan["groups"]["mapping_calibration"]
    results = {}
    for gain in plan["gains"]:
        name = f"gain_{gain:g}"
        calibration_rows = scaled_rows(
            cohorts["mapping_calibration"]["rows"],
            gain,
            plan["scale_floor_mm"],
        )
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
        selection_rows = scaled_rows(
            cohorts["selection"]["rows"], gain, plan["scale_floor_mm"]
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
        decision = evaluate_checks(summary, conditions, plan)
        results[name] = {
            "gain": gain,
            "rank": rank,
            "normalized_quantile": quantile,
            "mapping_calibration_scene_scores": scene_scores,
            "selection_summary": summary,
            "selection_conditions": conditions,
            "checks": decision,
            "passed": checks_pass(decision),
        }
        print(name, summary, decision, flush=True)

    passing = [name for name, result in results.items() if result["passed"]]
    selected = (
        max(
            passing,
            key=lambda name: (
                results[name]["selection_summary"]["accepted_fraction"],
                -results[name]["gain"],
            ),
        )
        if passing
        else None
    )
    result = {
        "plan_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "prior_report_sha256": plan["file_sha256"][plan["prior_report"]],
        "classifier_checkpoint_sha256": plan["file_sha256"][
            plan["classifier_checkpoint"]
        ],
        "device": device,
        "cohorts": cohorts,
        "results": results,
        "selected_mapping": selected,
        "passed_selection": selected is not None,
        "calibration_fits": len(plan["gains"]),
        "new_model_fits": 0,
        "optimizer_updates": 0,
        "hardware_writes": 0,
        "physical_movements": 0,
        "qualification_installed": False,
        "limitations": [
            "Training-only synthetic mapping selection; no confirmation or physical-camera claim.",
            "The frozen classifier is evaluated without retraining or threshold selection.",
            "Four fixed mappings share one mapping-calibration and one selection cohort.",
            "No runtime installation, physical qualification, or motion authority.",
        ],
    }
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps(
            {
                "results": {
                    name: {
                        key: value[key]
                        for key in (
                            "gain",
                            "normalized_quantile",
                            "selection_summary",
                            "selection_conditions",
                            "checks",
                            "passed",
                        )
                    }
                    for name, value in results.items()
                },
                "selected_mapping": selected,
                "passed_selection": selected is not None,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    run()

"""Training-only selection of a monotonic ensemble-disagreement mapping."""

import hashlib
import json
import sys
from pathlib import Path

AI = Path(__file__).resolve().parents[1]
ROOT = AI.parents[1]
sys.path[:0] = [str(AI), str(AI.parent / "src")]

import torch

from vision.diverse_pose_models import MODELS
from vision.evaluate_ensemble_scaled_uncertainty import infer_cohort, summarize
from vision.evaluate_grouped_uncertainty import calibrate
from vision.linear_residual_pose import LinearResidualPoseNet
from vision.synthetic_keyboard import catalog_for_workspace


def scaled_rows(rows, power, floor_mm):
    return [
        {
            **row,
            "scale_mm": floor_mm
            * (max(row["disagreement_mm"], floor_mm) / floor_mm) ** power,
        }
        for row in rows
    ]


def evaluate_checks(summary, conditions, plan):
    return {
        "overall_scene_coverage": summary["scene_coverage"]
        >= plan["minimum_scene_coverage"],
        "overall_accepted_fraction": summary["accepted_fraction"]
        >= plan["minimum_accepted_fraction"],
        "overall_accepted_image_coverage": summary["accepted_image_coverage"]
        is not None
        and summary["accepted_image_coverage"]
        >= plan["minimum_accepted_image_coverage"],
        "overall_accepted_scene_coverage": summary["accepted_scene_coverage"]
        is not None
        and summary["accepted_scene_coverage"]
        >= plan["minimum_accepted_scene_coverage"],
        "zero_accepted_errors_over_tolerance": summary[
            "accepted_errors_over_tolerance"
        ]
        == 0,
        "condition_accepted_fraction": {
            condition: values["accepted_fraction"]
            >= plan["minimum_condition_accepted_fraction"]
            for condition, values in conditions.items()
        },
        "condition_accepted_image_coverage": {
            condition: values["accepted_image_coverage"] is not None
            and values["accepted_image_coverage"]
            >= plan["minimum_accepted_image_coverage"]
            for condition, values in conditions.items()
        },
    }


def checks_pass(checks):
    return (
        all(value for value in checks.values() if isinstance(value, bool))
        and all(checks["condition_accepted_fraction"].values())
        and all(checks["condition_accepted_image_coverage"].values())
    )


def run():
    path = AI / "train/ensemble_scale_mapping_v1_plan.json"
    plan = json.loads(path.read_text())
    for name, digest in plan["file_sha256"].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise ValueError("source mismatch: " + name)
    output = AI / "eval/ensemble_scale_mapping_v1_report.json"
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

    base_plan = {**plan, "scale_floor_mm": plan["scale_floor_mm"]}
    mapping_calibration = infer_cohort(
        base_plan,
        plan["groups"]["mapping_calibration"],
        models,
        catalog,
        targets,
        device,
    )
    selection = infer_cohort(
        base_plan,
        plan["groups"]["selection"],
        models,
        catalog,
        targets,
        device,
    )
    start, count = plan["groups"]["mapping_calibration"]
    results = {}
    for power in plan["powers"]:
        name = f"power_{power:g}"
        calibration_rows = scaled_rows(
            mapping_calibration["rows"], power, plan["scale_floor_mm"]
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
        candidate_rows = scaled_rows(
            selection["rows"], power, plan["scale_floor_mm"]
        )
        summary = summarize(candidate_rows, quantile, plan["tolerance_mm"])
        conditions = {
            condition: summarize(
                [row for row in candidate_rows if row["condition"] == condition],
                quantile,
                plan["tolerance_mm"],
            )
            for condition in plan["conditions"]
        }
        checks = evaluate_checks(summary, conditions, plan)
        results[name] = {
            "power": power,
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
                -results[name]["power"],
            ),
        )
        if passing
        else None
    )
    result = {
        "plan_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "failed_confirmation_report_sha256": plan["file_sha256"][
            plan["failed_confirmation_report"]
        ],
        "device": device,
        "mapping_calibration": mapping_calibration,
        "selection": selection,
        "results": results,
        "selected_mapping": selected,
        "passed_selection": selected is not None,
        "calibration_fits": len(plan["powers"]),
        "new_model_fits": 0,
        "optimizer_updates": 0,
        "hardware_writes": 0,
        "physical_movements": 0,
        "qualification_installed": False,
        "limitations": [
            "Training-only synthetic mapping selection; no fresh calibration or confirmation claim.",
            "Five fixed monotonic powers share one mapping-calibration and one selection cohort.",
            "The selected mapping, if any, requires a new frozen calibration and confirmation chain.",
            "No runtime installation, physical qualification, or motion authority.",
        ],
    }
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps(
            {
                "results": {
                    name: {
                        "power": value["power"],
                        "normalized_quantile": value["normalized_quantile"],
                        "selection_summary": value["selection_summary"],
                        "checks": value["checks"],
                        "passed": value["passed"],
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

"""Calibrate and confirm a frozen ensemble-disagreement uncertainty scale."""

import hashlib
import json
import sys
from pathlib import Path

AI = Path(__file__).resolve().parents[1]
ROOT = AI.parents[1]
sys.path[:0] = [str(AI), str(AI.parent / "src")]

import torch

from train.train_diverse_pose_ensemble import (
    pairwise_disagreement,
    predict,
    render_set,
    score_predictions,
)
from vision.diverse_pose_models import MODELS
from vision.evaluate_grouped_uncertainty import calibrate, wilson
from vision.linear_residual_pose import LinearResidualPoseNet
from vision.synthetic_keyboard import catalog_for_workspace


def summarize(rows, quantile, tolerance):
    def radius(row):
        return None if quantile is None else quantile * row["scale_mm"]

    def violation(row):
        bound = radius(row)
        return bound is not None and row["error_mm"] > bound

    accepted = [
        row for row in rows if radius(row) is not None and radius(row) <= tolerance
    ]
    seeds = {row["seed"] for row in rows}
    bad_seeds = {row["seed"] for row in rows if violation(row)}
    accepted_seeds = {row["seed"] for row in accepted}
    accepted_bad_seeds = {row["seed"] for row in accepted if violation(row)}
    accepted_covered = sum(not violation(row) for row in accepted)
    return {
        "images": len(rows),
        "scenes": len(seeds),
        "scene_coverage": (len(seeds) - len(bad_seeds)) / len(seeds),
        "scene_wilson95": wilson(len(seeds) - len(bad_seeds), len(seeds)),
        "image_coverage": sum(not violation(row) for row in rows) / len(rows),
        "accepted_images": len(accepted),
        "accepted_fraction": len(accepted) / len(rows),
        "accepted_image_coverage": (
            accepted_covered / len(accepted) if accepted else None
        ),
        "accepted_bound_violations": sum(violation(row) for row in accepted),
        "accepted_errors_over_tolerance": sum(
            row["error_mm"] > tolerance for row in accepted
        ),
        "scenes_with_acceptance": len(accepted_seeds),
        "accepted_scene_coverage": (
            (len(accepted_seeds) - len(accepted_bad_seeds)) / len(accepted_seeds)
            if accepted_seeds
            else None
        ),
        "accepted_scene_wilson95": (
            wilson(
                len(accepted_seeds) - len(accepted_bad_seeds),
                len(accepted_seeds),
            )
            if accepted_seeds
            else None
        ),
    }


def infer_cohort(plan, group, models, catalog, targets, device):
    pixels, _, metadata = render_set(*group, plan, catalog)
    predictions = {
        name: predict(model, pixels, device, plan["batch_size"])
        for name, model in models.items()
    }
    candidate_rows, _ = score_predictions(
        predictions["candidate"], metadata, targets, plan["conditions"]
    )
    rows = []
    for index, (seed, style, condition, _) in enumerate(metadata):
        disagreement = pairwise_disagreement(predictions, index, targets)
        rows.append(
            {
                "seed": seed,
                "style": style,
                "condition": condition,
                "error_mm": candidate_rows[index]["maximum_mm"],
                "disagreement_mm": disagreement,
                "scale_mm": max(disagreement, plan["scale_floor_mm"]),
            }
        )
    return {
        "rows": rows,
        "pixels_sha256": hashlib.sha256(pixels.tobytes()).hexdigest(),
        "prediction_sha256": {
            name: hashlib.sha256(values.tobytes()).hexdigest()
            for name, values in predictions.items()
        },
    }


def run():
    path = AI / "eval/ensemble_scaled_uncertainty_v1_plan.json"
    plan = json.loads(path.read_text())
    for name, digest in plan["file_sha256"].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise ValueError("source mismatch: " + name)
    output = AI / "eval/ensemble_scaled_uncertainty_v1_report.json"
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

    calibration = infer_cohort(
        plan, plan["groups"]["calibration"], models, catalog, targets, device
    )
    start, count = plan["groups"]["calibration"]
    scene_scores = [
        {
            "seed": seed,
            "normalized_max": max(
                row["error_mm"] / row["scale_mm"]
                for row in calibration["rows"]
                if row["seed"] == seed
            ),
        }
        for seed in range(start, start + count)
    ]
    rank, quantile = calibrate(
        [row["normalized_max"] for row in scene_scores], plan["alpha"]
    )
    calibration["scene_scores"] = scene_scores
    print("calibration rank", rank, "quantile", quantile, flush=True)

    confirmation = infer_cohort(
        plan, plan["groups"]["confirmation"], models, catalog, targets, device
    )
    summary = summarize(confirmation["rows"], quantile, plan["tolerance_mm"])
    by_condition = {
        condition: summarize(
            [row for row in confirmation["rows"] if row["condition"] == condition],
            quantile,
            plan["tolerance_mm"],
        )
        for condition in plan["conditions"]
    }
    checks = {
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
            for condition, values in by_condition.items()
        },
        "condition_accepted_image_coverage": {
            condition: values["accepted_image_coverage"] is not None
            and values["accepted_image_coverage"]
            >= plan["minimum_accepted_image_coverage"]
            for condition, values in by_condition.items()
        },
    }
    passed = (
        all(value for value in checks.values() if isinstance(value, bool))
        and all(checks["condition_accepted_fraction"].values())
        and all(checks["condition_accepted_image_coverage"].values())
    )
    confirmation["summary"] = summary
    confirmation["conditions"] = by_condition
    result = {
        "plan_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "development_report_sha256": plan["file_sha256"][plan["development_report"]],
        "device": device,
        "rank": rank,
        "normalized_quantile": quantile,
        "calibration": calibration,
        "confirmation": confirmation,
        "checks": checks,
        "passed": passed,
        "calibration_fits": 1,
        "new_model_fits": 0,
        "optimizer_updates": 0,
        "hardware_writes": 0,
        "physical_movements": 0,
        "qualification_installed": False,
        "limitations": [
            "Synthetic marginal and accepted-subset coverage do not establish physical safety.",
            "The fixed 3 mm research tolerance is not a measured contact margin.",
            "Calibration and confirmation ranges are consumed; no tuning after outcomes.",
            "No runtime installation, ModelMotionBatch qualification, or motion authority.",
        ],
    }
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps(
            {
                "rank": rank,
                "normalized_quantile": quantile,
                "summary": summary,
                "conditions": by_condition,
                "checks": checks,
                "passed": passed,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    run()

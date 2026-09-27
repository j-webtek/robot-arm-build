"""Fresh grouped development evaluation of the selected compact ensemble."""

import hashlib
import json
import sys
from pathlib import Path

AI = Path(__file__).resolve().parents[1]
ROOT = AI.parents[1]
sys.path[:0] = [str(AI), str(AI.parent / "src")]

import torch

from train.compare_backbone_uncertainty import scene_metrics
from train.train_diverse_pose_ensemble import (
    pairwise_disagreement,
    predict,
    render_set,
    score_predictions,
)
from vision.diverse_pose_models import MODELS
from vision.linear_residual_pose import LinearResidualPoseNet
from vision.synthetic_keyboard import catalog_for_workspace


def run():
    path = AI / "eval/appearance_robust_ensemble_development_v1_plan.json"
    plan = json.loads(path.read_text())
    for name, digest in plan["file_sha256"].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise ValueError("source mismatch: " + name)
    output = AI / "eval/appearance_robust_ensemble_development_v1_report.json"
    if output.exists():
        raise FileExistsError(output)

    torch.set_num_threads(4)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    catalog = catalog_for_workspace(ROOT)
    targets = list(catalog.keyboard_targets.values())
    pixels, _, metadata = render_set(*plan["development_groups"], plan, catalog)

    candidate_model = LinearResidualPoseNet.from_export(
        torch.load(ROOT / plan["candidate_artifact"], weights_only=True, map_location="cpu")
    ).to(device)
    predictions = {
        "candidate": predict(candidate_model, pixels, device, plan["batch_size"])
    }
    for name, checkpoint_path in plan["selected_checkpoints"].items():
        model = MODELS[name]().to(device)
        model.load_state_dict(
            torch.load(ROOT / checkpoint_path, weights_only=True, map_location=device)
        )
        predictions[name] = predict(model, pixels, device, plan["batch_size"])

    scores = {}
    rows_by_model = {}
    for name, values in predictions.items():
        rows_by_model[name], scores[name] = score_predictions(
            values, metadata, targets, plan["conditions"]
        )
    disagreement_rows = [
        dict(
            seed=seed,
            style=style,
            condition=condition,
            error_mm=rows_by_model["candidate"][index]["maximum_mm"],
            ensemble_disagreement_mm=pairwise_disagreement(predictions, index, targets),
        )
        for index, (seed, style, condition, _) in enumerate(metadata)
    ]
    ranking = scene_metrics(
        disagreement_rows,
        "ensemble_disagreement_mm",
        plan["retention_fractions"],
    )
    curve = {point["requested_fraction"]: point for point in ranking["retention_curve"]}
    checks = {
        "scene_tail_auc": ranking["tail_auc"] >= plan["minimum_scene_tail_auc"],
        "retention_0_25_relative": curve[0.25]["tail_rate"]
        <= plan["retention_0_25_max_relative"] * ranking["tail_rate"],
        "retention_0_5_relative": curve[0.5]["tail_rate"]
        <= plan["retention_0_5_max_relative"] * ranking["tail_rate"],
        "member_mean_error": {
            name: {
                condition: scores[name][condition]["mean_mm"]
                <= plan["member_max_mean_ratio"] * scores["candidate"][condition]["mean_mm"]
                for condition in plan["conditions"]
            }
            for name in plan["selected_checkpoints"]
        },
        "member_appearance_error": {
            name: scores[name]["appearance_shift"]["mean_mm"]
            <= plan["member_appearance_max_mean_ratio"]
            * scores["candidate"]["appearance_shift"]["mean_mm"]
            for name in plan["selected_checkpoints"]
        },
    }
    passed = (
        checks["scene_tail_auc"]
        and checks["retention_0_25_relative"]
        and checks["retention_0_5_relative"]
        and all(all(values.values()) for values in checks["member_mean_error"].values())
        and all(checks["member_appearance_error"].values())
    )
    result = {
        "plan_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "selection_report_sha256": plan["file_sha256"][plan["selection_report"]],
        "device": device,
        "development_images": len(pixels),
        "development_pixels_sha256": hashlib.sha256(pixels.tobytes()).hexdigest(),
        "prediction_sha256": {
            name: hashlib.sha256(values.tobytes()).hexdigest()
            for name, values in predictions.items()
        },
        "scores": scores,
        "candidate_rows": rows_by_model["candidate"],
        "disagreement_rows": disagreement_rows,
        "scene_ranking": ranking,
        "checks": checks,
        "passed_development": passed,
        "new_fits": 0,
        "optimizer_updates": 0,
        "calibration_fits": 0,
        "hardware_writes": 0,
        "physical_movements": 0,
        "qualification_installed": False,
        "limitations": [
            "Fresh grouped synthetic development evidence from the same renderer; no physical-camera evidence.",
            "The selected checkpoints and all rules were frozen before this one evaluation.",
            "Development passage would permit only a separately frozen calibration and confirmation chain.",
            "Ensemble dispersion is uncalibrated and cannot authorize motion.",
        ],
    }
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps(
            {
                "scores": scores,
                "scene_ranking": ranking,
                "checks": checks,
                "passed_development": passed,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    run()

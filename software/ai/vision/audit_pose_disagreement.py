"""Zero-fit geometric disagreement audit between two frozen pose outputs."""

import hashlib
import json
import sys
from pathlib import Path

AI = Path(__file__).resolve().parents[1]
ROOT = AI.parents[1]
sys.path[:0] = [str(AI), str(AI.parent / "src")]

import numpy as np
import torch

from train.compare_backbone_uncertainty import scene_metrics
from vision.diagnose_pose_tail import decompose
from vision.evaluate_dark_only_normalization import normalize
from vision.landmark_occlusions import render_controlled
from vision.linear_residual_pose import LinearResidualPoseNet
from vision.synthetic_keyboard import catalog_for_workspace
from vision.train_pose import _pose_from_prediction


def disagreement(baseline_prediction, candidate_prediction, targets):
    baseline_pose = _pose_from_prediction(baseline_prediction)
    candidate_pose = _pose_from_prediction(candidate_prediction)
    return decompose(candidate_pose, baseline_pose, targets)["maximum_mm"]


def run():
    path = AI / "eval/pose_disagreement_v1_plan.json"
    plan = json.loads(path.read_text())
    for name, digest in plan["file_sha256"].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise ValueError("source mismatch: " + name)
    out = AI / "eval/pose_disagreement_v1_report.json"
    if out.exists():
        raise FileExistsError(out)

    source = json.loads((ROOT / plan["source_report"]).read_text())
    rows = source["rows"]
    if len(rows) != 4800:
        raise ValueError("unexpected source population")
    model = LinearResidualPoseNet.from_export(
        torch.load(ROOT / plan["artifact"], weights_only=True, map_location="cpu")
    )
    torch.set_num_threads(4)
    catalog = catalog_for_workspace(ROOT)
    targets = list(catalog.keyboard_targets.values())
    pixels = []
    meta = []
    start, count = plan["groups"]
    for seed in range(start, start + count):
        for style in plan["styles"]:
            for condition in plan["conditions"]:
                image, label, _ = render_controlled(seed, catalog, condition, style)
                image, _ = normalize(image)
                pixels.append(np.asarray(image.resize((128, 96))).transpose(2, 0, 1).copy())
                meta.append((seed, style, condition, label["pose"]))
    if [(seed, style, condition) for seed, style, condition, _ in meta] != [
        (row["seed"], row["style"], row["condition"]) for row in rows
    ]:
        raise ValueError("source row order mismatch")
    pixels = np.stack(pixels)
    if hashlib.sha256(pixels.tobytes()).hexdigest() != source["pixels_sha256"]:
        raise ValueError("rendered pixels differ from source evidence")
    baseline = []
    candidate = []
    with torch.no_grad():
        for batch in torch.from_numpy(pixels).split(64):
            normalized = batch.float() / 255
            baseline.append(model.backbone(normalized).numpy())
            candidate.append(model(normalized).numpy())
    baseline = np.concatenate(baseline)
    candidate = np.concatenate(candidate)

    result_rows = []
    maximum_error_delta = 0.0
    for index, (old, (_, _, _, truth)) in enumerate(zip(rows, meta)):
        candidate_metrics = decompose(
            _pose_from_prediction(candidate[index]), truth, targets
        )
        maximum_error_delta = max(
            maximum_error_delta,
            abs(candidate_metrics["maximum_mm"] - old["error_mm"]),
        )
        result_rows.append(
            dict(
                old,
                pose_disagreement_mm=float(
                    disagreement(baseline[index], candidate[index], targets)
                ),
            )
        )
    if maximum_error_delta > plan["error_recount_tolerance_mm"]:
        raise ValueError("candidate error recount differs from source evidence")

    ranking = {
        "pose_disagreement": scene_metrics(
            result_rows, "pose_disagreement_mm", plan["retention_fractions"]
        ),
        "nonlinear_regression": scene_metrics(
            result_rows, "nonlinear_scale_mm", plan["retention_fractions"]
        ),
    }
    candidate_curve = {
        point["requested_fraction"]: point
        for point in ranking["pose_disagreement"]["retention_curve"]
    }
    reference_curve = {
        point["requested_fraction"]: point
        for point in ranking["nonlinear_regression"]["retention_curve"]
    }
    checks = {
        "scene_tail_auc": ranking["pose_disagreement"]["tail_auc"]
        > ranking["nonlinear_regression"]["tail_auc"],
        "retention_tail_rate_0_25": candidate_curve[0.25]["tail_rate"]
        < reference_curve[0.25]["tail_rate"],
        "retention_tail_rate_0_5": candidate_curve[0.5]["tail_rate"]
        < reference_curve[0.5]["tail_rate"],
    }
    result = {
        "plan_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "source_report_sha256": plan["file_sha256"][plan["source_report"]],
        "pixels_sha256": source["pixels_sha256"],
        "baseline_predictions_sha256": hashlib.sha256(baseline.tobytes()).hexdigest(),
        "candidate_predictions_sha256": hashlib.sha256(candidate.tobytes()).hexdigest(),
        "candidate_error_recount_max_delta_mm": maximum_error_delta,
        "rows": result_rows,
        "scene_ranking": ranking,
        "checks": checks,
        "passed": all(checks.values()),
        "new_fits": 0,
        "new_images": 0,
        "calibration_fits": 0,
        "hardware_writes": 0,
        "physical_movements": 0,
        "qualification_installed": False,
        "limitations": [
            "Training-only grouped diagnostic; no independent confirmation or calibration.",
            "Baseline and residual candidate share a backbone, so disagreement is not an independent ensemble.",
            "Fixed retention comparisons are diagnostics, not selected runtime thresholds.",
            "Synthetic truth supplies evaluation labels but is absent from the disagreement score.",
            "Passing would justify only a separately specified calibration experiment.",
        ],
    }
    out.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"scene_ranking": ranking, "checks": checks, "passed": result["passed"]}, indent=2))


if __name__ == "__main__":
    run()

"""Build a held-out synthetic localization bundle from actual pose inference."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import sys

AI = Path(__file__).resolve().parents[1]
ROOT = AI.parents[1]
sys.path[:0] = [str(AI), str(AI.parent / "src")]

import numpy as np
import torch

from rocell_ai.precision_adapter_v2 import PoseModelOutputV2, adapt_pose_model_output
from rocell_ai.scene_observation import canonical_hash
from train.train_diverse_pose_ensemble import predict, render_set
from vision.linear_residual_pose import LinearResidualPoseNet
from vision.synthetic_keyboard import catalog_for_workspace, transform_target
from vision.train_pose import _pose_from_prediction


def _dataset_records(pixels, predictions, metadata, catalog):
    records = []
    target_ids = sorted(catalog.keyboard_targets)
    for index, (raw, (seed, style, condition, truth)) in enumerate(
        zip(predictions, metadata)
    ):
        predicted_pose = _pose_from_prediction(raw)
        errors = {}
        for target_id in target_ids:
            region = catalog.keyboard_targets[target_id]
            actual = transform_target(
                region.center.x, region.center.y, truth[:2], truth[2]
            )
            estimated = transform_target(
                region.center.x,
                region.center.y,
                predicted_pose[:2],
                predicted_pose[2],
            )
            errors[target_id] = math.dist(actual, estimated)
        records.append(
            {
                "case_id": f"s{seed}-{style}-{condition}",
                "seed": seed,
                "style": style,
                "condition": condition,
                "input_pixels_sha256": hashlib.sha256(pixels[index].tobytes()).hexdigest(),
                "truth_pose": list(truth),
                "normalized_model_output": [float(value) for value in raw],
                "predicted_pose": list(predicted_pose),
                "target_errors_mm": errors,
                "maximum_error_mm": max(errors.values()),
            }
        )
    return records


def evaluate(plan_path: Path) -> dict[str, object]:
    plan = json.loads(plan_path.read_text())
    for name, digest in plan["file_sha256"].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise ValueError("source mismatch: " + name)
    checkpoint = ROOT / plan["model_checkpoint"]
    if hashlib.sha256(checkpoint.read_bytes()).hexdigest() != plan["model_checkpoint_sha256"]:
        raise ValueError("model checkpoint mismatch")
    catalog = catalog_for_workspace(ROOT)
    if catalog.content_sha256 != plan["target_catalog_sha256"]:
        raise ValueError("target catalog mismatch")
    calibration_start, calibration_count = plan["calibration_group"]
    evaluation_start, evaluation_count = plan["evaluation_group"]
    if set(range(calibration_start, calibration_start + calibration_count)) & set(
        range(evaluation_start, evaluation_start + evaluation_count)
    ):
        raise ValueError("calibration and evaluation seeds overlap")

    torch.set_num_threads(4)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = LinearResidualPoseNet.from_export(
        torch.load(checkpoint, weights_only=True, map_location="cpu")
    ).to(device)
    datasets = {}
    for name, group in (
        ("calibration", plan["calibration_group"]),
        ("evaluation", plan["evaluation_group"]),
    ):
        pixels, _, metadata = render_set(*group, plan, catalog)
        predictions = predict(model, pixels, device, plan["batch_size"])
        datasets[name] = _dataset_records(pixels, predictions, metadata, catalog)

    calibration = datasets["calibration"]
    evaluation = datasets["evaluation"]
    calibration_dataset_sha256 = canonical_hash(calibration)
    evaluation_dataset_sha256 = canonical_hash(evaluation)
    if calibration_dataset_sha256 == evaluation_dataset_sha256:
        raise ValueError("calibration and evaluation dataset hashes must differ")
    radius = max(row["maximum_error_mm"] for row in calibration)
    covered = sum(row["maximum_error_mm"] <= radius for row in evaluation)
    measured_coverage = covered / len(evaluation)
    target_ids = sorted(catalog.keyboard_targets)

    per_target = {}
    adapter_abstentions = {target_id: 0 for target_id in target_ids}
    for row in evaluation:
        output = PoseModelOutputV2(
            model_id=plan["model_id"],
            model_sha256=plan["model_checkpoint_sha256"],
            frame_id="eval-" + row["case_id"],
            image_sha256=row["input_pixels_sha256"],
            normalized_pose=tuple(row["normalized_model_output"]),
            evaluated_at_epoch_ms=plan["replay_epoch_ms"],
            observation_confidence=plan["fixture_observation_confidence"],
        )
        adapted = adapt_pose_model_output(
            ROOT,
            output,
            domain_id=plan["domain_id"],
            required_target_ids=target_ids,
            trusted_qualifications={},
            expected_domain_id=plan["domain_id"],
            now_epoch_ms=plan["replay_epoch_ms"],
        )
        if adapted.accepted or adapted.precision_observation["abstain_reasons"] != [
            "localization_uncalibrated"
        ]:
            raise ValueError("empty qualification registry did not fail closed")
        for target_id in target_ids:
            adapter_abstentions[target_id] += 1

    for target_id in target_ids:
        errors = [row["target_errors_mm"][target_id] for row in evaluation]
        failure_ids = [
            row["case_id"]
            for row in evaluation
            if row["target_errors_mm"][target_id] > radius
        ]
        per_target[target_id] = {
            "sample_count": len(errors),
            "errors_mm": errors,
            "failure_count": len(failure_ids),
            "failure_case_ids": failure_ids,
            "abstention_count": adapter_abstentions[target_id],
            "maximum_error_mm": max(errors),
            "mean_error_mm": float(np.mean(errors)),
            "p95_error_mm": float(np.percentile(errors, 95)),
        }

    qualification_core = {
        "schema": "rocell.ai_localization_qualification.v0",
        "scope": "SYNTHETIC_OFFLINE_ONLY",
        "model_sha256": plan["model_checkpoint_sha256"],
        "target_catalog_sha256": catalog.content_sha256,
        "calibration_dataset_sha256": calibration_dataset_sha256,
        "evaluation_dataset_sha256": evaluation_dataset_sha256,
        "domain_id": plan["domain_id"],
        "coverage_probability": plan["declared_coverage_probability"],
        "error_bound_mm": radius,
        "target_ids": target_ids,
    }
    qualification = {
        **qualification_core,
        "qualification_sha256": canonical_hash(qualification_core),
    }
    core = {
        "schema": "rocell.ai_localization_evaluation_bundle.v1",
        "scope": "SYNTHETIC_OFFLINE_ONLY",
        "model_id": plan["model_id"],
        "model_checkpoint_sha256": plan["model_checkpoint_sha256"],
        "target_catalog_sha256": catalog.content_sha256,
        "calibration_dataset_sha256": calibration_dataset_sha256,
        "evaluation_dataset_sha256": evaluation_dataset_sha256,
        "domain_id": plan["domain_id"],
        "sampling_unit": "scene_style_condition_maximum_across_covered_targets",
        "covered_target_ids": target_ids,
        "declared_coverage_probability": plan["declared_coverage_probability"],
        "measured_coverage_probability": measured_coverage,
        "conservative_planar_error_bound_mm": radius,
        "calibration_sample_count": len(calibration),
        "evaluation_sample_count": len(evaluation),
        "per_target": per_target,
        "qualification_candidate": (
            qualification
            if measured_coverage >= plan["declared_coverage_probability"]
            else None
        ),
        "qualification_installed": False,
        "physical_deployment_qualified": False,
        "hardware_writes": 0,
        "physical_movements": 0,
        "limitations": [
            "Synthetic controlled renderer evidence only; no physical camera or deployment-domain claim.",
            "The conservative bound is the maximum calibration sample error, not a distribution-free guarantee.",
            "Calibration and evaluation use disjoint seeds but the same renderer family.",
            "The qualification is a candidate record and is not installed by this bundle.",
            "A candidate record is retained only when held-out measured coverage meets the declared probability.",
            "Every adapter evaluation abstains because the trusted qualification registry is empty.",
            "No ModelMotionBatch, execution permit, controller command, hardware access, or physical authority is created by this evaluation.",
        ],
    }
    return {**core, "bundle_sha256": canonical_hash(core)}


def main() -> None:
    plan_path = AI / "eval/precision_adapter_localization_v1_plan.json"
    output = AI / "eval/precision_adapter_localization_v1_bundle.json"
    if output.exists():
        raise FileExistsError(output)
    result = evaluate(plan_path)
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "model_checkpoint_sha256",
                    "target_catalog_sha256",
                    "calibration_dataset_sha256",
                    "evaluation_dataset_sha256",
                    "domain_id",
                    "declared_coverage_probability",
                    "measured_coverage_probability",
                    "conservative_planar_error_bound_mm",
                    "calibration_sample_count",
                    "evaluation_sample_count",
                    "qualification_installed",
                    "physical_deployment_qualified",
                    "bundle_sha256",
                )
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

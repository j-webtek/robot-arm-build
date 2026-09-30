"""Build synthetic-only target-occlusion data from retained Isaac mesh evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter


SCHEMA = "rocell.ai_official_mesh_occlusion_data.v1"
SOURCE_SCHEMA = "tactevra.isaac_fixed_overview_mesh_render.v1"
MAXIMUM_SAFE_REGION_OVERLAP = 0.20
BASELINE_SEED = 190
BASELINE_CROP_SIZE = 16
BASELINE_ITERATIONS = 800
BASELINE_LEARNING_RATE = 0.08
BASELINE_L2 = 0.001
SPLITS = {
    "train": {
        "poses": ("ready", "hover_t"),
        "lighting": ("nominal", "dim", "bright"),
    },
    "evaluation": {
        "poses": ("hover_e",),
        "lighting": ("warm", "glare", "blur"),
    },
}


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")


def _verify_source(path: Path) -> dict[str, Any]:
    source = json.loads(path.read_text(encoding="utf-8"))
    if source.get("schema") != SOURCE_SCHEMA:
        raise ValueError("official-mesh manifest schema mismatch")
    claimed = source.pop("receipt_sha256", None)
    if not isinstance(claimed, str) or _sha256(_canonical(source)) != claimed:
        raise ValueError("official-mesh receipt hash mismatch")
    source["receipt_sha256"] = claimed
    if source.get("result_status") != "PASS_WITH_BLOCKERS":
        raise ValueError("official-mesh source status is not admissible")
    if source.get("physical_authority") is not False or source.get("hardware_writes") != 0:
        raise ValueError("official-mesh source claims authority")
    evidence_dir = path.parent
    for artifact in source["artifact_atlases"].values():
        artifact_path = evidence_dir / artifact["path"]
        if _sha256(artifact_path.read_bytes()) != artifact["sha256"]:
            raise ValueError(f"artifact hash mismatch: {artifact_path.name}")
    return source


def _lighting(image: Image.Image, variant: str) -> Image.Image:
    rgb = image.convert("RGB")
    if variant == "nominal":
        return rgb
    if variant == "dim":
        return ImageEnhance.Brightness(rgb).enhance(0.62)
    if variant == "bright":
        return ImageEnhance.Brightness(rgb).enhance(1.28)
    if variant == "warm":
        red, green, blue = rgb.split()
        return Image.merge("RGB", (
            red.point(lambda value: min(255, round(value * 1.10))),
            green.point(lambda value: min(255, round(value * 1.02))),
            blue.point(lambda value: round(value * 0.86)),
        ))
    if variant == "glare":
        overlay = Image.new("RGB", rgb.size, "white")
        alpha = Image.new("L", rgb.size, 0)
        ImageDraw.Draw(alpha).ellipse((1080, 80, 1780, 760), fill=145)
        return Image.composite(overlay, rgb, alpha)
    if variant == "blur":
        return rgb.filter(ImageFilter.GaussianBlur(radius=1.4))
    raise ValueError(f"unknown lighting variant: {variant}")


def build(source_manifest: Path, output_dir: Path) -> dict[str, Any]:
    source_manifest = source_manifest.resolve(strict=True)
    output_dir = output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("output directory must be empty")
    output_dir.mkdir(parents=True, exist_ok=True)
    image_dir = output_dir / "images"
    image_dir.mkdir()
    source = _verify_source(source_manifest)
    rgb_path = source_manifest.parent / source["artifact_atlases"]["rgb"]["path"]
    rgb_atlas = Image.open(rgb_path).convert("RGB")
    pose_by_id = {row["pose_id"]: row for row in source["pose_results"]}

    image_records = []
    split_rows: dict[str, list[dict[str, Any]]] = {}
    for split, policy in SPLITS.items():
        rows = []
        for pose_id in policy["poses"]:
            pose = pose_by_id[pose_id]
            crop = rgb_atlas.crop(tuple(pose["atlas_crop_px"]))
            for variant in policy["lighting"]:
                transformed = _lighting(crop, variant)
                image_name = f"{split}__{pose_id}__{variant}.jpg"
                image_path = image_dir / image_name
                transformed.save(
                    image_path, "JPEG", quality=92, optimize=False,
                    progressive=False, subsampling=0,
                )
                image_sha = _sha256(image_path.read_bytes())
                image_records.append({
                    "split": split,
                    "pose_id": pose_id,
                    "lighting_variant": variant,
                    "path": f"images/{image_name}",
                    "sha256": image_sha,
                })
                for target in pose["targets"]:
                    overlap = target["safe_region_official_mesh_overlap_fraction"]
                    center_occluded = target["center_occluded_by_official_mesh"]
                    abstain = center_occluded or overlap > MAXIMUM_SAFE_REGION_OVERLAP
                    rows.append({
                        "id": f"{split}-{pose_id}-{variant}-{target['device']}-{target['target_id']}",
                        "image_path": f"images/{image_name}",
                        "image_sha256": image_sha,
                        "pose_id": pose_id,
                        "lighting_variant": variant,
                        "device": target["device"],
                        "target_id": target["target_id"],
                        "center_px": target["center_px"],
                        "safe_polygon_px": target["safe_polygon_px"],
                        "center_occluded": center_occluded,
                        "safe_region_overlap_fraction": overlap,
                        "decision": "abstain" if abstain else "target_visible",
                        "reason": "robot_occlusion" if abstain else None,
                        "synthetic_only": True,
                    })
        raw = b"".join(_canonical(row) + b"\n" for row in rows)
        (output_dir / f"{split}.jsonl").write_bytes(raw)
        split_rows[split] = rows

    train_poses = set(SPLITS["train"]["poses"])
    evaluation_poses = set(SPLITS["evaluation"]["poses"])
    train_lighting = set(SPLITS["train"]["lighting"])
    evaluation_lighting = set(SPLITS["evaluation"]["lighting"])
    if train_poses & evaluation_poses or train_lighting & evaluation_lighting:
        raise RuntimeError("train/evaluation group leakage")

    manifest: dict[str, Any] = {
        "schema": SCHEMA,
        "scope": "SYNTHETIC_ONLY_NO_DEPLOYMENT_QUALIFICATION",
        "source_manifest_sha256": _sha256(source_manifest.read_bytes()),
        "source_receipt_sha256": source["receipt_sha256"],
        "target_catalog_sha256": source["target_catalog_sha256"],
        "maximum_safe_region_overlap": MAXIMUM_SAFE_REGION_OVERLAP,
        "split_policy": SPLITS,
        "pose_groups_disjoint": True,
        "lighting_groups_disjoint": True,
        "images": image_records,
        "splits": {},
        "authority": {
            "hardware_accessed": False,
            "hardware_write_count": 0,
            "physical_movement_count": 0,
            "can_release_physical_gates": False,
        },
        "limitations": [
            "images, geometry, lighting transformations, and occlusion labels are synthetic",
            "camera and robot placement are nominal and unmeasured",
            "tool and camera-support geometry are absent",
            "evaluation split is a synthetic development fixture, not deployment qualification",
        ],
    }
    for split, rows in split_rows.items():
        payload = (output_dir / f"{split}.jsonl").read_bytes()
        manifest["splits"][split] = {
            "path": f"{split}.jsonl",
            "sha256": _sha256(payload),
            "count": len(rows),
            "abstain_count": sum(row["decision"] == "abstain" for row in rows),
            "visible_count": sum(row["decision"] == "target_visible" for row in rows),
        }
    manifest["dataset_sha256"] = _sha256(_canonical(manifest))
    (output_dir / "manifest.json").write_bytes(_canonical(manifest) + b"\n")
    return manifest


def _load_rows(dataset_dir: Path, split: str, manifest: dict[str, Any]) -> list[dict[str, Any]]:
    path = dataset_dir / manifest["splits"][split]["path"]
    payload = path.read_bytes()
    if _sha256(payload) != manifest["splits"][split]["sha256"]:
        raise ValueError(f"{split} data hash mismatch")
    return [json.loads(line) for line in payload.decode("utf-8").splitlines() if line]


def _features(dataset_dir: Path, rows: list[dict[str, Any]]) -> tuple[np.ndarray, np.ndarray]:
    cache: dict[str, Image.Image] = {}
    vectors = []
    labels = []
    for row in rows:
        image_path = dataset_dir / row["image_path"]
        image = cache.setdefault(row["image_path"], Image.open(image_path).convert("RGB"))
        if _sha256(image_path.read_bytes()) != row["image_sha256"]:
            raise ValueError(f"image hash mismatch: {row['image_path']}")
        polygon = row["safe_polygon_px"]
        x_values = [point[0] for point in polygon]
        y_values = [point[1] for point in polygon]
        padding = 12
        box = (
            max(0, int(min(x_values)) - padding),
            max(0, int(min(y_values)) - padding),
            min(image.width, int(max(x_values)) + padding + 1),
            min(image.height, int(max(y_values)) + padding + 1),
        )
        crop = image.crop(box).resize(
            (BASELINE_CROP_SIZE, BASELINE_CROP_SIZE), Image.Resampling.BILINEAR
        )
        vectors.append(np.asarray(crop, dtype=np.float64).reshape(-1) / 255.0)
        labels.append(row["decision"] == "abstain")
    return np.stack(vectors), np.asarray(labels, dtype=np.float64)


def _metrics(rows: list[dict[str, Any]], labels: np.ndarray,
             probabilities: np.ndarray) -> dict[str, Any]:
    predicted = probabilities >= 0.5
    expected = labels.astype(bool)
    tp = int(np.count_nonzero(predicted & expected))
    tn = int(np.count_nonzero(~predicted & ~expected))
    fp = int(np.count_nonzero(predicted & ~expected))
    fn = int(np.count_nonzero(~predicted & expected))
    bins = []
    ece = 0.0
    for lower in np.linspace(0.0, 0.9, 10):
        upper = lower + 0.1
        selected = (probabilities >= lower) & (
            probabilities <= upper if upper >= 1.0 else probabilities < upper
        )
        count = int(np.count_nonzero(selected))
        if not count:
            continue
        confidence = float(probabilities[selected].mean())
        rate = float(labels[selected].mean())
        ece += count / len(labels) * abs(confidence - rate)
        bins.append({
            "lower": float(lower), "upper": float(min(1.0, upper)),
            "count": count, "mean_probability": confidence,
            "abstain_rate": rate,
        })
    failures = [
        {
            "id": row["id"],
            "expected": "abstain" if bool(label) else "target_visible",
            "predicted": "abstain" if bool(prediction) else "target_visible",
            "abstain_probability": float(probability),
        }
        for row, label, prediction, probability in zip(
            rows, expected, predicted, probabilities, strict=True
        )
        if prediction != label
    ]
    return {
        "count": len(rows),
        "confusion": {
            "true_abstain": tp, "true_visible": tn,
            "false_abstain": fp, "missed_abstain": fn,
        },
        "accuracy": (tp + tn) / len(rows),
        "balanced_accuracy": 0.5 * (tp / (tp + fn) + tn / (tn + fp)),
        "brier_score": float(np.mean((probabilities - labels) ** 2)),
        "expected_calibration_error_10_bin": ece,
        "calibration_bins": bins,
        "failures": failures,
    }


def train_baseline(dataset_dir: Path, output_dir: Path) -> dict[str, Any]:
    dataset_dir = dataset_dir.resolve(strict=True)
    output_dir = output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("baseline output directory must be empty")
    output_dir.mkdir(parents=True, exist_ok=True)
    dataset_manifest_path = dataset_dir / "manifest.json"
    dataset_manifest = json.loads(dataset_manifest_path.read_text(encoding="utf-8"))
    claimed_dataset_sha = dataset_manifest.pop("dataset_sha256", None)
    if not isinstance(claimed_dataset_sha, str) or _sha256(_canonical(dataset_manifest)) != claimed_dataset_sha:
        raise ValueError("dataset manifest hash mismatch")
    dataset_manifest["dataset_sha256"] = claimed_dataset_sha
    if dataset_manifest.get("scope") != "SYNTHETIC_ONLY_NO_DEPLOYMENT_QUALIFICATION":
        raise ValueError("dataset scope mismatch")
    train_rows = _load_rows(dataset_dir, "train", dataset_manifest)
    evaluation_rows = _load_rows(dataset_dir, "evaluation", dataset_manifest)
    train_x, train_y = _features(dataset_dir, train_rows)
    evaluation_x, evaluation_y = _features(dataset_dir, evaluation_rows)
    mean = train_x.mean(axis=0)
    scale = train_x.std(axis=0)
    scale[scale < 1e-8] = 1.0
    train_x = (train_x - mean) / scale
    evaluation_x = (evaluation_x - mean) / scale
    train_x = np.column_stack((np.ones(len(train_x)), train_x))
    evaluation_x = np.column_stack((np.ones(len(evaluation_x)), evaluation_x))

    weights = np.zeros(train_x.shape[1], dtype=np.float64)
    positives = int(train_y.sum())
    negatives = len(train_y) - positives
    sample_weights = np.where(
        train_y == 1.0, len(train_y) / (2 * positives), len(train_y) / (2 * negatives)
    )
    for _ in range(BASELINE_ITERATIONS):
        logits = np.clip(train_x @ weights, -30.0, 30.0)
        probabilities = 1.0 / (1.0 + np.exp(-logits))
        gradient = train_x.T @ ((probabilities - train_y) * sample_weights) / len(train_y)
        gradient[1:] += BASELINE_L2 * weights[1:]
        weights -= BASELINE_LEARNING_RATE * gradient

    train_probabilities = 1.0 / (1.0 + np.exp(-np.clip(train_x @ weights, -30.0, 30.0)))
    evaluation_probabilities = 1.0 / (
        1.0 + np.exp(-np.clip(evaluation_x @ weights, -30.0, 30.0))
    )
    checkpoint = {
        "schema": "rocell.ai_target_crop_logistic.v1",
        "feature": {"crop_size": BASELINE_CROP_SIZE, "channels": "RGB", "padding_px": 12},
        "threshold": 0.5,
        "weights": weights.tolist(),
        "standardization_mean": mean.tolist(),
        "standardization_scale": scale.tolist(),
    }
    checkpoint_path = output_dir / "model.json"
    checkpoint_path.write_bytes(_canonical(checkpoint) + b"\n")
    scorecard: dict[str, Any] = {
        "schema": "rocell.ai_official_mesh_occlusion_baseline.v1",
        "seed": BASELINE_SEED,
        "algorithm": "deterministic_class_weighted_logistic_regression",
        "iterations": BASELINE_ITERATIONS,
        "learning_rate": BASELINE_LEARNING_RATE,
        "l2": BASELINE_L2,
        "dataset_manifest_sha256": _sha256(dataset_manifest_path.read_bytes()),
        "dataset_sha256": claimed_dataset_sha,
        "model_sha256": _sha256(checkpoint_path.read_bytes()),
        "train": _metrics(train_rows, train_y, train_probabilities),
        "evaluation": _metrics(evaluation_rows, evaluation_y, evaluation_probabilities),
        "promotion_status": "BLOCKED_SYNTHETIC_ONLY",
        "hardware_writes": 0,
        "physical_movements": 0,
        "limitations": dataset_manifest["limitations"],
    }
    scorecard["scorecard_sha256"] = _sha256(_canonical(scorecard))
    (output_dir / "scorecard.json").write_bytes(_canonical(scorecard) + b"\n")
    return scorecard


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--baseline-output", type=Path)
    args = parser.parse_args()
    try:
        manifest = build(args.source_manifest, args.output_dir)
        scorecard = (
            train_baseline(args.output_dir, args.baseline_output)
            if args.baseline_output is not None else None
        )
    except BaseException:
        if args.output_dir.exists():
            shutil.rmtree(args.output_dir)
        raise
    result = {
        "schema": manifest["schema"],
        "dataset_sha256": manifest["dataset_sha256"],
        "splits": manifest["splits"],
    }
    if scorecard is not None:
        evaluation = scorecard["evaluation"]
        result["baseline"] = {
            "scorecard_sha256": scorecard["scorecard_sha256"],
            "promotion_status": scorecard["promotion_status"],
            "evaluation": {
                key: evaluation[key]
                for key in (
                    "count", "confusion", "accuracy", "balanced_accuracy",
                    "brier_score", "expected_calibration_error_10_bin",
                )
            },
        }
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

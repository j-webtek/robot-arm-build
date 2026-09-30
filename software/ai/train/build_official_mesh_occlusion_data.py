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


SCHEMA_V1 = "rocell.ai_official_mesh_occlusion_data.v1"
SCHEMA_V2 = "rocell.ai_official_mesh_occlusion_data.v2"
SCHEMA_V3 = "rocell.ai_official_mesh_occlusion_data.v3"
SCHEMA_V4 = "rocell.ai_official_mesh_occlusion_data.v4"
SOURCE_SCHEMA_V1 = "tactevra.isaac_fixed_overview_mesh_render.v1"
SOURCE_SCHEMA_V2 = "tactevra.isaac_fixed_overview_mesh_render.v2"
SOURCE_SCHEMA_V3 = "tactevra.isaac_fixed_overview_mesh_render.v3"
SOURCE_SCHEMA_V4 = "tactevra.isaac_fixed_overview_mesh_render.v4"
MAXIMUM_SAFE_REGION_OVERLAP = 0.20
BASELINE_SEED = 190
BASELINE_CROP_SIZE = 16
BASELINE_ITERATIONS = 800
BASELINE_LEARNING_RATE = 0.08
BASELINE_L2 = 0.001
SPATIAL_CROP_SIZE = 32
SPATIAL_PADDING = 24
SPATIAL_EPOCHS = 8
SPATIAL_BATCH_SIZE = 128
SPATIAL_LEARNING_RATE = 0.002
LEGACY_SPLITS = {
    "train": {
        "poses": ("ready", "hover_t"),
        "lighting": ("nominal", "dim", "bright"),
    },
    "evaluation": {
        "poses": ("hover_e",),
        "lighting": ("warm", "glare", "blur"),
    },
}
EXPANDED_LIGHTING = {
    "train": ("nominal", "dim", "bright"),
    "development": ("warm", "glare", "blur"),
    "evaluation": ("cool", "side_shadow", "defocus"),
}
TRANSIT_LIGHTING = {
    "train": (
        "nominal", "dim", "bright", "warm", "glare", "blur",
        "cool", "side_shadow", "defocus",
    ),
    "development": ("desaturated", "gamma_dark", "vignette"),
    "evaluation": ("low_contrast", "right_shadow", "motion_blur"),
}
SPECIFICITY_LIGHTING = {
    "train": (
        "nominal", "dim", "bright", "warm", "glare", "blur", "cool",
        "side_shadow", "defocus", "desaturated", "gamma_dark", "vignette",
        "low_contrast", "right_shadow", "motion_blur",
    ),
    "development": ("soft_neutral", "gamma_mid", "left_shadow"),
    "evaluation": ("cool_flat", "top_shadow", "vertical_motion_blur"),
}


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")


def _verify_source(path: Path) -> dict[str, Any]:
    source = json.loads(path.read_text(encoding="utf-8"))
    if source.get("schema") not in {
        SOURCE_SCHEMA_V1, SOURCE_SCHEMA_V2, SOURCE_SCHEMA_V3, SOURCE_SCHEMA_V4
    }:
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


def _split_policy(source: dict[str, Any]) -> tuple[str, dict[str, dict[str, tuple[str, ...]]]]:
    if source["schema"] == SOURCE_SCHEMA_V1:
        return SCHEMA_V1, LEGACY_SPLITS
    pose_groups = source.get("pose_groups")
    if not isinstance(pose_groups, dict) or set(pose_groups) != {
        "training", "development", "evaluation"
    }:
        raise ValueError("expanded source must declare training/development/evaluation poses")
    normalized = {
        name: tuple(pose_groups[name])
        for name in ("training", "development", "evaluation")
    }
    flattened = [pose_id for pose_ids in normalized.values() for pose_id in pose_ids]
    rendered = [row["pose_id"] for row in source["pose_results"]]
    if len(set(flattened)) != len(flattened) or set(flattened) != set(rendered):
        raise ValueError("expanded pose groups must partition rendered poses")
    for row in source["pose_results"]:
        expected = next(name for name, poses in normalized.items() if row["pose_id"] in poses)
        if row.get("pose_group") != expected:
            raise ValueError(f"pose group mismatch: {row['pose_id']}")
    if source["schema"] == SOURCE_SCHEMA_V4:
        lighting = SPECIFICITY_LIGHTING
        schema = SCHEMA_V4
    elif source["schema"] == SOURCE_SCHEMA_V3:
        lighting = TRANSIT_LIGHTING
        schema = SCHEMA_V3
    else:
        lighting = EXPANDED_LIGHTING
        schema = SCHEMA_V2
    return schema, {
        "train": {"poses": normalized["training"], "lighting": lighting["train"]},
        "development": {
            "poses": normalized["development"],
            "lighting": lighting["development"],
        },
        "evaluation": {
            "poses": normalized["evaluation"],
            "lighting": lighting["evaluation"],
        },
    }


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
    if variant == "cool":
        red, green, blue = rgb.split()
        return Image.merge("RGB", (
            red.point(lambda value: round(value * 0.84)),
            green.point(lambda value: min(255, round(value * 1.01))),
            blue.point(lambda value: min(255, round(value * 1.12))),
        ))
    if variant == "side_shadow":
        overlay = Image.new("RGB", rgb.size, "black")
        alpha = Image.new("L", rgb.size, 0)
        ImageDraw.Draw(alpha).polygon(
            ((0, 0), (round(rgb.width * 0.58), 0),
             (round(rgb.width * 0.38), rgb.height), (0, rgb.height)),
            fill=105,
        )
        return Image.composite(overlay, rgb, alpha)
    if variant == "defocus":
        return rgb.filter(ImageFilter.GaussianBlur(radius=2.6))
    if variant == "desaturated":
        return ImageEnhance.Color(rgb).enhance(0.22)
    if variant == "gamma_dark":
        return rgb.point(lambda value: round(255 * (value / 255) ** 1.45))
    if variant == "vignette":
        y, x = np.ogrid[:rgb.height, :rgb.width]
        dx = (x - (rgb.width - 1) / 2) / (rgb.width / 2)
        dy = (y - (rgb.height - 1) / 2) / (rgb.height / 2)
        alpha = np.clip((dx * dx + dy * dy) * 105, 0, 105).astype(np.uint8)
        return Image.composite(Image.new("RGB", rgb.size, "black"), rgb, Image.fromarray(alpha))
    if variant == "low_contrast":
        return ImageEnhance.Contrast(rgb).enhance(0.48)
    if variant == "right_shadow":
        overlay = Image.new("RGB", rgb.size, "black")
        alpha = Image.new("L", rgb.size, 0)
        ImageDraw.Draw(alpha).polygon(
            ((round(rgb.width * 0.44), 0), (rgb.width, 0),
             (rgb.width, rgb.height), (round(rgb.width * 0.62), rgb.height)),
            fill=115,
        )
        return Image.composite(overlay, rgb, alpha)
    if variant == "motion_blur":
        weights = [0.0] * 25
        weights[10:15] = [1.0] * 5
        return rgb.filter(ImageFilter.Kernel((5, 5), weights, scale=5.0))
    if variant == "soft_neutral":
        return ImageEnhance.Contrast(ImageEnhance.Brightness(rgb).enhance(0.96)).enhance(0.84)
    if variant == "gamma_mid":
        return rgb.point(lambda value: round(255 * (value / 255) ** 0.82))
    if variant == "left_shadow":
        overlay = Image.new("RGB", rgb.size, "black")
        alpha = Image.new("L", rgb.size, 0)
        ImageDraw.Draw(alpha).polygon(
            ((0, 0), (round(rgb.width * 0.50), 0),
             (round(rgb.width * 0.34), rgb.height), (0, rgb.height)),
            fill=82,
        )
        return Image.composite(overlay, rgb, alpha)
    if variant == "cool_flat":
        red, green, blue = rgb.split()
        cooled = Image.merge("RGB", (
            red.point(lambda value: round(value * 0.91)),
            green,
            blue.point(lambda value: min(255, round(value * 1.07))),
        ))
        return ImageEnhance.Contrast(cooled).enhance(0.72)
    if variant == "top_shadow":
        overlay = Image.new("RGB", rgb.size, "black")
        alpha = Image.new("L", rgb.size, 0)
        ImageDraw.Draw(alpha).polygon(
            ((0, 0), (rgb.width, 0), (rgb.width, round(rgb.height * 0.42)),
             (0, round(rgb.height * 0.58))),
            fill=92,
        )
        return Image.composite(overlay, rgb, alpha)
    if variant == "vertical_motion_blur":
        weights = [0.0] * 25
        for index in (2, 7, 12, 17, 22):
            weights[index] = 1.0
        return rgb.filter(ImageFilter.Kernel((5, 5), weights, scale=5.0))
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
    schema, split_policy = _split_policy(source)
    rgb_path = source_manifest.parent / source["artifact_atlases"]["rgb"]["path"]
    rgb_atlas = Image.open(rgb_path).convert("RGB")
    pose_by_id = {row["pose_id"]: row for row in source["pose_results"]}

    image_records = []
    split_rows: dict[str, list[dict[str, Any]]] = {}
    for split, policy in split_policy.items():
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

    pose_groups = [set(policy["poses"]) for policy in split_policy.values()]
    lighting_groups = [set(policy["lighting"]) for policy in split_policy.values()]
    if any(
        left & right
        for index, left in enumerate(pose_groups)
        for right in pose_groups[index + 1:]
    ) or any(
        left & right
        for index, left in enumerate(lighting_groups)
        for right in lighting_groups[index + 1:]
    ):
        raise RuntimeError("pose or lighting group leakage")

    manifest: dict[str, Any] = {
        "schema": schema,
        "scope": "SYNTHETIC_ONLY_NO_DEPLOYMENT_QUALIFICATION",
        "source_manifest_sha256": _sha256(source_manifest.read_bytes()),
        "source_receipt_sha256": source["receipt_sha256"],
        "target_catalog_sha256": source["target_catalog_sha256"],
        "maximum_safe_region_overlap": MAXIMUM_SAFE_REGION_OVERLAP,
        "split_policy": split_policy,
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


def _features(
    dataset_dir: Path, rows: list[dict[str, Any]], family: str = "rgb_raw"
) -> tuple[np.ndarray, np.ndarray]:
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
        array = np.asarray(crop, dtype=np.float64) / 255.0
        if family == "rgb_raw":
            vector = array.reshape(-1)
        elif family == "chromatic_gray_edges":
            chromatic = array / np.maximum(array.sum(axis=2, keepdims=True), 1e-8)
            gray = array @ np.asarray((0.299, 0.587, 0.114))
            normalized = (gray - gray.mean()) / max(float(gray.std()), 1e-6)
            horizontal = np.diff(normalized, axis=1, prepend=normalized[:, :1])
            vertical = np.diff(normalized, axis=0, prepend=normalized[:1, :])
            vector = np.concatenate((
                chromatic.reshape(-1), normalized.reshape(-1),
                horizontal.reshape(-1), vertical.reshape(-1),
            ))
        else:
            raise ValueError(f"unknown feature family: {family}")
        vectors.append(vector)
        labels.append(row["decision"] == "abstain")
    return np.stack(vectors), np.asarray(labels, dtype=np.float64)


def _spatial_crops(
    dataset_dir: Path, rows: list[dict[str, Any]]
) -> tuple[np.ndarray, np.ndarray]:
    cache: dict[str, Image.Image] = {}
    verified: set[str] = set()
    crops = []
    labels = []
    for row in rows:
        image_path = dataset_dir / row["image_path"]
        if row["image_path"] not in verified:
            if _sha256(image_path.read_bytes()) != row["image_sha256"]:
                raise ValueError(f"image hash mismatch: {row['image_path']}")
            verified.add(row["image_path"])
        image = cache.setdefault(row["image_path"], Image.open(image_path).convert("RGB"))
        polygon = row["safe_polygon_px"]
        x_values = [point[0] for point in polygon]
        y_values = [point[1] for point in polygon]
        box = (
            max(0, int(min(x_values)) - SPATIAL_PADDING),
            max(0, int(min(y_values)) - SPATIAL_PADDING),
            min(image.width, int(max(x_values)) + SPATIAL_PADDING + 1),
            min(image.height, int(max(y_values)) + SPATIAL_PADDING + 1),
        )
        crop = image.crop(box).resize(
            (SPATIAL_CROP_SIZE, SPATIAL_CROP_SIZE), Image.Resampling.BILINEAR
        )
        crops.append(np.asarray(crop, dtype=np.float32).transpose(2, 0, 1) / 255.0)
        labels.append(row["decision"] == "abstain")
    return np.stack(crops), np.asarray(labels, dtype=np.float32)


def _metrics(rows: list[dict[str, Any]], labels: np.ndarray,
             probabilities: np.ndarray, threshold: float = 0.5) -> dict[str, Any]:
    predicted = probabilities >= threshold
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


def _fit_logistic(features: np.ndarray, labels: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    mean = features.mean(axis=0)
    scale = features.std(axis=0)
    scale[scale < 1e-8] = 1.0
    standardized = (features - mean) / scale
    design = np.column_stack((np.ones(len(standardized)), standardized))
    weights = np.zeros(design.shape[1], dtype=np.float64)
    positives = int(labels.sum())
    negatives = len(labels) - positives
    sample_weights = np.where(
        labels == 1.0, len(labels) / (2 * positives), len(labels) / (2 * negatives)
    )
    for _ in range(BASELINE_ITERATIONS):
        logits = np.clip(design @ weights, -30.0, 30.0)
        probabilities = 1.0 / (1.0 + np.exp(-logits))
        gradient = design.T @ ((probabilities - labels) * sample_weights) / len(labels)
        gradient[1:] += BASELINE_L2 * weights[1:]
        weights -= BASELINE_LEARNING_RATE * gradient
    return weights, mean, scale


def _probabilities(
    features: np.ndarray, weights: np.ndarray, mean: np.ndarray, scale: np.ndarray
) -> np.ndarray:
    design = np.column_stack((np.ones(len(features)), (features - mean) / scale))
    return 1.0 / (1.0 + np.exp(-np.clip(design @ weights, -30.0, 30.0)))


def _select_threshold(labels: np.ndarray, probabilities: np.ndarray) -> float:
    candidates = []
    expected = labels.astype(bool)
    positives = int(expected.sum())
    for threshold in (round(value, 2) for value in np.linspace(0.05, 0.95, 19)):
        predicted = probabilities >= threshold
        tp = int(np.count_nonzero(predicted & expected))
        tn = int(np.count_nonzero(~predicted & ~expected))
        fp = int(np.count_nonzero(predicted & ~expected))
        fn = int(np.count_nonzero(~predicted & expected))
        missed_rate = fn / positives
        balanced = 0.5 * (tp / (tp + fn) + tn / (tn + fp))
        candidates.append(((missed_rate <= 0.05, balanced, -fp, -fn), float(threshold)))
    return max(candidates)[1]


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


def train_selected_candidate(dataset_dir: Path, output_dir: Path) -> dict[str, Any]:
    """Select on development only, freeze, then score reserved evaluation once."""
    dataset_dir = dataset_dir.resolve(strict=True)
    output_dir = output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("candidate output directory must be empty")
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = dataset_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    claimed_dataset_sha = manifest.pop("dataset_sha256", None)
    if not isinstance(claimed_dataset_sha, str) or _sha256(_canonical(manifest)) != claimed_dataset_sha:
        raise ValueError("dataset manifest hash mismatch")
    manifest["dataset_sha256"] = claimed_dataset_sha
    if manifest.get("schema") != SCHEMA_V2:
        raise ValueError("candidate selection requires three-way v2 dataset")
    if manifest.get("scope") != "SYNTHETIC_ONLY_NO_DEPLOYMENT_QUALIFICATION":
        raise ValueError("dataset scope mismatch")

    train_rows = _load_rows(dataset_dir, "train", manifest)
    development_rows = _load_rows(dataset_dir, "development", manifest)
    candidates: list[dict[str, Any]] = []
    fitted: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    for family in ("rgb_raw", "chromatic_gray_edges"):
        train_x, train_y = _features(dataset_dir, train_rows, family)
        development_x, development_y = _features(dataset_dir, development_rows, family)
        weights, mean, scale = _fit_logistic(train_x, train_y)
        probabilities = _probabilities(development_x, weights, mean, scale)
        threshold = _select_threshold(development_y, probabilities)
        metrics = _metrics(development_rows, development_y, probabilities, threshold)
        missed = metrics["confusion"]["missed_abstain"]
        candidates.append({
            "feature_family": family,
            "threshold": threshold,
            "development": metrics,
            "development_missed_abstain_rate": missed / int(development_y.sum()),
        })
        fitted[family] = (weights, mean, scale)

    def rank(row: dict[str, Any]) -> tuple[bool, float, int, int]:
        confusion = row["development"]["confusion"]
        return (
            row["development_missed_abstain_rate"] <= 0.05,
            row["development"]["balanced_accuracy"],
            -confusion["false_abstain"],
            -confusion["missed_abstain"],
        )

    selected = max(candidates, key=rank)
    family = selected["feature_family"]
    threshold = selected["threshold"]
    weights, mean, scale = fitted[family]
    checkpoint = {
        "schema": "rocell.ai_target_crop_logistic.v2",
        "feature": {
            "family": family,
            "crop_size": BASELINE_CROP_SIZE,
            "padding_px": 12,
        },
        "threshold": threshold,
        "weights": weights.tolist(),
        "standardization_mean": mean.tolist(),
        "standardization_scale": scale.tolist(),
        "selection_dataset_sha256": claimed_dataset_sha,
        "selection_split": "development",
    }
    checkpoint_path = output_dir / "model.json"
    checkpoint_path.write_bytes(_canonical(checkpoint) + b"\n")

    # Evaluation is loaded only after the family, threshold, and checkpoint are frozen.
    evaluation_rows = _load_rows(dataset_dir, "evaluation", manifest)
    evaluation_x, evaluation_y = _features(dataset_dir, evaluation_rows, family)
    evaluation_probabilities = _probabilities(evaluation_x, weights, mean, scale)
    scorecard: dict[str, Any] = {
        "schema": "rocell.ai_official_mesh_occlusion_candidate.v2",
        "seed": BASELINE_SEED,
        "algorithm": "deterministic_class_weighted_logistic_regression",
        "selection_policy": {
            "fit_split": "train",
            "selection_split": "development",
            "evaluation_split": "evaluation_loaded_after_checkpoint_freeze",
            "maximum_development_missed_abstain_rate": 0.05,
            "ranking": [
                "meets_missed_abstain_rate", "balanced_accuracy",
                "fewest_false_abstentions", "fewest_missed_abstentions",
            ],
        },
        "dataset_manifest_sha256": _sha256(manifest_path.read_bytes()),
        "dataset_sha256": claimed_dataset_sha,
        "candidate_development_results": candidates,
        "selected_feature_family": family,
        "selected_threshold": threshold,
        "model_sha256": _sha256(checkpoint_path.read_bytes()),
        "evaluation": _metrics(
            evaluation_rows, evaluation_y, evaluation_probabilities, threshold
        ),
        "promotion_status": "BLOCKED_SYNTHETIC_ONLY",
        "hardware_writes": 0,
        "physical_movements": 0,
        "limitations": manifest["limitations"],
    }
    scorecard["scorecard_sha256"] = _sha256(_canonical(scorecard))
    (output_dir / "scorecard.json").write_bytes(_canonical(scorecard) + b"\n")
    return scorecard


def train_spatial_candidate(dataset_dir: Path, output_dir: Path) -> dict[str, Any]:
    """Fit a tiny CNN, freeze on development, then score evaluation once."""
    import torch

    dataset_dir = dataset_dir.resolve(strict=True)
    output_dir = output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError("spatial output directory must be empty")
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = dataset_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    claimed_dataset_sha = manifest.pop("dataset_sha256", None)
    if not isinstance(claimed_dataset_sha, str) or _sha256(_canonical(manifest)) != claimed_dataset_sha:
        raise ValueError("dataset manifest hash mismatch")
    manifest["dataset_sha256"] = claimed_dataset_sha
    if manifest.get("schema") not in {SCHEMA_V3, SCHEMA_V4}:
        raise ValueError("spatial selection requires a three-way v3 or v4 dataset")
    if manifest.get("scope") != "SYNTHETIC_ONLY_NO_DEPLOYMENT_QUALIFICATION":
        raise ValueError("dataset scope mismatch")

    torch.manual_seed(BASELINE_SEED)
    torch.use_deterministic_algorithms(True)
    torch.set_num_threads(1)

    class TinySpatial(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.features = torch.nn.Sequential(
                torch.nn.Conv2d(3, 8, 3, padding=1),
                torch.nn.ReLU(),
                torch.nn.MaxPool2d(2),
                torch.nn.Conv2d(8, 16, 3, padding=1),
                torch.nn.ReLU(),
                torch.nn.AdaptiveAvgPool2d((4, 4)),
            )
            self.classifier = torch.nn.Linear(16 * 4 * 4, 1)

        def forward(self, values):  # type: ignore[no-untyped-def]
            return self.classifier(self.features(values).flatten(1)).squeeze(1)

    train_rows = _load_rows(dataset_dir, "train", manifest)
    development_rows = _load_rows(dataset_dir, "development", manifest)
    train_x, train_y = _spatial_crops(dataset_dir, train_rows)
    development_x, development_y = _spatial_crops(dataset_dir, development_rows)
    train_tensor = torch.from_numpy(train_x)
    train_labels = torch.from_numpy(train_y)
    development_tensor = torch.from_numpy(development_x)
    model = TinySpatial().cpu()
    positives = float(train_y.sum())
    negatives = float(len(train_y) - positives)
    loss_fn = torch.nn.BCEWithLogitsLoss(
        pos_weight=torch.tensor(negatives / positives, dtype=torch.float32)
    )
    optimizer = torch.optim.Adam(model.parameters(), lr=SPATIAL_LEARNING_RATE)
    epoch_losses = []
    for epoch in range(SPATIAL_EPOCHS):
        generator = torch.Generator().manual_seed(BASELINE_SEED + epoch)
        order = torch.randperm(len(train_tensor), generator=generator)
        total_loss = 0.0
        for start in range(0, len(order), SPATIAL_BATCH_SIZE):
            indices = order[start:start + SPATIAL_BATCH_SIZE]
            optimizer.zero_grad(set_to_none=True)
            loss = loss_fn(model(train_tensor[indices]), train_labels[indices])
            loss.backward()
            optimizer.step()
            total_loss += float(loss.detach()) * len(indices)
        epoch_losses.append(total_loss / len(order))

    model.eval()
    with torch.no_grad():
        development_probabilities = torch.sigmoid(model(development_tensor)).numpy()
    threshold = _select_threshold(development_y.astype(np.float64), development_probabilities)
    development_metrics = _metrics(
        development_rows, development_y.astype(np.float64),
        development_probabilities, threshold,
    )
    development_missed_rate = (
        development_metrics["confusion"]["missed_abstain"] / int(development_y.sum())
    )
    state = {
        name: {
            "shape": list(value.shape),
            "values": value.detach().cpu().numpy().astype(np.float64).reshape(-1).tolist(),
        }
        for name, value in sorted(model.state_dict().items())
    }
    checkpoint = {
        "schema": "rocell.ai_target_crop_tiny_spatial.v1",
        "architecture": {
            "input": [3, SPATIAL_CROP_SIZE, SPATIAL_CROP_SIZE],
            "layers": [
                "conv_3_8_k3_pad1", "relu", "maxpool_2",
                "conv_8_16_k3_pad1", "relu", "adaptive_avgpool_4x4",
                "linear_256_1",
            ],
            "parameter_count": sum(value.numel() for value in model.parameters()),
        },
        "training": {
            "seed": BASELINE_SEED,
            "device": "cpu",
            "epochs": SPATIAL_EPOCHS,
            "batch_size": SPATIAL_BATCH_SIZE,
            "learning_rate": SPATIAL_LEARNING_RATE,
            "optimizer": "adam",
            "class_weighting": "negative_to_positive_ratio",
            "epoch_losses": epoch_losses,
        },
        "crop": {"size": SPATIAL_CROP_SIZE, "padding_px": SPATIAL_PADDING},
        "threshold": threshold,
        "selection_dataset_sha256": claimed_dataset_sha,
        "selection_split": "development",
        "development_missed_abstain_rate": development_missed_rate,
        "state_dict": state,
    }
    checkpoint_path = output_dir / "model.json"
    checkpoint_path.write_bytes(_canonical(checkpoint) + b"\n")

    # Evaluation bytes are loaded only after architecture, state, and threshold freeze.
    evaluation_rows = _load_rows(dataset_dir, "evaluation", manifest)
    evaluation_x, evaluation_y = _spatial_crops(dataset_dir, evaluation_rows)
    with torch.no_grad():
        evaluation_probabilities = torch.sigmoid(
            model(torch.from_numpy(evaluation_x))
        ).numpy()
    scorecard: dict[str, Any] = {
        "schema": "rocell.ai_official_mesh_occlusion_spatial_candidate.v1",
        "algorithm": "tiny_deterministic_cpu_cnn",
        "selection_policy": {
            "fit_split": "train",
            "selection_split": "development",
            "evaluation_split": "evaluation_loaded_after_checkpoint_freeze",
            "maximum_development_missed_abstain_rate": 0.05,
        },
        "dataset_manifest_sha256": _sha256(manifest_path.read_bytes()),
        "dataset_sha256": claimed_dataset_sha,
        "model_sha256": _sha256(checkpoint_path.read_bytes()),
        "selected_threshold": threshold,
        "development_missed_abstain_rate": development_missed_rate,
        "development_gate_met": development_missed_rate <= 0.05,
        "development": development_metrics,
        "evaluation": _metrics(
            evaluation_rows, evaluation_y.astype(np.float64),
            evaluation_probabilities, threshold,
        ),
        "promotion_status": "BLOCKED_SYNTHETIC_ONLY",
        "hardware_writes": 0,
        "physical_movements": 0,
        "limitations": manifest["limitations"],
    }
    scorecard["scorecard_sha256"] = _sha256(_canonical(scorecard))
    (output_dir / "scorecard.json").write_bytes(_canonical(scorecard) + b"\n")
    return scorecard


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--baseline-output", type=Path)
    parser.add_argument("--candidate-output", type=Path)
    parser.add_argument("--spatial-output", type=Path)
    args = parser.parse_args()
    try:
        manifest = build(args.source_manifest, args.output_dir)
        scorecard = (
            train_baseline(args.output_dir, args.baseline_output)
            if args.baseline_output is not None else None
        )
        candidate_scorecard = (
            train_selected_candidate(args.output_dir, args.candidate_output)
            if args.candidate_output is not None else None
        )
        spatial_scorecard = (
            train_spatial_candidate(args.output_dir, args.spatial_output)
            if args.spatial_output is not None else None
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
    if candidate_scorecard is not None:
        evaluation = candidate_scorecard["evaluation"]
        result["candidate"] = {
            "scorecard_sha256": candidate_scorecard["scorecard_sha256"],
            "promotion_status": candidate_scorecard["promotion_status"],
            "selected_feature_family": candidate_scorecard["selected_feature_family"],
            "selected_threshold": candidate_scorecard["selected_threshold"],
            "evaluation": {
                key: evaluation[key]
                for key in (
                    "count", "confusion", "accuracy", "balanced_accuracy",
                    "brier_score", "expected_calibration_error_10_bin",
                )
            },
        }
    if spatial_scorecard is not None:
        evaluation = spatial_scorecard["evaluation"]
        result["spatial_candidate"] = {
            "scorecard_sha256": spatial_scorecard["scorecard_sha256"],
            "promotion_status": spatial_scorecard["promotion_status"],
            "selected_threshold": spatial_scorecard["selected_threshold"],
            "development_gate_met": spatial_scorecard["development_gate_met"],
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

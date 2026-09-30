"""Build synthetic-only target-occlusion data from retained Isaac mesh evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
from typing import Any

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter


SCHEMA = "rocell.ai_official_mesh_occlusion_data.v1"
SOURCE_SCHEMA = "tactevra.isaac_fixed_overview_mesh_render.v1"
MAXIMUM_SAFE_REGION_OVERLAP = 0.20
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        manifest = build(args.source_manifest, args.output_dir)
    except BaseException:
        if args.output_dir.exists():
            shutil.rmtree(args.output_dir)
        raise
    print(json.dumps({
        "schema": manifest["schema"],
        "dataset_sha256": manifest["dataset_sha256"],
        "splits": manifest["splits"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

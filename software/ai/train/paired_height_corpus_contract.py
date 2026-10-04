"""Frozen row scheduling and exact admission for paired height corpora.

This module does not render, train, score, or open evaluation data.  It turns a
small frozen fixture into an exact train/development allowlist and verifies that
renderer manifests preserve the same source pixels for the 96 and 192 model
inputs.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterator


FIXTURE_SCHEMA = "tactevra.ai_residual_obstruction_paired_height_fixture.v1_1"
SHARD_SCHEMA = "tactevra.ai_residual_obstruction_paired_height_shard.v1_1"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load_fixture(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.resolve(strict=True).read_bytes()
    fixture = json.loads(raw)
    if fixture.get("schema") != FIXTURE_SCHEMA:
        raise ValueError("unsupported paired-height fixture")
    core = {key: value for key, value in fixture.items() if key != "bundle_sha256"}
    if fixture.get("bundle_sha256") != sha256_bytes(canonical(core)):
        raise ValueError("fixture canonical hash mismatch")
    if fixture.get("evaluation_identities_present") is not False:
        raise ValueError("evaluation identities must be absent")
    if fixture.get("images_generated") is not False or fixture.get("training_started") is not False:
        raise ValueError("fixture must be frozen before rendering and training")
    if fixture["camera"]["orientation"] != "EXACT_NADIR_FIXED":
        raise ValueError("paired height corpus only admits the fixed nadir family")
    output = fixture["output_contract"]
    sizes = output["derived_local_tensor_sizes_px"]
    if sizes != [[96, 96], [192, 192]]:
        raise ValueError("paired output sizes must be exactly 96 and 192")
    if output.get("stored_artifact") != "SENSOR_ALIGNED_NATIVE_RGB8_PNG":
        raise ValueError("fixture must store native sensor-aligned crops")
    if output.get("camera_model_order") != [
        "EXPOSURE_GAIN",
        "SENSOR_NOISE",
        "QUANTIZATION_GAMMA",
        "BT601_FULL_RANGE_YUY2_422_COSITED_LEFT",
        "FLOATING_CROP_ALIGNMENT",
        "RESAMPLE_MODEL_INPUT",
    ]:
        raise ValueError("camera model order differs from the sensor pipeline")
    return fixture, raw


def _split_heights(fixture: dict[str, Any], split: str, scene_id: str) -> list[int]:
    if split == "training":
        return [int(fixture["split_identities"]["training_scene_height_mm"][scene_id])]
    if split == "development":
        return [int(value) for value in fixture["camera"]["heights_board_mm"]]
    raise ValueError("only training and development are admitted")


def iter_row_identities(
    fixture: dict[str, Any],
    split: str,
    *,
    scene_ids: set[str] | None = None,
    target_keys: set[str] | None = None,
) -> Iterator[dict[str, Any]]:
    """Yield the exact deterministic identity schedule without image paths."""
    scenes = fixture["split_identities"][f"{split}_scene_ids"]
    appearances = fixture["split_identities"][f"{split}_appearance_ids"]
    for scene_id in scenes:
        if scene_ids is not None and scene_id not in scene_ids:
            continue
        for height_mm in _split_heights(fixture, split, scene_id):
            for appearance_id in appearances:
                for target in fixture["targets"]:
                    target_key = f"{target['device']}:{target['target_id']}"
                    if target_keys is not None and target_key not in target_keys:
                        continue
                    for variant in fixture["variants"]:
                        row_id = ":".join(
                            (
                                split,
                                scene_id,
                                str(height_mm),
                                appearance_id,
                                target["device"],
                                target["target_id"],
                                variant["variant_id"],
                            )
                        )
                        seed_material = f"{fixture['seed_contract']['salt']}|{row_id}".encode()
                        yield {
                            "row_id": row_id,
                            "split": split,
                            "scene_id": scene_id,
                            "height_board_mm": height_mm,
                            "appearance_id": appearance_id,
                            "device": target["device"],
                            "target_id": target["target_id"],
                            "variant_id": variant["variant_id"],
                            "camera_sample_seed": int(sha256_bytes(seed_material)[:16], 16),
                        }


def expected_counts(fixture: dict[str, Any]) -> dict[str, int]:
    training = sum(1 for _ in iter_row_identities(fixture, "training"))
    development = sum(1 for _ in iter_row_identities(fixture, "development"))
    return {
        "training_source_rows": training,
        "development_source_rows": development,
        "total_source_rows": training + development,
        "stored_native_crop_pngs": training + development,
        "derived_model_tensors_per_loader_epoch": 2 * (training + development),
    }


def _yuy2_roundtrip(rgb: Any, np: Any) -> Any:
    value = rgb.astype(np.float32)
    red, green, blue = value[..., 0], value[..., 1], value[..., 2]
    luminance = 0.299 * red + 0.587 * green + 0.114 * blue
    chroma_u = -0.168736 * red - 0.331264 * green + 0.5 * blue + 128.0
    chroma_v = 0.5 * red - 0.418688 * green - 0.081312 * blue + 128.0
    if rgb.shape[1] % 2:
        raise ValueError("sensor-aligned native crop width must be even")
    chroma_u = np.repeat(np.rint(chroma_u[:, ::2]), 2, axis=1)
    chroma_v = np.repeat(np.rint(chroma_v[:, ::2]), 2, axis=1)
    luminance = np.rint(luminance)
    restored = np.stack(
        (
            luminance + 1.402 * (chroma_v - 128.0),
            luminance - 0.344136 * (chroma_u - 128.0) - 0.714136 * (chroma_v - 128.0),
            luminance + 1.772 * (chroma_u - 128.0),
        ),
        axis=-1,
    )
    return np.clip(restored, 0, 255).astype(np.uint8)


def derive_model_input(
    native_rgb: Any,
    *,
    aligned_crop_box_px: list[float],
    output_size_px: int,
    seed: int,
    noise_std_rgb: list[float] | None,
    qualifying: bool,
) -> Any:
    """Apply the camera model at native pixels, then align and resize.

    RGB8 storage is a documented synthetic limitation.  Qualification refuses
    an absent measured noise profile.  Noise is intentionally sampled before
    YUY2 and before resizing so downsampling averages it like the real path.
    """
    import numpy as np
    from PIL import Image

    if output_size_px not in {96, 192}:
        raise ValueError("output_size_px must be 96 or 192")
    value = np.asarray(native_rgb)
    if value.ndim != 3 or value.shape[2] != 3 or value.dtype != np.uint8:
        raise ValueError("native_rgb must be uint8 HxWx3")
    if value.shape[1] % 2:
        raise ValueError("native crop must start and end on YUY2 pair boundaries")
    if noise_std_rgb is None:
        if qualifying:
            raise ValueError("qualifying load requires measured B0477 noise")
        noisy = value
    else:
        if len(noise_std_rgb) != 3 or any(float(item) < 0 for item in noise_std_rgb):
            raise ValueError("noise_std_rgb must contain three nonnegative values")
        noise = np.random.default_rng(seed).normal(
            0.0, np.asarray(noise_std_rgb, dtype=np.float32), value.shape
        )
        noisy = np.clip(value.astype(np.float32) + noise, 0, 255).astype(np.uint8)
    delivered = _yuy2_roundtrip(noisy, np)
    left, top, right, bottom = (float(item) for item in aligned_crop_box_px)
    if not (0 <= left < right <= value.shape[1] and 0 <= top < bottom <= value.shape[0]):
        raise ValueError("aligned crop box is outside the stored native crop")
    image = Image.fromarray(delivered, mode="RGB")
    return np.asarray(
        image.transform(
            (output_size_px, output_size_px),
            Image.Transform.EXTENT,
            (left, top, right, bottom),
            resample=Image.Resampling.BICUBIC,
        ),
        dtype=np.uint8,
    )


def admit_shard_manifest(
    fixture_path: Path,
    manifest_path: Path,
    *,
    artifact_root: Path | None = None,
) -> dict[str, Any]:
    """Admit one exact shard and optionally verify every referenced PNG."""
    fixture, fixture_raw = load_fixture(fixture_path)
    manifest_raw = manifest_path.resolve(strict=True).read_bytes()
    manifest = json.loads(manifest_raw)
    if manifest.get("schema") != SHARD_SCHEMA:
        raise ValueError("unsupported paired-height shard")
    if manifest.get("fixture_file_sha256") != sha256_bytes(fixture_raw):
        raise ValueError("fixture file hash mismatch")
    if manifest.get("fixture_bundle_sha256") != fixture["bundle_sha256"]:
        raise ValueError("fixture bundle hash mismatch")
    split = manifest.get("split")
    if split not in {"training", "development"}:
        raise ValueError("evaluation or unknown split is forbidden")
    shard = manifest.get("shard", {})
    scene_ids = set(shard.get("scene_ids", []))
    target_keys = set(shard.get("target_keys", []))
    if not scene_ids or not target_keys:
        raise ValueError("shard scene and target allowlists must be nonempty")
    expected = {
        row["row_id"]: row
        for row in iter_row_identities(
            fixture, split, scene_ids=scene_ids, target_keys=target_keys
        )
    }
    rows = manifest.get("observations")
    if not isinstance(rows, list) or len(rows) != len(expected):
        raise ValueError("shard observation inventory mismatch")
    seen: set[str] = set()
    allowed_paths: set[str] = set()
    for row in rows:
        row_id = row.get("row_id")
        if row_id in seen or row_id not in expected:
            raise ValueError("duplicate or unexpected row identity")
        seen.add(row_id)
        identity = expected[row_id]
        if any(row.get(key) != value for key, value in identity.items()):
            raise ValueError(f"row identity fields differ for {row_id}")
        native = row.get("native_crop")
        if not isinstance(native, dict):
            raise ValueError("missing stored native crop")
        relative = native.get("path")
        if not isinstance(relative, str) or not relative.endswith(".png"):
            raise ValueError("stored native crop must be a lossless PNG path")
        if relative in allowed_paths:
            raise ValueError("duplicate native crop path")
        allowed_paths.add(relative)
        digest = native.get("sha256")
        size = native.get("size_px")
        bounds = native.get("full_frame_integer_bounds_px")
        aligned = native.get("aligned_model_crop_box_px")
        if not isinstance(digest, str) or len(digest) != 64:
            raise ValueError("missing native crop hash")
        if not (
            isinstance(size, list)
            and len(size) == 2
            and all(isinstance(item, int) for item in size)
            and 320 <= min(size) <= max(size) <= 480
            and size[0] % 2 == 0
        ):
            raise ValueError("native crop dimensions are outside the frozen support range")
        if not (
            isinstance(bounds, list)
            and len(bounds) == 4
            and all(isinstance(item, int) for item in bounds)
            and bounds[0] % 2 == 0
            and bounds[2] % 2 == 0
            and bounds[2] - bounds[0] == size[0]
            and bounds[3] - bounds[1] == size[1]
        ):
            raise ValueError("native crop is not aligned to full-frame YUY2 pairs")
        if not (
            isinstance(aligned, list)
            and len(aligned) == 4
            and 0 <= aligned[0] < aligned[2] <= size[0]
            and 0 <= aligned[1] < aligned[3] <= size[1]
        ):
            raise ValueError("model crop alignment is outside the native crop")
        if artifact_root is not None:
            payload = (artifact_root / relative).resolve(strict=True).read_bytes()
            if not payload.startswith(PNG_SIGNATURE):
                raise ValueError(f"non-PNG payload: {relative}")
            if sha256_bytes(payload) != digest:
                raise ValueError(f"native crop hash mismatch: {relative}")
            from PIL import Image

            with Image.open(artifact_root / relative) as image:
                if list(image.size) != size:
                    raise ValueError(f"native crop pixel dimensions differ: {relative}")
    if seen != set(expected):
        raise ValueError("shard is missing frozen row identities")
    if set(manifest.get("file_allowlist", [])) != allowed_paths:
        raise ValueError("file allowlist does not exactly match model inputs")
    return {
        "status": "PASS_EXACT_PAIRED_SHARD_ADMISSION",
        "split": split,
        "source_row_count": len(rows),
        "stored_native_crop_png_count": len(allowed_paths),
        "manifest_file_sha256": sha256_bytes(manifest_raw),
    }


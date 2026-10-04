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


FIXTURE_SCHEMA = "tactevra.ai_residual_obstruction_paired_height_fixture.v1"
SHARD_SCHEMA = "tactevra.ai_residual_obstruction_paired_height_shard.v1"
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
    sizes = fixture["output_contract"]["local_tensor_sizes_px"]
    if sizes != [[96, 96], [192, 192]]:
        raise ValueError("paired output sizes must be exactly 96 and 192")
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
        "total_model_input_pngs": 2 * (training + development),
    }


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
        source_sha = row.get("lossless_source_rgb_sha256")
        if not isinstance(source_sha, str) or len(source_sha) != 64:
            raise ValueError("missing lossless source hash")
        outputs = row.get("model_inputs")
        if not isinstance(outputs, dict) or set(outputs) != {"96", "192"}:
            raise ValueError("both and only 96/192 model inputs are required")
        for size in (96, 192):
            output = outputs[str(size)]
            if output.get("source_rgb_sha256") != source_sha:
                raise ValueError("paired inputs must derive from the same source pixels")
            if output.get("size_px") != [size, size]:
                raise ValueError("paired input dimensions differ from their role")
            relative = output.get("path")
            if not isinstance(relative, str) or not relative.endswith(".png"):
                raise ValueError("paired inputs must be lossless PNG paths")
            if relative in allowed_paths:
                raise ValueError("duplicate output path")
            allowed_paths.add(relative)
            digest = output.get("sha256")
            if not isinstance(digest, str) or len(digest) != 64:
                raise ValueError("missing paired input hash")
            if artifact_root is not None:
                payload = (artifact_root / relative).resolve(strict=True).read_bytes()
                if not payload.startswith(PNG_SIGNATURE):
                    raise ValueError(f"non-PNG payload: {relative}")
                if sha256_bytes(payload) != digest:
                    raise ValueError(f"paired input hash mismatch: {relative}")
                from PIL import Image

                with Image.open(artifact_root / relative) as image:
                    if image.size != (size, size):
                        raise ValueError(f"paired input pixel dimensions differ: {relative}")
    if seen != set(expected):
        raise ValueError("shard is missing frozen row identities")
    if set(manifest.get("file_allowlist", [])) != allowed_paths:
        raise ValueError("file allowlist does not exactly match model inputs")
    return {
        "status": "PASS_EXACT_PAIRED_SHARD_ADMISSION",
        "split": split,
        "source_row_count": len(rows),
        "model_input_png_count": len(allowed_paths),
        "manifest_file_sha256": sha256_bytes(manifest_raw),
    }


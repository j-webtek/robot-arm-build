from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import pytest

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT))

from train.paired_height_corpus_contract import (  # noqa: E402
    SHARD_SCHEMA,
    admit_shard_manifest,
    canonical,
    derive_model_input,
    expected_counts,
    iter_row_identities,
    load_fixture,
    sha256_bytes,
)


ROOT = AI_ROOT
FIXTURE = ROOT / "sim/evidence/residual_obstruction_paired_height_v1_1.json"


def test_frozen_fixture_counts_and_balances_heights() -> None:
    fixture, _ = load_fixture(FIXTURE)
    assert len(fixture["targets"]) == 80
    assert expected_counts(fixture) == fixture["planned_counts"] == {
        "training_source_rows": 46080,
        "development_source_rows": 69120,
        "total_source_rows": 115200,
        "stored_native_crop_pngs": 115200,
        "derived_model_tensors_per_loader_epoch": 230400,
    }
    training_heights = list(fixture["split_identities"]["training_scene_height_mm"].values())
    assert {height: training_heights.count(height) for height in set(training_heights)} == {
        700: 6,
        850: 5,
        1000: 5,
    }


def test_rows_are_deterministic_and_development_is_height_paired() -> None:
    fixture, _ = load_fixture(FIXTURE)
    first = list(iter_row_identities(fixture, "training"))[:20]
    assert first == list(iter_row_identities(fixture, "training"))[:20]
    assert len({row["camera_sample_seed"] for row in first}) == len(first)
    selected = [
        row
        for row in iter_row_identities(fixture, "development")
        if row["scene_id"] == "v5_development_scene_01"
        and row["appearance_id"] == "v5_development_light_01"
        and row["device"] == "keyboard"
        and row["target_id"] == "A"
        and row["variant_id"] == "clear"
    ]
    assert [row["height_board_mm"] for row in selected] == [700, 850, 1000]


def _write_manifest(tmp_path: Path, fixture: dict, fixture_raw: bytes) -> Path:
    identity = next(
        iter_row_identities(
            fixture,
            "training",
            scene_ids={"v5_training_scene_01"},
            target_keys={"keyboard:A"},
        )
    )
    # The selected shard has all appearances and variants for one target/scene.
    identities = list(
        iter_row_identities(
            fixture,
            "training",
            scene_ids={"v5_training_scene_01"},
            target_keys={"keyboard:A"},
        )
    )
    rows = []
    allowlist = []
    for row in identities:
        path = f"{row['row_id'].replace(':', '_')}_native.png"
        allowlist.append(path)
        rows.append(
            {
                **row,
                "native_crop": {
                    "path": path,
                    "sha256": hashlib.sha256(path.encode()).hexdigest(),
                    "size_px": [400, 400],
                    "full_frame_integer_bounds_px": [100, 200, 500, 600],
                    "aligned_model_crop_box_px": [0.25, 0.5, 399.25, 399.5],
                },
            }
        )
    assert identity in identities
    payload = {
        "schema": SHARD_SCHEMA,
        "fixture_file_sha256": sha256_bytes(fixture_raw),
        "fixture_bundle_sha256": fixture["bundle_sha256"],
        "split": "training",
        "shard": {"scene_ids": ["v5_training_scene_01"], "target_keys": ["keyboard:A"]},
        "observations": rows,
        "file_allowlist": allowlist,
    }
    path = tmp_path / "manifest.json"
    path.write_bytes(canonical(payload) + b"\n")
    return path


def test_exact_shard_admission_and_tampering_rejection(tmp_path: Path) -> None:
    fixture, fixture_raw = load_fixture(FIXTURE)
    manifest = _write_manifest(tmp_path, fixture, fixture_raw)
    receipt = admit_shard_manifest(FIXTURE, manifest)
    assert receipt["source_row_count"] == 36
    assert receipt["stored_native_crop_png_count"] == 36

    payload = json.loads(manifest.read_text())
    payload["observations"][0]["native_crop"]["full_frame_integer_bounds_px"][0] = 101
    manifest.write_bytes(canonical(payload) + b"\n")
    with pytest.raises(ValueError, match="YUY2 pairs"):
        admit_shard_manifest(FIXTURE, manifest)


def test_evaluation_split_is_rejected(tmp_path: Path) -> None:
    fixture, fixture_raw = load_fixture(FIXTURE)
    manifest = _write_manifest(tmp_path, fixture, fixture_raw)
    payload = json.loads(manifest.read_text())
    payload["split"] = "evaluation"
    manifest.write_bytes(canonical(payload) + b"\n")
    with pytest.raises(ValueError, match="evaluation or unknown split"):
        admit_shard_manifest(FIXTURE, manifest)


def test_camera_model_runs_before_resampling_and_requires_noise_for_qualification() -> None:
    import numpy as np

    native = np.full((400, 400, 3), 80, dtype=np.uint8)
    native[:, 198:202] = [12, 12, 12]
    with pytest.raises(ValueError, match="requires measured B0477 noise"):
        derive_model_input(
            native,
            aligned_crop_box_px=[0.0, 0.0, 400.0, 400.0],
            output_size_px=96,
            seed=7,
            noise_std_rgb=None,
            qualifying=True,
        )
    output_96 = derive_model_input(
        native,
        aligned_crop_box_px=[0.0, 0.0, 400.0, 400.0],
        output_size_px=96,
        seed=7,
        noise_std_rgb=[4.0, 4.0, 4.0],
        qualifying=False,
    )
    output_192 = derive_model_input(
        native,
        aligned_crop_box_px=[0.0, 0.0, 400.0, 400.0],
        output_size_px=192,
        seed=7,
        noise_std_rgb=[4.0, 4.0, 4.0],
        qualifying=False,
    )
    assert output_96.shape == (96, 96, 3)
    assert output_192.shape == (192, 192, 3)
    clear_96 = np.concatenate((output_96[:, :40], output_96[:, 56:]), axis=1)
    clear_192 = np.concatenate((output_192[:, :80], output_192[:, 112:]), axis=1)
    assert float(clear_96.std()) < float(clear_192.std())

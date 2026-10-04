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
    expected_counts,
    iter_row_identities,
    load_fixture,
    sha256_bytes,
)


ROOT = AI_ROOT
FIXTURE = ROOT / "sim/evidence/residual_obstruction_paired_height_v1.json"


def test_frozen_fixture_counts_and_balances_heights() -> None:
    fixture, _ = load_fixture(FIXTURE)
    assert len(fixture["targets"]) == 80
    assert expected_counts(fixture) == fixture["planned_counts"] == {
        "training_source_rows": 46080,
        "development_source_rows": 69120,
        "total_source_rows": 115200,
        "total_model_input_pngs": 230400,
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
        source = hashlib.sha256((row["row_id"] + ":source").encode()).hexdigest()
        outputs = {}
        for size in (96, 192):
            path = f"{row['row_id'].replace(':', '_')}_{size}.png"
            allowlist.append(path)
            outputs[str(size)] = {
                "path": path,
                "sha256": hashlib.sha256(path.encode()).hexdigest(),
                "size_px": [size, size],
                "source_rgb_sha256": source,
            }
        rows.append({**row, "lossless_source_rgb_sha256": source, "model_inputs": outputs})
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
    assert receipt["model_input_png_count"] == 72

    payload = json.loads(manifest.read_text())
    payload["observations"][0]["model_inputs"]["192"]["source_rgb_sha256"] = "0" * 64
    manifest.write_bytes(canonical(payload) + b"\n")
    with pytest.raises(ValueError, match="same source pixels"):
        admit_shard_manifest(FIXTURE, manifest)


def test_evaluation_split_is_rejected(tmp_path: Path) -> None:
    fixture, fixture_raw = load_fixture(FIXTURE)
    manifest = _write_manifest(tmp_path, fixture, fixture_raw)
    payload = json.loads(manifest.read_text())
    payload["split"] = "evaluation"
    manifest.write_bytes(canonical(payload) + b"\n")
    with pytest.raises(ValueError, match="evaluation or unknown split"):
        admit_shard_manifest(FIXTURE, manifest)

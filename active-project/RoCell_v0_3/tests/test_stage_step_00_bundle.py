from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "rc03_stage_step_00_bundle", ROOT / "scripts" / "stage_step_00_bundle.py"
)
assert SPEC and SPEC.loader
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_fixture(root: Path) -> None:
    step_name = "00 - Measure Hardware and Print Approved Parts"
    step_root = root / "BUILD_BY_STEP" / step_name
    technical = step_root / "99 - TECHNICAL RECORDS - DO NOT EDIT"
    models = step_root / "03 - STL MODELS"
    technical.mkdir(parents=True)
    models.mkdir()
    records = []
    rows = []
    for index in range(32):
        filename = f"model_{index:02d}.stl"
        canonical = root / "stl" / filename
        canonical.parent.mkdir(exist_ok=True)
        canonical.write_bytes(f"solid model-{index}\nendsolid model-{index}\n".encode())
        sha = digest(canonical)
        resolution = "local_hash_verified_copy" if index < 19 else "canonical_hash_bound_reference"
        records.append({"canonical_path": f"stl/{filename}", "sha256": sha, "artifact_resolution": resolution})
        rows.append(
            {
                "file": filename,
                "plain_name": filename,
                "use": "PRINT_VIA_READY_JOB_ONLY",
                "job_ids": "00A",
                "profiles": "test",
                "quantity_by_job": "00A:1",
                "selections": "required",
                "canonical_path": f"stl/{filename}",
                "sha256": sha,
                "artifact_resolution": resolution,
            }
        )
    (technical / "STEP_MANIFEST.json").write_text(
        json.dumps({"canonical_files": records}), encoding="utf-8"
    )
    with (models / "STL MODEL LIST.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (root / stage.VERIFIER).write_text("portable verifier\n", encoding="utf-8")
    files = [
        {"path": path.relative_to(root).as_posix(), "sha256": digest(path), "size_bytes": path.stat().st_size}
        for path in sorted(root.rglob("*"))
        if path.is_file()
    ]
    (root / stage.BUNDLE_MANIFEST).write_text(
        json.dumps({"schema": stage.SCHEMA, "step_folder": step_name, "files": files}),
        encoding="utf-8",
    )


class Step00BundleTests(unittest.TestCase):
    def test_portable_bundle_verifies_exact_inventory_and_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_fixture(root)
            result = stage.verify_bundle(root)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["stl_record_count"], 32)

    def test_hash_drift_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_fixture(root)
            (root / "stl" / "model_31.stl").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                stage.verify_bundle(root)

    def test_manifest_path_escape_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_fixture(root)
            manifest_path = root / stage.BUNDLE_MANIFEST
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"].append({"path": "../escape", "sha256": "0" * 64})
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "escapes"):
                stage.verify_bundle(root)


if __name__ == "__main__":
    unittest.main()

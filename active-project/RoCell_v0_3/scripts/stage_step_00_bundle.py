#!/usr/bin/env python3
"""Stage or verify a complete, standalone RC03 Step 00 bundle."""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BUILD_ROOT = ROOT / "BUILD_BY_STEP"
STEP_PREFIX = "00 - "
BUNDLE_MANIFEST = "STEP_00_BUNDLE_MANIFEST.json"
BUNDLE_README = "START_HERE_STEP_00_BUNDLE.md"
VERIFIER = "verify_step_00_bundle.py"
SCHEMA = "tactevra.rc03-step-00-bundle.v1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def contained_path(root: Path, relative: str) -> Path:
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"Bundle path escapes its root: {relative}") from exc
    return candidate


def verify_bundle(root: Path) -> dict[str, Any]:
    root = root.resolve()
    manifest_path = root / BUNDLE_MANIFEST
    manifest = read_object(manifest_path)
    if manifest.get("schema") != SCHEMA:
        raise ValueError("Unsupported or missing Step 00 bundle schema")
    step_folder = manifest.get("step_folder")
    if not isinstance(step_folder, str) or not step_folder.startswith(STEP_PREFIX):
        raise ValueError("Bundle manifest has an invalid Step 00 folder")
    entries = manifest.get("files")
    if not isinstance(entries, list) or not entries:
        raise ValueError("Bundle manifest has no file inventory")
    expected: dict[str, str] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Bundle file inventory contains a non-object entry")
        relative = entry.get("path")
        digest = entry.get("sha256")
        if not isinstance(relative, str) or not relative or not isinstance(digest, str):
            raise ValueError("Bundle file inventory contains an invalid entry")
        if relative in expected:
            raise ValueError(f"Duplicate bundle inventory path: {relative}")
        path = contained_path(root, relative)
        if not path.is_file():
            raise ValueError(f"Bundle file is missing: {relative}")
        if sha256(path) != digest:
            raise ValueError(f"Bundle file hash mismatch: {relative}")
        expected[relative] = digest
    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path != manifest_path
    }
    if actual != set(expected):
        missing = sorted(set(expected) - actual)
        unexpected = sorted(actual - set(expected))
        raise ValueError(f"Bundle inventory mismatch; missing={missing}, unexpected={unexpected}")

    step_root = root / "BUILD_BY_STEP" / step_folder
    step_manifest = read_object(
        step_root / "99 - TECHNICAL RECORDS - DO NOT EDIT" / "STEP_MANIFEST.json"
    )
    records = step_manifest.get("canonical_files")
    if not isinstance(records, list):
        raise ValueError("Step manifest canonical_files is invalid")
    stl_records = [
        record
        for record in records
        if isinstance(record, dict)
        and isinstance(record.get("canonical_path"), str)
        and record["canonical_path"].startswith("stl/")
        and record["canonical_path"].lower().endswith(".stl")
    ]
    if len(stl_records) != 32:
        raise ValueError(f"Expected 32 Step 00 STL records, found {len(stl_records)}")
    for record in records:
        relative = record.get("canonical_path")
        digest = record.get("sha256")
        if not isinstance(relative, str) or not isinstance(digest, str):
            raise ValueError("Step manifest contains an invalid canonical file record")
        canonical = contained_path(root, relative)
        if not canonical.is_file() or sha256(canonical) != digest:
            raise ValueError(f"Canonical bundle payload is missing or changed: {relative}")
    catalog_path = step_root / "03 - STL MODELS" / "STL MODEL LIST.csv"
    with catalog_path.open(encoding="utf-8", newline="") as stream:
        catalog = list(csv.DictReader(stream))
    if len(catalog) != len(stl_records):
        raise ValueError("Step 00 model catalog does not cover all STL records")
    if any(row.get("use") != "PRINT_VIA_READY_JOB_ONLY" for row in catalog):
        raise ValueError("Step 00 model catalog lost PRINT_VIA_READY_JOB_ONLY policy")
    if {row.get("artifact_resolution") for row in catalog} != {
        "local_hash_verified_copy",
        "canonical_hash_bound_reference",
    }:
        raise ValueError("Step 00 model catalog does not preserve both resolution classes")
    return {
        "schema": SCHEMA,
        "status": "PASS",
        "file_count": len(expected),
        "canonical_file_count": len(records),
        "stl_record_count": len(stl_records),
        "step_folder": step_folder,
    }


def load_builder() -> Any:
    source = ROOT / "scripts" / "build_step_packages.py"
    spec = importlib.util.spec_from_file_location("rc03_build_step_packages", source)
    if not spec or not spec.loader:
        raise RuntimeError(f"Could not load Step package builder: {source}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def stage_bundle(output: Path) -> dict[str, Any]:
    output = output.resolve()
    try:
        output.relative_to(ROOT.resolve())
    except ValueError:
        pass
    else:
        raise ValueError("Output must be outside the RC03 project tree")
    if output.exists():
        raise ValueError(f"Output must be a fresh path: {output}")
    builder = load_builder()
    validation = builder.validate_existing(write_report=False)
    if validation.get("status") != "PASS":
        errors = validation.get("errors")
        detail = "; ".join(str(item) for item in errors[:5]) if isinstance(errors, list) else "unknown validation error"
        raise ValueError(f"Tracked BUILD_BY_STEP package must validate before staging: {detail}")
    step_dirs = sorted(path for path in BUILD_ROOT.iterdir() if path.is_dir() and path.name.startswith(STEP_PREFIX))
    if len(step_dirs) != 1:
        raise ValueError(f"Expected one tracked Step 00 folder, found {len(step_dirs)}")
    source_step = step_dirs[0]
    try:
        output.mkdir(parents=True)
        staged_build_root = output / "BUILD_BY_STEP"
        staged_build_root.mkdir()
        for filename in builder.ROOT_CONTROL_FILES:
            shutil.copy2(BUILD_ROOT / filename, staged_build_root / filename)
        staged_step = staged_build_root / source_step.name
        shutil.copytree(source_step, staged_step)
        step_manifest = read_object(
            source_step / builder.STEP_TECHNICAL_DIRECTORY / "STEP_MANIFEST.json"
        )
        records = step_manifest.get("canonical_files")
        if not isinstance(records, list):
            raise ValueError("Tracked Step 00 manifest canonical_files is invalid")
        for record in records:
            if not isinstance(record, dict):
                raise ValueError("Tracked Step 00 manifest contains a non-object record")
            relative = record.get("canonical_path")
            digest = record.get("sha256")
            if not isinstance(relative, str) or not isinstance(digest, str):
                raise ValueError("Tracked Step 00 manifest contains an invalid canonical record")
            source = contained_path(ROOT, relative)
            if not source.is_file() or sha256(source) != digest:
                raise ValueError(f"Canonical source is missing or changed: {relative}")
            target = contained_path(output, relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        shutil.copy2(Path(__file__), output / VERIFIER)
        (output / BUNDLE_README).write_text(
            "# RC03 standalone Step 00 bundle\n\n"
            f"Start at `BUILD_BY_STEP/{source_step.name}/00 - START HERE.md`.\n\n"
            "All canonical inputs referenced by Step 00 are included at their original relative paths. "
            "The `PRINT_VIA_READY_JOB_ONLY` policy still applies; this bundle does not authorize printing.\n\n"
            "Verify before use:\n\n"
            "```text\npython verify_step_00_bundle.py --verify .\n```\n",
            encoding="utf-8",
        )
        files = [
            {"path": path.relative_to(output).as_posix(), "sha256": sha256(path), "size_bytes": path.stat().st_size}
            for path in sorted(output.rglob("*"))
            if path.is_file()
        ]
        (output / BUNDLE_MANIFEST).write_text(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "step_folder": source_step.name,
                    "source_package_definition_hash": step_manifest.get("package_definition_hash"),
                    "source_canonical_snapshot_hash": step_manifest.get("canonical_snapshot_hash"),
                    "files": files,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        return verify_bundle(output)
    except Exception:
        if output.is_dir():
            shutil.rmtree(output)
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--output", type=Path, help="fresh destination outside the RC03 project tree")
    group.add_argument("--verify", type=Path, help="standalone bundle root to verify")
    args = parser.parse_args()
    result = stage_bundle(args.output) if args.output else verify_bundle(args.verify)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

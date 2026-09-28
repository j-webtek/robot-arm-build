#!/usr/bin/env python3
"""Stage and verify hash-bound canonical artifacts outside the repository.

The step-package manifests identify canonical files by repository-relative path and
SHA-256.  This tool resolves those records without following paths outside the
project, materializes a self-contained staging tree, and writes a receipt that can
be verified after the tree is copied to a machine with no repository access.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = PROJECT_ROOT / "BUILD_BY_STEP"
RECEIPT_NAME = "HASH_BOUND_ARTIFACTS.json"
ARTIFACT_DIRECTORY = "artifacts"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_relative_path(value: object) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError("canonical_path must be a non-empty string")
    pure = PurePosixPath(value)
    if pure.is_absolute() or ".." in pure.parts or "." in pure.parts:
        raise ValueError(f"unsafe canonical_path: {value!r}")
    if not pure.parts or any(not part for part in pure.parts):
        raise ValueError(f"invalid canonical_path: {value!r}")
    return Path(*pure.parts)


def resolve_record(project_root: Path, record: dict[str, Any]) -> tuple[Path, Path, str]:
    relative = canonical_relative_path(record.get("canonical_path"))
    recorded_hash = record.get("sha256")
    if not isinstance(recorded_hash, str) or len(recorded_hash) != 64:
        raise ValueError(f"invalid SHA-256 for {relative.as_posix()}")
    try:
        int(recorded_hash, 16)
    except ValueError as exc:
        raise ValueError(f"invalid SHA-256 for {relative.as_posix()}") from exc

    root = project_root.resolve()
    source = (root / relative).resolve()
    try:
        source.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"canonical path escapes the project: {relative.as_posix()}") from exc
    if not source.is_file():
        raise FileNotFoundError(source)
    actual_hash = sha256(source)
    if actual_hash != recorded_hash:
        raise ValueError(
            f"hash mismatch for {relative.as_posix()}: expected {recorded_hash}, found {actual_hash}"
        )
    return relative, source, recorded_hash


def manifest_records(manifest_path: Path) -> list[dict[str, Any]]:
    value = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"manifest root must be an object: {manifest_path}")
    records = value.get("canonical_files")
    if not isinstance(records, list) or not all(isinstance(item, dict) for item in records):
        raise ValueError(f"manifest canonical_files must be a list of objects: {manifest_path}")
    return records


def collect_records(project_root: Path, manifests: Iterable[Path]) -> list[dict[str, str]]:
    collected: dict[str, dict[str, str]] = {}
    root = project_root.resolve()
    for manifest in manifests:
        resolved_manifest = manifest.resolve()
        if not resolved_manifest.is_file():
            raise FileNotFoundError(resolved_manifest)
        try:
            manifest_label = resolved_manifest.relative_to(root).as_posix()
        except ValueError:
            manifest_label = resolved_manifest.name
        for record in manifest_records(resolved_manifest):
            relative, _, recorded_hash = resolve_record(root, record)
            key = relative.as_posix()
            previous = collected.get(key)
            if previous and previous["sha256"] != recorded_hash:
                raise ValueError(f"conflicting hashes for canonical artifact {key}")
            if previous:
                sources = set(previous["source_manifests"].split(";"))
                sources.add(manifest_label)
                previous["source_manifests"] = ";".join(sorted(sources))
            else:
                collected[key] = {
                    "canonical_path": key,
                    "sha256": recorded_hash,
                    "source_manifests": manifest_label,
                }
    return [collected[key] for key in sorted(collected)]


def stage(project_root: Path, manifests: Iterable[Path], output: Path) -> dict[str, Any]:
    root = project_root.resolve()
    destination = output.resolve()
    if destination == root or root in destination.parents:
        raise ValueError("staging output must be outside the project checkout")
    if destination.exists():
        raise FileExistsError(f"refusing to overwrite existing staging output: {destination}")

    records = collect_records(root, manifests)
    artifact_root = destination / ARTIFACT_DIRECTORY
    artifact_root.mkdir(parents=True)
    for record in records:
        relative, source, _ = resolve_record(root, record)
        target = artifact_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        if sha256(target) != record["sha256"]:
            raise RuntimeError(f"staged artifact hash mismatch: {relative.as_posix()}")

    receipt = {
        "schema_version": 1,
        "artifact_root": ARTIFACT_DIRECTORY,
        "artifact_count": len(records),
        "artifacts": records,
    }
    (destination / RECEIPT_NAME).write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    verify(destination)
    return receipt


def verify(staged_root: Path) -> dict[str, Any]:
    base = staged_root.resolve()
    receipt_path = base / RECEIPT_NAME
    value = json.loads(receipt_path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise ValueError("unsupported or invalid staging receipt")
    records = value.get("artifacts")
    if not isinstance(records, list) or not all(isinstance(item, dict) for item in records):
        raise ValueError("staging receipt artifacts must be a list of objects")
    if value.get("artifact_count") != len(records):
        raise ValueError("staging receipt artifact_count is inconsistent")
    artifact_root = base / ARTIFACT_DIRECTORY
    expected: set[Path] = set()
    for record in records:
        relative = canonical_relative_path(record.get("canonical_path"))
        expected.add(relative)
        path = artifact_root / relative
        if not path.is_file():
            raise FileNotFoundError(path)
        recorded_hash = record.get("sha256")
        if sha256(path) != recorded_hash:
            raise ValueError(f"staged artifact hash mismatch: {relative.as_posix()}")
    actual = {
        path.relative_to(artifact_root)
        for path in artifact_root.rglob("*")
        if path.is_file()
    }
    if actual != expected:
        raise ValueError(
            "staged artifact inventory mismatch: "
            f"missing={sorted(str(path) for path in expected - actual)}, "
            f"unexpected={sorted(str(path) for path in actual - expected)}"
        )
    return {"status": "PASS", "artifact_count": len(records), "receipt": str(receipt_path)}


def all_step_manifests() -> list[Path]:
    return sorted(PACKAGE_ROOT.glob("*/99 - TECHNICAL RECORDS - DO NOT EDIT/STEP_MANIFEST.json"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", action="append", type=Path, default=[])
    parser.add_argument("--all-step-manifests", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()

    if args.verify:
        if args.manifest or args.all_step_manifests or args.output:
            parser.error("--verify cannot be combined with staging options")
        result = verify(args.verify)
    else:
        manifests = list(args.manifest)
        if args.all_step_manifests:
            manifests.extend(all_step_manifests())
        manifests = sorted({path.resolve() for path in manifests})
        if not manifests or args.output is None:
            parser.error("staging requires --output and at least one manifest source")
        receipt = stage(PROJECT_ROOT, manifests, args.output)
        result = {
            "status": "PASS",
            "artifact_count": receipt["artifact_count"],
            "receipt": str(args.output.resolve() / RECEIPT_NAME),
        }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

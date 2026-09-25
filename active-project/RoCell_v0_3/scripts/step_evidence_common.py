#!/usr/bin/env python3
"""Shared fail-closed helpers for operator step-evidence recorders."""
from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import build_step_packages as packages


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "BUILD_BY_STEP"
SENTINEL = PACKAGE / packages.SENTINEL
ACTIVE_PATH = PACKAGE / packages.ACTIVE_BUILD_FILE
INDEX_PATH = PACKAGE / "INDEX.json"
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")


class EvidenceError(ValueError):
    """Raised when operator evidence cannot be changed safely."""


@dataclass(frozen=True)
class EvidenceContext:
    step_id: str
    build_id: str
    step_dir: Path
    build_dir: Path
    measurement_path: Path
    signoff_path: Path
    manifest: dict[str, Any]


def read_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise EvidenceError(f"{label} is unreadable JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise EvidenceError(f"{label} root must be an object")
    return value


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def _direct_child(parent: Path, name: str, label: str) -> Path:
    if not isinstance(name, str) or not name:
        raise EvidenceError(f"{label} is missing")
    try:
        parent_resolved = parent.resolve()
        child = (parent / name).resolve()
    except (OSError, ValueError) as exc:
        raise EvidenceError(f"{label} is not a valid filesystem name: {exc}") from exc
    if child.parent != parent_resolved:
        raise EvidenceError(f"{label} must resolve to one direct child of {parent}")
    return child


def load_context(step_id: str) -> EvidenceContext:
    if re.fullmatch(r"\d{2}", step_id or "") is None:
        raise EvidenceError("step must be a two-digit ID from 00 through 15")
    if not PACKAGE.is_dir() or not SENTINEL.is_file():
        raise EvidenceError("BUILD_BY_STEP is missing or unrecognized; regenerate it first")

    active = read_json_object(ACTIVE_PATH, "ACTIVE_BUILD.json")
    build_id = active.get("active_build_id")
    if not packages.valid_build_id(build_id):
        raise EvidenceError("no valid active build ID is selected; run scripts/set_active_build.py first")

    index = read_json_object(INDEX_PATH, "INDEX.json")
    if index.get("layout_version") != packages.LAYOUT_VERSION:
        raise EvidenceError("INDEX.json layout version is stale; regenerate BUILD_BY_STEP")
    rows = index.get("steps")
    if not isinstance(rows, list):
        raise EvidenceError("INDEX.json steps must be a list")
    matches = [row for row in rows if isinstance(row, dict) and row.get("id") == step_id]
    if len(matches) != 1:
        raise EvidenceError(f"INDEX.json must contain exactly one Step {step_id} row")

    step_dir = _direct_child(PACKAGE, matches[0].get("folder"), f"Step {step_id} folder")
    if not step_dir.is_dir():
        raise EvidenceError(f"Step {step_id} folder does not exist; regenerate BUILD_BY_STEP")
    manifest_path = step_dir / packages.STEP_MANIFEST_FILE
    manifest = read_json_object(manifest_path, f"Step {step_id} manifest")
    if manifest.get("step_id") != step_id:
        raise EvidenceError(f"Step {step_id} manifest identity does not match")
    if manifest.get("layout_version") != packages.LAYOUT_VERSION:
        raise EvidenceError(f"Step {step_id} manifest layout version is stale")
    if manifest.get("active_build_id") != build_id:
        raise EvidenceError("active build selection changed after generation; regenerate BUILD_BY_STEP")

    evidence_root = step_dir / packages.STEP_EVIDENCE_DIRECTORY
    build_dir = _direct_child(evidence_root, build_id, "active build evidence folder")
    if not build_dir.is_dir():
        raise EvidenceError(
            f"Step {step_id} evidence is not initialized for {build_id}; "
            f"run scripts/initialize_step_evidence.py --step {step_id}"
        )
    measurement_path = build_dir / packages.MEASUREMENT_RECORD_FILE
    signoff_path = build_dir / packages.SIGNOFF_RECORD_FILE
    if not measurement_path.is_file() or not signoff_path.is_file():
        raise EvidenceError("active build evidence is incomplete; measurement/signoff JSON is missing")
    return EvidenceContext(
        step_id=step_id,
        build_id=build_id,
        step_dir=step_dir,
        build_dir=build_dir,
        measurement_path=measurement_path,
        signoff_path=signoff_path,
        manifest=manifest,
    )


def load_record_pair(context: EvidenceContext) -> tuple[dict[str, Any], dict[str, Any]]:
    measurement = read_json_object(context.measurement_path, "measurement_record.json")
    signoff = read_json_object(context.signoff_path, "signoff.json")
    expected_definition = context.manifest.get("package_definition_hash")
    if not isinstance(expected_definition, str) or SHA256_RE.fullmatch(expected_definition) is None:
        raise EvidenceError("step manifest has no valid package definition hash")

    snapshot_values: list[str] = []
    for label, record in (("measurement_record.json", measurement), ("signoff.json", signoff)):
        if record.get("schema_version") != 1:
            raise EvidenceError(f"{label} schema_version must be 1")
        if record.get("step_id") != context.step_id or record.get("build_id") != context.build_id:
            raise EvidenceError(f"{label} step/build identity does not match the active context")
        if record.get("design_revision") != context.manifest.get("design_revision"):
            raise EvidenceError(f"{label} design revision does not match the step manifest")
        if record.get("package_definition_hash") != expected_definition:
            raise EvidenceError(f"{label} was created for a different package definition; start a new build ID")
        snapshot = record.get("canonical_snapshot_hash")
        alias = record.get("canonical_input_hash")
        if not isinstance(snapshot, str) or SHA256_RE.fullmatch(snapshot) is None or alias != snapshot:
            raise EvidenceError(f"{label} canonical snapshot provenance is invalid")
        snapshot_values.append(snapshot)
    if snapshot_values[0] != snapshot_values[1]:
        raise EvidenceError("measurement and signoff records came from different canonical snapshots")
    return measurement, signoff


def require_nonblank_text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EvidenceError(f"{label} must be nonblank text")
    return value.strip()


def has_recorded_value(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict, tuple, set)):
        return bool(value)
    return True


def resolve_existing_evidence_paths(build_dir: Path, raw_paths: Iterable[object]) -> list[str]:
    paths = list(raw_paths)
    if not paths:
        raise EvidenceError("at least one --evidence path is required")
    try:
        build_root = build_dir.resolve()
    except (OSError, ValueError) as exc:
        raise EvidenceError(f"active build evidence path is invalid: {exc}") from exc
    resolved_values: list[str] = []
    for raw in paths:
        text = require_nonblank_text(raw, "evidence path")
        relative = Path(text)
        if relative.is_absolute() or relative.drive or relative.root:
            raise EvidenceError(f"evidence path must be relative to the build-ID folder: {text!r}")
        try:
            candidate = (build_dir / relative).resolve(strict=True)
        except (OSError, ValueError) as exc:
            raise EvidenceError(f"evidence file does not exist or is invalid: {text!r}: {exc}") from exc
        try:
            stored = candidate.relative_to(build_root).as_posix()
        except ValueError as exc:
            raise EvidenceError(f"evidence path escapes the build-ID folder: {text!r}") from exc
        if not candidate.is_file():
            raise EvidenceError(f"evidence path must point to an existing file: {text!r}")
        if stored in {
            packages.MEASUREMENT_RECORD_FILE,
            packages.SIGNOFF_RECORD_FILE,
        }:
            raise EvidenceError("measurement/signoff JSON cannot be used as its own physical evidence")
        if stored not in resolved_values:
            resolved_values.append(stored)
    return resolved_values

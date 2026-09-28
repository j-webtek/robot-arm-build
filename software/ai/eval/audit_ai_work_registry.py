"""Audit the maintained AI work registry and emit a zero-authority receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_REGISTRY = ROOT / "software" / "ai" / "docs" / "AI_WORK_REGISTRY.json"
SCHEMA = ROOT / "software" / "ai" / "schemas" / "ai_work_registry_v1.schema.json"
RECEIPT_SCHEMA = ROOT / "software" / "ai" / "schemas" / "ai_work_registry_audit_v1.schema.json"


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def load_strict_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicates)
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def canonical_hash(value: Any) -> str:
    rendered = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(rendered).hexdigest()


def _resolve(root: Path, relative: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"registry path must be relative and contained: {relative}")
    root = root.resolve(strict=True)
    resolved = (root / candidate).resolve(strict=True)
    if resolved == root or root not in resolved.parents:
        raise ValueError(f"registry path escapes repository: {relative}")
    return resolved


def audit_registry(registry_path: Path = DEFAULT_REGISTRY, root: Path = ROOT) -> dict[str, Any]:
    registry = load_strict_json(registry_path)
    schema = load_strict_json(SCHEMA)
    errors = sorted(
        Draft202012Validator(schema).iter_errors(registry),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        first = errors[0]
        where = ".".join(str(part) for part in first.absolute_path) or "$"
        raise ValueError(f"schema validation failed at {where}: {first.message}")

    core = {key: value for key, value in registry.items() if key != "registry_sha256"}
    if registry["registry_sha256"] != canonical_hash(core):
        raise ValueError("registry SHA-256 mismatch")

    ids: set[str] = set()
    owned_tests: dict[str, str] = {}
    referenced_paths: set[str] = set()
    for stream in registry["workstreams"]:
        stream_id = stream["workstream_id"]
        if stream_id in ids:
            raise ValueError(f"duplicate workstream ID: {stream_id}")
        ids.add(stream_id)
        for field in ("source_paths", "test_paths", "documentation_paths", "evidence_paths"):
            for relative in stream[field]:
                _resolve(root, relative)
                referenced_paths.add(relative)
        for relative in stream["test_paths"]:
            if relative in owned_tests:
                raise ValueError(
                    f"test has multiple workstream owners: {relative} "
                    f"({owned_tests[relative]}, {stream_id})"
                )
            owned_tests[relative] = stream_id

    tracked_tests = {
        path.relative_to(root).as_posix()
        for path in (root / "software" / "ai" / "tests").glob("test_*.py")
        if path.is_file()
    }
    documented_tests = set(owned_tests)
    missing = sorted(tracked_tests - documented_tests)
    untracked = sorted(documented_tests - tracked_tests)
    if missing or untracked:
        raise ValueError(
            "AI test ownership mismatch; missing=" + repr(missing)
            + "; untracked=" + repr(untracked)
        )

    receipt_core = {
        "schema": "tactevra.ai_work_registry_audit.v1",
        "status": "PASS",
        "registry_sha256": registry["registry_sha256"],
        "workstream_count": len(ids),
        "tracked_ai_test_count": len(tracked_tests),
        "documented_ai_test_count": len(documented_tests),
        "referenced_path_count": len(referenced_paths),
        "unowned_test_paths": [],
        "multiply_owned_test_paths": [],
        "controller_authority": False,
        "hardware_writes": 0,
        "physical_movements": 0,
        "limitations": [
            "The registry proves documentation coverage and path integrity, not model correctness.",
            "Evaluation claims remain governed by their frozen artifacts and evidence-ledger entries."
        ],
    }
    receipt = {**receipt_core, "receipt_sha256": canonical_hash(receipt_core)}
    Draft202012Validator(load_strict_json(RECEIPT_SCHEMA)).validate(receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    receipt = audit_registry(args.registry)
    rendered = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(rendered.encode("utf-8"))
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

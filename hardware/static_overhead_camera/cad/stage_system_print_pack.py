"""Materialize or verify a standalone, offline SYSTEM_PRINT_PACK_v1 export."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
CAMERA_ROOT = Path(__file__).resolve().parent.parent
PACK_ROOT = CAMERA_ROOT / "cad/output/revisions/SYSTEM_PRINT_PACK_v1"
REFERENCE_FILE = "STL_HASH_REFERENCES.json"
RECEIPT_FILE = "STAGED_PACK_RECEIPT.json"


class PackError(ValueError):
    """Raised when a pack reference or staged export fails closed."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_child(root: Path, relative: str, label: str) -> Path:
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise PackError(f"{label} escapes its allowed root: {relative}") from exc
    return candidate


def load_references(pack_root: Path = PACK_ROOT) -> list[dict[str, object]]:
    manifest_path = pack_root / REFERENCE_FILE
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PackError(f"Reference manifest is unreadable: {manifest_path}") from exc
    if payload.get("schema") != "tactevra.camera-print-pack.hash-bound-stl-references.v1":
        raise PackError("Reference manifest schema is unsupported")
    references = payload.get("references")
    if not isinstance(references, list) or not references:
        raise PackError("Reference manifest must contain references")
    return references


def verify_sources(references: list[dict[str, object]]) -> None:
    seen_targets: set[str] = set()
    for entry in references:
        target = entry.get("target")
        canonical = entry.get("canonical")
        expected = entry.get("sha256")
        if not all(isinstance(value, str) and value for value in (target, canonical, expected)):
            raise PackError("Every reference requires target, canonical, and sha256 strings")
        if target in seen_targets:
            raise PackError(f"Duplicate reference target: {target}")
        seen_targets.add(target)
        safe_child(PACK_ROOT, target, "target")
        source = safe_child(REPO_ROOT, canonical, "canonical source")
        if not source.is_file():
            raise PackError(f"Canonical source is missing: {canonical}")
        actual = sha256(source)
        if actual != expected:
            raise PackError(f"Canonical source hash mismatch: {canonical}: {actual} != {expected}")


def verify_sidecar_closure(pack_root: Path) -> int:
    checked = 0
    for sidecar_path in sorted(pack_root.rglob("*.print.json")):
        try:
            sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise PackError(f"Print sidecar is unreadable: {sidecar_path}") from exc
        objects = sidecar.get("objects", [])
        if not isinstance(objects, list):
            raise PackError(f"Print sidecar objects must be a list: {sidecar_path}")
        for item in objects:
            relative = item.get("stl") if isinstance(item, dict) else None
            if not isinstance(relative, str) or not relative:
                raise PackError(f"Print sidecar object lacks an STL path: {sidecar_path}")
            target = safe_child(pack_root, str(sidecar_path.parent.relative_to(pack_root) / relative), "sidecar STL")
            if not target.is_file():
                raise PackError(f"Standalone dependency is missing: {target.relative_to(pack_root)}")
            checked += 1
    return checked


def verify_staged(output: Path, references: list[dict[str, object]]) -> dict[str, object]:
    output = output.resolve()
    if not output.is_dir():
        raise PackError(f"Staged pack does not exist: {output}")
    if not (output / "START_HERE.md").is_file():
        raise PackError("Staged pack is missing START_HERE.md")
    for entry in references:
        target = safe_child(output, str(entry["target"]), "staged target")
        if not target.is_file():
            raise PackError(f"Staged target is missing: {entry['target']}")
        actual = sha256(target)
        if actual != entry["sha256"]:
            raise PackError(f"Staged target hash mismatch: {entry['target']}")
    closure_count = verify_sidecar_closure(output)
    return {
        "schema": "tactevra.camera-print-pack.stage-receipt.v1",
        "status": "PASS",
        "reference_count": len(references),
        "sidecar_stl_dependencies_verified": closure_count,
    }


def stage(output: Path) -> dict[str, object]:
    output = output.resolve()
    if output.exists():
        raise PackError(f"Output must not already exist: {output}")
    try:
        output.relative_to(REPO_ROOT.resolve())
    except ValueError:
        pass
    else:
        raise PackError("Standalone staging output must be outside the repository")
    references = load_references()
    verify_sources(references)
    shutil.copytree(PACK_ROOT, output)
    shutil.copy2(Path(__file__), output / "verify_system_print_pack.py")
    for entry in references:
        source = safe_child(REPO_ROOT, str(entry["canonical"]), "canonical source")
        target = safe_child(output, str(entry["target"]), "staged target")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    receipt = verify_staged(output, references)
    (output / RECEIPT_FILE).write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--output", type=Path, help="fresh destination outside the repository")
    mode.add_argument("--verify", type=Path, help="existing staged pack to verify")
    args = parser.parse_args()
    if args.output:
        receipt = stage(args.output)
    else:
        references = load_references(args.verify)
        receipt = verify_staged(args.verify, references)
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Hash and strict-JSON checks for immutable RC03 imports."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping, Sequence


_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class BuildIntegrityError(RuntimeError):
    def __init__(self, errors: Iterable[str]) -> None:
        self.errors = tuple(str(error) for error in errors)
        super().__init__("; ".join(self.errors) or "RC03 integrity verification failed")


def _object_without_duplicates(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON field {key!r}")
        result[key] = value
    return result


def load_json_object(path: Path) -> dict[str, Any]:
    try:
        document = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_object_without_duplicates,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError(f"Nonfinite JSON constant {value!r}")
            ),
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise BuildIntegrityError((f"Could not read strict JSON {path}: {exc}",)) from exc
    if not isinstance(document, dict):
        raise BuildIntegrityError((f"Expected a JSON object in {path}",))
    return document


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_beneath(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative.strip():
        raise BuildIntegrityError(("Frozen source path is empty",))
    normalized_parts = tuple(
        part for part in relative.replace("\\", "/").split("/") if part not in ("", ".")
    )
    candidate = root.joinpath(*normalized_parts).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise BuildIntegrityError((f"Frozen source escapes RC03 root: {relative}",)) from exc
    return candidate


def verify_snapshot_sources(
    rc03_root: Path,
    source_entries: Iterable[Mapping[str, Any]],
) -> dict[str, str]:
    errors: list[str] = []
    verified: dict[str, str] = {}
    seen: set[str] = set()
    for index, entry in enumerate(source_entries):
        if not isinstance(entry, Mapping):
            errors.append(f"Frozen source entry {index} is not an object")
            continue
        relative = entry.get("path")
        expected = entry.get("sha256")
        if not isinstance(relative, str) or not relative:
            errors.append(f"Frozen source entry {index} has no path")
            continue
        if relative in seen:
            errors.append(f"Duplicate frozen source path: {relative}")
            continue
        seen.add(relative)
        if not isinstance(expected, str) or not _SHA256.fullmatch(expected):
            errors.append(f"Frozen source {relative} has an invalid SHA-256 digest")
            continue
        try:
            path = resolve_beneath(rc03_root, relative)
        except BuildIntegrityError as exc:
            errors.extend(exc.errors)
            continue
        if not path.is_file():
            errors.append(f"Missing frozen source: {relative}")
            continue
        actual = sha256_file(path)
        if actual != expected:
            errors.append(
                f"Frozen source hash mismatch for {relative}: expected {expected}, got {actual}"
            )
            continue
        verified[relative] = actual
    if not verified:
        errors.append("RC03 source snapshot is empty")
    if errors:
        raise BuildIntegrityError(errors)
    return verified

"""Strict, dependency-free validation helpers for simulation inputs."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping


class SimulationSourceError(ValueError):
    """A simulation source is missing, malformed, or mutually inconsistent."""


def identifier(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SimulationSourceError(f"{name} must be a non-empty string")
    return value.strip()


def finite(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SimulationSourceError(f"{name} must be a real number")
    result = float(value)
    if not math.isfinite(result):
        raise SimulationSourceError(f"{name} must be finite")
    return result


def positive(value: object, name: str) -> float:
    result = finite(value, name)
    if result <= 0.0:
        raise SimulationSourceError(f"{name} must be greater than zero")
    return result


def sequence(value: object, length: int, name: str) -> tuple[Any, ...]:
    if not isinstance(value, (list, tuple)) or len(value) != length:
        raise SimulationSourceError(f"{name} must contain exactly {length} values")
    return tuple(value)


def mapping(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SimulationSourceError(f"{name} must be an object")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _reject_duplicate_pairs(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SimulationSourceError(f"Duplicate JSON key {key!r}")
        result[key] = value
    return result


def load_json_object(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SimulationSourceError(f"Cannot read simulation source {path}: {exc}") from exc
    try:
        value = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_pairs,
            parse_constant=lambda constant: (_ for _ in ()).throw(
                SimulationSourceError(
                    f"Nonfinite JSON constant {constant!r} is not allowed"
                )
            ),
        )
    except (json.JSONDecodeError, SimulationSourceError) as exc:
        raise SimulationSourceError(f"Invalid JSON source {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SimulationSourceError(f"Simulation source {path} must contain a JSON object")
    return value


def source_path(root: Path, relative: str) -> Path:
    resolved_root = root.resolve()
    path = (resolved_root / relative).resolve()
    try:
        path.relative_to(resolved_root)
    except ValueError as exc:
        raise SimulationSourceError(f"Simulation source escapes root: {relative}") from exc
    return path

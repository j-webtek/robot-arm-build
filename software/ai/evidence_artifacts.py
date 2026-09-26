"""Verify frozen AI evidence without pretending ignored training bytes are committed."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path, PurePosixPath
import re
from typing import Mapping


_SHA256 = re.compile(r"[0-9a-f]{64}")
_EXTERNAL_PREFIX = ("software", "ai", "results")


@dataclass(frozen=True)
class ArtifactStatus:
    relative_path: str
    sha256: str
    bytes_present: bool


def verify_frozen_artifacts(
    root: Path, expected: Mapping[str, str]
) -> tuple[ArtifactStatus, ...]:
    """Verify hashes, allowing only ignored AI result bytes to be absent.

    A missing committed/source artifact is an error.  A checkpoint below the
    repository's ignored ``software/ai/results`` directory remains explicit in
    the returned status.  If those local bytes are present, they are hashed too.
    """

    statuses: list[ArtifactStatus] = []
    resolved_root = root.resolve()
    for relative_path, expected_sha256 in expected.items():
        pure_path = PurePosixPath(relative_path)
        if (
            pure_path.is_absolute()
            or ".." in pure_path.parts
            or not relative_path
        ):
            raise AssertionError(f"unsafe artifact path: {relative_path!r}")
        if _SHA256.fullmatch(expected_sha256) is None:
            raise AssertionError(f"invalid SHA256 for {relative_path}: {expected_sha256!r}")

        artifact = (resolved_root / Path(*pure_path.parts)).resolve()
        if resolved_root not in artifact.parents:
            raise AssertionError(f"artifact escapes repository root: {relative_path}")
        is_external = pure_path.parts[: len(_EXTERNAL_PREFIX)] == _EXTERNAL_PREFIX

        if not artifact.is_file():
            if not is_external:
                raise AssertionError(f"required repository artifact missing: {relative_path}")
            statuses.append(ArtifactStatus(relative_path, expected_sha256, False))
            continue

        actual = hashlib.sha256(artifact.read_bytes()).hexdigest()
        if actual != expected_sha256:
            raise AssertionError(
                f"artifact SHA256 mismatch for {relative_path}: "
                f"expected {expected_sha256}, got {actual}"
            )
        statuses.append(ArtifactStatus(relative_path, expected_sha256, True))
    return tuple(statuses)

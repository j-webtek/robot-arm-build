"""Exact-byte bounded loading for pinned application URDF inputs.

Application services revalidate their complete source context before running,
but a mutable path can still change after that boundary check.  This helper
captures one bounded byte snapshot, verifies its exact digest, and parses that
same snapshot without reopening the path.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path

from rocell.geometry import UrdfModel, parse_urdf


MAX_PINNED_URDF_BYTES = 1_000_000
_LOWER_HEX = frozenset("0123456789abcdef")


class PinnedModelLoadError(ValueError):
    """Pinned model bytes violate the bounded exact-byte contract."""


@dataclass(frozen=True, slots=True)
class LoadedPinnedUrdf:
    """Parsed model plus the identity of the exact bytes that produced it."""

    model: UrdfModel
    sha256: str
    byte_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.model, UrdfModel):
            raise TypeError("model must be an UrdfModel")
        if len(self.sha256) != 64 or any(
            character not in _LOWER_HEX for character in self.sha256
        ):
            raise PinnedModelLoadError(
                "loaded model SHA-256 must be lowercase hexadecimal"
            )
        if (
            isinstance(self.byte_count, bool)
            or not isinstance(self.byte_count, int)
            or not 0 < self.byte_count <= MAX_PINNED_URDF_BYTES
        ):
            raise PinnedModelLoadError("loaded model byte count is out of bounds")


def load_pinned_urdf(
    path: str | Path,
    expected_sha256: str,
) -> LoadedPinnedUrdf:
    """Load, hash, and parse one exact URDF snapshot with a MAX+1 sentinel."""

    source = Path(path)
    if (
        not isinstance(expected_sha256, str)
        or len(expected_sha256) != 64
        or any(character not in _LOWER_HEX for character in expected_sha256)
    ):
        raise PinnedModelLoadError(
            "expected model SHA-256 must be lowercase hexadecimal"
        )

    digest = hashlib.sha256()
    chunks: list[bytes] = []
    actual_bytes = 0
    try:
        with source.open("rb") as stream:
            while True:
                remaining_with_sentinel = MAX_PINNED_URDF_BYTES - actual_bytes + 1
                chunk = stream.read(min(65_536, remaining_with_sentinel))
                if not chunk:
                    break
                actual_bytes += len(chunk)
                if actual_bytes > MAX_PINNED_URDF_BYTES:
                    raise PinnedModelLoadError(
                        "pinned model exceeds its byte limit"
                    )
                digest.update(chunk)
                chunks.append(chunk)
    except OSError as exc:
        raise PinnedModelLoadError(f"cannot read pinned model {source}") from exc

    actual_sha256 = digest.hexdigest()
    if actual_sha256 != expected_sha256:
        raise PinnedModelLoadError("pinned model byte hash mismatch")
    payload = b"".join(chunks)
    try:
        model = parse_urdf(payload.decode("utf-8"), source_name=str(source))
    except (UnicodeDecodeError, ValueError) as exc:
        raise PinnedModelLoadError(
            "pinned model is not valid UTF-8 URDF"
        ) from exc
    return LoadedPinnedUrdf(model, actual_sha256, actual_bytes)


__all__ = [
    "MAX_PINNED_URDF_BYTES",
    "LoadedPinnedUrdf",
    "PinnedModelLoadError",
    "load_pinned_urdf",
]

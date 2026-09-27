"""Validate a compact external-artifact manifest and inspect local bytes.

The command never downloads, copies, or modifies an artifact. Its JSON result
distinguishes an intentionally unavailable external artifact from invalid,
mismatched, and verified states.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import date
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any


SHA256 = re.compile(r"[0-9a-f]{64}")
COMMIT = re.compile(r"[0-9a-f]{40}")
ARTIFACT_ID = re.compile(r"[a-z0-9][a-z0-9._-]{2,127}")
FIELDS = {
    "schema_version", "artifact_id", "artifact_kind", "repository_path",
    "sha256", "size_bytes", "storage", "required_for", "provenance",
    "retention", "limitations",
}
KINDS = {"model-checkpoint", "dataset", "bulk-evidence", "other"}


@dataclass(frozen=True)
class ArtifactResult:
    status: str
    artifact_id: str
    repository_path: str
    expected_sha256: str
    expected_size_bytes: int
    actual_sha256: str | None = None
    actual_size_bytes: int | None = None


def _nonempty_strings(value: Any, field: str) -> list[str]:
    if (not isinstance(value, list) or not value
            or any(not isinstance(item, str) or not item.strip() for item in value)):
        raise ValueError(f"{field} must be a non-empty list of non-empty strings")
    return value


def load_manifest(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or set(document) != FIELDS:
        raise ValueError(f"manifest must contain exactly {sorted(FIELDS)}")
    if document["schema_version"] != 1:
        raise ValueError("schema_version must be 1")
    if (not isinstance(document["artifact_id"], str)
            or ARTIFACT_ID.fullmatch(document["artifact_id"]) is None):
        raise ValueError("artifact_id must be a lowercase stable identifier")
    if document["artifact_kind"] not in KINDS:
        raise ValueError(f"artifact_kind must be one of {sorted(KINDS)}")
    if document["storage"] != "external":
        raise ValueError("storage must be external")

    relative = document["repository_path"]
    if not isinstance(relative, str):
        raise ValueError("repository_path must be a string")
    pure = PurePosixPath(relative.replace("\\", "/"))
    if (not relative or pure.is_absolute() or ".." in pure.parts
            or pure.as_posix() != relative):
        raise ValueError("repository_path must be a normalized repository-relative path")
    if not relative.startswith("software/ai/results/"):
        raise ValueError("repository_path must be below ignored software/ai/results/")
    if not isinstance(document["sha256"], str) or SHA256.fullmatch(document["sha256"]) is None:
        raise ValueError("sha256 must be 64 lowercase hexadecimal characters")
    if (not isinstance(document["size_bytes"], int)
            or isinstance(document["size_bytes"], bool)
            or document["size_bytes"] <= 0):
        raise ValueError("size_bytes must be a positive integer")
    _nonempty_strings(document["required_for"], "required_for")
    _nonempty_strings(document["limitations"], "limitations")

    provenance = document["provenance"]
    if (not isinstance(provenance, dict)
            or set(provenance) != {"source_commit", "producer_command"}):
        raise ValueError("provenance must contain source_commit and producer_command")
    if (not isinstance(provenance["source_commit"], str)
            or COMMIT.fullmatch(provenance["source_commit"]) is None):
        raise ValueError("provenance.source_commit must be a full lowercase Git SHA")
    if (not isinstance(provenance["producer_command"], str)
            or not provenance["producer_command"].strip()):
        raise ValueError("provenance.producer_command must be non-empty")

    retention = document["retention"]
    if (not isinstance(retention, dict)
            or set(retention) != {"owner", "review_after"}):
        raise ValueError("retention must contain owner and review_after")
    if not isinstance(retention["owner"], str) or not retention["owner"].strip():
        raise ValueError("retention.owner must be non-empty")
    try:
        date.fromisoformat(retention["review_after"])
    except (TypeError, ValueError) as exc:
        raise ValueError("retention.review_after must be an ISO date") from exc
    return document


def inspect_artifact(root: Path, manifest: dict[str, Any]) -> ArtifactResult:
    resolved_root = root.resolve()
    relative = manifest["repository_path"]
    artifact = (resolved_root / Path(*PurePosixPath(relative).parts)).resolve()
    if resolved_root not in artifact.parents:
        raise ValueError("artifact path escapes the repository root")

    base = dict(
        artifact_id=manifest["artifact_id"],
        repository_path=relative,
        expected_sha256=manifest["sha256"],
        expected_size_bytes=manifest["size_bytes"],
    )
    if not artifact.is_file():
        return ArtifactResult(status="external_artifact_unavailable", **base)

    actual_size = artifact.stat().st_size
    digest = hashlib.sha256()
    with artifact.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    actual_sha = digest.hexdigest()
    status = "verified"
    if actual_size != manifest["size_bytes"]:
        status = "size_mismatch"
    elif actual_sha != manifest["sha256"]:
        status = "digest_mismatch"
    return ArtifactResult(
        status=status, actual_sha256=actual_sha,
        actual_size_bytes=actual_size, **base,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--allow-unavailable", action="store_true",
        help="Return success for the explicit external_artifact_unavailable state.",
    )
    args = parser.parse_args()
    try:
        result = inspect_artifact(args.root, load_manifest(args.manifest))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "invalid_manifest", "error": str(exc)}, sort_keys=True))
        raise SystemExit(1) from exc
    print(json.dumps(asdict(result), sort_keys=True))
    if result.status == "verified":
        return
    if result.status == "external_artifact_unavailable" and args.allow_unavailable:
        return
    raise SystemExit(2 if result.status == "external_artifact_unavailable" else 1)


if __name__ == "__main__":
    main()

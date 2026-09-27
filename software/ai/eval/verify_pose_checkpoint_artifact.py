"""Emit a deterministic receipt for the pose-keyloss external checkpoint."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "ci"))

from check_external_artifact import inspect_artifact, load_manifest  # noqa: E402


DEFAULT_MANIFEST = ROOT / "software/ai/manifests/translation_weighted_pose_keyloss_v0.external.json"
CHECKER = ROOT / "scripts/ci/check_external_artifact.py"
STATUSES = {"external_artifact_unavailable", "verified"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(root: Path, manifest_path: Path, expected_status: str) -> dict:
    if expected_status not in STATUSES:
        raise ValueError(f"expected_status must be one of {sorted(STATUSES)}")
    manifest = load_manifest(manifest_path)
    result = inspect_artifact(root, manifest)
    if result.status != expected_status:
        raise ValueError(
            f"expected {expected_status}, observed {result.status}"
        )
    return {
        "schema": "tactevra.pose_checkpoint_external_artifact_receipt.v1",
        "manifest_path": "software/ai/manifests/translation_weighted_pose_keyloss_v0.external.json",
        "manifest_sha256": sha256(manifest_path),
        "checker_path": "scripts/ci/check_external_artifact.py",
        "checker_sha256": sha256(CHECKER),
        "expected_status": expected_status,
        "result": asdict(result),
        "artifact_reads": 1 if result.status == "verified" else 0,
        "artifact_writes": 0,
        "hardware_writes": 0,
        "physical_movements": 0,
        "qualification_installed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--expect", required=True, choices=sorted(STATUSES))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    receipt = verify(args.root, args.manifest, args.expect)
    payload = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode("utf-8")
    if args.output:
        if args.output.exists():
            raise FileExistsError("receipt output already exists")
        args.output.write_bytes(payload)
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()

"""Build a deterministic, non-publishing source-preview review packet.

The packet inventories the exact Git tree selected for review. It does not
create an archive, tag, release, attestation, or publication approval.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "tactevra.release-review-packet.v1"
FULL_SHA = re.compile(r"[0-9a-f]{40}")
CHECK_NAME = re.compile(r"[a-z][a-z0-9_-]*")


def git(*args: str, root: Path = ROOT) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=root, text=True, encoding="utf-8"
    ).strip()


def parse_checks(values: list[str]) -> dict[str, int]:
    checks: dict[str, int] = {}
    for value in values:
        name, separator, raw_status = value.partition("=")
        if not separator or not CHECK_NAME.fullmatch(name):
            raise ValueError(f"invalid check assignment: {value!r}")
        if name in checks:
            raise ValueError(f"duplicate check assignment: {name}")
        try:
            status = int(raw_status)
        except ValueError as exc:
            raise ValueError(f"check status must be an integer: {value!r}") from exc
        if status < 0 or status > 255:
            raise ValueError(f"check status must be between 0 and 255: {value!r}")
        checks[name] = status
    if not checks:
        raise ValueError("at least one --check name=status assignment is required")
    return checks


def parse_tree(raw: bytes) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for record in raw.split(b"\0"):
        if not record:
            continue
        metadata, separator, path_bytes = record.partition(b"\t")
        if not separator:
            raise ValueError("git tree record has no path separator")
        fields = metadata.decode("ascii").split()
        if len(fields) != 4:
            raise ValueError(f"unexpected git tree metadata: {metadata!r}")
        mode, object_type, object_id, raw_size = fields
        if object_type != "blob" or not raw_size.isdigit():
            raise ValueError(f"unsupported tree entry: {metadata!r}")
        path = path_bytes.decode("utf-8", errors="surrogateescape")
        entries.append(
            {
                "path": path,
                "mode": mode,
                "object_id": object_id,
                "bytes": int(raw_size),
            }
        )
    return entries


def git_tree(root: Path = ROOT) -> list[dict[str, object]]:
    raw = subprocess.check_output(
        ["git", "ls-tree", "-r", "-l", "-z", "--full-tree", "HEAD"], cwd=root
    )
    return parse_tree(raw)


def canonical_json(payload: object) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def build_packet(expected_sha: str, checks: dict[str, int], root: Path = ROOT) -> tuple[dict, dict]:
    expected_sha = expected_sha.lower()
    if not FULL_SHA.fullmatch(expected_sha):
        raise ValueError("expected SHA must be 40 lowercase hexadecimal characters")
    actual_sha = git("rev-parse", "HEAD", root=root).lower()
    if actual_sha != expected_sha:
        raise ValueError(f"checked out {actual_sha}, expected {expected_sha}")
    dirty = git("status", "--porcelain", "--untracked-files=no", root=root)
    if dirty:
        raise ValueError("tracked worktree changes prevent an exact-tree review packet")

    entries = git_tree(root)
    manifest = {
        "schema": "tactevra.source-tree-manifest.v1",
        "candidate_sha": actual_sha,
        "tree_sha": git("rev-parse", "HEAD^{tree}", root=root),
        "git_object_format": git("rev-parse", "--show-object-format", root=root),
        "tracked_file_count": len(entries),
        "logical_bytes": sum(int(entry["bytes"]) for entry in entries),
        "entries": entries,
    }
    manifest_bytes = canonical_json(manifest)
    check_results = {
        name: {"exit_code": status, "passed": status == 0}
        for name, status in sorted(checks.items())
    }
    packet = {
        "schema": SCHEMA,
        "candidate_sha": actual_sha,
        "tree_sha": manifest["tree_sha"],
        "commit_timestamp": git("show", "-s", "--format=%cI", "HEAD", root=root),
        "source_tree_manifest": {
            "path": "source-tree-manifest.json",
            "sha256": hashlib.sha256(manifest_bytes).hexdigest(),
            "tracked_file_count": manifest["tracked_file_count"],
            "logical_bytes": manifest["logical_bytes"],
        },
        "checks": check_results,
        "candidate_gate_passed": all(result["passed"] for result in check_results.values()),
        "publishes_release": False,
        "grants_release_authority": False,
        "grants_hardware_authority": False,
    }
    return packet, manifest


def summary_markdown(packet: dict) -> str:
    outcome = "PASS" if packet["candidate_gate_passed"] else "BLOCKED"
    rows = "\n".join(
        f"| `{name}` | `{result['exit_code']}` | {'Pass' if result['passed'] else 'Fail'} |"
        for name, result in packet["checks"].items()
    )
    source = packet["source_tree_manifest"]
    return (
        "# Tactevra source-preview review packet\n\n"
        f"**Candidate gate:** {outcome}\n\n"
        f"- Candidate commit: `{packet['candidate_sha']}`\n"
        f"- Git tree: `{packet['tree_sha']}`\n"
        f"- Tracked files: `{source['tracked_file_count']}`\n"
        f"- Logical bytes: `{source['logical_bytes']}`\n"
        f"- Manifest SHA-256: `{source['sha256']}`\n\n"
        "| Check | Exit code | Result |\n| --- | ---: | --- |\n"
        f"{rows}\n\n"
        "This packet is a deterministic review aid. It creates no tag or release, "
        "publishes no source archive, grants no publication authority, and grants "
        "no hardware authority.\n"
    )


def write_packet(output: Path, packet: dict, manifest: dict) -> None:
    output.mkdir(parents=True, exist_ok=False)
    (output / "source-tree-manifest.json").write_bytes(canonical_json(manifest))
    (output / "candidate-metadata.json").write_bytes(canonical_json(packet))
    (output / "REVIEW.md").write_text(summary_markdown(packet), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--check", action="append", default=[])
    args = parser.parse_args()
    try:
        checks = parse_checks(args.check)
        packet, manifest = build_packet(args.expected_sha, checks)
        write_packet(args.output, packet, manifest)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"release review packet could not be built: {exc}") from exc
    print(summary_markdown(packet))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

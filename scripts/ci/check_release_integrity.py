"""Check tracked source-preview contents against the reviewed release policy.

Policy mode runs in ordinary CI and rejects unexpected private, executable,
firmware, model-weight, key, and archive paths. Candidate mode additionally
fails while an explicitly recorded release blocker remains tracked.

This path check complements the content-oriented snapshot audit. Neither check
establishes redistribution rights or certifies that a snapshot is secret-free.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess


ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / ".github" / "release-integrity-policy.json"
ISSUE_PREFIX = "https://github.com/j-webtek/tactevra/issues/"
TOP_LEVEL_FIELDS = {
    "version",
    "archive_scope",
    "forbidden_tracked_prefixes",
    "forbidden_tracked_basenames",
    "forbidden_tracked_basename_prefixes",
    "forbidden_tracked_suffixes",
    "allowed_tracked_files",
    "candidate_blockers",
}


def normalize(value: str) -> str:
    normalized = PurePosixPath(value.replace("\\", "/")).as_posix()
    if (not normalized or normalized.startswith("/")
            or normalized == ".." or normalized.startswith("../")
            or "/../" in f"/{normalized}/"):
        raise ValueError(f"invalid repository-relative path: {value!r}")
    return normalized


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _string_list(policy: dict, field: str, *, paths: bool = False) -> list[str]:
    values = policy.get(field)
    if not isinstance(values, list) or any(not isinstance(value, str) or not value
                                           for value in values):
        raise ValueError(f"{field} must be a list of non-empty strings")
    result = [normalize(value) if paths else value.lower() for value in values]
    if len(result) != len(set(result)):
        raise ValueError(f"{field} contains duplicates")
    return result


def load_policy(path: Path = POLICY_PATH) -> dict:
    policy = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(policy, dict) or set(policy) != TOP_LEVEL_FIELDS:
        raise ValueError(f"policy must contain exactly {sorted(TOP_LEVEL_FIELDS)}")
    if policy["version"] != 1:
        raise ValueError("policy version must be 1")
    if policy["archive_scope"] != "github-generated-source-archives":
        raise ValueError("archive_scope must be github-generated-source-archives")

    for field in ("forbidden_tracked_prefixes",):
        _string_list(policy, field, paths=True)
    for field in ("forbidden_tracked_basenames",
                  "forbidden_tracked_basename_prefixes",
                  "forbidden_tracked_suffixes"):
        _string_list(policy, field)

    allowed = policy["allowed_tracked_files"]
    blockers = policy["candidate_blockers"]
    if not isinstance(allowed, list) or not isinstance(blockers, list):
        raise ValueError("allowed_tracked_files and candidate_blockers must be lists")

    seen: set[str] = set()
    for index, entry in enumerate(allowed):
        if not isinstance(entry, dict) or set(entry) != {"path", "sha256", "rationale"}:
            raise ValueError(f"allowed_tracked_files[{index}] has invalid fields")
        entry["path"] = normalize(entry["path"])
        digest = entry["sha256"].lower()
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError(f"invalid SHA-256 for allowed file {entry['path']}")
        entry["sha256"] = digest
        if not isinstance(entry["rationale"], str) or not entry["rationale"].strip():
            raise ValueError(f"empty rationale for allowed file {entry['path']}")
        if entry["path"] in seen:
            raise ValueError(f"duplicate governed path: {entry['path']}")
        seen.add(entry["path"])

    for index, entry in enumerate(blockers):
        if not isinstance(entry, dict) or set(entry) != {"path", "issue", "rationale"}:
            raise ValueError(f"candidate_blockers[{index}] has invalid fields")
        entry["path"] = normalize(entry["path"])
        if (not isinstance(entry["issue"], str)
                or not entry["issue"].startswith(ISSUE_PREFIX)):
            raise ValueError(f"invalid issue for candidate blocker {entry['path']}")
        if not isinstance(entry["rationale"], str) or not entry["rationale"].strip():
            raise ValueError(f"empty rationale for candidate blocker {entry['path']}")
        if entry["path"] in seen:
            raise ValueError(f"duplicate governed path: {entry['path']}")
        seen.add(entry["path"])
    return policy


def tracked_paths(root: Path = ROOT) -> list[str]:
    output = subprocess.check_output(
        ["git", "ls-files", "-z"], cwd=root,
    )
    return sorted(normalize(raw.decode("utf-8"))
                  for raw in output.split(b"\0") if raw)


def policy_errors(root: Path, policy: dict, tracked: list[str],
                  *, candidate: bool = False) -> list[str]:
    tracked_set = set(tracked)
    allowed = {entry["path"]: entry for entry in policy["allowed_tracked_files"]}
    errors: list[str] = []

    for path, entry in allowed.items():
        disk_path = root / Path(path)
        if path not in tracked_set or not disk_path.is_file():
            errors.append(f"allowed-file record is stale or untracked: {path}")
        elif sha256(disk_path) != entry["sha256"]:
            errors.append(f"allowed-file digest changed: {path}")

    prefixes = tuple(value.lower() for value in policy["forbidden_tracked_prefixes"])
    basenames = set(value.lower() for value in policy["forbidden_tracked_basenames"])
    basename_prefixes = tuple(
        value.lower() for value in policy["forbidden_tracked_basename_prefixes"])
    suffixes = tuple(value.lower() for value in policy["forbidden_tracked_suffixes"])
    for path in tracked:
        if path in allowed:
            continue
        lower = path.lower()
        basename = PurePosixPath(lower).name
        reasons = []
        if lower.startswith(prefixes):
            reasons.append("forbidden directory")
        if basename in basenames or basename.startswith(basename_prefixes):
            reasons.append("credential/private filename")
        if lower.endswith(suffixes):
            reasons.append("forbidden binary/model/key/archive suffix")
        if reasons:
            errors.append(f"{', '.join(reasons)}: {path}")

    if candidate:
        for entry in policy["candidate_blockers"]:
            if entry["path"] in tracked_set:
                errors.append(
                    f"candidate blocker remains tracked: {entry['path']} ({entry['issue']})")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("policy", "candidate"), default="policy")
    args = parser.parse_args()
    try:
        policy = load_policy()
        tracked = tracked_paths()
        errors = policy_errors(ROOT, policy, tracked, candidate=args.mode == "candidate")
    except (OSError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"release-integrity check could not run: {exc}") from exc
    if errors:
        details = "\n".join(f"- {error}" for error in errors)
        raise SystemExit(
            f"Release-integrity {args.mode} check failed:\n{details}\n"
            "Review .github/release-integrity-policy.json and docs/RELEASING.md."
        )
    blockers = sum(entry["path"] in set(tracked)
                   for entry in policy["candidate_blockers"])
    print(
        f"PASS: release-integrity {args.mode} check covers {len(tracked)} tracked paths; "
        f"{blockers} recorded candidate blocker(s) remain"
    )


if __name__ == "__main__":
    main()

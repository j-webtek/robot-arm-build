"""Reject unreviewed large or duplicate binary artifacts added by one change.

The existing repository history is a frozen baseline. This check evaluates only
files added or modified by the current change, so it can stop new clone-cost
growth without deleting historical hardware packages or rewriting Git history.
"""
from __future__ import annotations

from dataclasses import dataclass
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess


ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / ".github" / "repository-artifact-policy.json"
ISSUE_PREFIX = "https://github.com/j-webtek/tactevra/issues/"


@dataclass(frozen=True)
class TreeEntry:
    path: str
    object_id: str
    size: int


def normalize(value: str) -> str:
    normalized = PurePosixPath(value.replace("\\", "/")).as_posix()
    if (not normalized or normalized.startswith("/") or normalized == ".."
            or normalized.startswith("../") or "/../" in f"/{normalized}/"):
        raise ValueError(f"invalid repository-relative path: {value!r}")
    return normalized


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_policy(path: Path = POLICY_PATH) -> dict:
    policy = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "version", "max_changed_file_bytes", "governed_binary_suffixes", "exceptions",
    }
    if not isinstance(policy, dict) or set(policy) != required:
        raise ValueError(f"policy must contain exactly {sorted(required)}")
    if policy["version"] != 1:
        raise ValueError("policy version must be 1")
    limit = policy["max_changed_file_bytes"]
    if not isinstance(limit, int) or limit <= 0:
        raise ValueError("max_changed_file_bytes must be a positive integer")

    suffixes = policy["governed_binary_suffixes"]
    if (not isinstance(suffixes, list) or not suffixes
            or any(not isinstance(value, str) or not re.fullmatch(r"\.[a-z0-9]+", value)
                   for value in suffixes)):
        raise ValueError("governed_binary_suffixes must be lowercase file suffixes")
    if suffixes != sorted(set(suffixes)):
        raise ValueError("governed_binary_suffixes must be unique and sorted")

    exceptions = policy["exceptions"]
    if not isinstance(exceptions, list):
        raise ValueError("exceptions must be a list")
    seen: set[str] = set()
    for index, entry in enumerate(exceptions):
        fields = {"path", "sha256", "issue", "rationale"}
        if not isinstance(entry, dict) or set(entry) != fields:
            raise ValueError(f"exception {index} must contain exactly {sorted(fields)}")
        entry["path"] = normalize(entry["path"])
        if entry["path"] in seen:
            raise ValueError(f"duplicate exception path: {entry['path']}")
        seen.add(entry["path"])
        entry["sha256"] = entry["sha256"].lower()
        if not re.fullmatch(r"[0-9a-f]{64}", entry["sha256"]):
            raise ValueError(f"invalid exception digest: {entry['path']}")
        if (not isinstance(entry["issue"], str)
                or not entry["issue"].startswith(ISSUE_PREFIX)):
            raise ValueError(f"exception must link a Tactevra review issue: {entry['path']}")
        if not isinstance(entry["rationale"], str) or not entry["rationale"].strip():
            raise ValueError(f"empty exception rationale: {entry['path']}")
    return policy


def parse_tree(output: str) -> dict[str, TreeEntry]:
    entries: dict[str, TreeEntry] = {}
    pattern = re.compile(r"^\d+\s+blob\s+([0-9a-f]+)\s+(\d+)\t(.+)$")
    for line in output.splitlines():
        if not line:
            continue
        match = pattern.match(line)
        if not match:
            raise ValueError(f"unexpected git ls-tree record: {line!r}")
        object_id, raw_size, raw_path = match.groups()
        path = normalize(raw_path)
        entries[path] = TreeEntry(path=path, object_id=object_id, size=int(raw_size))
    return entries


def parse_changed_paths(output: str) -> list[str]:
    paths: list[str] = []
    for line in output.splitlines():
        if not line:
            continue
        status, raw_path = line.split("\t", 1)
        if status not in {"A", "M"}:
            continue
        paths.append(normalize(raw_path))
    return sorted(set(paths))


def exception_errors(root: Path, exceptions: dict[str, dict[str, str]]) -> list[str]:
    errors: list[str] = []
    for path, entry in exceptions.items():
        disk_path = root / Path(path)
        if not disk_path.is_file():
            errors.append(f"artifact exception path is missing: {path}")
        elif sha256(disk_path) != entry["sha256"]:
            errors.append(f"stale artifact exception (digest mismatch): {path}")
    return errors


def evaluate(root: Path, changed: list[str], tree: dict[str, TreeEntry], policy: dict) -> list[str]:
    exceptions = {entry["path"]: entry for entry in policy["exceptions"]}
    errors = exception_errors(root, exceptions)
    by_object: dict[str, list[str]] = {}
    for entry in tree.values():
        by_object.setdefault(entry.object_id, []).append(entry.path)

    suffixes = set(policy["governed_binary_suffixes"])
    limit = policy["max_changed_file_bytes"]
    for path in changed:
        entry = tree.get(path)
        if entry is None:
            continue
        exception = exceptions.get(path)
        if exception and sha256(root / Path(path)) == exception["sha256"]:
            continue
        if entry.size > limit:
            errors.append(
                f"changed file is {entry.size} bytes (limit {limit}): {path}")
        if PurePosixPath(path).suffix.lower() in suffixes:
            duplicates = sorted(other for other in by_object[entry.object_id] if other != path)
            if duplicates:
                errors.append(
                    f"changed binary duplicates tracked bytes: {path} -> {', '.join(duplicates)}")
    return errors


def git_tree(root: Path = ROOT) -> dict[str, TreeEntry]:
    result = subprocess.run(
        ["git", "ls-tree", "-r", "-l", "HEAD"], cwd=root, check=True,
        text=True, capture_output=True,
    )
    return parse_tree(result.stdout)


def git_changed_paths(base: str, root: Path = ROOT) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-status", "--no-renames", f"{base}..HEAD"],
        cwd=root, check=True, text=True, capture_output=True,
    )
    return parse_changed_paths(result.stdout)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default=os.environ.get("ARTIFACT_BASE", "HEAD^1"))
    args = parser.parse_args()
    try:
        policy = load_policy()
        tree = git_tree()
        changed = git_changed_paths(args.base)
        errors = evaluate(ROOT, changed, tree, policy)
    except (OSError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"repository-artifact check could not run: {exc}") from exc
    if errors:
        details = "\n".join(f"- {error}" for error in errors)
        raise SystemExit(
            "Repository artifact change exceeds ordinary review policy:\n"
            f"{details}\n"
            "See docs/ARTIFACT_GOVERNANCE.md for reduction and exception procedures."
        )
    print(
        f"PASS: {len(changed)} changed path(s) add no unreviewed oversized or "
        "duplicate governed artifacts"
    )


if __name__ == "__main__":
    main()

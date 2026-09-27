"""Measure and bound the logical size of GitHub-generated source archives.

GitHub source archives contain every tracked path. This check therefore measures
the committed tree rather than estimating a custom package that does not exist.
The current ceilings prevent silent growth; reduction targets are reported but
do not fail CI.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / ".github/source-archive-policy.json"
SCHEMA = "tactevra.source-archive-policy.v1"
POLICY_FIELDS = {
    "schema", "archive_mode", "archive_constraint", "ceilings",
    "reduction_targets", "baseline",
}
CEILING_FIELDS = {
    "max_tracked_files", "max_logical_bytes", "max_single_blob_bytes",
    "duplicate_min_blob_bytes", "max_duplicate_bytes",
}
TARGET_FIELDS = {"max_logical_bytes", "max_duplicate_bytes"}
BASELINE_FIELDS = {"commit", "tracked_files", "logical_bytes", "duplicate_bytes"}


@dataclass(frozen=True)
class TreeEntry:
    object_id: str
    size: int
    path: str


@dataclass(frozen=True)
class Footprint:
    tracked_files: int
    logical_bytes: int
    largest_blob_bytes: int
    duplicate_bytes: int


def _positive_ints(value: object, fields: set[str], label: str) -> dict[str, int]:
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(f"{label} must contain exactly {sorted(fields)}")
    if any(not isinstance(value[field], int) or value[field] <= 0 for field in fields):
        raise ValueError(f"{label} values must be positive integers")
    return value


def load_policy(path: Path = POLICY_PATH) -> dict:
    policy = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(policy, dict) or set(policy) != POLICY_FIELDS:
        raise ValueError(f"policy must contain exactly {sorted(POLICY_FIELDS)}")
    if policy["schema"] != SCHEMA:
        raise ValueError(f"schema must be {SCHEMA}")
    if policy["archive_mode"] != "github-generated-source-archives":
        raise ValueError("archive_mode must be github-generated-source-archives")
    if not isinstance(policy["archive_constraint"], str) or not policy["archive_constraint"].strip():
        raise ValueError("archive_constraint must be a non-empty string")
    ceilings = _positive_ints(policy["ceilings"], CEILING_FIELDS, "ceilings")
    targets = _positive_ints(policy["reduction_targets"], TARGET_FIELDS, "reduction_targets")
    baseline = policy["baseline"]
    if not isinstance(baseline, dict) or set(baseline) != BASELINE_FIELDS:
        raise ValueError(f"baseline must contain exactly {sorted(BASELINE_FIELDS)}")
    for field in BASELINE_FIELDS - {"commit"}:
        if not isinstance(baseline[field], int) or baseline[field] <= 0:
            raise ValueError("baseline measurements must be positive integers")
    commit = baseline.get("commit")
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("baseline.commit must be a full lowercase commit SHA")
    if targets["max_logical_bytes"] >= ceilings["max_logical_bytes"]:
        raise ValueError("logical-byte reduction target must be below its ceiling")
    if targets["max_duplicate_bytes"] >= ceilings["max_duplicate_bytes"]:
        raise ValueError("duplicate-byte reduction target must be below its ceiling")
    if baseline["logical_bytes"] > ceilings["max_logical_bytes"]:
        raise ValueError("baseline logical bytes exceed the declared ceiling")
    if baseline["duplicate_bytes"] > ceilings["max_duplicate_bytes"]:
        raise ValueError("baseline duplicate bytes exceed the declared ceiling")
    return policy


def parse_tree(output: str) -> list[TreeEntry]:
    entries: list[TreeEntry] = []
    pattern = re.compile(r"^\d+\s+blob\s+([0-9a-f]+)\s+(\d+)\t(.+)$")
    for line in output.splitlines():
        if not line:
            continue
        match = pattern.match(line)
        if not match:
            raise ValueError(f"unexpected git ls-tree record: {line!r}")
        object_id, raw_size, path = match.groups()
        entries.append(TreeEntry(object_id=object_id, size=int(raw_size), path=path))
    return entries


def git_tree(root: Path = ROOT) -> list[TreeEntry]:
    output = subprocess.check_output(
        ["git", "ls-tree", "-r", "-l", "HEAD"], cwd=root, text=True,
    )
    return parse_tree(output)


def summarize(entries: list[TreeEntry], duplicate_min_blob_bytes: int) -> Footprint:
    groups: dict[str, list[TreeEntry]] = defaultdict(list)
    for entry in entries:
        groups[entry.object_id].append(entry)
    duplicate_bytes = sum(
        group[0].size * (len(group) - 1)
        for group in groups.values()
        if len(group) > 1 and group[0].size >= duplicate_min_blob_bytes
    )
    return Footprint(
        tracked_files=len(entries),
        logical_bytes=sum(entry.size for entry in entries),
        largest_blob_bytes=max((entry.size for entry in entries), default=0),
        duplicate_bytes=duplicate_bytes,
    )


def evaluate(footprint: Footprint, policy: dict) -> list[str]:
    ceilings = policy["ceilings"]
    comparisons = {
        "tracked_files": "max_tracked_files",
        "logical_bytes": "max_logical_bytes",
        "largest_blob_bytes": "max_single_blob_bytes",
        "duplicate_bytes": "max_duplicate_bytes",
    }
    errors = []
    for observed_field, policy_field in comparisons.items():
        observed = getattr(footprint, observed_field)
        maximum = ceilings[policy_field]
        if observed > maximum:
            errors.append(f"{observed_field}: observed {observed}, ceiling {maximum}")
    return errors


def report(footprint: Footprint, policy: dict) -> dict:
    values = asdict(footprint)
    targets = policy["reduction_targets"]
    values["archive_mode"] = policy["archive_mode"]
    values["within_reduction_target"] = {
        "logical_bytes": footprint.logical_bytes <= targets["max_logical_bytes"],
        "duplicate_bytes": footprint.duplicate_bytes <= targets["max_duplicate_bytes"],
    }
    return values


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    try:
        policy = load_policy()
        footprint = summarize(git_tree(), policy["ceilings"]["duplicate_min_blob_bytes"])
        errors = evaluate(footprint, policy)
    except (OSError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"source-archive footprint check could not run: {exc}") from exc
    payload = report(footprint, policy)
    if args.as_json:
        print(json.dumps(payload, sort_keys=True))
    if errors:
        details = "\n".join(f"- {error}" for error in errors)
        raise SystemExit(
            "Source-archive footprint exceeds the reviewed containment ceiling:\n"
            f"{details}\nSee docs/SOURCE_DISTRIBUTION.md."
        )
    if not args.as_json:
        print(
            "PASS: source-archive footprint is contained at "
            f"{footprint.tracked_files} files / {footprint.logical_bytes} logical bytes; "
            f"{footprint.duplicate_bytes} duplicate bytes remain above the governed threshold"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

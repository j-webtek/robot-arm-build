#!/usr/bin/env python3
"""Classify a Git diff for bounded CI and repository routing."""

from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY = ROOT / ".github" / "automation-policy.json"


def _matches(path: str, patterns: Iterable[str]) -> bool:
    normalized = path.replace("\\", "/")
    return any(fnmatch.fnmatchcase(normalized, pattern) for pattern in patterns)


def load_policy(path: Path = DEFAULT_POLICY) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def classify_paths(paths: Iterable[str], policy: dict) -> dict[str, object]:
    normalized = (path.replace("\\", "/") for path in paths if path)
    changed = sorted({path[2:] if path.startswith("./") else path for path in normalized})
    lanes = sorted(
        label
        for label, patterns in policy["lanes"].items()
        if any(_matches(path, patterns) for path in changed)
    )
    contract = any(_matches(path, policy["contracts"]) for path in changed)
    if contract:
        # Shared contracts affect both producers and consumers even when the
        # file physically lives in only one workstream's directory.
        lanes = sorted(set(lanes) | {"area:ai", "area:arm"})
    labels = list(lanes)
    if any(_matches(path, policy["documentation"]) for path in changed):
        labels.append("documentation")
    if any(_matches(path, policy["release_readiness"]) for path in changed):
        labels.append("release-readiness")
    if contract or len([lane for lane in lanes if lane in {"area:ai", "area:arm"}]) > 1:
        labels.append("cross-workstream")
    docs_only = bool(changed) and all(
        _matches(path, policy["documentation"]) or path.startswith("assets/")
        for path in changed
    )
    return {
        "paths": changed,
        "labels": sorted(set(labels)),
        "lanes": lanes,
        "docs_only": docs_only,
        "contract": contract,
        "portable_full": any(_matches(path, policy["portable_full"]) for path in changed),
        "rc03_manual": any(_matches(path, policy["rc03_manual"]) for path in changed),
        "rc03_reportlab": any(_matches(path, policy["rc03_reportlab"]) for path in changed),
        "rc03_trimesh": any(_matches(path, policy["rc03_trimesh"]) for path in changed),
    }


def changed_paths(base: str, head: str) -> list[str]:
    output = subprocess.check_output(
        ["git", "diff", "--name-only", "--diff-filter=ACMRT", base, head],
        cwd=ROOT,
        text=True,
    )
    return [line for line in output.splitlines() if line]


def write_github_outputs(result: dict[str, object], destination: Path) -> None:
    keys = ("docs_only", "contract", "portable_full", "rc03_manual", "rc03_reportlab", "rc03_trimesh")
    with destination.open("a", encoding="utf-8") as handle:
        for key in keys:
            handle.write(f"{key}={str(bool(result[key])).lower()}\n")
        handle.write(f"labels={','.join(result['labels'])}\n")
        handle.write(f"changed_count={len(result['paths'])}\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base")
    parser.add_argument("--head")
    parser.add_argument("--paths", nargs="*")
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--github-output", type=Path)
    parser.add_argument("--force-full", action="store_true")
    args = parser.parse_args()
    paths = args.paths if args.paths is not None else changed_paths(args.base, args.head)
    result = classify_paths(paths, load_policy(args.policy))
    if args.force_full:
        for key in ("portable_full", "rc03_manual", "rc03_reportlab", "rc03_trimesh"):
            result[key] = True
    if args.github_output:
        write_github_outputs(result, args.github_output)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

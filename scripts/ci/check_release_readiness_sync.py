#!/usr/bin/env python3
"""Check that the release ledger and its GitHub issues tell the same story."""

from __future__ import annotations

import argparse
import json
import os
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / ".github" / "release-readiness.json"


def load_registry(path: Path = REGISTRY) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    ids = [item["id"] for item in data["blockers"]]
    if len(ids) != len(set(ids)):
        raise ValueError("release-readiness blocker IDs must be unique")
    for item in data["blockers"]:
        if item["status"] not in {"open", "cleared"}:
            raise ValueError(f"unsupported blocker status for {item['id']}: {item['status']}")
        if not re.fullmatch(r"https://github\.com/[^/]+/[^/]+/issues/\d+", item["issue"]):
            raise ValueError(f"invalid blocker issue URL for {item['id']}")
        if item["status"] == "cleared" and not item.get("resolution"):
            raise ValueError(f"cleared blocker {item['id']} has no resolution")
        if item["status"] == "open" and item.get("resolution") is not None:
            raise ValueError(f"open blocker {item['id']} must not claim a resolution")
    return data


def github_json(url: str, token: str):
    request = urllib.request.Request(url)
    request.add_header("Accept", "application/vnd.github+json")
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("X-GitHub-Api-Version", "2022-11-28")
    request.add_header("User-Agent", "tactevra-readiness-sync")
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def check_live(registry: dict, repository: str, token: str) -> list[str]:
    findings: list[str] = []
    for blocker in registry["blockers"]:
        issue_number = blocker["issue"].rsplit("/", 1)[-1]
        issue = github_json(f"https://api.github.com/repos/{repository}/issues/{issue_number}", token)
        expected = "open" if blocker["status"] == "open" else "closed"
        if issue["state"] != expected:
            findings.append(
                f"{blocker['id']}: registry is {blocker['status']} but issue #{issue_number} is {issue['state']}"
            )
    tracker = registry.get("tracker")
    if tracker:
        issue = github_json(f"https://api.github.com/repos/{repository}/issues/{tracker['issue']}", token)
        if issue["state"] != tracker["expected_state"]:
            findings.append(
                f"release tracker #{tracker['issue']} is {issue['state']}; expected {tracker['expected_state']}"
            )
        milestone = issue.get("milestone")
        if not milestone or milestone["title"] != tracker["milestone"]:
            findings.append(f"release tracker #{tracker['issue']} is not assigned to {tracker['milestone']!r}")
        elif milestone["state"] != tracker["milestone_state"]:
            findings.append(
                f"milestone {tracker['milestone']!r} is {milestone['state']}; expected {tracker['milestone_state']}"
            )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--online", action="store_true")
    parser.add_argument("--repository", default="j-webtek/tactevra")
    parser.add_argument("--summary", type=Path)
    args = parser.parse_args()
    try:
        registry = load_registry()
        findings = []
        if args.online:
            token = os.environ.get("GITHUB_TOKEN", "")
            if not token:
                raise ValueError("GITHUB_TOKEN is required for --online")
            findings = check_live(registry, args.repository, token)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        findings = [str(exc)]
    lines = ["### Release-readiness synchronization", ""]
    lines.append("No ledger/issue drift detected." if not findings else "Drift detected:")
    lines.extend(f"- {finding}" for finding in findings)
    output = "\n".join(lines) + "\n"
    print(output)
    if args.summary:
        with args.summary.open("a", encoding="utf-8") as handle:
            handle.write(output)
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())

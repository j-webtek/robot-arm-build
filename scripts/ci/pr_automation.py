#!/usr/bin/env python3
"""Route pull requests and enforce the shared AI/arm contract handoff."""

from __future__ import annotations

import argparse
import json
import os
import re
import urllib.request
from pathlib import Path

from change_classifier import classify_paths, load_policy


def api_json(url: str, token: str, *, method: str = "GET", payload=None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Accept", "application/vnd.github+json")
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("X-GitHub-Api-Version", "2022-11-28")
    request.add_header("User-Agent", "tactevra-pr-governance")
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response) if response.length != 0 else None


def pull_paths(api_url: str, token: str) -> list[str]:
    paths: list[str] = []
    page = 1
    while True:
        separator = "&" if "?" in api_url else "?"
        batch = api_json(f"{api_url}/files{separator}per_page=100&page={page}", token)
        paths.extend(item["filename"] for item in batch)
        if len(batch) < 100:
            return paths
        page += 1


def completeness_findings(body: str, result: dict[str, object]) -> list[str]:
    findings: list[str] = []
    normalized = body.lower()
    tiny_docs = bool(result["docs_only"]) and len(result["paths"]) <= 3
    if not tiny_docs:
        for heading in ("## what changes for the user?", "## ownership and handoff", "## evidence"):
            if heading not in normalized:
                findings.append(f"missing PR section: {heading}")
        placeholders = (
            "describe the outcome and link the relevant issue",
            "- lane: repository/docs / ai / arm / hardware / cross-workstream",
            "- commands run and results:",
        )
        if any(marker in normalized for marker in placeholders):
            findings.append("PR template still contains an unanswered required prompt")
    if result["contract"]:
        paths = result["paths"]
        if not any("test" in Path(path).name.lower() or "/tests/" in path for path in paths):
            findings.append("shared-contract change has no producer/consumer test or fixture change")
        if not any(path.startswith("docs/") or path.endswith("README.md") for path in paths):
            findings.append("shared-contract change has no documentation or migration-note file change")
        compatibility = re.search(r"compatibility:\s*(unchanged|additive|breaking)", body, re.I)
        if compatibility is None:
            findings.append("shared-contract change must declare compatibility as unchanged, additive, or breaking")
        if "migration" not in normalized and "rollback" not in normalized:
            findings.append("shared-contract change must describe migration or rollback")
    return findings


def update_labels(issue_url: str, token: str, result: dict[str, object], managed: set[str]) -> list[str]:
    current = api_json(f"{issue_url}/labels?per_page=100", token)
    existing = {item["name"] for item in current}
    desired = (existing - managed) | set(result["labels"])
    api_json(f"{issue_url}/labels", token, method="PUT", payload={"labels": sorted(desired)})
    return sorted(desired)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", type=Path, required=True)
    parser.add_argument("--apply-labels", action="store_true")
    parser.add_argument("--summary", type=Path)
    args = parser.parse_args()
    event = json.loads(args.event.read_text(encoding="utf-8"))
    pull = event["pull_request"]
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        raise SystemExit("GITHUB_TOKEN is required")
    paths = pull_paths(pull["url"], token)
    policy = load_policy()
    result = classify_paths(paths, policy)
    findings = completeness_findings(pull.get("body") or "", result)
    labels = result["labels"]
    if args.apply_labels:
        labels = update_labels(pull["issue_url"], token, result, set(policy["managed_labels"]))
    lines = [
        "### Pull-request automation",
        "",
        f"- Changed paths: `{len(paths)}`",
        f"- Routed labels: `{', '.join(labels) or 'none'}`",
        f"- Full portable CI: `{str(result['portable_full']).lower()}`",
        f"- Shared contract touched: `{str(result['contract']).lower()}`",
        f"- Completeness: `{'pass' if not findings else 'needs attention'}`",
    ]
    if findings:
        lines.extend(["", "Findings:", *[f"- {item}" for item in findings]])
    output = "\n".join(lines) + "\n"
    print(output)
    if args.summary:
        args.summary.write_text(output, encoding="utf-8")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())

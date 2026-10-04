#!/usr/bin/env python3
"""Keep the release ledger, dashboard, tracker, and milestone synchronized."""

from __future__ import annotations

import argparse
import json
import os
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / ".github" / "release-readiness.json"
DASHBOARD = ROOT / "docs" / "releases" / "READINESS.md"
BEGIN = "<!-- BEGIN GENERATED READINESS STATUS -->"
END = "<!-- END GENERATED READINESS STATUS -->"


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


def issue_number(blocker: dict) -> str:
    return blocker["issue"].rsplit("/", 1)[-1]


def render_dashboard_status(registry: dict) -> str:
    opened = [item for item in registry["blockers"] if item["status"] == "open"]
    suffix = "s" if len(opened) != 1 else ""
    lines = [BEGIN, f"**Registry status:** {len(opened)} open blocker{suffix}.", "", "| Blocker | Owner | State |", "| --- | --- | --- |"]
    for item in registry["blockers"]:
        number = issue_number(item)
        state = "Open" if item["status"] == "open" else "Cleared"
        lines.append(f"| [#{number}]({item['issue']}) — {item['id']} | {item['owner']} | **{state}** |")
    lines.extend([END, ""])
    return "\n".join(lines)


def render_tracker_body(registry: dict) -> str:
    opened = [item for item in registry["blockers"] if item["status"] == "open"]
    suffix = "s" if len(opened) != 1 else ""
    lines = [
        "## Objective", "",
        "Track the source-only experimental preview from the reviewed readiness registry. This issue records status; it does not select a candidate or authorize publication.", "",
        "## Current state", "", f"The registry has **{len(opened)} open blocker{suffix}**.",
    ]
    if opened:
        lines.extend([
            "", "**Phase:** Readiness-blocker resolution. Candidate selection remains held.",
            "", "**Candidate:** Not selected.",
        ])
    else:
        lines.extend([
            "", "**Phase:** Candidate qualification is ready to begin.",
            "", "**Candidate:** Not selected. No tag, release notes, or asset set is approved.",
            "", "**Decision owner:** @j-webtek, as repository maintainer.",
            "", "## Next accountable decision", "",
            "The maintainer must choose one bounded path:", "",
            "1. name one full commit SHA already on protected `main` and begin candidate qualification;",
            "2. defer the preview and leave this tracker open without selecting a candidate; or",
            "3. abandon this preview milestone, record the reason, and close the tracker as not planned.", "",
            "Candidate selection begins review; it does not authorize publication.",
        ])
    lines.extend([
        "", "## Registry-controlled blockers", "",
    ])
    for item in registry["blockers"]:
        mark = " " if item["status"] == "open" else "x"
        lines.append(f"- [{mark}] #{issue_number(item)} — {item['requirement']}")
    lines.extend([
        "", "## Candidate qualification", "",
        "- [ ] **Maintainer:** select one full commit SHA already on protected `main`.",
        "- [ ] **AI owner:** record the AI compatibility disposition against that exact SHA.",
        "- [ ] **Arm owner:** record the runtime/controller compatibility disposition against that exact SHA.",
        "- [ ] **Release administrator:** run the exact-SHA candidate audit and fresh-checkout verification, retaining the evidence.",
        "- [ ] **Maintainer:** review release notes, third-party notices, known limitations, and the source-only asset boundary.",
        "- [ ] **Maintainer:** explicitly approve the tag, SHA, title, notes, and assets.",
        "", "## Closure routes", "",
        "- **Completed:** publish the explicitly approved experimental preview, verify its public tag/SHA/assets, and record the result.",
        "- **Not planned:** explicitly abandon the milestone and record why no preview will be published.",
        "- **Deferred:** leave this tracker open; deferral is not completion.",
        "", "A passing check, merged PR, selected candidate, or cleared blocker does not itself authorize publication.", "",
        "Canonical status: [`release-readiness.json`](https://github.com/j-webtek/tactevra/blob/main/.github/release-readiness.json) · [readiness dashboard](https://github.com/j-webtek/tactevra/blob/main/docs/releases/READINESS.md)", "",
        "<!-- Generated by scripts/ci/check_release_readiness_sync.py; edit the registry, not this body. -->",
    ])
    return "\n".join(lines)


def render_milestone_description(registry: dict) -> str:
    opened = [f"#{issue_number(item)}" for item in registry["blockers"] if item["status"] == "open"]
    blockers = ", ".join(opened) if opened else "none"
    phase = "blocker resolution" if opened else "candidate qualification ready; candidate unselected"
    return ("Source-only experimental preview readiness. "
            f"Registry-controlled open blockers: {blockers}. "
            f"Phase: {phase}. "
            "Status: docs/releases/READINESS.md. Publication still requires exact-SHA review and explicit maintainer approval.")


def replace_generated_status(text: str, generated: str) -> str:
    pattern = re.compile(re.escape(BEGIN) + r".*?" + re.escape(END) + r"\n?", re.DOTALL)
    if pattern.search(text):
        return pattern.sub(generated, text, count=1)
    marker = "## Current gate summary"
    if marker not in text:
        raise ValueError(f"dashboard is missing insertion point: {marker}")
    return text.replace(marker, generated + "\n" + marker, 1)


def expected_dashboard(registry: dict, path: Path = DASHBOARD) -> str:
    return replace_generated_status(path.read_text(encoding="utf-8"), render_dashboard_status(registry))


def write_dashboard(registry: dict, path: Path = DASHBOARD) -> None:
    """Render before opening the destination so its existing body is preserved."""
    updated_dashboard = expected_dashboard(registry, path)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(updated_dashboard)


def github_json(url: str, token: str, method: str = "GET", payload: dict | None = None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Accept", "application/vnd.github+json")
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("X-GitHub-Api-Version", "2022-11-28")
    request.add_header("User-Agent", "tactevra-readiness-sync")
    if data is not None:
        request.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def check_dashboard(registry: dict, path: Path = DASHBOARD) -> list[str]:
    current = path.read_text(encoding="utf-8")
    return [] if current == expected_dashboard(registry, path) else ["readiness dashboard generated status is stale"]


def check_live(registry: dict, repository: str, token: str) -> list[str]:
    findings: list[str] = []
    for blocker in registry["blockers"]:
        number = issue_number(blocker)
        issue = github_json(f"https://api.github.com/repos/{repository}/issues/{number}", token)
        expected = "open" if blocker["status"] == "open" else "closed"
        if issue["state"] != expected:
            findings.append(f"{blocker['id']}: registry is {blocker['status']} but issue #{number} is {issue['state']}")
    tracker = registry.get("tracker")
    if tracker:
        issue = github_json(f"https://api.github.com/repos/{repository}/issues/{tracker['issue']}", token)
        if issue["state"] != tracker["expected_state"]:
            findings.append(f"release tracker #{tracker['issue']} is {issue['state']}; expected {tracker['expected_state']}")
        if issue.get("body", "").strip() != render_tracker_body(registry).strip():
            findings.append(f"release tracker #{tracker['issue']} body is stale")
        milestone = issue.get("milestone")
        if not milestone or milestone["title"] != tracker["milestone"]:
            findings.append(f"release tracker #{tracker['issue']} is not assigned to {tracker['milestone']!r}")
        else:
            if milestone["state"] != tracker["milestone_state"]:
                findings.append(f"milestone {tracker['milestone']!r} is {milestone['state']}; expected {tracker['milestone_state']}")
            if milestone.get("description", "").strip() != render_milestone_description(registry).strip():
                findings.append(f"milestone {tracker['milestone']!r} description is stale")
    return findings


def apply_github(registry: dict, repository: str, token: str) -> None:
    tracker = registry["tracker"]
    issue_url = f"https://api.github.com/repos/{repository}/issues/{tracker['issue']}"
    issue = github_json(issue_url, token)
    github_json(issue_url, token, "PATCH", {"body": render_tracker_body(registry)})
    milestone = issue.get("milestone")
    if not milestone:
        raise ValueError(f"release tracker #{tracker['issue']} has no milestone")
    github_json(f"https://api.github.com/repos/{repository}/milestones/{milestone['number']}", token, "PATCH", {"description": render_milestone_description(registry)})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--online", action="store_true")
    parser.add_argument("--apply-github", action="store_true")
    parser.add_argument("--write-dashboard", action="store_true")
    parser.add_argument("--repository", default="j-webtek/tactevra")
    parser.add_argument("--summary", type=Path)
    args = parser.parse_args()
    try:
        registry = load_registry()
        if args.write_dashboard:
            write_dashboard(registry)
        findings = check_dashboard(registry)
        if args.online or args.apply_github:
            token = os.environ.get("GITHUB_TOKEN", "")
            if not token:
                raise ValueError("GITHUB_TOKEN is required for online operations")
            if args.apply_github:
                apply_github(registry, args.repository, token)
            findings.extend(check_live(registry, args.repository, token))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        findings = [str(exc)]
    lines = ["### Release-readiness synchronization", ""]
    lines.append("No readiness drift detected." if not findings else "Drift detected:")
    lines.extend(f"- {finding}" for finding in findings)
    output = "\n".join(lines) + "\n"
    print(output)
    if args.summary:
        with args.summary.open("a", encoding="utf-8") as handle:
            handle.write(output)
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())

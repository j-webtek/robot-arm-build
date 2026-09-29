#!/usr/bin/env python3
"""Build a compact, non-authorizing repository-operations report."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def collect(root: Path = ROOT) -> dict:
    readiness = json.loads((root / ".github/release-readiness.json").read_text(encoding="utf-8"))
    automation = json.loads((root / ".github/automation-policy.json").read_text(encoding="utf-8"))
    dependabot = root / ".github/dependabot.yml"
    tracked = subprocess.check_output(["git", "ls-files"], cwd=root, text=True).splitlines()
    workflows = sorted(path.name for path in (root / ".github/workflows").glob("*.yml"))
    return {
        "as_of": date.today().isoformat(),
        "open_release_blockers": [item["issue"] for item in readiness["blockers"] if item["status"] == "open"],
        "cleared_release_blockers": [item["issue"] for item in readiness["blockers"] if item["status"] == "cleared"],
        "tracked_file_count": len(tracked),
        "workflow_count": len(workflows),
        "workflows": workflows,
        "shared_contract_pattern_count": len(automation["contracts"]),
        "dependabot_configured": dependabot.is_file(),
        "authority": "Operational summary only; it does not approve a release, model, hardware action, or rights disposition.",
    }


def render(data: dict) -> str:
    open_links = ", ".join(data["open_release_blockers"]) or "None"
    lines = [
        "# Weekly repository operations report", "",
        f"**As of:** {data['as_of']}", "",
        f"> {data['authority']}", "",
        "| Signal | Value |", "| --- | --- |",
        f"| Open release blockers | {len(data['open_release_blockers'])} |",
        f"| Cleared blockers retained for audit | {len(data['cleared_release_blockers'])} |",
        f"| Tracked files | {data['tracked_file_count']} |",
        f"| Workflows | {data['workflow_count']} |",
        f"| Shared-contract path patterns | {data['shared_contract_pattern_count']} |",
        f"| Dependabot configuration present | {'Yes' if data['dependabot_configured'] else 'No'} |",
        "", "## Current attention", "", f"Open blocker links: {open_links}", "",
        "## Workflow inventory", "",
    ]
    lines.extend(f"- `{name}`" for name in data["workflows"])
    lines.extend(["", "The scheduled workflow runs policy and live-state drift checks before retaining this report. A failed preceding check is the authoritative signal; this inventory is not a substitute for its logs.", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--summary", type=Path)
    args = parser.parse_args()
    data = collect()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    markdown = render(data)
    (args.output_dir / "repository-operations.md").write_text(markdown, encoding="utf-8")
    (args.output_dir / "repository-operations.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(markdown, end="")
    if args.summary:
        with args.summary.open("a", encoding="utf-8") as handle:
            handle.write(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

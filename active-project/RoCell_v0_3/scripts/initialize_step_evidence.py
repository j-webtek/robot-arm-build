#!/usr/bin/env python3
"""Create one non-overwriting active-build evidence folder from a fresh template."""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from build_step_packages import (
    EVIDENCE_TEMPLATE_DIRECTORY,
    LAYOUT_VERSION,
    MEASUREMENT_RECORD_FILE,
    SIGNOFF_RECORD_FILE,
    STEP_EVIDENCE_DIRECTORY,
    STEP_MANIFEST_FILE,
    valid_build_id,
)


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "BUILD_BY_STEP"
SENTINEL = PACKAGE / ".generated_by_build_step_packages"
ACTIVE_PATH = PACKAGE / "ACTIVE_BUILD.json"
INDEX_PATH = PACKAGE / "INDEX.json"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Initialize one step's evidence folder for the selected active build without overwriting evidence."
    )
    parser.add_argument("--step", required=True, choices=[f"{value:02d}" for value in range(16)])
    args = parser.parse_args()

    if not PACKAGE.is_dir() or not SENTINEL.is_file() or not ACTIVE_PATH.is_file():
        parser.error("BUILD_BY_STEP is missing or unrecognized; regenerate it first")
    try:
        active = json.loads(ACTIVE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        parser.error(f"ACTIVE_BUILD.json is unreadable: {exc}")
    if not isinstance(active, dict):
        parser.error("ACTIVE_BUILD.json root must be an object")
    build_id = active.get("active_build_id")
    if not valid_build_id(build_id):
        parser.error("ACTIVE_BUILD.json has no valid build ID; run scripts/set_active_build.py first")

    try:
        index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        parser.error(f"INDEX.json is unreadable: {exc}")
    if not isinstance(index, dict) or index.get("layout_version") != LAYOUT_VERSION:
        parser.error(f"INDEX.json is not layout version {LAYOUT_VERSION}; regenerate the package")
    rows = index.get("steps")
    if not isinstance(rows, list):
        parser.error("INDEX.json step list is missing")
    matches = [row for row in rows if isinstance(row, dict) and row.get("id") == args.step]
    if len(matches) != 1 or not isinstance(matches[0].get("folder"), str):
        parser.error(f"INDEX.json must identify exactly one Step {args.step} folder")
    step_row = matches[0]
    if step_row.get("state") != "READY_TO_START":
        parser.error(
            f"Step {args.step} is {step_row.get('state', 'MISSING_STATE')}, not READY_TO_START; "
            "regenerate, resolve the current gate/signoff state, and initialize only after the refreshed INDEX.json is ready"
        )
    step_dir = PACKAGE / step_row["folder"]
    try:
        step_dir.resolve().relative_to(PACKAGE.resolve())
    except ValueError:
        parser.error("INDEX.json step folder escapes BUILD_BY_STEP")
    if step_dir.resolve().parent != PACKAGE.resolve() or not step_dir.is_dir():
        parser.error(f"Step {args.step} folder is missing or is not a direct BUILD_BY_STEP child")
    manifest_path = step_dir / STEP_MANIFEST_FILE
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        parser.error(f"Step {args.step} manifest is unreadable: {exc}")
    if not isinstance(manifest, dict) or manifest.get("step_id") != args.step:
        parser.error(f"Step {args.step} manifest identity does not match INDEX.json")

    evidence_root = step_dir / STEP_EVIDENCE_DIRECTORY
    template = evidence_root / EVIDENCE_TEMPLATE_DIRECTORY
    destination = evidence_root / build_id
    if destination.resolve().parent != evidence_root.resolve():
        parser.error("active build ID does not resolve to a direct evidence-folder child")
    if not template.is_dir():
        parser.error(f"Step {args.step} has no current evidence template; regenerate the package")
    if destination.exists():
        parser.error(f"refusing to overwrite existing evidence: {destination}")

    for name in (MEASUREMENT_RECORD_FILE, SIGNOFF_RECORD_FILE):
        path = template / name
        if not path.is_file():
            parser.error(f"template is incomplete: missing {path}")
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("build_id") != build_id:
            parser.error(
                "template build_id does not match ACTIVE_BUILD.json; run scripts/build_step_packages.py first"
            )

    shutil.copytree(template, destination)
    print(json.dumps({"step_id": args.step, "build_id": build_id, "evidence_directory": str(destination)}, indent=2))


if __name__ == "__main__":
    main()

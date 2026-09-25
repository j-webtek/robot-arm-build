#!/usr/bin/env python3
"""Select the one BUILD_BY_STEP evidence ID allowed to affect step state."""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "BUILD_BY_STEP"
ACTIVE_PATH = PACKAGE / "ACTIVE_BUILD.json"
SENTINEL = PACKAGE / ".generated_by_build_step_packages"
BUILD_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}\Z")
WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{value}" for value in range(1, 10)),
    *(f"LPT{value}" for value in range(1, 10)),
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Set or clear the active physical-build ID used by BUILD_BY_STEP state computation."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--build-id", help="Unique build ID, for example 2026-08-31_CELL-A")
    group.add_argument("--clear", action="store_true", help="Clear the active build selection")
    args = parser.parse_args()

    if not PACKAGE.is_dir() or not SENTINEL.is_file():
        parser.error("BUILD_BY_STEP is missing or unrecognized; run scripts/build_step_packages.py first")

    build_id = None if args.clear else args.build_id
    if build_id is not None and (
        not BUILD_ID_PATTERN.fullmatch(build_id)
        or build_id.endswith(".")
        or build_id.split(".", 1)[0].upper() in WINDOWS_RESERVED_NAMES
    ):
        parser.error(
            "build ID must start with a letter/digit, use only letters, digits, dot, underscore, "
            "or hyphen, be 1-80 characters, and not be a reserved Windows name"
        )
    if build_id == "BUILD_ID_TEMPLATE":
        parser.error("BUILD_ID_TEMPLATE is reserved and cannot be selected")

    value = {"schema_version": 1, "active_build_id": build_id}
    temporary = ACTIVE_PATH.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, ACTIVE_PATH)
    print(json.dumps(value, indent=2))
    print("Run: python scripts/build_step_packages.py")


if __name__ == "__main__":
    main()

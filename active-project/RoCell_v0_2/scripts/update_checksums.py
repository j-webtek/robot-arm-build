#!/usr/bin/env python3
"""Regenerate SHA256SUMS.txt for distributable package files."""
from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "SHA256SUMS.txt"
EXCLUDED = {
    Path("SHA256SUMS.txt"),
    Path("stl/BOARD_REFERENCE_DO_NOT_PRINT.stl"),
}


def main() -> None:
    rows = []
    for path in sorted(ROOT.rglob("*"), key=lambda item: item.as_posix().lower()):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT)
        if relative in EXCLUDED or relative.parts[0] == "tmp":
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        rows.append(f"{digest}  ./{relative.as_posix()}")
    OUTPUT.write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(f"wrote {len(rows)} checksums to {OUTPUT}")


if __name__ == "__main__":
    main()

"""Build the retained, zero-I/O model/arm operational-readiness report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def build(*, repository_root: Path, output: Path) -> dict:
    root = Path(repository_root).resolve()
    sys.path.insert(0, str(root / "software/src"))
    try:
        from rocell.application.model_arm_operational_readiness_v1 import (
            build_model_arm_operational_readiness_v1,
        )
        report = build_model_arm_operational_readiness_v1(root)
    finally:
        sys.path.pop(0)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(report, indent=2, ensure_ascii=True) + "\n")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = build(repository_root=args.repository_root, output=args.output)
    print(json.dumps({
        "status": report["status"],
        "readiness_sha256": report["readiness_sha256"],
        "blocked_stage_ids": report["blocked_stage_ids"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

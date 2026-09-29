"""Run the read-only camera-arrival evidence inventory."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from rocell.application.camera_arrival_evidence_preflight_v1 import (
    CameraArrivalEvidencePreflightV1Error,
    inspect_camera_arrival_evidence_v1,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = inspect_camera_arrival_evidence_v1(args.workspace, args.evidence_root)
    except CameraArrivalEvidencePreflightV1Error as exc:
        parser.error(str(exc))
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ready_for_offline_qualification_review"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

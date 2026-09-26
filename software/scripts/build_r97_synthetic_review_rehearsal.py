"""Write deterministic synthetic r97 review evidence without hardware access."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from rocell.application.r97_independent_review_decision_v1 import (
    build_synthetic_r97_review_rehearsal_v1,
)


def build(
    output_dir: Path,
    *,
    rehearsal_id: str,
    review_started_utc: str,
    review_completed_utc: str,
) -> dict:
    decision, report = build_synthetic_r97_review_rehearsal_v1(
        rehearsal_id=rehearsal_id,
        review_started_utc=review_started_utc,
        review_completed_utc=review_completed_utc,
    )
    output_dir = Path(output_dir).resolve()
    decision_path = output_dir / "r97-synthetic-review-decision.json"
    report_path = output_dir / "r97-synthetic-review-report.json"
    if output_dir.exists():
        raise FileExistsError(
            "synthetic review output already exists; refusing to overwrite")
    output_dir.mkdir(parents=True, exist_ok=False)
    with decision_path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(decision.to_dict(), indent=2, sort_keys=True) + "\n")
    with report_path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n")
    return {
        "status": report.status,
        "decision_sha256": decision.decision_sha256,
        "decision_path": str(decision_path),
        "report_path": str(report_path),
        "synthetic_rehearsal_ready": True,
        "ready_for_epoch_intake": False,
        "installation_authorized": False,
        "controller_start_authorized": False,
        "execution_authorized": False,
        "hardware_access": False,
        "physical_authority": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--rehearsal-id", required=True)
    parser.add_argument("--review-started-utc", required=True)
    parser.add_argument("--review-completed-utc", required=True)
    args = parser.parse_args()
    print(json.dumps(build(
        args.output_dir,
        rehearsal_id=args.rehearsal_id,
        review_started_utc=args.review_started_utc,
        review_completed_utc=args.review_completed_utc,
    ), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

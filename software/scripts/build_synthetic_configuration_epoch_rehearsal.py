"""Build a full synthetic r97 review-to-epoch rehearsal without hardware I/O."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from rocell.application.controller_configuration_epoch_intake_v1 import (
    build_synthetic_controller_configuration_epoch_rehearsal_v1,
    parse_controller_configuration_epoch_intake_v1,
)
from rocell.application.r97_independent_review_decision_v1 import (
    parse_r97_independent_review_decision_v1,
)


def build(
    review_decision_path: Path,
    output_dir: Path,
    *,
    rehearsal_id: str,
    measured_monotonic_ns: int,
    valid_until_monotonic_ns: int,
    evaluated_monotonic_ns: int,
) -> dict:
    decision_document = json.loads(
        Path(review_decision_path).resolve().read_text(encoding="utf-8"))
    decision = parse_r97_independent_review_decision_v1(decision_document)
    intake, report = build_synthetic_controller_configuration_epoch_rehearsal_v1(
        rehearsal_id=rehearsal_id,
        firmware_review_decision=decision,
        measured_monotonic_ns=measured_monotonic_ns,
        valid_until_monotonic_ns=valid_until_monotonic_ns,
        evaluated_monotonic_ns=evaluated_monotonic_ns,
    )
    output_dir = Path(output_dir).resolve()
    if output_dir.exists():
        raise FileExistsError(
            "synthetic epoch output already exists; refusing to overwrite")
    output_dir.mkdir(parents=True, exist_ok=False)
    intake_path = output_dir / "synthetic-configuration-epoch-intake.json"
    report_path = output_dir / "synthetic-configuration-epoch-report.json"
    with intake_path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(intake.to_dict(), indent=2, sort_keys=True) + "\n")
    with report_path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n")
    parsed = parse_controller_configuration_epoch_intake_v1(
        json.loads(intake_path.read_text(encoding="utf-8")))
    if parsed.configuration_epoch_sha256 != intake.configuration_epoch_sha256:
        raise ValueError("written synthetic epoch failed strict round-trip")
    return {
        "status": "SYNTHETIC_EPOCH_REHEARSAL_ACCEPTED",
        "review_decision_sha256": decision.decision_sha256,
        "configuration_epoch_sha256": intake.configuration_epoch_sha256,
        "intake_report_sha256": report.report_sha256,
        "intake_path": str(intake_path),
        "report_path": str(report_path),
        "production_assessment_status": report.status,
        "production_blockers": list(report.blockers),
        "epoch_bound_build_proposal_ready": False,
        "installation_authorized": False,
        "controller_start_authorized": False,
        "execution_authorized": False,
        "hardware_access": False,
        "physical_authority": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("review_decision_path", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--rehearsal-id", required=True)
    parser.add_argument("--measured-monotonic-ns", type=int, required=True)
    parser.add_argument("--valid-until-monotonic-ns", type=int, required=True)
    parser.add_argument("--evaluated-monotonic-ns", type=int, required=True)
    args = parser.parse_args()
    print(json.dumps(build(
        args.review_decision_path,
        args.output_dir,
        rehearsal_id=args.rehearsal_id,
        measured_monotonic_ns=args.measured_monotonic_ns,
        valid_until_monotonic_ns=args.valid_until_monotonic_ns,
        evaluated_monotonic_ns=args.evaluated_monotonic_ns,
    ), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

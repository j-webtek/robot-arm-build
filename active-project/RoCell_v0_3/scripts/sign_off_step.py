#!/usr/bin/env python3
"""Place a step on HOLD or sign it PASS without hand-editing JSON."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from typing import Any

from step_evidence_common import (
    EvidenceError,
    atomic_write_json,
    has_recorded_value,
    load_context,
    load_record_pair,
    require_nonblank_text,
    resolve_existing_evidence_paths,
)


def _validated_pass_ids(measurement: dict[str, Any], signoff: dict[str, Any], build_dir) -> list[str]:
    required = signoff.get("required_test_ids")
    if (
        not isinstance(required, list)
        or not required
        or not all(isinstance(value, str) and value for value in required)
        or len(required) != len(set(required))
    ):
        raise EvidenceError("signoff required_test_ids must be a nonempty unique string list")
    rows = measurement.get("measurements")
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise EvidenceError("measurement_record.json measurements must be a list of objects")
    by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        test_id = row.get("test_id")
        if not isinstance(test_id, str) or not test_id or test_id in by_id:
            raise EvidenceError("measurement rows have a missing or duplicate test_id")
        by_id[test_id] = row
    if set(by_id) != set(required):
        raise EvidenceError("measurement rows do not exactly match the required test IDs")

    for test_id in required:
        row = by_id[test_id]
        if row.get("result") != "PASS":
            raise EvidenceError(f"{test_id} is not recorded PASS")
        if not has_recorded_value(row.get("value_or_observation")):
            raise EvidenceError(f"{test_id} has no measured value or objective observation")
        require_nonblank_text(row.get("unit"), f"{test_id} unit")
        require_nonblank_text(row.get("instrument_id"), f"{test_id} instrument")
        evidence = row.get("evidence_files")
        if not isinstance(evidence, list):
            raise EvidenceError(f"{test_id} evidence_files must be a list")
        resolve_existing_evidence_paths(build_dir, evidence)
    return list(required)


def sign_off(args: argparse.Namespace) -> dict[str, Any]:
    context = load_context(args.step)
    measurement, signoff = load_record_pair(context)
    operator = require_nonblank_text(args.operator, "operator")
    witness = require_nonblank_text(args.witness, "witness") if args.witness is not None else None
    holds = [require_nonblank_text(value, "hold reason") for value in (args.hold or [])]
    now = datetime.now(timezone.utc).isoformat()

    if args.status == "PASS":
        if holds:
            raise EvidenceError("PASS cannot include --hold; use --status HOLD")
        accepted = _validated_pass_ids(measurement, signoff, context.build_dir)
        signoff.update(
            {
                "status": "PASS",
                "accepted_test_ids": accepted,
                "open_holds": [],
                "operator": operator,
                "witness": witness,
                "signed_at": now,
            }
        )
    else:
        if not holds:
            raise EvidenceError("HOLD requires at least one --hold reason")
        if not measurement.get("operator"):
            measurement["operator"] = operator
        if not measurement.get("started_at"):
            measurement["started_at"] = now
        rows = measurement.get("measurements")
        accepted = [
            row.get("test_id")
            for row in rows
            if isinstance(row, dict) and row.get("result") == "PASS" and isinstance(row.get("test_id"), str)
        ] if isinstance(rows, list) else []
        signoff.update(
            {
                "status": "HOLD",
                "accepted_test_ids": accepted,
                "open_holds": list(dict.fromkeys(holds)),
                "operator": operator,
                "witness": witness,
                "signed_at": now,
            }
        )

    if args.status == "HOLD":
        # Establish the started-work identity before HOLD. A mid-write failure
        # remains fail-closed and the command can be safely rerun.
        atomic_write_json(context.measurement_path, measurement)
    atomic_write_json(context.signoff_path, signoff)
    return {
        "step_id": context.step_id,
        "build_id": context.build_id,
        "status": args.status,
        "accepted_test_ids": signoff["accepted_test_ids"],
        "open_holds": signoff["open_holds"],
        "signoff_record": str(context.signoff_path),
        "next_action": "Run python scripts/build_step_packages.py, then python scripts/build_step_packages.py --check",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Safely place one step on HOLD or sign it PASS for the selected active build."
    )
    parser.add_argument("--step", required=True, choices=[f"{value:02d}" for value in range(16)])
    parser.add_argument("--status", required=True, choices=("PASS", "HOLD"))
    parser.add_argument("--operator", required=True)
    parser.add_argument("--witness")
    parser.add_argument("--hold", action="append", help="HOLD reason; repeat for multiple holds")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        result = sign_off(args)
    except EvidenceError as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

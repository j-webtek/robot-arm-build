#!/usr/bin/env python3
"""Record or retest one step acceptance row without hand-editing JSON."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from typing import Any

from step_evidence_common import (
    EvidenceError,
    atomic_write_json,
    load_context,
    load_record_pair,
    require_nonblank_text,
    resolve_existing_evidence_paths,
)


def record_result(args: argparse.Namespace) -> dict[str, Any]:
    context = load_context(args.step)
    measurement, signoff = load_record_pair(context)
    if signoff.get("status") == "PASS":
        raise EvidenceError(
            "this step is already signed PASS; place it on HOLD with sign_off_step.py before recording a retest"
        )

    operator = require_nonblank_text(args.operator, "operator")
    value = require_nonblank_text(args.value, "value")
    unit = require_nonblank_text(args.unit, "unit")
    instrument = require_nonblank_text(args.instrument, "instrument")
    test_id = require_nonblank_text(args.test, "test ID")
    evidence_files = resolve_existing_evidence_paths(context.build_dir, args.evidence)

    rows = measurement.get("measurements")
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise EvidenceError("measurement_record.json measurements must be a list of objects")
    matches = [row for row in rows if row.get("test_id") == test_id]
    if len(matches) != 1:
        raise EvidenceError(f"measurement_record.json must contain exactly one {test_id!r} row")
    row = matches[0]
    required_ids = signoff.get("required_test_ids")
    if not isinstance(required_ids, list) or test_id not in required_ids:
        raise EvidenceError(f"{test_id!r} is not required by this step's controlled signoff")

    now = datetime.now(timezone.utc).isoformat()
    if row.get("result") != "NOT_TESTED" or row.get("value_or_observation") is not None:
        history = measurement.setdefault("corrections_and_retests", [])
        if not isinstance(history, list):
            raise EvidenceError("corrections_and_retests must be a list")
        history.append(
            {
                "test_id": test_id,
                "replaced_at": now,
                "replaced_by": operator,
                "reason": args.notes or "Retest recorded through record_step_result.py",
                "previous_record": dict(row),
            }
        )

    row.update(
        {
            "value_or_observation": value,
            "unit": unit,
            "instrument_id": instrument,
            "evidence_files": evidence_files,
            "result": args.result,
            "notes": args.notes,
        }
    )
    measurement["operator"] = operator
    if not measurement.get("started_at"):
        measurement["started_at"] = now
    instrument_ids = measurement.setdefault("instrument_ids", [])
    if not isinstance(instrument_ids, list):
        raise EvidenceError("instrument_ids must be a list")
    if instrument not in instrument_ids:
        instrument_ids.append(instrument)
    top_evidence = measurement.setdefault("evidence_files", [])
    if not isinstance(top_evidence, list):
        raise EvidenceError("top-level evidence_files must be a list")
    for path in evidence_files:
        if path not in top_evidence:
            top_evidence.append(path)

    if signoff.get("status") == "NOT_STARTED":
        signoff["status"] = "IN_PROGRESS"
        signoff["operator"] = operator
        signoff["signed_at"] = None
    if signoff.get("status") == "IN_PROGRESS":
        signoff["accepted_test_ids"] = [
            item.get("test_id")
            for item in rows
            if item.get("result") == "PASS" and isinstance(item.get("test_id"), str)
        ]
    # Write the measurement first. If the second replace is interrupted, the
    # existing validator fails closed; rerunning this command repairs signoff.
    atomic_write_json(context.measurement_path, measurement)
    atomic_write_json(context.signoff_path, signoff)
    return {
        "step_id": context.step_id,
        "build_id": context.build_id,
        "test_id": test_id,
        "result": args.result,
        "evidence_files": evidence_files,
        "measurement_record": str(context.measurement_path),
        "step_status": signoff.get("status"),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Safely record one acceptance result in the selected build and step."
    )
    parser.add_argument("--step", required=True, choices=[f"{value:02d}" for value in range(16)])
    parser.add_argument("--test", required=True, help="Controlled test ID, for example 03-A")
    parser.add_argument("--value", required=True, help="Measured value or objective observation")
    parser.add_argument("--unit", required=True, help="Measurement unit, or N/A for an observation")
    parser.add_argument("--instrument", required=True, help="Instrument ID or visual-inspection method")
    parser.add_argument(
        "--evidence",
        required=True,
        action="append",
        help="Existing file relative to this step's active build-ID folder; repeat as needed",
    )
    parser.add_argument("--result", required=True, choices=("PASS", "FAIL"))
    parser.add_argument("--operator", required=True)
    parser.add_argument("--notes")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        result = record_result(args)
    except EvidenceError as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

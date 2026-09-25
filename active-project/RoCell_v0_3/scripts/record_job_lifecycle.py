#!/usr/bin/env python3
"""Advance one print job by exactly one evidence-backed manual lifecycle state."""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import generate_build_tracker as tracker


ROOT = Path(__file__).resolve().parents[1]
RECORD_PATH = ROOT / "config" / "job_build_record.json"
MANUAL_STATES = tracker.MANUAL_STATES


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Advance one selected job by one manual lifecycle state; READY_TO_SLICE remains validator-derived."
    )
    parser.add_argument("--job", required=True, help="Controlled job ID, for example 00A or 03A")
    parser.add_argument("--state", required=True, choices=MANUAL_STATES)
    parser.add_argument("--operator", required=True)
    parser.add_argument("--evidence", required=True, help="Active build-ID evidence path and concise result")
    parser.add_argument("--completed-at", help="ISO-8601 timestamp; defaults to current UTC")
    args = parser.parse_args()

    report = tracker.build_tracker()
    rows = {row["job_id"]: row for row in report["jobs"]}
    if args.job not in rows:
        parser.error(f"unknown job ID: {args.job}")
    row = rows[args.job]
    if not row["selected"]:
        parser.error(f"{args.job} is NOT_SELECTED")

    recorded = row["recorded_state"]
    if recorded in {"UNRELEASED", "READY_TO_SLICE"}:
        expected = "SLICE_REVIEWED"
        if row["effective_state"] != "READY_TO_SLICE":
            missing = ", ".join(row["missing_prerequisites"]) or "unknown prerequisite"
            parser.error(f"{args.job} is not READY_TO_SLICE; resolve: {missing}")
    else:
        try:
            expected = MANUAL_STATES[MANUAL_STATES.index(recorded) + 1]
        except (ValueError, IndexError):
            parser.error(f"{args.job} cannot advance from {recorded}")
    if args.state != expected:
        parser.error(f"next allowed state for {args.job} is {expected}, not {args.state}")

    data = json.loads(RECORD_PATH.read_text(encoding="utf-8"))
    job_record = next(job for job in data["jobs"] if job["job_id"] == args.job)
    gates = json.loads((ROOT / "config" / "measurement_record.json").read_text(encoding="utf-8"))["gates"]
    if args.state == "POSTPRINT_PASS":
        incomplete = [gate for gate in job_record["postprint_gate_ids"] if gates[gate]["status"] != "PASS"]
        if incomplete:
            parser.error(f"POSTPRINT_PASS requires gates: {', '.join(incomplete)}")
    if args.state == "ASSEMBLY_PASS":
        incomplete = [gate for gate in job_record["assembly_gate_ids"] if gates[gate]["status"] != "PASS"]
        if incomplete:
            parser.error(f"ASSEMBLY_PASS requires gates: {', '.join(incomplete)}")

    completed_at = args.completed_at or datetime.now(timezone.utc).isoformat()
    if not args.operator.strip() or not args.evidence.strip():
        parser.error("operator and evidence must be non-blank")
    job_record["state_evidence"][args.state] = {
        "completed_at": completed_at,
        "operator": args.operator.strip(),
        "evidence": args.evidence.strip(),
    }
    job_record["current_state"] = args.state

    temporary = RECORD_PATH.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, RECORD_PATH)
    refreshed = tracker.build_tracker()
    tracker.write_outputs(refreshed)
    print(json.dumps(next(item for item in refreshed["jobs"] if item["job_id"] == args.job), indent=2))


if __name__ == "__main__":
    main()

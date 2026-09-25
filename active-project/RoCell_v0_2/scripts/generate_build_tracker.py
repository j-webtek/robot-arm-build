#!/usr/bin/env python3
"""Generate the professional print/build lifecycle tracker."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import validate_print_readiness as readiness

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config"
OUTPUT_JSON = ROOT / "BUILD_TRACKER.json"
OUTPUT_MD = ROOT / "BUILD_TRACKER.md"
EXPECTED_LIFECYCLE = [
    "UNRELEASED",
    "READY_TO_SLICE",
    "SLICE_REVIEWED",
    "PRINTED",
    "POSTPRINT_PASS",
    "KITTED",
    "ASSEMBLY_PASS",
    "IN_SERVICE",
]
MANUAL_STATES = EXPECTED_LIFECYCLE[2:]


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, dict)):
        return not value
    return False


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_tracker() -> dict[str, Any]:
    jobs_config = _load_json(CONFIG / "print_jobs.json")
    measurement = _load_json(CONFIG / "measurement_record.json")
    build_record = _load_json(CONFIG / "job_build_record.json")
    readiness.validate_measurement_record(measurement, jobs_config)

    revision = jobs_config["design_revision"]
    if measurement["design_revision"] != revision:
        raise ValueError("measurement and print-job design revisions disagree")
    if build_record.get("design_revision") != revision:
        raise ValueError("job_build_record.json design revision is stale")
    if build_record.get("lifecycle_states") != EXPECTED_LIFECYCLE:
        raise ValueError(
            "job_build_record.json lifecycle_states must exactly match the "
            "controlled lifecycle"
        )

    jobs = jobs_config["jobs"]
    job_records = build_record.get("jobs", [])
    records_by_id = {row.get("job_id"): row for row in job_records}
    expected_ids = {job["job_id"] for job in jobs}
    actual_ids = set(records_by_id)
    if len(records_by_id) != len(job_records):
        raise ValueError("job_build_record.json contains duplicate job IDs")
    if actual_ids != expected_ids:
        raise ValueError(
            "job_build_record.json and print_jobs.json disagree on job IDs; "
            f"missing={sorted(expected_ids - actual_ids)}, "
            f"extra={sorted(actual_ids - expected_ids)}"
        )

    gates = measurement["gates"]
    routes = measurement["selected_routes"]
    rows: list[dict[str, Any]] = []
    errors: list[str] = []

    for job in jobs:
        job_id = job["job_id"]
        build = records_by_id[job_id]
        selected = readiness.selection_active(job["selection"], routes)
        missing_prerequisites = [
            gate_id
            for gate_id in job["prerequisites"]
            if gates[gate_id]["status"] != "PASS"
        ]

        current_state = build.get("current_state")
        if current_state not in EXPECTED_LIFECYCLE:
            errors.append(f"{job_id}: invalid current_state {current_state!r}")
            current_index = 0
        else:
            current_index = EXPECTED_LIFECYCLE.index(current_state)

        if not selected:
            if current_index > 0:
                errors.append(
                    f"{job_id}: unselected route job cannot be advanced beyond UNRELEASED"
                )
            effective_state = "NOT_SELECTED"
        elif missing_prerequisites:
            if current_index > 0:
                errors.append(
                    f"{job_id}: recorded state {current_state} conflicts with "
                    "unresolved print prerequisites"
                )
            effective_state = "UNRELEASED"
        else:
            effective_state = (
                current_state
                if current_index >= EXPECTED_LIFECYCLE.index("READY_TO_SLICE")
                else "READY_TO_SLICE"
            )

        postprint_gate_ids = build.get("postprint_gate_ids", [])
        assembly_gate_ids = build.get("assembly_gate_ids", [])
        for field_name, gate_ids in (
            ("postprint_gate_ids", postprint_gate_ids),
            ("assembly_gate_ids", assembly_gate_ids),
        ):
            if not isinstance(gate_ids, list):
                errors.append(f"{job_id}: {field_name} must be a list")
                continue
            unknown = [gate_id for gate_id in gate_ids if gate_id not in gates]
            if unknown:
                errors.append(
                    f"{job_id}: {field_name} references unknown gates {unknown}"
                )

        evidence = build.get("state_evidence", {})
        if set(evidence) != set(MANUAL_STATES):
            errors.append(
                f"{job_id}: state_evidence must contain exactly {MANUAL_STATES}"
            )
        else:
            for state in MANUAL_STATES:
                state_index = EXPECTED_LIFECYCLE.index(state)
                if current_index < state_index:
                    continue
                state_record = evidence[state]
                if not isinstance(state_record, dict):
                    errors.append(f"{job_id}: {state} evidence must be an object")
                    continue
                blanks = [
                    key
                    for key in ("completed_at", "operator", "evidence")
                    if _is_blank(state_record.get(key))
                ]
                if blanks:
                    errors.append(
                        f"{job_id}: {state} requires completed evidence fields "
                        f"{', '.join(blanks)}"
                    )

        if current_index >= EXPECTED_LIFECYCLE.index("POSTPRINT_PASS"):
            incomplete = [
                gate_id
                for gate_id in postprint_gate_ids
                if gate_id in gates and gates[gate_id]["status"] != "PASS"
            ]
            if incomplete:
                errors.append(
                    f"{job_id}: POSTPRINT_PASS requires gates {incomplete}"
                )

        if current_index >= EXPECTED_LIFECYCLE.index("KITTED"):
            if _is_blank(build.get("kit_id")):
                errors.append(f"{job_id}: KITTED requires a non-blank kit_id")

        if current_index >= EXPECTED_LIFECYCLE.index("ASSEMBLY_PASS"):
            incomplete = [
                gate_id
                for gate_id in assembly_gate_ids
                if gate_id in gates and gates[gate_id]["status"] != "PASS"
            ]
            if incomplete:
                errors.append(
                    f"{job_id}: ASSEMBLY_PASS requires gates {incomplete}"
                )

        rows.append(
            {
                "job_id": job_id,
                "design_revision": revision,
                "selected": selected,
                "selection": job["selection"],
                "stage": job["stage"],
                "plate_file": job["plate_file"],
                "kit_id": build.get("kit_id"),
                "recorded_state": current_state,
                "effective_state": effective_state,
                "missing_prerequisites": missing_prerequisites,
                "postprint_gate_ids": postprint_gate_ids,
                "assembly_gate_ids": assembly_gate_ids,
            }
        )

    if errors:
        raise ValueError("invalid build lifecycle record:\n- " + "\n- ".join(errors))

    state_counts: dict[str, int] = {
        state: sum(row["effective_state"] == state for row in rows)
        for state in ["NOT_SELECTED", *EXPECTED_LIFECYCLE]
    }
    return {
        "schema_version": 1,
        "design_revision": revision,
        "lifecycle_states": EXPECTED_LIFECYCLE,
        "summary": {
            "total_jobs": len(rows),
            "selected_jobs": sum(row["selected"] for row in rows),
            "state_counts": state_counts,
        },
        "jobs": rows,
    }


def write_outputs(report: dict[str, Any]) -> None:
    OUTPUT_JSON.write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )
    summary = report["summary"]
    lines = [
        "# RoCell build tracker",
        "",
        f"**Design revision: {report['design_revision']}**",
        "",
        f"**{summary['selected_jobs']} selected / "
        f"{summary['total_jobs']} total jobs**",
        "",
        "Lifecycle: " + " -> ".join(report["lifecycle_states"]),
        "",
        "READY_TO_SLICE is derived from route selection and prerequisite gates. "
        "Every later state requires sequential signed evidence in "
        "config/job_build_record.json.",
        "",
        "| Job | Effective state | Recorded state | Stage | Kit | Plate | Blocking prerequisites |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in report["jobs"]:
        blocking = ", ".join(row["missing_prerequisites"]) or "-"
        lines.append(
            f"| {row['job_id']} | **{row['effective_state']}** | "
            f"{row['recorded_state']} | {row['stage']} | {row['kit_id']} | "
            f"{row['plate_file']} | {blocking} |"
        )

    lines += [
        "",
        "## State definitions",
        "",
        "- UNRELEASED: one or more selected-job prerequisites are unresolved.",
        "- READY_TO_SLICE: selected and every print prerequisite is PASS.",
        "- SLICE_REVIEWED: object count, orientation, supports, seams, brim, and critical layers were reviewed.",
        "- PRINTED: the complete cooled job was recovered and identified.",
        "- POSTPRINT_PASS: every mapped inspection/first-article gate is PASS.",
        "- KITTED: accepted parts, spares, hardware, and labels are together under the listed kit ID.",
        "- ASSEMBLY_PASS: every mapped module assembly gate is PASS.",
        "- IN_SERVICE: the accepted assembly was released for controlled operation.",
    ]
    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate and print the summary without writing generated trackers",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 2 while any selected job remains UNRELEASED",
    )
    args = parser.parse_args()
    report = build_tracker()
    if not args.check:
        write_outputs(report)
    print(json.dumps(report["summary"], indent=2))
    if args.strict and report["summary"]["state_counts"]["UNRELEASED"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()

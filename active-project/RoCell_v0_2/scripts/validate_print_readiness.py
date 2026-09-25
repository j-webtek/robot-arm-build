#!/usr/bin/env python3
"""Validate release evidence and generate the authoritative print queue."""
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config"
PLATES = ROOT / "print_plates_3mf"
VALID_GATE_STATUSES = {"PASS", "FAIL", "NOT_TESTED", "NA"}
REQUIRED_TEST_CONTEXT = (
    "operator",
    "date",
    "printer_serial",
    "measurement_tool_id",
    "evidence_directory",
    "qidi_studio_version",
)
REQUIRED_SCOPE_FIELDS = (
    "design_revision",
    "material",
    "process_profile",
    "nozzle_mm",
)
GEOMETRY_TOLERANCE_MM = 0.01
GEOMETRY_PARAMETER_MAP = (
    ("m3_insert_coupon_pass", "selected_pocket_mm", "heatset_m3_od"),
    ("m4_horizontal_insert_coupon_pass", "selected_pocket_mm", "m4_horizontal_insert_od"),
    ("setup_hardware_coupon_pass", "m3_head_recess_d_mm", "m3_head_recess_d"),
    ("setup_hardware_coupon_pass", "m4_washer_od_mm", "m4_washer_od"),
    ("setup_hardware_coupon_pass", "m5_washer_od_mm", "m5_washer_od"),
    ("setup_hardware_coupon_pass", "camera_hex_ac_mm", "camera_hex_ac"),
    ("tray_clearance_holes_coupon_pass", "m4_washer_od_mm", "m4_washer_od"),
    ("calibration_clearance_holes_coupon_pass", "m4_washer_od_mm", "m4_washer_od"),
    ("cradle_m4_washer_coupon_pass", "m4_washer_od_mm", "m4_washer_od"),
    ("precision_m3_head_coupon_pass", "m3_head_recess_d_mm", "m3_head_recess_d"),
    ("cable_tie_saddle_coupon_pass", "selected_slot_width_mm", "zip_tie_slot_w"),
    ("asa_mast_socket_coupon_pass", "selected_socket_mm", "mast_socket_size"),
    ("asa_m5_nut_coupon_pass", "selected_hex_mm", "m5_nut_ac"),
    ("asa_m5_clearance_coupon_pass", "m5_washer_od_mm", "m5_washer_od"),
)


def selection_active(selection: str, routes: dict[str, bool]) -> bool:
    if selection == "required":
        return True
    if selection == "any_tool_route":
        return bool(routes.get("phone_stylus_route") or routes.get("keyboard_rod_route"))
    return bool(routes.get(selection, False))


def _blank_paths(value: Any, path: str) -> list[str]:
    """Return every null, blank string, or empty collection below value."""
    if value is None:
        return [path]
    if isinstance(value, str):
        return [path] if not value.strip() else []
    if isinstance(value, dict):
        if not value:
            return [path]
        blanks: list[str] = []
        for key, item in value.items():
            blanks.extend(_blank_paths(item, f"{path}.{key}"))
        return blanks
    if isinstance(value, (list, tuple)):
        if not value:
            return [path]
        blanks = []
        for index, item in enumerate(value):
            blanks.extend(_blank_paths(item, f"{path}[{index}]"))
        return blanks
    return []


def _as_float(value: Any, label: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be numeric, not boolean")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be numeric; received {value!r}") from exc


def qidi_job_qualified(gate: dict[str, Any], job: dict[str, Any]) -> bool:
    """Require native QIDI Studio evidence for this exact job, not globally."""
    if gate.get("status") != "PASS":
        return False
    values = gate["recorded_values"]
    job_id = job["job_id"]
    try:
        return (
            job_id in values["validated_job_ids"]
            and bool(str(values["qidi_studio_version"]).strip())
            and bool(str(values["saved_profile_revision_by_job"][job_id]).strip())
            and abs(float(values["geometry_scale_percent_by_job"][job_id]) - 100.0) <= 0.001
            and int(values["object_count_by_job"][job_id]) == sum(job["parts"].values())
            and values["critical_layer_preview_pass_by_job"][job_id] is True
            and bool(str(values["evidence_reference_by_job"][job_id]).strip())
            and re.fullmatch(
                r"[0-9a-fA-F]{64}",
                str(values["native_project_sha256_by_job"][job_id]),
            ) is not None
        )
    except (KeyError, TypeError, ValueError):
        return False


def validate_qidi_roundtrip_gate(record: dict[str, Any], jobs_config: dict[str, Any]) -> None:
    """Validate the internal consistency of per-job native slicer evidence."""
    gate = record["gates"]["qidi_studio_roundtrip_confirmed"]
    if gate["status"] != "PASS":
        return
    values = gate["recorded_values"]
    validated = values["validated_job_ids"]
    if len(validated) != len(set(validated)):
        raise ValueError("qidi_studio_roundtrip_confirmed contains duplicate job IDs")
    jobs = {job["job_id"]: job for job in jobs_config["jobs"]}
    invalid_ids = sorted(set(validated) - set(jobs))
    if invalid_ids:
        raise ValueError(f"QIDI round-trip evidence references unknown jobs: {invalid_ids}")
    map_keys = (
        "saved_profile_revision_by_job",
        "geometry_scale_percent_by_job",
        "object_count_by_job",
        "critical_layer_preview_pass_by_job",
        "native_project_sha256_by_job",
        "evidence_reference_by_job",
    )
    for key in map_keys:
        if set(values[key]) != set(validated):
            raise ValueError(f"QIDI round-trip {key} keys must exactly match validated_job_ids")
    for job_id in validated:
        if jobs[job_id]["stage"] == "diagnostic":
            raise ValueError(f"Diagnostic job {job_id} does not require native-project release evidence")
        if not qidi_job_qualified(gate, jobs[job_id]):
            raise ValueError(f"Incomplete or inconsistent native QIDI Studio evidence for job {job_id}")


def validate_release_geometry(record: dict[str, Any]) -> list[dict[str, Any]]:
    """Compare accepted coupon selections with generated CAD parameters."""
    gate = record["gates"]["geometry_matches_measurements"]
    if gate["status"] != "PASS":
        return []

    revision = record["design_revision"]
    values = gate["recorded_values"]
    if values["design_revision"] != revision:
        raise ValueError(
            "geometry_matches_measurements recorded design_revision "
            f"{values['design_revision']!r} does not match {revision!r}"
        )
    if values["regeneration_completed"] is not True:
        raise ValueError("geometry_matches_measurements requires regeneration_completed=true")
    if values["affected_parts_reviewed"] is not True:
        raise ValueError("geometry_matches_measurements requires affected_parts_reviewed=true")

    parameter_path = (ROOT / str(values["effective_parameters_file"])).resolve()
    expected_parameter_path = (CONFIG / "parameters.json").resolve()
    if parameter_path != expected_parameter_path:
        raise ValueError(
            "geometry_matches_measurements effective_parameters_file must resolve to "
            "config/parameters.json"
        )
    parameters = json.loads(expected_parameter_path.read_text(encoding="utf-8"))

    checks: list[dict[str, Any]] = []
    for gate_id, value_key, parameter_key in GEOMETRY_PARAMETER_MAP:
        source = record["gates"][gate_id]
        if source["status"] != "PASS":
            continue
        observed = _as_float(
            source["recorded_values"][value_key],
            f"{gate_id}.{value_key}",
        )
        if parameter_key not in parameters:
            raise ValueError(f"config/parameters.json is missing {parameter_key}")
        expected = _as_float(parameters[parameter_key], parameter_key)
        delta = abs(observed - expected)
        check = {
            "gate_id": gate_id,
            "recorded_field": value_key,
            "parameter": parameter_key,
            "recorded_mm": observed,
            "parameter_mm": expected,
            "delta_mm": round(delta, 6),
            "tolerance_mm": GEOMETRY_TOLERANCE_MM,
            "status": "PASS" if delta <= GEOMETRY_TOLERANCE_MM else "FAIL",
        }
        checks.append(check)
        if delta > GEOMETRY_TOLERANCE_MM:
            raise ValueError(
                f"release geometry mismatch: {gate_id}.{value_key}={observed:.3f} mm "
                f"but {parameter_key}={expected:.3f} mm "
                f"(delta {delta:.3f} mm > {GEOMETRY_TOLERANCE_MM:.2f} mm)"
            )

    if not checks:
        raise ValueError(
            "geometry_matches_measurements cannot PASS until at least one mapped "
            "measurement or coupon source gate is PASS"
        )
    return checks


def validate_measurement_record(
    record: dict[str, Any],
    jobs_config: dict[str, Any],
) -> list[dict[str, Any]]:
    """Validate statuses, evidence completeness, scope, and release geometry."""
    record_revision = record.get("design_revision")
    jobs_revision = jobs_config.get("design_revision")
    if not record_revision or record_revision != jobs_revision:
        raise ValueError(
            "measurement_record.json and print_jobs.json design_revision values disagree"
        )

    gates = record.get("gates", {})
    if not isinstance(gates, dict) or not gates:
        raise ValueError("measurement_record.json must contain a non-empty gates object")

    prerequisite_ids = {
        gate_id
        for job in jobs_config["jobs"]
        for gate_id in job.get("prerequisites", [])
    }
    unknown = sorted(prerequisite_ids - set(gates))
    if unknown:
        raise ValueError(
            "print_jobs.json references undefined prerequisite gates: "
            + ", ".join(unknown)
        )

    context = record.get("test_context", {})
    context_blanks = _blank_paths(
        {key: context.get(key) for key in REQUIRED_TEST_CONTEXT},
        "test_context",
    )
    errors: list[str] = []
    for gate_id, gate in gates.items():
        status = gate.get("status")
        if status not in VALID_GATE_STATUSES:
            errors.append(f"{gate_id}: invalid status {status!r}")
            continue

        gate_scope = gate.get("scope")
        if not isinstance(gate_scope, dict):
            errors.append(f"{gate_id}: scope must be an object")
        else:
            missing_scope = [
                key for key in REQUIRED_SCOPE_FIELDS if key not in gate_scope
            ]
            if missing_scope:
                errors.append(
                    f"{gate_id}: missing scope fields {', '.join(missing_scope)}"
                )
            else:
                blank_scope = _blank_paths(
                    {key: gate_scope[key] for key in REQUIRED_SCOPE_FIELDS},
                    f"gates.{gate_id}.scope",
                )
                if blank_scope:
                    errors.append(
                        f"{gate_id}: blank scope values {', '.join(blank_scope)}"
                    )
                if gate_scope["design_revision"] != record_revision:
                    errors.append(
                        f"{gate_id}: scope revision {gate_scope['design_revision']!r} "
                        f"does not match {record_revision!r}"
                    )

        recorded = gate.get("recorded_values")
        if not isinstance(recorded, dict) or not recorded:
            errors.append(f"{gate_id}: recorded_values must be a non-empty object")
            continue
        if status == "PASS":
            blanks = _blank_paths(
                recorded,
                f"gates.{gate_id}.recorded_values",
            )
            if blanks:
                errors.append(
                    f"{gate_id}: PASS has blank evidence fields {', '.join(blanks)}"
                )
            if gate.get("category") != "machine" and context_blanks:
                errors.append(
                    f"{gate_id}: non-machine PASS requires complete test_context; "
                    f"blank fields: {', '.join(context_blanks)}"
                )

    if errors:
        raise ValueError("invalid release evidence:\n- " + "\n- ".join(errors))
    validate_qidi_roundtrip_gate(record, jobs_config)
    return validate_release_geometry(record)


def context_has_blanks(record: dict[str, Any]) -> bool:
    context = record.get("test_context", {})
    selected = {key: context.get(key) for key in REQUIRED_TEST_CONTEXT}
    return bool(_blank_paths(selected, "test_context"))


def build_report() -> dict[str, Any]:
    record = json.loads(
        (CONFIG / "measurement_record.json").read_text(encoding="utf-8")
    )
    jobs_config = json.loads(
        (CONFIG / "print_jobs.json").read_text(encoding="utf-8")
    )
    profiles = json.loads(
        (CONFIG / "print_profiles.json").read_text(encoding="utf-8")
    )
    geometry_checks = validate_measurement_record(record, jobs_config)
    jobs = jobs_config["jobs"]
    gates = record["gates"]
    routes = record["selected_routes"]

    manifest_rows = list(
        csv.DictReader((ROOT / "PLATE_MANIFEST.csv").open(encoding="utf-8"))
    )
    manifest = {row["job_id"]: row for row in manifest_rows}
    expected_job_ids = {job["job_id"] for job in jobs}
    if set(manifest) != expected_job_ids:
        missing = sorted(expected_job_ids - set(manifest))
        extra = sorted(set(manifest) - expected_job_ids)
        raise ValueError(
            "PLATE_MANIFEST.csv and config/print_jobs.json disagree on job IDs; "
            f"missing={missing}, extra={extra}"
        )

    results = []
    active_missing: list[str] = []
    for job in jobs:
        selected = selection_active(job["selection"], routes)
        missing = []
        for gate_id in job["prerequisites"]:
            if gate_id == "qidi_studio_roundtrip_confirmed":
                if not qidi_job_qualified(gates[gate_id], job):
                    missing.append(gate_id)
            elif gates[gate_id]["status"] != "PASS":
                missing.append(gate_id)
        if not selected:
            status = "NOT_SELECTED"
        elif missing:
            status = "WAITING"
            active_missing.extend(missing)
        else:
            status = "READY"

        plate_path = PLATES / job["plate_file"]
        sidecar_path = plate_path.with_suffix(".print.json")
        if not plate_path.exists() or not sidecar_path.exists():
            raise FileNotFoundError(
                f"Missing 3MF or settings sidecar for job {job['job_id']}"
            )
        profile_name = job["profile"]
        if profile_name not in profiles["process_profiles"]:
            raise ValueError(
                f"Job {job['job_id']} references unknown profile {profile_name}"
            )
        profile = profiles["process_profiles"][profile_name]
        results.append(
            {
                "job_id": job["job_id"],
                "design_revision": record["design_revision"],
                "status": status,
                "selected": selected,
                "stage": job["stage"],
                "plate_file": job["plate_file"],
                "settings_file": sidecar_path.name,
                "purpose": job["purpose"],
                "material": profile["material"],
                "process_profile": profile_name,
                "nozzle_mm": profile["nozzle_mm"],
                "layer_mm": profile["layer_height_mm"],
                "parts": job["parts"],
                "missing_gates": missing,
            }
        )

    unique_missing = list(dict.fromkeys(active_missing))
    summary = {
        "ready": sum(row["status"] == "READY" for row in results),
        "waiting": sum(row["status"] == "WAITING" for row in results),
        "not_selected": sum(
            row["status"] == "NOT_SELECTED" for row in results
        ),
        "total_jobs": len(results),
    }
    return {
        "schema_version": 2,
        "design_revision": record["design_revision"],
        "printer": record["printer"],
        "selected_routes": routes,
        "test_context_complete": not context_has_blanks(record),
        "geometry_release_checks": geometry_checks,
        "summary": summary,
        "jobs": results,
        "unresolved_gates": [
            {
                "gate_id": gate_id,
                "status": gates[gate_id]["status"],
                "scope": gates[gate_id]["scope"],
                "evidence_required": gates[gate_id]["evidence"],
                "recorded_values": gates[gate_id]["recorded_values"],
            }
            for gate_id in unique_missing
        ],
    }


def write_outputs(report: dict[str, Any]) -> None:
    (ROOT / "PRINT_READINESS.json").write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )
    summary = report["summary"]
    lines = [
        "# Print readiness - QIDI Plus4",
        "",
        f"**Design revision: {report['design_revision']}**",
        "",
        f"**{summary['ready']} ready / {summary['waiting']} waiting / "
        f"{summary['not_selected']} not selected / "
        f"{summary['total_jobs']} total jobs**",
        "",
        "This report is generated from config/measurement_record.json. "
        "READY means every release prerequisite is PASS with complete evidence; "
        "post-print, kitting, and assembly progression is tracked separately.",
        "",
        "| Job | Status | Stage | Material/profile | Layer | Plate | Purpose |",
        "|---|---|---|---|---:|---|---|",
    ]
    for job in report["jobs"]:
        lines.append(
            f"| {job['job_id']} | **{job['status']}** | {job['stage']} | "
            f"{job['material']} / {job['process_profile']} | "
            f"{job['layer_mm']:.2f} mm | {job['plate_file']} | "
            f"{job['purpose']} |"
        )
        if job["missing_gates"]:
            lines.append(
                f"|  | Missing |  |  |  |  | {', '.join(job['missing_gates'])} |"
            )

    lines += ["", "## Required next evidence", ""]
    if report["unresolved_gates"]:
        for gate in report["unresolved_gates"]:
            gate_scope = gate["scope"]
            lines.append(
                f"- {gate['gate_id']} ({gate['status']}; "
                f"{gate_scope['process_profile']}; "
                f"rev {gate_scope['design_revision']}): "
                f"{gate['evidence_required']}"
            )
    else:
        lines.append("- All selected-job prerequisite gates pass.")

    lines += [
        "",
        "## Safe workflow",
        "",
        "1. Complete operator, date, printer, measurement-tool, evidence-directory, and QIDI Studio test context.",
        "2. Confirm the 0.4 mm nozzle and calibrate every exact filament/profile combination.",
        "3. Print diagnostic jobs 00A, 00B, 00C, 00D, 00E, and 00F with their matching profiles.",
        "4. Measure devices and hardware; record each coupon selection and its process/profile/revision scope.",
        "5. Apply accepted selections to config/parameters.json, regenerate affected geometry, and pass the objective geometry check.",
        "6. Re-run python scripts/validate_print_readiness.py and print only jobs marked READY.",
        "7. Use python scripts/generate_build_tracker.py for slice review, print inspection, kitting, assembly, and service release.",
    ]
    (ROOT / "PRINT_READINESS.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 2 while selected jobs are waiting",
    )
    args = parser.parse_args()
    report = build_report()
    write_outputs(report)
    print(json.dumps(report["summary"], indent=2))
    if args.strict and report["summary"]["waiting"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()

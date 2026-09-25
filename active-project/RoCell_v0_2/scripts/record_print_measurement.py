#!/usr/bin/env python3
"""Safely record one compatibility gate or route selection and refresh readiness."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import validate_print_readiness as readiness

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "config" / "measurement_record.json"


def parse_value(value: str):
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def has_blank(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, dict):
        return any(has_blank(item) for item in value.values())
    if isinstance(value, list):
        return any(has_blank(item) for item in value)
    return False


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gate", help="Gate ID to update")
    parser.add_argument("--status", choices=sorted(readiness.VALID_GATE_STATUSES))
    parser.add_argument("--value", action="append", default=[], metavar="KEY=VALUE")
    parser.add_argument("--evidence-note")
    parser.add_argument("--route", choices=["phone_stylus_route", "keyboard_rod_route", "camera_mast_optional"])
    parser.add_argument("--selected", choices=["yes", "no"])
    parser.add_argument("--context", action="append", default=[], metavar="KEY=VALUE",
                        help="Record operator/date/printer/tool/evidence/QIDI Studio context")
    parser.add_argument("--qidi-job", help="Record a native QIDI Studio round-trip for one non-diagnostic job")
    parser.add_argument("--qidi-version")
    parser.add_argument("--profile-revision")
    parser.add_argument("--native-project")
    parser.add_argument("--geometry-scale-percent", type=float)
    parser.add_argument("--object-count", type=int)
    parser.add_argument("--critical-preview-pass", choices=["yes", "no"])
    args = parser.parse_args()

    data = json.loads(RECORD.read_text(encoding="utf-8"))
    if args.context:
        if args.route or args.gate or args.qidi_job:
            parser.error("--context is a separate operation; do not combine it with --gate/--route/--qidi-job")
        for assignment in args.context:
            if "=" not in assignment:
                parser.error(f"Invalid --context {assignment}; expected KEY=VALUE")
            key, value = assignment.split("=", 1)
            if key not in data["test_context"]:
                parser.error(f"Unknown test-context field: {key}")
            data["test_context"][key] = parse_value(value)
    elif args.qidi_job:
        required = {
            "--qidi-version": args.qidi_version,
            "--profile-revision": args.profile_revision,
            "--native-project": args.native_project,
            "--geometry-scale-percent": args.geometry_scale_percent,
            "--object-count": args.object_count,
            "--critical-preview-pass": args.critical_preview_pass,
            "--evidence-note": args.evidence_note,
        }
        missing_args = [name for name, value in required.items() if value is None or value == ""]
        if missing_args:
            parser.error("--qidi-job requires " + ", ".join(missing_args))
        jobs_doc = json.loads((ROOT / "config" / "print_jobs.json").read_text(encoding="utf-8"))
        jobs = {job["job_id"]: job for job in jobs_doc["jobs"]}
        if args.qidi_job not in jobs:
            parser.error(f"Unknown QIDI job: {args.qidi_job}")
        job = jobs[args.qidi_job]
        if job["stage"] == "diagnostic":
            parser.error("Diagnostic jobs do not use the production QIDI round-trip gate")
        expected_count = sum(job["parts"].values())
        if args.object_count != expected_count:
            parser.error(
                f"Object count for {args.qidi_job} must be {expected_count}, not {args.object_count}"
            )
        if abs(args.geometry_scale_percent - 100.0) > 0.001:
            parser.error("Released QIDI projects must retain exactly 100.0% geometry scale")
        if args.critical_preview_pass != "yes":
            parser.error("Cannot release a QIDI job whose critical layer preview did not pass")
        project_path = Path(args.native_project)
        if not project_path.is_absolute():
            project_path = ROOT / project_path
        project_path = project_path.resolve()
        if not project_path.is_file():
            parser.error(f"Native QIDI project does not exist: {project_path}")
        context_version = data.get("test_context", {}).get("qidi_studio_version")
        if context_version != args.qidi_version:
            parser.error(
                "--qidi-version must exactly match test_context.qidi_studio_version; "
                "update --context first when the slicer changes"
            )
        gate = data["gates"]["qidi_studio_roundtrip_confirmed"]
        values = gate["recorded_values"]
        existing_version = values.get("qidi_studio_version")
        if existing_version not in (None, args.qidi_version):
            parser.error("Existing QIDI evidence uses a different Studio version; invalidate and repeat it")
        values["qidi_studio_version"] = args.qidi_version
        if args.qidi_job not in values["validated_job_ids"]:
            values["validated_job_ids"].append(args.qidi_job)
        job_order = {job_id: index for index, job_id in enumerate(jobs)}
        values["validated_job_ids"].sort(key=job_order.__getitem__)
        values["saved_profile_revision_by_job"][args.qidi_job] = args.profile_revision
        values["geometry_scale_percent_by_job"][args.qidi_job] = args.geometry_scale_percent
        values["object_count_by_job"][args.qidi_job] = args.object_count
        values["critical_layer_preview_pass_by_job"][args.qidi_job] = True
        values["native_project_sha256_by_job"][args.qidi_job] = file_sha256(project_path)
        values["evidence_reference_by_job"][args.qidi_job] = args.evidence_note
        gate["status"] = "PASS"
    elif args.route:
        if args.selected is None:
            parser.error("--route requires --selected yes|no")
        data["selected_routes"][args.route] = args.selected == "yes"
    elif args.gate:
        if args.gate not in data["gates"]:
            parser.error(f"Unknown gate: {args.gate}")
        if args.status is None:
            parser.error("--gate requires --status")
        gate = data["gates"][args.gate]
        gate["status"] = args.status
        values = gate.setdefault("recorded_values", {})
        for assignment in args.value:
            if "=" not in assignment:
                parser.error(f"Invalid --value {assignment}; expected KEY=VALUE")
            key, value = assignment.split("=", 1)
            if key not in values:
                parser.error(f"Unknown recorded value {key} for {args.gate}")
            values[key] = parse_value(value)
        if args.evidence_note:
            gate["evidence_note"] = args.evidence_note
        if args.status == "PASS":
            if has_blank(values):
                missing = [key for key, value in values.items() if has_blank(value)]
                parser.error(
                    f"PASS rejected for {args.gate}; record every required value: {missing}"
                )
            if gate.get("category") != "machine" and has_blank(data.get("test_context", {})):
                missing = [
                    key for key, value in data.get("test_context", {}).items()
                    if has_blank(value)
                ]
                parser.error(
                    f"PASS rejected for {args.gate}; complete test context first: {missing}"
                )
            if not str(gate.get("evidence_note", "")).strip():
                parser.error(
                    f"PASS rejected for {args.gate}; supply --evidence-note with the result or photo path"
                )
    else:
        parser.error("Specify --gate, --route, --qidi-job, or one or more --context assignments")

    temp = RECORD.with_suffix(".json.tmp")
    temp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    temp.replace(RECORD)
    report = readiness.build_report()
    readiness.write_outputs(report)
    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    main()

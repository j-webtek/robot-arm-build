#!/usr/bin/env python3
"""Independent release-package checks for CAD, plates, profiles, layout and hashes."""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config"
STL = ROOT / "stl"
PLATES = ROOT / "print_plates_3mf"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fail(message: str) -> None:
    raise ValueError(message)


def validate_layout(layout: dict, frame_size: float) -> None:
    board_w = float(layout["board"]["width"])
    board_d = float(layout["board"]["depth"])
    rectangles = [
        ("keyboard", *layout["keyboard"]["origin_xy"], *layout["keyboard"]["outer_envelope"]),
        ("phone", *layout["phone"]["origin_xy"], *layout["phone"]["outer_envelope"]),
        ("calibration_puck", *layout["calibration_puck"]["origin_xy"], *layout["calibration_puck"]["size"]),
    ]
    rectangles += [
        (f"tag_{name}", x, y, frame_size, frame_size)
        for name, (x, y) in layout["tags"].items()
    ]
    for name, x, y, width, depth in rectangles:
        if min(x, y) < -1e-6 or x + width > board_w + 1e-6 or y + depth > board_d + 1e-6:
            fail(f"Layout rectangle leaves board: {name}")
    for index, (name_a, ax, ay, aw, ad) in enumerate(rectangles):
        for name_b, bx, by, bw, bd in rectangles[index + 1:]:
            overlap = np.minimum((ax + aw, ay + ad), (bx + bw, by + bd)) - np.maximum((ax, ay), (bx, by))
            if np.all(overlap > 1e-6):
                fail(f"Layout overlap: {name_a}/{name_b} = {overlap}")
    for hole in layout["pilot_holes"]:
        x, y, radius = float(hole["x"]), float(hole["y"]), float(hole["diameter"]) / 2
        if x - radius < 0 or y - radius < 0 or x + radius > board_w or y + radius > board_d:
            fail(f"Pilot hole leaves board: {hole}")
    # The four corner-tag fastener centers are the closest intentionally used
    # board-edge features; require the documented 14 mm center margin.
    for name in ("T0", "T1", "T2", "T3"):
        ox, oy = layout["tags"][name]
        for x in (ox + 6.0, ox + frame_size - 6.0):
            y = oy + frame_size / 2.0
            if min(x, board_w - x, y, board_d - y) < 14.0 - 1e-6:
                fail(f"Tag fastener violates 14 mm board-edge center margin: {name}")


def main() -> None:
    jobs_doc = json.loads((CONFIG / "print_jobs.json").read_text(encoding="utf-8"))
    profiles = json.loads((CONFIG / "print_profiles.json").read_text(encoding="utf-8"))
    parameters = json.loads((CONFIG / "parameters.json").read_text(encoding="utf-8"))
    layout = json.loads((CONFIG / "workcell_layout.json").read_text(encoding="utf-8"))
    jobs = jobs_doc["jobs"]
    if len({job["job_id"] for job in jobs}) != len(jobs):
        fail("Duplicate job ID")
    if len({job["plate_file"] for job in jobs}) != len(jobs):
        fail("Duplicate plate filename")

    configured_parts = {filename for job in jobs for filename in job["parts"]}
    disk_parts = {path.name for path in STL.glob("*.stl")} - {"BOARD_REFERENCE_DO_NOT_PRINT.stl"}
    if configured_parts != disk_parts:
        fail(f"Printable STL coverage mismatch; missing={disk_parts-configured_parts}, extra={configured_parts-disk_parts}")

    validation_rows = list(csv.DictReader((ROOT / "PART_VALIDATION.csv").open(encoding="utf-8")))
    if {Path(row["stl"]).name for row in validation_rows} != configured_parts:
        fail("PART_VALIDATION.csv does not cover every printable STL exactly")

    mesh_count = 0
    for filename in sorted(configured_parts):
        mesh = trimesh.load_mesh(STL / filename, force="mesh")
        components = len(mesh.split(only_watertight=False))
        if not mesh.is_watertight or not mesh.is_winding_consistent or components != 1 or mesh.volume <= 0:
            fail(f"Invalid STL {filename}: watertight={mesh.is_watertight}, winding={mesh.is_winding_consistent}, components={components}, volume={mesh.volume}")
        if np.any(mesh.extents > np.array([parameters["printer_safe_x"], parameters["printer_safe_y"], parameters["printer_safe_z"]]) + 1e-6):
            fail(f"STL exceeds protected Plus4 envelope: {filename} {mesh.extents}")
        mesh_count += 1

    expected_profile_gate = {
        "petg_general_0p4": "petg_general_profile_calibrated",
        "petg_tray_structural_0p4": "petg_tray_profile_calibrated",
        "petg_cradle_0p4": "petg_cradle_profile_calibrated",
        "petg_precision_0p4": "petg_precision_profile_calibrated",
        "petg_adapter_0p4": "petg_adapter_profile_calibrated",
        "petg_calibration_0p4": "petg_calibration_profile_calibrated",
        "tpu95a_0p4": "tpu_profile_calibrated",
        "asa_structural_0p4": "asa_profile_calibrated",
    }
    expected_plate_files = set()
    total_objects = 0
    plate_summary = []
    for job in jobs:
        job_id = job["job_id"]
        profile_name = job["profile"]
        if profile_name not in profiles["process_profiles"]:
            fail(f"Unknown profile in {job_id}: {profile_name}")
        prerequisites = set(job["prerequisites"])
        required_common = {"plus4_machine_confirmed", "nozzle_0p4_confirmed", expected_profile_gate[profile_name]}
        if not required_common.issubset(prerequisites):
            fail(f"{job_id} lacks process qualification: {required_common-prerequisites}")
        if job["stage"] != "diagnostic" and "qidi_studio_roundtrip_confirmed" not in prerequisites:
            fail(f"Non-diagnostic job lacks native QIDI Studio round-trip gate: {job_id}")

        plate_path = PLATES / job["plate_file"]
        sidecar_path = plate_path.with_suffix(".print.json")
        expected_plate_files.add(plate_path.name)
        if not plate_path.exists() or not sidecar_path.exists():
            fail(f"Missing plate or sidecar: {job_id}")
        sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
        if sidecar["job_id"] != job_id or sidecar["design_revision"] != jobs_doc["design_revision"]:
            fail(f"Sidecar identity/revision mismatch: {job_id}")
        if sidecar["parts"] != job["parts"] or sidecar["process_profile_name"] != profile_name:
            fail(f"Sidecar manifest/profile mismatch: {job_id}")
        if sidecar["plate_sha256"] != sha256(plate_path):
            fail(f"Plate hash mismatch: {job_id}")
        for filename, digest in sidecar["source_stl_sha256"].items():
            if digest != sha256(STL / filename):
                fail(f"Source STL hash mismatch: {job_id}/{filename}")
        scene = trimesh.load(plate_path, force="scene")
        if scene.is_empty or len(scene.geometry) != sum(job["parts"].values()):
            fail(f"3MF build-item count/read-back failure: {job_id}")
        bounds = np.asarray(scene.bounds)
        extents = bounds[1] - bounds[0]
        if np.any(extents > np.array(profiles["printer"]["safe_plate_envelope_mm"]) + 1e-6):
            fail(f"Plate exceeds protected envelope: {job_id}")
        center = (bounds[0, :2] + bounds[1, :2]) / 2
        if not np.allclose(center, np.array(profiles["printer"]["nominal_build_volume_mm"][:2]) / 2, atol=0.01):
            fail(f"Plate is not centered on the nominal bed: {job_id} center={center}")
        total_objects += len(scene.geometry)
        plate_summary.append({
            "job_id": job_id,
            "plate_file": plate_path.name,
            "objects": len(scene.geometry),
            "extent": [round(float(value), 1) for value in extents],
            "profile": profile_name,
        })

    disk_plates = {path.name for path in PLATES.glob("*.3mf")}
    if disk_plates != expected_plate_files:
        fail(f"Plate directory drift; unexpected={disk_plates-expected_plate_files}, missing={expected_plate_files-disk_plates}")
    manifest = list(csv.DictReader((ROOT / "PLATE_MANIFEST.csv").open(encoding="utf-8")))
    if {row["job_id"] for row in manifest} != {job["job_id"] for job in jobs}:
        fail("PLATE_MANIFEST.csv job coverage mismatch")

    validate_layout(layout, float(parameters["tag_frame_size"]))
    report = {
        "design_revision": jobs_doc["design_revision"],
        "status": "PASS",
        "printable_stls": mesh_count,
        "configured_jobs": len(jobs),
        "plate_objects": total_objects,
        "all_stls_watertight_single_body": True,
        "all_parts_and_plates_fit_protected_plus4_envelope": True,
        "all_3mf_files_roundtrip_in_independent_reader": True,
        "all_sidecar_and_source_hashes_match": True,
        "all_non_diagnostic_jobs_require_native_qidi_roundtrip": True,
        "layout_nonoverlap_and_edge_checks": True,
    }
    (ROOT / "RELEASE_VALIDATION.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# CAD and release-package verification", "",
        f"**Revision `{jobs_doc['design_revision']}` — automated status: PASS**", "",
        "The release check independently reloads every STL and 3MF; verifies positive, watertight, winding-consistent single bodies; checks the protected 295 x 295 x 280 mm QIDI Plus4 envelope; confirms object counts, centered placement, source/plate hashes, job/profile qualification, manifest coverage, and a non-overlapping board layout.", "",
        f"- Printable STL models: **{mesh_count}**", f"- Controlled print jobs: **{len(jobs)}**",
        f"- Total placed 3MF objects: **{total_objects}**", "- Unexpected or uncovered printable files: **0**", "",
        "## QIDI Plus4 plate read-back", "",
        "| Job | Plate | Objects | Envelope mm | Profile |", "|---|---|---:|---:|---|",
    ]
    for row in plate_summary:
        lines.append(
            f"| {row['job_id']} | `{row['plate_file']}` | {row['objects']} | "
            f"{' x '.join(str(value) for value in row['extent'])} | `{row['profile']}` |"
        )
    lines += [
        "", "## Release boundary", "",
        "This automated PASS establishes internal CAD/packaging consistency, not physical compatibility. Production remains locked by `PRINT_READINESS.md` until the exact devices, hardware, filament lots, coupons, QIDI Studio native projects, first articles, and post-print/assembly tests are measured and recorded.", "",
        "The camera thread/head interface, real USB cable bend envelope, stylus/rod retention, spring rate, extrusion shrink, and all force/creep limits deliberately remain physical gates rather than unverified CAD assumptions.", "",
        "Re-run `python scripts/validate_release_package.py` after every CAD, profile, job, or plate change.",
    ]
    (ROOT / "CAD_VERIFICATION.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

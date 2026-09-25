#!/usr/bin/env python3
"""Generate one auditable manufacturing traveler for every configured print job."""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config"
PLATES = ROOT / "print_plates_3mf"
OUT = ROOT / "job_cards"


ORIENTATION = {
    "keyboard_tray_left.stl": "Flat, exported base on bed; RC02-L readable on top",
    "keyboard_tray_right.stl": "Flat, exported base on bed; RC02-R readable on top",
    "keyboard_rear_clamp.stl": "Flat base on bed; padded face upright",
    "phone_cradle_a16.stl": "Flat base on bed; USB mark toward plate front",
    "phone_clamp_tip_TPU_M4.stl": "Upright, flared bore entry on bed",
    "phone_width_fit_test.stl": "Flat as exported",
    "keyboard_corner_fit_test.stl": "Flat as exported",
    "keyboard_seam_fit_male.stl": "Flat as exported; key upward",
    "keyboard_seam_fit_female.stl": "Flat as exported; pocket upward",
    "hardware_fit_gauge.stl": "Flat as exported; engraved labels upward",
    "m4_washer_fit_gauge.stl": "Flat as exported; W8.8/W9.2/W9.6 labels upward",
    "m3_head_fit_gauge.stl": "Flat as exported; H5.8/H6.2/H6.6 labels upward",
    "m3_insert_fit_gauge.stl": "Flat as exported; insert mouths upward",
    "m4_horizontal_insert_fit_gauge.stl": "Flat as exported; production-axis bores horizontal",
    "m5_nut_trap_fit_gauge.stl": "Tall block as exported; production-axis traps horizontal",
    "setup_hardware_fit_gauge.stl": "Flat as exported; all labels upward",
    "thread_pilot_fit_gauge.stl": "Tall block as exported; blind pilots horizontal",
    "cable_tie_saddle_fit_gauge.stl": "Flat as exported; saddles upward",
    "mast_socket_fit_test.stl": "Flat as exported; 20 mm socket engagement vertical",
    "tpu_tip_retention_gauge.stl": "Flat base on bed; both rigid pegs upward",
    "tag_frame_ID0_55mm.stl": "Flat as exported; ID0 and +Y readable",
    "tag_frame_ID1_55mm.stl": "Flat as exported; ID1 and +Y readable",
    "tag_frame_ID2_55mm.stl": "Flat as exported; ID2 and +Y readable",
    "tag_frame_ID3_55mm.stl": "Flat as exported; ID3 and +Y readable",
    "tag_frame_ID4_55mm.stl": "Flat as exported; ID4 and +Y readable",
    "tag_frame_ID5_55mm.stl": "Flat as exported; ID5 and +Y readable",
    "camera_plate_universal.stl": "Flat as exported; CAM/MAST labels upward",
    "calibration_puck.stl": "Flat as exported; crosshair upward; ironing off",
    "compliant_tool_body.stl": "Upright on lower end with specified brim",
    "compliant_tool_top_cap.stl": "Flat, underside on bed; UP visible after print",
    "compliant_tool_grip_fit_test.stl": "Upright as exported; full 28 mm grip face vertical",
    "spring_fit_gauge.stl": "Flat as exported; stepped cup upward",
    "stylus_collar_9mm.stl": "Flat flange on bed; split and radial pilot open",
    "rod_bushing_6_to_9mm.stl": "Upright on flange with 8 mm brim",
    "keyboard_tip_TPU_6mm.stl": "Upright, flared bore entry on bed",
    "stylus_diameter_gauge.stl": "Flat as exported; labels upward",
    "mast_foot_2020.stl": "Flat 92 x 92 mm base on bed; socket vertical",
}


DETAILS = {
    "00A": ("KIT-CAL", "Actual keyboard, board screws, M4 washers, calipers", "Inspect labels and all hole mouths; mate seam coupons fully; record corner seating, seam gap/rock, the smallest free-passing hole, and the smallest washer recess that seats flat.", "keyboard_corner_coupon_pass; keyboard_seam_coupon_pass; tray_clearance_holes_coupon_pass"),
    "00B": ("KIT-CAL", "Actual phone/case, M4 inserts/washers, USB cable and selected ties", "Record phone hand-fit, selected horizontal insert pocket, insert squareness/spin resistance, selected saddle, cable bend clearance, and the smallest flat-seating M4 washer recess.", "phone_width_coupon_pass; m4_horizontal_insert_coupon_pass; cable_tie_saddle_coupon_pass; cradle_m4_washer_coupon_pass"),
    "00C": ("KIT-CAL", "RoArm gripper, actual spring, M3 inserts/screws, calipers", "Verify the full 28 mm grip interface; record no slip/crush; record spring OD/ID/free length and both seat fits; install-test each M3 pocket and select the smallest below-flush M3 head recess.", "gripper_coupon_pass; spring_fit_coupon_pass; m3_insert_coupon_pass; precision_m3_head_coupon_pass"),
    "00D": ("KIT-CAL", "Measured stylus, M2/M3 screws, driver, calipers", "Select the smallest free-sliding stylus bore and usable thread pilot. The thick gauge selects a pilot only; final thin-collar pull/cycle testing remains mandatory.", "stylus_gauge_coupon_pass; adapter_retention_method_selected"),
    "00E": ("KIT-CAL", "M3/M4/M5 screws, washers, 1/4-20 hardware, TPU tip samples", "Record general clearances, screw-head and washer seats, camera hex choice, and rigid-peg preliminary fit. Do not use the rigid peg alone to release TPU production.", "general_clearance_holes_coupon_pass; setup_hardware_coupon_pass"),
    "00F": ("KIT-CAL", "M4 board screw/bolt, washer, and measuring tools", "Use the exact 0.16 mm calibration profile; record the smallest freely passing M4 option and smallest flat-seating washer recess. Retain and label this coupon separately from 00A/00E.", "calibration_clearance_holes_coupon_pass"),
    "01": ("KIT-KB", "Flatness surface, calipers, four board screws/washers", "Cool fully; inspect all four closed slots, washer tracks, solid-rail pad pockets, seam keys, datums, and overall flatness. Reject cracks or lifted corners.", "keyboard_left_first_article_pass"),
    "02": ("KIT-KB", "Accepted left half, keyboard, eight board screws/washers", "Repeat first-article checks; mate both halves; record seam gap, flushness, assembled envelope, and rocking. Ten removal/reinstall cycles follow mounting.", "keyboard_tray_pair_postprint_pass; keyboard_fixture_assembly_pass"),
    "03A": ("KIT-PHONE", "Phone/case, cable, 2 M4 inserts, 2 thumb screws, accepted TPU tips, 4 board screws/washers, ties", "Inspect flatness, closed mounting ears, rails, towers and raised cable saddle. Install inserts square, verify all keepouts, then complete ten phone cycles without button contact.", "phone_cradle_postprint_pass; phone_fixture_assembly_pass"),
    "03B": ("KIT-KB", "Keyboard, two face pads, two board screws/washers", "Verify both parts match, bases are flat, gussets intact, scales readable and slots open. Pad faces; tighten only to contact; run the keyboard repeatability test.", "keyboard_clamps_postprint_pass; keyboard_fixture_assembly_pass"),
    "03C1": ("KIT-VISION-TAG", "ID0 paper tile, matte tape, two screws/washers, ruler", "Verify the 55.4 mm pocket, 40.0 mm detection edge, thumbnail scoop, +Y orientation, flatness, and complete washer isolation from artwork.", "tag_artwork_scale_pass; tag_frame_first_article_pass"),
    "03C2": ("KIT-VISION-TAG", "ID1-ID5 tiles, matte tape, ten screws/washers", "Confirm every physical ID matches its debossed frame and board map. Check all faces flat, matte, unobstructed, and oriented +Y before mounting.", "tag_frame_batch_postprint_pass; tag_frame_installation_pass"),
    "03C3": ("KIT-VISION-CAM", "Actual camera, 1/4-20 screw, two M5 screws/T-nuts/washers, straps", "Measure camera thread direction, screw/head dimensions and safe engagement first. Check M5 ligaments, scales, strap slots, cable direction and no screw bottoming.", "camera_plate_hardware_pass"),
    "03D": ("KIT-PUCK", "Two board screws/washers, straightedge, depth/height gauge", "Reject a smeared crosshair/divot. Record free-state and mounted flatness plus assembled datum height; do not iron the top surface.", "calibration_puck_datum_pass"),
    "04A": ("KIT-TOOL-COMMON", "Two M3 inserts, two M3x10 screws, accepted spring, route adapter", "Inspect body straightness, grip flats, guide bore, spring chamber and keyed locator. Install inserts square; cap must seat only in the keyed orientation. Verify 3-6 mm smooth return after route assembly.", "tool_body_postprint_pass; tool_assembled_motion_pass"),
    "04B": ("KIT-TOOL-PHONE", "Measured stylus, selected M2 screw or removable retaining method, pull gauge", "Check bore, split and thin-wall pilot. Set projection, then quantify pull retention and repeat cycles; inspect after 24-hour creep and verify capacitive function.", "stylus_collar_retention_pass; stylus_function_pass"),
    "04C": ("KIT-TOOL-KB", "Deburred 6 mm rod, selected retaining method, pull gauge", "Check bore and split, press fit without cracks, set 30-40 mm projection, then quantify pull retention and 24-hour creep. No radial M3 screw is permitted in the thin flange.", "rod_bushing_retention_pass"),
    "05A": ("KIT-PHONE", "Actual M4 screw/peg and pull gauge", "Inspect flared bore, seating witness and contact face. Fit to actual hardware, record seating depth and provisional axial pull force; retain as the first article.", "phone_tpu_retention_coupon_pass"),
    "05B": ("KIT-PHONE", "Accepted first article and actual M4 hardware", "Compare all three with the accepted article; reject blocked bores, stringing or face defects. Label installed pair and spare pair across 05A/05B inventory.", "phone_tpu_batch_postprint_pass"),
    "05C": ("KIT-TOOL-KB", "Actual 6 mm rod and pull gauge", "Inspect bore entry, 8.5 mm seating witness and face. Record seating and axial pull force on the real rod; retain as first article.", "keyboard_tpu_retention_coupon_pass"),
    "05D": ("KIT-TOOL-KB", "Accepted first article and actual 6 mm rod", "Compare all three with the accepted article; reject blocked bores or face defects. Label installed parts and spares.", "keyboard_tpu_batch_postprint_pass"),
    "06": ("KIT-MAST", "Actual 2020 extrusion, M5 nuts/bolts/washers, calipers", "Measure extrusion X/Y at multiple points; record the 20 mm-engagement socket, horizontal nut trap, free-passing M5 bore and washer seat using the exact ASA lot.", "asa_mast_socket_coupon_pass; asa_m5_nut_coupon_pass; asa_m5_clearance_coupon_pass"),
    "07A": ("KIT-MAST", "One extrusion, two M5 clamp bolts/nuts, four base fasteners/washers", "Inspect layer bonding, flatness, socket, rear slit, lead-ins and rear-lug bolt path. Tighten bolts alternately; record grip, cracks and flatness immediately and after 24 hours.", "mast_foot_first_article_pass"),
    "07B": ("KIT-MAST", "Accepted first foot, second extrusion/foot hardware and crossbar", "Repeat 07A checks, label feet A/B, assemble the pair, then verify matched seating, crossbar level, plumb witness lines and stand stability.", "mast_second_foot_postprint_pass; mast_pair_installation_pass"),
}


def fmt_values(value: object) -> str:
    if not value:
        return "-"
    return "`" + json.dumps(value, sort_keys=True, separators=(", ", ": ")) + "`"


def card_markdown(job: dict, profiles: dict, gates: dict, build: dict, revision: str) -> tuple[str, dict]:
    job_id = job["job_id"]
    sidecar_path = PLATES / Path(job["plate_file"]).with_suffix(".print.json")
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    profile = profiles["process_profiles"][job["profile"]]
    kit, hardware, inspection, releases = DETAILS[job_id]
    build_row = build.get(job_id, {})
    lines = [
        f"# Job {job_id} - {job['purpose']}", "",
        "| Control field | Released value |", "|---|---|",
        f"| Design revision | `{revision}` |",
        f"| Lifecycle state | **{build_row.get('current_state', 'UNRELEASED')}** |",
        f"| Route / stage | `{job['selection']}` / `{job['stage']}` |",
        f"| Kit | `{kit}` |",
        f"| Plate | `{job['plate_file']}` |",
        f"| Plate SHA-256 | `{sidecar['plate_sha256']}` |",
        f"| Profile | `{job['profile']}` / `{sidecar['process_profile_sha256']}` |",
        f"| Printer | QIDI Plus4; 305 x 305 x 280 mm nominal; 5 mm protected edge margin |",
        f"| Material / nozzle / layer | {profile['material']} / {profile['nozzle_mm']:.1f} mm / {profile['layer_height_mm']:.2f} mm |",
        f"| Plate envelope | {' x '.join(str(v) for v in sidecar['plate_envelope_mm'])} mm; centered |",
        "| Native slice record | QIDI Studio version, sliced mass and time: ____________________ |",
        "", "## Objects and orientation", "",
        "| STL | Qty | Locked orientation | Source SHA-256 |", "|---|---:|---|---|",
    ]
    for filename, qty in job["parts"].items():
        lines.append(
            f"| `{filename}` | {qty} | {ORIENTATION[filename]} | "
            f"`{sidecar['source_stl_sha256'][filename]}` |"
        )
    lines += [
        "", "## Required gates", "",
        "| Gate | Status | Recorded values |", "|---|---|---|",
    ]
    for gate_id in job["prerequisites"]:
        gate = gates[gate_id]
        lines.append(f"| `{gate_id}` | **{gate['status']}** | {fmt_values(gate.get('recorded_values'))} |")
    lines += [
        "", "## Preflight and native QIDI Studio review", "",
        f"- Hardware, samples and tools: {hardware}.",
        "- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.",
        "- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.",
        f"- Apply `{job['profile']}`: {profile['walls']} walls, {profile['top_layers']} top / {profile['bottom_layers']} bottom layers, {profile['infill_percent']}% {profile['infill_pattern']} infill.",
        f"- Supports: {profile['supports']}. Bed adhesion: {profile['bed_adhesion']}.",
        f"- Dimensional controls: {profile['dimensional_controls']}.",
        "- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.",
        "- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.",
        "", "## Post-print inspection and released evidence", "",
        f"- {inspection}",
        "- Cool to room temperature before dimensional or flatness measurements. Confirm part count, engraved identity and revision before cleanup.",
        "- Quarantine any warped, cracked, delaminated, under-extruded, bridged-shut or untraceable part; do not silently rework a critical fit.",
        f"- Intended gate(s) after objective acceptance: `{releases.replace('; ', '`, `')}`.",
        "", "## Signoff", "",
        "| Record | Entry |", "|---|---|",
        "| Spool brand / lot / dry record | ______________________________ |",
        "| QIDI Studio project / version | ______________________________ |",
        "| Printed date / operator | ______________________________ |",
        "| Measured values / tool ID | ______________________________ |",
        "| Evidence folder / photo IDs | ______________________________ |",
        "| Result | [ ] PASS  [ ] REWORK  [ ] QUARANTINE |",
        "| Inspector / date | ______________________________ |",
    ]
    record = {
        "job_id": job_id,
        "design_revision": revision,
        "lifecycle_status": build_row.get("current_state", "UNRELEASED"),
        "kit": kit,
        "plate_file": job["plate_file"],
        "plate_sha256": sidecar["plate_sha256"],
        "profile": job["profile"],
        "profile_sha256": sidecar["process_profile_sha256"],
        "parts": job["parts"],
        "prerequisites": job["prerequisites"],
        "postconditions": [item.strip() for item in releases.split(";")],
    }
    return "\n".join(lines) + "\n", record


def main() -> None:
    jobs_doc = json.loads((CONFIG / "print_jobs.json").read_text(encoding="utf-8"))
    profiles = json.loads((CONFIG / "print_profiles.json").read_text(encoding="utf-8"))
    measurement = json.loads((CONFIG / "measurement_record.json").read_text(encoding="utf-8"))
    build_path = CONFIG / "job_build_record.json"
    build_doc = json.loads(build_path.read_text(encoding="utf-8")) if build_path.exists() else {"jobs": []}
    build = {row["job_id"]: row for row in build_doc.get("jobs", [])}
    kit_rows = list(csv.DictReader((ROOT / "JOB_KITS.csv").open(encoding="utf-8")))
    kit_map = {row["job_id"]: row["kit_id"] for row in kit_rows}
    jobs = jobs_doc["jobs"]
    ids = {job["job_id"] for job in jobs}
    if ids != set(DETAILS):
        raise ValueError(f"Job-card details mismatch; missing={ids-set(DETAILS)}, extra={set(DETAILS)-ids}")
    if ids != set(kit_map) or ids != set(build):
        raise ValueError("Job IDs disagree between print jobs, JOB_KITS.csv and job_build_record.json")
    for job_id in ids:
        if DETAILS[job_id][0] != kit_map[job_id] or build[job_id]["kit_id"] != kit_map[job_id]:
            raise ValueError(f"Kit mapping drift for {job_id}")
    missing_orientations = {
        filename for job in jobs for filename in job["parts"] if filename not in ORIENTATION
    }
    if missing_orientations:
        raise ValueError(f"Missing orientation guidance: {sorted(missing_orientations)}")
    all_postconditions = {
        item.strip()
        for job_id in DETAILS
        for item in DETAILS[job_id][3].split(";")
    }
    unknown_postconditions = all_postconditions - set(measurement["gates"])
    if unknown_postconditions:
        raise ValueError(f"Unknown job-card postcondition gates: {sorted(unknown_postconditions)}")

    OUT.mkdir(exist_ok=True)
    expected: set[Path] = set()
    combined = [
        "# RoCell RC02-PRO-R1 - controlled print job cards", "",
        "These travelers are generated from the authoritative job, profile, gate, lifecycle and 3MF sidecar records. Complete one card per physical plate. Never infer release from a filename: the prerequisite table and lifecycle state control the work.", "",
        f"Generated coverage: **{len(jobs)} jobs** on the QIDI Plus4.", "",
    ]
    records = []
    for job in jobs:
        markdown, record = card_markdown(
            job, profiles, measurement["gates"], build, jobs_doc["design_revision"]
        )
        path = OUT / f"JOB-{job['job_id']}.md"
        path.write_text(markdown, encoding="utf-8")
        expected.add(path)
        combined += [markdown, ""]
        records.append(record)
    for stale in OUT.glob("JOB-*.md"):
        if stale not in expected:
            stale.unlink()
    (ROOT / "JOB_CARDS.md").write_text("\n".join(combined), encoding="utf-8")
    (ROOT / "JOB_CARDS.json").write_text(
        json.dumps({"schema_version": 1, "design_revision": jobs_doc["design_revision"], "jobs": records}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Generated {len(records)} controlled job cards")


if __name__ == "__main__":
    main()

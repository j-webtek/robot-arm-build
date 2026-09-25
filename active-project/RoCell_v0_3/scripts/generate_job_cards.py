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
    "keyboard_station_left.stl": "Flat, exported base on bed; RC03-L/master and locator labels readable on top",
    "keyboard_station_right.stl": "Flat, exported base on bed; RC03-R/slave and seam-reference labels readable on top",
    "keyboard_rear_clamp.stl": "Flat base on bed; padded face upright",
    "phone_tcp_station.stl": "Flat base on bed; RC03 PHONE+TCP and TCP R3 readable; USB toward plate front and TOP toward plate rear",
    "phone_clamp_rail.stl": "Flat station-facing ledge on bed; clamp towers upward",
    "tag_application_frame_55mm.stl": "Flat as exported; 55 mm DIRECT and +Y/REAR marks plus center notches upward",
    "station_locator_fit_gauge.stl": "Flat as exported; raised BOARD-R/BOARD-S/SEAM-R/SEAM-S labels upward",
    "m4_captive_nut_fit_gauge.stl": "Flat as exported; top-loaded horizontal nut-channel labels upward",
    "phone_clamp_tip_TPU_M4.stl": "Upright, flared bore entry on bed",
    "phone_width_fit_test.stl": "Flat as exported",
    "keyboard_corner_fit_test.stl": "Flat as exported",
    "hardware_fit_gauge.stl": "Flat as exported; raised D3.2 through D5.7 labels upward",
    "m4_washer_fit_gauge.stl": "Flat as exported; raised OD8.8/OD9.2/OD9.6 labels upward",
    "m3_head_fit_gauge.stl": "Flat as exported; H5.8/H6.2/H6.6 labels upward",
    "phone_m3_insert_fit_gauge.stl": "Flat as exported; PHONE label and insert mouths upward",
    "tool_m3_insert_fit_gauge.stl": "Flat as exported; TOOL label and insert mouths upward",
    "m5_nut_trap_fit_gauge.stl": "Tall block as exported; production-axis traps horizontal",
    "setup_hardware_fit_gauge.stl": "Flat as exported; all labels upward",
    "cable_tie_saddle_fit_gauge.stl": "Flat as exported; saddles upward",
    "mast_socket_fit_test.stl": "Flat as exported; 20 mm socket engagement vertical",
    "tpu_tip_retention_gauge.stl": "Flat base on bed; both rigid pegs upward",
    "camera_plate_universal.stl": "Flat as exported; CAM/MAST labels upward",
    "calibration_puck.stl": "Flat as exported; crosshair upward; ironing off",
    "compliant_tool_body.stl": "Upright on lower end with specified brim",
    "compliant_tool_top_cap.stl": "Flat, underside on bed; UP visible after print",
    "compliant_tool_grip_fit_test.stl": "Upright as exported; full 28 mm grip face vertical",
    "spring_fit_gauge.stl": "Flat as exported; stepped cup upward",
    "stylus_collar_9mm.stl": "Flat flange on bed; split and measured sliding bore open",
    "rod_bushing_6_to_9mm.stl": "Upright on flange with 8 mm brim",
    "keyboard_tip_TPU_6mm.stl": "Upright, flared bore entry on bed",
    "stylus_diameter_gauge.stl": "Flat as exported; labels upward",
    "mast_foot_2020.stl": "Flat 92 x 92 mm base on bed; socket vertical",
}


DETAILS = {
    "00A": ("KIT-CAL", "Actual keyboard, 6 mm dowel pins, M4 screws/washers, calipers", "Inspect every production-axis round hole and radial slot. Select the smallest hand-serviceable 6 mm board locator pair, cycle the pins 20 times, verify keyboard corner clearance only, and record accepted clearance/washer choices. Retain the seam round/radial section for use with the actual master posts after job 01.", "keyboard_corner_coupon_pass; keyboard_station_registration_coupon_pass; tray_clearance_holes_coupon_pass"),
    "00B": ("KIT-CAL", "Actual phone/case, 6 mm dowel pins, M4 hardware, M3 inserts, washers, USB cable and selected wider tie", "Record the phone hand-fit, independent service-station round socket and radial-slot width, PHONE-labeled M3 insert gauge with its production 0.3 mm floor, and smallest flat-seating M4 washer recess. Retain the failed nut and cable-saddle objects as superseded screening evidence; they do not qualify the redesigned production rail.", "phone_width_coupon_pass; phone_station_registration_coupon_pass; phone_station_m3_insert_coupon_pass; cradle_m4_washer_coupon_pass"),
    "00C": ("KIT-CAL", "RoArm gripper, actual spring, M3 inserts/screws, calipers", "Verify the full 28 mm grip interface; record no slip/crush; record spring OD/ID/free length and both seat fits; install-test each production-edge-representative M3 pocket and select the smallest below-flush M3 head recess.", "gripper_coupon_pass; spring_fit_coupon_pass; compliant_tool_m3_insert_coupon_pass; precision_m3_head_coupon_pass"),
    "00D": ("KIT-CAL", "Measured stylus, selected removable retaining compound if needed, calipers", "Select the smallest free-sliding stylus bore. Document dry-fit retention or the minimal plastics-compatible removable compound; final thin-collar pull/cycle testing remains mandatory.", "stylus_gauge_coupon_pass; adapter_retention_method_selected"),
    "00E": ("KIT-CAL", "M3/M4/M5 screws, washers, 1/4-20 hardware, TPU tip samples", "Record general clearances, screw-head and washer seats, camera hex choice, and rigid-peg preliminary fit. Do not use the rigid peg alone to release TPU production.", "general_clearance_holes_coupon_pass; setup_hardware_coupon_pass"),
    "00F": ("KIT-CAL", "Actual M3 x 10 mm button-head puck screw and measuring tools", "Use the exact 0.16 mm calibration profile. Measure the actual M3 screw shank and head, record the smallest freely passing 3.2/3.4/3.6 mm M3 option, and select the smallest H5.8/H6.2/H6.6 recess in which the button head seats below the surrounding face without forcing. Retain and label this coupon separately from 00C/00E.", "calibration_clearance_holes_coupon_pass"),
    "01": ("KIT-KB", "Flatness surface, retained job 00A seam ladder, 6 mm production pins, three temporary/production M4 station screws and washers, calipers", "Cool fully; inspect master round/slot sockets, the continuous board-contact underside at all three retention zones, seam posts and clamp track. Measure the printed seam posts; independently select the smallest tool-free round-socket diameter and radial-slot width on the retained job 00A ladder; reject cracks, whitening, rocking, or lifted corners.", "keyboard_left_first_article_pass; keyboard_seam_coupon_pass"),
    "02": ("KIT-KB", "Accepted left station, keyboard, three temporary/production M4 station screws and washers, seam keys", "Repeat first-article checks; mate the slave to the accepted master without an independent pin pair; record seam gap, flushness, support plane, continuous base contact and rocking. Complete ten station removal/reinstall cycles after board installation.", "keyboard_station_pair_postprint_pass; station_remove_reinstall_repeatability_pass; keyboard_fixture_assembly_pass"),
    "03A": ("KIT-PHONE", "Phone/case, cable, two 6 mm pins, three M4 station screws/washers, M3 inserts, accepted rail and TPU tips", "With the station off the wood board, inspect continuous base contact at all three retention zones, locator sockets, keyed TCP receiver, fixed phone datums, replaceable-rail interface and all keepouts; install the TCP inserts square. For final mounting, seat the accepted rail before the two shared rail/station screws and verify its cable saddle with the actual cable. Complete ten station and phone cycles without button or cable contact.", "phone_tcp_station_postprint_pass; station_remove_reinstall_repeatability_pass; phone_fixture_assembly_pass"),
    "03B": ("KIT-KB", "Keyboard, two face pads, two M4 low-profile thumb screws", "Verify both guided sliders match, bases are flat, runners intact, scales readable, and slots open. Pad faces; tighten only to contact and run keyboard repeatability testing.", "keyboard_clamps_postprint_pass; keyboard_fixture_assembly_pass"),
    "03C1": ("KIT-PHONE", "Actual phone, USB cable, nominal 4.8 mm project tie, two standard M4 hex nuts and M4 clamp screws; accepted station and TPU tips only for the later seating stage", "First bench-qualify both redesigned 7.2 mm lower-half hex seats: each screw must catch at least three full turns and neither nut may spin through 20 cycles. Feed the project tie around the actual cable through the 5.6 x 2.2 mm saddle and confirm no cracking. After Job 03A exists, inspect rail seating, tower ligaments, clamp-axis keepouts and service replacement.", "phone_m4_captive_nut_coupon_pass; cable_tie_saddle_coupon_pass; phone_clamp_rail_first_article_pass; phone_fixture_assembly_pass"),
    "03C2": ("KIT-BOARD-SETUP", "1:1 board setup template, six direct adhesive tags, steel rule and calipers", "Verify the 55 mm application opening, center and +Y witness marks, flatness, and finger access. Prove the 100 mm template scale before installing any direct tag.", "tag_application_tool_postprint_pass"),
    "03C3": ("KIT-VISION-CAM", "Actual fallback camera, 1/4-20 screw, two M5 screws/T-nuts/washers, straps", "FIXED-MAST FALLBACK ONLY: do not treat this plate as an arm-camera adapter. Keep the job on hold until the camera architecture revision explicitly releases the fallback. Then measure camera thread direction, screw/head dimensions and safe engagement; check M5 ligaments, scales, strap slots, cable direction and no screw bottoming.", "camera_plate_hardware_pass"),
    "03D": ("KIT-PUCK", "Accepted phone/TCP station, two M3 screws, straightedge and depth/height gauge", "Keep slicer object calibration_puck_1 as 03D-A and calibration_puck_2 as 03D-B. Qualify each separately; both must have an intact crosshair/divot, no more than 0.15 mm lateral play, and no more than 0.10 mm mounted-height range over ten cycles. For each, calculate score = max(play / 0.15, height range / 0.10). Label the lower-score cartridge INSTALL; if tied at measuring resolution, choose the lower height range, then 03D-A. Label the other accepted cartridge SPARE - TCP RECALIBRATION REQUIRED.", "calibration_puck_datum_pass"),
    "04A": ("KIT-TOOL-COMMON", "Two M3 inserts, two M3x10 screws, accepted spring, route adapter", "Inspect body straightness, grip flats, guide bore, spring chamber and keyed locator. Install inserts square; cap must seat only in the keyed orientation. Verify 3-6 mm smooth return after route assembly.", "tool_body_postprint_pass; tool_assembled_motion_pass"),
    "04B": ("KIT-TOOL-PHONE", "Measured stylus, qualified removable compound only if dry fit is insufficient, pull gauge", "Check bore and split. Set projection, quantify dry-fit or minimal-compound pull retention and repeat cycles, prove removability, then inspect after 24-hour creep and verify capacitive function.", "stylus_collar_retention_pass; stylus_function_pass"),
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
    contract = sidecar["preset_contract"]
    filament = profiles["filament_presets"][contract["filament_preset_name"]]
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
        f"| Exact settings sheet | `print_plates_3mf/{contract['human_settings_file']}` / `{contract['human_settings_sha256']}` |",
        f"| QIDI process import | `{contract['qidi_process_profile_file']}` / `{contract['qidi_process_profile_sha256']}` |",
        f"| Filament preset | `{contract['filament_preset_name']}` / `{contract['filament_preset_sha256']}` |",
        f"| Preset completeness | **{contract['preset_data_status']}** |",
        f"| Unresolved filament fields | {', '.join(contract['unresolved_fields']) or 'None'} |",
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
        f"- Open `print_plates_3mf/{contract['human_settings_file']}` and follow every exact value in it.",
        f"- Import `{contract['qidi_process_profile_file']}` and select `{filament.get('qidi_studio_preset', filament.get('suggested_starting_preset', 'the exact qualified physical-spool preset'))}` as the separate filament preset.",
        "- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.",
        "- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.",
        f"- Apply `{job['profile']}`: {profile['walls']} walls, {profile['top_layers']} top / {profile['bottom_layers']} bottom layers, {profile['infill_percent']}% {profile['infill_pattern']} infill.",
        f"- Supports: {profile['supports']}. Bed adhesion: {profile['bed_adhesion']}.",
        f"- Dimensional controls: {profile['dimensional_controls']}.",
        "- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.",
        "- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.",
        "", "## Post-print inspection and released evidence", "",
        f"- {inspection}",
        "- Cool to room temperature before dimensional or flatness measurements. Confirm part count, modeled identity and revision before cleanup.",
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
        "filament_preset": contract["filament_preset_name"],
        "filament_preset_sha256": contract["filament_preset_sha256"],
        "preset_data_status": contract["preset_data_status"],
        "settings_file": f"print_plates_3mf/{contract['human_settings_file']}",
        "settings_sha256": contract["human_settings_sha256"],
        "qidi_process_profile_file": contract["qidi_process_profile_file"],
        "qidi_process_profile_sha256": contract["qidi_process_profile_sha256"],
        "resolved_preset_sha256": contract["resolved_preset_sha256"],
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
        f"# RoCell {jobs_doc['design_revision']} - controlled print job cards", "",
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

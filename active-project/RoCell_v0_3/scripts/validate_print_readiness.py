#!/usr/bin/env python3
"""Validate release evidence and generate the authoritative print queue."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config"
PLATES = ROOT / "print_plates_3mf"
FASTENER_MAP_PATH = ROOT / "FASTENER_MAP.csv"
WORKCELL_LAYOUT_PATH = CONFIG / "workcell_layout.json"
BOARD_DRILL_GUIDE_PATHS = {
    "output/pdf/RC03_BOARD_DRILL_GUIDE_LETTER_1TO1.pdf": (
        ROOT / "output" / "pdf" / "RC03_BOARD_DRILL_GUIDE_LETTER_1TO1.pdf"
    ),
    "output/pdf/RC03_BOARD_DRILL_GUIDE_24X36_FULL_SIZE_1TO1.pdf": (
        ROOT / "output" / "pdf" / "RC03_BOARD_DRILL_GUIDE_24X36_FULL_SIZE_1TO1.pdf"
    ),
}
CAMERA_ARCHITECTURE_DECISION_PATH = CONFIG / "camera_architecture_decision.json"
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
BOARD_LOCAL_FLATNESS_LIMIT_MM = 0.50
BOARD_OVERALL_BOW_LIMIT_MM = 1.50
BOARD_MINIMUM_BLIND_BORE_FLOOR_MM = 2.0
BOARD_WIDTH_NOMINAL_MM = 610.0
BOARD_DEPTH_NOMINAL_MM = 457.0
BOARD_EDGE_LENGTH_TOLERANCE_MM = 0.50
BOARD_OPPOSITE_EDGE_DIFFERENCE_LIMIT_MM = 0.50
BOARD_THICKNESS_MIN_MM = 17.50
BOARD_THICKNESS_MAX_MM = 18.50
BOARD_DIAGONAL_TOLERANCE_MM = 1.00
BOARD_DIAGONAL_DIFFERENCE_LIMIT_MM = 1.00
BOARD_LOCATOR_BORE_DEPTH_NOMINAL_MM = 15.0
BOARD_LOCATOR_BORE_DEPTH_TOLERANCE_MM = 0.20
BOARD_LOCATOR_PROJECTION_NOMINAL_MM = 5.0
BOARD_LOCATOR_PROJECTION_TOLERANCE_MM = 0.15
BOARD_LOCATOR_IDS = (
    "KBL-LOC-ROUND",
    "KBL-LOC-RADIAL",
    "PT-LOC-ROUND",
    "PT-LOC-RADIAL",
)
TOOL_ROUTE_IDS = ("keyboard_rod_route", "phone_stylus_route")
GEOMETRY_PARAMETER_MAP = (
    ("compliant_tool_m3_insert_coupon_pass", "selected_pocket_mm", "compliant_tool_m3_insert_pocket_d"),
    ("keyboard_station_registration_coupon_pass", "selected_round_socket_mm", "keyboard_locator_socket_d"),
    ("keyboard_station_registration_coupon_pass", "selected_radial_slot_width_mm", "keyboard_locator_slot_w"),
    ("phone_station_registration_coupon_pass", "selected_round_socket_mm", "phone_locator_socket_d"),
    ("phone_station_registration_coupon_pass", "selected_radial_slot_width_mm", "phone_locator_slot_w"),
    ("keyboard_seam_coupon_pass", "selected_round_socket_mm", "seam_round_socket_d"),
    ("keyboard_seam_coupon_pass", "selected_radial_slot_width_mm", "seam_radial_slot_w"),
    ("phone_m4_captive_nut_coupon_pass", "selected_channel_across_flats_mm", "phone_m4_nut_ac"),
    ("phone_station_m3_insert_coupon_pass", "selected_pocket_mm", "phone_station_m3_insert_pocket_d"),
    ("setup_hardware_coupon_pass", "m3_head_recess_d_mm", "m3_head_recess_d"),
    ("setup_hardware_coupon_pass", "m4_washer_od_mm", "m4_washer_od"),
    ("setup_hardware_coupon_pass", "m5_washer_od_mm", "m5_washer_od"),
    ("setup_hardware_coupon_pass", "camera_hex_ac_mm", "camera_hex_ac"),
    ("tray_clearance_holes_coupon_pass", "m4_washer_od_mm", "m4_washer_od"),
    ("calibration_clearance_holes_coupon_pass", "smallest_free_hole_mm", "m3_clearance"),
    ("calibration_clearance_holes_coupon_pass", "m3_head_recess_d_mm", "m3_head_recess_d"),
    ("cradle_m4_washer_coupon_pass", "m4_washer_od_mm", "m4_washer_od"),
    ("precision_m3_head_coupon_pass", "m3_head_recess_d_mm", "m3_head_recess_d"),
    ("cable_tie_saddle_coupon_pass", "selected_slot_width_mm", "zip_tie_slot_w"),
    ("cable_tie_saddle_coupon_pass", "selected_tunnel_height_mm", "zip_tie_tunnel_h"),
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


def _finite_number(value: Any, label: str, *, positive: bool = True) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a JSON number, not {value!r}")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{label} must be finite")
    if positive and number <= 0:
        raise ValueError(f"{label} must be greater than zero")
    if not positive and number < 0:
        raise ValueError(f"{label} must be zero or greater")
    return number


def _integer_at_least(value: Any, minimum: int, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be an integer")
    if value < minimum:
        raise ValueError(f"{label} must be at least {minimum}")
    return value


def _require_gate_pass(gates: dict[str, Any], gate_id: str, dependent: str) -> dict[str, Any]:
    gate = gates[gate_id]
    if gate.get("status") != "PASS":
        raise ValueError(f"{dependent} cannot PASS until {gate_id} is PASS")
    return gate["recorded_values"]


def _same_number(actual: Any, expected: Any, label: str) -> float:
    actual_number = _finite_number(actual, label)
    expected_number = _finite_number(expected, f"approved {label}")
    if not math.isclose(actual_number, expected_number, rel_tol=0.0, abs_tol=1e-9):
        raise ValueError(
            f"{label}={actual_number} does not match approved value {expected_number}"
        )
    return actual_number


def _require_exact_keys(value: Any, expected: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    actual = set(value)
    if actual != expected:
        raise ValueError(
            f"{label} fields must be exactly {sorted(expected)}; received {sorted(actual)}"
        )
    return value


def _bound_project_file(values: dict[str, Any], path_key: str, hash_key: str, label: str) -> tuple[str, str]:
    relative_value = values.get(path_key)
    digest = values.get(hash_key)
    if not isinstance(relative_value, str) or not relative_value.strip():
        raise ValueError(f"{label} {path_key} must be a nonblank project-relative path")
    relative = Path(relative_value)
    if relative.is_absolute() or relative.drive or relative.root:
        raise ValueError(f"{label} {path_key} must be project-relative")
    try:
        root = ROOT.resolve()
        resolved = (ROOT / relative).resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise ValueError(f"{label} {path_key} does not resolve to an existing project file") from exc
    if not resolved.is_file():
        raise ValueError(f"{label} {path_key} must resolve to a file")
    if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise ValueError(f"{label} {hash_key} is missing or malformed")
    actual = hashlib.sha256(resolved.read_bytes()).hexdigest()
    if digest != actual:
        raise ValueError(f"{label} {hash_key} is stale for {relative.as_posix()}")
    return relative.as_posix(), digest


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


def validate_calibration_cartridge_gate(record: dict[str, Any]) -> None:
    """Require two separately qualified cartridges and deterministic INSTALL selection."""
    gate = record["gates"]["calibration_puck_datum_pass"]
    if gate["status"] != "PASS":
        return

    values = gate["recorded_values"]
    if values.get("job_id") != "03D" or values.get("cartridge_count") != 2:
        raise ValueError("calibration_puck_datum_pass must identify Job 03D and exactly two cartridges")

    scores: dict[str, float] = {}
    height_ranges: dict[str, float] = {}
    for label in ("A", "B"):
        prefix = f"cartridge_{label}_"
        if values.get(prefix + "crosshair_result") != "PASS":
            raise ValueError(f"03D-{label} crosshair_result must be PASS")
        if values.get(prefix + "divot_result") != "PASS":
            raise ValueError(f"03D-{label} divot_result must be PASS")
        _finite_number(
            values.get(prefix + "free_state_flatness_mm"),
            f"03D-{label} free-state flatness mm",
            positive=False,
        )
        play = _finite_number(
            values.get(prefix + "lateral_play_mm"),
            f"03D-{label} lateral play mm",
            positive=False,
        )
        if play > 0.15:
            raise ValueError(f"03D-{label} lateral play exceeds 0.15 mm")
        cycles = _integer_at_least(
            values.get(prefix + "remove_reinstall_cycles"),
            10,
            f"03D-{label} remove/reinstall cycles",
        )
        measurements = values.get(prefix + "mounted_height_measurements_mm")
        if not isinstance(measurements, list) or len(measurements) != cycles:
            raise ValueError(
                f"03D-{label} mounted-height table must contain one value for each recorded cycle"
            )
        measured_heights = [
            _finite_number(item, f"03D-{label} mounted height {index + 1}")
            for index, item in enumerate(measurements)
        ]
        measured_range = max(measured_heights) - min(measured_heights)
        reported_range = _finite_number(
            values.get(prefix + "mounted_height_range_mm"),
            f"03D-{label} mounted-height range mm",
            positive=False,
        )
        if not math.isclose(reported_range, measured_range, rel_tol=0.0, abs_tol=0.0051):
            raise ValueError(f"03D-{label} mounted-height range does not match its measurement table")
        if measured_range > 0.1001:
            raise ValueError(f"03D-{label} mounted-height range exceeds 0.10 mm")
        reported_mean = _finite_number(
            values.get(prefix + "mean_mounted_height_mm"),
            f"03D-{label} mean mounted height mm",
        )
        measured_mean = sum(measured_heights) / len(measured_heights)
        if not math.isclose(reported_mean, measured_mean, rel_tol=0.0, abs_tol=0.0051):
            raise ValueError(f"03D-{label} mean mounted height does not match its measurement table")
        height_ranges[label] = reported_range
        scores[label] = max(play / 0.15, reported_range / 0.10)

    if scores["A"] < scores["B"]:
        expected_install = "A"
    elif scores["B"] < scores["A"]:
        expected_install = "B"
    elif height_ranges["A"] <= height_ranges["B"]:
        expected_install = "A"
    else:
        expected_install = "B"
    expected_spare = "B" if expected_install == "A" else "A"
    if values.get("installed_cartridge_id") != f"03D-{expected_install}":
        raise ValueError("calibration cartridge INSTALL label does not follow the controlled selection rule")
    if values.get("spare_cartridge_id") != f"03D-{expected_spare}":
        raise ValueError("calibration cartridge SPARE label must identify the other accepted cartridge")
    recorded_score = _finite_number(
        values.get("installed_selection_score"),
        "installed calibration-cartridge selection score",
        positive=False,
    )
    if not math.isclose(recorded_score, scores[expected_install], rel_tol=0.0, abs_tol=0.0011):
        raise ValueError("installed calibration-cartridge selection score is inconsistent")
    if values.get("accepted_spare_result") != "PASS":
        raise ValueError("calibration cartridge accepted_spare_result must be PASS")
    if values.get("spare_swap_requires_tcp_recalibration") is not True:
        raise ValueError("the calibration-cartridge spare must require TCP recalibration after a swap")


def _file_sha256(path: Path, label: str) -> str:
    if not path.is_file():
        raise ValueError(f"{label} does not exist: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _project_file(relative_value: Any, label: str) -> Path:
    if not isinstance(relative_value, str) or not relative_value.strip():
        raise ValueError(f"{label} must be a nonblank project-relative path")
    relative = Path(relative_value)
    if relative.is_absolute() or relative.drive or relative.root:
        raise ValueError(f"{label} must be project-relative")
    try:
        root = ROOT.resolve()
        resolved = (ROOT / relative).resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise ValueError(f"{label} does not resolve to a contained project file") from exc
    if not resolved.is_file():
        raise ValueError(f"{label} must resolve to a file")
    return resolved


def validate_profile_gate_bindings(
    record: dict[str, Any],
    jobs_config: dict[str, Any],
    profiles: dict[str, Any],
) -> None:
    """A PASS material gate must bind to the exact current process profile."""
    process_profiles = profiles["process_profiles"]
    gates = record["gates"]
    for job in jobs_config["jobs"]:
        profile_name = job["profile"]
        profile = process_profiles[profile_name]
        profile_gate_ids = [
            gate_id for gate_id in job["prerequisites"]
            if "profile_calibrated" in gate_id
        ]
        if len(profile_gate_ids) != 1:
            raise ValueError(
                f"job {job['job_id']} must have exactly one profile-calibration gate"
            )
        gate_id = profile_gate_ids[0]
        gate = gates[gate_id]
        scope = gate["scope"]
        if scope.get("process_profile") != profile_name:
            raise ValueError(
                f"{gate_id} scope profile does not match job {job['job_id']} profile"
            )
        if scope.get("material") != profile["material"]:
            raise ValueError(
                f"{gate_id} material does not match current profile {profile_name}"
            )
        if not math.isclose(
            _as_float(scope.get("nozzle_mm"), f"{gate_id} nozzle"),
            float(profile["nozzle_mm"]),
            rel_tol=0.0,
            abs_tol=1e-9,
        ):
            raise ValueError(f"{gate_id} nozzle does not match {profile_name}")
        if gate.get("status") != "PASS":
            continue
        values = gate["recorded_values"]
        recorded_hash = values.get("profile_sha256")
        if recorded_hash is None:
            revision = values.get("profile_revision", "")
            match = re.search(r"(?:SHA256\s+)?([0-9a-f]{64})\Z", str(revision))
            recorded_hash = match.group(1) if match else None
        expected_hash = _json_sha256(profile)
        if recorded_hash != expected_hash:
            raise ValueError(
                f"{gate_id} PASS is stale: recorded profile hash {recorded_hash!r} "
                f"does not match {profile_name} {expected_hash}"
            )


def validate_generated_print_control(
    job: dict[str, Any],
    profiles: dict[str, Any],
) -> dict[str, str]:
    """Validate one plate's readable and machine-readable exact preset package."""
    plate = PLATES / job["plate_file"]
    sidecar_path = plate.with_suffix(".print.json")
    if not plate.is_file() or not sidecar_path.is_file():
        raise FileNotFoundError(f"Missing 3MF or settings sidecar for job {job['job_id']}")
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    if sidecar.get("schema_version") != 2:
        raise ValueError(f"job {job['job_id']} sidecar schema must remain version 2")
    if sidecar.get("job_id") != job["job_id"] or sidecar.get("plate_file") != plate.name:
        raise ValueError(f"job {job['job_id']} sidecar identity mismatch")

    profile_name = job["profile"]
    profile = profiles["process_profiles"][profile_name]
    profile_hash = _json_sha256(profile)
    if sidecar.get("process_profile_name") != profile_name:
        raise ValueError(f"job {job['job_id']} sidecar process-profile name mismatch")
    if sidecar.get("process_profile") != profile:
        raise ValueError(f"job {job['job_id']} sidecar embeds a stale process profile")
    if sidecar.get("process_profile_sha256") != profile_hash:
        raise ValueError(f"job {job['job_id']} process-profile hash is stale")
    if sidecar.get("plate_sha256") != _file_sha256(plate, f"job {job['job_id']} plate"):
        raise ValueError(f"job {job['job_id']} plate hash is stale")

    contract = sidecar.get("preset_contract")
    if not isinstance(contract, dict) or contract.get("schema_version") != 1:
        raise ValueError(f"job {job['job_id']} lacks preset_contract schema 1")
    required_contract_keys = {
        "schema_version", "slicer", "preset_data_status",
        "filament_preset_name", "filament_preset", "process_preset_name",
        "process_preset", "human_settings_file", "human_settings_sha256",
        "qidi_process_profile_file", "qidi_process_profile_sha256",
        "filament_preset_sha256", "resolved_preset_sha256",
        "unresolved_fields", "part_assignments",
    }
    missing = sorted(required_contract_keys - set(contract))
    if missing:
        raise ValueError(f"job {job['job_id']} preset contract misses {missing}")
    if contract["slicer"] != profiles["slicer_contract"]:
        raise ValueError(f"job {job['job_id']} slicer contract is stale")
    if contract["process_preset_name"] != profile_name or contract["process_preset"] != profile:
        raise ValueError(f"job {job['job_id']} preset contract process is stale")
    if contract["preset_data_status"] != profile["preset_data_status"]:
        raise ValueError(f"job {job['job_id']} preset completeness is stale")

    filament_id = profile["filament_preset"]
    filament = profiles["filament_presets"][filament_id]
    filament_hash = _json_sha256(filament)
    if contract["filament_preset_name"] != filament_id or contract["filament_preset"] != filament:
        raise ValueError(f"job {job['job_id']} filament preset is stale")
    if contract["filament_preset_sha256"] != filament_hash:
        raise ValueError(f"job {job['job_id']} filament-preset hash is stale")
    if contract["unresolved_fields"] != filament.get("unresolved_fields", []):
        raise ValueError(f"job {job['job_id']} unresolved filament fields are stale")
    if filament.get("resolution_status") == "CONFIRMED_EXACT" and contract["unresolved_fields"]:
        raise ValueError(f"job {job['job_id']} exact filament preset cannot contain unresolved fields")

    expected_assignments = [
        {
            "stl": filename,
            "quantity": quantity,
            "filament_preset": filament_id,
            "process_preset": profile_name,
        }
        for filename, quantity in sorted(job["parts"].items())
    ]
    if contract["part_assignments"] != expected_assignments:
        raise ValueError(f"job {job['job_id']} part-to-preset assignments are stale")

    expected_settings_name = f"{plate.stem}.PRINT_SETTINGS.md"
    if contract["human_settings_file"] != expected_settings_name:
        raise ValueError(f"job {job['job_id']} readable settings filename is not paired to its plate")
    settings_path = plate.parent / expected_settings_name
    if contract["human_settings_sha256"] != _file_sha256(
        settings_path, f"job {job['job_id']} readable settings"
    ):
        raise ValueError(f"job {job['job_id']} readable settings hash is stale")

    process_path = _project_file(
        contract["qidi_process_profile_file"],
        f"job {job['job_id']} QIDI process profile",
    )
    expected_process_path = ROOT / "slicer_profiles" / "QIDI_PLUS4" / f"{profile_name}.process.json"
    if process_path != expected_process_path.resolve():
        raise ValueError(f"job {job['job_id']} QIDI process filename is not canonical")
    if contract["qidi_process_profile_sha256"] != _file_sha256(
        process_path, f"job {job['job_id']} QIDI process profile"
    ):
        raise ValueError(f"job {job['job_id']} QIDI process profile hash is stale")
    qidi = profile["qidi_studio"]
    expected_process = {
        "from": "User",
        "inherits": qidi["base_process_preset"],
        "name": qidi["import_name"],
        "print_settings_id": qidi["import_name"],
        "version": profiles["slicer_contract"]["verified_config_version"],
        "compatible_printers": [profiles["slicer_contract"]["machine_preset"]],
        **qidi["native_overrides"],
    }
    if json.loads(process_path.read_text(encoding="utf-8")) != expected_process:
        raise ValueError(f"job {job['job_id']} QIDI process profile contents are stale")

    resolved = {
        "design_revision": sidecar["design_revision"],
        "slicer": profiles["slicer_contract"],
        "printer": profiles["printer"],
        "filament_preset_name": filament_id,
        "filament_preset": filament,
        "process_preset_name": profile_name,
        "process_preset": profile,
        "qidi_process_profile_sha256": contract["qidi_process_profile_sha256"],
    }
    if contract["resolved_preset_sha256"] != _json_sha256(resolved):
        raise ValueError(f"job {job['job_id']} resolved-preset hash is stale")
    for key in (
        "filament_preset_sha256", "resolved_preset_sha256",
        "human_settings_file", "human_settings_sha256",
        "qidi_process_profile_file", "qidi_process_profile_sha256",
    ):
        if sidecar.get(key) != contract[key]:
            raise ValueError(f"job {job['job_id']} sidecar duplicate {key} is inconsistent")
    return {
        "settings_file": contract["human_settings_file"],
        "settings_sha256": contract["human_settings_sha256"],
        "qidi_process_profile_file": contract["qidi_process_profile_file"],
        "qidi_process_profile_sha256": contract["qidi_process_profile_sha256"],
        "filament_preset": filament_id,
        "preset_data_status": contract["preset_data_status"],
    }


def validate_board_setup_template_gate(record: dict[str, Any]) -> None:
    """Bind a measured print to one released guide and its exact source layout."""
    gate = record["gates"]["board_setup_template_scale_pass"]
    if gate["status"] != "PASS":
        return

    values = gate["recorded_values"]
    if values.get("template_revision") != record.get("design_revision"):
        raise ValueError(
            "board_setup_template_scale_pass template_revision must match the design revision"
        )

    selected = values.get("selected_guide_path")
    if selected not in BOARD_DRILL_GUIDE_PATHS:
        raise ValueError(
            "board_setup_template_scale_pass selected_guide_path must identify one released "
            "Letter or 24 x 36 drill guide"
        )
    guide_hash = values.get("selected_guide_sha256")
    if not isinstance(guide_hash, str) or re.fullmatch(r"[0-9a-f]{64}", guide_hash) is None:
        raise ValueError(
            "board_setup_template_scale_pass selected_guide_sha256 is missing or malformed"
        )
    if guide_hash != _file_sha256(BOARD_DRILL_GUIDE_PATHS[selected], "selected board drill guide"):
        raise ValueError(
            "board_setup_template_scale_pass selected_guide_sha256 is stale for the selected guide"
        )

    layout_hash = values.get("source_layout_sha256")
    if not isinstance(layout_hash, str) or re.fullmatch(r"[0-9a-f]{64}", layout_hash) is None:
        raise ValueError(
            "board_setup_template_scale_pass source_layout_sha256 is missing or malformed"
        )
    if layout_hash != _file_sha256(WORKCELL_LAYOUT_PATH, "source workcell layout"):
        raise ValueError(
            "board_setup_template_scale_pass source_layout_sha256 is stale for "
            "config/workcell_layout.json"
        )

    for axis in ("x", "y"):
        measured = _finite_number(
            values.get(f"{axis}_scale_bar_mm"),
            f"board setup template {axis.upper()} scale bar mm",
        )
        if not 99.8 <= measured <= 100.2:
            raise ValueError(
                f"board setup template {axis.upper()} scale bar must be 100.0 +/- 0.2 mm"
            )
    if values.get("page_scaling_setting") != "Actual Size / 100 percent":
        raise ValueError(
            "board_setup_template_scale_pass page_scaling_setting must be "
            "'Actual Size / 100 percent'"
        )
    if values.get("all_sheet_registration_marks_result") != "PASS":
        raise ValueError(
            "board_setup_template_scale_pass all_sheet_registration_marks_result must be PASS"
        )


def _csv_positive_number(value: Any, label: str) -> float:
    number = _as_float(value, label)
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{label} must be a finite number greater than zero")
    return number


def validate_selected_fastener_map(path: Path = FASTENER_MAP_PATH) -> None:
    """Reject a board release unless every retention point has an anchor-specific bore plan."""
    layout = json.loads(WORKCELL_LAYOUT_PATH.read_text(encoding="utf-8"))
    expected = {
        feature["id"]: feature
        for feature in layout["board_features"]
        if feature.get("type") == "m4_retention_through"
    }
    if len(expected) != 9:
        raise ValueError(
            "config/workcell_layout.json must define exactly nine M4 board-retention features"
        )

    required_columns = {
        "feature_id",
        "station",
        "world_x_mm",
        "world_y_mm",
        "selected_length_mm",
        "anchor_type",
        "anchor_manufacturer_part",
        "bore_mode",
        "final_board_bore_mm",
        "bore_depth_mm_or_through",
        "install_face",
        "pilot_diameter_mm",
        "qualification_reference",
        "acceptance",
    }
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fields = set(reader.fieldnames or ())
            missing = sorted(required_columns - fields)
            if missing:
                raise ValueError(f"FASTENER_MAP.csv is missing required columns: {missing}")
            rows = list(reader)
    except OSError as exc:
        raise ValueError(f"FASTENER_MAP.csv cannot be read: {path}") from exc

    ids = [str(row.get("feature_id", "")).strip() for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("FASTENER_MAP.csv contains duplicate feature_id rows")
    if set(ids) != set(expected):
        missing = sorted(set(expected) - set(ids))
        unexpected = sorted(set(ids) - set(expected))
        raise ValueError(
            "FASTENER_MAP.csv must contain exactly the nine released retention features; "
            f"missing={missing}, unexpected={unexpected}"
        )

    nonblank_fields = (
        "anchor_type",
        "anchor_manufacturer_part",
        "qualification_reference",
        "acceptance",
    )
    for row in rows:
        feature_id = str(row["feature_id"]).strip()
        feature = expected[feature_id]
        if row.get(None):
            raise ValueError(f"FASTENER_MAP.csv row {feature_id} has more values than columns")
        if str(row.get("station", "")).strip() != feature["station"]:
            raise ValueError(f"FASTENER_MAP.csv row {feature_id} station does not match the layout")
        for field, expected_value in (("world_x_mm", feature["x"]), ("world_y_mm", feature["y"])):
            actual = _csv_positive_number(row.get(field), f"FASTENER_MAP.csv {feature_id}.{field}")
            if not math.isclose(
                actual, float(expected_value), rel_tol=0.0, abs_tol=GEOMETRY_TOLERANCE_MM
            ):
                raise ValueError(
                    f"FASTENER_MAP.csv row {feature_id} {field} does not match the released layout"
                )

        _csv_positive_number(
            row.get("selected_length_mm"), f"FASTENER_MAP.csv {feature_id}.selected_length_mm"
        )
        for field in nonblank_fields:
            if not isinstance(row.get(field), str) or not row[field].strip():
                raise ValueError(f"FASTENER_MAP.csv {feature_id}.{field} must be nonblank")

        bore_mode = str(row.get("bore_mode", "")).strip().upper()
        if bore_mode not in {"THROUGH", "BLIND"}:
            raise ValueError(
                f"FASTENER_MAP.csv {feature_id}.bore_mode must be THROUGH or BLIND"
            )
        final_bore = _csv_positive_number(
            row.get("final_board_bore_mm"),
            f"FASTENER_MAP.csv {feature_id}.final_board_bore_mm",
        )
        pilot = _csv_positive_number(
            row.get("pilot_diameter_mm"),
            f"FASTENER_MAP.csv {feature_id}.pilot_diameter_mm",
        )
        if pilot > final_bore:
            raise ValueError(
                f"FASTENER_MAP.csv {feature_id}.pilot_diameter_mm cannot exceed the final bore"
            )
        bore_depth = str(row.get("bore_depth_mm_or_through", "")).strip()
        if bore_mode == "THROUGH":
            if bore_depth.upper() != "THROUGH":
                raise ValueError(
                    f"FASTENER_MAP.csv {feature_id}.bore_depth_mm_or_through must be THROUGH"
                )
        else:
            _csv_positive_number(
                bore_depth, f"FASTENER_MAP.csv {feature_id}.bore_depth_mm_or_through"
            )
        if str(row.get("install_face", "")).strip().upper() not in {"TOP", "UNDERSIDE"}:
            raise ValueError(
                f"FASTENER_MAP.csv {feature_id}.install_face must be TOP or UNDERSIDE"
            )


def validate_fixed_camera_fallback_release_gate(record: dict[str, Any]) -> None:
    """Bind a fallback-print release to the controlled camera decision."""
    gate_id = "fixed_camera_fallback_architecture_released"
    gate = record["gates"][gate_id]
    if gate["status"] != "PASS":
        return

    decision_bytes = CAMERA_ARCHITECTURE_DECISION_PATH.read_bytes()
    decision = json.loads(decision_bytes.decode("utf-8"))
    decision_sha256 = hashlib.sha256(decision_bytes).hexdigest()
    decision_status = decision.get("status")
    decision_revision = decision.get("design_revision")
    fallback = decision.get("fixed_camera_fallback_release")
    if decision_status != "ALIGNED_AND_REVISED":
        raise ValueError(
            f"{gate_id} cannot PASS while camera architecture status is "
            f"{decision_status!r}; expected 'ALIGNED_AND_REVISED'"
        )
    if decision_revision != record.get("design_revision"):
        raise ValueError(f"{gate_id} camera decision revision does not match the build")
    if not isinstance(fallback, dict) or fallback.get("authorized") is not True:
        raise ValueError(f"{gate_id} requires explicit fixed-camera fallback authorization")
    authorization_reference = fallback.get("authorization_reference")
    if not isinstance(authorization_reference, str) or not authorization_reference.strip():
        raise ValueError(f"{gate_id} fallback authorization reference must be nonblank")
    if fallback.get("release_revision") != decision_revision:
        raise ValueError(f"{gate_id} fallback release revision does not match the decision")

    values = _require_exact_keys(
        gate["recorded_values"],
        {
            "architecture_decision_status",
            "architecture_decision_revision",
            "architecture_decision_sha256",
            "fixed_camera_fallback_authorized",
            "fallback_authorization_reference",
        },
        gate_id,
    )
    expected = {
        "architecture_decision_status": decision_status,
        "architecture_decision_revision": decision_revision,
        "architecture_decision_sha256": decision_sha256,
        "fixed_camera_fallback_authorized": True,
        "fallback_authorization_reference": authorization_reference,
    }
    if values != expected:
        raise ValueError(f"{gate_id} evidence does not match the controlled camera decision")


def validate_engineering_release_gates(record: dict[str, Any]) -> None:
    """Validate safety-critical approval schemas and measured-to-approved relations."""
    gates = record["gates"]
    validate_fixed_camera_fallback_release_gate(record)
    validate_calibration_cartridge_gate(record)
    validate_board_setup_template_gate(record)

    clearance_gate = gates["phone_no_go_clearance_limit_approved"]
    clearance_values = clearance_gate["recorded_values"]
    approved_clearance = approved_uncertainty = None
    if clearance_gate["status"] == "PASS":
        approved_clearance = _finite_number(
            clearance_values["minimum_clearance_mm"],
            "phone_no_go_clearance_limit_approved.minimum_clearance_mm",
        )
        approved_uncertainty = _finite_number(
            clearance_values["maximum_measurement_uncertainty_mm"],
            "phone_no_go_clearance_limit_approved.maximum_measurement_uncertainty_mm",
            positive=False,
        )
        if approved_uncertainty >= approved_clearance:
            raise ValueError(
                "phone no-go maximum measurement uncertainty must be smaller than "
                "the approved minimum clearance"
            )

    side_gate = gates["phone_side_features_measured"]
    if side_gate["status"] == "PASS":
        approved = _require_gate_pass(
            gates, "phone_no_go_clearance_limit_approved", "phone_side_features_measured"
        )
        values = side_gate["recorded_values"]
        if values["approved_clearance_limit_id"] != approved["approval_id"]:
            raise ValueError("phone side-feature approval ID does not match the no-go approval")
        keepouts = values["right_side_keepouts_from_bottom_mm"]
        centers = values["selected_clamp_centers_from_bottom_mm"]
        if not isinstance(keepouts, list) or not keepouts:
            raise ValueError("phone side-feature keepouts must be a non-empty list")
        if not isinstance(centers, list) or len(centers) != 2:
            raise ValueError("phone side-feature record must contain exactly two clamp centers")
        center_values = [
            _finite_number(value, f"phone clamp center {index + 1} mm", positive=False)
            for index, value in enumerate(centers)
        ]
        intervals: list[tuple[float, float]] = []
        for index, keepout in enumerate(keepouts):
            item = _require_exact_keys(
                keepout,
                {"feature", "start_mm", "end_mm"},
                f"phone keepout {index + 1}",
            )
            if not isinstance(item["feature"], str) or not item["feature"].strip():
                raise ValueError(f"phone keepout {index + 1}.feature must be nonblank")
            start = _finite_number(
                item["start_mm"], f"phone keepout {index + 1}.start_mm", positive=False
            )
            end = _finite_number(
                item["end_mm"], f"phone keepout {index + 1}.end_mm", positive=False
            )
            if end <= start:
                raise ValueError(f"phone keepout {index + 1} end_mm must exceed start_mm")
            intervals.append((start, end))
        geometric_margins: list[float] = []
        for center in center_values:
            for start, end in intervals:
                if start <= center <= end:
                    raise ValueError("a selected phone clamp center lies inside a keepout interval")
                geometric_margins.append(min(abs(center - start), abs(center - end)))
        measured_margin = _finite_number(
            values["minimum_keepout_margin_mm"],
            "phone_side_features_measured.minimum_keepout_margin_mm",
        )
        if measured_margin > min(geometric_margins) + 1e-9:
            raise ValueError("recorded phone keepout margin exceeds the interval calculation")
        measured_uncertainty = _finite_number(
            values["clearance_measurement_uncertainty_mm"],
            "phone_side_features_measured.clearance_measurement_uncertainty_mm",
            positive=False,
        )
        if measured_uncertainty > _finite_number(
            approved["maximum_measurement_uncertainty_mm"],
            "approved phone no-go uncertainty",
            positive=False,
        ):
            raise ValueError("phone keepout measurement uncertainty exceeds the approval")
        if measured_margin - measured_uncertainty < _finite_number(
            approved["minimum_clearance_mm"], "approved phone no-go clearance"
        ):
            raise ValueError("conservative phone keepout margin is below the approved minimum")

    fixture_gate = gates["phone_fixture_assembly_pass"]
    if fixture_gate["status"] == "PASS":
        approved = _require_gate_pass(
            gates, "phone_no_go_clearance_limit_approved", "phone_fixture_assembly_pass"
        )
        values = fixture_gate["recorded_values"]
        if values["approved_no_go_clearance_limit_id"] != approved["approval_id"]:
            raise ValueError("phone fixture approval ID does not match the no-go approval")
        _same_number(
            values["approved_minimum_no_go_clearance_mm"],
            approved["minimum_clearance_mm"],
            "phone fixture minimum no-go clearance mm",
        )
        measured_margin = _finite_number(
            values["measured_minimum_no_go_clearance_mm"],
            "phone_fixture_assembly_pass.measured_minimum_no_go_clearance_mm",
        )
        measured_uncertainty = _finite_number(
            values["clearance_measurement_uncertainty_mm"],
            "phone_fixture_assembly_pass.clearance_measurement_uncertainty_mm",
            positive=False,
        )
        if measured_uncertainty > _finite_number(
            approved["maximum_measurement_uncertainty_mm"],
            "approved phone no-go uncertainty",
            positive=False,
        ):
            raise ValueError("phone fixture measurement uncertainty exceeds the approval")
        if measured_margin - measured_uncertainty < _finite_number(
            approved["minimum_clearance_mm"], "approved phone no-go clearance"
        ):
            raise ValueError("phone fixture conservative clearance is below the approved minimum")

    phone_tpu_approval_gate = gates["phone_tpu_retention_limits_approved"]
    phone_tpu_approval = phone_tpu_approval_gate["recorded_values"]
    if phone_tpu_approval_gate["status"] == "PASS":
        pull_force = _finite_number(
            phone_tpu_approval["minimum_pull_force_n"],
            "phone_tpu_retention_limits_approved.minimum_pull_force_n",
        )
        _finite_number(
            phone_tpu_approval["minimum_proof_duration_s"],
            "phone_tpu_retention_limits_approved.minimum_proof_duration_s",
        )
        gauge_range = _finite_number(
            phone_tpu_approval["force_gauge_required_range_n"],
            "phone_tpu_retention_limits_approved.force_gauge_required_range_n",
        )
        gauge_resolution = _finite_number(
            phone_tpu_approval["force_gauge_required_resolution_n"],
            "phone_tpu_retention_limits_approved.force_gauge_required_resolution_n",
        )
        if gauge_range < pull_force:
            raise ValueError("phone TPU force-gauge range is below the approved proof force")
        if gauge_resolution >= pull_force:
            raise ValueError("phone TPU force-gauge resolution must be finer than the proof force")

    phone_tpu_gate = gates["phone_tpu_retention_coupon_pass"]
    if phone_tpu_gate["status"] == "PASS":
        approved = _require_gate_pass(
            gates, "phone_tpu_retention_limits_approved", "phone_tpu_retention_coupon_pass"
        )
        values = phone_tpu_gate["recorded_values"]
        if values["approved_limits_id"] != approved["approval_id"]:
            raise ValueError("phone TPU coupon approval ID does not match")
        minimum_force = _same_number(
            values["minimum_pull_force_n"],
            approved["minimum_pull_force_n"],
            "phone TPU minimum pull force N",
        )
        if _finite_number(
            values["proof_duration_s"], "phone TPU achieved proof duration s"
        ) < _finite_number(
            approved["minimum_proof_duration_s"], "approved phone TPU proof duration s"
        ):
            raise ValueError("phone TPU proof duration is below the approved minimum")
        if _finite_number(
            values["measured_pull_force_n"], "phone TPU measured pull force N"
        ) < minimum_force:
            raise ValueError("phone TPU measured pull force is below the approved minimum")

    tool_approval_gate = gates["tool_force_tcp_limits_approved"]
    tool_approval = tool_approval_gate["recorded_values"]
    selected_tool_routes = {
        route for route in TOOL_ROUTE_IDS if record.get("selected_routes", {}).get(route, False)
    }
    route_limits: dict[str, dict[str, Any]] = {}
    if tool_approval_gate["status"] == "PASS":
        approved_routes = tool_approval["selected_routes"]
        if not isinstance(approved_routes, list) or len(approved_routes) != len(set(approved_routes)):
            raise ValueError("tool approval selected_routes must be a duplicate-free list")
        if set(approved_routes) != selected_tool_routes or not selected_tool_routes:
            raise ValueError("tool approval routes must exactly match the selected tool routes")
        limits_by_route = tool_approval["limits_by_route"]
        if not isinstance(limits_by_route, dict) or set(limits_by_route) != selected_tool_routes:
            raise ValueError("tool approval limits_by_route must exactly cover selected tool routes")
        gauge_range = _finite_number(
            tool_approval["force_gauge_required_range_n"],
            "tool approval force-gauge range N",
        )
        gauge_resolution = _finite_number(
            tool_approval["force_gauge_required_resolution_n"],
            "tool approval force-gauge resolution N",
        )
        largest_required_force = 0.0
        smallest_positive_force = math.inf
        for route in approved_routes:
            route_specific = (
                {
                    "rod_bushing_minimum_pull_force_n",
                    "rod_bushing_minimum_proof_duration_s",
                    "keyboard_tpu_minimum_pull_force_n",
                    "keyboard_tpu_minimum_proof_duration_s",
                }
                if route == "keyboard_rod_route"
                else {
                    "stylus_collar_minimum_pull_force_n",
                    "stylus_collar_minimum_proof_duration_s",
                }
            )
            limits = _require_exact_keys(
                limits_by_route[route],
                {"compression_force_checkpoints", "tcp_axis_range_limit_mm"}
                | route_specific,
                f"tool approval {route}",
            )
            checkpoints = limits["compression_force_checkpoints"]
            if not isinstance(checkpoints, list) or len(checkpoints) < 2:
                raise ValueError(f"tool approval {route} requires at least two force checkpoints")
            seen_travel: set[float] = set()
            for index, checkpoint in enumerate(checkpoints):
                item = _require_exact_keys(
                    checkpoint,
                    {"travel_mm", "minimum_force_n", "maximum_force_n"},
                    f"tool approval {route} checkpoint {index + 1}",
                )
                travel = _finite_number(
                    item["travel_mm"],
                    f"tool approval {route} checkpoint {index + 1} travel_mm",
                    positive=False,
                )
                if travel in seen_travel:
                    raise ValueError(f"tool approval {route} has duplicate checkpoint travel")
                seen_travel.add(travel)
                minimum = _finite_number(
                    item["minimum_force_n"],
                    f"tool approval {route} checkpoint {index + 1} minimum_force_n",
                    positive=False,
                )
                maximum = _finite_number(
                    item["maximum_force_n"],
                    f"tool approval {route} checkpoint {index + 1} maximum_force_n",
                )
                if maximum < minimum:
                    raise ValueError(f"tool approval {route} force maximum is below minimum")
                largest_required_force = max(largest_required_force, maximum)
                if minimum > 0:
                    smallest_positive_force = min(smallest_positive_force, minimum)
                smallest_positive_force = min(smallest_positive_force, maximum)
            _finite_number(
                limits["tcp_axis_range_limit_mm"],
                f"tool approval {route} TCP axis-range limit mm",
            )
            for key in route_specific:
                value = _finite_number(limits[key], f"tool approval {route}.{key}")
                if key.endswith("force_n"):
                    largest_required_force = max(largest_required_force, value)
                    smallest_positive_force = min(smallest_positive_force, value)
            route_limits[route] = limits
        if gauge_range < largest_required_force:
            raise ValueError("tool force-gauge range is below an approved force limit")
        if gauge_resolution >= smallest_positive_force:
            raise ValueError("tool force-gauge resolution is not fine enough for the approved limits")

    coupon_cross_checks = (
        (
            "keyboard_tpu_retention_coupon_pass",
            "keyboard_rod_route",
            "keyboard_tpu_minimum_pull_force_n",
            "keyboard_tpu_minimum_proof_duration_s",
        ),
        (
            "rod_bushing_retention_pass",
            "keyboard_rod_route",
            "rod_bushing_minimum_pull_force_n",
            "rod_bushing_minimum_proof_duration_s",
        ),
        (
            "stylus_collar_retention_pass",
            "phone_stylus_route",
            "stylus_collar_minimum_pull_force_n",
            "stylus_collar_minimum_proof_duration_s",
        ),
    )
    for gate_id, route, force_key, duration_key in coupon_cross_checks:
        gate = gates[gate_id]
        if gate["status"] != "PASS":
            continue
        approved = _require_gate_pass(gates, "tool_force_tcp_limits_approved", gate_id)
        if route not in approved["limits_by_route"]:
            raise ValueError(f"{gate_id} has no approved {route} limits")
        values = gate["recorded_values"]
        if values["approved_limits_id"] != approved["approval_id"]:
            raise ValueError(f"{gate_id} approval ID does not match")
        limits = approved["limits_by_route"][route]
        minimum_force = _same_number(
            values["minimum_pull_force_n"], limits[force_key], f"{gate_id} minimum pull force N"
        )
        if _finite_number(values["proof_duration_s"], f"{gate_id} proof duration s") < _finite_number(
            limits[duration_key], f"approved {gate_id} proof duration s"
        ):
            raise ValueError(f"{gate_id} proof duration is below the approved minimum")
        if _finite_number(
            values["measured_pull_force_n"], f"{gate_id} measured pull force N"
        ) < minimum_force:
            raise ValueError(f"{gate_id} measured pull force is below the approved minimum")

    assembled_gate = gates["tool_assembled_motion_pass"]
    if assembled_gate["status"] == "PASS":
        approved = _require_gate_pass(
            gates, "tool_force_tcp_limits_approved", "tool_assembled_motion_pass"
        )
        values = assembled_gate["recorded_values"]
        if values["approved_limits_id"] != approved["approval_id"]:
            raise ValueError("assembled tool approval ID does not match")
        result_routes = values["selected_routes"]
        if not isinstance(result_routes, list) or len(result_routes) != len(set(result_routes)):
            raise ValueError("assembled tool selected_routes must be a duplicate-free list")
        if set(result_routes) != selected_tool_routes:
            raise ValueError("assembled tool routes must exactly match selected tool routes")
        results_by_route = values["results_by_route"]
        if not isinstance(results_by_route, dict) or set(results_by_route) != selected_tool_routes:
            raise ValueError("assembled tool results must exactly cover selected tool routes")
        for route in result_routes:
            limits = approved["limits_by_route"][route]
            route_specific = (
                {
                    "rod_bushing_pull_force_n",
                    "rod_bushing_proof_duration_s",
                    "keyboard_tpu_pull_force_n",
                    "keyboard_tpu_proof_duration_s",
                }
                if route == "keyboard_rod_route"
                else {"stylus_collar_pull_force_n", "stylus_collar_proof_duration_s"}
            )
            common = {
                "cycle_count",
                "free_travel_mm",
                "force_measurements_by_checkpoint",
                "full_return_pass",
                "no_coil_bind_pass",
                "gripper_retention_pass",
                "functional_contact_pass",
                "tcp_probe_cycle_count",
                "tcp_range_x_mm",
                "tcp_range_y_mm",
                "tcp_range_z_mm",
            }
            result = _require_exact_keys(
                results_by_route[route], common | route_specific, f"assembled tool {route}"
            )
            _integer_at_least(result["cycle_count"], 20, f"assembled tool {route} cycle_count")
            travel = _finite_number(
                result["free_travel_mm"], f"assembled tool {route} free_travel_mm"
            )
            if not 3.0 <= travel <= 6.0:
                raise ValueError(f"assembled tool {route} free travel must remain within 3-6 mm")
            for key in (
                "full_return_pass",
                "no_coil_bind_pass",
                "gripper_retention_pass",
                "functional_contact_pass",
            ):
                if result[key] is not True:
                    raise ValueError(f"assembled tool {route}.{key} must be true")
            _integer_at_least(
                result["tcp_probe_cycle_count"], 10, f"assembled tool {route} TCP probe cycles"
            )
            tcp_limit = _finite_number(
                limits["tcp_axis_range_limit_mm"], f"approved {route} TCP axis range mm"
            )
            for axis in "xyz":
                measured = _finite_number(
                    result[f"tcp_range_{axis}_mm"],
                    f"assembled tool {route} TCP {axis.upper()} range mm",
                    positive=False,
                )
                if measured > tcp_limit:
                    raise ValueError(f"assembled tool {route} TCP {axis.upper()} range exceeds approval")
            measurements = result["force_measurements_by_checkpoint"]
            checkpoints = limits["compression_force_checkpoints"]
            if not isinstance(measurements, list) or len(measurements) != len(checkpoints):
                raise ValueError(f"assembled tool {route} force results must match every checkpoint")
            approved_by_travel = {float(item["travel_mm"]): item for item in checkpoints}
            measured_travel: set[float] = set()
            for index, measurement in enumerate(measurements):
                item = _require_exact_keys(
                    measurement,
                    {"travel_mm", "measured_force_n"},
                    f"assembled tool {route} force result {index + 1}",
                )
                point = _finite_number(
                    item["travel_mm"],
                    f"assembled tool {route} force result {index + 1} travel_mm",
                    positive=False,
                )
                if point not in approved_by_travel or point in measured_travel:
                    raise ValueError(f"assembled tool {route} force-result travel is unapproved or duplicate")
                measured_travel.add(point)
                force = _finite_number(
                    item["measured_force_n"],
                    f"assembled tool {route} force result {index + 1} measured_force_n",
                    positive=False,
                )
                checkpoint = approved_by_travel[point]
                minimum = _finite_number(
                    checkpoint["minimum_force_n"], f"approved {route} checkpoint minimum", positive=False
                )
                maximum = _finite_number(
                    checkpoint["maximum_force_n"], f"approved {route} checkpoint maximum"
                )
                if not minimum <= force <= maximum:
                    raise ValueError(f"assembled tool {route} force result is outside approval")
            if route == "keyboard_rod_route":
                retention_checks = (
                    ("rod_bushing_pull_force_n", "rod_bushing_minimum_pull_force_n"),
                    ("rod_bushing_proof_duration_s", "rod_bushing_minimum_proof_duration_s"),
                    ("keyboard_tpu_pull_force_n", "keyboard_tpu_minimum_pull_force_n"),
                    ("keyboard_tpu_proof_duration_s", "keyboard_tpu_minimum_proof_duration_s"),
                )
            else:
                retention_checks = (
                    ("stylus_collar_pull_force_n", "stylus_collar_minimum_pull_force_n"),
                    ("stylus_collar_proof_duration_s", "stylus_collar_minimum_proof_duration_s"),
                )
            for measured_key, approved_key in retention_checks:
                if _finite_number(
                    result[measured_key], f"assembled tool {route}.{measured_key}"
                ) < _finite_number(limits[approved_key], f"approved {route}.{approved_key}"):
                    raise ValueError(f"assembled tool {route}.{measured_key} is below approval")

    commissioning_gate = gates["commissioning_motion_contact_limits_approved"]
    commissioning = commissioning_gate["recorded_values"]
    if commissioning_gate["status"] == "PASS":
        commissioning_numeric_fields = (
            "empty_motion_tcp_speed_limit_mm_s",
            "empty_motion_tcp_acceleration_limit_mm_s2",
            "minimum_clearance_mm",
            "first_contact_tcp_speed_limit_mm_s",
            "first_contact_force_limit_n",
            "first_contact_travel_limit_mm",
            "station_20n_lateral_proof_duration_s",
            "station_10n_functional_proof_duration_s",
        )
        for key in commissioning_numeric_fields:
            _finite_number(commissioning[key], f"commissioning approval {key}")
        for key in (
            "controller_model_and_firmware",
            "estop_implementation",
            "board_anti_shift_implementation",
        ):
            if not isinstance(commissioning.get(key), str) or not commissioning[key].strip():
                raise ValueError(f"commissioning approval {key} must be nonblank")
        for path_key, hash_key in (
            ("homing_reference_procedure_path", "homing_reference_procedure_sha256"),
            ("empty_cell_program_path", "empty_cell_program_sha256"),
            ("final_process_program_path", "final_process_program_sha256"),
        ):
            _bound_project_file(commissioning, path_key, hash_key, "commissioning approval")
        if _as_float(commissioning["first_contact_tcp_speed_limit_mm_s"], "first-contact speed") > _as_float(
            commissioning["empty_motion_tcp_speed_limit_mm_s"], "empty-motion speed"
        ):
            raise ValueError("first-contact TCP speed limit may not exceed empty-motion speed limit")

    workcell_gate = gates["workcell_commissioning_pass"]
    if workcell_gate["status"] == "PASS":
        approved = _require_gate_pass(
            gates, "commissioning_motion_contact_limits_approved", "workcell_commissioning_pass"
        )
        values = workcell_gate["recorded_values"]
        if values["approved_motion_contact_limits_id"] != approved["approval_id"]:
            raise ValueError("workcell commissioning approval ID does not match")
        for key in (
            "controller_model_and_firmware",
            "homing_reference_procedure_path",
            "homing_reference_procedure_sha256",
            "empty_cell_program_path",
            "empty_cell_program_sha256",
            "final_process_program_path",
            "final_process_program_sha256",
            "estop_implementation",
            "board_anti_shift_implementation",
        ):
            if values.get(key) != approved.get(key):
                raise ValueError(f"workcell commissioning {key} does not match the approved artifact/implementation")
        upper_limit_pairs = (
            ("empty_motion_tcp_speed_used_mm_s", "empty_motion_tcp_speed_limit_mm_s"),
            (
                "empty_motion_tcp_acceleration_used_mm_s2",
                "empty_motion_tcp_acceleration_limit_mm_s2",
            ),
            ("first_contact_tcp_speed_used_mm_s", "first_contact_tcp_speed_limit_mm_s"),
            ("first_contact_force_measured_n", "first_contact_force_limit_n"),
            ("first_contact_travel_measured_mm", "first_contact_travel_limit_mm"),
        )
        for measured_key, approved_key in upper_limit_pairs:
            measured = _finite_number(values[measured_key], f"workcell {measured_key}")
            limit = _finite_number(approved[approved_key], f"approved {approved_key}")
            if measured > limit:
                raise ValueError(f"workcell {measured_key} exceeds approved {approved_key}")
        _same_number(
            values["minimum_clearance_limit_mm"],
            approved["minimum_clearance_mm"],
            "workcell minimum clearance limit mm",
        )
        if _finite_number(
            values["minimum_clearance_measured_mm"], "workcell measured minimum clearance mm"
        ) < _finite_number(approved["minimum_clearance_mm"], "approved minimum clearance mm"):
            raise ValueError("workcell measured clearance is below the approved minimum")
        for measured_key, approved_key in (
            ("station_20n_lateral_proof_duration_s", "station_20n_lateral_proof_duration_s"),
            ("station_10n_functional_proof_duration_s", "station_10n_functional_proof_duration_s"),
        ):
            if _finite_number(values[measured_key], f"workcell {measured_key}") < _finite_number(
                approved[approved_key], f"approved {approved_key}"
            ):
                raise ValueError(f"workcell {measured_key} is below the approved duration")

    board_gate = gates["board_fabrication_pass"]
    if board_gate["status"] == "PASS":
        board_values = board_gate["recorded_values"]
        measured_dimensions = {}
        for key in (
            "width_mm",
            "depth_mm",
            "thickness_mm",
            "front_width_mm",
            "rear_width_mm",
            "left_depth_mm",
            "right_depth_mm",
            "diagonal_1_mm",
            "diagonal_2_mm",
        ):
            measured_dimensions[key] = _finite_number(
                board_values.get(key), f"board_fabrication_pass {key}"
            )

        for key, nominal in (
            ("width_mm", BOARD_WIDTH_NOMINAL_MM),
            ("front_width_mm", BOARD_WIDTH_NOMINAL_MM),
            ("rear_width_mm", BOARD_WIDTH_NOMINAL_MM),
            ("depth_mm", BOARD_DEPTH_NOMINAL_MM),
            ("left_depth_mm", BOARD_DEPTH_NOMINAL_MM),
            ("right_depth_mm", BOARD_DEPTH_NOMINAL_MM),
        ):
            if abs(measured_dimensions[key] - nominal) > BOARD_EDGE_LENGTH_TOLERANCE_MM:
                raise ValueError(
                    f"board_fabrication_pass {key} is outside the released "
                    f"{nominal:.1f} +/- {BOARD_EDGE_LENGTH_TOLERANCE_MM:.2f} mm cut-size limit"
                )
        if abs(
            measured_dimensions["front_width_mm"] - measured_dimensions["rear_width_mm"]
        ) > BOARD_OPPOSITE_EDGE_DIFFERENCE_LIMIT_MM:
            raise ValueError(
                "board_fabrication_pass front/rear width difference exceeds 0.50 mm"
            )
        if abs(
            measured_dimensions["left_depth_mm"] - measured_dimensions["right_depth_mm"]
        ) > BOARD_OPPOSITE_EDGE_DIFFERENCE_LIMIT_MM:
            raise ValueError(
                "board_fabrication_pass left/right depth difference exceeds 0.50 mm"
            )
        if not (
            BOARD_THICKNESS_MIN_MM
            <= measured_dimensions["thickness_mm"]
            <= BOARD_THICKNESS_MAX_MM
        ):
            raise ValueError(
                "board_fabrication_pass thickness_mm must be within 17.50-18.50 mm"
            )

        mean_width = (
            measured_dimensions["front_width_mm"] + measured_dimensions["rear_width_mm"]
        ) / 2.0
        mean_depth = (
            measured_dimensions["left_depth_mm"] + measured_dimensions["right_depth_mm"]
        ) / 2.0
        expected_diagonal = math.hypot(mean_width, mean_depth)
        for key in ("diagonal_1_mm", "diagonal_2_mm"):
            if abs(measured_dimensions[key] - expected_diagonal) > BOARD_DIAGONAL_TOLERANCE_MM:
                raise ValueError(
                    f"board_fabrication_pass {key} differs from the edge-derived diagonal "
                    f"by more than {BOARD_DIAGONAL_TOLERANCE_MM:.2f} mm"
                )
        if abs(
            measured_dimensions["diagonal_1_mm"] - measured_dimensions["diagonal_2_mm"]
        ) > BOARD_DIAGONAL_DIFFERENCE_LIMIT_MM:
            raise ValueError(
                "board_fabrication_pass diagonal mismatch exceeds 1.00 mm"
            )
        coordinate_record = board_values.get("transferred_center_coordinate_record")
        if not isinstance(coordinate_record, str) or not coordinate_record.strip():
            raise ValueError(
                "board_fabrication_pass transferred_center_coordinate_record must be nonblank"
            )

        for key in (
            "both_faces_sealed_result",
            "all_edges_sealed_result",
            "finish_cure_result",
            "threaded_board_interface_result",
            "scrap_stack_proof_load_result",
        ):
            if board_values.get(key) != "PASS":
                raise ValueError(f"board_fabrication_pass {key} must be recorded PASS")
        for key in (
            "finish_product_and_batch",
            "finish_application_and_cure_record",
            "finish_evidence_reference",
        ):
            if not isinstance(board_values.get(key), str) or not board_values[key].strip():
                raise ValueError(f"board_fabrication_pass {key} must be nonblank")

        local_flatness = board_values.get("local_flatness_by_station_mm")
        if not isinstance(local_flatness, dict) or not local_flatness:
            raise ValueError(
                "board_fabrication_pass local_flatness_by_station_mm must contain measured stations"
            )
        for station, value in local_flatness.items():
            if not isinstance(station, str) or not station.strip():
                raise ValueError(
                    "board_fabrication_pass local_flatness_by_station_mm contains a blank station"
                )
            measured = _finite_number(
                value,
                f"board_fabrication_pass local_flatness_by_station_mm.{station}",
                positive=False,
            )
            if measured > BOARD_LOCAL_FLATNESS_LIMIT_MM:
                raise ValueError(
                    "board_fabrication_pass local flatness exceeds 0.50 mm"
                )
        overall_bow = _finite_number(
            board_values.get("overall_bow_mm"),
            "board_fabrication_pass overall_bow_mm",
            positive=False,
        )
        if overall_bow > BOARD_OVERALL_BOW_LIMIT_MM:
            raise ValueError("board_fabrication_pass overall bow exceeds 1.50 mm")

        for axis in ("x", "y"):
            measured = _finite_number(
                board_values.get(f"template_{axis}_scale_bar_mm"),
                f"board_fabrication_pass template_{axis}_scale_bar_mm",
            )
            if not 99.8 <= measured <= 100.2:
                raise ValueError(
                    f"board_fabrication_pass template {axis.upper()} scale bar must be "
                    "100.0 +/- 0.2 mm"
                )

        local_thicknesses = board_values.get("local_thickness_by_locator_mm")
        if not isinstance(local_thicknesses, dict) or set(local_thicknesses) != set(
            BOARD_LOCATOR_IDS
        ):
            raise ValueError(
                "board_fabrication_pass local_thickness_by_locator_mm must contain exactly "
                "KBL-LOC-ROUND, KBL-LOC-RADIAL, PT-LOC-ROUND, and PT-LOC-RADIAL"
            )
        measured_local_thicknesses: dict[str, float] = {}
        for locator_id in BOARD_LOCATOR_IDS:
            local_thickness = _finite_number(
                local_thicknesses[locator_id],
                f"board_fabrication_pass local_thickness_by_locator_mm.{locator_id}",
            )
            if not BOARD_THICKNESS_MIN_MM <= local_thickness <= BOARD_THICKNESS_MAX_MM:
                raise ValueError(
                    f"board_fabrication_pass local thickness at {locator_id} must be "
                    "within 17.50-18.50 mm"
                )
            measured_local_thicknesses[locator_id] = local_thickness

        bore_depths = board_values.get("blind_locator_bore_depths_mm")
        if not isinstance(bore_depths, dict) or set(bore_depths) != set(BOARD_LOCATOR_IDS):
            raise ValueError(
                "board_fabrication_pass blind_locator_bore_depths_mm must contain exactly "
                "the four named locator IDs"
            )
        for locator_id in BOARD_LOCATOR_IDS:
            depth = _finite_number(
                bore_depths[locator_id],
                f"board_fabrication_pass blind_locator_bore_depths_mm.{locator_id}",
            )
            if abs(depth - BOARD_LOCATOR_BORE_DEPTH_NOMINAL_MM) > (
                BOARD_LOCATOR_BORE_DEPTH_TOLERANCE_MM
            ):
                raise ValueError(
                    f"board_fabrication_pass blind locator bore depth at {locator_id} "
                    "must be 15.00 +/- 0.20 mm"
                )
            maximum_blind_depth = (
                measured_local_thicknesses[locator_id]
                - BOARD_MINIMUM_BLIND_BORE_FLOOR_MM
            )
            if depth > maximum_blind_depth:
                raise ValueError(
                    f"board_fabrication_pass blind locator bore depth at {locator_id} "
                    "leaves less than the required 2.0 mm local board floor"
                )

        projections = board_values.get("locator_projection_measurements_mm")
        if not isinstance(projections, dict) or set(projections) != set(BOARD_LOCATOR_IDS):
            raise ValueError(
                "board_fabrication_pass locator_projection_measurements_mm must contain "
                "exactly the four named locator IDs"
            )
        for locator_id in BOARD_LOCATOR_IDS:
            projection = _finite_number(
                projections[locator_id],
                f"board_fabrication_pass locator_projection_measurements_mm.{locator_id}",
            )
            if abs(projection - BOARD_LOCATOR_PROJECTION_NOMINAL_MM) > (
                BOARD_LOCATOR_PROJECTION_TOLERANCE_MM
            ):
                raise ValueError(
                    f"board_fabrication_pass locator projection at {locator_id} "
                    "must be 5.00 +/- 0.15 mm"
                )

        validate_selected_fastener_map(FASTENER_MAP_PATH)
        expected_hash = _file_sha256(FASTENER_MAP_PATH, "FASTENER_MAP.csv")
        recorded_hash = board_values.get("selected_fastener_map_sha256")
        if not isinstance(recorded_hash, str) or re.fullmatch(r"[0-9a-f]{64}", recorded_hash) is None:
            raise ValueError("board_fabrication_pass selected_fastener_map_sha256 is missing or malformed")
        if recorded_hash != expected_hash:
            raise ValueError(
                "board_fabrication_pass FASTENER_MAP.csv hash is stale; reopen board/fastener acceptance"
            )


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
    validate_engineering_release_gates(record)
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
    validate_profile_gate_bindings(record, jobs_config, profiles)
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

        profile_name = job["profile"]
        if profile_name not in profiles["process_profiles"]:
            raise ValueError(
                f"Job {job['job_id']} references unknown profile {profile_name}"
            )
        profile = profiles["process_profiles"][profile_name]
        controls = validate_generated_print_control(job, profiles)
        results.append(
            {
                "job_id": job["job_id"],
                "design_revision": record["design_revision"],
                "status": status,
                "selected": selected,
                "stage": job["stage"],
                "plate_file": job["plate_file"],
                "settings_file": str(Path(job["plate_file"]).with_suffix(".print.json")),
                "machine_settings_file": str(Path(job["plate_file"]).with_suffix(".print.json")),
                "readable_settings_file": controls["settings_file"],
                "readable_settings_sha256": controls["settings_sha256"],
                "qidi_process_profile_file": controls["qidi_process_profile_file"],
                "qidi_process_profile_sha256": controls["qidi_process_profile_sha256"],
                "filament_preset": controls["filament_preset"],
                "preset_data_status": controls["preset_data_status"],
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
        "3. Print required diagnostic jobs 00A, 00B, 00C, 00E, and 00F with their matching profiles; print 00D only when `phone_stylus_route` is selected.",
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

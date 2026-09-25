#!/usr/bin/env python3
"""Synchronize print-job sidecars and BOM to generated camera-portal CAD.

Run this only after ``generate_printable_frame.py``.  The generated CAD
manifest remains the geometry authority; this script converts its exact plate
allocation, hashes, quantities, and configured hardware into the operator
files consumed by ``validate_printable_frame_package.py``.
"""
from __future__ import annotations

import csv
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "printable_frame_design.json"
MANIFEST_PATH = ROOT / "cad" / "output" / "manifest.json"
JOBS_DIR = ROOT / "print_jobs"
JOBS_PATH = JOBS_DIR / "printable_camera_frame_jobs.json"
BOM_PATH = ROOT / "BOM_PRINTABLE_FRAME.csv"


PROFILE_SPECS = {
    "abs_structural": {
        "process_file": "../slicer_profiles/QIDI_PLUS4/abs_rapido_camera_frame_structural_0p4.process.json",
        "filament_preset": "QIDI ABS Rapido @Qidi X-Plus 4 0.4 nozzle",
        "material": "QIDI ABS Rapido",
    },
    "abs_holder_precision": {
        "process_file": "../slicer_profiles/QIDI_PLUS4/abs_rapido_camera_holder_precision_0p4.process.json",
        "filament_preset": "QIDI ABS Rapido @Qidi X-Plus 4 0.4 nozzle",
        "material": "QIDI ABS Rapido",
    },
    "tpu_pads": {
        "process_file": "../slicer_profiles/QIDI_PLUS4/tpu95a_camera_clamp_pad_0p4.process.json",
        "filament_preset": "Installed and identified TPU 95A preset for X-Plus 4 0.4 nozzle",
        "material": "TPU 95A",
    },
}


JOB_META = {
    "00G": (
        "Fit gates and compliant pads",
        "Print and accept board, splice, camera, retainer, and pad coupons before structural production parts.",
    ),
    "08A": (
        "Left board anchor and upright",
        "Left bench-bearing saddle, cap, retainers, portal plates, splices, and four upright modules.",
    ),
    "08B": (
        "Right board anchor and upright",
        "Right bench-bearing saddle, cap, retainers, portal plates, splices, and four upright modules.",
    ),
    "08C": (
        "Crossbar, booms, and camera carriage",
        "Four crossbar modules, four boom modules, splice collars, root straps, and positive-lock carriage.",
    ),
    "08D": (
        "Camera cage and keeper",
        "Four-sided camera cage and planar four-bolt keeper printed with the precision ABS process.",
    ),
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def relative_process(path_string: str) -> Path:
    return (JOBS_DIR / path_string).resolve()


def profile_record(key: str) -> dict:
    spec = dict(PROFILE_SPECS[key])
    process = load_json(relative_process(spec["process_file"]))
    spec.update(
        {
            "process_name": process["name"],
            "layer_height_mm": float(process["layer_height"]),
            "wall_loops": int(process["wall_loops"]),
            "top_shell_layers": int(process["top_shell_layers"]),
            "bottom_shell_layers": int(process["bottom_shell_layers"]),
            "infill": f"{process['sparse_infill_density']} {process['sparse_infill_pattern']}",
            "brim_type": process["brim_type"],
            "brim_width_mm": float(process["brim_width"]),
            "brim_object_gap_mm": float(process["brim_object_gap"]),
            "supports": False,
            "fuzzy_skin": "none",
        }
    )
    return spec


def consolidate_objects(plate: dict) -> list[dict]:
    counts = Counter(obj["part"] for obj in plate["objects"])
    return [
        {
            "part": part,
            "stl": f"../cad/output/stl/{part}.stl",
            "quantity": quantity,
        }
        for part, quantity in sorted(counts.items())
    ]


def make_subplate(plate: dict) -> dict:
    geometry_name = Path(plate["filename"]).name
    sidecar = f"{Path(geometry_name).stem}.print.json"
    return {
        "subplate_id": plate["subplate_id"],
        "geometry_3mf": f"../cad/output/plates_3mf/{geometry_name}",
        "geometry_sha256": plate["sha256"],
        "expected_object_count": int(plate["object_count"]),
        "sidecar": sidecar,
        "profile": plate["profile_key"],
        "native_save_as_pattern": f"{plate['subplate_id']}_QIDI_native_vNN.3mf",
        "objects": consolidate_objects(plate),
    }


def write_sidecars(design_id: str, profiles: dict, subplates: list[dict]) -> None:
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    expected = {subplate["sidecar"] for subplate in subplates}
    for path in JOBS_DIR.glob("*.print.json"):
        if path.name not in expected:
            if path.resolve().parent != JOBS_DIR.resolve():
                raise RuntimeError(f"refusing to remove out-of-scope sidecar: {path}")
            path.unlink()

    for subplate in subplates:
        profile = profiles[subplate["profile"]]
        payload = {
            "schema": "rocell.printable_camera_portal.print_sidecar.v1",
            "schema_version": 1,
            "design_id": design_id,
            "state": "PROTOTYPE_NOT_RELEASED_FOR_ROBOT_OPERATION",
            **subplate,
            "print": {
                "profile_key": subplate["profile"],
                "process_name": profile["process_name"],
                "process_file": profile["process_file"],
                "filament_preset": profile["filament_preset"],
                "scale_percent": 100.0,
                "supports": False,
                "fuzzy_skin": "none",
                "orientation": "use stored 3MF orientation and placement; do not auto-arrange",
            },
        }
        (JOBS_DIR / subplate["sidecar"]).write_text(
            json.dumps(payload, indent=2) + "\n", encoding="utf-8"
        )


def write_bom(config: dict, manifest: dict, subplates: list[dict]) -> None:
    part_subplates: dict[str, list[str]] = defaultdict(list)
    part_profiles: dict[str, set[str]] = defaultdict(set)
    for subplate in subplates:
        for obj in subplate["objects"]:
            part_subplates[obj["part"]].append(subplate["subplate_id"])
            part_profiles[obj["part"]].add(subplate["profile"])

    header = (
        "line_id",
        "category",
        "bag_id",
        "item_id",
        "quantity",
        "unit",
        "specification",
        "print_job_or_use",
        "state",
        "notes",
    )
    rows: list[dict] = []
    for index, part in enumerate(config["parts"], 1):
        name = part["part"]
        subplate_ids = sorted(set(part_subplates[name]))
        is_tpu = part_profiles[name] == {"tpu_pads"}
        state = "FIT_GATE" if part.get("print_first") else "PROTOTYPE"
        if part.get("sacrificial_quantity"):
            state = "INCLUDES_SACRIFICIAL_TEST_PIECE"
        rows.append(
            {
                "line_id": f"P{index:03d}",
                "category": "Printed TPU" if is_tpu else "Printed ABS",
                "bag_id": f"P-{subplate_ids[0]}",
                "item_id": name,
                "quantity": int(part["quantity"]),
                "unit": "each",
                "specification": part["material"],
                "print_job_or_use": ";".join(subplate_ids),
                "state": state,
                "notes": part.get("note", "Use the exact generated 3MF and mapped process at 100% scale."),
            }
        )

    for index, item in enumerate(manifest["hardware"], 1):
        name = item["item"]
        if "cable tie" in name.lower():
            category = "Cable hardware"
        elif "tether" in name.lower():
            category = "Safety hardware"
        else:
            category = "Metal hardware"
        rows.append(
            {
                "line_id": f"H{index:03d}",
                "category": category,
                "bag_id": "HARDWARE",
                "item_id": name,
                "quantity": int(item["quantity"]),
                "unit": "each",
                "specification": item["use"],
                "print_job_or_use": "PORTAL_AND_CAMERA_ASSEMBLY",
                "state": "PROCURE_AND_VERIFY",
                "notes": "Do not substitute size, length, head style, or locking feature without rechecking the CAD stack.",
            }
        )

    with BOM_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)


def main() -> dict:
    config = load_json(CONFIG_PATH)
    manifest = load_json(MANIFEST_PATH)
    if config["design_id"] != manifest["design_id"]:
        raise RuntimeError("generate CAD before synchronizing: config/manifest design_id mismatch")
    required = (
        manifest["contract_validation"]["status"],
        manifest["assembly_interface_validation"]["status"],
        manifest["fastener_interface_validation"]["status"],
        manifest["part_validation_status"],
        manifest["plate_validation"]["status"],
    )
    if any(status != "PASS" for status in required):
        raise RuntimeError(f"refusing to map a failed generated package: {required}")

    profiles = {key: profile_record(key) for key in PROFILE_SPECS}
    subplates = [make_subplate(plate) for plate in manifest["plate_validation"]["subplates"]]
    allocated = Counter()
    for subplate in subplates:
        allocated.update({obj["part"]: int(obj["quantity"]) for obj in subplate["objects"]})
    configured = Counter({part["part"]: int(part["quantity"]) for part in config["parts"]})
    if allocated != configured:
        raise RuntimeError(f"plate/config allocation mismatch: allocated={allocated}; configured={configured}")

    grouped: dict[str, list[dict]] = defaultdict(list)
    for subplate in subplates:
        grouped[subplate["subplate_id"].split("-")[0]].append(subplate)
    jobs = []
    for job_id in ("00G", "08A", "08B", "08C", "08D"):
        name, purpose = JOB_META[job_id]
        jobs.append(
            {
                "job_id": job_id,
                "name": name,
                "state": "DEFINED_PROTOTYPE_NOT_RELEASED",
                "purpose": purpose,
                "subplates": grouped[job_id],
            }
        )

    payload = {
        "schema": "rocell.printable_camera_portal.print_jobs.v1",
        "schema_version": 1,
        "design_id": config["design_id"],
        "revision_date": config["revision_date"],
        "state": "VALIDATED_GEOMETRY_SUBPLATES_NOT_RELEASED_FOR_ROBOT_OPERATION",
        "scope": "Printed board anchors, portal arms, camera carriage, and camera cage only.",
        "geometry": {
            "generated_manifest": "../cad/output/manifest.json",
            "plate_validation": "../cad/output/PLATE_VALIDATION.json",
            "scale_percent": 100.0,
            "orientation_rule": "Use each stored 3MF orientation and placement; do not auto-arrange or rescale.",
        },
        "printer": {
            "machine": config["printer"]["machine"],
            "protected_part_envelope_mm": config["printer"]["protected_part_envelope_mm"],
            "nozzle_mm": 0.4,
        },
        "profiles": profiles,
        "common_preflight": [
            "Match the selected 3MF SHA-256 and object count to this file and its sidecar.",
            "Select the named process and filament preset separately; generated 3MF files contain geometry only.",
            "Keep scale at 100%, supports off, fuzzy skin off, and inspect the complete layer preview.",
            "Save a new native QIDI project; never overwrite the generated geometry-only 3MF.",
        ],
        "jobs": jobs,
        "configured_printed_part_quantity_total": sum(configured.values()),
        "configured_hardware_quantity_total": sum(int(row["quantity"]) for row in manifest["hardware"]),
    }
    JOBS_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    write_sidecars(config["design_id"], profiles, subplates)
    write_bom(config, manifest, subplates)
    return {
        "status": "PASS",
        "design_id": config["design_id"],
        "subplates": len(subplates),
        "printed_objects": sum(configured.values()),
        "hardware_pieces": payload["configured_hardware_quantity_total"],
    }


if __name__ == "__main__":
    result = main()
    print(json.dumps(result, indent=2))
    if sys.platform == "win32":
        sys.stdout.flush()
        os._exit(0)

#!/usr/bin/env python3
"""Read-only validation for the generated printable camera-frame package.

This does not regenerate or modify CAD.  It independently reopens every STEP,
STL, and geometry-only 3MF named by the generated manifest and rejects stale,
missing, non-manifold, multi-body, or out-of-envelope printable geometry.
"""

from __future__ import annotations

import hashlib
import csv
import json
import os
import sys
import zipfile
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET

import cadquery as cq
import numpy as np
import trimesh


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "cad" / "output"
STEP_DIR = OUTPUT / "step"
STL_DIR = OUTPUT / "stl"
PLATE_DIR = OUTPUT / "plates_3mf"
CONFIG_PATH = ROOT / "config" / "printable_frame_design.json"
MANIFEST_PATH = OUTPUT / "manifest.json"
JOBS_DIR = ROOT / "print_jobs"
JOB_MANIFEST_PATH = JOBS_DIR / "printable_camera_frame_jobs.json"
BOM_PATH = ROOT / "BOM_PRINTABLE_FRAME.csv"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict:
    require(path.is_file(), f"missing JSON: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def quantity_counter(rows: list[dict], key: str) -> Counter:
    return Counter({row[key]: int(row["quantity"]) for row in rows})


def validate_step(path: Path) -> None:
    require(path.is_file() and path.stat().st_size > 0, f"missing/empty STEP: {path}")
    model = cq.importers.importStep(str(path))
    require(bool(model.vals()), f"STEP reopened without shapes: {path}")


def validate_stl(path: Path, safe: np.ndarray) -> None:
    require(path.is_file() and path.stat().st_size > 0, f"missing/empty STL: {path}")
    # STL stores triangle corners independently.  Weld coincident vertices on
    # import before making topology assertions; otherwise every valid binary
    # STL appears as one disconnected triangle per face.
    mesh = trimesh.load_mesh(path, force="mesh", process=True)
    require(mesh.is_watertight, f"non-watertight STL: {path}")
    require(mesh.is_winding_consistent, f"inconsistent winding: {path}")
    require(float(mesh.volume) > 0.0, f"non-positive STL volume: {path}")
    require(len(mesh.split(only_watertight=False)) == 1, f"multi-body printable STL: {path}")
    require(bool(np.all(mesh.extents <= safe + 1e-5)), f"STL exceeds protected envelope: {path}")


def three_mf_counts(path: Path) -> tuple[int, int]:
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("3D/3dmodel.model"))
    namespace = {"m": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"}
    resources = len(root.findall("./m:resources/m:object", namespace))
    build_items = len(root.findall("./m:build/m:item", namespace))
    return resources, build_items


def main() -> dict:
    config = load_json(CONFIG_PATH)
    manifest = load_json(MANIFEST_PATH)
    require(config["design_id"] == manifest["design_id"], "config/manifest design_id mismatch")
    safe = np.asarray(config["printer"]["protected_part_envelope_mm"], dtype=float)

    status_paths = {
        "contract": manifest["contract_validation"]["status"],
        "assembly_interfaces": manifest["assembly_interface_validation"]["status"],
        "fastener_interfaces": manifest["fastener_interface_validation"]["status"],
        "printable_parts": manifest["part_validation_status"],
        "plate_allocation": manifest["plate_allocation_validation"]["status"],
        "plates": manifest["plate_validation"]["status"],
        "printed_parts_assembly": manifest["printed_parts_only_assembly_validation"]["status"],
        "managed_inventory": manifest["managed_output_inventory_validation"]["status"],
    }
    require(all(value == "PASS" for value in status_paths.values()), f"manifest has failed status: {status_paths}")

    part_names = {row["part"] for row in manifest["parts"]}
    require(len(part_names) == len(manifest["parts"]), "duplicate printable part names in manifest")
    require({path.stem for path in STEP_DIR.glob("*.step")} == part_names, "STEP inventory differs from manifest")
    require({path.stem for path in STL_DIR.glob("*.stl")} == part_names, "STL inventory differs from manifest")

    for name in sorted(part_names):
        validate_step(STEP_DIR / f"{name}.step")
        validate_stl(STL_DIR / f"{name}.stl", safe)

    plate_rows = manifest["plate_validation"]["subplates"]
    plate_names = {Path(row["filename"]).name for row in plate_rows}
    listed_paths = {Path(path).name for path in manifest["geometry_only_3mf_subplates"]}
    actual_paths = {path.name for path in PLATE_DIR.glob("*.3mf")}
    require(plate_names == listed_paths == actual_paths, "3MF inventory differs from manifest")

    packaged_objects = 0
    for row in plate_rows:
        path = PLATE_DIR / Path(row["filename"]).name
        require(path.is_file() and path.stat().st_size > 0, f"missing/empty 3MF: {path}")
        require(sha256(path).lower() == row["sha256"].lower(), f"3MF checksum mismatch: {path}")
        resources, build_items = three_mf_counts(path)
        scene = trimesh.load(path, force="scene", process=False)
        expected = int(row["object_count"])
        require(resources == expected, f"3MF resource count mismatch: {path}")
        require(build_items == expected, f"3MF build-item count mismatch: {path}")
        require(len(scene.geometry) == expected, f"3MF round-trip object count mismatch: {path}")
        require(bool(np.all(scene.bounds[0] >= -1e-5)), f"3MF has negative packed coordinates: {path}")
        require(bool(np.all(scene.bounds[1] <= safe + 1e-5)), f"3MF exceeds protected envelope: {path}")
        packaged_objects += expected

    require(packaged_objects == int(manifest["plate_validation"]["object_count"]), "packaged object total mismatch")

    # Reconcile the operator-facing print manifest and all same-name sidecars
    # against the generated geometry.  The 3MF files intentionally contain no
    # process metadata, so this mapping is part of the usable print package.
    jobs = load_json(JOB_MANIFEST_PATH)
    require(jobs["design_id"] == manifest["design_id"], "print-job/manifest design_id mismatch")
    subplates = [subplate for job in jobs["jobs"] for subplate in job["subplates"]]
    require(len(subplates) == len(plate_rows), "print-job subplate count mismatch")
    require(len({row["subplate_id"] for row in subplates}) == len(subplates), "duplicate print-job subplate_id")
    expected_sidecars = {row["sidecar"] for row in subplates}
    actual_sidecars = {path.name for path in JOBS_DIR.glob("*.print.json")}
    require(expected_sidecars == actual_sidecars, "print-sidecar inventory differs from print manifest")

    plate_by_name = {Path(row["filename"]).name: row for row in plate_rows}
    manifested_part_quantities = quantity_counter(manifest["parts"], "part")
    hardware_total = sum(int(row["quantity"]) for row in manifest["hardware"])
    allocated_part_quantities: Counter = Counter()
    for subplate in subplates:
        geometry_path = (JOBS_DIR / subplate["geometry_3mf"]).resolve()
        plate_row = plate_by_name.get(geometry_path.name)
        require(plate_row is not None and geometry_path.parent == PLATE_DIR.resolve(), f"unmanaged job geometry: {geometry_path}")
        require(geometry_path.is_file(), f"missing job geometry: {geometry_path}")
        require(subplate["geometry_sha256"].lower() == plate_row["sha256"].lower(), f"job/plate hash mismatch: {geometry_path.name}")
        require(int(subplate["expected_object_count"]) == int(plate_row["object_count"]), f"job/plate object mismatch: {geometry_path.name}")

        subplate_parts = Counter()
        for obj in subplate["objects"]:
            require(obj["part"] in part_names, f"unknown print-job part: {obj['part']}")
            require(Path(obj["stl"]).stem == obj["part"], f"job STL/part mismatch: {obj['part']}")
            quantity = int(obj["quantity"])
            require(quantity > 0, f"non-positive print-job quantity: {obj['part']}")
            subplate_parts[obj["part"]] += quantity
        require(sum(subplate_parts.values()) == int(subplate["expected_object_count"]), f"job object total mismatch: {subplate['subplate_id']}")
        allocated_part_quantities.update(subplate_parts)

        profile_key = subplate["profile"]
        require(profile_key in jobs["profiles"], f"unknown profile key: {profile_key}")
        profile = jobs["profiles"][profile_key]
        sidecar = load_json(JOBS_DIR / subplate["sidecar"])
        require(sidecar["design_id"] == jobs["design_id"], f"sidecar design_id mismatch: {subplate['sidecar']}")
        for field in ("subplate_id", "geometry_3mf", "geometry_sha256", "expected_object_count", "native_save_as_pattern"):
            require(sidecar[field] == subplate[field], f"sidecar field mismatch {field}: {subplate['sidecar']}")
        sidecar_parts = Counter({row["part"]: int(row["quantity"]) for row in sidecar["objects"]})
        require(sidecar_parts == subplate_parts, f"sidecar object allocation mismatch: {subplate['sidecar']}")

        print_map = sidecar["print"]
        require(print_map["profile_key"] == profile_key, f"sidecar profile mismatch: {subplate['sidecar']}")
        require(print_map["process_name"] == profile["process_name"], f"sidecar process-name mismatch: {subplate['sidecar']}")
        require(print_map["filament_preset"] == profile["filament_preset"], f"sidecar filament mismatch: {subplate['sidecar']}")
        require(float(print_map["scale_percent"]) == 100.0, f"sidecar scale is not 100%: {subplate['sidecar']}")
        require(print_map["supports"] is False and print_map["fuzzy_skin"] == "none", f"sidecar support/fuzzy-skin mismatch: {subplate['sidecar']}")
        process_path = (JOBS_DIR / print_map["process_file"]).resolve()
        require(process_path == (JOBS_DIR / profile["process_file"]).resolve(), f"sidecar/profile process path mismatch: {subplate['sidecar']}")
        process = load_json(process_path)
        require(process["name"] == profile["process_name"], f"process JSON name mismatch: {process_path.name}")
        require(float(process["layer_height"]) == float(profile["layer_height_mm"]), f"process layer-height mismatch: {process_path.name}")
        require(process["enable_support"] == "0" and process["fuzzy_skin"] == "none", f"process support/fuzzy-skin mismatch: {process_path.name}")
        require(process["brim_type"] == profile["brim_type"], f"process brim type mismatch: {process_path.name}")
        require(float(process["brim_width"]) == float(profile["brim_width_mm"]), f"process brim width mismatch: {process_path.name}")
        require(float(process["brim_object_gap"]) == float(profile["brim_object_gap_mm"]), f"process brim gap mismatch: {process_path.name}")

    require(allocated_part_quantities == manifested_part_quantities, "print-job part allocation differs from generated manifest")

    require(BOM_PATH.is_file(), f"missing BOM: {BOM_PATH}")
    with BOM_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        bom_rows = list(csv.DictReader(handle))
    require(bom_rows and len({row["line_id"] for row in bom_rows}) == len(bom_rows), "empty or duplicate BOM line_id")
    bom_printed = Counter()
    bom_hardware_total = 0
    for row in bom_rows:
        quantity = int(row["quantity"])
        if row["category"].startswith("Printed "):
            bom_printed[row["item_id"]] += quantity
        if row["category"] in {"Metal hardware", "Cable hardware", "Safety hardware"}:
            bom_hardware_total += quantity
    require(bom_printed == manifested_part_quantities, "BOM printed-part allocation differs from generated manifest")
    require(bom_hardware_total == hardware_total, "BOM hardware total differs from generated manifest")
    require(int(jobs["configured_printed_part_quantity_total"]) == packaged_objects, "print manifest configured printed total mismatch")
    require(int(jobs["configured_hardware_quantity_total"]) == hardware_total, "print manifest configured hardware total mismatch")

    printed_assembly = manifest["printed_parts_only_assembly_validation"]
    for key in ("step", "stl"):
        path = ROOT / printed_assembly[key]
        require(path.is_file() and path.stat().st_size > 0, f"missing printed-parts assembly {key}: {path}")
        require(sha256(path).lower() == printed_assembly[f"{key}_sha256"].lower(), f"assembly checksum mismatch: {path}")

    configured_prints = sum(int(row["quantity"]) for row in config["parts"])
    manifested_prints = sum(int(row["quantity"]) for row in manifest["parts"])
    require(configured_prints == manifested_prints == packaged_objects, "configured/manifest/3MF print count mismatch")

    return {
        "status": "PASS",
        "design_id": manifest["design_id"],
        "manifest_sha256": sha256(MANIFEST_PATH),
        "part_types": len(part_names),
        "packaged_print_objects": packaged_objects,
        "installed_printed_bodies": int(printed_assembly["installed_printed_body_count"]),
        "subplates_3mf": len(plate_rows),
        "print_sidecars": len(actual_sidecars),
        "hardware_items_total": hardware_total,
        "protected_envelope_mm": safe.tolist(),
        "statuses": status_paths,
    }


if __name__ == "__main__":
    try:
        result = main()
        print(json.dumps(result, indent=2))
        sys.stdout.flush()
        if sys.platform == "win32":
            os._exit(0)
    except Exception as exc:  # concise CLI failure for builders and CI logs
        print(f"PRINTABLE_FRAME_PACKAGE_VALIDATION_FAIL: {exc}", file=sys.stderr)
        raise

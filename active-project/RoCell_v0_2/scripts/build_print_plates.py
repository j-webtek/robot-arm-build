#!/usr/bin/env python3
"""Create QIDI Plus4 3MF build plates from the validated STL parts."""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parents[1]
STL = ROOT / "stl"
OUT = ROOT / "print_plates_3mf"
OUT.mkdir(exist_ok=True)
PARAMS = json.loads((ROOT / "config" / "parameters.json").read_text(encoding="utf-8"))
PROFILE_CONFIG = json.loads((ROOT / "config" / "print_profiles.json").read_text(encoding="utf-8"))
JOB_CONFIG = json.loads((ROOT / "config" / "print_jobs.json").read_text(encoding="utf-8"))
JOBS = {job["job_id"]: job for job in JOB_CONFIG["jobs"]}
BED_X = float(PARAMS["printer_safe_x"])
BED_Y = float(PARAMS["printer_safe_y"])
BED_Z = float(PARAMS["printer_safe_z"])
NOMINAL_X, NOMINAL_Y, NOMINAL_Z = [
    float(value) for value in PROFILE_CONFIG["printer"]["nominal_build_volume_mm"]
]
EDGE_MARGIN = float(PROFILE_CONFIG["printer"]["edge_margin_mm"])
PLATE_ROWS: list[dict] = []


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_json(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def load_at(filename: str, x: float, y: float, copies: int = 1,
            dx: float = 0, dy: float = 0, rotate_z: float = 0):
    items = []
    for i in range(copies):
        mesh = trimesh.load_mesh(STL / filename, force="mesh").copy()
        components = len(mesh.split(only_watertight=False))
        if not mesh.is_watertight or components != 1 or mesh.volume <= 0:
            raise ValueError(
                f"Invalid source mesh {filename}: watertight={mesh.is_watertight}, "
                f"components={components}, volume={mesh.volume}"
            )
        if rotate_z:
            mesh.apply_transform(trimesh.transformations.rotation_matrix(
                np.radians(rotate_z), [0, 0, 1]
            ))
        # Normalize exported part to lower-left Z=0 after rotation and before placement.
        mn = mesh.bounds[0]
        mesh.apply_translation((-mn[0] + x + i * dx, -mn[1] + y + i * dy, -mn[2]))
        items.append((f"{Path(filename).stem}_{i+1}", mesh))
    return items


def export_plate(job_id: str, items: list[tuple[str, trimesh.Trimesh]]) -> None:
    job = JOBS[job_id]
    name = Path(job["plate_file"]).stem
    profile_name = job["profile"]
    profile = PROFILE_CONFIG["process_profiles"][profile_name]

    actual_parts = Counter(f"{base.rsplit('_', 1)[0]}.stl" for base, _ in items)
    if dict(actual_parts) != job["parts"]:
        raise ValueError(
            f"{job_id} part manifest mismatch: configured={job['parts']}, actual={dict(actual_parts)}"
        )
    for index, (name_a, mesh_a) in enumerate(items):
        for name_b, mesh_b in items[index + 1:]:
            overlap = np.minimum(mesh_a.bounds[1, :2], mesh_b.bounds[1, :2]) - np.maximum(
                mesh_a.bounds[0, :2], mesh_b.bounds[0, :2]
            )
            if np.all(overlap > 0.01):
                raise ValueError(
                    f"{name} has overlapping placements: {name_a} and {name_b} "
                    f"overlap by {overlap[0]:.2f} x {overlap[1]:.2f} mm"
                )

    # Center the arranged group on the physical 305 x 305 mm bed.  The models
    # keep their intended Z=0 orientation; only XY placement is changed here.
    group_min = np.min([mesh.bounds[0] for _, mesh in items], axis=0)
    group_max = np.max([mesh.bounds[1] for _, mesh in items], axis=0)
    group_center = (group_min[:2] + group_max[:2]) / 2.0
    target_center = np.array([NOMINAL_X / 2.0, NOMINAL_Y / 2.0])
    shift_xy = target_center - group_center
    for _, mesh in items:
        mesh.apply_translation((shift_xy[0], shift_xy[1], 0.0))

    scene = trimesh.Scene()
    # Some plates contain repeated parts. 3MF scene node and geometry names must
    # be unique or a repeated name can silently replace an earlier copy.
    name_counts: dict[str, int] = {}
    for object_index, (base_name, mesh) in enumerate(items, 1):
        name_counts[base_name] = name_counts.get(base_name, 0) + 1
        # Keep 3MF node names below 32 characters.  Trimesh's 3MF exporter can
        # silently omit a build item when a long source filename is reused as
        # the node name (camera_plate_universal exposed this edge case).
        unique_name = f"o{object_index:02d}_{base_name[:26]}"
        scene.add_geometry(mesh, node_name=unique_name, geom_name=unique_name)
    bounds = scene.bounds
    ext = bounds[1] - bounds[0]
    if ext[0] > BED_X + 1e-6 or ext[1] > BED_Y + 1e-6 or ext[2] > BED_Z + 1e-6:
        raise ValueError(
            f"{name} exceeds safe Plus4 envelope {BED_X} x {BED_Y} x {BED_Z}: {ext}"
        )
    if (
        bounds[0, 0] < EDGE_MARGIN - 1e-6
        or bounds[0, 1] < EDGE_MARGIN - 1e-6
        or bounds[1, 0] > NOMINAL_X - EDGE_MARGIN + 1e-6
        or bounds[1, 1] > NOMINAL_Y - EDGE_MARGIN + 1e-6
    ):
        raise ValueError(
            f"{name} violates the {EDGE_MARGIN:.1f} mm physical bed-edge margin: {bounds}"
        )
    path = OUT / f"{name}.3mf"
    scene.export(path)
    # Read-back verifies the archive is parseable.
    loaded = trimesh.load(path, force="scene")
    if loaded.is_empty:
        raise ValueError(f"3MF read-back failed: {path}")
    if len(loaded.geometry) != len(items):
        raise ValueError(
            f"3MF part-count mismatch for {path}: expected {len(items)}, "
            f"read back {len(loaded.geometry)}"
        )
    for geometry_name, mesh in loaded.geometry.items():
        components = len(mesh.split(only_watertight=False))
        if not mesh.is_watertight or components != 1 or mesh.volume <= 0:
            raise ValueError(
                f"Invalid 3MF geometry {geometry_name} in {path}: "
                f"watertight={mesh.is_watertight}, components={components}, "
                f"volume={mesh.volume}"
            )
    sidecar = {
        "schema_version": 2,
        "design_revision": JOB_CONFIG["design_revision"],
        "job_id": job_id,
        "plate_file": path.name,
        "printer": PROFILE_CONFIG["printer"],
        "stage": job["stage"],
        "selection": job["selection"],
        "purpose": job["purpose"],
        "parts": job["parts"],
        "prerequisites": job["prerequisites"],
        "process_profile_name": profile_name,
        "process_profile": profile,
        "slicer_warning": PROFILE_CONFIG["rules"]["temperature_policy"],
        "geometry_only_3mf": True,
        "qidi_studio_native_project_required": True,
        "qidi_studio_roundtrip_gate": "qidi_studio_roundtrip_confirmed",
        "plate_envelope_mm": [round(float(value), 1) for value in ext],
        "absolute_bed_bounds_mm": {
            "min": [round(float(value), 3) for value in bounds[0]],
            "max": [round(float(value), 3) for value in bounds[1]],
        },
        "centered_on_nominal_bed": True,
        "source_stl_sha256": {
            filename: sha256_file(STL / filename) for filename in sorted(job["parts"])
        },
        "process_profile_sha256": sha256_json(profile),
        "plate_sha256": sha256_file(path),
        "objects": [
            {
                "name": object_name,
                "bounds_mm": [
                    [round(float(value), 3) for value in mesh.bounds[0]],
                    [round(float(value), 3) for value in mesh.bounds[1]],
                ],
            }
            for object_name, mesh in items
        ],
    }
    (OUT / f"{name}.print.json").write_text(
        json.dumps(sidecar, indent=2) + "\n", encoding="utf-8"
    )

    PLATE_ROWS.append({
        "job_id": job_id,
        "plate_file": path.name,
        "stage": job["stage"],
        "selection": job["selection"],
        "material": profile["material"],
        "process_profile": profile_name,
        "nozzle_mm": profile["nozzle_mm"],
        "layer_mm": profile["layer_height_mm"],
        "purpose": job["purpose"],
        "prerequisites": ";".join(job["prerequisites"]),
        "objects": len(items),
        "extent_x_mm": round(float(ext[0]), 1),
        "extent_y_mm": round(float(ext[1]), 1),
        "extent_z_mm": round(float(ext[2]), 1),
    })
    print(
        f"{path.name}: {ext[0]:.1f} x {ext[1]:.1f} x {ext[2]:.1f} mm; "
        f"{len(items)} object(s)"
    )


def main() -> None:
    PLATE_ROWS.clear()
    export_plate("00A", [
        *load_at("keyboard_corner_fit_test.stl", 0, 0),
        *load_at("keyboard_seam_fit_male.stl", 68, 0),
        *load_at("keyboard_seam_fit_female.stl", 136, 0),
        *load_at("hardware_fit_gauge.stl", 0, 68),
        *load_at("m4_washer_fit_gauge.stl", 0, 108),
    ])
    export_plate("00B", [
        *load_at("phone_width_fit_test.stl", 0, 0),
        *load_at("m4_horizontal_insert_fit_gauge.stl", 96, 0),
        *load_at("cable_tie_saddle_fit_gauge.stl", 132, 0),
        *load_at("m4_washer_fit_gauge.stl", 0, 46),
    ])
    export_plate("00C", [
        *load_at("compliant_tool_grip_fit_test.stl", 0, 0),
        *load_at("spring_fit_gauge.stl", 38, 0),
        *load_at("m3_insert_fit_gauge.stl", 78, 0),
        *load_at("m3_head_fit_gauge.stl", 0, 40),
    ])
    export_plate("00D", [
        *load_at("stylus_diameter_gauge.stl", 0, 0),
        *load_at("thread_pilot_fit_gauge.stl", 102, 0),
    ])
    export_plate("00E", [
        *load_at("hardware_fit_gauge.stl", 0, 0),
        *load_at("setup_hardware_fit_gauge.stl", 0, 40),
        *load_at("tpu_tip_retention_gauge.stl", 170, 0),
    ])
    export_plate("00F", [
        *load_at("hardware_fit_gauge.stl", 0, 0),
        *load_at("m4_washer_fit_gauge.stl", 0, 40),
    ])
    export_plate("01", load_at("keyboard_tray_left.stl", 0, 0))
    export_plate("02", load_at("keyboard_tray_right.stl", 0, 0))
    export_plate("03A", load_at("phone_cradle_a16.stl", 0, 0))
    export_plate("03B", load_at("keyboard_rear_clamp.stl", 0, 0, copies=2, dx=60))

    export_plate("03C1", load_at("tag_frame_ID0_55mm.stl", 0, 0))
    export_plate("03C2", [
        *load_at("tag_frame_ID1_55mm.stl", 0, 0),
        *load_at("tag_frame_ID2_55mm.stl", 83, 0),
        *load_at("tag_frame_ID3_55mm.stl", 166, 0),
        *load_at("tag_frame_ID4_55mm.stl", 0, 83),
        *load_at("tag_frame_ID5_55mm.stl", 83, 83),
    ])
    export_plate("03C3", load_at("camera_plate_universal.stl", 0, 0))
    export_plate("03D", load_at("calibration_puck.stl", 0, 0))

    export_plate("04A", [
        *load_at("compliant_tool_body.stl", 0, 0),
        *load_at("compliant_tool_top_cap.stl", 38, 0, copies=2, dx=34),
    ])
    export_plate("04B", load_at("stylus_collar_9mm.stl", 0, 0, copies=2, dx=20))
    export_plate("04C", load_at("rod_bushing_6_to_9mm.stl", 0, 0, copies=2, dx=25))
    export_plate("05A", load_at("phone_clamp_tip_TPU_M4.stl", 0, 0))
    export_plate("05B", load_at("phone_clamp_tip_TPU_M4.stl", 0, 0, copies=3, dx=20))
    export_plate("05C", load_at("keyboard_tip_TPU_6mm.stl", 0, 0))
    export_plate("05D", load_at("keyboard_tip_TPU_6mm.stl", 0, 0, copies=3, dx=20))
    export_plate("06", [
        *load_at("mast_socket_fit_test.stl", 0, 0),
        *load_at("m5_nut_trap_fit_gauge.stl", 120, 0),
    ])
    export_plate("07A", load_at("mast_foot_2020.stl", 0, 0))
    export_plate("07B", load_at("mast_foot_2020.stl", 0, 0))

    if {row["job_id"] for row in PLATE_ROWS} != set(JOBS):
        raise ValueError("Not every configured print job was generated exactly once")

    expected = {OUT / row["plate_file"] for row in PLATE_ROWS}
    for stale in OUT.glob("*.3mf"):
        if stale not in expected:
            stale.unlink()
    expected_sidecars = {path.with_suffix(".print.json") for path in expected}
    for stale in OUT.glob("*.print.json"):
        if stale not in expected_sidecars:
            stale.unlink()

    with (ROOT / "PLATE_MANIFEST.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(PLATE_ROWS[0]))
        writer.writeheader()
        writer.writerows(PLATE_ROWS)

    # Regenerate the former hand-maintained part table from the same source as
    # the plates so profile, layer-height and quantity data cannot drift.
    plan_rows = []
    for job in JOB_CONFIG["jobs"]:
        profile = PROFILE_CONFIG["process_profiles"][job["profile"]]
        for filename, quantity in job["parts"].items():
            plan_rows.append({
                "job_id": job["job_id"],
                "stage": job["stage"],
                "selection": job["selection"],
                "part_file": filename,
                "qty": quantity,
                "material": profile["material"],
                "process_profile": job["profile"],
                "nozzle_mm": profile["nozzle_mm"],
                "layer_mm": profile["layer_height_mm"],
                "walls": profile["walls"],
                "top_layers": profile["top_layers"],
                "bottom_layers": profile["bottom_layers"],
                "infill_percent": profile["infill_percent"],
                "infill_pattern": profile["infill_pattern"],
                "supports": profile["supports"],
                "orientation": "Use the locked orientation and placement in the named 3MF; do not auto-orient",
            })
    with (ROOT / "PRINT_PLAN.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(plan_rows[0]))
        writer.writeheader()
        writer.writerows(plan_rows)

    readme = [
        "# QIDI Plus4 measured print jobs",
        "",
        "Start with `../PRINT_READINESS.md`. Print only a selected job marked READY.",
        "",
        "Every `.3mf` has a same-name `.print.json` sidecar. The sidecar is the authoritative source for material, nozzle, layer height, walls, top/bottom layers, infill, support guidance, contents, and prerequisite gate IDs.",
        "",
        "The 3MF files intentionally contain geometry and placement only. Use a calibrated QIDI Studio filament preset for the exact spool; do not infer temperatures from the filename.",
        "",
        "| Job | Stage | Selection | Plate | Material | Layer | Purpose |",
        "|---|---|---|---|---|---:|---|",
    ]
    for row in PLATE_ROWS:
        readme.append(
            f"| {row['job_id']} | {row['stage']} | {row['selection']} | "
            f"`{row['plate_file']}` | {row['material']} | {float(row['layer_mm']):.2f} mm | "
            f"{row['purpose']} |"
        )
    (OUT / "README.md").write_text("\n".join(readme) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

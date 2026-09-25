# Job 02 - Right keyboard tray after left first-article acceptance

| Control field | Released value |
|---|---|
| Design revision | `RC02-PRO-R1` |
| Lifecycle state | **UNRELEASED** |
| Route / stage | `required` / `production` |
| Kit | `KIT-KB` |
| Plate | `02_PETG_keyboard_right.3mf` |
| Plate SHA-256 | `38bd156f7dac84ae59168430a49b40f41355f5216b5cb8e3c87ed9cd8bc418b2` |
| Profile | `petg_tray_structural_0p4` / `a6683691851137c050c1549e2dc810a7be8db2d862064ffd63263d9c5a6165ad` |
| Printer | QIDI Plus4; 305 x 305 x 280 mm nominal; 5 mm protected edge margin |
| Material / nozzle / layer | PETG / 0.4 mm / 0.20 mm |
| Plate envelope | 162.5 x 157.0 x 11.0 mm; centered |
| Native slice record | QIDI Studio version, sliced mass and time: ____________________ |

## Objects and orientation

| STL | Qty | Locked orientation | Source SHA-256 |
|---|---:|---|---|
| `keyboard_tray_right.stl` | 1 | Flat, exported base on bed; RC02-R readable on top | `a9cdb802b6f0b233f5ee272e829316e31367ef50c8d9e4d7a788169d55520d93` |

## Required gates

| Gate | Status | Recorded values |
|---|---|---|
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "safe_plate_envelope_mm": [295, 295, 280]}` |
| `nozzle_0p4_confirmed` | **NOT_TESTED** | `{"installed_nozzle_mm": null, "verification_method": null}` |
| `petg_tray_profile_calibrated` | **NOT_TESTED** | `{"brand": null, "calibration_result": null, "drying_record": null, "filament_name": null, "profile_revision": null, "spool_lot": null}` |
| `keyboard_dimensions_measured` | **NOT_TESTED** | `{"cable_keepout_mm": null, "depth_mm": null, "device_model": null, "height_mm": null, "width_mm": null}` |
| `keyboard_corner_coupon_pass` | **NOT_TESTED** | `{"fit_result": null, "rocking_result": null, "selected_compensation_mm": null}` |
| `keyboard_seam_coupon_pass` | **NOT_TESTED** | `{"assembled_gap_mm": null, "fit_result": null, "flush_mismatch_mm": null}` |
| `tray_clearance_holes_coupon_pass` | **NOT_TESTED** | `{"board_screw_major_diameter_mm": null, "m4_washer_od_mm": null, "smallest_free_hole_mm": null, "washer_fit_result": null}` |
| `geometry_matches_measurements` | **NOT_TESTED** | `{"affected_parts_reviewed": null, "design_revision": null, "effective_parameters_file": null, "measurement_record_revision": null, "regeneration_completed": null}` |
| `keyboard_left_first_article_pass` | **NOT_TESTED** | `{"datum_surface_result": null, "flatness_mm": null, "job_id": null, "seam_key_result": null, "slot_fit_result": null, "washer_track_result": null}` |
| `qidi_studio_roundtrip_confirmed` | **NOT_TESTED** | `{"critical_layer_preview_pass_by_job": {}, "evidence_reference_by_job": {}, "geometry_scale_percent_by_job": {}, "native_project_sha256_by_job": {}, "object_count_by_job": {}, "qidi_studio_version": null, "saved_profile_revision_by_job": {}, "validated_job_ids": []}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: Accepted left half, keyboard, eight board screws/washers.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `petg_tray_structural_0p4`: 5 walls, 6 top / 6 bottom layers, 35% gyroid infill.
- Supports: off. Bed adhesion: Clean textured PEI; 6 mm brim recommended for the two large tray halves.
- Dimensional controls: Keep slicer seam away from mounting slots, male keys, female pocket mouths, and keyboard datums.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- Repeat first-article checks; mate both halves; record seam gap, flushness, assembled envelope, and rocking. Ten removal/reinstall cycles follow mounting.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, engraved identity and revision before cleanup.
- Quarantine any warped, cracked, delaminated, under-extruded, bridged-shut or untraceable part; do not silently rework a critical fit.
- Intended gate(s) after objective acceptance: `keyboard_tray_pair_postprint_pass`, `keyboard_fixture_assembly_pass`.

## Signoff

| Record | Entry |
|---|---|
| Spool brand / lot / dry record | ______________________________ |
| QIDI Studio project / version | ______________________________ |
| Printed date / operator | ______________________________ |
| Measured values / tool ID | ______________________________ |
| Evidence folder / photo IDs | ______________________________ |
| Result | [ ] PASS  [ ] REWORK  [ ] QUARANTINE |
| Inspector / date | ______________________________ |

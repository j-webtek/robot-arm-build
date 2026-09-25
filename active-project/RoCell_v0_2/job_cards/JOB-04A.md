# Job 04A - Shared compliant tool body with keyed cap and one spare cap

| Control field | Released value |
|---|---|
| Design revision | `RC02-PRO-R1` |
| Lifecycle state | **UNRELEASED** |
| Route / stage | `any_tool_route` / `route` |
| Kit | `KIT-TOOL-COMMON` |
| Plate | `04A_PETG_shared_compliant_tool.3mf` |
| Plate SHA-256 | `50d98e0061d42ba35f312e69871376c6867c0d63f44b66c210ff00f584b56b62` |
| Profile | `petg_precision_0p4` / `8a7d27cd2258c97d838fb416cc07a3e8842b840cc0868221bba343297b05e304` |
| Printer | QIDI Plus4; 305 x 305 x 280 mm nominal; 5 mm protected edge margin |
| Material / nozzle / layer | PETG / 0.4 mm / 0.16 mm |
| Plate envelope | 100.0 x 24.0 x 66.2 mm; centered |
| Native slice record | QIDI Studio version, sliced mass and time: ____________________ |

## Objects and orientation

| STL | Qty | Locked orientation | Source SHA-256 |
|---|---:|---|---|
| `compliant_tool_body.stl` | 1 | Upright on lower end with specified brim | `18c8d7ff2d57c0785b324c58e93b3c6558db7c56c339270ab183307b991225ba` |
| `compliant_tool_top_cap.stl` | 2 | Flat, underside on bed; UP visible after print | `e7adbf51fd9382a4eb2b9a9dd25df677d43fd488c4584c2bf3e3e7d1599b9081` |

## Required gates

| Gate | Status | Recorded values |
|---|---|---|
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "safe_plate_envelope_mm": [295, 295, 280]}` |
| `nozzle_0p4_confirmed` | **NOT_TESTED** | `{"installed_nozzle_mm": null, "verification_method": null}` |
| `petg_precision_profile_calibrated` | **NOT_TESTED** | `{"brand": null, "calibration_result": null, "drying_record": null, "filament_name": null, "profile_revision": null, "spool_lot": null}` |
| `m3_insert_coupon_pass` | **NOT_TESTED** | `{"insert_length_mm": null, "insert_od_mm": null, "installed_depth_mm": null, "retention_result": null, "selected_pocket_mm": null}` |
| `gripper_interface_measured` | **NOT_TESTED** | `{"jaw_opening_mm": null, "jaw_pad_height_mm": null, "jaw_pad_width_mm": null, "selected_grip_setting": null}` |
| `gripper_coupon_pass` | **NOT_TESTED** | `{"crush_result": null, "selected_grip_setting": null, "shim_each_side_mm": null, "slip_result": null}` |
| `spring_dimensions_measured` | **NOT_TESTED** | `{"approx_rate_n_per_mm": null, "coil_bind_length_mm": null, "free_length_mm": null, "id_mm": null, "od_mm": null}` |
| `spring_fit_coupon_pass` | **NOT_TESTED** | `{"binding_result": null, "cup_fit_result": null, "post_fit_result": null, "selected_step_mm": null}` |
| `precision_m3_head_coupon_pass` | **NOT_TESTED** | `{"fit_result": null, "m3_head_recess_d_mm": null, "screw_head_d_mm": null}` |
| `geometry_matches_measurements` | **NOT_TESTED** | `{"affected_parts_reviewed": null, "design_revision": null, "effective_parameters_file": null, "measurement_record_revision": null, "regeneration_completed": null}` |
| `qidi_studio_roundtrip_confirmed` | **NOT_TESTED** | `{"critical_layer_preview_pass_by_job": {}, "evidence_reference_by_job": {}, "geometry_scale_percent_by_job": {}, "native_project_sha256_by_job": {}, "object_count_by_job": {}, "qidi_studio_version": null, "saved_profile_revision_by_job": {}, "validated_job_ids": []}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: Two M3 inserts, two M3x10 screws, accepted spring, route adapter.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `petg_precision_0p4`: 5 walls, 6 top / 6 bottom layers, 40% gyroid infill.
- Supports: off. Bed adhesion: 5 mm brim around the upright tool body; remove carefully from the cap.
- Dimensional controls: Keep the slicer seam off the gripper flats and sliding guide bore.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- Inspect body straightness, grip flats, guide bore, spring chamber and keyed locator. Install inserts square; cap must seat only in the keyed orientation. Verify 3-6 mm smooth return after route assembly.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, engraved identity and revision before cleanup.
- Quarantine any warped, cracked, delaminated, under-extruded, bridged-shut or untraceable part; do not silently rework a critical fit.
- Intended gate(s) after objective acceptance: `tool_body_postprint_pass`, `tool_assembled_motion_pass`.

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

# Job 03C3 - Fixed-mast fallback camera plate; not an arm-camera adapter and not released while the camera architecture hold is open

| Control field | Released value |
|---|---|
| Design revision | `RC03-INT-R1` |
| Lifecycle state | **UNRELEASED** |
| Route / stage | `camera_mast_optional` / `production` |
| Kit | `KIT-VISION-CAM` |
| Plate | `03C3_PETG_camera_plate.3mf` |
| Plate SHA-256 | `b659444974c21f27d0832b97b0511edd4a879c2049d81ae010cb28d61c8eae42` |
| Profile | `petg_general_0p4` / `00f5efa4c8c65c9857564a255fdec4d4eaa571962c83d77095a470a20942edc6` |
| Exact settings sheet | `print_plates_3mf/03C3_PETG_camera_plate.PRINT_SETTINGS.md` / `736c5f8666a3beae5a87cf685c04831499f5510dacdec9e17ab651da5af8e214` |
| QIDI process import | `slicer_profiles/QIDI_PLUS4/petg_general_0p4.process.json` / `4e3fcda86460e9823234db1eff750e880a8b43bcb916dc2b584038b97376b605` |
| Filament preset | `exact_petg_spool_xplus4_0p4` / `e4af446b19a2425a1f87b49feb022fb06e525dc92f670689940c8dade2908fc4` |
| Preset completeness | **EXACT_PROCESS_SPOOL_PRESET_REQUIRED** |
| Unresolved filament fields | nozzle temperature, bed temperature, chamber temperature, flow ratio, pressure advance, maximum volumetric speed, cooling |
| Printer | QIDI Plus4; 305 x 305 x 280 mm nominal; 5 mm protected edge margin |
| Material / nozzle / layer | PETG / 0.4 mm / 0.20 mm |
| Plate envelope | 90.0 x 55.0 x 6.0 mm; centered |
| Native slice record | QIDI Studio version, sliced mass and time: ____________________ |

## Objects and orientation

| STL | Qty | Locked orientation | Source SHA-256 |
|---|---:|---|---|
| `camera_plate_universal.stl` | 1 | Flat as exported; CAM/MAST labels upward | `7fb63205ddc37b517ee452eda352893c7912cebe74086d977ef0beb8ec2d006f` |

## Required gates

| Gate | Status | Recorded values |
|---|---|---|
| `fixed_camera_fallback_architecture_released` | **NOT_TESTED** | `{"architecture_decision_revision": null, "architecture_decision_sha256": null, "architecture_decision_status": null, "fallback_authorization_reference": null, "fixed_camera_fallback_authorized": null}` |
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "provisional_protected_envelope_mm": [295, 295, 275]}` |
| `plus4_protected_envelope_verified` | **PASS** | `{"build_surface": "QIDI dual-sided textured PEI plate", "carriage_clearance_result": "PASS - protected envelope is inside official nominal volume", "enclosure_clearance_result": "PASS - operator confirmed completed printer qualification", "firmware_version": "Plus4_v1.7.1 official baseline; operator confirmed fully updated", "full_travel_test_result": "PASS - operator confirmed completed printer qualification", "printer_serial": "NOT_TRACKED_PROTOTYPE", "purge_and_exclusion_zone_result": "PASS - operator confirmed completed printer qualification", "verified_protected_envelope_mm": [295, 295, 275]}` |
| `nozzle_0p4_confirmed` | **PASS** | `{"installed_nozzle_mm": 0.4, "verification_method": "Official QIDI Plus4 standard specification and official printer.cfg; operator confirmed printer configuration"}` |
| `petg_general_profile_calibrated` | **NOT_TESTED** | `{"brand": null, "calibration_result": null, "drying_record": null, "filament_name": null, "profile_revision": null, "spool_lot": null}` |
| `camera_mount_interface_measured` | **NOT_TESTED** | `{"camera_model": null, "camera_thread": null, "safe_thread_engagement_mm": null, "selected_camera_screw_length_mm": null, "selected_tslot_screw_length_mm": null, "strap_width_mm": null}` |
| `general_clearance_holes_coupon_pass` | **NOT_TESTED** | `{"m3_selected_mm": null, "m4_or_board_screw_selected_mm": null, "m5_selected_mm": null}` |
| `setup_hardware_coupon_pass` | **NOT_TESTED** | `{"camera_hex_ac_mm": null, "fit_result": null, "m3_head_recess_d_mm": null, "m4_washer_od_mm": null, "m5_washer_od_mm": null}` |
| `geometry_matches_measurements` | **PASS** | `{"affected_parts_reviewed": true, "design_revision": "RC03-INT-R1", "effective_parameters_file": "config/parameters.json", "measurement_record_revision": "2026-09-06_JOB03C1_REWORK", "regeneration_completed": true}` |
| `qidi_studio_roundtrip_confirmed` | **NOT_TESTED** | `{"critical_layer_preview_pass_by_job": {}, "evidence_reference_by_job": {}, "geometry_scale_percent_by_job": {}, "native_project_sha256_by_job": {}, "object_count_by_job": {}, "qidi_studio_version": null, "saved_profile_revision_by_job": {}, "validated_job_ids": []}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: Actual fallback camera, 1/4-20 screw, two M5 screws/T-nuts/washers, straps.
- Open `print_plates_3mf/03C3_PETG_camera_plate.PRINT_SETTINGS.md` and follow every exact value in it.
- Import `slicer_profiles/QIDI_PLUS4/petg_general_0p4.process.json` and select `Generic PETG @Qidi X-Plus 4 0.4 nozzle` as the separate filament preset.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `petg_general_0p4`: 4 walls, 5 top / 5 bottom layers, 25% gyroid infill.
- Supports: off. Bed adhesion: 5 mm outer brim after the exact PETG spool is qualified.
- Dimensional controls: Use only with same-spool coupons.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- FIXED-MAST FALLBACK ONLY: do not treat this plate as an arm-camera adapter. Keep the job on hold until the camera architecture revision explicitly releases the fallback. Then measure camera thread direction, screw/head dimensions and safe engagement; check M5 ligaments, scales, strap slots, cable direction and no screw bottoming.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, modeled identity and revision before cleanup.
- Quarantine any warped, cracked, delaminated, under-extruded, bridged-shut or untraceable part; do not silently rework a critical fit.
- Intended gate(s) after objective acceptance: `camera_plate_hardware_pass`.

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

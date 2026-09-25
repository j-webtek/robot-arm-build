# Job 04A - Shared ABS compliant tool body with keyed cap and one spare cap

| Control field | Released value |
|---|---|
| Design revision | `RC03-INT-R1` |
| Lifecycle state | **UNRELEASED** |
| Route / stage | `any_tool_route` / `route` |
| Kit | `KIT-TOOL-COMMON` |
| Plate | `04A_ABS_shared_compliant_tool.3mf` |
| Plate SHA-256 | `91a9be9ec968c66b10543d13faae269d991b176fffd105d801a07f4a08107882` |
| Profile | `abs_rapido_precision_0p4` / `60827c142c2f8e88c0a45ace71712cf2c94f84d66dc796880352ab32de1e7195` |
| Exact settings sheet | `print_plates_3mf/04A_ABS_shared_compliant_tool.PRINT_SETTINGS.md` / `a5f98db5e0bd54f803e6b623cfd587be6cadb2b5f7ef55ea192664edb244027a` |
| QIDI process import | `slicer_profiles/QIDI_PLUS4/abs_rapido_precision_0p4.process.json` / `c115ad0ca8acafa86bc303973bbbae27578fdd57db8cbf437a7c8175710ba90a` |
| Filament preset | `qidi_abs_rapido_xplus4_0p4` / `ce549e11c71d71294ae086694987ac99842a14ba8fc26e24a879f7dd31b65bd4` |
| Preset completeness | **EXACT_REPRODUCIBLE** |
| Unresolved filament fields | None |
| Printer | QIDI Plus4; 305 x 305 x 280 mm nominal; 5 mm protected edge margin |
| Material / nozzle / layer | QIDI ABS Rapido / 0.4 mm / 0.16 mm |
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
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "provisional_protected_envelope_mm": [295, 295, 275]}` |
| `plus4_protected_envelope_verified` | **PASS** | `{"build_surface": "QIDI dual-sided textured PEI plate", "carriage_clearance_result": "PASS - protected envelope is inside official nominal volume", "enclosure_clearance_result": "PASS - operator confirmed completed printer qualification", "firmware_version": "Plus4_v1.7.1 official baseline; operator confirmed fully updated", "full_travel_test_result": "PASS - operator confirmed completed printer qualification", "printer_serial": "NOT_TRACKED_PROTOTYPE", "purge_and_exclusion_zone_result": "PASS - operator confirmed completed printer qualification", "verified_protected_envelope_mm": [295, 295, 275]}` |
| `nozzle_0p4_confirmed` | **PASS** | `{"installed_nozzle_mm": 0.4, "verification_method": "Official QIDI Plus4 standard specification and official printer.cfg; operator confirmed printer configuration"}` |
| `abs_rapido_precision_profile_calibrated` | **PASS** | `{"brand": "QIDI", "calibration_result": "PASS - operator confirmed the installed QIDI ABS Rapido preset and current native Job 00A slice; matching coupons provide dimensional release", "chamber_condition": "QIDI Plus4 enclosure sealed; 55 C chamber target from the installed QIDI ABS Rapido preset", "drying_record": "Operator confirmed print-ready; detailed drying record waived for prototype coupons", "filament_name": "ABS Rapido", "profile_revision": "RC03-INT-R1 abs_rapido_precision_0p4 SHA256 60827c142c2f8e88c0a45ace71712cf2c94f84d66dc796880352ab32de1e7195", "spool_lot": "NOT_TRACKED_PROTOTYPE"}` |
| `compliant_tool_m3_insert_coupon_pass` | **NOT_TESTED** | `{"insert_length_mm": null, "insert_od_mm": null, "installed_depth_mm": null, "retention_result": null, "selected_pocket_mm": null}` |
| `gripper_interface_measured` | **NOT_TESTED** | `{"jaw_opening_mm": null, "jaw_pad_height_mm": null, "jaw_pad_width_mm": null, "selected_grip_setting": null}` |
| `gripper_coupon_pass` | **NOT_TESTED** | `{"crush_result": null, "selected_grip_setting": null, "shim_each_side_mm": null, "slip_result": null}` |
| `spring_dimensions_measured` | **NOT_TESTED** | `{"approx_rate_n_per_mm": null, "coil_bind_length_mm": null, "free_length_mm": null, "id_mm": null, "od_mm": null}` |
| `spring_fit_coupon_pass` | **NOT_TESTED** | `{"binding_result": null, "cup_fit_result": null, "post_fit_result": null, "selected_step_mm": null}` |
| `precision_m3_head_coupon_pass` | **NOT_TESTED** | `{"fit_result": null, "m3_head_recess_d_mm": null, "screw_head_d_mm": null}` |
| `geometry_matches_measurements` | **PASS** | `{"affected_parts_reviewed": true, "design_revision": "RC03-INT-R1", "effective_parameters_file": "config/parameters.json", "measurement_record_revision": "2026-09-06_JOB03C1_REWORK", "regeneration_completed": true}` |
| `qidi_studio_roundtrip_confirmed` | **NOT_TESTED** | `{"critical_layer_preview_pass_by_job": {}, "evidence_reference_by_job": {}, "geometry_scale_percent_by_job": {}, "native_project_sha256_by_job": {}, "object_count_by_job": {}, "qidi_studio_version": null, "saved_profile_revision_by_job": {}, "validated_job_ids": []}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: Two M3 inserts, two M3x10 screws, accepted spring, route adapter.
- Open `print_plates_3mf/04A_ABS_shared_compliant_tool.PRINT_SETTINGS.md` and follow every exact value in it.
- Import `slicer_profiles/QIDI_PLUS4/abs_rapido_precision_0p4.process.json` and select `QIDI ABS Rapido @Qidi X-Plus 4 0.4 nozzle` as the separate filament preset.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `abs_rapido_precision_0p4`: 5 walls, 6 top / 6 bottom layers, 40% gyroid infill.
- Supports: off. Bed adhesion: 5 mm outer brim with 0.05 mm object gap on clean textured PEI.
- Dimensional controls: Keep the seam off gripper flats, spring seats, insert pockets, and the sliding guide bore; zero XY compensation pending Job 00C.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- Inspect body straightness, grip flats, guide bore, spring chamber and keyed locator. Install inserts square; cap must seat only in the keyed orientation. Verify 3-6 mm smooth return after route assembly.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, modeled identity and revision before cleanup.
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

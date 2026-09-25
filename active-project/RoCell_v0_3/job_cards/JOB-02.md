# Job 02 - ABS right slave keyboard station located from the accepted left-station seam

| Control field | Released value |
|---|---|
| Design revision | `RC03-INT-R1` |
| Lifecycle state | **UNRELEASED** |
| Route / stage | `required` / `production` |
| Kit | `KIT-KB` |
| Plate | `02_ABS_keyboard_station_right.3mf` |
| Plate SHA-256 | `bc8e2fffd5f004678e47ac33c5fca41b3366cab17931cbcd5565f9bf9c2969d0` |
| Profile | `abs_rapido_tray_structural_0p4` / `4cc77d229e3f397c7f8d7c1a793ace5ba9490cafe2ef9d31f16e7ffa4c28123f` |
| Exact settings sheet | `print_plates_3mf/02_ABS_keyboard_station_right.PRINT_SETTINGS.md` / `e384ebb2785694ebef13fdbcedf547ea7c1730028a0b115350ac93b1d78c7b3e` |
| QIDI process import | `slicer_profiles/QIDI_PLUS4/abs_rapido_tray_structural_0p4.process.json` / `c89e92d6af33cb676d7200e34937ec05c7cec9b55f2d0700b07b89a57cbd81c6` |
| Filament preset | `qidi_abs_rapido_xplus4_0p4` / `ce549e11c71d71294ae086694987ac99842a14ba8fc26e24a879f7dd31b65bd4` |
| Preset completeness | **EXACT_REPRODUCIBLE** |
| Unresolved filament fields | None |
| Printer | QIDI Plus4; 305 x 305 x 280 mm nominal; 5 mm protected edge margin |
| Material / nozzle / layer | QIDI ABS Rapido / 0.4 mm / 0.20 mm |
| Plate envelope | 162.5 x 192.0 x 7.0 mm; centered |
| Native slice record | QIDI Studio version, sliced mass and time: ____________________ |

## Objects and orientation

| STL | Qty | Locked orientation | Source SHA-256 |
|---|---:|---|---|
| `keyboard_station_right.stl` | 1 | Flat, exported base on bed; RC03-R/slave and seam-reference labels readable on top | `bc9cc0d252da8d1702c56bbd0afaf6ed79e5dd9891d121dd54372e4692675cf0` |

## Required gates

| Gate | Status | Recorded values |
|---|---|---|
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "provisional_protected_envelope_mm": [295, 295, 275]}` |
| `plus4_protected_envelope_verified` | **PASS** | `{"build_surface": "QIDI dual-sided textured PEI plate", "carriage_clearance_result": "PASS - protected envelope is inside official nominal volume", "enclosure_clearance_result": "PASS - operator confirmed completed printer qualification", "firmware_version": "Plus4_v1.7.1 official baseline; operator confirmed fully updated", "full_travel_test_result": "PASS - operator confirmed completed printer qualification", "printer_serial": "NOT_TRACKED_PROTOTYPE", "purge_and_exclusion_zone_result": "PASS - operator confirmed completed printer qualification", "verified_protected_envelope_mm": [295, 295, 275]}` |
| `nozzle_0p4_confirmed` | **PASS** | `{"installed_nozzle_mm": 0.4, "verification_method": "Official QIDI Plus4 standard specification and official printer.cfg; operator confirmed printer configuration"}` |
| `abs_rapido_tray_profile_calibrated` | **PASS** | `{"brand": "QIDI", "calibration_result": "PASS - operator confirmed the installed QIDI ABS Rapido preset and current native Job 00A slice; matching coupons provide dimensional release", "chamber_condition": "QIDI Plus4 enclosure sealed; 55 C chamber target from the installed QIDI ABS Rapido preset", "drying_record": "Operator confirmed print-ready; detailed drying record waived for prototype coupons", "filament_name": "ABS Rapido", "profile_revision": "RC03-INT-R1 abs_rapido_tray_structural_0p4 SHA256 4cc77d229e3f397c7f8d7c1a793ace5ba9490cafe2ef9d31f16e7ffa4c28123f", "spool_lot": "NOT_TRACKED_PROTOTYPE"}` |
| `keyboard_dimensions_measured` | **NOT_TESTED** | `{"cable_keepout_mm": null, "depth_mm": null, "device_model": null, "height_mm": null, "width_mm": null}` |
| `keyboard_corner_coupon_pass` | **PASS** | `{"fit_result": "PASS - corner seated within both datum walls without force; keyboard remained level with no observed binding or interference (operator verified)", "selected_compensation_mm": 0.0}` |
| `keyboard_seam_coupon_pass` | **NOT_TESTED** | `{"fit_result": null, "printed_post_diameter_mm": null, "rocking_or_yaw_result": null, "selected_radial_slot_width_mm": null, "selected_round_socket_mm": null, "tool_free_release_result": null}` |
| `keyboard_station_registration_coupon_pass` | **PASS** | `{"actual_pin_diameter_measurements_mm": ["6.0 nominal \u2014 not caliper-measured under prototype waiver"], "crack_or_whitening_result": "PASS \u2014 none visible in retained round-hole photo and none reported for slot fit", "insertion_removal_cycles": "WAIVED \u2014 round and slot were each functionally checked by hand; 20 repeated cycles not performed", "inversion_retention_result": "WAIVED \u2014 inversion retention test not performed for this prototype", "lateral_play_mm": "NOT MEASURED \u2014 operator accepted functional fit under prototype waiver", "selected_radial_slot_length_mm": 10.0, "selected_radial_slot_width_mm": 6.2, "selected_round_socket_mm": 6.2}` |
| `tray_clearance_holes_coupon_pass` | **PASS** | `{"board_screw_major_diameter_mm": 4.0, "m4_washer_od_mm": 9.2, "smallest_free_hole_mm": 4.4, "washer_fit_result": "PASS - actual M4 production washer fits all candidates; operator selected the photographed/current production OD9.2 recess for service margin and easy assembly"}` |
| `geometry_matches_measurements` | **PASS** | `{"affected_parts_reviewed": true, "design_revision": "RC03-INT-R1", "effective_parameters_file": "config/parameters.json", "measurement_record_revision": "2026-09-06_JOB03C1_REWORK", "regeneration_completed": true}` |
| `keyboard_left_first_article_pass` | **NOT_TESTED** | `{"datum_surface_result": null, "flatness_mm": null, "job_id": null, "seam_key_result": null, "slot_fit_result": null, "washer_track_result": null}` |
| `qidi_studio_roundtrip_confirmed` | **NOT_TESTED** | `{"critical_layer_preview_pass_by_job": {}, "evidence_reference_by_job": {}, "geometry_scale_percent_by_job": {}, "native_project_sha256_by_job": {}, "object_count_by_job": {}, "qidi_studio_version": null, "saved_profile_revision_by_job": {}, "validated_job_ids": []}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: Accepted left station, keyboard, three temporary/production M4 station screws and washers, seam keys.
- Open `print_plates_3mf/02_ABS_keyboard_station_right.PRINT_SETTINGS.md` and follow every exact value in it.
- Import `slicer_profiles/QIDI_PLUS4/abs_rapido_tray_structural_0p4.process.json` and select `QIDI ABS Rapido @Qidi X-Plus 4 0.4 nozzle` as the separate filament preset.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `abs_rapido_tray_structural_0p4`: 5 walls, 6 top / 6 bottom layers, 35% gyroid infill.
- Supports: off. Bed adhesion: 8 mm outer brim with 0.05 mm object gap; clean textured PEI; one production station per plate.
- Dimensional controls: Keep the slicer seam away from locator sockets, relieved hold-down holes, seam datums, clamp guides, and keyboard contact datums; zero XY compensation pending Job 00A.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- Repeat first-article checks; mate the slave to the accepted master without an independent pin pair; record seam gap, flushness, support plane, continuous base contact and rocking. Complete ten station removal/reinstall cycles after board installation.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, modeled identity and revision before cleanup.
- Quarantine any warped, cracked, delaminated, under-extruded, bridged-shut or untraceable part; do not silently rework a critical fit.
- Intended gate(s) after objective acceptance: `keyboard_station_pair_postprint_pass`, `station_remove_reinstall_repeatability_pass`, `keyboard_fixture_assembly_pass`.

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

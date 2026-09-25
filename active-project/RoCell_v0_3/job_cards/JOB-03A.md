# Job 03A - Integrated ABS phone and TCP service station with fixed datums, keyed receiver, and replaceable-rail interface

| Control field | Released value |
|---|---|
| Design revision | `RC03-INT-R1` |
| Lifecycle state | **UNRELEASED** |
| Route / stage | `required` / `first_article` |
| Kit | `KIT-PHONE` |
| Plate | `03A_ABS_phone_TCP_station.3mf` |
| Plate SHA-256 | `63cf85413ed08193b08445859bfcc8116c2e47064f2a086fdbfdb8bd7339e565` |
| Profile | `abs_rapido_cradle_0p4` / `0dca510bbadec73f611b731a8fd24f22310b3ba113759f58f0ed7f1cdc33c545` |
| Exact settings sheet | `print_plates_3mf/03A_ABS_phone_TCP_station.PRINT_SETTINGS.md` / `c3fd921347d91842d1f16728e8e88a45d25a776aa3aedd6d8810c9db9773c7b9` |
| QIDI process import | `slicer_profiles/QIDI_PLUS4/abs_rapido_cradle_0p4.process.json` / `9276ce2983256d815925224e7d8fc45032a531678dc336713fc88fa96137e259` |
| Filament preset | `qidi_abs_rapido_xplus4_0p4` / `ce549e11c71d71294ae086694987ac99842a14ba8fc26e24a879f7dd31b65bd4` |
| Preset completeness | **EXACT_REPRODUCIBLE** |
| Unresolved filament fields | None |
| Printer | QIDI Plus4; 305 x 305 x 280 mm nominal; 5 mm protected edge margin |
| Material / nozzle / layer | QIDI ABS Rapido / 0.4 mm / 0.20 mm |
| Plate envelope | 186.3 x 172.8 x 10.5 mm; centered |
| Native slice record | QIDI Studio version, sliced mass and time: ____________________ |

## Objects and orientation

| STL | Qty | Locked orientation | Source SHA-256 |
|---|---:|---|---|
| `phone_tcp_station.stl` | 1 | Flat base on bed; RC03 PHONE+TCP and TCP R3 readable; USB toward plate front and TOP toward plate rear | `63e02e28f9bb818007564eab7e82e2b9ce8417f30bdf3cbec3c3a86ec08ac32e` |

## Required gates

| Gate | Status | Recorded values |
|---|---|---|
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "provisional_protected_envelope_mm": [295, 295, 275]}` |
| `plus4_protected_envelope_verified` | **PASS** | `{"build_surface": "QIDI dual-sided textured PEI plate", "carriage_clearance_result": "PASS - protected envelope is inside official nominal volume", "enclosure_clearance_result": "PASS - operator confirmed completed printer qualification", "firmware_version": "Plus4_v1.7.1 official baseline; operator confirmed fully updated", "full_travel_test_result": "PASS - operator confirmed completed printer qualification", "printer_serial": "NOT_TRACKED_PROTOTYPE", "purge_and_exclusion_zone_result": "PASS - operator confirmed completed printer qualification", "verified_protected_envelope_mm": [295, 295, 275]}` |
| `nozzle_0p4_confirmed` | **PASS** | `{"installed_nozzle_mm": 0.4, "verification_method": "Official QIDI Plus4 standard specification and official printer.cfg; operator confirmed printer configuration"}` |
| `abs_rapido_cradle_profile_calibrated` | **PASS** | `{"brand": "QIDI", "calibration_result": "PASS - operator confirmed the installed QIDI ABS Rapido preset and current native Job 00A slice; matching coupons provide dimensional release", "chamber_condition": "QIDI Plus4 enclosure sealed; 55 C chamber target from the installed QIDI ABS Rapido preset", "drying_record": "Operator confirmed print-ready; detailed drying record waived for prototype coupons", "filament_name": "ABS Rapido", "profile_revision": "RC03-INT-R1 abs_rapido_cradle_0p4 SHA256 0dca510bbadec73f611b731a8fd24f22310b3ba113759f58f0ed7f1cdc33c545", "spool_lot": "NOT_TRACKED_PROTOTYPE"}` |
| `phone_dimensions_measured` | **NOT_TESTED** | `{"camera_bump_envelope_mm": null, "case_installed": null, "device_model": null, "length_mm": null, "thickness_mm": null, "width_mm": null}` |
| `phone_side_features_measured` | **NOT_TESTED** | `{"approved_clearance_limit_id": null, "clearance_measurement_uncertainty_mm": null, "minimum_keepout_margin_mm": null, "right_side_keepouts_from_bottom_mm": null, "selected_clamp_centers_from_bottom_mm": null}` |
| `phone_cable_measured` | **NOT_TESTED** | `{"connector_thickness_mm": null, "connector_width_mm": null, "minimum_bend_radius_mm": null, "selected_tie_width_mm": null, "straight_projection_mm": null}` |
| `phone_width_coupon_pass` | **PASS** | `{"fit_result": "PASS_BARE_PHONE_SEATS_BY_HAND_COUPON_IS_WIDTH_AND_RAIL_HEIGHT_ONLY", "lateral_clearance_mm": 1.5, "rail_height_result": "PASS_RAILS_VISIBLY_BELOW_SCREEN_FACE"}` |
| `phone_station_registration_coupon_pass` | **PASS** | `{"actual_pin_diameter_measurements_mm": ["6.0 nominal - not caliper-measured under prototype waiver"], "crack_or_whitening_result": "PASS_NONE_REPORTED", "insertion_removal_cycles": "WAIVED_FUNCTIONAL_HAND_FIT_CONFIRMED", "inversion_retention_result": "WAIVED_FOR_PROTOTYPE", "lateral_play_mm": "NOT_NUMERICALLY_MEASURED_FUNCTIONAL_FIT_ACCEPTED", "selected_radial_slot_length_mm": 10.0, "selected_radial_slot_width_mm": 6.2, "selected_round_socket_mm": 6.2}` |
| `phone_m4_captive_nut_coupon_pass` | **FAIL** | `{"actual_nut_across_flats_mm": "NOT_CALIPER_MEASURED_STANDARD_M4_NUT", "actual_nut_thickness_mm": "NOT_CALIPER_MEASURED_STANDARD_M4_NUT", "horizontal_screw_axis_result": "FAIL_SCREW_DID_NOT_ENGAGE_RELIABLY", "installation_result": "FAIL_NUT_DROPS_IN_WITH_EXCESSIVE_CLEARANCE", "selected_channel_across_flats_mm": 7.4, "selected_channel_depth_mm": 3.55, "spin_result_after_20_cycles": "FAIL_TOO_LOOSE_TO_COMPLETE_CYCLE_TEST"}` |
| `phone_station_m3_insert_coupon_pass` | **NOT_TESTED** | `{"insert_length_mm": null, "insert_od_mm": null, "installed_depth_mm": null, "retention_result": null, "selected_pocket_mm": null}` |
| `cable_tie_saddle_coupon_pass` | **FAIL** | `{"cable_clearance_result": "NOT_TESTABLE_BECAUSE_TIE_DID_NOT_FEED", "feed_result": "FAIL_SELECTED_WIDER_TIE_DID_NOT_PASS_LEGACY_SADDLE", "job_id": "00B_AS_BUILT_LEGACY_SCREENING", "saddle_crack_result": "PASS_NO_CRACK_VISIBLE_IN_PHOTOS", "selected_slot_width_mm": null, "selected_tie_width_mm": 4.8, "selected_tunnel_height_mm": 1.8, "tie_specification_basis": "OPERATOR_SELECTED_WIDER_NOMINAL_4P8_MM_TIE_CLASS_NOT_CALIPER_MEASURED"}` |
| `cradle_m4_washer_coupon_pass` | **PASS** | `{"actual_washer_od_mm": "NOT_CALIPER_MEASURED_PROTOTYPE_WAIVER", "fit_result": "PASS_MIDDLE_OD9.2_RECESS_LIES_FLAT_WITHOUT_FORCE", "m4_washer_od_mm": 9.2}` |
| `geometry_matches_measurements` | **PASS** | `{"affected_parts_reviewed": true, "design_revision": "RC03-INT-R1", "effective_parameters_file": "config/parameters.json", "measurement_record_revision": "2026-09-06_JOB03C1_REWORK", "regeneration_completed": true}` |
| `qidi_studio_roundtrip_confirmed` | **NOT_TESTED** | `{"critical_layer_preview_pass_by_job": {}, "evidence_reference_by_job": {}, "geometry_scale_percent_by_job": {}, "native_project_sha256_by_job": {}, "object_count_by_job": {}, "qidi_studio_version": null, "saved_profile_revision_by_job": {}, "validated_job_ids": []}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: Phone/case, cable, two 6 mm pins, three M4 station screws/washers, M3 inserts, accepted rail and TPU tips.
- Open `print_plates_3mf/03A_ABS_phone_TCP_station.PRINT_SETTINGS.md` and follow every exact value in it.
- Import `slicer_profiles/QIDI_PLUS4/abs_rapido_cradle_0p4.process.json` and select `QIDI ABS Rapido @Qidi X-Plus 4 0.4 nozzle` as the separate filament preset.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `abs_rapido_cradle_0p4`: 5 walls, 5 top / 5 bottom layers, 30% gyroid infill.
- Supports: off; stop and obtain engineering approval if the locked layer preview shows an unprintable tower. Bed adhesion: 8 mm outer brim with 0.05 mm object gap on clean textured PEI.
- Dimensional controls: Use the same-profile ABS locator, captive-M4, vertical-M3-insert, cable-saddle, and washer coupons; do not rework a released socket ad hoc.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- With the station off the wood board, inspect continuous base contact at all three retention zones, locator sockets, keyed TCP receiver, fixed phone datums, replaceable-rail interface and all keepouts; install the TCP inserts square. For final mounting, seat the accepted rail before the two shared rail/station screws and verify its cable saddle with the actual cable. Complete ten station and phone cycles without button or cable contact.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, modeled identity and revision before cleanup.
- Quarantine any warped, cracked, delaminated, under-extruded, bridged-shut or untraceable part; do not silently rework a critical fit.
- Intended gate(s) after objective acceptance: `phone_tcp_station_postprint_pass`, `station_remove_reinstall_repeatability_pass`, `phone_fixture_assembly_pass`.

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

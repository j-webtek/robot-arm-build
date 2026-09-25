# Job 03D - Two keyed ABS TCP datum cartridges: one selected INSTALL datum and one qualified recalibration-required SPARE

| Control field | Released value |
|---|---|
| Design revision | `RC03-INT-R1` |
| Lifecycle state | **UNRELEASED** |
| Route / stage | `required` / `first_article` |
| Kit | `KIT-PUCK` |
| Plate | `03D_ABS_TCP_datum_cartridges.3mf` |
| Plate SHA-256 | `597423729e6d84ed39847ef9093fec57dcce2d5a51fee3c1bf17228d5045c8f7` |
| Profile | `abs_rapido_calibration_0p4` / `f3c6513d491cad5e3fc611549c640439ac58189ddea5c79fe01725e3a846b114` |
| Exact settings sheet | `print_plates_3mf/03D_ABS_TCP_datum_cartridges.PRINT_SETTINGS.md` / `3e05dc8654924984aeb3fba467e18864eb5797ea8703391043aee9a286f29546` |
| QIDI process import | `slicer_profiles/QIDI_PLUS4/abs_rapido_calibration_0p4.process.json` / `c069454369dc8abe726d0db4359928e9fa870c694cdfdf7b044a3debeeb2d564` |
| Filament preset | `qidi_abs_rapido_xplus4_0p4` / `ce549e11c71d71294ae086694987ac99842a14ba8fc26e24a879f7dd31b65bd4` |
| Preset completeness | **EXACT_REPRODUCIBLE** |
| Unresolved filament fields | None |
| Printer | QIDI Plus4; 305 x 305 x 280 mm nominal; 5 mm protected edge margin |
| Material / nozzle / layer | QIDI ABS Rapido / 0.4 mm / 0.16 mm |
| Plate envelope | 72.0 x 30.0 x 4.0 mm; centered |
| Native slice record | QIDI Studio version, sliced mass and time: ____________________ |

## Objects and orientation

| STL | Qty | Locked orientation | Source SHA-256 |
|---|---:|---|---|
| `calibration_puck.stl` | 2 | Flat as exported; crosshair upward; ironing off | `3d232103d1cc89d083cc700526abe40344db3f34f80609a5f134cb37a9247ce6` |

## Required gates

| Gate | Status | Recorded values |
|---|---|---|
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "provisional_protected_envelope_mm": [295, 295, 275]}` |
| `plus4_protected_envelope_verified` | **PASS** | `{"build_surface": "QIDI dual-sided textured PEI plate", "carriage_clearance_result": "PASS - protected envelope is inside official nominal volume", "enclosure_clearance_result": "PASS - operator confirmed completed printer qualification", "firmware_version": "Plus4_v1.7.1 official baseline; operator confirmed fully updated", "full_travel_test_result": "PASS - operator confirmed completed printer qualification", "printer_serial": "NOT_TRACKED_PROTOTYPE", "purge_and_exclusion_zone_result": "PASS - operator confirmed completed printer qualification", "verified_protected_envelope_mm": [295, 295, 275]}` |
| `nozzle_0p4_confirmed` | **PASS** | `{"installed_nozzle_mm": 0.4, "verification_method": "Official QIDI Plus4 standard specification and official printer.cfg; operator confirmed printer configuration"}` |
| `abs_rapido_calibration_profile_calibrated` | **PASS** | `{"brand": "QIDI", "calibration_result": "PASS - operator confirmed the installed QIDI ABS Rapido preset and current native Job 00A slice; matching coupons provide dimensional release", "chamber_condition": "QIDI Plus4 enclosure sealed; 55 C chamber target from the installed QIDI ABS Rapido preset", "drying_record": "Operator confirmed print-ready; detailed drying record waived for prototype coupons", "filament_name": "ABS Rapido", "profile_revision": "RC03-INT-R1 abs_rapido_calibration_0p4 SHA256 f3c6513d491cad5e3fc611549c640439ac58189ddea5c79fe01725e3a846b114", "spool_lot": "NOT_TRACKED_PROTOTYPE"}` |
| `calibration_clearance_holes_coupon_pass` | **NOT_TESTED** | `{"fit_result": null, "m3_head_recess_d_mm": null, "m3_screw_major_diameter_mm": null, "screw_head_d_mm": null, "smallest_free_hole_mm": null}` |
| `phone_station_registration_coupon_pass` | **PASS** | `{"actual_pin_diameter_measurements_mm": ["6.0 nominal - not caliper-measured under prototype waiver"], "crack_or_whitening_result": "PASS_NONE_REPORTED", "insertion_removal_cycles": "WAIVED_FUNCTIONAL_HAND_FIT_CONFIRMED", "inversion_retention_result": "WAIVED_FOR_PROTOTYPE", "lateral_play_mm": "NOT_NUMERICALLY_MEASURED_FUNCTIONAL_FIT_ACCEPTED", "selected_radial_slot_length_mm": 10.0, "selected_radial_slot_width_mm": 6.2, "selected_round_socket_mm": 6.2}` |
| `geometry_matches_measurements` | **PASS** | `{"affected_parts_reviewed": true, "design_revision": "RC03-INT-R1", "effective_parameters_file": "config/parameters.json", "measurement_record_revision": "2026-09-06_JOB03C1_REWORK", "regeneration_completed": true}` |
| `qidi_studio_roundtrip_confirmed` | **NOT_TESTED** | `{"critical_layer_preview_pass_by_job": {}, "evidence_reference_by_job": {}, "geometry_scale_percent_by_job": {}, "native_project_sha256_by_job": {}, "object_count_by_job": {}, "qidi_studio_version": null, "saved_profile_revision_by_job": {}, "validated_job_ids": []}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: Accepted phone/TCP station, two M3 screws, straightedge and depth/height gauge.
- Open `print_plates_3mf/03D_ABS_TCP_datum_cartridges.PRINT_SETTINGS.md` and follow every exact value in it.
- Import `slicer_profiles/QIDI_PLUS4/abs_rapido_calibration_0p4.process.json` and select `QIDI ABS Rapido @Qidi X-Plus 4 0.4 nozzle` as the separate filament preset.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `abs_rapido_calibration_0p4`: 4 walls, 6 top / 6 bottom layers, 40% gyroid infill.
- Supports: off. Bed adhesion: 5 mm outer brim with 0.05 mm object gap on clean textured PEI.
- Dimensional controls: No ironing over crosshairs or divots; seam away from keyed receiver faces; zero XY compensation pending Job 00F.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- Keep slicer object calibration_puck_1 as 03D-A and calibration_puck_2 as 03D-B. Qualify each separately; both must have an intact crosshair/divot, no more than 0.15 mm lateral play, and no more than 0.10 mm mounted-height range over ten cycles. For each, calculate score = max(play / 0.15, height range / 0.10). Label the lower-score cartridge INSTALL; if tied at measuring resolution, choose the lower height range, then 03D-A. Label the other accepted cartridge SPARE - TCP RECALIBRATION REQUIRED.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, modeled identity and revision before cleanup.
- Quarantine any warped, cracked, delaminated, under-extruded, bridged-shut or untraceable part; do not silently rework a critical fit.
- Intended gate(s) after objective acceptance: `calibration_puck_datum_pass`.

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

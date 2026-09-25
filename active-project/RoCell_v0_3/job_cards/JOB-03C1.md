# Job 03C1 - Production-equivalent ABS phone keeper and clamp-tower rail that qualifies the revised captive-nut seats and adopted wide-tie saddle before Job 03A

| Control field | Released value |
|---|---|
| Design revision | `RC03-INT-R1` |
| Lifecycle state | **UNRELEASED** |
| Route / stage | `required` / `first_article` |
| Kit | `KIT-PHONE` |
| Plate | `03C1_ABS_phone_clamp_rail.3mf` |
| Plate SHA-256 | `e992ea3f29097bd346095a5c5ac08c33c9e2d35d7e9c27bce6041e43e3a9ef39` |
| Profile | `abs_rapido_cradle_0p4` / `0dca510bbadec73f611b731a8fd24f22310b3ba113759f58f0ed7f1cdc33c545` |
| Exact settings sheet | `print_plates_3mf/03C1_ABS_phone_clamp_rail.PRINT_SETTINGS.md` / `0a0a5ea8323faf956099084619fece6f7c8e879f6d7ae8baa2aff406effec156` |
| QIDI process import | `slicer_profiles/QIDI_PLUS4/abs_rapido_cradle_0p4.process.json` / `9276ce2983256d815925224e7d8fc45032a531678dc336713fc88fa96137e259` |
| Filament preset | `qidi_abs_rapido_xplus4_0p4` / `ce549e11c71d71294ae086694987ac99842a14ba8fc26e24a879f7dd31b65bd4` |
| Preset completeness | **EXACT_REPRODUCIBLE** |
| Unresolved filament fields | None |
| Printer | QIDI Plus4; 305 x 305 x 280 mm nominal; 5 mm protected edge margin |
| Material / nozzle / layer | QIDI ABS Rapido / 0.4 mm / 0.20 mm |
| Plate envelope | 19.2 x 172.8 x 16.0 mm; centered |
| Native slice record | QIDI Studio version, sliced mass and time: ____________________ |

## Objects and orientation

| STL | Qty | Locked orientation | Source SHA-256 |
|---|---:|---|---|
| `phone_clamp_rail.stl` | 1 | Flat station-facing ledge on bed; clamp towers upward | `f766a24143f11769a0bcef7236b09938f4c02434b3b5d8e6d77b21b37f49dcff` |

## Required gates

| Gate | Status | Recorded values |
|---|---|---|
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "provisional_protected_envelope_mm": [295, 295, 275]}` |
| `plus4_protected_envelope_verified` | **PASS** | `{"build_surface": "QIDI dual-sided textured PEI plate", "carriage_clearance_result": "PASS - protected envelope is inside official nominal volume", "enclosure_clearance_result": "PASS - operator confirmed completed printer qualification", "firmware_version": "Plus4_v1.7.1 official baseline; operator confirmed fully updated", "full_travel_test_result": "PASS - operator confirmed completed printer qualification", "printer_serial": "NOT_TRACKED_PROTOTYPE", "purge_and_exclusion_zone_result": "PASS - operator confirmed completed printer qualification", "verified_protected_envelope_mm": [295, 295, 275]}` |
| `nozzle_0p4_confirmed` | **PASS** | `{"installed_nozzle_mm": 0.4, "verification_method": "Official QIDI Plus4 standard specification and official printer.cfg; operator confirmed printer configuration"}` |
| `abs_rapido_cradle_profile_calibrated` | **PASS** | `{"brand": "QIDI", "calibration_result": "PASS - operator confirmed the installed QIDI ABS Rapido preset and current native Job 00A slice; matching coupons provide dimensional release", "chamber_condition": "QIDI Plus4 enclosure sealed; 55 C chamber target from the installed QIDI ABS Rapido preset", "drying_record": "Operator confirmed print-ready; detailed drying record waived for prototype coupons", "filament_name": "ABS Rapido", "profile_revision": "RC03-INT-R1 abs_rapido_cradle_0p4 SHA256 0dca510bbadec73f611b731a8fd24f22310b3ba113759f58f0ed7f1cdc33c545", "spool_lot": "NOT_TRACKED_PROTOTYPE"}` |
| `phone_width_coupon_pass` | **PASS** | `{"fit_result": "PASS_BARE_PHONE_SEATS_BY_HAND_COUPON_IS_WIDTH_AND_RAIL_HEIGHT_ONLY", "lateral_clearance_mm": 1.5, "rail_height_result": "PASS_RAILS_VISIBLY_BELOW_SCREEN_FACE"}` |
| `cradle_m4_washer_coupon_pass` | **PASS** | `{"actual_washer_od_mm": "NOT_CALIPER_MEASURED_PROTOTYPE_WAIVER", "fit_result": "PASS_MIDDLE_OD9.2_RECESS_LIES_FLAT_WITHOUT_FORCE", "m4_washer_od_mm": 9.2}` |
| `geometry_matches_measurements` | **PASS** | `{"affected_parts_reviewed": true, "design_revision": "RC03-INT-R1", "effective_parameters_file": "config/parameters.json", "measurement_record_revision": "2026-09-06_JOB03C1_REWORK", "regeneration_completed": true}` |
| `qidi_studio_roundtrip_confirmed` | **NOT_TESTED** | `{"critical_layer_preview_pass_by_job": {}, "evidence_reference_by_job": {}, "geometry_scale_percent_by_job": {}, "native_project_sha256_by_job": {}, "object_count_by_job": {}, "qidi_studio_version": null, "saved_profile_revision_by_job": {}, "validated_job_ids": []}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: Actual phone, USB cable, nominal 4.8 mm project tie, two standard M4 hex nuts and M4 clamp screws; accepted station and TPU tips only for the later seating stage.
- Open `print_plates_3mf/03C1_ABS_phone_clamp_rail.PRINT_SETTINGS.md` and follow every exact value in it.
- Import `slicer_profiles/QIDI_PLUS4/abs_rapido_cradle_0p4.process.json` and select `QIDI ABS Rapido @Qidi X-Plus 4 0.4 nozzle` as the separate filament preset.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `abs_rapido_cradle_0p4`: 5 walls, 5 top / 5 bottom layers, 30% gyroid infill.
- Supports: off; stop and obtain engineering approval if the locked layer preview shows an unprintable tower. Bed adhesion: 8 mm outer brim with 0.05 mm object gap on clean textured PEI.
- Dimensional controls: Use the same-profile ABS locator, captive-M4, vertical-M3-insert, cable-saddle, and washer coupons; do not rework a released socket ad hoc.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- First bench-qualify both redesigned 7.2 mm lower-half hex seats: each screw must catch at least three full turns and neither nut may spin through 20 cycles. Feed the project tie around the actual cable through the 5.6 x 2.2 mm saddle and confirm no cracking. After Job 03A exists, inspect rail seating, tower ligaments, clamp-axis keepouts and service replacement.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, modeled identity and revision before cleanup.
- Quarantine any warped, cracked, delaminated, under-extruded, bridged-shut or untraceable part; do not silently rework a critical fit.
- Intended gate(s) after objective acceptance: `phone_m4_captive_nut_coupon_pass`, `cable_tie_saddle_coupon_pass`, `phone_clamp_rail_first_article_pass`, `phone_fixture_assembly_pass`.

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

# Job 07A - First fixed-mast fallback foot with rear-lug clamp bolts; not part of the intended arm-mounted camera architecture

| Control field | Released value |
|---|---|
| Design revision | `RC03-INT-R1` |
| Lifecycle state | **UNRELEASED** |
| Route / stage | `camera_mast_optional` / `first_article` |
| Kit | `KIT-MAST` |
| Plate | `07A_ASA_mast_foot_first_article.3mf` |
| Plate SHA-256 | `fe98242302efb943e0fba6fb4db4e38f0008ecda19e306688be844dd162af84a` |
| Profile | `asa_structural_0p4` / `f1e5cb6562054f5363ffbb34572181e1e52fad37aea3595c4a7c5a9cfa8ec7c9` |
| Exact settings sheet | `print_plates_3mf/07A_ASA_mast_foot_first_article.PRINT_SETTINGS.md` / `e8d47f729bd0c125a7e9804dac2f342484c0f536f0c5f83a1bffeab28398e7ff` |
| QIDI process import | `slicer_profiles/QIDI_PLUS4/asa_structural_0p4.process.json` / `a6116150e09eb3212b6d4d76b7def11495593f564f497d2e8e5799ec6e69f7de` |
| Filament preset | `exact_asa_spool_xplus4_0p4` / `568d1ecd4a7a2acf80e0789ea89a8513e51af7d415c8d0e24041669682cb5953` |
| Preset completeness | **EXACT_PROCESS_SPOOL_PRESET_REQUIRED** |
| Unresolved filament fields | nozzle temperature, bed temperature, chamber temperature, flow ratio, pressure advance, maximum volumetric speed, cooling |
| Printer | QIDI Plus4; 305 x 305 x 280 mm nominal; 5 mm protected edge margin |
| Material / nozzle / layer | ASA / 0.4 mm / 0.24 mm |
| Plate envelope | 92.0 x 92.0 x 74.0 mm; centered |
| Native slice record | QIDI Studio version, sliced mass and time: ____________________ |

## Objects and orientation

| STL | Qty | Locked orientation | Source SHA-256 |
|---|---:|---|---|
| `mast_foot_2020.stl` | 1 | Flat 92 x 92 mm base on bed; socket vertical | `2b6384b63a5b191ef88ae5590b50ffb5cd0c64d2102b3145b8336b2fb901faa5` |

## Required gates

| Gate | Status | Recorded values |
|---|---|---|
| `fixed_camera_fallback_architecture_released` | **NOT_TESTED** | `{"architecture_decision_revision": null, "architecture_decision_sha256": null, "architecture_decision_status": null, "fallback_authorization_reference": null, "fixed_camera_fallback_authorized": null}` |
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "provisional_protected_envelope_mm": [295, 295, 275]}` |
| `plus4_protected_envelope_verified` | **PASS** | `{"build_surface": "QIDI dual-sided textured PEI plate", "carriage_clearance_result": "PASS - protected envelope is inside official nominal volume", "enclosure_clearance_result": "PASS - operator confirmed completed printer qualification", "firmware_version": "Plus4_v1.7.1 official baseline; operator confirmed fully updated", "full_travel_test_result": "PASS - operator confirmed completed printer qualification", "printer_serial": "NOT_TRACKED_PROTOTYPE", "purge_and_exclusion_zone_result": "PASS - operator confirmed completed printer qualification", "verified_protected_envelope_mm": [295, 295, 275]}` |
| `nozzle_0p4_confirmed` | **PASS** | `{"installed_nozzle_mm": 0.4, "verification_method": "Official QIDI Plus4 standard specification and official printer.cfg; operator confirmed printer configuration"}` |
| `asa_profile_calibrated` | **NOT_TESTED** | `{"brand": null, "calibration_result": null, "chamber_condition": null, "drying_record": null, "filament_name": null, "profile_revision": null, "spool_lot": null}` |
| `asa_mast_socket_coupon_pass` | **NOT_TESTED** | `{"extrusion_x_mm": null, "extrusion_y_mm": null, "fit_result": null, "selected_socket_mm": null}` |
| `asa_m5_nut_coupon_pass` | **NOT_TESTED** | `{"nut_across_flats_mm": null, "nut_thickness_mm": null, "retention_result": null, "selected_hex_mm": null}` |
| `asa_m5_clearance_coupon_pass` | **NOT_TESTED** | `{"bolt_major_diameter_mm": null, "m5_washer_fit_result": null, "m5_washer_od_mm": null, "selected_base_hole_mm": null, "selected_horizontal_hole_mm": null}` |
| `geometry_matches_measurements` | **PASS** | `{"affected_parts_reviewed": true, "design_revision": "RC03-INT-R1", "effective_parameters_file": "config/parameters.json", "measurement_record_revision": "2026-09-06_JOB03C1_REWORK", "regeneration_completed": true}` |
| `qidi_studio_roundtrip_confirmed` | **NOT_TESTED** | `{"critical_layer_preview_pass_by_job": {}, "evidence_reference_by_job": {}, "geometry_scale_percent_by_job": {}, "native_project_sha256_by_job": {}, "object_count_by_job": {}, "qidi_studio_version": null, "saved_profile_revision_by_job": {}, "validated_job_ids": []}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: One extrusion, two M5 clamp bolts/nuts, four base fasteners/washers.
- Open `print_plates_3mf/07A_ASA_mast_foot_first_article.PRINT_SETTINGS.md` and follow every exact value in it.
- Import `slicer_profiles/QIDI_PLUS4/asa_structural_0p4.process.json` and select `QIDI ASA @Qidi X-Plus 4 0.4 nozzle` as the separate filament preset.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `asa_structural_0p4`: 6 walls, 6 top / 6 bottom layers, 45% gyroid infill.
- Supports: off unless a released fallback revision approves build-plate-only support. Bed adhesion: 10 mm outer brim, enclosed printer, stable chamber, and no drafts.
- Dimensional controls: Use same-spool ASA socket and nut coupons before a full mast foot.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- Inspect layer bonding, flatness, socket, rear slit, lead-ins and rear-lug bolt path. Tighten bolts alternately; record grip, cracks and flatness immediately and after 24 hours.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, modeled identity and revision before cleanup.
- Quarantine any warped, cracked, delaminated, under-extruded, bridged-shut or untraceable part; do not silently rework a critical fit.
- Intended gate(s) after objective acceptance: `mast_foot_first_article_pass`.

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

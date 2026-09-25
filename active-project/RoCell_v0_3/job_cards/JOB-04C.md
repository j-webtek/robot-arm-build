# Job 04C - Two keyboard-route rod bushings for retention qualification and one spare

| Control field | Released value |
|---|---|
| Design revision | `RC03-INT-R1` |
| Lifecycle state | **UNRELEASED** |
| Route / stage | `keyboard_rod_route` / `route` |
| Kit | `KIT-TOOL-KB` |
| Plate | `04C_PETG_keyboard_rod_adapters.3mf` |
| Plate SHA-256 | `39b706d658b093fe29c7cd845412ba2082dacdb6cf321b97d9cb6209a5e81427` |
| Profile | `petg_adapter_0p4` / `ce4f08af3ad5623c70bc5bb65dc086ae69cb51b98410dd26e85dbd0c1f693747` |
| Exact settings sheet | `print_plates_3mf/04C_PETG_keyboard_rod_adapters.PRINT_SETTINGS.md` / `f4e96b64f789e345ba7dabbf4052e35498e57c95c64de12a87374e971eeb32fd` |
| QIDI process import | `slicer_profiles/QIDI_PLUS4/petg_adapter_0p4.process.json` / `0eac339f7768fb799fa420cd300710e080134d0c0737652fd9afd51d9bc4fa91` |
| Filament preset | `exact_petg_spool_xplus4_0p4` / `e4af446b19a2425a1f87b49feb022fb06e525dc92f670689940c8dade2908fc4` |
| Preset completeness | **EXACT_PROCESS_SPOOL_PRESET_REQUIRED** |
| Unresolved filament fields | nozzle temperature, bed temperature, chamber temperature, flow ratio, pressure advance, maximum volumetric speed, cooling |
| Printer | QIDI Plus4; 305 x 305 x 280 mm nominal; 5 mm protected edge margin |
| Material / nozzle / layer | PETG / 0.4 mm / 0.12 mm |
| Plate envelope | 38.5 x 13.5 x 38.8 mm; centered |
| Native slice record | QIDI Studio version, sliced mass and time: ____________________ |

## Objects and orientation

| STL | Qty | Locked orientation | Source SHA-256 |
|---|---:|---|---|
| `rod_bushing_6_to_9mm.stl` | 2 | Upright on flange with 8 mm brim | `c30bee2a303f025e94b21e1cf2c5639babbf5d75d3bb008711ea86b5e8160d63` |

## Required gates

| Gate | Status | Recorded values |
|---|---|---|
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "provisional_protected_envelope_mm": [295, 295, 275]}` |
| `plus4_protected_envelope_verified` | **PASS** | `{"build_surface": "QIDI dual-sided textured PEI plate", "carriage_clearance_result": "PASS - protected envelope is inside official nominal volume", "enclosure_clearance_result": "PASS - operator confirmed completed printer qualification", "firmware_version": "Plus4_v1.7.1 official baseline; operator confirmed fully updated", "full_travel_test_result": "PASS - operator confirmed completed printer qualification", "printer_serial": "NOT_TRACKED_PROTOTYPE", "purge_and_exclusion_zone_result": "PASS - operator confirmed completed printer qualification", "verified_protected_envelope_mm": [295, 295, 275]}` |
| `nozzle_0p4_confirmed` | **PASS** | `{"installed_nozzle_mm": 0.4, "verification_method": "Official QIDI Plus4 standard specification and official printer.cfg; operator confirmed printer configuration"}` |
| `petg_adapter_profile_calibrated` | **NOT_TESTED** | `{"brand": null, "calibration_result": null, "drying_record": null, "filament_name": null, "profile_revision": null, "spool_lot": null}` |
| `keyboard_rod_measured` | **NOT_TESTED** | `{"diameter_mm": null, "length_mm": null, "material": null, "measurement_locations": null}` |
| `adapter_retention_method_selected` | **NOT_TESTED** | `{"dry_fit_pull_result": null, "hardware_or_adhesive_spec": null, "plastic_compatibility_result": null, "removability_result": null, "retention_method": null, "route": null}` |
| `geometry_matches_measurements` | **PASS** | `{"affected_parts_reviewed": true, "design_revision": "RC03-INT-R1", "effective_parameters_file": "config/parameters.json", "measurement_record_revision": "2026-09-06_JOB03C1_REWORK", "regeneration_completed": true}` |
| `qidi_studio_roundtrip_confirmed` | **NOT_TESTED** | `{"critical_layer_preview_pass_by_job": {}, "evidence_reference_by_job": {}, "geometry_scale_percent_by_job": {}, "native_project_sha256_by_job": {}, "object_count_by_job": {}, "qidi_studio_version": null, "saved_profile_revision_by_job": {}, "validated_job_ids": []}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: Deburred 6 mm rod, selected retaining method, pull gauge.
- Open `print_plates_3mf/04C_PETG_keyboard_rod_adapters.PRINT_SETTINGS.md` and follow every exact value in it.
- Import `slicer_profiles/QIDI_PLUS4/petg_adapter_0p4.process.json` and select `Generic PETG @Qidi X-Plus 4 0.4 nozzle` as the separate filament preset.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `petg_adapter_0p4`: 4 walls, 5 top / 5 bottom layers, 100% rectilinear infill.
- Supports: off. Bed adhesion: 8 mm outer brim with 0.10 mm object gap after the exact PETG spool is qualified.
- Dimensional controls: Calibrate elephant-foot compensation so split bores remain open; never globally scale.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- Check bore and split, press fit without cracks, set 30-40 mm projection, then quantify pull retention and 24-hour creep. No radial M3 screw is permitted in the thin flange.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, modeled identity and revision before cleanup.
- Quarantine any warped, cracked, delaminated, under-extruded, bridged-shut or untraceable part; do not silently rework a critical fit.
- Intended gate(s) after objective acceptance: `rod_bushing_retention_pass`.

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

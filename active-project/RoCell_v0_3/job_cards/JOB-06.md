# Job 06 - Fixed-mast fallback 2020 socket and production-axis M5 nut/clearance/washer tests; blocked until the fallback architecture is explicitly released

| Control field | Released value |
|---|---|
| Design revision | `RC03-INT-R1` |
| Lifecycle state | **UNRELEASED** |
| Route / stage | `camera_mast_optional` / `diagnostic` |
| Kit | `KIT-MAST` |
| Plate | `06_ASA_mast_fit_tests.3mf` |
| Plate SHA-256 | `02525021bb7f82f1d5c04946222ef5d898551181deb6bedda3b60a54cede6daa` |
| Profile | `asa_structural_0p4` / `f1e5cb6562054f5363ffbb34572181e1e52fad37aea3595c4a7c5a9cfa8ec7c9` |
| Exact settings sheet | `print_plates_3mf/06_ASA_mast_fit_tests.PRINT_SETTINGS.md` / `a0201228b703bd3c1c282ab8fd0fd3124acebf9b68c1abbdbbf65ce502e3a461` |
| QIDI process import | `slicer_profiles/QIDI_PLUS4/asa_structural_0p4.process.json` / `a6116150e09eb3212b6d4d76b7def11495593f564f497d2e8e5799ec6e69f7de` |
| Filament preset | `exact_asa_spool_xplus4_0p4` / `568d1ecd4a7a2acf80e0789ea89a8513e51af7d415c8d0e24041669682cb5953` |
| Preset completeness | **EXACT_PROCESS_SPOOL_PRESET_REQUIRED** |
| Unresolved filament fields | nozzle temperature, bed temperature, chamber temperature, flow ratio, pressure advance, maximum volumetric speed, cooling |
| Printer | QIDI Plus4; 305 x 305 x 280 mm nominal; 5 mm protected edge margin |
| Material / nozzle / layer | ASA / 0.4 mm / 0.24 mm |
| Plate envelope | 146.0 x 90.0 x 30.0 mm; centered |
| Native slice record | QIDI Studio version, sliced mass and time: ____________________ |

## Objects and orientation

| STL | Qty | Locked orientation | Source SHA-256 |
|---|---:|---|---|
| `mast_socket_fit_test.stl` | 1 | Flat as exported; 20 mm socket engagement vertical | `3a8e939ae308baa04fda3891dfc8851a0a3b2caa9e2a91148414255e1114905b` |
| `m5_nut_trap_fit_gauge.stl` | 1 | Tall block as exported; production-axis traps horizontal | `a6a8dd06689060766bb31f7eca10e6910fb3313a758af185bcbcdfde3c40a01e` |

## Required gates

| Gate | Status | Recorded values |
|---|---|---|
| `fixed_camera_fallback_architecture_released` | **NOT_TESTED** | `{"architecture_decision_revision": null, "architecture_decision_sha256": null, "architecture_decision_status": null, "fallback_authorization_reference": null, "fixed_camera_fallback_authorized": null}` |
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "provisional_protected_envelope_mm": [295, 295, 275]}` |
| `plus4_protected_envelope_verified` | **PASS** | `{"build_surface": "QIDI dual-sided textured PEI plate", "carriage_clearance_result": "PASS - protected envelope is inside official nominal volume", "enclosure_clearance_result": "PASS - operator confirmed completed printer qualification", "firmware_version": "Plus4_v1.7.1 official baseline; operator confirmed fully updated", "full_travel_test_result": "PASS - operator confirmed completed printer qualification", "printer_serial": "NOT_TRACKED_PROTOTYPE", "purge_and_exclusion_zone_result": "PASS - operator confirmed completed printer qualification", "verified_protected_envelope_mm": [295, 295, 275]}` |
| `nozzle_0p4_confirmed` | **PASS** | `{"installed_nozzle_mm": 0.4, "verification_method": "Official QIDI Plus4 standard specification and official printer.cfg; operator confirmed printer configuration"}` |
| `asa_profile_calibrated` | **NOT_TESTED** | `{"brand": null, "calibration_result": null, "chamber_condition": null, "drying_record": null, "filament_name": null, "profile_revision": null, "spool_lot": null}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: Actual 2020 extrusion, M5 nuts/bolts/washers, calipers.
- Open `print_plates_3mf/06_ASA_mast_fit_tests.PRINT_SETTINGS.md` and follow every exact value in it.
- Import `slicer_profiles/QIDI_PLUS4/asa_structural_0p4.process.json` and select `QIDI ASA @Qidi X-Plus 4 0.4 nozzle` as the separate filament preset.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `asa_structural_0p4`: 6 walls, 6 top / 6 bottom layers, 45% gyroid infill.
- Supports: off unless a released fallback revision approves build-plate-only support. Bed adhesion: 10 mm outer brim, enclosed printer, stable chamber, and no drafts.
- Dimensional controls: Use same-spool ASA socket and nut coupons before a full mast foot.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- Measure extrusion X/Y at multiple points; record the 20 mm-engagement socket, horizontal nut trap, free-passing M5 bore and washer seat using the exact ASA lot.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, modeled identity and revision before cleanup.
- Quarantine any warped, cracked, delaminated, under-extruded, bridged-shut or untraceable part; do not silently rework a critical fit.
- Intended gate(s) after objective acceptance: `asa_mast_socket_coupon_pass`, `asa_m5_nut_coupon_pass`, `asa_m5_clearance_coupon_pass`.

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

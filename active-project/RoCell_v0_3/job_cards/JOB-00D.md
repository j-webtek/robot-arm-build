# Job 00D - Phone-stylus-route sliding-fit qualification using the exact adapter profile

| Control field | Released value |
|---|---|
| Design revision | `RC03-INT-R1` |
| Lifecycle state | **UNRELEASED** |
| Route / stage | `phone_stylus_route` / `diagnostic` |
| Kit | `KIT-CAL` |
| Plate | `00D_PETG_adapter_profile_fit_tests.3mf` |
| Plate SHA-256 | `bc6e9d9ec7a6702c2d640f1d43b68eec33864f6398adbb37bb6a0d5fc79f4642` |
| Profile | `petg_adapter_0p4` / `ce4f08af3ad5623c70bc5bb65dc086ae69cb51b98410dd26e85dbd0c1f693747` |
| Exact settings sheet | `print_plates_3mf/00D_PETG_adapter_profile_fit_tests.PRINT_SETTINGS.md` / `555dd4276ec5dc8cdda79dd8a9c845436e6d3b72e73449048f07954f2dd16bbb` |
| QIDI process import | `slicer_profiles/QIDI_PLUS4/petg_adapter_0p4.process.json` / `0eac339f7768fb799fa420cd300710e080134d0c0737652fd9afd51d9bc4fa91` |
| Filament preset | `exact_petg_spool_xplus4_0p4` / `e4af446b19a2425a1f87b49feb022fb06e525dc92f670689940c8dade2908fc4` |
| Preset completeness | **EXACT_PROCESS_SPOOL_PRESET_REQUIRED** |
| Unresolved filament fields | nozzle temperature, bed temperature, chamber temperature, flow ratio, pressure advance, maximum volumetric speed, cooling |
| Printer | QIDI Plus4; 305 x 305 x 280 mm nominal; 5 mm protected edge margin |
| Material / nozzle / layer | PETG / 0.4 mm / 0.12 mm |
| Plate envelope | 92.0 x 28.0 x 4.0 mm; centered |
| Native slice record | QIDI Studio version, sliced mass and time: ____________________ |

## Objects and orientation

| STL | Qty | Locked orientation | Source SHA-256 |
|---|---:|---|---|
| `stylus_diameter_gauge.stl` | 1 | Flat as exported; labels upward | `556c8114547de14b36d8990444de96f3229f99c93f6d06fb62216880c6f72c77` |

## Required gates

| Gate | Status | Recorded values |
|---|---|---|
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "provisional_protected_envelope_mm": [295, 295, 275]}` |
| `plus4_protected_envelope_verified` | **PASS** | `{"build_surface": "QIDI dual-sided textured PEI plate", "carriage_clearance_result": "PASS - protected envelope is inside official nominal volume", "enclosure_clearance_result": "PASS - operator confirmed completed printer qualification", "firmware_version": "Plus4_v1.7.1 official baseline; operator confirmed fully updated", "full_travel_test_result": "PASS - operator confirmed completed printer qualification", "printer_serial": "NOT_TRACKED_PROTOTYPE", "purge_and_exclusion_zone_result": "PASS - operator confirmed completed printer qualification", "verified_protected_envelope_mm": [295, 295, 275]}` |
| `nozzle_0p4_confirmed` | **PASS** | `{"installed_nozzle_mm": 0.4, "verification_method": "Official QIDI Plus4 standard specification and official printer.cfg; operator confirmed printer configuration"}` |
| `petg_adapter_profile_calibrated` | **NOT_TESTED** | `{"brand": null, "calibration_result": null, "drying_record": null, "filament_name": null, "profile_revision": null, "spool_lot": null}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: Measured stylus, selected removable retaining compound if needed, calipers.
- Open `print_plates_3mf/00D_PETG_adapter_profile_fit_tests.PRINT_SETTINGS.md` and follow every exact value in it.
- Import `slicer_profiles/QIDI_PLUS4/petg_adapter_0p4.process.json` and select `Generic PETG @Qidi X-Plus 4 0.4 nozzle` as the separate filament preset.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `petg_adapter_0p4`: 4 walls, 5 top / 5 bottom layers, 100% rectilinear infill.
- Supports: off. Bed adhesion: 8 mm outer brim with 0.10 mm object gap after the exact PETG spool is qualified.
- Dimensional controls: Calibrate elephant-foot compensation so split bores remain open; never globally scale.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- Select the smallest free-sliding stylus bore. Document dry-fit retention or the minimal plastics-compatible removable compound; final thin-collar pull/cycle testing remains mandatory.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, modeled identity and revision before cleanup.
- Quarantine any warped, cracked, delaminated, under-extruded, bridged-shut or untraceable part; do not silently rework a critical fit.
- Intended gate(s) after objective acceptance: `stylus_gauge_coupon_pass`, `adapter_retention_method_selected`.

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

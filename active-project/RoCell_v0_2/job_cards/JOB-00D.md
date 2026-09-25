# Job 00D - Stylus sliding-fit and horizontal thread-pilot tests using the exact adapter profile

| Control field | Released value |
|---|---|
| Design revision | `RC02-PRO-R1` |
| Lifecycle state | **UNRELEASED** |
| Route / stage | `required` / `diagnostic` |
| Kit | `KIT-CAL` |
| Plate | `00D_PETG_adapter_profile_fit_tests.3mf` |
| Plate SHA-256 | `cd8931b9b17661cafa9da8cdb222c6ac21634988b89676a45fe949d7b7bbcee2` |
| Profile | `petg_adapter_0p4` / `5addad813637abbe2dbc969afe8fde8637973498ff1f2439e590e070d62a2308` |
| Printer | QIDI Plus4; 305 x 305 x 280 mm nominal; 5 mm protected edge margin |
| Material / nozzle / layer | PETG / 0.4 mm / 0.12 mm |
| Plate envelope | 128.0 x 106.0 x 18.0 mm; centered |
| Native slice record | QIDI Studio version, sliced mass and time: ____________________ |

## Objects and orientation

| STL | Qty | Locked orientation | Source SHA-256 |
|---|---:|---|---|
| `stylus_diameter_gauge.stl` | 1 | Flat as exported; labels upward | `556c8114547de14b36d8990444de96f3229f99c93f6d06fb62216880c6f72c77` |
| `thread_pilot_fit_gauge.stl` | 1 | Tall block as exported; blind pilots horizontal | `308470eee0a96263d9e279bf6a6098d41f64eb7ce98f849e9a3de8e0435d06c7` |

## Required gates

| Gate | Status | Recorded values |
|---|---|---|
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "safe_plate_envelope_mm": [295, 295, 280]}` |
| `nozzle_0p4_confirmed` | **NOT_TESTED** | `{"installed_nozzle_mm": null, "verification_method": null}` |
| `petg_adapter_profile_calibrated` | **NOT_TESTED** | `{"brand": null, "calibration_result": null, "drying_record": null, "filament_name": null, "profile_revision": null, "spool_lot": null}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: Measured stylus, M2/M3 screws, driver, calipers.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `petg_adapter_0p4`: 4 walls, 5 top / 5 bottom layers, 100% rectilinear infill.
- Supports: off. Bed adhesion: Use an 8 mm brim for the upright rod bushing; skirt is sufficient for the short collar.
- Dimensional controls: Calibrate elephant-foot compensation so split bores remain open at the first layer.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- Select the smallest free-sliding stylus bore and usable thread pilot. The thick gauge selects a pilot only; final thin-collar pull/cycle testing remains mandatory.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, engraved identity and revision before cleanup.
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

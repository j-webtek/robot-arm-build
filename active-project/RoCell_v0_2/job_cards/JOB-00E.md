# Job 00E - General clearance, screw-head, washer, camera-hex, and TPU-retention setup tests

| Control field | Released value |
|---|---|
| Design revision | `RC02-PRO-R1` |
| Lifecycle state | **UNRELEASED** |
| Route / stage | `required` / `diagnostic` |
| Kit | `KIT-CAL` |
| Plate | `00E_PETG_general_setup_tests.3mf` |
| Plate SHA-256 | `b35f3c91aad94df05b7af152b5a266df5d09f17cffc8ba69b084b5c133786340` |
| Profile | `petg_general_0p4` / `ecd7e9e90881087b4ef04779c3717bc972489d689924d8602b5cae9d4855408c` |
| Printer | QIDI Plus4; 305 x 305 x 280 mm nominal; 5 mm protected edge margin |
| Material / nozzle / layer | PETG / 0.4 mm / 0.20 mm |
| Plate envelope | 208.0 x 124.0 x 14.0 mm; centered |
| Native slice record | QIDI Studio version, sliced mass and time: ____________________ |

## Objects and orientation

| STL | Qty | Locked orientation | Source SHA-256 |
|---|---:|---|---|
| `hardware_fit_gauge.stl` | 1 | Flat as exported; engraved labels upward | `beb9ecb2cd3b6020c998dc74d284e7639af7ac7b5040f7ab857d9c3fc3212c26` |
| `setup_hardware_fit_gauge.stl` | 1 | Flat as exported; all labels upward | `9316dd57f120a0d68c3ae228d5e8f0e54537131b5238397a6092e3163f9852d3` |
| `tpu_tip_retention_gauge.stl` | 1 | Flat base on bed; both rigid pegs upward | `cab0c935e90e3e64c977c4549b3a968d26e838a2437876fd63120bc249a0f0c6` |

## Required gates

| Gate | Status | Recorded values |
|---|---|---|
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "safe_plate_envelope_mm": [295, 295, 280]}` |
| `nozzle_0p4_confirmed` | **NOT_TESTED** | `{"installed_nozzle_mm": null, "verification_method": null}` |
| `petg_general_profile_calibrated` | **NOT_TESTED** | `{"brand": null, "calibration_result": null, "drying_record": null, "filament_name": null, "profile_revision": null, "spool_lot": null}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: M3/M4/M5 screws, washers, 1/4-20 hardware, TPU tip samples.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `petg_general_0p4`: 4 walls, 5 top / 5 bottom layers, 25% gyroid infill.
- Supports: off unless a job override says otherwise. Bed adhesion: Clean textured PEI; use a 5 mm brim only after observed corner lift.
- Dimensional controls: Use calibrated elephant-foot and XY-hole compensation from the diagnostic coupons.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- Record general clearances, screw-head and washer seats, camera hex choice, and rigid-peg preliminary fit. Do not use the rigid peg alone to release TPU production.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, engraved identity and revision before cleanup.
- Quarantine any warped, cracked, delaminated, under-extruded, bridged-shut or untraceable part; do not silently rework a critical fit.
- Intended gate(s) after objective acceptance: `general_clearance_holes_coupon_pass`, `setup_hardware_coupon_pass`.

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

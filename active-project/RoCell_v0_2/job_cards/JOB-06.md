# Job 06 - Same-profile 2020 socket and production-axis M5 nut/clearance/washer tests

| Control field | Released value |
|---|---|
| Design revision | `RC02-PRO-R1` |
| Lifecycle state | **UNRELEASED** |
| Route / stage | `camera_mast_optional` / `diagnostic` |
| Kit | `KIT-MAST` |
| Plate | `06_ASA_mast_fit_tests.3mf` |
| Plate SHA-256 | `4b72cee5268475f5af4122350fa62eaf9dbbde5100345e24cc5c3091c4f012ba` |
| Profile | `asa_structural_0p4` / `7f5a63b82b79566c55df616753ef9acc31e6a172a2689b726498aa2cb82c7a22` |
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
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "safe_plate_envelope_mm": [295, 295, 280]}` |
| `nozzle_0p4_confirmed` | **NOT_TESTED** | `{"installed_nozzle_mm": null, "verification_method": null}` |
| `asa_profile_calibrated` | **NOT_TESTED** | `{"brand": null, "calibration_result": null, "chamber_condition": null, "drying_record": null, "filament_name": null, "profile_revision": null, "spool_lot": null}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: Actual 2020 extrusion, M5 nuts/bolts/washers, calipers.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `asa_structural_0p4`: 6 walls, 6 top / 6 bottom layers, 45% gyroid infill.
- Supports: build-plate only under transverse bores if needed. Bed adhesion: 10 mm brim, enclosed printer, stable chamber, and no drafts.
- Dimensional controls: Use the ASA socket and nut coupons from the same spool before the first full foot.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- Measure extrusion X/Y at multiple points; record the 20 mm-engagement socket, horizontal nut trap, free-passing M5 bore and washer seat using the exact ASA lot.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, engraved identity and revision before cleanup.
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

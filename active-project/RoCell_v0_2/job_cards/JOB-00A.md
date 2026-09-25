# Job 00A - Keyboard corner, seam, clearance, and M4 washer tests using the exact tray profile

| Control field | Released value |
|---|---|
| Design revision | `RC02-PRO-R1` |
| Lifecycle state | **UNRELEASED** |
| Route / stage | `required` / `diagnostic` |
| Kit | `KIT-CAL` |
| Plate | `00A_PETG_keyboard_profile_fit_tests.3mf` |
| Plate SHA-256 | `e953101bb6dbb6a7935538f7615267a46dd3ee09c69a11161bd9fb2912c1392a` |
| Profile | `petg_tray_structural_0p4` / `a6683691851137c050c1549e2dc810a7be8db2d862064ffd63263d9c5a6165ad` |
| Printer | QIDI Plus4; 305 x 305 x 280 mm nominal; 5 mm protected edge margin |
| Material / nozzle / layer | PETG / 0.4 mm / 0.20 mm |
| Plate envelope | 174.0 x 138.0 x 11.0 mm; centered |
| Native slice record | QIDI Studio version, sliced mass and time: ____________________ |

## Objects and orientation

| STL | Qty | Locked orientation | Source SHA-256 |
|---|---:|---|---|
| `keyboard_corner_fit_test.stl` | 1 | Flat as exported | `782ce3b7a62afd0bf21bcb1f524788aa0eeabb07a27ee6998a2cde75308b2423` |
| `keyboard_seam_fit_male.stl` | 1 | Flat as exported; key upward | `36eb25c1b927a56d961e6ba19fa5ed424ee2d9cbf39732c4f3f0c6649f85d31c` |
| `keyboard_seam_fit_female.stl` | 1 | Flat as exported; pocket upward | `62f7a6f07e7decd8947c2763e0d5757d4d3be7382bfc0b3f79fd3dc243f46ba9` |
| `hardware_fit_gauge.stl` | 1 | Flat as exported; engraved labels upward | `beb9ecb2cd3b6020c998dc74d284e7639af7ac7b5040f7ab857d9c3fc3212c26` |
| `m4_washer_fit_gauge.stl` | 1 | Flat as exported; W8.8/W9.2/W9.6 labels upward | `8594207f90b7b1e08a7e91e665fcc29d9a92100835ad2fed3fa172585cb4d08f` |

## Required gates

| Gate | Status | Recorded values |
|---|---|---|
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "safe_plate_envelope_mm": [295, 295, 280]}` |
| `nozzle_0p4_confirmed` | **NOT_TESTED** | `{"installed_nozzle_mm": null, "verification_method": null}` |
| `petg_tray_profile_calibrated` | **NOT_TESTED** | `{"brand": null, "calibration_result": null, "drying_record": null, "filament_name": null, "profile_revision": null, "spool_lot": null}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: Actual keyboard, board screws, M4 washers, calipers.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `petg_tray_structural_0p4`: 5 walls, 6 top / 6 bottom layers, 35% gyroid infill.
- Supports: off. Bed adhesion: Clean textured PEI; 6 mm brim recommended for the two large tray halves.
- Dimensional controls: Keep slicer seam away from mounting slots, male keys, female pocket mouths, and keyboard datums.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- Inspect labels and all hole mouths; mate seam coupons fully; record corner seating, seam gap/rock, the smallest free-passing hole, and the smallest washer recess that seats flat.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, engraved identity and revision before cleanup.
- Quarantine any warped, cracked, delaminated, under-extruded, bridged-shut or untraceable part; do not silently rework a critical fit.
- Intended gate(s) after objective acceptance: `keyboard_corner_coupon_pass`, `keyboard_seam_coupon_pass`, `tray_clearance_holes_coupon_pass`.

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

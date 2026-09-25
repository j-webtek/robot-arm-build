# RoCell RC02-PRO-R1 - controlled print job cards

These travelers are generated from the authoritative job, profile, gate, lifecycle and 3MF sidecar records. Complete one card per physical plate. Never infer release from a filename: the prerequisite table and lifecycle state control the work.

Generated coverage: **24 jobs** on the QIDI Plus4.

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


# Job 00B - Phone width, horizontal M4 insert, cable-saddle, and washer tests using the exact cradle profile

| Control field | Released value |
|---|---|
| Design revision | `RC02-PRO-R1` |
| Lifecycle state | **UNRELEASED** |
| Route / stage | `required` / `diagnostic` |
| Kit | `KIT-CAL` |
| Plate | `00B_PETG_phone_profile_fit_tests.3mf` |
| Plate SHA-256 | `8df377ad10c14faa25363c9b48b95b021ef0474aad656b0ea7001c201fa382f9` |
| Profile | `petg_cradle_0p4` / `874f2e964792b58d533f2fd659f5ad595af5759c7acba9d2244d5fc5b20e841c` |
| Printer | QIDI Plus4; 305 x 305 x 280 mm nominal; 5 mm protected edge margin |
| Material / nozzle / layer | PETG / 0.4 mm / 0.20 mm |
| Plate envelope | 216.0 x 80.0 x 16.0 mm; centered |
| Native slice record | QIDI Studio version, sliced mass and time: ____________________ |

## Objects and orientation

| STL | Qty | Locked orientation | Source SHA-256 |
|---|---:|---|---|
| `phone_width_fit_test.stl` | 1 | Flat as exported | `96aaf6fe04d5be4ab6eb9c01f810583198dcc250f86f5d316134f385ce633c77` |
| `m4_horizontal_insert_fit_gauge.stl` | 1 | Flat as exported; production-axis bores horizontal | `47b228a28e1847036e8ebbac43e3d926d815aed85bf14d3a0d1fb07050a3d414` |
| `cable_tie_saddle_fit_gauge.stl` | 1 | Flat as exported; saddles upward | `c00cd708d208909996e38fab9653f2b991335407dbd38fbb7d7089fc98232158` |
| `m4_washer_fit_gauge.stl` | 1 | Flat as exported; W8.8/W9.2/W9.6 labels upward | `8594207f90b7b1e08a7e91e665fcc29d9a92100835ad2fed3fa172585cb4d08f` |

## Required gates

| Gate | Status | Recorded values |
|---|---|---|
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "safe_plate_envelope_mm": [295, 295, 280]}` |
| `nozzle_0p4_confirmed` | **NOT_TESTED** | `{"installed_nozzle_mm": null, "verification_method": null}` |
| `petg_cradle_profile_calibrated` | **NOT_TESTED** | `{"brand": null, "calibration_result": null, "drying_record": null, "filament_name": null, "profile_revision": null, "spool_lot": null}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: Actual phone/case, M4 inserts/washers, USB cable and selected ties.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `petg_cradle_0p4`: 5 walls, 5 top / 5 bottom layers, 30% gyroid infill.
- Supports: build-plate only under horizontal clamp bores if needed. Bed adhesion: 5 mm brim recommended around the asymmetric cradle and clamp towers.
- Dimensional controls: Use the horizontal M4 insert coupon; ream the 4.6 mm passages by hand after printing.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- Record phone hand-fit, selected horizontal insert pocket, insert squareness/spin resistance, selected saddle, cable bend clearance, and the smallest flat-seating M4 washer recess.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, engraved identity and revision before cleanup.
- Quarantine any warped, cracked, delaminated, under-extruded, bridged-shut or untraceable part; do not silently rework a critical fit.
- Intended gate(s) after objective acceptance: `phone_width_coupon_pass`, `m4_horizontal_insert_coupon_pass`, `cable_tie_saddle_coupon_pass`, `cradle_m4_washer_coupon_pass`.

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


# Job 00C - RoArm grip, stepped spring seat, M3 insert, and M3 head tests using the exact tool profile

| Control field | Released value |
|---|---|
| Design revision | `RC02-PRO-R1` |
| Lifecycle state | **UNRELEASED** |
| Route / stage | `required` / `diagnostic` |
| Kit | `KIT-CAL` |
| Plate | `00C_PETG_tool_profile_fit_tests.3mf` |
| Plate SHA-256 | `072fe182dd1689a3574b62e7a864fa86d0d54d8e614a3d7c0be092192c76a9a6` |
| Profile | `petg_precision_0p4` / `8a7d27cd2258c97d838fb416cc07a3e8842b840cc0868221bba343297b05e304` |
| Printer | QIDI Plus4; 305 x 305 x 280 mm nominal; 5 mm protected edge margin |
| Material / nozzle / layer | PETG / 0.4 mm / 0.16 mm |
| Plate envelope | 156.0 x 70.0 x 34.0 mm; centered |
| Native slice record | QIDI Studio version, sliced mass and time: ____________________ |

## Objects and orientation

| STL | Qty | Locked orientation | Source SHA-256 |
|---|---:|---|---|
| `compliant_tool_grip_fit_test.stl` | 1 | Upright as exported; full 28 mm grip face vertical | `2c892ebeccd9d4512bf877cac3c1d56c87329c1a30a47165221480021104d935` |
| `spring_fit_gauge.stl` | 1 | Flat as exported; stepped cup upward | `0b8464e8506bea26cc8972ce32fcfc4e7366c800eac4ee23e6fcd16677672f4c` |
| `m3_insert_fit_gauge.stl` | 1 | Flat as exported; insert mouths upward | `8726a5fcd79151256bed4b4e77829ce1970d5769aa8f1d8529be8c271d3cbf43` |
| `m3_head_fit_gauge.stl` | 1 | Flat as exported; H5.8/H6.2/H6.6 labels upward | `66d4f5ed4100304d44daa624f532a757b2b73ff6dea84858bdb8f33dfc3c4165` |

## Required gates

| Gate | Status | Recorded values |
|---|---|---|
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "safe_plate_envelope_mm": [295, 295, 280]}` |
| `nozzle_0p4_confirmed` | **NOT_TESTED** | `{"installed_nozzle_mm": null, "verification_method": null}` |
| `petg_precision_profile_calibrated` | **NOT_TESTED** | `{"brand": null, "calibration_result": null, "drying_record": null, "filament_name": null, "profile_revision": null, "spool_lot": null}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: RoArm gripper, actual spring, M3 inserts/screws, calipers.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `petg_precision_0p4`: 5 walls, 6 top / 6 bottom layers, 40% gyroid infill.
- Supports: off. Bed adhesion: 5 mm brim around the upright tool body; remove carefully from the cap.
- Dimensional controls: Keep the slicer seam off the gripper flats and sliding guide bore.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- Verify the full 28 mm grip interface; record no slip/crush; record spring OD/ID/free length and both seat fits; install-test each M3 pocket and select the smallest below-flush M3 head recess.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, engraved identity and revision before cleanup.
- Quarantine any warped, cracked, delaminated, under-extruded, bridged-shut or untraceable part; do not silently rework a critical fit.
- Intended gate(s) after objective acceptance: `gripper_coupon_pass`, `spring_fit_coupon_pass`, `m3_insert_coupon_pass`, `precision_m3_head_coupon_pass`.

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


# Job 00F - M4 clearance and washer verification using the exact fine-layer calibration-puck profile

| Control field | Released value |
|---|---|
| Design revision | `RC02-PRO-R1` |
| Lifecycle state | **UNRELEASED** |
| Route / stage | `required` / `diagnostic` |
| Kit | `KIT-CAL` |
| Plate | `00F_PETG_calibration_profile_clearance_test.3mf` |
| Plate SHA-256 | `0038168c44cd1e614ce979d368855489c8852ba79b2a0565fcccbddffe700cd3` |
| Profile | `petg_calibration_0p4` / `8bfef01f473a15368eb72901b0b8e472315afb089b489388fd077fff02eb0a06` |
| Printer | QIDI Plus4; 305 x 305 x 280 mm nominal; 5 mm protected edge margin |
| Material / nozzle / layer | PETG / 0.4 mm / 0.16 mm |
| Plate envelope | 160.0 x 70.0 x 6.0 mm; centered |
| Native slice record | QIDI Studio version, sliced mass and time: ____________________ |

## Objects and orientation

| STL | Qty | Locked orientation | Source SHA-256 |
|---|---:|---|---|
| `hardware_fit_gauge.stl` | 1 | Flat as exported; engraved labels upward | `beb9ecb2cd3b6020c998dc74d284e7639af7ac7b5040f7ab857d9c3fc3212c26` |
| `m4_washer_fit_gauge.stl` | 1 | Flat as exported; W8.8/W9.2/W9.6 labels upward | `8594207f90b7b1e08a7e91e665fcc29d9a92100835ad2fed3fa172585cb4d08f` |

## Required gates

| Gate | Status | Recorded values |
|---|---|---|
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "safe_plate_envelope_mm": [295, 295, 280]}` |
| `nozzle_0p4_confirmed` | **NOT_TESTED** | `{"installed_nozzle_mm": null, "verification_method": null}` |
| `petg_calibration_profile_calibrated` | **NOT_TESTED** | `{"brand": null, "calibration_result": null, "drying_record": null, "filament_name": null, "profile_revision": null, "spool_lot": null}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: M4 board screw/bolt, washer, and measuring tools.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `petg_calibration_0p4`: 4 walls, 6 top / 6 bottom layers, 40% gyroid infill.
- Supports: off. Bed adhesion: Skirt normally sufficient on clean textured PEI.
- Dimensional controls: Do not enable ironing over the crosshair or central divot.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- Use the exact 0.16 mm calibration profile; record the smallest freely passing M4 option and smallest flat-seating washer recess. Retain and label this coupon separately from 00A/00E.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, engraved identity and revision before cleanup.
- Quarantine any warped, cracked, delaminated, under-extruded, bridged-shut or untraceable part; do not silently rework a critical fit.
- Intended gate(s) after objective acceptance: `calibration_clearance_holes_coupon_pass`.

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


# Job 01 - Left keyboard tray first article

| Control field | Released value |
|---|---|
| Design revision | `RC02-PRO-R1` |
| Lifecycle state | **UNRELEASED** |
| Route / stage | `required` / `first_article` |
| Kit | `KIT-KB` |
| Plate | `01_PETG_keyboard_left.3mf` |
| Plate SHA-256 | `17bad44e8b245b3ceafbe51af3204fe5a9a37f88fd080e155f983e07026c3354` |
| Profile | `petg_tray_structural_0p4` / `a6683691851137c050c1549e2dc810a7be8db2d862064ffd63263d9c5a6165ad` |
| Printer | QIDI Plus4; 305 x 305 x 280 mm nominal; 5 mm protected edge margin |
| Material / nozzle / layer | PETG / 0.4 mm / 0.20 mm |
| Plate envelope | 184.5 x 157.0 x 11.0 mm; centered |
| Native slice record | QIDI Studio version, sliced mass and time: ____________________ |

## Objects and orientation

| STL | Qty | Locked orientation | Source SHA-256 |
|---|---:|---|---|
| `keyboard_tray_left.stl` | 1 | Flat, exported base on bed; RC02-L readable on top | `32f293bb28b7061b735c6f0f7be1e1c44f42d9520c5660795d09fe10e221550f` |

## Required gates

| Gate | Status | Recorded values |
|---|---|---|
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "safe_plate_envelope_mm": [295, 295, 280]}` |
| `nozzle_0p4_confirmed` | **NOT_TESTED** | `{"installed_nozzle_mm": null, "verification_method": null}` |
| `petg_tray_profile_calibrated` | **NOT_TESTED** | `{"brand": null, "calibration_result": null, "drying_record": null, "filament_name": null, "profile_revision": null, "spool_lot": null}` |
| `keyboard_dimensions_measured` | **NOT_TESTED** | `{"cable_keepout_mm": null, "depth_mm": null, "device_model": null, "height_mm": null, "width_mm": null}` |
| `keyboard_corner_coupon_pass` | **NOT_TESTED** | `{"fit_result": null, "rocking_result": null, "selected_compensation_mm": null}` |
| `keyboard_seam_coupon_pass` | **NOT_TESTED** | `{"assembled_gap_mm": null, "fit_result": null, "flush_mismatch_mm": null}` |
| `tray_clearance_holes_coupon_pass` | **NOT_TESTED** | `{"board_screw_major_diameter_mm": null, "m4_washer_od_mm": null, "smallest_free_hole_mm": null, "washer_fit_result": null}` |
| `geometry_matches_measurements` | **NOT_TESTED** | `{"affected_parts_reviewed": null, "design_revision": null, "effective_parameters_file": null, "measurement_record_revision": null, "regeneration_completed": null}` |
| `qidi_studio_roundtrip_confirmed` | **NOT_TESTED** | `{"critical_layer_preview_pass_by_job": {}, "evidence_reference_by_job": {}, "geometry_scale_percent_by_job": {}, "native_project_sha256_by_job": {}, "object_count_by_job": {}, "qidi_studio_version": null, "saved_profile_revision_by_job": {}, "validated_job_ids": []}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: Flatness surface, calipers, four board screws/washers.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `petg_tray_structural_0p4`: 5 walls, 6 top / 6 bottom layers, 35% gyroid infill.
- Supports: off. Bed adhesion: Clean textured PEI; 6 mm brim recommended for the two large tray halves.
- Dimensional controls: Keep slicer seam away from mounting slots, male keys, female pocket mouths, and keyboard datums.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- Cool fully; inspect all four closed slots, washer tracks, solid-rail pad pockets, seam keys, datums, and overall flatness. Reject cracks or lifted corners.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, engraved identity and revision before cleanup.
- Quarantine any warped, cracked, delaminated, under-extruded, bridged-shut or untraceable part; do not silently rework a critical fit.
- Intended gate(s) after objective acceptance: `keyboard_left_first_article_pass`.

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


# Job 02 - Right keyboard tray after left first-article acceptance

| Control field | Released value |
|---|---|
| Design revision | `RC02-PRO-R1` |
| Lifecycle state | **UNRELEASED** |
| Route / stage | `required` / `production` |
| Kit | `KIT-KB` |
| Plate | `02_PETG_keyboard_right.3mf` |
| Plate SHA-256 | `38bd156f7dac84ae59168430a49b40f41355f5216b5cb8e3c87ed9cd8bc418b2` |
| Profile | `petg_tray_structural_0p4` / `a6683691851137c050c1549e2dc810a7be8db2d862064ffd63263d9c5a6165ad` |
| Printer | QIDI Plus4; 305 x 305 x 280 mm nominal; 5 mm protected edge margin |
| Material / nozzle / layer | PETG / 0.4 mm / 0.20 mm |
| Plate envelope | 162.5 x 157.0 x 11.0 mm; centered |
| Native slice record | QIDI Studio version, sliced mass and time: ____________________ |

## Objects and orientation

| STL | Qty | Locked orientation | Source SHA-256 |
|---|---:|---|---|
| `keyboard_tray_right.stl` | 1 | Flat, exported base on bed; RC02-R readable on top | `a9cdb802b6f0b233f5ee272e829316e31367ef50c8d9e4d7a788169d55520d93` |

## Required gates

| Gate | Status | Recorded values |
|---|---|---|
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "safe_plate_envelope_mm": [295, 295, 280]}` |
| `nozzle_0p4_confirmed` | **NOT_TESTED** | `{"installed_nozzle_mm": null, "verification_method": null}` |
| `petg_tray_profile_calibrated` | **NOT_TESTED** | `{"brand": null, "calibration_result": null, "drying_record": null, "filament_name": null, "profile_revision": null, "spool_lot": null}` |
| `keyboard_dimensions_measured` | **NOT_TESTED** | `{"cable_keepout_mm": null, "depth_mm": null, "device_model": null, "height_mm": null, "width_mm": null}` |
| `keyboard_corner_coupon_pass` | **NOT_TESTED** | `{"fit_result": null, "rocking_result": null, "selected_compensation_mm": null}` |
| `keyboard_seam_coupon_pass` | **NOT_TESTED** | `{"assembled_gap_mm": null, "fit_result": null, "flush_mismatch_mm": null}` |
| `tray_clearance_holes_coupon_pass` | **NOT_TESTED** | `{"board_screw_major_diameter_mm": null, "m4_washer_od_mm": null, "smallest_free_hole_mm": null, "washer_fit_result": null}` |
| `geometry_matches_measurements` | **NOT_TESTED** | `{"affected_parts_reviewed": null, "design_revision": null, "effective_parameters_file": null, "measurement_record_revision": null, "regeneration_completed": null}` |
| `keyboard_left_first_article_pass` | **NOT_TESTED** | `{"datum_surface_result": null, "flatness_mm": null, "job_id": null, "seam_key_result": null, "slot_fit_result": null, "washer_track_result": null}` |
| `qidi_studio_roundtrip_confirmed` | **NOT_TESTED** | `{"critical_layer_preview_pass_by_job": {}, "evidence_reference_by_job": {}, "geometry_scale_percent_by_job": {}, "native_project_sha256_by_job": {}, "object_count_by_job": {}, "qidi_studio_version": null, "saved_profile_revision_by_job": {}, "validated_job_ids": []}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: Accepted left half, keyboard, eight board screws/washers.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `petg_tray_structural_0p4`: 5 walls, 6 top / 6 bottom layers, 35% gyroid infill.
- Supports: off. Bed adhesion: Clean textured PEI; 6 mm brim recommended for the two large tray halves.
- Dimensional controls: Keep slicer seam away from mounting slots, male keys, female pocket mouths, and keyboard datums.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- Repeat first-article checks; mate both halves; record seam gap, flushness, assembled envelope, and rocking. Ten removal/reinstall cycles follow mounting.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, engraved identity and revision before cleanup.
- Quarantine any warped, cracked, delaminated, under-extruded, bridged-shut or untraceable part; do not silently rework a critical fit.
- Intended gate(s) after objective acceptance: `keyboard_tray_pair_postprint_pass`, `keyboard_fixture_assembly_pass`.

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


# Job 03A - Phone cradle with closed mounting ears and raised cable saddle

| Control field | Released value |
|---|---|
| Design revision | `RC02-PRO-R1` |
| Lifecycle state | **UNRELEASED** |
| Route / stage | `required` / `production` |
| Kit | `KIT-PHONE` |
| Plate | `03A_PETG_phone_cradle.3mf` |
| Plate SHA-256 | `4de7e4f3e5161e070e629d4e408fecdc307a33639ed3791bc98a0c3fb8119e5b` |
| Profile | `petg_cradle_0p4` / `874f2e964792b58d533f2fd659f5ad595af5759c7acba9d2244d5fc5b20e841c` |
| Printer | QIDI Plus4; 305 x 305 x 280 mm nominal; 5 mm protected edge margin |
| Material / nozzle / layer | PETG / 0.4 mm / 0.20 mm |
| Plate envelope | 117.3 x 172.8 x 20.0 mm; centered |
| Native slice record | QIDI Studio version, sliced mass and time: ____________________ |

## Objects and orientation

| STL | Qty | Locked orientation | Source SHA-256 |
|---|---:|---|---|
| `phone_cradle_a16.stl` | 1 | Flat base on bed; USB mark toward plate front | `a6a9af5f1c350002bee9752ac4aa1f30642138d3e656f903ef064baefd2e9c18` |

## Required gates

| Gate | Status | Recorded values |
|---|---|---|
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "safe_plate_envelope_mm": [295, 295, 280]}` |
| `nozzle_0p4_confirmed` | **NOT_TESTED** | `{"installed_nozzle_mm": null, "verification_method": null}` |
| `petg_cradle_profile_calibrated` | **NOT_TESTED** | `{"brand": null, "calibration_result": null, "drying_record": null, "filament_name": null, "profile_revision": null, "spool_lot": null}` |
| `phone_dimensions_measured` | **NOT_TESTED** | `{"camera_bump_envelope_mm": null, "case_installed": null, "device_model": null, "length_mm": null, "thickness_mm": null, "width_mm": null}` |
| `phone_side_features_measured` | **NOT_TESTED** | `{"minimum_keepout_margin_mm": null, "right_side_keepouts_from_bottom_mm": null, "selected_clamp_centers_from_bottom_mm": null}` |
| `phone_cable_measured` | **NOT_TESTED** | `{"connector_thickness_mm": null, "connector_width_mm": null, "minimum_bend_radius_mm": null, "selected_tie_width_mm": null, "straight_projection_mm": null}` |
| `phone_width_coupon_pass` | **NOT_TESTED** | `{"fit_result": null, "lateral_clearance_mm": null, "rail_height_result": null}` |
| `m4_horizontal_insert_coupon_pass` | **NOT_TESTED** | `{"insert_length_mm": null, "insert_od_mm": null, "installed_depth_mm": null, "reamed_passage_mm": null, "retention_result": null, "selected_pocket_mm": null}` |
| `cable_tie_saddle_coupon_pass` | **NOT_TESTED** | `{"cable_clearance_result": null, "feed_result": null, "saddle_crack_result": null, "selected_slot_width_mm": null, "selected_tie_width_mm": null}` |
| `cradle_m4_washer_coupon_pass` | **NOT_TESTED** | `{"actual_washer_od_mm": null, "fit_result": null, "m4_washer_od_mm": null}` |
| `geometry_matches_measurements` | **NOT_TESTED** | `{"affected_parts_reviewed": null, "design_revision": null, "effective_parameters_file": null, "measurement_record_revision": null, "regeneration_completed": null}` |
| `qidi_studio_roundtrip_confirmed` | **NOT_TESTED** | `{"critical_layer_preview_pass_by_job": {}, "evidence_reference_by_job": {}, "geometry_scale_percent_by_job": {}, "native_project_sha256_by_job": {}, "object_count_by_job": {}, "qidi_studio_version": null, "saved_profile_revision_by_job": {}, "validated_job_ids": []}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: Phone/case, cable, 2 M4 inserts, 2 thumb screws, accepted TPU tips, 4 board screws/washers, ties.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `petg_cradle_0p4`: 5 walls, 5 top / 5 bottom layers, 30% gyroid infill.
- Supports: build-plate only under horizontal clamp bores if needed. Bed adhesion: 5 mm brim recommended around the asymmetric cradle and clamp towers.
- Dimensional controls: Use the horizontal M4 insert coupon; ream the 4.6 mm passages by hand after printing.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- Inspect flatness, closed mounting ears, rails, towers and raised cable saddle. Install inserts square, verify all keepouts, then complete ten phone cycles without button contact.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, engraved identity and revision before cleanup.
- Quarantine any warped, cracked, delaminated, under-extruded, bridged-shut or untraceable part; do not silently rework a critical fit.
- Intended gate(s) after objective acceptance: `phone_cradle_postprint_pass`, `phone_fixture_assembly_pass`.

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


# Job 03B - Two scaled, gusseted keyboard rear clamps

| Control field | Released value |
|---|---|
| Design revision | `RC02-PRO-R1` |
| Lifecycle state | **UNRELEASED** |
| Route / stage | `required` / `production` |
| Kit | `KIT-KB` |
| Plate | `03B_PETG_keyboard_clamps.3mf` |
| Plate SHA-256 | `bac9fd7c9acc6a1e715f0ca2b26c6f5f6b1c8e4a0dc3d7c30630db8556f48311` |
| Profile | `petg_general_0p4` / `ecd7e9e90881087b4ef04779c3717bc972489d689924d8602b5cae9d4855408c` |
| Printer | QIDI Plus4; 305 x 305 x 280 mm nominal; 5 mm protected edge margin |
| Material / nozzle / layer | PETG / 0.4 mm / 0.20 mm |
| Plate envelope | 112.0 x 34.0 x 25.0 mm; centered |
| Native slice record | QIDI Studio version, sliced mass and time: ____________________ |

## Objects and orientation

| STL | Qty | Locked orientation | Source SHA-256 |
|---|---:|---|---|
| `keyboard_rear_clamp.stl` | 2 | Flat base on bed; padded face upright | `07d94bcdb65be80d3002e9489ec659e127004d48233c895e6569a4da5dfdc938` |

## Required gates

| Gate | Status | Recorded values |
|---|---|---|
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "safe_plate_envelope_mm": [295, 295, 280]}` |
| `nozzle_0p4_confirmed` | **NOT_TESTED** | `{"installed_nozzle_mm": null, "verification_method": null}` |
| `petg_general_profile_calibrated` | **NOT_TESTED** | `{"brand": null, "calibration_result": null, "drying_record": null, "filament_name": null, "profile_revision": null, "spool_lot": null}` |
| `keyboard_dimensions_measured` | **NOT_TESTED** | `{"cable_keepout_mm": null, "depth_mm": null, "device_model": null, "height_mm": null, "width_mm": null}` |
| `keyboard_corner_coupon_pass` | **NOT_TESTED** | `{"fit_result": null, "rocking_result": null, "selected_compensation_mm": null}` |
| `general_clearance_holes_coupon_pass` | **NOT_TESTED** | `{"m3_selected_mm": null, "m4_or_board_screw_selected_mm": null, "m5_selected_mm": null}` |
| `setup_hardware_coupon_pass` | **NOT_TESTED** | `{"camera_hex_ac_mm": null, "fit_result": null, "m3_head_recess_d_mm": null, "m4_washer_od_mm": null, "m5_washer_od_mm": null}` |
| `geometry_matches_measurements` | **NOT_TESTED** | `{"affected_parts_reviewed": null, "design_revision": null, "effective_parameters_file": null, "measurement_record_revision": null, "regeneration_completed": null}` |
| `qidi_studio_roundtrip_confirmed` | **NOT_TESTED** | `{"critical_layer_preview_pass_by_job": {}, "evidence_reference_by_job": {}, "geometry_scale_percent_by_job": {}, "native_project_sha256_by_job": {}, "object_count_by_job": {}, "qidi_studio_version": null, "saved_profile_revision_by_job": {}, "validated_job_ids": []}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: Keyboard, two face pads, two board screws/washers.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `petg_general_0p4`: 4 walls, 5 top / 5 bottom layers, 25% gyroid infill.
- Supports: off unless a job override says otherwise. Bed adhesion: Clean textured PEI; use a 5 mm brim only after observed corner lift.
- Dimensional controls: Use calibrated elephant-foot and XY-hole compensation from the diagnostic coupons.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- Verify both parts match, bases are flat, gussets intact, scales readable and slots open. Pad faces; tighten only to contact; run the keyboard repeatability test.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, engraved identity and revision before cleanup.
- Quarantine any warped, cracked, delaminated, under-extruded, bridged-shut or untraceable part; do not silently rework a critical fit.
- Intended gate(s) after objective acceptance: `keyboard_clamps_postprint_pass`, `keyboard_fixture_assembly_pass`.

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


# Job 03C1 - ID0 tag frame first article with isolated artwork and washer zones

| Control field | Released value |
|---|---|
| Design revision | `RC02-PRO-R1` |
| Lifecycle state | **UNRELEASED** |
| Route / stage | `required` / `first_article` |
| Kit | `KIT-VISION-TAG` |
| Plate | `03C1_PETG_tag_frame_first_article.3mf` |
| Plate SHA-256 | `c49ef0465c90419dbb4e115d8493039ae78b852f48ac7eca887e21d72c0e3315` |
| Profile | `petg_general_0p4` / `ecd7e9e90881087b4ef04779c3717bc972489d689924d8602b5cae9d4855408c` |
| Printer | QIDI Plus4; 305 x 305 x 280 mm nominal; 5 mm protected edge margin |
| Material / nozzle / layer | PETG / 0.4 mm / 0.20 mm |
| Plate envelope | 78.0 x 78.0 x 4.0 mm; centered |
| Native slice record | QIDI Studio version, sliced mass and time: ____________________ |

## Objects and orientation

| STL | Qty | Locked orientation | Source SHA-256 |
|---|---:|---|---|
| `tag_frame_ID0_55mm.stl` | 1 | Flat as exported; ID0 and +Y readable | `5ef9601731298f7f674cd21ec9c0c6d3403db1f10e0e1f279bcceb9923034758` |

## Required gates

| Gate | Status | Recorded values |
|---|---|---|
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "safe_plate_envelope_mm": [295, 295, 280]}` |
| `nozzle_0p4_confirmed` | **NOT_TESTED** | `{"installed_nozzle_mm": null, "verification_method": null}` |
| `petg_general_profile_calibrated` | **NOT_TESTED** | `{"brand": null, "calibration_result": null, "drying_record": null, "filament_name": null, "profile_revision": null, "spool_lot": null}` |
| `tag_stock_measured` | **NOT_TESTED** | `{"stock_thickness_mm": null, "stock_type": null, "tile_height_mm": null, "tile_width_mm": null}` |
| `general_clearance_holes_coupon_pass` | **NOT_TESTED** | `{"m3_selected_mm": null, "m4_or_board_screw_selected_mm": null, "m5_selected_mm": null}` |
| `setup_hardware_coupon_pass` | **NOT_TESTED** | `{"camera_hex_ac_mm": null, "fit_result": null, "m3_head_recess_d_mm": null, "m4_washer_od_mm": null, "m5_washer_od_mm": null}` |
| `geometry_matches_measurements` | **NOT_TESTED** | `{"affected_parts_reviewed": null, "design_revision": null, "effective_parameters_file": null, "measurement_record_revision": null, "regeneration_completed": null}` |
| `qidi_studio_roundtrip_confirmed` | **NOT_TESTED** | `{"critical_layer_preview_pass_by_job": {}, "evidence_reference_by_job": {}, "geometry_scale_percent_by_job": {}, "native_project_sha256_by_job": {}, "object_count_by_job": {}, "qidi_studio_version": null, "saved_profile_revision_by_job": {}, "validated_job_ids": []}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: ID0 paper tile, matte tape, two screws/washers, ruler.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `petg_general_0p4`: 4 walls, 5 top / 5 bottom layers, 25% gyroid infill.
- Supports: off unless a job override says otherwise. Bed adhesion: Clean textured PEI; use a 5 mm brim only after observed corner lift.
- Dimensional controls: Use calibrated elephant-foot and XY-hole compensation from the diagnostic coupons.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- Verify the 55.4 mm pocket, 40.0 mm detection edge, thumbnail scoop, +Y orientation, flatness, and complete washer isolation from artwork.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, engraved identity and revision before cleanup.
- Quarantine any warped, cracked, delaminated, under-extruded, bridged-shut or untraceable part; do not silently rework a critical fit.
- Intended gate(s) after objective acceptance: `tag_artwork_scale_pass`, `tag_frame_first_article_pass`.

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


# Job 03C2 - Remaining ID1-ID5 tag frames after first-article acceptance

| Control field | Released value |
|---|---|
| Design revision | `RC02-PRO-R1` |
| Lifecycle state | **UNRELEASED** |
| Route / stage | `required` / `production` |
| Kit | `KIT-VISION-TAG` |
| Plate | `03C2_PETG_tag_frames_remaining.3mf` |
| Plate SHA-256 | `0ff8bff94b0a1bb09bb9f6a5bf50a8ded326c1cd9ae79e79aa3188f38fe18dcb` |
| Profile | `petg_general_0p4` / `ecd7e9e90881087b4ef04779c3717bc972489d689924d8602b5cae9d4855408c` |
| Printer | QIDI Plus4; 305 x 305 x 280 mm nominal; 5 mm protected edge margin |
| Material / nozzle / layer | PETG / 0.4 mm / 0.20 mm |
| Plate envelope | 244.0 x 161.0 x 4.0 mm; centered |
| Native slice record | QIDI Studio version, sliced mass and time: ____________________ |

## Objects and orientation

| STL | Qty | Locked orientation | Source SHA-256 |
|---|---:|---|---|
| `tag_frame_ID1_55mm.stl` | 1 | Flat as exported; ID1 and +Y readable | `e0abf77eec5661404b9776d84090b0f9d60234c0b9655d5670aab756da242742` |
| `tag_frame_ID2_55mm.stl` | 1 | Flat as exported; ID2 and +Y readable | `9aad4d845438f978a565afeb6b67f0cd8d24e9fe70a0bffdc6efb67b5d56bbf9` |
| `tag_frame_ID3_55mm.stl` | 1 | Flat as exported; ID3 and +Y readable | `e3acb03f9d9f6bd6b7ce6493551ad4fdccd78ea69c3a55c68eedc82e2bfd145d` |
| `tag_frame_ID4_55mm.stl` | 1 | Flat as exported; ID4 and +Y readable | `94aeecbe6349d9f7587772b1025e6de6f7df2033f9163f737230b0417f434a9c` |
| `tag_frame_ID5_55mm.stl` | 1 | Flat as exported; ID5 and +Y readable | `35339aecc93f8a394a555d959c66e9da67a21f1e4fe8f313759dc3798c7a1c6b` |

## Required gates

| Gate | Status | Recorded values |
|---|---|---|
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "safe_plate_envelope_mm": [295, 295, 280]}` |
| `nozzle_0p4_confirmed` | **NOT_TESTED** | `{"installed_nozzle_mm": null, "verification_method": null}` |
| `petg_general_profile_calibrated` | **NOT_TESTED** | `{"brand": null, "calibration_result": null, "drying_record": null, "filament_name": null, "profile_revision": null, "spool_lot": null}` |
| `tag_stock_measured` | **NOT_TESTED** | `{"stock_thickness_mm": null, "stock_type": null, "tile_height_mm": null, "tile_width_mm": null}` |
| `tag_artwork_scale_pass` | **NOT_TESTED** | `{"detection_edge_mm": null, "orientation_marked": null, "print_scale_percent": null, "tag_id": null, "tile_size_mm": null}` |
| `tag_frame_first_article_pass` | **NOT_TESTED** | `{"flatness_mm": null, "id_legibility_result": null, "job_id": null, "tag_fit_result": null, "washer_zone_result": null}` |
| `qidi_studio_roundtrip_confirmed` | **NOT_TESTED** | `{"critical_layer_preview_pass_by_job": {}, "evidence_reference_by_job": {}, "geometry_scale_percent_by_job": {}, "native_project_sha256_by_job": {}, "object_count_by_job": {}, "qidi_studio_version": null, "saved_profile_revision_by_job": {}, "validated_job_ids": []}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: ID1-ID5 tiles, matte tape, ten screws/washers.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `petg_general_0p4`: 4 walls, 5 top / 5 bottom layers, 25% gyroid infill.
- Supports: off unless a job override says otherwise. Bed adhesion: Clean textured PEI; use a 5 mm brim only after observed corner lift.
- Dimensional controls: Use calibrated elephant-foot and XY-hole compensation from the diagnostic coupons.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- Confirm every physical ID matches its debossed frame and board map. Check all faces flat, matte, unobstructed, and oriented +Y before mounting.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, engraved identity and revision before cleanup.
- Quarantine any warped, cracked, delaminated, under-extruded, bridged-shut or untraceable part; do not silently rework a critical fit.
- Intended gate(s) after objective acceptance: `tag_frame_batch_postprint_pass`, `tag_frame_installation_pass`.

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


# Job 03C3 - Universal camera plate isolated for measured camera hardware

| Control field | Released value |
|---|---|
| Design revision | `RC02-PRO-R1` |
| Lifecycle state | **UNRELEASED** |
| Route / stage | `required` / `production` |
| Kit | `KIT-VISION-CAM` |
| Plate | `03C3_PETG_camera_plate.3mf` |
| Plate SHA-256 | `92c277315d15a87632e73585a9b2bcc81c22a46df80c678eaf36de2fc3e6b27b` |
| Profile | `petg_general_0p4` / `ecd7e9e90881087b4ef04779c3717bc972489d689924d8602b5cae9d4855408c` |
| Printer | QIDI Plus4; 305 x 305 x 280 mm nominal; 5 mm protected edge margin |
| Material / nozzle / layer | PETG / 0.4 mm / 0.20 mm |
| Plate envelope | 90.0 x 55.0 x 6.0 mm; centered |
| Native slice record | QIDI Studio version, sliced mass and time: ____________________ |

## Objects and orientation

| STL | Qty | Locked orientation | Source SHA-256 |
|---|---:|---|---|
| `camera_plate_universal.stl` | 1 | Flat as exported; CAM/MAST labels upward | `1670976cd3f84915129c16e05b49de9e193a7b14d6be200289ee4e91cfbe51d9` |

## Required gates

| Gate | Status | Recorded values |
|---|---|---|
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "safe_plate_envelope_mm": [295, 295, 280]}` |
| `nozzle_0p4_confirmed` | **NOT_TESTED** | `{"installed_nozzle_mm": null, "verification_method": null}` |
| `petg_general_profile_calibrated` | **NOT_TESTED** | `{"brand": null, "calibration_result": null, "drying_record": null, "filament_name": null, "profile_revision": null, "spool_lot": null}` |
| `camera_mount_interface_measured` | **NOT_TESTED** | `{"camera_model": null, "camera_thread": null, "safe_thread_engagement_mm": null, "selected_camera_screw_length_mm": null, "selected_tslot_screw_length_mm": null, "strap_width_mm": null}` |
| `general_clearance_holes_coupon_pass` | **NOT_TESTED** | `{"m3_selected_mm": null, "m4_or_board_screw_selected_mm": null, "m5_selected_mm": null}` |
| `setup_hardware_coupon_pass` | **NOT_TESTED** | `{"camera_hex_ac_mm": null, "fit_result": null, "m3_head_recess_d_mm": null, "m4_washer_od_mm": null, "m5_washer_od_mm": null}` |
| `geometry_matches_measurements` | **NOT_TESTED** | `{"affected_parts_reviewed": null, "design_revision": null, "effective_parameters_file": null, "measurement_record_revision": null, "regeneration_completed": null}` |
| `qidi_studio_roundtrip_confirmed` | **NOT_TESTED** | `{"critical_layer_preview_pass_by_job": {}, "evidence_reference_by_job": {}, "geometry_scale_percent_by_job": {}, "native_project_sha256_by_job": {}, "object_count_by_job": {}, "qidi_studio_version": null, "saved_profile_revision_by_job": {}, "validated_job_ids": []}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: Actual camera, 1/4-20 screw, two M5 screws/T-nuts/washers, straps.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `petg_general_0p4`: 4 walls, 5 top / 5 bottom layers, 25% gyroid infill.
- Supports: off unless a job override says otherwise. Bed adhesion: Clean textured PEI; use a 5 mm brim only after observed corner lift.
- Dimensional controls: Use calibrated elephant-foot and XY-hole compensation from the diagnostic coupons.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- Measure camera thread direction, screw/head dimensions and safe engagement first. Check M5 ligaments, scales, strap slots, cable direction and no screw bottoming.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, engraved identity and revision before cleanup.
- Quarantine any warped, cracked, delaminated, under-extruded, bridged-shut or untraceable part; do not silently rework a critical fit.
- Intended gate(s) after objective acceptance: `camera_plate_hardware_pass`.

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


# Job 03D - TCP calibration puck isolated at its fine process

| Control field | Released value |
|---|---|
| Design revision | `RC02-PRO-R1` |
| Lifecycle state | **UNRELEASED** |
| Route / stage | `required` / `production` |
| Kit | `KIT-PUCK` |
| Plate | `03D_PETG_calibration_puck.3mf` |
| Plate SHA-256 | `7ab9f1184d22271a192897c9b705bc25f78073cc9f0a3efb2517557f758dcfe0` |
| Profile | `petg_calibration_0p4` / `8bfef01f473a15368eb72901b0b8e472315afb089b489388fd077fff02eb0a06` |
| Printer | QIDI Plus4; 305 x 305 x 280 mm nominal; 5 mm protected edge margin |
| Material / nozzle / layer | PETG / 0.4 mm / 0.16 mm |
| Plate envelope | 60.0 x 60.0 x 8.0 mm; centered |
| Native slice record | QIDI Studio version, sliced mass and time: ____________________ |

## Objects and orientation

| STL | Qty | Locked orientation | Source SHA-256 |
|---|---:|---|---|
| `calibration_puck.stl` | 1 | Flat as exported; crosshair upward; ironing off | `8853b88b08019bb84cedebf29685fcb3cde8d1701af9e01469a8344c35e0cbfc` |

## Required gates

| Gate | Status | Recorded values |
|---|---|---|
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "safe_plate_envelope_mm": [295, 295, 280]}` |
| `nozzle_0p4_confirmed` | **NOT_TESTED** | `{"installed_nozzle_mm": null, "verification_method": null}` |
| `petg_calibration_profile_calibrated` | **NOT_TESTED** | `{"brand": null, "calibration_result": null, "drying_record": null, "filament_name": null, "profile_revision": null, "spool_lot": null}` |
| `calibration_clearance_holes_coupon_pass` | **NOT_TESTED** | `{"board_screw_major_diameter_mm": null, "m4_washer_od_mm": null, "smallest_free_hole_mm": null, "washer_fit_result": null}` |
| `geometry_matches_measurements` | **NOT_TESTED** | `{"affected_parts_reviewed": null, "design_revision": null, "effective_parameters_file": null, "measurement_record_revision": null, "regeneration_completed": null}` |
| `qidi_studio_roundtrip_confirmed` | **NOT_TESTED** | `{"critical_layer_preview_pass_by_job": {}, "evidence_reference_by_job": {}, "geometry_scale_percent_by_job": {}, "native_project_sha256_by_job": {}, "object_count_by_job": {}, "qidi_studio_version": null, "saved_profile_revision_by_job": {}, "validated_job_ids": []}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: Two board screws/washers, straightedge, depth/height gauge.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `petg_calibration_0p4`: 4 walls, 6 top / 6 bottom layers, 40% gyroid infill.
- Supports: off. Bed adhesion: Skirt normally sufficient on clean textured PEI.
- Dimensional controls: Do not enable ironing over the crosshair or central divot.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- Reject a smeared crosshair/divot. Record free-state and mounted flatness plus assembled datum height; do not iron the top surface.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, engraved identity and revision before cleanup.
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


# Job 04A - Shared compliant tool body with keyed cap and one spare cap

| Control field | Released value |
|---|---|
| Design revision | `RC02-PRO-R1` |
| Lifecycle state | **UNRELEASED** |
| Route / stage | `any_tool_route` / `route` |
| Kit | `KIT-TOOL-COMMON` |
| Plate | `04A_PETG_shared_compliant_tool.3mf` |
| Plate SHA-256 | `50d98e0061d42ba35f312e69871376c6867c0d63f44b66c210ff00f584b56b62` |
| Profile | `petg_precision_0p4` / `8a7d27cd2258c97d838fb416cc07a3e8842b840cc0868221bba343297b05e304` |
| Printer | QIDI Plus4; 305 x 305 x 280 mm nominal; 5 mm protected edge margin |
| Material / nozzle / layer | PETG / 0.4 mm / 0.16 mm |
| Plate envelope | 100.0 x 24.0 x 66.2 mm; centered |
| Native slice record | QIDI Studio version, sliced mass and time: ____________________ |

## Objects and orientation

| STL | Qty | Locked orientation | Source SHA-256 |
|---|---:|---|---|
| `compliant_tool_body.stl` | 1 | Upright on lower end with specified brim | `18c8d7ff2d57c0785b324c58e93b3c6558db7c56c339270ab183307b991225ba` |
| `compliant_tool_top_cap.stl` | 2 | Flat, underside on bed; UP visible after print | `e7adbf51fd9382a4eb2b9a9dd25df677d43fd488c4584c2bf3e3e7d1599b9081` |

## Required gates

| Gate | Status | Recorded values |
|---|---|---|
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "safe_plate_envelope_mm": [295, 295, 280]}` |
| `nozzle_0p4_confirmed` | **NOT_TESTED** | `{"installed_nozzle_mm": null, "verification_method": null}` |
| `petg_precision_profile_calibrated` | **NOT_TESTED** | `{"brand": null, "calibration_result": null, "drying_record": null, "filament_name": null, "profile_revision": null, "spool_lot": null}` |
| `m3_insert_coupon_pass` | **NOT_TESTED** | `{"insert_length_mm": null, "insert_od_mm": null, "installed_depth_mm": null, "retention_result": null, "selected_pocket_mm": null}` |
| `gripper_interface_measured` | **NOT_TESTED** | `{"jaw_opening_mm": null, "jaw_pad_height_mm": null, "jaw_pad_width_mm": null, "selected_grip_setting": null}` |
| `gripper_coupon_pass` | **NOT_TESTED** | `{"crush_result": null, "selected_grip_setting": null, "shim_each_side_mm": null, "slip_result": null}` |
| `spring_dimensions_measured` | **NOT_TESTED** | `{"approx_rate_n_per_mm": null, "coil_bind_length_mm": null, "free_length_mm": null, "id_mm": null, "od_mm": null}` |
| `spring_fit_coupon_pass` | **NOT_TESTED** | `{"binding_result": null, "cup_fit_result": null, "post_fit_result": null, "selected_step_mm": null}` |
| `precision_m3_head_coupon_pass` | **NOT_TESTED** | `{"fit_result": null, "m3_head_recess_d_mm": null, "screw_head_d_mm": null}` |
| `geometry_matches_measurements` | **NOT_TESTED** | `{"affected_parts_reviewed": null, "design_revision": null, "effective_parameters_file": null, "measurement_record_revision": null, "regeneration_completed": null}` |
| `qidi_studio_roundtrip_confirmed` | **NOT_TESTED** | `{"critical_layer_preview_pass_by_job": {}, "evidence_reference_by_job": {}, "geometry_scale_percent_by_job": {}, "native_project_sha256_by_job": {}, "object_count_by_job": {}, "qidi_studio_version": null, "saved_profile_revision_by_job": {}, "validated_job_ids": []}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: Two M3 inserts, two M3x10 screws, accepted spring, route adapter.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `petg_precision_0p4`: 5 walls, 6 top / 6 bottom layers, 40% gyroid infill.
- Supports: off. Bed adhesion: 5 mm brim around the upright tool body; remove carefully from the cap.
- Dimensional controls: Keep the slicer seam off the gripper flats and sliding guide bore.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- Inspect body straightness, grip flats, guide bore, spring chamber and keyed locator. Install inserts square; cap must seat only in the keyed orientation. Verify 3-6 mm smooth return after route assembly.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, engraved identity and revision before cleanup.
- Quarantine any warped, cracked, delaminated, under-extruded, bridged-shut or untraceable part; do not silently rework a critical fit.
- Intended gate(s) after objective acceptance: `tool_body_postprint_pass`, `tool_assembled_motion_pass`.

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


# Job 04B - Two phone-route stylus collars for thin-wall retention qualification and one spare

| Control field | Released value |
|---|---|
| Design revision | `RC02-PRO-R1` |
| Lifecycle state | **UNRELEASED** |
| Route / stage | `phone_stylus_route` / `route` |
| Kit | `KIT-TOOL-PHONE` |
| Plate | `04B_PETG_phone_stylus_adapters.3mf` |
| Plate SHA-256 | `4f23eb2f4dcdd1b74458da5b1dd4077fb4da578030158055d60e3a59f49258af` |
| Profile | `petg_adapter_0p4` / `5addad813637abbe2dbc969afe8fde8637973498ff1f2439e590e070d62a2308` |
| Printer | QIDI Plus4; 305 x 305 x 280 mm nominal; 5 mm protected edge margin |
| Material / nozzle / layer | PETG / 0.4 mm / 0.12 mm |
| Plate envelope | 33.6 x 13.6 x 5.5 mm; centered |
| Native slice record | QIDI Studio version, sliced mass and time: ____________________ |

## Objects and orientation

| STL | Qty | Locked orientation | Source SHA-256 |
|---|---:|---|---|
| `stylus_collar_9mm.stl` | 2 | Flat flange on bed; split and radial pilot open | `041b31a9256250365eb8995a7ce42d3cb38875f75d0cc164228d3feaf0fa4637` |

## Required gates

| Gate | Status | Recorded values |
|---|---|---|
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "safe_plate_envelope_mm": [295, 295, 280]}` |
| `nozzle_0p4_confirmed` | **NOT_TESTED** | `{"installed_nozzle_mm": null, "verification_method": null}` |
| `petg_adapter_profile_calibrated` | **NOT_TESTED** | `{"brand": null, "calibration_result": null, "drying_record": null, "filament_name": null, "profile_revision": null, "spool_lot": null}` |
| `stylus_diameter_measured` | **NOT_TESTED** | `{"diameter_mm": null, "measurement_locations": null, "stylus_model": null}` |
| `stylus_gauge_coupon_pass` | **NOT_TESTED** | `{"excess_play_result": null, "selected_nominal_mm": null, "sliding_fit_result": null}` |
| `adapter_retention_method_selected` | **NOT_TESTED** | `{"hardware_or_adhesive_spec": null, "retention_method": null, "route": null, "thread_pilot_selection": null}` |
| `qidi_studio_roundtrip_confirmed` | **NOT_TESTED** | `{"critical_layer_preview_pass_by_job": {}, "evidence_reference_by_job": {}, "geometry_scale_percent_by_job": {}, "native_project_sha256_by_job": {}, "object_count_by_job": {}, "qidi_studio_version": null, "saved_profile_revision_by_job": {}, "validated_job_ids": []}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: Measured stylus, selected M2 screw or removable retaining method, pull gauge.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `petg_adapter_0p4`: 4 walls, 5 top / 5 bottom layers, 100% rectilinear infill.
- Supports: off. Bed adhesion: Use an 8 mm brim for the upright rod bushing; skirt is sufficient for the short collar.
- Dimensional controls: Calibrate elephant-foot compensation so split bores remain open at the first layer.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- Check bore, split and thin-wall pilot. Set projection, then quantify pull retention and repeat cycles; inspect after 24-hour creep and verify capacitive function.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, engraved identity and revision before cleanup.
- Quarantine any warped, cracked, delaminated, under-extruded, bridged-shut or untraceable part; do not silently rework a critical fit.
- Intended gate(s) after objective acceptance: `stylus_collar_retention_pass`, `stylus_function_pass`.

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


# Job 04C - Two keyboard-route rod bushings for retention qualification and one spare

| Control field | Released value |
|---|---|
| Design revision | `RC02-PRO-R1` |
| Lifecycle state | **UNRELEASED** |
| Route / stage | `keyboard_rod_route` / `route` |
| Kit | `KIT-TOOL-KB` |
| Plate | `04C_PETG_keyboard_rod_adapters.3mf` |
| Plate SHA-256 | `feb287014ddd1de53dcbd904953614f507ad0ab353590c75d0d2f0098160230f` |
| Profile | `petg_adapter_0p4` / `5addad813637abbe2dbc969afe8fde8637973498ff1f2439e590e070d62a2308` |
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
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "safe_plate_envelope_mm": [295, 295, 280]}` |
| `nozzle_0p4_confirmed` | **NOT_TESTED** | `{"installed_nozzle_mm": null, "verification_method": null}` |
| `petg_adapter_profile_calibrated` | **NOT_TESTED** | `{"brand": null, "calibration_result": null, "drying_record": null, "filament_name": null, "profile_revision": null, "spool_lot": null}` |
| `keyboard_rod_measured` | **NOT_TESTED** | `{"diameter_mm": null, "length_mm": null, "material": null, "measurement_locations": null}` |
| `adapter_retention_method_selected` | **NOT_TESTED** | `{"hardware_or_adhesive_spec": null, "retention_method": null, "route": null, "thread_pilot_selection": null}` |
| `geometry_matches_measurements` | **NOT_TESTED** | `{"affected_parts_reviewed": null, "design_revision": null, "effective_parameters_file": null, "measurement_record_revision": null, "regeneration_completed": null}` |
| `qidi_studio_roundtrip_confirmed` | **NOT_TESTED** | `{"critical_layer_preview_pass_by_job": {}, "evidence_reference_by_job": {}, "geometry_scale_percent_by_job": {}, "native_project_sha256_by_job": {}, "object_count_by_job": {}, "qidi_studio_version": null, "saved_profile_revision_by_job": {}, "validated_job_ids": []}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: Deburred 6 mm rod, selected retaining method, pull gauge.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `petg_adapter_0p4`: 4 walls, 5 top / 5 bottom layers, 100% rectilinear infill.
- Supports: off. Bed adhesion: Use an 8 mm brim for the upright rod bushing; skirt is sufficient for the short collar.
- Dimensional controls: Calibrate elephant-foot compensation so split bores remain open at the first layer.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- Check bore and split, press fit without cracks, set 30-40 mm projection, then quantify pull retention and 24-hour creep. No radial M3 screw is permitted in the thin flange.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, engraved identity and revision before cleanup.
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


# Job 05A - One phone TPU tip for dimensional and pull-off acceptance

| Control field | Released value |
|---|---|
| Design revision | `RC02-PRO-R1` |
| Lifecycle state | **UNRELEASED** |
| Route / stage | `required` / `first_article` |
| Kit | `KIT-PHONE` |
| Plate | `05A_TPU_phone_tip_first_article.3mf` |
| Plate SHA-256 | `05d7b42e788b5c03bc60740145ed28b08074330aa980aa9795f3c0c8d8c2e23b` |
| Profile | `tpu95a_0p4` / `59b69f285f6bead89753b66a3fa1005b3db9b065b58905e3dd84fa684dfa9e49` |
| Printer | QIDI Plus4; 305 x 305 x 280 mm nominal; 5 mm protected edge margin |
| Material / nozzle / layer | TPU 95A / 0.4 mm / 0.16 mm |
| Plate envelope | 7.5 x 7.5 x 8.0 mm; centered |
| Native slice record | QIDI Studio version, sliced mass and time: ____________________ |

## Objects and orientation

| STL | Qty | Locked orientation | Source SHA-256 |
|---|---:|---|---|
| `phone_clamp_tip_TPU_M4.stl` | 1 | Upright, flared bore entry on bed | `77883a940d153460346de3ffdfcf3a281e2572ab404dd1f4dc50ec8808afef94` |

## Required gates

| Gate | Status | Recorded values |
|---|---|---|
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "safe_plate_envelope_mm": [295, 295, 280]}` |
| `nozzle_0p4_confirmed` | **NOT_TESTED** | `{"installed_nozzle_mm": null, "verification_method": null}` |
| `tpu_profile_calibrated` | **NOT_TESTED** | `{"brand": null, "calibration_result": null, "drying_record": null, "filament_name": null, "profile_revision": null, "shore_hardness": "95A", "spool_lot": null}` |
| `qidi_studio_roundtrip_confirmed` | **NOT_TESTED** | `{"critical_layer_preview_pass_by_job": {}, "evidence_reference_by_job": {}, "geometry_scale_percent_by_job": {}, "native_project_sha256_by_job": {}, "object_count_by_job": {}, "qidi_studio_version": null, "saved_profile_revision_by_job": {}, "validated_job_ids": []}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: Actual M4 screw/peg and pull gauge.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `tpu95a_0p4`: 3 walls, 5 top / 5 bottom layers, 100% rectilinear infill.
- Supports: off. Bed adhesion: Clean PEI with no glue unless required by the exact TPU; use a 3 mm brim if a tip rocks.
- Dimensional controls: Dry filament and keep first-layer flow calibrated so the flared bore entries remain open.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- Inspect flared bore, seating witness and contact face. Fit to actual hardware, record seating depth and provisional axial pull force; retain as the first article.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, engraved identity and revision before cleanup.
- Quarantine any warped, cracked, delaminated, under-extruded, bridged-shut or untraceable part; do not silently rework a critical fit.
- Intended gate(s) after objective acceptance: `phone_tpu_retention_coupon_pass`.

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


# Job 05B - Three additional phone TPU tips, yielding two installed and two total spares

| Control field | Released value |
|---|---|
| Design revision | `RC02-PRO-R1` |
| Lifecycle state | **UNRELEASED** |
| Route / stage | `required` / `production` |
| Kit | `KIT-PHONE` |
| Plate | `05B_TPU_phone_tips_and_spares.3mf` |
| Plate SHA-256 | `58a9839c752eb968891f7bea76e2f95c51962d36f9d5013ff7c7cdcc446a67c9` |
| Profile | `tpu95a_0p4` / `59b69f285f6bead89753b66a3fa1005b3db9b065b58905e3dd84fa684dfa9e49` |
| Printer | QIDI Plus4; 305 x 305 x 280 mm nominal; 5 mm protected edge margin |
| Material / nozzle / layer | TPU 95A / 0.4 mm / 0.16 mm |
| Plate envelope | 47.5 x 7.5 x 8.0 mm; centered |
| Native slice record | QIDI Studio version, sliced mass and time: ____________________ |

## Objects and orientation

| STL | Qty | Locked orientation | Source SHA-256 |
|---|---:|---|---|
| `phone_clamp_tip_TPU_M4.stl` | 3 | Upright, flared bore entry on bed | `77883a940d153460346de3ffdfcf3a281e2572ab404dd1f4dc50ec8808afef94` |

## Required gates

| Gate | Status | Recorded values |
|---|---|---|
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "safe_plate_envelope_mm": [295, 295, 280]}` |
| `nozzle_0p4_confirmed` | **NOT_TESTED** | `{"installed_nozzle_mm": null, "verification_method": null}` |
| `tpu_profile_calibrated` | **NOT_TESTED** | `{"brand": null, "calibration_result": null, "drying_record": null, "filament_name": null, "profile_revision": null, "shore_hardness": "95A", "spool_lot": null}` |
| `phone_tpu_retention_coupon_pass` | **NOT_TESTED** | `{"axial_pull_test_method": null, "contact_face_result": null, "first_article_job": null, "installation_result": null, "pull_off_result": null}` |
| `qidi_studio_roundtrip_confirmed` | **NOT_TESTED** | `{"critical_layer_preview_pass_by_job": {}, "evidence_reference_by_job": {}, "geometry_scale_percent_by_job": {}, "native_project_sha256_by_job": {}, "object_count_by_job": {}, "qidi_studio_version": null, "saved_profile_revision_by_job": {}, "validated_job_ids": []}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: Accepted first article and actual M4 hardware.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `tpu95a_0p4`: 3 walls, 5 top / 5 bottom layers, 100% rectilinear infill.
- Supports: off. Bed adhesion: Clean PEI with no glue unless required by the exact TPU; use a 3 mm brim if a tip rocks.
- Dimensional controls: Dry filament and keep first-layer flow calibrated so the flared bore entries remain open.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- Compare all three with the accepted article; reject blocked bores, stringing or face defects. Label installed pair and spare pair across 05A/05B inventory.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, engraved identity and revision before cleanup.
- Quarantine any warped, cracked, delaminated, under-extruded, bridged-shut or untraceable part; do not silently rework a critical fit.
- Intended gate(s) after objective acceptance: `phone_tpu_batch_postprint_pass`.

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


# Job 05C - One keyboard TPU tip for dimensional and pull-off acceptance

| Control field | Released value |
|---|---|
| Design revision | `RC02-PRO-R1` |
| Lifecycle state | **UNRELEASED** |
| Route / stage | `keyboard_rod_route` / `first_article` |
| Kit | `KIT-TOOL-KB` |
| Plate | `05C_TPU_keyboard_tip_first_article.3mf` |
| Plate SHA-256 | `41396e0ed39b6662629bb10a23993eab7496816cb65cd709d81f16c8415b2c67` |
| Profile | `tpu95a_0p4` / `59b69f285f6bead89753b66a3fa1005b3db9b065b58905e3dd84fa684dfa9e49` |
| Printer | QIDI Plus4; 305 x 305 x 280 mm nominal; 5 mm protected edge margin |
| Material / nozzle / layer | TPU 95A / 0.4 mm / 0.16 mm |
| Plate envelope | 12.0 x 12.0 x 14.0 mm; centered |
| Native slice record | QIDI Studio version, sliced mass and time: ____________________ |

## Objects and orientation

| STL | Qty | Locked orientation | Source SHA-256 |
|---|---:|---|---|
| `keyboard_tip_TPU_6mm.stl` | 1 | Upright, flared bore entry on bed | `22ba42201e769ff4ed146b125d69d585b7188b7f274a1b3430b741ad62931d37` |

## Required gates

| Gate | Status | Recorded values |
|---|---|---|
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "safe_plate_envelope_mm": [295, 295, 280]}` |
| `nozzle_0p4_confirmed` | **NOT_TESTED** | `{"installed_nozzle_mm": null, "verification_method": null}` |
| `tpu_profile_calibrated` | **NOT_TESTED** | `{"brand": null, "calibration_result": null, "drying_record": null, "filament_name": null, "profile_revision": null, "shore_hardness": "95A", "spool_lot": null}` |
| `keyboard_rod_measured` | **NOT_TESTED** | `{"diameter_mm": null, "length_mm": null, "material": null, "measurement_locations": null}` |
| `qidi_studio_roundtrip_confirmed` | **NOT_TESTED** | `{"critical_layer_preview_pass_by_job": {}, "evidence_reference_by_job": {}, "geometry_scale_percent_by_job": {}, "native_project_sha256_by_job": {}, "object_count_by_job": {}, "qidi_studio_version": null, "saved_profile_revision_by_job": {}, "validated_job_ids": []}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: Actual 6 mm rod and pull gauge.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `tpu95a_0p4`: 3 walls, 5 top / 5 bottom layers, 100% rectilinear infill.
- Supports: off. Bed adhesion: Clean PEI with no glue unless required by the exact TPU; use a 3 mm brim if a tip rocks.
- Dimensional controls: Dry filament and keep first-layer flow calibrated so the flared bore entries remain open.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- Inspect bore entry, 8.5 mm seating witness and face. Record seating and axial pull force on the real rod; retain as first article.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, engraved identity and revision before cleanup.
- Quarantine any warped, cracked, delaminated, under-extruded, bridged-shut or untraceable part; do not silently rework a critical fit.
- Intended gate(s) after objective acceptance: `keyboard_tpu_retention_coupon_pass`.

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


# Job 05D - Three additional keyboard TPU tips, yielding two installed and two total spares

| Control field | Released value |
|---|---|
| Design revision | `RC02-PRO-R1` |
| Lifecycle state | **UNRELEASED** |
| Route / stage | `keyboard_rod_route` / `production` |
| Kit | `KIT-TOOL-KB` |
| Plate | `05D_TPU_keyboard_tips_and_spares.3mf` |
| Plate SHA-256 | `bf443f6f60d76e0b979218b090837654d87b4d6252922886dcd5be2fb8f8ac05` |
| Profile | `tpu95a_0p4` / `59b69f285f6bead89753b66a3fa1005b3db9b065b58905e3dd84fa684dfa9e49` |
| Printer | QIDI Plus4; 305 x 305 x 280 mm nominal; 5 mm protected edge margin |
| Material / nozzle / layer | TPU 95A / 0.4 mm / 0.16 mm |
| Plate envelope | 52.0 x 12.0 x 14.0 mm; centered |
| Native slice record | QIDI Studio version, sliced mass and time: ____________________ |

## Objects and orientation

| STL | Qty | Locked orientation | Source SHA-256 |
|---|---:|---|---|
| `keyboard_tip_TPU_6mm.stl` | 3 | Upright, flared bore entry on bed | `22ba42201e769ff4ed146b125d69d585b7188b7f274a1b3430b741ad62931d37` |

## Required gates

| Gate | Status | Recorded values |
|---|---|---|
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "safe_plate_envelope_mm": [295, 295, 280]}` |
| `nozzle_0p4_confirmed` | **NOT_TESTED** | `{"installed_nozzle_mm": null, "verification_method": null}` |
| `tpu_profile_calibrated` | **NOT_TESTED** | `{"brand": null, "calibration_result": null, "drying_record": null, "filament_name": null, "profile_revision": null, "shore_hardness": "95A", "spool_lot": null}` |
| `keyboard_rod_measured` | **NOT_TESTED** | `{"diameter_mm": null, "length_mm": null, "material": null, "measurement_locations": null}` |
| `keyboard_tpu_retention_coupon_pass` | **NOT_TESTED** | `{"axial_pull_test_method": null, "contact_face_result": null, "first_article_job": null, "installation_result": null, "pull_off_result": null}` |
| `qidi_studio_roundtrip_confirmed` | **NOT_TESTED** | `{"critical_layer_preview_pass_by_job": {}, "evidence_reference_by_job": {}, "geometry_scale_percent_by_job": {}, "native_project_sha256_by_job": {}, "object_count_by_job": {}, "qidi_studio_version": null, "saved_profile_revision_by_job": {}, "validated_job_ids": []}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: Accepted first article and actual 6 mm rod.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `tpu95a_0p4`: 3 walls, 5 top / 5 bottom layers, 100% rectilinear infill.
- Supports: off. Bed adhesion: Clean PEI with no glue unless required by the exact TPU; use a 3 mm brim if a tip rocks.
- Dimensional controls: Dry filament and keep first-layer flow calibrated so the flared bore entries remain open.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- Compare all three with the accepted article; reject blocked bores or face defects. Label installed parts and spares.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, engraved identity and revision before cleanup.
- Quarantine any warped, cracked, delaminated, under-extruded, bridged-shut or untraceable part; do not silently rework a critical fit.
- Intended gate(s) after objective acceptance: `keyboard_tpu_batch_postprint_pass`.

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


# Job 07A - First corrected mast foot with rear-lug clamp bolts

| Control field | Released value |
|---|---|
| Design revision | `RC02-PRO-R1` |
| Lifecycle state | **UNRELEASED** |
| Route / stage | `camera_mast_optional` / `first_article` |
| Kit | `KIT-MAST` |
| Plate | `07A_ASA_mast_foot_first_article.3mf` |
| Plate SHA-256 | `7f25240ea27f296a96ffa6b809fa4069ad633559d3741841919a340e0b481ee7` |
| Profile | `asa_structural_0p4` / `7f5a63b82b79566c55df616753ef9acc31e6a172a2689b726498aa2cb82c7a22` |
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
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "safe_plate_envelope_mm": [295, 295, 280]}` |
| `nozzle_0p4_confirmed` | **NOT_TESTED** | `{"installed_nozzle_mm": null, "verification_method": null}` |
| `asa_profile_calibrated` | **NOT_TESTED** | `{"brand": null, "calibration_result": null, "chamber_condition": null, "drying_record": null, "filament_name": null, "profile_revision": null, "spool_lot": null}` |
| `asa_mast_socket_coupon_pass` | **NOT_TESTED** | `{"extrusion_x_mm": null, "extrusion_y_mm": null, "fit_result": null, "selected_socket_mm": null}` |
| `asa_m5_nut_coupon_pass` | **NOT_TESTED** | `{"nut_across_flats_mm": null, "nut_thickness_mm": null, "retention_result": null, "selected_hex_mm": null}` |
| `asa_m5_clearance_coupon_pass` | **NOT_TESTED** | `{"bolt_major_diameter_mm": null, "m5_washer_fit_result": null, "m5_washer_od_mm": null, "selected_base_hole_mm": null, "selected_horizontal_hole_mm": null}` |
| `geometry_matches_measurements` | **NOT_TESTED** | `{"affected_parts_reviewed": null, "design_revision": null, "effective_parameters_file": null, "measurement_record_revision": null, "regeneration_completed": null}` |
| `qidi_studio_roundtrip_confirmed` | **NOT_TESTED** | `{"critical_layer_preview_pass_by_job": {}, "evidence_reference_by_job": {}, "geometry_scale_percent_by_job": {}, "native_project_sha256_by_job": {}, "object_count_by_job": {}, "qidi_studio_version": null, "saved_profile_revision_by_job": {}, "validated_job_ids": []}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: One extrusion, two M5 clamp bolts/nuts, four base fasteners/washers.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `asa_structural_0p4`: 6 walls, 6 top / 6 bottom layers, 45% gyroid infill.
- Supports: build-plate only under transverse bores if needed. Bed adhesion: 10 mm brim, enclosed printer, stable chamber, and no drafts.
- Dimensional controls: Use the ASA socket and nut coupons from the same spool before the first full foot.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- Inspect layer bonding, flatness, socket, rear slit, lead-ins and rear-lug bolt path. Tighten bolts alternately; record grip, cracks and flatness immediately and after 24 hours.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, engraved identity and revision before cleanup.
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


# Job 07B - Second camera mast foot after first-article acceptance

| Control field | Released value |
|---|---|
| Design revision | `RC02-PRO-R1` |
| Lifecycle state | **UNRELEASED** |
| Route / stage | `camera_mast_optional` / `optional` |
| Kit | `KIT-MAST` |
| Plate | `07B_ASA_mast_foot_second.3mf` |
| Plate SHA-256 | `63c6e356e24b395b53d4780ba27e248d6b6a836d0920af1070d2719b9b7f8bc3` |
| Profile | `asa_structural_0p4` / `7f5a63b82b79566c55df616753ef9acc31e6a172a2689b726498aa2cb82c7a22` |
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
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "safe_plate_envelope_mm": [295, 295, 280]}` |
| `nozzle_0p4_confirmed` | **NOT_TESTED** | `{"installed_nozzle_mm": null, "verification_method": null}` |
| `asa_profile_calibrated` | **NOT_TESTED** | `{"brand": null, "calibration_result": null, "chamber_condition": null, "drying_record": null, "filament_name": null, "profile_revision": null, "spool_lot": null}` |
| `asa_mast_socket_coupon_pass` | **NOT_TESTED** | `{"extrusion_x_mm": null, "extrusion_y_mm": null, "fit_result": null, "selected_socket_mm": null}` |
| `asa_m5_nut_coupon_pass` | **NOT_TESTED** | `{"nut_across_flats_mm": null, "nut_thickness_mm": null, "retention_result": null, "selected_hex_mm": null}` |
| `asa_m5_clearance_coupon_pass` | **NOT_TESTED** | `{"bolt_major_diameter_mm": null, "m5_washer_fit_result": null, "m5_washer_od_mm": null, "selected_base_hole_mm": null, "selected_horizontal_hole_mm": null}` |
| `geometry_matches_measurements` | **NOT_TESTED** | `{"affected_parts_reviewed": null, "design_revision": null, "effective_parameters_file": null, "measurement_record_revision": null, "regeneration_completed": null}` |
| `mast_foot_first_article_pass` | **NOT_TESTED** | `{"base_flatness_mm": null, "bolt_clamp_result": null, "crack_result_after_24h": null, "initial_crack_result": null, "job_id": null, "nut_fit_result": null, "socket_fit_result": null}` |
| `qidi_studio_roundtrip_confirmed` | **NOT_TESTED** | `{"critical_layer_preview_pass_by_job": {}, "evidence_reference_by_job": {}, "geometry_scale_percent_by_job": {}, "native_project_sha256_by_job": {}, "object_count_by_job": {}, "qidi_studio_version": null, "saved_profile_revision_by_job": {}, "validated_job_ids": []}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: Accepted first foot, second extrusion/foot hardware and crossbar.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `asa_structural_0p4`: 6 walls, 6 top / 6 bottom layers, 45% gyroid infill.
- Supports: build-plate only under transverse bores if needed. Bed adhesion: 10 mm brim, enclosed printer, stable chamber, and no drafts.
- Dimensional controls: Use the ASA socket and nut coupons from the same spool before the first full foot.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- Repeat 07A checks, label feet A/B, assemble the pair, then verify matched seating, crossbar level, plumb witness lines and stand stability.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, engraved identity and revision before cleanup.
- Quarantine any warped, cracked, delaminated, under-extruded, bridged-shut or untraceable part; do not silently rework a critical fit.
- Intended gate(s) after objective acceptance: `mast_second_foot_postprint_pass`, `mast_pair_installation_pass`.

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


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

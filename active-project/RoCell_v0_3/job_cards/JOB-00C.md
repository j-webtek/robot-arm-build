# Job 00C - ABS RoArm grip, stepped spring seat, profile-specific M3 insert, and M3 head tests using the exact tool profile

| Control field | Released value |
|---|---|
| Design revision | `RC03-INT-R1` |
| Lifecycle state | **UNRELEASED** |
| Route / stage | `required` / `diagnostic` |
| Kit | `KIT-CAL` |
| Plate | `00C_ABS_tool_profile_fit_tests.3mf` |
| Plate SHA-256 | `53f14d77ecbebc10860a80122d53860c8789249c29f6af2eecd455855fa14af5` |
| Profile | `abs_rapido_precision_0p4` / `60827c142c2f8e88c0a45ace71712cf2c94f84d66dc796880352ab32de1e7195` |
| Exact settings sheet | `print_plates_3mf/00C_ABS_tool_profile_fit_tests.PRINT_SETTINGS.md` / `59acdd097bba18a034df2e96cb271f7766e73d40de35bf780a890d1ac3727c66` |
| QIDI process import | `slicer_profiles/QIDI_PLUS4/abs_rapido_precision_0p4.process.json` / `c115ad0ca8acafa86bc303973bbbae27578fdd57db8cbf437a7c8175710ba90a` |
| Filament preset | `qidi_abs_rapido_xplus4_0p4` / `ce549e11c71d71294ae086694987ac99842a14ba8fc26e24a879f7dd31b65bd4` |
| Preset completeness | **EXACT_REPRODUCIBLE** |
| Unresolved filament fields | None |
| Printer | QIDI Plus4; 305 x 305 x 280 mm nominal; 5 mm protected edge margin |
| Material / nozzle / layer | QIDI ABS Rapido / 0.4 mm / 0.16 mm |
| Plate envelope | 156.0 x 70.0 x 34.0 mm; centered |
| Native slice record | QIDI Studio version, sliced mass and time: ____________________ |

## Objects and orientation

| STL | Qty | Locked orientation | Source SHA-256 |
|---|---:|---|---|
| `compliant_tool_grip_fit_test.stl` | 1 | Upright as exported; full 28 mm grip face vertical | `2c892ebeccd9d4512bf877cac3c1d56c87329c1a30a47165221480021104d935` |
| `spring_fit_gauge.stl` | 1 | Flat as exported; stepped cup upward | `0b8464e8506bea26cc8972ce32fcfc4e7366c800eac4ee23e6fcd16677672f4c` |
| `tool_m3_insert_fit_gauge.stl` | 1 | Flat as exported; TOOL label and insert mouths upward | `8ff0775cb466170e0749bf125b4b2743f134df072f75ac17090d61854fbc7d8d` |
| `m3_head_fit_gauge.stl` | 1 | Flat as exported; H5.8/H6.2/H6.6 labels upward | `7d1206ee09722d99cff871031562943e405c263ea5d1d1f5d82e193bf403cb2e` |

## Required gates

| Gate | Status | Recorded values |
|---|---|---|
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "provisional_protected_envelope_mm": [295, 295, 275]}` |
| `plus4_protected_envelope_verified` | **PASS** | `{"build_surface": "QIDI dual-sided textured PEI plate", "carriage_clearance_result": "PASS - protected envelope is inside official nominal volume", "enclosure_clearance_result": "PASS - operator confirmed completed printer qualification", "firmware_version": "Plus4_v1.7.1 official baseline; operator confirmed fully updated", "full_travel_test_result": "PASS - operator confirmed completed printer qualification", "printer_serial": "NOT_TRACKED_PROTOTYPE", "purge_and_exclusion_zone_result": "PASS - operator confirmed completed printer qualification", "verified_protected_envelope_mm": [295, 295, 275]}` |
| `nozzle_0p4_confirmed` | **PASS** | `{"installed_nozzle_mm": 0.4, "verification_method": "Official QIDI Plus4 standard specification and official printer.cfg; operator confirmed printer configuration"}` |
| `abs_rapido_precision_profile_calibrated` | **PASS** | `{"brand": "QIDI", "calibration_result": "PASS - operator confirmed the installed QIDI ABS Rapido preset and current native Job 00A slice; matching coupons provide dimensional release", "chamber_condition": "QIDI Plus4 enclosure sealed; 55 C chamber target from the installed QIDI ABS Rapido preset", "drying_record": "Operator confirmed print-ready; detailed drying record waived for prototype coupons", "filament_name": "ABS Rapido", "profile_revision": "RC03-INT-R1 abs_rapido_precision_0p4 SHA256 60827c142c2f8e88c0a45ace71712cf2c94f84d66dc796880352ab32de1e7195", "spool_lot": "NOT_TRACKED_PROTOTYPE"}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: RoArm gripper, actual spring, M3 inserts/screws, calipers.
- Open `print_plates_3mf/00C_ABS_tool_profile_fit_tests.PRINT_SETTINGS.md` and follow every exact value in it.
- Import `slicer_profiles/QIDI_PLUS4/abs_rapido_precision_0p4.process.json` and select `QIDI ABS Rapido @Qidi X-Plus 4 0.4 nozzle` as the separate filament preset.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `abs_rapido_precision_0p4`: 5 walls, 6 top / 6 bottom layers, 40% gyroid infill.
- Supports: off. Bed adhesion: 5 mm outer brim with 0.05 mm object gap on clean textured PEI.
- Dimensional controls: Keep the seam off gripper flats, spring seats, insert pockets, and the sliding guide bore; zero XY compensation pending Job 00C.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- Verify the full 28 mm grip interface; record no slip/crush; record spring OD/ID/free length and both seat fits; install-test each production-edge-representative M3 pocket and select the smallest below-flush M3 head recess.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, modeled identity and revision before cleanup.
- Quarantine any warped, cracked, delaminated, under-extruded, bridged-shut or untraceable part; do not silently rework a critical fit.
- Intended gate(s) after objective acceptance: `gripper_coupon_pass`, `spring_fit_coupon_pass`, `compliant_tool_m3_insert_coupon_pass`, `precision_m3_head_coupon_pass`.

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

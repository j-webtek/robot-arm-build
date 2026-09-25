# RoCell RC03-INT-R1 - controlled print job cards

These travelers are generated from the authoritative job, profile, gate, lifecycle and 3MF sidecar records. Complete one card per physical plate. Never infer release from a filename: the prerequisite table and lifecycle state control the work.

Generated coverage: **24 jobs** on the QIDI Plus4.

# Job 00A - ABS keyboard datum, board/seam locator, clearance, and washer qualification using the exact station profile

| Control field | Released value |
|---|---|
| Design revision | `RC03-INT-R1` |
| Lifecycle state | **POSTPRINT_PASS** |
| Route / stage | `required` / `diagnostic` |
| Kit | `KIT-CAL` |
| Plate | `00A_ABS_keyboard_station_fit_tests.3mf` |
| Plate SHA-256 | `cdedea55ccdf765a78d35b976cbd18ea153dc8caf6fb91ce08e507c9be837237` |
| Profile | `abs_rapido_tray_structural_0p4` / `4cc77d229e3f397c7f8d7c1a793ace5ba9490cafe2ef9d31f16e7ffa4c28123f` |
| Exact settings sheet | `print_plates_3mf/00A_ABS_keyboard_station_fit_tests.PRINT_SETTINGS.md` / `86498dd72c486e0df6386a8b96cd48884270c5c05b8efeaf4f41921e3919e323` |
| QIDI process import | `slicer_profiles/QIDI_PLUS4/abs_rapido_tray_structural_0p4.process.json` / `c89e92d6af33cb676d7200e34937ec05c7cec9b55f2d0700b07b89a57cbd81c6` |
| Filament preset | `qidi_abs_rapido_xplus4_0p4` / `ce549e11c71d71294ae086694987ac99842a14ba8fc26e24a879f7dd31b65bd4` |
| Preset completeness | **EXACT_REPRODUCIBLE** |
| Unresolved filament fields | None |
| Printer | QIDI Plus4; 305 x 305 x 280 mm nominal; 5 mm protected edge margin |
| Material / nozzle / layer | QIDI ABS Rapido / 0.4 mm / 0.20 mm |
| Plate envelope | 246.0 x 122.0 x 11.0 mm; centered |
| Native slice record | QIDI Studio version, sliced mass and time: ____________________ |

## Objects and orientation

| STL | Qty | Locked orientation | Source SHA-256 |
|---|---:|---|---|
| `keyboard_corner_fit_test.stl` | 1 | Flat as exported | `c12095d3506ea86025fcef6cd34702efb391aec1e00c9b23fd77bdb250703ad3` |
| `station_locator_fit_gauge.stl` | 1 | Flat as exported; raised BOARD-R/BOARD-S/SEAM-R/SEAM-S labels upward | `7b34ff9a05495ce702310171cd27c5201e0c1ee54fede8c9cdbeea7260d3d1d5` |
| `hardware_fit_gauge.stl` | 1 | Flat as exported; raised D3.2 through D5.7 labels upward | `4a9a35b618a420931b7e8b6b717aee4a3eb68f8948fff04e5a69fd65266e9e42` |
| `m4_washer_fit_gauge.stl` | 1 | Flat as exported; raised OD8.8/OD9.2/OD9.6 labels upward | `98f27d3b7f274754a274f9856a8318c8b0c98f2fb5b485223fec74236ae349ff` |

## Required gates

| Gate | Status | Recorded values |
|---|---|---|
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "provisional_protected_envelope_mm": [295, 295, 275]}` |
| `plus4_protected_envelope_verified` | **PASS** | `{"build_surface": "QIDI dual-sided textured PEI plate", "carriage_clearance_result": "PASS - protected envelope is inside official nominal volume", "enclosure_clearance_result": "PASS - operator confirmed completed printer qualification", "firmware_version": "Plus4_v1.7.1 official baseline; operator confirmed fully updated", "full_travel_test_result": "PASS - operator confirmed completed printer qualification", "printer_serial": "NOT_TRACKED_PROTOTYPE", "purge_and_exclusion_zone_result": "PASS - operator confirmed completed printer qualification", "verified_protected_envelope_mm": [295, 295, 275]}` |
| `nozzle_0p4_confirmed` | **PASS** | `{"installed_nozzle_mm": 0.4, "verification_method": "Official QIDI Plus4 standard specification and official printer.cfg; operator confirmed printer configuration"}` |
| `abs_rapido_tray_profile_calibrated` | **PASS** | `{"brand": "QIDI", "calibration_result": "PASS - operator confirmed the installed QIDI ABS Rapido preset and current native Job 00A slice; matching coupons provide dimensional release", "chamber_condition": "QIDI Plus4 enclosure sealed; 55 C chamber target from the installed QIDI ABS Rapido preset", "drying_record": "Operator confirmed print-ready; detailed drying record waived for prototype coupons", "filament_name": "ABS Rapido", "profile_revision": "RC03-INT-R1 abs_rapido_tray_structural_0p4 SHA256 4cc77d229e3f397c7f8d7c1a793ace5ba9490cafe2ef9d31f16e7ffa4c28123f", "spool_lot": "NOT_TRACKED_PROTOTYPE"}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: Actual keyboard, 6 mm dowel pins, M4 screws/washers, calipers.
- Open `print_plates_3mf/00A_ABS_keyboard_station_fit_tests.PRINT_SETTINGS.md` and follow every exact value in it.
- Import `slicer_profiles/QIDI_PLUS4/abs_rapido_tray_structural_0p4.process.json` and select `QIDI ABS Rapido @Qidi X-Plus 4 0.4 nozzle` as the separate filament preset.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `abs_rapido_tray_structural_0p4`: 5 walls, 6 top / 6 bottom layers, 35% gyroid infill.
- Supports: off. Bed adhesion: 8 mm outer brim with 0.05 mm object gap; clean textured PEI; one production station per plate.
- Dimensional controls: Keep the slicer seam away from locator sockets, relieved hold-down holes, seam datums, clamp guides, and keyboard contact datums; zero XY compensation pending Job 00A.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- Inspect every production-axis round hole and radial slot. Select the smallest hand-serviceable 6 mm board locator pair, cycle the pins 20 times, verify keyboard corner clearance only, and record accepted clearance/washer choices. Retain the seam round/radial section for use with the actual master posts after job 01.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, modeled identity and revision before cleanup.
- Quarantine any warped, cracked, delaminated, under-extruded, bridged-shut or untraceable part; do not silently rework a critical fit.
- Intended gate(s) after objective acceptance: `keyboard_corner_coupon_pass`, `keyboard_station_registration_coupon_pass`, `tray_clearance_holes_coupon_pass`.

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


# Job 00B - ABS phone width, station locator, profile-specific M3 insert, and washer qualification; retained nut and cable-saddle objects document superseded screening geometry

| Control field | Released value |
|---|---|
| Design revision | `RC03-INT-R1` |
| Lifecycle state | **PRINTED** |
| Route / stage | `required` / `diagnostic` |
| Kit | `KIT-CAL` |
| Plate | `00B_ABS_phone_station_fit_tests.3mf` |
| Plate SHA-256 | `cd7d1eddac818cb7268d3b6b71a21c72f609bcd2dfd66834d00fe2f31f668a76` |
| Profile | `abs_rapido_cradle_0p4` / `0dca510bbadec73f611b731a8fd24f22310b3ba113759f58f0ed7f1cdc33c545` |
| Exact settings sheet | `print_plates_3mf/00B_ABS_phone_station_fit_tests.PRINT_SETTINGS.md` / `5dde496287138dc5f8bf01eab3a3217fcf332374e092a4c46f49ae3a9ffda544` |
| QIDI process import | `slicer_profiles/QIDI_PLUS4/abs_rapido_cradle_0p4.process.json` / `9276ce2983256d815925224e7d8fc45032a531678dc336713fc88fa96137e259` |
| Filament preset | `qidi_abs_rapido_xplus4_0p4` / `ce549e11c71d71294ae086694987ac99842a14ba8fc26e24a879f7dd31b65bd4` |
| Preset completeness | **EXACT_REPRODUCIBLE** |
| Unresolved filament fields | None |
| Printer | QIDI Plus4; 305 x 305 x 280 mm nominal; 5 mm protected edge margin |
| Material / nozzle / layer | QIDI ABS Rapido / 0.4 mm / 0.20 mm |
| Plate envelope | 256.0 x 172.0 x 16.6 mm; centered |
| Native slice record | QIDI Studio version, sliced mass and time: ____________________ |

## Objects and orientation

| STL | Qty | Locked orientation | Source SHA-256 |
|---|---:|---|---|
| `phone_width_fit_test.stl` | 1 | Flat as exported | `1091a6d591259a4a22b6d9fd7b36d4a8264807ef5c169fe3c5b1019a16420cfa` |
| `station_locator_fit_gauge.stl` | 1 | Flat as exported; raised BOARD-R/BOARD-S/SEAM-R/SEAM-S labels upward | `7b34ff9a05495ce702310171cd27c5201e0c1ee54fede8c9cdbeea7260d3d1d5` |
| `m4_captive_nut_fit_gauge.stl` | 1 | Flat as exported; top-loaded horizontal nut-channel labels upward | `5771bfa01542ab24999c806f4347486d6cc1800f6a13a17ebfdb9264644e8aec` |
| `phone_m3_insert_fit_gauge.stl` | 1 | Flat as exported; PHONE label and insert mouths upward | `54a7990f706256dd30d3d5ea7487f479e970c1e1d8f212be1996b6df6d1a2e65` |
| `cable_tie_saddle_fit_gauge.stl` | 1 | Flat as exported; saddles upward | `8de2b07efef5bef8ef9297407c0bd22dd7945adc16f84fd0dab236e304398598` |
| `m4_washer_fit_gauge.stl` | 1 | Flat as exported; raised OD8.8/OD9.2/OD9.6 labels upward | `98f27d3b7f274754a274f9856a8318c8b0c98f2fb5b485223fec74236ae349ff` |

## Required gates

| Gate | Status | Recorded values |
|---|---|---|
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "provisional_protected_envelope_mm": [295, 295, 275]}` |
| `plus4_protected_envelope_verified` | **PASS** | `{"build_surface": "QIDI dual-sided textured PEI plate", "carriage_clearance_result": "PASS - protected envelope is inside official nominal volume", "enclosure_clearance_result": "PASS - operator confirmed completed printer qualification", "firmware_version": "Plus4_v1.7.1 official baseline; operator confirmed fully updated", "full_travel_test_result": "PASS - operator confirmed completed printer qualification", "printer_serial": "NOT_TRACKED_PROTOTYPE", "purge_and_exclusion_zone_result": "PASS - operator confirmed completed printer qualification", "verified_protected_envelope_mm": [295, 295, 275]}` |
| `nozzle_0p4_confirmed` | **PASS** | `{"installed_nozzle_mm": 0.4, "verification_method": "Official QIDI Plus4 standard specification and official printer.cfg; operator confirmed printer configuration"}` |
| `abs_rapido_cradle_profile_calibrated` | **PASS** | `{"brand": "QIDI", "calibration_result": "PASS - operator confirmed the installed QIDI ABS Rapido preset and current native Job 00A slice; matching coupons provide dimensional release", "chamber_condition": "QIDI Plus4 enclosure sealed; 55 C chamber target from the installed QIDI ABS Rapido preset", "drying_record": "Operator confirmed print-ready; detailed drying record waived for prototype coupons", "filament_name": "ABS Rapido", "profile_revision": "RC03-INT-R1 abs_rapido_cradle_0p4 SHA256 0dca510bbadec73f611b731a8fd24f22310b3ba113759f58f0ed7f1cdc33c545", "spool_lot": "NOT_TRACKED_PROTOTYPE"}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: Actual phone/case, 6 mm dowel pins, M4 hardware, M3 inserts, washers, USB cable and selected wider tie.
- Open `print_plates_3mf/00B_ABS_phone_station_fit_tests.PRINT_SETTINGS.md` and follow every exact value in it.
- Import `slicer_profiles/QIDI_PLUS4/abs_rapido_cradle_0p4.process.json` and select `QIDI ABS Rapido @Qidi X-Plus 4 0.4 nozzle` as the separate filament preset.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `abs_rapido_cradle_0p4`: 5 walls, 5 top / 5 bottom layers, 30% gyroid infill.
- Supports: off; stop and obtain engineering approval if the locked layer preview shows an unprintable tower. Bed adhesion: 8 mm outer brim with 0.05 mm object gap on clean textured PEI.
- Dimensional controls: Use the same-profile ABS locator, captive-M4, vertical-M3-insert, cable-saddle, and washer coupons; do not rework a released socket ad hoc.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- Record the phone hand-fit, independent service-station round socket and radial-slot width, PHONE-labeled M3 insert gauge with its production 0.3 mm floor, and smallest flat-seating M4 washer recess. Retain the failed nut and cable-saddle objects as superseded screening evidence; they do not qualify the redesigned production rail.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, modeled identity and revision before cleanup.
- Quarantine any warped, cracked, delaminated, under-extruded, bridged-shut or untraceable part; do not silently rework a critical fit.
- Intended gate(s) after objective acceptance: `phone_width_coupon_pass`, `phone_station_registration_coupon_pass`, `phone_station_m3_insert_coupon_pass`, `cradle_m4_washer_coupon_pass`.

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


# Job 00E - ABS general clearance, screw-head, washer, camera-hex, and TPU-retention setup tests

| Control field | Released value |
|---|---|
| Design revision | `RC03-INT-R1` |
| Lifecycle state | **UNRELEASED** |
| Route / stage | `required` / `diagnostic` |
| Kit | `KIT-CAL` |
| Plate | `00E_ABS_general_setup_tests.3mf` |
| Plate SHA-256 | `67073d37df50d0329a6b77ba5aed00166fff9cc850c9f6225b00abeba54661d7` |
| Profile | `abs_rapido_general_0p4` / `4d9038f98da0892dca1031e59696babbbf913c0947f9e4cbac288c6182d1bede` |
| Exact settings sheet | `print_plates_3mf/00E_ABS_general_setup_tests.PRINT_SETTINGS.md` / `0a1da7fcba38d7c228f9d681e467961e3bfe3069356d0591eab0a5fbbee8cbe5` |
| QIDI process import | `slicer_profiles/QIDI_PLUS4/abs_rapido_general_0p4.process.json` / `756895e547ed186ab4b0d532d6d66fc3e2ad31376bc342a0150cbd4667a5d239` |
| Filament preset | `qidi_abs_rapido_xplus4_0p4` / `ce549e11c71d71294ae086694987ac99842a14ba8fc26e24a879f7dd31b65bd4` |
| Preset completeness | **EXACT_REPRODUCIBLE** |
| Unresolved filament fields | None |
| Printer | QIDI Plus4; 305 x 305 x 280 mm nominal; 5 mm protected edge margin |
| Material / nozzle / layer | QIDI ABS Rapido / 0.4 mm / 0.20 mm |
| Plate envelope | 208.0 x 124.0 x 14.0 mm; centered |
| Native slice record | QIDI Studio version, sliced mass and time: ____________________ |

## Objects and orientation

| STL | Qty | Locked orientation | Source SHA-256 |
|---|---:|---|---|
| `hardware_fit_gauge.stl` | 1 | Flat as exported; raised D3.2 through D5.7 labels upward | `4a9a35b618a420931b7e8b6b717aee4a3eb68f8948fff04e5a69fd65266e9e42` |
| `setup_hardware_fit_gauge.stl` | 1 | Flat as exported; all labels upward | `e6394a26fe104fb2af1b05df14865a5be2908bf6e99fab79c93aa034a2dc57b4` |
| `tpu_tip_retention_gauge.stl` | 1 | Flat base on bed; both rigid pegs upward | `0476c9c867a9f28816c5df107f8bcff9e44b7e1ba79e8927501a8d1c6d32b777` |

## Required gates

| Gate | Status | Recorded values |
|---|---|---|
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "provisional_protected_envelope_mm": [295, 295, 275]}` |
| `plus4_protected_envelope_verified` | **PASS** | `{"build_surface": "QIDI dual-sided textured PEI plate", "carriage_clearance_result": "PASS - protected envelope is inside official nominal volume", "enclosure_clearance_result": "PASS - operator confirmed completed printer qualification", "firmware_version": "Plus4_v1.7.1 official baseline; operator confirmed fully updated", "full_travel_test_result": "PASS - operator confirmed completed printer qualification", "printer_serial": "NOT_TRACKED_PROTOTYPE", "purge_and_exclusion_zone_result": "PASS - operator confirmed completed printer qualification", "verified_protected_envelope_mm": [295, 295, 275]}` |
| `nozzle_0p4_confirmed` | **PASS** | `{"installed_nozzle_mm": 0.4, "verification_method": "Official QIDI Plus4 standard specification and official printer.cfg; operator confirmed printer configuration"}` |
| `abs_rapido_general_profile_calibrated` | **PASS** | `{"brand": "QIDI", "calibration_result": "PASS - operator confirmed the installed QIDI ABS Rapido preset and current native Job 00A slice; matching coupons provide dimensional release", "chamber_condition": "QIDI Plus4 enclosure sealed; 55 C chamber target from the installed QIDI ABS Rapido preset", "drying_record": "Operator confirmed print-ready; detailed drying record waived for prototype coupons", "filament_name": "ABS Rapido", "profile_revision": "RC03-INT-R1 abs_rapido_general_0p4 SHA256 4d9038f98da0892dca1031e59696babbbf913c0947f9e4cbac288c6182d1bede", "spool_lot": "NOT_TRACKED_PROTOTYPE"}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: M3/M4/M5 screws, washers, 1/4-20 hardware, TPU tip samples.
- Open `print_plates_3mf/00E_ABS_general_setup_tests.PRINT_SETTINGS.md` and follow every exact value in it.
- Import `slicer_profiles/QIDI_PLUS4/abs_rapido_general_0p4.process.json` and select `QIDI ABS Rapido @Qidi X-Plus 4 0.4 nozzle` as the separate filament preset.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `abs_rapido_general_0p4`: 4 walls, 5 top / 5 bottom layers, 25% gyroid infill.
- Supports: off. Bed adhesion: 5 mm outer brim with 0.05 mm object gap on clean textured PEI.
- Dimensional controls: Zero XY contour and hole compensation until the matching ABS coupon provides measured evidence; elephant-foot compensation 0.15 mm.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- Record general clearances, screw-head and washer seats, camera hex choice, and rigid-peg preliminary fit. Do not use the rigid peg alone to release TPU production.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, modeled identity and revision before cleanup.
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


# Job 00F - ABS M3 clearance and M3 button-head recess verification using the exact fine-layer calibration-puck profile

| Control field | Released value |
|---|---|
| Design revision | `RC03-INT-R1` |
| Lifecycle state | **UNRELEASED** |
| Route / stage | `required` / `diagnostic` |
| Kit | `KIT-CAL` |
| Plate | `00F_ABS_calibration_profile_clearance_test.3mf` |
| Plate SHA-256 | `dc2f6af58b927da87ae6a2469ab8ce8a00ce029e550b5d171833d2152e2b6b9c` |
| Profile | `abs_rapido_calibration_0p4` / `f3c6513d491cad5e3fc611549c640439ac58189ddea5c79fe01725e3a846b114` |
| Exact settings sheet | `print_plates_3mf/00F_ABS_calibration_profile_clearance_test.PRINT_SETTINGS.md` / `9d808f626a6a47e7609fdd206e314f5e69c06c4972844e791dcdba86262a47e9` |
| QIDI process import | `slicer_profiles/QIDI_PLUS4/abs_rapido_calibration_0p4.process.json` / `c069454369dc8abe726d0db4359928e9fa870c694cdfdf7b044a3debeeb2d564` |
| Filament preset | `qidi_abs_rapido_xplus4_0p4` / `ce549e11c71d71294ae086694987ac99842a14ba8fc26e24a879f7dd31b65bd4` |
| Preset completeness | **EXACT_REPRODUCIBLE** |
| Unresolved filament fields | None |
| Printer | QIDI Plus4; 305 x 305 x 280 mm nominal; 5 mm protected edge margin |
| Material / nozzle / layer | QIDI ABS Rapido / 0.4 mm / 0.16 mm |
| Plate envelope | 160.0 x 70.0 x 6.6 mm; centered |
| Native slice record | QIDI Studio version, sliced mass and time: ____________________ |

## Objects and orientation

| STL | Qty | Locked orientation | Source SHA-256 |
|---|---:|---|---|
| `hardware_fit_gauge.stl` | 1 | Flat as exported; raised D3.2 through D5.7 labels upward | `4a9a35b618a420931b7e8b6b717aee4a3eb68f8948fff04e5a69fd65266e9e42` |
| `m3_head_fit_gauge.stl` | 1 | Flat as exported; H5.8/H6.2/H6.6 labels upward | `7d1206ee09722d99cff871031562943e405c263ea5d1d1f5d82e193bf403cb2e` |

## Required gates

| Gate | Status | Recorded values |
|---|---|---|
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "provisional_protected_envelope_mm": [295, 295, 275]}` |
| `plus4_protected_envelope_verified` | **PASS** | `{"build_surface": "QIDI dual-sided textured PEI plate", "carriage_clearance_result": "PASS - protected envelope is inside official nominal volume", "enclosure_clearance_result": "PASS - operator confirmed completed printer qualification", "firmware_version": "Plus4_v1.7.1 official baseline; operator confirmed fully updated", "full_travel_test_result": "PASS - operator confirmed completed printer qualification", "printer_serial": "NOT_TRACKED_PROTOTYPE", "purge_and_exclusion_zone_result": "PASS - operator confirmed completed printer qualification", "verified_protected_envelope_mm": [295, 295, 275]}` |
| `nozzle_0p4_confirmed` | **PASS** | `{"installed_nozzle_mm": 0.4, "verification_method": "Official QIDI Plus4 standard specification and official printer.cfg; operator confirmed printer configuration"}` |
| `abs_rapido_calibration_profile_calibrated` | **PASS** | `{"brand": "QIDI", "calibration_result": "PASS - operator confirmed the installed QIDI ABS Rapido preset and current native Job 00A slice; matching coupons provide dimensional release", "chamber_condition": "QIDI Plus4 enclosure sealed; 55 C chamber target from the installed QIDI ABS Rapido preset", "drying_record": "Operator confirmed print-ready; detailed drying record waived for prototype coupons", "filament_name": "ABS Rapido", "profile_revision": "RC03-INT-R1 abs_rapido_calibration_0p4 SHA256 f3c6513d491cad5e3fc611549c640439ac58189ddea5c79fe01725e3a846b114", "spool_lot": "NOT_TRACKED_PROTOTYPE"}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: Actual M3 x 10 mm button-head puck screw and measuring tools.
- Open `print_plates_3mf/00F_ABS_calibration_profile_clearance_test.PRINT_SETTINGS.md` and follow every exact value in it.
- Import `slicer_profiles/QIDI_PLUS4/abs_rapido_calibration_0p4.process.json` and select `QIDI ABS Rapido @Qidi X-Plus 4 0.4 nozzle` as the separate filament preset.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `abs_rapido_calibration_0p4`: 4 walls, 6 top / 6 bottom layers, 40% gyroid infill.
- Supports: off. Bed adhesion: 5 mm outer brim with 0.05 mm object gap on clean textured PEI.
- Dimensional controls: No ironing over crosshairs or divots; seam away from keyed receiver faces; zero XY compensation pending Job 00F.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- Use the exact 0.16 mm calibration profile. Measure the actual M3 screw shank and head, record the smallest freely passing 3.2/3.4/3.6 mm M3 option, and select the smallest H5.8/H6.2/H6.6 recess in which the button head seats below the surrounding face without forcing. Retain and label this coupon separately from 00C/00E.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, modeled identity and revision before cleanup.
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


# Job 01 - ABS left master keyboard station with integrated datums, locator sockets, clamp track, and seam posts

| Control field | Released value |
|---|---|
| Design revision | `RC03-INT-R1` |
| Lifecycle state | **UNRELEASED** |
| Route / stage | `required` / `first_article` |
| Kit | `KIT-KB` |
| Plate | `01_ABS_keyboard_station_left.3mf` |
| Plate SHA-256 | `dbcb685037402a8ce90e39c216f00888c9abeb341829ff529248ac6f485e65f3` |
| Profile | `abs_rapido_tray_structural_0p4` / `4cc77d229e3f397c7f8d7c1a793ace5ba9490cafe2ef9d31f16e7ffa4c28123f` |
| Exact settings sheet | `print_plates_3mf/01_ABS_keyboard_station_left.PRINT_SETTINGS.md` / `54b2f8cc73105131175af762ec6b2f49b8f3c8dc25966d2a06a024d15b8c4688` |
| QIDI process import | `slicer_profiles/QIDI_PLUS4/abs_rapido_tray_structural_0p4.process.json` / `c89e92d6af33cb676d7200e34937ec05c7cec9b55f2d0700b07b89a57cbd81c6` |
| Filament preset | `qidi_abs_rapido_xplus4_0p4` / `ce549e11c71d71294ae086694987ac99842a14ba8fc26e24a879f7dd31b65bd4` |
| Preset completeness | **EXACT_REPRODUCIBLE** |
| Unresolved filament fields | None |
| Printer | QIDI Plus4; 305 x 305 x 280 mm nominal; 5 mm protected edge margin |
| Material / nozzle / layer | QIDI ABS Rapido / 0.4 mm / 0.20 mm |
| Plate envelope | 184.5 x 192.0 x 7.0 mm; centered |
| Native slice record | QIDI Studio version, sliced mass and time: ____________________ |

## Objects and orientation

| STL | Qty | Locked orientation | Source SHA-256 |
|---|---:|---|---|
| `keyboard_station_left.stl` | 1 | Flat, exported base on bed; RC03-L/master and locator labels readable on top | `a19b4288b9d6c3fae66f3baa3aa7726fc4acaa440bdb3f16ad3a7ea7791e9a1f` |

## Required gates

| Gate | Status | Recorded values |
|---|---|---|
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "provisional_protected_envelope_mm": [295, 295, 275]}` |
| `plus4_protected_envelope_verified` | **PASS** | `{"build_surface": "QIDI dual-sided textured PEI plate", "carriage_clearance_result": "PASS - protected envelope is inside official nominal volume", "enclosure_clearance_result": "PASS - operator confirmed completed printer qualification", "firmware_version": "Plus4_v1.7.1 official baseline; operator confirmed fully updated", "full_travel_test_result": "PASS - operator confirmed completed printer qualification", "printer_serial": "NOT_TRACKED_PROTOTYPE", "purge_and_exclusion_zone_result": "PASS - operator confirmed completed printer qualification", "verified_protected_envelope_mm": [295, 295, 275]}` |
| `nozzle_0p4_confirmed` | **PASS** | `{"installed_nozzle_mm": 0.4, "verification_method": "Official QIDI Plus4 standard specification and official printer.cfg; operator confirmed printer configuration"}` |
| `abs_rapido_tray_profile_calibrated` | **PASS** | `{"brand": "QIDI", "calibration_result": "PASS - operator confirmed the installed QIDI ABS Rapido preset and current native Job 00A slice; matching coupons provide dimensional release", "chamber_condition": "QIDI Plus4 enclosure sealed; 55 C chamber target from the installed QIDI ABS Rapido preset", "drying_record": "Operator confirmed print-ready; detailed drying record waived for prototype coupons", "filament_name": "ABS Rapido", "profile_revision": "RC03-INT-R1 abs_rapido_tray_structural_0p4 SHA256 4cc77d229e3f397c7f8d7c1a793ace5ba9490cafe2ef9d31f16e7ffa4c28123f", "spool_lot": "NOT_TRACKED_PROTOTYPE"}` |
| `keyboard_dimensions_measured` | **NOT_TESTED** | `{"cable_keepout_mm": null, "depth_mm": null, "device_model": null, "height_mm": null, "width_mm": null}` |
| `keyboard_corner_coupon_pass` | **PASS** | `{"fit_result": "PASS - corner seated within both datum walls without force; keyboard remained level with no observed binding or interference (operator verified)", "selected_compensation_mm": 0.0}` |
| `keyboard_station_registration_coupon_pass` | **PASS** | `{"actual_pin_diameter_measurements_mm": ["6.0 nominal \u2014 not caliper-measured under prototype waiver"], "crack_or_whitening_result": "PASS \u2014 none visible in retained round-hole photo and none reported for slot fit", "insertion_removal_cycles": "WAIVED \u2014 round and slot were each functionally checked by hand; 20 repeated cycles not performed", "inversion_retention_result": "WAIVED \u2014 inversion retention test not performed for this prototype", "lateral_play_mm": "NOT MEASURED \u2014 operator accepted functional fit under prototype waiver", "selected_radial_slot_length_mm": 10.0, "selected_radial_slot_width_mm": 6.2, "selected_round_socket_mm": 6.2}` |
| `tray_clearance_holes_coupon_pass` | **PASS** | `{"board_screw_major_diameter_mm": 4.0, "m4_washer_od_mm": 9.2, "smallest_free_hole_mm": 4.4, "washer_fit_result": "PASS - actual M4 production washer fits all candidates; operator selected the photographed/current production OD9.2 recess for service margin and easy assembly"}` |
| `geometry_matches_measurements` | **PASS** | `{"affected_parts_reviewed": true, "design_revision": "RC03-INT-R1", "effective_parameters_file": "config/parameters.json", "measurement_record_revision": "2026-09-06_JOB03C1_REWORK", "regeneration_completed": true}` |
| `qidi_studio_roundtrip_confirmed` | **NOT_TESTED** | `{"critical_layer_preview_pass_by_job": {}, "evidence_reference_by_job": {}, "geometry_scale_percent_by_job": {}, "native_project_sha256_by_job": {}, "object_count_by_job": {}, "qidi_studio_version": null, "saved_profile_revision_by_job": {}, "validated_job_ids": []}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: Flatness surface, retained job 00A seam ladder, 6 mm production pins, three temporary/production M4 station screws and washers, calipers.
- Open `print_plates_3mf/01_ABS_keyboard_station_left.PRINT_SETTINGS.md` and follow every exact value in it.
- Import `slicer_profiles/QIDI_PLUS4/abs_rapido_tray_structural_0p4.process.json` and select `QIDI ABS Rapido @Qidi X-Plus 4 0.4 nozzle` as the separate filament preset.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `abs_rapido_tray_structural_0p4`: 5 walls, 6 top / 6 bottom layers, 35% gyroid infill.
- Supports: off. Bed adhesion: 8 mm outer brim with 0.05 mm object gap; clean textured PEI; one production station per plate.
- Dimensional controls: Keep the slicer seam away from locator sockets, relieved hold-down holes, seam datums, clamp guides, and keyboard contact datums; zero XY compensation pending Job 00A.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- Cool fully; inspect master round/slot sockets, the continuous board-contact underside at all three retention zones, seam posts and clamp track. Measure the printed seam posts; independently select the smallest tool-free round-socket diameter and radial-slot width on the retained job 00A ladder; reject cracks, whitening, rocking, or lifted corners.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, modeled identity and revision before cleanup.
- Quarantine any warped, cracked, delaminated, under-extruded, bridged-shut or untraceable part; do not silently rework a critical fit.
- Intended gate(s) after objective acceptance: `keyboard_left_first_article_pass`, `keyboard_seam_coupon_pass`.

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


# Job 02 - ABS right slave keyboard station located from the accepted left-station seam

| Control field | Released value |
|---|---|
| Design revision | `RC03-INT-R1` |
| Lifecycle state | **UNRELEASED** |
| Route / stage | `required` / `production` |
| Kit | `KIT-KB` |
| Plate | `02_ABS_keyboard_station_right.3mf` |
| Plate SHA-256 | `bc8e2fffd5f004678e47ac33c5fca41b3366cab17931cbcd5565f9bf9c2969d0` |
| Profile | `abs_rapido_tray_structural_0p4` / `4cc77d229e3f397c7f8d7c1a793ace5ba9490cafe2ef9d31f16e7ffa4c28123f` |
| Exact settings sheet | `print_plates_3mf/02_ABS_keyboard_station_right.PRINT_SETTINGS.md` / `e384ebb2785694ebef13fdbcedf547ea7c1730028a0b115350ac93b1d78c7b3e` |
| QIDI process import | `slicer_profiles/QIDI_PLUS4/abs_rapido_tray_structural_0p4.process.json` / `c89e92d6af33cb676d7200e34937ec05c7cec9b55f2d0700b07b89a57cbd81c6` |
| Filament preset | `qidi_abs_rapido_xplus4_0p4` / `ce549e11c71d71294ae086694987ac99842a14ba8fc26e24a879f7dd31b65bd4` |
| Preset completeness | **EXACT_REPRODUCIBLE** |
| Unresolved filament fields | None |
| Printer | QIDI Plus4; 305 x 305 x 280 mm nominal; 5 mm protected edge margin |
| Material / nozzle / layer | QIDI ABS Rapido / 0.4 mm / 0.20 mm |
| Plate envelope | 162.5 x 192.0 x 7.0 mm; centered |
| Native slice record | QIDI Studio version, sliced mass and time: ____________________ |

## Objects and orientation

| STL | Qty | Locked orientation | Source SHA-256 |
|---|---:|---|---|
| `keyboard_station_right.stl` | 1 | Flat, exported base on bed; RC03-R/slave and seam-reference labels readable on top | `bc9cc0d252da8d1702c56bbd0afaf6ed79e5dd9891d121dd54372e4692675cf0` |

## Required gates

| Gate | Status | Recorded values |
|---|---|---|
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "provisional_protected_envelope_mm": [295, 295, 275]}` |
| `plus4_protected_envelope_verified` | **PASS** | `{"build_surface": "QIDI dual-sided textured PEI plate", "carriage_clearance_result": "PASS - protected envelope is inside official nominal volume", "enclosure_clearance_result": "PASS - operator confirmed completed printer qualification", "firmware_version": "Plus4_v1.7.1 official baseline; operator confirmed fully updated", "full_travel_test_result": "PASS - operator confirmed completed printer qualification", "printer_serial": "NOT_TRACKED_PROTOTYPE", "purge_and_exclusion_zone_result": "PASS - operator confirmed completed printer qualification", "verified_protected_envelope_mm": [295, 295, 275]}` |
| `nozzle_0p4_confirmed` | **PASS** | `{"installed_nozzle_mm": 0.4, "verification_method": "Official QIDI Plus4 standard specification and official printer.cfg; operator confirmed printer configuration"}` |
| `abs_rapido_tray_profile_calibrated` | **PASS** | `{"brand": "QIDI", "calibration_result": "PASS - operator confirmed the installed QIDI ABS Rapido preset and current native Job 00A slice; matching coupons provide dimensional release", "chamber_condition": "QIDI Plus4 enclosure sealed; 55 C chamber target from the installed QIDI ABS Rapido preset", "drying_record": "Operator confirmed print-ready; detailed drying record waived for prototype coupons", "filament_name": "ABS Rapido", "profile_revision": "RC03-INT-R1 abs_rapido_tray_structural_0p4 SHA256 4cc77d229e3f397c7f8d7c1a793ace5ba9490cafe2ef9d31f16e7ffa4c28123f", "spool_lot": "NOT_TRACKED_PROTOTYPE"}` |
| `keyboard_dimensions_measured` | **NOT_TESTED** | `{"cable_keepout_mm": null, "depth_mm": null, "device_model": null, "height_mm": null, "width_mm": null}` |
| `keyboard_corner_coupon_pass` | **PASS** | `{"fit_result": "PASS - corner seated within both datum walls without force; keyboard remained level with no observed binding or interference (operator verified)", "selected_compensation_mm": 0.0}` |
| `keyboard_seam_coupon_pass` | **NOT_TESTED** | `{"fit_result": null, "printed_post_diameter_mm": null, "rocking_or_yaw_result": null, "selected_radial_slot_width_mm": null, "selected_round_socket_mm": null, "tool_free_release_result": null}` |
| `keyboard_station_registration_coupon_pass` | **PASS** | `{"actual_pin_diameter_measurements_mm": ["6.0 nominal \u2014 not caliper-measured under prototype waiver"], "crack_or_whitening_result": "PASS \u2014 none visible in retained round-hole photo and none reported for slot fit", "insertion_removal_cycles": "WAIVED \u2014 round and slot were each functionally checked by hand; 20 repeated cycles not performed", "inversion_retention_result": "WAIVED \u2014 inversion retention test not performed for this prototype", "lateral_play_mm": "NOT MEASURED \u2014 operator accepted functional fit under prototype waiver", "selected_radial_slot_length_mm": 10.0, "selected_radial_slot_width_mm": 6.2, "selected_round_socket_mm": 6.2}` |
| `tray_clearance_holes_coupon_pass` | **PASS** | `{"board_screw_major_diameter_mm": 4.0, "m4_washer_od_mm": 9.2, "smallest_free_hole_mm": 4.4, "washer_fit_result": "PASS - actual M4 production washer fits all candidates; operator selected the photographed/current production OD9.2 recess for service margin and easy assembly"}` |
| `geometry_matches_measurements` | **PASS** | `{"affected_parts_reviewed": true, "design_revision": "RC03-INT-R1", "effective_parameters_file": "config/parameters.json", "measurement_record_revision": "2026-09-06_JOB03C1_REWORK", "regeneration_completed": true}` |
| `keyboard_left_first_article_pass` | **NOT_TESTED** | `{"datum_surface_result": null, "flatness_mm": null, "job_id": null, "seam_key_result": null, "slot_fit_result": null, "washer_track_result": null}` |
| `qidi_studio_roundtrip_confirmed` | **NOT_TESTED** | `{"critical_layer_preview_pass_by_job": {}, "evidence_reference_by_job": {}, "geometry_scale_percent_by_job": {}, "native_project_sha256_by_job": {}, "object_count_by_job": {}, "qidi_studio_version": null, "saved_profile_revision_by_job": {}, "validated_job_ids": []}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: Accepted left station, keyboard, three temporary/production M4 station screws and washers, seam keys.
- Open `print_plates_3mf/02_ABS_keyboard_station_right.PRINT_SETTINGS.md` and follow every exact value in it.
- Import `slicer_profiles/QIDI_PLUS4/abs_rapido_tray_structural_0p4.process.json` and select `QIDI ABS Rapido @Qidi X-Plus 4 0.4 nozzle` as the separate filament preset.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `abs_rapido_tray_structural_0p4`: 5 walls, 6 top / 6 bottom layers, 35% gyroid infill.
- Supports: off. Bed adhesion: 8 mm outer brim with 0.05 mm object gap; clean textured PEI; one production station per plate.
- Dimensional controls: Keep the slicer seam away from locator sockets, relieved hold-down holes, seam datums, clamp guides, and keyboard contact datums; zero XY compensation pending Job 00A.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- Repeat first-article checks; mate the slave to the accepted master without an independent pin pair; record seam gap, flushness, support plane, continuous base contact and rocking. Complete ten station removal/reinstall cycles after board installation.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, modeled identity and revision before cleanup.
- Quarantine any warped, cracked, delaminated, under-extruded, bridged-shut or untraceable part; do not silently rework a critical fit.
- Intended gate(s) after objective acceptance: `keyboard_station_pair_postprint_pass`, `station_remove_reinstall_repeatability_pass`, `keyboard_fixture_assembly_pass`.

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


# Job 03A - Integrated ABS phone and TCP service station with fixed datums, keyed receiver, and replaceable-rail interface

| Control field | Released value |
|---|---|
| Design revision | `RC03-INT-R1` |
| Lifecycle state | **UNRELEASED** |
| Route / stage | `required` / `first_article` |
| Kit | `KIT-PHONE` |
| Plate | `03A_ABS_phone_TCP_station.3mf` |
| Plate SHA-256 | `63cf85413ed08193b08445859bfcc8116c2e47064f2a086fdbfdb8bd7339e565` |
| Profile | `abs_rapido_cradle_0p4` / `0dca510bbadec73f611b731a8fd24f22310b3ba113759f58f0ed7f1cdc33c545` |
| Exact settings sheet | `print_plates_3mf/03A_ABS_phone_TCP_station.PRINT_SETTINGS.md` / `c3fd921347d91842d1f16728e8e88a45d25a776aa3aedd6d8810c9db9773c7b9` |
| QIDI process import | `slicer_profiles/QIDI_PLUS4/abs_rapido_cradle_0p4.process.json` / `9276ce2983256d815925224e7d8fc45032a531678dc336713fc88fa96137e259` |
| Filament preset | `qidi_abs_rapido_xplus4_0p4` / `ce549e11c71d71294ae086694987ac99842a14ba8fc26e24a879f7dd31b65bd4` |
| Preset completeness | **EXACT_REPRODUCIBLE** |
| Unresolved filament fields | None |
| Printer | QIDI Plus4; 305 x 305 x 280 mm nominal; 5 mm protected edge margin |
| Material / nozzle / layer | QIDI ABS Rapido / 0.4 mm / 0.20 mm |
| Plate envelope | 186.3 x 172.8 x 10.5 mm; centered |
| Native slice record | QIDI Studio version, sliced mass and time: ____________________ |

## Objects and orientation

| STL | Qty | Locked orientation | Source SHA-256 |
|---|---:|---|---|
| `phone_tcp_station.stl` | 1 | Flat base on bed; RC03 PHONE+TCP and TCP R3 readable; USB toward plate front and TOP toward plate rear | `63e02e28f9bb818007564eab7e82e2b9ce8417f30bdf3cbec3c3a86ec08ac32e` |

## Required gates

| Gate | Status | Recorded values |
|---|---|---|
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "provisional_protected_envelope_mm": [295, 295, 275]}` |
| `plus4_protected_envelope_verified` | **PASS** | `{"build_surface": "QIDI dual-sided textured PEI plate", "carriage_clearance_result": "PASS - protected envelope is inside official nominal volume", "enclosure_clearance_result": "PASS - operator confirmed completed printer qualification", "firmware_version": "Plus4_v1.7.1 official baseline; operator confirmed fully updated", "full_travel_test_result": "PASS - operator confirmed completed printer qualification", "printer_serial": "NOT_TRACKED_PROTOTYPE", "purge_and_exclusion_zone_result": "PASS - operator confirmed completed printer qualification", "verified_protected_envelope_mm": [295, 295, 275]}` |
| `nozzle_0p4_confirmed` | **PASS** | `{"installed_nozzle_mm": 0.4, "verification_method": "Official QIDI Plus4 standard specification and official printer.cfg; operator confirmed printer configuration"}` |
| `abs_rapido_cradle_profile_calibrated` | **PASS** | `{"brand": "QIDI", "calibration_result": "PASS - operator confirmed the installed QIDI ABS Rapido preset and current native Job 00A slice; matching coupons provide dimensional release", "chamber_condition": "QIDI Plus4 enclosure sealed; 55 C chamber target from the installed QIDI ABS Rapido preset", "drying_record": "Operator confirmed print-ready; detailed drying record waived for prototype coupons", "filament_name": "ABS Rapido", "profile_revision": "RC03-INT-R1 abs_rapido_cradle_0p4 SHA256 0dca510bbadec73f611b731a8fd24f22310b3ba113759f58f0ed7f1cdc33c545", "spool_lot": "NOT_TRACKED_PROTOTYPE"}` |
| `phone_dimensions_measured` | **NOT_TESTED** | `{"camera_bump_envelope_mm": null, "case_installed": null, "device_model": null, "length_mm": null, "thickness_mm": null, "width_mm": null}` |
| `phone_side_features_measured` | **NOT_TESTED** | `{"approved_clearance_limit_id": null, "clearance_measurement_uncertainty_mm": null, "minimum_keepout_margin_mm": null, "right_side_keepouts_from_bottom_mm": null, "selected_clamp_centers_from_bottom_mm": null}` |
| `phone_cable_measured` | **NOT_TESTED** | `{"connector_thickness_mm": null, "connector_width_mm": null, "minimum_bend_radius_mm": null, "selected_tie_width_mm": null, "straight_projection_mm": null}` |
| `phone_width_coupon_pass` | **PASS** | `{"fit_result": "PASS_BARE_PHONE_SEATS_BY_HAND_COUPON_IS_WIDTH_AND_RAIL_HEIGHT_ONLY", "lateral_clearance_mm": 1.5, "rail_height_result": "PASS_RAILS_VISIBLY_BELOW_SCREEN_FACE"}` |
| `phone_station_registration_coupon_pass` | **PASS** | `{"actual_pin_diameter_measurements_mm": ["6.0 nominal - not caliper-measured under prototype waiver"], "crack_or_whitening_result": "PASS_NONE_REPORTED", "insertion_removal_cycles": "WAIVED_FUNCTIONAL_HAND_FIT_CONFIRMED", "inversion_retention_result": "WAIVED_FOR_PROTOTYPE", "lateral_play_mm": "NOT_NUMERICALLY_MEASURED_FUNCTIONAL_FIT_ACCEPTED", "selected_radial_slot_length_mm": 10.0, "selected_radial_slot_width_mm": 6.2, "selected_round_socket_mm": 6.2}` |
| `phone_m4_captive_nut_coupon_pass` | **FAIL** | `{"actual_nut_across_flats_mm": "NOT_CALIPER_MEASURED_STANDARD_M4_NUT", "actual_nut_thickness_mm": "NOT_CALIPER_MEASURED_STANDARD_M4_NUT", "horizontal_screw_axis_result": "FAIL_SCREW_DID_NOT_ENGAGE_RELIABLY", "installation_result": "FAIL_NUT_DROPS_IN_WITH_EXCESSIVE_CLEARANCE", "selected_channel_across_flats_mm": 7.4, "selected_channel_depth_mm": 3.55, "spin_result_after_20_cycles": "FAIL_TOO_LOOSE_TO_COMPLETE_CYCLE_TEST"}` |
| `phone_station_m3_insert_coupon_pass` | **NOT_TESTED** | `{"insert_length_mm": null, "insert_od_mm": null, "installed_depth_mm": null, "retention_result": null, "selected_pocket_mm": null}` |
| `cable_tie_saddle_coupon_pass` | **FAIL** | `{"cable_clearance_result": "NOT_TESTABLE_BECAUSE_TIE_DID_NOT_FEED", "feed_result": "FAIL_SELECTED_WIDER_TIE_DID_NOT_PASS_LEGACY_SADDLE", "job_id": "00B_AS_BUILT_LEGACY_SCREENING", "saddle_crack_result": "PASS_NO_CRACK_VISIBLE_IN_PHOTOS", "selected_slot_width_mm": null, "selected_tie_width_mm": 4.8, "selected_tunnel_height_mm": 1.8, "tie_specification_basis": "OPERATOR_SELECTED_WIDER_NOMINAL_4P8_MM_TIE_CLASS_NOT_CALIPER_MEASURED"}` |
| `cradle_m4_washer_coupon_pass` | **PASS** | `{"actual_washer_od_mm": "NOT_CALIPER_MEASURED_PROTOTYPE_WAIVER", "fit_result": "PASS_MIDDLE_OD9.2_RECESS_LIES_FLAT_WITHOUT_FORCE", "m4_washer_od_mm": 9.2}` |
| `geometry_matches_measurements` | **PASS** | `{"affected_parts_reviewed": true, "design_revision": "RC03-INT-R1", "effective_parameters_file": "config/parameters.json", "measurement_record_revision": "2026-09-06_JOB03C1_REWORK", "regeneration_completed": true}` |
| `qidi_studio_roundtrip_confirmed` | **NOT_TESTED** | `{"critical_layer_preview_pass_by_job": {}, "evidence_reference_by_job": {}, "geometry_scale_percent_by_job": {}, "native_project_sha256_by_job": {}, "object_count_by_job": {}, "qidi_studio_version": null, "saved_profile_revision_by_job": {}, "validated_job_ids": []}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: Phone/case, cable, two 6 mm pins, three M4 station screws/washers, M3 inserts, accepted rail and TPU tips.
- Open `print_plates_3mf/03A_ABS_phone_TCP_station.PRINT_SETTINGS.md` and follow every exact value in it.
- Import `slicer_profiles/QIDI_PLUS4/abs_rapido_cradle_0p4.process.json` and select `QIDI ABS Rapido @Qidi X-Plus 4 0.4 nozzle` as the separate filament preset.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `abs_rapido_cradle_0p4`: 5 walls, 5 top / 5 bottom layers, 30% gyroid infill.
- Supports: off; stop and obtain engineering approval if the locked layer preview shows an unprintable tower. Bed adhesion: 8 mm outer brim with 0.05 mm object gap on clean textured PEI.
- Dimensional controls: Use the same-profile ABS locator, captive-M4, vertical-M3-insert, cable-saddle, and washer coupons; do not rework a released socket ad hoc.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- With the station off the wood board, inspect continuous base contact at all three retention zones, locator sockets, keyed TCP receiver, fixed phone datums, replaceable-rail interface and all keepouts; install the TCP inserts square. For final mounting, seat the accepted rail before the two shared rail/station screws and verify its cable saddle with the actual cable. Complete ten station and phone cycles without button or cable contact.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, modeled identity and revision before cleanup.
- Quarantine any warped, cracked, delaminated, under-extruded, bridged-shut or untraceable part; do not silently rework a critical fit.
- Intended gate(s) after objective acceptance: `phone_tcp_station_postprint_pass`, `station_remove_reinstall_repeatability_pass`, `phone_fixture_assembly_pass`.

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


# Job 03B - Two replaceable ABS guided keyboard rear clamp sliders

| Control field | Released value |
|---|---|
| Design revision | `RC03-INT-R1` |
| Lifecycle state | **UNRELEASED** |
| Route / stage | `required` / `production` |
| Kit | `KIT-KB` |
| Plate | `03B_ABS_keyboard_clamps.3mf` |
| Plate SHA-256 | `0f6e0900c6aec772e790d796ae389aa4506b5080550be71430cd05093acafbed` |
| Profile | `abs_rapido_general_0p4` / `4d9038f98da0892dca1031e59696babbbf913c0947f9e4cbac288c6182d1bede` |
| Exact settings sheet | `print_plates_3mf/03B_ABS_keyboard_clamps.PRINT_SETTINGS.md` / `005ea3f467f64abc7f1e1af070e3436d1d90822e25b22b82c776b7baa24f7c3c` |
| QIDI process import | `slicer_profiles/QIDI_PLUS4/abs_rapido_general_0p4.process.json` / `756895e547ed186ab4b0d532d6d66fc3e2ad31376bc342a0150cbd4667a5d239` |
| Filament preset | `qidi_abs_rapido_xplus4_0p4` / `ce549e11c71d71294ae086694987ac99842a14ba8fc26e24a879f7dd31b65bd4` |
| Preset completeness | **EXACT_REPRODUCIBLE** |
| Unresolved filament fields | None |
| Printer | QIDI Plus4; 305 x 305 x 280 mm nominal; 5 mm protected edge margin |
| Material / nozzle / layer | QIDI ABS Rapido / 0.4 mm / 0.20 mm |
| Plate envelope | 112.0 x 32.0 x 17.0 mm; centered |
| Native slice record | QIDI Studio version, sliced mass and time: ____________________ |

## Objects and orientation

| STL | Qty | Locked orientation | Source SHA-256 |
|---|---:|---|---|
| `keyboard_rear_clamp.stl` | 2 | Flat base on bed; padded face upright | `78c591895ae8392a5af9832f56cb7f15cb6a401c490153a1914b71ff5bcba373` |

## Required gates

| Gate | Status | Recorded values |
|---|---|---|
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "provisional_protected_envelope_mm": [295, 295, 275]}` |
| `plus4_protected_envelope_verified` | **PASS** | `{"build_surface": "QIDI dual-sided textured PEI plate", "carriage_clearance_result": "PASS - protected envelope is inside official nominal volume", "enclosure_clearance_result": "PASS - operator confirmed completed printer qualification", "firmware_version": "Plus4_v1.7.1 official baseline; operator confirmed fully updated", "full_travel_test_result": "PASS - operator confirmed completed printer qualification", "printer_serial": "NOT_TRACKED_PROTOTYPE", "purge_and_exclusion_zone_result": "PASS - operator confirmed completed printer qualification", "verified_protected_envelope_mm": [295, 295, 275]}` |
| `nozzle_0p4_confirmed` | **PASS** | `{"installed_nozzle_mm": 0.4, "verification_method": "Official QIDI Plus4 standard specification and official printer.cfg; operator confirmed printer configuration"}` |
| `abs_rapido_general_profile_calibrated` | **PASS** | `{"brand": "QIDI", "calibration_result": "PASS - operator confirmed the installed QIDI ABS Rapido preset and current native Job 00A slice; matching coupons provide dimensional release", "chamber_condition": "QIDI Plus4 enclosure sealed; 55 C chamber target from the installed QIDI ABS Rapido preset", "drying_record": "Operator confirmed print-ready; detailed drying record waived for prototype coupons", "filament_name": "ABS Rapido", "profile_revision": "RC03-INT-R1 abs_rapido_general_0p4 SHA256 4d9038f98da0892dca1031e59696babbbf913c0947f9e4cbac288c6182d1bede", "spool_lot": "NOT_TRACKED_PROTOTYPE"}` |
| `keyboard_dimensions_measured` | **NOT_TESTED** | `{"cable_keepout_mm": null, "depth_mm": null, "device_model": null, "height_mm": null, "width_mm": null}` |
| `keyboard_corner_coupon_pass` | **PASS** | `{"fit_result": "PASS - corner seated within both datum walls without force; keyboard remained level with no observed binding or interference (operator verified)", "selected_compensation_mm": 0.0}` |
| `general_clearance_holes_coupon_pass` | **NOT_TESTED** | `{"m3_selected_mm": null, "m4_or_board_screw_selected_mm": null, "m5_selected_mm": null}` |
| `setup_hardware_coupon_pass` | **NOT_TESTED** | `{"camera_hex_ac_mm": null, "fit_result": null, "m3_head_recess_d_mm": null, "m4_washer_od_mm": null, "m5_washer_od_mm": null}` |
| `geometry_matches_measurements` | **PASS** | `{"affected_parts_reviewed": true, "design_revision": "RC03-INT-R1", "effective_parameters_file": "config/parameters.json", "measurement_record_revision": "2026-09-06_JOB03C1_REWORK", "regeneration_completed": true}` |
| `qidi_studio_roundtrip_confirmed` | **NOT_TESTED** | `{"critical_layer_preview_pass_by_job": {}, "evidence_reference_by_job": {}, "geometry_scale_percent_by_job": {}, "native_project_sha256_by_job": {}, "object_count_by_job": {}, "qidi_studio_version": null, "saved_profile_revision_by_job": {}, "validated_job_ids": []}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: Keyboard, two face pads, two M4 low-profile thumb screws.
- Open `print_plates_3mf/03B_ABS_keyboard_clamps.PRINT_SETTINGS.md` and follow every exact value in it.
- Import `slicer_profiles/QIDI_PLUS4/abs_rapido_general_0p4.process.json` and select `QIDI ABS Rapido @Qidi X-Plus 4 0.4 nozzle` as the separate filament preset.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `abs_rapido_general_0p4`: 4 walls, 5 top / 5 bottom layers, 25% gyroid infill.
- Supports: off. Bed adhesion: 5 mm outer brim with 0.05 mm object gap on clean textured PEI.
- Dimensional controls: Zero XY contour and hole compensation until the matching ABS coupon provides measured evidence; elephant-foot compensation 0.15 mm.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- Verify both guided sliders match, bases are flat, runners intact, scales readable, and slots open. Pad faces; tighten only to contact and run keyboard repeatability testing.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, modeled identity and revision before cleanup.
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


# Job 03C1 - Production-equivalent ABS phone keeper and clamp-tower rail that qualifies the revised captive-nut seats and adopted wide-tie saddle before Job 03A

| Control field | Released value |
|---|---|
| Design revision | `RC03-INT-R1` |
| Lifecycle state | **UNRELEASED** |
| Route / stage | `required` / `first_article` |
| Kit | `KIT-PHONE` |
| Plate | `03C1_ABS_phone_clamp_rail.3mf` |
| Plate SHA-256 | `e992ea3f29097bd346095a5c5ac08c33c9e2d35d7e9c27bce6041e43e3a9ef39` |
| Profile | `abs_rapido_cradle_0p4` / `0dca510bbadec73f611b731a8fd24f22310b3ba113759f58f0ed7f1cdc33c545` |
| Exact settings sheet | `print_plates_3mf/03C1_ABS_phone_clamp_rail.PRINT_SETTINGS.md` / `0a0a5ea8323faf956099084619fece6f7c8e879f6d7ae8baa2aff406effec156` |
| QIDI process import | `slicer_profiles/QIDI_PLUS4/abs_rapido_cradle_0p4.process.json` / `9276ce2983256d815925224e7d8fc45032a531678dc336713fc88fa96137e259` |
| Filament preset | `qidi_abs_rapido_xplus4_0p4` / `ce549e11c71d71294ae086694987ac99842a14ba8fc26e24a879f7dd31b65bd4` |
| Preset completeness | **EXACT_REPRODUCIBLE** |
| Unresolved filament fields | None |
| Printer | QIDI Plus4; 305 x 305 x 280 mm nominal; 5 mm protected edge margin |
| Material / nozzle / layer | QIDI ABS Rapido / 0.4 mm / 0.20 mm |
| Plate envelope | 19.2 x 172.8 x 16.0 mm; centered |
| Native slice record | QIDI Studio version, sliced mass and time: ____________________ |

## Objects and orientation

| STL | Qty | Locked orientation | Source SHA-256 |
|---|---:|---|---|
| `phone_clamp_rail.stl` | 1 | Flat station-facing ledge on bed; clamp towers upward | `f766a24143f11769a0bcef7236b09938f4c02434b3b5d8e6d77b21b37f49dcff` |

## Required gates

| Gate | Status | Recorded values |
|---|---|---|
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "provisional_protected_envelope_mm": [295, 295, 275]}` |
| `plus4_protected_envelope_verified` | **PASS** | `{"build_surface": "QIDI dual-sided textured PEI plate", "carriage_clearance_result": "PASS - protected envelope is inside official nominal volume", "enclosure_clearance_result": "PASS - operator confirmed completed printer qualification", "firmware_version": "Plus4_v1.7.1 official baseline; operator confirmed fully updated", "full_travel_test_result": "PASS - operator confirmed completed printer qualification", "printer_serial": "NOT_TRACKED_PROTOTYPE", "purge_and_exclusion_zone_result": "PASS - operator confirmed completed printer qualification", "verified_protected_envelope_mm": [295, 295, 275]}` |
| `nozzle_0p4_confirmed` | **PASS** | `{"installed_nozzle_mm": 0.4, "verification_method": "Official QIDI Plus4 standard specification and official printer.cfg; operator confirmed printer configuration"}` |
| `abs_rapido_cradle_profile_calibrated` | **PASS** | `{"brand": "QIDI", "calibration_result": "PASS - operator confirmed the installed QIDI ABS Rapido preset and current native Job 00A slice; matching coupons provide dimensional release", "chamber_condition": "QIDI Plus4 enclosure sealed; 55 C chamber target from the installed QIDI ABS Rapido preset", "drying_record": "Operator confirmed print-ready; detailed drying record waived for prototype coupons", "filament_name": "ABS Rapido", "profile_revision": "RC03-INT-R1 abs_rapido_cradle_0p4 SHA256 0dca510bbadec73f611b731a8fd24f22310b3ba113759f58f0ed7f1cdc33c545", "spool_lot": "NOT_TRACKED_PROTOTYPE"}` |
| `phone_width_coupon_pass` | **PASS** | `{"fit_result": "PASS_BARE_PHONE_SEATS_BY_HAND_COUPON_IS_WIDTH_AND_RAIL_HEIGHT_ONLY", "lateral_clearance_mm": 1.5, "rail_height_result": "PASS_RAILS_VISIBLY_BELOW_SCREEN_FACE"}` |
| `cradle_m4_washer_coupon_pass` | **PASS** | `{"actual_washer_od_mm": "NOT_CALIPER_MEASURED_PROTOTYPE_WAIVER", "fit_result": "PASS_MIDDLE_OD9.2_RECESS_LIES_FLAT_WITHOUT_FORCE", "m4_washer_od_mm": 9.2}` |
| `geometry_matches_measurements` | **PASS** | `{"affected_parts_reviewed": true, "design_revision": "RC03-INT-R1", "effective_parameters_file": "config/parameters.json", "measurement_record_revision": "2026-09-06_JOB03C1_REWORK", "regeneration_completed": true}` |
| `qidi_studio_roundtrip_confirmed` | **NOT_TESTED** | `{"critical_layer_preview_pass_by_job": {}, "evidence_reference_by_job": {}, "geometry_scale_percent_by_job": {}, "native_project_sha256_by_job": {}, "object_count_by_job": {}, "qidi_studio_version": null, "saved_profile_revision_by_job": {}, "validated_job_ids": []}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: Actual phone, USB cable, nominal 4.8 mm project tie, two standard M4 hex nuts and M4 clamp screws; accepted station and TPU tips only for the later seating stage.
- Open `print_plates_3mf/03C1_ABS_phone_clamp_rail.PRINT_SETTINGS.md` and follow every exact value in it.
- Import `slicer_profiles/QIDI_PLUS4/abs_rapido_cradle_0p4.process.json` and select `QIDI ABS Rapido @Qidi X-Plus 4 0.4 nozzle` as the separate filament preset.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `abs_rapido_cradle_0p4`: 5 walls, 5 top / 5 bottom layers, 30% gyroid infill.
- Supports: off; stop and obtain engineering approval if the locked layer preview shows an unprintable tower. Bed adhesion: 8 mm outer brim with 0.05 mm object gap on clean textured PEI.
- Dimensional controls: Use the same-profile ABS locator, captive-M4, vertical-M3-insert, cable-saddle, and washer coupons; do not rework a released socket ad hoc.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- First bench-qualify both redesigned 7.2 mm lower-half hex seats: each screw must catch at least three full turns and neither nut may spin through 20 cycles. Feed the project tie around the actual cable through the 5.6 x 2.2 mm saddle and confirm no cracking. After Job 03A exists, inspect rail seating, tower ligaments, clamp-axis keepouts and service replacement.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, modeled identity and revision before cleanup.
- Quarantine any warped, cracked, delaminated, under-extruded, bridged-shut or untraceable part; do not silently rework a critical fit.
- Intended gate(s) after objective acceptance: `phone_m4_captive_nut_coupon_pass`, `cable_tie_saddle_coupon_pass`, `phone_clamp_rail_first_article_pass`, `phone_fixture_assembly_pass`.

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


# Job 03C2 - Reusable ABS 55 mm direct-tag application frame and board setup tooling

| Control field | Released value |
|---|---|
| Design revision | `RC03-INT-R1` |
| Lifecycle state | **UNRELEASED** |
| Route / stage | `required` / `production` |
| Kit | `KIT-BOARD-SETUP` |
| Plate | `03C2_ABS_board_setup_tools.3mf` |
| Plate SHA-256 | `6f84a4addac525d32ebe0685c5f11764a15270caf11d29bd6bda20338e1e3b6b` |
| Profile | `abs_rapido_general_0p4` / `4d9038f98da0892dca1031e59696babbbf913c0947f9e4cbac288c6182d1bede` |
| Exact settings sheet | `print_plates_3mf/03C2_ABS_board_setup_tools.PRINT_SETTINGS.md` / `fad0b88672c052346ceff5fd3fcc86caac6565b081497eeb372ffd4bf6b64416` |
| QIDI process import | `slicer_profiles/QIDI_PLUS4/abs_rapido_general_0p4.process.json` / `756895e547ed186ab4b0d532d6d66fc3e2ad31376bc342a0150cbd4667a5d239` |
| Filament preset | `qidi_abs_rapido_xplus4_0p4` / `ce549e11c71d71294ae086694987ac99842a14ba8fc26e24a879f7dd31b65bd4` |
| Preset completeness | **EXACT_REPRODUCIBLE** |
| Unresolved filament fields | None |
| Printer | QIDI Plus4; 305 x 305 x 280 mm nominal; 5 mm protected edge margin |
| Material / nozzle / layer | QIDI ABS Rapido / 0.4 mm / 0.20 mm |
| Plate envelope | 75.0 x 75.0 x 2.4 mm; centered |
| Native slice record | QIDI Studio version, sliced mass and time: ____________________ |

## Objects and orientation

| STL | Qty | Locked orientation | Source SHA-256 |
|---|---:|---|---|
| `tag_application_frame_55mm.stl` | 1 | Flat as exported; 55 mm DIRECT and +Y/REAR marks plus center notches upward | `492f7e3c567a7aa3a4bc255d59425f73dc0c64ab240df8af8f9adf861d53a10f` |

## Required gates

| Gate | Status | Recorded values |
|---|---|---|
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "provisional_protected_envelope_mm": [295, 295, 275]}` |
| `plus4_protected_envelope_verified` | **PASS** | `{"build_surface": "QIDI dual-sided textured PEI plate", "carriage_clearance_result": "PASS - protected envelope is inside official nominal volume", "enclosure_clearance_result": "PASS - operator confirmed completed printer qualification", "firmware_version": "Plus4_v1.7.1 official baseline; operator confirmed fully updated", "full_travel_test_result": "PASS - operator confirmed completed printer qualification", "printer_serial": "NOT_TRACKED_PROTOTYPE", "purge_and_exclusion_zone_result": "PASS - operator confirmed completed printer qualification", "verified_protected_envelope_mm": [295, 295, 275]}` |
| `nozzle_0p4_confirmed` | **PASS** | `{"installed_nozzle_mm": 0.4, "verification_method": "Official QIDI Plus4 standard specification and official printer.cfg; operator confirmed printer configuration"}` |
| `abs_rapido_general_profile_calibrated` | **PASS** | `{"brand": "QIDI", "calibration_result": "PASS - operator confirmed the installed QIDI ABS Rapido preset and current native Job 00A slice; matching coupons provide dimensional release", "chamber_condition": "QIDI Plus4 enclosure sealed; 55 C chamber target from the installed QIDI ABS Rapido preset", "drying_record": "Operator confirmed print-ready; detailed drying record waived for prototype coupons", "filament_name": "ABS Rapido", "profile_revision": "RC03-INT-R1 abs_rapido_general_0p4 SHA256 4d9038f98da0892dca1031e59696babbbf913c0947f9e4cbac288c6182d1bede", "spool_lot": "NOT_TRACKED_PROTOTYPE"}` |
| `tag_stock_measured` | **NOT_TESTED** | `{"adhesive_type": null, "compressed_adhesive_thickness_mm": null, "curl_result": null, "detection_edge_mm": null, "full_surface_adhesive": null, "matte_finish_result": null, "measured_optical_plane_z_mm": null, "stock_thickness_mm": null, "stock_type": null, "tile_height_mm": null, "tile_width_mm": null}` |
| `tag_artwork_scale_pass` | **NOT_TESTED** | `{"detection_edge_mm": null, "orientation_marked": null, "print_scale_percent": null, "tag_id": null, "tile_size_mm": null}` |
| `board_setup_template_scale_pass` | **NOT_TESTED** | `{"all_sheet_registration_marks_result": null, "page_scaling_setting": null, "selected_guide_path": null, "selected_guide_sha256": null, "source_layout_sha256": null, "template_revision": null, "x_scale_bar_mm": null, "y_scale_bar_mm": null}` |
| `geometry_matches_measurements` | **PASS** | `{"affected_parts_reviewed": true, "design_revision": "RC03-INT-R1", "effective_parameters_file": "config/parameters.json", "measurement_record_revision": "2026-09-06_JOB03C1_REWORK", "regeneration_completed": true}` |
| `qidi_studio_roundtrip_confirmed` | **NOT_TESTED** | `{"critical_layer_preview_pass_by_job": {}, "evidence_reference_by_job": {}, "geometry_scale_percent_by_job": {}, "native_project_sha256_by_job": {}, "object_count_by_job": {}, "qidi_studio_version": null, "saved_profile_revision_by_job": {}, "validated_job_ids": []}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: 1:1 board setup template, six direct adhesive tags, steel rule and calipers.
- Open `print_plates_3mf/03C2_ABS_board_setup_tools.PRINT_SETTINGS.md` and follow every exact value in it.
- Import `slicer_profiles/QIDI_PLUS4/abs_rapido_general_0p4.process.json` and select `QIDI ABS Rapido @Qidi X-Plus 4 0.4 nozzle` as the separate filament preset.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `abs_rapido_general_0p4`: 4 walls, 5 top / 5 bottom layers, 25% gyroid infill.
- Supports: off. Bed adhesion: 5 mm outer brim with 0.05 mm object gap on clean textured PEI.
- Dimensional controls: Zero XY contour and hole compensation until the matching ABS coupon provides measured evidence; elephant-foot compensation 0.15 mm.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- Verify the 55 mm application opening, center and +Y witness marks, flatness, and finger access. Prove the 100 mm template scale before installing any direct tag.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, modeled identity and revision before cleanup.
- Quarantine any warped, cracked, delaminated, under-extruded, bridged-shut or untraceable part; do not silently rework a critical fit.
- Intended gate(s) after objective acceptance: `tag_application_tool_postprint_pass`.

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


# Job 03C3 - Fixed-mast fallback camera plate; not an arm-camera adapter and not released while the camera architecture hold is open

| Control field | Released value |
|---|---|
| Design revision | `RC03-INT-R1` |
| Lifecycle state | **UNRELEASED** |
| Route / stage | `camera_mast_optional` / `production` |
| Kit | `KIT-VISION-CAM` |
| Plate | `03C3_PETG_camera_plate.3mf` |
| Plate SHA-256 | `b659444974c21f27d0832b97b0511edd4a879c2049d81ae010cb28d61c8eae42` |
| Profile | `petg_general_0p4` / `00f5efa4c8c65c9857564a255fdec4d4eaa571962c83d77095a470a20942edc6` |
| Exact settings sheet | `print_plates_3mf/03C3_PETG_camera_plate.PRINT_SETTINGS.md` / `736c5f8666a3beae5a87cf685c04831499f5510dacdec9e17ab651da5af8e214` |
| QIDI process import | `slicer_profiles/QIDI_PLUS4/petg_general_0p4.process.json` / `4e3fcda86460e9823234db1eff750e880a8b43bcb916dc2b584038b97376b605` |
| Filament preset | `exact_petg_spool_xplus4_0p4` / `e4af446b19a2425a1f87b49feb022fb06e525dc92f670689940c8dade2908fc4` |
| Preset completeness | **EXACT_PROCESS_SPOOL_PRESET_REQUIRED** |
| Unresolved filament fields | nozzle temperature, bed temperature, chamber temperature, flow ratio, pressure advance, maximum volumetric speed, cooling |
| Printer | QIDI Plus4; 305 x 305 x 280 mm nominal; 5 mm protected edge margin |
| Material / nozzle / layer | PETG / 0.4 mm / 0.20 mm |
| Plate envelope | 90.0 x 55.0 x 6.0 mm; centered |
| Native slice record | QIDI Studio version, sliced mass and time: ____________________ |

## Objects and orientation

| STL | Qty | Locked orientation | Source SHA-256 |
|---|---:|---|---|
| `camera_plate_universal.stl` | 1 | Flat as exported; CAM/MAST labels upward | `7fb63205ddc37b517ee452eda352893c7912cebe74086d977ef0beb8ec2d006f` |

## Required gates

| Gate | Status | Recorded values |
|---|---|---|
| `fixed_camera_fallback_architecture_released` | **NOT_TESTED** | `{"architecture_decision_revision": null, "architecture_decision_sha256": null, "architecture_decision_status": null, "fallback_authorization_reference": null, "fixed_camera_fallback_authorized": null}` |
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "provisional_protected_envelope_mm": [295, 295, 275]}` |
| `plus4_protected_envelope_verified` | **PASS** | `{"build_surface": "QIDI dual-sided textured PEI plate", "carriage_clearance_result": "PASS - protected envelope is inside official nominal volume", "enclosure_clearance_result": "PASS - operator confirmed completed printer qualification", "firmware_version": "Plus4_v1.7.1 official baseline; operator confirmed fully updated", "full_travel_test_result": "PASS - operator confirmed completed printer qualification", "printer_serial": "NOT_TRACKED_PROTOTYPE", "purge_and_exclusion_zone_result": "PASS - operator confirmed completed printer qualification", "verified_protected_envelope_mm": [295, 295, 275]}` |
| `nozzle_0p4_confirmed` | **PASS** | `{"installed_nozzle_mm": 0.4, "verification_method": "Official QIDI Plus4 standard specification and official printer.cfg; operator confirmed printer configuration"}` |
| `petg_general_profile_calibrated` | **NOT_TESTED** | `{"brand": null, "calibration_result": null, "drying_record": null, "filament_name": null, "profile_revision": null, "spool_lot": null}` |
| `camera_mount_interface_measured` | **NOT_TESTED** | `{"camera_model": null, "camera_thread": null, "safe_thread_engagement_mm": null, "selected_camera_screw_length_mm": null, "selected_tslot_screw_length_mm": null, "strap_width_mm": null}` |
| `general_clearance_holes_coupon_pass` | **NOT_TESTED** | `{"m3_selected_mm": null, "m4_or_board_screw_selected_mm": null, "m5_selected_mm": null}` |
| `setup_hardware_coupon_pass` | **NOT_TESTED** | `{"camera_hex_ac_mm": null, "fit_result": null, "m3_head_recess_d_mm": null, "m4_washer_od_mm": null, "m5_washer_od_mm": null}` |
| `geometry_matches_measurements` | **PASS** | `{"affected_parts_reviewed": true, "design_revision": "RC03-INT-R1", "effective_parameters_file": "config/parameters.json", "measurement_record_revision": "2026-09-06_JOB03C1_REWORK", "regeneration_completed": true}` |
| `qidi_studio_roundtrip_confirmed` | **NOT_TESTED** | `{"critical_layer_preview_pass_by_job": {}, "evidence_reference_by_job": {}, "geometry_scale_percent_by_job": {}, "native_project_sha256_by_job": {}, "object_count_by_job": {}, "qidi_studio_version": null, "saved_profile_revision_by_job": {}, "validated_job_ids": []}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: Actual fallback camera, 1/4-20 screw, two M5 screws/T-nuts/washers, straps.
- Open `print_plates_3mf/03C3_PETG_camera_plate.PRINT_SETTINGS.md` and follow every exact value in it.
- Import `slicer_profiles/QIDI_PLUS4/petg_general_0p4.process.json` and select `Generic PETG @Qidi X-Plus 4 0.4 nozzle` as the separate filament preset.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `petg_general_0p4`: 4 walls, 5 top / 5 bottom layers, 25% gyroid infill.
- Supports: off. Bed adhesion: 5 mm outer brim after the exact PETG spool is qualified.
- Dimensional controls: Use only with same-spool coupons.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- FIXED-MAST FALLBACK ONLY: do not treat this plate as an arm-camera adapter. Keep the job on hold until the camera architecture revision explicitly releases the fallback. Then measure camera thread direction, screw/head dimensions and safe engagement; check M5 ligaments, scales, strap slots, cable direction and no screw bottoming.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, modeled identity and revision before cleanup.
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


# Job 03D - Two keyed ABS TCP datum cartridges: one selected INSTALL datum and one qualified recalibration-required SPARE

| Control field | Released value |
|---|---|
| Design revision | `RC03-INT-R1` |
| Lifecycle state | **UNRELEASED** |
| Route / stage | `required` / `first_article` |
| Kit | `KIT-PUCK` |
| Plate | `03D_ABS_TCP_datum_cartridges.3mf` |
| Plate SHA-256 | `597423729e6d84ed39847ef9093fec57dcce2d5a51fee3c1bf17228d5045c8f7` |
| Profile | `abs_rapido_calibration_0p4` / `f3c6513d491cad5e3fc611549c640439ac58189ddea5c79fe01725e3a846b114` |
| Exact settings sheet | `print_plates_3mf/03D_ABS_TCP_datum_cartridges.PRINT_SETTINGS.md` / `3e05dc8654924984aeb3fba467e18864eb5797ea8703391043aee9a286f29546` |
| QIDI process import | `slicer_profiles/QIDI_PLUS4/abs_rapido_calibration_0p4.process.json` / `c069454369dc8abe726d0db4359928e9fa870c694cdfdf7b044a3debeeb2d564` |
| Filament preset | `qidi_abs_rapido_xplus4_0p4` / `ce549e11c71d71294ae086694987ac99842a14ba8fc26e24a879f7dd31b65bd4` |
| Preset completeness | **EXACT_REPRODUCIBLE** |
| Unresolved filament fields | None |
| Printer | QIDI Plus4; 305 x 305 x 280 mm nominal; 5 mm protected edge margin |
| Material / nozzle / layer | QIDI ABS Rapido / 0.4 mm / 0.16 mm |
| Plate envelope | 72.0 x 30.0 x 4.0 mm; centered |
| Native slice record | QIDI Studio version, sliced mass and time: ____________________ |

## Objects and orientation

| STL | Qty | Locked orientation | Source SHA-256 |
|---|---:|---|---|
| `calibration_puck.stl` | 2 | Flat as exported; crosshair upward; ironing off | `3d232103d1cc89d083cc700526abe40344db3f34f80609a5f134cb37a9247ce6` |

## Required gates

| Gate | Status | Recorded values |
|---|---|---|
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "provisional_protected_envelope_mm": [295, 295, 275]}` |
| `plus4_protected_envelope_verified` | **PASS** | `{"build_surface": "QIDI dual-sided textured PEI plate", "carriage_clearance_result": "PASS - protected envelope is inside official nominal volume", "enclosure_clearance_result": "PASS - operator confirmed completed printer qualification", "firmware_version": "Plus4_v1.7.1 official baseline; operator confirmed fully updated", "full_travel_test_result": "PASS - operator confirmed completed printer qualification", "printer_serial": "NOT_TRACKED_PROTOTYPE", "purge_and_exclusion_zone_result": "PASS - operator confirmed completed printer qualification", "verified_protected_envelope_mm": [295, 295, 275]}` |
| `nozzle_0p4_confirmed` | **PASS** | `{"installed_nozzle_mm": 0.4, "verification_method": "Official QIDI Plus4 standard specification and official printer.cfg; operator confirmed printer configuration"}` |
| `abs_rapido_calibration_profile_calibrated` | **PASS** | `{"brand": "QIDI", "calibration_result": "PASS - operator confirmed the installed QIDI ABS Rapido preset and current native Job 00A slice; matching coupons provide dimensional release", "chamber_condition": "QIDI Plus4 enclosure sealed; 55 C chamber target from the installed QIDI ABS Rapido preset", "drying_record": "Operator confirmed print-ready; detailed drying record waived for prototype coupons", "filament_name": "ABS Rapido", "profile_revision": "RC03-INT-R1 abs_rapido_calibration_0p4 SHA256 f3c6513d491cad5e3fc611549c640439ac58189ddea5c79fe01725e3a846b114", "spool_lot": "NOT_TRACKED_PROTOTYPE"}` |
| `calibration_clearance_holes_coupon_pass` | **NOT_TESTED** | `{"fit_result": null, "m3_head_recess_d_mm": null, "m3_screw_major_diameter_mm": null, "screw_head_d_mm": null, "smallest_free_hole_mm": null}` |
| `phone_station_registration_coupon_pass` | **PASS** | `{"actual_pin_diameter_measurements_mm": ["6.0 nominal - not caliper-measured under prototype waiver"], "crack_or_whitening_result": "PASS_NONE_REPORTED", "insertion_removal_cycles": "WAIVED_FUNCTIONAL_HAND_FIT_CONFIRMED", "inversion_retention_result": "WAIVED_FOR_PROTOTYPE", "lateral_play_mm": "NOT_NUMERICALLY_MEASURED_FUNCTIONAL_FIT_ACCEPTED", "selected_radial_slot_length_mm": 10.0, "selected_radial_slot_width_mm": 6.2, "selected_round_socket_mm": 6.2}` |
| `geometry_matches_measurements` | **PASS** | `{"affected_parts_reviewed": true, "design_revision": "RC03-INT-R1", "effective_parameters_file": "config/parameters.json", "measurement_record_revision": "2026-09-06_JOB03C1_REWORK", "regeneration_completed": true}` |
| `qidi_studio_roundtrip_confirmed` | **NOT_TESTED** | `{"critical_layer_preview_pass_by_job": {}, "evidence_reference_by_job": {}, "geometry_scale_percent_by_job": {}, "native_project_sha256_by_job": {}, "object_count_by_job": {}, "qidi_studio_version": null, "saved_profile_revision_by_job": {}, "validated_job_ids": []}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: Accepted phone/TCP station, two M3 screws, straightedge and depth/height gauge.
- Open `print_plates_3mf/03D_ABS_TCP_datum_cartridges.PRINT_SETTINGS.md` and follow every exact value in it.
- Import `slicer_profiles/QIDI_PLUS4/abs_rapido_calibration_0p4.process.json` and select `QIDI ABS Rapido @Qidi X-Plus 4 0.4 nozzle` as the separate filament preset.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `abs_rapido_calibration_0p4`: 4 walls, 6 top / 6 bottom layers, 40% gyroid infill.
- Supports: off. Bed adhesion: 5 mm outer brim with 0.05 mm object gap on clean textured PEI.
- Dimensional controls: No ironing over crosshairs or divots; seam away from keyed receiver faces; zero XY compensation pending Job 00F.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- Keep slicer object calibration_puck_1 as 03D-A and calibration_puck_2 as 03D-B. Qualify each separately; both must have an intact crosshair/divot, no more than 0.15 mm lateral play, and no more than 0.10 mm mounted-height range over ten cycles. For each, calculate score = max(play / 0.15, height range / 0.10). Label the lower-score cartridge INSTALL; if tied at measuring resolution, choose the lower height range, then 03D-A. Label the other accepted cartridge SPARE - TCP RECALIBRATION REQUIRED.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, modeled identity and revision before cleanup.
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


# Job 04A - Shared ABS compliant tool body with keyed cap and one spare cap

| Control field | Released value |
|---|---|
| Design revision | `RC03-INT-R1` |
| Lifecycle state | **UNRELEASED** |
| Route / stage | `any_tool_route` / `route` |
| Kit | `KIT-TOOL-COMMON` |
| Plate | `04A_ABS_shared_compliant_tool.3mf` |
| Plate SHA-256 | `91a9be9ec968c66b10543d13faae269d991b176fffd105d801a07f4a08107882` |
| Profile | `abs_rapido_precision_0p4` / `60827c142c2f8e88c0a45ace71712cf2c94f84d66dc796880352ab32de1e7195` |
| Exact settings sheet | `print_plates_3mf/04A_ABS_shared_compliant_tool.PRINT_SETTINGS.md` / `a5f98db5e0bd54f803e6b623cfd587be6cadb2b5f7ef55ea192664edb244027a` |
| QIDI process import | `slicer_profiles/QIDI_PLUS4/abs_rapido_precision_0p4.process.json` / `c115ad0ca8acafa86bc303973bbbae27578fdd57db8cbf437a7c8175710ba90a` |
| Filament preset | `qidi_abs_rapido_xplus4_0p4` / `ce549e11c71d71294ae086694987ac99842a14ba8fc26e24a879f7dd31b65bd4` |
| Preset completeness | **EXACT_REPRODUCIBLE** |
| Unresolved filament fields | None |
| Printer | QIDI Plus4; 305 x 305 x 280 mm nominal; 5 mm protected edge margin |
| Material / nozzle / layer | QIDI ABS Rapido / 0.4 mm / 0.16 mm |
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
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "provisional_protected_envelope_mm": [295, 295, 275]}` |
| `plus4_protected_envelope_verified` | **PASS** | `{"build_surface": "QIDI dual-sided textured PEI plate", "carriage_clearance_result": "PASS - protected envelope is inside official nominal volume", "enclosure_clearance_result": "PASS - operator confirmed completed printer qualification", "firmware_version": "Plus4_v1.7.1 official baseline; operator confirmed fully updated", "full_travel_test_result": "PASS - operator confirmed completed printer qualification", "printer_serial": "NOT_TRACKED_PROTOTYPE", "purge_and_exclusion_zone_result": "PASS - operator confirmed completed printer qualification", "verified_protected_envelope_mm": [295, 295, 275]}` |
| `nozzle_0p4_confirmed` | **PASS** | `{"installed_nozzle_mm": 0.4, "verification_method": "Official QIDI Plus4 standard specification and official printer.cfg; operator confirmed printer configuration"}` |
| `abs_rapido_precision_profile_calibrated` | **PASS** | `{"brand": "QIDI", "calibration_result": "PASS - operator confirmed the installed QIDI ABS Rapido preset and current native Job 00A slice; matching coupons provide dimensional release", "chamber_condition": "QIDI Plus4 enclosure sealed; 55 C chamber target from the installed QIDI ABS Rapido preset", "drying_record": "Operator confirmed print-ready; detailed drying record waived for prototype coupons", "filament_name": "ABS Rapido", "profile_revision": "RC03-INT-R1 abs_rapido_precision_0p4 SHA256 60827c142c2f8e88c0a45ace71712cf2c94f84d66dc796880352ab32de1e7195", "spool_lot": "NOT_TRACKED_PROTOTYPE"}` |
| `compliant_tool_m3_insert_coupon_pass` | **NOT_TESTED** | `{"insert_length_mm": null, "insert_od_mm": null, "installed_depth_mm": null, "retention_result": null, "selected_pocket_mm": null}` |
| `gripper_interface_measured` | **NOT_TESTED** | `{"jaw_opening_mm": null, "jaw_pad_height_mm": null, "jaw_pad_width_mm": null, "selected_grip_setting": null}` |
| `gripper_coupon_pass` | **NOT_TESTED** | `{"crush_result": null, "selected_grip_setting": null, "shim_each_side_mm": null, "slip_result": null}` |
| `spring_dimensions_measured` | **NOT_TESTED** | `{"approx_rate_n_per_mm": null, "coil_bind_length_mm": null, "free_length_mm": null, "id_mm": null, "od_mm": null}` |
| `spring_fit_coupon_pass` | **NOT_TESTED** | `{"binding_result": null, "cup_fit_result": null, "post_fit_result": null, "selected_step_mm": null}` |
| `precision_m3_head_coupon_pass` | **NOT_TESTED** | `{"fit_result": null, "m3_head_recess_d_mm": null, "screw_head_d_mm": null}` |
| `geometry_matches_measurements` | **PASS** | `{"affected_parts_reviewed": true, "design_revision": "RC03-INT-R1", "effective_parameters_file": "config/parameters.json", "measurement_record_revision": "2026-09-06_JOB03C1_REWORK", "regeneration_completed": true}` |
| `qidi_studio_roundtrip_confirmed` | **NOT_TESTED** | `{"critical_layer_preview_pass_by_job": {}, "evidence_reference_by_job": {}, "geometry_scale_percent_by_job": {}, "native_project_sha256_by_job": {}, "object_count_by_job": {}, "qidi_studio_version": null, "saved_profile_revision_by_job": {}, "validated_job_ids": []}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: Two M3 inserts, two M3x10 screws, accepted spring, route adapter.
- Open `print_plates_3mf/04A_ABS_shared_compliant_tool.PRINT_SETTINGS.md` and follow every exact value in it.
- Import `slicer_profiles/QIDI_PLUS4/abs_rapido_precision_0p4.process.json` and select `QIDI ABS Rapido @Qidi X-Plus 4 0.4 nozzle` as the separate filament preset.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `abs_rapido_precision_0p4`: 5 walls, 6 top / 6 bottom layers, 40% gyroid infill.
- Supports: off. Bed adhesion: 5 mm outer brim with 0.05 mm object gap on clean textured PEI.
- Dimensional controls: Keep the seam off gripper flats, spring seats, insert pockets, and the sliding guide bore; zero XY compensation pending Job 00C.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- Inspect body straightness, grip flats, guide bore, spring chamber and keyed locator. Install inserts square; cap must seat only in the keyed orientation. Verify 3-6 mm smooth return after route assembly.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, modeled identity and revision before cleanup.
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
| Design revision | `RC03-INT-R1` |
| Lifecycle state | **UNRELEASED** |
| Route / stage | `phone_stylus_route` / `route` |
| Kit | `KIT-TOOL-PHONE` |
| Plate | `04B_PETG_phone_stylus_adapters.3mf` |
| Plate SHA-256 | `e0c0f7e0a4d634347490cde4653329ea7c9527be5a967a2379077e1ad925c76f` |
| Profile | `petg_adapter_0p4` / `ce4f08af3ad5623c70bc5bb65dc086ae69cb51b98410dd26e85dbd0c1f693747` |
| Exact settings sheet | `print_plates_3mf/04B_PETG_phone_stylus_adapters.PRINT_SETTINGS.md` / `ceeca6a3cb6645b879ff3253f9cab91267a663253bb12e421abd1dc7f421b2db` |
| QIDI process import | `slicer_profiles/QIDI_PLUS4/petg_adapter_0p4.process.json` / `0eac339f7768fb799fa420cd300710e080134d0c0737652fd9afd51d9bc4fa91` |
| Filament preset | `exact_petg_spool_xplus4_0p4` / `e4af446b19a2425a1f87b49feb022fb06e525dc92f670689940c8dade2908fc4` |
| Preset completeness | **EXACT_PROCESS_SPOOL_PRESET_REQUIRED** |
| Unresolved filament fields | nozzle temperature, bed temperature, chamber temperature, flow ratio, pressure advance, maximum volumetric speed, cooling |
| Printer | QIDI Plus4; 305 x 305 x 280 mm nominal; 5 mm protected edge margin |
| Material / nozzle / layer | PETG / 0.4 mm / 0.12 mm |
| Plate envelope | 33.6 x 13.6 x 5.5 mm; centered |
| Native slice record | QIDI Studio version, sliced mass and time: ____________________ |

## Objects and orientation

| STL | Qty | Locked orientation | Source SHA-256 |
|---|---:|---|---|
| `stylus_collar_9mm.stl` | 2 | Flat flange on bed; split and measured sliding bore open | `abc908bcd256e8836d13c94cf58320654f78d972e0eb1923f50a6575233f2c8e` |

## Required gates

| Gate | Status | Recorded values |
|---|---|---|
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "provisional_protected_envelope_mm": [295, 295, 275]}` |
| `plus4_protected_envelope_verified` | **PASS** | `{"build_surface": "QIDI dual-sided textured PEI plate", "carriage_clearance_result": "PASS - protected envelope is inside official nominal volume", "enclosure_clearance_result": "PASS - operator confirmed completed printer qualification", "firmware_version": "Plus4_v1.7.1 official baseline; operator confirmed fully updated", "full_travel_test_result": "PASS - operator confirmed completed printer qualification", "printer_serial": "NOT_TRACKED_PROTOTYPE", "purge_and_exclusion_zone_result": "PASS - operator confirmed completed printer qualification", "verified_protected_envelope_mm": [295, 295, 275]}` |
| `nozzle_0p4_confirmed` | **PASS** | `{"installed_nozzle_mm": 0.4, "verification_method": "Official QIDI Plus4 standard specification and official printer.cfg; operator confirmed printer configuration"}` |
| `petg_adapter_profile_calibrated` | **NOT_TESTED** | `{"brand": null, "calibration_result": null, "drying_record": null, "filament_name": null, "profile_revision": null, "spool_lot": null}` |
| `stylus_diameter_measured` | **NOT_TESTED** | `{"diameter_mm": null, "measurement_locations": null, "stylus_model": null}` |
| `stylus_gauge_coupon_pass` | **NOT_TESTED** | `{"excess_play_result": null, "selected_nominal_mm": null, "sliding_fit_result": null}` |
| `adapter_retention_method_selected` | **NOT_TESTED** | `{"dry_fit_pull_result": null, "hardware_or_adhesive_spec": null, "plastic_compatibility_result": null, "removability_result": null, "retention_method": null, "route": null}` |
| `qidi_studio_roundtrip_confirmed` | **NOT_TESTED** | `{"critical_layer_preview_pass_by_job": {}, "evidence_reference_by_job": {}, "geometry_scale_percent_by_job": {}, "native_project_sha256_by_job": {}, "object_count_by_job": {}, "qidi_studio_version": null, "saved_profile_revision_by_job": {}, "validated_job_ids": []}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: Measured stylus, qualified removable compound only if dry fit is insufficient, pull gauge.
- Open `print_plates_3mf/04B_PETG_phone_stylus_adapters.PRINT_SETTINGS.md` and follow every exact value in it.
- Import `slicer_profiles/QIDI_PLUS4/petg_adapter_0p4.process.json` and select `Generic PETG @Qidi X-Plus 4 0.4 nozzle` as the separate filament preset.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `petg_adapter_0p4`: 4 walls, 5 top / 5 bottom layers, 100% rectilinear infill.
- Supports: off. Bed adhesion: 8 mm outer brim with 0.10 mm object gap after the exact PETG spool is qualified.
- Dimensional controls: Calibrate elephant-foot compensation so split bores remain open; never globally scale.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- Check bore and split. Set projection, quantify dry-fit or minimal-compound pull retention and repeat cycles, prove removability, then inspect after 24-hour creep and verify capacitive function.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, modeled identity and revision before cleanup.
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


# Job 05A - One phone TPU tip for dimensional and pull-off acceptance

| Control field | Released value |
|---|---|
| Design revision | `RC03-INT-R1` |
| Lifecycle state | **UNRELEASED** |
| Route / stage | `required` / `first_article` |
| Kit | `KIT-PHONE` |
| Plate | `05A_TPU_phone_tip_first_article.3mf` |
| Plate SHA-256 | `4171263d706936cee8f393d2b7be90f299f8a362ceb1ecf3a32732f6c45f1899` |
| Profile | `tpu95a_0p4` / `4d655c7387b95cece3d27151ae8a7283688bbf87db088790376aa3156d5afd4b` |
| Exact settings sheet | `print_plates_3mf/05A_TPU_phone_tip_first_article.PRINT_SETTINGS.md` / `9cf56d40d7cc29bf233cdce02e3376e324ad6462c7422435b77992b7a2942008` |
| QIDI process import | `slicer_profiles/QIDI_PLUS4/tpu95a_0p4.process.json` / `547c6502ce8d5f4b04a5d247b50fcafb884dbe587b1df9c43935dfa6d297e6ba` |
| Filament preset | `exact_tpu95a_spool_xplus4_0p4` / `945d923a44ad2a09516d5ae3dceffc8bcd567a4e4c25b408ff4879c2435bb9cf` |
| Preset completeness | **EXACT_PROCESS_SPOOL_PRESET_REQUIRED** |
| Unresolved filament fields | nozzle temperature, bed temperature, flow ratio, pressure advance, maximum volumetric speed, cooling |
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
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "provisional_protected_envelope_mm": [295, 295, 275]}` |
| `plus4_protected_envelope_verified` | **PASS** | `{"build_surface": "QIDI dual-sided textured PEI plate", "carriage_clearance_result": "PASS - protected envelope is inside official nominal volume", "enclosure_clearance_result": "PASS - operator confirmed completed printer qualification", "firmware_version": "Plus4_v1.7.1 official baseline; operator confirmed fully updated", "full_travel_test_result": "PASS - operator confirmed completed printer qualification", "printer_serial": "NOT_TRACKED_PROTOTYPE", "purge_and_exclusion_zone_result": "PASS - operator confirmed completed printer qualification", "verified_protected_envelope_mm": [295, 295, 275]}` |
| `nozzle_0p4_confirmed` | **PASS** | `{"installed_nozzle_mm": 0.4, "verification_method": "Official QIDI Plus4 standard specification and official printer.cfg; operator confirmed printer configuration"}` |
| `tpu_profile_calibrated` | **NOT_TESTED** | `{"brand": null, "calibration_result": null, "drying_record": null, "filament_name": null, "profile_revision": null, "shore_hardness": "95A", "spool_lot": null}` |
| `qidi_studio_roundtrip_confirmed` | **NOT_TESTED** | `{"critical_layer_preview_pass_by_job": {}, "evidence_reference_by_job": {}, "geometry_scale_percent_by_job": {}, "native_project_sha256_by_job": {}, "object_count_by_job": {}, "qidi_studio_version": null, "saved_profile_revision_by_job": {}, "validated_job_ids": []}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: Actual M4 screw/peg and pull gauge.
- Open `print_plates_3mf/05A_TPU_phone_tip_first_article.PRINT_SETTINGS.md` and follow every exact value in it.
- Import `slicer_profiles/QIDI_PLUS4/tpu95a_0p4.process.json` and select `Generic TPU 95A @Qidi X-Plus 4 0.4 nozzle` as the separate filament preset.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `tpu95a_0p4`: 3 walls, 5 top / 5 bottom layers, 100% rectilinear infill.
- Supports: off. Bed adhesion: 3 mm outer brim with 0.10 mm object gap after the exact dry TPU spool is qualified.
- Dimensional controls: Keep first-layer flow calibrated so flared bore entries remain open; do not force a failed tip onto hardware.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- Inspect flared bore, seating witness and contact face. Fit to actual hardware, record seating depth and provisional axial pull force; retain as the first article.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, modeled identity and revision before cleanup.
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
| Design revision | `RC03-INT-R1` |
| Lifecycle state | **UNRELEASED** |
| Route / stage | `required` / `production` |
| Kit | `KIT-PHONE` |
| Plate | `05B_TPU_phone_tips_and_spares.3mf` |
| Plate SHA-256 | `ba8da269c5c0363efaa344e161f7e2678265b8b4aebb2c541c396dfa0c435747` |
| Profile | `tpu95a_0p4` / `4d655c7387b95cece3d27151ae8a7283688bbf87db088790376aa3156d5afd4b` |
| Exact settings sheet | `print_plates_3mf/05B_TPU_phone_tips_and_spares.PRINT_SETTINGS.md` / `05ecdb00d5d89c5d971407a6d432ad7a8fd5e0b53a004beb1b01963c3da63fe3` |
| QIDI process import | `slicer_profiles/QIDI_PLUS4/tpu95a_0p4.process.json` / `547c6502ce8d5f4b04a5d247b50fcafb884dbe587b1df9c43935dfa6d297e6ba` |
| Filament preset | `exact_tpu95a_spool_xplus4_0p4` / `945d923a44ad2a09516d5ae3dceffc8bcd567a4e4c25b408ff4879c2435bb9cf` |
| Preset completeness | **EXACT_PROCESS_SPOOL_PRESET_REQUIRED** |
| Unresolved filament fields | nozzle temperature, bed temperature, flow ratio, pressure advance, maximum volumetric speed, cooling |
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
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "provisional_protected_envelope_mm": [295, 295, 275]}` |
| `plus4_protected_envelope_verified` | **PASS** | `{"build_surface": "QIDI dual-sided textured PEI plate", "carriage_clearance_result": "PASS - protected envelope is inside official nominal volume", "enclosure_clearance_result": "PASS - operator confirmed completed printer qualification", "firmware_version": "Plus4_v1.7.1 official baseline; operator confirmed fully updated", "full_travel_test_result": "PASS - operator confirmed completed printer qualification", "printer_serial": "NOT_TRACKED_PROTOTYPE", "purge_and_exclusion_zone_result": "PASS - operator confirmed completed printer qualification", "verified_protected_envelope_mm": [295, 295, 275]}` |
| `nozzle_0p4_confirmed` | **PASS** | `{"installed_nozzle_mm": 0.4, "verification_method": "Official QIDI Plus4 standard specification and official printer.cfg; operator confirmed printer configuration"}` |
| `tpu_profile_calibrated` | **NOT_TESTED** | `{"brand": null, "calibration_result": null, "drying_record": null, "filament_name": null, "profile_revision": null, "shore_hardness": "95A", "spool_lot": null}` |
| `phone_tpu_retention_coupon_pass` | **NOT_TESTED** | `{"approved_limits_id": null, "axial_pull_test_method": null, "contact_face_result": null, "first_article_job": null, "installation_result": null, "measured_pull_force_n": null, "minimum_pull_force_n": null, "proof_duration_s": null, "pull_off_result": null}` |
| `qidi_studio_roundtrip_confirmed` | **NOT_TESTED** | `{"critical_layer_preview_pass_by_job": {}, "evidence_reference_by_job": {}, "geometry_scale_percent_by_job": {}, "native_project_sha256_by_job": {}, "object_count_by_job": {}, "qidi_studio_version": null, "saved_profile_revision_by_job": {}, "validated_job_ids": []}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: Accepted first article and actual M4 hardware.
- Open `print_plates_3mf/05B_TPU_phone_tips_and_spares.PRINT_SETTINGS.md` and follow every exact value in it.
- Import `slicer_profiles/QIDI_PLUS4/tpu95a_0p4.process.json` and select `Generic TPU 95A @Qidi X-Plus 4 0.4 nozzle` as the separate filament preset.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `tpu95a_0p4`: 3 walls, 5 top / 5 bottom layers, 100% rectilinear infill.
- Supports: off. Bed adhesion: 3 mm outer brim with 0.10 mm object gap after the exact dry TPU spool is qualified.
- Dimensional controls: Keep first-layer flow calibrated so flared bore entries remain open; do not force a failed tip onto hardware.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- Compare all three with the accepted article; reject blocked bores, stringing or face defects. Label installed pair and spare pair across 05A/05B inventory.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, modeled identity and revision before cleanup.
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
| Design revision | `RC03-INT-R1` |
| Lifecycle state | **UNRELEASED** |
| Route / stage | `keyboard_rod_route` / `first_article` |
| Kit | `KIT-TOOL-KB` |
| Plate | `05C_TPU_keyboard_tip_first_article.3mf` |
| Plate SHA-256 | `1b6b6f5803d89ac00eb31cebc09e470365938842edfb7a748d278d81e5791c76` |
| Profile | `tpu95a_0p4` / `4d655c7387b95cece3d27151ae8a7283688bbf87db088790376aa3156d5afd4b` |
| Exact settings sheet | `print_plates_3mf/05C_TPU_keyboard_tip_first_article.PRINT_SETTINGS.md` / `8256bf1ff0f030d8023a16f9f4a299c115b0bf3a151e6fe933cbc1cb919aca4f` |
| QIDI process import | `slicer_profiles/QIDI_PLUS4/tpu95a_0p4.process.json` / `547c6502ce8d5f4b04a5d247b50fcafb884dbe587b1df9c43935dfa6d297e6ba` |
| Filament preset | `exact_tpu95a_spool_xplus4_0p4` / `945d923a44ad2a09516d5ae3dceffc8bcd567a4e4c25b408ff4879c2435bb9cf` |
| Preset completeness | **EXACT_PROCESS_SPOOL_PRESET_REQUIRED** |
| Unresolved filament fields | nozzle temperature, bed temperature, flow ratio, pressure advance, maximum volumetric speed, cooling |
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
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "provisional_protected_envelope_mm": [295, 295, 275]}` |
| `plus4_protected_envelope_verified` | **PASS** | `{"build_surface": "QIDI dual-sided textured PEI plate", "carriage_clearance_result": "PASS - protected envelope is inside official nominal volume", "enclosure_clearance_result": "PASS - operator confirmed completed printer qualification", "firmware_version": "Plus4_v1.7.1 official baseline; operator confirmed fully updated", "full_travel_test_result": "PASS - operator confirmed completed printer qualification", "printer_serial": "NOT_TRACKED_PROTOTYPE", "purge_and_exclusion_zone_result": "PASS - operator confirmed completed printer qualification", "verified_protected_envelope_mm": [295, 295, 275]}` |
| `nozzle_0p4_confirmed` | **PASS** | `{"installed_nozzle_mm": 0.4, "verification_method": "Official QIDI Plus4 standard specification and official printer.cfg; operator confirmed printer configuration"}` |
| `tpu_profile_calibrated` | **NOT_TESTED** | `{"brand": null, "calibration_result": null, "drying_record": null, "filament_name": null, "profile_revision": null, "shore_hardness": "95A", "spool_lot": null}` |
| `keyboard_rod_measured` | **NOT_TESTED** | `{"diameter_mm": null, "length_mm": null, "material": null, "measurement_locations": null}` |
| `qidi_studio_roundtrip_confirmed` | **NOT_TESTED** | `{"critical_layer_preview_pass_by_job": {}, "evidence_reference_by_job": {}, "geometry_scale_percent_by_job": {}, "native_project_sha256_by_job": {}, "object_count_by_job": {}, "qidi_studio_version": null, "saved_profile_revision_by_job": {}, "validated_job_ids": []}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: Actual 6 mm rod and pull gauge.
- Open `print_plates_3mf/05C_TPU_keyboard_tip_first_article.PRINT_SETTINGS.md` and follow every exact value in it.
- Import `slicer_profiles/QIDI_PLUS4/tpu95a_0p4.process.json` and select `Generic TPU 95A @Qidi X-Plus 4 0.4 nozzle` as the separate filament preset.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `tpu95a_0p4`: 3 walls, 5 top / 5 bottom layers, 100% rectilinear infill.
- Supports: off. Bed adhesion: 3 mm outer brim with 0.10 mm object gap after the exact dry TPU spool is qualified.
- Dimensional controls: Keep first-layer flow calibrated so flared bore entries remain open; do not force a failed tip onto hardware.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- Inspect bore entry, 8.5 mm seating witness and face. Record seating and axial pull force on the real rod; retain as first article.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, modeled identity and revision before cleanup.
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
| Design revision | `RC03-INT-R1` |
| Lifecycle state | **UNRELEASED** |
| Route / stage | `keyboard_rod_route` / `production` |
| Kit | `KIT-TOOL-KB` |
| Plate | `05D_TPU_keyboard_tips_and_spares.3mf` |
| Plate SHA-256 | `63efc560b375ce5a6abbd5092f51632a51de8771b90aca70794ec6b7e999e843` |
| Profile | `tpu95a_0p4` / `4d655c7387b95cece3d27151ae8a7283688bbf87db088790376aa3156d5afd4b` |
| Exact settings sheet | `print_plates_3mf/05D_TPU_keyboard_tips_and_spares.PRINT_SETTINGS.md` / `c2f91ab16e4faeea96945bdef95eba4cfb142430f44302565ebee51ca891ce9f` |
| QIDI process import | `slicer_profiles/QIDI_PLUS4/tpu95a_0p4.process.json` / `547c6502ce8d5f4b04a5d247b50fcafb884dbe587b1df9c43935dfa6d297e6ba` |
| Filament preset | `exact_tpu95a_spool_xplus4_0p4` / `945d923a44ad2a09516d5ae3dceffc8bcd567a4e4c25b408ff4879c2435bb9cf` |
| Preset completeness | **EXACT_PROCESS_SPOOL_PRESET_REQUIRED** |
| Unresolved filament fields | nozzle temperature, bed temperature, flow ratio, pressure advance, maximum volumetric speed, cooling |
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
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "provisional_protected_envelope_mm": [295, 295, 275]}` |
| `plus4_protected_envelope_verified` | **PASS** | `{"build_surface": "QIDI dual-sided textured PEI plate", "carriage_clearance_result": "PASS - protected envelope is inside official nominal volume", "enclosure_clearance_result": "PASS - operator confirmed completed printer qualification", "firmware_version": "Plus4_v1.7.1 official baseline; operator confirmed fully updated", "full_travel_test_result": "PASS - operator confirmed completed printer qualification", "printer_serial": "NOT_TRACKED_PROTOTYPE", "purge_and_exclusion_zone_result": "PASS - operator confirmed completed printer qualification", "verified_protected_envelope_mm": [295, 295, 275]}` |
| `nozzle_0p4_confirmed` | **PASS** | `{"installed_nozzle_mm": 0.4, "verification_method": "Official QIDI Plus4 standard specification and official printer.cfg; operator confirmed printer configuration"}` |
| `tpu_profile_calibrated` | **NOT_TESTED** | `{"brand": null, "calibration_result": null, "drying_record": null, "filament_name": null, "profile_revision": null, "shore_hardness": "95A", "spool_lot": null}` |
| `keyboard_rod_measured` | **NOT_TESTED** | `{"diameter_mm": null, "length_mm": null, "material": null, "measurement_locations": null}` |
| `keyboard_tpu_retention_coupon_pass` | **NOT_TESTED** | `{"approved_limits_id": null, "axial_pull_test_method": null, "contact_face_result": null, "first_article_job": null, "installation_result": null, "measured_pull_force_n": null, "minimum_pull_force_n": null, "proof_duration_s": null, "pull_off_result": null}` |
| `qidi_studio_roundtrip_confirmed` | **NOT_TESTED** | `{"critical_layer_preview_pass_by_job": {}, "evidence_reference_by_job": {}, "geometry_scale_percent_by_job": {}, "native_project_sha256_by_job": {}, "object_count_by_job": {}, "qidi_studio_version": null, "saved_profile_revision_by_job": {}, "validated_job_ids": []}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: Accepted first article and actual 6 mm rod.
- Open `print_plates_3mf/05D_TPU_keyboard_tips_and_spares.PRINT_SETTINGS.md` and follow every exact value in it.
- Import `slicer_profiles/QIDI_PLUS4/tpu95a_0p4.process.json` and select `Generic TPU 95A @Qidi X-Plus 4 0.4 nozzle` as the separate filament preset.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `tpu95a_0p4`: 3 walls, 5 top / 5 bottom layers, 100% rectilinear infill.
- Supports: off. Bed adhesion: 3 mm outer brim with 0.10 mm object gap after the exact dry TPU spool is qualified.
- Dimensional controls: Keep first-layer flow calibrated so flared bore entries remain open; do not force a failed tip onto hardware.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- Compare all three with the accepted article; reject blocked bores or face defects. Label installed parts and spares.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, modeled identity and revision before cleanup.
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


# Job 07A - First fixed-mast fallback foot with rear-lug clamp bolts; not part of the intended arm-mounted camera architecture

| Control field | Released value |
|---|---|
| Design revision | `RC03-INT-R1` |
| Lifecycle state | **UNRELEASED** |
| Route / stage | `camera_mast_optional` / `first_article` |
| Kit | `KIT-MAST` |
| Plate | `07A_ASA_mast_foot_first_article.3mf` |
| Plate SHA-256 | `fe98242302efb943e0fba6fb4db4e38f0008ecda19e306688be844dd162af84a` |
| Profile | `asa_structural_0p4` / `f1e5cb6562054f5363ffbb34572181e1e52fad37aea3595c4a7c5a9cfa8ec7c9` |
| Exact settings sheet | `print_plates_3mf/07A_ASA_mast_foot_first_article.PRINT_SETTINGS.md` / `e8d47f729bd0c125a7e9804dac2f342484c0f536f0c5f83a1bffeab28398e7ff` |
| QIDI process import | `slicer_profiles/QIDI_PLUS4/asa_structural_0p4.process.json` / `a6116150e09eb3212b6d4d76b7def11495593f564f497d2e8e5799ec6e69f7de` |
| Filament preset | `exact_asa_spool_xplus4_0p4` / `568d1ecd4a7a2acf80e0789ea89a8513e51af7d415c8d0e24041669682cb5953` |
| Preset completeness | **EXACT_PROCESS_SPOOL_PRESET_REQUIRED** |
| Unresolved filament fields | nozzle temperature, bed temperature, chamber temperature, flow ratio, pressure advance, maximum volumetric speed, cooling |
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
| `fixed_camera_fallback_architecture_released` | **NOT_TESTED** | `{"architecture_decision_revision": null, "architecture_decision_sha256": null, "architecture_decision_status": null, "fallback_authorization_reference": null, "fixed_camera_fallback_authorized": null}` |
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "provisional_protected_envelope_mm": [295, 295, 275]}` |
| `plus4_protected_envelope_verified` | **PASS** | `{"build_surface": "QIDI dual-sided textured PEI plate", "carriage_clearance_result": "PASS - protected envelope is inside official nominal volume", "enclosure_clearance_result": "PASS - operator confirmed completed printer qualification", "firmware_version": "Plus4_v1.7.1 official baseline; operator confirmed fully updated", "full_travel_test_result": "PASS - operator confirmed completed printer qualification", "printer_serial": "NOT_TRACKED_PROTOTYPE", "purge_and_exclusion_zone_result": "PASS - operator confirmed completed printer qualification", "verified_protected_envelope_mm": [295, 295, 275]}` |
| `nozzle_0p4_confirmed` | **PASS** | `{"installed_nozzle_mm": 0.4, "verification_method": "Official QIDI Plus4 standard specification and official printer.cfg; operator confirmed printer configuration"}` |
| `asa_profile_calibrated` | **NOT_TESTED** | `{"brand": null, "calibration_result": null, "chamber_condition": null, "drying_record": null, "filament_name": null, "profile_revision": null, "spool_lot": null}` |
| `asa_mast_socket_coupon_pass` | **NOT_TESTED** | `{"extrusion_x_mm": null, "extrusion_y_mm": null, "fit_result": null, "selected_socket_mm": null}` |
| `asa_m5_nut_coupon_pass` | **NOT_TESTED** | `{"nut_across_flats_mm": null, "nut_thickness_mm": null, "retention_result": null, "selected_hex_mm": null}` |
| `asa_m5_clearance_coupon_pass` | **NOT_TESTED** | `{"bolt_major_diameter_mm": null, "m5_washer_fit_result": null, "m5_washer_od_mm": null, "selected_base_hole_mm": null, "selected_horizontal_hole_mm": null}` |
| `geometry_matches_measurements` | **PASS** | `{"affected_parts_reviewed": true, "design_revision": "RC03-INT-R1", "effective_parameters_file": "config/parameters.json", "measurement_record_revision": "2026-09-06_JOB03C1_REWORK", "regeneration_completed": true}` |
| `qidi_studio_roundtrip_confirmed` | **NOT_TESTED** | `{"critical_layer_preview_pass_by_job": {}, "evidence_reference_by_job": {}, "geometry_scale_percent_by_job": {}, "native_project_sha256_by_job": {}, "object_count_by_job": {}, "qidi_studio_version": null, "saved_profile_revision_by_job": {}, "validated_job_ids": []}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: One extrusion, two M5 clamp bolts/nuts, four base fasteners/washers.
- Open `print_plates_3mf/07A_ASA_mast_foot_first_article.PRINT_SETTINGS.md` and follow every exact value in it.
- Import `slicer_profiles/QIDI_PLUS4/asa_structural_0p4.process.json` and select `QIDI ASA @Qidi X-Plus 4 0.4 nozzle` as the separate filament preset.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `asa_structural_0p4`: 6 walls, 6 top / 6 bottom layers, 45% gyroid infill.
- Supports: off unless a released fallback revision approves build-plate-only support. Bed adhesion: 10 mm outer brim, enclosed printer, stable chamber, and no drafts.
- Dimensional controls: Use same-spool ASA socket and nut coupons before a full mast foot.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- Inspect layer bonding, flatness, socket, rear slit, lead-ins and rear-lug bolt path. Tighten bolts alternately; record grip, cracks and flatness immediately and after 24 hours.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, modeled identity and revision before cleanup.
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


# Job 07B - Second fixed-mast fallback foot after first-article acceptance; not part of the intended arm-mounted camera architecture

| Control field | Released value |
|---|---|
| Design revision | `RC03-INT-R1` |
| Lifecycle state | **UNRELEASED** |
| Route / stage | `camera_mast_optional` / `optional` |
| Kit | `KIT-MAST` |
| Plate | `07B_ASA_mast_foot_second.3mf` |
| Plate SHA-256 | `1212bdb01b8d4fb140b8eeb7a6e68fdfc604696662d27a199120def6b2260658` |
| Profile | `asa_structural_0p4` / `f1e5cb6562054f5363ffbb34572181e1e52fad37aea3595c4a7c5a9cfa8ec7c9` |
| Exact settings sheet | `print_plates_3mf/07B_ASA_mast_foot_second.PRINT_SETTINGS.md` / `46c56c393526bef5911b0ab604e85f36aeceee2892195a473b9d7931589c97ec` |
| QIDI process import | `slicer_profiles/QIDI_PLUS4/asa_structural_0p4.process.json` / `a6116150e09eb3212b6d4d76b7def11495593f564f497d2e8e5799ec6e69f7de` |
| Filament preset | `exact_asa_spool_xplus4_0p4` / `568d1ecd4a7a2acf80e0789ea89a8513e51af7d415c8d0e24041669682cb5953` |
| Preset completeness | **EXACT_PROCESS_SPOOL_PRESET_REQUIRED** |
| Unresolved filament fields | nozzle temperature, bed temperature, chamber temperature, flow ratio, pressure advance, maximum volumetric speed, cooling |
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
| `fixed_camera_fallback_architecture_released` | **NOT_TESTED** | `{"architecture_decision_revision": null, "architecture_decision_sha256": null, "architecture_decision_status": null, "fallback_authorization_reference": null, "fixed_camera_fallback_authorized": null}` |
| `plus4_machine_confirmed` | **PASS** | `{"nominal_build_volume_mm": [305, 305, 280], "printer_model": "QIDI Plus4", "provisional_protected_envelope_mm": [295, 295, 275]}` |
| `plus4_protected_envelope_verified` | **PASS** | `{"build_surface": "QIDI dual-sided textured PEI plate", "carriage_clearance_result": "PASS - protected envelope is inside official nominal volume", "enclosure_clearance_result": "PASS - operator confirmed completed printer qualification", "firmware_version": "Plus4_v1.7.1 official baseline; operator confirmed fully updated", "full_travel_test_result": "PASS - operator confirmed completed printer qualification", "printer_serial": "NOT_TRACKED_PROTOTYPE", "purge_and_exclusion_zone_result": "PASS - operator confirmed completed printer qualification", "verified_protected_envelope_mm": [295, 295, 275]}` |
| `nozzle_0p4_confirmed` | **PASS** | `{"installed_nozzle_mm": 0.4, "verification_method": "Official QIDI Plus4 standard specification and official printer.cfg; operator confirmed printer configuration"}` |
| `asa_profile_calibrated` | **NOT_TESTED** | `{"brand": null, "calibration_result": null, "chamber_condition": null, "drying_record": null, "filament_name": null, "profile_revision": null, "spool_lot": null}` |
| `asa_mast_socket_coupon_pass` | **NOT_TESTED** | `{"extrusion_x_mm": null, "extrusion_y_mm": null, "fit_result": null, "selected_socket_mm": null}` |
| `asa_m5_nut_coupon_pass` | **NOT_TESTED** | `{"nut_across_flats_mm": null, "nut_thickness_mm": null, "retention_result": null, "selected_hex_mm": null}` |
| `asa_m5_clearance_coupon_pass` | **NOT_TESTED** | `{"bolt_major_diameter_mm": null, "m5_washer_fit_result": null, "m5_washer_od_mm": null, "selected_base_hole_mm": null, "selected_horizontal_hole_mm": null}` |
| `geometry_matches_measurements` | **PASS** | `{"affected_parts_reviewed": true, "design_revision": "RC03-INT-R1", "effective_parameters_file": "config/parameters.json", "measurement_record_revision": "2026-09-06_JOB03C1_REWORK", "regeneration_completed": true}` |
| `mast_foot_first_article_pass` | **NOT_TESTED** | `{"base_flatness_mm": null, "bolt_clamp_result": null, "crack_result_after_24h": null, "initial_crack_result": null, "job_id": null, "nut_fit_result": null, "socket_fit_result": null}` |
| `qidi_studio_roundtrip_confirmed` | **NOT_TESTED** | `{"critical_layer_preview_pass_by_job": {}, "evidence_reference_by_job": {}, "geometry_scale_percent_by_job": {}, "native_project_sha256_by_job": {}, "object_count_by_job": {}, "qidi_studio_version": null, "saved_profile_revision_by_job": {}, "validated_job_ids": []}` |

## Preflight and native QIDI Studio review

- Hardware, samples and tools: Accepted first foot, second extrusion/foot hardware and crossbar.
- Open `print_plates_3mf/07B_ASA_mast_foot_second.PRINT_SETTINGS.md` and follow every exact value in it.
- Import `slicer_profiles/QIDI_PLUS4/asa_structural_0p4.process.json` and select `QIDI ASA @Qidi X-Plus 4 0.4 nozzle` as the separate filament preset.
- Verify the exact spool lot/profile revision, drying record, 0.4 mm nozzle and clean build surface.
- Import at 100% scale. Do not auto-orient, globally XY-scale, merge objects, or move an object outside the centered group.
- Apply `asa_structural_0p4`: 6 walls, 6 top / 6 bottom layers, 45% gyroid infill.
- Supports: off unless a released fallback revision approves build-plate-only support. Bed adhesion: 10 mm outer brim, enclosed printer, stable chamber, and no drafts.
- Dimensional controls: Use same-spool ASA socket and nut coupons before a full mast foot.
- Inspect every layer preview, especially closed slot ends, horizontal bores, pocket roofs, first-layer hole mouths, seam keys and thin ligaments.
- Save a native QIDI Studio project and record its version/path. A geometry-only 3MF is not a released machine project.

## Post-print inspection and released evidence

- Repeat 07A checks, label feet A/B, assemble the pair, then verify matched seating, crossbar level, plumb witness lines and stand stability.
- Cool to room temperature before dimensional or flatness measurements. Confirm part count, modeled identity and revision before cleanup.
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


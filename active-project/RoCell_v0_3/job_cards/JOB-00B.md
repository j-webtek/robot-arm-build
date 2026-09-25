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

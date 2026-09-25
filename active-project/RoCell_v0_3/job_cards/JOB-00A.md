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

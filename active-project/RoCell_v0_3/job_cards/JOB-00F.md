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

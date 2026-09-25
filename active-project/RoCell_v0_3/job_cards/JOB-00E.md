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

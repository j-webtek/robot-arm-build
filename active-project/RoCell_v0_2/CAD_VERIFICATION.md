# CAD and release-package verification

**Revision `RC02-PRO-R1` — automated status: PASS**

The release check independently reloads every STL and 3MF; verifies positive, watertight, winding-consistent single bodies; checks the protected 295 x 295 x 280 mm QIDI Plus4 envelope; confirms object counts, centered placement, source/plate hashes, job/profile qualification, manifest coverage, and a non-overlapping board layout.

- Printable STL models: **37**
- Controlled print jobs: **24**
- Total placed 3MF objects: **52**
- Unexpected or uncovered printable files: **0**

## QIDI Plus4 plate read-back

| Job | Plate | Objects | Envelope mm | Profile |
|---|---|---:|---:|---|
| 00A | `00A_PETG_keyboard_profile_fit_tests.3mf` | 5 | 174.0 x 138.0 x 11.0 | `petg_tray_structural_0p4` |
| 00B | `00B_PETG_phone_profile_fit_tests.3mf` | 4 | 216.0 x 80.0 x 16.0 | `petg_cradle_0p4` |
| 00C | `00C_PETG_tool_profile_fit_tests.3mf` | 4 | 156.0 x 70.0 x 34.0 | `petg_precision_0p4` |
| 00D | `00D_PETG_adapter_profile_fit_tests.3mf` | 2 | 128.0 x 106.0 x 18.0 | `petg_adapter_0p4` |
| 00E | `00E_PETG_general_setup_tests.3mf` | 3 | 208.0 x 124.0 x 14.0 | `petg_general_0p4` |
| 00F | `00F_PETG_calibration_profile_clearance_test.3mf` | 2 | 160.0 x 70.0 x 6.0 | `petg_calibration_0p4` |
| 01 | `01_PETG_keyboard_left.3mf` | 1 | 184.5 x 157.0 x 11.0 | `petg_tray_structural_0p4` |
| 02 | `02_PETG_keyboard_right.3mf` | 1 | 162.5 x 157.0 x 11.0 | `petg_tray_structural_0p4` |
| 03A | `03A_PETG_phone_cradle.3mf` | 1 | 117.3 x 172.8 x 20.0 | `petg_cradle_0p4` |
| 03B | `03B_PETG_keyboard_clamps.3mf` | 2 | 112.0 x 34.0 x 25.0 | `petg_general_0p4` |
| 03C1 | `03C1_PETG_tag_frame_first_article.3mf` | 1 | 78.0 x 78.0 x 4.0 | `petg_general_0p4` |
| 03C2 | `03C2_PETG_tag_frames_remaining.3mf` | 5 | 244.0 x 161.0 x 4.0 | `petg_general_0p4` |
| 03C3 | `03C3_PETG_camera_plate.3mf` | 1 | 90.0 x 55.0 x 6.0 | `petg_general_0p4` |
| 03D | `03D_PETG_calibration_puck.3mf` | 1 | 60.0 x 60.0 x 8.0 | `petg_calibration_0p4` |
| 04A | `04A_PETG_shared_compliant_tool.3mf` | 3 | 100.0 x 24.0 x 66.2 | `petg_precision_0p4` |
| 04B | `04B_PETG_phone_stylus_adapters.3mf` | 2 | 33.6 x 13.6 x 5.5 | `petg_adapter_0p4` |
| 04C | `04C_PETG_keyboard_rod_adapters.3mf` | 2 | 38.5 x 13.5 x 38.8 | `petg_adapter_0p4` |
| 05A | `05A_TPU_phone_tip_first_article.3mf` | 1 | 7.5 x 7.5 x 8.0 | `tpu95a_0p4` |
| 05B | `05B_TPU_phone_tips_and_spares.3mf` | 3 | 47.5 x 7.5 x 8.0 | `tpu95a_0p4` |
| 05C | `05C_TPU_keyboard_tip_first_article.3mf` | 1 | 12.0 x 12.0 x 14.0 | `tpu95a_0p4` |
| 05D | `05D_TPU_keyboard_tips_and_spares.3mf` | 3 | 52.0 x 12.0 x 14.0 | `tpu95a_0p4` |
| 06 | `06_ASA_mast_fit_tests.3mf` | 2 | 146.0 x 90.0 x 30.0 | `asa_structural_0p4` |
| 07A | `07A_ASA_mast_foot_first_article.3mf` | 1 | 92.0 x 92.0 x 74.0 | `asa_structural_0p4` |
| 07B | `07B_ASA_mast_foot_second.3mf` | 1 | 92.0 x 92.0 x 74.0 | `asa_structural_0p4` |

## Release boundary

This automated PASS establishes internal CAD/packaging consistency, not physical compatibility. Production remains locked by `PRINT_READINESS.md` until the exact devices, hardware, filament lots, coupons, QIDI Studio native projects, first articles, and post-print/assembly tests are measured and recorded.

The camera thread/head interface, real USB cable bend envelope, stylus/rod retention, spring rate, extrusion shrink, and all force/creep limits deliberately remain physical gates rather than unverified CAD assumptions.

Re-run `python scripts/validate_release_package.py` after every CAD, profile, job, or plate change.

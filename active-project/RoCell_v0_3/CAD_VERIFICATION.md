# CAD and release-package verification

**Revision `RC03-INT-R1` — automated status: PASS**

**Controlled release-input SHA-256:** `355441399b03911334e2e770080d24a5f101026f3d16a863cff916b648b2e9f0`

**Authoritative layout SHA-256:** `e84db9aa7b88db442f042c6f546196e350c822a2e7609cb4b652b3da535df2e1`

**CAD generator SHA-256:** `2645ea95e02b75c6456d8f9d3095fd39fcb5e9bad5f5d8bcae6ab403781df4e8`

The release validator independently checks the RC03 master/slave cassette architecture, four blind locator features, nine M4 retention features, nominal exact-solid fit, six direct-applied tags, board-coordinate outputs, printable meshes, QIDI plate manifests, sidecars, per-job human settings, importable QIDI process profiles, resolved preset contracts, source/profile/plate hashes, and protected Plus4 envelopes.

- Printable STL models: **32**
- STEP models/assemblies: **34**
- Controlled print jobs: **24**
- Controlled BOM lines: **53**
- Named M4 fastener stacks: **9**
- Nominal exact-solid fit checks: **26**
- Robot planar reach screening points: **5** (screening only; IK/collision proof remains blocked)
- Arm-camera alignment requirements: **11** (engineering hold; exact specification absent)
- Traceable hardware candidates: **23** across **37** resolved sources (all unverified)
- Total placed 3MF objects: **49**
- Named board features: **13** (4 locator + 9 retention)
- Direct-applied runtime tags: **6**

## QIDI Plus4 plate read-back

| Job | Plate | Objects | Envelope mm | Profile |
|---|---|---:|---:|---|
| 00A | `00A_ABS_keyboard_station_fit_tests.3mf` | 4 | 246.0 x 122.0 x 11.0 | `abs_rapido_tray_structural_0p4` |
| 00B | `00B_ABS_phone_station_fit_tests.3mf` | 6 | 256.0 x 172.0 x 16.6 | `abs_rapido_cradle_0p4` |
| 00C | `00C_ABS_tool_profile_fit_tests.3mf` | 4 | 156.0 x 70.0 x 34.0 | `abs_rapido_precision_0p4` |
| 00D | `00D_PETG_adapter_profile_fit_tests.3mf` | 1 | 92.0 x 28.0 x 4.0 | `petg_adapter_0p4` |
| 00E | `00E_ABS_general_setup_tests.3mf` | 3 | 208.0 x 124.0 x 14.0 | `abs_rapido_general_0p4` |
| 00F | `00F_ABS_calibration_profile_clearance_test.3mf` | 2 | 160.0 x 70.0 x 6.6 | `abs_rapido_calibration_0p4` |
| 01 | `01_ABS_keyboard_station_left.3mf` | 1 | 184.5 x 192.0 x 7.0 | `abs_rapido_tray_structural_0p4` |
| 02 | `02_ABS_keyboard_station_right.3mf` | 1 | 162.5 x 192.0 x 7.0 | `abs_rapido_tray_structural_0p4` |
| 03A | `03A_ABS_phone_TCP_station.3mf` | 1 | 186.3 x 172.8 x 10.5 | `abs_rapido_cradle_0p4` |
| 03B | `03B_ABS_keyboard_clamps.3mf` | 2 | 112.0 x 32.0 x 17.0 | `abs_rapido_general_0p4` |
| 03C1 | `03C1_ABS_phone_clamp_rail.3mf` | 1 | 19.2 x 172.8 x 16.0 | `abs_rapido_cradle_0p4` |
| 03C2 | `03C2_ABS_board_setup_tools.3mf` | 1 | 75.0 x 75.0 x 2.4 | `abs_rapido_general_0p4` |
| 03C3 | `03C3_PETG_camera_plate.3mf` | 1 | 90.0 x 55.0 x 6.0 | `petg_general_0p4` |
| 03D | `03D_ABS_TCP_datum_cartridges.3mf` | 2 | 72.0 x 30.0 x 4.0 | `abs_rapido_calibration_0p4` |
| 04A | `04A_ABS_shared_compliant_tool.3mf` | 3 | 100.0 x 24.0 x 66.2 | `abs_rapido_precision_0p4` |
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

This PASS proves package consistency, not physical fit. Printing remains locked by PRINT_READINESS until the exact board, devices, hardware, filament lots, locator coupons, QIDI Studio projects, first articles, tag placement, flatness, and ten-cycle repeatability gates are measured and recorded.

Re-run `python scripts/validate_release_package.py` after every CAD, layout, profile, job, plate, drawing, fiducial-map, or evidence-schema change.

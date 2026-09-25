# Step 07 — Print Settings for This Step

**Generated control — do not edit. The linked canonical files and their hashes define the print setup.**

## Traceability only — do not print here

The jobs below identify the accepted Step-00 parts consumed by this assembly step. Do not print the convenience STL copies during assembly. A failed or missing part returns to Step 00 and its controlled job workflow.

| Job | Authority | Material | Preset status | Plate | Exact readable settings | Machine sidecar | QIDI process import | Traveler |
|---|---|---|---|---|---|---|---|---|
| `00B` | **READY** | QIDI ABS Rapido | `EXACT_REPRODUCIBLE` | [00B_ABS_phone_station_fit_tests.3mf](<../../print_plates_3mf/00B_ABS_phone_station_fit_tests.3mf>) | [00B_ABS_phone_station_fit_tests.PRINT_SETTINGS.md](<../../print_plates_3mf/00B_ABS_phone_station_fit_tests.PRINT_SETTINGS.md>) | [00B_ABS_phone_station_fit_tests.print.json](<../../print_plates_3mf/00B_ABS_phone_station_fit_tests.print.json>) | [abs_rapido_cradle_0p4.process.json](<../../slicer_profiles/QIDI_PLUS4/abs_rapido_cradle_0p4.process.json>) | [JOB-00B.md](<../../job_cards/JOB-00B.md>) |
| `00F` | **READY** | QIDI ABS Rapido | `EXACT_REPRODUCIBLE` | [00F_ABS_calibration_profile_clearance_test.3mf](<../../print_plates_3mf/00F_ABS_calibration_profile_clearance_test.3mf>) | [00F_ABS_calibration_profile_clearance_test.PRINT_SETTINGS.md](<../../print_plates_3mf/00F_ABS_calibration_profile_clearance_test.PRINT_SETTINGS.md>) | [00F_ABS_calibration_profile_clearance_test.print.json](<../../print_plates_3mf/00F_ABS_calibration_profile_clearance_test.print.json>) | [abs_rapido_calibration_0p4.process.json](<../../slicer_profiles/QIDI_PLUS4/abs_rapido_calibration_0p4.process.json>) | [JOB-00F.md](<../../job_cards/JOB-00F.md>) |
| `03A` | **WAITING** | QIDI ABS Rapido | `EXACT_REPRODUCIBLE` | [03A_ABS_phone_TCP_station.3mf](<../../print_plates_3mf/03A_ABS_phone_TCP_station.3mf>) | [03A_ABS_phone_TCP_station.PRINT_SETTINGS.md](<../../print_plates_3mf/03A_ABS_phone_TCP_station.PRINT_SETTINGS.md>) | [03A_ABS_phone_TCP_station.print.json](<../../print_plates_3mf/03A_ABS_phone_TCP_station.print.json>) | [abs_rapido_cradle_0p4.process.json](<../../slicer_profiles/QIDI_PLUS4/abs_rapido_cradle_0p4.process.json>) | [JOB-03A.md](<../../job_cards/JOB-03A.md>) |
| `03C1` | **WAITING** | QIDI ABS Rapido | `EXACT_REPRODUCIBLE` | [03C1_ABS_phone_clamp_rail.3mf](<../../print_plates_3mf/03C1_ABS_phone_clamp_rail.3mf>) | [03C1_ABS_phone_clamp_rail.PRINT_SETTINGS.md](<../../print_plates_3mf/03C1_ABS_phone_clamp_rail.PRINT_SETTINGS.md>) | [03C1_ABS_phone_clamp_rail.print.json](<../../print_plates_3mf/03C1_ABS_phone_clamp_rail.print.json>) | [abs_rapido_cradle_0p4.process.json](<../../slicer_profiles/QIDI_PLUS4/abs_rapido_cradle_0p4.process.json>) | [JOB-03C1.md](<../../job_cards/JOB-03C1.md>) |
| `03D` | **WAITING** | QIDI ABS Rapido | `EXACT_REPRODUCIBLE` | [03D_ABS_TCP_datum_cartridges.3mf](<../../print_plates_3mf/03D_ABS_TCP_datum_cartridges.3mf>) | [03D_ABS_TCP_datum_cartridges.PRINT_SETTINGS.md](<../../print_plates_3mf/03D_ABS_TCP_datum_cartridges.PRINT_SETTINGS.md>) | [03D_ABS_TCP_datum_cartridges.print.json](<../../print_plates_3mf/03D_ABS_TCP_datum_cartridges.print.json>) | [abs_rapido_calibration_0p4.process.json](<../../slicer_profiles/QIDI_PLUS4/abs_rapido_calibration_0p4.process.json>) | [JOB-03D.md](<../../job_cards/JOB-03D.md>) |

## Material rules

- QIDI ABS Rapido jobs use the confirmed `QIDI ABS Rapido @Qidi X-Plus 4 0.4 nozzle` filament preset and the exact job-specific imported process profile.
- PETG, TPU 95A, and ASA settings sheets intentionally show `EXACT_SPOOL_PRESET_REQUIRED` until the exact physical spool, drying record, calibrated flow, pressure advance, temperature, cooling, and volumetric limits are recorded. Do not guess these values.
- Never compensate for ABS shrink or a failed fit by globally scaling an STL. Measure the matching coupon, update the controlled CAD parameter if required, regenerate, and revalidate.
- The process JSON controls process settings only. The filament preset remains a separate QIDI Studio selection.

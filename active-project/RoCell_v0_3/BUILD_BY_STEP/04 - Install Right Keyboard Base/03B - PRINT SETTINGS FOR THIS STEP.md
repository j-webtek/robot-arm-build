# Step 04 — Print Settings for This Step

**Generated control — do not edit. The linked canonical files and their hashes define the print setup.**

## Traceability only — do not print here

The jobs below identify the accepted Step-00 parts consumed by this assembly step. Do not print the convenience STL copies during assembly. A failed or missing part returns to Step 00 and its controlled job workflow.

| Job | Authority | Material | Preset status | Plate | Exact readable settings | Machine sidecar | QIDI process import | Traveler |
|---|---|---|---|---|---|---|---|---|
| `00A` | **READY** | QIDI ABS Rapido | `EXACT_REPRODUCIBLE` | [00A_ABS_keyboard_station_fit_tests.3mf](<../../print_plates_3mf/00A_ABS_keyboard_station_fit_tests.3mf>) | [00A_ABS_keyboard_station_fit_tests.PRINT_SETTINGS.md](<../../print_plates_3mf/00A_ABS_keyboard_station_fit_tests.PRINT_SETTINGS.md>) | [00A_ABS_keyboard_station_fit_tests.print.json](<../../print_plates_3mf/00A_ABS_keyboard_station_fit_tests.print.json>) | [abs_rapido_tray_structural_0p4.process.json](<../../slicer_profiles/QIDI_PLUS4/abs_rapido_tray_structural_0p4.process.json>) | [JOB-00A.md](<../../job_cards/JOB-00A.md>) |
| `01` | **WAITING** | QIDI ABS Rapido | `EXACT_REPRODUCIBLE` | [01_ABS_keyboard_station_left.3mf](<../../print_plates_3mf/01_ABS_keyboard_station_left.3mf>) | [01_ABS_keyboard_station_left.PRINT_SETTINGS.md](<../../print_plates_3mf/01_ABS_keyboard_station_left.PRINT_SETTINGS.md>) | [01_ABS_keyboard_station_left.print.json](<../../print_plates_3mf/01_ABS_keyboard_station_left.print.json>) | [abs_rapido_tray_structural_0p4.process.json](<../../slicer_profiles/QIDI_PLUS4/abs_rapido_tray_structural_0p4.process.json>) | [JOB-01.md](<../../job_cards/JOB-01.md>) |
| `02` | **WAITING** | QIDI ABS Rapido | `EXACT_REPRODUCIBLE` | [02_ABS_keyboard_station_right.3mf](<../../print_plates_3mf/02_ABS_keyboard_station_right.3mf>) | [02_ABS_keyboard_station_right.PRINT_SETTINGS.md](<../../print_plates_3mf/02_ABS_keyboard_station_right.PRINT_SETTINGS.md>) | [02_ABS_keyboard_station_right.print.json](<../../print_plates_3mf/02_ABS_keyboard_station_right.print.json>) | [abs_rapido_tray_structural_0p4.process.json](<../../slicer_profiles/QIDI_PLUS4/abs_rapido_tray_structural_0p4.process.json>) | [JOB-02.md](<../../job_cards/JOB-02.md>) |
| `03B` | **WAITING** | QIDI ABS Rapido | `EXACT_REPRODUCIBLE` | [03B_ABS_keyboard_clamps.3mf](<../../print_plates_3mf/03B_ABS_keyboard_clamps.3mf>) | [03B_ABS_keyboard_clamps.PRINT_SETTINGS.md](<../../print_plates_3mf/03B_ABS_keyboard_clamps.PRINT_SETTINGS.md>) | [03B_ABS_keyboard_clamps.print.json](<../../print_plates_3mf/03B_ABS_keyboard_clamps.print.json>) | [abs_rapido_general_0p4.process.json](<../../slicer_profiles/QIDI_PLUS4/abs_rapido_general_0p4.process.json>) | [JOB-03B.md](<../../job_cards/JOB-03B.md>) |

## Material rules

- QIDI ABS Rapido jobs use the confirmed `QIDI ABS Rapido @Qidi X-Plus 4 0.4 nozzle` filament preset and the exact job-specific imported process profile.
- PETG, TPU 95A, and ASA settings sheets intentionally show `EXACT_SPOOL_PRESET_REQUIRED` until the exact physical spool, drying record, calibrated flow, pressure advance, temperature, cooling, and volumetric limits are recorded. Do not guess these values.
- Never compensate for ABS shrink or a failed fit by globally scaling an STL. Measure the matching coupon, update the controlled CAD parameter if required, regenerate, and revalidate.
- The process JSON controls process settings only. The filament preset remains a separate QIDI Studio selection.

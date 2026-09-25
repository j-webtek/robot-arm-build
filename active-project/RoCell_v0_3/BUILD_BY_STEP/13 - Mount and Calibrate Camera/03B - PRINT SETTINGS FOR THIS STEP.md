# Step 13 — Print Settings for This Step

**Generated control — do not edit. The linked canonical files and their hashes define the print setup.**

## Traceability only — do not print here

The jobs below identify the accepted Step-00 parts consumed by this assembly step. Do not print the convenience STL copies during assembly. A failed or missing part returns to Step 00 and its controlled job workflow.

| Job | Authority | Material | Preset status | Plate | Exact readable settings | Machine sidecar | QIDI process import | Traveler |
|---|---|---|---|---|---|---|---|---|
| `00E` | **READY** | QIDI ABS Rapido | `EXACT_REPRODUCIBLE` | [00E_ABS_general_setup_tests.3mf](<../../print_plates_3mf/00E_ABS_general_setup_tests.3mf>) | [00E_ABS_general_setup_tests.PRINT_SETTINGS.md](<../../print_plates_3mf/00E_ABS_general_setup_tests.PRINT_SETTINGS.md>) | [00E_ABS_general_setup_tests.print.json](<../../print_plates_3mf/00E_ABS_general_setup_tests.print.json>) | [abs_rapido_general_0p4.process.json](<../../slicer_profiles/QIDI_PLUS4/abs_rapido_general_0p4.process.json>) | [JOB-00E.md](<../../job_cards/JOB-00E.md>) |
| `03C3` | **NOT_SELECTED** | PETG | `EXACT_PROCESS_SPOOL_PRESET_REQUIRED` | [03C3_PETG_camera_plate.3mf](<../../print_plates_3mf/03C3_PETG_camera_plate.3mf>) | [03C3_PETG_camera_plate.PRINT_SETTINGS.md](<../../print_plates_3mf/03C3_PETG_camera_plate.PRINT_SETTINGS.md>) | [03C3_PETG_camera_plate.print.json](<../../print_plates_3mf/03C3_PETG_camera_plate.print.json>) | [petg_general_0p4.process.json](<../../slicer_profiles/QIDI_PLUS4/petg_general_0p4.process.json>) | [JOB-03C3.md](<../../job_cards/JOB-03C3.md>) |
| `06` | **NOT_SELECTED** | ASA | `EXACT_PROCESS_SPOOL_PRESET_REQUIRED` | [06_ASA_mast_fit_tests.3mf](<../../print_plates_3mf/06_ASA_mast_fit_tests.3mf>) | [06_ASA_mast_fit_tests.PRINT_SETTINGS.md](<../../print_plates_3mf/06_ASA_mast_fit_tests.PRINT_SETTINGS.md>) | [06_ASA_mast_fit_tests.print.json](<../../print_plates_3mf/06_ASA_mast_fit_tests.print.json>) | [asa_structural_0p4.process.json](<../../slicer_profiles/QIDI_PLUS4/asa_structural_0p4.process.json>) | [JOB-06.md](<../../job_cards/JOB-06.md>) |
| `07A` | **NOT_SELECTED** | ASA | `EXACT_PROCESS_SPOOL_PRESET_REQUIRED` | [07A_ASA_mast_foot_first_article.3mf](<../../print_plates_3mf/07A_ASA_mast_foot_first_article.3mf>) | [07A_ASA_mast_foot_first_article.PRINT_SETTINGS.md](<../../print_plates_3mf/07A_ASA_mast_foot_first_article.PRINT_SETTINGS.md>) | [07A_ASA_mast_foot_first_article.print.json](<../../print_plates_3mf/07A_ASA_mast_foot_first_article.print.json>) | [asa_structural_0p4.process.json](<../../slicer_profiles/QIDI_PLUS4/asa_structural_0p4.process.json>) | [JOB-07A.md](<../../job_cards/JOB-07A.md>) |
| `07B` | **NOT_SELECTED** | ASA | `EXACT_PROCESS_SPOOL_PRESET_REQUIRED` | [07B_ASA_mast_foot_second.3mf](<../../print_plates_3mf/07B_ASA_mast_foot_second.3mf>) | [07B_ASA_mast_foot_second.PRINT_SETTINGS.md](<../../print_plates_3mf/07B_ASA_mast_foot_second.PRINT_SETTINGS.md>) | [07B_ASA_mast_foot_second.print.json](<../../print_plates_3mf/07B_ASA_mast_foot_second.print.json>) | [asa_structural_0p4.process.json](<../../slicer_profiles/QIDI_PLUS4/asa_structural_0p4.process.json>) | [JOB-07B.md](<../../job_cards/JOB-07B.md>) |

## Material rules

- QIDI ABS Rapido jobs use the confirmed `QIDI ABS Rapido @Qidi X-Plus 4 0.4 nozzle` filament preset and the exact job-specific imported process profile.
- PETG, TPU 95A, and ASA settings sheets intentionally show `EXACT_SPOOL_PRESET_REQUIRED` until the exact physical spool, drying record, calibrated flow, pressure advance, temperature, cooling, and volumetric limits are recorded. Do not guess these values.
- Never compensate for ABS shrink or a failed fit by globally scaling an STL. Measure the matching coupon, update the controlled CAD parameter if required, regenerate, and revalidate.
- The process JSON controls process settings only. The filament preset remains a separate QIDI Studio selection.

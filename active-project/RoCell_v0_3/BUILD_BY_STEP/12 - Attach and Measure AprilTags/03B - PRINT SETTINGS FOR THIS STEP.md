# Step 12 — Print Settings for This Step

**Generated control — do not edit. The linked canonical files and their hashes define the print setup.**

## Traceability only — do not print here

The jobs below identify the accepted Step-00 parts consumed by this assembly step. Do not print the convenience STL copies during assembly. A failed or missing part returns to Step 00 and its controlled job workflow.

| Job | Authority | Material | Preset status | Plate | Exact readable settings | Machine sidecar | QIDI process import | Traveler |
|---|---|---|---|---|---|---|---|---|
| `03C2` | **WAITING** | QIDI ABS Rapido | `EXACT_REPRODUCIBLE` | [03C2_ABS_board_setup_tools.3mf](<../../print_plates_3mf/03C2_ABS_board_setup_tools.3mf>) | [03C2_ABS_board_setup_tools.PRINT_SETTINGS.md](<../../print_plates_3mf/03C2_ABS_board_setup_tools.PRINT_SETTINGS.md>) | [03C2_ABS_board_setup_tools.print.json](<../../print_plates_3mf/03C2_ABS_board_setup_tools.print.json>) | [abs_rapido_general_0p4.process.json](<../../slicer_profiles/QIDI_PLUS4/abs_rapido_general_0p4.process.json>) | [JOB-03C2.md](<../../job_cards/JOB-03C2.md>) |

## Material rules

- QIDI ABS Rapido jobs use the confirmed `QIDI ABS Rapido @Qidi X-Plus 4 0.4 nozzle` filament preset and the exact job-specific imported process profile.
- PETG, TPU 95A, and ASA settings sheets intentionally show `EXACT_SPOOL_PRESET_REQUIRED` until the exact physical spool, drying record, calibrated flow, pressure advance, temperature, cooling, and volumetric limits are recorded. Do not guess these values.
- Never compensate for ABS shrink or a failed fit by globally scaling an STL. Measure the matching coupon, update the controlled CAD parameter if required, regenerate, and revalidate.
- The process JSON controls process settings only. The filament preset remains a separate QIDI Studio selection.

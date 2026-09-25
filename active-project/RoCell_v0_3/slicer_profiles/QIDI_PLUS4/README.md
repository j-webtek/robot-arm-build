# RoCell QIDI Plus4 process presets

These JSON files are importable **process** presets for QIDI Studio. They do not replace the filament preset.

1. In QIDI Studio, select `X-Plus 4 0.4 nozzle` and `Textured PEI Plate`.
2. Import the process JSON named by the job's `.PRINT_SETTINGS.md` file.
3. Select the exact filament preset named in that settings file. For QIDI ABS Rapido this is the confirmed system preset. PETG, TPU, and ASA remain blocked until the exact physical spool preset is identified and calibrated.
4. Import the geometry-only 3MF at 100 percent, preserve its orientation and placement, inspect every layer, and save a native QIDI Studio project.
5. Print only when `PRINT_READINESS.md` marks that job `READY`.

| Profile ID | Import name | Base preset | Data status | File |
|---|---|---|---|---|
| `abs_rapido_calibration_0p4` | `RC03 ABS Rapido Calibration 0.16` | `0.16mm High Quality @XPlus4` | `EXACT_REPRODUCIBLE` | `abs_rapido_calibration_0p4.process.json` |
| `abs_rapido_cradle_0p4` | `RC03 ABS Rapido Cradle 0.20` | `0.20mm Standard @XPlus4` | `EXACT_REPRODUCIBLE` | `abs_rapido_cradle_0p4.process.json` |
| `abs_rapido_general_0p4` | `RC03 ABS Rapido General 0.20` | `0.20mm Standard @XPlus4` | `EXACT_REPRODUCIBLE` | `abs_rapido_general_0p4.process.json` |
| `abs_rapido_precision_0p4` | `RC03 ABS Rapido Precision 0.16` | `0.16mm High Quality @XPlus4` | `EXACT_REPRODUCIBLE` | `abs_rapido_precision_0p4.process.json` |
| `abs_rapido_tray_structural_0p4` | `RC03 ABS Rapido Tray Structural 0.20` | `0.20mm Standard @XPlus4` | `EXACT_REPRODUCIBLE` | `abs_rapido_tray_structural_0p4.process.json` |
| `asa_structural_0p4` | `RC03 ASA Mast Structural 0.24` | `0.24mm Draft @XPlus4` | `EXACT_PROCESS_SPOOL_PRESET_REQUIRED` | `asa_structural_0p4.process.json` |
| `petg_adapter_0p4` | `RC03 PETG Split Adapter 0.12` | `0.12mm High Quality @XPlus4` | `EXACT_PROCESS_SPOOL_PRESET_REQUIRED` | `petg_adapter_0p4.process.json` |
| `petg_general_0p4` | `RC03 PETG General 0.20` | `0.20mm Standard @XPlus4` | `EXACT_PROCESS_SPOOL_PRESET_REQUIRED` | `petg_general_0p4.process.json` |
| `tpu95a_0p4` | `RC03 TPU 95A Contact Tips 0.16` | `0.16mm High Quality @XPlus4` | `EXACT_PROCESS_SPOOL_PRESET_REQUIRED` | `tpu95a_0p4.process.json` |

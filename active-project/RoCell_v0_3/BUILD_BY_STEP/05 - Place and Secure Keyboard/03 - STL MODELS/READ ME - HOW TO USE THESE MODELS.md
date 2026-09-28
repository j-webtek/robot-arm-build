# STL files for this step

Step 00 uses a governed mix of small generated convenience copies and hash-bound links to the authoritative project-level `stl/` files. Steps 01–15 use only hash-bound links and intentionally contain no duplicate STL bytes.

## Rules

- Print only when the step and job card explicitly say to print. Assembly Steps 01-15 normally consume parts already accepted in Step 00.
- Never globally scale or auto-repair a production STL without reopening the measurement, regeneration, and validation workflow.
- A file marked `DO_NOT_PRINT` is a visualization/reference body only.
- Compare against `STL MODEL LIST.csv`; any hash mismatch is a STOP.
- Return to Step 00 and its qualified ready-job workflow if an accepted part is missing.

| STL | Usage | Job reference | SHA-256 |
| --- | --- | --- | --- |
| [keyboard_rear_clamp.stl](<../../../stl/keyboard_rear_clamp.stl>) | **TRACEABILITY_ONLY_DO_NOT_PRINT** | 03B | `78c591895ae8392a5af9832f56cb7f15cb6a401c490153a1914b71ff5bcba373` |
| [keyboard_station_left.stl](<../../../stl/keyboard_station_left.stl>) | **TRACEABILITY_ONLY_DO_NOT_PRINT** | 01 | `a19b4288b9d6c3fae66f3baa3aa7726fc4acaa440bdb3f16ad3a7ea7791e9a1f` |
| [keyboard_station_right.stl](<../../../stl/keyboard_station_right.stl>) | **TRACEABILITY_ONLY_DO_NOT_PRINT** | 02 | `bc9cc0d252da8d1702c56bbd0afaf6ed79e5dd9891d121dd54372e4692675cf0` |

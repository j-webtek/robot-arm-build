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
| [tag_application_frame_55mm.stl](<../../../stl/tag_application_frame_55mm.stl>) | **TRACEABILITY_ONLY_DO_NOT_PRINT** | 03C2 | `492f7e3c567a7aa3a4bc255d59425f73dc0c64ab240df8af8f9adf861d53a10f` |

# RoCell v0.3 - integrated QIDI Plus4 build package

**Controlled revision:** `RC03-INT-R1`

Start with `BUILD_BY_STEP/00 - START HERE.md`, then follow `01 - COMPLETE BUILD ORDER.md`. Step 00 measures hardware, qualifies printing, produces only approved jobs, and organizes accepted parts; Steps 01-15 match the illustrated assembly sequence. Every step uses the same plain-language order: `00 - START HERE`, `01 - BEFORE YOU START`, `02 - PARTS AND TOOLS CHECKLIST`, `03 - STL MODELS`, `04 - STEP-BY-STEP INSTRUCTIONS`, `05 - CHECK YOUR WORK`, `06 - SAVE MEASUREMENTS AND PHOTOS`, and `07 - FINISH THIS STEP AND CONTINUE`. Machine manifests and hashes are separated under `99 - TECHNICAL RECORDS - DO NOT EDIT`. Select one active physical build with `scripts/set_active_build.py`, regenerate, then initialize each ready step once with `scripts/initialize_step_evidence.py`; only that build ID can affect computed step states. Canonical STL basenames remain unchanged for job-card compatibility. Use `output/pdf/RC03_ILLUSTRATED_ASSEMBLY_GUIDE.pdf` for the visual sequence and `ASSEMBLY_MANUAL.pdf` for the complete engineering detail.

## What changed

- The build now uses three removable board-registered stations: keyboard left/master, keyboard right/slave, and phone/TCP service.
- The right keyboard station is located from the master seam and deliberately has no independent locator pins.
- Four 6 mm pins carry lateral station loads; nine M4 interfaces retain the three continuous station bases directly against the finished board.
- The phone nest and TCP receiver are integrated. The phone keeper/tower rail carries the cable saddle and remains replaceable, as does the TCP datum cartridge.
- Six AprilTags mount directly to the finished sealed board with full-surface matte adhesive. No printed tag holders or tag screws remain.
- Board fabrication uses a generated 1:1 paper template, printed guides, a hand drill, and depth stops. No router or CNC is required.
- The factory RoArm clamp remains load-bearing; a measured precut metal underside plate spreads its board load.
- QIDI ABS Rapido is now the primary rigid material for the 13 active diagnostic and production jobs. PETG remains only where split adapters need ductility (00D, 04B, and 04C) and for the inactive fixed-camera fallback plate 03C3; TPU 95A remains mandatory for jobs 05A-05D; ASA remains an inactive fixed-mast fallback material.
- Every plate has a machine-readable `.print.json` and a plain-language `.PRINT_SETTINGS.md` record. These resolve the exact process settings by job; PETG, TPU, and ASA thermal values remain deliberately unresolved until the exact physical spool is identified and calibrated.

## Package map

- `stl/` - validated printable parts for RC03.
- `print_plates_3mf/` - 24 modular, bed-centered QIDI Plus4 jobs with hashed `.print.json` preset sidecars and same-name `.PRINT_SETTINGS.md` operator guides.
- `config/print_jobs.json` - authoritative job contents, profiles, routes, and prerequisites.
- `config/print_profiles.json` - authoritative QIDI Studio machine, filament, process, speed, adhesion, cooling, and material-resolution contract for every job family.
- `config/measurement_record.json` - measurements, coupon selections, first articles, repeatability, direct-tag metrology, and safety gates.
- `config/job_build_record.json` - lifecycle evidence from unreleased through in-service.
- `config/v1_prehardware_configuration.json` - provisional V1 purchasing/scope decisions; every selected item remains physically unqualified.
- `config/hardware_candidates.json` - exact candidate MPNs, sources, quantities, and named qualification gates; candidates are not released substitutions.
- `config/digital_fit_report.json` - exact-solid nominal collision checks for stations, service parts, device envelopes, pins, and screw passages.
- `config/robot_reach_screening.json` - honest planar-only RoArm screening; it explicitly does not authorize reach or powered motion.
- `PREHARDWARE_READINESS.md` - one-page digital verdict and the engineering/physical holds that still prevent a build release.
- `RC03_INTEGRATED_BUILD_PLAN.md` - exact architecture, part changes, physical limits, and build sequence.
- `KEYBOARD_STATION_ENGINEERING_REVIEW.md` - master/slave load-path and tolerance review.
- `config/camera_architecture_decision.json` - controlling engineering hold for the intended arm-mounted camera; the existing paired mast is fallback-only until a formal revision aligns the complete camera system.
- `MANUFACTURING_REVIEW.md` - module risks and objective physical acceptance.
- `FASTENER_AND_PRINT_UX_GUIDE.md` - user-facing fastener, locator, insert, tag, and service guidance.
- `PRINT_ENHANCEMENT_PLAN.md` - per-job print and inspection plan.
- `JOB_CARDS.pdf` / `job_cards/` - one controlled traveler per job.
- `output/pdf/RC03_ILLUSTRATED_ASSEMBLY_GUIDE.pdf` - CAD-derived, ordered assembly illustrations with hardware stacks, STOP gates, acceptance limits, and commissioning signoff.
- `JOB_KITS.csv` - exact hardware, evidence, and storage mapping.
- `BUILD_TRACKER.md` - current lifecycle state and missing gates.
- `cad/step/` - neutral editable CAD, including board and assembly.
- `scripts/generate_cad.py` - parametric CadQuery source.
- `config/user_overrides.example.json` - measured overrides; copy to `config/user_overrides.json` before editing.
- `drawings/` - named board features, direct-tag placement geometry, coordinate CSVs, and 1:1 setup template.
- `fiducials/` - exact-size AprilTags, ChArUco calibration board, and revision/hash-stamped runtime map.
- `software_helpers/` - traceable camera capture, ChArUco calibration, and AprilTag detection helpers; Step 13 runs them from an isolated `.venv-vision` environment.
- `BOM.csv`, `FASTENER_MAP.csv`, `PRINT_PLAN.csv`, and `PLATE_MANIFEST.csv` - controlled purchasing, per-interface hardware selection, and manufacturing data.
- `PART_VALIDATION.csv` and `RELEASE_VALIDATION.json` - independent geometry/package checks.
- `outputs/` - the rendered print-compatibility workbook with route, gate, queue, profile, part, board, kit, and lifecycle views.
- `BUILD_BY_STEP/` - generated Step 00 plus Steps 01-15 operator work packages. Controlled source files stay canonical; only `ACTIVE_BUILD.json` (through its selector) and each step's `06 - SAVE MEASUREMENTS AND PHOTOS/` area are writable.

## Critical first steps

1. Confirm the installed nozzle is 0.4 mm and physically verify the provisional 295 x 295 x 275 mm protected envelope. For the primary rigid jobs, select `QIDI ABS Rapido @Qidi X-Plus 4 0.4 nozzle` and the exact job process named in its `.PRINT_SETTINGS.md`; do not substitute a generic ABS preset.
2. Measure the keyboard, phone/case, cable, pins, nuts, inserts, screws, washers, board, arm clamp, camera, gripper, spring, and selected tool-route hardware.
3. Print the QIDI ABS Rapido diagnostic jobs 00A, 00B, 00C, 00E, and 00F. Print PETG job 00D only when `phone_stylus_route` is selected and only after its exact PETG spool preset is recorded. Job 00A qualifies keyboard-station locators, clearances, and washer seats; Job 00B qualifies phone width, service-station locators, M3 inserts, and washer seats. Its failed nut/tie screening features are superseded.
4. Print the small Job 03C1 rail before Job 03A. Use that production-equivalent rail to qualify both redesigned M4 nut seats and the adopted wider tie around the actual USB cable; no replacement standalone nut/tie coupon is required.
5. Record canonical compatibility gates with `scripts/record_print_measurement.py`; record each step test with `scripts/record_step_result.py`; sign a completed step with `scripts/sign_off_step.py`. These helpers validate paths and state transitions, so raw evidence JSON should only be edited for controlled recovery.
6. Run `python scripts/validate_print_readiness.py`. Print only selected jobs marked **READY**.
7. Accept the keyboard master before the slave, and accept all large stations before drilling the final board.
8. Purchase/cut the 610 x 457 x 18 mm board, seal both faces equally, and allow full cure.
9. Print the board setup template at **Actual Size / 100%** and verify both 100 mm scale bars.
10. Dry-fit all pins, threaded interfaces, and stations before epoxy.
11. Apply/measure direct tags, resolve the camera-architecture hold, complete the route-specific calibration and ten-cycle repeatability checks, then run empty-cell motion checks before device contact.

Digital geometry validation does not prove fit to the physical printer output or actual hardware. The profile-specific coupons and physical gates are mandatory.

## Regenerate and verify

Run from this directory after changing measured overrides or source:

```text
python -m pip install -r requirements-cad.txt
python scripts/generate_cad.py
python scripts/generate_fiducials.py
python scripts/generate_drawings.py
python scripts/sync_documentation.py
python scripts/build_print_plates.py
python scripts/generate_prehardware_readiness.py
python scripts/validate_print_readiness.py
python scripts/generate_build_tracker.py
python scripts/generate_job_cards.py
python scripts/render_previews.py
python scripts/render_assembly_guide.py
python scripts/build_illustrated_assembly_guide.py
python scripts/build_manual_pdf.py
python scripts/build_manual_pdf.py --source JOB_CARDS.md --output JOB_CARDS.pdf --running-title "RoCell RC03-INT-R1 - Job Cards"
python scripts/validate_release_package.py
python scripts/sync_documentation.py --check
python scripts/build_step_packages.py
python scripts/build_step_packages.py --check
python scripts/update_checksums.py
```

Generation rejects disconnected, non-watertight, non-positive-volume, oversized, overlapping, incorrectly counted, stale-revision, coordinate-inconsistent, or manifest-mismatched parts and artifacts. Readiness remains conservative: a geometry-only 3MF is not a released QIDI Studio machine project.

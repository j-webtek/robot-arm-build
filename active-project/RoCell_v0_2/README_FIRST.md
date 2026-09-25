# RoCell v0.2 - print-ready CAD package

Start with **PRINT_READINESS.md**, then **ASSEMBLY_MANUAL.pdf**.

## What is in the package

- `stl/` - one STL per validated printable part.
- `print_plates_3mf/` - 24 modular, bed-centered QIDI Plus4 jobs. Every 3MF has a matching hashed `.print.json` settings and prerequisite sidecar.
- `PLATE_MANIFEST.csv` - material, process profile, object count, and envelope for every 3MF.
- `PRINT_READINESS.md` / `.json` - generated READY, WAITING, and NOT_SELECTED queue.
- `KEYBOARD_TRAY_ENGINEERING_REVIEW.md` - load-path, seam-fit, and acceptance review for the first two production parts.
- `MANUFACTURING_REVIEW.md` - module-by-module printability, fit, and build-risk review.
- `FASTENER_AND_PRINT_UX_GUIDE.md` - part-by-part washer, insert, orientation, and tightening guidance.
- `PRINT_ENHANCEMENT_PLAN.md` - exact improvements, critical dimensions, inspections, and release gates for all 37 printable STLs.
- `JOB_CARDS.pdf` / `job_cards/` - one controlled manufacturing traveler for every print job.
- `BUILD_TRACKER.md` / `config/job_build_record.json` - lifecycle state from unreleased through in-service.
- `JOB_KITS.csv` - exact kit, hardware, evidence, and storage mapping for every job.
- `outputs/01a0541f-aa79-78e1-8989-27e82ebc1acf/PRINT_COMPATIBILITY_WORKBOOK.xlsx` - human-readable measurement, gate, route, profile, and part map.
- `stl_large_printer_optional/` - a 325 mm one-piece keyboard tray reference; it does **not** fit the 305 mm Plus4 bed.
- `cad/step/` - editable neutral CAD files, including the complete assembly and structural board.
- `scripts/generate_cad.py` - parametric CadQuery source.
- `config/user_overrides.example.json` - copy to `config/user_overrides.json`, change measured dimensions, then regenerate.
- `config/print_profiles.json` - Plus4 safe envelope and recommended 0.4/0.6 mm material-process classes.
- `config/print_jobs.json` - authoritative job contents, profiles, routes, and prerequisites.
- `config/measurement_record.json` - authoritative physical measurements and coupon results.
- `drawings/` - board DXF, SVG, coordinate CSV, and a 1:1 tiled letter-size drill template.
- `fiducials/` - exact-size AprilTag runtime markers and a ChArUco camera-calibration board.
- `software_helpers/` - starter OpenCV scripts for camera calibration and AprilTag detection.
- `BOM.csv` - shopping list. `PRINT_PLAN.csv` is regenerated from the same authoritative job/profile data as the plates.
- `PART_VALIDATION.csv` - mesh and printer-envelope validation.
- `RELEASE_VALIDATION.json` - independent mesh, 3MF read-back, hash, job, profile, and board-layout validation.

## Critical first steps

1. Do **not** print the structural board. Cut one 610 x 457 x 18 mm plywood/MDF panel.
2. Confirm the installed nozzle is 0.4 mm and calibrate the exact PETG spool.
3. Print diagnostic jobs `00A` through `00F`; each coupon uses the exact tray, cradle, tool, adapter, general, or puck profile it releases.
4. Measure the actual phone/case and side features, keyboard, RoArm gripper, spring, fasteners, and inserts; record results with `scripts/record_print_measurement.py`.
5. Run `python scripts/validate_print_readiness.py` and print only jobs marked **READY**.
6. Print the board template at **Actual Size / 100%** and verify its 100 mm scale bar.
7. Bring up and stop the RoArm safely before placing the phone or keyboard in reach.

The CAD has been checked for watertight single-body STL meshes against both the Plus4 nominal 305 x 305 x 280 mm volume and a conservative 295 x 295 x 280 mm packing envelope. It has not been physically fitted to your exact printer output, phone case, keyboard manufacturing tolerances, extrusion, or arm, so the supplied fit coupons are mandatory before committing to the large prints.

## Regenerate and verify the package

Run these commands from this directory after changing `config/user_overrides.json` or the CAD source:

```text
python -m pip install -r requirements-cad.txt
python scripts/generate_cad.py
python scripts/build_print_plates.py
python scripts/validate_print_readiness.py
python scripts/generate_build_tracker.py
python scripts/generate_job_cards.py
python scripts/validate_release_package.py
python scripts/generate_drawings.py
python scripts/render_previews.py
python scripts/build_manual_pdf.py
python scripts/build_manual_pdf.py --source JOB_CARDS.md --output JOB_CARDS.pdf --running-title "RoCell RC02-PRO-R1 - Job Cards"
python scripts/update_checksums.py
```

Generation rejects non-watertight, non-positive-volume, disconnected, oversized, overlapping, incorrectly counted, or manifest-mismatched parts and plates. Readiness validation then prevents a selected production job from becoming READY until its physical measurements and coupon gates are recorded as PASS. The PDF builder uses WeasyPrint where its native libraries are available and falls back to Microsoft Edge or Google Chrome on Windows.

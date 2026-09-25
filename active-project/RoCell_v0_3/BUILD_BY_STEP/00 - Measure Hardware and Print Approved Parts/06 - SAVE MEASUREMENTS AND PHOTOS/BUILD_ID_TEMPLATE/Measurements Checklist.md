# Step 00 — Measurements Checklist

Use the copy inside your active build-ID folder as a work aid; never edit this generated template.

Record authoritative results with `scripts/record_step_result.py`; it safely updates `measurement_record.json`. Raw JSON editing is an advanced recovery fallback only.

Every `--evidence` path must be relative to the build-ID folder, remain contained within that folder, and point to an existing regular file. Neither `measurement_record.json` nor `signoff.json` is physical evidence. Repeat `--evidence` when one test has multiple files.

Command form:

`python scripts/record_step_result.py --step 00 --test TEST_ID --value "VALUE_OR_OBSERVATION" --unit "UNIT_OR_NA" --instrument "TOOL_ID_OR_METHOD" --evidence "photos/EXISTING_FILE.jpg" --result PASS --operator "OPERATOR_NAME"`

## 00-A — Every selected job is READY before print

- Method: Run validate_print_readiness.py and retain PRINT_READINESS.json
- Pass limit: No selected job may be WAITING
- Required evidence: Readiness report plus native QIDI project records
- Required record: value or observation
- Required record: unit and instrument ID
- Required record: original evidence file path
- Required record: PASS or FAIL result

## 00-B — All required fits use the matching production profile or production-equivalent first article

- Method: Check the actual hardware in its controlled diagnostic or Job 03C1 production interface
- Pass limit: Every required coupon gate is PASS and every selected value is regenerated into CAD
- Required evidence: Raw observations, photos, selected values, and first-article identity
- Required record: value or observation
- Required record: unit and instrument ID
- Required record: original evidence file path
- Required record: PASS or FAIL result

## 00-C — Printed parts are accepted and kitted

- Method: Count, inspect, label, and reconcile against JOB_KITS.csv
- Pass limit: No missing required part, spare, or traceability record
- Required evidence: Signed job cards and kit photos
- Required record: value or observation
- Required record: unit and instrument ID
- Required record: original evidence file path
- Required record: PASS or FAIL result

## 00-D — One named board drill guide is printed at verified 1:1 scale and remains traceable

- Method: Print either the nine Letter drilling tiles or the single 24 x 36 inch guide at Actual Size / 100 percent; measure the independent X and Y 100 mm controls on every physical drilling sheet; verify every matching tiled registration mark or the full-size board-edge/orientation controls; record the selected path plus guide and source-layout SHA-256 values
- Pass limit: Every X and Y control is 100.0 +/- 0.2 mm, all applicable registration/edge controls agree, and the recorded path and hashes match the exact files used; this scale check alone does not release hole positions
- Required evidence: Ruler photos for every drilling sheet, registration/edge photos, selected guide path, print settings, revision, guide SHA-256, and source-layout SHA-256
- Required record: value or observation
- Required record: unit and instrument ID
- Required record: original evidence file path
- Required record: PASS or FAIL result


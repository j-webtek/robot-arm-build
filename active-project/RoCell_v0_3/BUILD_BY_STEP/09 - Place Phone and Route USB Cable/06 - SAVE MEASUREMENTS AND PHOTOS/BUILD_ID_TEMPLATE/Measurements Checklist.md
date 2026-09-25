# Step 09 — Measurements Checklist

Use the copy inside your active build-ID folder as a work aid; never edit this generated template.

Record authoritative results with `scripts/record_step_result.py`; it safely updates `measurement_record.json`. Raw JSON editing is an advanced recovery fallback only.

Every `--evidence` path must be relative to the build-ID folder, remain contained within that folder, and point to an existing regular file. Neither `measurement_record.json` nor `signoff.json` is physical evidence. Repeat `--evidence` when one test has multiple files.

Command form:

`python scripts/record_step_result.py --step 09 --test TEST_ID --value "VALUE_OR_OBSERVATION" --unit "UNIT_OR_NA" --instrument "TOOL_ID_OR_METHOD" --evidence "photos/EXISTING_FILE.jpg" --result PASS --operator "OPERATOR_NAME"`

## 09-A — Phone device pose

- Method: Measure against the recorded station reference
- Pass limit: No more than 0.35 mm from the accepted reference
- Required evidence: Ten-cycle pose results
- Required record: value or observation
- Required record: unit and instrument ID
- Required record: original evidence file path
- Required record: PASS or FAIL result

## 09-B — Cable strain relief

- Method: Inspect connected phone through ten cycles
- Pass limit: No connector load, kink, saddle crack, or violated bend radius
- Required evidence: Side photos and cycle log
- Required record: value or observation
- Required record: unit and instrument ID
- Required record: original evidence file path
- Required record: PASS or FAIL result

## 09-C — TPU retention

- Method: Force-gauge pull to the engineering-approved proof load/duration plus ten load cycles
- Pass limit: Approved force and duration are achieved; tips remain retained and undamaged
- Required evidence: Approval ID, gauge ID, measured load/duration, cycle result, and witness photos
- Required record: value or observation
- Required record: unit and instrument ID
- Required record: original evidence file path
- Required record: PASS or FAIL result


# Step 06 — Measurements Checklist

Use the copy inside your active build-ID folder as a work aid; never edit this generated template.

Record authoritative results with `scripts/record_step_result.py`; it safely updates `measurement_record.json`. Raw JSON editing is an advanced recovery fallback only.

Every `--evidence` path must be relative to the build-ID folder, remain contained within that folder, and point to an existing regular file. Neither `measurement_record.json` nor `signoff.json` is physical evidence. Repeat `--evidence` when one test has multiple files.

Command form:

`python scripts/record_step_result.py --step 06 --test TEST_ID --value "VALUE_OR_OBSERVATION" --unit "UNIT_OR_NA" --instrument "TOOL_ID_OR_METHOD" --evidence "photos/EXISTING_FILE.jpg" --result PASS --operator "OPERATOR_NAME"`

## 06-A — Station locator fit

- Method: Tool-free install/remove cycle
- Pass limit: No more than 0.15 mm lateral play; no cracking or whitening
- Required evidence: Cycle count and play measurement
- Required record: value or observation
- Required record: unit and instrument ID
- Required record: original evidence file path
- Required record: PASS or FAIL result

## 06-B — Phone support plane

- Method: Straightedge and feelers
- Pass limit: No more than 0.30 mm variation
- Required evidence: Measured range
- Required record: value or observation
- Required record: unit and instrument ID
- Required record: original evidence file path
- Required record: PASS or FAIL result

## 06-C — TCP receiver seat

- Method: Straightedge/height comparison
- Pass limit: No more than 0.15 mm seat error
- Required evidence: Measured error
- Required record: value or observation
- Required record: unit and instrument ID
- Required record: original evidence file path
- Required record: PASS or FAIL result

## 06-D — PT-HOLD-TCP effective stack

- Method: Inspect washer recess and gauge the selected screw/anchor stack before torque
- Pass limit: Washer fully seated in 1.5 mm recess; 9.0 mm nominal effective printed stack; at least 5.0 mm useful thread engagement; no bottoming or underside projection; 0.25-0.35 N m
- Required evidence: Selected length, measured engagement, washer-seat photo, underside/interface photo, and final torque
- Required record: value or observation
- Required record: unit and instrument ID
- Required record: original evidence file path
- Required record: PASS or FAIL result


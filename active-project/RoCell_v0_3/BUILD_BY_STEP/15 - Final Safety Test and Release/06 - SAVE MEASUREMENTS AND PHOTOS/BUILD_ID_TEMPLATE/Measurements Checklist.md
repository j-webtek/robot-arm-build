# Step 15 — Measurements Checklist

Use the copy inside your active build-ID folder as a work aid; never edit this generated template.

Record authoritative results with `scripts/record_step_result.py`; it safely updates `measurement_record.json`. Raw JSON editing is an advanced recovery fallback only.

Every `--evidence` path must be relative to the build-ID folder, remain contained within that folder, and point to an existing regular file. Neither `measurement_record.json` nor `signoff.json` is physical evidence. Repeat `--evidence` when one test has multiple files.

Command form:

`python scripts/record_step_result.py --step 15 --test TEST_ID --value "VALUE_OR_OBSERVATION" --unit "UNIT_OR_NA" --instrument "TOOL_ID_OR_METHOD" --evidence "photos/EXISTING_FILE.jpg" --result PASS --operator "OPERATOR_NAME"`

## 15-A — Station reinstall repeatability

- Method: Ten remove/reinstall cycles per station
- Pass limit: X/Y no more than 0.25 mm; yaw no more than 0.20 degrees; Z no more than 0.20 mm
- Required evidence: Cycle table and worst values
- Required record: value or observation
- Required record: unit and instrument ID
- Required record: original evidence file path
- Required record: PASS or FAIL result

## 15-B — Structure and anchors

- Method: Apply 20 N lateral and 10 N functional station proofs for the recorded durations, plus 50 N axial at every board anchor for 60 seconds
- Pass limit: Every load/duration is achieved; permanent shift no more than 0.10 mm; no damage or rotation
- Required evidence: Force-tool ID, durations, before/after values, and photos
- Required record: value or observation
- Required record: unit and instrument ID
- Required record: original evidence file path
- Required record: PASS or FAIL result

## 15-C — Empty-cell motion

- Method: Run the full path at the engineering-approved TCP speed/acceleration with devices removed
- Pass limit: No collision and measured clearance never below the engineering-approved minimum
- Required evidence: Approval ID, actual mm/s and mm/s^2, motion log/video, cycle count, and clearance table
- Required record: value or observation
- Required record: unit and instrument ID
- Required record: original evidence file path
- Required record: PASS or FAIL result

## 15-D — Controlled first contact and final process

- Method: One device at a time at the engineering-approved first-contact TCP speed/force/travel with an observer at the E-stop
- Pass limit: All approved numeric limits respected; no device shift, hard stop, unintended input, or cable load
- Required evidence: Approval ID, actual mm/s, N and mm values, and signed commissioning record
- Required record: value or observation
- Required record: unit and instrument ID
- Required record: original evidence file path
- Required record: PASS or FAIL result


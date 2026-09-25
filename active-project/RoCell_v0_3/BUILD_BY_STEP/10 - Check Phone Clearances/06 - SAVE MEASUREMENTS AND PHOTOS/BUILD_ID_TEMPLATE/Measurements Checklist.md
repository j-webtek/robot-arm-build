# Step 10 — Measurements Checklist

Use the copy inside your active build-ID folder as a work aid; never edit this generated template.

Record authoritative results with `scripts/record_step_result.py`; it safely updates `measurement_record.json`. Raw JSON editing is an advanced recovery fallback only.

Every `--evidence` path must be relative to the build-ID folder, remain contained within that folder, and point to an existing regular file. Neither `measurement_record.json` nor `signoff.json` is physical evidence. Repeat `--evidence` when one test has multiple files.

Command form:

`python scripts/record_step_result.py --step 10 --test TEST_ID --value "VALUE_OR_OBSERVATION" --unit "UNIT_OR_NA" --instrument "TOOL_ID_OR_METHOD" --evidence "photos/EXISTING_FILE.jpg" --result PASS --operator "OPERATOR_NAME"`

## 10-A — Screen-edge clearance

- Method: Visual and measured tip position
- Pass limit: Both TPU contacts remain below/outside glass and bezel
- Required evidence: Front and side close photos
- Required record: value or observation
- Required record: unit and instrument ID
- Required record: original evidence file path
- Required record: PASS or FAIL result

## 10-B — Camera and button clearance

- Method: Measure closest approach and operate controls
- Pass limit: No contact or unintended input; measured margin minus uncertainty is at or above the engineering-approved minimum
- Required evidence: Approval ID, approved limit, uncertainty, minimum margins, and control test video/photo
- Required record: value or observation
- Required record: unit and instrument ID
- Required record: original evidence file path
- Required record: PASS or FAIL result

## 10-C — USB keepout

- Method: Inspect connector and bend under light cable disturbance
- Pass limit: No body contact, strain, kink, or bend-radius violation
- Required evidence: Connector and saddle photos
- Required record: value or observation
- Required record: unit and instrument ID
- Required record: original evidence file path
- Required record: PASS or FAIL result


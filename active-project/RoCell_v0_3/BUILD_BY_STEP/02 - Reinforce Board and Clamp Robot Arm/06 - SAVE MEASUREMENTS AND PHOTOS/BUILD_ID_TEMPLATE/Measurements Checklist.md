# Step 02 — Measurements Checklist

Use the copy inside your active build-ID folder as a work aid; never edit this generated template.

Record authoritative results with `scripts/record_step_result.py`; it safely updates `measurement_record.json`. Raw JSON editing is an advanced recovery fallback only.

Every `--evidence` path must be relative to the build-ID folder, remain contained within that folder, and point to an existing regular file. Neither `measurement_record.json` nor `signoff.json` is physical evidence. Repeat `--evidence` when one test has multiple files.

Command form:

`python scripts/record_step_result.py --step 02 --test TEST_ID --value "VALUE_OR_OBSERVATION" --unit "UNIT_OR_NA" --instrument "TOOL_ID_OR_METHOD" --evidence "photos/EXISTING_FILE.jpg" --result PASS --operator "OPERATOR_NAME"`

## 02-A — Board stays flat after clamping

- Method: Straightedge and feelers before and after clamp load
- Pass limit: No new local lift above the board acceptance limit
- Required evidence: Before/after measurements and underside photo
- Required record: value or observation
- Required record: unit and instrument ID
- Required record: original evidence file path
- Required record: PASS or FAIL result

## 02-B — Reinforcement clears all interfaces

- Method: Visual and tactile inspection from the underside
- Pass limit: No contact with anchors, feet, station hardware, or cable paths
- Required evidence: Underside overview photo
- Required record: value or observation
- Required record: unit and instrument ID
- Required record: original evidence file path
- Required record: PASS or FAIL result

## 02-C — Factory arm clamp is installed and stable

- Method: Record the clamp model/instructions and manufacturer-approved tightening setting, then perform static before/after mounting inspections without forcing or back-driving the arm
- Pass limit: Installation matches the clamp manufacturer; no clamp movement, board crushing, new bow, or permanent board shift
- Required evidence: Clamp model/instruction reference, tightening setting, and before/after reference measurements
- Required record: value or observation
- Required record: unit and instrument ID
- Required record: original evidence file path
- Required record: PASS or FAIL result


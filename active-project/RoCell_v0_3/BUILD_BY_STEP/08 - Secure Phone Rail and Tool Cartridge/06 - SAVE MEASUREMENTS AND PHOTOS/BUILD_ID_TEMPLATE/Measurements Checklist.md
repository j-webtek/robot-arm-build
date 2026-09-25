# Step 08 — Measurements Checklist

Use the copy inside your active build-ID folder as a work aid; never edit this generated template.

Record authoritative results with `scripts/record_step_result.py`; it safely updates `measurement_record.json`. Raw JSON editing is an advanced recovery fallback only.

Every `--evidence` path must be relative to the build-ID folder, remain contained within that folder, and point to an existing regular file. Neither `measurement_record.json` nor `signoff.json` is physical evidence. Repeat `--evidence` when one test has multiple files.

Command form:

`python scripts/record_step_result.py --step 08 --test TEST_ID --value "VALUE_OR_OBSERVATION" --unit "UNIT_OR_NA" --instrument "TOOL_ID_OR_METHOD" --evidence "photos/EXISTING_FILE.jpg" --result PASS --operator "OPERATOR_NAME"`

## 08-A — All three station retainers

- Method: Torque and stack inspection
- Pass limit: At least 5 mm engagement; no bottoming or underside projection; 0.25-0.35 N m final torque
- Required evidence: Lengths, three torque values, and underside photos
- Required record: value or observation
- Required record: unit and instrument ID
- Required record: original evidence file path
- Required record: PASS or FAIL result

## 08-B — Clamp-nut retention recheck

- Method: Confirm the previously qualified nuts still accept both clamp screws after final installation
- Pass limit: Nut does not spin, crack the tower, or obstruct the screw axis
- Required evidence: Close photos and confirmation against the Job 03C1 cycle record
- Required record: value or observation
- Required record: unit and instrument ID
- Required record: original evidence file path
- Required record: PASS or FAIL result

## 08-C — Cartridge remains a datum

- Method: Measure height and play after fastening
- Pass limit: Still within the Step 07 play and height limits
- Required evidence: Post-fastening measurements
- Required record: value or observation
- Required record: unit and instrument ID
- Required record: original evidence file path
- Required record: PASS or FAIL result


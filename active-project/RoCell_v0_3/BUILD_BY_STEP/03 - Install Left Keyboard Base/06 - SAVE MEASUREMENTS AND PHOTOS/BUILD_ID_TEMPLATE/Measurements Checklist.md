# Step 03 — Measurements Checklist

Use the copy inside your active build-ID folder as a work aid; never edit this generated template.

Record authoritative results with `scripts/record_step_result.py`; it safely updates `measurement_record.json`. Raw JSON editing is an advanced recovery fallback only.

Every `--evidence` path must be relative to the build-ID folder, remain contained within that folder, and point to an existing regular file. Neither `measurement_record.json` nor `signoff.json` is physical evidence. Repeat `--evidence` when one test has multiple files.

Command form:

`python scripts/record_step_result.py --step 03 --test TEST_ID --value "VALUE_OR_OBSERVATION" --unit "UNIT_OR_NA" --instrument "TOOL_ID_OR_METHOD" --evidence "photos/EXISTING_FILE.jpg" --result PASS --operator "OPERATOR_NAME"`

## 03-A — Station seats freely on both locators

- Method: Install/remove by hand without retainers
- Pass limit: No cracks, whitening, pry force, or measurable rocking
- Required evidence: Close photos of both sockets and seated base
- Required record: value or observation
- Required record: unit and instrument ID
- Required record: original evidence file path
- Required record: PASS or FAIL result

## 03-B — Free-state corner lift

- Method: Feeler measurement before clamping
- Pass limit: No more than 0.75 mm
- Required evidence: Worst corner value
- Required record: value or observation
- Required record: unit and instrument ID
- Required record: original evidence file path
- Required record: PASS or FAIL result

## 03-C — Retainer stacks

- Method: Torque driver and underside inspection
- Pass limit: At least 5 mm engagement; no bottoming or underside projection; 0.25-0.35 N m final torque
- Required evidence: Selected lengths and three torque values
- Required record: value or observation
- Required record: unit and instrument ID
- Required record: original evidence file path
- Required record: PASS or FAIL result


# Step 05 — Measurements Checklist

Use the copy inside your active build-ID folder as a work aid; never edit this generated template.

Record authoritative results with `scripts/record_step_result.py`; it safely updates `measurement_record.json`. Raw JSON editing is an advanced recovery fallback only.

Every `--evidence` path must be relative to the build-ID folder, remain contained within that folder, and point to an existing regular file. Neither `measurement_record.json` nor `signoff.json` is physical evidence. Repeat `--evidence` when one test has multiple files.

Command form:

`python scripts/record_step_result.py --step 05 --test TEST_ID --value "VALUE_OR_OBSERVATION" --unit "UNIT_OR_NA" --instrument "TOOL_ID_OR_METHOD" --evidence "photos/EXISTING_FILE.jpg" --result PASS --operator "OPERATOR_NAME"`

## 05-A — Keyboard device pose

- Method: Measure against recorded reference datums
- Pass limit: No more than 0.50 mm from the accepted reference
- Required evidence: Ten-cycle pose results
- Required record: value or observation
- Required record: unit and instrument ID
- Required record: original evidence file path
- Required record: PASS or FAIL result

## 05-B — Device support

- Method: Corner press and visual inspection
- Pass limit: No rocking, shell bow, lifted feet, or pad damage
- Required evidence: Loaded-device photos
- Required record: value or observation
- Required record: unit and instrument ID
- Required record: original evidence file path
- Required record: PASS or FAIL result

## 05-C — Clamp behavior

- Method: Mark slider positions and cycle the device
- Pass limit: Pads touch gently and remain repeatable through ten cycles
- Required evidence: Slider marks and cycle log
- Required record: value or observation
- Required record: unit and instrument ID
- Required record: original evidence file path
- Required record: PASS or FAIL result


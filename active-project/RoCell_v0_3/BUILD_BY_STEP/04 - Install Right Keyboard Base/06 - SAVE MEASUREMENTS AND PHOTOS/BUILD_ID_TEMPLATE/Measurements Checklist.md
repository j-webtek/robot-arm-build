# Step 04 — Measurements Checklist

Use the copy inside your active build-ID folder as a work aid; never edit this generated template.

Record authoritative results with `scripts/record_step_result.py`; it safely updates `measurement_record.json`. Raw JSON editing is an advanced recovery fallback only.

Every `--evidence` path must be relative to the build-ID folder, remain contained within that folder, and point to an existing regular file. Neither `measurement_record.json` nor `signoff.json` is physical evidence. Repeat `--evidence` when one test has multiple files.

Command form:

`python scripts/record_step_result.py --step 04 --test TEST_ID --value "VALUE_OR_OBSERVATION" --unit "UNIT_OR_NA" --instrument "TOOL_ID_OR_METHOD" --evidence "photos/EXISTING_FILE.jpg" --result PASS --operator "OPERATOR_NAME"`

## 04-A — Installed seam gap

- Method: Feeler gauges along the seam
- Pass limit: No more than 0.40 mm
- Required evidence: Worst gap and location
- Required record: value or observation
- Required record: unit and instrument ID
- Required record: original evidence file path
- Required record: PASS or FAIL result

## 04-B — Seam flush mismatch

- Method: Straightedge and feeler
- Pass limit: No more than 0.25 mm
- Required evidence: Worst mismatch and photo
- Required record: value or observation
- Required record: unit and instrument ID
- Required record: original evidence file path
- Required record: PASS or FAIL result

## 04-C — Combined support plane

- Method: Straightedge across both stations
- Pass limit: No more than 0.40 mm variation
- Required evidence: Measured range
- Required record: value or observation
- Required record: unit and instrument ID
- Required record: original evidence file path
- Required record: PASS or FAIL result

## 04-D — Slave retainer stacks

- Method: Verify selected screw length and engagement before final tightening; record each stack with a low-range torque driver and inspect the underside/interface after tightening
- Pass limit: At least 5 mm thread engagement in every stack; no blind-interface bottoming or underside projection; 0.25-0.35 N m final torque for KBR-HOLD-F, KBR-HOLD-R, and KBR-CLAMP
- Required evidence: Selected screw lengths, engagement check, three named final torque values, and underside/interface photos
- Required record: value or observation
- Required record: unit and instrument ID
- Required record: original evidence file path
- Required record: PASS or FAIL result

## 04-E — Installed slave-station rocking

- Method: With the board unloaded, press alternate slave-station corners and check any lifting corner with a feeler gauge
- Pass limit: No measurable rocking or corner lift after final torque
- Required evidence: Alternating-corner check result, worst measured lift if any, and short video or sequential photos
- Required record: value or observation
- Required record: unit and instrument ID
- Required record: original evidence file path
- Required record: PASS or FAIL result


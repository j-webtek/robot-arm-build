# Step 07 — Measurements Checklist

Use the copy inside your active build-ID folder as a work aid; never edit this generated template.

Record authoritative results with `scripts/record_step_result.py`; it safely updates `measurement_record.json`. Raw JSON editing is an advanced recovery fallback only.

Every `--evidence` path must be relative to the build-ID folder, remain contained within that folder, and point to an existing regular file. Neither `measurement_record.json` nor `signoff.json` is physical evidence. Repeat `--evidence` when one test has multiple files.

Command form:

`python scripts/record_step_result.py --step 07 --test TEST_ID --value "VALUE_OR_OBSERVATION" --unit "UNIT_OR_NA" --instrument "TOOL_ID_OR_METHOD" --evidence "photos/EXISTING_FILE.jpg" --result PASS --operator "OPERATOR_NAME"`

## 07-A — Rail seating

- Method: Visual inspection and thin feeler around both keys
- Pass limit: Rail fully flat; no gap, rocking, or forced alignment
- Required evidence: Top and side photos
- Required record: value or observation
- Required record: unit and instrument ID
- Required record: original evidence file path
- Required record: PASS or FAIL result

## 07-B — Recorded INSTALL cartridge lateral play

- Method: Confirm the cartridge ID, then perform a dial/feeler displacement check
- Pass limit: Installed ID matches the Job 03D record; lateral play no more than 0.15 mm
- Required evidence: Installed cartridge ID and measured play
- Required record: value or observation
- Required record: unit and instrument ID
- Required record: original evidence file path
- Required record: PASS or FAIL result

## 07-C — Recorded INSTALL cartridge height repeatability

- Method: Ten remove/reinstall cycles and height measurement
- Pass limit: No more than 0.10 mm range
- Required evidence: Installed cartridge ID and ten measured heights
- Required record: value or observation
- Required record: unit and instrument ID
- Required record: original evidence file path
- Required record: PASS or FAIL result


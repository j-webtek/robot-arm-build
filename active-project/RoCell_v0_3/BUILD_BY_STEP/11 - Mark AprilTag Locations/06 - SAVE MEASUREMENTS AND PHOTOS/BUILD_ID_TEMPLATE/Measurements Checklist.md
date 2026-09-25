# Step 11 — Measurements Checklist

Use the copy inside your active build-ID folder as a work aid; never edit this generated template.

Record authoritative results with `scripts/record_step_result.py`; it safely updates `measurement_record.json`. Raw JSON editing is an advanced recovery fallback only.

Every `--evidence` path must be relative to the build-ID folder, remain contained within that folder, and point to an existing regular file. Neither `measurement_record.json` nor `signoff.json` is physical evidence. Repeat `--evidence` when one test has multiple files.

Command form:

`python scripts/record_step_result.py --step 11 --test TEST_ID --value "VALUE_OR_OBSERVATION" --unit "UNIT_OR_NA" --instrument "TOOL_ID_OR_METHOD" --evidence "photos/EXISTING_FILE.jpg" --result PASS --operator "OPERATOR_NAME"`

## 11-A — Selected transfer-guide identity, scale, and registration

- Method: Compare route/path/hash to the Step 00 record; check both scale bars with a steel rule; inspect every Letter overlap/registration ID or the full-size board-edge/orientation controls
- Pass limit: Accepted route and hash match Step 00; both bars measure 100.0 +/- 0.2 mm at Actual Size; every Letter seam has the printed 12 mm overlap with matching IDs and no butted edge, or the one-page 24 x 36 guide passes its edge/orientation controls
- Required evidence: Selected route/path/hash plus photos of both ruler checks and all Letter seams or full-size edge/orientation controls
- Required record: value or observation
- Required record: unit and instrument ID
- Required record: original evidence file path
- Required record: PASS or FAIL result

## 11-B — Six controlled marks

- Method: Cross-check against tag_application_coordinates.csv
- Pass limit: All six centers and +Y marks present with no extra ambiguous marks
- Required evidence: Board overview and coordinate checklist
- Required record: value or observation
- Required record: unit and instrument ID
- Required record: original evidence file path
- Required record: PASS or FAIL result

## 11-C — Clean adhesive surface

- Method: Visual inspection after paper removal
- Pass limit: No paper, tape, gloss residue, or loose finish at any tag location
- Required evidence: Six cleaned-location photos
- Required record: value or observation
- Required record: unit and instrument ID
- Required record: original evidence file path
- Required record: PASS or FAIL result


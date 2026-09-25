# Step 12 — Measurements Checklist

Use the copy inside your active build-ID folder as a work aid; never edit this generated template.

Record authoritative results with `scripts/record_step_result.py`; it safely updates `measurement_record.json`. Raw JSON editing is an advanced recovery fallback only.

Every `--evidence` path must be relative to the build-ID folder, remain contained within that folder, and point to an existing regular file. Neither `measurement_record.json` nor `signoff.json` is physical evidence. Repeat `--evidence` when one test has multiple files.

Command form:

`python scripts/record_step_result.py --step 12 --test TEST_ID --value "VALUE_OR_OBSERVATION" --unit "UNIT_OR_NA" --instrument "TOOL_ID_OR_METHOD" --evidence "photos/EXISTING_FILE.jpg" --result PASS --operator "OPERATOR_NAME"`

## 12-A — Printed tile geometry

- Method: Calipers/rule on every installed and spare tile
- Pass limit: Tile 55.0 +/- 0.2 mm; detection edge 40.0 +/- 0.2 mm
- Required evidence: Measured tile table
- Required record: value or observation
- Required record: unit and instrument ID
- Required record: original evidence file path
- Required record: PASS or FAIL result

## 12-B — Installed tag placement

- Method: Verified <=0.05 mm-resolution origin-to-edge center measurement, two-offset baseline yaw calculation, and straightedge/feeler edge-lift check
- Pass limit: Center no more than 0.50 mm; yaw no more than 0.30 degrees; edge lift no more than 0.20 mm; measurement uncertainty no more than 0.10 mm
- Required evidence: Instrument verification/uncertainty, raw edge distances, calculations, six-row metrology table, and photos
- Required record: value or observation
- Required record: unit and instrument ID
- Required record: original evidence file path
- Required record: PASS or FAIL result

## 12-C — Optical-plane record

- Method: Measure tag-stock plus compressed adhesive Z for each tile
- Pass limit: All six installed Z values recorded
- Required evidence: Six optical-plane values
- Required record: value or observation
- Required record: unit and instrument ID
- Required record: original evidence file path
- Required record: PASS or FAIL result

## 12-D — Measured runtime-map handoff

- Method: After the physical measurement gate is PASS, regenerate fiducials/apriltag_map.json with scripts/generate_fiducials.py --map-only and run the six-name/source assertion
- Pass limit: coordinate_source is measured_installation; measurement status is PASS; T0, T1, T2, T3, K0, and P0 are present exactly once with the recorded measured geometry
- Required evidence: Generator and assertion console output plus the generated apriltag_map.json SHA-256
- Required record: value or observation
- Required record: unit and instrument ID
- Required record: original evidence file path
- Required record: PASS or FAIL result


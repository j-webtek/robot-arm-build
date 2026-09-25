# Step 13 — Measurements Checklist

Use the copy inside your active build-ID folder as a work aid; never edit this generated template.

Record authoritative results with `scripts/record_step_result.py`; it safely updates `measurement_record.json`. Raw JSON editing is an advanced recovery fallback only.

Every `--evidence` path must be relative to the build-ID folder, remain contained within that folder, and point to an existing regular file. Neither `measurement_record.json` nor `signoff.json` is physical evidence. Repeat `--evidence` when one test has multiple files.

Command form:

`python scripts/record_step_result.py --step 13 --test TEST_ID --value "VALUE_OR_OBSERVATION" --unit "UNIT_OR_NA" --instrument "TOOL_ID_OR_METHOD" --evidence "photos/EXISTING_FILE.jpg" --result PASS --operator "OPERATOR_NAME"`

## 13-B — Six-tag field of view and world-pose solve

- Method: Run the required-tag detector batch across at least 20 saved poses spanning the required empty-cell view
- Pass limit: T0, T1, T2, T3, K0, and P0 are present in every pose; board pose is solved from T0-T3 every time; K0/P0 remain held-out station-region checks
- Required evidence: FOV capture_session.json, pose list, 20 or more JSON reports with empty missing_required_tags and solved board_pose, annotated frames, and representative video
- Required record: value or observation
- Required record: unit and instrument ID
- Required record: original evidence file path
- Required record: PASS or FAIL result

## 13-C — Calibration and six-tag vision quality

- Method: Calibrate from 20-30 varied ChArUco views, then evaluate all six installed tags across the same 20-pose acceptance set
- Pass limit: At least 20 valid calibration views; 20/20 detections for each of T0, T1, T2, T3, K0, and P0; ChArUco RMS reprojection no more than 1.0 px
- Required evidence: ChArUco capture_session.json, camera intrinsics JSON, preview set, per-pose reports, and six-ID detection table
- Required record: value or observation
- Required record: unit and instrument ID
- Required record: original evidence file path
- Required record: PASS or FAIL result


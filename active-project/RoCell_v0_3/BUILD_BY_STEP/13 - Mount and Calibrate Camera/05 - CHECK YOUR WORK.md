# Step 13 — Check Your Work

Save original files under `06 - SAVE MEASUREMENTS AND PHOTOS/<BUILD_ID>/`, then record every test with `python scripts/record_step_result.py --step 13 ...`. Each `--evidence` path must be relative to that build-ID folder, remain contained within it, and name an existing regular file; `measurement_record.json` and `signoff.json` cannot cite themselves. A visual check alone is not evidence when a measured value is required.

Command form: `python scripts/record_step_result.py --step 13 --test TEST_ID --value "VALUE_OR_OBSERVATION" --unit "UNIT_OR_NA" --instrument "TOOL_ID_OR_METHOD" --evidence "photos/EXISTING_FILE.jpg" --result PASS --operator "OPERATOR_NAME"`. Repeat `--evidence` as needed. Raw JSON editing is an advanced recovery fallback only.

| Test | What must be true | How to check | Pass limit | Reviewed gate | Evidence to save | Record result in |
| --- | --- | --- | --- | --- | --- | --- |
| `13-B` | Six-tag field of view and world-pose solve | Run the required-tag detector batch across at least 20 saved poses spanning the required empty-cell view | T0, T1, T2, T3, K0, and P0 are present in every pose; board pose is solved from T0-T3 every time; K0/P0 remain held-out station-region checks | `tag_direct_installation_pass` | FOV capture_session.json, pose list, 20 or more JSON reports with empty missing_required_tags and solved board_pose, annotated frames, and representative video | `scripts/record_step_result.py` |
| `13-C` | Calibration and six-tag vision quality | Calibrate from 20-30 varied ChArUco views, then evaluate all six installed tags across the same 20-pose acceptance set | At least 20 valid calibration views; 20/20 detections for each of T0, T1, T2, T3, K0, and P0; ChArUco RMS reprojection no more than 1.0 px | `tag_direct_installation_pass` | ChArUco capture_session.json, camera intrinsics JSON, preview set, per-pose reports, and six-ID detection table | `scripts/record_step_result.py` |

## Completion status

| Requirement | Current result |
| --- | --- |
| `tag_direct_installation_pass` | **NOT_TESTED** |
| active-build step signoff | **NOT_STARTED** |

## If a check fails

If installed-tag geometry or detection is the cause, return to Step 12. If the camera plate, mast feet, or other printed support hardware is invalid, return to Step 00. Keep local mounting, cable, focus/exposure, capture, or calibration rework in Step 13. Reopen every downstream signoff affected by the correction.

The step is PASS only when every test is in limit, all required reviewed gates are PASS, and `signoff.json` is signed PASS.

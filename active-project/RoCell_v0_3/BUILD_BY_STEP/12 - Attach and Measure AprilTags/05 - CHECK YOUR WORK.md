# Step 12 — Check Your Work

Save original files under `06 - SAVE MEASUREMENTS AND PHOTOS/<BUILD_ID>/`, then record every test with `python scripts/record_step_result.py --step 12 ...`. Each `--evidence` path must be relative to that build-ID folder, remain contained within it, and name an existing regular file; `measurement_record.json` and `signoff.json` cannot cite themselves. A visual check alone is not evidence when a measured value is required.

Command form: `python scripts/record_step_result.py --step 12 --test TEST_ID --value "VALUE_OR_OBSERVATION" --unit "UNIT_OR_NA" --instrument "TOOL_ID_OR_METHOD" --evidence "photos/EXISTING_FILE.jpg" --result PASS --operator "OPERATOR_NAME"`. Repeat `--evidence` as needed. Raw JSON editing is an advanced recovery fallback only.

| Test | What must be true | How to check | Pass limit | Reviewed gate | Evidence to save | Record result in |
| --- | --- | --- | --- | --- | --- | --- |
| `12-A` | Printed tile geometry | Calipers/rule on every installed and spare tile | Tile 55.0 +/- 0.2 mm; detection edge 40.0 +/- 0.2 mm | `tag_artwork_scale_pass` | Measured tile table | `scripts/record_step_result.py` |
| `12-B` | Installed tag placement | Verified <=0.05 mm-resolution origin-to-edge center measurement, two-offset baseline yaw calculation, and straightedge/feeler edge-lift check | Center no more than 0.50 mm; yaw no more than 0.30 degrees; edge lift no more than 0.20 mm; measurement uncertainty no more than 0.10 mm | local signoff | Instrument verification/uncertainty, raw edge distances, calculations, six-row metrology table, and photos | `scripts/record_step_result.py` |
| `12-C` | Optical-plane record | Measure tag-stock plus compressed adhesive Z for each tile | All six installed Z values recorded | `tag_plane_placement_measured` | Six optical-plane values | `scripts/record_step_result.py` |
| `12-D` | Measured runtime-map handoff | After the physical measurement gate is PASS, regenerate fiducials/apriltag_map.json with scripts/generate_fiducials.py --map-only and run the six-name/source assertion | coordinate_source is measured_installation; measurement status is PASS; T0, T1, T2, T3, K0, and P0 are present exactly once with the recorded measured geometry | local signoff | Generator and assertion console output plus the generated apriltag_map.json SHA-256 | `scripts/record_step_result.py` |

## Completion status

| Requirement | Current result |
| --- | --- |
| `tag_plane_placement_measured` | **NOT_TESTED** |
| active-build step signoff | **NOT_STARTED** |

## If a check fails

If artwork scale, tag stock, or the application-frame print is invalid, return to Step 00 and requalify it. If a transferred center/orientation mark is wrong, return to Step 11. If one tag is damaged or misapplied, keep Step 12 on HOLD, replace that tag, and repeat all affected physical measurements before continuing.

The step is PASS only when every test is in limit, all required reviewed gates are PASS, and `signoff.json` is signed PASS.

# Step 11 — Check Your Work

Save original files under `06 - SAVE MEASUREMENTS AND PHOTOS/<BUILD_ID>/`, then record every test with `python scripts/record_step_result.py --step 11 ...`. Each `--evidence` path must be relative to that build-ID folder, remain contained within it, and name an existing regular file; `measurement_record.json` and `signoff.json` cannot cite themselves. A visual check alone is not evidence when a measured value is required.

Command form: `python scripts/record_step_result.py --step 11 --test TEST_ID --value "VALUE_OR_OBSERVATION" --unit "UNIT_OR_NA" --instrument "TOOL_ID_OR_METHOD" --evidence "photos/EXISTING_FILE.jpg" --result PASS --operator "OPERATOR_NAME"`. Repeat `--evidence` as needed. Raw JSON editing is an advanced recovery fallback only.

| Test | What must be true | How to check | Pass limit | Reviewed gate | Evidence to save | Record result in |
| --- | --- | --- | --- | --- | --- | --- |
| `11-A` | Selected transfer-guide identity, scale, and registration | Compare route/path/hash to the Step 00 record; check both scale bars with a steel rule; inspect every Letter overlap/registration ID or the full-size board-edge/orientation controls | Accepted route and hash match Step 00; both bars measure 100.0 +/- 0.2 mm at Actual Size; every Letter seam has the printed 12 mm overlap with matching IDs and no butted edge, or the one-page 24 x 36 guide passes its edge/orientation controls | `board_setup_template_scale_pass` | Selected route/path/hash plus photos of both ruler checks and all Letter seams or full-size edge/orientation controls | `scripts/record_step_result.py` |
| `11-B` | Six controlled marks | Cross-check against tag_application_coordinates.csv | All six centers and +Y marks present with no extra ambiguous marks | local signoff | Board overview and coordinate checklist | `scripts/record_step_result.py` |
| `11-C` | Clean adhesive surface | Visual inspection after paper removal | No paper, tape, gloss residue, or loose finish at any tag location | local signoff | Six cleaned-location photos | `scripts/record_step_result.py` |

## Completion status

| Requirement | Current result |
| --- | --- |
| active-build step signoff | **NOT_STARTED** |

## If a check fails

Set this step to `HOLD`; do not continue. Keep reversible local rework in Step 11. Return to Step 00 for a failed printed part, hardware-fit coupon, or source measurement; return to Step 01 for a failed board locator/anchor; or return to Step 10 — Check Phone Clearances when its installed handoff caused the failure. Reopen every affected downstream signoff.

The step is PASS only when every test is in limit, all required reviewed gates are PASS, and `signoff.json` is signed PASS.

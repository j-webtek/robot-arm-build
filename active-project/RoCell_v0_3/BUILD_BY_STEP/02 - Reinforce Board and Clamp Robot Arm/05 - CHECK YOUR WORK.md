# Step 02 — Check Your Work

Save original files under `06 - SAVE MEASUREMENTS AND PHOTOS/<BUILD_ID>/`, then record every test with `python scripts/record_step_result.py --step 02 ...`. Each `--evidence` path must be relative to that build-ID folder, remain contained within it, and name an existing regular file; `measurement_record.json` and `signoff.json` cannot cite themselves. A visual check alone is not evidence when a measured value is required.

Command form: `python scripts/record_step_result.py --step 02 --test TEST_ID --value "VALUE_OR_OBSERVATION" --unit "UNIT_OR_NA" --instrument "TOOL_ID_OR_METHOD" --evidence "photos/EXISTING_FILE.jpg" --result PASS --operator "OPERATOR_NAME"`. Repeat `--evidence` as needed. Raw JSON editing is an advanced recovery fallback only.

| Test | What must be true | How to check | Pass limit | Reviewed gate | Evidence to save | Record result in |
| --- | --- | --- | --- | --- | --- | --- |
| `02-A` | Board stays flat after clamping | Straightedge and feelers before and after clamp load | No new local lift above the board acceptance limit | local signoff | Before/after measurements and underside photo | `scripts/record_step_result.py` |
| `02-B` | Reinforcement clears all interfaces | Visual and tactile inspection from the underside | No contact with anchors, feet, station hardware, or cable paths | local signoff | Underside overview photo | `scripts/record_step_result.py` |
| `02-C` | Factory arm clamp is installed and stable | Record the clamp model/instructions and manufacturer-approved tightening setting, then perform static before/after mounting inspections without forcing or back-driving the arm | Installation matches the clamp manufacturer; no clamp movement, board crushing, new bow, or permanent board shift | local signoff | Clamp model/instruction reference, tightening setting, and before/after reference measurements | `scripts/record_step_result.py` |

## Completion status

| Requirement | Current result |
| --- | --- |
| active-build step signoff | **NOT_STARTED** |

## If a check fails

Set this step to `HOLD`; do not continue. Keep reversible local rework in Step 02. Return to Step 00 for a failed printed part, hardware-fit coupon, or source measurement; return to Step 01 for a failed board locator/anchor; or return to Step 01 — Seal Mark and Drill the Board when its installed handoff caused the failure. Reopen every affected downstream signoff.

The step is PASS only when every test is in limit, all required reviewed gates are PASS, and `signoff.json` is signed PASS.

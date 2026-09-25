# Step 08 — Check Your Work

Save original files under `06 - SAVE MEASUREMENTS AND PHOTOS/<BUILD_ID>/`, then record every test with `python scripts/record_step_result.py --step 08 ...`. Each `--evidence` path must be relative to that build-ID folder, remain contained within it, and name an existing regular file; `measurement_record.json` and `signoff.json` cannot cite themselves. A visual check alone is not evidence when a measured value is required.

Command form: `python scripts/record_step_result.py --step 08 --test TEST_ID --value "VALUE_OR_OBSERVATION" --unit "UNIT_OR_NA" --instrument "TOOL_ID_OR_METHOD" --evidence "photos/EXISTING_FILE.jpg" --result PASS --operator "OPERATOR_NAME"`. Repeat `--evidence` as needed. Raw JSON editing is an advanced recovery fallback only.

| Test | What must be true | How to check | Pass limit | Reviewed gate | Evidence to save | Record result in |
| --- | --- | --- | --- | --- | --- | --- |
| `08-A` | All three station retainers | Torque and stack inspection | At least 5 mm engagement; no bottoming or underside projection; 0.25-0.35 N m final torque | local signoff | Lengths, three torque values, and underside photos | `scripts/record_step_result.py` |
| `08-B` | Clamp-nut retention recheck | Confirm the previously qualified nuts still accept both clamp screws after final installation | Nut does not spin, crack the tower, or obstruct the screw axis | local signoff | Close photos and confirmation against the Job 03C1 cycle record | `scripts/record_step_result.py` |
| `08-C` | Cartridge remains a datum | Measure height and play after fastening | Still within the Step 07 play and height limits | `calibration_puck_datum_pass` | Post-fastening measurements | `scripts/record_step_result.py` |

## Completion status

| Requirement | Current result |
| --- | --- |
| active-build step signoff | **NOT_STARTED** |

## If a check fails

Set this step to `HOLD`; do not continue. Keep reversible local rework in Step 08. Return to Step 00 for a failed printed part, hardware-fit coupon, or source measurement; return to Step 01 for a failed board locator/anchor; or return to Step 07 — Fit Phone Rail and Tool Cartridge when its installed handoff caused the failure. Reopen every affected downstream signoff.

The step is PASS only when every test is in limit, all required reviewed gates are PASS, and `signoff.json` is signed PASS.

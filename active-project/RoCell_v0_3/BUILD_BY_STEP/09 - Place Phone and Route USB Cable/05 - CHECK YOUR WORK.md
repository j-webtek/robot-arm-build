# Step 09 — Check Your Work

Save original files under `06 - SAVE MEASUREMENTS AND PHOTOS/<BUILD_ID>/`, then record every test with `python scripts/record_step_result.py --step 09 ...`. Each `--evidence` path must be relative to that build-ID folder, remain contained within it, and name an existing regular file; `measurement_record.json` and `signoff.json` cannot cite themselves. A visual check alone is not evidence when a measured value is required.

Command form: `python scripts/record_step_result.py --step 09 --test TEST_ID --value "VALUE_OR_OBSERVATION" --unit "UNIT_OR_NA" --instrument "TOOL_ID_OR_METHOD" --evidence "photos/EXISTING_FILE.jpg" --result PASS --operator "OPERATOR_NAME"`. Repeat `--evidence` as needed. Raw JSON editing is an advanced recovery fallback only.

| Test | What must be true | How to check | Pass limit | Reviewed gate | Evidence to save | Record result in |
| --- | --- | --- | --- | --- | --- | --- |
| `09-A` | Phone device pose | Measure against the recorded station reference | No more than 0.35 mm from the accepted reference | local signoff | Ten-cycle pose results | `scripts/record_step_result.py` |
| `09-B` | Cable strain relief | Inspect connected phone through ten cycles | No connector load, kink, saddle crack, or violated bend radius | local signoff | Side photos and cycle log | `scripts/record_step_result.py` |
| `09-C` | TPU retention | Force-gauge pull to the engineering-approved proof load/duration plus ten load cycles | Approved force and duration are achieved; tips remain retained and undamaged | `phone_tpu_retention_coupon_pass` | Approval ID, gauge ID, measured load/duration, cycle result, and witness photos | `scripts/record_step_result.py` |

## Completion status

| Requirement | Current result |
| --- | --- |
| active-build step signoff | **NOT_STARTED** |

## If a check fails

Set this step to `HOLD`; do not continue. Keep reversible local rework in Step 09. Return to Step 00 for a failed printed part, hardware-fit coupon, or source measurement; return to Step 01 for a failed board locator/anchor; or return to Step 08 — Secure Phone Rail and Tool Cartridge when its installed handoff caused the failure. Reopen every affected downstream signoff.

The step is PASS only when every test is in limit, all required reviewed gates are PASS, and `signoff.json` is signed PASS.

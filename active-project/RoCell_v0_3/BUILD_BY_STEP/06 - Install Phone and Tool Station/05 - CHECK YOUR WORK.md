# Step 06 — Check Your Work

Save original files under `06 - SAVE MEASUREMENTS AND PHOTOS/<BUILD_ID>/`, then record every test with `python scripts/record_step_result.py --step 06 ...`. Each `--evidence` path must be relative to that build-ID folder, remain contained within it, and name an existing regular file; `measurement_record.json` and `signoff.json` cannot cite themselves. A visual check alone is not evidence when a measured value is required.

Command form: `python scripts/record_step_result.py --step 06 --test TEST_ID --value "VALUE_OR_OBSERVATION" --unit "UNIT_OR_NA" --instrument "TOOL_ID_OR_METHOD" --evidence "photos/EXISTING_FILE.jpg" --result PASS --operator "OPERATOR_NAME"`. Repeat `--evidence` as needed. Raw JSON editing is an advanced recovery fallback only.

| Test | What must be true | How to check | Pass limit | Reviewed gate | Evidence to save | Record result in |
| --- | --- | --- | --- | --- | --- | --- |
| `06-A` | Station locator fit | Tool-free install/remove cycle | No more than 0.15 mm lateral play; no cracking or whitening | `phone_station_registration_coupon_pass` | Cycle count and play measurement | `scripts/record_step_result.py` |
| `06-B` | Phone support plane | Straightedge and feelers | No more than 0.30 mm variation | `phone_tcp_station_postprint_pass` | Measured range | `scripts/record_step_result.py` |
| `06-C` | TCP receiver seat | Straightedge/height comparison | No more than 0.15 mm seat error | `phone_tcp_station_postprint_pass` | Measured error | `scripts/record_step_result.py` |
| `06-D` | PT-HOLD-TCP effective stack | Inspect washer recess and gauge the selected screw/anchor stack before torque | Washer fully seated in 1.5 mm recess; 9.0 mm nominal effective printed stack; at least 5.0 mm useful thread engagement; no bottoming or underside projection; 0.25-0.35 N m | local signoff | Selected length, measured engagement, washer-seat photo, underside/interface photo, and final torque | `scripts/record_step_result.py` |

## Completion status

| Requirement | Current result |
| --- | --- |
| active-build step signoff | **NOT_STARTED** |

## If a check fails

Set this step to `HOLD`; do not continue. Keep reversible local rework in Step 06. Return to Step 00 for a failed printed part, hardware-fit coupon, or source measurement; return to Step 01 for a failed board locator/anchor; or return to Step 05 — Place and Secure Keyboard when its installed handoff caused the failure. Reopen every affected downstream signoff.

The step is PASS only when every test is in limit, all required reviewed gates are PASS, and `signoff.json` is signed PASS.

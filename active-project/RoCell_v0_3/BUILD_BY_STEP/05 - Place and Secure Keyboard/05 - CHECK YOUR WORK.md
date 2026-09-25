# Step 05 — Check Your Work

Save original files under `06 - SAVE MEASUREMENTS AND PHOTOS/<BUILD_ID>/`, then record every test with `python scripts/record_step_result.py --step 05 ...`. Each `--evidence` path must be relative to that build-ID folder, remain contained within it, and name an existing regular file; `measurement_record.json` and `signoff.json` cannot cite themselves. A visual check alone is not evidence when a measured value is required.

Command form: `python scripts/record_step_result.py --step 05 --test TEST_ID --value "VALUE_OR_OBSERVATION" --unit "UNIT_OR_NA" --instrument "TOOL_ID_OR_METHOD" --evidence "photos/EXISTING_FILE.jpg" --result PASS --operator "OPERATOR_NAME"`. Repeat `--evidence` as needed. Raw JSON editing is an advanced recovery fallback only.

| Test | What must be true | How to check | Pass limit | Reviewed gate | Evidence to save | Record result in |
| --- | --- | --- | --- | --- | --- | --- |
| `05-A` | Keyboard device pose | Measure against recorded reference datums | No more than 0.50 mm from the accepted reference | `keyboard_fixture_assembly_pass` | Ten-cycle pose results | `scripts/record_step_result.py` |
| `05-B` | Device support | Corner press and visual inspection | No rocking, shell bow, lifted feet, or pad damage | `keyboard_fixture_assembly_pass` | Loaded-device photos | `scripts/record_step_result.py` |
| `05-C` | Clamp behavior | Mark slider positions and cycle the device | Pads touch gently and remain repeatable through ten cycles | `keyboard_fixture_assembly_pass` | Slider marks and cycle log | `scripts/record_step_result.py` |

## Completion status

| Requirement | Current result |
| --- | --- |
| `keyboard_fixture_assembly_pass` | **NOT_TESTED** |
| active-build step signoff | **NOT_STARTED** |

## If a check fails

Set this step to `HOLD`; do not continue. Keep reversible local rework in Step 05. Return to Step 00 for a failed printed part, hardware-fit coupon, or source measurement; return to Step 01 for a failed board locator/anchor; or return to Step 04 — Install Right Keyboard Base when its installed handoff caused the failure. Reopen every affected downstream signoff.

The step is PASS only when every test is in limit, all required reviewed gates are PASS, and `signoff.json` is signed PASS.

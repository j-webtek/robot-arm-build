# Step 10 — Check Your Work

Save original files under `06 - SAVE MEASUREMENTS AND PHOTOS/<BUILD_ID>/`, then record every test with `python scripts/record_step_result.py --step 10 ...`. Each `--evidence` path must be relative to that build-ID folder, remain contained within it, and name an existing regular file; `measurement_record.json` and `signoff.json` cannot cite themselves. A visual check alone is not evidence when a measured value is required.

Command form: `python scripts/record_step_result.py --step 10 --test TEST_ID --value "VALUE_OR_OBSERVATION" --unit "UNIT_OR_NA" --instrument "TOOL_ID_OR_METHOD" --evidence "photos/EXISTING_FILE.jpg" --result PASS --operator "OPERATOR_NAME"`. Repeat `--evidence` as needed. Raw JSON editing is an advanced recovery fallback only.

| Test | What must be true | How to check | Pass limit | Reviewed gate | Evidence to save | Record result in |
| --- | --- | --- | --- | --- | --- | --- |
| `10-A` | Screen-edge clearance | Visual and measured tip position | Both TPU contacts remain below/outside glass and bezel | `phone_fixture_assembly_pass` | Front and side close photos | `scripts/record_step_result.py` |
| `10-B` | Camera and button clearance | Measure closest approach and operate controls | No contact or unintended input; measured margin minus uncertainty is at or above the engineering-approved minimum | `phone_fixture_assembly_pass` | Approval ID, approved limit, uncertainty, minimum margins, and control test video/photo | `scripts/record_step_result.py` |
| `10-C` | USB keepout | Inspect connector and bend under light cable disturbance | No body contact, strain, kink, or bend-radius violation | `phone_cable_measured` | Connector and saddle photos | `scripts/record_step_result.py` |

## Completion status

| Requirement | Current result |
| --- | --- |
| `phone_fixture_assembly_pass` | **NOT_TESTED** |
| active-build step signoff | **NOT_STARTED** |

## If a check fails

Set this step to `HOLD`; do not continue. Keep reversible local rework in Step 10. Return to Step 00 for a failed printed part, hardware-fit coupon, or source measurement; return to Step 01 for a failed board locator/anchor; or return to Step 09 — Place Phone and Route USB Cable when its installed handoff caused the failure. Reopen every affected downstream signoff.

The step is PASS only when every test is in limit, all required reviewed gates are PASS, and `signoff.json` is signed PASS.

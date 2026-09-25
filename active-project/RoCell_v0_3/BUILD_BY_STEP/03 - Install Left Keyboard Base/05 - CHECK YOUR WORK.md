# Step 03 — Check Your Work

Save original files under `06 - SAVE MEASUREMENTS AND PHOTOS/<BUILD_ID>/`, then record every test with `python scripts/record_step_result.py --step 03 ...`. Each `--evidence` path must be relative to that build-ID folder, remain contained within it, and name an existing regular file; `measurement_record.json` and `signoff.json` cannot cite themselves. A visual check alone is not evidence when a measured value is required.

Command form: `python scripts/record_step_result.py --step 03 --test TEST_ID --value "VALUE_OR_OBSERVATION" --unit "UNIT_OR_NA" --instrument "TOOL_ID_OR_METHOD" --evidence "photos/EXISTING_FILE.jpg" --result PASS --operator "OPERATOR_NAME"`. Repeat `--evidence` as needed. Raw JSON editing is an advanced recovery fallback only.

| Test | What must be true | How to check | Pass limit | Reviewed gate | Evidence to save | Record result in |
| --- | --- | --- | --- | --- | --- | --- |
| `03-A` | Station seats freely on both locators | Install/remove by hand without retainers | No cracks, whitening, pry force, or measurable rocking | `keyboard_left_first_article_pass` | Close photos of both sockets and seated base | `scripts/record_step_result.py` |
| `03-B` | Free-state corner lift | Feeler measurement before clamping | No more than 0.75 mm | `keyboard_left_first_article_pass` | Worst corner value | `scripts/record_step_result.py` |
| `03-C` | Retainer stacks | Torque driver and underside inspection | At least 5 mm engagement; no bottoming or underside projection; 0.25-0.35 N m final torque | local signoff | Selected lengths and three torque values | `scripts/record_step_result.py` |

## Completion status

| Requirement | Current result |
| --- | --- |
| active-build step signoff | **NOT_STARTED** |

## If a check fails

Set this step to `HOLD`; do not continue. Keep reversible local rework in Step 03. Return to Step 00 for a failed printed part, hardware-fit coupon, or source measurement; return to Step 01 for a failed board locator/anchor; or return to Step 02 — Reinforce Board and Clamp Robot Arm when its installed handoff caused the failure. Reopen every affected downstream signoff.

The step is PASS only when every test is in limit, all required reviewed gates are PASS, and `signoff.json` is signed PASS.

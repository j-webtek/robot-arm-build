# Step 04 — Check Your Work

Save original files under `06 - SAVE MEASUREMENTS AND PHOTOS/<BUILD_ID>/`, then record every test with `python scripts/record_step_result.py --step 04 ...`. Each `--evidence` path must be relative to that build-ID folder, remain contained within it, and name an existing regular file; `measurement_record.json` and `signoff.json` cannot cite themselves. A visual check alone is not evidence when a measured value is required.

Command form: `python scripts/record_step_result.py --step 04 --test TEST_ID --value "VALUE_OR_OBSERVATION" --unit "UNIT_OR_NA" --instrument "TOOL_ID_OR_METHOD" --evidence "photos/EXISTING_FILE.jpg" --result PASS --operator "OPERATOR_NAME"`. Repeat `--evidence` as needed. Raw JSON editing is an advanced recovery fallback only.

| Test | What must be true | How to check | Pass limit | Reviewed gate | Evidence to save | Record result in |
| --- | --- | --- | --- | --- | --- | --- |
| `04-A` | Installed seam gap | Feeler gauges along the seam | No more than 0.40 mm | `keyboard_station_pair_postprint_pass` | Worst gap and location | `scripts/record_step_result.py` |
| `04-B` | Seam flush mismatch | Straightedge and feeler | No more than 0.25 mm | `keyboard_station_pair_postprint_pass` | Worst mismatch and photo | `scripts/record_step_result.py` |
| `04-C` | Combined support plane | Straightedge across both stations | No more than 0.40 mm variation | `keyboard_station_pair_postprint_pass` | Measured range | `scripts/record_step_result.py` |
| `04-D` | Slave retainer stacks | Verify selected screw length and engagement before final tightening; record each stack with a low-range torque driver and inspect the underside/interface after tightening | At least 5 mm thread engagement in every stack; no blind-interface bottoming or underside projection; 0.25-0.35 N m final torque for KBR-HOLD-F, KBR-HOLD-R, and KBR-CLAMP | local signoff | Selected screw lengths, engagement check, three named final torque values, and underside/interface photos | `scripts/record_step_result.py` |
| `04-E` | Installed slave-station rocking | With the board unloaded, press alternate slave-station corners and check any lifting corner with a feeler gauge | No measurable rocking or corner lift after final torque | local signoff | Alternating-corner check result, worst measured lift if any, and short video or sequential photos | `scripts/record_step_result.py` |

## Completion status

| Requirement | Current result |
| --- | --- |
| active-build step signoff | **NOT_STARTED** |

## If a check fails

Set this step to `HOLD`; do not continue. Keep reversible local rework in Step 04. Return to Step 00 for a failed printed part, hardware-fit coupon, or source measurement; return to Step 01 for a failed board locator/anchor; or return to Step 03 — Install Left Keyboard Base when its installed handoff caused the failure. Reopen every affected downstream signoff.

The step is PASS only when every test is in limit, all required reviewed gates are PASS, and `signoff.json` is signed PASS.

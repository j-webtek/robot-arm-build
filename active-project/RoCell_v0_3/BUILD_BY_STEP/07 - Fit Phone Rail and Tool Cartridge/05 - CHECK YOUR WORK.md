# Step 07 — Check Your Work

Save original files under `06 - SAVE MEASUREMENTS AND PHOTOS/<BUILD_ID>/`, then record every test with `python scripts/record_step_result.py --step 07 ...`. Each `--evidence` path must be relative to that build-ID folder, remain contained within it, and name an existing regular file; `measurement_record.json` and `signoff.json` cannot cite themselves. A visual check alone is not evidence when a measured value is required.

Command form: `python scripts/record_step_result.py --step 07 --test TEST_ID --value "VALUE_OR_OBSERVATION" --unit "UNIT_OR_NA" --instrument "TOOL_ID_OR_METHOD" --evidence "photos/EXISTING_FILE.jpg" --result PASS --operator "OPERATOR_NAME"`. Repeat `--evidence` as needed. Raw JSON editing is an advanced recovery fallback only.

| Test | What must be true | How to check | Pass limit | Reviewed gate | Evidence to save | Record result in |
| --- | --- | --- | --- | --- | --- | --- |
| `07-A` | Rail seating | Visual inspection and thin feeler around both keys | Rail fully flat; no gap, rocking, or forced alignment | `phone_clamp_rail_first_article_pass` | Top and side photos | `scripts/record_step_result.py` |
| `07-B` | Recorded INSTALL cartridge lateral play | Confirm the cartridge ID, then perform a dial/feeler displacement check | Installed ID matches the Job 03D record; lateral play no more than 0.15 mm | `calibration_puck_datum_pass` | Installed cartridge ID and measured play | `scripts/record_step_result.py` |
| `07-C` | Recorded INSTALL cartridge height repeatability | Ten remove/reinstall cycles and height measurement | No more than 0.10 mm range | `calibration_puck_datum_pass` | Installed cartridge ID and ten measured heights | `scripts/record_step_result.py` |

## Completion status

| Requirement | Current result |
| --- | --- |
| active-build step signoff | **NOT_STARTED** |

## If a check fails

Set this step to `HOLD`; do not continue. Keep reversible local rework in Step 07. Return to Step 00 for a failed printed part, hardware-fit coupon, or source measurement; return to Step 01 for a failed board locator/anchor; or return to Step 06 — Install Phone and Tool Station when its installed handoff caused the failure. Reopen every affected downstream signoff.

The step is PASS only when every test is in limit, all required reviewed gates are PASS, and `signoff.json` is signed PASS.

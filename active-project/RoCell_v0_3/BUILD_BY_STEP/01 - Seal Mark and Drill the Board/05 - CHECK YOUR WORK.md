# Step 01 — Check Your Work

Save original files under `06 - SAVE MEASUREMENTS AND PHOTOS/<BUILD_ID>/`, then record every test with `python scripts/record_step_result.py --step 01 ...`. Each `--evidence` path must be relative to that build-ID folder, remain contained within it, and name an existing regular file; `measurement_record.json` and `signoff.json` cannot cite themselves. A visual check alone is not evidence when a measured value is required.

Command form: `python scripts/record_step_result.py --step 01 --test TEST_ID --value "VALUE_OR_OBSERVATION" --unit "UNIT_OR_NA" --instrument "TOOL_ID_OR_METHOD" --evidence "photos/EXISTING_FILE.jpg" --result PASS --operator "OPERATOR_NAME"`. Repeat `--evidence` as needed. Raw JSON editing is an advanced recovery fallback only.

| Test | What must be true | How to check | Pass limit | Reviewed gate | Evidence to save | Record result in |
| --- | --- | --- | --- | --- | --- | --- |
| `01-A` | Local board flatness | 300 mm straightedge and feelers | No more than 0.50 mm over any 300 mm span | `board_fabrication_pass` | Worst measured span and photo | `scripts/record_step_result.py` |
| `01-B` | Overall board bow | Straightedge on cured board | No more than 1.50 mm over the full board | `board_fabrication_pass` | Measured bow and photo | `scripts/record_step_result.py` |
| `01-C` | Locator bores preserve a blind floor and pins have controlled projection | Record thickness, depth, and cured projection by the four named locator IDs; inspect the underside | Each depth is 15.00 +/- 0.20 mm and leaves at least 2.00 mm local floor; no breakout; each exposed projection is 5.00 +/- 0.15 mm | `board_fabrication_pass` | ID-keyed local thicknesses, actual depths, underside photos, depth-stop setup, and cured projections | `scripts/record_step_result.py` |
| `01-D` | All qualified station interfaces dry fit | Verify all nine anchor rows are complete, then install all stations and nine stacks by hand | Every final bore is traceable to its actual qualified anchor; no rocking, binding, bottoming, base lift, veneer damage, or underside projection | `board_fabrication_pass` | Dry-fit photos, fully completed FASTENER_MAP.csv, scrap-board qualification references, and recorded map SHA-256 | `scripts/record_step_result.py` |
| `01-E` | Board finish coverage and cure | Inspect both faces and every edge; compare elapsed cure time/conditions with the selected finish instructions | Both faces and every edge evenly sealed and fully cured; no tack, print transfer, contamination, or finish-induced warping | `board_fabrication_pass` | Finish product/batch, SDS/PPE record, application and cure timestamps, and face/edge photos | `scripts/record_step_result.py` |
| `01-F` | Board geometry and selected drill-guide registration pass before center transfer | Measure front/rear widths, left/right depths, thicknesses, and both diagonals; calculate the edge-derived diagonal; verify guide path/hash, FRONT/origin, board edges, every X/Y scale control, and all applicable registration IDs | Width 610.0 +/- 0.5 mm; depth 457.0 +/- 0.5 mm; thickness 17.50-18.50 mm; opposite like edges differ by no more than 0.50 mm; each diagonal is within 1.00 mm of the edge-derived value and the pair differs by no more than 1.00 mm; every X/Y scale control is 100.0 +/- 0.2 mm; no guide-edge or registration disagreement | `board_fabrication_pass` | Six board-dimension readings, four local thickness readings, diagonal calculation, selected-guide record, ruler photos, assembled-guide photo, and registration/edge-control photos | `scripts/record_step_result.py` |
| `01-G` | All thirteen transferred centers match the controlled coordinate schedule | Before drilling, identify each punch by feature ID and cross-check X from left/right plus Y from front/rear against drawings/board_hole_coordinates.csv | Exactly four locator and nine anchor centers are present; all four edge-distance checks agree for every ID; no tag, outline, dimension, or registration mark is transferred; any disagreement is corrected before drilling | `board_fabrication_pass` | Signed thirteen-row center audit and overhead photos before and after paper removal | `scripts/record_step_result.py` |

## Completion status

| Requirement | Current result |
| --- | --- |
| `board_fabrication_pass` | **NOT_TESTED** |
| active-build step signoff | **NOT_STARTED** |

## If a check fails

Set this step to `HOLD`; do not continue. Keep reversible local rework in Step 01. Return to Step 00 for a failed printed part, hardware-fit coupon, or source measurement; return to Step 01 for a failed board locator/anchor; or return to Step 00 — Measure Hardware and Print Approved Parts when its installed handoff caused the failure. Reopen every affected downstream signoff.

The step is PASS only when every test is in limit, all required reviewed gates are PASS, and `signoff.json` is signed PASS.

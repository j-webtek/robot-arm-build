# Step 01 — Measurements Checklist

Use the copy inside your active build-ID folder as a work aid; never edit this generated template.

Record authoritative results with `scripts/record_step_result.py`; it safely updates `measurement_record.json`. Raw JSON editing is an advanced recovery fallback only.

Every `--evidence` path must be relative to the build-ID folder, remain contained within that folder, and point to an existing regular file. Neither `measurement_record.json` nor `signoff.json` is physical evidence. Repeat `--evidence` when one test has multiple files.

Command form:

`python scripts/record_step_result.py --step 01 --test TEST_ID --value "VALUE_OR_OBSERVATION" --unit "UNIT_OR_NA" --instrument "TOOL_ID_OR_METHOD" --evidence "photos/EXISTING_FILE.jpg" --result PASS --operator "OPERATOR_NAME"`

## 01-A — Local board flatness

- Method: 300 mm straightedge and feelers
- Pass limit: No more than 0.50 mm over any 300 mm span
- Required evidence: Worst measured span and photo
- Required record: value or observation
- Required record: unit and instrument ID
- Required record: original evidence file path
- Required record: PASS or FAIL result

## 01-B — Overall board bow

- Method: Straightedge on cured board
- Pass limit: No more than 1.50 mm over the full board
- Required evidence: Measured bow and photo
- Required record: value or observation
- Required record: unit and instrument ID
- Required record: original evidence file path
- Required record: PASS or FAIL result

## 01-C — Locator bores preserve a blind floor and pins have controlled projection

- Method: Record thickness, depth, and cured projection by the four named locator IDs; inspect the underside
- Pass limit: Each depth is 15.00 +/- 0.20 mm and leaves at least 2.00 mm local floor; no breakout; each exposed projection is 5.00 +/- 0.15 mm
- Required evidence: ID-keyed local thicknesses, actual depths, underside photos, depth-stop setup, and cured projections
- Required record: value or observation
- Required record: unit and instrument ID
- Required record: original evidence file path
- Required record: PASS or FAIL result

## 01-D — All qualified station interfaces dry fit

- Method: Verify all nine anchor rows are complete, then install all stations and nine stacks by hand
- Pass limit: Every final bore is traceable to its actual qualified anchor; no rocking, binding, bottoming, base lift, veneer damage, or underside projection
- Required evidence: Dry-fit photos, fully completed FASTENER_MAP.csv, scrap-board qualification references, and recorded map SHA-256
- Required record: value or observation
- Required record: unit and instrument ID
- Required record: original evidence file path
- Required record: PASS or FAIL result

## 01-E — Board finish coverage and cure

- Method: Inspect both faces and every edge; compare elapsed cure time/conditions with the selected finish instructions
- Pass limit: Both faces and every edge evenly sealed and fully cured; no tack, print transfer, contamination, or finish-induced warping
- Required evidence: Finish product/batch, SDS/PPE record, application and cure timestamps, and face/edge photos
- Required record: value or observation
- Required record: unit and instrument ID
- Required record: original evidence file path
- Required record: PASS or FAIL result

## 01-F — Board geometry and selected drill-guide registration pass before center transfer

- Method: Measure front/rear widths, left/right depths, thicknesses, and both diagonals; calculate the edge-derived diagonal; verify guide path/hash, FRONT/origin, board edges, every X/Y scale control, and all applicable registration IDs
- Pass limit: Width 610.0 +/- 0.5 mm; depth 457.0 +/- 0.5 mm; thickness 17.50-18.50 mm; opposite like edges differ by no more than 0.50 mm; each diagonal is within 1.00 mm of the edge-derived value and the pair differs by no more than 1.00 mm; every X/Y scale control is 100.0 +/- 0.2 mm; no guide-edge or registration disagreement
- Required evidence: Six board-dimension readings, four local thickness readings, diagonal calculation, selected-guide record, ruler photos, assembled-guide photo, and registration/edge-control photos
- Required record: value or observation
- Required record: unit and instrument ID
- Required record: original evidence file path
- Required record: PASS or FAIL result

## 01-G — All thirteen transferred centers match the controlled coordinate schedule

- Method: Before drilling, identify each punch by feature ID and cross-check X from left/right plus Y from front/rear against drawings/board_hole_coordinates.csv
- Pass limit: Exactly four locator and nine anchor centers are present; all four edge-distance checks agree for every ID; no tag, outline, dimension, or registration mark is transferred; any disagreement is corrected before drilling
- Required evidence: Signed thirteen-row center audit and overhead photos before and after paper removal
- Required record: value or observation
- Required record: unit and instrument ID
- Required record: original evidence file path
- Required record: PASS or FAIL result


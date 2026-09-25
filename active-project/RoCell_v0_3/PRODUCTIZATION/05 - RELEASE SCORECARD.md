# Consumer release scorecard

**Engineering baseline:** `RC03-INT-R1`  
**Consumer candidate:** not yet assigned  
**Current digital package:** `PASS`  
**Current physical release:** `UNRELEASED`  
**Release decision:** `NOT ELIGIBLE`

Mark a box only when controlled evidence exists. A written intention is not evidence.

## Gate 0 — Release control

- [ ] Consumer revision assigned.
- [ ] Productization issue register active.
- [ ] Change log active.
- [ ] Generated files are changed only through controlled sources/generators.

## Gate 1 — V1 product frozen

- [ ] Product Definition complete.
- [ ] Exact intended use and excluded uses defined.
- [ ] Exact keyboard selected.
- [ ] Exact phone/case selected.
- [ ] Exact USB cable and routing hardware selected.
- [ ] Exact camera and support selected.
- [ ] One primary tool route selected.
- [ ] Exact board, finish, anchors, fasteners, pads, spring, adhesive, and safety hardware selected.
- [ ] Supported printer/material/QIDI/software/firmware versions fixed.
- [ ] Exact BOM and supported-substitution table complete.
- [ ] Every BOM row is classified as seller-supplied, customer-printed, customer-owned, exact customer purchase, or out of V1.

## Gate 2 — Structural and safety system released

- [ ] All nine `FASTENER_MAP.csv` rows complete.
- [ ] All nine stacks pass engagement, torque, bottoming, projection, cycle, and proof checks.
- [ ] Board cut, thickness, squareness, flatness, bow, hole-center, blind-floor, and pin-projection tolerances released.
- [ ] Board repair/rework/scrap matrix released.
- [ ] Reinforcement plate released as a controlled part.
- [ ] Factory clamp location and installation method released.
- [ ] E-stop/power-isolation model, wiring, placement, reset, and test released.
- [ ] Customer electrical boundary is explicit; seller-supplied cutoff is enclosed/prewired/plug-compatible where possible, and customer mains work is outside V1.
- [ ] Board anti-shift system and proof released.
- [ ] Camera support and cable strain relief released.
- [ ] Tool force/travel/retention/TCP limits released.
- [ ] Phone and keyboard contact/clearance limits released.
- [ ] Preliminary hazard analysis and powered-test controls complete before powered qualification.

## Gate 3 — CAD and print release

- [ ] Actual reference hardware measured with datums and uncertainty.
- [ ] CAD parameters match accepted measurements/coupons.
- [ ] Shared parameters split wherever profile-specific results differ.
- [ ] Tolerance-stack review complete.
- [ ] Screw regions, walls, edge distances, layer direction, and tool access reviewed.
- [ ] Full assembly/motion/cable collision review complete.
- [ ] Customer Print Verification Plate released.
- [ ] Customer QIDI/3MF projects released and physically reopened/resliced.
- [ ] Every project stays inside the physically released X/Y/Z machine envelope; a protected Z margin below nominal height is documented.
- [ ] Every project has preview, profile, time, mass, object count, inspection, and reject information.
- [ ] Two complete customer print sets accepted without geometry scaling or undocumented repair.
- [ ] Printed-part IDs and revisions are readable.

## Gate 4 — Board and mechanical modules

- [ ] Letter and 24 x 36 board-guide paths are unambiguous.
- [ ] Letter pages 1-3 reference-only and pages 4-12 working-tile rule is repeated wherever used.
- [ ] All thirteen centers pass the released transfer tolerance.
- [ ] Two complete board builds pass.
- [ ] Keyboard master/slave installation, seam, contact, torque, and repeatability pass.
- [ ] Phone/TCP base, rail, cartridge, cable, no-go, and repeatability pass.
- [ ] Six tag IDs, orientation, adhesion, center, yaw, lift, and optical plane pass.
- [ ] One released tool route passes travel, force, retention, creep, function, and TCP tests.

## Gate 5 — Software, vision, and commissioning

- [ ] Invalid detector example corrected.
- [ ] Step 13 tag-requirement contradiction resolved.
- [ ] Step 12 tag-map handoff explicit and tested.
- [ ] Dependencies pinned and installed from one supported launcher.
- [ ] Clean computer setup succeeds without manual command repair.
- [ ] Named camera calibration and FOV pose set released.
- [ ] Camera, tag visibility, and reprojection criteria pass.
- [ ] Approved robot homing, empty-cell, and process programs supplied.
- [ ] Controller, firmware, speed, acceleration, clearance, force, and travel limits released.
- [ ] E-stop behavior and restart prevention have a dedicated acceptance test.
- [ ] Empty motion, controlled first contact, proof loads, and final commissioning pass.

## Gate 6 — Customer package

- [ ] Ten-stage customer path complete.
- [ ] Start Here, compatibility, BOM, print, assembly, setup, safety, troubleshooting, maintenance, and spares documents complete.
- [ ] Every customer action has one stable ID.
- [ ] Every irreversible/safety action has an adequate close-up and correct/incorrect example.
- [ ] Every fastener has friendly name, ID, bag, length, quantity, destination, torque, and engagement.
- [ ] No customer-facing unresolved choice or engineering approval remains.
- [ ] All customer commands, links, files, and values physically tested.
- [ ] One Build Passport replaces manual customer JSON/hash work.
- [ ] Every customer check traces to an internal engineering requirement.
- [ ] Seller pack incoming inspection, lot traceability, bag count, label check, pack-out verification, damage protection, and missing-part workflow pass.
- [ ] Prerelease maintenance, spares, recalibration, backup/recovery, support, warranty, and return documentation complete.

## Gate 7 — Qualification and usability

- [ ] Full engineering build completes internal Steps 00-15.
- [ ] All selected physical gates PASS.
- [ ] Golden reference configuration archived.
- [ ] Intended-duty-cycle reliability test passes for mechanisms, devices, anchors, board, tags, camera, cable, pads, and contact tool.
- [ ] First-customer test completed from a clean read-only package.
- [ ] Zero P0 issues.
- [ ] Zero unresolved P1 issues.
- [ ] Corrected P2 issues regression-tested.
- [ ] Second clean end-to-end self-build passes.
- [ ] At least three unfamiliar builders complete beta; five targeted before release.
- [ ] No safety intervention or undocumented decision required.
- [ ] All builds reach the same accepted geometry and calibrated state.
- [ ] Separate applicable safety/compliance review complete.
- [ ] Engineering design release, seller kit release, and customer unit commissioning PASS are recorded as three distinct decisions.

## Immediate release blockers

Resolved entries are retained below as an audit trail and do not count as open blockers.

| Priority | Current blocker | Owner phase | Status |
|---|---|---:|---|
| P0 | Nine board fastener/anchor stacks unresolved | 2 | OPEN |
| P0 | Reinforcement plate and clamp installation not released | 2 | OPEN |
| P0 | E-stop/power-isolation and anti-shift system not released | 2 | OPEN |
| P0 | Both tool routes are selected, but route limits, fixtures, and physical qualification remain unreleased | 1-2 | OPEN |
| P0 | Final robot programs and operating limits absent | 5 | OPEN |
| P1 | Camera/support route not released | 1-2 | OPEN |
| P1 | Reference device/BOM configuration not completely frozen | 1 | OPEN |
| P1 | Customer print jobs are not READY | 3 | OPEN |
| P1 | Step 13 now supplies a complete non-overwriting detector batch with input-count and per-frame failure enforcement | 5 | CLOSED |
| P1 | Step 13 criteria now consistently require 20/20 detection of all six tags plus a solved T0-T3 board pose | 5 | CLOSED |
| P1 | Step 12 now regenerates the measured-installation map, validates exact ID coverage, records its hash, and hands it to Step 13 | 5 | CLOSED |
| P2 | Step 11 now repeats explicit tiled-Letter and single-sheet 24 x 36 Actual Size controls | 4/6 | CLOSED |
| P2 | Overview-image coverage is insufficient for action-level assembly | 6 | OPEN |
| P2 | Customer evidence workflow exposes Python/JSON/hash operations | 5-6 | OPEN |

## Release decision

Commercial release requires every Gate 0-7 checkbox, no open P0/P1 issue, completed risk/safety review, and signed evidence from engineering and usability validation.

**Engineering release signoff:** ____________________  **Date:** __________  
**Customer-package signoff:** _______________________  **Date:** __________  
**Safety/release signoff:** __________________________  **Date:** __________

# End-to-end productization roadmap

This roadmap is ordered by dependency. Work may run in parallel only when the exit gate of an earlier phase is not required by the parallel work.

## Phase 0 — Establish the release target

**Objective:** Preserve the current engineering baseline and define a separate consumer-release target.

### Actions

1. Keep `RC03-INT-R1` as the engineering baseline.
2. Assign the customer candidate a distinct revision, such as `RC03-CUST-R0`.
3. Create a change log with one entry for every physical, software, print, or instruction change.
4. Create one issue register using:
   - `P0` — safety risk, physical incompatibility, or irreversible damage;
   - `P1` — customer cannot continue without engineering help;
   - `P2` — ambiguity, avoidable rework, or multiple plausible interpretations;
   - `P3` — navigation, wording, or presentation improvement.
5. Record the controlled source files and generators that must change; do not edit generated step Markdown directly.

### Deliverables

- Consumer-release revision.
- Change log.
- Productization issue register.

### Exit gate

- The engineering baseline can always be reproduced.
- Consumer changes cannot be confused with physically released engineering data.

---

## Phase 1 — Freeze one supported V1 configuration

**Objective:** Replace the current universal/configurable concept with one product a customer can actually build.

### Actions

1. Write a one-page V1 Product Definition containing:
   - product name and revision;
   - intended use and explicitly excluded uses;
   - customer skill assumptions;
   - what the download contains;
   - what the customer purchases;
   - required workspace, computer, printer, and tools;
   - supported operating system, QIDI Studio version, and RoArm firmware/controller version.
2. Confirm the V1 commercial format: customer-printed plastic parts plus a seller-supplied, labeled hardware/safety/tag pack. Classify each BOM row as `SELLER SUPPLIES`, `CUSTOMER PRINTS`, `CUSTOMER OWNS`, or `NOT IN V1`.
3. Select the exact reference keyboard model.
4. Select the exact phone, case, and installed orientation.
5. Select the exact USB cable, connector direction, tie, and strain-relief method.
6. Select the exact camera, lens, USB cable, mounting plate, support, and fasteners.
7. Select one V1 contact-tool route. Defer the other route to a later SKU unless both can be fully qualified without adding customer decisions.
8. Select the exact spring, rod or stylus, soft tip, insert, nut, pin, screw, washer, pad, adhesive, epoxy, and finish products.
9. Select the exact 610 x 457 x 18 mm board material and allowed thickness/flatness range.
10. Qualify the selected QIDI ABS Rapido primary material and exact X-Plus 4 preset; select and qualify the exact PETG spool for split adapters, TPU 95A spool for contact tips, and ASA only if a later revision releases the inactive fixed-mast fallback.
11. Freeze the exact arm-mounted camera, carrier, cable route, payload/collision limits, and eye-in-hand calibration contract. Keep the 2020 mast only as an inactive fallback requiring its own later release.
12. Create one controlled BOM. Give every purchased and printed item a unique part number.
13. Define supported substitutions. Anything not tested is labeled unsupported rather than left to customer judgment.

### Deliverables

- V1 Product Definition.
- Exact BOM with manufacturer part numbers, quantities, and approved sources.
- Seller-supplied/customer-printed/customer-owned classification and hardware-pack layout.
- Supported-device and software table.
- Selected-route record with no blank route.

### Exit gate

- Every item needed to build and operate one V1 unit can be ordered or printed from the controlled list.
- No customer-facing decision requires measurement followed by design work.
- No released instruction contains `as specified`, `candidate`, `schematic`, or an unresolved approval.

---

## Phase 2 — Close all physical and safety blockers

**Objective:** Turn the reference configuration into a fully specified mechanical and safety system.

### Actions

1. Complete every `FASTENER_MAP.csv` row with:
   - released screw and washer;
   - released anchor and manufacturer part number;
   - pilot and final bore;
   - bore depth or through-hole state;
   - installation face and method;
   - measured engagement;
   - torque;
   - qualification evidence and proof result.
2. Release board cut-size, thickness, squareness, diagonal, flatness, bow, hole-center, blind-floor, and pin-projection tolerances.
3. Release repair-versus-scrap rules for an off-center bore, breakout, veneer split, spinning anchor, damaged locator, and bowed board.
4. Design or select the reinforcement plate and release:
   - material and thickness;
   - length, width, radii, and edge condition;
   - exact location from board datums;
   - clamp stack and allowed overhang;
   - anti-slip treatment;
   - conflict clearance to feet, anchors, and cables.
5. Select the factory-clamp procedure and the manufacturer-approved tightening setting or method.
6. Select the E-stop/power-isolation hardware and define:
   - electrical rating and wiring scope;
   - a seller-supplied, enclosed, prewired, plug-compatible interface wherever technically possible;
   - the exact voltage domain and connector polarity/keying exposed to the customer;
   - that customer mains wiring and opening a powered enclosure are outside V1;
   - location outside robot reach;
   - latching and reset behavior;
   - prevention of unexpected restart;
   - functional acceptance test.
7. Release the board anti-shift system and proof method.
8. Freeze the camera support and run a movement/tip/strain-relief proof.
9. Freeze tool travel, spring force, retention, pull, creep, TCP, contact-force, and replacement limits.
10. Freeze phone no-go margins, clamp-contact limits, pad compression, cable bend radius, and disturbance test.
11. Freeze keyboard contact, pad compression, pose datum, yaw, and repeatability measurement methods.
12. Define every required measurement fixture, direction, preload, datum, tool, and uncertainty.
13. Complete a preliminary hazard analysis before powering the first release configuration. Identify and control unexpected motion, pinch/crush, device contact, drilling, hot-insert installation, electrical power, cable entanglement, printed-part failure, and printer heat/fumes.

### Deliverables

- Completed fastener map.
- Released reinforcement/clamp drawing.
- Released E-stop and anti-shift specification.
- Released camera-support drawing or purchased-part installation specification.
- Numeric keyboard, phone, tool, and measurement limits.
- Controlled recovery/scrap matrix.

### Exit gate

- A second engineer can build the mechanical system from the released BOM and drawings without asking what hardware or limit to use.
- No schematic object is treated as production hardware.
- Every hazardous or irreversible action has an approved test and failure response.
- No powered qualification begins until preliminary risk controls are implemented and verified.

---

## Phase 3 — Qualify the customer print system

**Objective:** Keep engineering diagnostics internal and give the customer prepared, validated QIDI print projects.

### Actions

1. Retain jobs 00A-00F and all parameter-selection coupons as internal engineering qualification assets, but execute job 00D only for a selected phone-stylus route.
2. Create one small customer **Print Verification Plate**. It verifies the released printer/profile, not customer-selected geometry. Include labeled checks for:
   - first layer and dimensional scale;
   - M3/M4 passage;
   - insert pocket;
   - nut capture;
   - locator/service fit;
   - representative bridge and support-removal surface.
3. Define simple go/no-go methods for the verification plate. If it fails, correct the printer or material profile; do not scale production geometry.
4. Convert released production jobs into approximately seven to nine customer print packs for the selected V1 route. Keep each large station on its own plate.
5. Make the tested native QIDI/3MF project the primary customer file. Also generate each applicable customer stage's relevant STL source copies from the canonical models. Label them `STL SOURCE - USE ONLY THROUGH THE NAMED PRINT PACK`; exclude traceability-only and inactive-route models.
6. For every print pack provide:
   - friendly print-order name plus immutable internal job ID;
   - bed preview and finished-part photo/render;
   - exact material and color convention;
   - supported QIDI Studio version and profile;
   - expected time and filament mass from the final slice;
   - support, brim, seam, and cooldown instructions;
   - object count and part IDs;
   - post-processing and inspection card;
   - reprint/reject rule and destination hardware bag.
7. Confirm every plate remains inside the released machine envelope. Treat the existing 295 x 295 mm XY value as the starting candidate, then physically establish X, Y, and Z clearance to the carriage, enclosure, purge area, and build-plate exclusions before calling the envelope protected.
8. Prohibit customer auto-orientation, object movement, XY scaling, plate merging, or unapproved profile substitution.
9. Emboss or deboss part number, revision, orientation, left/right, and contact face wherever legible and structurally safe.
10. Print two complete customer sets on the reference QIDI Plus4 using only the released projects.
11. Inspect critical layers in QIDI Studio and physically inspect every datum, hole, insert pocket, base, seam, and service feature.
12. Record all permitted post-processing. Filing or sanding a released datum is not a normal customer operation.

### Deliverables

- Customer Print Verification Plate and card.
- Released customer QIDI/3MF projects.
- Print-pack previews and inspection cards.
- Friendly part catalog and label set.
- Two physically accepted print sets.

### Exit gate

- Two consecutive complete print sets pass without CAD changes, scaling, hidden slicer changes, or improvised datum repair.
- Every customer-visible part can be identified without opening an STL.
- The customer can sort all parts into milestone bags from the supplied catalog.

---

## Phase 4 — Make board preparation and mechanical assembly customer-safe

**Objective:** Make the no-router/no-CNC board process accurate, recoverable, and easy to understand.

### Actions

1. Keep both released drill-guide formats but present one recommended path:
   - Letter pages 1-3: reference only;
   - Letter pages 4-12: nine 1:1 working tiles with 12 mm overlap;
   - 24 x 36: one-sheet print-shop alternative.
2. Create one tile-map page showing page positions, overlap IDs, FRONT, +Y, board edges, and forbidden marks.
3. Provide full-scale silhouettes for every drill bit, anchor, screw, washer, and locator.
4. Specify the minimum rule length, square, straightedge, drill guide, clamps, backing/workholding, PPE, and depth-stop setup.
5. Provide a scrap-board practice action using the released board/anchor stack.
6. Add close-ups for scale measurement, tile registration, center punch, depth stop, blind floor, anchor installation, underside inspection, and dry fit.
7. Evaluate a printed transfer/drill-bushing aid. Release it only if physical testing proves that it reduces error without creating false accuracy.
8. Make the reinforcement plate, clamp position, E-stop, feet, and anti-shift method part of the same board milestone.
9. Build at least two accepted engineering/draft-workflow boards before freezing the customer process. Phase 8 separately requires a fresh first-customer board.

### Deliverables

- Released board guide set and tile map.
- Board tool/consumable card.
- Board acceptance card.
- Reinforcement, clamp, E-stop, feet, and anti-shift installation diagrams.
- Board troubleshooting and scrap matrix.

### Exit gate

- A customer can complete the board without selecting hardware or inventing tolerances.
- All thirteen centers, four blind locator bores, nine anchors, reinforcement, and safety hardware pass from the customer workflow.
- An out-of-limit condition clearly says whether to fix, replace, or stop.

---

## Phase 5 — Release software, vision, robot programs, and commissioning

**Objective:** Replace the current software-engineering workflow with one guided customer setup path.

### Actions

1. Correct the invalid detector example: remove unsupported `--tag-size-m` and include required `--output`.
2. Resolve the Step 13 all-six-tags versus T0-T3 acceptance contradiction.
3. Add the required Step 12 tag-map generation/handoff before camera calibration.
4. Pin supported dependency versions instead of open-ended minimum versions.
5. Support one operating system for V1 and test on a clean machine.
6. Provide one launcher, such as `START ROCELL SETUP`, that:
   - checks the computer and camera;
   - creates or verifies the environment;
   - discovers and identifies the camera;
   - shows live focus/exposure guidance;
   - captures and rejects inadequate ChArUco frames;
   - calibrates the camera;
   - captures the named FOV pose set;
   - detects the required tags;
   - saves reports, previews, and a human-readable PASS/FAIL summary.
7. Keep command-line instructions in a service appendix only.
8. Supply approved homing/reference, empty-cell, and final-process robot programs with version and checksum.
9. Freeze controller, firmware, speed, acceleration, clearance, force, and travel limits.
10. Define a named set of camera FOV and empty-cell robot poses; do not accept twenty nearly identical images.
11. Add dedicated E-stop tests for stop behavior, reset, and unexpected restart prevention.
12. Provide backup, restore, recalibration, and retry procedures.

### Deliverables

- Guided setup launcher.
- Pinned installer/environment.
- Fixed detector and map workflow.
- Named calibration and FOV pose set.
- Released robot programs and operating limits.
- Human-readable calibration and commissioning report.

### Exit gate

- A clean supported computer completes setup without manual package installation or command repair.
- Camera calibration, tag visibility, E-stop, empty motion, and controlled first contact pass from the customer directions.
- Every retry creates a traceable new attempt without overwriting accepted evidence.

---

## Phase 6 — Build the customer documentation package

**Objective:** Present only what the customer needs, at the moment it is needed.

### Actions

1. Keep the current 16-step system as the engineering/manufacturing/service backbone in a separate controlled archive, not inside the normal customer download.
2. Create the ten customer stages defined in `02 - CUSTOMER BUILD STRUCTURE.md`.
3. Apply the instruction, naming, visual, and troubleshooting standards in `03 - CUSTOMER INSTRUCTION AND FILE STANDARD.md`.
4. Create one customer Build Passport instead of exposing scattered JSON, CSV, hash, and signoff operations.
5. Produce:
   - one-page Start Here sheet;
   - compatibility and exact BOM;
   - print manual;
   - assembly and setup manual;
   - troubleshooting guide;
   - normal-use quick start;
   - maintenance/recalibration matrix;
   - spare-part catalog;
   - software recovery guide;
   - safety and emergency recovery guide.
6. Define prerelease service readiness: maintenance intervals, spare IDs, recalibration triggers, backup/restore, support intake, known failure paths, warranty/return handling, and missing-part replacement.
7. Trace every customer check back to the applicable internal engineering gate.
8. Remove duplicated or contradictory actions between the customer guide, detailed manual, and per-step folders.
9. Regenerate and verify every customer PDF and linked file after controlled-source changes.

### Deliverables

- Ten-stage customer package.
- Build Passport.
- Customer manual set and visual library.
- Internal-to-customer traceability matrix.

### Exit gate

- No customer action requires a hidden value or a second manual to discover its basic method.
- Every customer-facing command, link, filename, quantity, and acceptance value is tested.
- Every physical action is represented once in the primary workflow.

---

## Phase 7 — Complete the engineering qualification build

**Objective:** Establish the released values before testing the consumer experience.

### Actions

1. Build a full reference unit using the internal controlled Steps 00-15.
2. Complete all selected measurement gates with real evidence.
3. Qualify all print profiles, coupons, first articles, production parts, and spares.
4. Complete the board, reinforcement, E-stop, anti-shift, camera, tool, and robot-program tests.
5. Run all repeatability, force, proof, clearance, vision, and final commissioning tests.
6. Correct source data, CAD, processes, or limits when a gate fails; do not waive a failure through wording.
7. Freeze a golden reference unit and its complete as-built record.
8. Generate a read-only customer release candidate from the accepted configuration.
9. Finalize the customer documents and Build Passport with actual accepted photos, values, time, material, and recovery results from the engineering build.
10. Qualify the seller-supplied kit pack-out:
    - incoming inspection and supplier/lot traceability;
    - dimensional sampling of critical anchors and fasteners;
    - bag count and label verification;
    - second-person or scan-assisted pack check;
    - packed-contents photograph;
    - reinforcement-edge and E-stop-assembly inspection;
    - shipping-damage protection;
    - received-kit inventory by an unfamiliar person;
    - missing/damaged-part replacement and return workflow.
11. Define the intended duty cycle and complete a system reliability test covering repeated keyboard/phone interaction, spring/tip/pad creep and wear, anchor/clamp retention, board flatness, tag adhesion/optical stability, camera drift, cable disturbance, and repeated device removal/reinstallation.

### Deliverables

- Fully accepted engineering unit.
- Complete engineering evidence package.
- Golden configuration record.
- Read-only customer release candidate.

### Exit gate

- Every selected internal step is `COMPLETE`.
- Every required print job has reached its intended accepted state.
- Engineering design release and seller kit release decisions are signed for the reference configuration.
- No open P0 or P1 engineering issue remains.
- The seller pack-out and intended-duty-cycle reliability tests pass.
- The customer release candidate reflects the accepted engineering build rather than provisional values.

---

## Phase 8 — Run the first-customer build

**Objective:** Prove that a maker can complete the product without designer knowledge.

1. Follow `04 - FIRST-CUSTOMER VALIDATION PLAN.md` exactly.
2. Use a clean bench, fresh board, fresh print set, and read-only customer package.
3. Do not open CAD, engineering source, or private notes.
4. Record every pause, reread, search, mistake, support need, reprint, and undocumented assumption.
5. Finish the build session before revising instructions unless safety requires stopping.
6. Correct P0-P2 defects in their owning engineering, software, print, or documentation source.
7. Repeat every affected stage and then run a second clean end-to-end build.

### Exit gate

- Zero P0 issues.
- Zero unresolved P1 issues.
- No undocumented hardware, tool, value, or decision.
- No CAD, JSON, or source-file edit during the customer build.
- All ten customer stages pass using only stated checks and recovery paths.

---

## Phase 9 — External beta and commercial release candidate

**Objective:** Remove the designer’s knowledge advantage and prove repeatability across unfamiliar builders.

### Actions

1. Recruit at least three, preferably five, builders who did not develop the product.
2. Confirm each tester matches the stated customer skill profile.
3. Give each tester the same released files and BOM state.
4. Observe without coaching unless safety requires intervention.
5. Record time, errors, questions, rework, print failures, measurement failures, and support contacts by stage.
6. Correct every P0/P1 and repeated P2 issue.
7. Repeat any affected beta stage with a fresh builder.
8. Verify the preliminary hazard analysis and all design risk controls before any powered beta. Complete the final independent/applicable product risk, safety, and market-compliance review before sale.
9. Freeze the release candidate and run one final package smoke test from the distributed archive.

### Commercial exit gate

- No safety intervention was required.
- No builder needed an undocumented engineering decision.
- Every builder identified all parts and hardware correctly.
- No irreversible step was completed from an ambiguous instruction.
- All builds reached the same mechanical and calibrated state.
- All support questions have documented answers.
- Release scorecard is complete and signed.

---

## Phase 10 — Operate and improve the released product

**Objective:** Monitor and support the product after prerelease service readiness has already been completed.

### Actions

1. Monitor field issues, support questions, returns, near misses, and repeated failure modes by product revision and action ID.
2. Maintain spare availability and supplier-obsolescence plans.
3. Issue controlled safety, compatibility, software, and instruction updates.
4. Regression-test every later CAD, print, BOM, software, and instruction change.
5. Define when a field update requires customer notification, reinspection, recalibration, or product recall action.
6. Feed observed service data back into maintenance intervals and next-release design work.

### Exit gate

- Released customers remain supported without exposing unreleased engineering choices or losing revision traceability.

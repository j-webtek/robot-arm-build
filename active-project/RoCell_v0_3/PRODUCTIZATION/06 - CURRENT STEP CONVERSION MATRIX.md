# Current-step conversion matrix

This matrix preserves the technical intent of the current 16 steps while simplifying what the customer sees.

| Current step | Internal engineering purpose retained | Customer presentation | Required productization closure |
|---|---|---|---|
| 00 — Measure/print | Hardware measurement, profiles, coupons, parameter transfer, first articles, traceability, production release | Stages 1-3: compatibility, one printer check, prepared QIDI projects, simple inspection and sorting | Freeze hardware/routes; keep engineering diagnostics internal; release native projects, part catalog, go/no-go plate, bag labels, and exact material/profile. |
| 01 — Board | Board finish, layout transfer, 13-center audit, blind bores, anchors, locator pins, dry fit | Stage 4: one guided board workflow | Complete fastener map; release board/center tolerances, tools, guide choice, practice, close-ups, and repair/scrap matrix. |
| 02 — Arm | Clamp load path, reinforcement, board flatness, motion clearance, cutoff | Stage 4: supplied/exact reinforcement, clamp, feet, anti-shift, and E-stop actions | Release plate drawing/part, exact placement, clamp method, E-stop wiring/behavior, proof, and recovery. |
| 03 — Master | Establish keyboard coordinate system and master retention | Stage 5: identify, park slider rearward, seat, fasten, and check master | Exact bag/stack diagrams, start/tighten sequence, locator/rocking method, engagement proof, torque record, recovery. |
| 04 — Slave | Seam-located slave without overconstraint | Stage 5: confirm no slave pins, hand-seat seam, fasten, check plane | Explicitly prohibit drilling/adding slave pins; record torque/engagement/bottoming; add rocking acceptance; show seam/post/relief close-ups and interference recovery. |
| 05 — Keyboard | Device retention and repeatability | Stage 5: route cable, set contact indicator, cycle | Fixed supported keyboard; released pads/adhesive/contact indicator; fixed pose/yaw datums; cycle worksheet and wear limits. |
| 06 — Phone base | Establish service-station coordinate system | Stage 6: seat base and install TCP-side stack | Complete PT-HOLD-TCP stack; label round/radial/TCP and protected rail holes; define play/seat measurement. |
| 07 — Rail/cartridge fit | Dry-seat keyed service parts | Stage 6: seat rail and INSTALL cartridge before screws | Close-up keys/orientation; factory-qualify or supply simple go/no-go repeatability method; route-specific recovery. |
| 08 — Rail/cartridge secure | Shared-stack, nut, insert, and datum retention | Stage 6: one labeled hardware sequence | Complete PT-HOLD-R1/R2; release M3/M4 sequence, torque, engagement method, cross-pattern, and stack diagrams. |
| 09 — Phone/cable | Device seating, cable retention, safe clamp contact, cycles | Stage 6: use exact phone/cable, marked clamp setting, illustrated route | Freeze device/parts; numeric contact/bend/pull limits; off-device test fixture; cycle sheet; no subjective `just touches`. |
| 10 — Phone no-go | Prove glass/button/camera/USB clearance | Stage 6: use device-specific overlay and go/no-go checks | Release numeric margins for all regions, uncertainty method, cable-disturbance test, and compatibility/reconfiguration tree. |
| 11 — Tag marks | Transfer six centers/orientations from controlled guide | Stage 7: remove devices, protect fixtures, and transfer six named marks only | Repeat guide choice, pages 4-12, overlap/registration; remove early-tag implication; record six position checks. |
| 12 — Tags | Apply and measure six tags | Stage 7: use exact tags, registered tool, and simple worksheet/fixture | Freeze stock/adhesive/cleaning/dwell/removal; remove/store the temporary application fixture; accessible metrology; worked method; explicit tag-map generation handoff. |
| 13 — Camera | Mechanical retention, calibration, FOV/tag proof | Stage 8: install exact support and run one guided setup | Retain and regression-test the corrected non-overwriting detector batch and aligned 20/20 six-tag criteria; close the arm-camera architecture hold; pin dependencies; release the exact route-specific hardware/pose list, launcher, live guidance, reports, retry, and recovery. |
| 14 — Tool | Assemble and qualify selected compliant-tool route | Stage 9: assemble one exact route and use supplied checks | Select route; exact spring/tool/insert/fasteners; release travel/force/retention/creep/TCP limits and fixtures; add route-specific visuals. |
| 15 — Final release | Static proof, repeatability, E-stop, empty motion, contact, evidence/signoff | Stage 10: remove devices/tool, run guided empty tests, then controlled commissioning | Supply programs/limits; dedicated E-stop acceptance; load fixtures/directions; observer/witness rule; exclusion-zone and first-contact visuals; separate design, kit, and unit-commissioning decisions. |

## Cross-package corrections before customer release

1. **COMPLETED IN THE ENGINEERING PACKAGE:** the detailed detector batch matches the parser, refuses overwrites, counts inputs, and fails on any bad frame. Preserve this in customer conversion and regression tests.
2. **COMPLETED IN THE ENGINEERING PACKAGE:** Step 13 actions and tests consistently require 20/20 detection of T0-T3/K0/P0 and a solved T0-T3 board pose. Preserve this in customer conversion and regression tests.
3. **COMPLETED IN THE ENGINEERING PACKAGE:** drill guides use the current blue locator/orange anchor symbol system with redundant non-color labels and shapes. Preserve this in customer conversion and regression tests.
4. **COMPLETED IN THE ENGINEERING PACKAGE:** Step 11 distinguishes tiled Letter pages from the single-sheet 24 x 36 guide and controls overlap/registration at Actual Size. Preserve this in customer conversion.
5. **COMPLETED IN THE ENGINEERING PACKAGE:** Step 12 regenerates and validates the measured-installation tag map, records its SHA-256, and hands it to Step 13. Preserve this in customer conversion.
6. **COMPLETED IN THE ENGINEERING PACKAGE:** Step 04 requires at least 5 mm thread engagement, no bottoming/projection, 0.25-0.35 N·m final torque, and explicit rocking acceptance in checks 04-D/04-E. Preserve this in customer conversion and regression tests.
7. Replace generic `As specified` quantities and unresolved approvals in customer content.
8. Give every current failure path a symptom-specific return action, allowed repair, and scrap rule.
9. Separate customer files from traceability-only STL copies so the wrong models cannot be printed accidentally.
10. Preserve all current internal STOP gates even when the customer wording is simplified.

## Traceability rule

Every customer action and PASS check must identify:

- its current internal step;
- its controlled source requirement;
- the evidence produced by the customer workflow;
- the downstream stages invalidated if that evidence later fails.

Simplification may hide engineering mechanics from the customer. It must not remove the underlying safety, fit, repeatability, or release requirement.

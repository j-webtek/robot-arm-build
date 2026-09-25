# Fastener and print user-experience guide

**Revision:** `RC03-INT-R1`

This guide explains the assembly aids built into each printable part. Numeric release criteria remain controlled by `config/measurement_record.json` and `PRINT_READINESS.md`.

## Material and preset rule

- QIDI ABS Rapido is the primary rigid material for jobs 00A, 00B, 00C, 00E, 00F, 01, 02, 03A, 03B, 03C1, 03C2, 03D, and 04A.
- Use the exact process named in the job's `.PRINT_SETTINGS.md`; the tray, cradle, precision, general, and calibration processes are not interchangeable even though they share one ABS filament preset.
- PETG remains only for split-adapter jobs 00D, 04B, and 04C and for inactive fallback plate 03C3. TPU 95A remains mandatory for contact-tip jobs 05A-05D. ASA remains an inactive fixed-mast fallback material.
- Do not invent PETG, TPU, or ASA temperatures from the ABS values. Identify the exact physical spool, calibrate its vendor preset, record the material gate, and then print the matching coupon.
- Never globally scale an STL to compensate for material shrink. A failed fit returns to the matching coupon, controlled parameter, and regeneration workflow.

## Shared station conventions

- Locator pins carry lateral loads. M4 station screws hold each station's continuous base against the board at three broad-triangle retention zones.
- The keyboard-left master and phone/TCP station each use one round socket plus one axis-relieving radial slot.
- The keyboard-right station is a seam-located slave. It deliberately has no independent locator pair.
- Every station uses three broad-triangle retention screws. The keyboard clamp screw and the two phone-rail-side screws are shared retainers through the removable part and station.
- Start all three screws by hand before tightening. Use 0.25-0.35 N m only after the board-interface stack test passes.
- Keep each washer in its printed recess. Stop if a washer dishes, a hole whitens, a station creeps, or the base lifts near a retention zone.
- Never enlarge a released locator socket to make it fit. Return to the profile-specific locator coupon and update the controlled parameter.
- Locator board bores are blind. Use a brad-point bit and positive depth stop.
- Printed hole finishing is by hand using only coupon-selected sizes. Do not power-ream an assembled station or any TPU part.
- Every heat-set entry has an alignment lead-in. The selected straight pocket, actual insert, print axis, and profile control retention.

## Part-by-part handling

| Part | Built-in aid | User action |
|---|---|---|
| Keyboard left/master station | `RC03-L MASTER` title, round/radial locator sockets, printed seam posts, two washer recesses, and rear clamp guide tracks | Confirm job 00A selections; place the padded slider first; seat on both pins; start two fixed screws and the shared slider screw; do not force the seam |
| Keyboard right/slave station | `RC03-R SLAVE` title, round/radial seam sockets, relieved hold-downs, two washer recesses, and rear clamp guide tracks | Mate to the accepted master first; place the padded slider; start two fixed screws and the shared slider screw; tighten while checking seam gap/flushness; never add locator pins |
| Keyboard clamp sliders | Guided runner pockets, rounded adjustment slot, molded scale, gusseted face, and face-pad recess | Install the face pad; pass the low-profile M4 screw through the slider and station into the board anchor; slide only to contact and retighten |
| Phone/TCP station | `RC03 PHONE+TCP`, `TCP R3`, `USB`, and `TOP` titles, fixed phone datums, keyed receiver, and keyed rail seat | Install the Job 00B-qualified M3 inserts off-board; seat on both pins; place the accepted Job 03C1 rail before the two shared rail/station screws; use its production-qualified saddle for the cable route |
| Replaceable phone clamp rail | `RC03 CLAMP RAIL` and `NUT` titles, tower gussets, 7.2 mm lower-half hex seats, 4.0 mm horizontal screw axes, 5.6 x 2.2 mm tie saddle, and underside key pockets | On Job 03C1, bench-qualify both real M4 nuts/screws and the nominal 4.8 mm tie around the actual cable; then seat both molded keys before the shared board screws and use fingertip clamp force only |
| Phone TPU caps | Flared bore entry, seating witness and rounded contact face | Remove flash; seat to the witness; perform the actual-hardware pull test; replace polished, split, or loose tips |
| TCP datum cartridges | Keyed/clipped corner, orientation mark, recessed fastener seats, crosshair and protected divot | Keep slicer object `calibration_puck_1` as 03D-A and `calibration_puck_2` as 03D-B; qualify both separately; select INSTALL by the controlled normalized play/height-range score; label the other accepted part `SPARE - TCP RECALIBRATION REQUIRED` |
| Direct-tag application frame | 55 mm opening, center witnesses, +Y mark and finger relief | Verify the opening and flatness; align it to the 1:1 template; apply a full-surface adhesive tile; lift the tool without dragging the tag |
| Station locator gauge | Production-axis round and radial-slot ladders with labels and lead-ins | Measure actual pins; select independently for tray/service profiles; require 20 hand cycles, no damage and no more than 0.15 mm play |
| Phone width coupon | Production width and rail-height section | Test the actual phone in its final case state without forcing it |
| Keyboard corner coupon | Production corner walls and support plane | Confirm both datum clearances and no keyboard rocking |
| Seam section of station locator gauge | Independently labeled 8.2/8.3/8.4 mm round sockets and Y-radial slots in the production profile | After job 01, measure its actual posts and independently select the smallest tool-free round-socket diameter and radial-slot width; station-pair gap/flush is measured only after job 02 |
| Hardware gauges | Labeled M3/M4/M5 clearance and seat rows | Record the smallest free passage/flat seat under the exact profile; do not transfer results between profiles |
| Legacy service-profile M4 captive-nut gauge | Superseded top-loading 7.2/7.4/7.6 mm screening channels from the physical Job 00B plate | Retain as historical evidence only. The loose N7.4 result is a FAIL; qualify the redesigned seat on Job 03C1, not this gauge |
| Vertical M3 insert gauge in job 00B | Service-station profile and production axis | Select the TCP receiver insert pocket; record depth, squareness and resistance to rotation |
| Legacy cable-saddle gauge | Labeled narrow tie tunnels from the physical Job 00B plate | Retain the failed feed result as historical evidence. No replacement coupon is required; qualify the adopted 5.6 x 2.2 mm production saddle on Job 03C1 |
| Camera plate | `CAM`/`MAST` labels and recessed M5 tracks | Fixed-mast fallback only—not an arm-camera adapter; after formal fallback release, measure blind camera thread depth and confirm screw length before tightening |
| Compliant tool body/cap | Dedicated gripper flats, keyed cap, insert lead-ins and recessed heads | Install inserts square; keep seams off grip faces; alternate screw tightening; bag the spare cap |
| Stylus collar / rod bushing | Split retention geometry and measured sliding interface | Qualify dry fit first; if needed, use only a minimal plastics-compatible removable compound after final thin-part pull/cycle, creep, and removability tests |
| Optional mast feet | Washer seats, paired clamp bolts, slit, ribs and socket labels | Print one first; tighten clamp bolts alternately; inspect immediately and after 24 hours |

## Board hardware workflow

1. Test the exact board cutoff, tee nut or threaded insert, candidate screw lengths, washer and torque. Current station CAD uses no seating shims.
2. Require at least 5 mm thread engagement, no bottoming, and no projection below the feet.
3. Complete three assemble/remove cycles at 0.25-0.35 N m.
4. Apply a 50 N axial proof for 60 seconds; reject insert rotation or veneer damage.
5. Print the setup template at Actual Size and verify both 100 mm scale bars.
6. Drill small pilots through the generated guides.
7. Drill locator bores with the 6 mm brad-point bit and positive depth stop.
8. Dry-fit all four pins and three stations before using epoxy.
9. Install nine M4 board interfaces and check underside clearance before adding feet.

## Direct-tag workflow

1. Allow the equally sealed board faces to cure fully.
2. Clean each tag region with a finish-compatible method and a lint-free wipe.
3. Verify tag ID, 55.0 mm tile, 40.0 mm detection edge, and +Y orientation.
4. Register the application frame to the generated paper template.
5. Apply the full-surface matte adhesive from one edge while burnishing outward to avoid bubbles.
6. Remove the tool vertically without shifting the tile.
7. Measure installed center, yaw, adhesive-plus-stock optical Z, and edge lift.
8. Require the formally released route-specific visibility set at every required pose. For the fixed-camera fallback, require 20/20 static detections for each ID before camera-to-board calibration; do not apply that evidence to an arm-mounted eye-in-hand camera.

## Installation sequence that minimizes rework

1. Load the confirmed QIDI ABS Rapido filament preset and exact job processes; print and record required ABS diagnostic jobs 00A, 00B, 00C, 00E, and 00F. Add PETG job 00D only when `phone_stylus_route` is selected and its exact spool preset is recorded.
2. Feed every accepted size back to the controlled parameters and regenerate.
3. Print/accept the keyboard master, then the slave and the pair.
4. Print/accept the phone/TCP station, keyboard sliders, and phone rail.
5. Finish the board and pass its flatness, thread-stack, template-scale, and blind-bore checks.
6. Dry-install stations with their sliders/rail but without devices; confirm continuous base contact at every retention zone.
7. Install direct tags and complete metrology/vision acceptance.
8. Load keyboard, phone, and TCP cartridge; complete ten device cycles.
9. Complete ten station remove/reinstall cycles and calculate X/Y/Z/yaw ranges.
10. Recheck low-torque ABS station/tool interfaces and PETG split-adapter retention after 24 hours and after major temperature or humidity changes.

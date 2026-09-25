# RoCell RC03 print enhancement and release plan

**Revision:** `RC03-INT-R1`  
**Printer:** QIDI Plus4  
**Provisional protected envelope:** 295 x 295 x 275 mm; verify physically on the actual machine

The exact integrated architecture, board method, datum strategy, direct-tag coordinates, numeric physical gates, and assembly sequence are controlled in `RC03_INTEGRATED_BUILD_PLAN.md`. This document is the operator-facing per-print plan.

## Common professional-print standard

Every controlled print must have:

- a unique job ID, part manifest, process profile, locked orientation, and 3MF sidecar;
- engraved/debossed part identity, revision, +Y/contact/orientation witness where applicable;
- hand-startable fastener entrances, rounded slot ends, washer/head seats, and accessible tools paths;
- fillets/gussets at load transitions and no unsupported hidden cavities;
- explicit post-print measurements and evidence fields;
- one first article before releasing a mating, repeated, or spare part;
- per-job QIDI Studio import/slice/save/reopen evidence for every non-diagnostic plate;
- quarantine rules for warp, cracks, whitening, delamination, blocked passages, unreadable identity, or untraceable material/process.

Do not globally XY-scale a production part to solve a fit. Select the relevant diagnostic coupon, update the controlled parameter, regenerate, and repeat the affected gate.

## Release sequence

1. Confirm printer/nozzle and calibrate every exact material lot/profile.
2. Print required diagnostic jobs 00A, 00B, 00C, 00E, and 00F; print 00D only for an explicitly selected `phone_stylus_route`.
3. Record actual device/hardware measurements and all coupon choices.
4. Regenerate and pass `geometry_matches_measurements`.
5. Print/accept job 01 before job 02.
6. Print/accept the station pair, service station, keyboard sliders, phone rail, board setup tool, and TCP cartridges.
7. Fabricate the board with the 1:1 hand-drill template; no router or CNC.
8. Install and measure direct tags.
9. Complete station, keyboard, phone, and cartridge repeatability.
10. Release the selected compliant-tool route, TPU parts, camera parts, and optional mast through their existing gates.
11. Resolve the arm-camera architecture hold, perform the formally released route-specific calibration, and complete empty-cell motion checks before device contact.

## Per-job plan

### Job 00A - keyboard-station diagnostics

Contents:

- keyboard corner fit coupon;
- station locator gauge with 6 mm board-pin and 8 mm printed seam-post sections;
- tray-profile clearance ladder;
- tray-profile M4 washer-seat ladder.

Purpose:

- select actual keyboard datum clearance;
- independently select the 8.2/8.3/8.4 mm seam round-socket diameter and radial-slot width for the printed 8 mm posts without force, rocking, yaw, or tool-assisted removal;
- select round locator and radial-slot sizes from actual 6 mm pins;
- prove 20 pin cycles, hand service, inversion retention, no whitening/cracking, and no more than 0.15 mm play;
- select the exact station-profile hole and washer seats.

### Job 00B - phone/TCP-station diagnostics

Contents:

- phone width/rail coupon;
- station locator round/slot ladder printed in the service-station profile;
- top-loading captive M4 nut ladder reproducing the horizontal clamp axis;
- vertical M3 insert ladder;
- cable-tie saddle ladder;
- service-profile M4 washer-seat ladder.

Purpose:

- verify the final phone/case state and side-feature keepouts;
- select service-profile locator dimensions independently of job 00A;
- qualify the phone rail's captive M4 nut channels and the TCP receiver's vertical M3 inserts;
- qualify the actual tie/cable bend path;
- select service-profile washer seating.

### Job 00C - compliant-tool diagnostics

Qualify the actual RoArm grip interface, spring seats, precision-profile M3 inserts, and M3 head recess. Do not release the full compliant tool from nominal dimensions alone.

### Job 00D - phone-stylus-route diagnostics only

Run this job only when `phone_stylus_route` is selected. Qualify stylus diameter and measured dry fit. If dry fit is insufficient, qualify the minimum plastics-compatible removable compound on the final thin collar through pull/cycle, removability, and 24-hour creep testing. RC03 has no radial stylus screw.

### Job 00E - general setup diagnostics

Qualify general-profile clearances, heads/washers, camera hardware, and preliminary rigid-peg TPU retention. Final TPU release still requires the real flexible first article.

### Job 00F - TCP-cartridge profile diagnostics

Qualify the calibration-profile passage and screw/head or washer interface under the exact 0.16 mm process used for the datum cartridges.

### Job 01 - `keyboard_station_left.stl`

Stage: first article.

Inspect:

- master identity and revision;
- round/slot socket finish and insertion lead-ins;
- three M4 hold-down passages and direct-board base contact at all retention zones;
- front/left device datums and the open direct-board keyboard support region;
- seam master features;
- clamp track and shared clamp/station board-retainer passage;
- free-state corner lift and support-plane flatness.

Release job 02 only after this station is accepted.

### Job 02 - `keyboard_station_right.stl`

Stage: production after job 01.

Inspect:

- slave identity and absence of an independent pin pair;
- relieved board-retention holes and continuous direct-board base contact;
- seam fit to the accepted master;
- clamp track/shared board-retainer interface;
- combined support plane, seam gap/flushness, keyboard fit, and rocking.

Then complete ten station and keyboard cycles.

### Job 03A - `phone_tcp_station.stl`

Stage: first article.

Inspect:

- locator sockets, three retention passages, and continuous direct-board base contact;
- fixed phone datums and all measured keepouts;
- keyed TCP receiver, M3 insert pockets, and datum-seat flatness;
- replaceable rail ledge;
- replaceable-rail interface plus the rail-mounted tie saddle, connector path, and bend radius;
- station free-state flatness and phone support plane.

Then complete ten service-station and phone cycles.

### Job 03B - `keyboard_rear_clamp.stl` (quantity two)

Inspect runner fit, slot finish, gussets, pad recess, identity, scale/center witnesses, and pair matching. Clamp force is only enough to remove motion; the sliders do not locate the stations.

### Job 03C1 - `phone_clamp_rail.stl`

Stage: first article.

Before Job 03A, bench-check the loose rail's two redesigned 7.2 mm lower-half hex seats with the actual M4 nuts/screws and feed the nominal 4.8 mm tie around the actual cable through the 5.6 x 2.2 mm saddle. After Job 03A exists, inspect rail seating, tower-root ligaments, horizontal screw axes, side-feature keepouts, TPU-tip travel, and removal without disturbing the station. Prove the actual phone before releasing normal service.

### Job 03C2 - `tag_application_frame_55mm.stl`

Inspect the 55 mm opening, flatness, center/+Y witnesses, finger relief, and clean vertical removal. Verify both 100 mm scale bars on the generated board setup template before installing a direct tag.

No printed tag holder remains installed on the board.

### Job 03C3 - `camera_plate_universal.stl`

Fixed-mast fallback only; this is not an arm-camera adapter. Keep the job on hold until a controlled camera-architecture revision explicitly releases the fallback. Then measure the camera's blind thread and selected T-slot hardware, and inspect strap slots, ligaments, washer seats, cable direction, and screw-bottoming clearance.

### Job 03D - `calibration_puck.stl` (quantity two)

Stage: first article plus measured spare.

Inspect key/orientation, fastener seats, top flatness, crosshair, divot, and surface finish. Disable ironing. Keep slicer object `calibration_puck_1` as 03D-A and `calibration_puck_2` as 03D-B, then qualify each cartridge separately: no more than 0.15 mm lateral play and 0.10 mm installed-height range over ten cycles. Select `INSTALL` using the controlled normalized play/height-range score and label the other accepted part `SPARE - TCP RECALIBRATION REQUIRED`.

### Job 04A - compliant tool body and caps

Inspect grip faces, body straightness, guide bore, spring chamber, insert axes, keyed cap seating, 3-6 mm smooth travel, full return, and no coil bind. Retain one cap as a labeled spare.

### Job 04B - phone stylus collars

Release only after the selected stylus retention method passes final thin-part pull, cycle, 24-hour creep, and capacitive-function checks.

### Job 04C - keyboard rod bushings

Deburr and measure the actual rod. Qualify retention and 24-hour creep without an unvalidated radial screw in the thin flange.

### Jobs 05A/05B - phone TPU tips

Print one first article, pull-test it on the actual M4 clamp hardware, then release three more. Label two installed and two total spares.

### Jobs 05C/05D - keyboard TPU tips

Print one first article, pull-test it on the actual 6 mm rod, then release three more. Label installed parts and spares.

### Job 06 and jobs 07A/07B - optional camera mast

Fixed-mast fallback only; these parts do not implement the intended arm-mounted camera. The `fixed_camera_fallback_architecture_released` gate must remain blocking until the camera decision is `ALIGNED_AND_REVISED` and that controlled decision explicitly authorizes this fallback. Only then use the final ASA lot to qualify the actual 2020 socket, M5 nut trap, production-axis clearances, and washer seats. Print/accept one mast foot before the second. Inspect clamp cracks immediately and after 24 hours.

## Assembly UX controls

- All repeatable board features are named in the generated layout and drawing.
- Round locators and radial slots are visibly different and labeled.
- Master/slave identity is readable after printing.
- Service parts can be replaced without disturbing station registration.
- Wear faces use replaceable pads or TPU tips.
- Every adjustable part has a center/scale witness and a clear contact direction.
- All six direct tags share the finished board plane and have generated +Y/center witnesses.
- Board centerline and factory-arm clamp position are marked; a measured metal underside plate spreads arm load.

## Change control

Any later geometry or process change must update the design revision and regenerate the layout hash, CAD exports, 3MFs, sidecars, manifests, drawings, fiducial map, manual blocks, job cards, readiness report, validation report, previews, PDFs, and checksums. A PASS from another material, nozzle, profile, print axis, or revision does not transfer automatically.

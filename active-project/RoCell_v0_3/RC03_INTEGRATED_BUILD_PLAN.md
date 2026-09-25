# RoCell RC03 integrated build plan

**Controlled design revision:** `RC03-INT-R1`  
**Printer:** QIDI Plus4  
**Nominal build volume:** 305 x 305 x 280 mm  
**Provisional protected envelope:** 295 x 295 x 275 mm; physical machine-clearance verification required  
**Board process:** purchased or hand-cut rectangular board; hand drilling with a printed 1:1 template and depth stops; no router or CNC

## 1. Outcome

RC03 replaces the collection of independently aligned fixture pieces with three removable, board-registered printed stations:

1. A left/master keyboard station.
2. A right/slave keyboard station.
3. A combined phone/TCP service station.

The six AprilTags move directly onto the finished sealed board. The two keyboard clamp sliders, phone keeper/clamp rail, TPU tips, and TCP datum cartridge remain replaceable because they are wear, adjustment, or service parts. The universal camera plate is also replaceable but belongs only to the unqualified fixed-mast fallback; it is not an arm-camera adapter.

The board interface is intentionally simple:

- Four 6 mm locator pins: two for the keyboard master and two for the phone/TCP station.
- Nine M4 board interfaces: seven use conventional station-retention screws and two keyboard clamp positions use shared low-profile clamp/retention screws.
- The right keyboard station has no independent pin pair. It is located from the master station's seam and held through relieved holes.
- Each continuous printed base seats directly on the finished board. Three broad-triangle retention zones make lift and rocking inspection repeatable; current CAD uses no station shims.

This avoids the overconstrained loop that would result from pinning both keyboard halves while also forcing them through a keyed seam.

## 2. Source-of-truth rules

The generated layout record is authoritative for:

- board size and finished-top Z reference;
- every named board feature, including feature type, XY, diameter, depth, owning station, and instruction;
- station origins and occupied regions;
- all six AprilTag detection centers, tile sizes, roles, and expected yaw;
- printer envelopes and part bounds;
- design revision and layout hash.

The board-hole CSV, setup drawing, AprilTag map, manual tables, preview, and validator must derive from that record. An ordered list of unnamed coordinates is not acceptable.

## 3. Part-by-part implementation

### 3.1 `keyboard_station_left.stl`

Function: master keyboard datum and structural station.

Integrated features:

- front and left keyboard datum walls;
- open board-contact geometry so the keyboard's existing feet rest directly on the finished board;
- round locator socket and axis-relieving radial slot;
- three broad-triangle M4 hold-down passages, with the rear passage shared by the guided clamp slider;
- master side of the keyboard seam;
- rear clamp guide track;
- `RC03-L MASTER` molded identity;
- insertion lead-ins and accessible washer seats.

Release checks:

- one-piece STL fits the provisional 295 x 295 x 275 mm envelope;
- free-state corner lift no greater than 0.75 mm;
- support-plane flatness no greater than 0.40 mm;
- locator choice comes from the exact-profile job 00A coupon;
- the continuous base contacts the board at all three retention zones when retained;
- no cracks or whitening after repeated pin cycles.

### 3.2 `keyboard_station_right.stl`

Function: seam-located slave station.

Integrated features:

- right keyboard datum wall and open direct-board device support;
- slave side of the seam;
- three relieved M4 hold-down holes that clamp without imposing a second XY datum system;
- rear clamp guide track with its third hold-down passage shared by the clamp slider;
- `RC03-R SLAVE` molded identity.

Release checks:

- one-piece STL fits the provisional 295 x 295 x 275 mm envelope;
- no independent board locator pair exists;
- installed seam gap no greater than 0.40 mm;
- installed seam flush mismatch no greater than 0.25 mm;
- combined keyboard support plane no greater than 0.40 mm out of flat;
- the keyboard does not rock or bind after ten load/unload cycles.

### 3.3 `keyboard_rear_clamp.stl` (quantity two)

Function: replaceable, guided device clamp.

Features:

- guided runners matched to each station track;
- long adjustment slot with rounded ends and insertion relief;
- gusseted padded face;
- readable scale and center witness;
- part identity and contact-side mark;
- replaceable adhesive pad recess.

User-experience rule: tighten only until the pad contacts the keyboard. The clamp locates neither station and must not bow the keyboard shell.

### 3.4 `phone_tcp_station.stl`

Function: combined phone nest, cable management base, and TCP datum receiver.

Integrated features:

- fixed left/front phone datums based on the measured phone/case state;
- round locator socket plus axis-relieving radial slot;
- three broad-triangle M4 hold-down passages and continuous direct-board base contact;
- keyed receiver island for the removable TCP datum cartridge;
- protected M3 insert pockets for cartridge retention;
- USB/front orientation mark and a cable route to the tie saddle on the replaceable rail;
- interface ledge for the replaceable phone keeper/clamp rail;
- button, camera, connector, and bend-radius keepouts;
- `RC03 PHONE+TCP`, `TCP R3`, `USB`, and `TOP` molded labels.

Release checks:

- one-piece STL fits the provisional 295 x 295 x 275 mm envelope;
- phone support-plane flatness no greater than 0.30 mm;
- TCP receiver-seat flatness no greater than 0.15 mm;
- locator choice comes from the exact-profile job 00B coupon;
- the cable remains retained and clear through ten phone cycles;
- no clamp axis touches a side button or camera keepout.

### 3.5 `phone_clamp_rail.stl`

Function: replaceable phone keeper and clamp-tower spine.

Features:

- repeatable seating interface on the service station;
- two reinforced top-loading M4 hex-nut channels aligned to the horizontal clamp axes;
- two clamp axes positioned from measured phone side-feature intervals;
- TPU-tip clearance and stop witnesses;
- large fillets/gussets at tower roots;
- service removal access without disturbing station locators.

Release checks:

- the redesigned 7.2 mm lower-half captive-nut seat and 5.6 x 2.2 mm tie saddle are qualified on the production-equivalent Job 03C1 rail; the failed Job 00B screening features are historical evidence only;
- horizontal screw axes remain clear and do not break into a keepout;
- rail can be replaced while the service station stays registered;
- ten phone load/unload cycles preserve button, camera, and USB clearance.

### 3.6 `calibration_puck.stl` (quantity two)

Function: keyed, replaceable TCP datum cartridge.

Features:

- keyed planform that cannot be installed in the wrong orientation;
- clipped-corner orientation witness;
- crosshair and central probing divot;
- controlled fastener seats that do not disturb the datum face;
- one installed cartridge and one measured, labeled spare.

Release checks:

- lateral play no greater than 0.15 mm;
- mounted-height range no greater than 0.10 mm over ten cycles;
- crosshair and divot remain sharp; ironing is disabled;
- the accepted spare is measured and labeled, not merely printed.

### 3.7 `tag_application_frame_55mm.stl`

Function: reusable placement aid, not an installed tag frame.

Features:

- measured 55 mm tile opening with handling clearance selected by coupon/inspection;
- center crosshairs and edge witness notches;
- +Y/rear orientation mark;
- finger relief for clean removal after placement;
- flat, broad bearing face that references the paper setup template.

All six tags use full-surface matte adhesive directly on the finished sealed board. No tag-frame screws or permanent printed tag holders remain.

### 3.8 Profile-specific diagnostic parts

Job 00A adds:

- `station_locator_fit_gauge.stl` with independently labeled 6 mm board round/slot choices and 8 mm seam round/slot choices, printed in the keyboard-station profile;
- the keyboard corner-clearance, tray-hole, and washer-seat coupons.

Job 00B prints the locator gauge again in the service-station profile and includes a vertical M3 insert gauge. A selection from one profile does not automatically release the other profile.

The locator ladder must reproduce the production print axis and include round sockets and radial slots. Measure the actual pins in three orientations. Select the smallest option that can be inserted and removed by hand, survives at least 20 cycles without whitening/cracking, retains the pin when inverted, and has no more than 0.15 mm measured lateral play.

## 4. Direct AprilTag layout

Board Z=0 is the **finished sealed board top**. The optical tag plane is not a nominal printed-frame height. It is:

`compressed full-surface adhesive thickness + tag-stock thickness`

| Tag | ID | Role | Detection center X,Y mm | 55 mm tile origin X,Y mm |
|---|---:|---|---:|---:|
| T0 | 0 | World | 47, 40 | 19.5, 12.5 |
| T1 | 1 | World | 440, 40 | 412.5, 12.5 |
| T2 | 2 | World | 47, 410 | 19.5, 382.5 |
| T3 | 3 | World | 563, 410 | 535.5, 382.5 |
| K0 | 4 | Keyboard residual check | 324, 309 | 296.5, 281.5 |
| P0 | 5 | Phone residual check | 459, 309 | 431.5, 281.5 |

T0-T3 define the board transform. K0 and P0 are residual checks and must not be used as primary world tags.

Direct-tag acceptance:

- tile: 55.0 +/- 0.2 mm;
- detection edge: 40.0 +/- 0.2 mm;
- nominal center placement error: no more than 0.50 mm after metrology;
- yaw error: no more than 0.30 degrees;
- edge lift: no more than 0.20 mm;
- each tag detected in 20/20 static frames;
- reprojection error no greater than 1.0 pixel;
- installed center, yaw, and optical-plane Z recorded for every ID.

## 5. Board and arm interface

### 5.1 Board preparation

1. Purchase the 610 x 457 x 18 mm birch board cut to size where practical.
2. Lightly ease edges by hand; do not alter the controlled top reference face.
3. Seal both faces equally with a fully cured matte finish.
4. Measure local flatness over each station region and overall bow.
5. Print the generated setup template at Actual Size and verify both 100 mm scale bars.
6. Register the template to the board edges and verify named feature centers before drilling.
7. Drill small pilots through printed guides.
8. Drill locator bores with a 6 mm brad-point bit and positive depth stop. These bores are blind.
9. Drill/install the coupon-qualified M4 tee nuts or threaded inserts using a scrap-board stack test first.
10. Dry-fit every station and pin before applying epoxy to locator pins.

Board acceptance:

- local gap no greater than 0.50 mm across any 300 mm station region;
- overall bow no greater than 1.5 mm;
- locator projection within the generated layout tolerance;
- at least 5 mm usable M4 thread engagement;
- no screw bottoming or projection below the feet;
- three assembly/removal cycles at 0.25-0.35 N m;
- 50 N axial proof for 60 seconds with no insert rotation or veneer damage.

### 5.2 RoArm mounting

The factory RoArm clamp remains the load-bearing interface. RC03 adds:

- a board centerline/witness generated in the setup drawing;
- a measured clamp-position record;
- a precut metal underside reinforcement plate sized after measuring the real clamp footprint.

No printed component is treated as the primary arm load path. Hard arm-locator stops remain deferred until the actual factory-clamp geometry is measured and physically qualified.

## 6. Controlled print sequence

1. Confirm the installed 0.4 mm nozzle and calibrate the exact dry material lots.
2. Print required diagnostic jobs 00A, 00B, 00C, 00E, and 00F; print 00D only for an explicitly selected `phone_stylus_route`.
3. Record separate keyboard- and service-profile locator selections.
4. Record the profile-specific locator, M3 insert, hole, washer, phone, cable, tool, and TPU selections; retain the failed Job 00B nut/tie observations as superseded evidence.
5. Regenerate geometry and prove that the parameters match the recorded PASS selections.
6. Print job 01 and accept the left/master station; use its actual seam posts with the retained job 00A seam ladder to select the slave round-socket diameter and radial-slot width independently.
7. Feed both accepted seam selections into their dedicated controlled parameters, regenerate, then print job 02 and accept the master/slave station pair.
8. Print the small Job 03C1 rail first; bench-qualify both M4 nut seats and the wider-tie saddle, then release and print Job 03A. Print Job 03B independently. After Job 03A exists, finish the rail seating and phone-interface acceptance.
9. Print job 03C2 and validate the paper setup template before direct-tag installation.
10. Print two Job 03D cartridges, keeping slicer object `calibration_puck_1` as 03D-A and `calibration_puck_2` as 03D-B. Qualify both separately, select `INSTALL` using the controlled normalized play/height-range score, and label the other accepted part `SPARE - TCP RECALIBRATION REQUIRED`.
11. Print/qualify camera, tool-route, TPU, and optional mast jobs only through their existing route gates.
12. Import every non-diagnostic 3MF into QIDI Studio at 100%, inspect critical layers, save/reopen a native project, and record per-job evidence.

Each large station uses its own plate. Do not auto-orient, globally XY-scale, merge objects, or move objects into the protected 5 mm bed-edge margin.

## 7. Assembly and repeatability sequence

1. Install face pads on both keyboard sliders, install the phone station's M3 inserts off-board, and preload the phone rail's two top-loading nuts.
2. Dry-fit all four locator pins, three stations, both keyboard sliders, the phone rail, washers, and all nine shared/fixed M4 interfaces before using epoxy; use no station shims.
3. After the dry-fit cycles pass, remove the stations and epoxy only the four locator pins at the controlled projection.
4. Place the left keyboard slider on its tracks, seat the master on its pins, and start two fixed screws plus the third shared slider/station screw before tightening.
5. Mate the right/slave station to the seam, place its slider, and start two fixed screws plus the third shared slider/station screw before tightening.
6. Install the phone station's preloaded rail on its molded keys, then start the TCP-side screw and the two shared rail/station screws before tightening.
7. Install the accepted TCP cartridge and record its mounted height.
8. Apply and measure all six direct tags.
9. Complete ten station remove/reinstall cycles and calculate X, Y, Z, and yaw ranges per station.
10. Complete ten keyboard, ten phone, and ten TCP-cartridge cycles.
11. Resolve the arm-camera architecture hold, perform the formally released route-specific calibration, and run empty-cell motion checks before any device contact.

Station acceptance:

- peak-to-peak X and Y no greater than 0.25 mm;
- peak-to-peak yaw no greater than 0.20 degrees;
- peak-to-peak Z no greater than 0.20 mm;
- a 0.10 mm feeler does not enter beneath the base at any retained contact zone;
- 20 N lateral station load and 10 N functional-point load cause no cracking and no more than 0.10 mm permanent shift.

## 8. Release boundary

RC03 geometry may be generated and dimensionally inspected digitally, but the fixture is not physically released until the measurement record contains PASS evidence for:

- the actual keyboard, phone/case, cable, fasteners, inserts, pins, board, and camera interfaces;
- every profile-specific diagnostic coupon;
- QIDI Studio per-job round-trip evidence;
- the three printed station first articles;
- direct-tag scale, placement, plane measurement, and vision performance;
- ten-cycle station/device/cartridge repeatability;
- arm-clamp footprint and metal reinforcement selection;
- empty-cell safety motion.

Any failed physical gate changes parameters or process evidence first. Do not silently drill, sand, scale, or force a released datum to fit.

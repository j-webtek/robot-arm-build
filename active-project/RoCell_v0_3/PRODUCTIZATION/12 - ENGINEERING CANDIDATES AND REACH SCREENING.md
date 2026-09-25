# Engineering candidates and RoArm reach screening

**Registry revision:** `RC03-INT-R1`  
**Engineering state:** `CANDIDATE_UNVERIFIED`  
**Release authority:** none

This note explains the controlled engineering candidates in [`config/hardware_candidates.json`](../config/hardware_candidates.json). It supports reference purchasing and physical qualification only. It does not select a canonical build route, update a measurement result, authorize production printing, or approve customer construction or sale.

Every candidate remains unverified until the received item, final printed geometry, finished board, installed robot, power system, and complete workcell pass their controlled physical gates. Similar-looking substitutions do not inherit evidence.

## 1. Candidate configuration boundary

The registry adds exact ordering identities where the present BOM is generic and keeps alternatives separate:

- E-Z LOK `900407-10` underside board inserts and kit `EZ-900407-10`;
- BelMetric `SB4X20SS`, `SB4X25SS`, and `WF4SS` station hardware;
- Wera `05074715001` preset driver and `05056310001` 2.5 mm bit;
- seller-supplied reinforcement plate `B02-ARM-PLATE-R1`;
- POWERTEC `71755` prototype emergency-power-off candidate;
- MAKESafe `IRE-V120-P1-HP1` product-safety application-review direction;
- Arducam `B0495C` and Logitech `960-001401` camera options;
- SmallRig `4304` and the incomplete paired-80/20 `20-2020` support options;
- QIDI `PETG-BLACK` and `TPUHS` material candidates;
- Perixx `PERIBOARD-409U`, Samsung `SM-A166BZKDEUB`, and StarTech `R2CCR-1M-USB-CABLE` device candidates;
- Lee Spring `LP022J01S316` and McMaster-Carr `4143N11` tool candidates; and
- the existing Waveshare RoArm-M3 Pro platform.

The camera options, support options, and power options are alternatives. Evidence from one option cannot qualify another. The paired extrusion support has an exact extrusion candidate but still lacks exact brackets, T-nuts, base anchors, fastener lengths, support-base definition, ASA SKU, and cut tolerances; it is not yet a complete purchasable system.

The user-intended primary vision architecture is arm-mounted / eye-in-hand, but its exact camera specification and mounting contract are absent from RC03. That architecture is on `ENGINEERING_ALIGNMENT_HOLD`. The canonically selected `camera_mast_optional` route remains true as an unqualified fixed-overhead fallback; this registry neither changes that route selection nor treats the fallback as a substitute for the missing arm-camera specification.

The current controlled scope also keeps `phone_stylus_route` and `keyboard_rod_route` selected. Route selection is intent, not evidence. The exact passive stylus manufacturer/model is still open, so no stylus hardware entry has been invented for this exact-candidate registry. Jobs and tests for that route remain blocked on a real orderable candidate and its separate fit, conductivity, retention, force, TCP, and cycle evidence.

## 2. Board-anchor architecture

### Candidate interface

Use the E-Z LOK `900407-10` M4 x 0.7 x 10 mm flanged wood insert as an underside-installed candidate:

1. Preserve the controlled top-side station center and the candidate 4.6 mm screw passage.
2. From the underside, enlarge the insert zone using the candidate 15/64 inch / 5.953 mm drill and a positive depth stop.
3. Install the insert from the underside so its flange bears against the board underside.
4. Drive it with the specified 4 mm hand tool; do not use an impact driver.
5. Insert the station screw from above through one flat washer and the printed station into the board interface.

This is a candidate process, not a drill instruction for the production board. E-Z LOK states that drilling must be proven in the actual application. The required full-diameter bore depth, twist-drill point allowance, feed, and finish behavior must be selected from sectioned coupons made from the exact sealed 18 mm board stock.

The right-side anchor centers are 21.2 mm from the board edge. With the nominal 8.36 mm flange diameter, the nominal edge ligament is:

`21.2 - 8.36 / 2 = 17.02 mm`

That geometry is promising but does not prove veneer or edge strength. At least one destructive coupon must reproduce the exact 21.2 mm center-to-edge position and ply direction.

### Required anchor evidence

- Received MPN, lot, thread, body, flange, tool, and drill dimensions.
- Matching sealed-board interior and edge coupons.
- Sectioned bore depth and insert alignment.
- No veneer breakout, delamination, cracking, flange stand-off, or rotation.
- Three service cycles and the final cycle count required by the release plan.
- Dry 0.30 N m assembly using the selected screw, washer, and printed stack.
- 50 N axial proof for 60 seconds without pullout, rotation, migration, or board damage.
- At least 5.0 mm measured screw engagement, with no bottoming or underside projection.

Do not drill the production board until these checks are accepted.

## 3. Exact M4 station stacks

The candidate common interface is an A2 stainless ISO 7380-1 button-head screw, one A2 DIN 125A flat washer, and the underside insert. Do not add a lock washer or threadlocker. Apply a torque witness after the qualified 0.30 N m dry assembly.

The proposed seller pack is:

| Item | Installed candidate | Seller-pack quantity | Function |
|---|---:|---:|---|
| BelMetric `SB4X20SS` | 4 | 6 | Four nominal 4.0 mm station seats |
| BelMetric `SB4X25SS` | 5 | 7 | Four nominal 8.0 mm seats and one corrected TCP seat |
| BelMetric `WF4SS` | 9 | 12 | One 4.3 x 9.0 x 0.8 mm washer per anchor |

Using nominal values, thread engagement is screened as:

`engagement = screw length - printed seat - washer thickness - (board thickness - insert reach)`

| Stack | Nominal calculation | Nominal engagement | Engineering disposition |
|---|---|---:|---|
| 4.0 mm seat with M4 x 20 | `20 - 4.0 - 0.8 - (18 - 10)` | 7.2 mm | Candidate |
| 8.0 mm seat with M4 x 25 | `25 - 8.0 - 0.8 - (18 - 10)` | 8.2 mm | Candidate |
| Historical unrecessed 10.5 mm TCP seat with M4 x 25 | `25 - 10.5 - 0.8 - (18 - 10)` | 5.7 mm | Superseded; zero current locations |
| Current 10.5 mm island with 1.5 mm washer recess, giving a 9.0 mm effective seat | `25 - 9.0 - 0.8 - (18 - 10)` | 7.2 mm | Digital correction applied; physical qualification open |

### TCP digital correction applied; physical qualification remains required

The current TCP geometry retains the 10.5 mm structural island and adds a 1.5 mm washer recess. Its effective screw-seat stack is therefore a nominal **9.0 mm**, with **9.5 mm as the maximum accepted measured effective seat** after printing and cooling.

The correction is applied in the current CAD, and the dependent STL, STEP, and 3MF artifacts have been regenerated. The controlled exact-fit checks pass digitally. This closes the prior digital stack defect but does not qualify the printed recess, received washer, screw, insert, or finished board.

Using the maximum accepted 9.5 mm effective seat, 18.3 mm board thickness, 9.36 mm usable insert reach, and a 0.9 mm washer gives the conservative screen:

`25 - 9.5 - 0.9 - (18.3 - 9.36) = 5.66 mm`

That leaves 0.66 mm over the 5.0 mm minimum in this screen. It is not a tolerance release: measure every received and printed contributor, verify at least 5.0 mm actual engagement, and prove no bottoming or underside projection. An M4 x 30 screw is unnecessary and may bottom or project below the board.

The two current keyboard rear-clamp locations also combine clamp adjustment and station retention. The common button-head approach is preferred for measured torque, but it may be used there only if driver access and keyboard preload pass. Otherwise, redesign clamp preload and station retention as separate functions; do not ask a customer to reproduce station torque by hand with a thumb screw.

## 4. Reinforcement plate and board restraint

### Candidate drawing

`B02-ARM-PLATE-R1` is a seller-supplied, precut load-spreader candidate:

- 6061-T6 aluminum sheet;
- 0.125 inch / 3.175 mm thickness;
- 152.4 x 127.0 mm outline;
- 6.35 mm corner radii;
- no holes;
- raw or mill finish;
- deburred both faces, edges broken 0.25-0.5 mm;
- candidate outline tolerance of +/-0.25 mm; and
- incoming flatness no greater than 0.25 mm across the part.

The customer does not need a router or CNC. The seller orders or supplies the finished plate.

With a centered, rear-flush candidate placement, the plate occupies `x=228.8-381.2 mm` and `y=330.0-457.0 mm`. It remains inside the current `x=225-385 mm` clamp zone with about 3.8 mm per-side margin. Its front edge is 75.5 mm behind the nearest current board-anchor center at `y=254.5 mm`.

The approximate plate mass is:

`0.1524 x 0.1270 x 0.003175 x 2700 = 0.166 kg`

These are layout checks only. The received clamp must be measured. Require at least 10 mm between the actual clamp contact-pad edge and the plate edge. Use clean, direct plate-to-sealed-board contact; do not introduce an unqualified foam layer that can creep.

Qualify board flatness before and after clamping, absence of rocking and veneer crushing, clamp retention, and 24-hour and 7-day creep. Waveshare publishes a maximum table thickness but no controlled clamp torque, so the clamp-setting method remains an open physical requirement.

Six 3M `SJ-5023-BLACK` feet can provide 7.62 mm clearance over the 3.175 mm plate and protect the bench. They do not prove anti-shift performance. If the worst-case robot motion test moves the board, the released build must use a mechanically defined bench restraint. Exact supported bench thickness, edge geometry, and restraint hardware must be frozen before sale.

## 5. Honest power-control boundary

### Prototype emergency power-off candidate

The POWERTEC `71755` is a prewired 120 V, 9 A magnetic paddle cutoff with standard three-prong cords. The candidate order is:

`wall receptacle -> POWERTEC 71755 -> received Waveshare 12 V / 5 A adapter -> RoArm`

A nominal 60 W adapter output represents about 0.5 A at 120 V in the ideal case or approximately 0.625 A at 80 percent efficiency. That is below the published 9 A switch rating, but it does not address supply inrush, switching suitability, grounding, listing scope, or system safety. Verify the received power-adapter label, plug, AC input, condition, and inrush behavior.

The `71755` is only a prototype emergency power-off candidate. Do not label, advertise, or document it as a safety-rated E-stop. No validated performance level, safety category, STO function, diagnostic coverage, or RoArm stop-time rating has been established.

### Product-safety direction

The MAKESafe `IRE-V120-P1-HP1` family is the product-oriented application-review direction because the manufacturer publishes an enclosed industrial anti-restart/E-stop system and UL 508A / CSA #14-13 product-family information. Request a quote-configured 120 V unit with NEMA 5-15 input and output.

Do not purchase or select it until MAKESafe approves the exact Waveshare switching adapter and always-on digital controller in writing. The IRE manual assumes an existing machine off/run control and uses a machine-switch-detection circuit. The RoArm may not satisfy those assumptions.

### System hazards that remain open

- Waveshare states that the robot automatically moves joints toward a middle pose at power-on.
- Upstream AC removal is an uncontrolled loss of motor power; it may allow gravity drop and does not establish a controlled stop category.
- RoArm documentation reviewed here does not establish a safety-rated STO or E-stop input.
- USB may keep controller logic energized or create an unexpected back-power path.
- Resetting an upstream device must never itself command robot motion.
- The control must be reachable from every operator position while remaining outside the robot sweep.
- Plugs and receptacles need retention or bypass control appropriate to the final risk assessment.

For each candidate, record actual power removal, stop time, residual travel, worst-pose gravity behavior, USB back-power, connector retention, access, reset behavior, mains-interruption behavior, and ten consecutive no-automatic-restart trials. A competent system risk review must approve the final architecture and the exact wording of every safety claim.

## 6. Camera, support, and material options

### Vision candidates

The primary intended architecture is an arm-mounted camera used according to its intended specification. Before that route can be designed, the project needs the exact camera identity and lens, the robot link/frame and mount interface, mount mass and center of mass, fasteners and retention, moving-cable route, payload/collision model, occlusion analysis, eye-in-hand calibration transform, operating sequence, and revised Step 13 acceptance contract. No arm-mount CAD or powered use is authorized without that information.

The existing fixed-overhead fallback candidate is Logitech C920e `960-001401` on the paired mast. The alternate global-shutter evaluation candidate is Arducam `B0495C`, and SmallRig `4304` is another fixed-support evaluation option. Keep every camera/support pairing and its calibration evidence separate. None of these candidates silently implements the arm-mounted intent.

Arducam currently publishes two FOV sets for the B0495 family:

- current enclosed-product page: approximately 98 degrees diagonal, 85 horizontal, 69 vertical; and
- B0495 datasheet: approximately 95 degrees diagonal, 82 horizontal, 66 vertical.

Do not collapse this conflict into one falsely exact value. Use the smaller 82 x 66 degree values for preliminary framing. At a perfectly perpendicular 400 mm lens-to-tag-plane height, those values screen to approximately:

- width: `2 x 400 x tan(82/2) = 695 mm`; and
- height: `2 x 400 x tan(66/2) = 520 mm`.

That nominally covers the 610 x 457 mm board, but with only about 42.5 mm horizontal and 31.5 mm vertical margin per side before perspective, lens distortion, mounting error, or enclosure clearance. The camera’s published default focus range begins at 2 m, so manual focus at the intended 400-600 mm height is a mandatory physical gate.

The SmallRig `4304` is the commercial overhead-support candidate. Mount it independently to the bench behind the board, outside the work envelope, with a secondary tether and a qualified camera fastener. Prove clamp compatibility, ball-head lock, sag, cable disturbance, 24-hour drift, remove/reinstall recovery, and collision clearance.

If the SmallRig fixed-support evaluation cannot meet drift requirements, complete and qualify the paired `20-2020` fallback rather than improvising. The exact extrusion alone does not complete that system. Neither fixed-support option resolves the arm-camera alignment hold.

Minimum vision evidence includes at least 30 ChArUco views with at least 20 accepted, RMS reprojection error no greater than 1 pixel, all six tags detected in 20 of 20 required trials, locked imaging controls, cable-strain proof, 24-hour drift, and remove/reinstall recovery.

### QIDI Plus4 materials

The rigid and flexible material candidates are QIDI PETG-Tough Black `PETG-BLACK` and QIDI TPU95A-HF Black `TPUHS`. Freeze and record:

- exact SKU, color, spool lot, drying and storage history;
- printer serial, firmware, standard 0.4 mm nozzle, and build-surface side;
- QIDI Studio version and named profile revision;
- first-layer, XY scale, hole, insert, nut-capture, locator, bridge, warp, and support-removal results; and
- native QIDI project reopen/reslice results and hashes.

Complete two consecutive accepted rigid-part print sets without CAD or profile changes. Qualify PETG station creep at 24 hours and 7 days, and TPU pull-off, compression set, creep, and wear. The existing paired-mast option still lacks an exact ASA SKU and cannot be print-qualified as a complete support route until that selection is made.

## 7. Device and contact-tool candidates

The registry carries forward the pre-hardware device candidates with more explicit ordering identity:

- Perixx `PERIBOARD-409U`, USB-A, English-US, black;
- Samsung full UK reference order code `SM-A166BZKDEUB`, model family `SM-A166B`, bare with no case; and
- StarTech `R2CCR-1M-USB-CABLE`, right-angle device end to straight USB-C host end.

The Samsung full order code is a UK reference candidate. It is not a US commercial selection until regional identity and physical equivalence are decided. The exact cable must be proven with the intended USB-C host/power source, relaxed service loop, strain relief, connector direction, and no lateral port load.

The contact-tool candidates are:

- Lee Spring `LP022J01S316`; and
- McMaster-Carr `4143N11`, 303 stainless, 6 mm x 100 mm precision shaft.

The spring’s calculated incremental loads are only 0.429 N at 3 mm and 0.858 N at 6 mm before preload, friction, tolerance, off-axis effects, and tool mass. Measure the received force curve and complete 1-6 mm travel, return, bind, rub, creep, and final contact-force tests.

Measure the rod at several locations, inspect straightness and ends, and have the seller safely deburr or chamfer it as required. Qualify bushing retention, TPU pull-off and creep, spring travel, keyboard actuation, cycle wear, and TCP repeatability. Listing this exact rod does not enable `keyboard_rod_route` or change CAD.

## 8. RoArm mechanical and reach screening

Waveshare publishes the following RoArm-M3 Pro data:

- 5+1 degrees of freedom;
- maximum horizontal workspace diameter 1120 mm, giving a nominal 560 mm radius;
- maximum vertical workspace 798 mm;
- payload 0.2 kg at 0.5 m;
- repeatability approximately +/-5 mm under the same load;
- maximum clamped table thickness 72 mm;
- Pro arm mass approximately 1020.8 +/-15 g, excluding clamp; and
- clamp mass approximately 290 +/-10 g.

The official Xacro includes these useful nominal offsets:

- world to base: 70.1 mm Z;
- base to shoulder: 51.959 mm Z;
- shoulder to elbow vector norm: approximately 238.708 mm;
- elbow to wrist-pitch offset: 144.586 mm;
- wrist-pitch to roll vector norm: approximately 55.750 mm; and
- stock hand TCP offset: 115.428 mm.

Their simple serial sum is approximately 554.47 mm, consistent with the advertised 560 mm radial envelope. This is not task reachability evidence because link rotations, joint limits, target orientation, collision, singularity, load, and approach geometry matter.

### Current board screening

The current layout defines only an arm clamp zone at the board rear. It does not define the robot base-axis datum. For screening only, assume the axis is exactly at board coordinate `(305,457)`:

| Screened point | Board coordinate, mm | Planar radius, mm |
|---|---:|---:|
| Front board corner | `(0,0)` | 549.3 |
| Keyboard front-left | `(85,85)` | 432.2 |
| Phone actual front-right | `(577.1,84.2)` | 461.6 |
| Phone-station outer front-right | `(597.3,80)` | 477.1 |
| Configured TCP target | `(441,180)` | 308.6 |

The front corner leaves only about 10.7 mm against the advertised maximum radius. If the base axis is 100 mm behind the assumed rear-edge datum, the phone-station outer front-right point screens to approximately 559.5 mm. No boundary point should be accepted on an advertised maximum envelope.

### Honest conclusion

The present target positions **cannot be digitally proven reachable** from the current controlled data.

The following are missing:

- the installed board-to-robot-base transform `T_board_base`, including X, Y, Z, roll, pitch, and yaw;
- clamp edge-to-base-axis offset and the selected location inside the current clamp zone;
- robot, controller, base, and clamp revision plus clamp and board deflection;
- physical joint-zero/model calibration and uncertainty;
- custom tool TCP, moving mass, center of mass, cable drag, and collision geometry;
- if the intended arm-mounted camera proceeds, its eye-in-hand transform, mount mass and center of mass, moving-cable loads, occlusion model, and collision geometry;
- target tool orientation and approach, contact, and retreat poses; and
- collision geometry for board, clamp, stations, devices, camera, support, cables, and operator exclusions.

Required evidence order:

1. Import the official STEP and URDF/Xacro model.
2. Freeze clamp placement and board/table planes.
3. Measure `T_board_base` using a controlled jig or probe and record uncertainty.
4. Add the exact selected tool TCP, mass properties, cable load, and collision model.
5. Solve every approach/contact/retreat pose with joint, singularity, payload, and collision margins.
6. Reject paths that depend on the maximum workspace boundary.
7. Perform reduced-speed, tool-clear empty-cell sweeps.
8. Perform compliant, force-limited first contacts while the cutoff operator remains outside the sweep.

The published approximately +/-5 mm repeatability is much larger than the intended fixture tolerance. Vision correction and compliant contact are therefore functional requirements. The 0.2 kg at 0.5 m payload must include the complete tool, adapter, spring/rod moving mass, and cable drag.

## 9. Build-step ownership

| Current step | Candidate work owned by the step |
|---|---|
| 00 | Receive, identify, measure, and quarantine exact candidates; freeze printer/material/software records; print verification coupons. |
| 01 | Section and prove insert drilling in exact sealed board stock before production drilling. |
| 02 | Inspect and qualify plate, feet, anti-shift boundary, clamp method, power boundary, and robot-base datum. |
| 03-04 | Prove left-master/right-slave station seating, screw access, engagement, torque, and repeatability. |
| 05 | Prove exact keyboard, clamp preload, cable clearance, and removal cycles. |
| 06-08 | Preserve the regenerated 10.5 mm island / 1.5 mm recess / 9.0 mm effective TCP stack; physically prove all phone-station stacks and service hardware. |
| 09-10 | Prove exact bare phone, cable direction, service loop, strain relief, and no-go margins. |
| 11-12 | Install and measure exact tag stock and optical plane. |
| 13 | Keep the arm-mounted intent on hold until its exact specification and mount/calibration contract exist; meanwhile qualify the selected fixed-mast route only as a fallback, including calibration, detection, drift, tether, and collision gates. |
| 14 | Qualify exact spring, rod, bushing, TPU tip, force/travel, retention, TCP, and payload. |
| 15 | Close the risk assessment, cutoff/drop/restart tests, `T_board_base`, IK/collision evidence, empty-cell run, and compliant first contact. |

## 10. Stop conditions

Stop and return to engineering if any of the following occurs:

- received identity or dimensions differ from the registry;
- an insert damages the exact board coupon, rotates, migrates, or fails proof;
- any M4 stack has less than 5.0 mm engagement, bottoms, or projects below the board;
- the printed TCP washer recess is absent or damaged, the measured effective seat exceeds 9.5 mm, or actual engagement is below 5.0 mm;
- the clamp pad does not remain fully supported on the plate with the required edge margin;
- the board shifts, creeps, rocks, or loses flatness;
- a power candidate allows restart, unexpected motion, back-power, inaccessible stopping, or unacceptable gravity drop;
- camera focus, calibration, tag visibility, drift, tether, or collision checks fail;
- an arm-mounted camera is designed or powered before its exact specification, payload/collision model, cable route, and eye-in-hand calibration contract are controlled;
- the tool fails force, travel, bind, retention, creep, TCP, or payload limits; or
- `T_board_base`, complete IK/collision evidence, or reduced-speed physical commissioning is absent.

No item in this note is released merely because it has an exact part number.

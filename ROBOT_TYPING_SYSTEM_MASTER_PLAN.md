# RoCell robot typing system master plan

**Planning baseline:** active Freeze 011 with the 2026-09-05 static-overhead-primary decision; Freeze 009 remains archived historical provenance  
**Hardware release in scope:** RC03-INT-R1  
**Robot:** Waveshare RoArm-M3 Pro; the M3-S is outside this freeze and requires a separate qualified profile  
**Document role:** Governing roadmap for the software, calibration, verification, and commissioning work that turns the RC03 hardware cell into a physical keyboard-typing and phone-tapping system  
**Current status:** THE BUILDER HAS SELECTED A RIGID STATIC OVERHEAD EYE-TO-HAND CAMERA AS THE PHASE 1 PRIMARY AND CONFIRMED PURCHASING THE ARDUCAM USB 3.0 20 MP PACKAGE SOLD WITH A 60-DEGREE DIAGONAL, NOMINAL 16 MM C-MOUNT LENS AND METAL CASE. THE DESIGN MAPS THAT ORDER TO THE ARDUCAM B0477/IMX283 CATALOG CONFIGURATION WITH STATE `PURCHASED_PENDING_RECEIPT_INSPECTION`. THIS PURCHASE FIXES THE INTENDED SIMULATION AND CARRIAGE-DESIGN INPUT; IT DOES NOT VERIFY THE RECEIVED UNIT OR RELEASE CUTS, FABRICATION, INSTALLATION, MOTION, OR CONTACT. RECEIVED MODEL/SERIAL/USB IDENTITY, DELIVERED LENS AND MOUNT, RECEIVED-PART DIMENSIONS, COMPLETE COLLISION/LOAD PROOF, ONE-METRE FOCUS, MEASURED OPTICS, LIGHTING, STATIC EXTRINSIC, VISIBILITY, AND PHYSICAL QUALIFICATION REMAIN OPEN. ACTIVE FREEZE 011 AND BUILD `2026-09-01_CELL-A` ARE THE CURRENT CONTROLLED BASELINE; FREEZE 009 REMAINS IMMUTABLE ARCHIVED PROVENANCE. FREEZE 011 DELIBERATELY RETAINS LEGACY ARM-CAMERA FIELDS UNDER `CAMERA_ARCHITECTURE_ALIGNMENT_HOLD`; THE ADDITIVE B0477 PATH IS THE SELECTED PHASE 1 SIMULATION DIRECTION, NOT A PHYSICAL PROMOTION. JOB 00A REMAINS `POSTPRINT_PASS`, AND ROBOT POWER, CAMERA-GUIDED DESCENT, AND CONTACT REMAIN BLOCKED  
**Software checkpoint:** THE PURCHASED B0477 NOW HAS A STRICT SOURCE-HASHED PROFILE, FULL-NATIVE USB3/YUY2 MODE CONTRACT, EXACT HALF-SCALE 2736×1824 SYNTHETIC PROJECTION, ZERO-HARDWARE IDENTITY/CONTROL/REOPEN COMMISSIONING REHEARSAL, PROVIDER-NEUTRAL UVC INVENTORY CONTRACT WITH A DETERMINISTIC FAKE PROVIDER, SEALED 32-VIEW SYNTHETIC CHARUCO INTRINSICS CONTRACT (24 TRAINING / 8 HELD OUT), AND A B0477-SPECIFIC STATIC JPEG→TAG36H11→PLANAR-POSE REHEARSAL. THE INTRINSICS FIXTURE BINDS THE SAME SYNTHETIC PERSISTENT UVC IDENTITY AND REOPEN-SETTINGS HASHES AS THE INVENTORY FIXTURE. THE RECOMMENDED APPLICATION-LEVEL `rehearse-b0477-stack --require-pass` GATE CROSS-CHECKS ALL FIVE CORE ARTIFACTS AND, BY DEFAULT, THE NORMAL/TAG-LOSS PIXEL PAIR; IT CURRENTLY REPORTS `SYNTHETIC_B0477_STACK_COHERENT` WITH 10/10 CHECKS. THE NORMAL CAMERA-SPECIFIC REHEARSAL RECOVERS ALL SIX TAGS; THE FOUR-TAG-LOSS CASE NATURALLY REJECTS BEFORE POSE. THE USB/OPENCV BOUNDARY REQUESTS AND READS BACK FOURCC AS WELL AS WIDTH, HEIGHT, AND FRAME RATE. FROZEN BASELINE ACCEPTS 38/75 INDEPENDENT TARGET ROUTES; THE LOCKED, UNMEASURED RANK-1 OVERLAY ACCEPTS 75/75. THE REPLAY-STABLE REPORT-SCHEMA-V3 KEYBOARD `test` AND ANDROID `test.` SESSIONS RETAIN THEIR HISTORICAL FIXED-OVERVIEW JPEG→TAG36H11→PLANAR-POSE GATES; THE NEW B0477 PATH IS THE ADDITIVE PHASE 1 MIGRATION BOUNDARY. A SEPARATE ADAPTIVE-SCHEMA PATH SIMULATES THE HISTORICAL UPPER-ARM CAMERA FROM ACHIEVED SIX-JOINT FK AND REMAINS OPTIONAL PHASE 2 RESEARCH. A 12 MM SHIFTED KEYBOARD CASE AND 8 MM SHIFTED PHONE CASE CORRECT, CONVERGE, VERIFY INDEPENDENT OUTPUT, AND PARK; ZERO OFFSET RETAINS REVISION ZERO. THIS REMAINS SYNTHETIC ZERO-AUTHORITY SOFTWARE EVIDENCE: THE FIXTURES, THRESHOLDS, NUMERIC INTRINSICS, FIXED CAMERA POSE, AND SUPPORT ARE NOT PHYSICAL ACCEPTANCE DATA; HARDWARE PRESENCE, LIVE CAPTURE, PHYSICAL CALIBRATION/EXTRINSIC, ROBOT MOTION, AND CONTACT AUTHORITY REMAIN FALSE. ADAPTIVE ARTIFACT REPLAY IS NOT YET IMPLEMENTED, AND NO PHYSICAL CAMERA, ROBOT-FRAME/CONTROLLER CORRELATION, COLLISION QUALIFICATION, CONTACT GUARD, PHYSICAL OUTCOME OBSERVER, OR HARDWARE VALIDATION EXISTS. THE 19-BODY COLLISION CONTRACT REMAINS BLOCKED BY 7 MISSING AND 6 UNKNOWN BODY GEOMETRIES; NO CANONICAL GEOMETRY OR HARDWARE AUTHORITY CHANGED  
**Placemat geometry sensitivity checkpoint:** `stress-placemat-geometry` NOW REVALIDATES ACTIVE FREEZE 011, THE CURRENT 610 x 457 x 18 MM RC03 BOARD, ALL 46 KEYBOARD AND 29 PHONE TARGETS, THE REPAIRED STATIC-SUPPORT SOURCE LOCK, THE PURCHASED B0477 PROFILE, AND THE IMPLEMENTATION IDENTITY BEFORE RUNNING A BOUNDED GEOMETRY-ONLY MATRIX. THE DEFAULT 59 CASES PRODUCE 4,425 TARGET/CASE OBSERVATIONS: 0/46 KEYBOARD TARGETS AND 27/29 PHONE TARGETS SHOW A SAMPLED GAP, WITH WORST XY SAFE-REGION MARGINS OF +2.7525 MM AND -0.7560 MM. THE ZERO-BOUND CONTROL KEEPS ALL 75 NOMINAL CENTRES IN REGION. THESE ARE ASSUMED UNMEASURED SENSITIVITY INPUTS, NOT HARDWARE TOLERANCES, PROBABILITIES, CALIBRATION LIMITS, CAMERA VISIBILITY EVIDENCE, OR PHYSICAL AUTHORITY; SEE [`PLACEMAT_GEOMETRY_SENSITIVITY.md`](software/docs/PLACEMAT_GEOMETRY_SENSITIVITY.md)  
**Integrated V2 checkpoint:** AN ADDITIVE ZERO-HARDWARE V2 NOW BINDS THE EXACT SEMANTIC PLAN, SOURCE-REVALIDATED DENSE ACCEPTED ROUTE AND STORED JOINT SOLUTIONS, ONE STATEFUL SYNTHETIC B0477 REPORT PER CONTACT AT THE SETTLED FINAL HOVER, EVERY ROUTE ENDPOINT AND EXACT JOINT MIDPOINT COLLISION QUERY, ORDERED AUTHORIZATION-V2, CRASH-CONSERVATIVE PER-CONTACT JOURNALS, A NON-WIRE T=104-SHAPED CONTROLLER EMULATOR, GEOMETRY-RESOLVED VIRTUAL CONTACT, INDEPENDENT VIRTUAL OUTCOME, RETRACTION, FINAL PARK, AND COMPLETE RECEIPT REPLAY. PHONE STATE OBSERVATIONS ARE MANDATORY CHRONOLOGICAL PREREQUISITES FOR LATER MOTION, CAMERA, CONTACT, TAIL, AND FAULT-FRONTIER EVIDENCE. KEYBOARD `test` HAS 48 ROUTE WAYPOINTS, 47 EMULATOR COMMANDS, AND 4 SIMULATED CONTACT OCCURRENCES; ANDROID `test.` HAS 61 WAYPOINTS, 60 COMMANDS, AND 5 SIMULATED CONTACT OCCURRENCES, WHILE ITS STATE OBSERVATION OWNS NO CONTACT, COMMAND, AUTHORIZATION ENTRY, OR JOURNAL. CONTROLLER FAULTS BIND THE FAILED TRACE; A CAMERA FAULT SCHEDULE IS SEALED INTO THE ASSEMBLY AND ENFORCED AS A GLOBAL BOUNDARY. CAPTURE-AREA CAUSALITY IS HONESTLY COLLAPSED TO `SettledHoverObservationBoundary`, WHILE ANY TYPED B0477 FAULT IS MARKED `UNAUTHENTICATED_DIAGNOSTIC_ONLY`. V1 REMAINS UNCHANGED, AND V2 IS BOUNDED TO EIGHT PHYSICAL TARGETS. THE 26-BODY COLLISION INPUT IS AN EXPLICITLY ISOLATED SOFTWARE-BINDING FIXTURE, CALIBRATIONS REMAIN `NOMINAL_ONLY`, `R_ctrl` CORRELATION IS UNCOMMISSIONED, AND NO WIRE PAYLOAD OR LIVE PROVIDER EXISTS. PER-CONTACT JOURNALS DO NOT YET SUPPLY A MISSION-GLOBAL TRANSIT/HOVER DISPATCH HIGH-WATER, AND TWO LOWER-LEVEL WRAPPER FAILURES CAN TERMINALIZE JOURNALS THEN RAISE WITHOUT A STRUCTURED REPORT; GLOBAL DISPATCH AND PARTIAL-EFFECT RECEIPTS ARE REQUIRED BEFORE A PHYSICAL ADAPTER. THIS CLOSES A SOFTWARE ASSEMBLY GAP ONLY; PHYSICAL CLEARANCE, CAMERA CAPTURE, CALIBRATION, MOTION, CONTACT, AND RELEASE AUTHORITY REMAIN FALSE  
**First-power-on rehearsal:** `rehearse-first-power-on --scenario nominal --require-expected` NOW RUNS THE 15-STAGE CAMERA-FIRST ONBOARDING CONTRACT THROUGH BUILT-IN DETERMINISTIC FAKE CAMERA/ARM BOUNDARIES. IT PARSES AND HASHES ACTUAL RECEIPT FIXTURE VALUES BEFORE B0477 COMPARISON; TESTS MODE/CONTROL, SEQUENCE-PLUS-RAW-JPEG FRESHNESS, STATIC PIXEL REGISTRATION, AND POWER-ON OBSERVATION PROCEDURE ORDER; REJECTS VALID T=1051 DATA ALREADY BUFFERED BEFORE A NEW T=105; EXERCISES THE COMPLETE 15-ARTIFACT STATIC PHASE-1 CALIBRATION GRAPH, BOTH 12-ARTIFACT DEVICE CLOSURES, AND ALL 68 STALENESS EDGES; AND HASH-BINDS REPRESENTATIVE KEYBOARD/PHONE MISSIONS TO THE LATEST ACCEPTED STAGE-8 B0477 REGISTRATION CONTEXT. SETTINGS AND INTRINSICS DIRECTLY BIND THE RETAINED CAMERA/SUPPORT/LIGHT/CABLE STACK. NOMINAL COUNTS ARE 109 EXECUTED VIRTUAL WAYPOINTS, 9 VIRTUAL CONTACT ATTEMPTS/ACCEPTANCES, AND 9 OBSERVATIONS, SEPARATE FROM ZERO HARDWARE MOTION/CONTACT COMMANDS. THE FIRST-WAYPOINT STALL PROVES NO LATER VIRTUAL CONTACT/OBSERVATION AND UNCHANGED OUTPUT. THE REGRESSION MATRIX REQUIRES EVERY PRE-FAULT RECORD TO EQUAL NOMINAL, AND THE REPORT REQUIRES THE TERMINAL STAGE/DETAIL/CHECK/COUNT SIGNATURE; CHECKPOINT RESUME SOURCE-BINDS IMPLEMENTATION, RUNTIME CODEC IDENTITY, AND TRANSITIVE INPUTS AND REPLAYS THE EXACT PREFIX. ITS EXACT NOMINAL STATUS IS `SIMULATION_WORKFLOW_COMPLETE_PHYSICAL_ONBOARDING_NOT_STARTED`; TEMPORARY OPTICS FEASIBILITY PRECEDES RETAINED INSTALLATION, WHILE FINAL INTRINSICS ARE CAPTURED ONLY AFTER THAT INSTALLATION. INCOMPLETE PHYSICAL COLLISION GEOMETRY REMAINS BLOCKED, ACTIVE FREEZE 011 IS UNCHANGED, FREEZE 009 REMAINS ARCHIVED, AND EVERY PHYSICAL AUTHORITY REMAINS FALSE  
**Physical-arrival onboarding checkpoint:** THE ROOT `setup-rocell.ps1`, CHECKOUT-ANCHORED `rocell.ps1`, SIDE-EFFECT-FREE `host-doctor`, AND `start-rocell-onboarding.ps1` NOW PROVIDE A CONTROLLED WINDOWS ARRIVAL ENTRY PATH. `physical-onboard` CREATES A SOURCE-BOUND 15-STAGE DIAGNOSTIC SESSION WITH AN APPEND-ONLY HASH-CHAINED JOURNAL, LOGICALLY VERIFIED HIGH-WATER RECORD (WINDOWS POWER-LOSS DURABILITY REMAINS UNQUALIFIED), FRESH MUTATION CHALLENGES, BOUNDED CONTENT-ADDRESSED EVIDENCE, STRICT LEGACY WHOLE-TEMPLATE 55-ROW INTAKE VALIDATION, AND EXPLICIT CAMERA/SERIAL METADATA INVENTORY THAT NEVER OPENS OR SELECTS A DEVICE. ONLY `workspace_sources` AND `static_camera_contract` CAN PASS AUTOMATICALLY; ALL LATER STAGES STOP AT `WAITING_OPERATOR`, AND NO PUBLIC REVIEWED-STAGE ASSESSOR EXISTS. STRICT RECEIPTS FOR B0477 RECEIPT INSPECTION, POWER-OFF SAFETY REVIEW, ONE EXTERNALLY CONTROLLED FIRST-POWER OBSERVATION, AND EXACTLY BOUND OPERATOR DECISION CAN RETURN ONLY `DIAGNOSTIC_READY`, `HOLD`, OR `SIDE_EFFECT_UNCERTAIN` AND CANNOT MUTATE A SESSION OR GRANT AUTHORITY. `rehearse-physical-connections --require-expected` EXERCISES THE TEN-STEP HOST/B0477/ROARM LIFECYCLE AND NINE FAIL-STOP CASES USING ONLY CONSTRUCTOR-FIXED INCAPABLE PROVIDERS. NONE OF THESE PATHS APPLIES ROBOT POWER, OPENS A CAMERA OR ARM PORT, SENDS T=104, INITIALIZES/MOVES THE ARM, PROMOTES THE SELECTED STATIC CAMERA INTO ACTIVE FREEZE 011, REWRITES ARCHIVED FREEZE 009, OR CONFERS CALIBRATION/POWER/MOTION/CONTACT/RELEASE AUTHORITY  
**Adaptive software result (verified 2026-09-04):** PLANAR ESTIMATOR V1.1 USES MONOTONIC CONSENSUS. THE FULL-CATALOG SYNTHETIC POLICY IS 2.5 MM TRANSLATION / 0.5 DEGREE YAW-TILT / 5 PX MAXIMUM INLIER RMSE, WITH AT MOST 128 EXECUTED VIRTUAL WAYPOINTS PER SINGLE-TARGET ROUTE; IT ACCEPTED 75/75 ADAPTIVE TARGET SESSIONS WITH REPORT SHA-256 `232dcdd5c7bb6cb7afb6e4dcac6001797991faa54587dd7e0979e67880d8d4e2`. THE DISTINCT 1.5 MM / 0.25 DEGREE / 3 PX PERTURBATION POLICY PASSED ALL 20/20 DECLARED OUTCOMES, INCLUDING 4 EXPECTED SAFE REJECTIONS, WITH REPORT SHA-256 `9dda1bc28015ee6943d0e5017e16756dd30c6d0530d950a818161c28aa15dd20`. ALL VALUES REMAIN SYNTHETIC AND CONFER ZERO PHYSICAL AUTHORITY  
**Verification checkpoint:** THE 2026-09-04 QUICK QUALIFICATION PASSED 5/5 AND ITS SIX-ARTIFACT PACKAGE STRICTLY REPLAYED IDENTICALLY (`009e2cd6f37ba776aacb418cfbbac494a2a25435d9a91f4f04f7afde9a99c248`); STANDARD QUALIFICATION PASSED 17/17 WITH FRESH 75/75 TRAJECTORY COVERAGE (`2d540fef2fbf833cdd4ac32bffcb356beaa462cbb4bf27ad987466b30be8e7c4`). ON 2026-09-06 THE FINAL STABLE-TREE ORDINARY COMPLETE SUITE PASSED 1,896 TESTS WITH 3 OPT-IN TESTS DESELECTED IN 1,259.13 SECONDS, AND ALL 3 EXPLICITLY ENABLED MULTI-MINUTE STANDARD/ADAPTIVE CAMPAIGNS PASSED SEPARATELY IN 568.97 SECONDS, FOR 1,899 PASSING TESTS WITH NO FAILURES IN THE COMBINED RUN SET. THE SIX-FILE INTEGRATED FOCUS COVERAGE IS INCLUDED IN THAT COMPLETE RERUN. MYPY PASSED ALL 152 SOURCE FILES AND COMPILEALL PASSED. AN INDEPENDENT ADVERSARIAL AUDIT FOUND NO REMAINING REPRODUCIBLE HIGH/MEDIUM INTEGRITY FORGERY IN THE TESTED FAULT MATRIX; TWO REPORT-AVAILABILITY-ONLY WRAPPER CASES REMAIN EXPLICITLY TERMINALIZED AND NON-RETRYABLE. THE SOURCE-LOCKED STATIC SUPPORT VALIDATOR PASSED WITH 12 PHYSICAL QUALIFICATION BLOCKERS, AND THE BUILD-ALIGNMENT VALIDATOR PASSED WITH NO ERRORS. BUILD ALIGNMENT REMAINS `ALIGNED_CAMERA_HOLD_CONTACT_BLOCKED`, CONTACT IS FALSE, AND ALL PHYSICAL HOLDS REMAIN IN FORCE  
**Freeze record:** [`BUILD_ALIGNMENT_FREEZE.md`](BUILD_ALIGNMENT_FREEZE.md) and [`software/config/system_manifest.json`](software/config/system_manifest.json)  
**Approved camera migration:** [`STATIC_OVERHEAD_CAMERA_ARCHITECTURE_PLAN.md`](STATIC_OVERHEAD_CAMERA_ARCHITECTURE_PLAN.md), [`software/config/camera_architecture_plan.json`](software/config/camera_architecture_plan.json), and the additive [`hardware/static_overhead_camera/`](hardware/static_overhead_camera/README.md) design package

## Camera architecture control note — 2026-09-05

The historical Freeze-009 19-body collision contract remains blocked by its
missing and unknown physical geometry. A separate additive static-B0477 route
contract now inventories 26 required bodies, binds nine design-source hashes,
and exercises all 75 nominal targets through seven phases and six
midpoint-sampled transitions. Its only intended overlap exception is the exact
tool-tip/designated-target pair during that target's CONTACT phase. The model
uses explicit conservative synthetic fixtures. Its dense-route adapter is now
assembled into additive mission V2, where every accepted endpoint and incoming
exact joint midpoint is bound to the authorization-command sequence. The
current complete geometry is deliberately isolated test geometry and reports
`physical_clearance_established=false`; it provides no collision qualification
or physical authority.

The static-overhead plan controls all new Phase 1 camera, calibration,
simulation, and commissioning work. Legacy eye-on-arm fields retained in active
Freeze 011 remain under `CAMERA_ARCHITECTURE_ALIGNMENT_HOLD`; they originate in
historical Freeze 009 and are not current Phase 1 instructions. Eye-on-arm code
and evidence remain useful optional Phase 2 research but cannot satisfy the
Phase 1 camera gate.

This decision does not release the older 2020 mast, universal plate, Logitech
candidate, B0459/LN069 combination, Waveshare IMX335-B, or any other historical
camera hardware. The purchased Arducam B0477/IMX283 catalog configuration with
included nominal 16 mm lens and metal case is now the detailed-screening optical
baseline. The additive support package supplies a compact front portal, nominal
`Z=1000 mm` entrance pupil, and provisional `Z=920 mm` overhead floor. Its
source-locked software contract grants simulation authority only. Received-unit
identity and geometry, delivered lens/mount, complete collision/load proof,
one-metre focus, measured optics, and a superseding freeze remain prerequisites.

## Physical onboarding control note — 2026-09-06

The controlled arrival path is
[`software/docs/PHYSICAL_ONBOARDING_AUTOMATION.md`](software/docs/PHYSICAL_ONBOARDING_AUTOMATION.md).
The reviewed v2 implementation sequence for turning that backend into a
guided, resumable terminal/browser wizard is
[`software/docs/PHYSICAL_ONBOARDING_WIZARD_IMPLEMENTATION_PLAN.md`](software/docs/PHYSICAL_ONBOARDING_WIZARD_IMPLEMENTATION_PLAN.md).
Its additive Phase-0 foundation is implemented: strict source-bound contracts
define closed effect classes, canonical stage annotations, progressive intake,
configuration epochs, HZ-001..016, the workcell ICD, and a conservative target-
accuracy budget. The existing controller remains the per-session reviewed-state
authority; the planned v2 `CellCommissioningCoordinator` will separately own
cell-global attempts, quarantine, every-energization envelopes, and bounded
workers. Stages 13-14 remain behind a separate bootstrap/noncontact permit and
runner rather than adding motion to the wizard. All foundation files remain
runtime-inactive and grant zero physical authority.
On Windows, `start-rocell-onboarding.ps1 -CellId CELL-A` is the preferred entry
point: it prepares the hardware dependency profile, reruns the host gate, and
reruns the zero-I/O foundation validator and incapable-provider B0477/RoArm
connection rehearsal before it creates a source-bound diagnostic session with
only two zero-I/O stages prepared. It
never inventories or opens a device, powers the arm, or sends a command. Device
metadata inventory remains a later, explicit, challenge-gated operator action.

The persistent workflow records state; it does not commission the cell. Later
stages can currently be marked only `WAITING_OPERATOR`, evidence never passes a
stage merely by being stored, and the typed manual-receipt assessors are not yet
wired to a public stage-advance command. Their strongest positive result is
`DIAGNOSTIC_READY`, which is deliberately not physical PASS or authority. A
source change invalidates execution for an existing session; a stale challenge,
journal rollback, malformed/extra evidence, ambiguous device identity, or
uncertain side effect fails closed. The overhead architecture is selected for
new work but remains unpromoted relative to active Freeze 011; Freeze 009 is
retained only as immutable archived provenance.

## 1. Executive decision

We will build this as a calibrated robotic workcell, not as a collection of memorized servo poses.

The system will use:

- the existing RC03 board coordinate frame and mechanically indexed keyboard/phone stations;
- the RC03 reference articles: RoArm-M3 Pro, Perixx PERIBOARD-409, and bare Samsung Galaxy A16 5G;
- a rigid static overhead eye-to-hand primary camera, the existing ChArUco
  intrinsics workflow, and the six existing board AprilTags;
- a static camera-to-robot calibration layer, live camera-to-board observation,
  independent controller-frame correlation, and route-specific tool-center-
  point calibration;
- USB serial control of the RoArm-M3 at 115200 baud using our own typed protocol adapter;
- conservative, vertical approach/contact/retract primitives with passive tool compliance, measured contact-force sensing, and a physical power-cut E-stop;
- selected RC03 keyboard-rod and phone-stylus tool routes; a new
  `camera_overhead_primary` route will replace the misleading historical
  `camera_mast_optional` name in the superseding freeze;
- target maps for the frozen keyboard and phone after their real dimensions, layout, screen, and installation states pass measurement;
- static-camera board/station/device observation before every autonomous
  descent, with conditional top-visible tool-marker correction above clearance
  if the measured endpoint error budget requires it;
- an input compiler that translates requested text into physical key or screen actions; and
- independent observation of what the computer or phone actually received.

The most important feasibility constraint is the manufacturer's stated approximately **±5 mm unidirectional positioning repeatability under the same load**. The advertised 12-bit encoder feedback resolution of about 0.088 degrees is not equivalent to Cartesian tip accuracy. Stock phone QWERTY targets may be too small for reliable open-loop operation. Phone typing is therefore a gated objective: first prove large-target tapping, then prove a fixed keypad, and only then attempt a stock phone keyboard using closed-loop tool localization. If the measured error budget does not fit inside each target's safe area, the correct outcome is a larger UI, improved sensing/tooling, or a more precise arm—not optimistic offsets.

## 2. Mission and definition of done

### 2.1 Mission

Given a command such as:

```text
rocell type --device keyboard --text "Hello, world!"
rocell type --device phone --text "Hello, world!"
rocell tap --device phone --target send
```

the system shall:

1. verify that the workcell, camera, arm, tool, stations, and selected device profile are the commissioned versions;
2. localize the board and validate that calibration has not drifted;
3. compile the text or named action into supported physical targets and device-state transitions;
4. reject unsupported or unsafe actions before motion;
5. plan collision-checked transit, approach, contact, and retract segments;
6. execute through the arm controller while monitoring feedback and timeouts;
7. verify the result through a separate observation path; and
8. save a traceable run record.

### 2.2 Definition of done

The project is complete only when all of the following are true:

- RC03's physical manufacturing, station, tag, camera, compliant-tool, force/travel, E-stop, anti-shift, and empty-cell commissioning gates are PASS.
- The exact robot variant, firmware, keyboard model/layout, phone/case/orientation, camera, lens/settings, tool route, and host configuration are frozen in a system manifest.
- Camera identity/settings, intrinsics/distortion, the exact static support and
  `Wv_T_C_overhead_optical`, measured tag coordinates, board pose,
  board-to-arm/controller correlation, TCP, keyboard pose, and phone screen
  plane all have versioned calibration artifacts with residuals and source
  hashes.
- The runtime cannot energize a contact motion from stale, missing, nominal-only, or failed calibration.
- Every supported keyboard key and phone target has a safe contact region large enough for the measured end-to-end error bound.
- Keyboard and phone acceptance tests meet the performance gates in Section 20 without an unsafe contact.
- A user can request supported text through one documented CLI/API without writing raw robot coordinates.
- A physical E-stop removes actuator power independently of the host software, and the unpowered arm has a tested gravity-safe collapse/support envelope.
- A complete build, calibration, dry-run, operation, recovery, and revalidation procedure exists.

### 2.3 Explicit non-goals for the first release

- General-purpose manipulation or object grasping.
- Arbitrary six-degree-of-freedom paths. The RoArm-M3 provides five pose degrees of freedom plus its gripper, so the typing tool will use a fixed feasible downward orientation.
- General visual understanding of any keyboard or any phone UI.
- Unattended operation around people.
- Treating servo load estimates as a calibrated force sensor.
- Using Wi-Fi/HTTP as the primary motion transport.
- Supporting simultaneous two-key chords with a single contact tip.
- Using ROS2/MoveIt in the MVP unless direct serial characterization proves inadequate.

## 3. Existing RC03 baseline

The hardware package is already a strong foundation. This plan must consume it without casually duplicating or changing its controlled geometry.

### 3.1 Existing sources of truth

- [RC03 workcell layout](active-project/RoCell_v0_3/config/workcell_layout.json): 610 × 457 × 18 mm board, board axes, station geometry, device envelopes, TCP target, and six tag locations.
- [RC03 BOM](active-project/RoCell_v0_3/BOM.csv): frozen reference arm, keyboard, phone, tools, camera class, and safety hardware requirements.
- [RC03 measurement record](active-project/RoCell_v0_3/config/measurement_record.json): typed physical release gates and evidence fields.
- [RC03 active-build identity](active-project/RoCell_v0_3/BUILD_BY_STEP/ACTIVE_BUILD.json), [step index](active-project/RoCell_v0_3/BUILD_BY_STEP/INDEX.json), and build-specific evidence/signoffs: physical build identity and execution state.
- [RC03 digital release validation](active-project/RoCell_v0_3/RELEASE_VALIDATION.json) and [step-package validation](active-project/RoCell_v0_3/BUILD_BY_STEP/PACKAGE_VALIDATION.json): digital consistency and explicit physical-release state.
- [RC03 pre-hardware configuration](active-project/RoCell_v0_3/config/v1_prehardware_configuration.json), [pre-hardware readiness report](active-project/RoCell_v0_3/PREHARDWARE_READINESS.json), [digital fit report](active-project/RoCell_v0_3/config/digital_fit_report.json), and [reach screening](active-project/RoCell_v0_3/config/robot_reach_screening.json): controlled candidate selections and explicit digital-versus-physical limits.
- [Historical Freeze 009 camera decision](active-project/RoCell_v0_3/config/camera_architecture_decision.json): retained unchanged until the superseding freeze.
- [Approved static-overhead change plan](STATIC_OVERHEAD_CAMERA_ARCHITECTURE_PLAN.md): the controlling direction for all new Phase 1 camera work.
- [RC03 assembly manual](active-project/RoCell_v0_3/ASSEMBLY_MANUAL.md): assembly, camera, tags, compliant tool, repeatability, and first-motion process.
- [Board layout image](active-project/RoCell_v0_3/images/board_layout_dimensioned.png) and [assembly image](active-project/RoCell_v0_3/images/assembly_isometric.png): visual layout references.
- [AprilTag map](active-project/RoCell_v0_3/fiducials/apriltag_map.json): tag36h11 identities and nominal/measured board coordinates.
- [Camera capture helper](active-project/RoCell_v0_3/software_helpers/capture_camera_frames.py), [ChArUco calibration helper](active-project/RoCell_v0_3/software_helpers/calibrate_camera_charuco.py), and [AprilTag detector](active-project/RoCell_v0_3/software_helpers/detect_apriltags.py).
- [Reach-layout diagnostic contract](software/docs/REACH_LAYOUT_STUDY.md),
  [bounded park-pose contract](software/docs/PARK_OPTIMIZATION.md),
  [discrete route trajectory contract](software/docs/TRAJECTORY_SIMULATION.md),
  [pre-hardware layout and mission-coverage contract](software/docs/PREHARDWARE_MISSION_COVERAGE.md),
  [placemat geometry sensitivity contract](software/docs/PLACEMAT_GEOMETRY_SENSITIVITY.md),
  [full-body collision foundation](software/docs/COLLISION_FOUNDATION.md),
  [virtual commissioning and replay contract](software/docs/VIRTUAL_COMMISSIONING.md),
  [first-power-on onboarding and resumable rehearsal](software/docs/FIRST_POWER_ON_ONBOARDING.md),
  [offline eye-on-arm foundation](software/docs/EYE_ON_ARM_CALIBRATION.md), and
  [capture-bundle contract](software/docs/EYE_ON_ARM_CAPTURE_BUNDLE.md),
  [arm-camera correction simulation](software/docs/ARM_CAMERA_CORRECTION_SIMULATION.md), and
  [aggregate prehardware software qualification](software/docs/PREHARDWARE_QUALIFICATION.md):
  current simulation-only software inputs, report gates, and explicit physical
  blockers.

### 3.2 Board frame already defined

The authoritative board frame, called `B` in this plan, is:

- origin: front-left corner of the finished board top surface;
- +X: right;
- +Y: rear/toward the arm; and
- +Z: up.

Nominal board targets already include:

| Item | RC03 nominal definition |
| --- | --- |
| Board | 610 × 457 × 18 mm |
| Keyboard | origin near (85, 85) mm; nominal 315 × 147 × 21 mm |
| Phone | origin near (499.2, 84.2) mm; configured 77.9 × 164.4 × 7.9 mm |
| Phone screen plane | nominal Z = 11.9 mm, pending physical measurement |
| TCP cartridge target | center (441, 180) mm; nominal target-plane Z = 10.5 mm |
| World tags | T0-T3, IDs 0-3 |
| Held-out station checks | K0/P0, IDs 4-5 |

These device origins, screen/TCP Z values, station origins, candidate fit dimensions, and clamp-zone coordinates are **nominal design seeds and keepout geometry only**. They are not executable contact coordinates. Contact requires measured device transforms, installed-cartridge height, arm registration, and route-specific TCP evidence.

### 3.3 Current physical status

The digital RC03 package is internally validated, but the physical cell is not released:

- active build `2026-09-01_CELL-A` is assigned and must remain bound to all evidence;
- active Freeze 011 is the current synchronized snapshot, and the canonical
  alignment validator reports `ALIGNED_CAMERA_HOLD_CONTACT_BLOCKED`;
- Freeze 005 → 006 was the seven-source Job 00A lifecycle transition that
  recorded Job 00A as `PRINTED` and the keyboard-corner coupon as `PASS` at
  0.0 mm compensation;
- Freeze 006 → 007 was the five-source post-Freeze-006 traceability
  synchronization for the actual M4 screw/washer observations; it left the
  tray-clearance gate `NOT_TESTED` and the counts at 9/71/4;
- Freeze 007 → 008 was the seven-source operator-waived prototype
  functional-fit transition that promoted only
  `tray_clearance_holes_coupon_pass` to `PASS`;
- Freeze 008 → 009 was the seven-source operator-waived prototype keyboard
  locator functional-fit and lifecycle transition. It promoted only
  `keyboard_station_registration_coupon_pass` to `PASS`, retained the selected
  6.2 mm round socket, 6.2 mm radial-slot width, and controlled 10.0 mm slot
  length, and advanced Job 00A from `PRINTED` to `POSTPRINT_PASS`;
- Freeze 009 → 010 was the 14-source reconciliation that recorded the static-
  camera architecture conflict as an alignment hold, preserved the accepted
  Job 00A/00B fits, recorded two explicit Job 00B failures, and regenerated the
  Job 03C1 production-equivalent rail; Freeze 010 → 011 was a four-source
  workflow correction that removed Job 03C2's self-dependency without changing
  geometry, gate counts, or physical authority; and
- Freeze 005 remains the explicitly historical 14-source hardware-alignment
  and park/reach/simulation provenance baseline. Freezes 006–011 rebind the
  regenerated RC03 evidence and do not re-run or relabel those study results;
- both tool routes are selected. Active Freeze 011 deliberately retains the
  legacy arm-camera and `camera_mast_optional: false` fields under
  `CAMERA_ARCHITECTURE_ALIGNMENT_HOLD`; the approved 2026-09-05 change plan
  selects `camera_overhead_primary`, but the active project route schema has
  not yet been regenerated and must not be reinterpreted in place;
- active Freeze 011 reports 20 selected jobs (5 `READY`, 15 `WAITING`) and four
  optional-mast jobs as `NOT_SELECTED`; these are historical routing facts, not
  authority to omit the new static support from the superseding build package;
- the measurement record has 15 `PASS`, 63 `NOT_TESTED`, 4 `NA`, and 2 explicit
  `FAIL`; Job 00A's
  recorded and effective state is `POSTPRINT_PASS` because all three of its
  mapped post-print gates are `PASS`: `keyboard_corner_coupon_pass` at 0.0 mm
  compensation, operator-waived `keyboard_station_registration_coupon_pass`,
  and operator-waived `tray_clearance_holes_coupon_pass`. The locator selection
  uses the nominal, not caliper-measured, 6 mm production dowel with a 6.2 mm
  round socket, 6.2 mm radial-slot width, and controlled 10.0 mm slot length;
  numeric lateral-play measurement, 20 repeated cycles, and inversion testing
  were waived, with no cracking or whitening visible or reported. The 4.0 mm
  M4 major diameter likewise remains a nominal designation assumption; the
  actual screw passed cleanly at 4.4 mm with no smaller candidate passing, and
  the actual washer fit all candidates with the photographed/current 9.2 mm
  recess retained for assembly margin. These three gates complete Job 00A's
  mapped post-print acceptance but do not release dependent jobs, robot power,
  motion, or contact;
- the Pro/PERIBOARD-409/bare-A16 selections are frozen digital references, but
  their exact physical articles, static camera/lens/support/lighting, arm clamp,
  spring, tool, and material measurements remain unrecorded;
- station repeatability tests remain NOT_TESTED;
- `tag_plane_placement_measured` remains NOT_TESTED;
- the tag map still uses `coordinate_source: nominal_layout` with null optical Z values;
- the current RC03 physical-helper detector intentionally returns
  `BLOCKED_MAP_UNMEASURED` for board pose; the separate fixed-overview virtual
  detector/estimator described below does not promote that nominal map;
- tool force/TCP limits, commissioning motion/contact limits, and final workcell commissioning remain NOT_TESTED;
- robot reach is `SCREENING_ONLY_NOT_PROVEN`; the current planar calculation does not establish IK/orientation, payload, singularity, or collision feasibility;
- the corrected bounded IK placement study likewise found no complete
  contact-and-park finalist: its best 385 mm clamp-contact, -82 degree yaw,
  100/100 mm tool hypothesis accepted 20/46 keyboard contacts, 18/29 phone
  contacts, and 0/2 route parks with only 0.0100156 worst accepted arm-joint
  margin; this remains evidence to refine measured placement/tool hypotheses,
  not proof that the received physical arm is incapable;
- the bounded historical Freeze-005 park optimizer, retained unchanged as
  provenance by active Freeze 011, selected a simulation-only board-frame
  overlay at `(290, 10, 70) mm`; both 100 mm tools pass its independent
  pointwise IK screen with 0.2704734350 worst normalized arm-joint margin and
  10 mm modeled planar tool-tip clearance, but it changes no canonical geometry
  and proves neither a route from the installed state nor full-body collision;
- with that overlay, keyboard `"a"` accepts 24/24 trajectory waypoints with
  unsupported checks, while phone `"a"` stops at `APPROACH` because its
  normalized arm margin is 0.000657824, below 0.01; both reach finalists also
  reject phone `key_a` contact, so the current base/tool/layout hypothesis is
  not feasible for the complete keyboard-and-phone mission;
- complete independent mission screening confirms that baseline result across
  the locked catalog: only 38/75 park-to-target-to-park routes pass (20/46
  keyboard and 18/29 phone);
- a separate staged pre-hardware sensitivity study screened 243 coarse and 34
  refined hypotheses, found 49 regression passes, fully screened only the
  ranked top eight, and promoted six. Rank 1 (`reach-944d7463f4c67905`), with
  unmeasured rear-clamp X 385 mm, rear-edge-to-axis Y 75 mm, yaw -105 degrees,
  base Z 70.1 mm, zero clamp-to-axis X offset, and 120/100 mm virtual tools,
  accepts 75/75 independent target routes at the re-screened `(290, 10, 70)`
  mm park probe. This is sensitivity evidence, not a mechanical allowance,
  installed transform, fabrication instruction, or arbitrary-text proof;
- the typed 19-body full-collision contract and bounded primitive pose/discrete
  sweep kernels are implemented, but readiness remains
  `COLLISION_DIAGNOSTIC_BLOCKED_REQUIRED_GEOMETRY_INCOMPLETE`: seven
  robot/gripper bodies are missing geometry and six installed base/clamp,
  holder/camera/connector/cable/tool records remain unknown, so no route-level
  full-body check is claimed;
- a sixth locked simulation artifact now records rank-1 solely as an
  `UNMEASURED_SENSITIVITY_OVERLAY`. The strict virtual bootstrap validates the
  runtime policy, complete source context, gate projection, calibration
  inventory, non-opening arm profile, six-tag overview, and collision hold;
- the end-to-end virtual executor preserves action occurrence and each
  solver-achieved board-frame tip pose/tool axis through every
  waypoint/result, uses explicit non-physical calibration surrogates, and runs
  deterministic arm, fixed-overview pixel observation, keyboard/Android,
  fault, and outcome state. At every physical action's `HOVER` endpoint it
  renders a fresh JPEG, independently decodes released tag36h11 IDs, estimates
  `camera_overview_optical_T_board`, and gates approach on the locked synthetic
  tag/residual/fixture-pose policy. The pixel processor receives only a capture
  sequence and capture mode; action/target/waypoint association occurs after
  processing.
  Contact truth now hit-tests the achieved pose against the complete placemat
  keyboard or phone target-region map and independently applies synthetic
  depth, normal-angle, dwell, focus, and Android UI-state policy; the contact
  input receives neither a planned target identity nor a per-action expected
  character. A separate exact-once observer consumes only the resulting
  `ContactResult` and retains plaintext in memory while serializing only output
  hash and length. The legacy virtual session executes 48 keyboard and 61
  Android virtual waypoint moves; both match output hash/length, return to park,
  close, and generate zero hardware commands. The virtual-session report is
  schema v3; manifest schema v2 adds a separately hashed, redacted
  `vision.json` attempt ledger, and atomic evidence can be strictly verified
  and fully recomputed. These are software regression results, not physical
  sequence, physical static-overhead vision, collision, contact, or outcome
  evidence;
- the historical `camera_architecture_decision.json` remains
  `ENGINEERING_ALIGNMENT_HOLD`, while
  `software/config/camera_architecture_plan.json` controls the selected but
  unqualified static-overhead direction. Exact camera, lens, native mode,
  support geometry, height, lighting, static extrinsic, cable route, collision
  model, visibility atlas, and robot-frame registration remain open; and
- the historical Freeze-005 simulation runtime remains under `software/` as
  preserved study/replay provenance; active Freeze 011 rebinds the regenerated
  RC03 source snapshot without rewriting those reach, park, or simulation
  results: strict T=104/T=105/T=1051 protocol and replay boundaries, lazy
  serial transport, USB/OpenCV and optional ESP HTTP camera adapters, immutable
  RC03 import/capability projection, calibration registry, fail-closed
  preflight/permits, semantic keyboard/phone compilers, deterministic dry-runs,
  bounded reach-layout/park/full-route waypoint studies, and zero-authority
  offline eye-on-arm candidate/FK/capture-bundle verification;
- hardware-neutral typed runtime-port contracts now separate clock,
  cancellation, arm lifecycle/execution/feedback, observation, device-contact,
  outcome-observer, and evidence responsibilities and validate that one bound
  mission port set is zero-authority before use. They are an interface
  foundation, not a live-motion implementation or physical release;
- a distinct persistent physical-arrival controller now binds the active build,
  exact 15-stage plan, policy, controlled configuration/design/runbook inputs,
  and complete RoCell Python source tree. Its immutable session header,
  hash-chained journal, logically verified sync-attempted high-water record,
  content-addressed
  evidence, and fresh mutation challenges fail closed on source drift, rollback,
  stale state, or malformed evidence. The combined starter prepares only the
  two zero-I/O stages. Intake validation and explicitly requested metadata-only
  inventory are implemented, but no public assessor can pass a reviewed stage;
- canonical zero-authority manual receipts now cover exact B0477 receipt
  inspection, de-energized power-safety review, one externally controlled
  possible-motion first-power observation, and an exactly bound operator
  decision. Their dispositions are limited to `DIAGNOSTIC_READY`, `HOLD`, and
  `SIDE_EFFECT_UNCERTAIN`; an acknowledgement cannot upgrade a hold, and no
  receipt can mutate the onboarding session or promote a release;
- a separate ten-stage physical-shaped onboarding contract now drives only
  constructor-fixed `EXPLICIT_FAKE` providers through camera receipt,
  persistent OS selection, exact B0477 mode/control readback, buffer flush and
  fresh captures, reopen/reconnect, retained-install acquisition receipts with
  a precommitted 24-training/8-held-out split,
  explicit mount/lighting/focus/aperture/cable-route witnesses, arm identity
  while power is reported off, then a hash-linked safety observation,
  power-event request/observation, in-memory controller-session identity,
  explicit empty-input-buffer observation, and exactly one identity-bound
  synthetic T=105/T=1051 exchange. All 17 provider call boundaries fail closed
  and attempt cleanup. Its deterministic sequence times/nonces are explicitly
  untrusted simulation witnesses. The protocols expose no
  T=104, raw-write, motion, or contact method, and the immutable result cannot
  confer physical authority;
- a per-action append-only mission journal now derives stable occurrence IDs
  from the mission, plan, ordinal, and canonical action; commits intent and the
  possible-contact boundary before later results; and separates confirmed
  outcome, retract, park, fault, and `OUTCOME_UNCERTAIN` recovery. Automatic
  contact retry is forbidden once contact may have occurred. A sync-attempted
  high-water record binds the exact tail and permanently latches the first
  contact-boundary event, so a missing, truncated, unanchored, or rolled-back
  suffix fails closed instead of restoring contact permission. The current
  Windows compatibility path is not proof of power-loss durability. This
  journal is a restart-safety foundation and remains separate from onboarding
  checkpoints;
- an ordered authorization-v2 foundation now binds exact controller/connection,
  build/evidence-only release identity, the exact 12-artifact static Phase-1
  keyboard or phone closure, ordered trajectory plus collision report, device
  state, four independently sourced interlock samples, operator-arm nonce,
  mission plan, stable action occurrences, and every simulated command. The
  preferred closure adapter resolves those artifacts directly from the
  hardened registry and rejects missing, nominal-only, stale, extra-context,
  or unmodeled-parent inputs. A sealed cursor can advance only in exact order,
  rechecks identity/freshness/sequence evidence at each step, and emits a
  simulation-only receipt; reorder, duplication, omission, expiry, drift, or
  replay revokes it. These local Python seals, caller-supplied test times, and
  unkeyed filesystem hashes are not a physical trust boundary;
- a zero-authority multi-action mission kernel now combines runtime ports,
  stable journal occurrences, the authorization-v2 cursor, pre-motion feedback,
  fresh observation, route binding, hover/approach/contact/retract execution,
  independent semantic outcome validation, final park, and repeated final
  journal/port validation. It consumes authorization before every simulated
  execution command, seals outcome and report records, preserves primary plus
  cleanup failures, and accepts restart only with the exact safe remaining
  suffix. Once contact may have occurred it can observe/retract/park as allowed,
  but it never automatically repeats that contact;
- a manifest-last raw sensor-session package now preserves bounded synthetic
  transport bytes, raw/decoded/undistorted frame data, camera identity/mode/
  controls, timing, calibration/source bindings, detections, pose, and unsent
  feedback fixtures. Schema v2 additionally enforces exact packed-YUY2 and
  RGB8 layouts/strides/byte lengths, exact color primaries/transfer/matrix/
  range/chroma-siting/row-origin semantics, capture-to-perception freshness, bounded
  adjacent-stage/session durations, factory-only verified values, and
  monotonic stored-versus-applied replay policy. Exact-file/hash/canonical
  replay remains permanently zero-authority and is designed so recorded
  physical bytes can later replace fixtures without changing the evidence
  boundary;
- a B0477-specific bridge now exercises that evidence package with the exact
  detector-input JPEG, a `2736 x 1824`/`9,980,928`-byte YUY2 buffer, two
  `14,971,392`-byte RGB8 buffers, bounded JPEG chunks, raw and rectified tag
  batches, optical-map and pose bindings, and both normal and natural tag-loss
  cases. It records only an unsent T=105 fixture and synthetic T=1051. Generic
  B0477 source-bound replay exact-compares every verified/applied contract,
  camera/timing/calibration/JSON/blob/manifest value to the originating session,
  so another self-consistent generic package cannot be substituted. Generic
  replay verifies package integrity and declared bindings but does not yet
  independently recompute decode, undistortion, detection, pose, or calibration;
- the calibration registry now rejects unknown/noncanonical artifact,
  publication, and index shapes; guards roots, paths, symlinks, and bounded
  reads; verifies immutable per-digest predecessor receipts; and serializes
  same-process and cross-process writers. Its bounded linear-time publication
  graph requires exactly one genesis/head, strictly increasing versions, and no
  branch, cycle, missing predecessor, or orphaned publication. Self-consistent
  artifact/index tampering and concurrent publication now fail or converge
  without overwrite. A hostile actor able to rewrite the registry and its
  unkeyed receipts together still requires a separate signed or protected
  monotonic physical trust anchor;
- immutable typed vision records now bind exact frame identity/timing/settings,
  detector identity/configuration/implementation, canonical marked-tag corners
  and diagnostics, tag-map and intrinsics identities,
  pose/covariance/residuals, rejection reasons, and zero authority. The
  fixed-overview virtual runtime produces those records from real JPEG bytes,
  requires one passing result per physical-action hover, stores them in
  `vision.json`, and recomputes them during replay. It applies no waypoint or
  robot-frame correction. A separate adaptive-schema service now projects the
  achieved six-joint state through `Wv_T_link2 * link2_T_E * E_T_C_arm`,
  renders the resulting partial moving-camera view, independently recovers
  `C_arm_T_board`, and forms a quality-gated candidate `Wv_T_board`. The
  v1.1 planar estimator refines its unique maximum-support mask monotonically:
  refits may remove but never re-admit excluded tags. The synthetic mount and
  intrinsics are explicitly unmeasured;
- the B0477 static path now uses one canonical `C_overhead_optical` contract.
  It preserves the published 49-degree horizontal/38-degree vertical claims as
  provenance, uses an aspect-consistent 49-degree/33.799-degree square-pixel
  rectilinear projection, adds a nonzero Brown-Conrady synthetic stress warp,
  and rectifies detected capture corners into a separately named estimator
  pixel space before pose recovery. Frame, focal, FOV, distortion, inverse-map,
  or support-source drift fails closed; none of those synthetic coefficients
  are delivered-camera calibration;
- the adaptive runner keeps one opaque board transform shared only by its
  raster camera and achieved-FK contact projector. The correction planner
  cannot read that truth. A pure decision returns `REJECT`, `NO_CHANGE`, or
  `APPLY`; `APPLY` reconstructs the current tip from a typed fresh
  `VIRTUAL_PLANT` feedback sample, checks a vertical/lateral/vertical
  correction maneuver, re-solves the entire remaining Cartesian suffix under
  the same controller-limit/margin/rank/joint-delta gates, and atomically
  replaces the old queue only after all replacement waypoints pass. A
  corrected hover is re-observed before contact. Execution, source-waypoint,
  and registration-revision identities remain separate. Keyboard 12 mm and
  phone 8 mm shift regressions correct, converge, resolve the intended target
  from truth-derived contact, verify output independently, and park; adaptive
  full-catalog coverage additionally accepted 75/75 target sessions on
  2026-09-04 under its 2.5 mm / 0.5 degree / 5 px synthetic policy and
  128-execution per-route ceiling, with report SHA-256
  `232dcdd5c7bb6cb7afb6e4dcac6001797991faa54587dd7e0979e67880d8d4e2`;
  the distinct 1.5 mm / 0.25 degree / 3 px perturbation policy passed all
  20/20 declared outcomes, including four expected safe rejections, with
  report SHA-256
  `9dda1bc28015ee6943d0e5017e16756dd30c6d0530d950a818161c28aa15dd20`.
  Adaptive artifact
  persistence/replay and all physical qualification remain open;
- its simulation foundation pins an official Waveshare ROS Xacro commit and
  exact-byte bounded local kinematic projection, implements typed rigid
  transforms/URDF/FK, imports a nominal RC03 scene for AABB tool-tip clearance,
  provides both analytic tag projection and the real-JPEG fixed-overview
  detector/planar-pose path, maps synthetic keyboard and phone targets, builds
  deterministic park/transit/hover/approach/contact/retract paths, and performs
  bounded sequential numerical IK with sampled joint-margin/delta checks plus a
  fail-closed numerical-rank gate for the solver's weighted five-constraint task
  Jacobian; normalized conditioning is report-only, not physical singularity
  proof; and
- exact static support/camera geometry, measured camera intrinsics and
  `Wv_T_C_overhead_optical`, controller-frame correlation, full
  link/tool/gantry/camera/cable/lighting collision geometry, qualified frame
  freshness/settings behavior, commissioned calibration capture/promotion,
  measured keyboard/phone profiles, force/interlock hardware, hardware-in-loop
  characterization, motion execution, and result verification remain open.
  Frame-to-joint synchronization remains open only for the optional Phase 2
  arm camera.

Software can be developed against simulation and recorded images while the hardware is built, but energized device contact cannot bypass those gates.

### 3.3.1 Software implementation checkpoint

The pre-hardware runtime now connects the development flow through typed,
fail-closed paths. The legacy replay and optional adaptive path is:

```text
requested text
  -> device semantic compiler
  -> profile-bound nominal target catalog
  -> RC03 placemat/keepout scene
  -> documented reach placement + bounded park overlay
  -> optional promoted, sensitivity-only layout hypothesis
  -> deterministic tool-tip path checks
  -> bounded full-route waypoint densification
  -> sequential diagnostic URDF IK with controller-limit/margin/delta gates
  -> solver-weighted five-constraint task-Jacobian numerical-rank gate
  -> retained solver-achieved board-frame tip position and tool axis
  -> independent 46-keyboard + 29-phone route-coverage evidence
  -> full-body collision readiness hold
  -> validated zero-authority hardware-neutral runtime-port contract
  -> strict virtual-workcell bootstrap and locked rank-1 scenario
  -> explicit virtual calibration closure
  -> action-indexed virtual arm and one of two zero-authority vision paths:
       Phase 1 migration target: fresh fixed-overview JPEG at each
         physical-action HOVER
         -> camera_overview_optical_T_board quality gate + replay artifacts
       optional Phase 2 research: achieved six-joint FK -> moving C_arm -> fresh JPEG
         -> plan-blind tag36h11 decode -> C_arm_T_board
         -> candidate Wv_T_board -> REJECT / NO_CHANGE / APPLY
         -> on APPLY, full accepted corrected suffix -> atomic queue replacement
         -> corrected HOVER re-observation and convergence
  -> post-processing action/target/waypoint association only in both paths
  -> fresh achieved-FK contact resolved against full placemat target geometry,
     synthetic depth/normal/dwell policy, focus, and Android UI state
  -> ContactResult-only independent output observer
  -> natural image/capture fault rejection, fault-stop lifecycle, final park
  -> legacy report-v3/manifest-v2 replay OR adaptive report-v1 in-memory evidence
  -> explicit physical static-camera, static eye-to-hand registration,
     controller correlation, collision, contact, physical-outcome-observer,
     and hardware-validation holds
```

The additive dense V2 path reuses the same semantic compiler, locked rank-1
route, accepted IK evidence, and virtual device truth while making the joins
explicit:

```text
exact ActionPlan
  -> semantic-step schedule
     -> Android state observation owns no contact/command/journal
  -> physical contact occurrences
  -> accepted dense route with known initial park
  -> one non-wire controller target for every later waypoint
  -> one fresh synthetic B0477 report at each contact's final HOVER
  -> every endpoint + every incoming exact 0.5 joint midpoint collision query
  -> exact `NOMINAL_ONLY` static Phase-1 calibration projection
  -> ordered authorization-v2 command suffix + advancing synthetic interlocks
  -> per-contact durable journal
  -> non-wire controller emulator -> achieved geometry-based virtual contact
  -> ContactResult-only outcome -> retract -> final park
  -> zero-hardware report with every physical authority false
```

For the acceptance pair, keyboard `test` contains 48 route waypoints, 47
emulator commands, and four contacts; Android `test.` contains 61 waypoints,
60 commands, and five contacts. V1 remains unchanged. The V2 collision adapter
uses complete but deliberately isolated stand-in geometry so the 26-body query
and binding contract can run; it explicitly does not establish workcell
clearance. The emulator has no wire encoder or transport, and its `R_ctrl`
correlation is uncommissioned.

The implementation provides one coherent simulation-context loader, an
independent software simulation-bundle lock, a 17-check placemat alignment
report, exhaustive target/phase/tool IK screening, ordered calibration-status
reporting, strict non-opening arm-connection configuration, hash-pinned raw
feedback/FK reproduction, strict raw-wire/JPEG/detection/bracket capture-bundle
verification, a typed hardware-neutral mission-port boundary, a bounded
fixed-overview raster/detector/planar-estimator service, and semantic,
geometric, IK, park, trajectory, calibration, and vision reports that always
retain zero physical authority. The ports explicitly separate clock,
cancellation, arm lifecycle/execution/feedback, observation, contact, outcome,
and evidence services; their current existence does not authorize or implement
physical execution. Simulation services
load the pinned URDF through one exact-byte bounded boundary, hash the same
bytes they parse, and serialize the loaded digest and byte count in provenance.
Keyboard and phone compilers are explicitly bound to their geometry profile
IDs; a mismatched semantic map is rejected before path generation.

The selected B0477 preparation path is now a separate additive stack. A
provider-neutral UVC contract accepts inventory from an implementation boundary;
its checked-in provider is deterministic and fake, so it cannot enumerate or
open a device. A sealed synthetic ChArUco artifact commits 32 native-resolution
views before assessment (24 training and 8 held out), binds their hashes and
split, and links the same synthetic persistent-camera-identity and reopen-
settings hashes used by the UVC fixture. The application coherence assessor
then revalidates the purchase profile, support design, commissioning rehearsal,
UVC inventory, intrinsics artifact, exact `5472 x 3648 @ 9 fps YUY2` mode, and,
by default, a normal/tag-loss pixel pair. The current complete run is
`SYNTHETIC_B0477_STACK_COHERENT` at 10/10 checks. The optional
`--skip-pixel-vision` path is a faster five-artifact loop, not the milestone
gate. Both paths request zero camera frames, emit zero arm/contact commands,
and grant no hardware, capture, calibration, extrinsic, motion, contact, or
release authority. Their thresholds and numbers are synthetic test data and
must not be reused as physical acceptance criteria.

Every accepted IK waypoint now retains the solver-achieved board-frame tool-tip
position and hand-TCP axis rather than only the requested waypoint. At a contact
endpoint the session converts that achieved state into a bounded `ContactEvent`
containing board XYZ, contact normal, dwell, action occurrence, and an explicit
synthetic activation count. It supplies no planned target ID or expected
character. The keyboard/Android truth model independently resolves that event
against every content-addressed placemat target polygon plus synthetic
surface-depth, normal-angle, dwell, focus, and UI-state rules. Ambiguous,
outside, wrong-state, or policy-invalid contacts fail closed. Resolved text
comes only from the immutable region/output map and is returned in a typed
`ContactResult`.

The current virtual commissioning acceptance pair is keyboard `test` (48
accepted joint waypoints and four contacts) plus Android `test.` (61 waypoints,
an initial UI-state check, and five taps). A separate observer receives only
`ContactResult` values—never the action plan, a planned target, or an expected
character—enforces strictly increasing/exact-once result consumption, and
accumulates resolved plaintext only in memory. Before each of the four or five
contacts, respectively, the schema-v3 executor requires a fresh, independently
decoded fixed-overview JPEG/tag/planar-pose result at the corresponding hover.
It verifies only final output hash and length, never serializes a raw output or
JPEG field, and always records zero hardware commands. Repeated target names
retain distinct action indices.

Declarative camera faults now traverse the perception boundary: unavailable
capture stops with no frame, while tag-loss mode occludes world IDs 0-3 in the
rendered pixels and the estimator naturally fails its four-tag pose minimum
after the detector finds only held-out IDs 4-5. There is no pose retry, contact
retry, camera-backend fallback, or automatic resume. Manifest-v2 evidence binds
the complete redacted attempt ledger in `vision.json`; replay revalidates its
nested records and hashes and recomputes all session artifacts from the locked
sources. This completes the current fixed-overview pixel-gated plus
geometry-driven virtual-contact milestone; it does not reduce any physical
gate.

The replayable action plan still exposes the ordered semantic target sequence,
so these packages are redacted rather than confidential and require normal
access control for sensitive text.

The current schema checkpoint is the recorded keyboard golden at
[`software/runs/virtual-45c312f55d6a86c2a55f12bc/manifest.json`](software/runs/virtual-45c312f55d6a86c2a55f12bc/manifest.json):
session report
`45c312f55d6a86c2a55f12bcb88122a3f425e48ceeb8db6a93a52ae1104d70f3`,
4/4 pixel attempts passed, and replay returned `REPLAY_IDENTICAL`. This is a
regression anchor, not hardware evidence.

The fixed-overview vision runtime now exercises the complete typed boundary.
Immutable records cover exact frame/JPEG/timing/settings bindings, detector
identity and hashes, marked-tag canonical `TL, TR, BR, BL` corners and fit
diagnostics, map/intrinsics bindings, pose/covariance/residual evidence,
rejection reasons, and explicit zero authority. The processor receives only a
capture sequence and capture mode, not the plan, target, expected corners, or
simulator pose; the attempt ledger associates action identity only after the
result returns. The session's synthetic quality check separately compares the
estimated fixed-fixture pose with the known fixed-fixture pose and currently
requires IDs 0-5 as pose inliers, at most 1.0 px reprojection RMSE, at most
1.0 mm translation error, and at most 0.1 degree rotation error. That locked
regression therefore does **not** yet implement the Phase 1 held-out contract:
migration must fit T0-T3 only, exclude K0/P0 from the solve, and evaluate K0/P0
residuals afterward.

This is valid synthetic session/replay vision evidence only. Its topology now
matches the selected static-overhead primary, but it does not model a selected
camera/lens/support, calibrate distortion or `Wv_T_C_overhead_optical`, derive a
qualified board-to-robot transform, alter a waypoint, or apply any physical
robot-frame correction. It also does not create an independent
physical keyboard/OS or Android/ADB outcome observer. Physical capture,
calibration, qualification, outcome verification, and hardware validation
remain blocking work.

The present nominal contact screening result is a design rejection signal, not
a physical reach claim: with the nominal -100 mm virtual tool, only **6 of 46**
keyboard contacts (`A`, `C`, `SPACE`, `TAB`, `X`, and `Z`) solve within the
current URDF/controller-intersection assumptions, while **29 of 29** synthetic
phone contacts solve. Across the complete four-tool/four-phase matrix, **625 of
1,200** target poses solve. The required Cartesian park `(305, 400, 70)` solves
only for the no-extension `hand_tcp_only` case, and that solution has zero
effective joint margin; the 80, 100, and 120 mm contact-tool cases all reject it.
Even the phone result is therefore not a complete executable route. This means
the current assumed arm/base/tool arrangement must be revised or measured before
keyboard typing can advance. The phone result
does not establish tap reliability because its targets are synthetic, small,
and have no measured screen homography, tool/error-footprint proof,
static-camera visibility/tool-marker coverage, or UI-outcome observer.

The bounded park study has now removed that first nominal-park blocker without
editing the frozen placemat. Its selected `(290, 10, 70) mm` overlay passes
pointwise for both 100 mm tools with 0.2704734350 worst normalized arm margin
and 10 mm modeled planar point clearance. The full keyboard `"a"` route then
accepts 24/24 waypoints. The full phone `"a"` route still fails at `APPROACH`
because 0.000657824 is below the 0.01 arm-margin gate, and both reach finalists
reject its `key_a` contact. This is stronger integration evidence—the semantic
plan, placement/park selection, motion-phase ordering, densification,
sequential IK, and task-rank boundary are connected—but it also shows that the
current base/tool/layout remains infeasible for the full mission.

The broader service now searches only source-traceable sensitivity axes and
keeps field-level evidence with every value. Its bounded 243-hypothesis coarse
grid plus 34 refinements yields 49 regression passes, but the expensive full
catalog screen intentionally covers only the ranked top eight; 41 passes are
reported as omitted. Six are eligible for a separate mission-route screen.
Rank 1 accepts all 75 independent park-to-target-to-park routes, whereas the
explicitly historical Freeze-005 baseline, retained unchanged as simulation
provenance under active Freeze 011, accepts 38/75. This establishes a useful region
for physical measurement and redesign. It does not establish that rank 1 is
mechanically possible, nor does it prove a continuous multi-target sequence.

The collision layer supplies typed sphere, capsule, and oriented-box bodies,
evidence-bearing exclusions, mandatory positive clearance/uncertainty policy,
bounded pose queries, and bounded discrete sweeps. Its current-artifact audit
names all 19 required robot, attachment, and workcell bodies and fails closed
because complete geometry is unavailable. The route simulator still uses
coarse tool-tip AABBs. Separately, the static-B0477 mission contract requires
26 bodies and nine source bindings, then evaluates every dense endpoint and
one exact joint midpoint per incoming segment. V2 executes that query through
a deliberately isolated fixture so ordering, target-local CONTACT allowance,
harness sampling, and authorization binding can be tested now. Unknown links,
attachments, supports, and cables are intentionally placed outside the route;
that is not a clearance model. The new kernels cannot be promoted into
physical route acceptance until the missing/unknown bodies, frame bindings,
sampled cable geometry, and accepted clearance policy exist. Clear discrete
samples will remain diagnostic, not a continuous-collision certificate.

Trajectory schema v2 evaluates deterministic numerical rank of the solver's
weighted five-constraint residual at every selected IK state. It reports the
normalized minimum singular value and condition number without using either as
a release gate. This is not the physical six-dimensional geometric Jacobian,
manipulability/force capability, or collision analysis; all remain blocking.

The optional Phase 2 eye-on-arm capture bundle now structurally binds exact T=1051 wire bytes,
JPEGs, normalized detections, and host pre/exposure/post brackets to the
exact-file-pinned dataset/evidence pair and verified context. It still cannot
qualify device measurement time, clock-correlation content, camera/artifact
identities, original tag corners/inliers/covariance, commissioning, or artifact
promotion.

The software boundary must also reject a changed RC03 tree whose bytes no
longer match `system_manifest.json`. Hardware-side edits are never accepted by
silently refreshing hashes: the build owner must complete the controlled RC03
revision, then issue a synchronized system manifest and invalidate dependent
simulation/calibration evidence.

### 3.3.2 Placemat geometry sensitivity checkpoint

The source-bound [`stress-placemat-geometry`](software/docs/PLACEMAT_GEOMETRY_SENSITIVITY.md)
service now distinguishes nominal data-flow alignment from robustness to
assumed build error. It binds active Freeze 011, the current RC03 layout and
75-target catalog, the repaired static-support design, the purchased B0477
profile, and its implementation identity. Its default 59-case matrix reports
0/46 keyboard and 27/29 phone targets with sampled gaps; the zero-bound control
keeps all 75 nominal centres inside their regions. The service performs no IK,
pixel vision, collision proof, contact-depth acceptance, hardware access, or
motion. Its bounds are unmeasured sensitivity inputs and confer zero physical
authority.

### 3.4 Freeze, precedence, and RC03 import contract

The machine-readable freeze is [`software/config/system_manifest.json`](software/config/system_manifest.json). `FROZEN_DIGITAL` means a controlled design decision is fixed; it does not mean physical acceptance. `SELECTED_UNQUALIFIED`, `NOMINAL_ONLY`, and `OPEN_BLOCKING` values cannot authorize contact.

The runtime importer shall read controlled geometry, selected routes, active physical-build identity, canonical gate states, active-build step signoffs, and synchronization hashes. It shall produce an immutable `rc03_build_snapshot` and never infer physical PASS from nominal geometry or `RELEASE_VALIDATION.json: PASS`.

Hardware motion is blocked when the active build ID is null or mismatched, a required route is false, a required canonical gate or build-specific signoff is missing/stale/non-PASS, the tag map is nominal, the physical release is not accepted, or any source/snapshot hash disagrees. The current active build satisfies only the identity prerequisite; `safe_to_power_robot` and `contact_enabled` remain false. Source precedence is active-build evidence, canonical measurement/gate records, measured tag map, controlled layout/geometry, then generated reports and manuals.

## 4. Board review and changes to resolve before the board is locked

### 4.1 What is already right

- The board gives the arm, devices, fiducials, and tooling a shared physical structure.
- The four world tags are spread around the usable area rather than clustered.
- K0 and P0 are held out from the primary pose solve, which makes them useful residual checks.
- The keyboard and phone stations are mechanically registered and removable.
- The phone/TCP station has a replaceable datum cartridge.
- The existing package contains candidate 2020 mast/plate geometry that can
  inform the selected static-overhead design, while the bundled arm holder is
  retained only for an optional future local camera.
- The compliant tool already anticipates controlled axial travel and route-specific tips.

### 4.2 Gap: one TCP puck is not a full static-camera/robot/board calibration

The service station provides one known TCP cartridge point. One point can check
local contact height and one transform chain, but it cannot identify a full
six-dimensional board-to-robot transform, static camera extrinsic, or route-
specific TCP. The selected static camera therefore requires two independently
validated relationships:

```text
Wv_T_C_overhead_optical       fixed eye-to-hand camera extrinsic
C_overhead_optical_T_B(i)     fresh board observation from AprilTags

Wv_T_B(i) = Wv_T_C_overhead_optical * C_overhead_optical_T_B(i)
```

Board tags alone do not identify robot pose and cannot distinguish a bumped
camera from a shifted board. The support must be rigidly related to the
workcell reference, and the calibration shall include a robot-base/support
witness or an equivalent fail-closed installation check.

**Method A — distributed board-to-robot touch registration, Phase 1 baseline**

- Provide at least three non-collinear, touch-safe reference targets with known
  board XYZ coordinates; four or more with one held out is better.
- Spread them across the reachable keyboard and phone workspace rather than one
  local cluster.
- Register them through existing RC03 interfaces; never probe AprilTag paper.
- Probe them with the commissioned TCP and fit `Wv_T_B`/`B_T_Wv`. In the same
  unchanged installation, capture `C_overhead_optical_T_B` and derive
  `Wv_T_C_overhead_optical = Wv_T_B * B_T_C_overhead_optical`; use the existing
  keyed puck as an independent held-out check.
- Any added hole, permanent datum, or new fixed coordinate requires a
  controlled RC03 revision with regenerated geometry and checksums.

**Method B — static eye-to-hand robot-held-target solve, alternative**

- Lock the overhead camera, lens, focus, mode, settings, support, and cable.
- Move a qualified pose-observable target rigidly attached to the robot through
  diverse, non-singular poses while the camera remains fixed.
- Solve `Wv_T_C_overhead_optical`, bind it to the exact robot reference and
  camera installation, and retain held-out target poses.
- Gate on coverage, rank/condition, residuals, camera/support witness, and
  independent keyboard/puck/phone-region checks.
- Correlate `R_ctrl` independently; never alias it to `Wv`.

Either method must be reconciled with the live `C_overhead_optical_T_B`
estimate and a held-out end-to-end contact-location test. A top-visible tool
marker with calibrated `M_T_T` is conditional if measured endpoint uncertainty
does not fit inside target safe regions.

The existing paired 2020 mast is now a candidate input to the primary support
design, not a released fallback. Its 700 mm geometry, plate, anchoring,
stiffness, and collision envelope must be qualified or redesigned. The former
eye-on-arm `C_arm`/`E_T_Carm` workflow remains optional Phase 2 research with
its own payload, cable, synchronization, calibration, visibility, and
collision gates.

### 4.3 Gap: board tags do not prove device pose

T0-T3 localize the board. K0/P0 check the board transform near the stations. None is attached to the keyboard or phone, so none proves that the device is seated, has the expected case, or has not shifted inside its station.

The runtime therefore also needs:

- keyboard outline/key-anchor detection or a device-mounted/fixture-mounted presence marker;
- phone outline/screen-corner detection and a device-presence check;
- station seating and clamp checks in the operator preflight; and
- invalidation of device calibration after any device removal unless repeatability evidence supports reuse.

### 4.4 Static-overhead field-of-view, support, and occlusion gate

The Phase 1 camera is fixed to a rigid workcell or bench-referenced overhead
support, not to a moving RoArm link. The support height must first clear the
complete robot, tool, and cable swept volume. Only then may the camera and lens
be selected to cover the provisional 670 × 517 mm view and provide enough
pixels at the worst tag, keyboard key, phone target, and optional tool marker.
A 4:3 landscape image is geometrically efficient for the 610 × 457 mm
placemat, but the purchased B0477 detailed-screening configuration uses its full
native 3:2 frame. Its aspect-conservative calculated view still covers the
required envelope; physical measured undistorted coverage remains a gate.

The superseding camera addendum shall release this visibility contract:

- the primary clear observation posture sees all six installed tags; T0-T3
  solve `C_overhead_optical_T_B`, while K0/P0 remain independent checks;
- every supported keyboard and phone target has a qualified primary and
  recovery observation posture in which all six tags pass, along with device
  presence, focus, glare, residual, covariance, and freshness;
- the camera buffer is flushed within a measured bound and the accepted frame
  is uniquely fresh after the arm has settled;
- arm/tool occlusion during final approach is expected, so the runtime observes
  while retracted, approaches and contacts, retracts, then observes again;
- partial or weak geometry, stale or duplicate frames, changed settings,
  support movement, board movement, blur, phone-screen banding, glare, or a
  missing required device/tool feature blocks descent; and
- a failed primary camera cannot silently fall back to another camera.

The additive [static-camera hardware package](hardware/static_overhead_camera/README.md)
now supplies the candidate support, height, optical selection, BOM,
coordinates, schematics, and source-locked simulation contract. It must still
qualify gantry/post/crossbar stiffness, anchoring, positive camera retention,
fasteners, camera interface, strain relief, lighting, collision geometry,
warm-up, remove/reinstall repeatability, arm-cycle disturbance, and 24-hour
drift. The existing paired 2020 mast, 700 mm posts, universal plate, and
commercial boom are unsuitable as the default static primary and remain
historical unqualified alternatives.

### 4.4.1 Standalone package facts and historical arm-camera candidate

The exact purchased product is the standalone Waveshare RoArm-M3 page with the
RoArm-M3-Pro option, not the dual-arm AI kit. Its package image lists the
assembled Pro arm, 12 V/5 A supply, accessory pack, expansion mounting plate,
camera holder, EoAT expansion plate, and base mounting plate. A camera is not
listed. The product description separately says the illustrated camera is for
reference only and only the LED light is included in that peripheral example.

The word **ESP32** identifies the arm's onboard `ESP32-WROOM-32` controller. It
does not identify an included `ESP32-CAM`, OV2640, or camera-stream endpoint.
Arm commands and camera frames are separate transports.

Freeze 009 historically selected the bundled 21.0 × 13.5 mm holder and a
geometrically matching Waveshare IMX335-B candidate on the moving upper-arm
rails. The 2026-09-05 decision removes that mechanical-fit requirement from the
Phase 1 primary camera: an overhead camera instead needs a rigid support
interface, suitable optics, stable USB/UVC identity, and physical acceptance at
the final height. The IMX335-B and bundled holder remain unselected Phase 2
research inputs and must not be bought or commissioned merely because they fit
one another.

If a Phase 2 arm camera is later selected, it requires its own camera identity,
intrinsics, `E_T_Carm`, exposure-to-joint synchronization, payload/moment,
mounting, cable, collision, visibility, and disagreement policy. It cannot be
an automatic substitute for the overhead primary. The optional
`esp_http_mjpeg` adapter similarly remains unselected; Phase 1 prefers an
explicit USB/UVC source bound by persistent identity rather than camera index.

### 4.5 Contact sensing and gravity-safe power-loss gate

The compliant spring limits stiffness and absorbs small Z error, but it does not measure contact force. Servo load is not a calibrated force measurement. RC03-INT-R1 contains qualification by calibrated force gauge/weights, but it does not release an inline sensor, local guard, or gravity catch. Before installing those additions:

- select and mechanically integrate a route-appropriate inline single-axis load cell or force-sensitive element without obscuring required overhead/device/tool-marker observations or breaking the phone stylus's qualified conductive path;
- prefer a small local controller that samples the sensor, applies a latched hard-overforce threshold, and opens an independent motion-enable/interlock path without relying on host-PC or serial latency;
- retain a passive mechanical compression/overtravel stop because neither software nor a force sensor is the final physical travel limit;
- characterize added mass, offset, cable force, electrical noise, zero drift, sample rate, and influence on the arm error budget; and
- keep normal software thresholds below the independently approved hard threshold.

The power-cut E-stop also needs a mechanical consequence review. Removing servo power may let the arm fall under gravity. Establish and test a passive safe-collapse envelope with a dummy load and devices removed at representative poses. Add a counterbalance, tether/catch, physical support, or safe park geometry if an unpowered arm can strike a person, device, camera, or fixture. The E-stop gate passes only when power removal is independent **and** the resulting unpowered motion is acceptably contained. A local sensor/interlock is an engineering risk control, not a claim of safety certification.

The marker, contact guard, and gravity containment require a controlled RC03 addendum or later revision and their own PASS gates. Phase 1 may not simply install them under existing RC03 gates. Autonomous contact stays blocked until the addendum and affected downstream evidence pass.

## 5. Feasibility truth and error-budget rule

### 5.1 Manufacturer capability is a starting bound, not our result

Waveshare lists:

- approximately ±5 mm unidirectional positioning repeatability under the same load;
- 200 g payload at 500 mm reach;
- a 1120 mm maximum horizontal workspace diameter;
- 12 V/5 A recommended power; and
- automatic motion toward the middle position at startup.

We will characterize the actual assembled arm in the exact workcell. We will not convert encoder resolution into an unsupported tip-accuracy claim.

### 5.2 Target-safe-region rule

Every key or phone control shall be represented as a polygon in its device plane. The contactable safe region is the target polygon eroded by:

- physical tip radius;
- required edge guard margin; and
- the bounded lateral positioning uncertainty.

For conservative release, use a bounded sum:

```text
E_total = E_board_pose
        + E_camera_intrinsics_and_distortion
        + E_static_eye_to_hand
        + E_static_support_drift
        + E_robot_controller_correlation
        + E_tcp_and_compliance
        + E_device_pose
        + E_optional_tool_marker
        + E_descent_shift
        + E_motion_repeatability
```

If statistically independent terms are also reported as covariance/RMS, that is useful for diagnosis, but it does not replace the conservative release bound.

A target is enabled only when:

```text
E_total + tip_radius + guard_margin < target_inscribed_radius
```

For non-circular targets, the implementation will erode the actual polygon and require a non-empty safe polygon. The planned point will normally be the point of maximum distance from the eroded boundary, not merely the visual center.

### 5.3 Feasibility sequence

1. Characterize repeatability on a no-contact hover grid.
2. Characterize a single large compliant contact target.
3. Add visual tool correction and repeat the grid.
4. Demonstrate keyboard-size targets.
5. Demonstrate large phone targets.
6. Demonstrate a fixed numeric keypad.
7. Attempt stock phone QWERTY only if its target polygons pass the measured bound.

Failure at a step is a useful engineering result and determines the next hardware/sensing change.

## 6. System architecture

```text
User text / named action
          |
          v
  Input normalization and capability check
          |
          v
 Keyboard compiler or phone UI state machine
          |
          v
 Device-plane target polygons and action plan
          |
          v
 Calibration registry + frame transforms + uncertainty
          |
          v
 Safety supervisor and motion planner
          |
          v
 Static overhead camera ---> fresh board/device observation + support witness
          |                         |
          |                         v
          |              live Wv_T_B + bounded uncertainty
          |                         |
          v                         v
 USB serial RoArm adapter ----> checked hover + optional visible-tool correction
          |
          v
 Normal approach ---> bounded compliant contact ---> normal retract
          |
          v
 Independent computer/phone outcome verification
          |
          v
 Traceable run record, metrics, images where authorized, and recovery state
```

### 6.1 Architectural boundaries

| Layer | Responsibility | Must not do |
| --- | --- | --- |
| RC03 import | Read controlled board/device/station geometry and hashes | Silently rewrite RC03 source files |
| Arm protocol | Encode/decode serial JSON, preserve units and raw feedback | Decide whether a contact is safe |
| Geometry | Frames, transforms, planes, polygons, uncertainty | Send motion |
| Vision | Intrinsics, tags, screen/tool localization, quality scores | Assume an unknown transform |
| Device model | Key/screen target maps and state transitions | Use raw arm coordinates |
| Planner | Transit/approach/contact/retract paths and keepouts | Bypass release gates |
| Safety supervisor | State machine, interlocks, freshness, watchdogs, faults | Claim to replace a physical E-stop |
| Executor | Serialize actions and collect feedback | Improvise after an unclassified error |
| Verifier | Observe actual computer/phone result | Inject the same input being tested |
| CLI/API | User-facing commands and reports | Expose arbitrary contact coordinates by default |

## 7. Coordinate frames and transform contract

### 7.1 Required frames

| Symbol | Frame |
| --- | --- |
| `B` | RC03 board frame |
| `C_overhead_optical` | primary static overhead camera optical frame |
| `C_arm` | optional Phase 2 arm-mounted camera optical frame; disabled by default |
| `Wv` | vendor URDF `world` planning root |
| `R_u` | vendor URDF `base_link`; distinct from `Wv` because the pinned model includes a fixed offset |
| `R_ctrl` | firmware/T=104 Cartesian frame; never aliased to `Wv` or `R_u` |
| `E` | optional exact moving arm link carrying `C_arm` in Phase 2 |
| `G` | gripper/tool-holder frame represented by the controller |
| `T` | physical contact tip/TCP frame |
| `F` | pose-observable calibration target; robot-held for an eye-to-hand solve or board-registered for held-out validation |
| `M` | conditional visible tool witness for identity/seating/deflection, not global arm placement |
| `K` | keyboard device frame |
| `P` | phone body frame |
| `S` | physical phone screen-plane frame |
| `U` | phone logical pixel/UI frame |

### 7.2 Notation

`A_T_B` maps coordinates expressed in frame `B` into frame `A`.

Examples:

- The existing detector's `board_to_camera_matrix` is directionally
  `C_overhead_optical_T_B` for the primary frame, but its translation is in
  metres.
- The planning layer needs `B_T_Wv` (and its inverse) to convert board targets into the pinned vendor-URDF world for FK/IK.
- At image `i`, the primary registration is
  `Wv_T_B(i) = Wv_T_C_overhead_optical * C_overhead_optical_T_B(i)`; the
  camera extrinsic does not depend on arm joint state.
- Only the optional Phase 2 route uses
  `Wv_T_Carm(q_i) = Wv_T_E(q_i) * E_T_Carm`.
- A keyboard target follows `p_B = B_T_K * p_K` and then `p_Wv = inverse(B_T_Wv) * p_B`.
- A phone logical pixel follows `p_S = S_from_U(u, v)`, then `p_B = B_T_S * p_S`, then `p_Wv = inverse(B_T_Wv) * p_B`.
- A T=104 target is expressed in `R_ctrl`, whose audited FK differs from the vendor URDF endpoint by configuration-dependent residuals. No static alias or unqualified transform may turn a URDF pose into a controller command; the commissioned bridge must retain and bound that model discrepancy.
- The commanded gripper pose must account for `G_T_T`, the TCP offset.

### 7.3 Transform requirements

- Use right-handed 4×4 homogeneous transforms in double precision.
- Use millimetres and radians internally; convert only at explicit boundaries.
- The RC03 vision adapter shall multiply only the detector matrix's translation
  component by 1000 before inserting `C_overhead_optical_T_B` into the
  millimetre frame graph, preserve `source_translation_unit: m`, and reject
  untyped direct composition. An optional `C_arm_T_B` uses the same explicit
  boundary but a distinct artifact type.
- Attach frame names, calibration artifact IDs, timestamps, source hashes, residuals, and uncertainty to every persisted transform.
- Reject multiplication when frame names do not compose.
- Never mix the SDK's degree-based convenience API, raw JSON radians, and ROS metres/radians without typed boundary conversion tests.
- Maintain one transform convention across vision, calibration, planning, and logging.
- Require `arm_frame_contract.json` containing exact
  M3-Pro/controller/firmware identity, `Wv`/`R_u`/`R_ctrl`/`G` definitions,
  joint order/signs, commissioned-reference procedure hash, validated FK/URDF
  and controller-emulator source hashes, clamp/board/bench identity, and which
  feedback fields are reported versus FK-derived. Optional Phase 2 extends it
  with `E` and the camera-carrier chain.
- Require a separate static-camera contract containing persistent camera
  identity, native mode and settings, support/camera geometry, witness identity,
  `C_overhead_optical`, `Wv_T_C_overhead_optical`, calibration hashes, and
  freshness/settling policy.
- Do not assume T=105/T=1051 supplies a complete six-degree-of-freedom `Wv_T_G`; retain joint feedback and derive the tool-holder transform through validated vendor-URDF FK. Treat T=1051 Cartesian fields as separate `R_ctrl` diagnostics.
- Every persisted primary observation shall bind unique frame content,
  sequence/freshness, host capture bracket, exact settings, support witness, and
  action occurrence. It does not require joint-synchronized camera pose.
- Every optional arm-camera observation shall still bind exposure time to
  measured/interpolated joint feedback; a commanded pose is not a substitute.

### 7.4 Calibration invalidation

Invalidate affected transforms after any of the following:

- arm clamp movement, arm neutral recalibration, firmware/controller change, or board damage;
- static gantry/post/crossbar/plate/fastener, camera, lens, focus, aperture,
  resolution, driver, image orientation, strain relief, lighting, or aim change;
- optional arm-camera holder, carrier, camera, lens, or moving-cable change when
  that Phase 2 route exists;
- tool body, adapter, tip, gripper seating, spring, or marker change;
- station removal outside proven repeatability, fastener change, or board movement;
- keyboard removal/model/feet/layout change;
- phone removal, case/orientation/display scaling/navigation mode/keyboard-app change; or
- tag replacement, lift, damage, metrology change, or map regeneration.

The calibration registry shall express dependencies so invalidation is automatic and visible.

The dependency graph is explicit:

```text
rc03_build_snapshot
├─ measured_tag_map, station/device installation, static-camera/arm installation
├─ selected route assembly, contact guard, gravity-safe stop
camera_intrinsics <- camera serial, lens, focus, resolution
C_overhead_optical_T_B <- camera intrinsics, measured_tag_map, fresh qualified frame
Wv_T_C_overhead_optical <- camera/support identity, robot/base reference,
                             eye-to-hand calibration and held-out validation
Wv_T_B(i) <- Wv_T_C_overhead_optical, C_overhead_optical_T_B(i)
M_T_T <- optional visible marker, exact tool, TCP and held-out validation
G_T_T_free / force-travel <- exact route, spring, tip, sensor, seating
B_T_K <- active build, keyboard station, exact keyboard, seating evidence
B_T_P / B_T_S / S_from_U <- active build, phone station, exact phone/display/UI state
target_error_budget <- transforms, static-support drift, image freshness,
                       repeatability, load/approach, tool correction, targets
E_T_Carm <- optional Phase 2 camera/carrier/FK/timing artifacts only
released_capability <- target error budget plus projected canonical/build gates
```

Every artifact stores dependency hashes and active build ID. A mismatch yields
`BLOCKED_STALE_DEPENDENCY`; old evidence remains immutable. A static support,
camera, cable-strain, lighting, or aim change invalidates the static extrinsic,
visibility atlas, witness baseline, and dependent corrected-repeatability
evidence. Firmware, neutral, FK, servo, base, or clamp service invalidates robot
registration and controller correlation, but not camera intrinsics unless the
optical system changed. Tool changes invalidate TCP/compliance and `M_T_T`
without invalidating the static camera extrinsic. Optional arm-camera artifacts
remain in their own dependency branch. Hardware changes also reopen the earliest
affected RC03 step and every downstream signoff.

## 8. Calibration strategy

### 8.1 Camera intrinsics

Reuse and harden the existing ChArUco workflow:

1. Install the final camera on the accepted static support with final fasteners,
   positive retention, strain relief, witness marks, and lighting; lock native
   resolution/pixel format, orientation, focus, aperture, exposure, gain, and
   white balance.
2. Verify the printed 5×7 board's 25.0 mm squares and 17.5 mm markers.
3. Capture at least 30 sharp ChArUco views spanning the full image, edges,
   rotations, tilts, and relevant focus distances by moving the calibration
   target—not the commissioned camera; accept at least 20 and precommit a
   separate held-out validation set.
4. Calibrate and save the camera matrix, distortion coefficients, resolution, per-view errors, RMS, capture hashes, and settings.
5. Reject calibration if the runtime resolution differs.
6. Capture a held-out validation set; calibration images alone are not validation.

RC03's current criterion of no more than 1.0 pixel reprojection error remains the outer gate. Phone correction may require a tighter measured operational residual; that requirement will come from the target error budget.

### 8.2 Measured tag map and board pose

1. Complete `tag_direct_installation_pass` and `tag_plane_placement_measured` for all six tags.
2. Record actual X, Y, optical-plane Z, and yaw relative to the finished board top.
3. Regenerate `apriltag_map.json` as `coordinate_source: measured_installation` with a PASS placement gate.
4. Solve `C_overhead_optical_T_B` from T0-T3 in each fresh accepted frame.
5. Keep K0/P0 held out and report their residuals.
6. Require the existing 20/20 static detection gate for every ID.
7. Run an arm/tool-motion occlusion study and store visibility statistics for
   every primary/recovery observation posture plus support-witness, glare,
   freshness, and multi-frame stability evidence.

### 8.3 Static eye-to-hand robot/world registration

Required workflow:

1. Close the static support and optical definition with exact camera/lens,
   camera plate, posts/crossbar, attachment to the workcell or bench reference,
   lighting, cable route, collision geometry, and base/support witness.
2. Establish `Wv_T_C_overhead_optical` with a qualified eye-to-hand method. One
   method observes a rigid robot-held target `F` at 15-25 well-distributed,
   settled, achieved poses spanning both device regions and multiple heights.
   The other fits `Wv_T_B` from controlled touch datums and composes it with a
   simultaneous `B_T_C_overhead_optical` observation. Both require independent
   held-out validation.
3. Record raw frame bytes, detected target observations, exact achieved joint
   feedback/FK for calibration poses, capture brackets, warm-up state, support
   witness, camera/settings identities, and all source hashes. Timing is still
   evidence for a robot-held target solve, but the operational static camera
   pose is not recomputed from joints.
4. Reject solutions with inadequate spatial/axis diversity, weak rank,
   excessive residual, sensitivity to small perturbations, or disagreement
   between camera/support and robot/base witnesses.
5. Reject outliers only by a documented rule and preserve them in evidence.
6. Validate `Wv_T_B` on precommitted held-out robot poses and at independent
   board datums across the keyboard, phone, and TCP-puck regions.
7. Keep the existing single TCP puck as a held-out check; it is not enough by
   itself to solve a six-dimensional robot/board registration.
8. Store residual vectors, covariance/bounds, support drift, pose diversity,
   and controller-model discrepancy—not only one RMS number.

The core relations are:

```text
Wv_T_C_overhead_optical * C_overhead_optical_T_F(i) = Wv_T_F(q_i)
Wv_T_B(i) = Wv_T_C_overhead_optical * C_overhead_optical_T_B(i)
p_Wv = Wv_T_B(i) * p_B
Wv_T_T_observed = Wv_T_C_overhead_optical * C_overhead_optical_T_M * M_T_T  [if M is selected]
Wv_T_G_cmd = Wv_T_T_target * inverse(G_T_T_free)
```

Board tags alone cannot distinguish a camera bump from board movement. The
support/base witness and held-out robot/board checks therefore remain mandatory.
If held-out results do not meet the error budget, improve static support,
calibration geometry, controller correlation, target size, or the controlled
distributed-datum method from Section 4.2. Do not hide disagreement with offsets.

### 8.4 TCP and compliance calibration

For each selected route—keyboard rod/TPU and phone stylus separately, never installed simultaneously:

1. Complete the existing `tool_force_tcp_limits_approved` engineering gate using a calibrated force gauge.
2. Measure free travel, force at approved compression checkpoints, full return, coil-bind margin, retention/pull force, and 20-cycle behavior.
3. Determine the free-state `G_T_T_free`, spring axis, and tip contact point.
   Model the compressed TCP as `G_T_T(delta)` rather than one rigid transform.
   If selected, calibrate a top-visible marker `M_T_T` so the overhead camera
   can measure hover XY/attitude without treating it as the contact-force or Z
   model.
4. Probe the TCP cartridge at least ten times using a consistent approach direction.
5. Record X/Y/Z range and compare it with the approved route-specific axis limit.
6. Calibrate hover height, first-touch height, permitted compression travel, and retract distance for each device profile.
7. Calibrate the inline force sensor's zero, scale, drift, sample rate, normal warning/abort thresholds, and independent hard-overforce response using traceable reference loads.
8. Where feasible, perform TCP pivot calibration using 15-25 distinct orientations around a fixed point; otherwise use a metrologically controlled fixture and document the limited orientation observability.
9. Use a round, axially symmetric contact tip and require its axis to align with the device surface normal. Treat rotation about that axis as unconstrained because the arm does not provide a general six-degree-of-freedom tool pose.
10. Never infer phone contact force solely from servo load.

### 8.5 Keyboard frame and key map

1. Freeze the exact keyboard model, regional layout, feet state, cable state, and clamp preload.
2. Measure/observe at least three non-collinear keyboard anchors in board coordinates.
3. Fit `B_T_K` and the keyboard top plane.
4. Define every key as a polygon and center in `K`, including non-unit keys.
5. Generate regular alpha/numeric keys from measured pitch only after checking row stagger and rotation.
6. Teach or visually refine irregular keys such as Enter, Shift, Space, Backspace, modifiers, and arrow keys.
7. Measure press travel and release behavior on representative key types.
8. Measure a per-row or per-key contact-height correction map for sculpted/sloped keycaps; a single fitted keyboard plane is not an adequate contact-Z model unless measurement proves it is.
9. Validate held-out keys across the full keyboard; do not validate only the anchors used to fit the map.

### 8.6 Phone body, screen plane, and UI map

1. Freeze the exact phone, case, orientation, screen protector, display resolution/scaling, navigation mode, keyboard application/version, and cable state.
2. Complete the existing phone pose and no-go clearance gates.
3. Detect or teach four physical active-screen corners and measure the screen plane/normal.
4. Fit a homography from logical display pixels `U` to the physical screen plane `S`.
5. Validate using a phone-hosted test page/app that displays targets at held-out logical coordinates, records the actual physical touch-event coordinates, and reports the target/event pair to the independent verifier.
6. Define named UI targets as polygons in logical pixels, not as arm coordinates.
7. For soft-keyboard typing, define separate maps/states for lowercase, shifted uppercase, symbols page 1, symbols page 2, language/layout, and orientation.
8. Re-detect screen/UI state before each batch and after every state-changing tap.

ADB may be used as a read-only source of screenshots, display metadata, or UI state during development and verification. Acceptance input must still be produced by physical taps; the verifier must not call an ADB input command.

## 9. Static-overhead observation and optional tool correction

Because the arm's published repeatability is comparable to small phone targets,
a nominal board-to-base transform alone is insufficient. The overhead camera
must freshly re-observe the board, selected device, and support witness before
each autonomous descent. A top-visible tool marker is added only if the measured
endpoint error budget requires closed-loop hover correction.

The pre-contact correction loop will be:

1. Move to the route's conservative, prequalified clear observation posture
   using the last accepted `Wv_T_B` and separately qualified controller bridge.
2. Wait for arm settlement, flush a bounded number of camera frames, and capture
   a uniquely fresh image with exact settings and support-witness evidence.
3. Detect all six tags, solve `C_overhead_optical_T_B` from T0-T3, and validate
   K0/P0, device presence, residuals, covariance, focus/exposure, blur, glare,
   and freshness.
4. Compose the result with `Wv_T_C_overhead_optical`, device/target maps, and
   the controller bridge. If selected, observe `C_overhead_optical_T_M` in the
   same frame and use calibrated `M_T_T` to estimate hover TCP error.
5. If the bounded error is inside the approved hover tolerance, continue.
6. Otherwise command one bounded XY correction above the clearance plane, settle, and observe again.
7. Abort if observability is weak, a required feature is missing, synchronization is stale, correction grows, the iteration limit is reached, or the requested correction exceeds the approved bound.
8. After convergence, descend only along the measured device normal using the
   qualified TCP/compliance/contact model.
9. Do not make lateral corrections below the approved contact-clearance plane.
10. Retract to a clear posture, reacquire a fresh overhead observation, and
    verify the key/tap effect through the independent host or Android observer.

A tool marker is not a replacement for board tags, controller correlation, or
TCP/compliance calibration. The board and marker must be visible together; a
disagreement, occlusion, stale frame, or missing support witness blocks descent.
The optional arm camera may not be substituted automatically.

The iteration limit, confidence threshold, maximum correction, and convergence bound will be derived from characterization and committed to the relevant profile. A reasonable development objective is convergence within three iterations, but it is not a released limit until measured.

## 10. RoArm control layer

### 10.1 Primary transport

Use the ESP32 USB serial port, not the LiDAR Type-C port:

- 115200 baud;
- newline-terminated JSON;
- one serialized command owner;
- RTS/DTR disabled unless installed-unit characterization proves otherwise;
- transmit LF and accept LF or CRLF while retaining exact raw messages and unknown fields;
- a dedicated receiver/parser;
- monotonic timestamps;
- explicit timeouts and stale-feedback detection; and
- full raw message logging with sensitive-data controls.

HTTP is bench/control diagnostics only and is never an ARMED runtime fallback. The current official Python SDK treats HTTP as control-only and cannot provide the feedback needed for this work. While our process owns the arm, Web UI, ESP-NOW, HTTP, and other command writers are prohibited.

### 10.2 Commands required

| Command | Use |
| --- | --- |
| T=105/T=1051 | Documented raw feedback snapshot; retain reported XYZ/posture/joints/load/torque/voltage fields and unknown fields, then qualify the exact reply schema against installed firmware |
| T=104 | Interpolated/curve-controlled Cartesian target with opaque firmware `spd` coefficient; sole candidate primitive for characterized segments |
| T=1041 | Non-interpolated direct target at fastest behavior; prohibited for contact and disabled by default |
| T=101/102 | Joint-radian positioning for explicit empty-cell characterization; not homing/reference commands |
| T=121/122 | Degree-based joint controls; avoid internally unless needed for diagnostics |
| T=210 | Torque enable/release for controlled setup; not an emergency stop |
| T=123 | Continuous-jog mode/stop when that mode is active; not a general emergency stop |

### 10.3 Why not use `roarm-sdk.pose_ctrl` directly

The current official SDK is useful as a reference and diagnostic dependency, but its `pose_ctrl` maps to raw T=1041 and exposes no speed argument. That behavior is inappropriate as the only primitive for gentle keyboard/phone contact. Its high-level feedback path also discards raw load fields. Our adapter will therefore implement the documented JSON protocol directly, preserve complete raw replies and unknown fields, and expose typed millimetre/radian methods.

`spd` is a dimensionless controller curve coefficient, not TCP mm/s and not acceleration. The RC03 mm/s and mm/s² fields must be populated from measured trajectories for the installed arm; no fixed coefficient-to-speed conversion is assumed. A blocking controller command is also not treated as proof of physical motion completion until feedback/settling behavior is characterized.

The official SDK is AGPL-3.0 licensed. Before shipping or redistributing software, make an explicit license/dependency decision. A clean protocol adapter based on the public command specification keeps that decision isolated.

### 10.4 Driver acceptance

- Golden encode/decode tests for every supported message.
- COM-port disconnect/reconnect and malformed-line tests.
- Unit-conversion tests at SDK/raw/ROS boundaries.
- Timeout behavior for a blocked or non-responsive controller.
- Recorded replay tests without attached hardware.
- Hardware loop tests with the contact tool and devices removed.
- No contact command can be sent through the unbounded T=1041 API.

## 11. Motion model and safety supervisor

### 11.1 Standard action primitive

Every press/tap uses the same semantic phases:

```text
PARK
  -> TRANSIT at approved safe Z through a known corridor
  -> HOVER directly over target
  -> VISION CORRECT while still above clearance plane
  -> APPROACH along device normal at approved first-contact speed
  -> CONTACT within approved force/travel/time envelope
  -> RETRACT along the same normal
  -> TRANSIT or PARK
```

No lateral move is permitted below the profile's clearance plane.

### 11.2 Keepouts

The planner shall model at minimum:

- board perimeter and bench;
- robot base/clamp and reinforcement;
- keyboard station walls/clamps and keyboard body;
- phone station towers, cable, camera/button no-go regions, and phone body;
- TCP station/cartridge;
- static gantry/posts/crossbar, camera, lighting, and fixed cable; plus the
  optional arm-camera holder and moving cable only if Phase 2 is selected;
- tags as no-contact surfaces;
- complete possible power-on sweep, commissioned reference path, and safe-park path; and
- route-specific tool dimensions and compliance envelope.

Keepouts shall come from versioned configuration derived from RC03 geometry and physical measurement. They are not informal comments in code.

### 11.3 Safety states

```text
POWER_OFF
  -> CONNECTED
  -> REFERENCED
  -> LOCALIZED
  -> CALIBRATED
  -> DRY_RUN_READY
  -> ARMED
  -> EXECUTING
  -> COMPLETE

Any state -> FAULT -> POWER_OFF / controlled recovery
```

Entering `ARMED` requires all applicable checks to pass in one preflight transaction. A process restart returns to a non-armed state.

### 11.4 Mandatory preflight

- Physical power-cut E-stop installed, reachable, tested, and reset deliberately.
- Board mechanically prevented from sliding relative to the bench.
- Complete possible power-on swept volume clear before powering the arm; power application itself is treated as a motion event.
- Correct arm/controller/firmware and serial port identified.
- `power_on_middle`, `commissioned_reference_ready`, and `safe_park` are distinct recorded states; no SDK initialization call is sent automatically.
- Correct tool route and marker identified; gripper/tool seating checked.
- Camera live with locked commissioned settings.
- Current board pose and held-out residual checks pass.
- Calibration artifacts are current and hashes match.
- Device profile matches observed device/station state.
- Planned targets are supported and pass the safe-region error budget.
- Planned path passes keepout/clearance checks.
- Contact limits are approved and not operator-invented.
- Inline contact sensing is zeroed and healthy; the local overforce/interlock self-test and passive travel stop pass.
- The tested gravity-safe unpowered envelope is clear, or its passive catch/support is installed.
- Human explicitly arms the run; no one is inside the motion envelope.

### 11.5 Faults that stop the run

- E-stop or power/interlock state change;
- serial disconnect, malformed feedback burst, stale feedback, voltage fault, or motion timeout;
- camera frame timeout, changed resolution/settings, board-pose failure, or excess residual;
- missing/low-confidence or poorly distributed fiducial/device feature, stale
  or duplicate frame, changed camera settings, failed support witness, or
  missing conditional tool marker during a required check;
- target correction outside the approved bound or non-convergence;
- unexpected device/station pose;
- force-sensor fault/drift, local overforce/interlock trip, unexpected load trend used as a secondary heuristic, contact-travel violation, or failure to retract;
- verifier observes the wrong result beyond the allowed recovery policy; or
- any profile/hash mismatch.

Software soft-stop and torque release are best-effort recovery tools. They do not replace cutting actuator power, and cutting power is not safe by itself unless the gravity-collapse test and passive containment gate pass.

## 12. Keyboard typing design

### 12.1 Keyboard profile

Each supported keyboard gets a versioned profile containing:

- manufacturer/model/serial or asset ID;
- ANSI/ISO/JIS and operating-system layout;
- physical outline and board/device transform;
- key name, legend, logical meaning, polygon, center, row, and key size;
- measured press plane, travel, hover, contact, dwell, and retract parameters;
- safe region after error-budget erosion;
- approach direction and any per-key empirical residual correction;
- supported/disabled status and acceptance evidence; and
- invalidation dependencies.

### 12.2 Text compiler

The compiler converts requested text into semantic key actions before motion:

- normalize line endings and reject unsupported Unicode explicitly;
- map characters through the selected OS keyboard layout;
- group mode changes to reduce Caps Lock/Shift state churn;
- represent Backspace, Enter, Tab, arrows, and navigation keys explicitly;
- plan recovery without silently duplicating characters; and
- display the exact compiled action sequence for dry-run review.

### 12.3 One-tip modifier strategy

A single arm/tip cannot physically hold Shift while pressing a second key. The first release will use one of these documented operating modes:

1. OS Sticky Keys, allowing sequential modifier then key;
2. Caps Lock for uppercase runs, with Sticky Keys for shifted punctuation; or
3. a restricted no-chord character set.

The chosen mode is part of the keyboard profile and verifier state. Native simultaneous chords are unsupported until a two-contact tool or second actuator is designed and validated.

### 12.4 Keyboard verification

Use a controlled desktop acceptance application that:

- owns a text field and records actual HID-delivered key events/text;
- exposes expected versus observed text to the verifier;
- never injects the expected input itself;
- handles Caps Lock/Sticky Keys state explicitly; and
- records key-down/key-up timing and duplicate/missed actions.

The first MVP string is lowercase text using large central alpha keys and Space. Coverage expands only after per-key qualification.

## 13. Phone tapping and typing design

### 13.1 Phone profile

Each supported phone state gets a versioned profile containing:

- phone model, case, protector, orientation, and physical asset ID;
- screen pixel resolution, scaling, rotation, navigation mode, and active-area corners;
- `B_T_P`, `B_T_S`, screen homography, plane normal, and residuals;
- keyboard application/version/language/layout and UI-state templates;
- named target polygons in logical pixels;
- physical safe polygons after mapping and error erosion;
- stylus identity, tested conductivity, hover/contact/retract parameters;
- button, camera, cable, bezel, and clamp no-go regions; and
- acceptance evidence and invalidation dependencies.

### 13.2 Progressive phone capability

Phone capability will be released in this order:

1. one large test-app button;
2. a grid of large fixed targets spanning the screen;
3. a fixed numeric keypad;
4. a controlled test-app QWERTY with enlarged keys if needed;
5. the selected stock phone keyboard in a known state; and
6. selected real application workflows with explicit UI-state verification.

### 13.3 Phone UI state machine

The compiler must model UI state rather than assuming a static coordinate map:

```text
APP_READY
  -> TEXT_FIELD_FOCUSED
  -> KEYBOARD_LOWER
  -> KEYBOARD_SHIFTED / SYMBOLS_1 / SYMBOLS_2
  -> TEXT_UPDATED
  -> optional SEND target
```

After any state-changing tap, verify the new state before continuing. If the screen scrolls, rotates, opens a dialog, hides the keyboard, or changes layout, stop and re-localize; do not continue with stale coordinates.

### 13.4 Capacitive stylus gate

Before robot use, prove by hand in the final phone/case/protector state that:

- the stylus reliably registers a tap across the screen;
- the conductive path/capacitance is adequate without unsafe grounding;
- the tip does not scratch, drag, or leave residue;
- the compliant travel/force window is repeatable; and
- a mechanical or passive limit prevents damaging overtravel.

### 13.5 Phone verification

Preferred verification order:

1. read-only ADB screenshot/UI metadata where available;
2. the primary overhead image only through a separately implemented and
   qualified result observer, or another independently calibrated close-up
   camera, using template detection or OCR;
3. a controlled browser page/test app that displays target markers and received text, captures real `touchstart`/pointer coordinates, and reports those events to the verifier; and
4. manual confirmation only for early commissioning.

The action path and verification path must remain separate so a software input command cannot make a failed physical tap appear successful.

## 14. User command and internal action model

### 14.1 CLI boundary

Implemented now, with no live-motion command:

```text
rocell status
rocell bootstrap-sim
rocell doctor --mode sim
rocell camera-profile
rocell rehearse-camera-commissioning
rocell rehearse-b0477-uvc-inventory --require-pass
rocell rehearse-b0477-intrinsics
rocell rehearse-b0477-stack --require-pass
rocell rehearse-b0477-stack --skip-pixel-vision --require-pass  # fast core-only loop
rocell simulate-b0477-vision --mode normal|tag-loss --require-expected
rocell rehearse-first-power-on --scenario nominal --require-expected
rocell plan --device keyboard|phone --text "test"
rocell dry-run --device keyboard|phone --text "test"
rocell simulate --device keyboard|phone --text "test"
rocell sweep-targets --device keyboard|phone --phase contact
rocell optimize-layout
rocell optimize-park
rocell simulate-trajectory --device keyboard|phone --text "a" --use-optimized-park
rocell simulate-session --device keyboard|phone --text "test" [--record]
rocell simulate-adaptive-session --device keyboard|phone --text "a" [--truth-offset-x-mm <synthetic-mm>] --require-pass
rocell qualify-prehardware --profile quick|standard [--require-pass]
rocell replay-session --manifest <virtual-run>/manifest.json --require-identical
rocell study-layout-hypotheses
rocell screen-mission-routes [--from-layout-study-rank 1]
rocell collision-status
rocell calibration-status --device keyboard|phone
rocell solve-eye-on-arm-offline --dataset <path> --expected-sha256 <sha256>
rocell verify-eye-on-arm-fk-offline <exact-file arguments>
rocell verify-eye-on-arm-capture-bundle-offline <exact-file arguments>
rocell arm-feedback --port <explicit-port>   # capability-gated and currently denied
```

Every implemented planning/calibration/virtual-execution command is read-only
with respect to physical hardware and emits zero physical authority. Virtual
joint commands exist only inside the token-bound plant and cannot encode T=104.
Mission, collision, session, and replay strict flags only turn diagnostic gaps
or divergence into nonzero process exits; they cannot unlock power, motion, or
contact.

Later commands remain gated roadmap items:

```text
rocell calibrate camera
rocell calibrate board
rocell calibrate arm-board
rocell calibrate tool --route keyboard
rocell calibrate tool --route phone
rocell calibrate keyboard --profile <name>
rocell calibrate phone --profile <name>
rocell type --device keyboard --text "test"
rocell type --device phone --text "test"
rocell tap --device phone --target send
rocell park
rocell soft-stop
```

`soft-stop` will be documented as best effort and never presented as the emergency stop.

### 14.2 Internal action plan

The compiler emits semantic actions, not raw coordinates. Example:

```json
{
  "schema": "rocell.action_plan.v1",
  "device_profile": "keyboard/example-us-ansi-v1",
  "requested_text_sha256": "...",
  "actions": [
    {"type": "press_key", "key": "H"},
    {"type": "press_key", "key": "E"},
    {"type": "press_key", "key": "L"}
  ],
  "required_calibrations": [
    "camera_intrinsics",
    "measured_tag_map",
    "board_to_arm",
    "keyboard_pose",
    "keyboard_tcp"
  ]
}
```

Raw arm poses are generated only after preflight and are not accepted from the normal user-facing typing interface.

## 15. Planned software repository layout

The runtime lives outside the checksum-controlled RC03 hardware directory and consumes RC03 artifacts read-only. The following tree is the target architecture; the first safe subset is implemented and later modules remain gated work.

```text
software/
  pyproject.toml
  README.md
  src/rocell/
    cli.py
    application/
      bootstrap.py
      board_registration.py
      context.py
      simulate.py
      target_sweep.py
      reach_optimizer.py
      park_optimizer.py
      trajectory_simulation.py
      prehardware_layout_study.py
      mission_route_coverage.py
      collision_readiness.py
      calibration_status.py
      virtual_calibrations.py
      virtual_session.py
    models/
      units.py
      frames.py
      actions.py
      profiles.py
    rc03/
      importer.py
      integrity.py
      build_snapshot.py
    arm/
      protocol.py
      serial_transport.py
      roarm_m3.py
      feedback.py
      replay.py
    sensors/
      contact_force.py
      interlock.py
      replay.py
    geometry/
      transforms.py
      urdf.py
      planes.py
      polygons.py
      uncertainty.py
    kinematics/
      ik.py
    simulation/
      profile.py
      scene.py
      camera.py
      controller.py
      collision.py
      virtual_profile.py
      virtual_workcell.py
    targets/
      nominal.py
    calibration/
      registry.py
      static_eye_to_hand.py
      robot_world_hand_eye.py  # optional Phase 2
      arm_board.py
      tcp.py
      keyboard.py
      phone.py
    vision/
      camera.py
      usb_opencv.py
      esp_http.py
      mock_camera.py
      undistort.py
      static_board_measurement.py
      frame_joint_sync.py  # optional Phase 2
      board_pose.py
      tool_witness.py
      device_presence.py
      phone_screen.py
      ui_state.py
    motion/
      dry_run.py
      geometric_sim.py
      keepouts.py
      planner.py
      primitives.py
      executor.py
    safety/
      state_machine.py
      preflight.py
      watchdog.py
      faults.py
      contact_guard.py
    devices/
      keyboard.py
      phone.py
    typing/
      keyboard_compiler.py
      phone_compiler.py
      unicode_support.py
    verification/
      desktop_harness.py
      android_observer.py
      vision_observer.py
    evidence/
      virtual_session.py
      metrics.py
  config/
    camera_architecture_plan.json
    system_manifest.json
    simulation_hardware_profile.json
    simulation_bundle_lock.json
    virtual_commissioning_profile.json
    nominal_target_profiles.json
    arm_frame_contract.json
    camera_manifest.json
    gate_projection.json
    runtime.json
    invalidation_matrix.json
    contact_guard_manifest.json
    gravity_safe_stop_manifest.json
    keepouts.json
    keyboard_profiles/
    phone_profiles/
    contact_profiles/
  calibrations/
    README.md
    registry.json
  models/
    roarm_m3/
      README.md
      roarm_m3_kinematic_40dbd84.urdf
  tests/
    unit/
    recorded/
    integration/
    hardware_in_loop/
  tools/
    simulator.py
    record_serial.py
    replay_session.py
    validate_build_alignment.py
  firmware/
    contact_guard/
      README.md
  runs/
    README.md
```

### 15.1 Implementation conventions

- Python 3.10 for the MVP, matching the existing controlled vision workflow.
- One isolated environment for the runtime, with locked dependencies and hashes.
- JSON for controlled configuration/artifacts, with JSON Schema or strict Pydantic validation.
- NumPy/OpenCV for transforms and vision; pyserial for the transport.
- Pytest for unit, recorded-data, integration, and hardware-in-loop suites.
- No import-time connection to hardware.
- Dependency injection for camera/arm/verifier so recorded replay and simulation use the same planner.
- All persisted artifacts are atomic writes with schema/revision/hash metadata.

## 16. Evidence, observability, and privacy

Every run shall have a unique session ID and manifest containing:

- date/time, operator, host, software revision, Python/dependency lock hash;
- RC03 revision and workcell-layout/tag-map hashes;
- arm model/variant, controller firmware, serial identity, voltage, warm-up state;
- camera identity/settings and calibration hash;
- station/device/tool/profile/calibration IDs;
- approved motion/contact limits ID;
- requested command or a redacted/hash-only representation;
- per-action planned target, transforms used, uncertainty bound, raw feedback, observed hover error, corrections, contact/retract result, and verification result;
- all faults/retries and the explicit recovery decision; and
- final state and metrics.

Phone screenshots and typed text may contain sensitive information. Default to the minimum evidence needed, support hash/redaction modes, and require explicit opt-in for retaining full screenshots or plaintext outside controlled test content.

## 17. Implementation phases and gates

### Phase 0 — Digital freeze and physical-identity qualification

**Frozen now**

- RC03-INT-R1, RoArm-M3 Pro, Perixx PERIBOARD-409, and bare Samsung Galaxy A16 5G.
- Both tool routes and the 2026-09-05 static-overhead-primary architectural
  direction. Freeze 009's older camera route values remain immutable until the
  superseding freeze regenerates them.
- USB serial/115200/newline JSON, mm/rad internal units, T=104 candidate, T=1041 contact prohibition, and no HTTP runtime fallback.
- Static eye-to-hand registration using the existing board tags, an independent
  robot/base correlation method, and held-out puck/datum validation; no informal
  board holes.
- [`BUILD_ALIGNMENT_FREEZE.md`](BUILD_ALIGNMENT_FREEZE.md) and [`software/config/system_manifest.json`](software/config/system_manifest.json).

**Work**

- Continue active build `2026-09-01_CELL-A` through Step 00 and bind every evidence artifact to that identity.
- Record the exact M3-Pro serial/controller/USB/firmware/persistent configuration without flashing, neutral calibration, or other persistent writes.
- Measure and qualify the exact PERIBOARD-409; select its regional/OS layout.
- Measure and qualify the bare Galaxy A16 5G; select orientation, keyboard app, and display settings. Any later case/protector is a controlled change.
- Promote `camera_architecture_plan.json` through controlled change: identify
  exact static camera, sensor, lens, native mode/settings, support topology,
  height/aim, camera interface, lighting, fixed cable route, support witness,
  swept-volume clearance, and `Wv_T_C_overhead_optical` method.
- Select physical E-stop/power isolation and bench anti-shift hardware.
- Create the controlled RC03 addendum for static-camera integration, support
  collision geometry, calibration target/datum process, any conditional tool
  marker, contact guard/passive stop, and gravity-safe power-loss support.
- Select sensor range only after the responsible engineering force/travel envelope is approved.
- Use Section 4.2 Method A as the Phase 1 baseline: distributed controlled
  datums plus the existing puck as a held-out check. Retain Method B's
  robot-held-target solve as the alternative if observability or held-out
  residual evidence makes it preferable.
- Define controlled test text with no sensitive data.

**Deliverables**

- Frozen `software/config/system_manifest.json` and passing alignment validator.
- Immutable RC03 build-snapshot projection bound to active build `2026-09-01_CELL-A`.
- Calibration-datum design decision record.
- Static-support/camera/cable/lighting collision, rigidity/drift,
  pixel/FOV/height, pose-observability, occlusion, and freshness calculation/mock
  setup.
- Contact-sensing/interlock and gravity-collapse design decision records.
- Updated hardware change list, if any.

**Exit gate**

- Digital freeze hashes align; an active build exists; the static-camera
  architecture addendum is controlled; exact unit/device/camera/lens/support/
  lighting/cable identities are recorded; and no unresolved decision can move a
  board hole, tag, station, arm, camera, calibration target, tool stack, guard,
  or gravity-support geometry.

### Phase 1 — Complete RC03 physical build gates in parallel

**Work**

- Follow Step 00 and Jobs 00A-00F before production prints.
- Measure exact devices/hardware and regenerate controlled geometry if required.
- Build/qualify stations, tags, the formally released overhead support/camera/
  cable/lighting route, tools, and TCP pucks.
- Install E-stop, reinforcement, and anti-shift measures under RC03. Install the
  overhead support/camera, conditional tool marker, contact guard, or
  gravity-support hardware only after the applicable controlled addendum/
  revision and new gates are released.
- Complete station/device repeatability and structural proof.

**Deliverables**

- Updated controlled RC03 measurement/evidence records.
- PASS measured tag map and physical station/tool evidence.

**Exit gate**

- All prerequisites for camera/empty-cell commissioning are PASS. Device contact remains blocked.

### Phase 2 — Software skeleton, schemas, simulator, and RC03 importer

**Implemented beginning in Freeze 004, historically synchronized under Freeze 005, and retained under active Freeze 011 (software-only; physical release unchanged)**

- Installable package layout, typed units/frames/actions, immutable RC03 import, capability projection, strict protocol/replay boundaries, safety preflight, semantic compilers, and deterministic fixtures.
- Typed rigid transforms, strict parsing of a local kinematic projection pinned to the official Waveshare ROS Xacro, and forward kinematics.
- Nominal RC03 scene import with board, station, device, and tag proxies plus AABB tool-tip point/segment clearance checks.
- Deterministic fixed-overview grayscale JPEG rendering from released tag
  artwork, independent bounded tag36h11 pixel decoding, typed canonical
  detections, and standard-library planar board-pose estimator v1.1 with
  explicit tag-plane-height correction, monotonic consensus refinement, and
  zero physical authority.
- Synthetic nominal keyboard/phone target maps, deterministic vertical motion phases, and numerical IK.
- Exhaustive target/phase/tool screening with required park evidence and a
  bounded placement study that derives `B_T_Wv` from a physical
  `B_T_base_link` hypothesis through the pinned URDF offset. Placement results
  are diagnostic overlays and never modify the frozen placemat scenario.
- A historically Freeze-005-bound geometry-derived coarse/fine park-pose optimizer that
  screens board/keepout/tag clearance and independent IK for both selected
  route tools, with hard resource caps and no canonical geometry mutation.
- A strict, immutable optional Phase 2 eye-on-arm dataset and lazy numerical
  `Wv_T_B = Wv_T_E * E_T_Carm * C_arm_T_B` solver with precommitted held-out
  samples, observability/conditioning gates, residual classification, resource
  limits, deterministic report hashes, and `NOMINAL_ONLY` output.
- A complete nominal route diagnostic that enforces ordered
  park/transit/hover/approach/contact/retract endpoints, bounded Cartesian
  densification, previous-solution-first sequential IK, controller/URDF joint
  intersections, arm-joint margins, adjacent sampled-joint deltas, resource
  caps, and explicit unsupported physical proofs. Schema v2 additionally
  rejects numerical rank loss in the solver-weighted five-constraint task
  Jacobian and records normalized conditioning without treating it as physical
  singularity acceptance.
- Raw-feedback eye-on-arm evidence that recomputes every dataset `Wv_T_E` from
  exact content-hashed T=1051 fields, explicit joint-reference rules,
  measured `link2_T_E`, and the reviewed pinned URDF, plus a commissioning
  assessment that remains evidence-gate blocked.
- A strict offline capture bundle that preserves exact pre/post T=1051 wire
  lines, JPEG bytes/metadata, normalized detections, and declared
  pre/exposure/post brackets under bounded parsing and exact-file hash pins;
  structural pass has no physical timing or commissioning authority.
- One exact-byte bounded pinned-URDF loader across simulation, target sweep,
  reach, park, and trajectory services, with the parsed-byte digest and byte
  count retained in report provenance.
- A per-physical-action `HOVER` vision gate that processes only capture
  sequence/mode, associates the plan afterward, rejects capture/tag/pose/quality
  faults without retry, and blocks approach/contact unless the synthetic
  fixed-overview policy passes.
- A provider-neutral, bounded UVC inventory interface plus deterministic fake
  provider that rehearses persistent selection, exact native USB3/YUY2 mode,
  manual controls, and two-reopen stability without device access.
- A sealed 32-view synthetic ChArUco intrinsics contract with a precommitted
  24-training/8-held-out split, source/target/solution/map hashes, UVC identity
  and settings bindings, held-out residual gates, and permanent zero physical-
  calibration authority.
- An application-level B0477 coherence assessor that rejects disagreement
  across profile, source locks, support geometry, commissioning, UVC identity,
  mode/settings, intrinsics, authority, and the optional paired normal/tag-loss
  pixel reports. The default CLI runs the pair; its latest full run passes 10/10
  synthetic checks with no camera, arm, or contact access.
- An additive semantic execution schedule that preserves distinct semantic,
  contact-occurrence, route-waypoint, and authorization-command ordinals, with
  `VerifyPhoneState` retained as observation-only work.
- A strict non-wire T=104-shaped runtime plus dense-route adapter that bind one
  emulator target to every accepted waypoint after the known initial park,
  check pose/route/joint/hash continuity, and latch deterministic stall, reset,
  disconnect, timeout, and non-settling faults without importing a transport or
  constructing a wire command.
- A dense static-B0477 mission collision adapter that checks every accepted
  endpoint and every incoming exact 0.5 joint midpoint against the 26-body,
  nine-source contract. Its current complete fixture deliberately isolates
  unknown geometry and permanently denies physical-clearance evidence.
- An additive mission V2 assembler and executable zero-hardware coordinator
  that join per-contact final-HOVER B0477 evidence, collision results,
  `NOMINAL_ONLY` calibration projection, ordered authorization-v2, crash-safe
  journals, non-wire controller feedback, geometry-resolved virtual contact,
  independent outcome observation, retraction, and final park. V1 remains
  unchanged and no physical provider is exposed.
- Session report schema v3 and manifest schema v2 with a separately hashed,
  redacted `vision.json` ledger, strict typed reconstruction, and full
  planner/vision/executor recomputation. Legacy report-v2/manifest-v1 packages
  remain byte-verifiable history but do not contain pixel-vision evidence.

**Remaining work**

- Resolve exact static support/camera geometry and
  `Wv_T_C_overhead_optical`; correlate the controller Cartesian frame with the
  URDF model independently.
- Replace coarse point/AABB screening and the V2 isolated binding fixture with
  measured, accepted link, tool, gantry, camera, lighting, fixture, harness,
  and fixed-cable collision geometry plus the required continuous or
  conservatively swept-volume method.
- Implement and qualify a real OS UVC inventory/capture provider, then replace
  the fake identity, modes, controls, and reopen observations with evidence from
  the received camera. Add calibrated physical-camera/recorded-image replay,
  measured distortion/undistortion, bounded buffer flushing, support-witness,
  occlusion, glare, and freshness fault campaigns. The current inventory,
  ChArUco, fixed-overview pixel faults, thresholds, and reproducible reports are
  synthetic only; physical acceptance criteria must be reviewed separately.
- Add registry-resolved camera/support/artifact identities, original tag
  corners/inliers/covariance/detector logs, physical quality gates that never
  use simulator truth, and a qualified static eye-to-hand validation boundary.
- Retain raw `Wv_T_E`, `E_T_Carm`, frame/joint timing, and the structural
  capture-bundle work as optional Phase 2 research only; it does not satisfy the
  Phase 1 primary-camera gate.
- Add measured target profiles and a typed calibration promotion boundary
  without granting numerical candidates any live authority.

**Deliverables**

- Installable `rocell` package.
- `rocell doctor` in simulation mode and `rocell simulate --device ... --text ... --json` deterministic reporting.
- `rocell sweep-targets`, `rocell optimize-layout`, `rocell optimize-park`,
  `rocell simulate-trajectory`, `rocell solve-eye-on-arm-offline`,
  `rocell verify-eye-on-arm-fk-offline`, and
  `rocell verify-eye-on-arm-capture-bundle-offline` zero-authority diagnostic
  reporting.
- `rocell simulate-session` report-v3/manifest-v2 recording and
  `rocell replay-session` full artifact recomputation, including `vision.json`.
- Additive library-level dense mission V2 assembly/execution with exact
  semantic/contact/route/authorization joins, source-revalidated trajectory,
  mandatory state-observation ordering, stateful per-contact B0477 evidence,
  endpoint/midpoint collision binding, non-wire controller emulation, journal
  fault/restart handling, structured fault frontiers, full receipt replay,
  outcome verification, and final park.
- `rocell simulate-integrated-v2` operator entry point with a mandatory new
  persistent journal root for initial execution and fail-closed
  `--open-existing` behavior that refuses automatic retry after progression;
  deterministic controller and assembly-bound camera fault schedules are
  available for expected-failure rehearsal.
- Unit tests for transforms, frame mismatch, profiles, action compilation,
  scene clearance, raster/tag/pose vision, typed vision deserialization,
  session/evidence replay, FK, and IK.

**Exit gate**

- Text compiles to semantic actions and a simulated geometric/kinematic run without raw coordinate leakage or hardware access. Every report states that it is simulation-only and generated zero hardware commands.

### Phase 3 — Serial driver and no-contact arm characterization

**Work**

- Implement newline JSON transport and an installed-firmware-qualified raw T=105/T=1051 parser that preserves unknown fields.
- Implement bounded T=104 movement and diagnostic joint methods.
- Add recorded serial replay and fault injection.
- Characterize power-on middle motion, commissioned reference procedure, safe park, workspace, feedback rate/schema, T=104 completion/settling semantics, `spd`-to-measured-motion response, timeout behavior, voltage/load fields, and controller recovery as distinct items.
- Keep devices and contact tool removed during initial movement.

**Deliverables**

- Arm protocol/transport test report.
- Recorded sessions for automated replay tests.
- Safe startup/reference procedure bound by hash.

**Exit gate**

- Repeatable no-contact moves and feedback are understood; no unbounded contact API is reachable.

### Phase 4 — Static camera, repeatability, and feasibility characterization

**Work**

- Install the accepted overhead support, camera, fixed cable/lighting, and
  lightweight tool, but no devices.
- Warm the arm using a fixed procedure.
- Test a grid spanning keyboard and phone workspaces at multiple Z values.
- Use at least 30 repetitions per representative point with fixed load and consistent approach direction; also test reverse/alternate directions to quantify backlash.
- Measure open-loop error and, if selected, overhead tool-marker-corrected
  error: P50/P95/P99/max, camera/support drift, image freshness, arm/tool
  occlusion, settling, cable/support disturbance, and dependence on reach,
  temperature, load, and approach direction.
- Populate the first real error budget.

**Deliverables**

- Arm characterization dataset/report.
- Go/no-go matrix for keyboard, large-phone, keypad, and phone-QWERTY target sizes.

**Exit gate**

- At least keyboard-size targets have a credible path to passing. Phone-QWERTY is either provisionally feasible with correction or explicitly deferred.

### Phase 5 — Productionize vision and measured board localization

**Work**

- Harden camera capture/settings verification.
- Complete ChArUco calibration and held-out validation.
- Complete the measured tag map and static-camera board pose.
- Add persistent camera identity/settings readback, distortion correction,
  bounded frame flushing/freshness, multi-frame filtering, confidence/residual/
  covariance thresholds, route visibility, occlusion testing, support witness,
  and drift alarms.
- Add device presence and any conditionally required tool-witness detection.

**Deliverables**

- Versioned camera and measured-board calibration artifacts.
- `rocell calibrate camera`, `rocell calibrate board`, and `rocell status`.
- Recorded image regression suite.

**Exit gate**

- The released static-overhead primary/recovery dataset, RC03 reprojection gate,
  held-out K0/P0 checks, camera identity/settings/freshness, support witness, and
  every required route visibility/observability gate pass.

### Phase 6 — Static eye-to-hand, arm-to-board, and TCP calibration

**Work**

- Implement the selected static `Wv_T_C_overhead_optical` eye-to-hand solve and
  independent controlled datum/board-to-arm validation.
- Calibrate route-specific TCP/compliance relationships and `M_T_T` only if the
  released design requires an overhead-visible tool marker.
- Validate transforms on held-out points across both stations.
- Probe the installed TCP puck repeatedly.
- Calibrate contact-force sensing and validate the local hard-overforce path with traceable reference loads and a non-destructive dummy contact.
- Implement dependency-aware calibration invalidation.

**Deliverables**

- `Wv_T_C_overhead_optical`, live `B_T_Wv`/`Wv_T_B`, the separate `R_ctrl`
  correlation/model-residual artifact, support-witness/drift evidence, tool/TCP
  artifacts, solver observability/residual report, and validation report.
- `rocell calibrate arm-board` and `rocell calibrate tool`.

**Exit gate**

- The complete transform/error budget fits at least the keyboard target safe regions. No device contact yet.

### Phase 7 — Safety supervisor, planner, and empty-cell motion

**Work**

- Implement safety states, preflight, watchdogs, fault taxonomy, and best-effort soft stop.
- Integrate contact-force health/limits and the independent local interlock state without weakening its host-independent action.
- Model keepouts and transit/approach/retract corridors.
- Implement plan rendering and dry-run evidence.
- Execute empty-cell routes above every planned target with devices removed.
- Add one device at a time and repeat non-contact hover validation.

**Deliverables**

- Hashed commissioned-reference, empty-cell, safe-park, and final-process program candidates; the existing RC03 `homing/reference` evidence label does not assert sensor-based homing.
- `rocell plan`, `rocell dry-run`, `rocell park`, and fault/recovery guide.

**Exit gate**

- Existing RC03 `commissioning_motion_contact_limits_approved`, empty-cell, E-stop, anti-shift, and startup-envelope gates pass.
- The controlled contact-guard and gravity-safe power-loss addendum gates pass, and the active-build Step 15 evidence is current. Device contact remains blocked if any is absent.

### Phase 8 — Keyboard MVP and full supported layout

**Work**

- Calibrate the exact keyboard frame/plane/key polygons and per-row/per-key contact-height corrections.
- Start with a lowercase central-key subset and controlled verifier text field.
- Characterize contact height/travel and key release.
- Add Space, Enter, Backspace, then remaining alpha/numeric/punctuation keys.
- Add Caps Lock/Sticky Keys state handling for modifiers.
- Add per-key qualification and error-budget enable/disable flags.

**Deliverables**

- Keyboard profile, compiler, desktop verifier, and acceptance report.
- `rocell type --device keyboard`.

**Exit gate**

- Keyboard acceptance criteria in Section 20 pass with no unsafe contact.

### Phase 9 — Phone large targets, keypad, and conditional QWERTY

**Work**

- Hand-qualify the stylus and calibrate the phone body/screen/homography.
- Implement vision-guided hover correction.
- Demonstrate one large target and a full-screen target grid using the instrumented browser page/test app to record actual touch-event coordinates.
- Add fixed keypad with UI-state verification.
- Measure end-to-end error against actual QWERTY safe polygons.
- Implement QWERTY states only if the bound passes.
- Add read-only ADB and/or visual verification.

**Deliverables**

- Phone profile, phone UI state machine, verifier, and tiered capability report.
- `rocell tap` and the enabled tier of `rocell type --device phone`.

**Exit gate**

- Each advertised phone tier independently passes its acceptance criteria. A failed QWERTY gate does not invalidate safe large-target tapping.

### Phase 10 — Integrated command service and recovery

**Work**

- Complete CLI/API, status display, session records, and operator prompts.
- Add resumable/retry policy that never duplicates uncertain input silently.
- Test wrong device/profile, stale calibration, moved station, missing marker, UI drift, serial loss, camera loss, and E-stop cases.
- Document normal operation and every fault recovery.

**Deliverables**

- End-to-end runtime and operator guide.
- Fault-injection and recovery report.

**Exit gate**

- A new operator can run controlled test text from power-off through verified completion using only the guide.

### Phase 11 — Soak, release, and maintenance

**Work**

- Run keyboard and phone action soaks.
- Repeat after cold start, warm state, device remove/reinstall, tool remove/reinstall, and permitted station service.
- Establish daily preflight, periodic calibration, wear inspection, and change-control intervals.
- Freeze software/calibration/profile versions and hashes.

**Deliverables**

- Release candidate, validation report, known limitations, maintenance schedule, and rollback package.

**Exit gate**

- Definition of done is satisfied and final `workcell_commissioning_pass` is PASS.

## 18. Critical path and parallel work

| Workstream | Can start now | Hardware dependency |
| --- | --- | --- |
| Schemas, units, transforms, compiler, simulator | Yes | None |
| Serial driver against recorded/mocked data | Yes | Arm later for HIL |
| Static-vision/freshness regression around existing helpers | Yes | Final camera/lens/support/height/lighting for production calibration |
| RC03 importer and integrity checks | Yes | None |
| Keyboard generic layout/profile schema | Yes | Exact keyboard for calibration |
| Phone UI/profile schema and test app | Yes | Exact phone for homography/contact |
| Arm repeatability characterization | No | Static-camera addendum/support, accepted tool, E-stop |
| Board-to-arm/TCP calibration | No | Final static camera/support, arm/base, board, tool, target/datums/puck |
| Contact motion | No | All applicable RC03 and safety gates |

Software phases 2-3 should proceed while RC03 Phase 1 is being built. Physical commissioning remains the critical path for real contact.

## 19. Test strategy

### 19.1 Unit tests

- JSON protocol encode/decode and unit conversions.
- Transform direction/composition/inversion and frame mismatch rejection.
- Plane/homography fitting with synthetic noise and outliers.
- Polygon mapping/erosion and target disable rules.
- Keyboard and phone text compilation, modes, unsupported characters, and recovery semantics.
- Calibration dependency invalidation.
- Safety-state transitions and preflight reason codes.

### 19.2 Recorded-data tests

- Real serial logs replayed without hardware.
- ChArUco/tag/tool/device images spanning nominal, blur, glare, occlusion, and failure states.
- Phone UI screenshots for every supported state.
- Golden complete-session replays.

### 19.3 Simulation/dry-run tests

- Workspace and keepout checks for every target.
- Randomized calibration perturbations and stale artifacts.
- Target error-budget boundary cases.
- Fault injection at every action phase.

### 19.4 Hardware-in-loop tests

- Power/startup clear-zone behavior.
- Serial disconnect and camera loss with tool high and during planned motion.
- E-stop at representative non-contact motion phases.
- Repeatability grids, warm/cold drift, and approach-direction/backlash study.
- Tool retention and TCP probe cycles.
- Empty-cell paths, then one-device-at-a-time hover paths.
- Controlled first contacts under approved limits.

## 20. Acceptance criteria

Existing RC03 numeric limits remain authoritative for board/station/tag/tool/commissioning characteristics. The following are software/performance gates and do not authorize contact forces or speeds.

### 20.1 Hardware and vision prerequisites

| Area | Gate |
| --- | --- |
| RC03 physical release | All selected jobs/stations/devices/tool/tag/camera/commissioning prerequisites PASS |
| Tag placement | Existing center/yaw/lift limits PASS; map regenerated from measured installation |
| Tag/route detection | Every ID passes the released acceptance dataset; primary and recovery observations see all six with required distribution and device evidence |
| Vision reprojection | RC03 maximum 1.0 px; tighter operational bound if required by target error budget |
| Static capture integrity | Persistent identity, exact native mode/settings, unique freshness, buffering, latency, and multi-frame stability stay within released bounds |
| Static-camera mechanical integration | Gantry/support rigidity, retention, aim, fixed cable/lighting, witness, drift, swept-volume clearance, collision, and remove/reinstall gates PASS |
| Station repeatability | Existing RC03 X/Y/yaw/Z ranges PASS |
| Tool | Approved force/travel/TCP limits and assembled motion gate PASS |
| E-stop/anti-shift | Physical implementation and functional evidence PASS |

### 20.2 Transform and targeting gates

- Calibration residuals are reported per point and on held-out points across both device regions.
- No target is enabled unless its eroded safe polygon is non-empty under the current conservative error bound.
- Static board/device observation passes before every descent; any optional
  tool-marker hover correction converges within the released iteration and
  correction bounds on every enabled target.
- No lateral correction occurs below the approved clearance plane.
- A calibration change invalidates all dependent profiles before the next motion.

### 20.3 Keyboard development targets

Initial targets to ratify after characterization:

- each enabled key: 20 successful presses out of 20 with clean release and the correct observed key;
- lowercase MVP phrase: 10 exact runs out of 10;
- full supported mixed test suite: 10 exact runs out of 10 with modifier state restored;
- 1,000-action soak: at least 99.5% correct raw actions, zero unsafe/off-key contacts, and all discrepancies classified; and
- no station/device shift beyond its existing RC03 gate.

Release may support a subset of keys; disabled keys must fail at planning time, not during motion.

### 20.4 Phone development targets

Initial targets to ratify after characterization:

- single large target: 100 successful physical taps out of 100;
- distributed large-target grid: 20/20 per target across the active screen;
- fixed keypad: 20/20 per enabled key and 10 exact sequences out of 10;
- stock QWERTY, if enabled: 20/20 per enabled key, at least 99% correct raw taps in a 500-tap soak, 10 exact controlled strings out of 10, and zero bezel/button/camera/clamp contacts; and
- every state-changing tap visually or read-only-ADB verified before dependent taps continue.

If QWERTY fails the geometric error-budget gate, it is not advertised even if occasional strings succeed.

### 20.5 Safety/recovery gates

- Physical E-stop removes actuator power in every tested state.
- No auto-resume after restart, E-stop, serial loss, camera loss, or calibration fault.
- Uncertain key/tap outcome stops for verification; the system never blindly repeats an action that might duplicate input.
- All motion/contact values stay inside the responsible engineering approval recorded in RC03.
- Every fault produces a specific reason code, safe recovery instruction, and evidence entry.

## 21. Principal risks and responses

| Risk | Consequence | Response |
| --- | --- | --- |
| Published ±5 mm repeatability | Adjacent key/tap errors | Characterize; consistent approach/load; optional overhead tool-marker correction; per-target safe polygons; larger UI or hardware upgrade |
| Encoder resolution mistaken for accuracy | Unsafe optimism | Keep encoder and measured Cartesian metrics separate |
| Digital validation mistaken for physical release | Premature printing/motion/contact | Require active build, canonical and build-specific PASS gates, measured map, physical release, and matching hashes |
| Only one TCP puck | Incomplete board-to-arm transform | Static eye-to-hand solve plus independent multi-datum and puck validation, or controlled distributed touch fixture |
| Static camera or support moves | Systematic global target error | Rigid bench/base relationship, witness marks/base reference, live tag checks, drift alarms, and immediate invalidation |
| Gantry/camera/lighting intersects the arm sweep | Collision, calibration loss, or cable damage | Select height from full swept volume first; model every static body and prove clearance before optics release |
| Arm/tool occludes board or device evidence | Correction loss near target | Clear primary/recovery observation postures; observe retracted, contact, retract, reobserve; missing visibility blocks descent |
| Tool marker mistaken for full calibration | False confidence in placement | Use board/device observations for global correction; marker only for calibrated above-clearance TCP refinement |
| Camera lacks phone target resolution | QWERTY localization fails | Height/lens/pixel-budget gate; larger UI, optional qualified local camera, or hardware revision |
| T=1041 fastest direct motion | Damaging contact | Disable for contact; implement explicit T=104 primitive and planner bounds |
| T=104 `spd` mistaken for mm/s | Unsupported motion limits | Type as opaque coefficient and measure actual TCP speed/acceleration on the installed unit |
| Servo loads treated as force | Phone/key damage | Physical compliance, mechanical travel limit, force-gauge calibration; loads only heuristic |
| Power-on automatic motion | Collision/injury | Permanent clear startup envelope and power-on checklist |
| Software stop mistaken for E-stop | Injury/damage | Independent power-cut E-stop |
| Power cut lets the arm fall | Injury/device damage after E-stop | Test unpowered motion; passive safe-collapse envelope, support/catch/counterbalance, and safe park geometry |
| Host-only contact monitoring stalls | Overforce before the PC reacts | Inline sensor, local latched overforce path, passive travel stop, and periodic self-test |
| New marker/guard/catch installed outside RC03 | Stale CAD, keepouts, gates, and evidence | Controlled RC03 addendum/revision before installation; reopen downstream signoffs |
| Phone UI state changes | Wrong tap coordinates | State machine and verification after every transition |
| Single tip cannot chord | Missing uppercase/symbols/shortcuts | Sticky Keys/Caps Lock/restricted set; later multi-tip design |
| Device reinserted differently | Stale target map | Presence/pose check and dependency-aware invalidation |
| Capacitive stylus inconsistent | Missed taps/dragging | Hand qualification, conductive-path test, compliant normal contact |
| Official SDK license/API behavior | Distribution or motion surprises | Isolated adapter, license decision, direct documented protocol |
| Sensitive typed content/screens | Privacy leak | Controlled test text, redacted/hash-only logs, opt-in screenshots |

## 22. Decisions made by this plan

- The RC03 board frame remains the world geometry source of truth.
- RC03-INT-R1 is frozen to the RoArm-M3 Pro, Perixx PERIBOARD-409, and bare Samsung Galaxy A16 5G reference articles.
- Both RC03 tool routes remain selected. The 2026-09-05 change plan selects
  `camera_overhead_primary` as an unqualified Phase 1 route and leaves
  `camera_arm_secondary` unselected; Freeze 009's older
  `camera_mast_optional: false` value remains historical until schema migration.
- New runtime software lives at workspace root under `software/`, outside the controlled RC03 release.
- Python 3.10 and Windows-compatible USB serial are the MVP platform.
- Raw protocol units are normalized to millimetres/radians internally.
- RC03 vision translation is explicitly converted from metres to millimetres at the adapter boundary.
- T=1041 is disabled for contact paths.
- The existing vision helpers are reused and refactored behind tested library interfaces rather than discarded.
- Board pose, arm registration, tool TCP, and device maps are separate calibrations.
- The Phase 1 primary is a rigid static overhead USB/UVC camera in
  `C_overhead_optical`, with a fixed commissioned
  `Wv_T_C_overhead_optical` and a fresh per-frame
  `C_overhead_optical_T_B`.
- The purchased catalog configuration selected for detailed screening is the
  Arducam B0477/IMX283 at full native `5472 x 3648` YUY2 with its included
  nominal 16 mm manual C-mount lens. It is centred
  at `B=(305,228.5)` with nominal entrance-pupil `Z=1000 mm`; the support allows
  `Z=950..1050 mm` during qualification and keeps overhead swept-footprint
  geometry above a provisional `Z=920 mm` floor.
- Pre-delivery UVC work uses a provider-neutral contract and deterministic fake
  provider. The fake VID/PID/serial/path, modes, controls, and reopen evidence
  are explicit test inputs and can never be promoted as observations of the
  received camera.
- Pre-delivery intrinsics work uses a sealed 32-view synthetic ChArUco artifact
  with a 24/8 training/held-out split and UVC identity/settings hash bindings.
  Its thresholds and numeric solution test the artifact boundary only; the
  physical acceptance policy and dataset must be independently precommitted.
- `rehearse-b0477-stack --require-pass` is the preferred complete B0477
  regression because it cross-checks all core artifacts and the normal/tag-loss
  pixel pair. `--skip-pixel-vision` is a fast inner loop, not an equivalent
  milestone result. Neither path grants physical authority.
- `rehearse-first-power-on --scenario nominal --require-expected` joins the
  B0477 and RoArm preparation boundaries into the documented 15-stage order.
  Its terminal status is
  `SIMULATION_WORKFLOW_COMPLETE_PHYSICAL_ONBOARDING_NOT_STARTED`; strict
  checkpoint/resume source-binds implementation and transitive controlled
  inputs, replays every stored prefix record, and rejects divergence. Injected
  regression matrix compares every pre-fault record exactly with nominal, and
  fault reports require their terminal stage/detail/check/count signatures. The
  freshness gate jointly checks synthetic sequence and raw-JPEG identity,
  including a rewrapped-frame fault. The strict received-part boundary parses
  and hashes the modeled article before profile comparison. The selected
  static-overhead calibration rehearsal covers 15 artifacts, 12 requirements
  per device, 27 parent edges, and 41 source edges while keeping the physical
  registry blocked. The noncontact gate records exactly 109 virtual waypoints,
  nine virtual contact attempts/acceptances, and nine observations under a
  shared latest Stage-8 B0477 registration binding while explicitly retaining
  the incomplete physical-collision hold; historical fixed-overview virtual
  pixels still supply each action, so no fresh B0477 frame per contact is
  claimed. Its first-waypoint stall proves no later contact or observation and
  unchanged output. The emulator's two scripted T=105 open/query/close cycles
  exercise framing and bounded exchange accounting without minting
  a live feedback permit. Because T=1051 has no echoed transaction ID, both the
  emulator and live transport reject any bytes already buffered before a new
  request; the stale scenario blocks before a second T=105 write. Qualified
  physical buffering/timing remains open;
  the first physical session remains one bounded T=105 request, and installed
  firmware is read only through a separately approved
  non-motion method. None of these checks updates active Freeze 011 or satisfies a
  physical gate.
- The support candidate uses 1200 mm 4040 upright stock, 800 mm front rails,
  two 400 mm high booms, a 200 mm camera bridge, reversible board-edge
  registration, and positive bench anchoring. Low side rails may not run
  rearward beside the board. Exact cuts, anchors, brackets, camera retention,
  focus, measured optics, lighting, cable, support witness, and collision
  geometry remain open and carry no physical authority.
- The existing paired 2020 mast/700 mm posts/universal plate are unsuitable as
  the default static primary. The prior Waveshare IMX335-B/arm-holder
  combination is retained only as an unselected Phase 2 research input.
- The standalone package does not include camera electronics. The onboard
  ESP32 is the arm controller, not an identified camera; `esp_http_mjpeg`
  remains an optional unselected software adapter.
- A failed overhead camera never automatically falls back to an arm camera.
- Phone QWERTY requires a measured target error-budget PASS and may require a
  top-visible tool marker or separately qualified Phase 2 local camera.
- Verification is independent from actuation.
- ROS2/MoveIt is an optional later adapter, not an MVP dependency.
- No physical contact occurs until the existing responsible-engineering limits are approved and commissioning prerequisites pass.

## 23. Decisions still requiring the builder

These do not block software schema/simulator work, but they block final hardware calibration:

1. Physical M3-Pro identity, controller/firmware/USB identity, persistent configuration, and observed power-on behavior.
2. PERIBOARD-409 physical dimensions, ANSI/ISO/JIS variant, and controlling OS layout.
3. Bare Galaxy A16 5G physical dimensions, screen state, orientation, and phone keyboard application.
4. Physical acceptance of the selected B0477/16 mm detailed-screening
   candidate: received identity, one-metre focus, exact cage interface,
   persistent USB identity, full-native 3:2 mode and controls, measured usable
   FOV/distortion, collision-safe support/height/aim, rigidity/anchoring, fixed
   cable/lighting, support/base witness, optical pixel budget,
   freshness/buffering limits, primary/recovery visibility atlas, and whether a
   top-visible tool marker or optional Phase 2 arm camera is needed.
5. Physical E-stop/power-cut, gravity-safe containment, and board-to-bench anti-shift hardware.
6. Controlled static board-registered calibration target and any conditionally justified route-specific tool-witness design.
7. Controlled force-sensor/local-guard design and passive hard travel stop after force-envelope approval.
8. Whether held-out residuals require a controlled removable distributed-touch fixture.
9. Whether ADB read-only verification is acceptable on the phone.
10. Required character set and whether enabling OS Sticky Keys is acceptable.

Record each selection in the system manifest and calibration evidence; do not leave it only in conversation.

## 24. Immediate work order

The 2026-09-05 static-overhead plan and additive hardware package control all
new camera work. They have planning and simulation authority only. The
user-confirmed B0477 catalog purchase is recorded as
`PURCHASED_PENDING_RECEIPT_INSPECTION`; it does not promote the legacy camera
fields retained in active Freeze 011 or rewrite any archived freeze,
release the old mast, verify or physically qualify the received camera, or
enable power, motion, descent, or contact. The next controlled freeze must
migrate routes, configuration, geometry, instructions, evidence gates,
generated outputs, and checksums atomically.

Freeze 009 historically aligned the software to active build `2026-09-01_CELL-A` after the
append-only Job 00A evidence chain: the seven-source Freeze 005 → 006
lifecycle transition, the five-source Freeze 006 → 007 washer-fit
traceability synchronization, and the seven-source Freeze 007 → 008
operator-waived tray functional-fit transition, followed by the seven-source
Freeze 008 → 009 operator-waived keyboard-locator functional-fit and lifecycle
transition. Freeze 008 moved only `tray_clearance_holes_coupon_pass` to `PASS`,
producing 10 `PASS`, 70 `NOT_TESTED`, and 4 `NA`. Freeze 009 moved only
`keyboard_station_registration_coupon_pass` to `PASS`, retained the selected
6.2 mm round socket, 6.2 mm radial-slot width, and controlled 10.0 mm slot
length, advanced Job 00A to `POSTPRINT_PASS`, and produced 11 `PASS`, 69
`NOT_TESTED`, and 4 `NA`. Freeze 009 → 010 then recorded the camera alignment
hold, two Job 00B failures, and the Job 03C1 rework; Freeze 010 → 011 removed
a workflow self-dependency without changing geometry or authority. Active
Freeze 011 records 15 `PASS`, 63 `NOT_TESTED`, 4 `NA`, and 2 `FAIL`. None of
these transitions released robot power, motion, or contact. Freeze 005 remains the explicitly historical
reach, park, and simulation provenance baseline, and none of the later evidence
freezes re-runs or relabels its results. The implemented base includes the installable
package/CLI, typed units/frames/actions, verified immutable RC03 snapshot
importer, strict T=104/T=105/T=1051 protocol and replay, lazy
permit-consuming serial-feedback boundary, selection-neutral USB/ESP camera
adapters, calibration registry, safety preflight/exact-goal permits, semantic
compilers, and validated hardware-neutral runtime ports for clock,
cancellation, arm lifecycle/execution/feedback, observation, device contact,
outcome observation, and evidence. The serial transport exposes no raw
send/exchange API; a T=105 request consumes one build-gated feedback capability,
and live T=104 remains unconditionally blocked because exact-goal identity is
not evidence of calibrated bounds or checked-plan linkage.

The same boundary now has deterministic VIRTUAL/REPLAY adapters and a bounded
mission-through-ports rehearsal. It validates the bundle before and after the
mission, exercises cancellation/deadline checks, lifecycle, observation,
execution, independently correlated fresh achieved feedback with a nonzero
synthetic tracking deviation, opaque contact, outcome, and evidence, and always
attempts stop/close cleanup. The raw protocol boundary likewise has an
in-memory controller for truncated, overlong, malformed, wrong-type,
partial-write, timeout, disconnect, and reset responses. These are test
adapters, not physical motion implementations or permits.

The additive V2 flow now closes the separate hardware-free assembly gap. It
reconstructs the semantic plan into contact and observation schedules, maps
the accepted dense route to exact non-wire controller targets, associates a
fresh synthetic B0477 report with each contact's final hover, evaluates every
dense endpoint and incoming exact joint midpoint through the static 26-body
contract, projects the full static Phase-1 synthetic calibration closure into
authorization-v2, and executes the resulting sequence with durable journals,
geometry-resolved virtual contact, independent outcome observation, retraction,
and final park. Phone state observations are hard chronological prerequisites,
and retained authorization/T104/contact evidence is deterministically replayed.
Controller faults bind the failed trace; the assembly-bound camera fault
schedule is a global stop frontier, while capture-area faults use a coarse
causal boundary and only unauthenticated nested camera diagnostics. Its complete
collision fixture intentionally isolates unknown
bodies instead of modeling their physical location, and every calibration
artifact remains `NOMINAL_ONLY`. It is therefore an integrated software
rehearsal, not a physical-port implementation or clearance result. Per-contact
journals do not replace a mission-global dispatch ledger, and lower-level
partial-effect receipts remain required before a physical executor can recover
from every controller/contact wrapper boundary while still returning a report.

The simulation foundation captures and hashes exact bounded URDF bytes before
parsing them across its services, adds typed rigid transforms/URDF/FK, a
separately framed `R_ctrl` firmware FK and T=104 cosine-interpolation emulator,
a nominal RC03 scene with AABB tool-tip clearance, synthetic keyboard/phone
target maps, bounded reach and park optimization, full ordered route
densification, sequential IK, the trajectory-schema-v2 solver-task
numerical-rank gate, and retained solver-achieved tip/axis evidence. Its vision
path renders fixed-overview grayscale JPEGs, independently decodes the six
released tag36h11 patterns, creates strict typed detections, and estimates
`camera_overview_optical_T_board` through planar estimator v1.1. Its consensus
refinement is monotonic after unique maximum-support selection: a refit may
remove an inlier but cannot re-admit an excluded tag. A
separate path now projects a synthetic arm-mounted camera from achieved
six-joint FK and recovers a candidate `Wv_T_board` from the same independent
pixel boundary.

A strict bootstrap and sixth locked profile feed an action-indexed virtual
arm/camera/device executor. Every physical-action hover must pass the plan-blind
pixel/pose result before approach; processing is associated with the action
only afterward and no pose correction is applied. Contacts are resolved from
achieved board pose against complete placemat target polygons and synthetic
depth/normal/dwell/focus/UI policy without receiving a per-action expected
output. An exact-once `ContactResult`-only observer, explicit calibration
surrogates, natural camera/tag-loss and device/arm fault injection,
report-schema-v3 output, manifest-v2 `vision.json` evidence, and complete
planner/vision/executor recomputation finish that replay-stable virtual slice.
The separate adaptive executor uses a shared opaque camera/contact truth,
typed two-sided achieved feedback, pure board-pose classification, complete
safe-suffix re-solve, atomic queue replacement, corrected-hover convergence,
truth-derived contact, independent output verification, and final park. The
eye-on-arm foundation separately reproduces carrier FK from raw T=1051 evidence
and structurally binds exact wire/image/detection/bracket bytes.

The adaptive runner now also has immutable one-based fault schedules for
camera unavailable, tag loss, blur, noise, unqualified timestamps, and stale
frames. Faults are content-addressed, consumed exactly once, halt before
contact, and close the virtual plant. Corrected multi-character keyboard and
Android rehearsals preserve action/target/feedback/contact/outcome correlation
after atomic queue replacement. Separate bounded services run all 46 keyboard
and 29 phone targets through complete adaptive sessions and run fixed signed,
over-limit, and SHA-256-seeded combined translation/yaw perturbations without
serializing private transforms. Full-catalog coverage binds a 2.5 mm
translation, 0.5 degree yaw/tilt, and 5 px synthetic policy; perturbation binds
the stricter 1.5 mm, 0.25 degree, and 3 px policy. Each single-target adaptive
route is bounded to at most 128 executed virtual waypoints. The 2026-09-04
full-catalog run accepted 75/75 sessions with deterministic report SHA-256
`232dcdd5c7bb6cb7afb6e4dcac6001797991faa54587dd7e0979e67880d8d4e2`;
the estimator-v1.1 perturbation rerun passed all 20/20 declared outcomes,
including four expected safe rejections, with report SHA-256
`9dda1bc28015ee6943d0e5017e16756dd30c6d0530d950a818161c28aa15dd20`.

All commands emit zero-authority reports. The fixed-overview topology now
matches the selected Phase 1 architecture, but its current fixture, intrinsics,
quality thresholds, and truth comparison are synthetic and are not physical
robot-frame correction. The adaptive moving-camera fixture remains optional
Phase 2 research and likewise uses unmeasured mount/intrinsic values. No
physical outcome observer or hardware validation exists. Implemented diagnostic
passes can coexist with explicit IK, collision, physical singularity, physical
vision, commissioning, and physical-release blockers. No live-motion command is
exposed, no canonical geometry or hardware gate changed, and these components
confer no physical authority.

The current software checkpoint is specific: the documented historical
Freeze-005 placement, retained unchanged as historical simulation provenance
under active Freeze 011, accepts 38/75 independent target routes, including keyboard `"a"`
but excluding phone `"a"`. The locked, unmeasured rank-1 sensitivity overlay
accepts all 75 independent routes and completes the `test`/`test.` virtual
acceptance pair. The current recorded keyboard golden replays identically.
The additive V2 rendering of that same acceptance pair makes its initial park
a checked state rather than a command: keyboard `test` binds 48 route
waypoints to 47 non-wire commands and four contact journals, while Android
`test.` binds 61 waypoints to 60 commands and five contact journals. The phone
state observation remains a semantic observation with no contact, route or
authorization command, or journal. V2 binds every command to its endpoint and
incoming-midpoint collision evidence and every contact to its own final-HOVER
B0477 report without changing the legacy replay artifact.
Report schema v3 now shows that
every physical-action hover passed the fixed-overview JPEG/tag/planar-pose gate
and that simulated outputs arise from retained achieved IK poses, complete
placemat-region hit testing, and a separate result-only observer rather than a
per-action expected-character shortcut. Manifest schema v2 preserves the
redacted vision ledger in `vision.json`. That validates a stronger software
orchestration boundary. The adaptive-schema runner additionally preserves the
optional Phase 2 upper-arm-camera research path from achieved joint state,
strict two-sided
capture timing, real JPEG pixels, board-registration correction, complete
suffix re-solve/atomic replacement, and truth-derived contact. Its 12 mm
keyboard and 8 mm phone shift regressions pass, while over-limit and zero
correction-budget cases fault before contact. Separately, the 2026-09-04
full-catalog adaptive screen accepted 75/75 sessions under its bounded
2.5 mm / 0.5 degree / 5 px synthetic policy; its deterministic report SHA-256 is
`232dcdd5c7bb6cb7afb6e4dcac6001797991faa54587dd7e0979e67880d8d4e2`.
The stricter 1.5 mm / 0.25 degree / 3 px perturbation campaign passed all 20/20
declared outcomes, including four expected safe rejections, with report SHA-256
`9dda1bc28015ee6943d0e5017e16756dd30c6d0530d950a818161c28aa15dd20`.
Those results must guide measurement rather than dictate hardware: per-session
adaptive artifact replay, physical static-camera capture/undistortion/
registration, support and visibility qualification, physical
robot/controller-frame correction, physical outcome
observation, hardware validation, and full-body route collision remain absent
or blocked.

The aggregate `qualify-prehardware` service now binds this work into one
ordered zero-authority campaign. Its quick profile requires coherent startup,
the corrected 12 mm keyboard and 8 mm phone cases, legacy JPEG tag-loss
fail-stop, and an identical full-document rerun. Its standard profile adds
nominal adaptive sessions, excessive-offset rejection, all nine deterministic
legacy fault families, and a fresh 75/75 route screen against the promoted
rank-1 overlay. The report deliberately separates software campaign success,
coverage state, and permanent `physical_ready: false`; the promoted layout is
still an unmeasured sensitivity overlay. Qualification artifact persistence and
strict replay now use a dedicated six-artifact, manifest-last schema. Strict
verification rejects incomplete, extra, noncanonical, oversized, traversing,
symlinked, hash-drifted, private-payload, or nonzero-authority packages; replay
then reruns the public qualification rather than trusting stored PASS data. The
inner v1 report retains its legacy hash and runner-local evidence declaration,
while the outer manifest is authoritative for recording/replay.

The next work shall execute this order:

1. Continue active build `2026-09-01_CELL-A` through Step 00 without claiming
   any unperformed PASS. Job 00A is `POSTPRINT_PASS`; record and qualify Jobs
   00B–00F through their controlled prerequisites before dependent production
   printing. Record the Pro arm/controller/firmware, PERIBOARD-409, bare A16,
   tool, board, cable, and material identities. Do not treat the old holder rail
   or IMX335-B fields as Phase 1 purchase requirements. Use the confirmed B0477
   catalog profile for software and replaceable-carriage design, but hold camera
   receipt acceptance, final mount cuts/fabrication, locked optical settings,
   lighting selection, installation, and release until the swept-volume,
   received-part, and optical studies close. Prepare the host with
   `setup-rocell.ps1 -Profile hardware`, require `host-doctor`, rerun the
   incapable-provider `rehearse-physical-connections` gate, and create the
   arrival record with `start-rocell-onboarding.ps1`. Use the persistent session
   only through its documented challenges and stop line: no stored intake,
   inventory, receipt, or `DIAGNOSTIC_READY` assessment is a reviewed stage PASS
   or permission to connect, energize, initialize, move, or contact.
2. Use `qualify-prehardware --profile quick --require-pass` as the short
   software integration gate and run `--profile standard` at milestone
   boundaries; record/replay milestone qualification packages with the
   dedicated schema. Run `workcell --json`, then
   `stress-placemat-geometry --json` for the expected diagnostic sensitivity
   result and `stress-placemat-geometry --zero-bounds --require-no-gaps --json`
   for the all-75 nominal control. Do not require no gaps from the default
   unmeasured matrix or interpret its 27 phone-target gaps as a physical fail.
   Retain the new all-75 adaptive campaign, signed/boundary
   and seeded perturbation campaign, fixed-camera and optional moving-camera
   fault matrices,
   queue/revision/resource tests, independent FK oracle, protocol emulator, and
   mission-through-ports rehearsal as opt-in/nightly gates. Continue the still
   open portions: persist/replay full adaptive per-session JPEG and
   queue-installation evidence; extend the sealed B0477 intrinsics boundary with
   generated distortion/pose distributions and add lighting, freshness,
   occlusion, tool-marker, and visibility distributions beyond board-pose
   inputs; retain joint-tracking
   distributions only for the optional arm camera; and refactor the
   geometry-rich adaptive executor itself onto commissioned
   `MissionRuntimePorts` implementations without weakening authority. Retain
   the short fixed-overview and adaptive keyboard/phone cases as fast golden
   regressions. Retain the additive dense V2 keyboard/phone assembly,
   tamper/fault, journal-boundary, and restart-refusal tests as the strongest
   pre-hardware join gate; do not reinterpret their isolated collision fixture
   or non-wire controller runtime as a physical provider.
3. Replace the broader study's sensitivity-only clamp/base/yaw/tool axes with measured, uncertainty-bearing installed hypotheses. Compare the measurements with rank 1 rather than forcing the build to match it, then rerun the exact 75-route and virtual multi-target gates.
4. Populate the historical 19-body readiness contract and the additive
   static-B0477 26-body mission contract with one coherent set of accepted full
   link, gripper, base/clamp, static gantry/posts/crossbar/camera/lighting/fixed
   cable, connector, tool, harness, and fixture geometry. Replace V2's isolated
   binding fixture with the surveyed/FK-derived adapter; include an optional
   holder/moving cable only if Phase 2 is selected. Approve a positive
   clearance/uncertainty policy and integrate pose/sweep evidence into every
   route phase. Add the physical
   six-dimensional Jacobian/manipulability and installed-system IK/orientation,
   payload, cable, and approach/retract proof for both tool routes; keep the
   solver-weighted conditioning metric diagnostic-only.
5. Measure and version exact static support/camera geometry,
   `Wv_T_C_overhead_optical`, camera intrinsics/distortion/settings,
   support/base witness, URDF-to-controller Cartesian-frame correlation,
   board-to-robot transform, route TCP/compliance, and installed
   keyboard/phone target maps. Primary operation does not require
   exposure-to-joint camera-pose synchronization.
6. Adapt and qualify the existing JPEG/tag36h11/planar-pose boundary for the
   exact overhead camera and native mode, or substitute an independently validated
   physical implementation while retaining the typed contracts. Add measured
   distortion handling, recorded physical-image campaigns, persistent
   controls/identity, bounded buffer flushing, stale/duplicate-frame checks,
   support witness, and calibrated quality/covariance gates that never consume
   simulator truth. Migrate observation through `MissionRuntimePorts`, then add
   bounded overhead tool-marker correction only above proven clearance if the
   error budget requires it; never reuse the synthetic fixed-fixture comparison
   as robot localization. Build the controlled capture
   implementation that produces the strict offline bundle, then qualify its
   clock-correlation/device-time evidence, camera/artifact registry resolution,
   raw tag corners/inliers/covariance, and independent physical-validation
   boundary. Implement the physical-data calibration solve/report and guarded
   promotion workflows for exact intrinsics,
   the measured tag map, static eye-to-hand `Wv_T_C_overhead_optical` and
   `B_T_Wv`,
   independent `R_ctrl` correlation/model residuals, route TCP/compliance,
   keyboard pose/key map, and phone screen/target map, with dependency hashes
   and held-out residuals.
7. Close the static-camera architecture, support/optics, visibility, and reach
   holds; then release the controlled overhead-camera/calibration-datum/contact-
   guard/gravity-stop addendum without inventing mount dimensions or adding
   informal board holes. Keep any arm camera disabled unless a later Phase 2
   change separately qualifies it.
8. Proceed to hardware-in-loop feedback and empty-cell characterization only under the E-stop, gravity-safe, active-build, frame-contract, and gate-projection controls. Keep contact later and separately gated.

## 25. Primary external references

- [Waveshare RoArm-M3 product specification](https://www.waveshare.com/product/ai/robots/roarm-m3.htm) — workspace, payload, repeatability, power, encoder, controller, and interface specifications.
- [Waveshare standalone RoArm-M3 product](https://www.waveshare.com/roarm-m3.htm) — purchased product, Pro/S variants, package contents, bundled holder, 21 × 13.5 mm mount pattern, upper-arm rails, and onboard ESP32 arm-controller context.
- [Waveshare IMX335 5MP USB Camera (B)](https://www.waveshare.com/product/ai/cameras/single-cameras/imx335-5mp-usb-camera-b.htm) — historical Freeze 009 arm-holder candidate whose 21 × 13.5 mm pattern matches the bundled holder; it is not the selected Phase 1 overhead camera.
- [Waveshare ESP32-CAM](https://www.waveshare.com/ESP32-CAM.htm) — separate, non-included OV2640 product retained only as evidence for the optional adapter boundary.
- [Waveshare RoArm-M3 wiki](https://www.waveshare.com/wiki/RoArm-M3) — startup, precautions, interfaces, and secondary-development overview.
- [Waveshare RoArm-M3 motion command reference](https://www.waveshare.com/wiki/RoArm-M3-S_Robotic_Arm_Control) — raw JSON frames, units, T=104/T=1041/T=105, speed behavior, and controller axes.
- [Waveshare JSON command catalog](https://www.waveshare.com/wiki/RoArm-M3-S_JSON_Command_Meaning) — USB/UART/HTTP communication and torque/control commands.
- [Official Waveshare Python SDK](https://github.com/waveshareteam/waveshare_roarm_sdk) and [M3 API documentation](https://github.com/waveshareteam/waveshare_roarm_sdk/blob/main/doc/roarm_m3_en.md) — current SDK interface and transport constraints.
- [Official SDK command mapping](https://github.com/waveshareteam/waveshare_roarm_sdk/blob/main/roarm_sdk/common.py) — confirms the high-level pose API maps to T=1041 and shows feedback parsing behavior.
- [Official Waveshare ROS2/MoveIt workspace](https://github.com/waveshareteam/roarm_ws) — optional future URDF, driver, IKFast, MoveIt2, and line/arc planning path.
- [OpenCV ChArUco calibration guidance](https://docs.opencv.org/4.12.0/df/d4a/tutorial_charuco_detection.html) — high-precision corner calibration workflow and capture guidance.
- [OpenCV hand-eye/robot-world calibration API](https://docs.opencv.org/doc/doxygen/html/d4/d93/group__calib.html) and [PnP pose-estimation reference](https://docs.opencv.org/4.12.0/d5/d1f/calib3d_solvePnP.html) — candidate solvers and validation primitives for the camera/board/arm transform chain.

## 26. Change-control rule

This file is the cross-system roadmap. Update it when an architectural decision, release tier, phase gate, or definition of done changes. Do not use it to overwrite controlled RC03 geometry or evidence. Any change to board/station/tag/tool geometry must follow RC03's own revision, regeneration, validation, and checksum process. Any change to runtime behavior must update its schemas/tests/calibration dependencies and preserve a rollback version.

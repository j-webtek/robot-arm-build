# Pre-arm-calibration execution plan

Plan ID: `ROCELL-PRECAL-001`  
Revision: 2 — 2026-09-12  
Status: **IN PROGRESS — P1 hardware-free implementation and verification**  
Workspace: `C:\Users\Jack\Desktop\robot-arm-build`  
Working export parent: `software/runs/wizard-exports`

## 1. Purpose and definition of success

Implement the six agreed preparation steps so that, when the physical build is
ready, we have a coherent, tested application for connecting the selected camera
and arm, collecting trustworthy observations and beginning arm-reference
calibration through the supported commissioning process.

The eventual mission remains physical individual keyboard keystrokes and taps
on an Android screen. This plan prepares that mission; it does not authorize
contact, claim typing accuracy or make an unassembled arm safe to energize.

There are two separate completion levels:

- **Software preparation complete:** the six work packages' hardware-free
  deliverables and integrated tests pass, remaining physical measurements are
  explicit, and the operator interface cannot confuse simulation with hardware.
- **Ready to begin physical arm-reference calibration:** the required genuine
  camera/board, arm identity, power/startup and feedback evidence is collected
  and reviewed in canonical order, the installation is stable, and the separate
  calibration/noncontact authority is available. Software tests cannot grant it.

Revision 1 was documentation only. The user subsequently approved implementation;
revision 2 tracks hardware-free P1 work. This does not authorize an actual camera
campaign, USB descriptor query, serial open, control change, equipment power,
motion or hardware-freeze revision. The workspace currently has no Git repository;
revisions are saved as Markdown, not Git commits.

## 2. Governing documents and current baseline

This is the near-term execution checklist under the existing
[system master plan](../../ROBOT_TYPING_SYSTEM_MASTER_PLAN.md),
[build alignment](../../BUILD_ALIGNMENT_FREEZE.md),
[camera/arm connection plan](CAMERA_ARM_CONNECTION_INTEGRATION_PLAN.md) and
[developer playbook](CAMERA_ARM_DEVELOPER_PLAYBOOK.md). It does not replace the
controlled hardware sources, stage catalog, effect policies or evidence contracts.
Use the [completion matrix](ONBOARDING_APPLICATION_COMPLETION_MATRIX.md) for the
broader application's status. A historical checkpoint is not a current release.

### Baseline at plan creation (revision 1)

| Area | Evidence available | Remaining limit |
| --- | --- | --- |
| Hardware intent | RoArm-M3 Pro and purchased Arducam B0477 with nominal 16 mm manual C-mount lens; static overhead primary selected | Arm/board/support assembly and installed measurements are not complete |
| Camera metadata | Actual wizard-backend endpoint, USB-instance/container and driver/parent metadata checks succeeded | Persistent unit serial/selector and negotiated USB speed remain unqualified |
| Camera bench tests | Separate utility acquired images and observed full-resolution 5472 × 3648 YUY2 at 8 fps | This is not original wizard commissioning; no catalog-rate assumption may replace the observation |
| Camera helper | Separate metadata-only v2 helper/catalog built and tested | Inventory/identity only; no capture authority and no fallback to the drifted old catalog |
| Camera acquisition | Public probe/settings-capture components and modeled storage/dispatch tests exist | Fresh full-history acceptance still fails the admission deadline |
| Failure reporting | Specific retained startup causes now reach UI errors and ordinary/exact-attempt exports; 104 selected tests passed | Better reporting does not fix startup performance |
| Task simulation | Nominal keyboard/phone tasks and feasibility reporting exist | Locked default task path still has legacy eye-on-arm dependencies and unresolved IK gaps |
| Arm connection | Protocol, metadata, rehearsal and bounded feedback foundations exist | Original stages 9–12 and a qualified physical connection are unfinished |
| Calibration | Static-camera requirement/solver/evidence components exist | Installed data acquisition, complete stage integration and robot-frame evidence remain unfinished |

The latest recorded application fingerprint is
`ca3114a5b49859f88344382d4d6339114022f3f7e381f38da4e89f6b03700c13`.
Recompute it before implementation; it is a historical comparison, not a pin to
accept automatically. Old source-bound sessions must remain old sessions.

References:

- [Metadata successor](CAMERA_METADATA_SUCCESSOR_WORKORDER.md).
- [Received-camera bench observations](CAMERA_BENCH_2026-09-11.md).
- [Startup failure diagnostics](CAMERA_ATTEMPT_FAILURE_DIAGNOSTICS_WORKORDER.md).
- [Full-history timing failure](CAMERA_FULL_HISTORY_INTEGRATION_WORKORDER.md).
- [Static simulation migration](STATIC_TASK_SIMULATION_MIGRATION_WORKORDER.md).
- [Original arm identity work order](ARM_IDENTITY_ONBOARDING_WORKORDER.md).

### Decisions retained

- Use the purchased camera as the static overhead primary; do not return to an
  arm-mounted primary or buy a replacement as an implementation shortcut.
- Keep final focus, aperture, working distance and board-coverage checks deferred
  until the real support/build is ready. The earlier approximately 10-inch bench
  distance is not the installed camera height or a calibration input.
- Read geometry from the active RC03 package, not a new hand-entered duplicate.
  The nominal board is 610 × 457 mm; actual board, device and tag measurements
  still need provenance. Nominal key centers are not surveyed contact targets.
- Preserve the active package, old freezes, runtime binaries/catalogs, failed
  attempts and diagnostic exports. Changes require explicit versioning and
  dependency review, not silent rehashing of whatever is on disk.
- No automatic homing, torque changes, motion, contact, firmware flashing,
  driver installation, port reset or operating-system reboot belongs to this plan.

## 3. Work order versus physical commissioning order

The six numbered steps are development priorities, not permission to rearrange
physical prerequisites. Work on the arm interface and calibration screens can
use modeled predecessors before hardware is ready. Their physical actions must
remain held until genuine predecessor evidence exists.

| Package | Development dependency | What can happen before assembly? |
| --- | --- | --- |
| P1 — Reliable camera startup | Existing failure/timing evidence | Profiling, repair and complete no-device acceptance |
| P2 — Static-camera simulation | Audit current build/profile/graph sources | Versioned static model and synthetic observations |
| P3 — Reachability/collision | Reproduce legacy failures first; final results require P2 | Frame/TCP diagnosis and modeled workspace/path screening |
| P4 — Arm connection onboarding | Existing arm work order; shared interfaces below | Contracts, fake transport, UI and original-storage tests only |
| P5 — Received-camera qualification | P1 plus implemented genuine stage prerequisites | Develop all software now; separately admitted camera-only checks where eligible |
| P6 — Calibration-day interface | P2/P3 frame/geometry contracts; P4/P5 observation contracts | Build and rehearse the interface/data flow; installed evidence waits for the build |

Recommended implementation sequence:

1. P1 profiling/fix and a fresh complete software acceptance run.
2. P2 static-profile migration and P3 systematic reach/collision diagnosis.
3. P4 arm connection software and P5 missing camera qualification software.
4. P6 integrated calibration interface and complete no-device rehearsal.
5. Actual P5 camera qualification and passive installed camera/board work when
   their genuine prerequisites and operator approval are available.
6. Actual P4 arm stages in order, then the P6 readiness review for arm calibration.

P6's passive optical work must precede actual P4 arm admission. This is not a
cycle: the software interfaces can be built early; their physical execution
follows the existing [stage catalog](../config/physical_onboarding_stage_catalog.json):

| Canonical stages | Responsibility | Important boundary |
| --- | --- | --- |
| 1–4 | Sources, static-camera design, received equipment and camera identity | Identification alone is not activation or speed qualification |
| 5–6 | Mode/control verification, then independent frame-freshness qualification | One settings-verification image is not a freshness pass |
| 7–8 | Preliminary optical screen, then installed camera intrinsics and passive camera-to-board registration | Actuator supply disconnected; no robot-frame calibration inferred |
| 9–12 | Arm identity, power safety, observed startup and one-shot feedback | Metadata does not open COM; feedback does not authorize motion |
| 13 | Arm/reference-frame, controller/model and tool/target characterization | Separate externally authorized noncontact process |
| 14–15 | Noncontact acceptance and diagnostic handoff | Neither automatically grants keyboard/phone contact |

## 4. Shared design and implementation rules

### One service-backed workflow

Reuse this ownership chain for new work:

`Controlled source/configuration → validated contracts → application service →
reviewed action ticket → existing coordinator/original store → bounded provider →
verified result and cleanup → completion log → UI publication/export`.

- Pure geometry, validation, solving and policy functions must not access devices.
- Browser and terminal clients call the same registered application actions.
  No browser-owned serial implementation, raw helper command or parallel database.
- Each displayed result identifies its source version, architecture, session,
  device/selection, settings epoch and evidence provenance where applicable.
- Configuration proposals, observed settings, modeled measurements and accepted
  installed evidence are distinct values with distinct lifecycle states.
- Reuse existing static calibration, frame ingestion, serial and USB components;
  do not create duplicates merely because their current UI join is incomplete.
- Navigation, status polling and reopening retained reports remain inert.
  Automate validation, calculations, evidence collection within an admitted
  operation, report assembly and next-step guidance. Do not automate consent,
  physical actions, stage acceptance, uncertain retries or unknown measurements.

### Efficiency and code quality

- Comment frame directions, units, assumptions, ownership and rejection reasons.
  Explain why a safety/revalidation boundary exists, not just what a line does.
- Separate pure calculations from I/O so simulations exercise production logic.
- Bound frame queues, subprocess lifetimes, output sizes and memory. A slow UI
  must not delay cleanup or grow an unlimited video backlog.
- Use existing dataset streaming/chunk verification. Full-size test images must
  exercise the real byte/stride path, not only resized thumbnail logic.
- Keep accepted data immutable; limit copies to necessary ownership boundaries.
  Optimize measured costs without caching acceptance across mutable boundaries.
- Maintain closed inputs, explicit UNKNOWN states, structured errors and tests
  for rejection paths. Track remaining type-check findings; do not suppress them
  to describe a module or whole application as clean.

### Shared failure contract

A failure must identify the operation and what was actually observed, preserve
original evidence, withhold current publication when appropriate and explain the
next safe investigation/export action. Missing accounting is unknown, not zero.
Stopping the wizard is not a physical robot emergency stop. Cleanup uncertainty
and consumed attempts must not become automatic retries on reopening.

## 5. P1 — Make camera startup and the complete software path reliable

### Outcome

A fresh original-store simulation completes the intended identity-to-probe-to-
settings-frame workflow under unchanged admission rules. It can export, shut
down and reopen its history without replay or restored device ownership.

### Existing code and evidence to start from

- [Full-history work order](CAMERA_FULL_HISTORY_INTEGRATION_WORKORDER.md).
- [Probe admission](../src/rocell/application/camera_probe_admission.py),
  [original-scope checks](../src/rocell/application/camera_probe_original_scope.py)
  and [capacity](../src/rocell/application/camera_probe_capacity.py).
- [Camera persistence](../src/rocell/application/commissioning_camera_persistence.py)
  and [shared M1 persistence](../src/rocell/application/commissioning_m1_persistence.py).
- [Native supervisor](../src/rocell/providers/windows/native_camera_activation_supervisor.py).
- [Full-history test](../tests/unit/test_arrival_camera_full_history_ntfs.py)
  and [read-only timing summarizer](../scripts/summarize_camera_admission_trace.py).

### Tickets

- [ ] **P1.1 — Establish a reproducible timing baseline.** Reconcile the terminal
  run-03 evidence; record machine/load, source, fixture lineage, history size,
  record bytes and inclusive/exclusive timing semantics. Instrument exact nested
  validation calls without changing arguments, results, exceptions or clocks.
  Distinguish repeated source hashing, session/package reads, family audits,
  serialization, capacity queries and runtime verification. Do not sum overlapping
  spans as exclusive cost or equate a missing span with a cheap operation.
- [x] **P1.2 — Design and test the smallest measured optimization.** Specify which
  freshly verified data can be reused, for how long, and which subsequent events
  require another audit. Retain checks for record-only corruption, source/epoch/
  enrollment changes, lost leases, cancellation and post-disk mutations. No
  cross-call acceptance cache, longer deadline, renewed permit or omitted sibling
  record family is an acceptable fix.
- [ ] **P1.3 — Repair the production path and run bounded regressions.** Preserve
  error summaries and exact failed-attempt exports. Add tests for nominal and
  growing history, quota boundaries, slow disk/callbacks, changed bytes, deadline
  expiry and interrupted cleanup. A legitimate timeout must still reject release.
- [ ] **P1.4 — Run fresh full-history acceptance.** Construct all predecessors in
  a new test store with real production writers and explicitly modeled physical
  facts. Use public actions through reopen, fresh metadata, refresh, probe
  preparation/review, probe, staged settings, one-frame verification and both
  exports. Verify complete original readback and clean lease exit afterward.
- [ ] **P1.5 — Check restart and operator presentation.** A new application shows
  retained history and current holds, not an automatically connected camera.
  Confirm the browser/terminal show real causes and distinguish a successful
  worker, accepted data publication and a physical-stage verdict.

### Acceptance and handoff

- The full nominal chain passes with no production timing, quota or validation
  relaxation; source remains fixed for the duration of that run.
- Report measured slack at admission boundaries and growing-history behavior;
  one quiet-host success is not a worst-case performance qualification.
- Faults produce no data handoff after failed original verification, lease exit,
  current-context checks or completion logging. Unknown outcomes stay held.
- Record test commands, distinct case IDs, timings, JUnit, source fingerprint,
  exports and remaining limits in the existing work order and this plan's ledger.
- **P1 is not complete while the full-history timing failure remains unresolved.**

## 6. P2 — Align the simulator with the static overhead build

### Outcome

Keyboard and phone tasks explicitly select a coherent static-primary model,
with the correct coordinate/calibration dependencies and controlled geometry.
Old eye-on-arm reports remain valid historical reports of their original model.

### Reuse and source ownership

Start with the [migration work order](STATIC_TASK_SIMULATION_MIGRATION_WORKORDER.md),
[static requirement graph](../src/rocell/calibration/static_phase1_requirements.py),
[static calibration application](../src/rocell/application/static_phase1_calibration.py),
[development profiles](../src/rocell/typing/development_profiles.py),
[alignment checks](../src/rocell/workcell/alignment.py),
[simulation lock](../config/simulation_bundle_lock.json) and
[camera architecture plan](../config/camera_architecture_plan.json).

Hardware geometry comes from the controlled
[RC03 layout](../../active-project/RoCell_v0_3/config/workcell_layout.json),
[parameters](../../active-project/RoCell_v0_3/config/parameters.json),
[tag map](../../active-project/RoCell_v0_3/fiducials/apriltag_map.json) and the
[static support package](../../hardware/static_overhead_camera/README.md).
Consume these sources read-only. Conflicting releases are a review hold, not a
reason to mix whichever values make a scene look plausible.

### Tickets

- [ ] **P2.1 — Inventory every geometry/profile dependency.** Trace board origin,
  dimensions, keyboard/phone positions and heights, robot base, tool cases,
  fiducials, camera/lens/mode and gantry/cable bodies into the current simulator.
  Label each datum controlled nominal, synthetic, measured or unavailable; retain
  units and source hashes. Document missing per-key polygons and real screen maps.
- [ ] **P2.2 — Close the static frame contract.** Use explicit transform direction:
  `A_T_B` maps coordinates from frame B into frame A. Distinguish board `B`,
  camera `C_overhead_optical`, model/vendor frame `Wv`, controller `R_ctrl` and
  tool tip `T`. Preserve separate camera intrinsics, camera-to-board pose,
  robot/board relationship, controller correlation and tool calibration.
  Tags alone cannot determine robot coordinates.
- [ ] **P2.3 — Integrate, rather than duplicate, the static requirement graph.**
  Compare the existing static graph against task-profile and stage dependencies.
  Remove the legacy requirement only in an explicitly versioned static lane.
  Reject unknown/cyclic/mixed graphs; stage 8 must not depend on energized stage-13
  robot reference evidence. Robot-frame-dependent tasks still require that later
  evidence before any physical execution.
- [ ] **P2.4 — Build a versioned static simulation bundle.** Bind architecture,
  semantic profiles, camera model, geometry, URDF, tools, dependency graph and
  reports together. Preserve the old lock/bundle. Review any prospective controlled
  source promotion separately; creating this simulation must not release hardware.
- [ ] **P2.5 — Add static-view scenarios and migrate the task UI deliberately.**
  Keep the camera fixed while the modeled arm moves. Include clear observations,
  arm/tool occlusion, glare, tag loss, board/support movement, stale frames and
  settings drift. T0–T3 fit the board pose; K0/P0 remain independent checks.
  Show model/architecture/provenance in every task report and export.

### Acceptance and handoff

- The chosen static keyboard/phone lane cannot silently load eye-on-arm defaults.
- Nominal geometry matches its named build revision; measured data cannot be
  replaced by nominal defaults when a field is absent or a device moves.
- Changing camera settings, support, board, device seating or tool invalidates
  the corresponding downstream dependencies, not unrelated historical evidence.
- The schema/source migration is tested atomically, with explicit legacy tests.
- A documented coordinate map and geometry provenance table feed P3 and P6.

## 7. P3 — Resolve reachability and model complete approach/retreat paths

### Outcome

We understand the existing IK failures and have a bounded, repeatable assessment
of the intended keyboard/phone workspace, tool orientation and path clearance.
The output is a simulation result, not executable contact coordinates.

Reuse [IK](../src/rocell/kinematics/ik.py),
[URDF geometry](../src/rocell/geometry/urdf.py),
[transforms](../src/rocell/geometry/transforms.py),
[scene](../src/rocell/simulation/scene.py),
[collision](../src/rocell/simulation/collision.py) and
[static-route collision](../src/rocell/simulation/static_route_collision.py).

### Tickets

- [ ] **P3.1 — Reproduce the failures before changing the solver.** Retain the
  exact legacy `hi` point set, source/model/tool hashes and deterministic seeds.
  Record the shared park failure and keyboard-plane failures separately. Check
  transform direction, units, joint signs/limits and TCP extension against the
  source contract. Do not attribute every failure to physical reach.
- [ ] **P3.2 — Separate numerical and geometric failure modes.** Report position
  residual, tool-normal/orientation error, joint-limit intersection and forward-
  kinematic reconstruction for each solution. Compare bounded deterministic seeds
  or algorithms only after frame checks. Keep tolerances and controller limits;
  an out-of-limit solution is not a success.
- [ ] **P3.3 — Enumerate the supported task vocabulary.** Cover every intended
  key, phone target region, repeated press, approach and release. Define explicit
  handling of modifiers/chords, long presses, unsupported characters and screen
  orientation. Do not silently substitute host-side text injection or Android
  input commands for the arm's physical actions. Unresolved task capabilities
  must be rejected visibly or referred for a mission decision.
- [ ] **P3.4 — Check paths and visibility, not only endpoints.** Evaluate park,
  clear observation posture, approach, target, retreat and recovery. Include arm
  links, tools, fixtures, devices, gantry, camera, cables and lighting keepouts.
  Label sampled collision screens as sampled; add conservative continuous/swept-
  volume validation or retain an explicit continuous-path hold. Endpoint success
  does not establish path safety.
- [ ] **P3.5 — Exercise uncertainty and build tolerances.** Vary declared base,
  device, plane-height, tool and support uncertainties within an explicitly
  documented sensitivity study. Proposed tolerances are engineering assumptions,
  not measured acceptance. Identify which physical measurements dominate error.
- [ ] **P3.6 — Produce the workspace coverage report.** Display per-target reach,
  orientation, joint-limit, path/collision and visibility outcomes independently.
  Separate feasible, infeasible and inconclusive results; keep failed seeds and
  counterexamples. A needed layout/tool change requires explicit build review.

### Acceptance and handoff

- Every target/path in the declared supported mission has a traceable result;
  failed targets are not dropped or silently moved to achieve a pass rate.
- P2's static model is used for the final results. Legacy reproductions retain
  their original labels and are not upgraded to static evidence.
- Required routes pass the declared simulation checks, or a specific unresolved
  engineering hold remains. Diagnosis alone does not close a feasibility hold.
- Deliver a target/route coverage matrix, reproducible failure cases, uncertainty
  assumptions and a proposed measurement checklist for the physical build.

## 8. P4 — Finish connection-only arm onboarding and its simulation

### Outcome

The wizard can guide stages 9–12 using one authoritative service, with safe
wrong-device rejection, explicit power/startup boundaries and a bounded feedback
exchange. Develop and verify this against fake devices before physical use.

Reuse the [arm identity work order](ARM_IDENTITY_ONBOARDING_WORKORDER.md),
[serial profile](../config/arm_connection.json),
[native metadata](../src/rocell/application/wizard_native_arm_metadata.py),
[serial transport](../src/rocell/arm/serial_transport.py),
[feedback wire parser](../src/rocell/arm/feedback_wire.py) and
[owned feedback worker](../src/rocell/providers/windows/arm_feedback_worker.py).

### Tickets

- [ ] **P4.1 — Close the identity and stage contracts.** Distinguish received
  chassis/model/serial, controller USB identity, installed firmware and current
  COM mapping. Build the stage-9 submission/assessment/review originals described
  in the existing work order. Stage 9 depends on genuine stage-8 evidence and
  cannot manufacture later firmware qualification or an executable binding.
- [ ] **P4.2 — Build a deterministic virtual controller harness.** Reuse production
  parsers/validators; fake only the transport/process/device edge. Model boot text,
  reset, stale valid packets, fragmented/concatenated lines, malformed/oversized
  JSON, timeouts, partial writes, unplug/replug and changed-port/wrong-unit cases.
  Retain an exact ordered attempted-I/O transcript for assertions.
- [ ] **P4.3 — Integrate power/startup observations separately.** Implement stages
  10 and 11 with their own original evidence, cancellation and final-power-state
  handling. Operator reports are not instrument measurements. USB connection or
  serial opening can have reset/power implications; no observation is assumed
  safe merely because no motion command was deliberately sent.
- [ ] **P4.4 — Join the one-shot feedback workflow.** Resolve the reviewed unit at
  the final boundary, verify the scoped serial profile and exclusive ownership,
  then permit only the approved feedback exchange when all genuine prerequisites
  pass. Preserve unexpected bytes; no blind buffer purge, arbitrary command box,
  polling loop, torque command, homing or automatic retry. A valid response alone
  does not prove installed firmware identity or reference calibration.
- [ ] **P4.5 — Connect browser/terminal guidance and exports.** Show selected unit,
  evidence age/provenance, actual connection state, bounded observed feedback,
  unanswered requirements and safe disconnect/Stop meaning. Reuse existing action
  tickets and export mechanisms; do not infer a live connection from saved logs.
- [ ] **P4.6 — Complete original-store acceptance.** Use modeled predecessors
  with real storage and logging. Exercise partial retention, unknown final power,
  failed cleanup, result rotation and fresh reopening without replay. List the
  exact real-hardware checks still needed before the physical adapter is eligible.

### Acceptance and handoff

- Zero automatic connects or serial writes on launch, view, refresh or reopen.
- A selected COM number or friendly name cannot substitute for exact reviewed
  controller identity; changed identity or stale prerequisites stop before I/O.
- At most the separately approved feedback request is attempted. No motion,
  homing, torque, reset or firmware-update command occurs in tests or production
  connection-only scope. Unknown byte delivery never becomes a retry.
- Startup/reset and physical isolation uncertainties remain visible until actual
  supervised checks establish them. Stages 9–12 remain separate decisions.
- Completing software does not permit testing the unassembled arm. The received
  arm procedure waits for assembly, genuine predecessors and explicit approval.

## 9. P5 — Qualify the received camera through the supported workflow

### Outcome

The wizard can identify the intended physical camera and retain verified
connection, mode/control and freshness evidence. Separate software readiness,
temporary bench observations and final installed-camera acceptance.

Reuse the [metadata workflow](CAMERA_METADATA_SUCCESSOR_WORKORDER.md),
[USB integration](USB_IDENTITY_WIZARD_DISPATCH_WORKORDER.md),
[baseline guide](USB_BASELINE_OPERATOR_GUIDE.md),
[settings-capture handoff](CAMERA_CONFIGURATION_WIZARD_HANDOFF.md),
[settings/readback work order](CAMERA_SETTINGS_READBACK_WORKORDER.md) and
[bench observations](CAMERA_BENCH_2026-09-11.md). Prefer newer completed work-order
checkpoints over stale historical status paragraphs, after verifying their code.

### Tickets

- [ ] **P5.1 — Reconcile identity and runtime eligibility.** Preserve the actual
  B0477 endpoint/container mapping. Complete the supported original-bound route
  for descriptor-backed serial, topology and operating-speed evidence. The USB
  parent's identifier suffix is not a separately acquired serial property, and
  a USB 3 product/hub name is not a negotiated-speed observation. Metadata-only
  helper review does not authorize hub descriptor IO or camera activation.
- [ ] **P5.2 — Close original stage-5 assessment/review.** Reuse probe → explicit
  reported settings → bounded verification frame. Assess requested versus
  observed resolution, rational frame rate, subtype, stride/crop and controls.
  Evaluate the existing mode-policy prototype before adding another validator.
  Do not pass stage 5 from capability discovery alone or require stage-6 PASS
  to acquire the first stage-5 settings-verification observation.
- [ ] **P5.3 — Integrate separate freshness qualification.** Retain capture IDs,
  sequence, native/host timestamps, queue bounds, settle/latency observations and
  settings epochs. Reject stale/replayed observations and unknown freshness.
  Identical image pixels alone do not prove replay: a static scene can genuinely
  produce the same image. Specify the supported freshness evidence and limits
  before acceptance; one still frame cannot measure sustained freshness.
- [ ] **P5.4 — Prepare received-camera acceptance cases.** Test exact selection,
  camera busy in another application, unsupported modes, incomplete readback,
  disappearance, bounded capture, cleanup, close/reopen and restart invalidation.
  Reconnect and host-reboot trials follow their existing separately admitted
  original sequences. Do not repeat user unplug/replug actions without a defined
  test purpose; do not treat an app restart as a host reboot.
- [ ] **P5.5 — Review and qualify an actual mode policy.** Our bench observed
  full-resolution 8 fps, while a 9 fps request failed. Record that discrepancy;
  propose and review a compatible versioned profile if appropriate. Do not edit
  frozen evidence to make the nominal rate agree. Preview and calibration modes
  may differ only with explicit pixel transforms and separate qualification.
- [ ] **P5.6 — Run eligible camera-only checks with explicit consent.** Start only
  after P1 and required genuine original prerequisites pass. Confirm the current
  physical state, identify the exact device and state each operation's effects.
  Any settings write is a separate disclosed action. Keep the arm isolated and
  preserve all outcomes in the assigned folder. If board/receipt evidence needed
  by the current stage is absent, remain held; use no fabricated prefix.

### Acceptance and handoff

- Actual camera selection, runtime eligibility, identity evidence, measured
  operating link category, mode/control readback, cleanup and freshness have
  separate traceable outcomes. Unknowns and conflicts block the affected stage.
- Use actual observed modes; no silent resize, crop, driver/index fallback or
  assumed full-resolution 120 fps. Manual lens controls stay manual.
- Application/UI, provider and export describe the same operation and settings
  epoch. A still preview is labeled as a retained frame, not a live stream.
- Installed optics, all-six-tag coverage and support stability remain deferred
  until the real build. A temporary bench qualification cannot pass those rows.

## 10. P6 — Prepare the calibration-day interface, datasets and checklist

### Outcome

A developer-tested wizard can guide measurement intake, camera calibration and
passive registration, then assess readiness for the separate arm-reference
procedure. Build the whole interface using synthetic data now; install real
calibration only from correctly sourced, reviewed physical evidence later.

Reuse [static intrinsics](../src/rocell/calibration/static_camera_intrinsics.py),
[rigid correspondence](../src/rocell/calibration/rigid_correspondence.py),
[accuracy budgets](../src/rocell/calibration/accuracy_budget.py),
[configuration epochs](../src/rocell/application/physical_configuration_epochs.py)
and DEV-010 in the existing developer playbook.

### Tickets

- [ ] **P6.1 — Build a readiness and measurement intake page.** Show required
  measurements, units, source/provenance, uncertainty and the exact dependency
  blocked by each missing value. Collect board/tag dimensions and corner heights,
  camera installation, base/fixture placement, key surfaces, screen plane/case/
  orientation and tool geometry. Never prefill nominal values as observations.
- [ ] **P6.2 — Prepare acquisition and dataset validation.** Validate chart scale,
  camera/lens/settings identity, full pixel transforms, varied views, sharpness,
  exposure/clipping and coverage. Retain raw frames separately from derived
  previews and bind all settings/support epochs. Reuse bounded dataset writers;
  partial writes or missing frames stay incomplete and exportable.
- [ ] **P6.3 — Separate solving, evaluation and acceptance.** Implement candidate
  solve → independent evaluation → exact review → installation. Predeclare
  training/validation/held-out partitions; never tune with the final holdout.
  Derive thresholds from the target-accuracy budget and installed uncertainty.
  No arbitrary millimeter target or a low reprojection residual alone establishes
  accurate keyboard/phone contact. Unclosed limits remain blocking decisions.
- [ ] **P6.4 — Show trustworthy board/device overlays.** Draw the board, T0–T3
  fitting tags, independent K0/P0 checks, keyboard key regions, phone screen plane
  and coordinate axes. Make raw versus undistorted/cropped/display coordinates
  explicit. Correct plane height matters: board, keytops and screen are not
  interchangeable surfaces. Reject mirrored, wrong-scale or wrong-mode datasets.
- [ ] **P6.5 — Prepare the arm-reference evidence interface.** Import or collect
  evidence only through the existing separately authorized stage-13 boundary.
  Keep passive camera-to-board registration distinct from arm-to-board,
  controller/model and tool-tip transforms. Do not add wizard jog/move controls
  or use board tags alone to fabricate robot-frame calibration.
- [ ] **P6.6 — Prepare independent outcome observers.** Define keyboard observed
  characters/events and Android expected UI changes, including keyboard focus,
  app/page identity, screen rotation, latency and false-positive checks. Observe
  outcomes; do not substitute software input injection for mechanical typing or
  tapping. Calibrating geometry is not proof of successful actuation.
- [ ] **P6.7 — Rehearse the complete operator experience.** From a clean simulated
  setup, exercise missing measurements, valid candidate data, held-out failure,
  moved support/board/device, changed focus/mode/tool, interrupted acquisition,
  export and reopen. Show exactly what remains valid and what needs recollection.

### Physical readiness checklist — not an instruction to perform it now

- [ ] The arm is fully assembled and securely mounted; startup swept-volume and
  safety prerequisites have been reviewed through their supported process.
- [ ] Board, device fixtures and overhead support are installed, mechanically
  stable and consistent with the reviewed build revision.
- [ ] The actual working distance is measured; focus/aperture, lighting and mode
  are set for this installation, with full required tag coverage verified.
- [ ] Measured camera/board datasets pass passive stages 7–8 without implying
  robot-frame knowledge. Required settings/support epochs are current.
- [ ] Original stages 9–12 establish the intended arm/controller, safe startup
  observations, required firmware/serial evidence and bounded feedback behavior.
- [ ] Proposed tools, device planes, target maps, uncertainty allocations and
  independent observer interfaces are ready for characterization; unmeasured
  tool TCP/reference transforms remain explicitly unmeasured at entry.
- [ ] The supported external noncontact/reference procedure and its separate
  authority are available. No contact permission is inferred from this checklist.
- [ ] Export verification works and the operator knows where logs are stored and
  how to stop the software versus the separate physical safety procedure.

### Acceptance and handoff

The hardware-free wizard guides the complete process and all invalidation/error
cases without fake physical PASS states. The later genuine prerequisites make
the system eligible to begin arm-reference characterization—not automatically
calibrated, cleared for noncontact acceptance or permitted to type/tap.

## 11. Cross-package test and evidence strategy

| Lane | Required proof | What it does not prove |
| --- | --- | --- |
| Pure unit/contract | Deterministic transforms, schema rejection, source/epoch dependencies, policies | Device behavior or storage durability |
| Incapable provider | Protocol framing, exact request counts, deadline/cleanup/Stop paths | Received device or real driver behavior |
| Real local-storage composition | Original retention/readback, leases, partial writes, exact exports, restart | Truth of modeled physical predecessors |
| Public service/UI | Registered actions, input validation, clear status, inert navigation, export destination | A browser-render pass alone is full commissioning |
| Native-size dataset | Full resolution/stride, bounded memory, native-to-display transforms, failure retention | Correct installed optics or target accuracy |
| Full-history acceptance | Fresh complete supported original workflow under real timing/quotas | Worst-case host performance or received-hardware qualification |
| Received hardware | Explicitly scoped current unit/driver/camera or arm observations | Later stages, unattended operation or contact authority |

Cross-cutting negative cases: wrong unit, source/config drift, stale or mixed
architecture, malformed data, wrong transform/units, missing tag, invalid plane,
out-of-limit IK, collision, stale image, device busy, disconnect, failed close,
partial write, full disk, interruption, completion-log failure and restart.

Every implementation checkpoint must include:

1. Ticket IDs, exact edited files and a short explanation of the component join.
2. Before/after application/build/profile hashes and any deliberate migration.
3. Exact commands, environment, test selection, terminal results and timings.
4. Unique JUnit/output paths; failures retained, not overwritten or counted as
   passes. Distinguish selected regressions from a whole-repository run.
5. Verified ordinary and exact-attempt exports where applicable, with explicit
   modeled/received provenance and known redaction/omission limits.
6. Browser/terminal checks and launch-no-effects checks where their paths changed.
7. Remaining blockers, unmeasured hardware values and the next bounded ticket.

### Safe test execution convention

Commands below are templates for implementation time; they were not run while
writing this plan. Use a new path for every execution because pytest may clean
an existing `--basetemp`. Never reuse an original failure store as a test seed.

```powershell
$RocellPrecalRunId = 'precal-p1-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + ([guid]::NewGuid().ToString('N').Substring(0, 8))
$RocellPrecalTmp = Join-Path $PWD "software/runs/pytest-$RocellPrecalRunId"
$RocellPrecalJUnit = Join-Path $PWD ".codex-preserved/$RocellPrecalRunId.xml"
if ((Test-Path -LiteralPath $RocellPrecalTmp) -or (Test-Path -LiteralPath $RocellPrecalJUnit)) {
    throw 'Preserve the existing run; choose a new run ID.'
}
.\.venv\Scripts\python.exe -m pytest `
    software/tests/unit/test_camera_probe_admission_audit_reuse.py `
    software/tests/unit/test_camera_activation_dispatch_handoff.py `
    -q --basetemp=$RocellPrecalTmp --junitxml=$RocellPrecalJUnit
```

Review and extend the selection for the actual patch. The slow full-history run
uses its existing work-order procedure in a different new store. Keep source,
runtime inputs and timing policies fixed while it runs. Independent planning
does not justify modifying a running source-bound acceptance test's inputs.

## 12. Decisions to close during implementation

| Decision | Owner package | Rule until resolved |
| --- | --- | --- |
| Exact removable duplication in admission checks | P1 | Preserve checks and deadlines; measure before optimizing |
| Static task bundle/version and controlled-source promotion | P2 | Historical bundle remains historical; no mixed defaults or hardware release |
| Complete supported keys, modifiers/chords and Android tasks | P3 | Reject unsupported tasks; do not silently reduce the mission |
| Geometry/limits versus solver cause of IK failures | P3 | Inconclusive/failed routes remain non-executable |
| Arm identity, boot/reset and installed firmware evidence | P4 | No inferred firmware identity or general COM access |
| Actual serial and USB operating-speed evidence | P5 | Keep current persistent-identity/speed holds |
| Reviewed 8 fps full-resolution profile and any preview mode | P5 | Bench observation does not rewrite a frozen/qualified profile |
| Freshness, pixel/target accuracy and stability budgets | P5/P6 | Unknown thresholds cannot produce a PASS |
| Final mount height, lens adjustment and measured board/device/tool data | P6 plus physical build | Deferred; no nominal-as-measured substitution |

An implementer may resolve code details within the reviewed scope. A change to
hardware layout, procurement, mission coverage, effect permissions or physical
acceptance policy needs explicit review. Do not convert an unresolved decision
into a convenient default just to advance the wizard.

## 13. Progress ledger and next entry

This ledger tracks work-package completion; canonical physical stages remain
owned by their original records. Do not update them from this document.

| Package | Current state | Required exit artifact |
| --- | --- | --- |
| P1 | IN_PROGRESS; 796 earlier selected checks pass; run 07 test passes but concurrent source edits invalidate fixed-source acceptance | Measured fix, focused fault tests and fresh fixed-source full-history PASS |
| P2 | NOT_STARTED; static components exist but task migration is incomplete | Reviewed coherent static bundle and migration/UI evidence |
| P3 | NOT_STARTED; legacy failures retained | Reproducible cause analysis and complete target/path coverage report |
| P4 | NOT_STARTED; reusable protocol/metadata/rehearsal foundations exist | Stage 9–12 software integration and no-device acceptance; physical checks separate |
| P5 | NOT_STARTED; actual metadata/bench observations retained | Joined qualification software and separately reviewed received-camera evidence |
| P6 | NOT_STARTED; calibration components exist | Rehearsed intake/dataset/overlay/review interface and readiness checklist |

For each completed ticket append: date, ticket ID, source fingerprint, artifacts,
test/JUnit results, observed effects, remaining limits and next dependency. Mark
hardware-free and received-hardware acceptance separately. A planned ticket or
a green worker exit is not a completed package.

### P1 implementation entry — 2026-09-12

The [coherent-observation work order](CAMERA_COHERENT_OBSERVATION_WORKORDER.md)
records the preserved run-03 baseline, new regression tests, measured read-count
reduction and the exact production changes. One redundant session observation
is removed; all three callback record audits remain. Three final targeted
selections pass 417 cases; initial test development failures remain retained.
Fresh full-history run 04 failed after 2,346.00 s on fixed production source
`81dc579fa3126b18aea151160573757fac3af710f92e177604abc4c99162071a`.
The final release check took 2.031 s against a 2 s total startup window. The
specific retained error, unknown outcome and no-replay quarantine remain intact.
Settings/capture/camera exports and final post-capture assertions were not reached.
P1.2's narrow design is accepted; P1.1/P1.3/P1.4/P1.5 await remaining integrated
evidence. No P1 completion or physical stage advancement is claimed.

**Next dependency:** profile the lower-level original/evidence readers inside
release validation, test a measured optimization in fresh bounded fixtures, then
run another newly constructed full history. Preserve all independent validation
boundaries; do not extend deadlines, replay run 04 or test the actual camera.
The work order records exact artifacts and this next bounded ticket. P2–P6
implementation has not started under this plan. Read-only P2/P3 review reproduced
the existing IK gaps and identified static-model joins without changing geometry.

### P1 buffer-read successor — 2026-09-12

The [buffer-read work order](CAMERA_BOUNDED_READ_BUFFER_WORKORDER.md) records new
fresh-storage profiling, a one-function allocation/copying optimization and
679 passing selected checks. The 70-package callback retains the same 553 file
reads and 13,137 `nt.stat` calls while observed time decreases from 613–635 ms to
429–436 ms. Those file-only fixtures are not full-history acceptance.

Fresh full-history run 05 failed after 2,050.25 s on fixed production fingerprint
`a654894ea0572b11b02115ec2d0436a141926df8bae8d45f07f5200f94e9898c`.
The previous original stores remain untouched; no hardware, timeout, quota,
independent validation boundary or native runtime changed. The release callback
took 1.969 s, but the complete startup window still expired; camera settings,
capture and camera exports were not reached. **Next dependency:** profile prior
campaign/ledger history in newly constructed incapable fixtures, identify a
larger measured saving while retaining checks, then repeat full-history acceptance.
The expanded profiler passed four cases after run 05's terminal result (348.30 s),
bringing the current selected total to 681, with the two earlier profile cases
replaced rather than double-counted. Its eight-campaign fixture has 40 records,
40 attempt events and 70 evidence packages; callback samples are 2.446–2.659 s.
The measured metadata/path-check cost and bounded next ticket are in the work
order. These are fresh modeled camera-contract histories, not full USB/camera
acceptance. No metadata-check optimization has yet been made. There is no P1
PASS or automatic retry of the failed attempt.

### P1 existing-root successor — 2026-09-12

The [existing-root work order](STORAGE_EXISTING_ROOT_OBSERVATION_WORKORDER.md)
records the predicate/observation review, a single-module storage optimization,
28 new root tests and a mixed USB/camera profiling case. **757 distinct selected
checks pass** on source
`01440cf0377027aceab5f5375bd4ecbd1211f2e704b368262ad91e84f8391eb9`.
In the matched four-campaign profile, root walks fall 972 → 788 and metadata
calls 28,380 → 25,804; file reads and family audits remain unchanged. The
five-case profiler is diagnostic, not parent-startup or hardware qualification.

Fresh full-history run 06 **failed after 2,053.84 s**, on fixed source/test inputs
with no competing suites. Probe and capture release checks passed (1.625 s and
2.156 s under their unchanged 2 s / 5 s purpose-specific limits). Both modeled
campaigns are retained `SEALED_KNOWN`, but public settings capture failed before
ingestion/publication because the partial-workspace test's source-alias roster
omitted the capture workflow. Its actual source reader correctly refused the
missing launcher. Camera export and final post-capture assertions were not reached.

The test-only source roster was corrected after termination. The new
ingestion/source-change tests and related capture/configuration regressions pass
46 cases in 696.66 s, bringing the combined current selection to **796 distinct
passing cases** (seven reruns are not double-counted). Production source checks
and all prior originals stay unchanged. Fresh run 07 used the corrected fixture
and this task made no production input changes or launched competing suites.
Its test passed in **2,242.325 s**, including capture, verified export and final
original readback/clean leases, but the post-run source comparison failed.
Concurrent arm/UI edits outside this patch changed the checkout from
`01440cf0…91eb9` to `af19e6a3…7d615c`. The source-modeled fixture cannot establish
one fixed executing revision across those changes. P1.4 remains open.

The subsequent retention/export/registry/UI selection passed **144 cases** in
12.48 s. This later-source result is not combined with the earlier 796 cases as
one fixed-source release. Exact hashes, successful export verification, observed
timing and the source-drift evidence are in the existing-root work order.
**Next dependency:** coordinate concurrent edits or use a verified isolated
source snapshot, then construct fresh originals for acceptance. Preserve all
concurrent work and prior stores. No hardware authority or P1 completion is claimed.

The full-history test now automatically records and checks its actual terminal
checkout fingerprint, independently of modeled source identity. Four new guard
cases plus existing fixture checks pass 14 cases in 4.29 s; no slow acceptance
rerun is claimed. The shared checkout changed again during follow-up, confirming
that the next run needs a coordinated freeze or verified isolated input snapshot.
P2–P6 entries above describe work accepted under this task's plan; concurrent
arm/UI edits have not yet been reconciled into those completion claims.

### Camera-only isolated successor — 2026-09-12

The [isolated camera acceptance work order](CAMERA_ISOLATED_ACCEPTANCE_WORKORDER.md)
records a new copied-input run, independent of ongoing shared arm work. Its
23-case smoke and exact full-history case passed; the latter completed in
2,326.08 s with matching before/after input inventories and actual source
`426eb8a21300dec278d0eaf3e48e62051ef2ec5bc4fa54e70f49969e67762e69`.
It verifies probe/settings/capture/export, clean original readback and a genuine
fresh-application restart on the same simulated original store. Restart does not
restore an image, connection, settings reference, attempt or capture permission.
The export was independently verified from the isolated implementation.

This resolves the nominal fixed-source and post-capture restart gaps for that
snapshot, not every P1 requirement or the current mutable checkout. The full case
exports a capture attempt and retains the probe packet, but does not itself run
the separate public probe-attempt export. Growing-history and current UI evidence
remain to be reconciled. Public original validation remains slow (the settings
capture action took approximately 121 s), despite meeting the unchanged short
native admission limits. Keep a camera-only performance follow-up open.

The shared snapshot runner has separate 25-case file-only verification; its
post-launch JUnit/bounded-copy improvements are not relabeled as part of the older
copied runner. No physical camera, USB, serial, power or motion access occurred.
Do not mark P5 or installed calibration complete. The next camera integration
target is original stage-5 mode/control assessment and a separately reviewed
8 fps operating policy, preserving the earlier bench-versus-catalog discrepancy.

### Camera-only readback batching — 2026-09-12

The [camera evidence readback work order](CAMERA_EVIDENCE_READ_BATCH_WORKORDER.md)
records an implemented private batch scope and unchanged per-package validation,
opening/closing whole-store audits, exact ownership and late source/Stop/deadline
checks. Only two camera production modules and their tests changed in this patch;
arm/shared Arrival/UI/native/config work was preserved.

Frozen snapshot `camera-isolated-20260912-03` passed 23 smoke cases, the complete
original-history case in 1,869.04 s, and a later 25-case batch selection, all with
unchanged copied input/source checks. Actual source is
`adfc02617d55e9ecc71d3c40dd2f1d69f952e86883efd822d68fa5bb4af809f1`.
Capture/export, final original readback and fresh-application restart passed;
restart restored no connection or permission and left clean leases.

Observed public settings/capture latency is 83.281 s versus the prior 120.985 s;
capture family audits fall 110 → 42 and snapshots 106 → 37. Other independently
owned source changes were captured between snapshots, so the whole timing gain
is not attributed exclusively to this patch. The same-revision microbenchmarks
are recorded separately. Latency remains significant; P1 is not wholly complete.
The simulated stage 5 still waits for review. The separate versioned 8 fps
operating policy, mode/control assessment, freshness and physical qualification
remain next camera tasks. No physical device access or arm change occurred.

### Camera-only mode review guidance — 2026-09-12

The [mode-review guidance work order](CAMERA_MODE_REVIEW_GUIDANCE_WORKORDER.md)
records the first P5 presentation slice. Camera settings now distinguish the
full-resolution 9 fps reference, an 8 fps variance requiring policy review,
other reported modes and absent observations. Required manual-control support,
intent and readback are shown separately in browser and terminal. No mode is
selected or approved automatically; original evidence and admission are unchanged.
Frontend rational readback comparison now matches the native comparator while
retaining dimension/format/stride and malformed-input rejection.

The frozen selected regression passed **242 cases**, zero skips, with matching
input/source audits on `3fd50951f5f89f8c37132a522c053df1730949745723ba267fb1c033f6dbbb5d`.
This includes 36 new guidance/frontend cases; the initial 118-case run is a subset,
not additive. The full original-history lane was not rerun. This is not P5 closure:
an approved versioned operating profile and original-bound stage-5 assessment/
operator-review event remain separate work. No physical device or arm action ran.

### Camera-only operating proposal and evidence preflight — 2026-09-12

The [operating-evidence work order](CAMERA_OPERATING_EVIDENCE_PREFLIGHT_WORKORDER.md)
adds a pure backend, not a wizard approval route. An explicit proposal binds the
selected settings and exact rational mode to purchase bytes and mode-entry
context. An 8-fps variance requires its own rationale; the 9-fps purchase reference
is preserved. Native probe and two capture/readback subjects are reconstructed
using existing legacy/v2 verifiers. Missing manual exposure/white balance,
duplicate attempts, mismatching readback, cleanup failure and changed runtime or
layout remain blocked. A consistent result still carries no physical authority.

The scoped software-contract snapshot passed **474 cases**, including 82 new
tests, with no failures/errors/skips and unchanged input hashes. Two attempted
full snapshots caught concurrent shared/arm edits and remain preserved but
unaccepted. This reduced test scope is not full-workspace or original-history
acceptance. No arm file, UI route, native helper, purchase profile or device was
changed/accessed by this increment. P5 remains open: original-store publication,
USB/reopen/pixel joins, a separate reviewed policy event and wizard integration
are next. Installed optics, calibration and stage-6 freshness remain separate.

### Camera-only logged operating proposal in the wizard — 2026-09-12

The [proposal wizard work order](CAMERA_OPERATING_PROPOSAL_WIZARD_WORKORDER.md)
implements an explicit draft action after current mode-entry/settings context.
It records rationale and the 8-fps exception rationale when applicable, checks
ticket/context/owner consistency and final log/Stop/deadline conditions, and
shows a bounded DRAFT ONLY projection in browser and terminal. Normal diagnostic
exports include retained proposal drafts and completion outcomes. No settings
are applied, no device is opened and a fresh launch restores no current draft.

The isolated 16-module selection passed **605 cases**, including 37 new cases,
with no failures/errors/skips and unchanged copied input/source hashes. Omitted
fixture dependencies in an earlier reduced snapshot were supplied to a new copy;
no assertions were weakened. The detailed ledger preserves those failed runs.
This is camera-draft integration only, not full original-history, arm or physical
acceptance. P5 remains open: original-owner proposal/assessment retention and
readback, USB/reopen/pixel joins and a separate operator-review event are next.

### Camera-only original operating-evidence assessment — 2026-09-12

The [original assessment work order](CAMERA_ORIGINAL_OPERATING_ASSESSMENT_WORKORDER.md)
connects the logged draft to the original setup/configuration readers under
existing camera-session ownership. The operator explicitly selects up to two
saved settings captures. Native evidence, saved permits/results/admission settings
and reconstructed readbacks feed the existing preflight; missing evidence remains
held. A dedicated diagnostic export retains assessment history and log outcomes.
No device, settings write, stage transition, original-stage record or operating
approval is introduced. Fresh applications restore no assessment permission.

The isolated batch executed 632 cases with unchanged input/source hashes: **630
passed and two shared inventory-contract tests failed**, zero skips/errors. All
27 new camera cases passed, including real M1 readback with modeled predecessors,
service ownership, two saved tiny captures, wizard logs/export/fresh instances and
inert browser form/navigation. The two inventory failures are documented, not
silently omitted or counted as passing. This is not full regression acceptance.

P5 remains in progress: canonical proposal/assessment original-stage persistence,
readback/restart and a separate review event still need integration, along with
USB/reopen/pixel/freshness joins. The full original-history lane was not rerun.
Static task migration and installed optics/calibration remain separate work.

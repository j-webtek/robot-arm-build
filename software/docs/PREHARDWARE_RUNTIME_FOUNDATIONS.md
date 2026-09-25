# Pre-hardware runtime foundations

## Purpose and present status

This guide explains how the current RoCell software fits together before the
RoArm-M3 Pro and Arducam B0477 are available for integration. The software can
compile keyboard and Android text, exercise camera and controller-shaped
boundaries, simulate perception and contact, preserve restart state, and reject
inconsistent evidence. It cannot establish physical accuracy or authorize
power, motion, a key press, or a screen tap.

The controlled baseline is
`ROCELL-PHASE0-RC03-INT-R1-FREEZE-011`, active build
`2026-09-01_CELL-A`. Freeze 009 remains immutable in its archive. Freeze 010
source-locked the regenerated RC03 package and recorded the static-overhead
B0477 selection conflict as an engineering alignment hold; active Freeze 011
retains that hold while correcting a build-workflow dependency. The canonical
manifest and simulation profile therefore still contain legacy arm-camera
fields. The additive B0477 services are the selected Phase-1 simulation path,
not a physical camera release or a silent promotion of those fields. A later
controlled revision must reconcile the received hardware, measurements,
software identities, and release evidence.

The selected Phase-1 candidate is the purchased Arducam B0477 / Sony IMX283 /
included nominal 16 mm manual-focus lens in a rigid static overhead mount. The
current support candidate places the entrance pupil nominally at board-frame
`B=(305, 228.5, 1000) mm`, with the 950--1050 mm height interval retained for
screening. Those dimensions are hypotheses until the received camera, lens,
mount, workcell, field of view, focus, and collision clearances are measured.

## How the foundations connect

```text
exact source files + Freeze-011 manifest + simulation bundle lock
                              |
                              v
               revalidated SimulationContext
                              |
operator text -> exact ActionPlan -> semantic-step schedule
                         |              |
                         |              +-> observation-only phone-state steps
                         v
             contact-requesting semantic occurrences
                         |
nominal targets -> accepted dense route -> 47/60 non-wire targets for test/test.
                         |                    |
                         |                    +-> endpoint + joint-midpoint collision
                         |                    +-> final-HOVER B0477 observation/contact
                         v
               durable per-contact journals
                         |
15-artifact NOMINAL_ONLY closure + isolated collision fixture
                         |
                         v
              authorization-v2 exact command suffix
                         |
                         v
                  additive mission V2
 non-wire T104 runtime -> achieved virtual contact -> independent outcome
                         -> retract -> final park -> report

             every implemented path remains zero physical authority
```

There are now three complementary execution paths:

- `virtual_session.py` is the mature geometry-rich simulator. It compiles the
  semantic plan, plans joint waypoints, runs synthetic fixed-overview vision,
  resolves geometry-based virtual contact, observes the virtual outcome, and
  supports immutable replay through its direct application path.
- `multi_action_mission.py` is the newer crash-aware orchestration kernel. It
  consumes a complete `MissionRuntimePorts` bundle, durable journals, and a
  required ordered authorization cursor, but its commands and device payloads
  are canonical opaque bytes.
- `integrated_zero_hardware_mission.py` is the additive dense V2 rehearsal. It
  binds the real semantic plan and accepted dense trajectory to one non-wire
  controller target per commanded waypoint, a fresh synthetic B0477 report at
  each contact's final hover, endpoint and exact joint-midpoint collision
  results, authorization-v2, per-contact journals, achieved virtual contact,
  and independent virtual outcome verification. It also revalidates the
  accepted trajectory from current source bytes and retained joint solutions,
  keeps state observations as mandatory chronological prerequisites, and
  replay-checks the complete retained command/trace/contact evidence.

V2 closes the former zero-hardware assembler gap without changing V1 or
creating a physical executor. Its controller target has no wire encoder or
transport, its `R_ctrl` relationship is uncommissioned, its calibration
closure remains `NOMINAL_ONLY`, and its 26-body collision input is an explicitly
isolated software-binding fixture with `physical_clearance_established=false`.
It runs directly against the non-wire emulator rather than commissioned
`MissionRuntimePorts`. A pass in one execution path still does not imply that
the other paths ran.

## 1. Configuration and source locks

The software starts from controlled inputs, not ad hoc runtime defaults:

- `config/system_manifest.json` identifies Freeze 011 and the active build.
- `config/simulation_bundle_lock.json` hash-locks the simulation hardware
  profile, nominal targets, arm-frame contract, camera manifest, virtual
  commissioning profile, and pinned local RoArm URDF.
- `application/context.py` resolves those paths beneath the selected workspace,
  reloads their exact bytes, and rejects a context that differs from a fresh
  canonical load.
- `hardware/static_overhead_camera/config/support_design.json` separately
  source-locks the additive B0477/support design inputs and is checked by the
  static-support validator. Its layout lock now matches the current RC03
  `workcell_layout.json`; the complete B0477 coherence gate passes against that
  repaired source graph while retaining zero physical authority.

These hashes are valuable drift and corruption checks. They are not signatures
and do not authenticate a hostile filesystem or hostile process. Physical
release eventually needs protected source distribution, controlled signing or
an equivalent trust anchor, and an independently protected monotonic release
record.

## 2. Physical-shaped onboarding without hardware

`application/physical_shaped_onboarding.py` rehearses the future acquisition
order through one module-issued deterministic fake provider. Its ten stages
are:

1. inspect and bind the received-camera record;
2. enumerate by persistent identity and select exactly one camera;
3. apply the exact UVC mode/controls and verify readback;
4. flush buffers and prove fresh, advancing, distinct frames;
5. close/reopen and reprove identity plus configuration;
6. acquire retained-install calibration frames with a fixed training/held-out
   split and mount/light/focus/aperture/cable witnesses;
7. inspect the RoArm identity while power is reported off;
8. collect the complete pre-power safety-evidence shape;
9. observe the first power event with zero commands; and
10. perform one identity-bound `T=105` request, strictly parse the retained
    `T=1051` bytes, then account and clean up.

The request/receipt objects bind run, camera session, persistent identity,
configuration, arm identity, retained bytes, and evidence hashes. The
safety/power/feedback tail is one exact chain: safety-observation hash -> power
request/observation hashes -> synthetic controller-session identity ->
session-bound empty-input-buffer observation -> `T=105` request context and
retained `T=1051` receipt. Every link is recomputed and carries explicitly
untrusted synthetic sequence material to reject cross-run, cross-stage, or
substituted evidence inside the deterministic rehearsal. It is not a physical
clock, hardware attestation, or cryptographic authentication service.

The fake bundle accepts only the exact factory-issued fake type and exposes no
`T=104`, raw-write, motion, or contact method. This prevents accidental adapter
substitution at the ordinary API boundary; it is not an OS sandbox and Python
reflection is not a security boundary. Real providers must therefore be added
as a separately reviewed physical-acquisition workflow, not injected into this
fake runner or enabled with a boolean flag.

The broader `rehearse-first-power-on` command remains the operator-facing
15-stage simulation. See [First-power-on onboarding](FIRST_POWER_ON_ONBOARDING.md)
for its checkpoint and procedure contract.

## 3. Static B0477 optical, pixel, and replay chain

The B0477 chain keeps every pixel space explicit:

1. `b0477_optical_contract.py` builds the single canonical synthetic projection
   in `C_overhead_optical`, preserves the published field-of-view claims as
   provenance, and binds an analytic Brown-Conrady distortion/undistortion map.
2. `b0477_static_vision.py` renders synthetic distorted-proxy capture pixels.
   The bounded detector sees JPEG bytes only; it does not receive pose, tag
   corners, target identity, or scene truth.
3. Raw detections are accepted only in
   `B0477_SYNTHETIC_DISTORTED_PROXY_PIXELS`. They are rectified exactly once
   into `UNDISTORTED_PINHOLE_PIXELS`. Typed provenance rejects a raw batch sent
   to the estimator, stripped provenance, or double rectification.
4. Pose is fit from board tags T0--T3. K0 and P0 are withheld from that fit and
   checked afterward as independent station residuals. The nominal rehearsal
   also checks exact visible IDs, no unexpected IDs, reprojection RMSE,
   translation error, rotation error, and held-out corner/RMSE thresholds.
5. `b0477_sensor_session.py` bridges that capture into the generic raw
   sensor-session v2 package. It retains bounded YUY2 raw bytes, RGB8 decoded
   and rectified rasters. Pixel-buffer layout schema v2 pins the full-range,
   JPEG-derived BT.601 YCbCr and sRGB semantics, chroma siting, and row origin,
   detector-input JPEG, raw and rectified detections, pose records, exact
   camera mode/controls, timing brackets, source/calibration hashes, and an
   unsent synthetic feedback fixture.
6. `evidence/sensor_session.py` writes an exact-file, content-addressed,
   manifest-last package. Verification rejects missing, extra, reordered,
   oversized, noncanonical, stale, or hash-mismatched material. The B0477
   wrapper additionally exact-compares the replayed package with the originating
   B0477 source session.

The published full-resolution mode fixture is 5472 x 3648 YUY2 at 9 fps. The
pixel/replay simulation deliberately uses its one-half-scale 2736 x 1824 proxy
to stay inside bounded raster and detector limits. Neither is a promise about
the received unit: physical onboarding must enumerate actual modes, select one
controlled mode, and reject silent driver fallback.

Package verification establishes internal byte, schema, identity, and hash
consistency. Even source-bound B0477 replay does not independently prove that
the decoder, undistortion, detector, pose estimate, covariance, or calibration
is correct for the physical scene. A recorded-data verifier that recomputes
those derived products from retained physical raw input remains required.

## 4. Additive static-B0477 route-collision diagnostic

`simulation/static_route_collision.py` composes the historical primitive
collision evaluator without changing it. Its contract is specific to the
static-overhead B0477 workcell and requires an exact SHA-256 source closure for
nine named inputs: `robot_model`, `workcell_layout`, `target_profile`,
`static_support_design`, `b0477_mechanical_design`,
`fixed_usb_route_design`, `lighting_design`, `arm_harness_design`, and
`contact_tool_design`. These are caller-supplied, unkeyed content bindings;
they detect inconsistency but do not authenticate the files or their author.

The exact required inventory is 26 collision bodies:

| Scope | Required body IDs | Count |
| --- | --- | ---: |
| RoArm, contact tool, and moving harness | `robot:base_link`, `robot:link1`, `robot:link2`, `robot:link3`, `robot:link4`, `robot:link5`, `robot:gripper`, `robot:contact_tool`, `robot:tool_tip`, `attachment:arm_harness` | 10 |
| Board and devices | `workcell:board`, `installation:base_clamp`, `workcell:keyboard`, `workcell:phone` | 4 |
| Static support | `support:portal_left_post`, `support:portal_right_post`, `support:portal_crossbar`, `support:camera_boom`, `support:lighting_boom_left`, `support:lighting_boom_right` | 6 |
| Camera, fixed cable, and lights | `camera:b0477_enclosure`, `camera:b0477_lens`, `camera:b0477_connector`, `cable:fixed_usb_route`, `lighting:key_light_left`, `lighting:key_light_right` | 6 |

Every required body must have geometry usable by the diagnostic. `MISSING`
geometry blocks evaluation. `CONSERVATIVE_SYNTHETIC` geometry can support only
a synthetic diagnostic, while received and installed envelopes still have to
be measured and accepted. The moving `attachment:arm_harness` is
`CONFIGURATION_SAMPLED`: the caller must supply its geometry independently at
every evaluated phase and intermediate pose. The service deliberately does not
interpolate deformable harness geometry from segment endpoints. The fixed
overhead USB route is a separate static-root body.

Each target route has exactly seven phase entries in this order:

```text
PARK -> TRANSIT -> HOVER -> APPROACH -> CONTACT -> RETRACT -> PARK
```

It also has exactly six adjacent segments, `0->1`, `1->2`, `2->3`, `3->4`,
`4->5`, and `5->6`. Every segment must contain a bounded set of caller-supplied
intermediate poses; the default policy accepts 1--16 and requires an exact
midpoint sample at interpolation fraction `0.5`. A clear endpoint pair does not
excuse a colliding midpoint. These are discrete checks, not a continuous
collision proof.

Global pair exclusions are forbidden, including otherwise conventional
adjacent-link exclusions, because a global exception could hide a collision on
another phase or sample. The sole allowed overlap is the exact normalized pair
`robot:tool_tip` plus the route's designated `workcell:keyboard` or
`workcell:phone` body, only at the CONTACT phase endpoint. APPROACH, RETRACT,
and all intermediate samples receive no contact allowance; any other pair at
CONTACT still fails. The target binding also carries the semantic target-region
and target-profile hashes, and the CONTACT tool-tip origin must lie within the
policy tolerance of that bound target center. The default policy requires the
designated overlap to occur.

The frozen unit fixture exercises all 75 nominal targets--46 keyboard targets
and 29 phone targets--with seven phase results and six independently evaluated
midpoint-bearing segment results per target. Those fixtures return
`PASS_DIAGNOSTIC_ONLY` using conservative synthetic geometry. This establishes
contract behavior and nominal-catalog coverage, not clearance of a measured
arm, support, lens, cable, keyboard, phone, or route.

The additive dense adapter in `simulation/static_mission_route.py` now binds
the final accepted trajectory to V2 command ordinals and evaluates every dense
endpoint plus one exact 0.5 joint-interpolated midpoint for each incoming
segment. `simulation/static_mission_fixture.py` supplies the complete 26-body,
nine-source shape solely by isolating unknown links, attachments, support, and
cable geometry far from the modeled route. That fixture lets the binding,
ordering, intended-contact exception, and query code execute; it deliberately
cannot establish workcell clearance.

`multi_action_mission_v2.py` binds each command to those collision results and
authorization-v2 evidence. This is an additive V2 contract, not a retrofit of
the V1 `MultiActionMissionSpec` or the legacy geometry-rich session executor.
All reports retain `simulation_only=true`, `hardware_commands_generated=0`,
and false physical-gate, motion, contact, and clearance authority. Physical
geometry, continuous/swept clearance, dynamics, deflection, force, payload,
and unmodeled cable motion all remain required physical gates.

### 4.1 Placemat geometry sensitivity

`application/placemat_uncertainty.py` answers whether the software is consuming
the current RC03 geometry and how nominal target centres respond to bounded,
assumed geometry error. It revalidates active Freeze 011, the 610 x 457 x
18 mm board, keyboard and phone envelopes, all 46 keyboard and 29 phone target
regions, the repaired static-support contract, and the purchased B0477 profile.
The B0477/support binding identifies the selected static architecture; this
geometry study does not render pixels or measure device pose.

The default inputs apply +/-1.0 mm XY, +/-0.5 mm Z, and +/-0.2 degree yaw to
board registration and each device placement; +/-0.5 mm XYZ to each local
target map; and +/-0.75 mm XYZ to the TCP. The generator evaluates nominal,
signed one-axis, and combined device-corner cases: 59 cases x 75 targets =
4,425 observations. The current deterministic result observes no sampled gap
for the 46 keyboard targets and a sampled gap for 27 of 29 phone targets, with
worst XY safe-region margins of +2.7525 mm and -0.7560 mm respectively. The
zero-bound control evaluates 75 nominal observations with no gap.

These values are `ASSUMED_UNMEASURED_SENSITIVITY_BOUNDS`, not distributions,
manufacturing tolerances, calibration limits, safety margins, or physical
evidence. Consequently the default run is useful when it reports gaps;
`--require-no-gaps` is appropriate for the zero-bound control and intentionally
returns nonzero on the current default matrix. See
[Placemat geometry sensitivity simulation](PLACEMAT_GEOMETRY_SENSITIVITY.md)
for the complete model, results, and hardware substitution rules.

## 5. Calibration graph and registry

The static Phase-1 dependency graph contains 15 artifacts in five groups:

- B0477 identity, exact mode, retained settings, and static intrinsics;
- measured tag map and static camera-to-board extrinsic;
- RoArm reference, controller/model correlation, and arm-to-board transform;
- keyboard target map, keyboard TCP/contact behavior, and keyboard outcome
  observer; and
- phone target map, phone TCP/contact behavior, and phone outcome observer.

Keyboard and phone authorization each require their exact ordered 12-artifact
closure, including every declared parent hash and external context hash. A
single nominal or otherwise valid-looking artifact is insufficient.

`calibration_closure_from_registry()` is the intended authorization-v2 adapter.
It asks the real `CalibrationRegistry` to resolve the exact capability closure,
requires every artifact to be `VALID` for the selected manifest/build, reloads
the current artifacts, and independently checks every modeled parent and
context field before snapshotting their hashes. It rejects caller-assembled
partial closures, missing or non-valid artifacts, and extra/unmodeled graph
relationships.

`calibration/registry.py` provides bounded canonical reads, immutable
content-addressed artifacts, atomic index publication, append-only publication
receipts, a unique linear version history, rollback/missing-head detection,
path containment including Windows reparse escapes, and transitive parent
assessment. `NOMINAL_ONLY`, stale, invalid, missing, or context-mismatched
artifacts do not become physical calibration authority.

The current physical registry is intentionally empty. The in-memory rehearsal
constructs only `NOMINAL_ONLY` substitutes to exercise all graph edges. The
registry's unkeyed hashes and local publication history detect inconsistency;
they do not prove authorship or survive a fully hostile filesystem that can
rewrite all files coherently. Physical use needs an external protected anchor
or signature policy.

## 6. Semantic keyboard and Android plans

The typing compilers translate normalized text into semantic actions before
coordinates are considered:

- `KeyboardCompiler` emits named `PressKey` actions using the locked keyboard
  semantic profile.
- `PhoneCompiler` emits named `TapPhoneTarget` actions plus explicit
  `VerifyPhoneState` actions. A tap's predicted state is never treated as
  observed state.
- `ActionPlan` binds device, profile, normalized-text hash, action order, and a
  stable plan hash. Unsupported characters fail at compilation.
- `targets/nominal.py` resolves the current simulation-only 46 keyboard and 29
  phone target regions and verifies their semantic-profile bindings.

The nominal target regions are test seeds, not measurements of the received
keyboard or Android phone. Physical target maps must bind the exact device,
layout/IME/UI state, board transform, safe polygons, surface height/normal,
tool footprint, uncertainty, and held-out residuals.

`semantic_step_schedule.py` preserves four separate order domains instead of
conflating intent with motion. Every source action has a semantic-step ordinal;
only `PressKey` and `TapPhoneTarget` receive contact-occurrence ordinals;
accepted route waypoints retain route ordinals; and only waypoints after the
known initial park receive global authorization-command ordinals.
`VerifyPhoneState` remains an observation. It owns no contact, route command,
authorization command, or journal.

## 7. Action occurrence and durable journal

Repeated letters are separate physical-risk events. `ActionOccurrence` hashes
the mission ID, complete plan hash, action ordinal, and canonical action hash,
so the two `t` actions in `test` cannot share an occurrence ID.

Each occurrence has its own append-only, canonical, hash-chained journal:

```text
INTENT_COMMITTED -> PRE_CONTACT -> CONTACT_MAY_HAVE_OCCURRED
    -> OUTCOME_CONFIRMED -> RETRACTED -> PARKED

before possible contact: FAULTED
after possible contact without proof: OUTCOME_UNCERTAIN
```

The journal publishes a file-flushed high-water record for the exact tail,
directory-syncing publication where the platform supports it, and permanently
records whether the contact boundary was ever committed.
The mission kernel commits `CONTACT_MAY_HAVE_OCCURRED` before submitting the
contact-producing command. Consequently a crash after that boundary can never
be interpreted as `NOT_STARTED`, and contact is never retried automatically.
Missing, truncated, duplicated, reordered, cross-plan, or tampered journal
material fails closed.

Recovery is deliberately narrow:

- `INTENT_COMMITTED` or `PRE_CONTACT`: pre-contact work may be rerun after
  fresh gates and a newly issued remaining-suffix authorization.
- `CONTACT_MAY_HAVE_OCCURRED`: independently observe the outcome; do not
  repeat contact. The fresh semantic observation must retain nonempty contact
  event IDs before retraction can proceed.
- `OUTCOME_CONFIRMED`: obtain fresh state and perform only the authorized
  retract.
- `RETRACTED`: park only after current checks.
- `FAULTED` or `OUTCOME_UNCERTAIN`: manual review; no automatic contact.
- `PARKED`: no command remains.

## 8. Ordered authorization v2

`safety/authorization_v2.py` replaces permissive booleans and unordered goal
hashes with a simulation-only evidence context. It binds:

- arm, controller, firmware, persistent port, and connection-session identity;
- active build, manifest, and an evidence-only release receipt;
- the exact keyboard or phone static-calibration closure, preferably resolved
  directly through `calibration_closure_from_registry()`;
- a collision report to the exact ordered simulated trajectory;
- device state, operator-arm nonce, semantic plan, action occurrences, and
  command occurrences; and
- source identity, sequence, time, state, and raw hash for E-stop,
  board anti-shift, gravity containment, and contact-guard channels.

Issuance creates an `OrderedSimulationPermit`. The mission adapter exposes it
as an `AuthorizationV2MissionCursor` for exactly the safe command suffix implied
by the journals. Before every hover, approach, contact, retract, or park send,
the cursor requires the next absolute phase/occurrence/payload/constraint hash,
fresh continuity evidence, and advancing interlock samples. It consumes that
entry once and returns a receipt which the mission report binds to the executed
boundary. Skips, duplicates, reordering, mutation, drift, expiry, stale or
future samples, and missing authority all revoke or reject the cursor.

A fully `PARKED` journal set is the sole zero-command case and uses
`CompletedMissionAuthorizationCursor(plan_sha256)`. Every nonempty remaining
suffix requires the concrete authorization-v2 cursor; a structurally similar
custom cursor or a naked `OrderedSimulationPermit` is rejected.

This is a behavioral design, not a security authority. Its clock is supplied
by the simulation caller; its factory seals and frozen objects live in the same
Python process; and privileged reflection can bypass normal object discipline.
A physical implementation needs an isolated service, a service-owned trusted
clock, signed/protected evidence, an append-only cursor ledger, exclusive
transport ownership, and a separately reviewed receipt format.

The cursor always reports `can_authorize_live_transport == false`. It cannot be
passed to the live RoArm transport, and it cannot generate a firmware wire
command.

`safety/synthetic_authorization.py` supplies the deterministic V2 rehearsal
bridge. It projects only the exact static Phase-1 synthetic closure while
preserving every artifact's `NOMINAL_ONLY` state, constructs the ordered
simulation evidence, and advances synthetic interlock continuity for one
command at a time. Its fixed logical time, in-process seals, and unkeyed hashes
are test controls, not security or physical authority.

## 9. Multi-action runtimes, outcomes, and cleanup

`run_zero_authority_multi_action_mission` requires four inputs: a validated
`MissionRuntimePorts` bundle, immutable mission spec, exact journal set, and a
typed authorization cursor. Naked permits and missing cursors are rejected.

The nominal action order is:

1. validate every runtime port and its zero-authority metadata;
2. connect and reference the deterministic virtual/replay controller;
3. poll cancellation/preflight, read pre-motion feedback, and obtain a fresh
   observation;
4. bind route evidence, then authorize and execute hover and approach;
5. durably commit pre-contact and possible-contact journal boundaries;
6. authorize and execute contact, sample feedback, and ask the virtual device
   model to resolve one activation;
7. use a separate outcome-observer port to return an occurrence-bound semantic
   outcome and exact contact-event IDs;
8. commit the outcome, authorize retract, confirm achieved feedback, then
   journal retraction;
9. after all actions retract, authorize one park, confirm feedback, and mark
   every action parked; and
10. always attempt stop, close, final port validation, and final journal
    validation.

The report is factory-issued and cross-validates record order, failures,
outcome receipts, authorization receipts, final journals, and zero hardware
counters. Outcome receipts bind checkpoint, sequence, observed time, action
occurrence, semantic hash, and nonempty contact-event IDs to the matching
journal transition. A primary fault stops all later contacts. Cleanup faults
are retained separately so stop/close/reporting problems cannot erase the
original failure. Park is attempted only when journal/retraction state proves
it conservative and park is already the cursor's next authorized command; the
cleanup path never skips outstanding action commands to reach park.

The device-contact port remains virtual/replay truth, not a physical contact
API. A physical executor will need continuously monitored motion and contact
telemetry; achieved feedback plus bounded settling; overforce/overtravel and
premature/stuck-contact guards; and independently observed keyboard/Android
state after retraction.

The additive V2 path retains the same conservative intent while executing the
dense schedule. The accepted keyboard `test` route has 48 waypoints and 47
commands; Android `test.` has 61 waypoints and 60 commands. The initial park is
a checked starting condition, not a command. The missions contain four and
five simulated contact occurrences respectively. Before each contact, V2
requires the matching final-HOVER B0477 evidence and consumes the exact next
authorization entry; before submitting the contact-producing emulator target,
it durably commits `PRE_CONTACT` and `CONTACT_MAY_HAVE_OCCURRED`. A fault after
that boundary becomes `OUTCOME_UNCERTAIN`, and opening those journals never
authorizes automatic contact retry. Successful missions independently resolve
the virtual output, retract, execute the unowned final route tail, park every
journal, and retain zero hardware counters. Android state observations must be
present and passing before any later motion, camera, contact, or mission-tail
receipt; a later state-fault claim is rejected if an intervening contact has not
completed and durably retracted.

The controller fault injector is part of the deterministic non-wire runtime.
The B0477 fault injector is sealed into the immutable mission assembly, so its
selected contact is a global boundary that no command, camera, or contact
receipt may cross. Top-level capture-area causality is intentionally coarse:
`SettledHoverObservationBoundary` / `OBSERVATION_BOUNDARY_FAILURE`. A nested
typed B0477 `CAPTURE_FAILURE`, `TIMEOUT`, or `STALE_FRAME` receipt is retained
when available, but is serialized as `UNAUTHENTICATED_DIAGNOSTIC_ONLY`; this
zero-hardware report has no secret authenticity anchor that could prove a more
specific persisted cause. Human-readable exception text is also descriptive,
not causal evidence.

From the workspace root, run the acceptance pair with a different new,
nonexistent journal directory for each initial run:

```powershell
rocell --workspace . simulate-integrated-v2 --device keyboard --text "test" --journal-root .\software\runs\integrated-v2-keyboard-local-001 --require-pass --json
rocell --workspace . simulate-integrated-v2 --device phone --text "test." --journal-root .\software\runs\integrated-v2-phone-local-001 --require-pass --json
# Expected fail-closed run: the stale-frame schedule is assembly-bound and
# stops at contact occurrence zero's settled final HOVER, before approach.
rocell --workspace . simulate-integrated-v2 --device keyboard --text "test" --journal-root .\software\runs\integrated-v2-camera-fault-local-001 --camera-fault-kind stale-frame --camera-fault-contact-ordinal 0 --require-pass --json
```

The journal directories persist intentionally. `--open-existing` accepts only
the exact assembly-bound journal set and still refuses automatic execution if
any contact journal has advanced beyond `INTENT_COMMITTED`. Deterministic
non-wire controller failures can be exercised with `--fault-kind` and the
zero-based `--fault-command-ordinal`; the resulting journal state, rather than
the requested retry, controls recovery. Camera and controller fault injection
cannot be selected together in one run.

Per-contact journals do not yet provide a mission-global dispatch high-water
mark for transit and HOVER commands. Abrupt process recovery at those boundaries
therefore remains a physical-adapter blocker. Two internal integrity cases are
also deliberately fail-closed but report-unavailable: a command receipt wrapper
can fail after the emulator has advanced, or a contact receipt wrapper can fail
after virtual outcome application. Both paths terminalize every journal and
refuse reopen/retry before raising. A physical executor must add a durable global
dispatch ledger plus lower-level partial-attempt/effect receipts before these
boundaries are allowed to control hardware.

## What a green pre-hardware run means

| Green result | What it establishes | What it does not establish |
| --- | --- | --- |
| Source/context validation | Selected local inputs match their locked bytes | Hardware identity or malicious-filesystem authenticity |
| B0477 normal/tag-loss rehearsal | Synthetic optical/pixel contracts accept and reject the intended fixtures | Physical focus, distortion, lighting, timing, detection accuracy, or support rigidity |
| Sensor-session replay | Exact bounded package bytes and source bindings replay consistently | Independent perception truth or physical calibration |
| Placemat geometry sensitivity | Active Freeze-011 geometry, all 75 nominal targets, and the additive B0477/support bindings are revalidated while deterministic assumed displacements expose target-region sensitivity | Measured placement/TCP uncertainty, camera visibility, IK, collision freedom, contact reliability, or a physical pass/fail result |
| Static B0477 route-collision diagnostic | The additive 26-body, nine-source contract and synthetic fixtures exercise all 75 nominal targets through seven phase endpoints, six midpoint-bearing adjacent segments, per-pose harness geometry, and CONTACT-local overlap rules | Measured geometry, continuous collision freedom, dynamics, or physical motion/contact clearance |
| Integrated dense mission V2 | The semantic/contact/route/authorization joins, mandatory state-observation prefix, per-contact B0477 binding, endpoint/midpoint collision queries, exact non-wire command order, precommitted fault boundary, journal boundary, virtual outcome, receipt replay, and final park execute together | Sendable T=104, authenticated fault provenance, mission-global dispatch recovery, commissioned frames, measured collision clearance, physical camera freshness, physical calibration, or live motion/contact authority |
| Calibration rehearsal | The full dependency graph and invalidation rules are exercised | Any measured artifact or physical closure |
| Journal/restart tests | Simulated crash states cannot justify an automatic duplicate contact | Filesystem durability under every real power-loss/storage failure |
| Authorization-v2 tests | Exact simulated command order and evidence-continuity rules are enforced | In-process adversarial security or permission to use live transport |
| Multi-action mission pass | Generic virtual/replay ports execute, observe, retract, park, and account cleanly | Integrated physical routes, contact mechanics, or a live RoArm command |

## Focused verification

From `software/` in PowerShell:

```powershell
python -m pytest tests/unit/test_models_and_typing.py tests/unit/test_targets.py -q
python -m pytest tests/unit/test_b0477_optical_contract.py tests/unit/test_b0477_static_vision.py tests/unit/test_b0477_sensor_session.py -q
python -m pytest tests/unit/test_placemat_uncertainty.py -q
python -m pytest tests/unit/test_static_route_collision.py -q
python -m pytest tests/unit/test_calibration_registry.py tests/unit/test_physical_shaped_onboarding.py -q
python -m pytest tests/unit/test_mission_journal.py tests/unit/test_authorization_v2.py tests/unit/test_multi_action_mission.py -q
python -m pytest tests/unit/test_semantic_step_schedule.py tests/unit/test_dense_route_schedule.py tests/unit/test_t104_runtime.py -q
python -m pytest tests/unit/test_static_mission_route.py tests/unit/test_synthetic_authorization.py tests/unit/test_integrated_zero_hardware_mission.py -q
python -m mypy src
python -m compileall -q src
```

The higher-level zero-hardware checks are:

```powershell
$env:PYTHONPATH = (Resolve-Path src).Path
python -m rocell rehearse-b0477-stack --require-pass --json
python -m rocell simulate-b0477-vision --mode normal --require-expected --json
python -m rocell simulate-b0477-vision --mode tag-loss --require-expected --json
python -m rocell rehearse-first-power-on --scenario nominal --require-expected --json
python -m rocell workcell --json
# Default assumed bounds intentionally expose phone-target sensitivity gaps.
python -m rocell stress-placemat-geometry --json
# Zero-bound control: all 75 nominal target centres must remain in-region.
python -m rocell stress-placemat-geometry --zero-bounds --require-no-gaps --json
python tools/validate_static_camera_support.py --json
python tools/validate_build_alignment.py
```

Run the complete suite with `python -m pytest tests`. Slow deterministic
campaigns remain opt-in; use the documented environment flags rather than
assuming they ran as part of a default invocation.

## Physical-only gates that software must not waive

The following remain blocked until hardware is present and measured:

- received B0477, sensor, lens, enclosure, cable, USB identity, supported mode,
  control persistence, one-metre focus, aperture/focus locking, and image
  orientation;
- support dimensions, retention, deflection, vibration, warm-up drift,
  lighting, cable loading, full field of view, tag pixels, glare, occlusion, and
  the complete gantry/arm/tool/cable collision envelope;
- physical intrinsics/distortion, measured tag corners/plane, static extrinsic,
  independent held-out station checks, and drift/reseat limits;
- received RoArm/controller/firmware identity, exclusive serial ownership,
  actual startup motion, E-stop, gravity containment, anti-shift, power-loss
  behavior, and controller-to-URDF/frame correlation;
- measured board-to-arm transform, tool TCP/compliance, contact travel/force or
  qualified proxy, settling, route clearance, and recovery thresholds;
- measured keyboard and phone targets, device identity/UI state, activation
  behavior, and independent host/Android outcome observers; and
- a controlled successor to active Freeze 011 that explicitly releases each required
  capability. Passing simulation must never create that release.

## First hardware substitution sequence

Use the existing schemas as acceptance contracts, but substitute hardware in
small, one-way steps:

1. Photograph and measure the received B0477/lens/case/cable. Record serial,
   VID/PID, persistent OS path, mount interfaces, and differences from the
   purchase profile. Keep the RoArm unpowered.
2. Build and inspect the static support, positive retention, strain relief,
   lighting, and cable route. Update only additive design inputs; do not edit
   active Freeze 011 or any archived freeze in place.
3. Implement a separate read-only UVC acquisition adapter with OS/device
   permissions that cannot open serial. Enumerate all real modes and controls,
   select the controlled configuration, flush/capture/reopen/reboot, and record
   raw sessions.
4. Recompute decoding, intrinsics/distortion, undistortion, AprilTag detections,
   T0--T3 pose, and K0/P0 held-out residuals from retained physical images.
   Install accepted camera/tag/static-extrinsic artifacts only through the
   reviewed physical calibration process.
5. With power still off, identify the RoArm/controller/firmware/port and prove
   exclusive ownership. Complete E-stop, containment, anti-shift, startup
   envelope, gantry, cable, and collision inspections.
6. Observe the first power event with no command. After that evidence is
   accepted, perform one separately authorized feedback-only `T=105` exchange;
   retain exact request/response bytes and close the connection. No `T=104`.
7. Calibrate controller/model correlation, arm-to-board, and both tool TCPs
   through reviewed noncontact and guarded procedures. Measure target maps and
   independently qualify keyboard and Android outcome observers.
8. Replace the V2 synthetic B0477 source, isolated collision fixture, nominal
   calibration projection, and non-wire controller emulator one boundary at a
   time with independently recorded and qualified providers. Re-run the exact
   command, tamper, fault, journal, and restart campaigns without live motion;
   do not route a physical provider through the zero-authority factory.
9. Implement the isolated physical authorization/watchdog/contact-guard and
   bounded executor. Audit it separately from the simulation cursor.
10. Create a controlled successor freeze only after every physical artifact,
    safety gate, route, recovery rule, and operator procedure is accepted. Live
    motion and contact remain unavailable until that release explicitly exists.

Related detail is in the [B0477 integration guide](B0477_CAMERA_INTEGRATION.md),
[placemat geometry sensitivity guide](PLACEMAT_GEOMETRY_SENSITIVITY.md),
[software architecture](ARCHITECTURE.md),
[virtual commissioning contract](VIRTUAL_COMMISSIONING.md), and
[full-body collision foundation](COLLISION_FOUNDATION.md).

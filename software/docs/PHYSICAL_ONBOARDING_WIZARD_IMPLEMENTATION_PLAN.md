# Physical onboarding wizard implementation plan

**Plan ID:** `ROCELL-PHYSICAL-ONBOARDING-WIZARD-002`  
**Planning date:** 2026-09-06  
**Status:** reviewed v2 implementation contract; Phase-0 foundation and the M1
qualified zero-hardware application runtime are implemented, while M2 effect
coordination and every physical provider remain blocked; no physical authority  
**Current build baseline:** `2026-09-01_CELL-A`, active Freeze 011  
**Selected Phase-1 vision:** rigid static-overhead Arducam B0477 / Sony
IMX283 / included nominal 16 mm lens  
**Successful wizard end state:** `COMPLETE_DIAGNOSTIC`, never “ready to type”

This is the implementation roadmap for turning the existing physical-onboarding
backend into a guided, resumable arrival and commissioning wizard. It is a
planning document, not an operator procedure and not a release. The current
commands and physical stop line remain governed by
[Physical onboarding automation](PHYSICAL_ONBOARDING_AUTOMATION.md) and
[First-power-on onboarding](FIRST_POWER_ON_ONBOARDING.md).

The machine-readable Phase-0 contract set is rooted at
[`physical_onboarding_foundation.json`](../config/physical_onboarding_foundation.json).
Those files are strict, source-bound design inputs. They deliberately retain
`runtime_activation: false`; passing their validators cannot open a device,
power or move the arm, promote a build, or release contact.

The M1 application runtime is now implemented separately from the legacy v1
controller. It qualifies its actual local fixed Windows/NTFS deployment root, retains a
stable qualification anchor while repeating the startup self-test, creates
cell-global attempt and quarantine ledgers, enforces ordered OS leases around
its mutations, and creates source-bound v2 diagnostic sessions. Its public
facade exposes no effect method and reports zero device, camera, serial, power,
motion, and contact operations. See
[M1 qualified zero-hardware onboarding runtime](M1_ZERO_HARDWARE_RUNTIME.md).
This closes the core storage integration slice, not the effect-capable M2
coordinator or any physical-arrival stage.

**Connection/UI companion — 2026-09-07:** the
[camera and arm connection integration plan](CAMERA_ARM_CONNECTION_INTEGRATION_PLAN.md)
adds official-software research, concrete Windows provider boundaries, camera
preview/control and arm startup screens, and an ordered implementation queue.
It proposes building the small browser shell alongside the shared service,
while preserving this plan's M2/M12 activation gates, canonical stage ownership,
non-motion wizard boundary, and separate contact releases. It is an
implementation proposal, not a change to the active machine-readable policy.

## 1. Outcome we are building

When the hardware arrives, one controlled launcher should guide an operator
through the exact physical sequence for:

1. verifying the checkout, build, board, static-camera design, dependency
   epochs, authority policy, and unresolved hazards;
2. progressively closing only the hardware-intake rows owned by each stage,
   while inspecting and binding the received B0477 camera and RoArm-M3 Pro;
3. qualifying the camera's real identity, native mode, controls, freshness,
   optics, intrinsics, and static relationship to the placemat;
4. recording power-off safety evidence and every separately permitted actuator
   energization, including supervised first-power observation;
5. making exactly one identity-bound, feedback-only `T=105` query under a new
   energization envelope, with no motion-capable interface and no retry;
6. importing a conservative bootstrap-calibration campaign followed by
   separately permitted reference-calibration and noncontact-motion evidence;
7. closing a conservative keyboard/phone target-error budget; and
8. sealing one independently reviewable, zero-authority
   `CommissioningBundle` diagnostic package.

The wizard will automate verification, bookkeeping, bounded capture, replay,
assessment, and report generation. It will not automate robot mains power,
E-stop operation, initialization, homing, arbitrary serial access, motion,
descent, keyboard contact, phone contact, or release approval.

The system after this plan is implemented will have two deliberately separate
experiences:

- **Rehearsal mode:** fully simulated, visibly watermarked, incapable providers,
  a separate storage namespace, and a terminal result of
  `REHEARSAL_COMPLETE_ZERO_AUTHORITY`.
- **Physical diagnostic mode:** source-bound physical evidence, explicit
  operator/reviewer gates, no automatic retry, and a terminal result of
  `COMPLETE_DIAGNOSTIC` with `physical_release_effect: NONE`.

A rehearsal can never be converted into a physical session.
An unresolved cell or device quarantine cannot be bypassed by creating a new
session.

## 2. Decisions frozen by this v2 plan

The following choices are the implementation baseline unless a reviewed plan
revision explicitly changes them:

1. The existing 15 stage names and order remain canonical in
   `physical_onboarding.STAGE_ORDER`; the v2 implementation catalog binds that
   exact source and may add stage-specific implementation contracts without
   redefining the names or order. No sixteenth stage is added.
   `first_power_on_onboarding.STAGE_DEFINITIONS` supplies controlled rehearsal
   and operator explanations; tests keep those explanations semantically
   aligned, but they are not the catalog's canonical stage-order source.
2. Persistence is separated into three versioned truths: a per-session reviewed
   stage journal, a cell-global append-only attempt/effect ledger, and a
   cell-global quarantine ledger. Stage disposition is not used as an attempt
   log.
3. Legacy v1 sessions remain readable, verifiable, and exportable. Once v2 is
   activated, they cannot run effectful actions or be rewritten as v2; a new
   source-bound successor session is required.
4. V2 does not write stage state `ACQUIRING`. The UI derives “acquiring” from an
   unsealed attempt. `ACQUIRING` remains only for conservative v1 compatibility.
5. The wizard is an evidence-guided commissioning console, not a robot control
   panel.
6. The browser and terminal interfaces are thin clients over one pure-Python
   `ArrivalWizardService`. They never write session files directly.
7. The existing v1 controller remains hardware-incapable. A future
   `CellCommissioningCoordinator` owns global leases, effect attempts,
   quarantine checks, energization envelopes, and bounded workers.
8. There will be no `--live` boolean, generic device endpoint, raw serial
   endpoint, numeric camera-index selection, arbitrary COM-port field, command
   text box, jog control, or generic `pass`/`approve` operation.
9. Phase 1 uses the B0477 on the rigid static overhead support. The legacy
   arm-mounted IMX335 path stays historical/optional and cannot be selected by
   fallback.
10. Candidate camera and arm identities discovered during onboarding live in
   immutable session evidence. The wizard will not edit controlled runtime
   configuration during a session, because that would invalidate its source
   binding.
11. A controlled static-camera successor freeze must be created before the first
   real arrival session. The candidate is Freeze 012; Freeze 011 and archived
   Freeze 009 remain immutable.
12. Motion needed for Stages 13 and 14 is performed by a separate, narrowly
   released noncontact qualification runner. Stage 13 begins with a conservative
   bootstrap envelope that cannot authorize Stage 14. The wizard verifies and
   imports reports; it never gains a motion adapter.
13. Every actuator off-to-on transition requires a unique energization envelope
   and attempt record. A prior Stage-10 review is a prerequisite, not standing
   power authority. Emergency de-energization is always allowed.
14. Stage 8 owns installed intrinsics and camera-to-board registration. Stage 13
   owns robot/controller-to-board correlation, free-state TCP, and device maps.
15. The final runtime handoff is one immutable, predecessor-linked
   `CommissioningBundle`. Physical runtime code has no nominal calibration or
   nominal target-map fallback.
16. Keyboard and Android contact qualification remain two later, independent
   releases after diagnostic handoff.

## 3. Hardware and placemat contract the wizard must display and bind

The UI must read these values from the controlled files and show their source
hashes. It must not maintain a second hand-copied geometry configuration.

| Item | Controlled planning value | Physical status |
|---|---|---|
| Placemat frame | `B`: origin at front-left board top; +X right, +Y rear/toward arm, +Z up | Board dimensions and installed datums still require measurement |
| Board | `610 x 457 x 18 mm` | Nominal until received/built board is checked |
| Keyboard | Perixx PERIBOARD-409, nominal origin `(85, 85) mm`, size `315 x 147 x 21 mm` | Seating, surface, key polygons, and travel require measurement |
| Phone | Samsung Galaxy A16 5G, nominal origin `(499.2, 84.2) mm`, configured size `77.9 x 164.4 x 7.9 mm`, nominal screen plane `Z=11.9 mm` | Case, screen, UI, insets, and touch behavior require measurement |
| Board tags | T0-T3 for pose; K0/P0 as independent station checks; 40 mm detection edges | Printed scale, installed corners, optical plane, glare, and adhesion require measurement |
| Primary camera | Arducam B0477 / IMX283 / included nominal 16 mm manual C-mount lens | Purchased catalog configuration; received article remains unverified |
| Camera mode | `5472 x 3648 @ 9 fps`, `YUY2`, direct USB 3.2 Gen 1 UVC | Must be enumerated and read back on the actual host |
| Camera support | Static front portal on common metal U-frame; nominal entrance pupil `Z=1000 mm`, adjustment `950..1050 mm`; provisional lowest overhead hardware `Z=920 mm` | Screening concept only; cut lengths, stiffness, load, cable, and collision clearance remain open |
| Arm | Waveshare RoArm-M3 Pro, ESP32 controller, direct host USB serial, 115200 baud, RTS/DTR false | Received identity, firmware behavior, transforms, repeatability, and startup motion remain unverified |

The current optical screening predicts roughly `911 x 608 mm` conservative
coverage at the nominal 1000 mm height and about `6 px/mm`, but those numbers
are planning evidence only. The wizard must never present them as measured
focus, distortion, field of view, or targeting accuracy.

Every calibration or device map must depend on the exact upstream hashes that
produced it. A change to board location, tag stack, camera body, lens, focus,
aperture, mode, crop, driver, support, cable strain relief, lighting, arm base,
tool, keyboard, phone, case, OS UI, or target map must invalidate its declared
downstream artifacts.

## 4. Current foundation and exact gaps

### Already implemented and retained

- deterministic simulation of keyboard and Android action plans, target maps,
  trajectories, visibility, controller behavior, outcomes, and uncertainty;
- an exact 15-stage onboarding order shared by simulation and physical
  onboarding;
- immutable source-bound session headers;
- legacy append-only, hash-chained journal events and a logically verified
  high-water record, plus a separate v2 journal bound to its publication mode
  and durability qualification;
- the states `PENDING`, `WAITING_OPERATOR`, `ACQUIRING`, `PASS`, `BLOCKED`,
  `INVALIDATED`, `SIDE_EFFECT_UNCERTAIN`, and `COMPLETE_DIAGNOSTIC`;
- fresh precondition challenges on every existing mutation;
- automatic zero-I/O assessment for Stages 1 and 2;
- bounded content-addressed evidence and strict session verification;
- a strict whole-template 55-row hardware-intake validator; progressive
  due-stage closure is not yet implemented;
- explicit, non-opening camera and serial metadata inventory;
- exact receipt/assessment types for camera receipt, power safety, first power,
  and a controlled operator decision;
- provider-neutral B0477 and feedback-only RoArm contracts with incapable fake
  providers and a failure rehearsal;
- synthetic B0477 native-frame, calibration, replay, and static Phase-1
  dependency foundations;
- a serial transport that blocks motion and a separate, currently gated
  feedback command; and
- conservative v1 recovery: a crash in `ACQUIRING` never replays the action and
  `SIDE_EFFECT_UNCERTAIN` is terminal inside that session;
- an M1 local-fixed-volume Windows/NTFS-qualified publication adapter, stable durability anchor,
  fresh-startup requalification, ordered cell/session leases, and strict v2
  session publication; and
- cell-global append-only attempt and quarantine ledgers with evidence-only
  startup recovery: a pre-arm intent is aborted without replay, while an armed
  incomplete attempt becomes uncertain and latches quarantine across sessions.

### Missing before the wizard is arrival-ready

| Gap | Consequence now | Planned resolution |
|---|---|---|
| Legacy stage and attempt state are conflated | v1 `ACQUIRING` still implies reconciliation; the M1 v2 stores are separate but no reviewed stage/effect coordinator uses them yet | M2/M4 must make the separate v2 stores the only effect/review path and derive transient UI state |
| Legacy uncertainty is session-local | The M1 ledger/quarantine layer blocks a new v2 session when global uncertainty exists, but no physical runner is connected to it | M2 must require the cell-global admission check before every physical worker action and external runner |
| Qualified publication is not yet an effect boundary | M1 now rejects remote/removable volumes and qualifies the actual local fixed Windows/NTFS volume with the adapter, but no effect-capable coordinator consumes it and independent power-interruption qualification remains outstanding | Qualify the complete adapter/fault matrix, then require it at the M2 pre-effect intent boundary |
| Authority is summarized with booleans | Booleans cannot distinguish camera open, manual energization, serial reset risk, or external motion | Closed authority and effect-class policies; one-use permits bind the exact executor and risk class |
| Only first power has a ceremony | Stage 12 and each later motion campaign require additional off-to-on transitions | A unique `EnergizationEnvelope` and global attempt for every actuator energization |
| Stage-13 calibration has a circular motion prerequisite | Final transforms/collision evidence do not exist until some bounded motion is measured | Conservative empty-cell bootstrap permit and bundle phase before qualified noncontact validation |
| Stage 3 is described as closing all 55 intake rows | Later optical, collision, drift, calibration, and release facts cannot exist at receipt | Machine-readable progressive owner-stage map; `INT-055` remains post-diagnostic |
| No reviewed assessment-to-journal bridge | Public CLI stops at Stage 3 `WAITING_OPERATOR` | Stage-specific review service and `physical-onboard assess/apply-review` |
| Receipt types exist for only Stages 3, 10, and 11 | Remaining physical evidence cannot advance honestly | Strict receipts and assessors for Stages 4-9 and 12-15 |
| Legacy mutations do not use the M1 lease facade | M1 cell/session mutations hold ordered OS leases and recheck a challenge; legacy v1 and future stage services are still separate | Route future v2 review/effect mutations only through the lease-owning facade/coordinator |
| No guided frontend | Operator must assemble low-level commands manually | Shared service, terminal wizard, then loopback browser UI |
| No physical B0477 provider | Identity/mode/freshness paths are fake-only | Windows identity/topology/media provider implementing the narrow contract |
| Existing OpenCV adapter is insufficient | It permits numeric selectors and cannot prove topology, raw native mode, all controls, or device freshness | Treat OpenCV as preview/decode component only, not qualification authority |
| Native frames exceed current store bounds | One YUY2 frame is 39,923,712 bytes, above the 32 MiB item cap; 32 views exceed 512 MiB total | Chunked, manifest-last dataset evidence with controlled quotas |
| Camera architecture metadata says 4:3 and a single OpenCV backend | B0477 native mode is 3:2 and OpenCV cannot be identity/mode authority | Controlled migration to 3:2 plus separate native-UVC authority and pinned decode roles |
| Current pixel detector defaults below B0477 native pixels | An implicit resize or oversized rejection could invalidate geometry | Explicit calibrated working-image contract or separately qualified native bound |
| Physical dataset split is copied from synthetic 24/8 | Model choice could consume the final acceptance set | Precommit development/model-selection folds and an untouched one-time acceptance set before capture |
| No onboarding-only physical T=105 provider | Existing runtime feedback command has a circular commissioned-config dependency | One-use Stage-12 provider bound to Stage 9-11 session evidence |
| Physical intrinsics/extrinsic acquisition is not guided | Synthetic closure cannot be replaced with measured artifacts | Installed-camera capture, solve, held-out validation, staging, and replay workflow |
| Stages 13-14 need motion while onboarding has zero authority | They cannot be made executable safely inside this controller | Separate noncontact permit, executor, dispatch ledger, and report import |
| Freeze 011 retains legacy primary-camera fields under hold | A real session would soon become source-stale during architecture correction | Perform controlled static-primary successor migration first |
| No immutable handoff export/sign-off | Completion cannot be independently reviewed as one package | Manifested export plus reviewer/off-machine anchoring |
| No typed `CommissioningBundle` runtime boundary | Runtime could assemble ad hoc or nominal inputs | Four-phase predecessor-linked bundle and fail-closed physical loader |
| No closed target-error budget | Stock phone QWERTY may be smaller than total uncertainty | Conservative target-plane budget, eroded safe regions, and predefined UI/tool/precision fallbacks |

## 5. Target architecture

```text
PowerShell launcher
       |
       +--> terminal wizard -----------------------------+
       |                                                 |
       +--> loopback browser (presentation only) --------+-->
                                                         |
                                                ArrivalWizardService
                                                         |
                  +-------------------------+----------------------------+
                  |                         |                            |
          reviewed-stage service   CellCommissioningCoordinator    export/bundle
                  |                         |                       service
                  v                         v                            |
       PhysicalOnboardingController   global cell lease                 v
                  |                   attempt/effect ledger     CommissioningBundle
                  |                   quarantine ledger          builder/validator
                  |                   energization envelopes
                  |                   one-use effect permits
                  v                         |
       immutable session journal            v
       evidence and dataset stores   capability-scoped workers
                                     | one bounded B0477 campaign
                                     | arm metadata inventory
                                     | exact-one-T105 campaign
                                     + no generic power/motion/contact API

Separate reviewed system, never a wizard provider:
bootstrap/noncontact permit -> qualification runner -> same global effect and
quarantine ledgers -> sealed report -> verified wizard import
```

### Layer responsibilities

**`PhysicalOnboardingController`**

- remains the per-session reviewed-state and evidence persistence authority;
- verifies source binding, journal, high-water, evidence, stage order, and
  challenge;
- exposes only narrow reviewed transition methods, never raw
  `commit_stage_state` to a UI;
- does not represent global action attempts or global quarantine as stage state;
- never imports a camera, serial, web, or motion backend.

**`ArrivalWizardService`**

- produces immutable view models from verified controller state;
- exposes stage-specific actions and reason codes;
- coordinates drafts, upload staging, assessment previews, and exports;
- owns no durable truth and never accepts caller-selected disposition or
  authority;
- is shared by CLI tests and the browser layer.

**Reviewed-stage service**

- reconstructs a binding from the current verified snapshot;
- parses only the receipt schema registered for the active stage;
- verifies that every referenced evidence object exists and hashes correctly;
- recomputes the deterministic assessment server-side;
- validates the exact operator/reviewer decision;
- stores one canonical review bundle;
- maps the derived result to the one legal journal state.

**`CellCommissioningCoordinator`**

- acquires the cell-global lease before the per-session lease and revalidates
  source, session head, device identity, epochs, hazard gates, and quarantine;
- appends and durably publishes exact intents to the cell-global attempt/effect
  ledger before any possible external effect;
- issues one-use permits for a closed effect class and exact executor;
- creates a unique `EnergizationEnvelope` for every actuator off-to-on event;
- invokes exactly one self-contained bounded worker campaign;
- records observed effects, cleanup, final power state, and evidence before
  sealing an attempt as known;
- latches unresolved effects in the global quarantine ledger so a new session,
  process, or runner cannot bypass them; and
- never reconnects, reopens, retries, initializes, homes, parks, or loops.

**Provider subprocesses**

- are selected from a fixed server-side allowlist;
- communicate over bounded, exact-schema IPC;
- receive only the one-use permit and capability needed for one operation;
- contain no cross-capability methods or dynamic import names;
- execute a complete campaign, including open and close, inside one bounded
  process rather than exposing stateful device handles to the coordinator;
- exit after cleanup and report actual open/read/write/capture/close counts.

**Commissioning-bundle builder**

- accepts only reviewed, source-bound predecessor artifacts;
- verifies the bootstrap, reference, noncontact, and final-acceptance phases;
- closes the target-plane error budget or reports an explicit blocker; and
- emits an immutable diagnostic bundle with no runtime, power, motion, contact,
  or promotion authority.

### Target source layout

The M1 durability, lease, storage, v2, attempt, quarantine, and facade modules
in this layout now exist. Later entries remain planned and must preserve the
same capability separation.

```text
software/src/rocell/application/
  physical_onboarding_foundation.py
  physical_onboarding_stage_catalog.py
  configuration_epochs.py
  physical_onboarding_durability.py
  physical_onboarding_leases.py
  physical_onboarding_storage.py
  physical_onboarding_v2.py
  physical_onboarding_m1.py
  physical_onboarding_review.py
  physical_onboarding_stage_receipts.py
  cell_commissioning_coordinator.py
  physical_onboarding_attempts.py
  physical_onboarding_quarantine.py
  energization_envelopes.py
  commissioning_bundle.py
  physical_onboarding_export.py
  arrival_wizard.py

software/src/rocell/vision/
  b0477_live_provider.py
  windows_uvc_identity.py
  native_frame_dataset.py
  calibration_image_dataset.py
  physical_apriltag.py

software/src/rocell/arm/
  onboarding_feedback_provider.py
  onboarding_serial_identity.py

software/src/rocell/noncontact/
  bootstrap_permit.py
  permit.py
  dispatch_ledger.py
  qualification_runner.py

software/src/rocell/safety/
  effects.py
  onboarding_hazards.py

software/src/rocell/calibration/
  accuracy_budget.py

software/src/rocell/workcell/
  interface_contract.py

software/src/rocell/wizard/
  __init__.py
  service.py
  server.py
  templates/wizard.html
  static/wizard.css

software/tests/
  unit/
  contract/
  integration/
  fault/
  ui/
```

Names may be consolidated during implementation, but capability boundaries may
not be collapsed.

## 6. State, review, and action semantics

### Three separate durable state domains

V2 must not use one field to describe review progress, action execution, and
cell safety. These are separate, cross-linked records:

1. **Session stage journal:** reviewed dispositions for the canonical 15
   stages: `PENDING`, `WAITING_OPERATOR`, `PASS`, `BLOCKED`, `INVALIDATED`,
   `REVIEW_PENDING`, `INCIDENT_HOLD`, `SIDE_EFFECT_UNCERTAIN`, and terminal
   `COMPLETE_DIAGNOSTIC`.
2. **Cell-global attempt/effect ledger:** exact intents and effect observations
   across every session and the separate noncontact runner.
3. **Cell-global quarantine ledger:** unresolved cell, power, camera, arm, or
   controller uncertainty that blocks new effects regardless of session ID.

V2 never writes `ACQUIRING` to the stage journal. It remains readable only in
legacy v1 sessions, where recovery stays reconciliation-only. The browser may
derive friendly review substates without persisting new authority-bearing
states:

```text
NEEDS_EVIDENCE -> READY_FOR_ASSESSMENT -> NEEDS_REVIEW -> READY_TO_COMMIT
```

The durable flow for a passive reviewed stage is:

```text
verified WAITING_OPERATOR
-> retain evidence
-> construct exact typed receipt
-> derive assessment
-> display reasons
-> bind reviewer decision
-> acquire session lease and reverify challenge
-> recompute assessment
-> store canonical review bundle
-> commit PASS/BLOCKED/COMPLETE_DIAGNOSTIC
-> reload and verify
```

The durable flow for a possible device effect is:

```text
verified WAITING_OPERATOR
-> preview exact operation
-> acquire cell-global lease, then session lease
-> reverify sources, epochs, head, challenge, device identity, and quarantine
-> append INTENT_DURABLE for an exact effect class and operation hash
-> issue explicit one-use permit and obtain confirmation where required
-> atomically consume permit as EFFECT_ARMED before the first possible effect
-> invoke exactly one self-contained bounded worker campaign
-> append EFFECT_OBSERVED and CLEANUP_CONFIRMED with accounting
-> retain raw evidence and typed receipt
-> append SEALED_KNOWN, then assess/review and commit the legal stage result
-> reload and independently verify every store
```

If execution stops before `EFFECT_ARMED`, the attempt may be sealed
`ABORTED_PRE_EFFECT`. Once `EFFECT_ARMED` exists, any missing observation,
partial operation, ambiguous consequence, unknown cleanup, unknown device
state, or unknown final power state seals `SEALED_UNCERTAIN` and latches global
quarantine. The original action is never replayed. A reviewed reconciliation
record may clear a quarantine only under a future separately specified process;
starting a new session cannot clear it.

Result mapping is fixed:

| Derived result | Legal journal result |
|---|---|
| `DIAGNOSTIC_READY` plus valid acknowledgement | `PASS` |
| Deterministic known failure or reviewer hold | `BLOCKED` |
| Unknown before any possible external effect | `BLOCKED` |
| Global attempt sealed uncertain after an effect may have begun | `SIDE_EFFECT_UNCERTAIN` plus quarantine latch |
| Ready Stage 15 diagnostic package | `COMPLETE_DIAGNOSTIC` |

The reviewer may preserve or reduce readiness. A reviewer can place a hold on a
ready assessment, but cannot upgrade `HOLD` or uncertainty. No API accepts a
boolean pass flag or a caller-authored assessment disposition.

### Locking and Windows durability

Every effect attempt must acquire the cell-global lock before its per-session
lock. Every other mutation holds the applicable exclusive OS lock outside the
immutable data directory. Lock records include cell/session IDs, process ID,
process-start identity, launch nonce, operation, and acquisition time. The
coordinator rechecks the complete state challenge while both locks are held.
Read-only status may continue, but another writer returns a bounded busy
response and performs no worker call.

V2 physical effects remain disabled until a Windows storage adapter is
qualified on the deployment filesystem. The planned NTFS protocol uses
exclusive Win32 locks, same-volume temporary files, write-through file handles,
`FlushFileBuffers`, atomic replace with write-through semantics, and an explicit
directory/publication strategy. A startup self-test must prove the required
ordering and torn-tail recovery on the actual volume. The current portable
directory-sync compatibility path is not accepted as power-loss durability.
An OS-released lock after process death never makes an armed action repeatable.

### Closed authority classes and one-use permits

Every operation is assigned exactly one closed class from the controlled
authority/effect policy: `NO_DEVICE_IO`, `READ_ONLY_OS_INVENTORY`,
`BOUNDED_CAMERA_CAMPAIGN`, `MANUAL_ENERGY_CHANGE`,
`MANUAL_POSSIBLE_MOTION`, `SERIAL_OPEN_OR_WRITE`, or
`NONCONTACT_ARM_MOTION_EXTERNAL`. The UI never supplies this class. A worker
executable has a fixed maximum class and cannot accept a stronger permit.

An effect-capable POST/CLI apply requires a short-lived, one-use permit bound
to:

- attempt ID, session ID, cell ID, and configuration-epoch hashes;
- rehearsal or physical session type;
- source-binding and stage-plan hashes;
- current stage-journal, global-ledger, quarantine, and evidence-inventory
  heads;
- exact active stage and state;
- closed effect class, worker executable hash, provider/action ID;
- retained persistent device-identity hash;
- exact operation/request hash and resource limits;
- issuance/expiration and cryptographic nonce; and
- explicit power, motion, and contact authority ceilings, all false for wizard
  providers except the separately reviewed manual-energy or external-motion
  envelope they represent.

The permit is consumed before camera open, before displaying an energize
instruction, before serial open (opening an ESP32 port may reset it), or before
external motion dispatch. A partial operation or uncertain dispatch consumes
it. Refresh, double click, restart, or timeout never creates a replacement.

`required_effect_classes` is the complete ordered set of effect domains a stage
must account for; it is not an instruction to execute the operation once per
class. Each separable external effect has one predecessor-linked attempt and a
permit with one primary class. Causally inseparable consequences, such as
possible startup motion caused by one energization, are facets of that same
attempt and never authorize a second dispatch, energization, or retry.

### Energization envelopes and configuration epochs

Every actuator off-to-on transition has its own predecessor-linked
`EnergizationEnvelope`: exact power topology and evidence hashes, cell/device
epochs, operator and observer identities, E-stop and containment checks,
installed-object inventory, allowed downstream operation, issue/expiry,
confirmed initial state, and required final de-energized state. Stage 10 review
is only an input. It is never standing authority. Emergency de-energization is
always allowed and must not wait for software.

The eight controlled configuration epochs independently track software/build,
camera/support/optics, board/tags/bench, arm/controller/tool, power system,
keyboard station, phone station, and empty-cell safety. An epoch change is an
append-only successor record with a predecessor hash and reason code; it
invalidates every dependent artifact and prevents cross-epoch reuse unless all
declared dependency hashes still match.

## 7. Stage-by-stage wizard contract

Every stage screen uses the same layout: purpose, required power state,
preconditions, operator steps, exact automated action, evidence checklist,
machine assessment, reviewer decision, committed result, and next safe action.

| # | Stage and required state | Wizard automation | Operator/reviewer responsibility | Pass evidence and fail-stop behavior |
|---:|---|---|---|---|
| 1 | `workspace_sources`; no device access | Verify controlled hashes, build, environment, dependency metadata, zero-authority policy, journal format | Confirm intended cell/build | Any missing/drifted source blocks. Source drift later makes the session read-only; create a successor rather than rewriting it. |
| 2 | `static_camera_contract`; RoArm off | Cross-bind B0477 profile, support contract, native-mode contract, calibration graph, and static-primary architecture | Confirm the displayed physical diagram matches the intended build | Any architecture/source mismatch blocks without inventory/open. Physical use additionally requires the successor static-primary freeze. |
| 3 | `camera_receipt`; RoArm off; camera may remain disconnected | Validate the Stage-3-owned intake subset; create and assess `CameraReceiptInspection` | Photograph labels, case, lens, connectors, cable, fasteners, damage; enter measured mass, envelope, projection, thread/mount, usable fastener depth, board-flatness observation, and purchase record; reviewer signs/holds | Exact B0477/IMX283/nominal 16 mm article and every Stage-3 measurement/evidence obligation are required. `INT-005` is observed here, but its derived flatness-limit acceptance remains open until the Stage-14 accuracy budget closes. Later-stage intake rows remain explicitly pending, not falsely complete. Missing, damaged, ambiguous, or mismatched items produce `BLOCKED`; corrections are appended, never overwritten. |
| 4 | `camera_identity`; RoArm off; camera USB only | Inventory Windows PnP/UVC metadata without opening; compare unplug/replug and reboot observations; bind one persistent identity | Connect B0477 directly to a known USB 3 port and confirm the physical unit during each trial | Require stable VID/PID, unit serial or separately approved persistent symbolic identity, driver, path, and topology. Duplicate/missing/unstable identity or numeric-index-only evidence blocks. |
| 5 | `camera_mode_controls`; RoArm off; camera only | Open only the identity-bound device once; enumerate media types; request and read back `5472x3648 @ 9 fps YUY2`; record USB topology, driver, exposure/gain/WB state; close/reopen only as a separately predeclared qualification campaign | Clear the camera scene of private content before the first possible capture; verify direct port/cable; physically set, lock, and witness focus/aperture rings | Any missing privacy clearance, device/backend substitution, USB2 path, crop/scale, wrong FOURCC/mode, automatic control drift, reopen mismatch, or failed close blocks. No fallback occurs. |
| 6 | `camera_frame_freshness`; RoArm off; camera only | Run one bounded native-UVC campaign with a prescribed visible time-varying challenge; verify genuine sequence progression, raw bytes, negotiated size/stride, timing, drop/latency, and cleanup | Present the prescribed challenge and explicitly start one capture campaign | Distinct hashes alone do not prove freshness. Short, repeated, rewrapped, stale, malformed, late, or ambiguously timed frames cannot pass. Disconnect or close failure ends the action; no automatic reopen/retry. |
| 7 | `optics_intrinsics`; RoArm off; camera only | Render downsampled non-evidence previews; measure preliminary coverage/focus/illumination/throughput; guide support-height feasibility and precommit the installed-camera acquisition plan | Place camera at measured `950..1050 mm`; adjust manual focus/aperture; provide a scale traceable chart and varied trial poses | Every result is `PRELIMINARY_ONLY`. This stage does not own production intrinsics or camera-to-board registration. Insufficient one-metre focus, board/tag coverage, depth of field, illumination, or throughput blocks final installation. |
| 8 | `static_registration`; actuator 12 V physically disconnected; no arm motion | After retained installation and warm-up, acquire the production calibration dataset; solve installed intrinsics/distortion and `camera_overview_optical_T_board`; ingest the measured tag map; validate T0-T3 plus held-out K0/P0, visibility, bump/reseat/cable/thermal/drift trials | Rigidly secure support, camera, focus, aperture, cable, and lights; add witness marks; survey installed tag corners/plane; conduct guided disturbances while the arm cannot energize | Only installed, dependency-bound calibration can pass. Residual, observability, held-out station check, route visibility, drift, or reseat failure holds. Any camera/support/board epoch change invalidates this and all descendants. |
| 9 | `arm_identity`; actuator 12 V disconnected; do not open serial | Inventory USB/serial PnP metadata only and compare reconnect/reboot observations | Photograph the exact Pro arm, ESP32/controller, supply and cable; confirm exclusive owner and intended firmware-readback policy | Require unique persistent controller identity candidate, correct model/supply, 115200 profile, RTS/DTR false, and no auto-connect/init/retry. Ambiguity blocks; the port stays closed. Stage 9 cannot produce `qualified_controller_identity`. |
| 10 | `power_safety`; actuator power disconnected | Validate and assess `PowerSafetyReview`; cross-check evidence dependencies and declared keepout | Secure arm/board/support/cables; verify supply/polarity; test the independent power-cut E-stop on an inert load; prove gravity containment, startup swept-volume clearance, empty cell, and observer access; operator and observer sign | Every field must be known and current. Missing containment, failed power cut, inaccessible E-stop, collision unknown, stale evidence, or installed device/tool produces `BLOCKED`. Software never claims a passive check proves dynamic stopping. |
| 11 | `power_on_observation`; manual possible-motion event; ends de-energized | Durably arm a unique manual-energy attempt before showing the energize instruction; prepare local recording/timestamps; afterward build and assess `FirstPowerObservation` | Two-person ceremony: clear cell, observer at physical E-stop, manually energize once, send zero host commands, observe startup repositioning, manually de-energize, prove final state, and record it | Wizard has no power-control API. Unknown final power, lost observation, collision/contact, unknown motion, or ambiguous consequence seals the attempt uncertain and latches global quarantine. Never auto-repeat or command park. |
| 12 | `feedback_only_connection`; new energization envelope; devices/tool absent | Rebind the exact controller identity; consume the one-use serial permit before open because open may reset the ESP32; open with fixed settings; observe a bounded quiet-buffer dwell without discarding bytes; write exact `{"T":105}\n` once; retain all raw/timing/decoded evidence; close and require de-energization | Reperform the envelope checks, observer/E-stop setup, manual energization, and one-use preview for the exact identity; explicitly authorize one feedback campaign; manually de-energize at completion | Stage 10/11 are prerequisites, not standing power authority. No T=104, arbitrary port, or raw-write surface exists. Any pre-request byte blocks the write. Reset, partial write, timeout, malformed/stale reply, disconnect, extra data, uncertain cleanup, or unknown final power consumes the permit, seals uncertain, and quarantines; no retry. The Stage-9 inventory candidate becomes `qualified_controller_identity` only here, after the controlled exchange plus an approved installed-firmware observation; absent that evidence the stage remains blocked. |
| 13 | `reference_frame_calibration`; separate bootstrap and reference-motion authorizations required; each ends de-energized | Validate/import predecessor-linked bootstrap and reference-characterization reports; solve joint signs/zeros/ranges/repeatability, controller-to-board and arm-to-board transforms, free-state TCP, keyboard/phone maps, and observer bindings | First approve a conservative empty-cell bootstrap envelope with external geometry only, reduced limits, observer/E-stop setup, and no device contact; then independently approve the exact reference campaign and supervise the separate runner; independently prove actuator power off after each campaign | The wizard never executes motion. Bootstrap results cannot authorize Stage 14. Only sealed reports with complete attempt/effect ledgers, achieved feedback, dependency hashes, held-out residuals, and proven final disconnection are accepted. Unknown final power seals uncertain and quarantines. Automatic middle-position motion is never home. Contact compliance remains unmeasured and blocked. |
| 14 | `noncontact_acceptance`; separate bounded-motion release; no descent/contact; each campaign ends de-energized | Verify/import empty-cell stop/power-loss/park/settling and arm-induced visibility reports, then one-device-at-a-time hover reports; evaluate untouched acceptance data and the noncontact target-error budget | Clear cell first; supervise the separate runner; install one device only after empty-cell acceptance; inspect every stop and hover; independently prove actuator power off after each campaign | Complete collision geometry, exact plan hash, conservative limits, fresh localization, tracking, settling, safe stop/park, visibility, route clearance, final disconnection, and keyboard/phone noncontact budgets must pass. Any unknown effect or final power, collision, stall, occlusion, vision loss, power loss, or over-budget target seals uncertain/fail-stops and quarantines. |
| 15 | `physical_handoff`; stage performs no hardware I/O | Reverify sources, epochs, hazards, journals, global ledgers, evidence, dataset partitions, calibration dependencies, and accuracy decisions; build and validate an immutable predecessor-linked `CommissioningBundle` plus diagnostic report and blockers. The bundle has exactly 39 top-level required components, each assigned to one producer stage by the controlled catalog. | Independent reviewer verifies the bundle and explicitly scopes any later release | Commit `COMPLETE_DIAGNOSTIC`, never `PASS`. The bundle grants no power, motion, descent, contact, typing, promotion, or runtime fallback authority. `INT-055` remains a post-diagnostic release-freeze item. |

### Progressive hardware-intake ownership

The 55-row intake template remains canonical, but each fact becomes due only
when it can be measured honestly. Earlier stages show later rows as pending;
they do not manufacture placeholder evidence or close the whole template.

| Owner | Rows due |
|---|---|
| Stage 3 measurement/evidence owner | `INT-001..009`, `INT-017`, `INT-019..024`; `INT-005` acceptance remains deferred |
| Stage 4 | `INT-018` |
| Stage 5 | `INT-028..029` |
| Stage 7 | `INT-025..027` |
| Stage 8 | `INT-030..043`, `INT-046..048`, `INT-050..053` |
| Stage 9 | `INT-010` |
| Stage 10 | `INT-012..016`, `INT-044..045` |
| Stage 12 | `INT-011` |
| Stage 13 | `INT-049` |
| Stage 14 acceptance owner | `INT-005` derived flatness limit and `INT-054` |
| Post-diagnostic controlled release | `INT-055` |

The machine-readable stage catalog is authoritative for this mapping and must
be checked against the canonical 15-stage source on every load.

Post-handoff, keyboard and Android contact qualification each begin with dummy
targets and require their own tool retention, TCP/compliance, force/travel,
repeatability, damage, and independent outcome-observation evidence. Every
future contact remains:

```text
observe while retracted -> localize/quality gate -> approach -> contact
-> retract -> independently verify outcome
```

An ambiguous physical outcome is never automatically repeated.

## 8. Operator experience and local UI

### Entry points

The final supported Windows entry path will be:

```powershell
.\start-rocell-onboarding.ps1 -CellId CELL-A -OpenWizard
```

Equivalent explicit commands will remain available for recovery and automated
tests:

```powershell
.\rocell.ps1 physical-onboard wizard --session-id <id> --ui browser
.\rocell.ps1 physical-onboard wizard --session-id <id> --ui terminal
.\rocell.ps1 physical-onboard wizard --mode rehearsal --ui browser
```

`start-rocell-onboarding.ps1` must still complete the controlled environment,
host-doctor, incapable-provider rehearsal, and zero-I/O preparation before it
offers to open the browser. Opening the browser never starts a hardware action.

The landing experience offers four explicit choices:

1. practice with simulated hardware;
2. create a new physical diagnostic session;
3. resume an existing physical session; or
4. open a completed/blocked session read-only.

No screen has “Continue all,” “Skip,” or automatic multi-stage execution.

### Persistent page content

Every wizard page shows, without relying on color alone:

- cell ID, session ID, and rehearsal/physical mode;
- build ID, freeze ID, stage-plan hash, and current/stale source binding;
- stage number, name, exact reviewed state, journal head, and evidence digest;
- cell-global attempt-ledger and quarantine heads, with any open attempt or
  quarantine prominently identified;
- all 15 stages in a visible stepper, with future stages locked;
- required actuator-power state, ordered required effect classes, the current
  attempt's closed effect class, allowed device access, current one-use permit
  state, and worker identity;
- current configuration-epoch hashes and any downstream invalidations;
- the applicable energization-envelope ID and proven final power state;
- progressive intake due/completed/pending counts;
- calibration phase, dataset partition, target-error-budget status, and
  `CommissioningBundle` phase when applicable;
- operator and distinct observer/reviewer identities where required;
- evidence count, provider accounting, and last durable event; and
- a persistent statement: `DIAGNOSTIC ONLY — NOT READY TO TYPE`.

Hazard banners are exact and textual:

- `NO HARDWARE ACCESS`
- `ARM 12 V MUST BE DISCONNECTED`
- `CAMERA ACCESS ONLY`
- `POSSIBLE AUTOMATIC ARM MOTION — HUMAN POWER CONTROL`
- `FEEDBACK QUERY ONLY — NO MOTION COMMAND`
- `LIMITED NONCONTACT RUNNER — SEPARATE PERMIT`
- `NO CONTACT AUTHORITY`

There is no software button called “E-stop.” A `Stop procedure` link may explain
how to use the physical E-stop and append an incident/hold report, but must not
claim to remove power.

### Browser implementation

Version 1 uses a small server-rendered Flask application behind a local WSGI
server. It uses ordinary forms and page reloads; JavaScript is not required for
state mutation. This keeps the operator flow inspectable and avoids a Node,
Electron, or single-page-application toolchain. The terminal frontend is built
first and remains fully supported if browser launch fails.

The browser server must:

- bind only to `127.0.0.1` on an operating-system-selected port;
- reject non-loopback peers, unapproved `Host`, and foreign `Origin` values;
- exchange a cryptographically random one-use launch URL token for an
  `HttpOnly`, `SameSite=Strict` cookie, then remove the token from the URL;
- use a separate one-use CSRF nonce for every mutating form;
- accept mutation only through POST; GET never inventories, opens, captures,
  writes, or advances a stage;
- set a strict Content Security Policy, `frame-ancestors 'none'`,
  `Referrer-Policy: no-referrer`, and `Cache-Control: no-store`;
- use no CDN, analytics, telemetry, remote fonts, or remote scripts;
- escape all device metadata, filenames, labels, and reason text;
- enforce content type, body, file, count, time, memory, and disk quotas before
  staging uploads;
- serve no arbitrary directories and accept no browser-supplied filesystem
  paths; and
- close cleanly without changing journal state.

Templates and CSS affect operator behavior. Because the current source binder
walks only Python files under `software/src/rocell`, the HTML/CSS files must be
listed explicitly as controlled onboarding sources when implemented.

### Accessibility and error recovery

- Full keyboard navigation, logical focus order, high contrast, reduced motion,
  and minimum 44 x 44 px hazardous-action controls.
- Screen-reader live regions announce committed state changes, not continuous
  camera telemetry.
- Every image overlay has a table equivalent listing tag IDs, corners,
  residuals, acceptance, and rejection reasons.
- Audible cues also have visible equivalents; no flashing countdown or timed
  reading acknowledgement.
- Draft form data may be recovered outside immutable session storage. Drafts
  have no evidentiary status.
- A stale challenge says `Nothing executed`, displays the intervening change,
  and requires a new preview.
- Source drift makes the session read-only and offers verified export plus
  successor-session creation.
- A process restart with an unsealed v2 attempt opens global reconciliation,
  never the original action button. A legacy v1 `ACQUIRING` session remains
  reconciliation-only.
- `INCIDENT_HOLD`, `SIDE_EFFECT_UNCERTAIN`, or any global quarantine opens an
  incident-style page with export and physical-safing instructions but no
  continue/retry/new-session bypass control.
- Journal or evidence tampering disables every mutation and provides only an
  integrity report.

### CLI parity

The browser must not be the only recovery path. Planned commands are:

```text
physical-onboard assess
physical-onboard apply-review
physical-onboard reopen
physical-onboard invalidate
physical-onboard acquire
physical-onboard reconcile
physical-onboard quarantine-status
physical-onboard verify-foundation
physical-onboard export
physical-onboard wizard
```

Semantics:

- `assess` is pure and never mutates the session;
- `apply-review` reparses and recomputes everything, then requires the current
  challenge and one-use review token;
- `reopen` moves only a known `BLOCKED` or `INVALIDATED` stage back to
  `WAITING_OPERATOR` with typed remediation evidence;
- `invalidate` appends a typed cause and uses the existing downstream
  invalidation behavior;
- `acquire` accepts a fixed stage-specific action name and derives its effect
  class server-side, never raw device arguments or caller-supplied authority;
- `reconcile` records observed post-state and cannot replay an action;
- `quarantine-status` is read-only and shows cell-global blockers;
- `verify-foundation` validates the additive design contracts and grants no
  physical authority;
- `export` creates a verified archive outside the immutable session directory;
  and
- `wizard` presents one service through terminal or loopback browser.

There will be no generic `pass`, `set-state`, `set-disposition`, `command`,
`retry`, `jog`, `home`, or `park` command.

## 9. Application contracts

The exact Python representation will follow existing frozen-dataclass and
strict-JSON conventions. The following interfaces define the required
responsibilities.

```python
class WizardMode(str, Enum):
    REHEARSAL = "REHEARSAL"
    PHYSICAL_DIAGNOSTIC = "PHYSICAL_DIAGNOSTIC"


class WizardCapability(str, Enum):
    ZERO_IO = "ZERO_IO"
    EVIDENCE_ONLY = "EVIDENCE_ONLY"
    METADATA_ONLY = "METADATA_ONLY"
    CAMERA_DIAGNOSTIC = "CAMERA_DIAGNOSTIC"
    MANUAL_POWER_OBSERVATION = "MANUAL_POWER_OBSERVATION"
    FEEDBACK_T105_ONLY = "FEEDBACK_T105_ONLY"
    REPORT_IMPORT_ONLY = "REPORT_IMPORT_ONLY"


class AttemptState(str, Enum):
    INTENT_DURABLE = "INTENT_DURABLE"
    ABORTED_PRE_EFFECT = "ABORTED_PRE_EFFECT"
    EFFECT_ARMED = "EFFECT_ARMED"
    EFFECT_OBSERVED = "EFFECT_OBSERVED"
    CLEANUP_CONFIRMED = "CLEANUP_CONFIRMED"
    SEALED_KNOWN = "SEALED_KNOWN"
    SEALED_UNCERTAIN = "SEALED_UNCERTAIN"


@dataclass(frozen=True, slots=True)
class StageDefinition:
    stage: PhysicalOnboardingStage
    ordinal: int
    title: str
    capability: WizardCapability
    required_effect_classes: tuple[EffectClass, ...]
    required_power_state: str
    intake_record_ids: tuple[str, ...]
    receipt_schema: str | None
    assessor_id: str | None
    provider_action_id: str | None
    produced_bundle_components: tuple[str, ...]
    required_predecessors: tuple[PhysicalOnboardingStage, ...]
    evidence_requirements: tuple[str, ...]
    invalidation_causes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ExactOperationPermit:
    attempt_id: str
    session_id: str
    cell_id: str
    mode: WizardMode
    source_binding_sha256: str
    stage_plan_sha256: str
    journal_head_sha256: str
    global_attempt_head_sha256: str
    quarantine_head_sha256: str
    evidence_inventory_sha256: str
    stage: PhysicalOnboardingStage
    effect_class: EffectClass
    worker_executable_sha256: str
    operation_sha256: str
    selected_identity_sha256: str | None
    configuration_epoch_hashes: tuple[str, ...]
    issued_at_ns: int
    expires_at_ns: int
    nonce: str
    permit_sha256: str


@dataclass(frozen=True, slots=True)
class EnergizationEnvelope:
    envelope_id: str
    attempt_id: str
    allowed_operation_sha256: str
    power_topology_sha256: str
    safety_review_sha256: str
    installed_object_inventory_sha256: str
    operator_id: str
    observer_id: str
    expires_at_ns: int
    required_initial_state: str
    required_final_state: str


@dataclass(frozen=True, slots=True)
class ReviewedStageApplication:
    binding: ReceiptBinding
    subject_receipt_sha256: str
    derived_assessment_sha256: str
    operator_decision_sha256: str
    referenced_evidence_ids: tuple[str, ...]
    resulting_state: StageState
    review_bundle_sha256: str


@dataclass(frozen=True, slots=True)
class CommissioningComponentBinding:
    component_id: str
    producer_stage: PhysicalOnboardingStage
    artifact_sha256: str


@dataclass(frozen=True, slots=True)
class CommissioningBundle:
    # Exactly 39 bindings in the controlled catalog's canonical component order.
    component_bindings: tuple[CommissioningComponentBinding, ...]
    controlled_source_binding_sha256: str
    configuration_epoch_vector_sha256: str
    global_attempt_ledger_head_sha256: str
    global_quarantine_ledger_head_sha256: str
    bootstrap_phase_sha256: str
    reference_phase_sha256: str
    noncontact_phase_sha256: str
    final_acceptance_phase_sha256: str
    accuracy_budget_sha256: str
    reviewer_decision_sha256s: tuple[str, ...]
    open_blocker_ids: tuple[str, ...]
    physical_release_effect: Literal["NONE"]
    bundle_sha256: str
```

Minimum `ArrivalWizardService` surface:

```python
class ArrivalWizardService(Protocol):
    def list_sessions(self) -> tuple[SessionSummary, ...]: ...
    def create_session(self, request: CreateSessionRequest) -> WizardView: ...
    def view(self, session_id: str) -> WizardView: ...
    def preview_next(self, session_id: str) -> WizardActionPreview: ...
    def begin_stage(self, request: BeginStageRequest) -> WizardView: ...
    def stage_evidence(self, request: StageEvidenceRequest) -> EvidenceView: ...
    def assess(self, request: AssessmentPreviewRequest) -> AssessmentView: ...
    def apply_review(self, request: ApplyReviewRequest) -> WizardView: ...
    def prepare_acquisition(self, request: AcquisitionPreviewRequest) -> ExactOperationPermit: ...
    def execute_acquisition(self, request: AcquisitionRequest) -> AcquisitionView: ...
    def reconcile(self, request: ReconciliationRequest) -> WizardView: ...
    def invalidate(self, request: InvalidationRequest) -> WizardView: ...
    def export(self, request: ExportRequest) -> ExportView: ...
```

All request types use bounded identifiers and exact hashes. No provider type,
module path, COM port, camera index, serial bytes, T code, Cartesian coordinate,
joint coordinate, or authority flag comes from the browser.

The `CellCommissioningCoordinator` is the only component allowed to turn a
reviewed acquisition request into a worker invocation. Its public surface is
closed over registered actions:

```python
class CellCommissioningCoordinator(Protocol):
    def prepare(self, request: RegisteredActionRequest) -> ExactOperationPermit: ...
    def execute(self, permit: ExactOperationPermit) -> AttemptResult: ...
    def reconcile(self, request: ReconciliationRecord) -> QuarantineView: ...
    def quarantine_status(self, cell_id: str) -> QuarantineView: ...
```

`prepare` never invokes a provider. `execute` acquires locks in cell-then-
session order, revalidates all bound heads, durably appends the attempt, and
consumes the permit before delegating one campaign. No method accepts arbitrary
bytes, device paths, worker modules, power state, coordinates, or retry flags.

### Minimal HTTP routes

```text
GET  /                              verified stage page
GET  /sessions                     verified session list
GET  /evidence/<evidence-id>       verified retained preview only
POST /sessions                     zero-I/O session creation
POST /stage/start                  one current stage transition
POST /evidence                     bounded upload to staging then evidence store
POST /assessment/preview           pure server-side assessment
POST /review/apply                 exact reviewed commit
POST /diagnostic/prepare           issue one action ticket
POST /diagnostic/execute           consume ticket and run one action
POST /reconcile                    record post-state; never retry
POST /invalidate                   typed invalidation
POST /export                       verified export
POST /shutdown                     stop UI only
```

Each POST requires a current challenge, the applicable cell-then-session lease,
local session cookie, CSRF nonce, fixed action ID, and strict exact-field
parsing. Presentation equivalence means both clients submit the same canonical
service request and receive the same semantic result; cookies, CSRF nonces,
timestamps, and transport wrappers are not required to be byte-identical.

## 10. Physical provider design

### B0477 provider

Implement the existing narrow `B0477ConnectionProvider` protocol with a
physical-origin provider. Do not retrofit a live flag into the fake rehearsal.

On Windows, use the persistent PnP/symbolic-link identity from SetupAPI or
Configuration Manager and enumerate/read media types through Media Foundation
or DirectShow `IAMStreamConfig`. OpenCV may decode, create a downsampled
preview, or participate behind the provider, but it is not authoritative for
identity, USB topology, exact raw FOURCC, control readback, or freshness.

Each effectful provider invocation is one self-contained bounded campaign. The
worker receives an identity-bound permit, owns the device only for that
campaign, and cannot leave an open handle for a later API call. The fixed
qualification sequence is:

```text
metadata inventory
-> uniquely bind persistent B0477 identity
-> recheck mapping immediately before open
-> prove direct USB topology and negotiated speed
-> open exactly that device
-> enumerate native media types and controls
-> request exact native mode and manual controls
-> read back actual mode and controls
-> account for every pre-challenge buffer item under a bounded policy
-> present/observe the prescribed visible time-varying freshness challenge
-> capture bounded native frames with genuine sequence/timing evidence
-> close and record close outcome
```

Unplug/replug, close/reopen, and reboot trials are distinct predeclared
qualification actions. They are never error recovery or automatic retry.

The provider records:

- vendor/product identifiers, serial if genuinely exposed, container/device
  instance IDs, symbolic link, driver/provider/version, bus location, hub/path,
  and negotiated topology/speed;
- requested and read-back width, height, frame rate, FOURCC, stride, crop,
  orientation, and control auto/manual state;
- physical focus/aperture witness evidence separately from UVC controls;
- host monotonic brackets and any genuine device timestamp/sequence without
  upgrading host timing into device-exposure timing;
- raw frame bytes and hashes, derived lossless calibration image, and separate
  preview;
- actual inventory/open/configure/flush/capture/reopen/close counts and errors.

For native B0477 mode, `5472 * 3648 * 2 = 39,923,712` bytes is the minimum
packed YUY2 payload, not a universal exact buffer length. The authoritative
capture receipt must retain the negotiated row stride, padding, origin, and
sample length. Native aspect ratio is `3:2`. OpenCV may decode a captured sample
only after Windows UVC identity and media negotiation have established its
provenance; it is never the identity or mode authority.

If the B0477 exposes no stable serial, the stage remains held until a reviewed
persistent-identity policy proves an exact symbolic-link/container/topology
combination across reconnect and reboot. A numeric camera index can be an
internal ephemeral locator only after that mapping; it is never retained as
identity or shown as the selection authority.

### Arm identity and one-shot feedback provider

Stage 9 uses only metadata enumeration while actuator power is disconnected.
It must not open the serial port. Stage 12 uses a separate onboarding-only
provider rather than calling the existing general `arm-feedback` command.

The Stage-12 public surface is limited to:

```python
class OnboardingFeedbackProvider(Protocol):
    def verify_identity_mapping(self, request: IdentityMappingRequest) -> IdentityMappingReceipt: ...
    def acquire_one_t105(self, permit: OnboardingT105Permit) -> SingleT105FeedbackReceipt: ...
```

There is no raw write method. The one-use permit binds the session/source/head,
passed Stage 9-11 receipt hashes, exact persistent controller identity,
ephemeral mapped port, 115200/timeout/RTS/DTR settings, exact request digest,
one permitted write attempt, expiration, and nonce.

The provider must:

1. recheck persistent identity immediately before open;
2. durably consume the `SERIAL_OPEN_OR_WRITE` permit before open, because
   opening an ESP32 serial endpoint may assert control lines or reset it;
3. open with RTS/DTR and flow control disabled;
4. observe a bounded quiet-buffer dwell and retain any bytes found; do not
   flush/discard a reset banner to manufacture a clean precondition;
5. if and only if the buffer stayed quiet, attempt exactly the bytes
   `{"T":105}\n` once;
6. read one bounded response and retain all raw bytes losslessly;
7. parse the installed firmware response under a controlled minimum-field and
   version policy while retaining unknown fields; and
8. close once and record cleanup.

The fake runner's synthetic T=1051 field list must not be assumed to be the
physical firmware schema. Malformed data is tested against the emulator; random
or fuzz commands are never sent to the real arm.

### Manual energization

No provider controls robot power. Before the UI displays any instruction that
could cause actuator off-to-on transition, the coordinator durably records and
arms a unique `MANUAL_ENERGY_CHANGE` attempt plus `EnergizationEnvelope`.
Stage 11 ends with proven de-energization. Stage 12, bootstrap calibration, and
each later motion campaign require a new envelope; no earlier review or power
event is standing authority. Recording helpers may capture the static camera or
an independent video source, but a recording failure after energization cannot
become a normal retry. The operator and observer record the actual final power
state, startup motion classification, E-stop use, collision/contact, and
certainty. Emergency de-energization remains possible without software.

### Noncontact runner

Resolve the Stage-13/14 authority ordering with an external reviewed flow:

1. Stages 1-12 produce a zero-command-motion diagnostic candidate.
2. A reviewed `BootstrapMotionPermit` may authorize only a conservative
   empty-cell envelope derived from external measurements, hard mechanical and
   software limits, reduced speed/acceleration, small incremental moves,
   observer/E-stop readiness, and no installed keyboard, phone, or contact
   tool. It cannot authorize Stage 14.
3. The sealed bootstrap report supports a separately reviewed reference
   characterization plan. Only after that report closes the required
   transforms and free-state TCP may a `CommissioningMotionPermit` authorize
   one exact noncontact plan; neither permit accepts arbitrary commands.
4. The separate runner uses the same cell-global attempt/effect and quarantine
   ledgers as the wizard:

   ```text
   INTENT_DURABLE -> EFFECT_ARMED -> EFFECT_OBSERVED
                                  -> CLEANUP_CONFIRMED -> SEALED_KNOWN
                                  -> SEALED_UNCERTAIN + global quarantine
   ```

5. Each command binds build, session, configuration epochs,
   controller/camera identities,
   calibrations, collision report, route, speed/acceleration/workspace/duration
   limits, interlocks, observer/E-stop declarations, nonce, expiry, and
   `contact_allowed: false`.
6. The runner stops after any uncertainty and never reconnects, retries, homes,
   or parks automatically.
7. The wizard imports and independently verifies the immutable report for
   Stages 13-14.

This design keeps all motion code outside the wizard package and makes it
possible to audit that the wizard cannot emit `T=104`.

## 11. Evidence, native frames, and exports

### Existing session storage retained

The current immutable header, journal/high-water, and evidence package format
remain canonical for ordinary receipts and documents. Uploads first enter a
bounded staging directory outside the session. Only the backend verifies and
publishes them; operators never browse or edit the session directory.

Every visible evidence item carries:

- provenance: `OPERATOR_UPLOADED`, `WIZARD_GENERATED`, or
  `PROVIDER_CAPTURED`;
- exact stage, human label, capture time, media type, byte count, and SHA-256;
- source/provider/identity/settings hashes as applicable;
- receipt, assessment, decision, and predecessor references; and
- current or invalidated status.

Replacing a bad item means appending a new item and receipt. Nothing is edited
or deleted.

### Chunked native-frame dataset

The minimum packed B0477 native YUY2 payload is
`5472 * 3648 * 2 = 39,923,712` bytes, about 38.1 MiB. A negotiated buffer can be
larger because of row padding and transport metadata. Even the packed payload
cannot fit the current 32 MiB single-evidence limit, and 32 packed samples total
`1,277,558,784` bytes before padding, derived images, and metadata. The
implementation must not raise limits without a new bounded format and disk
preflight.

Add a manifest-last content-addressed dataset with:

```text
dataset-<dataset-sha256>/
  chunks/
    chunk-000000-<sha256>.bin
    ...
  manifest.json                 published last by the qualified storage adapter
```

The manifest records:

- schema/version, dataset purpose, session/stage, and source/provider hashes;
- ordered chunk hashes and bounded sizes;
- full reconstructed object hash and byte length;
- per-frame offset/length/hash, width, height, FOURCC, exact row stride and
  padding, row origin, chroma order/siting, colorimetry, and range;
- request/readback settings, frame/timing records, and raw-to-derived
  transformation hashes;
- separately hashed lossless calibration images and downsampled previews;
- maximum chunk count, frame count, total bytes, and required free-disk margin;
- payload-first/manifest-last publication and reconstruction verification.

The dataset directory name is derived from a canonical **manifest-core** digest
that excludes its own digest and location-dependent filename. The completed
manifest stores that core digest; verification recomputes it, verifies every
chunk, and rejects cycles, self-hash claims, reordered chunks, trailing bytes,
or unreferenced payload. Publication is called power-loss durable only after the
Windows adapter in Section 6 passes on-volume qualification.

Keep each chunk below the existing per-item bound. Add controlled policy fields
for dataset count, per-dataset and per-session bytes, and a minimum free-space
multiple before capture. Calibration acquisition must reserve its complete
bounded budget before opening the camera. A preview is always labelled
`PREVIEW — NOT NATIVE EVIDENCE`; a JPEG can never be reported as native YUY2.

### Native capture and calibration-image datasets

Do not make one schema carry two different claims:

- `NativeCaptureDataset` proves identity-bound UVC negotiation, raw sample
  structure, freshness, timing, accounting, and raw-to-derived provenance.
- `CalibrationImageDataset` contains lossless decoded calibration images,
  exact transforms back to retained native sample hashes, target detections,
  view metadata, and a precommitted partition assignment.

Before physical acquisition, commit view IDs and purposes into three disjoint
groups: development/training, model-selection/diagnostic folds, and an
untouched one-time final acceptance set. Counts are selected by a reviewed
coverage/power analysis; the synthetic `24/8` convention is not copied blindly.
No threshold, distortion model, exclusion rule, or solver option may be changed
after final-acceptance images are inspected. Overlap, relabeling, replacement,
or second use of the final set blocks the calibration release.

### Calibrated detector image space

The B0477 native image has `19,961,856` pixels, above the current detector cap
of `12,000,000`. No adapter may silently resize it or simply raise the cap.
Before physical calibration, select and source-bind one of two qualified modes:

1. native `5472 x 3648` detection with an explicitly raised bound plus measured
   memory, time, cancellation, and worst-case-candidate limits; or
2. a fixed `3:2` calibrated working image with an exact deterministic resampler,
   pixel-center convention, native-to-working transform, transformed
   intrinsics, covariance propagation, and replay back to native sample hashes.

All thresholds, corners, residuals, overlays, and poses name their pixel space.
Mixed/native/working coordinates, implicit OpenCV defaults, aspect changes, or
an unqualified resolution are blocking.

### Physical sensor session and replay

Synthetic `sensor_session` evidence remains a different schema. Add a physical
recorded-session schema that retains:

1. raw native transport/frame bytes;
2. decoded distorted pixels;
3. undistorted/cropped/scaled pixels;
4. exact UVC identity, mode, settings, driver, and transform chain;
5. timing brackets and freshness basis;
6. all AprilTag candidates, corners, decision margins, rejections, inlier mask,
   residuals, and covariance method; and
7. calibration/pose/output hashes.

Replay must reproduce raw hash -> normalization -> detection -> pose ->
calibration result. Host-receipt timing remains explicitly weaker than genuine
device-exposure timing.

Status pages may use a fast verification tier that checks bounded metadata,
heads, indexes, and previously verified object digests. Before any mutation,
review commit, effect, export, bundle construction, or promotion, the backend
must perform full reconstruction and hash verification of every referenced
object. A fast check never confers authority. Multi-hundred-megabyte and full-
GiB campaigns are opt-in slow tests; normal CI uses small structural fixtures
with the identical manifest and fault semantics.

### Calibration phases and target-error budget

Commissioning calibration is predecessor-linked and cannot skip forward:

```text
external-geometry bootstrap
-> measured reference characterization
-> independently permitted noncontact qualification
-> untouched final acceptance
```

Bootstrap artifacts use conservative external measurements and reduced motion;
they never authorize noncontact acceptance. Stage 8 supplies installed
intrinsics and camera-to-board registration. Stage 13 supplies arm/controller-
to-board correlation, free-state TCP, and device maps. Contact compliance,
loaded TCP, force, and surface actuation stay open for later contact releases.

For every keyboard and phone target, use the controlled conservative linear
bound at the target plane:

```text
E_total = board_pose
        + intrinsics_and_distortion
        + camera_board_registration
        + static_support_drift
        + arm_board
        + controller_correlation
        + free_tcp
        + device_pose
        + motion_repeatability
        + timing_and_settling
```

Each term carries its frame, operating domain, sample basis, bound method,
coverage, dependency hashes, and freshness. Missing, stale, or out-of-domain
terms are unbounded and blocking. RSS/covariance combinations remain diagnostic
unless independence is proved. The implemented conservative scalar erosion
requires a source-bound certificate for the target-centered safe-polygon
inradius and a source-bound certificate for the complete tool-footprint
circumradius, then subtracts those plus the guard. This is a conservative radial
substitute for polygon erosion; uncertified bare radii are rejected. `E_total`
must fit the remaining radius. Every result binds the policy digest and a
canonical manifest of all term, binding, clock, epoch, and geometry inputs.
The current sensitivity model is explicitly unmeasured: keyboard gaps were not
sampled, and 27 of 29 example phone targets had a sampled gap with worst margin
`-756 micrometres`. If stock Android QWERTY does not close, the frozen fallback
order is smaller characterized passive stylus, larger purpose-built UI, local
visual refinement, then mechanical precision improvement or a different arm.

### Commissioning bundle

Stage 15 produces one immutable `CommissioningBundle`, not a directory of
implicitly related files. It binds the four phase digests above, exact source
and configuration epochs, identities, global ledgers/quarantine state, dataset
partitions, transforms, target maps, error-budget decisions, provider/runner
implementations, reviewer decisions, open blockers, and predecessor graph.
Its controlled stage catalog defines exactly 39 different top-level required
components, from source/provider bindings through phase receipts, transforms,
maps, accuracy decisions, ledger heads, reviewer decisions, and open blockers;
each has exactly one producer stage. Independently, the static Phase-1
calibration dependency manifest also happens to contain 39 namespaced entries:
15 shared graph entries plus complete 12-entry keyboard and 12-entry phone
closures. Those calibration entries are not the bundle's top-level components
and must not be substituted for them.
Its physical release effect is always `NONE`. The physical runtime loader must
accept this typed bundle or fail closed; it has no nominal calibration,
identity, target-map, or transform fallback.

### Export and independent anchoring

Stage 15 creates a manifest-last, exact-file export outside the active session
directory. It contains the verified header, journal, high-water record,
cell-global attempt/effect and quarantine ledgers, evidence/dataset manifests,
reason-code summary, invalidation graph, provider accounting, calibrations,
imported noncontact reports, the `CommissioningBundle`, accuracy decisions,
open blockers, and an explicit zero-authority statement.

Unkeyed hashes establish integrity relationships, not operator authentication.
Before a physical release, independently anchor the export with at least one of:

- a reviewer-signed manifest;
- an off-machine read-only copy whose digest is recorded separately; or
- an approved WORM/evidence store.

## 12. Build/freeze and configuration lifecycle

The implementation uses three distinct configuration moments:

### A. Pre-arrival architecture migration

First land and validate the additive v2 foundation while `runtime_activation`
remains false. Preserve the existing canonical 15-stage source and stage-plan
hash. Legacy v1 sessions remain read/verify/export-only after activation; they
are never upgraded in place and cannot run effectful actions.

Create candidate Freeze 012 only after the v2 schemas, static B0477
architecture, provider IDs, evidence formats, recovery semantics, and
thresholds are reviewed. The migration must remove the legacy
arm-camera primary requirements from the canonical Phase-1 closure and replace
them with static intrinsics, static extrinsic, measured tag map, retained
support/camera settings, and route visibility requirements.

The current `refreeze_build_alignment.py` can transactionally archive and
rebind synchronized companion records, but it does not perform this semantic
camera migration by itself. Implement and test a dedicated deterministic
migration renderer first, review its dry-run diff and plan hash, then feed its
outputs through the existing refreeze transaction. Preserve Freeze 011 and all
older archives byte-for-byte.

The migration audit must enumerate every non-archived canonical source that
still requires eye-on-arm/IMX335/mast artifacts, including manifests,
calibration closures, simulation profiles, Step 13/operator instructions,
hardware candidates, build trackers, and validation tests. Historical prose
may remain only when unmistakably labelled as history or optional Phase 2.

Freeze 012 remains physically unreleased: received identity, calibration,
power, motion, and contact fields remain null/blocked.

### B. Arrival diagnostic session

The wizard collects candidate physical identity, mode, measurements, settings,
calibrations, and reports into immutable session evidence. It never writes those
values into `camera_profile`, `arm_connection`, the calibration registry, or
the active manifest during the session. This prevents a circular source-stale
workflow.

### C. Post-diagnostic promotion

After Stage 15, an independent promotion workflow consumes the verified
`CommissioningBundle` and its anchored export and creates a new controlled
freeze/configuration. It may promote only the reviewed identities/artifacts and
only the explicitly released capability. It cannot clear an unresolved global
quarantine or fill a missing physical artifact with a nominal value. Keyboard
contact and Android contact are separate later promotions, not implied by
camera or noncontact acceptance.

## 13. Implementation milestones

Milestones are ordered by dependency, not calendar time. Each milestone ends in
an independently testable, still-zero-authority increment.

### M0 — V2 foundation contracts *(implemented, zero-authority)*

Deliverables:

- this reviewed roadmap plus strict, additive contracts for effect classes,
  the 15-stage implementation catalog, progressive intake ownership,
  deferred measurement-versus-acceptance ownership, 39 bundle-component
  producers, configuration epochs, hazards, the workcell ICD, and target
  accuracy;
- one thin source-hash-bound foundation index and a read-only validator;
- zero-authority loaders with bounded parsing, duplicate-key, traversal,
  symlink, stale-source, and cross-contract checks;
- links from the master plan, README, and active onboarding runbook, while
  leaving legacy runtime behavior and the canonical stage hash unchanged.

Tests: mutate every authority-bearing and structurally controlled contract field
and every source hash; verify exact HZ-001..016, INT-001..055, eight epochs,
seven effect classes, 15 stages, source containment, immutability, and zero
hardware imports/I/O. Descriptive prose remains review-controlled rather than
falsely claimed as exhaustively mutation-locked.

Exit gate: every foundation validator passes, `runtime_activation` remains
false, all physical authorities remain false, Freeze 011 remains active and
held, and no physical session or effect is created.

### M1 — Qualified Windows durability, global leases, attempts, and quarantine

**Current checkpoint:** the M1 core application slice is implemented and
hardware-incapable. It includes the qualified publication adapter, strict
qualification-report loader, stable anchor plus fresh-startup comparison,
ordered leases and explicit stale-owner reconciliation receipts, separate
attempt/quarantine ledgers, v2 session persistence, and a lease-owning facade
for initialize/create/verify/evidence-only recovery. A new v2 session is refused
while a global attempt is unresolved or quarantine is latched. The facade has
no effect, worker, device, power, motion, or contact method.

With the core implementation and CLI/runbook cutover complete, the remaining
M1 qualification work is: complete fault injection at every durability boundary,
independent review of the Windows behavior on the final deployment host/volume,
and an external/off-machine anchor for coordinated rollback resistance. Torn
or unexpected suffixes and stale owner metadata remain manual-review stops;
they are never silently adopted or deleted. The exact safe workflow and current
limits are in
[M1 qualified zero-hardware onboarding runtime](M1_ZERO_HARDWARE_RUNTIME.md).

Deliverables:

- `CELL -> SESSION -> CAMERA -> ARM_CONTROLLER` `LockFileEx` lease ordering
  with process-owner metadata and challenge recheck;
- append-only global attempt/effect and quarantine ledgers with independent
  heads, exact recovery rules, and v1 read/verify/export compatibility;
- an NTFS-qualified publication adapter using bounded same-volume files,
  write-through/flush/replace semantics, deterministic torn-tail recovery, and
  an on-volume startup durability self-test;
- fail-closed startup: physical effects unavailable if filesystem or durability
  qualification is missing.

Tests: two-process races; process and power-loss injection at every lock,
append, flush, replace, and head boundary; disk full, short write, antivirus
lock, reparse/symlink/hardlink/traversal, suffix deletion, coordinated tamper,
global quarantine across new sessions, and legacy v1 mutation rejection.

Exit gate: a possible effect cannot start without a globally visible
`INTENT_DURABLE`; an armed but unsealed attempt becomes reconciliation-only and
globally quarantined; no restart or new session can replay or bypass it.

The implemented facade demonstrates the no-replay and cross-session admission
semantics with zero hardware authority. The full milestone exit gate remains
open until M2 makes this storage path mandatory for every possible effect and
the remaining deployment/fault qualification is independently accepted.

### M2 — Authority, bounded workers, one-use permits, and every energization

Deliverables:

- `CellCommissioningCoordinator`, closed effect-class registry, fixed worker
  executable hashes, and one-use exact-operation permits;
- self-contained worker protocol with strict IPC, resource ceilings, accounting,
  timeout/cancellation, and cleanup reports;
- `EnergizationEnvelope` schema and ceremony for every actuator off-to-on
  transition, including a proven final de-energized state;
- serial-open classified as a possible effect and emergency de-energization
  explicitly outside software permission checks.

Tests: permit expiry/reuse/substitution, class escalation, unregistered worker,
malformed/truncated IPC, worker death at every boundary, double click, wrong
lock order, serial-open reset simulation, repeated energization attempts, and
unknown final power state.

Exit gate: exactly one registered campaign can consume a permit; its first
possible effect follows `EFFECT_ARMED`; every energization is separately bound;
uncertainty seals and quarantines with no retry.

### M3 — Progressive intake, datasets, export/bundle, and accuracy budget

Deliverables:

- due-stage intake service implementing the exact INT ownership map and keeping
  `INT-055` post-diagnostic;
- separate chunked `NativeCaptureDataset` and `CalibrationImageDataset`
  packages, manifest-core digests, quotas, reconstruction, and disk preflight;
- precommitted development/model-selection/untouched-acceptance partitioning;
- calibrated detector-image-space contract for the B0477 native pixel count;
- export verifier, four-phase `CommissioningBundle` candidate/builder, and
  conservative target-plane accuracy assessment with no nominal fallback.

Tests: early/missing/duplicate intake facts; stride/padding and chunk faults;
manifest cycles/self-hash/reorder/trailing bytes; partition overlap/reuse;
native/working pixel-space mismatch; missing/stale/out-of-domain accuracy terms;
bundle predecessor/source/epoch/quarantine drift and fallback attempts.

Exit gate: small CI fixtures exercise the full structure, opt-in full-GiB tests
pass under quotas, and no package/budget/bundle result grants physical authority.

### M4 — Reviewed Stage-3 slice, shared service, and terminal wizard

Deliverables:

- pure `assess` and mutating `apply_review` boundaries, exact receipt/evidence/
  reviewer/current-state binding, typed reopen/invalidate, and reason codes;
- `ArrivalWizardService`, session list/create/resume/read-only views, and a
  terminal 15-stage stepper derived from the one canonical stage source;
- complete progressive camera-receipt flow for Stage 3, including immutable
  corrections, export, and successor-session handling;
- separate rehearsal/physical namespaces and structurally distinct provenance.

Tests: wrong/cross-session/stale receipt, forged assessment, reviewer upgrade,
evidence drift, decision replay, concurrent apply, source drift, invalidation,
rehearsal conversion, and zero hardware imports during status/preview/resume.

Exit gate: Stage 3 can be uploaded, assessed, reviewed, committed, resumed,
invalidated, and exported headlessly without device import; the rest of the
stepper is visible but locked by honest missing evidence.

### M5 — Remaining receipts and full fake 15-stage flow

Deliverables:

- strict receipt/assessment families for Stages 4-15, configuration-epoch and
  predecessor bindings, and plain-language remediation catalog;
- deterministic fake and recorded reports for camera, power, feedback,
  bootstrap, reference, noncontact, accuracy, and handoff phases;
- role-separation rules for operator, observer, assessor, reviewer, and release
  authority;
- complete rehearsal flow terminating only as
  `REHEARSAL_COMPLETE_ZERO_AUTHORITY`.

Tests: golden receipt and every missing/extra/duplicate/mismatched/stale/
uncertain/boundary field; role collisions; downstream invalidation; global
quarantine display; bundle gaps; attempts to label fake evidence physical.

Exit gate: all 15 pages complete under incapable providers, remain visibly
rehearsal-only, and exercise every reason, recovery, and terminal state without
hardware access.

### M6 — Physical-shaped B0477 provider and camera stages

Deliverables:

- Windows persistent identity/topology/media-control adapters behind injected
  backends;
- physical `B0477ConnectionProvider` implementation;
- raw YUY2 chunked capture with negotiated stride and preview/derived transform
  chain;
- explicit identity, native `3:2` mode/control, changing-stimulus freshness,
  reconnect, and cleanup campaigns, each consuming its permit before open;
- camera provider subprocess with no serial dependency;
- contract suite runnable against fake, recorded, shim, and eventual hardware
  backends.

Tests: absent/duplicate/wrong device, missing serial, index reassignment,
identity substitution, USB2, backend/mode/crop/FOURCC/control drift, stale or
short frame, timestamp anomalies, detach, timeout, and close/reopen failure.

Exit gate before hardware: every fault is deterministic with exact accounting;
under the declared local-software threat model, ordinary fake/rehearsal data
cannot satisfy physical-origin receipt construction. This is not a claim
against a trusted local administrator who can replace code or evidence. Exit
gate with hardware: Stages 3-6 capture and replay the exact received B0477.

### M7 — Physical calibration and static-registration workflow

Deliverables:

- guided focus/FOV/lighting/throughput screen at `950..1050 mm`;
- exact ChArUco board definition, print-scale evidence, and precommitted,
  disjoint development/model-selection/untouched-acceptance view IDs;
- distortion model selection without touching final acceptance, explicit
  native or calibrated-working detector resolution, native-to-undistorted
  transform, and strict artifact schema;
- measured six-tag map import/survey schema;
- installed `camera_overview_optical_T_board` solve, K0/P0 held-out checks,
  route visibility policy, and
  bump/reseat/cable/thermal/24-hour drift campaign;
- staging-only calibration registry candidate and replay tools;
- measured keyboard/phone target-map artifact builders with uncertainty/safe
  inset checks.

Tests: split overlap, wrong print scale, weak coverage, model degeneracy,
threshold boundaries, wrong mode/crop/settings/identity, corrupted transform,
tag loss/outliers, mount/lighting drift, and all 75 route visibility zones.

Exit gate before hardware: synthetic and recorded fixtures exercise every
path. Exit gate with hardware: Stages 7-8 pass only on final retained
installation and held-out physical evidence.

### M8 — Arm identity, safety, every-power envelopes, and onboarding-only T=105

Deliverables:

- strict arm/controller/supply identity receipts while actuator power is off;
- complete Stage-10 evidence/review, two-person Stage-11 possible-startup-motion
  ceremony, global attempt/quarantine integration, and proven final power-off;
- onboarding-only T105 permit and provider with no generic write/T104 method;
- a fresh Stage-12 `EnergizationEnvelope`; permit consumption before serial
  open; retained quiet-dwell/reset bytes; raw timing/bytes; lossless response;
  minimum-version policy; one-write accounting; close and final power-off;
- serial subprocess with no camera or motion dependency.

Tests: every incomplete/contradictory safety field; recording/process loss
before/after energization; unknown final power, E-stop/collision/contact;
wrong/duplicate/busy port, identity drift, dirty buffer, reset banner,
zero/partial/overlong write, timeout, disconnect, malformed/duplicate-key/non-
UTF8/overlong/multiline/wrong-T reply, extra lines, expired/reused permits,
concurrent attempts, open/reset failure, cleanup failure, new-session bypass,
and attempts to reuse Stage-11 power authority.

Exit gate before hardware: exact outbound fixtures prove the only possible arm
bytes are `{"T":105}\n`, once, after a separately armed serial-open effect.
Exit gate with hardware: Stages 9-12 retain one clean physical exchange and end
de-energized, or fail closed and quarantine without retry.

### M9 — Stage-13 bootstrap and reference calibration

Deliverables:

- `BootstrapMotionPermit`, conservative external-geometry envelope, empty-cell
  incremental program, and a sealed bootstrap report that has no Stage-14
  authority;
- separately reviewed reference-characterization permit and bounded runner
  using the same global attempt/quarantine ledgers and fresh energization per
  campaign;
- measured joint signs/zeros/ranges/repeatability, controller correlation,
  arm-to-board transform, free-state TCP, keyboard/phone device maps, and
  observer bindings;
- complete collision/FK mapping, watchdog/interlock/feedback/cancellation/
  cleanup contracts, and no contact-capable primitive.

Tests: missing final transforms at bootstrap, envelope escalation, wrong/stale
build/epoch/identity/geometry/trajectory/interlock/observer/permit, kill at
every dispatch boundary, stall/overshoot, feedback/camera loss, E-stop, power
loss, cleanup uncertainty, and automatic-home/park/retry attempts.

Exit gate before hardware: an incapable hardware emulator proves phase ordering,
accounting, fresh-power envelopes, and fail-stop behavior. With hardware,
Stage 13 accepts only predecessor-linked held-out evidence; contact compliance
and all contact authority remain open.

### M10 — Stage-14 noncontact acceptance and Stage-15 bundle

Deliverables:

- exact empty-cell stop/power-loss/settling/park programs and one-device-at-a-
  time hover/visibility programs under separately reviewed permits;
- arm-induced camera-visibility assessment and untouched final acceptance;
- target-by-target keyboard/phone noncontact error-budget closure with the
  predefined fallback decision when stock Android targets do not fit;
- Stage-15 dependency graph, verified `CommissioningBundle`, report, blocker
  list, export, promotion request, and independent anchor procedure.

Tests: collision/visibility/settling/route/target margin boundaries; changed
threshold after acceptance reveal; stale epoch; wrong permit/report; missing
phase; open quarantine; nominal-fallback injection; bundle reorder/tamper; and
attempted `PASS` instead of `COMPLETE_DIAGNOSTIC`.

Exit gate: rehearsal reaches only zero-authority completion. With reviewed
physical reports, diagnostic mode may reach `COMPLETE_DIAGNOSTIC`; it still
grants no runtime, power, contact, typing, or promotion authority.

### M11 — Browser, packaging, and prospective static-primary Freeze 012

Deliverables:

- server-rendered loopback UI over `ArrivalWizardService`, controlled local
  assets, launch/session/CSRF tokens, Host/Origin/CSP/no-store protections, and
  accessible keyboard/screen-reader/high-contrast behavior;
- one-command launcher, bounded gallery/uploads, integrity/reconciliation/
  export pages, pinned dependencies, and offline operator/recovery manual;
- deterministic static-primary semantic migration renderer, exhaustive affected-
  source inventory, prospective manifests/calibration closures/simulations,
  dry-run diff, plan hash, and transaction rehearsal;
- proof that the prospective Freeze 012 retains false power/motion/contact/
  release authority and leaves old freezes byte-identical.

Tests: GET side-effect audit; CSRF/cross-origin/DNS-rebinding/Host spoof; XSS,
body bombs and traversal; refresh/two tabs/processes/restart; semantic parity of
canonical browser/terminal requests and results; accessibility; migration
determinism, rollback, and archive preservation.

Exit gate: browser and terminal are semantically equivalent despite transport-
specific cookies/nonces/timestamps; the prospective tree has no canonical
Phase-1 eye-on-arm requirement, but Freeze 012 is not applied yet.

### M12 — Independent qualification, controlled apply, and first V2 session

Deliverables:

- full fake 15-stage qualification, source-surface and byte-fixture audit,
  security review, independent safety/hazard review, and all fast/full/slow
  verification evidence;
- final Freeze-012 dry run and plan hash, transactional apply, old-archive
  verification, full post-apply validation, and independent sign-off;
- first physical session creation only after v2 activation gates, Windows
  durability self-test, global-quarantine check, role assignment, and verified
  zero-I/O startup;
- installed hardware-profile dependency slots remain unfilled and blocking
  until each arrival stage measures them; `INT-055` is closed only by a later
  controlled release-freeze transaction.

Exit gate: active Freeze 012 is the static-primary, physically unreleased
baseline; every controlled source is stable; the first V2/effect-capable arrival
session starts at Stages 1-2 with zero device access; keyboard and Android
contact remain false. This does not deny the existing legacy diagnostic session.

## 14. Verification strategy

### Test layers

1. **Unit:** strict parsing, canonical serialization, hashes, reason codes,
   assessments, permits, attempts, quarantine, epochs, energization envelopes,
   quotas, transforms, accuracy budgets, bundles, and state mappings.
2. **Property/state-machine:** arbitrary valid/invalid transition sequences,
   receipt field perturbations, resource bounds, idempotency, and invalidation.
3. **Provider contract:** one shared suite against incapable fake, deterministic
   physical-shaped fake, recorded replay, OS shim, and later real hardware.
4. **Integration:** launcher -> service -> session/global ledgers -> evidence/
   dataset -> assessor -> bundle/export across all 15 stages in rehearsal mode.
5. **Kill/fault injection:** terminate before/after every persistence,
   provider-open, capture, write, response, cleanup, and report boundary.
6. **UI/security/accessibility:** loopback isolation, hostile requests,
   concurrency, refresh/restart, keyboard, screen reader, and visual labels.
7. **Hardware acceptance:** small stage-specific tests only after every earlier
   software gate passes; never fuzz the real arm.

### Mandatory invariant tests

- Page load, list, status, preview, resume, verify, and export cause zero device
  operations.
- Stages 1-12 cannot import or reach T104, arbitrary write, motion, power, or
  contact code.
- Every possible effect has `INTENT_DURABLE`, then consumes an exact permit as
  `EFFECT_ARMED` before camera open, energization instruction, serial open, or
  external motion dispatch.
- Crash before `EFFECT_ARMED` yields zero provider calls/effects and may seal
  `ABORTED_PRE_EFFECT`; crash after it yields reconciliation-only plus global
  quarantine until reviewed resolution.
- Two concurrent requests can produce at most one provider call and one legal
  global-attempt suffix; cell lock is always acquired before session lock.
- A new process, runner, or session cannot bypass a cell/device quarantine.
- V1 sessions remain verifiable/exportable but reject v2 effects and in-place
  migration.
- Every physical receipt binds the exact session, cell, source closure, stage
  plan, epoch vector, stage, provider/worker implementation, identity, global
  ledger heads, evidence, and predecessors.
- Under the declared local-software threat model, synthetic/rehearsal evidence
  cannot parse as physical-origin evidence; no claim is made against an
  administrator able to replace trusted code and keys.
- Operator review cannot upgrade a failed or uncertain assessment.
- Required operator, observer, assessor, reviewer, and release roles cannot be
  silently collapsed where the hazard policy requires separation.
- Unknown before an effect blocks; ambiguous after a possible effect becomes
  terminal uncertainty.
- Identity is rechecked at every open boundary; no camera or port fallback.
- Every actuator off-to-on transition has a fresh envelope. Stages 11 and 12
  each end disconnected; every Stage-13 and Stage-14 external campaign also
  requires independently proven final disconnection.
- T105 consumes its permit before serial open and permits one exact write
  attempt; T104 count is permanently zero.
- Failed close/cleanup is evidence and prevents pass.
- Progressive intake closes exactly the rows due at each stage; `INT-055` stays
  post-diagnostic.
- Camera freshness requires a changing visible stimulus, not only different
  hashes, and every detection names a qualified pixel space.
- Development, model-selection, and untouched-acceptance dataset partitions
  are precommitted, disjoint, and immutable before capture or acquisition.
- Bootstrap evidence cannot authorize reference or Stage-14 motion; every phase
  verifies its predecessor.
- Any missing/stale/out-of-domain accuracy term is unbounded and blocking.
- Stage 15 validates one `CommissioningBundle`, accepts no nominal fallback,
  and is `COMPLETE_DIAGNOSTIC` with zero physical release effect.

### Required fault matrix

| Area | Cases that must be injected | Required result |
|---|---|---|
| Source/stage | Source drift, stale head/challenge/evidence inventory, wrong stage/order/session, reused token | No provider call or journal mutation |
| Parser/assessor | Missing/extra/duplicate fields or keys, nonfinite/forbidden numbers, tampered hash, forged authority/disposition | Reject; never pass |
| Review | Acknowledge hold/uncertainty, wrong reviewer, evidence changes after preview, replayed decision | Cannot upgrade; stale/replay rejected |
| Concurrency | Double click, two tabs/processes, wrong lock order, lock loss, restart during POST, new session under quarantine | At most one append/effect; other caller gets busy/stale/quarantined |
| Journal/evidence | Kill at temp write/link/flush/replace/head/manifest, power loss, failed Windows startup self-test, disk full, permissions, antivirus lock, symlink/reparse/hardlink, suffix deletion | Prior verified state or detectable unsealed attempt; quarantine if effect certainty is lost; never replay |
| Web | CSRF, cross-origin, Host/DNS rebinding, GET side effect, XSS metadata, body bomb, traversal | Request rejected; no backend import/effect |
| Worker/IPC | Startup failure, truncation, timeout, unexpected exit, cancellation, cleanup exception | Known pre-effect block or post-effect uncertainty; no retry |
| Camera identity | None/multiple/wrong unit, missing serial, persistent collision, index reassignment, substitution | No open |
| Camera mode | USB2, backend fallback, false mode-set success, crop/scale/FOURCC/control drift | Close once; block |
| Camera frame | Wrong negotiated length/stride/padding, partial/repeated/rewrapped frame, unchanged stimulus, fake sequence/timestamp, latency/drop, unplug | No freshness pass; cleanup visible |
| Detector space | Native image over old pixel cap, implicit resize, aspect/pixel-center change, wrong intrinsics/covariance space | Reject before detection/calibration |
| Dataset | Missing/duplicate/reordered/tampered chunk, early manifest, self-hash cycle, trailing bytes, partition overlap/reuse, resource bomb, derived mismatch | Reject dataset; no calibration |
| Serial preflight | Wrong/multiple/busy port, identity drift, expired permit, open-triggered reset, buffer unavailable/dirty, RTS/DTR drift, reset banner | Permit consumed before open; zero writes when pre-request evidence is dirty; uncertain open effects quarantine |
| T105 | Partial write, exception, timeout, disconnect, malformed/stale/wrong/multiline response, extra buffer, permit race | Permit consumed; no retry; uncertainty where effect/post-state is ambiguous |
| Energization | Missing/reused/expired envelope, unknown initial/final power, Stage-11 envelope offered at Stage 12, observer/E-stop drift | Do not instruct energization, or quarantine after possible energy change; emergency off remains available |
| Calibration | Split overlap/reveal/reuse, scale error, poor coverage, degenerate solve, bad untouched residual, tag/mount/settings/epoch drift | Reject/invalidate; no promotion |
| Bootstrap/noncontact | Missing predecessor, bootstrap escalation, wrong permit/report hash, stale interlock, collision unknown, stall/overshoot, feedback/vision loss, E-stop/power loss | Stop dispatch; global quarantine and immutable partial report; no subsequent command |
| Accuracy/bundle | Missing/stale/unbounded term, unsafe eroded region, fallback injection, component/epoch/head mismatch, phase reorder, open quarantine | Reject budget/bundle; no handoff/promotion |
| Surface audit | Enumerate routes, public methods, imports, and outbound byte fixtures | No power, raw serial, T104, motion, descent, or contact surface in wizard |

Normal CI uses bounded structural dataset fixtures. Full native-frame and GiB-
scale campaigns are explicitly marked opt-in slow and run before arrival
qualification. The full non-slow suite, required slow campaigns, mypy,
compile/import checks,
controlled-source verification, build-alignment validation, and dependency audit
must all pass before an arrival build is frozen.

## 15. What can be completed before hardware, and what cannot

### Complete now with simulation, fakes, shims, and recorded fixtures

- all contracts, reviewed-state transitions, global attempt/quarantine records,
  Windows storage adapter/shims, locks, permits, energization envelopes,
  configuration epochs, evidence/dataset formats, bundles, exports, and
  recovery logic;
- terminal and browser wizard screens for every stage;
- full Stage-3 reviewed vertical slice and fake versions of all later stages;
- camera/arm provider contracts and OS adapters behind injected test backends;
- exact B0477 native-format normalization, chunking, replay, synthetic
  calibration, explicit detector pixel spaces, target-map builders, target
  error-budget logic, and visibility policies;
- T105 outbound-surface proof and complete protocol emulator fault matrix;
- noncontact permit/ledger/runner against a hardware-incapable controller peer;
- source migration renderer and prospective static-primary Freeze 012;
- security, accessibility, concurrency, crash, and tamper qualification;
- packaging, one-command launcher, offline runbook, and export verification.

### Must wait for received hardware

- the received B0477/lens/case/cable identity and dimensions;
- a stable persistent Windows camera identity and actual USB topology;
- actual native media modes, manual controls, freshness, throughput, latency,
  dropped frames, and close/reopen behavior;
- one-metre focus, usable FOV, distortion, depth of field, glare, lighting, and
  tag pixels;
- final support stiffness, vibration, settling, cable pull, collision clearance,
  bump/reseat, thermal and 24-hour drift;
- physical intrinsics, measured tag map, static camera-to-board transform,
  controller/arm/board correlation, free-state TCP, and repeatability;
- the received RoArm/controller/supply/firmware identity;
- physical E-stop effectiveness, gravity behavior, automatic startup sweep, and
  power-loss consequence;
- the one physical T105 response;
- real collision, stop, empty-cell, noncontact hover, and safe-park behavior;
- loaded-tool/contact compliance, keyboard key travel/force/outcome, and Android
  touch/outcome behavior.

Simulation proves software behavior under declared models; it cannot certify
those physical facts.

## 16. Arrival-day operating sequence after implementation

1. Leave camera USB, arm USB, and arm 12 V disconnected. Run the controlled
   launcher and require host/build/source/rehearsal PASS.
2. Initialize or verify the qualified M1 store on its final approved local fixed NTFS volume, then
   create and cross-verify one uniquely named physical v2 diagnostic session.
   Stages 1-2 run zero-I/O verification only after the later reviewed service
   is implemented.
3. Complete only the Stage-3-due intake rows and B0477 receipt inspection.
   Leave every later-owned row visibly pending; review Stage 3.
4. Connect only the B0477 directly to the approved USB 3 port. Qualify persistent
   identity, mode/controls, freshness, and reconnect behavior in Stages 4-6.
5. Use Stage 7 only for preliminary focus/FOV/lighting/throughput screening and
   to freeze the acquisition plan. Then retain the final gantry/camera/lens/
   focus/aperture/cable/light stack. With arm 12 V physically disconnected,
   Stage 8 captures production data and validates installed intrinsics,
   measured tag map, camera-to-board registration, held-out K0/P0, visibility,
   and drift.
6. Keep actuator 12 V disconnected. Connect only the controller USB and bind
   arm/controller/supply identity in Stage 9 without opening the port.
7. Complete the physical E-stop, containment, anti-shift, cabling, startup
   sweep, empty-cell, and two-person power-safety review in Stage 10.
8. With the observer at the physical E-stop, perform one manual power event
   while the host sends zero commands. Record and review Stage 11, prove final
   de-energization, and disconnect actuator power.
9. If and only if Stages 9-11 pass and global quarantine is clear, create a new
   Stage-12 energization envelope. Consume the serial permit before port open,
   make exactly one T105 query, close, manually de-energize, and prove final
   state. Do not retry a failure.
10. Independently review a conservative empty-cell bootstrap permit, run and
    seal it, then review the separate reference-characterization permit. Import
    the predecessor-linked reports for Stage 13; they still grant no Stage-14
    or contact authority.
11. Issue separate noncontact permits for empty-cell and one-device-at-a-time
    hover/visibility campaigns. Import reports, evaluate untouched acceptance
    and target budgets, then build and independently review the Stage-15
    `CommissioningBundle`. Finish as `COMPLETE_DIAGNOSTIC`.
12. Close `INT-055` and promote any eligible noncontact capability only in a
    separate controlled freeze transaction that consumes the verified bundle
    and cannot bypass quarantine.
13. Qualify keyboard contact and Android contact separately, starting with
    non-destructive dummy contacts and large targets. Neither is part of the
    arrival wizard's authority.

## 17. Definition of done

### Pre-hardware wizard-ready

- [ ] All 15 stages have exact definitions, receipts, assessors, reason codes,
  recovery, and simulated pages.
- [ ] Stage 3 works end to end through upload, assessment, review, journal,
  resume, invalidation, and export.
- [ ] Browser and terminal use the same service and produce the same records.
- [ ] Status/preview/resume import no hardware backend and perform zero I/O.
- [ ] Every mutation requires a fresh challenge; every effect acquires the
  cell-global then session lease and consumes a one-use exact-operation permit.
- [ ] Concurrent requests produce at most one effect.
- [ ] Every kill point fails closed; an armed unsealed attempt becomes globally
  quarantined and reconciliation-only; no session/process/runner can replay or
  bypass it.
- [ ] The Windows durability self-test passes on the deployment volume before
  effectful physical mode is available.
- [ ] Every energization has its own envelope and proven final power state.
- [ ] Configuration-epoch changes invalidate all dependent artifacts.
- [ ] Progressive intake ownership is exact and `INT-055` remains
  post-diagnostic.
- [ ] Rehearsal and physical evidence are structurally non-interchangeable.
- [ ] Native-frame chunking reconstructs exactly and rejects all tampering and
  resource-boundary faults.
- [ ] Dataset partitions are precommitted/disjoint and every detector result
  identifies a qualified native or calibrated working image space.
- [ ] Accuracy evaluation treats every missing/stale/out-of-domain term as
  unbounded and blocking; the bundle loader has no nominal fallback.
- [ ] Every camera and T105 fault has exact provider accounting and cleanup
  evidence.
- [ ] Static audit proves no wizard route/method/import can emit power, T104,
  arbitrary serial, motion, descent, or contact.
- [ ] UI security and accessibility suites pass.
- [ ] Candidate Freeze 012 aligns the canonical Phase-1 path to static B0477
  while every physical authority remains false.
- [ ] Full tests, type checking, compile checks, build validation, and an
  independent safety review pass.

### Camera arrival-ready

- [ ] Stages 3-8 can run while the RoArm remains unpowered.
- [ ] Exact physical-origin identity/mode/control/raw-frame evidence cannot be
  manufactured through the ordinary fake provider under the declared threat
  model.
- [ ] Physical thresholds are controlled inputs, not copied from synthetic
  fixture values.
- [ ] Raw and derived data replay independently to the same accepted result.

### Arm diagnostic-ready

- [ ] Stages 9-11 are reviewed under the required physical states.
- [ ] Stage 11 ends de-energized; Stage 12 requires a new envelope, consumes its
  permit before serial open, sends only exact T105 bytes once, and ends
  de-energized.
- [ ] Tests and provider accounting prove T104, retry, reconnect, initialization,
  homing, and motion counts remain zero.
- [ ] Any ambiguous action becomes reconciliation/uncertainty rather than retry.

### Noncontact-ready

- [ ] Stage-13 bootstrap and reference artifacts are separately permitted,
  predecessor-linked, and pass dependency and held-out validation.
- [ ] A separate release authorizes only an exact empty-cell/noncontact plan.
- [ ] The noncontact runner has a durable global command/effect ledger and exact
  plan/collision/interlock bindings.
- [ ] Stage 14 only imports verified reports; the wizard has no motion adapter.
- [ ] Stage 15 verifies a complete accuracy budget and immutable
  `CommissioningBundle`, then ends as `COMPLETE_DIAGNOSTIC` with no contact
  authority.

### Typing/tapping-ready — later releases, outside this plan

- [ ] Keyboard contact is separately qualified and released.
- [ ] Android contact is separately qualified and released.
- [ ] Each descent requires a fresh accepted board/device observation.
- [ ] Every contact retracts and has independent outcome verification.
- [ ] An ambiguous physical outcome is never automatically repeated.

## 18. Immediate execution queue

The next implementation work should proceed in this order:

1. M0 is complete: retain and revalidate the source-bound additive
   zero-authority contract set without changing runtime authority.
2. M1 core and its CLI/runbook cutover are implemented: retain the zero-hardware
   facade, then complete exhaustive durability fault injection, final-volume
   independent qualification, and external rollback anchoring before an effect
   cutover.
3. M2: implement closed authority classes, workers, permits, and every-
   energization envelopes.
4. M3: implement progressive intake, native/calibration datasets, export,
   `CommissioningBundle`, detector space, and accuracy budget.
5. M4: build the reviewed Stage-3 vertical slice, shared service, and terminal
   wizard.
6. M5: add the remaining receipts and qualify the full fake 15-stage flow.
7. M6-M7: implement B0477 Stages 4-8 against fakes/shims/recordings before the
   received camera.
8. M8: implement arm identity, safety, Stage-11/12 power envelopes, and exact
   T105 flow against the emulator.
9. M9-M10: implement bootstrap/reference and final noncontact/bundle workflows
   against an incapable motion peer.
10. M11: add the browser/packaging and finish the prospective Freeze-012
    migration without applying it.
11. M12: complete independent qualification, transactionally apply Freeze 012,
    revalidate, and only then create the first physical-arrival v2 session that
    can participate in the effect-capable coordinator while still starting at
    zero I/O.

The first vertical slice is intentionally Stage 3: it proves the complete
evidence -> receipt -> deterministic assessment -> human review -> journal ->
resume -> export chain without touching hardware. Once that seam is correct,
the later provider-backed stages plug into it without changing the trust model.

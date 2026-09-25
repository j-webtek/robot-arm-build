# Remaining wizard stages: implementation map

## Next-slice decision after stages 9–11 integration

Implementation follow-up: the stage-12 design below is now implemented in the
incapable shared service, including full private transactional retention,
independent synthetic post-worker observation, exact original-store verification
and raw-free browser/terminal projections. See the
[feedback integration contract](WIZARD_FEEDBACK_INTEGRATION.md) and
[implementation record](WIZARD_IMPLEMENTATION_PROGRESS.md) for executed checks.
The decision sequence below is retained as design rationale. The bounded
[stage-13 reference rehearsal](WIZARD_REFERENCE_INTEGRATION.md) is now implemented;
consult the implementation record for completed verification. Stages 14–15 and
all physical intake/activation remain pending; no existing physical hold changed.

The read-only [reference-frame next-slice audit](WIZARD_REFERENCE_FRAME_NEXT_SLICE.md)
maps existing transform/FK/IK and graph checks, exact stage-12 dependencies, and
missing arm-board/controller/TCP fitting work. It remains the historical audit;
the new numerical fitter and rehearsal do not close the physical reference
acceptance criteria. A graph marker or a valid feedback packet cannot establish
calibrated joint/reference state.

The read-only follow-up audit selects **coordinator-backed incapable feedback**
for stage 12, not an optics-style evaluator that fabricates a serial exchange.
Use the existing `providers/windows/arm_feedback_worker.py::ArmFeedbackWorker.run`
with its exact registered `IncapableSerialBackend`. Wrap it in the coordinator's
`BoundedCommissioningWorker` contract, initially in-process and explicitly
incapable; keep physical/native admission held.

Required implementation order:

1. Define a lossless bounded retained-feedback contract and pure verifier:
   exact request/reviewed binding, counters/settings/errors, complete
   `SingleT105FeedbackReceipt`, ordered timing, bounded response/unexpected bytes,
   prefix/omission counts and hashes. The existing diagnostic `to_dict()` omits
   parts of wire evidence and is not by itself that contract.
2. Define coordinator registration and server-owned admission for
   `SERIAL_OPEN_OR_WRITE`, `ARM_CONTROLLER`, one open/write/close and finite
   reads/bytes/time, with zero camera frames. `_facts()` currently supplies a
   camera selection; it must select a separately bound controller for this stage.
3. Bind a fresh `EnergizationEnvelope` to exact reviewed stage-9–11 evidence.
   The current worker always reports final power UNKNOWN. A successful close
   cannot become DEENERGIZED. Model a separately retained, explicitly synthetic
   post-campaign observer contract before nominal known sealing; without one,
   preserve uncertainty/quarantine. Do not weaken the coordinator check.
4. Add a scoped complete-evidence writer before known sealing. The current
   worker protocol does not yet carry that retention boundary. Connect its
   mandatory one-use authorizer to the exact consumed admission, not an unrelated
   diagnostic helper or caller-selected identity.
5. Integrate due-stage campaign, pure assessment/review and original-store reopen;
   verify lossless evidence against audited coordinator attempts without replay.
   Test uncertain fault campaigns in independent rehearsal cells, never continue
   dispatching after quarantine.

Required faults: boot/stale bytes with zero writes; short write without remainder
or retry; malformed/wrong/extra feedback; identity change; deadline/cancellation;
close or retention failure; parent/worker disappearance; stale/duplicate admission;
raw-byte tampering; missing final-power observation; and original-store reopen.

Separate later integrations remain necessary: the owned Windows process runner
currently launches only its fixed incapable process fixture, not an arm child
with durable parent redemption. The non-purging connection facade is not in the
arm worker's closed registry and does not implement the same mutable pyserial
settings/read-timeout interface. Neither may be silently substituted. This is a
bounded development decision, not a physical startup or firmware procedure.

## Original stage audit and prior implementation notes

Audit date: 2026-09-07. Scope: canonical stages 7–15. This is an implementation
companion, not a replacement stage catalog, physical runbook, release decision,
or claim that these stages are implemented in the interactive wizard.

Read with the [connection integration plan](CAMERA_ARM_CONNECTION_INTEGRATION_PLAN.md),
[developer playbook](CAMERA_ARM_DEVELOPER_PLAYBOOK.md), and
[canonical stage catalog](../config/physical_onboarding_stage_catalog.json).
DEV-009 covers arm identity/power/feedback; DEV-010 covers installed calibration;
DEV-011 covers the full sequence, dependency invalidation, and handoff.
The existing catalog remains the sole authority for order and component owners.

Implementation follow-up: stages 7–8 have since been integrated into durable
collection/assessment/review/reopen and exercised through the public API and
browser. See the current [implementation record](WIZARD_IMPLEMENTATION_PROGRESS.md)
for exact verification and remaining tests. The audit below preserves the
distinction between those synthetic checks and unimplemented physical intake.
Follow-up: stages 9–11 now have substantive injected-identity and typed
power-procedure evaluator integration, exact retained assessment/review and
original-store reconstruction. See [the arm setup contract](WIZARD_ARM_SETUP_INTEGRATION.md)
and implementation record for executed tests. The later stage-12 follow-up is
recorded above; stages 13–15 remain held in the shared service, and all physical
intake remains pending.

Post-audit implementation note: the bounded stages 7–8 slice below is now
implemented in the interactive REHEARSAL service, with complete substantive
reports, exact assessment/review, browser/terminal check cards and original-store
reopening. The real eight-stage Windows M1 progression/reopen test passed; see
[the optics API and workflow record](REHEARSAL_OPTICS_STAGES_API.md) for the
current tested scope and negative-test evidence. The original audit below is retained
as the design rationale, not a current claim that only six stages exist.

## Current position and the next concrete slice

The browser and terminal already share an explicit prepare → confirm → execute →
poll workflow, diagnostic exports, and a durable REHEARSAL session. At this
audit, `CommissioningRehearsalService` admits only the first six stages through
`_FIRST_SIX`; its camera stages retain real binary *synthetic* datasets. Stages
7–15 are not made usable by the generic forms or by existing standalone reports.

There is substantial reusable code: the separate
`run_first_power_on_rehearsal(...)` traverses all fifteen stages, and its built-in
`DeterministicOnboardingProvider.probe(stage)` invokes real parsers, pixel
registration, feedback emulation, dependency-graph checks, and virtual missions.
However, it is not the durable interactive session implementation. Its checkpoint
resume deliberately reruns deterministic probes; **do not use that replay model
to reopen a durable commissioning store or repeat an effectful campaign**.

**Implement stages 7–8 next as one bounded substantive rehearsal slice:**

1. Add a closed, hardware-incapable stage evaluator that runs the existing
   intrinsics parser/assessment and normal plus tag-loss B0477 pixel-registration
   checks. Preserve their full reports and checks, not merely their exit code.
2. Add a strict versioned stage-evidence envelope bound to the original session,
   source/catalog, operator, stage, reviewed predecessors, selected camera,
   settings epoch, dataset references, evaluator implementation, and result hash.
   Keep nominal projection inputs distinguishable from the current binary camera
   fixture; they are not automatically the same dataset or optical calibration.
3. Extend collection/assessment/review for those two stages only after their
   evaluator and evidence verifier exist. A failed constituent check must produce
   a blocked assessment. A successful result means **rehearsal checks passed;
   installed optics/calibration still unmeasured**.
4. Present the concrete check list, partition/fit/held-out counts, residuals and
   tagged schematic provenance in the same UI. Add original-store reopen support
   for these exact receipt versions before claiming resumable stage support.
5. Test a real temporary M1 store from stage 6 through stage 8, retained-evidence
   tampering at assessment/review/reopen, and a deliberately regressed evaluator.
   The latter must stop progress even when process execution itself succeeds.

Do not copy the first-four-stage `SOURCE_BOUND_SYNTHETIC_PREREQUISITES` fixture
pattern into later stages. Do not manufacture `PASS` from “a receipt exists,”
an expected-fault match, a Boolean checkbox, or a constant nominal scenario.

## Shared integration needed for every remaining stage

| Layer | Reuse | Work still required |
| --- | --- | --- |
| Canonical stage policy | `PhysicalOnboardingStage`, `STAGE_ORDER`, `load_physical_onboarding_stage_catalog` | Read required effects, power constraints, owned artifacts and bundle producers from the validated catalog; do not add a second stage list in JS or a new independent catalog. |
| Durable state and evidence | `PhysicalOnboardingM1Runtime`, `M1CommissioningPersistence.stage_transaction`, `store_evidence`, `commit_stage_state`; V2 snapshots and invalidation | Define and verify each new receipt/result schema and predecessor linkage before advancing. The storage layer proves publication/binding, not whether a stage's technical assessment is sufficient. |
| Effect accounting | `CellCommissioningCoordinator.prepare/execute`, `RegisteredActionRequest`, `CampaignRegistration`, `AttemptResult` | Register exact stage workers and bounded effects. Keep synthetic and physical compositions separate. The current coordinator/adapter is not an activated physical executor. |
| Browser/terminal | `ArrivalWizardService`, closed `ActionDefinition` schemas; existing `rehearsal_collect/assess/review` presentation | Due-stage semantic fields, explicit effect preview, bounded result summaries, remediation and evidence selectors. No raw path/COM, provider, command, permit, or blanket hardware-enable fields. |
| Reopening | `RehearsalReopenRegistry.discover/open` | Extend its exact receipt allowlist and reconstruction per stage; verify retained results and freshness without rerunning a probe. Keep corruption, orphan data, unsupported versions and uncertainty read-only. |
| Logs and exports | `wizard_diagnostic_log`, `wizard_diagnostic_export`, assigned export root | Export technical reports plus evidence/attempt/review references and omissions. A general log ZIP is not automatically the complete commissioning bundle or native raw-evidence archive. |

Required new envelope content, with exact names/version chosen in implementation:

- Composition/domain, stage, source/catalog hashes, cell/session, operator and
  evaluator identity; exact prerequisite receipt/assessment/review references.
- Complete input manifest: camera/controller identity, settings/support/geometry
  epochs and relevant dataset hashes. Use explicit `not_applicable` fields where
  appropriate; do not drop a required dependency silently.
- Structured checks with actual observed values, thresholds, outcomes, reason
  codes, and source-report references. Record separately whether a negative test
  correctly rejected a fault and whether nominal readiness checks succeeded.
- Known attempt/cleanup result for every dispatched campaign; an assessment
  cannot turn an unresolved or uncertain attempt into known completion.
- Explicit zero physical authority and scope limitations. Source/evidence/head
  changes invalidate a prepared ticket and any stale review. Assessment and
  review remain separate, with a distinct reviewer and exact evidence shown.

Constructor, view, tab navigation and operation polling remain device-inert and
must not discover, qualify, generate evidence, revalidate large captures, or
resume work implicitly. Those operations need named, bounded explicit actions.

## Stage 7 — optics_intrinsics

**Catalog boundary:** bounded camera campaign, arm power disconnected. Owns
`preliminary_optics_screen` and `physical_capture_plan`; it produces no installed
calibration bundle component. Intake: INT-025–027.

**Reusable APIs:**

- `calibration/static_camera_intrinsics.py`:
  `load_static_camera_intrinsics_rehearsal`,
  `parse_static_camera_intrinsics_json`,
  `assess_static_camera_intrinsics_rehearsal`.
- `workcell/static_camera_support.py`: `load_static_camera_support_design` for
  controlled support/coverage design, not measured installation truth.
- `application/b0477_optical_contract.py`:
  `build_b0477_synthetic_optical_contract`, pixel-space provenance and rectification
  contract. `b0477_stack_coherence.assess_b0477_stack_coherence` cross-checks the
  selected synthetic profile/UVC/settings/intrinsics/vision relationships.
- The existing optics probe validates the sealed synthetic ChArUco fixture and
  withheld physical authority. It does not run an installed-camera numeric solver
  or measure focus merely because its stage name contains “intrinsics.”

**Missing service/UI/evidence:** an explicit preliminary optics screen tied to
the retained camera/settings/support installation; focus and coverage regions,
reviewed chart/capture plan, exact native and working pixel spaces, and numeric
observations. Distinguish a nominal lens/coverage calculation, synthetic image
check and physical focus measurement in the UI. Current upscaled board fixtures
must not be treated as 20 MP resolved optical detail. Lock a precommitted future
capture/holdout plan without claiming that its planned images were acquired.

**Hardware-free tests now:** wrong profile/mode, changed image hashes, overlapping
fit/holdout IDs, insufficient counts/coverage, altered residuals, unknown fields,
authority promotion and parser regression; synthetic coverage/rectification
calculations. Existing anchors: `test_static_camera_intrinsics.py`,
`test_b0477_optical_contract.py`, `test_static_camera_support.py` and the optics
fault in `test_first_power_on_onboarding.py`.

**Physical evidence still required:** retained camera/lens focus and aperture,
installed working distance and coverage, actual keyboard/phone/tag-plane image
quality, illumination/control stability and reviewed scale-verified capture plan.
Do not transfer the preliminary screen into stage 8 as installed intrinsics.

## Stage 8 — static_registration

**Catalog boundary:** bounded camera campaign, power disconnected. Produces
installed intrinsics, measured tag map, static camera-to-board transform,
passive visibility atlas, optical stability, and dataset partition manifests.
Intake: INT-030–043, 046–048, 050–053.

**Reusable APIs:** `run_b0477_static_vision_capture_rehearsal` and
`run_b0477_static_vision_rehearsal` in `b0477_static_vision.py`; the normal path
fits T0–T3 and checks K0/P0 independently. `B0477HeldOutStationResidual`, optical
pixel-space provenance, the intrinsics schema, and the selected static Phase-1
graph supply useful contracts. `camera_capture_dataset` and
`verify_windows_capture_ingest` supply bounded retained-byte verification and
camera/source/settings/campaign linkage, not installed calibration acceptance.

**Missing service/UI/evidence:** installed-image acquisition and numeric
intrinsics solve/assessment are not provided by the synthetic intrinsics parser.
Add measured survey intake, typed transforms and uncertainty, frame conventions,
native→working transform linkage, scale verification, varied calibration views,
partition commitments, passive visibility results, and warm-up/reseat/cable-load
stability results. Fit and validation must use the explicitly selected retained
images; no regenerated nominal substitute. Bind stage 8 to the reviewed stage-7
plan and unchanged camera/settings. Display residuals and their units/region,
excluded holdouts and missing physical evidence, not a single green image.

**Hardware-free tests now:** real synthetic pixel detection/fit and tag-loss
rejection, fit-only T0–T3, held-out K0/P0, distorted/rectified space mismatch,
camera/settings/hash drift, substituted older registration, partial capture,
overlapping splits, corrupt retained bytes and residual threshold failure.
Anchors: `test_b0477_static_vision.py`, `test_b0477_stack_coherence.py`,
`test_static_camera_intrinsics.py`, `test_camera_capture_dataset.py` and native
ingest tests. Add exact stage-8 report retention/review/reopen tests.

**Physical evidence still required:** surveyed tag corners/planes and uncertainty,
real scale-verified varied images, installed lens calibration, independent station
validation, measured static extrinsic, visibility and mechanical/optical drift.
An overhead nominal homography is not an installed camera-to-board transform.

## Stage 9 — arm_identity

**Catalog boundary:** read-only OS inventory, power disconnected. Produces exact
arm physical identity; a controller inventory candidate is not yet qualified
firmware/controller identity. Intake: INT-010.

**Next bounded implementation design (approved, not implemented):** add a
standalone `rehearsal_arm_identity_stage.py` before enabling this service stage.
The proposed immutable `RehearsalArmIdentityBinding` contains workspace source,
catalog, cell/session/operator, stage, predecessor receipt/assessment/review
hashes and the exact stage-8 static-registration evaluation hash. Proposed APIs:

- `evaluate_rehearsal_arm_identity_stage(workspace, binding=...)`: explicit
  closed synthetic fixture evaluation using the real arm-profile loader and
  injected inventory/composer functions. No host enumeration or serial open.
- `verify_rehearsal_arm_identity_evidence(payload, expected_binding=...,
  expected_evidence_sha256=..., expected_evaluator_source_sha256=...)`: bounded,
  exact-schema, pure retained verification with no evaluator replay.

Retain complete raw, normalized and composed metadata reports; separate nominal
profile/inventory readiness from expected negative-test rejection. Exercise
wrong model, missing/duplicate identity, stale COM alias, topology/interface
change and malformed output. The current model's interface field is metadata,
not verified driver identity/version. USB/COM must not be used to infer received
Pro identity, firmware or boot behavior. Those remain physically unverified.
Join this evaluator to explicit collection, review, export and original-store
reconstruction only after its strict verifier and fault tests pass. The design
does not authorize enabling the currently held stage or any physical action.

**Reusable APIs:** `load_arm_connection_profile` in `arm/connection.py`;
`RawSerialPortObservation`, `NormalizedDeviceCandidate`,
`inventory_serial_ports_from_provider`, and
`compose_physical_device_inventory_report` in `physical_device_inventory.py`.
The existing arm-identity probe checks Pro versus wrong model and inactive
115200/RTS/DTR/auto-initialization policy without inventory or opening a port.
`ReviewedControllerBinding` in `providers/windows/arm_feedback_worker.py` is a
future exact identity/firmware/boot-policy binding, not something stage 9 can
complete from a COM string alone.

**Missing service/UI/evidence:** separate operator-observed unpowered Pro
arm/controller identity receipt and explicit metadata inventory/selection;
correlate chassis/controller/unit/driver/persistent path to an ephemeral COM
endpoint. Show mismatches and unknown fields. Firmware evidence remains pending
for the later qualified-controller stage. No serial open during this stage.

**Hardware-free tests now:** injected metadata for missing/duplicate IDs, wrong
Pro/S model, moved COM alias, changed USB topology/driver, stale selection and
unexpected inventory output. Tests must inject the enumerator, not enumerate
the developer host. Anchors: `test_arm_connection.py`,
`test_physical_device_inventory.py`, `test_arm_feedback_worker.py`.

**Physical evidence still required:** received unpowered arm/controller identity,
photos/labels and observed persistent OS association. Catalog/model strings and
a matching USB bridge alone do not establish installed firmware or robot identity.

## Stage 10 — power_safety

**Catalog boundary:** manual energy change; disconnected except the separately
bounded inert-load test. Produces power-safety review and owns startup swept-volume
screen. Intake: INT-012–016, 044–045.

**Reusable APIs:** `PowerSafetyReview`, `ReceiptBinding`, `BoundEvidence`,
`assess_power_safety` and `ControlledOperatorDecision` in
`physical_onboarding_receipts.py`; `assess_hardware_intake` for assigned intake
evidence; `assess_current_collision_readiness` for honest incomplete-geometry
reporting. `physical_shaped_onboarding.py` has procedure-shaped fake evidence.

**Missing service/UI/evidence:** a v2/source-domain bridge for the typed receipt
and bound inspection media, numeric supply/polarity observations, distinct review,
startup swept-volume/containment evidence, and separate inert-load versus
energized-arm procedures. Existing receipt binding is not automatically the new
M1 evidence-admission contract. No UI power switch or “all safe” default.

**Hardware-free tests now:** exercise the real assessor with absent E-stop evidence,
wrong supply data, unsecured components, unclear power, unplanned motion/contact,
missing hashes and uncertainty; test one-effect ordering and durable cancellation.
Anchors: `test_physical_onboarding_receipts.py`,
`test_physical_shaped_onboarding.py`, `test_commissioning_coordinator.py`.
The legacy power probe checks checklist ordering only; it does not simulate E-stop,
gravity or clearance and must not be reused as physical safety success.

**Physical evidence still required:** secured structures, measured supply/polarity,
independent disconnect/E-stop validation, startup clearance, gravity containment,
anti-shift and cable restraint. A complete fake checklist supplies none of these.

## Stage 11 — power_on_observation

**Catalog boundary:** ordered manual energy change and possible motion, one fresh
manual permit ending disconnected. Produces first-power observation and startup
sweep evidence; there is no standing power authorization.

**Reusable APIs:** `FirstPowerObservation`, `assess_first_power_observation`,
`EffectCertainty`, `StartupMotionClassification`; `EnergizationEnvelope` and
coordinator attempt lifecycle. The assessor already distinguishes unknown final
power/observation from known completion and rejects retries/abnormal events.

**Missing service/UI/evidence:** explicit stage-specific manual ceremony with
operator/observer, reviewed prerequisites and envelope, start/end observation,
bounded media intake and independent final disconnected confirmation. Record
unexpected startup movement or loss of observation as incident/uncertainty, not
a dismissible generic error. A UI cancel/worker close is not a physical E-stop.

**Hardware-free tests now:** derive results by running the actual receipt assessor
against typed synthetic events: missing sightline, unknown final power, multiple
attempts, unbounded motion, collision and E-stop use. Persist and reopen uncertain
attempts; assert no later stage/duplicate dispatch. Existing legacy startup probe
represents required fields but does not predict a startup trajectory.

**Physical evidence still required:** one independently controlled and observed
received-arm startup event, actual movement/clearance/settling and final
de-energization. Software cannot infer “home,” stationary pose, or safe power-off.

## Stage 12 — feedback_only_connection

**Catalog boundary:** ordered manual energy change and serial open/write, fresh
manual permit ending disconnected. Produces feedback exchange and qualified
controller identity. Intake: INT-011.

**Reusable APIs:** `ArmFeedbackWorker`, `ArmFeedbackCampaignRequest`,
`parse_arm_feedback_request`, `ReviewedControllerBinding`, and
`rehearse_arm_feedback_campaign` in `providers/windows/arm_feedback_worker.py`;
existing `SingleT105FeedbackRequest/Receipt`, `T105TransactionTiming`,
`feedback_wire` validation and typed feedback decoder. The new
`arm_feedback_contract` diagnostic action already exercises incapable scenarios;
it is not a stage-12 durable evidence integration. See
[the worker's detailed contract and native blockers](ARM_FEEDBACK_WORKER.md).

**Missing service/UI/evidence:** coordinator-backed exact one-use child
authorization, qualified process containment/identity resolution, raw plus safe
parsed evidence retention, and independently recorded final power-off. Preserve
the worker's open/configure/quiet-buffer/one-write/close accounting and native
holds. The default physical backend is held; the documented pySerial opening
purge problem requires a reviewed non-purging backend. Native work in progress
must be independently verified before this status changes.

**Hardware-free tests now:** wire and process fixtures for boot/stale bytes
(zero writes), partial write (one attempt, no remainder), timeout, bad JSON,
wrong response, extra bytes, changed identity, close failure, worker disappearance,
stale/duplicate redemption, retention failure and unknown final power. Retain
full reports through a real M1 temporary store. Anchors: `test_arm_feedback_worker.py`,
`test_physical_connection_rehearsal.py`, `test_physical_shaped_onboarding.py`,
coordinator/adapter tests. A matched negative scenario passes a *fault test*,
not the feedback stage.

**Physical evidence still required:** reviewed received controller/firmware/boot
policy, actual driver/bridge identity and open-time RTS/DTR/reset behavior,
preserved unexpected bytes, authorized single exchange and observed final power
off. A valid `T=1051` proves neither firmware revision, calibrated reference nor
stationarity. Do not mint a legacy `FeedbackPermit` to bypass v2 admission.

## Stage 13 — reference_frame_calibration

**Catalog boundary:** separately released external noncontact motion with manual
energy change and final disconnection. Imports bootstrap and reference-phase
receipts, arm-to-board/controller correlation/free-state TCP, target maps and
outcome-observer candidates. Intake: INT-049. No wizard “move to calibrate” action.

**Reusable APIs:** `run_static_phase1_calibration_rehearsal`,
`static_phase1_context_hashes`, `STATIC_OVERHEAD_PHASE1_GRAPH`,
`CalibrationRegistry.resolve`, `CalibrationArtifact` and parent-hash assessment.
The existing rehearsal exercises 15 shared graph entries, two 12-entry device
closures and every declared dependency-staleness edge. It preserves an empty or
invalid physical registry as blocked. `run_target_sweep` and
`run_placemat_uncertainty_simulation` provide additional nominal targeting checks.

**Missing service/UI/evidence:** strict assigned-source import/verification of
separately released reports; frame/unit/axis conventions, measured transforms and
uncertainty, source/epoch/phase predecessor chains and reviewer decisions. Bootstrap
must precede reference characterization. Show source-to-target transform chains,
coverage and blockers for keyboard and phone independently.

**Important mismatch to handle:** the static Phase-1 graph also describes
contact-dependent keyboard/phone TCP and activation/outcome qualification. It is
excellent for dependency rehearsal, but its entire physical closure is **not** a
stage-13 noncontact pass predicate. Stage 13 owns free-state TCP, target maps and
observer *candidates*. Keep future contact calibration/release explicitly deferred;
do not perform contact work to satisfy the broader graph or call candidates final.

**Hardware-free tests now:** real graph/registry resolution and exact independent
edge invalidations; mixed-source reports, stale support/settings/controller/TCP,
wrong units/frames, missing predecessor, synthetic-as-physical imports and
out-of-order phase receipts. Anchors: `test_static_phase1_calibration.py`,
`test_placemat_uncertainty.py`, target-sweep tests and first-power calibration tests.

**Physical evidence still required:** externally observed robot reference,
controller-model correlation, diverse reference correspondences and heldouts,
measured arm-to-board/free-state TCP/device surfaces/maps under separately released
noncontact procedures. Startup middle, URDF world, controller frame and safe park
are not interchangeable reference frames.

## Stage 14 — noncontact_acceptance

**Catalog boundary:** separately released external noncontact motion, manual
energy change, final disconnection. Produces noncontact qualification and untouched
final-acceptance phase receipts, acceptance report, arm-induced visibility atlas,
collision configuration and accuracy-budget assessment. Intake: INT-054; deferred
INT-005 closes here only after `TARGET_ACCURACY_BUDGET_CLOSED`.

**Reusable APIs:** `run_b0477_bound_virtual_acceptance` and
`run_default_virtual_session` exercise actual virtual routes, independently
observed keyboard/phone outcomes, park and cleanup; `run_trajectory_simulation`
and `revalidate_trajectory_simulation_report` bind kinematic results;
`assess_current_collision_readiness` preserves missing installed geometry;
`assess_target_accuracy_budget` applies typed, source/epoch/time-bound term
evidence with a conservative sum and eroded target margin.

**Missing service/UI/evidence:** independently measured installed collision
bodies/cables/tool geometry, arm-induced visibility, untouched final test
partition and separately released noncontact report intake. Bind to the exact
current stage-8 registration rather than rerendering a sequence-101 nominal report
and calling it the session's accepted camera evidence. Display missing geometry,
unbounded error terms, margins/units, coverage and final power observation.

**Hardware-free tests now:** run real virtual keyboard and phone pipelines,
first-waypoint stall, no work after fault, cleanup/park accounting and changed
registration bindings. Test accuracy missing/stale/future/wrong-domain terms,
oversized tool/negative margin and incorrect dependency hashes. Anchors:
`test_b0477_virtual_acceptance.py`, `test_first_power_on_onboarding.py`,
`test_accuracy_budget.py`, `test_collision_foundation.py`, trajectory tests.

**Physical evidence still required:** complete measured installed geometry,
approved noncontact routes and independently observed residual/visibility/drift
evidence spanning the operating domain and untouched final partition. Missing
accuracy terms are unbounded, not zero. The existing virtual acceptance includes
virtual contacts and shared B0477 preflight imagery; report those facts and never
label it a physical noncontact qualification or a fresh B0477 image per action.

## Stage 15 — physical_handoff

**Catalog boundary:** no device I/O or power change. Produces epoch vector,
global attempt/quarantine heads, reviewer decisions and open blockers as part of
the commissioning-bundle candidate. Ends `COMPLETE_DIAGNOSTIC`, **not `PASS`**.
INT-055 is post-diagnostic intake, not a stage-15 unlock.

**Reusable APIs:** `load_physical_onboarding_stage_catalog` exposes unique
`produced_bundle_components` and `bundle_component_producers` (39 components at
this audit); M1/session verification and `export_document/export_bytes` expose
retained heads/evidence; diagnostic export has assigned-root publication;
`load_configuration_epoch_policy` defines the eight epoch classes and their
earliest invalidation stages. The existing handoff probe validates the component
contract only and explicitly withholds the actual bundle/disposition.

**Missing service/UI/evidence:** typed complete bundle assembly/verification with
exact component producer, source/epoch, phase predecessor, reviewer and current
ledger-head closure. The epoch policy loader alone does not implement observed
change detection or returning-startup invalidation. Add a reviewed change diff
and durable invalidation through the existing guarded session boundary. Keep
older/synthetic evidence readable without promoting it to a physical component.
Export both machine-readable manifests and a human-readable checklist of open
blockers and next separately authorized actions.

**Hardware-free tests now:** exact component coverage, duplicate/missing/wrong
producer, stale dependency/head/reviewer, source drift, quarantine, export race,
corrupt files, complete-graph fixtures and stage-15 rejection of `PASS`. A
REHEARSAL-domain complete diagnostic traversal may demonstrate the workflow once
implemented, but must visibly remain rehearsal with zero physical components
accepted; it must not masquerade as physical commissioning completion.

**Physical evidence still required:** verified physical predecessor components and
reviewed current epoch/attempt/quarantine closure for a physical handoff. Export
success never grants motion/contact authority. Typing and phone tapping remain
a later separately implemented, qualified and released contact workflow.

## Implementation order after the stage-7/8 slice

1. **Stage 9 + shared receipt bridge:** explicit synthetic/unpowered identity
   intake and injected inventory; stage-specific typed evidence, operator and
   distinct review. Also generalize original-store verification by supported
   receipt version, not by accepting arbitrary JSON schemas.
2. **Stages 10–11 ceremony rehearsal:** drive the actual safety/startup assessors
   with bounded typed observations and failure cases. Implement every required
   power-envelope/attempt transition with incapable workers. Physical controls
   remain unavailable; uncertainty prevents later progress.
3. **Stage 12 durable worker integration:** join the existing one-shot incapable
   feedback worker to coordinator/process/evidence/UI boundaries. Native facade,
   containment and identity work can develop in parallel, but do not lift its
   physical holds as a consequence of this rehearsal integration.
4. **Stage 13 report intake + dependency views:** run substantive static graph
   checks now; implement strict external report contracts and stage-owned
   noncontact predicates without demanding contact-dependent graph leaves.
5. **Stage 14 virtual acceptance + budget intake:** reuse current-session static
   evidence explicitly; run real virtual routes/faults and accuracy assessment.
   Preserve physical collision and measurement blockers in both UI and exports.
6. **Stage 15 bundle + returning-startup invalidation:** verify the exact catalog
   producer closure, original-store reopen, current epochs and ledger heads;
   generate a complete diagnostic report with no release side effect.
7. **End-to-end qualification:** browser and terminal traverse all fifteen
   substantive REHEARSAL stages with real temporary durable stores, logs and
   reopen at each supported boundary. Then independently qualify physical
   provider composition and received-unit evidence under the original plan.

For each slice, completion means the evaluator, strict evidence verifier,
registered action, prepare/execute boundary, readable results, exact review,
export, reopen and negative tests all work together. Standalone code plus a
button, or an enabled next-stage guard, is not that integration.

## Cross-stage acceptance checks to add

- A failing child check, valid-but-blocked report or expected negative scenario
  cannot produce nominal stage acceptance. Mutate the actual evaluator outcome
  in a test; stage outcome must change even with an exit code of zero.
- No hidden work on constructor/view/navigation/poll/refresh; explicit
  verification actions are bounded. No browser or terminal raw device/path
  selector, blanket authority flag or default-yes effect confirmation.
- Changed source, catalog, current evidence, selected unit, settings or relevant
  epoch blocks stale prepared execution/review and invalidates the right stages.
- Original-store reopening verifies retained evidence without rerunning camera,
  serial, virtual mission or prior operator approval. Corrupt/unsupported/orphan
  evidence holds; no automatic copy, reset, repair or replay.
- Partial publication, cancellation, worker death, ambiguous cleanup and unknown
  final power cannot become `SEALED_KNOWN` or advance the sequence. Cross-session
  quarantine is not cleared by creating another session.
- Reports retain full technical provenance through assigned bounded exports;
  user-facing summaries avoid credential-bearing raw boot text. Native datasets
  keep their actual qualification status; immutable hashes alone are not trust.
- Stage 15 cannot be `PASS`; diagnostic completion cannot enable typing, tapping,
  motion, torque, homing, firmware changes, automatic startup or a physical power
  switch. Every hardware-free test reports actual device effects as zero.

## Audit limits

This document was produced by read-only source/catalog/test inspection. No test
results are claimed from this audit, and no camera, port, provider, controller,
physical campaign or hardware inventory was run. Native camera/arm work was
being developed independently; its source-controlled holds and dedicated
qualification documents must be checked again before an integration decision.
No existing plan, catalog, configuration or implementation file was changed.

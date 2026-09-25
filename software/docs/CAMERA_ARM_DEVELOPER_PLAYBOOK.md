# Developer playbook: camera, arm connection and onboarding

Read the [application completion matrix](ONBOARDING_APPLICATION_COMPLETION_MATRIX.md)
alongside this playbook. Hard-coded camera/arm holds still require production
integration; they must not be described as merely waiting for hardware testing.

Continue with the [full-history integration work order](CAMERA_FULL_HISTORY_INTEGRATION_WORKORDER.md).
The [settings-capture wizard handoff](CAMERA_CONFIGURATION_WIZARD_HANDOFF.md)
documents the now-integrated public action, original admission, still-image
publication and per-attempt export. Its tests still model predecessor semantics;
the new work verifies the complete retained-history path without that seam.
Stage-5 policy assessment and stage-6 freshness remain separate unfinished work.
Neither a captured image nor a passing software test qualifies the physical cell.

The [camera wizard usability handoff](CAMERA_WIZARD_USABILITY_HANDOFF.md) describes
the current available-action grouping, expandable original/blocked records,
shared early portable-ID validation and selected regression/browser evidence.
The assigned export parent remains `software/runs/wizard-exports`.

The actual browser task walkthrough also exposed the older task simulator's
legacy camera graph and sampled IK gaps. The
[static-task migration work order](STATIC_TASK_SIMULATION_MIGRATION_WORKORDER.md)
defines the versioned graph/bundle migration, visible outcome interpretation
and bounded IK diagnosis. These are software integration tasks; do not rename
legacy artifacts or count worker completion as path qualification.

The [task-feedback and full-resolution checkpoint](TASK_FEEDBACK_AND_FULLSIZE_CHECKPOINT.md)
records the now-visible outcome warnings, settings operator-ID validation,
full-sized synthetic frame tests, and independently verified browser export.
The [full-history work order](CAMERA_FULL_HISTORY_INTEGRATION_WORKORDER.md#run-02-terminal-admission-deadline-failure)
records the separate probe deadline failure and narrowly tested audit reuse.
Neither checkpoint establishes full-history timing or physical readiness.

The preceding [public original-bound camera probe](CAMERA_PROBE_PUBLIC_WIZARD_CHECKPOINT.md).
The wizard now joins current logged identity, complete original authentication,
substantive scoped facts/capacity, existing v2 dispatch, completion publication
and a separate complete attempt export. Tests use incapable producers, not real
hardware. Capture/stage acceptance/calibration and RoArm connection remain work.
The shared Session default deny is unchanged; only the gated probe supplies facts.

The preceding [probe preparation wizard handoff](CAMERA_PROBE_SETUP_WIZARD_CHECKPOINT.md).
File-only Prepare/Review actions now join the original Setup owner, current
logged metadata and a separate complete diagnostic export. The handoff documents
the narrow blocked-stage storage correction, test boundaries and next work:
full public original-store composition and substantive camera admission, followed
by probe/capture and the RoArm connection path. Saved records cannot open a camera.

The preceding [v2 original-result and application handoff](CAMERA_ACTIVATION_HANDOFF_WORKORDER.md).
The shared dispatch/service/data workflow now supports the explicit two-part
evidence contract, with tested settings/image ingestion and staged publication.
That workorder gives the exact next original-admission, public UI and export
tasks. It does not describe the current wizard as hardware-ready.

The preceding [installed v2 runtime and software-policy handoff](CAMERA_ACTIVATION_RUNTIME_WORKORDER.md#installed-runtime-checkpoint).
Both purpose-specific workers compile, and the real scoped campaign now enforces
the reviewed installed-file policy. Original acquisition/service/UI integration
remains next; matching software is not connected or qualified hardware.

The preceding [v2 scoped-campaign checkpoint](CAMERA_ACTIVATION_CAMPAIGN_CHECKPOINT.md)
documents the real internal adapter, fresh output-directory ownership and
evidence-preserving interruption path, plus the exact remaining runtime/original/
UI handoff. Initial runtime approval must not require prior hardware qualification.

The preceding [v2 original-retention checkpoint](CAMERA_ACTIVATION_STORAGE_CHECKPOINT.md)
documents how the core and original M1 store accept bounded camera-specific
evidence, preserve unknown native counts and audit partial publication/reopening.
The scoped campaign and installed software policy now join them; the original
runtime-review/acquisition/UI connection remains unfinished.

The preceding [v2 supervisor checkpoint](CAMERA_ACTIVATION_SUPERVISOR_CHECKPOINT.md)
documents the implemented lifecycle, Stop/cleanup behavior and 502 selected checks.
Its storage gaps are addressed by the camera-specific successor, without changing
historical v1/USB limits or granting physical access.

The preceding [v2 evidence/accounting checkpoint](CAMERA_ACTIVATION_EVIDENCE_CHECKPOINT.md)
for the newest installed run-record contract, missing-observation handling and
effect accounting. It states the exact remaining supervisor/campaign/storage join.

The preceding [v2 parent/process checkpoint](CAMERA_ACTIVATION_PARENT_CHECKPOINT.md)
for the newest installed preparation, shared handshake and contained-process
tests. It lists the exact remaining production retention/original-facts join.

Latest component: [installed camera v2 request/result validation](CAMERA_ACTIVATION_RESULT_CHECKPOINT.md).
It documents the new source boundary, native/Python round trips, preserved failed
installation check and exact next dispatch/original-storage work. These pure
codecs do not enable physical access.

For the current changes and reproducible evidence, read the
[camera-entry/cleanup checkpoint](CAMERA_ENTRY_CLEANUP_CHECKPOINT.md): label
validation, permit first issuance, native cleanup tests, historical runtime
preservation and the second NTFS entry failure. The follow-up
[entry storage checkpoint](CAMERA_ENTRY_STORAGE_CHECKPOINT.md) explains the
dedicated retention contract, fault tests and passing full run-03 acceptance.
The [native integration draft](../../.codex-preserved/camera-activation-identity-draft-20260910-01/INTEGRATION.md)
is the next component: compiled pre-open identity checking and tested codecs,
with the full wire-result codec subsequently installed; the physical
runtime/original-store/service/UI connection remains unfinished.

## Quick developer entry point

From `C:\Users\Jack\Desktop\robot-arm-build`:

```powershell
.\start-rocell-wizard.ps1 -Check
.\start-rocell-wizard.ps1
```

The second command opens the hardware-free rehearsal interface. For the
original-record workflow use `-Mode physical`; this is not a command to connect,
energize or move the arm. If browser access is unavailable, the supported
alternative is `-Ui terminal`. See the [operator instructions](WIZARD_WORKBENCH.md#launch)
for the guided actions and their prerequisites.

Exports default to `software\runs\wizard-exports`, as confirmed by the operator.
Keep ordinary diagnostic bundles separate from explicitly approved private
intake exports. A valid exported report means its contents verified, not that
hardware qualification passed. Retained timing holds and failed originals are
useful test evidence and must not be reused as retryable setup stores.

For a development change, pick one row in the completion matrix, read its
linked work order, run the corresponding [test lane](#9-test-lanes-and-commands),
and record actual results plus modeled boundaries. Full USB acceptance rebuilds
its predecessor chain and takes multiple minutes; use a fresh preserved pytest
directory and keep the application source fixed for the entire run. The detailed
history below is not an operator checklist for every startup.

For storage/admission changes, first run the bounded fresh and retained-history
worker checks documented in the [performance checkpoint](STORAGE_ADMISSION_PERFORMANCE.md).
They use a fixed hardware-incapable child and real storage/leases, and are much
smaller than the full public reconnect/reboot sequence. Their passing results
do not replace public acceptance or received-hardware qualification.

The [full-history timing triage instructions](CAMERA_FULL_HISTORY_INTEGRATION_WORKORDER.md#read-only-timing-triage)
describe `software/scripts/summarize_camera_admission_trace.py`. It provides
bounded, read-only per-action/function timing summaries from a retained test
checkpoint without reopening setup or replaying an attempt. This diagnostic
aggregation is separate from authenticating the original store or export.

### Verify a saved USB diagnostic bundle without reopening setup

The standalone developer utility uses the existing manifest verifier and
complete USB export codecs. Give it one exact absolute export directory:

```powershell
.\.venv\Scripts\python.exe software/scripts/verify_usb_identity_export.py `
  'C:\Users\Jack\Desktop\robot-arm-build\software\runs\wizard-exports\wizard-20260909T213704700602Z-e7bd0f4b550b4655b6098d0a6a724bf9' `
  --expected-original-sha256 0fa53bba1c4b54c44e67e0fda0b39cafa9fd0c1ce905b02a7980d20369085734
```

That concrete example is the retained, hardware-free run-04 failure, **not a
passing qualification**. For another bundle, supply its own path and omit the
optional hash unless independently recorded. Do not substitute the manifest,
report-file or individual-subject hash for the original-diagnostics hash.

Exit code 0 means the copied export verified and reconstructed. The JSON result
separately reports whether credential redaction prevents reconstruction of the
original bytes. Exit code 1 means verification failed; it neither repairs files
nor prints private device/operator subjects. The utility loads no commissioning
session, starts no child process and grants no camera/arm authority. It checks
copied payload hashes and rechecks the manifest after reconstruction. A
self-consistent manifest is not an external cryptographic trust anchor.

The utility's 12 focused cases pass as part of the 31-test inventory/collector
selection; the real preserved v5 and v6 bundles were also verified directly.
Use its separate unit file `test_usb_export_verifier_script.py` for changes to
this developer tool. It does not replace the ordinary wizard Export action.

Earlier completed slice: [AFTER_RECONNECT original workflow](USB_AFTER_RECONNECT_IMPLEMENTATION.md).
Fresh public run 06 passed in 1,062.33s: actual storage and supervisor/timing
gates, all actions, eleven roles/seven events, full v5 export/restore and fresh
original reopening without replay. Hardware/process observations are modeled;
physical qualification and capture/arm authority remain absent. Earlier failed
originals and exact diagnostics stay preserved.

Latest successor result: [AFTER_REBOOT](USB_AFTER_REBOOT_IMPLEMENTATION.md)
full public run 07 passed in 1,735.50 s, including the new-launch flow, all five
actions, eleven roles/seven events, full v6 export/restore and fresh original
reopen/no replay. Hardware/process facts were modeled. The accepted store and
verified ordinary export are preserved in the confirmed folder. The 0.782-s
post-pin timing margin is narrow; this is not a general performance guarantee.

Active build slice: [complete-series assessment/review](USB_COMPLETE_SERIES_IMPLEMENTATION.md).
Its original v14 Session reader, file-only assessment/review service actions,
browser/terminal controls and versioned v7 export/restore are installed. Actual
Setup/USB operations over modeled storage pass assess → review → export,
including both interfaces and inert navigation (206.40 s). The selected public
contract/export/display regressions also pass (286 tests). Both validators reject
inconsistent phase summaries and do not promote partial review files to PASS.
Full fresh public workflow/reopen/export acceptance now passes: **1 test in
2,090.53 s**, with actual storage/logs and explicitly modeled hardware/process
observations. The complete original copy, source snapshot and independently
verified v7 export are in the confirmed folder; no consumed operation is replayed.
The next
[camera identity-to-acquisition work order](CAMERA_IDENTITY_TO_ACQUISITION_WORKORDER.md)
specifies separate stage-5 entry, runtime/admission, supported settings and
bounded still-image publication using the existing owners. Its original v15
entry reader passes 254 fast checks and 10 composed modeled-history checks.
The one-shot Setup action, both interfaces and complete entry export are now
installed and pass the modeled public composition (168.93 s), plus 670 selected
fast/regression checks. The new action records `WAITING_OPERATOR` only; no
camera or arm is connected. Fresh public NTFS entry/export/reopen acceptance
has now passed in run 03 (2,230.09 s). Read the work order's exact test scope,
including the expanded type-check findings; do not infer a clean full suite.
The preceding selected public-contract regressions passed 286 tests.
Camera and arm activation
are still unfinished; do not turn a passed observation series into a hardware
permission flag.

### Use the camera-entry increment

1. Launch the original-record workflow explicitly with `-Mode physical`. Do not
   import a diagnostic bundle as an original session or relabel old source IDs.
2. Use the existing discovery/reopen and identity-review workflow. Once the
   exact current original review is accepted, the Camera page offers
   **Continue to camera setup**. Its navigation button only opens the form.
3. Review the file-only preview, enter the operator label, explicitly confirm
   no device access, then execute once. Inspect the entry status and hashes.
   `ENTERED` means stage 5 is waiting for commissioning, not connected or PASS.
4. Export general diagnostics to the assigned workspace folder. The entry's
   full original and attempted record are in `attachment-camera-mode-entry.json`.
   Also use the existing separate USB evidence export when investigating its
   predecessor; the general report only points to that larger evidence family.
5. On failure, inspect/export retained state. Do not replay a consumed ticket,
   edit evidence, bypass a hold or treat Stop as physical de-energization.

Relevant implementation owners: `PhysicalCameraSetupService` owns the queued
attempt and operation lock; `physical_camera_mode_entry_service.py` performs
the file-only transition through Session; Arrival owns logs/publication/export;
`physical_camera_mode_entry_projection.py` plus the browser/terminal validators
display cached state without device effects. No second connection manager or
logger was introduced. The
[checkpoint](../runs/wizard-exports/developer-checkpoint-camera-mode-service-20260910-01/CHECKPOINT.md)
contains selected source, tests and actual reports, not a complete runtime image.

Predecessor implementation history: [explicit USB reconnect trials](USB_RECONNECT_WIZARD_IMPLEMENTATION.md).
It adds original trial declaration, complete versioned exports, stricter boot
process accounting and a separately built physical-node presence producer.
The active successor adds exact original phase binding, runtime/policy review
and separate M1 presence admission; owned dispatch and original collection are
not inferred from those component contracts. Its work order identifies the new
trial BASELINE as the required application-facing acceptance. That
implementation now joins explicit phase start, fresh metadata timing, a
phase-bound descriptor command and separately admitted owned boot observation
to versioned original storage and full exports. The public BOOT_HELD path now
passes real NTFS Begin/Prepare/Review/Collect/export/reopen acceptance with
modeled hardware facts, no processes and no USB queries. The nominal boot-to-USB
public software path also passes real original M1 admission, full nine-role
export/restore and fresh reopening/no replay (two tests, 397.09s). Its boot, USB
and process observations are explicitly modeled; no device/process ran and no
stage PASS follows. Follow the work order's verified results, not API presence.
The [five-step absence contract](USB_ABSENCE_PHASE_IMPLEMENTATION.md) now records
the implemented original-journal/service/UI/export integration and its scoped
tests. Its first public NTFS acceptance failed; preserve that original and do
not retry its consumed permit. The corrected failure readback, faithful timing
model and duplicate-read optimization now pass fresh run 02 (700.42s), including
all actions, full export/restore and original reopen/no replay. This is modeled
hardware behavior over genuine storage, not physical qualification. Follow the
reconnect work order's bounded successor checklist. At that earlier checkpoint,
reconnect/reboot were open; use the current slice links above for their updated
status. Physical camera capture and arm commissioning remain open. The browser's general diagnostic export was
also verified in the operator-confirmed workspace folder.

Previous work order: [controlled USB identity integration](USB_IDENTITY_WIZARD_DISPATCH_WORKORDER.md).
It maps the implemented policy/owned-process/M1/campaign/dispatch components,
original-stage service, four visible USB actions and complete diagnostic export.
Read its active verification section for full-history results and remaining
acceptance work; do not infer hardware readiness from component test passes.
The preceding [metadata onboarding](CAMERA_IDENTITY_ONBOARDING_IMPLEMENTATION.md)
remains the five-role prerequisite workflow, BLOCKED review and export.
The full physical camera/arm connection and startup goal remains open.

**Playbook ID:** `ROCELL-CONNECTION-DEV-001`  
**Date:** 2026-09-07  
**Companion plan:** [`ROCELL-CONNECTION-INTEGRATION-001`](CAMERA_ARM_CONNECTION_INTEGRATION_PLAN.md)  
**Purpose:** an implementation and handoff guide for developers joining this work  
**Status:** implementation in progress; diagnostic workbench, thirteen-stage M1-backed camera/optics/arm/retained-feedback/nominal-reference rehearsal plus stage-14 NC-01 gap diagnostics with original-store reopening, native identity/ingestion clients and separate incapable Windows process/non-purging serial precursors implemented; see the implementation record for executed verification. Full ticket acceptance, NC-02/03, handoff, installed calibration and physical activation remain pending.

## 1. Start here

Previous implementation: [static-camera design onboarding](STATIC_CAMERA_ONBOARDING_IMPLEMENTATION.md).
Actual controlled design collection, exact review and explicit camera-receipt
entry now join the original stage-2 records and shared UI. Read the guide for
the source/transaction/publication contracts and stage-owned budgets. The pure
received-unit assessment was later joined by the
[stage-3 original submission/review UI](RECEIVED_CAMERA_ONBOARDING_IMPLEMENTATION.md).
No design or receipt PASS is physical qualification.

Previous implementation: [original source-stage reassessment](SOURCE_STAGE_ADMISSION_IMPLEMENTATION.md).
The stage-only collection/review service joins fresh source checks, actual
hardware-free ownership experiments, guarded isolation originals and original
M1 restart. Four explicit UI actions separate UNKNOWN, assessed eligibility,
reviewed source-stage acceptance and stage-2 entry. The guide includes the
operator sequence, component map, exported metadata and remaining connection
work. Source-stage PASS is not camera runtime release or physical approval.

Previous implementation: [camera acquisition dispatch transaction](CAMERA_ACQUISITION_DISPATCH_IMPLEMENTATION.md).
The service now has an original-store coordinator-to-data handoff, bounded-effect
accounting, preflight/consumed-scope context checks and historical failure
diagnostics. Model tests exercise probe/settings/real-file PNG ingestion; actual
NTFS tests exercise the public owner and original M1 readback. Original-stage
admission, qualified native release/output ownership and the public physical
action dispatcher remain unfinished. Do not treat test fixtures as approval.

Previous checkpoint: [durable passive intake and original-byte review](PHYSICAL_INTAKE_SUBMISSION_WORKFLOW.md).
The wizard now joins guarded inbox choices, complete immutable submissions,
procedural review, original M1 restart and separate private-byte exports. The
guide records shared APIs, exact resource limits, failure retention, the verified
public lifecycle and the still-missing physical admission/dispatch boundary.
All sixteen observations stayed UNKNOWN in the hardware-free walkthrough;
submitting or acknowledging evidence does not release a camera or arm.

Previous checkpoint: [progressive original configuration records](PHYSICAL_CONFIGURATION_EPOCH_WORKFLOW.md).
The real prerequisite action now retains one initial eight-domain dependency
vector in its original store, with exact restart readback, cached display and
reserved full diagnostic export. Four current-stage outputs and 28 later
outputs remain pending; no hardware binding is inferred from requirements.
The guide maps the actual producer boundaries and distinguishes this missing
input foundation from the still-unfinished admission/physical dispatch path.

Previous checkpoint: [two-boundary arm connection resolution](ARM_CONNECTION_RESOLUTION_WORKFLOW.md).
The contained incapable child now drives the actual Windows metadata acquisition
and resolution code before open and before its single feedback write. Full
bounded traces join versioned process evidence, explicit generic/native fixture
lineage, original-store verification and dedicated chosen-folder diagnostics.
The guide records actual verification, the preserved first public-publication
failure and its repair, and remaining physical admission/dispatch work.

Companion checkpoint: [retained camera data pipeline and reported-settings interface](PHYSICAL_CAMERA_CAPTURE_WORKFLOW.md).
Existing probe/configuration/native-capture/file-ingestion contracts now compose
into one testable application lifecycle and logged last-frame publication. The
public settings action stages only native-reported choices. Physical dispatch,
M1 prerequisite admission and release/ownership qualification remain separate
unfinished work; do not treat the modeled-native real-file tests as those joins.

Previous checkpoint: [canonical saved workspace-source workflow](PHYSICAL_SOURCE_REVIEW_WORKFLOW.md).
The original camera-only M1 store now retains a source receipt, deterministic
BLOCKED assessment and exact-subject review. Closed-role readback preserves
original context across restarts; a reserved complete export survives result
rotation. Extend later qualification contracts separately: do not turn file
checks, consent or reviewer labels into physical PASS evidence.

Previous checkpoint: [native arm identity metadata onboarding](WIZARD_ARM_METADATA_IMPLEMENTATION.md).
The fixed diagnostic child now collects native Windows controller metadata only
after explicit generic SERIAL review and confirmation. Strict source/review joins,
incapable fixtures, cached UI and a reserved latest-attempt export are integrated.
No `ReviewedControllerBinding`, port opening, firmware identity or physical stage
acceptance is manufactured from this metadata correlation.

Previous checkpoint: [installed runtime inspection/review and verified export](PHYSICAL_CAMERA_RUNTIME_REVIEW_IMPLEMENTATION.md).
The two purpose-specific Camera file actions join bounded actual observations,
exact staged publication, compact UI and reserved full-report export. Read the
[pure inspector API](PHYSICAL_CAMERA_RUNTIME_INSPECTION_API.md) before extending
the later runtime-registration/physical-acquisition boundary. File agreement or a
distinct reviewer label never qualifies a native runtime, camera, arm or motion.

Previous checkpoint: [feedback-window repair and verified NC-01 public lifecycle](FEEDBACK_SINGLE_WINDOW_IMPLEMENTATION.md).
The normal memory-first path completes thirteen reviewed rehearsal stages and
retains stage fourteen BLOCKED across collection, assessment, review, restart and
five verified exports. Physical stages and handoff remain pending. The checkpoint
records exact source, original-store and receipt hashes, scoped regressions and
the preserved preceding failed run; do not conflate their verification results.

Previous slice: [retained noncontact readiness diagnostic](WIZARD_NONCONTACT_IMPLEMENTATION.md).
NC-01 joins actual historical collision/accuracy calculations and original
stage-13 lineage. Its nominal readiness remains BLOCKED; synthetic controls are
separate. Read the API, reopen and presentation contracts linked there before
extending to NC-02/03, handoff or physical acceptance.

Previous slice: [passive intake draft notebook](PHYSICAL_INTAKE_NOTEBOOK_IMPLEMENTATION.md).
The wizard now stages source-bound operator observations independently of
canonical stage acceptance, with explicit revisions and a dedicated full-notebook
diagnostic attachment. Evidence-note text is not verified attachment ingestion.
Read the boundary and remaining acceptance requirements before extending this
into received-unit evidence review or physical connection authority.

Previous slice: [camera setup restart continuity](PHYSICAL_CAMERA_RESTART_IMPLEMENTATION.md).
This connects explicit metadata discovery, selected original-store opening,
verified requirement restoration, same-original fault recovery and planning
identity across two app launches. Live acquisition/arm commissioning remains
unfinished and separately gated.

Previous slice: [camera setup session and prerequisite workflow](PHYSICAL_CAMERA_SESSION_IMPLEMENTATION.md).
This adds actual pending M1 camera records, original-store verification, a
fixed-build prerequisite collector, safe UI publication and verified full-result
exports. It includes the implementation map and explicitly lists the remaining
received-unit, after-restart, native acquisition and physical arm joins.

Previous slice: [physical camera application integration](PHYSICAL_CAMERA_APPLICATION_IMPLEMENTATION.md).
Read this for the public plan/export workflow, exact metadata selection bridge,
camera-only M1/native composition, physical settings contracts, safe fault
projection and current evidence. It lists the remaining physical service,
capture-byte and qualification joins explicitly; a dormant runtime or prepared
intent does not close those tickets.

Previous slice: [native capture and exact arm identity integration](NATIVE_CAPTURE_CONNECTION_IMPLEMENTATION.md).
Read this for the new capture admission/runtime/retained-result APIs, explicit
frame validation and Windows controller metadata callback. Physical dispatch
and the later service/qualification joins remain held and unfinished.

Previous slice: [contained arm-feedback wizard integration](WIZARD_OWNED_ARM_INTEGRATION.md).
Read this for the actual owned child, scoped stage-12 coordinator, strict retained
evidence, original-store verification and operator workflow. Physical serial and
camera activation remain held. The earlier [actual-source wizard preflight](PHYSICAL_PREFLIGHT_INTEGRATION.md)
remains the source-only diagnostic workflow.
Read this for the service/worker/M1 join, operator workflow, scoped native
rehearsal, failure retention and executed tests. It does not close physical
connection or robot-execution acceptance criteria.

The [integration plan](CAMERA_ARM_CONNECTION_INTEGRATION_PLAN.md) explains what
we are building and why. This playbook explains where to work, the order of
implementation, what to test, and what to provide to the next developer.

The destination is one local interface with a real camera preview/settings
page, identity-bound arm diagnostics, guided startup and calibration, and
eventually a handoff to separately qualified robot execution. Hardware is not
available for this development phase. Do not present simulated observations
as received-hardware verification.

For the latest code, launch instructions and evidence, start with the
[workbench guide](WIZARD_WORKBENCH.md) and
[implementation record](WIZARD_IMPLEMENTATION_PROGRESS.md). The ticket text
below retains the complete acceptance criteria; an initial slice does not
close its parent ticket.
The [helper registration checkpoint](WIZARD_IMPLEMENTATION_PROGRESS.md#current-helper-registration-checkpoint)
adds explicit fixed-file inspection and separately reviewed metadata-only
provider registration to the generic-to-native endpoint workflow. See the
[registration API](WIZARD_CAMERA_HELPER_REGISTRATION_API.md) and
[presentation contract](WIZARD_CAMERA_HELPER_PRESENTATION.md). Physical camera
activation, qualified process admission and arm connection remain separate work.

The newer [contained camera integration](WIZARD_OWNED_CAMERA_INTEGRATION.md)
joins the unchanged camera client to the fixed incapable Windows child, real
YUY2 retention, exact M1 campaign evidence, assessment/review and original-store
reopening. It adds a distinct Guided rehearsal action, not physical camera
activation. Read the [process runner](OWNED_CAMERA_FIXTURE_RUNNER.md),
[evidence contract](REHEARSAL_OWNED_CAMERA_EVIDENCE.md),
[reopen contract](OWNED_CAMERA_REOPEN.md) and
[UI/smoke guide](WIZARD_OWNED_CAMERA_PROCESS_PRESENTATION.md) before extending it.

The [probe/configuration increment](WIZARD_CAMERA_CONFIGURATION_INTEGRATION.md)
extends that same path with retained modeled capability reports, immutable
validated mode/control staging and independent capture readback. It also joins
probe-only reopening and exact stage-six settings reuse. The UI and exports
keep these observations explicitly nonphysical; received-unit admission and
the complete DEV-008 acceptance criteria remain open.

The subsequent [native connection-path checkpoint](NATIVE_CONNECTION_IMPLEMENTATION_CHECKPOINT.md)
adds the real feedback-worker/non-purging-owner bridge and distinct native probe
registration, parent handshake, guarded C++ entry and bounded two-message pipes.
Read its exact caller obligations before using those low-level APIs. The physical
dispatcher and independent physical release remain missing. The newer checkpoints
add a distinct no-device physical-diagnostic M1 domain and contained incapable arm
IPC; neither supplies physical device authority or closes those parent tickets.

### First developer session

1. Read sections 1–5 here and the matching section of the integration plan.
2. Set up the workspace environment using section 3. Run the baseline checks
   and record the result before making changes.
3. Claim one ticket from section 6, identify its prerequisites, and fill in the
   task brief in section 11. Do not start by building an independent web app or
   replacing the existing transport/calibration stack.
4. Implement a thin path through contracts, application service, fake worker,
   tests and UI. Add native hardware bindings only at the reviewed boundary.
5. Hand off using the evidence template and review checklist, including what
   remains unimplemented and unverified.

### Navigation

- [Document authority and current state](#2-document-authority-and-current-state)
- [Environment and baseline commands](#3-environment-and-baseline-commands)
- [Code map](#4-code-map-and-edit-ownership)
- [Shared contracts](#5-shared-contracts-developers-must-agree-on)
- [Implementation tickets](#6-implementation-tickets)
- [Build walkthrough](#7-walkthrough-the-first-service-backed-camera-preview)
- [Engineering conventions](#8-engineering-conventions)
- [Test lanes](#9-test-lanes-and-commands)
- [Review and release gates](#10-review-and-release-gates)
- [Task and handoff templates](#11-copyable-task-and-handoff-templates)
- [Troubleshooting and next developer](#12-troubleshooting-and-next-developer)

## 2. Document authority and current state

### 2.1 Which document answers which question?

| Question | Source of truth |
| --- | --- |
| Overall product goals and roadmap | [Master plan](../../ROBOT_TYPING_SYSTEM_MASTER_PLAN.md) |
| Current physical build, frozen inputs and holds | [Build alignment freeze](../../BUILD_ALIGNMENT_FREEZE.md) and its machine-readable dependencies |
| Stage ownership, review, power/effect rules and M0–M12 milestones | [Reviewed wizard implementation plan](PHYSICAL_ONBOARDING_WIZARD_IMPLEMENTATION_PLAN.md) and [foundation contract](../config/physical_onboarding_foundation.json) |
| Camera/arm integration architecture, official sources and P0–P8 packages | [Connection integration plan](CAMERA_ARM_CONNECTION_INTEGRATION_PLAN.md) |
| Developer execution, tests and handoff | This playbook |
| Current v2 storage API and its limits | [M1 runtime guide](M1_ZERO_HARDWARE_RUNTIME.md) |
| Approved physical procedure | [Physical onboarding runbook](PHYSICAL_ONBOARDING_AUTOMATION.md), not development examples here |

A code or configuration change that disagrees with a controlled contract
needs explicit review and a corresponding contract/migration decision. Do not
silently choose whichever document makes an action easier. This playbook
does not activate hardware or supersede a safety gate.

### 2.2 Baseline to preserve

- Existing simulation, fake camera/arm lifecycle, metadata inventory, camera
  adapter, feedback-only serial adapter and calibration contracts are reusable.
- M1 has a real zero-hardware storage facade. The rehearsal-only coordinator,
  M1/OS-lease-owning effect transaction adapter and shared first-thirteen-stage
  service are implemented, including retained binary camera datasets and
  synthetic optics, injected arm identity, typed power-procedure checks,
  retained feedback and source-derived nominal reference fitting.
  The full fifteen-stage service, durable
  physical child admission and qualified physical provider composition are not
  delivered. Separate incapable process/serial tests do not close those gaps.
- The existing onboarding launcher creates a **legacy diagnostic session**.
  M1 `new-v2` is a separate command. Do not mix these stores or claim the
  launcher already produces a working v2 camera/arm interface.
- The current foundation validates with activation false. Its open migration
  gates can coexist with implemented M1 components; do not clear gates merely
  because a similarly named class or passing unit test exists.
- Active Freeze 011 still has a camera-architecture hold. The static-overhead
  B0477 path needs the reviewed successor migration before physical use.
- The purchased camera's exact identifiers, actual lens focus at the intended
  installation, installed firmware and measured geometry remain unverified.

Use independent status fields in tickets and UI:

```text
implementation: PLANNED | IMPLEMENTED
verification: NOT_RUN | UNIT_TESTED | INTEGRATION_REHEARSED | VERIFIED_ON_RECEIVED_UNIT
authority: NONE | explicitly named, independently qualified capability
```

These are reporting conventions, not replacement runtime enums. A test can
pass while a physical stage correctly remains blocked.

### 2.3 Non-negotiable development boundaries

1. No camera activation, serial open or power instruction from imports,
   constructors, status views, page refresh, doctor or session creation.
2. No guessed camera index/COM port as identity; no guessed hardware facts.
3. No direct UI-to-device calls or browser-supplied raw commands.
4. No automatic reconnect, retry, torque change, initialization or motion.
5. No promotion of simulation receipts into physical evidence.
6. No changes to frozen RC03 files, historical freezes or installed evidence
   to make a test green. Fault tests use isolated fixtures.
7. No public/LAN listener, cloud video upload or third-party control client in
   the initial interface.
8. No new motion surface in the commissioning wizard. Later execution uses a
   separately reviewed service and executor.

## 3. Environment and baseline commands

Run from the workspace root in Windows PowerShell. Replace the example root
with your actual checkout location; source code must never hard-code Jack's
user directory.

```powershell
Set-Location C:\Users\Jack\Desktop\robot-arm-build
.\setup-rocell.ps1 -Profile development
```

This setup command **creates/updates `.venv` and installs Python dependencies**.
It does not install a camera or serial driver and does not open devices. Run it
deliberately on a development copy, not as a way to alter an evidence-bound
deployment in use. The `development` profile currently selects serial, vision
and pytest extras. It does not yet provide a browser stack or native compiler.

Do not install a second OpenCV distribution alongside `opencv-contrib-python`.
Use the checked-in dependency constraints. UI/native build pins are a future
ticket, not permission to replace the current environment with arbitrary latest
versions. Normal development/onboarding should not require running as admin.

### 3.1 Zero-device baseline

Run each command separately and stop on nonzero exit status. In PowerShell,
check `$LASTEXITCODE` after native/Python commands; a printed JSON object alone
does not establish success.

```powershell
.\rocell.ps1 host-doctor --profile development --require-pass --json
.\rocell.ps1 physical-onboard verify-foundation --json
.\.venv\Scripts\python.exe software/tools/validate_build_alignment.py
.\rocell.ps1 rehearse-physical-connections --require-expected --json
.\rocell.ps1 rehearse-physical-connections --fault dirty-arm-buffer --require-expected --json
```

Expected baseline, observed during this playbook's verification:

| Command | Meaning of the expected result |
| --- | --- |
| Host doctor | `READY_WITH_PHYSICAL_HOLDS`; development dependencies ready, physical holds still present |
| Foundation | `VALID_ZERO_AUTHORITY_FOUNDATION`; six contracts validated, `runtime_activation: false` |
| Build alignment | `ALIGNED_CAMERA_HOLD_CONTACT_BLOCKED`; no alignment errors, contact remains blocked |
| Nominal connection rehearsal | `COMPLETE_SYNTHETIC`; `expected_outcome_observed: true`; physical operation counters zero |
| Dirty-buffer rehearsal | `EXPECTED_FAULT_BLOCKED`; `expected_outcome_observed: true`; physical operation counters zero |

These are baseline observations, not permanent values to hard-code into future
tests. A reviewed successor can change them; update the documented expectation
and its provenance together. Unexpected source drift is a reason to investigate,
not to regenerate hashes or bypass the check.

### 3.2 Existing versus future commands

| Command family | Current status and appropriate use |
| --- | --- |
| `host-doctor`, `rehearse-physical-connections` | Implemented; use for software readiness and incapable-provider rehearsal |
| `physical-onboard verify-foundation` | Implemented; validates design contracts, not device authority |
| `physical-onboard init-v2-storage`, `new-v2`, `verify-v2-runtime` | Implemented M1 storage operations; see the M1 guide for explicit initialization |
| `physical-onboard new/status/next/record/...` | Existing legacy workflow; do not repurpose it as v2 by changing a label |
| `physical-onboard wizard ...` | Implemented diagnostic/rehearsal interface; use `start-rocell-wizard.ps1 -Check` for an inert check or the [workbench guide](WIZARD_WORKBENCH.md) for explicit launch |
| Native camera helper/build commands | Implemented scaffold/client; actual build commands and qualification limits are in the [native README](../native/windows_camera/README.md). Building is not permission to enumerate, probe or capture |
| Live arm movement/contact | Not available through these onboarding commands |

For unit/integration development, prefer `pytest` temporary directories and
injected clocks/providers. Do not run `init-v2-storage` as a routine smoke test
against `CELL-A` or the shared `software/runs/physical-onboarding` store. M1
tests show how to isolate storage on the appropriate Windows volume. Test-only
unguarded ledger factories must never be copied into application code.

No Git repository is configured in this workspace at the time of writing.
Tickets and PR-sized changes are an organizational convention here, not a
claim that branches or PRs already exist. If work is moved into an approved
repository, follow its collaboration policy; do not initialize/publish a
repository or copy operational evidence as an incidental setup step.

## 4. Code map and edit ownership

The following linked files exist. Remaining target responsibilities are listed
separately; do not create a duplicate service from an early proposed filename.

| Responsibility | Start reading here | Developer rule |
| --- | --- | --- |
| CLI/parser and dispatch | [`cli.py`](../src/rocell/cli.py) | Keep new CLI glue thin; delegate to the shared service |
| Source/stage model | [`physical_onboarding.py`](../src/rocell/application/physical_onboarding.py), [`physical_onboarding_stage_catalog.py`](../src/rocell/application/physical_onboarding_stage_catalog.py) | Derive stage views from the canonical catalog |
| M1 facade | [`physical_onboarding_m1.py`](../src/rocell/application/physical_onboarding_m1.py) | Preserve its zero-hardware public boundary |
| V2 sessions | [`physical_onboarding_v2.py`](../src/rocell/application/physical_onboarding_v2.py) | Stage state is separate from effect-attempt state |
| Attempts and quarantine | [`physical_onboarding_attempts.py`](../src/rocell/application/physical_onboarding_attempts.py), [`physical_onboarding_quarantine.py`](../src/rocell/application/physical_onboarding_quarantine.py) | No hand-edited head/ledger repair or retry path |
| Leases/publication | [`physical_onboarding_leases.py`](../src/rocell/application/physical_onboarding_leases.py), [`physical_onboarding_storage.py`](../src/rocell/application/physical_onboarding_storage.py), [`physical_onboarding_durability.py`](../src/rocell/application/physical_onboarding_durability.py) | Preserve ordered locks and qualified publication |
| Effect taxonomy | [`effects.py`](../src/rocell/safety/effects.py) | Descriptive policy is not a runtime permit issuer |
| Device discovery | [`physical_device_inventory.py`](../src/rocell/application/physical_device_inventory.py) | Metadata only; do not activate sources to improve discovery |
| Wizard service/actions | [`arrival_wizard_service.py`](../src/rocell/application/arrival_wizard_service.py), [`wizard_actions.py`](../src/rocell/application/wizard_actions.py) | Preview/execute and logging own publication; no UI provider calls |
| Metadata selection | [`wizard_device_selection.py`](../src/rocell/application/wizard_device_selection.py), [`wizard_inventory_fixture.py`](../src/rocell/application/wizard_inventory_fixture.py) | Opaque explicit choice, preserve blockers; review is not native enrollment |
| Native endpoint enrollment | [`wizard_native_camera_enrollment.py`](../src/rocell/application/wizard_native_camera_enrollment.py), [`wizard_native_camera_metadata.py`](../src/rocell/application/wizard_native_camera_metadata.py) | Exact generic/native receipt join and staged metadata artifact; no implicit runtime registration, activation or persistent-unit qualification |
| Coordinator core | [`cell_commissioning_coordinator.py`](../src/rocell/application/cell_commissioning_coordinator.py) | Preserve exact admission and distinguish incapable rehearsal composition from qualified physical dispatch |
| Native camera client | [`camera_worker_client.py`](../src/rocell/providers/windows/camera_worker_client.py), [prepared-request API](WINDOWS_CAMERA_PREPARED_REQUESTS.md) | Metadata, preparation and activating probe/capture are separate operations |
| Browser/terminal shell | [`server.py`](../src/rocell/ui/server.py), [`terminal.py`](../src/rocell/ui/terminal.py), [`static/`](../src/rocell/ui/static/) | Same service and bounded projections; no auto-discovery or implicit consent |
| Diagnostic export | [`wizard_diagnostic_export.py`](../src/rocell/application/wizard_diagnostic_export.py) | Assigned launch directory, bounded attachments and verified manifest; not commissioning authority |
| Lifecycle fixtures | [`physical_shaped_onboarding.py`](../src/rocell/application/physical_shaped_onboarding.py), [`physical_connection_rehearsal.py`](../src/rocell/application/physical_connection_rehearsal.py) | Preserve explicitly fake provenance and injected failure accounting |
| Camera contracts/adapter | [`uvc_inventory.py`](../src/rocell/vision/uvc_inventory.py), [`usb_opencv.py`](../src/rocell/vision/usb_opencv.py) | Native Windows identity/media authority must precede OpenCV analysis |
| Arm protocol/transport | [`serial_transport.py`](../src/rocell/arm/serial_transport.py), [`feedback_wire.py`](../src/rocell/arm/feedback_wire.py), [`protocol.py`](../src/rocell/arm/protocol.py) | Reuse framing and validation; onboarding gets its own v2-authorized boundary |
| Sensor evidence | [`sensor_session.py`](../src/rocell/evidence/sensor_session.py), [`b0477_sensor_session.py`](../src/rocell/application/b0477_sensor_session.py) | Do not pretend the existing small-item limits hold full native datasets |
| Calibration/settings epochs | [`static_camera_intrinsics.py`](../src/rocell/calibration/static_camera_intrinsics.py), [`configuration_epochs.py`](../src/rocell/application/configuration_epochs.py) | Physical acquisition is new; synthetic calibration is not installed truth |
| Static geometry | [`static_camera_support.py`](../src/rocell/workcell/static_camera_support.py) | Reuse source-bound loaders; never duplicate board coordinates in JavaScript |

### Remaining integration ownership

The original service, coordinator, browser/static and camera-client scaffolds
are now implemented. The current UI uses static assets, not a separately
required `templates/` layer. Remaining work is a join across those existing
boundaries, not permission to introduce a second connection manager:

- Native-camera runtime registration and fresh pre-open identity validation:
  the endpoint/SetupAPI/CM metadata join and prospective artifact now exist,
  but received-unit qualification and physical-launch provider composition do not.
- Native camera campaign composition: prepared request, qualified child
  admission/containment, settings/readback and complete capture ingestion.
- Native feedback-only arm composition: reviewed identity and power evidence,
  exact one-use admission and the existing non-purging Win32 precursor.
- Installed calibration intake, noncontact acceptance and physical handoff.

Confirm the owning adapter/module against the latest checkpoint before claiming
a ticket. Early proposed `device_binding_service.py`, `camera_campaign_service.py`
and `arm_onboarding_service.py` names are not current callable APIs or a mandate
to create those files.

Coordinate edits to `cli.py`, package exports, `pyproject.toml`, source-bound
configuration and shared schemas through one integration owner per change.
UI, camera and arm developers can work independently against agreed contracts;
they must not each add a competing connection manager, settings store or
permit type. Hardware package and release changes require their own review.

## 5. Shared contracts developers must agree on

### 5.1 Service surface

Use the `ArrivalWizardService` and `CellCommissioningCoordinator` protocol
designs in [wizard plan section 9](PHYSICAL_ONBOARDING_WIZARD_IMPLEMENTATION_PLAN.md#9-application-contracts).
Those design sketches are not a promise of identical callable signatures.
The implemented `ArrivalWizardService` and coordinator core are linked above;
use their current tested contracts. Physical provider composition remains
pending even where the shared rehearsal implementation exists.

Preserve the separation between `view`/`preview_next`, stage/evidence/review
methods, `prepare_acquisition`, and `execute_acquisition`. Preparing an action
does not call a provider. Execution goes through the coordinator, never
straight from an HTTP handler to `SerialTransport.connect` or camera `open`.

Agree on strict versioned request/response schemas before separate teams build
against them. At minimum, bind:

| Record | Required meaning |
| --- | --- |
| Device candidate/binding | Observed identifiers, provenance and binding review; persistent identity separate from ephemeral endpoint |
| Action preview | Exact action kind, prerequisites, expected effects, duration/count/data budgets, settings/plan digest and state challenge |
| Registered action request | Server-resolved action and device binding, session/source/epoch references, request key and expected current state |
| Execution authorization | One-use exact-operation permit owned by the coordinator, not an authority flag supplied by the UI |
| Operation view | Operation/attempt ID, progress, typed reasons, count/timing observations and permitted next actions |
| Result receipt | Requested vs observed values, evidence references, effect certainty and cleanup outcome |
| Reviewed decision | Exact assessment/evidence/current-state hashes and reviewer identity; never a frontend Boolean `passed` |

The browser can submit a candidate ID or server-issued action ticket. It cannot
submit a COM path, camera index, worker module, executable path, T code, raw
bytes, hardware-authority flags or motion coordinates. Keep permit contents
server-side; expose only the narrow transport representation defined by the
reviewed service contract.

Reject unknown fields where the schema is closed, duplicate JSON keys,
nonfinite numbers, ambiguous coercions, oversized values and stale revisions.
Reuse existing validators rather than creating permissive parallel parsers.

### 5.2 Three state machines, not one status flag

1. **Stage:** durable assessment/review progress using `V2StageState`.
2. **Attempt:** durable effect lifecycle using `AttemptState`.
3. **UI:** transient derived progress such as capturing, waiting for operator,
   or awaiting cleanup. UI state is not independently authoritative.

Existing attempt paths:

```text
INTENT_DURABLE -> EFFECT_ARMED -> EFFECT_OBSERVED
              -> CLEANUP_CONFIRMED -> SEALED_KNOWN

INTENT_DURABLE -> ABORTED_PRE_EFFECT
after EFFECT_ARMED + unresolved outcome -> SEALED_UNCERTAIN
```

The first line is one sequential path; use the actual transition definitions
in code. On uncertainty, use the existing cell-global quarantine semantics.
An HTTP timeout or vanished worker does not prove the operation never happened.
Neither a new session nor a new request key clears that uncertainty.

### 5.3 Worker contract

- Use a registered, version/hash-bound worker and a self-contained finite
  campaign specification. No arbitrary executable/module dispatch.
- Preserve `CELL -> SESSION -> CAMERA -> ARM_CONTROLLER` lease ordering.
  Acquire only needed resources, in order. A campaign requiring both devices
  must declare that before dispatch; never dynamically invert the order.
- Revalidate state and physical identity at the relevant locked/pre-open
  boundary. Consume authorization before the first possible effect.
- Inject monotonic clock, I/O adapter and failure points for tests. Report
  open/write/capture/close counts and all cleanup failures.
- One bounded camera campaign owns its handle until cleanup. A web-server
  global must not keep it alive for a later request.
- Start with immutable preview settings. Apply/new snapshot actions follow
  the plan's finish/review/new-campaign rule unless already included in the
  approved capture specification. No hidden in-stream control channel.
- Onboarding serial permits one approved feedback request, not polling or
  raw writes. Unexpected pre-request bytes block the write; do not flush them.
- Limit IPC length, buffers, frame count, wall time and output bytes. Preview
  backpressure may drop display frames; evidence drops need explicit accounting.
- A Stop/cancel request reports cessation/cleanup certainty. Killing the host
  process is not evidence that servo power is off.

### 5.4 Physical versus rehearsal composition

Do not add a frontend-selectable `allow_hardware=true` flag or make the current
sealed fake descriptor claim physical provenance. Rehearsal uses incapable
providers and separate namespace/storage/provenance. Physical composition must
be admitted by the reviewed activation path and registered provider set.

Use shared pure schemas/assessors where appropriate. Hardware-observation
receipts require physical provenance that test doubles cannot manufacture.
The same screen can display either mode, but its mode badge and evidence
status must always be explicit.

## 6. Implementation tickets

Each ticket is intended to be reviewable independently. Split large tickets
into smaller changes while keeping the same acceptance contract. Do not claim
the whole ticket complete when only a schema or mock screen exists.

### 6.1 Dependency and ownership board

The table below defines ticket ownership and dependencies. Initial work on
DEV-000–006 is in progress; see the
[implementation record](WIZARD_IMPLEMENTATION_PROGRESS.md) for partial results
and remaining acceptance. Do not interpret the new diagnostic runner as the
qualified DEV-002/003 physical worker composition.

| Ticket | Deliverable / primary developer role | Build dependencies | Plan mapping |
| --- | --- | --- | --- |
| DEV-000 | Baseline and decisions / integration owner | None | P0 |
| DEV-001 | Service/campaign schemas / backend | DEV-000 | P0, M2/M4 |
| DEV-002 | Effect coordinator / runtime | DEV-001 | P1, M2 |
| DEV-003 | Worker harness and fault injection / runtime | DEV-001; integrates DEV-002 | P1, M2 |
| DEV-004 | Shared service and reviewed fake flow / backend | DEV-001/002/003 | P2, M4/M5 |
| DEV-005 | Browser/terminal workbench / interface | DEV-004 | P2, early M11 |
| DEV-006 | Windows native camera adapter / native | DEV-001; integrates DEV-002/003 | P3, M6 |
| DEV-007 | Binary capture datasets / evidence | DEV-001 | P4, M3 |
| DEV-008 | Camera preview/settings integration / camera + UI | DEV-005/006/007 | P3/P4, M6 |
| DEV-009 | Onboarding serial and power screens / arm | DEV-002/003/004/005 | P5, M8 |
| DEV-010 | Installed-calibration acquisition / vision | DEV-007/008 | P4, M7 |
| DEV-011 | Fifteen-stage integration and successor candidate / integration | DEV-009/010 | P6, M5/M9–M11 |
| DEV-012 | Packaging, independent qualification and activation review / release | DEV-011 | P7, M11/M12 |
| DEV-013 | Received-unit acceptance / commissioning | DEV-012 plus actual hardware/reviews | P8 |

These are **build dependencies**, not permission to connect hardware when a
ticket merges. Native/serial development stays fixture-driven until existing
physical activation and stage gates are satisfied. DEV-006 and DEV-007 can
progress against agreed contracts while the service/UI is being built; their
integration still goes through the coordinator. This is an ownership guide
for developers, not a request to launch agents or change other tasks.

### DEV-000 — Establish baseline and decision records

**Edit:** new developer notes/decision records; no runtime activation files.

Steps:

1. Run section 3 and record platform/interpreter, dependencies, source identity
   and existing failures. Review user-owned/unrelated changes before editing.
2. Read the integration plan's official-software decisions. Preserve existing
   vendor source pins; log any proposed version delta separately.
3. Write short decisions for native helper/backend, optional UI dependency
   packaging, preview campaign bounds, missing serial identity and firmware
   evidence method. Distinguish software decisions from hardware unknowns.
4. Identify the integration owner and reviewer for shared schema/config changes.

**Acceptance:** another developer can reproduce the baseline and knows which
choices are settled, provisional or arrival-blocking. No driver/compiler/UI
dependency is silently installed as part of the decision record.

### DEV-001 — Freeze the service and campaign schemas

**Edit:** proposed typed application/provider contracts and tests; controlled
policy updates only through the reviewed migration path.

Steps:

1. Map existing stage/effect/identity/receipt types to each service method.
2. Define bounded request/result/error shapes and canonical hash ownership.
3. Separate candidate ID from physical endpoint, plan from permit, observation
   from acceptance, and preview pixels from retained native evidence.
4. Publish small deterministic valid/invalid fixtures for other developers.
5. Record versioning and configuration-epoch invalidation rules.

**Acceptance:** serialization round trips are deterministic; unknown/extra
fields, mixed modes/provenance, invalid units, duplicate keys and stale hashes
fail. Imports and object construction perform zero hardware operations.

**Handoff:** schema/type map, fixture examples, reason-code catalog and explicit
list of proposed versus implemented APIs. No browser-specific domain schema.

### DEV-002 — Implement coordinated effects without weakening M1

**Edit:** `cell_commissioning_coordinator.py` and the minimal reviewed
lease-owning persistence boundary it needs; preserve the M1 public contract.

Steps:

1. Define the closed registered-action table and exact-operation permit path.
2. Implement current-challenge checks, ordered leases, durable intent/arming,
   one-use dispatch admission and result reconciliation.
3. Keep record mutation behind a lease-owning boundary. Do not reach into M1
   private fields from handlers or bolt `open_camera` onto its public facade.
4. Classify failed admission separately from uncertainty after arming.
5. Add duplicate request, expired permit and global quarantine behavior.

**Acceptance:** Given two identical execute requests, at most one worker is
admitted. Given stale identity/state or an unresolved prior attempt, no worker
is admitted. Given death after arming, no retry occurs and uncertainty is
handled by the existing quarantine contract. Read-only views never dispatch.

**Handoff:** transition tests, emitted event sequence, lease ownership proof
and known durability qualification gaps. M1 alone is not an effect permit.

### DEV-003 — Build the bounded worker harness

**Edit:** shared worker launcher/IPC schemas and incapable test workers.

Steps:

1. Validate worker executable identity and protocol version before launch.
2. Implement bounded input/output, progress, deadlines, cancellation and
   cleanup reporting; device calls stay outside the UI event loop.
3. Inject failures before/after launch, activation, configuration, read/write,
   result publication and close. Retain the primary and cleanup errors.
4. Prove a stalled child or slow browser cannot grow queues indefinitely.
5. Define process-exit handling without equating process death to stopped arm.

**Acceptance:** malformed IPC, worker crash, over-budget output and timeout
produce bounded outcomes with correct uncertainty. No arbitrary module path,
unregistered worker or repeated dispatch is accepted.

**Handoff:** one minimal fake worker, a fault matrix and integration test
helpers for camera and serial developers.

### DEV-004 — Implement ArrivalWizardService with reviewed fake flow

**Edit:** `arrival_wizard_service.py`, assessment/binding services and tests.

Steps:

1. Implement session view/preview over canonical source/stage projections.
2. Add due-stage evidence intake, pure assessment, exact reviewed commit and
   invalidation; preserve earlier receipts instead of overwriting them.
3. Connect prepare/execute to the coordinator and deterministic workers.
4. Derive blockers/next actions and operation progress from verified state.
5. Keep all physical composition unavailable while rehearsal is developed.

**Acceptance:** the fake flow exercises candidate selection, an approved
camera campaign, assessment/review and a blocked arm action with precise
missing prerequisites. Refresh/review replay does not start an action. Wrong
session/evidence/reviewer/state bindings fail.

**Handoff:** service-level scenario tests and stable view fixtures; no UI
developer needs to import a transport or edit a session JSON file.

### DEV-005 — Ship the first usable workbench in rehearsal

**Edit:** optional UI package, local templates/assets and thin CLI wiring.

Steps:

1. Build Overview, Camera, Arm, Onboarding and Diagnostics screens from the
   service. Provide terminal access to equivalent canonical actions.
2. Display mode/source status, selected device, actual versus requested
   settings, progress, evidence and plain-language next steps.
3. Add action preview/approval, disabled reasons, explicit Stop/cleanup,
   review and export. Keep future motion buttons unavailable with explanation.
4. Implement loopback/session/CSRF/Host/Origin protections and escaped local
   content before introducing any physical backend.
5. Show synthetic images supplied by the same tested service pipeline; do not
   hard-code a separate UI-only success state.

**Acceptance:** a second developer can launch a rehearsal, select the fake
camera, view a labeled image, stage/apply a supported setting, inspect a fake
arm connection failure and resume the correct state after refresh. All
physical operation counts remain zero.

**Handoff:** launch command implemented by this ticket, UI screenshots/test
results, accessibility notes and terminal/browser parity evidence.

### DEV-006 — Implement the Windows camera provider boundary

**Edit:** `software/native/windows_camera/` and the Python worker client.

Steps:

1. Scaffold a reproducible Windows SDK build and native tests; document the
   exact compiler/SDK/architecture and package verification.
2. Separate metadata-only inventory from permitted source activation.
3. Resolve symbolic endpoint identity and native media types; record requested
   and observed format, stride, sample length and available timing evidence.
4. Enumerate supported control ranges/modes, apply a validated setting and
   read it back. Unsupported APIs remain an explicit limitation.
5. Transfer bounded native buffers without JSON/base64; expose no device
   handle to the browser and no silent alternative backend/device selection.

**Acceptance:** injected Windows API tests cover identity reorder/removal,
coerced media type, unsupported control, bad stride and failed shutdown. The
real helper builds, but its received-B0477 verification remains NOT_RUN.

**Handoff:** executable manifest, build/test commands, wire schema, capability
matrix and hardware tests still required. No current-media success may be
reported as exact sensor provenance without supporting observations.

### DEV-007 — Implement native capture datasets

**Edit:** new chunked evidence storage/verifier integrated with M3 contracts.

Steps:

1. Distinguish immutable metadata receipts from large binary datasets.
2. Implement quotas, disk preflight, stride/padding validation, streamed
   hashing, chunks and manifest-last publication with no self-hash cycle.
3. Link native bytes to derived calibration images and preview transforms.
4. Implement reconstruction, verification tiers and precommitted partitions.
5. Test interrupted write/full disk/missing or duplicate chunk paths.

**Acceptance:** small fixtures exercise the full structure; resource-aware
native-size tests cover a frame exceeding the legacy 32 MiB item cap. No
truncated or incomplete package passes. Large frame storage does not require
holding the complete dataset in memory.

**Handoff:** dataset writer/reader/verifier contract, bounds, failure behavior
and opt-in full-size test command. Do not merely raise the global item limit.

### DEV-008 — Join camera preview, settings and evidence

**Edit:** camera campaign service and Camera page; reuse DEV-006/007.

Steps:

1. Wire selection -> action preview -> coordinator -> camera worker -> result
   -> service -> image/status. Enforce identity recheck before activation.
2. Show requested/observed mode and supported electronic controls. Use manual
   focus/aperture guidance for the purchased lens; never pretend autofocus.
3. Keep a finite preview budget and bounded latest-frame display queue.
4. Implement settings changes and snapshot/capture actions as the approved
   campaign lifecycle, with visible cleanup and new settings epochs.
5. Add freshness/quality checks, native calibration preset and explicitly
   separate lower-mode diagnostics if approved by the contract.

**Acceptance:** mode/readback drift, stale image, close failure and replacement
camera never yield a green qualified camera state. A slow client does not
delay evidence accounting or create unbounded memory growth. No automatic
renew/reopen occurs.

**Handoff:** end-to-end fake/native-API scenarios and physical preview/control
acceptance script ready for the received unit.

### DEV-009 — Join arm identity, power ceremony and feedback

**Edit:** arm onboarding service/worker and Arm/power screens.

Steps:

1. Reuse metadata inventory and the configured serial settings; resolve COM
   only from the reviewed controller binding at the final boundary.
2. Implement stages 9–12 exactly: unpowered identity, safety review, observed
   startup, then a separately authorized one-shot feedback campaign.
3. Require an energy envelope for each applicable event and evidence of final
   de-energization. The wizard has no software DC power switch.
4. Configure before open; preserve unexpected bytes; attempt no feedback
   write unless the quiet-buffer and exact permit checks pass.
5. Retain raw/parsed/timing/cleanup evidence and the separate installed
   firmware-identity hold. Never infer firmware revision from a valid packet.

**Acceptance:** injected reset text, stale valid response, partial write,
timeout, changed COM mapping and unknown final power state follow the expected
blocked/uncertain path. At most the one authorized request is attempted. No
torque/motion commands or retry are emitted.

**Handoff:** exact wire-count tests, stage/power dependencies and a checklist
for actual bridge reset/firmware behavior that cannot be proved in simulation.

### DEV-010 — Join installed calibration and board overlays

**Edit:** acquisition service, calibration candidates and Board page.

Steps:

1. Keep stage-7 preliminary focus/coverage distinct from stage-8 installed
   calibration. Detect changed optics/support/settings dependencies.
2. Guide scale-verified chart capture and varied views using the approved
   partition plan; retain native-to-working pixel transforms.
3. Solve/evaluate candidates, held-out stations and uncertainty. Reject
   nominal fallbacks and stale/wrong-device datasets.
4. Draw board, keyboard and phone geometry using canonical loaders and
   measured plane heights, with units and provenance visible.
5. Import robot/reference reports through the existing separate-release
   boundary; do not add a wizard move command to collect calibration points.

**Acceptance:** wrong scale, crop/mode, changed focus, insufficient coverage,
holdout reuse and moved board invalidate the correct outputs. Candidate
calibration never becomes physical authority merely because a solver succeeds.

**Handoff:** calibration dependency map, overlays with coordinate conventions,
data-partition evidence and unresolved physical accuracy limits.

### DEV-011 — Integrate all stages and the prospective successor

**Edit:** full stage service integration, epoch comparisons, bundle/export and
reviewed prospective static-primary migration tooling.

Steps:

1. Complete the 15-stage fake flow and report intake for separately qualified
   reference/noncontact campaigns; preserve progressive intake ownership.
2. Implement returning-startup comparisons and specific invalidation reasons.
3. Render the static-primary successor candidate and review its diff without
   changing old freezes or enabling power/motion/contact by default.
4. Verify the handoff bundle and all current source/evidence/epoch dependencies.

**Acceptance:** rehearsal reaches only zero-authority diagnostic completion;
source or hardware-identity changes invalidate the intended downstream stages.
No export or successful assessment grants typing/tapping permission.

**Handoff:** complete rehearsal transcript, prospective migration report and
the exact independent qualifications still needed for activation.

### DEV-012 — Package and qualify the arrival build

**Edit:** controlled launcher/profile packaging, offline manual, CI/release
evidence and reviewed activation/migration artifacts.

Steps:

1. Pin and verify optional UI/native dependencies and local assets; test a
   clean supported Windows environment and offline startup.
2. Keep old launcher semantics unless a new explicit mode is selected.
3. Run domain/integration/full-size/fault and UI review gates as required by
   M11/M12; collect independent durability and safety review evidence.
4. Apply a reviewed source migration only through its approved workflow,
   then repeat post-apply validation. Keep actual unit facts unfilled.

**Acceptance:** release report identifies what is implemented, simulated and
still physical-unverified; no default connect or resume occurs. A separate
reviewer can reconstruct the build and inspect recovery/export without UI.

**Handoff:** versioned package/source identity, dependency manifest, exact
setup/launch/test commands and arrival acceptance checklist.

### DEV-013 — Received-unit acceptance

**Edit:** retained observations and reviewed successor candidates, not the
original simulated or historical records.

Follow [integration plan section 13](CAMERA_ARM_CONNECTION_INTEGRATION_PLAN.md#13-arrival-day-acceptance-checklist)
and the approved physical runbooks after activation/stage gates pass. Prove
actual camera identity/controls/native capture/near focus, controller identity,
startup/reset and firmware compatibility, then installed calibration and
separately released noncontact behavior.

**Acceptance:** each claim is tied to the received unit and actual test. Keep
diagnostic connection, noncontact qualification and contact qualification
separate. Hardware deviations create reviewed corrections, not hidden
fallbacks. Individual keypress/tap execution is a subsequent scoped release.

## 7. Walkthrough: the first service-backed camera preview

This is the first visible vertical slice for DEV-004/005. It runs entirely
with incapable rehearsal workers until physical composition is qualified.

1. **Arrange a fixture:** synthetic B0477 candidate, reviewed fake prerequisites,
   an exact mode/control snapshot and a finite stream. Keep provenance and
   counters explicitly synthetic.
2. **Load the page:** `view` builds a `WizardView` from verified state. Assert
   zero worker dispatches and zero device operations.
3. **Choose a candidate:** the UI submits only its candidate ID and expected
   revision. The service rejects a stale or ambiguous selection.
4. **Preview an action:** resolve the registered campaign server-side. Show
   selected identity, settings, duration, counts and cleanup expectations.
   Preparing the preview still dispatches no worker.
5. **Approve and execute:** submit the exact current action ticket/request key.
   The coordinator rechecks admission, records the attempt and dispatches once.
6. **Display progress:** stream or poll an operation view, not a device object.
   A bounded derived preview displays its mode badge and frame age. Settings
   readback belongs to the result/progress contract, not guessed UI state.
7. **Stop or finish:** request cessation, await bounded cleanup, then display
   its observed outcome. Do not renew the campaign on browser reconnect.
8. **Assess and review:** a finished campaign produces evidence; a pure
   assessment and exact reviewed decision determine stage progress separately.
9. **Repeat with faults:** changed identity, unsupported control, old frames,
   worker death and failed close. Show a useful reason and no hidden retry.

Minimum tests for the slice:

```text
Given a valid rehearsal session,
when the operator views or refreshes the Camera page,
then no worker is dispatched.

Given an exact prepared action,
when Execute is submitted twice with the same request key,
then only one attempt is admitted and both callers see its status.

Given observed settings differ from the approved settings,
when the camera worker returns,
then the service reports the mismatch and does not accept calibration evidence.

Given the worker outcome is uncertain,
when the operator reloads or creates another session,
then the original attempt/hold remains visible and no operation is replayed.
```

When DEV-006 is ready, replace the injected provider implementation only
through the reviewed physical composition path. Do not change handlers,
stage rules, receipt meaning or source of authority to make real images appear.

## 8. Engineering conventions

### Comments and code organization

- Add module docstrings describing ownership, possible effects, and what the
  module intentionally cannot do.
- Comment invariants and reasoning: why serial-open is gated, why a buffer
  cannot be discarded, why a preview image cannot serve as native evidence.
  Avoid comments that only repeat the next line of code.
- Document units, clock domain, coordinate frame, schema version, memory
  ownership, blocking behavior and cleanup expectations at boundaries.
- Use typed immutable domain values where practical. Keep optional native,
  serial and UI imports out of pure models and normal simulation startup.
- Keep protocol constants/serialization in the protocol layer and authoritative
  geometry in existing loaders. Do not copy packet literals or board dimensions
  into templates, buttons or JavaScript.
- Do not add long domain logic to `cli.py` or HTTP handlers. Those should parse
  transport input, invoke the service and render a result.

### Error and cancellation handling

- Use typed domain errors and a single reason-code-to-remediation map. Separate
  validation failure, known failed action and uncertain effect.
- Preserve the original error and cleanup errors; do not replace both with
  `Connection failed`. Do not swallow exceptions and report success.
- Request cancellation through the coordinator. A lost browser, child process
  or serial connection never proves the arm is stationary or de-energized.
- Retry only pure computation where contractually permitted. Never wrap
  physical operations in generic retry/backoff decorators.
- Log operation/session identifiers, observed timings and hashes. Keep camera
  images and raw telemetry in scoped evidence, not unrestricted debug logs.
  Do not log tokens, secrets or incidental private camera content.

### Efficiency and measurable behavior

- Use finite queues, capped payloads and streaming hashes/writes. Avoid JSON
  frame data, whole-dataset copies and per-frame durable ledger events when the
  approved unit of work is a bounded campaign.
- Keep native capture/device reads off the UI event loop. Limit preview work
  independently of evidence capture; a slow client cannot stall safety state.
- Avoid repeated full-tree hashing or provider discovery on every browser
  animation tick. Use verified cached projections, with mandatory fresh
  challenge/source checks at admission and commit boundaries.
- Inject clocks and deterministic schedules into tests instead of arbitrary
  sleeps. Use deadlines around I/O and bound cleanup as well as the happy path.
- Report performance against the plan's targets and declared host. Do not
  infer 20 MP at 120 fps or require a preview faster than the native mode.

## 9. Test lanes and commands

Use the workspace interpreter. Run all commands below from the workspace root.
These lanes are hardware-free; missing physical hardware must not be turned
into a reason to skip parser, boundary or service tests.

### Lane A — Small existing boundary suite

```powershell
.\.venv\Scripts\python.exe -m pytest `
  software/tests/unit/test_arm_protocol.py `
  software/tests/unit/test_camera_sources.py `
  software/tests/unit/test_uvc_inventory.py `
  software/tests/unit/test_physical_device_inventory.py `
  software/tests/unit/test_physical_onboarding_m1_cli.py -q
```

This exact command passed **88 tests** on 2026-09-07 while preparing this
playbook. Those tests exercise existing boundaries, not the future wizard or
received hardware. Preserve test counts as dated evidence, not acceptance
constants for later versions.

### Lane B — State, storage and domain regression

```powershell
.\.venv\Scripts\python.exe -m pytest `
  software/tests/unit/test_physical_onboarding_m1.py `
  software/tests/unit/test_physical_onboarding_v2.py `
  software/tests/unit/test_physical_onboarding_attempts.py `
  software/tests/unit/test_physical_onboarding_quarantine.py `
  software/tests/unit/test_physical_onboarding_leases.py `
  software/tests/unit/test_physical_onboarding_storage.py `
  software/tests/unit/test_physical_onboarding_durability.py `
  software/tests/unit/test_physical_onboarding_foundation.py `
  software/tests/unit/test_physical_onboarding_stage_catalog.py `
  software/tests/unit/test_configuration_epochs.py -q
```

Storage tests require the appropriate Windows/local-volume conditions and
can be skipped by platform guards elsewhere. A skipped qualification test is
not evidence that its guarantee passed. Record skips and their significance.
Never redirect these tests to a shared operational ledger.

### Lane C — Lifecycle, evidence and calibration regression

```powershell
.\.venv\Scripts\python.exe -m pytest `
  software/tests/unit/test_physical_shaped_onboarding.py `
  software/tests/unit/test_sensor_session_evidence.py `
  software/tests/unit/test_b0477_sensor_session.py `
  software/tests/unit/test_static_camera_intrinsics.py `
  software/tests/unit/test_static_camera_support.py `
  software/tests/integration/test_physical_onboarding_cli.py -m "not slow" -q
```

### Lane D — Whole repository and explicit slow qualification

```powershell
.\.venv\Scripts\python.exe -m pytest software/tests -m "not slow"
.\.venv\Scripts\python.exe -m pytest software/tests -m slow
```

Run the second command only with a deliberate time/memory/disk budget. Even
the non-slow suite can take many minutes. Neither whole-repository lane was
run for this documentation change. New native/full-size suites must publish
their exact commands, resources and opt-in behavior when implemented; the
current `slow` marker does not prove future tests already exist.

### Wizard integration tests alongside each ticket

For a change to the reboot/new-launch join, first run the two cheap startup
and original-discovery checks, then the trial-prefix reopen check, then the
full public acceptance. These exercise the same real new-application
constructor. They catch missing packaged profiles and incorrect original
lineage before spending a full predecessor run. A lower-level M1 decoder test
does not replace public discovery/reopen in a new application.

```powershell
# Repeat this assignment before EACH command to reserve a new, never-used path.
$RebootTestRun = Join-Path '.codex-preserved' ('reboot-dev-' + [guid]::NewGuid().ToString('N'))
if (Test-Path -LiteralPath $RebootTestRun) { throw 'Test output already exists; choose a new path.' }
.\.venv\Scripts\python.exe -m pytest `
  software/tests/unit/test_arrival_usb_reboot_ntfs_acceptance.py -m 'not slow' `
  -q -x --tb=short --basetemp=$RebootTestRun --junitxml="$RebootTestRun-results.xml"
```

After a passing small run, use the same options with a new `RebootTestRun`
and one exact test node instead of the file plus `-m 'not slow'`:

- Prefix: `software/tests/unit/test_arrival_usb_reboot_ntfs_acceptance.py::test_fresh_trial_prefix_reopens_through_public_application`
- Full: `software/tests/unit/test_arrival_usb_reboot_ntfs_acceptance.py::test_public_reboot_all_actions_export_and_fresh_reopen`

Both larger checks require Windows/local NTFS. Do not run the whole slow file
unintentionally when one exact node is sufficient. Preserve each failed test
directory and its JUnit report; pytest can erase a reused `--basetemp`.
Keep source/configuration and the selected test fixed throughout the full run.
Do not run competing storage/performance suites during timing acceptance.
The work order records current timings and failures; these commands alone do
not imply passing public v13 or received-hardware acceptance.

The original proposed test list has been superseded by real service,
coordinator, worker, capture and interface tests. The current metadata and
helper-registration increment has this runnable focused lane:

```powershell
.\.venv\Scripts\python.exe -m pytest -q `
  software/tests/unit/test_wizard_device_selection.py `
  software/tests/unit/test_wizard_device_selection_integration.py `
  software/tests/unit/test_arrival_wizard_device_selection_ui.py `
  software/tests/unit/test_windows_camera_preparation.py `
  software/tests/unit/test_wizard_native_camera_metadata.py `
  software/tests/unit/test_wizard_native_camera_enrollment.py `
  software/tests/unit/test_wizard_native_camera_integration.py `
  software/tests/unit/test_wizard_native_camera_enrollment_ui.py `
  software/tests/unit/test_wizard_camera_helper_inspection.py `
  software/tests/unit/test_wizard_camera_helper_registration.py `
  software/tests/unit/test_wizard_camera_helper_integration.py `
  software/tests/unit/test_wizard_camera_helper_registration_ui.py
```

The selected regression scope and latest actual results are recorded in the
[implementation record](WIZARD_IMPLEMENTATION_PROGRESS.md#current-helper-registration-checkpoint).
Use that record for actual evidence and the exact broader command. File names
and test counts are not ticket completion criteria.

Use existing file layout conventions and avoid duplicate coverage where an
existing module is extended. Every new effectful boundary needs at least:
zero-I/O import/status test, exact identity binding, stale challenge, duplicate
request, byte/frame budget, timeout/cancel, crash-before/after-effect and cleanup
failure tests. Test invalid messages against fixtures, never physical devices.

For UI parity, compare canonical requests, receipts and stage outcomes while
allowing documented differences in cookies/nonces/presentation timing. Test
disabled controls server-side as well as visually. A disabled HTML button is
not an authorization boundary.

The development extra does not currently pin formatter/type-checker tools.
Before adding them to required CI, choose/pin the tools and configuration in a
reviewed dependency change. Do not tell another developer to run an unavailable
lint command or silently install tooling into a qualified deployment.

### Original playbook-authoring verification (historical)

Completed during authoring: Lane A; host doctor; foundation check; alignment
validator; nominal and dirty-buffer rehearsals; existing CLI help inspection.
All completed checks returned exit code 0. Both rehearsals reported zero
physical effect counts. Setup/install, M1 deployment initialization, lanes
B/C/D, native build, UI tests and all physical checks were **not run**.
This paragraph records the original documentation-only authoring pass, not the
subsequent implementation status. Later native build, UI and selected software
test evidence is retained by source in the implementation record; physical
received-unit checks still have not run.

## 10. Review and release gates

### Before merging or handing off any ticket

- [ ] Scope and dependencies match the ticket; unrelated changes preserved.
- [ ] Proposed APIs are labeled proposed until implemented and tested.
- [ ] Changed schema/source/epoch dependencies are listed.
- [ ] Tests cover the negative path and operation counts, not only output text.
- [ ] No hidden import/open/retry/motion path was added.
- [ ] Settings and unit observations remain distinct from expected values.
- [ ] No test-only bypass, fake permit or unguarded publisher reached runtime.
- [ ] Partial work, failures and skipped tests are reported explicitly.
- [ ] Comments explain the new invariant and the applicable physical limit.
- [ ] Docs, actual CLI help and example commands agree.

### Independent review required before physical activation

Use the existing M12 qualification requirements, not this checklist as a
substitute. Review effect permits, durable attempt boundaries, process/lock
ownership, power ceremonies, unknown outcomes, installed firmware, native
capture provenance, source migration and diagnostic-only scope. The author
should not self-certify the physical safety/qualification claim.

Neither a passing unit suite nor a camera image is a release. Frame acquisition
does not prove focus/calibration. A valid feedback packet does not prove home,
firmware identity, controller/model equivalence or safe contact.

### Stop conditions during development

Stop the affected work item and record the issue when a required guarantee
needs a new authority, destructive migration, third-party installation or
unavailable hardware observation. Continue independent in-scope fixture/UI work
where possible. Do not remove the failing gate, delete evidence, or repeatedly
connect devices to get past a blocker.

If actual hardware is unexpectedly connected, keep development scripts and
tests hardware-inert. Physical experiments belong to a separately authorized
commissioning session using the prepared acceptance procedure.

## 11. Copyable task and handoff templates

Keep these records with the task/change. If a repository is later established,
use its issue/PR system; otherwise use a clearly named development note. Do not
place developer progress notes inside operational evidence stores.

### 11.1 Task brief

```text
Ticket ID / title:
Owner / reviewer:
Status: PLANNED | IN_PROGRESS | BLOCKED | IMPLEMENTED_PENDING_REVIEW | ACCEPTED
Companion plan section / P package / M milestone:
Prerequisite ticket evidence:

Outcome visible to a developer/operator:
Existing entry points reused:
New types/APIs/files proposed:
Files permitted to change:
Explicit non-goals:
Physical authority: NONE for pre-hardware development

Contracts/invariants preserved:
Schema/source/epoch impact:
Happy-path acceptance scenario:
Fault/negative acceptance scenarios:
Existing test lanes:
New tests and commands:
Hardware observations deferred:
Expected handoff artifacts:
```

### 11.2 Small architecture decision

```text
Decision ID / date / owner:
Question:
Relevant controlled contract:
Options considered:
Selected approach and why:
Official source/version/license references, if introducing a dependency:
Assumptions versus received-hardware unknowns:
Tests needed to validate the choice:
Effect on existing modules and configuration epochs:
Fallback/rollback plan without replay or evidence deletion:
Review status:
```

### 11.3 Developer handoff

```text
Ticket(s) completed or partially completed:
Implementation status:
Verification status:
Physical authority/status:

Source/package identity and changed files:
What now works, stated in operator terms:
Exact command to demonstrate it:
Existing APIs changed / new APIs added:
Important module interactions and ownership:

Checks actually run:
  command | exit code | passed/failed/skipped | duration | environment
Checks not run and why:
Faults demonstrated and observed device-operation counts:
Evidence/output locations (no incidental private data):
Source/config/schema/epoch invalidations required:
Unresolved issues and received-hardware checks:

Next developer's first task:
First file(s) to read:
Prerequisites still missing:
Explicit do-not-do warnings:
Reviewer outcome:
```

### 11.4 Ticket acceptance record

```text
Ticket:
Reviewed change/source identity:
Reviewer:
Acceptance scenarios satisfied:
Remaining limitations / accepted deferrals:
Required follow-up ticket(s):
Implementation accepted: YES/NO
Verified on received hardware: YES/NO
Physical authority granted by this developer review: NONE
Separate qualification/release reference, if one later exists:
```

## 12. Troubleshooting and next developer

| Symptom | First investigation | Do not do |
| --- | --- | --- |
| Foundation valid but gates open | Compare implemented components with migration/activation milestones | Clear gates based on class names |
| M1 session refuses reuse after edits | Inspect source binding and successor-session rules | Edit the saved hash or delete ledgers |
| `wizard` command missing | Check whether DEV-004/005 is actually implemented | Invent a launch command in the handoff |
| No preview without hardware | Use the explicit rehearsal composition and synthetic image fixture | Open an arbitrary laptop webcam automatically |
| Camera index or COM number changes | Inspect persistent binding and endpoint resolution | Persist the first numerical match as identity |
| Expected fault rehearsal exits 0 | Check `expected_outcome_observed` and outcome/counters | Treat the deliberately blocked fault as a failed test |
| Native helper/driver unavailable | Report missing supported capability and exact environment | Install unknown packages/drivers or silently swap backend |
| Serial packet parses but stage blocked | Inspect firmware, power, freshness and cleanup evidence | Treat parsing as complete commissioning |
| Test helper grants authority easily | Confirm it is isolated test scaffolding | Reuse its fake released build or unguarded ledger in production |
| Calibration or phone targets fail | Inspect dependency epochs and measured target error budget | Inflate tolerances or substitute nominal geometry |

**Recommended first assignment:** DEV-000 and DEV-001. Preserve the verified
baseline, publish the service/worker contract fixtures, and hand those to the
coordinator and interface developers. The first useful integrated demo is
DEV-004/005's service-backed rehearsal Camera and Arm pages; do not wait for
physical hardware to make those pages usable.

Update ticket status only with evidence. Keep this playbook, the integration
plan, actual CLI help and code aligned as implementation advances. This
playbook's creation adds documentation/navigation only; it does not implement
the listed tickets or change hardware authority.

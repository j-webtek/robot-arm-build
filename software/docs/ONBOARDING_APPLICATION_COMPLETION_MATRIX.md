# Onboarding application: completion evidence and remaining work

Audit date: 2026-09-10; P1 implementation update: 2026-09-12.
This is an implementation-status companion to the
[connection plan](CAMERA_ARM_CONNECTION_INTEGRATION_PLAN.md) and
[developer playbook](CAMERA_ARM_DEVELOPER_PLAYBOOK.md), not a reduced goal.
The target remains a usable local application that connects the selected
camera and RoArm-M3 Pro, guides safe commissioning, runs the necessary tests,
and preserves useful failure diagnostics. Later motion/contact permission
remains separate from connection and feedback testing.

## Current evidence

Upcoming camera/UI implementation is sequenced in the
[commissioning roadmap](CAMERA_UI_COMMISSIONING_ROADMAP.md) (2026-09-13).
It defines durable evidence, continuity, separate review, freshness, integrated
acceptance and received-camera checkpoints, plus static simulation and installed
calibration handoff. Its milestones are plans, not completed commissioning.

Durable-camera M1 continuation (2026-09-13): the
[work order](CAMERA_DURABLE_EVIDENCE_WORKORDER.md) separates stage-local UI holds
from later qualification and adds a pre-seal capture checksum to original
accounting/storage. The [storage compatibility batch](../runs/wizard-exports/camera-durable-evidence-20260913-02/README.md)
passed 384 fixed-input checks. A [producer integration](../runs/wizard-exports/camera-durable-evidence-20260913-03/README.md)
adds the guarded read inside the existing consumed campaign, exact versioned
plans and extra record headroom; 55 producer/storage development tests passed,
including actual M1 fresh-store reopening with modeled native owners. Its
fixed-input compatibility batch passed **268 tests** across all 15 selected
modules, with unchanged source/inputs and no failures/errors/skips. These counts
belong to separate source revisions and are not additive. Public wizard defaults still
use the previous capture profile. Public admission/ingestion/assessment joins,
durable proposal/assessment records, separate review and later milestones remain
open; none of these tests qualify hardware or complete roadmap M1.

Camera saved-pixel continuation (2026-09-13): the
[pixel-assessment work order](CAMERA_PIXEL_ASSESSMENT_WORKORDER.md) adds actual
saved-file checks to the existing original-evidence assessment and its wizard
checklist. Earlier logged launch checksums are joined to original native capture
subjects; missing or changed files remain unverified. This is a diagnostic v2
report, not canonical stage-5 assessment/review or physical qualification.
No device access or settings changes occurred in this increment. The work order
records its selected tests separately from the historical checkpoints below.

Operator UI update (2026-09-12): [UI acceptance](UI_APPLICATION_HANDOFF.md) and
[operator guide](UI_OPERATOR_GUIDE.md). All 130 current registered forms are
reachable with unchanged per-action gates; final selected fixed-input UI/service
acceptance passed 906 checks. This completes the interface enhancement, not
physical commissioning or the outstanding camera/static-task work. Separately
gated physical arm diagnostics must not be confused with the held general
Connect/motion controls. Historical entries below retain their original scope.

Latest received-arm update (2026-09-12): [USB onboarding progress](ARM_USB_RECEIVED_UNIT_PROGRESS.md).
The CP210x missing native-interface property defect is fixed and the attached
USB unit correlates to COM6 in actual wizard metadata checks. Serial opening,
feedback and motion remain unreleased. Separately, camera full-history run 06
has terminated FAILED at a partial-fixture source check after probe/settings
staging succeeded; any older IN_PROGRESS entry below is superseded.

The [existing-root successor](STORAGE_EXISTING_ROOT_OBSERVATION_WORKORDER.md)
removes a duplicate ancestry walk inside one root-establishing helper, retaining
later file containment, fresh handle checks and independent admission audits.
**796 earlier distinct selected checks passed** on source `01440cf0…91eb9`, including a
mixed USB/camera profile. Full-history run 06 passed probe/capture release, then
failed post-capture ingestion at a missing test-source alias. The fixture-only
correction passes its 46-case regression. Run 07's complete test passes in
2,242.325 s, but its final source audit rejects concurrent arm/UI changes to
`af19e6a3…7d615c`. The verified export and clean final readback are retained;
fixed-source acceptance remains open. A later 144-case restart/export/UI
selection passes on the changed checkout and is not combined with the earlier
checks as one frozen release. Coordinate or isolate source before repeating acceptance.
Camera/arm hardware remains untouched and physical
release unchanged. The runs below are preserved historical evidence.

The [bounded-read buffer successor](CAMERA_BOUNDED_READ_BUFFER_WORKORDER.md)
measures and reduces Windows file-buffer allocation/copying without removing
file reads, path/handle checks or independent original validation. **681 distinct
selected checks pass**, including the expanded history profiler, on source
`a654894e…9898c`; fresh full-history
run 05 failed the complete startup deadline after 34:10. Source/test inputs
remained fixed. This is not a full-history PASS or
received-camera qualification. Previous failed originals remain unchanged.
The new profiling cases expose increased metadata/ledger cost as prior campaigns
accumulate; passing those tests is not startup-deadline acceptance.

The [P1 coherent-observation update](CAMERA_COHERENT_OBSERVATION_WORKORDER.md)
removes one redundant fresh camera session read while retaining all independent
record/global checks, permits and deadlines. **417 targeted tests pass**;
fresh full-history run 04 **fails** the final release admission deadline after
39:06. Its 2.031 s release check is still too slow for the 2 s total startup
window. Settings/capture/camera exports were not reached. Detailed originals,
timings and the next profiling ticket are retained; no hardware was accessed.
P1 and the [six-step plan](PRE_ARM_CALIBRATION_EXECUTION_PLAN.md) remain incomplete.

The [startup-failure diagnostics update](CAMERA_ATTEMPT_FAILURE_DIAGNOSTICS_WORKORDER.md)
(2026-09-12 UTC) carries verified original supervision causes into the public
camera error and normal/exact-attempt exports. Incapable-peer tests exercise
probe and settings-capture admission deadlines without changing their limits.
That diagnostics-only change improved failure reporting, not performance.
Runs 03 and 04 remain terminal failures; received-camera capture is unqualified.

Pre-build update (2026-09-11 local): the received-camera bench tests remain
separate from original commissioning. Optics/distance checks are deferred until
assembly at the operator's request. The new wizard `prebuild_vision_checks`
action groups seven **synthetic, no-device** checks with standard operation
retention/export. Selected verification: 287 tests passed plus a real diagnostic
child/export run; no physical stage changed. See the
[pre-build operability playbook](PREBUILD_OPERABILITY_PLAYBOOK.md) for the exact
checkpoint, next live-integration work and remaining limits.

Current integrated camera slice: [settings-capture wizard handoff](CAMERA_CONFIGURATION_WIZARD_HANDOFF.md).
The public `physical_camera_configuration_capture` action joins exact logged
settings, original admission/capacity, the existing native runtime, one-frame
readback, completion-gated still-image publication and per-attempt export.
Its selected 679-test checkpoint uses incapable producers and synthetic pixels;
predecessor semantic authentication remains modeled in that lane. It is not
full-history, received-camera or stage-acceptance evidence.

The [full-history integration work order](CAMERA_FULL_HISTORY_INTEGRATION_WORKORDER.md)
extends the existing fresh NTFS four-phase predecessor through public reopening,
current logged metadata, preparation/review and probe/settings/capture/export.
Run 01 failed before probing on an invalid synthetic portable operator label;
the full four-phase predecessor and subsequent mode entry/reopening completed.
The fixture and preview validation are corrected. Fresh run 02 reached public
probe preparation/review, then failed the final probe admission deadline;
uncertain original retention and quarantine remained intact. End-to-end
settings capture/export acceptance is still unproven. See the
[wizard usability/input handoff](CAMERA_WIZARD_USABILITY_HANDOFF.md)
for the current camera-page improvements and their separate test/browser evidence.
Original readers, leases, runtime file verification and timing gates are not
substituted. Source identity and physical observations remain explicitly modeled.

Stage-5 policy assessment/review, stage-6 freshness, installed optics/placemat
calibration, original-bound arm startup/feedback and final handoff still require
software integration as well as separate received-hardware evidence.

The actual browser walkthrough also found a separate task-model migration gap:
the locked nominal task simulator still uses the legacy eye-on-arm calibration
graph, although original onboarding selects static-primary. Both `hi` task
reports expose provisional IK failures. See the
[static-task migration work order](STATIC_TASK_SIMULATION_MIGRATION_WORKORDER.md)
and the verified browser/export evidence in the usability handoff. Worker
success does not establish full path feasibility or overhead-camera calibration.
The [task-feedback/full-resolution checkpoint](TASK_FEEDBACK_AND_FULLSIZE_CHECKPOINT.md)
now implements visible worker-versus-feasibility warnings and early settings-ID
validation, and tests full-sized synthetic YUY2 byte ingestion. It does not
migrate the task model or repair the remaining probe admission timing failure.

A [staged mode/control policy prototype](../../.codex-preserved/camera-mode-policy-draft-20260910-01/README.md)
now has 71 passing pure tests. It compares the selected full native mode and
manual controls, with explicit UNKNOWN persistence/lens/original evidence. It
is not installed in the wizard and cannot pass stage 5. The post-capture
original reader, assessment/review suffix and UI join remain software work.

### Historical component checkpoints

The entries below describe their checkpoint dates, not current missing-work
lists. Use the current table and next milestones for implementation decisions.

Previous increment: [public original-bound camera probe](CAMERA_PROBE_PUBLIC_WIZARD_CHECKPOINT.md).
Current logged metadata, substantive original admission/capacity, actual M1/v2
dispatch and completion publication now join through the public probe action.
A separate bounded attempt export and inert status card preserve failures.
Verification uses incapable native producers and modeled hardware facts. Stage-5
acceptance, public capture/calibration and physical RoArm connection are unfinished.
The shared default deny and separate later motion/contact gates remain intact.

Previous increment: [camera probe preparation wizard](CAMERA_PROBE_SETUP_WIZARD_CHECKPOINT.md).
File-only Prepare/Review, current logged metadata provenance, bounded browser
display and complete preparation/failed-attempt export are joined to Setup and
Arrival. A real NTFS test caught and verified the fix for blocked-stage review
storage. Complete public original-store composition, substantive admission facts,
capacity checks and physical probe/capture/arm connection remain implementation
work. This does not describe those holds as merely awaiting hardware.

Previous increment: [camera-v2 original-result and application handoff](CAMERA_ACTIVATION_HANDOFF_WORKORDER.md).
The same dispatch owner now rereads both original roles; the existing acquisition
service/data workflow handles probe, settings, capture readback and actual image
ingestion with staged publication. Initial focused tests pass 46 cases, including
three actual NTFS/M1 reopens with modeled device/admission facts. Original v16
admission/public UI/export and arm startup remain unfinished software work.

Previous increment: [installed camera-v2 runtime and enforced software policy](CAMERA_ACTIVATION_RUNTIME_WORKORDER.md#installed-runtime-checkpoint).
The new native workers accept only their fixed purpose, preserve legacy builds,
and pass incapable tests. Actual installed-file verification is called inside the
scoped campaign. The original acquisition/service/UI connection is still missing;
camera-capable binaries have not been executed and hardware is not qualified.

Previous increment: [camera-v2 scoped execution and output ownership](CAMERA_ACTIVATION_CAMPAIGN_CHECKPOINT.md).
The actual internal campaign now joins current scope to the supervisor and returns
exact retained diagnostics. Fresh Windows directory pinning and late-interruption
retention are tested. The approved native runtime and original acquisition/UI/
preview/export integration remain unfinished; hardware access is not enabled.

Previous increment: [camera-v2 coordinator/original retention](CAMERA_ACTIVATION_STORAGE_CHECKPOINT.md).
The new camera-only evidence pair, bounded parts/index, evidence-first uncertain
execution and complete-family M1 audit/readback are implemented. Final selected
coverage passes 687 checks; 38 actual local-storage checks pass with modeled
device facts. The admitted v2 campaign/runtime and
original acquisition/UI/export join remain unfinished; physical access stays held.

Previous increment: [v2 owned process supervisor](CAMERA_ACTIVATION_SUPERVISOR_CHECKPOINT.md).
The internal exact-preparation lifecycle now produces real before/after cleanup
observations and correctly bound v2 run records. Final selected coverage passes
502 checks, including 55 modeled supervisor cases and 20 real Windows exchanges
with an incapable helper. At that checkpoint, runtime review, active M1/campaign
binding, larger camera-specific original retention and UI joins remained work.

Previous increment: [v2 retained observations and application accounting](CAMERA_ACTIVATION_EVIDENCE_CHECKPOINT.md).
The new bounded record preserves unavailable observations and complete native
result bytes, independently re-verifies them and feeds the existing effect model.
Final focused tests pass 108 checks; selected regressions pass 653 and the separate
legacy-accounting/export/incapable-process lane passes 118. At that checkpoint
the live supervisor had not yet been implemented; the campaign/original-store
retention and UI join are still unfinished.

Previous increment: [v2 preparation and owned parent integration](CAMERA_ACTIVATION_PARENT_CHECKPOINT.md).
The installed shared parent now handles v2, with fixed process limits and a new
pipe-only Windows transport. Final focused coverage passes 149 checks including
22 actual pinned/Job-contained incapable-child exchanges and Stop/denial cases.
The live retention join, original facts, runtime review and UI dispatch remain
unfinished; the source differs again from earlier checkpoints.

Newest code increment: [installed v2 camera wire validation](CAMERA_ACTIVATION_RESULT_CHECKPOINT.md).
The expectation bridge, independent identity comparison, probe/capture request
and full result codecs are now in the codebase. Selected regressions pass 380
checks; the overlapping native interop lane passes 168. These are inert codecs,
not yet the original-facts/runtime/dispatch/UI connection. The new application
source differs from the earlier full NTFS acceptance source.

Latest component status is in the [entry/cleanup checkpoint](CAMERA_ENTRY_CLEANUP_CHECKPOINT.md).
The modeled public entry flow and 585 selected fast/regression checks pass after
fixing operator-label consistency and camera permit first issuance. Native worker
cleanup now compiles and passes incapable tests. Fresh public NTFS run 01 failed
at the label boundary; run 02 failed at the pending-stage storage boundary.
The [storage fix and real-storage tests](CAMERA_ENTRY_STORAGE_CHECKPOINT.md)
address that second integration defect. Fresh full public run 03 now passes in
2,230.09 s, including both exports and fresh-app v15 reopen without replay.
No physical hold was released. A separately compiled native v2 integration
draft advances camera acquisition; its pure Python codecs are now installed,
but the native worker and physical route are not installed/registered yet.

## Current requirement matrix

| User-facing requirement | Implemented foundation | Still needs software/application work | Still needs received-hardware evidence |
| --- | --- | --- | --- |
| Launch, navigation, status, Stop | Shared service-backed browser/terminal workbench; explicit action tickets; inert startup | Final packaging and returning-day configuration comparison/remediation | Clean-host installation and runtime qualification |
| Identify the camera | Receipt/metadata review; four-phase original USB trial; full public v14/v15 review, entry, exports and fresh-app reopen; original probe preparation and current logged metadata | Verify the combined full-history path into acquisition and returning-launch ownership | Actual unit/driver/USB speed/topology and reconnect/reboot continuity |
| Connect camera and see images | Public original-bound probe and settings-capture actions, runtime checks, one-frame ingestion, completion-gated still image and per-attempt export | Combined full-history acceptance, stage-5 policy assessment/review, stage-6 freshness and image-health guidance | Received modes, controls/readback, throughput, actual freshness and cleanup |
| Preserve camera operating evidence | Stage-ownership UI projection; checksum-bearing internal capture producer, original receipt/storage and fresh-store reopen; existing public captures remain on their prior profile | Public migration, durable proposal/assessment/review subjects, UI/export/restart joins and integrated fault acceptance | Real camera continuity, settings and freshness; installed optics remain separate |
| Focus, coverage and calibration | Synthetic intrinsics/registration checks; nominal board geometry | Physical chart acquisition, corner crops/quality guidance, measured overlays, solver/review and installed calibration candidates | Actual near-focus, lighting, support stability, surveyed geometry and held-out accuracy |
| Arm identity and supervised startup | Generic/native controller metadata, two-boundary identity resolver, incapable feedback/power rehearsals | Original stages 9–12 submission/review services, controller/model/firmware/boot binding, supervised energy observations, qualified physical worker and result publication | Pro/controller association, firmware/reset behavior, startup input, bounded feedback exchange and independent final power-off observation |
| Fault review and exports | Notes, complete failure retention, unique verified exports, original reopening without replay; separate original probe/settings-capture attempt exports | Join arm connection/power and future calibration receipts to the existing logging/export system; final commissioning handoff | Real fault/cleanup observations; software Stop must not claim physical de-energization |
| Keyboard and Android tasks | Semantic task compilation and nominal geometry/IK/vision simulation; actual browser keyboard/phone rehearsal and verified export; visible worker-versus-feasibility warnings and legacy-model disclosure | Versioned static-primary task/calibration migration; investigate sampled IK gaps; complete onboarding/handoff before separately qualifying a live motion/contact executor | Tool/contact setup, reference-frame validation and physical noncontact/contact acceptance |

The confirmed export parent is
`C:\Users\Jack\Desktop\robot-arm-build\software\runs\wizard-exports`.
Do not build a second logging/export system for the remaining connection work.

## Historical full-history results

**Complete-series acceptance:** complete-series run 01 passed in **2,090.53 s**.
The complete four-phase original chain, final ASSESS/REVIEW actions, exact
subject/publication checks, full v7 export/restore and fresh public reopening
without replay pass. Original storage, leases and logs are real; hardware and
process observations are modeled. The accepted identity stage is PASS; later
stages remain pending, both devices remain disconnected, and no physical
permission follows. The [accepted checkpoint](../runs/wizard-exports/hardware-free-usb-complete-accepted-20260909-01/README.md)
preserves the 599-file original, exact 361-file source snapshot and independently
verified ordinary bundle in the confirmed folder. Post-pin margin was 0.922 s,
so this is not a general timing guarantee.

**Predecessor acceptance:** full AFTER_REBOOT run 07 passed in 1,735.50 s, with
actual storage/logs and explicitly modeled hardware/process observations. All
eleven reboot roles, seven events, complete v6 export/restore and fresh public
reopen/no replay passed. Final quarantine was false. The complete accepted
store and an independently verified ordinary export are in the confirmed
folder. Timing margin remains narrow (0.782 s above the post-pin reserve).
See the [reboot work order](USB_AFTER_REBOOT_IMPLEMENTATION.md) for exact scope.
This supersedes the historical pending checkpoints below, not the remaining
camera/arm integration rows above.

**New reader checkpoint:** the additive v14 complete-series original Session
join and every partial-publication/rejection boundary pass with modeled
observations; legacy interface, quota, source and epoch regressions also pass.
Both launcher modes still start disconnected and use the confirmed export
parent. See the [complete-review work order](USB_COMPLETE_SERIES_IMPLEMENTATION.md)
for exact tests and historical source fingerprint. The successor now installs
Setup/USB assessment/review actions, both UI projections and complete v7 exports.
The modeled service/UI join passes in 206.40 s, including unchanged originals,
publication gating, both renderers, inert navigation and full export restore.
The selected public-contract/display/export regression suite passes 286 checks.
Full fresh public v14 acceptance subsequently passed as recorded above.
The next-entry original v15 reader was installed afterward: 254 fast contract,
layout and join-guard tests plus 10 composed modeled original-reader checks
pass. It verifies the full unchanged predecessor and distinguishes incomplete
retention from the committed stage-5 entry. The next increment adds the one-shot
Setup action, both interfaces and full entry export: 281 fast checks, 389 existing
regressions and one full modeled public entry/UI/export test pass. Stage 5 is
only `WAITING_OPERATOR`; no device opens. Fresh public NTFS entry, both exports
and fresh-app reopen subsequently passed in run 03 (2,230.09 s), as detailed in the
[camera acquisition work order](CAMERA_IDENTITY_TO_ACQUISITION_WORKORDER.md).
The earlier selected wizard/display/export and full legacy v14 reader regression
run passes 287 tests. Both current launch modes remain disconnected with zero
operations and the confirmed export parent.

Historical failed reboot runs remain preserved and documented in the
[reboot work order](USB_AFTER_REBOOT_IMPLEMENTATION.md). They exposed fixture,
mixed-inventory and timing issues before the successful run 07. The
[storage performance record](STORAGE_ADMISSION_PERFORMANCE.md) documents the
validated optimizations without reduced audits or longer admission deadlines.
Those historical failures are not the current acceptance status, and the later
pass does not turn their consumed attempts into retryable original stores.

## Hard-coded holds are unfinished integration, not hardware-only blockers

The following current source paths make that distinction explicit:

- [Arrival dispatcher](../src/rocell/application/arrival_wizard_service.py)
  has separate gated branches for original probe and settings capture. Its
  remaining generic acquisition branch still rejects unimplemented paths with
  `PHYSICAL_CAMERA_RELEASE_HELD`; stage-6 freshness is not the settings capture.
- [Owned native camera runner](../src/rocell/providers/windows/owned_native_camera_runner.py)
  retains the historical v1 incapable-only contract. Current probe/settings
  capture use the separate v2 activation supervisor; the old runner's hold is
  not evidence that those new branches are absent.
- [Action catalog](../src/rocell/application/wizard_actions.py) registers
  `arm_connect` as unavailable. `plan_task` and `simulate_task` do not execute
  physical keypresses or screen taps.
- [Owned arm runner](../src/rocell/providers/windows/owned_arm_feedback_runner.py)
  holds physical activation, and the
  [native serial API](../src/rocell/providers/windows/nonpurging_serial_api.py)
  holds before loading its native library.
- [Native companion validation](../src/rocell/providers/windows/arm_nonpurging_adapter.py)
  currently requires the physical hold and zero actual-effect counts. Removing
  a single guard would neither complete this contract nor safely enable COM.

Implement a separately reviewed physical composition with exact originals,
runtime identity, owned dispatch, bounded effects and cleanup evidence. Preserve
the existing incapable/rehearsal semantics and their historical evidence.
Do not introduce an "allow hardware" switch that bypasses these requirements.

## Next code milestones, in dependency order

1. **Verify complete identity-to-acquisition composition.** Follow the
   [full-history work order](CAMERA_FULL_HISTORY_INTEGRATION_WORKORDER.md), joining
   the existing original stage-5 entry/preparation and public probe/settings
   actions. Verify reachable same-store restart, current metadata ownership,
   unchanged predecessor records and existing history/timing limits.
2. **Complete camera qualification and calibration.** Add policy-derived
   settings/readback assessment and separate review, then freshness, optics and
   measured placemat registration. Use the existing capture/publication pipeline;
   a successful still image or diagnostic export does not pass these stages.
3. **Deliver the arm application path.** Add original stage-9 identity
   [submission/assessment/review](ARM_IDENTITY_ONBOARDING_WORKORDER.md),
   followed by stages 10–12 power/startup/feedback
   admission. Metadata correlation alone must not create an executable
   controller binding. Keep motion/contact as later, separate authority.
4. **Complete handoff and returning setup.** Connect installed calibration and
   noncontact evidence, configuration comparison/remediation, full handoff and
   clean-host packaging. Reopening logs or loading prior configuration is not
   permission to replay a hardware operation.

## What constitutes completion

### Received-camera metadata checkpoint — 2026-09-12 UTC

The [metadata-only runtime successor](CAMERA_METADATA_SUCCESSOR_WORKORDER.md)
repairs the drifted native-helper registration path using a separate guarded
build and closed 17-file catalog. Historical runtimes, catalogs and exports are
preserved. Four native test groups and 615 selected Python regressions passed.

Actual wizard-backend inventory/identity actions now match the received B0477
Media Foundation endpoint to its generic USB instance/container and retain
driver/parent-chain metadata. The full result and exact observations are in the
[pre-build playbook](PREBUILD_OPERABILITY_PLAYBOOK.md). This was real metadata
acquisition, with zero source activations or frame/control/arm operations; it was
not a live browser preview or full-history commissioning run.

Persistent binding remains `REVIEW_HELD` because the generic camera-function
record has no unit serial/persistent selector. Parent-instance text is not
substituted for qualified serial evidence. Negotiated USB speed, received-unit
qualification, camera activation and every calibration/arm stage remain separate.
This checkpoint does not close the dependency-ordered milestones above.

### Acceptance requirements

For each path above, require a public service-backed UI sequence, actual original
retention and exact review, negative/fault/Stop tests, complete assigned-folder
exports, fresh reopening without replay, and a production adapter that can act
when its independently verified prerequisites are satisfied. Hardware-free
tests must use labeled modeled observations without changing production timing
or qualification rules. Received-unit validation remains explicitly separate.

Current reconnect acceptance is tracked in the
[reconnect implementation record](USB_AFTER_RECONNECT_IMPLEMENTATION.md).
The broad onboarding goal remains open: passing that increment does not close
the camera, arm, calibration or handoff rows in this matrix.

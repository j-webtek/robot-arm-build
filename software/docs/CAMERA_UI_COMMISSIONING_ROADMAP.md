# Camera and UI commissioning: upcoming implementation plan

Date: 2026-09-13. Status: **M1 in progress; the roadmap is not complete**.

## Current execution status

| Milestone | Current state | Next completion evidence |
| --- | --- | --- |
| M1 durable camera originals | Contract, original reader/writer, public save, restart route and UI implemented under acceptance testing | Checkpoint-08 selected regression passed 601 cases. The later single-walk read revision passed checkpoint-09 storage (147) and public smoke (9); its fresh full-history lane is running. Full-workflow/latency acceptance remains open, with unchanged deadlines. |
| M2 USB continuity and close/reopen | Pure lifecycle comparison implemented; frozen checkpoint-08 smoke passed 34 cases (28 lifecycle, 6 export faults); no new action enabled | Exact original boundary/clock joins, versioned persistence, tests and UI. |
| M3 separate review | Open | Independently executed original-bound review and invalidation, not automatic approval after saving. |
| M4 frame freshness | Open | Bounded sequence/stimulus contracts, original timing evidence, fault tests and stage-6 UI. |
| M5 integrated acceptance | Incremental tests and browser inspections underway; milestone open | Entire M1–M4 sequence, full exports/restart/fault coverage and measured responsiveness on fixed inputs. |
| M6 received-camera checkpoint | Future operator-confirmed hardware procedure | Required software gates and fresh confirmation; no physical operation is authorized by this roadmap execution. |
| S1 static task simulation | Explicit static semantics and matching nominal target catalog added; 75-test live-tree compatibility selection passed, not a migrated simulator | Coherent static context/bundle, exact build geometry, CLI/UI selection and keyboard/phone feasibility diagnostics remain open. |
| H1 installed passive vision | Requires installed measurements | Support/coverage, intrinsics and camera-to-board registration; bench focus is not installed geometry. |
| H2 robot/contact handoff | Depends on H1, S1 and the separately commissioned arm | Robot-frame correlation, reviewed noncontact tests and eventual contact acceptance. |

The implementation evidence below is a checkpoint history. Counts from different
revisions are not added together as one release; modeled tests never become
received-unit qualification. The independently progressing arm implementation is
preserved, not superseded by this camera/UI work.

## Implementation checkpoints

Execution detail: [durable-evidence work order](CAMERA_DURABLE_EVIDENCE_WORKORDER.md).
The stage-ownership UI projection and capture-time reference candidate are
implemented. Durable original retention, restart reconstruction and the later
milestone gates remain open; launch diagnostics are not promoted to originals.
The foundation's fixed-input selected regression passed **866 tests**, with no
failures/errors/skips and unchanged inputs/source; see the
[implementation evidence](../runs/wizard-exports/camera-durable-evidence-20260913-01/README.md).
It is not the full-history acceptance lane or completed M1 durability acceptance.

A subsequent [backend increment](../runs/wizard-exports/camera-durable-evidence-20260913-02/README.md)
adds the pre-seal checksum reader and original-store/accounting contracts. Actual
NTFS tests exercise reopen and corruption, with modeled native predecessors.
Its frozen 20-module compatibility batch passed **384 tests** with unchanged
source/inputs; this remains a separate selection, not full acceptance.
A [producer integration](../runs/wizard-exports/camera-durable-evidence-20260913-03/README.md)
now supports that contract inside the consumed campaign and capacity checks.
Its real-file/M1 producer development batch passed 55 tests; the frozen 15-module
compatibility batch passed **268 tests** with unchanged source/inputs and no
failures/errors/skips. At that checkpoint, public admission/ingestion/readback
joins had not migrated.

The [active integration checkpoint](../runs/wizard-exports/camera-durable-evidence-20260913-04/README.md)
now implements those joins and the original/legacy diagnostic UI projection.
Development file/UI tests passed 81 cases; a later distinct checksum/metadata
selection passed 102. Integration exposed a v2 deadline-routing gap, a test
producer's optional-stride assumption, and repeated-history timing holds under
load. After corrections, both full-size actual-store service/reopening cases
passed with modeled setup/native producers. The public wizard now selects v2 in
source and public composition tests are running. None of these development
batches completes M1 or the fixed-input public acceptance gate.

The checkpoint-04 fixed run finished 325 passed and 6 failed (331 tests), with
unchanged source/inputs; it is not accepted. Later development is tracked in
the [original submission work order](CAMERA_OPERATING_SUBMISSION_WORKORDER.md):
the compound proposal/assessment codec passed 61 cases and the complete-snapshot
v17 layout passed 18 modeled cases. The narrow original-store guard passed 5
actual-NTFS tests, with modeled predecessors. The later legacy-receipt and layout
compatibility selections passed 33 and 91 cases respectively. A separate frozen
six-case nominal recovery run passed all 6 tests in 673.30 seconds, with unchanged
source/inputs. Full-prefix/native submission reader
routing is implemented. Later development adds native/store/service integration
(29 cases passed), a one-use public save-for-review action, flat diagnostic
exports and browser/terminal status (61 public/UI cases passed with modeled
backend/adoption seams). Fixed-input complete-history public save, reopen/export
and latency acceptance remain open. No count from these separate revisions
constitutes a complete M1 release.

The next [complete-history acceptance lane](../runs/wizard-exports/camera-durable-evidence-20260913-07/README.md)
now has a separate public two-capture save/reopen/export test. It failed at the
earlier probe's admission deadline, before the new submission, with unchanged
source/inputs; it is not accepted. Checkpoint 06 exposed a test-snapshot omission: required
camera/source documentation was excluded, so original-reader fixtures rejected
the incomplete source closure. The next snapshot retains all declared inputs;
no original validator, timeout or quota is bypassed. A separate real-browser
rehearsal inspection verified the empty/held submission card and form, not an
eligible hardware flow or full-history acceptance. The checkpoint-08 work tracks
the selected-regression recovery and preliminary M2 comparison separately.

Scope: finish the camera's original-evidence, review and onboarding workflow,
integrate it into the existing UI, and prepare the static-camera task path for
the assembled placemat. Preserve the independently progressing arm work.

This document records the next implementation sequence. It does not open a
camera, query USB, change settings, authorize arm power/motion, modify the
controlled build, or approve calibration. Hardware checkpoints require fresh
operator confirmation and the existing eligible, reviewed application actions.

## 1. Target outcome

The operator should be able to open the application, understand which camera
and setup are selected, follow the next eligible step, inspect the resulting
image and evidence, resolve a clearly explained blocker, and export a complete
diagnostic package to the assigned workspace folder.

The application must distinguish five different claims:

1. The local UI can reach its software service.
2. Windows metadata identifies a candidate device.
3. An explicit camera operation completed with verified output and cleanup.
4. A particular commissioning stage has sufficient original evidence and a
   separate recorded review.
5. The installed cell is calibrated and separately permitted to execute a task.

None of these automatically implies the next. Saved images and passing software
tests must not be presented as a currently connected or motion-ready robot.

## 2. Baseline we are building on

- The Camera page, Control Center, Activity and Diagnostics already expose
  existing service-owned actions, previews, results and exports.
- The camera software includes original-bound probe/settings/capture pathways,
  retained still-image publication, a draft operating-mode proposal, and an
  original-evidence diagnostic assessment.
- The newest assessment checks selected saved YUY2 files against earlier
  retained launch-completion checksums. It shows missing, mismatched and changed
  files without repair or recapture. The reference is not yet a separately
  authenticated, restartable canonical stage record.
- The latest selected camera/UI regression passed **601 tests** with unchanged
  copied inputs. This is layered, no-device regression, not physical acceptance.
- A separate frozen nominal full-history camera capture/export/reopen test
  passed on September 12. It used modeled hardware/native producers. It does not
  accept later source changes, growing-history performance, or the new stage
  records proposed here. Earlier failures remain historical evidence.
- The purchased camera is represented by the B0477/16 mm profile and selected
  static-overhead architecture. The bench's approximately 10-inch focus distance
  is not an installed mounting height. The recorded 8 fps observation remains
  distinct from the profile's 9 fps reference mode.
- The default task simulation still has a documented legacy eye-on-arm
  dependency graph and provisional IK gaps. Static-camera onboarding alone
  does not migrate that simulator or prove keyboard/phone path feasibility.

Evidence: [pixel-assessment handoff](../runs/wizard-exports/camera-pixel-assessment-20260913-01/README.md),
[isolated acceptance](CAMERA_ISOLATED_ACCEPTANCE_WORKORDER.md),
[UI handoff](UI_APPLICATION_HANDOFF.md), and
[static-task migration work order](STATIC_TASK_SIMULATION_MIGRATION_WORKORDER.md).
Do not add counts from different checkpoints and call them one tested release.

## 3. Delivery order and dependencies

These milestone IDs are planning labels, not new commissioning stage IDs.
Use the existing canonical stage order and catalog; do not create a competing
state machine or assume a design catalog revision is already active at runtime.

| Milestone | Deliverable | Depends on | Hardware needed to implement? |
| --- | --- | --- | --- |
| M1 | Durable proposal, capture-reference and assessment contracts | Current diagnostic assessment | No |
| M2 | Original-bound USB continuity and ordered close/reopen evidence | M1 binding design | No; real observations validated in M6 |
| M3 | Separate mode/control review, invalidation and guided UI | M1 + M2 | No; a modeled pass is not physical approval |
| M4 | Bounded frame-freshness campaign and stage-6 UI | M3 stage boundary; native campaign contracts | No; real timing validated in M6 |
| M5 | Integrated restart/export/fault acceptance and measured UI performance | M1–M4 | No |
| M6 | Received-camera-only wizard qualification | Relevant M5 software gates and operator confirmation | Camera, no assembled arm required |
| S1 | Coherent static-camera task simulation and IK diagnostics | Explicit static contracts and controlled geometry | No; independent software track |
| H1 | Installed optics, intrinsics and passive camera-to-board registration | Completed support/placemat and qualified camera path | Completed passive camera/board build |
| H2 | Robot-frame, noncontact and eventual contact handoff | H1 + separately qualified arm path + S1 | Assembled and independently commissioned arm |

Start with M1. Build tests and UI projections alongside each backend increment;
do not postpone all UI work until M5. S1 can be prepared independently, but any
changes to shared source must use their own fixed-input test snapshot. This plan
does not start another arm implementation workstream.

### Commissioning ownership decision required before M1 implementation

Map every current diagnostic hold to its existing stage owner. In particular:

- Stage 5, `camera_mode_controls`: original mode/control evidence and review.
- Stage 6, `camera_frame_freshness`: freshness qualification, separately owned.
- Stages 7–8, `optics_intrinsics` and `static_registration`: installed optics
  and passive camera-to-board observations.
- Stages 9–12: arm identity, power/startup and feedback.
- Stage 13, `reference_frame_calibration`: robot/board and controller correlation.
- Stages 14–15: noncontact acceptance and physical handoff.

The current diagnostic checklist combines stage-local and later prerequisites.
Do not require stage 7 or 13 evidence to enter an earlier passive stage, and do
not remove those later holds to make a stage-5 result green. Before defining a
review verdict, document exactly which stage it can satisfy. A mode/control
review must never claim whole-camera calibration or whole-cell operating
authority. Any necessary catalog/runtime migration needs explicit versioned
contracts and tests, not a renamed UI label.

## 4. M1 — Durable evidence and restartable references

### Implementation

1. Define closed, bounded, versioned original record contracts for the proposal,
   capture checksum reference, assessment and eventual review reference. Exact
   schema names and storage labels are design outputs, not existing APIs.
2. Bind records to the cell/session, stage entry, source/build identity, camera
   selection, native runtime, purchase-profile digest, selected mode, settings
   epoch, explicit capture attempts, native evidence and pixel hashes. Preserve
   rational frame rates, units and exact original bytes.
3. Create a durable checksum reference from the verified original capture flow
   while its owned bytes/result are available. For old launch-only references,
   either independently authenticate the retained original completion chain
   through a reviewed migration or keep them diagnostic-only. Never hash today's
   file and call that its historical capture checksum. Exported JSON is not an
   import or promotion route.
4. Extend the existing M1 persistence and exact original readers. Preserve
   append-only history, expected journal-head checks, ownership, quotas, current
   source checks and the original deadline. Assessments must name their exact
   input set; there is no implicit latest/best capture selection.
5. Retain and independently read back the new records before publishing a
   success. Handle interrupted/partial writes using the existing durability and
   uncertainty rules. Never roll back evidence or automatically replay an action.
6. On a fresh launch, reconstruct historical records from originals. Current
   eligibility still requires revalidation. Reopening does not connect a device,
   restore an old action ticket or authorize another capture.

### UI and export

Show a clear distinction between a draft, a saved diagnostic assessment, and a
verified original record. Display the selected capture references, provenance,
missing requirements and next action. Export the reference chain and original
record identities without duplicating full-resolution pixels unnecessarily.

### Completion gate

- Real original-store tests retain/read/reopen records without launch-memory
  substitution; old histories remain verifiable under their original semantics.
- Tests reject malformed/oversized records, altered hashes, wrong session/source,
  stale settings, duplicate captures, replaced paths and incompatible versions.
- Stop/deadline, crash points, disk-full/permission errors, conflicting owners,
  failed logging and partial retention preserve an explicit non-success result.
- Fresh launch and export verification work; no new device effects occur.
- Review/approval is still unavailable until M2–M3 requirements are satisfied.

## 5. M2 — Connection continuity and proven close/reopen order

### Implementation

1. Inventory the already retained generic/native USB, endpoint and activation
   records. Define the exact evidence join before adding any new collector.
2. Separate port/endpoint identity, selected-unit identity and negotiated USB
   speed. A USB 3-capable product or connector does not prove negotiated speed.
   Missing unit serial or unavailable speed remains unknown. Any alternative
   identity policy requires separate review; do not silently use a friendly name,
   first camera index, or parent-instance text as a qualified unit serial.
3. Bind before/after observations to the same intended unit, context, settings
   and attempt chain. Changed mapping, duplicate candidates or an unexplained
   identity change must block continuity, not cause automatic selection.
4. Prove order from original operation/cleanup records: first admitted capture,
   confirmed release, separately admitted reopening and later capture/readback.
   Two matching images or two distinct attempt IDs alone do not prove this order.
5. Distinguish application reopening, camera source close/reopen, cable reconnect
   and host reboot. Each evidence type has its own meaning. Cross-launch ordering
   cannot be inferred by comparing unrelated monotonic timestamps.
6. Add a narrow native observation only where existing records cannot supply a
   required fact. Use the existing owned, bounded provider lifecycle and disclosed
   effect category; do not add an unreviewed broad USB scan or reconnect loop.

### UI and completion gate

Show each continuity fact and its source, or a precise unknown/mismatch reason.
Keep any physical disconnect/reconnect action operator-paced. Test swapped
cameras, re-enumeration, missing/duplicate identity, slower or unknown bus speed,
out-of-order records, unconfirmed cleanup and changed settings. A qualifying
mode/control assessment must authenticate this evidence from originals; a pair
of fictional reports may exercise the UI but cannot qualify hardware.

## 6. M3 — Separate review and guided camera status

### Implementation

1. Add a distinct reviewed action for the exact retained mode/control assessment.
   The assessor must not invoke its own approval automatically. A separate review
   transaction is required; it need not invent a requirement for a second person.
2. The preview identifies the original assessment and input hashes, evidence
   outcomes, remaining later-stage holds, reviewer and decision/rationale fields.
3. The 8 fps variance must be visible and explicitly justified. Preserve the
   frozen purchase profile and 9 fps reference. No silent mode fallback, profile
   rewriting or acceptance of a missing control readback is permitted.
4. Re-read exact subjects at execution; reject a stale preview or changed owner,
   source, settings, runtime or evidence. Retain and independently read back the
   review before publishing the relevant stage outcome.
5. Define invalidation edges for camera/settings/runtime changes now, and support,
   lens, focus/iris, crop, geometry and calibration changes in later stages. Keep
   historical results inspectable while withholding affected current eligibility.

### UI

- Reuse service-owned action forms, one-use preview/execute tickets, Activity
  and Diagnostics. Do not create a second frontend command catalog.
- Show stage-local outcomes, overall readiness and deferred installed checks
  separately; avoid an overall percentage that implies readiness for motion.
- Provide a next eligible action or specific blocking prerequisite.
- Preserve entered non-sensitive form drafts only under the existing rules;
  browser refresh must not replay a review or hardware action.
- Loading a checklist is read-only and labeled historical; service availability
  remains visibly separate from camera connection and frame age.

### Completion gate

Test approve/reject/hold paths, duplicate submission, stale evidence, late Stop,
deadline/logging failure, fresh launch, exact review readback and downstream
invalidation. Use actual JavaScript tests plus a non-operating browser walkthrough.
Every UI verdict must be explained by the corresponding service/original record.

## 7. M4 — Frame freshness and bounded observation quality

### Implementation

1. Reuse the native capture owner and existing stage-6 requirements. Define the
   campaign contract before dispatch: mode, settings epoch, frame/time/byte limits,
   startup-discard policy if supported, output roster and cleanup obligations.
2. Capture a finite sequence. Retain host sequence/arrival times and available
   device/sample timestamps with their clock domains and limitations. A sample
   timestamp must not be labeled an exposure timestamp without evidence.
3. Exercise observable changes with a controlled visual stimulus during later
   bench testing. Equal pixels in a static scene do not prove replay; different
   pixels alone do not prove acceptable end-to-end latency.
4. Report supported measurements separately: interval/jitter, stalled delivery,
   sequence anomalies, dropped frames where observable, stimulus delay, exposure
   readback and cleanup. Unknown or unmeasurable facts stay explicit.
5. Select thresholds from the existing task/accuracy policy, or document and
   review a versioned policy before judging results. Do not invent a convenient
   FPS, latency or timeout threshold to make a run pass.
6. Bind the assessment/review to original sequence data and invalidate it when
   its relevant settings, runtime or device context changes. Keep this separate
   from optics, geometry and motion qualification.

### UI and completion gate

Use bounded progress with measured counts and a truthful last-observation age,
not a fabricated completion percentage or an unbounded live feed. Explain what
Stop requests and what cleanup is actually confirmed. Test repeats, static scenes,
stalls, delayed/out-of-order observations, clock resets, truncation, frame-budget
overflow, Stop and uncertain cleanup. Include full-size synthetic files under
production byte limits; tiny fixtures alone do not establish throughput.

## 8. M5 — Integrated acceptance, exports and responsiveness

1. Run the public wizard/backend sequence on fixed inputs: original predecessors,
   preparation/review, probe, settings/captures, proposal, assessment, separate
   review, freshness, exports, close, fresh launch and original reconstruction.
   Preserve the existing nominal full-history lane; explicitly extend or add a
   named lane rather than relabeling selected unit tests as end-to-end acceptance.
2. Test normal and failed probe exports, exact capture-attempt exports,
   assessment/review/freshness attachments, and exports after generic result-card
   rotation. Verify manifests independently from the exporter.
3. Test empty, nominal and growing histories approaching documented quotas, plus
   maximum supported pixel/sequence sizes. Include representative shared-host
   load in a separately labeled performance run.
4. Measure phase times, source/original-validation cost, bytes read and memory.
   The earlier full-history pass included long public actions; success alone does
   not establish a responsive wizard. Define a measured performance budget before
   optimizing, preserve production safety deadlines and never cache past required
   currentness checks.
5. Keep polling inexpensive and non-operating. Show the current phase, elapsed
   time, cancellation request and final cleanup result. A slow original read must
   not look like a frozen page or induce repeated operator clicks.
6. Walk the real UI using explicitly fictional/incapable observations: keyboard
   navigation, clear labels, long errors/IDs, unavailable actions, stale results,
   draft behavior, export-folder failures and readable next-step guidance.

### Completion gate

Require passing executed test identities, no skips masked as acceptance, source
and input manifests unchanged before/after, verified exports, and explicit
modeled-versus-real boundaries. Document the exact covered history/size range and
runtime dependencies. Preserve rejected snapshots, failures and timing reports.
Do not relax ownership, file guards, quotas, assertions or deadlines to get green.

## 9. M6 — Received-camera-only checkpoint

This is a future hardware procedure, not authorization to run it now. The arm
need not be assembled or connected. Confirm its supply/isolation state afresh
where required; software cannot infer the state from an old conversation.

1. Explain the bounded test and get operator confirmation. Confirm other camera
   applications are closed and the camera/cable are stable. Do not ask to revisit
   deferred focus-distance work merely to repeat the earlier bench experiment.
2. Use the eligible wizard metadata path and explicitly select the intended unit.
   Review identity and speed facts. Stop on ambiguity or an unmet predecessor;
   never import simulated original records to bypass commissioning.
3. Inspect advertised modes/control capability, select a reviewed candidate and
   verify requested versus actual readback. Preserve the 8/9 fps distinction.
4. Run separately confirmed finite captures and the required close/reopen sequence.
   Assess original metadata/pixels and review the resulting mode/control evidence.
5. Perform the bounded freshness test with the agreed visible stimulus. Preserve
   failures without automatic recovery or a second camera substitution.
6. Export the session, verify the export, explicitly close, and demonstrate a
   fresh application launch that restores history without replaying operations.

Completion means a received-camera bench checkpoint through the actual wizard,
with original evidence and readable logs. It does not establish full-board
coverage, final focus/iris, installed intrinsics, arm calibration or typing.
If a prerequisite is unavailable, deliver the precise blocked checkpoint and
its export; do not promise that plugging in the camera alone makes it eligible.

## 10. S1 and H1 — Static simulation and installed vision

### S1: software preparation before the build is complete

Follow the existing static-task migration work order, reusing the current static
calibration graph and semantic compilers rather than creating another simulator.

- Add a coherent versioned static context/bundle, semantic profiles and required
  calibration closure; keep legacy bundles and reports explicitly historical.
- Load board/device/tag coordinates from the controlled build sources. Test exact
  unchanged geometry and URDF identity. Distinguish nominal/synthetic key centers
  from surveyed key positions and the measured Android screen map.
- Preserve separate camera, board, vendor-world and controller frames. A passive
  camera-to-board solve does not establish robot-world registration.
- Simulate all-six-tag visibility, occlusion, stale observations, support/board/
  device displacement, settings drift and re-observation after retraction.
- Diagnose existing IK failures with pinned geometry, TCP, joint limits, seeds and
  FK residuals. Keep sampling distinct from continuous path/collision proof.
- Use the existing task UI and exports to show architecture, source versions,
  geometry provenance, feasibility failures and physical holds.

Completion is an honestly labeled static simulation route for both keyboard and
phone, with deterministic fault coverage and documented IK results. Unresolved
IK gaps remain blockers; moving nominal targets or loosening limits is not a fix.

### H1: installed passive camera/placemat commissioning

After the rigid support and board are assembled, measure the actual lens-to-plane
relationship, orientation, full usable coverage, tag positions, device seating,
support stability and cable clearance. The 10-inch bench focus observation and
nominal support screening dimensions must not become installed measurements.

Guide manual focus and iris at the installed height, then lock them and bind the
settings/mount witness to the dataset. Reuse intrinsic-calibration and static
registration modules. Solve pose from T0–T3 and validate K0/P0 independently;
include held-out images/points, edge coverage, glare and uncertainty checks.
Close numeric accuracy budgets from the smallest real targets and the full
error stack before accepting a calibration, not from an attractive reprojection
error alone. Changed optics/support/layout must invalidate affected artifacts.

Stages 7–8 stay passive with required actuator isolation. Do not require an
energized robot reference to perform camera-to-board registration, and do not
claim it supplies the later robot-world/controller transform.

## 11. H2 — Boundary with arm control and task execution

Coordinate through the existing arm work orders and current service contracts.
Re-audit that work at handoff; this camera plan does not freeze a potentially
stale statement about which separate arm diagnostic actions exist.

Before execution, require the independently qualified arm identity, power/startup
and feedback path, robot/board and controller correlation, TCP/tool/compliance
measurements, reviewed limits, occlusion/clearance routes, and noncontact tests.
Then validate controlled individual contacts and independent outcome observation:
keyboard input on the host and tapping outcomes on the Android device. Screen
orientation/layout changes and uncertain outcomes must not trigger blind repeats.

Semantic typing/tap plans are not arbitrary servo-command authority. General
Connect, task simulation and a saved successful camera result must not bypass
separate motion/contact gates. Actual typing/tapping is a later acceptance
milestone, not the completion criterion for this camera-only roadmap.

## 12. Implementation map

Paths below are existing reuse points, not an instruction to rewrite each file.
New schemas/modules/actions require explicit names and review in their own work
orders before implementation.

| Concern | Existing source area | Planned change |
| --- | --- | --- |
| Proposal and pure evidence checks | `application/camera_operating_proposal.py`, `camera_operating_evidence_preflight.py` | Reuse exact codecs/comparators; add reviewed stage-local contract boundaries |
| Original assessment and pixels | `application/camera_operating_original_assessment.py`, `camera_operating_pixels.py` | Join durable checksum/original references without replacing historical semantics |
| Original storage | `application/commissioning_camera_persistence.py`, `physical_camera_mode_entry_layout.py`, `physical_camera_mode_entry_readback.py` | Versioned retention, exact readback, review and restart integration |
| Owned native acquisition | `application/physical_camera_acquisition_service.py`, `providers/windows/` | Reuse bounded lifecycle; add only missing continuity/freshness observations |
| Wizard orchestration | `application/camera_operating_assessment_service.py`, `camera_operating_assessment_wizard.py`, `arrival_wizard_service.py`, `wizard_actions.py` | Reviewed actions, currentness and stage-local result publication |
| UI | `ui/static/app.js` and existing styles | Service-driven stage guidance, provenance, missing facts and invalidation |
| Static task path | `application/context.py`, `typing/development_profiles.py`, `simulation/bundle.py`, `workcell/alignment.py` | Coherent separately versioned static contract, no mixed legacy inputs |
| Installed calibration | `calibration/static_phase1_requirements.py`, `static_camera_intrinsics.py`, `application/static_phase1_calibration.py` | Reuse graph/calibration functions; qualify measured data through original onboarding |

All source areas above are relative to `software/src/rocell`.

## 13. Test, documentation and handoff rules

For every increment:

1. Write a bounded work order naming changed contracts, exact effects, owned
   files, compatibility behavior and observable acceptance criteria.
2. Add deterministic success/negative tests, then implement through existing
   owners. Use comments for provenance, ownership, frame/clock meaning and
   non-obvious safety/performance decisions.
3. Verify pure contracts, real file/original-store behavior, public service
   composition and actual UI rendering at distinct, honestly labeled levels.
4. Use a separately copied input tree for long/source-bound tests while the shared
   build changes. Never alter an active snapshot or substitute imported code.
5. Use a new result folder under
   `C:\Users\Jack\Desktop\robot-arm-build\software\runs\wizard-exports`.
   Export names must be unique; preserve prior evidence. Record exact test IDs,
   counts/duration, source/input identities, dependency scope, outcomes and limits.
6. Update this roadmap and the completion matrix with links to evidence. Do not
   mark a milestone complete because its UI exists or because tests with mocked
   predecessors pass. Include the next unresolved boundary.

### Immediate work package for the next implementation turn

- [x] Reconcile stage-local versus later holds with the canonical stage contract.
- [ ] Specify bounded M1 record schemas, exact bindings and legacy history behavior.
- [x] Specify and verify the internal pre-seal checksum creation point and reader;
      public original-admission/ingestion/assessment migration remains open.
- [ ] Add original-store tests for write/read/reopen, tampering, partial writes,
      late interruption and no restored hardware authority.
- [ ] Implement the smallest complete retention/readback slice and its UI/export
      projection; keep separate approval unavailable.
- [ ] Run fixed-input verification and record results before extending into M2.

No further hardware information is needed to begin this software work package.
Unknown physical facts must remain unknown until their scheduled checkpoints.

### Milestone ledger

| ID | Current status | Completion evidence required |
| --- | --- | --- |
| M1 | In progress: internal producer/storage verified; public v2 selection under test, original stage records still open | Durable original subjects, public exact readback/restart and fault tests |
| M2 | Planned | Authenticated identity/speed/order joins and negative tests |
| M3 | Planned | Separate stage-local review, invalidation and public UI/export tests |
| M4 | Planned | Bounded freshness contracts, assessment/review and fault coverage |
| M5 | Planned | Fixed-input integrated acceptance, full export matrix and measured performance |
| M6 | Awaiting software gates and operator confirmation | Actual camera-only wizard observations and verified export |
| S1 | Existing work order; migration remains open | Coherent static bundle/semantic graph and truthful feasibility evidence |
| H1 | Deferred until passive build is ready | Measured installed optical/registration evidence and independent checks |
| H2 | Later integration; separate arm ownership | Qualified transforms, noncontact and separately controlled task outcomes |

Saved as Markdown in the existing workspace. There is currently no Git repository
at this workspace root; this document is not a Git commit or a controlled-build
freeze promotion. The original planning document made no production changes.
Subsequent software work is tracked in the linked work order. No hardware state
changes have been made by this implementation increment.

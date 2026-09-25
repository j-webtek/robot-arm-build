# Retained noncontact readiness diagnostic — implementation brief

Date: 2026-09-08. Status: NC-01 implemented; the separately recorded
[feedback-window repair](FEEDBACK_SINGLE_WINDOW_IMPLEMENTATION.md) now verifies
the complete public software lifecycle on source d2acf827. The source-5b659910
failure below remains historical and preserved. Readiness remains BLOCKED;
physical acceptance, NC-02/03 and handoff are not complete.
Baseline source: `457e5a81058a053de122659d3cef3517e64e89326a54ea927de9e1c187d4a977`.

## Why this advances the application

The original onboarding goal includes camera/arm connection, calibration tests,
baselines and a controlled handoff to individual keystrokes and Android taps.
At this increment's start, the durable wizard supported thirteen rehearsal stages
but had no stage-14 gap report. Operator intake/export is implemented and tested;
it does not replace the remaining commissioning tests. This increment implements NC-01 from
[the audited noncontact plan](WIZARD_NONCONTACT_NEXT_SLICE.md), using its actual
existing collision-readiness and accuracy-budget APIs.

The full goal remains open. Do not call this physical noncontact acceptance or
claim that stage fifteen, physical connection, installed calibration or execution
is complete. Active Freeze011 and all physical release gates remain unchanged.

## Workflow and acceptance semantics

Use the existing original M1 rehearsal session and explicit collect → assess →
distinct-reviewer actions when `noncontact_acceptance` is due. Derive immutable
inputs only after rechecking the full original stage-13 receipt/assessment/review
and its camera, registration, feedback and independent synthetic-power dependencies.
No browser hashes, dimensions, paths, numerical policies or overrides are inputs.

Collection runs a closed no-device readiness diagnostic once. Retain complete
technical inputs and results before presenting a cached compact report. Assessment,
review and reopen verify original retained results; they must not repeat a solver,
plant, renderer, camera or hardware action. Source reads occur only at the existing
explicit guarded verification boundary, not in views or export.

Separate the actual outcome axes:

- Diagnostic invariant/fault cases can pass when the implementation correctly
  refuses missing or mismatched evidence.
- Nominal build collision/accuracy readiness remains BLOCKED / UNBOUNDED when
  installed geometry or measured terms are absent. Those failures must be inputs
  to the stage assessment, not hidden by successful software fault cases.
- Exact review of a blocked assessment records that blockage; it does not advance
  to a physical handoff, create a permit, mark intake complete or clear a hazard.

## Retained calculations

1. Run the actual source-bound historical collision-readiness audit. Retain its
   full contract, audit, pinned URDF evidence and explicit legacy eye-on-arm scope.
2. Inventory the separate static-camera contract's 26 body requirements and nine
   required source identities. Do not synthesize installed geometry from names
   or promote historical six-body AABB proxies into static-camera clearance.
   Complete static geometry and pose/sweep evaluation remain NOT_EVALUATED.
3. Load the actual strict accuracy policy. Run fixed typed missing/stale/domain/
   target-margin cases and a separately labelled finite synthetic control through
   the existing conservative calculator. Retain all inputs, term classifications,
   sums/margins and outputs, rather than storing literal expected PASS booleans.
4. Keep real-build terms UNMEASURED/UNBOUNDED and target safe geometry unqualified.
   The synthetic control is not a target-specific keyboard/phone acceptance test.
5. Explicitly report pose, route, sensitivity, visibility, dynamics and real motion
   as NOT_EVALUATED. NC-02/03 remain open; no optimizer, route campaign, overlay
   substitution or contact-aware route is dispatched by this increment.

## Ownership and limits

- Numeric contract/evaluator: new immutable noncontact binding/evidence modules,
  source-owned snapshots, pure retained verification and focused mathematical tests.
- Persistence: original stage-13 predecessor joins, stage-14 evidence association,
  assessment/review recomputation and original-store reopening, with no replay.
- Presentation: same browser/terminal, compact independent gap/fault-case summaries,
  complete retained details/export and explicit zero hardware authority.
- Main integration: shared service/actions, cancellation/source/log publication,
  actual original-store public workflow, package and final regression evidence.

Keep existing 128 KiB M1 outer JSON and ordinary export limits unchanged. Measure
complete successful/gap/fault envelopes before UI integration. If the selected
complete evidence cannot fit, stop and design a bounded artifact reader rather
than truncate evidence or increase global caps. All physical counters stay zero;
no actual camera/serial/native-metadata helper or actuator is invoked.

## Required checks

Exact predecessor/source/policy/geometry identities; stale or cross-session input;
full result tamper, dropped body or term, changed count/margin and unknown fields;
Stop/deadline/source drift and result/log failures; original unaccepted receipt
retention; no recomputation during assess/review/reopen; distinct reviewers; true
nominal BLOCKED outcome despite passing diagnostic controls; export bytes/hash
roundtrip; no global stage, power, camera, arm or typing authority promotion.

Record the final source, complete test command/results, exported original session
and remaining physical/NC-02/NC-03 work below when implementation is verified.

## Operator and developer workflow

Launch `.\start-rocell-wizard.ps1` from the workspace root. In Guided rehearsal,
continue the original reviewed session using explicit Discover/Open; do not
initialize a replacement to bypass stale source or a held stage. A source edit
requires a fresh source-bound rehearsal, not migration of old acceptance.

When stage 14 is due, collect once with an operator ID, inspect the gap report,
assess the retained evidence, and review the exact blocked assessment using a
different reviewer ID. Local typed IDs exercise the two-role process; they are
not authenticated accounts. Review records BLOCKED and leaves handoff PENDING.
Stop is a diagnostic cancellation request, not a hardware emergency stop.

Use Diagnostics & exports to save to the user's selected
`C:\Users\Jack\Desktop\robot-arm-build\software\runs\wizard-exports` folder.
The dedicated `attachment-noncontact-readiness.json` contains the complete
original receipt, including numerical inputs and results. After source/log/Stop
or context failure it remains historical and must not be called current evidence.
After restart, original-store verification restores retained results without
running the original numerical evaluators, camera campaign or serial campaign.

The reproducible developer walkthrough is
`software/scripts/wizard_noncontact_smoke.py --expected-source-sha256 <frozen-source>`
under the workspace venv. It creates one bounded incapable rehearsal store,
executes the first thirteen stages, then continues the same original store
through collection, assessment, blocked review and reopening across launches.
It verifies dedicated exports before/after nine notes evict generic full results.
Each action is attempted once; preserve the original store and exports on failure.
This is an actual public-service/M1 walkthrough, not browser-interaction testing.

## Code map

- [Numeric contract and retained representation](REHEARSAL_NONCONTACT_API.md).
- [Original-store reopening and predecessor audit](NONCONTACT_REOPEN_API.md).
- [Shared browser and terminal presentation](WIZARD_NONCONTACT_PRESENTATION.md).
- `application/commissioning_rehearsal_service.py`: collect, pure assessment,
  exact review and separate current/historical report caches.
- `application/arrival_wizard_service.py`: explicit action execution, logging,
  Stop/source/context publication boundaries and reserved diagnostic attachment.
- `tests/unit/test_wizard_noncontact_stage_integration.py`: actual calculations
  at a modeled transaction seam; not a substitute for the public M1 walkthrough.

No hardware profile, layout, active freeze, source-owned safety policy or physical
release gate is changed. The selected static camera remains a separate geometry
requirement; old eye-on-arm proxies are not promoted to installed static geometry.

## Original source-5b659910 verification checkpoint (historical)

Production fingerprint:
`5b6599106dfb2476e547f3b9aaeaf937fadcb6fb0d990390fe003df5a4523a8b`.
No production source edits occurred after the following original-store run began.

The seven-file focused integration selection passed **216 tests in 35.65 seconds**:

```text
.venv\Scripts\python.exe -m pytest software/tests/unit/test_rehearsal_noncontact_binding.py software/tests/unit/test_rehearsal_noncontact_stage.py software/tests/unit/test_noncontact_reopen.py software/tests/unit/test_arrival_wizard_noncontact_ui.py software/tests/unit/test_arrival_wizard_noncontact_publication.py software/tests/unit/test_wizard_noncontact_stage_integration.py software/tests/unit/test_wizard_noncontact_smoke.py -q
```

Those tests include actual source/calculator results, modeled transaction faults,
pure retained verification, both rendering adapters, public action/log publication
with modeled receipts, and actual temporary export roundtrips. They do not replace
the separate original-store walkthrough or qualify physical devices. A review
caught and fixed an adjacent camera-reopen invalidation nesting error; a dedicated
regression verifies the old acquisition intent is retired at explicit admission.

The broader frozen-source regression passed **2,467 tests**, with 4,536
deselected, in 1,476.93 seconds (24:36):

```text
.venv\Scripts\python.exe -m pytest software/tests/unit -m 'not slow' -k 'arrival or wizard or commissioning_rehearsal or noncontact or rehearsal_reference or reference_binding or physical_camera or physical_intake' -q
```

This is the named selection, not the entire repository suite. Some new
source-excluded publication/script tests were added after its collection; their
separate focused results are recorded above and below. Do not add overlapping
test counts. Black passed on the eight selected edited Python source/test files,
mypy passed on all six changed production Python modules, and Node syntax
validation passed for the browser application.

Both `start-rocell-wizard.ps1 -Check` and `-Mode physical -Check` passed, showed
no current noncontact report, authority false and the selected workspace export
folder. These checks opened neither a server socket nor a device.

The local wheel build with dependency installation disabled passed. Retained wheel:
`software/runs/wizard-package-check-5b659910/rocell-0.1.0-py3-none-any.whl`,
1,848,267 bytes, SHA-256
`bdf1277ce9355231512203d94b62b4606e5988090d8b749a410b58813a249552`.
All 254 packaged Python/HTML/CSS/JS entries match the current source byte-for-byte.
This is a development package check, not a qualified hardware installer.

### Actual public walkthrough: original failure preserved

The frozen-source walkthrough did **not** complete. Its original session is
`rehearsal-2209cd942ef14a71a0e48997c4245bfb`, stored at
`software/runs/wizard-rehearsal/wizard-fb32f71cdd6b407dad78c4e66525b517`.
Eleven rehearsal stages were reviewed PASS. The original stage-12 memory-only
feedback attempt `attempt-634ea628fcf840bc9104046ff4dcd68f` sealed
`SEALED_UNCERTAIN`, with quarantine latched and reason codes
`WORKER_OR_POST_ARM_PUBLICATION_FAILED` / `CommissioningCoordinatorError`.
Operation `operation-b770187c8b844ad49a1c9412d24619b8` finished FAILED at
13:18:57 UTC. Stage 12 remains WAITING_OPERATOR; stages 13–15 remain PENDING.
No NC-01 original-store receipt or successful complete stage-14 export was
produced by this run. The 216 focused tests must not be described as that proof.

No original action was retried, no quarantine was cleared, no source migration
occurred, and no replacement rehearsal was used to conceal the failure. The
original logs, M1 records, binary fixtures and earlier successful exports remain.
The returned failure reports zero actual device opens, serial writes, power,
motion and contact commands. Diagnosis is limited to retained evidence; a timing
or scheduling explanation is not established merely by the elapsed time.

The script exited after the failed action, so its complete in-memory operation
result was not exported before shutdown. The diagnostic event log preserves
its SHA-256 `95d0289361dbc4c2ed6a8571dde64c18de33d50def9cb62f49efe54cffadd922`,
not the full result bytes. This is an identified smoke-runner observability gap.
The complete original private M1 records still exist; they are not copied into
ordinary diagnostic exports.

The source-excluded smoke-runner gap was subsequently fixed without rerunning
that campaign: a known terminal failure now gets one same-live-service export
attempt before the original failure is raised. Export failure remains secondary;
an unknown running outcome prohibits further actions, including the legacy owned
wrapper's export path. The terminal failure and any export result are preserved
separately. This cannot recover the earlier lost in-memory result retroactively.
The updated two-file script regression passed **32 tests in 2.02 seconds**,
including a real temporary exporter roundtrip of a modeled fault result:

```text
.venv\Scripts\python.exe -m pytest software/tests/unit/test_wizard_noncontact_smoke.py software/tests/unit/test_wizard_arm_smoke_failure_export.py -q
```

Final source-excluded script SHA-256 values:
`wizard_noncontact_smoke.py` =
`bc2b1a5235ca425e2f2aa33ab55ab7d045bb0f7da149cfcb014d1b2cd90b16f7`;
`wizard_arm_setup_rehearsal_smoke.py` =
`0802a9d5852326a7c0b70a1a8c304f1bdeff5a8697e1bb80c2f560c159732eb9`.
Production fingerprint and the already-built wheel remain unchanged.

An explicit post-exit **historical event-log-only** export was independently
verified in the selected folder:
[wizard-20260908T132201918649Z-742414f38fef4150912ff349e1c643ed](../runs/wizard-exports/wizard-20260908T132201918649Z-742414f38fef4150912ff349e1c643ed/README.md).
Its manifest binding is
`0337d34defc0600e0f4cbc340235d80f4d3ed0c07b9434d4e36224e04811037a`;
the three payload files total 9,572 bytes. It explicitly discloses that it is
neither a current UI snapshot nor a full failed-operation/readiness report.

The [incident and repair plan](NONCONTACT_FEEDBACK_INCIDENT.md) records the
original evidence and timing inference. The strongest supported diagnosis is
loss of the full campaign budget during durable arming in the legacy memory
lane's separate lease cycles; the exact discarded exception is not recoverable.
The proposed repair reuses the existing single-lease adapter without relaxing
fresh checks or the original deadlines. It has not been implemented by NC-01.

That next step is now complete in the
[separate feedback repair and new-source lifecycle record](FEEDBACK_SINGLE_WINDOW_IMPLEMENTATION.md).
The new source's public walkthrough verifies thirteen PASS, stage fourteen BLOCKED
and handoff PENDING, including all five full-receipt exports and original-store
reopening. This does not relabel the original failed walkthrough as successful.
Do not extend a permit lifetime, change a clock, skip checks or release the old
quarantine to make this walkthrough pass. NC-02/03 and physical joins remain open.

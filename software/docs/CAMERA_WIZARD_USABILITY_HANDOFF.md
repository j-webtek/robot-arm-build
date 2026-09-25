# Camera wizard usability and early input validation

Date: 2026-09-10. This continues the camera/arm developer playbook; it does not
complete physical onboarding or change the hardware build. The full application
goal, calibration, arm startup/feedback, and later motion/contact gates remain.

## Operator-facing changes

The Camera page now presents next-step guidance, retained-image provenance and
current service state before the available action forms. Unavailable forms and
their exact hold reasons remain in a default-closed **Unavailable camera actions**
section. Metadata, original records and retained probe/settings attempts are in
**Detailed camera records & prerequisites**. All records are still rendered and
validated; collapsing a section does not remove evidence or qualify an action.

Both disclosures use native keyboard-accessible `details`/`summary` elements.
Their open/closed choices survive navigation and read-only refreshes. A focused
summary is restored when its tree is replaced. Queued toggle events from detached
pages cannot overwrite the current choice. These preferences are in-memory UI
state only, not source records, device selection, consent or an exported setting.

Forms require explicit boolean service eligibility and their existing local
intake requirements. Missing, null or truthy non-boolean eligibility cannot
enable controls or submit a preview. A permitted explicit submission still
requests a server ticket and waits for separate confirmation. No action registry,
provider, quota, timeout, hardware permission or automatic retry was added.

Older original-store setup actions require portable operator/reviewer IDs.
They now explain and validate the same existing rule at preview and execution:
1–64 ASCII letters/digits/underscore/hyphen/period, beginning with a letter or
digit. Spaces are rejected before ticketing, logging or store creation. Newer
camera-mode/probe display labels keep their distinct UTF-8 rule and allow spaces.

## Files and responsibilities

- `src/rocell/ui/static/app.js`: shared form eligibility, camera grouping and
  navigation-only disclosure state/focus preservation.
- `src/rocell/ui/static/app.css`: native disclosure layout and spacing.
- `src/rocell/application/wizard_actions.py`: shared portable-ID validation,
  early rejection and field guidance for the seven existing portable-ID actions.
- `src/rocell/application/physical_camera_setup_service.py`: calls that same
  portable-ID validator; accepted execution inputs are unchanged.
- `tests/unit/test_wizard_camera_disclosure_ui.py`: actual renderer in a finite
  DOM, including visibility, retained explanations, focus, stale events and
  zero-effect navigation; not a substitute for browser inspection.
- `tests/unit/test_wizard_setup_operator_input.py`: rule parity, existing accepted
  IDs, distinct newer labels, and public invalid-input rejection without writes.
- `tests/unit/test_arrival_camera_full_history_ntfs.py`: corrected synthetic
  refresh ID plus a cheap preflight before the slow original-history integration.

## Verification so far

Application fingerprint:

    70f10a3ec8306ca6c40b89b621f13848c579a17074849b236477e4ca13bde902

- New UI tests: **19 passed**, 2.44 s; report
  `.codex-preserved/camera-disclosure-20260910-01.xml`. The preceding red run
  detected the old layout/missing disclosures and preview-eligibility issues
  (18 failed, one passed); that report remains preserved separately.
- Input/runtime/protocol preflight: **72 passed, one slow test deselected**,
  2.30 s; `.codex-preserved/camera-onboarding-preflight-20260910-02.xml`.
  An earlier run had one incorrect test-only path accessor; it is preserved.
- Follow-up input audit also corrected the synthetic settings operator to its
  existing portable-ID format. Latest preflight: **73 passed, one slow test
  deselected**, 2.73 s;
  `.codex-preserved/camera-onboarding-preflight-20260910-03.xml`.
- Node syntax validation, Black checks on six touched Python files, and Mypy
  with `--check-untyped-defs --follow-imports=silent --ignore-missing-imports`
  on the two changed production Python files passed.
- Both rehearsal and physical `start-rocell-wizard.ps1 -Check` runs reported
  `READY_FOR_DIAGNOSTICS`, zero operations, both devices `NOT_CONNECTED`, no
  physical authority and the assigned workspace export folder. These checks
  do not enumerate/open devices or prove received-hardware compatibility.
- All 28 closed camera runtime files still match the copied runtime hashes from
  full-history run 01. No capable native executable was rebuilt or executed.
- Regression run 01's process handle was absent on continuation and no JUnit
  report existed. Its partial dot output is not acceptance. A fresh run 02 uses
  distinct basetemp/report paths; no original run or retained report is replaced.
- Regression run 02 is terminal: **1,578 passed, zero failures/errors/skips**,
  758.59 s (JUnit 758.505 s). It covers all 41 selected `*_ui.py` files plus
  action-catalog, Setup-service and public probe-preparation integration tests.
  Report: `.codex-preserved/camera-disclosure-regression-20260910-02.xml`;
  SHA-256 `dd7e52955bde29830df928141c619b56538e656fa99aa78fe1a007ac6dea5f3e`.
  Together with latest preflight this is **1,651 distinct passing test IDs**;
  the 19 new UI cases are already included, not added again. This is a selected
  regression suite, not the entire repository or physical acceptance.

### Actual browser review

Started the real PowerShell launcher in rehearsal mode and inspected the local
wizard in the in-app browser. Initially there were **six visible enabled camera
forms**, with **73 unavailable forms collapsed**. Opening the unavailable section
exposed all 73 disabled previews and the portable-ID help text. Navigation to Arm
and back preserved expansion; explicit status refresh preserved open/closed
choices. The detailed section still exposed original setup/prerequisite records.

Diagnostics showed zero events, no export, revision 0 and the assigned parent:

    C:\Users\Jack\Desktop\robot-arm-build\software\runs\wizard-exports

No form was previewed/submitted, no frame acquired, no inventory run, and no arm
port opened. The review tab was closed. The temporary server handle was no longer
present on continuation; its navigation-only diagnostic folder was absent.
Browser inspection used the computer-use skill's browser-first guidance; no OS
permissions, viewport, native UI settings or device configuration were changed.

### Actual browser action walkthrough and assigned-folder export

A separate real-launcher rehearsal session, `wizard-c574a60a8a5245a7be9835bf487fe058`,
executed the following through distinct Preview and Execute confirmations:

1. Software/geometry/dependency baseline.
2. A wrong-camera-identity rehearsal: the expected `WRONG_CAMERA_IDENTITY` hold
   was observed, not bypassed. Operation success here means the fault test
   behaved as expected; it does not mean the wrong camera connected.
3. A separate nominal camera rehearsal.
4. A nominal arm rehearsal.
5. A keyboard `hi` task simulation.
6. A phone `hi` task simulation.
7. Diagnostic export to the confirmed workspace parent.

The six worker operations completed using incapable/model providers. Their
result attachments report zero device opens, serial writes, power events,
motion commands and contact commands, and no physical authority. Both devices
remain `NOT_CONNECTED`; all 15 physical stages remain pending. The browser tab
and temporary launcher were explicitly closed after verification.

The unique, retained export is:

    software/runs/wizard-exports/wizard-20260910T194845352627Z-3a061d6cdec140f997a4b1b88899e5cc

Independent verification of its absolute path returned
`VERIFIED_DIAGNOSTIC_EXPORT`: nine indexed payloads, 370,464 bytes, source
fingerprint as above, rehearsal mode and physical authority `NONE`.
Manifest SHA-256:

    f1c4a5ff26b26ffa53a783ea29707f44608e5e0235d1bc22765e90d35aa7a0f3

The bundle contains six full worker results and 19 events. Its export operation
is queued in the snapshot because the snapshot precedes export completion.
The original diagnostic log independently verifies all 20 events, including
that final successful export completion; replay is forbidden. Log directory:

    software/runs/wizard-diagnostics/wizard-c574a60a8a5245a7be9835bf487fe058

Verified final log head SHA-256:

    e44517340fbed9966f35fd17e2899e499f39fe6b559b0a2d2c9a351f6d3e0164

#### Task simulation limitations found in the walkthrough

Both task reports explicitly return
`PASS_REQUIRED_SIMULATION_CHECKS_WITH_PROVISIONAL_IK_GAPS_AND_PHYSICAL_HOLDS`.
Required simulation checks pass, but the provisional inverse-kinematics samples
do **not** all converge. Keyboard: 2/8 converge; phone: 7/8 converge. The common
park point fails for both; several keyboard hover/approach/contact samples also
fail. These are sampled nominal-model results, not proof of unreachability or
permission to execute. Do not relax tolerances, bypass joint limits or change
the physical board layout just to make these results green.

The task plans also inherit the legacy `eye_on_arm_extrinsic` calibration
dependency from the development semantic profiles. This is inconsistent with
the selected static-primary camera architecture. The modern original camera
onboarding contract selects static-primary correctly; that does not silently
migrate the older task/qualification graph. A versioned, architecture-bound
task/calibration migration and clearer UI feasibility warnings are required.
Preserve these reports as historical evidence; do not rewrite them after a fix.

Implementation routing is in
`STATIC_TASK_SIMULATION_MIGRATION_WORKORDER.md`. Its renderer tests are prepared;
the expected red run has 33 failures and three passes against the unchanged UI.
No new task-result presentation is implemented yet. The portable-ID tests now
also specify early validation/help for the native-settings staging form, whose
existing executor still checks that rule late. That additional eight-case
coverage is prepared but not yet passing evidence. The 1,651-test result above
belongs to the earlier tested test/source checkpoint, not these new red cases.

## Still required

The full-history test's first execution failed before camera probing on the
now-corrected synthetic operator label. Its passing predecessor portions do not
prove the remaining probe/settings/capture/export composition. Re-run in a new
store after the selected regressions pass; do not load the failed store as a
fixture or change timing/admission rules to force a pass.

The next full-history run also reconstructs the exported settings-capture packet
and compares it with the exact retained attempt, then explicitly rereads the
post-capture original through the public action. It checks stable original
subjects, unchanged stage states and no active/stale storage lease owners.
These new assertions are requirements under test, not passing evidence yet.

Full-history run 02 was started at approximately 15:40 local time with six
preflights deselected and one slow test selected. It is now **terminal: one
failure, six deselected, 2152.85 s**. Its preserved paths are
`software/runs/pytest-camera-full-history-20260910-02` and
`.codex-preserved/camera-full-history-20260910-02.xml`. Source stayed at the
fingerprint above for the entire run.

At 16:07 local time, run 02 had completed the complete-series assessment/review
and reached the explicit public camera-mode entry action. It subsequently
reopened the original, collected fresh modeled metadata and completed probe
preparation/review. The public probe failed with `CAMERA_ATTEMPT_NOT_KNOWN`;
the retained supervisor identifies `ADMISSION_DEADLINE_EXPIRED` before release,
with uncertain accounting retained. Settings capture/export and final fresh
readback were not reached. See the full-history work order for details.

After termination, the task-result warnings and settings-input fix were
implemented and tested, with a new actual-browser export and full-resolution
pixel tests: `TASK_FEEDBACK_AND_FULLSIZE_CHECKPOINT.md`. Its source fingerprint
and evidence are separate from this earlier camera-disclosure checkpoint.

After that, continue maximum-history timing, policy-derived camera-mode/control
assessment and review, stage-6 freshness, installed optics/placemat registration,
original-bound RoArm startup/feedback, and the complete application handoff.
Physical qualification and physical keypress/tap permission remain unverified.

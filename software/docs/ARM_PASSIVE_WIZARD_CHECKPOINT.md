# Passive USB rehearsal: public wizard and diagnostic export

Date: 2026-09-12. Parent: [arm wizard implementation plan](ARM_WIZARD_IMPLEMENTATION_PLAN.md).

## Implemented outcome

The rehearsal-mode Arm page now offers **Rehearse passive USB connection**.
It follows the existing preview/confirm/action queue, executes a fixed incapable
child through the Windows process owner, and displays a compact retained result.
The terminal uses the same public service and result projection.

Update: the action also offers `lifecycle-nominal`, `lifecycle-open-failed` and
`lifecycle-cleanup-unknown`, which execute the actual serial lifecycle algorithm
with a memory-only Win32 provider inside the pinned child. See the
[lifecycle checkpoint](ARM_PASSIVE_LIFECYCLE_OBSERVATION.md) for package, test and
actual application export evidence. The smoke script now uses this stronger
rehearsal. The original `nominal` scenario remains an IPC-only fixture.

This is not a physical connection action. The child process is real; serial,
isolation, received-unit and startup observations are synthetic. Actual device
open/write/power/motion/contact counters remain zero. It is unavailable in
physical mode and does not satisfy original commissioning or power-safety gates.

## Flow and retention

1. Preview validates the registered scenario and current UI revision; no process
   starts at preview or on page refresh.
2. Explicit execution follows the existing diagnostic action-intent log.
3. The service creates one assigned per-operation child working directory and
   pins the fixed interpreter/fixture through the existing process owner.
4. The service checks source binding and finite remaining lifetime before child
   dispatch. Physical payloads and arbitrary commands/paths are not accepted.
5. The result retains the exact passive request, registered runtime inputs,
   bounded raw stdout/stderr, byte hashes, process result and passive summary.
6. The Arm card distinguishes process status, reported tree exit, completion-log
   confirmation and the separate passive outcome. Process success is not proof
   of device cleanup.
7. A dedicated retained diagnostic slot survives normal last-eight-result
   rotation. Only one passive rehearsal attempt is allowed per launch, so a
   second attempt cannot silently replace the first.
8. **Export logs** includes `attachment-passive-arm-rehearsal.json` through the
   existing assigned-folder exporter and verifier, including known failures.

The reserved in-memory slot is now also published as an immutable diagnostic
checkpoint in the assigned diagnostic root, named `<wizard-session>-passive.json`.
The existing durability primitive flushes, publishes without replacement and
reopens the bytes. The Arm card/export reports the checkpoint receipt. Publication
failure marks the operation FAILED while preserving its in-memory raw result for
export. This is not durable M1 original-attempt storage or stage acceptance.
No source/runtime hash turns synthetic references into observations.

Read-only historical inspection after shutdown is available with:

```powershell
.\.venv\Scripts\python.exe software/scripts/inspect_passive_arm_checkpoint.py "<checkpoint path from the Arm card>"
```

This reads one bounded regular file; it does not scan run folders, connect,
replay, repair, restore permissions or load the old result into a new wizard.
It rejects missing, truncated, oversized, renamed and checksum-mismatched files.
Checksums are corruption checks, not authentication against malicious rewriting.
The retained outcome may be FAILED or uncertain; successful file verification
never promotes that outcome. A crash before publication can still leave only
the diagnostic action intent; physical original-attempt recovery remains pending.
Export before closing is still recommended for the complete session context.

### Durable diagnostic checkpoint verification, 2026-09-12

- 248 selected tests passed in 26.20 seconds in
  `software/runs/pytest-passive-checkpoint-20260912-02`.
- Includes six real incapable-child scenarios, shutdown/readback, file damage,
  immutable publication, injected save failure with retained export, and wizard
  UI/terminal/process/codec regressions.
- Worker scratch directories now sit beside—not inside—the event-log session,
  preserving strict event-log verification. Historical folders were not modified.
- Actual application rehearsal/export passed for operation
  `operation-ec09c24b83d649dcb69ad94db3ec9550`.
- Export: `software/runs/wizard-exports/wizard-20260912T180050624069Z-6400f7006ef04c769145259e771bdccb`.
- Checkpoint: `software/runs/wizard-diagnostics/wizard-fd76a4ccce2a41cdaa0e2272f6d013b9-passive.json`.
- Source: `426eb8a21300dec278d0eaf3e48e62051ef2ec5bc4fa54e70f49969e67762e69`.
- No physical arm/camera access; all device observations remain synthetic.

## Verification

- Final selected suite: **239 passed in 23.93s**, under
  `software/runs/pytest-passive-arm-wizard-20260912-06`.
- Coverage includes all six public synthetic scenarios, inert preview,
  physical-mode refusal, one-attempt enforcement, raw-output hash preservation,
  verified export, result rotation, browser/terminal rendering, shared wizard
  behavior, owned process and request/result contracts.
- The new service module passed scoped Mypy.
- Earlier failures were retained: a test helper initially received a receipt
  instead of its operation ID; UI tests then exposed a real field omission due
  to misuse of the `facts` helper. Both were corrected before the final run.

Actual application smoke (not an injected service runner):

- Script: `software/scripts/wizard_passive_arm_rehearsal_smoke.py`.
- Operation: `operation-4f5cd409de054105850bc48f874164c5`.
- Source: `eb5d2604ea9e28432b8d800a861a24550655dfcc1f4479830f262eae1821f79e`.
- Outcome: `REHEARSAL_AND_EXPORT_VERIFIED`.
- Export: `software/runs/wizard-exports/wizard-20260912T175247856976Z-6ee803df4d874a12800038e37e431a26`.
- The export verifier passed. The actual attached arm and camera were not opened.

## Use

Start the wizard in rehearsal mode, open **Arm**, choose the passive rehearsal
scenario, preview it and confirm execution. Inspect the retained result card,
then use **Export logs**. To exercise the fixed nominal service/export path from
the workspace root without a browser:

```powershell
.\.venv\Scripts\python.exe software/scripts/wizard_passive_arm_rehearsal_smoke.py
```

That script creates a fresh rehearsal session and automatically exports its
successful nominal result. It stops on a failed/unknown outcome rather than
replaying. Its nominal smoke is not the interactive failure-recovery workflow.

## Next required work

### Pre-dispatch intent checkpoint, 2026-09-12

The service now persists `<wizard-session>-passive-intent.json` in the existing
diagnostic root **before dispatch**, after validating the prepared registration
and current source. The immutable, independently reopened record contains the
exact passive request, runtime registration and outer payload. A failed intent
publication aborts without starting a child. The later retained result embeds
that intent; ordinary exports therefore carry it without adding another export
attachment slot. This is rehearsal diagnostic storage, not physical admission.

Read one historical attempt after shutdown using:

```powershell
.\.venv\Scripts\python.exe software/scripts/inspect_passive_arm_attempt.py software/runs/wizard-diagnostics <wizard-session-id>
```

The inspector reads only the named intent and outcome. It does not scan the run
tree, create a session, repair files or restart a worker. It reports:

- `HISTORICAL_PAIR_VERIFIED`: exact request/runtime/source/operation/intent match;
  the contained observation may still have failed or reported uncertain cleanup.
- `OUTCOME_UNKNOWN_NO_REPLAY`: intent exists without a retained outcome.
- `OUTCOME_UNBOUND_NO_REPLAY`: an outcome exists but cannot be tied to that intent.
- Unreadable, malformed or checksum-damaged records fail inspection with exit 2.

No state grants replay, authentication, physical authority or current connection.
The matching-pair inspector exits zero only for file association, not device-test
success. Checksums detect corruption; they are not tamper-proof signatures.
Missing originals or power loss before publication remain unknown. Physical
original admission and qualified storage requirements remain unfinished.

Verification: **142 selected tests passed in 36.14 seconds** in
`software/runs/pytest-passive-intent-20260912-02`, including all public passive
scenarios, intent-write failure before dispatch, injected interruption after
intent, missing/damaged/unrelated outcomes and service/process regressions.

Actual application lifecycle rehearsal and verified export passed:

- Operation: `operation-c69a897d8b2c4c469f96e5661c766229`.
- Source: `a173e9aba203345921bb3b513700d40c3a79ced455b7cc2174082fdaff39dc2d`.
- Export: `software/runs/wizard-exports/wizard-20260912T182349268274Z-894a33b37b374d2b9bf1b4825b5128e7`.
- Post-shutdown read-only attempt inspection verified the historical pair.
- No actual arm/camera access or hardware commands occurred.

### Historical inspection now available in the wizard

On **Arm**, choose **Inspect saved passive arm attempt**, paste the exact
`wizard-` session ID from the original report, preview and confirm. This action
is available in either mode but only reads the named files in the configured
diagnostic folder. It accepts no filesystem path and performs no discovery scan,
device acquisition, repair, connection restoration or replay. Startup and page
refresh do not automatically read historical files.

The **Saved passive arm attempt** card and terminal show the same service-owned
summary: file-pair status, original operation/source, whether the source matches
this launch, original process/passive outcomes and integrity references.
Verification success means the historical files match—not that the original
test succeeded. A failed original test remains failed. A failed reinspection
replaces a previously verified display with an unverified state.

**Export logs** retains the inspection result and matched original raw process
bytes using the existing bounded result exporter. UI summaries omit raw bytes;
they remain in the operation's retained result/export. This does not republish
old results as a current passive attempt, alter original files or approve their
source. Ordinary result rotation still applies to history-inspection operations.

Regression: **189 selected tests passed in 30.87 seconds** in
`software/runs/pytest-passive-history-ui-20260912-02`, covering explicit restart
inspection, browser/terminal output, invalid IDs/paths, missing/damaged history,
failed original tests, changed source, export and existing wizard behavior.

An actual application-only inspection/export also passed for saved session
`wizard-7b5dc50f4bde46d7b7892349d7f7824c`. It correctly reported
`historical_source_matches_current: false`. Verified export:
`software/runs/wizard-exports/wizard-20260912T182900718715Z-40522582137b48088029c78850afaefa`.
Reproduce the read-only application smoke with:

```powershell
.\.venv\Scripts\python.exe software/scripts/wizard_passive_history_smoke.py <wizard-session-id>
```

No hardware access or new rehearsal occurred in this smoke. It stops on failed
or uncertain inspection/export without retry; the UI can export a failed
inspection explicitly. No physical commissioning milestone is completed here.

### Remaining physical integration work

- Implement original passive-attempt intent/outcome/raw-output storage and
  independent readback using the existing storage infrastructure.
- Authenticate entry references from actual original producers, including the
  electrical-isolation review; no checkbox/hash-only replacement.
- Define and qualify the capable passive lifecycle/runtime registration and
  fresh operator entry before opening any physical port.
- Continue genuine canonical stages and feedback, then completed-build camera,
  calibration, noncontact execution and controlled typing/tapping acceptance.

No milestone requiring physical evidence is marked complete by this rehearsal.

# Full-history camera onboarding integration

Status: implementation and verification in progress. This work continues
`CAMERA_CONFIGURATION_WIZARD_HANDOFF.md`; it does not replace the camera/arm
developer playbook or declare the complete application finished.

Latest successor: [P1 existing-root observation](STORAGE_EXISTING_ROOT_OBSERVATION_WORKORDER.md),
with 796 earlier distinct selected passing checks and a fresh mixed-history profile.
Full-history run 06 failed after successful probe/capture release on fixed source
`01440cf0…91eb9`: an omitted source alias in the partial-workspace test blocked
post-capture ingestion. The test-only correction passes its 46-case regression.
Run 07's test then passed in 2,242.325 s, including capture/export/final readback,
but the final source comparison failed: concurrent arm/UI edits changed the
checkout to `af19e6a3…7d615c`. Fixed-source acceptance remains open. The later
144-case restart/export/UI selection also passes, but is not combined with
earlier-source checks as one release. Preserve both the green test and its
source-drift limitation; coordinate or isolate source before another fresh run.

Previous successor: [P1 bounded-read buffers](CAMERA_BOUNDED_READ_BUFFER_WORKORDER.md),
with 681 selected passing checks, including expanded history profiling. Fresh full-history run 05 still
fails the complete startup deadline after 34:10; its exact failure, 940-span
trace and expanded fast-profiling work are retained in that successor.
The [earlier coherent-observation work order](CAMERA_COHERENT_OBSERVATION_WORKORDER.md)
retains the run-04 result:
On 2026-09-12, 417 targeted cases passed after removing one redundant camera
session observation. Fresh full-history run 04 **failed** after 2,346.00 s:
final release revalidation took 2.031 s and exceeded the unchanged admission
window. The exact attempt remains uncertain, quarantined and non-replayable.
Settings/capture/camera exports were not reached. The successor work order
records the fixed source, JUnit/checkpoint hashes, 940-span trace and next
profiling ticket. Runs 01–03 below remain preserved failures, not rebound inputs.

## Intended operator outcome

An operator can reopen an existing original onboarding store, collect and review
current camera metadata, prepare/review a bounded probe, probe the selected
camera, stage its reported settings, request one settings-verification frame,
and export the exact attempt from the same wizard. Neither restart nor a saved
report recreates live device ownership, consent, calibration or motion authority.

## Implementation sequence

1. Extend the existing real-NTFS four-phase USB acceptance fixture. Construct its
   entire predecessor in a new disposable store using the existing production
   writers; never import a saved acceptance store or transplant a modeled head.
2. Use public camera-mode entry and an actual new Arrival service to reopen the
   same store. Assert that the original records survive exactly, while current
   metadata, probe, image and settings references must be obtained again.
3. Collect generic/native metadata through real wizard tickets, logs and
   publication. The OS observations are incapable test peers, not real devices.
   Refresh the original setup explicitly after this new metadata invalidates
   its cached publication. Do not synthesize the publication receipt.
4. Copy only the closed reviewed camera-runtime file roster into the isolated
   workspace, before retaining originals. Verify the real installed bytes,
   manifest and pinned hashes with the production bounded software verifier.
   Do not execute, rebuild, repin or replace a capable native helper.
5. Drive public preparation/review, probe, settings, one-frame capture and exact
   attempt export. Keep original readers, current facts, capacity, NTFS leases,
   monotonic clocks, permit rules, native protocol validation, cleanup, result
   logging and image publication unchanged. Use an incapable native owner with
   independent synthetic metadata and tiny test pixels only at the process edge.
6. Check unchanged predecessor subjects, single-use tickets, retained reports,
   clean leases, log/export integrity and no arm connection or stage advancement.
   Record operation counts and timings instead of changing limits to fit a test.
7. Investigate any failed boundary. Preserve its new store, diagnostics and JUnit
   report; repair the actual cause before running again in another fresh store.

## Cheap checks before the slow original-history run

- Both copied runtime profiles pass their actual file verifier (26 files each).
- Synthetic USB-matched activation packets pass the actual native decoder;
  inconsistent independent metadata is rejected.
- No physical process, camera, serial, boot query or metadata API can start.
- Test collection and formatting succeed before constructing the slow prefix.

## Evidence and remaining boundaries

Every run uses a unique `software/runs/pytest-camera-full-history-*` directory
and `.codex-preserved/camera-full-history-*.xml` report. Existing stores and sealed
developer checkpoints are not inputs and are never overwritten. Exports remain
beneath the assigned test parent; the operator application's default remains
`software/runs/wizard-exports`.

The inherited predecessor models source identity in an isolated workspace,
received measurements, USB/boot facts and process peers. Early source/receipt
stages still use typed test construction. These facts must be stated alongside
any passing result: this is stronger software-composition evidence, not proof
of received hardware, actual OS metadata acquisition or a fully UI-created
history. The executing checkout fingerprint is recorded separately.

Maximum-history timing, policy-derived mode/control assessment, frame freshness,
optics/placemat registration, original-bound RoArm connection and later guarded
noncontact/contact workflows remain in the full application scope. A passing
nominal camera chain does not complete those requirements.

## Verification record — 2026-09-10

Implemented `tests/unit/test_arrival_camera_full_history_ntfs.py` and an optional
fresh-metadata test-peer factory in the existing reconnect fixture. The factory
selects fuller synthetic parent/driver observations before public collection;
it does not modify old retained receipts. Fixed that fixture's obsolete patch
of Arrival's removed `platform` import; Arrival uses process-local `sys.platform`.

Preflight run 03: **4 passed, zero failures/errors/skips**, JUnit time 2.036 s.
Both actual runtime-file reviews and both matching/mismatched native-protocol
cases are covered. Report:
`.codex-preserved/camera-full-history-preflight-20260910-03.xml`.
Earlier failed preflights remain preserved: run 01 found the obsolete import;
run 02 showed that the USB-only test peer's incomplete parent walk correctly
cannot authorize activation. Neither production validation nor limits changed.

Full-history run 01 was launched with:

```powershell
.\.venv\Scripts\python.exe -m pytest `
  software/tests/unit/test_arrival_camera_full_history_ntfs.py -v -m slow `
  --basetemp=software/runs/pytest-camera-full-history-20260910-01 `
  --junitxml=.codex-preserved/camera-full-history-20260910-01.xml
```

Run 01 is **terminal: one failure, four deselected, 2267.93 s**. It completed
the four-phase original USB sequence, review/export/reopen, camera-mode entry,
another fresh original reopening and current public metadata. It then failed
at `physical_camera_refresh`: the test's `MODELED refresh operator` contains
spaces, which the older portable-ID executor rejects (`CAMERA_SETUP_OPERATOR`).
No camera probe or settings capture was reached. Its entire new store,
checkpoints, diagnostic logs and JUnit are preserved; none is an input to a retry.
Do not reuse this command's basetemp/report paths for another execution.

That run's executing application fingerprint was:

    440d3f7a3adae328493e1cf48b8f3cca5e2415639f04ae083031730cc13f364e

The test now uses `MODELED-refresh-operator` and has a cheap input preflight.
The settings operator was also audited and corrected to its existing portable
format before retry. Post-capture acceptance now requires exact export packet
reconstruction, explicit fresh original readback and clean storage leases,
not only comparison of a cached Setup projection.
The underlying late-validation usability defect is also fixed: preview and
execution share the unchanged portable-ID rule, and the forms explain it. See
[camera wizard usability handoff](CAMERA_WIZARD_USABILITY_HANDOFF.md) for the
new source fingerprint and verification. No native binary, hardware-build file,
hardware admission condition, timing allowance or quota changed.

### Run 02: terminal admission deadline failure

Fresh run 02 terminated with **one failure, six deselected, 2152.85 s**.
Preserved original/test root:
`software/runs/pytest-camera-full-history-20260910-02`.
JUnit: `.codex-preserved/camera-full-history-20260910-02.xml`; SHA-256:

    244b1370c09eaa4c45825b4a30bf6e822988a069b6ba9e55fc024a078eed3e8f

Its production source remained
`70f10a3ec8306ca6c40b89b621f13848c579a17074849b236477e4ca13bde902`.
Complete USB history assessment/review, camera-mode entry, fresh-app original
reopening, current modeled metadata, refresh and probe preparation/review
completed. The public probe then failed with `CAMERA_ATTEMPT_NOT_KNOWN`.
No settings capture/export or final post-capture readback was reached.

The retained checkpoint's `original_probe.dispatch.transaction` has
`SEALED_UNCERTAIN`, `NATIVE_ACCOUNTING_UNAVAILABLE`, no automatic replay and
attempt `attempt-5ed9c505a32043c596de6c2cf0abaf0a`. The original result latches
quarantine. Its supervision record identifies `ADMISSION_DEADLINE_EXPIRED`,
`release_check_passed=false`, 232 READY bytes and 324 constructed release bytes.
Constructing release bytes is not delivery. Owner/process observations are
modeled; no actual hardware producer ran.

Supervisor duration was 5.359 s, with a later outer parent deadline. Fixed
budgets were admission 2000 ms, native 5000 ms, run 10000 ms and cleanup 2000 ms.
This localizes the failure to the final release-admission check. The report
does not time each callback, so the source-based cost analysis below is not
yet measured attribution of the whole delay.

The agent review found four full-family audits in one consumed-permit facts
callback chain: `_fresh_admission`, first original assertion, independent
capacity observation, then final original assertion. The implemented narrow fix
shares the first original assertion's freshly audited records with same-call
capacity arithmetic, while retaining the final full original audit. This
removes one redundant read, not any boundary or post-disk corruption check.
The public independent capacity observer must keep its own full audit.

Do not copy the configuration observer's larger optimization without addressing
the post-disk family-record-only mutation boundary: unchanged session snapshot
alone cannot prove those record bytes unchanged. Measure delegated audits in
incapable fixtures, preserve all final context/enrollment/lease checks, and
only retry full-history acceptance in a new store after focused tests pass.
Do not extend deadlines, replace clocks or suppress uncertain retention.

The change is limited to `application/camera_probe_admission.py` and
`application/camera_probe_capacity.py`. The independent observer still audits
its own complete family after validating the exact request and context. Nothing
is cached between callbacks, and the original reader is unchanged.

Focused verification is terminal: **60 passed**, no failures/errors/skips,
211.60 s (JUnit 211.564 s). Report
`.codex-preserved/probe-audit-reuse-20260910-01.xml`, SHA-256:

    7281fab00fa04176b15bc31ae2c1da892dbacffbd954fc491663243502f96c74

Twelve new real-storage cases check two callback audits, no cross-call cache,
exact byte-object reuse for same-call arithmetic, late context/source/lease/
enrollment/cancellation changes and new corruption in three record families
during disk observation. These fixtures explicitly model semantic admission;
they do not replace the full-history test. Black and selected production Mypy
checks passed. The redundant audit is removed, but a timing pass is **unproven**.
The next fresh full-history run will retain bounded test-only inclusive timings
around delegated real readers/admission checks, including on failure. This is
observation only; it must not replace checks, change their order or alter clocks.

The subsequent independent UI/input/full-resolution pixel work is verified in
`TASK_FEEDBACK_AND_FULLSIZE_CHECKPOINT.md`. It does not resolve or supersede this
failed integration result.

### Run 03: instrumented fresh acceptance — terminal failure

Reconciled on 2026-09-12: the previously launched run is terminal with **one
failure, no errors/skips**, JUnit time **2119.084 s**. The original JUnit remains
`.codex-preserved/camera-full-history-20260910-03.xml`, SHA-256
`635961bf7d77c44354e013978ca195329f45b090c1afd7a30c3ecba07804c16c`.
The launch notes below describe its original execution, not a current process.

The public probe again failed with `CAMERA_ATTEMPT_NOT_KNOWN`. Its retained
attempt `attempt-aaec44d9284d4fc8bd45ba868c449440` is `SEALED_UNCERTAIN`, with
`NATIVE_ACCOUNTING_UNAVAILABLE` and quarantine. Original supervision reports
`ADMISSION_DEADLINE_EXPIRED`, `release_check_passed=false`, and a 4.235-second
supervisor interval. No subsequent settings/capture acceptance was reached.
The owner/process facts remain explicitly modeled; this was not the received
camera. Constructed release bytes do not prove delivery or zero effects.

Read-only trace aggregation found 691 completed spans, no unfinished/dropped
spans and no observer errors. Eight `_fresh_admission` calls had an inclusive
maximum of 1.938 s; eighteen original-current-record reads had an inclusive
maximum of 0.469 s. These observations locate costs but overlap and must not be
added as exclusive latency or treated as a complete causal profile.

The [failure-diagnostics increment](CAMERA_ATTEMPT_FAILURE_DIAGNOSTICS_WORKORDER.md)
now addresses the misleading public error presentation. It does **not** resolve
this failed timing acceptance, relax deadlines or authorize replay. A later
performance fix still needs focused corruption/currentness tests and a fresh,
new-store full-history run. Preserve this store and all preceding records.

The timing preflight is terminal: **23 passed, one slow test deselected**,
no failures/errors/skips, JUnit 2.544 s. Its report is
`.codex-preserved/camera-admission-timing-preflight-20260910-02.xml`, SHA-256:

    91e076079f9bbaf6328e45b49b6f5dc56631e2a81c0a37ec6b35680118e31e52

`tests/unit/camera_admission_timing_trace.py` is test-only. The full-history
successor wraps exact M1 methods, original-context readers and the campaign's
actual runtime-verifier alias. It preserves arguments, returned objects and
raised exceptions, restores inherited method lookup, and labels worker-thread
observations with the explicit public action. The failure checkpoint includes
inclusive real-clock spans, unfinished observations and a 4,096-entry cap with
dropped/error counts. Nested durations overlap; do not sum them as exclusive
costs. The observer adds overhead and cannot turn a deadline failure into a pass.

Fresh run 03 was launched after these checks against application fingerprint:

    6d75261e39b8b62533fd73d35b477475a84ac3c79bbeb8ff8f573ddffe81bf98

Test-file SHA-256 at launch:

    042f7e0a27128c14a7740a4a1af128d6899e24db96588c67b7f048a31894af5a

```powershell
.\.venv\Scripts\python.exe -m pytest `
  software/tests/unit/test_arrival_camera_full_history_ntfs.py -v -m slow --tb=short `
  --basetemp=software/runs/pytest-camera-full-history-20260910-03 `
  --junitxml=.codex-preserved/camera-full-history-20260910-03.xml
```

These paths were absent before launch and are now owned by that one execution.
Do not rerun this command with the same paths. Production/configuration/native
files were kept fixed during that execution. Run 03's terminal failure is
recorded above; it is not accepted. No terminal result should be inferred from
a quiet test process or an intermediate file alone.

#### Read-only timing triage

After the terminal checkpoint is retained, summarize its timing observations:

```powershell
.\.venv\Scripts\python.exe software/scripts/summarize_camera_admission_trace.py `
  software/runs/pytest-camera-full-history-20260910-03/test_full_original_history_reo0/camera-full-history-checkpoint.json
```

This developer script reads at most 8 MiB, rejects malformed or duplicate JSON
fields, bounds entries to 4,096, and validates reported counters/timestamps.
Output goes to stdout only. It groups returned/raised/in-progress observations
by action and function, with inclusive completed totals and maxima. Dropped,
unfinished and observer-error counts remain explicit; incomplete observations
are never filled in. A missing trace, as in preserved run 02, returns a
diagnostic error rather than a fabricated empty/pass result.

The output is **not authenticated original evidence or export verification**.
Use the existing original/export readers separately. Even a complete trace
cannot establish admission success, explain all timing overhead, qualify
hardware, or authorize replay. Nothing executes an action or changes a file.

Selected script/observer tests: **49 passed**, no failures/errors/skips, 0.33 s
(JUnit 0.295 s), including the actual observer's snapshot contract and oversized
JSON integer rejection. Report
`.codex-preserved/camera-trace-summary-20260910-04.xml`, SHA-256:

    83de96a15c2565f88cea2a564c480fbb1b2f118905bba53694a3501d6f331e10

Black and selected script Mypy checks passed. Earlier reports remain retained.
Independent review found Python's integer-conversion `ValueError` was not
being normalized to a diagnostic error; this is now covered without changing
the interpreter's integer limit. No other actionable issues were reported.
These sub-second tests overlapped the earlier-history portion of run 03; this
is not an isolated host benchmark. The script and tests are outside production
source inputs; the running application fingerprint stayed `6d75261e...81bf98`.

### Live browser navigation review

A separate temporary rehearsal server was launched from the actual PowerShell
entry point on the fingerprint above. Overview, Camera, Arm, and Diagnostics &
exports were inspected in the in-app browser. No diagnostic was previewed or
executed. The next-step camera link focused/scrolled to the existing rehearsal
form without running it. The final UI showed event count 0, revision 0, no running
operation, disconnected devices, and the confirmed workspace export parent.
The temporary browser tab was closed and its own server interrupted; the
independent NTFS acceptance process was not interrupted.

This review exposed an application-usability gap: the initial rehearsal Camera
page renders **79 action forms, 73 disabled and 6 enabled**, plus the complete
physical setup/status history. The next-step link works, but the page still
requires operators to distinguish many unrelated or future forms. Software
qualification is incomplete even if the nominal backend chain later passes.

Implemented after run 01 terminated, with details and verification in the
[usability handoff](CAMERA_WIZARD_USABILITY_HANDOFF.md):

- Keep next-step guidance, image provenance and current connection state visible.
- Present current eligible camera forms together; retain unavailable actions and
  their exact reasons in a clearly labeled expandable section, not deleted data.
- Group detailed original/physical diagnostic panels rather than placing all
  history before the first usable form. Preserve access to historical failures.
- Opening a section or following a link must remain navigation-only: no preview,
  selection, consent, source refresh, capture, or backend state change.
- Preserve explicit expansion/focus appropriately across UI refresh; malformed
  action eligibility must never make an action available. The server stays the
  sole authority and every operation still needs its reviewed ticket.
- Verify the real renderer with finite-DOM tests and another browser walkthrough,
  including no-effect navigation and access to disabled-action explanations.

The browser findings are a UI review, not a full end-to-end browser acceptance
or physical setup test. No viewport overrides, OS permissions or device settings
were changed.

The 2.57-second initial finite-DOM UI regression run overlapped the tail of
full-history run 01. It changed no production source, original store or native
owner. Report this overlap when interpreting the diagnostic timings; they are
not isolated performance benchmarks. The terminal failure was the explicit
invalid operator label, not a timeout.

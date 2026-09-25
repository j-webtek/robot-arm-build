# P1: one fresh existing-root observation

Date: 2026-09-12. Status: implemented; 796 distinct selected checks passed on
`01440cf0…91eb9`. Run 07's test **PASSED**, but the final source comparison
**FAILED**: concurrent arm/UI edits changed the shared checkout during the run.
Fixed-source acceptance remains open. See the terminal audit below.
Continuation of [bounded-read profiling](CAMERA_BOUNDED_READ_BUFFER_WORKORDER.md)
under [ROCELL-PRECAL-001](PRE_ARM_CALIBRATION_EXECUTION_PLAN.md). No camera/arm IO.

## Candidate and evidence

The eight-campaign profile retains 39,780 `nt.stat` calls and 1,772 `safe_root`
calls per instrumented callback. Before this change, the publication adapter's
`_existing_root` called `_candidate`, which ran `contained_path`, then `safe_root`.
That performed two complete ancestry observations while establishing one root.
The retained baseline caller edges attribute those walks below.

Implemented narrow change: factor the existing lexical path validation into a
private helper. `_existing_root` uses that helper followed by one fresh
`safe_root`. `_candidate` retains its physical `contained_path` validation for
new publication destinations. There is no cache, saved approval or new API.

## Predicate and observation map

| Requirement | Before | Implemented |
| --- | --- | --- |
| Path type, absolute/canonical components, Windows-safe names | `_candidate` | Same code in lexical helper |
| Qualified-root lexical containment, including prefix siblings | `_candidate.relative_to` | Same check in lexical helper |
| Every ancestor's link/reparse/hardlink and IO checks | `contained_path`, then `safe_root` | One complete fresh `safe_root` walk |
| Actual existence, strict canonical resolution and directory type | Final `safe_root` | Same `safe_root` |
| New destination candidate's physical containment | `_candidate` → `contained_path` | Unchanged |
| Qualification root/volume/receipt observations | Calling operation | Unchanged, still independent |
| Later selected-file path containment and opened-handle validation | `read_bounded` after `_existing_root` | Unchanged, still independent |
| Global/selected snapshots, original guards, audits and leases | Admission callers | Unchanged |

For a stable filesystem, strict resolution equal to the lexically contained
candidate plus the full ancestor checks subsumes the earlier non-strict candidate
resolution. Missing roots remain rejected; missing destinations still follow the
unchanged `_candidate` path. No component's predicate is omitted.

This is not an assertion of identical rejection timing under arbitrary concurrent
path substitutions. Two earlier observations become one inside this root-establishing
helper. Neither version pins all ancestor handles or supplies filesystem snapshot
isolation. The later file-containment pass and native leaf-handle checks remain;
every operation re-observes its own roots. Root pinning or approval reuse across
reads is outside this ticket. Reject the change if it requires dropping those
independent boundaries or changes the documented stable-file rejection rules.

## Verification sequence

1. Preserve a baseline caller-attributed profile on source `a654894e…9898c`.
2. Run new counting/fault tests against the old code; retain expected count failure.
3. Implement only the lexical-helper/existing-root change, then verify all root
   predicates, later containment, qualification, publication, ledger and admission
   callers. Include actual isolated junctions, hardlinks, missing paths and IO errors.
4. Re-profile freshly constructed zero/four/eight-campaign stores. Compare call
   counts deterministically and wall times as observations, not guarantees.
5. A full-history successor requires a justified improvement, fixed inputs and
   passing regressions. Keep startup deadlines, quotas, native binaries and failed
   original stores unchanged. Actual device testing remains deferred.

All fixture directories must be newly named; never reuse a pytest base directory.
The full-history run-05 failure remains preserved regardless of successor results.

## Baseline and implementation evidence

New caller-attributed baseline: `storage-root-baseline-20260912-01.xml`,
**1 passed, 3 deselected, 64.08 s**, on source `a654894e…9898c`. The four-campaign
fixture has 70 references, 20 records and 20 attempt events. Its three callback
samples are 1,042.411 / 1,055.030 / 1,114.550 ms. These are host observations,
not deadline assertions or controlled comparisons with previous days' runs.
JUnit SHA-256:
`fc9503c56e78b4ae9247ffc3d5626f18e50db6347f5f2e595c19845cf3c8de29`.

The callback contains 184 `_existing_root` calls: 174 from bounded ledger/record
reads and ten from directory listings. All 184 first call `_candidate`, which
walks/resolves the same candidate before the final `safe_root`. Total callback
`safe_root` count is 972. Those root calls cost 0.223 s inclusive in the
instrumented callback; the nested candidate part accounts for 0.141 s. They
overlap and are not additive. Per-file read callers are 60 family record reads,
110 attempt-ledger reads and four quarantine-ledger reads.

The baseline counting/fault run has **27 passes and one expected failure**:
the deep existing-root case observes 11 extra ancestor checks in the old code.
Its new store and JUnit (`storage-root-red-20260912-01.xml`) are preserved.

Production change is confined to `physical_onboarding_storage.py`:
`_lexical_candidate` holds the unchanged lexical predicates; `_candidate` keeps
its destination observations; `_existing_root` establishes a directory with one
fresh complete walk. The shared buffer reader is not changed again.
New production fingerprint:
`01440cf0377027aceab5f5375bd4ecbd1211f2e704b368262ad91e84f8391eb9`.
No historical session is rebound to this fingerprint.

`storage-root-green-20260912-01.xml`: **128 passed in 6.63 s**, including 28 new
root cases, existing storage publication/concurrency cases, component/qualification
observations, durability and bounded-buffer behavior. Black passes the three
edited Python files; scoped Mypy passes the one changed production module.
Green JUnit SHA-256:
`fd8a1374a1a9939179f882ab2c88791909ebd3e69b3db0bba4121cef3c7b6571`.
Red JUnit SHA-256:
`e52040b268448d36885aeaca8a08496b9b515a6e1f0134dc94424750512da7a4`.
Production module SHA-256:
`23f1a5fbe73fa2b8cae8cd5ee66dea5e1e6d2b5c1e2e41b8967aa05ab0b1fc3f`.

The profiling test now retains cProfile caller edges as well as function rows.
Its added mixed history constructs one presence, three identity and one camera
campaign with zero-effect in-process workers. It uses production record formats,
family audits and ledgers, but prerequisite facts and stage movement are explicitly
modeled. It is not a replay of genuine original history, received-unit evidence,
real source hashing, sibling-session qualification or parent startup acceptance.
The full-history successor still has to exercise those integrated boundaries.

## Optimized profiling result

`storage-root-profile-20260912-01.xml`: **5 passed in 274.61 s**. JUnit SHA-256:
`55f8891d1741aa770d95f3bf7c195346ff02b63188ee7d7beb28434a401210aa`.
Fresh per-case JSON profiles, including caller edges, are under
`software/runs/pytest-storage-root-profile-20260912-01`.

| References / prior history | Three callback observations | `safe_root` calls | `nt.stat` calls |
| --- | --- | --- | --- |
| 4 / no campaigns | 155.079 / 143.712 / 143.553 ms | 134 | 3,339 |
| 70 / no campaigns | 426.869 / 421.550 / 421.196 ms | 134 | 12,843 |
| 70 / four camera campaigns | 975.794 / 977.900 / 989.367 ms | 788 | 25,804 |
| 70 / eight camera campaigns | 1,408.914 / 1,405.371 / 1,398.820 ms | 1,428 | 34,964 |
| 70 / five mixed campaigns | 1,174.019 / 1,215.343 / 1,183.513 ms | 960 | 28,424 |

The matched four-campaign baseline had 972 root calls, 28,380 `nt.stat` calls
and 868 bounded file reads. The optimized case removes **184 root walks and
2,576 metadata calls**, while retaining **868 file reads and three family
audits**. The observed callback saving is consistent with that reduced work;
ordinary host activity was not isolated. Do not attribute all differences from
older runs to the patch or infer worst-case deadline margin from these samples.
No competing test suite ran during the measured profiling callbacks.

The mixed fixture contains 25 family records / 54,707 canonical record bytes,
25 attempt events and 70 references / 730,179 payload bytes. Its domain counts
match the retained full-history shape (one presence, three identity, one camera
campaign), but its modeled record subjects are smaller than the full-history
subjects. It does not substitute for the final parent release path. The eight-
campaign case provides a separate growing-ledger observation, not quota-limit
qualification. All five passes assert valid fresh histories and equivalent
callback results, not elapsed-time acceptance.

Updated profiler test SHA-256:
`8c047fc0a7d6e42856762b0a4e73805b5b3c42ad82c2356ecb4ee923f6fe1681`.
New root-test SHA-256:
`7f77364243fc849cb71f0d713f1ca69c8915e76e121b63f744c9b5712f769aaa`.
The full-history test remains unchanged, SHA-256:
`623fae535135484c93fa118075fd02d88bd6752f122bda05e3090c6f77fbeb06`.

The measured saving plus these bounded histories justify a full-history
successor **only after** the wider storage/admission/UI regression selections
pass. Source and test inputs must stay fixed throughout that successor.

## Broader regressions and full-history successor

- `storage-root-consumers-20260912-01.xml`: **207 passed, 135.11 s**, covering
  V2 originals, attempt/quarantine ledgers, leases, M1, camera readback and
  USB identity/presence persistence. SHA-256:
  `d0e115dafc22e82d4f7c675812bddd5b21071e7e36044baf232ddfc8adff9cee`.
- `storage-root-regression-20260912-01.xml`: **417 passed, one slow case
  deselected, 181.74 s**, covering coherent camera/USB observations, original
  scope/capacity, consumed permits, parent/supervisor/dispatch, dataset and UI.
  SHA-256 `7679d9881a19c0e20705bd71f7edee59511a5e1cf1af6de029ea1b9f0e17fc17`.
- These two regression selections ran in parallel, **not** during profiling.
  JUnit case keys across them, the 128-case primitive selection and five-case
  profiler were checked for duplicates: **757 distinct passing cases**.
- Actual rehearsal and physical launcher `-Check` calls both report
  `READY_FOR_DIAGNOSTICS`, revision zero, camera/arm `NOT_CONNECTED`, no physical
  authority and zero diagnostic events. The assigned export directory remains
  `software/runs/wizard-exports`; no server or device operation was started.

Fresh run 06 is launched only after verifying its output paths are absent:

```powershell
.\.venv\Scripts\python.exe -m pytest `
  software/tests/unit/test_arrival_camera_full_history_ntfs.py -v -m slow --tb=short `
  --basetemp=software/runs/pytest-camera-full-history-20260912-06 `
  --junitxml=.codex-preserved/camera-full-history-20260912-06.xml
```

Production fingerprint was rechecked as `01440cf0…91eb9` before launch. The
unchanged full-history test uses fresh originals, normal storage/readback and
the actual parent/supervisor/production deadline logic; source identity and
hardware/process peers remain explicitly modeled. No competing test suites,
source/configuration/native-runtime or selected test-input changes are allowed
during the run. Documentation and bounded read-only review may continue.

### Run 06 terminal evidence

**1 failed, 7 deselected, 2,053.84 s (34:13).** Executing production fingerprint
remained `01440cf0…91eb9` when rechecked after termination. The original full-
history test-file SHA was still `623fae53…fbeb06` during the run. No inputs were
edited during execution; only documentation and bounded read-only review ran.
Additional local commands were stopped before the late camera checks.

- JUnit `.codex-preserved/camera-full-history-20260912-06.xml`, SHA-256
  `c1527a7930237cb2c09b9d663ffc13c7d51b1a385102336f04479d3aa7574611`.
- Checkpoint under
  `software/runs/pytest-camera-full-history-20260912-06/test_full_original_history_reo0/camera-full-history-checkpoint.json`,
  SHA-256 `c3eb6fa41a61df4e25b9a4090aee2cccad49ddb97944468b8245e169f1286b85`.
- Trace: 1,352 completed spans; no unfinished/dropped spans or observer errors.

Completed: complete USB history/review/export/reopen; fresh metadata; original
probe preparation/review; **probe**; reported-settings staging. The capture
campaign also reached native-result/readback handling; the public capture action
then failed before image ingestion/publication. Camera capture export and final
post-capture readback/lease assertions were **not reached**. Checkpoint `completed`
and camera `exports` remain empty; earlier USB exports are not camera acceptance.

| Release observation | Probe | Settings capture |
| --- | --- | --- |
| Existing protocol admission limit | 2,000 ms | 5,000 ms |
| Parent final `check_release` | 1,625 ms, returned | 2,156 ms, returned |
| Observed begin-return to release-end interval | 1,656 ms | 2,203 ms |

The limits above are already purpose-specific in the unchanged production
protocol; capture was **not** granted a new timeout. Trace endpoints are not
exact internal deadline/slack samples. Probe also has an earlier 2.078 s fresh-
admission observation, and capture has one at 2.547 s; those are not the final
release observations. A passed run would still not qualify worst-case host load
or actual received-camera startup.

The failed action is `physical_camera_configuration_capture`, operation
`operation-8809fb90c1d843c983d700b1a31bf62e`. Public completion is persisted with
`DIAGNOSTIC_FAILED` / `FileNotFoundError` for the temporary workspace's missing
`rocell.ps1`; the capture card is `FAILED_HELD`. This failure is not the earlier
probe admission timeout. The exact originals and failed public attempt are kept;
no retry or edit of that store is performed.

Read-only inspection of the retained result records confirms both underlying
campaigns are `SEALED_KNOWN`, with empty reason codes and modeled cleanup
confirmed: probe `attempt-20a71b7e72ca462cbec2a25b3b8c1922`, capture
`attempt-2b88c95b09b447408a892db731f8c8cb`. Capture records one **modeled** frame;
these are incapable-process test observations, not actual camera access. The
public capture's ingestion/publication failure is distinct from campaign state.

### Post-run test-fixture correction

`PhysicalCameraCaptureWorkflow.accept_capture` correctly performs its own fresh
source comparison before ingesting raw frame bytes. The long fixture deliberately
uses a partial copied workspace with a **modeled** source identity, but its alias
roster omitted `physical_camera_capture_workflow.source_fingerprint`. This left
that newly reached boundary calling the actual complete-checkout reader.
Copying only a dummy launcher would not fix the inconsistent source contract.

After run 06 ended, its fixture source roster was factored into
`model_isolated_camera_source` and extended to include the ingestion module.
The shared production `source_fingerprint` and every production source comparison
remain unchanged; the helper models only the existing partial-workspace source
fact. Fixed runtime-byte verification, originals, admission, clocks and quotas
are not replaced. This is a test-only correction, not a runtime permission change.

New fast tests in `test_camera_full_history_source_fixture.py` exercise the
actual settings-verification ingestion path with fresh small pixels, require the
fixture's source alias, and verify a changed source still rejects. Their modeled
native observations are not full-history or hardware acceptance. Development
run 01 also exposed an omitted test `configuration_verification=True` argument;
it is preserved. Corrected pre-fix run 02 reproduces two missing-launcher
failures while the changed-source rejection case passes.

The full-history test's new SHA-256 is
`0053711db72f71d9f6c44b3598f792bf667ba554056b68722911a5d3a01dd4c0`;
the new fast test's is
`89d3fb74b6adc081cb5e79547cb1d0b2092b926068e24afe64aed06a2cd88a50`.
No second production optimization was made after run 06. A further full run must
construct new originals and use this explicit corrected fixture, never repair
the failed store or describe the retained run 06 as passing.

### Corrected fixture regression and run 07

`camera-source-roster-green-20260912-01.xml`: **46 passed, one slow case
deselected, 696.66 s (11:36)**. This includes three new source-fixture/ingestion
cases, activation-to-pixel handoff, the seven full-history-file fast cases,
public settings capture/publication/export and original configuration-service
failure/no-replay checks. No production source comparison is bypassed in runtime
code. Black checks all five edited Python files. Production fingerprint remains
`01440cf0…91eb9`.

The current combined selections contain **796 distinct passing case IDs**;
seven of the 46 cases rerun earlier fast coverage and are not double-counted.
At that pre-run checkpoint the full workflow had not passed.
The corrected-fixture regression JUnit SHA-256 is
`fafa50ba8fc2ce49b1d378daa77551a93a6ec469a04a02c466def02cff8d4584`.

Run 07 started in a new absent output directory, with the corrected test-file
SHA `0053711d…dd4c0` above. This task launched no competing suite and made no
production input changes during the run. The intended shared-source freeze was
not achieved: the terminal audit found concurrent edits outside this patch. Live
pytest stdout is also retained, so predecessor checkpoint progress is visible
without repeatedly starting filesystem-inspection commands.

```powershell
.\.venv\Scripts\python.exe -m pytest `
  software/tests/unit/test_arrival_camera_full_history_ntfs.py -v -m slow --tb=short `
  --capture=tee-sys `
  --basetemp=software/runs/pytest-camera-full-history-20260912-07 `
  --junitxml=.codex-preserved/camera-full-history-20260912-07.xml
```

**Run 07: test PASS, fixed-source acceptance HELD.** The prior run's successful
modeled campaigns and failed ingestion remain preserved; no original was amended,
replayed or used as the seed for run 07. Real camera/arm access remained out of scope.

## P1.5 restart/export review while run 07 is active

This is a read-only coverage inventory, not an additional passing test claim.
The full-history test creates a fresh Arrival application before camera metadata,
probe and settings capture. Its final post-capture action is a same-application
original refresh with independent readback and lease checks; it does **not**
construct another Arrival application after capture. Do not describe that final
refresh as a complete post-capture restart acceptance run.

| Boundary | Existing coverage and meaning |
| --- | --- |
| Full predecessor restart and fresh camera entry | Run 07 assertions passed, subject to the source-drift hold below; physical facts/source identity are modeled |
| Same-launch post-capture originals and lease exit | Run 07 final assertions passed, subject to the same source-drift hold |
| New launch discards settings references and capture queues | `test_camera_configuration_wizard_retention.py::test_restart_has_no_settings_receipt_or_attempts`; queue context modeled, no original reader |
| Exact attempt export survives rotating ordinary history and holds | Retention tests; diagnostic packet continuity, not restored native ownership |
| Changed/missing export parts and wrong report family reject | `test_camera_configuration_attempt_export.py`; pure codec plus isolated export files |
| Source-bound original discovery/revalidation | `test_physical_camera_reopen_registry.py`; distinct from capture-queue restoration |
| Browser/terminal show old and current launch separately | `test_wizard_physical_camera_restart_ui.py`; renderer checks are not physical reopening |

After the active run terminates, rerun the relevant retention/export/registry/UI
selections on this source using a unique directory. Keep local historical-export
renderer fixtures separately labeled; do not treat their old source as current
integration evidence. Rehearsal's existing post-capture M1 reopen test exercises
the rehearsal service and must not be relabeled as the physical Arrival workflow.

The operator guide now leads with the current settings-capture path and marks
older integration notes as historical. It explicitly distinguishes opening
original setup, reading an export and reacquiring current process-local owners.

Selected post-run command (not to run concurrently with full-history admission):

```powershell
# Both destinations must be absent; choose another suffix if either exists.
.\.venv\Scripts\python.exe -m pytest `
  software/tests/unit/test_camera_configuration_wizard_retention.py `
  software/tests/unit/test_camera_configuration_attempt_export.py `
  software/tests/unit/test_camera_configuration_attempt_ui.py `
  software/tests/unit/test_physical_camera_reopen_registry.py `
  software/tests/unit/test_wizard_physical_camera_restart_ui.py `
  software/tests/unit/test_wizard_camera_next_step_ui.py `
  -q -m "not slow" -k "not actual_two_launch_public_export" --tb=short `
  --basetemp=software/runs/pytest-camera-restart-export-20260912-01 `
  --junitxml=.codex-preserved/camera-restart-export-20260912-01.xml
```

The excluded three parameterized cases render old local two-launch exports.
Their exclusion prevents mixing historical-source artifacts into this current
source selection; it does not replace a genuine post-capture restart test.

## Run 07 terminal audit — 2026-09-12, approximately 13:42 local

The test returned **one PASS in 2,242.325 s (37:22)**. All eight camera-successor
operations succeeded: fresh original refresh, probe preparation/review, probe,
settings, one-frame verification, exact-attempt export and final fresh original
refresh. The final assertion verifies stable predecessor subjects and no active
or stale leases. Arm and camera remain `NOT_CONNECTED`; physical authority is
false and stage 5 remains `WAITING_OPERATOR`. The test does not reopen another
Arrival application after capture, and does not qualify any actual hardware.

However, the post-run complete-checkout fingerprint comparison rejected:

- Recorded at test start: `01440cf0377027aceab5f5375bd4ecbd1211f2e704b368262ad91e84f8391eb9`.
- Observed after termination: `af19e6a300c8a466c364412f5798502790862970f08b983c9b84bbe7037d615c`.

Read-only timestamps show edits outside this patch during the run, including
`legacy_usb_metadata.py` at 13:10:34, `terminal.py` at 13:21:08, `app.js` at
13:27:39, `arrival_wizard_service.py` at 13:28:35, `controller_metadata.py` at
13:35:09 and the passive-arm/owned-process modules at 13:40:35. Additional arm
qualification files also changed. Their contents are preserved, not reverted.
The storage module and full-history test retain their recorded hashes above.
Markdown changes are excluded from this fingerprint and do not explain the drift.

The fixture deliberately models isolated source identity; its one actual
executing-checkout fingerprint was recorded at the start. Therefore its green
pytest result does not prove that subsequently imported/read files stayed at
that revision. Loaded older modules and later on-disk reads must not be treated
as one pinned release. **Do not mark P1.4 complete or combine this result with
the earlier selections as current fixed-source acceptance.**

Retained evidence:

- JUnit: `.codex-preserved/camera-full-history-20260912-07.xml`, SHA-256
  `9e9501199b35da8f70f70ae8e7edb9b8a6c8c81b7801a4c2489fe9d7915b61ef`.
- Checkpoint: `software/runs/pytest-camera-full-history-20260912-07/test_full_original_history_reo0/camera-full-history-checkpoint.json`, SHA-256
  `155a71ae0dfaa7d2ab742d5beeb3b6b984af780b0616bf7d9a7b50bd7c8e9c27`.
- Successful capture operation: `operation-4d30b92ef44c46a9ba3a0f028e9ffe72`.
- Exact export, under that test root:
  `reboot-exports/wizard-20260912T174055217553Z-e0686dddd2e14338b3a57f53318a2302`.
  Independent read-only verification reports `VERIFIED_DIAGNOSTIC_EXPORT`, four
  payload files / 135,733 bytes, manifest SHA-256
  `6b883d435c9a5d1c2214af10c391ee3dd6c35856a35c40ee4b5532a0661a5542`.
  Export source identity is explicitly modeled `a` × 64, not either checkout hash.

The trace contains 1,484 finished spans, zero unfinished/dropped spans and zero
observer errors. Probe release returned in 1,672 ms, with 31 ms between `begin`
return and release start (1,703 ms observed combined interval). Capture release
returned in 2,156 ms, with a 47 ms gap (2,203 ms combined). Purpose-specific
limits remain 2,000 ms probe / 5,000 ms capture. These are observed intervals,
not retained internal deadline timestamps, worst-case margins or fixed-source
performance qualification. Concurrent external work/load was not controlled.

The post-run retention/export/registry/UI selection returned **144 passed,
three historical-export cases deselected, 12.48 s**. Its JUnit is
`.codex-preserved/camera-restart-export-20260912-01.xml`, SHA-256
`b76a10804195d8c6d857bd0d0593415a5a760558cacbd371225f9c195a0b5833`.
This later selection ran after the drift; do not add it to the 796 earlier
checks as if they verified one frozen revision. It uses isolated files and
modeled UI/queue inputs, not physical hardware.

**Next dependency:** coordinate the shared checkout or create and verify an
isolated complete source snapshot before a fresh acceptance run. Record a
per-input manifest and verify it both before and after, in addition to the
actual aggregate fingerprint. Do not extend deadlines, rebind originals, stop
another task, overwrite concurrent changes or seed the successor with run 07's
store. The current test success is retained useful composition evidence, not
permission to close the fixed-source gate.

### Automatic terminal source guard added after run 07

The full-history test now records `executing_source_audit` in its checkpoint,
using the actual checkout reader separately from the isolated fixture's modeled
identity. A changed or unreadable ending source prevents a successful workflow
from passing. An audit read error is retained as data so it cannot mask an
earlier workflow exception. This is test code only, not a production policy or
runtime change. Endpoint comparison is not continuous change detection: a
verified isolated snapshot remains the preferred way to avoid concurrent edits.

Four new fast cases cover matching source, changed source, unreadable source and
missing terminal audit. Together with the existing fixture/full-file fast cases:
**14 passed, one slow case deselected, 4.29 s**. Black checks both edited tests.
Report: `.codex-preserved/camera-terminal-source-20260912-01.xml`, SHA-256
`d5acf58d9775da3b951911860115f0ae9456c92a2ad10121d375f9d77fff42c4`.

New test hashes, for a future successor only:

- `test_arrival_camera_full_history_ntfs.py`:
  `0e24b2511c06af72c286a9ff4e9004cdf1e9ca627ed77e5aaf31d7ab2eefc846`.
- `test_camera_full_history_source_fixture.py`:
  `0b4a6f5ba964bbe4d2aed9195ed08efd1b2b99137ad518d2be3620d9fc8ae608`.

The executing-checkout fingerprint changed again during this follow-up work;
the final observed value was
`17d25898589fba3ad8c356b87e30b1f5a120d90056e93bcb601e64df393824f2`.
It is an observation, not a reviewed release or a source pin for the 14-case run.
No combined current-revision test count is claimed. All eight edited Markdown
documents passed a 263-local-link existence check. Other contributors' changes
were not reverted, and no physical device operation was performed by this task.

### Camera-only successor

The new [isolated camera acceptance work order](CAMERA_ISOLATED_ACCEPTANCE_WORKORDER.md)
records the separate copied-input manifest, isolated smoke, complete lane and
post-capture fresh-application restart checks. Use its terminal execution ledger
for the successor outcome; preserve all run-07 limitations above. No result from
that copy is silently transferred to subsequent shared arm/UI/source edits.

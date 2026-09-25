# P1 camera admission: one fresh coherent observation

Date: 2026-09-12. Supports P1.1–P1.4 of the
[pre-arm-calibration plan](PRE_ARM_CALIBRATION_EXECUTION_PLAN.md).
Status: targeted implementation verified; full-history run 04 **FAILED**.
P1 remains incomplete. No hardware was accessed by this increment.

Successor: [bounded Windows read buffers](CAMERA_BOUNDED_READ_BUFFER_WORKORDER.md)
profiles fresh originals and reduces allocation/copying without removing a read
or check. Its latest 681 selected cases pass, including expanded history profiling;
full-history run 05 still fails the
complete startup deadline (1.969 s release callback plus startup/READY). Run 04's
terminal failure and all source bindings below remain historical and unchanged.

## Preserved baseline and measured boundary

Run 03 remains an original, failed integration run. See the
[full-history work order](CAMERA_FULL_HISTORY_INTEGRATION_WORKORDER.md) for its
source, JUnit, attempt identity and admission-deadline failure. No saved store
was restored as an input, repaired, repinned or retried.

The read-only trace has eight `_fresh_admission` observations. Their inclusive
durations are 1.875–1.938 s. Inside each one, `_admission_observation` takes
0.828–0.859 s, including a separately traced `snapshot` taking 0.203–0.204 s.
The first/final original record guards take 0.406–0.469 s each, including both
their record audits and independent snapshots. These are nested, overlapping
observations; do not sum them as exclusive cost. Trace timestamps alone do not
explain every part of the 4.235-second supervisor interval.

Read-only enumeration of the terminal run-03 original root finds 70 evidence
packages totaling 792,224 payload bytes and 25 camera-family records totaling
408,212 file bytes (5 camera, 15 USB identity, 5 USB presence). These are terminal
counts, including the failed attempt, not a claim about the earlier release
instant. The fixture source and physical observations were explicitly modeled;
executing checkout source was recorded separately. Historical host load was not
fully recorded and cannot be reconstructed. No isolated-host benchmark claim.

Source inspection identifies one removable duplication: the legacy camera
observation obtains `transaction.snapshot()` and then `runtime.verify()`, whose
existing `_verify_with_snapshot()` already returns the exact selected snapshot
alongside verification. USB identity uses that coherent pair already.

## Implemented boundary

- Extract the existing USB pair-validation checks into the protected shared
  `_coherent_admission_observation` method; USB retains its exact checks/error.
- Have the actual camera runtime supply its existing `_verify_with_snapshot`
  callback. The camera transaction uses that fresh pair for each admission.
- Cross-check exact types, cell/source/session identity, header/head hashes,
  qualification anchor, reconciliation state and canonical evidence inventory.
- Check the live transaction scope before and after the callback. No result is
  retained as approval for the next call. Legacy compositions without the hook
  keep independent reads.
- Leave global/sibling verification, complete camera-family audits, both probe
  original guards, post-disk audit, source/enrollment/Stop checks, native runtime
  verification, permits and every timeout/quota unchanged.

This is one coherent point-in-time observation, not continuous filesystem
monitoring. Removing the earlier duplicate observation is not identical temporal
coverage of a mutation existing only during that removed interval. Later guards
remain independent, and a newly changed package or record is never accepted
because it appeared in a previous snapshot.

Implementation files:

- [Shared persistence](../src/rocell/application/commissioning_m1_persistence.py).
- [Camera persistence](../src/rocell/application/commissioning_camera_persistence.py).
- [USB persistence](../src/rocell/application/commissioning_usb_identity_persistence.py).
- [Actual runtime composition](../src/rocell/application/physical_onboarding_m1.py).

## Tests and diagnostic instrumentation

[New camera tests](../tests/unit/test_camera_coherent_observation.py) cover mixed
pairs, identity/source mismatch, exact types, lost scope, retained legacy
behavior, a newly added original without a changed journal head, and corruption
in each of the three record families. They compare complete admission callbacks
with four versus 52 original references, alternating legacy/coherent order.
All three full record audits must still run; no device or process can execute.
These file-only fixtures have no prior campaign records. They are not substitutes
for the heavier full-history test or a maximum-record/maximum-byte benchmark.

The full-history observer now also delegates/times consumed-permit revalidation,
global and selected runtime reads, parent begin/release checks and capacity
arithmetic. Arguments, results, exceptions and clocks remain unchanged. Its
4,096-entry cap and dropped/error/unfinished counters remain explicit. New
observations cannot authenticate a saved trace or authorize an actual camera.

Retained development runs:

- `precal-coherent-red-20260912-01.xml`: one expected regression failure before
  the production change (camera transaction lacked the paired observation hook).
- `precal-coherent-20260912-01.xml`: 53 passed, two failures, 117.09 s. Both
  failures occurred in report metadata after the read-count/equality assertions:
  Python's `platform.platform()` attempted a shell command and the no-process
  fixture refused it. Use `sys.platform`, interpreter version and in-process
  Windows version data instead; the process guard is unchanged.
- `precal-coherent-20260912-02.xml`: **78 passed**, one slow test deselected,
  118.08 s. SHA-256
  `4893992abe1d6f717dc811143e83a66a543a6c7b1def258a29cef73fb28e1d87`.
- `precal-coherent-regression-20260912-01.xml`: **226 passed**, 85.68 s.
  SHA-256 `cdbde4870b1e33ac93c579e0ff0a5399ce6c943f30b325ef8eda69860e2a4af4`.
  Covers capacity, original scope, fresh M1 reads, camera storage lifecycle,
  consumed scopes, parent admission, supervisor faults and dispatch handoff.

The two final selections contain 304 cases without overlapping test files.
Black passes all six edited Python files; scoped Mypy passes the four production
files. The workspace virtual environment lacks Black, so the already installed
host Black executable was used; no dependency installation was performed.
Both launcher `-Check` modes return `READY_FOR_DIAGNOSTICS`, revision 0 and camera/
arm `NOT_CONNECTED`. These are inert launch checks, not a new commissioning run
or received-unit connection. Whole-application typing is not claimed clean.

Additional unchanged-source pixel/UI regression:
`.codex-preserved/precal-ui-pixels-20260912-01.xml`, **113 passed in 6.49 s**.
SHA-256 `ebb5ec2c88c75fe2d8d2510bbc5e8bebb855cb6d168501993cbe3a7a06449e55`.
This covers native-size synthetic YUY2 ingestion in both row orientations, the
actual renderer's worker-versus-feasibility distinctions and portable operator
input rules. The three final selections total **417 cases**, without overlapping
test files. No actual browser/device was operated by this added test selection.

Run-02 comparison artifacts report:

| File-only history | Legacy callback | Coherent callback | Full V2 loads | Family audits |
| --- | --- | --- | --- | --- |
| 4 references / 564 payload bytes | 187–188 ms | 156–172 ms | 4 → 3 | 3 → 3 |
| 52 references / 1,754 payload bytes | 625 ms | 484–516 ms | 4 → 3 | 3 → 3 |

Host: Windows version tuple 10.0.26200, Python 3.10.10. Durations use the real
monotonic clock; granularity and ordinary host activity affect the observations.
This is evidence of reduced work, not an admission-time guarantee. Source/type
inspection overlapped part of the focused run; it was not an isolated benchmark.
Actual unit, USB speed, camera controls and installed geometry remain unqualified.

Current production source fingerprint:
`81dc579fa3126b18aea151160573757fac3af710f92e177604abc4c99162071a`.
No configuration, native binary/catalog or hardware build file changed. Do not
rebind historical source-bound records to this fingerprint.

## Remaining acceptance

1. Focused and corruption/lifecycle/deadline selections passed (417 cases).
   Retain them as regressions for the next measured change.
2. Run 04 froze source/runtime inputs and reached a terminal failure, below.
   Diagnose and repair the remaining cost before another full-history run;
   use new store and JUnit paths. Observe admission decisions, not just timing.
3. Retain failures as failures; investigate any remaining boundary without
   extending deadlines or importing a constructed predecessor from an old run.
4. Verify public settings-frame/export/original readback and inert restart only
   after their corresponding test reaches them. Mark P1 complete only with its
   full required acceptance, not from the local load-count improvement.

## Full-history successor — run 04

Launched 2026-09-12 in a previously absent store:
`software/runs/pytest-camera-full-history-20260912-04`.
JUnit destination: `.codex-preserved/camera-full-history-20260912-04.xml`.
Terminal result: **1 failed, 7 deselected in 2,346.00 s (39:06)**.
JUnit suite time: 2,345.961 s; SHA-256
`5d4321fa4d7acd2fc42dd380bdcc8a0294f8b8fad34e5c5bce5679b2e4c34663`.
Production fingerprint is the `81dc579f…62071a` value above; test-file SHA-256:
`623fae535135484c93fa118075fd02d88bd6752f122bda05e3090c6f77fbeb06`.
Both were rechecked unchanged after termination.

The command selected the single `slow` full-history case in
`test_arrival_camera_full_history_ntfs.py` with `-v --tb=short` and these new
`--basetemp` / `--junitxml` paths. Existing run paths remain untouched. No source,
configuration, native-runtime or test-input edits are allowed during execution.
Read-only investigation and documentation updates do not rebind the run.

While run 04 was in its earlier USB prefix, three read-only hashes of the actual
checkout took 151.476 / 126.144 / 125.727 ms and returned the same fingerprint.
This cost is additional context: the full-history fixture explicitly models
its isolated-workspace source identity, so it cannot establish real checkout
hashing latency at a physical release boundary. No acceptance cache was added.
Two short nominal `hi` simulations (approximately 6.5 s and 2.8 s) and bounded
solver comparisons (approximately 20 s and 8 s) also ran during that early prefix.
Record this overlap; the complete run is not an isolated-host benchmark.
The 6.49-second pixel/UI regression also overlapped the earlier reboot prefix;
it changed no full-history source, runtime input, original or clock.

### Terminal evidence and reached boundary

Retained checkpoint:
`software/runs/pytest-camera-full-history-20260912-04/test_full_original_history_reo0/camera-full-history-checkpoint.json`.
Checkpoint SHA-256:
`2d13ce902120f4f227bee8e1f40b43775f18b377fd592dc28924674daecd2743`.
Its original store, diagnostic events and previous USB exports remain intact.
The checkpoint is a developer diagnostic, not a replacement exact-attempt export.

The complete four-phase USB predecessor, public final review/reopen and fresh
camera metadata completed using explicitly modeled physical/process facts.
Recorded public camera operations then succeeded: refresh (59.015 s), preparation
(112.516 s) and review (112.282 s). Probe operation
`operation-4bd10c2606a84d25b22bf4429b1e8eab` failed. The assertion prevents its
addition to the successful-operation list; its failure survives in diagnostic
events, the JUnit failure and original probe packet.

Attempt `attempt-4219484670514471a6d2f8a9107d5107` is `SEALED_UNCERTAIN`,
with `NATIVE_ACCOUNTING_UNAVAILABLE`, quarantine latched, no replay and exited
readback scope. Original supervision reports `ADMISSION_DEADLINE_EXPIRED` and
`release_check_passed: false`. Its total supervisor interval is 4.156 s.
The modeled owner's cleanup returned with no reported cleanup errors, remaining
handles or pins; this is not a native camera accounting receipt or proof of
physical cleanup. No actual process owner or hardware query ran in this fixture.

Settings staging, settings capture, camera exact-attempt export and the final
post-capture readback/lease assertions were **not reached**. `completed`, camera
`exports` and configuration `attempts` are empty. Do not describe previous USB
exports or the 417 targeted tests as this missing end-to-end acceptance.

Read-only terminal enumeration finds 70 evidence packages / 792,398 payload
bytes, and 25 family records / 408,416 file bytes (5 camera, 15 USB identity,
5 USB presence). These include failure retention, not the release-time inventory.

### Final-release timing diagnosis

The existing read-only summarizer validates the diagnostic trace structure:
940 completed/retained spans, zero unfinished/dropped spans or observer errors.
Selected spans in the **same final release** are:

| Inclusive observation | Duration | Interpretation |
| --- | --- | --- |
| `NativeCameraParentHandshake.check_release` | 2,031 ms | Raised at its post-callback admission-deadline check |
| `revalidate_consumed_permit` | 1,969 ms | Main nested validation cost |
| `_fresh_admission` | 1,860 ms | Nested within consumed-permit validation |
| Initial full `_audit_records` | 235 ms | Retained; not replaced by a cache |
| Coherent `_admission_observation` | 687 ms | Includes the global audit and independent selected-session read |
| `_global_snapshots` | 453 ms | Includes global binding checks and a session read |
| First original record guard | 485 ms | Includes a 250 ms family audit and 219 ms independent snapshot |
| Final original record guard | 453 ms | Includes a 219 ms family audit and 219 ms independent snapshot |
| Reviewed-runtime file verification | 31 ms each, three spans | Fresh checks retained around the exact release inputs |

These nested durations overlap; do not sum table rows as exclusive work. The
capacity span rounds to zero at this clock's granularity, not proof of zero cost.
The unchanged admission request allows **2,000 ms for the entire startup window**.
The release callback alone exceeds that by 31 ms; startup/READY also consumes
the window. The exact internal admission-deadline timestamp was not traced, so
an exact remaining-slack value is not claimed. `begin` starts that window after
its own revalidation: do not add its earlier 2.031 s callback to the admission
window or confuse the 4.156 s supervisor interval with that window.

Run 04's eight complete fresh admissions take 1.797–1.921 s. The coherent
observation reduces work but has **not** repaired integrated startup. Host load,
added instrumentation and slightly different retained bytes prevent treating
the run-03/run-04 elapsed difference as a controlled end-to-end speedup.

### Next bounded P1 ticket

1. Profile the lower-level V2/evidence and family-record readers used at the
   release boundary: file/path checks, actual byte reads, manifest validation,
   canonical decoding/hashing and repeated pure schema reconstruction. Keep
   real clocks and record profile overhead; do not seed a fixture from run 04.
2. Use new, incapable, real-storage growing-history fixtures to isolate those
   costs before paying for another complete predecessor. Distinguish payload
   bytes, evidence count, family records, attempts and sibling sessions.
3. Optimize only demonstrated duplicated work within one fresh verification.
   Preserve the global/sibling audit and independent selected-session read,
   both original guards, full post-disk family audit, source/Stop/enrollment
   checks and lease checks. A cached head or prior hash is not fresh validation.
4. Add mutation, interrupted-read, quota and slow-callback regressions for the
   chosen change, then rerun the 417 selected cases and a new full-history run
   under the original deadlines. Real checkout source hashing and native startup
   still need separate latency qualification; the fixture models those edges.

No further production change or blind full-history retry was made after this
failure. P2/P3 read-only findings are recorded in the
[static-task migration work order](STATIC_TASK_SIMULATION_MIGRATION_WORKORDER.md);
they do not advance P1 or change the frozen build.

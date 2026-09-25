# P1: reduce Windows evidence-reader allocation and copying

Date: 2026-09-12. Plan: `ROCELL-PRECAL-001`, P1.1–P1.4.
Status: 681 selected checks pass; full-history run 05 **FAILED**.
The allocation optimization is verified; integrated startup remains unresolved.

Successor: [existing-root observation](STORAGE_EXISTING_ROOT_OBSERVATION_WORKORDER.md)
implements the next measured metadata-read change. It records new-source test
results separately; all run-05 inputs and findings below remain historical.

This continues the [coherent-observation work order](CAMERA_COHERENT_OBSERVATION_WORKORDER.md)
after run 04 failed. It does not change the purchased B0477/static-camera design,
hardware freeze, physical stage order or deferred installed optics decisions.

## Measured problem

Run 04 retained a final release check of 2.031 s against a 2 s startup window.
Its evidence, failed attempt and quarantine remain unchanged. Rather than replay
that attempt, the new [reader profiling test](../tests/unit/test_camera_storage_reader_profile.py)
constructs fresh qualified NTFS stores with four versus 70 evidence packages.
Stages and semantic original-owner facts are explicitly modeled; no native
camera, serial, USB query or process owner is capable in this fixture.

The profiled boundary is the entire production `_fresh_admission` callback,
including both original guards and all three family audits. Three separate
uninstrumented samples precede one cProfile/allocation-observed call. cProfile
reports inclusive and exclusive costs separately; inclusive rows overlap.

The Windows reader previously allocated up to 1 MiB for **each** `ReadFile`,
including the EOF read, and used `buffer.raw[:count]`. The `.raw` access copies
the entire allocation before slicing. Small manifests and records consequently
allocated/copied much more memory cumulatively than their payload sizes.

Baseline artifacts:

- `.codex-preserved/camera-reader-baseline-20260912-01.xml`: 2 passed, 46.08 s;
  SHA-256 `9d7a75fc6654bafde87c1569ced482daeead32bf73a14528cc41ca496ab84577`.
- Each test directory under `software/runs/pytest-camera-reader-baseline-20260912-01`
  retains `camera-storage-reader-profile.json`, including complete profiler rows.
- Executing production fingerprint:
  `81dc579fa3126b18aea151160573757fac3af710f92e177604abc4c99162071a`.

## Implemented change and unchanged boundaries

Only one production function changes:
[`_windows_read_regular_file`](../src/rocell/application/physical_onboarding_durability.py).

1. Begin with at most 64 KiB, bounded by the caller's limit plus one byte.
2. Reuse that allocation for subsequent reads and EOF checks.
3. After a full chunk, double capacity only as needed, up to the existing 1 MiB
   ceiling. Large frame files quickly reach the previous large-read size.
4. Copy exactly the validated returned byte count with `ctypes.string_at`;
   explicit length preserves embedded NUL bytes and excludes stale buffer tails.
5. Continue through short reads until true zero-byte EOF. Count actual bytes,
   including the overflow byte, rather than trusting the initial file size.

Unchanged: path/component checks; a new file open for every call; opened-handle
disk/type/reparse/hardlink/size validation; delete sharing; IO failure rejection;
the final close attempt; JSON/manifest/hash validation; original-record families;
global/sibling and selected-session independent reads; leases; source/Stop/epoch/
enrollment checks; permits, admission clocks, timeouts and storage quotas.

There is no stored-file approval cache, no new device access, no changed native
binary/catalog, no new dependency and no changed public interface. This shared
file primitive also serves other onboarding readers, so regression coverage
includes those callers, not only the camera fast path. Existing close-result
policy is unchanged; an attempted close is not new proof of physical cleanup.

The optimization changes read chunk boundaries, not a guarantee of atomic file
contents under concurrent in-place edits. Existing integrity checks and read
limits still apply. Do not infer snapshot isolation from this buffering change.

## Measured callback comparison

Both runs used new independently built stores with matching modeled subjects;
neither imported a historical original. No competing test suite was launched
during these measured callbacks. Ordinary host activity was not isolated; a
read-only source/hash query overlapped the optimized fixture's construction.

| Fresh file-only history | Before, three callback samples | After, three callback samples | Before → after cumulative allocated buffer bytes |
| --- | --- | --- | --- |
| 4 references / 564 payload bytes | 172.087 / 169.558 / 171.353 ms | 153.720 / 153.860 / 153.862 ms | 71,966,141 → 10,289,152 |
| 70 references / 729,194 payload bytes | 634.857 / 612.880 / 630.776 ms | 430.949 / 429.168 / 436.104 ms | 590,832,269 → 36,241,408 |

The larger fixture's buffer allocation count fell from 1,106 to 553 while its
bounded-file read count remained **553** and `nt.stat` count remained **13,137**.
The small fixture retained 157 file reads and 3,633 `nt.stat` calls. This is
reduced allocation/copying, not skipped freshness or integrity checks.

Allocation figures are cumulative allocation requests during one instrumented
callback, **not peak resident memory**. The Windows reader's inclusive profiled
time in the larger fixture fell approximately 0.24 → 0.08 s; cProfile adds
overhead. Do not sum that span with its nested allocation calls.

These fixtures have zero campaign records, attempts and sibling sessions. They
do not establish performance at the full original-history admission boundary,
maximum supported quotas, real checkout-source hashing or received-unit startup.
Host: Windows 10.0.26200, Python 3.10.10. No real-time guarantee is claimed.

Optimized profile: `.codex-preserved/camera-reader-optimized-20260912-01.xml`,
2 passed in 36.76 s, with corresponding fresh JSON profiles under
`software/runs/pytest-camera-reader-optimized-20260912-01`.
JUnit SHA-256:
`cce4e6a5479b3db16694df641ac08a0da2cbe62a3d63edc1462ea7ec4844148e`.

Production fingerprint after the one-function change:
`a654894ea0572b11b02115ec2d0436a141926df8bae8d45f07f5200f94e9898c`.
Historical source-bound sessions must not be rebound to it.

## Tests and current acceptance

The [new buffer tests](../tests/unit/test_windows_bounded_read_buffers.py) cover:

- Small file/EOF reuse, exact copy lengths, binary bytes and embedded NULs.
- Empty files, exact limits and boundaries around 64 KiB and 1 MiB.
- Repeated short reads; observed growth beyond an initially accepted size.
- Bounded adaptive large-file reads using a 20 MiB synthetic payload.
- IO failure, impossible byte counts and allocation failure before/after a
  successful read, with close attempts and no returned partial payload.
- Actual newly created Windows files through the complete native handle path.

Retained development run `camera-buffer-red-20260912-01.xml`: 28 passed and two
expected failures on the previous reader's small/large allocation behavior.

`camera-buffer-green-20260912-01.xml`: **93 passed in 3.32 s**, combining the 30
new cases with component, durability and double-observation tests. Actual tests
include hardlink/reparse rejection, late hardlink substitution and atomic file
replacement behavior. SHA-256:
`22b0073f0cb16ff09dbdc881b88dec07d1297d4df94ed0344fc89257eaa57731`.

Black check passes all three changed Python files. Scoped Mypy passes the single
changed production module. Existing installed tools were used; no installation.

`camera-buffer-storage-20260912-01.xml`: **167 passed in 61.29 s**. This separate
selection covers V2 originals, attempt/quarantine ledgers, leases, real M1,
component/link observations and camera dataset/stage/transaction readback.
SHA-256 `e5839fe77fcbb868d73b9a531d73d71925db7264df62de33a02acd69f9233a24`.
It ran alongside the main camera regression selection, not as a timing benchmark.

Both actual launcher `-Check` modes remain inert: `READY_FOR_DIAGNOSTICS`,
revision 0, camera and arm `NOT_CONNECTED`, zero diagnostic events and no
physical authority. Both retain the assigned `software/runs/wizard-exports`
directory. These checks did not start a server or perform device operations.

`camera-buffer-regression-20260912-01.xml`: **417 passed, one slow case deselected,
208.40 s**. The previous camera coherent-observation, admission/capacity,
corruption, consumed-scope, parent/supervisor, dispatch, native-size pixel and UI
selections all pass on the new production fingerprint. SHA-256:
`b3dd6e8a92ccd582e16f97f939e5aca3908395bfe4be2555c6a8426711bcbca3`.

The four selections before run 05 contain **679 distinct test cases** (93 buffer/storage
primitives + 167 storage consumers + 417 camera/UI + 2 profiling cases). They
are selected regressions, not the whole repository suite or received hardware.

Remaining acceptance: resolve the complete startup-window cost, repeat relevant
regressions, then reach the full camera workflow in another new original store.
Run 05's terminal result is recorded below, not accepted as a pass.

Do not mark P1 complete from lower allocation or the targeted pass counts. The
next full-history run must independently reach probe, settings-frame, exports,
readback and cleanup under unchanged deadlines. No actual camera test is part
of this implementation increment.

## Fresh full-history successor — run 05

Launched 2026-09-12 only after checking both output paths were absent:

```powershell
.\.venv\Scripts\python.exe -m pytest `
  software/tests/unit/test_arrival_camera_full_history_ntfs.py -v -m slow --tb=short `
  --basetemp=software/runs/pytest-camera-full-history-20260912-05 `
  --junitxml=.codex-preserved/camera-full-history-20260912-05.xml
```

Executing production fingerprint is `a654894e…9898c` above. The full-history test
itself is unchanged from run 04, SHA-256
`623fae535135484c93fa118075fd02d88bd6752f122bda05e3090c6f77fbeb06`.
No source, configuration, native runtime or test-input edits are allowed during
the run. Documentation work does not rebind its source or originals.

Terminal result: **1 failed, 7 deselected, 2,050.25 s (34:10)**. All original readback,
native-byte verification, global/sibling audits, capacity, leases, deadlines,
supervisor, result logging and export verification stay in the production path.
Source identity in the isolated fixture and physical/process observations remain
explicitly modeled. Actual hardware-query and process-owner capability is absent.

### Terminal artifacts and failure

- JUnit suite time: 2,050.206 s; JUnit SHA-256:
  `d4146c15593f2100c932a683399cd7eae33694c15cc0700a10c8443ddccac4b8`.
- Checkpoint:
  `software/runs/pytest-camera-full-history-20260912-05/test_full_original_history_reo0/camera-full-history-checkpoint.json`.
  SHA-256 `545af41be141e1fcada82e45724e897ad93a909a049c4affd8a13b206eec3c6d`.
- Production fingerprint was rechecked unchanged after termination. The same
  full-history test-file SHA above was used; no run inputs changed in progress.
- Probe operation `operation-9ae2555970694f84a9022d5aaecf92b6` failed with
  `CAMERA_ATTEMPT_NOT_KNOWN`. Attempt
  `attempt-ce45d4ededc249a1908b30ff935d006e` is `SEALED_UNCERTAIN`, quarantined,
  without native accounting and with automatic replay disabled. Original
  supervision reports `ADMISSION_DEADLINE_EXPIRED`, `release_check_passed: false`.

The four-phase USB history, public review/reopens and fresh metadata completed.
Camera refresh (49.250 s), preparation (107.125 s) and review (119.407 s)
succeeded. Settings staging/capture, camera exact-attempt exports and the final
post-capture readback/lease checks were **not reached**. Checkpoint `completed`
and camera `exports` are empty. Earlier USB exports are not camera acceptance.

The total supervisor interval is 4.125 s. Its begin revalidation precedes the
admission window and must not be added to that window. The trace has 940
completed spans, zero unfinished/dropped spans and zero observer errors.

| Same final-release observation | Run 04 | Run 05 |
| --- | --- | --- |
| Parent `check_release` | 2,031 ms | 1,969 ms, still rejected |
| Consumed-permit revalidation | 1,969 ms | 1,890 ms |
| `_fresh_admission` | 1,860 ms | 1,765 ms |
| Coherent runtime observation | 687 ms | 640 ms |
| First original guard | 485 ms | 422 ms |
| Final original guard | 453 ms | 437 ms |

These are inclusive nested observations, not additive exclusive costs or a
controlled cross-run benchmark. Run 05 also contains a 2.172 s fresh-admission
sample elsewhere in the probe. A good median alone cannot authorize release.

The trace observes **46 ms between `begin` returning and `check_release`
starting**, then the 1,969 ms release call: 2,015 ms between the traced returns.
The unchanged 2,000 ms limit covers startup/READY **and** final revalidation,
not just the callback. This explains why a callback below two seconds still
fails. Exact internal admission-deadline/check timestamps were not retained;
the measured spans are not an exact slack measurement. The authoritative
outcome is the actual deadline rejection, not an estimate from these spans.

Run 05's overall elapsed time is shorter than run 04, but ordinary host load,
retained bytes and profiling overhead prevent attributing the entire difference
to this patch. No competing test suite ran during run 05. Documentation and
read-only dependency/event inspection overlapped earlier phases; additional
local commands were avoided during the late camera startup sequence.

### Next diagnostic improvement

After run 05 terminated, the fast profiling test was expanded to construct four
and eight prior **incapable camera-contract** campaigns through production
coordinator/persistence methods, then add the 70-package file history. Every
prior worker reports zero device effects; terminal records and attempt heads
are read back normally. It records actual record count/bytes and attempt events.
No run-05 original, permit, receipt or snapshot is imported into these fixtures.

This isolates growing record/ledger costs without the complete slow semantic/UI
predecessor. It still is **not** the mixed USB/camera family or genuine-original
acceptance path, nor a substitute for parent startup/READY timing. Source facts
and semantic original authentication remain modeled, and sibling sessions are
absent. Profile those missing dimensions before making a broad performance claim.

The next production optimization must be selected from this more representative
profile and preserve every predicate and independent observation boundary. Do
not launch another full-history run merely hoping host variation yields a pass;
do not increase deadlines or reuse a failed attempt. No second production patch
was made after run 05's failure.

### Expanded profiler result and next bounded ticket

The four-case expanded suite **passed in 348.30 s** after run 05 terminated.
JUnit: `.codex-preserved/camera-reader-campaigns-20260912-01.xml`, SHA-256
`96e54cbe65377c2e1476dea7bc90aa642bad85ec6a91dab2e0734f33abd47947`.
Its test-file SHA-256 is
`ddaa7fd9de8a9962b7b3d928e38fddca8144de167581fda131ad312d558806d2`.
Four JSON profiles are retained under
`software/runs/pytest-camera-reader-campaigns-20260912-01`.

| References | Prior campaigns / records / events | Record bytes | Three uninstrumented callback samples |
| --- | --- | --- | --- |
| 4 | 0 / 0 / 0 | 0 | 248.587 / 240.839 / 279.897 ms |
| 70 | 0 / 0 / 0 | 0 | 740.488 / 753.573 / 755.824 ms |
| 70 | 4 / 20 / 20 | 29,192 | 1,806.342 / 1,830.679 / 1,718.329 ms |
| 70 | 8 / 40 / 40 | 58,384 | 2,658.968 / 2,577.352 / 2,446.158 ms |

The same-source zero-campaign cases are slower than the earlier optimized
profile. Host/runtime variance is material; neither comparison isolates its
cause, and elapsed-time thresholds are deliberately not asserted by these tests.
Passing means equivalent callback results and valid newly built histories,
**not** passing the startup deadline. Record growth is an important additional
dimension; the eight-campaign samples already exceed two seconds without parent
startup/READY work.

The eight-campaign instrumented callback performs 1,028 bounded file reads,
39,780 `nt.stat` calls and 1,772 `safe_root` calls. `nt.stat` accounts for about
1.18 s exclusive time within the 3.26 s instrumented callback. Three family
audits take 1.67 s inclusive, containing many of those same operations. Those
spans must not be added together. Buffer allocations remain one per small-file
read, totaling 67,371,008 cumulative bytes; the optimization remains active.

The latest selection is **681 cases**: 677 non-profiling regressions plus these
four profiling cases. Two replace the earlier profiling cases; do not add all
four to 679. The production fingerprint remains `a654894e…9898c`.

Next ticket, before another long acceptance run:

1. Attribute metadata-call counts to ledger publication, evidence verification
   and directory enumeration separately. Inspect `read_bounded` / `_existing_root`
   in `physical_onboarding_storage.py` and `safe_root` / `contained_path` /
   `_read_regular_file` in `physical_onboarding_durability.py`. Repeated calls
   are candidates for investigation, **not** proof that observations are redundant.
2. Write an explicit before/after predicate and observation-boundary map for any
   proposed change. Preserve independent global/selected snapshots, both original
   guards, all record audits, fresh opens and native-handle validation. A cached
   root/path approval across reads or callbacks is not this ticket's scope.
3. Cover the changed primitive with fault tests for missing/replaced components,
   nonregular files, links/reparse points, containment, IO errors and late
   substitutions. Verify behavior, not only lower call counts. Do not convert
   separate checks into one observation without a reviewed equivalence argument.
4. Re-profile new zero/four/eight-campaign stores and a representative mixed
   USB/camera history; account for source checks, siblings and parent startup.
   Only a justified improvement with unchanged regressions merits a new complete
   original-history run. Preserve the two-second window and failed-attempt
   quarantine; do not optimize for one lucky timing sample.

No metadata-check optimization has been implemented here. This ticket and the
expanded profiler are the handoff for the still-incomplete P1 package.

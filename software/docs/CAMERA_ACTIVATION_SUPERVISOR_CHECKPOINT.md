# Camera v2: live process supervisor and retained diagnostics

Date: 2026-09-10. **Internal lifecycle implemented and tested.** It is not yet
the admitted physical camera/UI route. This advances the
[record/accounting checkpoint](CAMERA_ACTIVATION_EVIDENCE_CHECKPOINT.md) toward
the full [camera/arm application goal](ONBOARDING_APPLICATION_COMPLETION_MATRIX.md).

## Implemented connection machinery

`providers/windows/native_camera_activation_supervisor.py` joins the installed
preparation, parent handshake, Windows process owner and v2 run-record builder.
It does actual lifecycle work when explicitly invoked, rather than only
constructing packets or accepting a caller-supplied success result.

The exact-preparation entry `ActivationProcessSupervisor` is one-use, including
after denial or Stop. Construction/status are inert. Its `run` accepts only the
original deadline and cancellation event: no executable, argument-list, backend,
retry or fixture switch is exposed by that entry. It uses the preparation's
exact registration and returns an immutable `ActivationSupervision` outcome.

Execution owns the existing shared process reservation through pinning, startup,
REQUEST/READY/RELEASE, result delivery, cleanup and observation capture. It uses
the exact v2 pipe-only Windows owner, retaining the shared suspended creation,
atomic Job/handle restrictions and finite pipes. The installed parent checks the
whole preparation/current consumed-scope callback after pinning and immediately
before release delivery. Stop, failed scope checks, wrong PID, changed inputs,
bad output, deadlines and interruption cannot become a successful connection.

The scope callback is **not a permission issuer**. The production application
still must supply it from the actual consumed M1 scope, complete current original
records and independently reviewed runtime. A no-op lambda is a test fixture,
not a commissioning authorization. This component does not replace those owners.
No current UI action or scoped physical campaign calls the new supervisor yet.
The existing application and legacy runner physical holds were not changed.

## Failures, cleanup and retained bytes

The outcome preserves both pre-cleanup and post-cleanup observations. A property
that becomes unavailable later cannot erase the earlier bytes, or make them
appear to be a post-cleanup success. Unknown observations remain unknown.
Process cleanup and native camera cleanup remain distinct.

Final review added an interruption guard around post-cleanup observation
decoding, plus a `finally` fallback retaining any still-uncertain owner if an
unexpected diagnostic/retention exception escapes. A failed report-construction
path must not release the shared reservation and lose pending process storage.
The outer campaign still needs to record an escaped failure when no outcome
could be returned; preserving the owner is not a successful report publication.

The shared unresolved-owner hold retains the actual process owner when cleanup
throws, returns malformed/failed data, exceeds its original limit, leaves live
resources or cannot establish their closure. A subsequent attempt cannot replace
that owner. Pending kernel I/O storage remains alive with it. A Stop request or
process termination is not a claim that a camera driver is quiescent, and it is
not a robot emergency stop or observation of de-energization.

Original process limits are held separately from the registration handed to the
owner. Detected input drift cannot extend cleanup from its original two seconds
or alter observation byte limits. Cleanup is also capped by the original parent
deadline. If the clock fails, the last genuinely observed tick is used as a
no-wait cleanup boundary; no new current time or lifetime is invented. Clock
failures and cleanup exceptions remain explicit diagnostic failures.

`outcome.run_evidence(prepared)` converts only an outcome whose **actual executed
registration** exactly matches the expected preparation. It supplies the final
observation to the existing v2 record verifier. `outcome.diagnostics()` preserves
the additional before/after detail under a separate 1 MiB ceiling. Neither
projection performs file/device access or grants authority.

The detailed projection includes private paths and exact pipe bytes; it is not
an ordinary UI status object. The future original-store/export join must retain
this detail and apply the existing privacy/export policy. Do not send its raw
base64 buffers through a public summary or assume key-name redaction is enough.

## What actually ran

Unit tests model the owner while using the real installed parent, supervisor and
record codecs. An autouse guard forbids real owner construction. Final unit
coverage includes 55 cases for successful probe/capture, one-use entry, both
scope checks, Stop before/after delivery, partial output, malformed result,
constructor/pin/start/poll interruption, cleanup failure, missing attributes,
clock failures, original limits and the shared reservation/uncertainty hold.
Only explicitly modeled owners are cleared by unit-test teardown; a real
uncertain owner must never be discarded by such a fixture.

The native lane executes the **production lifecycle and real Windows owner**
with the same fixed camera-incapable helper used in previous checkpoints. Twelve
probe/capture exchanges cover success, changed driver, query exception, late
metadata, gate-not-started and failed native cleanup. Eight further exchanges
deny/cancel at begin or immediately before release. Denied attempts write no
release. Process/Job/PID, pins, pipes, clocks and process cleanup are real; camera
identity/effects/native cleanup, post-start native timing, modes/frame metadata
and current-scope permission facts are explicitly **MODELED**.

The private test core receives the helper's actual fixed registration, and every
test saves that registration with its observations before outcome assertions.
The physical v2 record converter rejects these outcomes because the helper's
registration is different. No camera, arm, pixel file or capture-capable native
worker is accessed by this native lane. The fixed helper is not an installed
or qualified physical runtime.

## Verification record

Reports are retained under `.codex-preserved`, without overwriting earlier runs:

| Report | Result | Scope |
| --- | --- | --- |
| `activation-supervisor-20260910-01.xml` | 39 passed, 4.28 s | Initial modeled lifecycle/retention cases |
| `activation-supervisor-owned-20260910-01.xml` | 3 failed / 16 passed, 2.92 s | Test expected an unprefixed PermissionError label; existing safe labeling correctly retains `OS_ERROR:`. Denial and cleanup succeeded; corrected the assertions |
| `activation-supervisor-20260910-02.xml` | 70 passed, 8.20 s | Expanded 50 modeled cases plus all 20 real contained-process cases |
| `activation-supervisor-regression-20260910-01.xml` | 500 passed, 49.43 s | Pre-fallback 53 modeled/20 native cases plus selected records/accounting, parent, registration, shared owner, legacy runner and physical campaign regressions |
| `activation-supervisor-final-20260910-01.xml` | 75 passed, 8.55 s | Final 55 modeled/20 native cases, including interruption during final decoding/retention |
| `activation-supervisor-regression-20260910-02.xml` | 502 passed, 50.67 s | Complete selected lane rerun on the final interruption-fallback source |

Lanes overlap; do not sum them as unique tests. Targeted mypy passes the supervisor,
v2 evidence and application-accounting modules. Black passes the three changed
source/test files. These checks are not repository-wide or hardware qualification.
The initial reports precede the final original-limit capture refinement; their
failures were not overwritten or relabeled as passes.

Application source initially changed from
`7cdc259eff441b34123c1448824214f40e85426416b0d90eedc305b62af59228` to
`75d8260da9fe7fe61b3d40fb10368794f358ea9a7f962b48c71bbc19b9d7f6ae`.
The final observation/retention interruption fallback changes it to
`f2cc4429a7ec69123fe3c20b17d76fbf705c143a9a939e4ff72b6a1e71043b7d`.
Installed native worker source remains
`0bc84f21e99d1d72eb7bc4a4969945016c7593247e67bf586f14101f59e298be`.
Fixed incapable helper hash remains
`577b57491a6d7e3c7a3b9081bda05be849db3725dce881b913d46e7c41312889`.
Neither native source nor helper was rebuilt/repinned. Earlier full public NTFS
acceptance belongs to its original source; that long test was not rerun here.

## Next production join: concrete constraints

1. **Retained camera execution contract.** The current coordinator's
   `MAX_RETAINED_CAMPAIGN_BYTES` is 128 KiB for an entire campaign, while the new
   v2 run record allows 512 KiB and the private supervision detail allows 1 MiB.
   Add a closed camera-specific successor with explicit total/artifact limits
   and corresponding original-store readers. Do not silently truncate details,
   drop the pre-cleanup observation or globally raise historical USB/v1 limits.
2. **Unknown counts.** `WorkerReceipt` still expects integer I/O counts. The core
   already has a USB-only `RetainedUncertainCampaignExecution` path; use its
   evidence-first/uncertain pattern for a separately bound camera successor.
   A missing native receipt must be durably diagnosable without a fake zero-count
   `WorkerReceipt` or throwing away the failed campaign's returned evidence.
3. **Admitted native runtime and campaign.** Install/review the v2 worker at the
   new purpose-specific paths, construct current camera facts from the complete
   original history, own output directories, consume the exact M1 permit and
   connect the supervisor's revalidation callback to that still-active scope.
   Existing `_denied_facts` and the legacy scoped campaign are not that join.
4. **Original stage/UI/export integration.** Extend stage-5 originals with a
   closed acquisition successor; preserve the accepted v15 entry and old bytes.
   Connect finite probe/capture, Stop, verified frame ingestion, actionable
   summaries and existing export/reopen workflows. Only then continue installed
   optics/placemat calibration and the separate arm startup/feedback workflow.

The confirmed export parent is
`C:\Users\Jack\Desktop\robot-arm-build\software\runs\wizard-exports`.
No new export system or automatic hardware action is introduced here.

The [final verified snapshot](../runs/wizard-exports/developer-checkpoint-camera-v2-supervisor-20260910-02/README.md)
contains 997 copies / 20,672,176 bytes, independently rehashed with zero mismatches.
All 374 copied application inputs reproduce the final `f2cc...` fingerprint, and
99 native process observations retain all five overlapping runs. Both launcher
modes were rechecked on that final source: zero operations, both devices
disconnected, physical authority false and the confirmed export parent. Initial
snapshot 01 remains intact at the earlier `75d8...` source without the final
fallback. The archived checkpoint omits only this post-seal navigation paragraph.

Reproduce the modeled lane from the workspace:

```powershell
.\.venv\Scripts\python.exe -m pytest software/tests/unit/test_native_camera_activation_supervisor.py -q --tb=short
```

The real contained-process lane is
`.codex-preserved/camera-activation-identity-draft-20260910-01/test_camera_activation_supervisor_owned.py`.
It requires the original fixed development helper/source pins. Use a fresh
pytest `--basetemp` and report path; never repoint it at a physical worker.

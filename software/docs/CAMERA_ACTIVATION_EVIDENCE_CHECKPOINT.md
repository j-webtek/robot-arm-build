# Camera v2: retained observations and application accounting

Date: 2026-09-10. **Installed and tested component, not a released physical
connection.** This follows the [parent/process checkpoint](CAMERA_ACTIVATION_PARENT_CHECKPOINT.md).
The [completion matrix](ONBOARDING_APPLICATION_COMPLETION_MATRIX.md) still governs
the full camera/arm wizard; the physical supervisor/campaign/original-store/UI
join remains unfinished.

Follow-up: the [owned process supervisor](CAMERA_ACTIVATION_SUPERVISOR_CHECKPOINT.md)
now implements the lifecycle that produces these records. Its actual contained
tests remain distinct from hardware/M1 qualification, and the campaign/original
storage/UI connection is still unfinished. This checkpoint retains its own
historical source and test scope.

## Installed behavior

| Component | Responsibility |
| --- | --- |
| `providers/windows/native_camera_activation_observations.py` | Read an existing owner's available attributes once per field; explicitly distinguish unavailable, invalid and observed values |
| `providers/windows/native_camera_activation_evidence.py` | Retain one bounded v2 run record and independently reconstruct its exact REQUEST/READY/RELEASE/result binding when reopened |
| `application/native_camera_bounded_effect.py` | New v2 accounting function maps the verified record into the existing application effect model, using independently retained invocation context |

The legacy v1 evidence schema, 128 KiB ceiling and assessment entry point remain
unchanged. The new record has a separate 512 KiB ceiling so it can retain the v2
transport's full 256 KiB stdout and 8 KiB stderr as base64, along with preparation
and finite diagnostic metadata. The result exists once in stdout, not again as a
stored decoded copy. No process limit or device budget was raised.

Every owner field explicitly records availability. A failed property read does
not become `false`, an empty pipe or zero resources. An observed `returncode=None`
(the owner has not observed exit) is different from an unavailable exit-code
property. A truncated observed buffer records its exact retained bytes/hash and
the amount omitted from **that in-memory buffer**; it cannot account for bytes the
child/driver never delivered. All of these records are diagnostics, not an atomic
kernel snapshot or proof of original-store provenance.

The record retains original start/finish/parent-deadline values when available,
cleanup attempt/return/timing/error availability, exact handshake bytes and the
live parent's accepted-result digest. Reopening does no file, camera, process,
clock or pixel access. It requires independent expected preparation and evidence
digest and re-parses the complete v2 native result rather than trusting stored
success Booleans. A self-consistent hash alone is not provenance or permission.

Native result validation and process cleanup are separate. A valid native
receipt can remain useful after Stop or failed process cleanup without producing
a successful run. Unknown native counts stay `None`, including pre-owner holds;
the new application function does not synthesize zero effects. Native source
cleanup does not prove that a camera driver is quiescent or that robot power is off.

The new application function also checks the independently retained invocation
start/deadline and campaign duration. The outer interval includes file pinning
before the native lifetime reservation: it is not incorrectly constrained to
the shorter native/run reservation. The live supervisor must still enforce every
original admission, run and cleanup deadline. Cleanup before the recorded start,
missing completion clocks, or a created process with zero observed peak processes
cannot become successful accounting.

## Developer integration contract

Use `capture_activation_owner(existing_owner, prepared.registration.budget)` at
the actual supervisor boundary, then `retain_activation_run(...)`. Do not fill
unavailable clocks, return values, pipe bytes or cleanup results with defaults.
The future supervisor must separately keep any uncertain owner and pending
buffers alive under the existing shared cleanup hold; a JSON record does not
own or clean up native resources.

Reopen using `verify_activation_run(record, expected_preparation=original,
expected_evidence_sha256=original_digest)`. For application accounting call
`assess_activation_camera_bounded_effect` with independently retained start,
deadline and registered campaign duration as well. `CONFIRMED` means only that
the reported bounded effect meets these checks; it does not qualify the runtime,
approve a stage, verify captured pixels, or authorize later commands.

This record binds the exact physical-candidate registration in its preparation.
It must **not** be used to label the development helper's different test-only
registration as a physical run. All new evidence/accounting tests use explicitly
modeled owners/receipts. Existing real Windows incapable-child tests remain a
separate lane with their own correctly labeled process observations.

## Verification

Reports are under `.codex-preserved`, without overwriting preceding attempts:

| Report | Result | Scope |
| --- | --- | --- |
| `activation-evidence-20260910-01.xml` | 1 failed / 81 passed, 8.46 s | Test supplied 9,100 stderr bytes while claiming it was below 8 KiB; collector correctly truncated. Corrected test data, unchanged cap |
| `activation-evidence-20260910-02.xml` | 82 passed, 8.31 s | New pure record/observation validation |
| `activation-evidence-20260910-03.xml` | 108 passed, 10.89 s | Final 88 observation/evidence and 20 application-accounting checks |
| `activation-evidence-regression-20260910-01.xml` | 653 passed, 41.78 s | Final v2 code plus selected legacy codecs, parent, runner, physical campaign, process, USB and host-boot regressions |
| `activation-evidence-export-native-20260910-01.xml` | 118 passed, 10.31 s | Legacy effect accounting, existing wizard export and 22 real pinned/Job-contained incapable-child exchanges |

Lanes overlap; do not sum them as unique tests. Targeted mypy passes all three
production modules; Black passes the five changed source/test files. Initial
mypy issues from a local inferred value type were fixed with an explicit `Any`
annotation; no type checks or effect checks were disabled.

Both launcher modes pass `-Check` with zero operations, camera/arm disconnected,
physical authority false and the confirmed export parent. Those checks do not
start a browser/server or connect a device. No camera/arm hardware or capture-capable
worker was accessed. The new v2 record/accounting tests do no pixel I/O; existing
regressions may use their synthetic filesystem fixtures. The real process lane uses the unchanged fixed
incapable helper, SHA-256
`577b57491a6d7e3c7a3b9081bda05be849db3725dce881b913d46e7c41312889`.

Application source changed from
`b639a48664cc8502c38f568459aaaee7c8ffbab5d797673ae96a076402d107bd` to
`7cdc259eff441b34123c1448824214f40e85426416b0d90eedc305b62af59228`.
Installed native worker source remains
`0bc84f21e99d1d72eb7bc4a4969945016c7593247e67bf586f14101f59e298be`.
The long full public NTFS original-history acceptance was not rerun on this
source. Earlier accepted originals belong to their own unchanged fingerprints.

## Continue from here

1. Join v2 observations/retention to the live owned supervisor, retaining actual
   failure/cleanup state even when no complete native result arrives. Keep
   development fixture registrations separate from physical candidates.
2. Update the scoped campaign and retained execution contract for unavailable
   native counters; the legacy `WorkerReceipt` currently expects integer counts.
   Do not hide that gap by inserting zero counts or dropping the failed attempt.
3. Install/review the v2 native runtime and derive current camera admission facts
   from the complete original setup records, active leases and consumed permit.
   The current physical runner and `_denied_facts` path remain held/unfinished.
4. Add the closed stage-5 acquisition successor, then connect explicit finite
   probe/capture, Stop, verified image ingestion and the existing UI/export path.
   Retaining a new run record alone cannot advance the v15 entry layout.

The export parent remains
`C:\Users\Jack\Desktop\robot-arm-build\software\runs\wizard-exports`.
Use the existing wizard exporter for operator diagnostics; this developer
checkpoint is not a second production export system or commissioning approval.

The [verified developer snapshot](../runs/wizard-exports/developer-checkpoint-camera-v2-evidence-20260910-01/README.md)
contains 917 copies / 19,255,906 bytes, independently rehashed with zero
mismatches. Its 373-input application snapshot reproduces the final source
fingerprint. All 22 new incapable-process observations and the initial failed
test report are retained. The archived `CHECKPOINT.md` is the pre-seal version
without this subsequent archive-navigation paragraph.

Focused reproduction from the workspace:

```powershell
.\.venv\Scripts\python.exe -m pytest software/tests/unit/test_native_camera_activation_evidence.py software/tests/unit/test_camera_activation_bounded_effect.py -q --tb=short
```

For preserved test runs, supply a fresh `--basetemp` and report path. Never retry
or overwrite an original failed setup attempt to turn its history into a pass.

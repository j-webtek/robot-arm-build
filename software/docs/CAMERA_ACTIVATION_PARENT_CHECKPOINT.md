# Camera v2: preparation and owned-process parent integration

Date: 2026-09-10. **Installed preparation/parent/transport code; physical dispatch
remains unfinished and disabled.** This follows the
[installed wire codecs](CAMERA_ACTIVATION_RESULT_CHECKPOINT.md), not a new reduced
application goal. The [completion matrix](ONBOARDING_APPLICATION_COMPLETION_MATRIX.md)
still governs the full camera/arm wizard.

Follow-up: [v2 run evidence and application accounting](CAMERA_ACTIVATION_EVIDENCE_CHECKPOINT.md)
are now installed and tested. The live supervisor/campaign/original-store/UI join
remains incomplete; this checkpoint retains its own historical test/source scope.

## What changed

| Component | Installed change |
| --- | --- |
| `native_camera_activation_registration.py` | Complete v2 preparation binds logical probe/capture intent, expected camera traits, source, runtime candidate, helper/build pins, session/attempt/permit, assigned directory and exact budgets |
| `native_camera_parent_admission.py` | The existing one-use parent accepts the new exact preparation type, rechecks the entire consumed-scope binding, validates READY against the owned PID, uses v2 RELEASE/result codecs and preserves old v1 behavior |
| `_owned_worker_win32.py` | Adds an exact camera-v2 pipe-only transport class using the existing suspended creation, atomic Job/handle assignment, file/directory pinning, finite pipes and cleanup implementation |

No native camera source, old runtime manifest, runtime trust pin, physical
dispatch hold, original-store codec or UI action was changed. The v2 native worker
itself remains a compiled draft, not an installed/qualified runtime. New runtime
candidate paths are purpose-specific (`build-owned-activation-probe` and
`build-owned-activation-capture`); no file is created or trusted by preparing one.

The candidate is explicitly `BUILD_REVIEW_REQUIRED`. It has no authority to run.
A caller cannot turn it into approval by setting `dispatch_enabled=true`,
repointing a helper, substituting a legacy manifest or supplying an arbitrary
argument list. The remaining build-review owner must independently verify the
current expected runtime, not learn trusted hashes from whatever is installed.

## Binding, time and process behavior

Preparation reconstructs the existing logical camera plan and checks its full
data/arguments, not just an echoed digest. Probe and capture use separate fixed
runtime paths and v2 request schemas. The capture directory must be exactly
`<assigned working directory>/capture-<attempt id>`; preparation never creates it.
The whole preparation is revalidated before REQUEST and immediately before the
release WriteFile. A callback must return `None`; a Boolean is not approval.

Probe has a 10 s run / 2 s cleanup budget, capture 15 s / 2 s. The original native
operation remains 5 s, with admission 2 s for probe or 5 s for capture. Full
remaining lifetime is checked before launch and release. Delays, clock reversal,
Stop, changed input and denied current scope make that handshake non-retryable.

Both purposes are limited to one process. Complete stdout is bounded to 256 KiB,
including READY and result together; stdin is 17 KiB and stderr 8 KiB. The parent
also enforces the combined stdout cap during result reconstruction. No shared
process cap was raised. Oversized combined output is a failed observation, not
an instruction to discard fields or silently retry.

Only the exact `WindowsOwnedCameraActivationPipeProcess` class uses the detached
console choice. Legacy camera owners and derived classes retain their previous
policy. Microsoft distinguishes console detachment from suspended creation and
Job breakaway in its [process-creation flag documentation](https://learn.microsoft.com/en-us/windows/win32/procthread/process-creation-flags).
The new class retains suspended creation and atomic Job assignment and never
adds breakaway. Native tests confirmed one observed Job process; this observation
does not qualify a received camera's driver/helper-process behavior.

## Real Windows test boundary

The new developer test uses the **installed parent and real pinned Windows process
owner**, with a fixed camera-incapable native result helper. It is not a new public
runner option. Its test-only registration uses a fixed executable/source list and
allows only six modeled scenarios. It does not substitute this registration into
the physical application path or claim an M1 permit was consumed.

For both probe and capture, 12 exchanges cover success, changed driver, query
exception, late metadata, failure before the gate and failed native cleanup.
Ten additional tests cover Stop/denial at begin or final release and mismatched
owned PID. Failed final checks produced READY only: no release bytes were written.
The actual owned child was terminated/drained and resources closed. Failures before
begin created no process. In all runs the shared unresolved-owner hold remained
empty; uncertain owners would be retained rather than discarded.

File pins, process/Job membership, PID, pipes, byte counts and process cleanup are
real. Camera identity, native post-start timing, camera effects/cleanup and frame
metadata are **MODELED**. No camera, arm, capture directory or pixel file was
accessed. A denied run retains `native_camera_result=null`, not fabricated native
zero-effect success. Process cleanup is not a robot emergency stop or proof of
camera-driver cleanup on received hardware.

## Verification record

All reports below are under `.codex-preserved` and preserved without overwriting:

| Report | Result | Scope |
| --- | --- | --- |
| `activation-preparation-20260910-01.xml` | 2 failed / 120 passed, 4.15 s | Test construction error: a changed endpoint kept the old endpoint hash and was rejected before the intended assertion; corrected fixture, unchanged guard |
| `activation-preparation-20260910-02.xml` | 122 passed, 3.99 s | v2 preparation/shared parent plus legacy parent checks |
| `activation-owned-exchange-20260910-01.xml` | 12 passed, 2.23 s | Real pinned Job/pipe exchange with incapable helper |
| `activation-owned-exchange-20260910-02.xml` | 22 passed, 2.73 s | Above plus actual Stop/denial boundaries |
| `activation-parent-regression-20260910-01.xml` | 420 passed, 13.58 s | Selected new and legacy camera, parent, runner, host-boot and USB accounting coverage before the final combined-output-cap assertion |
| `activation-transport-regression-20260910-01.xml` | 123 passed, 18.10 s | Creation-flag inspection, shared process owner, retained legacy capture and logical physical campaign tests |
| `activation-parent-final-20260910-01.xml` | 149 passed, 7.08 s | Final v2 preparation/combined-output cap, flag policy, legacy parent and all 22 actual owned exchanges |

Lanes overlap; do not sum them as unique tests. Targeted mypy passes the three
production modules, and Black passes all six changed source/test files. These
are not repository-wide or received-hardware qualification claims. Native helper
hash remains `577b57491a6d7e3c7a3b9081bda05be849db3725dce881b913d46e7c41312889`;
it was not rebuilt or repinned during this increment.

Application source changed from
`809c8510f383f748905f7117e5e86e19adfd02efd1679f856b24e5237c6ae262` to
`b639a48664cc8502c38f568459aaaee7c8ffbab5d797673ae96a076402d107bd`.
Installed native worker source remains
`0bc84f21e99d1d72eb7bc4a4969945016c7593247e67bf586f14101f59e298be`.
Earlier checkpoints and full NTFS acceptance belong to their original source
fingerprints; the long public original-history acceptance was not rerun here.

## Reproduce and continue

The [verified archive](../runs/wizard-exports/developer-checkpoint-camera-v2-parent-20260910-01/README.md)
is in the confirmed workspace export folder: 947 copies / 19,463,795 bytes,
independently verified with zero mismatches. The 371-input application snapshot
reproduces the final source fingerprint, and 56 real process-observation files
preserve initial/expanded/final test runs. Both launcher modes were rechecked:
zero operations, both devices disconnected, physical authority false and the
confirmed export directory. Earlier checkpoints were not overwritten.

```powershell
.\.venv\Scripts\python.exe -m pytest software/tests/unit/test_native_camera_activation_registration.py software/tests/unit/test_native_camera_activation_transport.py software/tests/unit/test_native_camera_parent_admission.py -q --tb=short
```

For the separately built, pinned incapable helper, run
`.codex-preserved/camera-activation-identity-draft-20260910-01/test_camera_activation_owned_exchange.py`
with pytest and a **new** `--basetemp` directory. Each actual owned exchange saves
its observations there even when an assertion fails. It requires the original
fixed development helper and source pins; it is not an operator runtime setup.

The next production join remains substantive:

1. Extend native run evidence/retention and the scoped campaign to v2 without
   coercing v2 observations into v1 or inventing missing process observations.
   `OwnedNativeCameraRunner` still accepts only legacy preparations and is held.
2. Install/review the new native runtime, derive current camera facts from the
   complete original setup records, and join the active lease/consumed permit.
   `PhysicalCameraSession._denied_facts` is still an unfinished implementation.
3. Add the closed stage-5 acquisition successor so valid probe/capture records
   can be retained and reread without relaxing the accepted v15 entry layout.
4. Wire explicit finite acquisition into the existing service/Stop/image/UI/export
   workflow, then continue arm feedback/startup and installed calibration.

There is no new physical Connect button in this increment. This is verified
connection machinery for that route, not completion of the user-facing wizard.

# One-use guarded native probe runner

`providers/windows/owned_native_camera_runner.py` joins exact preparation,
parent handshake, inherited two-write pipes, owned Windows Job/process cleanup,
and immutable evidence. The public physical runner remains **unconditionally
held** before file inspection, DLL loading, owner construction or authorization.
No release flag, backend callback, caller-supplied executable or metadata approval
can enable it in this increment. Native capture is outside this probe-only scope.

## Public API

```python
runner = OwnedNativeCameraRunner(
    prepared_probe,
    revalidate_consumed_permit=check_current_consumed_scope,
)
runner.status()  # inert; includes the shared unresolved-process hold
result = runner.run(cancellation=stop_event, deadline_ns=original_deadline_ns)
# Today: HELD / PHYSICAL_PROVIDER_QUALIFICATION_HELD, no owner constructed.
```

`run` is one-use, including pre-dispatch denial. It returns the immutable,
canonical-bytes-backed `OwnedNativeCameraRunEvidence`. Construction, status and
preparation do not read files, open devices or implicitly dispatch. No directory
is created by this runner; the coordinator assigns and creates the exact empty
working directory within its retained attempt before calling it.

The future qualified application adapter must compare a current **already
consumed** coordinator permit against the complete supplied
`PreparedOwnedNativeProbe`: session/attempt, full campaign registration and
operation hash, workspace source, selected endpoint and selected-identity hash,
runtime/helper/build-record pins, exact working directory and all budgets.
It must retain the original cancellation event and parent deadline, verify
current leases/source/permit scope, and never redeem/renew the permit again.
The callback receives a fresh exact preparation and must return `None` or raise.
Returning a Boolean does not grant authority. Providers deliberately do not
import the application coordinator or own its persistence lifecycle.

## Finite shared lifecycle

The implemented supervisor reserves the same process-wide admission lock as
`OwnedWindowsWorker`, pins the exact files/directory, and then calls
`NativeCameraParentHandshake.begin`. Before create/resume/initial input it checks
the original preparation, registered arguments/budgets, cancellation and time.
READY must be a single bounded first line with no result bytes before release,
and must bind the actual owned child PID and exact request. The final
`send_final_input` check calls the handshake's current-consumed-permit recheck
directly at the WriteFile boundary. There are only REQUEST and RELEASE writes;
RELEASE completion closes stdin and the child requires EOF.

Admission and execution waits check deadlines/cancellation before and after
polling. A last poll or cleanup that returns late cannot produce success.
Cleanup has its own bounded deadline inside the original parent deadline. A
cleanup exception or unresolved resource does not erase the primary failure.
All uncertain owners remain referenced in-process under the shared private
`_DISPATCH_LOCK` / `_UNRESOLVED_BACKEND` ownership boundary, preventing loss of
pending OVERLAPPED buffers or a competing worker overwriting the retained owner.
This intentional private coupling must migrate atomically if the shared owner
module is refactored. No cleanup retry or automatic campaign retry is attempted.

## Closed hardware-incapable execution lane

```python
fixture = prepare_incapable_native_admission(prepared_probe)
runner = IncapableNativeAdmissionRunner(
    fixture, revalidate_consumed_permit=check_test_scope,
)
result = runner.run(cancellation=stop_event, deadline_ns=original_deadline_ns)
```

This separate exact type fixes the compiled
`rocell_camera_admission_entry_tests.exe` path/hash and its source/package pins.
It cannot accept arbitrary binary paths, hashes, arguments or backend objects.
The test executable links the actual admission entry/protocol, but no camera,
COM or Media Foundation implementation. Its completion is
`rocell.native_camera_admission_only_test.v1`, not a native receipt. It can produce
only `SUCCEEDED_ADMISSION_ONLY`, never native probe success or hardware readiness.
Changing the reviewed test build is a pin failure, not an automatic update.

## Retention and verification

`providers/windows/owned_native_camera_evidence.py` provides:

```python
owned = verify_owned_native_camera_run_evidence(
    retained_document_or_typed_evidence,
    expected_preparation_sha256=trusted_attempt_preparation_hash,
    expected_evidence_sha256=trusted_retained_evidence_hash,
)
document = owned.to_dict()       # fresh complete private evidence
summary = owned.safe_summary()  # no raw endpoint, challenge or pipe content
```

Both independently supplied hashes are mandatory. The verifier is pure: no file
reads, native libraries, worker replay, metadata inventory or device effects.
It verifies the full preparation/actual process registration, exact PID and
READY/RELEASE joins, raw result agreement, strict types/counters and domain.
Any native receipt is parsed separately through the existing strict probe parser.

Evidence has a 128 KiB JSON ceiling. It retains complete **available** stdout and
stderr bytes (base64, length and SHA-256), bounded to 32 KiB / 8 KiB, plus intended
READY/RELEASE bytes, actual written-byte count, process observations, original
deadline, elapsed time, handshake state, primary error and independent cleanup
errors. Message serialization is not delivery proof. A pipe overflow or killed
child can leave output unobserved: `capture_complete=false` and
`omitted_bytes_exact=null` explicitly avoid claiming an invented total or hash
of unread bytes. The Win32 owner's retained overflow prefix is preserved, not
silently presented as complete output. No binary camera frames are present.

Summary keeps `native_receipt_valid`, `native_cleanup_confirmed` and
`process_cleanup_confirmed` independent. Every report remains unqualified with
`physical_authority=false`, `hardware_qualified=false`, zero retries and final
power `UNKNOWN_REQUIRES_SEPARATE_OBSERVATION`. Job termination is not a camera
shutdown receipt, firmware observation or physical power measurement.

Tests in `test_owned_native_camera_runner.py` cover pure/injected adversarial
lifecycle and evidence cases plus the real, fixed **incapable** entry child.
They do not execute the device-capable helper, enumerate metadata, approve a
native catalog or remove the physical coordinator hold. Existing
`NATIVE_CAMERA_ADMISSION.md` remains the native parser/build contract.

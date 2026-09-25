# Arm feedback worker / non-purging native adapter

Status: implemented and tested through the **actual `ArmFeedbackWorker` and
sealed incapable Win32 facade**. This closes the worker/backend API gap; it does
not connect the physical arm or complete DEV-009. No serial device, native DLL,
power, motion, firmware or configuration change was used in the tests.

## Files and API

- [arm_nonpurging_adapter.py](../src/rocell/providers/windows/arm_nonpurging_adapter.py):
  closed backend, fixed-settings connection adapter and immutable native evidence.
- [arm_feedback_worker.py](../src/rocell/providers/windows/arm_feedback_worker.py):
  minimal exact backend registration and request/result hooks. Its existing
  authorization, identity, quiet-buffer, wire, timing and cleanup logic is reused.
- [test_arm_nonpurging_adapter.py](../tests/unit/test_arm_nonpurging_adapter.py):
  combined worker/native-owner tests and pure retained verification tests.

```python
backend = NonPurgingArmFeedbackBackend(reviewed_controller_binding, api=api)
worker = ArmFeedbackWorker(
    authorizer=exact_external_authorizer,
    identity_resolver=exact_identity_resolver,
    backend=backend,
)
result = worker.run(exact_request, cancellation=cancel_event)
native_evidence = backend.retain_evidence(exact_request, result)
```

Only exact `IncapableWin32SerialApi` or `WindowsNativeSerialApi` types are
accepted; subclasses, raw COM arguments, factories and generic providers are
not accepted. Omitting `api` selects the **held native composition**, not a
simulation fallback. Construction and status do no I/O. `require_available()`
reaches the unchanged unconditional native hold before authorization, object
creation, DLL loading or device access. There is no release flag or waiver.

The backend's admission is one-use, including rejection. The worker binds the
complete immutable request before its normal admission and seals the actual
result/native snapshot after its cleanup path. Request/controller mutation is
checked again before owner I/O. `create_closed()` cannot be used before that
admission or after consumption. Cleanup remains possible even after request
drift; a drift check must not prevent closing owned resources.

## Exact connection behavior

The private connection exposes only the attributes the existing worker needs.
It validates the reviewed COM endpoint and every fixed serial setting instead
of treating assignments as arbitrary options. All closed settings must be
provided before open. 115200/8N1, false RTS/DTR and disabled flow control are
unchanged. The native owner independently applies and reads back its DCB and
timeouts after `CreateFile`.

Those closed values are **requested settings**, not proof that control lines
were electrically false before opening. Open-time bridge/driver resets remain
unqualified. The adapter has no purge, flush, reset, home, torque, motion,
raw-command or retry route. At most the existing ten-byte T105 line can be
submitted once.

Read timeouts are finite floats between 1 ms and 1 s. Conversion floors to
whole native milliseconds, never rounding above the remaining budget. Less
than one native millisecond refuses submission. Native cancellation completion
has its existing separate bounded wait; that cannot retroactively turn a late
campaign into timely success. The worker and future isolated supervisor still
own the overall deadline.

Partial writes preserve the API-reported partial byte count so the existing
worker refuses them without submitting a remainder. A write completing late
after cancellation remains an uncertain failed operation even if the native
owner subsequently reports all ten bytes transferred. Port closure alone is
insufficient: remaining event handles or pending I/O make close fail, and the
worker retains the uncertainty.

## Immutable native evidence companion

`ArmNativeLifecycleEvidence` exposes `payload`, `evidence_sha256`, `to_dict()`
and `view()`. Its schema is `rocell.arm_native_lifecycle_evidence.v1`; canonical
payloads are capped at **32 KiB**, with rejection rather than truncation. It
retains complete native status, resource accounting, primary/cleanup errors and
up to 1024 late-read bytes as canonical base64, exact byte count and SHA-256.

The companion binds the exact request, reviewed controller, source, operation,
energy-envelope digest and **every field/raw byte of the actual worker result**
through its canonical result digest. It additionally retains worker response
and unexpected-byte hashes/counts, including the existing unretained count.
The ordinary response/boot bytes remain in the existing full feedback evidence;
this companion must never replace that evidence or silently discard it to meet
an aggregate retention cap.

```python
verified = verify_arm_native_lifecycle_evidence(
    payload,
    expected_request=original_request,
    expected_result=original_or_verified_restored_worker_result,
    expected_evidence_sha256=trusted_companion_digest,
)
```

Verification is pure: no file reads, provider calls, worker replay or repairs.
It checks exact schemas, bindings and native/worker byte and cleanup accounting.
Successful worker status additionally requires closed, error-free native state,
verified settings, one complete fixed write, no pending resources/startup/late
bytes, and exact successful worker counts. A changed native companion cannot
contradict the retained successful worker result merely by recomputing its hash.

`retain_evidence()` requires the exact completed result generated by this
backend, refuses result mutation/substitution and checks that native state has
not changed since completion. Returned documents are detached copies. `view()`
omits raw bytes, endpoints and driver exception text. It keeps native cleanup,
device-cleanup proof and final power separate; the latter remains
`UNKNOWN_REQUIRES_SEPARATE_OBSERVATION` and all authority/connection flags false.

## Remaining integration and acceptance

The adapter does not implement the isolated arm child/codec and one-use parent
redemption channel, Windows identity-to-opened-handle proof, physical M1
composition, manual energy ceremony or independent final power observation.
It does not alter the commissioned serial transport or its existing gates.
No current wizard action dispatches this adapter to physical hardware. Existing
legacy worker limitations still include the unreleased pySerial alternative;
the native companion names this adapter's distinct non-purging qualification
hold. Neither limitation list is a release decision.

The source-frozen focused lane contains **359 passing tests** across adapter,
worker, native owner, full feedback evidence and existing rehearsal campaign.
Coverage includes startup/late bytes, fixed settings, partial and late writes,
identity/request changes, pending cancellation, all handle-close failures,
deadline loss, raw evidence binding, false-success tampering and detached pure
restoration. Native DLL loading is forbidden in the adapter suite. These are
not actual process containment, M1 publication or received-hardware tests.

See [native owner](NONPURGING_SERIAL_BACKEND.md),
[worker protocol](ARM_FEEDBACK_WORKER.md),
[durable feedback composition](ARM_FEEDBACK_REHEARSAL_CAMPAIGN.md) and
[DEV-009 playbook](CAMERA_ARM_DEVELOPER_PLAYBOOK.md#dev-009--join-arm-identity-power-ceremony-and-feedback).

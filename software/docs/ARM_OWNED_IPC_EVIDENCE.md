# Contained arm feedback: IPC and retained evidence

This increment runs the existing fixed-T105 feedback worker through the
non-purging adapter in a contained, hardware-incapable child. The IPC and evidence
modules are pure: construction, parsing, verification and summaries perform no
file, process, DLL or device operations. Physical serial activation remains
independently held. This is not a motion, initialization, reset, raw-command or
power-control interface.

## Module ownership and integration

- `providers/windows/arm_owned_protocol.py` owns the exact request, child gate,
  READY/RELEASE bytes and complete result codec.
- `providers/windows/arm_owned_evidence.py` owns immutable, lossless process and
  nested feedback/native evidence, plus a raw-free display projection.
- `owned_arm_feedback_package.py` pins a closed development source closure;
  `owned_arm_feedback_runner.py` owns the child process, PID, pipes, deadlines,
  cleanup and live consumed-authorization checks. `_owned_arm_feedback_child.py`
  invokes the actual `ArmFeedbackWorker` with `NonPurgingArmFeedbackBackend` and
  the exact incapable Win32 API. These responsibilities are not replaced by the
  pure codecs.
- The application/coordinator retains the complete artifact before a known seal
  and independently handles any post-campaign final-power observation. A process
  exit or serial close is never an observation of de-energization.

The pinned package is `SOURCE_PINNED_DEVELOPMENT_NOT_TRUSTED_RELEASE`. Its observed
development `packaging` dependency version (26) is not a trusted-release or
hardware qualification, nor a guarantee for every version in the project's
broader supported dependency range. The package's exact file pins and original
request must be revalidated by the owner; hashes alone do not authenticate
arbitrary caller-supplied evidence.

## Exact one-shot handshake

1. The server builds `ArmOwnedRequest` from the original typed
   `ArmFeedbackCampaignRequest`, session, attempt, source, operation, permit,
   selected controller identity and worker-registration hashes. The original
   parent monotonic deadline is retained, not refreshed.
2. After pinning and live consumed-scope checks, the owner sends one canonical
   REQUEST line. The child constructs READY from its actual PID and a fresh
   random challenge. The parent validates READY against its owned PID and exact
   request hash.
3. Immediately before the second write, the owner revalidates the same consumed
   scope and lifetime. RELEASE echoes the exact request, READY, PID, challenge,
   permit and unchanged deadline. The pipe must then reach EOF.
4. `ArmOwnedChildGate.accept_release` consumes its one attempt before checking
   bytes, EOF and clocks. A malformed, stale or denied release cannot be retried.
   The original READY identity/challenge is read-only. Admission is at most
   5 seconds for new v2 requests, and the complete inner worker budget plus 2 seconds of cleanup
   must still fit the original parent lifetime.
5. Only the incapable origin may pass this gate. A physically sourced request
   has distinct provenance and can only yield a structured `PHYSICAL_HELD`
   result; it cannot enter the rehearsal feedback decoder or open a port.

The gate constructs/checks bytes; it does not establish an authenticated
operator, deliver RELEASE or authorize a worker by itself. Those facts belong
to the exact owned runner and coordinator scope. A monotonic timestamp is only
meaningful in the original host's live clock domain, not as a restart permit.

`rocell.arm_owned_request.v2` binds `admission_timeout_ms=5000`. New preparation
and the fixed child require v2. The pure decoder retains historical
`rocell.arm_owned_request.v1` with its original `2000` ms bound, and rejects
cross-version duration substitution. Historical evidence remains readable, not
re-executable. READY, RELEASE, result and evidence schemas are unchanged because
their exact request hash binds the version and timeout. The original 30-second
synthetic envelope, 20-second parent campaign, 5-second inner worker and
2-second cleanup are not renewed or enlarged. Native-camera limits are unchanged.

## Public pure APIs

```python
request = build_arm_owned_request(
    session_id=..., attempt_id=..., source_sha256=...,
    operation_sha256=..., permit_sha256=...,
    selected_identity_sha256=..., worker_registration_sha256=...,
    feedback_request=typed_request, provenance=..., scenario=...,
    parent_deadline_monotonic_ns=original_deadline,
)
ready = parse_arm_owned_ready(
    ready_wire,
    expected_request_sha256=request.request_sha256,
    expected_child_pid=owned_pid,
)
release_wire = arm_owned_release(request, ready)
result = parse_arm_owned_result(
    result_wire, expected_request=request, returncode=observed_exit_code,
)
evidence = retain_arm_owned_evidence(
    request=request, process_result=owned_process_result,
    ready=ready, release_wire=release_wire,
)
verified = verify_arm_owned_evidence(
    evidence.payload,
    expected_request=trusted_original_request,
    expected_evidence_sha256=trusted_retained_digest,
)
```

`ArmOwnedEvidence.payload` is immutable canonical bytes. `to_dict()` returns a
detached full private record; `request` returns the exact typed inner request;
`feedback` and `native` return the independently verified existing evidence
types or `None`. `safe_summary()` never exposes raw bytes, an endpoint, a command
line or arbitrary private error text. The complete artifact, not the summary,
is the evidence to retain and reverify.

The inner request is reconstructed by the existing `parse_arm_feedback_request`.
Full feedback evidence uses the existing strict rehearsal verifier, including
its T105/T1051 receipt checks. The native companion uses the existing exact
request/result-bound native lifecycle verifier. There is no second permissive
serial-response parser.

## Bounds and failure semantics

| Item | Maximum canonical/raw bytes |
| --- | ---: |
| Original request, excluding its single LF | 60 KiB |
| READY or RELEASE, excluding its single LF | 2 KiB |
| Inner feedback line/retained unexpected input bound | 2,048 |
| Complete child result, excluding its single LF | 48 KiB |
| Entire observed stdout, including READY and result | 64 KiB |
| Entire observed stderr | 8 KiB |
| Complete retained artifact, including base64 and nested records | 128 KiB |

These are independent limits, not a promise that all maxima fit simultaneously.
The final 128 KiB aggregate is checked after lossless serialization. Oversize
refuses retention; the caller must hold/mark uncertainty, never trim records to
promote a campaign to known success. Original observed bytes, counts and errors
remain the process owner's responsibility if artifact creation fails.

A measured nominal pure fixture using the actual worker produced a 3,274-byte
request, 12,376-byte result wire, 8,301-byte full feedback record, 3,651-byte native
companion and 34,679-byte complete artifact. These sizes are fixture evidence,
not a bound for every failed campaign.

Exact stdout/stderr are retained as base64 with byte counts and SHA-256 hashes.
The complete native and feedback records are also independently retained in the
parsed result and must match the exact stdout sequence. Malformed or partial
stdout remains raw-only; the verifier does not guess or synthesize a receipt.
A valid serial result followed by process cleanup failure remains available,
but its aggregate summary is `INCOMPLETE`.

`COMPLETE_INCAPABLE_EVIDENCE` means a clean process lifecycle and complete nested
records. It can contain a correctly retained serial fault. Inspect separately:

- process status, creation, resume, tree exit, primary and cleanup errors;
- feedback status, exact-response validity, serial-close and unexpected bytes;
- native resource counts, pending I/O, startup/late bytes and native cleanup.

`device_cleanup_proven`, `arm_connected` and `physical_authority` remain false.
Final power remains `UNKNOWN_REQUIRES_SEPARATE_OBSERVATION`. Display cleanup errors
are limited to 16 safe codes with explicit total/omitted counts; the full private
error list remains retained. No serial-close or process-kill inference changes
these fields.

## Hardware-free verification

Run the focused pure contracts from the repository root:

```powershell
.venv/Scripts/python.exe -m pytest software/tests/unit/test_arm_owned_protocol.py software/tests/unit/test_arm_owned_evidence.py -q
```

The focused suite passed 63 tests. It forbids native DLL/process dispatch and
uses the actual worker plus exact incapable Win32 API for startup input, late
completion, short write, timeout, malformed/extra response and close/pending-I/O
faults. Pure process observations in that suite are explicitly modeled. Separate
owned-runner tests exercise the actual harmless child and the presentation
tests consume its real retained output. None establishes real COM identity,
electrical RTS/DTR behavior, USB stability, received firmware, physical stop
readiness, de-energization or permission to move/contact the board.

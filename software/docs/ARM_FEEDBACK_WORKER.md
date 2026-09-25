# Onboarding-only arm feedback worker

Status: implemented and fixture-tested; **physical serial activation remains
blocked**. This module does not connect the received arm, qualify its firmware,
complete stages 9–12, or enable power, motion, typing, or tapping.

Implementation: [arm_feedback_worker.py](../src/rocell/providers/windows/arm_feedback_worker.py).
Tests: [test_arm_feedback_worker.py](../tests/unit/test_arm_feedback_worker.py).
This is a bounded part of DEV-009, paired with the
[developer playbook](CAMERA_ARM_DEVELOPER_PLAYBOOK.md#dev-009--join-arm-identity-power-ceremony-and-feedback)
and [arm integration sequence](CAMERA_ARM_CONNECTION_INTEGRATION_PLAN.md#7-arm-connection-startup-and-initialization-workflow).

## What exists

The provider executes one exact, externally authorized serial lifecycle against
a sealed memory-only backend. A separate Windows/pySerial backend contains
closed-object construction but is stopped before import/construction by a
source-controlled physical-qualification hold. Neither an `allow_hardware`
option nor a permissive authorizer can remove that hold.

The module reuses `RoArmUsbSerialIdentity`, `SingleT105FeedbackRequest`,
`SingleT105FeedbackReceipt`, and `T105TransactionTiming`. Framing and typed
telemetry reuse `feedback_wire.py`, `protocol.py`, and `feedback.py`; there is
no second permissive response decoder. Missing telemetry fields remain null;
a syntactically valid `T=1051` packet is not a firmware/model identity check or
a complete onboarding assessment.

The legacy commissioned `SerialTransport`, `FeedbackPermit`, `arm-feedback`
command, `arm_connection.json`, current build state, and release gates are
unchanged. This is a distinct prospective onboarding contract, not a bypass
that manufactures a legacy commissioned permit.

## Significant native blocker discovered during implementation

The installed pySerial 3.5 Windows implementation calls `PurgeComm` with receive
and transmit clear/abort flags during `Serial.open()`. Therefore avoiding
`reset_input_buffer()` in our own worker does **not** preserve all bytes that
were present during native opening. This behavior was checked against both the
local dependency source and the [official pySerial 3.5 Windows source](https://raw.githubusercontent.com/pyserial/pyserial/v3.5/serial/serialwin32.py).

The status/report explicitly includes
`PYSERIAL_WINDOWS_OPEN_PURGES_INPUT_REQUIRES_REVIEWED_NONPURGING_BACKEND`.
A reviewed non-purging native opener, received-bridge tests, and independent
qualification are prerequisites for any physical release. Do not monkeypatch
the installed dependency, suppress its purge call dynamically, or relabel the
memory backend as physical to get past this finding.

Furthermore, pySerial documents possible OS/driver RTS/DTR activation or
glitches when opening. Requested false values and their property readbacks are
not electrical measurements or proof that the ESP32 did not reset.
[pySerial API documentation](https://pyserial.readthedocs.io/en/latest/pyserial_api.html#serial.Serial.open)

## Public API

`ReviewedControllerBinding` retains the exact `RoArmUsbSerialIdentity` plus
separate hashes for unpowered identity, controller-to-Pro-model review,
installed firmware evidence, boot policy, and the serial profile. Its origin
must be explicit. The COM name is an ephemeral observed endpoint inside that
binding, never an input that independently selects hardware. Only exact
`COM1` through `COM4096` strings are admitted; URLs, raw device paths, guessed
baud rates, and generic serial transports are not accepted.

`ArmFeedbackCampaignRequest` binds the controller review, existing single-query
request, source, operation, energization envelope, expiration, and finite
budget. Its `request_sha256` covers the fixed wire request and settings as well.
`parse_arm_feedback_request(payload: bytes)` is the strict future process-IPC
decoder: maximum 64 KiB, UTF-8 JSON, duplicate/nonfinite/unknown-field rejection,
exact constants, and no Boolean/numeric coercion.

```python
worker = ArmFeedbackWorker(
    authorizer=qualified_coordinator_authorizer,
    identity_resolver=reviewed_exact_os_identity_resolver,
    # Omitted backend is the hard-held WindowsPySerialBackend.
)
status = worker.status()             # No imports, enumeration, opens or writes.
result = worker.run(exact_request, cancellation=cancel_event)
projection = result.to_dict()        # No physical authorization or raw boot text.
```

This example describes the integration boundary, not a currently released way
to connect hardware. The mandatory authorizer must validate and consume exact
durable authority before returning `None`; denial raises. A Boolean return is
rejected. It must own and retain the applicable ordered leases for the whole
campaign, verify source and stage state, independently reviewed identity and
firmware/boot-policy evidence, the current power event/envelope, the complete
worker budget, and qualified provider provenance. Browser data cannot provide
an authorization Boolean or an already-trusted hash.

The identity resolver is also an integration seam: it must freshly resolve and
return the full observed identity, including driver and persistent paths. A
pySerial port list by itself does not prove all these fields or bind an opened
handle atomically. Final opened-handle/COM-race qualification is still needed.

Each worker object accepts one request in its entire lifetime, including after
denial, cancellation, or failure. It never retries or accepts a replacement
request. That in-memory rule does not replace the coordinator's durable
cross-process/cross-restart request and permit deduplication.

## Exact lifecycle and accounting

1. Validate the complete lifetime, origin, backend availability, and exact
   external authorization. Construction and status do not call any backend.
2. Resolve the reviewed controller identity immediately before creating a
   serial object. Changed unit, driver, persistent identity, or COM mapping
   blocks admission.
3. Create a closed serial object. Set 115200 baud, 8N1, one-second read/write
   timeouts, RTS/DTR false, and all hardware/software flow controls false before
   open. Retain exact pre-open settings readback.
4. Attempt one open. Recheck settings and observe the input buffer over the
   explicitly bounded quiet interval. Unexpected boot/stale bytes cause a
   bounded evidence-prefix read and termination with **zero request writes**.
   No flush-to-clean-and-continue path exists.
5. Resolve exact identity again, check the buffer once more, then attempt only
   `{"T":105}` followed by one LF. A full write must return exactly ten bytes;
   partial or ambiguous writes are recorded and never completed by retry.
6. Read one bounded response, reject framing/JSON/response-type/typed-field
   failures, and reject extra buffered bytes. Request IDs correlate our logs
   only: the firmware response does not echo a host transaction nonce.
7. Attempt close exactly once for every acquired serial object, including
   configuration/open failures. Retain the primary failure separately from
   close, deadline, and completion failures. Closing does not send a stop,
   torque, reset, initialization, or park command and does not remove DC power.

The default budget is five seconds, a 250 ms quiet interval, at most 512 read
calls, and 256-byte reads. Allowed budgets remain finite: 4–10 seconds,
250–1000 ms quiet time, at most 4096 reads, and at most 1024 bytes per read.
The existing line limit is at most 65,536 bytes; one extra byte detects an
overlong response. Quiet observation has a separate iteration cap. Reads
shorten their timeout to the remaining campaign time; the fixed one-second
write is not attempted if that timeout no longer fits. None of these software
bounds can forcibly interrupt a stalled native open/close without the separate
process supervisor described below.

Counts distinguish API object creation, attempted/confirmed open, write calls,
API-reported written bytes, reads and retained bytes, and attempted/confirmed
close. A factory returning an unexpectedly open object is uncertain, not a
harmless pre-open refusal. In rehearsal, actual physical operation counters
remain zero even though the in-memory API lifecycle counters are nonzero.

`SingleT105FeedbackReceipt` is created only after valid response, quiet suffix,
confirmed close, and timely completion. A returned nominal diagnostic packet
does not prove final power-off. Every report retains
`UNKNOWN_REQUIRES_SEPARATE_OBSERVATION` for final power and
`installed_firmware_proven_by_packet: false`.

## Evidence and exports

The immutable result retains response bytes, a bounded unexpected-byte prefix,
and an explicit count of unexpected bytes not retained. Unexpected data is
never discarded and then used as justification to continue. Host timing means
when bytes were observed by the host read, not firmware generation, UART
arrival, or sensor timestamps.

`result.to_dict()` deliberately exposes only typed numeric feedback,
settings/counts, hashes, fixed error codes/types, and limitations. Raw boot text
or unknown response fields can contain credentials; they are not copied into
ordinary UI logs, even as hexadecimal. The typed receipt and raw bytes remain
available to a separately authorized qualified evidence writer. This worker
does not choose paths, write files, export operational stores, or turn its
in-memory result into durable evidence on its own.

## Closed no-hardware rehearsal entry

`rehearse_arm_feedback_campaign(scenario)` accepts exactly:

| Scenario | Expected behavior |
| --- | --- |
| `nominal` | One in-memory query/reply and confirmed close |
| `boot-bytes` | Retained synthetic boot bytes, zero request writes |
| `short-write` | One partial write, no retry |
| `timeout` | One request, missing response, uncertain diagnostic result |
| `identity-change` | COM change after open, zero request writes |
| `close-failure` | Valid response retained, failed close prevents success |

The returned report has `expected_outcome_matched`, `observed`,
`physical_authority: false`, `actual_effect_counts` all zero, and
`arm_connected: false`. An expected-fault match means the software correctly
rejected the fault; it never means the arm connected or passed onboarding.
This entry always constructs the sealed memory backend and a virtual clock.
Its explicitly labeled in-memory exact-request acknowledgement has no durable
or production authorization role.

## Next process-harness integration contract

Do not rewrite the lifecycle in a CLI or UI handler. A later registered child
process should decode one bounded request with `parse_arm_feedback_request`,
construct one worker, and invoke `run` once. Required qualification work:

- Bind the registered child executable/module/package hash and source to the
  exact parent permit, request digest, attempt, session, controller and budget.
- Keep `CELL → SESSION → ARM_CONTROLLER` ownership in the qualified parent;
  the child must redeem its one-use authorization through a bounded trusted
  parent channel. Do not deserialize a frontend "authorized" flag or replace
  authorization with a no-op inside the child.
- Bound stdin, stdout/stderr, memory, handles, total wall time and process tree
  lifetime. The small result projection fits a 256 KiB envelope; any raw wire
  dataset must use a separate bounded qualified retention path.
- Deliver cancellation without adding a second controller command. Process
  termination or worker disappearance is uncertainty, not evidence of close,
  stopping, or final de-energization. Never automatically restart the child.
- Retain the serial result and raw evidence through the qualified coordinator
  before known completion. Independently retain the required final manual
  power-off observation; never map this result's unknown power state to
  `ObservedPowerState.DEENERGIZED` merely to satisfy a coordinator receipt.
- Resolve the pySerial open-time purge problem, controller/COM race, RTS/DTR
  electrical behavior, native cleanup certainty, installed firmware and boot
  policy before considering physical activation.

The current default Windows backend intentionally remains unavailable until
that independent review and source-controlled release exist.

## Next implementation checklist: native opener and process containment

The following paths and tickets are **proposed ownership boundaries**, not
implemented files or authorization to connect hardware. Keep this work in
separately reviewed changes; do not modify the installed pySerial package.

| Ticket / owner | Proposed owned files | Existing seam to preserve |
| --- | --- | --- |
| ARM-NATIVE-01 / Windows native developer | `software/native/windows_arm/serial_api.h`, `serial_api.cpp`, `serial_api_tests.cpp`, `CMakeLists.txt` | Closed object, explicit configure/open, bounded buffer/read/write/close; no motion/reset surface |
| ARM-IPC-02 / worker runtime developer | `software/src/rocell/providers/windows/arm_worker_process.py`, `arm_worker_main.py`; corresponding unit tests | `parse_arm_feedback_request`, `ArmFeedbackWorker.run`, exact request digest, safe result projection |
| ARM-BIND-03 / identity and integration developer | `software/src/rocell/providers/windows/arm_controller_identity.py`; corresponding unit tests | `ControllerIdentityResolver` and immutable reviewed identity; no COM-only selection |
| ARM-QUAL-04 / independent reviewer | `software/native/windows_arm/README.md`, reviewed build/qualification manifests, received-unit acceptance record | Existing physical holds, canonical stages 9–12, M1 durability and coordinator authorization |

Choose whether the native API uses a narrow in-process binding or a registered
native helper as an explicit ARM-NATIVE-01 design decision. The decision must
show how one owner holds the serial handle throughout the existing lifecycle;
do not duplicate response parsing, quiet-buffer admission, or retry policy in
a UI handler. Any necessary extension to the worker's currently closed backend
registry requires a separate reviewed change and remains physically held.

### ARM-NATIVE-01: pre-hardware acceptance

- [ ] Define an injectable Win32 call facade and handle-owner type. No native
  call occurs in construction, import, status, or object destruction as an
  implicit substitute for explicit cleanup. Keep final cleanup failures
  observable even if an exception already exists.
- [ ] Open only the endpoint produced by the reviewed binding. Use exclusive,
  non-inheritable ownership and the reviewed overlapped-I/O policy. Reject
  failed handle/event allocation and clean up each acquired resource once.
  Verify the required communication-resource open parameters against
  [Microsoft's communication handle contract](https://learn.microsoft.com/en-us/windows/win32/devio/communications-resource-handles).
- [ ] Trace every native call in fixture tests. Prove that no open path,
  configuration path, timeout path or cleanup path clears buffered input to
  manufacture quietness. Reject automatic purge/reset/fallback behavior; do
  not treat removal of one explicit `PurgeComm` call as sufficient proof.
- [ ] Test 115200/8N1, RTS/DTR false, disabled flow control, timeout units,
  settings readback mismatch, pending input, and extra response bytes. Inject
  configuration failure before and after resource acquisition.
- [ ] Test fragmented/empty/overlong/non-text reads, exact and partial writes,
  pending I/O, cancellation races, and failures of every cleanup operation.
  At most one fixed request write may be submitted; never submit its remainder.
  Cancellation is a request to cancel I/O, not evidence that cancellation or
  cleanup completed. Check completion separately, consistent with
  [Microsoft's cancellation contract](https://learn.microsoft.com/en-us/windows/win32/api/ioapiset/nf-ioapiset-cancelioex).
- [ ] Retain a native call trace and resource-accounting report showing no
  leaked event/port handles across every injected failure. Keep native API
  outcomes distinct from our host-level counters and electrical observations.

All these tests use injected native-call results, not a real COM port. A
passing fake native facade still cannot prove what the received bridge/driver
does electrically or which bytes it preserves.

### ARM-IPC-02 and ARM-BIND-03: pre-hardware acceptance

- [ ] Freeze the helper/package identity and closed request/result envelopes.
  Exercise pretty/compact JSON, duplicate keys, unknown fields, malformed
  lengths, nonfinite numbers, changed hashes and truncated packets through the
  real process pipes using only incapable children. Requests remain at most
  64 KiB; the safe result envelope remains at most 256 KiB.
- [ ] Bind an exact one-use child redemption to the parent-held attempt,
  request, source, controller and session. Test denied/stale/substituted
  redemption, two concurrent execute requests, worker restart, and parent
  restart. Every duplicate must dispatch zero additional workers/queries.
- [ ] Establish process-tree containment before any child can reach device
  code. Test denied containment setup, nested-job restrictions, child spawning,
  attempted breakaway, output flooding, stalled stdin/stdout, and parent death.
  Document the selected Windows Job Object policy and prove containment with
  harmless incapable processes. A process identifier alone is not ownership;
  see [Microsoft's Job Object guidance](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects).
- [ ] Define explicit memory, handle, process-count and elapsed-time bounds.
  Ensure startup, campaign and cleanup windows fit the exact permit/envelope
  lifetime. Reject a campaign that no longer fits rather than extending it.
  Termination/timeout after admission preserves an unresolved or uncertain
  attempt; it never becomes a successful close or a fresh retry opportunity.
- [ ] Test parent death and durable publication failure at intent, arming,
  write-start, receipt retention and seal boundaries using actual qualified
  temporary M1 stores plus incapable workers. Verify quarantine/reconciliation
  after restart and prove that changing session IDs cannot bypass the hold.
- [ ] Exercise metadata fixtures for duplicate controllers, missing unit
  serial, missing driver fields, moved USB topology, reassigned COM aliases,
  disconnect/reconnect between checks, and a mismatch between the selected
  endpoint and opened handle. Ambiguity blocks; no first-match fallback.
- [ ] Preserve raw/parsed wire evidence through the assigned qualified writer,
  while ordinary UI/export projections exclude boot credentials and unknown
  response values. Test truncated evidence, hash mismatch and failed durable
  retention before any known seal. A small stdout report is not raw evidence.
- [ ] Demonstrate that an external final-power observation is required even
  after a valid packet and confirmed API close. Do not synthesize a power-off
  observation in the child, fixture-to-physical adapter, or receipt mapper.

### ARM-QUAL-04: received-hardware acceptance, separately authorized

These checks are not authorized by this checklist or its software test results.
Prepare and independently approve the physical runbook first, including the
canonical stage prerequisites, startup swept-volume clearance, containment,
independent power cut, distinct operator/observer and required absence of
contact tooling/devices. No automatic demo, torque toggle, home, motion,
firmware flash or boot-mission edit is an acceptance shortcut.

- [ ] Record received Pro arm/controller correlation, unit identifiers,
  persistent OS mapping, installed driver/version, supply topology, installed
  firmware evidence and boot-policy observation method. A vendor archive hash
  or valid telemetry packet cannot stand in for received-unit evidence.
- [ ] Instrument the actual received USB bridge/control lines and retain
  observations around the separately approved open/close and power sequence.
  Characterize RTS/DTR behavior, reset/boot chatter and startup motion; property
  readbacks alone do not satisfy this test.
- [ ] Demonstrate startup-byte preservation and the quiet-buffer failure path
  on the actual host/driver/bridge combination under the approved runbook.
  If pre-open bytes cannot be observed or preserved as required, record that
  limitation and retain the hold instead of claiming a clean initial buffer.
- [ ] Validate the actual identity-to-opened-handle relationship, competing
  owner behavior, disconnect/timeout/cleanup outcomes, and bounded process
  containment. Record uncertainty whenever the approved observation cannot
  establish what happened; do not blindly replay a failed test.
- [ ] Retain separate final de-energization evidence and independent review of
  the exact received configuration, complete native build provenance and test
  results. Requalification is required after safety-relevant changes.

### Mandatory hold decision

Keep **all physical activation holds** if any checklist acceptance is missing,
any relevant test fails, input clearing or an undocumented fallback remains,
identity/firmware/boot policy is ambiguous, process containment or cleanup is
unproved, evidence is missing/tampered, or final power state is unknown. A known
reset or startup movement without an accepted containment/observation contract
also retains the hold.

Even complete provider tests do not activate today's rehearsal-only coordinator.
A separately implemented and independently reviewed physical composition,
current release decision and exact stage/power authorization are additionally
required. Do not remove `_require_independent_physical_qualification`, set a
runtime bypass, or relabel synthetic receipts as a consequence of a green test
suite. Record proposed release changes for independent review instead.

## Sources and verification

Existing pins remain unchanged: SDK commit
`d9893632aa7f5a9cb283136ab024faf3143ea7db` and firmware archive SHA-256
`a28247fee0bbb65cc034ff206031b8700d2b1ec8e3a1fa4b1a5a7365c55f1a57`.
See the [model source manifest](../models/roarm_m3/README.md#pinned-sources).
The [official UART guide](https://www.waveshare.com/wiki/RoArm-M3-S_Python_UART_Communication_Control)
and [robot feedback documentation](https://www.waveshare.com/wiki/RoArm-M3-S_Robotic_Arm_Control)
are protocol references, not authorization to run their demos or proof of the
received controller's firmware. pySerial source was inspected read-only; no
dependency, driver, controller, firmware, mission, or existing transport was
modified.

Run the fixture suite from the workspace root:

```powershell
.\.venv\Scripts\python.exe -m pytest software/tests/unit/test_arm_feedback_worker.py -q
```

The suite covers inert construction/status, permanent native holds, exact
settings/wire identity, one-use requests, framing/JSON faults, stale buffers,
COM changes, byte/read/deadline limits, cancellation, primary plus cleanup
errors, lossless private evidence versus safe status projections, closed IPC
parsing, and every public incapable scenario. No test enumerates or opens a
physical serial device.

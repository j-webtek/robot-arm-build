# Non-purging Windows serial backend — ARM-NATIVE-01

Status: **software fixture slice implemented; physical activation held**.
This is not an arm connection, a passed physical onboarding stage, or a release
of the current rehearsal-only coordinator. No device was enumerated or opened
while developing or testing this slice. No pySerial installation, legacy
transport, worker registry, configuration, firmware or power state was changed.

## Ownership and architecture decision

ARM-NATIVE-01 uses a narrow **Python ctypes Win32 facade**, not a separately
compiled C++ serial helper. An isolated worker process must own the facade and
connection throughout a campaign. The separate ARM-IPC-02 process supervisor
remains responsible for containment, outer deadlines and uncertain termination.

New files:

- `src/rocell/providers/windows/nonpurging_serial_api.py`: pure value types,
  injectable Win32 protocol, sealed incapable facade, and held Win32 call code.
- `src/rocell/providers/windows/nonpurging_serial_backend.py`: one connection
  owner, fixed settings, input-preservation latch and resource accounting.
- `tests/unit/test_nonpurging_serial_backend.py`: memory-only native-result
  fixtures. Every test blocks ctypes native DLL loading.

The existing `ArmFeedbackWorker` still accepts only its previously reviewed
backend registry. This new backend is deliberately **not registered** there,
and no current UI action can activate its native branch.

## Public seam for the next integration change

```python
from rocell.providers.windows.nonpurging_serial_api import (
    FIXED_QUERY,
    IncapableWin32Scenario,
    IncapableWin32SerialApi,
)
from rocell.providers.windows.nonpurging_serial_backend import (
    NonPurgingSerialConnection,
)

# reviewed_binding must have SYNTHETIC_REHEARSAL origin in this example.
# It is the existing typed ReviewedControllerBinding, not a COM string.
api = IncapableWin32SerialApi(IncapableWin32Scenario())
connection = NonPurgingSerialConnection(reviewed_binding, api=api)
connection.open()
try:
    # Illustrates the low-level fixture only. The existing campaign worker
    # still owns quiet-interval admission, identity checks and wire validation.
    assert connection.in_waiting == 0
    connection.write(FIXED_QUERY)
    raw_bytes = connection.read(256, timeout_ms=1000)
finally:
    connection.close()
report = connection.status()
```

Constructor and `status()` are inert. `is_open` reports conservative local
handle ownership, not a live hardware query. `open()` is single-use, including
failure. `write(payload)` accepts only the exact ten-byte `{"T":105}\n` request
and submits it at most once. There is no remainder submission, retry, motion,
initialization, reset, break, port-selection, buffer-clear or raw-command API.

`read(size, timeout_ms=...)` accepts 1–1024 bytes and a 1–1000 ms completion
wait. At most 4096 read admissions and 65,537 retained bytes are permitted per
connection. Queue queries are capped at 4096. These are local limits, **not an
overall campaign deadline**: the existing campaign and its process supervisor
must keep all calls, startup and cleanup within the exact authorization window.

Only exact `IncapableWin32SerialApi` or `WindowsNativeSerialApi` types are
accepted; arbitrary callbacks, foreign facades and subclasses cannot claim
incapable origin. A physical-origin binding cannot be relabeled by passing the
fixture facade. The public `Win32SerialApi` protocol documents the narrow test
seam, but it is not an unrestricted production dependency-injection endpoint.

`WindowsNativeSerialApi` creates no native API in construction. Every actual
native call path reaches the unconditional source-controlled
`NONPURGING_SERIAL_INDEPENDENT_PHYSICAL_QUALIFICATION_REQUIRED` hold before
loading `kernel32`. There is no release boolean, environment variable,
authorizer callback, DLL-path option or fixture switch. The actual ctypes
driver branch remains unexecuted and independently unqualified.

## Open and byte-preservation contract

The connection derives `\\.\COMn` only from its immutable reviewed identity.
The lower call boundary also rejects ordinary files, network paths, arbitrary
device paths and COM aliases outside COM1–COM4096. The requested open is:

- `GENERIC_READ | GENERIC_WRITE`;
- share mode zero, `OPEN_EXISTING`, no template handle;
- null security attributes, making the handle non-inheritable;
- `FILE_ATTRIBUTE_NORMAL | FILE_FLAG_OVERLAPPED`.

The owner records the fixed settings before attempting open, then applies and
reads them back after obtaining a handle: 115200 baud, 8 data bits, no parity,
one stop bit, binary mode, RTS/DTR disabled and all hardware/software flow
control disabled. DSR filtering, null removal and error-byte substitution are
disabled. XON/XOFF characters remain distinct even though flow control is off.
Read and write total constants are 1000 ms; interval and byte multipliers are
zero. No previous DCB, timeout or control-line state is restored during close.

**This does not electrically configure a device before CreateFile.** Win32
requires a handle for `SetCommState`; the desired pre-open values cannot prove
that a particular bridge/driver avoids an open-time RTS/DTR pulse or reset.
That limitation remains an independent physical hold.

Input queues are inspected immediately after open, again after settings
readback, during explicit queue checks and immediately before the one write.
Every completed nonempty read before the write, including late completion,
also latches pre-write input. Reading those bytes cannot manufacture a fresh
quiet state: a later write is still rejected. Raw bytes are returned unchanged
for the existing evidence/wire pipeline; this backend does not independently
interpret a T1051 response or silently discard extra/non-text data.

There is no call to `PurgeComm`, `SetupComm`, `FlushFileBuffers`, reset, break,
or control-line fallback. `ClearCommError` is used to obtain `COMSTAT`; it
acknowledges error flags, not queued input. Every nonzero error mask is retained
and fails the connection rather than being treated as recovery. The full
call trace is available on the memory fixture.

Microsoft documents that `SetCommState` does not empty the device queues; this
supports the API choice, not proof of the received bridge's earlier behavior.
See [communication handles](https://learn.microsoft.com/en-us/windows/win32/devio/communications-resource-handles),
[DCB](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-dcb),
[SetCommState](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-setcommstate),
[COMMTIMEOUTS](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-commtimeouts)
and [ClearCommError](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-clearcommerror).

## Pending I/O and cleanup contract

One port handle and two non-inheritable manual-reset event handles have one
owner. There is at most one outstanding operation. Each I/O receives a fresh
token/OVERLAPPED and stable buffer. Pure token validation precedes native
allocation/copy: fixed write size and bytes must agree exactly, reads have an
empty payload, and event/kind/size/token-reuse bounds are strict.

Completion uses bounded `GetOverlappedResultEx` with non-alertable waits. A
pending result at the deadline is a failure. The owner requests cancellation
once and then performs a separate completion check of at most 250 ms:

- `ERROR_NOT_FOUND` from cancellation is not completion proof.
- A write completing after cancellation is counted but the timed-out campaign
  remains failed. Its remainder is never submitted.
- A late read is retained separately for the qualified evidence writer; its
  payload is not exposed in status JSON.
- Aborted, completed, pending and malformed native results are distinct.
- Unknown completion errors remain conservative holds.

If completion is still unproved, buffers/OVERLAPPED/event/port ownership are
retained and the report says `CLEANUP_UNCONFIRMED`. The native facade pins its
outstanding buffer independently of the caller's lifetime until verified
terminal completion. There is no destructor that guesses at I/O cancellation
or treats garbage collection as explicit cleanup. The isolated supervisor must
contain and resolve/terminate such a worker; it must not publish known cleanup
or replay the campaign merely because the process exits.

When no I/O remains pending, each acquired event/port handle receives one close
attempt in reverse ownership order. Failure of one close does not suppress
other close attempts or the original primary failure. Repeated `close()` does
not retry failed handles. Counts distinguish acquired, attempted, confirmed
and unresolved resources. API completion/cleanup counts are not electrical or
power observations. Microsoft's [ReadFile lifetime rules](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-readfile),
[bounded completion API](https://learn.microsoft.com/en-us/windows/win32/api/ioapiset/nf-ioapiset-getoverlappedresultex)
and [CancelIoEx contract](https://learn.microsoft.com/en-us/windows/win32/api/ioapiset/nf-ioapiset-cancelioex)
are the references for these choices.

## Evidence and authority boundaries

`status()` contains only bounded metadata, request/settings hashes, numeric
counts, fixed error codes and byte hashes. It does not include arbitrary driver
exception messages or raw startup/response text. Returned read bytes and
`late_read_bytes` are private evidence inputs for the assigned qualified writer,
not browser-export fields. The existing shared T1051 validator remains the
protocol authority; a successful low-level transfer is not a passed feedback
campaign.

Every current report has `physical_authority=false`, `arm_connected=false`,
actual physical effect counts zero, and final power state
`UNKNOWN_REQUIRES_SEPARATE_OBSERVATION`. Zero actual effects reflect this
revision's sealed memory fixtures and unreachable native branch, not a recipe
for accounting after physical release. Any future release must separately
review native physical effect accounting and durable receipt integration.

## Acceptance and next handoff

Run from the workspace root:

```powershell
.\.venv\Scripts\python.exe -m pytest software/tests/unit/test_nonpurging_serial_backend.py software/tests/unit/test_arm_feedback_worker.py -q
```

Current fixture acceptance covers closed/inert construction, immutable binding
and origin, exclusive open parameters, DCB/timeout readback, every open-stage
failure, startup/delayed input, partial/duplicate writes, binary/extra data,
bounded reads, pending I/O, late completion, failed cancellation, cleanup
failures, malformed completion counts/types, token-copy bounds, Win32 structure
layout, arbitrary-path rejection and absence of purge/flush/reset paths.
Injected unresolved resources are intentionally retained and explicitly counted,
not inaccurately reported as leak-free cleanup.

Remaining work must retain all physical holds:

1. Separately review the adapter into the worker's closed backend registry.
   Preserve mandatory exact one-use coordinator authorization, final identity
   rechecks, quiet interval, total budget, shared wire codec and evidence
   publication-before-known-seal. Do not recreate them in this low-level class.
2. Finish and qualify ARM-IPC-02 isolated process containment before any device
   code can run. Prove whole-tree cleanup and uncertainty behavior using
   incapable children; bounded Python waits do not interrupt every OS call.
3. Implement/review ARM-BIND-03 identity-to-opened-handle correlation. Exact
   reviewed COM spelling alone does not close the reassignment race. This
   backend deliberately does not claim atomic USB-unit identity proof.
4. Independently review the native ctypes ABI/call implementation and build
   provenance. Fixture coverage of the handle owner does not exercise or
   qualify real kernel calls, bridge behavior, driver error semantics, or
   electrical RTS/DTR states.
5. Under a separately authorized stages 9–12 hardware runbook, gather received
   controller/driver/installed firmware/boot-policy evidence; verify startup
   input preservation, reset/line behavior, power/containment and final manual
   de-energization. No initial motion, torque/home/demo/reset shortcut is added.
6. Obtain an independently reviewed physical composition/release decision.
   A green suite does not authorize removal of the native hold or migration of
   synthetic evidence into a physical session.

The broader prerequisites and receipt requirements remain in
[ARM_FEEDBACK_WORKER.md](ARM_FEEDBACK_WORKER.md) and the
[DEV-009 playbook](CAMERA_ARM_DEVELOPER_PLAYBOOK.md#dev-009--join-arm-identity-power-ceremony-and-feedback).

# Servo diagnostic producer — experimental, not deployed

`servo_evidence.h` is a portable C++11 producer core, not a replacement sketch or
an automatically applicable firmware patch. It has no Arduino startup, native
serial/network adapter, motion dispatch, PID/torque writes or automatic retries.

## Implemented and tested

`callback_handoff.h` now provides a bounded nonblocking copy queue for callback
inputs. Host assertions cover FIFO, mutation isolation, malformed input, overflow
and 100 concurrent-producer trials. Faults latch and prevent later consumption;
there is no command execution or automatic replay. See
`software/docs/SERVO_BUS_OWNERSHIP_REVIEW.md` for the reference's direct ESP-NOW bus
calls and required native wiring. Host producer tests now use C++14 for the local
standard-library headers; ESP32 build/atomic support remains unverified.

`reference_read_adapter.h` is now tested against the actual pinned SCS source with
the candidate response-ID/length guard, using in-memory transport. It permits only
the named target and feedback reads, immediately captures Error only after a full
validated response, clears failed/error payloads, and reports missing error status
as -1. It does not initialize the library or mutate settings. Its template type name
is a precondition, not enforcement of a source hash: native builds must pin and
verify the guarded implementation before instantiation.

The protocol rehearsal covers eight truncation points, checksum corruption,
wrong ID/length, stale Error after failure, a separate later valid read, and seven
adapter cases including both 2-byte and 15-byte reads. The latter recovery does
not prove native serial-buffer resynchronization. Valid same-servo delayed packets
cannot be distinguished by command ID in this protocol; native exclusive ownership,
flush/deadline behavior and request chronology still require review.
Verified report: `wizard-20260918T010841190393Z-cce9a90947dd459f858ad359c6497356`.
It includes harness and adapter hashes as well as vendor/candidate hashes.

`command_capture.h` binds one retained dispatch to copied boot/command identity,
actual converted count/settings and dispatch time. It snapshots its own reads, so
later caller mutation cannot relabel or alter emitted evidence. It enforces a
finite sample count, after-dispatch acquisition and maximum pair duration; uncertain
dispatch or a capture fault stops further acquisition. It cannot be restarted or
reused for a second command. Dispatch and pair JSON now enter the Python decoder
directly in the host test. The original request/payload hash remains supplied by
the synthetic outer envelope; native receipt/conversion hooks are not implemented.
The adapter must also export `write_evidence()` (raw return, error, ACK policy);
the current v2 dispatch JSON carries only its derived status and command settings.
Serialization failure is reported to the caller, which must stop progression and
retain the capture; this class does not perform or certify durable export.

`servo_evidence_json.h` now emits the complete acquisition-pair JSON directly
from captured C++ records. It validates bounded ASCII boot/command identities and
explicit byte order, emits null raw data for failed reads, and clears output on
insufficient capacity. Its two temporary record buffers total 1,536 bytes; assess
ESP32 task-stack headroom before native integration. The host test consumes both
successful and failed emitted JSON without reconstructing read records in Python.
Outer trace metadata is still synthetic: this is not complete command capture.

- Records a write-library return separately from protocol error and explicit ACK
  policy. A return of 1 is not verified dispatch if ACK policy is unknown/disabled
  or the address is broadcast. Missing acknowledgment is a failed verification,
  not proof that the write never reached the servo; never retry automatically.
- Injected bus performs only named target-register (42/2 bytes) and feedback-block
  (56/15 bytes) reads, with independent monotonic intervals and sequences.
- Fresh zeroed per-read storage; failed/short/error reads cannot publish old bytes.
  The serializer must emit null raw data on failure, retaining count/error status.
- Fault latches prevent another acquisition after a failed pair or clock reversal.
  Invalid requests clear output and issue no bus call. There is no automatic reset.
- The C++ executable contains only a fake bus. Pytest compiles it with the host
  compiler, runs assertions and feeds its actual captured records into the Python
  v2 decoder. Elbow joint 3 uses reference servo ID 14 in this test.

Run from workspace root:

```powershell
.\.venv\Scripts\python.exe -m pytest software/tests/unit/test_servo_evidence_producer.py -q
```

The current workstation ran this successfully with clang++. This is **not** an
ESP32 cross-compile, Arduino dependency validation, full firmware build or hardware
test. Python uses synthetic boot/command/profile metadata around the captured
records; no device identity claim follows.

## Reviewed source semantics

Pinned servo-library archive SHA256:
`b8b377642b3eb45610226fdf96fbc61d7c012a512bdd7f8c904a9c1ac88328af`.
`SMS_STS.cpp:23–35`: WritePosEx encodes position and calls genWrite.
`SCS.cpp:93–98`: genWrite returns Ack's result.
`SCS.cpp:280–303`: Ack returns 1 without receiving a reply when Level is disabled
or ID is broadcast. With replies enabled, errors and return value must both be
checked. Transport write return values are not propagated by this path.
These semantics are reference-specific, not yet verified installed behavior.

## Still required before a deployment request

Native-adapter prerequisite: the pinned vendor `SCS::Read` accepts a checksummed
reply with the wrong servo ID or length. A naive `Read`/`Error` wrapper is therefore
not safe. The guarded adapter described above is only host-tested. The actual source was compiled with an in-memory packet transport
and the defect reproduced; a candidate ID/length guard rejects both malformed cases
while accepting the correct packet. Run
`software/scripts/rehearse_reference_read_guard.py` to reproduce and export. Its
temporary patch is not deployed. See `SERVO_READBACK_REFERENCE_REVIEW.md` for the
verified report and additional failed-read/stale-error caveat.

1. Bind the exact firmware/library build, byte order, servo model/mapping and
   acknowledgment configuration. Never enable ACKs by changing servo configuration
   automatically; read/review support first.
2. Hook actual T101 conversion and `WritePosEx` return without issuing a second
   write. Capture command/boot identity, immutable target/settings, payload hash
   and dispatch times. Handle rejected/duplicate commands explicitly.
3. Implement the adapter on the existing controller bus owner and enforce exclusive
   access across HTTP, serial, background feedback and ESP-NOW paths. This header
   assumes single ownership; it does not provide a cross-task lock.
4. Add bounded serialization, profile/build metadata, correlation windows, maximum
   sample count and retention. Failed pair records must be exported even though
   progression stops. Zero-width output after a refused call is not an acquisition.
5. Test complete producer → transport → wizard/export handling with injected errors;
   perform an actual pinned ESP32 build and review memory/timing/boot behavior.
6. Obtain explicit deployment authorization with backup/recovery details. No camera,
   contact, compensation expansion or firmware upload is enabled by these tests.

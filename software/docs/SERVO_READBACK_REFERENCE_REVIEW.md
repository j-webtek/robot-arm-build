# Servo readback reference review

Reviewed 2026-09-18. External source downloads only; no arm connection or changes.

## Finding

The vendor servo library has a potential read-only path to the missing evidence.
This is a reference capability, not verified installed support. We need not infer
goal acceptance from position: the library defines separate goal-position registers
and generic register reads. Integration is still needed in the arm controller.

Source: [Waveshare servo-driver archive](https://files.waveshare.com/upload/5/5a/SERVO_DRIVER_WITH_ESP32.zip).
Downloaded archive SHA256:
`b8b377642b3eb45610226fdf96fbc61d7c012a512bdd7f8c904a9c1ac88328af`.
Read `SCServo/SMS_STS.h`, `SCServo/SMS_STS.cpp` and `SCServo/SCS.cpp` without
importing/executing vendor examples. The pinned RoArm firmware archive does not
bundle these library files, so this is not proof of the arm's linked library.

The operator's earlier photo visibly labels one servo ST3235. It does not identify
every joint or firmware revision. [Waveshare's ST3235 documentation](https://www.waveshare.com/wiki/ST3235_Servo)
lists position, speed, load, voltage, current and temperature feedback. Exact
installed servo identity/register compatibility remains a deployment prerequisite.

## Candidate reference register map — NOT an executable allowlist

| Field | Address / width in reference | Notes |
| --- | --- | --- |
| Model | 3 / 2 bytes | Must establish model-number interpretation separately |
| CW / CCW deadband | 26 / 1; 27 / 1 | Read-only investigation of configuration, never change automatically |
| Operating mode | 33 / 1 | Direct read only; cached mode helper is unsafe in this archive |
| Torque enable | 40 / 1 | Missing is unknown, not disabled |
| Acceleration | 41 / 1 | Raw setting; do not claim calibrated acceleration |
| Goal position | 42 / 2 | Register readback, separate from host request or controller echo |
| Goal speed | 46 / 2 | Raw setting |
| Torque limit | 48 / 2 | Raw setting, not calibrated force |
| Present position | 56 / 2 | Sign-magnitude bit 15 in helper; mode/offset semantics matter |
| Present speed | 58 / 2 | Sign-magnitude bit 15 |
| Present load | 60 / 2 | Sign-magnitude bit 10; not force |
| Voltage / temperature | 62 / 1; 63 / 1 | Verify scaling before physical units |
| Moving | 66 / 1 | Not independently sufficient for arrival |
| Current | 69 / 2 | Sign-magnitude bit 15; scaling requires verification |

`SCS::readWord` performs a two-byte read and returns -1 on a short read. Preserve
read status separately from signed values: a negative measurement is not by itself
a failed acquisition. Also capture the library/protocol error status; a returned
byte count alone should not become proof of a healthy servo.

## Cache/freshness boundary and discovered reference defect

`SMS_STS::FeedBack(ID)` reads addresses 56 through 70 (15 bytes). It returns -1
and sets an error when the returned length differs. Helpers with ID=-1 consume
the cached buffer; they do not start a new acquisition. Only decode cached fields
after a successful read for the same servo, and retain its timestamps/sequence.
Capture the block/error before another transaction overwrites shared state.

In this archive `ReadMode(-1)` indexes mode address 33 relative to buffer start 56:
index -23, outside the buffer. Do not call that cached helper. This is a source
defect in the reviewed archive, NOT an established cause of our reverse-motion
issue and NOT proof that the installed firmware uses this code path.

Goal position and operating mode are outside the feedback block and need separate
successful reads with their own validity/time intervals. A single shared timestamp
must not imply simultaneous or atomic readback of all registers.

## Consequences for our diagnostic contract

1. Bind a reviewed register profile and servo identity to the producer; do not
   allow UI-provided arbitrary addresses.
2. Preserve separate target and position acquisition intervals. The current v1
   synthetic trace uses one interval and must be extended before claiming actual
   separate bus reads are correlated adequately.
3. Preserve raw unsigned words, decode sign-magnitude per field/profile, and record
   explicit read status. Current v1 nonnegative-count scope is a restricted fixture,
   not a universal protocol decoder.
4. Add health/configuration read validity and units. Do not treat load/current as
   calibrated contact force or configuration readback as permission to change it.
5. Identify the installed controller build and its linked library before preparing
   a deployment patch. Any firmware upload still requires explicit authorization.
6. Keep one bus owner; no second master and no vendor demo startup routines.

Next software work: reference-profile decoding tests and v2 evidence records for
separate acquisitions. Then injected producer tests and wizard integration. Live
readback stays UNKNOWN until the installed-compatible producer is reviewed/tested.

## Write-return semantics reviewed for the producer

## Read-response identity defect reproduced (2026-09-18 UTC)

The same archive's `SCS::Read` (`SCS.cpp:172–203`) verifies checksum and payload
byte count, but does not compare response ID or response length with the request.
Consequently a wrapper that merely calls `Read`, checks count/error, then attaches
the requested servo ID would overstate acquisition identity.

`software/scripts/rehearse_reference_read_guard.py` compiles the actual hash-pinned
`SCS.cpp` against `firmware/diagnostics/test_reference_read.cpp`, whose only
transport is a prepared in-memory packet. Results:

| Reply for a 2-byte read from servo 14 | Original library return | Candidate return |
| --- | --- | --- |
| Correct ID 14 and length 4 | 2 | 2 |
| ID 15, otherwise valid checksum | 2 | 0 |
| Length 5, otherwise valid checksum | 2 | 0 |

Candidate adds `if(bBuf[0]!=ID || bBuf[1]!=(unsigned int)nLen+2){ return 0; }`
after the response header read and before payload read. This candidate was applied
only in the temporary test build. Verified export:
`wizard-20260918T010622609994Z-a504a8aa51b447359993742f2b1eefda`.
The report retains archive/member/candidate hashes and original/candidate results.

Read also returns before clearing `Error` when header acquisition fails. A failed
read's error must therefore be treated as unavailable unless separately captured
as valid for that transaction; old `Error` is not fresh servo health evidence.

Before native binding, use a reviewed identity-validating implementation and test
truncation, checksum errors, stale packets, read timeouts and resynchronization.
This is a demonstrated REFERENCE defect, not an installed root-cause claim. No
library was installed, no servo bus connected, and no firmware uploaded.

### Write-return details

Additional inspection of the same hash-pinned archive: `WritePosEx` calls
`genWrite`, which returns `Ack`. In `SCS.cpp:280–303`, ACK-disabled and broadcast
paths return 1 without receiving a response. Therefore nonzero write return is
not by itself verified delivery. Preserve the ACK policy, exact return and device
error; unknown policy remains unknown. A failed acknowledgment may follow an
executed write and must not cause an automatic retry. The new portable C++ producer
tests these cases but does not identify or change the installed ACK configuration.

## Implemented decoder (offline only)

`servo_register_reference.py` now defines an immutable named reference map and pure
decoders for unsigned register words and the exact 15-byte feedback block. It
preserves raw words and the library's sign-magnitude interpretation, with no bus
access or physical-unit scaling. Goal position remains a raw register word pending
mode-specific interpretation. Byte order must be supplied explicitly for the block.
Mode and goal registers cannot be extracted from that block. Failed/unsupported
reads require null data and yield unknown values, never cached values or zeroes.

22 new tests cover signed negative one versus a failed read, both byte orders,
block bounds, invalid types/ranges and exclusion of out-of-block fields. Combined
with diagnostic contract/decoder tests, 57 passed. V1 trace/replay behavior is
unchanged. Separate acquisition timing and v2 producer binding remain next work;
this decoder does not establish installed compatibility or prove sensor freshness.

## Separately timed read-pair contract

`servo_acquisition_pair.py` now validates target-register and feedback-block reads
independently. Each carries boot/command/servo identity, sequence, register address
and width, read interval, status, device error and exact raw bytes. Successful
reads require explicit zero device error. Failed reads cannot reuse old bytes.
The pair enforces the pinned profile, ordering after dispatch/previous samples,
single-owner nonoverlapping intervals and a caller-declared maximum correlation
window. Either read order is allowed; no simultaneous-read claim is made.

This building block returns raw target and signed feedback separately, with no
endpoint or hardware authority. It is not yet connected to a live producer or the
full diagnostic trace decoder. Existing v1 exports remain unchanged. Eighteen new
tests and 34 register/export regressions passed (52 total). Next integrate this
contract into a versioned complete trace with explicit capability/producer metadata
and simulation/export/UI coverage before considering installed deployment.

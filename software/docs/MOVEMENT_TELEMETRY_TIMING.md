# Telemetry timing for movement characterization

## Implemented representation

`rocell.powered_telemetry_observation.v2` adds `read_windows`, with columns:

`[start_byte, end_byte, host_read_started_ns, host_read_finished_ns]`

Offsets refer to the original capture bytes; intervals are half-open. Timestamps
use the same monotonic host clock as the enclosing observation. Read finish is
recorded before parsing, so framing time does not inflate the measured read call.
Failed reads retain a zero-length coverage interval and an observation error;
any bytes obtained during cleanup are retained separately, without an invented
in-window timestamp. The maximum remains 512 read calls and 64 KiB capture bytes.

Rows are arrays to avoid repeating dictionary keys across hundreds of reads.
The supervisor's existing 4096-node limit has not been relaxed.

## Validation

- Exact row shape and integer types, no Boolean timestamp coercion.
- One row per reported read call, no more than 512.
- Contiguous byte coverage from zero to the accepted raw byte count.
- At most 256 returned bytes per read, including explicit empty reads.
- Ordered host intervals bounded by observation start/finish.
- Existing raw-byte reconstruction, zero-write and cleanup checks remain intact.

Tests: **45 passed in 25.63 seconds**, basetemp
`pytest-telemetry-timestamps-20260912-02`: telemetry wire/collector/public action,
native archive imports and framing/full-capacity IPC. Tests use memory inputs or
synthetic physical-shaped worker results, not the connected arm.

## Meaning and limitations

A frame ending inside a read became available to this collector by that call's
finish. It may have been generated earlier or buffered. Multiple frames from
one read do not have independently known measurement times. Frames crossing read
boundaries can be associated with their first/last contributing calls, not
assigned an invented uniform cadence.

Future movement analysis should report host-observed latency/settling bounds and
sampling gaps, disclose buffering uncertainty, and avoid claiming servo-internal
timing precision. Identical stationary values are still not freshness proof.

## Actual physical capture: 2026-09-12 23:24 UTC

Public wizard operation `operation-a5afb35b43a847e58ada659c61121297`
succeeded with `UNSOLICITED_TELEMETRY_CAPTURED`; native result was
`CAPTURED_CLOSED`, with zero confirmed writes, clean serial closure and confirmed
process-tree exit. This was a real operator-confirmed capture, not a simulation.

- 56,384 retained bytes; 255 complete parsed pose samples and one rejected line.
- 323 timestamped reads, none empty. Read-completion gaps: minimum 0 ms,
  median 16 ms, maximum 31 ms. These are host read gaps, NOT firmware sample rate.
- The 256-record parsing cap was reached. Bytes [53151, 56384), totaling 3,233,
  remain retained but unparsed; therefore parsed samples do not cover the entire
  capture. The byte-capacity limit itself was not reached.
- Voltage, torque-switch state and tG remain absent. Freshness and motion
  qualification remain unverified. No movement command was sent.

Verified export relative to `software/runs/wizard-exports`:
`wizard-20260912T232404247125Z-19c8b63e3aa54dcb9ff472dc0d9c23d1`.
Manifest SHA-256:
`31150c975bb0cb335615f6907ecb109d35f8aa015ef962742a44eb35cfb9ca1b`.
Outcome SHA-256:
`fb1266eb25edd3f7a79b84d20d7e40d90d84ff297094eb6c3bf4326af9559fb8`.

Read timing was calculated from retained native stdout after checking its SHA-256
against the export process record. Earlier v1 records remain historical untimed
captures; no read windows were synthesized for them.

Next software work: finite test-matrix simulation and full-window telemetry
coverage. Next physical stage: a separately qualified small slow movement and
telemetry-response check, before any multi-pose or speed sweep.

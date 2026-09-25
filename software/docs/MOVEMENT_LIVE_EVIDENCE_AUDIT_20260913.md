# Actual-unit evidence audit — 2026-09-13

Status: live movement not qualified. This audit inspects production diagnostic
and export roots, not pytest fixture directories. No device was opened during
the audit. It is not an approval or a replacement for original evidence.

## Available observations

- Recent actual supervised metadata identifies CP210x 10c4:ea60, serial
  `52E4E1E8337FEF119E92181CEDD322A4`, COM7. Metadata does not establish arm model,
  firmware, electrical power, clearance or calibrated position. Retained timing
  evidence is in [the metadata report](MOVEMENT_METADATA_TIMING_20260913.md).
- Two actual zero-command telemetry captures are documented in
  [the baseline report](MOVEMENT_BASELINE_20260913.md). They contain stable
  reported poses, not proof of current physical pose or response to a command.
- `ARM_RECEIVED_FIRMWARE_HISTORY.md` retains Jack's report that firmware is
  unchanged since delivery. It explicitly leaves installed version/binary hash
  unknown. `MOVEMENT_COMMAND_REVIEW.md` reviews pinned vendor reference source,
  not the installed binary. Do not relabel either as binary verification.
- The latest powered setup original is
  `operation-7339b425eb6643ca8bfc06b682d773af-powered-startup-original.json` in
  `software/runs/wizard-diagnostics/`, recorded at monotonic ns 199920828000000.
  At audit clock 203913140000000, it was approximately **66.54 minutes old**;
  the current-setup window is five minutes. Its power/clearance/stationary fields
  are historical operator reports, with firmware identity UNKNOWN, voltage null
  and startup motion unknown. Do not refresh its timestamp.

## Reference-by-reference state

| Required original | Available basis | Remaining qualification/assembly |
| --- | --- | --- |
| Configuration | Implemented typed command limits and serial code | Freeze the actual trial configuration and its exact original |
| Firmware review | Unchanged-delivery report and vendor source review | Explicit limited command-compatibility decision; keep installed binary unknown |
| Geometry | Physical build history and nominal simulator | Review the selected noncontact route and complete arm/cable envelope; tip simulation alone is insufficient |
| Received unit | Operator model/MAC history and current USB metadata | Retain explicit association with the current 52E4… unit; no model inference from bridge VID/PID |
| Native controller | Actual current diagnostic snapshots | Construct reviewed binding from actual identity/model/firmware/boot/profile originals, not placeholder digests |
| Operator presence | Historical setup record | New factual confirmation and final explicit operator input |
| Shutdown review | Earlier operator setup context | Confirm current access and gravity-drop clearance; serial cancellation is not a physical stop |
| Baseline qualification | Retained earlier zero-command captures | Fresh baseline and review of reported pose/limits for the chosen trial |

Source and build-snapshot hashes are reconstructed by existing code; they must
match the eventual draft and cannot be copied from an older source revision.

## Important exclusions and counts

An older section of `ARM_USB_RECEIVED_UNIT_PROGRESS.md` refers to USB serial
`A02C8734397FEF11A7321C1CEDD322A4`. That is not the currently observed 52E4… serial.
Do not merge those bindings or treat a COM-port name as proof they are the same
USB device. Preserve the historical record rather than rewriting it.

At audit time, direct production-root checks found:

- Zero `*-engineering-review-original.json` files in `wizard-diagnostics`.
- Zero `*-native_controller_review_sha256.original.json` files there.
- Zero `*-endpoint-report.json` files directly in `wizard-exports`.

These scoped findings mean the new production endpoint evidence set has not
been assembled and no native endpoint report is available in its assigned
publication root. They do not assert that similarly named files cannot exist
elsewhere. Passing tests contain synthetic records and are excluded.

## Next physical-stage sequence

1. Obtain a current factual setup confirmation: operator beside secured arm,
   supplied adapter switched on, USB connected, full arm/cable area clear and
   power shutdown reachable with the gravity-drop area clear.
2. Refresh supervised identity/baseline observations. Opening serial can cause
   startup movement; do not infer that a zero-command capture is risk-free.
3. Assemble actual originals and select one small, slow noncontact trial; record
   the explicit engineering decisions without inventing unknown facts.
4. Install the reviewed draft through the new host service method and use the
   final-confirmation path. Keep the original time budget and one-use gates.
5. Retain the actual endpoint result before considering a return, repetition or
   speed increase. No full sweep or contact tasks are authorized by this audit.

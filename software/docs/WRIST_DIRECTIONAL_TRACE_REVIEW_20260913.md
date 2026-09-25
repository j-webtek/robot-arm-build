# Wrist directional response: retained-trace review

## Servo-read freshness finding — 2026-09-14 UTC

Re-downloaded the [official source archive](https://files.waveshare.com/wiki/RoArm-M3/RoArm-M3_example_20260701.zip)
and verified SHA-256 `a28247fee0bbb65cc034ff206031b8700d2b1ec8e3a1fa4b1a5a7365c55f1a57`
before inspecting it in memory. No source was executed, installed or flashed.
Paths below are relative to RoArm-M3_example/.

- `RoArm-M3_module.h:72–100`: successful getFeedback reads position, speed,
  load, voltage, current and temperature. On failure it clears current,
  temperature and torque status and marks status false, but leaves cached
  position, speed and load unchanged.
- `RoArm-M3_module.h:625–642`: the angle-feedback routine calls getFeedback
  for each joint without checking its return value, then computes angles from
  the cached positions.
- `RoArm-M3_module.h:648–681`: T1051 publishes angles, loads, torque switches
  and supply voltage, but no per-joint successful-read status, acquisition
  timestamp, read sequence, position age, speed or temperature.
- `uart_ctrl.h:60–63`: T105 invokes these feedback routines. A query alone
  therefore does not prove that every underlying servo read succeeded.
- `RoArm-M3_config.h:96` uses 4096 position steps; `RoArm-M3_module.h:54–55`
  converts wrist steps to radians. One step is 0.087890625 degrees. The
  observed 0.748–0.967-degree misses exceed one step; integer resolution alone
  is not an adequate explanation under this reference model.

This is a source-level failure mode, NOT a diagnosis of the installed arm or
proof that its firmware matches this archive. The captured unit also omits
some fields present in this reference. Do not infer installed behavior or
read success from unchanged-since-delivery history or matching JSON type.

### Implication for automatic campaigns

Controller-reported endpoint settling remains a useful diagnostic, not fresh
physical-position proof. A cached-at-target stream could pass the reported
endpoint gate. Neither host timestamps nor a longer constant-report dwell
can distinguish it from fresh stationary samples. Existing freshness and
physical-accuracy flags must remain false; unattended release stays held.

The required supported diagnostic path should expose, for each joint:
successful/failed acquisition status, monotonic acquisition sequence/age,
raw position and commanded goal; speed, voltage, temperature and load when
actually available. On failed reads, position must be explicitly stale rather
than silently current. Host parsing must reject resets, stale/failed samples,
wrong joint/command association and unsupported protocol versions. Preserve
original bytes and all missing fields; never replace unavailable values by zero.

Next evidence should come from identifying the installed firmware and a vendor-
supported read-only diagnostic interface. If none exists, propose a versioned
firmware extension for review and bench validation. Do not flash or modify servo
registers as an implicit part of this investigation. Such an extension needs
explicit deployment approval and cannot itself prove a physical emergency stop.

## Positioning attempt outcome — 2026-09-14 UTC

The proposed -4-degree positioning test was performed as one independently
admitted move, operation-1f968b0dfb5d44fa8be8b76c79fcb26a. It ended at reported
-3.251953116 degrees, +0.748046884 degrees from target: TARGET_MISSED.
The final reported value was constant for at least 3.734 seconds. Complete
capture, unchanged other joints and clean transport were recorded. Consequently
the sequence below stopped at step 4; the positive approach to zero was NOT run.
Being below zero is not equivalent to passing the positioning leg. Repeated
misses cannot be converted into an accepted campaign by starting new sessions.

## Matched-target diagnostic decision — 2026-09-14 UTC

The absolute-target interface is now implemented and has physical evidence.
This supersedes the earlier statement below that only relative motion is available.
Two absolute trials remain confounded by target: the positive approach to 4 deg
ended at 3.7793 deg, whereas the negative approach to 0 deg ended at +0.9668 deg.
Do not call their difference a measured direction-only effect.

The next discriminating target is **0 degrees**, approached from below. Its
negative-approach reference is operation-b9fae47e71b8403ca09a916f85f4dcca.
All moves remain joint 4, spd 20, acc 1, with the existing 0.5-degree endpoint
tolerance, 5-degree maximum displacement and six-joint fresh-baseline checks.

1. Acquire a new owned zero-write capture. The last retained +0.9668-degree
   report is historical, not sufficient for a new command. Check source/unit,
   acquisition coverage, all-joint stability and clearance assumptions.
2. If the complete fresh baseline permits it, prepare one absolute -4-degree
   diagnostic. From the last report the displacement would be -4.9668 degrees,
   close to the existing five-degree cap. Do not round the start or relax the
   cap to make it fit. If any baseline sample exceeds the limit, hold.
3. Execute at most once under a new exact admission. Preserve the original
   command, trace, endpoint result, process receipt and export. This is a
   diagnostic positioning trial, not a successful campaign leg by definition.
4. If it misses, stop the sequence. Review the plateau and new endpoint;
   never automatically issue the zero-degree command, retry -4, or compensate.
   A later independent diagnostic requires a separate reviewed decision and
   fresh capture. Any invalid feedback, excursion, other-joint change or
   uncertain cleanup also holds further motion.
5. Only after the positioning result is accepted, obtain a fresh baseline below
   zero and separately admit a single absolute zero-degree approach. Reject
   it unless all samples satisfy the existing displacement/direction bounds.
6. Compare the retained zero-degree results, retaining source/runtime identities,
   starting positions, error, acquisition completeness and plateau spans. One
   sample each is exploratory evidence, not reliability or calibrated accuracy.

This document creates no admission, automatic sequence, or release. No command
was sent while preparing it. The outstanding matched-target measurement must
not be represented as completed by the simulation or by the differing-target
trials. Voltage, temperature and servo register diagnostics remain unavailable
through the reviewed motion path; no speculative PID/configuration writes.

## Configuration-query review — 2026-09-14 UTC

Re-fetched the pinned official archive below and checked its SHA-256 before
inspecting the JSON command definitions and dispatcher in memory. T108/T109
set/reset joint PID; T503 sets servo PID. T501 changes ID and T502 resets the
midpoint. None is a read-only diagnostic query. No read-only PID/deadband query
was identified in this reference command path; this is not proof of every
installed firmware capability. No command was sent and no firmware was flashed.

The latest retained T1051 records contain position/geometry fields and tB, tS,
tE, tT, tR. They do not contain voltage, temperature, commanded goal, device
sequence/timestamp, or movement-state fields. Raw tT ranges from -17 to 73 and
ends at 49, but it is not a calibrated torque or proof of the shortfall's cause.
Do not populate missing sensor values with zero or silently infer them from
the capabilities of the underlying servo. Obtaining register-level diagnostics
requires a separately reviewed supported transport/firmware path, not trial
commands through the current motion-only admission.

The current one-use observational intent authenticates a relative policy and
direction, not an absolute target. Same-target diagnostics therefore require a
versioned policy propagated through review, baseline selection, native command
matching, result reconstruction and UI preview; do not merely replace the rad
field after approval or chain repeated relative corrections.

## Additional physical trace — 2026-09-14 UTC

Reconstructed operation `operation-98a13adedc3d4e3fb08f7151df04f403` from the
verified export `../runs/wizard-exports/wizard-20260914T015705414159Z-b27c142d888e44d99ae0b524aff8a98f`.
The result attachment's retained post bytes passed byte-length and SHA-256
checks (`a80676ea9523a4b20c60a2dcdcfab1adaeb76c06aab2b6815818c12abd4a086b`).
The existing `_window` reconstruction returned 280 complete pose records and
no joint-record or host-gap issues in the selected complete-frame interval.
Documented acquisition-edge fragments remain excluded, not silently discarded
interior records.

The final reported wrist angle was 1.845703 degrees, first seen 1.297–1.313 s
after write completion. The last **203 records** repeated that value over a
conservative **3.609 s** host-time span. All other reported joint spans were
zero. Against the 0.976563-degree target, the final error was +0.869141 degrees:
still a target miss under the unchanged +/-0.5-degree criterion.

This strengthens the evidence that simply allowing more than five seconds is
not the leading correction: the reports had already plateaued well before
capture ended. It does not establish actual servo-sample freshness, identify
deadband/friction/backlash as the cause, or justify compensating overtravel.
The same-absolute-target, opposite-approach experiment below remains the
discriminating next motion test after its bounded policy is implemented and
reviewed. No new device access was used for this follow-up analysis.

No device opened and no command issued during this review. Raw post-capture
lengths and SHA-256 values were verified before complete-frame reconstruction.
All four framed intervals passed the existing joint-record and host-gap checks;
the first trial's incomplete acquisition remains incomplete, regardless.

## Observations

All commands used T101, joint 4, spd 20, acc 1. Angles below are controller
reports, not independently measured physical angles. Two trials per direction
at differing starting positions are preliminary evidence, not qualification.

| Attempt suffix | Requested change | Reported change | Final target error | Capture | Final constant-report span |
|---|---:|---:|---:|---:|---:|
| cffa673dd2f14d9fa07b3d9ad0ec03c5 | -5 deg | -4.0430 deg | +0.9570 deg | 3.922 s, incomplete | 2.562 s |
| 22687c57cccb43e8a0f0811e8ec905b6 | +5 deg | +4.7461 deg | -0.2539 deg | 5 s | 3.484 s |
| dd8557b674a5490dabdeb5b5f147b24f | +5 deg | +4.7461 deg | -0.2539 deg | 5 s | 3.766 s |
| 8782fb2d9d024ddaa58b0c68a07e2f8f | -5 deg | -4.0430 deg | +0.9570 deg | 5 s | 3.391 s |

Each source is `../runs/wizard-exports/operation-<suffix>-observational-stdout.original.json`.
Reconstruction used `rocell.arm.first_motion_analysis._window`, retaining the
documented unobserved attachment fragments and inspecting every complete line.
Constant-report spans conservatively run from the end of the first read spanning
the final repeated angle to the start of the last read spanning that angle.

The latest negative trial first reported its final angle about 1.531 s after
write completion, then repeated it for at least 3.391 s. Both positive trials
entered the existing +/-0.5-degree diagnostic target band and held it; both
negative trials ended outside it. All other reported joint spans were zero.
This supports a repeatable direction-dependent shortfall in the available
controller reports. It does not prove servo sample freshness or mechanical cause.

## Reference firmware comparison

Reviewed the [official reference archive](https://files.waveshare.com/wiki/RoArm-M3/RoArm-M3_example_20260701.zip)
in memory, without executing or installing it. SHA-256 matched the existing pin:
`a28247fee0bbb65cc034ff206031b8700d2b1ec8e3a1fa4b1a5a7365c55f1a57`.
This is **not verification of the installed firmware**.

Within `RoArm-M3_example/`:

- `uart_ctrl.h:16-22` passes the T101 joint/radian/speed/acceleration fields.
- `RoArm-M3_module.h:36-37` rounds radians to 4096-step revolutions.
- `RoArm-M3_module.h:364-370` constrains wrist to +/-pi/2 and sends the rounded
  target plus the configured middle position to WritePosEx.
- `RoArm-M3_config.h:94-96` defines middle position 2047 and range 4096.
- `RoArm-M3_module.h:54-55` converts wrist feedback with a pi offset, equivalent
  to 2048 counts. This one-count convention difference is about 0.0879 degrees;
  rounding contributes at most another half-count. Neither by itself explains
  the approximately 0.957-degree negative-direction shortfall.

The [servo documentation](https://www.waveshare.com/wiki/ST3215_Servo) describes
step-based position/speed control. Encoder-step resolution must not be treated
as guaranteed achieved position accuracy.

## Conclusion and next discriminating test

Merely extending the five-second capture is not the leading fix: the reported
negative endpoint was already constant for over three seconds. Directional
servo control/deadband, loading/friction, mechanical play, or differences in
installed firmware remain hypotheses. These traces cannot distinguish them.

Do not loosen the target criterion, add compensating overtravel, change PID,
write servo EEPROM or increase speed to force a pass. The command/observation
loop is functioning; precision behavior is what needs characterization.

Next useful motion experiment: compare approaches to the **same absolute wrist
target** from each direction at the same speed, retaining baseline and full
telemetry per leg. Current relative-only tests do not isolate approach direction
from endpoint position. Such a test needs an explicitly bounded target policy;
do not emulate it through unchecked repeated corrections. First review read-only
firmware/servo configuration capabilities to see which installed values can be
retrieved safely without reset, calibration or persistent writes.

# Elbow direction-dependent response: evidence and next discriminator

Updated 2026-09-17, after the 19:37 UTC trial. No hardware settings were changed
as part of this review. This is not an installed-firmware identification.

## Retained observations

| Trial | Requested change | Reported change | Interpretation |
| --- | ---: | ---: | --- |
| Earlier small decreasing, elbow 1.67357304 | -.015666734 rad | 0 | No reported response at that posture |
| Increasing, same starting elbow | +.012 rad | +.018407769 rad | Correct direction, overshoot |
| Decreasing, new elbow 1.691980809 | -.008 rad | 0 | No reported response at the new posture |

The last two exports are
`wizard-20260917T193314387752Z-d975fcaf16c34888a2ab6f69bce92c81` and
`wizard-20260917T193723231482Z-4f2c92274eb740ea8b8007d588c8a64b`.
Wrist commands previously changed reported state and completed repeated local
cycles. This argues against universally frozen feedback; it does not certify
individual encoder reads or rule out load, friction, deadband, control settings,
or installed-firmware behavior.

## Official-source review

Reference archive:
https://files.waveshare.com/wiki/RoArm-M3/RoArm-M3_example_20260701.zip

Verified SHA256:
`a28247fee0bbb65cc034ff206031b8700d2b1ec8e3a1fa4b1a5a7365c55f1a57`.
Downloaded and inspected in memory only; not flashed or executed.

- `RoArm-M3_module.h:350-358`: elbow speed is described as servo steps/second;
  goal counts are calculated from radians, offset by 1024 and clamped. The
  function forwards speed/acceleration to `WritePosEx`.
- `RoArm-M3_module.h:770-782`: single-joint control forwards the supplied values
  to the elbow helper. Increasing elbow angle is described as moving down.
- `json_cmd.h:373-388`: commands 501, 502 and 503 change ID, midpoint and PID,
  respectively. They are NOT read-only servo-status queries. Do not issue them
  speculatively to diagnose the problem.
- No numeric deadband or read-only deadband query was established by this review.
  Do not invent an installed deadband value from the no-response observations.
- The reference feedback path can retain old position on acquisition failure
  (see TIP_REVERSE_FIRMWARE_DIAGNOSIS.md). Interface agreement is insufficient
  to prove fresh acquisition.

Waveshare's [ST3215 documentation](https://www.waveshare.com/wiki/ST3215_Servo)
also describes speed in steps/second. The user's earlier image visibly labels
a servo ST3235; its [official documentation](https://www.waveshare.com/wiki/ST3235_Servo)
describes 4096-position encoding and feedback capability. Do not treat a library
example or a product-family page as proof of installed register settings.

## Selected next comparison

**Executed 19:42 UTC:** speed 40 produced the same unchanged reported elbow as
speed 20. Wire and reserved metadata both retain 40/1. Verified export
`wizard-20260917T194218360472Z-ab9990310e9141fe8cdef162b3bac6d0`.
The speed hypothesis did not resolve the no-response. This branch is stopped;
the procedure below is historical, not an instruction to repeat it.

Prepare a separately named single-command trial from the exact reported posture
`[.001533981,.033747577,1.691980809,-.052155347,.018407769,3.138524692]`:

- Same T101 joint 3 goal: 1.683980809 rad.
- Explicit speed 40 rather than 20; acceleration remains 1.
- Same under-3-mm commanded hypothetical-tip arc and 6-mm feedback-time bound.
- No change to torque, PID, calibration, mode, firmware or servo registers.
- Record the changed speed in both wire command and reservation configuration.
  Existing reservation metadata currently hardcodes 20 for single-joint trials;
  update it from the exact admitted command before adding this variant.
- Require fresh identity/posture checks, offline command/metadata/fault tests and
  durable preflight before execution. At most one send; no return or retry.
- Compare direction, counts, timing and final state with the retained speed-20
  run. A changed response supports speed-dependent behavior, not a root cause.
- If no reported response persists, stop this branch of movement experiments.
  Seek direct servo/read-status or physical observation evidence before any
  change to gains, torque or larger movement envelope. Do not fit an inverse
  correction to zero-response points.

This is a diagnostic speed comparison, not a faster task profile or a qualified
return to the wrist-cycle posture. The 100 mm tool remains hypothetical and
camera/contact/keyboard qualification remain deferred.

# RoArm-M3 Pro: wrist endpoint shortfall and diagnostic capability

Draft for owner review. **Not sent.** Do not attach full workspace exports
without reviewing their local paths, device identifiers and other private data.

## Message

We are integrating a RoArm-M3 Pro through USB serial on Windows. The owner
reports factory firmware unchanged since delivery, supplied power adapter on,
and a secured installation. We have not verified the installed firmware build.
We are testing low-speed single wrist-pitch commands before board calibration.

Each test sends exactly one T101 command for joint 4, spd 20, acc 1. We collect
a new baseline and five seconds of post-command T1051 telemetry, then close
the connection. There are no automatic retries, returns, compensation or PID
changes. Successful byte transmission and controller-reported position are
recorded separately from physical accuracy.

| Start reported (deg) | Target (deg) | Final reported (deg) | Final error (deg) |
|---:|---:|---:|---:|
| 1.845703 | 4 | 3.779297 | -0.220703 |
| 3.779297 | 0 | 0.966797 | +0.966797 |
| 0.966797 | -4 | -3.251953 | +0.748047 |

The last two tests had complete post-command captures with no detected host
coverage gaps or other-joint changes. Final values repeated for at least 3.906
and 3.734 seconds respectively, excluding edge-read duration uncertainty.
They failed our provisional +/-0.5-degree diagnostic criterion. We are not
claiming this criterion is a published product accuracy specification.
The positive and negative approaches above used different targets, so they do
not yet isolate direction as the cause. We stopped progression after misses.

Example last command (radians):

```json
{"T":101,"joint":4,"rad":-0.06981317007977318,"spd":20,"acc":1}
```

Our captured T1051 data contains joint angles, geometry and tB/tS/tE/tT/tR;
it lacks per-joint successful-read status, sample age/sequence, voltage and
temperature. In reference source `RoArm-M3_example_20260701.zip`, getFeedback
leaves cached position unchanged after a failed servo read, and the angle
publisher appears to use that cache without checking the return value.
We do not know whether our installed firmware shares that behavior.

Could you clarify:

1. What supported **read-only** method identifies the installed firmware/build
   without flashing, homing, torque changes or resetting the arm?
2. Is there a supported USB diagnostic command exposing per-servo successful
   read status, raw position, goal position, speed, voltage and temperature?
   How can stale cached position be distinguished from a fresh stationary read?
3. Are the observed shortfalls expected at these speed/acceleration settings?
   Which documented deadband, resolution, load or control parameters apply to
   this Pro wrist joint? Please suggest diagnostics before configuration writes.
4. What is the documented stop behavior for a directly issued T101 goal that
   has already reached the servo? Does T0 halt it, or only interpolation and
   queued/mission motion? What supported watchdog handles host/USB loss?
5. Why might our T1051 field set differ from the current reference example,
   and which reference source corresponds to our installed product build?

We can provide original command/telemetry records through the owner after
privacy review. Please identify any proposed action that changes flash, EEPROM,
servo parameters, torque or controller state so it can be separately reviewed.

## Local evidence map (remove before sending if unnecessary)

- +4-degree attempt: `operation-f05531b8aa8e4f969af7309d8a26d115`.
- Zero-degree attempt: `operation-b9fae47e71b8403ca09a916f85f4dcca`.
- -4-degree attempt: `operation-1f968b0dfb5d44fa8be8b76c79fcb26a`.
- Reports under `software/runs/wizard-exports/`, suffix
  `-absolute-wrist-report.json`; originals retained beside them.
- Latest verified export:
  `wizard-20260914T035142470717Z-731985c535f64d5b8d6f5347f89a861b`.

## Sources checked

- [Waveshare command documentation](https://www.waveshare.com/wiki/RoArm-M3-S_JSON_Command_Meaning).
- [Official reference archive](https://files.waveshare.com/wiki/RoArm-M3/RoArm-M3_example_20260701.zip),
  SHA-256 `a28247fee0bbb65cc034ff206031b8700d2b1ec8e3a1fa4b1a5a7365c55f1a57`.
- [Official SDK pinned revision](https://github.com/waveshareteam/waveshare_roarm_sdk/tree/d9893632aa7f5a9cb283136ab024faf3143ea7db):
  inspected roarm.py, common.py and generate.py in memory, not executed or installed.
  No firmware-version/per-servo freshness query identified in those inspected files;
  this limited search is not proof that no supported interface exists elsewhere.

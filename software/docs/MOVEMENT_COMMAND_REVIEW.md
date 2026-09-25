# Movement command review — 2026-09-12

Status: vendor documentation and pinned reference-source review; not installed
binary verification or live command admission. Source checkpoint: 2026-09-13.

The existing `CartesianGoal`/`RoArmM3` interface represents T104, while the
hardware-backed transport still holds motion. Retain that hold.

Waveshare documents T104 as endpoint inverse-kinematics control with a `spd`
parameter and blocking execution. Its speed follows a curve rather than a
constant physical velocity. Keep `spd` as a native coefficient; do not derive
mm/s or estimated travel duration from it without measurement. The documented
T104 example does not expose an `acc` parameter. Do not append the acceleration
field from a different command family to a T104 trial.

Source: [Waveshare robotic arm control](https://www.waveshare.com/wiki/RoArm-M3-S_Robotic_Arm_Control).
The [RoArm-M3 overview](https://www.waveshare.com/wiki/RoArm-M3) links this control
documentation; applicability to the received unchanged firmware still requires
qualification rather than assuming a known installed binary.

## Required follow-up before P2 completion or live selection

- Review the linked official firmware implementation and retain its version/hash
  as reference evidence, not as the installed unit's binary identity.
- Resolve the control page's broad coordinate-unit wording against individual
  axis definitions and implementation. Existing code represents XYZ in mm and
  pitch/roll/gripper in radians; do not change or certify it from an ambiguous
  summary sentence alone.
- Determine interpolation, coefficient constraints and telemetry behavior during
  the blocking command. Lack of concurrent telemetry may rule out this family
  for the intended monitored trial, even if endpoint motion works.
- Establish verified controlled-stop semantics, if available, independently of
  serial close. Do not interpret closing the host connection as stopping a move.
- Decide whether to retain T104 for initial constant-orientation XYZ trials or
  introduce a separately reviewed joint command. No arbitrary command escape hatch.
- Select actual trial displacement, speed ladder and tolerances only after
  geometry/clearance and observation prerequisites are available.

No command-family change, live numeric settings or movement was implemented by
this review. Simulation parameters must remain explicitly synthetic.

## Pinned reference-source inspection — 2026-09-13

Fetched the [official firmware archive](https://files.waveshare.com/wiki/RoArm-M3/RoArm-M3_example_20260701.zip)
into memory and verified SHA-256 against the existing simulation profile:
`a28247fee0bbb65cc034ff206031b8700d2b1ec8e3a1fa4b1a5a7365c55f1a57`.
No download was executed, installed or flashed. No device was opened. All line
references below are within `RoArm-M3_example/` in that exact archive.
The sketch displays version 0.84 at line 63; this is the reference sketch's
label, NOT the received arm's verified version.

### Movement and observation behavior

- `uart_ctrl.h:40–49` dispatches T104 with x/y/z/t/r/g/spd to
  `RoArmM3_allPosAbsBesselCtrl`. It does not pass acceleration.
- `RoArm-M3_module.h:1024–1035` rejects zero coefficient, sets goals and calls
  the blocking interpolation routine. Host validation must still reject
  negative, nonfinite and excessive work; the source is not a safe input gate.
- `RoArm-M3_module.h:854–873,895–936` uses cosine easing and maximum mixed
  XYZ/orientation delta (excluding gripper), advances by spd/delta, issues
  intermediate servo targets, delays 2 ms per loop and issues a terminal target.
  Bus calls, computation and servo response mean that 2 ms is NOT the move's
  sample cadence or a physical speed conversion. The gripper gets its target
  without the XYZ/orientation easing.
- `RoArm-M3_example.ino:179–205,213–215` dispatches commands before the normal
  feedback refresh, stall detection and telemetry work. The T104 loop does not
  perform pose feedback refresh. Therefore this reference does not establish
  continuous in-motion pose telemetry for a T104 trial. A queued T105 does not
  create an independent feedback thread.
- `RoArm-M3_module.h:625–642,648–681` refreshes servo feedback and generates
  T1051 from it. The reference includes voltage, gripper load and torque-state
  fields absent from our retained capture. Do not infer source/binary equality
  from matching pose math or the operator's unchanged-delivery history.

### Stop behavior and limits

- The sketch starts `serialTask` on core 0 (`RoArm-M3_example.ino:160–168`).
  `uart_ctrl.h:383–435` reads LF-terminated lines on that task. A compact T0
  substring sets StopFlag and drains queued commands outside the main dispatch
  path; a compact T999 substring clears it. This parser is whitespace-sensitive
  for its fast path, not equivalent to arbitrary JSON serialization.
- `RoArm-M3_module.h:895–897` checks StopFlag at the start of each interpolation
  iteration and returns. This ceases future interpolation from that routine,
  but does NOT issue an explicit servo hold/deceleration command, prove arrival
  at rest, or acknowledge physical stopping. The already-issued servo target
  can remain active. The terminal target at lines 934–935 has no additional
  immediately preceding StopFlag check.
- StopFlag is an ordinary shared bool (`RoArm-M3_config.h:251`); the inspected
  path provides no measured cross-task latency or safety-rated stop guarantee.
  An operator-reachable physical shutdown remains necessary; power removal can
  also remove holding torque, so the arm's fall/drop envelope must be clear.
- The separately named `emergencyStopProcessing` at module lines 174–177 releases
  torque for ten seconds and then reenables it. The reviewed T0 handler does
  not call that function. Do not conflate these behaviors or invoke torque
  release as a substitute for an independently qualified stop.
- Closing the host port, cancelling a worker or terminating its process is
  not a stop command. Never automatically clear a stop flag, replay a move,
  drain/retry movement writes, return home or advance to the next trial after
  an uncertain write/timeout/cancellation.

### Required executor decision

Keep T104 preview/simulation, but do not admit it as a continuously observed
pose/speed sweep on this evidence. Do not relax telemetry-gap policy merely
to make a blocking move pass. First resolve one of these explicitly:

1. Qualify a narrowly bounded T104 trial as an **endpoint-only observation**
   experiment with separate operator supervision/physical shutdown. It must
   not report missing in-motion overshoot as zero or certify path monitoring.
2. Review a separately bounded command family that leaves feedback scheduling
   available. Its units, servo stop behavior and admission tests require a
   separate contract; do not silently substitute T101 or direct T1041 commands.
3. Obtain independently timed external observation appropriate to the path.
   Current uncommissioned camera geometry is not that qualification.

These are engineering options, not authorizations. The eventual live executor
must bind the chosen observation contract to the exact trial, current hardware
evidence and reviewed response to faults. Firmware changes are outside this plan.

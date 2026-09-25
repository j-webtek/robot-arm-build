# Positional campaign stop review — 2026-09-13

Status: native campaign stop qualification **not established**. No device was
opened, commanded, flashed, torque-released, or stop-reset during this review.

## Pinned source evidence

Inspected the [official reference archive](https://files.waveshare.com/wiki/RoArm-M3/RoArm-M3_example_20260701.zip)
in memory and verified SHA-256:
`a28247fee0bbb65cc034ff206031b8700d2b1ec8e3a1fa4b1a5a7365c55f1a57`.
This does not establish the installed binary or installed behavior.

All paths below are inside `RoArm-M3_example/`:

- `json_cmd.h:1–7` defines T0 and T999 as stop/reset commands.
- `uart_ctrl.h:414–419` recognizes compact serial stop/reset text; stop sets a
  flag and drains queued commands. Reset clears the flag.
- `RoArm-M3_module.h:895–897` checks that flag during interpolation.
- `RoArm-M3_advance.h:253–258` checks it during mission playback.
- `uart_ctrl.h:16–22` dispatches direct T101 control. The wrist routine at
  `RoArm-M3_module.h:364–372` sends a servo target without a stop-flag check.
- `RoArm-M3_module.h:174–178` contains a separate torque-release function that
  waits ten seconds and reenables torque. The source search found its definition,
  not a call establishing it as the T0 handler.

The [vendor command documentation](https://www.waveshare.com/wiki/RoArm-M3-S_JSON_Command_Meaning)
also distinguishes torque unlocking from movement control and notes that later
movement can restore torque. Torque release is not a demonstrated safe stop.

## Engineering conclusion

Policy update: the user-approved bounded attended v2 workflow does not require
an emergency-stop qualification before its initial two small wrist movements.
Instead, it reviews the risk of an accepted goal finishing and keeps the whole
trajectory clear. The source findings below remain valid; no interruptible-stop
claim is made. Unattended release requirements are unchanged. See the current
priority section of AUTOMATED_POSITIONAL_TESTING_IMPLEMENTATION_PLAN.md.

The reference source does not establish that T0 arrests a direct T101 target
already accepted by a servo. Clearing a software queue is not cancellation of
that servo goal. Do not add automatic T0/T210/T999 actions as a claimed safe
campaign abort based only on their names or successful transmission.

The current software may stop admitting later commands, retain evidence, revoke
claims and close owned handles. Its reports must continue to say physical stop
is unverified. They must not suggest that an already-issued movement necessarily
ceased. This distinction applies to cancellation, stale feedback, uncertain
submission, worker termination and host loss.

## Required next evidence, without inventing measurements

1. Identify the installed controller behavior sufficiently to relate the actual
   unit to the reviewed command path. Unchanged-since-delivery is useful history,
   not a binary match or a stop qualification.
2. Select a stop strategy for the direct-joint profile with an explicit response
   to already-issued servo goals. Document gravity/load consequences before any
   power or torque interruption test. Do not automatically send a replacement
   target under the guise of stopping.
3. Qualify the strategy in an attended, cleared and bounded test, retaining
   command/capture timestamps and operator observations. Treat unavailable
   latency/position evidence as unknown rather than a pass.
4. Establish an independent protective response for host/USB loss before
   unattended use; a command sent over the failed channel cannot provide that.
5. Bind the qualification originals to the exact unit, firmware basis, tool,
   route, workcell, software and permitted failure response. A nonzero digest
   alone does not prove these conditions.

Native facade development can proceed without releasing execution. Neither this
document nor an authenticated operator review is a physical stop certificate.

## Software regression evidence

`software/runs/positional-stop-boundary-regression-20260913.xml`: **61 passed**.
Owned-campaign tests assert that failure handling submits no additional stop,
torque, reset or home commands and never reports a verified physical stop.
Unreleased physical provenance is rejected before IO. The existing single-trial
serial facade rejects campaign admission before native facade construction.
These assertions protect the current release boundary; they do not qualify an
actual stop method or make the full implementation plan complete.

# First actual-unit endpoint proposal

## Offline reference check completed

`software/scripts/bench_reference_kinematics.py` now reproduces the pinned
firmware FK/regular IK branch and checks 41 geometric subdivisions of this
proposal without accessing hardware. The official archive was fetched in
memory and its SHA-256 checked against the existing pin before transcribing
the equations. No firmware was installed or executed.

Retained result:
`software/runs/wizard-diagnostics/reference-kinematics-5ba387f8710f48108e3c8ac1773dd4d7.json`.
Reference FK versus reported pose residual is approximately `1.52e-7` mm and
`2.05e-10` radians in pitch. This is mathematical consistency, not physical
accuracy or freshness verification. The reference equations do not add `l1`
to reported Z; therefore do not interpret this Z as board height.

Predicted joint changes at the target: shoulder `-0.021812` degrees,
elbow `-0.767228` degrees, wrist `+0.789040` degrees; base effectively unchanged.
No sampled joint change exceeds 0.8 degrees. All 41 sampled points have a valid
regular-branch IK solution and FK roundtrip; finite sampling does not prove
continuous clearance, servo dynamics or that the installed firmware is identical.

Eight focused tests passed (`software/runs/bench-reference-20260913-01.xml`),
including invalid data, unreachable-target refusal and regular-branch roundtrips.
The script grants no physical authority. Adding it changes workspace source
fingerprints; any later endpoint draft must bind the new source, not an old hash.

Status: proposed, **not authorized or executed**. No return or second trial is
included. This selection is an engineering proposal under Jack's delegated
authority to choose incremental tests; it is not a claim that all gates pass.

## Posture and protocol reconciliation

The [official RoArm-M3 overview](https://www.waveshare.com/wiki/RoArm-M3)
defines the startup shoulder angle as zero and elbow angle as approximately
1.57 radians. The retained baseline reports shoulder 0.009203885 and elbow
1.613747789 radians. Together with Jack's current side-view confirmation, these
are consistent with the near-startup upright/horizontal posture. This is a
qualitative consistency conclusion, not an exact pose measurement.

The [official control definitions](https://www.waveshare.com/wiki/RoArm-M3-S_Robotic_Arm_Control)
identify +Z as upward, define the feedback angle fields, and describe T104 as
blocking, curve-speed endpoint control. The pinned source review in
`MOVEMENT_COMMAND_REVIEW.md` resolves XYZ millimeters versus angular radians.
Neither web documentation nor the photograph identifies the installed binary.

Identical reports from a stationary arm are not evidence of a fault. Conversely,
they cannot independently prove device sample freshness. Keep that distinction
without treating a suspected cached stream as a diagnosed hardware defect.

## One proposed trial

- Unit: `10c4:ea60`, serial `52E4E1E8337FEF119E92181CEDD322A4`.
- Frame: `R_ctrl`, not board coordinates or the URDF world frame.
- Change: **+2 mm Z only**, keeping X, Y, pitch, roll and gripper unchanged.
- Proposed T104 speed coefficient: **0.05**. This is not a known mm/s speed.
- No acceleration parameter, home command, torque change, queued return or retry.
- Use the existing fixed endpoint-only observation and native execution limits.
- Operator observation and accessible physical shutdown remain required;
  software cancellation is not a verified physical stop.

For offline review only, the 14:47 UTC baseline would imply:

| Quantity | Recorded start | Proposed target |
| --- | ---: | ---: |
| X, mm | 347.3156446 | 347.3156446 |
| Y, mm | -3.196743424 | -3.196743424 |
| Z, mm | 207.4284741 | 209.4284741 |
| Pitch, rad | 0.046019424 | 0.046019424 |
| Roll, rad | -0.003067962 | -0.003067962 |
| Gripper, rad | 3.149262558 | 3.149262558 |

These historical numbers are **not a command to send now**. A changed baseline
requires a newly reviewed draft, not silent target adjustment after approval.

## Why this candidate, and remaining gates

A small upward endpoint displacement avoids intentionally approaching the board
and avoids requested wrist/gripper rotation. That does not prove a safe swept
link/cable path or limit all joint movements: inverse kinematics determines
joint motion. Full-arm route review remains distinct from endpoint displacement.

Before executing, complete actual-unit firmware compatibility, baseline meaning,
native binding and route reviews, then the existing final-confirmation path.
Do not copy the feedback-only serial/compatibility approvals into motion reviews.
Keep the installed version unknown unless independently established. Retain
failures and refuse uncertain writes rather than progressing to a campaign.

## Observation after the trial

Retain raw pre/post telemetry, host acquisition times, command-write result,
cleanup result and the operator's observed response. A two-millimeter change
may be difficult to judge by eye. A clear endpoint telemetry response is not
automatically proof of full-path accuracy, overshoot, physical speed or contact
readiness. Only consider a separately specified next trial after reviewing it.

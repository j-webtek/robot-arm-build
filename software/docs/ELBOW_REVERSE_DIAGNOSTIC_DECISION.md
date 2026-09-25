# Reverse elbow: diagnostic decision

Updated execution plan:
[COMMAND_TO_SERVO_DIAGNOSTICS_PLAN.md](COMMAND_TO_SERVO_DIAGNOSTICS_PLAN.md).
The user selected nonvisual, command-correlated diagnostics. Video is not a
required next step; proceed with capability verification and software/simulation.
The ordered implementation and gates in that plan supersede the next-work list
below, which remains background for the decision.

Date: 2026-09-17. No commands, serial opens, firmware uploads, register writes,
torque changes or PID changes were made for this review.

## What the evidence establishes

- Local forward correction reached a reported endpoint within the declared modeled
  tolerance. Reverse to 1.79168956 from 1.807029368 did not change reported position
  at speed 20 or 40, acceleration 1. These are separate outcomes.
- The reverse request is ten nominal counts, not a rounding-to-zero request.
- The follow-up contains 113 unchanged samples over ~35 seconds. More stationary
  polling does not establish fresh servo acquisition.
- Earlier USB/HTTP captures already agreed on all six reported joints. The verified
  comparison at `wizard-20260917T190529522444Z-1eaf9e70d2a0476f9456361ba618fa6b`
  has a 1.062-second cross-channel gap, not a strict simultaneous acquisition.
  Agreement cannot rule out common controller state or failed servo acquisition.
- Retained command receipts prove host payload binding and HTTP receipt, not the
  servo's accepted goal register. No inference of hardware damage is warranted.

## Reference review and its limits

Re-downloaded the official archive in memory and verified SHA256
`a28247fee0bbb65cc034ff206031b8700d2b1ec8e3a1fa4b1a5a7365c55f1a57`:
[Waveshare reference archive](https://files.waveshare.com/wiki/RoArm-M3/RoArm-M3_example_20260701.zip).
Reviewed the command definitions and handler. This is NOT the verified installed
firmware; the installed HTTP behavior differs from this reference.

The command definitions contain T105 feedback but no exposed servo-goal-register,
PID-readback or per-acquisition-result getter. T108/109 change/reset PID; T112
changes torque limits; T501/502/503 change ID/midpoint/PID. None is a diagnostic
read. Do not send them to discover current state. T602 is a boot-mission-content
read in this reference, not a servo-register read or an installed-support guarantee.

The reference module calls `st.WritePosEx` for elbow control (line 358) and tests
`st.FeedBack(servoID)!=-1` for acquisition (line 73). Public feedback does not
retain a command-correlated record of these outcomes. The reference startup calls
dynamic adaptation with mode 0 and maximum limits; that does not establish the
installed settings. Do not infer current torque configuration from startup source.

[Waveshare's feedback documentation](https://www.waveshare.com/wiki/RoArm-M3-S_Robotic_Arm_Control)
describes angles, position, load and, in newer examples, torque switches and voltage.
Our retained packets omit torque-switch/voltage fields. Missing is unknown, not OFF
or zero. This documentation is shared/reference material, not installed detection.

## Useful evidence versus inconclusive repetition

| Question | Evidence needed | Current limitation |
| --- | --- | --- |
| Did the controller dispatch the requested goal? | Command ID/hash, computed servo ID/count/speed/acceleration, bus-write result | Host/HTTP receipt only |
| Did the servo accept that goal? | Supported readback of goal register with acquisition status | Not exposed by reviewed command interface |
| Is the position newly acquired? | Per-servo read result, device timestamp/sequence and value | HTTP timestamps describe transport, not sensor acquisition |
| Why did it not move? | Accepted goal, fresh position, operating mode/torque limit/PID/error data; physical observation where needed | Raw load alone is insufficient |

## Next work, in order

1. Inspect retained boot/interface artifacts for non-secret configuration clues;
   do not execute page scripts, boot missions or configuration setters. A boot
   mission read may be assessed separately against installed interface support,
   but cannot substitute for direct servo target/acquisition evidence.
2. Define an additive, read-only diagnostic packet for a future firmware adapter:
   command correlation, requested/accepted target distinguished, acquisition status,
   raw position count, time/sequence, and optional supported configuration readback.
   Simulate success, bus-write failure, stale acquisition and unavailable readback
   so the wizard reports the actual evidence level rather than false arrival.
3. Before deploying firmware instrumentation or using direct servo-bus access,
   review exact installed compatibility, backup/recovery and physical effects and
   obtain separate authorization. Do not flash firmware or connect a second bus
   master as an implicit next step.
4. Resume reverse characterization only with a reviewed discriminating test. Do
   not repeat the same speed/amplitude staircase. A wider noncontact trial needs
   its own reviewed trajectory; the historical offset implies a 21.63 mm sampled
   model envelope and is not admitted by the current 6 mm test.
5. Keep reported forward success and failed reverse records intact. Qualify return
   and repeatability before coordinated ghost press/retract. Simulation may advance
   the workflow but must not mark physical tests passed.

## Evidence references

- Forward: `wizard-20260917T212741969917Z-84e87697a9404f2a95a3a321374800bd`
- Reverse speed20: `wizard-20260917T213018314567Z-ebaacbf5eb60410ba58e880c6809b165`
- Follow-up: `wizard-20260917T213104814701Z-86eef1254d414e90bcb09785af62cc32`
- Reverse speed40: `wizard-20260917T213514249166Z-619a4a1004cd42a9a78f67f24018de83`
- Combined audit: `wizard-20260917T213545010729Z-d776091dd02344ed982ae903ed3b1d82`

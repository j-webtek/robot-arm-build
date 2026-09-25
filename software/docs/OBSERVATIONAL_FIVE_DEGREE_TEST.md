# Visible wrist commissioning test

User approved a slow 5-degree wrist test instead of a 90-degree turn.
The prior attempt `operation-183bc064c3db4b4294f4ba81c79f9a69` had zero
confirmed command bytes; the user subsequently reported **no movement**.
That observation is recorded here because the prior source-stale wizard cannot
accept a new observation record. It is not a signed wizard observation receipt.

## Approved bounded procedure

1. Verify software tests; restart the source-bound wizard without opening USB.
2. Select the exact reviewed RoArm-M3 Pro USB identity, retain current powered
   setup, and stage **5 degrees**, negative wrist-pitch direction.
3. Review displayed increment (-5 degrees), spd 20 and acc 1. Operator remains
   present with secured arm, clear movement area and reachable power shutdown.
4. Open once (opening itself can cause startup movement). Capture one second
   of owned telemetry. Require stable six-joint feedback and derive the exact
   absolute wrist target from that baseline; reject a target outside +/-10
   degrees. No homing, other-joint command or torque release.
5. Submit one T101/joint 4 command through authenticated admission, then retain
   five seconds of telemetry and close the owned connection. No return/retry.
6. Retain command-byte accounting, reported response, cleanup, and operator
   observation. Export logs. Failure does not authorize another attempt.

The policy is separately authenticated as
`FIVE_WRIST_DEGREES_FROM_OWNED_BASELINE_SPD20_ACC1_NO_RETURN`.
Existing one-degree approvals remain one degree; default setup remains one.
The wizard offers only 1 or 5 degrees, never an arbitrary angle. Reconstruction
uses the signed policy, not a UI summary. This is functional commissioning,
not board mapping, contact calibration or measured physical accuracy.

Host timing uses the existing 250 ms selected-sample admission allowance;
result reconstruction now uses the same constant rather than its older 100 ms
copy. Baseline-end recency, identity and all one-use checks remain unchanged.

Vendor reference: [RoArm-M3 joint control](https://www.waveshare.com/wiki/RoArm-M3-S_Robotic_Arm_Control).
T101 is single-joint radian control; joint 4 is wrist pitch. At 4096 steps per
revolution, 5 degrees is about 57 steps; spd 20 gives a nominal cruise-only
duration of about 2.85 seconds, excluding acceleration and device behavior.
The five-second observation window is not a guarantee of completion or stop.

## Verification and live outcome

Software report: `../runs/observational-five-degree-20260913-01.xml`.
Result: **287 tests passed in 71.13 seconds**. This includes exact +/-5-degree
targets, unchanged envelope rejection, approval substitution rejection, full
synthetic owned trial/result reconstruction, and public wizard setup/display.
Live outcome will be appended after a distinct current reviewed attempt.

### Live attempt: operation-cffa673dd2f14d9fa07b3d9ad0ec03c5

The fresh public wizard selected the expected USB unit and displayed -5 degrees,
spd 20, acc 1. One native command was issued: T101, joint 4,
rad -0.08880044359971648. All **64 bytes were confirmed written**, with
`write_completion_uncertain=false`. No return or retry was issued.

The one-second baseline completed. Post-command acquisition retained 46,138
bytes over 3.922 seconds but reached its 512-read ceiling before the planned
five seconds. Status: `POST_CAPTURE_INCOMPLETE` / `READ_CALL_LIMIT_REACHED`.
The lifecycle reported no errors, zero owned handles and zero pending I/O after
close. The supervisor confirmed process-tree exit. Closing serial is not a
physical stop, and this incomplete test is **not a functional pass**.

The last complete retained pose reports wrist -0.072097097 rad versus baseline
-0.001533981 rad: approximately -4.04 degrees of reported change. This supports
a controller-reported response, not verified physical accuracy or target dwell.
Operator observation and current stationary state remain pending.

Logs were exported through the wizard in operation
`operation-51b84e6f28c14985ac8a9dc5da01e867`. Original post-capture SHA-256:
`08b698560eb65d6592b0dec3b7672b48b8fe8c4e34e8c03ff5d5c546f7ff831a`.
Next software work is to reproduce short native read fragmentation under the
bounded five-second collector and reconcile its finite read/byte budgets.
Do not silently extend this consumed attempt or issue another command.

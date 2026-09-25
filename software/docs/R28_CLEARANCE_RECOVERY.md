# r28: one bounded shoulder clearance recovery step

The user's approval to proceed covers this reviewed installation and single
upward-step attempt. This is not a retry of r27's target and does not erase its
partial-arrival result. Camera, contact typing and full upright pose are deferred.

## Fixed contract

- Distinct signed scope `CLEARANCE_RECOVERY`, command `shoulder-clearance24-v1`.
- Fresh seven-joint enabled/stationary baseline, positions within2counts of
  `[2047,2448,1667,2905,1589,2040,2047]`, exact existing goals
  `[2047,2443,1671,2907,1589,2040,2047]`.
- Shoulder starting residuals explicitly bounded2–7counts in the recorded
  directions. Other joints remain within2counts of their existing goals.
- One paired target packet, goals12=2419 and13=1695; preserve commanded sum4114.
  Fresh actual-to-target travel must not exceed32counts. Speed20, acceleration1.
- Export baseline and intent; reacquire every joint before the write and require
  selected positions unchanged from intent. No explicit torque or settings write.
- Validate goal registers, direction, neighbor behavior and raw feedback. Require
  three stationary arrivals within2counts for completion. A plateau is still a
  failure; no retry, return or follow-on packet. Five-second acquisition deadline,
  separate ten-second terminal export barrier. Fault does not turn torque off.

The nominal model predicts7.052mm end-edge rise from the historical last sample.
This is not measured board clearance, lowest-gripper-point motion or stylus accuracy.

## Build evidence

Stage: `wizard-20260919T205358959700Z-0b3bd183ff3e49a9a4ce13686e0bb830`.
Compile: `wizard-20260919T205553183262Z-0cd25b4f86a44fcc85b252c2dec155de`.
Review: `wizard-20260919T205630341948Z-7b0cc74be8584538bd92a3de82a2909e`.
App SHA256: `88ccd20ebb1607a130cc25f6c5026690cd258cb14ba0d1b0bd763f32540f232e`.
App bytes1145728, offset0x10000, slot0x140000, headroom164992bytes.
Largest reviewed individual frame544bytes; not a total stack bound.
Bootloader and partition artifacts unchanged. Predecessor is verified r27.

Native/host owner tests exercise immediate and gradual arrival; wrong scope,
passive joints, changed goals/pose, wrong direction, neighboring-joint motion,
read failure, no motion, export failure and timeout. Two explicit plateau tests
model5/4-count residuals and confirm no second command. The board-interface
fixture was extended to recognize the new scope, then rerun successfully.

## Execution procedure

1. Verify local artifacts and current retained r27 fault; preserve all history.
2. One app-only r28 installation using the tested longer USB reset timing, full
   app readback and protected-region checks. Preserve settings/credentials.
3. One startup and read-only idle checks bound to the new installation journal.
4. One explicitly selected recovery session. Its fresh baseline is authoritative;
   do not substitute old readings or bypass a failed precondition.
5. Export and inspect every event and retained terminal result. Record partial
   progress separately from successful arrival. Stop on uncertainty or failure.

Status at preparation: built/reviewed, not yet installed or run.

## Actual installation and live result

r28 installed once, full app readback matched, protected flash unchanged, one
startup passed. Journal: `app-r28-deployment-events.jsonl`.
Installation review: `wizard-20260919T210209696762Z-2b981894a910498e8b234d36b98686ec`.
Startup: `wizard-20260919T210210125884Z-301f7f2ed27748cca197ebbfe01e47ea`.
Current boot: `710c666ba04bc64b1c265bbbebf033a1`.

One authorized recovery session was started. Its first fresh seven-joint scan
rejected the baseline with `RISE_BASELINE_NOT_HELD`. No target write occurred;
the subsequent retained-status GET confirmed `preload_writes=0`, explicit enable
NOT_ATTEMPTED, stateFAULT. No retry, return, settings or torque command followed.

Fresh sampled positions: `[2047,2448,1667,2904,1590,2041,2047]`.
Existing goals: `[2047,2443,1671,2907,1589,2040,2047]`. All torques1.
Both shoulders fit the expected recovery state. The elbow's2904 versus2907 goal
is a3-count residual and fails the unchanged-joint two-count baseline condition.
That is why the new target packet was not sent; it is not evidence the proposed
upward movement failed physically. One scan does not establish stationary drift
statistics or continuing current position after capture.

Run with retained failure record:
`wizard-20260919T210227902753Z-a407285db1ad45c498b0887219624116`.
Terminal status:
`wizard-20260919T210250390898Z-fd015fe6825846d5b0c4adb175210a82`.
The run's ordinary event-record count is0 because the first frame was a fault
frame; its raw joint response remains in the run operations, not discarded.

Validation this turn:81 motion/reviewer/planner tests;117 board/native owner tests
after fixing the new-scope fixture assertion;2 additional plateau tests;151
installation/startup/host regressions. Counts overlap and must not be summed as
a unique full-suite count. Add the actual3-count elbow-baseline failure as a
native regression case.

## Next change to evaluate

Separate baseline goal error from unexpected movement. A future recovery
contract should acquire multiple stationary baseline scans, retain existing
targets and a tightly bounded observed residual for each unchanged joint, then
limit drift from those measured positions during the step. Do not confuse this
with relaxing the selected shoulder's endpoint-accuracy test. Preview the actual
new baseline and reject nonstationarity, altered goals, larger offsets or wrong
direction. This requires explicit reviewed host/native agreement, not a manual
override of the installed r28 failure. No further live movement has been released
by this document alone.

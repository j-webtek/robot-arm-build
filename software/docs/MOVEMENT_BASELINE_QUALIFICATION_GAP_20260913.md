# Baseline qualification decision

Update: Jack has now supplied the requested current posture confirmation and
side-view photograph. See `MOVEMENT_POSTURE_OBSERVATION_20260913.md`. The coarse
posture question is resolved; do not repeat it. The original review below remains
historical evidence, with exact frame/freshness qualification still outstanding.

## Actual decision

The 14:47 UTC capture supports communication and full-window parsing, but not
an approved `controller_frame_and_baseline_qualified` decision. Retained review:
`software/runs/wizard-diagnostics/baseline-review-5ba387f8710f48108e3c8ac1773dd4d7.json`.
This is an offline observation, not a signed trial review or movement permit.

All 237 complete records were inspected. XYZ, pitch, roll, gripper and reported
joint angles each have zero range within this capture. This is consistent with
a stationary arm, but also with repeated cached feedback. No cause is inferred.

## Why this matters for the implemented executor

`application/endpoint_owned_trial.py::_baseline_context` compares the new
connection's baseline against the reviewed start pose and checks host timing.
Its explicit contract leaves pose meaning and device freshness to the
independent baseline review. Reusing this capture's latest values cannot
satisfy that review merely because the parser and timing checks pass.

The prepared zero-command capture also retains a zero-write serial profile and
a feedback-only compatibility review. They are supporting historical evidence,
not drop-in approvals for the endpoint motion binding.

## Next evidence needed

An independently observed current posture must be reconciled with the reported
joint angles/controller frame and the received firmware's feedback behavior.
This can begin with a current side view or live operator description of the
stationary arm, without changing its posture. The camera is not yet calibrated,
so a picture is only a coarse posture cross-check, not a millimeter measurement.

Do not push or reposition powered joints to create a telemetry change. Do not
home, release torque, flash firmware, send arbitrary commands or remove this
review requirement to break the qualification dependency. Any further device
query needs its own reviewed protocol and bounded execution path.

Once baseline meaning and the small noncontact route are supported, complete
the actual-unit reference assembly and use the existing one-trial executor.
Physical setup confirmation alone does not fill this technical evidence gap.

# Coordinated interpolation start-state discrepancy

## Correction after tracing the feedback path

The initial finding below was incomplete. The same reference source also assigns
`lastX/Y/Z/T` in `RoArmM3_computePosbyJointRad` (module.h:614–619).
`RoArmM3_getPosByServoFeedback` invokes it at line 642, and the T105 dispatch
invokes acquisition followed by reporting (uart_ctrl.h:60–62). Thus reference
T105 can refresh the stored interpolation origin before a coordinated command.
It does not update `lastR` in that FK function. A mere HTTP response is not proof
of successful per-servo acquisition, and installed source remains unverified.

Our commissioning runner performs a pre-command T105. Consequently, the
previous-goal-only replay omits a relevant event and cannot establish that the
real move used a stale origin. **Withdraw the claim of a demonstrated preview
start mismatch for the actual trial.** The two replay scenarios remain valid
counterfactuals, not a diagnosis. The simulator now explicitly models reference
feedback acquisition and invalidates state when its values are unavailable.
The live hold remains because the coordinated model failed prospectively and
exceeded the observed tip bound, not because the stale-origin explanation was proved.

## Finding

The official reference archive uses stored command-state coordinates for T104
interpolation. Our recent path previews used reported feedback as the start.
These are not equivalent after a target miss unless an intervening feedback path
refreshes the relevant state. See the correction above; the initial interpretation
omitted that path and is not a demonstrated mismatch for our actual command sequence.

Reference: https://files.waveshare.com/wiki/RoArm-M3/RoArm-M3_example_20260701.zip

Verified archive SHA256:
`a28247fee0bbb65cc034ff206031b8700d2b1ec8e3a1fa4b1a5a7365c55f1a57`.

`RoArm-M3_module.h`:

- Lines 736–742: `RoArmM3_lastPosUpdate` copies goal coordinates into last coordinates.
- Lines 863–879: interpolation length uses the difference between goal and last.
- Lines 895–905: interpolation starts from last coordinates, not a fresh servo read.
- Lines 934–936: sends the terminal target and updates last from goal.
- Lines 1024–1035: the all-position entry sets goal and invokes this interpolation.

The installed HTTP interface differs from this reference in other respects.
Do not flash firmware, send a reset/synchronization command, or overwrite goal
state based on this source review alone. A command to the measured pose can itself
produce motion when the internal starting state differs.

## Retained-command replay

Run `software/scripts/review_interpolation_history.py` for the pinned comparison.
Export: `wizard-20260917T202307336985Z-3ff118fe9ec04eb7909c22a31c761069`.

The prior transmitted goal differs from the next reported start by **5.078 mm**
in controller space. For the latest affine trial:

| Assumed interpolation start | Reference samples | Maximum modeled tip displacement from reported start |
|---|---:|---:|
| Reported feedback | 4 | 0.829 mm |
| Previous transmitted goal | 102 | 5.834 mm |

The second scenario begins with nominal elbow/wrist offsets of -0.532°/-0.861°
relative to the reported pose. It therefore has a substantially different
direction history and duration even though the final command is identical.
Neither ideal trace reproduces measured actuator dynamics. The observed 6.206 mm
tip-bound fault remains a fault, not explained away by this larger reference path.

## Consequences and next work

1. Suspend further T104 candidate execution while start-state uncertainty is not
   represented in its admission preview. Do not widen the 6 mm bound.
2. Track transmitted targets separately from measured positions. Track interruption,
   transport uncertainty and intervening command families as state-invalidating
   events; saved host history cannot certify internal controller state.
3. Screen plausible stored-goal and reported-start trajectories separately; mark
   unknown internal state explicitly. Include per-joint direction reversals and
   possible timing differences in diagnostics.
4. Inspect the installed interface/source lineage through read-only evidence to
   identify whether this behavior applies. Do not infer an installed firmware version.
5. Reassess response fitting using command-state displacement and command history,
   not only feedback-relative displacement. Keep chronological held-out testing.
6. Resume a bounded discriminating hardware experiment only after its path assumptions
   are explicit. Reliable coordinated motion, then vertical press/retract and ghost
   typing, remain the objective; wrist-only success is not completion.

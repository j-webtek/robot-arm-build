# Extend empirical compensation beyond the wrist

## Objective

Learn enough from command/feedback experiments to reduce endpoint error. A
complete mechanical explanation is not a prerequisite. Never copy wrist bias
coefficients to other joints or present controller feedback as tool-tip metrology.

Current evidence supports a local decreasing-approach wrist correction at +2
degrees, spd 20 / acc 1, unchanged tool and pose context. Everything below is
an extension of the method, not a claim that other joints are calibrated.

## Implemented software increment

- `arm/joint_endpoint_verification.py`: selected-axis endpoint checking for all
  six telemetry fields (`b,s,e,t,r,g`). Preserves checks for all other axes,
  movement response, excursion, quiet dwell, malformed rows and transport faults.
  Reuses the proven wrist monitor through coordinate reordering; no change to
  historical wrist verdict schemas or native command admission.
- `application/joint_bias_experiments.py`: bounded **synthetic-only** local bias
  fitting, separated by joint, approach direction, target and context. Requires
  three training trials and two disjoint validation trials per cell. One trial
  counts once regardless of telemetry-frame count. Existing compensated commands
  cannot be used as uncorrected training data.
- Prediction screening requires <=0.25-degree worst validation residual,
  improvement over no correction, and <=1-degree bias. An inverse proposal must
  preserve direction and remain inside its synthetic movement bounds.
- Sixty synthetic trials exercise twelve independent joint/direction cells,
  with deliberately different axis biases. These are not hardware observations.
  No non-wrist native command has been enabled or sent by this increment.

Verification: **84 passed**, including selected-axis simulations and existing
wrist correction/control regression tests. Report:
`software/runs/multi-joint-compensation-foundation.xml`.

## Model and data flow

For each local cell:

1. Retain intended endpoint, transmitted command, all six starting/final joint
   reports, raw feedback/read timing, speed/acceleration and setup identity.
2. Fit `bias = mean(reported final - uncorrected command)` using training trials.
3. Freeze that value before inspecting validation outcomes.
4. Predict `command = intended endpoint - bias` for the same cell.
5. Evaluate actual corrected responses against the **intended endpoint**, not
   against the adjusted command. Retain the command diagnostic separately.
6. Compare against interleaved uncorrected controls. Keep every failed trial.

The simplest useful model is a per-joint, per-direction offset. If it fails to
generalize between nearby targets or pose contexts, split the domain into local
cells first. Add interpolation or a coupled model only when held-out data justify
it; do not extrapolate untested coefficients across the full arm workspace.

## Next native integration

1. Confirm the selected axis's command ID, telemetry field, angle convention and
   permitted range from reviewed RoArm-M3 firmware/protocol sources. Telemetry
   column order alone is not authority to construct a motor command.
2. Extend a new versioned single-joint intent with explicit selected axis and
   immutable local movement envelope. Keep older wrist formats unchanged.
3. Carry the selected axis through fresh baseline admission, one-use command,
   raw collector, nominal endpoint checking and independent parent reconstruction.
   Reject changes in non-selected axes. Do not substitute a joint index into the
   existing wrist-only executor without auditing every axis-specific check.
4. Add a wizard preview naming the joint, intended endpoint, transmitted angle,
   expected sweep and maximum command count. Keep one-use admission, finite
   deadlines, existing cancellation/cleanup semantics and no automatic retry.
5. Simulate the entire owned path before its first hardware command: wrong axis,
   target/command substitution, other-axis drift, stale baseline, uncertain write,
   truncated feedback, cancellation and portable export reconstruction.

## Physical experiment sequence

Start with one selected axis and a small local excursion, not simultaneous joint
motion. Choose the axis and swept clearance using the assembled pose; base motion
sweeps the whole arm, and shoulder/elbow motion can change height and load. A
clearance envelope for a wrist-only test is not automatically one for those axes.

For each joint:

- Establish uncorrected command/feedback response and both approach directions.
- Collect >=3 training and >=2 held-out uncorrected trials per direction in the
  same local cell. Use bounded, explicit positioning commands between trials.
- Freeze the independent axis biases. If validation does not improve, do not
  enable compensation for that cell.
- Collect corrected repetitions and matched uncorrected controls, scoring
  nominal error, settling, drift and complete captures before progressing.
- Expand to a second target and relevant arm poses; retain domain restrictions
  until those conditions are demonstrated.

Only then test coordinated joint moves and Cartesian destinations. Joint-level
correction can improve servo-reported agreement, but keyboard/phone accuracy
also depends on arm geometry, deflection, tool offset and board registration.
Use calibrated external vision to validate the actual tool-tip destination.

## Current boundary

The model fitter remains simulation/analysis only. A versioned base-only v6
native probe now uses the selected-axis monitor with independent retained
reconstruction. The first uncorrected +1-degree base probe ran and missed its
endpoint; see `BASE_MAPPING_FIRST_PROBE_20260915.md`. Existing wrist live
semantics remain unchanged. No global or automatic multi-joint compensation
is enabled. Continue with bounded base characterization, both directions and
held-out measurements; proving the exact mechanical cause is not a gating task.

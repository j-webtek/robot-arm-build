# First local base correction experiment

## Status and purpose

Native correction/control integration is implemented and two live matched
pairs are complete, including a reversed-order repeat. See
[the first pair results](BASE_FIRST_COMPENSATION_PAIR_20260915.md) and
[the reversed-pair results](BASE_REVERSED_PAIR_20260915.md).
The corrected endpoint error was 0.054687474 degree versus 0.560546872 degree
for its matched control in both pairs. Broader validation remains pending.
The base record now contains seventeen commands: the original eleven uncorrected
characterization commands, two separate positioning commands, two corrected trials
and two uncorrected controls. The original training model remains frozen.

Determine whether an inverse of the frozen, direction-specific local line reduces
reported base endpoint error compared with an uncorrected command. This concerns
encoder-reported joint coordinates, not independently measured tool-tip position.
It does not establish board mapping, Cartesian accuracy or all-joint compensation.

## Evidence-backed candidate

| Quantity | Value |
| --- | --- |
| Desired reported endpoint | +1.000000 degrees |
| Candidate transmitted target | +2.335749465967 degrees |
| Predicted reported endpoint | +1.000000 degrees |
| Approach | Increasing base coordinate |
| Observed starting range | +0.351562491 to +0.439453128 degrees |
| Trained command range | +1.439453128 to +2.439453128 degrees |
| Speed / acceleration parameters | 20 / 1 |
| Post-command observation | Five seconds |
| Experiment endpoint-error screen | Absolute error at most 0.25 degree |

These are absolute joint coordinates, not relative rotations. The command is
computed as `(desired_endpoint - intercept) / slope`, with radians internally.
No coefficients are transferred from the wrist or the decreasing base branch.
The exact numerical prediction is algebraic, not a measured result.

The proposal uses a historical planned start of +0.439453128 degrees. At proposal
creation the last observed endpoint was +0.878906257 degrees, outside the fitted
starting range. Separate positioning and fresh feedback qualified the live pair.
The last observed endpoint after the reversed pair is +1.054687474 degrees,
outside the positive starting domain. Separate positioning and fresh native
feedback are needed before another corrected trial; historical data is not
permission to skip admission.

## Implemented offline path

- `src/rocell/application/base_correction_proposal.py` reconstructs the frozen
  model from eight original training exports and checks exact model-file bytes.
- It revalidates three held-out prediction/export pairs, including the two
  prospectively declared directional midpoint comparisons. The line must pass
  each 0.25-degree screen and outperform the comparator in aggregate.
- It rejects changed evidence, repeated validation targets, incompatible context,
  out-of-domain starts, other-joint pose changes and extrapolated motor targets.
- Nominal endpoint and motor command remain separate. Both must fit the local
  positive movement bounds. The proposal grants no motion authority.
- Synthetic scoring checks arrival against the desired endpoint, checks the
  transmitted-target excursion corridor, and retains other-joint and capture
  quality checks. Synthetic success cannot be treated as live evidence.

Artifacts:

- `runs/BASE_CORRECTION_PROPOSAL_20260915.json`
- `runs/BASE_CORRECTION_SYNTHETIC_SCORE_20260915.json`
- `runs/base-correction-proposal-regression-20260915.xml`

Validation: 25 targeted tests passed across the proposal and dataset modules.
The real proposal was also rebuilt from the eight training and three held-out
original exports. Unit proposal fixtures use explicitly synthetic readers;
neither those tests nor the synthetic score constitute a native execution test.

## Execution checklist

Steps 1-7 have been implemented and exercised for the first pair, including
simulation regression and independently reconstructed live exports. Step 8
(repeated matched validation) is next. The detailed requirements remain below.

1. Add an explicitly versioned native base experiment profile. Do not change
   semantics of existing uncorrected base profiles or reuse the wrist schema.
   Bind desired endpoint, actual transmitted target, approach, frozen evidence
   hashes and hardware/tool/pose context in the reviewed intent.
2. Add its matched uncorrected control: desired +1 degree, transmitted +1 degree.
   The control is an empirical comparison, not a model prediction: its command
   lies below the fitted command range. Do not apply or score extrapolated model
   predictions to that control.
3. Wire staging, wizard preview, child admission, process allowlist, native
   archive, endpoint reconstruction and portable exports. Show desired and
   transmitted coordinates separately in the UI and diagnostics.
4. At fresh native admission, enforce the model starting range for correction,
   approach, context and unchanged other-joint pose. Retain one command per
   campaign, bounded speed/delta, complete capture, cancellation handling,
   uncertain-write handling and no automatic retry/return. Historical planning
   data must not satisfy the fresh-baseline requirement.
5. Exercise the full owned native path in simulation: corrected arrival, nominal
   miss, arriving at the motor target instead of the desired endpoint, wrong
   model/hash/command, out-of-domain baseline, other-joint drift, short capture,
   malformed feedback, cancellation, uncertain write and duplicate execution.
   Independently reconstruct exported results and verify cleanup for each case.
6. Perform a separately reviewed positioning trial if needed. Verify its actual
   endpoint before selecting a correction or control. Do not count positioning
   as compensation evidence or automatically assume it restored the start.
7. Execute one corrected trial and one matched control as separate campaigns,
   with independently verified matching starts, approach, speed and context.
   Preserve and review each complete capture before the next movement. A miss
   ends that campaign; it does not trigger an automatic compensating command.
8. Repeat matched pairs only after the first pair has clean reconstructed
   evidence. Freeze the candidate throughout comparison; do not fit on these
   trials and then label them held-out validation. Decide whether to retain,
   revise or reject the candidate from measured errors and repeatability.

## Comparison and export contract

Keep original intent, model and prediction hashes, campaign ID, hardware context,
six-joint baseline, desired target, transmitted target, raw timestamped feedback,
final six-joint state, stable-tail span, endpoint error, approach, status, write
certainty and cleanup outcome. Record positioning/control/correction explicitly.
Keep faults and misses in the record rather than silently discarding them.

Score nominal error as `reported_final_base - desired_base`. Report paired
absolute-error improvement and repeat variability, not just the generic arrival
flag. An experiment passes its accuracy screen only when capture and other-joint
checks pass and absolute nominal error is at most 0.25 degree. The generic
0.5-degree arrival tolerance is not a replacement for that stricter screen.

Success supports only this local direction/pose/speed cell. Broader ranges,
different loads, additional joints and physical-space accuracy need separate
evidence. Do not enable continuous or coordinated corrected motion from one pair.

## Re-run targeted tests

From the workspace root:

```powershell
.\.venv\Scripts\python.exe -m pytest software/tests/unit/test_base_correction_proposal.py software/tests/unit/test_base_endpoint_dataset.py -q
```

Related evidence: [midpoint comparison](BASE_MIDPOINT_COMPARISON_20260915.md),
[frozen model and holdout](BASE_LOCAL_MODEL_AND_HOLDOUT_20260915.md), and
[joint mapping inventory](JOINT_MAPPING_INVENTORY.md).

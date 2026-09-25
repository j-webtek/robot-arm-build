# Offline endpoint models and prospective validation

## Implemented, 2026-09-14

`application/wrist_endpoint_models.py` independently verifies each selected
campaign export before analysis. Exact report hashes and campaign-disjoint
splits are listed in `WRIST_ENDPOINT_MODEL_MANIFEST_20260914.json`.
Missed endpoints remain observations; unexecuted and nonzero-target legs are
explicitly excluded from this zero-target fit. Hardware, tool, workcell and
protocol reference mismatches fail the comparison. No live command path uses
this module; it generates predictions, not inverse/compensated commands.

Training uses the earliest selected above-zero and below-zero trials (one each).
Validation uses five other campaigns (three above, two below). All outcomes had
already been inspected, so this is a **retrospective** campaign-disjoint check,
not an unbiased prospective test or a claim of model generalization.

| Model | Fitted endpoint error (degrees) | Validation MAE | Validation RMSE |
| --- | --- | ---: | ---: |
| Nominal | 0 | 0.755859 | 0.798790 |
| Constant bias | +0.263672 | 0.703125 | 0.703125 |
| Direction bias | Increasing -0.439453; decreasing +0.966797 | 0 | 0 |

The zero residual matches the repeated quantized endpoint reports. Physical
position error, encoder freshness, other targets and changed payloads remain
unvalidated. A prediction fit is not evidence that corrected commands improve
positioning. **No compensation was enabled or physically tested this turn.**

Reproduce from the workspace root:

```powershell
.\.venv\Scripts\python.exe software/scripts/compare_wrist_endpoint_models.py software/docs/WRIST_ENDPOINT_MODEL_MANIFEST_20260914.json
```

Retained derived output: `software/runs/WRIST_ENDPOINT_MODEL_COMPARISON_20260914.json`.
Tests: `software/runs/wrist-endpoint-models-20260914.xml`, 32 passed, including
changed hashes, duplicate campaigns, mixed context, incomplete reconstruction,
training/validation separation, missed endpoints, and unchanged motion flags.
Original exports were not modified. Future reports must be separate artifacts,
not overwritten training evidence.

## Frozen prospective experiment: nominal +2 degrees

All three prospective matched pairs are now complete; see
[repetition results](TWO_DEGREE_REPETITION_RESULTS_20260914.md).
Maximum frozen-model prediction error was 0.109375 degrees across six endpoints.
This completes prediction validation for this small dataset, not validation of
compensated commands or physical tool-tip accuracy.

First pair has now been collected and scored without refitting. See
[prospective results and exact exports](TWO_DEGREE_PROSPECTIVE_RESULTS_20260914.md).
Direction-model residuals were -0.066406 and +0.109375 degrees; one trial per
direction met the provisional prediction screen at that stage. The two remaining
pairs have since completed as recorded above. No corrected commands were tested.

The +2-degree target is outside this fit's target domain. Predictions below
are **extrapolation hypotheses**, fixed before collecting this experiment.
Do not retrain on the prospective data before reporting the frozen-model score.

| Approach | Nominal prediction | Constant-bias prediction | Direction-bias prediction |
| --- | ---: | ---: | ---: |
| Increasing from a reported angle below +1.5 deg | +2.000000 deg | +2.263672 deg | +1.560547 deg |
| Decreasing from a reported angle above +2.5 deg | +2.000000 deg | +2.263672 deg | +2.966797 deg |

### Execution design (not yet implemented or run)

1. Add enumerated +2-target profiles to the bench adapter, with simulation tests
   of complete, missed, cancelled and start-mismatch cases. Do not add arbitrary
   motion inputs or relax the existing native intent validator.
2. Acquire a fresh six-joint baseline for every separate campaign. The last
   recorded wrist was +3.779297 degrees, but that is not a current baseline.
3. First test +2 from above; planned starting side is near reported +3.779.
   Keep spd=20, acc=1, five-second observation, +/-0.5-degree nominal endpoint
   tolerance, <=5-degree per-leg displacement and existing drift/dwell checks.
4. Prepare the below-side condition through separately reviewed nominal zero
   positioning as needed; use the actual measured start, not the desired zero.
   All startup, side, delta and clearance gates still apply. Never mark a missed
   positioning target successful just to advance a sequence.
5. Collect up to three new endpoint trials per direction, alternating sides
   where the bounded routes permit. Every miss stops its own campaign. Review
   complete captures and fresh baseline before any separately staged diagnostic.
   Stop further motion on uncertain write, changed other joints, excursion,
   incomplete capture or unresolved communication/cleanup fault.
6. Use only uncompensated nominal +2 commands. Any second leg required by the
   two-leg runtime is explicitly shown before execution and conditional on the
   first endpoint passing; it is not a hidden return or retry. Prefer a
   separately reviewed one-leg route if supported rather than adding work solely
   to satisfy the campaign shape. No unattended release is implied.

### Scoring fixed before new data

- One endpoint per observation. Report every attempted campaign, excluded capture
  reason, commanded target, actual reported start, approach, final angle, nominal
  error, predicted error, residual, settling bounds, load field and other-joint drift.
- Score all three frozen models with pooled **and per-direction** MAE/RMSE, max
  absolute residual and sample counts. Include nominal TARGET_MISSED outcomes.
- This experiment's provisional model screen is per-direction maximum absolute
  prediction residual <=0.25 degrees, with direction-model pooled MAE lower than
  both nominal and constant baselines. This is a chosen engineering test criterion,
  not a vendor guarantee, significance test or motion acceptance tolerance.
- If the first matched pair contradicts the model strongly or its error exceeds
  the nominal model in both directions, review before further repetitions; keep
  the contradiction rather than refitting until it disappears.
- Even a passing screen only supports this configuration and nearby tested target.
  A separate bounded corrected-command experiment and external vision validation
  are still needed before claims about physical typing/tapping accuracy.

## Independent software follow-up

The intermittent first-line serial fragment remains a separate onboarding issue.
Add specific framing diagnostics and attachment-offset simulations before changing
acceptance rules. Do not mix transport fixes, servo tuning and compensation into
one physical experiment, since that would obscure why a result changed.

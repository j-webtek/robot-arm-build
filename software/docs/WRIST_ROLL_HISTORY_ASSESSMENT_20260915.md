# Wrist-roll history: offline model-readiness assessment

## Outcome

All 19 retained roll campaign exports at this checkpoint were inventoried,
pinned and independently verified. There are 18 retained submission attempts:
17 reconstructed endpoint-complete trials and one held trial. One additional
campaign has no retained trial and is not treated as a zero-error observation.

No hardware connection, motion, correction or firmware change was made in this
work. Roll count remains eighteen; base remains 44.

## Dataset inclusion

| Class | Count | Use |
| --- | ---: | --- |
| Clean, reconstructed 35-second persistent runs | 10 | Conditional error-prediction screen |
| Short-window completed runs | 7 | Historical context; insufficient duration for this screen |
| Held split-frame / late-change trial | 1 | Preserved failure and separately verified diagnostic replay |
| No retained trial | 1 | Preserved operational outcome; no invented endpoint |

The held v20 trial remains held. Its offline replay still finds the late change.
The short-window trial with later differing feedback is explicitly referenced,
not promoted into stable training data. This is not a success-only claim about
overall reliability: the prediction scores below are conditional on clean,
persistent 35-second observations.

## What repeats and what does not

Exact-geometry comparisons retain schema, source, configuration, staged
six-joint start, command/speed/acceleration, direction and controller/protocol/
payload/workcell context. Baseline and runtime registration hashes remain
visible but are not equality keys because they identify distinct executions.

- Recent v19 increasing pair: zero reported endpoint spread.
- Recent v19 decreasing pair: 0.087891-degree spread.
- v21 increasing pair: zero reported endpoint spread.
- v21 decreasing pair: 0.175781-degree spread.

Singleton groups have an unknown repeat spread, not a misleading zero. Zero
spread in two samples is not a future uncertainty bound. For the observed v21
decreasing pair, even the best single constant endpoint prediction would miss
one of those two samples by at least half their spread (0.087891 degree). This
is an observed-data property, not a bound on future trials or corrected moves.

## Chronological candidate screen

Candidate: prior mean *reported error* for the same direction, source/schema,
controller/protocol, payload/workcell, speed and acceleration. Each prediction
uses only strictly earlier eligible observations; neither its own result nor a
future result is included. Compare with predicting zero error. Different source
or schema contexts are not pooled to improve a score.

There are only four scored later trials; each has one earlier training sample
at one already-observed target. No novel-target generalization was tested.

| Error prediction | Mean absolute error | Worst absolute error |
| --- | ---: | ---: |
| Assume zero command error | 0.252930 deg | 0.472656 deg |
| Prior same-context/direction mean error | 0.065918 deg | 0.175781 deg |

The two increasing error predictions match; the decreasing predictions miss
by 0.087891 and 0.175781 degree. The direction-conditioned predictor is useful
for describing this small history, but does not resolve decreasing variability.

**These are predictions of errors on uncorrected commands—not measurements of
corrected-command accuracy.** Applying the negative predicted error changes the
command and may change the response. No inverse model is validated, no corrected
trial was run, and no compensation is enabled. A linear model is not fitted:
there are too few independent target points within each direction/context.

## Implementation and reproduction

- Inventory pins: `software/docs/WRIST_ROLL_HISTORY_PINS_20260915.json`.
- Replay builder: `software/scripts/review_roll_history_20260915.py`.
- Pure assessment: `software/src/rocell/arm/roll_history_assessment.py`.
- Dataset/results: `software/runs/WRIST_ROLL_HISTORY_ASSESSMENT_20260915.json`.

```powershell
.\.venv\Scripts\python.exe software/scripts/review_roll_history_20260915.py
.\.venv\Scripts\python.exe -m pytest software/tests/unit/test_roll_history_assessment.py software/tests/unit/test_endpoint_persistence.py -q
```

Replay fails on missing or changed pinned originals; it does not replace them
with newer favorable trials. All 19 original exports verified, and 41 focused
tests passed. Tests cover chronology/future leakage, held-row exclusion with
retention, context separation, duplicate/nonfinite rejection, equal timestamps,
singleton handling and the distinction between observed spread and uncertainty.

## Next work, before another command

1. Present four separate judgments in the testing workflow: transport/arrival,
   within-run persistence, across-run repeatability, and next-start eligibility.
   Preserve original verdicts and the existing broad tolerance; add a clearly
   separate precision assessment rather than relabeling a 0.473-degree miss as
   precise or silently changing prior pass criteria.
2. Prepare a finite prospective response-mapping experiment with exact start,
   direction, target and approach history recorded. Vary one factor at a time;
   small target changes are more informative now than repeating the same point
   indefinitely. Validate its geometry/budgets in simulation before admission.
3. Freeze candidate parameters and evaluation criteria before corrected trials.
   Compare with uncorrected controls from matching starts and keep all outcomes,
   including misses and late changes. Do not make the same trials both training
   and evaluation evidence, or assume an average cancels unpredictable errors.

Current last reported roll remains 0.007669904 rad. It does not match the v21
fixed increasing anchor (0.004601942). No repositioning or relaxed anchor is
authorized by this offline assessment. External physical tool-tip accuracy and
any cross-joint compensation remain unverified.

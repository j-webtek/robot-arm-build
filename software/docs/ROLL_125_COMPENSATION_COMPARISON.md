# Frozen 1.25-degree compensation: new variability observed

Two live, bounded single-command actions completed. Both passed original-body
endpoint replay and unchanged-hold verification. No retries, return, refit or
policy changes were made. All angles below are controller joint telemetry,
not independently measured tool-tip positions.

## New results

| Leg | Fresh roll start | Command | Desired | Initial and hold-final roll | Error vs desired |
| --- | ---: | ---: | ---: | ---: | ---: |
| High positioning | 1.494140602 | 2.5 | 2.5 | 2.285156222 | -0.214843778 |
| Frozen descending lookup | 2.285156222 | 0.95 | 1.25 | 1.406250023 | +0.156250023 |

The frozen candidate hash remained
`822965da1d902c86993a50c8647b06e672e37323b56a211a42a1c4bc6e48a910`.
Speed was 20 and acceleration 1. Fresh six-joint lookup baseline matched the
candidate evidence's recorded baseline. This does not match hidden mechanical
history or elapsed holding time.

High hold: 116 responses, 34.840869-second response span, maximum gap 407.365 ms.
Lookup hold: 115 responses, 34.903407-second response span, maximum gap 362.748 ms.
All six reported joints remained unchanged through each hold. The lookup failed
both illustrative +/-0.05 and +/-0.10-degree bands for the entire observed window,
while passing the broader 0.5-degree operational arrival check. Its conservative
host observation span was 34.748065 seconds. No narrow-band requirement was adopted.

## Same desired target comparison

Recent ascending uncorrected command 1.25 reported 1.230468748 degrees, error
-0.019531252. Recent descending uncorrected command 1.25 reported 1.494140602,
error +0.244140602. This new descending compensated command 0.95 reported
1.406250023, error +0.156250023.

Thus the observed inter-direction gap changed from 0.263671854 to 0.175781274
degrees, a reduction of approximately 0.087890580 degrees. This is a descriptive
comparison across sequential trials, not a controlled causal effect or a
guaranteed improvement. Compensation did not align the endpoints in this trial.

The two earlier held-out uses of this same frozen command reported 1.230468748.
There are now three completed held-out observations with endpoint range
1.230468748 to 1.406250023, not zero spread. Do not discard this result, average it
into a new offset immediately, or enable the candidate globally. Direction alone
does not uniquely predict the observed response under these tested conditions.

## Evidence

Directories under `software/runs/wizard-exports/`:

- High: `wizard-20260917T023739179740Z-cb144bbb5c0549519688d24e7b673522`
  manifest SHA-256 `a3ff99c95d11791b9a756f049da4bf258b7c29f6fd35dedda81d1828b4aa018c`.
- Lookup: `wizard-20260917T023838302816Z-82abe10cb761414ea7106beb29373733`
  manifest SHA-256 `a67703e59065af72c8ad2fbcc0677d56255d7544330d5dc04c9484862dd96fa8`.

Ascending reference and descending uncorrected reference are the control legs in
`ROLL_REVERSE_ORDER_EVIDENCE.json`. Neither is counted as compensated validation.
`ROLL_LOCAL_MAPPING_EVIDENCE.json` now retains all three compensated outcomes.

## Next useful work

Before another compensation change, replay all three lookup trials side by side:
exact command bytes/hash, receipt category, baseline, per-response endpoint path,
time to arrival, hold timing and preceding positioning history. Identify which
recorded conditions match and which differ; do not infer an unobserved cause.
Then define a small repeated block with identical positioning actions and a
fixed post-positioning hold protocol to test reproducibility. Keep failures and
all endpoint alternatives. Do not loosen the narrow examples or fit away the
variation simply to label the candidate successful.

Last reported roll: 1.406250023 degrees. No further motion was sent. A future
movement requires its own fresh baseline and existing single-use admission.

The offline comparison is now complete in `ROLL_125_TIMELINE_REVIEW.md`.
Commands and reported baselines match across all three trials; no definitive
cause was identified. The reviewer now emits reproducible timing profiles, and
the document specifies the next controlled block without enabling live sequences.

# Timestamp-based endpoint-band replay

Implemented offline in `src/rocell/arm/sustained_band.py` and integrated into
`scripts/review_wifi_roll_export.py`. No physical commands were sent.

The reviewer first checks export integrity, reconstructs original feedback,
replays the endpoint verdict and checks the hold summary. Only then does it
compute `band_sensitivity_examples`. Existing exact unchanged-hold validation
and CLI failure status are preserved independently.

## Interpretation

- Band examples: +/-0.05 and +/-0.10 degrees; neither is an adopted requirement.
- Illustrative minimum observation duration: 30 seconds, NOT a new live policy.
- Use actual host timestamps, not a sample-count or uniform-cadence estimate.
- Run duration extends from its first response completion to its last request
  start, conservatively excluding boundary request latencies.
- An out-of-band sample or response-to-response gap above one second breaks a run.
- Report both the final qualifying run and whether the entire observed window
  qualifies. A late return cannot erase earlier errors.
- A nominal 35-second capture is not necessarily 35 seconds of observed coverage.
- These are sampled controller joint readings: not proof of position between
  samples, device sample freshness, external tool position or Cartesian accuracy.

## Replayed results

Desired endpoint: 1.50 degrees; frozen lookup command: 1.25 degrees.

| Held-out trial | Conservative span | +/-0.05, 30s | +/-0.10, 30s | Exact unchanged hold |
| --- | ---: | --- | --- | --- |
| First: late change | 34.652017 s | Fails | Qualifies | Fails |
| Second: repeat | 34.772079 s | Fails | Qualifies | Passes |

The first trial's longest +/-0.05-degree run was only 3.715297 seconds; its final
run in that band was zero. The second had no samples in that band. Neither
record had a response gap above one second. Both ended at 1.406250023 degrees,
approximately -0.093749977 degrees from desired. The +/-0.10 result therefore
has little observed margin and must not be generalized from two trials.

Evidence directories under `software/runs/wizard-exports`:

- `wizard-20260917T020917549534Z-9a208e0f1d4b434499a106efd1e36ead`
- `wizard-20260917T021359421783Z-bb4a4ebad56b4f4b85501cfa3454e1d0`

Run `python software/scripts/review_wifi_roll_export.py <export-directory>` using
the workspace virtual environment. The first trial intentionally exits 1 for
the unchanged-hold failure even though its +/-0.10 sensitivity result qualifies.

## Verification and next step

Unit coverage includes real-timestamp duration, gaps, late changes, returns,
short windows, invalid settings, malformed times and nonfinite readings.
41 focused tests passed across the band evaluator, reviewer, correction simulator
and discrete transaction. Both real exports were separately replayed successfully;
this means their evidence was readable, not that both passed exact stability.

Next compare additional independent, bounded repetitions and approach directions
before choosing a compensation policy. Keep the frozen candidate disabled.
Do not enable automatic residual correction based on these two trials: the
existing simulator identifies both minimum-step and same-side policy conflicts.
A separately bounded small-step protocol and fresh hardware baseline are needed
before testing that alternative physically. Board/tool calibration remains separate.

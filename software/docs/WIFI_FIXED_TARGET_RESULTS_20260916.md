# Fixed-target Wi-Fi roll comparison — September 16, 2026

## Outcome

Four separately admitted live commands completed with software-verified reported
endpoints. Each was followed by a separate 35-second feedback-only observation.
There were no retries, corrections, automatic returns, or failed trials in this
four-leg comparison. No compensation was applied.

| Leg | Approach | Target | Final reported roll | Signed error | Follow-up responses |
| --- | --- | ---: | ---: | ---: | ---: |
| Low 1 | Descending | 1.0° | 1.230469° | +0.230469° | 119 |
| High 1 | Ascending | 2.5° | 2.285156° | −0.214844° | 119 |
| Low 2 | Descending | 1.0° | 1.142578° | +0.142578° | 118 |
| High 2 | Ascending | 2.5° | 2.285156° | −0.214844° | 118 |

All follow-up reported poses matched their trial's terminal pose on all six
joints, and showed zero within-window span. Thus the observed offsets persisted
through those windows; they were not observed to disappear with extra waiting.
The observations are separate actions, not continuous captures of the intervening
gaps. No controller-sample timestamp or external tool-tip measurement is available.

Before this set, another 35-second observation of the prior reverse endpoint
completed with 121 responses and no reported joint changes. Its roll remained
0.036815539 rad (2.109375005°).

## Interpretation

- The same high target produced the same reported endpoint twice.
- The low target's two reported endpoints differed by 0.087891°.
- Two repeats per target are descriptive evidence, not statistical qualification.
- Target and approach direction are coupled in this set; it does not isolate
  direction from target position, starting pose, path history or quantization.
- The low target errors differ from the earlier relative −1° trial's +0.472656°
  error. A single universal reverse-direction correction is not supported.
- Passing the 0.5° arrival criterion does not establish 0.1° precision or Cartesian
  millimetre accuracy. No thresholds were relaxed.

## Implemented controls

The wizard now offers **Move roll to 1 degree from above (Wi-Fi)** and **Move roll
to 2.5 degrees from below (Wi-Fi)**. These are fixed choices, not arbitrary angle
entry. The fresh delta must remain >0.5° and <=1.5° in the specified direction.
Existing +/-3° target bounds, speed 20/acceleration 1, single-use durable dispatch,
one-second feedback-gap allowance and ten-second completion deadline remain.

`software/scripts/bench_wifi_fixed_roll.py low` or `high` performs ONE LIVE trial
through the wizard. Only if it succeeds does the script run the read-only
observation. It then exports diagnostics, including a failed result if applicable.
There is no movement loop in this script. Construction/preview does not move.

## Original evidence

All four exports passed integrity verification. Original numeric feedback bodies
were validated, decoded back into endpoint rows, and used to reproduce the saved
endpoint verdict. Every follow-up original was checked against the terminal pose.
All paths below are under `software/runs/wizard-exports/`:

1. Low 1: `wizard-20260916T160621084722Z-4e818ac9b24f42aea926fd0f27840990`
   - Manifest SHA-256: `07cbe387222f2db17b6cf0a0302a70a4ba9634855f7426be2da7c32e84486ff7`
2. High 1: `wizard-20260916T160728444274Z-3dc165450789416f9e530084cf9d2f39`
   - Manifest SHA-256: `7cd776b1beed5554b1aaaaad33f508d156b46826fee08b51c82c46eb7ae5d172`
3. Low 2: `wizard-20260916T160811960226Z-84586d1ad8c3408e9a72292c6c87330b`
   - Manifest SHA-256: `6d1c33536e96a9c728062d0120796f72b05e26f046e852393552ecec250ca601`
4. High 2: `wizard-20260916T160854793840Z-33c3ff116d6f47d49e7d2f2bb80ec409`
   - Manifest SHA-256: `b275d1221249cec6ffe80aa097e14c100db06fd7ffa1b59da863eb7d368536bf`

Prior endpoint observation:
`wizard-20260916T160338501244Z-b0c68799a192460bbff29e42311a8a82`.

## Next experiment

Design a bounded same-target approach from both sides, with separate positioning
legs and fresh-baseline admissions. Preselect a finite repeat count and stopping
conditions. Keep compensation disabled for collection, then assess a candidate
on held-out trials rather than the same trials used to estimate it. Preserve exact
target, start, approach direction, speed, response timings and post-arrival drift.

Current last reported roll is 2.285156222°. No return-to-start was performed.

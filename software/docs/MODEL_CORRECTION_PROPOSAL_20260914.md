# Bounded model-correction proposal: offline only

**Status update:** the sections below retain the original development history.
The v4 one-command native integration and first successful corrected live trial
are now recorded in [First live result](MODEL_CORRECTION_FIRST_LIVE_RESULT_20260914.md).
One successful reported endpoint does not release general compensation.

## Implemented

`application/wrist_model_correction.py` builds a distinct immutable proposal
from the frozen model and reverified prospective campaign exports. It is not
an existing native intent and is not wired to the wizard's motion action.
No camera, serial connection or arm command was used during this work.

Current artifact:
`software/runs/OFFLINE_MODEL_CORRECTION_PROPOSALS_20260914_v2.json`.
The initial pack remains retained but is superseded: v2 adds a separate
correction-improvement screen, distinct from ordinary nominal-band acceptance.

| Approach | Intended endpoint | Proposed transmitted angle | Correction | Reference goal register |
| --- | ---: | ---: | ---: | ---: |
| Decreasing from historical +3.779297 deg | +2 deg | +1.033203106 deg | -0.966796894 deg | 2059 |
| Increasing from historical +0.791016 deg | +2 deg | +2.439453128 deg | +0.439453128 deg | 2075 |

These are hypotheses, not calibrated commands. The nominal target minus the
frozen directional bias produces the proposed command. Adding that same bias
back yields an algebraic prediction of 2 degrees; this is not experimental
proof. Changing a command can change load, quantization and hysteresis effects.

Reference firmware predictions are retained separately from transmitted angles.
The predicted feedback angle is NOT substituted for the command: doing that
would reapply the command/feedback midpoint asymmetry. The device performs its
own rounding. Reference firmware remains unverified as the installed binary.

## Evidence and bounds

- Frozen-model bytes must match the supplied expected SHA-256.
- At least three independently verified +2 trials per direction, with distinct
  report hashes, matching speed/acceleration and hardware/tool/workcell/protocol
  references. Model-data/prospective-data overlap is rejected.
- Prospective prediction error must satisfy the prior 0.25-degree screen and
  improve pooled prediction error over both frozen baseline models.
- Only the tested nominal +2 target is supported. Maximum bias correction is
  one degree. Start, intended target and proposed command remain within +/-10
  degrees; both nominal and adjusted moves must exceed 0.5 and not exceed five
  degrees, preserving approach direction.
- Starting wrist must remain within the demonstrated approach range plus
  0.5 degrees. All six start joints must be finite. These are historical inputs,
  not verified current position or independent six-joint clearance evidence.
- One experimental command only, spd 20, acc 1, five-second observation,
  unchanged +/-0.5-degree nominal tolerance; no automatic retry.
- Immutable proposal bytes/hash identify this diagnostic. They are not signed
  admission, current device authentication, permission, or an executable plan.

Historical starts in the pack are derived from the verified final campaign
`campaign-412a7d8918d64a8eac103d847e9829b7`: leg-02 post for above, leg-01
baseline for below. Their source references are retained. A future live attempt
must replace this planning context with its own fresh matched six-joint baseline.

## Nominal success versus correction improvement

Synthetic scoring reuses the existing wrist endpoint monitor against the
**intended endpoint**, with a separate diagnostic against the proposed command.
It preserves nominal and commanded corridor checks, dwell, other-joint checks,
bounded sample count, near-five-second span, gaps and transport/capture failures.
It deliberately remains conservative: excursions outside the nominal corridor
still fail, even if the shifted-command corridor would allow them.

The correction-improvement screen additionally requires absolute nominal error
<=0.25 degrees and less than the measured uncorrected mean absolute error for
the same approach. This stricter experiment screen does not change live motion
tolerances or claim statistical significance.

| Synthetic outcome | Nominal-band result | Correction-improvement result |
| --- | --- | --- |
| Reaches 2 degrees with required dwell | Pass | Pass |
| From above, reaches only 1.033-degree command | Fail | Fail |
| From below, reaches only 2.439-degree command | Pass within +/-0.5 | Fail: exceeds 0.25 and worsens prior 0.330 error |
| No response, drift, corruption, short window, gap, transport fault or departure | Fail | Fail |

Nothing about a passing synthetic result verifies hardware. All returned motion
and automatic-next-command flags remain false.

Regression: `software/runs/model-correction-final-20260914.xml`, **55 passed**.
Real model/prospective exports were reverified to generate both offline proposals.
No original exports, frozen model or training manifest were modified.

## Before the first corrected live command

1. Review and implement an explicit adapter for this proposal schema. Do not
   pass the shifted target into the ordinary two-endpoint campaign and let it
   score against that shifted target. Intended target and transmitted target
   must both be retained, hashed and checked by parent and child.
2. Prefer a single-command attended experiment, initially the decreasing
   approach that currently misses nominal tolerance. Keep source/runtime,
   identity, fresh-baseline, ownership, finite deadline, no-retry and cleanup
   checks. Do not add a hidden return leg or loosen existing motion bounds.
3. Keep the established one-command correction path unchanged until reviewed.
   It consumes older absolute-trial proposals, not these campaign/model records.
   Its quantized-target construction uses `reference_goal['representable_rad']`;
   audit that interaction with the corrected 2047/2048 reference model before
   reusing it. Do not assume the two proposal schemas are interchangeable.
4. Simulate the complete adapter with false nominal arrival, correct nominal
   arrival, mismatched target fields, changing baseline, cancelled dispatch,
   uncertain write, truncated capture, and retained-export reconstruction.
5. On live admission, compare one uncompensated control and one proposed
   corrected command under matched approach conditions, each with fresh baseline
   and immutable originals. A failure ends its attempt; no iterative convergence.
   Assess final intended-target error, drift, settling and capture quality.
6. Repeat a successful corrected experiment before any reusable policy. Use
   external calibrated vision before claiming board/tool-tip accuracy.

No corrected physical command has yet been sent or validated by this proposal.

## Baseline-bound integration increment

Implemented `application/wrist_model_correction_preview.py`:

- Reconstruct the model proposal from frozen bytes and reverified original
  exports; an edited proposal cannot supply a replacement command.
- Check the supplied current context references against the experiment's
  hardware/tool/workcell/protocol references.
- Validate every six-joint baseline row, host recency (100 ms maximum age),
  gaps, stability, historical pose agreement and both movement deltas.
- Keep nominal endpoint and candidate command separate in the canonical preview.
  Independent reconstruction rejects altered target, baseline or authority fields.
- Preserve one command, no retry, speed 20, acceleration 1 and five-second
  observation. The preview has no native admission or motion authority.

The legacy correction proposal's command construction was also corrected:
it now uses target minus measured bias directly, rather than feeding the
reference model's decoded feedback angle back as a command. This prevents
double-applying the command/feedback midpoint offset. Original exports are
unchanged. Previously sealed plans whose reconstructed candidate changes must
fail comparison and be restaged; they must not be silently reused or rewritten.

Focused regression: **95 passed**, recorded in
`software/runs/model-correction-preview-20260914.xml`.
Full selected correction/model/accuracy regression rerun: **497 passed,
17,986 deselected** in 99.90 seconds. An earlier broad invocation emitted one
failure indicator before being interrupted without a traceback; its cause was
not established. The complete rerun passed, so this is not evidence that an
intermittent failure has been diagnosed or resolved.

This is an integration increment, not the completed native adapter. Remaining:
bind this schema into authenticated parent/child request, owned raw baseline,
one-use dispatch and original-capture export/reconstruction, then exercise the
full failure matrix and run the bounded matched live experiment. Normalized
preview samples and matching hashes alone do not authenticate live hardware.
No device was opened and no command was sent during this increment.

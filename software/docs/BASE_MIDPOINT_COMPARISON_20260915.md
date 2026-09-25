# Prospective midpoint comparison: linear versus nearest anchor

## Fixed experiment

The frozen `BASE_LOCAL_MODEL_20260915.json` remains unchanged. Two exact native
v9 targets are arithmetic midpoints of its training command anchors:

- Positive: `(0.025123196519943297 + 0.04257648903988659) / 2` radians.
- Negative: `(-0.01649881603988659 - 0.008249407519943295) / 2` radians.

Only these named targets (`positive-midpoint`, `negative-midpoint`) are admitted
by the new trusted-host staging entry. No arbitrary angle input is introduced.
Fresh actual delta must be >0.5 and <=2.5 degrees, with the planned direction,
starting/target base angles within +/-5 degrees, the existing six-joint baseline
match, and all five nonselected-joint checks. One command, speed 20, acceleration
1, synchronized baseline, five-second post capture, no retry or return.

The negative midpoint is first because the current reported base position is
within the negative model's observed starting-angle range. The positive model
must not be used from an incompatible start or when it predicts movement
opposite to the command approach.

## Predeclared comparison

Freeze both predictions using the same fresh six-joint baseline before motion.
The nearest-anchor distance tie rule is **lower command angle**, with distances
within 1e-12 rad treated as tied. This deterministic rule is retained in the
prediction record; it cannot be changed based on the observed result.

Each model's absolute prediction error is compared with the existing 0.25-degree
screen. Report both numerical errors even if both pass. Prediction agreement is
separate from nominal endpoint arrival. A single midpoint cannot validate a whole
direction, establish model superiority, or enable compensation.

## Software changes and verification scope

- v9 intent, fixed target allowlist, fresh-start validation, synchronized capture.
- Trusted-host wizard staging and bench named-profile entry.
- Supervisor version admission and unchanged independent export reconstruction.
- Explicit nearest-anchor prediction in the offline predictor.
- Tests: both fixed targets, wrong target/joint, changed bounds, extra leg,
  bad baseline, cancellation, uncertain writes, misses, wizard review, full
  child/export composition and deterministic tie handling.

No hardware change, global gain, inverse correction or automatic compensation.

## Completed validation and results

Focused tests: 50 passed. Broad regression: **627 passed**, 156 inapplicable
profile combinations skipped (`runs/base-midpoint-regression-20260915.xml`).
Both predictions were saved before their respective command; the model file
and canonical hash were checked again during scoring. The original eight-row
training dataset and model were not retrained with either midpoint.

| Test | Command deg | Reported final deg | Linear prediction error deg | Nearest-anchor error deg |
|---|---:|---:|---:|---:|
| Negative midpoint | -0.7089843802 | 0.4394531285 | +0.0439453186 | +0.0878906372 |
| Positive midpoint | 1.9394531285 | 0.8789062569 | +0.0878906372 | +0.3515624913 |

Linear mean absolute error across these two prospective cases: **0.0659179779
degree**. Nearest-anchor MAE: **0.2197265642 degree**. Both linear predictions
passed the frozen 0.25-degree screen; nearest anchor failed the positive case.
This supports choosing the simple local line for a bounded follow-up experiment,
not a general accuracy claim. Both nominal destinations were still missed.

### Negative capture

- Baseline: `operation-27c3098527b2408d983d336601d80d28`.
- Campaign: `campaign-aee93c474a594f8a8a8987d8baec9e71`.
- Report SHA-256: `03b5a8c4f7684e1d062e958c8965de8cdeef851d1084a7f5bdb052a12640e67d`.
- Prediction file: `runs/BASE_NEGATIVE_MIDPOINT_PREDICTION_20260915.json`.
- One confirmed 65-byte command; five seconds / 281 poses / 57,823 bytes.
- Final 228 base samples constant for at least 4.063 seconds.
- Nominal error +1.1484375087 degrees; `TARGET_MISSED`.

### Positive capture

- Baseline: `operation-ec3bf734f99148e89910ac7aea9b2dc8`.
- Campaign: `campaign-9a7f7c335aaa48668db239ad54c49acf`.
- Report SHA-256: `0a77d6b4f3274c4894ce33e1cd773c0192167bbcb021c287a684c9ee04dbd189`.
- Prediction file: `runs/BASE_POSITIVE_MIDPOINT_PREDICTION_20260915.json`.
- One confirmed 63-byte command; five seconds / 282 poses / 57,708 bytes.
- Final 232 base samples constant for at least 4.125 seconds.
- Nominal error -1.0605468715 degrees; `NO_RESPONSE` denotes movement below
  the 0.5-degree monitor threshold, not zero reported encoder movement.

Both exports independently reconstructed; no capture errors, other-joint drift
beyond tolerance, excursion, uncertain write or pending I/O. Handles closed.
Actual six-joint starts, targets and context matched the frozen prediction inputs.
Score: `runs/BASE_MIDPOINT_COMPARISON_SCORE_20260915.json`.

## Next bounded compensation experiment

Design an offline inverse proposal for a desired reported base endpoint inside
the demonstrated output range. Reverify the frozen training/held-out originals
before proposing it. Keep desired endpoint and transmitted motor target separate,
screen both against the actual start, avoid extrapolation and recheck approach.
Add a versioned native correction profile and simulate its entire owned path
before any corrected movement. Compare it with an uncorrected control in matching
context. Positioning moves must remain separately admitted and labeled.

The current reported base angle is 0.8789062569 degrees, outside the positive
model's observed starting-angle range. Do not apply its inverse directly here;
a separately reviewed positioning move and fresh baseline are needed first.
The negative model and positive model are distinct; no coefficients are shared.
No corrected base command has been issued and no Cartesian accuracy is verified.

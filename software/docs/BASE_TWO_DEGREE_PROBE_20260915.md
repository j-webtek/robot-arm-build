# Base magnitude comparison: version 8

## Purpose and predeclared predictions

Compare a two-degree uncorrected request against the earlier one-degree probes.
The earlier positive captures each changed by 0.0878906372 degree. At two degrees:

- Fixed directional shortfall predicts about +1.0878906372 degree change.
- Proportional response predicts about +0.1757812744 degree change.

These are diagnostic hypotheses, not validated models or compensation commands.
One new observation cannot prove the cause or release generalized compensation.

## Implementation

- Intent v8 selects base only, exactly one nominal +/-2-degree request.
- Fresh-start actual delta must be >1.5 and <=2.5 degrees with matching direction.
- Starting and commanded base positions remain within +/-5 degrees.
- Speed 20, acceleration 1, one command, no automatic retry or return.
- Existing five other-joint checks and endpoint tolerance remain unchanged.
- Mandatory synchronized baseline: 1.25-second retained capture containing at
  most 250 ms / 4096 bytes of startup, then at least one clean second.
- Five-second post capture and independent original-bound export reconstruction.
- Wizard uses its existing trusted-host staging and reviewed single-use slot.
- CLI: `--base-probe plus-two --synchronized-baseline` (or `minus-two`).
  Two-degree requests without synchronization are rejected before device access.
- v6/v7 remain one-degree profiles; their validation rules are not widened.

## Rollout

Test axis/target/limit substitutions, envelope and fresh-start violations,
startup fragments, cancellation, uncertain writes, misses, parent reconstruction,
supervisor version dispatch and full wizard export. Then acquire a fresh baseline
and send only the positive probe. Review raw capture and endpoint before any
new movement. Record the two predictions above without modifying them afterward.

## Completed implementation and first live result

- Focused validation: 58 passed. Broad regression: **582 passed**, 92 inapplicable
  profile combinations skipped (`runs/base-two-degree-regression-20260915.xml`).
- Fresh planning baseline: `operation-6cf7ec6b33224e5aabc1eccd58525f33`, no motion
  writes and clean closure. Six reported joint coordinates matched the earlier
  increasing-probe starting pose.
- Campaign: `campaign-24ab41bbf99d4d8aac6c7c8a0f81861b`.
- Verified report SHA-256:
  `fc53925d2cc67ea71b691573518c91c1385075d23c9c9b41e569de58d6839980`.
- One confirmed 63-byte T101 joint-1 command, speed 20 / acceleration 1;
  no write uncertainty, retry or return.
- Start **0.4394531285 degrees**; intended/transmitted target **2.4394531285 degrees**;
  reported final **1.0546874740 degrees**.
- Reported change **+0.6152343455 degrees**; signed error **-1.3847656545 degrees**.
- Baseline synchronization retained 137 startup bytes in a 13,760-byte original.
- Post capture: five seconds, 281 poses, 57,637 raw bytes. Final 216 base samples
  constant for at least 3.843 seconds of host acquisition time.
- No other joint exceeded drift tolerance, no base excursion, no capture errors,
  all handles closed and zero pending I/O. Independent reconstruction succeeded.
- Preserved endpoint verdict: `TARGET_MISSED`. The command was sent successfully;
  the nominal destination was not reached.

## Interpretation and next step

Observed change was 0.4726562917 degree **below** the fixed-shortfall prediction
and 0.4394530712 degree **above** the proportional prediction. Neither simple
one-degree-derived hypothesis predicts this point closely enough to justify
using it for compensation. This is only one two-degree sample: it does not
identify a mechanical cause or demonstrate a general nonlinear mapping.

Next collect a separately admitted negative two-degree probe from the fresh
current reported pose, then comparable repetitions with explicitly reviewed
positioning. Maintain speed/load/context and preserve misses as observations.
Do not add 1.3848 degrees blindly, multiply by an inverse response ratio, or
fit a flexible model to these few observations. Device freshness and actual
Cartesian tool-tip accuracy remain independently unverified.

Machine-readable result: `runs/BASE_TWO_DEGREE_RESULT_20260915.json`.
Original export: `runs/wizard-exports/campaign-24ab41bbf99d4d8aac6c7c8a0f81861b/`.

Follow-up: the negative two-degree probe completed its capture and missed its
endpoint as well. See `BASE_TWO_DEGREE_DIRECTIONS_20260915.md` for the verified
comparison and the next fixed-target repetition design.

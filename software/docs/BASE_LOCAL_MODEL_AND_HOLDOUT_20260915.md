# Base dataset, local hypotheses and first unseen-target test

## Built

`application/base_endpoint_dataset.py` provides read-only analysis:

- `build_base_dataset`: reverify pinned portable exports and reread original
  request, six-joint baseline and post captures with bounded byte/hash checks.
  Keep target misses and subthreshold responses explicitly labeled. Require
  clean captures, permissible monitoring verdicts and a stable final tail.
- `fit_local_base_lines`: aggregate repetitions within exact command/direction
  groups, then fit two-anchor lines. Reject mixed context, speed or other-joint
  pose, duplicate campaigns and insufficient anchors. Expose capture profiles.
- `predict_unseen_base_target`: interpolation only, within observed starting-angle
  and other-joint context. Reject anchor reuse, extrapolation and predictions
  inconsistent with the requested approach direction. No inverse or motion permit.

Tests: **12 passed**, `runs/base-dataset-regression-20260915.xml`.
No native admission or movement-profile changes were made.

## Frozen training data

Eight original captures, two repeats at each of four command/direction groups.
Repeats are grouped, not split into fake independent target validation.

- Dataset: `runs/BASE_ENDPOINT_DATASET_20260915.json`.
- Canonical dataset SHA-256:
  `aba418750431a590fc96d2c303bf3966d8b8b25445b51bdbc282fde97eb37b5c`.
- Model: `runs/BASE_LOCAL_MODEL_20260915.json`.
- Canonical model SHA-256:
  `643f9b946319c400de08f2a508700ee27afd500f55e084dc8c7a5cf7f5d40852`.

Each direction has a separate line predicting **reported final angle from the
transmitted absolute command**. This is not a command-to-physical-position model.
Increasing slope: approximately 0.527344; decreasing slope: approximately
0.185950. Intercepts are retained in radians in the model. Do not interpret
these local slopes as global actuator gains or use their inverse blindly.
Training capture versions v6/v7/v8 remain disclosed. The model is not validated
globally, is not retrained with the test below, and cannot enable compensation.

## Prospective held-out test

Before motion, `runs/BASE_HELD_OUT_PREDICTION_20260915.json` froze:

- Fresh planning baseline: `operation-5b76cae41b474dd79c12c73b240d8e34`.
- Starting base coordinate: 0.3515624913 degrees.
- Unseen transmitted target: **2.3515624913 degrees**.
- Predicted reported final: **1.0083388994 degrees**.
- Prediction tolerance: **+/-0.25 degree**, separate from nominal arrival tolerance.
- Exact model file/canonical hashes and six-joint expected pose.

The target lies strictly inside the positive training interval and is not an
anchor. It is near the upper anchor, so this is not a strong test of the entire
interval. The existing synchronized v8 +2-degree profile admitted it normally.

Live campaign: `campaign-5f6f0189cac1462a842f65edc94f2753`.
Parent report SHA-256:
`1973d6fbc2df1a495858c45c57f312f816704acdff58a06a2306fcc952a53bb6`.

Actual six-joint start, context and transmitted target matched the frozen
prediction. One confirmed 63-byte command; no retry or correction. Five-second
post capture: 281 poses, 57,667 raw bytes; final 187 base samples constant for
at least 3.329 seconds. No other joint exceeded drift tolerance, no excursion,
no capture errors, all handles closed. Export reconstructed independently.

## Score and limitations

- Reported final: **1.0546874740 degrees**.
- Prediction error: **+0.0463485745 degree**; the frozen prediction screen passed.
- Nominal target error: **-1.2968750174 degrees**; arrival still failed.
- Preserved endpoint verdict: `TARGET_MISSED`.
- Score: `runs/BASE_HELD_OUT_SCORE_20260915.json`.

An after-the-fact descriptive nearest-anchor comparison predicts the endpoint
exactly (zero error). That comparator was not predeclared, so it is not a separate
prospective win; nevertheless this test does not establish an advantage for the
linear model. One unseen target is insufficient to choose between interpolation,
lookup/quantization or more complex pose/history effects.

Next freeze and compare linear and nearest-anchor predictions at additional
unseen targets, including the negative direction and farther from the anchors.
Any target outside the currently enumerated native profiles requires explicit
bounded integration/testing; do not alter a baseline or intent to manufacture
admission. Only after independent prediction evidence should we design a local
corrected-command experiment and compare it against an uncorrected control.
No automatic compensation or claim of physical Cartesian accuracy is released.

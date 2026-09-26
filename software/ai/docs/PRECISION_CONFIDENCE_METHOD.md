# Precision confidence and capture provenance development plan

Status: proposed research method; no calibrated confidence or qualification installed.

Observation confidence must describe a declared per-target event. Proposed event:
the detected target identity is correct and its predicted center lies within a
predeclared localization tolerance in the independently labelled target plane.
The tolerance, domain, target vocabulary and confidence-estimator version must be
fixed before calibration. Confidence is an estimated event probability; it is not
the uncertainty qualification's coverage probability or scene-model confidence.

Current KeyboardPoseNet outputs pose only. Its existing precision schema lacks
this confidence value, capture-service identity and authenticated clock provenance.
Keep `precision_binding_v2.preflight` abstaining. Do not insert a constant score,
reuse the scene score, or treat a small pose residual as calibrated confidence.

## Research sequence

1. Freeze the event/tolerance and capture-domain definition. Independently label
   target identity, target centers, visibility and occlusion; hidden renderer truth
   may label synthetic research only, never runtime placement.
2. Train a separate correctness estimator or confidence head on development data.
   Potential inputs include local target image features and visibility signals;
   ground truth and evaluation residuals must never be inference inputs.
3. Fit probability calibration on disjoint calibration groups. Group views by
   capture/scene to avoid correlated-view leakage. Keep pose training, confidence
   fitting and held-out evaluation identities explicit.
4. Evaluate reliability bins with counts, Brier score, abstention/coverage and
   false-accept rates on untouched groups. Select operating thresholds before
   inspecting evaluation labels; preserve failed results. No numeric release
   threshold is claimed in this plan: both lanes must approve domain-specific
   acceptance criteria before a qualification attempt.
5. Version a precision record binding per-target coordinates/confidence to image,
   model, confidence-method, event/tolerance and capture receipt. Consumer registry
   validates supported method and domain. Keep localization bounds separate.

## Capture binding implemented now

`rocell_ai.capture_binding.bind_capture` compares image bytes, frame, capture ID,
UTC millisecond timestamp, camera identity and clock-domain identity against an
externally supplied trusted receipt and shared MotionEvidenceV2. It rejects
mismatches/tampering and returns None when no trusted receipt exists. It accesses
no camera and installs no registry. Caller-supplied trust is not authentication.
A real capture-service adapter must authenticate the issuer and clock mapping;
model output cannot populate that registry. Capture binding alone cannot remove
the missing-confidence or localization-qualification blockers.

The receipt format is AI-internal research input, not a change to ModelMotionBatch.
Its result is not a permit, admission result, or calibration. Scene-lease freshness
and pre-planner revalidation remain arm-owned checks.


## First frozen synthetic experiment

The 4,225-parameter frozen-pose-feature head failed its predeclared criteria.
See `eval/localization_confidence_v0_scorecard.json`: held-out Brier 0.2353,
0/41,400 accepted at threshold 0.95, epoch 8 selected using development BCE.
This result cannot supply runtime observation confidence. The original threshold,
all failures and consumed seed ranges remain fixed. Study local image features
using development evidence before committing a new experiment; reserve fresh
calibration and evaluation groups. No runtime promotion follows from training.


## Local patch development comparison

Adding a predicted-target-centered grayscale patch (6,273-parameter head) reduced
Brier on the reused development set from 0.22393 to 0.22199. Both versions accept
zero at threshold 0.95. This is an optimistic feature-selection comparison, not
held-out improvement. No additional calibration/evaluation seeds were consumed.
See `eval/local_features_dev_v0_scorecard.json`. Investigate localization/feature
resolution before another held-out run; runtime abstention remains unchanged.

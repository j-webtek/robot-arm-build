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


## Resolution sensitivity diagnostic

On existing development groups, the unchanged pose model has 1.032 mm mean error
at its trained 128x96 input size. Feeding native 256x192 without retraining worsens
mean error to 13.503 mm. This is distribution-shift evidence, not a high-resolution
training comparison. A 1 mm tolerance is about 0.21 input pixel at 128x96, but
subpixel regression remains possible; do not assert a hard pixel accuracy floor.
Next compare matched-resolution training on development data before reserving a
new held-out experiment. See `eval/resolution_development_v0_scorecard.json`.


## Matched-resolution development fine-tuning

Equal-budget paired fine-tuning from the same checkpoint selected epoch 11 for
both sizes. Development mean/p95 errors were 0.945/2.065 mm at 128x96 and
1.442/3.530 mm at 256x192. Retain 128x96 as the development reference; this is not
runtime promotion. Shared pretraining at 128x96 and a single training seed limit
claims about resolution. No new calibration or evaluation data was accessed.
See `eval/matched_resolution_v0_scorecard.json`. Next investigate local geometric
refinement before another confidence or held-out qualification run.


## Rejected edge-centroid refinement

A fixed local edge-centroid correction capped at 1 mm worsened paired development
mean error from 0.945 to 1.237 mm and within-1mm rate from 63.1% to 45.9%.
Do not enable this heuristic. The diagnostic and failure remain in
`eval/local_refinement_v0_scorecard.json`; unit tests only confirm bounded behavior.
Next decompose translation, orientation and scene-condition errors before choosing
further model changes. No additional calibration/evaluation data was consumed.


## Development error attribution

Translation-only counterfactual mean key error is 0.885 mm versus rotation-only
0.278 mm (full prediction 0.945 mm). This supports prioritizing board-center
translation training while monitoring yaw. Counterfactuals use hidden truth only
for scoring and cannot be deployed. Challenge mean error is 1.067 mm versus
standard 0.868 mm; bundled augmentations do not isolate causal lighting or
obstruction contributions. See `eval/pose_decomposition_v0_scorecard.json`.


## Translation-weighted development candidate

A paired 4:4:1 XY/yaw loss versus 1:1:1 improved mean key error from 0.937 to
0.907 mm and within-1mm rate from 64.8% to 69.0%; yaw p95 also improved from
0.617 to 0.571 degrees. This meets the frozen development rule only. Candidate
and control now need a separately frozen fresh held-out comparison. Do not use
this pose improvement as observation confidence or localization qualification.
See `eval/translation_weighted_v0_scorecard.json`; no runtime checkpoint changed.


## Fresh paired evaluation

The translation-weighted candidate passed the frozen comparison on 500 fresh 18M
seed groups (1,500 synthetic images). Mean key error improved 0.947->0.868 mm,
p95 2.139->1.934 mm and within-1mm 62.8%->68.9%; all per-condition criteria passed.
Worst observed error increased 6.976->7.094 mm. This is evidence for independent
uncertainty calibration next, not runtime promotion or observation confidence.
18M evaluation groups are consumed. See `eval/translation_pair_v0_scorecard.json`.


## Candidate uncertainty study

Fresh 19M calibration / 20M evaluation produced a 5.201783 mm empirical radius
with 98.8% evaluation group error coverage. Full uncertainty disks fit every
actual key across all three conditions in only 380/500 groups (76%), below the
frozen 95% criterion. Combined study fails; no qualification installed. Individual
fit is 64,859/69,000 and must not replace the group criterion. Hidden target truth
remains evaluation-only. See `eval/candidate_uncertainty_v0_scorecard.json`.
Investigate tails on development data before changing the uncertainty method.


## Development tail stratification

At a fixed >3mm maximum-key-error threshold, 22/600 existing development images
have large errors: 5 standard, 7 appearance-shift and 10 challenge. Every position
quadrant and yaw bin contains failures. These are confounded descriptive strata,
not evidence for truth-based runtime exclusion or isolated obstruction causality.
See `eval/development_tails_v0_scorecard.json`. Next use paired single perturbations
on development images before targeting augmentation or abstention design.


## Paired added perturbations

At fixed tested strengths on 200 existing standard development images, halving
brightness raises mean key error 0.853->2.515 mm and >3mm-image count 5->87.
Blur sigma1.2 and one small fixed obstruction change means much less (0.832 and
0.871 mm). This supports prioritizing brightness-augmentation training, not
claiming generic blur/occlusion safety or a physical brightness threshold.
See `eval/single_perturbations_v0_scorecard.json`. No new held-out data consumed.


### Paired brightness augmentation development result

The frozen `train/brightness_pair_v0_plan.json` experiment improves darkened
standard-image mean error from 2.400 to 0.879 mm and reduces images with maximum
key error above 3 mm from 87 to 5 of 200. It **fails** the predefined per-condition
rule: standard, appearance-shift and challenge localization and yaw regress,
with large-error counts increasing in all three. Aggregate improvement does not
override these failures. Both arms have equal training budgets and select epochs
using the same development objective. The candidate is retained as failed research,
not promoted. See AI-052 through AI-054 and the paired scorecard for exact evidence.

Next: a frozen, bounded comparison with less dark-sample weight and a lower learning
rate, preserving the baseline-condition gates. These are reused development groups;
fresh calibration/evaluation remains necessary after any development success.


### Reduced brightness augmentation result

The follow-up uses 25 percent darkened training images and learning rate 0.00005
in both matched arms. It also **fails** the unchanged development criteria:
dark-image mean improves 2.577 -> 0.911 mm, but standard and appearance-shift means
exceed allowed regressions; all original-condition large-error counts and yaw-p95
checks regress. This joint intervention does not isolate the two parameter effects.
AI-055 through AI-057 retain the exact evidence. Neither brightness candidate is
promoted, and no new held-out groups were consumed.

Next research step: predeclare an otherwise matched comparison with an explicit
baseline-preservation distillation loss on original-condition training images.
Retain all per-condition gates; a lower aggregate mean cannot justify promotion.


### Baseline-preservation distillation result

Adding weight4 frozen-teacher preservation on original training images improves
original-condition means versus an otherwise matched augmentation control, but
**fails** the combined development gates. Darkened-image mean worsens 0.910 ->
1.012 mm; its >3mm image count rises 4 -> 12. Original-condition tails remain
above the frozen nonaugmented reference. Neither this candidate nor the matched
control is promoted. AI-058 through AI-060 retain source, hashes, cases and tests.

Next: freeze a bounded photometric-normalization diagnostic using the unchanged
initial checkpoint and the same per-condition limits. All three failed training
variants remain evidence; preprocessing must also earn fresh evaluation and
calibration before any runtime adoption.


### Fixed lighting normalization result

A fixed pixel-only luminance gain on the unchanged translation checkpoint passes
11/12 development checks but **fails the combined rule**. Darkened-image mean
improves 2.512 -> 0.845 mm; >3mm image count86 -> 6/200. Appearance-shift count
increases7 -> 8, violating the no-tail-regression criterion. AI-061 through AI-063
retain exact source, paired cases and tests. No preprocessing is installed.

Next: inspect paired appearance-shift threshold crossings and associated images
before another intervention. Do not relax criteria or treat the close development
result as calibration, generalization or physical evidence.


### Paired crossing diagnosis

AI-064 through AI-066 show that normalization recovered81 dark-image failures
while introducing1, leaving6 failures. Appearance-shift retained all7 previous
failures and introduced1. That new case changes maximum error1.604 -> 3.821 mm,
mainly translation, without pixel saturation; its gain overlaps gains of passing
cases. Paired image inspection alone does not establish the cause. The original
acceptance failure remains unchanged.

Next: predeclare a bounded pixel-only dark-image correction comparison, retaining
all acceptance limits. Any darkness threshold is a research parameter; physical
calibration and fresh evaluation remain separate requirements.


### Dark-only normalization development pass

AI-067 through AI-069 record a pass of all12 unchanged development checks for
correction only when pixel p95 luminance<128. Standard and appearance-shift images
are bypassed exactly; darkened mean2.512 -> 0.845 mm and >3mm count86 -> 6/200;
challenge mean1.033 -> 0.995 mm and count10 -> 9. This is selected on reused
development groups and is not generalization or physical evidence. No runtime
preprocessing or qualification is installed; all earlier failures remain intact.

Next: freeze fresh-seed evaluation, unchanged correction and acceptance rules,
with additional brightness levels near the threshold. Retain absolute errors,
all failures and post-evaluation limitations before confidence/calibration work.


### Fresh synthetic dark-only normalization evaluation

AI-070 through AI-072 pass all21 prespecified relative checks on500 unseen21M
seed groups across7 conditions. Darkened mean2.665 -> 0.854 mm, >3mm count228 ->
9/500; standard/appearance unchanged and challenge improved. Brightness factors
0.55/0.60/0.65 also pass. The correction and checkpoint were frozen;21M data is
now consumed. This is evidence within the same synthetic renderer, not physical
camera generalization, calibrated confidence or permission for motion.

Next: fresh uncertainty calibration and separate evaluation beyond21M using this
exact preprocessing. Retain full target-region containment and coverage criteria;
oracle geometry remains scoring-only and cannot become runtime calibration.


### Normalized uncertainty study remains blocked

AI-073 through AI-075 calibrate on fresh22M groups and evaluate on fresh23M groups
with frozen preprocessing over seven conditions. The6.042 mm global radius covers
99% of500 evaluation groups, but full predicted-disk containment in true key
regions passes only13% (65/500), below95%. Combined criteria **fail**; no
qualification is installed. Both seed ranges are now consumed. Earlier three-
condition studies are not matched comparisons of normalization effects.

Next: predeclare an image-conditioned uncertainty/abstention feasibility study
using development data. Preserve coverage and containment requirements and avoid
post-hoc radius reduction. Any selected method needs separate fresh calibration
and evaluation beyond23M; hidden target geometry remains scoring-only.


### Conditional disagreement feasibility

AI-076 through AI-078 pass a development-only study using prediction disagreement
under fixed brightness perturbations to choose a bin-specific radius and abstain
above3mm. Acceptance20%..73.5% per condition; accepted-group coverage96.26% and
containment97.86%. Fitting includes pose-training seeds, so these are optimistic
feasibility results, not calibrated confidence. Three inference passes are needed;
stable predictions can still share error. No runtime installation occurs.

Next: freeze the same method on fresh24M calibration and25M evaluation groups,
refitting radii only on calibration. Preserve availability and accepted-image/group
coverage/containment criteria; retain any failure without post-hoc changes.


### Fresh conditional uncertainty fails availability

AI-079 through AI-081 preserve the same method on fresh24M calibration and25M
evaluation. The smallest calibrated bin radius increases to4.289 mm; all four
radii exceed the fixed3mm cap. The method abstains on all3500 evaluation images,
so availability fails and accepted coverage/containment are undefined. The prior
development pass is retained but does not generalize. No runtime qualification
or threshold relaxation occurs; both new ranges are now consumed.

Next: inspect retained24M low-disagreement/high-error calibration examples to
understand stable prediction errors before selecting another intervention.
Do not optimize against25M evaluation; revised methods need new independent data.


### Stable prediction errors on retained calibration

AI-082 through AI-084 inspect only24M calibration evidence:70 of3263 images
with brightness disagreement<=0.25mm still have key errors>3mm, across35 scenes.
The worst representative has11.39mm center error despite0.17mm disagreement.
Brightness consistency therefore misses substantial stable error. Selected images
show distractors/obstructions, but no causal conclusion is established.25M results
are not used for this diagnosis, and the original failure remains unchanged.

Next: predeclare a spatial-shift consistency diagnostic on reused development
splits, undoing only known synthetic image shifts. This is not measured runtime
calibration; any chosen method needs separate future calibration/evaluation.

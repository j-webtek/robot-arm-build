# Image-dependent uncertainty scale

## Implemented prototype

The frozen pose model remains unchanged. A separate56-feature extractor accepts only an RGB image. Before pose brightness normalization, it measures eight global brightness/contrast/edge statistics and three statistics per tile on a4x4 image grid. It uses no simulator labels, masks, target coordinates or errors at inference.

A ridge regressor (fixed alpha1.0) predicts log(maximum target error +0.1mm). Exponentiated outputs are clipped to0.1..20mm as specified before execution. This value is an error scale, not a confidence probability or upper bound. The regressor uses training labels; pose parameters are frozen.

## Training-only evidence

Scenes33000000..33000599 are allocated to uncertainty training-selection only. Each has rectangle and ellipse obstruction styles with four conditions, totaling4800 images. Five scene-grouped folds keep all eight variants together. Each fit uses3840 images; validation uses960. Normalization and labels for each fit come exclusively from its training rows.

The fixed feasibility requirement was lower out-of-fold log-error MSE than a fold-training constant estimate in every condition. Results (constant -> image scale):

| Condition | Constant MSE | Image-scale MSE |
| --- | ---: | ---: |
| Standard |0.242925|0.234846|
| Appearance shift |0.259529|0.246693|
| Partial obstruction |0.240460|0.233817|
| Full obstruction |0.270347|0.254223|

The requirement passed. This does not demonstrate useful calibrated acceptance, accuracy under real lighting or occlusion, or physical qualification. No consumed calibration/confirmation rows were used as fit or selection data. Three verification tests passed. Fold coefficients and row-level evidence remain in eval/image_quality_scale_v1_report.json.

## Next experiment

Freeze a single full fit using these600 uncertainty-training scenes, the existing feature list and alpha1.0. Export the scalar regressor with the exact pose-model hash and preprocessing identity; verify standalone image inference parity. Do not alter pose weights.

Then freeze two disjoint unused scene ranges for calibration and confirmation after checking shared claims. Use one normalized score per calibration scene: maximum(error_mm / predicted_scale_mm) over all46 targets and four condition variants. Fit the99% scene quantile using the same finite-sample rank rule as the prior global experiment. For an image, its research radius is that fixed quantile times its predicted image scale. No oracle labels or error may enter that inference computation.

Keep the3mm research tolerance and require at least99% observed scene coverage plus nonzero accepted fraction on independent confirmation. Report acceptance and violations both overall and among accepted images/scenes, including every condition, with scenes as the independent unit. Marginal coverage does not imply conditional coverage among accepted images; neither supports physical qualification. Preserve failure without tuning. All previous calibration and confirmation ranges remain consumed and excluded from this new fit/calibration/confirmation chain.

ModelMotionBatchV2 and runtime admission remain unchanged. Measured target placement, calibrated transforms, actual contact margins, freshness and capability evidence are still required by the arm lane.


## Final fit and independent calibration outcome

The single full fit exported as5328-byte JSON (SHA256476a64054981226d63afe119d124188b1946cf9f8debbad83ae605d018fd8082). Reload predictions are exact; image-by-image parity on4800 training images differs by at most2.22e-16mm.

Separate34M calibration produced normalized quantile4.75657008897. Independent35M confirmation covered994/1000 scenes(99.4%) and3986/4000 images(99.65%), but accepted zero images at the unchanged3mm tolerance. The experiment fails its utility requirement. Zero accepted violations provides no accepted-subset assurance. Both ranges are now consumed. Different cohorts prevent a controlled claim that this scale improved coverage over the earlier global bound.

Four verification tests passed; failed utility evidence remains immutable. Before another calibration attempt, audit33M out-of-fold risk ranking to determine whether the features distinguish low-error images at all. Use training-only evidence; do not tune on these consumed calibration or confirmation rows. Pose/scale weights and runtime baseline remain frozen, with no physical qualification or motion authority.


## Training-only ranking audit

Frozen audit ebc27f659e84b68283f436fbfc3093278e3cf881 used only the saved33M out-of-fold predictions. Image tail-error AUROC is0.687362 and Spearman correlation0.226719; scene-maximum AUROC is0.590133 and correlation0.191710. These are descriptive, not significance claims.

At the fixed lowest10% retention,481 images include5 tails(1.0395%); the extra image is included because scores tie at the boundary. The lowest60 scenes include5 tails(8.3333%), compared with49/600(8.1667%) across all scenes. At25% scene retention,9/150 fail(6%). The features contain some signal but do not reliably isolate clean scenes. No diagnostic threshold was chosen for runtime or calibrated admission.

Three regression tests passed. No fitting, new images, calibration or runtime changes occurred. The zero-utility confirmation remains unchanged.

## Next bounded comparison

Before fitting, freeze a training-only comparison of the existing56 raw-image features against the frozen pose backbone's512 pooled spatial features. Use the same33M scene folds and error labels, alpha1.0, fold-only normalization and log(error+0.1) target. Keep the pose network frozen. Compare per-condition out-of-fold log-error MSE, scene tail AUROC and the same fixed retention curves. Require lower MSE in every condition and higher scene tail AUROC than the56-feature reference before considering another full fit or calibration. Preserve all failures; do not choose retention thresholds from this diagnostic. No31M/32M/34M/35M fitting or selection is allowed. Any subsequent calibration and confirmation still require independent, separately frozen data.

## Frozen-backbone comparison

The registered 512-feature comparison was executed on the same 600 scenes and
five grouped folds. The pose network and confirmed residual pose output remained
frozen. Each uncertainty fit used pooled 4 by 4 spatial features from the frozen
pose backbone, fixed ridge alpha 1.0, and the same `log(error + 0.1)` target as
the 56-feature image-statistic model.

The fixed comparison failed:

| Condition | 56 image features | 512 backbone features | Better |
| --- | ---: | ---: | --- |
| Standard | 0.234846 | 0.227759 | Backbone |
| Appearance shift | 0.246693 | 0.238840 | Backbone |
| Partial obstruction | 0.233817 | 0.234341 | Image statistics |
| Full obstruction | 0.254223 | 0.260045 | Image statistics |

Scene tail-error AUROC also fell from 0.590133 to 0.562354. The candidate
therefore fails both prerequisites for another calibration run: improvement in
every condition and improvement in scene-level tail ranking. Three verification
tests passed, and no new images or calibration ranges were consumed.

This closes the simple linear-head path for the current representation. The
next uncertainty experiment should learn an error-relevant representation on
training-only scene groups while keeping the confirmed pose output frozen. It
must improve partial/full obstruction metrics and scene-level tail ranking
before any full fit, export, calibration, or confirmation is attempted. The
consumed 31M, 32M, 34M, and 35M cohorts remain excluded from selection.

## Nonlinear frozen-feature study

A fixed 16,689-parameter nonlinear head was trained on the same frozen 512
descriptors with all scene variants grouped. The head used two GELU hidden
layers, one deterministic seed per fold, and a fixed 30-epoch schedule. There
was no architecture, learning-rate, epoch, or seed sweep.

The nonlinear head improved scene tail-error AUROC from 0.590133 to 0.644431.
It did not learn a reliable error magnitude: log-error MSE worsened from
0.234846 to 0.312227 on standard images, 0.246693 to 0.263520 on appearance
shift, 0.233817 to 0.336033 under partial obstruction, and 0.254223 to 0.336248
under full obstruction. The registered composite requirement therefore fails.

This separates two concerns that the previous experiments combined. The
frozen descriptors contain some learnable signal for ranking risky scenes, but
the tested nonlinear regressor does not provide a useful scale for calibrated
metric bounds. Another scale-calibration run is not justified.

The next bounded study should formulate scene-tail risk explicitly as a
class-balanced classification problem on the same grouped training evidence.
It must preregister one architecture and schedule, evaluate out of fold, and
report AUROC plus tail rates at fixed retention fractions. It may not select a
runtime threshold or use consumed calibration and confirmation cohorts. A
passing classifier would still require a separately designed calibration and
fresh confirmation chain before any runtime abstention gate could exist.

## Explicit scene-tail classifier

The fixed class-balanced classifier used the same 16,689-parameter architecture
and grouped folds, with a positive label when any of a scene's eight variants
exceeded 3 mm. Only 49 of 600 scenes were positive. Training labels were copied
to all variants within a scene, while scene grouping prevented cross-fold
leakage.

The classifier failed every preregistered comparison. Scene AUROC fell from
0.644431 for the nonlinear error ranker to 0.570540. At fixed 25% retention,
the classifier retained 9 failing scenes out of 150 versus 4 for the reference.
At 50%, it retained 22 failures out of 300 versus 17. Very low training losses
did not transfer to held-out scenes.

No further learned head should be fitted on this exact representation and
600-scene population. The next inexpensive diagnostic is zero-fit geometric
disagreement between the original baseline pose and the confirmed residual
candidate, measured as maximum displacement over all 46 named keyboard targets.
It is deployable because it uses two frozen model outputs and the target map,
without simulator truth at inference. The diagnostic must use grouped 33M
out-of-fold evidence and fixed retention comparisons. If it is weak, the next
uncertainty effort needs either a genuinely diverse pose ensemble or a broader
uncertainty-training population before any new calibration data is allocated.

## Frozen pose-disagreement diagnostic

The zero-fit diagnostic computed maximum target displacement between the
original baseline pose and confirmed residual-candidate pose. This uses two
deployable model outputs and all 46 named targets, with no simulator truth in
the score itself. Truth was used only to evaluate ranking on the existing 33M
training evidence.

The signal failed every fixed comparison. Scene tail AUROC was 0.556317 versus
0.644431 for the best nonlinear risk ranker. At 25% retention, disagreement
kept 12 failing scenes out of 150 versus 4 for the reference; at 50%, it kept
22 out of 300 versus 17. The lowest-disagreement 10% still contained 5 failures
among 60 scenes.

The baseline and residual candidate share the same backbone, so agreement
between them is not independent evidence. This result closes uncertainty work
based on additional heads or comparisons over this single representation and
600-scene population. The next credible path requires a broader, failure-rich
uncertainty-training set and genuinely diverse compact pose models. Their
dispersion must first demonstrate useful grouped training-only failure ranking;
new calibration and confirmation data should not be allocated before that gate.

## Diverse compact pose ensemble

Two independently initialized compact models were trained from scratch on a
new 36M cohort containing 1,600 grouped scenes and 12,800 rendered images. A
172,331-parameter SiLU convolutional network and an 82,763-parameter depthwise
separable network use different feature extractors from the frozen candidate.
The fixed 12-epoch schedules and all acceptance criteria were committed before
training. A disjoint 400-scene, 3,200-image development cohort was used once.

The study failed its fixed composite rule. Maximum pairwise target displacement
had scene tail AUROC 0.646260, below the required 0.70. At 25% retention it kept
6 failing scenes among 100 (6.0%), which did not meet the required 50% reduction
from the overall 11.25% scene failure rate. At 50% retention it kept 15 failures
among 200 (7.5%) and passed that relative reduction check. The lowest 10% did
contain zero failures among 40 scenes, but that descriptive subset was not a
registered independent confirmation result and cannot be promoted into a gate.

Both new members also exceeded the fixed two-times-candidate mean-error limit
under appearance shift: 1.676510 mm and 1.913844 mm versus 0.831711 mm for the
candidate. The remaining condition checks passed. This confirms that a diverse
ensemble can expose some useful ranking signal, while the tested members are
not accurate or stable enough to support calibrated uncertainty or runtime
admission.

The 36,001,600 through 36,001,999 development scenes are now consumed for this
decision and must not be used to tune another schedule, architecture, threshold,
or acceptance rule. The next bounded step should improve diverse member accuracy
and appearance robustness using a newly allocated training/selection cohort,
then test the frozen replacement once on a fresh grouped development cohort.
No calibration or confirmation population should be allocated until that fresh
study passes its preregistered failure-ranking and member-quality requirements.

## Appearance-robust ensemble selection

The fixed revision retained both compact architectures and changed only the
training recipe: 2,400 new grouped scenes, 24 epochs, and double loss weight for
appearance-shift samples. It used 19,200 training images. A disjoint 400-scene,
3,200-image selection cohort was used once for a registered go/no-go decision.

The selection rule passed. Scene tail AUROC rose to 0.717287. The selection
cohort contained 38 failing scenes out of 400 (9.5%); the lowest-disagreement
25% contained 4 failures out of 100 (4.0%), and the lowest 50% contained 10 out
of 200 (5.0%). Both satisfy the registered relative-reduction requirements.
Appearance-shift mean error was 1.298275 mm for the SiLU member and 1.483910 mm
for the separable member, versus 0.878960 mm for the frozen candidate. Both pass
the stricter 1.8-times-candidate selection limit, and every other member-quality
check also passes.

This is training-selection evidence. The selected checkpoints have no runtime,
calibration, confirmation, or physical authority. The 37,002,400 through
37,002,799 selection scenes are consumed and cannot be reused to set the fresh
development decision. The next step is one preregistered evaluation of these
exact checkpoint hashes on a new grouped development cohort, using the stronger
0.70 AUROC requirement and the same fixed-retention and member-quality rules.

## Fresh appearance-robust development gate

The two selected checkpoint hashes were promoted to tracked artifacts and
evaluated without fitting on 1,000 new 38M scenes, totaling 8,000 images. The
registered development rule passed in full. Scene tail AUROC was 0.725281. The
cohort contained 84 failing scenes (8.4%); the lowest-disagreement 25% contained
7 failures among 250 scenes (2.8%), and the lowest 50% contained 23 among 500
(4.6%). Both retained rates satisfy their fixed relative-reduction limits.

All member-quality checks also passed. Appearance-shift mean error was 1.221354
mm for the SiLU member and 1.366111 mm for the separable member, versus 0.839518
mm for the frozen candidate. The full-condition mean errors also remained below
the fixed two-times-candidate limits. No training, calibration, or threshold
selection occurred in this evaluation.

This passage demonstrates repeatable synthetic failure ranking. It does not
produce a metric uncertainty radius or a runtime acceptance threshold. The next
bounded study must freeze a monotonic mapping from ensemble disagreement to an
error scale, an independent scene-grouped calibration population, a finite-
sample coverage target, and a separate confirmation population before viewing
either new cohort. It must retain the 3 mm research tolerance, require nonzero
accepted utility, and preserve failure without tuning. Physical-camera evidence,
calibrated board-to-arm transforms, freshness, and capability checks remain
separate requirements.

## Ensemble-scale calibration and confirmation

The first frozen mapping used `max(ensemble disagreement, 1 mm)` as its image
scale. On 1,000 independent 39M calibration scenes, the 99% finite-sample scene
quantile was 2.865444 at rank 991. An image's research radius was that quantile
times its scale, and radius at most 3 mm was the only acceptance rule. A separate
1,000-scene 40M confirmation cohort was then evaluated without adjustment.

The composite rule failed. Marginal scene coverage passed at 994/1,000 (99.4%),
and accepted-subset coverage was 352/353 images (99.7167%) and 137/138 scenes
(99.2754%). Utility was 353/8,000 accepted images (4.4125%), below the frozen 5%
minimum. One accepted partial-obstruction image exceeded both its predicted
radius and the 3 mm tolerance. Partial accepted-image coverage was 62/63
(98.4127%), below 99%. All four conditions had nonzero accepted utility, but the
failed checks make the complete result a failure.

The 39M calibration and 40M confirmation ranges are consumed. The 5% utility,
3 mm tolerance, and accepted-subset requirements must not be weakened using
this outcome. The next bounded effort should use a new training-selection cohort
to compare a small preregistered family of monotonic disagreement mappings that
can separate the lowest-risk images more sharply, with special attention to
partial obstruction. Only a mapping selected without these consumed rows may
enter another independently frozen calibration and confirmation chain.

## Monotonic mapping selection

Five preregistered mappings raised the floored ensemble disagreement to powers
1.0, 1.25, 1.5, 1.75, and 2.0. Each mapping used the same 1,000 new 41M scenes
for a rank-991 quantile and the same disjoint 1,000-scene 42M cohort for its
training-only selection decision. The 39M and 40M rows were excluded.

No mapping passed. The linear mapping had the strongest near-pass: 99.2% scene
coverage, 935/8,000 accepted images (11.6875%), and 926/935 accepted-image
coverage (99.0374%). It still accepted six images above 3 mm, missed the 99%
accepted-scene requirement at 295/298 (98.9933%), and failed conditional image
coverage for partial and full obstruction. Powers 1.25 through 2.0 retained
9.625% to 11.35% utility but worsened accepted-subset coverage; every mapping
accepted the same six above-tolerance failures.

This closes scalar monotonic remapping of the present disagreement signal. A
monotonic transform cannot repair the ordering of low-disagreement obstruction
failures. The next uncertainty feature must add a deployable obstruction-
sensitive observable rather than another scalar transform. It should be trained
and evaluated only on new grouped training-selection evidence and must improve
partial/full accepted-subset ranking before another calibration pair is
allocated.

## Image-only obstruction signal

A fixed 69,561-parameter classifier was trained on 16,000 raw 43M images to
predict obstruction presence without masks or condition labels at inference.
Its probability multiplied the existing disagreement scale by `1 + p`. Separate
44M mapping-calibration and 45M selection cohorts contained 8,000 images each.

The composite selection rule failed. Classifier AUROC was 0.91947, recall
0.78625, and clean false-positive rate 0.124, missing the frozen 0.95, 0.90, and
0.10 requirements. The combined scale achieved 99.3% scene coverage, 12.675%
utility, and zero accepted errors above 3 mm. Overall accepted image and scene
coverage passed, as did partial-obstruction coverage. Full-obstruction accepted
coverage was only 21/23 (91.3043%), so that condition failed.

This establishes that an obstruction observable can improve utility and remove
above-tolerance accepted errors, but the tested classifier is not reliable
enough for promotion. The next training-only study should improve full-
obstruction recall with localized or multi-scale features and require the same
strict classifier and conditional-coverage checks on fresh selection evidence.

## Localized multi-scale obstruction signal

A compact 34,381-parameter network retained spatial features longer and pooled
both their average and maximum. It was trained on 16,000 new 46M images with
extra loss weight for partial and full obstruction. The image-only classifier
passed every registered classifier check on the disjoint 48M selection cohort:
AUROC was 0.995724, obstruction recall was 0.97875, and the clean false-positive
rate was 0.013.

The unchanged `max(disagreement, 1 mm) * (1 + probability)` scale still failed.
Its rank-991 quantile from 1,000 independent 47M scenes was 1.703479. On 1,000
48M selection scenes, marginal scene coverage was 98.3%, accepted utility was
1,572/8,000 (19.65%), accepted-image coverage was 98.6641%, and accepted-scene
coverage was 98.0322%. It accepted no error over 3 mm, but accepted only 7
partial and 5 full obstruction images. Full-obstruction accepted-image coverage
was 4/5. Standard and appearance accepted-subset coverage also missed 99%.

The classifier checkpoint is retained only as a reproducible research input.
It has no runtime, calibration, physical, or motion authority. These results
separate the next problem: the obstruction detector is effective, while the
fixed multiplicative mapping does not allocate useful uncertainty across clean
and obstructed images. The next bounded study should freeze a small family of
mappings or acceptance rules using the frozen classifier probability and pose
disagreement, select once on new grouped cohorts, and preserve the same
conditional coverage, utility, and 3 mm requirements. The classifier should not
be retrained or selected again in that study.

## Low-gain probability mapping selection

The frozen classifier and pose ensemble were evaluated without training on new
49M mapping-calibration and 50M selection cohorts. Four preregistered gains,
0.05, 0.075, 0.10, and 0.125, scaled floored disagreement by
`1 + gain * obstruction_probability`. No mapping passed.

The mappings accepted 1,206 to 1,387 of 8,000 images, so overall and every
conditional utility requirement passed. Their marginal scene coverage was only
98.4%. Accepted-image coverage ranged from 98.4375% to 98.7562%, and accepted-
scene coverage ranged from 97.5845% to 97.8972%. They admitted 7 to 11 actual
errors above 3 mm. Partial accepted-image coverage ranged from 96.9697% to
97.9487%; full accepted-image coverage ranged from 95.3947% to 95.8042%.

This closes low-gain scalar multiplication of disagreement by obstruction
probability. The classifier detects obstruction well, but a single image-level
class probability does not rank localization error within partial and full
obstruction. The next uncertainty feature needs localized geometric evidence,
such as landmark visibility and per-landmark residual or confidence, rather
than another global probability transform. Any such feature must use new
training-selection cohorts and cannot install runtime authority without a later
independent calibration and confirmation chain.

## Frozen localized geometric ranking

Three localized scores were evaluated without fitting on 1,000 new 51M scenes:
maximum pose-to-landmark corner residual, the same residual weighted by each
corner's predicted visibility, and a fixed fusion with ensemble disagreement.
All inputs came from frozen image models. No truth pose, geometric occlusion
mask, or condition label entered a score.

No localized score passed. Ensemble disagreement produced grouped scene AUROC
0.681113 with failure rates 5.6% and 6.2% in its lowest-risk 25% and 50%.
Maximum corner residual produced AUROC 0.566975; visibility weighting improved
it to 0.599522. The fixed fusion reached only 0.637970, with lowest-quartile and
lowest-half failure rates of 4.8% and 8.4%. Although its partial-obstruction
image AUROC was 0.812289, full-obstruction image AUROC was 0.649021 and did not
improve the disagreement baseline of 0.659727.

This rejects using the existing landmark model as an external uncertainty
probe for the pose estimator. Its spatial outputs were trained for keyboard
corner geometry, not for the pose model's localization error, and their errors
are not sufficiently coupled. The next bounded direction should train a compact
image-conditioned error or heteroscedastic head against held-out pose residuals,
with scene-grouped training and selection populations. Its uncertainty output
must remain research-only until independent calibration and confirmation pass.

## Direct pose-error head

A 52,481-parameter head was trained for 20 fixed epochs on 16,000 new 52M
images. Its inputs were the frozen pose model's 512-element image descriptor and
the frozen ensemble disagreement. Its target was `log1p(maximum target error)`.
No localization model weight changed. One disjoint 8,000-image 53M cohort was
used for the registered selection decision.

The result was a near miss and remains a failure. Grouped scene AUROC improved
from 0.701848 for disagreement to 0.729795 for the learned head, exceeding both
the 0.72 absolute and 0.02 improvement gates. The lowest-half scene failure rate
fell from 6.8% to 5.0%, and every conditional image AUROC passed 0.70: standard
0.841182, appearance 0.875036, partial 0.804697, and full 0.735054. The lowest-
quartile failure rate fell from 5.2% to 4.0%, but its frozen requirement was at
most 75% of baseline, or 3.9%. One additional failure in 250 scenes therefore
failed the complete rule.

The checkpoint is retained as research evidence and has no runtime authority.
This result supports direct supervision of pose error while showing that plain
regression does not rank the safest tail strongly enough. The next bounded
study should keep the frozen descriptor inputs and train one preregistered
tail-aware head on entirely new training-selection cohorts, using a failure-
weighted or ranking objective fixed before either cohort is evaluated. The
failed gate must remain unchanged.

## Tail-aware pose-risk head

The same 52,481-parameter architecture and frozen 513 inputs were trained from
scratch on 16,000 new 54M images. The sole change was the preregistered target:
balanced binary cross entropy for maximum target error above 3 mm. The training
cohort contained 688 positive and 15,312 negative images, fixing positive weight
at 22.255814. All 20 epochs completed without selection-based stopping.

The untouched 55M selection cohort passed every unchanged rule. Grouped scene
AUROC improved from 0.685100 for disagreement to 0.755267. The lowest-risk 25%
failure rate fell from 5.2% to 3.6%, and the lowest-risk 50% rate fell from 5.4%
to 3.6%. Conditional image AUROC was 0.914617 standard, 0.924934 appearance,
0.783335 partial obstruction, and 0.755344 full obstruction. All exceed 0.70.

This selects a failure-ranking feature for further research. It does not yield
millimetre uncertainty, an acceptance radius, or runtime authority. The tracked
checkpoint may enter one separately frozen mapping study on new grouped
mapping-calibration and selection cohorts. That study must preserve the 99%
coverage, conditional coverage, nonzero utility, and zero accepted errors above
3 mm rules before any independent confirmation is allocated.

## Tail-risk to metric mapping

The frozen tail-risk checkpoint was evaluated without additional model training
on 1,000 new 56M mapping-calibration scenes and 1,000 disjoint 57M selection
scenes. Four preregistered thresholds retained the lowest-risk 5%, 10%, 15%, or
20% of calibration images at a 1 mm scale and assigned every other image a 10
mm scale. Each mapping then received its own rank-991 scene conformal quantile.

No mapping passed the fixed selection rule. The 5% mapping retained 440/8,000
selection images, but reached only 97.7% marginal scene coverage, 89.7727%
accepted-image coverage, and 78.8991% accepted-scene coverage. The 10%, 15%,
and 20% mappings passed marginal scene coverage at 99.2%, 99.0%, and 99.0%, and
retained 781, 1,211, and 1,653 images. Their accepted-scene coverage was only
95.6757%, 96.3768%, and 97.2222%. They admitted 5, 8, and 11 errors above 3 mm.
At 20%, overall accepted-image coverage reached 99.0321%, but full-obstruction
accepted-image coverage was 95.9752% and 9 of its 323 accepted images exceeded
3 mm.

This preserves the distinction between ranking and calibrated uncertainty. A
binary tail-risk score can improve AUROC while still interleaving enough rare
localization failures among its low-risk images to defeat scene-wise and
conditional accepted-subset guarantees. The checkpoint and mapping report
remain research evidence only. No mapping, qualification, runtime behavior, or
motion authority is installed.

The next bounded direction should train a compact upper-tail error estimator on
fresh grouped training and selection cohorts, with a preregistered high-quantile
or exceedance objective that predicts a metric upper bound more directly. It
must still undergo separate mapping calibration, selection, and independent
confirmation with the present 99% coverage, per-condition utility, and zero
accepted errors above 3 mm requirements. This failed result does not justify
lowering any gate.

## Direct upper-tail metric head

A 52,481-parameter head was trained from scratch on 16,000 new 58M images using
95th-percentile pinball loss against maximum target error in millimetres. The
input remained the frozen pose descriptor plus ensemble disagreement, and a
softplus output constrained the predicted bound to be nonnegative. The fixed
20 epochs completed without selection-based stopping or hyperparameter search.

On 8,000 untouched 59M images, the learned bound reduced mean pinball loss from
0.201364 for the training-only constant bound to 0.113025 and reduced its median
from 2.866124 mm to 2.089084 mm. Its grouped scene AUROC was 0.720850, with 3.2%
and 4.8% failure rates in the lowest predicted-bound quartile and half. Every
conditional image AUROC passed: 0.913088 standard, 0.952180 appearance shift,
0.878273 partial obstruction, and 0.752728 full obstruction.

The complete selection still failed. Overall empirical bound coverage was
89.2375%, below the frozen 90% minimum. Standard, appearance-shift, and partial
coverage were 93.1%, 93.9%, and 88.95%, while full-obstruction coverage was only
81.0%, below the 85% conditional minimum. A few extreme outputs also reached
90.3775 mm, showing that the unconstrained upper tail needs explicit robustness
even though the median and loss improved.

The checkpoint remains research evidence with no metric calibration, runtime,
qualification, or motion authority. The next study should retain direct metric
supervision but address full-obstruction undercoverage and extreme outputs with
a preregistered robust formulation on fresh grouped populations. Candidate
options include a bounded residual parameterization around a conservative base
scale or a higher quantile with an explicit finite-bound penalty. Any candidate
must be selected before a separate calibration and confirmation chain, and the
failed coverage gates remain unchanged.

## Bounded upper-tail metric head

One new 52,481-parameter head used the same frozen inputs with a 97.5th-
percentile pinball target. Its output was constrained before loss to
`0.25 + 9.75 * sigmoid(raw)`, making every proposed bound finite and no greater
than 10 mm. It trained for the fixed 20 epochs on 16,000 new 60M images and was
evaluated once on 8,000 untouched 61M images.

The finite formulation fixed both coverage failures from the preceding study.
Overall coverage reached 92.525%, while standard, appearance-shift, partial,
and full-obstruction coverage reached 94.8%, 95.5%, 93.45%, and 86.35%. The
maximum predicted bound was 9.349887 mm. Mean pinball loss improved from
0.086246 for the training-only constant bound to 0.076669, and the median bound
fell from 3.268819 mm to 2.256930 mm. Every conditional image AUROC passed,
ranging from 0.726437 under full obstruction to 0.931307 in standard scenes.

The complete selection remains a failure. Grouped scene AUROC was 0.696362,
below the frozen 0.70 minimum, although lowest-quartile and lowest-half failure
rates were 3.2% and 4.8%. The single failed check prevents promotion or metric
calibration. The checkpoint remains reproducible research evidence with no
runtime, qualification, physical-camera, or motion authority.

This result isolates the remaining tradeoff: the bounded high-quantile
objective provides useful finite coverage but loses a small amount of scene
failure ordering. The next bounded study should combine the same finite metric
output and pinball objective with one preregistered binary tail-ranking
auxiliary loss on fresh grouped populations. It must retain all present metric,
coverage, finite-range, and ranking gates before any calibration is allocated.

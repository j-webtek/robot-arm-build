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

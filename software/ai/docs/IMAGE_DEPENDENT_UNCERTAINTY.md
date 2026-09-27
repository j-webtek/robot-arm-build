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

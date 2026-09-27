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

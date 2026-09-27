# Pose representation review

## Decision

Retain the 276,867-parameter KeyboardPoseNet at 128 x 96 for the next controlled study. Do not repeat the unchanged 256 x 192 adaptation or promote any previous failed candidate.

The earlier matched-resolution study (AI-025) used the same starting weights, samples, 12 epochs and optimizer settings. Mean target error was 0.945 mm at 128 x 96 versus 1.442 mm at 256 x 192 (52.6% higher); p95 was 2.065 versus 3.530 mm. Its starting weights were trained at the smaller size and it used one seed, so this is not proof that higher resolution cannot help. That older study also used different conditions and losses from the latest runs; its error values are not a direct ranking against current models.

## What the architecture review establishes

Four strided convolutions produce a 6 x 8 feature map from 128 x 96 inputs, or 12 x 16 from 256 x 192. Both are pooled into 4 x 4 features before the pose head. Spatial pooling and higher-resolution adaptation therefore change how image evidence reaches the head; shape inspection alone cannot identify the cause of clutter sensitivity.

The controlled clutter study recovered 21 of 32 failures by removing both synthetic clutter layers. Paired-clutter consistency training subsequently failed to establish a benefit across three seeds. These results justify testing an explicit visual training target instead of another consistency-coefficient sweep.

## Proposed bounded intervention

Add a training-only binary segmentation head to the shared stride-four feature map (24 x 32 at the retained input size). It predicts the visible keyboard case region. Construct the synthetic target from the case polygon minus the renderer's foreground overlay mask; downsample by area coverage to soft labels. Clutter elsewhere remains background. Blur and the geometric mask are not perceptual ground truth, and real-camera transfer remains unproven.

First implement and verify label generation on training scenes, including overlay removal, boundary coverage and empty-visible-region handling. Confirm that attaching a head leaves the initialized pose outputs identical to the baseline. Inspect fixed-batch auxiliary versus pose gradients before any training run; do not tune a coefficient on development accuracy.

Then freeze a paired comparison: same pose checkpoint, images, sample order, optimizer updates, epoch-selection rule and three seeds. Control has no auxiliary gradient; candidate adds the frozen segmentation objective. Score only the original cluttered development images with unchanged mean, tail and rotation criteria. Retain mask metrics separately: improved segmentation alone is not localization qualification.

The head may be discarded at inference. Any trained pose backbone still needs independent accuracy and uncertainty evidence before qualification. ModelMotionBatch remains the AI boundary; no arm fields, hardware authority or runtime image cleanup are added.

## Evidence

Exact source hashes: `eval/representation_review_v0_plan.json`. Architecture traces and retained metrics: `eval/representation_review_v0_report.json`. This review performed no training or physical operation.


## Follow-up decision: end the auxiliary-loss series

The random-head and learned-head auxiliary comparisons did not meet the full localization improvement rule in any of three seeds. The head-only probe did learn visible masks (88.2–90.8% mean IoU), so mask learnability alone does not resolve the pose errors.

The frozen overlap audit (`eval/warm_segmentation_overlap_v0_report.json`) finds all 19 previously persistent failures still fail in every warmed candidate. There are 21 cases failing all six current control/candidate models. The only recovered threshold case is appearance-shift scene 15000159 in seed260926: maximum target error changes from 3.033146 to 2.980808 mm. The other two candidates still fail that scene. No candidate introduces a new >3mm failure relative to its paired control. This is not a consistent solution to clutter sensitivity.

Do not sweep auxiliary coefficients or promote these checkpoints. The next bounded design should explicitly expose the learned spatial mask to a pose readout, rather than relying on an auxiliary gradient alone. Before training, define a parameter-matched control with constant-mask input, preserve baseline predictions at initialization with a zero-initialized residual, and test shapes, mask sensitivity after a controlled nonzero residual, and exact export behavior. Both arms must receive the same images, pose features, budget and selection rule. Use predicted masks at inference; geometric training labels must never become runtime inputs. The added inference cost and head-pretraining cost must be reported. This is a proposed experiment, not evidence that spatial conditioning works.

Do not consume fresh30M data for architecture selection. Reused development and these synthetic masks provide no physical calibration or localization uncertainty qualification. The AI boundary remains unchanged.


## Residual prototype feasibility

Implemented `vision/mask_conditioned_pose.py`. Both arms freeze the baseline pose network and learned segmentation head. At stride four, the candidate multiplies 32 feature channels by the predicted sigmoid mask; the control multiplies by ones. Both pool to4x4, flatten512 values and use an identical512→32→3 residual MLP. Its final layer starts at zero, so the initial prediction is exactly the baseline. The mask and pose backbone receive no gradients; only16,515 residual parameters are trainable. The control still computes the mask to match execution structure. This design tests mask conditioning of fixed features; it cannot establish the benefits of end-to-end feature adaptation.

The32-image CPU probe across three learned heads verified exact initial identity, nonzero mask sensitivity after manual residual-weight assignment, finite residual gradients, frozen backbone/head gradients and exact initial/nonzero export roundtrips. Image-only forward accepts no oracle mask or board coordinates. Research exports include mode and all model weights; they are not runtime-qualified artifacts.

Both arms have293,415 parameters versus276,867 baseline (+16,548, approximately6%). Serialized probe artifacts are1,179,040 bytes. Predicted-mask batch-one median CPU latency was0.7668–0.7805ms versus0.55255ms baseline (four threads,10 warmups,100 timed calls). These sequential host timings include Python overhead and are descriptive, not deployment guarantees. Inherited mask pretraining cost304 updates per seed remains part of total development cost.

Next: freeze a three-seed paired residual-only training experiment, using the same images, order, initialization, budget and selection in both arms. Keep the original baseline and constant-mask control comparisons, retain all failures and use no fresh holdout for model selection. The present probe ran zero optimizer updates and establishes no localization improvement.


## First paired residual-training result

The eight-epoch residual-only study (AI-267 onward) failed the full baseline-and-control rule in all three seeds. Candidate and control large-error counts were identical31/32/31, versus32 baseline. The candidate passed the baseline-only rule in two seeds; appearance mean averaged0.835753mm versus0.833798mm control and0.833364mm baseline. These results do not establish a benefit from predicted-mask conditioning. The model remains a research artifact; the baseline demo is unchanged.

Both arms used the same2,400 images,19,200 presentations,304 residual updates, AdamW0.001, key loss plus baseline anchor1, and minimum development pose-MSE epoch selection. Only16,515 parameters were trainable; baseline and learned head bytes stayed identical. Prior eight-epoch head training is additional shared cost. This budget was fixed before execution, with no coefficient or learning-rate sweep.

Next diagnose correction magnitude, per-axis variability, and alignment with true pose residuals on the existing training and development sets. Compare actual learned corrections against a training-only mean-offset diagnostic evaluated unchanged on development. This can distinguish scene-dependent learning from a generic shift; it must not become a runtime correction or use development-fitted offsets. Do not increase model size or resume a sweep before this diagnosis. No fresh holdout has been consumed.


## Correction diagnostic result

CPU inference on the existing2,400 training and800 development images finds nearly constant corrections in seed260927 for both modes: development standard deviations below4.5e-7mm for X/Y and1.7e-7degrees yaw. Correlations at that scale are numerical descriptions, not meaningful scene-specific learning evidence. The cause has not been established; inspect hidden activations and final-bias contribution before calling it a dead-ReLU failure.

For the other two predicted-mask seeds, development correction standard deviation is0.0111–0.0314mm X,0.0687–0.0716mm Y,0.0055–0.0073degrees yaw. The needed residual standard deviations are0.9050mm,0.6286mm,0.3528degrees. Y correlation is0.369–0.383; X0.063–0.137; yaw0.027–0.063. Some variation is learned, but its magnitude and alignment are limited, particularly in X and rotation. Training shows the same small variation; this is not evidence of a strong training fit that only fails on development.

A single mean normalized offset fitted on training alone was[-0.0059134068,0.0015876684,-0.0006194752]. Applied unchanged to development, it produces33 large-error cases versus32 baseline. It minimizes normalized pose MSE, not the anchored key-loss objective, so it is only a diagnostic comparator. No offset was installed.

Next freeze an activation/bias diagnostic for all six retained checkpoints: positive hidden-unit fractions, fully inactive units, hidden activation variation, output bias versus feature-dependent output, and initial-versus-trained activation statistics on the same training inputs. This can test whether hidden-unit collapse explains the constant seed before choosing an activation or normalization change. No extra training, architecture sweep, fresh holdout or runtime qualification is warranted by this diagnostic alone.


## Hidden-unit collapse confirmed on sampled training inputs

Initial-to-trained inactive counts (of32 units) were: seed260926 control10→31/candidate12→31; seed260927 control10→32/candidate8→32; seed260928 control16→30/candidate18→31. Inactive here means the preactivation never exceeded zero across all2,400 existing training images. These counts do not establish inactivity on every possible image.

For seed260927 both modes have all hidden activations exactly zero for all2,400 images and the feature-dependent output exactly zero. The correction is consequently the final output bias. This directly explains the constant correction on those images; it does not identify the optimizer step or cause that drove the preactivations negative. Other seeds retain only1–2 active units and limited correction variation.

Next freeze a single activation change: use LeakyReLU with fixed negative slope0.01 in the residual hidden layer, preserving the same weights, parameter count, zero-initialized output, paired mask/control design, losses and training budget. Verify nonzero negative-side gradients and exact export/initial baseline parity. Version the research artifact so old ReLU checkpoints cannot silently load with new semantics. Then run the same three-seed paired experiment, retaining all results and checking actual correction variation alongside localization criteria. No slope sweep or other simultaneous architecture change. Preventing all-zero hidden output is not proof of useful localization learning.


## Fixed LeakyReLU comparison

The fixed0.01 negative slope preserved identical initial weights and baseline outputs, introduced no parameters, and used a separate versioned research export that rejects legacy artifacts. Both negative-side gradient and nonzero-weight export tests passed before training.

Across all six selected models, no training or development image had an all-zero hidden vector, and direct residual outputs varied on every axis. Seed260927 now has nonzero scene variation, unlike the prior bias-only model. This addresses the observed all-zero activation failure on these samples, but does not establish useful accuracy.

Candidate tails31/31/32 versus matched control32/31/32 and baseline32each; full acceptance0/3, baseline-only2/3. Candidate appearance mean0.826935mm versus control0.829886mm and baseline0.833364mm. One candidate has12 full-obstruction tails versus11 baseline. Keep all failures; no model promotion, extra activation sweep or runtime change.

Next use a bounded training-only linear-readout diagnostic on the frozen pooled descriptors to assess whether they contain learnable residual information without nonlinear optimizer collapse. Fix a single regularization and training-only normalization before execution; compare predicted-mask and constant-mask descriptors with baseline/mean-offset diagnostics on both training and reused development. Report conditioning and training fit, and do not select regularization on development. This is an information/optimization diagnostic, not a new qualified controller. No fresh holdout should be consumed yet.


## Fixed ridge diagnostic: useful information in unmasked descriptors

With one preregistered alpha0.01 and training-only feature normalization, the shared constant-mask linear control reduced development tails32→20 (37.5%) and training tails to16. Its normalized pose MSE was0.000451740 training/0.000715115 development, versus baseline0.000853410/0.000859203. Per-condition development tails were3/7/3/7 for standard/appearance/partial/full versus baseline5/7/9/11. Means improved in every condition and yaw p95 stayed within110% of baseline; combined obstruction tails dropped20→10. Thus this control meets the baseline-only rule on reused development.

The three predicted-mask ridge fits had26/27/27 development tails and failed the full baseline/control rule. Their training tails19/18/18 were also above the control's16. No regularization sweep or development normalization was used. The deterministic control was fitted once, not treated as three independent replications.

The solved objective is mean per-image sum of squared normalized residual errors plus0.01 times squared weight norm, with an unpenalized intercept. Feature means/scales and the intercept are fitted only on training. This differs from the nonlinear anchored key-loss objective; the result does not isolate optimizer behavior as the sole cause of previous failures. Regularized matrix condition numbers were15,505–15,842 and normal-equation maximum residuals below6e-17 in float64.

Decision: discontinue mask conditioning for this candidate and select the unmasked linear diagnostic for an export/parity study. This choice is made after inspecting reused development and must be disclosed as model selection. Freeze the exact existing coefficients; do not refit, retune alpha or claim qualification. First verify an image-only standalone predictor, export/load parity, required normalization and total parameter/memory/latency cost on existing data. Then freeze a genuinely untouched synthetic evaluation starting in the reserved30M range. No fresh evaluation data has been consumed in this increment. Physical calibration and uncertainty qualification remain separate blockers even if new synthetic evaluation succeeds.


## Export verified; untouched evaluation failed

The image-only export preserves the original unmasked coefficients, omits the mask head, and bundles276,867 backbone parameters,1,539 linear coefficients and1,024 normalization values. The1,132,606-byte local artifact SHA256 is0cd2442e6a6190ad7228749bd47f20c108ec6062c5d319b1e36be054efd3af0e. On800 existing development images, maximum normalized prediction difference from the original calculation was2.22e-16; export/load was exact. Median batch-one CPU inference was0.70615ms versus0.54585ms baseline. No deployment-device or quantization performance claim follows.

The first reference-byte comparison failed after changing the NumPy multiplication batch shape. Its source/plan and failure are preserved. A separately frozen v1 calculation restored the original full800-row reference hash without changing coefficients or the1e-10 parity tolerance.

The frozen4000-image evaluation on previously unused seeds30000000..30000999 failed the acceptance rule. Baseline/candidate tails were18/25 standard,28/27 appearance,30/30 partial,43/39 full:119 versus121 total. Candidate recovered54 old failures and introduced56. Means worsened in standard, appearance and partial conditions; standard yaw also exceeded110% of baseline. Only full-obstruction mean/tails improved together. This overturns the case for promoting the candidate from its favorable reused-development result.

Retain the original baseline and demo. This is a failed candidate with a working export, not a qualified localization model. No hardware activity, new fitting, uncertainty qualification or integration completion occurred.

Data accounting:30000000..30000999 is now consumed evaluation data and must not be described as untouched again. The remaining30001000+ range has not been consumed by this evaluation. Before further model fitting, audit scene-group split integrity and training/development/evaluation coverage, and define model selection confined to grouped training splits. Keep all four condition variants of each seed together. The consumed evaluation may support diagnosis but must not become a repeatedly tuned validation gate. Any later confirmation requires a separately frozen unused range.


## Scene grouping audit after failed fresh evaluation

The three recent cohorts have no scene-ID overlap or exact cross-cohort image duplicates. Training covers123/125 pose bins;19/1000 consumed evaluation scenes occupy empty training bins. Nearest-training-pose distance p95 is similar for development and evaluation (0.227889 versus0.228354), so the audit does not identify a causal explanation. See GROUPED_MODEL_SELECTION.md for the five-fold training-only protocol. No fitting occurred. The frozen audit and initial endpoint-test failure remain preserved; a separate corrected helper reproduces all report bins and passes the exact endpoint test. Seven tests passed. The original baseline remains selected; no localization qualification or arm authority is added.

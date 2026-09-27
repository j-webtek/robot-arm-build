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

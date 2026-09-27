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

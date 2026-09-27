# Frozen candidate uncertainty feasibility

Status: specified, not executed. This is a synthetic feasibility protocol, not localization qualification. See `../eval/grouped_uncertainty_v1_protocol.json`.

## Why the aggregate improvement is insufficient

The consumed confirmation set contains112 persistent failures and9 introduced failures across57 distinct scenes. The worst candidate error is11.4173mm; the worst introduced error is9.48284mm. For59 failing images, translation-only and rotation-only errors are individually at most3mm while their combined target error exceeds3mm. These components are not additive or causal partitions. A center-only bound cannot stand in for target displacement.

No deployable quality scores were recorded. Condition labels, masks and error decompositions are simulation truth. They cannot be inputs to an abstention decision at inference. The candidate weights remain frozen; no confidence head or new runtime gate was installed.

## First conservative experiment

Before rendering, freeze an executable plan allocating two disjoint, previously unused ranges:1000 calibration scenes and1000 confirmation scenes. Recheck all intervening plans and shared claims before allocation. Neither15M development nor consumed30000000..30001999 may fit a bound or choose a threshold. The original29M scenes remain training-selection data.

For each calibration scene, compute one score: the maximum displacement over all46 keyboard targets and all four condition variants. Use the sorted score at one-based rank ceil((1000+1)*0.99)=991 as the global radius. This groups correlated variants and bounds target displacement jointly within the synthetic scene construction. A rank beyond the sample count means an infinite radius and abstention. Do not alter the alpha, score, model or gate after results.

The runtime-visible input to this research gate is only the frozen global radius. A radius at most3mm passes the research-only tolerance; a larger radius abstains on every image. That may produce zero utility, which must be preserved as a failed feasibility result. This3mm diagnostic threshold is not a commissioned physical contact margin.

On the separate confirmation cohort, report scene coverage, image coverage, bound violations, accepted fraction, maximum errors and binomial uncertainty using scenes as the unit. The preregistered descriptive pass requires at least99% observed scene coverage and nonzero accepted fraction. Passing does not establish99% physical coverage or a high-confidence statistical lower bound. A distribution-free interpretation requires exchangeable calibration and test scene scores from the same fixed generator; fixed synthetic seeds and unknown camera shift do not establish real-world applicability.

## Following dependencies

If the global bound has zero utility, preserve that outcome. A locally scaled uncertainty model would require image-derived signals developed on training data, a separate calibration allocation and a new independent confirmation cohort. Do not tune a quality score on these consumed confirmation failures. This audit may identify questions, not select thresholds.

Runtime integration additionally needs measured board-to-arm calibration, qualified target placement/orientation, uncertainty in that placement, fresh image identity, actual target-safe-region margins and capability evidence. Do not substitute nominal board rectangles or simulator pose for measured runtime geometry. ModelMotionBatchV2 remains the AI boundary. No arm-lane status or shared integration gate is advanced here.

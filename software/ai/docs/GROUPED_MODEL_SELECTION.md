# Grouped model selection

Status: grouped selection executed; final refit and independent confirmation pending. Machine-readable rules: `../eval/grouped_linear_selection_v1_protocol.json`.

## Audit findings

The three recent cohorts have disjoint scene IDs and no exact cross-cohort image duplicates. Training covers123/125 fixed pose bins; development101/125 and consumed evaluation125/125. Two development scenes and19 evaluation scenes occupy empty training bins. Their normalized nearest-training-pose p95 distances are similar (0.227889 and0.228354). Training uses rectangular obstructions; both other cohorts use elliptical obstructions. These summaries do not establish why the candidate failed.

The audit covers these three cohorts only. It does not establish independence from all historical pretraining or rule out near duplicates. The fixed baseline was already selected on15M development.

## Next experiment

Freeze executable source and its plan before fitting. Use only600 existing29M training scenes for selection. The audited five folds each contain120 validation scenes,30 per obstructed corner. Each fold fits480 scenes. Every lighting, obstruction and rendering-style variant of a scene belongs to the same fold.

Fit on rectangle variants and validate on ellipse variants within this training pool. Ellipse variants are derived training-selection data, not untouched confirmation data. Use the frozen original baseline representation; do not use mask heads learned from all600 scenes. Fit feature normalization, residual intercept and ridge coefficients using fold-training rows only. Evaluate the four preregistered alpha values0.001,0.01,0.1,1.0. Concatenate out-of-fold predictions before applying the fixed acceptance rule in the protocol; do not choose a different model per fold.

Reject all candidates if none qualify. Otherwise choose by total tail count, then overall mean target error, then larger alpha. Refit the selected configuration on all600 rectangle scenes, verify standalone export parity, and freeze a separate unused confirmation range before generating it. Do not use15M development or consumed30000000..30000999 for selection or retuning. Remaining30001000+ is not allocated by this protocol and must be checked for intervening use before a future claim.

No models were fitted by this audit. A synthetic selection result cannot establish physical calibration, uncertainty qualification or execution authority. The AI boundary remains ModelMotionBatchV2.


## Executed selection result

Frozen source e38664763e51f99c81781c42779a3d631ccfa805 executed20 fits, with fold-only normalization and disjoint scene groups. Out-of-fold tails were107,76,69,61 for alphas0.001,0.01,0.1,1.0 against74 baseline. Only alpha1.0 met every preregistered condition. Combined partial/full tails dropped46 to36; all four mean errors improved. See eval/grouped_linear_v1_report.json for coefficients, predictions and checks, including the rejected settings. Three verification tests passed.

This is selection evidence, not fresh confirmation. The original baseline remains in use. Next: freeze and execute a single final fit at alpha1.0, export with parity verification, then evaluate on separately preregistered unused scenes. No final fitting or hardware action occurred in this increment.

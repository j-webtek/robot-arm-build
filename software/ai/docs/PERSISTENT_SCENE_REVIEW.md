# Persistent synthetic scene review

AI lane; development diagnosis only. Publishing branch: `feature/translation-pair-evidence` in `j-webtek/tactevra`.

The four figures in `eval/persistent_visual_v0_page_*.png` show every persistent failure beside a same-condition successful case matched by normalized true pose. Green outlines are synthetic case labels. Controls can repeat; they are not causal counterfactuals.

## Findings

- None of the 19 failures or 19 matched control slots has a cropped case corner. Independent vector projection matches the corner labels exactly; this does not validate raster boundaries or physical geometry.
- Mean foreground-mask overlap is 2.65% for failures versus 0.81% for controls. Only one failure has fewer than three geometrically visible corners.
- Three failures and two controls exceed 90% of one simulated pose range. Pose extremes alone do not explain the set.
- Visual inspection of all four figures shows arm-like dark lines near cases 15000068 and 15000144, including cases with almost no foreground overlap. Ruler-like clutter crosses the upper case region in 15000083. Appearance cases 15000027, 15000056 and 15000181 include nearby or overlapping dark lines and blur/contrast changes.
- These are hypotheses from selected development cases, not proof of causal clutter sensitivity. Successful images also contain clutter.

## Next experiment

Freeze paired renderer ablations that remove only arm-like lines or ruler clutter while preserving RNG draws, pose, remaining layers and labels. Score all development cases and retain original-image results. Do not train on corrected development images, remove failed cases from acceptance, or use truth-derived offsets at runtime.

## Reproduction

Run `python software/ai/vision/audit_persistent_visual.py` in a checkout without its output report (outputs are protected against overwrite). Sources are pinned in the plan and figures are hashed in the report. Plotting environment: NumPy 1.26.3, matplotlib 3.9.4, contourpy 1.3.2. A missing-matplotlib attempt is preserved as AI-227. Initial unpinned installation upgraded NumPy; NumPy was restored before the successful audit. Pip also reported pre-existing missing pyarrow for datasets; this renderer does not use datasets.

Zero hardware writes, zero physical movements, no qualification or contract changes.

## Controlled clutter intervention

The frozen `clutter_ablation_v0` study scores all 800 original development cases with the established pose checkpoint. RNG draws are preserved; the selected line draw calls are skipped in a separate renderer. Original RGB, masks, labels and pose metrics reproduce the prior baseline exactly. Pose labels remain identical across all interventions.

| Rendered condition | Failures over 3 mm | Original persistent cases still failing |
|---|---:|---:|
| Original | 32 | 19 |
| Without arm-like line | 17 | 10 |
| Without ruler line | 25 | 15 |
| Without either | 11 | 6 |

No intervention introduced a new >3 mm failure. These results demonstrate sensitivity to these synthetic layers in this checkpoint; they do not establish physical-camera performance. Postprocessing can spread a layer's effect beyond its original pixels. Original-image failures remain the accuracy baseline.

Next: a frozen paired-clutter training experiment using training scenes only, with identical pose supervision across clutter variants and a fixed consistency objective. Score untouched cluttered development images. No runtime image cleanup, development-case exclusion, or coordinate correction is authorized by this evidence.

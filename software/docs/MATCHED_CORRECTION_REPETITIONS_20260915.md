# Matched correction repetitions: frozen +2-degree experiment

## Protocol, fixed before additional outcomes

Keep the previous model bytes and directional bias unchanged. Use the same
USB unit, unchanged payload, spd 20 / acc 1, five-second post capture and all
existing ownership, fresh-baseline, endpoint and cleanup checks.

Collect two additional corrected trials and two uncorrected controls, each
approaching +2 degrees from the previously tested +4-command position
(approximately +3.7793 degrees reported). Sequence:

1. Separate ordinary +4 positioning command; inspect verified result.
2. One corrected +2 trial; inspect and retain originals.
3. Separate ordinary +4 positioning command; inspect verified result.
4. One uncorrected +2 control; inspect and retain originals.
5. Repeat steps 1–4 once, only after individual results are reviewed.

Every command is a distinct reviewed single-use campaign with a fresh baseline.
There is no automatic return, retry or iterative coefficient adjustment. A
failed positioning or corrected trial ends progression pending diagnosis.
An uncorrected target miss is retained as a miss, not relabelled success; only
a separately reviewed new experiment may follow a clean, stable bounded miss.
No new command follows transport uncertainty, drift or incomplete feedback.

Report all outcomes, nominal errors, same-approach starting positions, capture
quality and export references. Corrected acceptance retains +/-0.5 degrees;
the improvement screen additionally requires <=0.25 degrees and improvement
over the prior uncorrected error. Do not fit on these held-out repetitions.

## Single-command support

V5 is an ordinary, non-compensated, one-command format restricted to the
already tested +2 and +4 targets. It retains the v3 capture capacity per leg,
but allows just one write and 96 KiB total capture. Targets equal transmitted
commands. Both actual delta and direction are rechecked on the fresh baseline.
Older formats retain their interpretation. The existing bench script exposes
`--single-target two` and `--single-target four`, mutually exclusive with
two-leg profiles and `--model-correction`.

## Results

Completed all eight planned commands, each with a fresh zero-command baseline,
separate one-use native campaign and retained original export. The earlier
successful corrected trial remains separately documented in
`MODEL_CORRECTION_FIRST_LIVE_RESULT_20260914.md`.

| New trial | Reported start | Command | Intended endpoint | Reported final | Signed nominal error | Nominal result |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Corrected 1 | 3.779297 | 1.033203 | 2.000000 | 2.021484 | +0.021484 | Pass |
| Control 1 | 3.779297 | 2.000000 | 2.000000 | 2.900391 | +0.900391 | Miss |
| Corrected 2 | 3.779297 | 1.033203 | 2.000000 | 2.021484 | +0.021484 | Pass |
| Control 2 | 3.779297 | 2.000000 | 2.000000 | 2.900391 | +0.900391 | Miss |

Angles are degrees. New corrected mean absolute error: **0.021484368 deg**.
Matched control MAE: **0.900390625 deg**. Descriptive error reduction: **97.61%**.
Both corrected trials passed the <=0.25-degree improvement screen. Including
the separate first trial, all three corrected outcomes report 2.021484368 deg.
No coefficient was refitted. Repeated quantized reports do not prove zero
physical variability, fresh servo readings, or a statistical confidence bound.

All four +4 positioning commands passed and ended at the same reported
3.779296882 degrees. Every post window was five seconds, with 281–282 decoded
pose samples. All eight captures reconstructed, with no detected other-joint
change or wrist excursion, no uncertain write, and clean bounded cleanup.
The two control misses remained HELD/TARGET_MISSED and are not counted as
successful endpoints. The first was reviewed as a clean stable bounded miss
before a new positioning campaign; neither failed campaign was resumed.

Total: eight confirmed motion commands, 506 command bytes; no hidden return.
All controller/protocol/workcell/tool reference hashes match across the eight
exports, and the frozen model hash remains unchanged. Baseline acquisition
may reset the controller; it sent zero motion-command bytes in each session.

### Original-export ledger

Each directory is `software/runs/wizard-exports/<campaign-id>/`. The structured
summary `software/runs/MATCHED_CORRECTION_REPETITIONS_20260915.json` retains exact
report hashes, target separation, capture metrics and cleanup evidence for
independent reconstruction; it is not a motion permission or fitted model.

| Order | Purpose | Campaign ID |
| --- | --- | --- |
| 1 | Position +4 | campaign-a444289b6977473aaf8848a212405fa5 |
| 2 | Corrected 1 | campaign-2b3a8de1371b480dafc0c58ebeb96709 |
| 3 | Position +4 | campaign-f9e761d7979e4404ac7d61bf330b6584 |
| 4 | Control 1 | campaign-23fd349658974e55836efd8de7e94e80 |
| 5 | Position +4 | campaign-583338ea958f4673a74cbde0cfcc510b |
| 6 | Corrected 2 | campaign-7aad656ea1ab4a44bb9bb7468b07376c |
| 7 | Position +4 | campaign-e203daaf563a4d9f9d1455144b6c899f |
| 8 | Control 2 | campaign-4d43d9c570d749b98421fa0e0f701597 |

Final reported wrist: **2.900390625 deg**, held there after the final control;
the last constant tail spanned 4.344 seconds. No further motion was sent.

### Verification and next boundary

Regression: **513 passed, 18,017 deselected**, recorded in
`software/runs/matched-correction-regression-20260915.xml`. This includes
single-command staging, supervisor format acceptance, native-shaped capture,
cancel/uncertain-write behavior and original-export reconstruction.

This supports repeatability of the local *reported* endpoint correction from
above at +2 degrees, spd 20 / acc 1, unchanged payload. It does not establish
tool-tip accuracy, the physical cause of the bias, different speeds/targets,
or the opposite approach. Next: independently test the opposite approach with
its already frozen bias before considering any reusable compensation policy;
use calibrated external vision for actual board-space accuracy. Automatic
compensation remains disabled outside explicit reviewed experiments.

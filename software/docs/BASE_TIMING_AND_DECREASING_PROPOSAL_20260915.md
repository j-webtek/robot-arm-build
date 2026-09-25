# Retained timing analysis and decreasing-base proposal

## Status

Offline work completed: four original experiment exports were reverified and
their intermediate reports summarized. A separate decreasing-direction inverse
proposal was rebuilt from the original eight training and three held-out exports.
No device was opened and no motion command was sent for this work.

The decreasing proposal is not executable through the existing positive-direction
v10/v11 profiles. Its own native correction/control profiles remain to be built
and tested. The base live-command count remains seventeen.

## What the saved timing shows

All intervals below are host acquisition bounds after confirmed command
completion, not independently measured motor-response timestamps.

| Reported event | Corrected trial 1 | Corrected trial 2 |
| --- | --- | --- |
| First changed angle report | 515-531 ms | 219 ms |
| First report within 0.25 degree of desired endpoint | 656-672 ms | 297-328 ms |
| Entry to final constant reported angle | 781-797 ms | 391-406 ms |
| Observed span of final constant run | 4.125 seconds | 4.500 seconds |
| Reported angle transitions | 7 | 7 |

Both corrected trials reported the same successive angle values, in the same
order, from 0.439453128 through 1.054687474 degrees. The controls showed zero
reported angle transitions and never entered the quarter-degree target band.

The first corrected run's observed interval from its first changed report to
its final constant report is bounded by 250-282 ms; the second is 172-187 ms.
Thus the recorded timing difference includes both a later first changed report
and a longer observed progression. It is not merely a different final dwell
timestamp. No reported reversal or differing final endpoint was present.

These records do not establish why timing differed. Host buffering, device sample
freshness and physical motion onset were not independently measured. Do not infer
an exact mechanical cause or retune acceleration from two records. Keep the full
five-second observation and feedback-based endpoint verification; do not replace
them with a fixed sleep based on the faster run.

Implementation: `application/base_reported_timing.py`, called after original
export reconstruction by `read_base_experiment_export`. It preserves acquisition
bounds and each constant-value run, including sample counts. Null response/band
entry values are retained for controls instead of inventing a response time.

Artifact: `runs/BASE_REPORTED_TIMING_20260915.json`, with campaign IDs and pinned
report hashes for all four captures. Historical exports were not modified.

## Decreasing-direction experiment candidate

Decreasing means approaching a lower reported coordinate from above. The desired
endpoint is positive; the proposed transmitted motor coordinate is negative.
All coordinates below are absolute base-joint coordinates, not relative turns.

| Quantity | Frozen proposal |
| --- | --- |
| Planned historical starting coordinate | +1.054687474 degrees |
| Desired reported endpoint | +0.4 degree |
| Proposed transmitted target | -0.684826381297 degrees |
| Algebraic predicted endpoint | +0.4 degree |
| Matched uncorrected control target | +0.4 degree |
| Model branch | DECREASING only |
| Model command anchors | -0.945312526 to -0.472656234 degrees |
| Model observed output range | +0.351562491 to +0.439453128 degrees |
| Model observed starting range | +0.527343766 to +1.054687474 degrees |
| Speed / acceleration parameters | 20 / 1 |

The decreasing model uses slope `0.18595042254139021` and intercept
`0.009203884814049577` radians. Its inverse is
`command = (radians(0.4) - intercept) / slope`, giving
`-0.011952475158143525` radians. It does not reuse the increasing branch's gain
or offset. This is an algebraic prediction, not a measured corrected endpoint.

Both nominal and transmitted movements must independently exceed 0.5 degree
and remain at most 2.5 degrees from the actual fresh starting coordinate, with
the decreasing approach preserved. Combined with the learned start range, this
means the usable starting coordinate for this experiment is **above +0.9 degree
and at most +1.054687474 degrees**. Merely falling somewhere in the model's
broader observed starting range is insufficient.

The last observed arm pose from the preceding live run was:
`[0.018407769, 0, 1.593806039, 0.050621366, -0.001533981, 3.149262558]` radians.
That historical pose is numerically eligible, but does not replace a fresh
baseline or current context check.

The decreasing model has only one original prospective interior held-out target;
its error was about 0.04395 degree. The model's observed output range is narrow
relative to the 0.25-degree experiment screen. Treat this as a bounded exploratory
candidate, not a precise or generally validated inverse. Additional observations
must not be silently folded into training during the comparison.

Artifact: `runs/DECREASING_BASE_CORRECTION_PROPOSAL_20260915.json`.
Entry point: `propose_decreasing_base_correction(...)` in
`application/base_correction_proposal.py`. Evidence verification is shared with
the increasing proposer; public entry points fix their own direction and desired
endpoint. The decreasing proposal uses `rocell.offline_base_correction_proposal.v2`
and explicitly reports `NOT_IMPLEMENTED_DECREASING_PROFILE`.

## Checks completed

- Rebuilt the exact frozen model from eight original training exports.
- Rechecked three held-out original prediction/capture pairs.
- Reverified and summarized all four original correction/control captures.
- Tested the separate decreasing branch and its synthetic nominal-endpoint score.
- Tested rejection of stale/wrong model hashes, altered predictions, out-of-domain
  starts, starts with insufficient nominal movement and changed other-joint pose.
- Tested that the positive native profile rejects a decreasing proposal.
- Tested timing bounds, unchanged reports, constant-value runs and malformed data.

Result: 51 tests passed. Report:
`runs/base-timing-decreasing-proposal-regression-20260915.xml`.
Synthetic success is not hardware evidence. Existing increasing proposer behavior
remains covered by the same regression run.

## Next implementation and live sequence

1. Add distinct decreasing native correction/control profiles. Bind the frozen
   branch, nominal +0.4-degree endpoint, inverse command, model/evidence hashes,
   pose/context and both actual-start movement limits. Preserve all prior schema
   meanings; do not widen the existing positive profiles.
2. Wire trusted wizard staging, reviewed preview, child admission, synchronized
   capture, reconstruction and export. Show desired versus transmitted target
   and direction explicitly. Keep one command per campaign and no automatic retry.
3. Simulate both complete native paths, including nominal miss, wrong branch,
   insufficient fresh nominal movement, changed context, other-joint drift,
   incomplete capture, cancellation, uncertain write and replay rejection.
4. Acquire fresh feedback and execute one corrected trial only if its actual
   starting pose qualifies. Independently review its complete original export.
5. Separately restore and verify a matched starting pose before the uncorrected
   control. The control is empirical: do not extrapolate the negative-command
   model onto its positive +0.4-degree command.
6. Compare desired-endpoint errors and the full reported transition timing.
   Retain misses and faults. Refit or broaden only through an explicitly separate
   experiment; no continuous or multi-joint compensation is released by this work.

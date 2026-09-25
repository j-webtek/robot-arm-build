# Framing-enabled pair repetition: variability found

## Completed scope

Two new separately admitted commands completed: increasing then decreasing,
each with fresh feedback and a 35-second observation. No retry or recovery
movement followed. Both exports independently reconstruct from original bytes.

| New run | Campaign | Report SHA256 |
| --- | --- | --- |
| Increasing | campaign-ace739d6a5d3488e950f0c01ba28e354 | 99656b9153743d82ad154809d12f2e42962fa701b167d4ce626a488847f9d186 |
| Decreasing | campaign-503fa3f0796a441d9866bfa614ea9a59 | 596f7a796a9685f09a65750e19ff3564ca6ad235bb4cdc5621ba36bc4d7a812a |

Fresh baseline operations were `operation-2cf1f779399944ef910c3ff330f6bb42`
and `operation-1db71f863d9246bc9faf6c97b8965c0f`, respectively.

## Comparison with the preceding v21 pair

| Direction | First / repeat final roll (rad) | First / repeat target error (deg) | Spread (deg) |
| --- | --- | --- | ---: |
| Increasing | 0.021475731 / 0.021475731 | -0.033203 / -0.033203 | 0 |
| Decreasing | 0.004601942 / 0.007669904 | +0.296875 / +0.472656 | 0.175781 |

Pairwise schema, staged six-joint starts, measured roll starts, commands,
configuration/source, controller/protocol, payload/workcell and risk references
match. Per-run baseline and runtime registration references differ and remain
explicit in the report. This is not a byte-identical process registration claim.

Each new run retained 1,948 complete post-command poses. Every 5/10/20/35-second
horizon had the same endpoint within its run; no after-five-second transitions
or other-axis drift. Maximum host gaps: 78 ms increasing, 63 ms decreasing.
Each command was fully written once (64 and 66 bytes), without uncertainty;
cleanup closed handles within budget with zero pending I/O.

Real split frames were handled in both runs: increasing 140 baseline bytes
plus 65 post bytes, decreasing 129 plus 74. The crossing frames were excluded
from post-motion evidence, with source bytes and framing proofs retained.

## Interpretation and stopped progression

The increasing endpoint repeated. The decreasing endpoint did not, despite
being stable within each run. The latest target error, +0.472656 degree, is
inside but close to the existing 0.5-degree arrival band. Thus a successful
delivery/persistence verdict is not a precision or repeatability qualification.

The latest final roll is 0.007669904 rad (0.439453 degree), not the next fixed
increasing start of 0.004601942 rad. The planned finite pair is finished and
no next command was sent. Do not relax the anchor, issue a corrective return,
or discard this result to preserve a repeatability claim.

No compensation was fitted or applied. The historical v20 late-change hold and
earlier v19 decreasing variation remain relevant. Two samples per direction
are a local screen, not a population estimate or proof of physical tool-tip
accuracy. These data do not identify a specific mechanical/firmware cause.

## Evidence and next best work

Reproduce with `software/scripts/review_roll_framed_repeats_20260915.py`.
It verifies all four pinned v21 exports, compares context and reports the
unmatched next anchor without hardware access. Saved output:
`software/runs/WRIST_ROLL_FRAMED_REPEATS_20260915.json`.

Before more motion, consolidate the retained wrist-roll history into an offline
model-evaluation dataset, retaining failed and late-changing trials separately
from clean repeat samples. Compare direction/start/target-conditioned errors
and repeat spreads, not a single universal offset. Separate arrival, persistence,
repeatability and next-start eligibility in the assessment; keep historical
verdicts immutable. Evaluate candidate corrections with explicit uncertainty and
held-out data before staging any corrected command. Avoid extrapolation across
joints or interpreting firmware Cartesian values as external measurements.

Roll count eighteen; base remains 44. No post-run reconnect. Last reported
[b,s,e,t,r,g]: `[0.007669904,0,1.593806039,0.047553404,0.007669904,3.149262558]`.

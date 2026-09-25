# Reversed-order speed comparison: completed

Executed the four-command scope declared in
`BASE_SPEED_MATCHED_REFERENCE_PLAN_20260915.md`: speed 20 increasing/decreasing,
then speed 10 increasing/decreasing. Each movement used an independent fresh
read-only baseline and one-use campaign, followed by original-export review.
No extra positioning, retry, recovery, or persistent configuration change.

## Results

| Setting / direction | Reported final deg | Absolute error deg | Final constant-run entry after write ms | Selected sample age ms |
| --- | ---: | ---: | --- | ---: |
| 20 / increasing | 1.054687474 | 0.054687474 | 781-796 | 141 |
| 20 / decreasing | 0.439453128 | 0.039453128 | 828-860 | 125 |
| 10 / increasing | 1.054687474 | 0.054687474 | 812-828 | 141 |
| 10 / decreasing | 0.439453128 | 0.039453128 | 828-843 | 141 |

All four endpoints passed. All other reported joints remained unchanged. Each
campaign submitted exactly once (63 bytes increasing, 65 decreasing), without
uncertainty. Cleanup closed all handles, with no pending I/O and within budget.
Original integrity, reconstruction and endpoint completion were independently
verified before further movement. All four preliminary baselines wrote zero
command bytes and closed cleanly.

The comparison reader rebuilt both new pairs and both previous pairs from their
original portable exports. Eight unique campaign IDs and eight unique report
hashes were required; no trial was reused as another observation. Same-direction
starts, transmitted targets and controller/protocol/payload context matched.

Both orders yielded zero endpoint-error reduction between settings. Host timing
differences changed sign or overlapped: there is no consistent timing winner.
This does not establish statistical equivalence, actual physical speed, global
repeatability, or tip accuracy. Device sample freshness is not independently
verified. No compensation model was retrained or generalized.

## Evidence

| Order | Campaign | Report SHA256 |
| --- | --- | --- |
| 1 | campaign-46366ed727f549c4b51d1340241bd4b5 | bc5f45952afcd902fb252a8a694fcc7b055cf7b44b5548fe9e586e12106374ea |
| 2 | campaign-a8611f5b4b9348e8a5b20d8505f259d8 | e30329985d67473829019b2055ce2b4e0eb5d6d3bc4aa15b48004ca2e4a5dedb |
| 3 | campaign-dbcd3a1687f54f55af8269e66bf507b8 | e5977cbcaa7d4d72feef78c430e3f7c87464201589b32af557d464c84b566c58 |
| 4 | campaign-97d82ab655584fe684c0d88b29dc2f83 | f96cac28ab27696debf6c024064c9b3c0ae98fe72dde7fdbef799571246e3cc4 |

Machine-readable observations, native accounting, baseline IDs, and all four
reconstructed pairs: `runs/BASE_SPEED_REVERSED_REPEAT_20260915.json`.
Originals remain under `runs/wizard-exports/<campaign-id>/`.

Final joints [b,s,e,t,r,g] radians:
`[0.007669904,0,1.593806039,0.047553404,-0.001533981,3.149262558]`.
Historical base command count: 44.

## Decision and next movement work

Close this local 10-versus-20 comparison; retain speed 20 as the existing default
because no benefit from changing it was demonstrated. Speed 10 remains an
explicit experimental profile, not an automatically selected optimization.

Next prepare wrist-roll characterization: review the existing logical joint 5 /
feedback r mapping, add a separately versioned small single-joint probe and
simulation/export coverage, then predeclare its first finite physical trial.
Start with raw commands and collect distinct direction/pose context; do not copy
base or wrist-pitch compensation coefficients. Validate against actual reports,
keep the five other-joint drift checks, and require fresh baseline matching.
No wrist-roll motion is authorized by this completed base campaign or included
in its command count. Larger sweeps and simultaneous multi-joint movement remain
outside this next small characterization step.

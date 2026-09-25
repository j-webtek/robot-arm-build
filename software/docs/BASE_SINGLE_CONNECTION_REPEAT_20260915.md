# Single-connection repeat before speed changes

Predeclared: one v14 campaign, at most four writes; no retry, positioning or return.
Keep the fixed increasing/decreasing targets, speed 20/acceleration 1, five-second
observations and existing 250 ms selected-sample-age gate. Read fresh feedback
first and require the model's existing pose context and per-leg handoff gates.

Reconstruct the exported originals, check four verified endpoints and three
six-joint handoffs, and compare dispatch sample ages with the preceding successful
run (140,156,172,172 ms). Record any pose/context difference; do not hide variation.
No speed change or continuous overlapping trajectory is authorized by this test.

Status: completed exactly four physical commands in one connection. No retry,
extra positioning, speed change or automatic return.

## Results

Fresh baseline `operation-2d2c3a3d1f634313a05dba3135c9fae9` matched the preceding
successful run's six-joint pose. Campaign:
`campaign-dc65f9fe58de4e48823ba18884558564`.
Report SHA256:
`8ad8d234f8d311ac10cc5e1db71834a3a5f10272ffc958aa28f7f6141eb252ef`.

All four endpoint decisions passed. Full native reconstruction and original
integrity independently verified. All three consecutive six-joint handoffs
matched exactly. Cleanup closed all handles with no pending I/O, and no other
joint drift or excursion was flagged.

| Leg | Desired degrees | Final reported degrees | Absolute error degrees | Selected-sample age at write ms |
| --- | ---: | ---: | ---: | ---: |
| 1 | 1.0 | 1.054687474 | 0.054687474 | 156 |
| 2 | 0.4 | 0.439453128 | 0.039453128 | 156 |
| 3 | 1.0 | 1.054687474 | 0.054687474 | 172 |
| 4 | 0.4 | 0.439453128 | 0.039453128 | 172 |

The previous successful run's ages were 140,156,172,172 ms. Both runs stayed at
or below 172 ms, leaving at least 78 ms under the unchanged 250 ms gate. This
does not guarantee a worst-case deadline under arbitrary host load.

The two runs have identical bound directional configurations and identical
reported six-joint starts/finals for every corresponding leg. Eight of eight
movements completed, but two runs do not establish global reliability or physical
Cartesian accuracy. Reported final constant-value entry ranged from 812 to
844 ms in this repeat; host capture timing is not independently verified physical
movement latency. Five-second observation windows were retained.

The comparison was rebuilt from both sets of original exports, not merely from
their summary values. Machine-readable result:
[BASE_SINGLE_CONNECTION_REPEAT_COMPARISON_20260915.json](../runs/BASE_SINGLE_CONNECTION_REPEAT_COMPARISON_20260915.json).

Last reported vector remains
`[0.007669904,0,1.593806039,0.047553404,-0.001533981,3.149262558]` radians.
Total historical base commands: 36. No further commands were sent.

Next implementation: [controlled speed-comparison plan](BASE_SPEED_COMPARISON_PLAN_20260915.md).

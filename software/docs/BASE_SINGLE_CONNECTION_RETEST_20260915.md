# Optimized single-connection retest

One fresh campaign only, maximum four commands, no retry or return. Use the same
v14 targets, speed 20/acceleration 1, existing 250 ms recency limit and per-leg
endpoint/handoff gates. The implementation removes repeated immutable-intent
decoding; it does not skip sample checks or context authentication.

Before dispatch: targeted recency and integration tests, then fresh identity and
six-joint baseline. Use the observed stable lower base start; preserve and record
the actual other-joint pose within the model's existing context bounds.

Reservation age failures now identify BEFORE_DISPATCH_CLAIM or AFTER_DISPATCH_CLAIM
and retain selected-sample age and the fixed limit. No arbitrary exception text
is copied to exports. One-use claims remain burned on failure.

After the run: verify original export integrity, full campaign reconstruction,
four per-leg endpoint decisions, consecutive six-joint handoffs, lifecycle and
cleanup. Compare sample age at each write with the previous partial attempt.
Do not overwrite the failed attempt or count a diagnostic export as completion.

Status: completed one physical four-leg campaign. No extra writes, retry or return.

## Verification

- 103 admission/collector/core tests passed, including both sides of the durable
  dispatch claim's age check and irreversible hold behavior.
- 16 full sequence staging/native-shaped/export integration cases passed.
  Report: `../runs/base-sequence-optimized-integration-20260915.xml`.
- Fresh baseline `operation-c21225d9ab784f6a9fe9a202be538d86` matched the previous
  run's lower pose exactly, including wrist pitch 0.047553404 rad.

## Physical result

Campaign: `campaign-029c36d104c0438799a662a72df61bb3`.
Parent report SHA256:
`018e82760e5938a2015eff9373a667507a2c2c0065aa522e9537277b0ede5c04`.
Originals reside under `software/runs/wizard-exports/<campaign-id>/`.

| Leg | Desired base degrees | Reported final degrees | Absolute error degrees | Selected-sample age at write ms | Baseline-end to write ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 1.0 | 1.054687474 | 0.054687474 | 140 | 78 |
| 2 | 0.4 | 0.439453128 | 0.039453128 | 156 | 93 |
| 3 | 1.0 | 1.054687474 | 0.054687474 | 172 | 110 |
| 4 | 0.4 | 0.439453128 | 0.039453128 | 172 | 109 |

All four endpoint decisions passed, all three successive six-joint handoffs
matched exactly, and original integrity, complete native reconstruction and
endpoint-completion consistency verified. The connection lifecycle retained
four exact submissions (63,65,63,65 bytes; 256 total), no errors, no pending I/O
and zero owned handles after closure. No other-joint drift or excursion was flagged.
Post-capture sample counts: 282,281,283,283.

The first attempt's two writes had selected-sample ages 234 and 218 ms; this run's
first two were 140 and 156 ms. Its final two writes remained at 172 ms, leaving
78 ms below the unchanged 250 ms limit. This is a measured improvement in host
processing/dispatch margin, not proof of a worst-case deadline or faster physical
motion. Baseline-to-write values include validation and durable I/O, not pure CPU
time. No speed, model coefficient, endpoint or recency threshold changed.

Machine-readable reconstruction and timing:
[BASE_SINGLE_CONNECTION_COMPLETE_20260915.json](../runs/BASE_SINGLE_CONNECTION_COMPLETE_20260915.json).
The older partial attempt is preserved separately and remains incomplete.

Last reported vector `[b,s,e,t,r,g]` radians:
`[0.007669904,0,1.593806039,0.047553404,-0.001533981,3.149262558]`.
Total historical base commands: 32. Four were sent in this retest.

## Next movement-focused step

Repeat one bounded single-connection campaign to check the newly measured timing
margin before changing mechanical demand. Then prepare a separate speed-comparison
profile with a frozen route, explicit speed-specific validation, and timing/error
exports. Do not silently reuse speed-20 compensation as validated at other speeds.
Keep settlement-gated progression distinct from overlapping continuous trajectories.

# Four-leg compensated base movement sequence

## Predeclared scope

Focus on reliable direction changes and command-feedback-review progression,
not camera metrology, new endpoint coverage or speed optimization.
Maximum four separately admitted commands: increasing corrected, decreasing
corrected, increasing corrected, decreasing corrected. Desired reported endpoints
are +1 and +0.4 degrees; frozen transmitted targets are +2.335749466 and
-0.684826381 degrees. Speed 20 / acceleration 1 remain fixed.

Each command uses the existing wizard/native profile, a fresh eligible six-joint
baseline, one-use admission and five-second capture. Independently reconstruct
the portable export before any next leg. Require nominal endpoint success,
matching next-profile start/context, clean capture and cleanup, no other-joint
drift/excursion or uncertain write. Any failure ends the sequence, with no return,
retry or substitute command. Serial sessions are separate: this is a reviewed
alternating sequence, not continuous streaming or proof of a continuous controller.

Expected initial [b,s,e,t,r,g] radians:
`[0.007669904,0,1.593806039,0.050621366,-0.001533981,3.149262558]`.

Keep these observations out of the frozen model training and matched-control
statistics. Export per-leg starts, desired/transmitted/final angles, error,
direction, reported timing and original report hashes. Report sequence completion
and endpoint handoffs separately from physical tip accuracy and device freshness.

## Status

Completed four of four commands, with three exact six-joint endpoint-to-start
handoffs. All four nominal endpoints passed. No retries, extra positioning,
returns or coefficient changes. All exports reconstructed consistently with no
trial errors, uncertain writes, other-joint drift/excursion flags, pending I/O
or unclosed handles.

## Results

| Leg | Direction | Desired degrees | Reported final degrees | Absolute error degrees | Post samples |
| --- | --- | ---: | ---: | ---: | ---: |
| 1 | Increasing | 1.0 | 1.054687474 | 0.054687474 | 282 |
| 2 | Decreasing | 0.4 | 0.439453128 | 0.039453128 | 282 |
| 3 | Increasing | 1.0 | 1.054687474 | 0.054687474 | 281 |
| 4 | Decreasing | 0.4 | 0.439453128 | 0.039453128 | 281 |

Each capture lasted five seconds. Confirmed write bytes: 63, 65, 63, 65.
Constant final reported tails spanned 4.015, 4.031, 3.969, 4.031 seconds.
Both cycles reproduced their endpoints exactly at the available reporting
resolution. This is successful reviewed sequencing, not proof of zero mechanical
variation, fresh device samples, continuous operation or accuracy at other poses.

Pinned original selections, full reconstructed endpoint records and reported
timing are in [the sequence artifact](../runs/BASE_ALTERNATING_MOVEMENT_20260915.json).
Each `legs` entry contains `selection` and `expected_schema`, suitable for
`read_base_experiment_export(selection, expected_schema=expected_schema)` in
`rocell.application.base_compensation_comparison`. Reverification must compare
successive six-joint final/start vectors and frozen context/model references.

Last reported vector remains the initial lower pose:
`[0.007669904,0,1.593806039,0.050621366,-0.001533981,3.149262558]` radians.

## Next movement-focused implementation

Implement one bounded four-leg campaign in a single owned connection, retaining
per-leg synchronized telemetry, endpoint settlement, next-start eligibility,
direction-specific inverse selection, cancellation and fault-hold progression.
Keep the same two endpoints and speed initially so connection/sequencing changes
can be evaluated without also changing mechanical demand. Preserve old intent
semantics; do not loosen current single-command profiles to accept arbitrary lists.

Simulate success, failure on each leg, stale/mismatched feedback, cancellation
between legs and export reconstruction before live dispatch. A failed leg must
prevent remaining writes; no automatic recovery/return. Then compare the bounded
single-connection run with this retained separate-session baseline. Only after
that comparison consider a separately declared speed change or expanded endpoint
range. Camera work is deferred in favor of motion-interface reliability.

The v14 four-leg contract and owned-executor simulation are now implemented;
native integration remains pending. See
[single-connection implementation status](BASE_SINGLE_CONNECTION_SEQUENCE_20260915.md).

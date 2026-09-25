# Reversed-order base compensation repeat

## Predeclared experiment

Repeat the frozen +1-degree desired endpoint experiment in the opposite order
from the first pair: uncorrected control first, corrected trial second. Admit
each command separately with fresh feedback and review its original export
before proceeding. Maximum two experiment commands in this repeat; no automatic
retry, return, speed change or model refit.

Both trials require the same six-joint start within the comparison's 0.01-degree
matching tolerance and the native fitted base starting domain. The last observed
base position, 0.439453128 degrees, is historical only. If it has changed, stop
and review whether separate positioning is needed rather than assuming the
repeat is executable.

- Desired endpoint: +1 degree in reported base coordinates.
- Control command: +1 degree, uncorrected.
- Corrected command: +2.335749465967 degrees.
- Speed / acceleration parameters: 20 / 1.
- Capture: five seconds per command, with all six joint readings retained.
- Corrected accuracy screen: absolute reported endpoint error at most 0.25 degree,
  plus valid capture, settling, movement and other-joint checks.
- Compare absolute error with the first pair without retraining. Report endpoint
  variation explicitly; two pairs cannot exclude all order effects or establish
  general physical-space accuracy.

Reference: [first pair](BASE_FIRST_COMPENSATION_PAIR_20260915.md).

## Execution status

Completed: two separately admitted experiment commands, control then corrected.
No positioning move, automatic retry, return or model refit was needed.

| Trial | Transmitted target | Reported endpoint | Signed error from desired 1 degree |
| --- | --- | --- | --- |
| Uncorrected control | 1 degree | 0.439453128 degrees | -0.560546872 degrees |
| Corrected repeat | 2.335749466 degrees | 1.054687474 degrees | +0.054687474 degrees |

Both reproduced the first pair's reported endpoints exactly. Both corrected
trials passed the 0.25-degree experiment screen; both controls missed. Absolute
error was 90.24% lower with correction in each pair. No endpoint order difference
was observed across these two pairs, but this sample does not exclude order
effects, quantization, load effects or changes at other poses/speeds.

The actual six-joint baseline matched exactly in all four experiments:
`[0.007669904, 0, 1.593806039, 0.050621366, -0.001533981, 3.149262558]` radians.
The model and both commands remained frozen throughout.

## Capture and movement review

- Control: 64 confirmed command bytes; 5.016 seconds, 282 pose samples, 57,813
  capture bytes. Base feedback was constant over the final 4.875 seconds.
- Corrected: 63 confirmed command bytes; 5 seconds, 282 pose samples, 57,873
  capture bytes. Final base feedback was constant over 253 samples / 4.5 seconds.
- Both exports independently reconstructed, with no capture errors, uncertain
  writes, other-joint drift or joint excursion. All owned handles closed, with
  no pending I/O.
- The control remained correctly marked `NO_RESPONSE` / `HELD`; the corrected
  trial was `REPORTED_SETTLED` / `ENDPOINTS_REPORTED_COMPLETE`.
- The corrected repeat's reported quiet-band entry bounds were 391-406 ms after
  command completion, compared with 781-797 ms in the first corrected trial.
  These are host-observed telemetry bounds, not independent physical arrival
  timestamps. Endpoints repeated, but motion timing was not identical.

Last observed pose after the corrected repeat:
`[0.018407769, 0, 1.593806039, 0.050621366, -0.001533981, 3.149262558]` radians
(base 1.054687474 degrees). This is outside the positive model's starting domain.
Do not send another correction directly from this pose. A future campaign must
verify a fresh eligible baseline, with separate positioning if needed.

## Original references

Exports are under `software/runs/wizard-exports/<campaign-id>/`; each report is
named `<campaign-id>-parent-report.json`.

| Role | Campaign | Report SHA-256 |
| --- | --- | --- |
| Repeated control | `campaign-3a0164a73c634d07a2559baef4c311fc` | `9fa80cb50989e6a048f340016bddc40fcd0a40e73e6ea5c9c9cd070a7fe8f471` |
| Repeated correction | `campaign-87d070a24af74d9c9d33000a3c2bf08e` | `22aa8b2a43b1bd3c11b5482a114da97a8f750d1bbfd07fa31e46e9a69f639887` |

Planning baseline operations were `operation-20f9cb20573b47379efb46bb6e5380f4`
and `operation-0e8dd30abc2541329664276b8a2c3fec`, respectively. Each sent zero
command bytes and closed cleanly; each motion campaign then acquired its own
fresh native baseline before dispatch.

## Reproducible repeat summary

`application/base_compensation_comparison.py` now provides
`summarize_base_compensation_repeats(pairs)`. Supply two through eight pair
selections in the existing `corrected` / `control` export-selection format.
It revalidates all original exports and rejects reused campaign IDs or report
hashes, changed model/context, changed desired endpoint and mismatched six-joint
starting poses. It reports error and endpoint variation without refitting or
granting motion authority.

Saved result: `runs/BASE_COMPENSATION_REPEATS_20260915.json`.

- Corrected mean and worst absolute error: 0.054687474 degrees, two trials.
- Control mean and worst absolute error: 0.560546872 degrees, two trials.
- Reported endpoint span: zero in each group. This is limited by encoder/report
  resolution and is not proof of zero physical repeat variation.
- Targeted checks before motion: 18 passed. Repeat-summary and original-comparison
  tests after implementation: 13 passed, recorded in
  `runs/base-reversed-pair-regression-20260915.xml`. Counts overlap.

## Next bounded step

Retain this correction as a local experimental mapping, not a general controller
setting. First inspect the already retained intermediate telemetry to compare
the settling times; another movement is not required to begin that analysis.
Then prepare an opposite-direction base correction using the separate decreasing
model, with its own bounded proposal and matched control. Do not reuse the
increasing coefficient, transfer it to another joint or extrapolate its domain.
Collect further repeats if the retained timing data or next comparison warrants
them; do not silently change speed while evaluating a new direction.

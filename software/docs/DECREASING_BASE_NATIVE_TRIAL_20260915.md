# First decreasing base correction/control pair

## Predeclared scope

Implement and simulate native v12 corrected and v13 uncorrected-control profiles,
then run one matched decreasing pair if actual fresh feedback qualifies.
No speed change, retraining, continuous movement or arbitrary endpoint input.

- Desired endpoint: +0.4 degree in reported base coordinates.
- Corrected absolute command: -0.684826381297 degrees.
- Control absolute command: +0.4 degree.
- Speed/acceleration parameters: 20/1; five-second observation after each command.
- Corrected trial starts above +0.9 and at most +1.054687474 degrees, with the
  frozen other-joint pose/context. Both desired and commanded moves remain bounded.
- Endpoint verification uses the desired endpoint, the 0.25-degree experiment
  screen and all existing capture/settling/other-joint checks.

Maximum three separately reviewed live commands for this first pair: decreasing
correction, one positioning command if needed, then decreasing control. Review
each original export before the next campaign. Do not automatically retry a miss.

If the first correction settles near +0.439453128 degrees, the already tested
increasing correction may be used as a separately labeled positioning campaign
to restore the +1.054687474-degree starting pose. It is not part of the decreasing
pair and must not be counted as new held-out training. If it does not restore a
matching eligible pose, stop and review rather than proceeding with the control.

Compare both six-joint starts within 0.01 degree, context and frozen model hashes.
The positive +0.4-degree control command lies outside the decreasing model's
negative command-anchor range: measure it directly; do not extrapolate the model.

## Status

Completed the first native pair, including its separately reviewed positioning
command. Exactly three live commands were sent; no retries or automatic returns.

## Implementation and verification

Native v12/v13 profiles are integrated through proposal generation, wizard
staging/preview, one-use admission, worker protocol, capture verification and
portable export reconstruction. Direction is explicit; v10/v11 positive-direction
semantics remain unchanged. Frozen evidence is rebuilt from eight training exports
and three held-out exports before staging. No model was retrained.

Both intended and transmitted deltas are checked against fresh feedback. Tests
caught a floating-point edge at exactly +0.9 degree; this boundary is now explicitly
excluded in both the proposer and native admission.

- Broad regression: 770 passed, 156 intentionally skipped; see
  `../runs/decreasing-base-native-regression-20260915.xml`.
- Proposal tests after descriptive integration-status update: 19 passed.
- Tests cover decreasing correction/control composition, mismatch/fault/cancel
  paths, no replay, endpoint reconstruction, process codec and wizard preview.

## Live results

All values below are reported joint degrees, not independently measured physical
or Cartesian accuracy. Speed/acceleration remained 20/1 throughout.

| Role | Start | Desired | Transmitted | Final | Absolute desired error |
| --- | ---: | ---: | ---: | ---: | ---: |
| Decreasing corrected | 1.054687474 | 0.400000000 | -0.684826381 | 0.439453128 | 0.039453128 |
| Positioning only | 0.439453128 | 1.000000000 | 2.335749466 | 1.054687474 | 0.054687474 |
| Decreasing control | 1.054687474 | 0.400000000 | 0.400000000 | 1.054687474 | 0.654687474 |

The corrected endpoint passed the 0.25-degree experiment screen. The control
reported no change across its capture and correctly held without retry. Its
nonzero helper exit represents that endpoint miss, not a transport/cleanup fault.
The six-joint starts of the pair match exactly. Reported absolute endpoint error
was 93.973746% lower with correction. Positioning is excluded from the pair and
from training data.

### Retained original exports

All directories below are under `software/runs/wizard-exports/`; each report is
named `<campaign-id>-parent-report.json` within its campaign directory.

- Corrected: `campaign-7515bad942804d94b1ef2a80107dd36b`;
  SHA256 `7ed0156983d39d53aa3d37f7c44e494880da675b3f4baa57c5422a3f6596ea9a`.
- Positioning: `campaign-efb22d425b254dba88d6553863bbffce`;
  SHA256 `88f671d2cc4ec62b243f89009f446d5bb700c92cdde5dbd3a4082e70d8879c96`.
- Control: `campaign-d1cc07eb027c4143bfb9e044d6a34d7f`;
  SHA256 `11564d4862cb497372972e167e434be46c0e7edc0e462809fb1af3a08575b432`.

Each export independently reconstructed consistently from retained originals:
no trial errors, uncertain writes, other-joint drift flags, excursion flags,
pending I/O or unclosed handles. Each post-command capture lasted five seconds.
Corrected/positioning/control write sizes were 65/63/64 bytes; post samples were
283/282/282. Constant final reported tails spanned 4.078/3.968/4.891 seconds.

The corrected capture first reported a change 610–625 ms after the write and
entered its final constant reported value at 828–844 ms. These are host capture
bounds, not verified physical movement latency or device sample freshness.

Machine-readable comparison, original selections and excluded positioning role:
[DECREASING_BASE_FIRST_PAIR_20260915.json](../runs/DECREASING_BASE_FIRST_PAIR_20260915.json).
Reproduce from the repository root by loading its `selections` and invoking
`compare_base_compensation_pair(**selections, direction='DECREASING')` from
`rocell.application.base_compensation_comparison`. This rereads portable originals;
the summary itself is not motion authority.

## Interpretation and next bounded work

This is one local decreasing pair, not repeat validation or a global inverse.
The frozen decreasing model has a narrow measured output range; the broad
0.25-degree screen must not be interpreted as precision demonstrated throughout
that range. Increasing correction has two matched pairs from earlier work.

Next: a predeclared reversed-order decreasing pair (control then corrected),
using fresh eligible starts and unchanged model/context/speed, followed by an
explicit direction-aware repeat summary. Only then consider expanding endpoint
coverage or moving to another independently characterized joint. Do not transfer
base coefficients to shoulder/elbow or infer Cartesian accuracy from encoders.

Last reported vector `[b,s,e,t,r,g]` in radians:
`[0.018407769, 0, 1.593806039, 0.050621366, -0.001533981, 3.149262558]`.
No further command was sent after the control.

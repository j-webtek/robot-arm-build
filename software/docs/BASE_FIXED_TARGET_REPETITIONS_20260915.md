# Fixed absolute-target base repetitions

## Outcome

Both repeated commands produced exactly the earlier reported endpoint. Arrival
still failed; repeatability and accuracy are different outcomes.

| Direction | Fixed command deg | Actual starts deg (original / repeat) | Final deg (both) | Final error deg |
|---|---:|---|---:|---:|
| Increasing | 2.4394531285 | 0.4394531285 / 0.3515624913 | 1.0546874740 | -1.3847656545 |
| Decreasing | -0.9453125260 | 1.0546874740 / 1.0546874740 | 0.3515624913 | +1.2968750174 |

Each local target now has two observations with zero reported final-angle span.
The positive repeat started 0.0878906372 degree lower but ended at the same
reported coordinate. This is preliminary target/approach-conditioned evidence,
not proof of a general mapping, physical tool-tip accuracy, or sample freshness.

## How targets stayed fixed without falsifying the baseline

The existing trusted-host staging accepts historical planning records and requires
a separate fresh owned baseline at execution. Reusing the original planning
records reproduced the exact absolute targets in **new** one-use v8 campaigns.
No consumed campaign was replayed and no ideal angle replaced measured feedback.

- Increasing planning record: `operation-6cf7ec6b33224e5aabc1eccd58525f33`.
- New preflight capture: `operation-e5210b5d7e2f47a5a77be5de8ba86a46`.
- Actual increasing delta was 2.0878906372 degrees, inside the already tested
  >1.5 to <=2.5 degree fresh-start bound. The actual start differed from the
  planned start by 0.0878906372 degree, within the existing 0.5-degree match gate.
- Decreasing planning record: `operation-8ed59631afe443d8acbe3086aae1b5f9`.
- New preflight capture: `operation-4c181567e3d14f0f8c8013686f2740ad`.
- Actual decreasing delta was -2 degrees. Both campaigns independently captured
  synchronized fresh baselines before admission. Both preflight captures had zero
  motion-write bytes and clean closure.

No software, firmware, thresholds, speed or acceleration changes were necessary.
No extra positioning command was sent. Each finite campaign held on its endpoint
miss; the next campaign was selected only after reviewing the retained result.

## New captures

Increasing:

- Campaign `campaign-23dc3be39db74fc0933ef4b6fd9f060e`.
- Report SHA-256 `f9ea1cab55790f63e5e6755c6bf880a8b8b3186e4c63c839cdd1d251e4b60f87`.
- One confirmed 63-byte command, no uncertainty.
- Five seconds, 281 poses, 57,612 bytes; final 219 base samples identical over
  at least 3.922 seconds of host acquisition timing.

Decreasing:

- Campaign `campaign-4bc548d1a8cb4b26b039c53db27a16db`.
- Report SHA-256 `e95214d13180f945aaa7afaa12524b754b84ef0ef9fdde1015dd7c4220d58b92`.
- One confirmed 64-byte command, no uncertainty.
- Five seconds, 282 poses, 58,059 bytes; final 225 base samples identical over
  at least 4 seconds of host acquisition timing.

Both: no capture errors, no other joint exceeding drift tolerance, no base
excursion, all handles closed, no pending I/O. All four original/repeated exports
were independently reverified; controller/protocol/workcell/tool hashes match.
Raw originals remain under `runs/wizard-exports/<campaign-id>/`.
Machine-readable comparison: `runs/BASE_FIXED_TARGET_REPETITIONS_20260915.json`.

## Next modeling work

The base inventory now contains eight motion observations: four one-degree
captures and four captures at the fixed two-degree-profile targets. The earlier
zero-write prefix failure remains excluded from endpoint measurements.

Build an offline target/approach-conditioned dataset retaining nominal target,
transmitted command, actual starting pose, final feedback, capture profile and
all context references. Keep repeated captures grouped so they cannot leak into
both training and purported independent target validation. Use a simple lookup
or bounded model only within the measured domain; two points per direction do
not justify a flexible fit or extrapolation.

Select an independent intermediate command as a held-out prediction experiment
before attempting compensation. Screen any predicted response against the actual
start and direction; if a simplistic model predicts a response inconsistent with
its approach assumptions, reject it instead of increasing the command blindly.
No global offset, inverse-gain multiplier, or automatic compensation is enabled.

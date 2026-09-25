# Base endpoint repeatability: two captures per direction

## Result

Four uncorrected one-degree probes have retained, independently reconstructed
endpoint records. Both repetitions in each direction have identical reported
starts, targets and final angles. These are servo-reported coordinates, not
independently measured physical tool-tip positions.

| Direction | Captures | Requested change | Reported change | Endpoint error |
|---|---:|---:|---:|---:|
| Increasing | 2 | +1 degree | +0.0878906372 degree | -0.9121093628 degree |
| Decreasing | 2 | -1 degree | -0.0878906372 degree | +0.9121093628 degree |

The observed final-angle span within each two-capture group is zero. This small
sample does not establish general repeatability, mechanical cause, device sample
freshness, or a validated compensation model. No target arrived within tolerance.
The original pair used v6; the second pair used v7 synchronized baselines. That
measurement-profile change is explicitly retained rather than hidden. Controller,
protocol, workcell and tool reference hashes match across all four captures.

## Latest decreasing probe

- Planning baseline: `operation-08965beeed9e403fb189b1606862cd8c`, zero motion writes,
  expected reported pose and clean closure.
- Campaign: `campaign-b3ce9cf64d834417946567242f84c6ba`.
- Parent report SHA-256:
  `5c158200f4631293439779401207d54dffe43f5e211858c986750d1777adda2d`.
- Start: 0.5273437656 degrees. Intended/transmitted target: -0.4726562344 degrees.
- Final: 0.4394531285 degrees, returning to the original reported base coordinate.
- One confirmed 65-byte command, no write uncertainty; speed 20 / acceleration 1.
- Synchronized baseline retained seven startup bytes in a 13,632-byte original.
- Post capture: five seconds, 282 pose records, 58,019 raw bytes.
- Final 234 base samples constant for at least 4.172 seconds of host acquisition.
- No other joint exceeded drift tolerance; no base excursion; capture errors empty;
  all handles closed with zero pending I/O. Export reconstruction verified.
- Preserved `NO_RESPONSE` verdict means movement below the monitor's 0.5-degree
  threshold, not literally zero reported movement. No retry or return followed.

Machine-readable comparisons and exact report hashes:
`software/runs/BASE_REPEATABILITY_20260915.json`.
Original exports: `software/runs/wizard-exports/<campaign-id>/`.
The intermediate v6 prefix failure remains a separate zero-write diagnostic and
is not counted as an endpoint observation.

## Next discriminating experiment (not yet enabled or run)

Repeating the same magnitude cannot distinguish a fixed directional shortfall
from a proportional response. Compare an uncorrected two-degree probe next,
with synchronization and the same tool/other-joint pose/speed context.

For illustration only, two hypotheses that both match the observed one-degree
change predict very different responses to a positive two-degree request:

- Fixed shortfall of 0.9121093628 degree: approximately +1.0878906372 degree change.
- Proportional response of 0.0878906372 per requested degree: approximately
  +0.1757812744 degree change.

These are contrasting predictions, not fitted or approved compensation commands.
Other behavior, including deadband or load/history dependence, remains possible.

Implementation sequence:

1. Add a separate versioned two-degree base-only profile. Do not weaken v6/v7
   one-degree contracts or change the historical records.
2. Keep one write, speed 20, acceleration 1, five-second post capture, +/-5-degree
   local base envelope and all five other-joint checks. Nominal delta exactly
   two degrees; fresh-start delta must remain within an explicitly tested bound
   (proposed >1.5 and <=2.5 degrees). Preserve approach direction and no retry.
3. Test wrong axis, changed targets/limits, baseline drift, synchronization,
   cancellation, uncertain writes, full wizard dispatch and portable exports.
4. Acquire a fresh baseline and run only the increasing probe first. Review
   complete telemetry, not just the final angle, before any reverse probe.
5. Compare the observation against both predictions without changing offsets.
   Repeat at matching endpoints before selecting or validating a compensation
   model. Do not invert the one-degree response ratio to command a large move.

No motion-profile change, faster sweep or compensation was enabled this turn.

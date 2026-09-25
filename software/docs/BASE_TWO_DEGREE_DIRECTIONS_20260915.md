# Two-degree base probes: first opposite-direction observations

## Verified comparison

| Direction | Start deg | Target deg | Reported final deg | Change deg | Endpoint error deg |
|---|---:|---:|---:|---:|---:|
| Increasing | 0.4394531285 | 2.4394531285 | 1.0546874740 | +0.6152343455 | -1.3847656545 |
| Decreasing | 1.0546874740 | -0.9453125260 | 0.3515624913 | -0.7031249826 | +1.2968750174 |

Both commanded exactly two degrees from their own reported starting pose,
speed 20 / acceleration 1, without compensation. Both missed their intended
endpoint; both captures reconstructed independently from retained originals.
The absolute response differs by 0.0878906372 degree. This is not a matched
same-start/target experiment: direction, angle and approach history differ.
Do not infer a direction-only coefficient or a validated nonlinear model.

## Latest negative probe

- Planning baseline: `operation-8ed59631afe443d8acbe3086aae1b5f9`; expected unit,
  stable matching reported pose, zero motion-write bytes and clean closure.
- Campaign: `campaign-124ebf7212574f569a6bfb89ba9a42ec`.
- Parent report SHA-256:
  `2bdb5de0dd4207ed86f7f5fd09245a2022d3e955c3347aeb9eac00fe0139230b`.
- Single 64-byte T101 joint-1 command; confirmed completion with no uncertainty.
- V8 synchronized baseline retained 197 startup bytes in a 13,632-byte original.
- Five-second post capture: 281 poses, 57,737 bytes. Last 225 base samples
  constant across at least 4.031 seconds of host acquisition timing.
- No other joint exceeded drift tolerance; no selected-axis excursion;
  no capture errors; all handles closed and no pending I/O.
- Endpoint verdict `TARGET_MISSED`; no retry or return command was sent.
- Last reported base coordinate: 0.3515624913 degrees. Independent physical
  tool-tip accuracy and device sample freshness remain unverified.

## Evidence and next test design

`runs/BASE_TWO_DEGREE_DIRECTIONS_20260915.json` contains both independently
verified report hashes, full endpoint summaries, synchronization partitions,
write/cleanup records and matching controller/protocol/workcell/tool hashes.
Portable originals remain in `runs/wizard-exports/<campaign-id>/`.

Current base data: four one-degree captures (two per direction), two two-degree
captures (one per direction), plus one excluded zero-write baseline failure.
No software or firmware changes were made during this negative probe.

Next collect repeated fixed absolute targets with explicitly retained actual
starting angles and approach direction, rather than allowing each relative
command to silently shift the target. Positioning legs must be separately
bounded and reviewed; count them separately from measurement trials. Preserve
the fresh baseline's actual coordinate instead of replacing it with an ideal
start, and never treat a positioning miss as successful arrival.

Use those observations to evaluate a local target/approach-conditioned lookup
or simple model against held-out points. Do not apply a global offset, transfer
the wrist correction, or fit a flexible curve merely because it interpolates
the existing few measurements. Maintain the current single-command workflow
until a bounded sequence and its progression rules are independently tested.

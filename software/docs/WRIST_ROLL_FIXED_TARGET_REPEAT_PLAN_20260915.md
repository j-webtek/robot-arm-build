# Wrist-roll fixed-target repetition plan

## Evidence and purpose

The first +1-degree request reported +0.791015620 degree of movement and error
-0.208984380 degree. The first -1-degree request reported -0.615234345 degree
of movement and error +0.384765655 degree. Both passed the existing 0.5-degree
endpoint band, but neither was exact. With one observation per direction at
different absolute targets/starts, this does not yet establish a direction-only
error model, backlash estimate, or reusable compensation offset.

The decreasing trial did not restore the original roll pose: current r is
0.001533981 rad, versus original -0.001533981 rad. Repeated relative +/-1-degree
commands would therefore change absolute destinations. Do not label that as a
matched-target repeat or silently apply offsets to force the original start.

## Implement before further movement

Add a separately versioned fixed-target roll profile. Preserve v16's relative
one-degree semantics. Bind these two previously transmitted raw targets:

- Increasing raw target: 0.015919311519943295 rad (~+0.91210937 degree).
- Decreasing raw target: -0.005181446519943296 rad (~-0.29687503 degree).

Use expected measured start anchors r=0.001533981 for increasing and
r=0.012271846 for decreasing. Other five joints stay bound to the current
bench pose. Preserve existing fresh-baseline checks, no compensation, speed 20,
acceleration 1, five-second capture, one-use command, travel/excursion checks,
all-other-joint monitoring and owned cleanup. Do not widen the endpoint band.

Validate explicit target/axis/command identity, fresh six-joint start, native
isolated package, wizard labels, export reconstruction, miss/fault/no-retry
behavior and prevention of accidental ingestion into base or pitch training.

## Finite first repeat, only after software validation

At most four independently admitted single commands: increasing, decreasing,
increasing, decreasing. Require fresh matched measured anchors before each.
Independently review every endpoint and export before proceeding. A passing
endpoint which does not match the next fixed start anchor ends progression;
no extra positioning, automatic return, retry, or changed command is included.

The first new increasing observation has a different start from the original
increasing probe; keep that distinction. Compare the two NEW increasing trials
with each other, and the two NEW decreasing trials with each other. Older
observations are context only unless their full measured starts match.

Rebuild errors and reported spread from distinct original exports with matched
six-joint starts, targets, speed, acceleration, payload and protocol context.
Keep misses as observations; do not fit only favorable data. Two repeated trials
per direction are a preliminary repeatability screen, not model validation.
Only after that screen define additional command points and held-out validation
for any proposed roll compensation. No base/pitch coefficients may be transferred.

Status: implemented and the four-command repeat screen completed on 2026-09-15.
v17 preserves the fixed targets; v16 remains unchanged for relative probes.
The focused native/wizard/export regression passed 135 tests (261 deselected).
All four live commands completed with independently reconstructed exports and
matching measured handoffs. The read-only pair reviewer passed nine additional
tests. See [results and next experiment](WRIST_ROLL_FIXED_REPEAT_20260915.md).

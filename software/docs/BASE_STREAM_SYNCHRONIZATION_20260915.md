# Versioned base-stream synchronization

## Reason

The repeat attempt `campaign-0aeee084a37943af97b21f61878bc1bc` began with
`}\r\n` and correctly held under v6 before writing. It remains a held original;
the new implementation does not retroactively make it valid.

## Implementation

- New opt-in intent v7, limited to the existing one-degree base probe.
- 1.25-second owned raw baseline capture, within existing byte/leg/overall budgets.
- Exactly one startup line, capped at 250 ms / 4096 bytes, followed by at least
  one second of clean six-joint pose samples.
- No search for a convenient later valid line. Further partial-prefix recognition
  is explicitly rejected after the known synchronization delimiter.
- Pure partition function shared by admission, independent reconstruction and
  portable export. Original raw bytes, windows, lengths and hashes remain intact.
- Explicit wizard preview; trusted-host opt-in and bench CLI flag.
- Old schemas and their validation semantics unchanged. No motion tolerance,
  angle, command count, speed, acceleration, or cancellation policy widened.

## Validation

Tests cover the actual observed prefix, an already aligned stream, CRLF boundary,
an arbitrary first startup line, second malformed/blank/partial lines, absent or
late delimiter, excess prefix bytes, insufficient baseline duration, portable
reconstruction, both direction commands, misses, changed starting pose,
cancellation, and supervisor request association. Incapable fixtures cannot
open or move hardware.

Live rollout must start with a fresh baseline, then one opt-in base command.
Inspect startup ranges and reconstructed result regardless of arrival. A target
miss remains a miss. Stop and review unexpected capture/transport faults rather
than retrying within the campaign.

## Completed validation and live rollout

- Broad regression: **543 passed**, 28 intentionally skipped non-base synchronized
  combinations (`runs/base-sync-regression-20260915.xml`).
- Additional focused regression: **39 passed**, overlapping the broad suite
  (`runs/base-sync-additional-20260915.xml`).
- Live planning baseline: `operation-7d6185a548574c31bf21fb0cbad82b30`, zero motion
  writes and clean closure; reported pose matched the original increasing probe.
- V7 campaign: `campaign-38e373e9116648f0a2eb8da5654134de`.
- Verified report SHA-256:
  `96a8631ba3cc812d16b77685f6eedcdc4a6cf6089ee51e30abb5ba46220584a4`.
- Baseline: 1.25 seconds / 13,632 bytes, startup range `[0,93)` retained and
  excluded from baseline analysis; no further prefix was skipped. Parent
  reconstruction independently reproduced the partition and endpoint result.
- Exactly one confirmed 64-byte base command, speed 20 / acceleration 1.
- Start 0.4394531285 degrees; target 1.4394531285 degrees;
  final 0.5273437656 degrees; change +0.0878906372 degrees;
  signed endpoint error -0.9121093628 degrees.
- Post: five seconds, 281 poses / 57,721 bytes; final 247 base samples constant
  for at least 4.406 seconds. No other joint changed beyond the monitor tolerance,
  no selected-axis excursion, no capture errors, all handles closed.
- Endpoint held as `NO_RESPONSE` under the existing 0.5-degree movement threshold.
  Synchronization succeeded; arrival did not. No retry or return was sent.

The reported positive endpoint exactly repeats the earlier v6 result, although
the baseline capture profile has deliberately changed. We now have two positive
captures and one negative capture, plus one excluded pre-write attempt. This is
still insufficient for a validated compensation model. Next collect the matching
negative repetition, then design a separately bounded magnitude comparison.

Machine-readable result: `runs/BASE_SYNC_LIVE_RESULT_20260915.json`. The complete
portable original export is in `runs/wizard-exports/<campaign-id>/`.

Follow-up: the matching synchronized negative repetition also completed its
capture and reproduced the earlier negative endpoint. Current four-capture
comparison and next magnitude experiment are in `BASE_REPEATABILITY_20260915.md`.

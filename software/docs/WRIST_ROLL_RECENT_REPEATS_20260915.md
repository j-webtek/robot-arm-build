# Recent wrist-roll repetition screen

## Completed

Two new separately admitted v19 commands were executed this turn: increasing
then decreasing, each preceded by fresh no-command feedback and followed by
35 seconds of continuous capture. All original exports independently verify.
There was no retry, correction or automatic continuation.

Fresh baseline operations:
- Increasing: `operation-afb11f6670054ad3824cb51e95843355`.
- Decreasing: `operation-0a3f72ce02a84f37821cf4f114bfc630`.

New campaigns:
- Increasing: `campaign-562c2a5eb4c043899a583ec0c4da329e`, report SHA256
  `532bbf41a2f41f11bb9dc9176fe34068668031c85243129b5c51bf0898d8dfe5`.
- Decreasing: `campaign-20bc8b3f7d764bc599e8fc0ac6d03f97`, report SHA256
  `3bee0038fe2b0710dc1034dd84f08d95db3f760b52e46f36e52804f67ed36e49`.

Both had exactly one confirmed write, no uncertain write, clean handle closure
and no pending I/O. Increasing retained 1,948 poses; decreasing 1,947. Every
5/10/20/35-second horizon had the same endpoint within each run. Other five
joints had zero reported drift. Maximum host gaps were 62 and 63 ms.

## Comparison with the preceding two trials

| Direction | Reported travel, first / repeat | Signed target errors | Endpoint spread |
| --- | --- | --- | --- |
| Increasing | +0.791016 / +0.791016 deg | -0.208984 / -0.208984 deg | 0 deg |
| Decreasing | -0.791016 / -0.703125 deg | +0.208984 / +0.296875 deg | 0.087891 deg |

Each direction has identical six-joint starts, exact commands, source version,
configuration, protocol, controller, payload and workcell references across
its two recent samples. Per-run baseline and runtime registration hashes differ
and remain explicitly reported. This is not byte-identical runtime evidence.

The decreasing variation is now present within this same source version, not
only in comparison with the older build. Both different decreasing endpoints
were individually persistent for 35 seconds. Therefore within-run settling
must not be confused with across-run repeatability. These results alone do not
establish a mechanical or firmware cause.

The original older decreasing result and the held late-change trial remain
part of the history; this screen does not erase them or select only successes
to claim general precision. Two observations per direction are a small local
screen, not a statistically established error distribution.

## Evidence and reproduction

Run `software/scripts/review_roll_recent_repeats_20260915.py` with workspace
Python. It verifies four pinned exports, decodes original captures, checks
reported handoffs and matching pair context, and prints all comparison data.
It does not connect, write, fit or apply compensation.

Saved output: `software/runs/WRIST_ROLL_RECENT_REPEATS_20260915.json`.
All four original bundles reconstructed with endpoint completion during review.

## Current pose and next experiment

Last reported joints [b,s,e,t,r,g]:
`[0.007669904,0,1.593806039,0.047553404,0.004601942,3.149262558]`.
Roll count fourteen; base remains 44. No post-run reconnect or further motion.

This roll value matches the v21 increasing fixed profile's required low anchor.
The next useful bounded test is fresh feedback followed, only if it matches,
by one v21 fixed increasing probe to 0.022055234519943297 rad. That tests the
new native framing path and revisits an already transmitted target from its
matching start. Compare it with the earlier increasing persistence trial,
disclosing its different source/schema context. Do not silently restart the
old unfinished four-command campaign.

Keep the 35-second persistence test and existing fault holds. Before enabling
compensation, evaluate direction-specific candidates against held-out trials
and retain observed variability; do not treat 0.209 degrees as a universal
offset. No model was fitted or compensation applied in this screen. Reported
joint repeatability is not measured tool-tip or Cartesian accuracy.

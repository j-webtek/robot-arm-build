# Versioned native cross-window framing integration

## Status

Later live update: the first v21 increasing fixed trial completed and exercised
an actual split-frame boundary. See `WRIST_ROLL_FRAMED_LIVE_20260915.md` for
originals, reconstruction and limitations. The text below records the earlier
software-integration checkpoint.

Implemented and tested without hardware access. No new motion or connection was
made. Roll movement count remains ten; base remains 44. This is not a new live
qualification or a physical accuracy claim.

The consolidated regression passed **352 tests**. One additional malformed-export
test passed afterward. JUnit report:
`software/runs/roll-framed-native-regression-20260915.xml`.

## What changed

- New intent v21 and roll-long-fixed configuration v2 opt into framing support.
  v20 and all older contracts keep their original decoder and verdicts.
- Native admission, retained-result reconstruction and portable export use
  `campaign_post_window`, the same version-gated decoder.
- Valid baseline/post crossing fragments are joined only to validate their
  syntax and acquisition bounds. The crossing frame is excluded from endpoint
  evidence; original capture bytes are never rewritten.
- The result commit binds the framing proof, including capture hashes, byte
  ranges and host-read bounds. Portable exports expose `cross_window_framing`.
- Malformed boundary or subsequent feedback yields a bounded named reason in
  the retained native trial, not arbitrary exception text. Incomplete trials
  remain diagnostic-only and do not acquire an endpoint-success claim.
- Native archive includes the decoder. Supervisor recognizes v21 with the same
  58-second process budget, 2-second cleanup budget, 60-second campaign ceiling
  and 47-second prelaunch reserve as the preceding long profile.
- Wizard staging accepts `framed=True` via the existing
  `configure_roll_long_fixed_probe` service. The existing wizard execution/export
  flow is reused. No new frontend toggle was added.

## How to select it

Existing calls remain v20 unless explicitly opted in:

```python
service.configure_roll_long_fixed_probe(
    usb_identity=usb_identity,
    start_joints_rad=fresh_start,
    originals=originals,
    direction="DECREASING",
    framed=True,
)
```

The existing bench CLI accepts `--cross-window-framing` only together with
`--roll-long-fixed increasing|decreasing`. All existing baseline/controller
arguments, identity checks, review and one-use admission still apply. This
example is not permission to dispatch from an unmatched pose.

## What did not change

Targets, measured-start anchors, speed, acceleration, 35-second observation,
one-write limit and no-retry behavior remain unchanged. Arrival checks do not
override persistence: a delayed endpoint change still holds the campaign.
This is telemetry-framing handling, not compensation or relaxed accuracy limits.

The pinned historical v20 export was replayed again: original integrity passes,
historical verdict remains HELD, and offline analysis still reports
REPORTED_ENDPOINT_CHANGED. The 0.088-degree change at roughly 18.3 seconds was
not hidden by the fix. See `WRIST_ROLL_CROSS_WINDOW_REPLAY_20260915.md`.

## Validation coverage

Tests cover split frames, malformed fragments, time and byte bounds, old-version
behavior, native-shaped streamed execution, both directions, delayed changes,
misses, cancellation, other-axis drift, held-result exports, isolated package
imports, supervisor deadlines, wizard execution/export and consumed-admission
replay rejection. Test kernels cannot command physical hardware.

## Next hardware step

1. Acquire fresh feedback through the existing owned wizard connection path.
2. Compare all six joints with the last report; do not use it as a fresh baseline.
3. Select or explicitly plan a bounded route from that measured pose. The last
   reported roll was 0.003067962 rad, whereas the old fixed increasing route
   requires 0.004601942 rad. Do not silently relax this anchor or resume that leg.
4. Run one admitted movement only after a matching route exists. Retain the
   complete 35-second capture and inspect arrival, persistence, other-axis drift,
   framing and cleanup together before proceeding.
5. Build matched-start repeats before fitting compensation. No new compensation
   values were fitted or applied in this integration.

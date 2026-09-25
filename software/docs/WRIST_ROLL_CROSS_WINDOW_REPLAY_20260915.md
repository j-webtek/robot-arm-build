# Cross-window framing replay: completed offline

## Result

The pinned retained campaign `campaign-ddd0578c2a554851bca029b2f496a2f7`
was replayed without connecting to hardware. Original integrity verified; its
historical HELD verdict and failed reconstruction remain unchanged.

The baseline's final 199 bytes and post capture's first four bytes form one
203-byte valid pose frame. The diagnostic excludes that crossing frame from
post-command evidence. It preserves source hashes and exact byte/read ranges;
it does not claim lossless transport or fresh device timestamps.

The remaining 1,948 complete poses have no decoded capture issues. Persistence
analysis reports **REPORTED_ENDPOINT_CHANGED**, not a pass:

- Five-second roll: 0.004601942 rad.
- Final roll: 0.003067962 rad.
- Reported difference: -0.087890580 degrees.
- Transition host-read interval: 18.312–18.328 seconds after write.
- Other five joints: zero reported drift; maximum host gap: 63 ms.

The broad arrival tolerance passes, but the stricter persistence check fails.
Neither finding establishes external physical accuracy or a mechanical cause.
This is why a five-second endpoint alone is insufficient for this trial.

## Implementation and reproduction

`software/src/rocell/arm/cross_window_framing.py` verifies original hashes,
byte coverage, timing order, bounded crossing-frame acquisition and valid joined
pose syntax. It examines only the first post newline, never searches forward
for a convenient valid record, and rejects additional malformed prefixes.
The crossing pose is never counted as new post-command feedback.

Run from the workspace:

```powershell
.\.venv\Scripts\python.exe software/scripts/review_roll_cross_window_20260915.py
.\.venv\Scripts\python.exe -m pytest software/tests/unit/test_cross_window_framing.py software/tests/unit/test_endpoint_persistence.py -q
```

The replay verifies the pinned report before reading original captures and
refuses an unexpected framing/persistence result. It prints JSON without writing
or accessing serial hardware. Saved output:
`software/runs/WRIST_ROLL_CROSS_WINDOW_REPLAY_20260915.json`.

Validation: 126 targeted tests passed, including every interior split position,
digest mismatch, invalid fragments, coverage/time faults, excessive acquisition
duration and malformed records after the crossing frame. Hashes bind retained
bytes; syntactic validity alone cannot prove that no bytes were lost in transit.

Expanded regression including existing stream synchronization, coverage and
first-motion analysis: **166 tests passed**.

## Next work and boundaries

Subsequent update: opt-in v21 native integration is now implemented and
software-tested. See `WRIST_ROLL_FRAMED_NATIVE_INTEGRATION_20260915.md`.
The paragraph below records the status at the original offline replay; no
historical v20 result was reclassified and no new hardware run has occurred.

This diagnostic is **not yet wired into native execution**. Historical schema
contracts remain unchanged. Next, introduce explicitly versioned native framing
support, carry the proof and named failure reasons into exports, and cover native
packaging, admission/reconstruction parity and wizard tests. Continue to reject
late endpoint changes after framing succeeds.

Before another physical campaign, obtain a fresh baseline and plan a bounded
route from that measured start. Do not resume the old increasing fixed leg:
its required start is 0.004601942 rad, unlike the last reported 0.003067962 rad.
Do not fit compensation from unmatched starts or silently loosen the anchors.

No commands were sent during this work. Roll count remains ten; base count 44.

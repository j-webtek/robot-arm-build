# Base directional comparison and repeat-attempt diagnostic

## Outcome

Two completed, uncorrected captures now cover opposite base approach directions.
Both requested a one-degree change at speed 20 / acceleration 1. Both reported
only about 0.08789 degree of change and missed the target. This is preliminary
directional characterization, **not** repeated validation or a fitted model.

| Direction | Start deg | Target deg | Final deg | Change deg | Error deg |
|---|---:|---:|---:|---:|---:|
| Increasing | 0.4394531285 | 1.4394531285 | 0.5273437656 | +0.0878906372 | -0.9121093628 |
| Decreasing | 0.5273437656 | -0.4726562344 | 0.4394531285 | -0.0878906372 | +0.9121093628 |

The absolute error is symmetric in this pair. The reported angle returned to
its original value. Neither observation establishes a universal gain or offset:
one encoder-sized increment under a small command could have multiple causes.
Do not invert the observed response ratio or apply the wrist bias to base.

## New reverse capture

- Baseline: `operation-9cc162ff7cfb43a19ef6b9b014e78f66`; no motion writes,
  expected identity, clean closure and matching reported pose.
- Campaign: `campaign-2d2d5c56c8674abaa728b1eb9e442cc0`.
- Parent report SHA-256:
  `64503e36c6a38ffd96f113a53d857130558ef915006821d5d6d9ef7031c67e9b`.
- One confirmed 65-byte T101 joint-1 command; no write uncertainty.
- Five seconds, 280 pose samples, 57,582 raw bytes.
- Final 241 base samples identical over at least 4.297 seconds of host timing.
- No other joint exceeded the drift threshold; no selected-axis excursion.
- No capture errors; all handles closed and zero pending I/O.
- Export originals and endpoint reconstruction verified independently.
- `NO_RESPONSE` is the preserved threshold-based verdict, not zero encoder change.

The first increasing capture is documented in `BASE_MAPPING_FIRST_PROBE_20260915.md`.
Its controller/protocol/workcell/tool references match the reverse capture.
Independent Cartesian accuracy and device sample freshness remain unverified.

## Attempted repetition: no command sent

- Planning baseline: `operation-77cbf97a9d3b4f59b49ef639e0620c82`.
- Campaign: `campaign-0aeee084a37943af97b21f61878bc1bc`.
- Report SHA-256:
  `22468e232ba884d0d184d0c260488420c6d0d29389c0ccebaa8d01619de8b4e8`.
- Native baseline: 10,944 bytes, 53 complete pose lines and one rejected opening
  line containing exactly `}\r\n`; an incomplete suffix is also retained.
- Baseline raw SHA-256:
  `f031bf68d529224cb5b527249707880b331589070950dfbe15da16dd80c5dbfa`.
- The prefix is consistent with a capture-boundary fragment, but not proven to
  be one. No bytes were discarded to promote the baseline into valid evidence.
- Baseline admission held; zero submission attempts and zero command bytes.
  Cleanup completed. The verified export is a diagnostic, not an endpoint result.
- A fake-kernel regression reproduces the exact prefix and requires a pre-write
  hold. No native admission or framing rule was weakened.

## Next work

1. Design explicit bounded stream synchronization before the admitted baseline,
   retaining startup bytes separately and preserving all interior-invalid-line
   rejection. Test it through child admission and parent reconstruction before
   enabling it; do not retrospectively reinterpret the held original.
2. Resume separately admitted same-target repetitions once that path is verified.
3. Collect more than one command magnitude and repeated samples in both
   directions before deciding between local bias, deadband, or gain models.
   Any wider native probe needs a separately tested bounded profile.
4. Keep non-response observations in characterization data, not silently in a
   bias-training set that requires demonstrated movement and held-out validation.

All original exports are under `software/runs/wizard-exports/<campaign-id>/`.
The machine-readable comparison is `software/runs/BASE_DIRECTION_COMPARISON_20260915.json`.
Focused regression: 45 passed, recorded in `base-direction-regression-20260915.xml`.
No compensation, faster sweep, or simultaneous multi-joint motion was enabled.

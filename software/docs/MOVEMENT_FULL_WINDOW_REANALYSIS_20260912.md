# Full-window telemetry reanalysis — 2026-09-12

Evidence type: **offline reanalysis of saved physical capture**. No device was
opened and no command or new physical capture was performed for this analysis.

## Original and integrity checks

Export: `software/runs/wizard-exports/wizard-20260912T232404247125Z-19c8b63e3aa54dcb9ff472dc0d9c23d1`.
Input: `attachment-powered-feedback-native-logs.json`, decoded native stdout,
then original capture bytes and v2 read windows.

The retained stdout SHA-256 was checked against its process record. The decoded
raw capture SHA-256 was checked against the original capture blob:
`279f7a7827440ab97dfd374b79cdc705c909b20538c9781769245463210993d1`.

No original result or export was modified. The original 255-sample count remains
correct for its deliberately capped decoder, not the new full-window analysis.

## Derived result

Analyzer: `rocell.arm.telemetry_coverage.analyze_window_coverage`.
Schema: `rocell.telemetry_window_coverage.v1`.

| Measurement | Result |
| --- | --- |
| Retained bytes | 56,384 |
| Processed complete-line bytes | 56,271 |
| Complete pose records | 270 |
| Incomplete telemetry lines | 0 |
| Rejected lines | 1 |
| Possible partial prefix | Bytes [0, 111) |
| Final unterminated suffix | Bytes [56271, 56384), 113 bytes |
| Latest complete record | Bytes [56063, 56271) |
| Latest record host acquisition bounds | [149045484000000, 149045500000000] ns |

The decoder recovered **15 additional complete poses** from the previously
unparsed range. It did not invent a completed frame from the final 113 bytes.
All complete lines are accounted for; the window still contains an incomplete
suffix and a rejected prefix, so it is not represented as a flawless stream.

The latest reported endpoint is x=345.3562001, y=-5.298113331,
z=210.3949988. This is reported telemetry, not independently verified location.
Voltage, torque-switch fields and tG remain absent. Host acquisition intervals
are not device sample times; freshness and physical authority remain false.

## Implementation and verification

- Shared one-line decoder preserves legacy parsing semantics and wire schema.
- Full-window iterator retains at most one expanded line at a time; raw input
  is capped at 64 KiB, read windows at 512, and line parsing at 4096 bytes.
- At most 65,536 newline records can exist in the accepted byte budget. Tiny
  malformed lines remain bounded, counted and do not expand the output.
- Display preview is independently capped at eight records; counting and latest
  record selection continue after that cap. No live permission is produced.
- Split/shared/empty read handling preserves host acquisition bounds without
  inventing individual device timestamps.

Focused verification: **50 tests passed in 8.32 seconds**, basetemp
`software/runs/pytest-coverage-20260912-01`, covering the new full-window analysis,
legacy stream behavior, native telemetry validation and native package isolation.
This is not a claim that the entire project test suite was run.

The live collector still uses its original compact summary. This increment adds
a separate derived analysis; wizard presentation/integration remains P5a work.

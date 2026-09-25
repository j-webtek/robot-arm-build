# Cross-session roll comparison and correction decision simulation

Update: `ROLL_COMPENSATION_GENERALIZATION_20260917.md` adds a reproducible
32-export comparison with the first micro-workflow result and approach-direction
controls. Run with `--include-recent`; the default cohort below is unchanged.

## Completed

Replayed 25 unique exports from the documented lookup/control evidence, original
spacing sweep, separate follow-up and completed paired session. Export integrity
and original endpoint/hold evidence were checked by the existing reviewer. The
paired session journal chain was also checked. This is a selected cohort, not
an exhaustive history. No hardware commands, model fitting or setting changes.

Artifacts:

- `software/scripts/review_cross_session_roll.py`: repeatable offline comparison.
- `software/src/rocell/arm/endpoint_correction_simulation.py`: pure decision replay.
- `software/runs/wizard-exports/cross-session-roll-f779bddc-offline.json`: records,
  source manifest hashes, cohort labels, matched groups and hypothetical decisions.
- 33 focused tests passed (correction decisions and existing export replay).

## Matching and observed response

Groups require the same full six-joint reported baseline, command, desired target,
speed and acceleration. Cohort labels retain experiment provenance. They do not
prove identical mechanical history, temperature, internal servo state or physical
pose. Successful probe groups below started at reported roll 2.285156222 degrees,
with desired roll 1.25 degrees, speed 20 and acceleration 1.

| Command degrees | Complete trials | Minimum reported endpoint | Maximum reported endpoint |
| --- | --- | --- | --- |
| 0.85 | 2 | 1.142578111 | 1.142578111 |
| 0.95 | 9 | 1.230468748 | 1.406250023 |
| 1.05 | 4 | 1.230468748 | 1.406250023 |
| 1.25 | 4 | 1.494140602 | 1.494140602 |

0.95 and 1.05 share the same observed endpoint range across sessions. Matching
the recorded baseline and command therefore does not explain all variation.
Do not claim a universal inverse mapping or physical millimeter accuracy.

The uncertain high-positioning attempt and incomplete 0.85 hold remain separate
failed records and are excluded from complete endpoint ranges, not discarded.
Recovery observations are not used to repair either failure.

## What was simulated

This is decision-policy replay against historical observations, NOT a dynamics
model or prediction of a corrective move's outcome. For an illustrative 0.05-degree
analysis band (not a changed live gate), the policy does the following:

1. Stop on incomplete/unverified evidence.
2. Accept an already in-band reported endpoint without another command.
3. Otherwise assess a direct move to the desired angle using the existing
   `DiscreteTransaction` geometry checks, with the settled angle as its baseline.
4. Even eligible geometry grants no hardware permission and predicts no response.

Across the 20 selected records targeting 1.25 degrees: 9 accept, 10 reject the
direct correction as outside the current envelope, and 1 stops for incomplete
evidence. Including five high-positioning records: 9 accept, 14 geometry rejections,
2 incomplete/unverified stops. Acceptance counts are selected-sample descriptions,
not an estimated independent success probability.

All observed remaining corrections are below the existing >0.5-degree minimum
step. The replay preserves that guard; it does not stretch a tiny correction into
a larger move, introduce a reposition/retry loop, or silently enable micro-moves.

## Next useful work

Build an offline bounded micro-movement commissioning proposal: specify exact
step sizes, maximum attempts and cumulative travel, unchanged-joint requirements,
fresh feedback deadlines, failure behavior, and hold/export requirements. Test
its decision logic against quantized, overshooting, unchanged and delayed feedback
before any live integration. A new micro-move mode would require its own explicit
admission; this document does not enable one. Retain the current single-command
path for live operation and do not repeatedly retry a fixed command to select
only favorable outcomes.

## Reproduce

```powershell
.venv\Scripts\python.exe software/scripts/review_cross_session_roll.py
.venv\Scripts\python.exe -m pytest software/tests/unit/test_endpoint_correction_simulation.py software/tests/unit/test_review_wifi_roll_export.py -q
```

Use `--output` with a new path to retain another report. Output creation is
exclusive and refuses to overwrite an existing report. The tool never connects
to the robot. Historic poses and analysis decisions are never live admissions.

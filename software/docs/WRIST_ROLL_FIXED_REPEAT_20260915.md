# Wrist-roll fixed-target repeat: results and next steps

## Outcome

Completed the planned four commands, increasing/decreasing/increasing/decreasing,
through the wizard's owned native path. Each was separately admitted after fresh
feedback. Each export was independently reconstructed before another movement.
There were no retries, extra positioning movements, compensation, or return moves.
The original relative v16 profile remains unchanged; v17 binds fixed raw targets.

| Matched direction | Raw command (degrees) | Reported final (both trials) | Signed error (degrees) | Reported spread |
| --- | ---: | ---: | ---: | ---: |
| Increasing | +0.912109363 | +0.703124983 | -0.208984380 | 0 |
| Decreasing | -0.296875017 | +0.087890637 | +0.384765655 | 0 |

Both pairs matched actual six-joint starting values, raw command, speed 20,
acceleration 1, source, controller/protocol, configuration, tool and workcell.
Per-trial runtime registration hashes differ because staging paths are unique;
their originals are individually verified, not assumed byte-identical.
The original v16 trials are context only and are excluded from this pair screen.

All four trials captured 281 post-command pose samples. Each sent exactly one
complete command (64 bytes increasing; 65 decreasing), without write uncertainty.
All five other joints reported zero drift. All handles closed, no I/O remained
pending, and cleanup stayed within budget. Selected baseline sample ages at
dispatch were 156, 125, 140 and 141 ms (host observation times, not verified device
sample ages). Reported quiet-entry bounds after write were respectively 313–344,
344–360, 297–313 and 328–344 ms. These are not precise physical settling times.

Roll command count is now six including the two earlier v16 probes. Base remains
44. Final reported pose [b,s,e,t,r,g] in radians:

```text
[0.007669904, 0, 1.593806039, 0.047553404, 0.001533981, 3.149262558]
```

## Reproducible evidence

Machine-readable results, report hashes, command bytes accounting, original
references, full starting/final poses and endpoint diagnostics are in
`software/runs/WRIST_ROLL_FIXED_REPEAT_20260915.json`.

In order, the original export directories under `software/runs/wizard-exports/`:

1. `campaign-24dd1038334743dfb570705d0707069d`
2. `campaign-ebf4113d3221479ab8db7c1a4e290414`
3. `campaign-d1cc3f8a7eb24cb1ac779e74f494e6ce`
4. `campaign-3f8bd7e08cbe4d54ab8a7291c536431f`

From the workspace root, reconstruct the pinned originals without opening hardware:

```powershell
.\.venv\Scripts\python.exe software/scripts/review_roll_fixed_repeat_20260915.py
```

The reader refuses substituted reports, duplicate trials, mismatched starts,
commands or context, incomplete reconstruction and failed cleanup. It includes
all four preselected trials; it does not select favorable observations or fit a
model. Tests cover matched scoring and eight mismatch cases.

Software validation: 135 focused profile/native/package/wizard/export tests passed
(`software/runs/roll-fixed-regression-20260915.xml`), plus nine offline reviewer
tests. No source edits occurred during the four live campaigns.

## Interpretation and next bounded experiment

This small screen shows reproducible controller-reported bias at these two
commands and measured starts. Zero reported spread does not mean zero physical
error: encoder resolution, mechanics and unmeasured tool position remain relevant.
The existing 0.5-degree acceptance band was not widened. Passing that band does
not mean exact endpoint placement. No general roll correction is ready yet.

Next work:

1. Define a small enumerated set of additional roll command points within the
   already bounded roll envelope, with explicit measured starts and finite routes.
   Keep speed, acceleration and payload fixed. Preview and simulate every route.
2. Test intermediate destinations approached from both sides where feasible;
   include any positioning moves in the declared budget, but label them separately
   from measurements. Stop on a failed endpoint or an unmatched next start.
3. Collect repeated originals at each point. Preserve misses and direction/start
   context; do not pool base, pitch or unmatched roll samples.
4. Compare a no-correction baseline against simple direction-conditioned local
   offset and linear inverse candidates. Use multiple input points before fitting
   a slope; do not infer a general gain from these two directional observations.
5. Freeze the chosen candidate and evaluate it on separately collected, held-out
   targets with matched uncorrected controls. Enable it only in the tested domain
   if error improves without worse drift, settling or failures.
6. Validate Cartesian tip accuracy separately once camera/board mapping is ready.

These next steps are preparation, not additional live movement in this run.

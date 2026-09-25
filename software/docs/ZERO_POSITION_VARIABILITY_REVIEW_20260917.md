# Zero-position variability: original feedback review

Offline review of three complete zero-command trials; no robot queries, movement,
model fitting or setting changes. Each export passed manifest verification and
original endpoint/unchanged-hold replay. Commands and all six reported baseline
angles match exactly. Command: T101, joint 5, rad 0, speed 20, acceleration 1.

| Trial | Baseline raw tR | Endpoint trajectory (deg) | Final / full hold (deg) | Hold raw tR | Hold samples |
| --- | ---: | --- | ---: | ---: | ---: |
| Earlier reverse-order zero | 0 | 0.351563 → 0.263672 → 0.263672 | 0.263672 | -20 | 116 |
| Balanced block zero 1 | -20 | 0.439453 → 0.263672 → 0.263672 → 0.263672 | 0.263672 | -20 | 115 |
| Balanced block zero 2 | -20 | 0.439453 → 0.439453 → 0.439453 | 0.439453 | -28 | 117 |

The two recent baseline raw-field sets also match: tB=13, tS=9, tE=65, tT=29,
tR=-20. The same canonical command payload hash occurs in all three trials.
No engineering units or physical interpretation are assigned to these raw fields.

## Timing and persistence

The first recent trial reports 0.439453 at 0.288383 seconds after dispatch and
0.263672 by 0.609829 seconds. The second reports 0.439453 at 0.308757, 0.616209
and 0.906367 seconds, then retains it throughout a 34.826824-second response span.
The second result is therefore not explained by merely having observed the same
trajectory earlier. The earlier settling decision did not conceal a later change
within the recorded hold. Continuous physical state between samples is unknown.

All three holds have zero reported six-joint span and maximum response gaps around
417–420 ms. The two recent baseline ages at dispatch were 9.1752 and 8.5232 ms;
HTTP receipt durations were 55.9521 and 53.3232 ms. These are host timings, not
physical movement-duration measurements. No transport failure is recorded here.

## Preceding history and limits

Balanced zero 2 is linked by the verified session journal to the preceding 0.95
descending lookup. That lookup reported 1.230468748 degrees with a complete stable
hold and raw tR=-20. Zero dispatch followed its final hold response by 20.886138 s.
Balanced zero 1 is the first leg, so it has no in-session predecessor; the review
does not infer an uninterrupted history from nearby filenames. The older trial's
predecessor is not established by this review.

The endpoint difference is 0.175781274 degrees despite identical command and
reported starting pose. Raw tR differs after the move and tracks the differing
endpoint in this small sample, but identical baseline tR did not predict which
endpoint occurred. It is not evidence for a tR-based pre-command compensation rule.
Hidden mechanical/control state and prior history remain possible explanations,
not identified causes. Neither torque, temperature nor millimeter accuracy is
established by these reports.

## Practical next step

Do not revise an offset from these three cases. A useful next experiment would
standardize an explicitly recorded predecessor and hold before every zero probe,
predeclare a small finite trial count, and retain full trajectory/raw-field data.
Compare endpoints and complete holds rather than extending settling time alone:
the differing endpoint already persisted for the full existing observation window.
Any such live test needs the existing fresh admission and unchanged limits; this
review sends nothing and grants no new motion authority.

## Reproduce

```powershell
.venv\Scripts\python.exe software/scripts/review_zero_variability.py
```

Optional `--output` creates a new JSON file exclusively, refusing overwrites.
Saved analysis: `software/runs/wizard-exports/zero-variability-review-20260917.json`.
It retains export/manifest references, original-body-checked raw fields, relative
feedback timing and the verified predecessor link. Original exports are unchanged.

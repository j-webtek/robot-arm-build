# Updated cross-session and approach-direction comparison

Latest update: the complete balanced block is included in the 40-export analysis
below. The original 32-export analysis is retained afterward for provenance.

## Complete balanced-block update

`--include-balanced` now includes all eight exports from session
`86b99f6aa91c4e0b800ad17ac13945b9`, in addition to the recent cohorts. It verifies
the journal chain against the frozen final hash, session identity, ordered distinct
leg references and completed eight-leg finish, then matches each referenced
manifest hash to its independently replayed export. Records retain comparison
session ID, leg index, predecessor reference and measured dispatch interval.

Updated totals: 40 unique exports, 38 fully validated endpoint/unchanged-hold
records, two retained failures, ten exact full-baseline groups and seven direction
groups. Earlier incomplete/uncertain records remain excluded from endpoint ranges
but present in the report. No saved source exports or compensation settings changed.

| Approach / command | Desired | Complete | Endpoint range (deg) | Within illustrative +/-0.05 deg |
| --- | ---: | ---: | --- | ---: |
| Ascending / 1.25 | 1.25 | 4 | 1.230468748 | 4/4 |
| Descending / 1.25 | 1.25 | 5 | 1.494140602 | 0/5 |
| Descending corrected / 0.95 | 1.25 | 12 | 1.230468748–1.406250023 | 10/12 |
| Descending probe / 1.05 | 1.25 | 4 | 1.230468748–1.406250023 | 2/4 |
| Descending probe / 0.85 | 1.25 | 2 | 1.142578111 | 0/2 |
| Zero positioning / 0 | 0 | 3 | 0.263671854–0.439453128 | 0/3 |
| High positioning / 2.5 | 2.5 | 8 | 2.285156222 | 0/8 |

These selected descriptive counts are not statistical reliability estimates.
The balanced block adds local successes without reducing the historical worst
observed corrected error (0.156250023 degrees). It does not qualify a global model.

### Identical-baseline zero variability

All three zero-positioning records have the same full reported six-joint baseline,
same command, speed 20 and acceleration 1. Their endpoint span is 0.175781274
degrees. Thus this variation is not explained by a difference in the recorded
initial joint angles or command parameters. It does not identify the mechanical
cause: prior paths, elapsed time and unmeasured internal state remain different.

The two new ascending probes reach the same endpoint despite different starting
rolls (0.263671854 and 0.439453128), so they belong in separate exact-baseline
groups even though they share a broader direction group. Do not erase this
distinction by averaging starting poses or claiming fully matched repetitions.

### Next investigation

Retain the experimental local mapping and its uncertainty; do not refit an offset
from the latest successful block. Before another live campaign, compare the zero
records' full feedback trajectories and preceding action/hold history, using the
existing original exports and journal links. Compare controller raw fields only
as raw fields unless engineering units are verified. This can identify recorded
differences worth controlling, but cannot establish causation or physical accuracy.
The optional 0.90-degree micro-correction remains hardware-untested.

Reproduce:

```powershell
.venv\Scripts\python.exe software/scripts/review_cross_session_roll.py --include-balanced
```

Saved report:
`software/runs/wizard-exports/cross-session-roll-with-balanced-20260917.json`.
The prior 25- and 32-export modes remain available unchanged. Forty-two offline
tests passed, including changed journal bytes, wrong session/order/hash, duplicate
leg IDs and incomplete finish rejection. No hardware commands were sent.

## Result

Replayed 32 unique selected exports, including the first live micro-workflow
predecessor and positioning move, reverse-order controls, and an earlier ascending
control. Thirty passed full endpoint plus unchanged-hold replay. Two failures are
retained separately: an uncertain command outcome and an incomplete hold. No
hardware access, coefficient fitting, calibration change or new motion occurred.

Original response replay and manifest checks—not copied Markdown numbers—produced
the comparison. Nine exact command/desired/full-baseline groups are retained.
Seven broader direction groups retain command, desired angle, speed, acceleration
and other-joint baseline, while explicitly listing differing starting roll angles.
This is a selected documented cohort, not all project history.

## Same desired endpoint: 1.25 degrees

| Approach | Command (deg) | Complete trials | Reported endpoint range (deg) | Within illustrative +/-0.05 deg |
| --- | ---: | ---: | --- | ---: |
| Ascending | 1.25 | 2 | 1.230468748 | 2/2 |
| Descending, uncorrected | 1.25 | 5 | 1.494140602 | 0/5 |
| Descending, local correction | 0.95 | 10 | 1.230468748–1.406250023 | 8/10 |
| Descending, spacing probe | 1.05 | 4 | 1.230468748–1.406250023 | 2/4 |
| Descending, spacing probe | 0.85 | 2 | 1.142578111 | 0/2 |

These fractions describe this selected sample; they are not reliability estimates
or independent trials. Training, probe, held-out and first-workflow provenance is
retained in record cohort labels and must not be conflated in model evaluation.
Session IDs describe software export sessions, not independent mechanical setups.

The latest 0.95-degree trial adds another 1.230468748 endpoint but does not remove
the prior 1.406250023 outcomes. Its maximum observed absolute desired error remains
0.156250023 degrees, versus 0.244140602 for the selected descending uncorrected
controls. This is a descriptive difference, not a paired causal improvement claim.
The 1.05-degree alternative offers no evidence here of a tighter endpoint range.

Stable telemetry does not imply exact physical position. Direction, travel,
preceding path, elapsed hold and unmeasured mechanics remain confounded. There is
no independent tip-position measurement and no millimeter-accuracy conclusion.

## Consequences for further testing

1. Keep the 0.95 local command experimental and direction-specific. Do not fit a
   global offset or promote it across joints, speeds or targets from these data.
2. Keep 1.25 ascending as a separate reference; do not apply the descending
   correction to it. Record commanded, desired and reported values independently.
3. Use the existing finite coordinator when an eligible out-of-band predecessor
   occurs in a planned trial. Its optional 0.90 command is still hardware-untested.
   Do not repeat trials solely until an out-of-band endpoint appears.
4. For the next physical comparison, predeclare a small balanced sequence and
   fixed holds before starting; include failures and late changes. Use fresh
   baseline/one-use admission for every leg. Stop on failed evidence; do not retry
   to replace an unfavorable result. This document itself authorizes no dispatch.
5. Evaluate any new mapping on separately reserved validation trials. Report the
   endpoint range and failures, not just average error or the latest success.

## Reproduce and inspect

```powershell
.venv\Scripts\python.exe software/scripts/review_cross_session_roll.py --include-recent
```

Add `--output` with a new filename to save another JSON report; existing output
files are never overwritten. The original default 25-export cohort remains
available without `--include-recent`.

Saved report:
`software/runs/wizard-exports/cross-session-roll-with-first-micro-20260917.json`.
It contains source manifest hashes, cohort labels, export session IDs, exact
baseline groups, direction groups and hypothetical correction-policy decisions.
The hypothetical direct-correction replay does not evaluate or authorize the
separate native micro-command mode.

Validation: 35 offline grouping, policy and original-export replay tests passed.
No retained hardware exports were modified.

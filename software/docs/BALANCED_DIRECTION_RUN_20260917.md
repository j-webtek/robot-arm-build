# Predeclared balanced direction comparison

## Frozen protocol before dispatch

Eight single-command legs, in exactly this order:

1. Zero positioning: command/desired 0 degrees.
2. A1 ascending control: command/desired 1.25 degrees.
3. High positioning: command/desired 2.5 degrees.
4. B1 descending frozen lookup: command 0.95, desired 1.25 degrees.
5. High positioning: command/desired 2.5 degrees.
6. B2 descending frozen lookup: command 0.95, desired 1.25 degrees.
7. Zero positioning: command/desired 0 degrees.
8. A2 ascending control: command/desired 1.25 degrees.

Existing joint-5 T101 actions, speed 20, acceleration 1; unchanged one-use
admission, fresh baseline, joint limits, endpoint and 35-second passive hold.
Existing scheduler targets dispatch 20 seconds after previous hold completion,
with its unchanged 18–22-second experimental comparability window. Every export
must pass original-response replay before progression. Predecessor final pose
must equal the next fresh six-joint baseline. No retry, repair, automatic return,
micro-correction, refit or promotion of compensation. Stop at the first failure.

Outcome criteria: compare all four probe endpoints against desired 1.25 and the
illustrative +/-0.05-degree band, retaining failed legs separately. Report each
endpoint and range, not only an average. This small balanced-order sample does
not isolate approach direction from starting angle/travel/history and cannot
establish physical-tip accuracy or independent reliability.

Runner: `software/scripts/run_controlled_roll_comparison.py --live-balanced-directions`.
Default invocation is inert. Each live leg uses the existing wizard service and
assigned workspace exports. The session journal is hash-linked and non-resumable.
Standing user bench/power/clearance conditions apply; local process inventory
cannot prove absence of an external controller. No limits are relaxed for this run.

## Results

Completed all eight legs, one command each, no retries or failures. Session
`86b99f6aa91c4e0b800ad17ac13945b9`; 62 focused scheduler/adapter/reviewer tests
passed before dispatch. All eight original-response replays passed again after
completion. The 34-record journal hash chain verified, ending in COMPLETED with
final hash `edb6dc46db55beeef5daa7274e9a4b47dc72421ffbbafec4824d1a5c3ade1646`.

| Leg | Command | Reported start | Reported endpoint | Error vs desired | Hold readings |
| --- | ---: | ---: | ---: | ---: | ---: |
| Zero positioning 1 | 0 | 1.230469 | 0.263672 | +0.263672 | 115 |
| A1 ascending control | 1.25 | 0.263672 | 1.230469 | -0.019531 | 118 |
| High positioning 1 | 2.5 | 1.230469 | 2.285156 | -0.214844 | 120 |
| B1 descending lookup | 0.95 | 2.285156 | 1.230469 | -0.019531 | 120 |
| High positioning 2 | 2.5 | 1.230469 | 2.285156 | -0.214844 | 118 |
| B2 descending lookup | 0.95 | 2.285156 | 1.230469 | -0.019531 | 119 |
| Zero positioning 2 | 0 | 1.230469 | 0.439453 | +0.439453 | 117 |
| A2 ascending control | 1.25 | 0.439453 | 1.230469 | -0.019531 | 119 |

Angles are degrees from controller telemetry. All six joint reports stayed
unchanged within each hold. Total hold readings: 946. Response spans:
34.743080–34.994231 seconds; largest gap across holds: 428.028 ms. Actual dispatch
intervals after preceding hold completion: 20.886138–20.947613 seconds.

All four probes ended at 1.230468748 degrees, within the illustrative +/-0.05 band
around 1.25. Within this run the ascending and corrected descending endpoints
matched exactly at controller reporting resolution. This is useful local evidence,
not a general guarantee: previous descending lookup endpoints at 1.406250023
remain part of the history and are not invalidated by this successful block.

Important variability: identical zero commands from the same reported starting
roll produced 0.263671854 and 0.439453128 degrees. Both passed the unchanged broad
0.5-degree arrival check, but neither is an accurate zero within the illustrative
narrow band. A1 and A2 therefore had different starting angles; do not describe
them as exactly baseline-matched. The final A2 still reached the same endpoint.
No model or candidate was updated to hide this variation.

## Original exports, in execution order

Under `software/runs/wizard-exports/`:

1. `wizard-20260917T115329625195Z-443e8a3260834658af22778859f4f70e`
2. `wizard-20260917T115427541537Z-30b505c62213410997a31a13f5130b28`
3. `wizard-20260917T115525636363Z-cd4ba042006c4e848186bbf398237be5`
4. `wizard-20260917T115623683196Z-a47e36dca5de436c97ee3115a50786e0`
5. `wizard-20260917T115721503001Z-eed66b0d65664866a1ce88f97d5b8d87`
6. `wizard-20260917T115819420752Z-21a775031e8f47758709eac84db45535`
7. `wizard-20260917T115916898649Z-ca21b67e6f5e4cfa83076736434949ee`
8. `wizard-20260917T120014798338Z-f51855e3a02a459c8e42783d8b47f66b`

Journal files share prefix `comparison-86b99f6aa91c4e0b800ad17ac13945b9-`.
Each LEG_VERIFIED event retains its export manifest hash and predecessor link.
Saved evidence is not permission to resume or dispatch another movement.

## Next useful step

Completed: all eight legs are now included in the frozen-journal-verified
40-export replay; see `ROLL_COMPENSATION_GENERALIZATION_20260917.md`. The
same-baseline zero span remains 0.175781274 degrees and is retained explicitly.

Add this entire block to the offline cross-session comparison, including both
zero-positioning outcomes, and quantify approach-distance/history differences
before choosing another physical experiment. The optional micro-correction is
still hardware-untested and was not part of this block. Final reported roll is
1.230468748 degrees; any future movement requires fresh feedback/admission.

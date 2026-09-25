# Frozen lookup repeat and opposite-direction control

Three explicit, individually verified movement actions completed. Each used a
fresh baseline, one command and a separate passive hold. Before advancing,
export integrity, original feedback replay and unchanged-hold checks passed.
No live policy, speed, compensation coefficient or candidate file was changed.

## Results (controller joint degrees)

| Action | Start | Command | Desired | Initial and final hold | Error vs desired |
| --- | ---: | ---: | ---: | ---: | ---: |
| Frozen descending lookup | 2.285156222 | 1.25 | 1.50 | 1.494140602 | -0.005859398 |
| Zero positioning | 1.494140602 | 0 | 0 | 0.263671854 | +0.263671854 |
| Ascending control | 0.263671854 | 1.25 | 1.25 | 1.230468748 | -0.019531252 |

All six joints were unchanged throughout each hold. Lookup: 116 responses,
35.012066 seconds response span, maximum gap 396.7534 ms. Zero positioning:
114 responses, 34.710384 seconds, maximum gap 423.0245 ms. Ascending control:
116 responses, 34.922011 seconds, maximum gap 392.1830 ms.

The lookup and ascending control each passed the illustrative +/-0.05 and
+/-0.10-degree sampled bands for 30 seconds **against their respective desired
angles**. These are not adopted requirements or Cartesian accuracy measurements.

## What the comparison means

The same wire command, 1.25 degrees at speed 20 / acceleration 1, produced
1.494140602 descending and 1.230468748 ascending: a 0.263671854-degree difference.
Compare raw endpoints, not errors relative to different desired targets.
Relative to the common command, errors were +0.244140602 and -0.019531252 degrees.
The desired-angle field is a host verification reference, not an additional
angle transmitted to the controller.

This supports retaining approach direction in a local response model. It does
not isolate a mechanical cause: starting angle, motion distance, prior path and
elapsed holding time were not identical. Only one new pair was collected.
Do not fit a global offset or extrapolate to other joints from this comparison.

## Lookup evidence update

There are now three completed held-out lookup trials and one separately retained
incomplete connection-reset attempt. Initial arrival passed in all three completed
trials; exactly unchanged holds passed in two. Final hold endpoints now span
1.406250023 to 1.494140602 degrees. One of three completed trials meets the
illustrative +/-0.05-degree full-window criterion; all three meet +/-0.10.
This sample is too small to treat these fractions as reliability guarantees.

The prior reset remains uncertain. This was a new reservation and fresh baseline,
not a retransmission of its consumed command. The successful new exchange does
not establish the cause or resolution of the reset.

## Evidence

Directories under `software/runs/wizard-exports/`:

- Lookup: `wizard-20260917T022838535576Z-e23657af7df24a7cbdafdfa665a8d841`
  manifest SHA-256 `ba734e76398cf9804941a671ef6648c333d49431877a336f2b7f9957c715d9b3`.
- Zero: `wizard-20260917T022934085802Z-42258b9400a94fc9ae385a66b5b762c3`
  manifest SHA-256 `ea99b6776cad851030e710ae5328de9016d97db34b3116aafa67afae9a33accd`.
- Ascending: `wizard-20260917T023026790706Z-152ba4ea102e4a7097c1cee0eb2ae37a`
  manifest SHA-256 `43dbd6e0e6671c692de0ef924086190800decc99c511c68348d9c9b4ecdb23db`.

## Next bounded comparison

Keep candidate disabled. Repeat the common-command comparison in reverse order
using the existing zero/center_up and high/center_down actions, checking each
positioning leg and hold before the next. Use uncorrected desired 1.25 for both
directions so verification references match; keep lookup validation separate.
Retain late changes and connection failures rather than discarding failed trials.
Compare initial and hold-final endpoints across repetitions before refitting.

Last reported roll: 1.230468748 degrees. This is historical, not authority for
the next movement; obtain a fresh baseline. No return or corrective movement sent.

## Reverse-order comparison completed

The next session executed zero, center_up, high, center_down using the existing
single-use wizard actions. Each leg passed original endpoint replay and a full
unchanged hold before progression. All commands used speed 20 and acceleration 1.
Both control legs used command AND desired endpoint 1.25 degrees, with no
compensation. No command was retried and no live software/policy was changed.

| Leg | Fresh start (deg) | Command | Hold final | Hold samples | Response span (s) | Max gap (ms) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Zero positioning | 1.230468748 | 0 | 0.263671854 | 116 | 34.815521 | 418.107 |
| Ascending control | 0.263671854 | 1.25 | 1.230468748 | 114 | 34.867242 | 480.538 |
| High positioning | 1.230468748 | 2.5 | 2.285156222 | 115 | 34.866988 | 386.186 |
| Descending control | 2.285156222 | 1.25 | 1.494140602 | 115 | 35.048537 | 396.303 |

All six joints remained unchanged within each hold, including relative to its
initial verified endpoint. Export IDs and hashes are recorded in
`ROLL_REVERSE_ORDER_EVIDENCE.json` and independently checked against all four
original exports. These uncorrected controls do not add held-out lookup trials.

The 0.263671854-degree descending-minus-ascending difference reproduced the
preceding opposite-order comparison. The ascending endpoint error was
-0.019531252 degrees; descending was +0.244140602 degrees. Thus the ascending
control meets both illustrative narrow bands, while descending meets neither
against desired 1.25, despite passing the broader operational arrival check.
Stable does not mean accurate against a narrow target.

Two recent comparisons are descriptive evidence, not statistical qualification.
Different approach distances and mechanical histories remain confounders; older
trials also show variability. Keep direction-conditioned compensation local and
disabled globally, rather than fitting a single new global offset.

### Next useful experiment

Use the existing frozen **1.25-degree desired** lookup (descending command 0.95)
after a verified high positioning leg. Compare its held endpoint against the
recent ascending uncorrected 1.25-degree control, now using the same desired
endpoint for both. This tests whether the existing directional command choice
reduces the discrepancy without refitting. Do not confuse this with the separate
1.50-degree desired / 1.25-command lookup. Stop on any failed check, retain all
results and obtain a fresh baseline for each leg.

Latest reported roll is 1.494140602 degrees. No final return movement was sent.

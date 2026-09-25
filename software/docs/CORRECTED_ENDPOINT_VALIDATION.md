# Corrected endpoint validation

## Implemented September 16, 2026

The discrete transaction and durable Wi-Fi reservation now accept an optional
`desired_endpoint` in radians, separately from `target`, the exact commanded
angle. Without the optional argument, existing v1 snapshots and decisions remain
unchanged. Corrected transactions, reservation records and verifier results use
v2 schemas and retain both values for reconstruction.

- Arrival error, three consecutive samples and settling dwell use the desired
  endpoint.
- Excursion bounds use the baseline and exact commanded angle, with the existing
  0.5-degree allowance. They do not expand to include the desired endpoint.
- The existing command limits remain: roll only, step greater than 0.5 and at most
  1.5 degrees, absolute command within 3 degrees, speed 20, acceleration 1.
- An explicit desired endpoint must be finite, within 3 degrees, on the same side
  of the baseline as the command, and within 0.5 degrees of the command.
- Other-joint drift, timing, one-use dispatch and no-retry behavior are unchanged.
- Durable reservation bytes include the desired endpoint before dispatch; their
  hash remains bound to the consumption record.

These changes provide measurement semantics, not a validated compensation model.
The initial software-only change was followed by the held-out physical trials
below. The frozen candidate remains globally disabled; two explicit native wizard
experiment actions now load it only after checking its pinned SHA-256. It is not
applied to ordinary movement commands.

## Next bounded hardware experiment

1. Add explicit held-out trial actions for the frozen candidate, recording its
   identity/hash, approach direction, desired angle and exact command. Do not add
   arbitrary corrected-angle input or enable global compensation.
2. Preview the exact trial. Obtain a fresh baseline and enforce existing step,
   direction, identity and transport checks. Stop if positioning is out of bounds;
   do not invent a fallback path or widen limits.
3. Use desired 1.25 degrees and the frozen descending command
   1.049804687506479 degrees, or ascending command 1.3134765703183617 degrees.
   Positioning moves remain separate, verified uncorrected actions.
4. Collect separate post-command feedback, then a passive hold, and export the
   original responses. Command HTTP receipt must not count as endpoint evidence.
5. Independently reconstruct the v2 decision using `desired_endpoint_rad` for
   `target` and the transaction command's `rad` for `command_target`.
6. Compare signed and absolute errors against the saved uncorrected observations.
   Label these held-out trials; do not refit the candidate with these results.

One successful trial is not a qualification. A worse error is still useful
evidence and must be preserved. Joint telemetry does not establish external
tool-tip accuracy, millimeter accuracy, or validity for other joints/targets.

## First held-out pair completed September 16, 2026

Implemented explicit `run_wifi_roll_corrected_down_trial` and
`run_wifi_roll_corrected_up_trial` wizard actions, their inert previews, report
display and diagnostic publication. The bench script accepts `corrected_down`
and `corrected_up`. Candidate bytes are pinned to SHA-256
`cda559d3b575d0a4c755317621454cfafd73fbc1cb0b7efaed113cc8409567f0`.
A mismatch fails before hardware access. Candidate metadata in each report
records direction, command, desired endpoint, held-out status and no refitting.

130 focused tests passed; JavaScript syntax check passed. Tests include invalid
candidate rejection before hardware access, corrected approach/delta limits,
durable desired-endpoint binding and independent endpoint reconstruction.

Four individually admitted physical commands completed, with no retries:

| Leg | Command (degrees) | Desired endpoint | Reported final | Error vs desired |
| --- | ---: | ---: | ---: | ---: |
| Position high | 2.5 | 2.5 | 2.285156222 | -0.214843778 |
| Corrected descending | 1.049804688 | 1.25 | 1.230468748 | -0.019531252 |
| Position low | 0 | 0 | 0.263671854 | +0.263671854 |
| Corrected ascending | 1.313476570 | 1.25 | 1.230468748 | -0.019531252 |

Each corrected leg was followed by a roughly 35-second passive capture with 118
successful original responses and zero reported span on all six joints. Maximum
response gaps: descending 415.5733 ms; ascending 373.2185 ms. Both are below the
provisional one-second allowance. All four exports passed integrity verification;
original feedback reconstructed the endpoint decisions exactly, including v2
desired/command separation. Both holds matched their preceding final poses.

Exports under `software/runs/wizard-exports/`, in table order:

- `wizard-20260916T162808650093Z-5e1c95d127a24892811c8e9f1844d203`
  manifest SHA-256 `9df32b5de1c123739dac806166f58b8fbcb5cc50273ce074dd0eeb41e1d522a5`
- `wizard-20260916T162851627243Z-9ab48b693ef1445e99d417072979eeed`
  manifest SHA-256 `0306328d6f4d1c9470d03dea20e1f10ad2074d66aa2b0c27cbb2bf59f31b40ef`
- `wizard-20260916T162914682238Z-00c477db0b424e1a94695e5692e260b0`
  manifest SHA-256 `d851e77538ab23f8396e9dadbffb0c5bdbf1cb73b8ca544374594040f55bbcef`
- `wizard-20260916T163000528819Z-7c7971187b1445ea984d033ac4ed82da`
  manifest SHA-256 `2de99866d65441c20c9c3fc6ae83097a47907842731c004e40ef78f4ddd331c2`

The earlier uncorrected descending errors were +0.244140602 and +0.156250023
degrees; ascending errors were -0.107421889 and -0.019531252 degrees. The first
corrected pair is encouraging, especially descending, but is not a controlled
statistical qualification: only one held-out trial per direction, and ascending
matches the best previous uncorrected outcome. No broad accuracy claim follows.

The candidate JSON is intentionally unchanged: its zero-trial validation fields
describe the frozen training-time snapshot, not current experiment status. This
document and exported reports record subsequent validation evidence.

Next: repeat a finite pair in reversed direction order with the same frozen
candidate, retaining per-leg baselines and no automatic fallback. Compare
repeatability before considering any additional target or joint. Last reported
roll: 1.230468748 degrees; this saved value is not a substitute for a fresh baseline.

## Reverse-order held-out pair completed September 16, 2026

Repeated ascending first, then descending, with the identical frozen candidate.
Each of four separate command actions acquired its own fresh baseline and passed
endpoint verification. Each export was independently checked before advancing.
No retry, model refit, tolerance change or automatic return was performed.

| Leg | Command (degrees) | Desired endpoint | Reported final | Error vs desired |
| --- | ---: | ---: | ---: | ---: |
| Position low | 0 | 0 | 0.175781274 | +0.175781274 |
| Corrected ascending | 1.313476570 | 1.25 | 1.230468748 | -0.019531252 |
| Position high | 2.5 | 2.5 | 2.285156222 | -0.214843778 |
| Corrected descending | 1.049804688 | 1.25 | 1.230468748 | -0.019531252 |

Ascending hold: 117 original responses, response span 34.8130 seconds, maximum
response gap 402.5656 ms. Descending hold: 120 original responses, response span
35.0149 seconds, maximum gap 469.2822 ms. Both approximately 35-second captures
completed successfully; every joint retained its preceding final reported value.

All four export manifests verified, original feedback reconstructed the recorded
rows, and recomputed endpoint verdicts exactly matched the stored verdicts. For
corrected legs this included the separate desired and commanded angles. Passive
hold summaries also reconstructed exactly from their original responses.

Exports under `software/runs/wizard-exports/`, in table order:

- `wizard-20260916T163127101824Z-563329e1b57246e8886ca2418b462b32`
  manifest SHA-256 `b5220075f17cf32e45673adbe4187039fc55d644908680ed0365c27d0b63a1c6`
- `wizard-20260916T163234668940Z-d4397e26d47b4d6e87e48a7219a896d0`
  manifest SHA-256 `6065b7022b4a413c09cb0d63ad3fa3f5ed56b6242229d98598fe7f25be82b482`
- `wizard-20260916T163250452238Z-7932984f3ce84d9e8b678d8f0bf722b3`
  manifest SHA-256 `86279737981a95c1cc770fe81a1925149ee4883b54166b69e8368aede2d11b30`
- `wizard-20260916T163340795873Z-2e233f6cfe0844d4a83965197fcd2520`
  manifest SHA-256 `2cd5991541836532b8d94d355545e6779f193f13f87c6204392835802a189af4`

### Interpretation and next experiment

There are now four held-out corrected trials: two per direction. All returned
1.230468748 degrees, giving absolute desired-endpoint error 0.019531252 degrees
and zero observed endpoint spread in the reported values. This is limited
controller-resolution evidence, not proof of zero physical variation or a
millimeter-level accuracy result. The candidate remains globally disabled.

Next use a small, predeclared interleaved corrected/uncorrected control comparison
at the same 1.25-degree target, speed and acceleration. Compare each direction
separately and record actual starting positions and prior paths; do not assume
identical starting positions merely because the positioning commands match.
Retain the frozen candidate, unchanged bounds and stop-on-failure behavior. This
comparison should precede extending compensation to another target or joint.

No source code changed during this repeat; the prior software test result remains
130 passing focused tests. Four new live legs and two passive holds passed. Last
reported roll remains 1.230468748 degrees, requiring a fresh baseline next time.

## Interleaved control comparison completed September 16, 2026

Predeclared sequence: zero / uncorrected ascending / zero / corrected ascending /
high / corrected descending / high / uncorrected descending. Each slash denotes
a separate explicitly executed action, not a queued automatic sequence. The
candidate SHA-256 was unchanged. All eight movement endpoints verified, and all
eight diagnostic exports were independently verified before advancing. Four
target trials also completed approximately 35-second passive holds. No refit,
retry, command-limit change or tolerance change occurred.

### Target results

All desired endpoints below are 1.25 degrees. Starting positions are fresh
pre-command feedback, not inferred from the preceding positioning command.

| Approach | Correction | Actual start (deg) | Command (deg) | Final reported (deg) | Desired-endpoint error (deg) |
| --- | --- | ---: | ---: | ---: | ---: |
| Ascending | None | 0.351562491 | 1.25 | 1.230468748 | -0.019531252 |
| Ascending | Frozen | 0.439453128 | 1.313476570 | 1.230468748 | -0.019531252 |
| Descending | Frozen | 2.285156222 | 1.049804688 | 1.406250023 | +0.156250023 |
| Descending | None | 2.285156222 | 1.25 | 1.494140602 | +0.244140602 |

Positioning final readings, in sequence: 0.439453128, 0.439453128,
2.285156222, 2.285156222 degrees. The first zero-position final reading differed
from the following fresh baseline by approximately 0.087890637 degrees. This
difference is within existing limits but means the ascending starts were not
identical. No cause is established by these data.

Passive holds, in target-trial order:

| Trial | Successful originals | Response span (s) | Maximum response gap (ms) |
| --- | ---: | ---: | ---: |
| Uncorrected ascending | 117 | 34.9519 | 411.3609 |
| Corrected ascending | 116 | 34.6908 | 410.1826 |
| Corrected descending | 119 | 35.0414 | 387.9853 |
| Uncorrected descending | 119 | 34.9185 | 411.5409 |

Every hold retained exactly the preceding endpoint on all six reported joints.
Original response reconstruction, desired/command endpoint decisions, hold
summaries and export integrity all verified independently.

### Evidence exports

Under `software/runs/wizard-exports/`, in eight-leg execution order:

1. `wizard-20260916T163509724732Z-e07e9946b30f4f2a9bde769d9cdb75c7`
   manifest SHA-256 `793ee17016e89fc227e7b6702bb982908e93ed3e7a7ba400e5937cc5beb91bdf`
2. `wizard-20260916T163602650283Z-c5564d51b5fa4bbdab0996b6bab017ce`
   manifest SHA-256 `15bcaaebd61aa5c7e616a956d23e9980388fa6696bf9b8fe22e72d72325f3ee5`
3. `wizard-20260916T163619446277Z-3fe0bdc52c844af0811ac8cc92722d9d`
   manifest SHA-256 `27aafe05f86937df6febbdf99fd413bec47b0262377dd7086aa33e1a45ac20df`
4. `wizard-20260916T163706950910Z-377c8f8eae31422d9ba74b626e4fdecc`
   manifest SHA-256 `70884aab686204b6e1b6c27adc6cf5eb9970045a85de15b2d2de3be77c67a6bd`
5. `wizard-20260916T163721090258Z-fc3aeb64755641c0924985ebebeaca4f`
   manifest SHA-256 `a5b5fd4d1910729b9ab5bef0521f56333a0f794848cb8e47b84a9274cad143a7`
6. `wizard-20260916T163810017329Z-d10eaab718d149ffb21e4087e64556d2`
   manifest SHA-256 `6e3147ab47e3063e2db362e2e29be633094b1fc09cd7402cf851b2bc58c81dd1`
7. `wizard-20260916T163825622217Z-2e21add68d274dadbe0c40de8183c1ae`
   manifest SHA-256 `8b2a61e2e2cf75380519f0c84c86cab2533f831fc160f2000fdfa2a056a041d3`
8. `wizard-20260916T163915138808Z-3f95fd0039a74a61866a4aec423d8c66`
   manifest SHA-256 `b8c89cbc892ceeab3372e09c9d3c90194fb6cfe682a08931158b3dbe6dfe00f6`

### Updated conclusion and next step

The ascending pair showed no endpoint improvement. The descending pair showed
0.087890580 degrees less absolute error with correction, but the corrected result
was worse than earlier corrected trials. Across six held-out corrected trials,
five ended at 1.230468748 degrees and one at 1.406250023 degrees. The previous
zero-spread observation therefore no longer describes the full corrected sample.

Passing the 0.5-degree operational arrival criterion is distinct from proving
compensation accuracy or repeatability. Direction-only additive correction is
still an experimental local model; do not promote it globally or increase its
offset based on this single worse result. No physical millimeter claim is made.

Next standardize the positioning hold and record the pre-command stability window
and delay as well as the actual baseline. Repeat a finite counterbalanced control
pair using unchanged candidate values and thresholds. Separate endpoint success
from experimental eligibility if starting conditions differ. This reduces a
known comparison confound without asserting it caused the variation. Only then
consider extending the mapping to additional targets or joints.

No source code changed in this comparison; prior software tests were not rerun.
Last reported roll: 1.494140602 degrees. Always obtain a new baseline before any
next command, and retain the existing step limit even near its boundary.

## Matched-start descending pair with full positioning holds

Completed September 16, 2026. Sequence: high / uncorrected descending / high /
corrected descending. All four actions included the same approximately 35-second
passive observation procedure after endpoint verification, including positioning.
Each export was independently verified before the next action. No source changes,
refitting, retries or limit changes were made.

| Leg | Fresh start (deg) | Command (deg) | Desired endpoint | Final reported | Error vs desired |
| --- | ---: | ---: | ---: | ---: | ---: |
| Position high | 1.494140602 | 2.5 | 2.5 | 2.285156222 | -0.214843778 |
| Uncorrected descending | 2.285156222 | 1.25 | 1.25 | 1.494140602 | +0.244140602 |
| Position high | 1.494140602 | 2.5 | 2.5 | 2.285156222 | -0.214843778 |
| Corrected descending | 2.285156222 | 1.049804688 | 1.25 | 1.406250023 | +0.156250023 |

Both preceding positioning baselines matched on all six joints, and both target
trial baselines matched on all six joints. Each fresh target baseline matched
the preceding positioning hold's final six-joint pose. This makes the local
comparison better matched than the prior ascending comparison; it does not
establish identical unobserved mechanical or thermal conditions.

All four holds had zero reported span on every joint and matched the corresponding
movement endpoint. Original responses reconstructed every recorded verdict and
hold summary, and all export manifests verified.

| Hold after | Original responses | Response span (s) | Maximum gap (ms) |
| --- | ---: | ---: | ---: |
| First positioning | 118 | 35.0058 | 423.4685 |
| Uncorrected target | 116 | 34.8292 | 506.0790 |
| Second positioning | 117 | 34.8997 | 419.3833 |
| Corrected target | 118 | 35.0205 | 410.0366 |

The elapsed time from positioning hold's final response to target dispatch was
11.2918158 seconds uncorrected and 15.8820899 seconds corrected. These delays
include export review and were recorded, not controlled to be identical. Fresh
baseline ages at dispatch were respectively 17.2048 and 17.4116 milliseconds.
The passive hold windows therefore were standardized approximately, not every
aspect of the inter-command timing.

Exports under `software/runs/wizard-exports/`, in execution order:

1. `wizard-20260916T164134893829Z-23395531293e4eb3a7c6a6becbe847f7`
   manifest SHA-256 `0b9e22ab17401aa94ebabff0c70ded62176467f1e5829468eaf33aed87e1f70e`
2. `wizard-20260916T164223167342Z-5a842000031f4f1ab2de6121f7eadb3b`
   manifest SHA-256 `a84f868c7f70f74ae84038dafec6a87c02c828d768391e1abaf897c591207ad1`
3. `wizard-20260916T164311381873Z-0fbaf6932ab748c2aa50971fbecb1edc`
   manifest SHA-256 `84745ed4126fa97d0b5287d4ee2fa7af82cf0f8162d17f0124ec72dba242a981`
4. `wizard-20260916T164404309788Z-4d2c629b844b49fe9b22665fc7ba0589`
   manifest SHA-256 `50ae6f9e094e266e5a2d22e24e6748bf4b09389ed66b17bc8129d5acd19f84a0`

### Interpretation

The corrected descending error was smaller by 0.087890580 degrees, reproducing
the preceding interleaved pair despite reversing corrected/uncorrected order and
adding full positioning holds. The longer holds did not recover the earlier
1.230468748-degree corrected outcome. This does not prove the cause of the
remaining error. The current sample now contains seven corrected held-out trials:
five at 1.230468748 degrees and two at 1.406250023 degrees.

Next characterize the local commanded-angle versus reported-endpoint response
with a small predeclared descending command probe around the existing correction,
using the same high positioning target, full holds, speed and acceleration.
Before implementation, freeze the probe values and order, preserve the existing
delta limits and separate operational arrival from experimental comparison.
Keep candidate validation data distinct from any new model-training data. Do not
increase compensation automatically or extrapolate to other joints from this pair.

Last reported roll: 1.406250023 degrees. All four physical legs and four passive
holds passed. No software tests rerun because no source changed; all findings
remain controller-reported joint evidence, not external Cartesian accuracy.

The next characterization step is implemented and its first two probes completed;
see [Local roll response probe](LOCAL_ROLL_RESPONSE_PROBE.md) for the frozen
protocol, measured results, exports and repeat plan. These new probe samples are
not added to the frozen candidate's held-out validation count.

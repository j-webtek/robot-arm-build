# Adjacent roll target characterization: desired 1.50 degrees

Status: implemented and initial two-trial characterization completed. The existing
1.25-degree lookup remains disabled globally and must not be applied here.

## Why this next step

The 1.25-degree mapping has two encouraging held-out lookup results but is local
to one approach, speed and starting pose. Measure an adjacent uncorrected target
before adding another mapping entry. Reusing the 0.30-degree offset would assume
the very transfer behavior this experiment needs to measure.

## Finite protocol

1. Implement an explicit descending characterization action: command and desired
   endpoint both 1.50 degrees, speed 20, acceleration 1. Label it characterization,
   not validation of the existing candidate. No arbitrary target field.
2. Test direction checks, existing command delta limits, inert preview, diagnostic
   publication and independent original-feedback reconstruction before live use.
3. Predeclared live order: high positioning / 1.50-degree target / high positioning /
   1.50-degree repeat. Execute separately and verify each export before advancing.
4. Include the full approximately 35-second passive hold after every leg. Capture
   actual six-joint baselines, timing and any differences in preceding history.
5. Keep the current absolute roll limit, delta greater than 0.5 and at most 1.5
   degrees, arrival tolerance, dwell, feedback deadlines and one-use admission.
   Stop if a fresh positioning delta falls outside these bounds; do not force a
   fallback path or weaken the check to complete the experiment.
6. A timeout, reset, identity mismatch, excursion, incomplete hold or invalid
   export ends the sequence. Preserve uncertain commands; do not replay them.

## Analysis and decision

Reconstruct desired-endpoint error from original feedback, compare the two
uncorrected results and report signed error and reported spread. Keep operational
arrival success separate from suitability for a new mapping. This protocol makes
no change to existing candidates and sends no contact, typing or Cartesian motion.

If the two samples support further characterization, predeclare bounded probe
commands around this new target before sampling them. Any selected correction
needs its own frozen candidate and later held-out trials. Do not fit on validation
data, extrapolate to other joints, or call controller telemetry physical millimeter
accuracy. A failed or inconsistent result is retained, not excluded as an outlier.

## Offline evidence workflow

`software/scripts/review_wifi_roll_export.py` accepts one or more saved export
directories and prints JSON without opening hardware. It checks manifest
integrity, reconstructs successful endpoint decisions and holds from originals,
and reports uncertain transactions separately without granting arrival status.
The tool intentionally rejects successful exports without the protocol's hold.

Current scoped record: `ROLL_LOCAL_MAPPING_EVIDENCE.json`. Detailed history:
`ROLL_LOOKUP_VALIDATION.md`. Both are evidence only, not motion admission.

## Implementation and first two trials

Added explicit `run_wifi_roll_adjacent_trial` wizard action, preview, report
publication/display and `adjacent` bench-script option. The action commands and
evaluates 1.50 degrees with characterization metadata and no correction candidate.
It uses the existing one-use reservation, delta/direction bounds, independent
post-command feedback and full-hold workflow. 160 focused tests and JavaScript
syntax checking passed before hardware execution.

Completed September 16 local / September 17 UTC:

| Leg | Fresh roll start (deg) | Command/desired (deg) | Reported final (deg) | Error (deg) |
| --- | ---: | ---: | ---: | ---: |
| Position high | 1.494140602 | 2.5 | 2.285156222 | -0.214843778 |
| Adjacent target | 2.285156222 | 1.5 | 1.757812514 | +0.257812514 |
| Position high | 1.757812514 | 2.5 | 2.285156222 | -0.214843778 |
| Adjacent repeat | 2.285156222 | 1.5 | 1.757812514 | +0.257812514 |

The two target baselines matched on all six reported joints and each matched the
preceding positioning hold's endpoint. Positioning origins differed, so prior
path histories were not identical. Hold-end-to-target-dispatch intervals were
16.2194282 and 15.2324972 seconds; fresh baseline ages at dispatch were 8.7170 and
16.5874 ms respectively.

All four full passive holds completed and retained their preceding endpoint on
every reported joint:

| Hold after | Successful originals | Response span (s) | Maximum gap (ms) |
| --- | ---: | ---: | ---: |
| First positioning | 114 | 34.6989 | 469.0725 |
| First target | 116 | 34.7906 | 721.2289 |
| Second positioning | 118 | 34.9508 | 671.5789 |
| Second target | 116 | 34.9099 | 618.5991 |

The larger response gaps remain in the evidence; deadlines were not relaxed.
Every movement and hold was independently reconstructed with
`review_wifi_roll_export.py`, and each export verified before the next command.

Exports under `software/runs/wizard-exports/`, in execution order:

1. `wizard-20260917T014551812931Z-6888d6ef6c104c479d8fc413684e1ad2`
   manifest SHA-256 `76ca9793fafb1b1aaca6e8395ddba5dedf6a3d34cc0e120bad1c1ef141fc684f`
2. `wizard-20260917T014644994099Z-af877b65be954adfb66fead21393c94f`
   manifest SHA-256 `941deabc28ed2bef909ad8dfb0f373374fb2f1178136b1f43708c5d40684a2a7`
3. `wizard-20260917T014737297666Z-07ee0c24a9344ee29d24abd1bdcdcde3`
   manifest SHA-256 `e724d454180e3511b29101cada9d46c3652329f536625af0394deda62bf76d19`
4. `wizard-20260917T014829379139Z-5c7ffe61fe2b481b95899a69184aef6b`
   manifest SHA-256 `ad683b888326ea3a9d776fca91c08b383d2e28ed4c7dd5118fd50c9a18d162a0`

## Next predeclared characterization pair

The observed +0.257812514-degree error repeated twice. This is a small-sample
controller-report result, not proof of a deterministic response or physical
accuracy. No model was fitted or enabled, and the older candidates are unchanged.

Next implement separate probes with desired endpoint 1.50 degrees and exact
commands 1.25 and 1.35 degrees, descending from the same high-position target.
The first is motivated by earlier observed command response near this region;
neither is an assumed transfer of the old compensation. Sequence: high/full hold,
1.25 probe/full hold, high/full hold, 1.35 probe/full hold. Existing limits and
stop-on-failure rules apply unchanged. Freeze these values before execution.

Test command/desired separation and metadata before live probing. These new
records will be characterization data. Do not reuse old 1.25-degree-target trials
as held-out validation of a new 1.50-degree model. Select a candidate only after
reviewing the probes, and reserve later new trials for its validation.

Last reported roll: 1.757812514 degrees. Obtain fresh feedback before any next
command; do not assume the next high-position delta will remain admissible.

## First adjacent-target probe pair completed

Implemented explicit `run_wifi_roll_adjacent_low_trial` and
`run_wifi_roll_adjacent_high_trial` actions, previews, publication/display and
bench options `adjacent_low` / `adjacent_high`. Both retain desired 1.50 degrees
independently of the command, use characterization metadata, and do not apply or
modify an existing candidate. 166 focused tests plus JavaScript syntax checking
passed before live testing.

September 16 local / September 17 UTC, predeclared order completed:

| Leg | Fresh roll start (deg) | Command (deg) | Desired (deg) | Final reported (deg) | Error vs desired (deg) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Position high | 1.757812514 | 2.5 | 2.5 | 2.285156222 | -0.214843778 |
| Low probe | 2.285156222 | 1.25 | 1.5 | 1.494140602 | -0.005859398 |
| Position high | 1.494140602 | 2.5 | 2.5 | 2.285156222 | -0.214843778 |
| High probe | 2.285156222 | 1.35 | 1.5 | 1.582031240 | +0.082031240 |

Both target baselines matched on all six reported joints and matched their
preceding positioning holds. Positioning origins differed. Hold-end-to-dispatch
intervals were 16.0715837 seconds low and 16.3021765 seconds high. Fresh baseline
ages were 9.2225 and 8.6879 ms respectively.

All four approximately 35-second passive holds retained their preceding endpoint
on all six reported joints:

| Hold after | Successful originals | Response span (s) | Maximum gap (ms) |
| --- | ---: | ---: | ---: |
| First positioning | 120 | 34.8515 | 421.3692 |
| Low probe | 115 | 34.7876 | 341.1852 |
| Second positioning | 120 | 34.8638 | 451.4974 |
| High probe | 118 | 34.7665 | 661.7258 |

The offline reviewer independently reconstructed all four endpoint decisions and
hold summaries from original responses. Every export verified before advancing.
No retries, fallback paths, deadline changes or compensation updates occurred.

Exports under `software/runs/wizard-exports/`, in execution order:

1. `wizard-20260917T015204433809Z-af730c00901d481ca6fbbf7c7a6b8de4`
   manifest SHA-256 `ac3990f5f7c7fd8e9c1401112ffd355bcd073b083e4d7837536b2a473caddbbf`
2. `wizard-20260917T015257360360Z-8fa39a93682c4cb3ade81be1ed02c2b4`
   manifest SHA-256 `cdd9cae3876a738241e65ba70acbebce7c82999c3e7487efd1b851aac86361b8`
3. `wizard-20260917T015348573699Z-a351cea752ec4d37b258016129947dd7`
   manifest SHA-256 `bd309bf46a02d1ed908e2162d2fe069eab3f3a33965f23f00ac6b2159ff7eb0e`
4. `wizard-20260917T015441803715Z-a0c24e125b16405fbba317766eebe347`
   manifest SHA-256 `3fbc1b92926b00a1f69650dec3aad7cf7739ae9b40b0d4f4e7bde4ef01695a57`

### Interpretation and next step

The lower command had smaller absolute desired-endpoint error in this pair. The
0.10-degree command difference produced 0.087890637 degrees of reported endpoint
difference. One sample per probe does not establish a reliable linear response
or an inverse model, and neither result measures external Cartesian accuracy.

Next repeat in reversed order: high positioning/full hold, 1.35-degree probe/full
hold, high positioning/full hold, 1.25-degree probe/full hold. Keep every existing
limit and command unchanged. Preserve actual starts and prior-path differences;
stop on the first failed leg, hold or export. Only after this comparison consider
freezing a separate local candidate and reserving new trials for validation.

Last reported roll: 1.582031240 degrees. These are characterization samples only;
no new candidate has been selected or enabled.

## Reverse-order probe pair completed

September 16 local / September 17 UTC. Completed high / 1.35-degree probe / high /
1.25-degree probe, each with a full passive hold and independently checked export.
No source code changed and software tests were not rerun; the latest suite remains
166 passing tests. No retry, deadline/limit change or compensation enablement.

| Leg | Fresh roll start (deg) | Command (deg) | Desired (deg) | Final reported (deg) | Error vs desired (deg) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Position high | 1.582031240 | 2.5 | 2.5 | 2.285156222 | -0.214843778 |
| High probe | 2.285156222 | 1.35 | 1.5 | 1.582031240 | +0.082031240 |
| Position high | 1.582031240 | 2.5 | 2.5 | 2.285156222 | -0.214843778 |
| Low probe | 2.285156222 | 1.25 | 1.5 | 1.494140602 | -0.005859398 |

Both target baselines and both preceding positioning origins matched on all six
reported joints. Target baselines matched their preceding hold endpoints.
Hold-end-to-dispatch intervals were 12.2889167 seconds high and 16.8072861 seconds
low; baseline ages at dispatch were 7.8144 and 9.3376 ms. Timing was measured, not
held identical; matching telemetry does not prove identical mechanical conditions.

All four holds retained their preceding endpoint on all six reported joints:

| Hold after | Successful originals | Response span (s) | Maximum gap (ms) |
| --- | ---: | ---: | ---: |
| First positioning | 119 | 34.9337 | 384.1352 |
| High probe | 115 | 34.8875 | 419.4844 |
| Second positioning | 118 | 35.0246 | 500.2014 |
| Low probe | 120 | 34.8341 | 360.8763 |

All four exports passed manifest verification and original-feedback reconstruction
of movement rows, endpoint decisions and hold summaries. Exports under
`software/runs/wizard-exports/`, in execution order:

1. `wizard-20260917T015639480390Z-cc1613fd6ff5457ab22187e13b80d85d`
   manifest SHA-256 `06cc8f42034e1f6f25edd6f1401498bcaad2eb7c3e0e5665c64508ffc9017b29`
2. `wizard-20260917T015728724276Z-2f1f964f7f614ef5993d2e6cb45e6426`
   manifest SHA-256 `0e7bc90c849fb90a12a49d3539005e0a7a1fc4c9d3b64777fd9702043be46fb8`
3. `wizard-20260917T015817762183Z-19a06b49efaf4496974f386034f8c4f9`
   manifest SHA-256 `4b8a6aa00ea8826b1f8e366838a10d048d2899a67ebffd4a13d8079bcfd6e7cc`
4. `wizard-20260917T015911527310Z-da41dd66b5e04ffc8d07e57a308b7da2`
   manifest SHA-256 `09356fe6d4c0bd0cffba9a16ca170630972ca3c4d59019ec79a7e35c12cfd26f`

### Candidate frozen; validation pending

Two characterization samples per command now repeat their respective endpoints.
The 1.25-degree command produced the smaller absolute desired-endpoint error in
both samples. Saved `WIFI_ROLL_150_LOOKUP_CANDIDATE.json` as a new disabled local
lookup: desired 1.50 degrees, command 1.25 degrees, descending, speed 20/acc 1.
The selection uses only these four probe exports; it does not borrow validation
from the older 1.25-degree-target mapping. No interpolation or global model fit.

Next implement a separate hash-bound validation action for this frozen artifact,
test it, then run a finite new control pair: high/full hold, uncorrected 1.50/full
hold, high/full hold, new lookup/full hold. Retain existing bounds and stop rules.
These completed probes remain training evidence, not held-out successes. Candidate
validation count is zero until new validation trials are actually completed.

Last reported roll: 1.494140602 degrees. The candidate is not loaded by any native
action yet and grants no motion authority or external spatial accuracy claim.

The validation action is now implemented and its first new trial has completed
with a late reported endpoint change during the hold. See
[1.50-degree lookup validation](ROLL_150_LOOKUP_VALIDATION.md). Initial arrival
passed, but the unchanged full-hold criterion did not; the candidate remains
disabled and this result is not counted as a full validation success.

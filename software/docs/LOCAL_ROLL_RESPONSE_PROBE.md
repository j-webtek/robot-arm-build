# Local descending response probe — September 16, 2026

Predeclared characterization sequence: high positioning (2.5 degrees), descending
command 0.95 degrees, high positioning, descending command 1.15 degrees. Each
action is separate and includes approximately 35 seconds of passive observation.
Verify each export before proceeding. Stop on any failed movement, observation,
identity, envelope or integrity check; no alternate positioning path or retry.

Desired comparison endpoint is 1.25 degrees for both probes. Exact commands are
retained separately, and excursion limits follow the commanded path. Existing
roll limits, speed 20, acceleration 1, 0.5-degree arrival tolerance, dwell and
feedback deadlines remain unchanged. Fresh actual command delta must be greater
than 0.5 and at most 1.5 degrees; do not assume the high positioning target was
reached exactly. Record all actual starting poses and timing.

These two samples characterize a local response; they are not held-out validation
of the existing frozen candidate and do not enable or refit it. Compare command
differences to final reported-angle differences, preserving any non-monotonic or
unchanged result. One sample per command cannot identify a reliable response
curve, causal mechanism or external tool-tip accuracy.

## Implementation and completed results

Added explicit wizard actions `run_wifi_roll_probe_low_trial` and
`run_wifi_roll_probe_high_trial`, inert previews, report display/publication and
bench-script choices `probe_low` and `probe_high`. Probe reports retain protocol,
desired endpoint and exact command, and label the samples `held_out: false` and
`model_updated: false`. Durable reservations bind the desired endpoint separately
from the wire command. No ordinary movement action enables these probes.

140 focused tests passed, including probe approach/delta rejection and durable
desired-endpoint binding; JavaScript syntax check passed before live testing.

| Leg | Fresh roll start (deg) | Command (deg) | Desired (deg) | Reported final (deg) | Error vs desired (deg) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Position high | 1.406250023 | 2.5 | 2.5 | 2.285156222 | -0.214843778 |
| Low probe | 2.285156222 | 0.95 | 1.25 | 1.230468748 | -0.019531252 |
| Position high | 1.230468748 | 2.5 | 2.5 | 2.285156222 | -0.214843778 |
| High probe | 2.285156222 | 1.15 | 1.25 | 1.406250023 | +0.156250023 |

Both probes' fresh six-joint baselines matched exactly and matched the final
preceding hold. The origins of the preceding positioning legs differed, so prior
path history was not identical. Time from positioning hold completion to probe
dispatch was 12.0722614 seconds low and 11.9919999 seconds high. Baseline ages at
dispatch were 8.2802 and 16.8588 ms respectively.

All four movements verified; all four approximately 35-second passive holds
completed successfully and retained the endpoint on every reported joint:

| Hold after | Original responses | Response span (s) | Maximum gap (ms) |
| --- | ---: | ---: | ---: |
| First positioning | 115 | 34.7374 | 378.7306 |
| Low probe | 116 | 34.8288 | 433.0367 |
| Second positioning | 115 | 34.8149 | 435.5518 |
| High probe | 116 | 34.8174 | 378.3132 |

Each export was verified before proceeding. Original response reconstruction
matched stored motion rows, desired/command endpoint verdicts and hold summaries.

Exports under `software/runs/wizard-exports/`, in execution order:

1. `wizard-20260916T164808273020Z-fb80a9a6786b4047bb923edc62c678bf`
   manifest SHA-256 `0382c02003c04d6ba3be874d64386cf0687297960a53309a37238175f077968b`
2. `wizard-20260916T164857189155Z-ce5868a3198f4e9b984030be1b21e5cd`
   manifest SHA-256 `e4d25c18dc239eafdd07374d7cc55c8b57158e908af7c4dcf991852c38abd009`
3. `wizard-20260916T164952813858Z-8714fd4c65f74663ae8ce6fc66c3dbc7`
   manifest SHA-256 `075b2b9b5cb148c2101b731e82a69e266f9b67a6e5a96c9b49f9f97ad65953cb`
4. `wizard-20260916T165041753722Z-3599cd746adf46fb85377c7dc880d50a`
   manifest SHA-256 `3b1a86edc2661878a779ea4e53b4db710e3ad63c2dc05f368a3a087681a4ff8c`

## Interpretation and next step

The 0.20-degree command difference produced a 0.175781274-degree reported endpoint
difference in this pair. The 0.95-degree probe was closer to the desired endpoint,
but it is only one characterization sample. Prior 1.049804688-degree commands
have reached both of these reported endpoints; these observations do not support
treating the response as an exact deterministic linear function.

Do not replace or refit the frozen candidate yet. Repeat the same two probes in
reversed order, preserving high positioning and full holds. Assess endpoint
spread and prior path differences before fitting any new local model. A future
model would need separate held-out trials; these characterization samples cannot
also serve as its independent validation evidence.

Last reported roll: 1.406250023 degrees. No retries, fallback paths, tolerance
changes or global compensation enablement occurred. Results are controller joint
telemetry, not external spatial accuracy.

## Reverse-order repeat completed September 16, 2026

Sequence: high positioning / 1.15-degree probe / high positioning / 0.95-degree
probe. Each leg included the full passive hold and separate export verification
before advancing. Commands, model and limits remained unchanged. No code changed;
the prior 140-test software result remains the latest test run.

| Leg | Fresh roll start (deg) | Command (deg) | Desired (deg) | Reported final (deg) | Error vs desired (deg) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Position high | 1.406250023 | 2.5 | 2.5 | 2.285156222 | -0.214843778 |
| High probe | 2.285156222 | 1.15 | 1.25 | 1.406250023 | +0.156250023 |
| Position high | 1.406250023 | 2.5 | 2.5 | 2.285156222 | -0.214843778 |
| Low probe | 2.285156222 | 0.95 | 1.25 | 1.230468748 | -0.019531252 |

Both probe baselines and both preceding positioning baselines matched on all six
reported joints. Fresh probe baselines matched their preceding hold endpoints.
Hold-completion-to-dispatch intervals were 11.8873606 seconds for the high probe
and 16.2965908 seconds for the low probe; baseline ages at dispatch were 8.9668
and 18.2508 milliseconds. Timing was recorded, not forced to be identical.

All four holds retained the preceding endpoint on every reported joint:

| Hold after | Original responses | Response span (s) | Maximum gap (ms) |
| --- | ---: | ---: | ---: |
| First positioning | 114 | 34.9229 | 441.2696 |
| High probe | 116 | 34.8126 | 371.6505 |
| Second positioning | 114 | 35.0204 | 437.4682 |
| Low probe | 113 | 34.7745 | 429.9564 |

Original feedback reconstructed all recorded motion rows, endpoint verdicts and
hold summaries; all four export manifests verified. Exports under
`software/runs/wizard-exports/`, in execution order:

1. `wizard-20260916T165256795229Z-04af7f26d59b44bdb15ce7d7cd4f118b`
   manifest SHA-256 `131b020c252ff4649ec7cfa5fce68c5eae73d5af432b517af6ffbf1ab6f35dfb`
2. `wizard-20260916T165345656746Z-fe82d8ab978b4b998bb2f60e912bc0bc`
   manifest SHA-256 `1f61af8d4bece5e2117f6b687d40ce34761d8c3c4dbfe532c97af854feb4c431`
3. `wizard-20260916T165438575987Z-a376c1c5e7ae496cb69a2acce028d79f`
   manifest SHA-256 `187f4e1adbccf31b337bcdaa7d87374796c8f770311ddda466f155bf0f1173d6`
4. `wizard-20260916T165531856317Z-2f021b4ee32e43d98eed5d77e78b3265`
   manifest SHA-256 `a31a4c18dd9d7946896d073d4be85dceabeb6bbac405244fe6f5840600a7a9d9`

### Updated interpretation and next step

Two characterization samples at each command now reproduce their respective
reported endpoints: 0.95 degrees maps to 1.230468748 degrees; 1.15 degrees maps
to 1.406250023 degrees. This is zero observed spread at controller resolution
within this small sample, not guaranteed repeatability or spatial accuracy.

Select 0.95 degrees as a proposed new local descending candidate for desired
1.25 degrees, based on these characterization results. This is a discrete local
lookup choice, not evidence for a globally linear inverse model. Do not interpolate
to claim a more exact command, and do not overwrite the older frozen candidate.

Next freeze a separate, disabled candidate artifact recording these four training
exports and the selection rule (lowest observed absolute desired-endpoint error).
Use distinct future validation actions/records for a finite comparison against
uncorrected 1.25-degree commands, preserving high positioning, full holds and
fresh-baseline checks. The completed probe samples remain characterization data
and must not be relabeled as held-out validation of the newly selected command.

Last reported roll: 1.230468748 degrees. No automatic return, retry, model update
or global compensation enablement occurred.

The selected command is now frozen in a separate disabled artifact and its first
new held-out comparison is complete. See [Lookup validation](ROLL_LOOKUP_VALIDATION.md).
The characterization records above remain training data and were not relabeled.

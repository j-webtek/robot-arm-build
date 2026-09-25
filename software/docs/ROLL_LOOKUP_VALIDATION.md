# Local descending lookup validation

Frozen before validation: `WIFI_ROLL_125_LOOKUP_CANDIDATE.json`. Desired endpoint
1.25 degrees, exact command 0.95 degrees, descending only, speed 20/acceleration 1.
Selected from four characterization samples, which must not count as validation.
This artifact is separate from the earlier direction-conditioned mean-error model.

Predeclared first validation sequence: high positioning with full hold, uncorrected
descending 1.25-degree command with full hold, high positioning with full hold,
new lookup-validation action with full hold. Each command is a separate admission.
Verify each movement, passive hold and export before advancing; stop on failure.
No retry, fallback positioning, larger movement envelope or global enablement.

Use existing step, arrival, dwell, excursion, identity and timing checks. Record
actual baselines and delays; distinguish operational success (0.5-degree arrival
tolerance) from improvement over control. Compare signed/absolute desired-endpoint
errors and preserve worse results. One validation pair is not qualification.

## Implementation

Candidate SHA-256:
`822965da1d902c86993a50c8647b06e672e37323b56a211a42a1c4bc6e48a910`.
The explicit wizard action `run_wifi_roll_lookup_trial` and bench choice `lookup`
verify this hash before hardware access. Reports bind candidate identity, model,
direction, desired endpoint and exact command, label new samples as held-out and
record no refitting/global enablement. The existing probe actions continue to
label their data as characterization, not validation.

144 focused software tests and JavaScript syntax checking passed before physical
testing. Tests cover changed-artifact rejection before hardware access, bounded
approach/step checks and durable desired-endpoint binding. Earlier candidate bytes
and all training exports were preserved.

## First held-out pair completed

September 16, 2026 local time; exports use September 17 UTC timestamps.

| Leg | Fresh roll start (deg) | Command | Desired endpoint | Reported final | Error vs desired |
| --- | ---: | ---: | ---: | ---: | ---: |
| Position high | 1.230468748 | 2.5 | 2.5 | 2.285156222 | -0.214843778 |
| Uncorrected control | 2.285156222 | 1.25 | 1.25 | 1.494140602 | +0.244140602 |
| Position high | 1.494140602 | 2.5 | 2.5 | 2.285156222 | -0.214843778 |
| Frozen lookup | 2.285156222 | 0.95 | 1.25 | 1.230468748 | -0.019531252 |

Target-trial baselines matched exactly on all six reported joints and matched
their preceding hold endpoints. Positioning origins differed. The final-hold-
response-to-dispatch intervals were 15.0825611 seconds control and 20.0607603
seconds lookup. Fresh baseline ages at dispatch were 17.6931 and 8.9225 ms.
This is not a claim of perfectly matched prior mechanical history or timing.

All four movements verified and all four approximately 35-second passive holds
retained their preceding endpoints on all six reported joints:

| Hold after | Original responses | Response span (s) | Maximum gap (ms) |
| --- | ---: | ---: | ---: |
| First positioning | 120 | 35.0311 | 458.1937 |
| Control | 116 | 34.8024 | 476.7730 |
| Second positioning | 126 | 34.9608 | 383.7358 |
| Lookup validation | 121 | 34.8554 | 422.5829 |

Original responses independently reconstructed every stored movement row,
endpoint verdict and hold summary. All four export manifests verified before
any subsequent command. No retry, fallback, tolerance change or global
compensation enablement occurred.

Exports under `software/runs/wizard-exports/`, in execution order:

1. `wizard-20260917T012940721512Z-44da2460f0c3458fba43bd830a135346`
   manifest SHA-256 `198a812d23d125fe4b35673b03bb2bec4bb222dce144a14f5085f196d3268e13`
2. `wizard-20260917T013032891308Z-c714355741a64fedb544fb182f7abe32`
   manifest SHA-256 `bb828e029e683a03ae7dd6e4bad6a6f3ad24a7d0b8eec98c06c21bf8476e93da`
3. `wizard-20260917T013121624155Z-395773d64dc241c2b95506075c010ed0`
   manifest SHA-256 `b92034fd65b256778a415194f20c91ba54f3e92c5f620a857725995199b931c2`
4. `wizard-20260917T013221002703Z-1cb4e631371f47e88b452c69c94d02b8`
   manifest SHA-256 `cff7e24260aa52fd8276d784f55568beedc135b91cf44a65f53504e40452fb13`

## Interpretation and next step

The new lookup's first held-out trial had lower absolute desired-endpoint error
than this control. The two earlier 0.95-degree probes are training evidence, not
additional held-out successes. Candidate selection remains local to this target,
direction, speed and tested starting neighborhood; no general accuracy claim is
supported and no external Cartesian accuracy has been measured.

Next repeat a finite reversed-order control pair (lookup first, control second),
using unchanged candidate bytes, full high-position holds and fresh baselines.
Keep reporting any differences in prior history and timing. Do not fit another
offset from the validation data or promote the candidate based on this one pair.
Last reported roll: 1.230468748 degrees; obtain a new baseline before motion.

## Reverse-order attempt interrupted; diagnostics recovered

September 16 local / September 17 UTC. The first high-position action dispatched
one command and received HTTP 200 transport receipt. Its first independent T105
feedback request then timed out during HTTP headers/body (802.776 ms elapsed with
the unchanged 800 ms I/O budget). No usable post-command row was obtained, so the
transaction correctly ended `COMMAND_OUTCOME_UNCERTAIN`, with `result: null` and
no retry or next movement. The requested reverse-order pair was not completed.
The timeout's underlying network/controller cause is not established.

A secondary bench-display defect raised `AttributeError` when attempting to read
an endpoint from the null result. Export still ran through the existing finally
block and retained the failed operation. Fixed the display to handle absent/null
results and explicitly show transaction state, failure reason and dispatch-attempt
status without fabricating endpoint data. Added hardware-free regression tests
for missing reports, uncertain first feedback, and failure causing only export
and shutdown. 86 focused tests passed. Command/timing policies were not changed.

The sequence stopped. A separate read-only approximately 35-second observation
then succeeded: 123 original responses, response span 34.9084 seconds, maximum
gap 388.9308 ms, zero reported span on all six joints. Current reported roll was
2.285156222 degrees. This supports a stable current position consistent with the
positioning command, but cannot retroactively verify its missing timing/path
evidence. The original movement remains uncertain and was not replayed.

Both exports passed integrity verification; the read-only summary independently
reconstructed from original responses. Under `software/runs/wizard-exports/`:

- Failed movement: `wizard-20260917T013404192516Z-6f569b0d02a14464aa951b62aa3b7c21`
  manifest-file SHA-256 `d5b5bde5a7b1c75337d8972fae346f776ea40abe2b1ff59a8819087a38fe4155`
- Read-only observation: `wizard-20260917T013556012810Z-61e8a82bb35a498e819320c3931ba5e8`
  manifest-file SHA-256 `46465a48ec677f46b3cefeb0ff27871eddf925191989804bf44c0eb60b3efb2d`

Next is a new explicitly recorded validation attempt from fresh feedback, not a
continuation/replay of the consumed positioning attempt. Current reported roll
is already at the high-position neighborhood; do not reissue high positioning
blindly. Keep the frozen candidate unchanged and preserve this interruption in
any reliability summary. The held-out candidate count remains one completed trial.

## New post-recovery validation attempt completed

September 16 local / September 17 UTC. Started a new separately admitted lookup
trial from fresh feedback, without replaying the consumed high-position command.
Then completed a separate high-position action and uncorrected descending control.
All three new movements and their approximately 35-second passive holds passed.
The earlier uncertain positioning transaction remains unchanged in the record.

| Leg | Fresh roll start (deg) | Command | Desired endpoint | Reported final | Error vs desired |
| --- | ---: | ---: | ---: | ---: | ---: |
| Frozen lookup | 2.285156222 | 0.95 | 1.25 | 1.230468748 | -0.019531252 |
| Position high | 1.230468748 | 2.5 | 2.5 | 2.285156222 | -0.214843778 |
| Uncorrected control | 2.285156222 | 1.25 | 1.25 | 1.494140602 | +0.244140602 |

The lookup and control six-joint baselines matched exactly. The lookup baseline
also matched the prior read-only recovery observation; the control baseline
matched its verified positioning hold. These are not identical preparation
histories: the lookup followed an uncertain positioning attempt and separate
recovery observation. Recovery-observation-end to lookup dispatch was 76.6183278
seconds; positioning-hold-end to control dispatch was 12.0091824 seconds. Fresh
baseline ages at dispatch were respectively 8.8295 and 17.3477 milliseconds.
This timing/history difference limits conclusions about order effects.

| Hold after | Successful originals | Response span (s) | Maximum gap (ms) |
| --- | ---: | ---: | ---: |
| Lookup | 119 | 34.9302 | 407.7400 |
| Positioning | 117 | 34.9724 | 375.4334 |
| Control | 118 | 35.0185 | 346.3491 |

All holds retained their preceding endpoint on all six reported joints. Original
responses independently reconstructed the motion rows, desired/command verdicts
and hold summaries. All three export manifests verified before advancing.

Exports under `software/runs/wizard-exports/`, in execution order:

1. `wizard-20260917T013749578310Z-712f9a5438db49a594325492d45c78eb`
   manifest SHA-256 `94d525978754cbd1192842afbb90cfa523d0c9f3d5bba478eb4a3a1682cbc53a`
2. `wizard-20260917T013841061830Z-36e2d5c90ead41d28625e6527271dedd`
   manifest SHA-256 `37eba99710d9bb5fd845c82e81e0482b501c60f8b1fd634c3dab81bf0c26fcb7`
3. `wizard-20260917T013930043053Z-7e8a6e845a0f410aafb8c10c65d8bbc2`
   manifest SHA-256 `9435c0c85e8ce2988fb3f676877c7be0cdebfee1baddfd3b2428861ff01c4937`

### Current evidence and next work

There are now two new held-out lookup trials, each reporting 1.230468748 degrees,
and two accompanying uncorrected controls, each reporting 1.494140602 degrees.
The lookup's absolute desired-endpoint error was 0.019531252 degrees versus
0.244140602 degrees for these controls. The original characterization probes are
not included in the held-out count. The interrupted positioning command is a
transport-reliability failure and is not hidden by subsequent successful trials.

Keep this as a promising experimental local lookup, not a globally enabled
correction or a physical accuracy certification. No source changed during this
attempt, no tests were rerun, and no limits or candidate bytes changed.

Next consolidate these verified exports into a reusable local mapping/evidence
record with explicit target, direction, speed, starting-pose scope, sample counts,
and interruption history. Preserve distinct operational and accuracy conclusions.
Then predeclare one adjacent target characterization protocol rather than assume
this 0.95-degree command or its offset applies elsewhere. Do not silently promote
the candidate or extrapolate it to another joint.

Last reported roll: 1.494140602 degrees. New movement always needs a fresh baseline.

## Offline consolidation completed

Added `ROLL_LOCAL_MAPPING_EVIDENCE.json` with the exact observed starting pose,
target/direction/speed scope, two held-out lookup records, two controls and the
uncertain positioning attempt. It remains disabled and is not loaded by senders.

Added `software/scripts/review_wifi_roll_export.py` to repeat original-feedback
and hold reconstruction without hardware. Replayed all four successful evidence
exports and preserved the timeout export as uncertain. Twenty focused tests
passed, including tampered row/verdict/desired-target/original-body rejection,
invalid-export rejection and bench failure handling. No new physical commands
were sent during consolidation.

The next protocol is documented in `ADJACENT_ROLL_TARGET_PLAN.md`: first measure
an uncorrected descending 1.50-degree target with existing bounds and full holds.
The new action still needs implementation and tests before executing that plan.
# Subsequent evidence update

The later comparison in `ROLL_125_COMPENSATION_COMPARISON.md` found a third
held-out endpoint of 1.406250023 degrees for the frozen 0.95 command, rather than
the earlier 1.230468748. The complete current sample is recorded in
`ROLL_LOCAL_MAPPING_EVIDENCE.json`. Earlier zero-spread statements below describe
only their historical two-trial sample; the candidate remains disabled.

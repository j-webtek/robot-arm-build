# Descending 1.50-degree lookup validation

Candidate: `WIFI_ROLL_150_LOOKUP_CANDIDATE.json`, SHA-256
`3bdb830355bdef5c493ed9ee8b6341bd7bf7dc8dbf9ab7ed1c04d98ac6b18e53`.
Exact command 1.25 degrees, desired endpoint 1.50 degrees, speed 20/acc 1.
Candidate remains globally disabled. Its freeze-time statement that no action
loaded it records historical state; the explicit validation action now does.

Implemented `run_wifi_roll_adjacent_lookup_trial`, preview, report display and
publication, and bench choice `adjacent_lookup`. Hash mismatch rejects the action
before hardware access. Reports distinguish held-out validation from earlier
characterization. 170 focused tests and JavaScript syntax checking passed before
the first physical validation. Existing limits, deadlines and candidate bytes did
not change; other candidates were not modified.

## First held-out pair: arrival passed, lookup hold differed

September 16 local / September 17 UTC. Executed separately: high/full hold,
uncorrected 1.50/full hold, high/full hold, lookup/full hold. Each of the first
three exports fully verified before advancing. The fourth export has valid
integrity and an independently reconstructed successful initial endpoint decision,
but failed the strict unchanged-hold criterion. No further command was sent.

| Leg | Fresh roll start (deg) | Command | Desired | Initial reported endpoint | Initial error |
| --- | ---: | ---: | ---: | ---: | ---: |
| Position high | 1.494140602 | 2.5 | 2.5 | 2.285156222 | -0.214843778 |
| Uncorrected control | 2.285156222 | 1.5 | 1.5 | 1.757812514 | +0.257812514 |
| Position high | 1.757812514 | 2.5 | 2.5 | 2.285156222 | -0.214843778 |
| Lookup validation | 2.285156222 | 1.25 | 1.5 | 1.494140602 | -0.005859398 |

Both target baselines matched on all six reported joints. Prior positioning
origins differed. Hold-end-to-dispatch intervals were 16.9093452 seconds control
and 13.7550417 seconds lookup; baseline ages were 18.6151 and 18.4241 ms.

| Hold after | Successful originals | Response span (s) | Max gap (ms) | Result |
| --- | ---: | ---: | ---: | --- |
| First positioning | 117 | 34.8123 | 399.2570 | Unchanged |
| Control | 115 | 34.7782 | 381.1429 | Unchanged |
| Second positioning | 114 | 34.8071 | 536.6837 | Unchanged |
| Lookup | 117 | 34.7906 | 408.0924 | Roll changed |

Lookup hold contained 14 readings at 1.494140602 degrees followed by 103 at
1.406250023 degrees. The last initial-value response completed 5.7017208 seconds
after dispatch; the first changed-value response completed at 5.9813156 seconds.
These are host observation times, not an exact device transition timestamp.
Other five joints had zero reported span. Final desired-endpoint error was
-0.093749977 degrees; reported roll span was 0.087890580 degrees.

The changed final value is still inside the existing 0.5-degree operational
arrival band. That does not satisfy this experiment's stricter unchanged-endpoint
hold comparison. The observation action's `SUCCEEDED` means feedback capture
completed, not that sustained accuracy passed. The offline reviewer correctly
rejected the full trial with `Hold differs from movement endpoint`.

## Evidence

All export manifests passed integrity checks. Original feedback reconstructed the
four initial arrival decisions and hold summaries. Do not label the fourth hold
unchanged or the full lookup validation successful.

Under `software/runs/wizard-exports/`, in execution order:

1. `wizard-20260917T020645203517Z-5dd9572b080a4761aa0966ba226ff511`
   manifest SHA-256 `d64ef778986b70a2741de9341c2af0dcfd0c02ae2b35934389f83e4e80e64796`
2. `wizard-20260917T020738792875Z-4b6a37f878a84884bd9ca83a6e7fbaef`
   manifest SHA-256 `1de863ba3f4997cb13b75764b29830e0618ae7e10971089d247ad5d8c03d462f`
3. `wizard-20260917T020827171244Z-14b28f2e659d4a93b4aec8d5455ba578`
   manifest SHA-256 `6acff25e13b34b3a7756b5cb2a040ed1b847de4183aaeddee33b18494c75c7cd`
4. `wizard-20260917T020917549534Z-9a208e0f1d4b434499a106efd1e36ead`
   manifest SHA-256 `556f5983f6d3102f1619f1a1e93bd4e966cd6661c39e7c370e3e74e1d60315da`

## Next step

Keep the candidate frozen and disabled. One held-out lookup was attempted; initial
arrival verified, but zero trials have passed the unchanged full-hold criterion.
Do not relabel training probes as successful validation or fit away this result.

First improve offline reporting to distinguish capture integrity, initial arrival,
late endpoint changes, final error and sustained-accuracy status in a structured
record rather than only raising an exception. Test that late changes cannot become
full validation successes. Then predeclare a fresh bounded repeat with the same
command and a full time-series hold to determine whether this change repeats.
No cause is established; do not assume backlash, drift or a firmware problem.

Last reported roll: 1.406250023 degrees. No retry or return was sent. Evidence is
controller joint telemetry only, not independently measured physical accuracy.

## Structured hold assessment and fresh repeat

Updated the offline reviewer to return `hold_assessment` separately from initial
arrival: unchanged status, changed joints/count, final hold angle/error, maximum
absolute hold error, roll span and first observed change time. Valid changed-hold
evidence now prints a structured record with `full_validation_success: false`
instead of being hidden behind an exception. CLI exit remains nonzero for that
record, including uncertain commands. Malformed/tampered evidence still raises.

`full_validation_success` means only the existing initial-arrival checks plus
this experiment's unchanged-hold criterion passed; it is not a candidate promotion
or an independent accuracy certification. The report retains
`physical_accuracy_verified: false` and `motion_authorized: false`.

107 focused tests passed, including late changes within the arrival band,
change-and-return, immediate difference at hold start, other-joint changes,
out-of-band error, invalid timing/empty hold and nonzero CLI exit on failure.
Replaying the previous changed-hold export produced the expected failure record
and retained its original manifest hash.

### New bounded physical repeat

Sequence: high positioning/full hold, unchanged frozen lookup/full hold. No retry
of the earlier trial, compensation change or deadline/limit adjustment occurred.

| Leg | Fresh roll start (deg) | Command | Desired | Initial endpoint | Hold final | Error vs desired |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Position high | 1.406250023 | 2.5 | 2.5 | 2.285156222 | 2.285156222 | -0.214843778 |
| Lookup repeat | 2.285156222 | 1.25 | 1.5 | 1.406250023 | 1.406250023 | -0.093749977 |

The lookup's fresh six-joint baseline matched the previous lookup baseline and
its new positioning hold. Hold-end-to-dispatch delay was 15.8734888 seconds;
baseline age at dispatch was 17.7454 ms. Prior positioning origins differed from
the earlier trial, so hidden mechanical history is not claimed identical.

Positioning hold: 117 originals, response span 34.7190 seconds, maximum gap
421.1535 ms. Lookup hold: 116 originals, span 34.9126 seconds, maximum gap
421.6473 ms. All six joints remained at their preceding endpoint throughout each
hold. Both exports passed integrity, original-feedback endpoint replay and hold
reconstruction. The repeat met the defined unchanged-hold criterion at a less
accurate reported endpoint than the earlier initial arrival.

Under `software/runs/wizard-exports/`:

- Positioning: `wizard-20260917T021306753150Z-162ee9cd09664e3688b823e0de3a80bd`
  manifest SHA-256 `2340321609bf90330558abafb2e37d7cc1dad2c376a93204e56c848a6bd169a1`
- Lookup: `wizard-20260917T021359421783Z-bb4a4ebad56b4f4b85501cfa3454e1d0`
  manifest SHA-256 `64ecde443c182410c539a47e84143035d3197b1bdf36450f404c4e881360c455`

### Current conclusion

Two held-out lookup trials now exist. Both initially passed the broad operational
arrival checks. One failed unchanged-hold stability; one passed it. Both finished
their holds at 1.406250023 degrees, error -0.093749977 degrees. The initial arrival
values differed by approximately 0.087890580 degrees. Preserve all these facts;
neither the zero-spread training results nor the best initial arrival alone
describes validation performance.

Keep the candidate disabled. Next consolidate initial-versus-hold endpoint ranges
in the mapping evidence and define a task-specific sustained accuracy requirement
before promotion. A bounded feedback-correction strategy can first be simulated
against these observed alternatives, including changes after apparent arrival,
rather than fitting another fixed offset to the two validation outcomes. No
automatic corrective movement is enabled by this suggestion.

Last reported roll: 1.406250023 degrees. No additional motion after the repeat.

Offline consolidation and hypothetical correction testing are now implemented;
see `ROLL_150_MAPPING_EVIDENCE.json` and `FEEDBACK_CORRECTION_SIMULATION.md`.
Current native policy rejects the proposed small correction; no live rules were
relaxed and no physical commands were sent during this work.

## Subsequent physical repeat and direction control

See `ROLL_150_REPEAT_INTERRUPTION.md` for the retained connection-reset attempt
and `ROLL_DIRECTION_COMPARISON_20260917.md` for the later successful fresh trial.
The latter held 1.494140602 degrees throughout its observation. There are now
three completed held-out observations and one incomplete attempt; the current
counts and endpoint ranges are in `ROLL_150_MAPPING_EVIDENCE.json`. An ascending
1.25-degree control reported 1.230468748 degrees and is not counted as lookup
validation. Candidate remains disabled and unchanged.

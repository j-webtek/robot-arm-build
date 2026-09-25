# Offline wrist-roll raw-field review

## Outcome

No hardware commands were sent. Added `software/scripts/review_roll_load.py`
to replay export integrity and endpoint/hold decisions before summarizing the
original response field `tR`. Endpoint and hold phases remain separate. Missing
fields and failed requests are counted, not filled with prior values. Every
report retains its export ID and manifest hash. No model or setting changed.

29 focused tests passed (raw-field reviewer and existing endpoint reviewer).

## Observations

Selected historical lookup trials, the controlled comparison, all six original
sweep probes, and the separate 0.85-degree follow-up were reviewed. Table values
are controller feedback, not independently measured physical angles.

| Command degrees | Reported endpoint degrees | Constant hold tR | Reviewed completed holds |
| --- | --- | --- | --- |
| 0.85 | 1.142578111 | -20 | 2 |
| 0.95 | 1.230468748 | -20 | 4 |
| 0.95 | 1.406250023 | -28 | 2 |
| 1.05 | 1.230468748 | 0 | 2 |

The original final 0.85 probe also reported 1.142578111 and tR=-20 through its
91 successful hold responses, but its next request failed. It remains incomplete
and is excluded from completed-hold counts. The separate follow-up does not
repair that session or its timing requirements.

The same endpoint can have different tR values (0.95 versus 1.05 commands), and
the same tR can occur at different endpoints (0.85 versus 0.95). Therefore a
one-variable tR-to-position correction is not justified. Constant fields across
polls also do not independently establish the servo's internal refresh rate.

## Meaning and limits

The local feedback parser labels tR as wrist-roll raw load. Its engineering
units and exact installed-firmware computation were not independently verified
in this review. Do not label these numbers temperature, amperes or physical
torque, or use their sign to infer a physical direction yet.

The [official SDK M3 documentation](https://github.com/waveshareteam/waveshare_roarm_sdk/blob/main/doc/roarm_m3_zh.md)
was inspected. It documents joint feedback and commands but does not establish
the mapping/units of this raw field. Its current HTTP feedback limitation refers
to the SDK path; our previously tested custom transport is separate. Installed
firmware identity is not proven by reading current upstream documentation.

## Reproduction

From the workspace root, pass exact saved export directories:

```powershell
.venv\Scripts\python.exe software/scripts/review_roll_load.py software/runs/wizard-exports/wizard-20260917T032746522159Z-b4027a972a934b6882ed3b2f35f77354
.venv\Scripts\python.exe -m pytest software/tests/unit/test_review_roll_load.py software/tests/unit/test_review_wifi_roll_export.py -q
```

Other inspected export timestamp prefixes (20260917): 013221002703,
023838302816, 025715945095, 030107530669, 031057713428, 031253219307,
031449148977, 031644640699, 031840247679 and 032028360335.
Full IDs are retained in the associated lookup and sweep evidence documents
and emitted by the reviewer. This is a selected comparison, not an exhaustive
inventory of every historical trial.

## Next experiment

Completed follow-up: [paired live results](PAIRED_SPACING_LIVE_RESULTS.md).
The new 1.05 trials reached a different endpoint from the earlier sweep;
consult that report before treating the observations above as repeatable mapping.

Compare repeated 0.95 and 1.05 descending commands from the same freshly
verified high baseline, preserving speed, acceleration and timing. Retain raw
tR alongside command, approach direction and endpoint; evaluate angle error and
repeatability first. Neither setting is globally enabled. Before using tR for
prediction, establish its firmware meaning and test predictive value on held-out
trials. Measurements collected after settling must not be treated as information
available before dispatch. Continue stopping on incomplete feedback rather than
automatically retrying or treating a partial hold as a pass.

# First model-corrected live wrist result

Follow-up: [Matched repetitions and controls](MATCHED_CORRECTION_REPETITIONS_20260915.md)
completed two additional corrected trials and two fresh uncorrected controls.

## Outcome

One corrected command reached the intended **+2-degree controller-reported
endpoint** within the unchanged acceptance band and the tighter improvement
screen. This is one successful local experiment, not physical/tool-tip
calibration or a released general compensation policy.

| Quantity | Result |
| --- | ---: |
| Approach | Decreasing |
| Fresh reported starting wrist | +3.779296882 deg |
| Intended endpoint / acceptance target | +2.000000000 deg |
| Transmitted T101 wrist command | +1.033203106 deg |
| Final reported wrist | +2.021484368 deg |
| Signed error against intended endpoint | +0.021484368 deg |
| Earlier same-approach uncorrected absolute error | 0.900390625 deg |
| Reduction relative to that historical error | 97.61% |
| Nominal endpoint verdict | REPORTED_SETTLED |
| Improvement screen | Passed: <=0.25 deg and better than historical error |
| Confirmed motion submissions | 1; 64 bytes; not uncertain |
| Complete post-command capture | 5.000 seconds; 281 decoded pose samples |
| Retained post-command bytes | 57,555 |
| Final constant reported tail | 234 samples spanning 4.172 seconds |
| Quiet-dwell entry after write | Host read bounds 0.703–0.718 seconds |
| Other-joint change / wrist excursion | Neither detected |
| Cleanup | All handles closed; zero pending IO; within budget |

The earlier controls were separate prior campaigns, not a newly interleaved
control pair. The percentage is a descriptive comparison, not a statistical
confidence claim. No new fitting or coefficient adjustment used this outcome.

The command-target diagnostic reports TARGET_MISSED, as expected: the arm
reported near the intended 2 degrees, not the deliberately shifted 1.033-degree
command. That diagnostic does not override nominal endpoint acceptance.

## Exact command and evidence

```json
{"T":101,"acc":1,"joint":4,"rad":0.018032796039886594,"spd":20}
```

- USB: CP210x 10C4:EA60, serial `52E4E1E8337FEF119E92181CEDD322A4`, COM7.
- Fresh zero-command baseline:
  `operation-fd08a72e13be461ebbba9a3ee2ce2592`.
- Successful campaign: `campaign-b238c71e70fe4a719e5a7d19c951efb1`.
- Original report SHA-256:
  `dc0e384dea18e0e06ddb3f691ba40e56bb3d6b1e54476b8ab8472077afe919cb`.
- Portable campaign directory:
  `software/runs/wizard-exports/campaign-b238c71e70fe4a719e5a7d19c951efb1/`.
- Wizard export:
  `software/runs/wizard-exports/wizard-20260914T235352824528Z-f532dbe65e314e7e864354ede83c8664/`.
- Independent retained-original verification: valid; reconstruction consistent;
  endpoint completion consistent; no trial errors.

Portable reconstruction checks consistency of originals. It does not authenticate
an off-host process receipt or independently measure physical position. Servo
feedback freshness remains unqualified; repeated reports can reflect cached data.
Calibrated external vision is still needed for board/tool-tip accuracy.

## Software now connected

1. Trusted wizard intake `configure_model_corrected_campaign` reconstructs the
   proposal from the frozen model and six independently checked prospective exports.
2. Explicit v4 intent binds the proposal as the configuration original, retains
   nominal and command targets separately, and permits exactly one command.
   V1–V3 campaign records retain their previous interpretation.
3. Existing host review, runtime pinning, current USB checks, owned baseline,
   durable one-use admission, native dispatch and finite cleanup are reused.
4. Fresh baseline checks enforce both nominal and commanded movement bounds and
   approach direction. Child and parent use the same nominal endpoint and
   command-corridor checks; parent reconstruction independently reads originals.
5. Export includes the raw command/capture records and nominal error, separate
   command diagnostic, improvement screen and proposal/model references.
6. Wizard preview displays intended endpoint, transmitted angle and actual
   command count. There is no retry, iterative convergence or implicit return.

Bench entry point: existing `software/scripts/bench_attended_campaign.py` now
accepts `--model-correction`, mutually exclusive with `--order`. It uses the fixed
frozen model and original export selection, not arbitrary supplied offsets. It
still requires an appropriate fresh baseline and reviewed controller directory.
Do not immediately rerun at the current endpoint: the demonstrated starting
approach must be deliberately re-established first.

## Earlier software refusal, retained separately

`campaign-3749fff1f983408aaf90380ab362d334` stopped at the supervisor's old
v2/v3 format allowlist. Receipt: process not created, initial thread not resumed,
zero stdin bytes, empty stdout/stderr, zero retries. It was not a movement test.
Report SHA-256:
`2bf4ba86f828bea04e353052338393f48f625c7022c04a6c05cfe9148d4f33dd`.

The supervisor was updated to accept the validated v4 format. Incapable-backend
tests cover v2/v3/v4 dispatch, wrong intent and insufficient lifetime. The failed
attempt was never resumed; a new baseline, new intent and new single-use campaign
were created after the fix.

## Next experiment

Final selected campaign/model regression: **493 passed, 18,017 deselected**
in 87.90 seconds. JUnit report:
`software/runs/model-correction-native-final-20260914.xml`.
This includes the isolated package, v4 supervisor, native-shaped collector,
wizard staging/preview, original-export reconstruction and failure tests.
Synthetic kernel tests cannot themselves qualify physical motion; the single
live result above is separate evidence.

Retain this successful result as held-out evidence. Deliberately return to the
same tested approach using a separately reviewed bounded positioning command,
then collect additional corrected repetitions and interleaved uncorrected
controls. Keep the model frozen, speed/acceleration and payload unchanged, and
export every attempt including misses. Do not broaden target ranges, speeds or
enable automatic compensation until repeatability is established.

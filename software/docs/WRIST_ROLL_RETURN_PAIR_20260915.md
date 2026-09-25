# Decreasing probe and recent return-pair comparison

## Live result

Fresh zero-command baseline `operation-2eec3be8a31749c5b9b33ca65473ee76`
matched all six previous endpoints. One v19 decreasing probe was sent through
the wizard: campaign `campaign-e621169d1a9147158c32c043e17022f8`.
Report SHA256: `262df257dd73f9e0f79d3fb825d6a885fea3053ae2d6fd89a21220cdc3b28017`.

| Quantity | Result |
| --- | ---: |
| Starting roll | 0.016873789 rad |
| Commanded absolute roll | -0.0005795035199432953 rad |
| Reported final roll | 0.003067962 rad |
| Commanded travel | -1 degree |
| Reported travel | -0.791015620 degree |
| Signed endpoint error | +0.208984380 degree |
| Complete post-command poses | 1,948 |
| Maximum host-read gap | 62 ms |

Endpoint identical at 5, 10, 20 and 35 seconds; no after-five-second transitions
or other-axis drift reported. One confirmed 66-byte write, no uncertainty,
cleanup confirmed with zero pending I/O. Independent export reconstruction and
endpoint completion pass. This passes the existing 0.5-degree arrival band;
the 0.209-degree error remains recorded and is not exact target attainment.

## What the comparison establishes

The immediately preceding increasing probe and this decreasing probe traverse
the same reported low/high endpoints in opposite directions. Their signed
errors are -0.208984380 and +0.208984380 degrees, respectively. The latest final
six-joint report exactly matches the prior increasing probe's starting report.
This is one observed round trip, not a repeatability distribution or proof of
physical tool-tip accuracy.

The older decreasing trial `campaign-2f1f627662f740948dca6f70b3145105`
had the same measured six-joint start, exact command, configuration, protocol,
controller, payload, workcell and risk references. Its final roll was
0.004601942 rad: today's final is 0.087890580 degree lower. Source/runtime
references differ, and each run has its own baseline. Preserve that provenance
difference; this is not a strictly same-build matched repetition. No causal
claim about software versus mechanical variation follows from these two runs.

## Reproducible evidence

Run `software/scripts/review_roll_return_pair_20260915.py` with the workspace
Python. It reads three pinned original exports, verifies their reconstruction,
redecodes baseline/post captures, checks start/command/context matching, and
prints the comparison. It performs no serial access, writes or fitting.

Saved output: `software/runs/WRIST_ROLL_RETURN_PAIR_20260915.json`.
All three original bundles verified successfully during this review.

Roll command count is twelve; base remains 44. No return, retry, compensation
or additional reconnect was sent after this command. Last reported joints:
`[0.007669904,0,1.593806039,0.047553404,0.003067962,3.149262558]`.

## Next bounded experiment

After fresh feedback, repeat the same increasing geometry from this low endpoint
using the existing one-degree relative profile. Compare against campaign
`campaign-83563fca6ffc425ab12d94061c3c7bb0`, including source/configuration
context, rather than fitting an offset immediately. If the full 35-second result
passes and matches the high start, a separately admitted decreasing repeat can
follow. Stop on any held verification or changed start. Preserve every outcome.
No escalation to continuous movement or cross-joint compensation yet.

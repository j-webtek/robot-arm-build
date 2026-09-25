# Fresh-start roll probe

Fresh no-command capture: operation-b9801f5f50014f1391f90b63882514ee.
USB identity matched; cleanup and process exit confirmed; zero write bytes.
Reported joints [b,s,e,t,r,g]:
`[0.007669904,0,1.593806039,0.047553404,0.003067962,3.149262558]`.
This agrees with the held trial's final report; device sample freshness and
physical tool-tip accuracy are not independently established.

The old increasing fixed anchor (0.004601942 rad) does not match. Do not resume
the unfinished fixed repeat or alter its anchor. Instead perform one existing
v19 relative increasing discovery probe: current roll plus one degree, raw
target 0.020521254519943295 rad, joint 5, speed 20, acceleration 1, 35-second
observation. Native admission reacquires/matches all six joints before writing.
One command maximum; no return, retry or compensation. Evaluate retained
arrival, persistence, framing, other-axis drift and cleanup before further work.

This existing relative profile retains its historical decoder; v21 framing is
only available for fixed anchors. If framing holds the trial, preserve that
verdict and inspect originals offline. Do not count this as v21 live validation
or a matched-start repetition of prior commands.

Status: planned before dispatch under the standing secured/clear, supervised,
powered setup authorization. Actual outcome must be recorded separately.

## Completed live outcome

Campaign `campaign-83563fca6ffc425ab12d94061c3c7bb0` completed its one-command
v19 probe. Portable original integrity, endpoint completion and independent
reconstruction all pass. Report SHA256:
`dd29aad9a417490e5c277246e3824b0bdaa1ec8443d9b0b6f0bc3a08d202585f`.

- Exact transmitted target: 0.020521254519943296 rad (approximately 1.175781 deg).
- Reported final: 0.016873789 rad (approximately 0.966797 deg).
- Signed endpoint error: approximately -0.208984 deg.
- Reported travel: approximately +0.791016 deg for the +1-degree command.
- 1,947 complete post-command poses; maximum host gap 62 ms.
- Same endpoint at 5, 10, 20 and 35 seconds; zero after-five-second transitions.
- Other five joints: zero reported drift. One submission; cleanup confirmed.

The broad 0.5-degree arrival band passes, as does the separate persistence
screen. This does not mean exact target attainment: the measured undershoot is
retained for modeling, not hidden by the pass label. No compensation was used.

Derived verified evidence: `software/runs/WRIST_ROLL_FRESH_START_PROBE_20260915.json`.
Full originals: `software/runs/wizard-exports/campaign-83563fca6ffc425ab12d94061c3c7bb0/`.
No additional command or post-run reconnect was performed. Roll count is now
eleven; base remains 44. Last reported joints:
`[0.007669904,0,1.593806039,0.047553404,0.016873789,3.149262558]`.

## Next useful test

Freshly confirm that pose, then consider one relative decreasing degree from
0.016873789 rad. That would reproduce the command/start geometry of the first
successful v19 decreasing persistence trial (campaign-2f1f627662f740948dca6f70b3145105),
unlike the unfinished v20 fixed trial. Compare all context references before
calling it a matched experiment; source/runtime versions have changed. Retain
35-second persistence and stop on any failure. Do not infer a global offset
from this single new increasing point.

# First completed wrist-roll persistence run

## Result

The corrected v19 profile completed one decreasing one-degree roll command and
35 seconds of observation in the same owned connection. No retry, return,
positioning or compensation command was sent. This validates the live capture
and export path for this trial; it does not validate general compensation.

| Quantity | Reported degrees |
| --- | ---: |
| Start | +0.966796894 |
| Commanded absolute target | -0.033203106 |
| Endpoint at 5, 10, 20 and 35 seconds | +0.263671854 |
| Final error versus command | +0.296874960 |
| Change between 5-second and 35-second endpoints | 0 |
| Endpoint after separately reopening the connection | +0.263671854 |

There were 1,949 post-command pose records, 399,717 post bytes and 2,217 post
reads. Horizon sample counts were 285, 563, 1,119 and 1,949. Coverage passed;
largest host observation gap was 62 ms. After five seconds, no reported roll
transition occurred. All five other joints reported zero drift.

Exactly one complete 66-byte command was submitted, without write uncertainty:

```json
{"T":101,"joint":5,"rad":-0.0005795035199432953,"spd":20,"acc":1}
```

Reported quiet-entry bounds were 360–375 ms after write. These are host-observed
feedback timing bounds, not independently measured physical settling times.
Owned cleanup closed all handles within budget with no pending I/O. Portable
export integrity, full original reconstruction and endpoint completion all passed.

## Reconnect comparison

Only after verifying the complete trial export, a separate zero-command baseline
was captured. Every decoded roll value in that capture was 0.004601942 rad,
matching the continuous trial's endpoint. All six final joint values matched.
The reconnect capture is retained separately; it was not spliced into the
35-second observation. Its cleanup completed and confirmed write-byte count was
zero. A reconnect-related or delayed change was not reproduced in this trial.

## Evidence

- Fresh initial baseline: `operation-0fec1279a7324283aaeb7ea3fc55e1bf`.
- Campaign: `campaign-2f1f627662f740948dca6f70b3145105`.
- Report SHA256: `f601f654983cc11fc8c85b6447b3564a8b81332399668bdd01a9f2cb412a91ec`.
- Original export directory: `software/runs/wizard-exports/campaign-2f1f627662f740948dca6f70b3145105/`.
- Reconnect baseline: `operation-9b716b3450aa4eb3947614f4658551d8`.
- Full derived verification, persistence horizons, lifecycle, write/cleanup and
  reconnect original hash: `software/runs/WRIST_ROLL_PERSISTENCE_LIVE_20260915.json`.

Host execution used the same owned connection for the command and post capture.
The pure persistence analyzer deliberately retains its
`single_connection_provenance_verified=false` flag: it cannot attest connection
history from pose rows alone. The native lifecycle/export supplies separate host
execution evidence. Neither proves device sample freshness or physical tip accuracy.

Current reported [b,s,e,t,r,g] radians:

```text
[0.007669904,0,1.593806039,0.047553404,0.004601942,3.149262558]
```

Roll motion command count: eight. Base count: unchanged at 44. The earlier v18
launch failure sent no command and is not counted as a movement.

## Interpretation and next step

This endpoint was persistent but remained +0.296875 degree above the command.
It passed the existing 0.5-degree arrival band; that is not exact placement.
Its error differs from the earlier decreasing point (+0.384766 degree), which
used a different start/target. Do not treat the difference as proven improvement,
noise, or a direction-only constant offset.

Next bounded trial: use the existing v19 profile for one increasing one-degree
probe from a freshly verified current pose, with the same 35-second capture and
separate reconnect comparison. This examines the direction where the earlier
late discrepancy appeared; it is not an exact repeat of that older target.
Freeze subsequent command points and actual measured starts before comparing
repeats or fitting a local model. Do not transfer base/pitch coefficients or
interpret joint feedback as measured Cartesian accuracy.

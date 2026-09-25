# Wrist-roll second-point discovery

## Finite scope

Use the existing v16 relative one-degree profile, unchanged. This is a two-command
discovery run, not a repeatability comparison and not compensation validation.
No new broad motion interface or relaxed limit is needed.

1. From the last measured six-joint pose
   `[0.007669904,0,1.593806039,0.047553404,0.001533981,3.149262558]`,
   capture a fresh baseline, then command increasing by one degree. The expected
   raw absolute roll target is 0.018987273519943295 rad (+1.087890637 degrees).
2. Reconstruct the original export and inspect the final six-joint pose. Only
   after clean endpoint completion and cleanup, capture a new baseline and issue
   a decreasing one-degree probe from that measured endpoint. Its absolute target
   is the newly measured roll minus pi/180; record it before dispatch in the
   wizard's existing immutable preview.

At most two command writes. No retries, extra positioning or automatic return.
If the first baseline differs from the stated starting pose, stop and reassess.
If either command fails the existing endpoint, drift, freshness, write or cleanup
checks, retain the miss and stop. The second probe is separately admitted, not
queued in advance. All existing v16 envelope checks remain enabled.

Speed 20, acceleration 1, five-second post capture, no contact or added payload.
User's standing bench/clearance/operator confirmation applies. Every test remains
limited to wrist roll; other joints are monitored. Software cancellation is not
a physical emergency stop. The already accepted local envelope is unchanged.

## Simulation and evidence

Exercise the changed starting pose through native-shaped capture/export fixtures,
including plausible biased reports, misses and other-joint drift. Re-run the
existing roll profile tests before live dispatch. Do not edit source during live
staging or execution.

Retain raw exports, exact targets, measured six-joint starts/ends, errors, write
accounting and cleanup. Do not pool the two commands as matched repeats, or treat
the earlier fixed targets as identical contexts. If these commands produce
distinct command/output pairs, define a later frozen repeat protocol using their
actual measured anchors. A second discovery point alone is not model validation.

Status: one discovery command completed; the second command was not sent.
The subsequent baseline differed from the motion-capture endpoint by
0.087890637 degree. A second zero-command capture confirmed the new reported
position. Progression was held for this new evidence, not a failed USB connection
or a request for another routine operator confirmation. See
[results and revised next step](WRIST_ROLL_SECOND_POINT_20260915.md).

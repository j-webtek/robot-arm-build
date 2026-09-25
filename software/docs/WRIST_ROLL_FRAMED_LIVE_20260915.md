# First framing-enabled live wrist-roll trial

## Outcome

Fresh no-command feedback `operation-07f68f7f0571486db7b6b004d7fcbba9` matched
the required low anchor. A new, separately admitted v21 increasing fixed probe
completed: `campaign-8162e80bb7d446f1b7a994d4e1ce65c3`.
Report SHA256: `53a8b1ccde41dae37ef556879d40c43b46f8f6ac1382f3313ee8e4935423e2f0`.

| Measurement | Result |
| --- | ---: |
| Starting roll | 0.004601942 rad |
| Raw command | 0.022055234519943297 rad / 1.263672 deg |
| Reported endpoint | 0.021475731 rad / 1.230469 deg |
| Reported travel | +0.966797 deg |
| Signed target error | -0.033203 deg |
| Complete post-command samples | 1,947 |
| Maximum host-read gap | 63 ms |

Endpoint identical at 5/10/20/35 seconds; no after-five-second change or reported
other-axis drift. One confirmed 64-byte write, no write uncertainty, cleanup
confirmed and no pending I/O. Portable original integrity, reconstructed commit
and endpoint completion independently verified. No compensation applied.

## Actual split-frame handling demonstrated

This was not merely an aligned capture exercising the version gate. The final
11 baseline bytes and first 194 post bytes formed one valid 205-byte pose.
Native verification excluded the entire crossing frame from post-command
evidence and exported the same proof reproduced by the offline verifier.

- Baseline fragment range: [13685,13696).
- Post excluded prefix: [0,194).
- Joined-frame SHA256:
  `3a0d0fb134fcda538f13e1aa4f73400f6d33ce58b4b148c09c665b1e47b77cef`.
- Status: CROSSING_FRAME_EXCLUDED.
- Crossing frame counted as post-command feedback: false.

Original bytes remain intact. This demonstrates the bounded framing path on a
live capture; it does not prove lossless transport, device sample freshness or
physical positioning accuracy in all conditions. Fault coverage remains based
on the prior software tests, not faults deliberately induced on the arm.

## Comparison with prior same-geometry trial

Prior v19 campaign `campaign-8e69010a84ae4ad2b8775c6cf1fd9df9` had the same
six-joint staged start, measured roll start and exact command, and reached the
same endpoint. Endpoint difference is zero. Schema, configuration, source,
runtime and per-run baseline references differ and are retained explicitly;
controller/protocol, payload and workcell references match.

The small error is therefore not evidence that framing improved mechanical
accuracy. It reproduces a previously observed result at this particular point.
The other increasing geometry had a 0.209-degree undershoot, so one constant
offset across targets is not established. Decreasing variability also remains.

## Reproduction and next test

`software/scripts/review_roll_framed_live_20260915.py` verifies both pinned
original exports and prints the comparison without hardware access. Saved
output: `software/runs/WRIST_ROLL_FRAMED_LIVE_20260915.json`.

Roll count fifteen; base remains 44. No further movement or reconnect was made.
Last reported joints:
`[0.007669904,0,1.593806039,0.047553404,0.021475731,3.149262558]`.

Next: refresh feedback and, if this high anchor still matches, consider one new
v21 decreasing fixed probe. This revisits the geometry of the earlier held v20
trial, whose roll changed after about 18.3 seconds. Preserve that historical
hold and compare all 35 seconds rather than judging only early arrival. Do not
restart the old campaign or automatically return/retry after any failure.

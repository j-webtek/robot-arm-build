# Second wrist-roll point: delayed endpoint discrepancy

## What ran

66 focused simulation tests passed, including new-start original reconstruction,
plausible biased responses, misses and other-joint drift. Then one increasing
v16 command ran through the wizard. No motion implementation or limit changed.

Start roll: 0.001533981 rad (+0.087890637 degrees).
Command: T101, joint 5, rad 0.018987273519943296, speed 20, acceleration 1.

| Observation | Reported roll (degrees) | Error versus command (degrees) |
| --- | ---: | ---: |
| End of five-second motion capture | +0.878906257 | -0.208984380 |
| Later feedback capture 1 | +0.966796894 | -0.121093743 |
| Later feedback capture 2 | +0.966796894 | -0.121093743 |

The short-window error matched the earlier increasing point. However, both later
captures reported an additional +0.087890637 degree (0.001533981 rad). Their host
capture windows were approximately 33.234–38.125 seconds and 60.719–65.609 seconds
after the command write. All 270 and 269 complete pose records respectively had
the later roll value. Both captures sent zero command bytes and closed cleanly.

The original motion trial had 280 post samples, one complete 64-byte write,
no uncertainty, no reported other-joint drift, and verified cleanup and export
reconstruction. Its selected baseline sample host age was 141 ms. The reported
quiet-entry bounds were 344–359 ms after write. These facts do not establish that
the physical joint remained permanently at that endpoint afterward.

## Consequence

Only one of the two budgeted motion commands was sent. The second was held when
fresh feedback disagreed with the prior endpoint. No retry, repositioning or
compensation was sent. This is useful movement-model evidence, not a failed
connection. Roll command count is seven; base count remains 44.

The evidence cannot distinguish delayed servo settling, encoder reporting effects,
or a serial-reopen/startup effect. No continuous capture covers the gap, and
opening a serial port can affect the controller even without command bytes.
Do not label the discrepancy definitively as backlash, drift or an exact encoder
tick, or train the two observation horizons as equivalent endpoints.

Latest reported [b,s,e,t,r,g] radians:

```text
[0.007669904,0,1.593806039,0.047553404,0.016873789,3.149262558]
```

This does not match either old v17 roll anchor. Do not re-use those routes without
an explicitly planned start. No Cartesian physical accuracy is established.

## Reproduction

Full derived evidence and original hashes:
`software/runs/WRIST_ROLL_SECOND_POINT_20260915.json`.
Motion originals: `software/runs/wizard-exports/campaign-7f6aa44cee654b4c88dc7b77ca129564/`.
Follow-up originals remain in `software/runs/wizard-diagnostics/`, identified by
the operation IDs and SHA256 hashes in the result JSON. They are not rewritten.

Run this read-only reconstruction from the workspace root:

```powershell
.\.venv\Scripts\python.exe software/scripts/review_roll_second_point_20260915.py
```

## Next implementation: endpoint persistence observation

1. Add a bounded same-connection observation phase after the existing five-second
   endpoint check. Preserve the five-second result separately; do not redefine
   historical success or silently change previous schemas.
2. Capture through approximately 35 seconds after a single small roll command,
   keeping the connection open. Explicitly budget duration, reads, raw bytes,
   supervisor deadline and cleanup; do not merely extend a Python sleep. No
   additional commands, retries or return motion belong to this profile.
3. Report early endpoint, later endpoint, min/max span, transitions, and persistence
   at named observation horizons. Monitor all six axes throughout. Separate
   clean but changed endpoints from malformed, missing or late telemetry.
4. Test delayed one-step settling, stable data, continuing drift, other-joint
   motion, corrupt data, capture limits and cancellation. Verify full retained
   export reconstruction and actual isolated native packaging before hardware.
5. Choose one command from the current measured start within the existing local
   roll envelope, preview it, run it once, and inspect same-connection evidence.
   Only afterward compare with a separately labelled reopened-connection capture.
6. Resume additional command-point mapping when the endpoint observation horizon
   is understood. Keep any proposed offset/linear model offline until repeated
   points and held-out corrected/control trials validate it.

No new movement was sent as part of these next-step preparations.

Persistence analysis is now implemented and replay-tested; native extended capture
is not yet released. See [implementation status and integration boundaries](WRIST_ROLL_PERSISTENCE_IMPLEMENTATION_20260915.md).

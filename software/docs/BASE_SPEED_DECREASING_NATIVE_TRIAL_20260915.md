# Decreasing speed-10 base trial

Predeclared: one v15 decreasing command, only after fresh reported pose matches
the previous increasing trial's final pose and existing admission gates. Use the
standing operator setup confirmation; independently check connection identity
and telemetry. No retry, positioning command, or automatic return.

- Expected [b,s,e,t,r,g] radians:
  `[0.018407769,0,1.593806039,0.047553404,-0.001533981,3.149262558]`.
- Desired base endpoint: +0.4 degree.
- Transmitted absolute target: -0.011952475158143525 rad.
- Speed 10, acceleration 1, five-second observation window.
- Preserve six-joint matching, fitted start-domain, travel/excursion checks,
  250ms selected-sample-age gate, one-use submission and owned cleanup.
- Reconstruct export independently; retain signed endpoint error, transition
  timing, all other joint drift, write accounting and cleanup.

The speed-20 inverse is an experimental candidate at speed 10. A passing leg
does not validate a general speed-specific model or physical tip accuracy.
Stop after this leg for review before planning matched speed-20 references.

Status at declaration: no device opened or command sent for this trial.

## Completed result

Fresh baseline `operation-3855182c0fb74cc1b592cb8ec5e1fe73` matched the expected
six-joint pose, with zero command bytes and confirmed cleanup. Campaign:
`campaign-a2b64fc6844c4e569fb5f7d5bb09e9c4`.
Report SHA256:
`1e0b433df333ee6aadfdfd2f5a5c2a1f70697e127e3de5c26562e83a60c0f4f7`.

- Exactly one native submission, 65 confirmed bytes; no uncertain write.
- Reported start: 1.054687474 degrees; final: 0.439453128 degrees.
- Desired 0.4 degree; signed error +0.039453128 degrees; endpoint screen passed.
- 282 post samples over five seconds, seven reported transitions.
- First changed report acquired 594-625ms after write; final constant-run entry
  860-875ms. The endpoint monitor's earlier quiet-band entry (766-782ms) is a
  different measure, not the instant the final encoder value appeared.
- Selected baseline sample age at write: 172ms, below the unchanged 250ms gate.
- Maximum reported drift in every other joint: zero; no excursion flagged.
- All handles closed, no pending I/O, cleanup within budget.
- Original integrity, reconstruction and endpoint completion independently
  verified from portable originals, not just the wizard success message.

Final [b,s,e,t,r,g] radians:
`[0.007669904,0,1.593806039,0.047553404,-0.001533981,3.149262558]`.
Machine-readable result: `runs/BASE_SPEED_DECREASING_NATIVE_RESULT_20260915.json`.
Originals: `runs/wizard-exports/campaign-a2b64fc6844c4e569fb5f7d5bb09e9c4/`.

Both directions now have one passing speed-10 observation. These reproduce the
reported endpoints seen in historical speed-20 observations, but do not establish
better accuracy, actual servo speed, or general compensation validity. No model
was fitted and no new settings were made persistent. Only the declared movement
was sent; base-command total is now 38.

Next: `BASE_SPEED_MATCHED_REFERENCE_PLAN_20260915.md`.

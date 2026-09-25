# r29: stable measured-baseline clearance recovery

## Purpose

r28 rejected a3-count elbow offset before writing any targets. Do not treat
that offset as a successful elbow arrival, but do not require unchanged joints
to achieve an unrelated accuracy target before every local recovery movement.
This revision observes the existing pose and limits new drift independently.
The user approved proceeding with this change and the bounded recovery workflow.

## Contract

- Distinct scope `STABLE_CLEARANCE_RECOVERY`, command
  `shoulder-stable-clearance24-v1`; r27/r28 scopes retain their original behavior.
- Three fresh seven-joint stationary scans, each separated by at least100ms
  from completion of the previous scan. Export and acknowledge each separately.
  Later baseline positions must stay within1count of the first baseline.
- All torques enabled, exact existing goals unchanged. Absolute positions still
  must be within2counts of the reviewed local reference
  `[2047,2448,1667,2905,1589,2040,2047]`. Shoulder residual directions/magnitudes
  remain explicitly bounded2–7counts; unchanged joints' starting goal errors
  are capped at5counts (the absolute pose bounds can be tighter).
- Preserve the first measured baseline. During intent, prewrite and postwrite,
  unchanged joints must remain stationary within2counts of their initial
  measured positions, with the same targets and enabled states. This is not
  permission for cumulative drift or arbitrary old target errors.
- Same one paired packet as r28: shoulder goals2419/1695, sum4114, speed20,
  acceleration1, actual-to-target travel no more than32counts. No elbow, wrist,
  base or gripper target changes; no explicit torque or settings writes.
- Selected shoulder arrival remains three stationary samples within2counts of
  the new targets. Unchanged joints are judged by measured drift, not their old
  residuals. Five-second post-command acquisition deadline; separate terminal
  export barrier. No return, retry or follow-on command after failure.

## Evidence and limits

Stage: `wizard-20260919T211408966692Z-1e9516442bc247d28c2fc38464bbdcc9`.
Compile: `wizard-20260919T211604203264Z-471612255f894a76877c46d285a3a416`.
Review: `wizard-20260919T211631764101Z-c0dc86b394944c8a9c89846b9362c75a`.
App SHA256: `d9d61fc6bcc3b32b6e84a6d3065dcd6bbbf96d374243b83fb140c9e5395baa00`.
Size1146336bytes, offset0x10000, slot0x140000, headroom164384bytes.
Largest reviewed individual frame560bytes; not a total stack bound.
After adding the new stability-event serializer,154 native/board/reviewer tests
passed. Twenty-eight reviewer/preview tests also passed; counts overlap.
Cases include unstable second baseline, bad scope, altered goals/pose, missing
samples, insufficient sampling interval, moving feedback, read failure, wrong
direction, neighboring drift, stationary plateau and export failure.

The nominal model still predicts approximately7mm end-edge rise. That is not
measured physical clearance or stylus accuracy. Fresh local checks cannot
establish an unmodeled collision-free path; no full upright or typing move is
included. Do not power off unsupported links: prior power removal caused a fall.

## Release sequence

Compile/review the frozen source, pin the exact app and review, verify retained
controller state, then one app-only installation/startup preserving settings and
credentials. Run one new scope only after startup evidence binds to that image.
Its fresh baseline governs the write. Export the result even if no packet is sent.

## Actual result: movement sent; transient neighbor deviation; settled shortfall

r29 installed once with verified full readback and unchanged protected flash.
Installation: `wizard-20260919T212145076702Z-ba9c407236f945eab31721616bcb1558`.
Startup: `wizard-20260919T212145480552Z-cfcf6d5b5e294214bedf6be0d5a022c2`.
Movement boot: `e3d2e54c22a191f01ee5f88031f81280`.

All three baseline scans were identical:
`[2047,2448,1667,2904,1590,2041,2047]`. Intent and immediate prewrite scan matched.
One target packet was sent. The first postwrite scan showed shoulders2440/1676
moving toward2419/1695, but wrist pitch1594 was4counts above baseline1590.
Wrist roll also reported nonzero speed during that scan. Either the neighbor
drift or stationary-neighbor test can stop progression; the controller reported
`RISE_STATE_CHANGED`. Do not equate this fault with a physical stop: the existing
servo targets remain active, and no torque-off or cancellation was sent.

Run: `wizard-20260919T212201457428Z-7365a00c813a4fdfb9727a9a4cec7146`.
Retained status: `wizard-20260919T212213524097Z-6f8ee242a83e4f7f8c59673b40aceb60`.
Five normal event records were exported; the sixth fault scan is preserved in
run operations. There was no return, additional target packet or settings write.

### Settled read-only capture

The installed owner locks bus access after fault. One separately journaled,
diagnostic-only startup of the same r29 image enabled fresh pose acquisition;
it sent no servo or settings commands. The helper requires the exact retained
postwrite fault and verified installation, and is one-use per previous boot.
Six helper guard tests passed. No movement retry was made.

Restart: `wizard-20260919T212333009436Z-8480f7760dd3484ab7bd606101fd0022`.
Fresh startup: `wizard-20260919T212356582148Z-759397d9c2a24c4896a47ddfef686884`.
Pose capture: `wizard-20260919T212404944815Z-59ea5b83a5984ddfac03f00c0213af3c`.
Assessment: `wizard-20260919T212404883110Z-d3b2fe63cc114e438ead8d5f8f9d81d2`.
Current boot: `aabbadc2924d859bfacb57e1aeccd6cf`, reserved by completed pose owner.

Three fresh snapshots agreed exactly, with all joints enabled and no sampled
motion. These are historical settled observations, not an ongoing pose guarantee.

| Servo | Before command | During first postwrite scan | Settled sample | Goal | Signed residual |
| --- | ---: | ---: | ---: | ---: | ---: |
| 11 | 2047 | 2047 | 2047 | 2047 | 0 |
| 12 | 2448 | 2440 | 2429 | 2419 | +10 |
| 13 | 1667 | 1676 | 1688 | 1695 | -7 |
| 14 | 2904 | 2904 | 2904 | 2907 | -3 |
| 15 | 1590 | 1594 | 1591 | 1589 | +2 |
| 16 | 2041 | 2042 | 2041 | 2040 | +1 |
| 17 | 2047 | 2047 | 2047 | 2047 | 0 |

Actual shoulder changes were-19/+21counts; intended travel was-29/+28. The wrist
excursion settled to+1count from baseline. This establishes directional movement
and a transient neighbor response, not arrival accuracy or measured clearance.
Do not fit a global compensation map or assume the next residual is identical.

Offline verified replay/comparison script: `scripts/analyze_r29_settled_recovery.py`.
Analysis: `wizard-20260919T212458408646Z-f7e6a7fbf4e942208ea216666ddf55f0`.
Additional release/startup/host regression suite:168 passed; not a full-suite count.

## Next engineering priorities

Offline implementation checkpoint: [fault settling capture](FAULT_SETTLING_CAPTURE_IMPLEMENTATION.md).
The read-only native collector and failure tests exist; authenticated session/host
integration and deployment remain pending. This does not change installed r29.

1. Add bounded read-only settling capture after a latched motion fault, while
   permanently disabling further writes in that session. Avoid needing restart
   merely to find out where the already-commanded movement settled.
2. Separate transient neighbor response, settled drift, selected-joint arrival
   quality and hard faults. Do not silently widen every threshold or claim a
   transient-limit breach was successful operation. This single trial supports
   investigating timing/load response, not proving its mechanism.
3. Plan the next local upward step from a fresh capture near2429/1688, accounting
   for goals2419/1695 and residual10/7; the old r29 starting window no longer fits.
   Prefer reviewed parameterized bounded plans over a new hardcoded firmware
   build per waypoint, preserving explicit ranges, signed scope and one-use
   session ownership. No further physical movement has been sent or admitted.

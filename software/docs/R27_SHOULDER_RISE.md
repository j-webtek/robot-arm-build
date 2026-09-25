# r27: one measured-state shoulder rise

Current user approval covers firmware installation/startup and bounded movement
testing toward upright. This release performs only the first local rise; it does
not claim the full upright/90-degree outcome is achieved.

## Image and review

- SHA-256: `c46e1ab78cb6b38c1244f1da8dd8b459340704b65af093c3b1875ed3d6158bba`.
- App bytes1,145,280; offset0x10000; predecessor r26; no filesystem changes.
- Stage: `wizard-20260919T201753511506Z-23f1c030a3764c42a532013d3df53a9d`.
- Compile: `wizard-20260919T201953164547Z-babaa8c788664e309b8a1abcba47af9a`.
- Review: `wizard-20260919T202100589399Z-f1770dd8252c4a598b3cf8803e3bc4d1`.
- 165,440 bytes app-slot headroom. Largest reviewed individual frame496 bytes;
  not a total stack bound. Existing partition/bootloader identities match.

## State and action contract

The r26 records showed positions `[2047,2455,1659,2906,1589,2040,2047]` with all
seven torques enabled. Its final export-handshake fault is preserved, not erased
or reclassified as session success. r27 does not replay those same-position writes.

Fresh baseline: seven stationary, enabled, tracking joints. Host requires each
position within16 counts of the recorded pose before signing the first receipt.
Controller independently bounds the shoulder/elbow local starting window.
Intent is separately exported, and actual positions are reacquired after that
receipt. Both shoulder positions must still equal their intent positions.

One `SyncWritePosEx` packet targets shoulder12 at fresh position minus12 counts,
shoulder13 at fresh position plus12 counts. Speed20 counts/s, acceleration1; keep
all other targets unchanged. Preserve the measured pair relationship rather than
forcing the nominal reference pair sum. No explicit torque commands, return,
retry, settings modification or automatic second movement.

The broadcast packet has no acknowledgement. Export it as SENT_UNACKNOWLEDGED,
then read target registers and actual positions. Positions must remain inside
the start-to-target envelope with two-count allowance; other joints must remain
held within two counts and retain their targets. Three consecutive stationary
arrivals within two counts are required. Wrong target/direction, invalid feedback,
unexpected neighbor behavior, timeout or export failure stops the sequence.

Acquisition deadline: five seconds after sending. Final exported samples retain
the separate ten-second persistence barrier; bookkeeping delay alone does not
invalidate samples already acquired inside the motion-observation window.
This corrects the r26 terminal-wait fault without relaxing its acquired-sample
requirements. A fault stops further commands; it is not a hardware power cutoff.

## Evidence and limits

Native/host bridge tests cover gradual and immediate motion, no motion, wrong
direction/goal, passive or out-of-window baseline, neighbor drift, failed reads,
wrong scope, failed receipts and final export delays. Real retained servo-library
wire tests verify the exact two-servo packet addresses/targets/speed/acceleration
and checksum in a memory-only serial sink. These are software tests, not actuator
performance measurements.

The nominal model predicts roughly2.86mm endpoint rise for this1.05-degree step.
No board registration or camera measurement exists, so do not claim physical
clearance or stylus accuracy. The next phase depends on the actual fresh readbacks.

## Physical result

## Installation failure and restored current state

The one r27 installation attempt stopped at ROM synchronization, before identity
checks, stub upload, flash erase or application write. Journal
`software/private-backups/controller-20260918-session1/app-r27-deployment-events.jsonl`
contains only RESERVED and STOPPED. The error was: download mode detected but no
sync reply. This is a USB/serial bootloader communication failure, not a failed
shoulder movement. Its underlying cause is not established. COM7 still enumerated
with the expected CP210x serial identity.

r27 is **not installed**. No shoulder-rise command was sent. Do not delete the
journal or rerun the consumed installer. The r26 application was not overwritten.

One separate recovery startup of existing r26 was performed, with guards requiring
this exact prewrite-only journal and prior verified r26 installation. No flash,
settings or servo commands were sent during recovery. Export:
`wizard-20260919T202608563404Z-c111bf72f6eb4528bf6d14e54536d326`.

Recovered r26 startup:
`wizard-20260919T202641742612Z-ba066f736fec46a2a5717089f33f7f6f`.
Current boot: `8b2dfca505cbe0d6e047e1ae040c1ebd`.
Read-only three-snapshot capture:
`wizard-20260919T202704807379Z-a676d0b5bb9c425db52cc995734b1bb0`.
Assessment:
`wizard-20260919T202704744598Z-d307126237ac46a6aea1597813fd2dd9`.
Category STABLE_SAMPLED_POSE, action_count0. Positions remained
`[2047,2455,1659,2906,1589,2040,2047]`; goals
`[2047,2455,1659,2907,1589,2040,2047]`; all torque states1.
The new boot is now reserved by the completed read-only pose owner.

Next: investigate bootloader connection timing/USB path before another installation
attempt. Prefer a direct known-good data cable if an extender/hub is in the path.
Do not remove external servo power casually: prior power removal let the arm fall.
Any later attempt needs a separately recorded, reviewed installation attempt,
not overwriting the failed journal or weakening the movement's endpoint checks.

Reference: [Espressif bootloader sync troubleshooting](https://docs.espressif.com/projects/esptool/en/latest/esp32/troubleshooting.html#download-mode-successfully-detected-but-getting-no-sync-reply-the-serial-tx-path-seems-to-be-down).

## Separately authorized second attempt

The user subsequently said “proceed and accept next steps.” One new r27 attempt
is selected explicitly with `--approved-r27-second-attempt`; this is not an
automatic retry or a continuation of the consumed first journal. No cable change
has been confirmed. The exact failed journal is hash-pinned and preserved, and
the prior verified r26 installation and recovery export are checked offline.
The new exclusive journal is `app-r27-attempt2-deployment-events.jsonl`, and r27
installation evidence now binds only to this journal (no fallback).

The only connection change is the pinned esptool 4.6 vendor longer Windows reset
timing: hold boot selection for 0.55 seconds after reset instead of 0.05 seconds.
There is one reset/connect attempt; normal synchronization and all controller,
predecessor-image, filesystem and protected-region checks remain mandatory.
No flash write occurs before these checks. One verified app write and startup
are followed by authenticated idle checks and, only if fresh pose checks pass,
one shoulder-rise packet with three settled readbacks and durable exports.
No preparation replay, return, extra movement or automatic recovery is included.

## Second-attempt installation and actual shoulder trial results

The longer reset connected successfully. No cable-change claim is made and this
single success does not establish the first failure's root cause. App SHA and
full readback matched; all protected flash regions, settings and credentials
remained unchanged. The second journal completed all six installation stages.
One startup was performed and checked. Installation review:
`wizard-20260919T203759748134Z-170106edee2243fb93ff30f5ee0c9e39`.
Startup: `wizard-20260919T203800038410Z-a51dd3ec4b404e9a80894b4bc8924162`.
Boot: `681c7954a64a176cc0a833d1419c203a`.

The authorized trial sent exactly one synchronized shoulder packet. Its result
was partial correct-direction travel, **not successful arrival**:

| Servo | Fresh start | Requested target | Every post-command sampled position | Residual |
| --- | ---: | ---: | ---: | ---: |
| 12 | 2455 | 2443 | 2448 | +5 counts |
| 13 | 1659 | 1671 | 1667 | -4 counts |

Both goal registers matched the commanded targets. Eleven fresh scans between
332670 and4789727 microseconds after the packet had identical selected positions.
No sample qualified for the required two-count arrival tolerance. The elbow
changed2906 to2905 (within the unchanged-joint allowance); other sampled positions
remained unchanged. These are servo encoder observations, not measured tool-tip
displacement. Do not infer stylus accuracy or reliable clearance from them.

The controller reached `FAULT / RISE_OBSERVATION_DEADLINE`; the host stopped while
submitting the final sample's export receipt. The host's generic ValueError is
not itself the root-cause diagnosis. A separate retained-status GET established
the specific controller reason. There was no return, retry, extra packet,
explicit torque operation or compensation. The fault prevents further sequence
progression; it does not switch off torque or cancel the already issued targets.

Run: `wizard-20260919T203825127176Z-0533f1bb58ca40d3b5371679adc34cd4`.
Retained status: `wizard-20260919T203853177393Z-9558379d4ab34ad8a3e4eec1b34302d5`.
Offline analysis: `wizard-20260919T204001067014Z-6fb1866e5f264894a7ceed60ffeb5935`.
Reproduce using `python software/scripts/analyze_r27_shoulder_rise.py`: it verifies
the run/status/event exports and replays all14 events through the independent
endpoint reviewer before exporting its summary. No hardware access is used.
Installer/binding/runner/reviewer regression suite:141 passed this turn.

### Next investigation, before another movement

1. Extract existing raw speed/moving/load/voltage data, preserving documented
   register definitions and any unverified units; inspect for shared-load or
   deadband patterns. Correct goals plus actual travel narrow this beyond a
   wholly undelivered command, but do not identify the physical cause.
2. Review retained servo configuration evidence and supported read-only queries
   for deadband/control settings and pair behavior. Do not change persistent
   settings, loosen endpoint tolerances or fit compensation from one trial.
3. Plan the next bounded test from fresh measured positions **and goals**, not
   from the pre-test baseline. Account for retained target errors and board
   contact/clearance. Do not replay preparation or blind-home to90degrees.
4. Separate safe local movement evidence from accuracy acceptance. Increasing
   timeout alone is not a demonstrated fix for a plateau across eleven scans.
   Continue toward an upright pose only with a reviewed next increment and
   reliable readings; stop again on unexpected motion or uncertain feedback.

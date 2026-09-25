# r24 failure-capture retest

## Status

Approved scope completed: r24 installed, one startup and one initialization
attempt performed. The attempt stopped before any write with
SHOULDERS_NOT_PASSIVE. See [test result](R24_SHOULDER_INITIALIZATION_RESULT.md).
The earlier r23 STATE_CHANGED cause remains unknown; it was not reproduced.

## Narrow correction

r24 retains the already-acquired seven-joint scan when the consistency predicate
fails, publishing STATE_MISMATCH before latching FAULT. It adds no servo reads,
writes, retries, torque changes, or relaxed limits. It preserves requested goals,
measured positions, torque state and raw feedback for comparison with baseline.
This repairs missing evidence, not a demonstrated actuator or mapping defect.

Only shoulder_preload_session.h and shoulder_hold_event_json.h differ from the
pinned r23 stage. The internal command identifier remains r23-shoulder-hold;
the binary hash and installation receipt identify the actual revision.

## Frozen candidate

- App SHA-256: `fe3eaec72bb31f72210bec45912b8d5bb4df27adcb292a94decf15106a9436be`
- Size: 1,141,424 bytes; application offset: 0x10000.
- Compile: `wizard-20260919T185758302257Z-b668430bfac94f8d9ffc7f71299fe908`
- Offline review: `wizard-20260919T190009172686Z-bae43dbebbb0421eae0ffb450c050528`
- Application-slot headroom: 169,296 bytes. Largest reviewed individual stack
  frame: 496 bytes; this is not a whole-call-stack or runtime-resource proof.

## Approved execution scope (consumed)

One r24 app-only installation and one startup, preserving existing settings and
credentials, followed by one bounded shoulder initialization test with fresh
joint checks and failure-record export. No lift, automatic retry, return move,
or torque-off. Initialization may enable the shoulder pair only if the existing
fresh-pose and goal checks pass. A restart is not a home command.

## Procedure after approval

1. Bind deployment/startup and live-runner validation to this exact r24 artifact
   and review; verify predecessor, backups, protected regions and one-use journal.
2. Install app only, verify readback, perform the single startup and export idle
   checks. Stop on identity, integrity or startup mismatch.
3. Bind a new one-use session to the verified boot. Acquire fresh seven-joint
   baseline; never reuse the spent r23 session or old positions as targets.
4. Run the existing bounded initialization once. Export each event before its
   receipt. On FAULT retrieve the retained record read-only, export and stop.
5. Compare each joint's failing position, goal and torque with baseline and the
   expected completed-write state. Distinguish acknowledgment from goal readback
   and physical arrival. If the failure is different or absent, report that
   honestly rather than attributing a cause without evidence.
6. Review results before proposing any further movement or configuration change.

The gripper's board-contact pose remains relevant. This retest does not authorize
a blind upright reset, and does not establish physical clearance or tip accuracy.

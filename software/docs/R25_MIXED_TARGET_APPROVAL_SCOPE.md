# r25 mixed-target candidate: build review and proposed scope

## Status

**Approved scope completed.** r25 was installed and started once; the one target
test completed with three verified readbacks and exports. See
[physical result](R25_MIXED_TARGET_RESULT.md). The preparation notes below describe
the pre-installation state and are retained for audit, not current authority.

Staged, compiled and reviewed offline. Not installed. Controller remains on r24.
No hardware access, startup, movement or settings change occurred in this step.
The deployment/startup and live-runner bindings must still be pinned to this
reviewed image before execution; the current runner rejects mixed hardware use.

## Exact candidate

- App SHA-256: `483604c16de0b2061335873fdc176b90551e16e7552fcd2aa6058e6449bbde5f`
- App size: 1,142,688 bytes; offset 0x10000; slot 0x140000.
- Slot headroom: 168,032 bytes.
- Build: ESP32 default 4MB partition layout, PSRAM disabled.
- Compiler reports 97,736 bytes global variables; this is not measured runtime heap.
- Reviewed maximum individual stack frame: 496 bytes, not total stack usage.
- Partition and bootloader artifacts match the existing reviewed profile.
- Scope: `MIXED_TARGET`; command identity: `mixed-shoulder-target-v1`.

Only three staged headers differ from verified r24: shoulder_preload_session.h,
shoulder_authorized_start.h, shoulder_board_session.h. The board header explicitly
selects the mixed experiment at build time. Existing startup code is unchanged:
no automatic initialization, target write or torque command.

## Evidence

- Stage: `wizard-20260919T193804942126Z-044d801291fc466180b9f24f004d9f91`
- Compile: `wizard-20260919T193954046321Z-8795999b45a94b96b3392ff91af09e7f`
- Artifact review: `wizard-20260919T194020438681Z-a684c7bfc4bc436aa129248bc7e25155`
- Regression run: 67 passed, including native authenticated host/export bridging,
  both torque outcomes, board ingress in both modes, and fault-stop cases.

## Proposed explicit approval

One r25 app-only installation and one startup, preserving settings and credentials,
followed by idle checks and one mixed-shoulder same-position target experiment.
Allow at most one target write to the passive shoulder's freshly measured
position, preserving the enabled shoulder, followed by three readbacks and
verified exports. A target write may activate the selected servo. No explicit
torque command, lift, return, automatic retry or follow-on movement.

## Procedure after approval

1. Pin installer, installation evidence and startup review to the exact image,
   predecessor r24 and review above. Release only this mixed-mode revision binding;
   do not add a generic force override or permit mixed execution on r24.
2. Run local preflight and regression checks. Verify actual controller identity,
   predecessor image and preserved flash regions before the single app-only write.
3. Verify application readback and unchanged protected regions, then one startup.
4. Verify fresh idle boot and bind one command session to it. Capture initial
   seven-joint state; reject invalid/moving/unmatched enabled-joint states.
5. For exactly one enabled shoulder, preserve its target/torque. Export intent
   for the passive shoulder, reacquire the pose and reject changed assumptions.
6. Send one target write only after the verified-export receipt. Export its
   delivery evidence and three subsequent scans. On failure preserve available
   records and stop without retry or torque release.
7. Report whether the selected target was stored, whether measured position
   matched, and whether torque remained passive or became enabled. Neither
   outcome grants permission for another action.

This experiment establishes same-pose target behavior, not lifting readiness or
travel/stylus accuracy. Real elapsed export/transport timing and runtime resources
remain hardware observations to collect, not claims from the successful build.

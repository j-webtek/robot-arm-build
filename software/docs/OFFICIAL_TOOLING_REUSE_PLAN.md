# Official tooling reuse and host-driven characterization

Updated 2026-09-20. This is the current architectural direction for the bounded
motion characterization work. It does not authorize motion or replace fresh
pose/clearance checks. Preserve installed firmware, credentials and settings.

For the detailed forward implementation order, deliverables and completion criteria,
follow [Control to typing implementation plan](CONTROL_TO_TYPING_IMPLEMENTATION_PLAN.md).

## Decision

Freeze further campaign-related firmware expansion while comparing the existing
host transport with the official SDK. Keep useful firmware diagnostics, but put
test sequencing, endpoint analysis and exports on the computer where possible.
Do not delete experimental firmware code or erase earlier failed measurements.

## Compatibility audit: findings and choices

| Area | Existing implementation / official behavior | Decision |
| --- | --- | --- |
| JSON | `arm/protocol.py` already implements official JSON encoding | Reuse; no new wire language |
| Serial | `arm/serial_transport.py` has 115200 feedback transport; its live motion path is deliberately gated | Keep; do not bypass gates or silently enable motion |
| SDK | Official source retries failed requests; movement returns do not prove arrival | Reference/optional adapter only; no dependency added yet |
| HTTP | Official SDK feedback is serial-only; local diagnostic HTTP is different | Preserve local diagnostics; do not confuse ACK with measured arrival |
| Feedback | Existing raw paired-servo diagnostics distinguish accepted goals and positions | Retain where standard logical-joint feedback lacks the necessary evidence |
| Campaign | `shoulder_characterization_sim.py` already runs 12 synthetic legs and exports each stage | Reuse rather than introduce a second simulator |
| ROS/MoveIt | Official ROS 2 Humble workspace includes model, driver and IK/planning packages | Offline model evaluation after transport comparison; no auto-connected driver |
| Missions | Firmware JSON sequence playback exists | Defer until host-verified movements are repeatable |
| Wi-Fi / recovery | Official configuration and filesystem tools exist | Maintenance/onboarding only, not a movement-test prerequisite |

The r31 recorded +9/-7 count residual is historical evidence, not a current pose
or a universal correction. Coupled shoulders must not receive independently
fitted offsets that violate their mechanical relationship. Encoder accuracy is
not Cartesian stylus accuracy.

## Implementation sequence and acceptance criteria

1. **Audit and freeze (implemented).** Record reuse decisions here. No SDK install,
   firmware deployment or device opening in this step. Existing diagnostic work
   stays available. Do not finish the experimental firmware campaign transport
   merely because it was started.
2. **Batch review (implemented, simulation only).** Reuse existing simulator and
   exporter; independently reassess raw legs; group endpoint residual and spread
   by servo, target, approach direction, speed and acceleration. Retain failures.
   Reject corrupt bundles and do not accept live data under a simulation label.
3. **Existing live-interface comparison (source audit complete; build verification pending).** See
   [architecture and interface audit](CONTROL_ARCHITECTURE_AND_INTERFACE_AUDIT.md).
   r31's local owner is single-step, fixed-envelope and sticky-reserved, not a
   general campaign executor. Inspect r31 routes and current
   host clients against the exact installed build. Document which route exposes
   fresh samples, goal registers, command identity and paired reads. Inspect a
   pinned SDK revision without importing/opening hardware. Compare serial-open
   behavior, retry rules, units, error handling and feedback freshness. Choose the
   existing adapter unless the SDK demonstrably reduces maintenance. Review SDK
   AGPL licensing before copying/distributing code.
4. **Host campaign integration (pending).** Connect a finite host runner to the
   selected existing diagnostic interface. Preserve one writer, fresh baseline,
   bounded travel, no blind retries, and durable per-leg export. Do not claim
   stock angle feedback provides raw-servo freshness if it does not. If installed
   firmware lacks a necessary capability, document that exact gap before a change.
5. **Fixed-build physical dataset (pending).** First use the already reviewed
   local envelope; vary one factor at a time. Collect both approach directions,
   repeated identical targets, timestamps, transmitted command, accepted target,
   fresh positions, settling duration, available load/status and failed attempts.
   Record build/config identity; do not pool changed configurations. Stop on
   uncertain delivery or invalid feedback. Historical goals are not starting poses.
6. **Analysis and held-out validation (pending).** Compare constant offset,
   direction-dependent behavior and speed/load effects only when the dataset
   supports them. Use separate held-out movements before applying compensation.
   A small stable miss can be a measurement, not an automatic firmware change.
7. **Ghost keyboard / MoveIt (pending).** Validate Pro geometry, joint mapping,
   limits and tool offset against the official model. Add board and keyboard
   collision geometry. Plan approach/press/retract offline before executing through
   the verified host runner. Defer real contact and camera registration.

## Run the implemented offline review

From `software`, using the workspace Python environment:

```powershell
..\.venv\Scripts\python.exe -m rocell.application.characterization_batch_review --simulate --exports runs/wizard-exports
```

To re-review one existing synthetic campaign-result bundle:

```powershell
..\.venv\Scripts\python.exe -m rocell.application.characterization_batch_review --source runs/wizard-exports/EXACT-BUNDLE --exports runs/wizard-exports
```

Each invocation publishes a new diagnostic bundle; nothing is overwritten. The
review records the source manifest hash and includes `attachment-batch-review.md`
alongside machine-readable JSON. The built-in +9/-7 synthetic residuals
are test inputs, not newly measured hardware results. No SDK import, serial port,
network request, torque command or firmware operation occurs. The CLI is usable
now; wizard UI wiring and a live evidence importer remain pending.

## Official references

- SDK: https://github.com/waveshareteam/waveshare_roarm_sdk
- Communication source: https://github.com/waveshareteam/waveshare_roarm_sdk/blob/main/roarm_sdk/roarm.py
- M3 API: https://github.com/waveshareteam/waveshare_roarm_sdk/blob/main/doc/roarm_m3_zh.md
- ROS workspace: https://github.com/waveshareteam/roarm_ws/tree/ros2-humble
- JSON: https://www.waveshare.com/wiki/RoArm-M3-S_JSON_Command_Meaning
- Missions: https://www.waveshare.com/wiki/RoArm-M3-S_Step_Recording_and_Reproduction
- Wi-Fi: https://www.waveshare.com/wiki/RoArm-M3-S_WIFI_Configuration
- Filesystem: https://www.waveshare.com/wiki/RoArm-M3-S_FLASH_File_System_Operation

Research reviewed upstream main; that is not a pinned deployment dependency.

## First implementation validation

- 34 focused tests passed: batch review, existing simulator and classification.
- Actual offline CLI invocation completed all 12 synthetic legs and verified its
  review export at `runs/wizard-exports/wizard-20260920T043539045436Z-c99464c20548462a92ac2621150e1c5d`.
- Six target/direction groups contain 24 paired-servo observations. Injected
  +9/-7 count errors remain visible despite zero within-group endpoint spread.
- No physical commands, SDK installation or firmware changes occurred.
- Local inspection identifies `ShoulderSessionHTTP` as an existing no-retry
  adapter with shoulder-session, local-step and settling route families. Its
  responses are explicitly unauthenticated; do not describe it as the newer
  authenticated campaign transport or presume every route is installed.
- This workspace has no Git repository at its root; files were saved, not Git-committed.

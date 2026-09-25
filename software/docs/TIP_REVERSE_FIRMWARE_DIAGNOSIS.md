# Reverse tip movement: firmware and evidence review

Reviewed 2026-09-17, after the 18:34 UTC reverse trial. No movement, firmware
installation, servo-register writes or torque changes were performed for this review.

## Findings

### Served interface inspection, 18:45 UTC

Read-only root-page export verified:
`wizard-20260917T184526089377Z-37a82dfd581a4032bd90927e00bec210`.
Page size 54,153 bytes; SHA256
`2f93fdc878a0ecc24d8e6e3a3c5803184165a6d2ec3cf265d86c41e2408e75e8`.
The page was read as text; none of its scripts or startup actions ran.
Its `getData()` (lines 1070-1097) sends T105 through XMLHttpRequest and parses
the HTTP response as telemetry. Thus the installed page explicitly expects the
HTTP feedback style we observe. This is evidence against blindly replacing our
transport with the newer reference WebSocket path, not proof of fresh servo reads.
The page's `getDevInfo()` calls `/getDevInfo`; one read-only request returned 404
(22 bytes, SHA256 `cb9cecc1145d2cb3c4e9d9a95551518872bb2701930b02b1fa8ef54cc836ae66`).
No installed firmware version was established.

The current official SDK documentation describes HTTP as control-send-only and
serial for feedback:
https://github.com/waveshareteam/waveshare_roarm_sdk/blob/main/doc/README.md
This applies to that SDK/interface and is not proof this older HTTP interface is
invalid. An independent serial read is a useful next discriminator if available;
opening serial can reset the controller, so inventory ports before opening any.
Do not install the SDK or invoke its constructor/initialization blindly.

### Additional packet/interface findings, 18:43 UTC

Verified packet review export:
`wizard-20260917T184345852055Z-3b065b49a62d4f378c11242cc4e546e8`.
All 31 retained packets from the T101 diagnostic have identical decoded content.
Elbow position is 1.67357304 and raw `tE` is 45 throughout. `torswitchE` and `v`
are absent in every packet. Raw load 45 is not a calibrated force or health
threshold. Identical content cannot distinguish a stationary servo from cached
acquisition. The new packet audit verifies each original response hash; 26
focused packet/trace/candidate tests pass.

Reference HTTP source differs materially from the observed interface:
`http_server.h:36-61` queues commands and returns `{\"ok\":1}`, while
`RoArm-M3_example.ino:179-189` executes queued commands and publishes telemetry
over WebSocket. Our arm returns numeric T1051 telemetry directly in HTTP.
The verified archive therefore must not be treated as an exact installed
implementation. `uart_ctrl.h:60-63` calls acquisition for T105 in the reference,
but that does not establish what this installed HTTP handler does.

Next read the arm's served interface/version clues without running page scripts
or sending motion/configuration commands. Compare its documented/read-only
feedback behavior with available source. Do not flash firmware, switch command
transports for motion, or treat repeated HTTP success as proof of fresh servo
reads. A distinct installed interface may explain differences, but causation
remains unproven.

The host command audit matched the reserved command to the transmitted payload
hash and reproduced its expected joints. The elbow reference target was count
2105, from baseline 2113; reported final count was 2115. This is not explained by
a one-count rounding discrepancy. It does not prove what was written on the bus.

The official reference archive was downloaded in memory and its SHA256 checked:

- URL: https://files.waveshare.com/wiki/RoArm-M3/RoArm-M3_example_20260701.zip
- SHA256: `a28247fee0bbb65cc034ff206031b8700d2b1ec8e3a1fa4b1a5a7365c55f1a57`
- This is reference source, **not verified installed firmware**.

| Source location | Finding | Consequence |
| --- | --- | --- |
| `RoArm-M3_module.h:51-53,353-360` | Elbow feedback subtracts pi/2; goal conversion adds 1024 counts. Both are increasing mappings. | No sign reversal found in this reference conversion. |
| `RoArm-M3_module.h:770-797` | T101 single-joint control calls the selected servo write with explicit speed/acceleration. | Existing T101 trials at 20/1 are a distinct control mode. |
| `RoArm-M3_module.h:749-758` | Cartesian motion uses shared `moveSpd` and `moveAcc` arrays in synchronous writes. | Passing zero arguments to the conversion helpers does not prove the bus acceleration is zero. |
| `RoArm-M3_config.h:99,262-269` | Initial shared speed is zero and acceleration is 20. | Correct prior shorthand that described T104 as unconditionally speed/acceleration zero. |
| `RoArm-M3_module.h:825-840,1217-1223` | Other all-joint paths change those arrays; one resets them to zero, another leaves assigned values. | Effective T104 servo settings can depend on prior commands. Current installed settings are unknown. |
| `RoArm-M3_module.h:895-936` | T104 interpolation has an explicit final target write. | No missing-final-write defect demonstrated in this source. |
| `RoArm-M3_module.h:72-100,625-642,648-675` | Failed servo reads leave the old position; ordinary joint feedback does not expose per-read acquisition status/timestamps. | Fresh HTTP responses and internally consistent FK do not prove fresh encoder acquisition. |

The T104 `spd` value controls interpolation progression, not a calibrated physical
speed or the shared servo settings. No claim that this difference caused the
observed error is justified yet.

## Earlier isolated elbow evidence

Verified exports:

- `wizard-20260917T163506671259Z-de320d9a030045a3a03e24bfa4bff6a7`
- `wizard-20260917T164028812312Z-ede1be83a00144d48545ebaea698d838`

Both requested T101 joint 3, rad 1.4758599604002836, speed 20, acceleration 1,
from elbow 1.563126423. Both retained final elbow 1.523242922: decreasing motion
was reported, but not arrival at the wire target. The first has a runner error;
the second does not. Neither is a clean physical accuracy measurement. Their
shoulder was zero and wrist .053689328, unlike the recent tip experiment.
Therefore a globally reversed elbow mapping is not supported, and these older
corrections cannot simply be transferred to the current posture.

## Next discriminating experiment

### Executed result, 18:41 UTC

The separate T101 comparison below was executed once after preview/tests/fresh
admission. Export `wizard-20260917T184148463017Z-fc3474830b1d4836b6df550bad581717`
verified: 31 samples, no runner error, no reported joint change. Elbow stayed at
count 2115 against predicted goal 2105. Endpoint failed, 4.961219 modeled mm.
No repeat or return followed. Thus T104-only behavior does not explain all the
evidence. Next use retained telemetry and supported read-only servo diagnostics
to distinguish actuator response from acquisition/configuration issues before
another movement. The experiment description below is historical, not a retry.

Keep the failed reverse sequence stopped. Prepare a **separate elbow-only T101
diagnostic** with explicit 20/1 settings, targeting the prior reverse trial's
elbow goal (1.6579063063032675 rad) from fresh matching current feedback. Preserve
all other joint goals; screen the elbow-only arc and hypothetical tip sweep.
This compares command modes at a nearby posture, not a perfectly controlled
repeat of the coordinated movement, since the wrist has already changed.

Before sending: bind one command and its starting pose, test endpoint/fault
handling, and export the preview. After sending: retain the exact command,
receipt, feedback trajectory, direction, settling and final residual; no automatic
retry, correction or return. If opposite response recurs, stop movement and
investigate servo acquisition/installed configuration rather than fit an offset.
If the direction is correct, use the evidence to plan a bounded fixed-endpoint
experiment; a single correct-direction response does not qualify compensation.

Do not change firmware, acceleration arrays, gains, torque or servo calibration
as part of this diagnostic. Camera/contact work remains deferred.

# Revision 3 baseline-scan application: deployment proposal

Status: user explicitly approved the proposed r3 installation and USB-only startup.
Execution completed successfully; see `BASELINE_SCAN_R3_DEPLOYMENT_RESULT.md`.
The remainder records the approved scope, not instructions to repeat the write.
Execution and verification results must be recorded separately; approval alone
does not establish installation. No baseline POST or movement is authorized here.

## Why this update

The arm dropped when motor power was removed. The user reports no damage, but the
old pose is no longer a valid starting assumption. Revision 3 adds a standalone
read-only baseline scan so joint target/position feedback can be acquired without
submitting a guessed motion target or provisioning a motion policy/key.

## Exact installation scope proposed

- Controller MAC: `FC:E8:C0:F8:D5:38`; recheck identity and USB port before writing.
- Application: `.firmware-tools/build-configured-diagnostic-candidate-r3--default-4mb-no-psram/RoArm-M3_example.ino.bin`.
- Offset `0x10000`; length 1,076,384 bytes, inside the 1,310,720-byte app0 slot.
- SHA-256 `46e23efb7f9f18557882b1b185ecf4874ba4b2123ef64867f3a2831c56e01ee1`.
- Sector erase range `0x10000` through `0x116fff` (exclusive `0x117000`).
- Preserve bootloader, partition table, OTA data, app1, NVS and LittleFS during
  flashing. Normal Wi-Fi startup can subsequently update NVS internally.
- Require current app readback to match the installed r2 image before overwrite.
  Retain r2 binary and original verified backups as recovery evidence. Do not
  automatically restore, retry writes or erase the chip on failure.
- Verify full new app readback and unchanged regions outside app0 before one
  deliberate USB-only startup. Then check passive diagnostic status and export.
- No policy/key provisioning, servo configuration, motion commands, baseline POST,
  or motor-power restoration is included in this installation proposal.

## Physical condition

Keep moving links resting securely on supports and main motor power disconnected;
USB supplies the controller. The base clamp alone does not support moving links.
Do not unplug holding power from an unsupported arm or restore it to lift the arm.
The post-drop mechanical inspection and powered acquisition setup remain separate
from this controller-only installation stage.

## Evidence and limitations

Build export: `wizard-20260918T142539650146Z-b647003206cc4cd190819583d13e6be8`.
Compilation succeeded with the verified 4 MB default partition layout, PSRAM off.
Sketch: 1,069,801 bytes; static RAM: 121,784 bytes; remaining static budget 205,896.
These are compiler figures, not runtime endurance evidence.

Simulation tests exercise the actual generated motion challenge and baseline
owner/routes. The shared one-session claim prevents baseline and motion ownership
in either order, including failure. A baseline POST queues one acquisition; a
GET retrieves stored evidence without another acquisition. Pair errors stop before
later joints; no automatic rescan or movement follows. The host records a durable
per-endpoint/boot claim before POST, exports preparation/results, and preserves
uncertain delivery without resending. Tests include lost reply and export failure.

The HTTP interface is LAN-only by intended deployment, not cryptographically
authenticated. A baseline request can consume the session, but cannot authorize
motion. Do not expose these services to the public Internet. Scans are sequential,
not simultaneous, and cannot prove stylus-tip accuracy, current clearance, or
freshness at a later movement. Native and simulated evidence is not live servo
validation. Existing main status describes the motion runtime; baseline results
are obtained through the separate baseline route, not inferred from IDLE status.

## After installation, separately

Review mechanical condition/support and safe servo power-up. Then explicitly
perform one baseline-only acquisition, review all retained evidence and select
bounded test windows from actual positions. A baseline claim disables motion for
that boot. Motion provisioning/testing belongs to a later reviewed session.

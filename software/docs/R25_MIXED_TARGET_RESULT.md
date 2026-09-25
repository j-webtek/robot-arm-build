# r25 physical same-position target experiment — completed

## Result

The approved r25 app-only installation, single startup and single mixed-target
experiment completed successfully. Exact application readback matched and
protected regions were unchanged, preserving settings and credentials.
115 host/installation/integration regression tests passed before deployment.

One target command was sent to shoulder servo13: target1659, speed20, acceleration1.
The command returned success with device_error0. Three later fresh seven-joint
scans each reported servo13 position1659, goal1659 and torque1. Before the command
servo13 was at1659, goal0, torque0. All six events were independently reviewed,
exported and acknowledged by command-bound authenticated export receipts.
Controller terminal: COMPLETE / TARGET_OBSERVED_ENABLED, writes1,
enable_delivery NOT_ATTEMPTED. Host terminal: MIXED_TARGET_OBSERVED.

No explicit torque command, lift, return, retry or follow-on movement was sent.
The target write was potentially actuating, as expressly approved.

## What we learned

In this observed trial, writing the current-position target was followed by the
selected servo's torque register changing from0 to1, without a separate torque
enable command. The previous assumption that a target preload necessarily leaves
torque disabled is not valid for this observed hardware path. This supports an
explanation for the earlier post-preload consistency fault, but does not recover
its missing historical scan or establish the internal servo mechanism.

Measured state at the final readback (register counts):

| Servo | Position | Goal | Torque |
|---|---:|---:|---:|
| 11 | 2047 | 0 | 0 |
| 12 | 2455 | 2455 | 1 |
| 13 | 1659 | 1659 | 1 |
| 14 | 2906 | 2907 | 1 |
| 15 | 1589 | 0 | 0 |
| 16 | 2040 | 0 | 0 |
| 17 | 2047 | 0 | 0 |

Other joints' positions, goals and torque states stayed unchanged through the
captured sequence. Both shoulders now had matched target/position registers.
This was a same-position test, not proof of travel accuracy, tip accuracy or
whole-arm readiness. Passive joints and board contact remain relevant.

## Reproducible evidence

- App SHA-256: `483604c16de0b2061335873fdc176b90551e16e7552fcd2aa6058e6449bbde5f`
- Installation: `wizard-20260919T194703360921Z-779daa770f574586944c36928ffc53a9`
- Startup: `wizard-20260919T194703726140Z-de982ade1b10412bb77447d70df38eb2`
- Boot: `45a8a8cc10693e7050eced442c8f5a20`
- Run and references to six event exports:
  `wizard-20260919T194718320297Z-00101cd1b26b47f2bc355d286ce9174b`
- Session is consumed; do not rerun this mixed-state initializer against the
  now-enabled pair or automatically restart it.

## Next work

Use an enabled-pair movement procedure, not passive initialization. Review the
paired shoulder mapping and a small increasing-clearance target change from a
fresh all-joint pose; account for other passive joints. Simulate the exact command
and endpoint checks, then propose a separately scoped one-way movement. Compare
requested target, readback target and actual measured position throughout, with
no automatic return before verified arrival. No further action is covered by the
completed approval.

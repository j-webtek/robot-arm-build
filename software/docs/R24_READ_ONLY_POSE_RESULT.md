# r24 read-only pose capture result

## Completed scope

One startup of the existing r24 image, idle checks and one three-snapshot pose
capture completed. No firmware installation, settings write, target command,
torque change, hold or follow-on movement was sent. The capture terminal reports
three snapshots and zero actions. External servo power was not cycled.

## Measured register state

All values below are encoder/register counts, not Cartesian coordinates.

| Servo | Position | Stored goal | Torque enabled | Position span, three scans |
|---|---:|---:|---:|---:|
| 11 | 2047 | 0 | 0 | 0 |
| 12, shoulder | 2455 | 2455 | 1 | 0 |
| 13, shoulder | 1659 | 0 | 0 | 0 |
| 14, elbow | 2906 | 2907 | 1 | 0 |
| 15 | 1589 | 0 | 0 | 0 |
| 16 | 2040 | 0 | 0 | 0 |
| 17 | 2047 | 0 | 0 | 0 |

Assessment: STABLE_SAMPLED_POSE. Goals, modes and torque states were unchanged;
the assessment also checked zero moving flags. This establishes sampled encoder
stability, not physical clearance, torque/load safety or stylus accuracy.

## Finding and implications

Shoulder12 is enabled and at its target. Shoulder13 is passive with a zero stored
target. This mixed state explains the recent SHOULDERS_NOT_PASSIVE rejection.
The software's passive-only entry assumption does not match the measured state.

Shoulder12's goal equals the earlier r23 preload target, while shoulder13 has not
received that preload. This is consistent with a transition associated with the
earlier attempt, but the discarded r23 failure scan means the timing and cause
of the torque transition remain unproven. Do not label internal servo behavior
as established, and do not conflate the later capture with the historical fault.

## Next implementation decision

Replace the one-size-fits-all passive entry path with explicit classifications:
passive, already enabled and tracking, or mixed. For this mixed case, review a
procedure that preserves shoulder12's matched target and torque, establishes
shoulder13's goal from a fresh measured pose before any enable, and verifies
both shoulders and neighboring joints after each operation. Account for the
possibility that a target write may coincide with torque activation; do not rely
on the word "preload" as a guarantee of a passive actuator.

Do not issue a naked torque-enable to servo13 with its zero goal. Do not disable
shoulder12 solely to satisfy the old initialization predicate. Validate the
mixed-state transition offline and review the exact bus operations before a new
bounded physical trial. No such transition is authorized by this capture scope.
The gripper's board-contact pose still constrains subsequent movement direction.

## Reproducible evidence

- Startup action: `wizard-20260919T191820176094Z-6e7abb62cf0a4d1e8d277e544d8f47b3`
- Idle checks: `wizard-20260919T191843142112Z-b7ccb4ddbabb40b2b2cc552855ce4e2d`
- New boot: `29286bc0ea72c76c74e234c4efc96ac9`
- Raw snapshots and assessment: `wizard-20260919T191851996517Z-3ba383b2c1d94cc284d9ab10fc6e7d58`
- Capture run: `wizard-20260919T191852048369Z-ec4479bb585244478bfe12f5420049bd`

Nineteen pose CLI/capture tests passed before execution. The startup helper used
the pinned reset implementation, matched the known USB adapter, checked the
expected old fault twice, and reserved the startup before opening the port.
No retry was performed. The new boot is now reserved by this observation session;
capture completion does not release it for actuation or reset it automatically.

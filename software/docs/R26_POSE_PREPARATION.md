# r26: finite preparation before shoulder lift

The user's current approval includes reviewed firmware updates, installation,
startup, and bounded testing toward a taller posture and approximately 90-degree
elbow. This revision addresses passive auxiliary joints before lifting; it does
not itself execute the lift or write settings.

## Exact image and evidence

- App SHA-256: `2a17bdf5a24cb1a3032d0212ca3c2db11d1f6a5b2027fdaf45b44f9c5e4f3c78`
- App bytes: 1,143,376; offset `0x10000`; slot `0x140000`.
- Stage: `wizard-20260919T200101089928Z-4bda40e9710644eb942c350ed5a7dad3`.
- Compile: `wizard-20260919T200324042010Z-eb4518e4effe49daa764f35ea98090d6`.
- Review: `wizard-20260919T200403483537Z-a7939864da8a496495e83327ce28caca`.
- Expected predecessor: r25. Existing filesystem/credentials remain unchanged.
- Largest reviewed individual compiled stack frame: 496 bytes. This is not a
  bound on the full call stack. Static globals: 97,736 bytes.

## Finite behavior

Signed scope `POSE_PREPARATION`, command `pose-preparation-v1`. Exclusive servo
ownership remains reserved through completion/failure. Select passive auxiliaries
in order 11,15,16,17; skip already-enabled ones. Require shoulders12/13 and elbow14
enabled, stationary and tracking. No automatic startup target writes.

For each selected joint:

1. Capture/export a seven-joint baseline.
2. Capture/export a fresh same-position target intent, speed20, acceleration1.
3. Reacquire state after the export receipt. Write once only if the selected
   position still equals the intended target and neighbors remain consistent.
4. Export the action's pre-write snapshot, acknowledgement/error and timestamps.
5. Acquire/export three independent later readbacks. Require the target register,
   stationary position within two counts, stable enabled state by completion,
   unchanged neighbors, and a two-second post-action/receipt deadline.
6. Only after the third record's durable export receipt may the next joint begin.

At most four target writes and 24 records. No explicit torque command, retry,
return, homing, EEPROM write or contact command. Target writes may activate servos;
this is deliberately not described as passive preloading. Any uncertain delivery,
feedback error, unexpected state, or failed export stops further writes.

## Validation and limits

87 targeted native/host tests passed, including a complete four-joint run and
authentication, receipt, delivery, drift, neighbor, read-failure and passive-state
faults. A separate 110-test installation/binding regression group passed. Frozen
r23 dispatch tests now compare with their recorded r23 build, not evolving source.

This procedure can verify observed encoder/target/torque state. It cannot prove
board clearance or Cartesian accuracy. The next movement must preserve the
measured shoulder-pair relationship and increase clearance first. Do not force
the observed pair sum to the reference model's nominal sum.

## Live result

r26 was installed once, read back in full, and started once. Protected regions
matched before/after. Installation export:
`wizard-20260919T200857808752Z-65c98571b1134ec1bb4c7c0dc0ee9e54`.
Idle startup export:
`wizard-20260919T200858235924Z-548f2c437fa74c999f74c34d4b0fbda7`.
Boot: `2711b0935621810cdaf52494b186395b`.

Run: `wizard-20260919T200919412755Z-f3ea3f2f6f2c458aa7bde1c4473e8474`.
Four same-position writes were acknowledged with device error0:

| Servo | Target | Three positions | Three torque states |
|---|---:|---|---|
| 11 | 2047 | 2047,2047,2047 | 1,1,1 |
| 15 | 1589 | 1589,1589,1589 | 1,1,1 |
| 16 | 2040 | 2040,2040,2040 | 1,1,1 |
| 17 | 2047 | 2047,2047,2047 | 1,1,1 |

All 24 event records were exported. No encoder position changed across the
records. The final selected-joint scan ended 1,540,574 microseconds after its
write, within the two-second acquisition window. However, the controller faulted
at sequence23 while awaiting the final export receipt: the same two-second timer
incorrectly continued to govern the host's terminal persistence work.

Read-only retained status export:
`wizard-20260919T201004067671Z-d3f08b8fb1684bcc8ade3f6168b1d290`.
Reason: `MIXED_OBSERVATION_DEADLINE`, four writes, no explicit enable command.
The host result is STOPPED, not a successfully completed session. Do not retry
these writes or claim a terminal success. The retained samples do establish
observed prepared target/torque state, subject to a fresh baseline before motion.

Next revision separates final export waiting from sample acquisition deadlines
and exercises the already-held state with one small mirrored shoulder rise.
It must not replay the passive-joint preparation simply to clear a software fault.

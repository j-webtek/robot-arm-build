# r24 approved installation and shoulder test result

## Outcome

The approved single app-only installation, single startup and single shoulder
initialization attempt are complete. The test stopped at initial admission with
`SHOULDERS_NOT_PASSIVE`, before any target preload or pair-enable command.
No lift, retry, return movement or torque-off was performed.

## Evidence

- Installed app SHA-256: `fe3eaec72bb31f72210bec45912b8d5bb4df27adcb292a94decf15106a9436be`
- Full application readback matched; protected flash regions were unchanged.
  Settings and credentials were preserved.
- Installation: `wizard-20260919T190726654387Z-277f4b6bfabe41d899b367ac221cb5ef`
- Startup: `wizard-20260919T190727196416Z-988e17aaf7284979baf78516e7ce3652`
- Boot: `ccf3154e75bdacbc513173ec0dacd8bf`
- Startup showed IDLE / NOT_CONFIGURED, zero records, no storage fault.
- Test: `wizard-20260919T190745612497Z-0265ac75683742dbb34a19c08a61c9ec`
- Controller result: FAULT / SHOULDERS_NOT_PASSIVE, sequence 0,
  preload_writes 0, enable_delivery NOT_ATTEMPTED, record_available false.
- 114 regression tests passed before deployment. The runner's additional r24
  fault-retrieval regression passed with its seven existing tests.

## What this establishes

The initial complete servo scan reported nonzero torque enable for shoulder12,
shoulder13, or both. The predicate checks torque registers, not whether the arm
looks stationary. The test did not reproduce r23's post-preload STATE_CHANGED:
it stopped earlier because the initial state differed.

The r24 correction retains post-preload consistency failures. It unfortunately
does not retain a baseline rejected for SHOULDERS_NOT_PASSIVE. Therefore the
export establishes the rejection reason but does not identify which shoulder
was enabled or retain its exact position/goal. Do not claim otherwise.

Offline source inspection found no servo reads/writes in diagnostic startup.
SCServo WritePosEx writes seven bytes beginning at acceleration address41,
while EnableTorque separately writes address40. This does not establish servo
internal behavior or explain when torque changed. Prior writes, servo behavior,
power history and feedback validity remain hypotheses, not findings.

## Next step

Do not force torque off to satisfy this passive-only initialization path and do
not rerun this spent boot. Preserve complete initial-pose evidence for every
baseline rejection, then review a read-only diagnostic path before further
actuation. Determine exact torque, goal and actual position for both shoulders
and all neighboring joints. Only then decide whether the appropriate next step
is passive initialization or an already-enabled observed-pose procedure.

Any new deployment/startup requires a new explicit scope. No further hardware
action is included in this completed approval. Upright recovery remains undone.

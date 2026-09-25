# Staged micro-command admission

## Implemented

`software/src/rocell/safety/micro_command_admission.py` adds a separate staged
admission without changing `WifiDispatchReservation` or its >0.5-degree guard.
It is not registered with a native sender or the wizard.

- Rechecks the predecessor manifest digest and export integrity.
- Reconstructs endpoint verification from original feedback bodies and compares
  it with the saved verdict and rows.
- Requires exactly one 0.95-degree joint-5 command, speed 20, acceleration 1,
  one attempt, and a complete unchanged six-joint hold (response span >=34 s,
  maximum response gap <=1 s).
- Requires predecessor reported roll within 1.35–1.45 degrees.
- Requires pinned-device original baseline feedback after that hold, within
  30 seconds, with the exact same reported six-joint pose and <=1-second age.
- Persists a unique staged intent with the fixed 0.90-degree command in radians,
  then consumes it durably once. Any failed consumption burns the process object.
- Rechecks predecessor and staged-record integrity before consumption; rejects
  wrong command, identity, timestamps, cancellation and another process.
- Returns audit metadata only. No sender bytes or `claim_native_send` method.

## Verification performed

27 focused tests passed across staged admission, micro-policy and command-strategy
simulation. Tests cover consumed/failed intent reuse, wrong units/command, changed
record/predecessor, cancellation, identity and baseline/timing checks. Unit tests
inject synthetic evidence; they do not exercise a device.

Read-only replay of real exports additionally showed:

- `wizard-20260917T025715945095Z-9f59e4d30a7d4fe58b45c4e99c2be4b4`:
  historical 1.40625-degree endpoint accepted as structural evidence.
- `wizard-20260917T034358977385Z-f3689f51e42f4bec9cada371e0b6b6b3`:
  1.23047-degree endpoint rejected as outside the experimental starting range.

Neither saved export was used to create live authority or dispatch a command.
No arm movement, live configuration update or physical accuracy claim occurred.

## Remaining before live integration

The offline post-command verifier is now implemented; see
[verifier status](MICRO_ENDPOINT_VERIFIER_STATUS.md). Native composition and
transaction-bound timing/ownership remain unfinished.

Native dispatch is deliberately disabled (`native_enabled=false` and
`motion_authorized=false` in staged records and receipts). This is NOT a completed
live admission path. Numeric timestamps and matching poses cannot establish that
the prior actuator setpoint is still current. Host clock continuity and ownership
must be established by a same-session controller rather than inferred from files.

The existing Windows transport mutex only covers cooperating local processes.
It cannot exclude the arm's web UI, external SDK clients or another computer.
Document the exclusive-controller commissioning assumption explicitly and keep
ownership from the new predecessor trial through the possible single micro-step.
Do not silently label that assumption proven by the mutex.

Next implement and test a dedicated post-command verifier: bounded excursion,
other-joint drift, deadlines, settling, signed displacement and before/after error.
Receipt alone must never count as endpoint evidence. Preserve unchanged/out-of-band
outcomes as experiment results, without retry or automatic return. Then compose
the same-session ownership, staged admission, one-use native send boundary,
verifier, passive hold and export through a separate explicit wizard action.
Recheck expiry at the actual send boundary after all potentially slow replay work.

Do not use this class as a way to bypass the existing admission. Additional
durability-failure/process-ownership tests and integrated original-body verifier
tests remain necessary before any live integration.

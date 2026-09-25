# Continuous cooperative micro-control session

Implemented `safety/micro_control_session.py` and integrated its optional staged
boundary into the offline transaction simulator. **62 focused tests passed**
across session, admission, transaction, endpoint/original-body and wizard suite.
No hardware access or arm movement occurred. Native micro dispatch is disabled.

## What the boundary checks

- One process and thread, one non-reusable context-manager lease.
- Predecessor intent recorded before its reported dispatch time.
- Replay-validated predecessor completion before admission creation, all within
  the same continuously held scope. Old predecessor exports cannot satisfy a
  newly started session by themselves.
- Exact fixed-command bytes and successfully persisted one-use consumption.
- No duplicate staged boundary claim, cancellation or clock reversal.
- Baseline freshness rechecked AFTER consumption-record disk verification.
- Context exit releases the lease on success or failure and prevents reopening.

The staged admission now exposes detached context and verified consumption
metadata. Its predecessor replay retains dispatch time for session binding.
Transaction integration verifies that the virtual boundary claim and virtual
dispatch use the same timestamp, then continues through endpoint, hold and export.

## Verified failure cases

Old predecessor, expired intent, reversed clock, changed thread, unconsumed intent,
wrong payload, cancellation, altered consumption file, slow disk verification and
lease acquisition failure all reject continuation. End-to-end simulation retained
the lease through result export and recorded zero native sends.

Unit tests use a synthetic lease, virtual clock and synthetic predecessor metadata.
They do not prove that a physical predecessor happened while a native mutex was
held. The existing raw predecessor replay remains responsible for original-body
validation; the session adds timing/ownership checks, not another physics model.

## Limits and next integration

This is cooperative ownership, not exclusive external control. A lease factory
must be supplied by a reviewed composition; the object cannot prove that an
arbitrary injected lease is the Windows arm mutex. Nor can that mutex exclude
the arm web UI or other computers. The staged claim remains explicitly
`native_enabled=false`, `motion_authorized=false` and
`exclusive_external_control_proven=false`.

Remaining: compose the real Windows lease over the predecessor command, hold,
export, fresh baseline and possible micro attempt; add a dedicated one-use native
send boundary with immediate identity/expiry checks and bounded HTTP deadlines;
poll feedback under real deadlines; retain/export through the wizard. Do not
reuse the simulation function as a hardware runner or broaden the existing
native sender's accepted reservation type without that dedicated integration.

The latest historical endpoint was already near the desired target. Future
commissioning must obtain fresh evidence and must not repeat predecessor moves
until an out-of-band starting condition appears. If the new predecessor is in
band, report that no correction is needed and send no micro-command.

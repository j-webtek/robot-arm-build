# Production controller runtime contract

This is the offline acceptance contract for the separate production runtime
that will eventually replace diagnostic-only controller applications such as
r96. It defines how planned commands cross the final arm boundary without
making model output, a planner result, or valid JSON equivalent to permission
to move.

The current implementation is a zero-I/O rehearsal. It cannot open a transport,
install firmware, restart the controller, send bytes, or move the arm.

## Startup behavior

Every new runtime instance begins in `SAFE_IDLE` with:

- zero startup movement commands;
- no writer owner;
- no automatic retry or replay;
- no transport or hardware access; and
- no execution or physical authority.

Startup never restores an unfinished command. A restart after a writer claim
enters `TERMINAL_LOCKED` with `RESTART_RECONCILIATION_REQUIRED`; a separate
observed-state reconciliation is required before any future session.

## One writer and ordered frames

Exactly one writer may claim a runtime instance. Every `T=102` frame binds:

- the writer instance;
- controller session and configuration epoch;
- exact encoding-profile hash;
- correlation ID;
- strictly increasing sequence number;
- issue and expiry times; and
- exact wire-byte hash.

The runtime accepts sequence 1, then 2, and so on. Duplicate, skipped,
out-of-order, foreign-writer, stale, future, wrong-session, wrong-epoch, or
wrong-profile frames lock the runtime terminally. They are never retried.

## Exact protocol surface

The command parser permits only deterministic compact newline-framed `T=102`
messages with fields in this exact encoding order:

```text
T, base, shoulder, elbow, wrist, roll, hand, spd, acc
```

All six joint targets must be finite numbers. `spd` and `acc` remain opaque
firmware settings with the existing explicit integer bounds; they are not
treated as physical speed or acceleration units.

After each admitted command, the runtime accepts only this exact canonical r97
acknowledgment before another command or feedback request:

```text
T, status="ACCEPTED_ONCE", ordinal=<pending sequence>
```

The acknowledgment proves only that r97 reached its single group-write call and
accepted that ordinal once. It does not prove servo arrival, contact, or task
success. A missing, stale, duplicate, reordered, malformed, or wrong-ordinal
acknowledgment terminally locks the session as uncertain; the command is never
retried.

Once no command acknowledgment is pending, the feedback rehearsal accepts only
the exact `{"T":105}\n` request and one
bounded, newline-terminated `T=1051` response containing all six joint fields:

```text
b, s, e, t, r, g
```

It reuses the shared duplicate-field, malformed JSON, reset-banner, response
type, length, and typed-value checks. A failed feedback exchange locks the
runtime without retry.

## Model and planner integration

The AI workstream continues to output target proposals, not servo commands.
The arm workstream remains responsible for transforming and validating those
proposals, producing a measured trajectory envelope, applying the qualified
joint mapping, and creating the exact hash-bound `T=102` frames.

The final relationship is:

```text
model target proposal
  -> shared ingress and calibration gates
  -> collision-screened measured trajectory envelope
  -> qualified zero-write T=102 encoding profile
  -> sole-writer ordered runtime frame
  -> production runtime admission
  -> separately authorized transport (not implemented here)
```

Thus the model cannot bypass calibration, collision screening, controller
qualification, sequencing, deadlines, or sole-writer ownership.

## What remains before physical use

1. Implement the same state machine and capability manifest in a separate
   controller firmware candidate with no startup movement.
2. Compile it reproducibly and independently review source plus linked image.
3. Prove runtime self-attestation of app hash and configuration epoch.
4. Bind it to independently reviewed protocol and joint-mapping evidence.
5. Pass the installed-controller surface and qualification gates.
6. Propose installation and startup separately; neither is authorized by this
   contract.
7. Qualify one bounded feedback exchange before proposing any movement.

The committed Python state machine and schemas are the executable specification
against which that firmware candidate must be tested.

The first offline implementation is documented in
[PRODUCTION_RUNTIME_FIRMWARE_R97.md](PRODUCTION_RUNTIME_FIRMWARE_R97.md). It is
compiled but intentionally uninstalled, independently unreviewed, and blocked
on a measured configuration-epoch binding.

## Configuration-epoch bootstrap

The epoch intake deliberately hashes two separate identity classes:

- the independently reviewed release packet and its candidate app, protocol,
  and joint-mapping identities; and
- retained, independently reviewed measurements for all eight controlled
  workcell components: software build, camera/support/optics, board/tags/bench,
  arm/controller/tool, power, keyboard station, phone station, and empty-cell
  safety.

The release side is not admitted from a free-form review hash plus an approval
label. Intake requires the complete typed external r97 review decision, assesses
its exact packet/manifest/app bindings and closed checklist, and verifies that
the epoch's stored decision digest and disposition match it. A missing,
mismatched, rejected, non-independent, author-conflicted, incomplete, or
open-finding decision blocks the epoch. The contract cannot authenticate the
human reviewer; that identity and evidence custody remain external controls.

The candidate app SHA remains an explicit field but is not recursively derived
from an app image that already embeds the epoch digest. This avoids an
impossible self-referential hash. A later epoch-bound firmware build can embed
the resulting configuration-epoch SHA while separately attesting its final app
SHA. Installation evidence must then prove that the running app matches that
candidate and that none of the measured components changed.

The current intake and assessment are zero-I/O. A passing result means only
`READY_FOR_EPOCH_BOUND_BUILD_PROPOSAL`; it does not authorize installation,
startup, transport, torque, feedback, or movement.

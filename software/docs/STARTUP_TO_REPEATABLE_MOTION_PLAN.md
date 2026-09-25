# From startup command to repeatable forward/reverse motion

Status: implementation follow-up, not deployment or movement permission.
Camera/contact/stylus-tip accuracy remain deferred. Keep r6's first-command review
separate from the later campaign image; do not silently enlarge its scope.

## Offline ledger checkpoint — 2026-09-18

`servo_goal_ledger.py` now reconstructs immutable per-servo goal/position entries
from a replay-verified, accepted startup run with a verified write and endpoint.
Only the elbow entry becomes commanded; the other six observed zero goals stay
uncommanded. A fresh seven-servo observation is checked against that ledger,
including identity, acquisition chronology, goal equality, position windows,
drift limits and stationary flags. Every review replays the source exports.

The native simulated pipeline supplies the successful linked evidence used in
the test. Negative cases cover changed commanded and untouched goals, position
drift, moving flags, boot/scan substitution, stale/future acquisition boundaries,
incomplete scans, uncertain delivery, non-arrival and unverified writes.

Follow-up implements offline two-scan continuation stability and direct mode/
torque evidence review. The first scan anchors stability; the second scan and
control reads must be fresh at the proposed boundary. Both scans must match the
replayed ledger, and their positions must also agree within the drift limit.
The shared control-state assessor is used by startup and continuation reviews.
Native-generated simulated predecessor exports exercise these checks, including
wrong mode/torque, short reads, errors, overlap, identity mismatch, bad separation
and drift between individually in-tolerance scans. The focused suite passed 21
tests. These are offline observations, not signed/native motion admission.

Campaign signing/ownership, native final admission and real repeatability tests
remain incomplete. r6 itself only supports the first startup command, not a
multi-leg campaign. See STARTUP_R6_DEPLOYMENT_PROPOSAL.md for deployment status;
the host-side continuation changes do not alter that reviewed binary.

## Reproduced boundary

The powered baseline found zero target registers on IDs 11–17 with valid nonzero
positions. r6 deliberately admits at most one authenticated startup command using
two stable scans and direct mode/torque reads. Its listener and boot claim do not
re-arm. After a successful elbow-only write, servo 14 should have that transmitted
goal; the other six goals may remain zero.

The native simulated bus now models that correctly: a write to 14 does not change
all seven targets. A regression verifies that another zero-goal startup observation
rejects `STARTUP_GOAL_NOT_ZERO`, and normal whole-arm admission rejects
`WHOLE_ARM_OUTSIDE_WINDOW` on the untouched zero goals. Neither rejection writes.
This is a demonstrated software workflow limitation, not proof of failed reverse
motion or an explanation of every historical endpoint discrepancy.

## Required next design

Use one explicit bounded campaign owner with one initial startup phase, followed
by separately authenticated and evidence-bound legs. Do not reset the controller,
clear a fault, rewrite zero goals, enable torque, or reconstruct one-shot owners as
an automatic workaround. Do not weaken existing normal admission globally.

The campaign maintains a per-servo goal ledger:

- Initially observed zero goals are recorded as uncommanded, not physical zero.
- A commanded goal enters the ledger only from retained exact dispatch, verified
  write evidence, matching fresh target readback and accepted endpoint evidence.
- Before each next leg, acquire fresh whole-arm target/position/control evidence.
  Commanded joints must match their ledger target and settling criteria. Untouched
  joints must retain their observed goal and stay within reviewed position/drift
  windows. Zero goals never substitute for measured position.
- Any uncertain write, changed goal, failed acquisition, moving flag, unsupported
  control state, unexpected displacement or lost export prevents the next leg.

Do not assume a ledger entry proves Cartesian tip position or clearance. All
measurements are sequential; freshness uses the oldest relevant read.

## Ordered implementation and verification

1. Finish reviewed first-command commissioning independently. Capture actual mode,
   torque, target and positions. Do not automatically enable torque on mismatch.
   Interpret valid non-arrival as non-arrival, and incomplete data as inconclusive.
2. Define a versioned campaign contract: boot/campaign ID, bounded leg count,
   unique leg IDs/nonces, exact signed targets/speeds, total deadline, per-joint
   windows, maximum per-leg delta and stop-on-fault semantics. Separate initial
   startup mode from continuation mode; reject either in the wrong phase.
3. Implement the ledger validator against raw evidence, with synthetic mixed-goal
   cases. It must reject changing an untouched target, drift, stale acquisition,
   wrong servo, prior-command substitution and incomplete endpoint confirmation.
4. Add exclusive native campaign ownership and an explicit awaiting-host-review
   state. Retain each leg immutably until export; never evict evidence to make a
   new command possible. A fresh one-use continuation authorization must bind the
   prior leg evidence hash and current campaign phase. A host acknowledgment is a
   host assertion, not device-verifiable proof of disk durability.
5. On the host, verify/export/replay a leg before issuing any continuation. Link
   each leg to its predecessor. If export fails or delivery becomes uncertain,
   stop the sequence; keep any read-only evidence collection separate from resend.
6. Simulate forward, reverse, return-to-start and repeated cycles through the real
   parser/converter/owner path. Inject failed ACK, stale read, mismatched target,
   network loss, host restart, duplicate/out-of-order legs, memory exhaustion,
   export failure, clock reversal and unauthorized mode transition.
7. Show campaign phase, each delivery verdict, endpoint verdict, measured delta,
   commanded target and export linkage in the wizard. Never label a completed
   export or accepted request as completed motion.
8. Compile a separate candidate; review app/partition/memory and provisioning
   changes; obtain separate approval before installation. r6 approval, if given,
   does not approve this later candidate.
9. Validate a bounded live forward/reverse pair. Then repeat at the same settings
   before widening count range or speeds. Extend to other joints only with their
   reviewed conversion/register mapping and mechanical coupling accounted for.

## Evidence needed before compensation or ghost typing

For every leg retain requested target, exact command bytes, converted/transmitted
count, speed/acceleration, ACK/error result, fresh target-register reads, fresh
position samples, timing/settling, per-joint admission evidence and export hashes.
Compare errors by approach direction and command size; do not fit failed or
inconclusive observations. Test any proposed correction on held-out repetitions.
Only then progress to coordinated noncontact approach/press/retract and short
ghost-key sequences. Physical registration and contact remain later milestones.

## What is not claimed

The first-command path is implemented and simulated; r6 is not installed. No live
startup arrival or reverse pair has been verified by this new diagnostics path.
The campaign/ledger design above is not yet a native runtime capability. Prior
user-observed movement is useful history, not a replacement for these new records.

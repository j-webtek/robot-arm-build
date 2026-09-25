# Fresh-pose local shoulder step — offline candidate

Latest: [r31 board composition and compiled-image review](R31_LOCAL_STEP_RELEASE_REVIEW.md).
Board routes and memory admission checks are implemented; r31 compiled and passed
offline artifact review. The host runner and independent endpoint review are now
implemented and tested against a native process with a simulated servo bus
(24 combined transport/runner/session tests passed). Live execution is explicitly
gated by the implemented r31 installation/startup and fresh-idle binding.
Actual deployment and startup evidence acquisition remain pending; see the r31
review for the latest regression and local-preflight results.

## What changed

The next-step proposal now derives its target from fresh measured position,
instead of reusing r29's obsolete starting position. It keeps measured position,
previous goal and proposed goal distinct. This is an offline candidate, not an
installed or movement-released feature.

Implemented:

- `src/rocell/application/local_shoulder_step.py`: validates three exact,
  same-boot, same-capture-owner, stationary seven-joint observations; calculates
  targets; fingerprints length-prefixed observation bytes; signs the exact plan
  using the existing nonce/boot/time-bound authentication envelope.
- `firmware/diagnostics/local_shoulder_step_contract.h`: typed native target and
  immediate-prewrite checks. It has no servo bus or write method.
- Python/native parity tests for step sizes and local starting positions, plus
  stale/changed/moving/disabled-state rejection and authenticated-byte tests.

## First local envelope

This is deliberately local, not an arbitrary whole-workspace target API:

- Three stationary scans, each at most 300 ms, at least 100 ms apart, and all
  positions within one count of the first scan. Raw feedback must agree with
  decoded positions; all seven joints must be enabled.
- Most recent reference no older than two seconds at proposal time, on the same
  controller boot clock. Historical records cannot be passed off as fresh data.
- Reference positions within two counts of
  `[2047,2429,1688,2904,1591,2041,2047]`, with existing goals exactly
  `[2047,2419,1695,2907,1589,2040,2047]`.
- Primary shoulder reduction selectable from 12 through 24 integer counts.
  Preserve the existing commanded pair sum of 4114; do not independently offset
  both servos from their measured load errors.
- Both actual-to-target travels must be in the intended directions and no more
  than 32 counts. New targets must also extend beyond the existing goals in those
  directions. Speed remains 20 and acceleration 1. At most one target packet.
- Fresh immediate-prewrite scan must follow the reference, be no older than one
  second, preserve goals and remain within one count of reference positions.
  Reference age at write is capped at 30 seconds. This is an explicit candidate
  timing policy, not an assertion that a previously read pose stays valid.

## Historical illustration — not a live command

| Quantity | Servo 12 | Servo 13 |
| --- | ---: | ---: |
| Last recorded settled position | 2429 | 1688 |
| Existing goal | 2419 | 1695 |
| Proposed goal for a 24-count primary step | 2405 | 1709 |
| Actual-position-to-target change | -24 | +21 |
| Existing-goal-to-target change | -14 | +14 |

Independently applying -24/+24 to both measured positions would produce
2405/1712 and change the commanded pair sum. The candidate avoids introducing
that change. It does not prove mechanical alignment or eliminate residual error.
No compensation model has been fitted.

## Remaining before a physical test

### Full native sequence integrated (offline)

`local_shoulder_step_session.h` now owns and retains the three reference records
it acquires itself. Each capture requires a verified durable-export receipt before
progression. Only afterward can signed-plan verification use those exact bytes.
There is no host API for replacing its reference records.

After authorization, the session acquires a fresh intent scan, exports the intent,
requires its signed receipt, then acquires another prewrite scan. Successful
admission emits one coupled target packet at speed 20/acceleration 1. Transmission
is unacknowledged; goal and encoder reads must establish arrival. Three stationary
in-tolerance samples and final export receipt are required for completion.

Failure preserves the fault and its available evidence. The existing settling
adapter now runs against this new native parent in the integration bridge. The
short-arrival and transient-neighbor scenarios preserve the original fault,
export it, collect settled readbacks, and leave the target-packet count at one.
The fake bus defines no explicit torque, reset or return APIs.

Native/host process tests exercise normal arrival, endpoint shortfall, neighbor
excursion, changed prewrite position, forged baseline receipt, wrong signed target
and failed receipt after transmission. Real Windows SHA/HMAC and real diagnostic
exports are used with synthetic keys. These remain simulated servo observations,
not actual arm movement or a live release.
Combined local-contract, authentication, integrated-session and settling regression:
61 tests passed in 17.14 seconds. No firmware installation or hardware I/O occurred.

### Native signed-plan verification implemented

`local_shoulder_step_authorization.h` now consumes the existing one-use start
envelope, validates three same-boot/same-owner raw observation records, recomputes
their length-prefixed SHA-256, and recomputes targets using the native local-step
contract. It rebuilds the entire canonical plan and compares exact authenticated
bytes. This rejects extra fields, altered targets/speed/identity/digest and
noncanonical encodings rather than trusting signed parameters merely because
their signature is valid. The verified contract remains subject to prewrite checks.

The 12-case native bridge uses real Windows SHA/HMAC with synthetic keys. Tests
cover valid admission, bad MAC, wrong digest, record substitution, target/speed/
command changes, extra fields, moving feedback, stale records, expired envelope,
and a changed pose after authentication. Replay of the start envelope is rejected.
Combined contract, native authentication and settling regression: 54 tests passed
in 9.99 seconds. This is offline evidence, not a physical movement result.

This verifier has no actuator API. Its reference buffer and canonical buffer are
object members, and the test allocates the object on the heap. Target ESP32 heap
and stack resources still require release review. The next native owner must
provide its OWN acquired/exported records; accepting host-supplied replacement
records would defeat that binding and is not an approved integration.

1. Add explicit board ownership and request routing for the integrated native
   session. Its references, verifier, prewrite checks and one-shot dispatch are
   implemented; do not replace them with host-provided state or shortcut receipts.
2. Integrate the live host runner and capability/revision binding, keeping actual
   completion separate from fault/settling results. Preserve read-only startup.
3. Extend board/transport failure testing and review the candidate's memory use.
   Native tests allocate the large reference/verifier buffers off the stack; that
   alone is not proof of adequate runtime heap on the ESP32.
4. Check nominal upward trajectory and relevant physical-clearance evidence. Joint
   limits or encoder arrival alone do not establish gripper/board/cable clearance.
5. Freeze/review the resulting firmware and release exact installation/startup/
   host bindings. r30 remains frozen and is not modified by this candidate work.
6. Reacquire actual current pose and run one admitted local step. No automatic
   retry, return, torque-off or follow-on motion follows a fault.

Validation: 25 focused contract tests passed; the combined contract and fault-
settling runner/authentication regression run passed 42 tests (overlapping counts).
No controller access, firmware change
or arm movement occurred for this contract checkpoint.

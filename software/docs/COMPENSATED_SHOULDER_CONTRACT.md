# Compensated shoulder endpoint contract — offline implementation

**Strategy superseded:** retain this work, but pause the single compensated r32
release. Follow [bounded motion characterization](BOUNDED_MOTION_CHARACTERIZATION_PLAN.md)
to gather uncompensated campaign evidence before selecting a compensation model.

Latest release status: [r32 board/build review](R32_COMPENSATED_STEP_RELEASE_REVIEW.md).
Board routing/resource checks are implemented (101 tests passed); r32 is frozen,
compiled and offline-reviewed. Installation and live revision binding remain
pending. r31 remains installed; no prospective physical compensation test yet.

## Purpose

Separate desired encoder endpoint, compensated command goals and predicted
encoder positions. This implements the next contract step from
[local offset analysis](LOCAL_PAIR_OFFSET_ANALYSIS.md); it is not integrated into
the installed r31 firmware or live command path.

Implemented independently in:

- `src/rocell/application/compensated_shoulder_contract.py`
- `firmware/diagnostics/compensated_shoulder_contract.h`

Neither implementation has a bus, transport, signing, torque or reset API.

## Fixed first-trial hypothesis

The r29 offset remains frozen at +10/-7 counts; it is not refitted to r31.
The local reference is r31's last observed seven-joint pose with exact existing
goals. Starting positions may vary by at most two counts, but shoulder residuals
must also remain within two counts of the frozen model's prediction.

The first desired motion is fixed at -14/+14 measured shoulder counts. Both
implementations independently project compensated integer goals while preserving
goal sum 4114, the local training neighborhood, command/travel bounds and a maximum
two-count predicted discrepancy from the desired endpoint.

At the historical reference, desired positions are 2400/1716, compensated goals
2391/1723 and predicted positions 2401/1716. These are an offline example, not
commands sent to hardware or a current-position guarantee.

## Freshness and observation rules

- Preparation requires an enabled stationary scan, duration at most 300 ms,
  no more than two seconds old, inside the fixed local reference.
- Prewrite requires a later enabled stationary scan, no more than one second
  old; goals unchanged; each joint within one count of the reference; total
  reference age at most 30 seconds; commanded travel still bounded.
- Postwrite observations must follow the send time and complete within five
  seconds. Shoulder goal registers must equal the compensated command goals.
- Selected positions are constrained to the desired travel interval plus two
  counts; overshooting toward the more extreme compensated goals is a fault,
  not a successful arrival. Nonselected goals remain unchanged, with stationary
  positions within two counts of their measured reference.
- A stationary observation within two counts of the desired measured endpoint
  qualifies as arrival even though its goal-register residual is intentionally
  nonzero. Short but in-range observations are pending, not successful.

The typed pose inputs must come from validated raw observations in a future
session owner. These contracts do not themselves acquire or authenticate scans.
They classify one observation; the owner must still require three qualifying
observations, latch faults and enforce export-before-progression.

## Validation

Command:

```powershell
.\.venv\Scripts\python.exe -m pytest software/tests/unit/test_compensated_shoulder_contract.py software/tests/unit/test_local_pair_offset.py -q -x
```

Result: **72 passed in 2.20 seconds**. Includes 49 host/native starting-pose
projection comparisons, nine host/native endpoint assessments, per-joint
prewrite checks and offset model tests. The initial native compilation exposed a
missing standard `<algorithm>` include; it was added before the passing run.

These tests validate code agreement and failure handling with synthetic poses.
They do not demonstrate physical compensation, controller timing, clearance or
millimeter accuracy. No firmware was built/installed or hardware accessed here.

## Remaining before a physical trial

1. Completed offline: distinct signed schema and independent native verifier,
   described in the authentication checkpoint below. Not yet attached to a
   session owner or board route.
2. Completed offline: finite native session with owned captures, fresh prewrite,
   one packet, three arrival samples, retained faults, read-only settling and
   export receipts. See the session checkpoint below. Board ownership/routing
   and matching host-runner integration remain pending.
3. Test altered offsets/goals/desired endpoints, stale/replaced records, bad
   signatures, false success flags, export failure and no follow-on write.
4. Review the candidate trajectory and compile/freeze the resulting firmware.
   Bind installation/startup evidence before one new prospective live trial.
   Never reuse the consumed r31 command or submit this through its old schema.

## Authentication checkpoint

Implemented `application/compensated_shoulder_authorization.py` and
`firmware/diagnostics/compensated_shoulder_authorization.h`.
New schema: `rocell.compensated_shoulder_step.v1`.

The host validates three bounded raw observations: common boot and capture owner,
enabled stationary joints, raw position bytes matching decoded counts, scan
ordering/duration/spacing, unchanged goals and stability against the first sample.
It applies the compensated contract to the last fresh sample and fingerprints
the exact length-prefixed record bytes.

The signed plan includes desired positions, command goals, predicted positions,
fixed model identity and +10/-7 offsets, goal sum 4114, speed 20, acceleration 1,
one-packet limit and two-count desired-endpoint tolerance. It uses the existing
boot/nonce/time-bound authentication envelope with a distinct plan schema.

The native verifier takes records from its future controller owner, not the
request body. It independently validates those records and computes the same
contract and digest. It reconstructs the complete allowed JSON and compares exact
authenticated bytes. A valid signature does not authorize a changed model,
endpoint, speed, tolerance or extra field. Its one-use gate rejects replay;
successful authentication still requires a fresh prewrite check.

Validation: 23 real native SHA/HMAC bridge tests passed; combined new and existing
contract/authentication regression: **132 passed in 7.09 seconds**. Includes bad
MAC, replaced record, changed digest/desired/command/predicted positions, offsets,
model, coupled sum, tolerance, speed, extra field, command identity, mixed boot/
owner, malformed raw position, movement/drift, expired/stale evidence and a pose
change after authentication. The installed local-step signer rejects this new
schema. The bridge also asserts replay rejection and no accessible contract after
failed verification.

Large record/canonical buffers remain members of a heap-allocated verifier in
the native test. Target ESP32 memory behavior has not been measured for this
candidate. No firmware build, installation, restart or hardware movement occurred.

Next: integrate this verifier and contract into a finite native owner with its own
three captures, separate desired/command fields in exported events, one target
packet, three qualifying endpoint observations and fault-settling/export handling.
Then connect and test the matching host runner. No live route currently accepts
this schema; do not bypass installed r31 admission to send the preview goals.

## Finite native-session checkpoint

`firmware/diagnostics/compensated_shoulder_session.h` now composes the compensated
verifier, endpoint contract, existing signed export barrier and fault-settling
parent interface. It is a separate candidate, not a change to installed r31.

The session owns three sampled reference records and requires each export receipt
before advancing. Authorization uses those retained bytes. It then acquires and
exports intent, reacquires a fresh prewrite scan, sends at most one unacknowledged
paired target packet at speed 20/acceleration 1, and records the send evidence.
Three qualifying stationary desired-endpoint observations are required; completion
also requires the final signed export receipt. No retry, return, explicit torque
change or home is implemented.

Observation checks distinguish compensated goal-register readback from desired
encoder arrival. Timeout, overshoot, neighbor motion, unexpected goals or invalid
feedback stops progression. Original fault records remain retained; the existing
read-only settling session can collect/export subsequent state without clearing
the parent fault or sending another target packet.

Events retain the base evidence schema and add the distinct `motion_contract`
identifier. After authentication, they include desired positions, command goals,
predicted positions, fixed model identity, desired-position error, raw goal
residual and arrival tolerance. The SEND event remains explicitly PRE_ACTION;
its positions/errors are not post-command arrival evidence.

Native process tests use real SHA/HMAC and signed durable exports with a simulated
servo bus. Success models the frozen +10/-7 residual; this tests software behavior,
not the truth of that physical model. Tests cover shortfall, neighboring drift,
overshoot, wrong goal readback, arrival at the command instead of desired position,
changed prewrite pose, altered plan and bad baseline/send/final export receipts.
Postwrite failures retain exactly one packet and do not retry; prewrite failures
retain zero. Fault-settling cases keep the parent fault while producing settled
read-only observations. A bad final receipt prevents successful completion even
after the endpoint observations qualify.

Combined session/authentication/contract and installed-session regression:
**100 passed in 16.51 seconds** (11 new session scenarios). No controller access,
firmware compilation/installation, startup or physical motion occurred.

Next: independent host event review and finite runner for this schema, then
board ownership/routes, resource checks and frozen firmware release review.
The host must recompute desired errors and goal residuals rather than trusting
the controller's success flag. Preserve the distinct desired/command fields in
wizard reports and diagnostic exports before admitting a prospective live trial.

## Host reviewer and runner checkpoint

Implemented `application/compensated_shoulder_review.py` and
`application/compensated_shoulder_runner.py`. The candidate uses a separate
`/rocell/compensated-step/` route namespace and command `compensated-step-1`.
These routes are a proposed interface, not installed board routes.

The host validates raw joint counts, event ordering, observation timestamps,
motion-contract identity, model identity, desired positions, command goals and
predicted positions. It recomputes desired-position errors and raw goal residuals
from the actual joint rows and independently derives each arrival flag. Three
qualifying observations and exactly one reported target packet are required for
COMPENSATED_STEP_OBSERVED; a controller COMPLETE flag alone is insufficient.

The finite runner retains raw records before review, durably exports POST intents,
and issues progression receipts only after successful independent review and
verified export. Fault records and same-parent settling remain separate: a
settled fault stays STOPPED. No retry, return or restart is added. Rejected raw
feedback remains available for diagnosis. If even the failure report cannot be
exported, the runner raises rather than claiming a saved result.

The runner explicitly rejects DEVICE_CAPTURE and the device HTTP adapter. It
does not inherit r31 live authority. End-to-end tests adapt route operations to
a native process with a simulated bus; they are not real HTTP/ESP32 validation.

Tests cover normal completion, shortfall, neighbor drift, changed prewrite state,
bad raw position bytes, premature COMPLETE, overshoot, wrong goal readback,
arrival at command rather than desired positions, altered error/desired fields,
inconsistent result flags and an internally consistent shortfall falsely marked
as arrival. Corrupted samples receive no progression receipt. Initial export
failure prevents any transport call. Test exports are verified independently.

Combined compensated runner/session/authentication/contract regression:
**108 passed in 33.29 seconds**, including 15 host runner scenarios. No firmware
compilation, installation, startup or hardware movement occurred in this checkpoint.

Next release steps:

1. Add board-owned compensated routes, exclusive reservation and memory checks;
   retain diagnostic-only startup and read-only fault settling.
2. Test route ownership, denied requests and resource failure without writes.
3. Compile/freeze/review a new firmware candidate and inspect the nominal local
   trajectory. Do not modify the already-frozen r31 artifact or settings image.
4. Add exact image/installation/startup/transport binding for the candidate.
5. Only then perform one freshly admitted prospective compensation trial and
   assess desired endpoint error alongside raw servo residuals. Physical accuracy
   and model generalization remain unverified until actual measurements exist.

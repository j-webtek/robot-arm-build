# Endpoint native admission: actual build audit

Date: 2026-09-13. Status: bare-arm bench scope confirmed; native integration pending.
Related: [Implementation playbook](MOVEMENT_CHARACTERIZATION_IMPLEMENTATION_PLAYBOOK.md).

## Finding

The current endpoint replay executor and one-write boundary require an existing
SafetySupervisor-issued EMPTY_CELL_MOTION permit. The real build cannot issue
one. Tests used the explicitly synthetic `released_snapshot` fixture; that is
not evidence that the received arm or workspace is released for movement.

Read-only import/evaluation of the current workspace produced:

- Active build: `2026-09-01_CELL-A`.
- Snapshot SHA-256: `a1e5d4ed21a48890bb0a70aea31c96e8afee175ad8679fe95013ba593d18604e`.
- Physical release: `UNRELEASED`.
- EMPTY_CELL_MOTION capability: denied.
- Reasons include robot power unreleased, incomplete physical gates, unrecorded
  exact physical identities, unproven reach, missing measured tag map, arm frame
  and reference contract, camera calibration/installation, device/station/tool
  acceptance, gravity-safe power-loss controls, motion-limit approval and final
  commissioning.
- The imported registry also retains arm-mounted-camera requirements and an
  unreleased fixed-camera fallback. These reflect the source registry; they do
  not override the operator's selected static-camera architecture.

Preflight also lacks current interlocks, qualified runtime evidence and resolved
calibration artifacts. Default diagnostic runtime flags mean **unverified here**,
not proof that the physical arm or camera is unplugged or faulty. This audit did
not open either device or assess current physical conditions.

## Why this matters

The supervisor's current scope is a commissioned cell. Routing an initial bare-arm
commissioning move through it creates an ordering mismatch if the final placemat,
camera installation and calibration are intentionally unfinished. Adding a
native serial writer alone would not solve this; replacing actual evidence with
the released test fixture would be an unsafe bypass.

The endpoints-first decision establishes the observation contract only. It does
not mark full-cell gates passed or authorize a different physical release scope.

## Scope decision (resolved)

The operator explicitly confirmed command/movement functionality testing before
board mapping. We will use the secured, non-contact bare-arm bench route below.
This resolves the scope choice, not exact-target approval or current physical
evidence. Do not require final camera/placemat calibration for this route.

The original alternatives were:

Confirm whether the next hardware stage is:

1. A secured bare-arm bench trial before final placemat/camera calibration; or
2. A trial in the completed cell, with its commissioning evidence ready to record.

For the completed-cell route, resolve actual source-bound release, calibration,
identity and current runtime evidence through existing paths. Do not alter
software to assume those artifacts exist.

For a bare-arm bench route, design and explicitly review a separate, narrowly
scoped bench admission policy before native integration. This must not reuse a
synthetic full-cell release or clear the existing cell/contact gates. It needs:

- Exact received controller/arm association and firmware compatibility review.
- Fresh operator presence and explicit one-target approval, with no campaign
  sweep, homing, contact, configuration change or automatic return.
- Secured installation and verified clearance for the complete arm/cables,
  including the power-loss/drop envelope—not just the tool endpoint.
- A practical, reachable supplied-power shutdown procedure and acknowledgment
  that loss of torque can allow the arm to fall; software cancel is not E-stop.
- A reviewed small controller-frame target and same-owned-session baseline whose
  freshness/pose meaning has been qualified, not merely recently buffered bytes.
- The selected endpoint-only observation contract and unavailable path/overshoot
  metrics, with continuous characterization retained as a later objective.
- Separate one-use admission/claim bound to source, identity, originals, deadline
  and exact target; failed/uncertain writes cannot be retried.
- Bounded native pending-I/O ownership, retained diagnostics and verified cleanup.
- Incapable admission/fault/concurrency tests before an operator-approved live
  trial. The existing final-cell permission system remains unchanged.

## Implementation checkpoint

`safety/bench_endpoint.py` now supplies a separate one-use bench permit. It binds
the exact endpoint request and owned connection, checks twelve bench-specific
reviews, pins their original hashes, and revalidates evidence at consumption.
Concurrent consumption permits at most one attempt; changed/expired evidence,
wrong targets or wrong connections burn the attempt. No cell capability is issued.

`application/endpoint_write_boundary.py` accepts this exact permit type alongside
the unchanged existing cell permit. Its baseline, identity, timing, cancellation,
one-write and uncertain-write/no-retry checks remain in force.

Important trust boundary: the evidence reader is a trusted service dependency.
Constructing a typed evidence object or supplying hash-shaped browser fields is
not authentication. Production wiring must verify retained originals, durably
claim the attempt across processes/restarts, and preserve exclusive native I/O
ownership. No production evidence reader, native motion writer or wizard arming
route was enabled by this checkpoint. No physical command was sent.

Next: compose authenticated bench reviews and durable attempt claiming with the
owned native worker, expose a single-target wizard review, then perform a fresh
operator-approved small trial. Full campaigns and contact tasks remain unavailable.

### Durable reservation checkpoint

Bench admission now requires a service-selected `attempt_root` and reserves the
attempt ID with the existing exclusive-create/write-through storage primitive
before issuing a permit. A partial reservation, cancellation, failed issuance,
changed review, or revoked permit does not free that ID. Evidence is refreshed
after disk publication; the record hash is checked again before consumption.
This implements the durable admission reservation mentioned above, not native
worker ownership or authentication of review originals.

Verified **145 tests passed**, including actual separate-process issuance races,
an injected interruption immediately after file creation, later re-issuance,
record tampering, and reviews changing during publication. All command writers
were incapable test doubles; zero device opens or physical commands occurred.

Production composition must select one stable qualified storage root, protect it
from alteration, authenticate review originals, and bind an exclusive worker
claim to this reservation. Arbitrarily choosing another root or deleting records
is not a supported recovery operation. Filesystem protection and durability
qualification remain deployment requirements, not facts proven by unit tests.

### Owned-session composition checkpoint

`endpoint_owned_trial.py` now joins baseline capture, baseline-derived context,
bench-permit consumption, one write, endpoint capture/analysis and unconditional
cleanup. Its native callbacks are trusted composition dependencies, not browser
inputs. It neither opens a device nor supplies a native writer. Integrated fault
tests are included in the **160 passing tests** checkpoint in the playbook.
This completes sequencing logic, not native admission, actual physical movement,
or wizard-to-device integration.

### Authenticated review originals checkpoint

Added `safety/bench_review_authority.py`: a bounded, canonical bundle of all
twelve review originals, authenticated with a protected coordinator HMAC key.
Each original binds the exact request, one non-contact bench scope, identified
reviewer, approval decision, evidence kind, rationale and expiry. Operator
attestations are distinguished from engineering reviews. Missing/unknown/denied
reviews cannot be sealed, and verification never renews their timestamps.

`AuthenticatedBenchReviewReader` reopens the fixed attempt's review bundle and
checks its authentication, current owned USB identity, current references,
connection association and freshness on each call. It composes with the existing
bench permit and durable reservation; changed originals prevent consumption.

This authenticates coordinator-issued records, not the physical truth of an
attestation. The signing API must remain private to a trusted coordinator after
actual review. No route accepts an uploaded key or signs browser-supplied
approvals, and no production key was created. Protected host key management,
operator-review issuance, native worker context validation/ownership and live
dispatch remain unimplemented. Do not mistake the test keys or synthetic review
originals for received-unit evidence. Combined regression: **194 passed**.

### Native facade checkpoint

`WindowsEndpointSerialApi` now implements a separate exact-T104 Win32 submission
path. It is not a widening of the feedback or passive provider. Native admission
requires the authenticated review reader, fresh port association and one-open
bench claim; writing additionally requires a consumed permit and one native
dispatch claim. Pending buffer/OVERLAPPED ownership is retained until terminal
completion. The old feedback validator still rejects motion payloads.

Validation used an incapable fake kernel only. This is not an open/closed-loop
hardware result. The new facade has no wizard activation route and is not yet
composed with the handle-owning backend or source-bound child supervisor. The
remaining worker, key/approval issuance and live qualification work is still
required before any actual device open or movement.

### Native owner and sequence checkpoint

The new endpoint facade now has a separate handle-owning connection and complete
trial composition entry point. It preserves fixed serial settings/readback,
bounded queue-aware reads, exact one-write dispatch, unresolved pending buffers,
late cleanup bytes and failure diagnostics. It does not modify or reuse a
read-only admission as motion authority.

The native composition was exercised only with a fake kernel and synthetic pose
bytes. Source-bound child ownership/supervision and actual review/key issuance
remain absent; no live CLI/wizard route was enabled. Those are the next required
integration steps before fresh operator approval and physical qualification.

### Launch and child-claim checkpoint

The native execution entry now requires a process-bound `EndpointWorkerClaim`.
Launch and claim records exclusively occupy their final names before writing;
partial/crashed attempts cannot be reused. Claiming and consumption recheck the
request, source/runtime associations, review bundle, timestamps and retained
originals. Separate-process contention and interrupted writes were tested.

Runtime-byte association is not executable qualification. A fixed source-pinned
parent registration/child package and owned process supervisor are still needed,
along with protected review/key issuance and the native wizard route. The claim
module itself creates no process and grants no standalone device authority.

### Isolated package checkpoint

The endpoint stack is now included in an explicit deterministic archive, and a
real isolated Python child imports it with native access disabled. This also
exposed and fixed an existing feedback-package regression caused by the catalog's
movement-engine import. Existing feedback/passive package checks now pass.

The new child exposes import checking only. It is not registered for live motion,
and rejects observe/execute modes. Fixed parent registration, handoff/result
protocol, key/review issuance and owned-process supervision remain required;
package import success is not physical or runtime safety qualification.

### Handoff and fixed registration checkpoint

Added request-bound handoff/wire validation and fixed endpoint worker registration
checks, including current interpreter/package hashes, exact argv/directory and
bounded process resources. The generic owned request can carry this schema,
but the owned supervisor still holds its physical composition before launch and
the isolated child still rejects `execute-one`. Tests verify both holds.

Result decoding/publication, protected key/review issuance, current child-side
identity/source reconstruction and parent activation remain outstanding before
the native wizard route and operator-approved hardware qualification.

# Shared AI-to-arm workplan

**Status:** active coordination document  
**Owners:** AI/model workstream and arm/runtime workstream  
**Started:** 2026-09-26  
**Repository:** `j-webtek/tactevra`
**Current capability baseline:** protected `main` at `a8bf36f` through merged
PR #152 (physical-camera localization evaluator) and PR #151 (Torch 2.13 test
dependency update)
**Authority:** this document coordinates development; it grants no hardware authority

## Paused baseline and next test campaign

The final-camera dependency is now recorded as an explicit targeted hold in
[`CAMERA_INTEGRATION_HOLD.md`](../../../docs/CAMERA_INTEGRATION_HOLD.md). Work on
contracts, zero-write paths, deterministic runtime behavior, campaign tooling,
evidence, documentation, and distribution may continue. Real-camera
calibration, localization qualification, perception-driven hover, contact, and
typing claims remain deferred until the fixed camera installation satisfies the
documented resume conditions.

The software wire contract is ready, but operational readiness remains blocked
on qualified perception, retained camera/support evidence, a complete measured
configuration epoch, commissioned planner calibration, and installed runtime
qualification. The current synthetic precision candidate measured 0.9975
coverage at a declared 0.99 with a 14.400834977 mm conservative planar bound.
Because that disk crosses ordinary key safe regions, it is retained as research
evidence and is not installed for deployment.

When physical testing resumes, the highest-value sequence is:

1. Freeze the final camera mount, arm base, board, keyboard, tool, cables, and
   lighting as one measured configuration epoch.
2. Collect and owner-AI review the four ARM-070 camera/support originals.
3. Commission camera-to-board, board-to-robot, keyboard-to-board, and
   tool-to-joint transforms with repeatability observations.
4. Evaluate the merged precision adapter on disjoint final-camera calibration
   and held-out captures, including glare, blur, obstruction, and placement
   changes that remain inside the declared domain.
5. Run zero-movement shadow batches through ingress, planning, and rejection
   gates before any sparse noncontact hover grid.
6. Attempt one independently verified contact only after the combined error
   budget fits inside the selected target safe region.

The governing criterion is
`perception + calibration + tracking/settling + tool-tip uncertainty < target safe-region margin`.
Additional broad ghost routines do not advance this baseline by themselves.

The AI S2/S3 physical-camera campaign is prepared in
[`PHYSICAL_CAMERA_LOCALIZATION_CAMPAIGN.md`](PHYSICAL_CAMERA_LOCALIZATION_CAMPAIGN.md).
Its strict external-evidence manifest and read-only preflight freeze split
separation, required lighting/occlusion/placement cases, independent surveyed
ground truth, file identities, and zero authority before model evaluation. This
preparation does not satisfy any missing physical-original or calibration gate.

## Purpose

This is the common working backbone for two independently advancing workstreams:

1. **AI/model lane:** understand the user's request, assess the scene, localize
   named targets, quantify uncertainty, and emit an ordered proposal batch.
2. **Arm/runtime lane:** admit that batch, bind it to measured state and
   calibration, plan a smooth safe trajectory, execute through one controlled
   writer, and independently verify the result.

The lanes may develop and test independently. Neither lane may declare an
integration stage complete by itself. A stage completes only when the AI lane,
the arm lane, and the shared integration gate each have committed evidence.

This document is intentionally shared and focused on current coordination.
Workers update only their owned lane fields, append results to the separate
[evidence ledger](EVIDENCE_LEDGER.md), and use the integration gate to expose
contract drift early.

## Common product objective

Given a supported user instruction and fresh observations, produce the intended
physical device interaction efficiently, repeatably, and safely, while preserving
the distinction between:

- what the user requested;
- what the AI inferred and proposed;
- what deterministic planning admitted;
- what bytes the controller received;
- what the arm reported doing; and
- what an independent observer verified actually happened.

The target architecture is:

```text
User request
  -> grounded semantic intent
  -> deterministic ActionPlan
  -> scene and target observations
  -> qualified ModelMotionBatch
  -> strict deterministic ingress
  -> fresh observed arm state
  -> measured reprojection, IK, limits, and collision screening
  -> sealed TrajectoryExecutionEnvelope
  -> single-use execution permit
  -> sole controller writer and correlated receipt
  -> settle verification
  -> independent task outcome verification
  -> next action, completion, or explicit stop
```

## Non-negotiable shared invariants

These rules apply to both lanes and may not be weakened to improve benchmark
scores or latency:

1. The AI/model boundary ends at `ModelMotionBatch`. A model never emits joint
   angles, PWM, Waveshare protocol JSON, serial bytes, permits, or write authority.
2. User text is compiled into a deterministic `ActionPlan`; every motion batch
   binds the exact `plan_hash` and preserves action order and repetitions.
3. Every coordinate declares its frame and metric units. No implicit frame,
   pixel-to-millimetre assumption, or undocumented axis convention is accepted.
4. Perception uncertainty and observation confidence are distinct values.
   Qualification coverage is not silently reused as per-observation confidence.
5. Image, scene, calibration, build, configuration, target-map, controller
   session, and tool/TCP identities are content-bound where applicable.
6. Every physical action begins from a fresh authenticated arm-state read.
   Action N+1 is not planned from action N's old starting state.
7. Deterministic arm code owns IK, limits, collision screening, motion timing,
   speed, acceleration, jerk, settling, contact policy, and controller encoding.
8. One process owns the writable controller transport. Every accepted execution
   has a unique correlation ID and a durable pre-dispatch boundary.
9. An ambiguous dispatch or outcome is never retried automatically.
10. Servo arrival does not prove task success. Independent device outcome
    evidence is required before advancing a multi-action task.
11. A passing synthetic study, simulation, schema test, or shadow encoding is
    identified as such and never described as physical qualification.
12. Phone state-changing actions require new scene evidence after each action.
    Keyboard batch reuse requires a still-valid scene lease and fixed-device
    evidence.

## Ownership boundary

| Artifact or decision | AI/model lane owns | Arm/runtime lane owns | Shared gate checks |
|---|---|---|---|
| Raw text interpretation | Proposed intent and abstention | Supported capability lookup | Exact intent survives compilation |
| `ActionPlan` | Consumes compiler output | Deterministic compiler/profile | Plan hash and ordered actions |
| Scene assessment | Visibility, obstruction, quality | Required evidence policy | Freshness and domain identity |
| Target localization | Named target, coordinate, uncertainty | Measured frame validation | Target bound fits safe region |
| `ModelMotionBatch` | Produces canonical batch | Strict decode and admission | Round-trip bytes and hash equality |
| Motion policy | May provide bounded intent hints only | Clearance, timing, dynamics, contact | Hints cannot weaken arm policy |
| Calibration and tool | References required capability | Owns measured transforms and TCP | Exact identity is commissioned |
| Joint trajectory | No ownership | Owns planning and screening | Exact envelope is evidence-bound |
| Controller protocol | No ownership | Owns sole encoder/writer | Correlation and receipt integrity |
| Outcome | May consume verified result | Collects independent evidence | Requested versus observed effect |

## Status vocabulary

Use exactly these status values in the stage table:

- `NOT_STARTED`
- `IN_PROGRESS`
- `READY_FOR_INTEGRATION`
- `BLOCKED`
- `COMPLETE`

`READY_FOR_INTEGRATION` means one lane has finished its own acceptance criteria.
Only the shared integration gate may change a stage's overall status to
`COMPLETE`.

## Master stage board

| Stage | Deliverable | AI lane | Arm lane | Integration gate | Overall |
|---|---|---:|---:|---:|---:|
| S0 | Shared v1 seam and baseline | COMPLETE | COMPLETE | COMPLETE | COMPLETE |
| S1 | Contract v2: freshness, uncertainty, capability | IN_PROGRESS | READY_FOR_INTEGRATION | COMPLETE | IN_PROGRESS |
| S2 | Full zero-hardware text-to-envelope shadow path | NOT_STARTED | READY_FOR_INTEGRATION | IN_PROGRESS | IN_PROGRESS |
| S3 | Measured localization and planning readiness | IN_PROGRESS | BLOCKED | NOT_STARTED | BLOCKED |
| S4 | Zero-write Waveshare adapter and receipts | READY_FOR_INTEGRATION | IN_PROGRESS | NOT_STARTED | IN_PROGRESS |
| S5 | One independently verified physical key action | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED |
| S6 | Ordered multi-action keyboard missions | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED |
| S7 | Performance and operational qualification | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED |
| P1 | Phone capability track | BLOCKED | BLOCKED | NOT_STARTED | BLOCKED |

The S0 status is supported by the shared v1 batch, strict ingress, sequence
coordinator, journal, and focused boundary tests. S2 integration is in progress:
a raw request now traverses the grounded parser, deterministic compiler, actual
v2 emitter, and arm shadow path when given an explicitly scoped synthetic
integration fixture. Qualified perception has not yet supplied that fixture, so
this is not the complete S2 path. S3 remains blocked
from integration because no deployment localization qualification is installed
and the measured planner does not yet reach physical execution admission. S4
lists AI as ready because no new AI authority is required. The zero-write
adapter and reviewed native-shaped T=102 bridge now share the controller's
ordered joint encoding, but authentic native transport, independently acquired
receipts, and physical qualification remain unfinished. A durable native T=102
handoff now commits an exclusive writer claim before any future transport open;
restart after that claim is retry-forbidden even though native open authority is
still absent. The claimed handoff now also reaches a hardware-incapable native
executor rehearsal: fresh claim-bound authority is consumed exactly once, an
exactly typed in-memory transport records one open/write/close lifecycle, and a
closed receipt distinguishes requested and confirmed bytes from authentic
controller receipt or movement. A real serial transport and physical authority
remain absent and require independent review. The executor lifecycle now also
has a durable terminal receipt journal: a content-bound `started.json` is
committed before the rehearsal transport may open, so pre-terminal restart is
always retry-forbidden, and a separately flushed `terminal.json` seals the
exact byte-accounted receipt with terminal no-replay semantics.
ARM-053 now defines the production-shaped seam outside that incapable executor:
an exact COM/USB identity, detached externally issued single-use authority,
external verifier interface, one-open/one-T=102-write/one-capture/one-close
abstract transport, exact T=1021 and settled T=1051 validation, and its own
durable pre-open/terminal attempt journal. No concrete transport, authority
issuer, verifier keyring, port discovery, or controller process is included,
so all current ARM-053 capture evidence remains scripted and explicitly
unqualified. ARM-054 now supplies a separately isolated Windows serial adapter
candidate with exact pre/post-open USB identity checks, finite read/write
timeouts, one
canonical T=102 write, bounded T=1021 capture, and exactly two T=105/T=1051
feedback exchanges. It is not connected to a CLI, authority issuer, controller
startup, or automatic runtime composition. The next dependency is independent
source review followed by separately authorized endpoint and physical
qualification, not further model-contract expansion.
ARM-055 now freezes that exact merged candidate into a deterministic,
content-addressed review packet and exercises the real adapter class through
ARM-053 using memory-only serial and inventory fixtures. The composition audit
shows crossed external authority is durably started and rejected before adapter
open, while a successful scripted path retains terminal no-replay evidence and
cannot promote controller provenance, movement qualification, or follow-on
authority. Packet status remains `AWAITING_EXTERNAL_INDEPENDENT_REVIEW`; this
repository has not performed or impersonated that review. The next dependency
is an external decision bound to the packet SHA-256, followed only under
separate authorization by read-only endpoint qualification.
ARM-056 now defines the closed return path for that outside decision. It binds
the exact packet, manifest, candidate commit, adapter source, ordered
adapter/composition checklist, reviewer declarations, findings, disposition,
and explicit validity window. Synthetic, future, expired, rejected,
packet-crossed, source-crossed, incomplete, author-conflicted, or open-finding
decisions cannot become endpoint-qualification-intake ready. Even a valid
external decision keeps endpoint open, controller start, execution, hardware,
and physical authority false. No independent review is yet present; the next
dependency remains a real outside decision and separately authorized read-only
endpoint qualification.
ARM-057 now makes the external exchange operational without crossing that
boundary. A deterministic builder emits the immutable packet, decision/report
schemas, reviewer procedure, and a content-addressed exchange manifest with no
decision included. A separate strict intake reads one returned regular JSON
file, rejects duplicate fields, oversize, symlinks, mutation, and overwrite,
then retains a normalized decision, assessment report, and raw-document hash.
Blocked reviews remain retained and non-authorizing. This tooling performs no
hardware access and does not solve reviewer identity or custody; those remain
external prerequisites.
ARM-058 adds an automated zero-write command/telemetry replay seam. It consumes
the exact Waveshare T=102 preview receipt and typed synthetic or retained-export
T=1051 samples, binds correlation/session/waypoint identity and timing, and
requires consecutive six-joint arrival plus stability at every previewed
waypoint. Crossed, stale, non-monotonic, malformed, incomplete, unstable, and
out-of-tolerance cases cannot become a replay PASS. Even PASS keeps physical
arrival, visual outcome, transport access, execution, and physical authority
false. This improves automated S4/S7 rehearsal coverage but does not satisfy
the pending ARM-054 independent-review or read-only endpoint prerequisites.
ARM-059 records the project owner's explicit acceptance of the exact internal
AI technical review as the adapter source-review prerequisite, while preserving
that no human review or external independence is claimed. The hash-bound owner
acceptance makes the next read-only endpoint-qualification intake eligible for
design and later separate authorization. It does not authorize endpoint open,
controller startup, any transport write, execution, hardware access, or
physical movement. Under this owner-defined policy the adapter review milestone
is complete with caveat; the next arm-lane dependency is the closed read-only
endpoint-qualification intake and its separately authorized physical run.
ARM-060 now defines that closed intake. It binds the exact ARM-059 acceptance,
one explicit host, one pinned COM/USB identity, and a finite passive-read plan.
The proposed run may open and close that endpoint once but permits zero writes,
zero active requests, zero movement or torque commands, no purge, no fallback,
no retry, and no DTR/RTS assertion. The implementation performs no discovery,
port open, or I/O. A valid record is only
`READY_FOR_SEPARATE_READ_ONLY_AUTHORIZATION`; every endpoint, controller,
transport, execution, hardware, and physical authority remains false. No real
intake is retained until the actual host and endpoint identity are established
without guessing. The next dependency is a separately authorized creation of
that exact intake and then a separately bounded passive qualification run.
ARM-061 now retains the first exact intake after a fresh Windows PnP-only
identity check found the historically documented CP210x controller on COM7 and
distinguished it from the host's Bluetooth serial endpoints. The host name is
represented by a SHA-256-derived pseudonymous identifier. Strict tests validate
the retained artifact against the closed schema and recomputed endpoint/intake
hashes. No serial open occurred. The next boundary is unchanged: a separate,
explicit authorization must name intake
`2d88fa8874088ce47b778343ea0ed07994bafb64267b8cd121765c52536ce1d9`
before the one-open, zero-write passive qualification may run.
ARM-062 completed that separately authorized passive run exactly once. PnP
identity matched before and after open; the endpoint opened and closed once;
the close was confirmed; and no bytes, requests, movement, torque action,
retry, purge, or DTR/RTS assertion occurred. The one-second window contained no
unsolicited complete or partial lines. This qualifies only the pinned endpoint
lifecycle under the passive zero-write policy. It does not qualify controller
protocol or firmware identity. ARM-063 now freezes the next active, non-moving
feedback proposal: one exact ten-byte `T=105` request, one bounded `T=1051`
response, and one open/write/read/close lifecycle, with no T=102, movement,
torque, retry, purge, fallback, startup, or DTR/RTS assertion. Its retained
intake hash is
`3b44d5e011d8c44afda1bb6deb1cc479b1fc0c45e59e39308d285cde416b8fcc`.
Only a fake endpoint has exercised the contract. The intake grants no live
open or write authority; the physical exchange requires a separate explicit
owner authorization naming that hash.
Neither passive evidence nor the fake rehearsal qualifies installed firmware,
physical telemetry accuracy, actuation, or model-command execution. The next
arm-lane dependency is the separately authorized ARM-063 exchange, not another
passive retry.
ARM-064 consumed that authorization exactly once. COM7 opened and closed once,
the pre-request buffer was empty, and the exact T=105 bytes were written once.
The installed surface returned `FAULT:NOT_READY\r\n` instead of T=1051. No
retry, movement, T=102, torque action, startup, purge, fallback, or DTR/RTS
assertion occurred. The exact fault exists in the finite ghost-typing source,
so the result is consistent with the known diagnostic surface but does not
attest installed firmware identity. The generic feedback seam and observed
planner start state remain blocked. The next dependency is resolving the
installed-runtime mismatch under a separate reviewed installation/startup
plan—not repeating this request.
ARM-065 now reconciles that terminal result with the sealed r97 candidate. The
assessment binds the ARM-064 receipt and response digests to the exact r97
packet, manifest, and app hashes and remains `BLOCKED`. The installed surface
is diagnostic-consistent but not attested as r97; independent r97 review and
all eight measured epoch components are absent; and r97 still reports a null
epoch. No installation intake is ready, and no installation, startup,
transport, execution, hardware, or physical authority was created. The shared
next dependency is external r97 review plus the measured configuration epoch,
followed by a separately reviewed hash-bound installation proposal.
ARM-066 verified the ignored seven-member r97 packet directly from the retained
compiled inputs; its SHA-256 remains
`987cbe86d98440734d8336c704f1ecd89692675a9cb1620cb674e4132957b416`.
It also adds the missing owner-side intake CLI for a returned external decision.
That CLI strictly parses, normalizes, assesses, and immutably retains one
decision while keeping every physical authority false. This makes the external
review handoff operational without pretending that repository code can perform
the independent review. The dependency is unchanged: a genuinely independent
reviewer must return the decision, then all eight measured epoch components
must be collected and reviewed.
ARM-067 records the owner's decision that no human reviewer will be used. The
exact r97 AI technical review is accepted through a hash-bound governance
override that explicitly sets `human_review_claimed=false` and
`external_independence_claimed=false`. External review is now optional rather
than blocking. The next active dependency is an owner-governed configuration
epoch containing retained physical evidence and AI review records for all
eight controlled workcell components. This override creates no installation,
startup, transport, execution, hardware, or physical authority.
ARM-068 implements that next boundary without rewriting the historical
independent-review epoch contract. Its owner-governed draft accepts zero through
eight components, requires the policy-defined binding set for each component,
and reports missing, stale, synthetic, or unreviewed evidence separately. A
confirmed-not-installed station may be represented, but still requires retained
physical evidence and owner-AI review. The retained initial assessment is
correctly `BLOCKED`: all eight components and their 32 required bindings are
missing. No configuration-epoch hash exists until the complete draft passes.
The next work is evidence population, beginning with the reproducible
`software_build` component; no controller operation is needed for that step.
ARM-069 closes that first component from retained original software inputs. It
binds the exact r97 app, packet, manifest, compile profile, source baseline,
dependency declaration, protocol encoder, and joint mapping into four
content-addressed binding records, then records a closed owner-AI review. The
partial epoch assessment advances only `software_build`; the other seven
components remain explicitly `MISSING`, the configuration-epoch hash remains
null, and every hardware authority remains false. The next ARM dependency is
the retained camera/support/optics evidence bundle, not another software-build
or controller test.
ARM-070 implements that camera/support/optics intake and evaluates the actual
repository baseline. The purchased profile still says
`PURCHASED_PENDING_RECEIPT`; received-unit, USB identity, commissioned mode,
control-readback, and qualified support evidence are absent, and all 55 hardware
intake rows remain unresolved. The retained result therefore keeps all four
camera bindings missing and does not alter the ARM-069 epoch. The next step is
physical-original collection through the existing onboarding workflow, not a
synthetic substitution or another controller test.
ARM-073 closes the software-only gap between those retained originals and the
ARM-070 binding slots. It accepts only four canonical owner-AI review records,
performs bounded substitution-aware reads beneath one safe root, verifies the
exact original and review hashes, and emits typed bindings plus zero-authority
receipts. It does not create evidence, perform a review, decide freshness,
advance the epoch, open a camera, or authorize hardware. The physical collection
dependency remains unchanged; once those originals exist, this adapter removes
manual transcription from their ARM-070 intake.
ARM-075 begins the offline T2B typing optimization gate without changing that
physical dependency. It consumes the exact T2A Cartesian screening samples,
binds them to the pinned build and calibration identities plus an explicitly
synthetic offline joint seed, and applies the canonical deterministic IK,
joint-margin, Jacobian-rank, and adjacent-joint continuity gates. Passing
samples advance only to `READY_FOR_INSTALLED_GEOMETRY_COLLISION_SCREENING`;
installed collision geometry, cable evidence, conservative segment sweeps,
controller access, and all physical authority remain absent.
ARM-076 adds the next zero-authority intake seam. It validates the exact
T1/T2A/IK lineage, preserves the synthetic start-state label, and produces the
bounded joint-sample plan plus exact installed-profile evidence slots needed by
the existing FK/collision/sweep pipeline. It refuses to substitute nominal
geometry for a measured installed profile and never presents its synthetic seed
as observed feedback. Physical evidence population and a fresh observed start
state remain the next dependencies.
The AI precision lane now has a mainline-compatible pose-output adapter and v2
batch producer. It preserves repeated targets and abstains on qualification,
domain, freshness, identity, confidence, or containment failure. Its retained
held-out evidence is still `SYNTHETIC_OFFLINE_ONLY`: the 14.400834977 mm bound
crosses ordinary key safe regions, so no deployment qualification is installed
and the operational-readiness perception gate remains blocked.

## Stage definitions

### S0 — Freeze the shared v1 seam

**Goal:** prove both lanes use one ordered, hash-bound model-to-planner contract.

AI lane completion:

- Emit the core `ModelMotionBatch`, not a duplicate AI-only command schema.
- Preserve action order and repeated targets.
- Bind intent, scene, precision, fusion, model, frame, and image identities.
- Emit no controller command or physical authority.

Arm lane completion:

- Strictly decode the same batch type.
- Compare device, plan hash, target order, evidence hashes, confidence, target
  containment, and interaction type.
- Require fresh observed joint state per admitted action.
- Stop before transport access.

Integration evidence:

- Actual emitter output round-trips through shared decoding and ingress.
- Repeated `H`, `H`, `I` remains ordered and unique by proposal ID.
- Current focused boundary suite passes.

**Status:** complete at baseline. Future schema changes must preserve a v1
compatibility fixture or record an explicit migration.

### S1 — Contract v2: freshness, uncertainty, and capability

**Goal:** remove semantic ambiguity before either lane approaches live execution.

AI lane objectives:

- Separate `observation_confidence` from localization qualification coverage.
- Emit a structured uncertainty object containing at least bound type, bound in
  millimetres, coverage probability, qualification hash, and domain ID.
- Bind capture identity and time, evaluation time, expiry/scene lease, model
  identity, target-map identity, and capability profile.
- Bind keyboard placement/orientation through independently evidenced geometry;
  never validate a predicted point against a target rectangle centered from that
  same prediction.
- Keep action coordinates, interaction intent, and target IDs; do not add servo
  or protocol fields.
- Define keyboard frame output as one explicit producer profile. If board-frame
  output remains selected, document how it was derived from image evidence.

Arm lane objectives:

- Strictly decode and validate the new fields without trusting the producer's
  acceptance decision.
- Enforce expiry at ingress and again immediately before planning.
- Validate qualification/domain/capability registries independently.
- Require the entire uncertainty region—not only its center—to fit the measured
  target safe region.
- Treat model speed and clearance as non-authoritative hints, or remove them and
  derive policy entirely from the arm configuration.
- Preserve a migration decoder for frozen v1 fixtures; never guess absent v2
  semantics for live work.

Shared integration gate:

- Canonical AI fixture validates under the published schema and Python decoder.
- Mutations of timestamp, qualification, uncertainty, frame, plan, capability,
  and target-map identities are rejected one at a time.
- Schema validation and runtime validation agree on numeric and index bounds.
- A v2 compatibility matrix is committed with producer and consumer versions.

Completion evidence:

- Contract/schema paths and SHA-256 hashes.
- Exact test command and results.
- Migration behavior for v1.
- Limitations and explicit non-authority statement.

### S2 — Full zero-hardware text-to-envelope shadow path

**Goal:** exercise the real components in order without writing to hardware.

AI lane objectives:

- Accept a raw supported text request through the grounded parser/reference
  interpreter.
- Compile it using the deterministic keyboard compiler.
- Run the selected scene and precision components, including abstention.
- Emit the exact batch consumed by the arm lane.
- Preserve unsupported and clarification outcomes rather than forcing a plan.

Arm lane objectives:

- Decode and admit the actual emitted bytes.
- Create the sequence coordinator and consume a fresh observed-state fixture.
- Run measured reprojection, IK, limits, and route/collision screening.
- Produce a sealed `TrajectoryExecutionEnvelope` when all gates pass, or one
  exact blocker when they do not.
- Generate no Waveshare bytes and perform zero writes.

Shared integration gate:

- One command runs the complete shadow path and emits one trace bundle.
- Trace links raw request hash, plan hash, observation hashes, batch hash,
  ingress hash, planner hash, observed-state hash, and envelope hash.
- Supported, ambiguous, stale, obstructed, out-of-bound, and unsupported cases
  all reach their expected terminal states.
- No test substitutes a hand-authored batch for the actual AI emitter output.

Completion evidence:

- Reproducible command and committed sanitized fixture set.
- End-to-end trace manifest.
- Cross-lane negative test matrix.
- Confirmation of zero hardware access and zero generated wire commands.

### S3 — Measured localization and planning readiness

**Goal:** replace synthetic assumptions with measured deployment evidence.

AI lane objectives:

- Freeze the final camera/domain definition and independent train,
  calibration, and held-out evaluation splits.
- Measure per-target localization error, abstention, obstruction detection, and
  scene-quality rejection from the actual camera geometry.
- Install a qualification only when its declared coverage and target-fit gates
  pass on held-out deployment data.
- Record domains and targets not covered by the qualification.

Arm lane objectives:

- Commission camera, board, device placement, robot base, and tool/TCP
  transforms with validity and expiry.
- Complete installed geometry, cable, keyboard, board, and exclusion-volume
  models needed for continuous collision screening.
- Demonstrate the planner's reserved ready status from fresh measured state,
  without encoding or transmitting commands.
- Measure joint limits and conservative velocity, acceleration, jerk, and
  settling limits.

Shared integration gate:

- Actual held-out camera observations produce v2 batches whose uncertainty
  regions fit named targets after measured reprojection.
- Those exact batches reach sealed trajectory envelopes from fresh state.
- Deliberately moved keyboard, stale calibration, wrong tool, occlusion, and
  out-of-domain images fail closed.
- Qualification and calibration artifacts remain separately identifiable.

Completion evidence:

- Qualification and calibration artifact hashes.
- Held-out scorecards and target coverage list.
- Planner-ready trace with zero hardware writes.
- Failure evidence for every required negative case.

### S4 — Zero-write controller adapter and correlated receipts

**Goal:** prove exact protocol encoding and execution lifecycle without sending.

AI lane objectives:

- Keep the batch contract stable and consume arm capability information only
  through the supported capability profile.
- Add no controller-specific fields.
- Verify model-side tests still pass against the adapter's supported action set.

Arm lane objectives:

- Implement a zero-write Waveshare encoder that accepts only a sealed,
  unexpired `TrajectoryExecutionEnvelope` plus a separate single-use permit.
- Define how timed waypoints map to the controller's actual command semantics.
- Define fixed-gripper/tool behavior explicitly.
- Reject stale sessions, duplicate correlation IDs, expired deadlines, altered
  envelopes, unsupported interpolation, and unmeasured limits.
- Build a sole-writer lifecycle and a content-bound receipt format covering
  submitted bytes, acknowledgements, feedback, timeouts, and closure.

Shared integration gate:

- Golden byte fixtures are deterministic and reviewable.
- Decode/encode units and joint ordering agree with the commissioned controller.
- Duplicate, stale, altered, partial-write, timeout, and restart cases fail
  without automatic resend.
- Test instrumentation proves transport write count remains zero.

Completion evidence:

- Encoder source and golden fixtures.
- Controller protocol/version citation or pinned vendor artifact.
- Receipt and permit schemas.
- Fault-injection results with zero physical writes.

### S5 — One independently verified physical key action

**Goal:** demonstrate one admitted model-originated key interaction end to end.

AI lane objectives:

- Produce one qualified target proposal from a fresh deployment observation.
- Abstain when any required scene, domain, confidence, or uncertainty condition
  is not satisfied.
- Retain the exact user request and plan lineage.

Arm lane objectives:

- Execute exactly one admitted envelope through the sole writer.
- Monitor tracking, limits, deadline, and settling throughout the action.
- Retract safely and preserve torque policy.
- Produce one execution receipt and independent keyboard outcome observation.
- Never retry an uncertain dispatch or outcome.

Shared integration gate:

- Requested key, proposed target, transmitted command, feedback, and observed
  character are separately recorded and agree.
- A failed or uncertain outcome terminates without a second press.
- Physical test approval, cleared workspace, build identity, and stop reason are
  recorded outside this plan in the run evidence.

Completion evidence:

- Sanitized physical run manifest and receipt hashes.
- Independent outcome artifact.
- Tracking/settling metrics and discrepancies.
- Explicit count of physical writes and movements.

### S6 — Ordered multi-action keyboard missions

**Goal:** execute supported strings smoothly while preserving per-action safety.

AI lane objectives:

- Preserve exact text, action order, repetitions, punctuation, and unsupported
  character handling.
- Define when a fixed-keyboard scene lease may span multiple actions and when a
  new observation is mandatory.
- Never repair or reorder a plan based on convenient geometry.

Arm lane objectives:

- Advance only after verified completion of the preceding action.
- Read fresh arm state for each action while caching only immutable geometry.
- Optimize safe hover-to-hover transitions, planner warm-up, and settled motion
  without bypassing ingress or outcome checks.
- Recover from restart through the durable journal without replaying an
  uncertain action.

Shared integration gate:

- Held-out strings cover repeated keys, rows, numbers, punctuation, space, and
  enter within the supported profile.
- Requested and independently observed output match exactly.
- Fault injection covers device movement, stale lease, dropped feedback,
  process restart, and ambiguous outcome.

Completion evidence:

- Mission corpus and held-out definition.
- Exact-match outcome scorecard.
- Per-action lineage and latency breakdown.
- Restart and fault-injection reports.

### S7 — Performance and operational qualification

**Goal:** improve speed only after correctness and recovery are demonstrated.

The arm-side implementation sequence, rolling-horizon boundary, motion-shaping
rules, and speed ladder are defined in the
[optimized typing execution plan](../../docs/OPTIMIZED_TYPING_EXECUTION_PLAN.md).
That plan retains a one-action commit horizon: preview and transition-cache work
may reduce latency, but neither grants physical authority.

AI lane objectives:

- Measure intent, scene, precision, fusion, and emission latency separately.
- Reduce inference latency without changing qualification semantics.
- Track abstention, false acceptance, coordinate error, and domain drift.

Arm lane objectives:

- Measure ingress, planning, encoding, dispatch, travel, settling, observation,
  and total action latency separately.
- Tune trajectories under measured limits and tracking error budgets.
- Add watchdog, cancellation, operator stop, and bounded resource behavior.

Shared integration gate:

- Publish p50/p95/p99 latency, exact outcome rate, tracking error, abstention,
  transport fault, and recovery metrics on held-out missions.
- Demonstrate that performance changes do not reduce safety-gate coverage.
- Freeze supported device/task/camera/tool profiles for the qualified release.

Completion evidence:

- Qualification report and release commit.
- Reproducible benchmark commands and environment identity.
- Regression thresholds enforced in CI.
- Remaining limitations and unsupported capabilities.

### P1 — Separate phone capability track

Phone work does not inherit keyboard readiness automatically. It requires:

- named screen states and legal transitions;
- a fresh observation after every state-changing tap;
- screen-local coordinates and measured screen placement;
- independent state verification before the next tap;
- explicit support for dialer navigation, number entry, call initiation, and
  cancellation; and
- its own held-out perception, planning, execution, and outcome qualification.

Until those gates exist, phone requests remain `unsupported_by_profile` or
blocked at the batch emitter.

## Shared contract-v2 design record

S1 owns the exact schema, but both workers must design against these semantics:

```text
ModelMotionBatchV2
  identity:
    batch_id, request_id, plan_hash, device, capability_profile
  evidence:
    frame_id, image_hash, capture_time, evaluation_time, expiry/scene_lease
    scene_hash, precision_hash, fusion_hash, model_id
  qualification:
    domain_id, qualification_hash, target_map_hash
    coverage_probability, error_bound_mm, bound_type
  actions[]:
    proposal_id, target_id, coordinate_frame, target_mm, interaction
    observation_confidence
  prohibited:
    joint targets, PWM, controller JSON, serial bytes, transport identity,
    execution permit, physical authority
```

This block is a semantic design target, not yet the authoritative schema.
Committed schema and decoder changes must link their evidence below.

## Required shared test matrix

Every contract or runtime change must preserve tests for:

| Category | Required cases |
|---|---|
| Intent | supported literal, ambiguity, extra operation, unsupported character, wrong device |
| Ordering | repeated key, punctuation, multi-row sequence, altered order, missing action |
| Provenance | altered plan, image, model, scene, precision, fusion, target map, qualification |
| Freshness | fresh, expired, future timestamp, moved device, changed scene lease |
| Geometry | center, safe-edge bound, uncertainty crossing edge, wrong frame, wrong plane |
| Capability | unsupported profile, wrong tool/TCP, phone through keyboard-only path |
| Arm state | fresh state, stale state, reused state, wrong controller session |
| Trajectory | joint limit, velocity, acceleration, jerk, collision, deadline, settling |
| Transport | duplicate correlation, partial write, timeout, stale session, restart |
| Outcome | verified, failed before dispatch, ambiguous after dispatch, mismatched character |
| Authority | no model servo fields, no wire bytes before permit, no automatic retry |

## Evidence ledger rules

1. Evidence rows are append-only. Never edit an old failure into a pass.
2. Corrections receive a new evidence ID and reference the superseded row.
3. Every row names one repository commit and one exact test/evaluation command.
4. Store large or structured artifacts in the appropriate committed evidence or
   evaluation directory; link them here rather than pasting raw output.
5. Mark `hardware_writes` and `physical_movements` explicitly, including zero.
6. Do not commit credentials, private settings, raw authorization material, or
   unsanitized user data.
7. A lane may set itself to `READY_FOR_INTEGRATION` after its acceptance criteria
   pass. Only a cross-lane evidence row may complete the integration gate.

### Evidence row template

Copy this row and fill every field:

```markdown
#### E-YYYYMMDD-AI|ARM|INT-NNN — short title

- Stage: S#
- Lane: AI | ARM | INTEGRATION
- Commit: full SHA
- Change: concise description
- Inputs/fixtures: paths and hashes
- Command: exact reproducible command
- Result: PASS | FAIL | BLOCKED, with counts/metrics
- Artifacts: repository-relative links
- Hardware writes: integer
- Physical movements: integer
- Limitations: explicit scope and unresolved issues
- Supersedes: evidence ID or `none`
- Next dependency: exact other-lane artifact or gate
```

## Evidence ledger

Detailed, append-only AI, arm, and integration results are kept in the
[Tactevra AI/arm evidence ledger](EVIDENCE_LEDGER.md). Keep this workplan focused
on current stages, ownership, dependencies, and operating rules. Add new results
to the ledger using the template above; do not rewrite an earlier result.

## Active work claims

The current zero-authority integration baseline is
[`model_arm_conformance_profile_v1.json`](../../config/model_arm_conformance_profile_v1.json),
SHA-256 `2430ec5f8362aae76e8250d2d9da292f85375d93750addd944a969b1bc2e4dbd`.
It binds the reviewed arm and AI commits, freezes the implemented v2 boundary,
and provides shared accepted/rejected cases without advancing operational readiness.

The pose-keyloss research checkpoint is now represented by the focused external-
artifact package in
[`POSE_KEYLOSS_EXTERNAL_ARTIFACT.md`](POSE_KEYLOSS_EXTERNAL_ARTIFACT.md) and
evidence `E-20260927-AI-410`. Its clean-clone state is explicitly unavailable,
its separately present bytes are identity-verified, and neither result installs
localization qualification or changes the AI-to-arm authority boundary.

AI work and test documentation is maintained through the
[`AI work and evidence handbook`](AI_WORK_AND_EVIDENCE_HANDBOOK.md), the
machine-checked [`AI work registry`](AI_WORK_REGISTRY.json), and evidence
`E-20260927-AI-419`. The registry assigns every tracked AI test module to one
workstream and binds its source, governing documents, retained evidence,
limitations, and next gate. This documentation baseline changes no lane or
integration status.

The post-preflight physical-camera evaluator is implemented at evidence
`E-20260927-AI-422`. It revalidates retained campaign bytes, binds every
prediction to image/model/preprocessing identities, derives an empirical bound
from calibration only, scores held-out coverage and unsafe-scene acceptance,
and checks a conservatively composed bound against the frozen target map. It
emits only an offline review recommendation and installs no qualification.

Workers add a short row before beginning a potentially overlapping change and
remove it only in the same commit that appends the resulting evidence row.

The latest completed SIM/WP2 increments are evidence `E-20260929-INT-445`
through `E-20260929-INT-449`. They retain a bounded triangle-preserving
`link2` partition candidate, bind all 165 remaining false positives to pinned
upstream `Adjacent` policy evidence, verify that all six separate SRDF `Never`
pairs remain free in the exact 49-pose corpus while preserving three
nonexcluded nonadjacent collision witnesses, and encode all twelve upstream
pairs in a strict hash-bound candidate document. The candidate is explicitly
uninstalled, defaults every pair to collision checking, has zero effective
exclusions, and grants no collision, clearance, controller, permit, transport,
or physical authority.

The held-out stress campaign in `E-20260929-INT-449` expands the selected
geometry and inert candidate to 256 disjoint Halton poses and 5,376 pair cases.
All six proposed `Never` pairs remain free and no false negative appears, but
13 false positives reappear across six nonproposed pairs. This prevents any
collision-query or exclusion-policy promotion and directs the next geometry
work toward those exact retained-pair witnesses.

The process-alignment overlay in `E-20260929-INT-450` returns WP2 to the actual
AI-to-arm seam. It binds an AI-produced `ModelMotionBatchV2` carrying ordered
`H, H, 1, PERIOD` proposals to the governed RC03 Isaac scene and authors the
proposal centers, inferred synthetic placement, key regions, and uncertainty
disks. The target centers share one rigid placement within numerical precision,
but the 14.400834977 mm localization disk exceeds each 7 mm key-edge margin.
The replay therefore stops before a joint schedule. The next simulation input
is the exact zero-write schedule from the arm typing pipeline, after its source
batch uses this same representative target geometry and passes the safe-region
uncertainty gate.

The source-bound schedule replay in `E-20260929-INT-451` consumes arm commit
`5072c163152848bd8d78fa3fbc024e32177ac98d` through the strict v2 ingress,
trajectory, IK, and joint-dynamics stages for representative ordered targets
`H, H, 1, PERIOD`. The nominal geometry fails the arm-margin gate, and the
simulation overlay with the nominal ready seed fails continuity; both failures
remain retained. With the existing simulation-only layout, 120 mm keyboard
tool, and a synthetic seed at the declared park pose, all 133 samples reach the
installed-geometry collision gate and replay in Isaac with maximum tool-tip
disagreement `0.07684842940066568` mm. This validates the offline coordinate,
ordering, IK, scheduling, and independent-FK seam only. It does not replace the
blocked safe-region AI evidence, execute collision screening, or change any
lane or integration-gate status. The arm branch subsequently advanced to
`7f22378613bc9866b14912e667882af9201fd52c` with profiled-service routing for
the shared emitter; the retained replay remains honestly bound to its exact
`5072c163152848bd8d78fa3fbc024e32177ac98d` source and should be repeated from
the newer service path when safe-region-qualified producer output exists.

The actual-emitter replay in `E-20260929-INT-452` closes that producer
substitution question for the synthetic representative case. It binds arm
commit `9e5c878852da6a6e8509598bce9ce43f218efc70`, the actual shared emitter's
canonical batch bytes, strict v2 admission, 133-sample schedule, and independent
Isaac FK replay. `H, H, 1, PERIOD` and every replay metric remain identical to
the fixture-origin run. The evidence explicitly marks the supplied observations
as synthetic and claims no deployment qualification. The remaining priority is
therefore qualified physical-camera localization and installed collision
geometry, not another synthetic producer substitution.

The fixed-fixture practice corpus in `E-20260929-INT-453` adds 16 deterministic
JPEGs from the existing plan-blind virtual arm-camera boundary: two achieved
camera poses crossed with nominal, dim, bright, warm, glare, blur, and two
foreground arm/tool-obstruction cases. Every sample binds the frozen 46-key and
29-phone target catalog in board millimetres and projected pixels, the exact
pixel transformation, source image identities, and zero authority. This is a
repeatable pretraining and data-pipeline fixture for a keyboard and phone that
remain fixed on the board. The device surfaces, lighting, obstruction, and
camera are synthetic approximations, so the corpus does not change S2/S3 lane
status, install localization qualification, or reduce the physical-camera and
installed-collision dependencies.

The fixed-overview segmentation corpus in `E-20260930-INT-454` aligns the
synthetic data flow more closely with the intended installation: one camera and
board transform remain fixed while three URDF joint states move a pose-bound
robot obstruction. It retains 15 RGB practice samples in three deterministic
atlases, plus per-pose semantic link masks, approximate millimetre depth maps,
and per-target obstruction overlap for all 75 targets. A repository-footprint
failure from the initial separate-image layout is retained; packing the RGB
samples into crop-addressed atlases brought the tracked archive back within its
governed ceiling. The link shapes remain capsule proxies rather than CAD meshes,
so this increment advances data-pipeline and abstention rehearsal only and does
not change any lane or integration status.

The official-mesh comparison in `E-20260930-INT-455` replaces the capsule
shape only for a bounded perception experiment. Seven visual meshes from the
pinned Waveshare source are placed by the governed URDF FK and rasterized in
Isaac from the identical fixed camera at `ready`, `hover_t`, and `hover_e`.
Capsule-to-mesh mask IoU is only `0.596819` to `0.709856`, and the capsule
misses `9,908` to `30,058` mesh pixels. The capsule corpus remains useful for
obstruction rehearsal, but this result rejects treating it as a conservative
robot silhouette. The official meshes are visual geometry only; no collision,
clearance, localization, lane, or integration status changes.

The target-bound extension in `E-20260930-INT-456` projects the frozen catalog
of 46 keyboard and 29 phone targets into each official-mesh render and records
center occlusion plus safe-region overlap. The official geometry obscures
`1/14/14` centers and overlaps `5/17/18` safe regions at
`ready/hover_t/hover_e`. These labels are now suitable for offline abstention
training and evaluation fixtures. Their camera and placement remain nominal,
so they install no physical qualification or authority.

The AI data builder in `E-20260930-AI-457` converts those target-bound renders
into 450 training and 225 held-out evaluation rows. Training uses `ready` and
`hover_t` with nominal, dim, and bright images; evaluation holds out both the
`hover_e` pose and warm, glare, and blur transformations. It labels only
`target_visible` or `abstain` under a predeclared 0.20 safe-region-overlap
threshold. This is a reproducible synthetic development dataset, with no
deployment qualification or change to the `ModelMotionBatchV2` boundary.

The first small occlusion baseline in `E-20260930-AI-458` demonstrates why the
held-out grouping matters. A class-weighted logistic model reaches 99.3%
training accuracy but only 66.7% on the held-out pose and lighting families,
with 13 missed abstentions, 62 false abstentions, Brier score `0.3274`, and
ten-bin calibration error `0.3329`. It remains blocked. The consumed synthetic
evaluation split cannot now be used to tune a replacement; new pose groups
must be declared before the next model experiment.

The predeclared pose expansion in `E-20260930-AI-459` now provides that new
geometry without consuming its final evaluation role. Nine official-mesh poses
are partitioned as three previously observed training poses, two new `H`
development poses, and four untouched `1`/`PERIOD` evaluation poses. The six
new states are selected by sequence from the hash-bound zero-authority actual-
emitter schedule. All masks are pose-distinct. These external synthetic bytes
still omit measured tool and camera-support geometry and cannot qualify physical
visibility, localization, collision clearance, or execution.

The three-way dataset in `E-20260930-AI-460` materializes 675 training, 450
development, and 900 reserved evaluation target crops across 27 distinct
images. Pose groups and lighting families are pairwise disjoint, and two
independent builds are byte-identical. The evaluation bytes exist for identity
and leakage checks but remain unscored; the next candidate must be selected
using training and development only before that group is evaluated once.

The compact selection experiment in `E-20260930-AI-461` selected brightness-
normalized chromatic/edge features at threshold `0.25` using development only,
then consumed the reserved evaluation once. Although evaluation accuracy is
94.0%, the model misses 52 of 129 required abstentions. That 40.3% miss rate is
unsafe for occlusion admission, so the checkpoint remains blocked and this
evaluation group is unavailable for further selection or tuning.

The transit-geometry expansion in `E-20260930-AI-462` adds twelve unused
actual-emitter schedule states while folding all consumed endpoint poses into
training. Six outbound/return states form development and six inter-key states
remain untouched evaluation geometry. All 21 official-mesh masks are distinct;
the reserved inter-key group contains materially more occlusion than the
development group. No model has consumed or scored the new evaluation group.

The deterministic dataset in `E-20260930-AI-463` expands the 21-pose source to
6,075 training, 1,350 development, and 1,350 reserved evaluation rows across
117 distinct images. Previously consumed lighting is confined to training;
development and evaluation use new pairwise-disjoint lighting families. Two
independent builds are byte-identical, and the evaluation group remains
unscored and unavailable during the next candidate-selection step.

The tiny spatial candidate in `E-20260930-AI-464` meets its predeclared
development missed-abstention preference and then misses only 2 of 276
occlusions on the fresh transit evaluation. It also falsely abstains on 433 of
1,074 visible targets, so it is substantially safer than the prior crop model
on its own fresh test but too conservative for useful typing cadence. The
checkpoint remains synthetic-only and blocked; its evaluation split is now
consumed and cannot be used to tune the false-abstention rate.

The fresh specificity campaign in `E-20260930-AI-465` freezes twelve unused
actual-emitter schedule poses and six new lighting families before rendering.
Its tiny spatial candidate reduces held-out false abstentions to 28 of 1,239
visible targets, but misses 15 of 111 required abstentions. The result is
reproducible and substantially more usable, while the higher dangerous miss
rate blocks promotion. Its evaluation is consumed and cannot be used for
threshold or architecture tuning.

The deterministic video bundle in `E-20260930-AI-466` turns the exact AI-465
source frames and frozen predictions into two hash-bound H.264 review artifacts.
One records all 33 official-mesh poses with ground-truth safe-region overlays;
the other records all 18 held-out pose/lighting images with per-target model
outcomes, including every false stop and missed abstention. Independent exports
are byte-identical. The videos add reviewable progression evidence only: they
do not add temporal physics, new evaluation data, runtime authority, or physical
qualification, and the AI-465 candidate remains blocked.

The target-aware experiment in `E-20260930-AI-468` predeclares twelve unused
actual-emitter schedule poses and six new lighting families, then gives the
tiny RGB crop model one additional catalog-derived safe-region channel. The
simulator robot mask remains label-only. On a fresh held-out synthetic group,
missed abstentions fall to 5 of 165 and false abstentions remain 27 of 1,185;
two complete builds are byte-identical. This is the first candidate in this
sequence to hold both synthetic error rates below 5% on its own fresh split.
It remains blocked because exact target alignment is assumed and neither final-
camera localization uncertainty nor physical support/tool geometry is present.
The consumed evaluation may not tune another candidate.

The deterministic v2 video bundle in `E-20260930-AI-469` binds the exact
four-channel AI-468 checkpoint to 45 official-mesh pose frames and all 18
consumed evaluation images. Two independent exports are byte-identical and the
evaluation overlays reproduce the frozen 160/1,158/27/5 confusion counts. The
manifest explicitly identifies the known-target safe-region channel and the
absence of simulator robot-mask input. This adds reviewable evidence only; it
does not qualify target alignment, add temporal physics, or change the model's
blocked status.

The development-only perturbation study in `E-20260930-AI-470` renders six
previously unused arm states and measures the frozen AI-468 checkpoint under
33 predeclared joint crop/mask offsets. No training or evaluation group is
present. The nominal fresh-pose result already misses 9 of 108 abstentions.
At 1 mm, false stops range from 35 to 62 of 1,242 visible targets; at 2 mm the
worst direction reaches 272; and selected 4–8 mm directions cause near-total
stopping. This confirms that exact target alignment was a material assumption.
Future inference must bind calibrated localization uncertainty and abstain when
the safe-region fit is not supported; these synthetic offsets do not establish
a deployable millimetre bound.

The offset-augmented candidate in `E-20260930-AI-471` assigns one deterministic
nominal, 1 mm, or 2 mm translation to every v5 training row, then freezes its
threshold and uncertainty policy on the v6 development-only corpus. Nominal
misses improve from 9 to 3 of 108 while false stops rise from 35 to 44 of 1,242.
The worst 1 mm direction still misses 6 abstentions, so no nonzero bound meets
both 5% limits. The policy consequently supports only 0 mm and must abstain on
any nonzero localization uncertainty. Evaluation remains unopened. This is a
real safety improvement and an explicit fail-closed policy, but the zero bound
is operationally too strict and blocks a fresh evaluation campaign.

The frozen-weight policy refreeze in `E-20260930-AI-472` corrects the original
0.05 threshold-grid blind spot without retraining or opening evaluation. A
predeclared 0.001 grid selects threshold `0.093`. Across nominal and all eight
1 mm directions, the worst missed-abstention count is `4/108` and the worst
visible false-stop count is `62/1242`, both below 5%. The source and repeated
checkpoint state dictionaries are identical, and two complete policy outputs
are byte-identical. The resulting synthetic uncertainty bound is 1 mm;
anything larger must return `abstain_localization_uncertain`. The 2 mm ring
fails, and this result remains synthetic development evidence rather than
physical-camera calibration or deployment qualification. A fresh untouched
evaluation campaign may now be predeclared against the frozen policy.

The one-time fresh synthetic evaluation in `E-20260930-AI-473` interleaves six
previously unused actual-emitter schedule poses between earlier transit
samples and holds out three new lighting families. Its 1,350 rows contain 270
required abstentions and 1,080 visible targets. The frozen E-472 checkpoint
keeps the worst missed-abstention rate to `3/270 = 1.11%`, but nominal false
stops are already `83/1080 = 7.69%` and the worst 1 mm direction reaches
`96/1080 = 8.89%`. The synthetic evaluation gate therefore fails and the
checkpoint remains blocked. The consumed v7 group cannot tune a successor.
Failure concentration on persistent keyboard hard negatives, especially
`ENTER`, `EQUAL`, `MINUS`, and `0`, directs the next work toward a separately
predeclared development corpus and improved target-specific specificity while
preserving the low missed-occlusion rate.

| Worker/lane | Stage | Paths expected to change | Branch/commit | State |
|---|---|---|---|---|
| AI | S2/S3 | fresh development-only hard-negative campaign for frozen E-472; no training or evaluation rows | `issue/190-isaac-sim-host` / pending | ACTIVE |
| Unclaimed | S2/S3 | physical-camera deployment qualification and safe-region-fit precision evidence | — | AVAILABLE |
| ARM | S4 | collect four physical-original `camera_support_optics` bindings through onboarding, then run the ARM-070 intake; no synthetic promotion | ARM-071 | WAITING_FOR_ORIGINALS |

## Worker update procedure

Each worker follows this process for every increment:

1. Pull/fetch current repository state and read this document, `CONTRACT.md`,
   and `MODEL_COMMAND_RUNTIME_IMPLEMENTATION_PLAN.md`.
2. Confirm the selected stage and the other lane's latest evidence.
3. Add or update one active work claim. Do not claim broad directories when a
   narrower path is sufficient.
4. Work on a feature branch or otherwise coordinate before editing shared files.
5. Make one bounded change. Do not mix model training, schema migration,
   controller behavior, and physical testing in one unreviewable increment.
6. Run lane tests plus the shared boundary suite affected by the change.
7. Append an evidence row. Update only the worker's owned lane status.
8. If both lanes are ready, run the shared integration gate using actual producer
   output—not a hand-authored substitute—and append an `INT` evidence row.
9. Review diff, run the repository audit, commit, and push or open a pull request
   according to the repository contribution process.
10. Leave failed evidence visible and name the precise next dependency.

## Merge and conflict rules

- AI workers primarily own `software/ai/rocell_ai`, training/evaluation assets,
  AI tests, and the AI-lane portions of this plan.
- Arm workers primarily own `software/src/rocell`, arm/runtime tests, controller
  adapters, and the arm-lane portions of this plan.
- Shared schemas, shared model types, this stage board, and integration tests
  require cross-lane review.
- Do not silently change a field's meaning while retaining its schema version.
- Do not loosen a consumer because a producer emitted invalid data; correct the
  producer or perform a documented schema migration.
- Resolve concurrent ledger edits by retaining both evidence rows in chronological
  order. Never discard another worker's evidence to resolve a Git conflict.

## Immediate coordinated work order

1. **S1 software boundary — complete for zero authority:** v2 producer bytes,
   strict decoding, trusted registry, freshness, mutation rejection, and ordered
   `H,H,I` ingress are covered by the shared conformance profile.
2. **AI S2/S3:** qualify the implemented precision adapter from final-camera
   physical originals and reduce or bound localization uncertainty inside the
   applicable key safe regions. The current 14.400834977 mm synthetic bound is
   retained evidence but may not populate deployment qualification.
3. **Arm S4:** collect the four physical-original camera/support/optics bindings
   already named by ARM-070; do not synthesize the trusted registry from model output.
4. **Integration S2:** rerun the conformance profile using actual qualified AI
   output and physical-original registry records, beginning with one keyboard target.
5. Continue measured planning and controller qualification independently. Speed,
   clearance, dynamics, encoding, transport, and retry remain arm-owned. Use the
   [optimized typing execution plan](../../docs/OPTIMIZED_TYPING_EXECUTION_PLAN.md)
   for the ordered T1-T6 implementation and qualification gates.
6. Require independent device-effect verification before expanding from one key
   to strings or phone workflows.
7. Rebuild `arm072_model_arm_operational_readiness.json` after any retained
   source advances. Do not begin a single-action review unless all six stage
   assessments are READY; the report itself never grants dispatch authority.

## Definition of shared completion

The shared program is not complete merely because the model predicts plausible
coordinates or the arm follows manually supplied commands. Completion requires:

- supported user text produces the intended deterministic plan;
- fresh qualified perception produces a correctly bounded named target;
- the exact batch survives strict arm admission;
- measured planning produces a smooth collision-screened trajectory;
- one controlled writer executes it without ambiguous retry;
- independent evidence confirms the intended device effect; and
- held-out missions meet declared correctness, recovery, and latency thresholds.

Until then, every artifact remains a scoped research, simulation, shadow,
commissioning, or bounded physical result with its limitations intact.

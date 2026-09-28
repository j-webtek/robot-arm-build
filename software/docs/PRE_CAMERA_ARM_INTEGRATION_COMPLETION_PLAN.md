# Pre-camera arm integration completion plan

- **Document status:** Active implementation plan; no hardware authority
- **Owners:** Arm/runtime lane, with shared AI/arm contract review
- **Audience:** Runtime, planning, controller, test, and AI-integration contributors
- **Reviewed:** 2026-09-28 against the merged T1, T2A, T2B-IK, and
  collision-evidence intake boundaries
- **Authority:** Normative for pre-camera implementation order and evidence;
  explanatory only for later physical qualification

## Purpose

Complete the valuable arm-side integration work that does not require the final
camera, measured keyboard localization, or new physical movement. The result
should accept a strictly admitted AI motion batch, preserve its intended order,
produce a smooth and dynamically bounded arm-owned schedule, rehearse safe
one-action execution, and explain every acceptance or rejection through durable
evidence.

This plan operationalizes T2 through T4 of the
[optimized typing execution plan](OPTIMIZED_TYPING_EXECUTION_PLAN.md). It does
not replace the [shared AI/arm workplan](../ai/docs/SHARED_AI_ARM_WORKPLAN.md),
which remains the cross-workstream status authority.

## Starting point

The repository already provides:

- strict, hash-bound `ModelMotionBatchV2` admission;
- ordered `TypingExecutionPlanV1` compilation, including repeated targets;
- Cartesian quintic shaping and bounded screening samples;
- deterministic IK, joint-bound, margin, Jacobian-rank, and continuity checks;
- a collision-evidence intake that names the installed evidence it still needs;
- controller encoding previews, one-action permit and lifecycle rehearsals, and
  durable no-replay receipts; and
- zero-write controller contract tests.

The remaining pre-camera gap is composition. Exact IK results are not yet a
joint-dynamics-qualified typing schedule; the optimized typing path is not yet
connected end to end to the controller preview and lifecycle boundaries; and
fault, replay, caching, and performance behavior need one common qualification
campaign.

## Required end state

At the pre-camera completion gate, the repository must deterministically take a
fixture such as `type robot` through:

```text
canonical AI bytes
  -> strict admission
  -> ordered typing plan
  -> Cartesian trajectory
  -> exact-sample IK
  -> joint-space time scaling
  -> collision-evidence decision
  -> rolling-horizon preview
  -> one-action execution envelope
  -> exact zero-write controller encoding
  -> correlated lifecycle receipt
```

For the current unmeasured workcell, the normal final result is an exact,
machine-readable blocker such as `MEASURED_INSTALLED_PROFILE_REQUIRED`, not a
fabricated pass. Synthetic fixtures may exercise later stages only when every
artifact remains explicitly labeled `SYNTHETIC_OFFLINE` and grants no physical
authority.

## Operating rules

1. The AI proposes ordered task intent and target evidence; the arm owns IK,
   dynamics, collision policy, timing, encoding, permits, and retry policy.
2. The commit horizon is one action. Preview and cache artifacts have zero
   authority.
3. No test may silently replace measured calibration, geometry, feedback, or
   camera evidence with a nominal value.
4. Repeated targets remain repeated actions; no optimization may reorder or
   deduplicate user intent.
5. An ambiguous dispatch or possible contact is terminal and never
   automatically retried.
6. Cache hits may reduce computation only. They may not bypass fresh-state,
   IK, collision, dynamics, or permit checks.
7. Simulation timing is not physical typing speed. Controller feedback is not
   proof that the intended key appeared.
8. Every artifact is canonical, content-addressed, versioned, resource-bounded,
   and traceable to its inputs.
9. This plan authorizes no controller startup, transport access, command write,
   torque change, movement, or firmware installation.

## Delivery sequence

Work proceeds in the order below. A stage may begin in a feature branch before
the prior stage merges, but it cannot be marked complete until all dependencies
and its evidence gate pass.

| ID | Deliverable | Depends on | Camera needed | Physical I/O | Initial status |
| --- | --- | --- | ---: | ---: | --- |
| PC0 | Freeze fixtures, profiles, metrics, and status vocabulary | Existing T1/T2 artifacts | No | None | COMPLETE |
| PC1 | Joint-space dynamics and deterministic time scaling | PC0, T2B-IK | No | None | COMPLETE |
| PC2 | Golden end-to-end shadow pipeline | PC1, collision intake | No | None | COMPLETE |
| PC3 | Rolling-horizon rebinding and restart safety | PC2 | No | None | COMPLETE |
| PC4 | Typing-specific zero-write controller bridge | PC2, PC3 | No | None | COMPLETE |
| PC5 | Fault injection and property testing | PC1-PC4 | No | None | COMPLETE |
| PC6 | Unified trace journal and deterministic replay | PC2-PC5 | No | None | COMPLETE |
| PC7 | Safe transition cache in shadow mode | PC3, PC6 | No | None | COMPLETE |
| PC8 | Performance benchmark and readiness report | PC1-PC7 | No | None | IN_PROGRESS |
| PC9 | Camera-arrival evidence tooling and dry run | PC6 | No for tooling | None before arrival | NOT_STARTED |
| PC10 | Pre-camera integration closure | PC0-PC9 | No | None | NOT_STARTED |

## PC0 — Freeze the qualification basis

**Completed 2026-09-28:** the retained
`pre_camera_typing_qualification_basis_v1.json` now pins the canonical source
files, fixture sequences, synthetic-only calibration/dynamics/controller
identities, Cartesian policy, stable terminal vocabulary, resource ceilings,
and benchmark requirements. A strict bounded loader rejects duplicate JSON
members, authority promotion, reordered fixtures, crossed identity hashes,
unsafe paths, source drift, non-finite dynamics, and physical claims. Ten
focused tests and eighteen existing T1/T2 regression tests pass with no
hardware access. This completion freezes the offline test basis only; none of
its synthetic values are installed-workcell measurements.

### Deliverables

- Select canonical fixtures for `robot`, `book`, `qaz`, `plm`, `H,H,1,PERIOD`,
  space, enter, and same-key repetition.
- Pin the schema, target catalog, arm model, calibration-fixture identity,
  planner policy, synthetic dynamics profile, and controller encoding profile
  used by offline tests.
- Define stable outcome codes for every planned gate.
- Define benchmark measurements and ceilings before optimization begins.
- Record that the pinned profiles are test fixtures, not installed workcell
  qualifications.

### Gate

Repeated compilation produces identical bytes and hashes on supported Python
versions. Crossed identity, reordered action, unsupported character, and
unbounded input fixtures fail closed. No test fixture is labeled measured.

## PC1 — Joint-space dynamics and deterministic time scaling

**Completed 2026-09-28:** the PC1 boundary consumes
the exact hash-valid T2B-IK sample order, explicitly maps the semantic PC0
joint order onto the canonical URDF joint order, applies deterministic bounded
time scaling, emits strictly monotonic nanosecond timestamps, reports whole-
schedule and per-segment velocity/acceleration/jerk demand and margin, and retains explicit
installed-dynamics, controller-tracking, collision, and fresh-state blockers.
The canonical parser revalidates artifact and profile hashes, exact fields,
sample/segment lineage, and timestamp consistency. Focused tests exercise all
three limiting dimensions at just-inside and just-outside rescale bounds,
stationary and reversal behavior, crossed order and source lineage, non-finite
limits, and deterministic reconstruction. This gate is synthetic and offline;
it produces no controller command or physical authority and does not qualify
installed dynamics or tracking.

### Deliverables

- Add a typed, canonical joint schedule artifact consuming the exact ordered IK
  sample results without route regeneration.
- Pin per-joint velocity, acceleration, and jerk ceilings in an arm-owned
  dynamics profile.
- Calculate segment durations and time-scale the route until every sampled
  joint stays within those ceilings.
- Preserve semantic dwell and phase boundaries while distinguishing collision
  samples from commanded stop points.
- Report demand, limit, margin, rescale factor, duration, and limiting joint for
  every segment and for the complete action.
- Reject non-finite values, non-monotonic time, discontinuity, missing joints,
  excessive rescaling, resource overflow, and crossed lineage.

### Tests

- Exact limit, just-inside, and just-outside cases for each dynamic dimension.
- Stationary repeated-key segment and direction reversal.
- Very short and long transitions.
- Mutation tests for sample order, timestamp, joint order, profile hash, and
  source hash.
- Determinism across repeated runs and supported platforms.

### Gate

Every passing schedule proves its pinned synthetic joint limits with positive
reported margin. Every violation rejects deterministically. The artifact still
states that controller tracking and settling are physically unqualified.

## PC2 — Golden end-to-end shadow pipeline

**Completed 2026-09-28:** one zero-I/O orchestration boundary composes the
real strict V2 decoder, trusted-registry admission and freshness recheck, T1
typing compiler, T2A Cartesian planner, T2B-IK screen, PC1 joint schedule, and
collision-evidence intake. Retained golden receipts for `robot` and
`H,H,1,PERIOD` preserve repeated targets and all nine stage hashes before
stopping at the honest installed-profile/fresh-state blocker. The retained
schema and parser revalidate the outer receipt hash, exact field and stage-hash
sets, ordered targets, terminal blocker lineage, and zero-authority assertions.
Eight stage-input mutations reject at the strict decoder, ingress, freshness,
IK lineage, or dynamics owner; five independently rehashed receipt mutations
reject at their owning receipt rule. This gate remains synthetic and grants no
transport, controller command, permit, or physical authority.

### Deliverables

- Compose the real AI V2 decoder, typing compiler, Cartesian planner, IK screen,
  joint dynamics gate, and collision-evidence intake behind one zero-I/O entry
  point.
- Retain one golden `type robot` trace and the punctuation/repetition fixture
  `H,H,1,PERIOD`.
- Store canonical stage hashes, ordered action identities, terminal status, and
  exact blocker lineage.
- Add mutation fixtures that change one field at a time and verify rejection at
  the owning boundary.

### Gate

The same input produces the same ordered stage hashes and terminal receipt. A
crossed or mutated input fails at the earliest responsible gate. The real
unmeasured path stops at its honest evidence blocker; the synthetic path cannot
gain permits, transport, or deployment status.

## PC3 — Rolling-horizon rebinding and restart safety

**Completed 2026-09-28:** `typing_rolling_horizon_v1` now retains exactly one
current action and at most one zero-authority preview. Each horizon is bound to
the exact observed start state, feedback receipt, controller session,
configuration epoch, calibration, tool profile, dynamics profile, freshness
limit, plan, and deadline. Revalidation deterministically invalidates and
discards both slots when any bound identity drifts or evidence expires.
Pre-dispatch restart reconstructs intent without replay; once a dispatch intent
has been retained, restart terminates `OUTCOME_UNCERTAIN` with automatic retry
forbidden. A strict parser and JSON Schema reject crossed indices, epochs,
hashes, roles, or authority fields. Twenty-four focused tests and fifty-four
affected lifecycle/planning tests pass with zero hardware access. This is
offline orchestration evidence only; it issues no permit or controller command.

### Deliverables

- Implement a state machine with a one-action commit horizon and one-action
  preview horizon.
- Bind the current action to an observed-state identity and configuration epoch.
- Preview the next action with zero authority while the current action remains
  pending.
- Invalidate preview on state drift, calibration/tool/profile change, stale
  evidence, controller-session change, cancellation, or expired deadline.
- Reconcile restarts from durable state without replaying a possibly completed
  action.

### Gate

Preview never creates a permit. Every forced invalidation discards or replans
the preview. Pre-dispatch restart may safely reconstruct intent; post-dispatch
or ambiguous restart terminates `OUTCOME_UNCERTAIN` with retry forbidden.

## PC4 — Typing-specific zero-write controller bridge

**Completed 2026-09-28:** `typing_controller_bridge_v1` now selects only the
PC3 current action from the exact arm-owned timed joint schedule, cross-checks
its semantics against the bound trajectory, and encodes deterministic pinned
Waveshare T=102 bytes. The sealed preview binds the action, schedule, dynamics,
configuration epoch, observed state, controller session, collision
qualification, execution envelope, single-use permit identity, and encoding
profile. It records bounded T=105/T=1051 feedback requirements but neither
consumes the physical permit nor opens a transport. Frozen golden bytes cover
ordinary motion, while focused tests cover repeated-target identity,
controller-setting boundaries, crossed lineages, expiry, feedback deadlines,
and independently rehashed mutations. Fifteen focused tests and eighty-three
affected protocol/planning tests pass with zero writes. PC5 fault campaigns may
now begin; installed-workcell qualification and physical authority remain
blocked.

### Deliverables

- Convert one qualified timed joint action into the existing pinned Waveshare
  command representation without opening a transport.
- Keep joint order, unit conversion, speed, acceleration, timing, and command
  policy arm-owned.
- Bind exact encoded bytes to the action, schedule, dynamics profile,
  configuration epoch, observed state, execution envelope, and single-use
  permit identity.
- Produce expected acknowledgement and feedback requirements plus bounded
  deadlines and terminal receipt fields.
- Add golden-byte fixtures for ordinary movement, repetition, boundary values,
  and invalid inputs.

### Gate

Exact controller bytes are deterministic and match the pinned protocol tests.
One action maps to one sealed dispatch intent. No AI field can directly inject
controller JSON, arbitrary dynamics, a port, retry behavior, or authority.

## PC5 — Fault injection and property testing

**Completed 2026-09-28:** a bounded, canonical campaign contract freezes
all 35 required cases across the six fault families below. Every observation
must carry its stable reason and terminal disposition and prove zero escaped
exception, authority leak, automatic retry, reorder, silent fallback, or
unbounded allocation. The strict report parser independently reconstructs the
campaign summary and hash. In parallel, the live V2 decoder gained a 32-level
JSON-depth ceiling and stable recursion rejection; rolling horizons now cap at
64 actions; and controller previews cap command count and per-command payload
bytes while normalizing malformed protocol payloads. The completion tranche
drives all declared planning, transport/feedback, sequence, restart, identity,
order, cache, deadline, cancellation, and resource cases through their actual
zero-hardware owning boundaries. A separately hash-bound, 64-entry observation
cache rejects corruption, crossed qualification identity, malformed contents,
duplicates, and overflow without carrying commands or authority. Twenty-nine
focused campaign tests and the 145-test affected boundary suite pass with zero
physical I/O. PC6 deterministic trace-journal work is ready.

### Required fault families

- malformed, duplicate, missing, oversized, NaN, infinity, and deeply nested
  model inputs;
- stale observation, crossed calibration/catalog/model/profile identities, and
  reordered or duplicated action indices;
- unreachable IK, joint-limit loss, singularity, discontinuity, dynamics
  overflow, collision-evidence absence, and clearance loss;
- late acknowledgement, missing or malformed feedback, partial write,
  disconnect, controller restart, sequence mismatch, and ambiguous completion;
- process crash before intent, after durable intent, during dispatch, after
  possible contact, and before effect verification; and
- cache corruption, cache identity crossing, deadline expiry, cancellation, and
  bounded-resource exhaustion.

### Gate

Property and mutation campaigns produce no uncaught exception, authority leak,
automatic retry, reorder, silent fallback, unbounded allocation, or inconsistent
terminal outcome. Every rejected case has a stable machine-readable reason.

## PC6 — Unified trace journal and deterministic replay

**Checkpoint 2026-09-28:** the first replay-only backbone now seals an exact
14-stage lineage from request and AI batch through ingress, execution plan,
trajectory, IK, joint schedule, collision screening, controller preview,
permit policy, encoding, dispatch rehearsal, feedback rehearsal, and the
effect-verification placeholder. Each bounded artifact is represented only by
its byte count and SHA-256 digest in a stage-order hash chain; raw payloads are
not copied into the journal. Deterministic replay detects missing, mutated,
empty/truncated, extra, reordered, and correlation/request-crossed artifacts.
The seven focused tests and 99-test affected journal/planning suite pass with
zero hardware access or authority. The next checkpoint adds the real PC2-PC5
adapter: it validates the strict batch, shadow receipt, rolling horizon,
controller preview, and fault-campaign contracts; rejects crossed request,
action, horizon, or schedule lineage; and derives the exact replay artifacts
and explicit not-observed effect placeholder. The combined 103-test suite
passes. ARM-088 adds the contained package and CLI: canonical
manifest/journal files plus 14 exact artifact files live beneath a
caller-selected nonsymlink evidence root; package identifiers cannot contain
paths; every file is bounded and hash-checked; and sensitive keys, absolute
paths, symlinks, noncanonical JSON, deletion, mutation, and unexpected entries
reject. `replay-typing-trace` verifies byte identity only and reports zero
authority. Twelve package tests, two CLI tests, and the 117-test affected suite
pass. PC6 remains in progress only until one actual adapter-produced golden
package is retained and replayed from a clean checkout. ARM-089 completes the
gate with an adapter-generated retained package containing the exact 14-stage
trace. The adapter regenerates every retained byte identically, and the
checked-in package replays through the CLI from an isolated workspace with
zero hardware authority. The expanded affected suite passes 119 tests.

### Deliverables

- Define one correlation lineage from request and AI batch through plan,
  trajectory, IK, dynamics, collision, preview, permit, encoding, dispatch
  rehearsal, feedback rehearsal, and effect-verification placeholder.
- Journal intent durably before any future dispatch boundary.
- Record canonical hashes and references rather than copying large or sensitive
  payloads unnecessarily.
- Provide a replay command that reconstructs decisions without hardware and
  detects missing or mutated artifacts.
- Redact ports, host identity, credentials, and private captures according to
  repository evidence policy.

### Gate

A clean checkout can replay the retained synthetic traces to the same decisions
and hashes. Mutation, deletion, truncation, or lineage crossing is detected and
cannot be reported as a pass.

## PC7 — Safe transition cache in shadow mode

**Checkpoint 2026-09-28:** ARM-090 adds the first bounded, deterministic
transition cache. Its exact directional key binds source and destination
targets, calibration, catalog, tool, arm model, dynamics, planner policy, and
device-pose epoch. Entries retain only canonical joint seed positions, a route
duration estimate, a planning-time-saved estimate, and the prior schedule hash.
Every hit requires fresh matching start state plus explicit IK, collision,
dynamics, and permit-policy validation; the returned hint still requires fresh
planning and full safety screening and carries no command, permit, or authority.
FIFO eviction, identity invalidation, corruption discard, and hit/miss/
validation/discard/time-saved metrics are deterministic. Fourteen focused tests
pass, including an actual cached-versus-uncached PC2 pipeline comparison, and
the affected PC2-PC7 suite passes 133 tests. ARM-091 completes the broader
campaign across every canonical PC0 typing fixture plus explicit reverse
travel, repeated keys, number/punctuation, and single-key routes. All seven
bound identity dimensions invalidate stale entries, and a seeded 128-operation
capacity campaign is deterministic and bounded. Thirty-one focused tests and
the 150-test affected suite pass. Cached and uncached receipts and schedule
hashes remain identical, satisfying the PC7 gate.

### Deliverables

- Cache only planning seeds and timing estimates for directional target pairs.
- Key entries by source/destination target, calibration, catalog, tool, arm
  model, dynamics, planner policy, device-pose epoch, and direction.
- Revalidate start state, IK, collision evidence, dynamics, and permit on every
  use.
- Track hit, miss, validation, discard, corruption, and time-saved metrics.
- Bound cache size and provide deterministic eviction and invalidation.

### Gate

Cached and uncached planning produce equivalent admitted schedules within the
declared deterministic contract. A cache hit never changes safety disposition
or creates authority. Crossed or stale entries are rejected rather than used.

## PC8 — Performance benchmark and readiness report

**Checkpoint 2026-09-28:** ARM-092 adds the bounded performance-report
contract. It requires at least 50 unique samples for cold cache, warm cache,
long strings, repeated keys, punctuation, keyboard extremes, forced rejection,
direct hover, and park-between-key baseline scenarios. Every sample accounts
for the nine declared CPU stages, total CPU, action and screening-sample counts,
serialized bytes, peak process memory, predicted route duration, cache result,
and estimated time saved. The report computes deterministic nearest-rank
p50/p95/p99 statistics, enforces all retained PC0 ceilings, and permanently
labels simulated duration as not being measured typing speed. Eight focused
tests and the 158-test affected suite pass. PC8 remains in progress pending an
instrumented pipeline runner, retained report, and bottleneck/readiness review.
ARM-093 adds the instrumented runner over the actual PC2 decoding, static
validation, planning, IK, time-scaling, collision-intake, and receipt boundaries.
It records process CPU, peak working set, screening samples, serialized receipt
bytes, predicted schedule duration, and declared cache estimates while keeping
preview and encoding at zero where the honest collision-evidence blocker stops
the route. Profiled and ordinary receipts are byte-equivalent. Ten focused
runner/report tests and the 160-test affected suite pass. A retained 50-sample-
per-scenario campaign and readiness analysis remain.

### Deliverables

- Benchmark p50, p95, and p99 where sample counts support them for decode,
  static validation, planning, IK, time scaling, collision intake, preview
  validation, encoding, and receipt creation.
- Measure total CPU time, peak bounded sample count, serialized artifact size,
  memory ceiling, cache behavior, and predicted route duration.
- Compare direct hover transitions with park-between-key baselines using the
  same route and safety policies.
- Run cold-cache, warm-cache, long-string, repeated-key, punctuation, keyboard
  extreme, and forced-rejection suites.
- Publish bottlenecks and budgets without presenting predicted duration as
  measured typing speed.

### Gate

The pipeline remains within declared resource ceilings, preserves every safety
margin, and shows a reproducible latency benefit or clearly documents why an
optimization was rejected. The report contains zero physical-performance
claims.

## PC9 — Camera-arrival evidence tooling and dry run

### Deliverables

- Prepare bounded commands and templates for original image capture, file
  hashing, persistent camera identity, mode/control readback, and retention.
- Prepare calibration inputs for camera-to-board, board-to-robot,
  keyboard-to-board, and tool-to-joint transforms with units and uncertainty.
- Prepare installed geometry, rigid attachment, cable-envelope, keyboard, and
  tool profile intake templates.
- Prepare real-capture localization evaluation and containment reports.
- Dry-run every tool with synthetic fixtures while ensuring that synthetic
  results cannot populate measured qualification slots.
- Provide an arrival-day checklist with explicit stop conditions and no
  implicit movement authority.

### Gate

Every required physical original has a documented destination, schema, hash,
review field, and downstream consumer. A synthetic dry run cannot advance the
measured configuration epoch or deployment registry.

## PC10 — Pre-camera integration closure

### Closure evidence

- All PC0-PC9 gates pass on a clean checkout.
- The full offline test matrix passes on the supported Windows and Ubuntu CI
  environments and supported Python versions.
- The `robot` and `H,H,1,PERIOD` golden traces replay deterministically.
- The live-path rehearsal stops exactly at missing measured evidence.
- The synthetic full-depth rehearsal reaches a zero-write terminal receipt with
  all synthetic labels intact.
- Fault injection proves bounded, deterministic failure and no automatic replay.
- Documentation, schema, dependency, repository, and audit checks pass.
- The shared workplan and evidence ledger receive exact commit, test, and
  limitation records.

### Exit status

Successful PC10 closure means:

> The arm software is ready to ingest final-camera measurements and begin
> separately authorized physical qualification.

It does **not** mean the camera, workcell, installed controller, collision
profile, contact behavior, outcome verification, physical typing speed, or
autonomous typing capability is qualified.

## Camera-dependent continuation

After camera arrival, work resumes at the existing shared gates:

1. collect and retain the final-camera originals;
2. commission the measured configuration epoch;
3. evaluate localization and uncertainty on disjoint real captures;
4. populate and screen the installed geometry and cable profile;
5. obtain a fresh observed arm state;
6. qualify one non-contact hover at the lowest speed class;
7. qualify one independently verified key action; and
8. expand to held-out short strings before performance tuning.

The [camera integration hold](../../docs/CAMERA_INTEGRATION_HOLD.md) remains in
force until its physical prerequisites are satisfied.

## Work and evidence procedure

For every PC increment:

1. implement one bounded deliverable;
2. add positive, negative, mutation, and resource-bound tests;
3. run focused tests, shared-boundary tests, documentation checks, and the
   relevant audit checks;
4. record exact commands, counts, commit identity, evidence class, result, and
   remaining blocker;
5. update this stage table and the shared workplan only after the gate passes;
6. preserve failed evidence rather than rewriting it; and
7. merge without modifying unrelated user-owned worktree changes.

## Completion checklist

- [x] PC0 qualification basis frozen
- [x] PC1 joint dynamics and time scaling complete
- [x] PC2 golden shadow pipeline complete
- [x] PC3 rolling horizon and restart safety complete
- [x] PC4 zero-write typing controller bridge complete
- [x] PC5 fault and property campaigns complete
- [x] PC6 trace journal and replay complete
- [x] PC7 transition cache shadow qualification complete
- [ ] PC8 performance report complete
- [ ] PC9 camera-arrival tools dry-run complete
- [ ] PC10 clean-checkout pre-camera closure recorded

## Related documents

- [Optimized typing execution plan](OPTIMIZED_TYPING_EXECUTION_PLAN.md)
- [Shared AI/arm workplan](../ai/docs/SHARED_AI_ARM_WORKPLAN.md)
- [Model command runtime implementation plan](../ai/docs/MODEL_COMMAND_RUNTIME_IMPLEMENTATION_PLAN.md)
- [Camera integration hold](../../docs/CAMERA_INTEGRATION_HOLD.md)
- [Evidence ledger](../ai/docs/EVIDENCE_LEDGER.md)
- [Documentation standard](../../docs/DOCUMENTATION_STANDARD.md)

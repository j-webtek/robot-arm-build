# Shared AI-to-arm workplan and evidence backbone

**Status:** active coordination document  
**Owners:** AI/model workstream and arm/runtime workstream  
**Started:** 2026-09-26  
**Repository:** `j-webtek/robot-arm-build`  
**Current baseline commit:** `ebe7eee` (`docs: establish shared AI arm workplan`)  
**Authority:** this document coordinates development; it grants no hardware authority

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

This document is intentionally shared and append-friendly. Workers update only
their owned lane fields, add evidence rows rather than rewriting history, and
use the integration gate to expose contract drift early.

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
lists AI as ready because no new AI authority is required; the arm adapter and
shared byte-level gate remain unfinished.

## Stage definitions

### S0 â€” Freeze the shared v1 seam

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

### S1 â€” Contract v2: freshness, uncertainty, and capability

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
- Require the entire uncertainty regionâ€”not only its centerâ€”to fit the measured
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

### S2 â€” Full zero-hardware text-to-envelope shadow path

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

### S3 â€” Measured localization and planning readiness

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

### S4 â€” Zero-write controller adapter and correlated receipts

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

### S5 â€” One independently verified physical key action

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

### S6 â€” Ordered multi-action keyboard missions

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

### S7 â€” Performance and operational qualification

**Goal:** improve speed only after correctness and recovery are demonstrated.

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

### P1 â€” Separate phone capability track

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
#### E-YYYYMMDD-AI|ARM|INT-NNN â€” short title

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

### E-20260926-INT-001 â€” shared v1 boundary baseline

- Stage: S0
- Lane: INTEGRATION
- Commit: `3495512` (short baseline identity; use full SHA in future rows)
- Change: confirmed actual AI batch emitter, shared strict batch decoder, ingress,
  sequence coordinator, durable journal, and trajectory envelope use compatible
  ordered and hash-bound contracts.
- Inputs/fixtures: existing unit fixtures in `software/ai/tests` and
  `software/tests/unit`
- Command: `python -m pytest -q software/ai/tests/test_batch_emitter.py software/tests/unit/test_model_motion_ingress.py software/tests/unit/test_model_motion_sequence_coordinator.py software/tests/unit/test_model_motion_sequence_journal.py software/tests/unit/test_trajectory_execution_envelope.py`
- Result: PASS, 29 tests passed
- Artifacts: `software/ai/rocell_ai/batch_emitter.py`,
  `software/src/rocell/models/model_motion_batch.py`,
  `software/src/rocell/application/model_motion_ingress.py`,
  `software/src/rocell/application/model_motion_sequence_coordinator.py`,
  `software/src/rocell/application/trajectory_execution_envelope.py`
- Hardware writes: 0
- Physical movements: 0
- Limitations: synthetic/offline localization; no installed deployment
  qualification; planner not execution-ready; no writable adapter or independent
  task outcome verifier
- Supersedes: none
- Next dependency: S1 contract-v2 producer and consumer agreement

### E-20260926-AI-001 â€” conservative synthetic localization study

- Stage: S3
- Lane: AI
- Commit: `515e336` (short baseline identity; use full SHA in future rows)
- Change: recorded a conservative empirical radius study without installing a
  deployment qualification.
- Inputs/fixtures: frozen synthetic calibration/evaluation manifests
- Command: see `software/ai/eval/README.md`
- Result: PASS for declared synthetic study criteria; 6.037862 mm empirical
  radius, 0.988 evaluation coverage across 500 groups, 46 nominal targets fit
- Artifacts: `software/ai/eval/conservative_radius_v0_scorecard.json`
- Hardware writes: 0
- Physical movements: 0
- Limitations: fixed synthetic renderer family; no measured deployment domain;
  `qualification_installed=false`; `physical_execution_authorized=false`
- Supersedes: E-20260926-AI-000 implicit earlier radius study
- Next dependency: measured final-camera dataset and independent qualification

### E-20260926-AI-002 â€” actual prediction key-margin study

- Stage: S1 and S3
- Lane: AI
- Commit: `7056603` (short baseline identity; use full SHA in future rows)
- Change: evaluated the already-selected robust checkpoint's actual displaced
  predictions against independently rendered rotated key regions while retaining
  the previously fixed 6.037862 mm uncertainty radius.
- Inputs/fixtures: `software/ai/eval/prediction_margin_v0.manifest.json`, fresh
  seeds 13000000â€“13000099, three conditions per seed
- Command: see `software/ai/eval/README.md`
- Result: 8,516/13,800 predicted key locations contained the full uncertainty
  disk; 118/300 images fit all 46 oracle key regions; 0/13,800 predictions fit
  the current fixed nominal board rectangles
- Artifacts: `software/ai/eval/prediction_margin_v0_scorecard.json`
- Hardware writes: 0
- Physical movements: 0
- Limitations: synthetic geometry; oracle placement used only for scoring; no
  scene-fusion or full-batch test; no qualification installed
- Supersedes: none
- Next dependency: jointly define an independently evidenced keyboard-placement,
  orientation, target-map, frame, uncertainty, and freshness contract in S1

## Active work claims

| AI | S1 | temperature coordinate bias diagnosis | feature/translation-pair-evidence | ACTIVE |







Workers add a short row before beginning a potentially overlapping change and
remove it only in the same commit that appends the resulting evidence row.

| Worker/lane | Stage | Paths expected to change | Branch/commit | State |
|---|---|---|---|---|
| Unclaimed | S2 | qualified perception adapter and complete shared gate | — | AVAILABLE |
| Unclaimed | S4 | external reviewer publishes a typed decision for sealed r97 packet `987cbe86...b416`; collect/review all eight measured epoch components | — | AVAILABLE |

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
   outputâ€”not a hand-authored substituteâ€”and append an `INT` evidence row.
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

1. **Joint S1 design:** agree on v2 freshness, uncertainty, capability, and
   motion-hint semantics before coding either decoder or emitter.
2. **AI S1 producer:** implement the v2 emitter and adversarial producer tests.
3. **Arm S1 consumer:** implement strict v2 decoding, independent registry and
   freshness checks, and v1 migration fixtures.
4. **Integration S1:** round-trip actual v2 producer bytes and mutation-test every
   identity and freshness field.
5. **Joint S2 runner:** compose raw text through the actual emitter and arm
   coordinator into a single zero-hardware trace.
6. Continue measured S3 work independently, but do not install a qualification
   or promote the planner until its own held-out and commissioning gates pass.
7. Begin S4 zero-write encoding only from sealed envelopes; do not couple it to
   model internals or add controller fields to the batch.

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


### E-20260926-AI-003 â€” S1 AI semantic proposal and unchanged boundary regression

- Stage: S1
- Lane: AI
- Commit: `a0c2715429d7d2ebbe83f2866eef1b8abdfe6ae1` (exact tested runtime/fixture source baseline; proposal and evidence are added together in this ledger entry's containing commit)
- Change: proposed v2 freshness/lease, separate confidence and uncertainty,
  independent placement/oriented target regions, target-map and capability binding,
  and removal of motion hints. No schema, emitter or consumer change.
- Inputs/fixtures: five test modules and proposal SHA-256 identities in
  `software/ai/eval/s1_ai_design_v0.json`; existing synthetic fixture factories.
- Command: `python -m pytest -q software/ai/tests/test_batch_emitter.py software/tests/unit/test_model_motion_ingress.py software/tests/unit/test_model_motion_sequence_coordinator.py software/tests/unit/test_model_motion_sequence_journal.py software/tests/unit/test_trajectory_execution_envelope.py`
- Result: PASS, 29 existing boundary regression tests; v2 implementation and joint
  agreement remain pending. This result does not validate the proposed v2 semantics.
- Artifacts: [AI proposal](CONTRACT_V2_AI_PROPOSAL.md),
  [evidence manifest](../eval/s1_ai_design_v0.json)
- Hardware writes: 0
- Physical movements: 0
- Limitations: document-only semantic increment; no qualified localization,
  measured placement, v2 schema/decoder/emitter or integration gate evidence.
  Current synthetic margin failures remain preserved in AI-002.
- Supersedes: none
- Next dependency: arm-lane review of clock/lease ownership, independent placement
  record, oriented target-map representation, uncertainty composition, confidence
  source, capability registry and removal of hints; then jointly publish v2 schema.


### E-20260926-AI-004 â€” repository snapshot audit findings retained

- Stage: S1
- Lane: AI
- Commit: `a0c2715429d7d2ebbe83f2866eef1b8abdfe6ae1` (tracked baseline; same working tree as AI-003)
- Change: ran required read-only repository upload audit during the semantic increment.
- Inputs/fixtures: tracked baseline plus `CONTRACT_V2_AI_PROPOSAL.md`; scanner
  `scripts/audit_github_snapshot.py`, repository text and archive contents.
- Command: `python scripts/audit_github_snapshot.py`
- Result: FAIL (exit 1), 5,587 paths, 784.7 MiB, 14 credential-literal-review
  findings in existing `software/tests/unit/` files; none in the new AI proposal.
- Artifacts: scanner and existing test fixtures at the source commit; no secret
  values copied into evidence.
- Hardware writes: 0
- Physical movements: 0
- Limitations: heuristic audit findings remain unresolved; this is not a clean
  repository security-audit claim. No affected fixture was changed by this increment.
- Supersedes: none
- Next dependency: fixture owners review the 14 existing test-literal findings;
  S1 still depends on arm-lane semantic agreement listed in AI-003.


### E-20260926-AI-005 â€” analytic oriented-target acceptance cases

- Stage: S1
- Lane: AI
- Commit: `72f12ffaa16aaf0bea002f335af8260afc432bb0` (evaluation-helper source baseline; new fixtures/tests and evidence committed together in this entry's containing commit)
- Change: added 10 analytic cases for independent target geometry, exact edge,
  uncertainty crossing, rotation, displaced targets and self-centering failure.
- Inputs/fixtures: `software/ai/eval/s1_geometry_cases_v0.json`; exact file hashes
  in `software/ai/eval/s1_geometry_evidence_v0.json`.
- Command: `python -m pytest -q software/ai/tests/test_s1_geometry_cases.py software/ai/tests/test_prediction_margin.py`
- Result: PASS, 7 tests including 10 analytic vectors. Rotated enclosing AABB
  accepts a point the true key region rejects; self-centering hides displacement.
- Artifacts: [vectors](../eval/s1_geometry_cases_v0.json),
  [evidence](../eval/s1_geometry_evidence_v0.json), `tests/test_s1_geometry_cases.py`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: evaluation-only geometry; fixtures are not independent runtime
  evidence. No schema/emitter/decoder change, qualification or integration completion.
  These tests cannot establish provenance independence; that requires a registry.
- Supersedes: none
- Next dependency: arm-lane agreement on AI S1 proposal and independently evidenced
  placement registry/oriented target-map semantics before v2 producer implementation.


### E-20260926-AI-006 â€” geometry increment audit retains existing findings

- Stage: S1
- Lane: AI
- Commit: `72f12ffaa16aaf0bea002f335af8260afc432bb0` (tracked baseline plus AI-005 working-tree fixtures)
- Change: repeated the required read-only snapshot audit.
- Inputs/fixtures: repository snapshot and `scripts/audit_github_snapshot.py`;
  new geometry fixture/test files hashed in AI-005 evidence manifest.
- Command: `python scripts/audit_github_snapshot.py`
- Result: FAIL, exit 1; 5,590 paths, 784.7 MiB, same 14 existing
  credential-literal-review findings in arm unit fixtures; no new AI-file findings.
- Artifacts: scanner output locations match AI-004; no secret values retained.
- Hardware writes: 0
- Physical movements: 0
- Limitations: heuristic audit remains unresolved; no fixture-owner review claimed.
- Supersedes: none (preserves AI-004 failed evidence)
- Next dependency: fixture owners review findings; S1 semantic agreement remains pending.


### E-20260926-ARM-001 â€” strict v2 arm contract and admission boundary

- Stage: S1
- Lane: Arm/runtime
- Commit: `c579746dd801987fa66445fecbc1f5ebd8fe99b1`
- Change: accepted the AI lane's core S1 semantics and implemented the published
  v2 batch/proposal schemas, strict duplicate-free decoder, explicit board-plane
  geometry profile, epoch-ms freshness and external lease checks, monotonic
  post-admission deadline, independently supplied capability/evidence/qualification
  bindings, ordered action indexes, oriented convex target regions, additive
  localization-plus-placement bounds, and separate surface-normal qualification.
  Speed and clearance are absent. The output remains zero-authority.
- Inputs/fixtures: existing v1 fixtures; analytic S1 geometry vectors; v2 H/I
  keyboard fixtures with independently supplied region, placement, model, camera,
  clock, lease, map, board-frame, capability and qualification identities.
- Command: `python -m pytest software/ai/tests/test_s1_geometry_cases.py software/ai/tests/test_batch_emitter.py software/tests/unit/test_model_motion_ingress.py software/tests/unit/test_model_motion_ingress_v2.py software/tests/unit/test_model_motion_sequence_coordinator.py software/tests/unit/test_model_motion_sequence_journal.py software/tests/unit/test_trajectory_execution_envelope.py -q`
- Result: PASS, 48 tests. Both JSON schemas also passed Draft 2020-12 schema
  self-validation. V1 and v2 decoders explicitly reject the other's wire format.
- Artifacts: `software/ai/schemas/model_motion_batch_v2.schema.json`,
  `software/ai/schemas/model_motion_proposal_v2.schema.json`,
  `software/src/rocell/models/model_motion_batch_v2.py`,
  `software/src/rocell/application/model_motion_ingress_v2.py`, and
  `software/tests/unit/test_model_motion_ingress_v2.py`.
- Schema SHA-256: batch
  `cf59e2b2f42de78b2c22b27aad5bc44881c20bea68e16af727b04e5ffa8327ce`;
  proposal
  `9cfd3c1fc493a738112795a8153b94855e6281e0d9aac0d1ed19b2705174136e`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: arm fixtures are handcrafted consumer tests, not actual AI emitter
  bytes; no localization qualification is installed; trusted registry records are
  injected by the caller and still require production registry plumbing. Admission
  generates no trajectory or controller command and grants no execution authority.
- Supersedes: arm-side semantic-review dependency in AI-003; it does not supersede
  the AI producer or shared integration gates.
- Next dependency: AI lane emits canonical v2 bytes matching these frozen field
  meanings, then the shared S1 integration gate mutation-tests those actual bytes.


### E-20260926-ARM-002 â€” v2 increment audit retains existing findings

- Stage: S1
- Lane: Arm/runtime
- Commit: `c579746dd801987fa66445fecbc1f5ebd8fe99b1`
- Change: ran the required read-only repository snapshot audit after the v2 arm
  implementation.
- Inputs/fixtures: repository snapshot and `scripts/audit_github_snapshot.py`.
- Command: `python scripts/audit_github_snapshot.py`
- Result: FAIL, exit 1; 5,593 paths, 903.2 MiB, the same 14 existing
  credential-literal-review findings in arm unit fixtures; no v2-file finding.
- Hardware writes: 0
- Physical movements: 0
- Limitations: heuristic audit remains unresolved and this is not a clean
  repository security-audit claim.
- Supersedes: none; retains AI-004 and AI-006 failed evidence.
- Next dependency: fixture owners review the 14 existing findings independently
  of the S1 producer/consumer integration work.


### E-20260926-ARM-003 â€” monotonic pre-planner lease and registry recheck

- Stage: S1
- Lane: Arm/runtime
- Commit: `f0074b1d4d63e7acdbfeb7bd7c1c017a7179e2b5`
- Change: added a second fail-closed gate immediately before deterministic
  planning. It verifies the original ingress hash and zero-authority fields,
  rejects equality at the monotonic deadline, and rechecks the active capability,
  external scene lease, independent placement, and target-map hashes so revocation
  after ingress cannot silently enter planning.
- Inputs/fixtures: accepted v2 H/I ingress report, exact-deadline case, changed
  placement registry identity, and tampered ingress content.
- Command: `python -m pytest software/tests/unit/test_model_motion_ingress_v2.py software/tests/unit/test_model_motion_ingress.py software/tests/unit/test_model_motion_sequence_coordinator.py -q`
- Result: PASS, 28 tests.
- Artifacts: `software/src/rocell/application/model_motion_ingress_v2.py` and
  `software/tests/unit/test_model_motion_ingress_v2.py`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: this recheck does not plan, encode, or execute movement; active
  registry identities are still supplied by the caller until persistent trusted
  registry plumbing is implemented.
- Supersedes: none; extends ARM-001.
- Next dependency: actual AI-emitted v2 bytes and production trusted-registry
  adapters for the shared S1 integration gate.


### E-20260926-ARM-004 â€” AI build review and coherent trusted registry snapshot

- Stage: S1
- Lane: Arm/runtime
- Commit: `10c74587e96b22c69527fc0b95df1154b7f2028f`
- Decision review: retain the split architecture. The parser/model/vision lane may
  propose intent and board-frame target coordinates; deterministic arm code owns
  trust resolution, freshness, uncertainty composition, planning, policy and all
  physical authority. The current actual AI emitter remains v1: it still carries
  speed/clearance, copies qualification coverage into confidence, uses nominal
  axis-aligned target rectangles, and emits none of the v2 camera, clock, lease,
  independent placement or uncertainty identities. It therefore must not be
  connected to the v2 planner path until the AI lane performs an explicit emitter
  migration and shared actual-byte integration gate.
- Change: added an immutable consumer-owned `TrustedMotionRegistryV2` snapshot and
  wrapper functions for ingress and pre-planner revalidation. The snapshot requires
  one coherent capability, camera/clock, external lease, evidence set, independent
  placement/frame/map, localization qualification, policy thresholds and exact
  oriented-region coverage. The model cannot populate or expand these records.
- Inputs/fixtures: v2 H/I model batch; coherent registry; incomplete target scope;
  region from a different placement; immutable region-map attempt.
- Command: `python -m pytest software/tests/unit/test_model_motion_ingress_v2.py software/tests/unit/test_model_motion_ingress.py software/ai/tests/test_s1_geometry_cases.py software/ai/tests/test_batch_emitter.py -q`
- Result: PASS, 35 tests.
- Artifacts: `software/src/rocell/application/model_motion_registry_v2.py` and
  `software/tests/unit/test_model_motion_ingress_v2.py`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: the snapshot is an in-process trusted adapter, not persistent signed
  registry storage; no installed localization qualification or actual v2 producer
  output exists. The v1 emitter remains available only for frozen offline research.
- Supersedes: the registry-plumbing limitation in ARM-001 and ARM-003 at the
  in-process boundary; it does not complete the AI emitter or shared integration.
- Next dependency: AI lane implements an explicit v2 emitter using the frozen
  schemas and produces canonical bytes plus one-field mutation fixtures. Then run
  the S1 producer-to-registry-to-arm integration gate without auto-upgrading v1.


### E-20260926-ARM-005 â€” trusted-registry increment audit

- Stage: S1
- Lane: Arm/runtime
- Commit: `10c74587e96b22c69527fc0b95df1154b7f2028f`
- Command: `python scripts/audit_github_snapshot.py`
- Result: FAIL, exit 1; 5,597 paths, 903.2 MiB, the same 14 existing
  credential-literal-review findings in arm unit fixtures; no trusted-registry
  adapter finding.
- Hardware writes: 0
- Physical movements: 0
- Limitations: heuristic audit remains unresolved; no clean security-audit claim.
- Supersedes: none; retains AI-004, AI-006 and ARM-002 failed evidence.
- Next dependency: fixture owners review the existing findings independently of
  v2 producer migration and integration.
### E-20260926-AI-007 â€” v2 typed producer assembly and consumer regression

- Stage: S1
- Lane: AI
- Commit: `413cb8796d7b470752d839b19763f8c903c771c7` (shared consumer/source baseline; new assembly, tests and evidence committed together in this entry's containing commit)
- Change: reviewed ARM-001/003 and adopted published shared types; implemented
  canonical v2 assembly with ordered repeated actions and missing-uncertainty
  abstention. No direct hardware or lower-level command fields added.
- Inputs/fixtures: arm v2 synthetic H/I fixture factories, compiler-shaped H,H,I
  plan; hashes in `software/ai/eval/s1_v2_assembly_evidence.json`.
- Command: `python -m pytest -q software/ai/tests/test_batch_emitter_v2.py software/ai/tests/test_batch_emitter.py software/tests/unit/test_model_motion_ingress.py software/tests/unit/test_model_motion_ingress_v2.py software/tests/unit/test_model_motion_sequence_coordinator.py software/tests/unit/test_model_motion_sequence_journal.py software/tests/unit/test_trajectory_execution_envelope.py`
- Result: PASS, 55 tests; actual assembler bytes decode and enter fixture-based
  consumer admission; repeated H,H,I preserved; confidence 0.93 remains distinct
  from coverage 0.99; missing evidence, wrong profile, uncovered/missing target,
  invalid confidence, same precision/placement hash and expiry reject or abstain.
- Artifacts: `software/ai/rocell_ai/batch_emitter_v2.py`,
  `software/ai/tests/test_batch_emitter_v2.py`, evidence manifest above.
- Hardware writes: 0
- Physical movements: 0
- Limitations: assembly consumes caller-supplied typed evidence. It cannot attest
  that coordinates derive from referenced precision evidence, establish trusted
  placement provenance, or validate qualification registries. Current perception
  has no qualified v2 adapter. No qualification installed; no integration completion.
- Supersedes: none
- Next dependency: AI precision adapter binds observed coordinates/confidence to
  exact evidence; persistent trusted registry adapters and full mutation matrix
  remain needed before cross-lane S1 completion.


### E-20260926-AI-008 â€” v2 assembly audit retains findings

- Stage: S1
- Lane: AI
- Commit: `413cb8796d7b470752d839b19763f8c903c771c7` (baseline plus AI-007 assembly/test working tree)
- Change: required read-only repository audit.
- Inputs/fixtures: repository snapshot, new AI-007 files and `scripts/audit_github_snapshot.py`.
- Command: `python scripts/audit_github_snapshot.py`
- Result: FAIL, exit 1; 5,598 paths, 784.8 MiB, same 14 existing arm-unit-fixture
  credential-literal findings; no new v2 assembly/test finding.
- Artifacts: existing scanner; AI-007 file-hash manifest.
- Hardware writes: 0
- Physical movements: 0
- Limitations: heuristic findings unresolved; no clean security audit claim.
- Supersedes: none; earlier failed audits retained.
- Next dependency: fixture-owner review; AI-007 perception/registry dependencies remain.


### E-20260926-INT-001 â€” actual v2 assembler bytes through trusted arm gates

- Stage: S1
- Lane: Shared integration
- Commits: `20b669c8914ba83cd4bdddc98abae128af1342a2` and
  `f032dc85b3dda58396865e5ca32c54857a4b5570`
- Change: passed canonical bytes from the actual AI v2 assembler through Draft
  2020-12 schema validation, the strict shared decoder, the consumer-owned trusted
  registry, arm ingress, and the monotonic pre-planner recheck. Closed a review
  gap by binding the registry and ingress to exact capture ID, frame ID and image
  hash in addition to camera, clock, derived evidence, lease and geometry records.
- Inputs/fixtures: repeated H,H,I plan; actual canonical assembler bytes; coherent
  synthetic registry fixture; one-field mutations for plan, image, frame, future
  time, capability, camera, clock, lease, placement, target map, qualification,
  domain, uncertainty and safe-region edge; exact expiry.
- Command: `python -m pytest software/tests/integration/test_model_motion_v2_shared_gate.py software/ai/tests/test_batch_emitter_v2.py software/ai/tests/test_batch_emitter.py software/tests/unit/test_model_motion_ingress.py software/tests/unit/test_model_motion_ingress_v2.py software/tests/unit/test_model_motion_sequence_coordinator.py software/tests/unit/test_model_motion_sequence_journal.py software/tests/unit/test_trajectory_execution_envelope.py -q`
- Result: PASS, 73 tests. The shared S1 producer/consumer contract integration
  gate is complete; all tested mutations fail closed before planning.
- Artifacts: `software/tests/integration/test_model_motion_v2_shared_gate.py`,
  `software/ai/rocell_ai/batch_emitter_v2.py`, and the v2 registry/ingress modules.
- Hardware writes: 0
- Physical movements: 0
- Limitations: all evidence and geometry remain synthetic/caller-supplied. This
  proves contract compatibility and rejection behavior, not perception correctness,
  installed qualification, physical planning readiness or execution authority.
- Supersedes: the actual-producer integration dependency in ARM-001/004 and AI-007;
  it does not supersede AI-007's missing precision-evidence adapter dependency.
- Next dependency: AI lane binds precision outputs to exact capture/evidence and
  reaches its own S1 acceptance criteria; S2 then composes the full zero-hardware
  text-to-envelope path using these exact bytes and trusted arm gates.


### E-20260926-INT-002 â€” shared v2 integration audit retains findings

- Stage: S1
- Lane: Shared integration
- Commit: `f032dc85b3dda58396865e5ca32c54857a4b5570`
- Command: `python scripts/audit_github_snapshot.py`
- Result: FAIL, exit 1; 5,601 paths, 903.3 MiB, the same 14 existing
  credential-literal-review findings in arm unit fixtures; no shared-gate finding.
- Hardware writes: 0
- Physical movements: 0
- Limitations: heuristic audit remains unresolved; no clean security-audit claim.
- Supersedes: none; retains all earlier failed audit evidence.
- Next dependency: fixture-owner review remains separate from AI precision binding
  and the S2 zero-hardware composition path.


### E-20260926-ARM-006 â€” v2 proposals enter arm-owned measured planning policy

- Stage: S2
- Lane: Arm/runtime
- Commit: `dfce88e823f9540db03650392dbbb169e366a336`
- Change: added a fail-closed adapter from an admitted v2 proposal and fresh
  pre-planner lease into the existing measured planner. The adapter verifies the
  ingress and pre-planner hashes, exact batch/action lineage, monotonic deadline,
  and zero-authority fields. It derives clearance and speed exclusively from an
  arm-owned policy, preserves the original v2 evidence hashes, and refuses to
  encode or authorize controller commands.
- Inputs/fixtures: coherent H/I v2 batch, consumer-owned trusted registry,
  admitted ingress report, fresh pre-planner report, conservative arm policy,
  tampered ingress, exact expiry, altered action identity, and an upstream report
  that falsely claims hardware access.
- Command: `python -m pytest software/tests/unit/test_model_motion_ingress_v2.py software/tests/unit/test_model_motion_planner_gate.py software/tests/integration/test_model_motion_v2_shared_gate.py -q`
- Result: PASS, 48 tests. The valid input reaches the real measured planner and
  terminates as `BLOCKED_CALIBRATION_MISSING_OR_STALE`; IK and route screening do
  not run, and no envelope or controller command is fabricated. Tamper, expiry,
  wrong-action, and upstream-authority cases fail closed.
- Artifacts: `software/src/rocell/application/model_motion_planner_gate_v2.py`,
  `software/src/rocell/application/__init__.py`, and
  `software/tests/unit/test_model_motion_ingress_v2.py`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: the internal v1 proposal is only a deterministic compatibility
  surrogate for the existing measured planner; it is not a wire migration and
  never replaces the original v2 lineage. No measured deployment calibration or
  localization qualification is installed, so no trajectory envelope is
  produced. The complete raw-text-to-envelope trace runner and v2 sequence
  coordinator remain unfinished.
- Supersedes: none; extends the S1 admission chain into S2 measured planning.
- Next dependency: compose the actual AI v2 bytes, this policy adapter, fresh
  observed-state fixtures, and ordered coordination into one zero-hardware trace;
  separately, the AI lane must bind precision output to exact evidence.


### E-20260926-ARM-007 â€” v2 planner-policy increment audit retains findings

- Stage: S2
- Lane: Arm/runtime
- Commit: `dfce88e823f9540db03650392dbbb169e366a336`
- Command: `python scripts/audit_github_snapshot.py`
- Result: FAIL, exit 1; 5,602 paths, 903.2 MiB, the same 14 existing
  credential-literal-review findings in arm unit fixtures; no v2 planner-policy
  adapter finding.
- Hardware writes: 0
- Physical movements: 0
- Limitations: heuristic findings remain unresolved; this is not a clean
  repository security-audit claim.
- Supersedes: none; retains all earlier failed audit evidence.
- Next dependency: fixture-owner review remains independent of the S2 shadow
  runner and AI precision-evidence binding work.
### E-20260926-AI-009 â€” precision binding test discovery failure

- Stage: S1
- Lane: AI
- Commit: `60447e80c262a24ade6da5423f0fdf022ef1c42d` (source baseline; new binding/test/evidence committed together in this entry's containing commit)
- Change: strict current-precision identity preflight; no runtime batch-contract change.
- Inputs/fixtures: synthetic VisionFusionTests precision fixture and arm v2 fixture;
  exact hashes/environment in `software/ai/eval/s1_precision_binding_evidence.json`.
- Command: `python -m pytest -q software/ai/tests/test_precision_binding_v2.py software/tests/integration/test_model_motion_v2_shared_gate.py software/ai/tests/test_batch_emitter_v2.py`
- Result: FAIL: exit 4, no tests ran; tracked shared-gate test absent from sparse checkout.
- Artifacts: `software/ai/rocell_ai/precision_binding_v2.py`, corresponding test,
  and `software/ai/eval/s1_precision_binding_evidence.json`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: preflight only, no end-to-end perception emission, installed qualification
  or deployment confidence method. Synthetic fixtures do not establish registry trust.
- Supersedes: none
- Next dependency: Restore exact tracked test; rerun.


### E-20260926-AI-010 â€” precision binding dependency failure

- Stage: S1
- Lane: AI
- Commit: `60447e80c262a24ade6da5423f0fdf022ef1c42d` (source baseline; new binding/test/evidence committed together in this entry's containing commit)
- Change: strict current-precision identity preflight; no runtime batch-contract change.
- Inputs/fixtures: synthetic VisionFusionTests precision fixture and arm v2 fixture;
  exact hashes/environment in `software/ai/eval/s1_precision_binding_evidence.json`.
- Command: `python -m pytest -q software/ai/tests/test_precision_binding_v2.py software/tests/integration/test_model_motion_v2_shared_gate.py software/ai/tests/test_batch_emitter_v2.py`
- Result: FAIL: exit 2, collection stopped because jsonschema was not installed after restoring the tracked test.
- Artifacts: `software/ai/rocell_ai/precision_binding_v2.py`, corresponding test,
  and `software/ai/eval/s1_precision_binding_evidence.json`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: preflight only, no end-to-end perception emission, installed qualification
  or deployment confidence method. Synthetic fixtures do not establish registry trust.
- Supersedes: none
- Next dependency: Install test dependency; rerun.


### E-20260926-AI-011 â€” precision binding preflight and shared-gate regression

- Stage: S1
- Lane: AI
- Commit: `60447e80c262a24ade6da5423f0fdf022ef1c42d` (source baseline; new binding/test/evidence committed together in this entry's containing commit)
- Change: strict current-precision identity preflight; no runtime batch-contract change.
- Inputs/fixtures: synthetic VisionFusionTests precision fixture and arm v2 fixture;
  exact hashes/environment in `software/ai/eval/s1_precision_binding_evidence.json`.
- Command: `python -m pytest -q software/ai/tests/test_precision_binding_v2.py software/tests/integration/test_model_motion_v2_shared_gate.py software/ai/tests/test_batch_emitter_v2.py`
- Result: PASS: 31 tests. Exact precision/frame/image/model/map bindings checked; tampered coordinates rejected. Current schema explicitly abstains for missing confidence and capture-clock provenance.
- Artifacts: `software/ai/rocell_ai/precision_binding_v2.py`, corresponding test,
  and `software/ai/eval/s1_precision_binding_evidence.json`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: preflight only, no end-to-end perception emission, installed qualification
  or deployment confidence method. Synthetic fixtures do not establish registry trust.
- Supersedes: AI-009/010 environment blockers resolved; failures retained
- Next dependency: Versioned precision confidence methodology and capture-service provenance adapter; no substitution of scene confidence or coverage.


### E-20260926-AI-012 â€” precision binding repository audit

- Stage: S1
- Lane: AI
- Commit: `60447e80c262a24ade6da5423f0fdf022ef1c42d` (source baseline; new binding/test/evidence committed together in this entry's containing commit)
- Change: strict current-precision identity preflight; no runtime batch-contract change.
- Inputs/fixtures: synthetic VisionFusionTests precision fixture and arm v2 fixture;
  exact hashes/environment in `software/ai/eval/s1_precision_binding_evidence.json`.
- Command: `python scripts/audit_github_snapshot.py`
- Result: FAIL: exit 1; 5,603 paths, 784.8 MiB, same 14 existing arm-unit credential-literal-review findings.
- Artifacts: `software/ai/rocell_ai/precision_binding_v2.py`, corresponding test,
  and `software/ai/eval/s1_precision_binding_evidence.json`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: preflight only, no end-to-end perception emission, installed qualification
  or deployment confidence method. Synthetic fixtures do not establish registry trust.
- Supersedes: none
- Next dependency: Fixture-owner review of existing findings.


### E-20260926-ARM-008 â€” actual v2 bytes produce a zero-hardware shadow trace

- Stage: S2
- Lane: Arm/runtime
- Commit: `f4f045afc2cce46ecfe0d7c4ed585a6268c3175e`
- Change: added one deterministic shadow boundary that strictly decodes actual AI
  v2 bytes, admits them through the consumer-owned registry, rechecks the
  monotonic lease, binds a fresh observed-state fixture and arm-owned motion
  policy, evaluates actions in order, and stops at the first exact planner
  blocker. The trace links request, plan, payload, batch, observation, ingress,
  pre-planner, observed-state, policy and per-action planner hashes.
- Inputs/fixtures: actual H,H,I bytes from `batch_emitter_v2`, coherent synthetic
  trusted registry, fresh zero-authority observed-state fixture, conservative arm
  policy, and one stale observed-state mutation.
- Command: `python -m pytest software/tests/integration/test_model_motion_v2_shared_gate.py software/tests/unit/test_model_motion_ingress_v2.py software/tests/unit/test_model_motion_planner_gate.py software/ai/tests/test_precision_binding_v2.py software/ai/tests/test_batch_emitter_v2.py -q`
- Result: PASS, 65 tests. The trace evaluates action 0 and terminates at
  `BLOCKED_CALIBRATION_MISSING_OR_STALE`; it emits no envelope, controller
  command or Waveshare byte. A stale observed state is rejected before planning.
- Artifacts: `software/src/rocell/application/model_motion_shadow_v2.py`,
  `software/src/rocell/application/__init__.py`, and
  `software/tests/integration/test_model_motion_v2_shared_gate.py`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: this is the first actual-byte S2 trace, not S2 completion. Missing
  measured calibrations prevent reprojection, IK and collision screening, so the
  trace cannot yet seal an execution envelope. It stops on action 0 and does not
  yet adapt the existing sequence coordinator to v2 or demonstrate ambiguous,
  obstructed and unsupported raw-request terminal cases in one command.
- Supersedes: none; extends ARM-006 from one planner call to a hash-linked actual
  producer-byte trace.
- Next dependency: add v2 ordered coordination and an envelope-ready measured or
  explicitly synthetic qualification fixture, then compose raw parser outcomes
  and the full cross-lane negative matrix without weakening the physical gate.


### E-20260926-ARM-009 â€” shadow-trace increment audit retains findings

- Stage: S2
- Lane: Arm/runtime
- Commit: `f4f045afc2cce46ecfe0d7c4ed585a6268c3175e`
- Command: `python scripts/audit_github_snapshot.py`
- Result: FAIL, exit 1; 5,606 paths, 903.2 MiB, the same 14 existing
  credential-literal-review findings in arm unit fixtures; no shadow-runner
  finding.
- Hardware writes: 0
- Physical movements: 0
- Limitations: heuristic findings remain unresolved; this is not a clean
  repository security-audit claim.
- Supersedes: none; retains all earlier failed audit evidence.
- Next dependency: fixture-owner review remains independent of S2 coordination
  and measured calibration work.


### E-20260926-ARM-010 â€” ordered v2 coordinator blocks unsafe envelope migration

- Stage: S2
- Lane: Arm/runtime
- Commit: `9c4acf3ede92e4394e942e138a82c5a95062d2fc`
- Change: added an ordered v2 sequence coordinator and routed the actual-byte
  shadow trace through it. The coordinator verifies ingress, pre-planner and
  planner report hashes; preserves repeated ordered proposals; consumes one
  fresh observed state only for the current action; forbids lookahead, automatic
  retry and authority; and remains on action 0 when the measured planner blocks.
  It also records a newly explicit contract boundary: the existing v1 trajectory
  envelope binds the measured-planner surrogate proposal, not the original v2
  proposal, so automatic envelope migration is forbidden.
- Inputs/fixtures: actual AI H,H,I v2 bytes, coherent trusted registry, fresh
  observed-state fixture, arm-owned conservative policy, missing measured
  calibration blocker, and a repeated evaluation attempt after the blocker.
- Command: `python -m pytest software/tests/integration/test_model_motion_v2_shared_gate.py software/tests/unit/test_model_motion_ingress_v2.py software/tests/unit/test_model_motion_planner_gate.py software/tests/unit/test_model_motion_sequence_coordinator.py software/ai/tests/test_precision_binding_v2.py software/ai/tests/test_batch_emitter_v2.py -q`
- Result: PASS, 71 tests. The coordinator snapshot retains all three ordered
  proposal hashes but plans only action 0, enters `BLOCKED`, rejects a second
  evaluation, generates no envelope or wire bytes, and grants no authority.
- Artifacts:
  `software/src/rocell/application/model_motion_sequence_coordinator_v2.py`,
  `software/src/rocell/application/model_motion_shadow_v2.py`,
  `software/src/rocell/application/__init__.py`, and
  `software/tests/integration/test_model_motion_v2_shared_gate.py`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: no action can advance because measured calibration is absent. A
  future v2 envelope must bind both the original v2 proposal/planner wrapper and
  the internal measured-planner trajectory lineage. This increment intentionally
  does not reinterpret the v1 envelope or fabricate an envelope-ready fixture.
- Supersedes: none; extends ARM-008 with an explicit ordered lifecycle.
- Next dependency: define and test a dual-lineage v2 trajectory-envelope wrapper,
  then produce it only from a fully screened measured planner result.


### E-20260926-ARM-011 â€” v2 coordinator audit retains findings

- Stage: S2
- Lane: Arm/runtime
- Commit: `9c4acf3ede92e4394e942e138a82c5a95062d2fc`
- Command: `python scripts/audit_github_snapshot.py`
- Result: FAIL, exit 1; 5,607 paths, 903.2 MiB, the same 14 existing
  credential-literal-review findings in arm unit fixtures; no v2 coordinator
  finding.
- Hardware writes: 0
- Physical movements: 0
- Limitations: heuristic findings remain unresolved; this is not a clean
  repository security-audit claim.
- Supersedes: none; retains all earlier failed audit evidence.
- Next dependency: fixture-owner review remains independent of the v2 envelope
  contract and measured calibration work.
### E-20260926-AI-013 â€” capture receipt binding and confidence-method plan

- Stage: S1
- Lane: AI
- Commit: `b3d3a7eb5ace6592115e270c035f6aa07816d24d` (source baseline; new implementation/tests/evidence committed together in this entry's containing commit)
- Change: implemented read-only exact capture-receipt binding; documented a
  per-target correctness-probability research method separate from coverage.
- Inputs/fixtures: synthetic frame bytes and externally supplied fixture receipt;
  file hashes in `software/ai/eval/s1_capture_binding_evidence.json`.
- Command: `python -m pytest -q software/ai/tests/test_capture_binding.py software/ai/tests/test_precision_binding_v2.py software/ai/tests/test_batch_emitter_v2.py`
- Result: PASS, 28 tests. Exact capture/frame/image/camera/clock/time bindings,
  absent registry, wrong issuer, changed bytes, tampering and extra-field rejection.
- Artifacts: `software/ai/rocell_ai/capture_binding.py`,
  `software/ai/docs/PRECISION_CONFIDENCE_METHOD.md`, evidence manifest above.
- Hardware writes: 0
- Physical movements: 0
- Limitations: caller-provided trust is not authentication; no real capture-service
  adapter or trained confidence method. Capture binding alone does not enable
  precision emission. No batch schema or arm status changed; no qualification installed.
- Supersedes: none
- Next dependency: authenticated capture-service/clock adapter and predeclared
  confidence event, tolerance, data splits and acceptance criteria before training.


### E-20260926-AI-014 â€” capture-binding audit findings retained

- Stage: S1
- Lane: AI
- Commit: `b3d3a7eb5ace6592115e270c035f6aa07816d24d` (baseline plus AI-013 working-tree files)
- Change: required read-only snapshot audit.
- Inputs/fixtures: repository snapshot, AI-013 file hashes and `scripts/audit_github_snapshot.py`.
- Command: `python scripts/audit_github_snapshot.py`
- Result: FAIL, exit 1; 5,609 paths, 784.9 MiB, same 14 existing arm-unit
  credential-literal-review findings; no capture-binding-file findings.
- Artifacts: scanner and AI-013 evidence manifest.
- Hardware writes: 0
- Physical movements: 0
- Limitations: heuristic findings unresolved; no clean audit claim.
- Supersedes: none; prior failed evidence retained.
- Next dependency: fixture-owner review, separate from AI confidence/capture work.


### E-20260926-ARM-012 â€” dual-lineage v2 trajectory-envelope contract

- Stage: S2
- Lane: Arm/runtime
- Commit: `af57bee3672d65a3063ce69527784a96213a6c43`
- Change: added a zero-authority v2 trajectory-envelope wrapper that preserves
  both the original v2 proposal/planner lineage and the internal measured-planner
  surrogate lineage. Binding requires explicit readiness at both planner layers,
  exact batch/action hashes and an already validated controller-independent v1
  measured trajectory. A blocked planner report cannot be wrapped. The S2 arm
  lane is now `READY_FOR_INTEGRATION` on its exact-blocker path.
- Inputs/fixtures: actual v2 H/I model and planner objects, real missing-calibration
  blocker, an explicitly synthetic dual-ready planner report used only to test
  the contract, a validated controller-independent trajectory envelope, crossed
  surrogate identity and tampered planner report.
- Command: `python -m pytest software/tests/unit/test_trajectory_execution_envelope_v2.py software/tests/unit/test_trajectory_execution_envelope.py software/tests/integration/test_model_motion_v2_shared_gate.py software/tests/unit/test_model_motion_ingress_v2.py software/tests/unit/test_model_motion_planner_gate.py software/tests/unit/test_model_motion_sequence_coordinator.py software/ai/tests/test_capture_binding.py software/ai/tests/test_precision_binding_v2.py software/ai/tests/test_batch_emitter_v2.py -q`
- Result: PASS, 91 tests. Blocked reports fail closed; the synthetic readiness
  fixture seals both lineages; crossed surrogate and tampered report identities
  reject; all envelope documents remain free of wire commands and authority.
- Artifacts:
  `software/src/rocell/application/trajectory_execution_envelope_v2.py`,
  `software/src/rocell/application/__init__.py`, and
  `software/tests/unit/test_trajectory_execution_envelope_v2.py`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: readiness is a contract-only synthetic fixture, not evidence that
  current measured planning passes. The real shadow trace still terminates at
  missing/stale calibration before reprojection or IK. The wrapper is not a
  dispatch permit and cannot be encoded by a writable adapter.
- Supersedes: the dual-lineage envelope dependency recorded by ARM-010; it does
  not supersede the missing-calibration blocker.
- Next dependency: shared integration composes raw parser outcomes, actual
  perception/assembler bytes and the arm shadow runner into one command with the
  supported, ambiguous, stale, obstructed, out-of-bound and unsupported matrix.


### E-20260926-ARM-013 â€” v2 envelope audit retains findings

- Stage: S2
- Lane: Arm/runtime
- Commit: `af57bee3672d65a3063ce69527784a96213a6c43`
- Command: `python scripts/audit_github_snapshot.py`
- Result: FAIL, exit 1; 5,613 paths, 903.3 MiB, the same 14 existing
  credential-literal-review findings in arm unit fixtures; no v2 envelope
  contract finding.
- Hardware writes: 0
- Physical movements: 0
- Limitations: heuristic findings remain unresolved; this is not a clean
  repository security-audit claim.
- Supersedes: none; retains all earlier failed audit evidence.
- Next dependency: fixture-owner review remains independent of the shared S2
  integration runner and measured calibration work.
### E-20260926-AI-015 â€” freeze localization-confidence research protocol

- Stage: S1
- Lane: AI
- Commit: `9c061d45ed2d7a299d7312890ce6155d8def55ee` (source baseline; protocol/helper/tests/evidence added together in this entry's containing commit)
- Change: froze 1 mm localization-only event, fresh 14M/15M/16M/17M seed groups,
  three conditions, threshold 0.95 and synthetic research criteria; implemented
  Brier, reliability-bin and abstention/false-accept scoring.
- Inputs/fixtures: analytic probability/outcome vectors; source hashes in
  `software/ai/eval/confidence_protocol_evidence.json` and training plan.
- Command: `python -m pytest -q software/ai/tests/test_confidence_metrics.py`
- Result: PASS, 10 tests. Empty acceptance reports undefined false-accept rate,
  not zero; invalid numeric inputs reject; frozen split/source checks pass.
- Artifacts: `software/ai/train/localization_confidence_v0_plan.json`,
  `software/ai/rocell_ai/confidence_metrics.py`, corresponding tests/evidence.
- Hardware writes: 0
- Physical movements: 0
- Limitations: no generated dataset, trained confidence head or evaluation results;
  known target identity assumed, visibility not measured. Research thresholds are
  not release criteria and cannot install qualification or runtime confidence.
- Supersedes: none
- Next dependency: freeze model architecture/optimization before confidence training;
  extend separate identity/visibility evidence and authenticated capture integration.


### E-20260926-AI-016 â€” confidence protocol audit findings retained

- Stage: S1
- Lane: AI
- Commit: `9c061d45ed2d7a299d7312890ce6155d8def55ee` (baseline plus AI-015 working-tree files)
- Change: required read-only repository audit.
- Inputs/fixtures: repository snapshot, AI-015 file hashes, `scripts/audit_github_snapshot.py`.
- Command: `python scripts/audit_github_snapshot.py`
- Result: FAIL, exit 1; 5,614 paths, 784.9 MiB, same 14 existing arm-unit
  credential-literal-review findings; no confidence-protocol file finding.
- Artifacts: scanner and AI-015 evidence manifest.
- Hardware writes: 0
- Physical movements: 0
- Limitations: heuristic findings remain unresolved; no clean audit claim.
- Supersedes: none; previous failures retained.
- Next dependency: fixture-owner review, independently of confidence research.


### E-20260926-AI-017 â€” frozen-feature confidence training fails research criteria

- Stage: S1
- Lane: AI
- Commit: `aaaca60a73ff59b312f963389961784a4ba567ae` (exact committed training source and architecture before execution)
- Change: trained a 4,225-parameter 130->32->1 confidence head on frozen pose
  features plus predicted XY. Adam, 12 epochs, development BCE selection and
  separate temperature-grid calibration were frozen before training.
- Inputs/fixtures: robust pose checkpoint SHA-256
  `a9590dce78cb801b9c37eab3522ce9785404ba2776152eefdde04a08983e8b60`;
  `train/localization_confidence_v0_plan.json` and architecture manifest;
  seeds 14M training (1,200), 15M development (200), 16M calibration (300),
  17M evaluation (300), each with 3 conditions and 46 targets. Exact input-source,
  plan/architecture, generated-data and output-model hashes are in the manifests
  and `eval/localization_confidence_v0_scorecard.json`.
- Command: `python software/ai/train/train_localization_confidence.py`
- Result: FAIL, `SYNTHETIC_RESEARCH_FAILED`; training completed successfully.
  Selected epoch 8, temperature 1.0. Evaluation 41,400 target/view samples:
  Brier 0.2353066 (required <=0.10), acceptance 0/41,400 (required >=10%).
  False-accept rate among accepted is undefined, not zero. All three conditions
  fail; Brier standard 0.2365861, appearance_shift 0.2238393, challenge 0.2454943.
- Artifacts: architecture/training source and scorecard above; model retained
  locally under ignored `software/ai/results/localization_confidence_v0/model.pt`,
  SHA-256 `3a2f1b969b834b82c5858a2ac1c53c39a18b135a368317ada95c4a471b80d8b4`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: synthetic localization-only event; correlated target/views, known
  identity, no visibility qualification or authenticated capture. No runtime
  confidence or localization qualification installed. Reproduction requires the
  pinned local pose checkpoint and a new/absent output directory.
- Supersedes: none; frozen protocol and failed result preserved.
- Next dependency: investigate confidence-head inputs on development data; consider
  local image features in a separately frozen experiment with fresh calibration
  and evaluation seeds. Do not lower this run's threshold or tune on 17M outcomes.

### E-20260926-AI-018 â€” confidence metric regression

- Stage: S1
- Lane: AI
- Commit: `aaaca60a73ff59b312f963389961784a4ba567ae`
- Change: reran scoring regression during the frozen confidence experiment.
- Inputs/fixtures: analytic vectors in `software/ai/tests/test_confidence_metrics.py`;
  source hashes pinned by the confidence protocol.
- Command: `python -m pytest -q software/ai/tests/test_confidence_metrics.py`
- Result: PASS, 10 tests; this validates metrics, not the model's failed criteria.
- Artifacts: metric helper and tests.
- Hardware writes: 0
- Physical movements: 0
- Limitations: unit tests only; not a batch contract change or physical evidence.
- Supersedes: none
- Next dependency: AI-017 development investigation.

### E-20260926-AI-019 â€” confidence training audit findings retained

- Stage: S1
- Lane: AI
- Commit: `aaaca60a73ff59b312f963389961784a4ba567ae`
- Change: required read-only snapshot audit during training.
- Inputs/fixtures: repository snapshot and `scripts/audit_github_snapshot.py`.
- Command: `python scripts/audit_github_snapshot.py`
- Result: FAIL, exit 1; 5,617 paths, 784.9 MiB, same 14 existing arm-unit
  credential-literal-review findings; no new training-source finding.
- Artifacts: scanner and existing test fixtures.
- Hardware writes: 0
- Physical movements: 0
- Limitations: heuristic findings remain unresolved; no clean audit claim.
- Supersedes: none
- Next dependency: fixture-owner review independently of confidence research.

### E-20260926-INT-003 â€” raw request reaches the actual v2 arm shadow path

- Stage: S2
- Lane: INTEGRATION
- Commit: `ffa5cf82fdf6be33e35e349ac1e171486ce186f5`
- Change: added a zero-authority shared runner from raw text through the grounded
  parser, deterministic compiler, actual v2 batch assembler, decoder, trusted
  ingress, sequence coordination, and arm shadow planner. The integration found
  and fixed a real producer/consumer discrepancy: the compiler's profile ID
  `development/keyboard-us-lowercase-semantic-v1` contains `/`, while the v2
  schema and arm runtime previously accepted only generic identifiers. Profile
  IDs now use a dedicated bounded rule; generic identifiers remain unchanged.
- Inputs/fixtures: explicit `SYNTHETIC_INTEGRATION_ONLY` typed observation,
  evidence, registry, and fresh observed-state fixtures from the existing v2
  shared gate; raw requests and terminal cases in
  `software/tests/integration/test_shared_shadow_runner_v2.py`.
- Command: `python -m pytest software/tests/integration/test_shared_shadow_runner_v2.py software/tests/integration/test_model_motion_v2_shared_gate.py software/ai/tests/test_batch_emitter_v2.py software/ai/tests/test_precision_binding_v2.py software/ai/tests/test_capture_binding.py software/tests/unit/test_model_motion_ingress_v2.py software/tests/unit/test_model_motion_planner_gate.py software/tests/unit/test_model_motion_sequence_coordinator.py software/tests/unit/test_trajectory_execution_envelope_v2.py -q`
- Result: PASS, 95 tests. Supported `type hhi on keyboard` preserves three
  ordered actions and reaches the exact current arm blocker
  `BLOCKED_CALIBRATION_MISSING_OR_STALE`. Ambiguous, unsupported, stale,
  obstructed, missing-perception, out-of-bounds, and expired-evidence cases stop
  at their expected terminal states. The exact compiler profile validates under
  both the published JSON schema and runtime decoder.
- Artifacts: `software/ai/rocell_ai/shared_shadow_runner_v2.py`,
  `software/tests/integration/test_shared_shadow_runner_v2.py`,
  `software/ai/schemas/model_motion_batch_v2.schema.json`,
  `software/src/rocell/models/model_motion_batch_v2.py`, and
  `software/src/rocell/application/model_motion_ingress_v2.py`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: this is partial S2 integration, not S2 completion. The accepted
  supported path uses an explicitly labeled synthetic integration fixture. The
  selected precision/confidence workstream has not emitted qualified deployment
  evidence, and AI-017 correctly records complete abstention under its failed
  research criteria. No envelope is produced because measured calibration is
  still missing or stale.
- Supersedes: none; extends INT-001 and INT-002 without changing their evidence.
- Next dependency: connect authenticated capture plus a qualified, independently
  bounded precision observation to this runner; then repeat the terminal matrix
  with actual producer evidence and measured calibration.

### E-20260926-INT-004 â€” S2 raw-runner audit findings retained

- Stage: S2
- Lane: INTEGRATION
- Commit: `ffa5cf82fdf6be33e35e349ac1e171486ce186f5`
- Change: ran the required read-only repository snapshot audit after the shared
  runner and profile-contract correction.
- Inputs/fixtures: repository snapshot and `scripts/audit_github_snapshot.py`.
- Command: `python scripts/audit_github_snapshot.py`
- Result: FAIL, exit 1; 5,622 paths, 903.3 MiB, the same 14 existing
  credential-literal-review findings in arm unit fixtures; no shared-runner,
  profile-schema, or profile-runtime finding.
- Artifacts: scanner and the existing named unit fixtures in its output.
- Hardware writes: 0
- Physical movements: 0
- Limitations: heuristic findings remain unresolved; this is not a clean
  repository security-audit claim.
- Supersedes: none; retains every earlier failed audit row.
- Next dependency: fixture-owner review remains independent of qualified
  perception integration and measured-calibration work.

### E-20260926-AI-020 â€” local image feature development comparison

- Stage: S1
- Lane: AI
- Commit: `070565245915893a993141cb248d626c440a9041` (exact frozen code/plan before execution)
- Change: added an 8x8 grayscale patch from a 16x16 pixel crop centered on the
  predicted target, combined with frozen pose features and predicted XY; trained
  6,273 parameters. Hidden truth supplies labels only, never patch placement.
- Inputs/fixtures: original 14M training and 15M development seeds, 3 conditions,
  46 keys. 165,600 training and 27,600 development target/view samples. Pose/head
  hashes pinned in `train/local_features_dev_v0_plan.json` and original plan;
  generated-data, plan and output-model hashes in the scorecard.
- Command: `python software/ai/train/compare_local_confidence_features.py`
- Result: PASS for completed development experiment, not readiness. Epoch 2
  selected by development BCE. Candidate Brier 0.2219927 vs baseline 0.2239326
  (improvement 0.0019399). Both accept 0/27,600 at 0.95; false-accept rate among
  accepted remains undefined. No new calibration or evaluation data consumed.
- Artifacts: `software/ai/eval/local_features_dev_v0_scorecard.json`, frozen plan
  and training script; local ignored model at
  `software/ai/results/local_features_dev_v0/model.pt`, SHA-256
  `5eaaa537c2c54367937a58b5fbf3545b6152436a626c91174f22423d6b7185a9`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: development data select epoch and feature choice; optimistic
  selection evidence only. No calibrated confidence, identity/visibility evidence,
  installed qualification or runtime promotion. Previous failed evaluation retained.
- Supersedes: none
- Next dependency: investigate localization/feature resolution on development
  data before another frozen held-out experiment; this small gain does not justify
  promotion or changing the original acceptance threshold.

### E-20260926-AI-021 â€” development scoring regression

- Stage: S1
- Lane: AI
- Commit: `070565245915893a993141cb248d626c440a9041`
- Change: reran descriptive scoring tests.
- Inputs/fixtures: analytic vectors in `software/ai/tests/test_confidence_metrics.py`.
- Command: `python -m pytest -q software/ai/tests/test_confidence_metrics.py`
- Result: PASS, 10 tests.
- Artifacts: scoring helper and tests; frozen source hashes in original protocol.
- Hardware writes: 0
- Physical movements: 0
- Limitations: metric correctness only, not model quality or physical evidence.
- Supersedes: none
- Next dependency: AI-020 development investigation.

### E-20260926-AI-022 â€” local-feature audit findings retained

- Stage: S1
- Lane: AI
- Commit: `070565245915893a993141cb248d626c440a9041`
- Change: required read-only repository audit during experiment.
- Inputs/fixtures: repository snapshot and `scripts/audit_github_snapshot.py`.
- Command: `python scripts/audit_github_snapshot.py`
- Result: FAIL, exit 1; 5,622 paths, 784.9 MiB, same 14 existing arm-unit
  credential-literal-review findings; no new local-feature source finding.
- Artifacts: scanner and existing fixtures.
- Hardware writes: 0
- Physical movements: 0
- Limitations: heuristic findings unresolved; no clean audit claim.
- Supersedes: none
- Next dependency: fixture-owner review independently of confidence research.


### E-20260926-AI-023 â€” development inference resolution sensitivity

- Stage: S1
- Lane: AI
- Commit: `effa56e1e696494e1b038d8eda82e0f43de53674` (exact frozen diagnostic source and manifest)
- Change: compared the unchanged pose checkpoint at trained 128x96 and untrained
  256x192 input sizes using only the 200 existing 15M development seed groups.
- Inputs/fixtures: 600 procedural images, 46 keys, three conditions; source/model
  hashes in `eval/resolution_development_v0.manifest.json`; image/catalog hashes
  and per-condition/group metrics in the scorecard.
- Command: `python software/ai/vision/diagnose_resolution.py`
- Result: PASS for completed diagnostic. At 128x96: mean 1.03166 mm, p95 2.30191 mm,
  58.42% within 1 mm. At untrained 256x192: mean 13.50350 mm, p95 25.63512 mm,
  0.315% within 1 mm. Each reports 27,600 correlated target/view errors.
- Artifacts: `software/ai/eval/resolution_development_v0_scorecard.json`, manifest
  and `software/ai/vision/diagnose_resolution.py`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: changing inference size alone introduces distribution shift; this
  does not compare matched-resolution training or prove a resolution accuracy
  floor. At 128x96, 1 mm spans approximately 0.21 pixel; subpixel regression is
  possible. The synthetic source is only 256x192. No confidence promotion,
  calibration/evaluation access, retraining or installed qualification.
- Supersedes: none
- Next dependency: freeze a matched train/evaluate resolution experiment using
  development data first; do not switch production input size from this diagnostic.


### E-20260926-AI-024 â€” resolution diagnostic audit findings retained

- Stage: S1
- Lane: AI
- Commit: `effa56e1e696494e1b038d8eda82e0f43de53674`
- Change: required read-only snapshot audit after diagnostic.
- Inputs/fixtures: repository snapshot, new diagnostic scorecard and `scripts/audit_github_snapshot.py`.
- Command: `python scripts/audit_github_snapshot.py`
- Result: FAIL, exit 1; 5,636 paths, 784.9 MiB, same 14 existing arm-unit
  credential-literal-review findings; no diagnostic file finding.
- Artifacts: scanner and existing fixtures.
- Hardware writes: 0
- Physical movements: 0
- Limitations: heuristic findings unresolved; no clean audit claim.
- Supersedes: none
- Next dependency: fixture-owner review, separately from localization research.


### E-20260926-AI-025 â€” matched-resolution development fine-tuning

- Stage: S1
- Lane: AI
- Commit: `cc9d000b927122bb200b6142315c96fb879ec2f8` (exact frozen training code and plan before execution)
- Change: paired 128x96/256x192 fine-tuning from identical robust pose weights,
  same seeded image order, 12 epochs, batch 64, AdamW learning rate 0.0002.
- Inputs/fixtures: 14M training (1,200 groups) and 15M development (200 groups),
  3 conditions; 3,600/600 images. Checkpoint/source/catalog hashes pinned in
  `train/matched_resolution_v0_plan.json`; pixel/output-model hashes in scorecard.
- Command: `python software/ai/vision/train_matched_resolution.py`
- Result: PASS for completed development comparison, not qualification. Both
  selected epoch 11 by development MSE. 128x96: mean 0.94513 mm, p95 2.06487 mm,
  63.12% within 1 mm. 256x192: mean 1.44220 mm, p95 3.52965 mm, 39.69% within
  1 mm. Each has 27,600 correlated target/view errors; retain 128x96 research
  resolution, with no runtime checkpoint replacement from development results.
- Artifacts: `software/ai/eval/matched_resolution_v0_scorecard.json`; local ignored
  checkpoints under `software/ai/results/matched_resolution_v0_128/` and `_256/`.
  SHA-256 values respectively
  `1dc517acd1da53166dc2df11a4d67e98aaf1186d96edd3342db0498fb6a6f2cc` and
  `15f495bb18437208ae8bbea273aa957f5468b40bba4374546a81716ed545aa37`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: same pretrained weights originated at 128x96, so this is an
  equal-budget adaptation comparison, not from-scratch proof that higher resolution
  cannot help. One training seed; development selects epoch and reports quality;
  no independent generalization or physical claim, new evaluation data or qualification.
- Supersedes: none; extends inference-only AI-023 without rewriting it.
- Next dependency: use 128x96 as the development reference; investigate target-local
  geometric refinement and confidence on development groups before a new frozen
  held-out run. Keep failed confidence results and runtime abstention unchanged.

### E-20260926-AI-026 â€” matched-resolution evidence checks

- Stage: S1
- Lane: AI
- Commit: `cc9d000b927122bb200b6142315c96fb879ec2f8` (training baseline; new evidence test and scorecard committed with this row)
- Change: verified frozen source hashes, equal budgets/counts, development-only
  splits and minimum-development-MSE checkpoint selection.
- Inputs/fixtures: paired plan/scorecard and `software/ai/tests/test_matched_resolution_evidence.py`.
- Command: `python -m pytest -q software/ai/tests/test_matched_resolution_evidence.py`
- Result: PASS, 1 evidence test covering both runs.
- Artifacts: test, frozen plan and scorecard.
- Hardware writes: 0
- Physical movements: 0
- Limitations: internal evidence consistency, not physical model qualification.
- Supersedes: none
- Next dependency: AI-025 development investigation.

### E-20260926-AI-027 â€” matched-resolution audit findings retained

- Stage: S1
- Lane: AI
- Commit: `cc9d000b927122bb200b6142315c96fb879ec2f8`
- Change: required read-only audit during training.
- Inputs/fixtures: repository snapshot and `scripts/audit_github_snapshot.py`.
- Command: `python scripts/audit_github_snapshot.py`
- Result: FAIL, exit 1; 5,638 paths, 785.0 MiB, same 14 existing arm-unit
  credential-literal-review findings; no matched-resolution source finding.
- Artifacts: scanner and existing fixtures.
- Hardware writes: 0
- Physical movements: 0
- Limitations: heuristic findings unresolved; no clean audit claim.
- Supersedes: none
- Next dependency: fixture-owner review independently of localization research.


### E-20260926-AI-028 â€” merged boundary regression

- Stage: S1
- Lane: AI
- Commit: `4687072c25f774a5651b39ba1ba79a07949a494f`
- Change: retained concurrent shared shadow/boundary changes and reran focused producer/consumer checks.
- Inputs/fixtures: v2 AI assembler and arm ingress fixtures, matched-resolution scorecard.
- Command: `python -m pytest -q software/ai/tests/test_batch_emitter_v2.py software/tests/unit/test_model_motion_ingress_v2.py software/ai/tests/test_matched_resolution_evidence.py`
- Result: PASS, 33 tests.
- Artifacts: named tests and merged shared boundary sources.
- Hardware writes: 0
- Physical movements: 0
- Limitations: focused offline regression only; no integration status changed by AI lane.
- Supersedes: none
- Next dependency: AI-025 development refinement and shared-stage outstanding dependencies.


### E-20260926-AI-029 â€” reject local-edge refinement after development comparison

- Stage: S1
- Lane: AI
- Commit: `524803de116214cbec6366568cdc49f6d1a577a4` (exact frozen helper/diagnostic/manifest before scoring)
- Change: tested fixed 9x9 gradient-energy centroid with Gaussian sigma 2 pixels,
  capped at 1 mm correction. Uses predicted location and image pixels only.
- Inputs/fixtures: 200 existing 15M development groups, 3 conditions, 46 targets;
  128x96 matched-resolution checkpoint hash
  `1dc517acd1da53166dc2df11a4d67e98aaf1186d96edd3342db0498fb6a6f2cc`.
  Source/model hashes in `eval/local_refinement_v0.manifest.json`; image/catalog
  hashes and per-condition metrics in scorecard.
- Command: `python software/ai/vision/diagnose_local_refinement.py`
- Result: FAIL for improvement hypothesis; diagnostic completed. Baseline mean
  0.945249 mm / p95 2.065851 mm / within-1mm 63.083%; refined mean 1.236834 mm /
  p95 2.665683 mm / within-1mm 45.949%. Reject this heuristic; no runtime change.
- Artifacts: `software/ai/eval/local_refinement_v0_scorecard.json`, frozen manifest,
  `vision/local_refinement.py` and `vision/diagnose_local_refinement.py`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: synthetic projection and known identities; correlated samples;
  development diagnostic only. Tiny baseline differences from AI-025 may reflect this
  run's CPU inference/direct renderer truth versus GPU/float32 decoded training
  labels. The paired comparison here uses identical inference/truth for both arms.
  No calibration/evaluation access, qualified confidence, or installed qualification.
- Supersedes: none; previous evidence retained.
- Next dependency: retain unrefined 128x96 development reference; decompose remaining
  pose error into translation/orientation and scene-condition contributions before
  choosing further model changes. Do not tune this rejected heuristic on held-out data.

### E-20260926-AI-030 â€” refinement bound and edge-case tests

- Stage: S1
- Lane: AI
- Commit: `524803de116214cbec6366568cdc49f6d1a577a4`
- Change: tested flat-image fallback, border fallback, finite-input rejection and
  maximum correction distance.
- Inputs/fixtures: analytic PIL images in `software/ai/tests/test_local_refinement.py`.
- Command: `python -m pytest -q software/ai/tests/test_local_refinement.py`
- Result: PASS, 4 tests; functional bounds do not overturn AI-029's accuracy failure.
- Artifacts: helper and tests.
- Hardware writes: 0
- Physical movements: 0
- Limitations: unit correctness only, not model-quality or physical evidence.
- Supersedes: none
- Next dependency: AI-029 error decomposition.


### E-20260926-AI-031 â€” local-refinement audit findings retained

- Stage: S1
- Lane: AI
- Commit: `524803de116214cbec6366568cdc49f6d1a577a4`
- Change: required read-only snapshot audit after diagnostic.
- Inputs/fixtures: repository snapshot, scorecard, `scripts/audit_github_snapshot.py`.
- Command: `python scripts/audit_github_snapshot.py`
- Result: FAIL, exit 1; 5,647 paths, 785.0 MiB, same 14 existing arm-unit
  credential-literal-review findings; no local-refinement file finding.
- Artifacts: scanner and existing fixtures.
- Hardware writes: 0
- Physical movements: 0
- Limitations: heuristic findings unresolved; no clean audit claim.
- Supersedes: none
- Next dependency: fixture-owner review independently of localization research.

### E-20260926-ARM-014 â€” sealed-envelope T102 zero-write preview

- Stage: S4
- Lane: ARM
- Commit: `575669b206fc671bb51277971843a9cf690082e4`
- Change: implemented a transport-free Waveshare T=102 preview adapter that
  accepts only a sealed dual-lineage v2 trajectory envelope, an exact encoding
  profile, and a separately issued single-use evidence-only permit. The observed
  starting waypoint is retained as state and never encoded as a movement. Every
  later waypoint maps the five planner joints to base/shoulder/elbow/wrist/roll,
  holds the gripper at one explicit fixed angle, and retains its host dispatch
  time separately from the firmware's opaque `spd` and `acc` fields.
- Inputs/fixtures: synthetic ready v2 envelope fixture from
  `software/tests/unit/test_trajectory_execution_envelope_v2.py`; encoding
  profile bound to exact vendor-source, joint-map, controller-session,
  configuration-epoch, and trajectory-limit hashes.
- Command: `python -m pytest software/ai/tests software/tests/unit/test_zero_write_waveshare_adapter_v1.py software/tests/unit/test_trajectory_execution_envelope_v2.py software/tests/unit/test_all_joint_command.py software/tests/unit/test_arm_protocol.py software/tests/integration/test_shared_shadow_runner_v2.py software/tests/integration/test_model_motion_v2_shared_gate.py software/tests/unit/test_model_motion_ingress_v2.py software/tests/unit/test_model_motion_planner_gate.py software/tests/unit/test_model_motion_sequence_coordinator.py -q`
- Result: PASS, 261 tests after merging the concurrent AI work. Golden bytes are
  deterministic. Reused permits, duplicate correlations, stale permits, altered
  envelopes, mismatched controller sessions/configuration epochs/limit profiles,
  unsupported interpolation or gripper behavior, invalid firmware settings, and
  schedules exceeding the envelope deadline fail closed without retry.
- Artifacts: `software/src/rocell/application/zero_write_waveshare_adapter_v1.py`,
  its application exports, and
  `software/tests/unit/test_zero_write_waveshare_adapter_v1.py`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: this is an encoding preview and receipt, not a sole writable
  transport owner or physical execution permit. It opens no transport, submits
  no bytes, receives no acknowledgement or feedback, and does not prove that
  the configured vendor artifact, mapping, rate settings, or joint limits match
  the installed controller. The ready trajectory used by the test is synthetic.
- Supersedes: none; starts the arm-owned S4 implementation.
- Next dependency: place this exact encoder behind one separately reviewed sole
  writer, define partial-write/timeout/restart closure, and qualify the installed
  firmware mapping before any physical authority is possible.

### E-20260926-ARM-015 â€” S4 preview audit findings retained

- Stage: S4
- Lane: ARM
- Commit: `575669b206fc671bb51277971843a9cf690082e4`
- Change: ran the required read-only repository snapshot audit after merging the
  current AI evidence and CI changes with the S4 preview implementation.
- Inputs/fixtures: repository snapshot and `scripts/audit_github_snapshot.py`.
- Command: `python scripts/audit_github_snapshot.py`
- Result: FAIL, exit 1; 5,653 paths, 903.4 MiB, the same 14 existing
  credential-literal-review findings in arm unit fixtures; no zero-write adapter,
  permit, receipt, or test finding.
- Artifacts: scanner and the existing named fixtures in its output.
- Hardware writes: 0
- Physical movements: 0
- Limitations: heuristic findings remain unresolved; this is not a clean
  repository security-audit claim.
- Supersedes: none; preserves every previous audit failure.
- Next dependency: fixture-owner review remains independent of S4 writer and
  installed-controller qualification.

### E-20260926-ARM-016 â€” zero-write sole-writer lifecycle and restart closure

- Stage: S4
- Lane: ARM
- Commit: `8ddd984d4dd8df1f18e58c2f743854642b84abe7`
- Change: wrapped the hash-bound T=102 preview receipt in a transport-free
  single-owner lifecycle. One correlation can be reserved once. Events are
  ordinal, hash-chained, bound to the exact preview receipt and writer instance,
  and exported as strict canonical journal bytes. Normal rehearsal closes
  terminally; injected partial write, acknowledgement timeout, feedback timeout,
  and uncertain close all close as `AMBIGUOUS_NO_RETRY`. A process restart after
  reservation reconstructs only as `RECONCILIATION_REQUIRED_NO_RETRY` and cannot
  automatically replay.
- Inputs/fixtures: ARM-014 zero-write preview receipt and its sealed synthetic v2
  trajectory fixture; analytic counterfactual fault labels only.
- Command: `python -m pytest software/ai/tests software/tests/unit/test_zero_write_sole_writer_v1.py software/tests/unit/test_zero_write_waveshare_adapter_v1.py software/tests/unit/test_trajectory_execution_envelope_v2.py software/tests/unit/test_all_joint_command.py software/tests/unit/test_arm_protocol.py software/tests/integration/test_shared_shadow_runner_v2.py software/tests/integration/test_model_motion_v2_shared_gate.py software/tests/unit/test_model_motion_ingress_v2.py software/tests/unit/test_model_motion_planner_gate.py software/tests/unit/test_model_motion_sequence_coordinator.py -q`
- Result: PASS, 272 tests. Concurrent claim attempts permit exactly one owner;
  consumed/closed/recovered journals refuse replay. Altered event content,
  duplicate JSON fields, wrong receipt identity, and unknown fault modes reject.
  Every success and failure report records zero transport opens, zero physical
  writes, no submitted bytes, and no automatic retry.
- Artifacts: `software/src/rocell/application/zero_write_sole_writer_v1.py`,
  its application exports, and
  `software/tests/unit/test_zero_write_sole_writer_v1.py`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: fault labels are counterfactual lifecycle injections; no serial or
  HTTP transport is imported, opened, or exercised. Restart safety depends on
  retaining and reconstructing the exact journal bytes; a production durable
  reservation store is not implemented. No installed controller mapping,
  firmware-version match, acknowledgement grammar, or feedback qualification is
  claimed.
- Supersedes: none; extends ARM-014 without granting physical authority.
- Next dependency: publish strict permit/receipt schemas and a committed golden
  byte fixture, then bind them to independently commissioned controller mapping
  and firmware evidence before considering the S4 arm lane ready.

### E-20260926-ARM-017 â€” sole-writer lifecycle audit findings retained

- Stage: S4
- Lane: ARM
- Commit: `8ddd984d4dd8df1f18e58c2f743854642b84abe7`
- Change: ran the required read-only repository snapshot audit after the
  zero-write writer lifecycle and fault matrix.
- Inputs/fixtures: repository snapshot and `scripts/audit_github_snapshot.py`.
- Command: `python scripts/audit_github_snapshot.py`
- Result: FAIL, exit 1; 5,655 paths, 903.5 MiB, the same 14 existing
  credential-literal-review findings in arm unit fixtures; no sole-writer,
  journal, report, or lifecycle-test finding.
- Artifacts: scanner and the existing named fixtures in its output.
- Hardware writes: 0
- Physical movements: 0
- Limitations: heuristic findings remain unresolved; this is not a clean
  repository security-audit claim.
- Supersedes: none; retains all earlier audit failures.
- Next dependency: fixture-owner review remains independent of S4 schema,
  golden-fixture, and controller-mapping work.

### E-20260926-AI-032 â€” translation and rotation development decomposition

- Stage: S1
- Lane: AI
- Commit: `c20b7c9d6319a267f66dd348f49b87ef734e3ac9` (exact frozen diagnostic and manifest before scoring)
- Change: scored unchanged model predictions plus translation-only and rotation-only
  counterfactuals; hidden renderer truth used only in diagnostic scoring.
- Inputs/fixtures: 200 existing 15M development groups, three conditions, 46 targets;
  checkpoint/source hashes in `eval/pose_decomposition_v0.manifest.json`; image and
  catalog hashes in scorecard. Same matched 128x96 checkpoint as AI-029.
- Command: `python software/ai/vision/diagnose_pose_decomposition.py`
- Result: PASS for completed attribution. Mean key error baseline 0.945249 mm,
  translation-only 0.885410 mm, rotation-only 0.278395 mm. Within-1mm rates 63.083%,
  66.167%, 96.217%, respectively; each 27,600 correlated target/view samples.
  Baseline mean standard 0.868360, appearance_shift 0.900634, challenge 1.066751 mm.
- Artifacts: `software/ai/eval/pose_decomposition_v0_scorecard.json`, manifest,
  `software/ai/vision/diagnose_pose_decomposition.py`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: counterfactual diagnostics are not deployable corrections; scalar
  error magnitudes are not additive. Condition bundles do not identify individual
  lighting/blur/obstruction causes. No independent evaluation, calibration,
  confidence promotion, or qualification installation.
- Supersedes: none
- Next dependency: freeze translation-focused pose training on development data,
  retaining yaw regression monitoring; require paired baseline comparison before
  consuming new calibration/evaluation groups.

### E-20260926-AI-033 â€” decomposition consistency checks

- Stage: S1
- Lane: AI
- Commit: `c20b7c9d6319a267f66dd348f49b87ef734e3ac9` (diagnostic baseline; new tests/evidence committed with this row)
- Change: checked exact previous baseline/image identity, source pins and equality
  of translation-only key mean error with center translation mean error.
- Inputs/fixtures: AI-029 and AI-032 scorecards and frozen manifest.
- Command: `python -m pytest -q software/ai/tests/test_pose_decomposition.py`
- Result: PASS, 2 tests.
- Artifacts: named test and scorecards.
- Hardware writes: 0
- Physical movements: 0
- Limitations: diagnostic consistency only, not physical or model qualification.
- Supersedes: none
- Next dependency: AI-032 translation-focused development experiment.

### E-20260926-AI-034 â€” decomposition audit findings retained

- Stage: S1
- Lane: AI
- Commit: `c20b7c9d6319a267f66dd348f49b87ef734e3ac9`
- Change: required read-only repository audit after diagnostic.
- Inputs/fixtures: repository snapshot, new scorecard and `scripts/audit_github_snapshot.py`.
- Command: `python scripts/audit_github_snapshot.py`
- Result: FAIL, exit 1; 5,656 paths, 785.0 MiB, same 14 existing arm-unit
  credential-literal-review findings; no decomposition-file finding.
- Artifacts: scanner and existing fixtures.
- Hardware writes: 0
- Physical movements: 0
- Limitations: heuristic findings unresolved; no clean audit claim.
- Supersedes: none
- Next dependency: fixture-owner review independently of AI development.


### E-20260926-AI-035 â€” translation-weighted development candidate

- Stage: S1
- Lane: AI
- Commit: `fe20dc15376361f38049e4791583af72b62e5a77` (exact frozen paired training code and plan)
- Change: compared normalized pose residual weights 1:1:1 versus 4:4:1 for XY/yaw,
  same starting checkpoint, seed/order, 128x96 input and 12-epoch AdamW budget.
  Both select minimum unweighted development MSE; training_mse in the history
  denotes each arm's normalized weighted training loss.
- Inputs/fixtures: 14M training/15M development groups, 3 conditions, 46 targets;
  3,600/600 images. Source/catalog/start checkpoint hashes in
  `train/translation_weighted_v0_plan.json`; pixel/model hashes in scorecard.
- Command: `python software/ai/vision/train_translation_weighted.py`
- Result: PASS for predeclared development candidate rule, not qualification.
  Control epoch 5 vs weighted epoch 12: mean key error 0.936551 -> 0.906526 mm;
  mean center error 0.878934 -> 0.856590 mm; yaw p95 0.616581 -> 0.571123 degrees;
  within-1mm 64.8007% -> 69.0217%. Key p95 2.133593 -> 2.051064 mm.
- Artifacts: `software/ai/eval/translation_weighted_v0_scorecard.json`, paired plan,
  `vision/train_translation_weighted.py`; ignored local models under
  `software/ai/results/translation_weighted_v0_control/` and `_translation_weighted/`.
  Model SHA-256 respectively
  `be261aa283dc63622d945b5ae313880c4b4fcad53381f8cdb45b3322e85e0490` and
  `0fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: repeated development selection, one training seed, synthetic known
  target geometry. No new held-out/calibration access, runtime model replacement,
  confidence validation or installed qualification.
- Supersedes: none; prior failed confidence/refinement studies retained.
- Next dependency: freeze fresh independent seed groups and paired evaluation
  criteria for this candidate and control before inspecting labels; then assess
  uncertainty separately. Development success alone cannot enable emission.

### E-20260926-AI-036 â€” paired training evidence validation

- Stage: S1
- Lane: AI
- Commit: `fe20dc15376361f38049e4791583af72b62e5a77` (training baseline; new test committed with evidence)
- Change: checked frozen sources, identical data hashes/budgets, selected epochs
  and exact predeclared candidate rule.
- Inputs/fixtures: paired plan/scorecard and `tests/test_translation_weighted_evidence.py`.
- Command: `python -m pytest -q software/ai/tests/test_translation_weighted_evidence.py`
- Result: PASS, 2 tests.
- Artifacts: named evidence test and scorecard.
- Hardware writes: 0
- Physical movements: 0
- Limitations: internal consistency, not independent generalization or qualification.
- Supersedes: none
- Next dependency: AI-035 frozen independent comparison.

### E-20260926-AI-037 â€” translation-training audit findings retained

- Stage: S1
- Lane: AI
- Commit: `fe20dc15376361f38049e4791583af72b62e5a77`
- Change: required read-only audit during training.
- Inputs/fixtures: repository snapshot and `scripts/audit_github_snapshot.py`.
- Command: `python scripts/audit_github_snapshot.py`
- Result: FAIL, exit 1; 5,659 paths, 785.0 MiB, same 14 existing arm-unit
  credential-literal-review findings; no new training-source finding.
- Artifacts: scanner and existing fixtures.
- Hardware writes: 0
- Physical movements: 0
- Limitations: heuristic findings unresolved; no clean audit claim.
- Supersedes: none
- Next dependency: fixture-owner review independently of AI research.


### E-20260926-AI-038 â€” fresh paired translation candidate evaluation

- Stage: S1
- Lane: AI
- Commit: `bc86500906578ba341862f1fd5cf758bf1db698b` (exact frozen evaluation source, checkpoints and criteria before scoring)
- Change: compared frozen translation-weighted candidate and control on fresh
  18M seeds with no training, threshold tuning or calibration.
- Inputs/fixtures: seeds 18000000â€“18000499, three conditions, 46 keys; 1,500 images
  and 69,000 correlated target/view errors per model. Checkpoint/source/catalog
  hashes in `eval/translation_pair_v0.manifest.json`; image hash and group scores
  in `eval/translation_pair_v0_scorecard.json`.
- Command: `python software/ai/vision/evaluate_translation_pair.py`
- Result: PASS, `PAIRED_RESEARCH_CRITERIA_PASS`, all four predeclared criteria pass
  in aggregate and each condition. Control -> candidate: mean key 0.947368 ->
  0.868438 mm; key p95 2.139202 -> 1.933529 mm; within-1mm 62.8087% -> 68.9072%;
  center mean 0.875454 -> 0.805079 mm; yaw p95 0.632257 -> 0.621475 degrees.
  Worst error worsens 6.975993 -> 7.093951 mm; improvement is not universal.
- Artifacts: frozen evaluator/manifest and full paired scorecard above.
- Hardware writes: 0
- Physical movements: 0
- Limitations: synthetic known-target localization only; no physical/domain,
  confidence or visibility qualification. Descriptive correlated samples, no
  significance claim. No calibrated uncertainty or runtime checkpoint replacement.
  18M groups are now consumed evaluation data and must not be reused as fresh.
- Supersedes: none; failed earlier evidence retained.
- Next dependency: freeze a new independent uncertainty-calibration split and
  evaluation split for the candidate; test complete bounds against independent
  target regions. Confidence and capture trust remain separate unresolved gates.

### E-20260926-AI-039 â€” paired held-out evidence verification

- Stage: S1
- Lane: AI
- Commit: `bc86500906578ba341862f1fd5cf758bf1db698b` (evaluation baseline; new test committed with evidence)
- Change: verified source/manifest hashes, fresh seed identities, paired group
  mean aggregation and recomputation of each acceptance criterion.
- Inputs/fixtures: frozen manifest, scorecard, `tests/test_translation_pair_evidence.py`.
- Command: `python -m pytest -q software/ai/tests/test_translation_pair_evidence.py`
- Result: PASS, 1 evidence test.
- Artifacts: named test, manifest and scorecard.
- Hardware writes: 0
- Physical movements: 0
- Limitations: consistency only; no installed qualification or integration status change.
- Supersedes: none
- Next dependency: AI-038 independent uncertainty study.


### E-20260926-AI-040 â€” paired evaluation audit findings retained

- Stage: S1
- Lane: AI
- Commit: `bc86500906578ba341862f1fd5cf758bf1db698b`
- Change: required read-only audit after evaluation.
- Inputs/fixtures: repository snapshot, paired scorecard/test and `scripts/audit_github_snapshot.py`.
- Command: `python scripts/audit_github_snapshot.py`
- Result: FAIL, exit 1; 5,665 paths, 785.6 MiB, same 14 existing arm-unit
  credential-literal-review findings; no paired-evaluation file finding.
- Artifacts: scanner and existing fixtures.
- Hardware writes: 0
- Physical movements: 0
- Limitations: heuristic findings unresolved; no clean audit claim.
- Supersedes: none
- Next dependency: fixture-owner review independently of AI qualification research.


### E-20260926-AI-041 â€” protected-main publishing blocker

- Stage: S1
- Lane: AI
- Commit: `5b94a8dfc218be5a31c94f172db6ae3b62378b88`
- Change: published completed paired evidence to `feature/translation-pair-evidence` after main protection rejected direct push.
- Inputs/fixtures: completed AI-038â€“040 changes and preserved arm merge.
- Command: `git push origin main`; `git push -u origin feature/translation-pair-evidence`; GitHub connector `github_create_pull_request` targeting main.
- Result: BLOCKED for PR creation: main push rejected GH006 (PR and four checks required); branch push succeeded; connector returned HTTP 403 Resource not accessible by integration. Local gh CLI unavailable.
- Artifacts: remote branch `feature/translation-pair-evidence`; no PR created.
- Hardware writes: 0
- Physical movements: 0
- Limitations: changes are published on branch but not merged to main; no protection bypass attempted.
- Supersedes: none
- Next dependency: authorized GitHub PR creation and required checks before merge.


### E-20260926-AI-042 â€” candidate uncertainty and full-region study

- Stage: S1
- Lane: AI
- Commit: `de696d1abff38f1db40a01daed8fd4235c350517` (exact frozen source/manifest before scoring)
- Change: calibrated 99% nearest-rank radius from seed-group maximum errors;
  independently evaluated error coverage and full-disk containment around actual
  predictions in hidden-truth oriented key regions. No automatic qualification.
- Inputs/fixtures: 1,000 fresh 19M calibration groups and 500 fresh 20M evaluation
  groups, 3 conditions/46 targets. Candidate/source/catalog hashes in
  `eval/candidate_uncertainty_v0.manifest.json`; group hashes/scores in scorecard.
- Command: `python software/ai/vision/evaluate_candidate_uncertainty.py`
- Result: FAIL, `SYNTHETIC_COMBINED_CRITERIA_FAIL`. Radius 5.201783 mm; error coverage
  494/500 groups (98.8%) passes 95% criterion. Actual complete-region group fit
  380/500 (76%) fails 95% criterion. 64,859/69,000 individual target predictions
  fit; this does not replace the frozen all-target/all-condition group criterion.
- Artifacts: `software/ai/eval/candidate_uncertainty_v0_scorecard.json`, manifest,
  evaluator; full source study retained locally under ignored
  `software/ai/results/candidate_uncertainty_v0_full.json` (content hash in scorecard).
- Hardware writes: 0
- Physical movements: 0
- Limitations: empirical coverage, not population guarantee. Hidden truth is
  evaluation-only and cannot become runtime placement calibration. Synthetic
  known targets only; no confidence/capture/physical qualification. 19M/20M seed
  groups are consumed and cannot be reused as fresh independent evaluation.
- Supersedes: none; earlier failures and improvements preserved.
- Next dependency: investigate residual-tail causes using development groups;
  any target-specific or conditional uncertainty method needs separate frozen
  calibration/evaluation and must preserve complete-region checking. No promotion.

### E-20260926-AI-043 â€” uncertainty evidence verification

- Stage: S1
- Lane: AI
- Commit: `de696d1abff38f1db40a01daed8fd4235c350517` (study baseline; test and evidence committed together)
- Change: recomputed calibration quantile, evaluation coverage, region-fit counts,
  frozen source identities and failure outcome.
- Inputs/fixtures: frozen manifest/scorecard and `tests/test_candidate_uncertainty_evidence.py`.
- Command: `python -m pytest -q software/ai/tests/test_candidate_uncertainty_evidence.py`
- Result: PASS, 1 evidence test; study failure remains unchanged.
- Artifacts: named test and scorecard.
- Hardware writes: 0
- Physical movements: 0
- Limitations: consistency only; no qualification or integration status change.
- Supersedes: none
- Next dependency: AI-042 development-tail investigation.

### E-20260926-AI-044 â€” uncertainty study audit findings retained

- Stage: S1
- Lane: AI
- Commit: `de696d1abff38f1db40a01daed8fd4235c350517`
- Change: required read-only repository audit during study.
- Inputs/fixtures: repository snapshot and `scripts/audit_github_snapshot.py`.
- Command: `python scripts/audit_github_snapshot.py`
- Result: FAIL, exit 1; 5,670 paths, 786.0 MiB, same 14 existing arm-unit
  credential-literal-review findings; no candidate-study file finding.
- Artifacts: scanner and existing fixtures.
- Hardware writes: 0
- Physical movements: 0
- Limitations: heuristic findings unresolved; no clean audit claim.
- Supersedes: none
- Next dependency: fixture-owner review; protected-main PR blocker AI-041 remains.


### E-20260926-AI-045 â€” audit passes after fixture-owner review merge

- Stage: S1
- Lane: AI
- Commit: `260a0811b3af6352ddc0eeb0f4186d083a8d59bd`
- Change: merged fixture-owner review manifest and updated auditor from main; reran audit.
- Inputs/fixtures: `scripts/audit_fixture_reviews.json`, reviewed fixtures and repository snapshot.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS, exit 0; 5,674 paths, 786.1 MiB, 0 unresolved findings,
  14 reviewed synthetic fixtures.
- Artifacts: `docs/AUDIT_FIXTURE_REVIEW.md`, review manifest and auditor.
- Hardware writes: 0
- Physical movements: 0
- Limitations: heuristic audit only, not a security guarantee; earlier audit failures retained.
- Supersedes: unresolved audit dependency in AI-044 after owner review; no historical result rewritten.
- Next dependency: protected-main PR creation/checks from AI-041; AI-042 localization work remains separate.


### E-20260926-AI-046 â€” development residual-tail stratification

- Stage: S1
- Lane: AI
- Commit: `ee9ab18fdefb69aab4213318e902d24974322b67` (exact frozen diagnostic and manifest)
- Change: analyzed candidate residuals on existing development images using a
  predeclared >3mm maximum-key-error diagnostic and marginal scene/pose bins.
- Inputs/fixtures: 200 existing 15M development groups, 600 images, 46 targets;
  checkpoint/source hashes in `eval/development_tails_v0.manifest.json`; image
  hash, per-image, per-key and stratified metrics in scorecard.
- Command: `python software/ai/vision/diagnose_development_tails.py`
- Result: PASS for descriptive diagnostic. 22/600 images exceed 3mm: standard
  5/200 (2.5%), appearance_shift 7/200 (3.5%), challenge 10/200 (5%). All four
  position bins and all three orientation bins contain large-error cases.
  Mean maximum-key error 1.215390 mm; mean center error 0.856611 mm.
- Artifacts: `software/ai/eval/development_tails_v0_scorecard.json`, manifest,
  `software/ai/vision/diagnose_development_tails.py`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: marginal strata are correlated/confounded, not causal or statistically
  significant effects. Truth-derived pose bins are scoring metadata, not runtime
  rules. No per-image occlusion labels; cannot isolate lighting/obstruction causes.
  No new calibration/evaluation data consumed; no qualification or runtime changes.
- Supersedes: none
- Next dependency: freeze a paired single-perturbation development study to isolate
  added brightness, blur and obstruction effects before targeted retraining;
  preserve all consumed calibration/evaluation splits.

### E-20260926-AI-047 â€” development-tail evidence checks

- Stage: S1
- Lane: AI
- Commit: `ee9ab18fdefb69aab4213318e902d24974322b67` (diagnostic baseline; new test committed with evidence)
- Change: verified frozen hashes, exact development-only seed set, fixed tail
  threshold and stratified counts.
- Inputs/fixtures: frozen manifest/scorecard and `tests/test_development_tails.py`.
- Command: `python -m pytest -q software/ai/tests/test_development_tails.py`
- Result: PASS, 1 evidence test.
- Artifacts: named test, manifest and scorecard.
- Hardware writes: 0
- Physical movements: 0
- Limitations: consistency only; not a runtime rejection rule or physical qualification.
- Supersedes: none
- Next dependency: AI-046 controlled perturbation experiment.


### E-20260926-AI-048 â€” tail diagnostic repository audit

- Stage: S1
- Lane: AI
- Commit: `ee9ab18fdefb69aab4213318e902d24974322b67` (diagnostic baseline plus scorecard/test)
- Change: required read-only audit after diagnostic.
- Inputs/fixtures: repository snapshot and reviewed fixture manifest.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS, exit 0; 5,678 paths, 786.3 MiB; 0 unresolved findings and 14 reviewed synthetic fixtures.
- Artifacts: auditor, fixture review manifest and AI-046 artifacts.
- Hardware writes: 0
- Physical movements: 0
- Limitations: heuristic audit only; protected-main publishing blocker AI-041 remains.
- Supersedes: none
- Next dependency: authorized PR creation/checks; AI-046 perturbation study independently.


### E-20260926-AI-049 â€” paired single-perturbation development study

- Stage: S1
- Lane: AI
- Commit: `a8f2a0982939877473c11bfa61167e921ea20479` (exact frozen diagnostic/manifest before scoring)
- Change: added brightness factor 0.5, Gaussian blur 1.2 pixels, or fixed small
  opaque rectangle separately to the same standard development image per seed.
- Inputs/fixtures: existing 15M 200 development groups; 4 variants/seed, 46 targets;
  checkpoint/source hashes in `eval/single_perturbations_v0.manifest.json`;
  per-condition pixel hashes, paired cases and counts in scorecard.
- Command: `python software/ai/vision/diagnose_single_perturbations.py`
- Result: PASS for completed diagnostic. Mean key error base 0.853172 mm,
  darkened 2.515475 mm, blur 0.832448 mm, obstruction 0.871324 mm. Images with
  maximum key error >3mm: 5, 87, 4, 5 respectively (200 each). Darkening worsens
  178/200 images and introduces 83 new >3mm cases. Added effects are paired.
- Artifacts: `software/ai/eval/single_perturbations_v0_scorecard.json`, manifest,
  `software/ai/vision/diagnose_single_perturbations.py`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: base renderer already contains nuisance effects; fixed synthetic
  strengths/obstruction location do not represent all camera/arm conditions.
  No interactions, visibility qualification, measured lighting threshold or
  held-out data. Small mean changes do not establish blur/obstruction safety.
- Supersedes: none
- Next dependency: freeze paired brightness-augmentation training versus control
  on development groups, retaining baseline/yaw checks; later use fresh calibration
  and evaluation. Do not infer a deployable darkness threshold from this study.

### E-20260926-AI-050 â€” paired perturbation evidence tests

- Stage: S1
- Lane: AI
- Commit: `a8f2a0982939877473c11bfa61167e921ea20479` (diagnostic baseline; test committed with evidence)
- Change: verified base-image immutability, brightness arithmetic, unknown-condition
  rejection, source hashes, development seeds and paired metric counts.
- Inputs/fixtures: analytic PIL image and frozen paired scorecard/manifest.
- Command: `python -m pytest -q software/ai/tests/test_single_perturbations.py`
- Result: PASS, 2 tests.
- Artifacts: named test and AI-049 scorecard.
- Hardware writes: 0
- Physical movements: 0
- Limitations: offline consistency only, no confidence or physical qualification.
- Supersedes: none
- Next dependency: AI-049 brightness-robustness training.

### E-20260926-AI-051 â€” paired perturbation publication audit

- Stage: S1
- Lane: AI
- Commit: `a8f2a0982939877473c11bfa61167e921ea20479` (frozen diagnostic baseline; scorecard and tests committed with evidence)
- Change: audited the publication snapshot after adding paired perturbation evidence.
- Inputs/fixtures: repository snapshot including AI-049 scorecard and AI-050 tests;
  existing reviewed synthetic fixture allowlist.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS; 5682 paths, 786.5 MiB, 0 unresolved findings,
  14 reviewed synthetic fixtures.
- Artifacts: repository snapshot and audit stdout.
- Hardware writes: 0
- Physical movements: 0
- Limitations: heuristic snapshot audit only; no physical or localization
  qualification. Protected-main publication blocker AI-041 remains.
- Supersedes: none; historical failed audit evidence remains unchanged.
- Next dependency: paired brightness-augmentation development comparison;
  authorized PR creation and protected-branch checks for main publication.

### E-20260926-ARM-018 â€” published zero-write controller boundary

- Stage: S4
- Lane: ARM
- Commit: `b858420` (implementation commit; evidence row committed separately)
- Change: published strict Draft 2020-12 schemas for the Waveshare T=102
  encoding profile, single-use preview permit, zero-write preview receipt,
  hash-chained sole-writer journal, and lifecycle report. Added stable
  serializations for profile and permit plus a committed exact-byte T=102
  fixture generated through the existing sealed-envelope path.
- Inputs/fixtures: synthetic ready v2 envelope from the established arm test
  factory; `software/tests/fixtures/zero_write_waveshare_v1/t102_waypoint_1.jsonl`;
  fixed offline profile and monotonic timestamps.
- Command: `$env:PYTHONPATH='software/src;software/ai/src;software/tests/unit'; python -m pytest -q software/ai/tests software/tests/unit/test_model_motion_ingress_v2.py software/tests/unit/test_model_motion_sequence_journal.py software/tests/unit/test_model_motion_sequence_coordinator.py software/tests/unit/test_trajectory_execution_envelope_v2.py software/tests/unit/test_zero_write_waveshare_adapter_v1.py software/tests/unit/test_zero_write_sole_writer_v1.py software/tests/integration/test_zero_write_waveshare_contract_v1.py`
- Result: PASS, 210 tests. Runtime documents validate against all five closed
  schemas; exact wire bytes and their SHA-256 match the committed fixture;
  content hashes recompute; the journal round-trips; unpublished fields and
  asserted hardware authority reject.
- Artifacts: five `software/ai/schemas/zero_write_*_v1.schema.json` files,
  schema README, golden JSONL fixture, and
  `software/tests/integration/test_zero_write_waveshare_contract_v1.py`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: all inputs and bytes are synthetic/offline. The profile binds a
  controller-joint-mapping hash but does not prove that mapping, firmware
  version, acknowledgement grammar, feedback behavior, or installed hardware.
  The encoder still owns no transport or physical authority.
- Supersedes: none; extends ARM-014 and ARM-016 with a published interchange
  boundary.
- Next dependency: independently commission the installed controller mapping
  and firmware evidence before any S4 readiness or physical dispatch claim.

### E-20260926-ARM-019 â€” zero-write schema audit findings retained

- Stage: S4
- Lane: ARM
- Commit: `b858420` (implementation baseline)
- Change: ran the required read-only repository snapshot audit after publishing
  the zero-write schemas and golden byte fixture.
- Inputs/fixtures: repository snapshot and `scripts/audit_github_snapshot.py`.
- Command: `python scripts/audit_github_snapshot.py`
- Result: FAIL, exit 1; 5,670 paths, 903.5 MiB, the same 14 existing
  credential-literal-review findings in arm unit fixtures; no new schema,
  golden-fixture, adapter-serialization, or integration-test finding.
- Artifacts: scanner and the existing named fixtures in its output.
- Hardware writes: 0
- Physical movements: 0
- Limitations: heuristic findings remain unresolved; this is not a clean
  repository security-audit claim.
- Supersedes: none; retains all earlier audit failures.
- Next dependency: fixture-owner review remains independent of installed
  controller mapping and firmware qualification.

### E-20260926-ARM-020 â€” reviewed-fixture integration verification

- Stage: S4
- Lane: ARM
- Commit: `681e3a3` plus merged `origin/main` at `1cb96bd` (verified integration
  baseline; this evidence row committed separately)
- Change: merged the repository's independently reviewed synthetic-fixture
  allowlist and reran the zero-write/shared-contract tests and snapshot audit
  without changing the S4 artifacts or erasing ARM-019's historical result.
- Inputs/fixtures: ARM-018 artifacts, current AI tests, motion-ingress and
  sequence tests, trajectory envelope tests, snapshot-audit tests, and reviewed
  exception records from `scripts/audit_fixture_reviews.json`.
- Commands: the ARM-018 pytest command plus
  `software/tests/unit/test_snapshot_audit.py`; then
  `python scripts/audit_github_snapshot.py`.
- Result: PASS, 229 tests in 43.41 seconds. Audit PASS, exit 0; 5,673 paths,
  903.5 MiB, 0 unresolved review findings, 14 reviewed synthetic fixtures.
- Artifacts: ARM-018 schema/fixture/test artifacts plus the independently merged
  audit review records and tests.
- Hardware writes: 0
- Physical movements: 0
- Limitations: reviewed audit exceptions are exact synthetic test fixtures, not
  production credentials. Passing schemas and golden bytes still do not qualify
  installed controller mapping, firmware, acknowledgements, feedback, or any
  physical execution path.
- Supersedes: ARM-019 only for current audit status; ARM-019 remains the exact
  pre-review snapshot result.
- Next dependency: independently commission the installed controller mapping
  and firmware evidence before any S4 readiness or physical-dispatch claim.

### E-20260926-AI-052 â€” matched brightness augmentation development failure

- Stage: S1
- Lane: AI
- Commit: `4801532e942e8f2574d86813665e327d833502ca` (frozen training source and plan before execution)
- Change: paired fine-tuning from the existing translation-weighted checkpoint.
  Candidate adds a brightness-0.5 copy of every training image; control duplicates
  the unchanged image for equal optimizer steps. Both use weights 4:4:1, 12 epochs,
  common unweighted four-condition development-MSE epoch selection.
- Inputs/fixtures: reused 14M training groups (1200 x 3 x 2 = 7200 images),
  reused 15M development groups (200 x 4 = 800 images), 46 targets/image.
  Source/catalog/initial checkpoint hashes in `train/brightness_pair_v0_plan.json`;
  training/development pixel hashes and output checkpoint hashes in scorecard.
- Command: `python software/ai/vision/train_brightness_pair.py`
- Result: FAIL predefined development candidate rule. Darkened-standard mean key
  error improves 2.399967 -> 0.878742 mm; >3mm maximum-key-error images 87 -> 5/200.
  Standard worsens 0.816161 -> 0.989308 mm, tail 3 -> 6;
  appearance-shift worsens 0.796980 -> 1.013772 mm, tail 5 -> 10;
  challenge worsens 1.029145 -> 1.089872 mm, tail 9 -> 14.
  All original conditions also exceed the allowed 10% yaw-p95 regression.
  Aggregate mean improves 1.260563 -> 0.992923 mm but cannot override condition gates.
  Selected epochs control 12, candidate 10. No model promotion.
- Artifacts: `eval/brightness_pair_v0_scorecard.json`, frozen plan/source;
  ignored local `results/brightness_pair_v0_control/` and
  `results/brightness_pair_v0_brightness_augmented/` checkpoint/result directories.
- Hardware writes: 0
- Physical movements: 0
- Limitations: one training seed; development data reused for study selection;
  fixed synthetic brightness applied after resizing; no fresh evaluation,
  calibrated uncertainty, authentic camera capture or physical evidence.
  Zero contract changes; shared boundary suite not triggered.
- Supersedes: none; AI-049 and all earlier failed evidence remain intact.
- Next dependency: freeze a bounded lower-intensity brightness training comparison
  (reduced dark-sample proportion and lower learning rate) against a matched control,
  retaining the per-condition error, tail and yaw gates. Require fresh calibration
  and evaluation only after development criteria pass; no installed qualification.

### E-20260926-AI-053 â€” brightness evidence consistency tests

- Stage: S1
- Lane: AI
- Commit: `4801532e942e8f2574d86813665e327d833502ca` (frozen implementation baseline; tests committed with results)
- Change: checked source/plan hashes, matched sample budgets, common development
  pixels, distinct training pixels, epoch selection, seed coverage and case metrics.
- Inputs/fixtures: AI-052 plan and scorecard, 800 cases per arm.
- Command: `python -m pytest -q software/ai/tests/test_brightness_pair_evidence.py`
- Result: PASS, 2 tests; existing pytest-asyncio configuration deprecation warning.
- Artifacts: named test and AI-052 scorecard.
- Hardware writes: 0
- Physical movements: 0
- Limitations: consistency tests do not establish physical accuracy or confidence.
- Supersedes: none
- Next dependency: AI-052 development comparison; preserve failed candidate.

### E-20260926-AI-054 â€” brightness evidence publication audit

- Stage: S1
- Lane: AI
- Commit: `4801532e942e8f2574d86813665e327d833502ca` (implementation baseline plus AI-052 scorecard/test snapshot)
- Change: ran the repository publication audit.
- Inputs/fixtures: repository snapshot with brightness evidence; reviewed synthetic fixture allowlist.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS; 5698 paths, 787.0 MiB, 0 unresolved findings,
  14 reviewed synthetic fixtures.
- Artifacts: audit stdout and repository snapshot.
- Hardware writes: 0
- Physical movements: 0
- Limitations: heuristic audit, not localization qualification; AI-041 protected-main
  PR publication blocker remains. Historical audit failures remain unchanged.
- Supersedes: none
- Next dependency: protected-branch PR/checks; AI-052 next development experiment.

### E-20260926-ARM-021 â€” installed-controller qualification gate

- Stage: S4
- Lane: ARM
- Commit: `f78b2f1` (implementation commit; evidence row committed separately)
- Change: added a fail-closed assessment between the installed controller's
  independently reviewed evidence and the zero-write Waveshare encoding
  profile. The gate binds controller session, configuration epoch, mapping
  hash, protocol-source hash, T=102 command fields, T=1051 feedback fields,
  planner joint order, fixed gripper field, evidence origin, review disposition,
  and monotonic freshness.
- Inputs/fixtures: modeled physical-shaped and synthetic evidence records;
  existing sealed-envelope/profile factory; published strict evidence and
  assessment schemas. No retained physical original was consumed.
- Command: `$env:PYTHONPATH='software/src;software/ai/src;software/tests/unit'; python -m pytest -q software/ai/tests software/tests/unit/test_model_motion_ingress_v2.py software/tests/unit/test_model_motion_sequence_journal.py software/tests/unit/test_model_motion_sequence_coordinator.py software/tests/unit/test_trajectory_execution_envelope_v2.py software/tests/unit/test_zero_write_waveshare_adapter_v1.py software/tests/unit/test_zero_write_sole_writer_v1.py software/tests/unit/test_installed_controller_qualification_v1.py software/tests/integration/test_zero_write_waveshare_contract_v1.py software/tests/unit/test_snapshot_audit.py`
- Result: PASS, 244 tests in 45.74 seconds. Missing, synthetic, stale,
  unreviewed, pre-capture, session/epoch/mapping/protocol mismatched, reordered,
  and wrong-gripper evidence all block. Exact modeled evidence reaches only
  `READY_FOR_ZERO_WRITE_PROFILE_BINDING`; execution and transport authority
  remain false and zero hardware commands are generated.
- Artifacts:
  `software/src/rocell/application/installed_controller_qualification_v1.py`,
  two `installed_controller_qualification_*_v1.schema.json` schemas, exports,
  schema documentation, and the named unit test.
- Hardware writes: 0
- Physical movements: 0
- Limitations: success cases use modeled physical-shaped records and prove only
  deterministic gate behavior. The module neither collects nor independently
  authenticates evidence. No installed firmware, mapping, startup behavior,
  feedback behavior, controller identity, or physical execution is qualified.
- Supersedes: none; closes the software trust-boundary gap identified by ARM-018.
- Next dependency: collect retained originals under a separately approved,
  bounded physical qualification and obtain independent review before using a
  passing evidence record.

### E-20260926-ARM-022 â€” controller-gate repository audit

- Stage: S4
- Lane: ARM
- Commit: `f78b2f1` (implementation baseline)
- Change: ran the required read-only repository snapshot audit after adding the
  installed-controller qualification gate.
- Inputs/fixtures: repository snapshot, reviewed fixture registry, and
  `scripts/audit_github_snapshot.py`.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS, exit 0; 5,677 paths, 903.6 MiB, 0 unresolved review findings,
  14 reviewed synthetic fixtures.
- Artifacts: scanner, reviewed fixture registry, and the new gate artifacts.
- Hardware writes: 0
- Physical movements: 0
- Limitations: repository scanning and reviewed synthetic fixture exceptions do
  not qualify controller hardware, firmware, mapping, or runtime behavior.
- Supersedes: none.
- Next dependency: collect and independently review exact installed-controller
  evidence; keep physical execution blocked until that is complete.

### E-20260926-ARM-023 â€” controller-gate release-doc integration

- Stage: S4
- Lane: ARM
- Commit: `592092b` plus merged `origin/main` at `b1bb742` (verified integration
  baseline; this evidence row committed separately)
- Change: merged concurrent experimental-release/support documentation and
  reverified the controller gate without altering its trust or authority rules.
- Inputs/fixtures: ARM-021 suite plus the current repository snapshot.
- Commands: ARM-021 pytest command; `python scripts/audit_github_snapshot.py`.
- Result: PASS, 244 tests in 41.32 seconds. Audit PASS, exit 0; 5,682 paths,
  903.6 MiB, 0 unresolved review findings, 14 reviewed synthetic fixtures.
- Hardware writes: 0
- Physical movements: 0
- Limitations: integration success is still offline and does not qualify the
  installed controller, mapping, firmware, feedback, or startup behavior.
- Supersedes: ARM-022 only for the current integrated snapshot counts.
- Next dependency: separately approved physical evidence collection and
  independent review before zero-write profile binding can pass on real data.

### E-20260926-AI-055 â€” reduced brightness augmentation development failure

- Stage: S1
- Lane: AI
- Commit: `0a878a5ed15a8e516a0ef6b586b940286e64244d` (frozen source and plan before training)
- Change: matched comparison at learning rate 0.00005; candidate darkens extra
  image copies for alternating training seed groups (1800/7200 images, 25 percent).
  Control duplicates unchanged images. Both start from the original translation
  candidate, use 12 epochs and weights 4:4:1, and select the epoch using common
  four-condition unweighted development MSE. Previous rejected model is not used.
- Inputs/fixtures: reused 14M training groups (1200 x 3 x 2), 15M development
  groups (200 x 4), 46 targets/image. Exact source, initial-checkpoint and catalog
  hashes in `train/brightness_reduced_v0_plan.json`; pixel and output checkpoint
  hashes and case-level metrics in the scorecard.
- Command: `python software/ai/vision/train_brightness_reduced.py`
- Result: FAIL predefined development candidate rule. Darkened-standard mean
  key error 2.577164 -> 0.911283 mm and >3mm maximum-key-error images 106 -> 5/200.
  Standard mean 0.814534 -> 0.919565 mm, tail 3 -> 4;
  appearance-shift mean 0.821052 -> 1.060568 mm, tail 6 -> 10;
  challenge mean 1.038751 -> 1.056718 mm, tail 8 -> 13.
  All original conditions fail the yaw-p95 allowance; challenge alone passes
  the original-condition mean-error allowance. Aggregate mean 1.312875 ->
  0.987033 mm cannot override those failures. Selected epochs control 12,
  candidate 9. No promotion or installed qualification.
- Artifacts: `eval/brightness_reduced_v0_scorecard.json`, frozen plan/source,
  ignored local `results/brightness_reduced_v0_control/` and
  `results/brightness_reduced_v0_brightness_augmented/` checkpoints/results.
- Hardware writes: 0
- Physical movements: 0
- Limitations: development selection on reused groups; one training seed;
  factor0.5 applied after resize; lower rate and reduced proportion form a
  combined intervention, so their individual effects are not identified.
  No fresh evaluation, physical capture, calibrated uncertainty or boundary
  change. Shared boundary suite not triggered.
- Supersedes: none; AI-052 failure remains intact.
- Next dependency: freeze a bounded comparison adding baseline-preservation
  distillation on original-condition training images against an otherwise matched
  augmentation control, with unchanged development gates. No fresh evaluation
  or confidence calibration until a candidate passes development criteria.

### E-20260926-AI-056 â€” reduced brightness evidence tests

- Stage: S1
- Lane: AI
- Commit: `0a878a5ed15a8e516a0ef6b586b940286e64244d` (frozen implementation baseline; tests committed with evidence)
- Change: checked hashes, matched budgets, selected epochs, shared development
  pixels, seed/case metrics, 25-percent schedule and independently recounted gates.
- Inputs/fixtures: AI-055 plan/scorecard, 800 cases per arm; alternating-seed schedule.
- Command: `python -m pytest -q software/ai/tests/test_brightness_reduced_evidence.py`
- Result: PASS, 3 tests; existing pytest-asyncio configuration deprecation warning.
- Artifacts: named test and AI-055 scorecard.
- Hardware writes: 0
- Physical movements: 0
- Limitations: offline evidence consistency, not physical localization confidence.
- Supersedes: none
- Next dependency: AI-055 baseline-preservation experiment.

### E-20260926-AI-057 â€” reduced brightness publication audit

- Stage: S1
- Lane: AI
- Commit: `0a878a5ed15a8e516a0ef6b586b940286e64244d` (implementation baseline plus result/test snapshot)
- Change: audited the publication snapshot.
- Inputs/fixtures: repository with AI-055/056 artifacts and reviewed fixture allowlist.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS; 5706 paths, 787.5 MiB, 0 unresolved findings, 14 reviewed synthetic fixtures.
- Artifacts: audit stdout and repository snapshot.
- Hardware writes: 0
- Physical movements: 0
- Limitations: heuristic audit only; AI-041 protected-main PR blocker remains.
- Supersedes: none; historical failed audit evidence retained.
- Next dependency: protected-branch PR/checks and AI-055 development experiment.

### E-20260926-AI-058 â€” baseline-preservation distillation development failure

- Stage: S1
- Lane: AI
- Commit: `cc6b73dea829e33b6e49e065b42d300c47e64415` (frozen training source/plan before execution)
- Change: both arms use identical 25-percent darkened training images, LR0.00005,
  12 epochs, normalized pose weights 4:4:1 and common development-MSE selection.
  Candidate adds weight4 teacher-preservation loss on original images; control
  weight0. Teacher predictions are detached from the initial checkpoint, using
  training images only. The frozen nonaugmented AI-055 control is an additional
  reference; passing against a regressed augmentation control alone is insufficient.
- Inputs/fixtures: reused 14M 1200 training groups, 7200 images (5400 original);
  reused 15M 200 development groups x4 conditions, 46 targets/image.
  Source, catalog, initial checkpoint and reference-scorecard hashes are in
  `train/brightness_preserved_v0_plan.json`; output checkpoint, pixel and teacher
  prediction hashes and case metrics are in the scorecard.
- Command: `python software/ai/vision/train_brightness_preserved.py`
- Result: FAIL predefined combined development rule. Versus matched augmentation
  control, standard mean 0.918388 -> 0.877357 mm, appearance-shift 1.059982 ->
  0.940878 mm, challenge 1.057172 -> 1.043721 mm, darkened-standard 0.910199 ->
  1.011594 mm. >3mm image counts: standard 4 -> 6, appearance 10 -> 10,
  challenge 13 -> 13, darkened 4 -> 12 (200 images/condition).
  Candidate also fails original-condition mean/tail limits against the frozen
  nonaugmented reference. Aggregate mean 0.986436 -> 0.968388 mm cannot override
  failed gates. Selected epochs control9/candidate10. No model promotion.
- Artifacts: `eval/brightness_preserved_v0_scorecard.json`, frozen plan/source;
  ignored local `results/brightness_preserved_v0_augmentation_control/` and
  `results/brightness_preserved_v0_preservation/` checkpoints/results.
- Hardware writes: 0
- Physical movements: 0
- Limitations: reused development selection, one seed, synthetic factor0.5 after
  resize, teacher may preserve its own errors; GPU numerical reproducibility is
  not bitwise guaranteed. No fresh evaluation or runtime confidence qualification.
  No boundary change; shared boundary suite not triggered.
- Supersedes: none; earlier brightness failures remain intact.
- Next dependency: freeze a development-only photometric-normalization comparison
  on the unchanged initial checkpoint, with unchanged per-condition error/tail/yaw
  limits. This tests a different intervention after three failed training variants;
  it must not become a runtime preprocessing rule without subsequent evidence.

### E-20260926-AI-059 â€” preservation evidence and loss tests

- Stage: S1
- Lane: AI
- Commit: `cc6b73dea829e33b6e49e065b42d300c47e64415` (implementation baseline; tests committed with evidence)
- Change: verified frozen hashes, identical training/development pixels and teacher
  predictions, sample budgets, epoch selection, per-case metrics, independent gate
  recounts and masked loss gradients (dark images contribute zero preservation loss).
- Inputs/fixtures: AI-058 plan/scorecard, AI-055 reference, analytic Torch tensors.
- Command: `python -m pytest -q software/ai/tests/test_brightness_preserved_evidence.py`
- Result: PASS, 4 tests; existing pytest-asyncio configuration deprecation warning.
- Artifacts: named test and AI-058 scorecard.
- Hardware writes: 0
- Physical movements: 0
- Limitations: offline consistency and loss correctness, not physical confidence.
- Supersedes: none
- Next dependency: AI-058 normalization diagnostic.

### E-20260926-AI-060 â€” preservation evidence publication audit

- Stage: S1
- Lane: AI
- Commit: `cc6b73dea829e33b6e49e065b42d300c47e64415` (implementation baseline plus result/test snapshot)
- Change: audited the repository publication snapshot.
- Inputs/fixtures: repository including AI-058/059 artifacts and reviewed fixture allowlist.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS; 5711 paths, 788.0 MiB, 0 unresolved findings, 14 reviewed synthetic fixtures.
- Artifacts: audit stdout and repository snapshot.
- Hardware writes: 0
- Physical movements: 0
- Limitations: heuristic audit only; AI-041 protected-main PR publication blocker remains.
- Supersedes: none; historical audit failures retained.
- Next dependency: protected-branch PR/checks and AI-058 diagnostic.

### E-20260926-AI-061 â€” fixed lighting normalization development failure

- Stage: S1
- Lane: AI
- Commit: `dd2f0f14f26f78afd327b5aa2d8c6764b4c78f2b` (frozen source and manifest before scoring)
- Change: unchanged initial translation checkpoint; compare original pixels against
  global RGB gain220/p95(luminance), denominator>=1, gain clipped[0.5,2.5], rounded
  and clipped to uint8 after resizing. No truth, target location or camera metadata
  participates in preprocessing; no parameters were tuned after scoring.
- Inputs/fixtures: reused 15M 200 development groups x4 conditions, 46 targets.
  Source/checkpoint/catalog hashes in `eval/lighting_normalization_v0.manifest.json`;
  paired cases, gains and input-pixel digests in scorecard.
- Command: `python software/ai/vision/evaluate_lighting_normalization.py`
- Result: FAIL combined development criteria (11/12 checks pass). Darkened-standard
  mean 2.512120 -> 0.845294 mm; >3mm image count86 -> 6/200.
  Standard mean0.853172 -> 0.846697 mm, tail5 -> 5;
  appearance-shift mean0.833414 -> 0.873718 mm, tail7 -> 8;
  challenge mean1.032991 -> 0.937176 mm, tail10 -> 8.
  Appearance-shift tail increase is the failing check. No runtime preprocessing
  installation, checkpoint promotion or localization qualification.
- Artifacts: `eval/lighting_normalization_v0_scorecard.json`, manifest, evaluator.
- Hardware writes: 0
- Physical movements: 0
- Limitations: reused synthetic development groups, fixed camera rendering and
  synthetic darkening; global gain cannot recover occluded or clipped content.
  Model was not trained with this normalization. Passing individual checks is
  not a held-out, physical or calibrated-confidence claim. No contract changes;
  shared boundary suite not triggered.
- Supersedes: none; all failed training variants remain retained.
- Next dependency: diagnose paired appearance-shift threshold crossings from
  existing cases and image evidence before choosing another normalization rule.
  Preserve failure; do not relax tail criteria to pass this candidate.

### E-20260926-AI-062 â€” lighting normalization evidence tests

- Stage: S1
- Lane: AI
- Commit: `dd2f0f14f26f78afd327b5aa2d8c6764b4c78f2b` (implementation baseline; tests committed with results)
- Change: checked analytic gray/black/white transform behavior, immutability,
  bounded gain, provenance, seed coverage, per-case metrics and independent gates.
- Inputs/fixtures: analytic PIL images and AI-061 manifest/scorecard (800 paired cases).
- Command: `python -m pytest -q software/ai/tests/test_lighting_normalization.py`
- Result: PASS, 2 tests; existing pytest-asyncio configuration deprecation warning.
- Artifacts: named test and AI-061 scorecard.
- Hardware writes: 0
- Physical movements: 0
- Limitations: offline correctness only; no physical confidence qualification.
- Supersedes: none
- Next dependency: AI-061 paired crossing diagnosis.

### E-20260926-AI-063 â€” normalization publication audit

- Stage: S1
- Lane: AI
- Commit: `dd2f0f14f26f78afd327b5aa2d8c6764b4c78f2b` (implementation baseline plus result/test snapshot)
- Change: audited the repository publication snapshot.
- Inputs/fixtures: repository with AI-061/062 artifacts and reviewed fixture allowlist.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS; 5715 paths, 788.5 MiB, 0 unresolved findings, 14 reviewed synthetic fixtures.
- Artifacts: audit stdout and repository snapshot.
- Hardware writes: 0
- Physical movements: 0
- Limitations: heuristic audit only; AI-041 protected-main PR publication blocker remains.
- Supersedes: none; historical audit failures retained.
- Next dependency: protected-branch PR/checks and AI-061 diagnostic.

### E-20260926-AI-064 â€” paired normalization crossing diagnosis

- Stage: S1
- Lane: AI
- Commit: `e5e3bc7fe7fbdff2b6e43324bf72b2b9066ff327` (frozen diagnostic and input hashes before run)
- Change: recounted paired transitions across the existing 3mm threshold for all
  conditions; reconstructed all eight appearance-shift cases failing either arm
  and produced a labeled contact sheet with pixel statistics/hashes.
- Inputs/fixtures: retained AI-061 800 paired development cases; exact scorecard,
  renderer and normalization source hashes in `eval/normalization_crossings_v0.manifest.json`.
- Command: `python software/ai/vision/diagnose_normalization_crossings.py`
- Result: PASS diagnostic, with AI-061 acceptance failure unchanged. New/persistent/
  recovered failures respectively: standard0/5/0, appearance1/7/0,
  challenge1/7/3, darkened1/5/81. Appearance seed15000114 has maximum error
  1.603918 -> 3.821403 mm; center1.561153 -> 3.765002 mm;
  yaw0.059889 -> 0.070912 degrees; gain1.152520, no saturated RGB samples.
  Its gain lies within stable-pass gain range0.938971..1.207564, so a simple
  gain range cannot separate it from all passing examples. Visual inspection of
  paired contact sheet shows no obvious arm obstruction for this new failure;
  that observation is not a causal explanation or visibility qualification.
- Artifacts: `eval/normalization_crossings_v0_report.json`, manifest, diagnostic;
  ignored reproducible `results/normalization_crossings_v0/appearance_crossings.png`
  with hash in report, visually inspected after generation.
- Hardware writes: 0
- Physical movements: 0
- Limitations: post-hoc analysis of reused synthetic development labels; crossing
  labels are unavailable at inference and must never be used as a runtime gate.
  No new predictions, tuned threshold, calibration, or qualification. No boundary
  change; shared boundary suite not triggered.
- Supersedes: none; AI-061 remains a failed acceptance result.
- Next dependency: predeclare a bounded dark-only normalization comparison using
  image pixels alone and unchanged acceptance limits. Treat any chosen darkness
  threshold as a research parameter, not physical calibration; require fresh
  held-out evaluation and confidence work after development success.

### E-20260926-AI-065 â€” crossing diagnosis consistency tests

- Stage: S1
- Lane: AI
- Commit: `e5e3bc7fe7fbdff2b6e43324bf72b2b9066ff327` (implementation baseline; tests committed with report)
- Change: verified strict3mm boundary cases, frozen hashes, seed groups,
  transition accounting, source-case preservation and all eight selected details.
- Inputs/fixtures: analytic threshold values; AI-061 scorecard and AI-064 report.
- Command: `python -m pytest -q software/ai/tests/test_normalization_crossings.py`
- Result: PASS, 2 tests; existing pytest-asyncio configuration deprecation warning.
- Artifacts: named tests and AI-064 report.
- Hardware writes: 0
- Physical movements: 0
- Limitations: consistency only, not physical accuracy or causal identification.
- Supersedes: none
- Next dependency: AI-064 bounded comparison.

### E-20260926-AI-066 â€” crossing diagnosis publication audit

- Stage: S1
- Lane: AI
- Commit: `e5e3bc7fe7fbdff2b6e43324bf72b2b9066ff327` (implementation baseline plus report/test snapshot)
- Change: audited publication snapshot.
- Inputs/fixtures: repository with AI-064/065 artifacts and reviewed fixture allowlist.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS; 5721 paths, 788.5 MiB, 0 unresolved findings, 14 reviewed synthetic fixtures.
- Artifacts: audit stdout and repository snapshot.
- Hardware writes: 0
- Physical movements: 0
- Limitations: heuristic audit; AI-041 protected-main PR blocker remains.
- Supersedes: none; historical failures preserved.
- Next dependency: protected-branch PR/checks and AI-064 comparison.

### E-20260926-ARM-024 â€” passive r96 evidence candidate and live identity capture

- Stage: S4
- Lane: ARM
- Change: added a pure fail-closed assembler, strict schema, tests, and a
  one-GET/no-retry r96 collector. The collector never opens serial and cannot
  produce approved qualification evidence. A separately approved live run
  correlated the unchanged r96 boot with exact local app bytes, its one-attempt
  install journal, protected-region result, and final registration export.
- Physical observation: one HTTP `GET` of the fixed r96 capability endpoint.
  Boot `4390cfab5cd74a16fd5048406c1b5adf` remained unchanged and reported one
  maximum leg, no automatic progression, no gripper writes, and motion
  unauthorized. COM7 was not opened; the controller was not restarted.
- Local artifact: ignored
  `software/runs/installed-controller-qualification/r96-passive-20260926.json`;
  evidence hash
  `45f7390a22ba312cb004d7b23c12c0370bcdd49bca61e87750858be449937eb8`;
  file hash
  `6c11665a036e0875469098156a7ed8e1332e207739c444192adecda6e3b219d0`.
- Command: `$env:PYTHONPATH='software/src;software/ai/src;software/tests/unit'; python -m pytest -q software/tests/unit/test_installed_controller_passive_evidence_v1.py software/tests/unit/test_installed_controller_qualification_v1.py software/tests/unit/test_zero_write_waveshare_adapter_v1.py software/tests/unit/test_zero_write_sole_writer_v1.py software/tests/integration/test_zero_write_waveshare_contract_v1.py`.
- Result: PASS, 58 tests. Capability drift, app/hash mismatch, install-stage
  drift, different boot, retry-enabled result, and non-verified result all fail
  closed. The schema rejects claimed approval or execution authority.
- Artifacts:
  `software/src/rocell/application/installed_controller_passive_evidence_v1.py`,
  `software/scripts/capture_r96_passive_evidence.py`,
  `software/ai/schemas/installed_controller_passive_evidence_v1.schema.json`,
  `software/tests/unit/test_installed_controller_passive_evidence_v1.py`, and
  `software/docs/INSTALLED_CONTROLLER_PASSIVE_EVIDENCE.md`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: the runtime does not attest its app hash; retained installation
  and feedback records are correlated but not independently reviewed. Mapping,
  protocol, startup, feedback and configuration-epoch bindings remain absent.
  The candidate is `UNREVIEWED`, qualification readiness is false, and it grants
  no transport, execution, or physical authority.
- Supersedes: ARM-023 only for the statement that no physical original had been
  consumed; all ARM-023 authority and qualification limitations remain.
- Next dependency: an independent reviewer validates the candidate and supplies
  separately hashed evidence for all seven blockers. Do not construct a passing
  qualification record until every blocker is closed.

### E-20260926-ARM-025 â€” passive-evidence integration verification

- Stage: S4
- Lane: ARM
- Change: re-ran the shared AI/arm and zero-write controller boundary after the
  passive-evidence increment, then audited the complete repository snapshot.
- Commands: `python scripts/ci/check_docs.py`; ARM-021's integrated pytest
  selection with `test_installed_controller_passive_evidence_v1.py` added;
  `python scripts/audit_github_snapshot.py`; `git diff --check`.
- Result: documentation PASS for 19 maintained documents and two SVG assets;
  pytest PASS, 253 tests in 38.41 seconds; audit PASS, 5,688 paths, 903.6 MiB,
  zero unresolved findings and 14 reviewed synthetic fixtures; diff check PASS.
- Hardware writes: 0
- Physical movements: 0
- Limitations: software verification and a passive identity observation do not
  independently qualify the installed mapping, protocol, startup, feedback, or
  configuration epoch. The local candidate remains unreviewed and blocked.
- Supersedes: ARM-023 only for the current integrated test/audit counts; it does
  not supersede ARM-024's live observation or limitations.
- Next dependency: independent evidence review and explicit resolution of the
  seven blockers listed by ARM-024.

### E-20260926-AI-067 â€” dark-only normalization development pass

- Stage: S1
- Lane: AI
- Commit: `2ebb30f4814ec62d5a8b6fb473b790e1a0b34de6` (frozen evaluator/manifest before scoring)
- Change: unchanged translation checkpoint, pixel-only correction when p95
  luminance<128. Brighter images are copied unchanged; corrected gain220/p95
  is clipped[1,2.5]. Threshold128 is a research choice informed by earlier
  development diagnostics, not measured camera calibration.
- Inputs/fixtures: reused 15M 200 development groups x4 conditions, 46 targets/image;
  exact source/checkpoint/catalog hashes in `eval/dark_only_normalization_v0.manifest.json`;
  input digests, paired metrics and gains in scorecard.
- Command: `python software/ai/vision/evaluate_dark_only_normalization.py`
- Result: PASS all12 predefined development checks. Darkened-standard mean
  2.512120 -> 0.845294 mm; >3mm maximum-key-error images86 -> 6/200.
  Standard unchanged mean0.853172 mm/tail5; appearance unchanged0.833414 mm/tail7;
  challenge mean1.032991 -> 0.995131 mm/tail10 -> 9.
  Corrected images: standard0, appearance0, challenge13, darkened200.
  No runtime preprocessing installation or localization qualification.
- Artifacts: `eval/dark_only_normalization_v0_scorecard.json`, manifest and evaluator.
- Hardware writes: 0
- Physical movements: 0
- Limitations: adaptive research selection on reused synthetic development data;
  no held-out evidence, actual camera measurements or confidence calibration.
  Passing relative criteria leaves absolute localization failures. No shared
  integration gate advanced. No batch contract change; boundary suite not triggered.
- Supersedes: none; earlier failed normalization/training evidence retained.
- Next dependency: freeze fresh-seed paired evaluation with unchanged checkpoint,
  correction and acceptance limits, plus prespecified brightness levels near the
  gate. Use unconsumed seeds beyond20M; no retuning after scoring. Confidence and
  physical calibration remain separate blockers even if evaluation passes.

### E-20260926-AI-068 â€” dark-only normalization tests

- Stage: S1
- Lane: AI
- Commit: `2ebb30f4814ec62d5a8b6fb473b790e1a0b34de6` (implementation baseline; tests committed with evidence)
- Change: checked pixel immutability, black/white behavior, threshold127/128/129,
  exact bypass, frozen provenance, seeds, metric/gate recounts and correction counts.
- Inputs/fixtures: analytic PIL images and AI-067 manifest/scorecard (800 paired cases).
- Command: `python -m pytest -q software/ai/tests/test_dark_only_normalization.py`
- Result: PASS, 3 tests; existing pytest-asyncio configuration deprecation warning.
- Artifacts: named tests and AI-067 scorecard.
- Hardware writes: 0
- Physical movements: 0
- Limitations: offline consistency, not physical accuracy or confidence evidence.
- Supersedes: none
- Next dependency: AI-067 fresh evaluation.

### E-20260926-AI-069 â€” dark-only normalization publication audit

- Stage: S1
- Lane: AI
- Commit: `2ebb30f4814ec62d5a8b6fb473b790e1a0b34de6` (implementation baseline plus result/test snapshot)
- Change: audited publication snapshot after merging latest arm passive-evidence work.
- Inputs/fixtures: repository with AI-067/068 artifacts and reviewed fixture allowlist.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS; 5730 paths, 789.0 MiB, 0 unresolved findings, 14 reviewed synthetic fixtures.
- Artifacts: audit stdout and repository snapshot.
- Hardware writes: 0
- Physical movements: 0
- Limitations: heuristic audit only; AI-041 protected-main PR publication blocker remains.
- Supersedes: none; historical failures retained.
- Next dependency: protected-branch PR/checks and AI-067 fresh evaluation.

### E-20260926-AI-070 â€” fresh synthetic normalization evaluation pass

- Stage: S1
- Lane: AI
- Commit: `2d2165850ab22357f1ec81bb8d8424360f4f9aec` (frozen evaluator/manifest before scoring)
- Change: evaluated the unchanged checkpoint and imported frozen dark-only
  normalization on fresh21M seeds. Added prespecified brightness factors0.55,
  0.60 and0.65 to probe the threshold neighborhood. No tuning after evaluation.
- Inputs/fixtures: seeds21000000..21000499, 500 groups x7 conditions =3500 images,
  46 targets/image per arm. Source/checkpoint/catalog hashes in
  `eval/normalization_fresh_v0.manifest.json`; input hashes and paired cases in
  scorecard. This seed range is now consumed and cannot be claimed fresh again.
- Command: `python software/ai/vision/evaluate_normalization_fresh.py`
- Result: PASS all21 predefined relative mean/tail/yaw checks. Darkened mean
  2.664649 -> 0.853881 mm, >3mm maximum-key-error count228 -> 9/500.
  Standard unchanged0.861101 mm/tail9; appearance unchanged0.850701 mm/tail17;
  challenge1.019997 -> 0.992334 mm/tail22 -> 18.
  Brightness0.55: mean1.456758 -> 0.924903 mm/tail79 -> 9;
  brightness0.60: mean1.087081 -> 0.995574 mm/tail28 -> 19;
  brightness0.65: mean0.996495 -> 0.994915 mm/tail15 -> 15.
  No runtime installation, confidence qualification or integration-stage advancement.
- Artifacts: `eval/normalization_fresh_v0_scorecard.json`, manifest and evaluator.
- Hardware writes: 0
- Physical movements: 0
- Limitations: unseen seeds within the same renderer, not an independent physical
  camera distribution. Seven views share each seed and are not3500 independent
  scenes. Relative non-regression criteria do not require zero failures or prove
  calibrated confidence; some targets still exceed3mm. No batch contract changes;
  shared boundary suite not triggered.
- Supersedes: none; development selection and failed studies remain retained.
- Next dependency: freeze a new uncertainty-calibration/evaluation protocol on
  unconsumed seed ranges beyond21M with this exact preprocessing, preserving
  error-coverage and full target-region containment checks. Do not install
  qualification or treat oracle target placement as runtime calibration.

### E-20260926-AI-071 â€” fresh normalization evidence tests

- Stage: S1
- Lane: AI
- Commit: `2d2165850ab22357f1ec81bb8d8424360f4f9aec` (implementation baseline; tests committed with evidence)
- Change: checked source/manifest hashes, transformation/bypass boundary behavior,
  all3500 paired cases, fresh seed coverage and independent metric/gate recounts.
- Inputs/fixtures: analytic PIL images and AI-070 manifest/scorecard.
- Command: `python -m pytest -q software/ai/tests/test_normalization_fresh.py`
- Result: PASS, 3 tests; existing pytest-asyncio configuration deprecation warning.
- Artifacts: named tests and AI-070 scorecard.
- Hardware writes: 0
- Physical movements: 0
- Limitations: consistency testing, not physical localization qualification.
- Supersedes: none
- Next dependency: AI-070 fresh uncertainty protocol.

### E-20260926-AI-072 â€” fresh normalization publication audit

- Stage: S1
- Lane: AI
- Commit: `2d2165850ab22357f1ec81bb8d8424360f4f9aec` (implementation baseline plus scorecard/test snapshot)
- Change: audited publication snapshot with latest contributor-operations main merged.
- Inputs/fixtures: repository with AI-070/071 artifacts and reviewed fixture allowlist.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS; 5736 paths, 791.0 MiB, 0 unresolved findings, 14 reviewed synthetic fixtures.
- Artifacts: audit stdout and repository snapshot.
- Hardware writes: 0
- Physical movements: 0
- Limitations: heuristic audit only; AI-041 protected-main PR publication blocker remains.
- Supersedes: none; historical failures preserved.
- Next dependency: protected-branch PR/checks and AI-070 uncertainty study.

### E-20260926-AI-073 â€” normalized uncertainty combined-criteria failure

- Stage: S1
- Lane: AI
- Commit: `097dd89aae7e0068031978117bebaaee98f8671e` (frozen implementation/manifest before calibration or scoring)
- Change: used unchanged checkpoint and dark-only normalization; fixed a99%
  nearest-rank radius from calibration seed-group maxima over46 keys x7 conditions
  before computing evaluation results. Independently scored the full disk around
  each prediction against hidden true oriented key regions.
- Inputs/fixtures: calibration seeds22000000..22000999 (1000 groups), evaluation
  seeds23000000..23000499 (500 groups), seven conditions from AI-070.
  Exact source/checkpoint/catalog hashes in `eval/normalized_uncertainty_v0.manifest.json`;
  group hashes/scores and fit counts in scorecard; both seed ranges now consumed.
- Command: `python software/ai/vision/evaluate_normalized_uncertainty.py`
- Result: FAIL combined criteria. Radius6.041821790 mm; error coverage495/500=99%
  passes95% requirement. Full-region containment65/500 groups=13% fails95%
  requirement. Individual predicted regions fitting111769/161000; group criterion
  still governs. No qualification, runtime preprocessing or model replacement.
- Artifacts: `eval/normalized_uncertainty_v0_scorecard.json`, manifest, two evaluators;
  ignored complete `results/normalized_uncertainty_v0_full.json` with study/group
  hashes retained by scorecard.
- Hardware writes: 0
- Physical movements: 0
- Limitations: global radius, same synthetic renderer and oracle geometry for
  scoring only; no calibrated per-observation confidence, actual camera transform
  or physical evidence. This seven-condition study differs from earlier three-
  condition uncertainty studies and cannot isolate normalization's effect by
  comparing their radii directly. AI-070 relative localization gains remain valid.
  No batch changes; shared boundary suite not triggered; integration gates unchanged.
- Supersedes: none; prior passes/failures retained.
- Next dependency: predeclare a bounded development-only image-conditioned
  uncertainty/abstention feasibility study on reused development groups. Preserve
  coverage and region-fit criteria; do not shrink this radius after seeing evaluation
  results. Any selected method requires new calibration/evaluation beyond23M.

### E-20260926-AI-074 â€” normalized uncertainty evidence test

- Stage: S1
- Lane: AI
- Commit: `097dd89aae7e0068031978117bebaaee98f8671e` (implementation baseline; test committed with evidence)
- Change: recounted nearest-rank calibration, empirical coverage, independent seed
  ranges, seven-condition ordering, target counts, group containment and final status.
- Inputs/fixtures: AI-073 manifest/scorecard and frozen source hashes.
- Command: `python -m pytest -q software/ai/tests/test_normalized_uncertainty_evidence.py`
- Result: PASS, 1 test; existing pytest-asyncio configuration deprecation warning.
- Artifacts: named test and AI-073 scorecard.
- Hardware writes: 0
- Physical movements: 0
- Limitations: evidence consistency only, not physical qualification.
- Supersedes: none
- Next dependency: AI-073 conditional-uncertainty feasibility study.

### E-20260926-AI-075 â€” normalized uncertainty publication audit

- Stage: S1
- Lane: AI
- Commit: `097dd89aae7e0068031978117bebaaee98f8671e` (implementation baseline plus result/test snapshot)
- Change: audited publication snapshot.
- Inputs/fixtures: repository with AI-073/074 artifacts and reviewed fixture allowlist.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS; 5741 paths, 791.7 MiB, 0 unresolved findings, 14 reviewed synthetic fixtures.
- Artifacts: audit stdout and repository snapshot.
- Hardware writes: 0
- Physical movements: 0
- Limitations: heuristic audit; AI-041 protected-main PR publication blocker remains.
- Supersedes: none; historical audit failures preserved.
- Next dependency: protected-branch PR/checks and AI-073 feasibility study.

### E-20260926-AI-076 â€” conditional disagreement abstention feasibility pass

- Stage: S1
- Lane: AI
- Commit: `89c87f25e4cd796469ea8a6c8d0a30da652cbc68` (frozen evaluator/protocol before fitting or evaluation)
- Change: measured maximum target prediction disagreement under brightness0.95/1.05
  around normalized input. Frozen bins at0.25/0.5/1mm; each radius is99th percentile
  of within-bin seed-group worst errors. Minimum50 fitting groups; abstain for
  missing radius or radius>3mm. No truth used for binning or abstention.
- Inputs/fixtures: reused pose-training14M seeds14000000..14000599 (600 fitting groups),
  reused development15M seeds15000000..15000199 (200 groups), seven conditions;
  4200 fitting/1400 evaluation images, three model passes per image, 46 targets.
  Exact source/checkpoint/catalog hashes in `eval/disagreement_uncertainty_v0.manifest.json`;
  per-case input hashes, predictions/truth/errors and decisions in report.
- Command: `python software/ai/vision/evaluate_disagreement_uncertainty.py`
- Result: PASS development feasibility criteria. Bin radii2.884125/3.565022/
  4.873882/7.330715 mm; fitting supports561/563/371/61 seed groups (bins can share
  a seed across conditions). Only first bin admitted. Acceptance20%..73.5%
  per condition; accepted-image coverage95.08%..98.96%, containment96.72%..100%.
  Among187 groups with accepted images, coverage180/187=96.26%, containment
  183/187=97.86%. Abstained images are excluded from success counts and availability
  is reported separately. No qualification or runtime installation.
- Artifacts: `eval/disagreement_uncertainty_v0_report.json`, manifest and evaluator.
- Hardware writes: 0
- Physical movements: 0
- Limitations: fitting seeds overlap pose training and development groups are reused;
  optimistic method selection, not calibrated deployment confidence or fresh evidence.
  Stable predictions may share bias. Oracle key regions are scoring-only. No batch
  contract changes; boundary suite not triggered; shared integration status unchanged.
- Supersedes: none; global-radius failure AI-073 remains retained.
- Next dependency: freeze this exact binning, perturbation, abstention and criteria
  on fresh calibration24M and evaluation25M seed ranges before scoring. Refit radii
  from calibration only; report acceptance, accepted-image and accepted-group
  coverage/containment without treating abstention as success. No runtime qualification.

### E-20260926-AI-077 â€” disagreement feasibility evidence tests

- Stage: S1
- Lane: AI
- Commit: `89c87f25e4cd796469ea8a6c8d0a30da652cbc68` (implementation baseline; tests committed with evidence)
- Change: checked bin boundaries, frozen hashes, fitting supports/quantiles,
  abstention/null outcomes, per-condition metrics and nonvacuous group criteria.
- Inputs/fixtures: analytic bin edges and complete AI-076 report/manifest.
- Command: `python -m pytest -q software/ai/tests/test_disagreement_uncertainty.py`
- Result: PASS, 3 tests; existing pytest-asyncio configuration deprecation warning.
- Artifacts: named tests and AI-076 report.
- Hardware writes: 0
- Physical movements: 0
- Limitations: offline consistency only, not physical qualification.
- Supersedes: none
- Next dependency: AI-076 fresh study.

### E-20260926-AI-078 â€” disagreement feasibility publication audit

- Stage: S1
- Lane: AI
- Commit: `89c87f25e4cd796469ea8a6c8d0a30da652cbc68` (implementation baseline plus report/test snapshot)
- Change: audited publication snapshot.
- Inputs/fixtures: repository with AI-076/077 artifacts and reviewed fixture allowlist.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS; 5745 paths, 794.6 MiB, 0 unresolved findings, 14 reviewed synthetic fixtures.
- Artifacts: audit stdout and repository snapshot.
- Hardware writes: 0
- Physical movements: 0
- Limitations: heuristic audit only; AI-041 protected-main PR publication blocker remains.
- Supersedes: none; historical failures retained.
- Next dependency: protected-branch PR/checks and AI-076 fresh calibration/evaluation.

### E-20260926-ARM-026 â€” r96 command-surface compatibility decision

- Stage: S4
- Lane: ARM
- Change: added a pure, fail-closed compatibility boundary that requires the
  exact passively observed application to expose a reviewed generic dispatcher,
  `T=102` commands, `T=105` requests, `T=1051` responses, runtime app-hash
  attestation, and independent approval. Added closed evidence/report schemas,
  public exports, tests, an offline assessor, and operator documentation.
- Inputs: ignored passive evidence from ARM-024; exact r96 staged source,
  compiled app and ELF; retained compile review; predecessor image hash.
- Offline assessment: `BLOCKED`. The installed app hash matches the reviewed
  r96 hash, but blockers are `RUNTIME_APP_HASH_NOT_ATTESTED`,
  `GENERIC_COMMAND_DISPATCH_ABSENT`, `T102_COMMAND_UNAVAILABLE`,
  `T105_FEEDBACK_REQUEST_UNAVAILABLE`,
  `T1051_FEEDBACK_RESPONSE_UNAVAILABLE`, and
  `INDEPENDENT_REVIEW_INCOMPLETE`.
- Local artifact: ignored
  `software/runs/installed-controller-qualification/r96-surface-compatibility-20260926.json`;
  report hash
  `fdcd559ddf407e67082cb3c80f410ef35b3a3163e21264c677b2a17ee2184706`;
  surface evidence hash
  `88315efd7167c1059196504db9a10f20afe0e6f6fd49e52169695a4862092643`;
  file hash
  `4af82bf96e54daa1dc9e790f76d2d6ceb728fb59ed3ebb6504ff712d80dc880e`.
- Command: `$env:PYTHONPATH='software/src;software/scripts'; python software/scripts/assess_r96_controller_surface.py --passive-evidence software/runs/installed-controller-qualification/r96-passive-20260926.json --output software/runs/installed-controller-qualification/r96-surface-compatibility-20260926.json`.
- Test result: targeted compatibility, passive-evidence, and qualification suite
  PASS, 34 tests. Every missing requirement fails closed; schemas reject
  mutation into execution authority.
- Hardware writes: 0
- Physical movements: 0
- Limitations: this is an offline compatibility decision, not independent r96
  evidence approval and not qualification of a new runtime. No transport,
  execution, or physical authority is created.
- Supersedes: ARM-024's proposed path of closing r96's protocol blockers. r96
  remains valid as historical passive and diagnostic evidence, but is
  structurally incompatible with the production command surface.
- Next dependency: design a separate safe-idle, sole-writer generic runtime
  candidate with bounded T=102/T=105/T=1051 handling and runtime attestation;
  independently review it offline before proposing installation or startup.

### E-20260926-ARM-027 â€” command-surface integration verification

- Stage: S4
- Lane: ARM
- Change: verified the r96 compatibility decision across the shared AI/arm,
  zero-write, sole-writer, passive-evidence, qualification, schema, and snapshot
  boundaries, then audited the complete repository snapshot.
- Commands: `python scripts/ci/check_docs.py`; ARM-021's integrated pytest
  selection with `test_installed_controller_surface_compatibility_v1.py` added;
  `python scripts/audit_github_snapshot.py`; `git diff --check`.
- Result: documentation PASS for 21 maintained documents and two SVG assets;
  pytest PASS, 263 tests in 38.93 seconds; audit PASS, 5,696 paths, 903.6 MiB,
  zero unresolved findings and 14 reviewed synthetic fixtures; diff check PASS.
- Hardware writes: 0
- Physical movements: 0
- Limitations: integrated software verification does not qualify a replacement
  controller runtime and does not authorize installation, startup, transport,
  execution, or physical movement.
- Supersedes: ARM-025 only for current integrated test, document, and audit
  counts. It does not alter ARM-024's observation or ARM-026's blocked result.
- Next dependency: implement and independently review the separate production
  runtime contract offline, retaining r96 unchanged as diagnostic history.

### E-20260926-AI-079 â€” fresh conditional uncertainty availability failure

- Stage: S1
- Lane: AI
- Commit: `081e15ea084a381e0c2cb22ff9a2c7f7fb7121cf` (frozen protocol before calibration/evaluation)
- Change: preserved checkpoint, normalization, perturbations0.95/1.05, bins
  0.25/0.5/1mm, nearest-rank99% group-error radius, minimum50 support and3mm
  admission cap. Refit radii on fresh calibration only before evaluation.
- Inputs/fixtures: calibration24000000..24000999 (1000 groups/7000 images),
  evaluation25000000..25000499 (500 groups/3500 images), seven conditions,
  three passes/image,46 targets. Both ranges are now consumed. Exact hashes in
  `eval/disagreement_fresh_v0.manifest.json`; full cases/input hashes in report.
- Command: `python software/ai/vision/evaluate_disagreement_fresh.py`
- Result: FAIL. Bin radii4.289480/5.604864/7.043847/13.453540 mm, with supports
  924/910/640/120 calibration seed groups (groups may occur in multiple bins).
  All radii exceed3mm, so0/3500 images and0/500 groups accepted; acceptance0%
  in every condition fails the10% minimum. Coverage and containment are null,
  not successful or zero-error claims. Earlier optimistic development pass did
  not generalize to fresh calibration; no thresholds relaxed or model promoted.
- Artifacts: `eval/disagreement_fresh_v0_report.json`, manifest and evaluator.
- Hardware writes: 0
- Physical movements: 0
- Limitations: fresh seeds within the same renderer; no physical capture or
  deployment qualification. Stable perturbation predictions can share position
  bias; this result does not establish its cause. The study does not invalidate
  the separately measured normalization improvement. No contract changes;
  boundary suite not triggered; arm/integration stages unchanged.
- Supersedes: none; AI-076 development evidence retained with its original caveat.
- Next dependency: diagnose low-disagreement/high-error cases in retained24M
  calibration evidence (position/yaw, condition and paired images) before another
  method. Do not tune against25M evaluation or reduce radii after seeing failure;
  any revised method needs new independent calibration/evaluation beyond25M.

### E-20260926-AI-080 â€” fresh conditional uncertainty evidence tests

- Stage: S1
- Lane: AI
- Commit: `081e15ea084a381e0c2cb22ff9a2c7f7fb7121cf` (implementation baseline; tests committed with evidence)
- Change: verified bins, frozen provenance, calibration supports/quantiles,
  abstention/null accounting, group gates and exact disjoint fresh seed ranges.
- Inputs/fixtures: analytic bin values and AI-079 full report/manifest.
- Command: `python -m pytest -q software/ai/tests/test_disagreement_fresh.py`
- Result: PASS,4 tests; existing pytest-asyncio configuration deprecation warning.
- Artifacts: named tests and AI-079 report.
- Hardware writes: 0
- Physical movements: 0
- Limitations: evidence consistency only; failing model study remains failed.
- Supersedes: none
- Next dependency: AI-079 retained-calibration diagnostic.

### E-20260926-AI-081 â€” fresh conditional uncertainty publication audit

- Stage: S1
- Lane: AI
- Commit: `081e15ea084a381e0c2cb22ff9a2c7f7fb7121cf` (implementation baseline plus report/test snapshot)
- Change: audited publication snapshot.
- Inputs/fixtures: repository with AI-079/080 artifacts and reviewed fixture allowlist.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS;5755 paths,800.3 MiB,0 unresolved findings,14 reviewed synthetic fixtures.
- Artifacts: audit stdout and repository snapshot.
- Hardware writes: 0
- Physical movements: 0
- Limitations: heuristic audit only; AI-041 protected-main PR blocker remains.
- Supersedes: none; historical failures retained.
- Next dependency: protected-branch PR/checks and AI-079 diagnostic.

### E-20260926-AI-082 â€” stable-but-inaccurate calibration diagnosis

- Stage: S1
- Lane: AI
- Commit: `5ca137b762d9af787825e100f56cad068f7456d4` (frozen source/protocol before analysis)
- Change: analyzed only retained24M fitting cases from AI-079; selected bin0
  (disagreement<=0.25mm) with error>3mm. Summarized condition/position/yaw errors
  and rendered the twelve worst distinct seed representatives for inspection.
- Inputs/fixtures: AI-079 report, specifically7000 calibration cases; source,
  renderer and normalization hashes in `eval/stable_errors_v0.manifest.json`.
  The source container also holds25M records, but no25M metrics or cases are used.
- Command: `python software/ai/vision/diagnose_stable_errors.py`
- Result: PASS diagnostic; uncertainty method remains failed. Of3263 low-
  disagreement images,70 across35 seed groups exceed3mm. Counts by standard,
  appearance,challenge,darkened,brightness0.55/0.60/0.65:12/13/13/14/8/6/4.
  Worst selected seed24000868: maximum key error11.67mm, center error11.39mm,
  yaw0.35deg, disagreement0.17mm (rounded). Image inspection shows arm-like
  obstructions and ruler lines in selected examples; this does not prove cause.
- Artifacts: `eval/stable_errors_v0_report.json`, manifest, diagnostic;
  ignored reproducible `results/stable_errors_v0/stable_errors.png`, visually
  inspected, with image hash and selected input hashes in report.
- Hardware writes: 0
- Physical movements: 0
- Limitations: post-hoc calibration-only diagnosis, correlated conditions and
  hidden truth for scoring/selection only. No new confidence rule, model update
  or qualification. No batch change; boundary suite not triggered.
- Supersedes: none; AI-079 failure retained.
- Next dependency: predeclare a development-only spatial-shift consistency
  diagnostic on reused14M/15M data, testing whether inverse-corrected predictions
  expose errors missed by brightness perturbation. Any image-to-board correction
  is limited to the known synthetic projection and is not runtime calibration;
  no tuning against25M and fresh future calibration/evaluation remains required.

### E-20260926-AI-083 â€” stable-error diagnostic evidence test

- Stage: S1
- Lane: AI
- Commit: `5ca137b762d9af787825e100f56cad068f7456d4` (implementation baseline; test committed with report)
- Change: checked frozen inputs, calibration-only seed selection, condition counts,
  position/yaw calculations and twelve distinct representatives.
- Inputs/fixtures: AI-082 report/manifest and AI-079 retained calibration cases.
- Command: `python -m pytest -q software/ai/tests/test_stable_errors.py`
- Result: PASS,1 test; existing pytest-asyncio configuration deprecation warning.
- Artifacts: named test and AI-082 report.
- Hardware writes: 0
- Physical movements: 0
- Limitations: consistency only, not physical accuracy or causal attribution.
- Supersedes: none
- Next dependency: AI-082 spatial consistency diagnostic.

### E-20260926-AI-084 â€” stable-error diagnosis publication audit

- Stage: S1
- Lane: AI
- Commit: `5ca137b762d9af787825e100f56cad068f7456d4` (implementation baseline plus report/test snapshot)
- Change: audited publication snapshot.
- Inputs/fixtures: repository with AI-082/083 artifacts and reviewed fixture allowlist.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS;5761 paths,800.3 MiB,0 unresolved findings,14 reviewed synthetic fixtures.
- Artifacts: audit stdout and repository snapshot.
- Hardware writes: 0
- Physical movements: 0
- Limitations: heuristic audit; AI-041 protected-main PR blocker remains.
- Supersedes: none; historical failures retained.
- Next dependency: protected-branch PR/checks and AI-082 diagnostic.

### E-20260926-AI-085 â€” spatial consistency availability failure

- Stage: S1
- Lane: AI
- Commit: `bca1428141590564a805089399982723f7552c82` (frozen protocol before scoring)
- Change: replaced brightness perturbations with four cardinal one-pixel shifts,
  edge replication and inverse correction using the fixed synthetic610x457mm
  board projection at128x96. Original prediction remains the estimator; disagreement
  alone selects a radius. Same bins, support,99% quantile,3mm cap and coverage/
  containment/availability criteria as development brightness study.
- Inputs/fixtures: reused14M600 fitting and15M200 development seed groups,
  seven conditions,4200/1400 images, five passes/image,46 targets. Source/model/
  catalog hashes in `eval/spatial_uncertainty_v0.manifest.json`; full cases in report.
- Command: `python software/ai/vision/evaluate_spatial_uncertainty.py`
- Result: FAIL availability. Bin supports1/167/500/462; radii null/2.155254/
  3.533526/4.873882mm. Only second bin admitted. Accepted counts per200 images:
  standard11,appearance43,challenge12,darkened15,brightness0.55:9,0.60:7,0.65:6.
  Six of seven conditions fail10% availability. Accepted-group coverage59/61=
  96.72%, containment61/61=100%; these do not override failed availability.
  Per-condition accepted coverage minimum41/43=95.35%; containment100%.
  No new qualification or runtime behavior installed.
- Artifacts: `eval/spatial_uncertainty_v0_report.json`, manifest and evaluator.
- Hardware writes: 0
- Physical movements: 0
- Limitations: pose-training overlap in fitting and reused development selection;
  small accepted sample, correlated views, edge padding artifacts possible.
  Inverse transform is synthetic-only, not measured runtime calibration. No
  fresh evaluation consumed or batch changed; boundary suite not triggered.
- Supersedes: none; earlier failures retained, integration status unchanged.
- Next dependency: freeze a development comparison of the mean inverse-corrected
  spatial predictions versus the unchanged base estimate. Test localization
  improvement directly with per-condition mean/tail/yaw regression limits before
  revisiting uncertainty; do not lower availability or expand the3mm cap to pass.

### E-20260926-AI-086 â€” spatial uncertainty evidence and transform tests

- Stage: S1
- Lane: AI
- Commit: `bca1428141590564a805089399982723f7552c82` (implementation baseline; tests committed with evidence)
- Change: verified shift direction, edge replication, immutability, inverse
  synthetic coordinate correction, hashes, radius/support and abstention metrics.
- Inputs/fixtures: analytic image/pose and AI-085 manifest/report.
- Command: `python -m pytest -q software/ai/tests/test_spatial_uncertainty.py`
- Result: PASS,4 tests; existing pytest-asyncio configuration deprecation warning.
- Artifacts: named tests and AI-085 report.
- Hardware writes: 0
- Physical movements: 0
- Limitations: offline consistency only; model study remains failed.
- Supersedes: none
- Next dependency: AI-085 estimator comparison.

### E-20260926-AI-087 â€” spatial uncertainty publication audit

- Stage: S1
- Lane: AI
- Commit: `bca1428141590564a805089399982723f7552c82` (implementation baseline plus report/test snapshot)
- Change: audited publication snapshot.
- Inputs/fixtures: repository with AI-085/086 artifacts and reviewed fixture allowlist.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS;5765 paths,803.3 MiB,0 unresolved findings,14 reviewed synthetic fixtures.
- Artifacts: audit stdout and repository snapshot.
- Hardware writes: 0
- Physical movements: 0
- Limitations: heuristic audit; AI-041 protected-main PR publication blocker remains.
- Supersedes: none; historical audit failures retained.
- Next dependency: protected-branch PR/checks and AI-085 estimator comparison.

### E-20260926-ARM-028 â€” production runtime executable contract

- Stage: S4
- Lane: ARM
- Change: implemented a zero-I/O executable specification for the separate
  production controller runtime. The manifest binds candidate app, protocol,
  joint mapping, configuration epoch, controller session and encoding profile.
  The state machine starts safe-idle, permits one writer, accepts only exact
  deterministic T=102 frames in strict sequence and time bounds, rehearses exact
  T=105/T=1051 feedback, and terminally locks on ambiguity or restart.
- Safety properties: zero startup commands; zero transport opens; zero hardware
  writes; no automatic retry; no replay; no authority. Foreign writers,
  mismatched session/epoch/profile, stale frames, sequence gaps or duplicates,
  noncanonical messages, missing feedback joints and wrong response types all
  fail closed.
- Tests: `software/tests/unit/test_production_controller_runtime_contract_v1.py`
  PASS, 18 tests, including concurrent writer claims and schema authority
  mutation rejection.
- Artifacts:
  `software/src/rocell/application/production_controller_runtime_contract_v1.py`,
  two `production_controller_runtime_*_v1.schema.json` schemas, public exports,
  tests, and `software/docs/PRODUCTION_CONTROLLER_RUNTIME_CONTRACT.md`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: this is the executable host-side specification, not controller
  firmware, a compiled app, installed qualification, or transport authority.
- Supersedes: ARM-027's next dependency only; r96 remains unchanged and blocked
  for production binding.
- Next dependency: implement a separate firmware candidate against this
  contract, compile reproducibly, and independently review source and linked
  image before any installation proposal.

### E-20260926-ARM-029 â€” production runtime contract integration verification

- Stage: S4
- Lane: ARM
- Change: verified the production runtime contract across shared AI/arm ingress,
  measured envelopes, zero-write encoding, sole-writer lifecycle, installed
  qualification, installed surface compatibility, schemas, and snapshot audit.
- Commands: `python scripts/ci/check_docs.py`; integrated ARM-027 pytest
  selection with `test_production_controller_runtime_contract_v1.py` added;
  `python scripts/audit_github_snapshot.py`; `git diff --check`.
- Result: documentation PASS for 22 maintained documents and two SVG assets;
  focused controller boundary PASS, 77 tests; integrated PASS, 281 tests in
  40.46 seconds; audit PASS, 5,703 paths, 903.7 MiB, zero unresolved findings
  and 14 reviewed synthetic fixtures; diff check PASS.
- Hardware writes: 0
- Physical movements: 0
- Limitations: green contract tests prove deterministic software behavior only;
  they do not prove firmware implementation, timing, servo response, installed
  identity, or physical movement safety.
- Supersedes: ARM-028 only for current integrated verification counts.
- Next dependency: build the firmware-side candidate offline, retaining exact
  manifest and protocol semantics, then conduct independent source/image review.


### E-20260926-AI-088 â€” spatial averaging report serialization failure

- Stage: S1
- Lane: AI
- Commit: `fcac5ddd22f398f2b9c4237fdf1c0a455f7b80c5`
- Change: frozen paired spatial-averaging development experiment.
- Inputs/fixtures:15M200 groups x7 conditions; exact hashes in spatial-average manifest.
- Command: `python software/ai/vision/evaluate_spatial_average.py`
- Result: FAILED exit1 at JSON serialization: NumPy bool_ overall comparison cannot serialize. No scorecard written; no result accepted.
- Artifacts: frozen source/manifest and retained tool traceback.
- Hardware writes:0
- Physical movements:0
- Limitations: no usable result. Inspection also identifies circular-mean yaw wrap requiring wrapped angle-error scoring.
- Supersedes:none
- Next dependency: freeze native-bool serialization and wrapped yaw-error correction before rerunning; preserve this failure.

### E-20260926-AI-089 â€” spatial averaging development tail failure

- Stage:S1
- Lane:AI
- Commit:`659ba427a7964a43869296ab027eea5ea4c3fda3` (corrected source/manifest frozen before rerun)
- Change: compared equal mean inverse-corrected center and circular yaw across
  base plus four one-pixel shifted inputs against unchanged normalized base.
  Wrapped yaw error scoring handles pi boundary. No retraining or tuned weights.
- Inputs/fixtures: reused15M200 groups x7 conditions,1400 images,46 targets,
  five passes/image; exact source/checkpoint/catalog hashes in spatial-average
  manifest; cases and input digests in scorecard.
- Command:`python software/ai/vision/evaluate_spatial_average.py`
- Result:FAIL combined criteria. Overall mean0.910859 -> 0.864746mm (about5.1%
  reduction); mean error and yaw-p95 improve in every condition. Tail count
  brightness0.55 rises6 -> 7/200, brightness0.60 rises10 -> 11/200, failing
  no-tail-regression limits. Other tails:standard5 -> 4,appearance7 -> 7,
  challenge9 -> 9,darkened6 -> 6,brightness0.65:8 -> 8.20/22 checks pass;
  failed checks cannot be overridden by aggregate improvement. No promotion.
- Artifacts:`eval/spatial_average_v0_scorecard.json`, manifest and evaluator.
- Hardware writes:0
- Physical movements:0
- Limitations: reused development selection, five model passes, synthetic inverse
  projection only. Does not establish fresh generalization or runtime calibration.
  No batch changes; boundary suite not triggered; integration status unchanged.
- Supersedes:none; AI-088 failed execution retained.
- Next dependency: predeclare a robust median aggregation comparison on development
  data with unchanged per-condition limits; inspect tail effects without tuning
  against25M. Any accepted estimator requires new independent evaluation and
  uncertainty calibration; do not install this mean estimator.

### E-20260926-AI-090 â€” spatial averaging evidence tests

- Stage:S1
- Lane:AI
- Commit:`659ba427a7964a43869296ab027eea5ea4c3fda3` (implementation baseline; tests committed with evidence)
- Change: tested circular mean across pi and recounted frozen provenance,
  seeds, means, tail counts, yaw ranges and condition gates.
- Inputs/fixtures: analytic poses and AI-089 manifest/scorecard.
- Command:`python -m pytest -q software/ai/tests/test_spatial_average.py`
- Result:PASS,2 tests; existing pytest-asyncio configuration deprecation warning.
- Artifacts:named tests and AI-089 scorecard.
- Hardware writes:0
- Physical movements:0
- Limitations: offline evidence correctness only; model acceptance still fails.
- Supersedes:none
- Next dependency:AI-089 median comparison.

### E-20260926-AI-091 â€” spatial averaging publication audit

- Stage:S1
- Lane:AI
- Commit:`659ba427a7964a43869296ab027eea5ea4c3fda3` (implementation baseline plus scorecard/test snapshot)
- Change:audited publication snapshot after latest dependency-review main merge.
- Inputs/fixtures:repository with AI-089/090 artifacts and reviewed fixture allowlist.
- Command:`python scripts/audit_github_snapshot.py`
- Result:PASS;5774 paths,804.1 MiB,0 unresolved findings,14 reviewed synthetic fixtures.
- Artifacts:audit stdout and repository snapshot.
- Hardware writes:0
- Physical movements:0
- Limitations:heuristic audit; AI-041 protected-main PR blocker remains.
- Supersedes:none; historical failures retained.
- Next dependency:protected-branch PR/checks and AI-089 median comparison.

### E-20260926-AI-092 â€” spatial median development pass

- Stage: S1
- Lane: AI
- Commit: `1c0b7af55ef624172505aa2d9547ebe602892cd7` (frozen evaluator/manifest before scoring)
- Change: coordinate-wise median of five inverse-corrected centers and median
  wrapped yaw offsets relative to base. Same normalized base control, shifts,
  checkpoint and per-condition mean/tail/yaw limits as AI-089; no tuned weights.
- Inputs/fixtures: reused15M200 groups x7 conditions=1400 images,46 targets,
  five passes/image. Exact source/checkpoint/catalog hashes in
  `eval/spatial_median_v0.manifest.json`; paired cases and input hashes in scorecard.
- Command: `python software/ai/vision/evaluate_spatial_median.py`
- Result: PASS all22 development checks. Overall mean0.910859 -> 0.865577mm
  (about4.97% reduction); every condition mean and yaw-p95 improve. >3mm counts
  per200 images:standard5 -> 4,appearance7 -> 7,challenge9 -> 8,darkened6 -> 5,
  brightness0.55:6 -> 5,0.60:10 -> 10,0.65:8 -> 6. No runtime promotion.
- Artifacts: `eval/spatial_median_v0_scorecard.json`, manifest and evaluator.
- Hardware writes: 0
- Physical movements: 0
- Limitations: adaptively selected using reused development data; five passes
  increase compute; inverse image-to-board shift uses synthetic projection, not
  measured camera calibration. Absolute tail errors remain. No batch changes;
  shared boundary tests not triggered, integration status unchanged.
- Supersedes: none; mean-aggregation failure AI-089 remains retained.
- Next dependency: freeze identical estimator and acceptance gates on unconsumed
 26M500 seed groups before scoring. No tuning after evaluation; separate fresh
  uncertainty study and physical calibration remain required even if it passes.

### E-20260926-AI-093 â€” spatial median evidence tests

- Stage: S1
- Lane: AI
- Commit: `1c0b7af55ef624172505aa2d9547ebe602892cd7` (implementation baseline; tests committed with evidence)
- Change: tested pi-boundary yaw, resistance to a single analytic outlier, frozen
  provenance, seed order and per-condition metric/gate recounts.
- Inputs/fixtures: analytic poses and AI-092 manifest/scorecard.
- Command: `python -m pytest -q software/ai/tests/test_spatial_median.py`
- Result: PASS,3 tests; existing pytest-asyncio configuration deprecation warning.
- Artifacts: named tests and AI-092 scorecard.
- Hardware writes: 0
- Physical movements: 0
- Limitations: offline consistency, not physical localization qualification.
- Supersedes: none
- Next dependency: AI-092 fresh evaluation.

### E-20260926-AI-094 â€” spatial median publication audit

- Stage: S1
- Lane: AI
- Commit: `1c0b7af55ef624172505aa2d9547ebe602892cd7` (implementation baseline plus result/test snapshot)
- Change: audited publication snapshot.
- Inputs/fixtures: repository with AI-092/093 artifacts and reviewed fixture allowlist.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS;5778 paths,804.9 MiB,0 unresolved findings,14 reviewed synthetic fixtures.
- Artifacts: audit stdout and repository snapshot.
- Hardware writes: 0
- Physical movements: 0
- Limitations: heuristic audit; AI-041 protected-main PR publication blocker remains.
- Supersedes: none; historical failures retained.
- Next dependency: protected-branch PR/checks and AI-092 evaluation.

### E-20260926-AI-095 â€” fresh spatial median tail failure

- Stage: S1
- Lane: AI
- Commit: `5b6d0bcdfd2cc2e54591aaccc793f3b7534de7a9` (frozen evaluator/manifest before scoring)
- Change: imported unchanged median estimator, shifts, normalization and checkpoint;
  applied the same overall and per-condition acceptance limits on fresh26M seeds.
- Inputs/fixtures:26000000..26000499,500 groups x7 conditions=3500 images,
 46 targets/image, five passes/image. Exact source/checkpoint/catalog hashes in
 `eval/spatial_median_fresh_v0.manifest.json`; paired cases/input digests in scorecard.
 The26M range is now consumed and cannot be reused as fresh evidence.
- Command: `python software/ai/vision/evaluate_spatial_median_fresh.py`
- Result: FAIL,20/22 checks pass. Mean and yaw-p95 improve in every condition,
  but appearance-shift >3mm count14 -> 16/500 and brightness0.65 count14 -> 15/500
  violate tail limits. Other counts:standard12 -> 9,challenge16 -> 12,
  darkened11 -> 9,brightness0.55:14 -> 12,0.60:15 -> 13. No promotion.
- Artifacts: `eval/spatial_median_fresh_v0_scorecard.json`, manifest and evaluator.
- Hardware writes:0
- Physical movements:0
- Limitations: same synthetic renderer, correlated condition views; unseen seeds
  do not establish physical camera accuracy. Lower mean does not override failures.
  Synthetic projection is not runtime calibration. No batch changes; boundary
  suite not triggered; shared integration status unchanged.
- Supersedes:none; AI-092 development pass retained alongside failed fresh result.
- Next dependency: freeze a development-only landmark-localization baseline with
  explicit keyboard geometry outputs and visibility/occlusion evaluation, comparing
  against current normalized pose baseline. Stop post-hoc aggregation tuning on26M;
  future selected models require independent data beyond26M and confidence work.

### E-20260926-AI-096 â€” fresh spatial median evidence tests

- Stage:S1
- Lane:AI
- Commit:`5b6d0bcdfd2cc2e54591aaccc793f3b7534de7a9` (implementation baseline; tests committed with evidence)
- Change: checked circular median behavior, analytic outlier resistance, frozen
  provenance, exact26M seed coverage and metric/gate recounts.
- Inputs/fixtures:analytic poses and AI-095 manifest/scorecard.
- Command:`python -m pytest -q software/ai/tests/test_spatial_median_fresh.py`
- Result:PASS,3 tests; existing pytest-asyncio configuration deprecation warning.
- Artifacts:named tests and AI-095 scorecard.
- Hardware writes:0
- Physical movements:0
- Limitations:offline consistency only; model acceptance still fails.
- Supersedes:none
- Next dependency:AI-095 landmark baseline.

### E-20260926-AI-097 â€” fresh median publication audit

- Stage:S1
- Lane:AI
- Commit:`5b6d0bcdfd2cc2e54591aaccc793f3b7534de7a9` (implementation baseline plus result/test snapshot)
- Change:audited publication snapshot.
- Inputs/fixtures:repository with AI-095/096 artifacts and reviewed fixture allowlist.
- Command:`python scripts/audit_github_snapshot.py`
- Result:PASS;5784 paths,807.0 MiB,0 unresolved findings,14 reviewed synthetic fixtures.
- Artifacts:audit stdout and repository snapshot.
- Hardware writes:0
- Physical movements:0
- Limitations:heuristic audit; AI-041 protected-main PR publication blocker remains.
- Supersedes:none; historical failures retained.
- Next dependency:protected-branch PR/checks and AI-095 landmark baseline.

### E-20260926-AI-098 â€” landmark architecture and label foundation

- Stage:S1
- Lane:AI
- Commit:`947f67df03713473f5af55d67819790dbc910612` (frozen renderer/model/audit before scoring)
- Change: added an isolated instrumented renderer retaining original RGB output,
  four ordered semantic case corners and geometric foreground-mask fractions in
  radius2px disks. Added a61032-parameter CNN with four48x64 heatmaps and four
  visibility logits from256x192 input, plus differentiable pixel-coordinate decoding.
- Inputs/fixtures:15M200 reused groups x standard/appearance domains=400 images,
 1600 corners; exact sources in `eval/landmark_labels_v0.manifest.json`; image,
 mask hashes and labels retained in report. No source photographs consumed.
- Command:`python software/ai/vision/evaluate_landmark_labels.py`
- Result:PASS foundation audit,0 RGB/pose mismatches across400 images.1564 corners
 fully unoccluded,36 partially occluded,0 fully occluded. Architecture exists but
 is UNTRAINED; no accuracy, calibrated visibility or performance claim. Label
 population is insufficient for fully occluded visibility behavior.
- Artifacts:`vision/landmark_renderer.py`, `vision/landmark_model.py`, evaluator,
 manifest and `eval/landmark_labels_v0_report.json`.
- Hardware writes:0
- Physical movements:0
- Limitations: synthetic case geometry only; mask covers drawn foreground arm,
 ruler and reflective line, not perceptual visibility under blur/contrast.
 Photo-texture and challenge-mask labeling unsupported. Existing hashed renderer
 unchanged; instrumented copy requires continued parity checks. No runtime or
 batch contract change; boundary suite not triggered; integration gates unchanged.
- Supersedes:none; existing pose studies remain retained.
- Next dependency:add controlled partial/full corner occlusions with explicit
 labels and held-out occluder variants; then freeze training/loss/selection and
 per-condition comparison against normalized pose baseline before training.
 Visibility logits must not substitute for localization uncertainty.

### E-20260926-AI-099 â€” landmark foundation tests

- Stage:S1
- Lane:AI
- Commit:`947f67df03713473f5af55d67819790dbc910612` (implementation baseline; tests committed with evidence)
- Change: verified source hashes, corner ordering/centroid/visibility bounds,
 output shapes, finite gradients, and uniform/peaked heatmap coordinate decoding.
- Inputs/fixtures:AI-098 report and analytic Torch image/heatmap tensors.
- Command:`python -m pytest -q software/ai/tests/test_landmark_foundation.py`
- Result:PASS,2 tests; existing pytest-asyncio configuration deprecation warning.
- Artifacts:named tests and AI-098 report.
- Hardware writes:0
- Physical movements:0
- Limitations:implementation checks only; architecture remains untrained.
- Supersedes:none
- Next dependency:AI-098 occlusion data and frozen training protocol.

### E-20260926-AI-100 â€” landmark foundation publication audit

- Stage:S1
- Lane:AI
- Commit:`947f67df03713473f5af55d67819790dbc910612` (implementation baseline plus report/test snapshot)
- Change:audited publication snapshot.
- Inputs/fixtures:repository with AI-098/099 artifacts and reviewed fixture allowlist.
- Command:`python scripts/audit_github_snapshot.py`
- Result:PASS;5790 paths,807.6 MiB,0 unresolved findings,14 reviewed synthetic fixtures.
- Artifacts:audit stdout and repository snapshot.
- Hardware writes:0
- Physical movements:0
- Limitations:heuristic audit; AI-041 protected-main PR publication blocker remains.
- Supersedes:none; historical failures retained.
- Next dependency:protected-branch PR/checks and AI-098 data foundation.

### E-20260926-AI-101 â€” controlled occlusions and first landmark training failure

- Stage: S1
- Lane: AI
- Commit: `99dae837d1f6de5caec9ec42c62bcbc4a6a9f006` (frozen data/training/loss/selection protocol before execution)
- Change: added controlled partial/full corner masks; trained61032-parameter
  heatmap/visibility model from random initialization for8 epochs. Rectangle
  occluders for training, ellipse variants for development. Localization loss
  weights Gaussian heatmap labels by visible fraction; visibility uses soft BCE.
- Inputs/fixtures: reused14M600 groups x4 conditions=2400 training images and
 15M200 groups x4=800 development images; standard,appearance,partial,full.
 Exact source/catalog/baseline hashes in `train/landmark_v0_plan.json`; pixel,
 output-checkpoint hashes, histories and800 cases in scorecard.
- Command: `python software/ai/train/train_landmarks.py`
- Result: FAIL comparison. Epoch8 selected by minimum development loss5.353226.
 Landmark mean key error standard23.993929mm,appearance30.851021mm,
 partial27.048675mm,full24.756265mm versus baseline0.853231/0.833362/
 1.026278/1.228562mm. Every landmark image exceeds3mm. Visibility head falsely
 marks201/201 fully occluded development corners visible at0.5 threshold.
 Data/training run completed; model unsuitable for promotion or confidence use.
- Artifacts: `vision/landmark_occlusions.py`, training runner/plan,
 `eval/landmark_v0_scorecard.json`, ignored `results/landmark_v0/model.pt`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: initial short-budget model versus pretrained pose checkpoint,
 unequal training history; not evidence against landmark architectures generally.
 Unconditional pose uses all four predicted corners, including occluded corners;
 diagnostic only, not admission. Baseline uses same normalized image downsampled
 to128x96, not identical preprocessing order to earlier studies. Reused seeds,
 new occluder shapes, no fresh physical/generalization claim. No batch changes;
 boundary suite not triggered; no shared stage advanced.
- Supersedes: none; all earlier evidence retained.
- Next dependency: frozen diagnostic of peak versus soft-argmax corner errors,
 heatmap mass spread and visibility-label imbalance on retained development
 images before changing architecture/loss. Preserve this checkpoint and failure;
 do not treat visibility logits as localization confidence.

### E-20260926-AI-102 â€” occlusion and landmark pipeline tests

- Stage: S1
- Lane: AI
- Commit: `99dae837d1f6de5caec9ec42c62bcbc4a6a9f006` (implementation baseline; tests committed with results)
- Change: checked control-image preservation, full/partial masks, unchanged pose,
 monotonic occlusion masks, source hashes, selected epoch, metrics and false visibility.
- Inputs/fixtures: analytic/source masks across12 seeds and both occluder styles;
 AI-101 report plus existing landmark foundation tests.
- Command: `python -m pytest -q software/ai/tests/test_landmark_training.py software/ai/tests/test_landmark_foundation.py`
- Result: PASS,4 tests; existing pytest-asyncio configuration deprecation warning.
- Artifacts: named tests and AI-101 scorecard.
- Hardware writes: 0
- Physical movements: 0
- Limitations: pipeline correctness does not override failed trained-model metrics.
- Supersedes: none
- Next dependency: AI-101 model diagnostic.

### E-20260926-AI-103 â€” landmark training publication audit

- Stage: S1
- Lane: AI
- Commit: `99dae837d1f6de5caec9ec42c62bcbc4a6a9f006` (implementation baseline plus scorecard/test snapshot)
- Change: audited publication snapshot.
- Inputs/fixtures: repository with AI-101/102 artifacts and reviewed fixture allowlist.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS;5795 paths,808.3 MiB,0 unresolved findings,14 reviewed synthetic fixtures.
- Artifacts: audit stdout and repository snapshot.
- Hardware writes: 0
- Physical movements: 0
- Limitations: heuristic audit; AI-041 protected-main PR publication blocker remains.
- Supersedes: none; historical failures retained.
- Next dependency: protected-branch PR/checks and AI-101 diagnostic.

### E-20260926-AI-104 â€” landmark decoding and visibility diagnosis

- Stage: S1
- Lane: AI
- Commit: `bc8ed03bfed5681c2c423162dbc30642c45e8ec2` (frozen diagnostic/manifest before scoring)
- Change: inspected unchanged saved checkpoint on all retained development images;
  compared heatmap peak/soft-argmax error, entropy, mass within8px of truth and
  visibility output by geometric visibility class. No retraining or tuned decoder.
- Inputs/fixtures:15M800 development images,3200 corners, ellipse occluders;
  checkpoint/source/scorecard hashes in `eval/landmark_diagnostic_v0.manifest.json`.
- Command: `python software/ai/vision/diagnose_landmarks.py`
- Result: PASS diagnosis; trained model remains failed. Clear2736 corners:
  soft mean26.132636px vs peak3.991214px, peak p956.338789px, mean local mass0.518875.
  Partial263: soft26.077368px vs peak4.338650px; hidden201: soft22.233041px
  vs peak4.172279px. Mean predicted visibility clear0.921696,partial0.905462,
  hidden0.899715; every corner exceeds0.5, including all201 hidden corners.
  Heatmaps contain useful peak location information but distributed probability
  causes substantially different soft-argmax output; no precise causal ablation.
- Artifacts: `eval/landmark_diagnostic_v0_report.json`, manifest and diagnostic.
- Hardware writes: 0
- Physical movements: 0
- Limitations: reused development data; peak errors still substantial and peak
  decoding is not promoted. Geometric mask labels do not capture all perceptual
  visibility. Class imbalance/spread observations do not isolate training causes.
  No batch changes; boundary suite not triggered; integration gates unchanged.
- Supersedes: none; AI-101 failure retained.
- Next dependency: freeze a matched corrective training comparison with visible-
  corner coordinate loss and class-balanced visibility loss, retaining geometric
  error and hidden-corner false-visible reporting. Keep data/initialization/budget
  matched and record combined-intervention limits; fresh evaluation only after
  development evidence justifies it. No calibrated confidence claim.

### E-20260926-AI-105 â€” landmark diagnostic evidence test

- Stage: S1
- Lane: AI
- Commit: `bc8ed03bfed5681c2c423162dbc30642c45e8ec2` (implementation baseline; test committed with report)
- Change: verified frozen source/manifest,3200 unique corner records, class counts,
  error/local-mass means and false-visible counts.
- Inputs/fixtures: AI-104 manifest/report and retained source hashes.
- Command: `python -m pytest -q software/ai/tests/test_landmark_diagnostic.py`
- Result: PASS,1 test; existing pytest-asyncio configuration deprecation warning.
- Artifacts: named test and AI-104 report.
- Hardware writes: 0
- Physical movements: 0
- Limitations: diagnostic consistency only; no model qualification.
- Supersedes: none
- Next dependency: AI-104 corrective comparison.

### E-20260926-AI-106 â€” landmark diagnostic publication audit

- Stage: S1
- Lane: AI
- Commit: `bc8ed03bfed5681c2c423162dbc30642c45e8ec2` (implementation baseline plus report/test snapshot)
- Change: audited publication snapshot after merging newcomer-verification main.
- Inputs/fixtures: repository with AI-104/105 artifacts and reviewed fixture allowlist.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS;5800 paths,809.6 MiB,0 unresolved findings,14 reviewed synthetic fixtures.
- Artifacts: audit stdout and repository snapshot.
- Hardware writes: 0
- Physical movements: 0
- Limitations: heuristic audit; AI-041 protected-main PR publication blocker remains.
- Supersedes: none; historical failures retained.
- Next dependency: protected-branch PR/checks and AI-104 corrective training.

### E-20260926-AI-107 â€” matched landmark loss correction failure

- Stage: S1
- Lane: AI
- Commit: `82f3707d33a05e75a614a03fbf1ff87d8cee069a` (frozen protocol before either training arm)
- Change: matched seeded initialization/data/order/eight-epoch budget; control
  original loss, candidate visible-corner coordinate loss (squared error/16px)
  plus balanced positive/negative soft visibility loss. Both choose checkpoints
  using the same corrected development loss. Existing pose baseline retained.
- Inputs/fixtures:14M600 groups/2400 training images,15M200 groups/800 development
  images, rectangle training/ellipse development occluders. Exact source/catalog/
  baseline hashes in `train/landmark_corrected_v0_plan.json`; paired pixel/checkpoint
  hashes, histories and cases in arm scorecards and comparison report.
- Command: `python software/ai/train/train_landmarks_corrected.py`
- Result: FAIL corrective criteria and existing-pose comparison. Mean key errors
  control -> corrected:standard20.879164 -> 9.484379mm,appearance27.866548 ->
 13.456419mm,partial23.985062 -> 11.709188mm,full22.069383 -> 11.777097mm.
 Standard/appearance yaw-p95 exceed allowed regression. False-visible hidden
 corners201 -> 14/201, but clear-corner recall2736/2736 -> 335/2736=12.24%,
 below90%. Both selected epoch8. No model promotion; combined intervention does
 not isolate each loss's contribution.
- Artifacts: `train/train_landmarks_corrected.py`, frozen plan,
 `eval/landmark_corrected_v0_control_scorecard.json`, corrected scorecard and
 comparison JSON; ignored local control/corrected model checkpoints.
- Hardware writes: 0
- Physical movements: 0
- Limitations: reused development, one seed, short budget; both models remain far
 worse than pretrained pose baseline. Uncalibrated visibility and unconditional
 four-corner pose decoding are diagnostic only. No batch changes; boundary suite
 not triggered, shared integration status unchanged.
- Supersedes: none; prior failed landmark studies retained.
- Next dependency: freeze a matched loss ablation separating coordinate-only and
 balanced-visibility-only changes, using identical initialization/data/budget and
 selection objective. Record localization, hidden false visibility and clear recall;
 do not tune thresholds or claim calibrated confidence from this result.

### E-20260926-AI-108 â€” corrective landmark loss tests

- Stage: S1
- Lane: AI
- Commit: `82f3707d33a05e75a614a03fbf1ff87d8cee069a` (implementation baseline; tests committed with evidence)
- Change: verified balanced rare-hidden gradients, finite all-clear loss,
  matched pixels, frozen hashes, selection, visibility counts and comparison gates.
- Inputs/fixtures: analytic Torch logits and paired AI-107 reports/manifest.
- Command: `python -m pytest -q software/ai/tests/test_landmark_corrected.py`
- Result: PASS,2 tests; existing pytest-asyncio configuration deprecation warning.
- Artifacts: named tests and AI-107 reports.
- Hardware writes: 0
- Physical movements: 0
- Limitations: implementation consistency does not override failed model criteria.
- Supersedes: none
- Next dependency: AI-107 separate-loss comparison.

### E-20260926-AI-109 â€” corrected landmark publication audit

- Stage: S1
- Lane: AI
- Commit: `82f3707d33a05e75a614a03fbf1ff87d8cee069a` (implementation baseline plus reports/test snapshot)
- Change: audited publication snapshot.
- Inputs/fixtures: repository with AI-107/108 artifacts and reviewed fixture allowlist.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS;5806 paths,810.9 MiB,0 unresolved findings,14 reviewed synthetic fixtures.
- Artifacts: audit stdout and repository snapshot.
- Hardware writes: 0
- Physical movements: 0
- Limitations: heuristic audit; AI-041 protected-main PR publication blocker remains.
- Supersedes: none; historical failures retained.
- Next dependency: protected-branch PR/checks and AI-107 ablation.

### E-20260926-AI-110 — separate landmark loss ablations

- Stage: S1
- Lane: AI
- Commit: `5a29b0178378478955a12b70a2cf78582f1f4b88` (frozen before execution)
- Change: separated coordinate-only and balanced-visibility-only objectives, retaining frozen matched control and combined failures.
- Inputs/fixtures: 600 training groups from seed14000000, 200 reused development groups from15000000; four conditions, rectangle training/ellipse development occluders; 2400/800 images. Exact source/catalog/checkpoint hashes in `train/landmark_ablation_v0_plan.json`; identical pixel hashes verified against frozen control.
- Command: `python software/ai/train/train_landmarks_ablation.py`
- Result: FAIL both arms. Coordinate-only mean errors standard/appearance/partial/full 8.512/12.892/11.084/11.248 mm versus control20.879/27.867/23.985/22.069; >3mm tails194/200/197/199 out of200 each. Hidden false-visible201/201, clear recall2736/2736. Standard/appearance yaw regressions fail. Visibility-only means24.012/29.538/26.409/25.285 mm; tails200 each; hidden false-visible88/201, clear recall1572/2736 (57.46%, below90%). Both select epoch8 with common combined development objective. Both remain worse than existing pose baseline.
- Artifacts: `eval/landmark_ablation_v0_comparison.json` and two arm scorecards. Coordinate checkpoint SHA256 `c19e3f2b193c331cf0a2d97210aca2a94a501a5af04205b154a3cc92a168535c`; visibility checkpoint `ee2f83c3631673544ee5ff9f9ee6b3930f8648e1a35b445a510f36d8fc56c1b8` (ignored local results).
- Hardware writes: 0
- Physical movements: 0
- Limitations: one seed, reused development, GPU not bitwise guaranteed; geometric visibility uncalibrated. No localization qualification, runtime calibration, boundary or integration gate change.
- Supersedes: none; all failed evidence retained.
- Next dependency: diagnose spatially localized visibility features versus current global pooling, using frozen checkpoint/occlusion evidence before another training change. Preserve coordinate-only localization result as research, not admission.

### E-20260926-AI-111 — ablation provenance and decision checks

- Stage: S1
- Lane: AI
- Commit: `5a29b0178378478955a12b70a2cf78582f1f4b88` (implementation baseline; tests committed with evidence)
- Change: verify pinned hashes, matched pixels, checkpoint selection, independently recounted visibility and recomputed decision gates.
- Inputs/fixtures: AI-110 manifest/reports and frozen AI-107 control; SHA256 references in manifest/comparison.
- Command: `python -m pytest -q software/ai/tests/test_landmark_ablation.py`
- Result: PASS,1 test; existing pytest-asyncio configuration warning.
- Artifacts: named test and AI-110 scorecards.
- Hardware writes: 0
- Physical movements: 0
- Limitations: consistency verification does not qualify models; no batch contract changes, shared boundary suite not triggered.
- Supersedes: none
- Next dependency: AI-110 visibility diagnosis.

### E-20260926-AI-112 — ablation publication audit

- Stage: S1
- Lane: AI
- Commit: `5a29b0178378478955a12b70a2cf78582f1f4b88` (implementation baseline plus results/test snapshot)
- Change: audit publication snapshot.
- Inputs/fixtures: repository with AI-110/111 artifacts and reviewed synthetic fixture allowlist.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS;5812 paths,812.2 MiB,0 unresolved findings,14 reviewed synthetic fixtures.
- Artifacts: audit stdout and repository snapshot.
- Hardware writes: 0
- Physical movements: 0
- Limitations: heuristic audit; AI-041 protected-main publication blocker remains.
- Supersedes: none
- Next dependency: protected-branch PR/checks and AI-110 diagnosis.
### E-20260926-ARM-030 — r97 production runtime firmware candidate

- Stage: S4
- Lane: ARM
- Change: implemented and reproducibly compiled the minimal r97 controller-side
  runtime against ARM-028. The sketch starts safe-idle, exposes only canonical
  T=102 and T=105 input, returns T=1051 joint feedback, contains one seven-servo
  group-write call site, and terminally locks on ambiguity without retry.
- Excluded surfaces: vendor generic dispatcher, Wi-Fi, HTTP, ESP-NOW,
  filesystem, mission playback, persistence, torque changes, single-servo
  writes, automatic retry, and startup movement are absent from sketch source.
- Attestation: startup dynamically reports the running app digest plus pinned
  host protocol and joint-mapping source hashes. Configuration epoch remains
  explicitly null and is a qualification blocker rather than an assumed value.
- Compile: `default-4mb-no-psram` PASS; app SHA-256
  `7d2e47d40141e95b611fcf37ca38d495fcf3da4dc3051f128bbae95e10840d1d`;
  314,640 bytes of a 1,310,720-byte slot; verified export
  `wizard-20260926T173219601251Z-d485be98eea84923b79039bc01b7dbe4`.
- Artifacts: `software/scripts/stage_r97_production_runtime.py`,
  `software/scripts/review_r97_production_runtime.py`, firmware-source tests,
  and `software/docs/PRODUCTION_RUNTIME_FIRMWARE_R97.md`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: compile and first-party inspection do not prove behavior on an
  installed controller. Independent source/image review, configuration-epoch
  binding, installed identity/surface checks, and feedback qualification remain
  mandatory before any installation or movement proposal.
- Supersedes: ARM-029's implementation dependency only. It does not authorize
  installation, startup, transport, feedback reads, or movement.
- Next dependency: run repository integration verification, then obtain an
  independent offline review of the exact source and app image.

### E-20260926-ARM-031 — r97 offline integration verification

- Stage: S4
- Lane: ARM
- Change: verified the exact staged r97 source, compile evidence, app image,
  required linked symbols, host runtime contract, installed-surface gate,
  qualification boundary, zero-write adapter, sole-writer lifecycle, model
  ingress, and measured trajectory-envelope integration.
- Results: r97 source/image review PASS with status
  `COMPILED_AWAITING_INDEPENDENT_REVIEW_NOT_INSTALLED`; focused r97 plus host
  contract PASS, 30 tests; integrated boundary selection PASS, 107 tests in
  11.95 seconds; documentation PASS for 22 maintained documents and two SVG
  assets; snapshot audit PASS for 5,709 paths and 903.7 MiB with zero unresolved
  findings and 14 reviewed synthetic fixtures; diff check PASS.
- Environment note: an attempted unscoped full-suite collection encounters an
  existing Python package-name collision in three legacy tests importing
  `scripts`; the bounded integration selection avoids those unrelated live
  installer modules and is fully green.
- Hardware writes: 0
- Physical movements: 0
- Limitations: no controller was opened, installed, started, queried, or moved.
  Independent review and configuration-epoch binding remain incomplete.
- Supersedes: ARM-030 only for current offline verification evidence.
- Next dependency: independent review of exact app SHA-256
  `7d2e47d40141e95b611fcf37ca38d495fcf3da4dc3051f128bbae95e10840d1d`;
  only after approval should an installation/startup proposal be drafted.

### E-20260926-AI-113 — paired corner visibility response

- Stage: S1
- Lane: AI
- Commit: `a38231105cda7e0104b8fc8238076bed6e697db9` (source and input manifest frozen before execution)
- Change: compare same-seed standard/full occlusion predictions for four frozen landmark models; target must change clear-to-hidden, comparison corners remain clear.
- Inputs/fixtures: AI-107/110 scorecards, 200 reused development groups starting15000000;196 eligible pairs per model. Exact input/source SHA256 in `vision/landmark_visibility_response_plan.json`.
- Command: `python software/ai/vision/diagnose_landmark_visibility_response.py`
- Result: diagnostic completed; target probability drops control/combined/coordinate-only/visibility-only 0.001482/0.000263/0.000317/0.001827. Target-minus-peer selectivity0.000081/0.000152/0.000105/0.000231. Fixed0.5 visible-to-hidden crossings0/0/0/2 of196. Positive selectivity56/104/107/142. Small response supports testing localized visibility features; does not prove pooling causality.
- Artifacts: `eval/landmark_visibility_response.json`, runner and frozen manifest.
- Hardware writes: 0
- Physical movements: 0
- Limitations: existing predictions, reused synthetic development data, image-wide normalization also changes; descriptive study without qualification threshold. No local-head model trained. No batch contract or integration-status change.
- Supersedes: none; previous failures retained.
- Next dependency: freeze matched global-pooling versus corner-local visibility-head training, using predicted locations at evaluation; oracle crops can only be explicitly labeled diagnostics. Preserve localization and clear-recall gates.

### E-20260926-AI-114 — visibility response verification

- Stage: S1
- Lane: AI
- Commit: `a38231105cda7e0104b8fc8238076bed6e697db9` (source baseline; test committed with evidence)
- Change: analytic targeted/global response discrimination and complete report recomputation with hash verification.
- Inputs/fixtures: analytic four-corner predictions, AI-113 pinned input reports and output.
- Command: `python -m pytest -q software/ai/tests/test_landmark_visibility_response.py`
- Result: PASS,2 tests; existing pytest-asyncio configuration warning.
- Artifacts: named test and AI-113 report.
- Hardware writes: 0
- Physical movements: 0
- Limitations: verifies calculation, not model qualification; boundary contract unchanged, shared boundary tests not triggered.
- Supersedes: none
- Next dependency: AI-113 matched local-head study.

### E-20260926-AI-115 — visibility diagnostic publication audit

- Stage: S1
- Lane: AI
- Commit: `a38231105cda7e0104b8fc8238076bed6e697db9` (frozen source plus report/test snapshot)
- Change: audit publication snapshot.
- Inputs/fixtures: repository with AI-113/114 artifacts and reviewed fixture allowlist.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS;5820 paths,812.4 MiB,0 unresolved findings,14 reviewed synthetic fixtures.
- Artifacts: audit stdout and snapshot.
- Hardware writes: 0
- Physical movements: 0
- Limitations: heuristic audit; AI-041 protected-main publication blocker remains.
- Supersedes: none
- Next dependency: protected-branch PR/checks and AI-113 training study.

### E-20260926-AI-116 — matched predicted-local visibility training

- Stage: S1
- Lane: AI
- Commit: `b06f609a33e09e0a0a402b665b05f245d55e7cb6` (source/plan frozen before execution)
- Change: retrain matched global versus local visibility pooling with identical parameter initialization, combined loss, ordering, budget and checkpoint selection. Local head samples3x3 feature cells around hard predicted heatmap peaks; no oracle positions at training or evaluation.
- Inputs/fixtures:2400 training images (600 groups from14000000),800 reused development images (200 groups from15000000),four conditions; rectangle/ellipse occluders. Exact sources/catalog/baseline hashes in `train/landmark_local_visibility_v0_plan.json`; identical pixel hashes verified.
- Command: `python software/ai/train/train_local_visibility.py`
- Result: FAIL local promotion rule. Hidden false-visible global36/201 versus local4/201; clear recall563/2736 (20.58%) versus2065/2736 (75.48%), below90%. Global mean key errors standard/appearance/partial/full8.514/12.938/11.005/11.125mm; local8.537/12.821/11.348/11.438mm. >3mm tails global194/200/197/198 versus local191/198/198/200 out of200 each. All relative yaw checks pass, but mean/occluded tails regress. Both selected epoch8; both worse than pretrained pose baseline. Global self-comparison in JSON is bookkeeping, not an independent candidate gate.
- Artifacts: `eval/landmark_local_visibility_v0_comparison.json` and global/local scorecards. Ignored local checkpoint hashes global `2ae47a78deabd3479f8ef3f3efdeea2ef95ecdcffca0c78ed736ce8ecf4c36b8`, local `3d2fd582bcb7591d4ef04aff8c9db5fedc38ce37d704786ed7d82265cb5b82d7`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: one seed,eight epochs,reused synthetic development; GPU nondeterminism and shared-feature training effects preclude broad causal/generalization claims. No calibrated uncertainty or runtime qualification. ModelMotionBatch boundary unchanged; integration gates unchanged.
- Supersedes: none; all failed studies retained.
- Next dependency: freeze paired obstruction-response and error-stratified local-head diagnosis, distinguishing wrong predicted crop locations from clear-corner rejection before choosing another training change.

### E-20260926-AI-117 — local visibility implementation verification

- Stage: S1
- Lane: AI
- Commit: `b06f609a33e09e0a0a402b665b05f245d55e7cb6` (implementation baseline; tests committed with evidence)
- Change: test identical initialization, constant-field pooling agreement, feature/head gradients and hard-position gradient exclusion; verify artifact hashes, same pixels, selection and independently recomputed criteria.
- Inputs/fixtures: analytic feature fields, seeded networks and AI-116 pinned reports/manifest.
- Command: `python -m pytest -q software/ai/tests/test_local_visibility.py`
- Result: PASS,3 tests; existing pytest-asyncio configuration warning.
- Artifacts: named test and AI-116 reports.
- Hardware writes: 0
- Physical movements: 0
- Limitations: implementation consistency does not override model failures. No boundary contract changes; shared boundary suite not triggered.
- Supersedes: none
- Next dependency: AI-116 diagnostic.

### E-20260926-AI-118 — local visibility publication audit

- Stage: S1
- Lane: AI
- Commit: `b06f609a33e09e0a0a402b665b05f245d55e7cb6` (frozen source plus result/test snapshot)
- Change: audit publication snapshot.
- Inputs/fixtures: repository with AI-116/117 artifacts and reviewed fixture allowlist.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS;5827 paths,813.8 MiB,0 unresolved findings,14 reviewed synthetic fixtures.
- Artifacts: audit stdout and snapshot.
- Hardware writes: 0
- Physical movements: 0
- Limitations: heuristic audit; AI-041 protected-main publication blocker remains.
- Supersedes: none
- Next dependency: protected-branch PR/checks and AI-116 diagnostic.
### E-20260926-ARM-032 — r97 accepted-once host correlation

- Stage: S4
- Lane: ARM
- Change: closed the host/firmware receipt gap for r97. The host contract now
  permits exactly one in-flight T=102, requires the exact canonical
  `T=1021,status=ACCEPTED_ONCE,ordinal=N` response for the pending sequence, and
  forbids another command or T=105 exchange until that receipt is consumed.
- Failure behavior: missing, stale, duplicate, reordered, wrong-ordinal,
  malformed, overlong, CRLF, or extra-field responses terminally lock the
  session. A timeout is retained as uncertain after one admission and never
  retries or replays the command.
- Semantics: the acknowledgment proves only that r97 accepted the command once
  and reached its one group-write call. `arrival_proven` is schema-fixed false;
  fresh T=105/T=1051 feedback and later arrival verification remain separate.
- Artifacts: updated production runtime state machine, manifest/rehearsal
  schemas, public exports, unit tests, schema README, controller contract, and
  r97 firmware documentation.
- Results: focused runtime PASS, 26 tests; integrated model/trajectory,
  zero-write, qualification, surface, firmware, and runtime boundaries PASS,
  115 tests in 10.57 seconds; documentation PASS for 23 maintained documents
  and two SVG assets; snapshot audit PASS for 5,712 paths and 903.7 MiB with
  zero unresolved findings and 14 reviewed synthetic fixtures; diff check PASS.
- Hardware writes: 0
- Physical movements: 0
- Limitations: this is still zero-I/O rehearsal. It does not install r97, open a
  controller, consume a live receipt, bind configuration epoch, or prove servo
  arrival.
- Supersedes: ARM-031 only for host/r97 acknowledgment compatibility and current
  offline integration counts; the independent review blocker remains.
- Next dependency: independently review the exact r97 source/image, then bind a
  measured configuration epoch before any installation/startup proposal.

### E-20260926-ARM-033 — sealed r97 independent-review handoff

- Stage: S4
- Lane: ARM
- Change: added a deterministic review-packet builder and fail-closed inspector
  so an independent reviewer can receive the exact r97 source, linked app and
  ELF images, compile report, first-party report, closed member manifest, and
  explicit review procedure without relying on mutable workspace paths.
- Packet identity: SHA-256
  `987cbe86d98440734d8336c704f1ecd89692675a9cb1620cb674e4132957b416`;
  manifest SHA-256
  `e7c67071d0485b016cf44e0158fddb92edc0373e1e73532a3b1847f976d5117e`;
  app SHA-256 remains
  `7d2e47d40141e95b611fcf37ca38d495fcf3da4dc3051f128bbae95e10840d1d`.
- Safety behavior: archive membership is closed; duplicate, additional, unsafe,
  missing, or hash/size-mismatched members fail inspection. The source/image
  binding and existing first-party blocker must match before a packet is built.
  Packet construction and inspection grant no approval, epoch binding,
  installation, startup, movement, or physical authority.
- Results: focused packet, r97 source, production-runtime, and bounded shared
  AI/arm boundary tests PASS, 214 tests in 15.85 seconds. Documentation PASS
  for 23 maintained documents and two SVG assets; snapshot audit PASS for
  5,715 paths and 903.8 MiB with zero unresolved findings and 14 reviewed
  synthetic fixtures; diff check PASS. The actual seven-member packet was
  produced and reinspected locally.
- Hardware writes: 0
- Physical movements: 0
- Limitations: this makes independent review reproducible but does not perform
  or impersonate it. The packet is stored in the ignored `runs/review-packets/`
  evidence area and must be transferred unchanged to a genuinely independent
  reviewer. No measured configuration epoch exists yet.
- Supersedes: ARM-032 only for review-handoff readiness; all independent-review,
  measured-epoch, installation, startup, and physical blockers remain.
- Next dependency: an independent reviewer publishes a separate decision bound
  to the exact packet SHA-256, followed by measured configuration-epoch intake.

### E-20260926-AI-119 — local visibility error diagnosis

- Stage: S1
- Lane: AI
- Commit: `8110be4d686878debfcc34f004b433b9a68bafec` (frozen before execution)
- Change: recompute local-head predicted peak/soft coordinate errors on CPU, stratify geometric classes at fixed4/8pixel cuts, and compare frozen global/local paired occlusion responses.
- Inputs/fixtures:200 reused groups15000000..15000199, four conditions,800 images/3200 corners; local checkpoint SHA256 `3d2fd582bcb7591d4ef04aff8c9db5fedc38ce37d704786ed7d82265cb5b82d7`. Exact source, checkpoint and scorecard hashes in `eval/local_visibility_diagnostic_v0.manifest.json`.
- Command: `python software/ai/vision/diagnose_local_visibility.py`
- Result: diagnostic completed. Paired clear-to-hidden crossings global0 versus local172/196; local mean target drop0.358145, unaffected-peer drop0.000669. CPU clear predicted-visible2068/2736; below4px831/1025,4–8px1181/1262,>=8px56/449. Of668 clear rejections,393 have>=8px peak error and275 have<8px. Clear peak mean13.877px/p9590.154px; soft mean9.220px. Hidden false-visible4/201. Both crop location and near-corner classification remain relevant.
- Artifacts: `eval/local_visibility_diagnostic_v0_report.json`, runner and manifest.
- Hardware writes: 0
- Physical movements: 0
- Limitations: CPU recomputation differs from retained GPU scorecard by3 clear decisions (2068 versus2065); cause not isolated, neither overwritten. Reused synthetic development; error strata association is not causal proof. No calibrated uncertainty, boundary changes or integration completion.
- Supersedes: none
- Next dependency: isolate CPU/GPU and single/batch inference disagreement with identical stored pixels/checkpoint, then freeze a location-estimator comparison for the visibility crop. No oracle runtime crop or qualification.

### E-20260926-AI-120 — local diagnostic verification

- Stage: S1
- Lane: AI
- Commit: `8110be4d686878debfcc34f004b433b9a68bafec` (source baseline; tests committed with evidence)
- Change: verify hashes and independently recount all fixed error strata and paired crossing counts.
- Inputs/fixtures: AI-119 manifest,3200 corner rows and paired response rows; source/input hashes in manifest.
- Command: `python -m pytest -q software/ai/tests/test_local_visibility_diagnostic.py`
- Result: PASS,1 test; existing pytest-asyncio configuration warning.
- Artifacts: named test and diagnostic report.
- Hardware writes: 0
- Physical movements: 0
- Limitations: arithmetic/provenance verification; no boundary changes, shared boundary suite not triggered.
- Supersedes: none
- Next dependency: AI-119 inference parity diagnosis.

### E-20260926-AI-121 — local diagnostic publication audit

- Stage: S1
- Lane: AI
- Commit: `8110be4d686878debfcc34f004b433b9a68bafec` (source baseline plus result/test snapshot)
- Change: audited publication snapshot.
- Inputs/fixtures: repository with AI-119/120 artifacts and reviewed fixture allowlist.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS;5835 paths,815.2 MiB,0 unresolved findings,14 reviewed synthetic fixtures.
- Artifacts: audit stdout and snapshot.
- Hardware writes: 0
- Physical movements: 0
- Limitations: heuristic audit; AI-041 protected-main publication blocker remains.
- Supersedes: none
- Next dependency: protected-branch PR/checks and AI-119 parity diagnosis.
### E-20260926-ARM-034 — measured configuration-epoch intake contract

- Stage: S4
- Lane: ARM
- Change: added a strict zero-I/O intake and assessment for the configuration
  epoch required by the production runtime. It binds the exact r97 review
  packet, candidate app, protocol source, joint-mapping source, optional
  predecessor, and all eight ordered workcell components to retained evidence
  plus separate independent-review decisions.
- Bootstrap decision: the candidate app SHA is explicit but remains separate
  from the epoch digest. This prevents a circular requirement in which the app
  binary must contain an epoch hash that itself depends on the final app hash.
  A later epoch-bound build embeds the stable epoch digest and attests its final
  app SHA separately.
- Admission behavior: synthetic, unreviewed, future-dated, stale, reordered,
  incomplete, or release-identity-mismatched inputs block. A complete intake
  reaches only `READY_FOR_EPOCH_BOUND_BUILD_PROPOSAL`; installation, controller
  startup, transport, execution, hardware access, and physical authority remain
  schema-fixed false.
- Artifacts: typed intake/report implementation, closed JSON schemas, public
  exports, unit/schema tests, schema documentation, and controller-runtime
  bootstrap documentation.
- Results: bounded shared AI/arm, r97, runtime, and epoch-intake suite PASS, 228
  tests in 16.25 seconds; documentation PASS for 23 maintained documents and
  two SVG assets; snapshot audit PASS for 5,719 paths and 903.8 MiB with zero
  unresolved findings and 14 reviewed synthetic fixtures; diff check PASS.
- Hardware writes: 0
- Physical movements: 0
- Limitations: no real review decision or physical component evidence was
  supplied, so no measured epoch record was created and no build is presently
  ready. Tests use synthetic evidence strictly to exercise contract behavior.
- Supersedes: ARM-033 only for readiness to consume future measured evidence;
  independent review and all physical evidence collection remain external.
- Next dependency: supply an independent decision for packet
  `987cbe86d98440734d8336c704f1ecd89692675a9cb1620cb674e4132957b416`
  and independently reviewed retained measurements for all eight components.

### E-20260926-AI-122 — local visibility device/batch parity

- Stage: S1
- Lane: AI
- Commit: `deb618c51d84f366591aef46c6b69d471cb60005` (source/plan frozen before execution)
- Change: compare CPU/CUDA inference at batch1/32 on identical normalized uint8 pixels and checkpoint, retaining peak indices, top-two margins and probabilities.
- Inputs/fixtures:800 reused development images/3200 corners from15000000..15000199; input pixel hash matches AI-116. Checkpoint `3d2fd582bcb7591d4ef04aff8c9db5fedc38ce37d704786ed7d82265cb5b82d7`; exact input/source hashes in `eval/local_visibility_parity_plan.json`.
- Command: `python software/ai/vision/diagnose_local_visibility_parity.py`
- Result: diagnostic completed; exact decision parity FAIL across devices. CPU1 versus CPU32:0 peak/decision changes,max probability delta1.1921e-7. CPU1 versus CUDA1:4 peak changes,3 decision changes,max delta0.395179. CPU1 versus CUDA32:6 peak changes,3 decision changes,max delta0.300818. CUDA32 exactly reproduces retained GPU report (delta0). Different cases flip in CUDA1 and CUDA32. Every decision flip changes hard peak; CPU top-two margins for changed cases range0.0000410..0.00194645. Hard selection amplifies observed numerical sensitivity; underlying kernel/precision source not isolated.
- Artifacts: `eval/local_visibility_parity_report.json` including exact environment, all predictions and changed indices; frozen runner/plan.
- Hardware writes: 0
- Physical movements: 0
- Limitations: one checkpoint, reused synthetic images, one CPU/GPU environment; no cross-platform bound or correction established. No model qualification, batch boundary change or integration gate completion.
- Supersedes: none; both earlier CPU/GPU reports retained.
- Next dependency: freeze matched continuous heatmap-weighted local feature pooling versus hard-peak pooling; assess localization, visibility and device/batch decision stability without oracle positions or threshold tuning.

### E-20260926-AI-123 — parity evidence verification

- Stage: S1
- Lane: AI
- Commit: `deb618c51d84f366591aef46c6b69d471cb60005` (source baseline; tests committed with evidence)
- Change: recompute comparison counts, verify every decision flip changes peak, input hashes and exact retained GPU reproduction.
- Inputs/fixtures: AI-122 manifest/report and pinned AI-116 scorecard.
- Command: `python -m pytest -q software/ai/tests/test_local_visibility_parity.py`
- Result: PASS,1 test; existing pytest-asyncio configuration warning.
- Artifacts: named test and AI-122 report.
- Hardware writes: 0
- Physical movements: 0
- Limitations: calculation consistency does not establish inference stability. Boundary unchanged, shared boundary tests not triggered.
- Supersedes: none
- Next dependency: AI-122 pooling experiment.

### E-20260926-AI-124 — parity publication audit

- Stage: S1
- Lane: AI
- Commit: `deb618c51d84f366591aef46c6b69d471cb60005` (source baseline plus result/test snapshot)
- Change: audit publication snapshot.
- Inputs/fixtures: repository with AI-122/123 artifacts and reviewed fixture allowlist.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS;5843 paths,816.4 MiB,0 unresolved findings,14 reviewed synthetic fixtures.
- Artifacts: audit stdout and snapshot.
- Hardware writes: 0
- Physical movements: 0
- Limitations: heuristic audit; AI-041 protected-main publication blocker remains.
- Supersedes: none
- Next dependency: protected-branch PR/checks and AI-122 pooling study.

### E-20260926-AI-125 — matched hard versus weighted local pooling

- Stage: S1
- Lane: AI
- Commit: `82b8fc76aee4aa2d7849cbe6cba9f35b5891daf6` (frozen source baseline; results/tests committed with this evidence)
- Change: matched hard versus weighted local pooling.
- Inputs/fixtures: 2400 training/800 reused development images;600 groups from14000000 and200 from15000000, four conditions. Exact source/catalog/checkpoint hashes in train/landmark_weighted_visibility_v0_plan.json.
- Command: `python software/ai/train/train_weighted_visibility.py`
- Result: FAIL promotion. Weighted mean errors standard/appearance/partial/full9.201/13.261/11.167/11.337mm versus hard9.951/14.340/12.013/12.135; all relative mean/tail/yaw checks pass. Hidden false-visible6→15/201; clear recall2283→1699/2736 (83.44%→62.10%), below90%. Both select epoch8. Hard checkpoint7f8f9263e90bada8b96190a702c1be67d0aafc0d8288669644276c063373ce02; weighted1551db19d1a4e34b4ebf9e793e4fa87b9d8e8f07ceefcd9f8cf94f6bf2b5d3a1.
- Artifacts: eval/landmark_weighted_visibility_v0_*; ignored local checkpoints
- Hardware writes: 0
- Physical movements: 0
- Limitations: One seed, reused synthetic development, GPU nondeterminism; full softmax weighting may dilute local evidence. Both remain worse than pose baseline; no qualification. Reference self-comparison is bookkeeping.
- Supersedes: none; prior failed evidence and shared integration statuses retained.
- Next dependency: Diagnose heatmap mass spread versus clear/hidden errors before selecting a pooling modification; retain all failures.

### E-20260926-AI-126 — matched pooling inference parity

- Stage: S1
- Lane: AI
- Commit: `70db43fae214c1b374b5fb52789e57be5e3c8fba` (frozen source baseline; results/tests committed with this evidence)
- Change: matched pooling inference parity.
- Inputs/fixtures: AI-125 checkpoints and identical800 development pixels; exact hashes in eval/weighted_visibility_{hard,weighted}_parity_plan.json.
- Command: `python software/ai/vision/diagnose_weighted_visibility_parity.py`
- Result: FAIL zero-decision-disagreement criterion for both. Hard CPU1→CUDA1:3 flips,max delta0.150383; CPU1→CUDA32:0 flips,max0.000206590. Weighted CPU1→CUDA1:1 flip,max0.000301659; CPU1→CUDA32:4 flips,max0.000349224. CPU1/32:0 flips both; both CUDA32 reports exactly reproduce retained training evaluation. Continuous weighting reduces probability excursions but does not ensure threshold decision parity.
- Artifacts: eval/weighted_visibility_{hard,weighted}_parity_report.json
- Hardware writes: 0
- Physical movements: 0
- Limitations: Single environment and reused images; no cross-platform bound. Weighted peak changes are diagnostic only, not selected sampling positions.
- Supersedes: none; prior failed evidence and shared integration statuses retained.
- Next dependency: Analyze threshold margins and pooling mass spread without tuning thresholds on these reports.

### E-20260926-AI-127 — weighted pooling implementation verification

- Stage: S1
- Lane: AI
- Commit: `70db43fae214c1b374b5fb52789e57be5e3c8fba` (frozen source baseline; results/tests committed with this evidence)
- Change: weighted pooling implementation verification.
- Inputs/fixtures: Analytic constant features, matching initialization/gradient checks, AI-125/126 pinned scorecards/manifests.
- Command: `python -m pytest -q software/ai/tests/test_weighted_visibility.py`
- Result: PASS,4 tests; existing pytest-asyncio configuration warning. Hashes, pixels, selection, visibility gates, parity recounts and retained GPU predictions verified.
- Artifacts: software/ai/tests/test_weighted_visibility.py
- Hardware writes: 0
- Physical movements: 0
- Limitations: Tests verify implementation/evidence consistency, not model qualification. ModelMotionBatch boundary unchanged; shared boundary suite not triggered.
- Supersedes: none; prior failed evidence and shared integration statuses retained.
- Next dependency: AI-125/126 diagnostic dependencies.

### E-20260926-AI-128 — weighted pooling publication audit

- Stage: S1
- Lane: AI
- Commit: `70db43fae214c1b374b5fb52789e57be5e3c8fba` (frozen source baseline; results/tests committed with this evidence)
- Change: weighted pooling publication audit.
- Inputs/fixtures: Repository snapshot including AI-125/126/127 and reviewed fixture allowlist.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS;5855 paths,820.1 MiB,0 unresolved findings,14 reviewed synthetic fixtures.
- Artifacts: audit stdout and snapshot
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic audit; AI-041 protected-main publication blocker remains.
- Supersedes: none; prior failed evidence and shared integration statuses retained.
- Next dependency: Protected-branch PR/checks and AI-125/126 diagnostics.
### E-20260926-ARM-035 — typed external r97 review-decision boundary

- Stage: S4
- Lane: ARM
- Change: added a closed, content-addressed external-review decision and report
  contract for r97, then required configuration-epoch assessment to consume the
  full typed decision. Epoch admission now verifies exact packet, manifest, and
  app identities, the eleven-item checklist, independence and author-separation
  assertions, findings, disposition, decision digest, and disposition match.
- Safety behavior: a missing, mismatched, rejected, non-independent,
  author-conflicted, incomplete, or open-finding decision blocks. The decision
  and report keep installation, startup, execution, hardware access, and
  physical authority false. There is no transport or device I/O.
- Trust boundary: validation proves only structure and internal content binding.
  It cannot authenticate the reviewer identity, establish independent custody,
  or turn a self-authored fixture into independent evidence. Tests use clearly
  labeled synthetic decisions; no real review decision was created.
- Artifacts: typed decision/report implementation, closed JSON schemas, public
  exports, epoch-intake linkage, unit/schema tests, and firmware/runtime/schema
  documentation.
- Results: bounded shared AI/arm, r97, runtime, review-decision, and epoch-intake
  suite PASS, 249 tests in 16.78 seconds; documentation PASS for 25 maintained
  documents and two SVG assets; snapshot audit PASS for 5,725 paths and 903.8
  MiB with zero unresolved findings and 14 reviewed synthetic fixtures; diff
  check PASS.
- Hardware writes: 0
- Physical movements: 0
- Limitations: no external reviewer decision and no measured workcell component
  evidence have been supplied. No epoch-bound build is ready.
- Supersedes: ARM-034 only for the release-review decision binding; every
  external evidence and physical-use blocker remains.
- Next dependency: a genuinely independent reviewer publishes an authenticated
  decision for packet
  `987cbe86d98440734d8336c704f1ecd89692675a9cb1620cb674e4132957b416`,
  followed by independently reviewed retained measurements for all eight epoch
  components.

### E-20260926-AI-129 — weighted heatmap spread and threshold diagnosis

- Stage: S1
- Lane: AI
- Commit: `6e4105736ad903ac5b91981c24ff2f514c753a1a` (frozen source; result/tests committed with evidence)
- Change: weighted heatmap spread and threshold diagnosis.
- Inputs/fixtures: 800 reused synthetic development images,3200 corners, weighted checkpoint1551db19d1a4e34b4ebf9e793e4fa87b9d8e8f07ceefcd9f8cf94f6bf2b5d3a1; exact source/input hashes in eval/weighted_spread_v0.manifest.json.
- Command: `python software/ai/vision/diagnose_weighted_spread.py`
- Result: Completed descriptive diagnosis. Rejected/accepted clear counts1037/1699; entropy4.93842/4.24252, mass within8px0.46830/0.53454, peak error5.19219/12.36132px. Hidden rejected/accepted186/15; entropy4.29255/3.91302, mass0.44928/0.38421. Thus greater spread associates with clear rejection, but rejected clear peaks are closer on average; no single-cause claim. All5 retained CPU/GPU flipped cases have CPU threshold distance5.90e-6..1.09553e-4.
- Artifacts: eval/weighted_spread_v0_report.json; frozen runner/manifest
- Hardware writes: 0
- Physical movements: 0
- Limitations: Reused data, diagnostic truth-centered mass only, CPU single-image inference; group averages are associations. No retraining, threshold tuning, qualification or runtime calibration.
- Supersedes: none; failures and integration statuses preserved.
- Next dependency: Freeze a matched fixed-temperature0.5 versus1.0 continuous-weighting training comparison, chosen as one explicit hypothesis (no sweep); retain existing visibility/localization/stability criteria and require fresh evaluation before any promotion.

### E-20260926-AI-130 — weighted spread verification

- Stage: S1
- Lane: AI
- Commit: `6e4105736ad903ac5b91981c24ff2f514c753a1a` (frozen source; result/tests committed with evidence)
- Change: weighted spread verification.
- Inputs/fixtures: AI-129 manifest/rows and frozen AI-126 parity report; exact hashes in manifest.
- Command: `python -m pytest -q software/ai/tests/test_weighted_spread.py`
- Result: PASS,1 test; hashes, group means/counts and individual threshold distances independently recomputed. Existing pytest-asyncio configuration warning.
- Artifacts: software/ai/tests/test_weighted_spread.py
- Hardware writes: 0
- Physical movements: 0
- Limitations: Arithmetic/provenance check, not qualification; batch contract unchanged, shared boundary suite not triggered.
- Supersedes: none; failures and integration statuses preserved.
- Next dependency: AI-129 matched pooling hypothesis.

### E-20260926-AI-131 — weighted spread publication audit

- Stage: S1
- Lane: AI
- Commit: `6e4105736ad903ac5b91981c24ff2f514c753a1a` (frozen source; result/tests committed with evidence)
- Change: weighted spread publication audit.
- Inputs/fixtures: Repository snapshot with AI-129/130 and reviewed fixture allowlist.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS;5864 paths,821.5 MiB,0 unresolved findings,14 reviewed synthetic fixtures.
- Artifacts: audit stdout and repository snapshot
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic audit; AI-041 protected-main publication blocker remains.
- Supersedes: none; failures and integration statuses preserved.
- Next dependency: Protected-branch PR/checks and AI-129 experiment.

### E-20260926-AI-132 — fixed temperature training comparison

- Stage: S1
- Lane: AI
- Commit: `f950639a36a1433840a29410a934f37752aaff4e` (frozen source baseline; results/tests committed with evidence)
- Change: fixed temperature training comparison.
- Inputs/fixtures: 2400 training/800 reused development images,600 groups from14000000/200 from15000000,four conditions. Exact sources/catalog/baseline hashes in train/landmark_temperature_v0_plan.json.
- Command: `python software/ai/train/train_temperature_visibility.py`
- Result: FAIL overall relative gate despite visibility PASS. Temperature1→0.5 clear recall2060→2722/2736 (75.29%→99.49%), hidden false-visible42→2/201. Mean errors standard/appearance/partial/full9.277/13.389/11.361/11.504→7.714/11.530/10.465/10.659mm. >3mm tails197/200/197/198→194/196/197/199 out of200 each; full-condition tail regression fails. All relative mean/yaw checks pass. Both select epoch8. Checkpoint hashes t1=8727f2120c64a4d0c958410ba142cf4d0647528379fe1b8a63a9ee79177478b7,t05=356a4dec05c6c2194c6d31542fed0d7199d5e989eb4b7678888d1a01aa493281.
- Artifacts: eval/landmark_temperature_v0_*; ignored checkpoints
- Hardware writes: 0
- Physical movements: 0
- Limitations: One seed,reused synthetic development,GPU nondeterminism. Absolute localization remains far worse than pose baseline. Reference self-comparison is bookkeeping; no qualification.
- Supersedes: none; historical failures and shared integration status preserved.
- Next dependency: Freeze diagnostic of t05 soft-coordinate bias versus heatmap peak and visibility failures; retain fixed criteria and require fresh evidence before promotion.

### E-20260926-AI-133 — temperature inference parity

- Stage: S1
- Lane: AI
- Commit: `ff92b9d5f3b9faebb9b451e3b3a3e94a342f35ae` (frozen source baseline; results/tests committed with evidence)
- Change: temperature inference parity.
- Inputs/fixtures: AI-132 checkpoints and identical800 development pixels; exact hashes in eval/temperature_visibility_{t1,t05}_parity_plan.json.
- Command: `python software/ai/vision/diagnose_temperature_visibility_parity.py`
- Result: FAIL zero-disagreement criterion both. CPU1/32 and CPU1/CUDA1 decisions agree for both; CPU1/CUDA32 differs by1 decision each. Max cross-device probability deltas t1=0.000275016,t05=0.000681102. Both CUDA32 predictions exactly reproduce retained training evaluation.
- Artifacts: eval/temperature_visibility_{t1,t05}_parity_report.json
- Hardware writes: 0
- Physical movements: 0
- Limitations: One environment; no cross-platform guarantee. No correction, decision threshold tuning or qualification.
- Supersedes: none; historical failures and shared integration status preserved.
- Next dependency: Diagnose remaining near-threshold t05 case alongside localization; do not erase retained parity failure.

### E-20260926-AI-134 — temperature verification

- Stage: S1
- Lane: AI
- Commit: `ff92b9d5f3b9faebb9b451e3b3a3e94a342f35ae` (frozen source baseline; results/tests committed with evidence)
- Change: temperature verification.
- Inputs/fixtures: Analytic constant features,seeded networks,AI-132/133 pinned reports/manifests.
- Command: `python -m pytest -q software/ai/tests/test_temperature_visibility.py`
- Result: PASS,4 tests; initialization,pooling agreement,gradient routing,hashes,pixels,selection,criteria,parity recounts and exact GPU reproduction verified. Existing pytest-asyncio warning.
- Artifacts: software/ai/tests/test_temperature_visibility.py
- Hardware writes: 0
- Physical movements: 0
- Limitations: Consistency tests do not qualify a model. Batch contract unchanged; shared boundary suite not triggered.
- Supersedes: none; historical failures and shared integration status preserved.
- Next dependency: AI-132/133 diagnostics.

### E-20260926-AI-135 — temperature publication audit

- Stage: S1
- Lane: AI
- Commit: `ff92b9d5f3b9faebb9b451e3b3a3e94a342f35ae` (frozen source baseline; results/tests committed with evidence)
- Change: temperature publication audit.
- Inputs/fixtures: Repository snapshot with AI-132/133/134 and reviewed fixture allowlist.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS;5876 paths,825.1 MiB,0 unresolved findings,14 reviewed synthetic fixtures.
- Artifacts: audit stdout and snapshot
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic audit; AI-041 protected-main publication blocker remains.
- Supersedes: none; historical failures and shared integration status preserved.
- Next dependency: Protected-branch PR/checks and AI-132 diagnostics.
### E-20260926-ARM-036 — synthetic r97 review integration lane

- Stage: S4
- Lane: ARM
- Change: added a distinct `SYNTHETIC_TEST_ONLY` review origin, deterministic
  offline rehearsal builder, report status, public API, schemas, and tests. The
  AI and arm lanes can now exchange a concrete content-addressed review artifact
  while developing their shared serialization and identity bindings.
- Safety behavior: a structurally correct synthetic review reaches only
  `SYNTHETIC_REHEARSAL_ACCEPTED`. Its report retains
  `SYNTHETIC_EVIDENCE_NOT_INDEPENDENT`, fixes `ready_for_epoch_intake=false`,
  and keeps installation, startup, execution, hardware access, and physical
  authority false. Epoch assessment independently proves the synthetic decision
  remains blocked.
- Artifacts: `build_synthetic_r97_review_rehearsal_v1`,
  `software/scripts/build_r97_synthetic_review_rehearsal.py`, expanded decision
  and report schemas, unit/schema/builder tests, and production documentation.
- Results: generated rehearsal decision SHA-256
  `7b04b99c2c740bbbce4a7cc41e47d158ae2f8be93df6447b9b594e68f9a28c17`
  round-tripped through the strict decoder and remained epoch-ineligible;
  bounded shared AI/arm, r97, runtime, review, epoch, and builder suite PASS,
  255 tests in 16.94 seconds; documentation PASS for 25 maintained documents
  and two SVG assets; snapshot audit PASS for 5,727 paths and 903.9 MiB with
  zero unresolved findings and 14 reviewed synthetic fixtures; diff check PASS.
  Generated output resides only in the ignored local evidence area.
- Hardware writes: 0
- Physical movements: 0
- Limitations: this improves integration coverage only. It is not independent
  review, cannot authenticate a reviewer, and cannot replace measured physical
  evidence or authorize deployment.
- Supersedes: ARM-035 only for synthetic integration usability; the external
  review and every production/physical blocker remain unchanged.
- Next dependency: use this lane for model/arm contract tests while a genuinely
  independent reviewer and measurement owners produce the external evidence
  required by S4.

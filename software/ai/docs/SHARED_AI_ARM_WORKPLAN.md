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

### E-20260926-AI-136 — temperature coordinate decoder diagnosis

- Stage: S1
- Lane: AI
- Commit: `e9e6b07539996716239bd1f88d2c8490b01edeaa` (frozen source; result/tests committed with evidence)
- Change: temperature coordinate decoder diagnosis.
- Inputs/fixtures: 800 reused development images/3200 corners,15M200 groups,four conditions; checkpoint356a4dec05c6c2194c6d31542fed0d7199d5e989eb4b7678888d1a01aa493281. Exact source/input hashes in eval/temperature_bias_v0.manifest.json.
- Command: `python software/ai/vision/diagnose_temperature_bias.py`
- Result: Diagnostic completed; no decoder promotion supported. Clear mean existing/sharpened/peak8.219/7.057/9.237px,p9516.099/27.157/60.008px. Partial mean8.362/12.237/13.697,p9518.232/56.471/83.143px. Hidden mean6.181/8.233/6.178,p9513.724/17.938/11.299px. Fixed0.5 coordinate sharpening worsens clear tails and occluded means. Prior remaining CUDA32 flip image106/corner2 has CPU/GPU distance0.000144124/0.000009775 from0.5.
- Artifacts: eval/temperature_bias_v0_report.json; frozen runner/manifest
- Hardware writes: 0
- Physical movements: 0
- Limitations: CPU diagnostic,reused synthetic data,oracle truth used only for error measurement; no runtime decoder change,calibration or qualification. Visibility temperature and coordinate decoder temperature are separate.
- Supersedes: none; earlier failures and integration statuses preserved.
- Next dependency: Freeze a failure attribution study of heatmap peaks versus semantic corner identity and keyboard geometry; determine corner swaps/multimodality before further model changes. Preserve parity and absolute-error blockers.

### E-20260926-AI-137 — coordinate diagnostic verification

- Stage: S1
- Lane: AI
- Commit: `e9e6b07539996716239bd1f88d2c8490b01edeaa` (frozen source; result/tests committed with evidence)
- Change: coordinate diagnostic verification.
- Inputs/fixtures: AI-136 pinned manifest,3200 rows and prior parity report.
- Command: `python -m pytest -q software/ai/tests/test_temperature_bias.py`
- Result: PASS,1 test; hashes,group counts/means/p95,signed-vector norms and threshold margins independently checked. Existing pytest-asyncio warning.
- Artifacts: software/ai/tests/test_temperature_bias.py
- Hardware writes: 0
- Physical movements: 0
- Limitations: Consistency verification only; batch contract unchanged, shared boundary suite not triggered.
- Supersedes: none; earlier failures and integration statuses preserved.
- Next dependency: AI-136 attribution study.

### E-20260926-AI-138 — coordinate diagnostic publication audit

- Stage: S1
- Lane: AI
- Commit: `e9e6b07539996716239bd1f88d2c8490b01edeaa` (frozen source; result/tests committed with evidence)
- Change: coordinate diagnostic publication audit.
- Inputs/fixtures: Repository with AI-136/137 and reviewed fixture allowlist.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS;5882 paths,827.2 MiB,0 unresolved findings,14 reviewed synthetic fixtures.
- Artifacts: audit stdout and snapshot
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic audit; AI-041 protected-main publication blocker remains.
- Supersedes: none; earlier failures and integration statuses preserved.
- Next dependency: Protected-branch PR/checks and AI-136 diagnosis.

### E-20260926-AI-139 — corner identity and rival peak attribution

- Stage: S1
- Lane: AI
- Commit: `20520312354e67e734f910020295cf156e728fb7` (frozen source; results/tests committed with evidence)
- Change: corner identity and rival peak attribution.
- Inputs/fixtures: 800 reused15M200 images,3200 corners; frozen t05 checkpoint356a4dec05c6c2194c6d31542fed0d7199d5e989eb4b7678888d1a01aa493281. Exact source/input hashes in eval/corner_attribution_v0.manifest.json.
- Command: `python software/ai/vision/diagnose_corner_attribution.py`
- Result: Completed descriptive attribution. Clear/partial/hidden >8px peak errors202/76/17; peaks within8px of another corner1/0/0. Strongest rival outside8px of primary is within8px of correct corner189/52/12; rival also >=0.5 primary strength149/24/8. Thus near-other-corner errors are rare in this definition; alternate responses often retain correct-corner evidence.
- Artifacts: eval/corner_attribution_v0_report.json; frozen runner/manifest
- Hardware writes: 0
- Physical movements: 0
- Limitations: Reused synthetic CPU study; geometric proximity is not confirmed semantic swap, rival may be a broad shoulder, thresholds descriptive only. No oracle selection/runtime calibration, retraining, qualification or boundary change.
- Supersedes: none; prior failures and integration statuses preserved.
- Next dependency: Freeze a bounded geometry-consistency candidate-peak decoder study. Use only predicted peaks and declared synthetic keyboard dimensions at selection, never truth pose/placement; truth only scores results. Retain mean/tail/yaw, visibility and stability criteria; require fresh evaluation before promotion.

### E-20260926-AI-140 — corner attribution verification

- Stage: S1
- Lane: AI
- Commit: `20520312354e67e734f910020295cf156e728fb7` (frozen source; results/tests committed with evidence)
- Change: corner attribution verification.
- Inputs/fixtures: AI-139 manifest and3200 diagnostic rows with pinned source/input hashes.
- Command: `python -m pytest -q software/ai/tests/test_corner_attribution.py`
- Result: PASS,1 test; independently recomputed class counts,proximity and rival intersections,ratio ranges and zero authority. Existing pytest-asyncio warning.
- Artifacts: software/ai/tests/test_corner_attribution.py
- Hardware writes: 0
- Physical movements: 0
- Limitations: Consistency verification only. Batch contract unchanged; shared boundary suite not triggered.
- Supersedes: none; prior failures and integration statuses preserved.
- Next dependency: AI-139 geometry-consistency study.

### E-20260926-AI-141 — corner attribution publication audit

- Stage: S1
- Lane: AI
- Commit: `20520312354e67e734f910020295cf156e728fb7` (frozen source; results/tests committed with evidence)
- Change: corner attribution publication audit.
- Inputs/fixtures: Repository with AI-139/140 and reviewed fixture allowlist.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS;5887 paths,829.8 MiB,0 unresolved findings,14 reviewed synthetic fixtures.
- Artifacts: audit stdout and repository snapshot
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic audit; AI-041 protected-main publication blocker remains.
- Supersedes: none; prior failures and integration statuses preserved.
- Next dependency: Protected-branch PR/checks and AI-139 study.
### E-20260926-ARM-037 — full synthetic review-to-epoch rehearsal

- Stage: S4
- Lane: ARM
- Change: extended the synthetic integration lane across configuration-epoch
  intake. The builder strictly ingests the content-addressed ARM-036 decision,
  deterministically constructs all eight ordered synthetic component records,
  serializes and strictly re-parses the epoch, and runs the unchanged production
  assessment.
- Safety behavior: rehearsal success requires the production report to remain
  `BLOCKED` with exactly `FIRMWARE_REVIEW_DECISION_BLOCKED` and
  `COMPONENT_NOT_PHYSICAL_ORIGINAL`. Epoch-bound build proposal, installation,
  startup, execution, hardware access, and physical authority remain false.
- Artifact identity: synthetic configuration epoch SHA-256
  `671c044b48b9f3aaac2e5f260a6b8c948f6c2a060451730d015b9431d46cf6c6`;
  assessment report SHA-256
  `0c560ec3228fb29ebb676684f62d810e3c456ed42dd6dd5ad11e98be64345ea4`;
  input review decision SHA-256
  `7b04b99c2c740bbbce4a7cc41e47d158ae2f8be93df6447b9b594e68f9a28c17`.
- Artifacts: strict epoch JSON decoder,
  `build_synthetic_controller_configuration_epoch_rehearsal_v1`,
  `software/scripts/build_synthetic_configuration_epoch_rehearsal.py`, unit and
  builder tests, ignored local decision/intake/report evidence, and updated
  production documentation.
- Results: bounded shared AI/arm, r97, runtime, review, epoch, and builder suite
  PASS, 260 tests in 17.10 seconds; documentation PASS for 25 maintained
  documents and two SVG assets; snapshot audit PASS for 5,730 paths and 903.9
  MiB with zero unresolved findings and 14 reviewed synthetic fixtures; diff
  check PASS. Generated output resides only in the ignored local evidence area.
- Hardware writes: 0
- Physical movements: 0
- Limitations: every component is synthetic and every component review hash is
  simulated. This proves interface compatibility and fail-closed behavior only,
  not workcell measurement, reviewer independence, or controller readiness.
- Supersedes: ARM-036 only for full synthetic epoch integration coverage; all
  external-review, measured-evidence, installation, and physical blockers remain.
- Next dependency: connect the model/arm offline integration harness to this
  strict epoch fixture while physical measurement owners and an independent
  reviewer produce the evidence required for production admission.

### E-20260926-ARM-038 — synthetic epoch through model-to-arm encoding

- Stage: S4
- Lane: ARM
- Change: added a typed cross-layer assessor that binds the exact ARM-036
  synthetic review decision and ARM-037 eight-component epoch to a real v2
  model-motion batch, its indexed proposal, a sealed trajectory, a matching
  Waveshare T=102 profile, and the transport-free preview receipt. The portable
  offline CI selection now includes this integration boundary.
- Safety behavior: rehearsal success requires the unchanged epoch assessment to
  remain `BLOCKED` with exactly `FIRMWARE_REVIEW_DECISION_BLOCKED` and
  `COMPONENT_NOT_PHYSICAL_ORIGINAL`. Crossed epoch, batch, proposal, profile, or
  receipt identities reject. The resulting report fixes production dispatch,
  installation, startup, execution, retry, hardware access, and physical
  authority false; it creates no runtime frame or dispatch permit.
- Artifact identity: review decision SHA-256
  `7b04b99c2c740bbbce4a7cc41e47d158ae2f8be93df6447b9b594e68f9a28c17`;
  configuration epoch SHA-256
  `671c044b48b9f3aaac2e5f260a6b8c948f6c2a060451730d015b9431d46cf6c6`;
  model batch SHA-256
  `133a24fec9e136909d31ce1a7529ef00d5a9977bc2a17806c1bf2d95c9932544`;
  preview receipt SHA-256
  `ee03428d9b91f5fbd3d457c8dbddc50739c81eac9a46135a66e98e32f8e5adfd`;
  combined rehearsal report SHA-256
  `5b3b2c7d2c445770d7d16ee2c8f3e53cae5e6f6eff9d10e1406c983840d5beeb`.
- Artifacts: `synthetic_epoch_model_arm_rehearsal_v1.py`, closed JSON schema,
  positive/tamper integration tests, public application exports, portable CI
  inclusion, and shared model/runtime documentation.
- Results: exact lineage produced one reviewable encoded command and zero
  writes; bounded shared AI/arm, review, epoch, envelope, and encoding suite
  PASS, 221 tests in 18.04 seconds; focused new integration suite PASS, 4 tests
  in 1.26 seconds; documentation PASS for 25 maintained documents and two SVG
  assets; snapshot audit PASS for 5,733 paths and 903.9 MiB with zero unresolved
  findings and 14 reviewed synthetic fixtures. The isolated CI helper could not
  run locally because `.venv-ci` was absent; its exact test list passed under
  the active offline Python environment and protected CI remains required.
- Hardware writes: 0
- Physical movements: 0
- Limitations: the planner-ready trajectory is a synthetic test fixture and the
  encoded command is inspection evidence only. This proves identity and schema
  compatibility, not real perception accuracy, measured calibration, collision
  completeness, installed-controller qualification, or physical execution.
- Supersedes: ARM-037 only for downstream model-to-encoder integration coverage;
  all independent-review, measured-evidence, installation, and physical-use
  blockers remain.
- Next dependency: have the AI lane emit independently evaluated batches against
  this unchanged interface, while the arm lane replaces synthetic trajectory and
  epoch inputs only after measured calibration, collision, controller, and review
  evidence independently qualify.

### E-20260926-AI-142 — geometry candidate decoder development study

- Stage: S1
- Lane: AI
- Commit: `db5f956d5cbdf7b340d2a971b9eb317c56a703de` (frozen source; results/tests committed with evidence)
- Change: geometry candidate decoder development study.
- Inputs/fixtures: 800 reused15M200 images,four conditions,t05 checkpoint356a4dec05c6c2194c6d31542fed0d7199d5e989eb4b7678888d1a01aa493281; exact hashes in eval/geometry_candidate_v0_plan.json.
- Command: `python software/ai/vision/evaluate_geometry_candidates.py`
- Result: PASS all12 relative development mean/tail/yaw checks. Soft→geometry means standard7.713→5.946,appearance11.529→4.716,partial10.465→6.312,full10.659→6.550mm. >3mm tails194→183,196→168,197→180,198→192/200. Geometry yawp952.046/1.724/2.265/2.151deg. Two predicted candidates per corner,16 combinations; fixed residual_mm2/16 plus mean negative log probability, rigid315x147mm synthetic rectangle. Truth only scores results.
- Artifacts: eval/geometry_candidate_v0_report.json; decoder/runner/frozen plan
- Hardware writes: 0
- Physical movements: 0
- Limitations: Relative development pass only; absolute tails remain unacceptable. Reused synthetic dimensions/projection are not measured calibration. Unconditional hidden-corner decoding, existing visibility/parity blockers retained; no qualification or boundary changes.
- Supersedes: none; previous failures and integration statuses preserved.
- Next dependency: Freeze fresh27M500-group evaluation of unchanged decoder/checkpoint/cost across same four conditions before any further tuning; retain absolute metrics and all existing qualification blockers.

### E-20260926-AI-143 — geometry decoder verification

- Stage: S1
- Lane: AI
- Commit: `db5f956d5cbdf7b340d2a971b9eb317c56a703de` (frozen source; results/tests committed with evidence)
- Change: geometry decoder verification.
- Inputs/fixtures: Analytic rotated/translated rectangle plus AI-142 pinned report/manifest.
- Command: `python -m pytest -q software/ai/tests/test_geometry_candidates.py`
- Result: PASS,2 tests; rigid fit, hashes,800 rows,mean/tail recounts and relative gates verified. Existing pytest-asyncio warning.
- Artifacts: software/ai/tests/test_geometry_candidates.py
- Hardware writes: 0
- Physical movements: 0
- Limitations: Implementation verification is not qualification. Batch contract unchanged; shared boundary suite not triggered.
- Supersedes: none; previous failures and integration statuses preserved.
- Next dependency: AI-142 fresh evaluation.

### E-20260926-AI-144 — geometry publication audit

- Stage: S1
- Lane: AI
- Commit: `db5f956d5cbdf7b340d2a971b9eb317c56a703de` (frozen source; results/tests committed with evidence)
- Change: geometry publication audit.
- Inputs/fixtures: Repository with AI-142/143 and reviewed fixture allowlist.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS;5897 paths,830.4 MiB,0 unresolved findings,14 reviewed synthetic fixtures.
- Artifacts: audit stdout and snapshot
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic audit; AI-041 protected-main publication blocker remains.
- Supersedes: none; previous failures and integration statuses preserved.
- Next dependency: Protected-branch PR/checks and AI-142 fresh evaluation.

### E-20260926-AI-145 — fresh geometry decoder evaluation

- Stage: S1
- Lane: AI
- Commit: `5b4ed1df56fb24145fd1bb6a42a9cd777afe57ef` (frozen source; results/tests committed with evidence)
- Change: fresh geometry decoder evaluation.
- Inputs/fixtures: Fresh seeds27000000..27000499,500 groups x4 conditions=2000 images; unchanged decoder/cost and t05 checkpoint356a4dec05c6c2194c6d31542fed0d7199d5e989eb4b7678888d1a01aa493281. Exact source/input hashes in eval/geometry_candidate_fresh_v0_plan.json.
- Command: `python software/ai/vision/evaluate_geometry_candidates_fresh.py`
- Result: PASS all12 relative checks. Soft→geometry means standard10.244→5.975,appearance13.809→4.586,partial12.925→6.167,full13.080→6.295mm. >3mm tails484→458,497→426,494→459,498→466/500. Geometry yawp952.113/1.708/2.227/1.988deg. Absolute failure prevalence85.2–93.2% remains unacceptable; no qualification.
- Artifacts: eval/geometry_candidate_fresh_v0_report.json; frozen runner/plan
- Hardware writes: 0
- Physical movements: 0
- Limitations: Fresh random groups from same synthetic generator, not real camera or distribution shift qualification. Synthetic geometry/projection not measured calibration. Visibility/device stability not reevaluated; prior blockers retained.27M split now consumed; do not reuse as fresh.
- Supersedes: none; failed evidence and integration status retained.
- Next dependency: Return to development data and decompose residual translation/orientation and grid-quantization errors before choosing a subpixel refinement. Preserve fixed decoder and fresh evidence; any changed candidate needs a new untouched split.

### E-20260926-AI-146 — fresh geometry verification

- Stage: S1
- Lane: AI
- Commit: `5b4ed1df56fb24145fd1bb6a42a9cd777afe57ef` (frozen source; results/tests committed with evidence)
- Change: fresh geometry verification.
- Inputs/fixtures: Analytic rigid rectangle,AI-145 manifest and2000 rows.
- Command: `python -m pytest -q software/ai/tests/test_geometry_candidates_fresh.py`
- Result: PASS,2 tests; hashes,rigid fit,exact500 seeds/four conditions,unique cases,mean/tail counts and comparison gates verified. Existing pytest-asyncio warning.
- Artifacts: software/ai/tests/test_geometry_candidates_fresh.py
- Hardware writes: 0
- Physical movements: 0
- Limitations: Implementation verification does not qualify localization. Batch contract unchanged; shared boundary suite not triggered.
- Supersedes: none; failed evidence and integration status retained.
- Next dependency: AI-145 development residual decomposition.

### E-20260926-AI-147 — fresh geometry publication audit

- Stage: S1
- Lane: AI
- Commit: `5b4ed1df56fb24145fd1bb6a42a9cd777afe57ef` (frozen source; results/tests committed with evidence)
- Change: fresh geometry publication audit.
- Inputs/fixtures: Repository snapshot with AI-145/146 and reviewed fixture allowlist.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS;5901 paths,831.8 MiB,0 unresolved findings,14 reviewed synthetic fixtures.
- Artifacts: audit stdout and snapshot
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic audit; AI-041 protected-main publication blocker remains.
- Supersedes: none; failed evidence and integration status retained.
- Next dependency: Protected-branch PR/checks and AI-145 development diagnosis.

### E-20260926-AI-148 — development geometry residual decomposition

- Stage: S1
- Lane: AI
- Commit: `03b4779971bb22804955eef77bd9122caa02be3d` (frozen source; results/tests committed with evidence)
- Change: development geometry residual decomposition.
- Inputs/fixtures: AI-142 retained800 development rows,15M200 groups,four conditions; exact source/input hashes in eval/geometry_residual_v0_plan.json. Fresh27M evidence not used.
- Command: `python software/ai/vision/diagnose_geometry_residual.py`
- Result: Diagnostic completed. Actual means standard/appearance/partial/full5.946/4.716/6.312/6.550mm; translation-only5.856/4.521/6.165/6.400; rotation-only0.918/0.943/1.131/1.049. Translation p9510.148/9.437/10.821/10.906mm. Oracle nearest4px-grid truth corners fitted to rectangle give1.767mm mean and45/200 >3mm images in each condition. Exact actual metrics reproduced.
- Artifacts: eval/geometry_residual_v0_report.json; frozen runner/plan
- Hardware writes: 0
- Physical movements: 0
- Limitations: Oracle counterfactuals are diagnostic only, not deployable corrections or measured calibration. Components nonadditive. Nearest-grid reference is not a universal lower bound. No runtime change,qualification or integration gate completion.
- Supersedes: none; prior failures and integration statuses retained.
- Next dependency: Freeze fixed3x3 probability-weighted subpixel refinement of already-selected candidates, leaving combination choice/cost unchanged. Evaluate on development before allocating new fresh split; no oracle selection or offsets.

### E-20260926-AI-149 — geometry decomposition verification

- Stage: S1
- Lane: AI
- Commit: `03b4779971bb22804955eef77bd9122caa02be3d` (frozen source; results/tests committed with evidence)
- Change: geometry decomposition verification.
- Inputs/fixtures: AI-148 manifest/report and pinned AI-142 predictions.
- Command: `python -m pytest -q software/ai/tests/test_geometry_residual.py`
- Result: PASS,1 test; hashes,800 case identities,exact actual reproduction,translation-only identity and summary counts/means verified. Existing pytest-asyncio warning.
- Artifacts: software/ai/tests/test_geometry_residual.py
- Hardware writes: 0
- Physical movements: 0
- Limitations: Implementation consistency only; batch contract unchanged,shared boundary tests not triggered.
- Supersedes: none; prior failures and integration statuses retained.
- Next dependency: AI-148 subpixel experiment.

### E-20260926-AI-150 — residual publication audit

- Stage: S1
- Lane: AI
- Commit: `03b4779971bb22804955eef77bd9122caa02be3d` (frozen source; results/tests committed with evidence)
- Change: residual publication audit.
- Inputs/fixtures: Repository with AI-148/149 and reviewed fixture allowlist.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS;5905 paths,832.4 MiB,0 unresolved findings,14 reviewed synthetic fixtures.
- Artifacts: audit stdout and snapshot
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic audit; AI-041 protected-main publication blocker remains.
- Supersedes: none; prior failures and integration statuses retained.
- Next dependency: Protected-branch PR/checks and AI-148 experiment.
### E-20260926-ARM-039 — actual AI-emitter bytes through arm admission

- Stage: S2/S4 bridge
- Lane: ARM
- Change: replaced the hand-built batch at the producer/consumer seam with the
  exact canonical bytes returned by `rocell_ai.batch_emitter_v2.assemble` for a
  synthetic qualified-shape observation fixture. The arm decoder, registry
  ingress, freshness gate, and measured planner consume that same payload. A
  separate synthetic-ready planner copy is used only to prove that the admitted
  batch/proposal identity can continue through the ARM-038 epoch and zero-write
  encoding rehearsal.
- Safety behavior: the measured planner must remain
  `BLOCKED_CALIBRATION_MISSING_OR_STALE` with next stage
  `COMMISSION_REQUIRED_CALIBRATIONS`; any crossed or tampered payload, ingress,
  freshness, planner, proposal, epoch, or preview identity rejects. The report
  fixes production dispatch, installation, controller startup, execution,
  retry, hardware access, and physical authority false.
- Artifact identity: canonical emitter payload SHA-256
  `9e64e21670aa4545a4ea326bf122716e8b40eac4b86ae1d7e80141553f9a779e`;
  model batch SHA-256
  `260c2ed2ae641c3a350637db2d784c43a42d1f440846a2514d2a6c46e1e9c980`;
  intent plan SHA-256
  `682eabd41a40d5516d87b9b26e97eb9ca9276eca519d1b3f3a8422e5676f2c81`;
  ingress SHA-256
  `402b25b4f7c6d4b0b0fef8da57cdb32086c3401934aed8d55a124ea5f78e3d12`;
  freshness gate SHA-256
  `b69f0e032737f8f0042d7ec968735aa3877ef1eeb9a8d0d96597f91780ae0c4c`;
  measured planner gate SHA-256
  `ba29c35e895e352081990daf242d0671823b262604f7bdf09c16bcd2dbc409a7`;
  configuration epoch SHA-256
  `671c044b48b9f3aaac2e5f260a6b8c948f6c2a060451730d015b9431d46cf6c6`;
  preview receipt SHA-256
  `06562a60f2babc2dc06faf3dd93879d7b0f550fd73ad8d14248e1e808fc0e6bc`;
  combined report SHA-256
  `de86a22022f57f6c579300b3d933888ff24e46f466cb8d517f29f6aba4f735bc`.
- Artifacts: `ai_emitted_epoch_model_arm_rehearsal_v1.py`, closed JSON
  schema, real-emitter integration/tamper tests, public application exports,
  portable CI inclusion, and shared status/assurance documentation.
- Results: focused integration suite PASS, 4 tests in 1.82 seconds; bounded
  shared AI/arm suite PASS, 225 tests in 18.37 seconds; documentation PASS for
  25 maintained documents and two SVG assets; snapshot audit PASS for 5,736
  paths and 903.9 MiB with zero unresolved findings and 14 reviewed synthetic
  fixtures; diff check PASS. Protected CI remains required before merge.
- Hardware writes: 0
- Physical movements: 0
- Limitations: the AI emitter is real code, but its input here is a synthetic
  evidence fixture, not an independently evaluated model prediction. The AI
  research lane's current localization and uncertainty failures remain retained
  and unpromoted, and the stable batch contract is unchanged. The measured
  planner produced no trajectory because commissioned calibration is absent;
  the downstream trajectory and controller bytes remain synthetic inspection
  evidence only.
- Supersedes: ARM-038 only for the AI-producer-to-arm-consumer seam. ARM-038's
  downstream synthetic proof and every physical-use blocker remain.
- Next dependency: the AI lane must independently qualify an emitted batch
  without changing the shared contract, while the arm lane must commission
  measured calibration, collision, installed-controller, and review evidence
  before any physical admission.

### E-20260926-AI-151 — selected candidate subpixel development comparison

- Stage: S1
- Lane: AI
- Commit: `d17b76d53ac6d9a311d83fe9538094229f1098ad` (frozen source; results/tests committed with evidence)
- Change: selected candidate subpixel development comparison.
- Inputs/fixtures: 800 reused15M200 images,four conditions,t05 checkpoint356a4dec05c6c2194c6d31542fed0d7199d5e989eb4b7678888d1a01aa493281. Exact source/input hashes in eval/subpixel_candidate_v0_plan.json.
- Command: `python software/ai/vision/evaluate_subpixel_candidates.py`
- Result: PASS all12 relative checks. Grid→subpixel mean standard5.946→3.040,appearance4.716→2.450,partial6.312→4.773,full6.550→5.236mm. >3mm tails183→125,168→77,180→172,192→186/200. Refined yawp951.285/1.236/1.594/1.523deg. Candidate choices/cost unchanged; fixed clipped3x3 probability centroid then same rigid fit.
- Artifacts: eval/subpixel_candidate_v0_report.json; decoder/runner/frozen plan
- Hardware writes: 0
- Physical movements: 0
- Limitations: Development pass only; absolute errors and occlusion tails remain high. Synthetic projection/dimensions not measured calibration; visibility/device-stability blockers remain. No qualification or batch-boundary change.
- Supersedes: none; prior failures and integration statuses retained.
- Next dependency: Freeze fresh28M500-group evaluation of unchanged refinement/checkpoint/selection before further tuning;27M consumed. No runtime promotion.

### E-20260926-AI-152 — subpixel verification

- Stage: S1
- Lane: AI
- Commit: `d17b76d53ac6d9a311d83fe9538094229f1098ad` (frozen source; results/tests committed with evidence)
- Change: subpixel verification.
- Inputs/fixtures: Analytic rigid rectangle,AI-151 manifest/800 rows and retained AI-142 report.
- Command: `python -m pytest -q software/ai/tests/test_subpixel_candidates.py`
- Result: PASS,2 tests; hashes,rigid fit,metrics/gates and exact unchanged candidate choices/original poses/grid scores verified. Existing pytest-asyncio warning.
- Artifacts: software/ai/tests/test_subpixel_candidates.py
- Hardware writes: 0
- Physical movements: 0
- Limitations: Implementation verification only; boundary unchanged,shared boundary suite not triggered.
- Supersedes: none; prior failures and integration statuses retained.
- Next dependency: AI-151 fresh evaluation.

### E-20260926-AI-153 — subpixel publication audit

- Stage: S1
- Lane: AI
- Commit: `d17b76d53ac6d9a311d83fe9538094229f1098ad` (frozen source; results/tests committed with evidence)
- Change: subpixel publication audit.
- Inputs/fixtures: Repository with AI-151/152 and reviewed fixture allowlist.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS;5913 paths,833.0 MiB,0 unresolved findings,14 reviewed synthetic fixtures.
- Artifacts: audit stdout and repository snapshot
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic audit; AI-041 protected-main publication blocker remains.
- Supersedes: none; prior failures and integration statuses retained.
- Next dependency: Protected-branch PR/checks and AI-151 fresh evaluation.

### E-20260926-AI-154 — fresh subpixel evaluation

- Stage: S1
- Lane: AI
- Commit: `0fcabf20a80d825746bd561b69af9aaf7d8d5f69` (frozen source; results/tests committed with evidence)
- Change: fresh subpixel evaluation.
- Inputs/fixtures: Fresh seeds28000000..28000499,500 groups x4 conditions=2000 images. Unchanged refinement/selection/cost and t05 checkpoint356a4dec05c6c2194c6d31542fed0d7199d5e989eb4b7678888d1a01aa493281; exact hashes in eval/subpixel_candidate_fresh_v0_plan.json.
- Command: `python software/ai/vision/evaluate_subpixel_candidates_fresh.py`
- Result: PASS all12 relative checks. Grid→subpixel means standard6.057→3.315,appearance4.456→2.418,partial6.210→4.792,full6.622→5.478mm. >3mm tails470→361,421→183,462→436,476→470/500. Refined yawp951.381/1.283/1.616/1.512deg. Absolute occlusion error prevalence87.2–94% remains unacceptable; no qualification.
- Artifacts: eval/subpixel_candidate_fresh_v0_report.json; frozen runner/plan
- Hardware writes: 0
- Physical movements: 0
- Limitations: Same synthetic generator,not camera distribution qualification; dimensions/projection not measured calibration. Visibility/device parity blockers remain.28M split now consumed; no tuning on this result.
- Supersedes: none; historical failures and shared integration status retained.
- Next dependency: Return to15M development and freeze predicted-visibility-weighted rigid fitting of refined selected corners, with explicit abstention for fewer than three supported corners. Evaluate coverage plus accepted errors; no oracle visibility or threshold tuning.

### E-20260926-AI-155 — fresh subpixel verification

- Stage: S1
- Lane: AI
- Commit: `0fcabf20a80d825746bd561b69af9aaf7d8d5f69` (frozen source; results/tests committed with evidence)
- Change: fresh subpixel verification.
- Inputs/fixtures: Analytic rectangle,AI-154 pinned manifest and2000 rows.
- Command: `python -m pytest -q software/ai/tests/test_subpixel_candidates_fresh.py`
- Result: PASS,2 tests; hashes,exact500 seeds,four conditions,unique cases,rigid fit and relative metric gates verified. Existing pytest-asyncio warning.
- Artifacts: software/ai/tests/test_subpixel_candidates_fresh.py
- Hardware writes: 0
- Physical movements: 0
- Limitations: Consistency tests do not qualify localization; batch unchanged,shared boundary suite not triggered.
- Supersedes: none; historical failures and shared integration status retained.
- Next dependency: AI-154 development occlusion-aware fit.

### E-20260926-AI-156 — fresh subpixel publication audit

- Stage: S1
- Lane: AI
- Commit: `0fcabf20a80d825746bd561b69af9aaf7d8d5f69` (frozen source; results/tests committed with evidence)
- Change: fresh subpixel publication audit.
- Inputs/fixtures: Repository with AI-154/155 and reviewed fixture allowlist.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS;5918 paths,834.7 MiB,0 unresolved findings,14 reviewed synthetic fixtures.
- Artifacts: audit stdout and snapshot
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic audit; AI-041 protected-main publication blocker remains.
- Supersedes: none; historical failures and shared integration status retained.
- Next dependency: Protected-branch PR/checks and AI-154 development study.

### E-20260926-AI-157 — visibility weighted fit development study

- Stage: S1
- Lane: AI
- Commit: `7cb6012e61febd434718967b5cad0801124db13f` (frozen source; results/tests committed with evidence)
- Change: visibility weighted fit development study.
- Inputs/fixtures: 800 reused15M200 images,four conditions,t05 checkpoint356a4dec05c6c2194c6d31542fed0d7199d5e989eb4b7678888d1a01aa493281; exact hashes in eval/visible_candidate_v0_plan.json.
- Command: `python software/ai/vision/evaluate_visible_candidates.py`
- Result: FAIL overall. Coverage standard/appearance/partial/full200/200/194/192 of200 (100/100/97/96%). Same accepted subset subpixel→weighted means3.040→3.038,2.450→2.462,4.757→4.375,5.045→3.965mm. >3mm tails125→132,77→85,166→162,178→156. Full yawp951.480→1.658 exceeds1.1x; standard/appearance tails and appearance mean fail. Predicted0.5 support,minimum3,probability-weighted rigid fit; abstentions retained.
- Artifacts: eval/visible_candidate_v0_report.json; frozen decoder/runner/plan
- Hardware writes: 0
- Physical movements: 0
- Limitations: Uncalibrated visibility,synthetic development,all-corner candidate selection still unchanged. No qualification or boundary change; prior visibility/device parity blockers remain.
- Supersedes: none; failures and integration statuses retained.
- Next dependency: Freeze a bounded ablation separating hard visibility support (equal weights among supported corners) from probability weighting on the same development cases. This tests whether continuous weights harm clear scenes without oracle visibility or threshold tuning.

### E-20260926-AI-158 — visibility weighted fit verification

- Stage: S1
- Lane: AI
- Commit: `7cb6012e61febd434718967b5cad0801124db13f` (frozen source; results/tests committed with evidence)
- Change: visibility weighted fit verification.
- Inputs/fixtures: Analytic rotated rectangle with excluded corrupted corner,abstention case,and AI-157 pinned report.
- Command: `python -m pytest -q software/ai/tests/test_visible_candidates.py`
- Result: PASS,2 tests; weighted transform,minimum support,hashes,coverage,same-subset metrics and gates verified. Existing pytest-asyncio warning.
- Artifacts: software/ai/tests/test_visible_candidates.py
- Hardware writes: 0
- Physical movements: 0
- Limitations: Consistency checks not qualification; batch unchanged,shared boundary suite not triggered.
- Supersedes: none; failures and integration statuses retained.
- Next dependency: AI-157 support/weight ablation.

### E-20260926-AI-159 — visibility fit publication audit

- Stage: S1
- Lane: AI
- Commit: `7cb6012e61febd434718967b5cad0801124db13f` (frozen source; results/tests committed with evidence)
- Change: visibility fit publication audit.
- Inputs/fixtures: Repository with AI-157/158 and reviewed fixture allowlist.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS;5923 paths,835.7 MiB,0 unresolved findings,14 reviewed synthetic fixtures.
- Artifacts: audit stdout and snapshot
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic audit; AI-041 protected-main publication blocker remains.
- Supersedes: none; failures and integration statuses retained.
- Next dependency: Protected-branch PR/checks and AI-157 ablation.

### E-20260926-AI-160 — equal support weighting ablation

- Stage: S1
- Lane: AI
- Commit: `99db4efb6114abb4f4b91aca18c31ea90e39d0e2` (frozen source; results/tests committed with evidence)
- Change: equal support weighting ablation.
- Inputs/fixtures: Retained AI-157800 development predictions,15M200 groups,four conditions. Exact source/input hashes in eval/equal_support_v0_plan.json; identical refined points,support and abstentions.
- Command: `python software/ai/vision/evaluate_equal_support.py`
- Result: FAIL overall versus both references; all16 checks versus probability weighting pass. Equal means standard/appearance/partial/full3.008/2.386/4.283/3.904mm; tails127/80/161/154 on200/200/194/192 accepted. Original subpixel tails125/77/166/178; first two regress. Full yawp951.643 exceeds1.1x original1.480. Coverage100/100/97/96%. Mean criterion predeclared nonincrease(1e-12 tolerance),allowing exact all-supported equivalence.
- Artifacts: eval/equal_support_v0_report.json; frozen runner/plan
- Hardware writes: 0
- Physical movements: 0
- Limitations: Reused synthetic evidence; no oracle support,no calibration,qualification or runtime promotion. Remaining support exclusions matter beyond continuous weights.
- Supersedes: none; historical failures and integration status retained.
- Next dependency: Freeze per-case support-error attribution: false exclusions versus true obstruction and translation/yaw effects. Use oracle visibility only for labeled diagnostic strata,never runtime fitting; retain rejected/accepted cases and all failures.

### E-20260926-AI-161 — equal support verification

- Stage: S1
- Lane: AI
- Commit: `99db4efb6114abb4f4b91aca18c31ea90e39d0e2` (frozen source; results/tests committed with evidence)
- Change: equal support verification.
- Inputs/fixtures: AI-160 manifest/report and retained AI-157800 rows.
- Command: `python -m pytest -q software/ai/tests/test_equal_support.py`
- Result: PASS,1 test; hashes,case identities,acceptance,unchanged references,means/tails and comparison criteria verified. Existing pytest-asyncio warning.
- Artifacts: software/ai/tests/test_equal_support.py
- Hardware writes: 0
- Physical movements: 0
- Limitations: Consistency verification only; batch unchanged,shared boundary suite not triggered.
- Supersedes: none; historical failures and integration status retained.
- Next dependency: AI-160 support attribution.

### E-20260926-AI-162 — equal support publication audit

- Stage: S1
- Lane: AI
- Commit: `99db4efb6114abb4f4b91aca18c31ea90e39d0e2` (frozen source; results/tests committed with evidence)
- Change: equal support publication audit.
- Inputs/fixtures: Repository with AI-160/161 and reviewed fixture allowlist.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS;5927 paths,836.3 MiB,0 unresolved findings,14 reviewed synthetic fixtures.
- Artifacts: audit stdout and snapshot
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic audit; AI-041 protected-main publication blocker remains.
- Supersedes: none; historical failures and integration status retained.
- Next dependency: Protected-branch PR/checks and AI-160 diagnosis.
### E-20260926-ARM-040 — installed measured collision profile at planner seam

- Stage: S3
- Lane: ARM
- Change: connected the existing strict installed collision-geometry profile
  to measured trajectory screening and both v1/v2 model-motion planner entry
  points. New screening reports use the additive v2 schema and bind the geometry
  source, collision contract, installed-profile content, and measured
  clearance-policy hashes. The frozen v1 schema remains unchanged.
- Safety behavior: the screener rechecks manifest, manifest hash, active build,
  build snapshot, robot model, and base-contract lineage. A typed profile from
  another context rejects. A diagnostically complete installed profile removes
  only `FULL_COLLISION_GEOMETRY_INCOMPLETE`; it necessarily retains
  `CONTINUOUS_FULL_BODY_COLLISION_SWEEP_NOT_IMPLEMENTED`, with full collision
  screening, continuous-clearance proof, commands, hardware access, and
  physical authority all false.
- Artifacts: `measured_trajectory_screening.py`, planner-gate propagation,
  `measured_trajectory_screening_v2.schema.json`, positive/crossed-build unit
  tests, portable CI inclusion, and shared status/assurance documentation.
- Artifact identity: measured trajectory screening implementation SHA-256
  `9aaccc382534663c80b8dc03840934d52af07100b79d75e492122a911aaa6d61`;
  v2 report schema SHA-256
  `0e0676a67eefd1c7feb3784f07e7590b425ba93c3dcd20bdf62d0f20d0e6a2c3`.
- Results: focused planner/screening integration suite PASS, 36 tests in 6.19
  seconds; expanded shared AI/arm suite PASS, 237 tests in 22.25 seconds;
  documentation PASS for 26 maintained documents and two SVG assets; snapshot
  audit PASS for 5,738 paths and 904.0 MiB with zero unresolved findings and 14
  reviewed synthetic fixtures; diff check PASS. Protected CI remains required
  before merge.
- Hardware writes: 0
- Physical movements: 0
- Limitations: no measured installed profile has been supplied by the workcell;
  tests use typed measured-shape fixtures. No per-waypoint rigid-body transforms,
  deformable cable samples, phase-local contact allowances, or continuous sweep
  implementation exist in this increment.
- Supersedes: no physical evidence. This closes the previously disconnected
  installed-profile/planner seam while preserving every calibration, collision,
  controller, review, and physical-use blocker.
- Next dependency: implement deterministic per-waypoint full-body and cable
  collision evaluation against this exact profile, then qualify it with
  independently measured installed geometry and conservative clearance data.

### E-20260926-AI-163 — support exclusion attribution

- Stage: S1
- Lane: AI
- Commit: `2cbe9584af422a35821caa3db1794f9cbee04600` (frozen source; results/tests committed with evidence)
- Change: support exclusion attribution.
- Inputs/fixtures: Retained AI-157/160800 development predictions,15M200 groups; regenerated geometric labels used only for strata. Exact source/input hashes in eval/support_attribution_v0_plan.json.
- Command: `python software/ai/vision/diagnose_support_attribution.py`
- Result: Diagnostic completed. No-exclusion412 cases,all accepted,exact0 metric changes. Clear-only8 accepted cases:8 false exclusions,2 new/2 recovered >3mm tails,mean delta+0.04974mm. Occluded-only374 cases,366 accepted/8 abstained:23 new/47 recovered tails,mean delta-0.90375mm,translation delta-1.00919mm,yaw delta+0.10634deg. Mixed6 cases all abstained. Thus true geometric obstruction exclusions also produce regressions; false clear exclusion alone does not explain them.
- Artifacts: eval/support_attribution_v0_report.json; frozen runner/plan
- Hardware writes: 0
- Physical movements: 0
- Limitations: Geometric visibility not perceptual confidence; partial obstruction counted as occluded,not necessarily unusable. Associations,not causal proof; no oracle fitting,qualification or boundary change.
- Supersedes: none; prior failures and integration statuses retained.
- Next dependency: Freeze fixed half-weight retention of predicted-unsupported corners versus zero-weight exclusion,keeping min3 support and equal weights on supported corners. This tests geometric information loss with one predeclared0.5 weight,no sweep; compare against both original subpixel and equal-support fits on identical accepted cases.

### E-20260926-AI-164 — support attribution verification

- Stage: S1
- Lane: AI
- Commit: `2cbe9584af422a35821caa3db1794f9cbee04600` (frozen source; results/tests committed with evidence)
- Change: support attribution verification.
- Inputs/fixtures: AI-163 pinned manifest/800 rows.
- Command: `python -m pytest -q software/ai/tests/test_support_attribution.py`
- Result: PASS,1 test; hashes,geometric classes,accepted/abstained counts,new/recovered tails and all mean deltas independently recounted. Existing pytest-asyncio warning.
- Artifacts: software/ai/tests/test_support_attribution.py
- Hardware writes: 0
- Physical movements: 0
- Limitations: Consistency verification only; batch unchanged,shared boundary suite not triggered.
- Supersedes: none; prior failures and integration statuses retained.
- Next dependency: AI-163 retention experiment.

### E-20260926-AI-165 — support attribution publication audit

- Stage: S1
- Lane: AI
- Commit: `2cbe9584af422a35821caa3db1794f9cbee04600` (frozen source; results/tests committed with evidence)
- Change: support attribution publication audit.
- Inputs/fixtures: Repository with AI-163/164 and reviewed fixture allowlist.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS;5932 paths,836.7 MiB,0 unresolved findings,14 reviewed synthetic fixtures.
- Artifacts: audit stdout and snapshot
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic audit; AI-041 protected-main publication blocker remains.
- Supersedes: none; prior failures and integration statuses retained.
- Next dependency: Protected-branch PR/checks and AI-163 experiment.

### E-20260926-AI-166 — half weight retention experiment

- Stage: S1
- Lane: AI
- Commit: `dfacdba3c7d27893867977f37f64b8c0af67f833` (frozen source; results/tests committed with evidence)
- Change: half weight retention experiment.
- Inputs/fixtures: Retained AI-157/160800 development predictions; exact hashes in eval/half_support_v0_plan.json. Same points,support0.5,min3,accepted200/200/194/192.
- Command: `python software/ai/vision/evaluate_half_support.py`
- Result: FAIL overall. Half-retention means standard/appearance/partial/full3.011/2.417/4.319/4.394mm; >3mm tails124/79/157/175. Versus original subpixel appearance tail77→79 fails. Versus equal-support all means regress and full tails154→175 regress; full yaw improves1.643→1.512deg. Original min3 gate retained before fitting; supported weight1,unsupported0.5. Output arm equal is documented half-retention candidate.
- Artifacts: eval/half_support_v0_report.json; frozen runner/plan
- Hardware writes: 0
- Physical movements: 0
- Limitations: Reused synthetic evidence,uncalibrated support,not a runtime policy. No qualification or batch changes; failed criteria retained.
- Supersedes: none; prior failures and integration statuses retained.
- Next dependency: Stop fixed-weight exploration. Freeze per-corner refined-coordinate error and rigid-fit residual attribution to distinguish outliers from common translation bias before changing candidate selection or model supervision.

### E-20260926-AI-167 — half retention verification

- Stage: S1
- Lane: AI
- Commit: `dfacdba3c7d27893867977f37f64b8c0af67f833` (frozen source; results/tests committed with evidence)
- Change: half retention verification.
- Inputs/fixtures: AI-166 manifest/report and retained original visibility predictions.
- Command: `python -m pytest -q software/ai/tests/test_half_support.py`
- Result: PASS,1 test; hashes,case identities,acceptance,unchanged references,means/tails and criteria verified. Existing pytest-asyncio warning.
- Artifacts: software/ai/tests/test_half_support.py
- Hardware writes: 0
- Physical movements: 0
- Limitations: Consistency verification only; batch unchanged,shared boundary suite not triggered.
- Supersedes: none; prior failures and integration statuses retained.
- Next dependency: AI-166 coordinate attribution.

### E-20260926-AI-168 — half retention publication audit

- Stage: S1
- Lane: AI
- Commit: `dfacdba3c7d27893867977f37f64b8c0af67f833` (frozen source; results/tests committed with evidence)
- Change: half retention publication audit.
- Inputs/fixtures: Repository with AI-166/167 and reviewed fixture allowlist.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS;5936 paths,837.4 MiB,0 unresolved findings,14 reviewed synthetic fixtures.
- Artifacts: audit stdout and snapshot
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic audit; AI-041 protected-main publication blocker remains.
- Supersedes: none; prior failures and integration statuses retained.
- Next dependency: Protected-branch PR/checks and AI-166 diagnosis.
### E-20260926-ARM-041 — hash-bound per-waypoint collision evidence

- Stage: S3
- Lane: ARM
- Change: added a bounded evaluator that consumes the exact v2 measured
  trajectory-screening report, its exact installed collision profile, and one
  explicit collision pose for every accepted planner waypoint. Each sample is
  bound to the canonical waypoint and joint-result hashes and carries the full
  pose content required for replay. Configuration-sampled bodies such as the
  moving camera cable must provide pose-local geometry at every waypoint.
- Safety behavior: crossed profile, trajectory, waypoint, or joint-result
  lineage rejects. Missing or unusable deformable geometry blocks the sample;
  any primitive collision blocks the route. Even when all supplied full-body
  samples are clear, the report remains
  `DISCRETE_WAYPOINTS_CLEAR_CONTINUOUS_PROOF_REQUIRED`, retains
  `CONTINUOUS_FULL_BODY_COLLISION_SWEEP_REQUIRED`, and fixes controller
  commands, hardware access, and physical authority to zero/false.
- Artifacts: `measured_waypoint_collision_sequence.py`, closed v1 JSON schema,
  positive/collision/missing-cable/crossed-lineage/resource-bound tests, public
  application exports, portable CI selection, and shared assurance updates.
- Artifact identity: waypoint collision evaluator SHA-256
  `e25145b2bfa143c287cc701fd678e25ad36e4786d6f428794fbe48ea524feb4b`;
  v1 report schema SHA-256
  `3aaaed58858d098deed83f617d56cdd39b41de8fd6680a9e5847450cfcf05d2e`.
- Results: focused collision/planner suite PASS, 38 tests in 3.55 seconds;
  portable shared AI/arm selection PASS, 189 tests in 20.80 seconds;
  snapshot audit PASS, 19 tests in 0.54 seconds; documentation PASS for 26
  maintained documents and two SVG assets; compile and diff checks PASS.
- Hardware writes: 0
- Physical movements: 0
- Limitations: tests use accepted-measured typed fixtures, not independently
  measured installed workcell evidence. The boundary hash-binds supplied rigid
  transforms to their waypoint but does not yet recompute robot-link transforms
  from the joint solution. Discrete waypoint samples do not bound inter-waypoint
  motion, and no phase-local contact allowance is present.
- Supersedes: ARM-040 only for explicit per-waypoint primitive evaluation and
  deformable-body sample completeness. Continuous clearance, FK-derived pose
  provenance, installed qualification, and every physical-use gate remain.
- Next dependency: derive robot-link transforms from the pinned URDF and exact
  joint result inside a trusted adapter, then require conservative bounded
  inter-waypoint samples for both rigid and configuration-sampled bodies.

### E-20260926-AI-169 — refined coordinate bias attribution

- Stage: S1
- Lane: AI
- Commit: `61d37269f269005116c7de24220dcaa62b811275` (frozen source; results/tests committed with evidence)
- Change: refined coordinate bias attribution.
- Inputs/fixtures: Retained AI-157800 refined-corner predictions,15M200 groups,four conditions; exact source/input hashes in eval/refined_bias_v0_plan.json.
- Command: `python software/ai/vision/diagnose_refined_bias.py`
- Result: Diagnostic completed. Bad >3mm cases standard/appearance/partial/full125/77/172/186; >=50% single-corner energy69/22/87/112 (290 total),>=50% common translation energy31/10/18/41 (100 total),categories may overlap. Shared-bias means2.980/2.275/4.689/5.131mm. FitRMS<=3mm cases20/6/10/3 include14/6/5/3 bad cases (28/39). Residual/error correlations0.018/0.492/0.921/0.912. Residual is insufficient as calibrated uncertainty.
- Artifacts: eval/refined_bias_v0_report.json; frozen runner/plan
- Hardware writes: 0
- Physical movements: 0
- Limitations: Oracle error decomposition diagnostic only; no offset correction/calibration. Descriptive3mm/50% cuts not admission thresholds. Reused synthetic data; no qualification or boundary changes.
- Supersedes: none; prior failures and integration statuses retained.
- Next dependency: Freeze one fixed robust-fit comparison using refined predicted corners only (Huber IRLS,3mm residual scale,5 iterations),with same original candidate selection and all-case scoring. Preserve absolute metrics and do not infer confidence from residual.

### E-20260926-AI-170 — refined bias verification

- Stage: S1
- Lane: AI
- Commit: `61d37269f269005116c7de24220dcaa62b811275` (frozen source; results/tests committed with evidence)
- Change: refined bias verification.
- Inputs/fixtures: AI-169 pinned manifest/800 rows.
- Command: `python -m pytest -q software/ai/tests/test_refined_bias.py`
- Result: PASS,1 test; hashes,energy decomposition identity,majority counts and low-residual false assurances verified. Existing pytest-asyncio warning.
- Artifacts: software/ai/tests/test_refined_bias.py
- Hardware writes: 0
- Physical movements: 0
- Limitations: Consistency check only; batch unchanged,shared boundary suite not triggered.
- Supersedes: none; prior failures and integration statuses retained.
- Next dependency: AI-169 robust fitting study.

### E-20260926-AI-171 — refined bias publication audit

- Stage: S1
- Lane: AI
- Commit: `61d37269f269005116c7de24220dcaa62b811275` (frozen source; results/tests committed with evidence)
- Change: refined bias publication audit.
- Inputs/fixtures: Repository with AI-169/170 and reviewed fixture allowlist.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS;5943 paths,837.9 MiB,0 unresolved findings,14 reviewed synthetic fixtures.
- Artifacts: audit stdout and snapshot
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic audit; AI-041 protected-main publication blocker remains.
- Supersedes: none; prior failures and integration statuses retained.
- Next dependency: Protected-branch PR/checks and AI-169 study.

### E-20260926-AI-172 — fixed Huber fitting comparison

- Stage: S1
- Lane: AI
- Commit: `0f6b90585a8961658ba6eacc99186cb80db20891` (frozen source; results/tests committed with evidence)
- Change: fixed Huber fitting comparison.
- Inputs/fixtures: All800 retained15M200 refined coordinate sets; exact source/input hashes in eval/robust_fit_v0_plan.json. Same candidates,Huber3mm scale,5 iterations,ordinary fit initialization.
- Command: `python software/ai/vision/evaluate_robust_fit.py`
- Result: FAIL overall. Original→robust means standard3.040→2.993,appearance2.450→2.776,partial4.773→4.440,full5.236→5.186mm. >3mm tails125→126,77→115,172→173,186→178/200. Appearance yawp951.236→1.391 and partial1.594→1.790 exceed1.1x. All800 cases scored,including original visibility abstentions. Output arm equal denotes robust candidate.
- Artifacts: eval/robust_fit_v0_report.json; frozen fit/runner/plan
- Hardware writes: 0
- Physical movements: 0
- Limitations: Synthetic development,correlated corner errors and four-point geometry limit residual reweighting. No calibrated residual confidence,qualification,boundary change or runtime promotion.
- Supersedes: none; previous failures and integration statuses retained.
- Next dependency: Stop fit-only variations. Audit corner-coordinate label/render alignment and learned heatmap error direction by semantic corner and condition before defining a new localization training objective; no empirical offset correction from reused data.

### E-20260926-AI-173 — robust fit verification

- Stage: S1
- Lane: AI
- Commit: `0f6b90585a8961658ba6eacc99186cb80db20891` (frozen source; results/tests committed with evidence)
- Change: robust fit verification.
- Inputs/fixtures: Analytic exact rigid pose/translation,AI-172 pinned report and original predictions.
- Command: `python -m pytest -q software/ai/tests/test_robust_fit.py`
- Result: PASS,2 tests; rigid recovery,translation equivariance,hashes,all-case scoring,retained references and criteria verified. Existing pytest-asyncio warning.
- Artifacts: software/ai/tests/test_robust_fit.py
- Hardware writes: 0
- Physical movements: 0
- Limitations: Consistency verification only; batch unchanged,shared boundary suite not triggered.
- Supersedes: none; previous failures and integration statuses retained.
- Next dependency: AI-172 label/heatmap audit.

### E-20260926-AI-174 — robust fit publication audit

- Stage: S1
- Lane: AI
- Commit: `0f6b90585a8961658ba6eacc99186cb80db20891` (frozen source; results/tests committed with evidence)
- Change: robust fit publication audit.
- Inputs/fixtures: Repository with AI-172/173 and reviewed fixture allowlist.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS;5948 paths,838.5 MiB,0 unresolved findings,14 reviewed synthetic fixtures.
- Artifacts: audit stdout and snapshot
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic audit; AI-041 protected-main publication blocker remains.
- Supersedes: none; previous failures and integration statuses retained.
- Next dependency: Protected-branch PR/checks and AI-172 audit.

### E-20260926-AI-175 — label alignment and directional error audit

- Stage: S1
- Lane: AI
- Commit: `35c9177b92c350c2170c06dbfc56fe4a07764ec3` (frozen source; results/tests committed with evidence)
- Change: label alignment and directional error audit.
- Inputs/fixtures: Retained AI-157800 development cases/3200 refined corners; intercepted PIL polygon calls on regenerated scenes. Exact source/input hashes in eval/label_alignment_v0_plan.json.
- Command: `python software/ai/vision/audit_label_alignment.py`
- Result: PASS vector alignment: maximum draw-label delta0px,independent rigid projection delta2.84217e-14px. Standard local signed means corners0..3=(2.047,2.048),(-1.790,2.126),(-0.410,-3.188),(4.202,-3.983)mm. Appearance=(2.950,4.188),(-2.459,4.282),(-2.399,-5.836),(5.343,-3.228)mm. These signs indicate inward bias in both conditions; occlusion alters direction/magnitude.
- Artifacts: eval/label_alignment_v0_report.json; frozen audit/plan
- Hardware writes: 0
- Physical movements: 0
- Limitations: Checks polygon arguments,not final raster edge visibility after blur/clutter. Errors are selected refined heatmap candidates,not raw logits. No empirical offset correction,physical calibration or qualification.
- Supersedes: none; previous failures and integration statuses retained.
- Next dependency: Freeze matched localization training with a geometry-consistency auxiliary loss versus unchanged t05 control; use labeled synthetic geometry only as training supervision,never runtime calibration. Keep identical seed/data/budget/selection and unchanged decoder/evaluation criteria; no reused-data offset fitting.

### E-20260926-AI-176 — alignment verification

- Stage: S1
- Lane: AI
- Commit: `35c9177b92c350c2170c06dbfc56fe4a07764ec3` (frozen source; results/tests committed with evidence)
- Change: alignment verification.
- Inputs/fixtures: AI-175 manifest,800 images/3200 rows.
- Command: `python -m pytest -q software/ai/tests/test_label_alignment.py`
- Result: PASS,1 test; hashes,vector alignment,independent formula tolerance,per-corner counts and signed summary recomputation verified. Existing pytest-asyncio warning.
- Artifacts: software/ai/tests/test_label_alignment.py
- Hardware writes: 0
- Physical movements: 0
- Limitations: Consistency verification only; batch unchanged,shared boundary suite not triggered.
- Supersedes: none; previous failures and integration statuses retained.
- Next dependency: AI-175 matched localization objective study.

### E-20260926-AI-177 — alignment publication audit

- Stage: S1
- Lane: AI
- Commit: `35c9177b92c350c2170c06dbfc56fe4a07764ec3` (frozen source; results/tests committed with evidence)
- Change: alignment publication audit.
- Inputs/fixtures: Repository with AI-175/176 and reviewed fixture allowlist.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS;5952 paths,839.2 MiB,0 unresolved findings,14 reviewed synthetic fixtures.
- Artifacts: audit stdout and snapshot
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic audit; AI-041 protected-main publication blocker remains.
- Supersedes: none; previous failures and integration statuses retained.
- Next dependency: Protected-branch PR/checks and AI-175 study.
### E-20260926-ARM-042 — FK-derived collision-pose adapter

- Stage: S3
- Lane: ARM
- Change: added a trusted offline adapter that reconstructs every robot-link,
  gripper, hand-TCP, and tool-parent transform from the exact accepted IK joint
  result, fixed gripper state, hash-pinned URDF, and measured `B_T_Wv`.
  Non-URDF holder/camera frames are derived from measured fixed transforms
  anchored to named URDF links. The adapter then feeds the ARM-041 full-body
  waypoint evaluator without accepting caller-supplied robot-link overrides.
- Safety behavior: context, build, calibration, model, base collision contract,
  trajectory, and installed-profile lineage are revalidated. Attachment and
  configuration-sampled geometry source hashes must already exist in the
  installed profile. Missing attachment coverage, non-measured cable geometry,
  crossed calibration, malformed joints, or any override attempt rejects.
  Clear output retains the continuous-sweep blocker and has zero commands,
  hardware access, or physical authority.
- Artifacts: `fk_collision_pose_adapter.py`, closed v1 JSON schema,
  FK-change/attachment-coverage/override/cable-provenance/crossed-calibration
  tests, public application exports, portable CI selection, and shared
  assurance updates.
- Artifact identity: FK collision-pose adapter SHA-256
  `5e9609b4a55539be30a51c731fdc2fc40aa66aae679693e28c275772a9b8defc`;
  v1 report schema SHA-256
  `54061ef2e45911908016f85306c736698b6868bd73c8e60f8066106be07ce1a9`.
- Results: focused collision/FK/planner suite PASS, 42 tests in 4.48 seconds;
  portable shared AI/arm selection PASS, 193 tests in 20.65 seconds;
  snapshot audit PASS, 19 tests in 0.48 seconds; documentation PASS for 26
  maintained documents and two SVG assets; compile and diff checks PASS.
- Hardware writes: 0
- Physical movements: 0
- Limitations: fixtures use accepted-measured typed geometry rather than an
  independently measured installed workcell. Fixed attachment transforms are
  only as trustworthy as the profile-bound sources. Evaluation remains at
  planner waypoints; no conservative segment subdivision, cable swept volume,
  or phase-local contact allowance is implemented.
- Supersedes: ARM-041's caller-supplied robot rigid-transform limitation. It
  does not supersede ARM-041's discrete-only or physical-evidence limitations.
- Next dependency: derive bounded intermediate joint samples for every segment,
  recompute all rigid transforms at each sample, and require profile-bound cable
  geometry or a conservative cable envelope at each intermediate state.

### E-20260926-AI-178 — geometry auxiliary matched training

- Stage: S1
- Lane: AI
- Commit: `fa1eedd1f479fcf2d8ad7024ec06628aedf0af11` (frozen source; results/tests committed with evidence)
- Change: geometry auxiliary matched training.
- Inputs/fixtures: 2400 training/800 reused development images,14M600/15M200 groups. Exact source/catalog/checkpoint hashes in train/landmark_geometry_aux_v0_plan.json. Both t05 networks,same initialization/data/order/8epochs/common original development objective.
- Command: `python software/ai/train/train_geometry_auxiliary.py`
- Result: FAIL all12 relative localization checks and visibility. Control→aux mean standard8.248→13.881,appearance12.765→17.767,partial10.934→14.902,full11.050→14.751mm; tails192/199/196/198→200/200/199/199. Hidden false-visible6→100/201; clear recall2661→1422/2736. Coefficient1 geometry term is six pair-vector squared errors scaled16px,weighted by pair visibility. Control checkpointdc87386d602222652aab4f6e2a052e59d6e39fc862c3847f97b470e5b52803f7; auxiliarya2fe809acb36d94ae137f0b3e525889b284dbc5fe611cd4a537c9b8fb200e9f5.
- Artifacts: eval/landmark_geometry_aux_v0_*; ignored checkpoints
- Hardware writes: 0
- Physical movements: 0
- Limitations: One seed,reused development,GPU nondeterminism. Inherited comparison limitation text incorrectly says temperature1/0.5; actual frozen source/plan instantiate t05 for BOTH arms. Retained report is not rewritten; this entry clarifies metadata. No qualification or runtime change.
- Supersedes: none; prior failures and integration statuses retained.
- Next dependency: Freeze per-loss magnitudes and shared-feature gradient norms/cosines for control versus geometry objectives at seeded initialization and retained checkpoints; no coefficient sweep or retraining before diagnosis.

### E-20260926-AI-179 — geometry auxiliary verification

- Stage: S1
- Lane: AI
- Commit: `fa1eedd1f479fcf2d8ad7024ec06628aedf0af11` (frozen source; results/tests committed with evidence)
- Change: geometry auxiliary verification.
- Inputs/fixtures: Analytic translated/corrupted corners,visibility masks and AI-178 pinned reports.
- Command: `python -m pytest -q software/ai/tests/test_geometry_auxiliary.py`
- Result: PASS,2 tests; translation invariance,occlusion exclusion,all-hidden finite loss,hashes,matched pixels,selection,visibility recounts and criteria verified. Existing pytest-asyncio warning.
- Artifacts: software/ai/tests/test_geometry_auxiliary.py
- Hardware writes: 0
- Physical movements: 0
- Limitations: Consistency tests not qualification; batch unchanged,shared boundary suite not triggered.
- Supersedes: none; prior failures and integration statuses retained.
- Next dependency: AI-178 gradient diagnostic.

### E-20260926-AI-180 — geometry training publication audit

- Stage: S1
- Lane: AI
- Commit: `fa1eedd1f479fcf2d8ad7024ec06628aedf0af11` (frozen source; results/tests committed with evidence)
- Change: geometry training publication audit.
- Inputs/fixtures: Repository with AI-178/179 and reviewed fixture allowlist.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS;5962 paths,840.6 MiB,0 unresolved findings,14 reviewed synthetic fixtures.
- Artifacts: audit stdout and snapshot
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic audit; AI-041 protected-main publication blocker remains.
- Supersedes: none; prior failures and integration statuses retained.
- Next dependency: Protected-branch PR/checks and AI-178 diagnosis.

### E-20260926-AI-181 — loss gradient snapshot diagnosis

- Stage: S1
- Lane: AI
- Commit: `ba9d05524e261dda8cc931115c8a7cb7498aef97` (frozen source; results/tests committed with evidence)
- Change: loss gradient snapshot diagnosis.
- Inputs/fixtures: Four fixed32-image reused training batches from14M starts0/8/16/24,128 images; seeded initialization and retained control/geometry checkpoints. Exact source/checkpoint hashes and seeds in eval/gradient_diagnostic_v0_plan.json; pixel hashes in report.
- Command: `python software/ai/vision/diagnose_loss_gradients.py`
- Result: Completed. Geometry/base shared-feature norm ratio means initialization1.9734,control3.3776,geometry2.5254. Geometry/base cosine ranges0.659–0.721,0.787–0.842,0.052–0.415. Geometry/visibility cosines all negative at initialization(-0.068..-0.021) and failed checkpoint(-0.314..-0.020),positive at control(0.200..0.527). Supports scale-imbalance/conflict hypothesis,not causal proof.
- Artifacts: eval/gradient_diagnostic_v0_report.json; frozen runner/plan
- Hardware writes: 0
- Physical movements: 0
- Limitations: CPU frozen snapshots,not optimizer trajectories; raw gradients omit AdamW state.128 reused images cannot establish generalization or coefficient optimum. No training,qualification or boundary changes.
- Supersedes: none; prior failures and integration statuses retained.
- Next dependency: Freeze one matched auxiliary coefficient0.1 versus control comparison (no sweep),logging per-objective magnitudes and keeping identical data/budget/selection/criteria. Retain coefficient1 failure; fresh evaluation required for any eventual candidate.

### E-20260926-AI-182 — gradient report verification

- Stage: S1
- Lane: AI
- Commit: `ba9d05524e261dda8cc931115c8a7cb7498aef97` (frozen source; results/tests committed with evidence)
- Change: gradient report verification.
- Inputs/fixtures: AI-181 manifest/12 state-batch rows.
- Command: `python -m pytest -q software/ai/tests/test_loss_gradients.py`
- Result: PASS,1 test; hashes,identical pixels across states,norm ratios,cosine ranges,finite losses and summary means verified. Existing pytest-asyncio warning.
- Artifacts: software/ai/tests/test_loss_gradients.py
- Hardware writes: 0
- Physical movements: 0
- Limitations: Report consistency only; batch unchanged,shared boundary suite not triggered.
- Supersedes: none; prior failures and integration statuses retained.
- Next dependency: AI-181 bounded training comparison.

### E-20260926-AI-183 — gradient publication audit

- Stage: S1
- Lane: AI
- Commit: `ba9d05524e261dda8cc931115c8a7cb7498aef97` (frozen source; results/tests committed with evidence)
- Change: gradient publication audit.
- Inputs/fixtures: Repository with AI-181/182 and reviewed fixture allowlist.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS;5966 paths,840.6 MiB,0 unresolved findings,14 reviewed synthetic fixtures.
- Artifacts: audit stdout and snapshot
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic audit; AI-041 protected-main publication blocker remains.
- Supersedes: none; prior failures and integration statuses retained.
- Next dependency: Protected-branch PR/checks and AI-181 study.
### E-20260926-ARM-043 — bounded inter-waypoint joint sampling

- Stage: S3
- Lane: ARM
- Change: added a deterministic diagnostic qualifier that starts from the
  authenticated observed joint state, subdivides each accepted IK segment under
  a bounded maximum joint-step policy, and passes every generated configuration
  through the ARM-042 FK-derived full-body collision adapter.
- Safety behavior: each intermediate cable sample must bind the exact generated
  joint-sample hash and use measured geometry whose source is already bound by
  the installed collision profile. Missing start state, malformed endpoints,
  crossed sample evidence, incomplete geometry, collisions, or sample-cap
  exhaustion reject. Clear samples retain a conservative swept-volume blocker;
  no continuous-clear claim, command, hardware access, or physical authority is
  produced.
- Artifacts: `bounded_segment_collision_qualification.py`, closed v1 JSON
  schema, bounded-step/lineage/resource-cap tests, public application exports,
  and assurance/status updates.
- Artifact identity: bounded segment qualifier SHA-256
  `7494809d311fef38065a17ae548fb90c3da2a9412585acf00af12d2fe2dc001d`;
  v1 report schema SHA-256
  `0bf9448fe8521a9f3d3df2c6cce4c4608efbd6db866abb020af14790647ea4e9`.
- Results: focused collision/FK/planner suite PASS, 17 tests in 4.19 seconds;
  portable shared AI/arm selection PASS, 196 tests in 20.73 seconds;
  documentation PASS for 26 maintained documents and two SVG assets; compile
  and diff checks PASS.
- Hardware writes: 0
- Physical movements: 0
- Limitations: linear joint interpolation plus finite sampling is diagnostic,
  not a conservative continuous swept-volume proof. Test geometry is typed as
  accepted measured evidence but remains synthetic fixture data rather than an
  independently measured installed workcell.
- Supersedes: ARM-042 only for deterministic bounded intermediate sampling and
  exact per-sample cable-evidence binding. It does not supersede physical
  metrology, conservative inter-sample coverage, phase-local contact policy, or
  installed release qualification.
- Next dependency: construct a conservative swept-volume bound for every rigid
  primitive and a profile-bound conservative cable envelope across each adjacent
  sample pair, then prove the bound under the installed clearance policy.

### E-20260926-AI-184 — coefficient0.1 geometry training

- Stage: S1
- Lane: AI
- Commit: `c67f9ee26dc0cb24956164bcbe090684e0579801` (frozen source; results/tests committed with evidence)
- Change: coefficient0.1 geometry training.
- Inputs/fixtures: Matched t05 networks,2400/800 reused14M600/15M200 images,8epochs; exact hashes in train/landmark_geometry_tenth_v0_plan.json.
- Command: `python software/ai/train/train_geometry_tenth.py`
- Result: FAIL. Control→candidate mean standard9.017→9.544,appearance13.051→13.902,partial11.413→11.734,full11.470→11.784mm. >3mm tails196/196/200/199→196/199/198/195. All yaw checks pass,but all means and appearance tail fail. Hidden false-visible1→3/201; clear recall2617→2578/2736. Epoch8 candidate terms heatmap5.9462,coordinate0.4416,visibility0.4874,raw geometry0.7557,applied0.07557;sum6.95072. Both select epoch8. Control checkpoint94bd425ecf91623d2c301a359e944b174e6956b1630842faa844254e765172e9; candidate4964dd70bcdf89a6cad70f99c12d6f16e48889f014d34b80bd1bcb890a495c69.
- Artifacts: eval/landmark_geometry_tenth_v0_*; ignored checkpoints
- Hardware writes: 0
- Physical movements: 0
- Limitations: One seed,reused development,GPU nondeterminism; no qualification or runtime change. Correct objective scaling does not imply useful objective.
- Supersedes: none; prior failures and integration statuses retained.
- Next dependency: Stop auxiliary coefficient tuning. Freeze a consolidated same-pixel development comparison of established pose baseline versus original t05 landmark plus geometry/subpixel decoder,including visibility and abstention limitations,to choose the next model investment from absolute performance rather than relative landmark gains.

### E-20260926-AI-185 — coefficient verification

- Stage: S1
- Lane: AI
- Commit: `c67f9ee26dc0cb24956164bcbe090684e0579801` (frozen source; results/tests committed with evidence)
- Change: coefficient verification.
- Inputs/fixtures: Analytic geometry tests,AI-184 pinned reports,per-epoch objective logs.
- Command: `python -m pytest -q software/ai/tests/test_geometry_tenth.py`
- Result: PASS,3 tests;geometry behavior,hashes,matched pixels,selection,criteria,and exact0.1 applied coefficient/objective sum verified. Existing pytest-asyncio warning.
- Artifacts: software/ai/tests/test_geometry_tenth.py
- Hardware writes: 0
- Physical movements: 0
- Limitations: Consistency verification only; batch unchanged,shared boundary suite not triggered.
- Supersedes: none; prior failures and integration statuses retained.
- Next dependency: AI-184 consolidated comparison.

### E-20260926-AI-186 — coefficient publication audit

- Stage: S1
- Lane: AI
- Commit: `c67f9ee26dc0cb24956164bcbe090684e0579801` (frozen source; results/tests committed with evidence)
- Change: coefficient publication audit.
- Inputs/fixtures: Repository with AI-184/185 and reviewed fixture allowlist.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS;5974 paths,841.9 MiB,0 unresolved findings,14 reviewed synthetic fixtures.
- Artifacts: audit stdout and snapshot
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic audit; AI-041 protected-main publication blocker remains.
- Supersedes: none; prior failures and integration statuses retained.
- Next dependency: Protected-branch PR/checks and AI-184 comparison.

### E-20260926-AI-187 — consolidated pose versus landmark comparison

- Stage: S1
- Lane: AI
- Commit: `47d0e33f84aaccae3fd47aabeaf4c7790b99faa8` (frozen source; results/tests committed with evidence)
- Change: consolidated pose versus landmark comparison.
- Inputs/fixtures: 800 reused15M200 images. Same normalized256x192 source; pose receives128x96 resize,landmark full resolution. Pose checkpoint0fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d; original t05 landmark356a4dec05c6c2194c6d31542fed0d7199d5e989eb4b7678888d1a01aa493281 plus frozen geometry/subpixel. Exact source hashes in eval/pose_landmark_v0_plan.json.
- Command: `python software/ai/vision/evaluate_pose_landmark.py`
- Result: Landmark FAIL all12 comparison checks. Pose versus landmark means standard0.853/3.040,appearance0.833/2.450,partial1.026/4.773,full1.229/5.236mm. >3mm tails pose5/7/9/11 versus125/77/172/186 per200. Pose yawp950.526/0.514/0.782/0.829deg versus1.285/1.236/1.594/1.523. Landmark predicted min3 support200/200/194/192 descriptive only; all cases scored.
- Artifacts: eval/pose_landmark_v0_report.json; frozen runner/plan
- Hardware writes: 0
- Physical movements: 0
- Limitations: Unequal model training histories; not architecture superiority proof. Reused synthetic development,pose lacks calibrated per-observation uncertainty and visibility. Both unqualified; no runtime or arm/integration status change.
- Supersedes: none; previous failures and integration statuses retained.
- Next dependency: Prioritize established pose localization; retain landmark visibility as separate research. Freeze an identical-input diagnostic of pose >3mm failures versus predicted landmark visibility,including false rejection of good pose cases. Do not assume visibility is localization confidence or install a gate from development evidence.

### E-20260926-AI-188 — consolidated comparison verification

- Stage: S1
- Lane: AI
- Commit: `47d0e33f84aaccae3fd47aabeaf4c7790b99faa8` (frozen source; results/tests committed with evidence)
- Change: consolidated comparison verification.
- Inputs/fixtures: AI-187 manifest/report,retained subpixel predictions and original training pixel hash.
- Command: `python -m pytest -q software/ai/tests/test_pose_landmark.py`
- Result: PASS,2 tests; rigid fit,hashes,same normalized pixels,exact landmark reproduction,support counts and comparison criteria verified. Existing pytest-asyncio warning.
- Artifacts: software/ai/tests/test_pose_landmark.py
- Hardware writes: 0
- Physical movements: 0
- Limitations: Implementation verification only; batch unchanged,shared boundary suite not triggered.
- Supersedes: none; previous failures and integration statuses retained.
- Next dependency: AI-187 pose failure/visibility diagnostic.

### E-20260926-AI-189 — comparison publication audit

- Stage: S1
- Lane: AI
- Commit: `47d0e33f84aaccae3fd47aabeaf4c7790b99faa8` (frozen source; results/tests committed with evidence)
- Change: comparison publication audit.
- Inputs/fixtures: Repository with AI-187/188 and reviewed fixture allowlist.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS;5978 paths,842.6 MiB,0 unresolved findings,14 reviewed synthetic fixtures.
- Artifacts: audit stdout and snapshot
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic audit; AI-041 protected-main publication blocker remains.
- Supersedes: none; previous failures and integration statuses retained.
- Next dependency: Protected-branch PR/checks and AI-187 diagnosis.


### E-20260926-AI-190 — pose visibility association diagnostic

- Stage: S1
- Lane: AI
- Commit: `705a3f3bd9701ccdf1ee9857863fe5fc863f6231` (frozen source; results/tests committed with evidence)
- Change: pose visibility association diagnostic.
- Inputs/fixtures: AI-187 retained 800 predictions, seeds15000000..15000199 x four conditions; source/report hashes pinned in eval/pose_visibility_v0_plan.json. Existing support threshold sigmoid visibility>=0.5,minimum3 corners; pose maximum target error>3mm. Audit additionally uses reviewed fixture allowlist.
- Command: `python software/ai/vision/diagnose_pose_visibility.py`
- Result: FAIL as localization safeguard: 28/32 errors over3mm remain accepted; 4/32 detected (12.5%); 10 accurate cases rejected. Coverage786/800 (98.25%). Standard accepted bad5/200; appearance7/200; partial7/194; full9/192. No threshold sweep.
- Artifacts: eval/pose_visibility_v0_report.json; vision/diagnose_pose_visibility.py
- Hardware writes: 0
- Physical movements: 0
- Limitations: Reused synthetic development; fixed visibility rule is not calibrated localization uncertainty. No runtime gate installed.
- Supersedes: none; earlier failed evidence and arm/integration status retained.
- Next dependency: Freeze a direct pose-tail diagnosis by seed, translation/yaw contribution and controlled condition before selecting a bounded pose-training change. Visibility may describe occlusion but must not substitute for coordinate uncertainty. Protected-branch publication still requires PR/checks.


### E-20260926-AI-191 — pose visibility verification

- Stage: S1
- Lane: AI
- Commit: `705a3f3bd9701ccdf1ee9857863fe5fc863f6231` (frozen source; results/tests committed with evidence)
- Change: pose visibility verification.
- Inputs/fixtures: AI-187 retained 800 predictions, seeds15000000..15000199 x four conditions; source/report hashes pinned in eval/pose_visibility_v0_plan.json. Existing support threshold sigmoid visibility>=0.5,minimum3 corners; pose maximum target error>3mm. Audit additionally uses reviewed fixture allowlist.
- Command: `python -m pytest -q software/ai/tests/test_pose_visibility.py`
- Result: PASS,2 tests: threshold boundaries, confusion counts, empty accepted set, hashes and retained evidence recount. Existing pytest-asyncio warning.
- Artifacts: tests/test_pose_visibility.py
- Hardware writes: 0
- Physical movements: 0
- Limitations: Implementation verification only; batch contract unchanged, shared boundary tests not triggered.
- Supersedes: none; earlier failed evidence and arm/integration status retained.
- Next dependency: Freeze a direct pose-tail diagnosis by seed, translation/yaw contribution and controlled condition before selecting a bounded pose-training change. Visibility may describe occlusion but must not substitute for coordinate uncertainty. Protected-branch publication still requires PR/checks.


### E-20260926-AI-192 — pose visibility publication audit

- Stage: S1
- Lane: AI
- Commit: `705a3f3bd9701ccdf1ee9857863fe5fc863f6231` (frozen source; results/tests committed with evidence)
- Change: pose visibility publication audit.
- Inputs/fixtures: AI-187 retained 800 predictions, seeds15000000..15000199 x four conditions; source/report hashes pinned in eval/pose_visibility_v0_plan.json. Existing support threshold sigmoid visibility>=0.5,minimum3 corners; pose maximum target error>3mm. Audit additionally uses reviewed fixture allowlist.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS;5982 paths,842.6 MiB,0 unresolved findings,14 reviewed synthetic fixtures.
- Artifacts: audit stdout and repository snapshot
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic audit; AI-041 protected-main publication blocker remains.
- Supersedes: none; earlier failed evidence and arm/integration status retained.
- Next dependency: Freeze a direct pose-tail diagnosis by seed, translation/yaw contribution and controlled condition before selecting a bounded pose-training change. Visibility may describe occlusion but must not substitute for coordinate uncertainty. Protected-branch publication still requires PR/checks.


### E-20260926-AI-193 — pose tail decomposition

- Stage: S1
- Lane: AI
- Commit: `87d8ad7d7fdd168d855933f1a4e4e4887039eb8e` (frozen source; results/tests committed with evidence)
- Change: pose tail decomposition.
- Inputs/fixtures: 800 reused15M cases (15000000..15000199 x four conditions), normalized identical images; pose checkpoint SHA256 0fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d. All source/checkpoint/report hashes pinned in eval/pose_tail_v0_plan.json.
- Command: `python software/ai/vision/diagnose_pose_tail.py`
- Result: Completed; exact AI-187 pixel and pose metric reproduction. Standard/appearance/partial/full tails5/7/9/11 per200. New failures versus standard0/3/4/6; recovered0/1/0/0. Translation larger than rotation-only maximum in3/2/4/4 failures; translation alone exceeds3mm in3/4/3/4; rotation alone in1/3/1/3. Partial/full raise average maximum key error by0.274/0.525mm. Both components matter; occlusion adds failures.
- Artifacts: eval/pose_tail_v0_report.json
- Hardware writes: 0
- Physical movements: 0
- Limitations: Oracle decomposition only; components can reinforce/cancel and are not additive. Reused synthetic development and renderer; no physical calibration or runtime uncertainty.
- Supersedes: none; failed evidence and arm/integration status retained.
- Next dependency: Freeze a controlled pose fine-tuning comparison from the established checkpoint: equal training budget, unchanged loss, control without added controlled occlusion versus mixed occlusion candidate; evaluate clear-image regression and occlusion tails on development before any fresh holdout. Do not train on the diagnosed development seeds or install qualification.


### E-20260926-AI-194 — pose tail verification

- Stage: S1
- Lane: AI
- Commit: `87d8ad7d7fdd168d855933f1a4e4e4887039eb8e` (frozen source; results/tests committed with evidence)
- Change: pose tail verification.
- Inputs/fixtures: 800 reused15M cases (15000000..15000199 x four conditions), normalized identical images; pose checkpoint SHA256 0fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d. All source/checkpoint/report hashes pinned in eval/pose_tail_v0_plan.json.
- Command: `python -m pytest -q software/ai/tests/test_pose_tail.py`
- Result: PASS,2 tests: known translation/rotation, source hashes, all800 retained metrics, triangle bound and paired failure sets. Existing pytest-asyncio warning.
- Artifacts: tests/test_pose_tail.py
- Hardware writes: 0
- Physical movements: 0
- Limitations: Implementation tests only; batch contract unchanged; shared boundary suite not triggered.
- Supersedes: none; failed evidence and arm/integration status retained.
- Next dependency: Freeze a controlled pose fine-tuning comparison from the established checkpoint: equal training budget, unchanged loss, control without added controlled occlusion versus mixed occlusion candidate; evaluate clear-image regression and occlusion tails on development before any fresh holdout. Do not train on the diagnosed development seeds or install qualification.


### E-20260926-AI-195 — pose tail publication audit

- Stage: S1
- Lane: AI
- Commit: `87d8ad7d7fdd168d855933f1a4e4e4887039eb8e` (frozen source; results/tests committed with evidence)
- Change: pose tail publication audit.
- Inputs/fixtures: 800 reused15M cases (15000000..15000199 x four conditions), normalized identical images; pose checkpoint SHA256 0fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d. All source/checkpoint/report hashes pinned in eval/pose_tail_v0_plan.json.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS;5986 paths,843.1 MiB,0 unresolved findings,14 reviewed synthetic fixtures.
- Artifacts: audit stdout and snapshot
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic audit; protected-main publication blocker AI-041 retained.
- Supersedes: none; failed evidence and arm/integration status retained.
- Next dependency: Freeze a controlled pose fine-tuning comparison from the established checkpoint: equal training budget, unchanged loss, control without added controlled occlusion versus mixed occlusion candidate; evaluate clear-image regression and occlusion tails on development before any fresh holdout. Do not train on the diagnosed development seeds or install qualification.
### E-20260926-ARM-044 — conservative adjacent-sample sweep envelopes

- Stage: S3
- Lane: ARM
- Change: added a deterministic offline qualifier that encloses each rigid
  primitive over every adjacent ARM-043 sample pair. The rigid displacement
  margin uses the pinned URDF path radius and exact ancestor-joint delta sum.
  Configuration-sampled cable bodies require a separately measured root-frame
  envelope bound to the exact start/end sample hashes and an installed-profile
  source.
- Safety behavior: conservative envelopes are evaluated under the installed
  clearance policy. Missing/crossed envelope evidence, unbound sources,
  unsupported prismatic arm joints, incomplete poses, or envelope collisions
  reject. Clear envelopes do not become physical authority. Diagnostic-only
  global pair exclusions prevent a continuous-proof claim, while phase-local
  contact policy and installed physical qualification remain explicit blockers.
- Artifacts: `conservative_segment_sweep_qualification.py`, closed v1 JSON
  schema, clear/collision/crossed-envelope tests, public application exports,
  and shared assurance/status updates.
- Artifact identity: conservative sweep qualifier SHA-256
  `0f953ead5c94ff795bb412eed661b87f38e4b36d1ef5c27be8eebcd9106d90d6`;
  v1 report schema SHA-256
  `2892acc794c9d61a57b02edd462f8ed02cf6f2217e688a0ce40a367e40857c69`.
- Results: focused collision/FK/sweep suite PASS, 43 tests in 2.92 seconds;
  portable shared AI/arm selection PASS, 199 tests in 23.91 seconds;
  documentation PASS for 26 maintained documents, eight public titles,
  required navigation, and two SVG assets; compile and diff checks PASS.
- Hardware writes: 0
- Physical movements: 0
- Limitations: a deformable cable envelope is supplied evidence, not inferred
  cable physics. The rigid bound is intentionally conservative and may reject
  feasible routes. Current installed pair exclusions remain diagnostic rather
  than accepted engineering evidence, and fixture geometry is not independently
  measured installed-workcell evidence.
- Supersedes: ARM-043's unresolved rigid and cable inter-sample coverage gap for
  exact supplied conservative envelopes. It does not supersede accepted pair
  exclusions, phase-local contact semantics, installed physical qualification,
  controller qualification, or execution review.
- Next dependency: replace diagnostic URDF-adjacent exclusions with accepted
  engineering evidence, define phase-local intended-contact rules, and bind the
  resulting collision qualification into the no-write trajectory envelope gate.


### E-20260926-AI-196 — paired pose occlusion fine tuning

- Stage: S1
- Lane: AI
- Commit: `24250e9c3d1d60ab352d9de631d468da1b48eb6e` (frozen source; results/tests committed with evidence)
- Change: paired pose occlusion fine tuning.
- Inputs/fixtures: training14M600 groups x4 images, development15M200 x4; starting pose SHA256 0fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d. Rectangle training/ellipse development, normalized128x96; four epochs,AdamW0.0001,loss4:4:1,batch64,seed260926. Source hashes in train/pose_occlusion_v0_plan.json; pixel/checkpoint hashes in eval/pose_occlusion_v0_report.json.
- Command: `python software/ai/train/train_pose_occlusion.py`
- Result: FAIL frozen candidate criteria. Occluded tails20->15 versus both baseline/control; candidate standard/appearance/partial/full tails4/6/5/10 vs baseline5/7/9/11,control4/6/8/12. Candidate means0.843/0.870/0.974/1.127mm vs baseline0.853/0.833/1.026/1.229,control0.802/0.790/1.009/1.209. Standard yawp95 baseline0.525->0.581deg exceeds10% bound; appearance mean regresses. Control selected epoch4,candidate3. control checkpoint SHA256 9ae845c83dce2afcb32cfe1e48668ac7d3863305a98036d616aa3c12c6bc0f00; occlusion checkpoint SHA256 06cb514ce93546728027685966937872dd36151edfaf57d8a989e86ab392b8ae
- Artifacts: train/train_pose_occlusion.py; eval/pose_occlusion_v0_report.json; tests/test_pose_occlusion.py; ignored local results/pose_occlusion_v0_* checkpoints.
- Hardware writes: 0
- Physical movements: 0
- Limitations: One seed,GPU nondeterminism; repeated synthetic development selects checkpoints. CUDA baseline differs slightly from prior CPU results; within-run baseline used. No fresh holdout consumed, no model promotion or qualification.
- Supersedes: none; failed evidence and ARM-044 retained; no arm/integration status edits.
- Next dependency: Freeze a bounded balanced-replay comparison preserving clear examples while adding occlusion; hold sample budget,loss,selection and acceptance criteria constant. Aim to preserve the observed occlusion benefit without clear/appearance regression. No fresh qualification until development criteria pass.


### E-20260926-AI-197 — pose occlusion verification

- Stage: S1
- Lane: AI
- Commit: `24250e9c3d1d60ab352d9de631d468da1b48eb6e` (frozen source; results/tests committed with evidence)
- Change: pose occlusion verification.
- Inputs/fixtures: training14M600 groups x4 images, development15M200 x4; starting pose SHA256 0fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d. Rectangle training/ellipse development, normalized128x96; four epochs,AdamW0.0001,loss4:4:1,batch64,seed260926. Source hashes in train/pose_occlusion_v0_plan.json; pixel/checkpoint hashes in eval/pose_occlusion_v0_report.json.
- Command: `python -m pytest -q software/ai/tests/test_pose_occlusion.py`
- Result: PASS,2 tests: equal sample budgets/intervention,hashes,all condition metrics,epoch selection,checkpoint hashes and comparison checks. Existing pytest-asyncio warning.
- Artifacts: train/train_pose_occlusion.py; eval/pose_occlusion_v0_report.json; tests/test_pose_occlusion.py; ignored local results/pose_occlusion_v0_* checkpoints.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Implementation verification; batch unchanged, shared boundary suite not triggered.
- Supersedes: none; failed evidence and ARM-044 retained; no arm/integration status edits.
- Next dependency: Freeze a bounded balanced-replay comparison preserving clear examples while adding occlusion; hold sample budget,loss,selection and acceptance criteria constant. Aim to preserve the observed occlusion benefit without clear/appearance regression. No fresh qualification until development criteria pass.


### E-20260926-AI-198 — pose occlusion publication audit

- Stage: S1
- Lane: AI
- Commit: `24250e9c3d1d60ab352d9de631d468da1b48eb6e` (frozen source; results/tests committed with evidence)
- Change: pose occlusion publication audit.
- Inputs/fixtures: training14M600 groups x4 images, development15M200 x4; starting pose SHA256 0fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d. Rectangle training/ellipse development, normalized128x96; four epochs,AdamW0.0001,loss4:4:1,batch64,seed260926. Source hashes in train/pose_occlusion_v0_plan.json; pixel/checkpoint hashes in eval/pose_occlusion_v0_report.json.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS;5992 paths,844.2 MiB,0 unresolved findings,14 reviewed synthetic fixtures.
- Artifacts: train/train_pose_occlusion.py; eval/pose_occlusion_v0_report.json; tests/test_pose_occlusion.py; ignored local results/pose_occlusion_v0_* checkpoints.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic audit; protected-main publication blocker AI-041 retained.
- Supersedes: none; failed evidence and ARM-044 retained; no arm/integration status edits.
- Next dependency: Freeze a bounded balanced-replay comparison preserving clear examples while adding occlusion; hold sample budget,loss,selection and acceptance criteria constant. Aim to preserve the observed occlusion benefit without clear/appearance regression. No fresh qualification until development criteria pass.


### E-20260926-AI-199 — balanced pose replay comparison

- Stage: S1
- Lane: AI
- Commit: `5021c019fe9a6eef6caa30a448edb3ae96e58980` (frozen source; results/tests committed with evidence)
- Change: balanced pose replay comparison.
- Inputs/fixtures: training14M600 groups x4, development15M200 x4. Starting checkpoint0fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d; rectangle training/ellipse development;4 epochs,AdamW0.0001,loss4:4:1,batch64,seed260926. Frozen source hashes in train/pose_balanced_v0_plan.json; pixel/checkpoint hashes in eval/pose_balanced_v0_report.json.
- Command: `python software/ai/train/train_pose_balanced.py`
- Result: FAIL. Candidate standard/appearance/partial/full means0.843/0.854/0.997/1.166mm; tails4/6/9/12 vs baseline5/7/9/11 and control4/6/8/12. Combined obstruction tails21 vs baseline/control20; prior50% occlusion candidate15. Appearance mean and standard yawp95 regress versus baseline; clear means regress versus control. Control epoch4,candidate3. control checkpoint SHA256 bb401f24e8925a78ff01ca6bb8654d711cd475b56dd02dea4b43a90bcfa2c0bf; occlusion checkpoint SHA256 55a08e79cf8829c486063cd8b7463377844522e6b6d42d23bc1ccbd5db2b32bb
- Artifacts: train/train_pose_balanced.py; eval/pose_balanced_v0_report.json; tests/test_pose_balanced.py; ignored local results/pose_balanced_v0_* checkpoints.
- Hardware writes: 0
- Physical movements: 0
- Limitations: One seed,GPU nondeterminism and reused synthetic development selection; no holdout consumed. The25% mix also changes which occlusion examples are seen, not a pure exposure-frequency experiment. No promotion or qualification.
- Supersedes: none; prior failures and arm/integration status retained.
- Next dependency: Stop mix-ratio tuning. Freeze a bounded paired objective comparison using identical50% occlusion images and starting checkpoint: existing pose-parameter loss versus differentiable key-position displacement loss, preserving common epoch selection and acceptance criteria. Synthetic target geometry is training supervision only, never runtime calibration.


### E-20260926-AI-200 — balanced replay verification

- Stage: S1
- Lane: AI
- Commit: `5021c019fe9a6eef6caa30a448edb3ae96e58980` (frozen source; results/tests committed with evidence)
- Change: balanced replay verification.
- Inputs/fixtures: training14M600 groups x4, development15M200 x4. Starting checkpoint0fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d; rectangle training/ellipse development;4 epochs,AdamW0.0001,loss4:4:1,batch64,seed260926. Frozen source hashes in train/pose_balanced_v0_plan.json; pixel/checkpoint hashes in eval/pose_balanced_v0_report.json.
- Command: `python -m pytest -q software/ai/tests/test_pose_balanced.py`
- Result: PASS,2 tests. Exact2400-image budget,1200standard/600appearance/300partial/300full,75 examples per occlusion-type/corner; hashes,metrics,epoch selection,checkpoint identities,comparison checks and unchanged development pixels verified. Existing pytest-asyncio warning.
- Artifacts: train/train_pose_balanced.py; eval/pose_balanced_v0_report.json; tests/test_pose_balanced.py; ignored local results/pose_balanced_v0_* checkpoints.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Implementation verification only; batch unchanged, shared boundary tests not triggered.
- Supersedes: none; prior failures and arm/integration status retained.
- Next dependency: Stop mix-ratio tuning. Freeze a bounded paired objective comparison using identical50% occlusion images and starting checkpoint: existing pose-parameter loss versus differentiable key-position displacement loss, preserving common epoch selection and acceptance criteria. Synthetic target geometry is training supervision only, never runtime calibration.


### E-20260926-AI-201 — balanced replay publication audit

- Stage: S1
- Lane: AI
- Commit: `5021c019fe9a6eef6caa30a448edb3ae96e58980` (frozen source; results/tests committed with evidence)
- Change: balanced replay publication audit.
- Inputs/fixtures: training14M600 groups x4, development15M200 x4. Starting checkpoint0fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d; rectangle training/ellipse development;4 epochs,AdamW0.0001,loss4:4:1,batch64,seed260926. Frozen source hashes in train/pose_balanced_v0_plan.json; pixel/checkpoint hashes in eval/pose_balanced_v0_report.json.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS;5996 paths,845.2 MiB,0 unresolved findings,14 reviewed synthetic fixtures.
- Artifacts: train/train_pose_balanced.py; eval/pose_balanced_v0_report.json; tests/test_pose_balanced.py; ignored local results/pose_balanced_v0_* checkpoints.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic audit; AI-041 protected-main publication blocker retained.
- Supersedes: none; prior failures and arm/integration status retained.
- Next dependency: Stop mix-ratio tuning. Freeze a bounded paired objective comparison using identical50% occlusion images and starting checkpoint: existing pose-parameter loss versus differentiable key-position displacement loss, preserving common epoch selection and acceptance criteria. Synthetic target geometry is training supervision only, never runtime calibration.


### E-20260926-AI-202 — paired key displacement objective

- Stage: S1
- Lane: AI
- Commit: `45ec6182f0193d8a57f83a30936d80968bc0431b` (frozen source; results/tests committed with evidence)
- Change: paired key displacement objective.
- Inputs/fixtures: training14M600 x4,development15M200 x4; initial checkpoint0fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d. Both arms50% occlusion,rectangle training/ellipse development,4 epochs,AdamW0.0001,batch64,seed260926. Control4:4:1 pose loss,candidate46-key squared displacement/900. Source hashes in train/pose_keyloss_v0_plan.json; pixel/checkpoint hashes in eval/pose_keyloss_v0_report.json.
- Command: `python software/ai/train/train_pose_keyloss.py`
- Result: FAIL overall, only baseline appearance-mean criterion fails. Candidate means standard0.821,appearance0.863,partial0.947,full1.101mm vs baseline0.853/0.833/1.026/1.229 and control0.843/0.870/0.973/1.127. Candidate tails3/5/5/8 (21total) vs baseline5/7/9/11 (32) and control4/6/6/10 (26). All paired-control criteria pass; obstruction tails13 vs baseline20/control16. Both select epoch3. control checkpoint SHA256 1739de33237f58dd39033d44ff3532b3619ae69daccc62642aad3d4ad773a87b; occlusion checkpoint SHA256 2fe0f07e235f68f994e2d0f46f59794c6cdad43563c40f0f3de54d3daf19d33d
- Artifacts: train/key_displacement_loss.py; train/train_pose_keyloss.py; eval/pose_keyloss_v0_report.json; tests/test_pose_keyloss.py; ignored results/pose_keyloss_v0_* checkpoints.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Single seed,GPU nondeterminism,reused synthetic development; candidate objective changes gradient scaling as well as geometric weighting. Arm name occlusion denotes key-loss candidate for inherited report compatibility. No promotion,qualification or fresh holdout.
- Supersedes: none; previous failed evidence and arm/integration status retained.
- Next dependency: Freeze paired standard-versus-appearance residual attribution for baseline/control/key-loss candidate on retained cases, identifying whether the remaining appearance regression is broad translation bias or concentrated failures before choosing one corrective training change. No acceptance-rule relaxation or fresh holdout until development criteria pass.


### E-20260926-AI-203 — key displacement verification

- Stage: S1
- Lane: AI
- Commit: `45ec6182f0193d8a57f83a30936d80968bc0431b` (frozen source; results/tests committed with evidence)
- Change: key displacement verification.
- Inputs/fixtures: training14M600 x4,development15M200 x4; initial checkpoint0fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d. Both arms50% occlusion,rectangle training/ellipse development,4 epochs,AdamW0.0001,batch64,seed260926. Control4:4:1 pose loss,candidate46-key squared displacement/900. Source hashes in train/pose_keyloss_v0_plan.json; pixel/checkpoint hashes in eval/pose_keyloss_v0_report.json.
- Command: `python -m pytest -q software/ai/tests/test_pose_keyloss.py`
- Result: PASS,2 tests: scalar geometry agreement,zero/known translation loss,finite-difference autograd check,identical training pixels,hashes,metrics,selection and comparison criteria. Existing pytest-asyncio warning.
- Artifacts: train/key_displacement_loss.py; train/train_pose_keyloss.py; eval/pose_keyloss_v0_report.json; tests/test_pose_keyloss.py; ignored results/pose_keyloss_v0_* checkpoints.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Implementation verification only; batch contract unchanged,shared boundary tests not triggered.
- Supersedes: none; previous failed evidence and arm/integration status retained.
- Next dependency: Freeze paired standard-versus-appearance residual attribution for baseline/control/key-loss candidate on retained cases, identifying whether the remaining appearance regression is broad translation bias or concentrated failures before choosing one corrective training change. No acceptance-rule relaxation or fresh holdout until development criteria pass.


### E-20260926-AI-204 — key displacement publication audit

- Stage: S1
- Lane: AI
- Commit: `45ec6182f0193d8a57f83a30936d80968bc0431b` (frozen source; results/tests committed with evidence)
- Change: key displacement publication audit.
- Inputs/fixtures: training14M600 x4,development15M200 x4; initial checkpoint0fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d. Both arms50% occlusion,rectangle training/ellipse development,4 epochs,AdamW0.0001,batch64,seed260926. Control4:4:1 pose loss,candidate46-key squared displacement/900. Source hashes in train/pose_keyloss_v0_plan.json; pixel/checkpoint hashes in eval/pose_keyloss_v0_report.json.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS;6001 paths,846.3 MiB,0 unresolved findings,14 reviewed synthetic fixtures.
- Artifacts: train/key_displacement_loss.py; train/train_pose_keyloss.py; eval/pose_keyloss_v0_report.json; tests/test_pose_keyloss.py; ignored results/pose_keyloss_v0_* checkpoints.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic audit; protected-main publication blocker AI-041 retained.
- Supersedes: none; previous failed evidence and arm/integration status retained.
- Next dependency: Freeze paired standard-versus-appearance residual attribution for baseline/control/key-loss candidate on retained cases, identifying whether the remaining appearance regression is broad translation bias or concentrated failures before choosing one corrective training change. No acceptance-rule relaxation or fresh holdout until development criteria pass.


### E-20260926-AI-205 — appearance residual attribution

- Stage: S1
- Lane: AI
- Commit: `44236431c73142a94329a897358e34bd4a10a7be` (frozen source; results/tests committed with evidence)
- Change: appearance residual attribution.
- Inputs/fixtures: retained AI-202 baseline/control/key-loss metrics,200 seeds15000000..15000199,paired standard/appearance. Exact report and runner SHA256 in eval/appearance_residual_v0_plan.json; no new inference or training.
- Command: `python software/ai/vision/diagnose_appearance_residual.py`
- Result: Completed. Candidate versus baseline appearance mean+0.029881mm,median+0.020577mm,105worse/95improved; translation magnitude+0.018502mm,rotation-only maximum+0.030818mm. Signed translation change[-0.165992,-0.012357]mm. Top10 account for24.17% of positive regression; after descriptive trimming mean remains+0.000638mm. Candidate vs control appearance mean improves0.007190mm. Pattern includes distributed small regression and larger contributors; not an isolated outlier or proven causal offset.
- Artifacts: vision/diagnose_appearance_residual.py; eval/appearance_residual_v0_report.json; tests/test_appearance_residual.py.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Retained synthetic development,not fresh evidence. Top10 descriptive only; all cases remain in acceptance metrics. No oracle correction or calibration.
- Supersedes: none; previous failures and arm/integration status retained.
- Next dependency: Freeze paired key-loss training with versus without a fixed baseline-prediction preservation penalty on standard/appearance training images only. Same images,budget,starting checkpoint and criteria; teacher has no truth authority and may retain errors. Test whether reduced prediction drift retains occlusion gains; do not sweep coefficients or relax acceptance.


### E-20260926-AI-206 — appearance attribution verification

- Stage: S1
- Lane: AI
- Commit: `44236431c73142a94329a897358e34bd4a10a7be` (frozen source; results/tests committed with evidence)
- Change: appearance attribution verification.
- Inputs/fixtures: retained AI-202 baseline/control/key-loss metrics,200 seeds15000000..15000199,paired standard/appearance. Exact report and runner SHA256 in eval/appearance_residual_v0_plan.json; no new inference or training.
- Command: `python -m pytest -q software/ai/tests/test_appearance_residual.py`
- Result: PASS,2 tests: known broad/concentrated/zero changes,frozen hashes,200case counts,concentration and trimmed metrics. Existing pytest-asyncio warning.
- Artifacts: vision/diagnose_appearance_residual.py; eval/appearance_residual_v0_report.json; tests/test_appearance_residual.py.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Implementation verification only; batch unchanged,shared boundary suite not triggered.
- Supersedes: none; previous failures and arm/integration status retained.
- Next dependency: Freeze paired key-loss training with versus without a fixed baseline-prediction preservation penalty on standard/appearance training images only. Same images,budget,starting checkpoint and criteria; teacher has no truth authority and may retain errors. Test whether reduced prediction drift retains occlusion gains; do not sweep coefficients or relax acceptance.


### E-20260926-AI-207 — appearance attribution publication audit

- Stage: S1
- Lane: AI
- Commit: `44236431c73142a94329a897358e34bd4a10a7be` (frozen source; results/tests committed with evidence)
- Change: appearance attribution publication audit.
- Inputs/fixtures: retained AI-202 baseline/control/key-loss metrics,200 seeds15000000..15000199,paired standard/appearance. Exact report and runner SHA256 in eval/appearance_residual_v0_plan.json; no new inference or training.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS;6005 paths,846.8 MiB,0 unresolved findings,14 reviewed synthetic fixtures.
- Artifacts: vision/diagnose_appearance_residual.py; eval/appearance_residual_v0_report.json; tests/test_appearance_residual.py.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic audit; AI-041 protected-main publication blocker retained.
- Supersedes: none; previous failures and arm/integration status retained.
- Next dependency: Freeze paired key-loss training with versus without a fixed baseline-prediction preservation penalty on standard/appearance training images only. Same images,budget,starting checkpoint and criteria; teacher has no truth authority and may retain errors. Test whether reduced prediction drift retains occlusion gains; do not sweep coefficients or relax acceptance.
### E-20260926-ARM-045 — phase-local contact and collision envelope gate

- Stage: S3
- Lane: ARM
- Change: added a deterministic gate that binds one v2 model proposal, its
  measured trajectory screening, the ARM-044 conservative sweep result, the
  installed collision profile, and the sealed no-write trajectory envelope.
  Contact proposals require one exact target-bound `CONTACT` waypoint and one
  exact installed tool/device body pair; hover proposals cannot carry either.
- Safety behavior: every global exclusion must be `ENGINEERING_GLOBAL` with
  `ACCEPTED_ENGINEERING` evidence. The phase-local allowance never enters the
  global exclusion set, permits only one contact waypoint, cannot cross device
  or target identity, emits no controller/wire commands, and grants neither
  physical nor contact authority. Installed physical qualification remains
  required.
- Artifacts: `phase_local_contact_envelope_gate.py`, closed v1 JSON schema,
  accepted/rejection/tamper tests, public application exports, and updated
  collision/translation assurance documentation. ARM-044 reports now expose
  the exact trajectory-screening digest required for downstream lineage.
- Artifact identity: contact-envelope gate SHA-256
  `607b2cefc4be9151c8f6182ee21cc56af2ce739e44872cb3e178dba29430adb0`;
  v1 report schema SHA-256
  `f91499c82a2be28a5cb724387e5e39afd9f9c6d9958f0c85a4c768bd12e21dd0`.
- Results: focused collision/sweep/envelope suite PASS, 16 tests in 4.66
  seconds; portable shared AI/arm selection PASS, 203 tests in 29.62 seconds;
  documentation PASS for 26 maintained documents, eight public titles,
  required navigation, and two SVG assets; compile checks PASS.
- Hardware writes: 0
- Physical movements: 0
- Limitations: accepted engineering exclusions and measured collision geometry
  in tests remain synthetic fixtures. The gate proves policy/lineage structure,
  not an installed unit, contact force, device registration, controller
  execution, or observed task outcome. The allowance does not filter an
  ARM-044 collision: the supplied conservative sweep must already be clear;
  installed intended-contact geometry still needs independent qualification.
- Supersedes: ARM-044's missing phase-local-contact and no-write-envelope binding
  for exact supplied evidence. It does not supersede installed metrology,
  physical qualification, execution review, controller permit, or outcome
  verification.
- Next dependency: qualify the installed profile and contact policy with
  independently reviewed physical evidence, then connect this collision-policy
  artifact as a mandatory input to the single-use execution review/permit gate.


### E-20260926-AI-208 — baseline preservation penalty comparison

- Stage: S1
- Lane: AI
- Commit: `ce016b51974f925bd38b14998d2c941e74a9451e` (frozen source; results/tests committed with evidence)
- Change: baseline preservation penalty comparison.
- Inputs/fixtures: training14M600 x4,development15M200 x4; initial/teacher checkpoint0fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d. Both arms key-loss,50% occlusion,4epochs,AdamW0.0001,batch64,seed260926; candidate adds coefficient1 teacher-key penalty only on standard/appearance training images. Source hashes train/pose_anchor_v0_plan.json; image/teacher/checkpoint hashes eval/pose_anchor_v0_report.json.
- Command: `python software/ai/train/train_pose_anchor.py`
- Result: FAIL overall; all baseline comparisons PASS, paired-control comparisons FAIL. Candidate means standard0.797,appearance0.831,partial0.944,full1.116mm vs baseline0.853/0.833/1.026/1.229 and control0.822/0.864/0.947/1.101. Candidate tails4/6/6/9 (25total) vs baseline5/7/9/11 (32) and control3/5/5/9 (22). Obstruction tails15 vs baseline20/control14. Candidate epoch4,control3. control checkpoint SHA256 32827846727a3e6fdbbedad1b94d3952867a776ae5e9aa8e5f23944ca60684ec; occlusion checkpoint SHA256 efdc3b783ea6eca98393ebeb1e0f02d4bb3c2b1bcb8a837b1135b57d1ef91c0a
- Artifacts: train/train_pose_anchor.py; eval/pose_anchor_v0_report.json; tests/test_pose_anchor.py; ignored results/pose_anchor_v0_* checkpoints.
- Hardware writes: 0
- Physical movements: 0
- Limitations: One seed,GPU nondeterminism,reused development selection. Appearance gain over baseline only0.002344mm; not established repeatability. Teacher can preserve errors and has no truth/calibration authority. Historical occlusion arm denotes anchored candidate. No promotion or fresh holdout.
- Supersedes: none; prior failures and arm/integration statuses retained.
- Next dependency: Freeze two additional training seeds for the unchanged paired experiment,report each run and aggregate variation rather than pick a winning seed. Keep coefficient,data,budget,selection and acceptance rules fixed; test repeatability before any new parameter change or fresh qualification.


### E-20260926-AI-209 — baseline preservation verification

- Stage: S1
- Lane: AI
- Commit: `ce016b51974f925bd38b14998d2c941e74a9451e` (frozen source; results/tests committed with evidence)
- Change: baseline preservation verification.
- Inputs/fixtures: training14M600 x4,development15M200 x4; initial/teacher checkpoint0fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d. Both arms key-loss,50% occlusion,4epochs,AdamW0.0001,batch64,seed260926; candidate adds coefficient1 teacher-key penalty only on standard/appearance training images. Source hashes train/pose_anchor_v0_plan.json; image/teacher/checkpoint hashes eval/pose_anchor_v0_report.json.
- Command: `python -m pytest -q software/ai/tests/test_pose_anchor.py`
- Result: PASS,3 tests: geometry/autograd,masked teacher detached,zero-mask handling,equal image/teacher hashes,1200 anchor images per arm,checkpoint identities,selection and metrics. Existing pytest-asyncio warning.
- Artifacts: train/train_pose_anchor.py; eval/pose_anchor_v0_report.json; tests/test_pose_anchor.py; ignored results/pose_anchor_v0_* checkpoints.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Implementation verification only; batch unchanged,shared boundary suite not triggered.
- Supersedes: none; prior failures and arm/integration statuses retained.
- Next dependency: Freeze two additional training seeds for the unchanged paired experiment,report each run and aggregate variation rather than pick a winning seed. Keep coefficient,data,budget,selection and acceptance rules fixed; test repeatability before any new parameter change or fresh qualification.


### E-20260926-AI-210 — baseline preservation publication audit

- Stage: S1
- Lane: AI
- Commit: `ce016b51974f925bd38b14998d2c941e74a9451e` (frozen source; results/tests committed with evidence)
- Change: baseline preservation publication audit.
- Inputs/fixtures: training14M600 x4,development15M200 x4; initial/teacher checkpoint0fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d. Both arms key-loss,50% occlusion,4epochs,AdamW0.0001,batch64,seed260926; candidate adds coefficient1 teacher-key penalty only on standard/appearance training images. Source hashes train/pose_anchor_v0_plan.json; image/teacher/checkpoint hashes eval/pose_anchor_v0_report.json.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS;6012 paths,847.8 MiB,0 unresolved findings,14 reviewed synthetic fixtures.
- Artifacts: train/train_pose_anchor.py; eval/pose_anchor_v0_report.json; tests/test_pose_anchor.py; ignored results/pose_anchor_v0_* checkpoints.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic audit; protected-main blocker AI-041 retained.
- Supersedes: none; prior failures and arm/integration statuses retained.
- Next dependency: Freeze two additional training seeds for the unchanged paired experiment,report each run and aggregate variation rather than pick a winning seed. Keep coefficient,data,budget,selection and acceptance rules fixed; test repeatability before any new parameter change or fresh qualification.


### E-20260926-AI-211 — two additional anchor training seeds

- Stage: S1
- Lane: AI
- Commit: `23ccd07d96acfc2ac3af0eb3e05ccd400200d101` (frozen source; results/tests committed with evidence)
- Change: two additional anchor training seeds.
- Inputs/fixtures: AI-208 seed260926 plus260927/260928; training14M600 x4,development15M200 x4; identical initial/teacher checkpoint0fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d,key-loss4epochs,AdamW0.0001,batch64,anchor coefficient1. Source hashes in train/pose_anchor_replica_*_plan.json and eval/pose_anchor_replication_v0_plan.json; generated hashes in replica and aggregate reports.
- Command: `python software/ai/train/train_pose_anchor_replicas.py`
- Result: Both replicas FAIL full criteria. Seed260927 candidate25 vs control29 total >3mm failures; seed260928 candidate27 vs control24. Seed260927 passes baseline checks,260928 fails. 260927/control checkpoint SHA256 7d5892ff1927f02f26c9361c54f582a2bbdac8e7002284ab7163b5e15dec67b5; 260927/occlusion checkpoint SHA256 a4b2c53e54722d156f28604d4589086d3bbd113b7ab0dd4265b6acb06fbfa681; 260928/control checkpoint SHA256 e50b8b329ad582e5e63c84f9e4153d2b830886b46add67040752194dff3417f1; 260928/occlusion checkpoint SHA256 0784058fbc3712e79c9d4d478f877bb89a63587c767f66330188ca027eeaee5a
- Artifacts: train/train_pose_anchor_replicas.py; vision/summarize_anchor_replicas.py; eval/pose_anchor_replica_*_report.json; eval/pose_anchor_replication_v0_report.json; tests/test_anchor_replicas.py.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Same synthetic development data,not independent data replication;GPU nondeterminism. No seed selection,model promotion or fresh holdout.
- Supersedes: none; all prior failed evidence and arm/integration status retained.
- Next dependency: Stop penalty-coefficient tuning. Design a fixed-budget training-diversity comparison using explicitly reserved new training seeds,holding objective and steps constant,with all three seeds retained. Diagnose whether repeatedly reusing600 training scenes limits robustness; keep new training seeds separate from future qualification data and keep all current models unqualified.


### E-20260926-AI-212 — three-seed anchor aggregation

- Stage: S1
- Lane: AI
- Commit: `23ccd07d96acfc2ac3af0eb3e05ccd400200d101` (frozen source; results/tests committed with evidence)
- Change: three-seed anchor aggregation.
- Inputs/fixtures: AI-208 seed260926 plus260927/260928; training14M600 x4,development15M200 x4; identical initial/teacher checkpoint0fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d,key-loss4epochs,AdamW0.0001,batch64,anchor coefficient1. Source hashes in train/pose_anchor_replica_*_plan.json and eval/pose_anchor_replication_v0_plan.json; generated hashes in replica and aggregate reports.
- Command: `python software/ai/vision/summarize_anchor_replicas.py`
- Result: Full passes0/3,baseline passes2/3. Seeds260926/27/28: candidate failures25/25/27,control22/29/24,baseline32/32/32. Candidate appearance means0.831020/0.832420/0.836195mm; mean0.833212 versus baseline0.833364. Control appearance range0.836309..0.880173. Baseline appearance gain is tiny and not consistent; paired-control advantage not established.
- Artifacts: train/train_pose_anchor_replicas.py; vision/summarize_anchor_replicas.py; eval/pose_anchor_replica_*_report.json; eval/pose_anchor_replication_v0_report.json; tests/test_anchor_replicas.py.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Descriptive ranges only,not confidence intervals; repeated images cannot be pooled as independent observations. No acceptance relaxation.
- Supersedes: none; all prior failed evidence and arm/integration status retained.
- Next dependency: Stop penalty-coefficient tuning. Design a fixed-budget training-diversity comparison using explicitly reserved new training seeds,holding objective and steps constant,with all three seeds retained. Diagnose whether repeatedly reusing600 training scenes limits robustness; keep new training seeds separate from future qualification data and keep all current models unqualified.


### E-20260926-AI-213 — anchor replication verification

- Stage: S1
- Lane: AI
- Commit: `23ccd07d96acfc2ac3af0eb3e05ccd400200d101` (frozen source; results/tests committed with evidence)
- Change: anchor replication verification.
- Inputs/fixtures: AI-208 seed260926 plus260927/260928; training14M600 x4,development15M200 x4; identical initial/teacher checkpoint0fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d,key-loss4epochs,AdamW0.0001,batch64,anchor coefficient1. Source hashes in train/pose_anchor_replica_*_plan.json and eval/pose_anchor_replication_v0_plan.json; generated hashes in replica and aggregate reports.
- Command: `python -m pytest -q software/ai/tests/test_anchor_replicas.py`
- Result: PASS,2 tests: fixed experiment parameters,exact source/checkpoint/input/teacher hashes,all three runs retained,aggregate metrics and pass statuses. Existing pytest-asyncio warning.
- Artifacts: train/train_pose_anchor_replicas.py; vision/summarize_anchor_replicas.py; eval/pose_anchor_replica_*_report.json; eval/pose_anchor_replication_v0_report.json; tests/test_anchor_replicas.py.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Implementation verification; batch unchanged,shared boundary tests not triggered.
- Supersedes: none; all prior failed evidence and arm/integration status retained.
- Next dependency: Stop penalty-coefficient tuning. Design a fixed-budget training-diversity comparison using explicitly reserved new training seeds,holding objective and steps constant,with all three seeds retained. Diagnose whether repeatedly reusing600 training scenes limits robustness; keep new training seeds separate from future qualification data and keep all current models unqualified.


### E-20260926-AI-214 — anchor replication publication audit

- Stage: S1
- Lane: AI
- Commit: `23ccd07d96acfc2ac3af0eb3e05ccd400200d101` (frozen source; results/tests committed with evidence)
- Change: anchor replication publication audit.
- Inputs/fixtures: AI-208 seed260926 plus260927/260928; training14M600 x4,development15M200 x4; identical initial/teacher checkpoint0fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d,key-loss4epochs,AdamW0.0001,batch64,anchor coefficient1. Source hashes in train/pose_anchor_replica_*_plan.json and eval/pose_anchor_replication_v0_plan.json; generated hashes in replica and aggregate reports.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS;6025 paths,849.9 MiB,0 unresolved findings,14 reviewed synthetic fixtures.
- Artifacts: train/train_pose_anchor_replicas.py; vision/summarize_anchor_replicas.py; eval/pose_anchor_replica_*_report.json; eval/pose_anchor_replication_v0_report.json; tests/test_anchor_replicas.py.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic audit; AI-041 protected-main publication blocker retained.
- Supersedes: none; all prior failed evidence and arm/integration status retained.
- Next dependency: Stop penalty-coefficient tuning. Design a fixed-budget training-diversity comparison using explicitly reserved new training seeds,holding objective and steps constant,with all three seeds retained. Diagnose whether repeatedly reusing600 training scenes limits robustness; keep new training seeds separate from future qualification data and keep all current models unqualified.
### E-20260926-INT-005 — clean-clone AI/arm synchronization checkpoint

- Stage: S1/S3 boundary maintenance
- Lane: INTEGRATION
- Change: synchronized the AI evidence branch with current protected `main`
  (`0f17c61`) and made frozen AI artifact verification portable to a clean
  GitHub checkout. Repository-required inputs remain mandatory. Checkpoints
  intentionally excluded by `/software/ai/results/` remain identified by exact
  path and SHA-256; their bytes are verified whenever locally present and their
  absence is explicitly represented when not present.
- Inputs/fixtures: unchanged AI-202 and AI-208 frozen plans/reports; unchanged
  v2 `ModelMotionBatch` boundary; current ARM-045 phase-local contact gate.
- Commands: targeted AI evidence tests; the explicit portable test selection
  from `scripts/ci/offline_checks.py`; `scripts/ci/check_docs.py`; compile checks.
- Result: PASS. Newest key-loss and anchor evidence plus verifier tests passed,
  10 tests. Shared AI/arm boundary selection passed, 203 tests. Documentation
  passed for 26 maintained documents, eight public titles, required navigation,
  and two SVG assets. Compile checks passed. Contract diff review found no
  model-to-arm schema change in the AI experiment series.
- Artifacts: `software/ai/evidence_artifacts.py`, verifier unit tests, and
  clean-clone-safe updates to `test_pose_keyloss.py` and
  `test_pose_anchor.py`. Frozen plans, reports, and recorded checkpoint digests
  were not rewritten.
- Hardware writes: 0
- Physical movements: 0
- Limitations: this verifies software lineage and interface compatibility, not
  model accuracy, model qualification, installed geometry, controller timing,
  or physical execution. AI-202 and AI-208 remain failed experiments. Ignored
  checkpoint bytes are not recoverable from GitHub by design; reproducing the
  byte-level training result still requires the separately retained artifacts.
- Supersedes: AI-203 and AI-209's trainer-machine-only test assumption. It does
  not supersede their experimental results or promote either candidate.
- Next dependency: keep training replication separate from the stable arm
  ingestion contract. Any future model-output schema change must update the
  shared contract fixtures and pass the 203-test boundary selection before arm
  integration work accepts it.


### E-20260926-AI-215 — replication evidence portability alignment

- Stage: S1
- Lane: AI
- Commit: `e89bc9526a275a1e31acdefa6e074d09e80991e9` (merged verifier source; replication-test adaptation committed with this evidence)
- Change: adopt INT-005 artifact verification in the new replication tests, preserving all frozen training artifacts and both workers' ledger entries.
- Inputs/fixtures: AI-211 replica plans/reports/checkpoint digests and INT-005 verifier fixtures; exact hashes retained in manifests.
- Command: `python -m pytest -q software/ai/tests/test_anchor_replicas.py software/ai/tests/test_evidence_artifacts.py`
- Result: PASS,7 tests. Required source artifacts remain mandatory; ignored checkpoints are verified when present and explicitly represented when absent.
- Artifacts: tests/test_anchor_replicas.py; unchanged evidence_artifacts.py.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Current run had local checkpoint bytes; absence behavior covered by verifier fixtures, not a new full clean-clone run. No accuracy/qualification or boundary change.
- Supersedes: AI-213 trainer-only checkpoint-presence assumption,not experimental results.
- Next dependency: AI-214 fixed-budget training-diversity comparison; protected-main integration remains separate.


### E-20260926-AI-216 — fixed-budget training diversity

- Stage: S1
- Lane: AI
- Commit: `d8f651ef83b897fde77a63c5ff8f4b7ef3f56075` (frozen source; results/tests committed with evidence)
- Change: fixed-budget training diversity.
- Inputs/fixtures: training seeds29000000..29002399 now permanently training-only. Control repeats first600 groups; candidate cycles four disjoint600group blocks. Each group four conditions,4epochs,AdamW0.0001,batch64,key loss+anchor1,optimization seeds260926/27/28. Development15000000..15000199 x4. Initial/teacher0fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d. Exact source hashes in train/pose_diversity_*_plan.json; per-epoch image/teacher and checkpoint hashes in reports.
- Command: `python software/ai/train/train_pose_diversity.py`
- Result: FAIL full rule for all3 seeds. Baseline passes2/3. Candidate total tails23/25/25 vs repeated-scene control22/23/24 and starting baseline32 each. Checkpoints SHA256: 260926/control=9f9137dc96ae478ff4c2b2e5fe8975c4755abfe1d4af992f1275c9790cfe2b46; 260926/occlusion=778504bfbd561786a1bd66a7ecd3ebe00080b2ce8e95082659f95b0b0ca9c671; 260927/control=6148954ca968df755fed858e7ca603b94eba07e4034da3a5c3765c168e9daf63; 260927/occlusion=a648d04a41403c5cf4d2e73fa4b6923d9dbfeda4824563a2a97366aeaf5cae2e; 260928/control=f92f66338ef40cce6978c177ef11de9246f3005bad140a0ca48368b34cd8b2d7; 260928/occlusion=d6a3d60470f7eda103e19558e4af9494ba7381f29f3baa65970f31c533254483
- Artifacts: train/train_pose_diversity.py; vision/summarize_pose_diversity.py; eval/pose_diversity_*_report.json; tests/test_pose_diversity.py.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Dataset identity/reuse changes with diversity; not an isolated count-only causal result. Larger set receives fewer repeats. Historical occlusion arm means diverse candidate; both arms use anchored key loss.
- Supersedes: none; previous failures and arm/integration status retained.
- Next dependency: Freeze one longer-budget paired comparison on these fixed training sets,cycling the2400-scene candidate corpus while repeating600-scene control under equal updates. Keep objective/criteria/three seeds unchanged to test whether additional training resolves the diversity tradeoff. No new scenes or qualification before development criteria pass.


### E-20260926-AI-217 — training diversity aggregation

- Stage: S1
- Lane: AI
- Commit: `d8f651ef83b897fde77a63c5ff8f4b7ef3f56075` (frozen source; results/tests committed with evidence)
- Change: training diversity aggregation.
- Inputs/fixtures: training seeds29000000..29002399 now permanently training-only. Control repeats first600 groups; candidate cycles four disjoint600group blocks. Each group four conditions,4epochs,AdamW0.0001,batch64,key loss+anchor1,optimization seeds260926/27/28. Development15000000..15000199 x4. Initial/teacher0fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d. Exact source hashes in train/pose_diversity_*_plan.json; per-epoch image/teacher and checkpoint hashes in reports.
- Command: `python software/ai/vision/summarize_pose_diversity.py`
- Result: All3 runs retained. Candidate appearance means0.801144/0.811246/0.842921mm; control0.808037/0.800634/0.822443,baseline0.833364. Mean candidate0.818437/control0.810371. No seed selection or model promotion.
- Artifacts: train/train_pose_diversity.py; vision/summarize_pose_diversity.py; eval/pose_diversity_*_report.json; tests/test_pose_diversity.py.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Three optimization seeds share reused development data; ranges are not confidence intervals. No qualification data consumed.
- Supersedes: none; previous failures and arm/integration status retained.
- Next dependency: Freeze one longer-budget paired comparison on these fixed training sets,cycling the2400-scene candidate corpus while repeating600-scene control under equal updates. Keep objective/criteria/three seeds unchanged to test whether additional training resolves the diversity tradeoff. No new scenes or qualification before development criteria pass.


### E-20260926-AI-218 — training diversity verification

- Stage: S1
- Lane: AI
- Commit: `d8f651ef83b897fde77a63c5ff8f4b7ef3f56075` (frozen source; results/tests committed with evidence)
- Change: training diversity verification.
- Inputs/fixtures: training seeds29000000..29002399 now permanently training-only. Control repeats first600 groups; candidate cycles four disjoint600group blocks. Each group four conditions,4epochs,AdamW0.0001,batch64,key loss+anchor1,optimization seeds260926/27/28. Development15000000..15000199 x4. Initial/teacher0fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d. Exact source hashes in train/pose_diversity_*_plan.json; per-epoch image/teacher and checkpoint hashes in reports.
- Command: `python -m pytest -q software/ai/tests/test_pose_diversity.py`
- Result: PASS,2 tests: disjoint candidate/repeated control ranges,9600presentations/152steps each,identical first-epoch pixels/teacher,per-epoch hashes,checkpoint identities and full aggregate reproduction. Existing pytest-asyncio warning.
- Artifacts: train/train_pose_diversity.py; vision/summarize_pose_diversity.py; eval/pose_diversity_*_report.json; tests/test_pose_diversity.py.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Implementation verification only; contract unchanged,shared boundary tests not triggered.
- Supersedes: none; previous failures and arm/integration status retained.
- Next dependency: Freeze one longer-budget paired comparison on these fixed training sets,cycling the2400-scene candidate corpus while repeating600-scene control under equal updates. Keep objective/criteria/three seeds unchanged to test whether additional training resolves the diversity tradeoff. No new scenes or qualification before development criteria pass.


### E-20260926-AI-219 — training diversity in-progress snapshot audit

- Stage: S1
- Lane: AI
- Commit: `d8f651ef83b897fde77a63c5ff8f4b7ef3f56075` (frozen source; results/tests committed with evidence)
- Change: training diversity in-progress snapshot audit.
- Inputs/fixtures: training seeds29000000..29002399 now permanently training-only. Control repeats first600 groups; candidate cycles four disjoint600group blocks. Each group four conditions,4epochs,AdamW0.0001,batch64,key loss+anchor1,optimization seeds260926/27/28. Development15000000..15000199 x4. Initial/teacher0fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d. Exact source hashes in train/pose_diversity_*_plan.json; per-epoch image/teacher and checkpoint hashes in reports.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS;6034 paths,851.0MiB,0 unresolved findings,14 reviewed synthetic fixtures.
- Artifacts: train/train_pose_diversity.py; vision/summarize_pose_diversity.py; eval/pose_diversity_*_report.json; tests/test_pose_diversity.py.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Audit ran while training was in progress; later numeric reports and aggregation were not all present at scan time. Heuristic audit,AI-041 protected-main blocker retained.
- Supersedes: none; previous failures and arm/integration status retained.
- Next dependency: Freeze one longer-budget paired comparison on these fixed training sets,cycling the2400-scene candidate corpus while repeating600-scene control under equal updates. Keep objective/criteria/three seeds unchanged to test whether additional training resolves the diversity tradeoff. No new scenes or qualification before development criteria pass.
### E-20260926-ARM-046 — single-use execution-review admission boundary

- Stage: S4
- Lane: ARM
- Change: added a closed, zero-authority review boundary for exactly one indexed
  v2 action. It binds the model batch/proposal, v2 trajectory envelope,
  phase-local collision/contact gate, installed collision-policy qualification,
  and installed-controller qualification evidence/report. The controller
  session and configuration epoch must match the trajectory.
- Command-management behavior: review lifetime is capped at 30 seconds; a
  review can be cancelled; exact-digest consumption is atomic and single-use;
  crossed, stale, synthetic, unreviewed, expired, cancelled, mismatched, and
  reused inputs reject. Concurrent consumers cannot both succeed.
- Safety behavior: the review and consumption receipt emit no controller or
  wire commands, perform no hardware access, grant no physical/contact
  authority, prohibit automatic retry, and explicitly report that no permit was
  issued. The safety supervisor remains the only future permit issuer.
- Artifacts: `single_action_execution_review_v1.py`, three closed JSON schemas,
  positive/rejection/tamper/stale/cancellation/expiry/concurrency tests, public
  application exports, portable CI selection, and assurance documentation.
- Artifact identity: implementation SHA-256
  `7f7ef24608bddcc1c01fc226aedd1ef3b3f6659bd2bdbb43ad513ade4b176b9b`;
  collision qualification, review, and consumption schema SHA-256 values
  `1b8d77263da5de5bbcb0813b912059473d80f07cb992a6ec3b7150ccadab2a97`,
  `d9b9569faeafece65fb264019f733bcfa15c43155c355a708144074d69ee112f`,
  and `0c04178ed15d6bf235f6c5d70b97fa9b8f2dc776c7bf2ce14107f8fa718c49b9`.
- Results: focused ARM-046 suite PASS, 7 tests; portable shared AI/arm
  selection PASS, 210 tests in 41.38 seconds; documentation PASS for 27
  maintained documents, eight public titles, required navigation, and two SVG
  assets; documentation self-tests PASS, 18 tests; compile and diff checks PASS.
- Evidence status: all passing physical-shaped unit inputs are modeled fixtures;
  no claim of installed measurement, independent custody, controller readiness,
  hardware write, or physical movement is made.
- Hardware writes: 0
- Physical movements: 0
- Supersedes: ARM-045 only for the missing offline execution-review seam. It
  does not supersede authentic installed evidence, safety-supervisor permit
  issuance, command encoding/writing, feedback correlation, or outcome
  verification.
- Next dependency: connect a valid consumed review to the existing safety
  supervisor so it may consider a short-lived motion permit, then require the
  sole writer to consume that permit exactly once and emit correlated lifecycle
  acknowledgements without automatic retry.


### E-20260926-AI-220 — longer fixed-budget diversity training

- Stage: S1
- Lane: AI
- Commit: `d00e0578245b7df3bed732d8730ac67a52244dc0` (frozen source; results/tests committed with evidence)
- Change: longer fixed-budget diversity training.
- Inputs/fixtures: same training-only29000000..29002399 corpus; control600scenes repeated8times,candidate2400scenes cycled twice. Four conditions,8epochs,AdamW0.0001,batch64,key loss+anchor1,seeds260926/27/28; development15M200 x4. Initial/teacher0fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d. Source hashes in train/pose_diversity_long_*_plan.json; per-epoch pixels/teacher/checkpoint hashes in reports.
- Command: `python software/ai/train/train_pose_diversity_long.py`
- Result: Full rule FAIL3/3; baseline comparisons PASS3/3. Candidate total tails21/23/24 vs control22/23/21 and baseline32each. Checkpoint SHA256: 260926/control=670cc2885b7891f8fd90227b1a91f1cd37f929c8c95e66b1ec2cdad75669e3f6; 260926/occlusion=ecef71cc550bb0a96fd04c6a10d5fd6bfb3b181c2cfacd956271a3a9ac63da4f; 260927/control=7d99e0e65db8eeb45b5f9dbbd1823a0bb9d830e009fc82d985304a3dc46a5a2d; 260927/occlusion=e690a56152824b5d7f1dd89eeaa8674170d3c57667d2f2dbcdc788ea2955f7ab; 260928/control=1c40688832e5e390ddd31ece36e3b8fe919d3967d0c218a27022c5cbd80af58e; 260928/occlusion=007d23669bb0272f1da15e37ecfb8553eeaf90f82f1e4395d60c68ce912d92f1
- Artifacts: train/train_pose_diversity_long.py; vision/summarize_pose_diversity_long.py; eval/pose_diversity_long_*_report.json; tests/test_pose_diversity_long.py.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Same reused development and GPU nondeterminism; no physical data or qualification. Both objectives unchanged; historical occlusion arm denotes diverse candidate.
- Supersedes: none; failed evidence and ARM-046 retained; no arm/integration status changes.
- Next dependency: Stop extending training budgets without diagnosis. Freeze cross-seed persistent-failure analysis of the retained long-run predictions,including failures shared by baseline/control/candidate and translation/rotation contributions. Identify systematic simulator or representation weaknesses before choosing another intervention; no qualification or runtime change.


### E-20260926-AI-221 — longer diversity aggregation

- Stage: S1
- Lane: AI
- Commit: `d00e0578245b7df3bed732d8730ac67a52244dc0` (frozen source; results/tests committed with evidence)
- Change: longer diversity aggregation.
- Inputs/fixtures: same training-only29000000..29002399 corpus; control600scenes repeated8times,candidate2400scenes cycled twice. Four conditions,8epochs,AdamW0.0001,batch64,key loss+anchor1,seeds260926/27/28; development15M200 x4. Initial/teacher0fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d. Source hashes in train/pose_diversity_long_*_plan.json; per-epoch pixels/teacher/checkpoint hashes in reports.
- Command: `python software/ai/vision/summarize_pose_diversity_long.py`
- Result: All3 seeds retained. Candidate appearance means0.818657/0.810537/0.815380mm,mean0.814858 vs control0.812969 and baseline0.833364. Four-epoch candidate tails23/25/25 become21/23/24; baseline passes2/3 become3/3. Paired-control dominance remains unestablished.
- Artifacts: train/train_pose_diversity_long.py; vision/summarize_pose_diversity_long.py; eval/pose_diversity_long_*_report.json; tests/test_pose_diversity_long.py.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Four/eight epoch training reruns can differ numerically on GPU; descriptive comparison,not exact-prefix counterfactual. No winning-seed selection or acceptance relaxation.
- Supersedes: none; failed evidence and ARM-046 retained; no arm/integration status changes.
- Next dependency: Stop extending training budgets without diagnosis. Freeze cross-seed persistent-failure analysis of the retained long-run predictions,including failures shared by baseline/control/candidate and translation/rotation contributions. Identify systematic simulator or representation weaknesses before choosing another intervention; no qualification or runtime change.


### E-20260926-AI-222 — longer diversity verification

- Stage: S1
- Lane: AI
- Commit: `d00e0578245b7df3bed732d8730ac67a52244dc0` (frozen source; results/tests committed with evidence)
- Change: longer diversity verification.
- Inputs/fixtures: same training-only29000000..29002399 corpus; control600scenes repeated8times,candidate2400scenes cycled twice. Four conditions,8epochs,AdamW0.0001,batch64,key loss+anchor1,seeds260926/27/28; development15M200 x4. Initial/teacher0fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d. Source hashes in train/pose_diversity_long_*_plan.json; per-epoch pixels/teacher/checkpoint hashes in reports.
- Command: `python -m pytest -q software/ai/tests/test_pose_diversity_long.py`
- Result: PASS,2 tests: corpus wrap/reuse,19200presentations/304updates each,first-epoch equality,exact reused image hashes versus four-epoch study,checkpoint/source lineage and aggregate reproduction. Existing pytest-asyncio warning.
- Artifacts: train/train_pose_diversity_long.py; vision/summarize_pose_diversity_long.py; eval/pose_diversity_long_*_report.json; tests/test_pose_diversity_long.py.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Implementation verification only; batch unchanged,shared boundary suite not triggered.
- Supersedes: none; failed evidence and ARM-046 retained; no arm/integration status changes.
- Next dependency: Stop extending training budgets without diagnosis. Freeze cross-seed persistent-failure analysis of the retained long-run predictions,including failures shared by baseline/control/candidate and translation/rotation contributions. Identify systematic simulator or representation weaknesses before choosing another intervention; no qualification or runtime change.


### E-20260926-AI-223 — longer diversity publication audit

- Stage: S1
- Lane: AI
- Commit: `d00e0578245b7df3bed732d8730ac67a52244dc0` (frozen source; results/tests committed with evidence)
- Change: longer diversity publication audit.
- Inputs/fixtures: same training-only29000000..29002399 corpus; control600scenes repeated8times,candidate2400scenes cycled twice. Four conditions,8epochs,AdamW0.0001,batch64,key loss+anchor1,seeds260926/27/28; development15M200 x4. Initial/teacher0fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d. Source hashes in train/pose_diversity_long_*_plan.json; per-epoch pixels/teacher/checkpoint hashes in reports.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS;6056paths,856.3MiB,0 unresolved findings,14 reviewed synthetic fixtures.
- Artifacts: train/train_pose_diversity_long.py; vision/summarize_pose_diversity_long.py; eval/pose_diversity_long_*_report.json; tests/test_pose_diversity_long.py.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic audit; protected-main publication blocker AI-041 retained.
- Supersedes: none; failed evidence and ARM-046 retained; no arm/integration status changes.
- Next dependency: Stop extending training budgets without diagnosis. Freeze cross-seed persistent-failure analysis of the retained long-run predictions,including failures shared by baseline/control/candidate and translation/rotation contributions. Identify systematic simulator or representation weaknesses before choosing another intervention; no qualification or runtime change.


### E-20260926-AI-224 — cross-seed persistent failure diagnosis

- Stage: S1
- Lane: AI
- Commit: `4905a0e3c9ccf29aedcc78596bc89b1cc2f96792` (frozen source; results/tests committed with evidence)
- Change: cross-seed persistent failure diagnosis.
- Inputs/fixtures: retained AI-220 long-run reports,seeds260926/27/28; 800 development cases15000000..15000199 x4,baseline counted once and six trained predictions per case. Exact source/report hashes in eval/persistent_pose_v0_plan.json.
- Command: `python software/ai/vision/diagnose_persistent_pose.py`
- Result: Completed.19/800 image cases fail all6 trained predictions: standard3,appearance5,partial4,full7. All19 also fail starting baseline;114/134 trained failure occurrences (85.07%) are persistent. Translation larger in a majority of predictions for8/19 persistent cases; rotation magnitude dominates the remaining11. Baseline failures recovered by all6: standard1,appearance0,partial3,full2.
- Artifacts: vision/diagnose_persistent_pose.py; eval/persistent_pose_v0_report.json; tests/test_persistent_pose.py.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Repeated cases are not independent trials; component magnitudes do not prove causal defects. No uncertainty claim or oracle correction.
- Supersedes: none; previous failures and arm/integration status retained.
- Next dependency: Freeze a visual/renderer audit of these19 persistent cases alongside matched successful cases. Inspect occlusion,visibility,cropping,pose extremes and label alignment before a targeted training/representation change. Preserve all cases in scoring; no hand correction or exclusion based on development truth.


### E-20260926-AI-225 — persistent failure verification

- Stage: S1
- Lane: AI
- Commit: `4905a0e3c9ccf29aedcc78596bc89b1cc2f96792` (frozen source; results/tests committed with evidence)
- Change: persistent failure verification.
- Inputs/fixtures: retained AI-220 long-run reports,seeds260926/27/28; 800 development cases15000000..15000199 x4,baseline counted once and six trained predictions per case. Exact source/report hashes in eval/persistent_pose_v0_plan.json.
- Command: `python -m pytest -q software/ai/tests/test_persistent_pose.py`
- Result: PASS,2 tests: baseline counted once,all-six versus five-case threshold,source hashes,all800 rows and134failure occurrences reproduced. Existing pytest-asyncio warning.
- Artifacts: vision/diagnose_persistent_pose.py; eval/persistent_pose_v0_report.json; tests/test_persistent_pose.py.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Implementation verification only; batch unchanged,shared boundary tests not triggered.
- Supersedes: none; previous failures and arm/integration status retained.
- Next dependency: Freeze a visual/renderer audit of these19 persistent cases alongside matched successful cases. Inspect occlusion,visibility,cropping,pose extremes and label alignment before a targeted training/representation change. Preserve all cases in scoring; no hand correction or exclusion based on development truth.


### E-20260926-AI-226 — persistent failure publication audit

- Stage: S1
- Lane: AI
- Commit: `4905a0e3c9ccf29aedcc78596bc89b1cc2f96792` (frozen source; results/tests committed with evidence)
- Change: persistent failure publication audit.
- Inputs/fixtures: retained AI-220 long-run reports,seeds260926/27/28; 800 development cases15000000..15000199 x4,baseline counted once and six trained predictions per case. Exact source/report hashes in eval/persistent_pose_v0_plan.json.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS;6060paths,856.5MiB,0 unresolved findings,14 reviewed synthetic fixtures.
- Artifacts: vision/diagnose_persistent_pose.py; eval/persistent_pose_v0_report.json; tests/test_persistent_pose.py.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic audit; AI-041 protected-main publication blocker retained.
- Supersedes: none; previous failures and arm/integration status retained.
- Next dependency: Freeze a visual/renderer audit of these19 persistent cases alongside matched successful cases. Inspect occlusion,visibility,cropping,pose extremes and label alignment before a targeted training/representation change. Preserve all cases in scoring; no hand correction or exclusion based on development truth.
### E-20260926-ARM-047 — reviewed permit bridge and lifecycle acknowledgements

- Stage: S4
- Lane: ARM
- Change: connected one consumed ARM-046 review to the existing
  `SafetySupervisor`. The bridge derives the required capability from the
  review's exact lowercase device and uppercase interaction fields, uses the
  review digest as the supervisor plan hash, and enumerates exact goal hashes.
- Runtime behavior: the supervisor still rechecks current build capability,
  calibration, interlocks, runtime health, operator arming, and safety state.
  Only it can issue the short-lived permit. A crossed/tampered receipt, wrong
  capability, missing current condition, or authorization failure rejects.
- Lifecycle behavior: hash-chained `ACCEPTED`, `STARTED`, and exactly one
  `COMPLETED`, `FAILED`, or `UNCERTAIN` acknowledgement are supported. Every
  state explicitly denies automatic retry and follow-on movement.
- Artifacts: `reviewed_motion_permit_bridge_v1.py`, closed admission/lifecycle
  schemas, compatibility/rejection/preflight/terminal tests, public exports,
  and portable CI selection.
- Artifact identity: implementation SHA-256
  `0b888d409124fdfaaa24c82c14249e1e7ecb47a8103c37f4c8c2096545b0964c`;
  admission and lifecycle schema SHA-256 values
  `a945e7cd20098efa70c13dd2f2c0149f83ccd67a06ca6f56ddc7a6ac157df3fc`
  and `896014f3fd0945e6a59be8d004d5971fbb9834cb1a8d579eed3a666125a48408`.
- Results: focused ARM-046/047 suite PASS, 13 tests; portable shared AI/arm
  selection PASS, 216 tests in 30.31 seconds; compile and diff checks PASS.
- Hardware writes: 0
- Physical movements: 0
- Limitations: tests use modeled released-build and physical-shaped evidence.
  The lifecycle consumes acknowledgements supplied by a future sole writer; it
  does not itself prove a native write, arrival, settling, contact, or outcome.
- Supersedes: ARM-046's missing supervisor-permit bridge and lifecycle contract.
  It does not supersede authentic installed evidence, sole-writer integration,
  transport receipts, feedback verification, or independent task observation.
- Next dependency: integrate the exact-goal permit and lifecycle with the sole
  writable adapter so permit consumption occurs at the final outbound boundary,
  then bind controller receipt, feedback/settling, and independent outcome
  evidence without adding any retry path.


### E-20260926-AI-227 — visual audit dependency failure

- Stage: S1
- Lane: AI
- Commit: `6270eb27847a7c42e3fae2af89d4d5db7ab03fc7`
- Command: `python software/ai/vision/audit_persistent_visual.py`
- Inputs/fixtures: exact hashes in eval/persistent_visual_v0_plan.json,19 persistent cases and same-condition controls.
- Result: FAILED before rendering: ModuleNotFoundError matplotlib. No report or figures produced.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Local plotting dependency absent; no visual conclusion.
- Next dependency: install plotting dependency and rerun unchanged frozen script; preserve this failure.


### E-20260926-AI-228 — visual audit environment recovery

- Stage: S1
- Lane: AI
- Commit: `6270eb27847a7c42e3fae2af89d4d5db7ab03fc7` (frozen runner/plan;results and review committed with evidence)
- Change: visual audit environment recovery.
- Inputs/fixtures: AI-224 retained19persistent cases;nearest normalized-pose same-condition zero-failure controls,seed tie-break,with replacement. Exact source hashes in eval/persistent_visual_v0_plan.json;image/figure hashes in report.
- Command: `python -m pip install matplotlib; python -m pip install numpy==1.26.3 matplotlib==3.9.4 contourpy==1.3.2`
- Result: Initial install selected numpy2.5.3; restored original1.26.3 before evaluation,matplotlib3.9.4/contourpy1.3.2 installed.
- Artifacts: eval/persistent_visual_v0_report.json;eval/persistent_visual_v0_page_1.png through page_4.png;docs/PERSISTENT_SCENE_REVIEW.md;tests/test_persistent_visual.py.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Local dependency change,not model training. Pip reports pre-existing datasets missing pyarrow; unrelated to renderer. AI-227 retained.
- Supersedes: none;failed dependency attempt and all arm evidence retained.
- Next dependency: Freeze RNG-preserving arm-line/ruler renderer ablations over all development cases; retain unmodified results,no training or qualification. Publish only AI branch feature/translation-pair-evidence to verified canonical j-webtek/tactevra remote.


### E-20260926-AI-229 — persistent scene renderer and visual review

- Stage: S1
- Lane: AI
- Commit: `6270eb27847a7c42e3fae2af89d4d5db7ab03fc7` (frozen runner/plan;results and review committed with evidence)
- Change: persistent scene renderer and visual review.
- Inputs/fixtures: AI-224 retained19persistent cases;nearest normalized-pose same-condition zero-failure controls,seed tie-break,with replacement. Exact source hashes in eval/persistent_visual_v0_plan.json;image/figure hashes in report.
- Command: `python software/ai/vision/audit_persistent_visual.py`
- Result: Completed unchanged frozen script.19failures/19matched control slots;cropped0/0,vector label error0px,foreground means2.6475%/0.8099%,fewer-than3corners1/0,pose-extreme3/2. Viewed all4 figure pages. Nearby arm-like lines/ruler clutter recur,including near-zero-overlap failures; causal sensitivity remains a hypothesis.
- Artifacts: eval/persistent_visual_v0_report.json;eval/persistent_visual_v0_page_1.png through page_4.png;docs/PERSISTENT_SCENE_REVIEW.md;tests/test_persistent_visual.py.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Selected reused synthetic development,matched with replacement;no raster/physical label qualification. No exclusion or correction.
- Supersedes: none;failed dependency attempt and all arm evidence retained.
- Next dependency: Freeze RNG-preserving arm-line/ruler renderer ablations over all development cases; retain unmodified results,no training or qualification. Publish only AI branch feature/translation-pair-evidence to verified canonical j-webtek/tactevra remote.


### E-20260926-AI-230 — visual review verification

- Stage: S1
- Lane: AI
- Commit: `6270eb27847a7c42e3fae2af89d4d5db7ab03fc7` (frozen runner/plan;results and review committed with evidence)
- Change: visual review verification.
- Inputs/fixtures: AI-224 retained19persistent cases;nearest normalized-pose same-condition zero-failure controls,seed tie-break,with replacement. Exact source hashes in eval/persistent_visual_v0_plan.json;image/figure hashes in report.
- Command: `python -m pytest -q software/ai/tests/test_persistent_visual.py software/ai/tests/test_pose_diversity_long.py`
- Result: PASS,3 tests: frozen hashes,figure identities,pair outcome/condition membership,geometry checks,and prior training-budget lineage after NumPy restoration. Existing pytest-asyncio warning.
- Artifacts: eval/persistent_visual_v0_report.json;eval/persistent_visual_v0_page_1.png through page_4.png;docs/PERSISTENT_SCENE_REVIEW.md;tests/test_persistent_visual.py.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Implementation verification;batch unchanged,shared boundary suite not triggered.
- Supersedes: none;failed dependency attempt and all arm evidence retained.
- Next dependency: Freeze RNG-preserving arm-line/ruler renderer ablations over all development cases; retain unmodified results,no training or qualification. Publish only AI branch feature/translation-pair-evidence to verified canonical j-webtek/tactevra remote.


### E-20260926-AI-231 — visual review publication audit

- Stage: S1
- Lane: AI
- Commit: `6270eb27847a7c42e3fae2af89d4d5db7ab03fc7` (frozen runner/plan;results and review committed with evidence)
- Change: visual review publication audit.
- Inputs/fixtures: AI-224 retained19persistent cases;nearest normalized-pose same-condition zero-failure controls,seed tie-break,with replacement. Exact source hashes in eval/persistent_visual_v0_plan.json;image/figure hashes in report.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS;6073paths,857.1MiB,0 unresolved findings,14 reviewed synthetic fixtures.
- Artifacts: eval/persistent_visual_v0_report.json;eval/persistent_visual_v0_page_1.png through page_4.png;docs/PERSISTENT_SCENE_REVIEW.md;tests/test_persistent_visual.py.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic audit;AI-041 protected-main publication blocker retained.
- Supersedes: none;failed dependency attempt and all arm evidence retained.
- Next dependency: Freeze RNG-preserving arm-line/ruler renderer ablations over all development cases; retain unmodified results,no training or qualification. Publish only AI branch feature/translation-pair-evidence to verified canonical j-webtek/tactevra remote.


### E-20260926-AI-232 — RNG-preserving clutter intervention

- Stage: S1
- Lane: AI
- Commit: `ae5276557e5f208ce9292975e01c2e19a00c78fb` (frozen source;results/tests committed with evidence)
- Change: RNG-preserving clutter intervention.
- Inputs/fixtures: all800 reused15M200 x4 development cases,original/no-arm/no-ruler/neither;checkpoint0fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d,CPU128x96. Exact source/report/checkpoint hashes eval/clutter_ablation_v0_plan.json;per-mode pixel hashes in report.
- Command: `python software/ai/vision/evaluate_clutter_ablation.py`
- Result: Completed. All800 originals reproduce RGB/masks/labels and baseline pose metrics;all intervention poses identical. Failures original32,no-arm17,no-ruler25,neither11. Recovered15/7/21 respectively,introduced0each. Of19persistent cases,remaining10/15/6. Original-vs-neither means standard0.853->0.737,appearance0.833->0.731,partial1.026->0.927,full1.229->1.131mm.
- Artifacts: vision/clutter_ablation_renderer.py;vision/clutter_ablation_occlusions.py;vision/evaluate_clutter_ablation.py;eval/clutter_ablation_v0_report.json;tests/test_clutter_ablation.py;docs/PERSISTENT_SCENE_REVIEW.md.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Established baseline checkpoint only; synthetic layer removal,not physical clutter robustness. Blur/contrast/normalization spread effects beyond line pixels. No runtime cleanup,training or acceptance exclusion.
- Supersedes: none;prior failures and arm/integration status retained.
- Next dependency: Freeze training-only paired-clutter consistency comparison with identical pose supervision,common budget and fixed coefficient;evaluate original unmodified development scenes. No runtime clutter removal or model qualification. Publish only feature/translation-pair-evidence to j-webtek/tactevra.


### E-20260926-AI-233 — clutter intervention verification

- Stage: S1
- Lane: AI
- Commit: `ae5276557e5f208ce9292975e01c2e19a00c78fb` (frozen source;results/tests committed with evidence)
- Change: clutter intervention verification.
- Inputs/fixtures: all800 reused15M200 x4 development cases,original/no-arm/no-ruler/neither;checkpoint0fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d,CPU128x96. Exact source/report/checkpoint hashes eval/clutter_ablation_v0_plan.json;per-mode pixel hashes in report.
- Command: `python -m pytest -q software/ai/tests/test_clutter_ablation.py`
- Result: PASS,2 tests: original pixel/label/mask equality,pose/corner invariance,mask subset behavior,frozen hashes and report recovery/new-failure recount. Existing pytest-asyncio warning.
- Artifacts: vision/clutter_ablation_renderer.py;vision/clutter_ablation_occlusions.py;vision/evaluate_clutter_ablation.py;eval/clutter_ablation_v0_report.json;tests/test_clutter_ablation.py;docs/PERSISTENT_SCENE_REVIEW.md.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Implementation verification only;batch unchanged,shared boundary suite not triggered.
- Supersedes: none;prior failures and arm/integration status retained.
- Next dependency: Freeze training-only paired-clutter consistency comparison with identical pose supervision,common budget and fixed coefficient;evaluate original unmodified development scenes. No runtime clutter removal or model qualification. Publish only feature/translation-pair-evidence to j-webtek/tactevra.


### E-20260926-AI-234 — clutter intervention publication audit

- Stage: S1
- Lane: AI
- Commit: `ae5276557e5f208ce9292975e01c2e19a00c78fb` (frozen source;results/tests committed with evidence)
- Change: clutter intervention publication audit.
- Inputs/fixtures: all800 reused15M200 x4 development cases,original/no-arm/no-ruler/neither;checkpoint0fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d,CPU128x96. Exact source/report/checkpoint hashes eval/clutter_ablation_v0_plan.json;per-mode pixel hashes in report.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS;6079paths,858.5MiB,0 unresolved findings,14 reviewed synthetic fixtures.
- Artifacts: vision/clutter_ablation_renderer.py;vision/clutter_ablation_occlusions.py;vision/evaluate_clutter_ablation.py;eval/clutter_ablation_v0_report.json;tests/test_clutter_ablation.py;docs/PERSISTENT_SCENE_REVIEW.md.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic audit;AI-041 protected-main publication blocker retained.
- Supersedes: none;prior failures and arm/integration status retained.
- Next dependency: Freeze training-only paired-clutter consistency comparison with identical pose supervision,common budget and fixed coefficient;evaluate original unmodified development scenes. No runtime clutter removal or model qualification. Publish only feature/translation-pair-evidence to j-webtek/tactevra.


### E-20260926-AI-235 — paired clutter consistency training

- Stage: S1
- Lane: AI
- Commit: `193da276fb502aa86af2e0342746496be30f6227` (frozen source;results/tests committed with evidence)
- Change: paired clutter consistency training.
- Inputs/fixtures: training29000000..29000599 x4 paired original/removed-arm-and-ruler,identical pose supervision;4epochs,152updates,AdamW0.0001,batch64pairs,anchor1 in both arms,consistency1 candidate only,seeds260926/27/28. Original unmodified15M200 x4 development. Initial/teacher0fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d. Exact source hashes train/pose_clutter_pair_*_plan.json;pixel/teacher/checkpoint hashes in reports.
- Command: `python software/ai/train/train_pose_clutter_pair.py`
- Result: Full rule FAIL3/3,baseline pass1/3. Candidate tails20/22/26 vs paired-supervision control21/22/25 and baseline32each. Both arms see identical pair images/teacher predictions. Checkpoint SHA256: 260926/control=d00856fea028459271b8a6950c20e5abba60f40a1b78f9558ae6479e6157a3af; 260926/occlusion=a05ae9481cfae5af90703054f22820bc318b4e5a4c25841f8cb832e4a890c67c; 260927/control=e74d1d656e0b21e9522788aa24cf12d1c2a9f46e28b707e2a039d2217e11bfa5; 260927/occlusion=2f0cbd5e3906869abde4cb6d78cd1d90b7119f1f26cae68c956ee435ac7519a9; 260928/control=4e93e8da1331d0af156032c04bee9020d71bbf847b2657104c6c75c920e29842; 260928/occlusion=361e5037bb48d7644e148aedeb3a2df92060a52d2e9f255a9f333df04c11fa1e
- Artifacts: train/train_pose_clutter_pair.py;vision/summarize_pose_clutter_pair.py;eval/pose_clutter_pair_*_report.json;tests/test_pose_clutter_pair.py.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Single fixed coefficient,three seeds,reused synthetic development. Symmetric consistency has no demonstrated advantage. Historical occlusion arm means consistency candidate. No model promotion or runtime cleanup.
- Supersedes: none;prior failures and arm/integration status retained.
- Next dependency: Stop consistency-coefficient tuning. Review earlier matched-resolution evidence against current clutter failures before choosing a bounded representation/input-resolution intervention; avoid duplicating a previously failed comparison. Original cluttered cases remain acceptance data; no qualification.


### E-20260926-AI-236 — paired clutter consistency aggregation

- Stage: S1
- Lane: AI
- Commit: `193da276fb502aa86af2e0342746496be30f6227` (frozen source;results/tests committed with evidence)
- Change: paired clutter consistency aggregation.
- Inputs/fixtures: training29000000..29000599 x4 paired original/removed-arm-and-ruler,identical pose supervision;4epochs,152updates,AdamW0.0001,batch64pairs,anchor1 in both arms,consistency1 candidate only,seeds260926/27/28. Original unmodified15M200 x4 development. Initial/teacher0fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d. Exact source hashes train/pose_clutter_pair_*_plan.json;pixel/teacher/checkpoint hashes in reports.
- Command: `python software/ai/vision/summarize_pose_clutter_pair.py`
- Result: All3 runs retained;mean total failures both22.667. Candidate appearance means0.808281/0.815878/0.841149,average0.821769 vs control0.814087 and baseline0.833364. One-seed improvement reverses on another.
- Artifacts: train/train_pose_clutter_pair.py;vision/summarize_pose_clutter_pair.py;eval/pose_clutter_pair_*_report.json;tests/test_pose_clutter_pair.py.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Same evaluation images across seeds;descriptive ranges,not independent data replication or significance proof.
- Supersedes: none;prior failures and arm/integration status retained.
- Next dependency: Stop consistency-coefficient tuning. Review earlier matched-resolution evidence against current clutter failures before choosing a bounded representation/input-resolution intervention; avoid duplicating a previously failed comparison. Original cluttered cases remain acceptance data; no qualification.


### E-20260926-AI-237 — paired clutter consistency verification

- Stage: S1
- Lane: AI
- Commit: `193da276fb502aa86af2e0342746496be30f6227` (frozen source;results/tests committed with evidence)
- Change: paired clutter consistency verification.
- Inputs/fixtures: training29000000..29000599 x4 paired original/removed-arm-and-ruler,identical pose supervision;4epochs,152updates,AdamW0.0001,batch64pairs,anchor1 in both arms,consistency1 candidate only,seeds260926/27/28. Original unmodified15M200 x4 development. Initial/teacher0fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d. Exact source hashes train/pose_clutter_pair_*_plan.json;pixel/teacher/checkpoint hashes in reports.
- Command: `python -m pytest -q software/ai/tests/test_pose_clutter_pair.py`
- Result: PASS,2 tests: symmetric nonzero gradients to both predictions,zero identical-pair loss,equal pair/input/teacher identities,2400pairs/epoch,19200presentations,checkpoint hashes,epoch selection,unchanged original development pixels and aggregate recount. Existing pytest-asyncio warning.
- Artifacts: train/train_pose_clutter_pair.py;vision/summarize_pose_clutter_pair.py;eval/pose_clutter_pair_*_report.json;tests/test_pose_clutter_pair.py.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Implementation verification only;batch unchanged,shared boundary suite not triggered.
- Supersedes: none;prior failures and arm/integration status retained.
- Next dependency: Stop consistency-coefficient tuning. Review earlier matched-resolution evidence against current clutter failures before choosing a bounded representation/input-resolution intervention; avoid duplicating a previously failed comparison. Original cluttered cases remain acceptance data; no qualification.


### E-20260926-AI-238 — paired clutter publication audit

- Stage: S1
- Lane: AI
- Commit: `193da276fb502aa86af2e0342746496be30f6227` (frozen source;results/tests committed with evidence)
- Change: paired clutter publication audit.
- Inputs/fixtures: training29000000..29000599 x4 paired original/removed-arm-and-ruler,identical pose supervision;4epochs,152updates,AdamW0.0001,batch64pairs,anchor1 in both arms,consistency1 candidate only,seeds260926/27/28. Original unmodified15M200 x4 development. Initial/teacher0fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d. Exact source hashes train/pose_clutter_pair_*_plan.json;pixel/teacher/checkpoint hashes in reports.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS;6089paths,861.7MiB,0 unresolved findings,14 reviewed synthetic fixtures.
- Artifacts: train/train_pose_clutter_pair.py;vision/summarize_pose_clutter_pair.py;eval/pose_clutter_pair_*_report.json;tests/test_pose_clutter_pair.py.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic audit;AI-041 protected-main blocker retained.
- Supersedes: none;prior failures and arm/integration status retained.
- Next dependency: Stop consistency-coefficient tuning. Review earlier matched-resolution evidence against current clutter failures before choosing a bounded representation/input-resolution intervention; avoid duplicating a previously failed comparison. Original cluttered cases remain acceptance data; no qualification.


### E-20260926-AI-239 — resolution and representation evidence review

- Stage: S1
- Lane: AI
- Commit: `45542e9bb679c982a08ce8e4631a5157939e23b2` (frozen source;results/review/tests committed with evidence)
- Change: resolution and representation evidence review.
- Inputs/fixtures: retained AI-025 resolution plan/scorecard,AI-232 clutter report,AI-236 paired-clutter aggregate,exact pose model source. All SHA256 pinned in eval/representation_review_v0_plan.json. Zero tensors used only to trace feature shapes,not accuracy.
- Command: `python software/ai/vision/review_pose_representation.py`
- Result: Completed. Prior128x96mean0.945128mm,p952.064873 versus256x192mean1.442204,p953.529652;larger mean52.59%worse in that adaptation study. Model276867parameters;last convolution spatial map6x8 vs12x16,both pooled4x4. Retain128x96 and prepare visible-keyboard segmentation auxiliary feasibility study.
- Artifacts: vision/review_pose_representation.py;eval/representation_review_v0_report.json;docs/POSE_REPRESENTATION_REVIEW.md;tests/test_representation_review.py.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Old comparison one seed,128-trained starting weights,different conditions/loss;not proof higher resolution cannot help. Shape inspection not causal evidence. New head is untested;no training or model promotion.
- Supersedes: none;prior failures and arm/integration status retained.
- Next dependency: Implement and verify training-only visible-case segmentation labels and an auxiliary head at the shared stride-four feature map;ensure unchanged initial pose output,inspect fixed-batch gradient scale,then freeze a paired training study. No runtime segmentation authority,contract change or qualification. Publish only feature/translation-pair-evidence to j-webtek/tactevra.


### E-20260926-AI-240 — representation review verification

- Stage: S1
- Lane: AI
- Commit: `45542e9bb679c982a08ce8e4631a5157939e23b2` (frozen source;results/review/tests committed with evidence)
- Change: representation review verification.
- Inputs/fixtures: retained AI-025 resolution plan/scorecard,AI-232 clutter report,AI-236 paired-clutter aggregate,exact pose model source. All SHA256 pinned in eval/representation_review_v0_plan.json. Zero tensors used only to trace feature shapes,not accuracy.
- Command: `python -m pytest -q software/ai/tests/test_representation_review.py`
- Result: PASS,1 test: frozen hashes,exact old metrics/ratio,clutter totals and zero-authority markers. Existing pytest-asyncio warning.
- Artifacts: vision/review_pose_representation.py;eval/representation_review_v0_report.json;docs/POSE_REPRESENTATION_REVIEW.md;tests/test_representation_review.py.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Retained evidence verification only;batch unchanged,shared boundary suite not triggered.
- Supersedes: none;prior failures and arm/integration status retained.
- Next dependency: Implement and verify training-only visible-case segmentation labels and an auxiliary head at the shared stride-four feature map;ensure unchanged initial pose output,inspect fixed-batch gradient scale,then freeze a paired training study. No runtime segmentation authority,contract change or qualification. Publish only feature/translation-pair-evidence to j-webtek/tactevra.


### E-20260926-AI-241 — representation review publication audit

- Stage: S1
- Lane: AI
- Commit: `45542e9bb679c982a08ce8e4631a5157939e23b2` (frozen source;results/review/tests committed with evidence)
- Change: representation review publication audit.
- Inputs/fixtures: retained AI-025 resolution plan/scorecard,AI-232 clutter report,AI-236 paired-clutter aggregate,exact pose model source. All SHA256 pinned in eval/representation_review_v0_plan.json. Zero tensors used only to trace feature shapes,not accuracy.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS;6094paths,861.7MiB,0 unresolved findings,14 reviewed synthetic fixtures.
- Artifacts: vision/review_pose_representation.py;eval/representation_review_v0_report.json;docs/POSE_REPRESENTATION_REVIEW.md;tests/test_representation_review.py.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic audit;AI-041 protected-main publication blocker retained.
- Supersedes: none;prior failures and arm/integration status retained.
- Next dependency: Implement and verify training-only visible-case segmentation labels and an auxiliary head at the shared stride-four feature map;ensure unchanged initial pose output,inspect fixed-batch gradient scale,then freeze a paired training study. No runtime segmentation authority,contract change or qualification. Publish only feature/translation-pair-evidence to j-webtek/tactevra.


### E-20260926-AI-242 — visible-case auxiliary feasibility

- Stage: S1
- Lane: AI
- Commit: `45836f58301d7173c4e7b72fd213b13a796eb758` (frozen source;results/tests committed with evidence)
- Change: visible-case auxiliary feasibility.
- Inputs/fixtures: training-only starts29000000/008/016/024,8groups x4conditions per batch,rectangle occlusion,CPU128x96. Initial checkpoint0fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d;seed260926,balanced mask BCE vs key loss,coefficient0.001 preregistered. Exact source hashes eval/segmentation_feasibility_v0_plan.json;pixel/target hashes in report.
- Command: `python software/ai/vision/diagnose_segmentation_auxiliary.py`
- Result: Completed:33extra parameters,24x32soft-area masks;exact initial pose equality on128 training images. Coefficient0.001 auxiliary/shared pose-gradient ratios0.012182/0.018737/0.002851/0.007475;cosines0.01051/0.00781/0.06435/0.04958. No empty masks in fixed probe;target mean16.1–16.5%;optimizer updates0.
- Artifacts: train/segmentation_auxiliary.py;vision/diagnose_segmentation_auxiliary.py;eval/segmentation_feasibility_v0_report.json;tests/test_segmentation_auxiliary.py.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Four fixed training batches at initialization only;not proof of optimization stability or better localization. Mask geometry is not perceptual/physical truth.
- Supersedes: none;prior failures and arm/integration status retained.
- Next dependency: Freeze paired original-image training with identical auxiliary-head architecture/control initialization and no mask gradient in control,coefficient0.001 candidate. Same pose loss/anchor,data,budget/selection and three seeds;score original cluttered development images and retain segmentation metrics separately. No runtime or qualification change. Publish only feature/translation-pair-evidence to j-webtek/tactevra.


### E-20260926-AI-243 — auxiliary label and head verification

- Stage: S1
- Lane: AI
- Commit: `45836f58301d7173c4e7b72fd213b13a796eb758` (frozen source;results/tests committed with evidence)
- Change: auxiliary label and head verification.
- Inputs/fixtures: training-only starts29000000/008/016/024,8groups x4conditions per batch,rectangle occlusion,CPU128x96. Initial checkpoint0fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d;seed260926,balanced mask BCE vs key loss,coefficient0.001 preregistered. Exact source hashes eval/segmentation_feasibility_v0_plan.json;pixel/target hashes in report.
- Command: `python -m pytest -q software/ai/tests/test_segmentation_auxiliary.py`
- Result: PASS,3 tests: exact area coverage/foreground subtraction,empty/full/soft-class finite loss gradients,unchanged initial pose,discardable head,source/checkpoint lineage and probe recount. Existing pytest-asyncio warning.
- Artifacts: train/segmentation_auxiliary.py;vision/diagnose_segmentation_auxiliary.py;eval/segmentation_feasibility_v0_report.json;tests/test_segmentation_auxiliary.py.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Implementation verification only;batch contract unchanged,shared boundary suite not triggered.
- Supersedes: none;prior failures and arm/integration status retained.
- Next dependency: Freeze paired original-image training with identical auxiliary-head architecture/control initialization and no mask gradient in control,coefficient0.001 candidate. Same pose loss/anchor,data,budget/selection and three seeds;score original cluttered development images and retain segmentation metrics separately. No runtime or qualification change. Publish only feature/translation-pair-evidence to j-webtek/tactevra.


### E-20260926-AI-244 — auxiliary feasibility publication audit

- Stage: S1
- Lane: AI
- Commit: `45836f58301d7173c4e7b72fd213b13a796eb758` (frozen source;results/tests committed with evidence)
- Change: auxiliary feasibility publication audit.
- Inputs/fixtures: training-only starts29000000/008/016/024,8groups x4conditions per batch,rectangle occlusion,CPU128x96. Initial checkpoint0fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d;seed260926,balanced mask BCE vs key loss,coefficient0.001 preregistered. Exact source hashes eval/segmentation_feasibility_v0_plan.json;pixel/target hashes in report.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS;6099paths,861.7MiB,0 unresolved findings,14 reviewed synthetic fixtures.
- Artifacts: train/segmentation_auxiliary.py;vision/diagnose_segmentation_auxiliary.py;eval/segmentation_feasibility_v0_report.json;tests/test_segmentation_auxiliary.py.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic audit;AI-041 protected-main publication blocker retained.
- Supersedes: none;prior failures and arm/integration status retained.
- Next dependency: Freeze paired original-image training with identical auxiliary-head architecture/control initialization and no mask gradient in control,coefficient0.001 candidate. Same pose loss/anchor,data,budget/selection and three seeds;score original cluttered development images and retain segmentation metrics separately. No runtime or qualification change. Publish only feature/translation-pair-evidence to j-webtek/tactevra.


### E-20260926-AI-245 — paired segmentation auxiliary training

- Stage: S1
- Lane: AI
- Commit: `96e489e3cd0818053820cc6b06adc05fecc20cb2` (frozen source;results/tests committed with evidence)
- Change: paired segmentation auxiliary training.
- Inputs/fixtures: original29000000..29000599 x4 training,original15M200 x4 development;4epochs,9600presentations,152updates,AdamW0.0001,batch64,key loss+anchor1 both,balanced mask BCE0.001 candidate;identical head initializations,seeds260926/27/28. Initial/teacher0fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d. Source hashes train/pose_segmentation_*_plan.json;inputs/masks/teacher/checkpoint hashes in reports.
- Command: `python software/ai/train/train_pose_segmentation.py`
- Result: Full rule FAIL3/3;baseline PASS3/3. Candidate and control tails identical22/23/24 vs baseline32each. Mask BCE candidate0.632876/0.679543/0.678997 vs control0.660642/0.700939/0.716994;candidate IoU0.661374/0.052425/0.166410. No localization gain established. Checkpoint SHA256: 260926/control pose=3cd918c5cde540f8d3baf20eea9a37bc7190b74d3bdad3b520c1d55cba04c5dc training=2ebfde77408fe7eda92e3483ad921101de64ade9f95e3b2854f44f670cf93359; 260926/occlusion pose=2049ba45d2626d58ef796814692f80fd8068a20ba2c5f512ef02bf441cfd628d training=f0b8bf712a7c233ee893f524b85b9957dcd7ae62483a7ac396950ed84d15c003; 260927/control pose=2a578175168e399302c230dfdf69d3f90ba6f10fbff54018a5ffc345536e3c52 training=9fb105add2ee225f564591b77a711870e4b9ba1adfb8cb55153798183d3a54bf; 260927/occlusion pose=b1a27a35586378c11ab42f1a45cecadcc31905266c515b96a88c4106012c6bbc training=18a106b5c4b8e2856c77499b07636886f11f9c100b1a15737836a7560875db1a; 260928/control pose=1c101a33a3894ea65509e2d2ee1945c9d1e55e9916d96b2ca8eb466029b85ca8 training=ffcdce58bb1ea210a1920db33ed7cd29a103e7c36af609ae2d4da62e04473e61; 260928/occlusion pose=2c24f13e3128dcaee12031f657cbc82a9f6ce8655133d4982f891fc9392625a5 training=45a5ff7aa3fe6a501c3d32be45532b49716de04ae866333fcbeb316e88fc9380
- Artifacts: train/train_pose_segmentation.py;vision/summarize_pose_segmentation.py;eval/pose_segmentation_*_report.json;tests/test_pose_segmentation.py;ignored local training/pose checkpoint pairs.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Reused development selects pose epoch;segmentation metrics descriptive. Random control heads remain untrained;IoU strongly initialization-dependent. No mask-based qualification or model promotion.
- Supersedes: none;prior failures and arm/integration status retained.
- Next dependency: Freeze a head-only visible-mask learning probe on frozen baseline features across all3 seeds;verify whether the33-parameter linear head can reliably learn the task before modifying shared features or sweeping auxiliary coefficients. Pose weights/predictions must remain identical;segmentation success alone grants no localization authority. Publish only feature/translation-pair-evidence to j-webtek/tactevra.


### E-20260926-AI-246 — segmentation auxiliary aggregation

- Stage: S1
- Lane: AI
- Commit: `96e489e3cd0818053820cc6b06adc05fecc20cb2` (frozen source;results/tests committed with evidence)
- Change: segmentation auxiliary aggregation.
- Inputs/fixtures: original29000000..29000599 x4 training,original15M200 x4 development;4epochs,9600presentations,152updates,AdamW0.0001,batch64,key loss+anchor1 both,balanced mask BCE0.001 candidate;identical head initializations,seeds260926/27/28. Initial/teacher0fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d. Source hashes train/pose_segmentation_*_plan.json;inputs/masks/teacher/checkpoint hashes in reports.
- Command: `python software/ai/vision/summarize_pose_segmentation.py`
- Result: All3seeds retained;candidate appearance mean0.809090mm vs control0.809980 and baseline0.833364;no tail improvement. Full passes0/3,baseline passes3/3.
- Artifacts: train/train_pose_segmentation.py;vision/summarize_pose_segmentation.py;eval/pose_segmentation_*_report.json;tests/test_pose_segmentation.py;ignored local training/pose checkpoint pairs.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Three optimization seeds,same evaluation cases;not independent data replication or statistical significance.
- Supersedes: none;prior failures and arm/integration status retained.
- Next dependency: Freeze a head-only visible-mask learning probe on frozen baseline features across all3 seeds;verify whether the33-parameter linear head can reliably learn the task before modifying shared features or sweeping auxiliary coefficients. Pose weights/predictions must remain identical;segmentation success alone grants no localization authority. Publish only feature/translation-pair-evidence to j-webtek/tactevra.


### E-20260926-AI-247 — segmentation training verification

- Stage: S1
- Lane: AI
- Commit: `96e489e3cd0818053820cc6b06adc05fecc20cb2` (frozen source;results/tests committed with evidence)
- Change: segmentation training verification.
- Inputs/fixtures: original29000000..29000599 x4 training,original15M200 x4 development;4epochs,9600presentations,152updates,AdamW0.0001,batch64,key loss+anchor1 both,balanced mask BCE0.001 candidate;identical head initializations,seeds260926/27/28. Initial/teacher0fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d. Source hashes train/pose_segmentation_*_plan.json;inputs/masks/teacher/checkpoint hashes in reports.
- Command: `python -m pytest -q software/ai/tests/test_pose_segmentation.py`
- Result: PASS,2 tests: identical initial/input/mask/teacher hashes,common budget/selection,original evaluation pixels,untrained control versus changed candidate head,exact backbone-only exports,checkpoint lineage and aggregate recount. Existing pytest-asyncio warning.
- Artifacts: train/train_pose_segmentation.py;vision/summarize_pose_segmentation.py;eval/pose_segmentation_*_report.json;tests/test_pose_segmentation.py;ignored local training/pose checkpoint pairs.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Local checkpoint byte checks passed;clean clones explicitly skip the local-head test if ignored checkpoints absent. Contract unchanged;shared boundary suite not triggered.
- Supersedes: none;prior failures and arm/integration status retained.
- Next dependency: Freeze a head-only visible-mask learning probe on frozen baseline features across all3 seeds;verify whether the33-parameter linear head can reliably learn the task before modifying shared features or sweeping auxiliary coefficients. Pose weights/predictions must remain identical;segmentation success alone grants no localization authority. Publish only feature/translation-pair-evidence to j-webtek/tactevra.


### E-20260926-AI-248 — segmentation training publication audit

- Stage: S1
- Lane: AI
- Commit: `96e489e3cd0818053820cc6b06adc05fecc20cb2` (frozen source;results/tests committed with evidence)
- Change: segmentation training publication audit.
- Inputs/fixtures: original29000000..29000599 x4 training,original15M200 x4 development;4epochs,9600presentations,152updates,AdamW0.0001,batch64,key loss+anchor1 both,balanced mask BCE0.001 candidate;identical head initializations,seeds260926/27/28. Initial/teacher0fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d. Source hashes train/pose_segmentation_*_plan.json;inputs/masks/teacher/checkpoint hashes in reports.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS;6109paths,864.8MiB,0 unresolved findings,14 reviewed synthetic fixtures.
- Artifacts: train/train_pose_segmentation.py;vision/summarize_pose_segmentation.py;eval/pose_segmentation_*_report.json;tests/test_pose_segmentation.py;ignored local training/pose checkpoint pairs.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic audit;AI-041 protected-main blocker retained.
- Supersedes: none;prior failures and arm/integration status retained.
- Next dependency: Freeze a head-only visible-mask learning probe on frozen baseline features across all3 seeds;verify whether the33-parameter linear head can reliably learn the task before modifying shared features or sweeping auxiliary coefficients. Pose weights/predictions must remain identical;segmentation success alone grants no localization authority. Publish only feature/translation-pair-evidence to j-webtek/tactevra.


### E-20260926-AI-249 — frozen-feature segmentation head learning

- Stage: S1
- Lane: AI
- Commit: `746f11bd41f1dec5b3486841bbe0d9e6be160ec8` (frozen execution source; results/tests committed with this evidence)
- Change: frozen-feature segmentation head learning.
- Inputs/fixtures: training seeds 29000000..29000599 x4 conditions (2400 images); development 15000000..15000199 x4 (800 images); optimization seeds 260926/260927/260928; frozen baseline SHA256 0fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d. Only 33 head parameters trained, eight fixed epochs, AdamW 0.001, batch64. Plan SHA256 f986fd27a6bb37746bb08b4819a3d1fd91fa6e7835e1e55b7923009700cbaaff; per-input, mask, backbone and head hashes retained in report.
- Command: `python software/ai/train/train_segmentation_head_probe.py`
- Result: PASS mask feasibility 3/3 seeds. Final mean IoU 0.907517/0.881770/0.900564; balanced BCE 0.357558/0.383092/0.381471. Each condition mean IoU >=0.8 and BCE decreased. 304 head updates per seed; zero pose updates; pose output maximum delta exactly 0 on all 800 development images. Backbone hashes unchanged.
- Artifacts: `eval/segmentation_head_probe_v0_report.json` SHA256 45a5f4bf73018ae48407c70f3f1e74ddf94e643662a91a5e6c4474773fdbe579; `train/segmentation_head_probe_v0_plan.json`; `train/train_segmentation_head_probe.py`; `tests/test_segmentation_head_probe.py`; ignored local per-seed head checkpoints.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Synthetic masks and reused development only; no localization improvement, calibrated uncertainty, model promotion, or runtime authority.
- Supersedes: none; earlier failed evidence and arm/integration statuses retained.
- Next dependency: Freeze paired joint training initialized with the corresponding trained head in both arms; retain previous joint-training budget, learning rate, pose loss, selection and auxiliary coefficient to isolate trained-head initialization. Evaluate localization against paired control and baseline; mask feasibility grants no coordinate qualification. Publish only feature/translation-pair-evidence.


### E-20260926-AI-250 — head probe verification

- Stage: S1
- Lane: AI
- Commit: `746f11bd41f1dec5b3486841bbe0d9e6be160ec8` (frozen execution source; results/tests committed with this evidence)
- Change: head probe verification.
- Inputs/fixtures: training seeds 29000000..29000599 x4 conditions (2400 images); development 15000000..15000199 x4 (800 images); optimization seeds 260926/260927/260928; frozen baseline SHA256 0fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d. Only 33 head parameters trained, eight fixed epochs, AdamW 0.001, batch64. Plan SHA256 f986fd27a6bb37746bb08b4819a3d1fd91fa6e7835e1e55b7923009700cbaaff; per-input, mask, backbone and head hashes retained in report.
- Command: `python -m pytest -q software/ai/tests/test_segmentation_head_probe.py`
- Result: PASS: 2 tests; known IoU, frozen lineage, fixed budget, mask/pixel hashes, condition criteria, pose invariance, and available checkpoint hashes verified. Existing pytest-asyncio warning.
- Artifacts: `eval/segmentation_head_probe_v0_report.json` SHA256 45a5f4bf73018ae48407c70f3f1e74ddf94e643662a91a5e6c4474773fdbe579; `train/segmentation_head_probe_v0_plan.json`; `train/train_segmentation_head_probe.py`; `tests/test_segmentation_head_probe.py`; ignored local per-seed head checkpoints.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Ignored local checkpoint bytes are checked when present; portable evidence retains hashes when absent. Batch contract unchanged; boundary suite not triggered.
- Supersedes: none; earlier failed evidence and arm/integration statuses retained.
- Next dependency: Freeze paired joint training initialized with the corresponding trained head in both arms; retain previous joint-training budget, learning rate, pose loss, selection and auxiliary coefficient to isolate trained-head initialization. Evaluate localization against paired control and baseline; mask feasibility grants no coordinate qualification. Publish only feature/translation-pair-evidence.


### E-20260926-AI-251 — head probe publication audit

- Stage: S1
- Lane: AI
- Commit: `746f11bd41f1dec5b3486841bbe0d9e6be160ec8` (frozen execution source; results/tests committed with this evidence)
- Change: head probe publication audit.
- Inputs/fixtures: training seeds 29000000..29000599 x4 conditions (2400 images); development 15000000..15000199 x4 (800 images); optimization seeds 260926/260927/260928; frozen baseline SHA256 0fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d. Only 33 head parameters trained, eight fixed epochs, AdamW 0.001, batch64. Plan SHA256 f986fd27a6bb37746bb08b4819a3d1fd91fa6e7835e1e55b7923009700cbaaff; per-input, mask, backbone and head hashes retained in report.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS: 6113 paths; 864.9 MiB; 0 unresolved review findings; 14 reviewed synthetic fixtures.
- Artifacts: `eval/segmentation_head_probe_v0_report.json` SHA256 45a5f4bf73018ae48407c70f3f1e74ddf94e643662a91a5e6c4474773fdbe579; `train/segmentation_head_probe_v0_plan.json`; `train/train_segmentation_head_probe.py`; `tests/test_segmentation_head_probe.py`; ignored local per-seed head checkpoints.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic snapshot audit; historical AI-041 blocker retained.
- Supersedes: none; earlier failed evidence and arm/integration statuses retained.
- Next dependency: Freeze paired joint training initialized with the corresponding trained head in both arms; retain previous joint-training budget, learning rate, pose loss, selection and auxiliary coefficient to isolate trained-head initialization. Evaluate localization against paired control and baseline; mask feasibility grants no coordinate qualification. Publish only feature/translation-pair-evidence.


### E-20260926-AI-252 — learned-head joint training

- Stage: S1
- Lane: AI
- Commit: `1ada8bacbdce064b9756153fafe67ff637d7263a` (frozen execution source; evidence and tests committed together)
- Change: learned-head joint training.
- Inputs/fixtures: Training 29000000..29000599 x4, development 15000000..15000199 x4; seeds260926/27/28; four joint epochs,9600 image presentations,152 updates per arm; same learned head per seed in both arms (additional304 head-only updates), AdamW0.0001,key loss+anchor1,candidate mask BCE0.001. Frozen source/input/checkpoint hashes in train/pose_warm_segmentation_*_plan.json; input/mask/teacher and output checkpoint hashes in per-seed reports.
- Command: `python software/ai/train/train_pose_warm_segmentation.py`
- Result: Full rule FAIL3/3; baseline rule PASS3/3. Candidate large-error totals21/23/24 versus paired control22/23/24 and baseline32each. Candidate mean mask IoU0.909181/0.888051/0.901049. No consistent localization benefit from trained heads.
- Artifacts: train/train_pose_warm_segmentation.py; vision/summarize_pose_warm_segmentation.py; eval/pose_warm_segmentation_*_report.json; tests/test_pose_warm_segmentation.py; ignored local training/pose checkpoints.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Synthetic reused development selects epoch; GPU nondeterminism; no physical calibration or localization qualification.
- Supersedes: none; failed evidence retained.
- Next dependency: Stop this auxiliary-loss series without a coefficient sweep or promotion. Perform a frozen inference-only case-overlap audit of warmed candidates versus controls and the previously identified19 persistent failures, including recovered and newly failed cases, to choose the next representation change from evidence. Reused development cannot qualify localization; fresh30M data remains unused. Arm and integration statuses unchanged.


### E-20260926-AI-253 — learned-head aggregation

- Stage: S1
- Lane: AI
- Commit: `1ada8bacbdce064b9756153fafe67ff637d7263a` (frozen execution source; evidence and tests committed together)
- Change: learned-head aggregation.
- Inputs/fixtures: Training 29000000..29000599 x4, development 15000000..15000199 x4; seeds260926/27/28; four joint epochs,9600 image presentations,152 updates per arm; same learned head per seed in both arms (additional304 head-only updates), AdamW0.0001,key loss+anchor1,candidate mask BCE0.001. Frozen source/input/checkpoint hashes in train/pose_warm_segmentation_*_plan.json; input/mask/teacher and output checkpoint hashes in per-seed reports.
- Command: `python software/ai/vision/summarize_pose_warm_segmentation.py`
- Result: Full passes0/3; baseline passes3/3. Appearance mean candidate0.809012mm versus paired control0.810255mm and baseline0.833364mm. All seeds retained.
- Artifacts: train/train_pose_warm_segmentation.py; vision/summarize_pose_warm_segmentation.py; eval/pose_warm_segmentation_*_report.json; tests/test_pose_warm_segmentation.py; ignored local training/pose checkpoints.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Same development scenes for all seeds; descriptive comparisons are not independent data replication.
- Supersedes: none; failed evidence retained.
- Next dependency: Stop this auxiliary-loss series without a coefficient sweep or promotion. Perform a frozen inference-only case-overlap audit of warmed candidates versus controls and the previously identified19 persistent failures, including recovered and newly failed cases, to choose the next representation change from evidence. Reused development cannot qualify localization; fresh30M data remains unused. Arm and integration statuses unchanged.


### E-20260926-AI-254 — preserved verification failure

- Stage: S1
- Lane: AI
- Commit: `1ada8bacbdce064b9756153fafe67ff637d7263a` (frozen execution source; evidence and tests committed together)
- Change: preserved verification failure.
- Inputs/fixtures: Training 29000000..29000599 x4, development 15000000..15000199 x4; seeds260926/27/28; four joint epochs,9600 image presentations,152 updates per arm; same learned head per seed in both arms (additional304 head-only updates), AdamW0.0001,key loss+anchor1,candidate mask BCE0.001. Frozen source/input/checkpoint hashes in train/pose_warm_segmentation_*_plan.json; input/mask/teacher and output checkpoint hashes in per-seed reports.
- Command: `python -m pytest -q software/ai/tests/test_pose_warm_segmentation.py`
- Result: FAIL:1 failed,1 passed in1.61s. Exact historical control score equality failed; example appearance0.8082424139008907 versus historical0.807518299335391mm. Failure source hash c2a8a5df031211beaf35bd6eeb6b77fea5a2517e7604c1a5785186a32722ca86. Structured failure retained in eval/pose_warm_segmentation_test_failure.json.
- Artifacts: train/train_pose_warm_segmentation.py; vision/summarize_pose_warm_segmentation.py; eval/pose_warm_segmentation_*_report.json; tests/test_pose_warm_segmentation.py; ignored local training/pose checkpoints.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Exact independent GPU training replay was an invalid test requirement; historical score drift is preserved, not rounded away.
- Supersedes: none; failed evidence retained.
- Next dependency: Stop this auxiliary-loss series without a coefficient sweep or promotion. Perform a frozen inference-only case-overlap audit of warmed candidates versus controls and the previously identified19 persistent failures, including recovered and newly failed cases, to choose the next representation change from evidence. Reused development cannot qualify localization; fresh30M data remains unused. Arm and integration statuses unchanged.


### E-20260926-AI-255 — corrected lineage verification

- Stage: S1
- Lane: AI
- Commit: `1ada8bacbdce064b9756153fafe67ff637d7263a` (frozen execution source; evidence and tests committed together)
- Change: corrected lineage verification.
- Inputs/fixtures: Training 29000000..29000599 x4, development 15000000..15000199 x4; seeds260926/27/28; four joint epochs,9600 image presentations,152 updates per arm; same learned head per seed in both arms (additional304 head-only updates), AdamW0.0001,key loss+anchor1,candidate mask BCE0.001. Frozen source/input/checkpoint hashes in train/pose_warm_segmentation_*_plan.json; input/mask/teacher and output checkpoint hashes in per-seed reports.
- Command: `python -m pytest -q software/ai/tests/test_pose_warm_segmentation.py`
- Result: PASS:2 tests in1.73s. Verify actual initial states equal baseline plus learned head; identical paired inputs, masks and teacher; unchanged hyperparameters; selected epoch; head training/control invariance; backbone-only export and aggregate hashes.
- Artifacts: train/train_pose_warm_segmentation.py; vision/summarize_pose_warm_segmentation.py; eval/pose_warm_segmentation_*_report.json; tests/test_pose_warm_segmentation.py; ignored local training/pose checkpoints.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Test correction only; experiment reports and acceptance rule unchanged. Existing pytest-asyncio warning. Local checkpoint verification requires local bytes; portable source/report checks retained. Contract unchanged; shared boundary suite not triggered.
- Supersedes: none; failed evidence retained.
- Next dependency: Stop this auxiliary-loss series without a coefficient sweep or promotion. Perform a frozen inference-only case-overlap audit of warmed candidates versus controls and the previously identified19 persistent failures, including recovered and newly failed cases, to choose the next representation change from evidence. Reused development cannot qualify localization; fresh30M data remains unused. Arm and integration statuses unchanged.


### E-20260926-AI-256 — publication snapshot audit

- Stage: S1
- Lane: AI
- Commit: `1ada8bacbdce064b9756153fafe67ff637d7263a` (frozen execution source; evidence and tests committed together)
- Change: publication snapshot audit.
- Inputs/fixtures: Training 29000000..29000599 x4, development 15000000..15000199 x4; seeds260926/27/28; four joint epochs,9600 image presentations,152 updates per arm; same learned head per seed in both arms (additional304 head-only updates), AdamW0.0001,key loss+anchor1,candidate mask BCE0.001. Frozen source/input/checkpoint hashes in train/pose_warm_segmentation_*_plan.json; input/mask/teacher and output checkpoint hashes in per-seed reports.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS:6123paths,868.0MiB,0unresolved findings,14reviewed synthetic fixtures.
- Artifacts: train/train_pose_warm_segmentation.py; vision/summarize_pose_warm_segmentation.py; eval/pose_warm_segmentation_*_report.json; tests/test_pose_warm_segmentation.py; ignored local training/pose checkpoints.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Audit ran before final ledger and failure-artifact additions; heuristic snapshot audit, not runtime assurance.
- Supersedes: none; failed evidence retained.
- Next dependency: Stop this auxiliary-loss series without a coefficient sweep or promotion. Perform a frozen inference-only case-overlap audit of warmed candidates versus controls and the previously identified19 persistent failures, including recovered and newly failed cases, to choose the next representation change from evidence. Reused development cannot qualify localization; fresh30M data remains unused. Arm and integration statuses unchanged.


### E-20260926-AI-257 — learned-head failure overlap

- Stage: S1
- Lane: AI
- Commit: `3d10598bdf2390c766536ecb7f52a32968301593` (frozen analysis source; results/tests/docs committed with evidence)
- Change: learned-head failure overlap.
- Inputs/fixtures: retained pose_warm_segmentation_260926/260927/260928 reports, each800 development scenes15000000..15000199 x4; prior persistent_pose_v0 report. Exact SHA256 of all inputs and source in eval/warm_segmentation_overlap_v0_plan.json. Output report SHA256 42b202d02765e5ff9709efa5046ae1dd56d3e09ea213e15dbe5eb03da4181bec.
- Command: `python software/ai/vision/audit_warm_segmentation_overlap.py`
- Result: 800 cases; recovered by seed1/0/0; introduced0/0/0; all19 prior persistent cases still fail all candidates;21 cases fail all six current models. Sole recovery scene15000159/appearance_shift/seed260926:3.033146102269828 to2.980807932140745mm. No recovery consistent across seeds.
- Artifacts: vision/audit_warm_segmentation_overlap.py; eval/warm_segmentation_overlap_v0_plan.json; eval/warm_segmentation_overlap_v0_report.json; tests/test_warm_segmentation_overlap.py; docs/POSE_REPRESENTATION_REVIEW.md.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Retained outputs only: zero new forward passes and optimizer updates. Same reused synthetic development; threshold crossings and GPU nondeterminism do not establish causality.
- Supersedes: none; prior failed evidence retained; arm/integration statuses unchanged.
- Next dependency: Freeze a learned-mask-conditioned residual pose readout feasibility design with parameter-matched constant-mask control, exact baseline initialization, no oracle inference inputs, and measured added cost. Verify representation before training; no auxiliary-coefficient sweep or promotion. Fresh30M remains unused. Publish only feature/translation-pair-evidence.


### E-20260926-AI-258 — overlap verification

- Stage: S1
- Lane: AI
- Commit: `3d10598bdf2390c766536ecb7f52a32968301593` (frozen analysis source; results/tests/docs committed with evidence)
- Change: overlap verification.
- Inputs/fixtures: retained pose_warm_segmentation_260926/260927/260928 reports, each800 development scenes15000000..15000199 x4; prior persistent_pose_v0 report. Exact SHA256 of all inputs and source in eval/warm_segmentation_overlap_v0_plan.json. Output report SHA256 42b202d02765e5ff9709efa5046ae1dd56d3e09ea213e15dbe5eb03da4181bec.
- Command: `python -m pytest -q software/ai/tests/test_warm_segmentation_overlap.py`
- Result: PASS:6 tests in0.08s; known recovery/introduction and strict3mm threshold, duplicate/missing/nonfinite/baseline mismatch rejection, frozen lineage and population recount.
- Artifacts: vision/audit_warm_segmentation_overlap.py; eval/warm_segmentation_overlap_v0_plan.json; eval/warm_segmentation_overlap_v0_report.json; tests/test_warm_segmentation_overlap.py; docs/POSE_REPRESENTATION_REVIEW.md.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Existing pytest-asyncio warning. Contract unchanged, so shared boundary suite not triggered.
- Supersedes: none; prior failed evidence retained; arm/integration statuses unchanged.
- Next dependency: Freeze a learned-mask-conditioned residual pose readout feasibility design with parameter-matched constant-mask control, exact baseline initialization, no oracle inference inputs, and measured added cost. Verify representation before training; no auxiliary-coefficient sweep or promotion. Fresh30M remains unused. Publish only feature/translation-pair-evidence.


### E-20260926-AI-259 — overlap publication audit

- Stage: S1
- Lane: AI
- Commit: `3d10598bdf2390c766536ecb7f52a32968301593` (frozen analysis source; results/tests/docs committed with evidence)
- Change: overlap publication audit.
- Inputs/fixtures: retained pose_warm_segmentation_260926/260927/260928 reports, each800 development scenes15000000..15000199 x4; prior persistent_pose_v0 report. Exact SHA256 of all inputs and source in eval/warm_segmentation_overlap_v0_plan.json. Output report SHA256 42b202d02765e5ff9709efa5046ae1dd56d3e09ea213e15dbe5eb03da4181bec.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS:6128paths,868.8MiB,0unresolved findings,14reviewed synthetic fixtures.
- Artifacts: vision/audit_warm_segmentation_overlap.py; eval/warm_segmentation_overlap_v0_plan.json; eval/warm_segmentation_overlap_v0_report.json; tests/test_warm_segmentation_overlap.py; docs/POSE_REPRESENTATION_REVIEW.md.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic audit before final documentation append; not runtime qualification.
- Supersedes: none; prior failed evidence retained; arm/integration statuses unchanged.
- Next dependency: Freeze a learned-mask-conditioned residual pose readout feasibility design with parameter-matched constant-mask control, exact baseline initialization, no oracle inference inputs, and measured added cost. Verify representation before training; no auxiliary-coefficient sweep or promotion. Fresh30M remains unused. Publish only feature/translation-pair-evidence.


### E-20260926-AI-260 — offline baseline demonstration

- Stage: S1
- Lane: AI
- Commit: `1eb001f5dbcb72c8d956a49fbea8db712187494b` (frozen demonstration source; output/tests/docs committed together)
- Change: offline baseline demonstration.
- Inputs/fixtures: six frozen requests in eval/local_baseline_demo_v0_plan.json; scenes15000000/standard,15000027/appearance_shift,15000068/full; baseline checkpoint SHA256 0fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d. Exact source hashes in plan, image/catalog hashes in report. report.json SHA256 27136e43dcb6c764d55b830ec8f8095264c29b733005b01dd28cd53814f7d1e0; index.html SHA256 fa8e34fd9c52034f8e9aa5bee8f7dc99eacc8b088881fa34736a416f31a71344.
- Command: `python software/ai/rocell_ai/local_baseline_demo.py`
- Result: Six illustrative cases generated using actual CPU pose inference and grounded parser. Three semantic plans accepted; missing evidence blocks clear/lighting motion, explicit fixture obstruction abstains. Stale, ambiguous and call requests blocked. Max requested-key errors0.761534/4.100415/4.686925mm. All motion batches null; no assembly, IK or execution.
- Artifacts: rocell_ai/local_baseline_demo.py; rocell_ai/local_baseline_demo.html; eval/local_baseline_demo_v0/index.html and report.json; tests/test_local_baseline_demo.py; docs/LOCAL_BASELINE_DEMO.md.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Selected reused synthetic cases, not a benchmark. No LLM/live camera. Obstruction/freshness are fixture declarations; simulator truth scores only. Local ignored checkpoint required for regeneration; committed standalone HTML works without it.
- Supersedes: none; prior model failures and arm/integration status retained. User requested this baseline demonstration before additional training.
- Next dependency: Use the demo as the current baseline; next research remains a predicted-mask-conditioned residual pose prototype with matched control and baseline-preserving initialization. No training resumed in this increment.


### E-20260926-AI-261 — baseline demonstration verification

- Stage: S1
- Lane: AI
- Commit: `1eb001f5dbcb72c8d956a49fbea8db712187494b` (frozen demonstration source; output/tests/docs committed together)
- Change: baseline demonstration verification.
- Inputs/fixtures: six frozen requests in eval/local_baseline_demo_v0_plan.json; scenes15000000/standard,15000027/appearance_shift,15000068/full; baseline checkpoint SHA256 0fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d. Exact source hashes in plan, image/catalog hashes in report. report.json SHA256 27136e43dcb6c764d55b830ec8f8095264c29b733005b01dd28cd53814f7d1e0; index.html SHA256 fa8e34fd9c52034f8e9aa5bee8f7dc99eacc8b088881fa34736a416f31a71344.
- Command: `python -m pytest -q software/ai/tests/test_local_baseline_demo.py`
- Result: PASS:4 tests in2.05s; exact repeated-key order, stale/unsupported decisions, JSON script escaping, image/plan/source hashes, coordinate error recount and shared runner stopping before assembly.
- Artifacts: rocell_ai/local_baseline_demo.py; rocell_ai/local_baseline_demo.html; eval/local_baseline_demo_v0/index.html and report.json; tests/test_local_baseline_demo.py; docs/LOCAL_BASELINE_DEMO.md.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Existing pytest-asyncio warning. No contract change; shared boundary suite not triggered. The null-input path deliberately cannot claim batch admission.
- Supersedes: none; prior model failures and arm/integration status retained. User requested this baseline demonstration before additional training.
- Next dependency: Use the demo as the current baseline; next research remains a predicted-mask-conditioned residual pose prototype with matched control and baseline-preserving initialization. No training resumed in this increment.


### E-20260926-AI-262 — browser review

- Stage: S1
- Lane: AI
- Commit: `1eb001f5dbcb72c8d956a49fbea8db712187494b` (frozen demonstration source; output/tests/docs committed together)
- Change: browser review.
- Inputs/fixtures: six frozen requests in eval/local_baseline_demo_v0_plan.json; scenes15000000/standard,15000027/appearance_shift,15000068/full; baseline checkpoint SHA256 0fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d. Exact source hashes in plan, image/catalog hashes in report. report.json SHA256 27136e43dcb6c764d55b830ec8f8095264c29b733005b01dd28cd53814f7d1e0; index.html SHA256 fa8e34fd9c52034f8e9aa5bee8f7dc99eacc8b088881fa34736a416f31a71344.
- Command: `python -m http.server 8765 --bind 127.0.0.1 --directory software/ai/eval/local_baseline_demo_v0; browser UI: createBrowserTab(iab,http://127.0.0.1:8765), setValue(case,Lighting variation), click(truth), setValue(case,Arm obstruction), restore Clear keyboard/truth`
- Result: PASS manual UI verification: page rendered; selection updates text plan, coordinate rows and error; truth checkbox hides truth cells; obstruction shows PERCEPTION_ABSTAIN_OBSTRUCTED. Clear case restored and tab left open.
- Artifacts: rocell_ai/local_baseline_demo.py; rocell_ai/local_baseline_demo.html; eval/local_baseline_demo_v0/index.html and report.json; tests/test_local_baseline_demo.py; docs/LOCAL_BASELINE_DEMO.md.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Browser inspection of generated standalone artifact; no automated cross-browser coverage. Loopback server serves only demo directory and is temporary; HTML also opens directly offline.
- Supersedes: none; prior model failures and arm/integration status retained. User requested this baseline demonstration before additional training.
- Next dependency: Use the demo as the current baseline; next research remains a predicted-mask-conditioned residual pose prototype with matched control and baseline-preserving initialization. No training resumed in this increment.


### E-20260926-AI-263 — baseline demonstration snapshot audit

- Stage: S1
- Lane: AI
- Commit: `1eb001f5dbcb72c8d956a49fbea8db712187494b` (frozen demonstration source; output/tests/docs committed together)
- Change: baseline demonstration snapshot audit.
- Inputs/fixtures: six frozen requests in eval/local_baseline_demo_v0_plan.json; scenes15000000/standard,15000027/appearance_shift,15000068/full; baseline checkpoint SHA256 0fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d. Exact source hashes in plan, image/catalog hashes in report. report.json SHA256 27136e43dcb6c764d55b830ec8f8095264c29b733005b01dd28cd53814f7d1e0; index.html SHA256 fa8e34fd9c52034f8e9aa5bee8f7dc99eacc8b088881fa34736a416f31a71344.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS:6135paths,868.9MiB,0 unresolved findings,14 reviewed synthetic fixtures.
- Artifacts: rocell_ai/local_baseline_demo.py; rocell_ai/local_baseline_demo.html; eval/local_baseline_demo_v0/index.html and report.json; tests/test_local_baseline_demo.py; docs/LOCAL_BASELINE_DEMO.md.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic audit before final ledger append; not qualification.
- Supersedes: none; prior model failures and arm/integration status retained. User requested this baseline demonstration before additional training.
- Next dependency: Use the demo as the current baseline; next research remains a predicted-mask-conditioned residual pose prototype with matched control and baseline-preserving initialization. No training resumed in this increment.


### E-20260926-AI-264 — mask-conditioned residual feasibility

- Stage: S1
- Lane: AI
- Commit: `c74b06648dc874d7a1c322bba2ce3e8b6453f52f` (frozen probe source; evidence/tests committed together)
- Change: mask-conditioned residual feasibility.
- Inputs/fixtures: training scenes29000000..29000007 x4conditions; learned heads260926/260927/260928; frozen baseline SHA256 0fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d. Exact source/head hashes in eval/mask_conditioned_probe_v0_plan.json; pixel SHA25600172608af702804ea6bdccbf37ddb6165e1d9a6b5a2bd30af58f4b0a6998fb0; output SHA256 ec2625fef214a878dfe032bb6eec8845e3a76809becc361a4ad5ed853e51332a.
- Command: `python software/ai/vision/probe_mask_conditioned_pose.py`
- Result: PASS:32images x3heads x2modes; initial pose delta0, exact initial/nonzero export roundtrips, finite residual gradients and no backbone/head gradients. Both293415parameters,16515trainable,1179040serialized bytes. Predicted-mask CPU medians0.7805/0.7716/0.7668ms versus baseline0.55255ms; batch1,fourthreads,10warmups,100iterations.
- Artifacts: vision/mask_conditioned_pose.py; vision/probe_mask_conditioned_pose.py; eval/mask_conditioned_probe_v0_plan.json and report.json; tests/test_mask_conditioned_pose.py; docs/POSE_REPRESENTATION_REVIEW.md.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Manual nonzero residual assignment and backward passes test wiring only; zero optimizer updates. CPU timing is host-specific and sequential. No accuracy improvement or physical qualification. Inherited head pretraining304updates per seed; no new data/holdout.
- Supersedes: none; all failed prior evidence and arm/integration statuses retained.
- Next dependency: Freeze paired three-seed residual-only training with predicted-mask versus constant-mask input, same baseline/features/head/image order/budget/selection, and unchanged baseline/control acceptance criteria. No runtime model promotion or mask confidence qualification.


### E-20260926-AI-265 — residual architecture verification

- Stage: S1
- Lane: AI
- Commit: `c74b06648dc874d7a1c322bba2ce3e8b6453f52f` (frozen probe source; evidence/tests committed together)
- Change: residual architecture verification.
- Inputs/fixtures: training scenes29000000..29000007 x4conditions; learned heads260926/260927/260928; frozen baseline SHA256 0fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d. Exact source/head hashes in eval/mask_conditioned_probe_v0_plan.json; pixel SHA25600172608af702804ea6bdccbf37ddb6165e1d9a6b5a2bd30af58f4b0a6998fb0; output SHA256 ec2625fef214a878dfe032bb6eec8845e3a76809becc361a4ad5ed853e51332a.
- Command: `python -m pytest -q software/ai/tests/test_mask_conditioned_pose.py`
- Result: PASS:8 tests in1.61s; image-only signature and size, spatial mask sensitivity, exact baseline/nonzero export, frozen gradients, malformed artifacts and frozen evidence lineage.
- Artifacts: vision/mask_conditioned_pose.py; vision/probe_mask_conditioned_pose.py; eval/mask_conditioned_probe_v0_plan.json and report.json; tests/test_mask_conditioned_pose.py; docs/POSE_REPRESENTATION_REVIEW.md.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Existing pytest-asyncio warning; local source/report checks support ignored checkpoint absence. Batch contract unchanged; shared boundary suite not triggered. Inherited head pretraining304updates per seed; no new data/holdout.
- Supersedes: none; all failed prior evidence and arm/integration statuses retained.
- Next dependency: Freeze paired three-seed residual-only training with predicted-mask versus constant-mask input, same baseline/features/head/image order/budget/selection, and unchanged baseline/control acceptance criteria. No runtime model promotion or mask confidence qualification.


### E-20260926-AI-266 — residual prototype snapshot audit

- Stage: S1
- Lane: AI
- Commit: `c74b06648dc874d7a1c322bba2ce3e8b6453f52f` (frozen probe source; evidence/tests committed together)
- Change: residual prototype snapshot audit.
- Inputs/fixtures: training scenes29000000..29000007 x4conditions; learned heads260926/260927/260928; frozen baseline SHA256 0fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d. Exact source/head hashes in eval/mask_conditioned_probe_v0_plan.json; pixel SHA25600172608af702804ea6bdccbf37ddb6165e1d9a6b5a2bd30af58f4b0a6998fb0; output SHA256 ec2625fef214a878dfe032bb6eec8845e3a76809becc361a4ad5ed853e51332a.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS:6140paths,868.9MiB,0unresolved findings,14reviewed synthetic fixtures.
- Artifacts: vision/mask_conditioned_pose.py; vision/probe_mask_conditioned_pose.py; eval/mask_conditioned_probe_v0_plan.json and report.json; tests/test_mask_conditioned_pose.py; docs/POSE_REPRESENTATION_REVIEW.md.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic audit before final documentation append; not runtime assurance. Inherited head pretraining304updates per seed; no new data/holdout.
- Supersedes: none; all failed prior evidence and arm/integration statuses retained.
- Next dependency: Freeze paired three-seed residual-only training with predicted-mask versus constant-mask input, same baseline/features/head/image order/budget/selection, and unchanged baseline/control acceptance criteria. No runtime model promotion or mask confidence qualification.


### E-20260926-AI-267 — paired residual-only training

- Stage: S1
- Lane: AI
- Commit: `82b6b7e0c2f8207dfe37f97f1d4ab957246f8cae` (frozen execution source; results/tests/docs committed together)
- Change: paired residual-only training.
- Inputs/fixtures: scenes29000000..29000599 x4 training;15000000..15000199 x4 development; seeds260926/260927/260928. Fixed8epochs,AdamW0.001,key loss+anchor1;16515 residual parameters only. Baseline SHA256 0fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d. Exact source/head hashes in train/pose_mask_residual_*_plan.json; input/frozen-state/teacher/checkpoint hashes in eval/pose_mask_residual_*_report.json; aggregate binds all report hashes.
- Command: `python software/ai/train/train_pose_mask_residual.py`
- Result: Full rule FAIL3/3; baseline-only PASS2/3. Candidate/control tails both31/32/31 versus baseline32each. Frozen pose and mask states unchanged; initial pose delta0;304 residual updates and19200 image presentations per arm.
- Artifacts: train/train_pose_mask_residual.py; vision/summarize_pose_mask_residual.py; eval/pose_mask_residual_*_report.json; tests/test_pose_mask_residual.py; ignored local results/pose_mask_residual_*/model.pt.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Reused development selects epoch; GPU nondeterminism; no calibration or qualification. Inherited head pretraining304updates per seed is additional shared cost. Frozen-feature residual study is not a full-backbone comparison.
- Supersedes: none; failed evidence retained; arm/integration statuses unchanged.
- Next dependency: Freeze an inference-only correction diagnostic on existing training/development: correction magnitude and per-axis variability/alignment versus true residual, with a training-only mean-offset comparator. No development-fit offset, runtime correction, architecture expansion or sweep. Keep demo baseline and fresh30M data unchanged.


### E-20260926-AI-268 — residual study aggregation

- Stage: S1
- Lane: AI
- Commit: `82b6b7e0c2f8207dfe37f97f1d4ab957246f8cae` (frozen execution source; results/tests/docs committed together)
- Change: residual study aggregation.
- Inputs/fixtures: scenes29000000..29000599 x4 training;15000000..15000199 x4 development; seeds260926/260927/260928. Fixed8epochs,AdamW0.001,key loss+anchor1;16515 residual parameters only. Baseline SHA256 0fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d. Exact source/head hashes in train/pose_mask_residual_*_plan.json; input/frozen-state/teacher/checkpoint hashes in eval/pose_mask_residual_*_report.json; aggregate binds all report hashes.
- Command: `python software/ai/vision/summarize_pose_mask_residual.py`
- Result: All3seeds retained; candidate appearance mean0.8357533143736205mm versus control0.8337978144490462 and baseline0.8333639909177747. Full passes0/3,baseline passes2/3.
- Artifacts: train/train_pose_mask_residual.py; vision/summarize_pose_mask_residual.py; eval/pose_mask_residual_*_report.json; tests/test_pose_mask_residual.py; ignored local results/pose_mask_residual_*/model.pt.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Same development cases across optimization seeds; descriptive aggregation, not independent dataset replication.
- Supersedes: none; failed evidence retained; arm/integration statuses unchanged.
- Next dependency: Freeze an inference-only correction diagnostic on existing training/development: correction magnitude and per-axis variability/alignment versus true residual, with a training-only mean-offset comparator. No development-fit offset, runtime correction, architecture expansion or sweep. Keep demo baseline and fresh30M data unchanged.


### E-20260926-AI-269 — residual training verification

- Stage: S1
- Lane: AI
- Commit: `82b6b7e0c2f8207dfe37f97f1d4ab957246f8cae` (frozen execution source; results/tests/docs committed together)
- Change: residual training verification.
- Inputs/fixtures: scenes29000000..29000599 x4 training;15000000..15000199 x4 development; seeds260926/260927/260928. Fixed8epochs,AdamW0.001,key loss+anchor1;16515 residual parameters only. Baseline SHA256 0fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d. Exact source/head hashes in train/pose_mask_residual_*_plan.json; input/frozen-state/teacher/checkpoint hashes in eval/pose_mask_residual_*_report.json; aggregate binds all report hashes.
- Command: `python -m pytest -q software/ai/tests/test_pose_mask_residual.py`
- Result: PASS:2 tests in1.69s. Paired initialization/input/teacher hashes, unchanged frozen sources, residual weight changes, mode-preserving exports, fixed budget, epoch selection and full acceptance recount.
- Artifacts: train/train_pose_mask_residual.py; vision/summarize_pose_mask_residual.py; eval/pose_mask_residual_*_report.json; tests/test_pose_mask_residual.py; ignored local results/pose_mask_residual_*/model.pt.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Ignored checkpoint bytes checked locally when available; portable frozen-artifact checks retained. Existing pytest-asyncio warning. Contract unchanged; shared boundary suite not triggered.
- Supersedes: none; failed evidence retained; arm/integration statuses unchanged.
- Next dependency: Freeze an inference-only correction diagnostic on existing training/development: correction magnitude and per-axis variability/alignment versus true residual, with a training-only mean-offset comparator. No development-fit offset, runtime correction, architecture expansion or sweep. Keep demo baseline and fresh30M data unchanged.


### E-20260926-AI-270 — residual study publication audit

- Stage: S1
- Lane: AI
- Commit: `82b6b7e0c2f8207dfe37f97f1d4ab957246f8cae` (frozen execution source; results/tests/docs committed together)
- Change: residual study publication audit.
- Inputs/fixtures: scenes29000000..29000599 x4 training;15000000..15000199 x4 development; seeds260926/260927/260928. Fixed8epochs,AdamW0.001,key loss+anchor1;16515 residual parameters only. Baseline SHA256 0fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d. Exact source/head hashes in train/pose_mask_residual_*_plan.json; input/frozen-state/teacher/checkpoint hashes in eval/pose_mask_residual_*_report.json; aggregate binds all report hashes.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS:6150paths,872.0MiB,0 unresolved findings,14 reviewed synthetic fixtures.
- Artifacts: train/train_pose_mask_residual.py; vision/summarize_pose_mask_residual.py; eval/pose_mask_residual_*_report.json; tests/test_pose_mask_residual.py; ignored local results/pose_mask_residual_*/model.pt.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic snapshot audit before final documentation append; not runtime assurance.
- Supersedes: none; failed evidence retained; arm/integration statuses unchanged.
- Next dependency: Freeze an inference-only correction diagnostic on existing training/development: correction magnitude and per-axis variability/alignment versus true residual, with a training-only mean-offset comparator. No development-fit offset, runtime correction, architecture expansion or sweep. Keep demo baseline and fresh30M data unchanged.


### E-20260926-AI-271 — residual correction diagnosis

- Stage: S1
- Lane: AI
- Commit: `f6ce7a0c0d65e537b68cbf1063358dc497dd37b4` (frozen diagnostic source; results/tests/docs committed together)
- Change: residual correction diagnosis.
- Inputs/fixtures: scenes29000000..29000599 x4training,15000000..15000199 x4development; all6 residual checkpoints from seeds260926/27/28 and both modes. Exact checkpoint/source hashes in eval/residual_corrections_v0_plan.json; input/prediction hashes and metrics in report SHA256 37cc54d53016462bad59f7562d45c01c35ecd9fc1e8a0f3f5ae541642cf76785. Baseline SHA2560fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d.
- Command: `python software/ai/vision/diagnose_residual_corrections.py`
- Result: All6checkpoints evaluated. Seed260927 both modes near-constant: development X/Y std<4.5e-7mm,yaw<1.7e-7deg. Other predicted-mask seeds std X0.0111..0.0314mm,Y0.0687..0.0716mm,yaw0.0055..0.0073deg against needed0.9050mm/0.6286mm/0.3528deg. Training-only offset gives33development tails versus32baseline.
- Artifacts: vision/diagnose_residual_corrections.py; eval/residual_corrections_v0_plan.json and report.json; tests/test_residual_corrections.py; docs/POSE_REPRESENTATION_REVIEW.md.
- Hardware writes: 0
- Physical movements: 0
- Limitations: CPU inference on GPU-trained checkpoints; no bitwise historical assertion. Near-zero-variance correlations are not meaningful learning evidence. Offset uses unweighted pose MSE, not anchored key loss. No causal activation diagnosis yet. Zero optimizer updates; reused synthetic data; no runtime correction/qualification installed.
- Supersedes: none; prior failures and arm/integration statuses retained.
- Next dependency: Freeze hidden-activation and output-bias diagnostic across all six checkpoints, comparing initial/trained activations on existing training inputs. Test the unit-collapse hypothesis before selecting activation/normalization changes. No new holdout or training sweep.


### E-20260926-AI-272 — correction diagnostic verification

- Stage: S1
- Lane: AI
- Commit: `f6ce7a0c0d65e537b68cbf1063358dc497dd37b4` (frozen diagnostic source; results/tests/docs committed together)
- Change: correction diagnostic verification.
- Inputs/fixtures: scenes29000000..29000599 x4training,15000000..15000199 x4development; all6 residual checkpoints from seeds260926/27/28 and both modes. Exact checkpoint/source hashes in eval/residual_corrections_v0_plan.json; input/prediction hashes and metrics in report SHA256 37cc54d53016462bad59f7562d45c01c35ecd9fc1e8a0f3f5ae541642cf76785. Baseline SHA2560fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d.
- Command: `python -m pytest -q software/ai/tests/test_residual_corrections.py`
- Result: PASS:6tests in1.63s. Known variable/constant corrections, training-only offset counterexample, invalid-array rejection, physical-unit scales, source/input hashes and MSE decomposition identities.
- Artifacts: vision/diagnose_residual_corrections.py; eval/residual_corrections_v0_plan.json and report.json; tests/test_residual_corrections.py; docs/POSE_REPRESENTATION_REVIEW.md.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Existing pytest-asyncio warning. Contract unchanged; shared boundary suite not triggered. Source verification permits absent ignored checkpoint bytes but checks them when available. Zero optimizer updates; reused synthetic data; no runtime correction/qualification installed.
- Supersedes: none; prior failures and arm/integration statuses retained.
- Next dependency: Freeze hidden-activation and output-bias diagnostic across all six checkpoints, comparing initial/trained activations on existing training inputs. Test the unit-collapse hypothesis before selecting activation/normalization changes. No new holdout or training sweep.


### E-20260926-AI-273 — correction diagnostic snapshot audit

- Stage: S1
- Lane: AI
- Commit: `f6ce7a0c0d65e537b68cbf1063358dc497dd37b4` (frozen diagnostic source; results/tests/docs committed together)
- Change: correction diagnostic snapshot audit.
- Inputs/fixtures: scenes29000000..29000599 x4training,15000000..15000199 x4development; all6 residual checkpoints from seeds260926/27/28 and both modes. Exact checkpoint/source hashes in eval/residual_corrections_v0_plan.json; input/prediction hashes and metrics in report SHA256 37cc54d53016462bad59f7562d45c01c35ecd9fc1e8a0f3f5ae541642cf76785. Baseline SHA2560fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS:6154paths,872.1MiB,0unresolved findings,14reviewed synthetic fixtures.
- Artifacts: vision/diagnose_residual_corrections.py; eval/residual_corrections_v0_plan.json and report.json; tests/test_residual_corrections.py; docs/POSE_REPRESENTATION_REVIEW.md.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic audit before final documentation append; not runtime assurance. Zero optimizer updates; reused synthetic data; no runtime correction/qualification installed.
- Supersedes: none; prior failures and arm/integration statuses retained.
- Next dependency: Freeze hidden-activation and output-bias diagnostic across all six checkpoints, comparing initial/trained activations on existing training inputs. Test the unit-collapse hypothesis before selecting activation/normalization changes. No new holdout or training sweep.


### E-20260926-AI-274 — residual activation and bias audit

- Stage: S1
- Lane: AI
- Commit: `6aaaae60938dab01333586e7fbc82c1c3e199f25` (frozen audit source; results/tests/docs committed together)
- Change: residual activation and bias audit.
- Inputs/fixtures: scenes29000000..29000599 x4conditions (2400 training images), all6 residual checkpoints and reconstructed initial states for seeds260926/27/28. Source/checkpoint hashes in eval/residual_activations_v0_plan.json; initial-state, pixel, activation and feature-output hashes in report SHA256 6ca00bc22268dd72a6ac4f3157690fd278b8eb1ac4030d72add33a2230f1760a.
- Command: `python software/ai/vision/diagnose_residual_activations.py`
- Result: Inactive units initial→trained:260926constant10→31,predicted12→31;260927constant10→32,predicted8→32;260928constant16→30,predicted18→31. Seed260927 both modes have exactly zero hidden activations and feature-dependent output on all2400 images: correction equals final bias. Exact component reconstruction and initial-state lineage verified.
- Artifacts: vision/diagnose_residual_activations.py; eval/residual_activations_v0_plan.json and report.json; tests/test_residual_activations.py; docs/POSE_REPRESENTATION_REVIEW.md.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Inactive is defined only over sampled training images. Initial/final snapshots do not show the optimizer trajectory or cause. No accuracy or runtime qualification established. Zero optimizer updates; no new data or holdout.
- Supersedes: none; failed evidence and arm/integration status retained.
- Next dependency: Freeze residual LeakyReLU0.01-only variant with versioned research export, exact initial baseline parity and negative-side gradient tests; then same-budget three-seed paired learning and variation check. No slope sweep, runtime qualification or other simultaneous architecture change.


### E-20260926-AI-275 — activation audit verification

- Stage: S1
- Lane: AI
- Commit: `6aaaae60938dab01333586e7fbc82c1c3e199f25` (frozen audit source; results/tests/docs committed together)
- Change: activation audit verification.
- Inputs/fixtures: scenes29000000..29000599 x4conditions (2400 training images), all6 residual checkpoints and reconstructed initial states for seeds260926/27/28. Source/checkpoint hashes in eval/residual_activations_v0_plan.json; initial-state, pixel, activation and feature-output hashes in report SHA256 6ca00bc22268dd72a6ac4f3157690fd278b8eb1ac4030d72add33a2230f1760a.
- Command: `python -m pytest -q software/ai/tests/test_residual_activations.py`
- Result: PASS:5tests in1.62s; known inactive/active units, exact bias-only case, invalid-array rejection, frozen hashes, training pixel identity and population/count recount.
- Artifacts: vision/diagnose_residual_activations.py; eval/residual_activations_v0_plan.json and report.json; tests/test_residual_activations.py; docs/POSE_REPRESENTATION_REVIEW.md.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Existing pytest-asyncio warning. Contract unchanged; shared boundary suite not triggered. Missing ignored checkpoint bytes permitted by portable verifier; present bytes verified. Zero optimizer updates; no new data or holdout.
- Supersedes: none; failed evidence and arm/integration status retained.
- Next dependency: Freeze residual LeakyReLU0.01-only variant with versioned research export, exact initial baseline parity and negative-side gradient tests; then same-budget three-seed paired learning and variation check. No slope sweep, runtime qualification or other simultaneous architecture change.


### E-20260926-AI-276 — activation audit snapshot

- Stage: S1
- Lane: AI
- Commit: `6aaaae60938dab01333586e7fbc82c1c3e199f25` (frozen audit source; results/tests/docs committed together)
- Change: activation audit snapshot.
- Inputs/fixtures: scenes29000000..29000599 x4conditions (2400 training images), all6 residual checkpoints and reconstructed initial states for seeds260926/27/28. Source/checkpoint hashes in eval/residual_activations_v0_plan.json; initial-state, pixel, activation and feature-output hashes in report SHA256 6ca00bc22268dd72a6ac4f3157690fd278b8eb1ac4030d72add33a2230f1760a.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS:6158paths,872.2MiB,0unresolved findings,14reviewed synthetic fixtures.
- Artifacts: vision/diagnose_residual_activations.py; eval/residual_activations_v0_plan.json and report.json; tests/test_residual_activations.py; docs/POSE_REPRESENTATION_REVIEW.md.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic audit before final docs append; not runtime assurance. Zero optimizer updates; no new data or holdout.
- Supersedes: none; failed evidence and arm/integration status retained.
- Next dependency: Freeze residual LeakyReLU0.01-only variant with versioned research export, exact initial baseline parity and negative-side gradient tests; then same-budget three-seed paired learning and variation check. No slope sweep, runtime qualification or other simultaneous architecture change.


### E-20260926-AI-277 — fixed leaky activation verification

- Stage: S1
- Lane: AI
- Commit: `e99d19ad39df7ba451a962ad285540d41399a0fa` (frozen execution source; results/tests/docs committed together)
- Change: fixed leaky activation verification.
- Inputs/fixtures: scenes29000000..29000599 x4training,15000000..15000199 x4development; seeds260926/27/28; same initial weights,8epochs,19200presentations,304updates,AdamW0.001,key loss+anchor1 as ReLU comparison. Only hidden activation changed to fixed LeakyReLU0.01. Exact source/head hashes in train/pose_leaky_residual_*_plan.json; input/frozen/teacher/checkpoint hashes in reports; aggregate binds all reports.
- Command: `python -m pytest -q software/ai/tests/test_mask_conditioned_leaky_pose.py`
- Result: PASS:2tests in1.63s before training; identical initial weights and baseline predictions; negative-side gradient0.01; exact nonzero export roundtrip; legacy/wrong-slope artifacts rejected.
- Artifacts: vision/mask_conditioned_leaky_pose.py; train/train_pose_leaky_residual.py; eval/pose_leaky_residual_*_report.json; vision/summarize_pose_leaky_residual.py; tests/test_mask_conditioned_leaky_pose.py; tests/test_pose_leaky_residual.py; ignored local model.pt checkpoints.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Research artifact version only; no shared motion contract changed. Existing pytest-asyncio warning. No localization qualification or runtime model update.
- Supersedes: none; ReLU failures and all arm/integration statuses retained.
- Next dependency: Freeze one training-only regularized linear-readout diagnostic on fixed pooled descriptors, with training-only normalization and matched mask/control representations; report training fit/conditioning and reused-development errors without tuning regularization on development. No activation sweep or new holdout.


### E-20260926-AI-278 — paired leaky residual training

- Stage: S1
- Lane: AI
- Commit: `e99d19ad39df7ba451a962ad285540d41399a0fa` (frozen execution source; results/tests/docs committed together)
- Change: paired leaky residual training.
- Inputs/fixtures: scenes29000000..29000599 x4training,15000000..15000199 x4development; seeds260926/27/28; same initial weights,8epochs,19200presentations,304updates,AdamW0.001,key loss+anchor1 as ReLU comparison. Only hidden activation changed to fixed LeakyReLU0.01. Exact source/head hashes in train/pose_leaky_residual_*_plan.json; input/frozen/teacher/checkpoint hashes in reports; aggregate binds all reports.
- Command: `python software/ai/train/train_pose_leaky_residual.py`
- Result: Full rule FAIL3/3; baseline PASS2/3. Candidate tails31/31/32 versus control32/31/32 and baseline32each. All6models have0all-hidden-zero images and nonzero residual std on all axes in both splits; frozen sources unchanged.
- Artifacts: vision/mask_conditioned_leaky_pose.py; train/train_pose_leaky_residual.py; eval/pose_leaky_residual_*_report.json; vision/summarize_pose_leaky_residual.py; tests/test_mask_conditioned_leaky_pose.py; tests/test_pose_leaky_residual.py; ignored local model.pt checkpoints.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Reused synthetic development selects epoch; GPU nondeterminism; removing zero hidden vectors does not establish useful accuracy. No slope/learning-rate sweep. Inherited head pretraining304updates per seed additional. No localization qualification or runtime model update.
- Supersedes: none; ReLU failures and all arm/integration statuses retained.
- Next dependency: Freeze one training-only regularized linear-readout diagnostic on fixed pooled descriptors, with training-only normalization and matched mask/control representations; report training fit/conditioning and reused-development errors without tuning regularization on development. No activation sweep or new holdout.


### E-20260926-AI-279 — leaky study aggregation

- Stage: S1
- Lane: AI
- Commit: `e99d19ad39df7ba451a962ad285540d41399a0fa` (frozen execution source; results/tests/docs committed together)
- Change: leaky study aggregation.
- Inputs/fixtures: scenes29000000..29000599 x4training,15000000..15000199 x4development; seeds260926/27/28; same initial weights,8epochs,19200presentations,304updates,AdamW0.001,key loss+anchor1 as ReLU comparison. Only hidden activation changed to fixed LeakyReLU0.01. Exact source/head hashes in train/pose_leaky_residual_*_plan.json; input/frozen/teacher/checkpoint hashes in reports; aggregate binds all reports.
- Command: `python software/ai/vision/summarize_pose_leaky_residual.py`
- Result: All3seeds retained. Appearance mean candidate0.8269351051589647mm,control0.8298856440815955,baseline0.8333639909177747. Full passes0/3,baseline-only2/3.
- Artifacts: vision/mask_conditioned_leaky_pose.py; train/train_pose_leaky_residual.py; eval/pose_leaky_residual_*_report.json; vision/summarize_pose_leaky_residual.py; tests/test_mask_conditioned_leaky_pose.py; tests/test_pose_leaky_residual.py; ignored local model.pt checkpoints.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Same evaluation images across optimization seeds; not independent data replication. No localization qualification or runtime model update.
- Supersedes: none; ReLU failures and all arm/integration statuses retained.
- Next dependency: Freeze one training-only regularized linear-readout diagnostic on fixed pooled descriptors, with training-only normalization and matched mask/control representations; report training fit/conditioning and reused-development errors without tuning regularization on development. No activation sweep or new holdout.


### E-20260926-AI-280 — leaky training evidence verification

- Stage: S1
- Lane: AI
- Commit: `e99d19ad39df7ba451a962ad285540d41399a0fa` (frozen execution source; results/tests/docs committed together)
- Change: leaky training evidence verification.
- Inputs/fixtures: scenes29000000..29000599 x4training,15000000..15000199 x4development; seeds260926/27/28; same initial weights,8epochs,19200presentations,304updates,AdamW0.001,key loss+anchor1 as ReLU comparison. Only hidden activation changed to fixed LeakyReLU0.01. Exact source/head hashes in train/pose_leaky_residual_*_plan.json; input/frozen/teacher/checkpoint hashes in reports; aggregate binds all reports.
- Command: `python -m pytest -q software/ai/tests/test_pose_leaky_residual.py`
- Result: PASS:2tests in1.68s. Prior identical initial weights and hyperparameters, paired input/frozen/teacher hashes, selected epoch, fixed budget, nonzero correction variation, frozen source bytes, versioned exports and acceptance recount.
- Artifacts: vision/mask_conditioned_leaky_pose.py; train/train_pose_leaky_residual.py; eval/pose_leaky_residual_*_report.json; vision/summarize_pose_leaky_residual.py; tests/test_mask_conditioned_leaky_pose.py; tests/test_pose_leaky_residual.py; ignored local model.pt checkpoints.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Ignored checkpoint bytes verified locally; portable checks retained. Existing pytest-asyncio warning. Shared boundary suite not triggered because contract unchanged. No localization qualification or runtime model update.
- Supersedes: none; ReLU failures and all arm/integration statuses retained.
- Next dependency: Freeze one training-only regularized linear-readout diagnostic on fixed pooled descriptors, with training-only normalization and matched mask/control representations; report training fit/conditioning and reused-development errors without tuning regularization on development. No activation sweep or new holdout.


### E-20260926-AI-281 — leaky study snapshot audit

- Stage: S1
- Lane: AI
- Commit: `e99d19ad39df7ba451a962ad285540d41399a0fa` (frozen execution source; results/tests/docs committed together)
- Change: leaky study snapshot audit.
- Inputs/fixtures: scenes29000000..29000599 x4training,15000000..15000199 x4development; seeds260926/27/28; same initial weights,8epochs,19200presentations,304updates,AdamW0.001,key loss+anchor1 as ReLU comparison. Only hidden activation changed to fixed LeakyReLU0.01. Exact source/head hashes in train/pose_leaky_residual_*_plan.json; input/frozen/teacher/checkpoint hashes in reports; aggregate binds all reports.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS:6170paths,875.3MiB,0unresolved findings,14reviewed synthetic fixtures.
- Artifacts: vision/mask_conditioned_leaky_pose.py; train/train_pose_leaky_residual.py; eval/pose_leaky_residual_*_report.json; vision/summarize_pose_leaky_residual.py; tests/test_mask_conditioned_leaky_pose.py; tests/test_pose_leaky_residual.py; ignored local model.pt checkpoints.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic audit before final documentation append; not runtime assurance. No localization qualification or runtime model update.
- Supersedes: none; ReLU failures and all arm/integration statuses retained.
- Next dependency: Freeze one training-only regularized linear-readout diagnostic on fixed pooled descriptors, with training-only normalization and matched mask/control representations; report training fit/conditioning and reused-development errors without tuning regularization on development. No activation sweep or new holdout.


### E-20260926-AI-282 — fixed ridge residual diagnostic

- Stage: S1
- Lane: AI
- Commit: `033a6f98be1d7db165b4636a123798dd8d5bb3ea` (frozen diagnostic source; results/tests/docs committed together)
- Change: fixed ridge residual diagnostic.
- Inputs/fixtures: scenes29000000..29000599 x4training,15000000..15000199 x4development; baseline pose plus frozen512-dimensional pooled descriptors,constant-one mask or three learned heads. Alpha0.01 fixed,training-only mean/std and residual mean; no hyperparameter selection. Source/checkpoint hashes in eval/linear_residual_v0_plan.json; coefficients and input/prediction hashes in report SHA256 eafa4501b969d070796cfd7068fb691e4006c6c50fb24a92e77dea618b73fd99.
- Command: `python software/ai/vision/probe_linear_residual.py`
- Result: Four closed-form training fits. Shared unmasked control training/development tails16/20 versus development baseline32; control meets baseline-only mean/tail/yaw/obstruction rule. Mask candidates development tails26/27/27,full rule FAIL3/3. Control MSE0.000451740training/0.000715115development versus baseline0.000853410/0.000859203. Matrix condition15505..15842; normal-equation residual<6e-17.
- Artifacts: vision/probe_linear_residual.py; eval/linear_residual_v0_plan.json and report.json; tests/test_linear_residual.py; docs/POSE_REPRESENTATION_REVIEW.md.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Reused synthetic development; selecting the control for follow-up is post-result model selection. No fresh holdout. Objective differs from anchored nonlinear key loss, so gains cannot be assigned solely to optimization. One deterministic control,three inherited-mask candidates,not independent optimization replications. Four analytical fits are training despite zero gradient optimizer updates. No runtime correction or qualification installed.
- Supersedes: none; all failed mask candidates and arm/integration statuses retained.
- Next dependency: Freeze the exact existing unmasked-control coefficients for an image-only export/parity/cost study; disclose reused-development selection. After parity, preregister untouched synthetic30M evaluation without refitting or tuning. No physical or integration gate completion.


### E-20260926-AI-283 — ridge verification

- Stage: S1
- Lane: AI
- Commit: `033a6f98be1d7db165b4636a123798dd8d5bb3ea` (frozen diagnostic source; results/tests/docs committed together)
- Change: ridge verification.
- Inputs/fixtures: scenes29000000..29000599 x4training,15000000..15000199 x4development; baseline pose plus frozen512-dimensional pooled descriptors,constant-one mask or three learned heads. Alpha0.01 fixed,training-only mean/std and residual mean; no hyperparameter selection. Source/checkpoint hashes in eval/linear_residual_v0_plan.json; coefficients and input/prediction hashes in report SHA256 eafa4501b969d070796cfd7068fb691e4006c6c50fb24a92e77dea618b73fd99.
- Command: `python -m pytest -q software/ai/tests/test_linear_residual.py`
- Result: PASS:6tests in1.63s; known ridge solution and unpenalized intercept, constant columns, frozen training normalization, invalid alpha rejection, source/input hashes, equation residual and acceptance recount.
- Artifacts: vision/probe_linear_residual.py; eval/linear_residual_v0_plan.json and report.json; tests/test_linear_residual.py; docs/POSE_REPRESENTATION_REVIEW.md.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Existing pytest-asyncio warning. Shared batch contract unchanged; boundary suite not triggered. Portable verifier permits absent ignored checkpoint bytes; verifies them when present. Four analytical fits are training despite zero gradient optimizer updates. No runtime correction or qualification installed.
- Supersedes: none; all failed mask candidates and arm/integration statuses retained.
- Next dependency: Freeze the exact existing unmasked-control coefficients for an image-only export/parity/cost study; disclose reused-development selection. After parity, preregister untouched synthetic30M evaluation without refitting or tuning. No physical or integration gate completion.


### E-20260926-AI-284 — ridge snapshot audit

- Stage: S1
- Lane: AI
- Commit: `033a6f98be1d7db165b4636a123798dd8d5bb3ea` (frozen diagnostic source; results/tests/docs committed together)
- Change: ridge snapshot audit.
- Inputs/fixtures: scenes29000000..29000599 x4training,15000000..15000199 x4development; baseline pose plus frozen512-dimensional pooled descriptors,constant-one mask or three learned heads. Alpha0.01 fixed,training-only mean/std and residual mean; no hyperparameter selection. Source/checkpoint hashes in eval/linear_residual_v0_plan.json; coefficients and input/prediction hashes in report SHA256 eafa4501b969d070796cfd7068fb691e4006c6c50fb24a92e77dea618b73fd99.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS:6174paths,875.7MiB,0unresolved findings,14reviewed synthetic fixtures.
- Artifacts: vision/probe_linear_residual.py; eval/linear_residual_v0_plan.json and report.json; tests/test_linear_residual.py; docs/POSE_REPRESENTATION_REVIEW.md.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic snapshot audit before final documentation append; not runtime qualification. Four analytical fits are training despite zero gradient optimizer updates. No runtime correction or qualification installed.
- Supersedes: none; all failed mask candidates and arm/integration statuses retained.
- Next dependency: Freeze the exact existing unmasked-control coefficients for an image-only export/parity/cost study; disclose reused-development selection. After parity, preregister untouched synthetic30M evaluation without refitting or tuning. No physical or integration gate completion.


### E-20260926-AI-285 — preserved linear export reference failure

- Stage: S1
- Lane: AI
- Commit: `2baa41e793ca4f85eee35f1a6131843f64d54ced` (frozen failed source)
- Change: initial standalone export verification.
- Inputs/fixtures: existing800 development images15000000..15000199 x4, exact unmasked coefficients from linear_residual_v0_report.json; source/checkpoint hashes in linear_export_v0_plan.json.
- Command: `python software/ai/vision/export_linear_residual.py`
- Result: FAIL at historical reference-prediction hash assertion. Exported prediction tolerance <=1e-10 passed before failure; no artifact or report was written. Exact max delta not printed in failed run. Preserved failure in eval/linear_export_v0_failure.json.
- Artifacts: unchanged vision/export_linear_residual.py and eval/linear_export_v0_plan.json; failed evidence JSON; separate corrected v1 source/plan.
- Hardware writes: 0
- Physical movements: 0
- Limitations: reference computation used64-row matrix multiplications versus original800-row calculation; floating-point shape sensitivity suspected, not established until corrected replay. No fitting or fresh data consumed.
- Supersedes: none; failed source and plan preserved.
- Next dependency: run separately frozen v1 reference using original full-array multiplication; do not relax1e-10 exported-model tolerance or change coefficients. Fresh evaluation depends on parity success.


### E-20260926-AI-286 — corrected standalone export parity

- Stage: S1
- Lane: AI
- Commit: `024bee407c7039224710cff3a418c64a31fdf374` (frozen corrected export source; tests/results committed with evidence)
- Change: corrected standalone export parity.
- Inputs/fixtures:800existing development images15000000..15000199 x4; exact prior unmasked fit; source hashes in eval/linear_export_v1_plan.json,model/pixel/prediction hashes in report.
- Command: `python software/ai/vision/export_linear_residual_v1.py`
- Result: PASS800existing development images; original full-array reference hash restored. Maximum normalized delta2.220446049250313e-16 <=1e-10; exact export/load and image-preprocessing parity. Artifact SHA2560cd2442e6a6190ad7228749bd47f20c108ec6062c5d319b1e36be054efd3af0e,1132606bytes. Backbone276867parameters +1539linear coefficients +1024normalization values. CPU median0.70615ms versus baseline0.54585ms;100batch-one calls after10warmups.
- Artifacts: vision/linear_residual_pose.py; vision/export_linear_residual_v1.py; eval/linear_export_v1_report.json; tests/test_linear_export.py; ignored results/linear_residual_export_v1/model.pt.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Selected on reused development; no new fits. CPU host timing only, float32backbone/float64residual. No calibration/uncertainty/runtime qualification. Failed v0 source and evidence retained. Batch contract unchanged.
- Supersedes: none; v1 corrects reference batching, not weights or tolerance.
- Next dependency: Execute separately frozen4000-image evaluation on30000000..30000999 x4, with fixed mean/tail/yaw/obstruction rule and no tuning.


### E-20260926-AI-287 — standalone export verification

- Stage: S1
- Lane: AI
- Commit: `024bee407c7039224710cff3a418c64a31fdf374` (frozen corrected export source; tests/results committed with evidence)
- Change: standalone export verification.
- Inputs/fixtures:800existing development images15000000..15000199 x4; exact prior unmasked fit; source hashes in eval/linear_export_v1_plan.json,model/pixel/prediction hashes in report.
- Command: `python -m pytest -q software/ai/tests/test_linear_export.py`
- Result: PASS6tests in1.63s: exact reload, image-only input, malformed scale/weights/schema/preprocessing rejection and frozen parity lineage. Existing pytest-asyncio warning.
- Artifacts: vision/linear_residual_pose.py; vision/export_linear_residual_v1.py; eval/linear_export_v1_report.json; tests/test_linear_export.py; ignored results/linear_residual_export_v1/model.pt.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Selected on reused development; no new fits. CPU host timing only, float32backbone/float64residual. No calibration/uncertainty/runtime qualification. Failed v0 source and evidence retained. Batch contract unchanged.
- Supersedes: none; v1 corrects reference batching, not weights or tolerance.
- Next dependency: Execute separately frozen4000-image evaluation on30000000..30000999 x4, with fixed mean/tail/yaw/obstruction rule and no tuning.


### E-20260926-AI-288 — untouched synthetic linear evaluation

- Stage: S1
- Lane: AI
- Commit: `c3284111e869487a0a5e947235242e8c6f331841` (frozen fresh-evaluation source/plan before image generation; results/tests/docs committed together)
- Change: untouched synthetic linear evaluation.
- Inputs/fixtures:30000000..30000999 x4conditions,ellipse obstruction,1000cases per condition. Frozen export SHA2560cd2442e6a6190ad7228749bd47f20c108ec6062c5d319b1e36be054efd3af0e; baseline SHA2560fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d. All source/artifact hashes in eval/linear_fresh_v0_plan.json; pixel/prediction hashes and individual errors in report SHA256 7d52f04e6ebec8d598ec5493688a0500b20539e69471e087170656365b5ea75a.
- Command: `python software/ai/vision/evaluate_linear_fresh.py`
- Result: FAIL fixed acceptance.4000images:baseline119tails,candidate121;54recovered,56introduced. Per-condition baseline/candidate tails18/25standard,28/27appearance,30/30partial,43/39full. Candidate means0.953486/0.847452/1.009655/1.092544mm versus baseline0.851725/0.840330/0.990319/1.142997. Standard mean/tail/yaw fail;appearance/partial mean fail. Combined obstruction tails73→69, insufficient for full rule.
- Artifacts: vision/evaluate_linear_fresh.py; eval/linear_fresh_v0_plan.json and report.json; tests/test_linear_fresh.py; docs/POSE_REPRESENTATION_REVIEW.md.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Previously unused seeds from same synthetic renderer, not physical validation. Candidate selected after reused-development analysis. No refit or tuning. Paired condition variants are correlated; no statistical significance claim. This range is now consumed. Zero new fits; no runtime model update or localization qualification.
- Supersedes: none; favorable development result and failed export attempt retained. Arm/integration statuses unchanged.
- Next dependency: Retain original baseline. Audit grouped scene-split integrity and train/development/evaluation coverage, then define model selection confined to grouped training data before new fitting.30000000..30000999 is consumed; no retuning against it or renewed untouched-data claims. Later confirmation requires separately frozen unused data.


### E-20260926-AI-289 — fresh evaluation verification

- Stage: S1
- Lane: AI
- Commit: `c3284111e869487a0a5e947235242e8c6f331841` (frozen fresh-evaluation source/plan before image generation; results/tests/docs committed together)
- Change: fresh evaluation verification.
- Inputs/fixtures:30000000..30000999 x4conditions,ellipse obstruction,1000cases per condition. Frozen export SHA2560cd2442e6a6190ad7228749bd47f20c108ec6062c5d319b1e36be054efd3af0e; baseline SHA2560fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d. All source/artifact hashes in eval/linear_fresh_v0_plan.json; pixel/prediction hashes and individual errors in report SHA256 7d52f04e6ebec8d598ec5493688a0500b20539e69471e087170656365b5ea75a.
- Command: `python -m pytest -q software/ai/tests/test_linear_fresh.py`
- Result: PASS:2tests in1.65s; strict all-condition and obstruction rule, all4000unique scene/condition keys, artifact/input lineage, complete mean/tail/yaw recount, recovery/introduction accounting and no-fit/no-authority fields.
- Artifacts: vision/evaluate_linear_fresh.py; eval/linear_fresh_v0_plan.json and report.json; tests/test_linear_fresh.py; docs/POSE_REPRESENTATION_REVIEW.md.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Existing pytest-asyncio warning. Contract unchanged; shared boundary suite not triggered. Portable artifact verifier checks local ignored bytes when present. Zero new fits; no runtime model update or localization qualification.
- Supersedes: none; favorable development result and failed export attempt retained. Arm/integration statuses unchanged.
- Next dependency: Retain original baseline. Audit grouped scene-split integrity and train/development/evaluation coverage, then define model selection confined to grouped training data before new fitting.30000000..30000999 is consumed; no retuning against it or renewed untouched-data claims. Later confirmation requires separately frozen unused data.


### E-20260926-AI-290 — export/evaluation snapshot audit

- Stage: S1
- Lane: AI
- Commit: `c3284111e869487a0a5e947235242e8c6f331841` (frozen fresh-evaluation source/plan before image generation; results/tests/docs committed together)
- Change: export/evaluation snapshot audit.
- Inputs/fixtures:30000000..30000999 x4conditions,ellipse obstruction,1000cases per condition. Frozen export SHA2560cd2442e6a6190ad7228749bd47f20c108ec6062c5d319b1e36be054efd3af0e; baseline SHA2560fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d. All source/artifact hashes in eval/linear_fresh_v0_plan.json; pixel/prediction hashes and individual errors in report SHA256 7d52f04e6ebec8d598ec5493688a0500b20539e69471e087170656365b5ea75a.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS:6186paths,879.2MiB,0 unresolved findings,14 reviewed synthetic fixtures.
- Artifacts: vision/evaluate_linear_fresh.py; eval/linear_fresh_v0_plan.json and report.json; tests/test_linear_fresh.py; docs/POSE_REPRESENTATION_REVIEW.md.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic snapshot audit before final documentation append; not runtime assurance. Zero new fits; no runtime model update or localization qualification.
- Supersedes: none; favorable development result and failed export attempt retained. Arm/integration statuses unchanged.
- Next dependency: Retain original baseline. Audit grouped scene-split integrity and train/development/evaluation coverage, then define model selection confined to grouped training data before new fitting.30000000..30000999 is consumed; no retuning against it or renewed untouched-data claims. Later confirmation requires separately frozen unused data.


### E-20260926-AI-291 — three-cohort split audit

- Stage: S1
- Lane: AI
- Commit: `c0bd40e686af7ff437a1b882a7a119510d95e8bc` (frozen audit source/plan; results, regression correction and protocol committed together in successor)
- Inputs/fixtures:29M600 scenes rectangle,15M200 scenes ellipse,30M1000 consumed scenes ellipse; four conditions each. Full frozen source/input hashes in eval/scene_split_audit_v0_plan.json. Report SHA256 `a23e1163dd93fa37cfcbb5bdeb723eba5aa79cc051698216a9680fb6f6147e8a`; individual pixel hashes and poses retained.
- Command: `python software/ai/vision/audit_scene_splits.py`
- Result: PASS:7200 existing images,1800 scenes; zero shared IDs or exact cross-cohort pixel duplicates. Training123/125 bins;2 development and19 consumed-evaluation scenes in empty training bins. Five folds120 scenes each,30 per corner.
- Artifacts: eval/scene_split_audit_v0_report.json; eval/scene_split_audit_v0_test_failure.json; eval/grouped_linear_selection_v1_protocol.json; vision/scene_pose_bins.py; tests/test_scene_split_audit.py; docs/GROUPED_MODEL_SELECTION.md.
- Hardware writes: 0
- Physical movements: 0
- Limitations: No new fits or unused evaluation images. Three cohorts only, not full historical pretraining. No exact duplicates does not exclude near duplicates. Coverage summaries do not establish failure causality. Baseline previously selected on15M; future grouped selection conditional on fixed baseline. Snapshot heuristic; existing pytest warning. Contract unchanged; shared boundary tests not triggered. Arm/integration statuses unchanged; no qualification installed.
- Supersedes: none; failed test and failed previous fresh evaluation retained.
- Next dependency: Freeze executable grouped training-only selection source/plan before fitting. Keep original baseline; reject all configurations if eligibility fails. Export parity and separately frozen unused confirmation required after any selection.


### E-20260926-AI-292 — boundary regression failure

- Stage: S1
- Lane: AI
- Commit: `c0bd40e686af7ff437a1b882a7a119510d95e8bc` (frozen audit source/plan; results, regression correction and protocol committed together in successor)
- Inputs/fixtures:29M600 scenes rectangle,15M200 scenes ellipse,30M1000 consumed scenes ellipse; four conditions each. Full frozen source/input hashes in eval/scene_split_audit_v0_plan.json. Report SHA256 `a23e1163dd93fa37cfcbb5bdeb723eba5aa79cc051698216a9680fb6f6147e8a`; individual pixel hashes and poses retained.
- Command: `python -m pytest -q software/ai/tests/test_scene_split_audit.py`
- Result: FAIL:1 failed,6 passed in1.88s. Exact upper yaw endpoint rejected through floating rounding. Preserved frozen implementation/report and eval/scene_split_audit_v0_test_failure.json.
- Artifacts: eval/scene_split_audit_v0_report.json; eval/scene_split_audit_v0_test_failure.json; eval/grouped_linear_selection_v1_protocol.json; vision/scene_pose_bins.py; tests/test_scene_split_audit.py; docs/GROUPED_MODEL_SELECTION.md.
- Hardware writes: 0
- Physical movements: 0
- Limitations: No new fits or unused evaluation images. Three cohorts only, not full historical pretraining. No exact duplicates does not exclude near duplicates. Coverage summaries do not establish failure causality. Baseline previously selected on15M; future grouped selection conditional on fixed baseline. Snapshot heuristic; existing pytest warning. Contract unchanged; shared boundary tests not triggered. Arm/integration statuses unchanged; no qualification installed.
- Supersedes: none; failed test and failed previous fresh evaluation retained.
- Next dependency: Freeze executable grouped training-only selection source/plan before fitting. Keep original baseline; reject all configurations if eligibility fails. Export parity and separately frozen unused confirmation required after any selection.


### E-20260926-AI-293 — corrected helper and selection protocol verification

- Stage: S1
- Lane: AI
- Commit: `c0bd40e686af7ff437a1b882a7a119510d95e8bc` (frozen audit source/plan; results, regression correction and protocol committed together in successor)
- Inputs/fixtures:29M600 scenes rectangle,15M200 scenes ellipse,30M1000 consumed scenes ellipse; four conditions each. Full frozen source/input hashes in eval/scene_split_audit_v0_plan.json. Report SHA256 `a23e1163dd93fa37cfcbb5bdeb723eba5aa79cc051698216a9680fb6f6147e8a`; individual pixel hashes and poses retained.
- Command: `python -m pytest -q software/ai/tests/test_scene_split_audit.py`
- Result: PASS:7 tests in1.79s. Separate scene_pose_bins helper fixes closed endpoint handling; recount matches all frozen report bins. Protocol specified, not executed; four fixed ridge alphas, five scene-group folds, fold-only normalization, consumed sets excluded.
- Artifacts: eval/scene_split_audit_v0_report.json; eval/scene_split_audit_v0_test_failure.json; eval/grouped_linear_selection_v1_protocol.json; vision/scene_pose_bins.py; tests/test_scene_split_audit.py; docs/GROUPED_MODEL_SELECTION.md.
- Hardware writes: 0
- Physical movements: 0
- Limitations: No new fits or unused evaluation images. Three cohorts only, not full historical pretraining. No exact duplicates does not exclude near duplicates. Coverage summaries do not establish failure causality. Baseline previously selected on15M; future grouped selection conditional on fixed baseline. Snapshot heuristic; existing pytest warning. Contract unchanged; shared boundary tests not triggered. Arm/integration statuses unchanged; no qualification installed.
- Supersedes: none; failed test and failed previous fresh evaluation retained.
- Next dependency: Freeze executable grouped training-only selection source/plan before fitting. Keep original baseline; reject all configurations if eligibility fails. Export parity and separately frozen unused confirmation required after any selection.


### E-20260926-AI-294 — split audit snapshot review

- Stage: S1
- Lane: AI
- Commit: `c0bd40e686af7ff437a1b882a7a119510d95e8bc` (frozen audit source/plan; results, regression correction and protocol committed together in successor)
- Inputs/fixtures:29M600 scenes rectangle,15M200 scenes ellipse,30M1000 consumed scenes ellipse; four conditions each. Full frozen source/input hashes in eval/scene_split_audit_v0_plan.json. Report SHA256 `a23e1163dd93fa37cfcbb5bdeb723eba5aa79cc051698216a9680fb6f6147e8a`; individual pixel hashes and poses retained.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS:6194 paths,882.1MiB,0 unresolved findings,14 reviewed synthetic fixtures.
- Artifacts: eval/scene_split_audit_v0_report.json; eval/scene_split_audit_v0_test_failure.json; eval/grouped_linear_selection_v1_protocol.json; vision/scene_pose_bins.py; tests/test_scene_split_audit.py; docs/GROUPED_MODEL_SELECTION.md.
- Hardware writes: 0
- Physical movements: 0
- Limitations: No new fits or unused evaluation images. Three cohorts only, not full historical pretraining. No exact duplicates does not exclude near duplicates. Coverage summaries do not establish failure causality. Baseline previously selected on15M; future grouped selection conditional on fixed baseline. Snapshot heuristic; existing pytest warning. Contract unchanged; shared boundary tests not triggered. Arm/integration statuses unchanged; no qualification installed.
- Supersedes: none; failed test and failed previous fresh evaluation retained.
- Next dependency: Freeze executable grouped training-only selection source/plan before fitting. Keep original baseline; reject all configurations if eligibility fails. Export parity and separately frozen unused confirmation required after any selection.


### E-20260926-AI-295 — grouped training-only model selection

- Stage: S1
- Lane: AI
- Commit: `e38664763e51f99c81781c42779a3d631ccfa805` (source/plan frozen before rendering or fitting; evidence/tests/docs in successor commit)
- Inputs/fixtures:29000000..29000599, four conditions per scene, rectangle fit/ellipse validation. Five folds480 training and120 validation scenes each; all variants grouped. Fixed original baseline SHA2560fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d. Source/protocol/artifact hashes in train/grouped_linear_v1_plan.json; pixel/prediction hashes, all fold coefficients and all out-of-fold errors in report SHA256 `0d853d6e8a9e4c94221bbce3e228d47126b8ba92a25a3b4b7c1e94d5a11b6e70`.
- Command: `python software/ai/train/select_grouped_linear.py`
- Result: PASS selection:20 closed-form fits; alphas0.001/0.01/0.1/1.0 yield107/76/69/61 tails versus74 baseline. Only1.0 satisfies all-condition mean/tail/yaw and strict combined obstruction improvement. Selected condition tails11/14/13/23 versus14/14/19/27. Mean errors0.807134/0.830765/0.895669/1.042441mm versus0.834092/0.838270/0.950769/1.109897mm. Obstruction tails46 to36. No final fit.
- Artifacts: train/select_grouped_linear.py; train/grouped_linear_v1_plan.json; eval/grouped_linear_v1_report.json; tests/test_grouped_linear_selection.py; docs/GROUPED_MODEL_SELECTION.md.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Training selection only, not independent confirmation or physical accuracy. Historical baseline selection remains conditional. Ellipse variants within training pool are derived selection data. Four alphas selected once using fixed rule; failed configurations retained. No final model, runtime promotion, calibrated uncertainty or qualification. ModelMotionBatchV2 unchanged; shared boundary suite not triggered. Snapshot audit heuristic, before final ledger append. Arm/integration statuses unchanged.
- Supersedes: none; previous failed fresh evaluation retained.
- Next dependency: Freeze one final fit at selected alpha1.0 on all600 rectangle scenes; verify standalone export parity; separately freeze an unused confirmation range after checking intervening use. Do not tune on consumed15M/30M evaluation.


### E-20260926-AI-296 — grouped selection regression verification

- Stage: S1
- Lane: AI
- Commit: `e38664763e51f99c81781c42779a3d631ccfa805` (source/plan frozen before rendering or fitting; evidence/tests/docs in successor commit)
- Inputs/fixtures:29000000..29000599, four conditions per scene, rectangle fit/ellipse validation. Five folds480 training and120 validation scenes each; all variants grouped. Fixed original baseline SHA2560fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d. Source/protocol/artifact hashes in train/grouped_linear_v1_plan.json; pixel/prediction hashes, all fold coefficients and all out-of-fold errors in report SHA256 `0d853d6e8a9e4c94221bbce3e228d47126b8ba92a25a3b4b7c1e94d5a11b6e70`.
- Command: `python -m pytest -q software/ai/tests/test_grouped_linear_selection.py`
- Result: PASS:3 tests in1.68s. Validation perturbations do not alter fold-training fit; rejection/tie rules, complete metric recount, disjoint fold populations and frozen lineage verified. Existing pytest-asyncio warning.
- Artifacts: train/select_grouped_linear.py; train/grouped_linear_v1_plan.json; eval/grouped_linear_v1_report.json; tests/test_grouped_linear_selection.py; docs/GROUPED_MODEL_SELECTION.md.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Training selection only, not independent confirmation or physical accuracy. Historical baseline selection remains conditional. Ellipse variants within training pool are derived selection data. Four alphas selected once using fixed rule; failed configurations retained. No final model, runtime promotion, calibrated uncertainty or qualification. ModelMotionBatchV2 unchanged; shared boundary suite not triggered. Snapshot audit heuristic, before final ledger append. Arm/integration statuses unchanged.
- Supersedes: none; previous failed fresh evaluation retained.
- Next dependency: Freeze one final fit at selected alpha1.0 on all600 rectangle scenes; verify standalone export parity; separately freeze an unused confirmation range after checking intervening use. Do not tune on consumed15M/30M evaluation.


### E-20260926-AI-297 — grouped selection snapshot audit

- Stage: S1
- Lane: AI
- Commit: `e38664763e51f99c81781c42779a3d631ccfa805` (source/plan frozen before rendering or fitting; evidence/tests/docs in successor commit)
- Inputs/fixtures:29000000..29000599, four conditions per scene, rectangle fit/ellipse validation. Five folds480 training and120 validation scenes each; all variants grouped. Fixed original baseline SHA2560fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d. Source/protocol/artifact hashes in train/grouped_linear_v1_plan.json; pixel/prediction hashes, all fold coefficients and all out-of-fold errors in report SHA256 `0d853d6e8a9e4c94221bbce3e228d47126b8ba92a25a3b4b7c1e94d5a11b6e70`.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS:6198 paths,889.5MiB,0 unresolved findings,14 reviewed synthetic fixtures.
- Artifacts: train/select_grouped_linear.py; train/grouped_linear_v1_plan.json; eval/grouped_linear_v1_report.json; tests/test_grouped_linear_selection.py; docs/GROUPED_MODEL_SELECTION.md.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Training selection only, not independent confirmation or physical accuracy. Historical baseline selection remains conditional. Ellipse variants within training pool are derived selection data. Four alphas selected once using fixed rule; failed configurations retained. No final model, runtime promotion, calibrated uncertainty or qualification. ModelMotionBatchV2 unchanged; shared boundary suite not triggered. Snapshot audit heuristic, before final ledger append. Arm/integration statuses unchanged.
- Supersedes: none; previous failed fresh evaluation retained.
- Next dependency: Freeze one final fit at selected alpha1.0 on all600 rectangle scenes; verify standalone export parity; separately freeze an unused confirmation range after checking intervening use. Do not tune on consumed15M/30M evaluation.


### E-20260926-AI-298 — selected refit and export parity

- Stage: S1
- Lane: AI
- Commit: `becbef91e3834b4495ff7071ced03d7edca0e35d` (frozen before fit; evidence committed with confirmation source)
- Inputs/fixtures:29000000..29000599 x4 rectangle variants,2400 training images. Full source and selection hashes in train/grouped_linear_refit_v1_plan.json. Pixel SHA256 fe9e1fdf76cf5cff6cb6f542e8e65034f0e6d692fd7267e50f2740d93542a77a.
- Command: `python software/ai/train/refit_grouped_linear.py`
- Result: PASS:one final closed-form fit at selected alpha1.0. Max normalized export/reference delta2.220446049250313e-16, below1e-10;2400-image reload exact, image preprocessing exact. Artifact1132606bytes SHA256 c9f4ef6d8f9e50317a917154fccacce46506ab2e7cde8267396e28fec156147b.
- Artifacts: train/refit_grouped_linear.py; train/grouped_linear_refit_v1_plan.json; eval/grouped_linear_refit_v1_report.json; ignored results/grouped_linear_refit_v1/model.pt. Full coefficients retained in tracked report.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Training parity only; no independent accuracy result. Original baseline remains in use. No coordinate uncertainty/calibration qualification. ModelMotionBatchV2 unchanged; arm/integration status unchanged.
- Supersedes: none; earlier rejected candidates and failed evaluation retained.
- Next dependency: Freeze confirmation on unused30001000..30001999 x4 ellipse conditions; fixed original acceptance rule, zero tuning.


### E-20260926-AI-299 — grouped candidate unused-scene confirmation

- Stage: S1
- Lane: AI
- Commit: `4c26b75d7748131e30e148a7990a4c0cd9c65e3c` (confirmation source, artifact and plan frozen before new scenes; results/tests/docs in successor)
- Inputs/fixtures:30001000..30001999 x4 conditions, ellipse obstruction,1000 cases per condition. Candidate artifact SHA256 c9f4ef6d8f9e50317a917154fccacce46506ab2e7cde8267396e28fec156147b. Full frozen hashes in eval/grouped_linear_confirmation_v1_plan.json; individual errors and pixel/prediction hashes in report SHA256 `0870d83f68ceb4b185b46e174e401e8c73e11f3b58c61e1d0f91a0eea823abad`.
- Command: `python software/ai/vision/evaluate_grouped_linear_confirmation.py`
- Result: PASS fixed acceptance:4000 images, baseline138 tails versus121 candidate (12.32% fewer);26 recovered and9 introduced. Standard23→20,appearance30→28,partial32→30,full53→43. Mean errors0.864370→0.858235,0.870828→0.863050,1.002389→0.968973,1.158315→1.106871mm. Combined obstruction85→73. All condition checks pass; standard yaw p95 increases0.516452→0.546551degrees within fixed10% allowance.
- Artifacts: vision/evaluate_grouped_linear_confirmation.py; eval/grouped_linear_confirmation_v1_plan.json and report.json; tests/test_grouped_linear_confirmation.py; docs/GROUPED_MODEL_SELECTION.md.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Same-renderer synthetic confirmation, correlated variants, no physical-camera data or statistical-significance claim. No fits during confirmation; no threshold change or tuning. Range30001000..30001999 is now consumed. Candidate still has121 tails and9 newly introduced failures. No runtime promotion or calibrated uncertainty qualification; arm/integration statuses unchanged. Batch contract unchanged; boundary tests not triggered. Snapshot heuristic before final ledger append.
- Supersedes: none; previous failed fresh test and rejected settings retained.
- Next dependency: Freeze candidate weights. Audit remaining and introduced failures plus observation-quality signals, then specify an independent uncertainty/abstention calibration protocol. Consumed evaluation may inform diagnostics but cannot serve as fresh confirmation or calibration-selection evidence. Retain runtime baseline until separate qualification evidence exists.


### E-20260926-AI-300 — refit and confirmation verification

- Stage: S1
- Lane: AI
- Commit: `4c26b75d7748131e30e148a7990a4c0cd9c65e3c` (confirmation source, artifact and plan frozen before new scenes; results/tests/docs in successor)
- Inputs/fixtures:30001000..30001999 x4 conditions, ellipse obstruction,1000 cases per condition. Candidate artifact SHA256 c9f4ef6d8f9e50317a917154fccacce46506ab2e7cde8267396e28fec156147b. Full frozen hashes in eval/grouped_linear_confirmation_v1_plan.json; individual errors and pixel/prediction hashes in report SHA256 `0870d83f68ceb4b185b46e174e401e8c73e11f3b58c61e1d0f91a0eea823abad`.
- Command: `python -m pytest -q software/ai/tests/test_grouped_linear_confirmation.py`
- Result: PASS:4 tests in1.76s. All4000 scene-condition pairs, metric/transition recount, fixed acceptance, coefficient/export and source lineage checked. Existing pytest warning.
- Artifacts: vision/evaluate_grouped_linear_confirmation.py; eval/grouped_linear_confirmation_v1_plan.json and report.json; tests/test_grouped_linear_confirmation.py; docs/GROUPED_MODEL_SELECTION.md.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Same-renderer synthetic confirmation, correlated variants, no physical-camera data or statistical-significance claim. No fits during confirmation; no threshold change or tuning. Range30001000..30001999 is now consumed. Candidate still has121 tails and9 newly introduced failures. No runtime promotion or calibrated uncertainty qualification; arm/integration statuses unchanged. Batch contract unchanged; boundary tests not triggered. Snapshot heuristic before final ledger append.
- Supersedes: none; previous failed fresh test and rejected settings retained.
- Next dependency: Freeze candidate weights. Audit remaining and introduced failures plus observation-quality signals, then specify an independent uncertainty/abstention calibration protocol. Consumed evaluation may inform diagnostics but cannot serve as fresh confirmation or calibration-selection evidence. Retain runtime baseline until separate qualification evidence exists.


### E-20260926-AI-301 — confirmation snapshot audit

- Stage: S1
- Lane: AI
- Commit: `4c26b75d7748131e30e148a7990a4c0cd9c65e3c` (confirmation source, artifact and plan frozen before new scenes; results/tests/docs in successor)
- Inputs/fixtures:30001000..30001999 x4 conditions, ellipse obstruction,1000 cases per condition. Candidate artifact SHA256 c9f4ef6d8f9e50317a917154fccacce46506ab2e7cde8267396e28fec156147b. Full frozen hashes in eval/grouped_linear_confirmation_v1_plan.json; individual errors and pixel/prediction hashes in report SHA256 `0870d83f68ceb4b185b46e174e401e8c73e11f3b58c61e1d0f91a0eea823abad`.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS:6205 paths,893.0MiB,0 unresolved findings,14 reviewed synthetic fixtures.
- Artifacts: vision/evaluate_grouped_linear_confirmation.py; eval/grouped_linear_confirmation_v1_plan.json and report.json; tests/test_grouped_linear_confirmation.py; docs/GROUPED_MODEL_SELECTION.md.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Same-renderer synthetic confirmation, correlated variants, no physical-camera data or statistical-significance claim. No fits during confirmation; no threshold change or tuning. Range30001000..30001999 is now consumed. Candidate still has121 tails and9 newly introduced failures. No runtime promotion or calibrated uncertainty qualification; arm/integration statuses unchanged. Batch contract unchanged; boundary tests not triggered. Snapshot heuristic before final ledger append.
- Supersedes: none; previous failed fresh test and rejected settings retained.
- Next dependency: Freeze candidate weights. Audit remaining and introduced failures plus observation-quality signals, then specify an independent uncertainty/abstention calibration protocol. Consumed evaluation may inform diagnostics but cannot serve as fresh confirmation or calibration-selection evidence. Retain runtime baseline until separate qualification evidence exists.


### E-20260927-AI-302 — candidate failure decomposition

- Stage: S1
- Lane: AI
- Commit: `2a2b572a28f0d729680cd58732eb01b87a434641` (audit source/plan frozen before execution; report/tests/protocol/docs in successor)
- Inputs/fixtures: Existing4000-row grouped_linear_confirmation_v1_report.json, scenes30001000..30001999 x4. Source/script hashes in eval/grouped_failure_audit_v1_plan.json. Audit report SHA256 `93c477bb03699e48147887db0ee94794375021cf391f3bdd05428ebb4158499f`. Frozen model SHA256 c9f4ef6d8f9e50317a917154fccacce46506ab2e7cde8267396e28fec156147b.
- Command: `python software/ai/vision/audit_grouped_failures.py`
- Result: PASS descriptive audit:112 persistent,9 introduced,26 recovered,3853 both within3mm. Candidate121 failing images span57 scenes. Worst11.417265mm; introduced worst9.482836mm.59 failing images have both isolated components <=3mm. No runtime quality signals in source evidence.
- Artifacts: vision/audit_grouped_failures.py; eval/grouped_failure_audit_v1_plan.json and report.json; tests/test_grouped_failure_audit.py; eval/grouped_uncertainty_v1_protocol.json; docs/GROUPED_UNCERTAINTY_PROTOCOL.md.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Consumed synthetic data only; zero new images/fits. Truth-derived decomposition cannot serve as observation quality or causal attribution. No abstention classifier, confidence calibration or physical qualification exists from this increment. Scene-group uncertainty proposal not executed; exchangeability assumptions do not establish physical-camera applicability. Snapshot heuristic before final ledger append; existing pytest warning. ModelMotionBatchV2 unchanged; boundary tests not triggered. Arm/integration statuses unchanged.
- Supersedes: none; previous failed and successful evaluations retained.
- Next dependency: Check intervening allocations, freeze executable uncertainty protocol and two unused scene ranges; execute global-bound calibration and separate confirmation. Preserve zero-utility outcome if radius exceeds3mm. Keep weights frozen and runtime baseline unchanged.


### E-20260927-AI-303 — failure audit regression and protocol

- Stage: S1
- Lane: AI
- Commit: `2a2b572a28f0d729680cd58732eb01b87a434641` (audit source/plan frozen before execution; report/tests/protocol/docs in successor)
- Inputs/fixtures: Existing4000-row grouped_linear_confirmation_v1_report.json, scenes30001000..30001999 x4. Source/script hashes in eval/grouped_failure_audit_v1_plan.json. Audit report SHA256 `93c477bb03699e48147887db0ee94794375021cf391f3bdd05428ebb4158499f`. Frozen model SHA256 c9f4ef6d8f9e50317a917154fccacce46506ab2e7cde8267396e28fec156147b.
- Command: `python -m pytest -q software/ai/tests/test_grouped_failure_audit.py`
- Result: PASS:2 tests in0.18s; exact3mm boundary, complete disjoint4000-row partition, condition/member recount and frozen hashes. Specified separate1000-scene calibration and1000-scene confirmation protocol; alpha0.01, joint target/variant scene scores, fixed3mm research-only utility gate. Not executed; no ranges allocated.
- Artifacts: vision/audit_grouped_failures.py; eval/grouped_failure_audit_v1_plan.json and report.json; tests/test_grouped_failure_audit.py; eval/grouped_uncertainty_v1_protocol.json; docs/GROUPED_UNCERTAINTY_PROTOCOL.md.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Consumed synthetic data only; zero new images/fits. Truth-derived decomposition cannot serve as observation quality or causal attribution. No abstention classifier, confidence calibration or physical qualification exists from this increment. Scene-group uncertainty proposal not executed; exchangeability assumptions do not establish physical-camera applicability. Snapshot heuristic before final ledger append; existing pytest warning. ModelMotionBatchV2 unchanged; boundary tests not triggered. Arm/integration statuses unchanged.
- Supersedes: none; previous failed and successful evaluations retained.
- Next dependency: Check intervening allocations, freeze executable uncertainty protocol and two unused scene ranges; execute global-bound calibration and separate confirmation. Preserve zero-utility outcome if radius exceeds3mm. Keep weights frozen and runtime baseline unchanged.


### E-20260927-AI-304 — failure audit repository review

- Stage: S1
- Lane: AI
- Commit: `2a2b572a28f0d729680cd58732eb01b87a434641` (audit source/plan frozen before execution; report/tests/protocol/docs in successor)
- Inputs/fixtures: Existing4000-row grouped_linear_confirmation_v1_report.json, scenes30001000..30001999 x4. Source/script hashes in eval/grouped_failure_audit_v1_plan.json. Audit report SHA256 `93c477bb03699e48147887db0ee94794375021cf391f3bdd05428ebb4158499f`. Frozen model SHA256 c9f4ef6d8f9e50317a917154fccacce46506ab2e7cde8267396e28fec156147b.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS:6211 paths,893.7MiB,0 unresolved findings,14 reviewed synthetic fixtures.
- Artifacts: vision/audit_grouped_failures.py; eval/grouped_failure_audit_v1_plan.json and report.json; tests/test_grouped_failure_audit.py; eval/grouped_uncertainty_v1_protocol.json; docs/GROUPED_UNCERTAINTY_PROTOCOL.md.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Consumed synthetic data only; zero new images/fits. Truth-derived decomposition cannot serve as observation quality or causal attribution. No abstention classifier, confidence calibration or physical qualification exists from this increment. Scene-group uncertainty proposal not executed; exchangeability assumptions do not establish physical-camera applicability. Snapshot heuristic before final ledger append; existing pytest warning. ModelMotionBatchV2 unchanged; boundary tests not triggered. Arm/integration statuses unchanged.
- Supersedes: none; previous failed and successful evaluations retained.
- Next dependency: Check intervening allocations, freeze executable uncertainty protocol and two unused scene ranges; execute global-bound calibration and separate confirmation. Preserve zero-utility outcome if radius exceeds3mm. Keep weights frozen and runtime baseline unchanged.


### E-20260927-AI-305 — global uncertainty feasibility failure

- Stage: S1
- Lane: AI
- Commit: `7992e942194285390893a91b16c1e78e50c973f6` (source/plan frozen before calibration/confirmation; evidence/tests/docs in successor)
- Inputs/fixtures:31000000..31000999 calibration and32000000..32000999 confirmation,1000 scenes/4000 images each, four ellipse conditions,46 targets. Model SHA256 c9f4ef6d8f9e50317a917154fccacce46506ab2e7cde8267396e28fec156147b. Source/artifact hashes in eval/grouped_uncertainty_v1_plan.json. Report SHA256 `9a1ead5d6695989d04b9274831056ab5e3d7c24a6a00b5f2697fc6415483c8b1`; full pixel/prediction hashes and per-image/scene scores retained.
- Command: `python software/ai/vision/evaluate_grouped_uncertainty.py`
- Result: FAIL fixed feasibility:rank991/1000 calibration bound4.9120642323mm exceeds3mm tolerance; accepted fraction0. Confirmation covers987/1000 scenes(98.7%), below99% rule;95% Wilson interval[97.7886%,99.2387%]. Image coverage99.275%(3971/4000),13 scene violations. No gate tuning.
- Artifacts: vision/evaluate_grouped_uncertainty.py; eval/grouped_uncertainty_v1_plan.json and report.json; tests/test_grouped_uncertainty.py; eval/grouped_uncertainty_v1_test_failure.json; docs/GROUPED_UNCERTAINTY_PROTOCOL.md.
- Hardware writes: 0
- Physical movements: 0
- Limitations: One global-bound calibration fit, zero model fits. Both newly generated ranges now consumed. Same-renderer synthetic scenes; interval assumes binomial scene observations and is not physical-camera assurance.99% marginal target does not guarantee every1000-scene sample meets99%; observed rule nevertheless fails and utility is zero. No runtime bound installed or calibrated physical qualification. Contract unchanged; boundary suite not triggered. Existing pytest warning; arm/integration statuses unchanged.
- Supersedes: none; zero-utility and initial test failure retained.
- Next dependency: Specify image-derived uncertainty features and grouped training-only evaluation with frozen pose model; no training/threshold selection using these consumed calibration/confirmation cohorts. Any locally scaled bound requires a separately frozen calibration and independent confirmation allocation. Keep runtime baseline unchanged.


### E-20260927-AI-306 — uncertainty test endpoint failure

- Stage: S1
- Lane: AI
- Commit: `7992e942194285390893a91b16c1e78e50c973f6` (source/plan frozen before calibration/confirmation; evidence/tests/docs in successor)
- Inputs/fixtures:31000000..31000999 calibration and32000000..32000999 confirmation,1000 scenes/4000 images each, four ellipse conditions,46 targets. Model SHA256 c9f4ef6d8f9e50317a917154fccacce46506ab2e7cde8267396e28fec156147b. Source/artifact hashes in eval/grouped_uncertainty_v1_plan.json. Report SHA256 `9a1ead5d6695989d04b9274831056ab5e3d7c24a6a00b5f2697fc6415483c8b1`; full pixel/prediction hashes and per-image/scene scores retained.
- Command: `python -m pytest -q software/ai/tests/test_grouped_uncertainty.py`
- Result: FAIL:1 failed,7 passed in1.80s. Test expected exact Wilson lower endpoint0; floating cancellation yields3.469446951953614e-18. Failure retained in eval/grouped_uncertainty_v1_test_failure.json.
- Artifacts: vision/evaluate_grouped_uncertainty.py; eval/grouped_uncertainty_v1_plan.json and report.json; tests/test_grouped_uncertainty.py; eval/grouped_uncertainty_v1_test_failure.json; docs/GROUPED_UNCERTAINTY_PROTOCOL.md.
- Hardware writes: 0
- Physical movements: 0
- Limitations: One global-bound calibration fit, zero model fits. Both newly generated ranges now consumed. Same-renderer synthetic scenes; interval assumes binomial scene observations and is not physical-camera assurance.99% marginal target does not guarantee every1000-scene sample meets99%; observed rule nevertheless fails and utility is zero. No runtime bound installed or calibrated physical qualification. Contract unchanged; boundary suite not triggered. Existing pytest warning; arm/integration statuses unchanged.
- Supersedes: none; zero-utility and initial test failure retained.
- Next dependency: Specify image-derived uncertainty features and grouped training-only evaluation with frozen pose model; no training/threshold selection using these consumed calibration/confirmation cohorts. Any locally scaled bound requires a separately frozen calibration and independent confirmation allocation. Keep runtime baseline unchanged.


### E-20260927-AI-307 — uncertainty verification after test correction

- Stage: S1
- Lane: AI
- Commit: `7992e942194285390893a91b16c1e78e50c973f6` (source/plan frozen before calibration/confirmation; evidence/tests/docs in successor)
- Inputs/fixtures:31000000..31000999 calibration and32000000..32000999 confirmation,1000 scenes/4000 images each, four ellipse conditions,46 targets. Model SHA256 c9f4ef6d8f9e50317a917154fccacce46506ab2e7cde8267396e28fec156147b. Source/artifact hashes in eval/grouped_uncertainty_v1_plan.json. Report SHA256 `9a1ead5d6695989d04b9274831056ab5e3d7c24a6a00b5f2697fc6415483c8b1`; full pixel/prediction hashes and per-image/scene scores retained.
- Command: `python -m pytest -q software/ai/tests/test_grouped_uncertainty.py`
- Result: PASS:8 tests in1.83s. Corrected analytic endpoint assertion to absolute1e-15; frozen source/report/thresholds unchanged. Quantile rank, small-sample infinite-bound abstention, fixed gate, disjoint scene groups, all8000 rows and coverage recount verified.
- Artifacts: vision/evaluate_grouped_uncertainty.py; eval/grouped_uncertainty_v1_plan.json and report.json; tests/test_grouped_uncertainty.py; eval/grouped_uncertainty_v1_test_failure.json; docs/GROUPED_UNCERTAINTY_PROTOCOL.md.
- Hardware writes: 0
- Physical movements: 0
- Limitations: One global-bound calibration fit, zero model fits. Both newly generated ranges now consumed. Same-renderer synthetic scenes; interval assumes binomial scene observations and is not physical-camera assurance.99% marginal target does not guarantee every1000-scene sample meets99%; observed rule nevertheless fails and utility is zero. No runtime bound installed or calibrated physical qualification. Contract unchanged; boundary suite not triggered. Existing pytest warning; arm/integration statuses unchanged.
- Supersedes: none; zero-utility and initial test failure retained.
- Next dependency: Specify image-derived uncertainty features and grouped training-only evaluation with frozen pose model; no training/threshold selection using these consumed calibration/confirmation cohorts. Any locally scaled bound requires a separately frozen calibration and independent confirmation allocation. Keep runtime baseline unchanged.


### E-20260927-AI-308 — uncertainty snapshot audit

- Stage: S1
- Lane: AI
- Commit: `7992e942194285390893a91b16c1e78e50c973f6` (source/plan frozen before calibration/confirmation; evidence/tests/docs in successor)
- Inputs/fixtures:31000000..31000999 calibration and32000000..32000999 confirmation,1000 scenes/4000 images each, four ellipse conditions,46 targets. Model SHA256 c9f4ef6d8f9e50317a917154fccacce46506ab2e7cde8267396e28fec156147b. Source/artifact hashes in eval/grouped_uncertainty_v1_plan.json. Report SHA256 `9a1ead5d6695989d04b9274831056ab5e3d7c24a6a00b5f2697fc6415483c8b1`; full pixel/prediction hashes and per-image/scene scores retained.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS:6215 paths,897.4MiB,0 unresolved findings,14 reviewed synthetic fixtures. Snapshot before additional failed-test artifact and final documentation append.
- Artifacts: vision/evaluate_grouped_uncertainty.py; eval/grouped_uncertainty_v1_plan.json and report.json; tests/test_grouped_uncertainty.py; eval/grouped_uncertainty_v1_test_failure.json; docs/GROUPED_UNCERTAINTY_PROTOCOL.md.
- Hardware writes: 0
- Physical movements: 0
- Limitations: One global-bound calibration fit, zero model fits. Both newly generated ranges now consumed. Same-renderer synthetic scenes; interval assumes binomial scene observations and is not physical-camera assurance.99% marginal target does not guarantee every1000-scene sample meets99%; observed rule nevertheless fails and utility is zero. No runtime bound installed or calibrated physical qualification. Contract unchanged; boundary suite not triggered. Existing pytest warning; arm/integration statuses unchanged.
- Supersedes: none; zero-utility and initial test failure retained.
- Next dependency: Specify image-derived uncertainty features and grouped training-only evaluation with frozen pose model; no training/threshold selection using these consumed calibration/confirmation cohorts. Any locally scaled bound requires a separately frozen calibration and independent confirmation allocation. Keep runtime baseline unchanged.


### E-20260927-AI-309 — image-dependent scale training feasibility

- Stage: S1
- Lane: AI
- Commit: `d5680841be29143c5fe0900c211f59c2a834c4f5` (source/features/plan frozen before rendering/fitting; report/tests/docs in successor)
- Inputs/fixtures:33000000..33000599, rectangle/ellipse x4conditions,600 scenes/4800 images. Five folds3840 fit/960 validation images; all8 variants grouped. Frozen pose artifact SHA256 c9f4ef6d8f9e50317a917154fccacce46506ab2e7cde8267396e28fec156147b. Source hashes in train/image_quality_scale_v1_plan.json; report SHA256 `9b58bf614dde9006056e3ac92f90a7213ff3d8d78ca109e5ea51e14842104c80` includes pixel/feature/prediction hashes, fold coefficients and all row errors/scales.
- Command: `python software/ai/train/evaluate_image_quality_scale.py`
- Result: PASS fixed feasibility:five grouped fits on4800 images. Constant versus scale log-error MSE:standard0.242925→0.234846,appearance0.259529→0.246693,partial0.240460→0.233817,full0.270347→0.254223. All conditions improve. No final fit or bound calibration.
- Artifacts: vision/image_quality_scale.py; train/evaluate_image_quality_scale.py; train/image_quality_scale_v1_plan.json; eval/image_quality_scale_v1_report.json; tests/test_image_quality_scale.py; docs/IMAGE_DEPENDENT_UNCERTAINTY.md.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Five uncertainty-regressor fits, zero pose fits/calibration fits. Freshly allocated uncertainty-training data only; no untouched confirmation claim. Error-scale output is not confidence or an upper bound. Modest synthetic MSE improvement cannot establish useful acceptance or physical-camera behavior. Historical pose selection remains fixed. No calibrated qualification/runtime gate installed. Batch contract unchanged; shared boundary suite not triggered. Snapshot heuristic before final docs; existing pytest warning. Arm/integration statuses unchanged.
- Supersedes: none; failed global bound retained.
- Next dependency: Freeze one full scale fit and export parity, then separately allocate/freeze independent normalized-score calibration and confirmation. Keep pose weights, features, alpha and3mm research tolerance fixed. Report accepted-subset violations without claiming conditional coverage from marginal calibration.


### E-20260927-AI-310 — image-only scale regression verification

- Stage: S1
- Lane: AI
- Commit: `d5680841be29143c5fe0900c211f59c2a834c4f5` (source/features/plan frozen before rendering/fitting; report/tests/docs in successor)
- Inputs/fixtures:33000000..33000599, rectangle/ellipse x4conditions,600 scenes/4800 images. Five folds3840 fit/960 validation images; all8 variants grouped. Frozen pose artifact SHA256 c9f4ef6d8f9e50317a917154fccacce46506ab2e7cde8267396e28fec156147b. Source hashes in train/image_quality_scale_v1_plan.json; report SHA256 `9b58bf614dde9006056e3ac92f90a7213ff3d8d78ca109e5ea51e14842104c80` includes pixel/feature/prediction hashes, fold coefficients and all row errors/scales.
- Command: `python -m pytest -q software/ai/tests/test_image_quality_scale.py`
- Result: PASS:3 tests in0.29s. RGB-only finite feature extraction, brightness/edge responses, training-only fit isolation, positive clipped outputs, complete4800-row fold/population/metric recount and lineage verified.
- Artifacts: vision/image_quality_scale.py; train/evaluate_image_quality_scale.py; train/image_quality_scale_v1_plan.json; eval/image_quality_scale_v1_report.json; tests/test_image_quality_scale.py; docs/IMAGE_DEPENDENT_UNCERTAINTY.md.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Five uncertainty-regressor fits, zero pose fits/calibration fits. Freshly allocated uncertainty-training data only; no untouched confirmation claim. Error-scale output is not confidence or an upper bound. Modest synthetic MSE improvement cannot establish useful acceptance or physical-camera behavior. Historical pose selection remains fixed. No calibrated qualification/runtime gate installed. Batch contract unchanged; shared boundary suite not triggered. Snapshot heuristic before final docs; existing pytest warning. Arm/integration statuses unchanged.
- Supersedes: none; failed global bound retained.
- Next dependency: Freeze one full scale fit and export parity, then separately allocate/freeze independent normalized-score calibration and confirmation. Keep pose weights, features, alpha and3mm research tolerance fixed. Report accepted-subset violations without claiming conditional coverage from marginal calibration.


### E-20260927-AI-311 — image-scale snapshot review

- Stage: S1
- Lane: AI
- Commit: `d5680841be29143c5fe0900c211f59c2a834c4f5` (source/features/plan frozen before rendering/fitting; report/tests/docs in successor)
- Inputs/fixtures:33000000..33000599, rectangle/ellipse x4conditions,600 scenes/4800 images. Five folds3840 fit/960 validation images; all8 variants grouped. Frozen pose artifact SHA256 c9f4ef6d8f9e50317a917154fccacce46506ab2e7cde8267396e28fec156147b. Source hashes in train/image_quality_scale_v1_plan.json; report SHA256 `9b58bf614dde9006056e3ac92f90a7213ff3d8d78ca109e5ea51e14842104c80` includes pixel/feature/prediction hashes, fold coefficients and all row errors/scales.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS:6221 paths,898.5MiB,0 unresolved findings,14 reviewed synthetic fixtures.
- Artifacts: vision/image_quality_scale.py; train/evaluate_image_quality_scale.py; train/image_quality_scale_v1_plan.json; eval/image_quality_scale_v1_report.json; tests/test_image_quality_scale.py; docs/IMAGE_DEPENDENT_UNCERTAINTY.md.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Five uncertainty-regressor fits, zero pose fits/calibration fits. Freshly allocated uncertainty-training data only; no untouched confirmation claim. Error-scale output is not confidence or an upper bound. Modest synthetic MSE improvement cannot establish useful acceptance or physical-camera behavior. Historical pose selection remains fixed. No calibrated qualification/runtime gate installed. Batch contract unchanged; shared boundary suite not triggered. Snapshot heuristic before final docs; existing pytest warning. Arm/integration statuses unchanged.
- Supersedes: none; failed global bound retained.
- Next dependency: Freeze one full scale fit and export parity, then separately allocate/freeze independent normalized-score calibration and confirmation. Keep pose weights, features, alpha and3mm research tolerance fixed. Report accepted-subset violations without claiming conditional coverage from marginal calibration.


### E-20260927-AI-312 — final image-scale fit and export

- Stage: S1
- Lane: AI
- Commit: `fc2ee94d35164321214dead7718d33e280813ee6` (frozen before fit; report/model committed with subsequent calibration source)
- Inputs/fixtures:33000000..33000599 x2styles x4conditions,4800 images. Feature SHA256539efe4b6762ec5024e96621e6262ae879d8e0d66e63e85a362bdc033fbb8cb8. Source/artifact hashes in train/image_scale_refit_v1_plan.json; frozen pose unchanged.
- Command: `python software/ai/train/refit_image_scale.py`
- Result: PASS:one full scale fit at alpha1.0;5328-byte export SHA256476a64054981226d63afe119d124188b1946cf9f8debbad83ae605d018fd8082. Exact JSON reload predictions; all4800 image-call/reference max delta2.220446049250313e-16mm (<1e-12).
- Artifacts: vision/image_scale_export.py; train/refit_image_scale.py; train/image_scale_refit_v1_plan.json; eval/image_scale_refit_v1_model.json and report.json.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Error scale only, no calibrated bound. Zero pose fits/calibration fits; no runtime promotion or qualification. Batch contract and arm/integration statuses unchanged.
- Supersedes: none.
- Next dependency: Independently frozen34000000..34000999 normalized-score calibration and35000000..35000999 confirmation; fixed3mm research gate and99% scene criterion.


### E-20260927-AI-313 — image-dependent uncertainty confirmation

- Stage: S1
- Lane: AI
- Commit: `642827db5a82fd66ac6fec7aa438a2dd8f36da32` (scale artifact and source/plan frozen before calibration/confirmation; report/tests/docs in successor)
- Inputs/fixtures:34000000..34000999 calibration and35000000..35000999 confirmation; each1000 scenes x4ellipse conditions. Pose SHA256 c9f4ef6d8f9e50317a917154fccacce46506ab2e7cde8267396e28fec156147b; scale SHA256476a64054981226d63afe119d124188b1946cf9f8debbad83ae605d018fd8082. Full source hashes in eval/scaled_uncertainty_v1_plan.json; report SHA256 `88519196d646f757c07d722653fe00a98e0c71b68efe681921d50f9b145006cd` includes all scores, errors, scales and pixel/prediction hashes.
- Command: `python software/ai/vision/evaluate_scaled_uncertainty.py`
- Result: FAIL utility:rank991 normalized quantile4.75657008897. Confirmation994/1000 scenes covered(99.4%;95% Wilson98.6972%–99.7247%),3986/4000 images covered(99.65%). Zero accepted images in every condition; zero accepted violations is vacuous. Scene coverage passes but nonzero-acceptance requirement fails.
- Artifacts: vision/evaluate_scaled_uncertainty.py; eval/scaled_uncertainty_v1_plan.json and report.json; tests/test_scaled_uncertainty.py; docs/IMAGE_DEPENDENT_UNCERTAINTY.md.
- Hardware writes: 0
- Physical movements: 0
- Limitations: One normalized-quantile calibration fit, zero pose/scale fits during confirmation. Both34M/35M ranges now consumed. Synthetic marginal coverage is not conditional accepted coverage or physical qualification. Different cohorts prohibit attributing coverage change versus prior global experiment to the scale alone. No tuning or threshold relaxation. Runtime baseline and ModelMotionBatchV2 unchanged; boundary tests not triggered; arm/integration status unchanged. Existing pytest warning; heuristic snapshot before final docs.
- Supersedes: none; failed global bound and zero-utility scaled bound retained.
- Next dependency: Training-only out-of-fold risk-ranking audit on33M evidence to test whether image statistics distinguish low-error cases before any further calibration. Do not tune on consumed31M/32M/34M/35M calibration or confirmation rows. Freeze pose/scale and preserve3mm research rule; no runtime installation.


### E-20260927-AI-314 — scale export and confirmation verification

- Stage: S1
- Lane: AI
- Commit: `642827db5a82fd66ac6fec7aa438a2dd8f36da32` (scale artifact and source/plan frozen before calibration/confirmation; report/tests/docs in successor)
- Inputs/fixtures:34000000..34000999 calibration and35000000..35000999 confirmation; each1000 scenes x4ellipse conditions. Pose SHA256 c9f4ef6d8f9e50317a917154fccacce46506ab2e7cde8267396e28fec156147b; scale SHA256476a64054981226d63afe119d124188b1946cf9f8debbad83ae605d018fd8082. Full source hashes in eval/scaled_uncertainty_v1_plan.json; report SHA256 `88519196d646f757c07d722653fe00a98e0c71b68efe681921d50f9b145006cd` includes all scores, errors, scales and pixel/prediction hashes.
- Command: `python -m pytest -q software/ai/tests/test_scaled_uncertainty.py`
- Result: PASS:4 tests in1.87s. Strict artifact rejection, image roundtrip, full-fit lineage, complete8000-row scene/condition accounting, disjoint calibration/confirmation, quantile/coverage recount and accepted-subset violations verified.
- Artifacts: vision/evaluate_scaled_uncertainty.py; eval/scaled_uncertainty_v1_plan.json and report.json; tests/test_scaled_uncertainty.py; docs/IMAGE_DEPENDENT_UNCERTAINTY.md.
- Hardware writes: 0
- Physical movements: 0
- Limitations: One normalized-quantile calibration fit, zero pose/scale fits during confirmation. Both34M/35M ranges now consumed. Synthetic marginal coverage is not conditional accepted coverage or physical qualification. Different cohorts prohibit attributing coverage change versus prior global experiment to the scale alone. No tuning or threshold relaxation. Runtime baseline and ModelMotionBatchV2 unchanged; boundary tests not triggered; arm/integration status unchanged. Existing pytest warning; heuristic snapshot before final docs.
- Supersedes: none; failed global bound and zero-utility scaled bound retained.
- Next dependency: Training-only out-of-fold risk-ranking audit on33M evidence to test whether image statistics distinguish low-error cases before any further calibration. Do not tune on consumed31M/32M/34M/35M calibration or confirmation rows. Freeze pose/scale and preserve3mm research rule; no runtime installation.


### E-20260927-AI-315 — scaled uncertainty snapshot audit

- Stage: S1
- Lane: AI
- Commit: `642827db5a82fd66ac6fec7aa438a2dd8f36da32` (scale artifact and source/plan frozen before calibration/confirmation; report/tests/docs in successor)
- Inputs/fixtures:34000000..34000999 calibration and35000000..35000999 confirmation; each1000 scenes x4ellipse conditions. Pose SHA256 c9f4ef6d8f9e50317a917154fccacce46506ab2e7cde8267396e28fec156147b; scale SHA256476a64054981226d63afe119d124188b1946cf9f8debbad83ae605d018fd8082. Full source hashes in eval/scaled_uncertainty_v1_plan.json; report SHA256 `88519196d646f757c07d722653fe00a98e0c71b68efe681921d50f9b145006cd` includes all scores, errors, scales and pixel/prediction hashes.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS:6231 paths,900.0MiB,0 unresolved findings,14 reviewed synthetic fixtures.
- Artifacts: vision/evaluate_scaled_uncertainty.py; eval/scaled_uncertainty_v1_plan.json and report.json; tests/test_scaled_uncertainty.py; docs/IMAGE_DEPENDENT_UNCERTAINTY.md.
- Hardware writes: 0
- Physical movements: 0
- Limitations: One normalized-quantile calibration fit, zero pose/scale fits during confirmation. Both34M/35M ranges now consumed. Synthetic marginal coverage is not conditional accepted coverage or physical qualification. Different cohorts prohibit attributing coverage change versus prior global experiment to the scale alone. No tuning or threshold relaxation. Runtime baseline and ModelMotionBatchV2 unchanged; boundary tests not triggered; arm/integration status unchanged. Existing pytest warning; heuristic snapshot before final docs.
- Supersedes: none; failed global bound and zero-utility scaled bound retained.
- Next dependency: Training-only out-of-fold risk-ranking audit on33M evidence to test whether image statistics distinguish low-error cases before any further calibration. Do not tune on consumed31M/32M/34M/35M calibration or confirmation rows. Freeze pose/scale and preserve3mm research rule; no runtime installation.


### E-20260927-AI-316 — training-only risk-ranking audit

- Stage: S1
- Lane: AI
- Commit: `ebc27f659e84b68283f436fbfc3093278e3cf881` (audit source/plan frozen before execution; report/tests/docs in successor)
- Inputs/fixtures: Saved33M600scene x8variant out-of-fold scale evidence only. Source/script hashes in eval/scale_ranking_v1_plan.json. Report SHA256 `5f89833ec39c20df60b1fbcd3e25d353116dbe1e7e8f837518a1bfbefac153c9`. All prior models frozen.
- Command: `python software/ai/vision/audit_scale_ranking.py`
- Result: PASS descriptive audit:4800images141tails,600scenes49tails. Image AUROC0.687362/Spearman0.226719; scene AUROC0.590133/Spearman0.191710. Lowest10% includes5/481 image tails and5/60 scene tails;25% includes9/150 scene tails. No useful scene separation established at lowest10%.
- Artifacts: vision/audit_scale_ranking.py; eval/scale_ranking_v1_plan.json and report.json; tests/test_scale_ranking.py; docs/IMAGE_DEPENDENT_UNCERTAINTY.md.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Zero fits/new images/calibration. Descriptive training-selection evidence, correlated variants, no statistical significance or physical claim. Fixed retention thresholds are diagnostics only, not runtime gates. Fold-constant ranks reflect fold intercept variation. No qualification or boundary changes; boundary tests not triggered. Existing pytest warning; arm/integration statuses unchanged.
- Supersedes: none; zero-utility bounds preserved.
- Next dependency: Freeze grouped33M comparison of512 frozen backbone features against56 image features at fixed alpha1.0; require every-condition MSE improvement and scene AUROC improvement before further calibration. Exclude consumed calibration/confirmation data from selection.


### E-20260927-AI-317 — ranking audit verification

- Stage: S1
- Lane: AI
- Commit: `ebc27f659e84b68283f436fbfc3093278e3cf881` (audit source/plan frozen before execution; report/tests/docs in successor)
- Inputs/fixtures: Saved33M600scene x8variant out-of-fold scale evidence only. Source/script hashes in eval/scale_ranking_v1_plan.json. Report SHA256 `5f89833ec39c20df60b1fbcd3e25d353116dbe1e7e8f837518a1bfbefac153c9`. All prior models frozen.
- Command: `python -m pytest -q software/ai/tests/test_scale_ranking.py`
- Result: PASS:3 tests in0.37s. AUROC orientation/ties, rank ties, retention tie inclusion, constant ranks, lineage and all condition/style/scene metric recounts verified.
- Artifacts: vision/audit_scale_ranking.py; eval/scale_ranking_v1_plan.json and report.json; tests/test_scale_ranking.py; docs/IMAGE_DEPENDENT_UNCERTAINTY.md.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Zero fits/new images/calibration. Descriptive training-selection evidence, correlated variants, no statistical significance or physical claim. Fixed retention thresholds are diagnostics only, not runtime gates. Fold-constant ranks reflect fold intercept variation. No qualification or boundary changes; boundary tests not triggered. Existing pytest warning; arm/integration statuses unchanged.
- Supersedes: none; zero-utility bounds preserved.
- Next dependency: Freeze grouped33M comparison of512 frozen backbone features against56 image features at fixed alpha1.0; require every-condition MSE improvement and scene AUROC improvement before further calibration. Exclude consumed calibration/confirmation data from selection.


### E-20260927-AI-318 — ranking audit snapshot review

- Stage: S1
- Lane: AI
- Commit: `ebc27f659e84b68283f436fbfc3093278e3cf881` (frozen source; evidence/docs in successor)
- Inputs/fixtures: Repository snapshot including33M ranking audit; exact source/report hashes recorded in AI-316 and eval/scale_ranking_v1_plan.json.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS:6235 paths,900.1MiB,0 unresolved findings,14 reviewed synthetic fixtures.
- Artifacts: eval/scale_ranking_v1_report.json; docs/IMAGE_DEPENDENT_UNCERTAINTY.md; shared ledger.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic snapshot before final ledger append, not model or physical assurance; no boundary/arm status changes.
- Supersedes: none.
- Next dependency: Frozen training-only512-feature versus56-feature uncertainty comparison, as specified in AI-316; no further calibration without improvement.


### E-20260927-AI-319 — frozen-backbone uncertainty comparison

- Stage: S1
- Lane: AI
- Commit: `6c3d0ccf5d12d0afd52e80b4cb75f086917f96d5` (source and plan frozen before feature extraction or fitting; report, tests, and documentation committed in the successor)
- Inputs/fixtures: Existing `33000000..33000599` uncertainty-training scenes, rectangle and ellipse styles, four conditions, 4,800 images, and the same five grouped scene folds. Frozen pose artifact SHA256 `c9f4ef6d8f9e50317a917154fccacce46506ab2e7cde8267396e28fec156147b`; reference report SHA256 `9b58bf614dde9006056e3ac92f90a7213ff3d8d78ca109e5ea51e14842104c80`. All source hashes are in `train/backbone_uncertainty_v1_plan.json`; report SHA256 `8d791d31a24918d875de0ecc833305145a4aa5a309730a100f7876079ec49491` retains fold fits and every out-of-fold prediction.
- Command: `python software/ai/train/compare_backbone_uncertainty.py`
- Result: FAIL fixed comparison. Backbone versus image-statistic log-error MSE: standard `0.227759 < 0.234846` and appearance shift `0.238840 < 0.246693`, but partial obstruction `0.234341 > 0.233817` and full obstruction `0.260045 > 0.254223`. Scene tail AUROC fell from `0.590133` to `0.562354`. The every-condition MSE and scene-ranking requirements both fail.
- Artifacts: `train/compare_backbone_uncertainty.py`; `train/backbone_uncertainty_v1_plan.json`; `eval/backbone_uncertainty_v1_report.json`; `tests/test_backbone_uncertainty.py`; `docs/IMAGE_DEPENDENT_UNCERTAINTY.md`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Five uncertainty fits, zero pose fits, calibration fits, or new images. Reuses uncertainty-training evidence and cannot support a fresh confirmation claim. Frozen backbone features can contain synthetic shortcuts. No threshold was chosen, no model was exported, and no runtime qualification was installed. ModelMotionBatchV2 and arm/integration statuses are unchanged.
- Supersedes: none; both zero-utility calibration results and the weak 56-feature ranking remain preserved.
- Next dependency: Stop simple linear uncertainty heads on the current representation. Specify a grouped, training-only uncertainty representation experiment that learns error-relevant features explicitly while freezing the confirmed pose output; require obstruction-condition and scene-ranking gains before spending new calibration data.


### E-20260927-AI-320 — backbone comparison verification

- Stage: S1
- Lane: AI
- Commit: `6c3d0ccf5d12d0afd52e80b4cb75f086917f96d5` (frozen evidence source; tests and documentation committed in the successor)
- Inputs/fixtures: Same 4,800 saved 33M uncertainty-training rows and frozen artifacts as AI-319; report SHA256 `8d791d31a24918d875de0ecc833305145a4aa5a309730a100f7876079ec49491`.
- Command: `python -m pytest -q software/ai/tests/test_backbone_uncertainty.py`
- Result: PASS: 3 tests in 2.07s. Tests verify fit-row isolation, input rejection, bounded predictions, scene maximum aggregation, complete 4,800-row population, disjoint grouped folds, fold-only fits, every condition MSE, scene rankings, frozen lineage, and the failed acceptance decision.
- Artifacts: `tests/test_backbone_uncertainty.py`; `eval/backbone_uncertainty_v1_report.json`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Existing pytest-asyncio configuration warning. Verification establishes reproducibility, not accuracy or physical assurance. Contract unchanged, so shared boundary tests were not triggered.
- Supersedes: none.
- Next dependency: Same as AI-319.


### E-20260927-AI-321 — backbone comparison snapshot review

- Stage: S1
- Lane: AI
- Commit: `6c3d0ccf5d12d0afd52e80b4cb75f086917f96d5` (frozen evidence source; final ledger append in successor)
- Inputs/fixtures: Repository snapshot containing the frozen comparison and its generated report; exact hashes recorded in AI-319.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS: 6,239 paths, 901.6 MiB, 0 unresolved review findings, 14 reviewed synthetic fixtures.
- Artifacts: `eval/backbone_uncertainty_v1_report.json`; `tests/test_backbone_uncertainty.py`; shared evidence ledger.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic repository review before the final ledger append; not model, runtime, or physical assurance. Arm and integration statuses remain unchanged.
- Supersedes: none.
- Next dependency: Same as AI-319.


### E-20260927-AI-322 — nonlinear uncertainty representation study

- Stage: S1
- Lane: AI
- Commit: `22c374ba8710427c4feb2ca5660aafcb3d90cd7d` (architecture, schedule, source, and plan frozen before fitting; report, tests, and documentation committed in the successor)
- Inputs/fixtures: Existing `33000000..33000599` uncertainty-training scenes, rectangle and ellipse styles, four conditions, 4,800 images, and five grouped scene folds. Frozen pose artifact SHA256 `c9f4ef6d8f9e50317a917154fccacce46506ab2e7cde8267396e28fec156147b`; reference report SHA256 `9b58bf614dde9006056e3ac92f90a7213ff3d8d78ca109e5ea51e14842104c80`. Fixed 16,689-parameter `512→32→8→1` GELU head; 30 epochs, batch 64, AdamW learning rate 0.001 and weight decay 0.0001, fold seeds 270927..270931. Full hashes in `train/nonlinear_uncertainty_v1_plan.json`; report SHA256 `b9ac4856d8af925d19d2e3b25e049c22f738590fba2deb7e52ff9fedc0fc0d4d` retains all states and predictions.
- Command: `python software/ai/train/evaluate_nonlinear_uncertainty.py`
- Result: FAIL fixed composite rule. Scene tail AUROC improves from `0.590133` to `0.644431`, but log-error MSE worsens in every condition: standard `0.234846→0.312227`, appearance shift `0.246693→0.263520`, partial `0.233817→0.336033`, full `0.254223→0.336248`. The ranking check passes, while all four scale-error checks fail.
- Artifacts: `vision/nonlinear_uncertainty.py`; `train/evaluate_nonlinear_uncertainty.py`; `train/nonlinear_uncertainty_v1_plan.json`; `eval/nonlinear_uncertainty_v1_report.json`; `tests/test_nonlinear_uncertainty.py`; `docs/IMAGE_DEPENDENT_UNCERTAINTY.md`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Five uncertainty-head fits, 9,000 optimizer updates total, zero pose/calibration fits or new images. One architecture and schedule, no sweep or early stopping. Reused synthetic uncertainty-training evidence; no confirmation claim. Improved ranking does not create a calibrated radius. No head export, threshold selection, runtime installation, or physical qualification. ModelMotionBatchV2 and arm/integration statuses unchanged.
- Supersedes: none; prior failed linear heads and zero-utility bounds remain preserved.
- Next dependency: Treat scale regression and tail-risk ranking as separate tasks. Specify one grouped training-only, class-balanced scene-tail classifier using the frozen descriptors, with fixed architecture/schedule and no threshold selection. Require materially better scene AUROC plus useful fixed-retention tail reduction before any calibration allocation.


### E-20260927-AI-323 — nonlinear uncertainty verification

- Stage: S1
- Lane: AI
- Commit: `22c374ba8710427c4feb2ca5660aafcb3d90cd7d` (frozen experiment source; tests and docs in successor)
- Inputs/fixtures: Same 4,800 grouped 33M rows and frozen artifacts as AI-322; report SHA256 `b9ac4856d8af925d19d2e3b25e049c22f738590fba2deb7e52ff9fedc0fc0d4d`.
- Command: `python -m pytest -q software/ai/tests/test_nonlinear_uncertainty.py`
- Result: PASS: 3 tests in 2.93s. Tests verify architecture and parameter count, strict inputs, deterministic training, training-row isolation, bounded inference, complete population and fold assignment, optimizer counts, all condition metrics, scene ranking, lineage, and the failed decision.
- Artifacts: `tests/test_nonlinear_uncertainty.py`; `eval/nonlinear_uncertainty_v1_report.json`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Existing pytest-asyncio configuration warning. Verification establishes reproducibility only. Contract unchanged; shared boundary suite not triggered.
- Supersedes: none.
- Next dependency: Same as AI-322.


### E-20260927-AI-324 — nonlinear uncertainty snapshot review

- Stage: S1
- Lane: AI
- Commit: `22c374ba8710427c4feb2ca5660aafcb3d90cd7d` (frozen experiment source; final ledger append in successor)
- Inputs/fixtures: Repository snapshot containing the nonlinear study and generated evidence; exact hashes recorded in AI-322.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS: 6,244 paths, 906.0 MiB, 0 unresolved review findings, 14 reviewed synthetic fixtures.
- Artifacts: `eval/nonlinear_uncertainty_v1_report.json`; `tests/test_nonlinear_uncertainty.py`; shared evidence ledger.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic repository review before final ledger append; not model or physical assurance. No arm or integration status changes.
- Supersedes: none.
- Next dependency: Same as AI-322.


### E-20260927-AI-325 — grouped scene-tail classifier study

- Stage: S1
- Lane: AI
- Commit: `a3609e8187b5e17995052b19b4c441dd2d10a797` (labels, architecture, class balance, schedule, source, and plan frozen before fitting; evidence/tests/docs committed in the successor)
- Inputs/fixtures: Existing `33000000..33000599` uncertainty-training scenes, eight variants each, 49 positive scenes with any error over 3 mm and 551 negative scenes. Frozen descriptor SHA256 `183a1780b4fcfb3fb908b021af08cab07a2662a0ef8fb9ae18abf42c8e2b05c8`; pose artifact SHA256 `c9f4ef6d8f9e50317a917154fccacce46506ab2e7cde8267396e28fec156147b`; source report SHA256 `b9ac4856d8af925d19d2e3b25e049c22f738590fba2deb7e52ff9fedc0fc0d4d`. Fixed 16,689-parameter classifier, fold-only normalization and class weighting, 30 epochs, batch 64, AdamW learning rate 0.001 and weight decay 0.0001. Full hashes in `train/tail_risk_classifier_v1_plan.json`; report SHA256 `8a6bf9c11ccb8ebb2f3ea8feadeec4d2f2b93684fba736fb6ee032981cb1059d` retains every fit and prediction.
- Command: `python software/ai/train/evaluate_tail_risk_classifier.py`
- Result: FAIL all fixed checks. Scene tail AUROC falls from the nonlinear-regression reference `0.644431` to `0.570540`. At 25% retention the classifier has `9/150` tails (6.0%) versus `4/150` (2.67%); at 50% it has `22/300` (7.33%) versus `17/300` (5.67%). Training weighted BCE reaches 0.0133..0.0367 while out-of-fold ranking worsens, consistent with overfitting but not a causal proof.
- Artifacts: `vision/tail_risk_classifier.py`; `train/evaluate_tail_risk_classifier.py`; `train/tail_risk_classifier_v1_plan.json`; `eval/tail_risk_classifier_v1_report.json`; `tests/test_tail_risk_classifier.py`; `docs/IMAGE_DEPENDENT_UNCERTAINTY.md`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Five classifier fits, 9,000 optimizer updates total, zero pose/calibration fits or new images. Scene labels are copied to correlated variants. Only 49 positive scenes and one fixed architecture/schedule. Probabilities are uncalibrated ranks. No threshold, export, runtime installation, or physical qualification. ModelMotionBatchV2 and arm/integration statuses unchanged.
- Supersedes: none; all prior failed uncertainty paths remain preserved.
- Next dependency: Do not fit another head on the same descriptors and 600 scenes. First audit a zero-fit, deployable geometric signal: baseline-versus-confirmed-candidate target disagreement on grouped 33M rows. Require scene-ranking and fixed-retention improvement before considering a larger ensemble or broader uncertainty-training dataset.


### E-20260927-AI-326 — scene-tail classifier verification

- Stage: S1
- Lane: AI
- Commit: `a3609e8187b5e17995052b19b4c441dd2d10a797` (frozen classifier source; tests and docs in successor)
- Inputs/fixtures: Same 4,800 rows, 600 grouped scenes, and frozen artifacts as AI-325; report SHA256 `8a6bf9c11ccb8ebb2f3ea8feadeec4d2f2b93684fba736fb6ee032981cb1059d`.
- Command: `python -m pytest -q software/ai/tests/test_tail_risk_classifier.py`
- Result: PASS: 3 tests in 2.98s. Tests verify architecture, deterministic class-balanced fitting, input rejection, bounded probabilities, exact scene labels and class counts, fold isolation, optimizer counts, class weights, complete population, scene rankings, fixed-retention comparisons, lineage, and the failed decision.
- Artifacts: `tests/test_tail_risk_classifier.py`; `eval/tail_risk_classifier_v1_report.json`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Existing pytest-asyncio configuration warning. Reproducibility only; no accuracy or physical assurance. Contract unchanged, so boundary tests were not triggered.
- Supersedes: none.
- Next dependency: Same as AI-325.


### E-20260927-AI-327 — scene-tail classifier snapshot review

- Stage: S1
- Lane: AI
- Commit: `a3609e8187b5e17995052b19b4c441dd2d10a797` (frozen classifier source; final ledger append in successor)
- Inputs/fixtures: Repository snapshot containing the classifier study and evidence; exact hashes recorded in AI-325.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS: 6,249 paths, 910.5 MiB, 0 unresolved review findings, 14 reviewed synthetic fixtures.
- Artifacts: `eval/tail_risk_classifier_v1_report.json`; `tests/test_tail_risk_classifier.py`; shared evidence ledger.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic snapshot before final ledger append; not model or physical assurance. No arm or integration status changes.
- Supersedes: none.
- Next dependency: Same as AI-325.


### E-20260927-AI-328 — frozen pose-disagreement audit

- Stage: S1
- Lane: AI
- Commit: `188f1425264fe773c17aa8f3f4a62d4433ad8fce` (score, comparison, source, and plan frozen before inference; evidence/tests/docs committed in the successor)
- Inputs/fixtures: Existing `33000000..33000599` grouped uncertainty-training scenes and 4,800 variants. Frozen original baseline is embedded in the confirmed residual artifact SHA256 `c9f4ef6d8f9e50317a917154fccacce46506ab2e7cde8267396e28fec156147b`; source report SHA256 `b9ac4856d8af925d19d2e3b25e049c22f738590fba2deb7e52ff9fedc0fc0d4d`. Score is maximum displacement over all 46 targets between baseline and candidate poses. Full hashes in `eval/pose_disagreement_v1_plan.json`; report SHA256 `43747f73ae0bf6fcb6ed8758f09dd84b0508cdce23fafc9659ddd1b10680d0a7` retains every score and prediction hash.
- Command: `python software/ai/vision/audit_pose_disagreement.py`
- Result: FAIL all fixed comparisons. Disagreement scene tail AUROC is `0.556317` versus `0.644431` reference. At 25% retention it keeps `12/150` failures (8.0%) versus `4/150` (2.67%); at 50% it keeps `22/300` (7.33%) versus `17/300` (5.67%). Lowest-disagreement 10% contains `5/60` failures, slightly worse than the full-scene rate. Candidate error recount matches prior evidence within the frozen 1e-9 mm tolerance.
- Artifacts: `vision/audit_pose_disagreement.py`; `eval/pose_disagreement_v1_plan.json` and report; `tests/test_pose_disagreement.py`; `docs/IMAGE_DEPENDENT_UNCERTAINTY.md`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Zero fits, new images, calibration, or threshold selection. Baseline and residual candidate share a backbone and are not a diverse ensemble. Training-only synthetic diagnostic; no independent confirmation or physical claim. No runtime installation or qualification. ModelMotionBatchV2 and arm/integration statuses unchanged.
- Supersedes: none; all negative uncertainty evidence remains preserved.
- Next dependency: Stop uncertainty work on correlated outputs from the current backbone. Define a broader uncertainty-training population and genuinely diverse compact pose ensemble, including independent initialization or architecture, before evaluating ensemble dispersion. Do not allocate new calibration/confirmation data until grouped training evidence shows useful failure ranking.


### E-20260927-AI-329 — pose-disagreement verification

- Stage: S1
- Lane: AI
- Commit: `188f1425264fe773c17aa8f3f4a62d4433ad8fce` (frozen diagnostic source; tests and docs in successor)
- Inputs/fixtures: Same 4,800 rows and frozen artifacts as AI-328; report SHA256 `43747f73ae0bf6fcb6ed8758f09dd84b0508cdce23fafc9659ddd1b10680d0a7`.
- Command: `python -m pytest -q software/ai/tests/test_pose_disagreement.py`
- Result: PASS: 2 tests in 1.89s. Tests verify zero/equal-pose and translated/rotated disagreement geometry, frozen lineage, complete population, source-error recount, nonnegative scores, scene ranking, fixed-retention comparisons, and the failed decision.
- Artifacts: `tests/test_pose_disagreement.py`; `eval/pose_disagreement_v1_report.json`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Existing pytest-asyncio configuration warning. Reproducibility only; no accuracy or physical assurance. Contract unchanged, so boundary tests were not triggered.
- Supersedes: none.
- Next dependency: Same as AI-328.


### E-20260927-AI-330 — pose-disagreement snapshot review

- Stage: S1
- Lane: AI
- Commit: `188f1425264fe773c17aa8f3f4a62d4433ad8fce` (frozen diagnostic source; final ledger append in successor)
- Inputs/fixtures: Repository snapshot containing the disagreement audit and evidence; exact hashes recorded in AI-328.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS: 6,253 paths, 912.0 MiB, 0 unresolved review findings, 14 reviewed synthetic fixtures.
- Artifacts: `eval/pose_disagreement_v1_report.json`; `tests/test_pose_disagreement.py`; shared evidence ledger.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic snapshot before final ledger append; not model or physical assurance. No arm or integration status changes.
- Supersedes: none.
- Next dependency: Same as AI-328.


### E-20260927-AI-331 — diverse compact pose ensemble study

- Stage: S1
- Lane: AI
- Commit: `cb22df8c3a2f7d1dc7c54b287a6a8ec3eebcd7a6` (architectures, populations, schedules, acceptance rule, source, and plan frozen before rendering or fitting; report, tests, and documentation committed in the successor)
- Inputs/fixtures: New training scenes `36000000..36001599` and disjoint development scenes `36001600..36001999`, rectangle and ellipse styles, and standard, appearance-shift, partial-obstruction, and full-obstruction conditions: 12,800 training images and 3,200 development images. Training pixel SHA256 `11b81f3dbd1c38e48ab57e2aac91870de80f17e3a091d97fd004cb9fad5aac5e`; development pixel SHA256 `840580d70cb5570188ab1727d43c30ae7c55ea9edecc894cab29a492222a159a`; frozen candidate SHA256 `c9f4ef6d8f9e50317a917154fccacce46506ab2e7cde8267396e28fec156147b`; plan SHA256 `2d6838e1820a34c3cb3ff5dab2a13701df0cddb0d13801b3c18f791a3d7fc0c8`; report SHA256 `161a077d71f3f9497dc2023fe7ef480317ce8756cba196ab36e56c5d5262db03`. The 172,331-parameter SiLU and 82,763-parameter separable models used fixed seeds, 12 epochs, and 2,400 total optimizer updates; checkpoint and prediction hashes are retained in the report.
- Command: `python software/ai/train/train_diverse_pose_ensemble.py`
- Result: FAIL fixed composite rule. Scene tail AUROC is `0.646260` versus required `0.70`. Overall development scene failure is `45/400` (11.25%); lowest-disagreement 10% has `0/40`, 25% has `6/100` (6.0%) and fails its <=5.625% requirement, and 50% has `15/200` (7.5%) and passes its <=8.4375% requirement. Both new members fail only the appearance-shift mean-error check: SiLU `1.676510` mm and separable `1.913844` mm versus candidate `0.831711` mm. No registered gate passes because the composite decision is false.
- Artifacts: `vision/diverse_pose_models.py`; `train/train_diverse_pose_ensemble.py`; `train/diverse_pose_ensemble_v1_plan.json`; `eval/diverse_pose_ensemble_v1_report.json`; ignored local checkpoints under `results/diverse_pose_ensemble_v1_*`; `tests/test_diverse_pose_ensemble.py`; `docs/IMAGE_DEPENDENT_UNCERTAINTY.md`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Two pose fits on a synthetic renderer, one fixed seed per architecture, CUDA training with possible nondeterminism, and one development cohort used for the decision. The zero-failure 10% subset is descriptive and not independent confirmation. Dispersion is uncalibrated. There is no threshold, export, runtime installation, physical-camera qualification, or motion authority. ModelMotionBatchV2 and arm/integration statuses are unchanged.
- Supersedes: none; correlated-disagreement, learned-head, and zero-utility calibration failures remain preserved.
- Next dependency: Do not tune against the consumed 36M development rows or allocate calibration data. Improve diverse-member appearance robustness on a newly allocated training/selection cohort, freeze the resulting architecture and schedule, then evaluate it once on fresh grouped development evidence with preregistered ranking and member-quality requirements.


### E-20260927-AI-332 — diverse ensemble verification

- Stage: S1
- Lane: AI
- Commit: `cb22df8c3a2f7d1dc7c54b287a6a8ec3eebcd7a6` (frozen experiment source; tests and documentation committed in the successor)
- Inputs/fixtures: Same 12,800 training images, 3,200 development images, frozen candidate, plan, checkpoints, and report as AI-331; exact hashes are retained there and in the generated report.
- Command: `python -m pytest -q software/ai/tests/test_diverse_pose_ensemble.py`
- Result: PASS: 3 tests in 1.78s. Tests verify both architecture parameter counts and strict inputs, pairwise target-displacement geometry, frozen hashes, exact scene populations, training history and optimizer counts, candidate metric recounts, scene aggregation and ranking, every fixed acceptance check, the failed composite decision, and zero hardware or physical authority.
- Artifacts: `tests/test_diverse_pose_ensemble.py`; `eval/diverse_pose_ensemble_v1_report.json`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Existing pytest-asyncio configuration warning. Verification establishes internal reproducibility, not accuracy, calibration, or physical assurance. Contract unchanged, so shared boundary tests were not triggered.
- Supersedes: none.
- Next dependency: Same as AI-331.


### E-20260927-AI-333 — diverse ensemble snapshot review

- Stage: S1
- Lane: AI
- Commit: `cb22df8c3a2f7d1dc7c54b287a6a8ec3eebcd7a6` (frozen experiment source; final ledger append in successor)
- Inputs/fixtures: Repository snapshot containing the frozen diverse-ensemble source, generated report, verification tests, and interpretation; exact hashes recorded in AI-331.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS: 6,258 paths, 914.0 MiB, 0 unresolved review findings, 14 reviewed synthetic fixtures.
- Artifacts: `eval/diverse_pose_ensemble_v1_report.json`; `tests/test_diverse_pose_ensemble.py`; `docs/IMAGE_DEPENDENT_UNCERTAINTY.md`; shared evidence ledger.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic repository review before the final ledger append; not model, runtime, or physical assurance. No arm or integration status changes.
- Supersedes: none.
- Next dependency: Same as AI-331.


### E-20260927-AI-334 — appearance-robust ensemble selection

- Stage: S1
- Lane: AI
- Commit: `98e9739d8c13495ac133d9632838198c90ac43ee` (training recipe, populations, selection rule, source, and plan frozen before rendering or fitting; report, tests, and documentation committed in the successor)
- Inputs/fixtures: New training scenes `37000000..37002399` and disjoint selection scenes `37002400..37002799`, rectangle and ellipse styles, and four conditions: 19,200 training images and 3,200 selection images. Appearance-shift samples have fixed loss weight 2.0; all others 1.0. Training pixel SHA256 `c4460f62e30941c0dd20ff5c2793f6a9295929f377c7fd64761ad90c682bcb80`; selection pixel SHA256 `760db131855cbdbf8532090cf5e9c4ddf6e77caf0c2b0e40c8893df9ac3c2048`; training-weight SHA256 `d6303f3369d6a2efb9c0c6780b747f324de752ea64898742e265712e0468cb6e`; plan SHA256 `8698a55675e19d5dab113c43e1ffec71c5ddaff2b40e61f2556a3efbd3b1c5a8`; report SHA256 `17815b1d24e593812a87d9b88257578722712bd0afc7d51e5d6b3be484aa9702`. Frozen candidate and previous report hashes are retained in the plan. SiLU checkpoint SHA256 `22ac55a2c869a0aaac8f1c03364cd2f05456c492e10fd4825a58f8727d0b425b`; separable checkpoint SHA256 `7236e5a4a25d3465bbac07ff6d41e3dc43508ee765a77e67f59c7bd0bc558dea`.
- Command: `python software/ai/train/train_appearance_robust_ensemble.py`
- Result: PASS fixed selection rule. Scene tail AUROC `0.717287` exceeds `0.68`. Overall selection failure is `38/400` (9.5%); 25% retention has `4/100` (4.0%) and 50% has `10/200` (5.0%), passing both relative reductions. SiLU and separable appearance means are `1.298275` mm and `1.483910` mm versus candidate `0.878960` mm, passing the fixed 1.8-times limit. Every all-condition two-times member check passes. Two pose fits and 7,200 optimizer updates were performed.
- Artifacts: `train/train_appearance_robust_ensemble.py`; `train/appearance_robust_ensemble_v1_plan.json`; `eval/appearance_robust_ensemble_v1_report.json`; ignored local checkpoints under `results/appearance_robust_ensemble_v1_*`; `tests/test_appearance_robust_ensemble.py`; `docs/IMAGE_DEPENDENT_UNCERTAINTY.md`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Synthetic renderer only, one seed per architecture, CUDA nondeterminism may remain, and selection evidence is used only for go/no-go. It is not independent development, confirmation, calibrated uncertainty, runtime admission, or physical qualification. ModelMotionBatchV2 and arm/integration statuses are unchanged.
- Supersedes: none; the failed first diverse-ensemble result and all prior negative uncertainty evidence remain preserved.
- Next dependency: Freeze the exact two selected checkpoint hashes and evaluate them once on a new grouped development cohort. Require scene AUROC at least 0.70, the same fixed-retention reductions, and the same member-quality limits. Do not allocate calibration data until that fresh development rule passes.


### E-20260927-AI-335 — appearance-robust ensemble verification

- Stage: S1
- Lane: AI
- Commit: `98e9739d8c13495ac133d9632838198c90ac43ee` (frozen study source; tests and documentation committed in the successor)
- Inputs/fixtures: Same 19,200 training images, 3,200 selection images, frozen candidate, plan, and selected checkpoints as AI-334; exact hashes are recorded there and in the report.
- Command: `python -m pytest -q software/ai/tests/test_appearance_robust_ensemble.py`
- Result: PASS: 2 tests in 1.77s. Tests verify frozen lineage, disjoint grouped allocations, fixed condition weights, exact populations, training histories and optimizer counts, candidate metric recounts, scene aggregation and ranking, every registered selection check, the passing composite decision, and zero hardware or physical authority.
- Artifacts: `tests/test_appearance_robust_ensemble.py`; `eval/appearance_robust_ensemble_v1_report.json`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Existing pytest-asyncio configuration warning. Verification establishes internal reproducibility, not physical accuracy or calibrated uncertainty. Contract unchanged, so shared boundary tests were not triggered.
- Supersedes: none.
- Next dependency: Same as AI-334.


### E-20260927-AI-336 — appearance-robust selection snapshot review

- Stage: S1
- Lane: AI
- Commit: `98e9739d8c13495ac133d9632838198c90ac43ee` (frozen study source; final ledger append in successor)
- Inputs/fixtures: Repository snapshot containing the frozen appearance-robust study, generated report, tests, and interpretation; exact hashes recorded in AI-334.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS: 6,262 paths, 915.9 MiB, 0 unresolved review findings, 14 reviewed synthetic fixtures.
- Artifacts: `eval/appearance_robust_ensemble_v1_report.json`; `tests/test_appearance_robust_ensemble.py`; `docs/IMAGE_DEPENDENT_UNCERTAINTY.md`; shared evidence ledger.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic repository review before final ledger append; not model, runtime, or physical assurance. No arm or integration status changes.
- Supersedes: none.
- Next dependency: Same as AI-334.


### E-20260927-AI-337 — fresh appearance-robust development gate

- Stage: S1
- Lane: AI
- Commit: `66596ec1afd061588178aaa1c0538feba5bbd2fa` (checkpoint hashes, 38M population, decision rule, source, and plan frozen before rendering or inference; report, tests, and documentation committed in the successor)
- Inputs/fixtures: Selected SiLU checkpoint SHA256 `22ac55a2c869a0aaac8f1c03364cd2f05456c492e10fd4825a58f8727d0b425b`; separable checkpoint SHA256 `7236e5a4a25d3465bbac07ff6d41e3dc43508ee765a77e67f59c7bd0bc558dea`; frozen candidate SHA256 `c9f4ef6d8f9e50317a917154fccacce46506ab2e7cde8267396e28fec156147b`; selection report SHA256 `17815b1d24e593812a87d9b88257578722712bd0afc7d51e5d6b3be484aa9702`. Fresh scenes `38000000..38000999`, two styles, and four conditions total 8,000 images; development pixel SHA256 `1dd89bb56e6462c906ba322929e50e3a9e5ddc96642be45fdd7b522feb0a8ae1`; plan SHA256 `5f195d4d43c72f75094a8c2104d48617f3f6876f088227e489a89b7ba1276e31`; report SHA256 `1356b89880c06f84be3a7d83a5fc42d0bc3b07406f16b4664f1673f7528acdf8`. Prediction hashes for all three models are retained in the report.
- Command: `python software/ai/vision/evaluate_appearance_robust_ensemble.py`
- Result: PASS every fixed development check. Scene tail AUROC `0.725281` exceeds `0.70`. Overall failure is `84/1000` scenes (8.4%); 25% retention has `7/250` (2.8%) and 50% has `23/500` (4.6%), passing both relative reductions. SiLU and separable appearance means are `1.221354` mm and `1.366111` mm versus candidate `0.839518` mm; every appearance and all-condition member-quality check passes. Zero fits or optimizer updates.
- Artifacts: tracked selected checkpoints under `results/appearance_robust_ensemble_v1_*`; `vision/evaluate_appearance_robust_ensemble.py`; development plan and report under `eval/`; `tests/test_appearance_robust_ensemble_development.py`; `docs/IMAGE_DEPENDENT_UNCERTAINTY.md`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Fresh grouped synthetic development evidence from the same renderer; no physical-camera evidence. Disagreement remains an uncalibrated rank, with no metric radius or runtime threshold. Passing permits only a separately frozen calibration and confirmation chain. No runtime installation, physical qualification, or motion authority. ModelMotionBatchV2 and arm/integration statuses are unchanged.
- Supersedes: none; all earlier failed uncertainty and ensemble evidence remains preserved.
- Next dependency: Freeze a monotonic disagreement-to-error scale, independent scene-grouped calibration and confirmation ranges, finite-sample coverage target, and nonzero utility rule before viewing either cohort. Retain the 3 mm research tolerance and preserve failure without tuning.


### E-20260927-AI-338 — fresh development verification

- Stage: S1
- Lane: AI
- Commit: `66596ec1afd061588178aaa1c0538feba5bbd2fa` (frozen evaluation source; tests and documentation committed in the successor)
- Inputs/fixtures: Same 8,000 fresh 38M images, three frozen model artifacts, plan, and report as AI-337; exact hashes are recorded there and in the report.
- Command: `python -m pytest -q software/ai/tests/test_appearance_robust_ensemble_development.py`
- Result: PASS: 2 tests in 1.93s. Tests verify frozen checkpoint lineage, fresh development-only scope, exact grouped population, candidate score recounts, scene aggregation and ranking, every fixed acceptance check, the passing composite decision, and zero fit, hardware, or physical authority.
- Artifacts: `tests/test_appearance_robust_ensemble_development.py`; `eval/appearance_robust_ensemble_development_v1_report.json`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Existing pytest-asyncio configuration warning. Verification establishes internal reproducibility, not calibrated uncertainty or physical accuracy. Contract unchanged, so shared boundary tests were not triggered.
- Supersedes: none.
- Next dependency: Same as AI-337.


### E-20260927-AI-339 — fresh development snapshot review

- Stage: S1
- Lane: AI
- Commit: `66596ec1afd061588178aaa1c0538feba5bbd2fa` (frozen evaluation source; final ledger append in successor)
- Inputs/fixtures: Repository snapshot containing the tracked selected checkpoints, frozen fresh-development plan and source, generated report, tests, and interpretation; exact hashes recorded in AI-337.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS: 6,268 paths, 921.6 MiB, 0 unresolved review findings, 14 reviewed synthetic fixtures.
- Artifacts: selected checkpoints; fresh development plan/report; verification test; uncertainty documentation; shared evidence ledger.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic repository review before final ledger append; not model, runtime, or physical assurance. No arm or integration status changes.
- Supersedes: none.
- Next dependency: Same as AI-337.


### E-20260927-AI-340 — ensemble-scale calibration and confirmation

- Stage: S1
- Lane: AI
- Commit: `42d57f6afe17758e9223798568a56eff6f91fe18` (scale formula, finite-sample rule, both populations, coverage and utility checks, source, and plan frozen before rendering either cohort; report, tests, and documentation committed in the successor)
- Inputs/fixtures: Tracked candidate and selected ensemble checkpoints with hashes frozen in the plan; development report SHA256 `1356b89880c06f84be3a7d83a5fc42d0bc3b07406f16b4664f1673f7528acdf8`. Calibration scenes `39000000..39000999` and confirmation scenes `40000000..40000999`, each with two styles and four conditions for 8,000 images. Calibration pixel SHA256 `f2f8a1ee8a791a10bad9c6ce4a059e820ec3d4211d937931a731ead4f09428bf`; confirmation pixel SHA256 `3dd3d60ad373492b44685731f7859806a30590e3dc88bacc1115b4adb2b8020d`; plan SHA256 `6cde5b1ad69692dadf4340a6b8974704af13926722bb4be29d5fcd792f527aa7`; report SHA256 `401813be12e9c5fece909f70d04825c63cb62dd9fc46d167b613bc07cd6c7f0f`. All six prediction hashes are retained in the report.
- Command: `python software/ai/vision/evaluate_ensemble_scaled_uncertainty.py`
- Result: FAIL fixed composite rule. The rank-991 99% calibration quantile is `2.865444`. Confirmation marginal scene coverage passes at `994/1000` (99.4%). Accepted utility is `353/8000` (4.4125%), below 5%. Accepted coverage is `352/353` images (99.7167%) and `137/138` scenes (99.2754%), but one accepted partial-obstruction image exceeds both its bound and 3 mm; partial accepted coverage is `62/63` (98.4127%), below 99%. Overall utility, zero accepted errors over tolerance, and partial conditional coverage checks fail. All condition utility checks pass.
- Artifacts: `vision/evaluate_ensemble_scaled_uncertainty.py`; `eval/ensemble_scaled_uncertainty_v1_plan.json`; `eval/ensemble_scaled_uncertainty_v1_report.json`; `tests/test_ensemble_scaled_uncertainty.py`; `docs/IMAGE_DEPENDENT_UNCERTAINTY.md`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: One quantile calibration and zero model fits or optimizer updates. Synthetic marginal and accepted-subset coverage do not establish physical safety. The 3 mm research tolerance is not a measured contact margin. Both ranges are consumed. No threshold change, runtime installation, ModelMotionBatch qualification, physical qualification, or motion authority. Arm/integration statuses are unchanged.
- Supersedes: none; the prior zero-utility scale failure and all negative evidence remain preserved.
- Next dependency: Do not weaken the 5% utility or accepted-subset rules against this result. Use a new training-selection cohort to compare a small preregistered family of monotonic disagreement mappings, including partial-obstruction performance, before allocating another calibration and confirmation pair.


### E-20260927-AI-341 — ensemble-scale verification

- Stage: S1
- Lane: AI
- Commit: `42d57f6afe17758e9223798568a56eff6f91fe18` (frozen calibration source; tests and documentation committed in the successor)
- Inputs/fixtures: Same 16,000 images across independent calibration and confirmation cohorts, tracked frozen models, plan, and report as AI-340; exact hashes are recorded there and in the report.
- Command: `python -m pytest -q software/ai/tests/test_ensemble_scaled_uncertainty.py`
- Result: PASS: 2 tests in 1.91s. Tests verify summary accounting, frozen lineage, exact grouped populations, scale-floor computation, scene-score and rank-991 quantile recounts, overall and per-condition confirmation summaries, every registered check, the failed composite decision, and zero model, hardware, or physical authority.
- Artifacts: `tests/test_ensemble_scaled_uncertainty.py`; `eval/ensemble_scaled_uncertainty_v1_report.json`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Existing pytest-asyncio configuration warning. Verification establishes internal recount consistency, not calibrated physical safety. Contract unchanged, so shared boundary tests were not triggered.
- Supersedes: none.
- Next dependency: Same as AI-340.


### E-20260927-AI-342 — ensemble-scale snapshot review

- Stage: S1
- Lane: AI
- Commit: `42d57f6afe17758e9223798568a56eff6f91fe18` (frozen calibration source; final ledger append in successor)
- Inputs/fixtures: Repository snapshot containing the frozen calibration/confirmation plan and source, generated report, tests, and interpretation; exact hashes recorded in AI-340.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS: 6,272 paths, 925.3 MiB, 0 unresolved review findings, 14 reviewed synthetic fixtures.
- Artifacts: ensemble-scale plan/report; verification test; uncertainty documentation; shared evidence ledger.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic repository review before final ledger append; not model, runtime, or physical assurance. No arm or integration status changes.
- Supersedes: none.
- Next dependency: Same as AI-340.


### E-20260927-AI-343 — monotonic ensemble-scale mapping selection

- Stage: S1
- Lane: AI
- Commit: `348f519ae5fe18d270ba578e07fb3b3b5eecc1b2` (mapping family, two populations, quantile, checks, winner rule, source, and plan frozen before rendering or inference; report, tests, and documentation committed in the successor)
- Inputs/fixtures: Fixed powers `1.0, 1.25, 1.5, 1.75, 2.0`; mapping-calibration scenes `41000000..41000999` and disjoint selection scenes `42000000..42000999`, each with two styles and four conditions for 8,000 images. Mapping-calibration pixel SHA256 `cf94d0380a8765a27bbb0fbaae886da448191546a131d0d8046ba32cec1fb9f5`; selection pixel SHA256 `eacfbd41068cf380f26570f70a669168b1662ee715df3ccd337988adca5e01c1`; failed confirmation report SHA256 `401813be12e9c5fece909f70d04825c63cb62dd9fc46d167b613bc07cd6c7f0f`; plan SHA256 `afe4e0ce83827bae568ce17a99cba13a6728e0592ab403538deedad0fe17eb47`; report SHA256 `be52be07051648b7d0fdafb243a9690add5524f4b90ffd800df2763bb26a5042`. Model prediction hashes for both cohorts are retained in the report.
- Command: `python software/ai/train/select_ensemble_scale_mapping.py`
- Result: FAIL fixed selection rule; no mapping selected. The linear mapping has 99.2% scene coverage and `935/8000` accepted images (11.6875%), but accepts six images above 3 mm, accepted-scene coverage is `295/298` (98.9933%), and partial/full conditional image coverage fails. Powers 1.25, 1.5, 1.75, and 2.0 accept 11.35%, 10.1875%, 11.1875%, and 9.625%; each accepts the same six above-tolerance errors and fails accepted-subset coverage. Powers 1.75 and 2.0 also fail marginal scene coverage. Five quantile calibrations, zero model fits or optimizer updates.
- Artifacts: `train/select_ensemble_scale_mapping.py`; `train/ensemble_scale_mapping_v1_plan.json`; `eval/ensemble_scale_mapping_v1_report.json`; `tests/test_ensemble_scale_mapping.py`; `docs/IMAGE_DEPENDENT_UNCERTAINTY.md`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Training-only synthetic mapping selection using shared cohorts across five preregistered candidates. No selected map, fresh calibration, confirmation, runtime threshold, physical-camera evidence, or motion authority. ModelMotionBatchV2 and arm/integration statuses are unchanged.
- Supersedes: none; failed ensemble calibration and earlier failures remain preserved.
- Next dependency: Stop scalar monotonic remapping of current disagreement. Add a deployable obstruction-sensitive observable and require improved partial/full accepted-subset ranking on new grouped training-selection evidence before another calibration allocation.


### E-20260927-AI-344 — monotonic mapping verification

- Stage: S1
- Lane: AI
- Commit: `348f519ae5fe18d270ba578e07fb3b3b5eecc1b2` (frozen selection source; tests and documentation committed in the successor)
- Inputs/fixtures: Same 16,000 images, five mappings, frozen models, plan, and report as AI-343; exact hashes are recorded there and in the report.
- Command: `python -m pytest -q software/ai/tests/test_ensemble_scale_mapping.py`
- Result: PASS: 2 tests in 2.57s. Tests verify monotonic power/floor behavior, frozen lineage, exact grouped populations, every rank-991 quantile, overall and per-condition summaries and checks for all five mappings, deterministic no-selection outcome, and zero model, hardware, or physical authority.
- Artifacts: `tests/test_ensemble_scale_mapping.py`; `eval/ensemble_scale_mapping_v1_report.json`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Existing pytest-asyncio configuration warning. Verification establishes recount consistency, not physical safety. Contract unchanged, so shared boundary tests were not triggered.
- Supersedes: none.
- Next dependency: Same as AI-343.


### E-20260927-AI-345 — monotonic mapping snapshot review

- Stage: S1
- Lane: AI
- Commit: `348f519ae5fe18d270ba578e07fb3b3b5eecc1b2` (frozen selection source; final ledger append in successor)
- Inputs/fixtures: Repository snapshot containing the frozen mapping study, generated report, tests, and interpretation; exact hashes recorded in AI-343.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS: 6,276 paths, 929.5 MiB, 0 unresolved review findings, 14 reviewed synthetic fixtures.
- Artifacts: mapping plan/report; verification test; uncertainty documentation; shared evidence ledger.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic repository review before final ledger append; not model, runtime, or physical assurance. No arm or integration status changes.
- Supersedes: none.
- Next dependency: Same as AI-343.


### E-20260927-AI-346 — image-only obstruction-risk scale study

- Stage: S1
- Lane: AI
- Commit: `7c27ffc4ef32a6d4bbd4c8d8a2a8a845126fd6c6` (classifier, cohorts, combined scale, thresholds, source, and plan frozen before training; report, tests, and documentation committed in the successor)
- Inputs/fixtures: Training scenes `43000000..43001999` (16,000 raw images), mapping-calibration scenes `44000000..44000999`, and selection scenes `45000000..45000999` (8,000 images each). Training pixel SHA256 `9d4fa2aefd9f00ba724b3740d55e1cfb72f342907895169dabf782aab1232162`; mapping raw-pixel SHA256 `6c7c16ab667af4e39a7d0d4af3dbbaae63939701875440e349021ab9ce42741c`; selection raw-pixel SHA256 `f8255ddc90a795dc6a8b3410d9a1ae8814877787e871e571c0d240c4bc9f6b94`; plan SHA256 `3cd9f8ca6d2a93f39bb295c2c73e0401785b82c7a16dc4950f4ee4fd1254b49c`; report SHA256 `6b4bd12ea0b6830028847ab79e10de97912c84425a3ae18c621ab2ad06996529`; 69,561-parameter checkpoint SHA256 `fcfdb42a6665816e02828f884e7d61bf15476d963f4846b992bdaa19c93a3e1d`.
- Command: `python software/ai/train/train_obstruction_risk_scale.py`
- Result: FAIL fixed composite rule. Classifier AUROC `0.91947`, obstruction recall `0.78625`, and clean false-positive rate `0.124` miss required `0.95`, `0.90`, and `<=0.10`. Combined scale reaches 99.3% scene coverage, `1014/8000` utility (12.675%), 99.6055% accepted-image coverage, 99.4764% accepted-scene coverage, and zero accepted errors above 3 mm. Full-obstruction accepted coverage is `21/23` (91.3043%), failing its 99% condition rule; all other scale checks pass. One classifier fit, one quantile calibration, and 2,000 optimizer updates.
- Artifacts: `vision/obstruction_risk_model.py`; `train/train_obstruction_risk_scale.py`; `train/obstruction_risk_scale_v1_plan.json`; `eval/obstruction_risk_scale_v1_report.json`; ignored local classifier checkpoint; `tests/test_obstruction_risk_scale.py`; uncertainty documentation.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Synthetic training-selection evidence, one classifier seed, and no fresh confirmation or physical-camera claim. No classifier promotion, runtime installation, physical qualification, or motion authority. ModelMotionBatchV2 and arm/integration statuses are unchanged.
- Supersedes: none; failed scalar mappings and calibration evidence remain preserved.
- Next dependency: Improve full-obstruction recall using a preregistered localized or multi-scale image-only architecture on new grouped training-selection evidence. Retain the same classifier, conditional-coverage, utility, and 3 mm rules before another calibration pair.


### E-20260927-AI-347 — obstruction-risk verification

- Stage: S1
- Lane: AI
- Commit: `7c27ffc4ef32a6d4bbd4c8d8a2a8a845126fd6c6` (frozen study source; tests and documentation committed in the successor)
- Inputs/fixtures: Same 32,000 images across training, mapping-calibration, and selection cohorts as AI-346; exact model, pixel, plan, and report hashes recorded there.
- Command: `python -m pytest -q software/ai/tests/test_obstruction_risk_scale.py`
- Result: PASS: 2 tests in 1.77s. Tests verify architecture size and strict input, frozen lineage, exact grouped populations, combined-scale construction, all decision checks, failed selection, and zero hardware or physical authority.
- Artifacts: `tests/test_obstruction_risk_scale.py`; `eval/obstruction_risk_scale_v1_report.json`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Existing pytest-asyncio configuration warning. Recount consistency only; no physical assurance. Contract unchanged, so shared boundary tests were not triggered.
- Supersedes: none.
- Next dependency: Same as AI-346.

### E-20260927-AI-348 — obstruction-risk snapshot review

- Stage: S1
- Lane: AI
- Commit: `7c27ffc4ef32a6d4bbd4c8d8a2a8a845126fd6c6` (frozen study source; final ledger append in successor)
- Inputs/fixtures: Repository snapshot containing the frozen obstruction-risk study, report, tests, and interpretation; exact hashes recorded in AI-346.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS: 6,281 paths, 934.4 MiB, 0 unresolved review findings, 14 reviewed synthetic fixtures.
- Artifacts: obstruction-risk plan/report; verification test; uncertainty documentation; shared ledger.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic repository review; not model, runtime, or physical assurance. No arm or integration status changes.
- Supersedes: none.
- Next dependency: Same as AI-346.

### E-20260927-AI-349 — localized multi-scale obstruction-scale study

- Stage: S1
- Lane: AI
- Commit: `6f4510a513bb02750c326e394401c3ae6c399def` (architecture, training recipe, cohorts, fixed scale, thresholds, source, and plan frozen before training; report, checkpoint, tests, and documentation committed in the successor)
- Inputs/fixtures: Training scenes `46000000..46001999` (16,000 raw images), mapping-calibration scenes `47000000..47000999`, and selection scenes `48000000..48000999` (8,000 images each). Training pixel SHA256 `133e6028663a2097829c174017c0523b5269a58a675ad88812ac3bebeed4f124`, label SHA256 `fcc0c7ad06ec8e99b61072e8c255520fbde97b126c87a3655fe4912ac7940404`, and weight SHA256 `307797f0af6ce029cddf368d67043a7a864592976bcc7345f96bcc43e75354b3`; mapping raw-pixel SHA256 `b152169730b3cca7fabd38d33d86c890de8803a2fe97c492857a08e250ca9a90`; selection raw-pixel SHA256 `d9564dfeee96d082ce3523336742c6ccb9696753aa4b39e8746410786fd53475`; plan SHA256 `5f479b9d1f8a5edfd1bcd2ff027a31eeefc1d09591f1e2be244b09f4e4e44d4d`; report SHA256 `d40396a5cfbb66aa200f6c400b7ae560dfb3d5d8538e64f32d6a5d2f4fb24e78`; 34,381-parameter checkpoint SHA256 `96cc444276e9d9f35d0ed722891dc3eab2a7a1502960ed36df18ce17236200d9`. Pose and obstruction prediction hashes are retained in the report.
- Command: `python software/ai/train/train_multiscale_obstruction_scale.py`
- Result: FAIL fixed composite rule after one classifier fit, one rank-991 calibration, and 3,000 optimizer updates. The classifier passes: AUROC `0.995723625`, obstruction recall `0.97875`, and clean false-positive rate `0.013`. The quantile is `1.7034787433390106`. Selection scene coverage is 98.3%; utility is `1572/8000` (19.65%); accepted-image coverage is 98.6641%; accepted-scene coverage is 98.0322%; and zero accepted errors exceed 3 mm. Partial/full utility fails at `7/2000` and `5/2000`; full accepted-image coverage is `4/5`. Standard and appearance accepted coverage also miss 99%. No scale or qualification selected.
- Artifacts: `vision/multiscale_obstruction_model.py`; `train/train_multiscale_obstruction_scale.py`; `train/multiscale_obstruction_scale_v1_plan.json`; `eval/multiscale_obstruction_scale_v1_report.json`; `results/multiscale_obstruction_scale_v1/model.pt`; `tests/test_multiscale_obstruction_scale.py`; `docs/IMAGE_DEPENDENT_UNCERTAINTY.md`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Synthetic training-selection evidence, one seed, and no fresh confirmation or physical-camera claim. The retained checkpoint is a research input only. No mapping promotion, runtime installation, physical qualification, or motion authority. ModelMotionBatchV2 and arm/integration statuses are unchanged.
- Supersedes: none; the earlier classifier and every failed uncertainty mapping remain preserved.
- Next dependency: Freeze a small family of probability/disagreement mappings or acceptance rules, keep this classifier checkpoint fixed, and make one selection on new grouped mapping-calibration and selection cohorts. Retain all conditional coverage, utility, and 3 mm rules before allocating confirmation evidence.

### E-20260927-AI-350 — localized multi-scale obstruction verification

- Stage: S1
- Lane: AI
- Commit: `6f4510a513bb02750c326e394401c3ae6c399def` (frozen study source; tests and documentation committed in the successor)
- Inputs/fixtures: Same 32,000 images, frozen pose models, compact classifier, plan, and report as AI-349; exact hashes are recorded there and in the report.
- Command: `python -m pytest -q software/ai/tests/test_multiscale_obstruction_scale.py`
- Result: PASS: 2 tests in 1.81s. Tests verify the strict compact architecture, frozen lineage, exact grouped populations, scale floor, classifier checks, every composite decision check, the failed selection, and zero hardware or physical authority.
- Artifacts: `tests/test_multiscale_obstruction_scale.py`; `eval/multiscale_obstruction_scale_v1_report.json`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Existing pytest-asyncio configuration warning. Recount consistency only; no physical assurance. Contract unchanged, so shared boundary tests were not triggered.
- Supersedes: none.
- Next dependency: Same as AI-349.

### E-20260927-AI-351 — localized multi-scale snapshot review

- Stage: S1
- Lane: AI
- Commit: `6f4510a513bb02750c326e394401c3ae6c399def` (frozen study source; final ledger append in successor)
- Inputs/fixtures: Repository snapshot containing the frozen study, generated report, retained research checkpoint, tests, interpretation, and shared evidence ledger; exact hashes recorded in AI-349.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS: 6,286 paths, 939.3 MiB, 0 unresolved review findings, 14 reviewed synthetic fixtures.
- Artifacts: multi-scale plan/report/checkpoint; verification test; uncertainty documentation; shared ledger.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic repository review before final ledger append; not model, runtime, or physical assurance. No arm or integration status changes.
- Supersedes: none.
- Next dependency: Same as AI-349.

### E-20260927-AI-352 — frozen obstruction-probability mapping selection

- Stage: S1
- Lane: AI
- Commit: `bd51f17b44dfbae07c862988b79a36c437e2a2c2` (four gains, two populations, finite-sample rule, checks, winner rule, source, plan, and active claim frozen before inference; report, tests, interpretation, and claim removal committed in the successor)
- Inputs/fixtures: Frozen 34,381-parameter classifier SHA256 `96cc444276e9d9f35d0ed722891dc3eab2a7a1502960ed36df18ce17236200d9`; prior report SHA256 `d40396a5cfbb66aa200f6c400b7ae560dfb3d5d8538e64f32d6a5d2f4fb24e78`; gains `0.05, 0.075, 0.10, 0.125`; mapping-calibration scenes `49000000..49000999` and selection scenes `50000000..50000999`, each with two styles and four conditions for 8,000 images. Mapping raw-pixel SHA256 `b7334c7392575b830305f3c0e6348677117cd381de6fc8594efe2cae55a00129` and obstruction-prediction SHA256 `67afabd28d785e62414d6c46542ec7c9f09b640dd8e384b2de80f57f370ec29e`; selection raw-pixel SHA256 `f4e568831b117874777d65501299fdae87cc2db123bae21ee396150e23dc5f2e` and obstruction-prediction SHA256 `2c31b3f87d088866c766cded856ce4757fd21343cecb020ddad3339b4293c0d6`; plan SHA256 `6b55cabb6bbc904e32a5ddb863db68a8860cdb830b4184d0e64abd0de600bf9e`; report SHA256 `1b5a65b5e46acc9350f3a1595c7ee82a8efeb6f12bd9c09372085629f485abe6`. Pose prediction hashes are retained in the report.
- Command: `python software/ai/train/select_multiscale_obstruction_mapping.py`
- Result: FAIL fixed selection rule; no mapping selected. All gains pass overall and conditional utility, accepting 1,206 to 1,387 of 8,000 images. Every gain has only 98.4% marginal scene coverage. Accepted-image coverage is 98.4375% to 98.7562%, accepted-scene coverage is 97.5845% to 97.8972%, and each mapping accepts 7 to 11 errors over 3 mm. Partial accepted-image coverage is 96.9697% to 97.9487%; full accepted-image coverage is 95.3947% to 95.8042%. Four quantile calibrations, zero new model fits, and zero optimizer updates.
- Artifacts: `train/select_multiscale_obstruction_mapping.py`; `train/multiscale_obstruction_mapping_v1_plan.json`; `eval/multiscale_obstruction_mapping_v1_report.json`; `tests/test_multiscale_obstruction_mapping.py`; `docs/IMAGE_DEPENDENT_UNCERTAINTY.md`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Training-only synthetic mapping selection using shared cohorts across four preregistered candidates. The strong classifier remains frozen, but its global probability does not rank conditional localization error. No selected map, fresh confirmation, runtime threshold, physical-camera evidence, or motion authority. ModelMotionBatchV2 and arm/integration statuses are unchanged.
- Supersedes: none; all prior failed uncertainty evidence remains preserved.
- Next dependency: Stop global scalar transforms. Preregister a localized geometric uncertainty feature based on landmark visibility and per-landmark residual or confidence, then test its ranking on new grouped training-selection evidence before allocating another calibration chain.

### E-20260927-AI-353 — obstruction-probability mapping verification

- Stage: S1
- Lane: AI
- Commit: `bd51f17b44dfbae07c862988b79a36c437e2a2c2` (frozen mapping-selection source; tests and documentation committed in the successor)
- Inputs/fixtures: Same 16,000 new images, frozen classifier and pose models, four gains, plan, and report as AI-352; exact hashes are recorded there and in the report.
- Command: `python -m pytest -q software/ai/tests/test_multiscale_obstruction_mapping.py`
- Result: PASS: 2 tests in 2.50s. Tests verify the exact mapping equation, frozen artifact lineage, grouped populations, all four rank-991 quantiles, summaries, conditional checks, deterministic no-selection result, and zero training, hardware, or physical authority.
- Artifacts: `tests/test_multiscale_obstruction_mapping.py`; `eval/multiscale_obstruction_mapping_v1_report.json`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Existing pytest-asyncio configuration warning. Recount consistency only; no physical assurance. Contract unchanged, so shared boundary tests were not triggered.
- Supersedes: none.
- Next dependency: Same as AI-352.

### E-20260927-AI-354 — obstruction-probability mapping snapshot review

- Stage: S1
- Lane: AI
- Commit: `bd51f17b44dfbae07c862988b79a36c437e2a2c2` (frozen mapping-selection source; final ledger append in successor)
- Inputs/fixtures: Repository snapshot containing the frozen study, report, tests, interpretation, and shared ledger; exact hashes recorded in AI-352.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS: 6,291 paths, 944.6 MiB, 0 unresolved review findings, 14 reviewed synthetic fixtures.
- Artifacts: mapping plan/report; verification test; uncertainty documentation; shared ledger.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic repository review before final ledger append; not model, runtime, or physical assurance. No arm or integration status changes.
- Supersedes: none.
- Next dependency: Same as AI-352.

### E-20260927-AI-355 — localized geometric risk ranking

- Stage: S1
- Lane: AI
- Commit: `e660c05d6c4541b890411df04f5b1537aabbc8bf` (features, fresh population, ranking metrics, checks, selection rule, source, plan, and claim frozen before inference; report, tests, interpretation, and claim removal committed in the successor)
- Inputs/fixtures: Frozen landmark checkpoint SHA256 `356a4dec05c6c2194c6d31542fed0d7199d5e989eb4b7678888d1a01aa493281`; fresh scenes `51000000..51000999`, two styles, and four conditions for 8,000 images. Raw pixel SHA256 `78eb226f682e15ee919bcdfe9f94dd6f433cc765dd2ab621daea96d7cb8a4de1`; resized pixel SHA256 `80beb65f03adb51a6129847d46d1f043863e3b244af8071a82ce46c9e124bea1`; candidate/SILU/separable prediction SHA256 values `c20c6d6a366f43daa7be2679038ab3bf05ef80d6969c7551523ee89dded933ad`, `fba477f93f06cd3e28071e8c404fa5db78142d81e418c9a53566a7d5113c8cd2`, and `cfe265e2f3d286209d5fc65741231621a4375c1b1983c0340a8ba83abd4163b1`; landmark prediction SHA256 `3532161eb9afb5491b35c14aa7a66f2a67fd9d1d1d382998c897ee4acf230397`; plan SHA256 `2794f8875bc41f839c5502ff38bb8a4c60ac9aef5fa74f67b8dacd9bc6368e58`; report SHA256 `ebcf7005d784445d4056003c6c74dbc39048251e3cde551e8d13c8515badf718`.
- Command: `python software/ai/vision/evaluate_localized_geometric_risk.py`
- Result: FAIL fixed selection rule; no feature selected. Ensemble disagreement scene AUROC is `0.681112862`, with `109/1000` failed scenes and 5.6%/6.2% failure in its lowest-risk 25%/50%. Maximum corner residual AUROC is `0.566974536`; visibility-weighted residual is `0.599522236`; fixed fusion is `0.637969913`, with 4.8%/8.4% low-risk failure. Fusion partial/full image AUROC is `0.812288727`/`0.649020753`; full does not improve the disagreement baseline `0.659726797`. Every localized feature fails minimum scene AUROC, required improvement, and both low-risk reductions. Zero model or calibration fits and zero optimizer updates.
- Artifacts: `vision/evaluate_localized_geometric_risk.py`; `eval/localized_geometric_risk_v1_plan.json`; `eval/localized_geometric_risk_v1_report.json`; `tests/test_localized_geometric_risk.py`; `docs/IMAGE_DEPENDENT_UNCERTAINTY.md`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Fresh grouped synthetic ranking evidence, but the landmark model is an older synthetic research model and its outputs are not calibrated confidence. Three millimetres is only a research label. No feature selection, metric calibration, runtime installation, physical-camera evidence, or motion authority. ModelMotionBatchV2 and arm/integration statuses are unchanged.
- Supersedes: none; the global probability and earlier uncertainty failures remain preserved.
- Next dependency: Train a compact image-conditioned error or heteroscedastic head directly against frozen pose residuals using new scene-grouped training and selection populations. Require fresh failure ranking before allocating independent metric calibration and confirmation evidence.

### E-20260927-AI-356 — localized geometric risk verification

- Stage: S1
- Lane: AI
- Commit: `e660c05d6c4541b890411df04f5b1537aabbc8bf` (frozen ranking source; tests and documentation committed in the successor)
- Inputs/fixtures: Same 8,000 fresh images, frozen pose and landmark models, four ranking scores, plan, and report as AI-355; exact hashes are recorded there and in the report.
- Command: `python -m pytest -q software/ai/tests/test_localized_geometric_risk.py`
- Result: PASS: 2 tests in 3.09s. Tests verify image/pose-derived corner features, frozen lineage, exact grouped population, complete ranking recounts, every selection check, deterministic no-selection outcome, and zero fitting, hardware, or physical authority.
- Artifacts: `tests/test_localized_geometric_risk.py`; `eval/localized_geometric_risk_v1_report.json`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Existing pytest-asyncio configuration warning. Recount consistency only; no physical assurance. Contract unchanged, so shared boundary tests were not triggered.
- Supersedes: none.
- Next dependency: Same as AI-355.

### E-20260927-AI-357 — localized geometric risk snapshot review

- Stage: S1
- Lane: AI
- Commit: `e660c05d6c4541b890411df04f5b1537aabbc8bf` (frozen ranking source; final ledger append in successor)
- Inputs/fixtures: Repository snapshot containing the frozen study, report, tests, interpretation, and shared ledger; exact hashes recorded in AI-355.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS: 6,295 paths, 952.0 MiB, 0 unresolved review findings, 14 reviewed synthetic fixtures.
- Artifacts: localized ranking plan/report; verification test; uncertainty documentation; shared ledger.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic repository review before final ledger append; not model, runtime, or physical assurance. No arm or integration status changes.
- Supersedes: none.
- Next dependency: Same as AI-355.

### E-20260927-AI-358 — direct pose-error head selection

- Stage: S1
- Lane: AI
- Commit: `953b46cbaaa2694de89fad712e5433bf8f6520c7` (architecture, frozen inputs, training objective, populations, checks, source, plan, and claim frozen before feature extraction or training; report, checkpoint, tests, interpretation, and claim removal committed in the successor)
- Inputs/fixtures: Training scenes `52000000..52001999` (16,000 images) and selection scenes `53000000..53000999` (8,000 images), each with two styles and four conditions. Training pixel/feature/target SHA256 values `779b2efa0d1168a57bca59af249f57523da27795526697cfd413d0e2c490332c`, `d2b6d6c7564d385f3e76ad379624933a3c14ee66e1f3dc4903778b2557bbac84`, and `f08f701b1bb5e349b5a1b2dcb8f810d1e77bae95772f91385a7e796d996c4bf6`; selection pixel/feature/target SHA256 values `7a12dc83fdc196a735e2174021a72fa8e014b98786b2e0e671e2057f1e16aa56`, `1e5991862fbc817610f9ee81cdb48a26581da617a7786bc551d531eed3ce4f33`, and `a13fd869b6316b4851cd6f476677f3d637970f56e4abef8c79999c854e9df05b`; training candidate/SILU/separable prediction hashes `4f6444a95f711b12317fd48c5334b90bf7df6e06d53b1d97221cc1f7bfc4cd14`, `b70ac569173cbc8508026b2897eab770c008718d24c60871a190c9956784f34a`, and `33dd062bfe95bc74806f580ca244fd22e43fbdf01217ade4dced42dd4d13c942`; selection prediction hashes are retained in the report. Plan SHA256 `a46320df1adbdbffacf97313dede473be4f757a2e9e8a6f1005ada8d370e6e53`; report SHA256 `46b3d1f66e15f40e5e6e872b87e6f4aebaac55ba92033a16d03540f77f5cbda2`; checkpoint SHA256 `0bee4cd1682dea9c7a893b8adcf932c866aa805c71a5b790e96f30cefb726df5`; normalization SHA256 `4863325d0adb4d128d2748dfd7a83bc0d1690a24d56ea99b52f7eb719f339dbf`; risk prediction SHA256 `9696d81a453f4bf58e9f0614acf95d7902e9bc97c8bbebb756c9cab1ce986f15`.
- Command: `python software/ai/train/train_pose_error_head.py`
- Result: FAIL fixed selection rule by one lowest-quartile scene. The 52,481-parameter head raises grouped scene AUROC from `0.701847595` to `0.729795210`, passes the 0.72 minimum and 0.02 improvement, lowers lowest-half failure from 6.8% to 5.0%, and passes all conditional image AUROCs: standard `0.841182455`, appearance `0.875035897`, partial `0.804697167`, full `0.735053654`. Lowest-quartile failure is `10/250` (4.0%) versus a required maximum of 3.9% from `13/250 * 0.75`; that check fails, so the complete selection fails. One model fit, zero calibration fits, and 2,500 optimizer updates.
- Artifacts: `vision/pose_error_head.py`; `train/train_pose_error_head.py`; `train/pose_error_head_v1_plan.json`; `eval/pose_error_head_v1_report.json`; `results/pose_error_head_v1/model.pt`; `tests/test_pose_error_head.py`; `docs/IMAGE_DEPENDENT_UNCERTAINTY.md`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Synthetic training-selection evidence for one seed and objective. The retained checkpoint is research evidence only. No metric calibration, confirmation, runtime installation, physical-camera evidence, or motion authority. ModelMotionBatchV2 and arm/integration statuses are unchanged.
- Supersedes: none; the near miss does not erase any earlier failed evidence or qualify the head.
- Next dependency: Keep the failed gate unchanged. Freeze one tail-aware head using the same frozen descriptor inputs and a preregistered failure-weighted or ranking objective on entirely new grouped training-selection cohorts before any calibration allocation.

### E-20260927-AI-359 — direct pose-error head verification

- Stage: S1
- Lane: AI
- Commit: `953b46cbaaa2694de89fad712e5433bf8f6520c7` (frozen training-selection source; tests and documentation committed in the successor)
- Inputs/fixtures: Same 24,000 images, frozen pose models, 52,481-parameter head, plan, report, and retained research checkpoint as AI-358; exact hashes are recorded there and in the report.
- Command: `python -m pytest -q software/ai/tests/test_pose_error_head.py`
- Result: PASS: 2 tests in 2.35s. Tests verify strict architecture and normalization, frozen lineage, exact grouped populations, ranking recounts, every fixed check including the single failed lowest-quartile check, and zero calibration, hardware, or physical authority.
- Artifacts: `tests/test_pose_error_head.py`; `eval/pose_error_head_v1_report.json`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Existing pytest-asyncio configuration warning. Recount consistency only; no physical assurance. Contract unchanged, so shared boundary tests were not triggered.
- Supersedes: none.
- Next dependency: Same as AI-358.

### E-20260927-AI-360 — direct pose-error head snapshot review

- Stage: S1
- Lane: AI
- Commit: `953b46cbaaa2694de89fad712e5433bf8f6520c7` (frozen training-selection source; final ledger append in successor)
- Inputs/fixtures: Repository snapshot containing the frozen study, report, retained research checkpoint, tests, interpretation, and shared ledger; exact hashes recorded in AI-358.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS: 6,300 paths, 957.3 MiB, 0 unresolved review findings, 14 reviewed synthetic fixtures.
- Artifacts: error-head plan/report/checkpoint; verification test; uncertainty documentation; shared ledger.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic repository review before final ledger append; not model, runtime, or physical assurance. No arm or integration status changes.
- Supersedes: none.
- Next dependency: Same as AI-358.

### E-20260927-AI-361 — tail-aware pose-risk head selection

- Stage: S1
- Lane: AI
- Commit: `baf71ec880a6a81ea21f3d9db348c4193c273f16` (balanced tail objective, unchanged gates, populations, source, plan, and claim frozen before feature extraction or training; report, checkpoint, tests, interpretation, and claim removal committed in the successor)
- Inputs/fixtures: Training scenes `54000000..54001999` (16,000 images) and selection scenes `55000000..55000999` (8,000 images), each with two styles and four conditions. Training pixel/feature/target SHA256 values `f0c5c954a6cc71d9318b91a5ad029ced1ca3d47860d0ba7721a767f60db9ea0f`, `873485b2d2b0c1bfa1e54995717e36e70521770074fd7834252679bc7abdcd2e`, and `1b2569a21fa1d1e93fc61547234e51547cb4f22ba3d17448a1687e6d1dcdd6d2`; selection pixel/feature/target SHA256 values `cb370f30231e52fb4e7499c013e99cd5389010e5a530ab645c9126f518a84301`, `16135ee8f5548f438ca6a9a707a3af079eed6f80da37385302643a8a8b77e86c`, and `c0dbe7e5e7710acec97371b7ae4e3c7e9ebd167c911b74bc741027ddd9c60c6a`; all pose prediction hashes are retained in the report. Plan SHA256 `6d03ea52498af5d6c219733905f6c0c39e8ad189c5190d13c46ca3bf2438e045`; report SHA256 `40524c98512aa98383f70aa0156b062276660572081ff1c4b808fdec460211cf`; checkpoint SHA256 `79d48b0ef63effea3642c2e08a20d8a6800f27f75e0ed97ed8050f146d4f326e`; normalization SHA256 `6758071d393e432f969c0f90c72bf5645a3e26286c2acaaecf615a3d4f849691`; risk prediction SHA256 `da86af9621834e5f01d6aae5503df04d350e8aaf88d36804e12c7d583aaa1c45`.
- Command: `python software/ai/train/train_tail_risk_head.py`
- Result: PASS fixed training-selection rule. The 52,481-parameter head trains on 688 positive and 15,312 negative images with positive weight `22.25581395348837`. On untouched selection, scene AUROC rises from `0.6851` to `0.755266667`; lowest-quartile failure falls from 5.2% to 3.6%; lowest-half failure falls from 5.4% to 3.6%. Conditional image AUROC is standard `0.914617486`, appearance `0.924933862`, partial `0.783335065`, full `0.755343893`; every fixed check passes. One model fit, zero calibration fits, and 2,500 optimizer updates.
- Artifacts: `train/train_tail_risk_head.py`; `train/tail_risk_head_v1_plan.json`; `eval/tail_risk_head_v1_report.json`; `results/tail_risk_head_v1/model.pt`; `tests/test_tail_risk_head.py`; `docs/IMAGE_DEPENDENT_UNCERTAINTY.md`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Synthetic training-selection evidence for one seed, candidate, and 3 mm binary target. Passing selects a ranking feature only. It supplies no metric radius, calibration, confirmation, runtime installation, physical-camera evidence, or motion authority. ModelMotionBatchV2 and arm/integration statuses are unchanged.
- Supersedes: none; the regression near miss and all earlier failed evidence remain preserved.
- Next dependency: Freeze one mapping study using this exact checkpoint on new grouped mapping-calibration and selection cohorts. Retain 99% marginal and accepted-subset coverage, per-condition utility/coverage, and zero accepted errors above 3 mm before allocating independent confirmation.

### E-20260927-AI-362 — tail-aware pose-risk verification

- Stage: S1
- Lane: AI
- Commit: `baf71ec880a6a81ea21f3d9db348c4193c273f16` (frozen training-selection source; tests and documentation committed in the successor)
- Inputs/fixtures: Same 24,000 images, frozen pose models, 52,481-parameter head, plan, report, and selected research checkpoint as AI-361; exact hashes are recorded there and in the report.
- Command: `python -m pytest -q software/ai/tests/test_tail_risk_head.py`
- Result: PASS: 1 test in 2.37s. The test verifies frozen lineage, exact grouped populations, training class balance and weight, complete ranking recounts, every fixed passing check, and zero calibration, hardware, or physical authority.
- Artifacts: `tests/test_tail_risk_head.py`; `eval/tail_risk_head_v1_report.json`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Existing pytest-asyncio configuration warning. Recount consistency only; no physical assurance. Contract unchanged, so shared boundary tests were not triggered.
- Supersedes: none.
- Next dependency: Same as AI-361.

### E-20260927-AI-363 — tail-aware pose-risk snapshot review

- Stage: S1
- Lane: AI
- Commit: `baf71ec880a6a81ea21f3d9db348c4193c273f16` (frozen training-selection source; final ledger append in successor)
- Inputs/fixtures: Repository snapshot containing the frozen study, report, selected research checkpoint, tests, interpretation, and shared ledger; exact hashes recorded in AI-361.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS: 6,305 paths, 962.9 MiB, 0 unresolved review findings, 14 reviewed synthetic fixtures.
- Artifacts: tail-risk plan/report/checkpoint; verification test; uncertainty documentation; shared ledger.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic repository review before final ledger append; not model, runtime, or physical assurance. No arm or integration status changes.
- Supersedes: none.
- Next dependency: Same as AI-361.

### E-20260927-AI-364 — tail-risk metric mapping selection

- Stage: S1
- Lane: AI
- Commit: `22973ffaecef66bac74ed6f4c2cbaaa9d4f13127` (mapping family, immutable inputs, fresh populations, fixed checks, source, plan, and claim frozen before inference; failed report, tests, interpretation, and claim removal committed in the successor)
- Inputs/fixtures: Frozen tail-risk checkpoint SHA256 `79d48b0ef63effea3642c2e08a20d8a6800f27f75e0ed97ed8050f146d4f326e`; mapping-calibration scenes `56000000..56000999` and selection scenes `57000000..57000999`, each with two styles and four conditions for 8,000 images. Calibration pixel/feature/target/risk-prediction SHA256 values `9eb1ac7e53fc73221b60c26e8a9e953cada1aacfd3427e30adf4c166e195ccf0`, `7e62e00321cb365e0a53400f5d25d4677ab1945a8825108231053bed5046ee39`, `f6e010a11c41085102e92f1a98af2c9d0e9481d70b8f94dcacf3221d251bb27c`, and `2f67f77971e7a27006eb51aa08c2a1a8b4ee8aec0e84daefb692227196ada238`; selection values `dbb044689b9122683a8508f6e4d6188264ae91114958bf2e9fb64b5e3445ccd0`, `01eb1ae79e87e965038c92639410607ccc3ccaf679ac32246a0471d1be44af98`, `c3f1359ab8a591d9f996b9bfa40acdcf2c1985ac59c743711906bf7786c52fbb`, and `d957b26c990ce48ef2f620ddb407761115fbe123e39099081427a9db0c7e2dd0`. Plan SHA256 `6ef7bfd12e827a9053071f1cf27a4fdbed9f3c556d6e0cf3d359c41d577d227e`; report SHA256 `d5d5a68459b6fa256c06391b3326283c587a4de7e7ab2ea2cac17b913f2c5db9`.
- Command: `python software/ai/train/select_tail_risk_mapping.py`
- Result: FAIL fixed selection rule; no mapping selected. Low-risk fractions 0.05, 0.10, 0.15, and 0.20 used thresholds `-11.917281151`, `-10.326743126`, `-9.127495766`, and `-8.262100220`, with rank-991 normalized quantiles `1.968840241`, `2.555912495`, `2.643276930`, and `2.805078506`. They retained 440, 781, 1,211, and 1,653 of 8,000 selection images. Marginal scene coverage was 97.7%, 99.2%, 99.0%, and 99.0%; accepted-image coverage was 89.7727%, 98.4635%, 98.7614%, and 99.0321%; accepted-scene coverage was 78.8991%, 95.6757%, 96.3768%, and 97.2222%. Accepted errors above 3 mm were 2, 5, 8, and 11. At 20%, full obstruction retained 323 images, covered 95.9752%, and admitted 9 errors above 3 mm. Four mapping fits, zero new model fits, and zero optimizer updates.
- Artifacts: `train/select_tail_risk_mapping.py`; `train/tail_risk_mapping_v1_plan.json`; `eval/tail_risk_mapping_v1_report.json`; `tests/test_tail_risk_mapping.py`; `docs/IMAGE_DEPENDENT_UNCERTAINTY.md`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Synthetic mapping-calibration and selection evidence. The four mappings share their respective fixed cohorts, and no independent confirmation was allocated after failure. A binary risk ranking is not a calibrated millimetre radius. No mapping, qualification, runtime behavior, physical-camera evidence, or motion authority. ModelMotionBatchV2 and arm/integration statuses are unchanged.
- Supersedes: none; the passed ranking evidence remains valid while all metric-mapping failures are preserved.
- Next dependency: On entirely fresh grouped training-selection populations, preregister and train a compact upper-tail metric error estimator using a high-quantile or exceedance objective. It must later pass separate mapping calibration, selection, and independent confirmation under the unchanged 99% marginal/accepted-subset, per-condition utility, and zero accepted errors above 3 mm rules.

### E-20260927-AI-365 — tail-risk metric mapping verification

- Stage: S1
- Lane: AI
- Commit: `22973ffaecef66bac74ed6f4c2cbaaa9d4f13127` (frozen mapping-selection source; tests and documentation committed in the successor)
- Inputs/fixtures: Same 16,000 fresh images, frozen pose ensemble and tail-risk head, four two-level mappings, plan, and failed report as AI-364; exact hashes are recorded there and in the report.
- Command: `python -m pytest -q software/ai/tests/test_tail_risk_mapping.py`
- Result: PASS: 2 tests in 2.40s. Tests verify bounded two-level scale assignment, immutable input lineage, both exact grouped populations, all four thresholds, scene scores, conformal ranks and quantiles, complete overall and conditional summary recounts, every fixed check, deterministic no-selection outcome, and zero model fitting, optimizer, hardware, physical, qualification, or runtime authority.
- Artifacts: `tests/test_tail_risk_mapping.py`; `eval/tail_risk_mapping_v1_report.json`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Existing pytest-asyncio configuration warning. Recount consistency only; no physical assurance. Contract unchanged, so shared boundary tests were not triggered.
- Supersedes: none.
- Next dependency: Same as AI-364.

### E-20260927-AI-366 — tail-risk metric mapping snapshot review

- Stage: S1
- Lane: AI
- Commit: `22973ffaecef66bac74ed6f4c2cbaaa9d4f13127` (frozen mapping-selection source; final ledger append in successor)
- Inputs/fixtures: Repository snapshot containing the frozen study, failed report, verification test, interpretation, and shared ledger; exact hashes recorded in AI-364.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS: 6,310 paths, 967.6 MiB, 0 unresolved review findings, 14 reviewed synthetic fixtures.
- Artifacts: mapping plan/report; verification test; uncertainty documentation; shared ledger.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic repository review before final ledger append; not model, runtime, or physical assurance. No arm or integration status changes.
- Supersedes: none.
- Next dependency: Same as AI-364.

### E-20260927-AI-367 — direct upper-tail metric head selection

- Stage: S1
- Lane: AI
- Commit: `d62c0f171e7cee6ca33fbf77fd49cd3b6c16455a` (95th-percentile objective, fixed gates, fresh populations, source, plan, and claim frozen before feature extraction or training; failed report, checkpoint, tests, interpretation, and claim removal committed in the successor)
- Inputs/fixtures: Training scenes `58000000..58001999` (16,000 images) and selection scenes `59000000..59000999` (8,000 images), each with two styles and four conditions. Training pixel/feature/target SHA256 values `bce2adccce0f499ceb03f0b86d3305c7c6f3aea2c0f9851b61590e4eb76ac6c5`, `b9899fcaaf27ab7e41a4fff1b1e77cda3e51d2c656ea59e6af578d740da003bc`, and `a288b9a0c70feae510f03a5be0a38bdc4c91adb95beb827f5966a51586257b9c`; selection values `d4bea73e19f51b68d4fd47d7f65c217b3873f5a8bca047c829b8c0fd38b62cb5`, `1b629b28cfd4326b31cb5209b7b23f65767ed53cd843f5ef93dc686809a9d9ec`, and `c124a8c8abdc7c5471780fd5d9bee6b357cfeb8ca1f665be95c921e48340151e`; all pose prediction hashes are retained in the report. Plan SHA256 `1d3a99a717009b08e13b24c456628d3873a132c46fdce2cf5e43ce8bb0ccd67f`; report SHA256 `8213429fd1d2a48ff74f1018d661b76f7e52ccdb9e33ab1308e4406a06192b42`; checkpoint SHA256 `a14a2821256112367144af761ad2c6e3aaee9c1a3945950127883cee9867cf1e`; normalization SHA256 `66abe3396f48e9940bca5fab0867de50dc3aeb3f2c56b7cabdf783927bf63217`; selection prediction SHA256 `88e39598bab64a3cf282a2dfa4c9956f627b7db2f2a742a6d7013587aac8e707`.
- Command: `python software/ai/train/train_upper_tail_error_head.py`
- Result: FAIL fixed selection rule. The 52,481-parameter head reduces selection mean 0.95 pinball loss from `0.201363615` for the training-only constant bound to `0.113025096`, and median bound from `2.866124392` mm to `2.089084268` mm. Scene AUROC is `0.720850255`; lowest-quartile/half failure is 3.2%/4.8%; conditional image AUROCs are standard `0.913087980`, appearance `0.952179750`, partial `0.878273048`, and full `0.752727520`. Overall coverage is `0.892375`, below 0.90, and full-obstruction coverage is `0.81`, below 0.85; all other checks pass. Maximum predicted bound is `90.377532959` mm. One model fit, zero calibration fits, and 2,500 optimizer updates.
- Artifacts: `train/train_upper_tail_error_head.py`; `train/upper_tail_error_head_v1_plan.json`; `eval/upper_tail_error_head_v1_report.json`; `results/upper_tail_error_head_v1/model.pt`; `tests/test_upper_tail_error_head.py`; `docs/IMAGE_DEPENDENT_UNCERTAINTY.md`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Synthetic training-selection evidence for one seed, architecture, and 0.95 quantile. The failed checkpoint is research evidence only. No metric calibration, independent confirmation, runtime installation, physical-camera evidence, or motion authority. ModelMotionBatchV2 and arm/integration statuses are unchanged.
- Supersedes: none; the metric-mapping failure and all earlier evidence remain preserved.
- Next dependency: Retain direct metric supervision but preregister one robust upper-tail formulation on entirely fresh grouped training-selection populations. It should address full-obstruction undercoverage and extreme outputs through a bounded residual parameterization or a higher quantile with an explicit finite-bound penalty before any calibration allocation.

### E-20260927-AI-368 — direct upper-tail metric head verification

- Stage: S1
- Lane: AI
- Commit: `d62c0f171e7cee6ca33fbf77fd49cd3b6c16455a` (frozen training-selection source; tests and documentation committed in the successor)
- Inputs/fixtures: Same 24,000 images, frozen pose models, 52,481-parameter head, plan, failed report, and retained research checkpoint as AI-367; exact hashes are recorded there and in the report.
- Command: `python -m pytest -q software/ai/tests/test_upper_tail_error_head.py`
- Result: PASS: 2 tests in 2.12s. Tests verify pinball direction, metric summaries, frozen lineage, checkpoint integrity, exact grouped populations, complete metric and ranking recounts, every fixed check including the two failed coverage checks, and zero calibration, hardware, physical, qualification, or runtime authority.
- Artifacts: `tests/test_upper_tail_error_head.py`; `eval/upper_tail_error_head_v1_report.json`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Existing pytest-asyncio configuration warning. Recount consistency only; no physical assurance. Contract unchanged, so shared boundary tests were not triggered.
- Supersedes: none.
- Next dependency: Same as AI-367.

### E-20260927-AI-369 — direct upper-tail metric snapshot review

- Stage: S1
- Lane: AI
- Commit: `d62c0f171e7cee6ca33fbf77fd49cd3b6c16455a` (frozen training-selection source; final ledger append in successor)
- Inputs/fixtures: Repository snapshot containing the frozen study, failed report, retained research checkpoint, verification test, interpretation, and shared ledger; exact hashes recorded in AI-367.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS: 6,314 paths, 973.4 MiB, 0 unresolved review findings, 14 reviewed synthetic fixtures.
- Artifacts: upper-tail plan/report/checkpoint; verification test; uncertainty documentation; shared ledger.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic repository review before final ledger append; not model, runtime, or physical assurance. No arm or integration status changes.
- Supersedes: none.
- Next dependency: Same as AI-367.

### E-20260927-AI-370 — bounded upper-tail metric head selection

- Stage: S1
- Lane: AI
- Commit: `a0ffc32e23c6e6533350ecf5218e969906f3d08b` (bounded 97.5th-percentile objective, unchanged metric/ranking gates, fresh populations, source, plan, and claim frozen before feature extraction or training; failed report, checkpoint, tests, interpretation, and claim removal committed in the successor)
- Inputs/fixtures: Training scenes `60000000..60001999` (16,000 images) and selection scenes `61000000..61000999` (8,000 images), each with two styles and four conditions. Training pixel/feature/target SHA256 values `445a710ef31e5ea5089d0a3f7c11d3bfa1964d718547457e91ce490a03245632`, `732db4e3c86f33a79af1be26bd8d2122ec74dba660456fec95db2ee19112cafb`, and `ccb7a4bb799ec1b0df1f005d25b0ab1de7dc0d103e36496ce0c48ee9b91d6435`; selection values `068d9de2eb740b23795ef58b19f37b494066e98897107ae06d436cb4737b4ca1`, `acf07ca7c1ed7ce3eed35dbf0572c738f855b491089495a86d4c79f48b14a02b`, and `b6c3a94c4d4798b1b7485bb06b5a63b2363ce8a33bc1fa158ef8812c72b27247`; all pose prediction hashes are retained in the report. Plan SHA256 `4ff59806009d84bd889e1f63dd1ed13651c5fe3bb7190f1c772d03a772ee0262`; report SHA256 `d0632877b0918c8b71417a8c34e6e580b12599c6144cb4876d4bb11dcc821fb7`; checkpoint SHA256 `c9ee03b9962e28443fbac7644cdfbb9c068e544aeb75cc58dc2ba8b6b494b16c`; normalization SHA256 `0b02a9f05d7a1a5adb5e7dea20ac08b74224a898426b4cb5ee425c3a7052f293`; selection prediction SHA256 `5b47a703809359e1c3c5de12a849fa31eb73b570734a4ddef1532d45fe710e2a`.
- Command: `python software/ai/train/train_bounded_upper_tail_head.py`
- Result: FAIL fixed selection rule by one check. The 52,481-parameter head constrains output to `[0.25,10.0]` mm and reaches maximum `9.349886894` mm. Overall coverage is `0.92525`; standard/appearance/partial/full coverage is `0.948`/`0.955`/`0.9345`/`0.8635`, fixing both preceding coverage failures. Mean 0.975 pinball loss improves from `0.086245948` to `0.076668675`; median bound improves from `3.268818617` mm to `2.256930113` mm. Every conditional image AUROC passes at standard `0.931306934`, appearance `0.874005557`, partial `0.869377453`, and full `0.726436553`. Scene AUROC is `0.696362295`, below the frozen `0.70` minimum; all other checks pass. One model fit, zero calibration fits, and 2,500 optimizer updates.
- Artifacts: `train/train_bounded_upper_tail_head.py`; `train/bounded_upper_tail_head_v1_plan.json`; `eval/bounded_upper_tail_head_v1_report.json`; `results/bounded_upper_tail_head_v1/model.pt`; `tests/test_bounded_upper_tail_head.py`; `docs/IMAGE_DEPENDENT_UNCERTAINTY.md`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Synthetic training-selection evidence for one seed, architecture, quantile, and frozen output range. The near-miss checkpoint is research evidence only. No metric calibration, independent confirmation, runtime installation, physical-camera evidence, or motion authority. ModelMotionBatchV2 and arm/integration statuses are unchanged.
- Supersedes: none; both preceding metric failures and all earlier evidence remain preserved.
- Next dependency: Preserve the bounded output, direct pinball target, and all present gates. On entirely fresh grouped populations, preregister one multitask head with a fixed binary `>3 mm` tail-ranking auxiliary loss to recover the missing scene ordering before any calibration allocation.

### E-20260927-AI-371 — bounded upper-tail metric verification

- Stage: S1
- Lane: AI
- Commit: `a0ffc32e23c6e6533350ecf5218e969906f3d08b` (frozen training-selection source; tests and documentation committed in the successor)
- Inputs/fixtures: Same 24,000 images, frozen pose models, 52,481-parameter head, plan, failed report, and retained research checkpoint as AI-370; exact hashes are recorded there and in the report.
- Command: `python -m pytest -q software/ai/tests/test_bounded_upper_tail_head.py`
- Result: PASS: 2 tests in 2.14s. Tests verify the frozen output transformation at its endpoints and midpoint, immutable lineage, checkpoint integrity, exact grouped populations, complete metric and ranking recounts, all fixed passing checks, the one failed scene-AUROC check, and zero calibration, hardware, physical, qualification, or runtime authority.
- Artifacts: `tests/test_bounded_upper_tail_head.py`; `eval/bounded_upper_tail_head_v1_report.json`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Existing pytest-asyncio configuration warning. Recount consistency only; no physical assurance. Contract unchanged, so shared boundary tests were not triggered.
- Supersedes: none.
- Next dependency: Same as AI-370.

### E-20260927-AI-372 — bounded upper-tail metric snapshot review

- Stage: S1
- Lane: AI
- Commit: `a0ffc32e23c6e6533350ecf5218e969906f3d08b` (frozen training-selection source; final ledger append in successor)
- Inputs/fixtures: Repository snapshot containing the frozen study, failed report, retained research checkpoint, verification test, interpretation, and shared ledger; exact hashes recorded in AI-370.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS: 6,319 paths, 979.3 MiB, 0 unresolved review findings, 14 reviewed synthetic fixtures.
- Artifacts: bounded-head plan/report/checkpoint; verification test; uncertainty documentation; shared ledger.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic repository review before final ledger append; not model, runtime, or physical assurance. No arm or integration status changes.
- Supersedes: none.
- Next dependency: Same as AI-370.

### E-20260927-AI-373 — bounded metric and tail-risk multitask selection

- Stage: S1
- Lane: AI
- Commit: `9d72898ac177940a0db8ad169c25e0648a30c37e` (shared architecture, fixed multitask objective, unchanged metric gates, auxiliary gates, fresh populations, source, plan, and claim frozen before feature extraction or training; failed report, checkpoint, tests, interpretation, and claim removal committed in the successor)
- Inputs/fixtures: Training scenes `62000000..62001999` (16,000 images) and selection scenes `63000000..63000999` (8,000 images), each with two styles and four conditions. Training pixel/feature/target SHA256 values `36d238a62bd848681c566120b53fea4460036d31a33350843b41c0cd91266370`, `e8f5e0da8954587525ffb0e0a73952d932b281685df2ef6967261a68d30a58a0`, and `8cbda5d05b567788b1dc47b938835f91322ead397940809d7045fc7a33970573`; selection values `f85e2cb4b4fe707d2f2ca957163bea9119cac0071fc255e9acd135bb45364395`, `cb59e6939e0de8043a7d304fbcbf10af490ba3002fe330982eda381fef4ee1b9`, and `09cd792eaa3962eaf5fa2fa0241fc8f17cc5fdc687f3c92dd2371f50daf40e67`; all pose prediction hashes are retained in the report. Plan SHA256 `7be0cd259544d99770fbe82b340c4078ecc8770fdcd663735a5565e5835e868f`; report SHA256 `0f15069352800f10b79fafa48ac52c886d57fe8f9c6a3f845c61a858ebd65a08`; checkpoint SHA256 `404da04151798ce5aba74e14848bfb5785f1a18bfe0864c815aa5455bdce8b99`; normalization SHA256 `4a053d1e933dcfebacf4ec21c3999d332d96873100dd1732beb6dc459b9536a7`; metric/risk prediction SHA256 values `03e9315d8183ee49e14daeeb38d928ecc1f642fc439a77e27cd087385de37e1b` and `7122b25b1eb2de0b4450b9db39bdf7bad8e775d6a15e8aca828f118749f112f5`.
- Command: `python software/ai/train/train_multitask_upper_tail_head.py`
- Result: FAIL fixed selection rule. The 52,514-parameter shared head trains with `pinball + 0.05 * balanced BCE` on 591 positive and 15,409 negative images, positive weight `26.072758037`. Metric coverage passes overall at `0.925375` and under full obstruction at `0.884`; mean pinball loss improves from `0.083385583` to `0.077571542`; median bound improves from `3.328519106` mm to `2.360533118` mm; all metric condition AUROCs and the finite range pass. Metric scene AUROC fails at `0.685361744`. Auxiliary scene AUROC fails its 0.72 gate at `0.683132568`, and auxiliary full-obstruction image AUROC fails 0.70 at `0.699576306`. One model fit, zero calibration fits, and 2,500 optimizer updates.
- Artifacts: `vision/multitask_error_head.py`; `train/train_multitask_upper_tail_head.py`; `train/multitask_upper_tail_head_v1_plan.json`; `eval/multitask_upper_tail_head_v1_report.json`; `results/multitask_upper_tail_head_v1/model.pt`; `tests/test_multitask_upper_tail_head.py`; `docs/IMAGE_DEPENDENT_UNCERTAINTY.md`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Synthetic training-selection evidence for one seed, architecture, and fixed loss weight. The failed checkpoint is research evidence only. No metric calibration, independent confirmation, runtime installation, physical-camera evidence, or motion authority. ModelMotionBatchV2 and arm/integration statuses are unchanged.
- Supersedes: none; the bounded single-task near miss and all earlier evidence remain preserved.
- Next dependency: Close shared-trunk training at this fixed weight. Freeze a late-fusion mapping study using the already specialized bounded-metric and tail-risk checkpoints without retraining, on entirely fresh mapping-calibration and selection cohorts. Require the existing conditional coverage, utility, and zero accepted errors above 3 mm gates before independent confirmation.

### E-20260927-AI-374 — bounded metric and tail-risk multitask verification

- Stage: S1
- Lane: AI
- Commit: `9d72898ac177940a0db8ad169c25e0648a30c37e` (frozen training-selection source; tests and documentation committed in the successor)
- Inputs/fixtures: Same 24,000 images, frozen pose models, 52,514-parameter head, plan, failed report, and retained research checkpoint as AI-373; exact hashes are recorded there and in the report.
- Command: `python -m pytest -q software/ai/tests/test_multitask_upper_tail_head.py`
- Result: PASS: 2 tests in 2.42s. Tests verify dual output shapes and exact parameter count, immutable lineage, checkpoint integrity, exact grouped populations, complete metric and both ranking recounts, every fixed check including the three failed checks, and zero calibration, hardware, physical, qualification, or runtime authority.
- Artifacts: `tests/test_multitask_upper_tail_head.py`; `eval/multitask_upper_tail_head_v1_report.json`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Existing pytest-asyncio configuration warning. Recount consistency only; no physical assurance. Contract unchanged, so shared boundary tests were not triggered.
- Supersedes: none.
- Next dependency: Same as AI-373.

### E-20260927-AI-375 — bounded metric and tail-risk multitask snapshot review

- Stage: S1
- Lane: AI
- Commit: `9d72898ac177940a0db8ad169c25e0648a30c37e` (frozen training-selection source; final ledger append in successor)
- Inputs/fixtures: Repository snapshot containing the frozen study, failed report, retained research checkpoint, verification test, interpretation, and shared ledger; exact hashes recorded in AI-373.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS: 6,325 paths, 986.0 MiB, 0 unresolved review findings, 14 reviewed synthetic fixtures.
- Artifacts: multitask plan/report/checkpoint; verification test; uncertainty documentation; shared ledger.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic repository review before final ledger append; not model, runtime, or physical assurance. No arm or integration status changes.
- Supersedes: none.
- Next dependency: Same as AI-373.

### E-20260927-AI-376 — specialized-head late-fusion mapping selection

- Stage: S1
- Lane: AI
- Commit: `68461580d39f44a5abd7ea006d8605f3511bc827` (frozen specialist lineage, empirical-CDF fusion, fixed gain, mapping-calibration and selection populations, unchanged acceptance gates, source, plan, and claim frozen before inference; failed report, tests, interpretation, and claim removal committed in the successor)
- Inputs/fixtures: Frozen bounded-metric checkpoint/report SHA256 `c9ee03b9962e28443fbac7644cdfbb9c068e544aeb75cc58dc2ba8b6b494b16c`/`d0632877b0918c8b71417a8c34e6e580b12599c6144cb4876d4bb11dcc821fb7`; frozen tail-risk checkpoint/report SHA256 `79d48b0ef63effea3642c2e08a20d8a6800f27f75e0ed97ed8050f146d4f326e`/`40524c98512aa98383f70aa0156b062276660572081ff1c4b808fdec460211cf`. Mapping-calibration scenes `64000000..64000999` and selection scenes `65000000..65000999`, each with two styles and four conditions for 8,000 images. Calibration pixel/feature/target/metric/risk SHA256 values `46ef043471b5914d9849b74566b2dac1d0ffc6b6d4fd656e31d696cb6e169b4f`, `48948cb778c8517bd6b64746023ca1c1d994474a2298d6a91d86e7842fa2c56b`, `18b41e38fd6a80a0bde473fbba03109a92993d4fa8b3e8711f9801a7e88e0369`, `7060f62b92a6ba6d130cb6a2116175bf1f0a00ba01291adc3c621cc22dd944d9`, and `ed33a9bf68b280e816c83640d6d8ed19241e1e0d21e385525e91a9bc5d23d6cb`; selection values `f5bb40d4c81482260ed2c9132ea2cb9bbb7de374d535b2ecac7525af2544d877`, `48e433f2f346542d10fbaf5a5553a4daee1186a785f9ad074fdda61e8325dc60`, `ea1c824ffbd05d21b536c56e68877d0074e61c8d79b6d20d038d6da772a449ca`, `052c3b72073db32db3243880cd55500d136022b77e26c114aecf6ff38dcc51ef`, and `0ceeeef19a53423711578f7c7fb2aac21420ff7251158d641fc171d8ee397b6e`. Risk-reference SHA256 `4f5eb482cb58de83adb1d3be827da565e0fafbd12124c569b96542f85de0cb7f`; plan SHA256 `2e271e19cf9670951c58445205ce0fea0cf644006925722d5fcbd16fb8a75df4`; report SHA256 `8296328aaad2c98dc659d4d8d409d39513f4ede04fb3d0d8cc66249ca4d29edb`.
- Command: `python software/ai/train/select_late_fusion_mapping.py`
- Result: FAIL fixed selection rule. The empirical-risk-CDF multiplier and rank-991 conformal fit yield normalized quantile `2.183702391`. On selection, marginal scene coverage is 99.2%; 1,170/8,000 images are accepted (14.625%); all condition utility checks pass; and zero accepted error exceeds 3 mm. Overall accepted-image coverage is `0.982905983` and accepted-scene coverage is `0.985074627`, below 0.99. Conditional accepted-image coverage is standard `0.989417989`, appearance `0.995780591`, partial `0.966850829`, and full `0.941605839`; standard, partial, and full fail. Twenty accepted images exceed their predicted radius. One mapping fit, zero new model fits, and zero optimizer updates.
- Artifacts: `train/select_late_fusion_mapping.py`; `train/late_fusion_mapping_v1_plan.json`; `eval/late_fusion_mapping_v1_report.json`; `tests/test_late_fusion_mapping.py`; `docs/IMAGE_DEPENDENT_UNCERTAINTY.md`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Synthetic mapping-calibration and selection evidence for one fixed CDF fusion and gain. No independent confirmation was allocated after failure. No mapping, runtime installation, physical-camera evidence, qualification, or motion authority. ModelMotionBatchV2 and arm/integration statuses are unchanged.
- Supersedes: none; the specialist, multitask, and earlier mapping evidence remains preserved.
- Next dependency: Keep both specialists frozen. On entirely fresh mapping-calibration and selection cohorts, preregister one explicit risk-percentile acceptance gate layered over separately calibrated metric radii. Preserve the same marginal coverage, utility, conditional accepted-subset coverage, and zero accepted errors above 3 mm gates before independent confirmation.

### E-20260927-AI-377 — specialized-head late-fusion verification

- Stage: S1
- Lane: AI
- Commit: `68461580d39f44a5abd7ea006d8605f3511bc827` (frozen mapping source; tests and documentation committed in the successor)
- Inputs/fixtures: Same 16,000 fresh images, frozen specialists, empirical risk CDF, fusion plan, and failed report as AI-376; exact hashes are recorded there and in the report.
- Command: `python -m pytest -q software/ai/tests/test_late_fusion_mapping.py`
- Result: PASS: 2 tests in 2.05s. Tests verify empirical-CDF boundary semantics and exact fusion arithmetic, immutable lineage, exact grouped populations, risk-reference hash, all fused calibration rows, scene scores, rank and quantile, complete overall and conditional recounts, every fixed failed check, and zero model fitting, optimizer, hardware, physical, qualification, or runtime authority.
- Artifacts: `tests/test_late_fusion_mapping.py`; `eval/late_fusion_mapping_v1_report.json`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Existing pytest-asyncio configuration warning. Recount consistency only; no physical assurance. Contract unchanged, so shared boundary tests were not triggered.
- Supersedes: none.
- Next dependency: Same as AI-376.

### E-20260927-AI-378 — specialized-head late-fusion snapshot review

- Stage: S1
- Lane: AI
- Commit: `68461580d39f44a5abd7ea006d8605f3511bc827` (frozen mapping source; final ledger append in successor)
- Inputs/fixtures: Repository snapshot containing the frozen mapping study, failed report, verification test, interpretation, and shared ledger; exact hashes recorded in AI-376.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS: 6,330 paths, 992.9 MiB, 0 unresolved review findings, 14 reviewed synthetic fixtures.
- Artifacts: late-fusion plan/report; verification test; uncertainty documentation; shared ledger.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic repository review before final ledger append; not model, runtime, or physical assurance. No arm or integration status changes.
- Supersedes: none.
- Next dependency: Same as AI-376.

### E-20260927-AI-379 — explicit risk-gated metric selection

- Stage: S1
- Lane: AI
- Commit: `e40263374929ca32bfc68c2f69785c690cc6a7a1` (separate radius calibration, fixed 25th-percentile risk gate, fresh populations, unchanged final gates, source, plan, and claim frozen before inference; failed report, tests, interpretation, and claim removal committed in the successor)
- Inputs/fixtures: Frozen bounded-metric checkpoint/report SHA256 `c9ee03b9962e28443fbac7644cdfbb9c068e544aeb75cc58dc2ba8b6b494b16c`/`d0632877b0918c8b71417a8c34e6e580b12599c6144cb4876d4bb11dcc821fb7`; frozen tail-risk checkpoint/report SHA256 `79d48b0ef63effea3642c2e08a20d8a6800f27f75e0ed97ed8050f146d4f326e`/`40524c98512aa98383f70aa0156b062276660572081ff1c4b808fdec460211cf`. Mapping-calibration scenes `66000000..66000999` and selection scenes `67000000..67000999`, each with two styles and four conditions for 8,000 images. Calibration pixel/feature/target/metric/risk SHA256 values `42ac94c8dfa0e66f5dabcec7975d5dcb54d54bc0f9ed7d08676642072080ef7d`, `715467622cd804ea9a401da14669557f639abf4ca90f829a493902f4c38476fc`, `a85eb9bf7b9b1fed642cb827afb22a213f8ae3720646211d1aa795ff84941889`, `acaa05cf036c8f2132d144a4f3457ded34edbac5eae545b959276e9b27951263`, and `82da4c445685eef0801f7ac6b697d904f94c8bf05afa68c58a1127dae7f520b5`; selection values `07f7a64fa3c06c3634d33ac3220d9627f192f91b5fece33d45ea753023332b3c`, `1d777ea2bbf22a8f7ec3b30078f87c2bc67146db7f687d218844ab14dc856e7d`, `57e06ac36382702e58c3b08455a55027e5d682fef482096ebf6788684830440b`, `d45ca3e23e390c1c1563c04253e4c25d9a341c5fb23101512e02d46568045d55`, and `4ddbfc726767e887504fbb0c6ef8e3c7f10016dc0be3e46f8feca9d5e08e6c33`. Risk-reference SHA256 `801ca31545470da3f75f3edc3a77623526770000eb4da6d9022153e9e3d0b714`; plan SHA256 `338f41b776fbbd57b525db5d0fb00f266794f9d6ed6ef3cbd3b0fa84a73a3527`; report SHA256 `6c24ca9c2f19d098889b5ae6bcdfad6ecbf0fbd981ae8bda30784989bba0f468`.
- Command: `python software/ai/train/select_risk_gated_metric.py`
- Result: FAIL fixed selection rule by three checks. Independent metric calibration yields rank 991 and normalized quantile `1.849293028`. Marginal scene coverage is 99.4%; 354/8,000 images are accepted (4.425%); accepted-image coverage is `0.994350282`; accepted-scene coverage is `0.992`; and zero accepted error exceeds 3 mm. Overall utility fails the 5% minimum. Full obstruction retains 19/2,000 (0.95%), just below 1%. Appearance, partial, and full accepted-image coverage are 100%; standard is `0.977777778` because 2 of 90 accepted standard images exceed their predicted radius. One mapping fit, zero new model fits, and zero optimizer updates.
- Artifacts: `train/select_risk_gated_metric.py`; `train/risk_gated_metric_v1_plan.json`; `eval/risk_gated_metric_v1_report.json`; `tests/test_risk_gated_metric.py`; `docs/IMAGE_DEPENDENT_UNCERTAINTY.md`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Synthetic mapping-calibration and selection evidence for one fixed gate. No independent confirmation was allocated after failure. The 3 mm threshold is a research tolerance, not a measured contact margin. No gate, runtime installation, physical-camera evidence, qualification, or motion authority. ModelMotionBatchV2 and arm/integration statuses are unchanged.
- Supersedes: none; the late-fusion and all earlier failed evidence remains preserved.
- Next dependency: On entirely fresh mapping-calibration and selection cohorts, preregister one slightly broader risk gate together with a small conservative radius inflation. Require recovery of overall and full-obstruction utility while removing low-risk radius violations under every unchanged final gate before independent confirmation.

### E-20260927-AI-380 — explicit risk-gated metric verification

- Stage: S1
- Lane: AI
- Commit: `e40263374929ca32bfc68c2f69785c690cc6a7a1` (frozen mapping source; tests and documentation committed in the successor)
- Inputs/fixtures: Same 16,000 fresh images, frozen specialists, independent metric calibration, risk reference, gate plan, and failed report as AI-379; exact hashes are recorded there and in the report.
- Command: `python -m pytest -q software/ai/tests/test_risk_gated_metric.py`
- Result: PASS: 2 tests in 2.02s. Tests verify conjunctive radius/risk eligibility, immutable lineage, exact grouped populations, risk-reference hash, all attached outputs, scene scores, rank and quantile, complete gated overall and conditional recounts, every fixed passing and failed check, and zero model fitting, optimizer, hardware, physical, qualification, or runtime authority.
- Artifacts: `tests/test_risk_gated_metric.py`; `eval/risk_gated_metric_v1_report.json`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Existing pytest-asyncio configuration warning. Recount consistency only; no physical assurance. Contract unchanged, so shared boundary tests were not triggered.
- Supersedes: none.
- Next dependency: Same as AI-379.

### E-20260927-AI-381 — explicit risk-gated metric snapshot review

- Stage: S1
- Lane: AI
- Commit: `e40263374929ca32bfc68c2f69785c690cc6a7a1` (frozen mapping source; final ledger append in successor)
- Inputs/fixtures: Repository snapshot containing the frozen gate study, failed report, verification test, interpretation, and shared ledger; exact hashes recorded in AI-379.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS: 6,334 paths, 998.8 MiB, 0 unresolved review findings, 14 reviewed synthetic fixtures.
- Artifacts: risk-gate plan/report; verification test; uncertainty documentation; shared ledger.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic repository review before final ledger append; not model, runtime, or physical assurance. No arm or integration status changes.
- Supersedes: none.
- Next dependency: Same as AI-379.

### E-20260927-AI-382 — inflated radius and broader risk-gate selection

- Stage: S1
- Lane: AI
- Commit: `f2bc5401e4c0472d9a0540e1253c52b7d5ea56d1` (frozen specialist lineage, 1.15 radius inflation, 40th-percentile risk gate, fresh populations, unchanged final gates, source, plan, and claim committed before inference; failed report, tests, interpretation, and claim removal committed in the successor)
- Inputs/fixtures: Frozen prior risk-gate report SHA256 `6c24ca9c2f19d098889b5ae6bcdfad6ecbf0fbd981ae8bda30784989bba0f468`; bounded-metric checkpoint/report SHA256 `c9ee03b9962e28443fbac7644cdfbb9c068e544aeb75cc58dc2ba8b6b494b16c`/`d0632877b0918c8b71417a8c34e6e580b12599c6144cb4876d4bb11dcc821fb7`; tail-risk checkpoint/report SHA256 `79d48b0ef63effea3642c2e08a20d8a6800f27f75e0ed97ed8050f146d4f326e`/`40524c98512aa98383f70aa0156b062276660572081ff1c4b808fdec460211cf`. Mapping-calibration scenes `68000000..68000999` and selection scenes `69000000..69000999`, each with two styles and four conditions for 8,000 images. Calibration pixel/feature/target/metric/risk SHA256 values `bda8c42df95efee8be43dfc3023d2db6c34e60c9886e2dc310cda3a9162efb22`, `5136017cf0c42a04b25c16df1418d45faf2ed3e73b8152694214be4a546435d8`, `d009c349eefe8b2ab96e52b90e64be952db8d4091973602e3017345c1edfb79a`, `d6c6be871eaf7a437e347191d6bcdb17d80663c423fb3db8656135db9e69bff2`, and `c9d2140388a6a58f5c08a736333ad6406c1991e15d057c1e03cfb00bc5f10576`; selection values `e8f1d0a43767ad558e0b488d1ec5718c5ab7ca8ac352080238beb5641b6fdbba`, `a15594ab03bac25302960997ba224765ca1f2199d88bab667c61e2352026abe1`, `05419b0b969231a892caf64799c71712f0fe5ef77c2a477638ac9294e38172ac`, `c9d9d57901fc32ea61e22dd78145b43c2cba1469a41d525a8512ae9195108f4c`, and `51a427d26cbd6b55b26cc3b7b1fdcdd9db41bfd4865d3272d8b3510e0a962e64`. Risk-reference SHA256 `bcacee7e443b3993c477e5142ce73d46000f9c68c9a4f5305801704ed287aefe`; plan SHA256 `8f40454c1dcef2692718f68251f5bc4c59b8c34125d0a456d83f665a3d6a77fd`; report SHA256 `5e6cbe95c00be3e3c77699ef69a05d128b7998b4110d2ce3131c2f045bf90c17`.
- Command: `python software/ai/train/select_inflated_risk_gate.py`
- Result: FAIL fixed selection rule by two utility checks. Independent metric calibration yields rank 991 and quantile `1.738460491`; the registered 1.15 multiplier yields applied quantile `1.999229564`. Marginal scene coverage is 99.3%; 280/8,000 images are accepted (3.5%); accepted-image and accepted-scene coverage are both 100%; every condition has 100% accepted-image coverage; and zero accepted error exceeds 3 mm. Overall utility fails the 5% minimum. Full obstruction retains 18/2,000 (0.9%), below 1%; partial obstruction is exactly 1%. One mapping fit, zero new model fits, and zero optimizer updates.
- Artifacts: `train/select_inflated_risk_gate.py`; `train/inflated_risk_gate_v1_plan.json`; `eval/inflated_risk_gate_v1_report.json`; `tests/test_inflated_risk_gate.py`; `docs/IMAGE_DEPENDENT_UNCERTAINTY.md`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Synthetic mapping-calibration and selection evidence for one fixed inflation and risk gate. No independent confirmation was allocated after failure. The 3 mm threshold is a research tolerance, not a measured contact margin. No threshold, mapping, runtime installation, physical-camera evidence, qualification, or motion authority. ModelMotionBatchV2 and arm/integration statuses are unchanged.
- Supersedes: none; the preceding risk-gate near miss and all earlier failed evidence remain preserved.
- Next dependency: Do not tune on 69M. On entirely fresh grouped populations, preregister a bounded improvement to the metric proposal or a new selection mechanism that can recover overall and full-obstruction utility while retaining the unchanged marginal, accepted-subset, conditional, and zero-above-tolerance gates before independent confirmation.

### E-20260927-AI-383 — inflated radius and broader risk-gate verification

- Stage: S1
- Lane: AI
- Commit: `f2bc5401e4c0472d9a0540e1253c52b7d5ea56d1` (frozen mapping source; tests and documentation committed in the successor)
- Inputs/fixtures: Same 16,000 fresh images, frozen specialists, empirical risk reference, inflated-radius plan, and failed report as AI-382; exact hashes are recorded there and in the report.
- Command: `python -m pytest -q software/ai/tests/test_inflated_risk_gate.py`
- Result: PASS: 2 tests in 1.95s. Tests verify that inflation is applied once after calibration, immutable lineage, both exact grouped populations, risk-reference hash, attached output reconstruction, scene scores, conformal rank and both quantiles, complete overall and conditional recounts, every fixed passing and failed check, and zero model fitting, optimizer, hardware, physical, qualification, or runtime authority.
- Artifacts: `tests/test_inflated_risk_gate.py`; `eval/inflated_risk_gate_v1_report.json`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Existing pytest-asyncio configuration warning. Recount consistency only; no physical assurance. Contract unchanged, so shared boundary tests were not triggered.
- Supersedes: none.
- Next dependency: Same as AI-382.

### E-20260927-AI-384 — inflated radius and broader risk-gate snapshot review

- Stage: S1
- Lane: AI
- Commit: `f2bc5401e4c0472d9a0540e1253c52b7d5ea56d1` (frozen mapping source; final ledger append in successor)
- Inputs/fixtures: Repository snapshot containing the frozen study, failed report, verification test, interpretation, and shared ledger; exact hashes recorded in AI-382.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS: 6,338 paths, 1,004.8 MiB, 0 unresolved review findings, 14 reviewed synthetic fixtures.
- Artifacts: inflated-risk-gate plan/report; verification test; uncertainty documentation; shared ledger.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic repository review before final ledger append; not model, runtime, or physical assurance. No arm or integration status changes.
- Supersedes: none.
- Next dependency: Same as AI-382.

### E-20260927-AI-385 — conservative gated late-fusion selection

- Stage: S1
- Lane: AI
- Commit: `4d3e4ff0061d0349ac8d98c3dd8f8ec203b08321` (frozen specialist lineage, previously fixed fusion gain, inflation and gate, fresh populations, unchanged final gates, source, plan, and claim committed before inference; failed report, tests, interpretation, and claim removal committed in the successor)
- Inputs/fixtures: Frozen late-fusion report SHA256 `8296328aaad2c98dc659d4d8d409d39513f4ede04fb3d0d8cc66249ca4d29edb`; frozen inflated-gate report SHA256 `5e6cbe95c00be3e3c77699ef69a05d128b7998b4110d2ce3131c2f045bf90c17`; bounded-metric checkpoint/report SHA256 `c9ee03b9962e28443fbac7644cdfbb9c068e544aeb75cc58dc2ba8b6b494b16c`/`d0632877b0918c8b71417a8c34e6e580b12599c6144cb4876d4bb11dcc821fb7`; tail-risk checkpoint/report SHA256 `79d48b0ef63effea3642c2e08a20d8a6800f27f75e0ed97ed8050f146d4f326e`/`40524c98512aa98383f70aa0156b062276660572081ff1c4b808fdec460211cf`. Mapping-calibration scenes `70000000..70000999` and selection scenes `71000000..71000999`, each with two styles and four conditions for 8,000 images. Calibration pixel/feature/target/metric/risk SHA256 values `7686f7f0fa3ce7e79b6d1d106d120d879fcd03452b8912afbfa25fb5edf2ac67`, `f50c7e7b3fc7698e05596e9d8ca0aafb54eb692af900b9c2df0baf0f40e799bd`, `85cc754463c489462265d0edfa8ff03f1d9c3969c95951f1471188cef3c95c07`, `752bc714639c222afb91640cde86a40995b86a3a546efbc4a3fdc0cf79ea6169`, and `9c97929febb646937ecf984889bce2f89fd799ee0a6fb36dd545f161d9e4f8a5`; selection values `2a2ade139ed9c87cdde828b132becb7a65c94d382985d4177981e57c327cb7f2`, `afa9c284d92b2b5b0518b717c66e9bb46d23d70492e58cb0081d5f204b29a044`, `2dde182398436f9b5bddc001dab7dde07d3ee5ea7da2bc58e2c6fbb2ddd7753c`, `d54646b625c5ae2f94501c2ccca554fb61a81ba47628d98e988fb904c34021d7`, and `173113bf66915ce755a622cb7b5075a9a8c5fb2b2704510830c6a1bc0443b82b`. Risk-reference SHA256 `8ca149c2faa6720166262ee8d2efc203ae28d5bdb5e4239b4d14d532415e0cc8`; plan SHA256 `225a87070752246d7e5c7d6e671457c3c41533d79484161c898c7af1a210ba7e`; report SHA256 `14c86c35894f35424d672cb4a7d31b57b8953ff70bab3c933f11067edaf0609b`.
- Command: `python software/ai/train/select_conservative_gated_late_fusion.py`
- Result: FAIL fixed selection rule. Rank-991 calibration yields quantile `2.150357817`; the frozen 1.15 inflation yields `2.472911490`. Marginal scene coverage is 99.8%; 706/8,000 images are accepted (8.825%); accepted-image coverage is `0.991501416`; accepted-scene coverage is `0.995575221`; and every condition passes utility. Six accepted images exceed their predicted radius, including two full-obstruction errors above 3 mm. Partial and full accepted-image coverage fail at `0.977272727` and `0.970588235`. One mapping fit, zero new model fits, and zero optimizer updates.
- Artifacts: `train/select_conservative_gated_late_fusion.py`; `train/conservative_gated_late_fusion_v1_plan.json`; `eval/conservative_gated_late_fusion_v1_report.json`; `tests/test_conservative_gated_late_fusion.py`; `docs/IMAGE_DEPENDENT_UNCERTAINTY.md`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Synthetic mapping-calibration and selection evidence for one fixed combination of earlier components. No independent confirmation was allocated after failure. The 3 mm threshold is a research tolerance, not a measured contact margin. No mapping, runtime installation, physical-camera evidence, qualification, or motion authority. ModelMotionBatchV2 and arm/integration statuses are unchanged.
- Supersedes: none; all component studies and failures remain preserved.
- Next dependency: Do not tune on 71M. On entirely fresh grouped training-selection populations, preregister an obstruction-aware metric uncertainty study that targets the partial/full tail directly. Retain the recovered utility as an explicit later calibration goal while preserving all current coverage and zero-above-tolerance gates.

### E-20260927-AI-386 — conservative gated late-fusion initial verification

- Stage: S1
- Lane: AI
- Commit: `4d3e4ff0061d0349ac8d98c3dd8f8ec203b08321` (frozen mapping source; verification implementation and correction committed in the successor)
- Inputs/fixtures: Same 16,000 fresh images, frozen specialists, empirical risk reference, conservative gated-fusion plan, and failed report as AI-385; exact hashes are recorded there and in the report.
- Command: `python -m pytest -q software/ai/tests/test_conservative_gated_late_fusion.py`
- Result: FAIL: 1 failed, 1 passed in 2.03s. The report-recount test passed. The arithmetic unit test used exact equality for binary floating-point multiplication and observed `3.0 * 1.15 * 2.0 != 6.9` at machine representation. This was a test assertion defect, not an evidence or model discrepancy.
- Artifacts: `tests/test_conservative_gated_late_fusion.py`; `eval/conservative_gated_late_fusion_v1_report.json`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Failed verification preserved before correction. No study values or report data changed. Existing pytest-asyncio configuration warning. Contract unchanged, so shared boundary tests were not triggered.
- Supersedes: none.
- Next dependency: Replace the exact floating-point assertion with an approximate numeric comparison and rerun the identical verification command.

### E-20260927-AI-387 — conservative gated late-fusion corrected verification

- Stage: S1
- Lane: AI
- Commit: `4d3e4ff0061d0349ac8d98c3dd8f8ec203b08321` (frozen mapping source; corrected test and documentation committed in the successor)
- Inputs/fixtures: Same artifacts as AI-386; only the unit assertion uses `pytest.approx(6.9)` after the preserved exact-equality failure.
- Command: `python -m pytest -q software/ai/tests/test_conservative_gated_late_fusion.py`
- Result: PASS: 2 tests in 1.96s. Tests verify fusion arithmetic before one inflation, immutable lineage, both exact grouped populations, risk-reference hash, fused-output reconstruction, scene scores, conformal rank and both quantiles, complete overall and conditional recounts, every fixed passing and failed check, and zero model fitting, optimizer, hardware, physical, qualification, or runtime authority.
- Artifacts: `tests/test_conservative_gated_late_fusion.py`; `eval/conservative_gated_late_fusion_v1_report.json`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Existing pytest-asyncio configuration warning. Recount consistency only; no physical assurance. Contract unchanged, so shared boundary tests were not triggered.
- Supersedes: none; AI-386 remains preserved as failed evidence.
- Next dependency: Same as AI-385.

### E-20260927-AI-388 — conservative gated late-fusion snapshot review

- Stage: S1
- Lane: AI
- Commit: `4d3e4ff0061d0349ac8d98c3dd8f8ec203b08321` (frozen mapping source; final ledger append in successor)
- Inputs/fixtures: Repository snapshot containing the frozen study, failed report, corrected verification test, interpretation, preserved failed verification, and shared ledger; exact hashes recorded in AI-385.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS: 6,342 paths, 1,011.5 MiB, 0 unresolved review findings, 14 reviewed synthetic fixtures.
- Artifacts: conservative gated-fusion plan/report; verification test; uncertainty documentation; shared ledger.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic repository review before final ledger append; not model, runtime, or physical assurance. No arm or integration status changes.
- Supersedes: none.
- Next dependency: Same as AI-385.

### E-20260927-AI-389 — obstruction-weighted metric-head selection

- Stage: S1
- Lane: AI
- Commit: `ae07a269fee863edee6e58cf4904fde719daabe6` (fixed architecture, condition weights, objective, prior-comparison gates, fresh populations, source, plan, and claim committed before feature extraction or training; passing report, checkpoint, tests, interpretation, and claim removal committed in the successor)
- Inputs/fixtures: Training scenes `72000000..72001999` (16,000 images) and selection scenes `73000000..73000999` (8,000 images), each with two styles and four conditions. Training pixel/feature/target SHA256 values `3ae3712d50c397e625fb3c6e7a104acfce71036adaa70c64dda99d008807b1ad`, `6c662c7911f9834546f7bb77f4a9222d5a3a9867714b060788c911626361cce5`, and `03fece73e3fd2d22612a81df3165e3f033dce0c802f55de3afa93630a3cdaf85`; selection values `d9d4e508e3e921cc9fff7c9d5a5ae72d4ed9f1a5b9281b39645eb337007c96d6`, `7f9a3448caf02554c84a30a7281532b501975c9dfd060a9538f230b1094ccc69`, and `09c514e42aebefeba3a8f048e3ebe6c014ba822e4077694a1cf2380e06b842ac`; all pose prediction hashes are retained in the report. Prior bounded-head checkpoint/report SHA256 `c9ee03b9962e28443fbac7644cdfbb9c068e544aeb75cc58dc2ba8b6b494b16c`/`d0632877b0918c8b71417a8c34e6e580b12599c6144cb4876d4bb11dcc821fb7`; trigger report SHA256 `14c86c35894f35424d672cb4a7d31b57b8953ff70bab3c933f11067edaf0609b`. Plan SHA256 `eec1b92f1e9bfa632a5bdd106ac25e00116f455c96bccf760a5d4ee1ea562857`; report SHA256 `4ec0f5979b6739c28c56107f1296c05fcacbb6f982f1e05e3ef97162909b09f9`; checkpoint SHA256 `433d134b92b710566a0798c38dc344d1a768d2c87e44ef92135ffc075dfa9662`; normalization SHA256 `3c691b6b9baf0ffbfe61c16ac94ae6c5cbec27f05358e780f1e199d06105a591`; new/prior selection prediction SHA256 values `38aa46e73fc6c7bbe8c3008530de5f33143e434c4127c8feb552873a2b775177` and `5910a12aacf6b9fdb3da83f331e0d72abe270599138d8af6fc5a614159049204`.
- Command: `python software/ai/train/train_obstruction_weighted_metric_head.py`
- Result: PASS fixed selection rule. The 52,481-parameter head trained for 20 epochs with condition weights 1/1/2/4 and a total training weight of 32,000, completing 2,500 optimizer updates. On selection, overall coverage is `0.94775`; standard, appearance-shift, partial, and full coverage are `0.973`, `0.963`, `0.9505`, and `0.9045`. The frozen prior head reaches `0.927`, `0.954`, `0.942`, `0.94`, and `0.872`, so partial improves by 1.05 points and full by 3.25 points. Mean pinball loss improves from prior `0.071729333` to `0.069618193`; median bound is `2.495371342` mm versus prior `2.255104303` mm and weighted constant `3.668837070` mm. Scene AUROC is `0.734116928`; conditional image AUROCs are standard `0.949362504`, appearance `0.846142134`, partial `0.851990450`, and full `0.752107023`. All outputs remain within `[0.25,10.0]` mm and every frozen check passes. One model fit and zero calibration fits.
- Artifacts: `train/train_obstruction_weighted_metric_head.py`; `train/obstruction_weighted_metric_head_v1_plan.json`; `eval/obstruction_weighted_metric_head_v1_report.json`; `results/obstruction_weighted_metric_head_v1/model.pt`; `tests/test_obstruction_weighted_metric_head.py`; `docs/IMAGE_DEPENDENT_UNCERTAINTY.md`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Synthetic training-selection evidence for one seed and one fixed condition-weight schedule. Synthetic condition labels influence training loss but are not model inputs. This selects only a research feature; no metric calibration, independent confirmation, runtime installation, physical-camera evidence, qualification, or motion authority. ModelMotionBatchV2 and arm/integration statuses are unchanged.
- Supersedes: none; the prior bounded head and all failed mapping evidence remain preserved.
- Next dependency: Freeze one mapping-calibration and selection study on entirely fresh grouped populations using this checkpoint with the existing tail-risk specialist. Preserve the current marginal, utility, conditional accepted-subset, and zero accepted errors above 3 mm gates before any independent confirmation.

### E-20260927-AI-390 — obstruction-weighted metric-head verification

- Stage: S1
- Lane: AI
- Commit: `ae07a269fee863edee6e58cf4904fde719daabe6` (frozen training-selection source; tests and documentation committed in the successor)
- Inputs/fixtures: Same 24,000 images, fixed 1/1/2/4 weight schedule, prior head, new checkpoint, plan, and passing report as AI-389; exact hashes are recorded there and in the report.
- Command: `python -m pytest -q software/ai/tests/test_obstruction_weighted_metric_head.py`
- Result: PASS: 2 tests in 2.14s. Tests verify explicit condition weights and weighted pinball arithmetic, immutable lineage, checkpoint integrity, both exact grouped populations, training weight sum and weighted constant, complete candidate/prior/constant metric recounts, ranking metrics, every fixed passing check, and zero calibration, hardware, physical, qualification, or runtime authority.
- Artifacts: `tests/test_obstruction_weighted_metric_head.py`; `eval/obstruction_weighted_metric_head_v1_report.json`; `results/obstruction_weighted_metric_head_v1/model.pt`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Existing pytest-asyncio configuration warning. Recount consistency only; no physical assurance. Contract unchanged, so shared boundary tests were not triggered.
- Supersedes: none.
- Next dependency: Same as AI-389.

### E-20260927-AI-391 — obstruction-weighted metric-head snapshot review

- Stage: S1
- Lane: AI
- Commit: `ae07a269fee863edee6e58cf4904fde719daabe6` (frozen training-selection source; final ledger append in successor)
- Inputs/fixtures: Repository snapshot containing the frozen study, passing report, selected research checkpoint, verification test, interpretation, and shared ledger; exact hashes recorded in AI-389.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS: 6,346 paths, 1,017.8 MiB, 0 unresolved review findings, 14 reviewed synthetic fixtures.
- Artifacts: obstruction-weighted plan/report/checkpoint; verification test; uncertainty documentation; shared ledger.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic repository review before final ledger append; not model, runtime, or physical assurance. No arm or integration status changes.
- Supersedes: none.
- Next dependency: Same as AI-389.

### E-20260927-AI-392 — obstruction-weighted metric risk-gate selection

- Stage: S1
- Lane: AI
- Commit: `fe9de23ed3bbdf7bef4c91f2c4c0e51d2c66d62c` (selected metric and risk lineage, direct calibration, fixed 40th-percentile gate, fresh populations, unchanged final gates, source, plan, and claim committed before inference; passing report, tests, interpretation, and claim removal committed in the successor)
- Inputs/fixtures: Obstruction-weighted metric checkpoint/report SHA256 `433d134b92b710566a0798c38dc344d1a768d2c87e44ef92135ffc075dfa9662`/`4ec0f5979b6739c28c56107f1296c05fcacbb6f982f1e05e3ef97162909b09f9`; tail-risk checkpoint/report SHA256 `79d48b0ef63effea3642c2e08a20d8a6800f27f75e0ed97ed8050f146d4f326e`/`40524c98512aa98383f70aa0156b062276660572081ff1c4b808fdec460211cf`. Mapping-calibration scenes `74000000..74000999` and selection scenes `75000000..75000999`, each with two styles and four conditions for 8,000 images. Calibration pixel/feature/target/metric/risk SHA256 values `25e3bb2d463d9b8bb726ab99bc2a0def52b076893f21374e2c5d780a4e223284`, `03b159fa0b28eec3da5181db4d9fbd5ea9ca1b3026c94ccc89b88089aeb49978`, `0a13ce4b93735e62c4abbf7fd2478d59de69ab574af013ae64193ebef3b65e94`, `da9aa238fadba92a3401bda33e4e8b545f8883c15987dfd98b0b93252aa98b5a`, and `9639324839685043cc520989ea345e0eeec704a286bc4c727f0487e5f431d8a7`; selection values `d6598df6961367b35660d5c65232ab6020d529f719b4bd2870ed502a37f13184`, `e48e15db76721bb68d84e7d94f69e28efaabdc8bd33f0146c4646fa9d2aa8e18`, `5c9f30a9c8ab869b088e96dd64a8402103e2449a9fdaba671b88ab9148ada782`, `b4591aece105dee7703db0f18b172967a0727516ad01f6ea626fc1ca00d22c8f`, and `4c53cfc485097ffd4d928a7704b1a7f938fac57b2ec6b86b1ae0f37c5ae47822`. Risk-reference SHA256 `5b7cd690c08027e1bba3346602fecb68e87d63168a0beccf4cf8b662089682da`; plan SHA256 `8c895befdfdcfad92e8405b5e993c68f6b266165d8f1894c68c528a7a3088684`; report SHA256 `0ea5d5e07a49390ac6fb5c967d31f0730ed69ba55c23ee3dd2c08844c4d37c02`.
- Command: `python software/ai/train/select_obstruction_weighted_risk_gate.py`
- Result: PASS fixed selection rule. Rank-991 direct metric calibration yields normalized quantile `1.678368111`. Marginal scene coverage is 99.6%; 454/8,000 images are accepted (5.675%); accepted-image and accepted-scene coverage are both 100%; zero accepted images exceed their predicted radius or 3 mm. Condition acceptance is standard 6.3%, appearance shift 10.8%, partial 3.15%, and full 2.45%, with 100% accepted-image coverage in every condition. One mapping fit, zero new model fits, and zero optimizer updates.
- Artifacts: `train/select_obstruction_weighted_risk_gate.py`; `train/obstruction_weighted_risk_gate_v1_plan.json`; `eval/obstruction_weighted_risk_gate_v1_report.json`; `tests/test_obstruction_weighted_risk_gate.py`; `docs/IMAGE_DEPENDENT_UNCERTAINTY.md`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Synthetic mapping-calibration and selection evidence for one fixed gate. This is selection, not independent confirmation. The 3 mm threshold is a research tolerance, not a measured contact margin. No mapping installation, runtime behavior, physical-camera evidence, qualification, or motion authority. ModelMotionBatchV2 and arm/integration statuses are unchanged.
- Supersedes: none; the selected metric feature and all earlier mapping evidence remain preserved.
- Next dependency: Freeze this exact checkpoint pair, 74M risk reference, normalized quantile, gate, and acceptance rule before evaluating one entirely fresh independent confirmation population. No recalibration or selection-population adjustment is permitted.

### E-20260927-AI-393 — obstruction-weighted metric risk-gate verification

- Stage: S1
- Lane: AI
- Commit: `fe9de23ed3bbdf7bef4c91f2c4c0e51d2c66d62c` (frozen mapping source; test and documentation committed in the successor)
- Inputs/fixtures: Same 16,000 fresh images, frozen metric/risk specialists, empirical risk reference, direct calibration plan, and passing report as AI-392; exact hashes are recorded there and in the report.
- Command: `python -m pytest -q software/ai/tests/test_obstruction_weighted_risk_gate.py`
- Result: PASS: 1 test in 1.98s. The test verifies immutable lineage, both exact grouped populations, risk-reference hash, attached output reconstruction, scene scores, conformal rank and quantile, complete overall and conditional recounts, every fixed passing check, zero accepted violations, and zero model fitting, optimizer, hardware, physical, qualification, or runtime authority.
- Artifacts: `tests/test_obstruction_weighted_risk_gate.py`; `eval/obstruction_weighted_risk_gate_v1_report.json`.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Existing pytest-asyncio configuration warning. Recount consistency only; no physical assurance. Contract unchanged, so shared boundary tests were not triggered.
- Supersedes: none.
- Next dependency: Same as AI-392.

### E-20260927-AI-394 — obstruction-weighted metric risk-gate snapshot review

- Stage: S1
- Lane: AI
- Commit: `fe9de23ed3bbdf7bef4c91f2c4c0e51d2c66d62c` (frozen mapping source; final ledger append in successor)
- Inputs/fixtures: Repository snapshot containing the frozen study, passing report, verification test, interpretation, and shared ledger; exact hashes recorded in AI-392.
- Command: `python scripts/audit_github_snapshot.py`
- Result: PASS: 6,351 paths, 1,024.0 MiB, 0 unresolved review findings, 14 reviewed synthetic fixtures.
- Artifacts: obstruction-weighted risk-gate plan/report; verification test; uncertainty documentation; shared ledger.
- Hardware writes: 0
- Physical movements: 0
- Limitations: Heuristic repository review before final ledger append; not model, runtime, or physical assurance. No arm or integration status changes.
- Supersedes: none.
- Next dependency: Same as AI-392.

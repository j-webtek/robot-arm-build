# Tactevra AI/arm evidence ledger

- **Document status:** Append-only evidence record
- **Owners:** AI/model workstream, arm/runtime workstream, and integration reviewers
- **Split from the shared workplan:** 2026-09-27
- **Authority:** Evidence history only; this document grants no hardware authority

This file preserves the detailed results produced by the two development lanes
and their shared integration gates. For current stages, ownership, acceptance
criteria, and the required evidence-row format, use the
[shared AI-to-arm workplan](SHARED_AI_ARM_WORKPLAN.md#evidence-ledger-rules).

Entries are chronological records, not a claim that every result remains the
current implementation. Read each row's commit, result, limitations, and next
dependency. Failures remain visible, and corrections receive a new row.

Historical identifiers are preserved exactly. The source record contains a
duplicate `E-20260926-INT-001` identifier; both rows remain unchanged to avoid
rewriting history. New entries must use a unique evidence ID.

## Evidence entries

### E-20260926-INT-001 — shared v1 boundary baseline

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

### E-20260926-AI-001 — conservative synthetic localization study

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

### E-20260926-AI-002 — actual prediction key-margin study

- Stage: S1 and S3
- Lane: AI
- Commit: `7056603` (short baseline identity; use full SHA in future rows)
- Change: evaluated the already-selected robust checkpoint's actual displaced
  predictions against independently rendered rotated key regions while retaining
  the previously fixed 6.037862 mm uncertainty radius.
- Inputs/fixtures: `software/ai/eval/prediction_margin_v0.manifest.json`, fresh
  seeds 13000000–13000099, three conditions per seed
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

### E-20260926-AI-003 — S1 AI semantic proposal and unchanged boundary regression

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


### E-20260926-AI-004 — repository snapshot audit findings retained

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


### E-20260926-AI-005 — analytic oriented-target acceptance cases

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


### E-20260926-AI-006 — geometry increment audit retains existing findings

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


### E-20260926-ARM-001 — strict v2 arm contract and admission boundary

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


### E-20260926-ARM-002 — v2 increment audit retains existing findings

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


### E-20260926-ARM-003 — monotonic pre-planner lease and registry recheck

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


### E-20260926-ARM-004 — AI build review and coherent trusted registry snapshot

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


### E-20260926-ARM-005 — trusted-registry increment audit

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
### E-20260926-AI-007 — v2 typed producer assembly and consumer regression

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


### E-20260926-AI-008 — v2 assembly audit retains findings

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


### E-20260926-INT-001 — actual v2 assembler bytes through trusted arm gates

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


### E-20260926-INT-002 — shared v2 integration audit retains findings

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


### E-20260926-ARM-006 — v2 proposals enter arm-owned measured planning policy

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


### E-20260926-ARM-007 — v2 planner-policy increment audit retains findings

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
### E-20260926-AI-009 — precision binding test discovery failure

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


### E-20260926-AI-010 — precision binding dependency failure

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


### E-20260926-AI-011 — precision binding preflight and shared-gate regression

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


### E-20260926-AI-012 — precision binding repository audit

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


### E-20260926-ARM-008 — actual v2 bytes produce a zero-hardware shadow trace

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


### E-20260926-ARM-009 — shadow-trace increment audit retains findings

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


### E-20260926-ARM-010 — ordered v2 coordinator blocks unsafe envelope migration

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


### E-20260926-ARM-011 — v2 coordinator audit retains findings

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
### E-20260926-AI-013 — capture receipt binding and confidence-method plan

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


### E-20260926-AI-014 — capture-binding audit findings retained

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


### E-20260926-ARM-012 — dual-lineage v2 trajectory-envelope contract

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


### E-20260926-ARM-013 — v2 envelope audit retains findings

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
### E-20260926-AI-015 — freeze localization-confidence research protocol

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


### E-20260926-AI-016 — confidence protocol audit findings retained

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


### E-20260926-AI-017 — frozen-feature confidence training fails research criteria

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

### E-20260926-AI-018 — confidence metric regression

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

### E-20260926-AI-019 — confidence training audit findings retained

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

### E-20260926-INT-003 — raw request reaches the actual v2 arm shadow path

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

### E-20260926-INT-004 — S2 raw-runner audit findings retained

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

### E-20260926-AI-020 — local image feature development comparison

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

### E-20260926-AI-021 — development scoring regression

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

### E-20260926-AI-022 — local-feature audit findings retained

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


### E-20260926-AI-023 — development inference resolution sensitivity

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


### E-20260926-AI-024 — resolution diagnostic audit findings retained

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


### E-20260926-AI-025 — matched-resolution development fine-tuning

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

### E-20260926-AI-026 — matched-resolution evidence checks

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

### E-20260926-AI-027 — matched-resolution audit findings retained

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


### E-20260926-AI-028 — merged boundary regression

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


### E-20260926-AI-029 — reject local-edge refinement after development comparison

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

### E-20260926-AI-030 — refinement bound and edge-case tests

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


### E-20260926-AI-031 — local-refinement audit findings retained

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

### E-20260926-ARM-014 — sealed-envelope T102 zero-write preview

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

### E-20260926-ARM-015 — S4 preview audit findings retained

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

### E-20260926-ARM-016 — zero-write sole-writer lifecycle and restart closure

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

### E-20260926-ARM-017 — sole-writer lifecycle audit findings retained

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

### E-20260926-AI-032 — translation and rotation development decomposition

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

### E-20260926-AI-033 — decomposition consistency checks

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

### E-20260926-AI-034 — decomposition audit findings retained

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


### E-20260926-AI-035 — translation-weighted development candidate

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

### E-20260926-AI-036 — paired training evidence validation

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

### E-20260926-AI-037 — translation-training audit findings retained

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

### E-20260926-ARM-018 — published zero-write controller boundary

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

### E-20260926-ARM-019 — zero-write schema audit findings retained

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

### E-20260926-ARM-020 — reviewed-fixture integration verification

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

### E-20260926-ARM-021 — installed-controller qualification gate

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

### E-20260926-ARM-022 — controller-gate repository audit

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

### E-20260926-ARM-023 — controller-gate release-doc integration

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

### E-20260926-ARM-024 — passive r96 evidence candidate and live identity capture

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

### E-20260926-ARM-025 — passive-evidence integration verification

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

### E-20260926-ARM-026 — r96 command-surface compatibility decision

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

### E-20260926-ARM-027 — command-surface integration verification

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

### E-20260926-ARM-028 — production runtime executable contract

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

### E-20260926-ARM-029 — production runtime contract integration verification

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

### E-20260926-ARM-048 — sole-writer dispatch and settling rehearsal

- Stage: S4
- Lane: ARM
- Change: replaced caller-authored lifecycle start acknowledgements with a
  hash-verified dispatch receipt emitted after the supervisor permit is consumed
  at one exact encoded write boundary. Added a single-owner, single-use,
  hardware-incapable writer rehearsal and closed dispatch, settlement, and
  execution schemas.
- Runtime behavior: validates exact admission/permit/goal identity, encodes
  before consuming authority, performs exactly one write attempt, records
  payload and retained-byte hashes, and requires fresh ordered consecutive
  T=1051 pose samples inside explicit position/angle tolerances for a completed
  motion lifecycle. Zero write is `FAILED`; partial write, disconnect after
  write, stale/missing/invalid feedback, or unsettled arrival is `UNCERTAIN`.
- Retry behavior: all dispatch outcomes consume the claimed session and permit;
  every terminal explicitly denies retry and follow-on movement.
- Artifacts: `reviewed_motion_sole_writer_v1.py`, three closed v1 schemas,
  dispatch-receipt lifecycle binding, fault/settling/expiry/cross-binding tests,
  public exports, and portable CI selection.
- Artifact identity: writer and lifecycle-bridge implementation SHA-256 values
  `64510f6bfbadd42f9cb5da7f0b91cadc15e249124664a75effe19701dd894c1c`
  and `1fb9ae620c7718d0d534c2fcfff30aada94c1ee557860a2bdb4efe50db35a7d3`;
  dispatch, settlement, and execution schema SHA-256 values
  `821a626407bb3f255cc734a54c534d8a7409f982478bb9bfb726b3760b8fe12b`,
  `c4f528699cacd3fc2876e1bc032777f42c41573a592f8c37004d32b29e60d824`,
  and `6121e860323981dad22bd8155042bc6746355127ef68415a752d0c71bff41056`.
- Results: focused ARM-047/048 suite PASS, 14 tests; portable shared AI/arm
  selection PASS, 224 tests in 32.12 seconds; documentation checks PASS, 26
  self-tests; compile and diff checks PASS.
- Evidence status: deterministic in-memory evidence only. The I/O fixture has
  no port, serial factory, callback, socket, or device handle.
- Hardware writes: 0
- Physical movements: 0
- Limitations: no authentic controller receipt, native transport write,
  independently acquired feedback, or independent keyboard/phone outcome is
  claimed. A settled replay proves only the arm-side state machine and evidence
  contract.
- Supersedes: ARM-047's caller-supplied lifecycle start seam. It does not
  supersede native writer enablement or physical qualification.
- Next dependency: bind the qualified receipt semantics to the separately
  reviewed native sole-writer boundary, correlate independently acquired fresh
  feedback, and require independent task-outcome evidence before advancing an
  ordered model sequence. Native enablement requires its own explicit physical
  authorization and evidence review.

### E-20260926-ARM-049 — reviewed native-shaped T=102 runtime bridge

- Stage: S4
- Lane: ARM
- Change: resolved the ARM-048 Cartesian-fixture versus production-runtime
  mismatch by binding the exact supervisor-issued permit and lifecycle to the
  deterministic ordered joint frame used by the trajectory encoder and
  controller contract: `T`, `base`, `shoulder`, `elbow`, `wrist`, `roll`,
  `hand`, `spd`, `acc` (`T=102`).
- Runtime binding: one decoded T=102 goal is content-bound to the review and
  permit, writer identity, controller session, configuration epoch, encoding
  profile, sequence, correlation ID, frame deadline, and encoded byte digest.
  Authority is consumed immediately before one modeled outbound-byte write.
- Receipt and feedback behavior: a full modeled write requires one exact
  correlated `T=1021` `ACCEPTED_ONCE` acknowledgment and fresh monotonic
  `T=1051` joint feedback. Two consecutive samples inside the configured joint
  tolerance are required for modeled settlement. Zero write is `FAILED`;
  partial/disconnected write, mismatched acknowledgment, stale/malformed
  feedback, collection failure, or unsettled arrival is `UNCERTAIN`. Every
  single-action outcome terminally closes that runtime instance and is never
  retried.
- Artifacts: `reviewed_t102_runtime_bridge_v1.py`, strengthened production
  runtime return types and write-fault latches, two closed v1 schemas, public
  exports, compatibility/fault/session/expiry/settling tests, and portable CI
  selection.
- Artifact identity: runtime contract, incapable sole-writer, and T=102 bridge
  implementation SHA-256 values
  `3a5a5bf651240211f250791d7f5a778df3e1135c49ab6b0d1d1b1ba38b110abd`,
  `3ecab0ee2e45ae9bfb439fd77ff7dfe3074ce518a51992c629a3977fd59645d5`,
  and `dc57e7382dd4fd1a3b61c8d0668257393ec722d7bf8e21bb9beb0aaacbc2e7bc`;
  settlement and execution schema SHA-256 values
  `e9b00aa0621db1e37cd2cb3b4f85df380b61cb6cf197f473eaca2748fb0f62bc`
  and `60dbc94c3717b90e13c679b55cdacc3610d5de2d3f9df8d5c5994a20169210d6`.
- Results: focused runtime/permit/writer/T=102 suite PASS, 49 tests; portable
  shared AI/arm selection PASS, 233 tests in 37.28 seconds; documentation
  checks PASS, 29 self-tests plus maintained-link/title validation; compile and
  diff checks PASS.
- Evidence status: deterministic in-memory evidence only. The I/O fixture owns
  no serial factory, port, socket, callback, device handle, controller process,
  or firmware operation.
- Hardware writes: 0
- Physical movements: 0
- Limitations: `T=1021` and `T=1051` inputs are modeled test bytes, not
  independently acquired controller evidence. A completed rehearsal proves
  contract compatibility and fail-closed lifecycle behavior; it does not prove
  an authentic controller receipt, physical arrival, key contact, or task
  outcome.
- Supersedes: ARM-048's Cartesian final-boundary fixture and its unresolved
  production-runtime shape mismatch. It does not supersede native-writer
  enablement, physical qualification, or independent task observation.
- Next dependency: externally review and qualify a separately implemented
  native sole-writer transport that preserves this exact T=102/session/epoch/
  profile contract, then acquire authentic controller acknowledgment, joint
  feedback, and independent task-outcome evidence under explicit physical-test
  authorization.

### E-20260926-ARM-050 — durable native T=102 handoff boundary

- Stage: S4
- Lane: ARM
- Change: added a filesystem-only durable handoff between ARM-049's exact
  reviewed T=102 frame and a future separately reviewed native sole writer. An
  immutable prepared record binds the review, permit, decoded goal, encoded
  payload, frame, correlation, sequence, writer, controller session,
  configuration epoch, encoding profile, adapter candidate, and frame lifetime.
- Dispatch-boundary behavior: an exclusive `claim.json` marker is flushed before
  any future transport may open. Exactly one concurrent claimant succeeds. A
  restart before the claim is safely cancellable and requires fresh replanning
  and authority; a restart after the claim is
  `RETRY_FORBIDDEN_DISPATCH_UNCERTAIN`, even if no write was ultimately made.
  A malformed or truncated claim marker fails closed instead of resuming.
- Rejection behavior: duplicate preparation, duplicate/concurrent claim, stale
  claim, crossed writer/session/epoch/profile/payload, tampered canonical data,
  symlink roots, and unexpected journal entries reject without opening a
  transport or writing controller bytes.
- Artifacts: `native_t102_handoff_journal_v1.py`; closed prepared, writer-claim,
  and recovery-snapshot schemas; public exports; concurrency, restart,
  crossing, staleness, tamper, and filesystem-boundary tests; portable CI
  selection.
- Artifact identity: implementation SHA-256
  `4e4da8347943184a0cfc6fe03f56ba47ae08989d740310c4bcdce1e63e4e3da0`;
  prepared, writer-claim, and snapshot schema SHA-256 values
  `33b71855fe653db978c5e96de0068c46d349522bce7ac22019a7c9d38d6fe9a9`,
  `9f77344d3ccb7ed2782ea6a3d6da29d9222c411afe3c18dc0ef184c942b1c92a`,
  and `8dd1648761ae5244de9473891ed9018c005fe2ecb727116ab886124b48408d28`.
- Results: focused runtime/T=102/handoff suite PASS, 47 tests; portable shared
  AI/arm selection PASS, 245 tests in 36.19 seconds; compile and diff checks
  PASS.
- Evidence status: deterministic local-filesystem evidence only. The module has
  no serial factory, port, socket, device handle, callback, controller process,
  firmware operation, or transport-open function.
- Hardware writes: 0
- Physical movements: 0
- Limitations: the writer claim deliberately grants no transport or physical
  authority and contains no authentic controller receipt. Once claimed, even a
  known pre-open crash requires manual reconciliation rather than resend. This
  is conservative ambiguity containment, not proof of native execution.
- Supersedes: ARM-049's volatile-only final handoff boundary. It does not
  supersede native-adapter review, authentic receipt/feedback acquisition,
  physical qualification, or independent task observation.
- Next dependency: implement and independently review a native executor that
  accepts only this exact claimed handoff plus fresh single-use authority,
  opens one pinned controller transport, publishes an authentic byte-accounted
  receipt, and never resends an ambiguous claim. Any physical use remains a
  separate explicitly authorized test.

### E-20260926-ARM-051 — claimed native T=102 executor rehearsal

- Stage: S4
- Lane: ARM
- Change: extended ARM-050 with read-only revalidation of the exact claimed
  handoff and added a hardware-incapable executor rehearsal. A fresh authority
  binds the external approval-record digest, durable claim, frame, writer,
  controller session, and bounded monotonic lifetime. It has exactly one use
  and explicitly grants neither hardware access nor physical authority.
- Executor behavior: after revalidating the claim, adapter, reviewed admission,
  encoded frame, session, profile, epoch, and freshness, the boundary consumes
  authority before one exact in-memory open/write/close lifecycle. The receipt
  binds the claimed and prepared records, authority, approval record, frame,
  payload digest, pinned endpoint identity, correlation, writer, session,
  requested byte count, confirmed byte count, API attempt counts, and a closed
  error code. It never equates recorded bytes with controller receipt or
  physical movement.
- Failure behavior: unclaimed, stale, crossed, or tampered handoffs reject
  before open. Expired/crossed/reused authority rejects before open. Concurrent
  attempts have one authority consumer. Open failure, zero write, partial
  write, write exception, invalid byte count, and uncertain close are terminal
  with automatic retry forbidden. The rehearsal rejects subclasses so a real
  transport cannot be smuggled through this qualification boundary.
- Artifacts: `native_t102_executor_rehearsal_v1.py`; strengthened
  `native_t102_handoff_journal_v1.py`; closed rehearsal-authority and receipt
  schemas; public exports; exact-binding, fault, expiry, concurrency, schema,
  and type-confinement tests; portable CI selection.
- Artifact identity: executor implementation SHA-256
  `804fd68dc4f484a24126296591f0768bf33a6ab0ab5b9f116198bd75a503aba1`;
  strengthened handoff implementation SHA-256
  `e1f744fa6f1678c227b1d8b330ce7d11cadbf940a6a04897f294e0a6f99ed298`;
  authority and receipt schema SHA-256 values
  `bbc97d0ac02715f4643042bd13f2b8a9a447574ebef6f4e27aca209b8546de9d`
  and `b4d5151a48209921e27b60f90cae3c9fa343169d072098fb10cdcd52c8f68d08`.
- Results: focused claim/executor suite PASS, 23 tests; expanded
  runtime/permit/writer/T=102 suite PASS, 72 tests; portable shared AI/arm
  selection PASS, 256 tests in 36.92 seconds; compile and diff checks PASS.
- Evidence status: deterministic filesystem plus in-memory evidence only. The
  exact accepted transport class has no serial factory, port, socket, callback,
  device handle, controller process, firmware operation, or external I/O.
- Hardware writes: 0
- Physical movements: 0
- Limitations: the approval-record digest is a rehearsal binding, not a physical
  authorization issuer. The endpoint digest is pinned but no endpoint is
  opened. Confirmed bytes mean only that the incapable recorder accepted the
  full payload. There is no authentic T=1021 acknowledgement, T=1051 feedback,
  physical arrival, task outcome, or durable terminal execution receipt yet.
- Supersedes: ARM-050's lack of a qualified executor lifecycle and byte-accounted
  rehearsal. It does not supersede the durable pre-open ambiguity boundary,
  native-adapter review, authentic receipt acquisition, physical qualification,
  or independent task observation.
- Next dependency: independently implement and review a production transport
  adapter outside this incapable boundary, plus a durable terminal receipt
  journal. The adapter must accept only the exact claimed handoff and an
  externally issued single-use physical authority, open one pinned controller
  endpoint, account for one write, collect authentic acknowledgement/feedback,
  and never resend any ambiguous claim. Physical use remains a separate,
  explicitly authorized test.

### E-20260926-ARM-052 — durable T=102 terminal receipt journal

- Stage: S4
- Lane: ARM
- Change: added a filesystem-backed journal around ARM-051's claimed executor
  rehearsal. Before the incapable transport may open, an immutable
  `started.json` binds the prepared handoff, exclusive claim, single-use
  authority, approval record, exact T=102 frame and payload, pinned endpoint,
  correlation, writer, controller session, and monotonic start. After the one
  executor attempt, `terminal.json` seals the exact byte-accounted receipt.
- Recovery behavior: an execution-started journal without a terminal record is
  always `RETRY_FORBIDDEN_EXECUTION_UNCERTAIN`; a complete journal is
  `TERMINAL_NO_REPLAY`. Both records are canonical JSON, content-hashed,
  exclusive, flushed, and revalidated after restart. Truncated, malformed,
  tampered, crossed, duplicated, symlinked, or unexpectedly extended journals
  fail closed.
- Receipt validation: terminal admission independently checks the exact receipt
  fields and hash plus mutual consistency among status, error code, requested
  and confirmed bytes, and open/write/close attempt counts. A rehashed but
  internally inconsistent receipt cannot be sealed. All incapable executor
  outcomes—including open, zero-write, partial-write, invalid-count,
  write-exception, close, and full-recording paths—can be terminally retained
  without claiming controller receipt or movement.
- Artifacts: `native_t102_terminal_receipt_journal_v1.py`; closed execution-
  started, terminal, and recovery-snapshot schemas; public exports; durable
  wrapper; restart, concurrency, fault, schema, crossing, consistency,
  truncation, unexpected-entry, and symlink tests; portable CI selection.
- Artifact identity: implementation SHA-256
  `b2c04ae8651dd7b65f1edbdccb5280c44aa325c7cbf0e1bfe041757a2bace55a`;
  execution-started, terminal, and snapshot schema SHA-256 values
  `57245097a4c2b51b10dfe7b4cb1276052456c97ffd0a4be7557b441906d00dfd`,
  `3e6fc91c9589e92460c6bdb710ac4d3e7789d6e58a5cc157b84757956a11abd0`,
  and `ec5a3fe76a1df211d7bcaf2b2a1667e0a1d4e2e73766201552253ce1e0174f88`.
- Results: focused claimed-executor/terminal-journal suite PASS, 39 tests;
  expanded runtime/permit/writer/T=102 suite PASS, 88 tests; portable shared
  AI/arm selection PASS, 272 tests in 37.51 seconds; compile and diff checks
  PASS.
- Evidence status: deterministic local-filesystem and in-memory evidence only.
  The accepted transport remains ARM-051's exact incapable class and this
  journal owns no serial factory, port, socket, callback, device handle,
  controller process, firmware operation, or external I/O.
- Hardware writes: 0
- Physical movements: 0
- Limitations: the execution authority remains rehearsal-only, the pinned
  endpoint is a digest rather than an opened device, and recorded bytes remain
  in memory. The terminal record is durable evidence of the rehearsal lifecycle,
  not an authentic controller acknowledgement, joint-feedback stream, physical
  arrival, task outcome, or production transport qualification.
- Supersedes: ARM-051's volatile terminal receipt and unresolved crash window
  after execution-started publication. It preserves ARM-050's pre-open claim
  boundary and does not supersede native-adapter review, authentic receipt
  acquisition, physical qualification, or independent task observation.
- Next dependency: independently implement and review a production transport
  adapter outside the incapable executor type. It must consume an externally
  issued single-use physical authority, bind one resolved endpoint to the
  pinned identity, reuse this pre-open/terminal journal discipline, account for
  exactly one write, acquire authentic T=1021/T=1051 evidence, and never resend
  an ambiguous execution. Physical use remains separately authorized.

### E-20260926-ARM-053 — abstract production T=102 transport boundary

- Stage: S4
- Lane: ARM
- Change: defined the production-shaped seam outside ARM-051's exact incapable
  executor. The candidate binds ARM-050's claimed handoff to one exact COM/USB
  identity, one detached externally issued authority record, and one positive
  decision from an externally supplied verifier. The authority is atomic and
  single-use; this repository contains no issuer, verifier keyring, discovery,
  fallback endpoint, or concrete serial implementation.
- Lifecycle: a durable `started.json` is exclusively written and flushed before
  the abstract transport may open. The contract allows one open, verifies the
  observed endpoint before write, allows one exact T=102 write, captures once,
  validates a sequence-correlated T=1021 response and two settled monotonic
  T=1051 samples, closes once, and seals `terminal.json`. Every ambiguous state
  is no-retry and no-follow-on; a pre-terminal restart is retry-forbidden.
- Artifacts: `native_t102_production_transport_v1.py`, seven closed schemas,
  public application exports, bounded offline CI selection, contract/fault/
  identity/authority/concurrency/restart tests, and
  `NATIVE_T102_PRODUCTION_TRANSPORT_BOUNDARY.md`.
- Results: focused ARM-053 suite PASS, 17 tests; expanded native T=102/runtime
  suite PASS, 91 tests; portable shared AI/arm selection PASS, 289 tests in
  68.80 seconds; documentation checks PASS, 43 self-tests plus maintained-link,
  evidence-scope, and release-integrity validation.
- Evidence status: deterministic filesystem plus scripted in-memory evidence.
  The test transport exists only inside the test module and owns no port,
  serial factory, socket, callback, device handle, controller process, firmware
  operation, or external I/O.
- Hardware writes: 0
- Physical movements: 0
- Limitations: `CONTROLLER_EVIDENCE_CAPTURED_SETTLED_UNQUALIFIED` proves only
  contract composition and parsing. The receipt deliberately keeps concrete
  transport qualification, authentic controller receipt, physical movement,
  and follow-on authorization false. An external verifier interface is not a
  shipped approval verifier.
- Supersedes: ARM-052's missing production-shaped adapter seam. It does not
  supersede ARM-052's incapable rehearsal, independently reviewed native
  implementation, physical qualification, or task-outcome verification.
- Next dependency: implement and independently review one concrete Windows
  adapter that satisfies this abstract boundary, then qualify endpoint identity,
  bounded waits/cleanup, and authentic T=1021/T=1051 provenance under a
  separately explicit physical test authorization.

### E-20260926-ARM-054 — isolated Windows serial adapter candidate

- Stage: S4
- Lane: ARM
- Change: implemented a concrete pyserial-shaped Windows adapter behind the
  ARM-053 abstract boundary. It resolves only the pinned COM name, requires the
  exact USB VID/PID/serial identity before open, re-reads the same identity
  after exclusive open, enforces 115200 8N1 no flow, rejects stale buffered
  input without purging, writes one canonical T=102 frame once, captures one
  bounded T=1021 line, performs exactly two bounded T=105/T=1051 feedback
  exchanges, timestamps them monotonically, and closes once.
- Failure behavior: no discovery fallback, reopen, resend, recapture, purge,
  reset, startup motion, torque command, or automatic retry path exists.
  Identity drift, stale bytes, partial/invalid writes, timeout, malformed or
  wrong-type lines, reset banners, and overlong/truncated framing fail closed.
- Artifacts: `providers/windows/native_t102_serial_transport_v1.py`, focused
  offline adapter tests, portable CI selection, adapter boundary documentation,
  and updated ARM-053/shared workplan references.
- Results: focused adapter plus ARM-053 suite PASS, 33 tests; portable shared
  AI/arm selection PASS, 305 tests in 39.12 seconds; documentation checks PASS,
  43 self-tests plus maintained-link, evidence-scope, and release-integrity
  validation; compile and diff checks PASS.
- Evidence status: deterministic memory-only serial and inventory fixtures.
  pyserial is lazy-loaded only at explicit open; no automated test opens a real
  endpoint or composes the adapter with an authority issuer.
- Hardware writes: 0
- Physical movements: 0
- Limitations: this is an implementation candidate, not an independently
  reviewed or physically qualified transport. It does not authenticate the
  installed controller, prove real T=1021/T=1051 provenance, verify movement or
  task outcome, or authorize follow-on action.
- Supersedes: ARM-053's missing concrete Windows adapter source. It does not
  supersede the external-authority boundary, durable no-replay journal,
  independent source review, physical qualification, or task verification.
- Next dependency: independent review of the adapter and its composition,
  followed by a separately authorized read-only endpoint qualification before
  any proposal for one bounded physical movement.

### E-20260927-ARM-055 — deterministic adapter review and composition handoff

- Stage: S4
- Lane: ARM
- Change: froze the exact merged ARM-054 candidate into a deterministic,
  content-addressed ZIP with strict membership, canonical manifest, retained
  offline verification, and explicit external-review instructions. Added an
  offline integration test that composes the actual adapter class through
  ARM-053 rather than qualifying it only in isolation.
- Composition behavior: the successful memory-fixture path retains ARM-053's
  durable start and terminal records, one T=102 write, two T=105 evidence
  requests, settled scripted readback, and terminal no-replay status. Crossed
  external authority produces a durable start record and rejects before the
  adapter opens. No composition path promotes scripted evidence to authentic
  controller provenance or movement qualification.
- Artifacts: `native_t102_adapter_review_packet_v1.py`,
  `build_arm054_adapter_review_packet.py`, retained ARM-054 offline-verification
  JSON, packet and integration tests, this ledger entry, and
  `NATIVE_T102_ADAPTER_REVIEW_HANDOFF.md`.
- Artifact identity: packet SHA-256
  `65749a9f122fd4f685375652b6e52a101038a88b0fed1c1b921aea6c4b059f0d`;
  manifest SHA-256
  `0aff3af9a167e82b792fd55ff6bdd544c6ee2b961109c1dac6d7cb34c17bba4b`;
  bound ARM-054 commit `9bd17ac21d7fd00d18f3dd4378b9bea529b5b681`.
- Results: focused adapter/review/composition/ARM-053 suite PASS, 43 tests;
  portable shared AI/arm selection PASS, 315 tests in 38.23 seconds;
  documentation checks PASS, 43 self-tests plus maintained-link,
  evidence-scope, and release-integrity validation; compile and diff checks
  PASS.
- Evidence status: deterministic repository, filesystem, and memory-only serial
  evidence. Packet status is `AWAITING_EXTERNAL_INDEPENDENT_REVIEW`; no external
  decision is claimed or generated by this repository.
- Hardware writes: 0
- Physical movements: 0
- Limitations: packet integrity cannot authenticate reviewer identity or
  independence. The serial and controller responses remain scripted fixtures;
  no real endpoint was opened, no controller was started, and no physical
  authorization was issued.
- Supersedes: ARM-054 only for reproducible external-review handoff and offline
  ARM-053 composition coverage. It does not supersede independent review,
  endpoint qualification, controller provenance, calibration/collision
  qualification, physical movement authority, or task-outcome verification.
- Next dependency: transfer the immutable packet to a genuinely independent
  reviewer and retain a separately authenticated decision bound to its SHA-256.
  Only a separate authorization may begin read-only endpoint qualification.

### E-20260927-ARM-056 — external adapter-review decision intake boundary

- Stage: S4
- Lane: ARM
- Change: added a closed, content-addressed decision and assessment report for
  a genuinely external review of the exact ARM-055 packet. The decision binds
  packet, manifest, ARM-054 candidate commit, adapter source, reviewer
  attestation digest, ordered checklist, findings, disposition, and a bounded
  UTC validity window.
- Fail-closed behavior: synthetic origin, rejection, crossed identities,
  unasserted independence, implementation-author conflict, incomplete checks,
  open findings, assessment before completion, and expiration all block
  read-only endpoint-qualification intake. Strict parsing rejects added fields,
  authority promotion, malformed types, and content-hash mismatch.
- Artifacts: `native_t102_adapter_review_decision_v1.py`, two closed JSON
  schemas, focused tests, public exports, portable CI selection, and
  `NATIVE_T102_ADAPTER_REVIEW_DECISION.md`.
- Results: focused adapter packet/decision/r97 decision suite PASS, 51 tests;
  portable shared AI/arm selection PASS, 338 tests in 39.40 seconds;
  documentation checks PASS, 43 self-tests plus maintained-link,
  evidence-scope, and release-integrity validation; compile and diff checks
  PASS.
- Evidence status: synthetic in-process fixtures only. No real reviewer
  decision, reviewer authentication, custody proof, or independent assessment
  is claimed. A dedicated synthetic origin is quarantined from endpoint intake.
- Hardware writes: 0
- Physical movements: 0
- Limitations: a structurally accepted external-origin document cannot by
  itself prove who controlled the reviewer identity. Acceptance means only
  eligibility for a future read-only qualification intake and keeps endpoint
  open, controller start, execution, hardware, and physical authority false.
- Supersedes: ARM-055 only for the typed decision-return boundary. It does not
  supersede actual independent review, reviewer authentication, endpoint
  qualification, controller provenance, physical authority, or outcome
  verification.
- Next dependency: obtain and authenticate a genuinely independent decision
  bound to the exact ARM-055 packet, then separately design and authorize a
  read-only endpoint qualification. Movement remains out of scope.

### E-20260927-ARM-057 — operational external-review exchange and intake

- Stage: S4
- Lane: ARM
- Change: added a deterministic offline exchange builder that emits the exact
  ARM-055 packet, decision and report schemas, reviewer procedure, and a
  content-addressed manifest without fabricating a decision. Added a separate
  strict return-intake CLI that normalizes and assesses one supplied decision
  into an exclusive evidence directory.
- Intake behavior: duplicate fields, non-UTF-8/malformed JSON, oversize input,
  symlinked evidence, unknown fields, content-hash mismatch, and existing
  output directories fail closed. Accepted and blocked decisions both retain
  the raw input-document hash, normalized document, assessment report, and
  summary; blocked decisions remain endpoint-intake ineligible.
- Artifacts: `build_arm054_adapter_review_exchange.py`,
  `assess_arm054_adapter_review_decision.py`, focused CLI tests, portable CI
  selection, and updated external-review procedure/workplan.
- Results: focused packet/decision/exchange suite PASS, 35 tests; portable
  shared AI/arm selection PASS, 342 tests in 42.38 seconds; documentation
  checks PASS, 43 self-tests plus maintained-link, evidence-scope, and
  release-integrity validation; compile and diff checks PASS.
- Evidence status: deterministic filesystem fixtures only. The exchange
  contains no decision, and tests use explicitly non-proven review fixtures.
  No reviewer authentication, external custody, or real decision is claimed.
- Hardware writes: 0
- Physical movements: 0
- Limitations: the intake verifies document structure and bindings, not who
  controlled the reviewer identity or evidence channel. It grants no endpoint
  open, controller start, execution, hardware, or physical authority.
- Supersedes: ARM-056 only for operational packaging and return intake. It does
  not supersede genuine independent review, authenticated custody, endpoint
  qualification, controller provenance, or physical authorization.
- Next dependency: transfer the exchange to a genuinely independent reviewer
  through an externally controlled channel and intake their authenticated
  decision. Only a later, separate authorization may permit read-only endpoint
  qualification.

### E-20260927-ARM-058 — zero-write shadow telemetry replay

- Stage: S4/S7
- Lane: ARM
- Change: added a deterministic assessor that binds the exact zero-write
  Waveshare T=102 preview receipt to ordered synthetic or retained-export
  T=1051 samples. It compares all six commanded and reported joints, requires
  consecutive in-tolerance and mutually stable samples for every previewed
  waypoint, and retains signed residuals, maximum residual, command and sample
  hashes, timing, session, correlation, and origin.
- Fail-closed behavior: crossed correlation or controller session, unknown
  waypoint, pre-dispatch/stale/non-monotonic timing, malformed T=1051,
  incomplete joints, unsupported origin, and unbound retained exports are
  rejected. Out-of-tolerance or unstable complete data remains
  `SIMULATION_REPLAY_UNVERIFIED` rather than becoming a false PASS.
- Artifacts: `shadow_telemetry_replay_v1.py`, closed JSON result schema,
  focused tests, portable CI selection,
  `SHADOW_TELEMETRY_REPLAY.md`, and shared plan/checklist updates.
- Results: focused zero-write/telemetry/sole-writer/integration suite PASS, 50
  tests in 11.43 seconds; portable shared AI/arm selection PASS, 354 tests in
  41.45 seconds; documentation checks PASS, 43 self-tests plus maintained-link,
  evidence-scope, and release-integrity validation; compile and diff checks
  PASS.
- Evidence status: deterministic synthetic fixtures only in the committed test
  run. The retained-export path requires a source hash but does not authenticate
  that export as a live controller transaction.
- Hardware writes: 0
- Physical movements: 0
- Limitations: replay PASS proves only that the previewed command targets and
  supplied telemetry agree under the declared policy. Physical arrival,
  authentic controller provenance, collision safety, visual outcome, task
  success, and repeatability remain unproven. Every report fixes transport,
  execution, hardware, and physical authority false.
- Supersedes: no prior physical evidence. It closes the missing automated
  command-versus-telemetry simulation seam without changing the ARM-057
  independent-review dependency.
- Next dependency: obtain the genuine ARM-054 external review and separately
  authorize read-only endpoint qualification. Authenticated retained telemetry
  can then be replayed through this boundary and compared with an independent
  visual observation; movement remains separately gated.

### E-20260927-ARM-059 — owner-accepted AI adapter review with caveat

- Stage: S4
- Lane: ARM
- Change: added a separate owner-governance acceptance record for the exact
  internal AI technical review of ARM-054. The record consumes bounded strict
  JSON, binds the file and canonical-content hashes, and requires the exact
  packet, manifest, candidate commit, adapter source, ordered 11-check pass,
  passing technical disposition, retained non-independence provenance, and no
  open technical findings.
- Governance behavior: the project owner elects to treat that review as the
  source-review prerequisite. The record explicitly keeps
  `human_review_claimed=false` and `external_independence_claimed=false`; it
  does not alter or impersonate the external-review decision schema.
- Artifacts: `native_t102_owner_ai_review_acceptance_v1.py`, its closed JSON
  schema, focused tests, public exports,
  `NATIVE_T102_OWNER_AI_REVIEW_ACCEPTANCE.md`, and shared-plan updates.
- Evidence status: deterministic parsing and synthetic fixtures. The accepted
  source review is the exact owner-designated AI report; no live endpoint or
  controller evidence is added.
- Hardware writes: 0
- Physical movements: 0
- Limitations: read-only endpoint-qualification intake eligibility is not
  permission to open an endpoint. Controller startup, transport writes,
  execution, hardware access, and physical authority all remain false.
- Supersedes: the external-human-review dependency only under the owner's
  explicitly stated project policy. It does not supersede the provenance
  caveat, endpoint qualification, controller provenance, calibration/collision
  qualification, movement authority, or task verification.
- Next dependency: implement the closed read-only endpoint-qualification intake
  and obtain separate authorization before any real endpoint is opened.

### E-20260927-ARM-060 — closed read-only endpoint intake contract

- Stage: S4
- Lane: ARM
- Change: added a strict, hardware-incapable intake that binds the exact
  ARM-059 owner acceptance to one declared host, one pinned COM/USB serial
  identity, and one finite passive observation plan. Closed parsing
  reconstructs and rehashes both endpoint and intake and rejects crossed
  identity, policy promotion, authority promotion, extra fields, and unbounded
  capture values.
- Observation policy: verify pinned identity before and after one open, capture
  only bounded passive lines, then close once. Transport writes, active
  requests, movement, torque commands, purge, fallback, retry, and DTR/RTS
  assertion are all forbidden.
- Artifacts: `native_t102_read_only_endpoint_intake_v1.py`, its closed JSON
  schema, focused tests, public exports,
  `NATIVE_T102_READ_ONLY_ENDPOINT_INTAKE.md`, and shared-plan updates.
- Evidence status: deterministic offline and synthetic endpoint fixtures only.
  No real COM name, USB identity, or host identity is claimed or retained.
- Hardware writes: 0
- Physical movements: 0
- Limitations: `READY_FOR_SEPARATE_READ_ONLY_AUTHORIZATION` is a proposal
  readiness state, not permission to enumerate or open a port. Read-only
  endpoint, controller-start, transport-write, execution, hardware, and
  physical authority all remain false.
- Supersedes: the missing intake-format implementation dependency after
  ARM-059. It does not supersede actual endpoint identification, separate
  operator authorization, passive qualification, controller provenance,
  calibration/collision qualification, movement authority, or task
  verification.
- Next dependency: establish the exact physical host and endpoint identity,
  retain a matching intake under separate authorization, and obtain a new
  bounded authorization before the passive zero-write run.

### E-20260927-ARM-061 — retained exact read-only endpoint intake

- Stage: S4
- Lane: ARM
- Change: performed Windows PnP-only identity discovery and retained the first
  real ARM-060 intake. The present CP210x controller matched the historically
  documented COM7, VID `10C4`, PID `EA60`, and USB serial identity; separate
  Bluetooth COM endpoints were excluded. The host is bound through a
  pseudonymous SHA-256-derived identifier.
- Artifact: `software/ai/eval/arm061_read_only_endpoint_intake.json`, intake
  SHA-256
  `2d88fa8874088ce47b778343ea0ed07994bafb64267b8cd121765c52536ce1d9`.
  Schema validation and strict parsing recompute both endpoint and intake
  hashes.
- Evidence status: fresh Windows Plug-and-Play metadata plus the previously
  documented physical endpoint identity. This is endpoint identity evidence,
  not controller-protocol, firmware, telemetry, or pose evidence.
- Endpoint opens: 0
- Hardware writes: 0
- Physical movements: 0
- Limitations: inventory presence does not prove controller protocol identity,
  firmware provenance, telemetry validity, or mechanical readiness. The intake
  remains `READY_FOR_SEPARATE_READ_ONLY_AUTHORIZATION`; read-only endpoint,
  startup, write, execution, hardware, and physical authority are false.
- Supersedes: the missing exact host/endpoint intake artifact after ARM-060. It
  does not supersede separate authorization or the passive qualification run.
- Next dependency: obtain an explicit authorization naming the retained intake
  hash before opening COM7 once for the bounded zero-write passive capture.

### E-20260927-ARM-062 — bounded passive endpoint qualification

- Stage: S4
- Lane: ARM
- Authorization: one open and one close against intake
  `2d88fa8874088ce47b778343ea0ed07994bafb64267b8cd121765c52536ce1d9`,
  maximum four passive lines, one-second read window, and zero writes, active
  requests, startup, movement, torque changes, retry, fallback, purge, or
  DTR/RTS assertion.
- Result: `PASSIVE_CAPTURE_COMPLETED`. Exact PnP identity matched before and
  after open; open succeeded once; close was attempted once and confirmed.
  The passive window contained zero unsolicited complete or partial lines.
- Artifact:
  `software/ai/eval/arm062_passive_read_only_qualification_20260927.json`,
  normalized retained-file SHA-256
  `ac84722855d43e66e07d512bd60c3d19b2c468c0defe1505303f233bc4148aea`.
  The direct PowerShell receipt had raw SHA-256
  `5e3beac11908bef4c310ff599e86d44dc6dae407c2cd57e0f3bdc4dca6886ed9`;
  repository retention changed only JSON whitespace from CRLF to LF.
  The runner source and a closed receipt schema are retained with static and
  semantic tests.
- Endpoint opens: 1
- Endpoint closes: 1 confirmed
- Hardware writes: 0
- Active requests: 0
- Physical movements: 0
- Limitations: an empty passive window proves no controller protocol, firmware,
  telemetry, pose, or actuation property. Elapsed lifecycle time includes open,
  post-open identity verification, read, and close overhead; the read loop was
  bounded by the authorized monotonic one-second deadline.
- Supersedes: the pending passive endpoint lifecycle qualification after
  ARM-061. It does not supersede active controller identity/feedback
  qualification, calibration/collision checks, movement authority, or outcome
  verification.
- Next dependency: design an active but still non-moving identity or feedback
  qualification with its own exact write/request budget and separate owner
  authorization. No passive retry is warranted.

### E-20260927-ARM-063 — frozen active-feedback intake and fake rehearsal

- Stage: S4
- Lane: ARM
- Change: bound the exact ARM-061 endpoint intake and ARM-062 passive receipt
  to canonical request bytes `{"T":105}\n`, one bounded T=1051 response, and
  one terminal open/write/read/close lifecycle. Added closed parsing, schema,
  public exports, and a fake-only exchange runner that rejects arbitrary
  transports.
- Artifact: `software/ai/eval/arm063_active_feedback_intake.json`, intake
  SHA-256
  `3b44d5e011d8c44afda1bb6deb1cc479b1fc0c45e59e39308d285cde416b8fcc`;
  request SHA-256
  `2cace64403a9db92d57acd8814d55c833529c0341468529900bd89f089e1fa3c`.
- Result: PASS in focused offline tests. The fake exchange proves exact request
  bytes, stale-buffer rejection, single response parsing, six numeric joint
  fields, unconditional close, and zero retry/T=102/movement/torque commands.
- Endpoint opens: 0 physical; 1 fake per successful rehearsal
- Hardware writes: 0
- Physical movements: 0
- Limitations: fake behavior does not prove that COM7 speaks the expected
  protocol, that installed firmware emits valid T=1051, or that reported joint
  values match physical pose. The intake explicitly leaves open, write,
  execution, hardware, and physical authority false.
- Supersedes: the missing design requested by ARM-062. It does not supersede
  separate active-feedback authorization or live qualification.
- Next dependency: obtain explicit authorization naming intake
  `3b44d5e011d8c44afda1bb6deb1cc479b1fc0c45e59e39308d285cde416b8fcc`
  before exactly one active non-moving COM7 feedback exchange.

### E-20260927-ARM-064 — one-shot active feedback rejected by installed surface

- Stage: S4
- Lane: ARM
- Authorization: exact ARM-063 intake
  `3b44d5e011d8c44afda1bb6deb1cc479b1fc0c45e59e39308d285cde416b8fcc`;
  one pinned COM7 open, one canonical T=105 write, one bounded T=1051 read,
  and one close; no startup, T=102, movement, torque, retry, fallback, purge,
  or DTR/RTS assertion.
- Result: `ACTIVE_FEEDBACK_FAILED_TERMINAL`. Identity matched before and after;
  open succeeded once; the receive buffer was empty; all ten authorized bytes
  were written once; one 17-byte line was read; close was confirmed once.
  The response was exactly `FAULT:NOT_READY\r\n`, not T=1051. No retry ran.
- Artifact:
  `software/ai/eval/arm064_active_feedback_qualification_20260927.json`, file
  SHA-256
  `8bf9d1d5fc3f523918953633ef24b51bcf59c44b8d6df8e7fc7fbd8426c3c1d1`;
  response SHA-256
  `148028ad79af17d51f9c75cdd7f49e04bc274fa5830e58aae4568006921c4a53`.
- Source analysis: `ghost_typing_b_board.h` contains the exact fault before its
  finite leg-command comparison when its one-use state is not ready. This is
  consistency evidence only, not cryptographic installed-firmware identity.
- Endpoint opens: 1
- Hardware writes: 1 request / 10 bytes
- Active requests: 1
- Physical movements: 0
- Limitations: no T=1051 telemetry or pose was obtained; controller firmware
  identity, joint accuracy, and the generic production protocol remain
  unqualified. The original receipt's generic parse-failure text is retained
  unchanged; its base64 raw line supplies the authoritative response.
- Supersedes: the pending active-feedback attempt after ARM-063. It does not
  qualify the generic feedback protocol or observed planner start state.
- Next dependency: resolve the installed diagnostic-versus-production runtime
  mismatch through the existing reviewed installation/configuration-epoch
  gates. Do not retry T=105 against the current surface.

### E-20260927-ARM-065 — r97 runtime-transition assessment remains blocked

- Stage: S4
- Lane: ARM
- Change: reconciled the exact ARM-064 terminal receipt with the sealed r97
  review packet, manifest, and application identities using a deterministic
  zero-I/O assessment and closed schema.
- Artifact:
  `software/ai/eval/arm065_r97_runtime_transition_assessment.json`; assessment
  SHA-256 `591df4379a55410a59d1a74e182d07ca1ac95c607950084890b214b6d5875f3f`.
- Result: `BLOCKED`. The installed surface is consistent with the finite
  diagnostic application but is not attested as r97; active feedback was
  rejected; external r97 review is missing; the eight-component measured
  configuration epoch is missing; and r97 embeds a null epoch.
- Endpoint opens: 0
- Hardware writes: 0
- Physical movements: 0
- Authority: installation, startup, transport, execution, hardware, and
  physical authority all remain false.
- Limitations: source-string consistency is not installed-image identity. The
  assessment does not replace an external reviewer, physical measurements, or
  a later installation/startup authorization.
- Next dependency: external independent review of packet
  `987cbe86d98440734d8336c704f1ecd89692675a9cb1620cb674e4132957b416`
  and independently reviewed measurements for all eight configuration-epoch
  components. Only then may an epoch-bound build and separate installation
  intake be proposed.

### E-20260927-ARM-066 — external r97 decision intake is operational

- Stage: S4
- Lane: ARM
- Change: reproduced and reinspected the existing seven-member r97 review
  packet from retained compiled inputs, added a reviewer handoff guide, and
  implemented a strict owner-side CLI for one returned external decision.
- Packet verification: SHA-256
  `987cbe86d98440734d8336c704f1ecd89692675a9cb1620cb674e4132957b416`,
  exactly matching the frozen ARM-033 identity.
- Intake behavior: one regular non-symlink JSON file, 128-KiB maximum, strict
  UTF-8 JSON with duplicate-field rejection, full closed decision parsing,
  exact packet/manifest/app assessment, normalized immutable output, and
  overwrite refusal.
- Results: focused external-decision, r97-decision, and ARM-065 tests PASS.
- Endpoint opens: 0
- Hardware writes: 0
- Physical movements: 0
- Authority: installation, startup, transport, execution, hardware, and
  physical authority remain false even when a decision passes.
- Limitations: no external decision was created or received. Reproducing and
  validating the packet does not authenticate reviewer independence or evidence
  custody.
- Next dependency: transfer the unchanged packet to a genuinely independent
  reviewer and ingest their returned decision with
  `software/scripts/assess_r97_external_review_decision.py`; afterward collect
  and independently review all eight measured configuration-epoch components.

### E-20260927-ARM-067 — owner accepts non-independent r97 AI review

- Stage: S4
- Lane: ARM
- Owner decision: no human reviewer will be used; remove that dependency and
  continue.
- Change: bound the exact passing r97 synthetic AI technical decision to an
  explicit owner governance override. The record does not relabel AI evidence
  as human or externally independent.
- Artifact: `software/ai/eval/arm067_r97_owner_ai_review_acceptance.json`;
  acceptance SHA-256
  `76bac6177af918fcee476f7645df6559a960ad52e68c68875db52cdf6a091698`.
- Bound identities: packet `987cbe86...b416`, manifest `e7c67071...117e`, app
  `7d2e47d4...d1d`, AI decision `f84c9568...dc6b`.
- Result: `OWNER_ACCEPTED_AI_REVIEW_GOVERNANCE_OVERRIDE`; ready for an
  owner-governed configuration-epoch intake.
- Endpoint opens: 0
- Hardware writes: 0
- Physical movements: 0
- Authority: installation, startup, transport, execution, hardware, and
  physical authority remain false.
- Limitations: owner acceptance removes a governance dependency; it does not
  improve evidence independence or prove installed firmware, calibration,
  geometry, or motion behavior.
- Supersedes: ARM-066 only as the mandatory external-review dependency. The
  external workflow remains an optional future path.
- Next dependency: collect and AI-review retained physical evidence for the
  eight configuration components, then construct the owner-governed epoch.

### E-20260927-ARM-068 — owner-governed epoch contract and missing-evidence baseline

- Stage: S4
- Lane: ARM
- Change: added a parallel owner-governed configuration-epoch draft and
  assessment rather than mutating the historical independent-review contract.
  The draft is bound to ARM-067 acceptance and the exact r97 packet, app,
  protocol-source, and joint-mapping identities.
- Component policy: all eight controlled components remain ordered; each has
  the exact required binding roster from `configuration_epochs.json`. Partial
  drafts are accepted for assessment, while missing bindings, stale evidence,
  synthetic evidence, and incomplete owner-AI review remain distinct blockers.
- Artifacts: `software/ai/eval/arm068_owner_epoch_draft.json`, draft SHA-256
  `72e00112d41fc5849dd58d1c0abd858980ce9849817d6e2a6a82bcb78c842dc6`;
  `software/ai/eval/arm068_owner_epoch_missing_evidence_report.json`, assessment
  SHA-256
  `6931ed878e12d8daebf0a92597e687904bb85dc5979c302c5d42cee83b34fe70`.
- Result: `BLOCKED` by `COMPONENT_MISSING`. All eight component IDs and all 32
  required binding IDs are enumerated. The configuration-epoch SHA remains
  null, as required for an incomplete draft.
- Verification: 447 tests in the bounded offline CI selection passed; schema,
  strict parsing, tamper rejection, acceptance/release mismatch, component
  blocker separation, retained-artifact equality, and a complete non-authority
  fixture are covered.
- Endpoint opens: 0
- Hardware writes: 0
- Physical movements: 0
- Authority: installation, startup, transport, execution, hardware, and
  physical authority remain false. A future complete pass permits only an
  epoch-bound build proposal.
- Limitations: the contract and passing all-physical test fixture do not create
  physical evidence. The retained artifact intentionally contains no component
  records.
- Supersedes: ARM-067's missing owner-governed epoch software boundary. It does
  not supersede the need for measured retained evidence.
- Next dependency: populate and owner-AI review each physical-original
  component, starting with the reproducible `software_build` evidence bundle.

### E-20260927-ARM-069 — reproducible software-build epoch evidence

- Stage: S4
- Lane: ARM
- Source baseline: commit
  `1d7671a3eacb205788972f47ef36d36a09b63994`, tree
  `189016aab61678b5d2cd508cfe4b752dbb4ac749`.
- Change: generated a deterministic retained-original software bundle for the
  exact r97 release and closed the four `software_build` bindings:
  `build_snapshot`, `source_binding`, `dependency_receipt`, and
  `provider_hashes`. A separate closed owner-AI review binds that bundle while
  explicitly claiming no human review, external independence, or physical
  measurement.
- Artifacts: `software/ai/eval/arm069_software_build_evidence.json`, bundle
  SHA-256 `3b482186b5e62d7fadc8b1241d6a5cd7365f328c19661d5421b553fc8b902610`;
  `software/ai/eval/arm069_software_build_owner_ai_review.json`, review SHA-256
  `ac20a7122e365b7a688c2bde67358ddf214da3a049a211c1b9bc7e66d2748fee`;
  `software/ai/eval/arm069_owner_epoch_draft.json`, draft SHA-256
  `6b43fedbcdf8f865be19056724d824a3e94232e96ac4559e7db092ff43c89a40`;
  `software/ai/eval/arm069_owner_epoch_partial_assessment.json`, assessment
  SHA-256 `a2e7b468a685813de164e2f81e9769fd10524ce76c665ce172110205385d8e97`.
- Result: `software_build` is `READY`; the other seven components remain
  `MISSING`. Global status is `BLOCKED`, configuration-epoch SHA is null, and
  no epoch-bound build proposal is ready.
- Verification: deterministic rebuild, JSON Schema validation, provider-tamper
  rejection, crossed-review rejection, retained-artifact equality, and partial
  epoch state are covered by the bounded offline suite.
- Endpoint opens: 0
- Hardware writes: 0
- Physical movements: 0
- Authority: installation, startup, transport, execution, hardware, and
  physical authority remain false.
- Limitations: this closes software provenance only. It does not attest the
  installed controller or measure camera, bench, tool, power, keyboard, phone,
  or empty-cell state.
- Supersedes: ARM-068 only for the missing `software_build` component.
- Next dependency: collect and owner-AI review retained
  `camera_support_optics` evidence while keeping the other six components
  visible as missing.

### E-20260927-ARM-070 — camera/support/optics intake and honest gap assessment

- Stage: S4
- Lane: ARM
- Source baseline: merge commit
  `c9f7ab03d7ee2fab477828f4f4ef5566ddd46052`, tree
  `608a18b3de2a04c347af6ce235aa900c3bf3ba39`.
- Change: added a deterministic four-binding camera/support/optics intake,
  readiness assessment, strict schemas, and an adapter that can create the
  shared epoch component only after all four physical-original bindings are
  current and owner-AI accepted.
- Baseline facts: camera profile state `PURCHASED_PENDING_RECEIPT`; received
  unit, persistent USB identity, commissioned mode, and controls snapshot are
  null; support state is
  `SCREENING_CANDIDATE_PHYSICAL_QUALIFICATION_OPEN`; all 55 hardware-intake rows
  remain unresolved.
- Artifacts: `software/ai/eval/arm070_camera_support_optics_intake.json`, intake
  SHA-256 `63757a5bdb2f835579d4b46f665ae86a889e226e64206e88c085696b7c6eac14`;
  `software/ai/eval/arm070_camera_support_optics_readiness.json`, assessment
  SHA-256 `093fb631ffdba64cf415ebb962c90876625f4bef8d83df0aee1b3f080fddf6ce`.
- Result: `BLOCKED`; `camera_receipt`, `camera_identity`,
  `camera_mode_controls`, and `support_witnesses` are all `MISSING`. Component
  admission is false and the ARM-069 epoch is unchanged.
- Verification: deterministic source binding, schema validation, distinct
  synthetic/stale/unreviewed/future-evidence blockers, cross-lineage rejection,
  complete non-authority fixture, and retained-artifact equality are covered.
- Endpoint opens: 0
- Hardware writes: 0
- Physical movements: 0
- Authority: camera open, installation, startup, transport, execution,
  hardware, and physical authority remain false.
- Limitations: this implements and evaluates the intake; it does not create the
  missing physical observations or qualify the purchased camera/support.
- Supersedes: none. ARM-069 remains the current partial epoch.
- Next dependency: use the existing physical onboarding workflow to retain and
  owner-AI review the four originals, then rerun this intake with their exact
  hashes and validity windows.

### E-20260927-INT-071 — model/arm v2 conformance baseline

- Stage: S1/S2 integration boundary.
- Lane: INTEGRATION.
- Reviewed sources: arm `main`
  `3e20e81c15591e8b5ef6dd2545dacbce458bae0d`; AI branch
  `feature/translation-pair-evidence`
  `caf1962389971de949a5aee40b3244bf48fcb607`.
- Change: froze a machine-readable division of model and arm responsibilities,
  corrected the v2 contract status to match implemented code, and added an
  executable conformance matrix around the actual AI batch assembler, strict
  v2 decoder, consumer-owned registry ingress, and freshness gate.
- Artifact: `software/config/model_arm_conformance_profile_v1.json`, SHA-256
  `2430ec5f8362aae76e8250d2d9da292f85375d93750addd944a969b1bc2e4dbd`.
- Result: `ALIGNED` for the zero-authority software boundary. Canonical producer
  bytes preserve `H,H,I` and reach fresh sequential planner admission. Missing
  qualified uncertainty abstains; phone plans, low confidence, safe-region
  crossings, model-owned motion policy, controller commands, and authority
  claims fail closed.
- AI review result: latest `inflated_risk_gate_v1` selection is false and no
  qualification is installed. Its synthetic research scale cannot populate the
  arm's trusted localization qualification.
- Planner result: `BLOCKED_CALIBRATION_MISSING_OR_STALE`; no synthetic promotion.
- Verification: 37 focused producer/consumer tests passed, including JSON Schema
  validation and all six shared conformance cases.
- Endpoint/camera opens: 0.
- Hardware writes: 0.
- Physical movements: 0.
- Authority: controller commands remain empty; hardware and physical authority
  remain false.
- Limitations: this proves structural compatibility and fail-closed behavior,
  not model accuracy, physical calibration, trajectory readiness, typing, or
  device-effect verification.
- Supersedes: the stale `PROPOSED` status text in the v2 design document; it does
  not supersede any blocked physical gate or AI failure evidence.
- Next dependency: AI produces separately confirmed qualified uncertainty and a
  precision adapter; arm supplies physical-original camera, placement, target
  region, surface, calibration, and capability records for a one-key integration.

### E-20260927-INT-072 — cross-lane operational-readiness gate

- Stage: S2/S4 integration boundary.
- Lane: INTEGRATION.
- Source baseline: GitHub `main`
  `c75811d419a999375ec0ba4e4da1a813e21e3480`.
- Change: added a deterministic, content-bound readiness report that composes
  the v2 conformance profile, ARM-067 owner-governance acceptance, ARM-069
  measured-epoch assessment, ARM-070 camera/support intake, measured planner
  status, and ARM-065 installed-runtime assessment.
- Artifact: `software/ai/eval/arm072_model_arm_operational_readiness.json`,
  readiness SHA-256
  `12ae1acfe097151fe647aa9fe60ef60c0c3db359e735782c2f2d2640ff8338b9`.
- Result: `wire_contract` is READY. `qualified_perception`,
  `camera_support_optics`, `measured_configuration_epoch`,
  `measured_planner_calibration`, and `installed_controller_runtime` remain
  BLOCKED with exact next dependencies.
- Governance correction: ARM-067 superseded the mandatory external-review
  dependency. The composite report removes only that stale blocker; it retains
  the unattested runtime, rejected active-feedback surface, missing measured
  epoch, missing calibration, and missing physical-original evidence.
- Verification: deterministic rebuild, strict JSON Schema validation, source
  hashing, retained-report hash validation, camera-binding lineage rejection,
  source substitution rejection, and zero-authority assertions are covered.
- Endpoint/camera opens: 0.
- Hardware writes: 0.
- Physical movements: 0.
- Authority: controller commands remain empty; camera open, controller startup,
  movement, dispatch, hardware, and physical authority remain false.
- Limitations: this makes the current gap machine-readable; it does not create
  physical originals, qualify perception, attest the runtime, commission
  calibration, or authorize a physical action.
- Supersedes: no evidence result. It supersedes only fragmented manual reading
  of the five readiness blockers.
- Next dependency: AI supplies qualified perception; arm collects the four
  camera/support originals and remaining measured epoch components, commissions
  planner calibration, and resolves installed-runtime feedback qualification.

### E-20260927-ARM-073 — retained camera/support binding adapter

- Stage: S4
- Lane: ARM
- Source baseline: GitHub `main`
  `36ebe29c68ec3339110597ae78093acdebb9d28b`.
- Change: added a strict file-backed bridge from four retained physical-original
  files and their owner-AI review records into the canonical ARM-070
  `CameraSupportBindingV1` sequence.
- Contract: review and receipt JSON Schemas are closed; evidence reads are
  bounded to 16 MiB, review reads to 128 KiB, paths remain beneath one canonical
  root, regular-file substitution checks are reused from onboarding durability,
  and duplicate fields, hash drift, traversal, partial sets, and reordered sets
  fail closed.
- Integration result: a complete current fixture produces all four typed
  bindings, passes fresh ARM-070 assessment, and can construct the
  `camera_support_optics` epoch component. A stale fixture still loads as an
  authenticated record but is rejected by ARM-070 with `EVIDENCE_STALE`, keeping
  authentication separate from admission policy.
- Endpoint/camera opens: 0.
- Hardware writes: 0.
- Physical movements: 0.
- Authority: epoch advancement, camera open, controller startup, transport,
  execution, hardware, and physical authority remain false.
- Limitations: the adapter does not collect a physical original, manufacture an
  owner-AI decision, evaluate perception accuracy, or make the currently missing
  ARM-070 evidence exist. Its root digest is an audit binding to the selected
  canonical path; evidence and review identity remain content-hash based.
- Supersedes: no evidence result and no physical gate. It removes only the need
  to transcribe accepted retained originals manually into ARM-070 bindings.
- Next dependency: collect and owner-AI review the four physical originals in
  canonical order, then load them through this adapter and rerun ARM-070.

### E-20260927-AI-403 — precision adapter mainline integration review

- Stage: S2/S3.
- Lane: AI/INTEGRATION.
- Source: remote `codex/precision-adapter-v2` commits `ff950c8` and
  `dedd639`, rebased selectively onto GitHub `main` `26d12aa`; stale branch
  history and its superseded inline ledger were not imported.
- Change: integrated the pose-output-to-`rocell.ai_precision_observation.v2`
  adapter and ordered `ModelMotionBatchV2` producer, including exact
  `localization_uncalibrated` abstention and zero-authority output behavior.
- Retained evaluation: 2,000 disjoint calibration cases, 2,000 held-out cases,
  all 46 keyboard targets, declared coverage 0.99, measured coverage 0.9975,
  conservative planar bound 14.400834977163141 mm.
- Identity: model
  `c9f4ef6d8f9e50317a917154fccacce46506ab2e7cde8267396e28fec156147b`;
  target catalog
  `6779213e832ab27eeda1e7fb245f57ff8cb0d56707b5aa73a8f31ec483a620f2`;
  calibration dataset
  `942ecf9055ffd93e01fa2cfed0745c45c857bbcec9431603497bedd7df1606c0`;
  evaluation dataset
  `0c6a49a46b398de03262a6cf368b7f03b5fe42d8575b1815969871f6be072412`.
- Evidence bundle:
  `990f0736c4b6eaf6799bef079480b7d874290209a5f6427e0f4c010e219d3fd3`.
  It retains aggregate statistics, failure IDs, and per-target ordered-series
  digests instead of 92,000-plus bulk sample lines, satisfying current
  repository evidence policy without changing the measured result.
- Qualification candidate:
  `4811a738f55926cc68a9a4db110d54e589768d0d52301c6b3c8376fc6205f2ba`;
  retained but not installed. The 14.4 mm disk crosses ordinary key safe
  regions, so deployment qualification and physical authority remain false.
- Contract fixture: exact retained model-output record produces ordered
  `H,H,1,PERIOD` bytes; deterministic replay detects batch or metadata drift.
  The research checkpoint and two research modules remain external by digest;
  mainline fails closed with an explicit dependency error when full evaluation
  is requested without them.
- Verification: 64 focused adapter, evidence, schema, strict-ingress, shared
  gate, and conformance tests passed; maintained-doc, public-record, and
  release-integrity checks passed before the final bounded CI run.
- Endpoint/camera opens: 0.
- Hardware writes: 0.
- Physical movements: 0.
- Authority: no joints, controller JSON, permits, transport access, hardware
  access, or physical authority are emitted.
- Next dependency: evaluate final-camera physical originals and produce a
  safe-region-fit uncertainty bound before installing any deployment
  qualification or rerunning the operational-readiness perception gate.

### E-20260927-ARM-074 — T2A jerk-bounded typing trajectory preparation

- Stage: S5 optimization research; T2A of the optimized typing execution plan.
- Lane: ARM.
- Source: T1 `TypingExecutionPlanV1` on GitHub `main` commit `8a19cb0`.
- Change: compiled the exact ordered T1 action chain into semantic Cartesian
  endpoints, bounded-step screening samples, and an analytical quintic
  rest-to-rest timing model. Direct hover-to-hover timing is compared with the
  same actions returning to the route reference after every key.
- Profile: every nonzero endpoint segment uses
  `10s^3 - 15s^4 + 6s^5`; duration is the maximum of the analytical velocity,
  acceleration, and jerk requirements. Collision samples are separate from
  timing endpoints, so sampling density does not create fictitious stops.
- Coverage: `H,H,1,PERIOD` preserves exact contact order and the repeated H;
  dense adjacent samples remain within the configured Cartesian step; all
  computed peak demands remain within the declared Cartesian limits; canonical
  replay is deterministic; invalid dynamics bounds fail closed.
- Synthetic benchmark fixture: 14 semantic endpoints, 87 Cartesian screening
  samples, and 13 timed segments. Under the pinned 80 mm/s, 160 mm/s^2, and
  800 mm/s^3 policy, direct travel was 417.712599485 mm versus
  598.833228888 mm through park; the conservative rest-to-rest estimate was
  16,640.180 ms versus 22,490.212 ms, a 26.0115% reduction. These are model
  outputs for comparison, not measured speed or a release target.
- Endpoint/camera opens: 0.
- Hardware writes: 0.
- Physical movements: 0.
- Authority: controller commands, permits, transport access, hardware access,
  and physical authority remain absent.
- Limitations: no IK or joint-dynamics screen has run; no installed-geometry or
  continuous collision claim is made; the timing estimate is Cartesian and
  rest-to-rest, not measured controller latency or physically qualified speed.
- Next dependency: T2B consumes the exact bounded samples with deterministic IK
  and installed-geometry collision screening, retaining action and hash binding.

### E-20260928-ARM-075 — T2B exact-sample deterministic IK screen

- Stage: S5 optimization research; first software-only half of T2B in the
  optimized typing execution plan.
- Lane: ARM.
- Source: T2A `TypingTrajectoryPlanV1` and the canonical numerical IK acceptance
  gates on branch `codex/typing-t2b-offline-screening`.
- Change: added a hash-bound adapter that consumes the exact ordered T2A
  screening samples, binds them to the pinned build and planner calibration,
  and evaluates each sample through the existing numerical IK, calibrated joint
  bounds, normalized joint margin, task-Jacobian rank, and adjacent-joint
  continuity checks. The seed type accepts only the explicit
  `SYNTHETIC_OFFLINE` classification and cannot claim feedback or measurement.
- Coverage: a local five-millimetre synthetic cycle derived from the pinned
  ready-state FK passes every exact sample deterministically; crossed
  calibration identity, malformed/non-finite joint seeds, and resource limits
  fail closed. Focused result: 3 tests passed.
- Artifacts:
  `software/src/rocell/application/typing_trajectory_ik_screen_v1.py`;
  `software/tests/unit/test_typing_trajectory_ik_screen_v1.py`;
  `software/docs/OPTIMIZED_TYPING_EXECUTION_PLAN.md`.
- Endpoint/camera opens: 0.
- Hardware writes: 0.
- Physical movements: 0.
- Authority: the report contains no controller commands, permits, transport,
  hardware access, observed-feedback claim, or physical authority.
- Limitations: the passing fixture is synthetic and local. No installed
  collision geometry, configuration-sampled cable evidence, conservative
  segment sweep, controller timing, measured route, or physical qualification
  has run. A pass means only that the pinned offline IK acceptance gates accept
  the supplied exact samples.
- Next dependency: bind the exact accepted joint results to the existing
  FK-derived installed-geometry collision sequence and conservative segment
  sweep boundaries. Until those measured inputs exist, retain
  `INSTALLED_GEOMETRY_COLLISION_SCREENING_REQUIRED`.

### E-20260928-ARM-076 — typing collision-evidence intake seam

- Stage: S5 optimization research; second software-only T2B increment.
- Lane: ARM.
- Source: ARM-075 exact-sample IK receipt and the existing installed-geometry,
  FK-derived collision, bounded-segment, and conservative-sweep contracts.
- Change: added a strict hash-bound intake that replays the exact T1/T2A
  lineage, validates the T2B-IK/build/calibration/model identities, preserves
  the `SYNTHETIC_OFFLINE` start-state classification, and reuses the canonical
  bounded joint interpolation. It emits the exact rigid-attachment,
  configuration-body, per-sample geometry, and adjacent-sample sweep-envelope
  evidence slots required by the installed profile.
- Coverage: deterministic missing-profile and matching-profile cases, JSON
  schema validation, crossed/mutated IK rejection, and regression coverage for
  the shared FK/bounded-segment machinery. Focused result: 17 tests passed.
- Artifacts:
  `software/src/rocell/application/typing_collision_intake_v1.py`;
  `software/ai/schemas/typing_collision_intake_v1.schema.json`;
  `software/tests/unit/test_typing_trajectory_ik_screen_v1.py`;
  `software/docs/OPTIMIZED_TYPING_EXECUTION_PLAN.md`.
- Endpoint/camera opens: 0.
- Hardware writes: 0.
- Physical movements: 0.
- Authority: the report contains no commands, transport access, hardware
  access, collision-pass claim, observed-feedback claim, or physical authority.
- Limitations: no measured installed profile is currently supplied to this
  typing route, no cable geometry or sweep envelopes were created, and no
  collision evaluation ran. The synthetic start remains execution-ineligible.
- Next dependency: populate the already enumerated slots from independently
  measured installed geometry and capture a fresh observed start state, then
  pass the exact evidence through the existing FK, bounded-sample, and
  conservative-sweep qualifiers.

### E-20260927-AI-404 — pose-checkpoint package test collection failure

- Stage: S1 artifact identity and retention.
- Lane: AI.
- Source baseline: protected GitHub `main`
  `f32c3deadee78fb2871018e39e892079f096032a`.
- Change: first combined source/contract test invocation for the focused #56/#61
  pose-keyloss external-artifact package.
- Command: `python -m pytest scripts/ci/test_check_external_artifact.py software/ai/tests/test_pose_checkpoint_external_artifact_source.py -q` from the repository root.
- Result: FAIL during collection before any assertion because the new test did
  not add `software/ai` to `sys.path`; `ModuleNotFoundError: No module named
  'eval'`. The manifest, checkpoint identity, verifier behavior, and artifact
  bytes were unchanged. The generic artifact-present checker and the focused
  verifier independently returned `verified` during the same shell increment.
- Endpoint/camera opens: 0.
- Hardware writes: 0.
- Physical movements: 0.
- Authority: no model load, controller access, permit, transport, or physical
  authority.
- Limitations: test-harness import-path failure only; no clean-clone receipt or
  reviewable completion claim existed.
- Supersedes: none; this failed collection remains preserved.
- Next dependency: add only the missing test import path and rerun the identical
  combined suite.

### E-20260927-AI-405 — pose-keyloss external-artifact source freeze

- Stage: S1 artifact identity and retention.
- Lane: AI.
- Source baseline: protected GitHub `main`
  `f32c3deadee78fb2871018e39e892079f096032a`; research history branch
  `feature/translation-pair-evidence` remains unchanged.
- Change: pinned the translation-weighted pose-keyloss checkpoint as an external
  artifact and froze a focused zero-authority verifier, tests, and reproduction
  instructions before generating either requested receipt.
- Identity: repository path
  `software/ai/results/translation_weighted_v0_translation_weighted/pose_model.pt`;
  exact size 1,111,650 bytes; SHA-256
  `0fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d`;
  manifest SHA-256
  `bc67bee359bc9458adb99334ccc08830023c25467e59897b015cef58c5dc4a87`.
- Provenance: frozen producer commit
  `fe20dc15376361f38049e4791583af72b62e5a77`; credential-free command
  `python software/ai/vision/train_translation_weighted.py`; retention owner
  Tactevra AI producer (`j-webtek`), review after 2027-09-27.
- Command: `python -m pytest scripts/ci/test_check_external_artifact.py software/ai/tests/test_pose_checkpoint_external_artifact_source.py -q`; `python -m py_compile software/ai/eval/verify_pose_checkpoint_artifact.py`; `git diff --check`.
- Result: PASS: 8 tests in 0.07s, source compilation passed, and the diff check
  was clean. Tests assert exact identity/provenance, the exact
  `external_artifact_unavailable` clean-root state, and fail-closed expected-state
  mismatch. The verifier binds the existing repository checker hash, records
  separate artifact read/write counts, and accepts only unavailable or verified.
- Artifacts: compact manifest, `verify_pose_checkpoint_artifact.py`, focused
  source test, reproduction/provenance instructions, this evidence row.
- Endpoint/camera opens: 0.
- Hardware writes: 0.
- Physical movements: 0.
- Authority: artifact identity only; no model promotion, qualification,
  controller access, transport, or release approval.
- Limitations: source and contract verification only. No receipt or compact
  result scorecard is claimed in this increment. Reproduction additionally
  requires the pinned external starting checkpoint and environment.
- Supersedes: none.
- Next dependency: commit this freeze, create a fresh worktree from that exact
  commit and record `external_artifact_unavailable`, separately verify the local
  external bytes as `verified`, then commit both receipts and a compact scorecard.

### E-20260927-AI-406 — first clean-worktree creation blocked by path length

- Stage: S1 artifact identity and retention.
- Lane: AI.
- Commit: `88a018d75cb8245d079148503aa46929a0c4efc9`.
- Change: attempted to create the requested clean evidence worktree beneath the
  already deep workspace path.
- Inputs/fixtures: committed source-freeze tree only; external checkpoint absent.
- Command: `git worktree add --detach _tmp/pose-checkpoint-clean 88a018d75cb8245d079148503aa46929a0c4efc9`.
- Result: BLOCKED before verification because Windows path length prevented the
  checkout from materializing repository files. No receipt was generated and
  the partial path was not used as evidence.
- Artifacts: none.
- Hardware writes: 0.
- Physical movements: 0.
- Limitations: environment/path failure only; it establishes no artifact state.
- Supersedes: none; this blocked attempt remains preserved.
- Next dependency: create a registered detached worktree at a short canonical
  path and rerun the unavailable check from that exact commit.

### E-20260927-AI-407 — repository evidence-scope precheck lacked sparse input

- Stage: S1 artifact identity and retention.
- Lane: AI.
- Commit: `88a018d75cb8245d079148503aa46929a0c4efc9`.
- Change: ran the retention-budget precheck before the main sparse checkout
  included its policy configuration.
- Inputs/fixtures: changed pose artifact package; sparse checkout without
  `.github/evidence-retention-exceptions.json`.
- Command: `python scripts/ci/check_evidence_scope.py`.
- Result: BLOCKED because the policy configuration was absent from the sparse
  worktree. No evidence files were removed, rewritten, or exempted.
- Artifacts: none.
- Hardware writes: 0.
- Physical movements: 0.
- Limitations: checkout-materialization failure only; it is not a policy pass.
- Supersedes: none; the later successful run is recorded separately.
- Next dependency: materialize `.github` and rerun the identical command.

### E-20260927-AI-408 — portable-suite sparse-materialization failures

- Stage: S1 artifact identity and retention.
- Lane: AI.
- Commit: `88a018d75cb8245d079148503aa46929a0c4efc9`.
- Change: exercised the repository's portable install and test flow in fresh
  detached worktree `C:\\p56`, preserving each incomplete sparse checkout.
- Inputs/fixtures: clean committed tree with the external checkpoint absent;
  progressively materialized `software/tests/integration`, `software/scripts`,
  `software/native`, `software/firmware`, and `software/tests/fixtures`.
- Command: `.\\.venv-ci\\Scripts\\python.exe scripts/ci/offline_checks.py test`
  after each sparse-checkout increment.
- Result: FAIL/BLOCKED in three attempts: first the integration test directory
  was absent; next `software/scripts` was absent; then 480 passed, 16 failed,
  and 4 skipped because native review, firmware, and zero-write fixture inputs
  were absent. These were checkout omissions, not corrected test results.
- Artifacts: console results only; no receipt was accepted from these attempts.
- Hardware writes: 0.
- Physical movements: 0.
- Limitations: the failed attempts did not evaluate a complete committed tree.
- Supersedes: none; all failed attempts remain preserved.
- Next dependency: materialize the named committed inputs and rerun the same
  portable test command once against the complete required selection.

### E-20260927-AI-409 — repository audit sparse-materialization failures

- Stage: S1 artifact identity and retention.
- Lane: AI.
- Commit: `88a018d75cb8245d079148503aa46929a0c4efc9`.
- Change: ran the maintained-document and public-record audits before their
  tracked assets were materialized by the main sparse checkout.
- Inputs/fixtures: focused six-path artifact package; sparse checkout initially
  omitted `assets`, `active-project`, `presentations`, `software/freezes`, and
  then `software/native/windows_usb_identity`.
- Command: `python scripts/ci/check_docs.py`; `python scripts/ci/check_public_records.py`.
- Result: BLOCKED. The first run reported missing tracked brand/media and linked
  documentation; after adding their parent selections, the document check still
  reported the omitted Windows USB identity README. Public-record validation
  passed as soon as its tracked media receipt was materialized. No tracked file
  was edited to suppress a result.
- Artifacts: console results only.
- Hardware writes: 0.
- Physical movements: 0.
- Limitations: sparse checkout failures only; they are not audit passes.
- Supersedes: none; final complete-input audit results are recorded separately.
- Next dependency: materialize every named tracked input and rerun the identical
  checks.

### E-20260927-AI-410 — pose-keyloss external-artifact evidence package verified

- Stage: S1 artifact identity and retention.
- Lane: AI.
- Commit: `88a018d75cb8245d079148503aa46929a0c4efc9`.
- Change: completed the focused #56/#61 package with separate clean-clone and
  artifact-present receipts, a compact reconciled scorecard, and no binary or
  bulk report.
- Inputs/fixtures: manifest SHA-256
  `bc67bee359bc9458adb99334ccc08830023c25467e59897b015cef58c5dc4a87`;
  external checkpoint size 1,111,650 and SHA-256
  `0fd4ee3edd1dc6e0068c6e1530fdf7017a77a3e7841334682272e99aa344125d`;
  source scorecard SHA-256
  `1af39548986a69deea0a4a7a03f75749ae5a9f78ee86fc418489cb3e88e4888f`.
- Command: `python software/ai/eval/verify_pose_checkpoint_artifact.py --root C:\\p56 --manifest C:\\p56\\software/ai/manifests/translation_weighted_pose_keyloss_v0.external.json --expect external_artifact_unavailable --output software/ai/eval/pose_keyloss_external_artifact_unavailable_receipt.json`; `python software/ai/eval/verify_pose_checkpoint_artifact.py --root . --expect verified --output software/ai/eval/pose_keyloss_external_artifact_verified_receipt.json`; `python -m pytest scripts/ci/test_check_external_artifact.py software/ai/tests/test_pose_checkpoint_external_artifact_source.py software/ai/tests/test_pose_checkpoint_external_artifact_result.py -q`; `python scripts/ci/check_evidence_scope.py`; `python scripts/ci/check_docs.py`; `python scripts/ci/check_public_records.py`; `python scripts/ci/check_repository_artifacts.py`; `python scripts/ci/check_release_integrity.py`; and, in `C:\\p56`, `.\\.venv-ci\\Scripts\\python.exe scripts/ci/offline_checks.py test`.
- Result: PASS. Clean clone returned exactly `external_artifact_unavailable`;
  separately present bytes returned exactly `verified`; 11 focused tests passed
  in 0.09s; evidence scope passed; portable suite passed 496 with 4 documented
  Windows symlink skips in 66.93s. Documentation, public-record, repository-
  artifact, and release-integrity audits passed with complete tracked inputs.
  Development candidate metrics were mean key
  error 0.906526367 mm, p95 2.051064264 mm, and within-1-mm fraction
  0.690217391; model promotion and qualification remain false.
- Artifacts: unavailable receipt SHA-256
  `e9347f172421bc6faa8b8a75b176cbcf25f8e5b75ca6518e84673008abb8110c`;
  verified receipt SHA-256
  `09d0b08b20acbd120b255e018a69b1867de2c2b99fe7b497789adcc793ca8b7a`;
  compact scorecard SHA-256
  `0fb3077fcea31a61b4d6c977e4266f5b313ac69497af021bf697e02dcbc5fb3f`.
- Hardware writes: 0.
- Physical movements: 0.
- Limitations: synthetic development selection with one seed per arm; identity
  verification does not establish real-camera accuracy, safe-region fit,
  physical contact success, model promotion, qualification, or runtime authority.
- Supersedes: none. AI-406 through AI-409 remain failed/blocked history.
- Next dependency: review and merge the focused package, then obtain final-camera
  physical originals and safe-region-fit uncertainty before qualification.

### E-20260927-AI-411 — camera campaign source-freeze diff failure

- Stage: S2/S3 physical-camera localization readiness.
- Lane: AI.
- Commit: `844f1e58fb2cb31b2d8555d9f76d12259d90a65d`.
- Change: first source freeze for the physical-camera campaign contract,
  preflight, runbook, schemas, and focused tests.
- Inputs/fixtures: schema-authored 300-capture calibration and 300-capture
  evaluation fixture with 1,200 retained temporary files and all 11 required
  evaluation conditions.
- Command: `git diff --cached --check`.
- Result: FAIL: two Markdown lines in the new runbook had trailing whitespace.
  The commit completed because the shell command did not stop on that nonzero
  subcommand; the failure is retained instead of being rewritten as a pass.
- Artifacts: source commit above; no evaluation receipt or physical original.
- Hardware writes: 0.
- Physical movements: 0.
- Limitations: formatting failure only; it is not evidence that preflight or
  physical localization succeeded.
- Supersedes: none.
- Next dependency: remove only the trailing whitespace in a separate commit,
  rerun the diff check, and verify the corrected source.

### E-20260927-AI-412 — portable-runner environment failures

- Stage: S2/S3 physical-camera localization readiness.
- Lane: AI.
- Commit: `3a8ef7a5a946f3b10d685522da365880bbc5a0b1`.
- Change: attempted the repository portable suite against the corrected camera
  campaign source before the detached test environment was complete.
- Inputs/fixtures: corrected committed source; no physical camera files.
- Command: `python scripts/ci/offline_checks.py test`; then
  `C:\\camtest\\.venv-ci\\Scripts\\python.exe scripts/ci/offline_checks.py install-base`,
  `smoke`, `install-tests`, and `test`; then, from `C:\\camtest`,
  `.\\.venv-ci\\Scripts\\python.exe scripts/ci/offline_checks.py test`.
- Result: BLOCKED in three preserved attempts: the primary worktree lacked
  `.venv-ci`; the next invocation used the wrong current directory; and the
  first detached-worktree test lacked sparse-selected integration files. No
  test failure was converted into a pass and no source was changed to bypass
  the runner.
- Artifacts: console output only.
- Hardware writes: 0.
- Physical movements: 0.
- Limitations: environment and sparse-checkout failures only; they do not
  assess physical data or model accuracy.
- Supersedes: none.
- Next dependency: materialize the runner's committed integration, script,
  native, firmware, and fixture inputs, then rerun the identical test command.

### E-20260927-AI-413 — physical-camera localization test baseline prepared

- Stage: S2/S3 physical-camera localization readiness.
- Lane: AI.
- Commit: `3a8ef7a5a946f3b10d685522da365880bbc5a0b1`.
- Change: froze a strict external physical-camera campaign contract, a
  content-verifying read-only preflight receipt, an operator runbook, and
  focused tests. The package requires disjoint calibration/evaluation sessions,
  at least 300 captures per split, at least 20 held-out captures for each of 11
  lighting/blur/occlusion/placement/absence conditions, immutable camera/mode/
  epoch identities, and independent surveyed-fiducial ground truth.
- Inputs/fixtures: generated temporary 300/300 split fixture; 600 unique image
  identities, 600 unique ground-truth identities, two disjoint sessions, and
  minimum held-out condition count 27. No fixture bytes were retained in Git.
- Command: `python -m pytest software/ai/tests/test_physical_camera_localization_campaign.py -q`; `python -m py_compile software/ai/eval/preflight_physical_camera_campaign.py`; `git diff --check`; `python scripts/ci/check_evidence_scope.py`; `python scripts/ci/check_docs.py`; `python scripts/ci/check_public_records.py`; `python scripts/ci/check_repository_artifacts.py`; `python scripts/ci/check_release_integrity.py`; and, in detached worktree `C:\\camtest`, `.\\.venv-ci\\Scripts\\python.exe scripts/ci/offline_checks.py test`.
- Result: PASS: 6 focused tests in 2.60 seconds; compilation and all repository
  audits passed; portable suite passed 496 with 4 documented Windows symlink
  skips in 72.62 seconds. Tests reject duplicate JSON fields, split-session
  overlap, declared-only condition coverage, and altered retained bytes.
- Artifacts: `software/ai/docs/PHYSICAL_CAMERA_LOCALIZATION_CAMPAIGN.md`;
  `software/ai/schemas/physical_camera_localization_campaign_v1.schema.json`;
  `software/ai/schemas/physical_camera_localization_preflight_receipt_v1.schema.json`;
  `software/ai/eval/preflight_physical_camera_campaign.py`.
- Hardware writes: 0.
- Physical movements: 0.
- Limitations: readiness contract only. No camera was opened, no physical image
  was collected, no model was loaded, no localization metric was measured, no
  qualification was installed, and no arm or integration status changed.
- Supersedes: none. AI-411 and AI-412 remain failed/blocked history.
- Next dependency: retain the four ARM-070 physical originals, freeze the final
  configuration epoch and calibrations, collect the external campaign, and run
  this preflight before any model evaluation.

### E-20260927-AI-414 — initial full AI suite exposed environment-sensitive assertion

- Stage: S1/S2/S3 documentation and test governance.
- Lane: AI.
- Commit: `10a148ff8730c0ed54a1fbb643fb6718d764a84d`.
- Change: exercised every AI test while assembling the workstream registry and
  found an existing assertion that assumed one external research checkpoint was
  always absent even when its bytes happened to exist locally.
- Inputs/fixtures: all 34 tracked AI test modules; local external research
  artifact state, with several declared sources absent and one checkpoint
  present.
- Command: `python -m pytest software/ai/tests -q`.
- Result: FAIL: 1 failed and 166 passed. The evaluator correctly failed closed
  for missing declared research inputs, but
  `test_full_evaluator_fails_closed_when_research_artifacts_are_external`
  asserted one hard-coded missing path instead of the evaluator's actual
  declared missing set.
- Artifacts: corrected source is retained in the named commit; the test now
  verifies a nonempty missing set, membership in declared dependencies, and
  actual absence for every reported path.
- Hardware writes: 0.
- Physical movements: 0.
- Limitations: developer-environment portability failure only; no model metric,
  checkpoint quality, calibration, or physical behavior was evaluated.
- Supersedes: none; the failed result remains preserved.
- Next dependency: rerun the complete AI suite after freezing the corrected
  assertion and its declared dependency set.

### E-20260927-AI-415 — registry source freeze rejected CRLF-generated JSON

- Stage: S1/S2/S3 documentation and test governance.
- Lane: AI.
- Commit: `10a148ff8730c0ed54a1fbb643fb6718d764a84d`.
- Change: attempted the first staged source freeze for the handbook, registry,
  schemas, audit receipt, and ownership tests.
- Inputs/fixtures: staged registry and receipt generated by Windows text-mode
  writes.
- Command: `git diff --cached --check`.
- Result: FAIL: every generated JSON line was reported with trailing
  whitespace because CRLF bytes reached the staged files. The source was
  normalized to LF and the receipt writer was changed to `write_bytes` before
  the named commit was created.
- Artifacts: `software/ai/eval/audit_ai_work_registry.py` and the normalized
  registry/receipt in the named commit.
- Hardware writes: 0.
- Physical movements: 0.
- Limitations: source-format failure only; it established no documentation
  completeness or model result.
- Supersedes: none; the failed freeze remains preserved.
- Next dependency: rerun the registry audit and staged diff check using the
  byte-stable writer.

### E-20260927-AI-416 — clean standard test environment lacked AI research dependencies

- Stage: S1/S2/S3 documentation and test governance.
- Lane: AI.
- Commit: `10a148ff8730c0ed54a1fbb643fb6718d764a84d`.
- Change: ran the entire AI suite in a detached clean environment containing
  only the repository's standard base and test dependencies.
- Inputs/fixtures: exact committed tree in `C:\\aidocs`; `.venv-ci` created by
  the maintained portable installer; no model binary was added.
- Command: `.\\.venv-ci\\Scripts\\python.exe -m pytest software/ai/tests -q`.
- Result: BLOCKED during collection: five localization research modules raised
  `ModuleNotFoundError: No module named 'numpy'`. This showed that the full AI
  suite depended on undeclared research packages even though the portable
  boundary suite passed 496 tests with 4 documented Windows symlink skips.
- Artifacts: console result only; no failed receipt was promoted.
- Hardware writes: 0.
- Physical movements: 0.
- Limitations: dependency declaration failure only; it did not evaluate model
  quality or physical readiness.
- Supersedes: none; the blocked clean run remains preserved.
- Next dependency: declare an isolated, exact AI test dependency set and repeat
  the full suite from a clean committed checkout.

### E-20260927-AI-417 — first isolated AI environment command used the wrong installer contract

- Stage: S1/S2/S3 documentation and test governance.
- Lane: AI.
- Commit: `429ac7a9de3afa4354ae2410c8b61fb618158570`.
- Change: tested the first written `.venv-ai` setup procedure in a detached
  checkout.
- Inputs/fixtures: clean commit, newly created `.venv-ai`, exact
  `numpy==2.2.6` and `torch==2.5.1` requirements file.
- Command: `.\\.venv-ai\\Scripts\\python.exe scripts/ci/offline_checks.py install-base`.
- Result: FAIL before installation: `offline_checks.py` intentionally requires
  a repository-root `.venv-ci` and rejected `.venv-ai`. The procedure was
  corrected to invoke `pip install ".\\software[test]"` directly in the isolated
  AI environment.
- Artifacts: corrected instructions are retained in commit
  `d33326716ce02d461046c76fbe4f9b301bb1d6dc`.
- Hardware writes: 0.
- Physical movements: 0.
- Limitations: procedure validation failure only; no tests or model evaluation
  ran.
- Supersedes: none; the invalid command remains preserved.
- Next dependency: recreate the environment from the corrected committed
  instructions and run `pip check` before testing.

### E-20260927-AI-418 — sparse clean-checkout materialization failures

- Stage: S1/S2/S3 documentation and test governance.
- Lane: AI.
- Commit: `d33326716ce02d461046c76fbe4f9b301bb1d6dc`.
- Change: validated the corrected AI environment and full suite in a deliberately
  sparse detached worktree before expanding it to the complete committed tree.
- Inputs/fixtures: sparse selections initially omitted `software/src`, then
  arm unit-test helper modules, and then configuration/static simulation files.
- Command: `.\\.venv-ai\\Scripts\\python.exe -m pip install ".\\software[test]"`;
  then `.\\.venv-ai\\Scripts\\python.exe -m pytest software/ai/tests -q` after
  each sparse expansion.
- Result: BLOCKED/FAIL in preserved attempts: package build first reported
  missing `src`; collection next reported four missing
  `test_model_motion_ingress_v2` imports; the following run reached 105 passes
  but ended with 58 failures and 4 errors because target profiles and the static
  simulation bundle were not materialized. These files exist in the commit and
  a full checkout; no source was changed to hide the failures.
- Artifacts: console results only.
- Hardware writes: 0.
- Physical movements: 0.
- Limitations: sparse-checkout construction failures only. They are not AI
  behavior regressions or a valid clean-clone test result.
- Supersedes: none; all sparse failures remain preserved.
- Next dependency: disable sparse checkout and rerun identical environment,
  suite, and audit commands against the complete committed tree.

### E-20260927-AI-419 — AI work, testing, and evidence baseline verified

- Stage: S1/S2/S3 documentation and test governance.
- Lane: AI.
- Commit: `d33326716ce02d461046c76fbe4f9b301bb1d6dc`.
- Change: completed the maintained AI handbook, seven-workstream registry,
  registry and receipt schemas, machine audit, test ownership guide, exact AI
  research test requirements, navigation, and portable failure correction.
- Inputs/fixtures: complete clean committed checkout; Python 3.12.0;
  `numpy==2.2.6`; `torch==2.5.1`; 34 tracked AI test modules; 105 registry
  source/document/test/evidence paths; all repository portable fixtures.
- Command: `python -m venv .venv-ai`; `.\\.venv-ai\\Scripts\\python.exe -m pip install ".\\software[test]"`; `.\\.venv-ai\\Scripts\\python.exe -m pip install -r software/ai/requirements-test.txt`; `.\\.venv-ai\\Scripts\\python.exe -m pip check`; `.\\.venv-ai\\Scripts\\python.exe -m pytest software/ai/tests -q`; `.\\.venv-ai\\Scripts\\python.exe software/ai/eval/audit_ai_work_registry.py`; `.\\.venv-ai\\Scripts\\python.exe scripts/ci/check_docs.py`; `.\\.venv-ai\\Scripts\\python.exe scripts/ci/check_evidence_scope.py`; `.\\.venv-ai\\Scripts\\python.exe scripts/ci/check_public_records.py`; `.\\.venv-ai\\Scripts\\python.exe scripts/ci/check_repository_artifacts.py`; `.\\.venv-ai\\Scripts\\python.exe scripts/ci/check_release_integrity.py`; then `python -m venv .venv-ci` and `.\\.venv-ci\\Scripts\\python.exe scripts/ci/offline_checks.py install-base`, `smoke`, `install-tests`, and `test`.
- Result: PASS: `pip check` reported no broken requirements; the full AI suite
  passed 167 tests and 47 subtests in 38.04 seconds; the registry audit passed
  with 7 workstreams, 34/34 uniquely owned test modules, 105 existing referenced
  paths, registry SHA-256
  `ea5da4211f33041e8adad425e6e190bb3df4a5dc9e5f5f313f4956b4faaef34d`,
  and receipt SHA-256
  `db64a0b41fa9044be5056c5b56073034aa83771358452e627976a0953a411b10`;
  all six repository audits passed; the portable suite passed 496 tests with 4
  documented Windows symlink skips in 71.81 seconds.
- Artifacts: `software/ai/docs/AI_WORK_AND_EVIDENCE_HANDBOOK.md`;
  `software/ai/docs/AI_WORK_REGISTRY.json`;
  `software/ai/eval/ai_work_registry_audit_v1.json`;
  `software/ai/tests/README.md`; `software/ai/requirements-test.txt`.
- Hardware writes: 0.
- Physical movements: 0.
- Limitations: this proves documentation coverage, path integrity, test
  reproducibility, and declared zero authority. It does not prove model
  correctness outside retained benchmarks, camera calibration, localization
  qualification, key contact, phone operation, or integration readiness.
- Supersedes: none. AI-414 through AI-418 remain visible failed/blocked history.
- Next dependency: merge this documentation baseline, collect the four retained
  ARM-070 camera/support originals, and execute the frozen physical-camera
  campaign before any localization qualification claim.

### E-20260927-AI-420 — prerequisite PR merge attempts blocked by repository policy

- Stage: S2/S3 physical-camera evaluation preparation.
- Lane: AI.
- Commit: `555ddd72952cd5560c6ae1f4bc2605f8361d4e09`.
- Change: attempted to land the camera campaign and documentation prerequisites
  before creating the evaluator branch.
- Inputs/fixtures: PR #147 at
  `f357fa54536c9cb9315aee15107a5a610efce01a`; PR #148 at
  `555ddd72952cd5560c6ae1f4bc2605f8361d4e09`; protected `main`.
- Command: GitHub REST `PUT /repos/j-webtek/tactevra/pulls/147/merge` with
  `merge_method=merge`, followed by the same endpoint with
  `merge_method=squash`.
- Result: BLOCKED in two preserved attempts. The repository rejected merge
  commits, then rejected squash because protected `main` had advanced and six
  required checks were expected on the updated base. No protection was bypassed.
- Artifacts: GitHub PRs #147 and #148; console/API responses only.
- Hardware writes: 0.
- Physical movements: 0.
- Limitations: repository administration failure only; it evaluates no model,
  camera, localization result, or runtime behavior.
- Supersedes: none; the rejected attempts remain visible.
- Next dependency: merge current protected `main` into both branches, retain
  both workers' ledger content, rerun required checks, and use the permitted
  squash method.

### E-20260927-AI-421 — evaluator portable suite initially lacked sparse paths

- Stage: S2/S3 physical-camera evaluation preparation.
- Lane: AI.
- Commit: `56252e47558e6aa0a351f61611d7de0e5a8a49c4`.
- Change: ran the portable repository suite in detached worktree
  `C:\\aievaluate` after exact-source AI verification.
- Inputs/fixtures: clean source commit, installed `.venv-ci`, inherited sparse
  worktree selection that omitted `software/tests/integration`.
- Command: `.\\.venv-ci\\Scripts\\python.exe scripts/ci/offline_checks.py test`.
- Result: BLOCKED before collection because
  `software/tests/integration/test_zero_write_waveshare_contract_v1.py` was not
  materialized. Git tree inspection confirmed the file was present in the
  commit. No source or test list was changed.
- Artifacts: console result only.
- Hardware writes: 0.
- Physical movements: 0.
- Limitations: worktree materialization failure only; it is not an evaluator or
  repository regression.
- Supersedes: none; the failed portable attempt remains preserved.
- Next dependency: materialize the tracked integration, script, native,
  firmware, and fixture paths and rerun the identical command.

### E-20260927-AI-422 — fail-closed physical-camera evaluator verified

- Stage: S2/S3 physical-camera localization evaluation.
- Lane: AI.
- Commit: `56252e47558e6aa0a351f61611d7de0e5a8a49c4`.
- Change: implemented the offline post-preflight evaluator, strict ground-truth,
  evaluation-plan, and result schemas, image/model/preprocessing prediction
  binding, calibration-only empirical bound, held-out per-target/per-condition
  metrics, unsafe-scene false-accept checks, evidenced uncertainty composition,
  frozen target-safe-region checks, documentation, registry ownership, and
  non-finite JSON rejection.
- Inputs/fixtures: generated 300-calibration/300-evaluation retained campaign;
  600 unique image and truth identities; 11 required conditions; two targets;
  image-bound frozen prediction records; synthetic test-only 1.0 mm calibration
  maximum, 0.4 mm additional evidenced uncertainty, and 2.0 mm safe radii. No
  fixture or claimed physical score was retained.
- Command: in clean detached worktree `C:\\aievaluate`, `python -m venv .venv-ai`;
  `.\\.venv-ai\\Scripts\\python.exe -m pip install ".\\software[test]"`;
  `.\\.venv-ai\\Scripts\\python.exe -m pip install -r software/ai/requirements-test.txt`;
  `.\\.venv-ai\\Scripts\\python.exe -m pip check`;
  `.\\.venv-ai\\Scripts\\python.exe -m pytest software/ai/tests -q`;
  `.\\.venv-ai\\Scripts\\python.exe software/ai/eval/audit_ai_work_registry.py`;
  `.\\.venv-ai\\Scripts\\python.exe scripts/ci/check_docs.py`;
  `.\\.venv-ai\\Scripts\\python.exe scripts/ci/check_evidence_scope.py`;
  `.\\.venv-ai\\Scripts\\python.exe scripts/ci/check_public_records.py`;
  `.\\.venv-ai\\Scripts\\python.exe scripts/ci/check_repository_artifacts.py`;
  `.\\.venv-ai\\Scripts\\python.exe scripts/ci/check_release_integrity.py`;
  and, after materializing the tracked portable inputs,
  `.\\.venv-ci\\Scripts\\python.exe scripts/ci/offline_checks.py test`.
- Result: PASS. Clean full AI suite passed 174 tests and 47 subtests in 54.44
  seconds. Registry audit passed with 7 workstreams, 35/35 uniquely owned AI
  test modules, 110 referenced paths, registry SHA-256
  `05f4b615b1ae1d9182d199b1e13ce66200f99b459996b113a3da0e58197961b9`,
  and receipt SHA-256
  `7cb7bb02ea9dacc607beccf12897f386ccc4e0da34039595d1f99975b3d63813`.
  All six repository audits passed. The corrected portable suite passed 496
  tests with 4 documented Windows symlink skips in 72.41 seconds. Focused tests
  prove recommendation, safe-region blocking, unsafe false-accept blocking,
  held-out coverage blocking, identity/coverage rejection, and non-finite-number
  rejection.
- Artifacts: `software/ai/eval/evaluate_physical_camera_localization.py`;
  `software/ai/schemas/physical_camera_localization_ground_truth_v1.schema.json`;
  `software/ai/schemas/physical_camera_localization_evaluation_plan_v1.schema.json`;
  `software/ai/schemas/physical_camera_localization_evaluation_result_v1.schema.json`;
  `software/ai/tests/test_physical_camera_localization_evaluator.py`;
  `software/ai/docs/PHYSICAL_CAMERA_LOCALIZATION_CAMPAIGN.md`.
- Hardware writes: 0.
- Physical movements: 0.
- Limitations: synthetic fixtures validate evaluator behavior only. No physical
  camera data, model inference, coordinate accuracy, calibration accuracy,
  safe-region qualification, motion batch, key contact, or device outcome was
  produced. Prediction provenance still depends on a separately frozen
  inference producer. `QUALIFICATION_RECOMMENDED` remains an offline review
  recommendation; installation is always false.
- Supersedes: none. AI-420 and AI-421 remain preserved blocked history.
- Next dependency: implement and freeze the image/model/preprocessing-bound
  physical-camera inference producer, then collect the four ARM-070 originals
  and external 300/300 campaign before running this evaluator on real evidence.

### E-20260928-AI-423 — FREEZE-013 static simulation bundle reconciliation

- Stage: S1/S2/S3 simulation and evidence governance.
- Lane: AI with repository review.
- Commit: `869d6f7ed7d1013a8003457a819ccaee3a03a1e7`.
- Change: compared the stale static bundle boundary to the active governed
  FREEZE-013 state, minted immutable bundle identity
  `ROCELL-STATIC-B0477-SIM-BUNDLE-002`, rebound the two changed artifacts, and
  retained a machine-readable reconciliation record for issue #167.
- Inputs/fixtures: prior bundle-001 lock SHA-256
  `e825dd29cf856cea44d9ce40ca3bfb5fc305d3493cd129d6b6bea9f04c800f7c`;
  prior FREEZE-011 manifest SHA-256
  `e85120de64b2128a2f5ab0f4e9f8868f6070e485f747234f89c813d910b5b0f1`;
  active FREEZE-013 manifest SHA-256
  `0cfb19c0972d4fe5cc526ca78d44422b2ef9c52354a8da637ec608b8dec7f55d`;
  refreeze transaction SHA-256
  `d1c9175a71b7e6c7a5dcbf5c43eaea70c300c3f7df15f67313355812944e571b`.
- Determination: FREEZE-013 is the intended source state. The manifest changed
  only its identity/date and the Step 00 `INDEX.json` and
  `PACKAGE_VALIDATION.json` provenance hashes. The simulation hardware profile
  changed only `binding.system_manifest_id`. Robot numerics, targets, optics,
  support design, kinematic model, arm frame contract, semantic bindings, and
  all physical-authority flags remained unchanged.
- Command: clean Python 3.10.10 `.venv-ai`; install `.[test]` and
  `software/ai/requirements-test.txt`; `pip check`; run
  `python -m pytest software/ai/tests -q`; run the AI registry, docs,
  evidence-scope, public-records, repository-artifact, and release-integrity
  audits; create maintained `.venv-ci` and run `offline_checks.py install-base`,
  `smoke`, `install-tests`, and `test`.
- Result: PASS. `pip check` reported no broken requirements; the focused static
  context suite passed 33 tests; the full AI suite passed 174 tests and 47
  subtests; all six repository audits passed; the portable repository suite
  passed 507 tests.
- Artifacts:
  `software/ai/eval/static_simulation_bundle_002_reconciliation.json`;
  `software/config/static_simulation_bundle_lock.json`;
  `software/tests/unit/test_static_simulation_context.py`.
- Hardware writes: 0.
- Physical movements: 0.
- Limitations: this proves exact source reconciliation, fail-closed loading,
  and software-suite health only. It does not promote a model, release a
  physical freeze, establish camera calibration or localization accuracy,
  authorize controller execution, prove contact, or demonstrate device input.
- Supersedes: none. Bundle 001 remains an immutable prior evidence boundary in
  Git history; bundle 002 is a new identity rather than a silent rewrite.
- Next dependency: merge the reviewed reconciliation, close issue #167, and
  retain issue #88 as the remaining source-preview blocker.

### E-20260929-INT-424 — Isaac WP0 test checkout was incomplete

- Stage: S2/S3 simulation oracle WP0.
- Lane: INTEGRATION.
- Commit: `2973bf912445ce70be26c8e88c6eb6ae256b4611`.
- Change: ran the merged Isaac request/receipt contract suite beside the new
  runner-probe tests in the issue #190 worktree before the sparse checkout had
  materialized every tracked WP0 input.
- Inputs/fixtures: tracked paths
  `software/tests/fixtures/isaac_sim/` and `software/schemas/`; contract-test
  source SHA-256
  `01bc2497819d266ee7081646a3e7d4a2ea6557130eac30a222a422ee21805e2b`.
- Command: `python -m pytest software/tests/unit/test_isaac_sim_host_probe.py software/tests/unit/test_isaac_sim_contracts.py -q`; then
  `git sparse-checkout add software/tests/fixtures software/integrations; python -m pytest software/tests/unit/test_isaac_sim_host_probe.py software/tests/unit/test_isaac_sim_contracts.py -q`.
- Result: BLOCKED. The first attempt reported 8 failed and 6 passed because all
  tracked Isaac fixtures were absent. The second reported 2 failed and 12
  passed because both tracked JSON schemas were still absent. Both failures
  were checkout-materialization errors; no validator behavior was changed.
- Artifacts: console results only; tracked fixtures and schemas remain the
  unchanged test inputs.
- Hardware writes: 0.
- Physical movements: 0.
- Limitations: this is worktree setup evidence. It evaluates no Isaac physics,
  USD asset, collision, contact, camera, arm command, or physical outcome.
- Supersedes: none; both failed attempts remain recorded here.
- Next dependency: materialize `software/schemas/` and rerun the identical
  focused suite before relying on WP0 results.

### E-20260929-INT-425 — Isaac Sim 6.1.0 runner candidate installed and bound

- Stage: S2/S3 simulation oracle WP0.
- Lane: INTEGRATION.
- Commit: `2973bf912445ce70be26c8e88c6eb6ae256b4611`.
- Change: installed the exact Isaac Sim 6.1.0 Python distribution and CUDA 13
  Torch in a dedicated external environment; added a standard-library-only
  host probe that hashes installed distribution metadata without importing or
  launching Isaac; retained a compact zero-authority candidate report; and
  added deterministic, fail-closed hardware-free tests and runner guidance.
- Inputs/fixtures: host-probe artifact SHA-256
  `063a4fe5afae0f786043b9eae36cad28b69ca224eddb8e47c84252dc757eb017`;
  probe source SHA-256
  `d911c6d30fc365e78b943712db2abeedb72326ef3dd2ce7b8b6315ffbc750914`;
  probe-test SHA-256
  `2b72270544a3919256a4b52dad0d96bbdef5473a3ccdcd40d55ae97281186b1f`;
  unchanged fail-closed toolchain-lock SHA-256
  `171da8d802226145f382041e1ca321cc1665ecb1f356933e48b4a5989928d42e`.
  The report binds 26 distributions, installation digest
  `ccb196b9c987865ee86918301f00705b1dd5a42449c3119f2119aeb2adf51258`,
  extension digest
  `3a510e375fc27c0ac2b540e14976ef6ae4255286d43753b45fc999ce2188e8bc`,
  driver 591.86, and two RTX 3090 GPUs with 24576 MiB each.
- Command: `py -3.12 -m venv C:\IsaacSim\env_6_1_0`;
  `C:\IsaacSim\env_6_1_0\Scripts\python.exe -m pip install --upgrade pip`;
  `C:\IsaacSim\env_6_1_0\Scripts\python.exe -m pip install torch==2.11.0 --index-url https://download.pytorch.org/whl/cu130`;
  `C:\IsaacSim\env_6_1_0\Scripts\python.exe -m pip install "isaacsim[all,extscache]==6.1.0.0" --extra-index-url https://pypi.nvidia.com`;
  `$env:PYTHONPATH = (Resolve-Path 'software/src').Path; C:\IsaacSim\env_6_1_0\Scripts\python.exe -m rocell.integrations.isaac_sim.host_probe --output software/integrations/isaac_sim/evidence/windows_dual_rtx3090_candidate_20260929.json`;
  `git sparse-checkout add software/schemas; python -m pytest software/tests/unit/test_isaac_sim_host_probe.py software/tests/unit/test_isaac_sim_contracts.py -q`;
  `python scripts/ci/check_docs.py`; `python scripts/ci/check_evidence_scope.py`;
  `python scripts/ci/check_repository_artifacts.py`.
- Result: PASS for installation, non-launching evidence capture, and repository
  checks. Exact installed versions are Isaac Sim 6.1.0.0 and Torch
  2.11.0+cu130; Torch reports CUDA available with two RTX 3090 devices. The
  focused suite passed 14 tests in 0.53 seconds. Documentation, evidence-scope,
  and repository-artifact audits passed. The candidate correctly reports
  `CANDIDATE_BLOCKED` with four named blockers.
- Artifacts:
  `software/integrations/isaac_sim/evidence/windows_dual_rtx3090_candidate_20260929.json`;
  `software/src/rocell/integrations/isaac_sim/host_probe.py`;
  `software/tests/unit/test_isaac_sim_host_probe.py`;
  `software/integrations/isaac_sim/README.md`.
- Hardware writes: 0.
- Physical movements: 0.
- Limitations: Isaac Sim was not launched and no NVIDIA license/EULA was
  accepted by automation. The host driver 591.86 is below NVIDIA's documented
  tested Windows driver 595.97, and RTX 3090 is outside the documented 6.1.0
  minimum GPU set. No settings profile, live extension export, USD import,
  kinematic parity, simulation data, collision/contact evidence, controller
  access, or physical qualification exists. The repository lock remains
  `UNSELECTED`; this result changes no AI lane, arm lane, or integration gate.
- Supersedes: none. INT-424 remains visible failed setup evidence.
- Next dependency: obtain explicit acceptance for NVIDIA's applicable terms
  and a reviewed driver update, then run a first standalone/headless
  compatibility launch and retain the live version, extension, and settings
  identities before proposing a selected toolchain lock.

### E-20260929-INT-426 — NVIDIA outer installer failed before driver update

- Stage: S2/S3 simulation oracle WP0.
- Lane: INTEGRATION.
- Commit: `b071fa10a392ba1ea3c51135f3d7a48b464aa33e`.
- Change: downloaded the official NVIDIA 595.97 Windows package after owner
  authorization, verified its Windows signature, and attempted its outer
  self-extracting silent installer.
- Inputs/fixtures: official 957,358,592-byte installer SHA-256
  `979ed00fea181c786f608967377d6d83ac82e6368275994a4182ec79d97b3122`;
  valid Authenticode signer `NVIDIA Corporation`, certificate thumbprint
  `B66776FC8E70C58ED98199E8391264C827AAC534`.
- Command: `Start-Process -FilePath C:\IsaacSim\installers\595.97-desktop-win10-win11-64bit-international-dch-whql.exe -ArgumentList '-s','-noreboot' -Verb RunAs -PassThru -Wait`.
- Result: FAIL. The signed outer installer exited `-2147024891`
  (`0x80070005`, access denied), and both GPUs continued to report driver
  591.86. No retry result was substituted for this failed attempt.
- Artifacts: installer retained externally at the hash above; console result
  only. No installer binary or extracted driver payload is committed.
- Hardware writes: 0 robot/controller writes. The unsuccessful driver
  installer may have updated NVIDIA application support files but did not
  change the active display driver.
- Physical movements: 0.
- Limitations: operating-system driver installation evidence only. It tests no
  Isaac process, scene, robot model, physics, rendering, or physical system.
- Supersedes: none; INT-425 remains the prelaunch candidate boundary.
- Next dependency: extract the same verified package and run its signed inner
  display-driver installer with NVIDIA's documented silent switches.

### E-20260929-INT-427 — initial headless receipt extraction failed closed

- Stage: S2/S3 simulation oracle WP0.
- Lane: INTEGRATION.
- Commit: `b071fa10a392ba1ea3c51135f3d7a48b464aa33e`.
- Change: attempted to retain structured evidence from the newly installed
  Isaac environment after driver correction.
- Inputs/fixtures: Isaac Sim 6.1.0.0 installation digest
  `ccb196b9c987865ee86918301f00705b1dd5a42449c3119f2119aeb2adf51258`;
  NVIDIA driver 595.97; external smoke scripts and logs.
- Command: `$env:OMNI_KIT_ACCEPT_EULA='YES'; C:\IsaacSim\env_6_1_0\Scripts\python.exe C:\IsaacSim\smoke_6_1_0.py *> C:\IsaacSim\evidence\first_launch_6_1_0.log` and two corrected reruns of the same command.
- Result: FAIL in retained stages. The first command could not create its log
  because the evidence directory was absent. After creating the directory,
  Isaac started and shut down but the script called nonexistent
  `IApp.get_version`, initially without a durable error receipt and then with a
  retained `AttributeError` status. Isaac's shutdown forced process exit zero,
  demonstrating that exit code alone is insufficient evidence.
- Artifacts: external logs SHA-256
  `53bf754512d4bd640b576a8ecf1037221347a10c281141f640e4fda08f1789c3`
  and failed status JSON; neither is promoted as a passing receipt.
- Hardware writes: 0.
- Physical movements: 0.
- Limitations: the Isaac application did initialize, but these attempts do not
  provide a valid version/extension/settings receipt and cannot select the
  repository lock. No USD scene or robot asset was loaded.
- Supersedes: none; these failures remain visible alongside the later corrected
  probe.
- Next dependency: use Kit 6.1's `get_app_version` API, write an explicit PASS
  or ERROR sidecar before shutdown, and validate the resulting canonical
  receipt in hardware-free CI.

### E-20260929-INT-428 — driver-qualified Isaac headless launch verified

- Stage: S2/S3 simulation oracle WP0.
- Lane: INTEGRATION.
- Commit: `b071fa10a392ba1ea3c51135f3d7a48b464aa33e`.
- Change: extracted the verified 595.97 package, verified the inner NVIDIA
  `setup.exe` signature, installed the display driver directly, confirmed CUDA
  health, implemented a current-API headless launch probe with an explicit
  status sidecar, retained its canonical receipt, and added hardware-free
  receipt validation.
- Inputs/fixtures: first-launch receipt file SHA-256
  `bc41e5070109de62a1a78388e9b46ebd8a0882cecc567141ad43ea9ba90b20ee`;
  receipt content SHA-256
  `fa28e3a5878f77cc928a93861b35cdf9fac53b857840fbdacef9907aefc1d0ee`;
  probe source SHA-256
  `db9df17670a32d134f54030883288359803852031a6caab37efccf57ff103b0e`;
  test source SHA-256
  `e23fe207f0a03ef69b018af6158bb3f27d0763873134af69503a89ec880e9280`;
  installer and installation identities from INT-426 and INT-425.
- Command: `C:\IsaacSim\tools\7zr.exe x C:\IsaacSim\installers\595.97-desktop-win10-win11-64bit-international-dch-whql.exe -oC:\IsaacSim\installers\595.97-extracted -y`;
  `Start-Process -FilePath C:\IsaacSim\installers\595.97-extracted\setup.exe -WorkingDirectory C:\IsaacSim\installers\595.97-extracted -ArgumentList '-s','-n','Display.Driver' -Verb RunAs -PassThru -Wait`;
  `$env:OMNI_KIT_ACCEPT_EULA='YES'; C:\IsaacSim\env_6_1_0\Scripts\python.exe software\integrations\isaac_sim\first_launch_probe.py --output C:\IsaacSim\evidence\first_launch_receipt_6_1_0.json --status-output C:\IsaacSim\evidence\first_launch_receipt_6_1_0.status.json --installation-sha256 ccb196b9c987865ee86918301f00705b1dd5a42449c3119f2119aeb2adf51258 --installer-sha256 979ed00fea181c786f608967377d6d83ac82e6368275994a4182ec79d97b3122`;
  `python -m py_compile software/integrations/isaac_sim/first_launch_probe.py`;
  `python -m pytest software/tests/unit/test_isaac_sim_host_probe.py software/tests/unit/test_isaac_sim_first_launch_evidence.py software/tests/unit/test_isaac_sim_contracts.py -q`;
  `python scripts/ci/check_docs.py`; `python scripts/ci/check_evidence_scope.py`;
  `python scripts/ci/check_public_records.py`;
  `python scripts/ci/check_repository_artifacts.py`; `git diff --check`.
- Result: PASS for the bounded compatibility launch and repository checks.
  Both RTX 3090s report driver 595.97 and Torch 2.11.0+cu130 retained CUDA 13.0
  access. Isaac Sim 6.1.0.0 / Kit 6.1.0 started headlessly and shut down; the
  receipt binds 303 unique enabled extensions at digest
  `6e0d70db81fe16273341e65bd3cf0bc70dffe4a88a5cc0a7bacf51110dd27c70`
  and the launch settings at digest
  `0cbc21c4dbeeb7b2a0ce6c4c4875681834da8c12c83aa49cd36f09654b3ea473`.
  The focused suite passed 17 tests in 0.82 seconds and all four repository
  audits passed.
- Artifacts:
  `software/integrations/isaac_sim/evidence/windows_dual_rtx3090_first_launch_20260929.json`;
  `software/integrations/isaac_sim/first_launch_probe.py`;
  `software/tests/unit/test_isaac_sim_first_launch_evidence.py`;
  `software/integrations/isaac_sim/README.md`.
- Hardware writes: 0 robot/controller writes. One authorized operating-system
  display-driver update occurred and is outside the robot authority boundary.
- Physical movements: 0.
- Limitations: this is compatibility-startup evidence only. No USD scene,
  RoArm asset, physics step, rendered frame, collision/contact check, trajectory,
  robot transport, or physical qualification exists. RTX 3090 remains outside
  NVIDIA's documented 6.1.0 minimum GPU set. The log reports device 0 at PCIe
  x4 versus x16 maximum, no CUDA peer access, a stale localhost Omniverse proxy,
  and an OpenUSD asset-converter build warning. The toolchain lock remains
  `UNSELECTED`, and no AI, arm, or integration gate status changed.
- Supersedes: none. INT-426 and INT-427 remain visible failed evidence.
- Next dependency: isolate or resolve the OpenUSD asset-converter warning,
  define the governed RoArm import inputs, and begin WP1 joint/link/axis/unit
  mapping plus deterministic FK parity before reviewing a selected lock.

### E-20260929-INT-429 — initial Isaac URDF joint mapping assumption failed closed

- Stage: S2/S3 simulation oracle WP1.
- Lane: INTEGRATION.
- Commit: `8594c10b6a757e743388c7440aab2f31014ac463`.
- Change: ran the first governed import probe against the pinned meshless
  RoArm-M3 URDF and required every source joint to appear as a USD Physics
  joint.
- Inputs/fixtures: governed URDF SHA-256
  `a565718e7d74b07702802cf41eb9549a6e38e50b5e80aa9b887ab1ae3d0d8190`;
  Isaac Sim 6.1.0.0 installation digest
  `ccb196b9c987865ee86918301f00705b1dd5a42449c3119f2119aeb2adf51258`;
  NVIDIA driver 595.97.
- Command: `$env:OMNI_KIT_ACCEPT_EULA='YES'; C:\IsaacSim\env_6_1_0\Scripts\python.exe software\integrations\isaac_sim\urdf_import_probe.py --urdf software\models\roarm_m3\roarm_m3_kinematic_40dbd84.urdf --output-dir C:\IsaacSim\artifacts\issue190\wp1-import-001a --receipt C:\IsaacSim\evidence\urdf_import_001.json --status-output C:\IsaacSim\evidence\urdf_import_001.status.json`.
- Result: FAIL. Isaac emitted all nine source links and six movable joints but
  did not emit `world_to_base_link` or `link5_to_hand_tcp` as Physics joint
  prims. The explicit status was `RuntimeError: imported joint mismatch:
  missing=['link5_to_hand_tcp', 'world_to_base_link'], extra=[]`.
- Artifacts: failed status and 11,450-byte generated USD retained externally
  under `C:\IsaacSim\evidence` and
  `C:\IsaacSim\artifacts\issue190\wp1-import-001a`; neither is promoted as
  passing evidence.
- Hardware writes: 0.
- Physical movements: 0.
- Limitations: importer representation discovery only. No physics step, FK
  parity, collision/contact result, rendering, robot transport, or physical
  qualification was attempted.
- Supersedes: none; this failed assumption remains visible beside INT-430.
- Next dependency: classify the two fixed source joints from their imported
  nested transforms while continuing to require exact movable-joint and link
  sets.

### E-20260929-INT-430 — governed RoArm URDF import and mapping retained

- Stage: S2/S3 simulation oracle WP1.
- Lane: INTEGRATION.
- Commit: `8594c10b6a757e743388c7440aab2f31014ac463`.
- Change: implemented the bounded Isaac URDF import probe, retained a compact
  canonical mapping receipt, explicitly represented the two collapsed fixed
  joints, bound the external generated USD manifest, added hardware-free
  receipt tests, and documented reproduction and scope.
- Inputs/fixtures: governed URDF SHA-256
  `a565718e7d74b07702802cf41eb9549a6e38e50b5e80aa9b887ab1ae3d0d8190`;
  probe SHA-256
  `ff3b6575376b1d7e037d3b45dbdcc06e9c3da9e6d0b0c99c121812f669f27fff`;
  committed receipt file SHA-256
  `d537aa8aa0c4dc30eff62fd918b45c6afb103a8a81fd2180cdb7add757139ae1`;
  receipt content SHA-256
  `24f8a531ca3544ffcbc5514146a0988a1d9004533c031f6b7665fb1c2262c343`;
  test SHA-256
  `6007d4ec370bc1fcbde9423543ceaadf97b1a216126f9764b99e4d85a323b596`.
- Command: `$env:OMNI_KIT_ACCEPT_EULA='YES'; C:\IsaacSim\env_6_1_0\Scripts\python.exe software\integrations\isaac_sim\urdf_import_probe.py --urdf software\models\roarm_m3\roarm_m3_kinematic_40dbd84.urdf --output-dir C:\IsaacSim\artifacts\issue190\wp1-import-002 --receipt C:\IsaacSim\evidence\urdf_import_002.json --status-output C:\IsaacSim\evidence\urdf_import_002.status.json`;
  `python -m py_compile software/integrations/isaac_sim/urdf_import_probe.py software/tests/unit/test_isaac_sim_urdf_import_evidence.py`;
  `python -m pytest software/tests/unit/test_isaac_sim_urdf_import_evidence.py software/tests/unit/test_isaac_sim_first_launch_evidence.py software/tests/unit/test_isaac_sim_host_probe.py software/tests/unit/test_isaac_sim_contracts.py -q`;
  `python scripts/ci/check_docs.py`; `python scripts/ci/check_evidence_scope.py`;
  `python scripts/ci/check_public_records.py`;
  `python scripts/ci/check_repository_artifacts.py`; `git diff --check`.
- Result: PASS. The receipt binds nine unique links, six unique movable Physics
  joints, and both source fixed joints as collapsed nested transforms. The one
  external 11,450-byte USD has SHA-256
  `492ebbc606aa050251074736dbedd3fa5bb72ba6d8175269ba7c955f52e180b6`;
  its canonical manifest digest is
  `b84b6b6542c76dbffa4f43446db53d724a9c6e44333a43654eb351ca40e7d378`.
  The focused suite passed 22 tests in 1.06 seconds and all four repository
  audits passed.
- Artifacts:
  `software/integrations/isaac_sim/evidence/roarm_m3_urdf_import_20260929.json`;
  `software/integrations/isaac_sim/urdf_import_probe.py`;
  `software/tests/unit/test_isaac_sim_urdf_import_evidence.py`;
  `software/integrations/isaac_sim/README.md`.
- Hardware writes: 0.
- Physical movements: 0.
- Limitations: meshless kinematic-import evidence only. The source retains zero
  effort and velocity placeholders and lacks inertial, visual, and collision
  geometry. No dynamics, FK parity, trajectory, clearance, contact, render,
  hardware, or physical qualification claim is made. RTX 3090 remains outside
  NVIDIA's documented Isaac 6.1.0 minimum GPU set, and the toolchain lock
  remains `UNSELECTED`.
- Supersedes: none. INT-429 remains retained failed evidence.
- Next dependency: set actual Isaac articulation states for the fixed zero,
  home, and ready corpus and compare the imported `hand_tcp` world pose against
  governed FK values before reviewing runner selection.

### E-20260929-INT-431 — unnormalized Isaac articulation omitted base rotation DOF

- Stage: S2/S3 simulation oracle WP1.
- Lane: INTEGRATION.
- Commit: `21cd36177f37e788bca8951d664a804398826155`.
- Change: opened the retained unnormalized USD in a live Isaac physics
  articulation, enumerated its DOFs, teleported the exposed joints through the
  fixed corpus, and retained the topology blocker separately from its otherwise
  passing base-zero pose measurements.
- Inputs/fixtures: unnormalized import receipt content SHA-256
  `24f8a531ca3544ffcbc5514146a0988a1d9004533c031f6b7665fb1c2262c343`;
  preserved unnormalized receipt file SHA-256
  `5113c2ba391cfd8720358ce0386dcdb34c01a8afcb0bd27296eb322a395fccca`;
  unnormalized external USD SHA-256
  `492ebbc606aa050251074736dbedd3fa5bb72ba6d8175269ba7c955f52e180b6`;
  governed URDF SHA-256
  `a565718e7d74b07702802cf41eb9549a6e38e50b5e80aa9b887ab1ae3d0d8190`.
- Command: `$env:OMNI_KIT_ACCEPT_EULA='YES'; C:\IsaacSim\env_6_1_0\Scripts\python.exe software\integrations\isaac_sim\fk_parity_probe.py --usd C:\IsaacSim\artifacts\issue190\wp1-import-002\roarm_m3_kinematic_40dbd84\roarm_m3_kinematic_40dbd84.usda --import-receipt software\integrations\isaac_sim\evidence\roarm_m3_urdf_import_20260929.json --output C:\IsaacSim\evidence\fk_parity_001.json --status-output C:\IsaacSim\evidence\fk_parity_001.status.json`.
- Result: BLOCKED. The three base-zero corpus poses passed the provisional
  0.1 mm / 0.05 degree thresholds, but the live articulation exposed only five
  DOFs and omitted `base_link_to_link1`. The status receipt recorded
  `parity_pass=true`, `status=BLOCKED`, content SHA-256
  `0e5f00a8ea1ec378f35823026efa41a467503e65652604d63eaffe5dfece2017`.
- Artifacts:
  `software/integrations/isaac_sim/evidence/roarm_m3_urdf_import_unnormalized_20260929.json`;
  blocked parity receipt and logs retained externally in `C:\IsaacSim\evidence`.
- Hardware writes: 0.
- Physical movements: 0.
- Limitations: base-zero kinematic diagnostic only. It could not test nonzero
  base rotation, performed no dynamics step, and provides no collision,
  contact, render, hardware, or physical qualification.
- Supersedes: none. INT-429 and INT-430 remain visible import evidence.
- Next dependency: deterministically promote the collapsed `base_link` to the
  articulation root and rerun the identical corpus with all six DOFs visible.

### E-20260929-INT-432 — complete six-DOF Isaac FK corpus passes

- Stage: S2/S3 simulation oracle WP1.
- Lane: INTEGRATION.
- Commit: `21cd36177f37e788bca8951d664a804398826155`.
- Change: normalized the generated USD articulation root to `base_link`,
  preserved all six source movable joints in live Isaac order, implemented the
  live articulation FK probe, retained canonical import and parity receipts,
  added hardware-free evidence tests, and documented the bounded result.
- Inputs/fixtures: normalized import receipt file SHA-256
  `f3211aaa496e375f2c5922b50082d84fc64926a8a78e83ca857bfe4d899ddcde`;
  import receipt content SHA-256
  `ab9bdc8de92f71d23f465ab54233d9819a3a177edb42e347032f35b417f0fc85`;
  parity receipt file SHA-256
  `73568d4d8387426345d8df47eb23509866d307e39c55061a18a847e4698bba0e`;
  parity receipt content SHA-256
  `baa6fd635e3004f75426234cc3ff72da240dae8c0b69074e7882dfbdbea2287e`;
  normalized external USD SHA-256
  `a0ec437fb4d647f354007dc352a3af8b13576eaf4931d69d60a510bf235ebea2`;
  import probe SHA-256
  `c12cddef1b972b96bc53303aaa92341f6f54c3b78d0dac0cc08f9f5bc4923d55`;
  FK probe SHA-256
  `0426a628b51420998486fb5c58f97cd393f915a3edbe791dd81518bbc3e7fcbf`.
- Command: `$env:OMNI_KIT_ACCEPT_EULA='YES'; C:\IsaacSim\env_6_1_0\Scripts\python.exe software\integrations\isaac_sim\urdf_import_probe.py --urdf software\models\roarm_m3\roarm_m3_kinematic_40dbd84.urdf --output-dir C:\IsaacSim\artifacts\issue190\wp1-import-003 --receipt C:\IsaacSim\evidence\urdf_import_003.json --status-output C:\IsaacSim\evidence\urdf_import_003.status.json`;
  `$env:OMNI_KIT_ACCEPT_EULA='YES'; C:\IsaacSim\env_6_1_0\Scripts\python.exe software\integrations\isaac_sim\fk_parity_probe.py --usd C:\IsaacSim\artifacts\issue190\wp1-import-003\roarm_m3_kinematic_40dbd84\roarm_m3_kinematic_40dbd84.usda --import-receipt C:\IsaacSim\evidence\urdf_import_003.json --output C:\IsaacSim\evidence\fk_parity_002.json --status-output C:\IsaacSim\evidence\fk_parity_002.status.json`;
  `python -m pytest software/tests/unit/test_isaac_sim_urdf_import_evidence.py software/tests/unit/test_isaac_sim_fk_parity_evidence.py software/tests/unit/test_isaac_sim_first_launch_evidence.py software/tests/unit/test_isaac_sim_host_probe.py software/tests/unit/test_isaac_sim_contracts.py -q`;
  `python scripts/ci/check_docs.py`; `python scripts/ci/check_evidence_scope.py`;
  `python scripts/ci/check_public_records.py`;
  `python scripts/ci/check_repository_artifacts.py`; `git diff --check`.
- Result: PASS for the bounded kinematic parity corpus. The live articulation
  exposes the exact six-DOF source order. Zero, home, and ready all pass at
  thresholds 0.1 mm translation and 0.05 degrees rotation; worst translation
  error is 0.00012833903159220256 mm and reported rotation error is 0 degrees.
  The focused suite passed 27 tests in 1.29 seconds and all four repository
  audits passed.
- Artifacts:
  `software/integrations/isaac_sim/evidence/roarm_m3_urdf_import_20260929.json`;
  `software/integrations/isaac_sim/evidence/roarm_m3_fk_parity_20260929.json`;
  `software/integrations/isaac_sim/urdf_import_probe.py`;
  `software/integrations/isaac_sim/fk_parity_probe.py`;
  `software/tests/unit/test_isaac_sim_urdf_import_evidence.py`;
  `software/tests/unit/test_isaac_sim_fk_parity_evidence.py`.
- Hardware writes: 0.
- Physical movements: 0.
- Limitations: parity uses instantaneous articulation teleport and the imported
  fixed `hand_tcp` transform without a dynamics step. The meshless source has
  invalid mass and inertia placeholders and no visual or collision geometry.
  This result makes no dynamics, trajectory, clearance, contact, rendering,
  controller, hardware, or physical qualification claim. RTX 3090 remains
  outside NVIDIA's documented Isaac 6.1.0 minimum GPU set, and the repository
  toolchain lock remains `UNSELECTED`. No AI, arm, or integration gate status
  changed.
- Supersedes: INT-431's missing-base-DOF topology for the normalized artifact
  only; INT-431 remains retained failed evidence.
- Next dependency: define and import governed reduced collision geometry and
  valid inertial properties before any dynamics, clearance, or contact oracle
  work; runner lock selection remains a separate review decision.

### E-20260929-INT-433 — nominal RC03 rigid scene retained with collision blockers

- Stage: S2/S3 simulation oracle WP2.
- Lane: INTEGRATION.
- Commit: `0ffb24b5860cea90ad3338429a4adf19134f0727`.
- Change: projected the strict RC03 nominal scene into a metre-based external
  Isaac USD, referenced the normalized six-DOF robot at the frozen nominal
  board transform, retained six static rigid obstacle envelopes, six nominal
  fiducials and the nominal `H` target marker, and added a compact canonical
  receipt plus hardware-free validation. Collision queries and hover replay
  are explicitly inadmissible.
- Inputs/fixtures: scene-probe SHA-256
  `69fb0caa5045e8fb3938f2ad71859f0da35963ddd85dfe847a593a5dd4a4f945`;
  test SHA-256
  `af86a721b2b3a584a1d0894f5c3b67e5f7082353f197d040235d6b4674752a0f`;
  committed receipt file SHA-256
  `df50ff6a0df0ab1b3561783d0140925d9302cd5b1a16e59207cd6f8e13a2d98b`;
  receipt content SHA-256
  `0d080880e6c7915cae43d04771c9a17748060c4d682a1de86003d54021067bcd`;
  target-profile SHA-256
  `6779213e832ab27eeda1e7fb245f57ff8cb0d56707b5aa73a8f31ec483a620f2`;
  simulation-hardware-profile SHA-256
  `6c24745f8330d0aa77c423d9376adb7bb6c1a090426ed1a38814eb32f6dcd190`;
  RC03 layout SHA-256
  `e84db9aa7b88db442f042c6f546196e350c822a2e7609cb4b652b3da535df2e1`;
  AprilTag-map SHA-256
  `81c867d28660cdade79cb8024104d82e5568effa0736f07f0947c1007ac23700`;
  normalized robot-import receipt file SHA-256
  `f3211aaa496e375f2c5922b50082d84fc64926a8a78e83ca857bfe4d899ddcde`.
- Command: `$env:OMNI_KIT_ACCEPT_EULA='YES'; C:\IsaacSim\env_6_1_0\Scripts\python.exe software\integrations\isaac_sim\rc03_scene_probe.py --workspace . --rc03-root active-project\RoCell_v0_3 --robot-usd C:\IsaacSim\artifacts\issue190\wp1-import-003\roarm_m3_kinematic_40dbd84\roarm_m3_kinematic_40dbd84.usda --robot-import-receipt software\integrations\isaac_sim\evidence\roarm_m3_urdf_import_20260929.json --output-dir C:\IsaacSim\artifacts\issue190\wp2-scene-002 --receipt C:\IsaacSim\evidence\rc03_scene_002.json --status-output C:\IsaacSim\evidence\rc03_scene_002.status.json`;
  `python -m py_compile software/integrations/isaac_sim/rc03_scene_probe.py software/tests/unit/test_isaac_sim_rc03_scene_evidence.py`;
  `python -m pytest software/tests/unit/test_isaac_sim_fk_evidence.py software/tests/unit/test_isaac_sim_import_evidence.py software/tests/unit/test_isaac_sim_host_evidence.py -q`;
  `python -m pytest software/tests/unit/test_isaac_sim_rc03_scene_evidence.py software/tests/unit/test_isaac_sim_urdf_import_evidence.py software/tests/unit/test_isaac_sim_fk_parity_evidence.py software/tests/unit/test_isaac_sim_first_launch_evidence.py software/tests/unit/test_isaac_sim_host_probe.py software/tests/unit/test_isaac_sim_contracts.py -q`;
  `python scripts/ci/check_docs.py`; `python scripts/ci/check_evidence_scope.py`;
  `python scripts/ci/check_public_records.py`;
  `python scripts/ci/check_repository_artifacts.py`; `git diff --check`.
- Result: PASS_WITH_BLOCKERS for bounded rigid scene composition. The external
  6,847-byte stage SHA-256 is
  `77600a60975daaa4d58a20f597851a5d397ed9c452d44ab47ea1832bf42e0f35`,
  with canonical external-manifest digest
  `fcd219cab737e48ccffd464360705a9de931ab46a23640f4336bc4223b662664`.
  Reopening the stage found exactly six collision prims and all six composed
  robot joints. The corrected focused suite passed 32 tests in 1.49 seconds,
  and all four repository audits passed. The earlier focused-test command
  failed before collection because it named three nonexistent test files;
  that failed attempt is retained here and was corrected without rewriting it.
- Artifacts:
  `software/integrations/isaac_sim/evidence/rc03_nominal_rigid_scene_20260929.json`;
  `software/integrations/isaac_sim/rc03_scene_probe.py`;
  `software/tests/unit/test_isaac_sim_rc03_scene_evidence.py`;
  external USD and status evidence under
  `C:\IsaacSim\artifacts\issue190\wp2-scene-002` and
  `C:\IsaacSim\evidence`.
- Hardware writes: 0.
- Physical movements: 0.
- Limitations: the board, keyboard, phone and three station bodies are static
  nominal envelopes. The station heights are 35 mm conservative proxies. Arm
  links, the tool and camera support have no collision geometry; source
  inertial properties are invalid; robot placement is nominal and unmeasured;
  and the Isaac toolchain lock remains `UNSELECTED`. This evidence provides no
  dynamics, trajectory, clearance, contact, rendering, controller, hardware or
  physical qualification, and changes no AI, arm or integration gate status.
- Supersedes: none. INT-431 and INT-432 remain the governing topology and FK
  evidence.
- Next dependency: define reviewed reduced collision geometry for the arm,
  tool and camera support, replace fixture proxies with governed solid heights,
  and obtain measured robot placement before any clearance or hover oracle is
  admissible.

### E-20260929-INT-434 — STEP probe import-order attempt failed closed

- Stage: S2/S3 simulation oracle WP2.
- Lane: INTEGRATION.
- Commit: `204fe02906d1e914bed0a20a753a2fb6e61dbfe0`.
- Change: attempted the first repository-owned inspection of the pinned
  official RoArm STEP assembly with the installed Isaac HOOPS converter.
- Inputs/fixtures: official archive SHA-256
  `1e2111145276aac14e521f47990fc41de87e2e735623d115a39cc176c9762da2`;
  extracted STEP SHA-256
  `728eb52f0bdd32dc0b907c9bb983d3d0b8adf7a5ea945949785a6e496f5089ff`;
  failed status-file SHA-256
  `96ad33a2d241d21cb26e6adbb44fb62f31b9f78dc0dd00e492fae346511c6f36`.
- Command: `$env:OMNI_KIT_ACCEPT_EULA='YES'; C:\IsaacSim\env_6_1_0\Scripts\python.exe software\integrations\isaac_sim\step_inspection_probe.py --archive C:\IsaacSim\sources\roarm-m3-step-260310\RoArm-M3_STEP_260310.zip --step C:\IsaacSim\sources\roarm-m3-step-260310\extracted\RoArm-M3_STEP\RoArm-M3.step --output-dir C:\IsaacSim\artifacts\issue190\wp2-cad-002 --receipt C:\IsaacSim\evidence\step_inspection_002.json --status-output C:\IsaacSim\evidence\step_inspection_002.status.json`.
- Result: FAIL. The probe imported `omni.converter.hoops` before enabling
  `omni.kit.converter.hoops_core`; the explicit status recorded
  `ModuleNotFoundError: No module named 'omni.converter'`. Isaac shutdown again
  forced process exit zero, so the status sidecar rather than the process code
  preserved the failure.
- Artifacts: failed status and log retained externally under
  `C:\IsaacSim\evidence`; the empty output directory contains no promoted USD.
- Hardware writes: 0.
- Physical movements: 0.
- Limitations: initialization-order evidence only. No CAD conversion, geometry
  inventory, collision shape, physics step, trajectory, hardware, or physical
  qualification resulted.
- Supersedes: none; this failure remains visible beside INT-435.
- Next dependency: enable the HOOPS core extension, advance Kit startup, then
  import the backend and rerun the same pinned inputs with explicit status
  validation.

### E-20260929-INT-435 — pinned official STEP inspection retained

- Stage: S2/S3 simulation oracle WP2.
- Lane: INTEGRATION.
- Commit: `204fe02906d1e914bed0a20a753a2fb6e61dbfe0`.
- Change: downloaded and hash-verified the pinned official Waveshare archive,
  verified its sole STEP member byte for byte, converted it twice with the
  installed HOOPS backend, inventoried the resulting USD, retained four named
  upstream structural components as unassigned collision seeds, and added a
  compact canonical receipt plus hardware-free tests. No generated vendor CAD
  asset is committed.
- Inputs/fixtures: probe SHA-256
  `417d37f34e9bd05f985e7fedf5d0571920b88e108e7e516fcde28fd3ce1b2e66`;
  test SHA-256
  `65822a8d2784eeae22afb6fc5d9f1d9ab758c028393d740bb646cd5b4618f528`;
  committed receipt file SHA-256
  `255a3612d1c932646f3ba4c09357f5337b679d46a1aeb210ffe9976a5c93ddbb`;
  receipt content SHA-256
  `b51c20e34c3b3edfa4ba40b88d04299aa346803b43b12909dade7c41c44cf967`;
  archive SHA-256
  `1e2111145276aac14e521f47990fc41de87e2e735623d115a39cc176c9762da2`;
  extracted STEP SHA-256
  `728eb52f0bdd32dc0b907c9bb983d3d0b8adf7a5ea945949785a6e496f5089ff`.
- Command: `Invoke-WebRequest -Uri https://files.waveshare.com/wiki/RoArm-M3/RoArm-M3_STEP_260310.zip -OutFile C:\IsaacSim\sources\roarm-m3-step-260310\RoArm-M3_STEP_260310.zip`;
  `$env:OMNI_KIT_ACCEPT_EULA='YES'; C:\IsaacSim\env_6_1_0\Scripts\python.exe software\integrations\isaac_sim\step_inspection_probe.py --archive C:\IsaacSim\sources\roarm-m3-step-260310\RoArm-M3_STEP_260310.zip --step C:\IsaacSim\sources\roarm-m3-step-260310\extracted\RoArm-M3_STEP\RoArm-M3.step --output-dir C:\IsaacSim\artifacts\issue190\wp2-cad-003 --receipt C:\IsaacSim\evidence\step_inspection_003.json --status-output C:\IsaacSim\evidence\step_inspection_003.status.json`;
  `$env:OMNI_KIT_ACCEPT_EULA='YES'; C:\IsaacSim\env_6_1_0\Scripts\python.exe software\integrations\isaac_sim\step_inspection_probe.py --archive C:\IsaacSim\sources\roarm-m3-step-260310\RoArm-M3_STEP_260310.zip --step C:\IsaacSim\sources\roarm-m3-step-260310\extracted\RoArm-M3_STEP\RoArm-M3.step --output-dir C:\IsaacSim\artifacts\issue190\wp2-cad-004 --receipt C:\IsaacSim\evidence\step_inspection_004.json --status-output C:\IsaacSim\evidence\step_inspection_004.status.json`;
  `python -m py_compile software/integrations/isaac_sim/step_inspection_probe.py software/tests/unit/test_isaac_sim_step_inspection_evidence.py`;
  `python -m pytest software/tests/unit/test_isaac_sim_step_inspection_evidence.py software/tests/unit/test_isaac_sim_rc03_scene_evidence.py software/tests/unit/test_isaac_sim_urdf_import_evidence.py software/tests/unit/test_isaac_sim_fk_parity_evidence.py software/tests/unit/test_isaac_sim_first_launch_evidence.py software/tests/unit/test_isaac_sim_host_probe.py software/tests/unit/test_isaac_sim_contracts.py -q`;
  `python scripts/ci/check_docs.py`; `python scripts/ci/check_evidence_scope.py`;
  `python scripts/ci/check_public_records.py`;
  `python scripts/ci/check_repository_artifacts.py`; `git diff --check`.
- Result: PASS_WITH_BLOCKERS for pinned CAD inspection. Isaac identified the
  source as millimetre/Z-up and produced 2,893 prims and 770 meshes over an
  assembly bound from `[-48.994985,-42.71,0]` to
  `[356.851785,42.51,389.380716]` mm. Separate corrected conversions produced
  the identical 26,872,057-byte USD SHA-256
  `cfcd4e6170350d948de1976164665ddde99cfad457b72730f7ffcbdd119496d3`;
  its canonical external manifest digest is
  `9e7fbf1d2a81cdc039603613aabdf91b63a301c46e0230da78b733e7934485b9`.
  The two passing status-file SHA-256 values are
  `2a145f2793d66d0d3a2c27ccea412f5c7f31ef39b382ddb1015252c5328c5ef4`
  and `a4ed5791b6f7950871dfc42cc97b53e24a118000f7f97d14f9e46d21cb31e1ad`.
  The focused suite passed 38 tests in 1.71 seconds and all four repository
  audits passed.
- Artifacts:
  `software/integrations/isaac_sim/evidence/roarm_m3_step_inspection_20260929.json`;
  `software/integrations/isaac_sim/step_inspection_probe.py`;
  `software/tests/unit/test_isaac_sim_step_inspection_evidence.py`;
  generated CAD USD, status, and logs retained externally under
  `C:\IsaacSim\artifacts\issue190\wp2-cad-004` and
  `C:\IsaacSim\evidence`.
- Hardware writes: 0.
- Physical movements: 0.
- Limitations: the STEP assembly pose is not bound to a governed URDF joint
  state. `AL-BASE`, `AL-SHOULDER`, `AL-ELBOW-A`, and `AL-ELBOW-B` retain null
  dynamic-link assignments and are incomplete inspection seeds. No reduced
  shapes, arm collision geometry, valid inertia, tool, camera support, measured
  placement, clearance, trajectory, contact, rendering, controller, hardware,
  or physical qualification exists. Upstream redistribution scope remains
  unconfirmed, and the toolchain lock remains `UNSELECTED`. No AI, arm, or
  integration gate status changed.
- Supersedes: none. INT-434 remains retained failed evidence; INT-433 remains
  the governing nominal rigid-scene composition evidence.
- Next dependency: derive and review the assembly-pose-to-URDF-state binding,
  assign complete CAD groups to dynamic links, and generate conservative
  reduced link-local shapes before collision differential or hover replay can
  become admissible.

### E-20260929-INT-436 — official CAD assembly pose classified against governed states

- Stage: S2/S3 simulation oracle WP2.
- Lane: INTEGRATION.
- Commit: `9775ab3b875eede9a941a55a10af573ffc507e42`.
- Change: derived a CAD-to-URDF world translation from the pinned assembly's
  paired shoulder-servo envelopes and assembly floor, compared six governed
  URDF link origins in fixed zero, home, and ready states against six named CAD
  product envelopes, selected the strongly separated home-pose hypothesis, and
  retained dynamic-link assignment, collision geometry, and clearance replay
  as explicitly inadmissible.
- Inputs/fixtures: probe SHA-256
  `930b9d8d5ecfba3c8decc1af4f0f496ba841341bf1492ef704b9984a108a4abf`;
  test SHA-256
  `64c30e83ebbdca02c2945ff94a906d96449ef0807e77e2ab54253a9cac9858c6`;
  committed receipt file SHA-256
  `e4271e62147c8e421e4d303365563514da24fbe33b1ae46328dddffad3827f50`;
  receipt content SHA-256
  `3817f28d9171ee3cb33d024f3f31e57495b02fb383ba60277953f6148ba00f3`;
  external receipt file SHA-256
  `c62be383dba83a440635ae2c2283cd09beb56ab18de0257c2ff275106c214acc`
  (same canonical JSON content; Windows external output uses CRLF);
  external status-file SHA-256
  `4e8962bc08c3e74583ec91d4cf483a812a45485737638e2f15b5425d54732424`;
  CAD USD SHA-256
  `cfcd4e6170350d948de1976164665ddde99cfad457b72730f7ffcbdd119496d3`;
  STEP inspection receipt content SHA-256
  `b51c20e34c3b3edfa4ba40b88d04299aa346803b43b12909dade7c41c44cf967`;
  governed URDF SHA-256
  `a565718e7d74b07702802cf41eb9549a6e38e50b5e80aa9b887ab1ae3d0d8190`.
- Command: `C:\IsaacSim\env_6_1_0\Scripts\python.exe software\integrations\isaac_sim\step_pose_binding_probe.py --workspace . --cad-usd C:\IsaacSim\artifacts\issue190\wp2-cad-004\roarm_m3_official.usda --step-receipt software\integrations\isaac_sim\evidence\roarm_m3_step_inspection_20260929.json --output C:\IsaacSim\evidence\step_pose_binding_001.json --status-output C:\IsaacSim\evidence\step_pose_binding_001.status.json`;
  `python -m py_compile software/integrations/isaac_sim/step_pose_binding_probe.py software/tests/unit/test_isaac_sim_step_pose_binding_evidence.py`;
  `python -m pytest software/tests/unit/test_isaac_sim_step_pose_binding_evidence.py software/tests/unit/test_isaac_sim_step_inspection_evidence.py software/tests/unit/test_isaac_sim_rc03_scene_evidence.py software/tests/unit/test_isaac_sim_urdf_import_evidence.py software/tests/unit/test_isaac_sim_fk_parity_evidence.py software/tests/unit/test_isaac_sim_first_launch_evidence.py software/tests/unit/test_isaac_sim_host_probe.py software/tests/unit/test_isaac_sim_contracts.py -q`;
  `python scripts/ci/check_docs.py`; `python scripts/ci/check_evidence_scope.py`;
  `python scripts/ci/check_public_records.py`;
  `python scripts/ci/check_repository_artifacts.py`; `git diff --check`.
- Result: PASS_WITH_BLOCKERS for the bounded pose hypothesis. The derived
  `CAD_T_URDF_WORLD` has identity rotation and translation
  `[7.005001, 0, 0]` mm. Home supported all six witnesses with maximum residual
  2.215515 mm and RMS residual 0.904480 mm. Ready was the runner-up at
  133.237718 mm maximum residual, producing a 131.022203 mm classification
  margin; zero reached 305.130844 mm. The focused suite passed 43 tests in
  1.93 seconds and all four repository audits passed.
- Artifacts:
  `software/integrations/isaac_sim/evidence/roarm_m3_step_pose_binding_20260929.json`;
  `software/integrations/isaac_sim/step_pose_binding_probe.py`;
  `software/tests/unit/test_isaac_sim_step_pose_binding_evidence.py`;
  external generated receipt and status under `C:\IsaacSim\evidence`.
- Hardware writes: 0.
- Physical movements: 0.
- Limitations: AABB witnesses classify the fixed assembly pose but do not prove
  exact joint-axis correspondence or define complete CAD-product membership per
  dynamic link. No reduced collision shapes, self-collision validation, valid
  inertia, tool geometry, camera-support geometry, measured robot placement,
  dynamics, trajectory, clearance, contact, rendering, controller, hardware,
  or physical qualification resulted. The Isaac toolchain lock remains
  `UNSELECTED`. No AI, arm, or integration gate status changed.
- Supersedes: the assembly-pose uncertainty stated by INT-435 only; INT-435 and
  all earlier failed evidence remain retained.
- Next dependency: review complete CAD-product membership for each dynamic link
  and generate conservative reduced link-local shapes before any collision
  differential or hover replay can become admissible.

### E-20260929-INT-437 — fixed-pose CAD link-membership candidates retained

- Stage: S2/S3 simulation oracle WP2.
- Lane: INTEGRATION.
- Commit: `5ac4ae5079814d21ccc4572848459a64f936c62d`.
- Change: partitioned every mesh in the pinned converted STEP assembly by its
  direct component instance, ranked two governed-link candidates for each
  component from its AABB centroid distance to the classified home-pose link
  skeleton, identified component groups crossing governed joint origins, and
  retained every reviewed dynamic-link assignment as null.
- Inputs/fixtures: probe SHA-256
  `cb6245e1894d80e083a5e1358895c8aae4c8c40829e0d54414cf46f0b2f74057`;
  test SHA-256
  `0768f5d461b3922fa5ac6a90aa763e7d60f2e694a2ddc1b9ab64a111b1c155f8`;
  committed receipt file SHA-256
  `711437e98d148e16bfaa03cd2f69ee459efa276c15a95775535946991e2a9386`;
  receipt content SHA-256
  `c1ecd6b636368e38ae815aca436699d9fa44ca7e70e1456048794d0f5769fd78`;
  external receipt file SHA-256
  `e5c303d5b0f609d9f1cc63abb63d89d20d5fe88f80e9a65c0bdcc29ed7498f42`
  (same canonical JSON content; Windows external output uses CRLF);
  external status-file SHA-256
  `d8f1c151775095228c162c7eaa11c95c65d046b6cc4d3b2b03f1da7e6222dd04`;
  CAD USD SHA-256
  `cfcd4e6170350d948de1976164665ddde99cfad457b72730f7ffcbdd119496d3`;
  pose receipt content SHA-256
  `3817f28d9171ee3cb33d024f3f31e57495b02fb383ba60277953f6148ba00f3f`;
  governed URDF SHA-256
  `a565718e7d74b07702802cf41eb9549a6e38e50b5e80aa9b887ab1ae3d0d8190`.
- Command: `$env:PYTHONUTF8='1'; C:\IsaacSim\env_6_1_0\Scripts\python.exe software\integrations\isaac_sim\step_link_membership_probe.py --workspace . --cad-usd C:\IsaacSim\artifacts\issue190\wp2-cad-004\roarm_m3_official.usda --pose-receipt software\integrations\isaac_sim\evidence\roarm_m3_step_pose_binding_20260929.json --output C:\IsaacSim\evidence\step_link_membership_001.json --status-output C:\IsaacSim\evidence\step_link_membership_001.status.json`;
  `python -m py_compile software/integrations/isaac_sim/step_link_membership_probe.py software/tests/unit/test_isaac_sim_step_link_membership_evidence.py`;
  `python -m pytest software/tests/unit/test_isaac_sim_step_link_membership_evidence.py software/tests/unit/test_isaac_sim_step_pose_binding_evidence.py software/tests/unit/test_isaac_sim_step_inspection_evidence.py software/tests/unit/test_isaac_sim_rc03_scene_evidence.py software/tests/unit/test_isaac_sim_urdf_import_evidence.py software/tests/unit/test_isaac_sim_fk_parity_evidence.py software/tests/unit/test_isaac_sim_first_launch_evidence.py software/tests/unit/test_isaac_sim_host_probe.py software/tests/unit/test_isaac_sim_contracts.py -q`;
  `python scripts/ci/check_docs.py`; `python scripts/ci/check_evidence_scope.py`;
  `python scripts/ci/check_public_records.py`;
  `python scripts/ci/check_repository_artifacts.py`; `git diff --check`.
- Result: PASS_WITH_BLOCKERS for the complete candidate inventory. The 162
  direct component instances partition all 770 stage meshes. Forty-eight
  instances have a nearest-link margin above 10 mm; 114 remain ambiguous and
  19 component envelopes cross at least one governed joint origin. The nearest
  candidate distribution is base_link 33, link1 35, link2 27, link3 26, link4
  11, link5 23, and gripper_link 7. Reviewed assignment count remains zero.
  The focused suite passed 48 tests in 2.17 seconds and all four repository
  audits passed.
- Artifacts:
  `software/integrations/isaac_sim/evidence/roarm_m3_step_link_membership_candidates_20260929.json`;
  `software/integrations/isaac_sim/step_link_membership_probe.py`;
  `software/tests/unit/test_isaac_sim_step_link_membership_evidence.py`;
  external generated receipt and status under `C:\IsaacSim\evidence`.
- Hardware writes: 0.
- Physical movements: 0.
- Limitations: nearest support-segment ranking is a review aid, not proof of
  rigid membership. The fixed-pose STEP contains no reviewed joint or mate
  graph; one pose cannot separate components that move together in that pose;
  and direct component subtrees can contain parts on both sides of a joint.
  No link-local collision shapes, inertia, dynamics, trajectory, clearance,
  contact, rendering, controller, hardware, or physical qualification
  resulted. The tool, camera support, measured placement, and Isaac toolchain
  lock remain unresolved. No AI, arm, or integration gate status changed.
- Supersedes: none. INT-436 remains the governing pose-classification evidence;
  this row quantifies its unresolved membership dependency.
- Next dependency: obtain a reviewed STEP joint/mate graph or at least one
  independently identified articulated CAD state, then establish leaf-level
  rigid motion groups before reducing any component to collision geometry.

### E-20260929-INT-438 — official per-link mesh grouping bound to STEP envelope

- Stage: S2/S3 simulation oracle WP2.
- Lane: INTEGRATION.
- Commit: `0b222ebdca6c29364f12cdb138ce436a3774d328`.
- Change: read the official RoArm-M3 Xacro and STL assets as immutable Git blobs
  at the already governed upstream commit, verified identical visual/collision
  bindings for seven governed links, transformed the link meshes through the
  governed home pose and CAD frame, compared their union envelope with the
  independently converted official STEP assembly, and retained raw and reduced
  collision admission as false.
- Inputs/fixtures: probe SHA-256
  `12427f4ec0d49257e4aac0601c4100ff9ee43fe170bf2018afbf9e23ab404199`;
  test SHA-256
  `cd589b2f071e97c31e65c97499f163fcdce650c6e541e68528dbd9e50808555d`;
  committed receipt file SHA-256
  `ab8749f813a20cc93e804eddfaccca8d1997a9d6ef86eb6cebf7368e6e368640`;
  receipt content SHA-256
  `77b7c16e2d7c7a8ee0579b071d6a911516a8ba6d675188971e0c54e466b30954`;
  external receipt file SHA-256
  `976d176d20ccb6e4fac287106aa5eb755bac07b8e579db0b260b102b590401a3`
  (same canonical JSON content; Windows external output uses CRLF);
  external status-file SHA-256
  `b083e36e7d52e713588e57f7f0352251c0aafd71179a2ebde87d2dfdbcc35066`;
  upstream commit `40dbd84b553695212fab713e8465f817ba95454d`, tree
  `3a1d24388e15b318ba0c5305a94b5140b5b239bd`, and Xacro SHA-256
  `b6333849d0e377008eee0a87a5b8cdcf44f7a73edf3d7600e95506a023a234b6`;
  STEP receipt content SHA-256
  `b51c20e34c3b3edfa4ba40b88d04299aa346803b43b12909dade7c41c44cf967`;
  pose receipt content SHA-256
  `3817f28d9171ee3cb33d024f3f31e57495b02fb383ba60277953f6148ba00f3f`;
  governed URDF SHA-256
  `a565718e7d74b07702802cf41eb9549a6e38e50b5e80aa9b887ab1ae3d0d8190`.
- Command: `git clone --filter=blob:none --no-checkout https://github.com/waveshareteam/roarm_ws.git C:\IsaacSim\sources\roarm_ws-40dbd84`;
  `git -C C:\IsaacSim\sources\roarm_ws-40dbd84 fetch origin 40dbd84b553695212fab713e8465f817ba95454d`;
  `git -C C:\IsaacSim\sources\roarm_ws-40dbd84 checkout --detach 40dbd84b553695212fab713e8465f817ba95454d`;
  `$env:PYTHONUTF8='1'; C:\IsaacSim\env_6_1_0\Scripts\python.exe software\integrations\isaac_sim\upstream_link_mesh_probe.py --workspace . --upstream-repo C:\IsaacSim\sources\roarm_ws-40dbd84 --step-receipt software\integrations\isaac_sim\evidence\roarm_m3_step_inspection_20260929.json --pose-receipt software\integrations\isaac_sim\evidence\roarm_m3_step_pose_binding_20260929.json --output C:\IsaacSim\evidence\upstream_link_meshes_001.json --status-output C:\IsaacSim\evidence\upstream_link_meshes_001.status.json`;
  `python -m py_compile software/integrations/isaac_sim/upstream_link_mesh_probe.py software/tests/unit/test_isaac_sim_upstream_link_mesh_evidence.py`;
  `python -m pytest software/tests/unit/test_isaac_sim_upstream_link_mesh_evidence.py software/tests/unit/test_isaac_sim_step_link_membership_evidence.py software/tests/unit/test_isaac_sim_step_pose_binding_evidence.py software/tests/unit/test_isaac_sim_step_inspection_evidence.py software/tests/unit/test_isaac_sim_rc03_scene_evidence.py software/tests/unit/test_isaac_sim_urdf_import_evidence.py software/tests/unit/test_isaac_sim_fk_parity_evidence.py software/tests/unit/test_isaac_sim_first_launch_evidence.py software/tests/unit/test_isaac_sim_host_probe.py software/tests/unit/test_isaac_sim_contracts.py -q`;
  `python scripts/ci/check_docs.py`; `python scripts/ci/check_evidence_scope.py`;
  `python scripts/ci/check_public_records.py`;
  `python scripts/ci/check_repository_artifacts.py`; `git diff --check`.
- Result: PASS_WITH_BLOCKERS for authoritative upstream link grouping. Seven
  referenced meshes contain 19,030 processed vertices, 38,344 triangles, and
  19 connected bodies. Five meshes are watertight; `link1` and `link5` are not.
  The governed home-pose mesh union spans
  `[-48.994999,-40.799999,-0.999998]` to
  `[355.130799,40.799999,387.543710]` mm in the CAD frame and differs from the
  STEP assembly envelope by at most 1.910001 mm, below the declared 2 mm
  diagnostic threshold. `gripper_left_link.stl` exists upstream but is not
  referenced by the Xacro. The focused suite passed 53 tests in 2.45 seconds
  and all four repository audits passed.
- Artifacts:
  `software/integrations/isaac_sim/evidence/roarm_m3_upstream_link_meshes_20260929.json`;
  `software/integrations/isaac_sim/upstream_link_mesh_probe.py`;
  `software/tests/unit/test_isaac_sim_upstream_link_mesh_evidence.py`;
  pinned external upstream checkout under `C:\IsaacSim\sources` and generated
  receipt/status under `C:\IsaacSim\evidence`.
- Hardware writes: 0.
- Physical movements: 0.
- Limitations: global envelope agreement supports the official per-link
  grouping but does not prove surface-level or link-local equivalence with the
  STEP assembly. The Xacro reuses high-detail visual triangle meshes directly
  as collision meshes; two referenced meshes are non-watertight, the extra
  left-gripper asset is unreferenced, and no convex reduction or self-collision
  pair policy has been reviewed. Tool geometry, camera-support geometry,
  measured placement, dynamics, trajectory, clearance, contact, controller,
  hardware, and physical qualification remain absent. The Isaac toolchain lock
  remains `UNSELECTED`. No AI, arm, or integration gate status changed.
- Supersedes: none. INT-437 remains the fixed-STEP product-candidate evidence;
  this row establishes a stronger independent per-link geometry source.
- Next dependency: derive deterministic conservative reduced shapes from the
  seven pinned link meshes, quantify enclosure error against each source mesh,
  and review the self-collision pair policy before any collision query can be
  admissible.

### E-20260929-INT-439 — conservative link-local box candidates retained

- Stage: S2/S3 simulation oracle WP2.
- Lane: INTEGRATION.
- Commit: `5abd805bf5958d3b2c38a55398d426f6ad103306`.
- Change: reduced each pinned official link mesh to deterministic link-local
  identity-oriented box candidates. Connected components receive separate
  boxes unless their count exceeds the runtime contract's 64-primitives-per-
  body limit; `link5` therefore uses one declared whole-link envelope. The
  change emits evidence only and installs no collision geometry profile.
- Inputs/fixtures: probe SHA-256
  `f0f056ff8beb4c7e9552c9b37969a81ddeaea1339afc745ed1959aba8be6065c`;
  test SHA-256
  `90cf7bb0346fd1e9f6dec1dc0e63951266e2a0b706e645f062de4be07e51a0a0`;
  committed receipt file SHA-256
  `e7007e4c4b0e5924cbaf77ab3257eaf7338711150f5d28f1b1f372740a93b70e`;
  receipt content SHA-256
  `91708da2a349ae3f5e6469d8f6809c2e94543f93a401f98cfd6325303a9e79e1`;
  external final receipt SHA-256
  `e7007e4c4b0e5924cbaf77ab3257eaf7338711150f5d28f1b1f372740a93b70e`;
  external final status SHA-256
  `a92fb5c252ba523fbba0683879c64c80c1dd40985593acb9be32049deff8a0ed`;
  source mesh receipt file SHA-256
  `ab8749f813a20cc93e804eddfaccca8d1997a9d6ef86eb6cebf7368e6e368640`
  and content SHA-256
  `77b7c16e2d7c7a8ee0579b071d6a911516a8ba6d675188971e0c54e466b30954`.
- Failed/corrected evidence retained: run 001 rejected a zero-thickness
  `link5` component rather than emit an invalid runtime box; status SHA-256
  `d875833cd48cec5f15ee91b998f80d0ad8e61b49ccbce6839cbe2e5050c46a75`.
  Run 002 added a declared 0.000001 mm half-extent floor and contained every
  vertex, but its 114 `link5` component boxes exceeded the runtime limit;
  receipt SHA-256
  `5c349123667f2a652c5aae8ce27cc83f121e3ba05e70a14f4bdd5f51783fb1b8`
  and status SHA-256
  `c85e3aa012a4a67036c00120f4f1554ea6b5a7caae8f1a7ca7dd688ad5a3212d`.
  Neither intermediate was promoted or overwritten.
- Command: `$env:PYTHONUTF8='1'; C:\IsaacSim\env_6_1_0\Scripts\python.exe software\integrations\isaac_sim\link_mesh_reduction_probe.py --upstream-repo C:\IsaacSim\sources\roarm_ws-40dbd84 --mesh-receipt software\integrations\isaac_sim\evidence\roarm_m3_upstream_link_meshes_20260929.json --output C:\IsaacSim\evidence\link_mesh_reduction_003.json --status-output C:\IsaacSim\evidence\link_mesh_reduction_003.status.json`;
  `python -m py_compile software/integrations/isaac_sim/link_mesh_reduction_probe.py software/tests/unit/test_isaac_sim_link_mesh_reduction_evidence.py`;
  `python -m pytest software/tests/unit/test_isaac_sim_link_mesh_reduction_evidence.py software/tests/unit/test_isaac_sim_upstream_link_mesh_evidence.py software/tests/unit/test_isaac_sim_step_link_membership_evidence.py software/tests/unit/test_isaac_sim_step_pose_binding_evidence.py software/tests/unit/test_isaac_sim_step_inspection_evidence.py software/tests/unit/test_isaac_sim_rc03_scene_evidence.py software/tests/unit/test_isaac_sim_urdf_import_evidence.py software/tests/unit/test_isaac_sim_fk_parity_evidence.py software/tests/unit/test_isaac_sim_first_launch_evidence.py software/tests/unit/test_isaac_sim_host_probe.py software/tests/unit/test_isaac_sim_contracts.py -q`;
  `python scripts/ci/check_docs.py`; `python scripts/ci/check_evidence_scope.py`;
  `python scripts/ci/check_public_records.py`;
  `python scripts/ci/check_repository_artifacts.py`; `git diff --check`.
- Result: PASS_WITH_BLOCKERS. Fourteen candidate boxes across seven links cover
  all 19,030 processed source vertices with 0.0 mm maximum vertex overflow.
  Twelve candidate sources are watertight and two are not. For watertight
  sources, the median box/source volume ratio is 1.822853 and the maximum is
  21.140792. `link5` has 114 processed face-connected fragments and uses one
  whole-link envelope to remain within the primitive-count contract. The
  focused suite passed 58 tests in 2.72 seconds and all four repository audits
  passed.
- Artifacts:
  `software/integrations/isaac_sim/evidence/roarm_m3_link_mesh_reduction_20260929.json`;
  `software/integrations/isaac_sim/link_mesh_reduction_probe.py`;
  `software/tests/unit/test_isaac_sim_link_mesh_reduction_evidence.py`;
  external run 001, 002, and 003 receipts/status under `C:\IsaacSim\evidence`.
- Hardware writes: 0.
- Physical movements: 0.
- Limitations: vertex containment proves only that each box encloses its source
  vertices. It does not qualify collision false positives, clearance, contact,
  or self-collision exclusions. Volume ratios are omitted for non-watertight
  sources, and the 21.140792 maximum plus `link5` whole-link fallback may be too
  conservative for useful planning. Tool, camera-support, static-environment,
  measured-placement, dynamics, trajectory, controller, hardware, and physical
  qualification remain absent. The Isaac toolchain lock remains `UNSELECTED`.
  No AI, arm, or integration gate status changed.
- Supersedes: none. INT-438 remains the source-link grouping evidence; this row
  supplies bounded candidate geometry without installing it.
- Next dependency: run a collision differential corpus against the raw meshes,
  refine high-inflation and `link5` candidates within the 64-primitive limit,
  then review the self-collision pair policy before proposing any installed
  collision geometry profile.

### E-20260929-INT-440 — serialized containment correction retained

- Stage: S2/S3 simulation oracle WP2.
- Lane: INTEGRATION.
- Commit: `d0f66c753adfee8be280d1df20f56ab4f442eab0`.
- Change: checked the exact six-decimal candidate primitives emitted by
  INT-439 against their source vertices, found that serialization rounding
  could shrink a box, and added a declared 0.000002 mm half-extent containment
  pad before serialization. The corrected receipt replaces the tracked
  candidate artifact while the earlier receipt remains preserved in Git and
  INT-439.
- Inputs/fixtures: corrected probe SHA-256
  `84db7f1931be14eb08ddb63493c04373ededae126d7b4dc31154be8717f36bd1`;
  corrected test SHA-256
  `cd4378e37031f65d4ee8e1febf6e1caac52dee8a58d6605f16eb96bf14933879`;
  corrected committed receipt file SHA-256
  `7176ac55e0a4f5a7099d48a6968e53e3e0134ee027f55837c594470b53eb5431`;
  corrected receipt content SHA-256
  `e714a88c01b567f54b2e8c91b8f1144fcc35db38d2953dfe2c6f31e1d576adab`;
  external receipt SHA-256
  `73e59e8e14785db2f5907d0924e5fa3246bb5b4f9f74387755e5b07e9f853610`;
  external status SHA-256
  `87e27d0d35cfa90ba0707989c9ec087154d851dd78471d3767dadd36d2ff0f89`.
- Command: exact serialized-candidate replay against each sorted source
  component with `C:\IsaacSim\env_6_1_0\Scripts\python.exe` found a maximum
  overflow of `0.000000881713866363043 mm` at `gripper_link` component zero;
  `$env:PYTHONUTF8='1'; C:\IsaacSim\env_6_1_0\Scripts\python.exe software\integrations\isaac_sim\link_mesh_reduction_probe.py --upstream-repo C:\IsaacSim\sources\roarm_ws-40dbd84 --mesh-receipt software\integrations\isaac_sim\evidence\roarm_m3_upstream_link_meshes_20260929.json --output C:\IsaacSim\evidence\link_mesh_reduction_004.json --status-output C:\IsaacSim\evidence\link_mesh_reduction_004.status.json`;
  `python -m pytest software/tests/unit/test_isaac_sim_link_mesh_reduction_evidence.py -q`;
  `git diff --check`.
- Result: CORRECTED_PASS_WITH_BLOCKERS. Exact serialized boxes now retain 0.0
  mm maximum vertex overflow. Candidate count remains 14; median watertight
  volume ratio remains 1.822853 and the padded maximum becomes 21.140797.
  Five focused tests passed.
- Hardware writes: 0.
- Physical movements: 0.
- Limitations: this correction establishes serialized vertex containment only.
  All collision, clearance, self-collision-policy, tool, camera-support,
  placement, controller, hardware, and physical blockers from INT-439 remain.
  No AI, arm, or integration gate status changed.
- Supersedes: INT-439 only for the tracked candidate receipt identity and exact
  serialized-containment claim. INT-439 remains the retained original result.
- Next dependency: run the corrected boxes through the raw-mesh collision
  differential corpus before considering any installation proposal.

### E-20260929-INT-441 — three-pose raw-mesh collision differential

- Stage: S2/S3 simulation oracle WP2.
- Lane: INTEGRATION.
- Commit: `7fea403cd4d81408cb1487ba5cfc17148e95eded`.
- Change: compared the corrected 14-box candidates with the immutable official
  raw link meshes for every unordered link pair at the governed zero, home,
  and ready poses using an identity-bound python-fcl wheel through trimesh.
  Adjacent pairs were measured rather than silently excluded.
- Inputs/fixtures: probe SHA-256
  `8496df7cf5efaa7febbfacaff2f077a2c04649e7e878fea311a0681236646bd6`;
  test SHA-256
  `509c5b83336c41b40cdf99974b8a779fc3f6938b28d0ee15498f6ed134c523ed`;
  committed receipt file SHA-256
  `33a4377ab12f33719bd7d001300e4b37dc7ecbd1aee9437ee7b9407eb0adfbab`;
  receipt content SHA-256
  `46e9133e7e8bc0529f03f3e1fb97e0927a5e3eff77a3d1d0282498c2d397f58f`;
  external status SHA-256
  `2d7223583a89d5b48a9a78fc4e71695344cfc7f6b2d0b6ebbac173d002dc648d`;
  python-fcl 0.7.0.11 Windows CPython 3.12 wheel SHA-256
  `63c662c8ff30eeb78913624a4ac56209a6061248ed97066c3b744255d943299f`;
  corrected reduction receipt content SHA-256
  `e714a88c01b567f54b2e8c91b8f1144fcc35db38d2953dfe2c6f31e1d576adab`.
- Command: `C:\IsaacSim\env_6_1_0\Scripts\python.exe -m pip download --no-deps --only-binary=:all: --dest C:\IsaacSim\sources\python-fcl-0.7.0.11 python-fcl==0.7.0.11`;
  `C:\IsaacSim\env_6_1_0\Scripts\python.exe -m pip install C:\IsaacSim\sources\python-fcl-0.7.0.11\python_fcl-0.7.0.11-cp312-cp312-win_amd64.whl`;
  `$env:PYTHONUTF8='1'; C:\IsaacSim\env_6_1_0\Scripts\python.exe software\integrations\isaac_sim\collision_differential_probe.py --workspace . --upstream-repo C:\IsaacSim\sources\roarm_ws-40dbd84 --mesh-receipt software\integrations\isaac_sim\evidence\roarm_m3_upstream_link_meshes_20260929.json --reduction-receipt software\integrations\isaac_sim\evidence\roarm_m3_link_mesh_reduction_20260929.json --fcl-wheel C:\IsaacSim\sources\python-fcl-0.7.0.11\python_fcl-0.7.0.11-cp312-cp312-win_amd64.whl --output C:\IsaacSim\evidence\collision_differential_002.json --status-output C:\IsaacSim\evidence\collision_differential_002.status.json`;
  `python -m py_compile software/integrations/isaac_sim/collision_differential_probe.py software/tests/unit/test_isaac_sim_collision_differential_evidence.py`;
  `python -m pytest software/tests/unit/test_isaac_sim_collision_differential_evidence.py software/tests/unit/test_isaac_sim_link_mesh_reduction_evidence.py software/tests/unit/test_isaac_sim_upstream_link_mesh_evidence.py software/tests/unit/test_isaac_sim_step_link_membership_evidence.py software/tests/unit/test_isaac_sim_step_pose_binding_evidence.py software/tests/unit/test_isaac_sim_step_inspection_evidence.py software/tests/unit/test_isaac_sim_rc03_scene_evidence.py software/tests/unit/test_isaac_sim_urdf_import_evidence.py software/tests/unit/test_isaac_sim_fk_parity_evidence.py software/tests/unit/test_isaac_sim_first_launch_evidence.py software/tests/unit/test_isaac_sim_host_probe.py software/tests/unit/test_isaac_sim_contracts.py -q`;
  `python scripts/ci/check_docs.py`; `python scripts/ci/check_evidence_scope.py`;
  `python scripts/ci/check_public_records.py`;
  `python scripts/ci/check_repository_artifacts.py`; `git diff --check`.
- Result: PASS_WITH_BLOCKERS across 63 pair-pose cases: 48 free-space
  agreements, three collision agreements, 12 candidate false positives, and
  zero candidate false negatives. Each pose has the same four false-positive
  adjacent pairs: `link1/link2`, `link2/link3`, `link3/link4`, and
  `link5/gripper_link`. All 45 nonadjacent pair-pose cases agree. The focused
  suite passed 63 tests in 3.05 seconds and all four repository audits passed.
- Artifacts:
  `software/integrations/isaac_sim/evidence/roarm_m3_collision_differential_20260929.json`;
  `software/integrations/isaac_sim/collision_differential_probe.py`;
  `software/tests/unit/test_isaac_sim_collision_differential_evidence.py`;
  exact external wheel under `C:\IsaacSim\sources` and generated receipt/status
  under `C:\IsaacSim\evidence`.
- Hardware writes: 0.
- Physical movements: 0.
- Limitations: three static poses do not cover continuous joint space. The
  diagnostic reports adjacent contacts without selecting exclusions. Two raw
  meshes remain non-watertight. Tool, camera-support, environment, measured
  placement, clearance, contact dynamics, controller, hardware, and physical
  qualification remain absent. The Isaac toolchain lock remains `UNSELECTED`.
  Collision query, clearance replay, and candidate installation remain false.
  No AI, arm, or integration gate status changed.
- Supersedes: none. INT-440 governs the candidate receipt identity; this row
  measures its bounded differential without promoting it.
- Next dependency: review the four adjacent-pair relationships against the
  kinematic design, expand the corpus beyond three poses, and refine the high-
  inflation shapes before proposing any pair exclusions or installed profile.

### E-20260929-INT-442 — governed-limit joint-space collision expansion

- Stage: S2/S3 simulation oracle WP2.
- Lane: INTEGRATION.
- Commit: `95d8f812e458aa47a739b8e596f482f4348601a8`.
- Change: expanded INT-441 from three poses to 49 deterministic joint-space
  poses derived only from the governed URDF limits. The corpus contains the
  three governed anchors, all-limit and midpoint anchors, every single-joint
  lower and upper limit, and 32 six-dimensional Halton samples. It compares
  all 21 unordered link pairs and separates adjacent from nonadjacent results.
- Inputs/fixtures: probe SHA-256
  `b0f2f399bc1f944e8a74f50d8e0dc0e5726edca4c594da34a2d7748576e2b33b`;
  test SHA-256
  `f62ee829695515dd6fdd0656fcdfd9fb516531cfbdca98184f2e1c2e1dc6a3b4`;
  committed compact receipt file SHA-256
  `6da0540ce8e668ec28d35f1f949932dacbcbb1419fa07c4445ab65df33def636`;
  compact receipt content SHA-256
  `6161d29a6ce36a3ca9ac54755a7b3f69393af2e3afe49f9f26ee4496da861844`;
  external detailed receipt file SHA-256
  `f1226994510a3489820494021445ba50f4b17bbafaacb5605114b77ef8988f50`
  and content SHA-256
  `0e5908b601b7184312343c9c610ecb9bf0754ad716ff1a59e35b4e8411c4c734`;
  external status SHA-256
  `6c552b622574581b65b8f27ac73d7bffac1eb67686e1b9ff09126326b4388112`;
  governed URDF SHA-256
  `a565718e7d74b07702802cf41eb9549a6e38e50b5e80aa9b887ab1ae3d0d8190`;
  corrected reduction receipt content SHA-256
  `e714a88c01b567f54b2e8c91b8f1144fcc35db38d2953dfe2c6f31e1d576adab`;
  python-fcl wheel SHA-256
  `63c662c8ff30eeb78913624a4ac56209a6061248ed97066c3b744255d943299f`.
- Command: `$env:PYTHONUTF8='1'; C:\IsaacSim\env_6_1_0\Scripts\python.exe software\integrations\isaac_sim\collision_joint_space_probe.py --workspace . --upstream-repo C:\IsaacSim\sources\roarm_ws-40dbd84 --mesh-receipt software\integrations\isaac_sim\evidence\roarm_m3_upstream_link_meshes_20260929.json --reduction-receipt software\integrations\isaac_sim\evidence\roarm_m3_link_mesh_reduction_20260929.json --fcl-wheel C:\IsaacSim\sources\python-fcl-0.7.0.11\python_fcl-0.7.0.11-cp312-cp312-win_amd64.whl --output C:\IsaacSim\evidence\collision_joint_space_003.detailed.json --summary-output C:\IsaacSim\evidence\collision_joint_space_003.summary.json --status-output C:\IsaacSim\evidence\collision_joint_space_003.status.json`;
  `python -m py_compile software/integrations/isaac_sim/collision_joint_space_probe.py software/tests/unit/test_isaac_sim_collision_joint_space_evidence.py`;
  `python -m pytest software/tests/unit/test_isaac_sim_collision_joint_space_evidence.py software/tests/unit/test_isaac_sim_collision_differential_evidence.py software/tests/unit/test_isaac_sim_link_mesh_reduction_evidence.py software/tests/unit/test_isaac_sim_upstream_link_mesh_evidence.py software/tests/unit/test_isaac_sim_step_link_membership_evidence.py software/tests/unit/test_isaac_sim_step_pose_binding_evidence.py software/tests/unit/test_isaac_sim_step_inspection_evidence.py software/tests/unit/test_isaac_sim_rc03_scene_evidence.py software/tests/unit/test_isaac_sim_urdf_import_evidence.py software/tests/unit/test_isaac_sim_fk_parity_evidence.py software/tests/unit/test_isaac_sim_first_launch_evidence.py software/tests/unit/test_isaac_sim_host_probe.py software/tests/unit/test_isaac_sim_contracts.py -q`;
  `python scripts/ci/check_docs.py`; `python scripts/ci/check_evidence_scope.py`;
  `python scripts/ci/check_public_records.py`;
  `python scripts/ci/check_repository_artifacts.py`; `git diff --check`.
- Result: PASS_WITH_BLOCKERS across 1,029 pair-pose cases: 780 free-space
  agreements, 57 collision agreements, 192 candidate false positives, and
  zero candidate false negatives. Adjacent pairs account for 191 false
  positives. One nonadjacent false positive occurs between `link2` and
  `gripper_link` at `halton_019`, where the raw meshes remain 13.607432 mm
  apart while candidate boxes report -13.915923 mm signed separation. The
  focused suite passed 68 tests in 3.23 seconds and all four audits passed.
- Artifacts:
  `software/integrations/isaac_sim/evidence/roarm_m3_collision_joint_space_20260929.json`;
  `software/integrations/isaac_sim/collision_joint_space_probe.py`;
  `software/tests/unit/test_isaac_sim_collision_joint_space_evidence.py`;
  external detailed receipt and status under `C:\IsaacSim\evidence`.
- Hardware writes: 0.
- Physical movements: 0.
- Limitations: 49 deterministic poses are substantially broader than three
  anchors but do not cover continuous joint space. The one nonadjacent false
  positive shows that adjacent-pair policy alone cannot make these candidates
  suitable. Two raw meshes remain non-watertight. Tool, camera-support,
  environment, measured placement, clearance, contact dynamics, controller,
  hardware, and physical qualification remain absent. No pair exclusion was
  selected; profile installation and collision-query admission remain false.
  No AI, arm, or integration gate status changed.
- Supersedes: INT-441 only for corpus breadth. INT-441 remains the retained
  exact three-pose differential.
- Next dependency: refine the `link2` and gripper candidate shapes against the
  `halton_019` witness, then rerun this exact corpus. Separately review adjacent
  joint pairs against mechanical design evidence before any exclusion proposal.

### E-20260929-INT-443 — targeted OBB variants and exact corpus replay

- Stage: S2/S3 simulation oracle WP2.
- Lane: INTEGRATION.
- Commit: `6fba9a80826415336a89d27f7a3c8704f223a284`.
- Change: derived deterministic oriented-box alternatives for the two `link2`
  components and the gripper component implicated by INT-442, then replayed
  the exact 49-pose, 1,029-case corpus for combined, `link2`-only, and gripper-
  only variants. The `link2`-only result is retained as the preferred
  diagnostic candidate; it is not installed or admitted.
- Inputs/fixtures: refinement probe SHA-256
  `6a26872df78ce6969417f90fcb9fa9cf47d36fccc2d15fc275cfd8dd9f09fe82`;
  replay probe SHA-256
  `2fc3bacc136377441c9bcf5e34891fdfa08b64c0217b9882b22bd060aec66abf`;
  test SHA-256
  `b738bef3011dede889a4cb344b00ae92430cba7de10172cf0b6aa0e833c39feb`;
  committed `link2` candidate file/content SHA-256
  `0eb782c71b1ab72c4bbbc7a22abea16f4aead33ce32e435288c9c8a2413b3b41` /
  `68f0aa41c4f46e12b563285f5a48b65f3d0457a7939a1bf537dec93b11740bcb`;
  committed `link2` replay file/content SHA-256
  `c22c6f4db52c9c97634097fab7647b81421148adad3afcae6c24a78ec9ef6e29` /
  `c256eed4869005fa312eaa3371a7b5483f4a4e5e3bcd0fa5128a6ccc053d1fa1`;
  external detailed replay file/content SHA-256
  `7fa6cabff51f8166efc227b013dc6fa54f825c3a3f978405981acf38017fe107` /
  `c7af3fc8caea53bf8440326c5a26622b71c68ced2ceceb42509d0d9a8038a1d0`;
  selected replay status SHA-256
  `85bf4c26994d0533dcc62f3ca9acc8f328f40b51acf9fd6347cd28a7fb8e5c2b`.
- Rejected evidence retained: combined candidate content SHA-256
  `0e412308371d801f6d185617e9e73258cc7f13d35a9d2c6e954795ab150ca605`
  and replay content SHA-256
  `99054875ee0dc0e95f5b58311ec630922aed0166f02dc4895421666ab219862d`;
  gripper-only candidate content SHA-256
  `40458bb4bb82fbe75642ce793b7d561c17928d9e49649c6a1bc5c6da3690905f`
  and replay content SHA-256
  `483e58dbc5954c92931c2c0f8becae555731f17db53e0552075684831fc9c0ad`.
  Combined replay had 144 false positives including two nonadjacent cases;
  gripper-only had 193 false positives including two nonadjacent cases.
- Command: `$env:PYTHONUTF8='1'; C:\IsaacSim\env_6_1_0\Scripts\python.exe software\integrations\isaac_sim\targeted_obb_refinement_probe.py --upstream-repo C:\IsaacSim\sources\roarm_ws-40dbd84 --mesh-receipt software\integrations\isaac_sim\evidence\roarm_m3_upstream_link_meshes_20260929.json --base-reduction software\integrations\isaac_sim\evidence\roarm_m3_link_mesh_reduction_20260929.json --target-links link2 --output C:\IsaacSim\evidence\targeted_obb_refinement_002_link2.json --status-output C:\IsaacSim\evidence\targeted_obb_refinement_002_link2.status.json`;
  `$env:PYTHONUTF8='1'; C:\IsaacSim\env_6_1_0\Scripts\python.exe software\integrations\isaac_sim\collision_joint_space_probe.py --workspace . --upstream-repo C:\IsaacSim\sources\roarm_ws-40dbd84 --mesh-receipt software\integrations\isaac_sim\evidence\roarm_m3_upstream_link_meshes_20260929.json --reduction-receipt C:\IsaacSim\evidence\targeted_obb_refinement_002_link2.json --expected-reduction-sha256 68f0aa41c4f46e12b563285f5a48b65f3d0457a7939a1bf537dec93b11740bcb --fcl-wheel C:\IsaacSim\sources\python-fcl-0.7.0.11\python_fcl-0.7.0.11-cp312-cp312-win_amd64.whl --output C:\IsaacSim\evidence\collision_joint_space_link2_001.detailed.json --summary-output C:\IsaacSim\evidence\collision_joint_space_link2_001.summary.json --status-output C:\IsaacSim\evidence\collision_joint_space_link2_001.status.json`;
  the same two commands were run with target sets `link2,gripper_link` and
  `gripper_link`, each bound to its exact receipt SHA-256 above;
  `python -m pytest software/tests/unit/test_isaac_sim_targeted_obb_refinement_evidence.py software/tests/unit/test_isaac_sim_collision_joint_space_evidence.py software/tests/unit/test_isaac_sim_collision_differential_evidence.py software/tests/unit/test_isaac_sim_link_mesh_reduction_evidence.py software/tests/unit/test_isaac_sim_upstream_link_mesh_evidence.py software/tests/unit/test_isaac_sim_step_link_membership_evidence.py software/tests/unit/test_isaac_sim_step_pose_binding_evidence.py software/tests/unit/test_isaac_sim_step_inspection_evidence.py software/tests/unit/test_isaac_sim_rc03_scene_evidence.py software/tests/unit/test_isaac_sim_urdf_import_evidence.py software/tests/unit/test_isaac_sim_fk_parity_evidence.py software/tests/unit/test_isaac_sim_first_launch_evidence.py software/tests/unit/test_isaac_sim_host_probe.py software/tests/unit/test_isaac_sim_contracts.py -q`;
  four repository audits; `git diff --check`.
- Result: PASS_WITH_BLOCKERS for the `link2`-only diagnostic candidate. Its
  second component volume falls to 94.1967% of the original axis-aligned box;
  serialized vertex overflow remains 0.0 mm. Exact replay reduces false
  positives from 192 to 143: 142 adjacent and one nonadjacent. It preserves
  zero false negatives and all 57 collision agreements. The original
  `halton_019` witness clears, but one `link2`/gripper false positive remains at
  `all_upper`: 21.640035 mm raw separation and -6.752044 mm box signed
  separation. The focused suite passed 73 tests in 3.51 seconds and all
  four audits passed.
- Artifacts:
  `software/integrations/isaac_sim/evidence/roarm_m3_targeted_obb_link2_20260929.json`;
  `software/integrations/isaac_sim/evidence/roarm_m3_collision_joint_space_link2_20260929.json`;
  `software/integrations/isaac_sim/targeted_obb_refinement_probe.py`;
  `software/tests/unit/test_isaac_sim_targeted_obb_refinement_evidence.py`;
  all variant and detailed replay receipts under `C:\IsaacSim\evidence`.
- Hardware writes: 0.
- Physical movements: 0.
- Limitations: oriented boxes materially reduce adjacent false positives but
  do not remove the nonadjacent witness. Gripper orientation introduces a new
  base/gripper false positive and is rejected. The finite corpus, nonwatertight
  source meshes, missing tool/camera/environment geometry, placement, dynamics,
  controller, hardware, and physical blockers remain. No exclusion was
  selected; profile installation and collision-query admission remain false.
  No AI, arm, or integration gate status changed.
- Supersedes: none. INT-442 remains the baseline corpus. This row retains a
  preferred diagnostic variant plus the rejected alternatives.
- Next dependency: partition or otherwise tighten the gripper and remaining
  `link2` geometry without increasing nonadjacent false positives, then replay
  the same corpus. Review adjacent exclusions only after mechanical evidence.

### E-20260929-INT-444 — OBB replay rotation correction

- Stage: S2/S3 simulation oracle WP2.
- Lane: INTEGRATION.
- Commit: `14f26c1b0ed8e85f5000e83c851cb174b23b7f79`.
- Change: primitive-level witness inspection found that the joint-space replay
  applied box centers but omitted each candidate's `rotation_row_major`.
  Added the serialized rotation to the local box transform and reran baseline,
  `link2`-only, gripper-only, and combined candidates across all 1,029 cases.
- Inputs/fixtures: corrected replay probe SHA-256
  `9c49195eb41c812e1efe7af9fcc981fc80d197423344051410fad3aff61dd180`;
  corrected test SHA-256
  `6e917043f237e0b84617dc74d680a037807a14d2ae61382cd732838a49a4cdb5`;
  corrected committed `link2` replay file/content SHA-256
  `76582476094243a66374e098b8197d97a8048029d3c9dac936cef8ea64ff655f` /
  `72635bbb2712676cf33973d50efc4394d642b81077822f1188140f9503a957fd`;
  corrected external detailed replay file/content SHA-256
  `9a33d753335f4156cd25fcee21eeecd71fd8c684ec8585bb7ab066f21be7bc05` /
  `04aaee95e298cca7b09d9873197dddc669f07beec92bcf5f6f093019fb10e746`;
  corrected status SHA-256
  `6308f530d4395f5ea100c17eae16922672dad4849b3c125a02e89cf90a0fc616`;
  gripper-only corrected summary file SHA-256
  `4eb9d384d62b56e951f9f5e2d05da097f577af5e8371b8db728819d246c43f3f`;
  combined corrected summary file SHA-256
  `863be7f1f0a4f8882838de1f27bafafc00a6ff4086f6a371c886a053eb3b48c0`.
- Command: reran the exact INT-443 replay command for each variant after adding
  `local[:3, :3] = rotation_row_major`; baseline replay was also rerun as a
  control with receipt SHA-256
  `e714a88c01b567f54b2e8c91b8f1144fcc35db38d2953dfe2c6f31e1d576adab`;
  `python -m pytest software/tests/unit/test_isaac_sim_targeted_obb_refinement_evidence.py software/tests/unit/test_isaac_sim_collision_joint_space_evidence.py software/tests/unit/test_isaac_sim_collision_differential_evidence.py software/tests/unit/test_isaac_sim_link_mesh_reduction_evidence.py software/tests/unit/test_isaac_sim_upstream_link_mesh_evidence.py software/tests/unit/test_isaac_sim_step_link_membership_evidence.py software/tests/unit/test_isaac_sim_step_pose_binding_evidence.py software/tests/unit/test_isaac_sim_step_inspection_evidence.py software/tests/unit/test_isaac_sim_rc03_scene_evidence.py software/tests/unit/test_isaac_sim_urdf_import_evidence.py software/tests/unit/test_isaac_sim_fk_parity_evidence.py software/tests/unit/test_isaac_sim_first_launch_evidence.py software/tests/unit/test_isaac_sim_host_probe.py software/tests/unit/test_isaac_sim_contracts.py -q`;
  `git diff --check`.
- Result: CORRECTED_PASS_WITH_BLOCKERS. Baseline control remains byte-identical
  at 192 false positives, zero false negatives, 57 collision agreements, and
  780 free agreements. Correctly rotated `link2`-only, gripper-only, and
  combined OBB candidates each produce the same classification counts. No OBB
  variant demonstrates the improvement claimed by INT-443. Seventy-three
  focused tests passed in 3.49 seconds.
- Hardware writes: 0.
- Physical movements: 0.
- Limitations: this correction invalidates INT-443's comparative collision
  conclusion, while its candidate containment and volume measurements remain
  valid. The original 192 false positives and nonadjacent `halton_019` witness
  remain. All finite-corpus, geometry, policy, installation, controller,
  hardware, and physical limitations remain. No gate status changed.
- Supersedes: INT-443 for every replay classification and preferred-variant
  conclusion. INT-443 remains preserved as the original erroneous evidence.
- Next dependency: identify the exact baseline primitive pair at `halton_019`
  and evaluate a triangle-preserving partition rather than a whole-component
  orientation change.

### E-20260929-INT-445 — bounded triangle-preserving link2 partition replay

- Stage: S2/S3 simulation oracle WP2.
- Lane: INTEGRATION.
- Commit: `da55752a55460698463dc86c28121eb421bfada3`.
- Change: identified the exact baseline `halton_019` witness as `link2`
  component 0 against gripper component 0, then evaluated deterministic
  triangle-centroid partitions of the implicated `link2` component. Every
  source triangle is assigned exactly once and every candidate box encloses
  every vertex of its assigned triangles. Retained the first bounded variant
  that removes the nonadjacent witness without a false negative: 16 recursive
  groups. The candidate remains uninstalled and has no collision authority.
- Inputs/fixtures: partition probe SHA-256
  `fe678dcef544a3dc17ee719ed00c0f2aa6602fad85fd545da167c2bd7e86af8a`;
  corrected replay probe SHA-256
  `9c49195eb41c812e1efe7af9fcc981fc80d197423344051410fad3aff61dd180`;
  test SHA-256
  `ee464b8fbb59a64ce92c1331dfda69f22b8b96ba090ea542d668def8dc814922`;
  selected candidate file/content SHA-256
  `5628fac4ac9d27caf138002831e0eb1ebf2d90dfc0c96a34817c0495fb874a4b` /
  `0568f7ba269cf190ca4b9d6bc41ac17c90c72c3489fad433bb064ca2239e5fc6`;
  selected replay file/content SHA-256
  `986cf17c52e4394ab19999a41625ac94cb73840397314f0877c2578739ef9b66` /
  `1cad314d6901c0f639c4771f7be79b235eeadf844eba600129d4f8bb45991b87`;
  external selected detailed file/content SHA-256
  `e2beac0e5a054b8a992adb46b5debe6d1f3285d0409d8e442a79fe2da43bf954` /
  `6543cb63293897458d06dba6f3420699de67c9f1549f7cc12302c9f75b0e4550`;
  selected candidate/replay status SHA-256
  `5ac3e455b62f786321af785ab82abb1a05b5e88feaadf681108d2b2e3ca585e7` /
  `93a60d70a8c939274de41e666318c825752b7a350e0a87fb961446afa0842f63`;
  upstream commit `40dbd84b553695212fab713e8465f817ba95454d`;
  base-reduction content SHA-256
  `e714a88c01b567f54b2e8c91b8f1144fcc35db38d2953dfe2c6f31e1d576adab`;
  python-fcl wheel SHA-256
  `63c662c8ff30eeb78913624a4ac56209a6061248ed97066c3b744255d943299f`.
- Rejected and failed evidence retained: 2, 4, and 8 recursive groups each
  preserve the baseline 192 false positives and one nonadjacent false
  positive. Their candidate content SHA-256 values are respectively
  `ed7aaf21a1a87306d07fe17a1c7e6705b36d86761bd1739210d4cf2231d75fa3`,
  `18e9834a66908130cdcdc9df8695b0895fa7fc5be89449a01a68daba4a9adfe9`,
  and `ef16d2f1477ed7351c1f8798c7c9f18b77d6eead6114bc8e1fea413a93df7292`;
  replay content SHA-256 values are
  `26eb856865c3a9be1f72adcd501d19d2c466aa34e7c834436f1d24fd37269059`,
  `b762c53cb8d39b624e9410ef5d60888ef802749589332a0b92152f223d3519ab`,
  and `1a6f4fcf8f07d757c46d1e730183e06e96013811d8613dec3fe9aabe86f384c6`.
  The 32-group candidate content SHA-256 is
  `c31e24862bc14deb86c939a3b7c61572bbb53c9e429223a49ee828302e0a0804`;
  its replay content SHA-256 is
  `4b1c4ab823c3a2961c2197f076025af00dcdd3efe521ee902c0ce828a7156124`;
  it matches the 16-group classification and provides no further benefit.
  An exploratory 63-group request was rejected by the declared 2-to-32 input
  bound; its retained error status SHA-256 is
  `cfabcd9f977334cd19160274c620770ef61bbca4a50cfb7574a342a7db23ce6a`.
- Command: `$env:PYTHONUTF8='1'; $py='C:\IsaacSim\env_6_1_0\Scripts\python.exe'; foreach ($bands in 2,4,8,16,32) { $stem="C:\IsaacSim\evidence\triangle_partition_final_${bands}"; & $py software\integrations\isaac_sim\triangle_partition_refinement_probe.py --upstream-repo C:\IsaacSim\sources\roarm_ws-40dbd84 --mesh-receipt software\integrations\isaac_sim\evidence\roarm_m3_upstream_link_meshes_20260929.json --base-reduction software\integrations\isaac_sim\evidence\roarm_m3_link_mesh_reduction_20260929.json --band-count $bands --strategy recursive-longest-centroid-axis --output "$stem.candidate.json" --status-output "$stem.candidate.status.json"; $receipt=(Get-Content -Raw "$stem.candidate.json" | ConvertFrom-Json).receipt_sha256; & $py software\integrations\isaac_sim\collision_joint_space_probe.py --workspace . --upstream-repo C:\IsaacSim\sources\roarm_ws-40dbd84 --mesh-receipt software\integrations\isaac_sim\evidence\roarm_m3_upstream_link_meshes_20260929.json --reduction-receipt "$stem.candidate.json" --expected-reduction-sha256 $receipt --fcl-wheel C:\IsaacSim\sources\python-fcl-0.7.0.11\python_fcl-0.7.0.11-cp312-cp312-win_amd64.whl --output "$stem.detailed.json" --summary-output "$stem.summary.json" --status-output "$stem.replay.status.json" }`;
  `python -m pytest software/tests/unit/test_isaac_sim_triangle_partition_refinement_evidence.py software/tests/unit/test_isaac_sim_targeted_obb_refinement_evidence.py software/tests/unit/test_isaac_sim_collision_joint_space_evidence.py software/tests/unit/test_isaac_sim_collision_differential_evidence.py software/tests/unit/test_isaac_sim_link_mesh_reduction_evidence.py software/tests/unit/test_isaac_sim_upstream_link_mesh_evidence.py software/tests/unit/test_isaac_sim_step_link_membership_evidence.py software/tests/unit/test_isaac_sim_step_pose_binding_evidence.py software/tests/unit/test_isaac_sim_step_inspection_evidence.py software/tests/unit/test_isaac_sim_rc03_scene_evidence.py software/tests/unit/test_isaac_sim_urdf_import_evidence.py software/tests/unit/test_isaac_sim_fk_parity_evidence.py software/tests/unit/test_isaac_sim_first_launch_evidence.py software/tests/unit/test_isaac_sim_host_probe.py software/tests/unit/test_isaac_sim_contracts.py -q`;
  four repository audits; `git diff --check`.
- Result: PASS_WITH_BLOCKERS. The selected candidate partitions all 9,216
  source triangles exactly once, records 0.0 mm serialized vertex overflow,
  uses 17 primitives for `link2` and 29 across all links, and stays below the
  64-primitives-per-body bound. Exact replay across 49 poses and 1,029 cases
  records 807 free agreements, 57 collision agreements, 165 adjacent false
  positives, zero nonadjacent false positives, and zero false negatives. The
  `link2`/gripper minimum candidate separation becomes 13.421512 mm versus
  13.607432 mm for the raw meshes. Seventy-eight focused tests passed in
  3.70 seconds and all four repository audits passed.
- Artifacts:
  `software/integrations/isaac_sim/triangle_partition_refinement_probe.py`;
  `software/integrations/isaac_sim/evidence/roarm_m3_triangle_partition_link2_20260929.json`;
  `software/integrations/isaac_sim/evidence/roarm_m3_collision_joint_space_triangle_partition_20260929.json`;
  `software/tests/unit/test_isaac_sim_triangle_partition_refinement_evidence.py`;
  all variant and detailed receipts under `C:\IsaacSim\evidence`.
- Hardware writes: 0.
- Physical movements: 0.
- Limitations: the retained result covers a finite deterministic corpus, not
  continuous joint space. The 165 remaining false positives are adjacent-link
  cases whose policy has not been reviewed. Partition groups are open surface
  subsets, so no per-group volume ratio is asserted. Existing nonwatertight
  source meshes, whole-link `link5` fallback, missing tool, camera-support and
  environment geometry, nominal placement, dynamics, controller, hardware,
  and physical qualification blockers remain. No profile, pair exclusion,
  collision query, clearance replay, lane gate, or integration gate is
  admitted or completed.
- Supersedes: INT-444 only for the next dependency. INT-444 remains the
  correction record, and INT-442 remains the governed baseline.
- Next dependency: review the 165 adjacent witnesses against mechanical design
  evidence before proposing any exclusion policy, and broaden deterministic
  replay only after tool, camera-support, and measured environment geometry
  are bound.

### E-20260929-INT-446 — pinned RoArm-M3 self-collision policy review

- Stage: S2/S3 simulation oracle WP2.
- Lane: INTEGRATION.
- Commit: `36414de12edbc7e46d2d0fbf87dc1d9496ef5be6`.
- Change: bound the retained triangle-partition replay to the exact upstream
  RoArm-M3 SRDF at the pinned source commit and to direct parent-child pairs in
  the governed URDF. Classified every remaining false-positive pair against
  both sources and computed adjacent-only and full-SRDF counterfactual summary
  counts. No exclusion profile is installed or admitted.
- Inputs/fixtures: review probe SHA-256
  `429f7473c9ca5c46054f9dfee7d53299c1f2393f47ea75b611f6820e629473bf`;
  test SHA-256
  `84191f336a0acf3af82fb5a63f3d2a5028963831882b0b4f5402d3b45a124b2d`;
  committed review file/content SHA-256
  `91365b63c7e1fc032d4d94fcd098dfb233079f7777326c89d2c5b7ddeec7e04d` /
  `c6c1df0b304f7f8b36bd6b8e1015244d1b5e427b24476a85f84b846de5001423`;
  external status SHA-256
  `b226629109f45ab60137c4cf84620eea19031bf806d5615e356e87c5a7aae380`;
  upstream commit `40dbd84b553695212fab713e8465f817ba95454d`;
  upstream SRDF path
  `src/roarm_main/roarm_moveit/config/roarm_m3/roarm_m3.srdf` and SHA-256
  `29f1daaeea91a490b85581a9a62dd07be9ab959d7817fad89836c466e8288499`;
  selected replay content SHA-256
  `1cad314d6901c0f639c4771f7be79b235eeadf844eba600129d4f8bb45991b87`.
- Command: `$env:PYTHONUTF8='1'; C:\IsaacSim\env_6_1_0\Scripts\python.exe software\integrations\isaac_sim\self_collision_policy_review_probe.py --workspace . --upstream-repo C:\IsaacSim\sources\roarm_ws-40dbd84 --replay-summary software\integrations\isaac_sim\evidence\roarm_m3_collision_joint_space_triangle_partition_20260929.json --output C:\IsaacSim\evidence\self_collision_policy_review_001.json --status-output C:\IsaacSim\evidence\self_collision_policy_review_001.status.json`;
  `python -m pytest software/tests/unit/test_isaac_sim_self_collision_policy_review_evidence.py software/tests/unit/test_isaac_sim_triangle_partition_refinement_evidence.py software/tests/unit/test_isaac_sim_targeted_obb_refinement_evidence.py software/tests/unit/test_isaac_sim_collision_joint_space_evidence.py software/tests/unit/test_isaac_sim_collision_differential_evidence.py software/tests/unit/test_isaac_sim_link_mesh_reduction_evidence.py software/tests/unit/test_isaac_sim_upstream_link_mesh_evidence.py software/tests/unit/test_isaac_sim_step_link_membership_evidence.py software/tests/unit/test_isaac_sim_step_pose_binding_evidence.py software/tests/unit/test_isaac_sim_step_inspection_evidence.py software/tests/unit/test_isaac_sim_rc03_scene_evidence.py software/tests/unit/test_isaac_sim_urdf_import_evidence.py software/tests/unit/test_isaac_sim_fk_parity_evidence.py software/tests/unit/test_isaac_sim_first_launch_evidence.py software/tests/unit/test_isaac_sim_host_probe.py software/tests/unit/test_isaac_sim_contracts.py -q`;
  four repository audits; `git diff --check`.
- Result: PASS_WITH_BLOCKERS. The SRDF contains 12 exclusions: six `Adjacent`
  and six `Never`. Its six `Adjacent` pairs exactly equal the six direct-joint
  pairs in the governed URDF. All 165 remaining false-positive cases belong to
  four of those direct-joint pairs, leaving zero unsupported false-positive
  pairs. The adjacent-only counterfactual excludes 294 pair-pose cases,
  including 54 raw/candidate collision agreements and 165 candidate false
  positives. Its retained 735 nonadjacent cases contain three collision
  agreements, 732 free agreements, zero false positives, and zero false
  negatives. The full-SRDF counterfactual would exclude 588 cases and is
  recorded without selection. Eighty-three focused tests passed in 3.97
  seconds and all four repository audits passed.
- Artifacts:
  `software/integrations/isaac_sim/self_collision_policy_review_probe.py`;
  `software/integrations/isaac_sim/evidence/roarm_m3_self_collision_policy_review_20260929.json`;
  `software/tests/unit/test_isaac_sim_self_collision_policy_review_evidence.py`;
  external status under `C:\IsaacSim\evidence`.
- Hardware writes: 0.
- Physical movements: 0.
- Limitations: this is a pair-summary counterfactual, not a geometry requery or
  an installed runtime policy. Excluding direct-joint pairs also removes 54
  raw-mesh collision agreements at their mechanical interfaces. The upstream
  SRDF's six `Never` exclusions have not been independently justified and are
  not selected. Finite-corpus, nonwatertight source, whole-link `link5`, tool,
  camera-support, environment, placement, dynamics, controller, hardware, and
  physical blockers remain. No pair exclusion, collision query, clearance
  replay, lane gate, or integration gate is admitted or completed.
- Supersedes: INT-445 only for its adjacent-policy next dependency. INT-445
  remains the selected finite replay and geometry evidence.
- Next dependency: review the six SRDF `Never` pairs against the selected
  replay and source geometry, then define a shared runtime exclusion-policy
  contract before any candidate can be installed.

### E-20260929-INT-447 — finite replay review of SRDF `Never` pairs

- Stage: S2/S3 simulation oracle WP2.
- Lane: INTEGRATION.
- Commit: `0ad69c7d05cec46ea56ea0c5a160394e1ff8dd66`.
- Change: reviewed all six pinned upstream SRDF pairs labeled `Never` against
  the committed 49-pose selected-candidate replay. Retained positive minimum
  raw and candidate separation for each pair and separately retained every
  nonexcluded nonadjacent collision witness. No exclusion is installed.
- Inputs/fixtures: probe SHA-256
  `e6636880f10728b9445fa2814bf7997cfff7ebf9ae695d450e7f26c421dce23b`;
  test SHA-256
  `211add37d11e9646a12ca1ece96a6a5b3dd1934b9f303f90838922bb42080459`;
  committed review file/content SHA-256
  `75ae1fe48c2b9e287f076d1465ebfdb59913a9ca0b253b12c20ad6e6f44e7490` /
  `a2210f019e0dae09274be1e30b36dbaf69ffe3064b54030bb699568c9230c0e8`;
  external status SHA-256
  `82fe018131df2a2a635ed6bc08f8d2d1b9b2a8b6b404785a46c0d4825c8e7963`;
  policy-review content SHA-256
  `c6c1df0b304f7f8b36bd6b8e1015244d1b5e427b24476a85f84b846de5001423`;
  replay content SHA-256
  `1cad314d6901c0f639c4771f7be79b235eeadf844eba600129d4f8bb45991b87`.
- Command: `$env:PYTHONUTF8='1'; C:\IsaacSim\env_6_1_0\Scripts\python.exe software\integrations\isaac_sim\srdf_never_pair_review_probe.py --policy-review software\integrations\isaac_sim\evidence\roarm_m3_self_collision_policy_review_20260929.json --replay-summary software\integrations\isaac_sim\evidence\roarm_m3_collision_joint_space_triangle_partition_20260929.json --output C:\IsaacSim\evidence\srdf_never_pair_review_001.json --status-output C:\IsaacSim\evidence\srdf_never_pair_review_001.status.json`;
  `python -m pytest software/tests/unit/test_isaac_sim_srdf_never_pair_review_evidence.py software/tests/unit/test_isaac_sim_self_collision_policy_review_evidence.py software/tests/unit/test_isaac_sim_triangle_partition_refinement_evidence.py software/tests/unit/test_isaac_sim_targeted_obb_refinement_evidence.py software/tests/unit/test_isaac_sim_collision_joint_space_evidence.py software/tests/unit/test_isaac_sim_collision_differential_evidence.py software/tests/unit/test_isaac_sim_link_mesh_reduction_evidence.py software/tests/unit/test_isaac_sim_upstream_link_mesh_evidence.py software/tests/unit/test_isaac_sim_step_link_membership_evidence.py software/tests/unit/test_isaac_sim_step_pose_binding_evidence.py software/tests/unit/test_isaac_sim_step_inspection_evidence.py software/tests/unit/test_isaac_sim_rc03_scene_evidence.py software/tests/unit/test_isaac_sim_urdf_import_evidence.py software/tests/unit/test_isaac_sim_fk_parity_evidence.py software/tests/unit/test_isaac_sim_first_launch_evidence.py software/tests/unit/test_isaac_sim_host_probe.py software/tests/unit/test_isaac_sim_contracts.py -q`;
  four repository audits; `git diff --check`.
- Result: PASS_WITH_BLOCKERS. All 294 cases across the six `Never` pairs are
  raw/candidate free-space agreements, with zero collisions, false positives,
  or false negatives. Every pair retains positive recorded raw and candidate
  minima; the lowest raw minimum is 34.870661 mm and the lowest candidate
  minimum is 26.995907 mm. Three nonexcluded nonadjacent pairs remain visible:
  `link1`/gripper, `link2`/`link4`, and `link2`/`link5` each record one
  raw/candidate collision agreement. Eighty-eight focused tests passed in
  4.22 seconds and all four repository audits passed.
- Artifacts:
  `software/integrations/isaac_sim/srdf_never_pair_review_probe.py`;
  `software/integrations/isaac_sim/evidence/roarm_m3_srdf_never_pair_review_20260929.json`;
  `software/tests/unit/test_isaac_sim_srdf_never_pair_review_evidence.py`;
  external status under `C:\IsaacSim\evidence`.
- Hardware writes: 0.
- Physical movements: 0.
- Limitations: agreement across 49 poses supports but cannot prove the SRDF's
  continuous-workspace `Never` semantics. Pair-summary minima are not a
  continuous clearance certificate. The three retained collision witnesses
  require trajectory and policy handling rather than exclusion. Existing
  geometry, tool, camera-support, environment, placement, dynamics,
  controller, hardware, and physical blockers remain. No exclusion profile,
  collision query, clearance replay, lane gate, or integration gate is
  admitted or completed.
- Supersedes: INT-446 only for its `Never`-pair next dependency. INT-446
  remains the upstream SRDF and adjacent-policy binding evidence.
- Next dependency: jointly define a strict, hash-bound runtime exclusion-policy
  contract that defaults to no exclusions and cannot grant controller or
  physical authority; keep installation blocked until reviewed separately.

### E-20260929-INT-448 — inert hash-bound exclusion-policy candidate

- Stage: S2/S3 simulation oracle WP2.
- Lane: INTEGRATION.
- Commit: `3cdd25c75d2272310423733aa84b3056ba969c56`.
- Change: added a strict shared schema, immutable loader, and deterministic
  probe for a collision-exclusion policy candidate. The retained candidate
  binds the exact base collision contract, governed robot model, selected
  geometry and replay, pinned upstream SRDF, adjacent review, and `Never`
  review. It proposes all twelve upstream pairs while requiring an empty
  effective-exclusion set, collision checking by default, an explicitly
  uninstalled state, and false values for every authority flag. The loader has
  no installation or application method.
- Inputs/fixtures: loader SHA-256
  `38770b54b3a1d5c0e0e2df9d2b0ce6c60618643e140fac2b75add8359577a08b`;
  schema SHA-256
  `136d5d804271fdee42f43495fcd5a7bcbc6a832f952c188b546520ef55a70b2d`;
  probe SHA-256
  `5f1bcc14e0ebf494974e4c8d55e8aca16b73f32f56ba16eb0b014903d9ef49ef`;
  loader-test SHA-256
  `77fca91ec847c81506718040f42df207ecd34e462a1c8e07bdd381a58cebb6ec`;
  evidence-test SHA-256
  `bfe6c6956d911ca8161d8e88712275711d2facb9796d61c0153f73a66fe66dad`;
  committed candidate file/content SHA-256
  `88e31c4b525ded8ca48d4bae7cf70faff396e2d9f92249296f2b2f3a9c1d3c3f` /
  `651adee0ee18c4d11233e3ed37389a4811236e08b54c0f91a32fd6dfa436e75a`;
  external status SHA-256
  `412d38041194682b54285d9e4423517f68ea7f64c2a4168f5f7290557d7541b9`;
  base collision contract SHA-256
  `d3238c0c95a1d2e7ff74fcb8dccc3eb0aadb0f897b2ea041319bbcd6442af5c3`;
  governed robot model SHA-256
  `a565718e7d74b07702802cf41eb9549a6e38e50b5e80aa9b887ab1ae3d0d8190`;
  selected geometry/replay content SHA-256
  `0568f7ba269cf190ca4b9d6bc41ac17c90c72c3489fad433bb064ca2239e5fc6` /
  `1cad314d6901c0f639c4771f7be79b235eeadf844eba600129d4f8bb45991b87`;
  adjacent/`Never` review content SHA-256
  `c6c1df0b304f7f8b36bd6b8e1015244d1b5e427b24476a85f84b846de5001423` /
  `a2210f019e0dae09274be1e30b36dbaf69ffe3064b54030bb699568c9230c0e8`;
  upstream SRDF SHA-256
  `29f1daaeea91a490b85581a9a62dd07be9ab959d7817fad89836c466e8288499`.
- Command: `python software\integrations\isaac_sim\exclusion_policy_candidate_probe.py --workspace . --geometry-candidate software\integrations\isaac_sim\evidence\roarm_m3_triangle_partition_link2_20260929.json --replay-summary software\integrations\isaac_sim\evidence\roarm_m3_collision_joint_space_triangle_partition_20260929.json --policy-review software\integrations\isaac_sim\evidence\roarm_m3_self_collision_policy_review_20260929.json --never-review software\integrations\isaac_sim\evidence\roarm_m3_srdf_never_pair_review_20260929.json --output C:\IsaacSim\evidence\collision_exclusion_policy_candidate_001.json --status-output C:\IsaacSim\evidence\collision_exclusion_policy_candidate_001.status.json`;
  `python -m pytest software/tests/unit/test_collision_exclusion_policy_candidate.py software/tests/unit/test_isaac_sim_exclusion_policy_candidate_evidence.py software/tests/unit/test_isaac_sim_srdf_never_pair_review_evidence.py software/tests/unit/test_isaac_sim_self_collision_policy_review_evidence.py software/tests/unit/test_isaac_sim_triangle_partition_refinement_evidence.py software/tests/unit/test_isaac_sim_targeted_obb_refinement_evidence.py software/tests/unit/test_isaac_sim_collision_joint_space_evidence.py software/tests/unit/test_isaac_sim_collision_differential_evidence.py software/tests/unit/test_isaac_sim_link_mesh_reduction_evidence.py software/tests/unit/test_isaac_sim_upstream_link_mesh_evidence.py software/tests/unit/test_isaac_sim_step_link_membership_evidence.py software/tests/unit/test_isaac_sim_step_pose_binding_evidence.py software/tests/unit/test_isaac_sim_step_inspection_evidence.py software/tests/unit/test_isaac_sim_rc03_scene_evidence.py software/tests/unit/test_isaac_sim_urdf_import_evidence.py software/tests/unit/test_isaac_sim_fk_parity_evidence.py software/tests/unit/test_isaac_sim_first_launch_evidence.py software/tests/unit/test_isaac_sim_host_probe.py software/tests/unit/test_isaac_sim_contracts.py -q`;
  four repository audits; `git diff --check`.
- Result: PASS_WITH_BLOCKERS. The candidate contains twelve proposed
  exclusions, zero effective exclusions, `CHECK_COLLISION` as the default pair
  disposition, and false collision-query, clearance-replay, controller,
  execution-permit, transport, and physical authority. Strict parsing rejects
  duplicate fields, content tampering, wrong file or source hashes, unknown,
  duplicate, or noncanonical pairs, a nonempty effective set, and any true
  authority flag. One hundred two focused tests passed in 4.68 seconds and all
  four repository audits passed.
- Artifacts:
  `software/src/rocell/simulation/exclusion_policy.py`;
  `software/ai/schemas/collision_exclusion_policy_candidate_v1.schema.json`;
  `software/integrations/isaac_sim/exclusion_policy_candidate_probe.py`;
  `software/integrations/isaac_sim/evidence/roarm_m3_collision_exclusion_policy_candidate_20260929.json`;
  `software/tests/unit/test_collision_exclusion_policy_candidate.py`;
  `software/tests/unit/test_isaac_sim_exclusion_policy_candidate_evidence.py`;
  external status under `C:\IsaacSim\evidence`.
- Hardware writes: 0.
- Physical movements: 0.
- Limitations: the document is a review candidate only. Installed measured
  geometry and engineering acceptance are absent. Finite-corpus, geometry,
  tool, camera-support, environment, placement, dynamics, controller,
  hardware, and physical qualification blockers remain. There is no runtime
  installation path and no collision-query, clearance, controller, permit,
  transport, or physical authority. No lane or integration gate changed.
- Supersedes: INT-447 only for its shared candidate-contract next dependency.
  INT-445 through INT-447 remain the retained geometry and policy evidence.
- Next dependency: arm/runtime lane review of the shared candidate schema and
  a separate promotion/install contract that requires accepted measured
  geometry and explicit engineering acceptance before any effective exclusion
  can exist.

### E-20260929-INT-449 — held-out collision-policy stress campaign

- Stage: S2/S3 simulation oracle WP2.
- Lane: INTEGRATION.
- Commits: `5f839803605139487998531d9603f1ad52c4dbec` and
  `d6a5e48fccb420e9a565d9c9fb5e55e3d7c1efb7`.
- Change: extended the existing joint-space differential probe with bounded,
  configurable Halton ranges while preserving its default 49-pose reproduction
  behavior. Added a strict assessment that binds the inert exclusion candidate
  to a 256-pose held-out replay, separates proposed from retained pairs, and
  preserves pair-level contradictions. The held-out indices 1001 through 1256
  are disjoint from the original indices 1 through 32. No proposal is applied.
- Inputs/fixtures: joint-space probe SHA-256
  `c9bc0fb6d61bdd9ab248a55591dd8043d20396e576202c99d30d7f41249094b1`;
  stress-assessment probe SHA-256
  `5addf69009f92aa1e5e819bde9b6dbb123b4a917aafb766ab494df303e38d68a`;
  unit-test SHA-256
  `9823aa0ad6e8fb095e027df2b9a887a319b2dac5c56aa1c1fb2b84b4c4e3eb5e`;
  evidence-test SHA-256
  `eb2b3cc22feddbf21cdb998e6fd6fcd5d6cf634d1cc792baebf44a8f823a3cf5`;
  committed replay file/receipt SHA-256
  `8b598c5b582f063a5989cd434ef2f4d2a842445c69aa8706becd7948681dc31b` /
  `199a8f77e6cdbc00154ae0f01aca490b4a074c56b6b28dcf0ace641390b8ffe8`;
  committed assessment file/receipt SHA-256
  `d4872389634bbb712de08507088b0bdbe2902d89780f449cf8f709d77d26365f` /
  `8b2662fb183022d93600d4dd72be815e2b0f3a0b0d77722bcd52f478e411bc9a`;
  external detailed replay SHA-256
  `ba6038334744845264987fbf020846eda490c2065a2ecca407c5245d8805273b`;
  replay-status SHA-256
  `79f15e7bdd5a3672246a68dbbff79cf5d11c9fbbe13324953ab5619434ff2648`;
  selected geometry/candidate content SHA-256
  `0568f7ba269cf190ca4b9d6bc41ac17c90c72c3489fad433bb064ca2239e5fc6` /
  `651adee0ee18c4d11233e3ed37389a4811236e08b54c0f91a32fd6dfa436e75a`;
  python-fcl wheel SHA-256
  `63c662c8ff30eeb78913624a4ac56209a6061248ed97066c3b744255d943299f`.
- Preserved intermediate evidence: the first aggregate-only assessment remains
  under `C:\IsaacSim\evidence` with file/status SHA-256
  `65c0253a9c4ff36a956e3ccc7fec666e5c29bcc2419b229b2680d527d9138863` /
  `763f9166287a67254d66a41ae1745681e6258caa4b8031e1d9c21b18d9a7187d`.
  It was not rewritten after the pair-level assessment was added.
- Command: `$env:PYTHONUTF8='1'; C:\IsaacSim\env_6_1_0\Scripts\python.exe software\integrations\isaac_sim\collision_joint_space_probe.py --workspace . --upstream-repo C:\IsaacSim\sources\roarm_ws-40dbd84 --mesh-receipt software\integrations\isaac_sim\evidence\roarm_m3_upstream_link_meshes_20260929.json --reduction-receipt software\integrations\isaac_sim\evidence\roarm_m3_triangle_partition_link2_20260929.json --expected-reduction-sha256 0568f7ba269cf190ca4b9d6bc41ac17c90c72c3489fad433bb064ca2239e5fc6 --fcl-wheel C:\IsaacSim\sources\python-fcl-0.7.0.11\python_fcl-0.7.0.11-cp312-cp312-win_amd64.whl --halton-start 1001 --halton-count 256 --halton-only --output C:\IsaacSim\evidence\collision_policy_stress_001.detailed.json --summary-output C:\IsaacSim\evidence\collision_policy_stress_001.summary.json --status-output C:\IsaacSim\evidence\collision_policy_stress_001.replay.status.json`;
  `python software\integrations\isaac_sim\collision_policy_stress_probe.py --workspace . --candidate software\integrations\isaac_sim\evidence\roarm_m3_collision_exclusion_policy_candidate_20260929.json --stress-replay C:\IsaacSim\evidence\collision_policy_stress_001.summary.json --output C:\IsaacSim\evidence\collision_policy_stress_002.assessment.json --status-output C:\IsaacSim\evidence\collision_policy_stress_002.assessment.status.json`;
  `python -m pytest software/tests/unit/test_isaac_sim_collision_policy_stress.py software/tests/unit/test_isaac_sim_collision_policy_stress_evidence.py software/tests/unit/test_collision_exclusion_policy_candidate.py software/tests/unit/test_isaac_sim_exclusion_policy_candidate_evidence.py software/tests/unit/test_isaac_sim_srdf_never_pair_review_evidence.py software/tests/unit/test_isaac_sim_self_collision_policy_review_evidence.py software/tests/unit/test_isaac_sim_triangle_partition_refinement_evidence.py software/tests/unit/test_isaac_sim_targeted_obb_refinement_evidence.py software/tests/unit/test_isaac_sim_collision_joint_space_evidence.py software/tests/unit/test_isaac_sim_collision_differential_evidence.py software/tests/unit/test_isaac_sim_link_mesh_reduction_evidence.py software/tests/unit/test_isaac_sim_upstream_link_mesh_evidence.py software/tests/unit/test_isaac_sim_step_link_membership_evidence.py software/tests/unit/test_isaac_sim_step_pose_binding_evidence.py software/tests/unit/test_isaac_sim_step_inspection_evidence.py software/tests/unit/test_isaac_sim_rc03_scene_evidence.py software/tests/unit/test_isaac_sim_urdf_import_evidence.py software/tests/unit/test_isaac_sim_fk_parity_evidence.py software/tests/unit/test_isaac_sim_first_launch_evidence.py software/tests/unit/test_isaac_sim_host_probe.py software/tests/unit/test_isaac_sim_contracts.py -q`;
  four repository audits; `git diff --check`.
- Result: PASS_WITH_BLOCKERS across 256 held-out poses and 5,376 pair
  cases: 334 collision agreements, 4,147 free agreements, 895 candidate false
  positives, and zero false negatives. All six proposed `Never` pairs remain
  free in all 1,536 cases with positive recorded minima. The nine nonproposed
  pairs retain 36 collision agreements, 2,255 free agreements, 13 false
  positives across six pairs, and zero false negatives. Those false-positive
  pairs are base/`link4` (1), base/`link5` (2), base/gripper (1),
  `link1`/`link5` (3), `link1`/gripper (5), and `link2`/gripper (1).
  One hundred fourteen focused tests passed in 5.16 seconds and all four
  repository audits passed.
- Artifacts:
  `software/integrations/isaac_sim/collision_joint_space_probe.py`;
  `software/integrations/isaac_sim/collision_policy_stress_probe.py`;
  `software/integrations/isaac_sim/evidence/roarm_m3_collision_policy_stress_replay_20260929.json`;
  `software/integrations/isaac_sim/evidence/roarm_m3_collision_policy_stress_assessment_20260929.json`;
  `software/tests/unit/test_isaac_sim_collision_policy_stress.py`;
  `software/tests/unit/test_isaac_sim_collision_policy_stress_evidence.py`;
  detailed replay and both assessment versions under `C:\IsaacSim\evidence`.
- Hardware writes: 0.
- Physical movements: 0.
- Limitations: the held-out corpus is finite and does not prove continuous
  workspace behavior. Reappearing nonproposed false positives show that the
  49-pose zero-nonadjacent-false-positive result does not generalize to this
  corpus. Source meshes remain nonwatertight, `link5` remains a whole-link
  fallback, and tool, camera-support, environment, measured placement,
  dynamics, controller, hardware, and physical qualification are absent. The
  candidate remains uninstalled with zero effective exclusions and grants no
  collision-query, clearance, controller, permit, transport, or physical
  authority. No lane or integration gate changed.
- Supersedes: INT-448 only for the next geometry dependency. INT-445 through
  INT-448 remain the retained candidate derivation and finite review evidence.
- Next dependency: inspect exact primitive witnesses for the 13 retained-pair
  false positives, prioritizing the whole-link `link5` fallback and gripper
  envelope, then refine geometry without introducing any false negative.

### E-20260929-INT-450 — AI batch to governed Isaac scene alignment

- Stage: S2/S3 simulation process alignment, WP2.
- Lane: INTEGRATION.
- Commit: `296de99bd6ad9232d856fb5c8eb0aca365a3da0e`.
- Change: added a zero-write Isaac overlay for an actual AI-produced
  `ModelMotionBatchV2`. The probe strict-decodes the canonical batch, verifies
  its exact target-catalog and RC03-scene bindings, preserves action order and
  repeated targets, infers one synthetic rigid keyboard placement from unique
  target correspondences, checks each uncertainty disk against its placed key
  safe region, and authors proposal centers, safe regions, and uncertainty
  disks into an external USD. It never accepts a trajectory, changes the
  articulation, steps physics, encodes a controller command, or accesses
  hardware.
- Inputs/fixtures: RC03 workcell layout SHA-256
  `e84db9aa7b88db442f042c6f546196e350c822a2e7609cb4b652b3da535df2e1`;
  retained scene USD/receipt SHA-256
  `77600a60975daaa4d58a20f597851a5d397ed9c452d44ab47ea1832bf42e0f35` /
  `df50ff6a0df0ab1b3561783d0140925d9302cd5b1a16e59207cd6f8e13a2d98b`;
  AI batch/metadata file SHA-256
  `26fa25a5824c2bd3e1b8312f91b801afa02c240487771533b8faed5c4bd531c5` /
  `930cab4459878911069043e99b6718113971fc6c7fee78c6a4d29501462b7afd`;
  probe SHA-256
  `9da9c8b4ea14763c19a9a0cc6017efce9662203fe38f86298c108c6e5d85ecd4`;
  integration/evidence test SHA-256
  `a105bbf2f682771ce82a6fa69685bfb5d849e1970f11ffb7d63bba9957f7cfbf` /
  `9459193a0df8edfca1a83c18557dae18966ea8e32e304169f9f6f705c3b6f18a`;
  committed receipt/status file SHA-256
  `1e88fa086b37d882b4527a6138ad764b9590add883efef6de7257e19e89d682c` /
  `8f72143ae1feb4ca0931f26e3d29d6c14ca78169fa2e686da86fdbb5f62dbcc5`;
  external overlay USD SHA-256
  `a7dcc53a5ed5d83d47aa524818978e5b7d363008c452a81c5d30e59e6703532b`.
- Command: `$env:OMNI_KIT_ACCEPT_EULA='YES'; C:\IsaacSim\env_6_1_0\Scripts\python.exe software\integrations\isaac_sim\model_motion_scene_overlay_probe.py --workspace . --scene-usd C:\IsaacSim\artifacts\issue190\wp2-scene-002\rc03_nominal_rigid_scene.usda --scene-receipt software\integrations\isaac_sim\evidence\rc03_nominal_rigid_scene_20260929.json --batch software\ai\eval\precision_adapter_batch_v2_contract_fixture.json --batch-metadata software\ai\eval\precision_adapter_batch_v2_contract_fixture_metadata.json --output-dir C:\IsaacSim\artifacts\issue190\wp2-command-overlay-001 --receipt C:\IsaacSim\evidence\model_motion_overlay_001.json --status-output C:\IsaacSim\evidence\model_motion_overlay_001.status.json`;
  `$env:PYTHONPATH=(Resolve-Path software/src).Path; python -m pytest software/tests/integration/test_model_motion_scene_overlay_probe.py software/tests/unit/test_isaac_sim_model_motion_scene_overlay_evidence.py software/tests/unit/test_isaac_sim_rc03_scene_evidence.py software/tests/integration/test_model_motion_v2_shared_gate.py software/ai/tests/test_precision_adapter_v2.py software/ai/tests/test_batch_emitter_v2.py -q`;
  `python scripts/maintain_repository.py verify`;
  `git diff --check`.
- Preserved failed attempt: the first wrapper containing
  `if(Test-Path $out){Remove-Item -LiteralPath $out -Recurse -Force}` was
  rejected by the command safety boundary before a process started. The
  absolute output path was separately confirmed absent, then the exact probe
  command above ran without a deletion step. No artifact or evidence file was
  rewritten by that failed attempt. The repository verifier then failed once
  for missing `mistune` package metadata and again for missing `weasyprint`
  package metadata after `mistune>=3` was installed. The declared local test
  dependencies were installed with `python -m pip install "mistune>=3"` and
  `python -m pip install "beautifulsoup4>=4.12" "weasyprint>=70"`; the third
  exact verifier run passed. Both dependency failures occurred before any
  repository mutation by the verifier and are retained here.
- Result: `BLOCKED_UNCERTAINTY_CROSSES_INFERRED_SAFE_REGIONS`. Four actions and
  twelve overlay prims preserved `H, H, 1, PERIOD`, including the repeated H at
  action index 1. Three unique target correspondences fit one rigid synthetic
  placement with maximum residual `7.105427357601002e-14` mm. Every proposal
  center sits at its inferred placed key center, leaving 7 mm to each edge,
  while the qualified synthetic planar disk is `14.400834977163141` mm. Thus
  zero of four uncertainty disks fit. Forty-five focused boundary, producer,
  precision-adapter, scene, and retained-evidence tests passed in 3.15 seconds.
  The repository verifier then passed 123 CI unit tests plus documentation,
  public-record, evidence-scope, artifact, repository-health, source-footprint,
  release-integrity, and readiness-synchronization checks.
- Hardware-write count: 0.
- Physical-movement count: 0.
- Limitations: the RC03 board, keyboard, phone, station, locator, and tag values
  are governed design/simulation geometry. They are not installed measurements;
  the source itself still requires physical board, keyboard underside,
  phone/case, hardware, and tag-stack observations. The batch is a synthetic
  contract fixture whose metadata explicitly denies deployment qualification.
  The inferred placement is visualization-only and cannot replace camera or
  robot calibration. No joint schedule, articulation replay, physics contact,
  collision clearance, controller encoding, or task-effect observation ran.
  No lane or integration-gate status changed.
- Next dependency: consume the arm typing pipeline's exact source-bound
  zero-write joint schedule for a representative batch that uses these same
  target coordinates and satisfies the safe-region uncertainty gate. Replay
  the schedule only in Isaac, compare simulated TCP contact to ordered targets,
  and retain misses, collisions, and ordering failures without hardware or
  physical authority.

### E-20260929-INT-451 — source-bound arm schedule replay in Isaac

- Stage: S2/S3 simulation process alignment, WP2.
- Lane: INTEGRATION.
- Implementation commit: `ff395ff5900f99be3958857c659feccbde31092d`.
  Arm source commit: `5072c163152848bd8d78fa3fbc024e32177ac98d`.
- Change: added a strict extractor for a complete arm-lane shadow-pipeline
  report and a zero-authority in-memory Isaac replay. The extractor requires
  accepted IK at every sample, exact Cartesian/joint semantic agreement,
  canonical joint order, preserved requested order and repetitions, accepted
  synthetic joint dynamics, and no controller commands. The Isaac probe binds
  the bundle, robot USD/import receipt, and simulation-only virtual profile,
  then teleports all scheduled joint states and independently reconstructs the
  120 mm tool-tip pose from the live articulation. It takes zero physics steps.
- Inputs/fixtures: implementation SHA-256
  `f32ea136c8661f9ac93287e766f4911b42c22e534a887efb1c2deadff20d49a2` /
  `fed7abe930bc3bf8e373de7fa017caa012dd89d13326b94e27c0b99eb4152ead`;
  integration/evidence test SHA-256
  `c872ce832a3482fb3cb89ca23bde0cf2b9f370d709a9c4600fb9e6f7f20ab86a` /
  `7c22343eaad6cdc6915ac5c6076b806b82429d49c7c43d183801d0590e20728a`;
  arm export helper SHA-256
  `7314ad8f409c7a3fea32b6dfe06201fa7754881da2fc0881ab0588dd0762f92a`;
  successful full arm report SHA-256
  `681455f0b734e924f0074ccfb7228ecb94c04ba62f5657f9d66b27af438c618b`;
  committed replay bundle file/content SHA-256
  `4aece6ef7c7194aea59af2263caff6d4a3be65273a5df92348bf796b7103bb8c` /
  `b890df278560724de964b374b4d4cc46e0e9c51b430051319034a1d259fdfdc0`;
  committed replay receipt file/content SHA-256
  `3780fd590f912835c85b69d3265291572eca767ab63ab3b859b9dcbbe18b6078` /
  `ea6cc125388ac4b71c2a73374604a2ca672c21889d016cb17af1faebf6fe01cc`;
  status SHA-256
  `7539b48bcc4439d98695050024fd4e90c35d6cce8737fca535fd17199727b431`;
  virtual-profile SHA-256
  `38b348ace299140e5908cf367fc15f32b33bebe9b064d5efffe5dcf95f7b4634`;
  robot USD SHA-256
  `a0ec437fb4d647f354007dc352a3af8b13576eaf4931d69d60a510bf235ebea2`.
- Commands: `$env:PYTHONPATH='software/src;software/tests/unit;software/tests/integration'; python C:\IsaacSim\tools\export_representative_schedule_5072.py`;
  `$env:PYTHONPATH='software/src;software/tests/unit;software/tests/integration'; python C:\IsaacSim\tools\export_representative_schedule_promoted_5072.py`;
  `python software/integrations/isaac_sim/joint_schedule_replay_bundle.py --arm-report C:\IsaacSim\evidence\representative_schedule_promoted_5072.json --arm-commit 5072c163152848bd8d78fa3fbc024e32177ac98d --output C:\IsaacSim\evidence\representative_joint_schedule_bundle_5072.json`;
  `$env:OMNI_KIT_ACCEPT_EULA='YES'; C:\IsaacSim\env_6_1_0\Scripts\python.exe software\integrations\isaac_sim\joint_schedule_isaac_replay_probe.py --usd C:\IsaacSim\artifacts\issue190\wp1-import-003\roarm_m3_kinematic_40dbd84\roarm_m3_kinematic_40dbd84.usda --import-receipt software\integrations\isaac_sim\evidence\roarm_m3_urdf_import_20260929.json --bundle C:\IsaacSim\evidence\representative_joint_schedule_bundle_5072.json --virtual-profile software\config\virtual_commissioning_profile.json --output C:\IsaacSim\evidence\joint_schedule_isaac_replay_5072.json --status-output C:\IsaacSim\evidence\joint_schedule_isaac_replay_5072.status.json`;
  `python -m pytest software/tests/integration/test_joint_schedule_replay_bundle.py software/tests/unit/test_isaac_sim_joint_schedule_replay_evidence.py -q`;
  repository verification and `git diff --check`.
- Preserved failed evidence: the nominal RC03 transform and 100 mm tool report
  is retained externally at SHA-256
  `5f4c4b9c68cafc591f4d8040ea7630b58e008be4133422cfb16c7b62c9a8aec2`.
  It stops after 16 of 121 samples with
  `MINIMUM_NORMALIZED_ARM_JOINT_MARGIN_REJECTED`; the first rejected sample has
  `0.0029863366428572314` normalized margin and `0.001590271049715872` mm
  position error. The simulation overlay with the nominal ready seed is
  retained externally at SHA-256
  `3061f8363858a7019ce11b9a0a4392dfe196397e5eac465f045b15fde0457775`.
  Its first park sample converges but exceeds adjacent-joint continuity with a
  `1.9655926496107192` rad maximum delta. These failures were not relaxed;
  the successful report uses a separately identified synthetic seed at the
  overlay's declared park pose. The first Isaac launch stopped before startup
  because `OMNI_KIT_ACCEPT_EULA` was absent from that shell; the existing
  accepted installation was then exposed with the exact successful command.
- Result: PASS_WITH_BLOCKERS. All 133 IK samples pass with maximum arm-solver
  position error `0.07691098332647842` mm, minimum normalized arm-joint margin
  `0.154335044383209`, and maximum adjacent joint delta
  `0.09243468166349966` rad. Synthetic joint dynamics accepts every sample.
  Isaac preserves four ordered contacts `H, H, 1, PERIOD`, reports maximum
  full-route tool-tip disagreement `0.07684842940066568` mm and maximum joint
  readback disagreement `5.923525581152944e-08` rad. Contact disagreements are
  `0.00007682018682808492`, `0.00007682018682808492`,
  `0.0001850485047460475`, and `0.00014589261019436637` mm. Fifty-eight focused
  boundary, producer, scene, replay, and retained-evidence tests passed in 3.50
  seconds. Repository verification passed 123 CI unit tests plus documentation,
  public-record, evidence-scope, artifact, repository-health, source-footprint,
  release-integrity, and readiness-synchronization checks.
- Artifacts:
  `software/integrations/isaac_sim/joint_schedule_replay_bundle.py`;
  `software/integrations/isaac_sim/joint_schedule_isaac_replay_probe.py`;
  `software/integrations/isaac_sim/evidence/representative_joint_schedule_bundle_5072_20260929.json`;
  `software/integrations/isaac_sim/evidence/joint_schedule_isaac_replay_5072_20260929.json`;
  `software/integrations/isaac_sim/evidence/joint_schedule_isaac_replay_5072_20260929.status.json`;
  `software/tests/integration/test_joint_schedule_replay_bundle.py`;
  `software/tests/unit/test_isaac_sim_joint_schedule_replay_evidence.py`;
  full and failed reports under `C:\IsaacSim\evidence`.
- Hardware-write count: 0.
- Physical-movement count: 0.
- Limitations: the source batch, localization qualification, layout, 120 mm
  tool, and park seed are synthetic or unmeasured simulation inputs. The
  earlier AI batch's `14.400834977163141` mm uncertainty still does not fit the
  7 mm key-edge margin and was not promoted. Replay uses joint teleportation
  with zero physics steps. Installed collision geometry, collision clearance,
  valid inertial properties, dynamics, controller tracking, measured start
  state, key travel, contact force, camera localization, hardware, and physical
  qualification remain absent. After this replay completed, the arm branch
  advanced to `7f22378613bc9866b14912e667882af9201fd52c`, adding shared-emitter
  routing through the profiled shadow service. That later source was reviewed
  but is not retroactively claimed by this commit-bound replay. No lane or
  integration-gate status changed.
- Supersedes: INT-450 only for its joint-schedule replay dependency. INT-450's
  uncertainty blocker remains active and retained.
- Next dependency: feed an actual precision-adapter batch whose qualified
  uncertainty fits the observed key safe regions through this same schedule
  path, starting from the current profiled-service arm source, then run
  installed-geometry collision screening before any dynamics or contact
  simulation. Separately replace the virtual layout, tool length, and synthetic
  park seed with measured calibration and fresh observed state.

### E-20260929-INT-452 — actual-emitter schedule lineage and Isaac replay

- Stage: S2/S3 simulation process alignment, WP2.
- Lane: INTEGRATION.
- Implementation commit: `c764259a94cd0c1d9726257f2ce4f8d1ed1ddc49`.
  Arm source commit: `9e5c878852da6a6e8509598bce9ce43f218efc70`.
- Change: extended the simulation-local replay bundle to v2 so it can require
  and bind actual shared-emitter lineage. The extractor verifies that the
  producer payload SHA-256 equals the canonical retained batch SHA-256, marks
  the supplied observations synthetic, denies deployment qualification, and
  preserves the existing strict schedule, order, zero-authority, and digest
  checks. The latest arm source's actual emitter produced nominal RC03 centers
  for `H, H, 1, PERIOD`; the same production ingress, trajectory, IK, and
  synthetic joint-dynamics boundaries emitted 133 samples, which were replayed
  through the independent Isaac articulation.
- Inputs/fixtures: bundle builder/probe SHA-256
  `e4daf07db09a0c003e35ce913e1bde17ce2c22c12fdbb77822880000d42381f5` /
  `67a3d628c85f9bdbe5a1bdc88a3756916df9fda1f336a13c1631061357490540`;
  integration/evidence test SHA-256
  `ded1c39d84c01c52fd301309d65a14f6d257aac1512d83b51da94d8652eafc99` /
  `4e4b78a0180edd9079c399e591d21f7ba8e2a69b0d40d633e499c0ad9161386a`;
  external export helper/full-report SHA-256
  `0fc75ad67990721a57ea4a48c43111f24267c070632a4e6e26b026e7ce3aa8dd` /
  `8e997fe024e465f29cc583ccb23bceda7f236844ceaabca4b1609db2fca58d41`;
  actual-emitter input/payload SHA-256
  `b5dc580825819a27a5aba3e58275453aa4c7c0a6b365d24a80a9b2c095f06c6d` /
  `d4bad540537d48bee7227aab089f247216a3a88343cb16bd728d41e9ac623f7a`;
  committed bundle file/content SHA-256
  `6a59ce143f5527c7a9ced09b08d5515644ea4fb859dd69691e08483eb020ee42` /
  `52e8e1977cc88bc4d80b1664ccaaec5b4a2d4286c744bf74655f3d683577d71a`;
  committed replay receipt file/content SHA-256
  `b66993bab6aba1a5ab592f2fabb85bf4bca98658fe1bec4e997ea8b5a31b3fc6` /
  `5ac28fd35d62f0cf27d1c9c86c092ecfb74fa9cd36e93eb99dcc0f47dcf90e8c`;
  status SHA-256
  `d3a573a4c60455c554366775f9d32592a618f4dfcdb9b9ecfce55fe901b38ee8`.
- Commands: `$env:PYTHONPATH='software/src;software/ai;software/tests/unit;software/tests/integration'; python C:\IsaacSim\tools\export_actual_emitter_representative_schedule_9e5c878.py`;
  `python software/integrations/isaac_sim/joint_schedule_replay_bundle.py --arm-report C:\IsaacSim\evidence\actual_emitter_representative_schedule_9e5c878.json --arm-commit 9e5c878852da6a6e8509598bce9ce43f218efc70 --require-actual-emitter --output C:\IsaacSim\evidence\actual_emitter_joint_schedule_bundle_9e5c878.json`;
  `$env:OMNI_KIT_ACCEPT_EULA='YES'; C:\IsaacSim\env_6_1_0\Scripts\python.exe software\integrations\isaac_sim\joint_schedule_isaac_replay_probe.py --usd C:\IsaacSim\artifacts\issue190\wp1-import-003\roarm_m3_kinematic_40dbd84\roarm_m3_kinematic_40dbd84.usda --import-receipt software\integrations\isaac_sim\evidence\roarm_m3_urdf_import_20260929.json --bundle C:\IsaacSim\evidence\actual_emitter_joint_schedule_bundle_9e5c878.json --virtual-profile software\config\virtual_commissioning_profile.json --output C:\IsaacSim\evidence\actual_emitter_joint_schedule_isaac_replay_9e5c878.json --status-output C:\IsaacSim\evidence\actual_emitter_joint_schedule_isaac_replay_9e5c878.status.json`;
  `python -m pytest software/tests/integration/test_joint_schedule_replay_bundle.py software/tests/unit/test_isaac_sim_joint_schedule_replay_evidence.py -q`;
  shared focused suite, repository verification, and `git diff --check`.
- Result: PASS_WITH_BLOCKERS. The actual emitter preserves `H, H, 1, PERIOD`,
  including the repeated key, and its canonical output is byte-bound to the
  retained batch. All 133 arm samples pass exactly as in INT-451. Isaac reports
  the identical maximum full-route tool-tip disagreement
  `0.07684842940066568` mm and maximum joint readback disagreement
  `5.923525581152944e-08` rad. This equality isolates producer substitution:
  replacing fixture-origin batch construction with the actual shared emitter
  changes no downstream motion for the same observations. Sixty-two focused
  boundary, producer, scene, replay, and retained-evidence tests passed in 3.57
  seconds. Repository verification passed 123 CI unit tests plus documentation,
  public-record, evidence-scope, artifact, repository-health, source-footprint,
  release-integrity, and readiness-synchronization checks.
- Artifacts:
  `software/integrations/isaac_sim/evidence/actual_emitter_joint_schedule_bundle_9e5c878_20260929.json`;
  `software/integrations/isaac_sim/evidence/actual_emitter_joint_schedule_isaac_replay_9e5c878_20260929.json`;
  `software/integrations/isaac_sim/evidence/actual_emitter_joint_schedule_isaac_replay_9e5c878_20260929.status.json`;
  updated bundle builder, replay probe, integration tests, and evidence tests;
  full source report under `C:\IsaacSim\evidence`.
- Hardware-write count: 0.
- Physical-movement count: 0.
- Limitations: the observations supplied to the actual emitter are synthetic
  nominal target centers with fixture qualification evidence. The v2 bundle
  explicitly sets `synthetic_observations=true` and
  `deployment_qualification_claimed=false`. The simulation-only layout, 120 mm
  tool, and synthetic park seed remain unmeasured. Isaac uses joint teleport
  with zero physics steps. The `14.400834977163141` mm localization uncertainty
  from the actual precision-adapter fixture still exceeds the 7 mm key-edge
  margin. Installed collision geometry, collision clearance, valid inertia,
  dynamics, controller tracking, fresh observed state, contact force, key
  travel, hardware, and physical qualification remain absent. No lane or
  integration-gate status changed.
- Supersedes: INT-451 only for the synthetic producer-substitution dependency.
  INT-451's failed geometry/seed evidence and all physical blockers remain.
- Next dependency: obtain safe-region-fitting output from a deployment-scoped
  physical-camera qualification, then feed those actual observations through
  this now-verified emitter-to-schedule boundary. In parallel, the arm lane must
  install accepted collision geometry before any dynamic or contact replay.

### E-20260929-INT-453 — fixed-fixture synthetic camera practice corpus

- Stage: S2/S3 synthetic perception and data-pipeline rehearsal.
- Lane: INTEGRATION supporting the AI/model lane; no lane status changed.
- Implementation commit: `3fa068b8b4630105f0743843afdc59ef1bbeee73`.
- Change: added a deterministic corpus generator around the existing plan-blind
  virtual arm-camera JPEG path. It captures two achieved arm/camera poses,
  projects the frozen nominal target map, renders simplified keyboard and phone
  target surfaces, and emits eight declared pixel cases per pose: nominal,
  55-percent dim, 145-percent bright, warm cast, elliptical glare, foreground
  arm/tool proxy, the same proxy under dim light, and defocus blur. Each sample
  includes its image digest, achieved joint state, base capture identities,
  target board coordinates, pixel centers and safe polygons, in-frame state,
  exact pixel transform, and synthetic occlusion labels. The generator and
  manifest explicitly deny physical-camera and deployment qualification.
- Inputs/fixtures: generator SHA-256
  `b364906e0798c4f032bf2e329041a775a008e5ee7aa7a23ee0b1c83e0cb90163`;
  focused test SHA-256
  `06899eecfdc5d2e3e652782d94e13dd7c4b0013827b5a9d36ca9865a77a1225f`;
  retained manifest file SHA-256
  `a529ffbdc39aff5450d0378f2e3020c83b398a3e7f853b0ef4e957748e34c7fd`;
  canonical corpus SHA-256
  `03e2d3d7ac2d3a0026b2c24cb0a9d709190794e1adb5b69e038374fa46f152e4`;
  frozen target-catalog SHA-256
  `6779213e832ab27eeda1e7fb245f57ff8cb0d56707b5aa73a8f31ec483a620f2`;
  virtual camera service-definition SHA-256
  `8c6f6df05a8f4e88e933cddb2237bbc9a17b9a8b96602b60638756c3c3119831`.
  The manifest carries the exact SHA-256 of every retained JPEG.
- Commands: `New-Item -ItemType Directory -Force software/runs | Out-Null; $env:PYTHONPATH=(Resolve-Path 'software/src').Path; python software/integrations/isaac_sim/fixed_fixture_practice_corpus.py --output-dir C:\IsaacSim\artifacts\issue190\fixed-fixture-practice-v1`;
  `$env:PYTHONPATH=(Resolve-Path 'software/src').Path; python -m pytest software/tests/unit/test_fixed_fixture_practice_corpus.py software/tests/unit/test_virtual_arm_camera.py -q`;
  `$env:PYTHONPATH=(Resolve-Path 'software/src').Path; python -c "from scripts.ci.offline_checks import TESTS; import pytest; raise SystemExit(pytest.main(['-q', *TESTS]))"`;
  repository policy scripts and `git diff --check`.
- Preserved failed evidence: the first generator invocation stopped before any
  capture because the ignored `software/runs` bootstrap directory was absent.
  The exact error was `BootstrapConfigurationError: evidence_root directory is
  missing: software/runs`. The directory was created and the identical command
  then completed. A later `python scripts/ci/offline_checks.py test` invocation
  stopped because this worktree has no `.venv-ci`; the equivalent declared
  `TESTS` tuple was then run with the active Python environment. Neither failed
  invocation accessed hardware, wrote a controller command, or moved the arm.
- Result: PASS_WITH_BLOCKERS. Sixteen JPEGs totaling 1,265,525 bytes plus a
  532,000-byte manifest were retained. Every sample contains 75 targets and all
  75 projected centers are in frame. The obstruction proxy covers 26 targets
  at `hover_t` and 29 at `hover_e`; both poses also have a combined dim and
  obstructed case. Deterministic regeneration produced identical corpus and
  per-image hashes. Eleven focused corpus and virtual-camera tests passed in
  5.28 seconds. The declared repository offline suite passed 503 tests with 4
  platform skips in 44.49 seconds, and all documentation, evidence-scope,
  artifact, repository-health, source-footprint, release-integrity, and
  readiness-synchronization policy checks passed.
- Artifacts:
  `software/integrations/isaac_sim/fixed_fixture_practice_corpus.py`;
  `software/integrations/isaac_sim/evidence/fixed_fixture_practice_v1/manifest.json`;
  the 16 JPEGs in that directory;
  `software/tests/unit/test_fixed_fixture_practice_corpus.py`;
  reproduction documentation in `software/integrations/isaac_sim/README.md`.
- Hardware-write count: 0.
- Physical-movement count: 0.
- Limitations: the virtual camera intrinsics and mount are unmeasured. The
  rendered key and phone surfaces use nominal safe rectangles rather than
  photoreal device assets. Lighting is a deterministic pixel transformation,
  and obstruction is an image-space proxy rather than rendered robot CAD or a
  depth-aware mask. The fixed-fixture assumption has not been physically
  verified or bound to a measured configuration epoch. These images may train
  invariance and validate data plumbing, but they cannot measure sim-to-real
  error, establish localization coverage, fit an uncertainty bound, release a
  safe-region gate, prove installed collision clearance, or authorize motion.
- Supersedes: none.
- Next dependency: register the real fixed camera, keyboard, phone, board, and
  lighting as one measured configuration epoch; capture a small, disjoint
  physical validation set from that exact installation; then measure the
  synthetic-to-physical gap and qualify or reject synthetic augmentation per
  perturbation. In parallel, replace the image-space obstruction proxy with a
  rendered, pose-bound robot geometry mask and retain depth/segmentation labels.

### E-20260930-INT-454 — fixed-overview FK obstruction masks and depth

- Stage: S2/S3 synthetic perception and obstruction-abstention rehearsal.
- Lane: INTEGRATION supporting the AI/model lane; no lane status changed.
- Implementation commits: `e786bade481fd8d7723e8e4daf94edddf30664dd`
  and corrective packaging commit
  `53ca5ce4ccd44b15b81a1537aa3db3f7affc9fb5`.
- Change: added a fixed-overview corpus generator that holds the synthetic
  camera and board registration constant while deriving three robot poses from
  the pinned URDF and exact joint states. Each URDF parent/child span becomes a
  declared projected capsule with a stable link label and conservative
  per-link depth. The output includes one semantic label PNG and uint16
  millimetre-depth PNG per pose, 15 RGB lighting samples packed into three
  deterministic atlases with exact crop rectangles, and board/pixel target
  labels carrying robot-center occlusion and safe-region overlap fraction.
- Inputs/fixtures: final generator SHA-256
  `87b0d43dbf78122785db9163d2bae928b3db14ed2bc65f681f4b965026bc4b35`;
  focused test SHA-256
  `fa04ec5109e67bcacf5a50f6c806130add37f820433084c570d6389a125ab12d`;
  retained manifest file SHA-256
  `fcd43eae86aeefaa5d4309dfc874f6d56adb673f539e39fb33c59df18cebff46`;
  canonical corpus SHA-256
  `7b0f6be41f75464fae4a6fc75facfd0f7a62d90bc2eee62c64b5c5c7ef5353f6`;
  frozen target-catalog SHA-256
  `6779213e832ab27eeda1e7fb245f57ff8cb0d56707b5aa73a8f31ec483a620f2`;
  pinned kinematic-model SHA-256
  `a565718e7d74b07702802cf41eb9549a6e38e50b5e80aa9b887ab1ae3d0d8190`;
  base synthetic frame SHA-256
  `854ba1e893be26dc849a15ac6665710efcab19340c807dd6707ce2743b9b3487`.
- Commands: `$env:PYTHONPATH=(Resolve-Path 'software/src').Path; python software/integrations/isaac_sim/fixed_overview_segmentation_corpus.py --output-dir C:\IsaacSim\artifacts\issue190\fixed-overview-segmentation-v1-atlas`;
  `$env:PYTHONPATH=(Resolve-Path 'software/src').Path; python -m pytest software/tests/unit/test_fixed_overview_segmentation_corpus.py software/tests/unit/test_fixed_fixture_practice_corpus.py software/tests/unit/test_virtual_pixel_vision.py software/tests/unit/test_virtual_arm_camera.py -q`;
  the declared offline `TESTS` tuple through the active Python environment;
  all repository policy scripts and `git diff --check`.
- Preserved failed evidence: the initial implementation retained 15 separate
  RGB JPEGs, producing 6,105 tracked files against the governed 6,100-file
  ceiling. `check_source_archive_footprint.py` failed with that exact count.
  The individual images were then replaced by three pose atlases whose manifest
  records exact crop rectangles and independently hashed crop JPEG encodings.
  The corrected archive contains 6,093 tracked files. No ceiling was raised and
  no test or image case was removed.
- Result: PASS_WITH_BLOCKERS. Three poses and five lighting cases produce 15
  addressable RGB samples, three semantic masks, and three depth maps. The RGB
  atlases total 2,025,452 bytes, masks/depth total 37,595 bytes, and the manifest
  is 125,241 bytes. The ready pose obscures 4 target centers and overlaps 6
  target safe regions; `hover_t` obscures 14 centers and overlaps 19 regions;
  `hover_e` obscures 14 centers and overlaps 21 regions. Nineteen focused
  corpus, fixed-camera, and arm-camera tests passed in 11.86 seconds. The
  declared repository suite passed 503 tests with 4 Windows platform skips in
  42.67 seconds. Documentation, public-record, evidence-scope, artifact,
  repository-health, corrected source-footprint, release-integrity, and
  readiness-synchronization checks passed.
- Artifacts:
  `software/integrations/isaac_sim/fixed_overview_segmentation_corpus.py`;
  `software/integrations/isaac_sim/evidence/fixed_overview_segmentation_v1/manifest.json`;
  three RGB atlases, three link-label masks, and three robot-depth maps in that
  directory; `software/tests/unit/test_fixed_overview_segmentation_corpus.py`;
  reproduction documentation in `software/integrations/isaac_sim/README.md`.
- Hardware-write count: 0.
- Physical-movement count: 0.
- Limitations: robot bodies are radius-declared capsules around URDF link
  origins, not CAD meshes. Depth is one conservative value per rendered link,
  not a per-triangle z-buffer. The fixed overview camera, board registration,
  device surfaces, lighting response, fixture state, and link radii are
  synthetic or unmeasured. The overlap labels support abstention rehearsal but
  cannot establish visibility performance, localization coverage, an error
  bound, installed collision clearance, physical qualification, or authority.
- Supersedes: INT-453 only for the fixed-camera obstruction approximation;
  INT-453 remains the arm-camera perturbation corpus and retained evidence.
- Next dependency: replace capsule proxies with the pinned robot CAD in the
  governed Isaac scene and export triangle-level RGB, semantic segmentation,
  and depth from the identical fixed camera. Compare CAD and capsule masks per
  pose before deciding whether the lighter-weight generator is conservative.

### E-20260930-INT-455 — official visual-mesh fixed-overview comparison

- Stage: S2/S3 synthetic perception and obstruction-abstention rehearsal.
- Lane: INTEGRATION supporting the AI/model lane; no lane status changed.
- Implementation commit: `8562cab663e4e389ce7815be4db1172f1c519abf`.
- Change: added an Isaac probe that pins the upstream Waveshare commit and
  seven per-link visual-mesh hashes, applies the governed URDF forward
  kinematics for `ready`, `hover_t`, and `hover_e`, and renders each pose from
  the same fixed overview. The retained package contains crop-addressed RGB,
  binary robot-mask, and uint16 millimetre-depth atlases plus a hash-bound
  receipt and zero-authority status. Each mesh mask is compared pixel for pixel
  with the corresponding INT-454 capsule proxy.
- Inputs/fixtures: upstream commit
  `40dbd84b553695212fab713e8465f817ba95454d`; governed URDF SHA-256
  `a565718e7d74b07702802cf41eb9549a6e38e50b5e80aa9b887ab1ae3d0d8190`;
  upstream mesh receipt SHA-256
  `77b7c16e2d7c7a8ee0579b071d6a911516a8ba6d675188971e0c54e466b30954`;
  capsule corpus SHA-256
  `7b0f6be41f75464fae4a6fc75facfd0f7a62d90bc2eee62c64b5c5c7ef5353f6`;
  final probe SHA-256
  `91b610c6834b4306da8dad2605f5ca882161c1a629836722f3f0b5ad06bdc934`;
  focused test SHA-256
  `01a9d6b8442a17da65778f425617fa78f772fbac0ea4705fae1134d63c005ad3`;
  retained manifest file SHA-256
  `729554a4716e571e0db0735a9896af700c1eb9767923c32f7c53cff6a404d79c`;
  canonical receipt SHA-256
  `0abf73eaf3e58f9d7df5f1f2ac2a39dcc666f729f8c7bd34631eb535e9302055`.
- Commands: `$env:OMNI_KIT_ACCEPT_EULA='YES'; $env:PYTHONPATH=(Resolve-Path 'software/src').Path; C:\IsaacSim\env_6_1_0\Scripts\python.exe software\integrations\isaac_sim\isaac_fixed_overview_mesh_render_probe.py --workspace . --upstream-repo C:\IsaacSim\sources\roarm_ws-40dbd84 --mesh-receipt software\integrations\isaac_sim\evidence\roarm_m3_upstream_link_meshes_20260929.json --capsule-manifest software\integrations\isaac_sim\evidence\fixed_overview_segmentation_v1\manifest.json --output-dir C:\IsaacSim\artifacts\issue190\fixed-overview-official-mesh-v6 --receipt C:\IsaacSim\evidence\fixed_overview_official_mesh_v6.json --status-output C:\IsaacSim\evidence\fixed_overview_official_mesh_v6.status.json`;
  `$env:PYTHONPATH=(Resolve-Path 'software/src').Path; python -m pytest software/tests/unit/test_isaac_fixed_overview_mesh_render_evidence.py software/tests/unit/test_fixed_overview_segmentation_corpus.py software/tests/unit/test_fixed_fixture_practice_corpus.py software/tests/unit/test_virtual_pixel_vision.py software/tests/unit/test_virtual_arm_camera.py -q`;
  `$env:PYTHONPATH=(Resolve-Path 'software/src').Path; python -c "from scripts.ci.offline_checks import TESTS; import pytest; raise SystemExit(pytest.main(['-q', *TESTS]))"`;
  documentation, public-record, evidence-scope, artifact, repository-health,
  source-footprint, release-integrity, readiness-synchronization, Ruff, and
  `git diff --check` checks.
- Preserved failed evidence: the first render exited zero but used every
  nonbackground semantic ID, thereby including `UNLABELLED` board/device
  geometry; its receipt/status file SHA-256 values are
  `4b531c2b140913e56bfc09e99286e2ce4617c10755e3056e87d6c01d20dcc1b1`
  and `06c7e4ec73f57e54a4bfde34e36edf349186a0f4a6180b9153c7555c5c72bbb9`.
  The first correction failed closed because all three inherited-visibility
  masks remained identical; status SHA-256
  `7e09cfc4626774afd78ae160eed61ea30be1c91fe58ac7fcdcde09579231a3ec`.
  Explicit per-mesh visibility then correctly exposed that the ready view has
  only six visible link IDs; the overly strict seven-ID assertion failed with
  status SHA-256
  `54c596fec1ff6ba5becb7475bde134c0f6b6cf6ec7def2ca18d24780d3e9df71`.
  The first evidence test also exposed uint16-versus-Pillow-int32 depth hash
  normalization, while Ruff rejected one unused import; both were corrected
  before the retained run. None of these failures was relabeled as passing.
- Result: PASS_WITH_BLOCKERS. At `ready`, the official mesh has 88,567 pixels,
  capsule IoU is `0.5968193509715699`, 9,908 mesh pixels lie outside the
  capsule, and 43,230 capsule pixels lie outside the mesh. At `hover_t`, those
  values are 173,242, `0.7098557113660929`, 22,847, and 38,625. At `hover_e`,
  they are 190,210, `0.6980977455407738`, 30,058, and 39,202. Robot-only depth
  spans 180 to 501 mm across the poses. Therefore the capsule proxy is not a
  conservative official-mesh silhouette. Twenty focused tests passed in 12.52
  seconds. The declared shared suite passed 503 tests with 4 Windows platform
  skips in 45.22 seconds. All applicable repository policy checks passed. The
  committed tree is exactly at the 6,100-file ceiling without raising it.
- Artifacts:
  `software/integrations/isaac_sim/isaac_fixed_overview_mesh_render_probe.py`;
  `software/integrations/isaac_sim/evidence/fixed_overview_official_mesh_v1/`;
  `software/tests/unit/test_isaac_fixed_overview_mesh_render_evidence.py`;
  reproduction documentation in `software/integrations/isaac_sim/README.md`.
- Hardware-write count: 0.
- Physical-movement count: 0.
- Limitations: the official upstream meshes are high-detail visual/perception
  geometry, not reviewed reduced collision geometry. Link1 and link5 are not
  watertight. The renderer uses synthetic materials and lighting, nominal and
  unmeasured camera/robot placement, no tool geometry, and no camera-support
  geometry. The run performs zero physics steps and establishes no collision
  clearance, safe-region localization, physical-camera qualification,
  controller behavior, permit, transport, or physical authority.
- Supersedes: INT-454 only for assessing whether its capsules conservatively
  approximate official visual-mesh silhouettes; INT-454 remains a valid cheap
  synthetic obstruction and perturbation corpus.
- Next dependency: replace the capsule labels in future synthetic training
  renders with the retained official visual-mesh mask/depth path, then add the
  missing tool and camera-support visual geometry. Separately collect a small
  measured physical fixed-camera validation set before assigning any
  synthetic-to-physical qualification or safe-region error bound.

### E-20260930-INT-456 — target-bound official-mesh occlusion labels

- Stage: S2/S3 synthetic perception and obstruction-abstention rehearsal.
- Lane: INTEGRATION supporting the AI/model lane; no lane status changed.
- Implementation commit: `822bb2c99833476ac953c6e916527b467ea53384`.
- Change: extended the retained official-mesh probe and receipt to project the
  frozen 75-target catalog through the exact fixed-overview camera. Every pose
  now carries ordered board-millimetre and pixel geometry, target depth,
  in-frame state, center occlusion, and official-mesh safe-region overlap.
  Receipt serialization is canonical and compact; no tracked artifact was
  added and the repository remains at its 6,100-file ceiling.
- Inputs/fixtures: target-catalog SHA-256
  `6779213e832ab27eeda1e7fb245f57ff8cb0d56707b5aa73a8f31ec483a620f2`;
  upstream commit `40dbd84b553695212fab713e8465f817ba95454d`;
  implementation SHA-256
  `1ee458a4e1565bddd14e40b25934934f8ee73444e4da1e86ce8eef51e12e3e1e`;
  test SHA-256
  `6af1e17858fb434bcd887e0bfc0585e172efc4268e4318acfdc5889230503a77`;
  retained manifest file SHA-256
  `97c8a211e8e0ab9ca5d0e16ae97127d794a0b42aeae74a74bd258ad3888c0b88`;
  canonical receipt SHA-256
  `3b8229d210f8353062009c4f6650ce9bd0a1575a0af09aa85fee20d56db89967`.
- Commands: `$env:OMNI_KIT_ACCEPT_EULA='YES'; $env:PYTHONPATH=(Resolve-Path 'software/src').Path; C:\IsaacSim\env_6_1_0\Scripts\python.exe software\integrations\isaac_sim\isaac_fixed_overview_mesh_render_probe.py --workspace . --upstream-repo C:\IsaacSim\sources\roarm_ws-40dbd84 --mesh-receipt software\integrations\isaac_sim\evidence\roarm_m3_upstream_link_meshes_20260929.json --capsule-manifest software\integrations\isaac_sim\evidence\fixed_overview_segmentation_v1\manifest.json --output-dir C:\IsaacSim\artifacts\issue190\fixed-overview-official-mesh-v7 --receipt C:\IsaacSim\evidence\fixed_overview_official_mesh_v7.json --status-output C:\IsaacSim\evidence\fixed_overview_official_mesh_v7.status.json`;
  `$env:PYTHONPATH=(Resolve-Path 'software/src').Path; python -m pytest software/tests/unit/test_isaac_fixed_overview_mesh_render_evidence.py software/tests/unit/test_fixed_overview_segmentation_corpus.py software/tests/unit/test_fixed_fixture_practice_corpus.py software/tests/unit/test_virtual_pixel_vision.py software/tests/unit/test_virtual_arm_camera.py -q`;
  Ruff, source-footprint, and `git diff --check` checks.
- Result: PASS_WITH_BLOCKERS. All three poses retain the same ordered 46-key
  and 29-phone catalog. `ready` obscures 1 target center and overlaps 5 safe
  regions; `hover_t` obscures 14 centers and overlaps 17 regions; `hover_e`
  obscures 14 centers and overlaps 18 regions. The largest safe-region overlap
  is 0.91 at ready and 1.00 at each hover. Twenty focused tests passed in 12.30
  seconds. The source archive remains within policy at exactly 6,100 files.
- Hardware-write count: 0.
- Physical-movement count: 0.
- Limitations: labels inherit INT-455's synthetic lighting, nominal unmeasured
  camera and placement, missing tool/camera-support geometry, and visual-only
  mesh scope. They support offline training and abstention evaluation only;
  they do not establish localization accuracy, physical visibility coverage,
  collision clearance, execution permission, or physical authority.
- Supersedes: none; augments INT-455 with target-level labels.
- Next dependency: expose this retained receipt through the AI data-building
  path as a synthetic-only occlusion dataset, then train/evaluate abstention on
  disjoint pose/lighting splits without treating those scores as deployment
  qualification. Add measured tool and camera-support geometry when available.

### E-20260930-AI-457 — official-mesh occlusion data builder

- Stage: S2/S3 synthetic perception and abstention development.
- Lane: AI/model; no arm or integration status changed.
- Implementation commit: `35495d0d79c231490149bd22ad1cdbd51a4d815f`.
- Change: added a hash-verifying builder that consumes the retained INT-456
  receipt and official-mesh RGB atlas, materializes nine deterministic images,
  and emits target-specific `target_visible`/`abstain` JSONL. Training uses
  `ready` and `hover_t` crossed with nominal, dim, and bright lighting.
  Evaluation holds out `hover_e` and warm, glare, and blur transformations.
  Both pose and lighting groups are therefore disjoint. The 0.20 maximum
  safe-region overlap is declared before label generation; center occlusion
  always abstains.
- Inputs/fixtures: implementation SHA-256
  `275857499ca39ff0398cadc6f0ddda5e3883606fbcd668de69fbf14dc1f77d60`;
  test SHA-256
  `de552ce13c6935b65a8307a7a06fafd355517118af50ab7b976d4aa12caef480`;
  source manifest file SHA-256
  `9ae31bfc21a6ec522fa8fd0d91ab0d37f789ea1717a371ec4750855308839d5c`;
  source receipt SHA-256
  `b09559c54a5bd65715f5a34003b15c4dd20abd05e860e3cc6d1d4089ffe7e99b`;
  target-catalog SHA-256
  `6779213e832ab27eeda1e7fb245f57ff8cb0d56707b5aa73a8f31ec483a620f2`.
- Commands: `python software/ai/train/build_official_mesh_occlusion_data.py --source-manifest software/integrations/isaac_sim/evidence/fixed_overview_official_mesh_v1/manifest.json --output-dir C:\IsaacSim\artifacts\issue190\official-mesh-occlusion-data-v1`;
  `$env:PYTHONPATH=(Resolve-Path 'software/src').Path; python -m pytest software/tests/unit/test_isaac_fixed_overview_mesh_render_evidence.py software/tests/unit/test_fixed_overview_segmentation_corpus.py software/tests/unit/test_fixed_fixture_practice_corpus.py software/tests/unit/test_virtual_pixel_vision.py software/tests/unit/test_virtual_arm_camera.py software/ai/tests/test_offline.py -q`;
  Ruff, documentation, evidence-scope, artifact, source-footprint,
  release-integrity, and `git diff --check` checks.
- Result: PASS_WITH_BLOCKERS. The deterministic dataset SHA-256 is
  `d18f398e2aa7cf9e4297780158e91946d0c03f44afec97830311daf1a614a546`.
  Training contains 450 rows: 51 abstentions and 399 visible labels, JSONL
  SHA-256 `140636df91e1884ca28d5f8cb9fb3662946a0ab8633f452098de4e87c3f8f107`.
  Evaluation contains 225 rows: 45 abstentions and 180 visible labels, JSONL
  SHA-256 `c00b3c3ded761af0c57e4211441d253bfa9848623b658be02dd114a2b40d70ca`.
  Nine images total 910,461 bytes. The external generated manifest SHA-256 is
  `ff6c9f5523d4334309d685e975a58bb33f57af678b7d8b4792d0b78a4dcf85ea`.
  Forty-nine focused AI, evidence, corpus, and virtual-camera tests passed in
  13.48 seconds. Tampered receipt identity, nondeterministic output, and group
  leakage are rejected.
- Evidence consolidation: the redundant retained `status.json` was removed
  and its `PASS_WITH_BLOCKERS`, minimum-IoU, and maximum-missed-pixel content
  moved inside the canonical receipt before its new hash was calculated. The
  prior file and hashes remain preserved in INT-455 and INT-456. This one-path
  consolidation freed the path used by the builder and kept the repository at
  the unchanged 6,100-file ceiling.
- Hardware-write count: 0.
- Physical-movement count: 0.
- Limitations: all images, pose geometry, transformations, and labels are
  synthetic. The evaluation split is a development fixture rather than a
  physical or deployment qualification set. Tool and camera-support geometry
  remain absent. No localization error, physical visibility coverage,
  collision clearance, model promotion, controller behavior, execution
  permission, or physical authority is established.
- Supersedes: none; consumes and preserves INT-456 source evidence.
- Next dependency: train a small offline occlusion/abstention baseline on the
  generated training split and score the untouched synthetic evaluation split,
  reporting class balance, confusion matrix, calibration, and failure cases.
  Keep any resulting model blocked from deployment until measured physical
  camera data is collected under a registered configuration epoch.

### E-20260930-AI-458 — held-out synthetic occlusion baseline

- Stage: S2/S3 synthetic perception and abstention development.
- Lane: AI/model; no arm or integration status changed.
- Implementation commit: `0134496ab25e28fbf1085d1565174535993bc8b9`.
- Change: trained a deterministic class-weighted logistic baseline on
  standardized 16-by-16 RGB crops around each requested target. Training uses
  only the INT-457 training split. The 0.5 threshold, 800 iterations, 0.08
  learning rate, and 0.001 L2 term are fixed in source. The scorecard retains
  the training and held-out confusion matrices, Brier scores, ten-bin
  calibration errors, calibration bins, and every misclassified case.
- Inputs/fixtures: implementation SHA-256
  `7223eda0881632c2bd8f402c9ada78be1f60b83d92a7107f027b2e5d637fc3d0`;
  test SHA-256
  `a767b7efa189e2b5514ef2c5757b3d6c267fd937c2ccd7e5ca3c66015d0f5ad1`;
  dataset SHA-256
  `d18f398e2aa7cf9e4297780158e91946d0c03f44afec97830311daf1a614a546`.
- Commands: `python software/ai/train/build_official_mesh_occlusion_data.py --source-manifest software/integrations/isaac_sim/evidence/fixed_overview_official_mesh_v1/manifest.json --output-dir C:\IsaacSim\artifacts\issue190\official-mesh-occlusion-data-v3 --baseline-output C:\IsaacSim\artifacts\issue190\official-mesh-occlusion-baseline-v2`;
  `$env:PYTHONPATH=(Resolve-Path 'software/src').Path; python -m pytest software/tests/unit/test_isaac_fixed_overview_mesh_render_evidence.py software/tests/unit/test_fixed_overview_segmentation_corpus.py software/tests/unit/test_fixed_fixture_practice_corpus.py software/tests/unit/test_virtual_pixel_vision.py software/tests/unit/test_virtual_arm_camera.py software/ai/tests/test_offline.py -q`;
  Ruff, documentation, source-footprint, and `git diff --check` checks.
- Result: BLOCKED_SYNTHETIC_ONLY. Training confusion is 49 true abstentions,
  398 true-visible labels, 1 false abstention, and 2 missed abstentions:
  accuracy `0.9933333333333333`, balanced accuracy `0.9791390240306649`,
  Brier score `0.008785044955760532`, and calibration error
  `0.03074390236995543`. Held-out evaluation confusion is 32 true
  abstentions, 118 true-visible labels, 62 false abstentions, and 13 missed
  abstentions: accuracy `0.6666666666666666`, balanced accuracy
  `0.6833333333333333`, Brier score `0.3273629285787362`, and calibration
  error `0.3328667785273153`. The large train/evaluation gap rejects promotion.
  Model SHA-256 is
  `79504ae753d6e0baf82575cd14aae89a9b98eac8e77d9a99ab2398e07204dee1`;
  canonical scorecard SHA-256 is
  `37ce4ecc808c0c906cb81e7a84fd830daa031cb42e00df1ef742fb0c676a541d`;
  scorecard file SHA-256 is
  `c88dc43181e705eb31b83deaa14da626f1519111da05b09e45cf99d41bcc178d`.
  Forty-nine focused tests passed in 21.97 seconds, including deterministic
  retraining and exact retained confusion checks.
- Hardware-write count: 0.
- Physical-movement count: 0.
- Limitations: the baseline sees only synthetic target crops from three robot
  poses and six deterministic lighting families. It has no temporal context,
  no physical frames, no tool or support geometry, and no deployment-calibrated
  uncertainty. Its evaluation split is now consumed and cannot be used as fresh
  selection or tuning evidence. It produces an offline visibility decision,
  not coordinates, motion, controller commands, permits, or authority.
- Supersedes: none; first measured baseline on INT-457.
- Next dependency: predeclare and render additional official-mesh robot pose
  groups. Reserve separate development and untouched evaluation pose/lighting
  families before testing a lighting-normalized or convolutional model. The
  consumed `hover_e` results may diagnose failure modes but may not select the
  next candidate. Physical promotion remains dependent on measured fixed-camera
  data under a registered configuration epoch.

### E-20260930-AI-459 — predeclared official-mesh pose expansion

- Stage: S2/S3 synthetic perception and abstention development.
- Lane: AI/model with an inert Isaac rendering fixture; no arm or integration
  status changed.
- Implementation commit: `33dca133ff53d6d27cff4b746d6b56d40c9e5acc`.
- Change: expanded the fixed-overview official visual-mesh renderer from three
  to nine poses and declared all split roles before rendering. Previously seen
  `ready`, `hover_t`, and consumed `hover_e` form the training geometry;
  schedule sequences 34/35 (`hover_h`/`contact_h`) form development geometry;
  and sequences 63/64/103/104 (`hover_1`/`contact_1`/`hover_period`/
  `contact_period`) are reserved for untouched evaluation. The six new states
  are read from the retained actual-emitter schedule by exact sequence and the
  schedule must retain zero authority. Only the original three poses carry a
  capsule comparison because the capsule corpus has no labels for new poses.
- Inputs/fixtures: renderer SHA-256
  `2070df6e087f54ac924a2d5a81ecf4cf5c49f90dbf98c15472dfa3bc892e300f`;
  schedule file SHA-256
  `6a59ce143f5527c7a9ced09b08d5515644ea4fb859dd69691e08483eb020ee42`;
  schedule bundle SHA-256
  `52e8e1977cc88bc4d80b1664ccaaec5b4a2d4286c744bf74655f3d683577d71a`;
  target-catalog SHA-256
  `6779213e832ab27eeda1e7fb245f57ff8cb0d56707b5aa73a8f31ec483a620f2`;
  source upstream commit `40dbd84b553695212fab713e8465f817ba95454d`.
- Commands: `$env:OMNI_KIT_ACCEPT_EULA='YES'; $env:PYTHONPATH=(Resolve-Path
  'software/src').Path; C:\IsaacSim\env_6_1_0\Scripts\python.exe
  software/integrations/isaac_sim/isaac_fixed_overview_mesh_render_probe.py
  --workspace . --upstream-repo C:\IsaacSim\sources\roarm_ws-40dbd84
  --mesh-receipt software/integrations/isaac_sim/evidence/roarm_m3_upstream_link_meshes_20260929.json
  --capsule-manifest software/integrations/isaac_sim/evidence/fixed_overview_segmentation_v1/manifest.json
  --schedule-bundle software/integrations/isaac_sim/evidence/actual_emitter_joint_schedule_bundle_9e5c878_20260929.json
  --output-dir C:\IsaacSim\artifacts\issue190\fixed-overview-official-mesh-v2-run2
  --receipt C:\IsaacSim\evidence\fixed_overview_official_mesh_v2_run2.json
  --status-output C:\IsaacSim\evidence\fixed_overview_official_mesh_v2_run2.status.json`;
  `python -m ruff check software/integrations/isaac_sim/isaac_fixed_overview_mesh_render_probe.py`;
  `python -m pytest software/tests/unit/test_isaac_fixed_overview_mesh_render_evidence.py -q`.
- Failed evidence preserved: the same render command first named the nonempty
  pre-existing external directory `fixed-overview-official-mesh-v2` and stopped
  before Isaac initialization with `ValueError: output directory must be
  empty`. Its status SHA-256 is
  `4db7c8a1d90df84431d85b444cb740002859148e3aff03cdaa1b6659792fb931`.
  Hardware writes and physical movements were zero.
- Result: PASS_WITH_BLOCKERS. All nine semantic masks are distinct. Center-
  occluded target counts for `ready`, `hover_t`, `hover_e`, `hover_h`,
  `contact_h`, `hover_1`, `contact_1`, `hover_period`, and `contact_period`
  are respectively `1,14,14,12,12,9,9,7,7`; counts exceeding the predeclared
  0.20 safe-region-overlap threshold are `2,15,15,17,15,13,12,9,9`.
  Canonical receipt SHA-256 is
  `47fb8d389d956b877e444f4c9221c08a9b2d73fa6b4f6898eaf3d401a7e79ca0`;
  receipt file SHA-256 is
  `f5072ea7884c080837d1bd5945b00a82ddd14b8c08bda0a4a058e6f5c4dbe375`.
  RGB/mask/depth atlas SHA-256 values are respectively
  `e26789c36a7cfc121b943ad2874912e7971e22a48161cae75fc27443383ca942`,
  `513e66280b51f7da76bf5ec7b1d4a799b0f0723de0713c58651109f45b729641`,
  and `7e77446b1ce5eb3adb0cc2b21e47e43e6bb78c1e8d55c16b1c29d469b4e49012`.
  Three focused retained-evidence tests passed in 9.82 seconds and Ruff passed.
- Artifact location: external only at
  `C:\IsaacSim\artifacts\issue190\fixed-overview-official-mesh-v2-run2` and
  `C:\IsaacSim\evidence\fixed_overview_official_mesh_v2_run2.json`; repository
  retention would exceed the governed 6,100-file ceiling. The hashes above
  identify the exact local bytes but do not make them clean-clone available.
- Hardware-write count: 0.
- Physical-movement count: 0.
- Physics-step count: 0.
- Limitations: official visual meshes, camera, board placement, lighting, and
  occlusion labels remain synthetic. Tool and camera-support geometry are
  absent. The reserved evaluation poses have not been used for model selection
  or scoring. This evidence establishes no physical visibility coverage,
  localization accuracy, collision clearance, controller behavior, execution
  permission, or physical authority.
- Supersedes: none; expands INT-455/INT-456 while preserving AI-458 as the
  consumed first baseline.
- Next dependency: materialize training/development/evaluation datasets with
  disjoint predeclared lighting families, select a compact candidate using only
  training and development, then score the reserved evaluation group once.

### E-20260930-AI-460 — three-way official-mesh occlusion dataset

- Stage: S2/S3 synthetic perception and abstention development.
- Lane: AI/model; no arm or integration status changed.
- Implementation commit: `280878de88f38672e3c04145d211a7d0146d35fa`.
- Change: extended the hash-verifying synthetic dataset builder without
  changing its v1 results. A v2 source must declare training, development, and
  evaluation pose groups that exactly partition every rendered pose and agree
  with each pose row. Training uses nominal/dim/bright lighting, development
  uses warm/glare/blur, and evaluation uses newly implemented cool/side-shadow/
  defocus transformations. These pose and lighting families are pairwise
  disjoint. The reserved evaluation JSONL and images are materialized for
  immutable identity and leakage checking but have not been scored or used to
  select a model.
- Inputs/fixtures: builder SHA-256
  `0f4bd03e7bc32bd6016f20204e849fc18604c9f7ff2dece5fc84079ec901ee37`;
  focused evidence-test SHA-256
  `d46ff3e3d2bc1a01dd33164c59a091f05915e603e1bcecc5e099b45d977fa900`;
  source receipt file SHA-256
  `f5072ea7884c080837d1bd5945b00a82ddd14b8c08bda0a4a058e6f5c4dbe375`;
  source receipt SHA-256
  `47fb8d389d956b877e444f4c9221c08a9b2d73fa6b4f6898eaf3d401a7e79ca0`;
  target-catalog SHA-256
  `6779213e832ab27eeda1e7fb245f57ff8cb0d56707b5aa73a8f31ec483a620f2`.
- Commands: `Copy-Item C:\IsaacSim\evidence\fixed_overview_official_mesh_v2_run2.json
  C:\IsaacSim\artifacts\issue190\fixed-overview-official-mesh-v2-run2\manifest.json`;
  `python software/ai/train/build_official_mesh_occlusion_data.py
  --source-manifest C:\IsaacSim\artifacts\issue190\fixed-overview-official-mesh-v2-run2\manifest.json
  --output-dir C:\IsaacSim\artifacts\issue190\official-mesh-occlusion-expanded-v1`;
  repeated with output `official-mesh-occlusion-expanded-v2` for deterministic
  byte comparison; `$env:PYTHONPATH=(Resolve-Path 'software/src').Path; python
  -m pytest software/tests/unit/test_isaac_fixed_overview_mesh_render_evidence.py
  software/tests/unit/test_fixed_overview_segmentation_corpus.py
  software/tests/unit/test_fixed_fixture_practice_corpus.py
  software/tests/unit/test_virtual_pixel_vision.py
  software/tests/unit/test_virtual_arm_camera.py software/ai/tests/test_offline.py
  -q`; Ruff and `git diff --check`.
- Result: PASS_WITH_BLOCKERS. Two independent builds are byte-identical.
  Dataset SHA-256 is
  `e672b3a1fe9d23376b91c07ce56f85005443cf521645373110de24791712607d`;
  manifest file SHA-256 is
  `0ace2d7e018cdd53fee659375a3c325f6b33093d54f8e70824cf8e63b77dbd50`.
  Training contains 675 rows with 96 abstentions and 579 visible labels,
  JSONL SHA-256
  `a2fd3e3e52dd42757fbda35882eeecc8f9dae4a80ccd59eb21f12bad5983c97f`.
  Development contains 450 rows with 96 abstentions and 354 visible labels,
  JSONL SHA-256
  `2b6b695fbf8f7f8df9a8515c44e2731d60ca9fb717af4bc0f5a087c7ac301146`.
  Reserved evaluation contains 900 rows with 129 abstentions and 771 visible
  labels, JSONL SHA-256
  `c7eba79268e436cb9dda75cdded8910807f97bee40ac2dd4bb530651cddfd954`.
  All 27 generated images have distinct SHA-256 values and total 2,844,007
  bytes. Fifty-one focused tests passed in 22.16 seconds and Ruff passed. The
  tracked repository remains at exactly 6,100 files.
- Artifact location: external only at
  `C:\IsaacSim\artifacts\issue190\official-mesh-occlusion-expanded-v1` and
  deterministic repeat `...expanded-v2`; hashes identify exact local bytes but
  do not make them clean-clone available.
- Hardware-write count: 0.
- Physical-movement count: 0.
- Limitations: all source renders, transformations, geometry, and labels are
  synthetic. The dataset omits measured tool and camera-support geometry,
  physical frames, temporal evidence, and deployment-calibrated uncertainty.
  Merely materializing the reserved evaluation group is not model evaluation.
  The dataset cannot qualify localization, collision clearance, controller
  behavior, execution permission, or physical authority.
- Supersedes: none; preserves the v1 AI-457/AI-458 dataset and baseline exactly.
- Next dependency: train compact candidates on training only, select one using
  development only, freeze its checkpoint and decision threshold, then score
  the reserved evaluation group once. Keep every result synthetic-only and
  blocked from deployment pending measured fixed-camera evidence.

### E-20260930-AI-461 — compact occlusion candidate selection and reserved evaluation

- Stage: S2/S3 synthetic perception and abstention development.
- Lane: AI/model; no arm or integration status changed.
- Implementation commit: `c16893093045bfe93756b4ad0966783223775404`.
- Change: fit two deterministic class-weighted logistic candidates using only
  AI-460 training rows: raw RGB crops and brightness-normalized chromatic,
  grayscale, and first-difference edge features. Each threshold was selected
  on development only from explicit 0.05 increments. Ranking first preferred a
  development missed-abstention rate at or below 0.05, then balanced accuracy,
  false abstentions, and missed abstentions. Neither candidate met the 0.05
  bound, so the deterministic ranking fallback selected the higher-balanced-accuracy
  chromatic/edge candidate. Its feature family, threshold, weights, and
  standardization were frozen before the reserved evaluation JSONL was loaded.
  That evaluation was then scored exactly once.
- Inputs/fixtures: implementation SHA-256
  `673709ec4aaba36dcf6eb79235533669a99bd900155ff03d7769e8c14542c401`;
  focused evidence-test SHA-256
  `fb0a2825dfaa9b34700734c162a09bb82eb954970bb79ad5a0bea79891790ae8`;
  dataset SHA-256
  `e672b3a1fe9d23376b91c07ce56f85005443cf521645373110de24791712607d`;
  training/development/evaluation JSONL identities remain exactly those in
  AI-460.
- Command: `python software/ai/train/build_official_mesh_occlusion_data.py
  --source-manifest C:\IsaacSim\artifacts\issue190\fixed-overview-official-mesh-v2-run2\manifest.json
  --output-dir C:\IsaacSim\artifacts\issue190\official-mesh-occlusion-expanded-v3
  --candidate-output C:\IsaacSim\artifacts\issue190\official-mesh-occlusion-candidate-v1`;
  `$env:PYTHONPATH=(Resolve-Path 'software/src').Path; python -m pytest
  software/tests/unit/test_isaac_fixed_overview_mesh_render_evidence.py
  software/tests/unit/test_fixed_overview_segmentation_corpus.py
  software/tests/unit/test_fixed_fixture_practice_corpus.py
  software/tests/unit/test_virtual_pixel_vision.py
  software/tests/unit/test_virtual_arm_camera.py software/ai/tests/test_offline.py
  -q`; Ruff, documentation, and `git diff --check` checks.
- Failed evidence preserved: two focused pre-run test attempts returned one
  failure because the threshold unit fixture expected `0.20` while its negative
  examples gave `0.10` the same false-positive count and better recall. Rounding
  the threshold grid did not change that correct `0.10` selection. The fixture
  was corrected to distinguish the thresholds; the selection implementation
  retained explicit two-decimal thresholds. Both failures involved no model
  evaluation, hardware write, or physical movement.
- Development results: raw RGB selected threshold `0.90` and produced 73 true
  abstentions, 234 true-visible labels, 120 false abstentions, and 23 missed
  abstentions; balanced accuracy `0.7107168079096045`, Brier score
  `0.32920465840558444`, and calibration error `0.3401623490847901`.
  Chromatic/edge features selected threshold `0.25` and produced 86 true
  abstentions, 236 true-visible labels, 118 false abstentions, and 10 missed
  abstentions; balanced accuracy `0.78125`, Brier score
  `0.28322995445080373`, calibration error `0.2813957820375068`, and missed-
  abstention rate `0.10416666666666667`. Neither met the declared 0.05 bound.
- Reserved evaluation result: BLOCKED_SYNTHETIC_ONLY. The frozen chromatic/edge
  checkpoint at threshold `0.25` produced 77 true abstentions, 769 true-visible
  labels, 2 false abstentions, and 52 missed abstentions: accuracy `0.94`,
  balanced accuracy `0.7971525955418816`, Brier score
  `0.05842087208017514`, and calibration error `0.05288915202213142`. The
  missed-abstention rate is `52/129 = 0.40310077519379844`; the high overall
  accuracy therefore does not support admission. Model SHA-256 is
  `c016363ef67aaac110c4c1743f6bd5a3f47f24f1f83f342842d7d5984d7e3d3d`;
  canonical scorecard SHA-256 is
  `209b9ff2801f2f05783c7f42d47dcee43aedad399d9c976468d20b37ec6cd1c3`;
  scorecard file SHA-256 is
  `176041bf12154d5f040dc1392819c5419ebdcf9b23fb17878d4db8579f7eba14`.
  Fifty-three focused tests passed in 21.91 seconds and Ruff passed. The tracked
  repository remains at exactly 6,100 files.
- Artifact location: external only at
  `C:\IsaacSim\artifacts\issue190\official-mesh-occlusion-candidate-v1`;
  hashes identify the local bytes but do not make them clean-clone available.
- Hardware-write count: 0.
- Physical-movement count: 0.
- Limitations: all data and labels are synthetic and omit measured tool and
  camera-support geometry, physical frames, temporal evidence, and deployment-
  calibrated uncertainty. The evaluation group is now consumed and cannot be
  used to tune another candidate. The checkpoint emits only an offline
  occlusion probability and has no coordinate, motion, controller, permit,
  transport, or physical authority.
- Supersedes: none; rejects promotion of the AI-460 compact candidate.
- Next dependency: add predeclared geometry diversity that covers the observed
  evaluation failure modes, including tool/camera-support meshes when measured,
  and reserve another untouched pose group before evaluating a spatial model.
  Physical promotion still requires measured fixed-camera evidence under a
  registered configuration epoch.

### E-20260930-AI-462 — fresh transit-geometry official-mesh expansion

- Stage: S2/S3 synthetic perception and abstention development.
- Lane: AI/model with an inert Isaac rendering fixture; no arm or integration
  status changed.
- Implementation commit: `b3c095ab327a827a77ca2a0fc71255f5abe09927`.
- Change: expanded the fixed-camera official-mesh source from nine endpoint
  poses to 21 predeclared poses. All nine geometries consumed through AI-461
  now form training. Previously unused actual-emitter schedule sequences
  8/17/26 and 112/120/128 form outbound/return development geometry. Unused
  sequences 44/52/60 and 72/84/96 form untouched H-to-1 and 1-to-PERIOD
  evaluation geometry. Split roles and exact sequence bindings were committed
  before rendering. The evaluation group has not been supplied to a model.
- Diagnostic input: the consumed AI-461 evaluation scorecard was read only to
  group its 54 failures. It contained 52 missed occlusions and two false
  abstentions; 36 failures used the cool transformation and failures occurred
  across all four endpoint poses. This diagnosis did not select, label, score,
  or inspect the new transit evaluation group.
- Inputs/fixtures: renderer SHA-256
  `89bcc878f11b7cf675a9b986479363afcd1048ddd2f8994e6c75a08731b1d815`;
  focused evidence-test SHA-256
  `128e3b2da941f46ce53a165c0b7691c06070848c3fddab9323b42f48ac49f435`;
  schedule file SHA-256
  `6a59ce143f5527c7a9ced09b08d5515644ea4fb859dd69691e08483eb020ee42`;
  schedule bundle SHA-256
  `52e8e1977cc88bc4d80b1664ccaaec5b4a2d4286c744bf74655f3d683577d71a`;
  target-catalog SHA-256
  `6779213e832ab27eeda1e7fb245f57ff8cb0d56707b5aa73a8f31ec483a620f2`.
- Command: `$env:OMNI_KIT_ACCEPT_EULA='YES'; $env:PYTHONPATH=(Resolve-Path
  'software/src').Path; C:\IsaacSim\env_6_1_0\Scripts\python.exe
  software/integrations/isaac_sim/isaac_fixed_overview_mesh_render_probe.py
  --workspace . --upstream-repo C:\IsaacSim\sources\roarm_ws-40dbd84
  --mesh-receipt software/integrations/isaac_sim/evidence/roarm_m3_upstream_link_meshes_20260929.json
  --capsule-manifest software/integrations/isaac_sim/evidence/fixed_overview_segmentation_v1/manifest.json
  --schedule-bundle software/integrations/isaac_sim/evidence/actual_emitter_joint_schedule_bundle_9e5c878_20260929.json
  --output-dir C:\IsaacSim\artifacts\issue190\fixed-overview-official-mesh-v3-run1
  --receipt C:\IsaacSim\evidence\fixed_overview_official_mesh_v3_run1.json
  --status-output C:\IsaacSim\evidence\fixed_overview_official_mesh_v3_run1.status.json`;
  `$env:PYTHONPATH=(Resolve-Path 'software/src').Path; python -m pytest
  software/tests/unit/test_isaac_fixed_overview_mesh_render_evidence.py
  software/tests/unit/test_fixed_overview_segmentation_corpus.py
  software/tests/unit/test_fixed_fixture_practice_corpus.py
  software/tests/unit/test_virtual_pixel_vision.py
  software/tests/unit/test_virtual_arm_camera.py software/ai/tests/test_offline.py
  -q`; Ruff, documentation, and `git diff --check` checks.
- Result: PASS_WITH_BLOCKERS. All 21 semantic masks are distinct. Across the
  nine training poses there are 85 center occlusions and 107 target regions
  above the predeclared 0.20 safe-overlap threshold. Across six development
  poses there are 34 center occlusions and 43 threshold crossings. Across six
  untouched evaluation poses there are 77 center occlusions and 92 crossings.
  Per-evaluation-pose center/crossing counts are respectively `13/17`, `14/16`,
  `12/13`, `14/15`, `13/17`, and `11/14`, demonstrating materially varied and
  harder inter-key obstruction geometry.
- Artifact identities: canonical receipt SHA-256
  `ce72cbdd921f3cbcdf81ffe15a1b90eaf8b5749e6df4c8764783fa07a0c89766`;
  receipt file SHA-256
  `1bc26ad7cabf59587f5606e7c834526e76bbaa1b3e2a0a2321af0bbaff167ecc`;
  RGB/mask/depth atlas SHA-256 values respectively
  `07c91a0bb2332801042e10ed290fa794ca3aea64caca3fb33507ee3c03b57d3a`,
  `2e752cfce9c36c4ed659bdf193c9b9eb6f5bada9016e987cfdcb471b86899052`,
  and `75df29523ea008572f69b8cff284e5b140fba2cb4bf6785e99224d49d474a032`.
  Fifty-four focused tests passed in 21.72 seconds; Ruff and documentation
  checks passed.
- Artifact location: external only at
  `C:\IsaacSim\artifacts\issue190\fixed-overview-official-mesh-v3-run1` and
  `C:\IsaacSim\evidence\fixed_overview_official_mesh_v3_run1.json`; hashes
  identify exact local bytes but do not make them clean-clone available.
- Hardware-write count: 0.
- Physical-movement count: 0.
- Physics-step count: 0.
- Limitations: visual meshes, camera, board placement, lighting, and labels are
  synthetic. Measured tool and camera-support geometry, physical frames,
  temporal evidence, and deployment-calibrated uncertainty remain absent.
  This evidence qualifies no localization, collision clearance, controller,
  execution, transport, permit, or physical authority.
- Supersedes: none; preserves AI-459 through AI-461 and provides fresh geometry
  for a subsequent three-way dataset.
- Next dependency: predeclare new disjoint lighting families, materialize the
  21-pose training/development/evaluation dataset, select a spatial candidate
  using training/development only, and score the new evaluation once. Physical
  promotion still requires measured fixed-camera evidence.

### E-20260930-AI-463 — deterministic transit-occlusion dataset

- Stage: S2/S3 synthetic perception and abstention development.
- Lane: AI/model; no arm or integration status changed.
- Implementation commit: `0deb40d7ff208cf2f00086518479df7487b90db6`.
- Change: added a v3 dataset policy for the hash-bound AI-462 source. Training
  uses all nine consumed endpoint poses crossed with all nine consumed lighting
  families. Development uses six fresh outbound/return poses crossed with
  desaturation, dark gamma, and vignette. Evaluation uses six untouched
  inter-key poses crossed with low contrast, right-side shadow, and horizontal
  motion blur. Pose and lighting groups are pairwise disjoint and were committed
  before generation. The evaluation bytes were materialized only for immutable
  identity and leakage checks; no model loaded or scored them.
- Inputs/fixtures: builder SHA-256
  `69e7f2803af2de26ad1f22725f76ecf7643e599b555c2c38c3e4a12c5f804e0c`;
  focused evidence-test SHA-256
  `5cda332b3891814e3c34fc677912890f8ce1958b6e61453c2692084f040ea492`;
  source receipt file SHA-256
  `1bc26ad7cabf59587f5606e7c834526e76bbaa1b3e2a0a2321af0bbaff167ecc`;
  source receipt SHA-256
  `ce72cbdd921f3cbcdf81ffe15a1b90eaf8b5749e6df4c8764783fa07a0c89766`;
  target-catalog SHA-256
  `6779213e832ab27eeda1e7fb245f57ff8cb0d56707b5aa73a8f31ec483a620f2`.
- Commands: `Copy-Item C:\IsaacSim\evidence\fixed_overview_official_mesh_v3_run1.json
  C:\IsaacSim\artifacts\issue190\fixed-overview-official-mesh-v3-run1\manifest.json`;
  `python software/ai/train/build_official_mesh_occlusion_data.py
  --source-manifest C:\IsaacSim\artifacts\issue190\fixed-overview-official-mesh-v3-run1\manifest.json
  --output-dir C:\IsaacSim\artifacts\issue190\official-mesh-transit-occlusion-data-v1`;
  repeated with output `official-mesh-transit-occlusion-data-v2` for byte
  comparison; `$env:PYTHONPATH=(Resolve-Path 'software/src').Path; python -m
  pytest software/tests/unit/test_isaac_fixed_overview_mesh_render_evidence.py
  software/tests/unit/test_fixed_overview_segmentation_corpus.py
  software/tests/unit/test_fixed_fixture_practice_corpus.py
  software/tests/unit/test_virtual_pixel_vision.py
  software/tests/unit/test_virtual_arm_camera.py software/ai/tests/test_offline.py
  -q`; Ruff and `git diff --check`.
- Result: PASS_WITH_BLOCKERS. Two independent builds are byte-identical.
  Dataset SHA-256 is
  `21dfc1a685d2abd322c63bc9eecff6361f9aa39b5c339bde0f3b99bfe7a7e27c`;
  manifest file SHA-256 is
  `bf713aeb6d5bc17afa953024828b6b2da42ba0de8a8cbca154d19e7306a79222`.
  Training contains 6,075 rows with 963 abstentions and 5,112 visible labels,
  JSONL SHA-256
  `384da017be3933682e7f56892a997849c28a9e595a0f3a8d96a42fd4982ab7a3`.
  Development contains 1,350 rows with 129 abstentions and 1,221 visible labels,
  JSONL SHA-256
  `458d94706dbf85b865d019d2f5a6bc4807b807fde512c9443bbc7207d94dd1a9`.
  Reserved evaluation contains 1,350 rows with 276 abstentions and 1,074
  visible labels, JSONL SHA-256
  `22e5392399a082fe7200ce9cb00870afef07b6e8a481c1626ae946ce193561f7`.
  All 117 images have distinct SHA-256 values and total 12,554,138 bytes.
  Fifty-six focused tests passed in 22.32 seconds and Ruff passed. The tracked
  repository remains at exactly 6,100 files.
- Artifact location: external only at
  `C:\IsaacSim\artifacts\issue190\official-mesh-transit-occlusion-data-v1`
  with deterministic repeat `...data-v2`; hashes identify exact local bytes
  but do not make them clean-clone available.
- Hardware-write count: 0.
- Physical-movement count: 0.
- Limitations: every render, transformation, geometry value, and label remains
  synthetic. The dataset lacks measured tool/camera-support geometry, physical
  frames, temporal evidence, and deployment-calibrated uncertainty. Merely
  materializing the evaluation bytes is not model evaluation. This artifact
  establishes no localization, collision clearance, controller, execution,
  transport, permit, or physical authority.
- Supersedes: none; preserves all AI-457 through AI-462 evidence.
- Next dependency: fit spatial candidates on training, select architecture and
  threshold on development only, freeze the checkpoint, and score the reserved
  evaluation once. Physical promotion remains dependent on measured fixed-
  camera evidence under a registered configuration epoch.

### E-20260930-AI-464 — tiny spatial occlusion candidate

- Stage: S2/S3 synthetic perception and abstention development.
- Lane: AI/model; no arm or integration status changed.
- Implementation commit: `fe1d1f28029870f7c264b6313ecbd80b7bb5d51e`.
- Change: added a deterministic CPU-only 1,649-parameter convolutional model
  over 32-by-32 RGB crops with 24-pixel source padding. Its fixed architecture
  is 3→8 convolution/ReLU/max-pool, 8→16 convolution/ReLU, adaptive 4-by-4
  pooling, and a 256→1 linear head. Training uses eight epochs, 128-row batches,
  Adam at 0.002, seed 190, deterministic Torch algorithms, and positive-class
  weighting. The threshold was selected only on AI-463 development with the
  existing preference for at most 0.05 missed abstentions. Architecture,
  weights, and threshold were serialized canonically before evaluation bytes
  were loaded. The reserved evaluation was scored exactly once.
- Inputs/fixtures: implementation SHA-256
  `2ef61da6fe22e03d4b87637a0e421d9e8c0928b42bb149db3f2c0f41fa360cc7`;
  focused evidence-test SHA-256
  `a95cd6e1fead66bea4e16636be2fe645c91e24a26e2af9f608acba5c01df5ea4`;
  dataset SHA-256
  `21dfc1a685d2abd322c63bc9eecff6361f9aa39b5c339bde0f3b99bfe7a7e27c`;
  training/development/evaluation JSONL identities remain exactly those in
  AI-463.
- Command: `python software/ai/train/build_official_mesh_occlusion_data.py
  --source-manifest C:\IsaacSim\artifacts\issue190\fixed-overview-official-mesh-v3-run1\manifest.json
  --output-dir C:\IsaacSim\artifacts\issue190\official-mesh-transit-occlusion-data-v3
  --spatial-output C:\IsaacSim\artifacts\issue190\official-mesh-spatial-candidate-v1`;
  `$env:PYTHONPATH=(Resolve-Path 'software/src').Path; python -m pytest
  software/tests/unit/test_isaac_fixed_overview_mesh_render_evidence.py
  software/tests/unit/test_fixed_overview_segmentation_corpus.py
  software/tests/unit/test_fixed_fixture_practice_corpus.py
  software/tests/unit/test_virtual_pixel_vision.py
  software/tests/unit/test_virtual_arm_camera.py software/ai/tests/test_offline.py
  -q`; Ruff, documentation, source-footprint, and `git diff --check` checks.
- Training result: weighted loss decreased monotonically over eight epochs from
  `1.1415249223277402` to `0.4837107294969598`. Development selected threshold
  `0.35` and produced 124 true abstentions, 1,096 true-visible labels, 125 false
  abstentions, and 5 missed abstentions: missed-abstention rate
  `0.03875968992248062`, accuracy `0.9037037037037037`, balanced accuracy
  `0.9294326038512085`, Brier score `0.08806267391690031`, and calibration
  error `0.2052697585799076`. The declared development safety preference passed.
- Reserved evaluation result: BLOCKED_SYNTHETIC_ONLY. The frozen model produced
  274 true abstentions, 641 true-visible labels, 433 false abstentions, and 2
  missed abstentions: missed-abstention rate `2/276 = 0.007246376811594203`,
  visible-target false-abstention rate `433/1074 = 0.4031657355679702`, accuracy
  `0.6777777777777778`, balanced accuracy `0.7947939438102178`, Brier score
  `0.14953791361640184`, and calibration error `0.24486421483534357`. The low
  miss rate is meaningful safety progress, while the high false-abstention rate
  blocks useful cadence and any promotion.
- Artifact identities: model SHA-256
  `42adeaf6e89f53c868512e51e2d4e288d79ebe9f2a28f52895f4f122dbff8af6`;
  canonical scorecard SHA-256
  `fb1cb5e49334d39976d7154fc55c7007330b350bdbb3a1124f9cf09c1bff6d60`;
  scorecard file SHA-256
  `41195473b27846e9cdfc5d6798662fc679efb2f273dd081cf1e6b79b53e01cdc`.
  Fifty-seven focused tests passed in 21.80 seconds; Ruff, documentation, and
  source-footprint checks passed. The repository remains at 6,100 files.
- Artifact location: external only at
  `C:\IsaacSim\artifacts\issue190\official-mesh-spatial-candidate-v1`; hashes
  identify exact local bytes but do not make them clean-clone available.
- Hardware-write count: 0.
- Physical-movement count: 0.
- Limitations: all data and labels remain synthetic and omit measured tool and
  camera-support geometry, physical frames, temporal evidence, and deployment-
  calibrated uncertainty. Evaluation is consumed and cannot tune the model or
  threshold. The checkpoint emits an offline occlusion probability only and
  has no coordinate, motion, controller, permit, transport, or physical
  authority.
- Supersedes: none; rejects promotion while improving the dangerous error class
  relative to the prior synthetic candidate on a fresh, harder split.
- Next dependency: reserve another unused schedule-pose evaluation group before
  tuning specificity on new development data. Add representative visible
  transit negatives and measured tool/camera-support geometry when available.
  Physical promotion remains dependent on measured fixed-camera evidence under
  a registered configuration epoch.

### E-20260930-AI-465 — fresh visible-transit specificity candidate

- Stage: S2/S3 synthetic perception and abstention development.
- Lane: AI/model with inert Isaac rendering; no arm or integration status
  changed.
- Implementation commit: `f0dbbeec1490a1373bf29b70489f356c3163326f`.
- Change: before rendering or model selection, reserved twelve previously
  unused states from the exact 133-sample actual-emitter schedule. All 21
  previously consumed poses and fifteen previously consumed lighting families
  became training input. Schedule samples 2/4/6 and 124/126/130, crossed with
  soft-neutral, mid-gamma, and left-shadow lighting, formed visible-heavy
  development. Samples 10/13/20 and 114/118/122, crossed with cool-flat,
  top-shadow, and vertical-motion-blur lighting, remained untouched evaluation.
  Pose and lighting groups are pairwise disjoint. The 1,649-parameter spatial
  architecture, eight-epoch training policy, and development-only threshold
  selection remained fixed. Evaluation bytes loaded once after checkpoint and
  threshold freeze.
- Inputs/fixtures: renderer SHA-256
  `35883bccc1814d5ecde06f43602af7a4ec01fd10f6513e6956067d4305a9366d`;
  dataset/model implementation SHA-256
  `f738b0290fac7d7cecef76ecbfc8c6624fd378cbd223a35a157c4848ff15eb24`;
  focused test SHA-256
  `a3249d1ebb6817a8046b7164b4ed2aaf211cfddfc07c64e03099e9a4aa5d48a3`;
  actual-emitter schedule file SHA-256
  `6a59ce143f5527c7a9ced09b08d5515644ea4fb859dd69691e08483eb020ee42`;
  target-catalog SHA-256
  `6779213e832ab27eeda1e7fb245f57ff8cb0d56707b5aa73a8f31ec483a620f2`.
- Commands: `$env:OMNI_KIT_ACCEPT_EULA='YES'; $env:PYTHONPATH=(Resolve-Path
  'software/src').Path; C:\IsaacSim\env_6_1_0\Scripts\python.exe
  software\integrations\isaac_sim\isaac_fixed_overview_mesh_render_probe.py
  --workspace . --upstream-repo C:\IsaacSim\sources\roarm_ws-40dbd84
  --mesh-receipt software\integrations\isaac_sim\evidence\roarm_m3_upstream_link_meshes_20260929.json
  --capsule-manifest software\integrations\isaac_sim\evidence\fixed_overview_segmentation_v1\manifest.json
  --schedule-bundle software\integrations\isaac_sim\evidence\actual_emitter_joint_schedule_bundle_9e5c878_20260929.json
  --output-dir C:\IsaacSim\artifacts\issue190\fixed-overview-official-mesh-v4-run1
  --receipt C:\IsaacSim\evidence\fixed_overview_official_mesh_v4_run1.json
  --status-output C:\IsaacSim\evidence\fixed_overview_official_mesh_v4_run1.status.json`;
  `python software/ai/train/build_official_mesh_occlusion_data.py
  --source-manifest C:\IsaacSim\artifacts\issue190\fixed-overview-official-mesh-v4-run1\manifest.json
  --output-dir C:\IsaacSim\artifacts\issue190\official-mesh-specificity-data-v1
  --spatial-output C:\IsaacSim\artifacts\issue190\official-mesh-specificity-candidate-v1`;
  the same builder command with `v2` output directories for deterministic byte
  comparison; focused pytest, shared boundary pytest, Ruff, documentation,
  repository audit, source-footprint, and `git diff --check` checks.
- Render result: PASS_WITH_BLOCKERS. All 33 official-mesh masks are distinct.
  The 21 training poses contain 196 center occlusions and 242 safe-overlap
  crossings. The visible-heavy six-pose development group contains 13 center
  occlusions and 15 crossings. The six-pose evaluation group contains 32
  center occlusions and 37 crossings. Canonical render receipt SHA-256 is
  `def37772c86853319b27be21f6133fa7750619cb3d8d80d8a3578227d772af35`;
  receipt file SHA-256 is
  `1c734f4cdff14c7cdf07528c80a10e415f43dbcb8fcbbb86bc67400553839c2c`;
  status file SHA-256 is
  `4ea62dcee8013e6fc0d3e4ef56ea5a223887db4ef7254970ec2ee3e3b39e65da`.
  RGB/mask/depth atlas SHA-256 values are respectively
  `c7a2215e42739ba80f0592067e15eb6152eccca4bc5d85f4cf7100fbf9955953`,
  `a5018b9f5edefb4125a1b4a00c126487c0e9f39f23de52b8005da2d851b8f8e6`,
  and `2955540537bf1f447c7b894eca166f511f8f271871d539cde0503dbac6323508`.
- Dataset result: two independent 355-file builds are byte-identical. Each is
  54,200,927 bytes. Dataset SHA-256 is
  `e913da3a300019e1e5b21817e99b5c4319fc13479ef33eaf3df7b9c022e1f444`;
  manifest file SHA-256 is
  `01b35301729bd9718284e638787feed84709daecbf702dbbb71fccdd3061ae6c`.
  Training has 23,625 rows with 3,630 abstentions; development has 1,350
  rows with 45 abstentions; evaluation has 1,350 rows with 111 abstentions.
  Their JSONL SHA-256 values are respectively
  `5b021e2a58e709074dcafa85f9414fd39c1799f076f5d5c15805219e0f5cfc10`,
  `e4acd5f6afec07ac45d1213429de00b5f212a8be699691fdd9eb7defa29a777e`,
  and `0468943b5ee38ebd5ee521e07e9f15828f77cb1811d7bab5530697024e18ec77`.
- Candidate result: BLOCKED_SYNTHETIC_ONLY. Both independent checkpoint and
  scorecard builds are byte-identical. Selected threshold is `0.30`.
  Development records 45 true abstentions, 1,277 true-visible labels, 28 false
  abstentions, and zero missed abstentions: accuracy `0.9792592592592593`,
  balanced accuracy `0.989272030651341`, Brier score
  `0.011989938053770022`, and calibration error `0.02784303200189714`.
  Untouched evaluation records 96 true abstentions, 1,211 true-visible labels,
  28 false abstentions, and 15 missed abstentions: missed-abstention rate
  `15/111 = 0.13513513513513514`, visible-target false-abstention rate
  `28/1239 = 0.022598870056497176`, accuracy `0.9681481481481482`, balanced
  accuracy `0.9211329974041839`, Brier score `0.027426143289465753`, and
  calibration error `0.028454788347913162`. Model SHA-256 is
  `aee2e2136768ea3fb80bf7978902d9013e73c32b7fed31b8285a002f5ea1afdd`;
  canonical scorecard SHA-256 is
  `40887e2162e06cd28cdd1a7fdd7973630ca56be2abdfe84ae6be42311ded038c`;
  scorecard file SHA-256 is
  `e4db3849a5641b6a76b9e5f690ec7e9f9095a6ec49e474d22b03c52e4ce884d1`.
- Validation: 59 focused simulator/perception tests passed in 22.43 seconds;
  70 shared v2 precision, producer, strict-ingress, and conformance tests passed
  in 5.51 seconds. Ruff and maintained-document checks passed. The repository
  audit inspected 6,100 paths and 622.5 MiB with zero unresolved findings and
  14 exact reviewed synthetic fixtures. `git diff --check` passed.
- Artifact location: external only under
  `C:\IsaacSim\artifacts\issue190\fixed-overview-official-mesh-v4-run1`,
  `official-mesh-specificity-data-v1`, `...data-v2`,
  `official-mesh-specificity-candidate-v1`, and `...candidate-v2`; hashes bind
  exact local bytes but do not make them clean-clone available.
- Hardware-write count: 0.
- Physical-movement count: 0.
- Physics-step count: 0.
- Limitations: all geometry, camera, lighting, pixels, and labels remain
  synthetic. Tool and camera-support geometry, physical frames, temporal
  evidence, and deployment-calibrated uncertainty remain absent. The safer
  AI-464 result and more usable AI-465 result are from different consumed
  evaluation domains and do not form an authorized ensemble or threshold.
  This evidence qualifies no localization, collision clearance, controller,
  execution, transport, permit, or physical authority.
- Supersedes: none. AI-464 remains the retained low-miss candidate; AI-465
  demonstrates a reproducible specificity improvement and a safety-recall
  regression on a fresh domain.
- Next dependency: reserve another unused schedule-pose evaluation group before
  any tuning. Use new development only to investigate calibrated two-stage or
  overlap-aware abstention that preserves AI-464-level miss behavior while
  approaching AI-465 specificity. Add measured tool/camera-support geometry
  when available; physical promotion remains dependent on final fixed-camera
  evidence under a registered configuration epoch.

### E-20260930-AI-466 — deterministic simulator progression videos

- Stage: S2/S3 synthetic perception review evidence.
- Lane: AI/model; no arm or integration status changed.
- Implementation commit: `89b8a9cf588bd18d2a5318b25d9d5258c651e4c5`.
- Change: added a deterministic PyAV/libx264 exporter for retained simulator
  evidence. The first H.264 video presents all 33 exact official-mesh source
  poses at two frames per second with green visible and red blocked safe-region
  polygons. The second reconstructs the exact frozen 1,649-parameter AI-465
  checkpoint and presents all 18 held-out pose/lighting images with per-target
  true-visible, true-abstain, false-abstain, and missed-abstain overlays. The
  exporter verifies source, atlas, dataset, image, model, scorecard, and scope
  hashes before encoding and writes a canonical bundle manifest.
- Inputs/fixtures: source manifest file SHA-256
  `1c734f4cdff14c7cdf07528c80a10e415f43dbcb8fcbbb86bc67400553839c2c`;
  canonical source receipt SHA-256
  `def37772c86853319b27be21f6133fa7750619cb3d8d80d8a3578227d772af35`;
  dataset manifest file SHA-256
  `01b35301729bd9718284e638787feed84709daecbf702dbbb71fccdd3061ae6c`;
  canonical dataset SHA-256
  `e913da3a300019e1e5b21817e99b5c4319fc13479ef33eaf3df7b9c022e1f444`;
  model SHA-256
  `aee2e2136768ea3fb80bf7978902d9013e73c32b7fed31b8285a002f5ea1afdd`;
  canonical scorecard SHA-256
  `40887e2162e06cd28cdd1a7fdd7973630ca56be2abdfe84ae6be42311ded038c`;
  exporter source SHA-256
  `ce29399a237313b677cb513c59cd30bae48794594bd6b7cfaa8f467ab8d6fb31`;
  focused test SHA-256
  `bfa8843db7b6a1b63948340de428035c657f77d6d51b7296e3ef0eccae541daa`.
- Exact command: `python software/ai/train/build_official_mesh_occlusion_data.py
  --source-manifest C:\IsaacSim\artifacts\issue190\fixed-overview-official-mesh-v4-run1\manifest.json
  --record-existing C:\IsaacSim\artifacts\issue190\official-mesh-specificity-data-v1
  C:\IsaacSim\artifacts\issue190\official-mesh-specificity-candidate-v1
  C:\IsaacSim\artifacts\issue190\sim-progression-videos-v1`; repeated with
  final output `sim-progression-videos-v2`, followed by SHA-256 comparison,
  PyAV decode inspection, focused pytest, shared boundary pytest, Ruff,
  maintained-document checks, repository audit, source-footprint check, and
  `git diff --check`.
- Result: PASS_WITH_BLOCKERS. Both final exports are byte-identical. Canonical
  bundle SHA-256 is
  `9463f52c80f32bbdcdc2ca6a00a48392fe0d5e3b5c1cb78977efa9bbc6088d7a`;
  manifest file SHA-256 is
  `faa1640e69d60add772d2bb05533d43b7945a26d55e135f6dc132581fce36adb`.
  `official_mesh_pose_progression.mp4` is H.264, 960-by-540, 33 frames,
  2 fps, 16.5 seconds, 263,269 bytes, SHA-256
  `3bb24d91f4145f9eb8fea18062207e9a254d55f694faefa664701f226f1830fe`.
  `occlusion_candidate_evaluation.mp4` is H.264, 960-by-540, 18 frames,
  2 fps, 9.0 seconds, 167,067 bytes, SHA-256
  `0d0ab2f8413f8633fd85342d71dda979a0a2ad66c92e82ea8c825d6a39eacfab`.
  Its outcomes exactly reproduce AI-465: 1,211 true visible, 96 true abstain,
  28 false abstain, and 15 missed abstain at threshold `0.30`.
- Validation: 60 focused simulator/perception tests passed in 22.26 seconds;
  96 shared v2 precision, producer, strict-ingress, shadow-runner, trajectory,
  and conformance tests passed in 6.91 seconds. Ruff, maintained-document,
  AI work-registry, repository-audit, source-footprint, and `git diff --check`
  gates passed. The repository audit inspected 6,100 paths and 622.5 MiB with
  zero unresolved findings and 14 exact reviewed synthetic fixtures.
- Artifact location: external only at
  `C:\IsaacSim\artifacts\issue190\sim-progression-videos-v1`, with byte-
  identical repeat `...videos-v2`. Hashes identify exact local bytes but do not
  make the MP4 files clean-clone available.
- Hardware-write count: 0.
- Physical-movement count: 0.
- Physics-step count: 0; encoding reuses exact retained static frames.
- Limitations: these are presentation videos derived from static synthetic
  renders, not continuous simulator trajectories or screen recordings. H.264
  is lossy; the hash-bound source images, dataset rows, and scorecard remain the
  authoritative numeric evidence. No new evaluation examples were created and
  the recordings should not be admitted to training merely because they are
  videos. Measured camera, tool, support, and physical-domain evidence remain
  absent. The bundle grants no localization, collision, controller, execution,
  transport, permit, or physical authority, and AI-465 remains blocked.
- Supersedes: none; adds a review medium for the retained AI-465 evidence.
- Next dependency: produce the same bundle type for future frozen simulator
  milestones. Add a continuous trajectory recording only after its simulation
  timestep, camera cadence, state binding, and frame-retention rules are
  declared. Physical promotion still requires final fixed-camera evidence
  under a registered configuration epoch.

### E-20260930-AI-467 — interrupted target-aware crop materialization

- Stage: S2/S3 synthetic perception development.
- Lane: AI/model; no arm or integration status changed.
- Implementation commit: `bd59785f06c0714e363dafa7568d68b9ec1b5efb`.
- Change attempted: predeclared twelve unused actual-emitter schedule poses and
  six new lighting families, rendered a 45-pose v5 source, materialized the
  three-way dataset, and began deterministic training of a four-channel RGB
  plus known-safe-region candidate.
- Exact command: `python software/ai/train/build_official_mesh_occlusion_data.py
  --source-manifest C:\IsaacSim\artifacts\issue190\fixed-overview-official-mesh-v5-run1\manifest.json
  --output-dir C:\IsaacSim\artifacts\issue190\official-mesh-target-aware-data-v1
  --target-aware-output C:\IsaacSim\artifacts\issue190\official-mesh-target-aware-candidate-v1`.
- Result: FAILED_INTERRUPTED. Dataset materialization completed with 733 files,
  112,366,840 bytes, and manifest file SHA-256
  `a1010e1a7c7599f60241ffd83610e7c19f52cd67fca102d6f39165d605a6debe`.
  Candidate construction repeatedly reopened one image for every target while
  building the safe-region channel. The run was manually stopped before model
  fitting completed; the candidate directory contains zero files. No metric or
  promotion claim is made from this attempt.
- Hardware-write count: 0.
- Physical-movement count: 0.
- Physics-step count: 0 during dataset/model work; the separately completed
  retained source render also declares zero physics steps.
- Limitations: this is retained failed process evidence. The completed dataset
  bytes are not treated as a completed model result. No controller, permit,
  transport, collision, localization, or physical authority was created.
- Corrective dependency: cache image dimensions per materialized image rather
  than reopening the image for each of its 75 target rows. The correction is
  commit `a40c8b4bcc0502360594910dd2e641ae119656aa` and the failed output remains
  retained rather than overwritten.

### E-20260930-AI-468 — fresh target-aware occlusion candidate

- Stage: S2/S3 synthetic perception and abstention development.
- Lane: AI/model with inert Isaac rendering; no arm or integration status
  changed.
- Implementation commits: predeclared split and model
  `bd59785f06c0714e363dafa7568d68b9ec1b5efb`; image-dimension cache correction
  `a40c8b4bcc0502360594910dd2e641ae119656aa`.
- Change: all 33 previously consumed official-mesh poses and all 21 previously
  consumed lighting families became training-only. Schedule samples
  11/15/19 and 113/117/121 with neutral-low, bottom-shadow, and diagonal-blur
  lighting formed development. Samples 23/27/31 and 115/119/123 with green-
  cast, corner-glare, and horizontal-blur lighting remained untouched
  evaluation. The 1,721-parameter candidate consumes 32-by-32 RGB crops plus a
  fourth binary channel derived from the catalog target safe region. The
  simulator robot mask supplies labels only and is explicitly absent from
  inference input. Eight deterministic CPU epochs and development-only
  threshold selection remain fixed; evaluation loaded once after checkpoint
  serialization.
- Inputs/fixtures: renderer SHA-256
  `e50b6978c2aa2c88169375458a82315c8a6c5698d99c5cc7947c03103bec435b`;
  dataset/model builder SHA-256
  `2e06b8d9d82e2aff8fb55347d6d13523093f958976e8f528ae995475d52d3b3b`;
  focused test SHA-256
  `e27d0782a02e9c3afafbb1f20b4c07823b4d0d6635fda7889cd428e5fc2fe508`;
  schedule file SHA-256
  `6a59ce143f5527c7a9ced09b08d5515644ea4fb859dd69691e08483eb020ee42`;
  target-catalog SHA-256
  `6779213e832ab27eeda1e7fb245f57ff8cb0d56707b5aa73a8f31ec483a620f2`.
- Render command: `$env:OMNI_KIT_ACCEPT_EULA='YES'; $env:PYTHONPATH=(Resolve-Path
  'software/src').Path; C:\IsaacSim\env_6_1_0\Scripts\python.exe
  software\integrations\isaac_sim\isaac_fixed_overview_mesh_render_probe.py
  --workspace . --upstream-repo C:\IsaacSim\sources\roarm_ws-40dbd84
  --mesh-receipt software\integrations\isaac_sim\evidence\roarm_m3_upstream_link_meshes_20260929.json
  --capsule-manifest software\integrations\isaac_sim\evidence\fixed_overview_segmentation_v1\manifest.json
  --schedule-bundle software\integrations\isaac_sim\evidence\actual_emitter_joint_schedule_bundle_9e5c878_20260929.json
  --output-dir C:\IsaacSim\artifacts\issue190\fixed-overview-official-mesh-v5-run1
  --receipt C:\IsaacSim\evidence\fixed_overview_official_mesh_v5_run1.json
  --status-output C:\IsaacSim\evidence\fixed_overview_official_mesh_v5_run1.status.json`.
- Dataset/model command: `python
  software/ai/train/build_official_mesh_occlusion_data.py --source-manifest
  C:\IsaacSim\artifacts\issue190\fixed-overview-official-mesh-v5-run1\manifest.json
  --output-dir C:\IsaacSim\artifacts\issue190\official-mesh-target-aware-data-v1-retry1
  --target-aware-output C:\IsaacSim\artifacts\issue190\official-mesh-target-aware-candidate-v1-retry1`;
  repeated with final `...data-v2` and `...candidate-v2` directories for exact
  byte comparison.
- Render result: PASS_WITH_BLOCKERS. All 45 official-mesh masks are distinct.
  Training contains 241 center occlusions and 294 abstention labels across 33
  poses; development contains 33 center occlusions and 40 abstention labels;
  evaluation contains 44 center occlusions and 55 abstention labels. Canonical
  render receipt SHA-256 is
  `dece049dd226781a7a7d53f5c29056bfc47e83134e6f05da1b5e9d4c59d67c5a`;
  receipt file SHA-256 is
  `a3583b4c9582efa2e4285845892b16dfa4e18cec97231a9d1b7d57de0647d576`;
  status file SHA-256 is
  `48f49d1e410042402969af379433c974970f21bec5e0953c2ede00fc8de0e213`.
  RGB/mask/depth atlas SHA-256 values are respectively
  `40d1db4d30fdb513fa1aa0fa94a5515e874e22d3e689f48ed7831cb361f3ea47`,
  `b041300f649edeaaaf0beff7b5ebfaa3cf71e90b1828c03773549dcfbaf8a911`,
  and `4e3ab545b58d400000041fd7963ff2b0b06bb4a1c4d127bd34a6dbc76d143891`.
- Dataset result: two independent 733-file builds are byte-identical. Each is
  112,366,840 bytes. Dataset SHA-256 is
  `393a6cfdad649efe99d27e62f952d81dbf2d34428ff0c80eeba6f51ab0980767`;
  manifest file SHA-256 is
  `a1010e1a7c7599f60241ffd83610e7c19f52cd67fca102d6f39165d605a6debe`.
  Training has 51,975 rows with 6,174 abstentions; development has 1,350 rows
  with 120 abstentions; evaluation has 1,350 rows with 165 abstentions. Their
  JSONL SHA-256 values are respectively
  `0238f0c36ae66a84bcc79121a04a5297f73c50af55ab5baeaf49b9aab05053fa`,
  `737363083324b6ca5e246153df6a7b7d08cf86ac519c9715c4eedc847bd626e0`,
  and `a44da607ed72ed1dcebdf162b851d15b80775840a3e1f2c4cd0609ad023a6676`.
- Candidate result: BLOCKED_SYNTHETIC_ONLY. Both independent checkpoints and
  scorecards are byte-identical. Weighted loss falls monotonically from
  `0.8524029298348172` to `0.1863514108285702`; development selects threshold
  `0.10`, with 120 true abstentions, 1,196 true-visible labels, 34 false
  abstentions, and zero missed abstentions. Fresh evaluation records 160 true
  abstentions, 1,158 true-visible labels, 27 false abstentions, and 5 missed
  abstentions. Missed-abstention rate is `5/165 = 0.030303030303030304`;
  visible-target false-abstention rate is `27/1185 = 0.02278481012658228`;
  accuracy is `0.9762962962962963`, balanced accuracy
  `0.9734560797851937`, Brier score `0.01932606178893815`, and calibration
  error `0.02123716483410034`. The remaining misses are `APOSTROPHE` and
  `SEMICOLON` at return sample 115 and `SLASH` at return sample 119. Model
  SHA-256 is
  `a986eb4cdd654905893029c54e11d2175910810f3f87dfe029580b97dc385bcb`;
  canonical scorecard SHA-256 is
  `c6edaf88eaef98dfab60470b3b4d97c6c80b429f117a7f39aa927361c1cbd66a`;
  scorecard file SHA-256 is
  `1bfbe3959e89e5825d7eceb028d76ea29e78362e5f6dccb67f0032fa07b53e6d`.
- Validation: 64 focused simulator/perception tests passed in 25.14 seconds;
  96 shared v2 boundary tests passed in 6.84 seconds. The final audit commands
  also include Ruff, maintained-document, AI work-registry, repository-audit,
  source-footprint, and `git diff --check` gates.
- Artifact location: external only under
  `C:\IsaacSim\artifacts\issue190\fixed-overview-official-mesh-v5-run1`,
  `official-mesh-target-aware-data-v1-retry1`,
  `official-mesh-target-aware-candidate-v1-retry1`, and byte-identical
  `...data-v2`/`...candidate-v2`; hashes identify local bytes but do not make
  them clean-clone available.
- Hardware-write count: 0.
- Physical-movement count: 0.
- Physics-step count: 0.
- Limitations: all geometry, pixels, target masks, transformations, and labels
  remain synthetic. The known safe-region channel assumes exact target-map
  alignment; this experiment does not measure behavior under localization or
  placement error. The evaluation is consumed and cannot tune another model.
  Results from different held-out domains provide directional evidence but are
  not a paired proof that every AI-465 failure is corrected. Measured tool,
  camera-support, and physical-camera evidence remain absent. The checkpoint
  emits only an offline occlusion probability and grants no localization,
  collision, controller, execution, transport, permit, or physical authority.
- Supersedes: none. It improves the combined synthetic safety/cadence result on
  a fresh domain while preserving AI-464, AI-465, and failed AI-467 evidence.
- Next dependency: bind a progression-video bundle to this exact four-channel
  checkpoint, then test target-mask perturbation from predeclared localization
  offsets on new development data before reserving another untouched evaluation
  group. Physical promotion still requires final fixed-camera qualification and
  measured installed support/tool geometry.

### E-20260930-AI-469 — target-aware progression video bundle

- Stage: S2/S3 synthetic perception review evidence.
- Lane: AI/model with offline presentation encoding; no arm or integration
  status changed.
- Implementation commit:
  `2eda502f65b2fd38e4d3f8ac8ef34c94e5a02ba4`.
- Change: the deterministic video exporter now loads either the existing
  three-channel spatial checkpoint or the four-channel target-aware checkpoint.
  For the latter it reconstructs the exact RGB plus known-target-safe-region
  input, replays the already consumed evaluation without model selection, and
  emits a v2 bundle manifest that names all four channels and explicitly records
  `simulator_robot_mask_input: false`. The previous v1 path remains supported.
- Inputs/fixtures: source manifest file SHA-256
  `a3583b4c9582efa2e4285845892b16dfa4e18cec97231a9d1b7d57de0647d576`;
  canonical source receipt SHA-256
  `dece049dd226781a7a7d53f5c29056bfc47e83134e6f05da1b5e9d4c59d67c5a`;
  dataset manifest file SHA-256
  `a1010e1a7c7599f60241ffd83610e7c19f52cd67fca102d6f39165d605a6debe`;
  canonical dataset SHA-256
  `393a6cfdad649efe99d27e62f952d81dbf2d34428ff0c80eeba6f51ab0980767`;
  model SHA-256
  `a986eb4cdd654905893029c54e11d2175910810f3f87dfe029580b97dc385bcb`;
  canonical scorecard SHA-256
  `c6edaf88eaef98dfab60470b3b4d97c6c80b429f117a7f39aa927361c1cbd66a`;
  exporter source SHA-256
  `e81d42f7bf6b83c3501750ff488b3a123a04ecc338395f4e31e95ac7165cfc5a`;
  focused test SHA-256
  `303816eece6d9f17ba67be21c0bacf36540a7f4eec8af92bbb5acd6c38d930a9`.
- Exact command: `python software/ai/train/build_official_mesh_occlusion_data.py
  --source-manifest C:\IsaacSim\artifacts\issue190\fixed-overview-official-mesh-v5-run1\manifest.json
  --record-existing C:\IsaacSim\artifacts\issue190\official-mesh-target-aware-data-v1-retry1
  C:\IsaacSim\artifacts\issue190\official-mesh-target-aware-candidate-v1-retry1
  C:\IsaacSim\artifacts\issue190\target-aware-progression-videos-v1`;
  repeated with final output `target-aware-progression-videos-v2`, followed by
  byte comparison, PyAV decode, representative-frame inspection, focused and
  shared pytest, Ruff, maintained-document, AI work-registry,
  repository-health, source-footprint, and `git diff --check` gates.
- Result: PASS_WITH_BLOCKERS. Both exports are byte-identical. Canonical bundle
  SHA-256 is
  `b1b7847072792eaf519d47ee34a22bd3eeb8ee3430d859e03b7761732c885979`;
  manifest file SHA-256 is
  `d7df9ec26f6ab96f1041c9ddac605f5e92ff6d3aa4bf905f70d6f1bfc84b6f07`.
  `official_mesh_pose_progression.mp4` is H.264, 960-by-540, 45 frames,
  2 fps, 22.5 seconds, 341,457 bytes, SHA-256
  `50bff986386c86436bf047ea009bd2a0f289d3aa4836e2eca74e391e24524d02`.
  `occlusion_candidate_evaluation.mp4` is H.264, 960-by-540, 18 frames,
  2 fps, 9.0 seconds, 167,922 bytes, SHA-256
  `ae52e2b560a7681c2f672edc92d0e093cc82d64b1c6ccbb53436c70aced5535f`.
  Its overlays exactly reproduce AI-468 at threshold `0.10`: 160 true
  abstentions, 1,158 true-visible decisions, 27 false abstentions, and 5 missed
  abstentions.
- Validation: 64 focused simulator/perception tests passed in 24.84 seconds;
  101 shared v2 precision, adapter, producer, strict-ingress, shadow-runner,
  trajectory, and conformance tests passed in 11.47 seconds. Ruff,
  maintained-document, AI work-registry, repository-health, source-footprint,
  and `git diff --check` gates passed. Repository health matched policy and the
  source archive remained at 6,100 files and 652,778,946 logical bytes.
- Artifact location: external only at
  `C:\IsaacSim\artifacts\issue190\target-aware-progression-videos-v1`, with
  byte-identical repeat `...videos-v2`. Hashes identify exact local bytes but
  do not make the MP4 files clean-clone available.
- Hardware-write count: 0.
- Physical-movement count: 0.
- Physics-step count: 0; encoding uses retained static images.
- Limitations: these are lossy presentation videos from static synthetic
  frames, not continuous trajectories, new examples, or physical-camera
  evidence. The evaluation was already consumed by AI-468 and cannot be used
  for tuning. The fourth channel assumes exact catalog target alignment and
  has not been perturbed by localization error. Measured camera, support, and
  tool geometry remain absent. The bundle grants no localization, collision,
  controller, execution, transport, permit, or physical authority; AI-468
  remains blocked.
- Supersedes: none; adds a deterministic review medium for AI-468.
- Next dependency: predeclare target-mask offset families on new development
  poses, measure degradation without consuming a new evaluation group, and
  reserve fresh evaluation only after the perturbation policy is frozen.

### E-20260930-AI-470 — development-only target-mask perturbation study

- Stage: S2/S3 synthetic localization-sensitivity evidence.
- Lane: AI/model with inert Isaac rendering and frozen offline inference; no
  arm or integration status changed.
- Implementation commit:
  `c5098efd68dd9a20a83ec9b263b60c370f415960`.
- Change: a v6 renderer campaign predeclares schedule samples 12, 16, 21, 116,
  125, and 129 as fresh development-only arm states. Training and evaluation
  groups are empty. The frozen AI-468 checkpoint is measured at nominal
  alignment and 1, 2, 4, and 8 mm offsets in eight directions. Each offset
  translates the RGB crop and catalog safe-region mask together while keeping
  ground-truth occlusion labels fixed. The nominal 2 px/mm conversion is
  derived from the synthetic 1,000 px focal length and 500 mm target depth.
- Inputs/fixtures: renderer SHA-256
  `ec1ee85d9adbde21324993981fdbacc37b9adb14e99fc9457c50d0b6b01d676f`;
  dataset/study builder SHA-256
  `cbe6d97e3bb6b384fd5e865f63153e7ae95a0304ba2fde552f2887646c7defc5`;
  focused test SHA-256
  `2ffd99d35576c18921d6f2ed1dfa95cd8fd6208ae9be4ad9d97fd45d11312b58`;
  schedule file SHA-256
  `6a59ce143f5527c7a9ced09b08d5515644ea4fb859dd69691e08483eb020ee42`;
  target catalog SHA-256
  `6779213e832ab27eeda1e7fb245f57ff8cb0d56707b5aa73a8f31ec483a620f2`;
  frozen model SHA-256
  `a986eb4cdd654905893029c54e11d2175910810f3f87dfe029580b97dc385bcb`.
- Render command: `$env:OMNI_KIT_ACCEPT_EULA='YES'; $env:PYTHONPATH=(Resolve-Path
  'software/src').Path; C:\IsaacSim\env_6_1_0\Scripts\python.exe
  software\integrations\isaac_sim\isaac_fixed_overview_mesh_render_probe.py
  --workspace . --upstream-repo C:\IsaacSim\sources\roarm_ws-40dbd84
  --mesh-receipt software\integrations\isaac_sim\evidence\roarm_m3_upstream_link_meshes_20260929.json
  --capsule-manifest software\integrations\isaac_sim\evidence\fixed_overview_segmentation_v1\manifest.json
  --schedule-bundle software\integrations\isaac_sim\evidence\actual_emitter_joint_schedule_bundle_9e5c878_20260929.json
  --campaign mask-perturbation-v6
  --output-dir C:\IsaacSim\artifacts\issue190\fixed-overview-mask-perturbation-v6-run1
  --receipt C:\IsaacSim\evidence\fixed_overview_mask_perturbation_v6_run1.json
  --status-output C:\IsaacSim\evidence\fixed_overview_mask_perturbation_v6_run1.status.json`.
- Dataset command: `python
  software/ai/train/build_official_mesh_occlusion_data.py --source-manifest
  C:\IsaacSim\artifacts\issue190\fixed-overview-mask-perturbation-v6-run1\manifest.json
  --output-dir C:\IsaacSim\artifacts\issue190\mask-perturbation-development-data-v1`;
  repeated with final `...data-v2` for byte comparison.
- Study command: `python
  software/ai/train/build_official_mesh_occlusion_data.py --source-manifest
  C:\IsaacSim\artifacts\issue190\fixed-overview-mask-perturbation-v6-run1\manifest.json
  --perturb-existing C:\IsaacSim\artifacts\issue190\mask-perturbation-development-data-v1
  C:\IsaacSim\artifacts\issue190\official-mesh-target-aware-candidate-v1-retry1
  C:\IsaacSim\artifacts\issue190\target-mask-perturbation-study-v1`;
  repeated into `...study-v2` and `...study-v2-retry1`. All three report files
  are byte-identical.
- Render result: PASS_WITH_BLOCKERS. Six pose-distinct official-mesh masks
  contain 32 center occlusions and 36 safe-region overlap crossings. Canonical
  receipt SHA-256 is
  `52d3958341f1d8f8ca610598d10717fcd1188ce0295bbe0a0a5697a8c3505005`;
  manifest file SHA-256 is
  `b9943488381ded4395a01f78980de86f1b7cee1e8a3421902398d198514c78bc`;
  status file SHA-256 is
  `7eacc56b9e4882c8cae1c8f62b650efbbe516f7c671a4b5ad951564975fa566a`.
  RGB/mask/depth atlas SHA-256 values are respectively
  `936da8acdf3da0dbec609cda338d98aae4d3dd235bf1c732c573aa4b628acf2f`,
  `c397f55f75d2c835b831012db337e917e1f84155bc18a14bcaaf0c5771606fc1`,
  and `f6eaf59c33ef3eb6b64457de3d7427d5af7178034b60a8ea5f4d61aca93a8e04`.
- Dataset result: two independent 22-file, 2,711,888-byte builds are
  byte-identical. Dataset SHA-256 is
  `35011f05e5ecbc39d2768dcccfdee052ff90674f5f378c7e18ba3cf0715138b0`;
  manifest file SHA-256 is
  `15d26c3f9ee6b992f00d470985b86d158e19c7eddc0d242e9e9adcd6e939d276`.
  Development has 1,350 rows with 108 abstentions and 1,242 visible labels.
  Train and evaluation each contain zero rows and the canonical empty-file
  SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
- Study result: BLOCKED_SYNTHETIC_ONLY. All three 2,486,710-byte reports are
  byte-identical. Canonical report SHA-256 is
  `58c72ac60e6f8d26f980ad6e9b41ac2ad24c5f9236fd6a534271a77980ff8956`;
  report file SHA-256 is
  `bf6044c26841ba1818545aed15ed858ccedd4d89745501a28d5ef507f0430fee`.
  Nominal alignment records 99 true abstentions, 1,207 true-visible labels,
  35 false abstentions, and 9 missed abstentions: missed rate `9/108 =
  0.08333333333333333` and visible false-stop rate `35/1242 =
  0.02818035426731079`. Across the eight 1 mm directions, missed abstentions
  range from 4 to 9 and false stops from 35 to 62. At 2 mm the ranges are 4–9
  and 32–272; at 4 mm, 0–8 and 44–950; at 8 mm, 0–13 and 56–1,230. The worst
  missed-abstention direction is -8 mm x with 13 misses. The worst false-stop
  direction is +8 mm y with 1,230 false stops and only 12 true-visible
  decisions. Some offsets reducing misses do so by stopping broadly and do not
  establish robustness.
- Validation: 67 focused simulator/perception tests passed in 25.34 seconds;
  101 shared v2 precision, adapter, producer, strict-ingress, shadow-runner,
  trajectory, and conformance tests passed in 11.43 seconds. Final validation
  also includes Ruff, maintained-document, AI work-registry,
  repository-health, source-footprint, and `git diff --check` gates.
- Artifact location: external only under
  `C:\IsaacSim\artifacts\issue190\fixed-overview-mask-perturbation-v6-run1`,
  `mask-perturbation-development-data-v1`, byte-identical `...data-v2`, and
  the three byte-identical `target-mask-perturbation-study-*` directories.
  Hashes identify exact local bytes but do not make them clean-clone available.
- Hardware-write count: 0.
- Physical-movement count: 0.
- Physics-step count: 0.
- Limitations: all camera geometry, images, labels, and offsets are synthetic.
  The px/mm mapping uses nominal geometry and is not a measured physical error
  bound. Development-only rows diagnose sensitivity but cannot qualify or
  compare a tuned successor. There is no evaluation group. Tool and camera-
  support geometry remain absent. The checkpoint and study grant no
  localization, collision, controller, execution, transport, permit, or
  physical authority.
- Supersedes: none; converts AI-468's exact-alignment limitation into measured
  directional synthetic evidence.
- Next dependency: add localization-offset augmentation and an explicit
  uncertainty-to-abstention rule using development data only. Freeze that
  policy before rendering and opening a new untouched evaluation group.

### E-20260930-AI-471 — offset-augmented candidate and uncertainty policy

- Stage: S2/S3 synthetic localization-robustness development.
- Lane: AI/model offline training and development-only policy selection; no
  arm or integration status changed.
- Implementation commit:
  `038f64c1f6d7178c958f42ebfed91a466b457302`.
- Change: each of the 51,975 v5 training rows receives one deterministic
  hash-selected offset from nominal plus every 1 mm and 2 mm direction. The
  same 1,721-parameter four-channel CNN is trained for eight deterministic CPU
  epochs. The frozen model is then scored on all 33 v6 development offsets.
  Policy selection accepts the largest 0, 1, 2, or 4 mm bound only when every
  direction inside it keeps both missed-abstention and visible false-stop rates
  at or below 5%. Uncertainty above the selected bound produces
  `abstain_localization_uncertain`. No evaluation group exists or is opened.
- Inputs/fixtures: implementation SHA-256
  `64ddf1af83a4c259747841a7131c6d7de60ea539b7e518a180c74e3660c853a7`;
  focused test SHA-256
  `8cb4742124008320fc55d86ebd2f1dab13c8708d772bf75749edabc301df3b10`;
  training dataset SHA-256
  `393a6cfdad649efe99d27e62f952d81dbf2d34428ff0c80eeba6f51ab0980767`;
  training manifest file SHA-256
  `a1010e1a7c7599f60241ffd83610e7c19f52cd67fca102d6f39165d605a6debe`;
  development dataset SHA-256
  `35011f05e5ecbc39d2768dcccfdee052ff90674f5f378c7e18ba3cf0715138b0`;
  development manifest file SHA-256
  `15d26c3f9ee6b992f00d470985b86d158e19c7eddc0d242e9e9adcd6e939d276`.
- Exact command: `python
  software/ai/train/build_official_mesh_occlusion_data.py --source-manifest
  C:\IsaacSim\artifacts\issue190\fixed-overview-mask-perturbation-v6-run1\manifest.json
  --train-localization-robust
  C:\IsaacSim\artifacts\issue190\official-mesh-target-aware-data-v1-retry1
  C:\IsaacSim\artifacts\issue190\mask-perturbation-development-data-v1
  C:\IsaacSim\artifacts\issue190\localization-robust-candidate-v1`;
  repeated with final `...candidate-v2`, with stdout redirected to separate
  external receipts.
- Training result: weighted loss falls monotonically from
  `0.8715942066010516` to `0.2215171820912985`. All 17 augmentation offsets
  receive 2,955–3,137 rows. Two independent checkpoints and scorecards are
  byte-identical. Model file SHA-256 is
  `16f1810ee5ad51b8414ea524ad54399a85fcce56a45aa76512c2b81ed56d22e6`;
  canonical scorecard SHA-256 is
  `c61cb0d9bcc59b93337aa1f83a7465814842dfec25e74f824a6231435da766ea`;
  scorecard file SHA-256 is
  `69e9ba90dbc82771add2ee4ba9579b4b32adc1b953d9ffd1bf60858683e11f4d`.
- Development result: BLOCKED_AWAITING_FRESH_EVALUATION, with evaluation still
  unopened. Threshold `0.10` is selected. At nominal alignment the candidate
  records 105 true abstentions, 1,198 true-visible labels, 44 false
  abstentions, and 3 missed abstentions. Missed rate is `3/108 =
  0.027777777777777776`; visible false-stop rate is `44/1242 =
  0.03542673107890499`. Across 1 mm directions, misses range 1–6 and false
  stops 44–61. The +1 mm x/+1 mm y direction has 6 misses, or
  `0.05555555555555555`, so 1 mm fails the safety limit by one case. At 2 mm
  the ranges are 0–6 and 43–187; at 4 mm, 0–5 and 44–720; at 8 mm, 0–9 and
  42–1,053. The largest supported synthetic bound is therefore 0 mm. Any
  nonzero localization uncertainty must abstain.
- Comparison with AI-470: nominal misses improve from 9 to 3 while false stops
  increase from 35 to 44. Offset augmentation creates a valid nominal policy
  and materially improves safety, but does not yet establish useful nonzero
  tolerance.
- Validation: 68 focused simulator/perception tests passed in 24.97 seconds;
  101 shared v2 precision, adapter, producer, strict-ingress, shadow-runner,
  trajectory, and conformance tests passed in 11.47 seconds. Final validation
  also includes Ruff, maintained-document, AI work-registry,
  repository-health, source-footprint, and `git diff --check` gates.
- Artifact location: external only under
  `C:\IsaacSim\artifacts\issue190\localization-robust-candidate-v1`, with
  byte-identical repeat `...candidate-v2`. Hashes identify exact local bytes
  but do not make the checkpoint clean-clone available.
- Hardware-write count: 0.
- Physical-movement count: 0.
- Physics-step count: 0.
- Limitations: training, target geometry, offsets, and development evidence are
  synthetic. The selected 0 mm bound is not a physical calibration and cannot
  support deployment. No fresh evaluation has been rendered or scored. Tool
  and camera-support geometry remain absent. The checkpoint and uncertainty
  policy grant no localization, collision, controller, execution, transport,
  permit, or physical authority.
- Supersedes: none; improves nominal safety relative to AI-470 and adds an
  explicit fail-closed uncertainty policy while preserving all prior evidence.
- Next dependency: improve the worst 1 mm development direction without
  exceeding the 5% false-stop limit, then freeze a nonzero uncertainty bound
  before allocating a fresh untouched evaluation campaign.

### E-20260930-AI-472 — frozen-weight millithreshold policy refreeze

- Stage: S2/S3 synthetic localization-uncertainty policy selection.
- Lane: AI/model offline development-only policy selection; no arm or
  integration status changed.
- Claim commit:
  `d8e6fad5debb16c8dde71ea5d8665f326b28213e`.
- Implementation commit:
  `34aea6d53f980bbf1049f3a22564bf78a89d0241`.
- Change: the frozen E-471 model is rescored on the existing 33 predeclared v6
  offsets using a fixed threshold grid from `0.050` through `0.950` in `0.001`
  increments. The refreeze path verifies the source model and scorecard,
  development-manifest identity, synthetic-only scope, empty training and
  evaluation splits, unopened evaluation state, and zero hardware authority.
  It changes only the decision threshold and uncertainty policy; model state
  values remain identical to E-471. Detailed metrics are materialized only for
  the selected threshold to keep the finer search bounded.
- Inputs/fixtures: implementation SHA-256
  `66d5079f8ed442097f16a44d5113a5319d82c5b448eba8d42b5a71bfc77b2357`;
  focused test SHA-256
  `f40655963f9d424502ae1d3df76503813a955595bdeca733e0b83dcd9e854181`;
  source render manifest file SHA-256
  `b9943488381ded4395a01f78980de86f1b7cee1e8a3421902398d198514c78bc`;
  target catalog SHA-256
  `6779213e832ab27eeda1e7fb245f57ff8cb0d56707b5aa73a8f31ec483a620f2`;
  development dataset SHA-256
  `35011f05e5ecbc39d2768dcccfdee052ff90674f5f378c7e18ba3cf0715138b0`;
  development manifest file SHA-256
  `15d26c3f9ee6b992f00d470985b86d158e19c7eddc0d242e9e9adcd6e939d276`;
  source model file SHA-256
  `16f1810ee5ad51b8414ea524ad54399a85fcce56a45aa76512c2b81ed56d22e6`;
  source canonical scorecard SHA-256
  `c61cb0d9bcc59b93337aa1f83a7465814842dfec25e74f824a6231435da766ea`.
- Exact command: `python
  software/ai/train/build_official_mesh_occlusion_data.py --source-manifest
  C:\IsaacSim\artifacts\issue190\fixed-overview-mask-perturbation-v6-run1\manifest.json
  --refreeze-localization-policy
  C:\IsaacSim\artifacts\issue190\mask-perturbation-development-data-v1
  C:\IsaacSim\artifacts\issue190\localization-robust-candidate-v1
  C:\IsaacSim\artifacts\issue190\localization-policy-refreeze-v1`;
  repeated with final output `...refreeze-v2` and stdout redirected to
  `C:\IsaacSim\artifacts\issue190\localization-policy-refreeze-v2.stdout.json`.
- Result: PASS_WITH_BLOCKERS. The selected threshold is `0.093` and the largest
  supported synthetic planar-error bound is 1 mm. Nominal alignment records
  105 true abstentions, 1,194 true-visible decisions, 48 false abstentions,
  and 3 missed abstentions. Across all eight 1 mm directions, missed
  abstentions range from 1 to 4 and false stops range from 47 to 62. The worst
  missed rate is `4/108 = 0.037037037037037035`; the worst visible false-stop
  rate is `62/1242 = 0.0499194847020934`. The +1 mm x/+1 mm y direction reaches
  the 62-false-stop edge. The 2 mm ring fails with 0–6 misses and 45–207 false
  stops, so uncertainty above 1 mm must produce
  `abstain_localization_uncertain`.
- Reproducibility: both 37,660-byte model files are byte-identical at SHA-256
  `e7b57b6e06edfb2b26972565c02149762c6e9a25ec67718f9d28b1c62dc6af3d`;
  both 2,081,052-byte scorecard files are byte-identical at SHA-256
  `de381870fd0e7d541aa32fd154069c897bb2fc99f9d5c7c8d7b1dd04646d3ae3`;
  canonical scorecard SHA-256 is
  `224f7677f395192f80f9ecbeea816bed232cafb8d5e05cc2855123be044b7b20`.
  The refrozen and source `state_dict` objects compare equal. Evaluation is
  absent and unopened.
- Validation: 69 focused simulator/perception tests passed in 25.30 seconds;
  101 shared v2 precision, adapter, producer, strict-ingress, shadow-runner,
  trajectory, and conformance tests passed in 11.41 seconds. Ruff,
  maintained-document, AI work-registry, repository-health, source-footprint,
  and `git diff --check` gates passed. At arm commit
  `a842e71863dc4c0c8bcf8198567ea25bfc1fb5cf`, the precision-observation v2,
  motion-batch v2, conformance-profile schema, and installed conformance
  profile blobs remain identical to this AI branch.
- Artifact location: external only under
  `C:\IsaacSim\artifacts\issue190\localization-policy-refreeze-v1`, with
  byte-identical repeat `...refreeze-v2`. Hashes identify exact local bytes but
  do not make the checkpoint clean-clone available.
- Hardware-write count: 0.
- Physical-movement count: 0.
- Physics-step count: 0; this increment replays retained synthetic images.
- Limitations: the camera, target geometry, labels, and offsets are synthetic.
  The 1 mm bound is a development result under nominal 2 px/mm geometry, not a
  measured physical-camera calibration or deployment qualification. The
  threshold is selected on the existing v6 development corpus, so that corpus
  cannot evaluate this policy. The 2 mm ring fails. Tool and camera-support
  geometry remain absent. The artifact grants no localization, collision,
  controller, execution, transport, permit, or physical authority.
- Supersedes: none; preserves E-471's coarse-grid failure while correcting the
  policy resolution with unchanged weights.
- Next dependency: predeclare and render a fresh untouched synthetic evaluation
  campaign with new arm poses and lighting, freeze its identity before opening
  it, then score this exact checkpoint once. Physical deployment remains
  separately blocked on final-camera calibration and installed geometry.

### E-20260930-AI-473 — one-time fresh 1 mm policy evaluation

- Stage: S2/S3 synthetic localization-policy evaluation.
- Lane: AI/model with inert Isaac rendering and frozen offline inference; no
  arm or integration status changed.
- Claim commit:
  `fa39a666e752557604057eba6302a8d538f2056a`.
- Implementation commit:
  `657974574191a53583db13cfea1dea79dd6a1a5a`.
- Change: a v7 campaign predeclares actual-emitter schedule samples 40, 48,
  56, 76, 88, and 100 as evaluation-only poses. They are disjoint from all
  prior training, development, and evaluation samples and interleave the
  previously observed H-to-1 and 1-to-period transit poses. Three new
  deterministic lighting families—amber cast, center glare, and anti-diagonal
  motion blur—are evaluation-only. The evaluator accepts only an evaluation-
  only v7 dataset and the exact frozen E-472 1 mm checkpoint, then scores
  nominal plus every 1 mm direction once. It emits a synthetic blocked report
  with no execution authority regardless of the metric result.
- Inputs/fixtures: renderer SHA-256
  `0dff477d8f091926512d52130c6503e92d98bd29c2e0db09190f44ca3fa702c5`;
  dataset/evaluator SHA-256
  `036e076be8979ee9b9d58f84a41234af518de5fb461f5342cb681afb9dcbd802`;
  focused test SHA-256
  `fd777f8b94bd27506f4e4b0bb17a29833257a0deca04959c892025a60392500e`;
  schedule file SHA-256
  `6a59ce143f5527c7a9ced09b08d5515644ea4fb859dd69691e08483eb020ee42`;
  target catalog SHA-256
  `6779213e832ab27eeda1e7fb245f57ff8cb0d56707b5aa73a8f31ec483a620f2`;
  frozen model file SHA-256
  `e7b57b6e06edfb2b26972565c02149762c6e9a25ec67718f9d28b1c62dc6af3d`;
  frozen canonical scorecard SHA-256
  `224f7677f395192f80f9ecbeea816bed232cafb8d5e05cc2855123be044b7b20`.
- Render command: `$env:OMNI_KIT_ACCEPT_EULA='YES'; $env:PYTHONPATH=(Resolve-Path
  'software/src').Path; C:\IsaacSim\env_6_1_0\Scripts\python.exe
  software\integrations\isaac_sim\isaac_fixed_overview_mesh_render_probe.py
  --workspace . --upstream-repo C:\IsaacSim\sources\roarm_ws-40dbd84
  --mesh-receipt software\integrations\isaac_sim\evidence\roarm_m3_upstream_link_meshes_20260929.json
  --capsule-manifest software\integrations\isaac_sim\evidence\fixed_overview_segmentation_v1\manifest.json
  --schedule-bundle software\integrations\isaac_sim\evidence\actual_emitter_joint_schedule_bundle_9e5c878_20260929.json
  --campaign policy-evaluation-v7
  --output-dir C:\IsaacSim\artifacts\issue190\fixed-overview-policy-evaluation-v7-run1
  --receipt C:\IsaacSim\evidence\fixed_overview_policy_evaluation_v7_run1.json
  --status-output C:\IsaacSim\evidence\fixed_overview_policy_evaluation_v7_run1.status.json`.
- Dataset command: `python
  software/ai/train/build_official_mesh_occlusion_data.py --source-manifest
  C:\IsaacSim\artifacts\issue190\fixed-overview-policy-evaluation-v7-run1\manifest.json
  --output-dir
  C:\IsaacSim\artifacts\issue190\localization-policy-evaluation-data-v1`;
  repeated with final `...data-v2` before inference.
- Evaluation command, run once: `python
  software/ai/train/build_official_mesh_occlusion_data.py --source-manifest
  C:\IsaacSim\artifacts\issue190\fixed-overview-policy-evaluation-v7-run1\manifest.json
  --evaluate-localization-policy
  C:\IsaacSim\artifacts\issue190\localization-policy-evaluation-data-v1
  C:\IsaacSim\artifacts\issue190\localization-policy-refreeze-v1
  C:\IsaacSim\artifacts\issue190\localization-policy-evaluation-report-v1`.
- Render result: PASS_WITH_BLOCKERS. Six pose-distinct official-mesh renders
  provide 90 safe-region-overlap abstention labels before lighting expansion.
  Canonical receipt SHA-256 is
  `c8e8a7e152b0c763867ac488838c918a7e073c75c225c3503b92a8f9fc1dd3bf`;
  manifest file SHA-256 is
  `d3cf5f5928d84d3226b7872322716e78590218e7f52ae617c6d66a135ee86095`;
  status file SHA-256 is
  `b90f34b85a8a02304a7fd62aace847e886352f50611019f8059b7573bb0093f1`.
  RGB, mask, and depth atlas SHA-256 values are respectively
  `6fb715b004f96ef3cfe02297edd3e9ff74f662d8e8efb89d0e3c9a5b150ff88b`,
  `bac8ace8bc39ae910732eab386a851a8769774bc4b23cb1d67386a048fc8fc1b`,
  and `72eba5ebf287ecdf7365299f147a67e34734417d30cc582c606367b0c7861433`.
- Dataset result: both independent 22-file, 2,898,387-byte builds are
  byte-identical. Dataset SHA-256 is
  `cc9665f58629ad311cf5d9913bf7ca3f993caf708302182905c78108d300556a`;
  manifest file SHA-256 is
  `b1cc90d3aa415faf822f98860fbc310af0a987b823fb86c04fed4474b166c68f`.
  Training and development each contain zero rows. Evaluation contains 1,350
  rows: 270 abstentions and 1,080 visible labels across 18 distinct images.
- Evaluation result: BLOCKED_SYNTHETIC_ONLY. At frozen threshold `0.093`,
  nominal alignment records 267 true abstentions, 997 true-visible decisions,
  83 false abstentions, and 3 missed abstentions. Across all 1 mm directions,
  misses range from 0 to 3 and false stops range from 82 to 96. The worst
  missed rate is `3/270 = 0.011111111111111112`, within the 5% safety limit;
  the worst visible false-stop rate is `96/1080 = 0.08888888888888889`, above
  the 5% cadence limit. The synthetic gate fails. Nominal false stops are
  already `83/1080 = 0.07685185185185185`. The -1 mm x/-1 mm y direction is
  worst at 96 false stops and one miss.
- Failure concentration: nominal false stops contain 36 center-glare, 29
  amber-cast, and 18 anti-diagonal-blur rows. `ENTER`, `EQUAL`, `MINUS`, and
  `0` account for 57 of 83 nominal false stops. These are observations from a
  consumed split and may define a separate future development campaign but
  may not tune this checkpoint or be reused as evaluation.
- Report identity: canonical report SHA-256 is
  `05a4ccb746ee97f5b55b1aba4d53a83924ec98477bdeb34759ae5589ac8a03c2`;
  the 145,274-byte report file SHA-256 is
  `bd436b5b2554eebfa1b56d8e4f4106b6663501fc796bd520ebad44d35f55c222`.
- Validation: 72 focused simulator/perception tests passed in 25.82 seconds;
  101 shared v2 precision, adapter, producer, strict-ingress, shadow-runner,
  trajectory, and conformance tests passed in 11.49 seconds. Ruff,
  maintained-document, AI work-registry, repository-health, source-footprint,
  and `git diff --check` gates passed. At arm commit
  `a842e71863dc4c0c8bcf8198567ea25bfc1fb5cf`, the precision-observation v2,
  motion-batch v2, conformance-profile schema, and installed conformance
  profile blobs remain identical to this AI branch.
- Artifact location: external only under
  `C:\IsaacSim\artifacts\issue190\fixed-overview-policy-evaluation-v7-run1`,
  `localization-policy-evaluation-data-v1`, byte-identical `...data-v2`, and
  `localization-policy-evaluation-report-v1`. Hashes identify exact local
  bytes but do not make them clean-clone available.
- Hardware-write count: 0.
- Physical-movement count: 0.
- Physics-step count: 0; retained schedule states are rendered statically.
- Limitations: all camera geometry, images, labels, and offsets are synthetic.
  The evaluated 1 mm ring uses nominal 2 px/mm geometry and is not physical
  calibration. The v7 evaluation group is consumed and cannot tune a
  successor. Tool and camera-support geometry remain absent. The failed report
  grants no localization, collision, controller, execution, transport, permit,
  or physical authority.
- Supersedes: none; preserves E-472's development pass and records that its
  visible-target specificity does not generalize to the fresh v7 campaign.
- Next dependency: predeclare a new development-only hard-negative corpus that
  represents the persistent keyboard targets and new lighting families, then
  improve specificity without exceeding the 5% missed-abstention limit. A
  later successor requires another untouched evaluation group; physical
  deployment remains separately blocked on final-camera calibration and
  installed geometry.

### E-20260930-AI-474 — development-only hard-negative diagnostic

- Stage: S2/S3 synthetic target-specificity diagnosis.
- Lane: AI/model with inert Isaac rendering and frozen offline inference; no
  arm or integration status changed.
- Claim commit:
  `39274887d71b3aeb18f62dcb9e50b826cc097366`.
- Implementation commit:
  `9a6f364824ad9cecf1c50a716299f3b85f4acb23`.
- Change: a v8 campaign predeclares unused actual-emitter schedule samples 42,
  50, 58, 78, 90, and 98 as development-only poses. They interleave but do not
  reuse the consumed v7 evaluation samples. Amber low contrast, right-center
  glare, and offset anti-diagonal blur are new deterministic development-only
  transforms related to the consumed failure categories but byte-distinct from
  v7. The diagnostic holds the E-472 model and threshold fixed, scores nominal
  plus every 1 mm direction, and records `selection_performed: false`,
  `training_performed: false`, and `evaluation_group_present: false`.
- Inputs/fixtures: renderer SHA-256
  `2eb9083e4621a373ecbc7129c8af63242304520ef881a3e1f43eb0682b9db918`;
  dataset/diagnostic SHA-256
  `a14260988411d9a82b95175062a390313508792951b88e4b7f27f115cc49b3ac`;
  focused test SHA-256
  `a03d34a65ec58561eff7763c0cea3b7726d767221f24d88ce7cc5d7242c890c5`;
  schedule file SHA-256
  `6a59ce143f5527c7a9ced09b08d5515644ea4fb859dd69691e08483eb020ee42`;
  target catalog SHA-256
  `6779213e832ab27eeda1e7fb245f57ff8cb0d56707b5aa73a8f31ec483a620f2`;
  frozen model file SHA-256
  `e7b57b6e06edfb2b26972565c02149762c6e9a25ec67718f9d28b1c62dc6af3d`.
- Render command: `$env:OMNI_KIT_ACCEPT_EULA='YES'; $env:PYTHONPATH=(Resolve-Path
  'software/src').Path; C:\IsaacSim\env_6_1_0\Scripts\python.exe
  software\integrations\isaac_sim\isaac_fixed_overview_mesh_render_probe.py
  --workspace . --upstream-repo C:\IsaacSim\sources\roarm_ws-40dbd84
  --mesh-receipt software\integrations\isaac_sim\evidence\roarm_m3_upstream_link_meshes_20260929.json
  --capsule-manifest software\integrations\isaac_sim\evidence\fixed_overview_segmentation_v1\manifest.json
  --schedule-bundle software\integrations\isaac_sim\evidence\actual_emitter_joint_schedule_bundle_9e5c878_20260929.json
  --campaign hard-negative-v8
  --output-dir C:\IsaacSim\artifacts\issue190\fixed-overview-hard-negative-v8-run1
  --receipt C:\IsaacSim\evidence\fixed_overview_hard_negative_v8_run1.json
  --status-output C:\IsaacSim\evidence\fixed_overview_hard_negative_v8_run1.status.json`.
- Dataset command: `python
  software/ai/train/build_official_mesh_occlusion_data.py --source-manifest
  C:\IsaacSim\artifacts\issue190\fixed-overview-hard-negative-v8-run1\manifest.json
  --output-dir C:\IsaacSim\artifacts\issue190\hard-negative-development-data-v1`;
  repeated with final `...data-v2` before diagnosis.
- Diagnostic command: `python
  software/ai/train/build_official_mesh_occlusion_data.py --source-manifest
  C:\IsaacSim\artifacts\issue190\fixed-overview-hard-negative-v8-run1\manifest.json
  --diagnose-localization-hard-negatives
  C:\IsaacSim\artifacts\issue190\hard-negative-development-data-v1
  C:\IsaacSim\artifacts\issue190\localization-policy-refreeze-v1
  C:\IsaacSim\artifacts\issue190\hard-negative-diagnostic-v1`;
  repeated with final output `...diagnostic-v2`.
- Render result: PASS_WITH_BLOCKERS. Six official-mesh renders provide 87
  safe-region-overlap abstention labels before lighting expansion. Canonical
  receipt SHA-256 is
  `358979bb9ee62d1a56b4a5bad4f0a5d420ff4e22c1da8667f6c67c49674ef0a2`;
  manifest file SHA-256 is
  `c9a846c31dce4bd5a55281e9e069558eae314906c2bdbda6607d1f94decf89e8`;
  status file SHA-256 is
  `fce7d2382dfb11670b958f1ac15d0b4aad9738d4716bbcb69704f3f9f7ff3798`.
  RGB, mask, and depth atlas SHA-256 values are respectively
  `c1d31ec860d9e358a850b2494e7223dd58f768667245a09246ff115311220fe7`,
  `0270659110006ad77c83fc960326a53a7d2f2b0cb020071083febd20cee55a6f`,
  and `683346da184dd266e44cb4a37b7b4940115c51993d76c0beb55342cf1bdb4bef`.
- Dataset result: both independent 22-file, 2,920,254-byte builds are
  byte-identical. Dataset SHA-256 is
  `21f5643fa556214f34a1ddc20e3f768c74ee68c9af42db9dbcd62ec182597b2d`;
  manifest file SHA-256 is
  `f07dee0da2a755e5db497da69a76b365cc52543d1b5913ed858023ff829389e8`.
  Development contains 1,350 rows: 261 abstentions and 1,089 visible labels.
  Training and evaluation each contain zero rows.
- Diagnostic result: BLOCKED_DEVELOPMENT_ONLY. At frozen threshold `0.093`,
  nominal alignment records 257 true abstentions, 990 true-visible decisions,
  99 false abstentions, and 4 missed abstentions. Across all 1 mm directions,
  misses range from 1 to 5 and false stops range from 93 to 110. The worst
  missed rate is `5/261 = 0.019157088122605363`; the worst false-stop rate is
  `110/1089 = 0.10101010101010101`. The -1 mm x/-1 mm y direction is worst for
  false stops. Low missed-occlusion error reproduces, but specificity remains
  substantially outside the 5% limit.
- Failure concentration: at nominal alignment, amber low contrast contributes
  41 false stops, right-center glare 34, and offset anti-diagonal blur 24.
  `ENTER`, `EQUAL`, and `MINUS` each fail in all 18 development images and
  contribute 48 of 99 false stops. The repeated target pattern supports adding
  explicit target identity or target-geometry features rather than selecting a
  new threshold on these rows.
- Reproducibility: both 172,451-byte diagnostic reports are byte-identical.
  Canonical report SHA-256 is
  `af07d0b289d008b13611cea4eb2d737a77085474546367ad2afe64ec01a1f6da`;
  report file SHA-256 is
  `43db5d20493d0cadff91befaa24bfeebcaed6c74659b6dea30d4be6175c05c57`.
- Validation: 75 focused simulator/perception tests passed in 25.57 seconds;
  101 shared v2 precision, adapter, producer, strict-ingress, shadow-runner,
  trajectory, and conformance tests passed in 11.46 seconds. Ruff,
  maintained-document, AI work-registry, repository-health, source-footprint,
  and `git diff --check` gates passed. At arm commit
  `e34547d76b3ec5fab3b5ca5004bb29c36ef195ab`, the precision-observation v2,
  motion-batch v2, conformance-profile schema, and installed conformance
  profile blobs remain identical to this AI branch.
- Artifact location: external only under
  `C:\IsaacSim\artifacts\issue190\fixed-overview-hard-negative-v8-run1`,
  `hard-negative-development-data-v1`, byte-identical `...data-v2`, and the
  byte-identical `hard-negative-diagnostic-v1` and `...v2` reports. Hashes
  identify exact local bytes but do not make them clean-clone available.
- Hardware-write count: 0.
- Physical-movement count: 0.
- Physics-step count: 0; retained schedule states are rendered statically.
- Limitations: the consumed v7 evaluation informed the class of new
  development transforms, so v8 is selection data and cannot evaluate a
  successor. All camera geometry, images, labels, and offsets are synthetic.
  The 1 mm ring uses nominal 2 px/mm geometry and is not physical calibration.
  Tool and camera-support geometry remain absent. This diagnostic grants no
  localization, collision, controller, execution, transport, permit, or
  physical authority.
- Supersedes: none; preserves the failed v7 evaluation and reproduces its
  specificity problem on new development-only bytes without model changes.
- Next dependency: predeclare separate target-aware training data, add a small
  explicit target identity or geometry representation to the offline model,
  and select the successor against v8 while keeping missed abstentions at or
  below 5%. A later successor requires another untouched evaluation group.

### E-20260930-AI-475 — explicit target-identity candidate fails specificity gate

- Stage: S2/S3 synthetic target-specificity training and development selection.
- Lane: AI/model with inert Isaac rendering and offline inference; no arm or
  integration status changed.
- Claim commit:
  `81b114e5d8cd21b39b9591657e70896c9d487d45`.
- Implementation commit:
  `becab5594cdea1ba8c2f3c88656436f11b297d53`.
- Change: a v9 campaign predeclares actual-emitter schedule samples 41, 43,
  45, 47, 49, 51, 77, 79, 81, 83, 85, and 87 as training-only poses. They are
  disjoint from every prior declared pose. Amber edge boost, right glare dim,
  and anti-diagonal blur contrast are new deterministic training-only lighting
  transforms. The 1,800-parameter candidate retains RGB plus the known target
  safe-region mask and concatenates 75 device-qualified one-hot target values
  plus normalized catalog center x/y and safe-region width/height immediately
  before its classifier. Training uses only v9; threshold and uncertainty
  selection use only the retained v8 development corpus. No evaluation group
  was created or opened.
- Inputs/fixtures: renderer SHA-256
  `6f22fc9e5e5b8fa34481064d9cf7057242be90a9a9487d67d6887813d49c2771`;
  dataset/training implementation SHA-256
  `4113baf38d5aa2eda4ff0a485c901a6f2ea68f8664c0665fdf0d04b383378fc8`;
  focused test SHA-256
  `845cfe6296b78ed66072bdca2e379131a35758c10a75b675709b60e5edf475f0`;
  schedule file SHA-256
  `6a59ce143f5527c7a9ced09b08d5515644ea4fb859dd69691e08483eb020ee42`;
  target catalog SHA-256
  `6779213e832ab27eeda1e7fb245f57ff8cb0d56707b5aa73a8f31ec483a620f2`;
  v8 selection dataset SHA-256
  `21f5643fa556214f34a1ddc20e3f768c74ee68c9af42db9dbcd62ec182597b2d`.
- Render command: `$env:OMNI_KIT_ACCEPT_EULA='YES'; $env:PYTHONPATH=(Resolve-Path
  'software/src').Path; C:\IsaacSim\env_6_1_0\Scripts\python.exe
  software\integrations\isaac_sim\isaac_fixed_overview_mesh_render_probe.py
  --workspace . --upstream-repo C:\IsaacSim\sources\roarm_ws-40dbd84
  --mesh-receipt software\integrations\isaac_sim\evidence\roarm_m3_upstream_link_meshes_20260929.json
  --capsule-manifest software\integrations\isaac_sim\evidence\fixed_overview_segmentation_v1\manifest.json
  --schedule-bundle software\integrations\isaac_sim\evidence\actual_emitter_joint_schedule_bundle_9e5c878_20260929.json
  --campaign target-identity-training-v9 --output-dir
  C:\IsaacSim\artifacts\issue190\fixed-overview-target-identity-training-v9-run1
  --receipt C:\IsaacSim\evidence\fixed_overview_target_identity_training_v9_run1.json
  --status-output
  C:\IsaacSim\evidence\fixed_overview_target_identity_training_v9_run1.status.json`.
- Dataset command: `python
  software/ai/train/build_official_mesh_occlusion_data.py --source-manifest
  C:\IsaacSim\artifacts\issue190\fixed-overview-target-identity-training-v9-run1\manifest.json
  --output-dir C:\IsaacSim\artifacts\issue190\target-identity-training-data-v1`;
  repeated with final `...data-v2`.
- Training command: `python
  software/ai/train/build_official_mesh_occlusion_data.py --source-manifest
  C:\IsaacSim\artifacts\issue190\fixed-overview-target-identity-training-v9-run1\manifest.json
  --train-target-identity
  C:\IsaacSim\artifacts\issue190\target-identity-training-data-v1
  C:\IsaacSim\artifacts\issue190\hard-negative-development-data-v1
  C:\IsaacSim\artifacts\issue190\target-identity-candidate-v1`;
  repeated with final output `...candidate-v2`.
- Render result: PASS_WITH_BLOCKERS. Twelve pose-distinct official-mesh renders
  provide 191 safe-region-overlap abstention labels before lighting expansion.
  Canonical receipt SHA-256 is
  `bb034c897fc4e2042d89d99ff33787c713d6430b29f858d852fe36b796ca68b4`;
  manifest file SHA-256 is
  `448c5012d469b22ce7a051995d73adba48a560b3441cb30803db20d8113fcaaa`;
  status file SHA-256 is
  `2da9fc001126c747b0be1d8e0da67a2a7d973c5968c9a56b35ec4151bf516a70`.
  RGB, mask, and depth atlas SHA-256 values are respectively
  `0527b3f6c24e81c64f4210e439b6c2628477f0eb2c7f5d2db4449ce4786f4cc6`,
  `0f1096e3d7446dcbb689ffc34e235560e0be306ba75374774b287e93278de4c3`,
  and `74d22c36838a00ae61869cdc9e33e2845cb0fa8e3970f4b86e73bc4108da4b04`.
- Dataset result: both independent 40-file, 5,774,498-byte builds are
  byte-identical. Dataset SHA-256 is
  `ac424019f83fe6f46fa3e95e93e5c435dc7fd6fb8e794127bf435eb3c1b2d29d`;
  manifest file SHA-256 is
  `b4872968fdb7f33ee0c610175818d94a5d6a924a8cb1543b39bf39956b0a1023`;
  deterministic directory-content SHA-256 is
  `e8e3fab6320ef22a0e6211906a0f37dcb72f2a811e01e9354bec3b905e34b221`.
  Training contains 2,700 rows: 573 abstentions and 2,127 visible labels.
  Development and evaluation each contain zero rows.
- Candidate result: FAILED_DEVELOPMENT_GATE. Both independent checkpoints and
  scorecards are byte-identical. The 42,507-byte model SHA-256 is
  `276a2caf5c7b678cc484f51eda58587579ece1c264c481b4a2e2c57073a6d26e`.
  Canonical scorecard SHA-256 is
  `01e1a2ff6586f92a25d27ad27cb4c4765570342eea76b8eed14c14f119e6f202`;
  the 2,604,591-byte scorecard file SHA-256 is
  `34dfa8ebb8bc39ea3f53728bd9db84b450ec31e8270b0dcc8ea660f22a7f6e93`.
  At selected threshold `0.25`, nominal alignment records 252 true
  abstentions, 682 true-visible decisions, 407 false abstentions, and 9 missed
  abstentions. Across the 1 mm ring, misses range from 7 to 10 and false stops
  range from 405 to 425. Worst missed rate is `10/261 = 3.83%`; worst false-
  stop rate is `425/1089 = 39.03%`. The selector returns a 0 mm bound and
  `development_gate_met: false`. Nominal false stops concentrate in amber low
  contrast (195), offset anti-diagonal blur (113), and right-center glare (99).
  `ENTER` and `TAB` each false-stop in all 18 nominal images. This is worse
  than the retained E-474 architecture and is not a model improvement.
- Interpretation: the exact target identity is now present, but late
  concatenation after global adaptive pooling acts mainly as a classifier
  bias and loses the local spatial relationship needed to distinguish target
  overlap from visually similar key regions. This rejects this architecture;
  it does not reject target conditioning generally.
- Validation: 34 focused simulator/perception tests passed in 14.37 seconds;
  83 shared v2 precision, adapter, producer, strict-ingress, shadow,
  coordinator, journal, and trajectory-envelope tests passed in 7.44 seconds.
  Ruff, maintained-document, AI work-registry, repository-health,
  source-footprint, and `git diff --check` gates passed. Source footprint is
  6,100 files and 652,914,544 logical bytes. At arm commit
  `9fa8fabf7076623ca17cb855050201739efc9596`, the precision-observation v2,
  motion-batch v2, conformance-profile schema, and installed conformance
  profile blobs remain identical to this AI branch.
- Artifact location: external only under
  `C:\IsaacSim\artifacts\issue190\fixed-overview-target-identity-training-v9-run1`,
  byte-identical `target-identity-training-data-v1` and `...data-v2`, and
  byte-identical `target-identity-candidate-v1` and `...candidate-v2`. Hashes
  identify exact local bytes but do not make them clean-clone available.
- Hardware-write count: 0.
- Physical-movement count: 0.
- Physics-step count: 0; retained schedule states are rendered statically.
- Limitations: all camera geometry, images, labels, target descriptors, and
  offsets are synthetic. The fixed identity vocabulary assumes the exact
  frozen catalog. The 1 mm ring uses nominal 2 px/mm geometry and is not
  physical calibration. V8 remains development/selection data and cannot
  evaluate this or a successor. Tool and camera-support geometry, physical
  frames, temporal evidence, and deployment calibration remain absent. The
  failed candidate grants no localization, collision, controller, execution,
  transport, permit, or physical authority.
- Supersedes: none; preserves E-474 and adds failed evidence for one explicit
  target-identity architecture without consuming a new evaluation group.
- Next dependency: retain v9 for training and v8 for development, then test a
  bounded target-conditioned spatial fusion that applies the target descriptor
  before spatial pooling while preserving the 5% missed-abstention ceiling.
  Only after a candidate passes development may a new untouched evaluation
  campaign be predeclared.

### E-20260930-AI-476 — target-conditioned spatial fusion passes development

- Stage: S2/S3 synthetic target-specificity training and development selection.
- Lane: AI/model with offline inference over retained synthetic images; no arm
  or integration status changed.
- Claim commit:
  `6df5bbc5d6bf560b6c8469f87f8fcca93bf1394f`.
- Implementation commit:
  `e3b06692ec342e8209a1e28b845ac680772909c8`.
- Change: the exact E-472 four-channel visual backbone and classifier are
  frozen. A 79-value descriptor containing 75 device-qualified target entries
  and normalized catalog center x/y and safe-region width/height drives a
  2,560-parameter FiLM conditioner after the second convolution and before
  adaptive spatial pooling. Modulation scale is `0.25`. Only the conditioner
  trains for 20 epochs with Adam, learning rate `0.001`, weight decay `0.0001`,
  and unweighted binary cross entropy. Training uses only v9; threshold and
  uncertainty selection use only v8. No evaluation group was created or opened.
- Inputs/fixtures: implementation SHA-256
  `2d102186278d01dd88720128f7e5fbdb5d67b7e12ace9d8fc86443d89834231a`;
  focused test SHA-256
  `553a95b29ee18ed4697715d1082c66f13ad2ebaa3315cb6e805666f76bed4953`;
  frozen E-472 seed model SHA-256
  `e7b57b6e06edfb2b26972565c02149762c6e9a25ec67718f9d28b1c62dc6af3d`;
  target catalog SHA-256
  `6779213e832ab27eeda1e7fb245f57ff8cb0d56707b5aa73a8f31ec483a620f2`;
  v9 training dataset SHA-256
  `ac424019f83fe6f46fa3e95e93e5c435dc7fd6fb8e794127bf435eb3c1b2d29d`;
  v9 manifest SHA-256
  `b4872968fdb7f33ee0c610175818d94a5d6a924a8cb1543b39bf39956b0a1023`;
  v8 development dataset SHA-256
  `21f5643fa556214f34a1ddc20e3f768c74ee68c9af42db9dbcd62ec182597b2d`;
  v8 manifest SHA-256
  `f07dee0da2a755e5db497da69a76b365cc52543d1b5913ed858023ff829389e8`.
- Exact command: `$train='C:\IsaacSim\artifacts\issue190\target-identity-training-data-v1';
  $dev='C:\IsaacSim\artifacts\issue190\hard-negative-development-data-v1';
  $seed='C:\IsaacSim\artifacts\issue190\localization-policy-refreeze-v1';
  $run1='C:\IsaacSim\artifacts\issue190\target-conditioned-fusion-v1';
  $run2='C:\IsaacSim\artifacts\issue190\target-conditioned-fusion-v2';
  Write-Output "run1_exists=$(Test-Path -LiteralPath $run1) run2_exists=$(Test-Path -LiteralPath $run2)";
  python software\ai\train\build_official_mesh_occlusion_data.py
  --source-manifest C:\IsaacSim\artifacts\issue190\fixed-overview-target-identity-training-v9-run1\manifest.json
  --train-target-conditioned-fusion $train $dev $seed $run1 >
  C:\IsaacSim\artifacts\issue190\target-conditioned-fusion-v1.stdout.json;
  python software\ai\train\build_official_mesh_occlusion_data.py
  --source-manifest C:\IsaacSim\artifacts\issue190\fixed-overview-target-identity-training-v9-run1\manifest.json
  --train-target-conditioned-fusion $train $dev $seed $run2 >
  C:\IsaacSim\artifacts\issue190\target-conditioned-fusion-v2.stdout.json`.
- Result: `BLOCKED_AWAITING_FRESH_EVALUATION` after passing the preregistered
  development gate. Both runs produce byte-identical 95,659-byte models and
  1,416,993-byte scorecards. Model/file SHA-256 is
  `55da91e5a2c14e2c6fb6ebab7c1302e9c1fd5a8cc41644e8f6467ffdcb3c5c74`;
  canonical scorecard SHA-256 is
  `c7cd205140f014673a367591ab18d2b342a2af4ad7f633eec234cae5c0277537`;
  scorecard file SHA-256 is
  `704d5dcd82951867c887a0d0295decf2ca8bdd5da1751bbdcca8ad0fd0ad7ac1`;
  byte-identical stdout SHA-256 is
  `3216b246638eb2ee8655bc56c01f84234cfe1d31c5d3c62c703c92f30fdaa13a`.
  All frozen seed convolution and classifier values match exactly.
- Metrics: selected threshold is `0.107`. Nominal alignment records 258 true
  abstentions, 1,045 true-visible decisions, 44 false abstentions, and 3 missed
  abstentions: false-stop rate `44/1089 = 4.04%`; missed-abstention rate
  `3/261 = 1.15%`. Across all eight 1 mm directions, false stops range from 39
  to 52 and misses range from 3 to 6. Worst rates are
  `52/1089 = 4.78%` at +1 mm x/-1 mm y and `6/261 = 2.30%`. The selector
  returns a 1 mm synthetic planar bound with `development_gate_met: true`.
  At nominal alignment, false stops concentrate in amber low contrast (23),
  right-center glare (11), and offset anti-diagonal blur (10); target `8`
  contributes 8, and `S`, `U`, and `X` contribute 6 each. All three nominal
  misses are target `Q`, one per lighting family.
- Validation: 35 focused simulator/perception tests passed in 15.33 seconds.
  The shared boundary suite passed 83 tests in 7.24 seconds. Ruff passed.
  Maintained-document validation passed across 48 docs, 28 public titles, and
  two SVG assets. The AI work-registry audit passed with 35 tracked and
  documented AI tests, 110 referenced paths, and zero unowned or multiply
  owned tests. Repository-health policy, source-footprint, and
  `git diff --check` gates passed. Source footprint is 6,100 tracked files, 652,946,878
  logical bytes, 4,890,152 duplicate bytes, and a 55,939,877-byte largest blob.
  At arm commit `f8a2c1980a19d890f3d368f5fb9e88978823d9cd`, the
  precision-observation v2, motion-batch v2, conformance-profile schema, and
  installed conformance-profile blobs remain identical to this AI branch.
- Artifact location: external only under
  `C:\IsaacSim\artifacts\issue190\target-conditioned-fusion-v1` and
  byte-identical `...fusion-v2`, plus their byte-identical stdout captures.
  Hashes identify exact local bytes but do not make them clean-clone available.
- Hardware-write count: 0.
- Physical-movement count: 0.
- Physics-step count: 0; this increment trains over retained static renders.
- Limitations: all camera geometry, images, labels, target descriptors, and
  offsets are synthetic. The frozen identity vocabulary assumes the exact
  catalog. The 1 mm ring uses nominal 2 px/mm simulator geometry and is not
  physical calibration. V8 is consumed development/selection data and cannot
  evaluate this candidate. Tool and camera-support geometry, physical frames,
  temporal evidence, and deployment calibration remain absent. Passing this
  development gate grants no localization, collision, controller, execution,
  transport, permit, or physical authority.
- Supersedes: none; preserves the failed E-475 result and demonstrates that
  pre-pool target conditioning succeeds on retained development where late
  descriptor concatenation failed.
- Next dependency: predeclare a new pose- and lighting-disjoint synthetic
  evaluation campaign, freeze its identities before rendering, evaluate this
  exact checkpoint once, and preserve the result whether it passes or fails.
  Physical deployment qualification remains a later, separate requirement.

### E-20260930-AI-477 — frozen fusion checkpoint fails fresh recall gate

- Stage: S2/S3 one-time synthetic evaluation of the frozen E-476 checkpoint.
- Lane: AI/model with inert Isaac rendering and offline inference; no arm or
  integration status changed.
- Claim commit:
  `1b3d5629d3d7461b067c225595ba69c916f30bc1`.
- Implementation and predeclaration commit:
  `4b7fd0ca9198a57671305e7ba34b44f5400f614f`.
- Change: v10 freezes six evaluation-only actual-emitter schedule poses at
  sequences 46, 54, 62, 80, 92, and 102 before rendering. All are absent from
  v1-v9. `blue_edge_shadow`, `lower_left_glare`, and `vertical_blur_dim` are
  deterministic evaluation-only transforms absent from every earlier lighting
  group. The evaluator verifies the dataset, checkpoint, scorecard, target
  catalog, 1 mm policy, and zero-authority fields, then applies the frozen
  threshold to nominal alignment and all eight 1 mm directions. It performs no
  training, threshold selection, relabeling, or model mutation.
- Inputs/fixtures: renderer SHA-256
  `1b15f0633b014fad69cbe29d3e2f8aa67a6e1c57e6388f11f69dce8d573cb6aa`;
  builder/evaluator SHA-256
  `d983f4d9927141a19e165f3916c40d73596eb0b7eb64ae406bb910a6b968a0fd`;
  focused test SHA-256
  `fcaeb360b6df2ac48b7036eec87f6494e36a6832e8f7591c0a8eaeb1e2fe451e`;
  schedule file SHA-256
  `6a59ce143f5527c7a9ced09b08d5515644ea4fb859dd69691e08483eb020ee42`;
  target catalog SHA-256
  `6779213e832ab27eeda1e7fb245f57ff8cb0d56707b5aa73a8f31ec483a620f2`;
  frozen E-476 model SHA-256
  `55da91e5a2c14e2c6fb6ebab7c1302e9c1fd5a8cc41644e8f6467ffdcb3c5c74`.
- Render command: `$env:OMNI_KIT_ACCEPT_EULA='YES';
  $env:PYTHONPATH=(Resolve-Path 'software/src').Path;
  C:\IsaacSim\env_6_1_0\Scripts\python.exe
  software\integrations\isaac_sim\isaac_fixed_overview_mesh_render_probe.py
  --workspace . --upstream-repo C:\IsaacSim\sources\roarm_ws-40dbd84
  --mesh-receipt software\integrations\isaac_sim\evidence\roarm_m3_upstream_link_meshes_20260929.json
  --capsule-manifest software\integrations\isaac_sim\evidence\fixed_overview_segmentation_v1\manifest.json
  --schedule-bundle software\integrations\isaac_sim\evidence\actual_emitter_joint_schedule_bundle_9e5c878_20260929.json
  --campaign fusion-evaluation-v10 --output-dir
  C:\IsaacSim\artifacts\issue190\fixed-overview-fusion-evaluation-v10-run1
  --receipt C:\IsaacSim\evidence\fixed_overview_fusion_evaluation_v10_run1.json
  --status-output
  C:\IsaacSim\evidence\fixed_overview_fusion_evaluation_v10_run1.status.json`.
- Dataset command: `Copy-Item -LiteralPath
  C:\IsaacSim\evidence\fixed_overview_fusion_evaluation_v10_run1.json
  -Destination
  C:\IsaacSim\artifacts\issue190\fixed-overview-fusion-evaluation-v10-run1\manifest.json;
  python software\ai\train\build_official_mesh_occlusion_data.py
  --source-manifest
  C:\IsaacSim\artifacts\issue190\fixed-overview-fusion-evaluation-v10-run1\manifest.json
  --output-dir C:\IsaacSim\artifacts\issue190\fusion-evaluation-data-v1`;
  repeated with final output `...data-v2`.
- Evaluation command: `$data='C:\IsaacSim\artifacts\issue190\fusion-evaluation-data-v1';
  $candidate='C:\IsaacSim\artifacts\issue190\target-conditioned-fusion-v1';
  python software\ai\train\build_official_mesh_occlusion_data.py
  --source-manifest
  C:\IsaacSim\artifacts\issue190\fixed-overview-fusion-evaluation-v10-run1\manifest.json
  --evaluate-target-conditioned-fusion $data $candidate
  C:\IsaacSim\artifacts\issue190\fusion-evaluation-report-v1 >
  C:\IsaacSim\artifacts\issue190\fusion-evaluation-report-v1.stdout.json`;
  repeated with final report and stdout suffix `v2`.
- Render result: `PASS_WITH_BLOCKERS`. Canonical receipt SHA-256 is
  `3320501484816252b49ae15dbf645cebd611f160846737a4100b781a01a10f06`;
  225,162-byte manifest file SHA-256 is
  `f581416316d5f98fafa328f3052a519ee408c536ba4b9700a7eb7b1c08e7cc5e`;
  status file SHA-256 is
  `0d3f62d8f28b7cefc45a39bbc6bf7edf81a3c153047b892e455169b93e69b1a1`.
  RGB, mask, and depth atlas SHA-256 values are respectively
  `8b8e9019f49c11214b70fe98d107e8727636ca651183d3d70734e3309dd57e9b`,
  `953a52138c06bc0f792a7c6fc844e328fe05f0b7894c21b3f609272a664548d3`,
  and `27df1c65ce2332c6e4eb910be05650443f1a503d076ae11a6204e3a467acd341`.
- Dataset result: both independent 22-file, 2,948,327-byte builds are
  byte-identical. Dataset SHA-256 is
  `a60568c213fc64c62e1ee831bffc1a4f46475113c1c6f913adf994e325a9fca3`;
  manifest file SHA-256 is
  `7c1ea9d10a53118d0e93d86505be3e6fcb4c6c4cc3b5573ba809996274b18ee6`;
  deterministic directory-content SHA-256 is
  `5c6bbd05ab5ba781b35a11aaad8bb35b09e796d4b5748d0116d1ca1a40635058`.
  Evaluation contains 1,350 rows: 249 abstentions and 1,101 visible labels.
  Training and development each contain zero rows.
- Evaluation result: `FAILED_SYNTHETIC_GATE`. Both independent 83,540-byte
  reports are byte-identical. Canonical report SHA-256 is
  `5a6d5e4074447b33811c1a868ad7f5da55ea88690eca3f380ef35b70e4d7f21c`;
  report file SHA-256 is
  `3a2f53ebc6e6b65b65810f7ee4860ff79f5f0213f143e92dbc233329b97e45c2`;
  byte-identical stdout SHA-256 is
  `1c7c8f618a6eb9379c2a136cc867fea7b8e111249656fffdf91aefdbc5d3d7be`.
  At frozen threshold `0.107`, nominal alignment records 237 true abstentions,
  1,073 true-visible decisions, 28 false abstentions, and 12 missed abstentions.
  Nominal rates are `28/1101 = 2.54%` false stops and `12/249 = 4.82%` misses.
  Across the 1 mm ring, false stops range from 24 to 50 and misses range from 5
  to 15. Worst false-stop rate is `50/1101 = 4.54%` at +1 mm x/-1 mm y. Worst
  missed-abstention rate is `15/249 = 6.02%` at -1 mm x/0 mm y, so the fixed
  5% gate fails.
- Failure concentration: the 15 worst-direction misses contain `D` four times,
  `PERIOD` and `L` three times each, `Q` and `X` twice each, and `TAB` once.
  Eight occur at pose `fusion_eval_h_to_1_62`; the lighting split is six each
  for blue-edge shadow and lower-left glare, plus three for vertical blur dim.
  Nominal misses are 12, led by `D` four times and `L` three times. Specificity
  is retained: even the worst false-stop direction remains below 5%.
- Validation: 37 focused simulator/perception tests passed in 15.89 seconds.
  The shared boundary suite passed 83 tests in 7.21 seconds. Ruff passed.
  Maintained-document validation passed across 48 docs, 28 public titles, and
  two SVG assets. The AI work-registry audit passed with 35 tracked and
  documented AI tests, 110 referenced paths, and zero unowned or multiply
  owned tests. Repository-health policy, source-footprint, and
  `git diff --check` gates passed. Source footprint is 6,100 tracked files,
  652,974,944 logical bytes, 4,890,152 duplicate bytes, and a 55,939,877-byte
  largest blob. At arm commit
  `943dd06ee2e732e02f68decbb27abe704b23ce00`, the precision-observation v2,
  motion-batch v2, conformance-profile schema, and installed profile blobs are
  byte-identical to this AI branch.
- Artifact location: external only under
  `C:\IsaacSim\artifacts\issue190\fixed-overview-fusion-evaluation-v10-run1`,
  byte-identical `fusion-evaluation-data-v1` and `...data-v2`, and byte-identical
  `fusion-evaluation-report-v1` and `...report-v2`. Hashes identify exact local
  bytes but do not make them clean-clone available.
- Hardware-write count: 0.
- Physical-movement count: 0.
- Physics-step count: 0; schedule states are rendered statically.
- Limitations: all camera geometry, images, labels, target descriptors, and
  offsets are synthetic. The 1 mm ring uses nominal 2 px/mm simulator geometry
  and is not physical calibration. V10 is now consumed evaluation evidence and
  cannot tune a successor. Tool and camera-support geometry, physical frames,
  temporal evidence, and deployment calibration remain absent. This failed
  evaluation grants no localization, collision, controller, execution,
  transport, permit, or physical authority.
- Supersedes: none; preserves E-476's passing development result and adds the
  required fresh failed evaluation without rewriting or tuning either result.
- Next dependency: declare new training and development poses and lighting for
  an occlusion-recall candidate, retaining the target-conditioned pre-pool
  specificity mechanism. Do not reuse v10 images, labels, probabilities, or
  failures for selection. A successor requires another untouched evaluation.

### E-20261001-AI-478 — occlusion-recall successor passes nominal development

- Stage: S2/S3 synthetic recall training and development selection.
- Lane: AI/model with inert Isaac rendering and offline training; no arm or
  integration status changed.
- Claim commit:
  `f25ca76bf31eb2effdf951e821e05dbe39a40d7a`.
- Implementation and predeclaration commit:
  `1545b0b9af65b06ee0c2b77c66ccbf1305d3a9a8`.
- Corrected pose declaration commit:
  `b5ec2d687d3e626d63e56ff313229609b6d64fcd`.
- Change: v11 reserves twelve training and six development schedule states
  absent from v1-v10, and contains no evaluation group. Three train-only and
  three development-only deterministic lighting transforms are absent from all
  previous campaigns. The exact E-476 checkpoint seeds the successor. Both
  visual convolutions and the classifier remain frozen; only the pre-pool FiLM
  conditioner trains for 12 epochs with Adam, learning rate `0.0005`, weight
  decay `0.0001`, and a fixed positive abstention weight of `1.5`. Threshold
  and uncertainty selection use v11 development only. Consumed v10 evaluation
  bytes are excluded and `consumed_evaluation_dataset_sha256` remains null.
- Preserved failed evidence: the first frozen render used schedule samples 36,
  37, and 39, whose joint states are identical. It failed closed with
  `official mesh semantic masks are not pose-distinct`, wrote no receipt or
  admissible dataset, and recorded status-file SHA-256
  `7e09cfc4626774afd78ae160eed61ea30be1c91fe58ac7fcdcde09579231a3ec`.
  The correction replaced only duplicate development samples 37 and 39 with
  previously unused H-transit samples 30 and 32 and rendered to a new output
  directory. The failed output remains preserved.
- Inputs/fixtures: renderer SHA-256
  `c468e323dd2b230d7728c4479ef8edd4b79d0620eeb728a5b13e9afdc838e3cd`;
  builder/trainer SHA-256
  `53fef0738be57c08726db02f5765336248de5a2ea07869d12d786f6198a80f8d`;
  focused test SHA-256
  `b8d858f56187e883fda89344b42ff9f6c1d766294a738b4e0b9fb8b36b319aac`;
  schedule file SHA-256
  `6a59ce143f5527c7a9ced09b08d5515644ea4fb859dd69691e08483eb020ee42`;
  target catalog SHA-256
  `6779213e832ab27eeda1e7fb245f57ff8cb0d56707b5aa73a8f31ec483a620f2`;
  E-476 seed model SHA-256
  `55da91e5a2c14e2c6fb6ebab7c1302e9c1fd5a8cc41644e8f6467ffdcb3c5c74`.
- Corrected render command: `$env:OMNI_KIT_ACCEPT_EULA='YES';
  $env:PYTHONPATH=(Resolve-Path 'software/src').Path;
  C:\IsaacSim\env_6_1_0\Scripts\python.exe
  software\integrations\isaac_sim\isaac_fixed_overview_mesh_render_probe.py
  --workspace . --upstream-repo C:\IsaacSim\sources\roarm_ws-40dbd84
  --mesh-receipt software\integrations\isaac_sim\evidence\roarm_m3_upstream_link_meshes_20260929.json
  --capsule-manifest software\integrations\isaac_sim\evidence\fixed_overview_segmentation_v1\manifest.json
  --schedule-bundle software\integrations\isaac_sim\evidence\actual_emitter_joint_schedule_bundle_9e5c878_20260929.json
  --campaign occlusion-recall-v11 --output-dir
  C:\IsaacSim\artifacts\issue190\fixed-overview-occlusion-recall-v11-run2
  --receipt C:\IsaacSim\evidence\fixed_overview_occlusion_recall_v11_run2.json
  --status-output
  C:\IsaacSim\evidence\fixed_overview_occlusion_recall_v11_run2.status.json`.
- Dataset command: `Copy-Item -LiteralPath
  C:\IsaacSim\evidence\fixed_overview_occlusion_recall_v11_run2.json
  -Destination
  C:\IsaacSim\artifacts\issue190\fixed-overview-occlusion-recall-v11-run2\manifest.json;
  python software\ai\train\build_official_mesh_occlusion_data.py
  --source-manifest
  C:\IsaacSim\artifacts\issue190\fixed-overview-occlusion-recall-v11-run2\manifest.json
  --output-dir C:\IsaacSim\artifacts\issue190\occlusion-recall-data-v1`;
  repeated with final output `...data-v2`.
- Training command: `python
  software\ai\train\build_official_mesh_occlusion_data.py --source-manifest
  C:\IsaacSim\artifacts\issue190\fixed-overview-occlusion-recall-v11-run2\manifest.json
  --train-occlusion-recall
  C:\IsaacSim\artifacts\issue190\occlusion-recall-data-v1
  C:\IsaacSim\artifacts\issue190\target-conditioned-fusion-v1
  C:\IsaacSim\artifacts\issue190\occlusion-recall-candidate-v1`;
  repeated with dataset and candidate suffix `v2`.
- Render result: `PASS_WITH_BLOCKERS`. The 18 distinct states comprise 12
  training and six development poses; evaluation has zero. Canonical receipt
  SHA-256 is
  `4ebac2b69bdb03121359ff9cf592ca86be15adb57c14a0041a75c3ce61bc4fdf`;
  receipt file SHA-256 is
  `7716c76895ec9d9a0719beabf1fa1565af0cc372339d4847e8ca2883dfea4aaf`;
  status file SHA-256 is
  `42e067ea3050b10a24f01424ef61e83fa6aa3dc93ce945d909f575cafaea15a8`.
  RGB, mask, and depth atlas SHA-256 values are respectively
  `e73ebbad9158222e43c2f7ab523c67cae4ddc674770ef02a530c8054de5290b2`,
  `886e2b658e310ef14166402b2e8ad4a00e29a12cd2b941f92f14a6ce84c651c4`,
  and `e12b4c7594870b7fb3f948294bbeabf9f0a14538f36c5a41be8c1638baaad819`.
- Dataset result: both independent 58-file builds are byte-identical. Dataset
  SHA-256 is
  `5c99f7638b87eadc359e267de7a5d2e5a37dd43598b39fe415c46a4219eb817f`;
  manifest file SHA-256 is
  `1aaee7460e968eb72baa08f5ef9b7f5b5b9d6b2014bb0b779ac6befc573dc0fd`;
  directory-content SHA-256 is
  `0612376e48636ba605b07944a69c3e3b6a0eb923cf6f02b68348c35e763c64bd`.
  Training contains 2,700 rows: 501 abstentions and 2,199 visible targets.
  Development contains 1,350 rows: 246 abstentions and 1,104 visible targets.
  Evaluation contains zero rows.
- Training result: `BLOCKED_AWAITING_FRESH_EVALUATION` after passing nominal
  development. Both runs produce byte-identical 95,658-byte models and
  1,524,008-byte scorecards. Model/file SHA-256 is
  `27c7be58e11f8bf3341cb4eb56abdf7786d984e2664b6eb07d6349243730e09c`;
  canonical scorecard SHA-256 is
  `807928f2559d14fa8b0b9da1781d379650deeadb40ec8690e41484be16eaa0d4`;
  scorecard file SHA-256 is
  `5aa9aa4f7bf826b54d1337bdcb1d00601ea76c3333469354062740ce238cbbc2`.
  All frozen convolution and classifier values match E-476 exactly.
- Metrics: selected threshold is `0.162`. Nominal alignment records 235 true
  abstentions, 1,073 true-visible decisions, 31 false abstentions, and 11
  missed abstentions: false-stop rate `31/1104 = 2.81%` and missed-abstention
  rate `11/246 = 4.47%`. Seven of eight 1 mm directions keep both rates below
  5%; +1 mm x/0 mm y records `13/246 = 5.28%` misses. Worst 1 mm false-stop
  rate is `48/1104 = 4.35%` at +1 mm x/-1 mm y. The selector therefore returns
  a 0 mm synthetic planar bound with `development_gate_met: true`.
- Validation: 39 focused simulator/perception tests passed in 16.02 seconds.
  The shared AI-to-arm boundary selection passed 59 tests in 3.82 seconds.
  Ruff passed. Maintained-document validation passed across 48 docs, 28 public
  titles, and two SVG assets. Public-record, evidence-scope, repository-artifact,
  repository-health, release-integrity, and release-readiness checks passed.
  Source footprint is 6,100 tracked files, 653,007,891 logical bytes, 4,890,152
  duplicate bytes, and remains within policy. The AI work-registry audit passed
  with 35 tracked and documented tests, 110 referenced paths, and zero unowned
  or multiply owned tests. `git diff --check` passed. At `origin/main`
  `0c6bea062bcf2baebe232efcf1063a392192fb9d`, precision-observation v2,
  motion-batch v2, conformance-profile schema, and installed profile blobs are
  byte-identical to this AI branch.
- Artifact location: external only under
  `C:\IsaacSim\artifacts\issue190\fixed-overview-occlusion-recall-v11-run2`,
  byte-identical `occlusion-recall-data-v1` and `...data-v2`, and byte-identical
  `occlusion-recall-candidate-v1` and `...candidate-v2`. Hashes identify exact
  local bytes but do not make them clean-clone available.
- Hardware-write count: 0.
- Physical-movement count: 0.
- Physics-step count: 0; schedule states are rendered statically and training
  uses retained images offline.
- Limitations: all camera geometry, images, labels, target descriptors, and
  offsets are synthetic. The 0 mm bound is synthetic development evidence and
  is not physical calibration. V11 has selected this checkpoint and cannot
  evaluate it. V10 remains consumed and was not reused. Tool and camera-support
  geometry, physical frames, temporal evidence, and deployment calibration
  remain absent. Passing nominal development grants no localization,
  collision, controller, execution, transport, permit, or physical authority.
- Supersedes: none; preserves E-476 and the failed E-477 evaluation, and adds a
  separately trained recall successor without rewriting either result.
- Next dependency: predeclare a new pose- and lighting-disjoint evaluation-only
  campaign, freeze its identities before rendering, and evaluate this exact
  checkpoint once. Preserve the outcome whether it passes or fails. Physical
  deployment qualification remains a separate later requirement.

### E-20261001-AI-479 — frozen recall checkpoint narrowly fails specificity

- Stage: S2/S3 one-time synthetic evaluation of the frozen E-478 checkpoint.
- Lane: AI/model with inert Isaac rendering and offline inference; no arm or
  integration status changed.
- Claim commit:
  `8f82376cc9176db99c0f8cd8a1dba3757ee7df0e`.
- Implementation and predeclaration commit:
  `838b165eea0ebf36d3681f0b875e134d3b448d51`.
- Change: v12 freezes six evaluation-only actual-emitter schedule poses at
  sequences 73, 82, 91, 99, 105, and 110, all absent from v1-v11.
  `upper_left_soft_vignette`, `warm_center_bloom`, and `diagonal_smear_cool`
  are deterministic evaluation-only transforms absent from every earlier
  lighting group. The evaluator admits only the exact E-478 model and
  scorecard hashes, preserves threshold `0.162`, gates nominal alignment at
  the checkpoint's declared 0 mm bound, and reports the eight 1 mm directions
  only as non-selecting stress evidence. It performs no training, threshold
  selection, relabeling, policy expansion, or model mutation.
- Inputs/fixtures: renderer SHA-256
  `f8fa72b4a8a13c64e0b5589753e615870f9a5e80c0e1b8f21db08165e4cf3325`;
  builder/evaluator SHA-256
  `e8dcc1c5c3256974a4ddfdb65704a61b9bc6d83da8cdf1191b135e3e90a1d861`;
  focused test SHA-256
  `7c4776169c00bffbba6fbc3ef9d8c62336435428a1f97fe3a7c75c9fe6ab719a`;
  schedule file SHA-256
  `6a59ce143f5527c7a9ced09b08d5515644ea4fb859dd69691e08483eb020ee42`;
  target catalog SHA-256
  `6779213e832ab27eeda1e7fb245f57ff8cb0d56707b5aa73a8f31ec483a620f2`;
  frozen E-478 model SHA-256
  `27c7be58e11f8bf3341cb4eb56abdf7786d984e2664b6eb07d6349243730e09c`;
  frozen E-478 canonical scorecard SHA-256
  `807928f2559d14fa8b0b9da1781d379650deeadb40ec8690e41484be16eaa0d4`.
- Render command: `$env:OMNI_KIT_ACCEPT_EULA='YES';
  $env:PYTHONPATH=(Resolve-Path 'software/src').Path;
  C:\IsaacSim\env_6_1_0\Scripts\python.exe
  software\integrations\isaac_sim\isaac_fixed_overview_mesh_render_probe.py
  --workspace . --upstream-repo C:\IsaacSim\sources\roarm_ws-40dbd84
  --mesh-receipt software\integrations\isaac_sim\evidence\roarm_m3_upstream_link_meshes_20260929.json
  --capsule-manifest software\integrations\isaac_sim\evidence\fixed_overview_segmentation_v1\manifest.json
  --schedule-bundle software\integrations\isaac_sim\evidence\actual_emitter_joint_schedule_bundle_9e5c878_20260929.json
  --campaign recall-evaluation-v12 --output-dir
  C:\IsaacSim\artifacts\issue190\fixed-overview-recall-evaluation-v12-run1
  --receipt C:\IsaacSim\evidence\fixed_overview_recall_evaluation_v12_run1.json
  --status-output
  C:\IsaacSim\evidence\fixed_overview_recall_evaluation_v12_run1.status.json`.
- Dataset command: `Copy-Item -LiteralPath
  C:\IsaacSim\evidence\fixed_overview_recall_evaluation_v12_run1.json
  -Destination
  C:\IsaacSim\artifacts\issue190\fixed-overview-recall-evaluation-v12-run1\manifest.json;
  python software\ai\train\build_official_mesh_occlusion_data.py
  --source-manifest
  C:\IsaacSim\artifacts\issue190\fixed-overview-recall-evaluation-v12-run1\manifest.json
  --output-dir C:\IsaacSim\artifacts\issue190\recall-evaluation-data-v1`;
  repeated with final output `...data-v2`.
- Evaluation command: `python
  software\ai\train\build_official_mesh_occlusion_data.py --source-manifest
  C:\IsaacSim\artifacts\issue190\fixed-overview-recall-evaluation-v12-run1\manifest.json
  --evaluate-occlusion-recall
  C:\IsaacSim\artifacts\issue190\recall-evaluation-data-v1
  C:\IsaacSim\artifacts\issue190\occlusion-recall-candidate-v1
  C:\IsaacSim\artifacts\issue190\recall-evaluation-report-v1 >
  C:\IsaacSim\artifacts\issue190\recall-evaluation-report-v1.stdout.json`;
  repeated with dataset, report, and stdout suffix `v2`.
- Render result: `PASS_WITH_BLOCKERS`. Canonical receipt SHA-256 is
  `df4d320b58efaea287b88ef5af563b4181dfd37c4589eece5a93b4f6b468144e`;
  receipt file SHA-256 is
  `5ee827b556603d512aab3830e702b61461ae452d6b435e6dd6d693a2d40ac79b`;
  status file SHA-256 is
  `40cf85b4e2931e01c2855e8f03742e5ceb188d36dba6b420218e05dbb08245a2`.
  RGB, mask, and depth atlas SHA-256 values are respectively
  `fc6403c546fe2ca154e7fe2c6cc19dcdeea8ca27e17596f565169c548e614328`,
  `1d3575abc92b12c2a3f48b7419dde99a7477120d53465e136babcb318dfeb6c9`,
  and `fe01bac42cc958e937ee75925846fad447dc9fa5799c22a3206c5056f33f7780`.
- Dataset result: both independent 22-file builds are byte-identical. Dataset
  SHA-256 is
  `9fc5c0947005bc8a2443072370df8b0df16ca1201acb8b3adbf9fd24ae6fd825`;
  manifest file SHA-256 is
  `ff8ff6bbf4d00c341976d773ef28f02dc132acd43d989658b13877cb5dc4439d`;
  directory-content SHA-256 is
  `b88f25029836d26d903f445a7e7182239053fa1474fbb1d25f222955ec173d07`.
  Evaluation contains 1,350 rows: 219 abstentions and 1,131 visible targets.
  Training and development each contain zero rows.
- Evaluation result: `FAILED_SYNTHETIC_GATE`. Both independent 122,483-byte
  reports are byte-identical. Canonical report SHA-256 is
  `49612bbce8bb7e293a39acb857f85bf6e15a237b625c241fa0011bdea7189b15`;
  report file SHA-256 is
  `e2ddcc64ddacb88c86cdd877b589d3004df78e68fa02b808c2efa75b4a0cd453`;
  byte-identical stdout SHA-256 is
  `86db2ce8a41b32258698c8987440f09e18848328c9d1c26968e057b026bfd229`.
  Nominal alignment records 219 true abstentions, 1,074 true-visible
  decisions, 57 false abstentions, and zero missed abstentions. Recall is
  perfect at `0/219 = 0%`, but false stops are `57/1131 = 5.04%`, one case
  above the fixed 5% ceiling. The nominal synthetic gate therefore fails.
  Across the 1 mm stress ring, misses range from 0 to 5
  (`0%` to `5/219 = 2.28%`) while false stops range from 58 to 74
  (`5.13%` to `74/1131 = 6.54%`). The stress gate also fails specificity.
- Failure concentration: the 57 nominal false stops span 13 targets. Target
  `7` contributes 9; `SPACE` and `5` contribute 7 each; `E` and `W` contribute
  5 each. By lighting, upper-left soft vignette contributes 29, warm center
  bloom 19, and diagonal cool smear 9. Pose counts range from 7 to 12, led by
  period-transit sample 82 with 12. This is consumed evaluation diagnosis and
  cannot select successor weights, thresholds, architecture, or data.
- Validation: 41 focused simulator/perception tests passed in 16.46 seconds.
  The shared AI-to-arm boundary selection passed 59 tests in 3.76 seconds.
  Ruff passed. Maintained-document validation passed across 48 docs, 28 public
  titles, and two SVG assets. Public-record, evidence-scope, repository-artifact,
  repository-health, release-integrity, and release-readiness checks passed.
  Source footprint is 6,100 tracked files, 653,038,199 logical bytes, 4,890,152
  duplicate bytes, and remains within policy. The AI work-registry audit passed
  with 35 tracked and documented tests, 110 referenced paths, and zero unowned
  or multiply owned tests. `git diff --check` passed.
- Artifact location: external only under
  `C:\IsaacSim\artifacts\issue190\fixed-overview-recall-evaluation-v12-run1`,
  byte-identical `recall-evaluation-data-v1` and `...data-v2`, and byte-identical
  `recall-evaluation-report-v1` and `...report-v2`. Hashes identify exact local
  bytes but do not make them clean-clone available.
- Hardware-write count: 0.
- Physical-movement count: 0.
- Physics-step count: 0; schedule states are rendered statically and inference
  uses retained images offline.
- Limitations: all camera geometry, images, labels, target descriptors, and
  offsets are synthetic. The 1 mm ring uses nominal 2 px/mm simulator geometry
  and is not physical calibration. V12 is now consumed evaluation evidence and
  cannot tune a successor. Tool and camera-support geometry, physical frames,
  temporal evidence, and deployment calibration remain absent. This failed
  evaluation grants no localization, collision, controller, execution,
  transport, permit, or physical authority.
- Supersedes: none; preserves E-478's passing development result and adds the
  required fresh failed evaluation without rewriting or tuning either result.
- Next dependency: diagnose the 57 nominal false stops by target, pose, and
  lighting using the frozen report only. Any successor training and development
  data must be separately declared and cannot reuse v12 images, labels,
  probabilities, or failure identities for selection.


### E-20261001-AI-480 — specificity-balanced successor passes fresh development

- Stage: S2/S3 synthetic training and development of a zero-authority target-conditioned occlusion successor.
- Lane: AI/model with inert Isaac rendering and offline inference; no arm or integration status changed.
- Claim commit: `978b4ea184023c987b74db4f94c72172aad406a7`.
- Implementation and predeclaration commit: `03cde98cb84cefb599d24168c865a60a6a68c383`.
- Change: v13 reserves all thirteen remaining unused, pose-distinct actual-emitter schedule states before rendering. Training uses sequences 33, 65, 74, 86, 94, 97, 109, and 111; development uses 75, 89, 93, 95, and 101. Six deterministic lighting transforms are absent from v1-v12. The trainer admits only the exact E-478 model and scorecard, freezes both convolutions and the classifier, updates only the 224-parameter FiLM conditioner for 12 epochs with Adam, learning rate `0.00025`, weight decay `0.0001`, and ordinary binary cross entropy, and selects threshold and uncertainty only on v13 development. V12 bytes and identities are excluded. No evaluation group is created or opened.
- Inputs/fixtures: renderer SHA-256 `01396da0f7bd7b569eb3ac17a01b5ef8e3da54bac33ca89d6766d45673c9b3f1`; builder/trainer SHA-256 `23cdd1cefa59ba2a7ebc9fc3786242331a54707555cbe6500fa5f9004feb9608`; focused test SHA-256 `a9927da55d24293286aa5cbe0227d46fe41b67dfd6be68d8ee81b45c8dbf940f`; schedule file SHA-256 `6a59ce143f5527c7a9ced09b08d5515644ea4fb859dd69691e08483eb020ee42`; target catalog SHA-256 `6779213e832ab27eeda1e7fb245f57ff8cb0d56707b5aa73a8f31ec483a620f2`; exact seed model SHA-256 `27c7be58e11f8bf3341cb4eb56abdf7786d984e2664b6eb07d6349243730e09c`; exact seed canonical scorecard SHA-256 `807928f2559d14fa8b0b9da1781d379650deeadb40ec8690e41484be16eaa0d4`.
- Render command: `$env:OMNI_KIT_ACCEPT_EULA='YES'; $env:PYTHONPATH=(Resolve-Path 'software/src').Path; C:\IsaacSim\env_6_1_0\Scripts\python.exe software\integrations\isaac_sim\isaac_fixed_overview_mesh_render_probe.py --workspace . --upstream-repo C:\IsaacSim\sources\roarm_ws-40dbd84 --mesh-receipt software\integrations\isaac_sim\evidence\roarm_m3_upstream_link_meshes_20260929.json --capsule-manifest software\integrations\isaac_sim\evidence\fixed_overview_segmentation_v1\manifest.json --schedule-bundle software\integrations\isaac_sim\evidence\actual_emitter_joint_schedule_bundle_9e5c878_20260929.json --campaign specificity-rebalance-v13 --output-dir C:\IsaacSim\artifacts\issue190\fixed-overview-specificity-rebalance-v13-run1 --receipt C:\IsaacSim\evidence\fixed_overview_specificity_rebalance_v13_run1.json --status-output C:\IsaacSim\evidence\fixed_overview_specificity_rebalance_v13_run1.status.json`.
- Dataset command: `Copy-Item -LiteralPath C:\IsaacSim\evidence\fixed_overview_specificity_rebalance_v13_run1.json -Destination C:\IsaacSim\artifacts\issue190\fixed-overview-specificity-rebalance-v13-run1\manifest.json; python software\ai\train\build_official_mesh_occlusion_data.py --source-manifest C:\IsaacSim\artifacts\issue190\fixed-overview-specificity-rebalance-v13-run1\manifest.json --output-dir C:\IsaacSim\artifacts\issue190\specificity-rebalance-data-v1`; repeated with final output `...data-v2`.
- Training command: `python software\ai\train\build_official_mesh_occlusion_data.py --source-manifest C:\IsaacSim\artifacts\issue190\fixed-overview-specificity-rebalance-v13-run1\manifest.json --train-specificity-rebalance C:\IsaacSim\artifacts\issue190\specificity-rebalance-data-v1 C:\IsaacSim\artifacts\issue190\occlusion-recall-candidate-v1 C:\IsaacSim\artifacts\issue190\specificity-rebalance-candidate-v1`; repeated with dataset and candidate suffix `v2`.
- Render result: `PASS_WITH_BLOCKERS`. Canonical receipt SHA-256 is `5bf8456427e2c2dd4ac9c1b06c4425e0de10bcc22586c1411eb745595ba525c6`; receipt and copied-manifest file SHA-256 is `7644684f2f77050cc2cd179748b29b47b5d41820fb9065b1572b33f38513891a`; status file SHA-256 is `2991dbee2d2616310739ff92081bcf458b0089f0f919545b977a3f064e33c842`.
- Dataset result: both independent builds are byte-identical. Dataset SHA-256 is `db73af8b171eec859131673e7ddacbc2fa02728c1848eb1287b5afe277dba6ed`; manifest file SHA-256 is `7cac23de40eff04aede8f0b04bb8144f97b87ff3a179aea2cf5e1c91a61b894a`; directory-content SHA-256 is `29a866348d7219277e8ddab580abfd9afe852d0bff19919558b7d029b5674319`. Training contains 1,800 rows with 297 abstentions; development contains 1,125 rows with 204 abstentions; evaluation contains zero rows.
- Training result: both independent model, scorecard, stdout, and complete candidate directory bytes are identical. Model SHA-256 is `b20a02990d47ee87d97383d130052c4517391442d517ea94b5b5e78749a7525d`; canonical scorecard SHA-256 is `d11a71c67e2f7072e52a4a28d9c2bdbf5f6da308c5704bfe47a379c79cad9f00`; scorecard file SHA-256 is `4ceb8284f56e3f8b294a5f877bbdc2c8976a55cd5228b91336ff4fa8de90d554`; stdout SHA-256 is `1fddde75cb995ad254c59bb68cf3c285b5f848b53cc7c635c607ea9c732d6a69`; candidate directory-content SHA-256 is `693e3e471f60d6bebfb85157380ca24ee69ce5662802c2c0ce9a51f929ff6699`. Threshold `0.406` passes nominal development with 195 true abstentions, 910 true-visible decisions, 9 misses (`4.41%`), and 11 false stops (`1.19%`). Every 1 mm and 2 mm direction passes both 5% ceilings. At 2 mm, the worst miss rate is `9/204 = 4.41%` and the worst false-stop rate is `36/921 = 3.91%`. The 4 mm ring fails, reaching `13/204 = 6.37%` misses and `326/921 = 35.40%` false stops in different directions. The selected bound is therefore 2 mm and status remains `BLOCKED_AWAITING_FRESH_EVALUATION`.
- Validation: 43 focused simulator/perception tests passed in 20.97 seconds;
  107 shared AI-to-arm boundary and trajectory tests passed in 12.41 seconds.
  Ruff, maintained-document, public-record, evidence-scope,
  repository-artifact, repository-health, release-integrity, and
  release-readiness checks passed. The source footprint remains contained at
  6,100 files and 653,073,429 logical bytes. The AI work-registry audit passed
  with 35 tracked and documented tests, 110 referenced paths, and zero
  unowned or multiply owned tests. `git diff --check` passed.
- Artifact location: external only under `C:\IsaacSim\artifacts\issue190\fixed-overview-specificity-rebalance-v13-run1`, byte-identical `specificity-rebalance-data-v1` and `...data-v2`, and byte-identical `specificity-rebalance-candidate-v1` and `...candidate-v2`. Hashes identify exact local bytes but do not make them clean-clone available.
- Hardware-write count: 0.
- Physical-movement count: 0.
- Physics-step count: 0; schedule states are rendered statically and training uses retained images offline.
- Limitations: all camera geometry, images, masks, labels, target descriptors, and offsets are synthetic. The selected 2 mm bound assumes nominal 2 px/mm simulator geometry and is not physical calibration or deployment evidence. No untouched evaluation group exists for this checkpoint. Tool and camera-support geometry, physical frames, temporal evidence, and deployment calibration remain absent. This candidate grants no localization, collision, controller, execution, transport, permit, or physical authority.
- Supersedes: none; preserves E-479's failed consumed evaluation and creates a new independently predeclared train/development successor without rewriting or reusing that evidence.
- Next dependency: predeclare and run a new untouched synthetic evaluation campaign for the exact v13 model and scorecard. No schedule states remain in the current actual-emitter bundle, so fresh evaluation requires a separately generated and frozen inert schedule with pose-distinct states.


### E-20261001-AI-481 — specificity-balanced successor fails untouched v14 evaluation

- Stage: S2/S3 untouched synthetic evaluation of the exact E-480 checkpoint.
- Lane: AI/model with static inert Isaac rendering and offline inference; no arm or integration status changed.
- Claim commit: `1c8e31c334dac2983d039301fe1703bb658c1077`.
- Implementation and predeclaration commit: `123557c28e356b03dd3d58aed84c290a24d3bb0e`.
- Change: v14 creates a separately frozen, evaluation-only static visual pose fixture from six predeclared rational fractions of the exact zero-authority source schedule. It adds three lighting transforms absent from v1-v13 and an evaluator bound to the exact E-480 model, scorecard, threshold `0.406`, and 2 mm synthetic uncertainty policy. The 4 mm ring is stress evidence only. No training, selection, threshold change, model mutation, policy expansion, controller field, motion authority, or physical write is permitted.
- Inputs/fixtures: static fixture file SHA-256 `638e17a18feb79aa15864078ff80df37e69ebe6889710de08d98ed709013fb69`; canonical fixture bundle SHA-256 `93b77619af1bb90a3261b36cdbd7a209c3ac5bddf3b8a26b05fa2ae2b4625985`; source schedule file SHA-256 `6a59ce143f5527c7a9ced09b08d5515644ea4fb859dd69691e08483eb020ee42`; target catalog SHA-256 `6779213e832ab27eeda1e7fb245f57ff8cb0d56707b5aa73a8f31ec483a620f2`; exact model SHA-256 `b20a02990d47ee87d97383d130052c4517391442d517ea94b5b5e78749a7525d`; exact canonical scorecard SHA-256 `d11a71c67e2f7072e52a4a28d9c2bdbf5f6da308c5704bfe47a379c79cad9f00`. Renderer SHA-256 is `668bc00e632685ac698c569e3625d86dae6bdfe089ddee116bb363ab1088efe8`; builder/evaluator SHA-256 is `90b306fadfcd7824cf83ac2feec20d5de7d336852c160bfb133f6854983a4a6b`; fixture builder SHA-256 is `9e99cfedafc1725cfd4f76d338754331e4d18e5a396262ff5daa5b1a225b44c8`.
- Render command: `$env:OMNI_KIT_ACCEPT_EULA='YES'; $env:PYTHONPATH=(Resolve-Path 'software/src').Path; C:\IsaacSim\env_6_1_0\Scripts\python.exe software\integrations\isaac_sim\isaac_fixed_overview_mesh_render_probe.py --workspace . --upstream-repo C:\IsaacSim\sources\roarm_ws-40dbd84 --mesh-receipt software\integrations\isaac_sim\evidence\roarm_m3_upstream_link_meshes_20260929.json --capsule-manifest software\integrations\isaac_sim\evidence\fixed_overview_segmentation_v1\manifest.json --schedule-bundle software\ai\sim\evidence\static_interpolated_evaluation_poses_v1.json --campaign rebalance-evaluation-v14 --output-dir C:\IsaacSim\artifacts\issue190\fixed-overview-rebalance-evaluation-v14-run1 --receipt C:\IsaacSim\evidence\fixed_overview_rebalance_evaluation_v14_run1.json --status-output C:\IsaacSim\evidence\fixed_overview_rebalance_evaluation_v14_run1.status.json`.
- Dataset command: `Copy-Item -LiteralPath C:\IsaacSim\evidence\fixed_overview_rebalance_evaluation_v14_run1.json -Destination C:\IsaacSim\artifacts\issue190\fixed-overview-rebalance-evaluation-v14-run1\manifest.json; python software\ai\train\build_official_mesh_occlusion_data.py --source-manifest C:\IsaacSim\artifacts\issue190\fixed-overview-rebalance-evaluation-v14-run1\manifest.json --output-dir C:\IsaacSim\artifacts\issue190\specificity-rebalance-evaluation-data-v1`; repeated with output suffix `v2`.
- Evaluation command: `python software\ai\train\build_official_mesh_occlusion_data.py --source-manifest C:\IsaacSim\artifacts\issue190\fixed-overview-rebalance-evaluation-v14-run1\manifest.json --evaluate-specificity-rebalance C:\IsaacSim\artifacts\issue190\specificity-rebalance-evaluation-data-v1 C:\IsaacSim\artifacts\issue190\specificity-rebalance-candidate-v1 C:\IsaacSim\artifacts\issue190\specificity-rebalance-evaluation-report-v1`; repeated with dataset and report suffix `v2` against the same exact checkpoint.
- Render result: `PASS_WITH_BLOCKERS` for six static poses. Canonical receipt SHA-256 is `bfe243bb88e1eaf8544eec9bad58d84daa77ec4540473f8e49a768b94676a3c3`; receipt and copied-manifest file SHA-256 is `8ca817ca4abffe9f218feb45079221349b395e47e89039365cc756a4ee2dd54f`; status file SHA-256 is `9b8659b6b4ebf54d5577044f69617f69c0294330d8ff3de2fa144e1503d0557c`.
- Dataset result: both independent 22-file trees are byte identical. Canonical dataset SHA-256 is `98d30863887793a76e29dbcfeee48e4f6fe14e1d4a58f41cc232007d603b3379`; manifest file SHA-256 is `306abc668e90a39ef24ab08dda03d5cb4e2e1873dde650ca4863e1afb6b99fc5`. Evaluation contains 1,350 rows: 219 expected abstentions and 1,131 visible targets; train and development are empty.
- Evaluation result: both reports are byte identical. Canonical report SHA-256 is `97e26c28be37544d00b074ace9fb53b5b674f90ad5948208e72a5cdbbbc82521`; report file SHA-256 is `697882506d5ed294bf43727fac96da0751b0db689409b2a069df7e3ba8956585`. Nominal confusion is 195 true abstentions, 1,110 true-visible decisions, 24 misses, and 21 false stops: `24/219 = 10.96%` missed abstentions and `21/1131 = 1.86%` false abstentions. Inside the declared 2 mm envelope, the worst miss rate is `31/219 = 14.16%` at `(x=1 mm, y=-1 mm)` and the worst false-stop rate is `62/1131 = 5.48%` at `(x=2 mm, y=-2 mm)`. Both exceed the fixed 5% ceilings. At 4 mm, maxima reach `15.07%` misses and `36.87%` false stops. Status is `FAILED_SYNTHETIC_GATE`. The report retains each offset measurement plus per-target failure counts.
- Validation command: `python -m pytest software/tests/unit/test_static_evaluation_pose_fixture.py software/tests/unit/test_isaac_fixed_overview_mesh_render_evidence.py -q`; `python -m ruff check software/ai/train/build_official_mesh_occlusion_data.py software/integrations/isaac_sim/isaac_fixed_overview_mesh_render_probe.py software/tests/unit/test_isaac_fixed_overview_mesh_render_evidence.py software/ai/sim/build_static_evaluation_pose_fixture.py software/tests/unit/test_static_evaluation_pose_fixture.py`; `git diff --check`.
- Validation result: 47 focused simulator/perception tests passed in 17.67 seconds; 174 AI tests passed in 33.38 seconds; 80 available shared boundary, coordinator, journal, and trajectory tests passed in 13.21 seconds; and 55 public-record, evidence-scope, repository-artifact, repository-health, source-footprint, release-integrity, and readiness unit checks passed in 0.33 seconds. A broader combined command, `python -m pytest software/ai/tests software/tests/unit -q`, failed during collection because this branch lacks the arm-lane modules `scripts.preflight_r89_live_campaign`, `scripts.deploy_r90_pose_hover`, and `scripts.deploy_reviewed_hover_r89`; the failure is preserved and was not treated as model evidence. The first GitHub policy run also failed because the three reviewed v14 source files increased the observed tracked count from the former 6,100 ceiling to 6,103. The policy correction raises only the tracked-file ceiling to the exact measured 6,103 and leaves all byte and duplicate limits unchanged. The direct maintained-doc, public-record, evidence-scope, artifact, policy, source-footprint, release-integrity, and readiness commands then passed; the measured footprint is 6,103 files, 653,129,268 logical bytes, and 4,890,152 duplicate bytes. Ruff and `git diff --check` passed. Fixture test SHA-256 is `51994cb44a3ecdb0d0cbba72238768c0bfe438ab51fa9f1fcd7c132c8bc00ab6`; focused simulator/evaluator test SHA-256 is `196df5f36a696ff5647f7a4c95157bc5e627d0ff142b01f00e67202b9147edf8`.
- Artifact location: retained externally under `C:\IsaacSim\artifacts\issue190\fixed-overview-rebalance-evaluation-v14-run1`, byte-identical `specificity-rebalance-evaluation-data-v1` and `...data-v2`, and byte-identical `specificity-rebalance-evaluation-report-v1` and `...report-v2`. Hashes bind the exact local bytes but do not make them clean-clone available.
- Hardware-write count: 0.
- Physical-movement count: 0.
- Physics-step count: 0; the generated states are rendered statically and inference uses retained images offline.
- Limitations: all camera geometry, poses, images, masks, labels, target descriptors, and offsets are synthetic. Interpolated states are visual fixtures rather than trajectories and provide no dynamics, reachability, clearance, or collision evidence. The 2 mm envelope assumes nominal 2 px/mm simulator geometry and is not physical calibration. Tool and camera-support geometry, physical frames, temporal evidence, and deployment calibration remain absent. V14 is consumed and cannot tune a successor. This failure grants no localization, collision, controller, execution, transport, permit, deployment, or physical authority.
- Supersedes: none; preserves E-480's passing development result and adds the required untouched failed evaluation without rewriting or tuning either result.
- Next dependency: predeclare new train/development data and a mechanism aimed at pose generalization. Exclude every v14 image, mask, label, probability, failure identity, pose identity, lighting identity, and threshold outcome from training and selection. A future candidate requires another newly frozen untouched evaluation source.


### E-20261001-AI-482 — geometry-first self-occlusion and clustered qualification design

- Stage: S2/S3 architecture and evaluation-policy revision after the E-481 failure.
- Lane: AI/model documentation and shared perception-boundary design only; no arm or integration status changed.
- Claim commit: `f55f3a4b9947fb61e89ce02a1b374bc969804518`.
- Implementation commit: `b84420c493bdf91498e01686873fc22ba4096d85`.
- Change: known robot self-occlusion becomes a deterministic perception input projected from fresh measured joint state, commissioned camera/board calibration, and pinned official visual meshes. The learned model is restricted to residual obstructions and image failures such as cables, hands, glare, foreign objects, and degradation. Conservative fusion abstains if either route abstains, if they disagree, or if either route is stale or unqualified. Projected visibility evidence provides no collision, trajectory, permit, transport, or physical authority.
- Leakage control: simulator ground-truth robot masks are labels and scoring references only. Runtime-like silhouette features must come from the telemetry/calibration projection route and include predeclared perturbations of joint state, intrinsics, distortion, and extrinsics. Perfect renderer masks are forbidden as learned inputs.
- Label definition: historical E-457 through E-481 `target_visible` labels require both an uncovered target center and safe-region robot-mask overlap at or below `0.20`; center coverage or overlap above `0.20` is an abstention. A successor must freeze an ambiguity margin or continuous overlap-fraction target before generation and report failures by overlap fraction.
- Statistical gate: future point estimates cannot pass by themselves. A deterministic seeded pose-level cluster bootstrap resamples whole pose clusters and records the maximum error across all offsets inside the declared localization envelope on every replicate. The predeclared one-sided 95% upper-confidence limits are at most `0.02` missed abstentions and at most `0.10` visible false abstentions. This simultaneously addresses pose dependence, asymmetric consequence, and worst-offset multiplicity.
- Evaluation budget: before generation, the untouched set requires at least 64 independent pose clusters, 800 abstention-labeled observations, and 3,200 visible observations, with pose and lighting identities disjoint from training and development. Power and cluster-bootstrap simulations must show the design can pass. One primary evaluation set opens once for one frozen candidate; one separately identified escrow family remains unrendered. A failed set is consumed and cannot tune any successor.
- First physical protocol: begin ChArUco intrinsics, distortion, and camera-to-board captures plus measured lighting and parked-arm images in parallel. For the first interaction milestone, retract to a commissioned parked pose, wait for settling, capture fresh evidence for one action, then retract and recapture. Keyboard host events and development-mode phone ADB state are independent outcome observations when available and create no movement authority.
- Interpretation correction: byte-identical builds and reports demonstrate deterministic pipeline behavior. They do not establish statistical robustness of the observed rate; clustered uncertainty is required for that claim.
- Validation command: `python scripts/ci/check_docs.py; python scripts/ci/check_public_records.py; python scripts/ci/check_evidence_scope.py; python scripts/ci/check_repository_artifacts.py; python scripts/ci/check_repository_health.py --policy-only; python scripts/ci/check_source_archive_footprint.py --json; python scripts/ci/check_release_integrity.py --mode policy; python scripts/ci/check_release_readiness_sync.py; git diff --check`.
- Validation result: maintained-doc, public-record, evidence-scope, repository-artifact, repository-health, source-footprint, release-integrity, release-readiness, and diff checks passed. At implementation commit `b84420c493bdf91498e01686873fc22ba4096d85`, the measured footprint is 6,103 files, 653,138,378 logical bytes, and 4,890,152 governed duplicate bytes.
- Fixtures/data/metrics: no model, dataset, image, calibration, mask, threshold, or runtime artifact was generated or changed. This increment freezes design and future acceptance policy only.
- Hardware-write count: 0.
- Physical-movement count: 0.
- Physics-step count: 0.
- Limitations: no projection service, uncertainty propagation, cluster-bootstrap evaluator, ChArUco capture, parked-pose controller behavior, keyboard event collector, or ADB outcome adapter is implemented by this increment. The limits are synthetic research gates and do not qualify deployment. The arm lane retains exclusive ownership of calibration installation, planning, admission, encoding, transport, and execution.
- Supersedes: the next-campaign recommendation following E-481. It does not rewrite E-481, retroactively change the v14 5% gate, or promote the failed checkpoint.
- Next dependency: separately claim and implement the read-only deterministic self-occlusion projection contract and its uncertainty-envelope tests, then independently claim the ChArUco capture and lighting-survey data protocol. Any model campaign begins only after those inputs and the clustered power simulation are frozen.


### E-20261001-AI-483 — corrected occlusion qualification semantics

- Stage: S2/S3 qualification-policy correction before projection or render implementation.
- Lane: AI/model documentation and shared perception-boundary policy only; no arm-lane or integration-gate status changed.
- Claim commit: `d219820b3d77ce835059727d2addcc38ec546895`.
- Implementation commit: `6635291eed20c3c2ca660ed42b40301ab1c7b2ca`.
- Change: the fused OR decision now owns the authoritative one-sided 95% pose-cluster-bootstrap gates of at most 2% missed abstentions and 10% false abstentions. On the same clustered set, the geometric and residual paths receive false-stop upper-bound shares of 4% and 6%. Overlap between path stops is retained, so the shares do not arithmetically prove the fused gate. The redundant disagreement condition was removed.
- Temporal contract: projection binds the image exposure timestamp and clock identity to measured-position samples bracketing exposure and to a qualified interpolation rule. Latest feedback, commanded position, unsynchronized clocks, missing brackets, or excessive sample gaps require abstention.
- Dilation contract: image-space dilation must be derived by propagating ChArUco reprojection residuals, measured feedback resolution and noise, observed directional backlash, and parked-pose repeatability through the mesh projection. Guessed pixel margins are nonqualifying.
- Ambiguity policy: the uncovered-center overlap band is frozen at `[0.18, 0.22]`. Either decision is accepted for binary scoring inside the band, but every row remains in dataset totals and cluster resampling and is listed with pose, target, lighting, overlap, label, and decision. Center coverage always requires abstention, and the band cannot hide outside-band errors or be widened after observation.
- Power policy: 64 independent poses is a floor. The pre-render power tool estimates intra-pose correlation from grouped v13/v14 diagnostics and also uses a pessimistic value equal to the larger of its one-sided 95% upper bound and `0.30`. It increases pose count until the frozen design has at least 90% simulated probability of passing both fused gates at design rates of 1% misses and 6% false stops, while retaining minimum totals of 800 abstention and 3,200 visible labels.
- Operating scope: the initial parked-pose set is separate from the later broad-pose gate. It combines synthetic calibration/lighting variation with at least 30 independent physical park cycles across three sessions, records repeatability, ChArUco drift, tool/cable obstructions, fused decisions, exact binomial bounds, and false stops, and requires zero accepted known self-occlusions plus abstention for every labeled residual obstruction. It supports a supervised parked-observation milestone only and does not qualify mid-motion observation, unattended deployment, or physical authority.
- Document SHA-256 values at the implementation commit: shared workplan `a49f88dbd7b841cafc9b7f651d9b0f0da47d25ae104c38429aa1ced54e0fa1dd`; translation assurance `423d9e0910770ef7e36c5de3e4944c8f0fbc1de413f54cf14be41a7fbd94fb49`; training README `097286d04b55ffade4c5c3e32a51c8dcd0a14a726a1607ebe4a0ecc9f8f4e697`.
- Validation command: `python scripts/ci/check_docs.py; python scripts/ci/check_public_records.py; python scripts/ci/check_evidence_scope.py; python scripts/ci/check_repository_artifacts.py; python scripts/ci/check_repository_health.py --policy-only; python scripts/ci/check_source_archive_footprint.py --json; python scripts/ci/check_release_integrity.py --mode policy; python scripts/ci/check_release_readiness_sync.py; git diff --check`.
- Validation result: maintained-doc, public-record, evidence-scope, repository-artifact, repository-health, source-footprint, release-integrity, release-readiness, and diff checks passed. At implementation commit `6635291eed20c3c2ca660ed42b40301ab1c7b2ca`, the measured footprint is 6,103 files, 653,143,687 logical bytes, and 4,890,152 governed duplicate bytes.
- Fixtures/data/metrics: no model, dataset, image, calibration, mask, threshold, evaluation fixture, runtime artifact, or render was generated or changed. The numeric values above are predeclared future acceptance and power-design policy, not measured performance.
- Hardware-write count: 0.
- Physical-movement count: 0.
- Physics-step count: 0.
- Limitations: no projection service, time-synchronization adapter, measured-feedback source, uncertainty propagation, ICC estimator, power simulator, parked-pose dataset, or physical calibration evidence is implemented here. Thirty physical park cycles cannot by themselves demonstrate a 2% population error ceiling; their exact interval must remain visible, and the evidence is limited to supervised parked operation. The arm lane retains exclusive ownership of calibration installation, planning, admission, encoding, transport, and execution.
- Supersedes: E-482 only where its fusion wording, fixed 64-pose interpretation, unspecified dilation, and unspecified ambiguity scoring conflict with this correction. E-481 and all earlier measured evidence remain unchanged.
- Next dependency: separately claim and implement the read-only projection evidence contract and exposure-time measured-feedback validation first. Then claim the correlation-aware power and cluster-bootstrap tool before spending render compute. ChArUco capture, mechanical uncertainty measurement, and the parked-pose evidence protocol proceed as separately reviewed physical-data increments.


### E-20261001-AI-484 — read-only synthetic self-occlusion projection contract

- Stage: S2/S3 strict projection-evidence boundary before projection rendering or a new campaign.
- Lane: AI/model schema, validation, and offline tests only; no arm-lane or integration-gate status changed.
- Claim commit: `91d4ea6c20c42683fda5aacaf5141e6e5d0fe302`.
- Implementation commit: `d88364022d48d58ee7d1b61b1ddcf9fc40338447`.
- Change: added strict `rocell.ai_self_occlusion_projection_qualification.v1` and `rocell.ai_self_occlusion_projection_evidence.v1` synthetic-only schemas plus a read-only validator. Evidence binds exact image bytes and exposure interval to a single clock, measured-position receipt hashes before and after exposure, clock-correlation identity, qualified interpolation identity, the interpolated-state digest, camera/board/mesh/catalog/uncertainty/projector identities, measured dilation derivation, and deterministic named-target overlap decisions. It contains no joint values, command fields, transport fields, permits, collision claims, or physical authority.
- Timing behavior: commanded and latest-only position sources are structurally rejected. Exposure must be enclosed by the measured-feedback bracket on the same qualified clock. The trusted synthetic policy bounds bracket width and evidence age. Missing qualification, wrong domain, mismatched source or clock-correlation hashes, identity drift, stale evidence, excessive bracket width, and altered dilation all abstain.
- Visibility behavior: an uncovered target with dilated overlap below `0.18` is `VISIBLE`; overlap from `0.18` through `0.22` is `ABSTAIN_AMBIGUOUS`; center coverage or overlap above `0.22` is `ABSTAIN_SELF_OCCLUDED`. Dilation cannot reduce raw overlap. These are projection-path decisions only and do not establish localization, collision clearance, reachability, or execution safety.
- Trust behavior: evidence cannot self-install its qualification. Only a caller-authenticated `TrustedSyntheticProjectionQualificationV1` registry entry can admit the exact qualification hash, and the only accepted status is `ACCEPTED_SYNTHETIC_OFFLINE_ONLY`. Synthetic qualification is forced to `physical_deployment_qualified=false` with zero writes and zero movements.
- Artifact SHA-256 values: validator `cc5bf2c86e3376662c62229ebe00598ebcff3cd203dc202a647a3876b1cb6582`; evidence schema `a49ff6d66461bea6cbc051f808ad5353621ef8702a8b77deca9e8db8e5b1ec68`; qualification schema `cf32b5ef22bc7927f209ec3b7a5d3d9178470a80a44d5ff16e1a26e4c9ca0cf1`; focused test `00d9e4f0ff09fe1d68fc7d8cd8b6ac65806fda3d9b142cd259f0fd325929fc82`; registry audit receipt `444532eee10272c73ec2688ac7b64c83e32c68d9c4a75f9488976cd212e3fca0`.
- Focused and suite commands: `python -m pytest software/ai/tests/test_self_occlusion_projection.py software/ai/tests/test_ai_work_registry.py -q`; `python -m pytest software/ai/tests -q`; `python -m pytest software/tests/unit/test_model_motion_ingress_v2.py software/tests/integration/test_model_arm_conformance_profile_v1.py -q`; `python -m ruff check software/ai/rocell_ai/self_occlusion_projection.py software/ai/tests/test_self_occlusion_projection.py software/ai/tests/test_ai_work_registry.py`; `python software/ai/eval/audit_ai_work_registry.py --output software/ai/eval/ai_work_registry_audit_v1.json`.
- Policy command: `python scripts/ci/check_docs.py; python scripts/ci/check_public_records.py; python scripts/ci/check_evidence_scope.py; python scripts/ci/check_repository_artifacts.py; python scripts/ci/check_repository_health.py --policy-only; python scripts/ci/check_source_archive_footprint.py --json; python scripts/ci/check_release_integrity.py --mode policy; python scripts/ci/check_release_readiness_sync.py; git diff --check`.
- Validation result: 24 focused projection/registry tests passed; 192 AI tests passed; 34 shared model-to-arm ingress and conformance tests passed; Ruff, registry audit, maintained-document, public-record, evidence-scope, repository-artifact, repository-health, source-footprint, release-integrity, release-readiness, and diff checks passed. The registry covers 36 tracked AI tests and 112 referenced paths with no unowned or multiply owned test. The committed source footprint is 6,107 files, 653,195,583 logical bytes, and 4,890,152 governed duplicate bytes; only the tracked-file ceiling changed from 6,103 to the exact 6,107 required by the four reviewed source/schema/test files.
- Preserved failed development evidence: the first focused run failed all 18 cases because fixture placeholders `g` through `o` were not hexadecimal SHA-256 strings; production digest rejection worked as designed. After correcting fixture hashes, the first full AI run produced 191 passes and one failure because the governance test still expected 35 tracked AI tests. The expectation and generated registry audit were updated to the actual governed count of 36. Neither failure changed acceptance policy or erased prior output.
- Fixtures/data/metrics: fixtures are deterministic in-memory synthetic records. No model, image, render, mask, physical capture, calibration, threshold, training dataset, or evaluation campaign was generated or changed. Test pass counts establish contract behavior only.
- Hardware-write count: 0.
- Physical-movement count: 0.
- Physics-step count: 0.
- Limitations: the increment does not project meshes, inspect or authenticate joint values, validate the contents behind feedback receipt hashes, derive a measured dilation, install calibration, qualify a camera/clock, or supply fused residual-obstacle decisions. Caller authentication and upstream byte custody remain required. The contract is synthetic-only and cannot be used as deployment qualification or physical authority.
- Supersedes: none. It implements the first dependency declared by E-483 and leaves E-481 through E-483 unchanged.
- Next dependency: separately claim and implement the correlation-aware power and pose-cluster-bootstrap tool using grouped v13/v14 diagnostics and the frozen pessimistic-correlation scenario. Do not spend new render compute until that tool and its sample-size result are committed.


### E-20261001-AI-485 — correlation-aware synthetic occlusion power plan

- Stage: S2/S3 pre-render statistical planning for the later broad-pose occlusion evaluation.
- Lane: AI/model offline evaluation tooling only; no arm-lane or integration-gate status changed.
- Claim commit: `7ec9880a2f93d28295f0cc41af70a10f2fc0226d`.
- Implementation commit: `3fe8e57eca77dcd369be79e188d6ae2b0724d39a`.
- Change: added a strict aggregate-only planner that reconciles the retained v13 development and frozen v14 evaluation dataset, manifest, report, target-catalog, confusion, and failure identities; estimates endpoint-specific intra-pose correlation with a seeded whole-pose bootstrap; and runs empirical-upper and pessimistic-correlation beta-binomial power scenarios. The receipt emits source hashes and aggregate statistics only. It contains zero pose, target, row, image-path, or failure identities and cannot select a model or threshold.
- Exact retained inputs: v13 dataset file SHA-256 `3aa029d64b247601841e951f2645679391be55d138e7464b0769c6fe3eb25c60`, manifest file SHA-256 `7cac23de40eff04aede8f0b04bb8144f97b87ff3a179aea2cf5e1c91a61b894a`, report file SHA-256 `4ceb8284f56e3f8b294a5f877bbdc2c8976a55cd5228b91336ff4fa8de90d554`; v14 dataset file SHA-256 `e1c92152eac5486b0d8eb4cb41976637353cb12e81b62ddb7a08e34a46a3bd54`, manifest file SHA-256 `306abc668e90a39ef24ab08dda03d5cb4e2e1873dde650ca4863e1afb6b99fc5`, and report file SHA-256 `697882506d5ed294bf43727fac96da0751b0db689409b2a069df7e3ba8956585`. Both bind target catalog SHA-256 `6779213e832ab27eeda1e7fb245f57ff8cb0d56707b5aa73a8f31ec483a620f2`.
- Planning method: 5,000 seeded whole-pose bootstrap samples form a one-sided empirical ICC upper input by taking the maximum 95th percentile across both sources and all 17 offsets within the component-wise 2 mm envelope. Power uses 2,000 deterministic beta-binomial trials, whole-pose effects, worst-of-17 offsets, and a design-effect one-sided Wilson planning bound. Design rates remain frozen at 1% missed abstentions and 6% visible false stops; fused limits remain 2% and 10%; required joint planning power is 90%. The calculation is a planning approximation. Actual qualification remains a seeded pose-cluster-bootstrap upper bound, worst across declared offsets.
- Measured result: empirical upper correlations are `0.767574770` for missed abstentions and `0.024507274` for visible false stops. The pessimistic correlations are `0.767574770` and `0.30`. Median retained cluster sizes are 45 abstention-labeled and 180 visible rows per pose. The 64-pose floor has `0.000` joint planning power in both scenarios. The first tested size meeting the 90% joint target in both is 2,048 poses, with `0.936` empirical and `0.927` pessimistic joint power. No new render or model inference was performed.
- Exact generation command: `python software/ai/eval/plan_clustered_occlusion_power.py --v13-dataset C:\IsaacSim\artifacts\issue190\specificity-rebalance-data-v1\development.jsonl --v13-manifest C:\IsaacSim\artifacts\issue190\specificity-rebalance-data-v1\manifest.json --v13-report C:\IsaacSim\artifacts\issue190\specificity-rebalance-candidate-v1\scorecard.json --v14-dataset C:\IsaacSim\artifacts\issue190\specificity-rebalance-evaluation-data-v1\evaluation.jsonl --v14-manifest C:\IsaacSim\artifacts\issue190\specificity-rebalance-evaluation-data-v1\manifest.json --v14-report C:\IsaacSim\artifacts\issue190\specificity-rebalance-evaluation-report-v1\report.json --output software/ai/eval/clustered_occlusion_power_plan_v1.json`; the identical command writing `%TEMP%\clustered_occlusion_power_plan_v1_second.json` reproduced the exact output bytes.
- Artifact SHA-256 values: planner `894cb19043256346d48de4d9d84bd7b367f4f3c61cd4999ff822d3ddf97ff0fa`; retained plan file `986e438d99282e198fbf926c3c5e139e2a2a8ab145f0a2bedfecf6d01b8026c0`; canonical embedded plan SHA-256 `754f06c26b6a7b7ade29ca3ca136d0d3ff5f7d5e994e7135ddf39ee3ceced288`; schema `862e02e4dbe1af2b39772bcbd6334feda59a4be596b999708485d1fc7747ff49`; test `8764c6510b65e2f556f6b00c6b3731f63e8950220e7dfa8b5e3b8a0e56a2554c`; registry audit receipt `6f0c4a455b211029724f1ed699547c6d3a25cc1d5b8e8d7fc3f4deba9bb38497`.
- Validation commands: `python -m pytest software/ai/tests/test_clustered_occlusion_power.py software/ai/tests/test_ai_work_registry.py -q`; `python -m pytest software/ai/tests -q`; `python -m pytest software/tests/unit/test_model_motion_ingress_v2.py software/tests/integration/test_model_arm_conformance_profile_v1.py -q`; `python -m ruff check software/ai/eval/plan_clustered_occlusion_power.py software/ai/tests/test_clustered_occlusion_power.py software/ai/tests/test_ai_work_registry.py`; `python software/ai/eval/audit_ai_work_registry.py --output software/ai/eval/ai_work_registry_audit_v1.json`; `python scripts/ci/check_docs.py; python scripts/ci/check_public_records.py; python scripts/ci/check_evidence_scope.py; python scripts/ci/check_repository_artifacts.py; python scripts/ci/check_repository_health.py --policy-only; python scripts/ci/check_source_archive_footprint.py --json; python scripts/ci/check_release_integrity.py --mode policy; python scripts/ci/check_release_readiness_sync.py; git diff --check`.
- Validation result: 9 focused planner/registry tests passed; 196 AI tests passed; 34 shared model-to-arm ingress and conformance tests passed; Ruff, schema validation, registry audit, maintained-document, public-record, evidence-scope, repository-artifact, repository-health, release-integrity, release-readiness, and diff checks passed. Two independent generation runs were byte identical. The registry covers 37 AI tests and 116 referenced paths. The committed footprint is 6,111 files, 653,240,743 logical bytes, and 4,890,152 governed duplicate bytes; only the tracked-file ceiling changed from 6,107 to the exact 6,111 required by the four reviewed planner/schema/test/result files.
- Preserved failed development evidence: the first focused run had one failure because the zero-ICC case divided by zero in the beta-binomial concentration conversion. The simulator now evaluates zero ICC through the ordinary binomial limit, and the focused suite passed. The first Ruff run then rejected two unused imports; they were removed without changing the method or result. The first policy sequence reached `git diff --check`, which rejected CRLF introduced while rewriting the registry on Windows; the registry was rewritten with LF and the check passed. None of these failures changed gates, rates, correlation estimates, or sample-size selection.
- Hardware-write count: 0.
- Physical-movement count: 0.
- Physics-step count: 0; the planner reads retained JSON/JSONL only.
- Limitations: all inputs and outputs are synthetic. Six v14 and five v13 poses make the empirical ICC upper estimate itself uncertain, so the pessimistic scenario remains mandatory. The beta-binomial/design-effect Wilson calculation sizes a campaign but is not the future qualification estimator. The 2,048-pose recommendation applies to the later broad mid-motion synthetic gate, not the separate parked-pose milestone. It does not qualify projection geometry, measured feedback, dilation, camera calibration, localization, collision safety, contact, deployment, or physical authority.
- Supersedes: the fixed 64-pose interpretation only. E-481 remains a failed consumed evaluation; E-482 through E-484 otherwise remain unchanged.
- Next dependency: define and implement the separate parked-pose synthetic/physical qualification protocol and collect commissioned ChArUco, measured-feedback, backlash, repeatability, cable/tool-obstruction, and lighting evidence. A future broad campaign must freeze a new candidate, preserve v14 exclusion from selection, and predeclare the 2,048-pose design plus an unopened escrow family before rendering.


### E-20261001-AI-486 — strict parked-pose evidence protocol remains incomplete

- Stage: S2/S3 supervised parked-observation evidence protocol before physical collection.
- Lane: AI/model schemas and offline evaluator only; no arm-lane or integration-gate status changed.
- Claim commit: `801c7d4d19745db11f02757a96746332782b78cc`.
- Implementation commit: `9dc1f7fa6642b6468bb5df85d0a6bed33e0fa592`.
- Change: added strict parked-pose campaign and result schemas plus an offline evaluator. The campaign binds the commissioned park identity, camera calibration, camera-to-board transform, official robot visual meshes, target catalog, projection qualification, residual model, conservative fusion policy, repeatability qualification, ChArUco drift qualification, exact images, exposure bindings, measured-feedback bracket receipts, projection/residual-observer evidence, and authorized collection effects. It carries no joint values, servo commands, controller JSON, motion policy, permit, or transport fields.
- Synthetic policy: runtime-like projected silhouettes and simulator truth-mask labels are separate hashes, and `truth_mask_used_as_model_input` is fixed false. Required calibration perturbations, lighting variants, visible cases, known self-occlusions, and cable/tool residual obstructions must all be present. Both source paths and conservative OR fusion are independently checked.
- Physical policy: at least 30 unique completed and settled park cycles across at least three sessions are required. Every row binds image/exposure, measured-feedback bracket, projection, residual observation, ChArUco capture, park repeatability, drift evidence, and measured lighting identity. Visible, known self-occlusion, cable, and tool cases are mandatory. Every known self-occlusion must be detected by the geometric path and every residual obstruction by the residual path; the fused decision is recomputed as OR. Repeatability and drift must remain within independently bound campaign limits.
- Collection/evaluator separation: a physical campaign must retain actual collection hardware-write and physical-movement counts plus its authorization-evidence hash. The evaluator's own `hardware_writes` and `physical_movements` remain zero. The result always fixes `physical_deployment_qualified=false` and `controller_authority=false`; even structurally complete evidence advances only to owner review of the supervised parked workflow.
- Statistical output: false stops are reported separately for synthetic and physical visible cases with exact two-sided 95% Clopper-Pearson bounds. With zero events in only 30 trials, the upper bound is `0.11570330822202779`, demonstrating that 30 cycles cannot establish a 2% population failure ceiling.
- Retained result: `parked_pose_qualification_pending_v1.json` is `INCOMPLETE`, has no campaign SHA-256, and records the sole blocker `campaign_not_collected`. Synthetic observations, physical cycles, collection writes, collection movements, evaluator writes, and evaluator movements are all zero. This is the current factual readiness state rather than a fabricated campaign.
- Exact receipt command: `python software/ai/eval/evaluate_parked_pose_qualification.py --output software/ai/eval/parked_pose_qualification_pending_v1.json`; the same command writing `%TEMP%\parked_pose_qualification_pending_v1_second.json` reproduced byte-identical output.
- Artifact SHA-256 values: evaluator `2579f4f52db19df7afbd51d7c18aab7c2a4ddfb889e22d61b51d707f425ee8e8`; pending result file `db494161c53e8164d79034749417cb4c807ce134ef87eea9425cb5c060d8ce92`; canonical embedded result SHA-256 `afbdf74bcf4d0887a496fb6f1320e55360491c337df3f6aaf53eca63b229b9c4`; campaign schema `eb8e656af4ab4d2280d9a860b7c766769a76f41234b6bfd8eb5b9746df882964`; result schema `8ac5cc862bd53c414c9eb48f85a79db4e7113a947ac1f1137fed1fb97f90b2ab`; focused test `cf89490b6cefe2b60837f55a0ea65b0306fadb2feeb59e95ce4c49e626d64906`; registry audit receipt `680b793ef75020f7ae0131437a6873dfeaf9ae4c0bdb2197f52df8b1fe38e3a6`.
- Validation commands: `python -m pytest software/ai/tests/test_parked_pose_qualification.py software/ai/tests/test_ai_work_registry.py -q`; `python -m pytest software/ai/tests -q`; `python -m pytest software/tests/unit/test_model_motion_ingress_v2.py software/tests/integration/test_model_arm_conformance_profile_v1.py -q`; `python -m ruff check software/ai/eval/evaluate_parked_pose_qualification.py software/ai/tests/test_parked_pose_qualification.py software/ai/tests/test_ai_work_registry.py`; `python software/ai/eval/audit_ai_work_registry.py --output software/ai/eval/ai_work_registry_audit_v1.json`; `python scripts/ci/check_docs.py; python scripts/ci/check_public_records.py; python scripts/ci/check_evidence_scope.py; python scripts/ci/check_repository_artifacts.py; python scripts/ci/check_repository_health.py --policy-only; python scripts/ci/check_source_archive_footprint.py --json; python scripts/ci/check_release_integrity.py --mode policy; python scripts/ci/check_release_readiness_sync.py; git diff --check`.
- Validation result: 13 focused protocol/registry tests passed; 203 AI tests passed; 34 shared model-to-arm ingress and conformance tests passed; both schemas validated under JSON Schema 2020-12; Ruff, registry audit, maintained-document, public-record, evidence-scope, repository-artifact, repository-health, source-footprint, release-integrity, release-readiness, and diff checks passed. Two pending-receipt generations were byte identical. The registry covers 38 AI tests and 121 referenced paths. The committed footprint is 6,116 files, 653,289,398 logical bytes, and 4,890,152 governed duplicate bytes; only the tracked-file ceiling changed from 6,111 to the exact 6,116 required by the five reviewed evaluator/schema/test/result files.
- Preserved failed development evidence: the first focused test run passed all seven cases, but the following Ruff run rejected one unused `deepcopy` import in the test. The import was removed without changing protocol behavior. No physical data, acceptance gate, or result was changed in response.
- Hardware-write count: 0 for this implementation and evaluator run.
- Physical-movement count: 0 for this implementation and evaluator run.
- Physics-step count: 0; no simulator or renderer was opened.
- Limitations: no ChArUco, lighting, repeatability, backlash, measured-feedback, cable, tool, image, synthetic perturbation, or park-cycle evidence was collected. Hash bindings do not establish custody or truth of future source artifacts; upstream collectors and owner review must authenticate them. Structural test fixtures demonstrate evaluator behavior only and are not retained physical evidence. The protocol is limited to supervised observation after a commissioned park and settle cycle and cannot qualify mid-motion observation, unattended deployment, collision safety, contact, localization, or physical execution.
- Supersedes: none. It implements the parked-pose protocol dependency declared by E-483 and E-485 while preserving the broad 2,048-pose gate and all consumed v14 evidence.
- Next dependency: collect the commissioned camera/support originals and ChArUco/lighting/repeatability evidence through the ARM-071 onboarding path, then collect the separately authorized physical park cycles. Until those originals exist, the AI lane can implement a file-backed preflight that authenticates retained campaign artifacts without generating or moving the arm.


### E-20261001-AI-487 — file-backed parked-pose preflight remains blocked

- Stage: S2/S3 retained-artifact authentication before parked-pose evaluation.
- Lane: AI/model read-only preflight only; no arm-lane or integration-gate status changed.
- Claim commit: `e869e154223affb89f8b7f9754e01396c646b417`.
- Implementation commit: `ad2c8ce9aeee11e0b6fcfddcda1e0c5a6afa72ed`.
- Change: added strict evidence-index and preflight-receipt schemas plus a read-only file preflight. It derives the exact required artifact set from the campaign rather than trusting index coverage. Required types include commissioned park identity, camera and board calibration, robot visual meshes, target catalog, projection qualification, residual model, fusion policy, repeatability and drift qualifications, collection authorization, custody review, every synthetic image/runtime-like projection/truth label, and every physical image/exposure binding/measured-feedback bracket/projection/residual observation/ChArUco capture/repeatability/drift record.
- Integrity behavior: every required SHA-256 must have exactly one index entry and one unique contained relative path. The preflight verifies artifact type, expected declared-custody class, byte count, stable bytes during hashing, and SHA-256. Missing, extra, duplicate-digest, duplicate-path, altered, size-mismatched, traversal, final-symlink, nested-symlink, symlink-root, index-self-hash, campaign-self-hash, and campaign/index binding failures stop the run. Physical rows also require a retained collection-authorization artifact.
- Custody boundary: `PHYSICAL_RETAINED_ORIGINAL` and other index custody values are declarations. A passing preflight authenticates retained bytes and bindings only. It cannot prove who captured them, physical originality, measurement truth, model behavior, calibration quality, safety, or deployment readiness. The custody-review bytes require independent owner authentication.
- Structural fixture result: a temporary full protocol fixture reconciled exactly 270 retained artifacts: 240 physical-declared bindings, 18 synthetic bindings, ten reviewed configuration/software bindings, one collection authorization, and one custody review. This fixture exists only in the test temporary directory and is not physical evidence.
- Retained result: `parked_pose_preflight_pending_v1.json` is `BLOCKED` by `campaign_package_not_retained`. Campaign, index, and custody-review identities are null; verified artifacts and bytes are zero; physical deployment qualification and controller authority are false; evaluator writes and movements are zero.
- Exact receipt command: `python software/ai/eval/preflight_parked_pose_campaign.py --output software/ai/eval/parked_pose_preflight_pending_v1.json`; the same command writing `%TEMP%\parked_pose_preflight_pending_v1_second.json` reproduced byte-identical output.
- Artifact SHA-256 values: preflight `ad1ca6338220a11df2be1fef8eb0908c59a1ebf20b8153aebe8fbe7288f26db8`; pending receipt file `9d5528846a038b154f914a938c7e3b3bba0d90b773cdf953cb9f3ff9273fd0d2`; canonical embedded receipt SHA-256 `a94e4b5c44f574eff6f03c35c4a8b3ae3ed677058f1d815d2fde5cee5b4dd960`; evidence-index schema `027b8a7119e3bafc67989da48dd0540e44a2f23b7825642fff98ea274b508a06`; receipt schema `3c9128bbe6a506dfd9e2c87c5f07c8e557cea4967b849ccb39b41544f18fe15d`; focused test `8a853383a4c142784431d754c59ba6439204192fb95305286981ec3a273087d6`; registry audit receipt `f0fb92ffd86a490999f161541ced101086f8fac944b9874a3363e27cf5eb51b9`.
- Validation commands: `python -m pytest software/ai/tests/test_parked_pose_preflight.py software/ai/tests/test_ai_work_registry.py -q`; `python -m pytest software/ai/tests -q`; `python -m pytest software/tests/unit/test_model_motion_ingress_v2.py software/tests/integration/test_model_arm_conformance_profile_v1.py -q`; `python -m ruff check software/ai/eval/preflight_parked_pose_campaign.py software/ai/tests/test_parked_pose_preflight.py software/ai/tests/test_ai_work_registry.py`; `python software/ai/eval/audit_ai_work_registry.py --output software/ai/eval/ai_work_registry_audit_v1.json`; `python scripts/ci/check_docs.py; python scripts/ci/check_public_records.py; python scripts/ci/check_evidence_scope.py; python scripts/ci/check_repository_artifacts.py; python scripts/ci/check_repository_health.py --policy-only; python scripts/ci/check_source_archive_footprint.py --json; python scripts/ci/check_release_integrity.py --mode policy; python scripts/ci/check_release_readiness_sync.py; git diff --check`.
- Validation result: on the Windows development host, 11 focused preflight/registry tests passed and one symlink test skipped because unprivileged symlink creation was unavailable; 208 AI tests passed and the same single test skipped; 34 shared model-to-arm ingress and conformance tests passed. Both schemas validated under JSON Schema 2020-12. Ruff, registry audit, maintained-document, public-record, evidence-scope, repository-artifact, repository-health, source-footprint, release-integrity, release-readiness, and diff checks passed. Two pending-receipt generations were byte identical. The registry covers 39 AI tests and 126 referenced paths. The committed footprint is 6,121 files, 653,323,561 logical bytes, and 4,890,152 governed duplicate bytes; only the tracked-file ceiling changed from 6,116 to the exact 6,121 required by the five reviewed preflight/schema/test/result files.
- Preserved non-pass evidence: Windows could not create the symlink needed by the symlink-rejection test, so pytest recorded an explicit skip rather than treating the case as passed. The test remains enabled for Linux CI. No protocol behavior, artifact, gate, or result was changed because of the host limitation.
- Hardware-write count: 0.
- Physical-movement count: 0.
- Physics-step count: 0; no simulator or renderer was opened.
- Limitations: no actual campaign package, physical original, custody review, ChArUco capture, measured-feedback receipt, calibration, lighting survey, park cycle, cable/tool observation, or synthetic campaign asset exists. Regular-file hash validation does not prevent a dishonest producer from supplying false but internally consistent bytes. It also does not establish model performance or qualify the supervised workflow. Owner review, authorized collection, semantic evaluation, and arm-owned safety gates remain separate.
- Supersedes: none. It implements E-486's file-backed preflight dependency and leaves both parked-pose receipts blocked/incomplete.
- Next dependency: ARM-071 must onboard the four camera/support physical originals. After that, freeze an authorized collection package layout and capture the calibration/lighting/repeatability inputs. The AI lane can next implement a deterministic package builder that inventories already retained files but must not generate evidence content, move the arm, or self-assign physical custody.


### E-20261001-AI-488 — deterministic retained-package index builder

- Stage: S2/S3 retained parked-pose package assembly before file preflight.
- Lane: AI/model offline metadata assembly only; no arm-lane or integration-gate status changed.
- Claim commit: `e6546925ab4009f6887113b75ef9c8f6020637b9`.
- Implementation commit: `e7b16c2de470a1c01040fab0be17e22b44cdfcdc`.
- Change: added an externally authored custody-declaration schema and a deterministic index builder over one frozen parked-pose campaign and one exact retained evidence directory. Artifact types come from the campaign contract. Custody values come only from the separately supplied declarations. The builder verifies both self-hashes, their shared campaign identity, exact declaration coverage, protocol-required custody classes, one nonempty contained regular file per required digest, stable bytes during hashing, and no unmatched retained file.
- Rejection behavior: malformed schemas, duplicate JSON fields, campaign or declaration self-hash mismatch, wrong campaign binding, missing physical collection authorization, missing/extra/duplicate custody declarations, wrong declared custody class, missing/extra/empty files, duplicate content at multiple paths, root/nested/file symlinks, non-regular files, and file-set changes during inventory fail closed. CLI output is required to remain outside the evidence root so repeated indexing cannot silently inventory its own metadata.
- Structural fixture result: the builder inventoried the temporary 270-artifact protocol fixture twice and produced the exact same evidence index both times. The independently invoked preflight accepted that index as `PASS_FILE_INTEGRITY_ONLY`, with 270 verified artifacts, 240 physical-declared bindings, and 18 synthetic bindings. All files and declarations were test-generated inside pytest temporary storage and are not retained physical evidence.
- Custody boundary: `PHYSICAL_RETAINED_ORIGINAL` and every other custody value remain externally supplied declarations. The builder checks consistency with the protocol but cannot authenticate the author, capture event, physical originality, or measurement truth. The custody-review artifact still requires independent owner authentication.
- Exact validation commands: `python -m ruff check software/ai/eval/build_parked_pose_evidence_index.py software/ai/tests/test_parked_pose_package_builder.py software/ai/tests/test_ai_work_registry.py`; `python -m pytest software/ai/tests/test_parked_pose_package_builder.py software/ai/tests/test_parked_pose_preflight.py software/ai/tests/test_ai_work_registry.py -q`; `python -m pytest software/ai/tests -q`; `python -m pytest software/tests/unit/test_model_motion_ingress_v2.py software/tests/integration/test_model_arm_conformance_profile_v1.py -q`; `python software/ai/eval/audit_ai_work_registry.py --output software/ai/eval/ai_work_registry_audit_v1.json`; `python scripts/ci/check_docs.py; python scripts/ci/check_public_records.py; python scripts/ci/check_evidence_scope.py; python scripts/ci/check_repository_artifacts.py; python scripts/ci/check_repository_health.py --policy-only; python scripts/ci/check_source_archive_footprint.py --json; python scripts/ci/check_release_integrity.py --mode policy; python scripts/ci/check_release_readiness_sync.py; git diff --check`.
- Validation result: on the Windows development host, 16 focused builder/preflight/registry tests passed and two symlink tests skipped because unprivileged symlink creation was unavailable; 213 AI tests passed and the same two tests skipped; 34 shared model-to-arm ingress and conformance tests passed. JSON Schema 2020-12 validation, Ruff, registry audit, maintained-document, public-record, evidence-scope, repository-artifact, repository-health, source-footprint, release-integrity, release-readiness, and diff checks passed. The registry covers 40 AI tests and 129 referenced paths.
- Artifact SHA-256 values: builder `d4383efe920df4422371dbabe7ede84c88488233406f50d09905df6fc7adc023`; custody-declaration schema `e50b9be66605194c2ff1492010c5198f0dce0215d5e4d40dd67e56eef0d61229`; focused test `77b4f6533740055b2ba26c99f1a13b7dc245455f91bff687e29c165b67c8fa7f`; registry audit receipt `b6eeb0966e1c1f1fea1a28fdd5e82e9ff05ebca0a2483ae03fec1fba1a20fd51`.
- Preserved non-pass evidence: Windows could not create symlinks for the builder and preflight rejection cases, so pytest recorded two explicit skips. Both tests remain enabled for Linux CI. No contract, artifact, gate, or result was altered because of this host limitation.
- Hardware-write count: 0.
- Physical-movement count: 0.
- Physics-step count: 0; no simulator or renderer was opened.
- Implementation-commit footprint: 6,124 tracked files, 653,347,836 logical bytes, 4,890,152 governed duplicate bytes, and a 55,939,877-byte largest blob. The tracked-file ceiling changed from 6,121 to exactly 6,124 for the reviewed builder, schema, and test files.
- Limitations: no real campaign, image, calibration, measured-feedback bracket, ChArUco capture, authorization, or authenticated custody declaration was supplied. The fixture proves deterministic assembly and rejection behavior only. A malicious producer can still supply false but internally consistent evidence and declarations. This increment does not evaluate model accuracy, qualify the parked workflow, authorize collection, or grant physical authority.
- Supersedes: none. It implements E-487's deterministic package-builder dependency while leaving both retained parked-pose receipts blocked/incomplete.
- Next dependency: ARM-071 must retain and authenticate the four camera/support originals. After the measured configuration epoch exists, an authorized collector must freeze the campaign and separately authenticated custody declarations; the builder can then assemble their index for unchanged preflight and evaluation.


### E-20261001-AI-489 — pose-diverse visibility successor fails clustered development gate

- Stage: S2/S3 synthetic target-visibility training and development-only selection after the consumed v14 evaluation.
- Lane: AI/model, static inert Isaac rendering, offline dataset assembly, and offline model training only; no arm-lane or integration-gate status changed.
- Claim commit: `bcc8dd970fa97fa711647b66b815944a24feb951`.
- Frozen implementation/predeclaration commit: `3ecb30eca9a4b4aee8cccfa4eef6a3144cc5f1fc`.
- Packaging repair commits: `0c5401ca5cd42aa49e44c46a0b1969ce4d7d2c7b` bounds atlas dimensions after run 1 exposed Pillow's 65,500-pixel limit; `ba1ea9bf43098eb37e6d17c4785d428023cc1aab` writes deterministic 16-pose atlas chunks after run 2 exhausted RTX resource descriptors. Neither repair changed pose identities, split, lighting, labels, training parameters, thresholds, gates, seed, or source checkpoint.
- Change: v15 freezes 96 fresh static schedule-interpolated visual poses, with 72 training poses and every fourth accepted pose in a 24-pose development split. It uses three new training and three new development lighting transforms, contains no evaluation group, seeds the exact E-480 checkpoint, freezes both convolutions and the classifier, and trains only the FiLM conditioner for 16 epochs at learning rate `0.00035`, positive-abstention weight `1.5`, seed `190`, and deterministic CPU execution. Selection limits were frozen at at most 2% missed abstentions and 10% false abstentions for both point metrics and seeded one-sided 95% whole-pose bootstrap UCBs.
- Fixtures and source identities: source schedule file SHA-256 `6a59ce143f5527c7a9ced09b08d5515644ea4fb859dd69691e08483eb020ee42`; v15 fixture file SHA-256 `38e169e1b8b59d77785470b44e5feca8dad78fce18bc6dab8459ffa3f867ae0e`; canonical fixture bundle SHA-256 `df7ccb80e12121497a48f886f6d9c1aa29f82a91f5be9f73990914e682109061`; target catalog SHA-256 `6779213e832ab27eeda1e7fb245f57ff8cb0d56707b5aa73a8f31ec483a620f2`; seed model SHA-256 `b20a02990d47ee87d97383d130052c4517391442d517ea94b5b5e78749a7525d`; seed canonical scorecard SHA-256 `d11a71c67e2f7072e52a4a28d9c2bdbf5f6da308c5704bfe47a379c79cad9f00`.
- Source artifact identities after packaging repair: fixture builder `13a9a08417d2c1b6f5cba1119e55db8fd1db6473abaa77a7cbb6e0675a282be8`; renderer `c395a39bfb62fc8b67c64a6e670fba39d4d685b0f3f331c60a15e585fd4b7159`; dataset/training builder `7f1ee2952b68f60c9394e9787ad71d3bb48b24a3b6a736f62554b9b1cc95182a`; fixture test `9539437cc80cd0b3068b4915bdd0eddb3927ced08d7b80dce7d60fe2e92a9801`; focused renderer/training test `33490b9b678b9d080c23e0981ad1c9d51a67e80be2e6ab4976da7164c8add1b0`.
- Exact successful render command: `$env:OMNI_KIT_ACCEPT_EULA='YES'; $env:PYTHONPATH=(Resolve-Path 'software/src').Path; C:\IsaacSim\env_6_1_0\Scripts\python.exe software\integrations\isaac_sim\isaac_fixed_overview_mesh_render_probe.py --workspace . --upstream-repo C:\IsaacSim\sources\roarm_ws-40dbd84 --mesh-receipt software\integrations\isaac_sim\evidence\roarm_m3_upstream_link_meshes_20260929.json --capsule-manifest software\integrations\isaac_sim\evidence\fixed_overview_segmentation_v1\manifest.json --schedule-bundle software\ai\sim\evidence\pose_diverse_training_development_v1.json --campaign pose-diverse-training-v15 --output-dir C:\IsaacSim\artifacts\issue190\fixed-overview-pose-diverse-v15-run3 --receipt C:\IsaacSim\evidence\fixed_overview_pose_diverse_v15_run3.json --status-output C:\IsaacSim\evidence\fixed_overview_pose_diverse_v15_run3.status.json`.
- Exact dataset command: `Copy-Item -LiteralPath C:\IsaacSim\evidence\fixed_overview_pose_diverse_v15_run3.json -Destination C:\IsaacSim\artifacts\issue190\fixed-overview-pose-diverse-v15-run3\manifest.json; python software\ai\train\build_official_mesh_occlusion_data.py --source-manifest C:\IsaacSim\artifacts\issue190\fixed-overview-pose-diverse-v15-run3\manifest.json --output-dir C:\IsaacSim\artifacts\issue190\pose-diverse-data-v1`; repeated unchanged with output suffix `v2`.
- Exact training command: `python software\ai\train\build_official_mesh_occlusion_data.py --source-manifest C:\IsaacSim\artifacts\issue190\fixed-overview-pose-diverse-v15-run3\manifest.json --train-pose-diverse-successor C:\IsaacSim\artifacts\issue190\pose-diverse-data-v1 C:\IsaacSim\artifacts\issue190\specificity-rebalance-candidate-v1 C:\IsaacSim\artifacts\issue190\pose-diverse-candidate-v1`; repeated unchanged with candidate output suffix `v2`.
- Render result: run 3 is `PASS_WITH_BLOCKERS` for 96 poses and 18 chunked atlas artifacts. Canonical receipt SHA-256 is `8677602fcd57d60bee7cbb0855336af74c37a0de1b436bc8ca373efccd324912`; receipt/copied-manifest file SHA-256 is `acdc2cebb1b4b5ff6fa3090f1197932c84ff3b5b5a47ad7b1b90321fc22f0eb1`; status file SHA-256 is `72fb4fe825c44eb99bc7cb5b198b2ec8ff32bf350ff2d84b34f3dcd9fa56330c`.
- Dataset result: both independent 292-file trees are byte identical, contain 46,719,682 bytes, and have inventory digest `e16995eadf146eaaf62f15bfd8cc04c70d8d0d14ca0ec3740eeafb1ed21a427f`. Canonical dataset SHA-256 is `a478dcf510ee0936bf029a8e6f27b00f7cd41a5847ba9f6caec15174a9f6da09`; manifest file SHA-256 is `b20e34deb5a89cabcb333ec4d7627f8c6918871d225bc6da03f0fa9e7ba9c081`. Training has 16,200 rows with 2,463 abstentions and 13,737 visible labels; development has 5,400 rows with 786 abstentions and 4,614 visible labels; evaluation has zero rows.
- Model result: both model files are byte identical with SHA-256 `9e09a13fae22cbbc75d2b15d9fe2e9cfbf76638d61220d635dd31272e298cfbb`. Both scorecard files are byte identical with file SHA-256 `e61907d5111b3f1328d976156362c14f54522a16df62c6db941b22e73bc19616` and canonical embedded scorecard SHA-256 `0079e0d7f3b7b4f77d191b7258cafbbe8a53e88441767059f6d4a63858edf490`.
- Metrics: selected threshold is `0.141`. Nominal development has 781 true abstentions, 4,468 true-visible decisions, five missed abstentions, and 146 false abstentions: `5/786 = 0.64%` misses and `146/4614 = 3.16%` false stops. Point metrics pass through the component-wise 1 mm ring; the worst point miss rate there is `15/786 = 1.91%` at `(-1,+1) mm`, and the worst false-stop rate is `283/4614 = 6.13%` at `(+1,-1) mm`. The seeded 2,000-resample 24-pose bootstrap reports worst missed-abstention UCB `3.249097%` and worst false-abstention UCB `7.134968%`. The miss UCB exceeds the frozen 2% ceiling, so `pose_cluster_upper_bound_gate_met=false`, `development_gate_met=false`, and promotion status is `FAILED_DEVELOPMENT_GATE`. The internal point selector's 1 mm value is not an installable qualification because the authoritative clustered gate failed.
- Preserved failed evidence: the first fixture algorithm used uniform fractions and failed with `RuntimeError: generated render poses are not fresh and distinct`; its focused run recorded one failed and two passed tests before the prime-modulus fixture was frozen. Isaac run 1 rendered 288 valid per-pose files but failed while writing an over-limit vertical atlas with `OSError: broken data stream when writing image file`; its retained status SHA-256 is `18c1792be8706b68e66d29561f36f4780` and reports zero writes and movements. Run 2 then emitted `Fatal [omni.rtx] Out of resource descriptors!` during the monolithic tiled-atlas path and was interrupted after remaining CPU-active without producing a receipt or status; its empty/incomplete output was not admitted. Both failures remain separate from successful run 3 and did not alter the frozen experiment.
- Validation commands: `python -m ruff check software/ai/sim/build_pose_diverse_training_fixture.py software/integrations/isaac_sim/isaac_fixed_overview_mesh_render_probe.py software/ai/train/build_official_mesh_occlusion_data.py software/tests/unit/test_pose_diverse_training_fixture.py software/tests/unit/test_isaac_fixed_overview_mesh_render_evidence.py`; `python -m pytest software/tests/unit/test_pose_diverse_training_fixture.py software/tests/unit/test_isaac_fixed_overview_mesh_render_evidence.py -q`; `python -m pytest software/ai/tests -q`; `python -m pytest software/tests/unit/test_model_motion_ingress_v2.py software/tests/integration/test_model_arm_conformance_profile_v1.py -q`; `python software/ai/eval/audit_ai_work_registry.py`; `python scripts/ci/check_docs.py; python scripts/ci/check_public_records.py; python scripts/ci/check_evidence_scope.py; python scripts/ci/check_repository_artifacts.py; python scripts/ci/check_repository_health.py --policy-only; python scripts/ci/check_source_archive_footprint.py --json; python scripts/ci/check_release_integrity.py --mode policy; python scripts/ci/check_release_readiness_sync.py; git diff --check`.
- Validation result: the final combined focused suite passed 51 tests in 18.53 seconds; the earlier pre-chunk suite passed 50 tests and the first post-chunk renderer suite passed 48 tests. The full AI suite passed 213 tests with two Windows symlink skips; 34 shared ModelMotionBatch ingress/conformance tests passed. Ruff, registry audit, maintained-doc, public-record, evidence-scope, repository-artifact, repository-health, source-footprint, release-integrity, readiness, and diff checks passed. Registry audit receipt file SHA-256 is `8b64ab98fc98f69918f48d48a6b431f528b50fe5cb98595488ffecf0cdb3f0ff`. The source footprint is 6,127 tracked files, 653,478,428 logical bytes, and 4,890,152 governed duplicate bytes; hardware writes and physical movements remained zero.
- Hardware-write count: 0.
- Physical-movement count: 0.
- Physics-step count: 0; every arm state is rendered statically and all model work is offline.
- Limitations: all camera geometry, robot placement, images, masks, labels, lighting, target coordinates, and offset perturbations are synthetic. The 96 states densely sample one governed path and are correlated; they do not cover arbitrary arm configurations. The tool and camera-support meshes, commissioned camera calibration, synchronized measured joint feedback, physical lighting, cables, hands, and unexpected objects remain absent. This campaign trains target visibility/occlusion only and does not improve the retained KeyboardPoseNet localization bound of `14.400834977 mm`. Passing point metrics do not override the failed clustered gate. The artifacts grant no localization, collision, reachability, controller, transport, permit, deployment, or physical authority.
- Supersedes: none. It preserves the failed v14 evaluation and implements its fresh pose-generalization training dependency without opening another evaluation set. It also leaves E-482 through E-488 and the geometry-first architecture intact.
- Next dependency: keep this checkpoint rejected. Use the pose-level failures as development diagnostics only under a separately predeclared successor design. Implement and physically commission the synchronized geometry-projection path and measured dilation inputs in parallel. Any later learned residual candidate needs a new frozen train/development design and, only after passing its clustered gate, a newly predeclared untouched evaluation source. Do not reuse v14 or claim the 1 mm point result as runtime calibration.


### E-20261001-AI-490 — v15 development misses are concentrated by pose and target

- Stage: S2/S3 synthetic development-only diagnosis after the failed v15 clustered gate.
- Lane: AI/model analysis only; no arm-lane or integration-gate status changed.
- Claim commit: `4d0bfd7b63bba52433224db98e09ebbb254eef1f`.
- Implementation commit: `048bb41acd2cbe6350672e82f402bc54d096cc12`.
- Change: added a strict read-only diagnostic, report schema, retained report, and tests. The tool verifies the v15 dataset, scorecard, and pose-fixture canonical hashes; refuses any evaluation group or physical authority; binds every failure to an exact development row; limits analysis to the selected 1 mm ring; and attributes misses and false stops by whole pose, target, lighting identity, source interval, and offset. It does not load images, run inference, alter the threshold, train a model, render a pose, or open an evaluation source.
- Exact command: `python software/ai/eval/diagnose_pose_cluster_development.py --dataset-manifest C:\IsaacSim\artifacts\issue190\pose-diverse-data-v1\manifest.json --development-rows C:\IsaacSim\artifacts\issue190\pose-diverse-data-v1\development.jsonl --scorecard C:\IsaacSim\artifacts\issue190\pose-diverse-candidate-v1\scorecard.json --pose-fixture software\ai\sim\evidence\pose_diverse_training_development_v1.json --output software\ai\eval\pose_cluster_development_diagnostic_v1.json`.
- Inputs and fixtures: dataset manifest file SHA-256 `b20e34deb5a89cabcb333ec4d7627f8c6918871d225bc6da03f0fa9e7ba9c081`; canonical dataset SHA-256 `a478dcf510ee0936bf029a8e6f27b00f7cd41a5847ba9f6caec15174a9f6da09`; development JSONL SHA-256 `dae77167465e727a83961374d6013fb98124241124b292e3107b4114e2296e72`; scorecard file SHA-256 `e61907d5111b3f1328d976156362c14f54522a16df62c6db941b22e73bc19616`; canonical scorecard SHA-256 `0079e0d7f3b7b4f77d191b7258cafbbe8a53e88441767059f6d4a63858edf490`; model SHA-256 `9e09a13fae22cbbc75d2b15d9fe2e9cfbf76638d61220d635dd31272e298cfbb`; target catalog SHA-256 `6779213e832ab27eeda1e7fb245f57ff8cb0d56707b5aa73a8f31ec483a620f2`; pose fixture file SHA-256 `38e169e1b8b59d77785470b44e5feca8dad78fce18bc6dab8459ffa3f867ae0e`; canonical fixture SHA-256 `df7ccb80e12121497a48f886f6d9c1aa29f82a91f5be9f73990914e682109061`.
- Artifact hashes: diagnostic source SHA-256 `29799dd47eae71dcf0cef844ff8f96a0a49adb487744680644dc0d5109204032`; retained report file SHA-256 `a13a999c8c8ca279e72bdd11bca79d6803b291600f0e1bdce152542e250a482a`; embedded canonical report SHA-256 `f88e2b40b980465857a64c9c7d1fe09cfb878db2012852ffad1965728f5de447`.
- Metrics: 24 development pose clusters, 5,400 rows, and nine offsets inside the selected 1 mm ring. Across those offsets there are 58 missed abstentions and 1,693 false abstentions. Seven poses and eight pose-target pairs contain any miss. `pose_diverse_development_016` with target `MINUS` contributes 27/58 misses (`46.5517%`) and repeats equally across all three lighting variants. The two highest-miss poses contribute 41/58 (`70.6897%`). The worst clustered offset is `(-1,+1) mm`, where the retained one-sided 95% missed-abstention UCB is `3.249097%`.
- Interpretation: the failure is correlated with specific pose-target geometry rather than a broad lighting-only breakdown. This explains the gap between passing row-level point metrics and the failed whole-pose bound. It does not establish that repairing the dominant clusters will generalize and does not justify changing the frozen threshold.
- Validation commands: `python -m ruff check software/ai/eval/diagnose_pose_cluster_development.py software/ai/tests/test_pose_cluster_development_diagnostic.py`; `python -m pytest -q software/ai/tests/test_pose_cluster_development_diagnostic.py`; plus the full AI, shared boundary, registry, maintained-document, evidence-scope, artifact, repository-health, source-footprint, release-integrity, readiness, and diff checks recorded with the completing commit.
- Validation result: four focused diagnostic tests passed; the final full AI suite passed 217 tests with two expected Windows symlink skips; 34 shared ModelMotionBatch ingress and conformance tests passed; the registry audit passed with 41 tracked/documented AI tests and 134 referenced paths. Ruff, maintained-doc, public-record, evidence-scope, repository-artifact, repository-health, source-footprint, release-integrity, readiness, and diff checks passed. Registry audit receipt file SHA-256 is `1dfa54ae24e180296eac6c49f586a2d1802d0afe07d0f8b2fa12e5a693eb202f`.
- Preserved failed validation: the first combined registry run failed one assertion because the maintained registry-count test still expected 40 tests after this increment added the 41st. The contemporaneous full AI run recorded `1 failed, 216 passed, 2 skipped`. The count assertion was updated to the audited inventory of 41, after which the full suite passed. No model, threshold, metric, report, or gate changed in response.
- Source footprint: 6,131 tracked files, 653,525,143 logical bytes, 4,890,152 governed duplicate bytes, and a 55,939,877-byte largest blob. The exact four-file ceiling increase covers only the analyzer, schema, aggregate report, and focused test.
- Hardware-write count: 0.
- Physical-movement count: 0.
- Physics-step count: 0; Isaac Sim was not opened.
- Limitations: this is one consumed synthetic development split drawn from correlated static states on one governed path. Failure identities are design evidence and are no longer eligible to select or evaluate v16. The diagnostic contains no physical camera, commissioned calibration, synchronized measured feedback, measured dilation, cable/hand obstruction capture, localization qualification, collision evidence, controller command, transport field, execution permit, or physical authority.
- Supersedes: none. V15 remains rejected, v14 remains consumed, and every untouched evaluation source remains closed.
- Next dependency: predeclare v16 with fresh train/development identities, source-interval group isolation, fresh pose neighborhoods around the diagnosed intervals, balanced failed-target coverage, and frozen architecture/training/bootstrap rules before rendering. Commission synchronized deterministic geometry projection and measured dilation in parallel. Open an untouched evaluation source only after the fresh clustered development gate passes.


### E-20261001-AI-491 — v16 grouped-neighborhood campaign is frozen before rendering

- Stage: S2/S3 synthetic target-visibility successor predeclaration.
- Lane: AI/model fixture, inert Isaac render contract, offline dataset policy, and tests only; no arm-lane or integration-gate status changed.
- Claim commit: `83a2fbaed74900cdc0dc2bce6993e2b3b024806a`.
- Implementation/predeclaration commit: `20be6d127db5d2d90cc3f31a4b889208992845df`.
- Change: froze a deterministic 320-pose fixture with 256 training and 64 development poses, balanced three-interval source blocks, a one-block buffer between splits, training-only coverage of all seven blocks implicated by E-490, exact exclusion of all 96 consumed v15 fractions, six fresh deterministic lighting identities, an empty evaluation split, and a v16 Isaac receipt/dataset contract. No rendering or model training occurred in this increment.
- Exact fixture command: `python software/ai/sim/build_grouped_neighborhood_training_fixture.py --source software/integrations/isaac_sim/evidence/actual_emitter_joint_schedule_bundle_9e5c878_20260929.json --v15-fixture software/ai/sim/evidence/pose_diverse_training_development_v1.json --v15-diagnostic software/ai/eval/pose_cluster_development_diagnostic_v1.json --output software/ai/sim/evidence/grouped_neighborhood_training_development_v1.json`.
- Frozen training plan: exact v15 model SHA-256 `9e09a13fae22cbbc75d2b15d9fe2e9cfbf76638d61220d635dd31272e298cfbb`; train `conv2`, `conditioner`, and `classifier` while keeping `conv1` frozen; 12 deterministic CPU epochs; learning rate `0.00015`; positive abstention weight `1.75`; weight decay `0.0001`; fixed `2.0` row emphasis for `MINUS`, `U`, `7`, `1`, `0`, `PERIOD`, and `6`. Development retains the 2% miss and 10% false-stop point and whole-pose UCB ceilings, 2,000 resamples, and bootstrap seed `19016`.
- Fixture metrics: canonical bundle SHA-256 `21af4a14ed154d2cecd07cc995ea6c497fd356ef85d9181cf012885f924b2fa5`; file SHA-256 `0e0f30a801a38720f0dc6ddc5b769c8447dda09a67a8577ddf37fd7fffb5abae`; 18 training blocks with 14 or 15 poses each; ten development blocks with six or seven poses each; all train/development block distances are at least two.
- Artifact SHA-256 values: fixture builder `e54073297e11805b863ffc8d5fb8eec8fa80d13c3e13cdc773633d20ebd64c07`; renderer `81c3ab21376fb119f0203b92a8cb3f7f936b670e9440145779e51f6d66291c6a`; dataset/training builder `511da032529bacbea3171b90a26d8079e5498bde6fd1beaee0e61b321d6cf31c`; fixture test `5df35d9c8005c6edd20d0f04f97195d48d7df4ed2068927299d57076f664e353`; renderer/dataset test `f96ec9ad8f7c7a8dda4fd9eccc192d1a3cd5e965ed8484b7f9086fb015bd1bbc`.
- Validation commands: `python -m pytest software/tests/unit/test_grouped_neighborhood_training_fixture.py software/tests/unit/test_isaac_fixed_overview_mesh_render_evidence.py software/ai/tests/test_ai_work_registry.py -q`; `python software/ai/eval/audit_ai_work_registry.py`; `git diff --check`.
- Validation result: 59 focused tests passed. Registry audit passed with 41 tracked/documented AI tests and 135 referenced paths; audit receipt SHA-256 is `44aa66be7e3b5a5fd4ab6651b1002767bb9b7ab3c2c1994a1f8b46c1c993ccda`.
- Preserved failed pre-artifact validation: the first generator invocation rejected an incorrect draft assumption of 121 source samples; the actual pinned source contains 133. After binding that exact count, the first allocation policy rejected development block 37 because it received only three rows against the frozen floor of four. The final deterministic balanced-block quota gives every development block six or seven rows. Neither failure produced a retained fixture, render, dataset, or model and no observed model metric changed the design.
- Hardware-write count: 0.
- Physical-movement count: 0.
- Physics-step count: 0; Isaac Sim was not opened.
- Limitations: all poses, geometry, labels, and planned lighting remain synthetic. Block isolation reduces adjacent-path leakage but does not create physical independence. V15 failure identities informed training neighborhoods and target emphasis, so v15 is consumed and cannot evaluate v16. This work does not qualify localization, camera calibration, synchronized feedback, dilation, collision, contact, deployment, controller transport, permits, or physical authority.
- Next dependency: implement the exact frozen v16 training entry point and its rejection tests, then run the committed Isaac campaign without changing identities or gates. Preserve any simulator failure as a separate result.


### E-20261001-AI-492 — v16 lowers the clustered miss bound but remains rejected

- Stage: S2/S3 synthetic target-visibility training and development-only selection.
- Lane: AI/model, inert Isaac rendering, offline dataset assembly, and offline training only; no arm-lane or integration-gate status changed.
- Claim commit: `83a2fbaed74900cdc0dc2bce6993e2b3b024806a`.
- Frozen fixture/render predeclaration commit: `20be6d127db5d2d90cc3f31a4b889208992845df`.
- Training implementation and repairs: `b68a6cb2a2596768f2c4941970efedbd942e74f8` added the entry point; `a77ee493ebb9b2f50e9177bca87653cb025ce986` restored the module's original LF representation after Windows rewrote its line endings; `ce6172b8b43a22613d3eaf128cc80873423e076a` corrected the copied seed assertion to the exact failed v15 1 mm policy. The combined functional diff remains the frozen v16 implementation; no observed metric changed its poses, lighting, architecture, weights, epochs, gates, or bootstrap seed.
- Exact render command: `$env:OMNI_KIT_ACCEPT_EULA='YES'; $env:PYTHONPATH=(Resolve-Path 'software/src').Path; C:\IsaacSim\env_6_1_0\Scripts\python.exe software\integrations\isaac_sim\isaac_fixed_overview_mesh_render_probe.py --workspace . --upstream-repo C:\IsaacSim\sources\roarm_ws-40dbd84 --mesh-receipt software\integrations\isaac_sim\evidence\roarm_m3_upstream_link_meshes_20260929.json --capsule-manifest software\integrations\isaac_sim\evidence\fixed_overview_segmentation_v1\manifest.json --schedule-bundle software\ai\sim\evidence\grouped_neighborhood_training_development_v1.json --campaign grouped-neighborhood-training-v16 --output-dir C:\IsaacSim\artifacts\issue190\fixed-overview-grouped-v16-run1 --receipt C:\IsaacSim\evidence\fixed_overview_grouped_v16_run1.json --status-output C:\IsaacSim\evidence\fixed_overview_grouped_v16_run1.status.json`.
- Exact dataset command: `Copy-Item -LiteralPath C:\IsaacSim\evidence\fixed_overview_grouped_v16_run1.json -Destination C:\IsaacSim\artifacts\issue190\fixed-overview-grouped-v16-run1\manifest.json; python software\ai\train\build_official_mesh_occlusion_data.py --source-manifest C:\IsaacSim\artifacts\issue190\fixed-overview-grouped-v16-run1\manifest.json --output-dir C:\IsaacSim\artifacts\issue190\grouped-neighborhood-data-v1`; repeated unchanged with output suffix `v2`.
- Exact training command: `python software\ai\train\build_official_mesh_occlusion_data.py --source-manifest C:\IsaacSim\artifacts\issue190\fixed-overview-grouped-v16-run1\manifest.json --train-grouped-neighborhood-successor C:\IsaacSim\artifacts\issue190\grouped-neighborhood-data-v1 C:\IsaacSim\artifacts\issue190\pose-diverse-candidate-v1 C:\IsaacSim\artifacts\issue190\grouped-neighborhood-candidate-v1`.
- Render result: `PASS_WITH_BLOCKERS`; 320 static poses; 256 training, 64 development, zero evaluation; 60 chunked atlas artifacts; canonical receipt SHA-256 `576e6512a2c27d33773957592805499975895edb162537b457ed198caa514bab`; receipt file SHA-256 `8e54e4f8b9e58b4a11c986678e410724c1b0d929904d4229bb31b1c8f63a4043`; status file SHA-256 `d758476ede52f3602aa6fffce93760cc73798075fa0d87c8d8d63e4ebaf5758b`.
- Dataset result: both independent 964-file trees are byte identical, contain 159,025,407 bytes, and have inventory SHA-256 `d0debf41b369f851e2691a516790675ade74589266b54ddc33d224608f2a2562`. Canonical dataset SHA-256 is `7a7521d7fdad19b33f86261c3f30560b101d720538e8d994fd9852e7901d32a8`; manifest file SHA-256 is `17c18d1d2189b5f79bfdbdcda84a1ec47b1174ea349db27b05d9e98309614204`. Training has 57,600 rows with 8,994 abstentions and 48,606 visible labels; development has 14,400 rows with 2,118 abstentions and 12,282 visible labels; evaluation is empty.
- Model result: model file SHA-256 `af917bb4ecc0aa07de904b44e0c78f1afda4ebf64d5629dddb09f064d0cd7969`; scorecard file SHA-256 `ef03701d5841dafb15537cfbd34e5b0e6b4046583e8689dc30e185e5e7a7bbab`; canonical scorecard SHA-256 `ec11ca7302901c7051ef5aadae2d0df7833f58f30cf4d8c0f0e8b92f74c3ec38`. Twelve epoch losses decreased monotonically from `0.0780796` to `0.0550298`.
- Metrics: selected threshold `0.138`; selected synthetic offset ring 2 mm. Nominal development confusion is 2,106 true abstentions, 12 missed abstentions, 12,049 true-visible decisions, and 233 false abstentions: `12/2118 = 0.5666%` misses and `233/12282 = 1.8971%` false stops. Point metrics pass. The authoritative 2,000-resample 64-pose bootstrap with seed `19016` evaluated all 17 declared offsets through 2 mm and reports worst missed-abstention UCB `2.821616%` and worst false-abstention UCB `7.802481%`. The miss UCB exceeds the 2% ceiling; `pose_cluster_upper_bound_gate_met=false`, `development_gate_met=false`, and promotion status is `FAILED_DEVELOPMENT_GATE`.
- Interpretation: v16's clustered miss bound is directionally lower than v15's `3.249097%`, but the development corpora differ, so this is not a controlled head-to-head improvement claim. The 2 mm point result is not installable calibration or runtime qualification.
- Validation commands: `python -m ruff check software/ai/sim/build_grouped_neighborhood_training_fixture.py software/integrations/isaac_sim/isaac_fixed_overview_mesh_render_probe.py software/ai/train/build_official_mesh_occlusion_data.py software/tests/unit/test_grouped_neighborhood_training_fixture.py software/tests/unit/test_isaac_fixed_overview_mesh_render_evidence.py`; `python -m pytest software/tests/unit/test_grouped_neighborhood_training_fixture.py software/tests/unit/test_isaac_fixed_overview_mesh_render_evidence.py -q`; `python -m pytest software/ai/tests -q`; `python -m pytest software/tests/unit/test_model_motion_ingress_v2.py software/tests/integration/test_model_arm_conformance_profile_v1.py -q`; `git diff --check`.
- Validation result: 53 focused fixture/render/training tests passed; 217 AI tests passed with two expected Windows symlink skips; 34 shared ModelMotionBatch ingress/conformance tests passed; Ruff and diff checks passed.
- Preserved failed evidence: the first training invocation produced no model or scorecard and failed seed admission because the new entry point asserted 2 mm while the exact rejected v15 seed records 1 mm. The assertion was corrected to the retained seed identity before rerunning. The initial training-entry commit also rewrote the large module's line endings on Windows; `git diff --check` reported the full-file trailing-whitespace churn, and the next commit restored LF bytes. The predeclaration prose said "nine declared offsets" too broadly; the committed selector has always evaluated every offset in the selected ring, so v16 conservatively scored 17 offsets at 2 mm. These failures and discrepancy did not change the experiment after model evidence was observed.
- Hardware-write count: 0.
- Physical-movement count: 0.
- Physics-step count: 0; all arm states were placed as static perception renders.
- Limitations: all camera geometry, placement, images, masks, labels, target coordinates, and lighting are synthetic. Source-block separation reduces adjacent-path leakage but does not make poses independent. The model addresses residual target visibility only; deterministic synchronized geometry projection remains primary for known self-occlusion. Tool/support meshes, commissioned calibration, measured feedback, measured dilation, physical lighting, cables, hands, localization qualification, collision, contact, and deployment evidence remain absent. No controller command, joint output, transport field, permit, or physical authority was created.
- Supersedes: none. V14 evaluation, v15 development, and v16 development are consumed and cannot select or evaluate another successor.
- Next dependency: keep v16 rejected. Diagnose its development failures by pose, target, lighting, and offset without altering the checkpoint. In parallel, commission the deterministic synchronized geometry path and physical parked-pose evidence. Any learned successor requires a new frozen train/development design and a later untouched evaluation source only after its clustered development gate passes.


### E-20261001-AI-493 — v16 failures are distributed across pose geometry

- Stage: S2/S3 synthetic development-only diagnostic.
- Lane: AI/model read-only attribution only; no arm-lane or integration-gate status changed.
- Claim commit: `07b941ed1f98a425a514b1dd7bfca8b48b9a9fe7`.
- Implementation commit: `bc880ad9087d18b99becf7c4db765d8b77edb026`.
- Change: added a strict, deterministic diagnostic that reconciles the rejected v16 dataset manifest, development rows, scorecard, and frozen pose fixture, then attributes every in-bound missed and false abstention by exact offset, pose, target, lighting identity, and source block. It rejects non-v16 schemas, a nonfailed candidate, evaluation rows, identity/hash mismatches, and any nonzero effect or authority claim. It does not load images, run inference, train, render, select a threshold, open evaluation, or promote the candidate.
- Exact command: `python software/ai/eval/diagnose_grouped_neighborhood_development.py --dataset-manifest C:\IsaacSim\artifacts\issue190\grouped-neighborhood-data-v1\manifest.json --development-rows C:\IsaacSim\artifacts\issue190\grouped-neighborhood-data-v1\development.jsonl --scorecard C:\IsaacSim\artifacts\issue190\grouped-neighborhood-candidate-v1\scorecard.json --pose-fixture software/ai/sim/evidence/grouped_neighborhood_training_development_v1.json --output software/ai/eval/grouped_neighborhood_development_diagnostic_v1.json`; repeated unchanged with `%TEMP%\grouped_neighborhood_development_diagnostic_v1_second.json`.
- Bound input SHA-256 values: dataset manifest file `17c18d1d2189b5f79bfdbdcda84a1ec47b1174ea349db27b05d9e98309614204`; canonical dataset `7a7521d7fdad19b33f86261c3f30560b101d720538e8d994fd9852e7901d32a8`; development rows file `13beb5470db53da2a2e517945a0e519d77a5375ec010c3da10a485567708de9c`; scorecard file `ef03701d5841dafb15537cfbd34e5b0e6b4046583e8689dc30e185e5e7a7bbab`; canonical scorecard `ec11ca7302901c7051ef5aadae2d0df7833f58f30cf4d8c0f0e8b92f74c3ec38`; model `af917bb4ecc0aa07de904b44e0c78f1afda4ebf64d5629dddb09f064d0cd7969`; target catalog `6779213e832ab27eeda1e7fb245f57ff8cb0d56707b5aa73a8f31ec483a620f2`; fixture file `0e0f30a801a38720f0dc6ddc5b769c8447dda09a67a8577ddf37fd7fffb5abae`; canonical fixture `21af4a14ed154d2cecd07cc995ea6c497fd356ef85d9181cf012885f924b2fa5`.
- Artifact SHA-256 values: analyzer `a26c72f37b0150ccb35c236b01634e7ff1f7c3f0976b98ec7e963802b8b58df9`; report file `67a8a19915fa60fa35bbcb96794c007e69c013d19958d7d9e3401829da860374`; canonical report `4846c8ce7d281e647d6d68f75f44a8cde8fff6d40558ec22a8336658d56ccecc`; schema `035b535b0a0837755fb7909dc658f56855f6df3f402c115316a31700a5fa62ee`; tests `a0aa75e7a8c41a1ca4c92b44e073bea94224ba6d8f969258d100adc22105418a`; registry `a24de29ee1165d3eccb0c05d7db877096a46696c152f0b1a2a899f1511d83941`; registry audit file `e28bbd6adfd0a231c7fc531839d633524cd9690f9ec4f04195e752082bc3c276`; registry audit receipt `d24707447286b8d070964688ae050ac5a6712b9a735fc0691e157e731d077ae5`.
- Metrics: 64 development poses; 14,400 rows; 17 in-bound offsets; 348 missed abstentions across offsets; 6,243 false abstentions across offsets; 28 poses, 46 pose-target pairs, and eight source blocks with a miss. The dominant pose-target is `grouped_development_064` / `P` with 41 misses (`11.781609%`). Source block 37 has 93 misses (`26.724138%`); the top three source blocks have 264 of 348 (`75.862069%`). Target miss totals are `EQUAL=63`, `MINUS=63`, `P=63`, `I=53`, `R=28`, `4=15`, `5=15`, `APOSTROPHE=13`, `9=10`, `COMMA=7`, `M=7`, `T=7`, and `SPACE=4`. Lighting totals are `grouped_overhead_low=131`, `grouped_side_glare=95`, and `grouped_soft_focus=122`. The worst clustered miss offset is `(-2 mm, 0 mm)`, with miss UCB `0.028216164514586323` and false-stop UCB `0.019722425127830533`.
- Interpretation: the failures are more distributed than v15 and indicate a broad pose-geometry/generalization problem rather than one dominant key pair. This is diagnostic evidence, not a controlled model-improvement claim, and it does not justify changing the frozen threshold.
- Validation commands: two exact diagnostic commands above followed by byte comparison; `python -m pytest software/ai/tests/test_grouped_neighborhood_development_diagnostic.py software/ai/tests/test_ai_work_registry.py -q`; `python -m pytest software/ai/tests -q`; `python -m pytest software/tests/unit/test_model_motion_ingress_v2.py software/tests/integration/test_model_arm_conformance_profile_v1.py -q`; `python -m ruff check software/ai/eval/diagnose_grouped_neighborhood_development.py software/ai/tests/test_grouped_neighborhood_development_diagnostic.py`; `python software/ai/eval/audit_ai_work_registry.py --output software/ai/eval/ai_work_registry_audit_v1.json`; `git diff --check`.
- Validation result: repeated reports were byte identical; 10 focused diagnostic/registry tests passed; all 221 AI tests passed with two expected Windows symlink skips; all 34 shared ingress/conformance tests passed; Ruff and diff checks passed; registry audit passed with 42 tracked/documented AI tests and 139 referenced paths.
- Preserved failed evidence: before the retained report existed, the first focused test run produced `1 failed, 3 passed`; the report-loading test failed closed with `FileNotFoundError`. The report was then generated through the intended command, after which the focused suite passed. No model, threshold, split, policy, or authority changed in response.
- Hardware-write count: 0.
- Physical-movement count: 0.
- Physics-step count: 0; Isaac Sim was not opened.
- Limitations: this analyzes one consumed synthetic development split and correlated static visual states. Failure concentration is not an unbiased generalization estimate. It contains no physical camera, commissioned calibration, synchronized measured feedback, measured dilation, physical lighting, tool/cable/hand evidence, localization qualification, collision evidence, controller command, transport field, permit, deployment qualification, or physical authority.
- Supersedes: none. V16 remains rejected; v14 evaluation and v15/v16 development remain consumed.
- Next dependency: keep v16 rejected and preserve its threshold. Prioritize the synchronized deterministic geometry path for known self-occlusion. If another learned successor is attempted, freeze fresh group-isolated train/development identities, architecture, training, bootstrap, and asymmetric gates before rendering, and do not open an untouched evaluation source until its clustered development gate passes.


### E-20261001-AI-494 — geometry-first fusion closes synthetic v16 misses by construction

- Stage: S2/S3 synthetic development-only architecture replay.
- Lane: AI/model read-only mask reconciliation and fusion replay; no arm-lane or integration-gate status changed.
- Claim commit: `e2cb582a0f0400ac2d2d9f6446da399d5735836b`.
- Implementation commit: `a576f6658acf7ccab6da067fcce4f6ee152ac962`.
- Change: added a deterministic replay that verifies the retained v16 Isaac source receipt, dataset, development rows, rejected scorecard, target catalog, and four development robot-mask atlases; independently rerasterizes every target safe polygon against the atlas crop; reconciles 4,800 pose-target overlaps and 14,400 lighting rows; reconstructs learned decisions from every scorecard failure identity; and applies conservative geometry OR learned abstention at every frozen offset inside 2 mm. It opens no evaluation source and performs no render, training, threshold selection, or promotion.
- Exact command: `python software/ai/eval/replay_geometry_first_fusion_development.py --source-manifest C:\IsaacSim\artifacts\issue190\fixed-overview-grouped-v16-run1\manifest.json --dataset-manifest C:\IsaacSim\artifacts\issue190\grouped-neighborhood-data-v1\manifest.json --development-rows C:\IsaacSim\artifacts\issue190\grouped-neighborhood-data-v1\development.jsonl --scorecard C:\IsaacSim\artifacts\issue190\grouped-neighborhood-candidate-v1\scorecard.json --output software/ai/eval/geometry_first_fusion_replay_v1.json`; repeated unchanged with `%TEMP%\geometry_first_fusion_replay_v1_second.json`.
- Bound source SHA-256 values: Isaac manifest file `8e54e4f8b9e58b4a11c986678e410724c1b0d929904d4229bb31b1c8f63a4043`; canonical Isaac receipt `576e6512a2c27d33773957592805499975895edb162537b457ed198caa514bab`; dataset manifest file `17c18d1d2189b5f79bfdbdcda84a1ec47b1174ea349db27b05d9e98309614204`; canonical dataset `7a7521d7fdad19b33f86261c3f30560b101d720538e8d994fd9852e7901d32a8`; development rows `13beb5470db53da2a2e517945a0e519d77a5375ec010c3da10a485567708de9c`; scorecard file `ef03701d5841dafb15537cfbd34e5b0e6b4046583e8689dc30e185e5e7a7bbab`; canonical scorecard `ec11ca7302901c7051ef5aadae2d0df7833f58f30cf4d8c0f0e8b92f74c3ec38`; model `af917bb4ecc0aa07de904b44e0c78f1afda4ebf64d5629dddb09f064d0cd7969`; target catalog `6779213e832ab27eeda1e7fb245f57ff8cb0d56707b5aa73a8f31ec483a620f2`; mask atlases `c4e33e0b4b686aaed688abe39a81d0f54638351de2d2b9ba7beb7cc58a4235ab`, `215622ca38eb246d487057a800180f5e76f7ed5ad3232952798b3c756ddd09a4`, `81d1b96a34e2eea4480cc396cc3cf7212003ec34a1d2297d6116e9bdf24565fc`, and `587e3ed2ddbe9380ac67e5276822b7c98af8d6eae332f12f70a4dbd075cde513`.
- Artifact SHA-256 values: replay tool `b165034b89d390ba1d211ce9b8676bd9b547fbd502d14ccbe7d7e08461ad0f9d`; report file `e25faa568fe6600bc0ab866cf14bd9074e9e0b946c00cc968af1c7c84366d8fc`; canonical report `737f923ae835b6a3b07ca573014f030c5f47707414ef2f55eb575783fc5816c9`; schema `7b4bf3d66240274711c3cba2cccf0ee119be874ca9928fd96f9d18717eb3b9fd`; tests `600a5473acf3fbcb1540af6d7c5df074cb2131c2853bb1c6069517a85d9f4dcc`; registry file `73c012023c136f7d605219d7a36ea62180579eb4b6b50d7f86516e7e25c8ecbb`; canonical registry `98b372fa10e1b00114ba093426cbf83dcbc6fd46d615251623d843e2c2a16718`; registry audit file `0b4cc2adcac2f8df280bda1e39939d79a519e19d2a6d4ed649a0a82e17a69a25`; registry audit receipt `59ce2627525fab7117a7f11fc95c003351d026e46c06590d5f4b407d7a86df3b`.
- Nominal result: learned confusion is 2,106 true abstentions, 12 misses, 12,049 true visible decisions, and 233 false stops. Conservative fusion is 2,118 true abstentions, zero misses, 12,049 true visible decisions, and 233 strict false stops. Fifteen strict geometry false stops are inside the frozen ambiguity band and are already a subset of learned false stops. Accepting either answer for those rows gives 218 nominal false stops (`1.7750%`).
- Ring result: all 17 offsets through the selected 2 mm ring have zero fused misses. Worst strict fused false stops are 881 of 12,282 visible rows (`7.1731%`); worst ambiguity-accepted fused false stops are 866 (`7.0510%`). The report retains all 54 ambiguity-band row identities rather than excluding them. These are point replay counts, not a new clustered qualification or gate pass.
- Interpretation: the result verifies the architecture seam and conservative OR behavior. It does not demonstrate independent accuracy because the retained Isaac semantic mask is also the source of the synthetic truth label. The zero misses therefore occur by construction when the exact source geometry is available. V16 remains rejected as a learned checkpoint and is not a residual-obstruction model.
- Validation commands: two exact replay commands above followed by byte comparison; `python -m pytest software/ai/tests/test_geometry_first_fusion_replay.py software/ai/tests/test_ai_work_registry.py -q`; `python -m pytest software/ai/tests -q`; `python -m pytest software/tests/unit/test_model_motion_ingress_v2.py software/tests/integration/test_model_arm_conformance_profile_v1.py -q`; `python -m ruff check software/ai/eval/replay_geometry_first_fusion_development.py software/ai/tests/test_geometry_first_fusion_replay.py software/ai/tests/test_ai_work_registry.py`; `python software/ai/eval/audit_ai_work_registry.py --output software/ai/eval/ai_work_registry_audit_v1.json`; `git diff --check`.
- Validation result: repeated retained reports are byte identical; 11 focused replay/registry tests passed; all 226 AI tests passed with two expected Windows symlink skips; all 34 shared ingress/conformance tests passed; Ruff and diff checks passed; registry audit passed with 43 tracked/documented AI tests and 143 referenced paths.
- Preserved failed evidence: the first real-artifact invocation failed closed because the draft source-schema constant did not match the exact retained v16 schema; the constant was corrected to `tactevra.isaac_fixed_overview_mesh_render.v16` before producing the report. The first combined focused run produced `1 failed, 10 passed` because the registry paths were updated before its canonical hash; regenerating the canonical registry hash resolved that expected integrity failure. A subsequent `git diff --check` exposed a Windows text-mode CRLF rewrite of the registry; the file was restored to LF bytes without changing its JSON content.
- Hardware-write count: 0.
- Physical-movement count: 0.
- Physics-step count: 0; Isaac Sim was not opened and only retained atlas bytes were read.
- Limitations: no measured dilation, commissioned camera calibration, camera-to-board transform, exposure-time measured-feedback bracket, qualified interpolation, tool/support mesh, cable, hand, glare truth, physical image, localization qualification, collision evidence, controller command, transport field, permit, deployment qualification, or physical authority is present. The existing learned checkpoint detects synthetic self-occlusion and cannot be treated as the future residual-obstruction model.
- Supersedes: none. V16 remains rejected and every consumed dataset remains consumed.
- Next dependency: commission the geometry producer against exposure-synchronized measured servo feedback and independently measured dilation, then collect parked-pose physical originals and synthetic residual-obstruction cases for cable, tool, hand, glare, and degradation. Train or select the residual path only on a separately frozen design; retain conservative OR fusion and open no untouched evaluation until its clustered development gate passes.


### E-20261001-AI-495 — residual-obstruction pretraining is frozen before crop generation

- Stage: S2/S3 synthetic parked residual-obstruction pretraining predeclaration.
- Lane: AI/model fixture and offline model plan only; no arm-lane or integration-gate status changed.
- Claim commit: `5efc901ae7271218c562f45cd995f1710e9f62e9`.
- Implementation/predeclaration commit: `7e0509d0828a557c04a38aef47fc51c49dea70c8`.
- Change: added a strict deterministic fixture builder, schema, retained fixture, and tests. The builder binds the exact fixed-camera practice manifest, corpus, target catalog, and `hover_t__nominal` / `hover_e__nominal` image hashes; preserves the same ordered 75-target catalog across splits; assigns eight cases per target; freezes crop geometry, procedural obstruction parameters, the small offline model plan, and asymmetric target-cluster development gates; and rejects source mutation, mixed target catalogs, authority, or physical effects. It emits specifications only and does not generate crop images, train, open evaluation, or create motion authority.
- Exact command: `python software/ai/sim/build_residual_obstruction_campaign_fixture.py --source-manifest software/integrations/isaac_sim/evidence/fixed_fixture_practice_v1/manifest.json --output software/ai/sim/evidence/residual_obstruction_pretraining_v1.json`; repeated unchanged with `%TEMP%\residual_obstruction_pretraining_v1_second.json`.
- Bound source SHA-256 values: source manifest file `a529ffbdc39aff5450d0378f2e3020c83b398a3e7f853b0ef4e957748e34c7fd`; canonical source corpus `03e2d3d7ac2d3a0026b2c24cb0a9d709190794e1adb5b69e038374fa46f152e4`; source generator `b364906e0798c4f032bf2e329041a775a008e5ee7aa7a23ee0b1c83e0cb90163`; target catalog `6779213e832ab27eeda1e7fb245f57ff8cb0d56707b5aa73a8f31ec483a620f2`; training source image `2b6f4d49da7e28e78e9ca900d1f4133432b88d44ec7c9b8bc70f9fe98eed1e92`; development source image `d0f3802c9035a4e3f8141dad87bcfa6a89930f3d009d926927b3378de923418b`.
- Artifact SHA-256 values: fixture builder `e677f04193ebcfc764fbc0a06a9ff5bb638e1292c4c2161bb0ad252fdc37aa34`; retained fixture file `c6588a42e9e2e48c28773e09290a04eb7fc940eb5a83349185d17e3243c59602`; canonical fixture `06f3972c71fa4132083cd963285824d49577eaf933cab4e411da84224a2ebfef`; schema `37673f358a670953d1c326148c60d8121f50486e3af9c832823aff8c63e7786b`; tests `1497eba96fec207f84fabaa515ec459b011b9d0b5846cac5e7542d37d32ee207`; registry file `dea5db40e4bb0262088acd79814462a18642d27ca78cce40e6e76bdebf7bd822`; canonical registry `5197d76e8e66f3f19c347953574b334989adf48475802ffa12f4850788966c72`; registry audit file `c1c99b0f7a4a1c35121d29cffbab79f143dfb5e8988fd2b4280e1a6a5f6f437f`; registry audit receipt `5e6fcbe98c9d38c0c12ad48c747f733c66791ae391f4e1b1076e74ae2a200d9e`.
- Frozen inventory: 1,200 specifications total; training has 600 rows with 150 visible and 450 abstention labels; development has 600 rows with 150 visible and 450 abstention labels; evaluation has zero rows. Each split contains all 75 targets and exactly one clear, adjacent-distractor, cable, tool, hand, foreign-object, glare, and degradation case per target. Training uses only `hover_t`; development uses only `hover_e`.
- Frozen model and gate: `target_crop_residual_cnn_v1`, channels `[16,32,64]`, 12 epochs, batch 64, learning rate `0.0005`, weight decay `0.0001`, seed `19017`, thresholds `0.05` through `0.95` by `0.05`; point and 2,000-resample target-cluster upper bounds must both pass 2% missed abstentions and 10% visible false stops. Evaluation remains unopened.
- Validation commands: two exact fixture commands above followed by SHA-256 comparison; `python -m pytest software/ai/tests/test_residual_obstruction_campaign_fixture.py software/ai/tests/test_ai_work_registry.py -q`; `python -m pytest software/ai/tests -q`; `python -m pytest software/tests/unit/test_model_motion_ingress_v2.py software/tests/integration/test_model_arm_conformance_profile_v1.py -q`; `python -m ruff check software/ai/sim/build_residual_obstruction_campaign_fixture.py software/ai/tests/test_residual_obstruction_campaign_fixture.py software/ai/tests/test_ai_work_registry.py`; `python software/ai/eval/audit_ai_work_registry.py --output software/ai/eval/ai_work_registry_audit_v1.json`; `python scripts/ci/check_docs.py`; `python scripts/ci/check_public_records.py`; `python scripts/ci/check_evidence_scope.py`; `python scripts/ci/check_repository_artifacts.py`; `python scripts/ci/check_repository_health.py --policy-only`; `python scripts/ci/check_source_archive_footprint.py --json`; `python scripts/ci/check_release_integrity.py --mode policy`; `python scripts/ci/check_release_readiness_sync.py`; `git diff --check`.
- Validation result: repeated fixtures were byte identical; 11 focused fixture/registry tests passed; all 231 AI tests passed with two expected Windows symlink skips; all 34 shared ingress/conformance tests passed; Ruff and all repository governance checks passed. The registry audit covers 44 tracked/documented AI tests and 147 referenced paths. Source footprint is 6,146 tracked files, 655,127,539 logical bytes, 4,890,152 governed duplicate bytes, and a 55,939,877-byte largest blob.
- Hardware-write count: 0.
- Physical-movement count: 0.
- Physics-step count: 0; Isaac Sim was not opened.
- Limitations: this is a synthetic procedural design over only two correlated retained views with simplified surfaces and an unmeasured camera. It contains no generated crop dataset, trained model, measured metric, untouched evaluation, physical camera, commissioned calibration, synchronized feedback, measured dilation, real cable/tool/hand/glare evidence, localization qualification, collision evidence, controller command, transport field, permit, deployment qualification, or physical authority. Pose separation between two views does not establish physical or statistical independence.
- Supersedes: none. V16 remains rejected; the geometry-first seam remains primary for known self-occlusion; every evaluation source remains closed.
- Next dependency: generate the exact frozen crops outside this fixture, inventory and hash them independently, train only the declared model, and apply the target-cluster development gate without opening evaluation. Commission exposure-synchronized measured-feedback projection, measured dilation, and physical parked-pose originals in parallel.


### E-20261001-AI-496 — first residual-obstruction candidate fails development

- Stage: S2/S3 synthetic parked residual-obstruction crop generation, offline training, and development-only selection.
- Lane: AI/model external dataset and model artifacts plus retained development scorecard; no arm-lane or integration-gate status changed.
- Claim commit: `b1279e50471ad18f16dc36a4265f17b10314c470`.
- Implementation commit: `cf7aa8613876ae1b4c70f73b8322cf8007b4367e`.
- Change: added one deterministic materialize/verify/train entry point, a strict retained-result schema, a retained failed scorecard, and focused tests. It materializes only the 1,200 specifications frozen by E-495, independently verifies exact regular-file hashes and inventory, trains only `target_crop_residual_cnn_v1` with the frozen 12-epoch plan, scores every declared threshold with the frozen 2,000-resample target-cluster bootstrap, rejects missing/extra/changed files, and opens no evaluation source. Generated images and model bytes remain external hashed artifacts.
- Exact materialization commands: `python software/ai/train/build_residual_obstruction_pretraining.py materialize --fixture software/ai/sim/evidence/residual_obstruction_pretraining_v1.json --source-manifest software/integrations/isaac_sim/evidence/fixed_fixture_practice_v1/manifest.json --output-dir C:\IsaacSim\artifacts\issue190\residual-obstruction-data-v1`; repeated unchanged with output suffix `v2`.
- Exact verification commands: `python software/ai/train/build_residual_obstruction_pretraining.py verify --fixture software/ai/sim/evidence/residual_obstruction_pretraining_v1.json --dataset-dir C:\IsaacSim\artifacts\issue190\residual-obstruction-data-v1`; repeated unchanged with dataset suffix `v2`.
- Exact training commands: `python software/ai/train/build_residual_obstruction_pretraining.py train --fixture software/ai/sim/evidence/residual_obstruction_pretraining_v1.json --dataset-dir C:\IsaacSim\artifacts\issue190\residual-obstruction-data-v1 --output-dir C:\IsaacSim\artifacts\issue190\residual-obstruction-candidate-v1 --retained-report software/ai/eval/residual_obstruction_development_v1.json`; repeated unchanged with dataset and candidate suffix `v2` and without rewriting the retained report.
- Dataset result: both 1,201-file trees are byte identical, contain 7,747,442 bytes, and have manifest file SHA-256 `32f2264cabb7833f3d2cee13d9ab7fcdcca91d7b75ba1e9dc1221dfc29800aa7`. Canonical dataset SHA-256 is `a6188e5ae191e2bfc71dae37ee26f174d5a056d3d4958ae7c2f472ef9bff2830`; inventory SHA-256 is `9dbbe3bb397f85fff576b68b80610901b5f3ab5d6a07cea501a3780dcd273a7d`. Each tree contains 600 training and 600 development PNG crops; evaluation has zero rows.
- Model result: both 95,797-byte model files are byte identical with SHA-256 `90d32245902a20653e829627772d78604bd8c11880bc5be1c54bf14343831946`. Both scorecards are byte identical with file SHA-256 `d2197eb2292c4ed603132dc3aa1ee06d40ce910382b9c9e74bfafac06c457a29` and canonical result SHA-256 `c04f8dc67ba09fa4fc582b85d1b186c13d9c0dafa7855d41545c193a568a6573`. Training loss decreases from `0.6869502171` to `0.5415630054` across 12 epochs.
- Development result: `FAILED_DEVELOPMENT_GATE`; no threshold was selected. Thresholds `0.05` through `0.65` detect every obstruction but falsely stop every visible row. At `0.75`, 126/450 obstructions are missed (`28.0%`, target-cluster upper bound `32.6667%`) and 40/150 visible rows falsely stop (`26.6667%`, upper bound `36.0%`). At `0.80`, misses are 363/450 (`80.6667%`, upper bound `85.5556%`) while false stops are 2/150 (`1.3333%`, upper bound `4.0%`). No declared threshold meets both 2% and 10% point and clustered limits. Threshold adjustment cannot repair this candidate.
- Artifact SHA-256 values: pipeline `7b61d7b5e0615089fcff0cec6dca379e55cb41e556c29388f55361bb7ef17532`; retained scorecard `d2197eb2292c4ed603132dc3aa1ee06d40ce910382b9c9e74bfafac06c457a29`; schema `80f66959bc82dba51a49e34deb7e3d8a4409b53b63d2c1d3f0a60437931662da`; tests `16b4c6b1d43d89569c9ced209b28c02db588403d359761fc49cb0e3d86d63211`; registry file `ba87dc6c6291a725fa497f3b1fbd5c78a97efdce93847628bcdcf9372b64ba55`; canonical registry `3a09abbdee0259f4451a041f967586751036427cfcb50ae547f1620d814f748b`; registry audit file `e48affd50cc33dd1214f6b0e3fea945b50b2c4ee7579533ac9d4e66acb6d1a27`; registry audit receipt `f6b09fbba2a3f082658c1540a2c8c180c45f3f0fa321f1e1d98e1d38e3bc034b`.
- Validation commands: the exact generation, verification, and training commands above; `python -m pytest software/ai/tests/test_residual_obstruction_pretraining.py software/ai/tests/test_ai_work_registry.py -q`; `python -m pytest software/ai/tests -q`; `python -m pytest software/tests/unit/test_model_motion_ingress_v2.py software/tests/integration/test_model_arm_conformance_profile_v1.py -q`; `python -m ruff check software/ai/train/build_residual_obstruction_pretraining.py software/ai/tests/test_residual_obstruction_pretraining.py software/ai/tests/test_ai_work_registry.py`; `python software/ai/eval/audit_ai_work_registry.py --output software/ai/eval/ai_work_registry_audit_v1.json`; `python scripts/ci/check_docs.py`; `python scripts/ci/check_public_records.py`; `python scripts/ci/check_evidence_scope.py`; `python scripts/ci/check_repository_artifacts.py`; `python scripts/ci/check_repository_health.py --policy-only`; `python scripts/ci/check_source_archive_footprint.py --json`; `python scripts/ci/check_release_integrity.py --mode policy`; `python scripts/ci/check_release_readiness_sync.py`; `git diff --check`.
- Validation result: the two datasets, models, and scorecards are byte identical; 11 focused pipeline/registry tests passed; all 236 AI tests passed with two expected Windows symlink skips; all 34 shared ingress/conformance tests passed; Ruff and repository governance checks passed. Registry audit covers 45 tracked/documented AI tests and 151 referenced paths. Source footprint is 6,150 tracked files, 655,176,760 logical bytes, 4,890,152 governed duplicate bytes, and a 55,939,877-byte largest blob.
- Hardware-write count: 0.
- Physical-movement count: 0.
- Physics-step count: 0; Isaac Sim was not opened and all work was offline image processing and CPU training.
- Limitations: this is a failed synthetic development result over two correlated practice views, simplified surfaces, deterministic image-space proxies, and an unmeasured camera. It contains no untouched evaluation, physical obstruction image, commissioned calibration, measured feedback, measured dilation, localization qualification, collision evidence, controller command, transport field, permit, deployment qualification, or physical authority. The development split is consumed and cannot select a repaired successor.
- Supersedes: none. The candidate is rejected, V16 remains rejected, the geometry-first seam remains primary for known self-occlusion, and every evaluation source remains closed.
- Next dependency: diagnose the consumed development probabilities by obstruction variant and target without changing the checkpoint or threshold. Use that diagnosis only to predeclare a fresh pose- and appearance-diverse residual campaign. Continue exposure-synchronized measured-feedback projection, measured dilation, and physical parked-pose originals in parallel.


### E-20261002-AI-497 — residual failure spans every target and includes duplicate distractor crops

- Stage: S2/S3 consumed synthetic development-only diagnosis after the failed residual gate.
- Lane: AI/model read-only model reconstruction and failure attribution; no arm-lane or integration-gate status changed.
- Claim commit: `126db9ede1d6f7a057abd53e58493505257cae4a`.
- Implementation commits: `343b4b548bb9b92745af71bd6d7cf4cd50c607cd` adds the exact model decoder, diagnostic, schema, retained report, registry, and tests; `60fcebe9513f449f6c93c8e3dd44b96e12506312` retains the independently discovered clear/distractor byte-identity count in that report and schema. Neither commit changes the checkpoint, threshold grid, dataset, or evaluation state.
- Change: the diagnostic verifies the frozen fixture, exact 1,200-file dataset inventory, rejected scorecard, and model hash; decodes the deterministic model artifact; reconstructs all 600 development probabilities; requires their byte hash and ordered observation hash to match E-496; attributes distributions at thresholds `0.75` and `0.80` by all eight variants and all 75 targets; measures per-target visible/obstruction separation; and checks clear/distractor image hashes. It rejects model, source, scorecard, identity, probability, evaluation-state, or authority mismatches.
- Exact command: `python software/ai/eval/diagnose_residual_obstruction_development.py --fixture software/ai/sim/evidence/residual_obstruction_pretraining_v1.json --dataset-dir C:\IsaacSim\artifacts\issue190\residual-obstruction-data-v1 --model C:\IsaacSim\artifacts\issue190\residual-obstruction-candidate-v1\model.bin --scorecard C:\IsaacSim\artifacts\issue190\residual-obstruction-candidate-v1\scorecard.json --output software/ai/eval/residual_obstruction_development_diagnostic_v1.json`; repeated unchanged with dataset/candidate suffix `v2` and `%TEMP%\residual_obstruction_development_diagnostic_v1_second.json`.
- Bound input SHA-256 values: fixture file `c6588a42e9e2e48c28773e09290a04eb7fc940eb5a83349185d17e3243c59602`; canonical fixture `06f3972c71fa4132083cd963285824d49577eaf933cab4e411da84224a2ebfef`; dataset manifest file `32f2264cabb7833f3d2cee13d9ab7fcdcca91d7b75ba1e9dc1221dfc29800aa7`; canonical dataset `a6188e5ae191e2bfc71dae37ee26f174d5a056d3d4958ae7c2f472ef9bff2830`; dataset inventory `9dbbe3bb397f85fff576b68b80610901b5f3ab5d6a07cea501a3780dcd273a7d`; model file `90d32245902a20653e829627772d78604bd8c11880bc5be1c54bf14343831946`; scorecard file `d2197eb2292c4ed603132dc3aa1ee06d40ce910382b9c9e74bfafac06c457a29`; canonical scorecard `c04f8dc67ba09fa4fc582b85d1b186c13d9c0dafa7855d41545c193a568a6573`.
- Global result: pairwise AUC is `0.7585185185`. Visible probabilities have minimum `0.714412451`, maximum `0.802202523`, mean `0.738759756`, and median `0.737469614`. Obstruction probabilities have minimum `0.678780198`, maximum `0.907149673`, mean `0.770756662`, and median `0.770943880`.
- Target result: zero of 75 targets are locally separable. For every target, the minimum obstruction probability is below the maximum visible probability. The worst separation margin is `-0.038004994` on target `2`; the best is still negative at `-0.000876069`. The problem therefore spans the full target catalog rather than one target or keyboard region.
- Variant result: all 75 development `none_adjacent_distractor` PNG files are byte identical to the corresponding `none_clear` files, so the planned adjacent distractor did not enter the crop. `image_degraded` is the lowest-scoring obstruction variant with mean `0.734067500`; 17/75 rows abstain at `0.75` and 0/75 at `0.80`. Cable abstains on 46/75 at `0.75` and 21/75 at `0.80`; tool abstains on 46/75 and 35/75. Localized glare is the only obstruction family with 75/75 abstentions at `0.75`. Clear and adjacent-distractor each produce 20/75 false stops at `0.75` and 1/75 at `0.80`.
- Interpretation: the failed gate reflects dataset construction, source-pose transfer, and broad variant overlap. Threshold adjustment cannot correct it. A successor must prove that every adjacent distractor changes retained pixels while preserving zero target overlap, introduce multiple source-pose and appearance groups with split isolation, and broaden degradation/cable/tool severity before generation. These consumed identities cannot evaluate that successor.
- Artifact SHA-256 values: final diagnostic tool `1816b9f7147e26954780749ecbe88c3368902b62065c09ba4c4ab385603d0a4b`; retained report file `91a3185c431067a5533ea3d6cc21342605a93b04f55935c914a4ea1f0779bb84`; canonical report `b4e9e51ad92962894330500e18ce062ef059759b851716552b7a6b6b7b23235d`; schema `da42c754dcfbda98495064f2ebbc4ee0ff164f3eb1534a9617d1ed7cdac50da5`; tests `7153f406f7a1bc128c23f0ac3ea0034e4845e76a77f729947eb8b371a808c5ac`; registry file `0382f51934997d676e0a2221d58a1e66b42262b3caa0c5b3b1c88d7af8381681`; canonical registry `139b4078727b849861ab28593cc5dc066156e368f0812620c6e13ef630153f88`; registry audit file `e18cd4b3b5d75f2f6118645c8e3368fb51cd4b3c64a3e7deec870f45f8270314`; registry audit receipt `d71dd8806e27fc222a316754f2e048e33fc70f4d10441f95ae6217baed93d581`.
- Validation commands: two exact diagnostic commands above followed by file SHA-256 comparison; `python -m pytest software/ai/tests/test_residual_obstruction_development_diagnostic.py software/ai/tests/test_ai_work_registry.py -q`; `python -m pytest software/ai/tests -q`; `python -m pytest software/tests/unit/test_model_motion_ingress_v2.py software/tests/integration/test_model_arm_conformance_profile_v1.py -q`; `python -m ruff check software/ai/eval/diagnose_residual_obstruction_development.py software/ai/tests/test_residual_obstruction_development_diagnostic.py software/ai/tests/test_ai_work_registry.py`; `python software/ai/eval/audit_ai_work_registry.py --output software/ai/eval/ai_work_registry_audit_v1.json`; `python scripts/ci/check_docs.py`; `python scripts/ci/check_public_records.py`; `python scripts/ci/check_evidence_scope.py`; `python scripts/ci/check_repository_artifacts.py`; `python scripts/ci/check_repository_health.py --policy-only`; `python scripts/ci/check_source_archive_footprint.py --json`; `python scripts/ci/check_release_integrity.py --mode policy`; `python scripts/ci/check_release_readiness_sync.py`; `git diff --check`.
- Validation result: repeated reports are byte identical; 10 focused diagnostic/registry tests passed; all 240 AI tests passed with two expected Windows symlink skips; all 34 shared ingress/conformance tests passed; Ruff and repository governance checks passed. Registry audit covers 46 tracked/documented AI tests and 155 referenced paths. Source footprint is 6,154 tracked files, 655,243,424 logical bytes, 4,890,152 governed duplicate bytes, and a 55,939,877-byte largest blob.
- Hardware-write count: 0.
- Physical-movement count: 0.
- Physics-step count: 0; Isaac Sim was not opened and only retained crop/model bytes were read.
- Limitations: this reuses a consumed synthetic development split from two correlated practice views with simplified surfaces and an unmeasured camera. Per-variant and per-target identities are design evidence only. There is no untouched evaluation, physical obstruction image, commissioned calibration, synchronized feedback, measured dilation, localization qualification, collision evidence, controller command, transport field, permit, deployment qualification, or physical authority.
- Supersedes: none. The residual candidate remains rejected, its development split is consumed, V16 remains rejected, the geometry-first seam remains primary for known self-occlusion, and every evaluation source remains closed.
- Next dependency: predeclare a fresh pose- and appearance-diverse residual campaign before generating data. Require nonduplicate adjacent distractors, multiple source-pose and appearance groups isolated across train/development, and severity diversity for degradation, cable, and tool cases. Continue exposure-synchronized measured-feedback projection, measured dilation, and physical parked-pose originals in parallel.


### E-20261002-AI-498 — residual successor v2 is frozen before rendering

- Stage: S2/S3 synthetic parked residual-obstruction successor predeclaration.
- Lane: AI/model render fixture, model plan, and development-gate policy only; no arm-lane or integration-gate status changed.
- Claim commit: `2c4dbec42f3447b8b4c512b21dcd4dbced0f2f96`.
- Implementation/predeclaration commit: `d754434045bac59b177be107925ac2a27aba7bda`.
- Change: added a deterministic v2 fixture builder, strict schema, retained fixture, and focused tests. The fixture binds the exact retained fixed-camera source and E-497 diagnostic, freezes six training and three development parked-camera perturbation identities, four training and three development appearance identities, 15 target-balanced variants, exact observation counts, renderer admission, a small RGB-only offline model, threshold candidates, whole-view clustered development gates, and an empty evaluation split. It emits no images or model and performs no training.
- Exact command: `python software/ai/sim/build_residual_obstruction_successor_fixture.py --source-manifest software/integrations/isaac_sim/evidence/fixed_fixture_practice_v1/manifest.json --diagnostic software/ai/eval/residual_obstruction_development_diagnostic_v1.json --output software/ai/sim/evidence/residual_obstruction_successor_v2.json`; repeated unchanged with `%TEMP%\residual_obstruction_successor_v2_second.json`.
- Bound source SHA-256 values: source manifest file `a529ffbdc39aff5450d0378f2e3020c83b398a3e7f853b0ef4e957748e34c7fd`; canonical source corpus `03e2d3d7ac2d3a0026b2c24cb0a9d709190794e1adb5b69e038374fa46f152e4`; source generator `b364906e0798c4f032bf2e329041a775a008e5ee7aa7a23ee0b1c83e0cb90163`; target catalog `6779213e832ab27eeda1e7fb245f57ff8cb0d56707b5aa73a8f31ec483a620f2`; diagnostic file `91a3185c431067a5533ea3d6cc21342605a93b04f55935c914a4ea1f0779bb84`; canonical diagnostic `b4e9e51ad92962894330500e18ce062ef059759b851716552b7a6b6b7b23235d`.
- Frozen campaign: six training and three development view groups with camera translation/rotation perturbations around a synthetic parked-observation reference; four training appearances (`neutral`, `dim`, `bright`, `warm`) and three disjoint development appearances (`cool`, `directional shadow`, `sensor noise`); 75 targets; 15 variants per target; 27,000 training rows; 10,125 development rows; zero evaluation rows.
- Variant policy: three visible families (`clear`, `adjacent left`, `adjacent right`) and 12 abstention families spanning three cable widths, tool edge/center, hand, foreign object, localized glare, light/heavy defocus, compression, and motion blur. Adjacent distractors require at least 64 changed crop pixels and exactly zero safe-region overlap. Obstruction masks must satisfy the declared overlap bands. Duplicate observation bytes fail the campaign. Truth and runtime geometry masks are prohibited as model inputs.
- Frozen model and gate: `target_crop_residual_cnn_v2`; RGB only; convolution channels `[16,32,64]`; 18 epochs; batch 128; learning rate `0.0003`; weight decay `0.0001`; deterministic label/variant-balanced sampling; seed `19018`; threshold grid `0.05` through `0.95` by `0.05`. Development requires point and 2,000-resample whole-view cluster upper bounds at most 2% missed obstructions and 6% residual false stops, including the maximum across development appearances.
- Artifact SHA-256 values: builder `f2a04f5898813d95490a80a5fea417d5752835922f35e3eb09c6be61196c4070`; retained fixture file `54d6b3eeceda18f5bdeeb628abacb45715cbbeac7cc518de9c51e01ee309cc0d`; canonical fixture `0833469f9d7244ba5c2f2ded3819c2c8c3ab438c68ad84fdfca8f475fedb5bfd`; schema `a284aeeb7b6e52241286745a2eddc3f6bbbc84d6a1b1ed7f1bfc5816a14916ce`; tests `3476a3db3fb5250debda38dbb618a00d1cb2d815d221d8675bca90f4b3eb8f18`; registry file `be4e665bc060cfbac97213bf235df13e066add663fbb86d3a3fe31d32d31ddea`; canonical registry `7c62decf67e99e4be0d60c2d5a9b9f03e62b7ec2a53c8cf5f99545b40b2e0022`; registry audit file `1a4a2a833b4ec3a42256521d1fad81d3722f02d2ebdc6e6d7ffff6d7a93ce7a9`; registry audit receipt `263c9155b209c9abde1233d574da4f8287af7a2e5aee3772028dd6c05fde32e7`.
- Validation commands: two exact fixture commands above followed by file SHA-256 comparison; `python -m pytest software/ai/tests/test_residual_obstruction_successor_fixture.py software/ai/tests/test_ai_work_registry.py -q`; `python -m pytest software/ai/tests -q`; `python -m pytest software/tests/unit/test_model_motion_ingress_v2.py software/tests/integration/test_model_arm_conformance_profile_v1.py -q`; `python -m ruff check software/ai/sim/build_residual_obstruction_successor_fixture.py software/ai/tests/test_residual_obstruction_successor_fixture.py software/ai/tests/test_ai_work_registry.py`; `python software/ai/eval/audit_ai_work_registry.py --output software/ai/eval/ai_work_registry_audit_v1.json`; `python scripts/ci/check_docs.py`; `python scripts/ci/check_public_records.py`; `python scripts/ci/check_evidence_scope.py`; `python scripts/ci/check_repository_artifacts.py`; `python scripts/ci/check_repository_health.py --policy-only`; `python scripts/ci/check_source_archive_footprint.py --json`; `python scripts/ci/check_release_integrity.py --mode policy`; `python scripts/ci/check_release_readiness_sync.py`; `git diff --check`.
- Validation result: repeated fixtures are byte identical; 11 focused fixture/registry tests passed; all 245 AI tests passed with two expected Windows symlink skips; all 34 shared ingress/conformance tests passed; Ruff and repository governance checks passed. Registry audit covers 47 tracked/documented AI tests and 159 referenced paths. Source footprint is 6,158 tracked files, 655,285,216 logical bytes, 4,890,152 governed duplicate bytes, and a 55,939,877-byte largest blob.
- Hardware-write count: 0.
- Physical-movement count: 0.
- Physics-step count: 0; Isaac Sim was not opened.
- Limitations: every view, camera perturbation, appearance, obstruction, label, and acceptance condition remains synthetic. The source scene has simplified target surfaces and an unmeasured camera. The consumed v1 diagnostic informed this design and cannot evaluate v2. This fixture has no rendered image, measured performance, physical obstruction evidence, commissioned calibration, synchronized feedback, measured dilation, localization qualification, collision evidence, controller command, transport field, permit, deployment qualification, or physical authority.
- Supersedes: none. Residual v1 and V16 remain rejected; the geometry-first seam remains primary for known self-occlusion; every evaluation source remains closed.
- Next dependency: implement the exact v2 parked-view renderer and fail closed on any split, identity, changed-pixel, safe-overlap, obstruction-overlap, or duplicate-byte mismatch. Independently inventory the generated campaign before training. Continue exposure-synchronized measured-feedback projection, measured dilation, and physical parked-pose originals in parallel.


### E-20261002-AI-499 — residual v2 renderer produces an admitted reproducible crop corpus

- Stage: S2/S3 synthetic residual-obstruction renderer binding and crop materialization.
- Lane: AI/model offline synthetic rendering and evidence only; no arm-lane or integration-gate status changed.
- Claim commit: `8b108fb88065f90d2c40425b24732cdb16c276d0`.
- Renderer-contract commit: `4dcadad59c64195d09986782dbee2793b89c3c2e`.
- Renderer implementation/evidence commit: `0a307a2f51f3ce82db240312542e5cb02cd8ca0c`.
- Change: first froze a separate renderer contract binding the exact retained `hover_t__nominal` image, ordered 75-target catalog, deterministic planar affine camera approximation, target geometry transform, raster rules, PNG policy, crop size, changed-pixel rule, overlap definition, and fail-closed no-duplicate policy. Only after that commit, added the renderer, independent verifier, compact retained receipt, strict receipt schema, and focused tests. The renderer produces RGB crops only; truth masks are used for labels/admission and are prohibited as model inputs. No model was trained or scored and no evaluation source was opened.
- Exact contract command: `python software/ai/sim/build_residual_obstruction_renderer_contract.py --fixture software/ai/sim/evidence/residual_obstruction_successor_v2.json --source-manifest software/integrations/isaac_sim/evidence/fixed_fixture_practice_v1/manifest.json --output software/ai/sim/evidence/residual_obstruction_renderer_contract_v1.json`.
- Exact render commands: `python software/ai/sim/render_residual_obstruction_v2.py render --fixture software/ai/sim/evidence/residual_obstruction_successor_v2.json --contract software/ai/sim/evidence/residual_obstruction_renderer_contract_v1.json --source-manifest software/integrations/isaac_sim/evidence/fixed_fixture_practice_v1/manifest.json --output-dir C:\IsaacSim\artifacts\issue190\residual-obstruction-v2-render-v1`; repeated unchanged with output suffix `v2`.
- Exact verification commands: `python software/ai/sim/render_residual_obstruction_v2.py verify --fixture software/ai/sim/evidence/residual_obstruction_successor_v2.json --contract software/ai/sim/evidence/residual_obstruction_renderer_contract_v1.json --dataset-dir C:\IsaacSim\artifacts\issue190\residual-obstruction-v2-render-v1`; repeated unchanged with dataset suffix `v2`.
- Exact retained-receipt command: `python software/ai/sim/render_residual_obstruction_v2.py receipt --fixture software/ai/sim/evidence/residual_obstruction_successor_v2.json --contract software/ai/sim/evidence/residual_obstruction_renderer_contract_v1.json --dataset-dir C:\IsaacSim\artifacts\issue190\residual-obstruction-v2-render-v1 --output software/ai/sim/evidence/residual_obstruction_v2_render_receipt.json`.
- Bound input SHA-256 values: v2 fixture file `54d6b3eeceda18f5bdeeb628abacb45715cbbeac7cc518de9c51e01ee309cc0d`; canonical fixture `0833469f9d7244ba5c2f2ded3819c2c8c3ab438c68ad84fdfca8f475fedb5bfd`; source manifest file `a529ffbdc39aff5450d0378f2e3020c83b398a3e7f853b0ef4e957748e34c7fd`; canonical source corpus `03e2d3d7ac2d3a0026b2c24cb0a9d709190794e1adb5b69e038374fa46f152e4`; base image `2b6f4d49da7e28e78e9ca900d1f4133432b88d44ec7c9b8bc70f9fe98eed1e92`; target catalog `6779213e832ab27eeda1e7fb245f57ff8cb0d56707b5aa73a8f31ec483a620f2`; renderer-contract file `3d9e661050dd92640f01d5122f747f7efec42e3728bd17d3b926401282d9d965`; canonical renderer contract `e5bef5305086d962400bdbd98efe39cf4f4dc02471243d9966375d42888f7c90`.
- Dataset result: each independent external tree contains 37,125 PNG crops plus one manifest and occupies 329,046,332 bytes. The manifests are byte identical with file SHA-256 `8ab18548adb510943bcb39e8d16653334f17710ae6d4780ae2bc4ca6fbec9f84`; canonical dataset SHA-256 is `0328262ed2eaffb56895f39a9b975044c84f9be4d7a5b8006981601ebce43d0a`; inventory SHA-256 is `6bb68cc216ea6271d2567f7aad94a1a7ebd5feeced4c31f79b0fe6623b612ef5`. Training contains 27,000 crops, development contains 10,125, and evaluation contains zero. All 37,125 PNG byte hashes are unique. Retained PNG bytes total 304,206,952 per tree.
- Admission metrics: the 7,425 visible labels comprise clear, adjacent-left, and adjacent-right cases; 29,700 labels are abstentions. Each of 15 variants contains 2,475 observations. Adjacent-left changes 793–799 pixels and adjacent-right changes 795–799 pixels, both with exactly zero safe-region overlap. Every cable, tool, hand, and foreign-object overlap stays within its predeclared band. Every crop is 96 by 96 RGB, all file hashes and sizes verify, no extra file exists, and neither truth nor runtime geometry masks are exposed as model inputs.
- Artifact SHA-256 values: contract builder `2d9be04787a35633045a59e5b4c29640d39222a6535338e62bd0c4a9a05b3aa8`; contract schema `340f771de9a0392539077f473beca29f86e519cfa15b13d08ca9a7ef24969aa8`; retained contract `3d9e661050dd92640f01d5122f747f7efec42e3728bd17d3b926401282d9d965`; contract tests `c05a9f02a4c7c92249ae1363e32e9b2e171263b8d2cd1d019810c2a5600de2cb`; renderer `c7d6aa4b8865d6d61f8239534c5861682971d70f911671b06dc5d665a9d50db5`; receipt schema `a42581c27eb64da462f641d75d83411c131a98b4e6a4a7367c34775e7a796195`; retained receipt file `572d5b93f1cfe375c0ef5340d083bd730f27200928239e80040d0eb5df44e78c`; canonical receipt `2b917f6f1f6da6dc2c6de9d947c37846435a8f626737f08f678e5553720ca9d4`; renderer tests `99f56dbbc4e2a8c513deb2b8da373246a337ebee2f5a47e95f669c2ca761dcdc`; registry file `e9d9090bb5ac1a3563a0a7595f2b9db9c24ad8250d115e6eb47f46be0cf47f50`; canonical registry `e16418e5ef86f7f7adc9141999c37f1012190fa033bfe11cb3f20451ce49d0e1`; registry audit file `82b560d98845361f871ea1655799e5d9f0a83eeb0178ab6ef932cfa78eb15a38`; registry audit receipt `f102e3da2470ff435c300f89ae0a83964ef8d81008f47e5b7509ad24cc4ccccb`.
- Validation commands: the exact render, verify, and receipt commands above; manifest SHA-256 comparison with `Get-FileHash`; `python -m pytest -q software/ai/tests/test_residual_obstruction_v2_renderer.py software/ai/tests/test_residual_obstruction_renderer_contract.py`; `python -m pytest software/ai/tests -q`; `python -m pytest software/tests/unit/test_model_motion_ingress_v2.py software/tests/integration/test_model_arm_conformance_profile_v1.py -q`; `python -m ruff check software/ai/sim/render_residual_obstruction_v2.py software/ai/tests/test_residual_obstruction_v2_renderer.py software/ai/tests/test_ai_work_registry.py`; `python software/ai/eval/audit_ai_work_registry.py --output software/ai/eval/ai_work_registry_audit_v1.json`; `python scripts/ci/check_docs.py`; `python scripts/ci/check_public_records.py`; `python scripts/ci/check_evidence_scope.py`; `python scripts/ci/check_repository_artifacts.py`; `python scripts/ci/check_repository_health.py --policy-only`; `python scripts/ci/check_source_archive_footprint.py --json`; `python scripts/ci/check_release_integrity.py --mode policy`; `python scripts/ci/check_release_readiness_sync.py`; `git diff --check`.
- Validation result: ten focused renderer/contract tests passed; all 255 AI tests passed with two expected Windows symlink skips; all 34 shared ingress/conformance tests passed; Ruff and repository governance checks passed. Registry audit covers 49 tracked/documented AI tests and 167 referenced paths. Source footprint is 6,166 tracked files, 655,350,506 logical bytes, 4,890,152 governed duplicate bytes, and a 55,939,877-byte largest blob.
- Preserved failed evidence: the first focused renderer/contract run produced `1 failed, 8 passed` because the test used a uniform image and incorrectly required blur and motion blur to alter it. The test fixture alone was changed to a deterministic textured image; renderer behavior, the frozen contract, and every admission threshold stayed unchanged. No dataset existed at that point. A later read-only PowerShell size-summary command had an empty-pipe parser error; the corrected command reported the identical tree sizes above and did not modify either dataset.
- Hardware-write count: 0.
- Physical-movement count: 0.
- Physics-step count: 0; Isaac Sim was not opened in this increment. The renderer used the exact retained Isaac-derived practice image as its base and performed offline deterministic pixel-domain transformations.
- Limitations: every crop derives from one simplified synthetic base image through deterministic pixel-domain transformations. The planar affine camera approximation is not a calibrated 3D render. Procedural obstruction shapes and lighting do not establish physical realism. Dataset admission proves bindings, identities, split counts, byte uniqueness, and declared pixel/overlap constraints; it does not prove useful features, model accuracy, camera calibration, localization, collision safety, contact success, deployment readiness, or physical authority. The development split is unopened but will become consumed when used for threshold selection; evaluation remains absent.
- Supersedes: none. Residual v1 and v16 remain rejected; the geometry-first seam remains primary for known self-occlusion; every evaluation source remains closed.
- Next dependency: materialize the frozen RGB-only v2 loader from this admitted manifest, verify exact identity/split isolation, train `target_crop_residual_cnn_v2` once under the frozen seed and hyperparameters, and score only development against the precommitted point and whole-view cluster gates. Preserve failure without threshold changes and do not create an evaluation source unless a later separately frozen design requires it.


### E-20261002-AI-500 — residual v2 training is reproducible and fails development

- Stage: S2/S3 synthetic residual-obstruction training and development-only selection.
- Lane: AI/model offline loading, GPU training, and synthetic development scoring only; no arm-lane or integration-gate status changed.
- Claim commit: `454d5e76b816c271561d8a77d1b89f6692e295c0`.
- Implementation/evidence commit: `e6de99167656734f86d60abfd76593a1f156f4bc`.
- Change: added a strict manifest-verified RGB crop loader, deterministic label-and-variant-balanced sampler, the frozen three-layer CNN v2, deterministic CUDA training, exact model serialization, whole-view clustered bootstrap scoring, worst-development-appearance scoring, strict result schema, retained failed scorecard, and focused tests. The implementation accepts only the frozen fixture, renderer contract, and admitted dataset, refuses evaluation data and existing output directories, and creates candidate files only after training and scoring complete.
- Exact training command: `python software/ai/train/train_residual_obstruction_v2.py --fixture software/ai/sim/evidence/residual_obstruction_successor_v2.json --contract software/ai/sim/evidence/residual_obstruction_renderer_contract_v1.json --dataset-dir C:\IsaacSim\artifacts\issue190\residual-obstruction-v2-render-v1 --output-dir C:\IsaacSim\artifacts\issue190\residual-obstruction-v2-candidate-v2`; repeated unchanged with output suffix `v3`.
- Bound inputs: fixture file SHA-256 `54d6b3eeceda18f5bdeeb628abacb45715cbbeac7cc518de9c51e01ee309cc0d`; canonical fixture `0833469f9d7244ba5c2f2ded3819c2c8c3ab438c68ad84fdfca8f475fedb5bfd`; renderer-contract file `3d9e661050dd92640f01d5122f747f7efec42e3728bd17d3b926401282d9d965`; canonical contract `e5bef5305086d962400bdbd98efe39cf4f4dc02471243d9966375d42888f7c90`; dataset-manifest file `8ab18548adb510943bcb39e8d16653334f17710ae6d4780ae2bc4ca6fbec9f84`; canonical dataset `0328262ed2eaffb56895f39a9b975044c84f9be4d7a5b8006981601ebce43d0a`; inventory `6bb68cc216ea6271d2567f7aad94a1a7ebd5feeced4c31f79b0fe6623b612ef5`.
- Reproducibility: both completed GPU runs produced byte-identical 95,120-byte models with SHA-256 `0f5982b6af2761ce367837c35094647cfa5711f1fd042ede36650ba9306a1367` and byte-identical scorecards with file SHA-256 `a82755040aec805a68aea263c86d24c07ce03657c6756999041c4977beac548a`. Canonical result SHA-256 is `8b748d1b21f38beb1580cb7217bddbd643dde81e6b1b277341a531465a7618fb`; development-probability SHA-256 is `d9931a32be2b6d3fd29c53b77dd012392ef003c0d27a389bbea10caf1529b7b6`.
- Training result: all 27,000 training crops were sampled for each of 18 deterministic epochs with equal visible/abstain allocation and uniform allocation across variants inside each label. Loss decreased from `0.6909732927` to `0.4133035734`. Development contains 10,125 rows: 8,100 obstruction and 2,025 visible. Evaluation contains zero rows.
- Development result: `FAILED_DEVELOPMENT_GATE`; no threshold was selected. At threshold `0.10`, missed obstructions are 80/8,100 (`0.9877%`) with whole-view upper `1.1235%`, but visible false stops are 1,230/2,025 (`60.7407%`) with whole-view upper `62.1235%`. At threshold `0.20`, misses are 566/8,100 (`6.9877%`) with whole-view upper `7.2099%`, while false stops are 758/2,025 (`37.4321%`) with whole-view upper `38.6173%`. Its worst-appearance miss and false-stop rates are `18.7037%` and `54.2222%`. Every one of the 19 frozen thresholds fails at least one 2% miss or 6% false-stop point, whole-view, or worst-appearance limit.
- Artifact SHA-256 values: training tool `f080741f0be075785dd6aadba12436e154a2dad235a05fe65e72540f893b09da`; result schema `72f23070be500ce4803373ead84d77d3a83cc73b022010b7ece76e6d983b6785`; retained scorecard `a82755040aec805a68aea263c86d24c07ce03657c6756999041c4977beac548a`; focused tests `159c9dd88158b9267a5ffbed40c84e205e9975e5cba7652270379a4893b1cfa5`; registry file `77db21123855d2bca77eb60172bce899ed601fbc1187548e25514aa29ac7d666`; canonical registry `78b90029ce33e2cea4e297531a55a467eb2bf715cfb5c563ffeb59e2bd6256c4`; registry audit file `ebfa88d8d335ee5d663834e4377dc5e868985e17d1d338f38a0415ff5bd2b711`; registry audit receipt `81e16b997742ea3384e747c8ce33ee2fe6abf8dbf3eed9501dda5c3c955e9222`.
- Validation commands: the two exact training commands above followed by `Get-FileHash` model/scorecard comparison; `python -m pytest -q software/ai/tests/test_residual_obstruction_v2_training.py`; `python -m pytest software/ai/tests -q`; `python -m pytest software/tests/unit/test_model_motion_ingress_v2.py software/tests/integration/test_model_arm_conformance_profile_v1.py -q`; `python -m ruff check software/ai/train/train_residual_obstruction_v2.py software/ai/tests/test_residual_obstruction_v2_training.py software/ai/tests/test_ai_work_registry.py`; `python software/ai/eval/audit_ai_work_registry.py --output software/ai/eval/ai_work_registry_audit_v1.json`; `python scripts/ci/check_docs.py`; `python scripts/ci/check_public_records.py`; `python scripts/ci/check_evidence_scope.py`; `python scripts/ci/check_repository_artifacts.py`; `python scripts/ci/check_repository_health.py --policy-only`; `python scripts/ci/check_source_archive_footprint.py --json`; `python scripts/ci/check_release_integrity.py --mode policy`; `python scripts/ci/check_release_readiness_sync.py`; `git diff --check`.
- Validation result: four focused training tests passed; all 259 AI tests passed with two expected Windows symlink skips; all 34 shared ingress/conformance tests passed; Ruff and repository governance checks passed. Registry audit covers 50 tracked/documented AI tests and 171 referenced paths. Source footprint is 6,170 tracked files, 655,403,428 logical bytes, 4,890,152 governed duplicate bytes, and a 55,939,877-byte largest blob.
- Preserved failed evidence: the first attempted run used output suffix `v1` and failed before completing epoch one because deterministic CUDA mode requires `CUBLAS_WORKSPACE_CONFIG` before CuBLAS initialization. It emitted no model or scorecard and left only an empty output directory. The implementation now sets `:4096:8` before importing Torch and defers output-directory creation until after training/scoring. The frozen architecture, data, seed, sampler, epochs, thresholds, and gates did not change. The two subsequent runs reproduced exactly.
- Hardware-write count: 0.
- Physical-movement count: 0.
- Physics-step count: 0; Isaac Sim was not opened and training used offline retained crop bytes.
- Limitations: training and development derive from one simplified synthetic base scene with pixel-domain camera, appearance, and obstruction transforms. The strong appearance-specific failure shows that deterministic rendering diversity did not create sufficient invariant separation. This result contains no untouched evaluation, physical obstruction image, commissioned calibration, synchronized measured feedback, measured dilation, localization qualification, collision evidence, controller command, transport field, permit, deployment qualification, or physical authority.
- Supersedes: none. Residual v1, residual v2, and v16 remain rejected; geometry-first handling remains primary for known self-occlusion; evaluation remains absent.
- Next dependency: diagnose the consumed v2 development probabilities by variant, appearance, view, and target without changing the checkpoint or threshold. Use the diagnosis only to predeclare a fresh successor that addresses appearance transfer and physically shaped residual obstructions. Continue measured-feedback geometry projection, measured dilation, and physical parked-pose collection in parallel.


### E-20261002-AI-501 — residual v2 diagnosis proves catalog-wide score overlap

- Stage: S2/S3 consumed synthetic development-only diagnosis after the rejected residual v2 gate.
- Lane: AI/model read-only probability reconstruction and failure attribution; no arm-lane or integration-gate status changed.
- Claim commit: `6419340feaf3abb0050a93bffa54482aff5dc608`.
- Implementation/evidence commit: `cc2d6b0ddea32359e8fc6c3cd957b14e336450c5`.
- Change: added a fail-closed diagnostic that binds the exact v2 fixture, renderer contract, admitted dataset manifest, rejected checkpoint, and scorecard; reconstructs all 10,125 ordered development probabilities with the exact training-time CUDA preprocessing path; verifies the frozen probability digest; attributes score distributions and threshold errors by 15 variants, three appearance identities, three views, and all 75 targets; computes global pairwise AUC and target-local separation margins; retains a strict aggregate report, schema, registry update, and focused tests. It cannot retrain, change a threshold, read evaluation data, promote the model, or create physical authority.
- Exact command: `python software/ai/eval/diagnose_residual_obstruction_v2.py --fixture software/ai/sim/evidence/residual_obstruction_successor_v2.json --contract software/ai/sim/evidence/residual_obstruction_renderer_contract_v1.json --dataset-dir C:\IsaacSim\artifacts\issue190\residual-obstruction-v2-render-v1 --model C:\IsaacSim\artifacts\issue190\residual-obstruction-v2-candidate-v2\model.bin --scorecard C:\IsaacSim\artifacts\issue190\residual-obstruction-v2-candidate-v2\scorecard.json --output software/ai/eval/residual_obstruction_v2_diagnostic_v1.json`; repeated unchanged with output `%TEMP%\residual_obstruction_v2_diagnostic_v1_second.json` and compared byte for byte.
- Bound input SHA-256 values: fixture file `54d6b3eeceda18f5bdeeb628abacb45715cbbeac7cc518de9c51e01ee309cc0d`; canonical fixture `0833469f9d7244ba5c2f2ded3819c2c8c3ab438c68ad84fdfca8f475fedb5bfd`; renderer-contract file `3d9e661050dd92640f01d5122f747f7efec42e3728bd17d3b926401282d9d965`; canonical contract `e5bef5305086d962400bdbd98efe39cf4f4dc02471243d9966375d42888f7c90`; dataset-manifest file `8ab18548adb510943bcb39e8d16653334f17710ae6d4780ae2bc4ca6fbec9f84`; canonical dataset `0328262ed2eaffb56895f39a9b975044c84f9be4d7a5b8006981601ebce43d0a`; model file `0f5982b6af2761ce367837c35094647cfa5711f1fd042ede36650ba9306a1367`; scorecard file `a82755040aec805a68aea263c86d24c07ce03657c6756999041c4977beac548a`; canonical scorecard `8b748d1b21f38beb1580cb7217bddbd643dde81e6b1b277341a531465a7618fb`; development probabilities `d9931a32be2b6d3fd29c53b77dd012392ef003c0d27a389bbea10caf1529b7b6`.
- Global result: pairwise AUC is `0.8975297058` across 8,100 obstruction and 2,025 visible development rows. All 75 targets are locally nonseparable because each target's minimum obstruction probability is no greater than its maximum visible probability. The best target margin is `-0.202038795`; the worst is `-0.785702050` for `key_space`.
- Appearance result at threshold `0.20`: cool produces 505/2,700 obstruction misses and 110/675 visible false stops; sensor noise produces 7 misses and 282 false stops; shadow produces 54 misses and 366 false stops. Mean obstruction/visible probabilities are `0.463768`/`0.105928` for cool, `0.671587`/`0.232419` for sensor noise, and `0.636035`/`0.261453` for shadow. View errors are similar enough that appearance transfer is the stronger observed factor.
- Variant result at threshold `0.20`: clear creates 537/675 visible false stops; adjacent-left and adjacent-right create 119/675 and 102/675. Compression creates 174/675 obstruction misses; cable thin, medium, and thick create 84, 79, and 63; tool edge and center create 97 and 57. Most other obstruction variants have near-zero misses. This pattern and the negative target-local margins do not support a threshold-only correction.
- Successor dependency: predeclare a fresh campaign with independent base scenes and group isolation, explicit appearance-invariance training, physically shaped/material/depth/transparency obstruction variation, and a positive held-out target-local margin requirement before any evaluation source can be opened.
- Artifact SHA-256 values: diagnostic tool `e611f535736426c35727382c510b568c68f2afe205251b60b0f94ff311df391a`; diagnostic schema `1412d5270718a2edca122718e700e28f3ccd8f00f75ea5cc003d9d7cb4517661`; retained report file `9560c6bd6c2d0463741e2f0e8221d16d520f062b7fdfd525f79272a7374cbfb6`; canonical report `48496f1015b31c859bdf4ca2e53a8b4b50ef59ad524f35ea74e5caf864fe8517`; focused tests `efdc6ab3afecd9ff8dd85c927fbc3055702f58e9a8570e8a9750e3abfb022937`; registry file `ba02a041cc840605c5cf4b67ab1e6b302ec33255864be9c5ab40edb56358511c`; canonical registry `bf98ae8c9d91e353d5103b60711a3eb465a8dca30f51f48619e9c4475a1ca324`; registry-audit file `aa1fe38c0c581322c973b89ac1efe88fe4b12da9fc762356ab1f7764f3346daf`; registry-audit receipt `9c3364e156c1ec6bd8e8850e8ab9585c9279f639676fc60e633f8ed4a737a485`.
- Validation commands: the two exact diagnostic commands above followed by byte comparison; `python -m pytest -q software/ai/tests/test_residual_obstruction_v2_diagnostic.py`; `python -m pytest software/ai/tests -q`; `python -m pytest software/tests/unit/test_model_motion_ingress_v2.py software/tests/integration/test_model_arm_conformance_profile_v1.py -q`; `python -m ruff check software/ai/eval/diagnose_residual_obstruction_v2.py software/ai/tests/test_residual_obstruction_v2_diagnostic.py software/ai/tests/test_ai_work_registry.py`; `python software/ai/eval/audit_ai_work_registry.py --output software/ai/eval/ai_work_registry_audit_v1.json`; `python scripts/ci/check_docs.py`; `python scripts/ci/check_public_records.py`; `python scripts/ci/check_evidence_scope.py`; `python scripts/ci/check_repository_artifacts.py`; `python scripts/ci/check_repository_health.py --policy-only`; `python scripts/ci/check_source_archive_footprint.py --json`; `python scripts/ci/check_release_integrity.py --mode policy`; `python scripts/ci/check_release_readiness_sync.py`; `git diff --check`.
- Validation result: repeated diagnostic reports are byte identical; two focused diagnostic tests passed; all 261 AI tests passed with two expected Windows symlink skips; all 34 shared ingress/conformance tests passed; Ruff, registry, maintained-document, public-record, evidence-scope, repository-artifact, repository-health, source-footprint, release-integrity, release-readiness, and diff checks passed. The registry covers 51 tracked/documented AI tests and 175 referenced paths. The committed footprint is 6,174 tracked files, 655,490,464 logical bytes, 4,890,152 governed duplicate bytes, and a 55,939,877-byte largest blob.
- Preserved failed evidence: the first diagnostic reconstruction used CPU inference and failed closed with `development probability reconstruction mismatch`. Deterministic CUDA then also failed because preprocessing divided by 255 in NumPy/CPU rather than reproducing the training path. The final implementation batches original `uint8` pixels and performs the exact CUDA `.to(dtype=float32).div_(255.0)` conversion, after which the frozen probability hash reproduced. No checkpoint, data, threshold, gate, or evaluation state changed during either correction.
- Hardware-write count: 0.
- Physical-movement count: 0.
- Physics-step count: 0; Isaac Sim was not opened and the diagnostic read retained offline crop/model bytes.
- Limitations: this is reuse of consumed synthetic development evidence from one simplified base scene and pixel-domain transformations. It can explain rejection and guide a fresh design, but cannot estimate untouched generalization, physical realism, camera performance, projection error, measured dilation, localization, collision safety, contact success, deployment readiness, or physical qualification. It contains no controller command, joint/PWM/serial/Waveshare field, motion policy, execution permit, transport field, or physical authority.
- Supersedes: none. Residual v1, residual v2, and v16 remain rejected; geometry-first handling remains primary for known self-occlusion; every evaluation source remains closed.
- Next dependency: freeze the fresh residual successor design before generation, then use independent base scenes and physically grounded obstruction geometry. Continue synchronized measured-feedback projection, measured dilation, and physical parked-pose original collection as parallel prerequisites.


### E-20261002-AI-502 — residual v3 freezes independent Isaac scenes and 3D obstruction semantics

- Stage: S2/S3 fresh synthetic residual-obstruction successor predeclaration before rendering or training.
- Lane: AI/model Isaac campaign and small offline-model contract only; no arm-lane or integration-gate status changed.
- Claim commit: `a0aec0a58ccc1f939f4ca48945397d8b550d5d1b`.
- Implementation/evidence commit: `29025a142f6d2eca0e67d95d85663e029dc3dc0d`.
- Change: added a deterministic v3 fixture builder, strict JSON schema, retained fixture, registry ownership, and focused tests. The fixture binds the exact practice-corpus identity and consumed v2 diagnostic, requires all three frozen v2 findings, freezes eight training and four development base-scene identities with disjoint seeds, and requires every base scene to be a fresh Isaac 3D render. It prohibits source-image warping and model access to truth masks or depth. It freezes four paired physically based appearances and 12 variants covering clear/adjacent-visible cases, rubber/translucent mesh cables, matte/gloss mesh tools, foreign objects, rendered glare, defocus, motion blur, and compression. Mesh variants declare material, depth, opacity where applicable, and target-safe-region overlap ranges.
- Exact command: `python software/ai/sim/build_residual_obstruction_successor_v3.py --source-manifest software/integrations/isaac_sim/evidence/fixed_fixture_practice_v1/manifest.json --diagnostic software/ai/eval/residual_obstruction_v2_diagnostic_v1.json --output software/ai/sim/evidence/residual_obstruction_successor_v3.json`; repeated unchanged with output `%TEMP%\residual_obstruction_successor_v3_second.json` and compared byte for byte.
- Bound input SHA-256 values: practice manifest file `a529ffbdc39aff5450d0378f2e3020c83b398a3e7f853b0ef4e957748e34c7fd`; canonical practice corpus `03e2d3d7ac2d3a0026b2c24cb0a9d709190794e1adb5b69e038374fa46f152e4`; target catalog `6779213e832ab27eeda1e7fb245f57ff8cb0d56707b5aa73a8f31ec483a620f2`; v2 diagnostic file `9560c6bd6c2d0463741e2f0e8221d16d520f062b7fdfd525f79272a7374cbfb6`; canonical v2 diagnostic `48496f1015b31c859bdf4ca2e53a8b4b50ef59ad524f35ea74e5caf864fe8517`; rejected model `0f5982b6af2761ce367837c35094647cfa5711f1fd042ede36650ba9306a1367`.
- Frozen campaign: 8 training and 4 development base scenes are identity-disjoint; four paired appearances and 12 variants over 75 targets predeclare 28,800 training and 14,400 development observations. Evaluation count is zero. Each scene must use a fresh full-frame 3D render and independently seeded bounded camera and fixture-surface randomization.
- Frozen training/gate design: `target_crop_residual_cnn_v3` remains a small RGB-only CNN with channels 24/48/64, GroupNorm, deterministic balanced sampling, binary classification loss, and a `0.2` weighted paired-logit Huber appearance-consistency loss. Development retains 2% missed-obstruction and 6% visible-false-stop ceilings, 95% 4,000-resample base-scene cluster bounds, worst-appearance and worst-variant-family gates, and a strictly positive local separation margin for every target. No threshold is selected and evaluation must remain unopened.
- Artifact SHA-256 values: fixture builder `c0d643e9d7d4ddfcd5d18e6784695cdbd323270108ca549b9779a29f10217653`; schema `a3fff358d89e06e3ad7f64d2fd24faece970a80d46483bf448b007bbbdf9c096`; retained fixture file `56b04e0bcc35c26eea2848a0244827d7285e5056667f17deae628c0986921cbd`; canonical fixture `7e861cb17b5f4717d732989d1ddaaeb4ab3e3e4e0ae1d92dd19de35afa397fed`; focused tests `2feed456ddf636153e3fb06014b8dd8acb66ddd52099725431e948674e771da9`; registry file `8ce660b5d6ec939ff0a0f42c5860f59535c8f3921d217d761064ac9e65d11609`; canonical registry `acf2259447c5093b1987309025428727f447a3ae97686cc5919fcd3257972591`; registry-audit file `d20e3795fdcacfba463c7d6786fcea2be602c79ec178bcd8c177211818c19300`; registry-audit receipt `c0cd9d4fe702002405ae4e01f84969b3f6efa23f3d556873e2211fc4c82ada29`.
- Validation commands: the two exact fixture commands above followed by SHA-256 comparison; `python -m pytest -q software/ai/tests/test_residual_obstruction_successor_v3.py software/ai/tests/test_ai_work_registry.py`; `python -m pytest software/ai/tests -q`; `python -m pytest software/tests/unit/test_model_motion_ingress_v2.py software/tests/integration/test_model_arm_conformance_profile_v1.py -q`; `python -m ruff check software/ai/sim/build_residual_obstruction_successor_v3.py software/ai/tests/test_residual_obstruction_successor_v3.py software/ai/tests/test_ai_work_registry.py`; `python software/ai/eval/audit_ai_work_registry.py --output software/ai/eval/ai_work_registry_audit_v1.json`; `python scripts/ci/check_docs.py`; `python scripts/ci/check_public_records.py`; `python scripts/ci/check_evidence_scope.py`; `python scripts/ci/check_repository_artifacts.py`; `python scripts/ci/check_repository_health.py --policy-only`; `python scripts/ci/check_source_archive_footprint.py --json`; `python scripts/ci/check_release_integrity.py --mode policy`; `python scripts/ci/check_release_readiness_sync.py`; `git diff --check`.
- Validation result: repeated fixtures are byte identical; 11 focused fixture/registry tests passed; all 266 AI tests passed with two expected Windows symlink skips; all 34 shared ingress/conformance tests passed; Ruff, schema validation, registry, maintained-document, public-record, evidence-scope, repository-artifact, repository-health, source-footprint, release-integrity, release-readiness, and diff checks passed. Registry audit covers 52 tracked/documented AI tests and 179 referenced paths. The committed footprint is 6,178 tracked files, 655,531,306 logical bytes, 4,890,152 governed duplicate bytes, and a 55,939,877-byte largest blob.
- Preserved failed evidence: the first registry/policy rewrite used the Windows default newline conversion, and `git diff --check` rejected the affected lines as trailing whitespace. The same semantic JSON updates were rewritten with explicit LF line endings and then passed. The fixture, hashes, counts, model plan, and gates did not change.
- Hardware-write count: 0.
- Physical-movement count: 0.
- Physics-step count: 0; Isaac Sim was not opened and no v3 observation was rendered in this increment.
- Limitations: this is a synthetic campaign design, not measured evidence. The declared independent scenes, camera jitter, materials, geometry, depth, opacity, and lighting ranges are unrendered. The camera and physical obstacle appearances remain unmeasured. The v2 development diagnosis motivated v3 but cannot evaluate or select it. No model, threshold, evaluation result, camera calibration, localization qualification, collision evidence, contact success, deployment qualification, controller command, joint/PWM/serial/Waveshare field, motion policy, permit, transport, or physical authority exists here.
- Supersedes: none. Residual v1, residual v2, and v16 remain rejected; geometry-first handling remains primary for known self-occlusion; every evaluation source remains closed.
- Next dependency: implement the exact v3 Isaac renderer and fail-closed admission receipt, then generate all fresh base scenes and 3D variants. Reject any source-image reuse, split leakage, duplicate bytes, geometry/material/depth/overlap mismatch, or missing paired appearance before training.


### E-20261002-AI-503 — residual v3 Isaac renderer passes a bounded four-target smoke

- Stage: S2/S3 fresh synthetic residual-obstruction renderer and admission, partial smoke only.
- Lane: AI/model Isaac rendering and synthetic evidence admission only; no arm-lane or integration-gate status changed.
- Claim commit: `14c3d2ff0cffd6bad1a7bb96194f6efa98c9348c`.
- Implementation/evidence commit: `04d333b7db120d10e6e5b818128fcbfd04cdd90c`.
- Change: added an Isaac Sim 6.1 target-local renderer that reads the frozen v3 fixture, creates fresh USD board/target geometry, assigns distinct target semantics, builds actual 3D cable/tool/foreign-object obstruction primitives, samples RGB/semantic/depth annotators, applies paired appearance and deterministic sensor variants, and fails closed when measured target overlap falls outside the frozen contract. Target-range arguments bound GPU resource use. Only RGB crops are retained as model inputs; semantic and depth data are admission evidence and are not model inputs.
- Exact successful command: `$env:OMNI_KIT_ACCEPT_EULA='YES'; C:\IsaacSim\env_6_1_0\Scripts\python.exe software\integrations\isaac_sim\residual_obstruction_v3_isaac_probe.py --workspace . --fixture software\ai\sim\evidence\residual_obstruction_successor_v3.json --output-dir C:\IsaacSim\artifacts\issue190\residual-v3-smoke-009 --scene-limit 1 --target-start 0 --target-count 4 --status-output C:\IsaacSim\evidence\residual-v3-smoke-009.status.json`.
- Bound fixture SHA-256 values: retained fixture file `56b04e0bcc35c26eea2848a0244827d7285e5056667f17deae628c0986921cbd`; canonical fixture `7e861cb17b5f4717d732989d1ddaaeb4ab3e3e4e0ae1d92dd19de35afa397fed`.
- Successful smoke: one of 12 frozen scenes, four of 75 targets, four paired appearances, and all 12 variants produced 192 observations. All 192 RGB hashes are unique. The retained external directory contains 193 files totaling 629,212 bytes. Manifest file SHA-256 is `b9de04520d2618f76c8df2ea16a374430d2645f66945c42fedd327a5fedd8469`; canonical dataset SHA-256 is `f640d67ff700c567a7908d8e71857e7ffcc56f00067e12af77beb98f03379778`.
- Measured overlap: adjacent-left and adjacent-right `0.0`; rubber and translucent cables `0.6`; matte tool edge `0.45` to `0.5`; gloss tool center `0.75`; foreign object `0.56` to `0.5875`. Every value is inside its predeclared variant band.
- Artifact SHA-256 values: renderer `b22e2fb3ebf5743bfb0ca51bfeefa2de66b23249d98dacdc7dfba9d8f473a9b8`; smoke schema `21ecba598143240072dd5096aa6a12592281ecb42282d0d80ec49ca3360d40fe`; smoke report file `2210af5f352ca49615ff96aa18ed8b6fa51c0d4e78b8351fdf1cac81f4364dc2`; canonical smoke report `3632fc4bd3ed169b70b5ab36690cc11c690cec3fc6c0eee5aef05ec46b14f439`; focused tests `47fa731de3b0eb939488305a44cb6a41eae8b4e0c5b18544ab12ee61b3466b07`; registry file `6a3ee39f9b8b61cac370bb2357a48cf30428733d1d5e9ed2b82d002db22f5c23`; canonical registry `f00c7c3e9cb1391b2c083e726a5906d2b32c18bc2ac23f5dd7acd2e2515fd0de`; registry-audit file `9290a0adbd59ba9a4f2ca7ddb83bef9642b627dfef50efe82a416d0e26d3ab5a`; registry-audit receipt `087c1740f3cb19b0b1ac802637beb46c88f0e2ebe3db98523bbbab0d59bedc9b`.
- Validation commands: the exact Isaac command above; `python -m pytest -q software/ai/tests/test_residual_obstruction_v3_renderer_smoke.py software/ai/tests/test_ai_work_registry.py`; `python -m pytest software/ai/tests -q`; `python -m pytest software/tests/unit/test_model_motion_ingress_v2.py software/tests/integration/test_model_arm_conformance_profile_v1.py -q`; `python -m ruff check software/integrations/isaac_sim/residual_obstruction_v3_isaac_probe.py software/ai/tests/test_residual_obstruction_v3_renderer_smoke.py software/ai/tests/test_ai_work_registry.py`; `python software/ai/eval/audit_ai_work_registry.py --output software/ai/eval/ai_work_registry_audit_v1.json`; `python scripts/ci/check_docs.py`; `python scripts/ci/check_public_records.py`; `python scripts/ci/check_evidence_scope.py`; `python scripts/ci/check_repository_artifacts.py`; `python scripts/ci/check_repository_health.py --policy-only`; `python scripts/ci/check_source_archive_footprint.py --json`; `python scripts/ci/check_release_integrity.py --mode policy`; `python scripts/ci/check_release_readiness_sync.py`; `git diff --check`.
- Validation result: three focused smoke tests and six registry tests passed; all 269 AI tests passed with two expected Windows symlink skips; all 34 shared ingress/conformance tests passed; Ruff, registry, maintained-document, public-record, evidence-scope, repository-artifact, repository-health, source-footprint, release-integrity, release-readiness, and diff checks passed. Registry audit covers 53 tracked/documented AI tests and 182 referenced paths. The committed footprint is 6,182 tracked files, 655,570,435 logical bytes, 4,890,152 governed duplicate bytes, and a 55,939,877-byte largest blob.
- Preserved failed evidence: `smoke-001` created 75 simultaneous RGB/semantic/depth render products and Isaac terminated after exhausting the RTX descriptor pool; no manifest was admitted. `smoke-002` produced 192 observations before measured-overlap admission existed and is not admitted. `smoke-003/004` failed closed because the first cable-overlap denominator included neighboring target semantics. `smoke-005/006` failed closed because all target distractors were visible together. `smoke-007` failed closed because tool-center overlap was `0.90`, above the frozen `0.80` maximum. `smoke-008` failed closed because foreign-object overlap was `0.9875`, above the frozen `0.70` maximum. The first registry update also failed because its strict schema permits only `software/ai/...` source paths; the integration script was removed from that registry list instead of broadening the schema.
- Hardware-write count: 0.
- Physical-movement count: 0.
- Physics-step count: 0; the successful smoke used 192 zero-delta Replicator render captures and did not advance a robot simulation or emit an arm command.
- Limitations: this is synthetic partial renderer evidence, not a complete corpus, trained model, untouched evaluation, camera qualification, localization qualification, measured projection/dilation evidence, collision proof, contact success, deployment qualification, or physical qualification. Eleven scenes and 71 targets remain unrendered. Isaac closes before the optional status file is flushed, so the external manifest and repository smoke report are the authoritative retained records for this increment. No controller command, joint/PWM/serial/Waveshare field, motion policy, permit, transport field, or physical authority exists here.
- Supersedes: none. Residual v1, residual v2, and v16 remain rejected; v3 training and evaluation remain unopened; geometry-first handling remains primary for known self-occlusion.
- Next dependency: add an independent shard merger/admission verifier, render all frozen train/development scene-target shards, and verify exact coverage, uniqueness, split isolation, fixture binding, overlap, material, and depth before any v3 training.

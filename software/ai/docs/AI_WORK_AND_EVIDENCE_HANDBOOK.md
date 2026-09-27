# AI work, testing, and evidence handbook

**Purpose:** one maintained procedure for understanding, changing, testing, and
reviewing the Tactevra AI lane.

**Authority:** documentation and offline evidence only. Nothing in this handbook
opens a camera, starts a controller, writes hardware, installs qualification, or
authorizes movement.

## Authoritative navigation

| Need | Authoritative record |
|---|---|
| Current stage and ownership | [Shared AI/arm workplan](SHARED_AI_ARM_WORKPLAN.md) |
| Chronological results, including failures | [Evidence ledger](EVIDENCE_LEDGER.md) |
| AI workstream-to-source/test/evidence ownership | [AI work registry](AI_WORK_REGISTRY.json) |
| AI-to-runtime contract | [Contract](CONTRACT.md) |
| Translation invariants | [Translation assurance](MODEL_TO_ARM_TRANSLATION_ASSURANCE.md) |
| Motion proposal boundary | [Model motion proposal](MODEL_MOTION_PROPOSAL.md) |
| Runtime sequence | [Runtime implementation plan](MODEL_COMMAND_RUNTIME_IMPLEMENTATION_PLAN.md) |
| Model architecture and priorities | [AI system baseline](AI_SYSTEM_BASELINE_AND_IMPLEMENTATION_PLAN.md) |
| Training history | [Training README](../train/README.md) |
| Evaluation history | [Evaluation README](../eval/README.md) |
| Test ownership and commands | [AI tests README](../tests/README.md) |
| Final-camera procedure | [Physical-camera campaign](PHYSICAL_CAMERA_LOCALIZATION_CAMPAIGN.md) |
| External checkpoint identity | [Pose checkpoint artifact](POSE_KEYLOSS_EXTERNAL_ARTIFACT.md) |

The JSON registry is machine checked. Every tracked AI test must have exactly
one workstream owner and every source, documentation, test, and evidence path in
the registry must exist.

## System boundary

```text
user request
  -> grounded intent or explicit rejection
  -> deterministic ActionPlan
  -> image-bound scene observation
  -> named-target localization plus calibrated uncertainty or abstention
  -> ordered ModelMotionBatch
  -> deterministic arm ingress, calibration, IK, collision and dynamics checks
  -> separately authorized controller path
  -> independent device-effect verification
```

The AI boundary ends at `ModelMotionBatch`. AI code may not emit joint targets,
PWM, controller JSON, serial bytes, permits, transport choices, collision-clear
claims, or physical success claims.

## Current model and method inventory

### Intent and language models

- The deterministic grounded parser is the current reference because it binds
  the literal request to the runtime compiler and rejects unsupported phrasing.
- The locally evaluated Llama 3.1 8B Q4 candidate scored 17/31 on the first
  frozen comparison, made five false execution proposals, and returned one
  invalid response.
- The official Llama 3.2 1B candidate scored 0/31 with the strict proposal
  contract before fine-tuning.
- SFT v0 through v3 improved portions of the offline benchmark but retained
  wrong compiler-accepted proposals or lost supported-request coverage. All
  remain blocked from arm control.
- The grounded path scored 30/30 on the agent-authored v9 challenge. That is a
  narrow offline result, not proof of general English understanding or safety.

### Scene model

- Offline Gemma 3 4B is the provisional scene observer.
- It detected a keyboard in 10/10 correlated positive setup photos with 1.692
  seconds median latency.
- The deterministic image-quality gate rejected five severe stress variants.
  The model itself still described a keyboard in some corrupted or absent-device
  cases, so deterministic fusion remains required.

### Precision model

- KeyboardPoseNet and its translation-weighted research checkpoint estimate
  keyboard center and yaw for deterministic target projection.
- The translation-weighted development candidate measured 0.906526367 mm mean
  key error and 2.051064264 mm p95 on synthetic development data.
- The separately retained precision-adapter study has a conservative
  14.400834977 mm bound. It crosses ordinary key safe regions, so no deployment
  qualification is installed.
- Checkpoint bytes remain external. Git retains exact size, SHA-256, provenance,
  a compact scorecard, and separate absent/present verification receipts.

## Work lifecycle

Every AI increment follows this sequence.

### 1. Select and claim

1. Fetch current protected `main`.
2. Read the shared workplan and latest relevant evidence rows.
3. Select one bounded stage and AI-owned path set.
4. Add one active-work claim before changing implementation.
5. Work on a dedicated branch. Preserve other branches as research history.

### 2. Freeze the question before measuring

Record before training or evaluation:

- objective and promotion criterion;
- exact source commit;
- model/base revision and license status;
- tokenizer, template, preprocessing, and generation settings;
- training, calibration, development, and held-out dataset identities;
- split construction and reuse status;
- seeds, budget, optimizer, loss, and selection rule;
- target catalog, camera/configuration domain, and coordinate frames;
- expected output schema and explicit forbidden fields.

If an evaluation set influences a prompt, rule, threshold, checkpoint, or
example choice, mark it consumed and freeze a new held-out set.

### 3. Run without changing the contract

- Keep raw/bulk runs and model weights in ignored or external storage.
- Record exact commands and dependency/runtime versions.
- Hash inputs before the run and outputs before review.
- Keep calibration and held-out evaluation separate.
- Preserve invalid outputs, abstentions, false execution proposals, and failure
  case IDs.
- Never repair labels or omit difficult cases after seeing model output.

### 4. Evaluate the relevant failure modes

Intent work reports exact match, compiler acceptance, false execution, invalid
output, supported-request coverage, and latency.

Scene work reports device presence, condition class, image quality, obstruction,
abstention, disagreement, and per-condition errors.

Localization work reports per-target and per-condition mean, p95, maximum error,
coverage, uncertainty calibration, safe-region fit, and abstention. Average
accuracy cannot replace a conservative bound.

Integration work reports exact plan, image, observation, model, target-map,
calibration, configuration, and batch identities. It separately records permits,
commands, writes, retries, movements, and independent outcomes.

### 5. Test in layers

Run the smallest meaningful focused tests first. For a clean full-AI-suite
environment, create `.venv-ai`, install the repository base and test groups,
then install the exact AI research dependencies:

```powershell
python -m venv .venv-ai
.\.venv-ai\Scripts\python.exe scripts/ci/offline_checks.py install-base
.\.venv-ai\Scripts\python.exe scripts/ci/offline_checks.py install-tests
.\.venv-ai\Scripts\python.exe -m pip install -r software/ai/requirements-test.txt
```

Run the maintained suite and audits from that environment:

```powershell
.\.venv-ai\Scripts\python.exe -m pytest software/ai/tests -q
.\.venv-ai\Scripts\python.exe software/ai/eval/audit_ai_work_registry.py
.\.venv-ai\Scripts\python.exe scripts/ci/check_docs.py
.\.venv-ai\Scripts\python.exe scripts/ci/check_evidence_scope.py
.\.venv-ai\Scripts\python.exe scripts/ci/check_public_records.py
.\.venv-ai\Scripts\python.exe scripts/ci/check_repository_artifacts.py
.\.venv-ai\Scripts\python.exe scripts/ci/check_release_integrity.py
```

Run the shared producer/consumer boundary tests whenever a batch, precision,
capture, schema, or arm-consumed contract changes. Run the portable repository
suite from a fresh `.venv-ci` checkout before review.

### 6. Retain evidence

Commit small reviewable records:

- plan or manifest;
- compact scorecard;
- schema and source tests;
- reproduction/provenance instructions;
- exact file identities;
- limitations and next dependency;
- zero or nonzero hardware-write and physical-movement counts.

Keep checkpoints, adapters, raw captures, bulk prediction tables, caches, and
logs outside Git. Use an external-artifact manifest when exact bytes must be
recoverable. Absence and presence receive separate receipts.

### 7. Record failures before corrections

Append failed or blocked evidence with the exact command and cause. A later
correction receives a new evidence ID. Never rewrite a failure as if the first
attempt passed, delete inconvenient cases, or silently change a benchmark after
it has been consumed.

### 8. Review and hand off

Before opening a PR, provide:

- selected stage and workstream;
- full tested commit SHA;
- exact commands and fixtures;
- metrics and case counts;
- model/data/artifact hashes;
- authority counts;
- limitations;
- next dependency;
- evidence-ledger entry;
- updated registry when source, tests, documentation, or evidence ownership
  changes.

Remove the active claim in the same commit that adds the completion evidence.
AI may mark only its own lane ready. It cannot change arm status or declare an
integration gate complete.

## Physical-camera process

The camera campaign begins only after the four retained ARM-070 originals,
frozen camera mode and support, configuration epoch, camera intrinsics, required
transforms, keyboard target map, and model manifest exist.

Bulk images and independent surveyed-fiducial truth remain external. The
campaign requires disjoint calibration and evaluation sessions, 300 captures
per split, and declared lighting, blur, occlusion, placement, and device-absence
coverage. Run the read-only preflight before model evaluation. A passing
preflight establishes evidence identity and coverage only.

## Meaning of status claims

- **Research result:** measured under its declared synthetic or offline scope.
- **Identity verified:** bytes match a manifest; quality is not established.
- **Implemented zero authority:** code path and contracts exist without physical
  permission.
- **Ready for integration:** one lane passed its own criteria; the shared gate
  has not necessarily passed.
- **Qualified:** the exact model, domain, calibration, configuration, and bound
  passed the applicable held-out gate.
- **Physical success:** a separately authorized action occurred and an
  independent observer verified the intended device effect.

Do not collapse these terms. In particular, simulation success, servo arrival,
model confidence, and artifact identity do not prove a key press.

## Maintaining this handbook

When a new AI source area or test is added:

1. assign it to exactly one registry workstream;
2. update the workstream result, limitations, and next gate;
3. add or revise the governing procedure;
4. run the registry audit and AI tests;
5. append evidence rather than replacing history.

The registry audit is intentionally structural. It makes undocumented tests and
stale links visible, while the frozen scorecards and ledger continue to govern
the truth of model-performance claims.

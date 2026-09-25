# Power-safety and first-power assessor rehearsal

Scope: the standalone `rehearsal_power_stages.py` evaluator and retained verifier
for canonical stages 10 (`power_safety`) and 11 (`power_on_observation`). This
module performs **hardware-incapable software checks**, not a physical power
ceremony. It does not add UI controls, commit M1 stages, publish physical
receipts, issue permits, inspect equipment, enumerate devices or open a port.
Shared service/UI/reopen integration is a separate layer; consult the current
[implementation record](WIZARD_IMPLEMENTATION_PROGRESS.md) for that status.

Read with the [remaining-stage map](WIZARD_REMAINING_STAGE_INTEGRATION.md),
[connection integration plan](CAMERA_ARM_CONNECTION_INTEGRATION_PLAN.md), and
[developer playbook](CAMERA_ARM_DEVELOPER_PLAYBOOK.md). The existing canonical
stage catalog remains authoritative for stage order and real effect boundaries.

## What is actually evaluated

The evaluator constructs exact `PowerSafetyReview` and `FirstPowerObservation`
models and invokes the existing `assess_power_safety` and
`assess_first_power_observation` functions. It retains every complete typed input
and every complete assessment. It does not promote the legacy procedure-shaped
provider's checklist-field presence into safety success.

There are 11 stage-10 checks (10 assessor cases plus one zero-effect invariant)
and 15 stage-11 checks (14 assessor cases plus one invariant). First measured
canonical report sizes were approximately 56 KiB and 78 KiB, respectively;
the strict maximum is **96 KiB**, leaving room in the existing 128 KiB M1 payload
limit for the service's wrapper. Nothing is truncated to meet that limit.

| Stage | Nominal cases | Explicit fault cases |
| --- | --- | --- |
| 10 | Complete synthetic disconnected power-off review | Unknown power, uncertain review, connected power, unverified stop, wrong voltage/current, missing polarity verification, unsecured arm/camera/placemat, missing cable/clearance/reachable-disconnect checks, unexpected energization/motion/contact during review |
| 11 | Complete synthetic event with no startup motion; complete synthetic event with expected automatic repositioning | Unknown final power, lost observation, automatic retry, multiple attempts, unbounded or unknown startup motion, uncertain effect/outcome, connected pre/post state, missing startup prerequisites, abnormal observations, controlled abort |

Stage 10's uncertain input is `HOLD` under its actual assessor. Stage 11's unknown
final power or lost observation is `SIDE_EFFECT_UNCERTAIN`, not ordinary `HOLD`.
An expected fault check passes only when both the exact disposition and sorted
reason codes match its independent finite expectation. The full returned report
also includes the assessor's Boolean readiness/hold/uncertainty fields.

Each `NOMINAL` row must independently pass. A matching `EXPECTED_FAULT` row does
not supply nominal readiness. A coherent assessor regression is retained with
failed checks and overall `BLOCKED`, even if the other cases passed. Malformed
reports instead fail verification; neither path invents a successful result.

## Binding and public API

`RehearsalPowerBinding` is frozen and validates these exact fields:

- `workspace_source_sha256`, `catalog_sha256`;
- `cell_id`, `session_id`, `operator_id`;
- `stage`, exactly `power_safety` or `power_on_observation`;
- `predecessor_receipt_sha256`, `predecessor_assessment_sha256`,
  `predecessor_review_sha256`;
- `arm_identity_evidence_sha256`, the inner retained stage-9 evaluator digest.

The predecessor trio hashes the **complete canonical M1 evidence payloads**,
including an assessment's embedded self-hash when present. It is not the
assessment's internal `assessment_sha256` field. The service must authenticate
and recursively verify the same original-session reviewed predecessor chain:
stage 9 for stage 10, stage 10 for stage 11. This module cannot discover whether
a supplied hash belongs to a trusted or passed predecessor.

```python
from rocell.application.rehearsal_power_stages import (
    RehearsalPowerBinding,
    evaluate_rehearsal_power_stage,
    verify_rehearsal_power_evidence,
)

# Values come from owned, verified server-side session/evidence state.
binding = RehearsalPowerBinding(**trusted_binding_fields)

# Only an explicit admitted collection action calls evaluation.
evidence = evaluate_rehearsal_power_stage(workspace, binding, sequence=0)
payload = evidence.canonical_bytes()

# At assessment, review and reopening: verify the retained bytes, never evaluate.
retained = verify_rehearsal_power_evidence(
    payload,
    expected_binding=binding,
    expected_evidence_sha256=trusted_retained_evidence_sha256,
    expected_evaluator_source_sha256=trusted_evaluator_module_sha256,
)
```

`sequence` is a strict integer from 0 through 1,000,000. It changes only synthetic
fixture identities and deterministic timestamps. It does not retry a power event
or change an attempt count. The caller should normally use the exact stage
collection sequence it already owns. There is no provider, raw observation,
hardware-enable Boolean, path-to-media, serial command or energy-control argument.

`RehearsalPowerEvidence` provides `outcome`, `checks`, `evidence_sha256`,
`evaluation_sha256` (an alias), `canonical_bytes()` and `to_dict()`. Returned nested
reports/checks are detached copies. The digest is computed over the immutable
canonical bytes; it is intentionally **not** a self-referential payload field.

## Provenance and retained data

The exact envelope includes schema, stage, binding, evaluator, sequence,
provenance, complete `reports`, per-report hashes, `selected_inputs`, its hash,
derived checks/outcome, zero-authority fields, and an explicit scope statement.

Evaluation reads only three fixed, bounded Python source files: this module,
`physical_onboarding_receipts.py`, and `physical_onboarding.py`. It rejects
link/reparse components, requires the selected workspace to contain the loaded
evaluator, and rechecks all three files before returning. The evaluator's
`source_file_sha256` is the SHA-256 of **this module alone**, for consistency with
the other stage evaluators. `dependency_source_sha256` separately retains the
other two exact file hashes. These provenance reads do not authenticate a
caller-supplied workspace snapshot; the service's source-drift gate still applies.

Inner legacy receipt bindings use domain-separated synthetic source/header
digests and `synthetic-...` session/cell identifiers. They are assessor fixtures,
not physical M1 session headers or independently publishable admission evidence.
Their bound media slots contain retained small synthetic text documents, not
inspection photographs or event video. All synthetic package/manifest/payload
documents, byte sizes and hashes are retained and reconstructed exactly. Names
like `wiring_image_evidence_ids` are the existing typed model's slots; this
rehearsal does not claim that the text is a real wiring image.

`selected_inputs` includes that fixture material, every complete typed subject's
semantic receipt hash, stage-plan hash, arm identity dependency and predecessor
stage. Settings and image datasets are explicitly not applicable because no
device is configured and no native camera data is evaluated here.

The public compact projection can expose:

```text
stage, outcome, evaluation_sha256, selected_inputs_sha256,
checks, provenance, physical_authority=false, meaning
```

Each of at most 16 checks has exactly `check_id`, `check_kind`
(`NOMINAL`, `EXPECTED_FAULT`, or `INVARIANT`), strict Boolean `passed`, bounded
`observed`, and `meaning`. Display expected-fault success as a rehearsal check
passing, not a successful power operation. Do not render a power switch or infer
physical connection from the nominal synthetic disposition.

## Retained verification and failure behavior

Verification performs no filesystem or OS work and never calls an assessor or
the evaluator. It parses canonical bounded JSON, reconstructs the actual typed
models, compares them with the exact finite fixtures, validates complete report
schemas/subject bindings/self-hashes/authority/Boolean consistency, and derives
checks from the closed expectations. It checks the input manifest, per-report
hashes, selected-input hash, full expected binding and overall outcome.

Duplicate/unknown/missing fields, floats or nonfinite values, oversized/deep
structures, Boolean-as-integer confusion, noncanonical encodings, changed
subjects, substituted parent/session/source data, forged check results and
conflicting assessment fields fail closed. Verification does not repair evidence
or replay collection. A previously retained `BLOCKED` report remains blocked.

Both expected digest arguments are optional for isolated structural tests, but
**the service must supply both from trusted state** at assessment, review and
reopen. Hashes in an untrusted envelope alone do not authenticate provenance.
The source and complete evidence pins also bind the retained dependency hashes;
the pure verifier deliberately does not read dependency files itself.

Collection cancellation and evidence retention are owned by the integrating
service: check cancellation/source/owned transaction freshness before evaluation,
again before publication, and before linking or committing a result. A cancelled,
orphaned, missing or unverified result must not become an approved stage or be
automatically regenerated on reopening. This evaluator has no persistence or
stage-commit hooks and cannot clear such a hold.

## What remains physically unverified

All actual device enumeration/open, hardware command, power event, motion/contact
command, physical receipt publication and permit publication counts are zero.
Synthetic observation fields are procedural test inputs, not predicted startup
trajectories, measured clearance, installed safety or independent final power-off
proof. Their uncertainty classification is a software test outcome, not a claim
that an actual arm was energized and is now in an unknown state.

The received build still needs measured supply/polarity, secured structures,
independent disconnect/stop validation, startup swept-volume and gravity
containment evidence, cable restraint, an independently controlled/observed
startup event, and independently confirmed final disconnection. UI cancellation,
worker exit, serial close or a passing synthetic report establishes none of these.
Stage 12 controller connection and all later physical work remain outside this
module; no physical hold or energy-control policy is weakened here.

## Tests

Run from the workspace root:

```powershell
.\.venv\Scripts\python.exe -m pytest software/tests/unit/test_rehearsal_power_stages.py -q
```

The suite exercises every finite scenario against the actual assessors, retained
full-report equality, complete source/session/predecessor binding, tampering,
schema/size/type bounds, unknown power versus ordinary hold, nominal and
expected-fault assessor regressions, immutable output, explicit synthetic media,
source changes during collection, and no-I/O/no-assessor verification. Test
failures are not interpreted as physical faults and no test opens hardware.

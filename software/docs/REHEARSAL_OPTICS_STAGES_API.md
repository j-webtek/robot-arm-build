# Hardware-free stage 7–8 evaluator and rehearsal workflow

The evaluator alone does not advance a wizard stage, open a camera, issue a
permit, or qualify installed optics/calibration. The application integration
retains and assesses its reports through the existing original-session M1
REHEARSAL workflow; a separate exact human review remains required.
See the [remaining-stage implementation map](WIZARD_REMAINING_STAGE_INTEGRATION.md)
for the design rationale and integration work beyond this bounded slice.

The service/reopen integration is implemented in the working tree. The real
Windows M1 eight-stage progression passed, including original-store reopening
with a WAIT receipt, pending review and completed stage 8 (313.29 seconds).
The six additional failure/cancellation store cases passed in 1,225.30 seconds;
all seven real-store integration cases passed. The evaluator, pure UI, terminal,
action-registry and local-server selection passed 224 tests, and both Arrival
action-preview tests passed. Do not infer physical readiness from these checks.

Implementation: [rehearsal_optics_stages.py](../src/rocell/application/rehearsal_optics_stages.py).
Tests: [test_rehearsal_optics_stages.py](../tests/unit/test_rehearsal_optics_stages.py).

## Public API

`RehearsalOpticsBinding` is a frozen dataclass with exact fields:

- `workspace_source_sha256`, `catalog_sha256`, `cell_id`, `session_id`,
  `operator_id`, `stage` (`optics_intrinsics` or `static_registration`).
- `predecessor_receipt_sha256`, `predecessor_review_sha256`.
- `camera_identity_sha256`, `settings_epoch`, `camera_dataset_manifest_sha256`.

All hashes are lowercase SHA-256. Identifiers are bounded nonempty strings;
arbitrary filesystem/device paths and authority flags are not accepted.
These values are caller-owned dependency bindings. The caller must derive them
from verified current session evidence, not browser-submitted trusted hashes.

```python
evidence = evaluate_rehearsal_optics_stage(workspace, binding, sequence=0)
payload = evidence.canonical_bytes()  # Immutable UTF-8 JSON, at most 96 KiB.
digest = evidence.evidence_sha256    # SHA-256 of the full canonical payload.

verified = verify_rehearsal_optics_evidence(
    payload,
    expected_binding=binding,
    expected_evidence_sha256=digest,
    expected_evaluator_source_sha256=trusted_evaluator_source_digest,
)
```

The verifier's two expected digest arguments are optional for structural checks;
assessment/review/reopen integration should supply independently trusted retained
digests. Without a trusted digest, a self-consistently rewritten document proves
only its own consistency, not that an approved evaluator produced it.

`RehearsalOpticsEvidence.outcome` is `REHEARSAL_CHECKS_PASSED` or `BLOCKED`;
`.checks` and `.to_dict()` return detached data. All outcomes retain zero physical
and stage-advance authority. Exceptions are `RehearsalOpticsError` for malformed,
inconsistent or over-budget evidence; input/resource failures do not manufacture
a passing report. Existing lower-level acquisition/parser failures may also
raise before a retained result exists; the service must hold rather than infer
successful collection.

## Work performed

Stage 7 reads only the fixed existing synthetic intrinsics fixture and purchased
profile. It invokes the real strict parser and assessor, retains the exact
fixture UTF-8 bytes and full assessment, and records its fit/held-out counts and
source/input/split hashes. This is a schema/residual contract rehearsal, not an
installed-camera numeric solve or focus measurement.

Stage 8 runs the existing B0477 nominal and tag-loss JPEG pixel pipelines at the
same bounded synthetic sequence (0–1,000,000). It retains both complete structured
reports, their input pixel hashes and source manifests. Its actual nominal
pose/inlier/residual policy and independent K0/P0 checks must pass **and** the
negative probe must reject without a pose. A `REJECTED` label alone is insufficient;
expected negative-test success cannot replace failed nominal checks. Intrinsics
stage accepts only the unused default sequence zero.

The selected session camera/settings/dataset hashes are dependency-only. The
evaluated image pixels come from the existing nominal scene renderer, **not** the
stage-6 native-sized binary dataset. This module does not retain JPEG bytes,
prove native-frame freshness, measure the purchased lens, redefine board geometry,
or assert that fixture optical settings equal session settings.

## Evidence shape and verification

Schema: `rocell.rehearsal_optics_stage.v1`. Exact top-level keys:

`schema`, `binding`, `evaluator`, `sequence`, `provenance`, `reports`,
`report_hashes`, `selected_inputs`, `selected_inputs_sha256`, `checks`, `outcome`,
`authority`.

`evaluator` contains the fixed algorithm identifier and the evaluator source-file
SHA-256 observed during explicit evaluation. Stage 7 `reports.intrinsics` contains
`fixture_path`, `fixture_utf8`, `fixture_sha256`, and `assessment`. Stage 8 contains
`reports.normal` and `reports.tag_loss`. Full reports are retained; nothing is
truncated to fit the limit. Current nominal payloads are approximately 25 KiB and
23 KiB respectively, leaving room beneath the reopening evidence cap for a small
outer stage receipt.

Verification is pure: it reads no files, runs no detector/renderer/solver/assessor,
opens no provider, and changes no session. It reparses the retained intrinsics
artifact or reconstructs the existing pure vision value models, verifies exact
report schemas and source links, and recomputes checks/outcome/input hashes from
retained substantive fields. Embedded `outcome` and `checks` are never authority.
A regressed assessor's reported failure remains `BLOCKED`, even if parsing the
fixture succeeds. Invalid or unknown fields, Boolean-as-number substitutions,
nonfinite values, duplicate keys, excessive nesting/length, mismatched bindings,
changed source links or stale trusted hashes reject verification.

## Required caller responsibilities

- Bind the exact due stage and reviewed predecessor to the original durable
  session; separately verify the stage-6 binary capture chain and current epochs.
- Invoke evaluation only after an explicit prepared action. No work on imports,
  view, tab changes, polling or reopening. Do not replay a missing collection.
- Retain the complete canonical report under a guarded M1 transaction before
  assessment; preserve failures/cancellation and do not fabricate camera attempts.
- Verify expected bindings and retained digest again for assessment/review/reopen.
  Human review remains separate and cannot change a blocked derived result to pass.
- Keep physical commissioning, installed measurements and contact release held.

## Durable integration contract

The stage receipt is `rocell.rehearsal_optics_receipt.v1`: existing
rehearsal common fields plus `evaluation` (the complete document) and
`evaluation_sha256`. An explicit collect first stores
`rocell.rehearsal_optics_stage_open.v1`, then evaluates, then retains the result.
Cancellation before result publication leaves a held missing-result stage;
reopening does not repeat the evaluation. There is no fabricated camera attempt
or physical observation associated with these no-device checks.

Service and reopen derive dependencies from the verified stage-6 camera receipt,
selected identity/settings and the immediately preceding committed PASS
receipt/review. Stage 8 also verifies the retained stage-7 evaluator result. They
use the current trusted evaluator source hash, not its self-declared hash alone.
The original stage-6 ingest envelope and native dataset content must still verify
before acceptance. Stored M1 ASCII JSON is explicitly converted back to the
evaluator's canonical UTF-8 before its digest is checked.

Collection success is separate from technical readiness: collecting a valid
`BLOCKED` report succeeds as a retention operation, but assessment derives
`OPTICS_CHECK_FAILED:<check_id>` reasons and review cannot override them. Both
frontends display those actual checks, their values and synthetic limitations.
The complete report is also included in the collect-operation result for bounded
diagnostic export; old operation results may be omitted under the existing
declared retention policy, while the original immutable M1 receipt remains.

### Operator sequence and interruption semantics

1. Review the original stage-6 camera result before preparing stage-7 collect.
2. Explicitly collect using the registered action and an operator identity. The
   service records `WAITING_OPERATOR` and the opening receipt before performing
   the bounded fixture evaluation; collection alone grants no stage acceptance.
3. Inspect the full result or compact check card. Explicit assessment revalidates
   retained dependencies and derives PASS/BLOCKED from the substantive checks.
4. A distinct reviewer accepts that exact assessment and preceding state head.
   A failed technical check remains BLOCKED regardless of reviewer intent.
5. Repeat the explicit process for stage 8. The next unsupported stage stays
   held; there is no implied full-wizard or physical release.

Stop is checked after potentially long dependency reads, before image probes,
after evaluation before result publication, and before assessment/review
publication and state commit. A committed receipt remains inspectable; a missing
or orphan result remains held. Stop does not mean the arm was emergency-stopped.
Explicit reopening can restore a complete WAIT receipt or pending review without
rerunning any probe. It cannot manufacture a missing result, copy the session,
restore old human approval, or implicitly load a camera preview.

Run the focused hardware-free suite from the workspace root:

```powershell
.\.venv\Scripts\python.exe -m pytest software/tests/unit/test_rehearsal_optics_stages.py -q
.\.venv\Scripts\python.exe -m pytest software/tests/unit/test_commissioning_rehearsal_optics.py -q
.\.venv\Scripts\python.exe -m pytest software/tests/unit/test_arrival_wizard_optics_ui.py -q
```

The real M1 store file is marked `slow`: each case qualifies original Windows
storage and retains native-sized synthetic camera datasets. It is deliberately
excluded by a caller's `-m "not slow"` selection, not replaced with memory-only
evidence. The explicit file command above still runs the full integration lane.

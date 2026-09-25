# Stage-9 arm identity rehearsal API

This is a standalone, hardware-incapable building block for `arm_identity`, not
permission to open a serial port or proof that a received arm is a RoArm-M3 Pro.
It does not publish to M1, advance a wizard, issue a permit, or change power.
Service/review/reopen integration is owned separately and must explicitly admit
this version. Never select a physical device using these fictional identities.

## Public contract

Module: `rocell.application.rehearsal_arm_identity_stage`.

```python
binding = RehearsalArmIdentityBinding(
    workspace_source_sha256=source_digest,
    catalog_sha256=catalog_digest,
    cell_id=cell_id,
    session_id=session_id,
    operator_id=operator_id,
    predecessor_receipt_sha256=receipt_payload_digest,
    predecessor_assessment_sha256=assessment_payload_digest,
    predecessor_review_sha256=review_payload_digest,
    static_registration_evidence_sha256=stage8_evaluation_digest,
    stage="arm_identity",  # default; no other stage accepted
)
evidence = evaluate_rehearsal_arm_identity_stage(workspace, binding)
verified = verify_rehearsal_arm_identity_evidence(
    evidence.canonical_bytes(),
    expected_binding=binding,
    expected_evidence_sha256=trusted_retained_evidence_digest,
    expected_evaluator_source_sha256=trusted_evaluator_file_digest,
)
```

All digests are exact lowercase SHA-256. Predecessor hashes identify complete
canonical M1 receipt/assessment/review payloads, including an assessment's
embedded self-hash; they are not the assessment's internal hash field. The
static-registration digest identifies the inner stage-8 evaluation. The caller
must obtain these values from its audited prerequisite lineage, not browser
fields, and separately check current source/catalog/session/operator authority.

The verifier's two expected hash arguments default to `None`, matching the
optics API. Without trusted hashes it verifies structural/semantic consistency
only, **not authenticated evidence admission**. M1 callers must supply both.
The evaluator cannot establish the truth of arbitrary caller-supplied bindings.

`RehearsalArmIdentityEvidence` holds immutable canonical bytes and exposes
`outcome`, `checks`, `evidence_sha256`, `canonical_bytes()` and `to_dict()`.
Returned dictionaries are independent copies. Constructing a value object is
not verification or admission. `RehearsalArmIdentityError` rejects unsupported,
inconsistent, oversized, duplicate-key, nonfinite or incorrectly bound data.
Malformed fixed inputs fail closed; a valid retained blocked report remains
reviewable and never becomes a successful stage assessment.

## Effects and substantive evaluation

Only the explicit evaluator reads the fixed
`software/config/arm_connection.json`. It invokes the existing
`load_arm_connection_profile` and preserves both exact UTF-8 source/hash and
the loaded profile or bounded rejection diagnostic. Nominal policy requires
the expected Pro model, USB serial/newline contract, 115200 baud, no configured
port/commissioned identity, disabled auto-connect/initialize/RTS/DTR/blind
retry, and exclusive ownership. Unknown profile fields block the check.

The evaluator invokes `inventory_serial_ports_from_provider` ten times with
an internal, closed in-memory enumerator. Nine valid fixture batches flow
through the real `compose_physical_device_inventory_report`; the intentionally
malformed observation is rejected by the existing inventory API. No pyserial
enumeration, OS inventory, subprocess, serial open, camera or network API is
invoked. Constructor/import/verification paths do not perform collection.

| Fixture | Required interpretation |
| --- | --- |
| Nominal | Exactly one complete candidate matches the full fictional selected snapshot. |
| Wrong model | Separately modeled S chassis label does not match Pro; no model inferred from USB. |
| Missing device | Zero candidates cannot select an arm. |
| Missing unit serial | VID/PID and an ephemeral COM name do not replace persistent unit identity. |
| Duplicate identity | Two matching persistent IDs are ambiguous, even with different COM aliases. |
| Stale alias | COM remapping invalidates the selected snapshot; no automatic fallback/reselection. |
| Changed topology | A changed raw location invalidates the snapshot, even when normalized candidate hash is unchanged. |
| Changed interface | Changed interface metadata is detected, not treated as verified driver identity. |
| Changed USB identity | A different persistent identity cannot reuse the old selection/COM alias. |
| Unexpected output | The existing type guard must reject the malformed injected observation. |

Each report retains full raw fixture values, normalized candidates, the composed
inventory report and its hash, expected fault reasons, model-label input, and
any bounded exception. An independent pure oracle checks the limited fixture
normalization against the raw inputs; unexpected metadata changes cannot pass
merely because another expected fault was also detected. This oracle is not an
OS parser and must not be generalized into a physical selection implementation.

The inventory API currently maps raw `interface` to `driver_service`, and does
not include raw `location` in its candidate hash. The evidence explicitly keeps
both observations separately. These fields prove neither actual Windows driver
service/version nor USB topology qualification. The raw HWID field similarly
does not establish a qualified controller or firmware identity. All identifiers
are deliberately fictional `INCAPABLE` values; `COM42` is never opened.

The composer's timestamp is a fixed synthetic zero, labeled as such in
provenance. It is not a fabricated observation time. Source/profile bytes are
checked before and after evaluation. Fixed reads are bounded and reject
link/reparse components; this is not a native file-lock/power-loss qualification.

## Retained schema and UI projection

Version: `rocell.rehearsal_arm_identity_stage.v1`.
Evaluator: `SUBSTANTIVE_SYNTHETIC_ARM_IDENTITY_V1`.
Exact top-level fields:

```text
schema, binding, evaluator, provenance, reports, report_hashes,
selected_inputs, selected_inputs_sha256, checks,
nominal_outcome, negative_checks_outcome, outcome, authority
```

`evaluator` contains `id` and `source_file_sha256`. `selected_inputs` binds the
profile bytes/report, complete scenario inputs/reports, synthetic selection,
and exact predecessor/static-registration hashes. Physical controller, firmware
and driver identities are `NOT_ACQUIRED`; camera settings are explicitly
not applicable because stage 8 is a dependency, not reevaluated here.

There are 12 check rows, each with exactly:

```text
check_id, check_kind, passed, observed, meaning
```

`check_kind` is `NOMINAL`, `EXPECTED_FAULT`, or `INVARIANT`. `profile_policy`
and `nominal_inventory` are nominal. Nine `reject_<fixture>` rows are expected
fault checks. `physical_identity_held` is the invariant. Observations carry
reason codes, candidate counts, report references/hashes and consistency
results; `meaning` names the retained report. No raw protocol bytes or device
control fields are needed in the compact UI projection.

- `nominal_outcome`: `NOMINAL_CHECKS_PASSED` or `BLOCKED`.
- `negative_checks_outcome`: `EXPECTED_FAULTS_REJECTED` or `BLOCKED`.
- `outcome`: `REHEARSAL_CHECKS_PASSED` only when every check passes, otherwise
  `BLOCKED`. Successful negative checks cannot conceal failed nominal checks.

The pure verifier performs no filesystem/provider/loader/composer/evaluator
calls. It reparses typed retained metadata, checks exact closed fixture inputs,
raw/candidate relationships and report hashes, then recomputes checks, input
manifest and all three outcomes. Unsupported fields/versions, Boolean-number
coercion, altered authority/provenance, and inconsistent summaries are rejected.
Bounds are 96 KiB UTF-8, nesting depth 20, 64 fields/elements per container,
signed-63-bit integer magnitudes, finite numbers, two candidates per fixture,
and 2,048-character retained diagnostics. Nominal evidence is about 33 KiB.

## Physical holds and integration responsibility

Every physical authority/effect flag is false, serial bytes written is zero,
release effect is `NONE`, and composition is `HARDWARE_INCAPABLE_REHEARSAL`.
Received Pro arm/chassis/controller evidence, firmware, boot/reset behavior,
installed driver identity/version and actual power state remain unobserved.
The USB bridge, profile model string and synthetic model label cannot qualify
them. This module creates no `ReviewedControllerBinding` or serial capability.

The integrator must retain these bytes and hashes in its existing durable
transaction, verify them again at assessment/review/reopen without replay,
bind current stage-8/camera dependencies, handle cancellation and durable
publication, and maintain distinct reviewer/effect-accounting requirements.
Those actions and the original-store path boundary are outside this module.

## Tests

From the workspace root:

```powershell
.\.venv\Scripts\python.exe -m pytest software/tests/unit/test_rehearsal_arm_identity_stage.py -q
black --check software/src/rocell/application/rehearsal_arm_identity_stage.py software/tests/unit/test_rehearsal_arm_identity_stage.py
mypy --follow-imports=skip software/src/rocell/application/rehearsal_arm_identity_stage.py
```

Tests invoke real profile and injected inventory APIs, verify no replay/file
reads, exercise every fixture, regress nominal and negative outcomes separately,
alter normalized metadata/composer reports, mutate profile policy, tamper all
binding fields/authority/hashes/schema, enforce JSON bounds and source-change
rejection, and confirm immutable retained views. They never enumerate host
devices or open a port.

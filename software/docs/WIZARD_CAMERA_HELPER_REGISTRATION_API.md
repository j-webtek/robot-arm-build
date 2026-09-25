# Camera helper registration: metadata only

Implemented in
[`wizard_camera_helper_registration.py`](../src/rocell/application/wizard_camera_helper_registration.py).
This pure, session-local state records a review of the **fixed development
helper catalog**, not a camera qualification or a trusted software release.
Every state method is inert: no filesystem inspection, provider construction,
process execution, device enumeration, camera activation, probe or capture.

New wizard inspections select the separately built metadata-only v2 catalog
(17 fixed files). Historical v1 reports retain their original 11-file contract.
The verifier dispatches only these known catalog IDs; complete matching rows
are required and the provider revalidates that same catalog before each lookup.
There is no fallback or automatic acceptance of new file hashes. See the
[versioned inspection contract](WIZARD_CAMERA_HELPER_INSPECTION.md) and
[completed successor checkpoint](CAMERA_METADATA_SUCCESSOR_WORKORDER.md).

## Explicit action and publication contract

```python
state = WizardCameraHelperRegistration(mode, session_id, source_sha256)
# The separately admitted inspection action obtains a complete inspection.
staged = state.staged_copy()
report = staged.ingest(
    inspection_report,
    operation_id=inspection_operation_id,
    operator_id=inspection_operator_id,
)
# Caller validates and retains report, durably logs success, then publishes
# staged state. Discard the staged copy if any publication step fails.

preview = state.preview()  # Retained evidence only; never reinspects.
staged = state.staged_copy()
report = staged.review(reviewer_id, operation_id=review_operation_id)
# Perform the same result/log/publication checks before publishing.
artifact = staged.registration()  # Immutable artifact or None; no dispatch.
```

The reviewer label must differ from the inspection operator label, including
case-folded equality. Review and inspection also require different operation
IDs. These are **diagnostic role-separation labels, not authenticated human
identities**. They do not establish independent people or approve a source
change. The wizard owns source/revision checks, cancellation, action admission,
result retention and publication; this registry does not create capabilities.

Before a new inspection or failed source/log boundary, the caller invalidates
the current state and any provider derived from it. Before a review attempt,
`invalidate_review(reason)` clears the old review and registration while
retaining the inspection. `invalidate(reason)` clears both. These changes are
also applied internally before ingest/review validation, so rejected input
cannot leave a prior registration looking current. An output-limit failure
rolls back the affected mutation. `staged_copy()` uses a fresh lock and shares
only immutable bytes and scalar values.

## Exact retained inspection

Ingest takes the actual complete inspection report and invokes the strict
pure `verify_camera_helper_inspection` contract against the constructor's
workspace source and mode-appropriate provenance. Rehearsal accepts only
`INCAPABLE_FIXTURE`; physical-mode metadata review accepts only
`WORKSPACE_FILE_INSPECTION`. The fixed catalog, complete file observations,
inspection digest and eligibility must all agree. Unknown fields, altered
catalog/source/helper hashes, mixed authority and malformed observations are
rejected. Inspection hashes identify retained bytes; they are not signatures
or independent authentication of who obtained those bytes.

`MATCHED_METADATA_CATALOG` permits only a metadata registration. Valid
`MISSING_FILES`, `HASH_DRIFT` and `UNSAFE_OR_UNREADABLE` reports remain explicitly
reviewable but held; acknowledging them produces no registration artifact.
The inspection summary does not display an expected helper digest as an
observed one when eligibility is false. Full observations remain losslessly
retained in `export_snapshot()`.

The historical full-build record is **not silently upgraded**. The warning
`CLIENT_CHANGED_SINCE_BUILD_RECORD` and the separate current client catalog
pin remain visible. Matching this metadata catalog does not prove a current
full-build match, trusted release, driver behavior, process-containment
qualification or received-unit identity. It does not clear any camera/arm
commissioning gate.

## Immutable registration artifact

`ReviewedCameraHelperRegistration` stores bounded canonical JSON bytes.
`.payload`, `.inspection` and `.to_dict()` return detached dictionaries;
`.registration_sha256` hashes the canonical payload, without a self-hash
cycle. The payload binds:

- Mode, session and workspace-source SHA-256.
- Exact catalog, helper and complete inspection digests and provenance.
- Inspection operator/operation and review reviewer/operation labels.
- The closed operations `inventory` and `identity` only.
- Explicit development-only scope and false activation/qualification flags.

The complete inspection is retained alongside the artifact, not duplicated
inside its payload. Public construction of the immutable class does **not**
confer trust. A provider factory must independently validate the artifact's
exact fields, full inspection and expected mode/source/catalog, then recheck
the fixed files before each separately admitted metadata query. Review itself
never reads those files. No raw path or alternative helper can be supplied
through this review API.

## Bounded presentation and errors

`view()` has schema `rocell.wizard_camera_helper_registration.v1` and states
`NO_INSPECTION`, `INSPECTION_RETAINED`, `METADATA_HELPER_REGISTERED`,
`REVIEW_HELD` or `INVALIDATED`. The summary includes only fixed catalog labels
and hashes, inspection/operator/operation provenance, review digest/status,
up to 32 visible holds, and a bounded invalidation reason. It contains no file
paths or complete file list. An inspection retained after review invalidation
remains visible with `INSPECTION_RETAINED` and its reason.

`preview()` is a bounded review summary. `ingest`, `review` and
`export_snapshot()` return the full
`rocell.wizard_camera_helper_registration_report.v1` envelope containing
`view`, complete `inspection_report` and nullable `registration_artifact`.
The envelope is capped at 256 KiB, depth 16, 8,192 JSON nodes, 128 items per
array, 64 fields per object and 4,096 UTF-8 bytes per string. Actor labels and
operation/session identifiers are capped at 128 UTF-8 bytes; UI forms may
impose tighter limits. Reports are rejected rather than truncated.

Historical v1 measurement with its fixed nominal rehearsal fixture and the focused test's short
session/operator labels: the full reviewed report is 7,483 canonical bytes
(9,080 pretty-printed bytes), retains all 11 file observations and displays 10
continuing holds. The actual worker-result envelope also passes the existing
diagnostic sanitizer unchanged; no hash-bound record is silently redacted or
truncated to obtain registration.

`probe_allowed`, `capture_allowed`, `connected`, `qualified` and
`physical_authority` are always exactly false, even when metadata registration
succeeds. `CameraHelperRegistrationError.code` provides a bounded machine
reason; inspector failures are wrapped in a fixed public message, preserving
the original exception only as an internal cause. `KeyboardInterrupt` and
`SystemExit` are not swallowed.

## Hardware-free tests

The focused suite is
[`test_wizard_camera_helper_registration.py`](../tests/unit/test_wizard_camera_helper_registration.py).
It uses the actual incapable fixed-catalog inspection producer and strict
verifier; no filesystem inspection, native helper, OS inventory or device
calls are required. Tests cover full bindings, rehashed forged reports,
held observations, role labels, rollback, stale-state invalidation, immutable
and detached outputs, staged publication, bounds and inert state methods.

Received-hardware testing, trusted release review, native process/driver
qualification and camera capture remain separate, unimplemented permissions
from the perspective of this registry.

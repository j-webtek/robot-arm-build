# Saved workspace-source evidence API

This module produces actual local-file/software facts for canonical stage
`workspace_sources`, then derives a **BLOCKED** assessment and an exact-subject
review. It neither commits M1 records nor changes a stage. The setup service
owns original-store leases, durable append/readback, stage transitions,
publication and restart. There is no PASS override or physical execution API.

## Public contracts

Module: `rocell.application.physical_source_stage_evidence`.

```python
collect_workspace_source_receipt(
    workspace, *, prerequisites, source_sha256, session_id, origin_launch_id,
    collection_launch_id, header_sha256, operator_id, cancellation, progress=None
) -> WorkspaceSourceReceipt

assess_workspace_source_receipt(receipt) -> WorkspaceSourceAssessment
review_workspace_source_assessment(
    receipt, assessment, *, reviewer_id, review_launch_id
) -> WorkspaceSourceReview

verify_workspace_source_receipt(
    value, *, prerequisites, expected_source_sha256, expected_session_id,
    expected_origin_launch_id, expected_header_sha256, expected_receipt_sha256
) -> WorkspaceSourceReceipt
verify_workspace_source_assessment(
    value, *, receipt, expected_assessment_sha256
) -> WorkspaceSourceAssessment
verify_workspace_source_review(
    value, *, receipt, assessment, expected_review_sha256
) -> WorkspaceSourceReview
```

The three frozen types take canonical immutable `payload: bytes`; expose
`.payload`, `.sha256`, `.to_dict()` and `.safe_summary()`; and reject unknown
fields, duplicate keys, invalid types, changed subject chains and oversized
records. Dict/summary results are detached copies. Verifiers accept bytes,
plain bounded dicts or the exact typed artifact. Expected evidence digests must
come from independently audited original M1 references, never a browser field
or the untrusted artifact's own digest.

Schemas are `rocell.workspace_source_receipt.v1`,
`rocell.workspace_source_assessment.v1`, and
`rocell.workspace_source_review.v1`. Labels are exactly
`workspace-source-receipt-v1`, `workspace-source-assessment-v1`, and
`workspace-source-review-v1`. Hashes cover full sorted compact ASCII JSON bytes,
without a newline or an embedded artifact self-hash.

Binding keys are `source_sha256`, `session_id`, `origin_launch_id`,
`collection_launch_id`, `header_sha256`, `prerequisites_sha256`, and `operator_id`.
The original prerequisite's exact workspace-stage row and source-file digests
must match. The assessment binds the receipt digest; review binds both receipt
and assessment digests. Original origin, collection launch and later review
launch are not silently relabeled during restart.

## Actual collection and bounds

The collector calls existing `import_build_snapshot`,
`load_physical_onboarding_foundation`, `load_physical_onboarding_policy`, and
`assess_physical_host_readiness`. It does not use the legacy V1 stage controller
or that controller's software-only PASS predicate.

The retained source roster is the fixed controlled-policy file list plus at
most 64 exact RC03 source entries from the source-bound system manifest. It is
limited to 128 files, 2 MiB/file and 32 MiB aggregate. Files and ancestry are
checked before reads; Windows ordinary disk-file handles exclude concurrent
write/delete sharing while existing semantic loaders reread these paths. A
second file snapshot must agree. Broader implementation sources are separately
covered by the existing bounded workspace fingerprint before/after collection;
this is not a permanent pinned execution window, trusted release or filesystem
rollback qualification. Camera helper binaries are not executed or reapproved.

Receipt, assessment and review are each capped at 256 KiB; summaries at 24 KiB.
Collection has one original 30-second monotonic budget, checked around each
source read, existing calculator and progress callback. Synchronous OS/file
calls are not hard-preempted; a late completion is refused, not advertised as a
timely success. No retry, budget renewal, directories, files or M1 records are
created by the collector.

Host dependency checks inspect package metadata without importing optional
device backends. Windows kernel version is read with `sys.getwindowsversion()`
and passed to the existing host calculator; POSIX uses `os.uname()`. This avoids
the cold `platform.release()` path that can launch Windows `ver`. None of these
observations establishes USB, camera, COM, serial, robot-power or contact state.

`WorkspaceSourceEvidenceError.code` is fixed diagnostic text. Its optional
`.receipt` preserves a complete, already verified receipt when Stop, a progress
callback, deadline or guard cleanup fails late. Such data is historical only;
the service must not publish current success or assert M1 retention merely
because the local receipt exists.

## Assessment, review and projection

Receipt status is `FILE_FACTS_COLLECTED`. Seven software checks distinguish
controlled build integrity, foundation semantics, unchanged file snapshot,
runtime policy, launcher/bootstrap, base software and selected static-camera
plan. The first three require actual successful source verification; malformed
controlled sources do not produce normal-looking receipts.

Assessment is deterministic: `status=ASSESSED`, `verdict=BLOCKED`. Minimum
missing reasons are `DISCONNECTED_ACTUATOR_POWER_NOT_OBSERVED`,
`HZ_012_QUALIFICATION_EVIDENCE_MISSING`, and
`STATIC_CAMERA_RELEASE_NOT_QUALIFIED`; software failures add
`SOFTWARE_PREREQUISITES_NOT_READY`. Even all software checks passing cannot
supply a physical observation or change this version's verdict.

Review is `ACKNOWLEDGED_BLOCKED`, also `verdict=BLOCKED`. Reviewer/operator
labels are nonempty, trimmed, control-free strings at most 128 UTF-8 bytes.
They must differ under Python `casefold()`. Labels remain literal; the review
records `distinct_operator_labels=true` and
`authenticated_independent_people=false`. Procedural labels are not proof of
two authenticated people.

All records/summaries retain `physical_authority=false`,
`canonical_stage_pass=false`, `device_io_performed=false`, and
`power_state=UNKNOWN`; effect counters are exact integer zero. Compact schemas
replace `.v1` with `_summary.v1`, retain original bindings and exact subject
hashes, and omit raw host paths/package-origin details. Assessment/review never
claims M1 commit status—the independently audited session stage owns that fact.

## Verification record

Final focused suite: 50 tests passed, including actual controlled-file
collection with subprocess creation forbidden, pure no-replay verification,
subject/context/type tampering, Unicode reviewer rules, deterministic BLOCKED,
copy isolation and retained late Stop/progress/guard failures. Broad source
fingerprint is explicitly modeled in those file tests; the files/calculators
are real, not modeled physical observations. Black and mypy passed for the
production module. Actual public M1/restart/export verification is separately
owned and recorded by the integration workflow.

Additional final cases cover original-deadline retention, late source drift and
Windows write/rename refusal against a test-owned copied source file. The actual
public application and live-browser results are recorded in
[the integration checkpoint](PHYSICAL_SOURCE_REVIEW_WORKFLOW.md), not inferred
from these pure/file tests.

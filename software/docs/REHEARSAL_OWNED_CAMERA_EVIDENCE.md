# Retained evidence for the incapable owned-camera process

[`rehearsal_owned_camera_evidence.py`](../src/rocell/application/rehearsal_owned_camera_evidence.py)
is a pure evidence boundary, not another worker, provider or coordinator. It
never enumerates devices, starts a process, opens a camera, reads files,
decodes pixels, changes power or grants an execution permit. Its domain is
always `INCAPABLE_CAMERA_PROCESS_REHEARSAL`.

## API

```python
artifact = retain_owned_camera_evidence(
    binding=server_binding,
    activation_request=activation_request_or_none,
    process_result=owned_worker_result_or_none,
    native_receipt=native_camera_receipt_or_none,
    capture=ingest_receipt_or_none,
    error=None,  # Or {code, message, error_type?}.
    capture_envelope=exact_ingest_envelope_or_none,
    source_contract=exact_source_contract_or_none,
)

# Publish artifact.payload in the current coordinator's retained transaction,
# before a known seal. The caller must enforce the coordinator lifecycle.
retained_bytes = artifact.payload
retained_sha256 = artifact.evidence_sha256
summary = artifact.view()

# No worker, solver, provider or filesystem work is replayed here.
verified = verify_owned_camera_evidence(retained_bytes, expected_binding)
```

`RehearsalOwnedCameraEvidence` is frozen and bytes-backed. `to_dict()` returns
the complete detached document; `view()` derives a bounded detached summary.
The schema is `rocell.rehearsal_owned_camera_evidence.v1`. The payload is
canonical ASCII JSON with sorted fields and no trailing newline; its SHA-256
is external, so it has no self-hash cycle.

The caller must first check the independently retained M1 evidence hash and
audit its permit/attempt registration. `verify_owned_camera_evidence` checks
the exact caller-supplied binding and the retained document's contracts; its
signature deliberately does not supply a second expected evidence digest.
An internal hash is not a signature, authentication, physical qualification
or proof that a caller-supplied observation actually occurred.

## Binding and unchanged source contracts

The exact binding has seven fields: `session_id`, `attempt_id`,
`source_sha256`, `permit_sha256`, `operation_sha256`,
`selected_identity_sha256` and `settings_epoch`. Both IDs are bounded to 96
characters; all other fields are lowercase SHA-256 digests. Unexpected fields
or a different expected binding are refused.

The activation campaign ID must equal the attempt ID, its workspace source
must match, and its reviewed endpoint-binding digest must equal the selected
identity digest. An endpoint hash alone is not that identity binding. The
request also matches the existing closed incapable camera codec: YUY2,
5,472 × 3,648, 9 fps, 10,944-byte stride, no control changes, one to four
frames, and exact per-frame/total raw budgets. The fixture's GRAY8 inputs and
YUY2 files are handled by the caller's separately admitted process and ingest
pipeline, never by this module.

Full stdout is retained alongside the process report, including malformed,
failed or cancelled output. Where a parsed result exists, the exact outer
request/attempt echo, camera-request hash, incapable provenance, closed
scenario, template digest list and native wire must agree with it. Native
receipt fields, counters, sample layout and cleanup observations are compared
to the typed retained receipt; Boolean values cannot impersonate integer
counts. The raw native cleanup record stays in stdout even though the typed
receipt exposes only its derived cleanup Boolean.

The owned process request digest is retained and compared with the child
echo. The complete request-envelope registration, source pins and exact
authorizer admission remain the coordinator/worker's responsibility; this
module does not reconstruct missing command arguments or invent a permit.

## Capture metadata is not a new content-verification run

For capture completeness the caller supplies the exact bounded
`ingest-receipt.json` and sibling `source-contract.json` documents returned
by the actual ingestion pipeline. This module does not open their paths.
Their hashes use the existing ingestion serialization: canonical ASCII JSON
**plus its trailing newline**, which differs deliberately from the outer
evidence serialization.

The inline documents must match the typed request/native receipt, source,
attempt, endpoint, settings epoch and capture receipt. The existing pure
ingest validator recalculates frame-count/layout/row bounds, budget,
QPC-to-nanosecond conversion and the resulting synthetic capture plan. The
plan's own declaration-bound hash and the retained dataset references must
agree. No partial truncation, sample rebasing, inferred cleanup or substituted
request hash is used to make a capture complete.

This verifies **metadata binding only**. The retained
`content_verified` value is the original ingest observation, not a second
observation made by this module. On assessment/reopen, the caller must also
run `verify_windows_capture_ingest` against the exact retained source,
campaign, settings and endpoint, checking all actual dataset bytes and
publication sentinels. Missing inline documents or mismatched references keep
the evidence incomplete even if an ingest receipt says it succeeded.

## Full retention and limits

The complete payload retains:

- Exact activation-request metadata and process report, including primary and
  cleanup errors, return code and full timing/counter fields.
- Stdout and stderr, each as canonical base64, exact byte length and SHA-256.
- The full typed native receipt and capture metadata, with the exact inline
  ingestion provenance documents.
- A bounded caller error, when present.

Stdout is capped at 32 KiB, stderr at 8 KiB, and the entire canonical evidence
at 128 KiB. These are refusal limits, not truncation allowances. JSON is
bounded to depth 24, 16,384 nodes, 512 items per array and 64 fields per object.
At most 512 process cleanup observations are retained; the summary shows the
first 16 plus exact total/omitted counts. Raw wire remains in the private
evidence even when it is not valid JSON. It is not copied into the UI summary.

With the pure focused fixture's short identifiers and no preview, measured
complete evidence sizes are 15,816 / 17,344 / 18,878 / 20,410 bytes for one /
two / three / four full-resolution frame metadata records. These measurements
do not include raw image files; those belong to the separate dataset pipeline.
Longer paths and optional previews can increase metadata size, subject to the
same unchanged 128 KiB limit.

The artifact is a private diagnostic record and may contain assigned paths,
opaque endpoints and exact process output. It does not redact its hash-bound
payload. The caller must use the assigned private evidence/export location
and expose only the bounded summary in ordinary UI views.

## Summary and acceptance meaning

`view()` has schema `rocell.rehearsal_owned_camera_summary.v1`, the complete
seven-field binding, external evidence hash, separate nullable `process`,
`native` and `capture` sections, fixed blockers and meaning text. It omits raw
paths, endpoints, commands, bytes and absolute nanosecond observations.

`RETAINED_COMPLETE_REHEARSAL` requires all of the following independently:

- Successful owned process result, actual created/resumed flags, confirmed
  tree exit, zero return code, and no primary or cleanup error.
- Exact matching synthetic native wire, successful native receipt and its
  separately derived synthetic cleanup observation.
- Matching complete capture metadata/provenance, and no caller error.

Otherwise the result is `RETAINED_INCOMPLETE_REHEARSAL`. Missing or wrong
inner evidence is retained for investigation where structurally bounded;
returning an artifact or successfully checking its binding is not itself a
complete-campaign result. The coordinator must explicitly inspect the derived
status, not infer success from a native status string or capture flag.

The `device_cleanup_proven`, `physical_authority` and `qualified` fields are
always false. OS process cleanup does not prove device cleanup; synthetic
native cleanup does not prove physical camera shutdown; neither proves final
arm power state. Standing physical restrictions remain even when the
rehearsal-completeness blocker list is empty.

## Test scope

[`test_rehearsal_owned_camera_evidence.py`](../tests/unit/test_rehearsal_owned_camera_evidence.py)
uses typed, explicitly synthetic metadata only. It covers nominal and missing
evidence; malformed raw bytes; request/source/identity/wire drift; native and
process cleanup separation; cancellation/timeouts; fixed schema/type/budget
checks; exact raw retention; defensive copies; and forbidden filesystem or
process calls. These tests do not create a child or allocate full image files.
The parent integration lane is responsible for actual incapable-child
execution, full YUY2-file ingestion, M1 publication and dataset reopen tests.

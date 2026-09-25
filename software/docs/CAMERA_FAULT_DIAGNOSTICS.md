# Retained camera fault explanations

`application/camera_fault_diagnostics.py` provides one pure integration call:

```python
diagnostic = camera_fault_diagnostic(retained_camera_evidence)
```

The argument must be an exact `RehearsalOwnedCameraEvidence`. The helper checks
the 128 KiB input bound and repeats existing canonical/semantic validation. It
does not run a process, inspect a device, read frame files, audit M1, change
quarantine or verify that historical evidence matches the current launch. Its
caller remains responsible for trusted permit, source and retained-evidence
hash checks. A hash in this projection is a reference, not authentication.

## Integration and publication

Add the returned dictionary as a sibling `camera_fault_diagnostic` in the
existing camera operation's diagnostic result or cached state. Do not modify
the immutable historical camera evidence or its existing summary schema.
Publish it only through the service's existing full-result retention and
completion-log rules. Invalid projection input raises
`CameraFaultDiagnosticError`, code `INVALID_CAMERA_FAULT_EVIDENCE`, with fixed
public text. Preserve the full private evidence even when projection fails.

The projection does **not** parse a rejected packet again to invent a control
name or observed value. It matches an exact retained local exception signature
or derives a fixed category from the existing evidence verifier's holds and
process status. It never copies raw stdout, stderr, endpoint paths, arbitrary
exception messages, cleanup-resource names or unknown error codes into the UI.

## Exact public schema

The rehearsal service integration publishes the projection at these exact paths:

- `commissioning_rehearsal.camera_fault_diagnostic` in the cached service view;
- `steps[name="retained-incapable-owned-camera-diagnostics"].report.camera_fault_diagnostic`
  in an ordinary returned operation result;
- `CommissioningRehearsalService.retained_camera_diagnostics()["camera_fault_diagnostic"]`
  for the outer Arrival exception/export path after a late failure.

All are null/absent before a capture produces evidence. The public cached read
returns detached data; it never reopens files or invokes a provider. Clearing a
current preview after Stop, source drift or failed stage publication preserves
the historical diagnostic, without restoring camera readiness. A new explicit
camera campaign/probe or attached session retires the previous cache. The full
immutable stage receipt/evidence schemas are unchanged.

If a worker produces valid evidence but coordinator execution raises before a
result returns, the history carries `attempt_result: null` and
`raw_evidence_location: "CAMPAIGN_WORKER_EVIDENCE_DURABLE_RETENTION_UNCONFIRMED"`.
It must not be described as a known M1 seal. Otherwise the original returned
attempt state is retained exactly, including uncertainty/quarantine. No cached
projection can clear either the local service hold or the durable quarantine.

Service-ordering tests use actual pure evidence producers with explicitly
injected workers/coordinators/storage. Export tests use the real diagnostic
exporter in a temporary assigned directory. They test publication/retention,
not received-camera acquisition or M1 qualification.

Schema: `rocell.camera_fault_diagnostic.v1`. All keys are required:

| Field | Contract |
| --- | --- |
| `status` | `FAULT_REPORTED` or `NO_REPORTED_FAULT` |
| `evidence_sha256` | Exact retained artifact SHA-256, 64 lowercase hex characters |
| `reason_category` | One fixed category from the table below |
| `reported_code` | `INVALID_CAMERA_CONTRACT`, `CANCELLED`, `TIMED_OUT`, `UNCLASSIFIED`, or null |
| `basis` | `RETAINED_CALLER_ERROR_EXACT_MATCH`, `RETAINED_PROCESS_STATUS`, `RETAINED_VALIDATION_HOLD`, or `NONE` |
| `reason`, `next_investigation`, `meaning` | Fixed explanatory prose; each at most 512 UTF-8 bytes |
| `retry_this_attempt_allowed`, `automatic_retry_allowed`, `clear_quarantine_allowed` | Always false; this projection grants no recovery authority |
| `physical_authority`, `qualified` | Always false |

The complete projection is below 2 KiB. There are no raw details, input paths,
control values, timestamps, embedded native packets or nested technical reports.

| Category | Basis and investigation |
| --- | --- |
| `PROCESS_CLEANUP_UNCONFIRMED` | Retained process cleanup errors or missing tree-exit confirmation; investigate ownership before any further effect |
| `OPERATION_CANCELLED` / `OPERATION_TIMED_OUT` | Retained process status; inspect original lifetime and cleanup without resume or renewal |
| `CONTROL_READBACK_MISMATCH_REPORTED` | Exact local caller rejection plus retained requested controls; inspect private request/readback/probe data |
| `UNCLASSIFIED_CALLER_ERROR` | Other caller error; private inspection required, no guessed hardware cause |
| `PROCESS_EXECUTION_UNCONFIRMED` | Process success was not confirmed |
| `REQUEST_OR_PROCESS_EVIDENCE_UNAVAILABLE` | Required activation/process evidence missing |
| `NATIVE_EVIDENCE_UNVERIFIED` | Native/request binding or synthetic native completion unverified |
| `CAPTURE_RETENTION_UNVERIFIED` | Capture dataset metadata binding unverified |
| `NONE` | No fault reported in complete rehearsal evidence; still no physical/current-session qualification |

Cleanup uncertainty takes priority, then cancellation/timeout, then caller
rejection, then remaining validation holds. The full retained evidence continues
to contain secondary errors. A single diagnostic category does not erase them.

## Actual retained failure verification

The read-only test checks the original store under wizard launch
`wizard-10fae4dbb9af43e5be77b17bb98247a5`, attempt
`attempt-38f34693a33e48838c193c8733b6076b`.

Its 10,669-byte camera artifact has SHA-256
`fb21b59256ce21aa8fe7d7508a54c03e580b5ffe13c29d0c4e1195f2ce3d749f`.
The retained caller triple is:

```json
{
  "code": "INVALID_CAMERA_CONTRACT",
  "error_type": "CameraWorkerError",
  "message": "INVALID_CAMERA_CONTRACT: requested control did not read back exactly"
}
```

The process reports successful tree exit, but the typed native receipt is absent.
The attempt is `SEALED_UNCERTAIN`, with quarantine latched. The new projection
correctly reports `CONTROL_READBACK_MISMATCH_REPORTED`; it does not promote the
rejected native packet, infer device cleanup, clear quarantine or permit retry.

The optional original-record test checks record/payload hashes, byte count,
attempt/permit joins and unchanged original bytes. This is historical structural
read-back, **not** a full M1 journal audit or current-source requalification. It
skips when the local diagnostic store is absent; portable pure fixtures exercise
the same mapping separately.

```powershell
.venv/Scripts/python.exe -m pytest software/tests/unit/test_camera_fault_diagnostics.py -q
```

Tests cover exact signatures versus prefix/suffix/unknown-message substitution,
unknown/raw-message omission, cleanup precedence, cancellation/deadline status,
missing/bad evidence, defensive views, tampered hashes and pre-decode byte bounds.
Purity tests forbid file reads, subprocess calls and camera operations. No
hardware, native execution, automatic repair or catalog/pin refresh is performed.

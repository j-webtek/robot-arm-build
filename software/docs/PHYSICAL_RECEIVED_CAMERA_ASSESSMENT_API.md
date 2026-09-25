# Received-camera record completeness foundation

2026-09-08. `physical_received_camera.py` is a pure assessment foundation.
It does not collect observations, discover attachments, create a submission,
mutate M1 stages, approve hardware or release native acquisition.

## API

`assess_received_camera_receipt(prerequisites, notebook, *, binding,
inspection=None, notebook_reference=None)` returns `ReceivedCameraAssessment`.

The notebook is the exact `PhysicalIntakeNotebook`, validated against the original
`PhysicalCameraPrerequisites` and its 16 camera-receipt-owned questions. The
optional structured input is the existing `CameraReceiptInspection`, assessed
by the existing `assess_camera_receipt`. A missing inspection remains unknown.
The foundation never parses INT-017 identity prose or INT-024 lens-mount prose
into structured facts. Those originals remain separate for exact-subject review.

`notebook_reference` must be an exact original `EvidenceReference` owned by the
`camera_receipt` stage, with content-addressed package identity and payload hash
and length matching the supplied notebook bytes. It must also appear unchanged
among the structured inspection's bound originals for the record to be complete.
A missing reference yields INCOMPLETE; a source-stage reference is rejected.
This module cannot relabel or reconstruct a stage-3 original from a source-stage
draft. Every inspection reference must likewise have valid original-reference
shape and the existing camera-receipt stage ownership.

The binding is exactly:

- `receipt_id` (`receivedcamera-` plus 32 lowercase hex characters);
- original source, cell, session, header, origin launch and prerequisites hashes;
- current collection launch and operator;
- the original static-contract receipt/assessment/review hash triple;
- the explicit original camera-receipt entry-event hash.

The notebook must match the original source/session/prerequisites/origin and
current collection launch. Structured inspection must match the camera-domain
source binding, original header/session/cell and collection operator. This is a
pure lineage join, not evidence that caller-supplied expected hashes are trusted.

`verify_received_camera_assessment(value, *, prerequisites, expected_binding,
expected_notebook_sha256, expected_inspection_sha256,
expected_notebook_reference, expected_assessment_sha256)` accepts exact bytes or
the typed assessment. It reparses the original notebook and inspection and
recomputes every derived result. The expected notebook reference may be null
only for the correspondingly incomplete record.

The immutable result exposes `.payload`, `.sha256`, `.to_dict()` and
`.safe_summary()`. The result constructor also requires original prerequisites,
as does the existing notebook constructor. Returned mappings are detached.
Payloads are canonical ASCII JSON with no floats, duplicate fields or nonfinite
numbers. Full payloads are limited to 128 KiB and compact summaries to 24 KiB.

## Deterministic outcome and limits

`RECEIPT_COMPLETE` requires all 16 observations to be OBSERVED, the exact
camera-stage notebook reference, the structured B0477/16 mm inspection to be
diagnostically ready, and exact decimal thickness values satisfying
`17.5 <= minimum <= maximum <= 18.5` mm. Every missing observation or failed
check yields `RECEIPT_INCOMPLETE`. UNKNOWN is never promoted to observed.

The original notebook owns numeric representation and positivity checks; no
float rounding, unit coercion or nominal substitution is introduced. Flatness
must be recorded, including a legitimate nonnegative zero, but its acceptance
is always `DEFERRED_LIMIT` pending the later target accuracy budget. No assumption
that installed clamp preload was actually used is made from a numeric value.

No tolerances are invented for nominal board size, camera enclosure, lens depth,
mass, thread, C-versus-CS mount identity or bench suitability. Very large but
well-formed positive measurements can therefore make a record complete; they
do not make its geometry acceptable. Missing acceptance contracts remain explicit
residuals and cannot be inferred from `RECEIPT_COMPLETE`.

The assessor verifies only the supplied notebook bytes against their reference.
It cannot read or authenticate images, purchase records or other referenced
packages. The future stage owner must resolve those originals under its actual
leases before treating the complete record as reviewed. The five physical
authority, hardware qualification, stage-PASS, device-I/O and attachment-byte
verification flags remain false. No USB identity, optical, support, load,
collision or native-release decision is made.

Tests use actual original question parsing plus explicitly modeled observations
and package metadata. They exercise exact decimal endpoints and ordering, every
UNKNOWN row, structured identity/condition faults, stage/domain/reference drift,
tampering, no-I/O verification, absent acceptance thresholds and byte bounds.
No received hardware observation or native process is executed by these tests.

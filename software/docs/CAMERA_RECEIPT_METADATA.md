# Native camera metadata versus verified frame files

`providers/windows/camera_worker_client.py` separates native receipt parsing
from file inspection. Neither half opens a camera or authorizes a capture.
Physical activation remains independently held in the owned runner.

## Pure retained parsing

```python
metadata = WindowsCameraWorkerClient._parse_receipt_metadata(
    raw_native_receipt, "capture", exact_binding, requested_mode,
    (exact_budget, assigned_output_directory), requested_controls,
)
```

This returns `NativeCameraReceiptMetadata`, with `NativeFrameMetadata` frame
rows. It validates the existing native schema, exact endpoint, requested and
observed format, control readback, activation/shutdown counts, cleanup fields,
frame names, sample geometry, timing fields, counts and byte budgets. It does
not stat, enumerate or open the assigned output directory. Failed receipts and
unconfirmed native cleanup remain failed/uncertain observations.

The native wire does not contain frame hashes. `NativeFrameMetadata` therefore
has no `sha256` field: no placeholder hash, guessed file content or synthetic
sample is introduced during retained verification. Native cleanup is a reported
camera/COM lifecycle fact; process cleanup is a separate owned-process fact.
Neither establishes qualified device ownership cessation or final power.

## Explicit artifact validation

```python
receipt = validate_capture_artifacts(
    raw_native_receipt, request=original_typed_activation_request,
)
```

This explicit filesystem action rechecks exact typed request/nested inputs and
reparses the original raw native receipt. A caller cannot supply a hand-built
metadata object instead. It reads only the exact sequential frame files in the
request's assigned directory, validates regular-file ancestry and reported
length, hashes bounded bytes, and rejects missing/extra data. A successful
capture must have no unreported files. The returned `NativeCameraReceipt`
contains real parent-computed `NativeFrameArtifact.sha256` values.

The existing `_parse_receipt` API still returns this same hash-bearing type and
performs the same file checks; inventory/probe callers retain their existing
behavior. This refactoring does not silently change their wire schemas.

The parent still owns directory containment and the original request/permit.
These read-only hashes are not an immutable dataset, permission to connect,
crash-durability proof or a hostile-writer isolation guarantee. Subsequent
`ingest_windows_capture` rechecks sample bytes and publishes diagnostic evidence.
Received-camera data must use its `PHYSICAL_UNVERIFIED` domain, never
`INCAPABLE_NATIVE_FIXTURE`. Retained content can later be rechecked by
`verify_windows_capture_ingest` without replaying capture or needing the original
native input directory. Process/native records alone cannot replace that
content verification.

## Tests

`test_camera_receipt_metadata.py` forbids process/DLL dispatch, verifies pure
parsing with filesystem methods forbidden, rejects malformed/forged receipt
metadata, and checks hashes against fixed small YUY2 files under `tmp_path`.
It covers changed file lengths, missing/unreported files, request drift and the
legacy parser return-value join. These are physical-shaped wire fixtures, not
received-camera observations or hardware qualification.

## Owned capture evidence

`owned_native_camera_evidence.py` now admits the exact
`PreparedOwnedNativeCapture` type through a distinct retained schema,
`rocell.owned_native_camera_capture_run_evidence.v1`. Probe and admission-only
fixture records keep their existing v1 schema and valid byte representation.
A capture record cannot carry an admission-only fixture preparation or silently
reuse the probe schema. Its fixed runtime, original request, capture settings,
assigned output path, source, permit, actual-PID READY and exact RELEASE are
retained and cross-checked together.

The existing pure API is retained:

```python
artifact = retain_owned_native_camera_run(
    probe=exact_capture_preparation,  # Compatibility keyword; exact typed union.
    fixture=None,
    # Original bounded owner observations, raw wires and result fields follow.
    **observed_run,
)
verified = verify_owned_native_camera_run_evidence(
    artifact,
    expected_preparation_sha256=trusted_original_preparation_hash,
    expected_evidence_sha256=trusted_retained_evidence_hash,
)
```

`verified.native_receipt` returns capture metadata, not a hash-bearing frame
receipt; it is `None` when no valid native result was retained. Exact bounded
stdout/stderr and the full raw result remain private evidence. Malformed or
partial output is retained without inventing a native receipt or exact count of
unobserved omitted bytes. The full aggregate remains capped at 128 KiB; oversize
is a failure, not a reason to trim evidence into a successful record.

The capture-only summary schema is
`rocell.owned_native_camera_capture_run_summary.v1`. It keeps the existing
independent native/process cleanup fields and adds `operation: "capture"`,
nullable `capture_metadata` (`status`, `frames_reported`,
`total_frame_bytes_reported`), `frame_content_verified: false` and
`device_cleanup_proven: false`. A valid native FAILED receipt cannot be recast
as successful evidence by removing its process error/hold. A clean process exit
does not turn failed native cleanup into successful cleanup.

This summary is not a file-validation or dataset receipt. An explicit later
`validate_capture_artifacts` call must take the original raw native receipt and
exact `camera_plan.request`; it neither mutates nor upgrades the stored owned
record. Any later dataset and preview must retain the separate
`PHYSICAL_UNVERIFIED` domain and content-verification evidence.

`test_owned_native_camera_capture_evidence.py` covers raw/evidence/preparation
hash joins, endpoint/permit/source/domain drift, preservation of failures,
metadata-only reconstruction with file methods forbidden, the pure parent
handshake, and the real production runner's default pre-owner physical hold.
Its complete native/process records are explicitly modeled test inputs; only
the small explicit artifact test reads fixed temporary sample bytes.

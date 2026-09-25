# Reopening retained owned-camera rehearsal evidence

The owned-process camera path extends the existing camera stage receipt; it
does not replace the legacy in-process rehearsal path or authorize a physical
camera. The two camera stages remain `camera_mode_controls` and
`camera_frame_freshness`. All images in this path are generated from explicitly
synthetic source templates by the incapable child process.

## Integration API and trust boundary

```python
# Inside the original session's currently owned CELL/SESSION transaction:
records = tx._audit_records()
evidence = _read_evidence(session_directory, snapshot, source_sha256, catalog_sha256)
artifact = _verify_owned_camera_campaign(
    stage_document, source_sha256, records, evidence=evidence
)

# Then recheck the actual capture dataset with the existing bridge verifier.
# This step reads retained files; it never captures another frame.
verify_windows_capture_ingest(
    stage_document["capture_dataset"],
    expected_source_sha256=source_sha256,
    expected_settings_epoch=stage_document["plan"].get(
        "effective_settings_epoch", stage_document["plan"]["settings_epoch"]
    ),
    expected_campaign_id=stage_document["attempt_result"]["attempt_id"],
    expected_endpoint_sha256=expected_fixed_endpoint_sha256,
)
```

The reusable join is in
[`commissioning_rehearsal_reopen.py`](../src/rocell/application/commissioning_rehearsal_reopen.py).
Its `records` parameter is **not** a browser-supplied document or an alternative
ledger reader. The caller must first obtain the verified immutable records
from the actual M1 transaction under its original ordered leases. That audit
establishes store, attempt-ledger and record-publication integrity; the helper
then checks their exact owned-camera semantic join.

The helper returns the immutable artifact from
[`rehearsal_owned_camera_evidence.py`](../src/rocell/application/rehearsal_owned_camera_evidence.py).
It neither instantiates `OwnedBinaryCameraWorker` nor starts any worker,
process, device lookup, capture or preview publication. Its only independent
source read is the fixed incapable child script through the existing bounded
regular-file reader, capped at 1 MiB, to compare the current script digest with
the retained registration. Dataset bytes are verified separately by the
caller; a valid inline evidence document is not a fresh content observation.

## Exact retained join

The owned path requires `rocell.rehearsal_camera_campaign.v2`, the exact
`OWNED_INCAPABLE_CAMERA_PROCESS` plan, and both extra fields:
`retained_campaign_sha256` and `camera_process`. Unknown fields, omitted owned
fields, a v1 owned receipt or a backend marker inconsistent with the audited
registration are rejected. Removing the backend marker cannot silently select
the less demanding legacy path.

For the selected attempt there must be exactly one reservation, known result
and retained campaign record, plus both `EFFECT_OBSERVED` and
`CLEANUP_CONFIRMED` lifecycle receipts. Their complete receipts and permit
digests must agree. The permit must match the fixed incapable registration,
source domain, session, selected synthetic camera, stage and operation plan.
The admission must have no unresolved attempt, quarantine or open blocker.

Exactly one retained blob is accepted, with schema
`rocell.rehearsal_owned_camera_evidence.v1` and role
`owned-camera-campaign`. Its canonical base64, byte count and SHA-256 must
match the immutable M1 record. The known receipt's evidence tuple must contain
only that complete blob digest, and its output byte count must equal the blob
size. Substituting only dataset or envelope digests is not sufficient.

The full evidence verifier binds session, attempt, source, permit, operation,
selected identity and settings epoch. Its derived summary must be
`RETAINED_COMPLETE_REHEARSAL` and equal the exact saved `camera_process`
summary. Its full capture receipt must equal the stage's `capture_dataset`.
The known counters are one open, the exact requested frame/read count, the
exact requested control-write count (zero in the legacy path) and one close.
The synthetic worker's final power remains `UNKNOWN`;
serial or arm power is not observed by a camera process.

## Plan and resource limits

The closed plan retains one to four YUY2 frames at 5,472 × 3,648, 9 fps and
10,944-byte stride. Reopening checks all fixed plan fields, not only its hash:
20,000 ms native duration, 25,000 ms owned-process timeout, 2,000 ms cleanup,
32 KiB stdout and 8 KiB stderr. The registered bounded campaign remains
60,000 ms with the existing 128 KiB complete evidence limit.

The binary artifact budget is
`(2 × 39,923,712 + 4,990,464) × frame_count + 128 MiB`.
The extra 4,990,464 bytes per frame accounts for the source-derived GRAY8
template. Dataset and ingestion-envelope locations must still be inside the
original assigned fixture/session path, and existing frame-content,
manifest, source-contract and incomplete-publication checks are unchanged.

## Failure and replay semantics

A missing or changed blob, lifecycle receipt, source pin, permit, saved summary
or capture reference holds reconstruction. No repair, implicit restart,
approval replay or fresh acquisition is attempted. File-content verification
runs only after the owned record join succeeds. Failed or cancelled campaigns
remain useful diagnostic evidence but cannot satisfy this known-camera
reconstruction path.

`_verify_camera_receipt(..., records=audited_records, evidence=stage_evidence)` performs this join for
owned campaigns before its existing capture verification. Legacy in-process
receipts preserve their existing schema, budget and file-verification route.
The standing physical flags remain false: process cleanup and synthetic
native cleanup are distinct from received-device cleanup, qualification,
connection, calibration and physical power state.

## Verification scope

[`test_owned_camera_reopen.py`](../tests/unit/test_owned_camera_reopen.py)
contains 42 focused tests for both camera stages, missing/duplicate records,
plan and source drift, byte/hash/role tampering, exact result counts and
bindings, backend downgrade, verification ordering and the legacy path.
These tests use typed synthetic metadata and explicitly mocked already-audited
records/file-verifier seams. They do not claim to test M1 publication, launch
a process, allocate image files, inspect devices or prove physical behavior.
The separate integration lane is responsible for the real incapable child,
actual generated-file ingestion, qualified M1 retention and original-store
reopen.

## Capability-probe and configured-capture extension

The same original M1 transaction supplies immutable stage evidence and audited
records to two additional reusable helpers:

```python
probe = _verify_camera_probe_receipt(
    probe_document, source_sha256, records, directory=session_directory
)
probe_document, probe, configuration_document, configuration = (
    _verify_camera_configuration_context(
        evidence, records, source_sha256, session_id,
        directory=session_directory,
    )
)
```

The context returns four `None` values only when no probe/configuration
artifacts or probe reservation exist. A complete probe may have no staged
configuration yet. The original reviewed synthetic camera, source, session,
opening event, operator and exact probe reservation/result/blob are checked;
there is no newly selected endpoint or worker construction during restore.

The probe auxiliary schema is `rocell.rehearsal_camera_probe_receipt.v1` and
its single retained M1 blob is `rocell.rehearsal_camera_probe_evidence.v1`, role
`owned-camera-probe`. The exact registered probe budget is 60,000 ms and
128 KiB retained evidence, with one open/close and zero reads, writes or
frames. Its fixed native/process/cleanup durations are 5,000/10,000/2,000 ms.
The retained owned payload must name the exact attempt-specific directory
`camera-probe-<attempt-id>`; when supplied, `directory` binds its parent to the
original session. Full reconstruction additionally verifies that this is the
only expected probe directory and that it is an ordinary, empty directory.

The configuration auxiliary schema is
`rocell.rehearsal_camera_configuration_receipt.v1`. It follows the original
stage opening, brightness settings and probe. Its full immutable configuration
is restored against the verified probe's capabilities; electronic and
synthetic epochs must join to the exact effective dataset epoch. Duplicate,
orphan, reordered or altered auxiliary evidence holds rather than repairing
the session.

Configured capture plans add exactly `electronic_configuration`,
`probe_evidence_sha256` and `effective_settings_epoch`. Their stage receipts
add `camera_readback`. The audited operation-plan hash, control-write budget,
full retained native/process evidence, dataset epoch and recomputed readback
must agree. Empty requested controls preserve the original v1 child wire;
nonempty controls use the closed v2 fixture wire. Both still require the
configuration/probe dependency when the session chose that path.

A verified complete probe can reopen with stage 5 still waiting and no camera
capture receipt. The exception permits only the exact known auxiliary probe;
a missing capture receipt after a separate capture reservation still holds.
Once any probe reservation exists, an unconfigured or in-process capture is
not accepted as fallback. Restoration never reruns the probe, reapplies a
setting, captures frames or republishes a preview.

[`test_camera_configuration_reopen.py`](../tests/unit/test_camera_configuration_reopen.py)
adds 30 pure tests, including probe-only/configured partial restoration,
missing or duplicate audited records, auxiliary ordering/source/cwd checks,
downgrade refusal and complete configured-capture joins for both empty controls
and manual-plus-auto controls. These use no real M1 or process execution.
The [pure evidence API](CAMERA_CONFIGURATION_EVIDENCE.md) describes the exact
caps and distinction between staged electronic intent and dataset provenance.

# Native capture → diagnostic dataset → actual-pixel preview

The [bridge](../src/rocell/application/windows_camera_capture_ingest.py) connects
the Windows native camera receipt/files to the binary dataset store. It is a
DEV-007/008 integration step, not camera activation or hardware commissioning.
Its constructor/planning path performs no filesystem or device I/O.

## Exact call sequence

Before capture, retain the server-owned `CameraActivationRequest` and prepare:

```python
plan = prepare_windows_camera_ingest(
    request,
    capture_directory=assigned_native_directory,
    dataset_root=assigned_dataset_root,
    source_sha256=request.source_sha256,
    settings_epoch=reviewed_settings_epoch,
    domain="PHYSICAL_UNVERIFIED",  # Or explicit INCAPABLE_NATIVE_FIXTURE.
    frames=(
        FramePlan(
            "frame-000000",
            preview=PreviewTransform(0, 0, 5472, 3648, 912, 608),
        ),
    ),
    retention_timeout_ms=120_000,
)
```

Paths are assigned internal `Path` objects, not arbitrary browser device paths.
They may be absent during planning; both must exist as separate safe local
directories when ingestion is explicitly invoked. The tuple must match the
request's frame count. The final frame alone may request a preview. Train/holdout
partitions can be assigned before capture using the existing `FramePlan` rules.

The coordinator/native worker remains responsible for actual one-use authority,
capture, and cleanup. After receiving a typed, validated successful native receipt:

```python
result = ingest_windows_capture(
    request, native_receipt, plan=plan, cancelled=cancellation.is_set
)
ui_png = result.latest_preview.png_bytes if result.latest_preview else None
safe_json_receipt = result.to_dict()  # Contains no binary/base64 pixel payload.
```

`to_dict()["dataset"]["path"]` and `["manifest_sha256"]` bind the inner dataset.
The result also carries the exact final envelope path/hash, source-contract hash,
content-verification result, and latest preview transform/native/PNG hashes.
There is no authorizer callback, helper execution, camera selection by index,
camera open, control write, serial action, or automatic retry in this module.

## Independent checks and retained evidence

Ingestion requires the current, separately pinned `rocell.windows_camera.v1`
contract and expected native dataclass fields. Its pure plan pins the full
activation-request digest, assigned input/output directories, workspace source,
settings epoch, explicit provenance domain, partitions/transforms, artifact quotas,
and retention deadline. Request, endpoint, count, format, or settings/readback drift
cannot silently produce a normal dataset.

The bridge checks successful cleanup, exactly one source activation/open/shutdown,
requested electronic-control readback, selected-endpoint presence, enumerated
native mode, finite frame/count/byte budgets, exact file membership, single-link
regular files, lengths, SHA-256, sequence, QPC frequency/order and explicit stride.
Windows input handles deny write/delete sharing during hashing, rendering and
publication. Input handles and metadata are checked/closed before the final
bridge completion marker. Linux has bounded checks but not this Windows sharing
isolation; no hostile-administrator isolation is claimed on either platform.

The receipt's endpoint digest is retained as an **endpoint reference**, not an
invented serial, persistent-unit guarantee, VID/PID, container GUID or USB speed.
Original native metadata is preserved verbatim as typed JSON in the source contract.

Each call creates a fresh tree; existing files/directories are never overwritten:

```text
assigned-dataset-root/
  ingest-<uuid>/
    source-contract.json       # Request, receipt, hashes, exact plan; written first.
    capture-<uuid>/            # Existing dataset format, unchanged.
      capture-plan.json
      chunks/<sha256>.bin
      manifest.json           # Inner dataset commit; content verification follows.
    ingest-receipt.json        # Outer completion, published last without overwrite.
```

Final JSON is staged and flushed, then copied by a second exclusive final-file
write/flush. A final cancellation check precedes removal of the pending sentinel.
This small JSON copy works with the Windows directory rename guard, which also
denies hardlink creation. Both verifiers reject pending or unexpected entries,
including complete-looking final bytes after a flush/removal failure. Pending
files are retained on failure. A cancellation can leave a committed **inner diagnostic
dataset** without a completed bridge envelope. That is not successful ingestion,
permission to replay, or authority to repair/remove retained evidence. No cleanup
routine erases partial captures, datasets, or prior results.

## Preview and timing semantics

The shared `render_yuy2_preview(read_row, mode=..., transform=..., cancelled=...)`
utility consumes actual active YUY2 rows from its accessor. The bridge supplies
rows using the observed row-zero offset and signed stride, correctly excluding
padding for display while retaining every native byte in the dataset. The renderer
supports exact crop, clockwise 0/90/180/270-degree rotation and nearest-pixel-center
downsampling without upscaling. It processes bounded source rows and one output RGB
image, never joins a full native frame. Output is a bounded PNG, not a substitute
schematic or arbitrary supplied image.

Native v1 has no observed color matrix/range. Consequently the preview explicitly
declares `BT601_LIMITED_DIAGNOSTIC_POLICY_NOT_OBSERVED`; it does not assert camera
colorimetry or calibration. Byte ordering and this chosen conversion follow
[Microsoft's YUY2 format/conversion documentation](https://learn.microsoft.com/en-us/windows/win32/medfound/recommended-8-bit-yuv-formats-for-video-rendering).
The dataset's generic verifier still labels preview association as declared,
because that verifier does not independently recompute pixels. This bridge does
derive them; its source contract/envelope records the policy and hashes.

Media time is converted exactly from 100 ns units to ns, never relabeled as sensor
exposure or UTC. QPC ticks/frequency are preserved; integer floor/ceil conversion
produces a nanosecond rounding bracket around the **single observed host QPC
point**, not a fabricated acquisition interval or wall-clock timestamp. Fixture
timing is explicitly labeled synthetic. Negative/overflow media times, changing
QPC frequency, discontinuity, noncanonical row origins, varying per-frame layouts,
or sample lengths other than `abs(stride) * height` are rejected by this first
adapter. It never trims, pads, reverses, rebases, or invents missing native data.

## Resource and acceptance boundaries

### Reverification before assessment, review, or explicit reopen

Use the complete receipt retained by the trusted commissioning ledger, not
browser-authored paths or hashes:

```python
verification = verify_windows_capture_ingest(
    retained_capture_receipt,  # NativeCaptureIngestReceipt.to_dict(), or decoded JSON
    expected_source_sha256=current_source_digest,
    expected_settings_epoch=reviewed_settings_epoch,
    expected_campaign_id=known_attempt_id,
    expected_endpoint_sha256=reviewed_exact_endpoint_digest,
)
```

The call returns `DatasetVerification` only after checking the bounded canonical
ingest envelope and sibling source contract against their externally retained
hashes; their exact v1 schemas, zero-authority declarations, native request and
receipt references; and the dataset manifest, capture-plan hash, every retained
sample and current source/settings/campaign/endpoint binding. The envelope must
be `ingest-<uuid>/ingest-receipt.json`, with its dataset a direct `capture-<uuid>`
child and its source contract the sibling `source-contract.json`. The caller
must additionally enforce containment within the selected original session
store. The verifier does not search for substitute evidence or infer identity.

Each metadata document is at most 256 KiB; decoding also has nesting/node/text
bounds. Existing no-link local-path checks and Windows read locks hold the
provenance files through content verification. Original provider-spool files are
not needed or reread, and no file is repaired, replaced, deleted, or regenerated.
Content verification is synchronous and bounded by the dataset reader's quotas,
not a forcibly interruptible operating-system I/O deadline. It is not isolation
against an administrator or native power-loss qualification. A returned record
remains synthetic or physical-unverified and does not accept freshness, optics,
received-unit identity, or physical release.

- Native artifacts remain within the request's frame/byte budgets. Separate
  dataset quotas include the derived preview; default ceilings are 32 frames,
  64 MiB/frame, 2 GiB total and 4,096 references, with <=1 MiB streamed blocks.
- At most one latest preview is held, <=2048×2048 output pixels and <=4 MiB PNG.
- Bridge JSON is <=256 KiB per document. Coordinator `maximum_output_bytes`
  describes its receipt JSON, **not** permission for unlimited native artifacts.
- Retention has explicit cancellation/deadline checks around block/row/publication
  work. A blocked operating-system file call or the existing content verifier
  cannot be forcibly interrupted by this synchronous adapter; a late result must
  not be accepted beyond the caller's overall campaign deadline.
- All outputs remain `SYNTHETIC` or `PHYSICAL_UNVERIFIED`, `physical_authority=false`,
  `m1_qualified=false`, and `received_hardware_accepted=false`. Byte hashes and a
  known diagnostic seal do not provide M1 native power-loss qualification,
  trustworthy received-unit identity, freshness acceptance or physical release.

## Hardware-free verification

Run from the repository root, checking each exit code:

```powershell
.\.venv\Scripts\python.exe -m pytest software/tests/unit/test_windows_camera_capture_ingest.py -q
.\.venv\Scripts\python.exe -m pytest software/tests/unit/test_camera_rehearsal_campaign.py -q
```

The bridge suite uses small regular-file fixtures, including actual Windows
sharing checks; no helper/camera/serial/authorizer is invoked. It covers byte
roundtrip, padded top-down/bottom-up samples, crop/rotation/downsampling pixels,
request/receipt/mode/identity drift, missing/corrupt/extra/linked files, strict
timing/provenance, quotas, cancellation, flush failure and nonoverwrite. The
separate synthetic-worker suite exercises a B0477-sized 39,923,712-byte frame
through this same ingestion/preview path without camera access. This is software
evidence only; received hardware and native driver behavior remain unverified.

# Native camera capture dataset API

This standalone DEV-007 component stores bounded caller-supplied bytes. It does
not open a camera, write an M1 ledger, advance onboarding stages, qualify
hardware, or grant physical authority. Coordinator-owned acquisition and M3
evidence integration remain separate work.

## Main entry points

`rocell.application.camera_capture_dataset` provides:

- `CameraCaptureDatasetStore(absolute_existing_root, quotas=DatasetQuotas())`:
  construction and `status()` perform no filesystem/device I/O or writes.
- `publish(plan, frames, cancelled=callback) -> DatasetReceipt`: explicit,
  synchronous publication into a fresh `capture-<uuid>` child. The caller must
  assign an existing local parent and run streaming producers inside its own
  bounded campaign/worker. A blocked producer cannot be interrupted by this
  synchronous writer alone.
- `verify_capture_dataset(path, tier="content", expected_manifest_sha256=None,
  expected_binding=None) -> DatasetVerification`: structural verification and,
  by default, streamed payload verification. A separately retained receipt hash
  and expected binding should be supplied when available.
- `iter_native_frame(path, frame_id)`: verifies the dataset and yields bounded
  native byte blocks. Consume the iterator fully; it does not return a giant
  joined frame or silently strip row padding.

The `metadata` verification tier checks commitment, strict schemas, file
inventory, types, linkage and lengths but **does not validate payload contents**.
Its result has `content_verified=False`. Neither tier authenticates hardware.

## Typed capture inputs

`CapturePlan` binds a `CaptureBinding`, `SampleLayout` and immutable tuple of
`FramePlan` entries. The binding includes source SHA-256, campaign ID, settings
epoch, explicit device backend/persistent identity, and separate requested and
observed `VideoMode` values. Unknown observed VID/PID/serial values stay `None`;
the writer never guesses them. Supported provenance is `SYNTHETIC` or
`PHYSICAL_UNVERIFIED`, with an explicit corresponding backend.

This first version accepts even-width YUY2. `SampleLayout` records positive
stride and `TOP_DOWN`/`BOTTOM_UP` row order; each native sample must contain
exactly `stride_bytes × observed_height` bytes, including padding. Mode
mismatches remain visible through `requested_mode_matches=False`; storing them
does not satisfy native calibration requirements.

Each `NativeFrameInput` supplies its planned ID, `SampleTiming`, an iterable of
nonempty `bytes` blocks at most 1 MiB, and an optional `PreviewInput`.
`SampleTiming` distinguishes host sequence/arrival brackets from optional media
sample time. Host counters are not sensor sequence numbers, media timestamps
are not exposure timestamps, and changed hashes do not establish freshness.

Frame IDs are unique and ordered before data writing. Partitions are
`DIAGNOSTIC`, `CALIBRATION_TRAIN`, or `CALIBRATION_HOLDOUT`; a calibration plan
must contain both train and holdout entries. A frame cannot be assigned to both.
The plan is written and hashed before the first stream is consumed.

Minimal synthetic publication (the caller supplies an existing `assigned_root`
and its actual `source_sha256`; this does not inspect or connect hardware):

```python
from rocell.application.camera_capture_dataset import (
    CameraCaptureDatasetStore, CaptureBinding, CapturePlan, DeviceIdentity,
    FramePlan, NativeFrameInput, SampleLayout, SampleTiming, VideoMode,
    verify_capture_dataset,
)

mode = VideoMode(4, 3, 9, 1)
binding = CaptureBinding("SYNTHETIC", source_sha256, "campaign-1", "settings-1",
                         DeviceIdentity("SYNTHETIC", "fixture-1"), mode, mode)
plan = CapturePlan(binding, SampleLayout(8), (FramePlan("frame-0"),))
sample = NativeFrameInput("frame-0", SampleTiming(0, 0, 1), [bytes(range(24))])
receipt = CameraCaptureDatasetStore(assigned_root).publish(plan, [sample])
verified = verify_capture_dataset(receipt.path,
    expected_manifest_sha256=receipt.manifest_sha256, expected_binding=binding)
assert verified.content_verified and not verified.physical_authority
```

Source and identity values are caller declarations, not independently measured
by the writer. The coordinator must retain the receipt and establish those
bindings before any future evidence integration.

Preview plans explicitly declare crop, right-angle rotation, aspect-preserving
downscale, PNG/JPEG encoding, output size, and byte ceiling. Upscaling and crops
outside the observed native image are rejected. Actual preview headers and
decoding must match that declaration, and `PreviewInput.native_sha256` must
match the stored native sample digest. The writer verifies this **declared
association**, not that the preview pixels mathematically result from the
native pixels; the manifest states that limitation.

## Storage and failure behavior

Default hard ceilings are 32 frames, 64 MiB per padded native frame, 2 GiB total
logical data, 4 MiB per preview, 1 MiB per chunk and 4096 chunk references.
Smaller caller quotas are supported. Disk preflight reserves the planned worst
case plus metadata and a configurable reserve. Disk exhaustion can still occur
later; it fails publication without automatic retry.

`5472 × 3648 × 2 = 39,923,712` native bytes fit without the legacy 32 MiB item
cap. Thirty-two such frames require 1,277,558,784 logical bytes before previews
or padding. Repeated content-addressed chunks may be shared, but logical byte
limits count every referenced sample, not only physical disk use.

Layout:

```text
capture-<uuid>/
  capture-plan.json
  chunks/<sha256>.bin
  manifest.json
```

The writer exclusively creates files and never overwrites an existing dataset.
The final manifest is staged/flushed, copied with an exclusive final-file
write/flush, checked for cancellation, then its pending sentinel removed. The
verifier rejects that sentinel even when final bytes look complete. The second
small JSON write avoids hardlink operations denied by the Windows directory
rename guard. The manifest has no self-hash cycle: the returned receipt carries
its digest externally. A canceled stream, wrong count/length, failed staged
manifest, extra file, missing chunk, link/reparse/hard-linked file, duplicate
registry entry or tampering prevents successful verification. Partial trees
remain for inspection; this API does not delete, repair or resume them.

Cancellation is checked during streaming, after the final frame and immediately
before the manifest publication decision. Cancellation after commitment does
not retroactively erase immutable data. Windows directory ancestry is pinned
during publication/verification using the existing diagnostic directory guard.
This is not hostile-concurrent-writer isolation, off-machine authentication or
qualified power-loss durability; M1/M3 review and native hardware acceptance are
still required before any operational-evidence use.

## Verification commands

```powershell
.\.venv\Scripts\python.exe -m pytest software/tests/unit/test_camera_capture_dataset.py -m "not slow" -q
.\.venv\Scripts\python.exe -m pytest software/tests/unit/test_camera_capture_dataset.py -m slow -q
```

Small isolated fixtures cover the complete structure and corruption/failure
paths. The explicit native-size test streams and verifies a real-sized B0477
sample with bounded allocations; it is still synthetic, not a camera capture.

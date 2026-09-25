# Binary camera rehearsal: implementation and operator handoff

This increment connects the first six-stage guided rehearsal to retained native-
sized image fixtures. It does **not** connect a physical camera, qualify the lens,
complete commissioning, or change the hardware freeze.

## Operator workflow

1. Launch `start-rocell-wizard.ps1` in its default rehearsal mode.
2. Initialize the separate durable rehearsal, collect/assess/review stages 1–4,
   and select the synthetic B0477 identity. Reviewer ID must differ from operator.
3. Open stage five, then **Prepare synthetic camera settings**. The brightness
   offset is bounded to -64…64 and explicitly is not a UVC exposure/gain setting.
   The settings document and its SHA-256 epoch are retained before the campaign.
4. Preview and explicitly run **Run coordinated synthetic camera campaign**.
   Start with one frame. The maximum is four, with no indefinite stream/retry.
5. Review the capture metadata and the image on **Camera**. That image is derived
   from the retained YUY2 sample, not an independent schematic redraw. Then assess
   and review the exact evidence. Both the dataset contents and the saved native
   provenance/envelope hashes are verified again at assessment and review.
6. Stage six repeats a finite capture using the same reviewed settings. A setting
   cannot silently change while an older assessment is pending. This increment
   does not provide a later-stage settings-change/invalidation workflow.
7. Export diagnostics to the assigned workspace export folder. Preserve the
   original rehearsal store too: the bounded diagnostic export is not a binary
   dataset backup and intentionally does not copy hundreds of megabytes.

Stages 7–15 and every physical stage remain pending. A passing synthetic
freshness stage tests the workflow, not real sensor timing or received optics.

## Data path and ownership

```text
exact UI ticket + retained settings epoch
  -> CommissioningRehearsalService: due-stage checks and M1 transactions
  -> CellCommissioningCoordinator: leases, intent, arming, receipt, cleanup
  -> SyntheticBinaryCameraWorker: bounded source-derived YUY2 fixture files
  -> Windows capture ingestion: identity/mode/sample/budget validation
  -> CameraCaptureDatasetStore: chunked plan-first, manifest-last retention
  -> content verification + actual-byte-derived PNG
  -> known attempt result -> separate assessment -> exact operator review
```

`camera_rehearsal_campaign.py` has no device or native-executable invocation.
It reuses the existing source-bound static-vision placemat renderer: the nominal
2736×1824 raster is expanded twofold in each direction to 5472×3648 YUY2. The
settings transform changes synthetic luma. Neutral chroma and the bridge's
explicit diagnostic color policy are not observed sensor colorimetry.

Upsampling exercises full-size byte counts, stride, streaming, retained-file
integrity and preview transforms. It does **not** create 20 MP optical detail,
measure focus, or validate board/keyboard/phone installation dimensions.

The native ingestion plan is constructed before fixture creation and pins exact
source, assigned directories, endpoint binding, mode, settings epoch and frame
partitions. The native protocol fixture and resulting dataset both retain the
`INCAPABLE_NATIVE_FIXTURE` / `SYNTHETIC` domain. The physical bridge uses a
different explicit `PHYSICAL_UNVERIFIED` domain and does not activate a device.

## Resource and failure limits

- One raw frame is 39,923,712 bytes; the displayed PNG is 912×608.
- One to four frames, a 60-second campaign deadline, bounded preview size and
  chunked hashing/publication. The development image dependencies must already
  be installed; the wizard never installs them automatically.
- Reserve raw samples plus retained copies plus 128 MiB free-space margin.
  Core `maximum_output_bytes` bounds the JSON worker receipt; the separately
  operation-bound binary artifact budget bounds native/retained bytes. Do not
  reinterpret a 4 KiB receipt budget as permission for unbounded frame storage.
- Cancellation is checked while generating rows and ingesting chunks. Partial
  artifacts remain for diagnosis. Post-arming ambiguity can quarantine the
  separate rehearsal; there is no automatic replay, delete or repair.
- Identity-mismatch and cleanup-uncertain scenarios report deliberate simulated
  contract faults and do not manufacture a successful retained dataset.
- Opening a new stage/campaign or encountering a failed commissioning operation
  clears the displayed preview. Retained historical files/results are not deleted
  and cannot masquerade as an image from the failed current attempt.

The dataset/ingestion envelope is a verified diagnostic package, **not M1-
qualified native frame publication or power-loss qualification**. The M1 ledger
retains the worker's dataset/envelope hashes before known sealing. Neither those
hashes nor synthetic PASS states release physical camera or arm activation.

## Developer checks

```powershell
.\.venv\Scripts\python.exe -m pytest software/tests/unit/test_camera_rehearsal_campaign.py -q
.\.venv\Scripts\python.exe -m pytest software/tests/unit/test_windows_camera_capture_ingest.py -q
.\.venv\Scripts\python.exe -m pytest software/tests/unit/test_commissioning_rehearsal_service.py -q
```

The final command uses actual local Windows NTFS storage and may take several
minutes. No command above should enumerate/open a physical camera or serial port.

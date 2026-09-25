# Windows camera worker: DEV-006 implementation boundary

Status: **implemented native spike; compiled; fixture-tested; not verified on
the received B0477; not authorized for physical activation**. This is a backend
for the [connection plan](../../docs/CAMERA_ARM_CONNECTION_INTEGRATION_PLAN.md),
not an independent commissioning utility or an activation release. The wizard
keeps physical acquisition closed pending its reviewed coordinator, source
migration and independent qualification. Do not run this helper against a
camera merely because it compiled.

The [identity metadata resolver](IDENTITY_METADATA.md) is now linked into the
explicit metadata-only `identity` action and its typed Python client method.
It uses the separate `rocell.windows_camera_identity.v1` receipt; the existing
camera v1 receipt is unchanged. Neither operation is called by construction or
page load. Actual Windows device-tree behavior remains unverified.

## What is implemented

- Explicit Media Foundation metadata enumeration returns opaque symbolic
  endpoint and friendly label. It does not activate a source. It does **not**
  manufacture a unit serial, VID/PID, container, USB speed or topology result.
- Explicit identity lookup maps one opaque candidate endpoint to its observed
  devnode, instance ID, container GUID, location paths and bounded parent chain.
  This SetupAPI/Configuration Manager branch runs before COM/MF startup and
  never activates a camera. Each missing field retains its unavailable reason;
  friendly names and endpoint suffixes are never promoted to serial/USB speed.
- Probe re-enumerates and matches the exact reviewed endpoint, activates once,
  enumerates native modes and supported control readback, then shuts down.
- Capture selects an enumerated native **YUY2** mode, disables format converters
  and video processing, reads back the actual mode, validates the entire
  requested control batch, applies it, and reads the values/modes back.
- A finite asynchronous frame burst has one outstanding sample request. It
  records host sequence, Media Foundation timestamp (100 ns units), arrival QPC
  and its frequency, observed stride/row origin, bytes and optional discontinuity.
  None is claimed to be a sensor sequence or exposure timestamp.
- Native frames go to new binary files, never JSON/base64. One buffer is held
  at a time. The client hashes files incrementally and checks bounds, count,
  actual file length and returned mode before accepting a receipt.
- All paths are explicit, all operations are finite, all cleanup is reported.
  There is no first-device fallback, retry, reconnect, background camera owner,
  auto-focus/aperture control, firmware modification or serial/robot access.

The capture seam is a finite frame burst, not yet an integrated five-minute
live-preview transport. The application may derive diagnostic previews from its
verified frame artifacts; they do not automatically become calibration evidence.
Native chunked evidence publication, approved persistent identity binding,
worker/cell leases, one-use permits and live preview backpressure belong to their
separate playbook tickets. A compiled helper is not evidence those exist.

## Build and hardware-free tests

Observed environment on 2026-09-07: Windows x64, CMake 3.31.3,
Visual Studio Build Tools 2022, MSVC **19.42.34435.0**
(tool directory 14.42.34433), Windows SDK **10.0.22621.0**.
The CMake target enables `/W4 /WX`, C++17, control-flow guard, ASLR and NX.
The build links Windows SDK libraries only; no camera vendor SDK, downloaded
C++ dependency, kernel driver or extra Python package is required.

From the repository root in PowerShell:

```powershell
cmake -S software/native/windows_camera -B software/native/windows_camera/build -G "Visual Studio 17 2022" -A x64 -T v143 "-DCMAKE_SYSTEM_VERSION=10.0.22621.0"
cmake --build software/native/windows_camera/build --config Release --parallel 2
ctest --test-dir software/native/windows_camera/build -C Release --output-on-failure
.\.venv\Scripts\python.exe -m pytest software/tests/unit/test_windows_camera_worker.py software/tests/unit/test_windows_camera_identity.py -q
Get-FileHash -Algorithm SHA256 software/native/windows_camera/build/Release/rocell_windows_camera.exe
```

Run these commands separately and check exit codes. Quote the whole `-D` SDK
argument in PowerShell. `v143` chooses the installed compatible toolset; verify
the actual compiler against the build record before registering a package.
The source/build instructions are repeatable, but byte-identical reproducibility
across machines has **not** been demonstrated. A new executable hash requires a
new reviewed registration; never update a saved registration automatically.

CTest invokes three hardware-free tests: the helper's `--self-test` (14 pure
contract assertions), the separate incapable FakeApi executable (43 assertions)
and 22 fake-generated native receipts parsed by the production Python boundary.
No test calls the helper's real `inventory`, `identity`, `probe` or `capture`
branches. No COM/MF startup, device-tree query or camera access occurs. The
cross-language CTest uses the existing repository `.venv` and is only registered
when that interpreter exists. Python unit tests use injected runners and
temporary fixture files; the current camera/identity suite passes 95 tests.

The locally produced executable is
`build/Release/rocell_windows_camera.exe`. `integrated_build_manifest.json` records
the rebuilt helper's dated hash and limitations. `build_manifest.json` and
`identity_metadata_build_record.json` are explicitly superseded historical
records whose hashes do not represent the integrated source/build. None is a
trusted release manifest or authority artifact. Packaging/signing, protected installation,
reviewed runtime registration and clean-machine qualification remain outstanding.

## Python integration contract

Read [camera_worker_client.py](../../src/rocell/providers/windows/camera_worker_client.py).
Construction is inert, including no helper-hash read. The explicit inventory
method verifies the registered helper hash and invokes only metadata enumeration.
It must be called from an explicit inventory action, never status/page loading.

For one server-resolved `CameraCandidate` from that inventory, call
`resolve_identity_metadata(candidate, duration_ms=5000, max_parent_nodes=8)` only
after an explicit metadata request. This method verifies the registered helper
hash, invokes only the `identity` action, and returns `NativeCameraIdentityReceipt`.
The actual interface path is retained separately from the requested endpoint;
`exact_endpoint_observed` is false for any string mismatch or mapping cleanup
error. This observation is not persistent unit identity or an activation permit.
Full fields, bounds and binding limitations are in [IDENTITY_METADATA.md](IDENTITY_METADATA.md).

Probe/capture require:

1. `CameraEndpointBinding`: exact opaque symbolic link, matching SHA-256 of its
   UTF-8 bytes, and SHA-256 of the independently reviewed binding artifact.
2. Current source SHA-256, bounded campaign ID, immutable `CameraCampaignBudget`,
   selected `NativeCameraMode` and optional `CameraControlSetting` tuple.
3. A required external `authorize(CameraActivationRequest)` callable. It must
   consume the exact one-use coordinator authority or throw. The request binds
   all of the above, helper hash, output directory and serialized argument hash.
   There is no `authorized=true` field, no default permissive authorizer, and no
   browser-supplied endpoint/executable/control channel. Do not copy the tests'
   no-op authorizer into application composition.
4. A new empty absolute, non-reparse output directory owned by the campaign.
   Free-space preflight must cover its approved byte budget. Files are opened
   with `CREATE_NEW`; failures preserve existing/partial files for inspection.

IPC schema: `rocell.windows_camera.v1`. `NativeCameraReceipt` separates requested
and observed formats, typed control observations, hashed artifacts, operation
counts, cleanup and limitations. Unknown fields, duplicate JSON keys, ambiguous
coercions, nonfinite numbers, identity mismatch, unexpected mode, impossible
stride and inconsistent effect/artifact counts are rejected. A successful native
exit with a failed receipt (or the reverse) is rejected. Invalid/missing receipts
after activation dispatch raise `CameraWorkerError(effect_uncertain=True)`.
Failed receipts with uncertain shutdown retain `receipt.effect_uncertain=True`.
The coordinator must persist/reconcile these results and hold uncertainty; it must
not infer cleanup from process exit or start another campaign automatically.

Hard implementation ceilings, not claims of device capability:

| Resource | Maximum |
| --- | --- |
| Combined stdout/stderr | 256 KiB |
| MF metadata candidates / native modes | 64 / 128 |
| Controls | 6 explicitly named electronic controls |
| Native frame files | 32 per campaign |
| One frame / total file payload | 64 MiB / 2 GiB |
| Activation campaign time | 300 seconds plus 5-second outer cleanup allowance |

The default client runner uses a shell-free, hidden subprocess and capped pipe
readers. The outer deadline also bounds a driver wedged in activation, shutdown
or release. Forced termination is an uncertain cleanup outcome, not proof of
device deactivation. There is no interactive cancellation channel in this first
native burst protocol; caller cancellation must wait for bounded completion or
explicitly retain forced-termination uncertainty.

## Limits and received-unit acceptance

- MF endpoint metadata is not full persistent unit identity. The compiled
  SetupAPI/container/location-path provider is integrated, but observed data
  still needs application-level binding assessment, reviewed reconnect policy,
  source-bound coordinator integration and real Windows qualification before
  physical selection. No camera serial or negotiated USB speed is assumed.
- `IAMVideoProcAmp` / `IAMCameraControl` are queried on the MF source. Not every
  installed source exposes them. Missing interface/range/readback leaves controls
  unavailable; requesting one fails without a substitute backend. Actual B0477
  driver support and control units/ranges must be verified on the received unit.
- Capture accepts one native sample buffer. Stride must be observed through
  `IMF2DBuffer2` or the media type, never inferred merely from the requested width.
  If 2D accessible capacity differs from sample current length, the worker fails
  instead of persisting spare allocation bytes as sensor data. Multibuffer samples
  and unverified layouts need a separately qualified implementation.
- Unit tests inject worker receipts, not every COM API. The native self-test does
  not emulate driver calls. Driver removal, identity races, coerced formats,
  control failures, streaming latency and shutdown must additionally be qualified
  with an instrumented Windows API seam and the received hardware.
- Helper hash checking plus non-reparse checks are not protection against an
  adversarial local administrator replacing paths after validation. Runtime
  package ACLs/registration and output-directory ownership require qualification.
- No native full-size B0477 throughput, focus at the intended board distance,
  USB3 link speed, installed native controls, scene freshness, calibration or
  physical capture has been verified. No host webcam was used for these tests.
- These raw temporary artifacts are not M3 immutable manifest-last datasets.
  Do not export/publish them as accepted installed calibration until that service
  validates and seals them with the exact receipt and source/settings epochs.

## Official API references consulted

- [Microsoft symbolic capture endpoint attribute](https://learn.microsoft.com/en-us/windows/win32/medfound/mf-devsource-attribute-source-type-vidcap-symbolic-link): treat the symbolic link as opaque; the friendly label is separate. Explicit SetupAPI mapping supplies observations for later binding assessment.
- [Microsoft asynchronous sample callback](https://learn.microsoft.com/en-us/windows/win32/api/mfreadwrite/nf-mfreadwrite-imfsourcereadercallback-onreadsample): samples may be null for stream events, and media times have 100-nanosecond units.
- [Microsoft 2D buffer bounds](https://learn.microsoft.com/en-us/windows/win32/api/mfobjects/nf-mfobjects-imf2dbuffer2-lock2dsize): stride can be negative; row origin and accessible buffer bounds must be validated; every successful lock needs unlock.
- [Microsoft video control range](https://learn.microsoft.com/en-us/windows/win32/api/strmif/nf-strmif-iamvideoprocamp-getrange): discover range, step, default and auto/manual capability instead of assuming support. The control API is legacy; MF remains the acquisition backend.
- [Integration-plan vendor source table](../../docs/CAMERA_ARM_CONNECTION_INTEGRATION_PLAN.md#4-official-software-and-documentation-integration-decisions): purchased B0477 native modes and manual-optics assumptions, with received-unit holds intact.

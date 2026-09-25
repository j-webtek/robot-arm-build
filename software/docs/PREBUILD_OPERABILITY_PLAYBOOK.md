# Pre-build operability: camera first, no arm access

## Current decision

The received B0477 is available on USB. The RoArm-M3 Pro is unassembled;
the final overhead support and placemat build are not ready. At the operator's
request, distance, focus, aperture, final coverage and installed calibration
are **deferred until the build exists**. There is no pending one-metre bench
test. Deferred does not mean passed or guaranteed adjustable at the final height.

Keep the arm unplugged/unpowered. No connection, boot, homing, torque, motion,
keyboard contact or phone tapping is authorized by this workflow. Software Stop
only cancels diagnostics; it is not a physical emergency stop.

## What is already demonstrated

See [received-camera observations](CAMERA_BENCH_2026-09-11.md) for retained
original bench files and limitations. Camera enumeration, short throughput,
read-only electronic controls, still acquisition, release and one supervised
unplug/replug cycle have been exercised through the **separate bench utility**.
They do not establish live integration in the commissioning wizard.

The delivered unit reports 5472 x 3648 YUY2 at **8 fps**, and 2720 x 1536 at
**30 fps**. The pinned reference still contains catalog-based assumptions.
Synthetic coherence against that reference is not acceptance of the delivered
camera's modes. Do not silently rewrite the profile or lower qualification gates.

## Do now: one grouped software check in the existing wizard

From the workspace root:

```powershell
.\start-rocell-wizard.ps1
```

1. Leave the hardware as it is; no camera access is needed for this check.
   If an older wizard is already open, export anything needed, close that
   session deliberately, then launch afresh. A browser refresh does not load
   changed Python source.
2. Open **Camera**, find **Run pre-build vision checks (no devices)**, preview
   the action, then confirm once. The action is also available in physical
   diagnostic mode, but performs the same entirely synthetic checks there.
3. Review all seven steps in the operation result. The first checks actual
   synthetic-image marker detection, normal registration and rejection when
   the four pose-fit markers disappear. The remaining steps run the nominal,
   wrong-identity, wrong-mode, stale-frame, identity-drift and close-failure
   connection fixtures. Correct rejection of an injected fault is success.
4. An overall failure remains a failure, with the individual step report and
   stderr retained. Do not infer camera readiness from process completion alone.
5. Open **Diagnostics & exports**, optionally record an issue note, then
   preview/confirm **Export diagnostic report**. Use the assigned workspace
   folder `software/runs/wizard-exports`. Each export gets a new directory and
   is checksum-verified by the application. Preserve earlier failures.
6. Stop here for operator review before any live camera action. This pack
   does not display live pixels, acquire metadata, change controls or advance
   any physical commissioning stage.

Implementation: the action catalog registers `prebuild_vision_checks`; the
fixed diagnostic worker calls the existing source-bound CLI rehearsals. The
normal wizard preview/confirmation, bounded child process, Stop, operation
log and export mechanisms are reused. No new device provider or bypass is added.

## Highest-value next work, in order

| Priority | Test / integration | What must be retained | Operator pause / limitation |
| --- | --- | --- | --- |
| 1 | Wizard software path: start disconnected, preview, execute, report, export | Seven-step synthetic result, failures, zero device effects, unchanged physical stages | Implemented by the grouped check; no camera permission needed |
| 2 | Camera-only identity and native mode onboarding in the real wizard | Exact selected unit, native endpoint, actual modes, read-only controls, source binding | Close Windows Camera and confirm readiness first; metadata is not permission to stream |
| 3 | Resolve full-history native acquisition integration | Fresh original-path test with attempt/result/export/reopen and no modeled prerequisite acceptance | Existing full-history failure is unresolved; do not substitute bench JSON for original evidence |
| 4 | Delivered-mode assessment | Explicit 8 fps / 30 fps discrepancies, policy decision and regression tests | Do not accept a requested mode if readback differs; no silent fallback |
| 5 | Finite camera image through wizard UI | Selected identity, requested/observed format, timestamps, raw/still file hashes, completed release, visible provenance | Explicit capture confirmation; no parallel Windows Camera owner; snapshot is not live preview |
| 6 | Image-health and freshness handling | Distinguish no frame, decode failure, stale timestamp, under/overexposure, repeat content and marker absence | Test logic with fixtures first; a static scene can legitimately produce identical images |
| 7 | Failure/recovery and bounded endurance | Busy device, timeout, lost camera, cancellation, clean release, explicit retry, elapsed/frame counts | Separate operator confirmations before physical unplug/replug; retain pre-failure records |
| 8 | Reversible electronic controls | Before values/modes, requested change, actual readback, restore attempt and final state | Separate confirmation before writes; restoration cannot be assumed after loss of the device |

Live camera onboarding must be usable **without a finished board**. A can or
plain tabletop is an acceptable image transport test: absent placemat markers
should say "camera image available; board not registered", not imply a broken
camera and not release robot actions. Conversely, synthetic marker detection
does not establish detection at the installed distance or on the actual print.

Keep the existing original-evidence prerequisites intact while completing that
integration. A future camera-only diagnostic branch, if needed, must be clearly
separate from commissioning authority, not a way to mark missing build evidence
as accepted. The new grouped check is only a software rehearsal branch.

## Still deferred until assembly

- Rigid mount geometry, final focus/iris, full-field sharpness and lighting.
- Intrinsics at the retained capture mode; placemat markers and board registration.
- Measured keyboard/phone surface heights, tool offset and physical reachability.
- Arm identity/firmware/startup, independent safety and power checks, feedback,
  noncontact motion and then separately authorized contact trials.

The current short typing simulator still has a legacy camera graph and
provisional IK gaps. It is useful for semantic/UI tests but is not evidence that
the assembled static-camera workcell can reach or press every target.

## Verification and handoff

`tests/unit/test_prebuild_vision_checks.py` covers closed input, both wizard
modes, busy-state blocking, retained failures, real synthetic algorithms over
the HTTP service, duplicate-submit suppression and verified export, with
device entry points/process launch forbidden. It also checks camera status and
physical stage gates remain unchanged. This is in-process worker integration;
the bounded production subprocess lifecycle has its own regression tests.

Use fresh test/export directories on every run. Consult the
[completion matrix](ONBOARDING_APPLICATION_COMPLETION_MATRIX.md) and
[camera/arm developer playbook](CAMERA_ARM_DEVELOPER_PLAYBOOK.md) before changing
any physical admission or qualification path.

### Verified checkpoint — 2026-09-11 local / 2026-09-12 UTC

- Selected regression run: **287 passed in 22.82 seconds**. Includes the new
  action/real synthetic HTTP pipeline, actual JavaScript rendering under a
  finite DOM, service, action catalog, worker, process lifecycle and export
  tests. Not the full repository suite or full-history physical commissioning.
- JUnit: workspace-relative
  `.codex-preserved/prebuild-vision-20260911-03.xml`, SHA-256
  `bd64cf6a2903bd1478c5d0c26362c13ad83c8830579af7ea33696e1c70d1ed10`.
  Earlier run 01 retained a failed test assertion that incorrectly expected all
  markers to disappear. Correct behavior retains markers 4/5 while rejecting
  pose registration; the product algorithm did not need changing.
- Separate actual service/production-child run: operation
  `operation-fef41c2a729e446fadc1a54930e081d1` completed all seven checks.
  Camera stayed disconnected, physical stages unchanged, no device effects.
  The diagnostic session was shut down after export, not left running.
- Verified diagnostic export:
  `software/runs/wizard-exports/wizard-20260912T002543328118Z-98699c41ec77445babd8543b6331c024`.
  The full seven-step result is retained as a JSON attachment. This export is
  software rehearsal evidence only, with no live camera images.

### First actual wizard metadata attempt and offline correction

After the operator confirmed Windows Camera closed and the arm unplugged, a
fresh **physical-mode** service ran `inventory_devices` once through the real
diagnostic child. This was the backend used by the wizard, not a browser click
or a new bench-utility capture. The fixed PnP query reads metadata only;
no camera/serial endpoint open, video stream or settings action was requested.

- Operation `operation-a68f099a12d24d23878a196f79a350be` failed with
  `Windows PnP output root must be an array`. No usable camera candidate was
  published. This does not establish either camera absence or camera failure.
- Failure export, verified and retained unchanged:
  `software/runs/wizard-exports/wizard-20260912T002816063526Z-353d9361433a403a98da3a89b69a7190`.
  The failed worker did not retain its raw PnP stdout, so this export records
  the parsing error rather than a complete received-device snapshot.
- Offline reproduction confirmed Windows PowerShell unrolls a one-item array
  sent through the `ConvertTo-Json` pipeline. The fixed collector wraps the
  producing pipeline in `@(...)` and serializes the resulting array through
  `-InputObject`. Both boundaries matter for empty and singleton inventories.
  The Python decoder still rejects non-array roots; identity gates are unchanged.
- New tests execute the actual PowerShell script with local fixture functions
  replacing both PnP commands and module autoloading disabled. They cover empty,
  one, multiple and over-limit inventories; missing serial, Unicode and class
  filtering; and strict rejection of malformed JSON roots. They make no actual
  device query. The first test run's fixture/assertion errors are retained too.
- Selected regression: **110 passed in 13.68 seconds**; JUnit
  `.codex-preserved/pnp-serialization-20260911-02.xml`, SHA-256
  `938e0eab1bd730b2e2ffa507740f183496cb8b9ae8f6a3cb70d8882851d5ddbe`.
  Corrected `physical_device_inventory.py` SHA-256:
  `5294a0c49d16a42d77c442a2c85177f500caed6aa7da530b6e7923de82136a6d`.

The failed session was shut down after export. The separately confirmed retry
is recorded below; the old ticket and failure report were not replayed or changed.

### Confirmed actual metadata retry — 2026-09-12 UTC

The operator explicitly requested a retry and reported no setup changes:
camera positioned/plugged in, Windows Camera closed, arm still unplugged.
A fresh physical-mode service ran `inventory_devices` once and exported its
result, then shut down. No camera selection/review, native lookup, video stream,
electronic settings or arm connection was performed.

- Operation `operation-78c0b77f6c1549879b1b41b10144ab6d`: **SUCCEEDED**;
  actual diagnostic worker elapsed 2.344 seconds, exit code 0.
- Exactly one camera candidate: **Arducam B0477 (USB3 20MP)**,
  VID `04b4`, PID `0477`, source `WINDOWS_PNP`.
- The generic camera-function PnP record does **not** supply a unit serial.
  Missing persistent-unit selector, USB topology and negotiated speed remain
  explicit blockers. Do not infer "no serial exists" or fill this field using
  old bench evidence: the USB parent/native mapping needs its own current check.
- Four serial metadata candidates were returned; none was selected or opened,
  and none was assumed to be the arm. Device opens, serial writes, power events,
  motion and contact counts were all zero. All physical stages were unchanged;
  camera remained `NOT_CONNECTED` (metadata found, not a video connection).
- Verified export:
  `software/runs/wizard-exports/wizard-20260912T004023948056Z-32573d2f32484c1f904426e8c81022a4`.
  Source binding:
  `8e0e3d3821b2f44ca0cb79d072854149120485d37f2b81deb18298a65512f9a5`.

The serialization correction now has received-camera metadata verification.
The next step is explicit current camera identity/native-endpoint matching,
with the registered metadata-helper and review prerequisites checked first.
That is still separate from capture or settings authority. No repositioning or
repetition of the deferred focus checklist is needed for metadata checks.

### USB parent checked; native endpoint lookup held — 2026-09-12 UTC

On the operator's next `Continue`, a supplemental read-only Windows PnP query
resolved exactly the previously observed camera-function instance and its
immediate USB parent. This query was **outside** the wizard collector; its
result is retained as a labeled diagnostic note, not original commissioning
evidence or a native endpoint binding.

- Observation time: `2026-09-12T01:03:20.8711027Z`.
- Camera function:
  `USB\VID_04B4&PID_0477&MI_00\7&257B140A&0&0000`.
- USB parent:
  `USB\VID_04B4&PID_0477\ARDUCAM_20250915_0001`.
  This is the observed parent instance identifier, not a separately acquired
  serial-number property or proof of uniqueness across multiple cameras.
- Both nodes were present, status `OK`, problem code `0`, with the same
  container `{FDA6FF49-D5B1-515D-AE69-EDB736E25233}`.
- Negotiated USB speed and native capture-endpoint mapping were not acquired.

Before any native executable launch, the fixed helper-catalog inspection
returned **HASH_DRIFT / metadata ineligible**. The old helper executable and
historical build record still match, but seven pinned source/client files do
not: `camera_worker.cpp`, `CMakeLists.txt`, `identity_metadata.h`,
`identity_metadata.cpp`, `identity_metadata_tests.cpp`,
`identity_metadata_wire_test.py`, and `camera_worker_client.py`.
This blocks registration; it is a software-version alignment issue, not
evidence of a bad camera, cable or focus setting.

The same inspection was retained through the actual wizard service as
`operation-caa57e1882994400a32a04c2d480bc28`. Operation `SUCCEEDED` means the
file inspection completed; its eligibility verdict remains **HASH_DRIFT**.
No helper review/registration, native inventory or identity query was executed.
Native endpoint actions remained disabled; the current launch also had no
reviewed generic candidate, because old selections are not restored on restart.

Verified export containing the full file comparison and supplemental PnP note:
`software/runs/wizard-exports/wizard-20260912T010400203497Z-0cefe15100e44c008d5c39a6f74b0f79`.
The diagnostic service shut down after export. No camera/serial endpoint open,
capture, control write, power event or motion occurred; physical stages stayed
unchanged. Earlier exports and all build records remain untouched.

#### Next software work before retrying native lookup

1. Review current native/client changes against retained build records; select
   one coherent metadata-only runtime/source version. Do not point the old
   executable at newly accepted source hashes as if it were rebuilt from them.
2. If a new build is needed, use a separate build directory and new explicit
   record; preserve the old runtime/catalog and do not promote capture authority.
3. Verify the native identity/cleanup/parser fake-API and Python wire contracts,
   then test registration acceptance, source drift rejection and denied capture.
4. Introduce an explicitly reviewed successor metadata catalog/provider path.
   Do not remove hash checks, teach them to accept whatever is on disk, or run
   an unregistered helper to bypass the hold.
5. In a fresh wizard session: inspect/review the coherent metadata helper,
   acquire/review the exact generic camera, discover native endpoints, select
   the matching endpoint, acquire identity and review the exact mapping.
   Export every outcome, including partial failures. Camera capture, USB-speed
   qualification and the arm remain separate subsequent steps.

### Metadata runtime aligned; received endpoint matched — 2026-09-12 UTC

The five software steps above are complete within metadata-only scope. The
operator authorized continuing software and metadata checks without repeated
proceed prompts; capture, USB descriptor IO, settings and arm access were not
added to that scope. No physical repositioning or focus checklist was required.

The [successor work order](CAMERA_METADATA_SUCCESSOR_WORKORDER.md) records a
separate guarded build, immutable build record, fixed 17-file catalog and new
wizard default. The old executables, manifests, v1 catalog and failed reports
remain unchanged. Matching the successor is not acceptance of the old drift.
Four native test groups and **615 selected Python tests** passed, including
catalog drift/missing-file failures, mixed-report rejection, no fallback,
metadata-only provider scope and service/export integration. These are bounded
regressions, not complete commissioning acceptance.

Two fresh physical-mode service sessions used actual production metadata
providers. Both were shut down after assigned-folder exports; neither used
video capture, a settings write, USB hub-descriptor IO or any arm operation.

1. The first session inspected/reviewed the new helper, acquired/reviewed the
   generic B0477 camera, and enumerated one native endpoint. The orchestration
   stopped because the returned Media Foundation interface GUID was not the
   earlier DirectShow interface GUID. This partial result is preserved at
   `software/runs/wizard-exports/wizard-20260912T011648755304Z-2aa086769eec4658a8a4cd487a38544e`.
   It was not overwritten or treated as a completed identity lookup.
2. The second session repeated fresh prerequisites, selected the exact observed
   Media Foundation endpoint, acquired its native identity, reviewed the exact
   result and exported it. These were separately admitted wizard-backend
   operations, not browser-click verification or injected device observations.

The completed metadata run is session
`wizard-d9b2d8c15a6d42778c5eb3ac144ff608`. Identity operation
`operation-7ce0825af956405eb1af1c9ac3b60e0c` succeeded with
`rocell.windows_camera_identity.v2` and
`WINDOWS_SETUPAPI_CONFIGURATION_MANAGER_METADATA` provenance.

| Observation | Received result |
| --- | --- |
| Camera | Arducam B0477 (USB3 20MP), VID `04b4`, PID `0477` |
| Camera-function instance | `USB\VID_04B4&PID_0477&MI_00\7&257B140A&0&0000` |
| Container | `fda6ff49-d5b1-515d-ae69-edb736e25233` |
| Exact endpoint / generic instance / container match | All true |
| Driver | Microsoft; service `usbvideo`; INF `usbvideo.inf`; version `10.0.26100.9444` |
| Immediate USB parent | `USB\VID_04B4&PID_0477\ARDUCAM_20250915_0001` |
| Parent traversal | `REACHED_OBSERVED_ROOT`; metadata cleanup errors empty |
| Source activations, samples, frames, control writes | All zero |
| Final enrollment review | `REVIEW_HELD`; no persistent binding |

The exact Media Foundation endpoint is:

```text
\\?\usb#vid_04b4&pid_0477&mi_00#7&257b140a&0&0000#{e5323777-f976-4f5b-9b55-b94699c46e44}\global
```

Its SHA-256 is
`702c0c6aa34eca4aa95d42d5c3a0610423c485e7394be57cb64ff657f17e2c2d`.
Do not replace the previously observed DirectShow interface GUID or assume
API-specific endpoint strings are interchangeable. The actual native identity
receipt establishes this endpoint's device-instance/container mapping.

The review completed procedurally but returned
`METADATA_ACKNOWLEDGED_BUT_HELD`: `CAMERA_PERSISTENT_UNIT_SELECTOR_MISSING` and
`CAMERA_UNIT_SERIAL_MISSING` remain. The generic camera-function record still
does not supply a unit serial. The parent's suffix is an observed USB instance
identifier, not a separately acquired serial property or uniqueness proof.
Its appearance is not grounds to remove the missing-identity gates. Similarly,
USB 3 product/hub names do not measure negotiated link speed. Driver metadata
observation is not driver qualification.

Verified diagnostic export with eight result attachments, full metadata
receipts, review, note and event history:
`software/runs/wizard-exports/wizard-20260912T011802570264Z-f97251374e6648128bd0ae956595830e`.
Workspace source binding at acquisition:
`385da3bb6559d7baaa7bd3b8060309e364e12560dcd3f86a87e89ad9a1d17fe9`.
All physical stages remained unchanged and the camera state was `NOT_CONNECTED`:
the system identified it without starting a video connection. The arm remained
untouched. Diagnostic role labels describe software steps, not independent
authenticated reviewers. Exports identify local devices; review before sharing.

#### Remaining dependencies

- Persistent-unit identity and negotiated speed need separately admitted,
  original-bound USB evidence and review; do not infer them from this report.
- The original-bound camera probe/settings workflow still needs its separate
  full-history integration check. The new metadata helper cannot capture.
- Final focus, aperture, coverage, rigid overhead mount and measured board
  registration remain deferred until the hardware build is ready.
- Arm assembly/startup, feedback, calibration and physical key/tap execution
  remain separate held stages. No successful metadata check releases them.

This checkpoint requires no user action. A fresh wizard launch still requires
fresh explicit inspections/reviews; old operations are not resumed or replayed.

### Clearer startup-failure diagnostics — 2026-09-12 UTC

The [failure-diagnostics increment](CAMERA_ATTEMPT_FAILURE_DIAGNOSTICS_WORKORDER.md)
makes the wizard surface a retained camera startup cause such as
`ADMISSION_DEADLINE_EXPIRED`, while preserving the stable dispatch code and the
uncertain/quarantined attempt. The old `CAMERA_ATTEMPT_NOT_KNOWN` label alone
could hide that the attempt existed but lacked complete native accounting.

The main operation result now explains that distinction. Its small structured
summary survives normal diagnostic export; the exact-attempt export preserves
the complete original evidence and completion. Missing accounting stays unknown,
not zero effects, and a constructed release buffer is not proof of delivery.
Rendering/status polling does not retry or reconnect anything.

Verification uses incapable process peers, real deadline checks and original
storage, not this plugged-in camera. Received hardware was not queried or
activated in this increment. Final optics/board calibration remain deferred.
The preserved full-history run 03 is now correctly documented as a terminal
admission-deadline failure; the admission-performance fix remains open.

Final verification: **102 combined regression cases plus two distinct public
settings-capture cases passed**. Both launcher check modes remain inert and
disconnected; the metadata-only helper/build record are unchanged. Exact reports,
test export paths and remaining typing-check findings are in the linked work
order. No user hardware action is required by this completed software increment.

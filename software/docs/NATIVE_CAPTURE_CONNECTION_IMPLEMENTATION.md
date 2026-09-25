# Native camera capture connection implementation

Date: 2026-09-08. Status: capture admission and controller-resolution
prerequisites implemented and verified within the non-hardware scope below. No physical
activation or new physical connection button is enabled.

The previous increment completed the contained arm-feedback rehearsal and its
thirteen-stage application/restart integration. This increment advances the
actual camera preview connection path, not another replacement simulation.
The existing Media Foundation helper implements finite YUY2 capture, requested
controls, readback, bounded files and a native receipt. This increment adds a
separate guarded capture entry and its Python parent/result join. Direct capture
invocations remain refused; the physical runner still refuses dispatch before
process creation, native work or file inspection.

## Required implementation

1. Add a distinct capture admission codec and dormant runtime preparation. Bind
   the exact selected endpoint, source, helper/build pins, consumed permit,
   native mode/control request, budgets and assigned output location. The
   browser cannot supply arbitrary commands, helper paths or authority flags.
2. Add `--owned-capture` to a separately compiled development helper. Validate
   the complete request, actual child PID/challenge, one RELEASE and EOF before
   constructing native capture options or starting COM/Media Foundation.
   Legacy direct capture remains refused. A probe request cannot authorize
   capture, and a capture request cannot enter the old probe gate.
3. Reuse the existing parent-owned process and current-permit handshake, with
   exact capture preparation/result typing. Retain the actual native receipt;
   do not relabel admission-only or synthetic completion as physical capture.
4. Verify protocol, request reconstruction, result/native cleanup, assigned
   destination, cancellation/deadline and no-replay behavior without hardware.
   Compile the real helper but execute only separate incapable native test
   executables. Preserve old binaries, manifests and failed stores.
5. Inspect the arm's remaining exact controller metadata-resolution seam in
   parallel. Reuse existing metadata contracts and the worker callback; do not
   infer firmware, startup behavior, power or atomic handle identity from USB.

## Wire and lifetime contract

New request schema: `rocell.native_camera_capture_admission_request.v1`.
The existing fourteen probe binding fields are retained, with a distinct schema
and one additional `capture_json` string. That string is a canonical flat JSON
object with these exact fields:

| Field | Meaning |
| --- | --- |
| `width`, `height`, `fps_numerator`, `fps_denominator` | Exact native mode; existing typed integer limits, even YUY2 width |
| `subtype` | Exactly `YUY2`; no implicit conversion |
| `frame_count`, `max_frame_bytes`, `max_total_bytes` | Existing finite campaign limits, never an unbounded stream |
| `output_directory` | Exact server-assigned child working directory plus `capture-<attempt_id>` |
| `controls` | Canonical sorted `name,value,mode` entries separated by semicolons; empty allowed; existing six control IDs only |
| `requested_stride_bytes` | Empty string for unspecified, otherwise canonical signed nonzero integer; observed native stride is independently checked |

The nested encoded flat object deliberately reuses the existing bounded native
flat decoder without broadening the old probe schema or parser field-count
limit. All numeric/text/control/path validation is duplicated at the language
boundary and cross-language tests must demonstrate parity.

New capture admission has a fixed **five-second** wait, native capture remains
five seconds, and the owned process has fifteen seconds plus two seconds of
independent cleanup. Preparation requires this full seventeen-second lifetime
inside the original parent permit; there is no renewal or retry. The old probe
admission remains two seconds. This new capture bound accounts for the measured
mature-session validation delay found in the arm integration.

## Edit ownership and verification

- Root: Python capture codec/preparation, existing parent/runner join, integration
  tests and final evidence record.
- Native agent: new capture protocol/entry, guarded production branch, separate
  capture build/test project, incapable native tests and new build record.
- Arm agent: bounded controller-resolution seam and tests, without opening ports.
- Evidence agent: independent receipt/retention review and agreed evidence tests.

Existing probe source/pins/builds should stay unchanged where possible. The new
capture build is separate; building it does not register or qualify a helper.
Source drift remains visible. Freeze 011, hardware geometry, physical power and
all activation/commissioning gates are unchanged.

## Completion evidence for this increment

### Implemented joins and developer entry points

| Layer | Implementation and caller obligation |
| --- | --- |
| Capture intent | `providers/windows/native_camera_capture_protocol.py`: distinct request and canonical nested configuration. Exact mode, sorted controls, stride, budgets and assigned path are checked without I/O. |
| Dormant runtime | `native_camera_capture_registration.py`: `prepare_owned_native_capture` reconstructs the existing `CameraWorkerPlan`, not an independent camera command. Its helper/build paths are fixed and the runtime stays unqualified. |
| Parent admission | `native_camera_parent_admission.py`: exact probe/capture typed union, original consumed-permit checks, actual child PID/challenge, one release and original deadlines. The full preparation is revalidated, not just an endpoint string. |
| Owned runner | `owned_native_camera_runner.py`: capture preparation uses the existing bounded process owner; the production runner's physical hold occurs before owner creation. Tests do not add an enable flag. |
| Native entry | `native/windows_camera/capture_admission_protocol.*`, `capture_admission_entry.*` and the guarded branch in `camera_worker.cpp`: validate request/release/EOF before COM/Media Foundation. Separate `capture/CMakeLists.txt` builds the development helper and incapable tests. |
| Retained result | `owned_native_camera_evidence.py`: distinct capture evidence schema retains the full native result and process observations. Metadata verification never invents or reads frame hashes. |
| Frame files | `camera_worker_client.py`: pure `NativeCameraReceiptMetadata` parsing is separate from explicit `validate_capture_artifacts(raw_receipt, request=original_request)`. Only bounded real-file validation produces hashes. Existing receipt callers retain their return types. |
| Arm resolution | `application/arm_controller_resolution.py` and `providers/windows/controller_metadata.py`: lazy explicit Windows CM metadata acquisition and a directly usable exact pre-open/pre-write resolver callback. No port opens or power observations. |

Read [camera receipt/file contracts](CAMERA_RECEIPT_METADATA.md) and
[arm resolver contracts](ARM_CONTROLLER_RESOLUTION.md) before composing these
APIs. The latter includes the actual worker callback construction and Microsoft
references. The reader is implemented, not a callback-only placeholder, but its
native calls have only been exercised through injected ABI functions here.

The eventual physical campaign must own this sequence: obtain current reviewed
identity and settings; prepare the exact request and assigned output; obtain
the original scoped permit; perform admission under independent process
supervision; retain result and cleanup observations; separately validate actual
frame files; publish physical-unverified content and its preview. A matching
native receipt is not permission, frame content verification, camera cleanup
qualification or a passed installed-calibration stage.

Two cross-language review findings were corrected before regression: Windows
path objects compare case-insensitively, so the assigned capture directory now
uses exact string equality to match C++; the requested-mode echo now must equal
the admitted mode exactly, including frame-rate numerator/denominator and stride.
Observed native format remains an independent check. Unsorted controls are
explicitly refused rather than silently changing an existing logical plan.

### Executed checks

Current Python/UI/configuration source fingerprint:
`67cc7816e89819b696c765ad355af5ae92e5caabe1a0fe080c268ea605c249e3`.
Native C++ source/build hashes are recorded separately; the application source
fingerprint does not include them.

- Capture protocol/preparation, capture evidence, parent and actual capture
  interop selection: **99 passed in 5.35 seconds**. This overlaps other counts.
- Actual Windows process-owner and incapable compiled C++ probe/capture entry
  selection: **10 passed in 4.03 seconds**. Covers delayed grant, final-check
  refusal, wrong PID/permit and admission-only-result rejection. No sample
  directory is created and no camera-capable helper is executed.
- Separate native CTest selection: **2 passed in 13.33 seconds**, covering
  84 parser assertions and eight actual-pipe cases. The real capture helper and
  capture-disabled compile check both compiled; neither was executed.
- Arm metadata/resolver plus worker/non-purging regression: **200 passed in
  1.26 seconds**, including 86 new tests. All CM/DLL boundaries and serial I/O
  are injected; this is not OS-device discovery or received-arm verification.
- Eight changed Python modules pass mypy and Black checks. Browser
  `ui/static/app.js` passes `node --check`.
- Offline wheel assembly passed with no dependency resolution or downloads.
  All **241** workspace Python/HTML/CSS/JS package entries match byte-for-byte.
  Artifact: `software/runs/wizard-package-check-67cc7816/rocell-0.1.0-py3-none-any.whl`,
  1,727,956 bytes; SHA-256
  `fd3bdb0f920442730190f669936fe6ffd2fe975532e73c48eef0be9c5b2a2c5c`.
  This wheel is not an independently qualified hardware release.
- Inert `start-rocell-wizard.ps1 -Mode physical -Check` passed: camera and arm
  `NOT_CONNECTED`, physical authority false, all fifteen physical stages pending,
  exports assigned to the user-selected
  `C:\Users\Jack\Desktop\robot-arm-build\software\runs\wizard-exports`.

The first broad selection reported **2,729 passed and two failed** in 244.90
seconds. Both failures asserted the previous two-file drift set for the fixed
historical helper catalog; the modified camera client is correctly a third
drifted file. Only these test expectations were updated. The catalog, historical
binary, registration hold and production code were unchanged; all **59** tests
in the two helper inspection/integration files then passed in 2.72 seconds.
The full selected rerun then passed: **2,731 passed, 3,372 deselected in 232.20
seconds**. This is the documented non-slow selection, not the entire repository
test suite. Production source remained unchanged through both runs.

### Fresh public-service nominal camera run

The documented `--probe-and-configure --assess-and-review` smoke completed with
**exit code 0**, using 21 one-shot public actions and a real Windows-owned
incapable child. The modeled probe, explicit gain32/manual plus automatic
exposure request, contained synthetic capture, independent matching readback,
stage-five assessment/review and assigned-folder export all succeeded.
One retained synthetic YUY2 frame reports 40,108,288 logical bytes. The process
tree exited with no cleanup errors. This is not a physical camera result.

- Source: `67cc7816e89819b696c765ad355af5ae92e5caabe1a0fe080c268ea605c249e3`.
- Launch: `wizard-79cb7e4f088d44068809d2788e4c4077`.
- Original rehearsal: `rehearsal-1868b115ed08404fbbd83785a0e3ca19`, under
  `software/runs/wizard-rehearsal/wizard-79cb7e4f088d44068809d2788e4c4077`.
- Camera attempt: `attempt-e9f4e7ea6b71436386f18245972472f4`;
  retained process evidence SHA-256:
  `c637ac1774a3a385d68d766fc30bd78f786be7313930e81a54337caacbd9a954`.
- Final stage: `camera_frame_freshness` pending (stage six); all fifteen
  physical stages still pending and camera/arm still `NOT_CONNECTED`.
- Independently verified diagnostic export:
  `software/runs/wizard-exports/wizard-20260908T091512573454Z-bcfc2d701a2e4e66b78a6e392cf973eb`.
  Its eleven payload files total 296,628 bytes; manifest SHA-256:
  `003249393bcec63517eedfbf69165bf9b41d87c2ed127b1834aa73e81615c961`.

The export is diagnostic, not a complete commissioning-store backup or a
physical qualification artifact. Keep the original separate rehearsal store.

### Fresh public-service settings mismatch run

The separate `--probe-and-configure --fault control-readback-drift` smoke also
completed with **exit code 0**: its expected negative scenario was retained,
not accepted as a successful camera campaign. It used 19 one-shot actions.
The actual campaign operation was **FAILED**; stage five remained
`camera_mode_controls` / `WAITING_OPERATOR`, the session stayed `HELD` and
quarantined, and no stage-five assessment/review was accepted.

Read-only inspection of the retained bytes confirmed the specific fault, not
just a generic failed result: automatic exposure was requested, while the
modeled native row returned manual flags (`2`). The retained error is
`INVALID_CAMERA_CONTRACT: requested control did not read back exactly`.
Gain32 remained unchanged. The process exited 0 with confirmed tree exit and no
process cleanup errors, but the mismatched native packet was not promoted to a
valid typed receipt. Native/device cleanup stayed unconfirmed and the attempt
sealed uncertain. No recovery, retry, replay or quarantine clearance was tried.

- Launch: `wizard-10fae4dbb9af43e5be77b17bb98247a5`.
- Original rehearsal: `rehearsal-55b4eca01edb40e1bd2035a02ea143b8`, under
  `software/runs/wizard-rehearsal/wizard-10fae4dbb9af43e5be77b17bb98247a5`.
- Camera attempt: `attempt-38f34693a33e48838c193c8733b6076b`;
  retained evidence SHA-256:
  `fb21b59256ce21aa8fe7d7508a54c03e580b5ffe13c29d0c4e1195f2ce3d749f`.
  Its 10,669 decoded bytes matched the original wrapper's length and hash.
- Independently verified diagnostic export:
  `software/runs/wizard-exports/wizard-20260908T091706772843Z-1c8492684bce415390299d80be8ee2c8`.
  Its eleven payload files total 219,845 bytes; manifest SHA-256:
  `46de880feea14b939d41f95cad71cee6705c0a4d5b1c9ed20354215f3d5c429b`.

Both fresh runs preserved all fifteen physical-pending stages and disconnected
camera/arm status. The application source fingerprint stayed unchanged.

The previous thirteen-stage M1/public-service success is recorded
in [the arm integration checkpoint](WIZARD_OWNED_ARM_INTEGRATION.md) on its own
source fingerprint. It is historical evidence, not a current-source rerun or a
store to migrate automatically.

### Reproduce this software verification

Run one command at a time from the workspace root with source frozen. These
lanes do not enumerate host devices or execute the camera-capable helper.
Do not run concurrent expensive commissioning campaigns: their real absolute
deadlines are part of the behavior under test. The smoke creates a new separate
rehearsal store and verified export; it never reuses an older reviewed session.

```powershell
.venv/Scripts/python.exe -m pytest software/tests/unit -m 'not slow' -k 'arrival or wizard or native_camera or windows_camera or capture_ingest or camera_receipt_metadata or controller_metadata or arm_controller_resolution or owned_native or arm_feedback or arm_owned or owned_arm or consumed_commissioning_scope or commissioning_coordinator or rehearsal_feedback or rehearsal_reference or scoped_rehearsal_dispatch' -q

.venv/Scripts/python.exe software/scripts/wizard_owned_camera_smoke.py --probe-and-configure --assess-and-review --expected-source-sha256 67cc7816e89819b696c765ad355af5ae92e5caabe1a0fe080c268ea605c249e3

.venv/Scripts/python.exe software/scripts/wizard_owned_camera_smoke.py --probe-and-configure --fault control-readback-drift --expected-source-sha256 67cc7816e89819b696c765ad355af5ae92e5caabe1a0fe080c268ea605c249e3
```

The smoke calls the same public service actions used by the UI: prerequisite
collection/assessment/review, modeled camera probe, explicit mode/control
staging, contained synthetic capture, independent readback, stage-five
assessment/review and selected-folder export. It stops with stage six pending;
it is not a browser-render test, a full thirteen-stage rerun or the new physical
native capture path. A source mismatch or failed action is retained as a hold,
not retried, repaired or bypassed by the script.

### Native build identity

Read-only verification matched all **15 source pins and four artifact hashes**
in `native/windows_camera/owned_capture_build_manifest.json`.
Manifest SHA-256:
`b6b60e92b1f95487be7c9230ddade77827b64a30063377b2f41a66d526eda2a5`.
The capture-capable helper is
`native/windows_camera/build-owned-capture/Release/rocell_windows_camera.exe`,
243,200 bytes, SHA-256
`31d2f2742b18c0935b3d7af07f8058f129421871be00860a3d7768e1e940ae2f`.
The incapable entry test executable has SHA-256
`16315844fa922eb9f0708c13ada643fd6cfc5338a0c3495294c6bb2d0b70b1b9`.
Do not substitute either binary into an older reviewed runtime. Historical
builds/manifests and the metadata catalog were preserved, not refreshed into an
approval. Compilation is not trusted release registration.

Current inspection of the historical metadata catalog correctly reports
`HASH_DRIFT` for `camera_worker.cpp`, the original `CMakeLists.txt` (changed in an
earlier increment), and `camera_worker_client.py`. Its binary and manifest still
match their historical pins. The new capture build uses a separate CMake project
and does not change the old CMake file in this increment. Reviewing a drifted
report does not register a provider or clear the hold.

## Remaining work toward the full wizard goal

1. Join native probe/capture to a separately qualified physical coordinator,
   fixed-runtime review and current-permit admission, with retained physical
   evidence and native failure/cleanup handling. Keep camera acquisition
   permission separate from any arm power/motion permission.
2. Join real frame-file validation/publication to the existing service preview
   and settings/readback views. Source/identity/settings drift, partial output,
   cancellation or uncertain cleanup must hold and remain exportable.
3. Place the actual controller metadata reader and non-purging serial owner
   inside the qualified physical process lifecycle. The callback's before/after
   checks do not hard-bound stalled native calls or atomically bind a COM name
   to the opened handle. No friendly-name/COM fallback can resolve that gap.
4. Finish the remaining noncontact-acceptance and handoff rehearsal stages;
   retain original-store no-replay verification and distinguish simulated
   acceptance from received-hardware approval.
5. On arrival, inspect actual unit identities, supported modes/USB bandwidth,
   camera focus/coverage, arm firmware/boot behavior and physical power. Measure
   installed geometry and calibration rather than promoting nominal plans.
6. Only after those separate gates, integrate the authorized typing/tapping
   executor. The current wizard cannot move the arm, press keys or tap a phone.

### Next implementation slice: real camera acquisition service composition

The independent read-only integration review identified two separate hard stops:
`PhysicalDiagnosticPreflightCoordinator` / `M1PhysicalDiagnosticPersistence`
are deliberately stage-1/2 **NO_DEVICE_IO** with CELL then SESSION ownership;
`OwnedNativeCameraRunner` separately holds physical dispatch before owner/pins.
Do not broaden the source-only domain or add an enable Boolean to bypass either.
Also, `camera_configuration.py` and `rehearsal_camera_probe_evidence.py` explicitly
represent incapable observations; they cannot become physical evidence through
a renamed status or provenance string.

Implement a distinct physical-camera acquisition service and scoped campaign
composition, dormant until its separate qualification/review. The existing
`WizardNativeCameraEnrollment.binding()` supplies reviewed metadata only;
freeze its evidence, purpose-specific probe/capture runtime review and exact
settings into one service-owned plan. The camera composition needs its own
camera-stage/effect admission and CELL then SESSION then CAMERA ownership.
The source-only report's `WAITING_OPERATOR` stage is not a passed prerequisite.
Model actual receipt/identity/hazard and disconnected-actuator requirements
explicitly; do not borrow synthetic PASS states.

Use `ConsumedCommissioningScope.revalidate()` at both owned-runner boundaries.
After capture, retain complete native/process evidence, validate original
raw receipt plus actual sample files, then prepare/ingest/verify the dataset
under `PHYSICAL_UNVERIFIED`. The shared service should publish a derived PNG
only after durable result read-back and successful completion logging. Label it
**last captured frame—not live** and bind source, endpoint, settings and campaign
hashes. Drift, Stop or failed publication invalidates current preview status.
Reopen verifies retained evidence and content without executing providers again.

Budget the entire sequence deliberately: capture preparation needs seventeen
seconds and admission needs five seconds, whereas ingestion's current default
is 120 seconds. The acquisition/revalidation/retention plan must fit its original
permit or define a separately bounded post-acquisition retention phase. Do not
silently inherit incompatible defaults or renew authority.

Acceptance cases for this **future** slice:

1. Public physical startup/view/prepare and missing qualification remain inert:
   zero process owners, pins, native calls or frame reads.
2. One retained endpoint/runtime/settings plan reaches the actual scoped worker
   seam under qualified test storage. Duplicate requests do not redispatch;
   downstream injected observations remain clearly synthetic, not received data.
3. Source/identity/settings drift after pins or READY, cancellation or inadequate
   remaining lifetime prevents RELEASE without refreshing any deadline.
4. Temporary YUY2 samples exercise real validation, ingestion, retention and
   service preview publication. Missing files, stride/hash drift, uncertain
   cleanup or log failure produce no current preview.
5. Original-store reopen reconstructs capabilities/configuration/capture and
   verifies datasets with every provider/runner forbidden. Corruption and
   cross-domain substitution hold without repair or replay.

This is unfinished software work, not only a hardware blocker. Camera-only
permission need not wait for arm typing qualification, but can never authorize
arm power, motion or contact. Received-unit and installed-calibration checks
remain necessary after the software composition exists.

Still outside this increment: qualified physical coordinator/runtime release,
received-camera identity/modes/USB speed/focus, actual frame acquisition and
installed calibration; serial physical qualification; final noncontact/handoff
stages and the later authorized typing/tapping executor.

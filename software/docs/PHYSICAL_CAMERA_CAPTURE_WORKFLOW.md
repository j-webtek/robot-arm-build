# Camera data workflow: implementation and developer handoff

Date: 2026-09-08. Companion to `CAMERA_ARM_DEVELOPER_PLAYBOOK.md`,
especially DEV-008. This increment connects existing production components;
it does not release native hardware activation or complete the overall wizard.

Next-input foundation: [progressive original configuration records](PHYSICAL_CONFIGURATION_EPOCH_WORKFLOW.md)
now retains the initial eight-domain dependency vector during setup. This is
not the complete `PhysicalCameraAdmissionFacts` assembler: source/receipt
acceptance, physical hazard evidence and release-qualified native dispatch
remain required before the retained data path below can consume real capture.

## Outcome and limits

The application now has a working **retained camera data path**:

1. Verify the exact original native probe and its independently retained hash.
2. Derive only the modes and electronic controls that probe actually reported.
3. Let an operator explicitly stage a supported mode and control intent.
4. Construct the real, separately scoped native capture campaign plan.
5. Check the capture's identity, mode, control readback and cleanup observations.
6. Validate the original YUY2 files, retain a chunked diagnostic dataset, verify
   its contents, and derive one bounded PNG from those retained pixels.
7. Publish the last captured image only after exact result retention, successful
   completion logging and final source/identity/Stop checks.

Tests exercise this path with **modeled native/process observations and actual
small YUY2 files**. Those are not observations of Jack's camera. No device,
native helper, serial port, power supply or robot movement is used by this work.

The ordinary app still cannot perform a physical probe/capture or connect the
arm. The new public settings action becomes available only after a valid native
probe has reached the internal service handoff; the physical dispatcher that
would supply it remains unfinished and independently held. This is a concrete
data-path implementation, not a claim that the incoming-hardware setup is ready.

## Components and ownership

| Component | Responsibility | Does not do |
| --- | --- | --- |
| `physical_camera_capture_workflow.py` | Original preparation/evidence joins, capabilities, settings, capture plan, readback, file ingestion and cached preview | Activate a camera, mint permission, pass an M1 stage |
| `physical_camera_configuration.py` | Existing typed capability, intent and readback contracts | Infer missing controls, qualify optics or verify pixels |
| `physical_native_camera_campaign.py` | Existing actual finite native preparation and scoped campaign | Turn successful diagnostics into a known physical outcome |
| `windows_camera_capture_ingest.py` | Existing original-buffer validation, chunked dataset, derived PNG and retained-content verification | Connect a device or prove camera/power shutdown |
| `physical_camera_acquisition_service.py` | Pending/current publication, reported settings fields and exact source/session/endpoint context | Accept browser evidence uploads or bypass native release |
| `arrival_wizard_service.py` | Explicit tickets, final result/log checks, opaque image cache and reserved export | Expose raw device paths or arbitrary robot commands |
| Browser and terminal UI | Display reported support, staged intent, readback and separately verified last frame | Manufacture hardware readiness from display state |

All paths above are relative to `software/src/rocell/application/`, except the
browser/terminal files under `software/src/rocell/ui/`.

## Internal integration sequence

`PhysicalCameraCaptureWorkflow` takes the exact workspace, original camera-store
parent, source/cell/session, reviewed `PhysicalCameraSelection`, and separate
probe/capture runtime registrations. Construction and cached reads do no I/O.

- `accept_probe(evidence, expected_preparation=..., expected_evidence_sha256=...)`
  derives capabilities from the exact retained probe. The independent digest
  must come from the real service/M1 retention boundary, not from the same
  untrusted JSON being offered for acceptance.
- `stage_settings(mode_choice_id, controls, expected_capabilities_sha256=...)`
  returns immutable intent. Controls use typed native integer units and reported
  capability flags/ranges/steps. Unsupported controls are not offered. Manual
  focus and aperture are physical adjustments, not invented electronic APIs.
- `capture_plan(budget=...)` returns the existing real campaign plan. It does
  not run that plan, create a native working directory or consume a permit.
- `accept_capture(...)` accepts the original capture preparation/evidence,
  exact settings epoch, Stop event and optional narrower retention deadline.
  Readback mismatch is retained without reading pixels. Clean matching readback
  reaches original-file validation, ingestion and independent verification.
- `staged_copy()` gives the application a pending publication candidate. Copies
  share a bounded one-use retention ledger, so discarding a candidate does not
  allow the same capture to be ingested again automatically.
- `invalidate()` removes current observations/preview but preserves diagnostics.
  `retained_diagnostics()` and `last_preview()` return detached cached data.

At the acquisition-service layer, the future admitted dispatcher supplies
`accept_retained_probe` or `stage_retained_capture`. It must retain original
native records and own the applicable M1 admission/uncertainty obligations.
These methods are **not HTTP endpoints** and do not authenticate their caller.

`pending_observation_result` builds a distinct
`rocell.wizard_retained_native_camera_data.v1` data result. It is deliberately
not the zero-device-effect `rocell.wizard_worker_result.v1` diagnostic schema:
an earlier native capture's effects must not be misreported as zero. The
reserved physical actions remain rejected by the old diagnostic dispatcher.

The future admitted dispatcher must retain/log that exact data result, then call
`ArrivalWizardService._publish_physical_camera_observation`. The latter rechecks
the original result, completion log, source, current reviewed endpoint and Stop
before publication. Only then may an opaque image ID name the cached PNG.
Unit tests enter this internal handoff explicitly; they do not claim a normal
public camera-activation action ran.

## Public settings action

`physical_camera_configuration` is now an implemented physical-mode,
**non-device-I/O** action rather than an unconditional reserved placeholder.

The current probe supplies the dynamic mode/control fields. Mode and operator
begin unselected; each electronic control defaults to **do not request a
change**. The displayed current value is a report, not a setting the app applies.
Prepare binds the exact probe/settings context; execute checks it again.
The result is validated against the unchanged registered diagnostic schema.
Only exact unredacted retention and successful completion logging publish the
new candidate. Staging withdraws the preceding image/readback. A later capture
must independently observe the requested settings.

The action accepts no native evidence document, output path, camera index,
arbitrary device endpoint or runtime-enabling option.

## Budgets, files and cancellation

Post-capture file retention has its own fixed **120-second** budget. An outer
deadline can only shorten it. It does not renew the native permit, extend the
native campaign or reopen a device. Source/Stop/deadline checks surround
synchronous validation and verification. Those existing file primitives cannot
forcibly interrupt a stalled filesystem call; a late return cannot publish.

Native inputs must already exist at the exact original paths:

```text
<original-camera-store>/
  native-camera-<attempt-id>/capture-<attempt-id>/frame-*.yuy2
  capture-datasets/ingest-<unique-id>/...
```

The workflow does not create the native input directories. Original parent/input
and dataset paths are guarded against replacement while files are checked and
retained. It creates only the fixed dataset child and new unique ingestion
directories. Original inputs/partial outputs are preserved after failure.

Preview is at most 640 pixels per edge, preserves exact aspect ratio, never
upscales, and has a 2 MiB bound. No silent crop is used for an unsupported aspect
ratio. At most one latest-frame preview is cached. The underlying dataset keeps
the original samples; the preview is a diagnostic conversion, not native sensor
colorimetry or calibrated board coordinates.

## Presentation and diagnostic export

The existing physical-camera UI contract is reused. Its new `CONTENT_VERIFIED`
state requires matching successful readback, both native and process cleanup
observations, and a separately bound verified frame. The readback's own
`frame_content_verified` stays false: settings comparison alone did not inspect
pixels. The separate last-frame record carries the content claim.

The preview says **last captured**, never live, connected or qualified. A newly
published image ID cannot display the previous cached object URL while its PNG
loads. Pending/historical/source-invalid/log-failed state cannot serve a new
current capture through the publication handoff.

Exports continue to use the user's chosen workspace folder:

`C:\Users\Jack\Desktop\robot-arm-build\software\runs\wizard-exports`

`attachment-native-camera-data.json` reserves the latest full data-chain
diagnostics before rotating ordinary results. It contains native evidence,
configuration, readback and dataset references, **not raw image samples**.
Source-invalid/redacted records are labeled historical; overflow fails rather
than truncating a document and claiming a complete export. Datasets remain in
their original assigned folder for separate investigation.

## Required next implementation, in order

1. Complete service-owned physical prerequisite intake/acceptance and exact
   original-store acquisition admission. File review and operator labels cannot
   substitute for the required physical observations or eight configuration
   dependencies.
2. Complete the reviewed native release and native-directory ownership join.
   Keep the present helper/source mismatch visible; do not rebuild or repin
   binaries merely to make an inspection green. Then connect the actual
   camera-only coordinator to the handoffs implemented here.
3. Exercise the complete admitted lifecycle with incapable native API fixtures,
   including exact output ownership, retained result and uncertain cleanup.
   Camera campaign v1 currently seals uncertainty; this increment does not
   invent a known seal or automatic stage pass.
4. Complete the arm's physical binding/campaign path. Existing Windows metadata
   correlation is not `ReviewedControllerBinding`: reviewed model, installed
   firmware, boot/reset behavior, serial profile, stage-10 safety and stage-11
   startup evidence are still needed. Join the existing fresh pre-open/pre-write
   resolver and one-shot feedback worker through a distinct physical admitted
   lifecycle. Never substitute the rehearsal child's synthetic identity.
5. Integrate installed calibration, remaining noncontact acceptance and handoff.
   Keyboard/phone contact execution remains a separate later release.

## Verification record

The focused production-workflow, public settings/publication and browser/terminal
tests are in:

- `software/tests/unit/test_physical_camera_capture_workflow.py`
- `software/tests/unit/test_physical_camera_capture_publication.py`
- `software/tests/unit/test_wizard_physical_camera_capture_ui.py`

They use actual file/PNG bytes and explicitly modeled native observations.
No received-hardware or clean-host qualification is claimed.

Integrated source fingerprint:
`236722bdee5e7414f6c3611e739acbe1be29ab92dee5503c15e9091789bb50b7`.

- **95 focused tests passed** (32.58 s): 35 workflow, 28 independent
  service/publication/export, 32 browser/terminal tests. The last group includes
  the actual tiny-file producer and pending-probe projection regression.
- **3,094 scoped regression tests passed**, eight slow tests deselected
  (408.76 s). Selection: Arrival/wizard, physical camera/intake/source, owned
  native camera, native runtime registration and arm controller modules under
  `software/tests/unit/`. This is not a claim that every repository test ran.
- Separately, the opt-in native-size dataset test passed (0.87 s):
  `test_camera_capture_dataset.py::test_full_b0477_native_frame_over_32mib_is_streamed_without_large_allocation`.
  It retained/verified/reconstructed 39,923,712 bytes at 5472×3648, with tracked
  peak allocation below 12 MiB. This measures the existing dataset storage
  component, not whole-app memory, real camera throughput or received media modes.
- Black, mypy on the four modified application/terminal modules, and Node's
  syntax check passed. Existing dependency typecheck informational notes are
  not new errors.
- A fresh, actual-source `ArrivalWizardService(mode="physical")` startup/read
  check confirmed the selected workspace export folder, no image, all fifteen
  physical stages pending, native actions held and settings awaiting a retained
  probe. No action, device inventory, M1 campaign or hardware operation was run.
- Offline wheel built with `--no-index --no-deps --no-build-isolation`.
  All **258** packaged Python/HTML/CSS/JS entries were byte-compared with source.
  Package: `software/runs/wizard-package-check-236722bd/rocell-0.1.0-py3-none-any.whl`,
  1,913,803 bytes, SHA-256
  `75293c92a4cca06fd169771a109c93d85f438fad24d3ac98d5c7addde58ba12a`.
  This is a packaging check, not a clean-host installation test.
- Existing probe/capture native executables retain their original SHA-256s
  (`e6072f26…9eb027a1` and `31d2f274…e940ae2f` respectively); no native rebuild,
  repinning, release change or controlled hardware-freeze edit was performed.

All older saved sessions/exports remain under their original source fingerprints; none was
rewritten or automatically reopened to create this evidence.

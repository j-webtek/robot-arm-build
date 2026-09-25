# Contained camera campaign integration

Status: implemented and verified as an incapable rehearsal, following the
`7b044827` helper-registration checkpoint. This is a bounded DEV-003/006/007/008
integration, not complete ticket acceptance, physical activation or a controlled
hardware-build change.

Current source fingerprint:
`05b56230bd00efcbf6664cefcca0fc6c3dc7ae4fb18a605080e10645d65da3f1`.
The source/configuration fingerprint excludes tests, documentation and runs.

## Intended operator path

At a due camera stage in Guided rehearsal, explicitly choose **Run contained
incapable camera-process campaign**. The shared service prepares source-derived scene
templates, binds a finite camera request to the current consumed M1 attempt,
runs one fixed incapable child under the existing Windows owned-process
supervisor, validates the native-shaped response, ingests its actual YUY2 bytes,
retains process/native/capture evidence, then displays a derived preview.
Assessment, independent-label review, restart verification and export stay
separate actions. A held run never publishes a current preview or advances a
physical stage. Existing in-process rehearsal remains available and distinctly
labeled; there is no automatic backend fallback.

## Composition

1. Root application worker: exact source/settings/identity/permit checks; bounded
   source-derived grayscale templates; unchanged `WindowsCameraWorkerClient`
   preparation/capture API; ingestion and retained coordinator receipt.
2. Windows transport: one additional closed incapable camera codec and fixed
   stdlib-only child inside `OwnedWindowsWorker`, plus
   `OwnedPreparedCameraRunner`. The current generic fixture codec is preserved.
   `PHYSICAL_UNQUALIFIED` remains rejected before process/backend admission.
3. Evidence: immutable bounded full process stdout/stderr, native request/receipt,
   source contract and ingest envelope, with exact source/attempt/settings
   binding. All raw pipe bytes are retained within the chosen caps, not silently
   truncated to make a nominal result fit.
4. Interface: cached `camera_process` projection in Guided rehearsal, separating
   observed process cleanup from synthetic camera cleanup and physical device
   qualification. Rendering never opens files or dispatches a process.

## Fixed fixture and limits

- The child launches only the installed base Python executable with isolated
  `-I -S`, a fixed pinned fixture script and a closed scenario. No native camera
  helper, device library, camera enumeration or serial API is imported/called.
- One to four pinned GRAY8 templates, each 2736 × 1824 = 4,990,464 bytes, come
  from the existing source-bound placemat renderer. The parent applies the
  existing synthetic luma offset; it is not a UVC control or autofocus setting.
- The child expands each template exactly 2× to 5472 × 3648 YUY2, stride 10,944,
  39,923,712 bytes/frame. This preserves nominal geometry but does not create
  native optical detail. Timestamps/counters retain incapable provenance.
- Native-shaped capture duration: 20 seconds. Owned process: 25-second run,
  2-second cleanup; parent camera campaign: 60 seconds including template
  preparation and retention. No deadline is renewed automatically.
- Application pipe caps: 32 KiB stdout + 8 KiB stderr, fitting complete base64
  retention plus metadata within the existing 128 KiB M1 evidence budget.
- Separate disk preflight covers templates, raw frames, retained frames,
  metadata/previews and margin. Fresh no-overwrite directories retain partial
  artifacts after failure; no automatic deletion, retry or replay.

## Exact admission and evidence

The coordinator owns ordered M1 leases and consumes one exact attempt. The
worker acknowledges that consumed permit once; it does not create another
permit or redeem the same one twice. Camera authorization checks the exact
prepared request. The owned runner's after-pins callback validates the same
acknowledged permit, source, request, registration, digest and deadline before
execution. This incapable composition is not qualified native child redemption.

Full retained evidence must distinguish: process never created; created but
not resumed; process/tree exit; native receipt validity and synthetic cleanup;
capture content verification; and final physical power/qualification, which
remain unknown/unqualified. Process death never proves device shutdown.
Raw/native failures remain available even when parsing or cleanup fails.

## Required tests before checkpoint

- Inert construction/status/preparation and closed command/payload validation.
- Generic owned fixture regression and physical registration denial.
- Exact request, template, output ancestry, source and permit mismatch rejection.
- Denied admission; cancellation before resume and during work; timeout;
  malformed response; identity mismatch; native/process cleanup uncertainty.
- Nominal actual contained child producing full-size bytes; strict native parser;
  dataset content/preview ingestion; full evidence retained before M1 sealing.
- Browser/terminal projection, public wizard action, assessment/review, original
  session reopening and verified assigned-folder exports.

The received Arducam and RoArm are still unavailable. Physical process/driver
qualification, release review, static-camera migration, received identities,
installed focus/coverage/calibration, arm startup/feedback and later motion/contact
authority remain separate required work.

## Verified implementation checkpoint

On the current source above:

- Selected non-slow regression: **1,666 passed, 3,311 deselected**, 112.64 seconds.
  This includes camera preparation/identity/ingestion, owned process and codec,
  retained evidence/reopening, stage cancellation, action/service/export and
  browser/terminal projection coverage. This is not the entire repository suite.
- Two actual Windows NTFS/process integration cases: **2 passed**, 200.39 seconds,
  with source equality before/after each case. The nominal case really collects
  and reviews the first four prerequisites, captures one full YUY2 fixture,
  retains the complete child output and native/ingest contracts, assesses it,
  explicitly reopens the original pending-review store, reviews it, then rejects
  a corrupted dataset on another read-only reopen. Worker replay and legacy
  camera fallback are prohibited. The cleanup-uncertain case retains the raw
  failed camera receipt, distinguishes successful process cleanup from modeled
  camera cleanup failure, quarantines and exposes no current preview or retry.
- Actual one- and four-frame child processes are also covered in the process
  runner tests. A four-frame complete M1 service workflow is not claimed here.
  Identity-mismatch/malformed-result full-M1 cases are implemented but were not
  executed in this checkpoint; their process/evidence paths are covered below
  that integration layer. The slow tests are explicitly marked `slow`.
- Ten changed production modules pass mypy. Selected Black and JavaScript syntax
  checks pass. Independent review found and closed a Stop-during-final-storage-
  acquisition publication gap; four pure tests cover both camera stages and
  normal controls. These pure tests do not substitute for the real-storage cases.
- Startup `-Check` performs zero operations, shows both physical devices as
  `NOT_CONNECTED`, no camera process result and fifteen `PHYSICAL_PENDING`
  stages. The assigned export folder is `software/runs/wizard-exports`.
- The six-contract foundation remains activation-false. Build alignment remains
  `ALIGNED_CAMERA_HOLD_CONTACT_BLOCKED`, with no errors or change to Freeze 011.
- Offline wheel build, no installation:
  `software/runs/wizard-package-check-05b56230/rocell-0.1.0-py3-none-any.whl`,
  1,573,845 bytes, SHA-256
  `aedc10487c89de7a15aa08048a9fc3a27480eb511eac271883ba43df3df27865`.
  Eleven archive entries match the current application, runner and UI sources.
  This is a development packaging check, not a qualified arrival installer.

Counts from overlapping selections are not additive. Earlier development
sources `c3c9ce47` and `57ea64b2` and their artifacts remain historical; they are
not relabeled as the final corrected source. Interrupted broad/duplicate test
selections are not included as passes. No real camera helper, OS device
inventory, camera/serial endpoint, power, motion or contact was exercised.
This increment has automated UI rendering/API checks, not fresh visual browser QA.

Reproduce the selected lane from the workspace root:

```powershell
.\.venv\Scripts\python.exe -m pytest software/tests/unit -q -m 'not slow' `
  -k '(arrival_wizard or wizard_actions or wizard_worker or wizard_diagnostic or wizard_device_selection or wizard_native_camera or wizard_camera_helper or windows_camera_preparation or windows_camera_worker or windows_camera_identity or windows_camera_capture_ingest or wizard_reference_stage_integration or owned_camera or owned_worker_process or wizard_feedback_stage_integration) and not wizard_owned_camera_integration'
```

For the actual-store cases, select the nominal test and the
`[cleanup-uncertain]` test from
`tests/unit/test_wizard_owned_camera_integration.py`, without `-m 'not slow'`.
Allow several minutes and keep production source unchanged for the entire run.
Do not run multiple expensive NTFS commissioning sequences concurrently.

The normal public-API smoke script is
`software/scripts/wizard_owned_camera_smoke.py`. It creates a fresh explicit
incapable rehearsal, performs no backend fallback, and attempts a verified
diagnostic export on both successful and held outcomes. See the
[presentation/smoke guide](WIZARD_OWNED_CAMERA_PROCESS_PRESENTATION.md).

### Actual public wizard API and assigned-folder export

The normal public smoke also completed on the final source, without service
doubles or a copied store. It initialized a new rehearsal, collected/assessed/
reviewed the first four prerequisites, prepared settings, captured one frame
through the contained backend, assessed/reviewed stage five and exported.
All 19 explicitly prepared actions completed successfully with completion logs.
Stage six remains pending; all fifteen physical stages remain pending.
The script shut the service down in its finalizer; no server was left running.

```powershell
.\.venv\Scripts\python.exe software/scripts/wizard_owned_camera_smoke.py `
  --frame-count 1 --fault none --assess-and-review `
  --expected-source-sha256 05b56230bd00efcbf6664cefcca0fc6c3dc7ae4fb18a605080e10645d65da3f1
```

- Launch: `wizard-5385d173e8b94621ae73d94f6355f8fc`.
- Original rehearsal: `rehearsal-7750003c2143474fb797c67c851e7ee1`, under
  `software/runs/wizard-rehearsal/wizard-5385d173e8b94621ae73d94f6355f8fc`.
- Campaign: `attempt-8cfbda8ba282468f8322b4e6034fd1c1`.
- Full private campaign evidence SHA-256:
  `b7aef67fced59cda350b3991346e356c97af1f7b5e26ee75909180da5386d4eb`.
  The process succeeded with confirmed tree exit; the synthetic native receipt
  was `OK`. The retained child stdout is 1,951 bytes. Dataset logical bytes are
  40,108,288: one 39,923,712-byte YUY2 frame plus its derived preview, not an
  optical-resolution or camera-driver qualification claim.
- Verified diagnostic export:
  [wizard-20260908T035318678230Z-fff25638f167473b90beb662c48f7673](../runs/wizard-exports/wizard-20260908T035318678230Z-fff25638f167473b90beb662c48f7673/README.md).
  Independent verification returned `VERIFIED_DIAGNOSTIC_EXPORT`: eleven payload
  files, 212,615 payload bytes, authority `NONE`, manifest SHA-256
  `8b9bab1580e61f3eb8e68e35f74b59e4a1cb85b3aa49b22bf9aea44317f8c2a7`.
- The camera result attachment is 20,742 bytes, SHA-256
  `8435aa6a01335ddd22ebe3c21cbcc6e2427c36ba68898a1dd0ab580bf918ee50`.
  It includes the safe process/native/capture projection and exact M1 evidence
  hash. It does not silently copy private raw child bytes, the raw frame dataset
  or the complete M1 store into an ordinary diagnostic export.

Earlier development exports/wheels and temporary failed/interrupted test
artifacts were preserved. No hardware package, driver, firmware, permission,
device configuration, movement command or contact limit was changed.

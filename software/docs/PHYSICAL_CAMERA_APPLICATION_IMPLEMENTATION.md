# Physical camera application integration work record

Date: 2026-09-08. Status: application planning and held-native join implemented
and checked; verification and remaining joins are recorded below. The complete developer
playbook goal remains active; this file records the next application join, not
permission to connect hardware or a replacement definition of done.

## Plan before implementation

The previous [native capture checkpoint](NATIVE_CAPTURE_CONNECTION_IMPLEMENTATION.md)
provides the verified native/Python components and identifies the remaining
joins. Implement these together in the existing application:

1. Add a distinct camera-only physical diagnostic coordinator/storage domain.
   Reuse the exact-permit, one-use consumption, scoped revalidation, immutable
   evidence and qualified NTFS machinery. Preserve the source-only domain's
   NO_DEVICE_IO restriction and the rehearsal domain's identity. The new domain
   admits only bounded camera campaigns at mode/controls or frame-freshness
   stages, with CELL then SESSION then CAMERA ownership, retained evidence and
   scoped callbacks. It admits no energy envelope, arm lease or motion action.
2. Compose the actual native probe/capture preparation and owned runner into a
   scoped camera campaign. Bind reviewed endpoint, purpose-specific runtime,
   logical intent, output and source to one plan. Retain the returned original
   evidence even on holds. The native runner remains physically unavailable
   until independent release qualification; no test Boolean enables it.
3. Add distinct physical probe-derived capabilities, staged mode/control intent
   and capture readback verification. Do not relabel rehearsal reports, infer
   unavailable controls or assume the probe/capture helper builds are identical.
4. Join a cached physical-camera acquisition service/view to ArrivalWizardService
   and the existing Camera card/terminal. Explicit planning can explain missing
   prerequisites without opening hardware. Probe/capture actions remain held
   until their physical requirements are met. Status and action preview perform
   no device operations; existing source fingerprint file reads remain allowed.
5. Make current retained camera failures actionable in the UI and exported
   diagnostic attachments. Use a fixed-code projection of verified retained
   evidence, never arbitrary backend error messages or rejected raw device data.
   A reported readback rejection is not a validated observation of control state.
6. Test new domain separation/admission, actual qualified storage joins with
   clearly labeled test workers, pure evidence/configuration, public service
   planning/invalidation, browser/terminal projections and diagnostic exports.
   Execute no physical camera helper, metadata DLL/serial reader, arm power,
   motion or contact. Keep all historical stores/builds/catalogs intact.

## Ownership and shared interface

- Root: coordinator/storage/native campaign, application service/actions, final
  integration and this record.
- Native agent: new `physical_camera_configuration.py`, its tests and contract.
- UI agent: existing browser/terminal renderers, presentation tests and operator
  notes. No independent web application or renderer-side authorization.
- Diagnostics agent: new pure `camera_fault_diagnostics.py`, tests and its
  fixed safe projection. Existing retained evidence schemas stay unchanged.

The cached top-level `physical_camera` projection uses
`rocell.wizard_physical_camera.v1`: status, source/session binding, reviewed
endpoint hashes, separate probe/capture runtimes, nullable prepared plan,
capabilities/intent/readback, last-frame provenance, publication, fault and
fixed blockers. Connected/qualified/physical-authority remain false for this
held development composition. A future finite preview must say "last captured
frame—not live" and bind source, endpoint, settings, native frame, capture
evidence, manifest and derived preview hashes. Failed publication or drift
withholds its current image token, not its historical evidence.

## Acceptance and remaining boundaries

This increment must prove real existing-code joins, not parser-only success.
Missing release qualification must refuse native ownership before process
creation or file/sample access. One-shot admission must revalidate the original
scope, never refresh a permit to hide slow persistence. Camera capture's
seventeen-second minimum owned lifetime and five-second admission are unchanged.
Actual dataset ingestion must eventually have an explicit compatible budget;
the current 120-second ingestion default cannot silently fit a 30-second permit.

Received-unit identity, supported modes/USB bandwidth, driver shutdown, focus,
coverage, physical power conditions and installed calibration remain unverified.
Source-only reports do not pass those stages. Hardware qualification is not a
substitute for unfinished software integration, and camera-only permission may
never authorize the arm.

## Implemented application path

The public action is **Camera → Prepare physical camera acquisition plan** in
physical mode. It is deliberately a planning action, not a disguised connect
button. It requires no attached devices and permits inspection of the missing
requirements before an operator attempts hardware onboarding.

1. `ArrivalWizardService.prepare_action` validates the closed input fields,
   current source and revision. It derives the entire planning context on the
   server and binds its hash to an opaque one-shot ticket. A browser cannot
   supply a device path, output folder, selected-identity hash or plan hash.
2. `PhysicalCameraAcquisitionService.preview_plan` takes one detached current
   enrollment snapshot. Missing metadata remains an explicit hold; a present
   but invalid identity binding is rejected. Planning creates no directories,
   M1 session, owner, process or device operation. Source-file checks already
   performed by Arrival remain distinct from this pure preparation.
3. When a current reviewed endpoint exists, `PhysicalCameraSelection` retains
   the original UTF-8 metadata review inside a separately hashed canonical
   ASCII identity document. This preserves Unicode endpoint/reviewer bindings
   and matches the camera M1 identity codec without rewriting old evidence.
4. Probe planning composes the actual `PhysicalNativeCameraCampaign`, including
   its native preparation checks, separate runtime candidate, output policy
   and reserved camera-only cell/session IDs. The full campaign plan and its
   hash are retained inside the wizard intent. Capture planning names the
   missing retained probe and reviewed settings; it does not guess a mode or
   create a synthetic physical capture plan.
5. Explicit execution rederives the original context, checks cancellation and
   retains the complete intent in a normal bounded diagnostic result. Only
   after full-result retention and completion logging does the cached view
   publish that **plan/report** as current. Camera status remains HELD,
   connected/qualified/authority stay false, and last-frame remains null.
6. Stop, source drift, new inventory/helper/native review, failed logging or
   failed publication withdraw the current plan. Private historical intent and
   any bounded diagnostic result remain available. A duplicate ticket returns
   the original operation; there is no automatic dispatch or retry.
7. Diagnostic redaction is checked before publication. If redaction changes a
   bound intent, the operation fails with `BOUND_CAMERA_INTENT_REDACTED`, keeps
   a clearly redacted report and the original result hash, and publishes no
   current plan. A sanitized document is not misrepresented as the original
   bytes named by the old hash. Its export can be valid as a redacted
   diagnostic without proving the exact original intent.

The separate pure physical capability/configuration/readback layer is complete
at its contract boundary; see [its contract](PHYSICAL_CAMERA_CONFIGURATION.md).
It accepts retained physical native observations with independent trusted
references, not rehearsal reports. It binds supported mode choices, supported
control ranges and settings epochs without applying settings or verifying
pixels. The wizard does **not** yet admit those observations into its camera
M1 session or enable the physical configuration action.

## Camera-only storage/native integration

The new `PhysicalCameraAcquisitionCoordinator` and
`M1PhysicalCameraPersistence` use a distinct composition/source binding,
`physical-camera-records` directory and `rocell.m1_physical_camera_record.v1`
schema. They reuse the existing immutable journal, exact-permit and Windows
lease implementations. Old rehearsal and source-only record domains are not
rewritten or relaxed.

Only bounded camera actions at the mode/controls or frame-freshness stages are
registered. Admission requires CELL → SESSION → CAMERA ownership, exact
selected identity, scoped execution and retained evidence. Arm resources,
actuator energy envelopes, power changes, motion and contact are rejected.
Power remains UNKNOWN, not inferred off from a camera-only test.

The [native campaign implementation](PHYSICAL_NATIVE_CAMERA_CAMPAIGN.md)
connects the actual consumed M1 scope to the unchanged owned native runner. An
actual qualified NTFS test traverses storage → camera coordinator → consumed
scope → real held runner → immutable evidence → original-store reopening.
Its predecessor-stage records are explicitly incapable test fixtures, not
physical qualification. The independent native hold fires before ownership,
file pinning, process launch or device calls. The held attempt is retained as
SEALED_UNCERTAIN/quarantined; it does not pass a stage or become retryable.

## Actionable camera faults

`camera_fault_diagnostics.py` verifies the original retained incapable camera
evidence and projects a fixed allowlisted explanation into the commissioning
view and named diagnostic result step. In particular, the earlier settings
drift case now explains that the caller rejected exact requested-control
readback. This is not promoted to a validated observation of a real control.

The service preserves the original evidence hash and safe explanation after
late Stop, source changes or publication failures. Exports retain it with the
full operation result. Browser/terminal cards use closed known fields, not an
arbitrary recursive scan of raw errors. Quarantine, original attempts and
no-retry/no-clear permissions are unchanged. See
[fault diagnostics](CAMERA_FAULT_DIAGNOSTICS.md) and
[presentation rules](WIZARD_PHYSICAL_CAMERA_PRESENTATION.md).

## Executed verification

Current frozen production source:
`cc22805071ddfa52c83a45ebc52ced95367e49877e52eb1a92890466135f1392`.
Documentation, tests, scripts and generated runs are outside this production
source fingerprint. No native source/build/catalog or controlled hardware
configuration was edited in this increment.

- New root physical-service lane: **28 passed**, including actual public
  tickets, current Unicode endpoint → native campaign preparation, source/
  Stop/log failure, redaction rejection, duplicate execution and real exports.
  Combined with existing native integration and new late-fault tests:
  **56 passed in 5.60 seconds**.
- Physical settings: 41 focused tests; selection: 27 focused tests; camera-only
  core: 40 focused tests. Six separate actual qualified-NTFS camera-domain
  storage tests passed in 70.28 seconds. Their injected predecessors/workers
  are explicitly test fixtures.
- Native campaign: 45 fast tests, plus **one actual M1/native-held-runner test
  passed in 27.15 seconds**. This does not execute the camera-capable binary.
- UI agent: **415 tests passed in 45.89 seconds**, with real pure physical
  producers, original safe fault projections, browser transport and terminal
  output. A later reviewed Unicode service/native plan cross-check also passed.
- Late-fault Arrival/export integration: **3 focused / 38 combined passed**.
  These tests use explicitly injected worker/coordinator/M1 fixtures through
  the actual service and diagnostic exporter, not physical observations.
- Root focused cross-module lane: 211 passed before the additional redaction
  regression; mypy seven shared/root modules and later two changed modules
  passed. Black and JavaScript syntax checks passed.

Counts overlap; they are separate lanes, not a summed unique-test total.

The broad current-source non-slow selection completed with **3,014 passed,
one failed and 3,355 deselected in 422.04 seconds**. The sole failure was the
closed expected action-list assertion in `test_wizard_actions.py`, which had
not yet listed the four new camera actions. Only that expected list was
updated; no production code, safety gate or registry validation was relaxed.
The entire action module plus physical service module then passed:
**88 passed in 1.69 seconds**. The seven-minute broad lane was not rerun after
this test-only change; do not describe it as an all-green single invocation.

The broad selection was:

```powershell
.\.venv\Scripts\python.exe -m pytest software/tests/unit -m 'not slow' -k 'arrival or wizard or native_camera or windows_camera or capture_ingest or camera_receipt_metadata or controller_metadata or arm_controller_resolution or owned_native or arm_feedback or arm_owned or owned_arm or consumed_commissioning_scope or commissioning_coordinator or rehearsal_feedback or rehearsal_reference or scoped_rehearsal_dispatch or physical_camera or commissioning_camera or camera_fault' -q
```

Wheel assembly passed without dependency resolution or downloads. All **247**
workspace Python/HTML/CSS/JS package entries matched the wheel byte-for-byte.
Artifact: `software/runs/wizard-package-check-cc228050/rocell-0.1.0-py3-none-any.whl`,
1,768,661 bytes; SHA-256
`a099e34f39f8719b763c7dfb15a236b3af7bf5f9b7f2dec0a5349462f0345bc6`.
It is a development package, not a qualified hardware release. Final Black
checks of ten root-edited files and `node --check` of the browser script passed.

### Fresh public physical-mode plan/export check

Run from the workspace root with the expected source identity:

```powershell
.\.venv\Scripts\python.exe software/scripts/wizard_physical_camera_plan_smoke.py --expected-source-sha256 cc22805071ddfa52c83a45ebc52ced95367e49877e52eb1a92890466135f1392
```

This finite script uses the actual service without provider/test injection. It
performs exactly three public actions: prepare/retain a probe intent,
prepare/retain a capture intent, then export. It never performs an inventory,
creates a camera M1 session, opens a helper/device, or advances a physical stage.

Executed successfully on 2026-09-08:

- Launch: `wizard-e72523ec82224ece86a4c85861b0e7b3`.
- Probe intent SHA-256:
  `44f0ea92ec9b9a9e4ebcc52b9436bf0e5d77f24cd1d0cc37829a0c5b6994caea`.
- Capture intent SHA-256:
  `cc6c9b13c9ddfdcc20cd611e53657d14a1651b57ddcbd06a93bb7064608d7e52`.
- Export: `software/runs/wizard-exports/wizard-20260908T101358684458Z-6941463c8e79460986d29d7f880839aa`.
  Six files, 75,441 bytes. Both full plan attachments rehashed correctly.
  Export receipt manifest binding:
  `3f37664c3e3c0c5ae376988eee46decc84a78cd423ef0fe8b576d382dcf20fad`.
- Camera and arm remained NOT_CONNECTED; all 15 physical stages remained
  PHYSICAL_PENDING; no last-frame image or hardware qualification appeared.

A separate live local browser startup loaded the current service and displayed
the matching source, purchased camera profile, disconnected arm/camera and all
15 pending stages. This was a read-only startup/accessibility check, not a
camera capture or a completed interactive physical setup.

### Fresh contained camera-fault/export check

```powershell
.\.venv\Scripts\python.exe software/scripts/wizard_owned_camera_smoke.py --probe-and-configure --fault control-readback-drift --expected-source-sha256 cc22805071ddfa52c83a45ebc52ced95367e49877e52eb1a92890466135f1392
```

The current-source run used actual public Arrival tickets, the real rehearsal
service, qualified storage, retained modeled capability probe/configuration,
and the real contained incapable camera process. No provider/test doubles were
injected by the script. Its child supplies explicitly synthetic native-format
records; neither camera nor serial hardware is accessed.

- **19 actions; script exit 0**, meaning the expected fault and its diagnostic
  retention/export were verified. The camera campaign itself correctly FAILED.
- Launch: `wizard-c3d7710ddec74f14ac222bd637eacfbc`.
- Rehearsal session: `rehearsal-515a45fb74ed4d32a95580403165f44d`.
- Original attempt: `attempt-e0e067e96c5f4a6ca8489100db5c6c11`.
- Original retained evidence SHA-256:
  `725a4e389811cf49a630d259b3a62c077e3e75c6d3d98817125f804da1730a50`.
- Safe explanation: `CONTROL_READBACK_MISMATCH_REPORTED`, reported code
  `INVALID_CAMERA_CONTRACT`, basis `RETAINED_CALLER_ERROR_EXACT_MATCH`.
  The rejected packet remains unverified; no real control observation is claimed.
- Stage five stayed `WAITING_OPERATOR`, session HELD/quarantined, and all 15
  physical stages stayed pending. Retry, automatic retry and quarantine clearing
  stayed false. No assessment/review acceptance followed the fault.
- Export: `software/runs/wizard-exports/wizard-20260908T102323999459Z-8d3f74f418fd4edebab7185c3754344f`.
  Eleven payload files, 229,492 payload bytes; verified manifest binding
  `c0335fe2e1bff1e8999a0171a2827929578e4ea716550307b82d60810d0f067c`.
  The full failed-operation attachment and the report snapshot contained the
  identical safe diagnostic and original evidence hash. This is now an explicit
  smoke-script assertion, not merely a visually inspected log message.

## Historical next-join queue at this checkpoint

The later [camera data workflow increment](PHYSICAL_CAMERA_CAPTURE_WORKFLOW.md)
implements the file-validation/ingestion and retained-data/settings/UI portions
of items 4–5 below. Original-store initialization/readback also progressed in
the linked setup/source-workflow checkpoints. Native input-directory ownership,
admitted physical dispatch and qualification are still unfinished. Use the newer
handoff's ordered list for current implementation work; this queue is retained
to explain this older checkpoint's limits.

1. Add service-owned intake and review of the camera domain's actual physical
   prerequisites. Do not copy fixture predecessor receipts or trust browser
   checkboxes as independent hardware evidence. Bind the current enrollment,
   purpose-specific runtime file review, source and all configuration epochs.
2. Join explicit physical M1 initialization/admission to the wizard. Keep the
   pure planned namespace distinct from an actually created/verified session.
   The capability projection's session must use that camera-domain session;
   its metadata selection must preserve the separate launch-session lineage.
3. Qualify purpose-specific native release, owner lifetime/cleanup and driver
   behavior before changing any held action. Existing fixed development hashes
   are references, not current-file checks or qualification certificates.
4. Add output-directory ownership/pinning and a separately bounded physical
   capture-byte validation/ingestion step. Bind original native bytes,
   settings, endpoint, M1 evidence and derived preview. Do not count metadata
   validation as pixel verification or fit 120-second ingestion into a
   30-second permit by silently extending/refreshing it.
5. Connect retained physical probe → supported settings intent → explicit
   bounded capture → exact readback to the UI. Publish only after durable
   retention and current-source/context checks; show a last captured frame,
   never claim a live stream without implementing one.
6. Complete the parallel physical arm service/pre-open/pre-write resolver,
   safe startup evidence, installed calibration and the final noncontact/
   handoff rehearsal stages. Camera authorization must never grant arm power,
   movement, keypress or phone-contact authority.

These are unfinished software joins as well as received-hardware verification
requirements. The presence of tested components does not mean that plugging
in the camera and arm will yet complete the full playbook.

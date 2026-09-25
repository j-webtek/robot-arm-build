# Local onboarding workbench

The first application shell joins the existing software checks and camera/arm
rehearsals to one local browser or terminal interface. It is a diagnostic
workbench, **not a released physical commissioning or robot execution system**.

The [completion matrix](ONBOARDING_APPLICATION_COMPLETION_MATRIX.md) distinguishes
the remaining camera/arm production integration from received-hardware testing.

## Current entry points — 2026-09-12

Use the concise [operator guide](UI_OPERATOR_GUIDE.md) for startup, component
navigation, explicit control, result review, draft editing and exports. The
[UI acceptance handoff](UI_APPLICATION_HANDOFF.md) records the current UI audit;
it does not release the pending physical connection/calibration work.

The new [Control Center](UI_CONTROL_CENTER_HANDOFF.md) searches all registered
actions and opens their existing original forms, with exact hold reasons and no
automatic execution. The broader [operator UI plan](UI_CONTROL_APPLICATION_PLAN.md)
records the editing, guidance, and completed UI acceptance work.
The new [Activity & results workspace](UI_ACTIVITY_HANDOFF.md) exposes the full
retained launch history, explicit result reads, retention limits and recovery
guidance. Navigating either directory never runs or replays a hardware action.
Ordinary [in-tab form drafts](UI_FORM_DRAFTS_HANDOFF.md) now survive unchanged
setup rerenders. Dependent choices require matching reselection and explicit
restoration; identity labels, confirmations and device selections are not saved.

Start with [Launch](#launch) and [What to do in the interface](#what-to-do-in-the-interface),
not the implementation history below. Use rehearsal mode for the unassembled
build. The assigned export parent remains `software/runs/wizard-exports`.

The public [settings-capture workflow](CAMERA_CONFIGURATION_WIZARD_HANDOFF.md)
now exists: eligible original camera setup can stage reported settings, request
one explicitly admitted verification frame and export the exact attempt. It is
not continuous video, automatic connection, stage-6 freshness qualification or
arm control. Missing genuine prerequisites keep the physical action held.

Current startup work is tracked in the
[six-step execution plan](PRE_ARM_CALIBRATION_EXECUTION_PLAN.md) and
[P1 existing-root work order](STORAGE_EXISTING_ROOT_OBSERVATION_WORKORDER.md).
The latter records 796 earlier selected passing checks. Complete-history run 07's
test passes after a fixture correction, but concurrent arm/UI edits caused its
final source comparison to fail. Fixed-source acceptance remains open; the later
144-case restart/export/UI result is tracked separately. These results do not
qualify the received camera or authorize arm operation.

Reopening original setup and importing a readable diagnostic export are separate
operations. Neither restores a live camera owner, settings consent or a capture
ticket. Export any needed current-launch attempt before closing; after restart,
explicitly discover/select original setup and reacquire eligible current metadata.
Do not initialize a replacement merely to continue an existing history.

## Historical implementation checkpoints

The entries below record what existed at each earlier checkpoint. Statements
such as "not yet integrated" describe that entry's date, not the current status
of every later component. Use the current links above for unresolved work.

An earlier internal increment was [stage-5 settings readback](CAMERA_SETTINGS_READBACK_WORKORDER.md).
It separates configuration verification from later frame freshness using the
existing controller. This is not yet a new public capture button: substantive
original admission, capacity, UI/export and policy assessment remain pending.

The preceding [original-bound camera probe](CAMERA_PROBE_PUBLIC_WIZARD_CHECKPOINT.md)
adds a gated one-use capability probe, original admission/capacity checks,
completion-backed result publication, status card and dedicated attempt export.
It is not a live stream or a camera/arm Connect release. Capture, physical stage
acceptance, calibration and RoArm connection still require software integration
and received-hardware verification. Read the linked operator procedure first.

The preceding [probe preparation wizard](CAMERA_PROBE_SETUP_WIZARD_CHECKPOINT.md)
adds explicit file-only Prepare/Review forms, current logged metadata checks and
a separate complete preparation/failed-attempt export in Diagnostics. The camera
page shows hashes and attempt status without opening a device. Current admission,
physical Connect/preview and arm startup remain software work; hardware arrival
by itself will not finish those software connections.

The preceding [v2 camera application handoff](CAMERA_ACTIVATION_HANDOFF_WORKORDER.md)
adds original paired-result readback and the internal probe/settings/capture/
preview lifecycle. Tests use modeled native effects; public connection controls
still require original admission and UI/export integration. Diagnostics use the
confirmed workspace export folder; startup remains disconnected.

The preceding [installed v2 camera runtime component](CAMERA_ACTIVATION_RUNTIME_WORKORDER.md#installed-runtime-checkpoint)
adds purpose-specific builds and enforced software-file verification. It does not
yet enable public camera connection/preview. A status-view issue was also fixed:
checking Windows availability no longer starts an OS-version shell subprocess.

The preceding [v2 internal campaign component](CAMERA_ACTIVATION_CAMPAIGN_CHECKPOINT.md)
adds scoped execution, fresh output-directory ownership and preserved interruption
diagnostics. It does not enable public physical connection or preview controls;
runtime approval and original acquisition/UI integration remain unfinished.

The preceding [v2 diagnostic-storage component](CAMERA_ACTIVATION_STORAGE_CHECKPOINT.md)
preserves large camera failure records and unknown counters through the core and
original local storage. No physical Connect/preview control is enabled by this
change; the admitted acquisition/runtime/UI integration remains unfinished.

The preceding [v2 process-supervisor component](CAMERA_ACTIVATION_SUPERVISOR_CHECKPOINT.md)
handles bounded startup, Stop, results and cleanup internally. No new physical
Connect/preview button is enabled: its admitted runtime and original-store/UI
join is still unfinished, and both launcher modes continue to start disconnected.

The preceding [v2 run-record/accounting component](CAMERA_ACTIVATION_EVIDENCE_CHECKPOINT.md)
improves retained failure diagnostics without interpreting missing data as success.
It has not yet been connected to physical acquisition or the public UI/export flow.

The [v2 parent/process connection machinery](CAMERA_ACTIVATION_PARENT_CHECKPOINT.md)
now has installed preparation/handshake support and real contained-process tests
using an incapable helper. Physical connection/UI dispatch is still unfinished;
starting either wizard mode does not connect hardware automatically.

The latest [installed v2 camera codecs](CAMERA_ACTIVATION_RESULT_CHECKPOINT.md)
improve connection-result verification but do not add an executable camera or
arm action yet. Launch remains inert; the confirmed export folder is unchanged.

The latest [entry/cleanup checkpoint](CAMERA_ENTRY_CLEANUP_CHECKPOINT.md) fixes
operator labels containing spaces in **Continue to camera setup**. Enter a
trimmed label of at most 64 UTF-8 bytes; this is a procedural label, not a login.
Other Setup actions retain their existing portable-ID restrictions. Camera entry
still opens no device, and physical acquisition remains unfinished.

For first use, go directly to [Launch](#launch),
[What to do in the interface](#what-to-do-in-the-interface), or
[Logs and investigation](#logs-and-investigation). Use the default rehearsal
mode without hardware. The confirmed export parent is
`C:\Users\Jack\Desktop\robot-arm-build\software\runs\wizard-exports`.
The implementation history below is for developer traceability, not a list of
steps an operator must perform on every launch.

Earlier verified increment: [AFTER_RECONNECT](USB_AFTER_RECONNECT_IMPLEMENTATION.md).
Fresh public run 06 passed in 1,062.33s, including all five service actions,
same-original Refresh, eleven retained roles/seven events, full v5 export/restore
and fresh original reopening without replay. Earlier failures remain preserved.
Hardware and process observations were modeled; this is software integration
acceptance, not physical camera/arm qualification. The
[operator guide](USB_BASELINE_OPERATOR_GUIDE.md) explains the explicit sequence.

The [AFTER_REBOOT successor](USB_AFTER_REBOOT_IMPLEMENTATION.md) now has five
explicit actions, original readback/collector, new-launch Setup joins, both
interface cards and a complete v6 export. Full public NTFS v13 run 07 passed with
modeled hardware/process observations. Physical connection,
capture, calibration and arm startup remain unfinished as listed in the matrix.

The [complete identity review](USB_COMPLETE_SERIES_IMPLEMENTATION.md) adds two
file-only controls after the four original USB phases: **Assess all four original
USB phases**, then **Review final camera-identity assessment**. Read the exact
assessment hash and any failed checks; use a distinct procedural reviewer label
and an explicit decision (default: reject). A final accepted identity is not
permission to capture images or move the robot. Partial attempts are export-only.
Exports include original subjects and attempts through the ordinary v7 USB bundle
in the confirmed folder. The modeled service/UI assess → review → export flow
and selected public-contract regressions pass. Full fresh public acceptance also
passes (2,090.53 s), including original storage, export/restore and reopening
without replay; hardware/process observations are modeled. The next stage-5
entry now includes the tested original v15 reader, one-shot Setup action, both
interfaces and complete entry export. The modeled public entry/UI/export path
passes; fresh public NTFS entry, both exports and fresh-app reopen now pass in
run 03 (2,230.09 s). Use
**Continue to camera setup** only after the current original identity review:
its form and preview are inert, and execution records `WAITING_OPERATOR`, not
PASS or a connection. Partial attempts remain inspectable/exportable without
automatic retry. General export includes `attachment-camera-mode-entry.json`;
full historical USB evidence still uses its separately labeled export action.
The [entry storage checkpoint](CAMERA_ENTRY_STORAGE_CHECKPOINT.md) records the
real pending-stage integration fix, passing focused tests and the successful
fresh full acceptance run. This is not a camera connection or activation test.
See the [developer work order](CAMERA_IDENTITY_TO_ACQUISITION_WORKORDER.md)
for verification scope and the still-unfinished camera/arm production joins.

Previous verified increment: [physical USB absence](USB_ABSENCE_PHASE_IMPLEMENTATION.md).
Five separate actions guide unplug reporting, boot-scope review, boot collection,
exact presence-query review and one explicit collection. Closed original-state
checks control availability; neither a page load nor an export starts a query.
The service/UI and v4 export have scoped test coverage and a passing full
real-storage public test with modeled observations, complete restore and fresh
reopening/no replay. Its earlier failed original remains preserved. Complete
reconnect qualification and received-hardware connection are not yet verified.

The [USB reconnect trial workflow](USB_RECONNECT_WIZARD_IMPLEMENTATION.md) adds
**Declare USB qualification trial** after eligible original identity metadata
or a clean completed baseline. Supply cable/port labels and explicitly confirm
the file-only action. The separate panel shows the original plan and partial
save failures; its presence does not mean any trial phase was collected. Export
retains the full plan and original events in the assigned folder. Device-phase
collection and qualification remain unfinished; the earlier standalone baseline
cannot be retroactively relabeled as trial evidence.

The [original USB baseline workflow](USB_IDENTITY_WIZARD_DISPATCH_WORKORDER.md)
adds four separate Camera actions: fixed-file inspection, exact target/policy
review, one controlled query and complete evidence export. Only the explicitly
admitted collection queries USB; startup, page viewing and review do not.
The export parent is `software/runs/wizard-exports`. USB baseline evidence does
not release camera capture, qualify reconnect/reboot stability or connect the
arm. The work order records full-history integration tests and remaining work.

The [camera identity workflow](CAMERA_IDENTITY_ONBOARDING_IMPLEMENTATION.md)
now joins reviewed helper/native metadata to original collection, separate
BLOCKED review, restart and a complete dedicated export. It guides users to
existing metadata forms without executing them. Driver v2 is a separately built,
unqualified development artifact; physical USB/serial/stability qualification
and camera activation remain unfinished.

The [received-camera wizard](RECEIVED_CAMERA_ONBOARDING_IMPLEMENTATION.md) adds
explicit blank/revised drafts, original attachments and structured inspection,
exact-subject review, restart and a separate complete metadata bundle. The
Camera page's top next-step links navigate to eligible forms without executing
them. Camera receipt PASS does not connect a camera or release the robot.

The latest [static-camera onboarding workflow](STATIC_CAMERA_ONBOARDING_IMPLEMENTATION.md)
joins actual controlled design files to original collection, distinct review
and a separate received-camera entry action. The Camera panel distinguishes
design acceptance from received measurements and installation qualification.
No hardware connection or motion is enabled by these steps. The guide includes
the operator sequence, developer map, export contract and remaining work.

The preceding [source-stage reassessment workflow](SOURCE_STAGE_ADMISSION_IMPLEMENTATION.md)
adds fresh software/ownership checks, explicit isolation originals, exact review
and a separate stage-2 entry action. UNKNOWN remains blocked; accepting source
prerequisites never connects the camera or starts the arm. The guide gives the
operator sequence, limits, developer map and remaining connection work.
**Export logs** includes `attachment-source-qualification-data.json` in the
confirmed workspace export folder, without private isolation attachment bytes.

The preceding [camera dispatch transaction](CAMERA_ACQUISITION_DISPATCH_IMPLEMENTATION.md)
joins the coordinator to original-store readback and the existing captured-data
pipeline. It is currently an internal, tested application path; the physical
probe/capture buttons are still held until original admission and native release
are implemented. The camera and arm are not ready for plug-in-and-type use.

The [durable intake workflow](PHYSICAL_INTAKE_SUBMISSION_WORKFLOW.md) adds
fixed-inbox discovery, original attachment retention, exact-submission review
and restart-safe metadata. Complete all sixteen questions with observations or
explicit UNKNOWN reasons. OBSERVED requires an attachment; one file can support
several questions. **Export logs** preserves full intake metadata in
`attachment-intake-evidence.json`. **Export private original intake files** is
separate, explicitly approved and unredacted, in the selected workspace export
folder. It does not connect devices or accept physical stages.

The preceding [progressive configuration records](PHYSICAL_CONFIGURATION_EPOCH_WORKFLOW.md)
join **Collect prerequisites** to one immutable, original-store dependency
record. The Camera panel separates saved references from missing predecessors
and outputs expected at later stages. Refresh/restart never regenerate this
record or turn it into a hardware measurement. **Export logs** keeps the full
record in `attachment-configuration-records.json`, under the selected workspace
export directory, even after recent results rotate.

Quick launch from the workspace root:

```powershell
.\start-rocell-wizard.ps1 -Check
.\start-rocell-wizard.ps1
```

The second command opens the rehearsal workbench. To use the original setup
workflow, launch with `-Mode physical`; launching it does not connect, power
or move hardware. Eligible USB metadata operations are separate explicitly
reviewed actions; physical camera capture and arm commissioning remain pending.
On Camera, initialize a new store **or** explicitly discover
and reopen the original; collect prerequisites only for a new setup. Assess and
review the saved sources, inspect the remaining holds, then export logs. The
default export parent is
`C:\Users\Jack\Desktop\robot-arm-build\software\runs\wizard-exports`.

The [arm connection resolution workflow](ARM_CONNECTION_RESOLUTION_WORKFLOW.md)
now joins the real Windows metadata decoder and two fresh controller comparisons
to the contained incapable feedback child. The arm panel distinguishes PRE_OPEN
and PRE_WRITE checks, historical missing traces and separate cleanup results.
`attachment-owned-arm-connection.json` reserves diagnostic export space before
ordinary result rotation. Physical port opening, startup and typing remain held.

The companion [camera data workflow](PHYSICAL_CAMERA_CAPTURE_WORKFLOW.md) connects
retained native probe/settings/readback to verified YUY2 datasets and last-frame
publication. **Stage reported native camera settings** now uses only an original
probe's choices. Physical probe/capture dispatch is still held, so this action
will remain unavailable in a fresh ordinary launch until that separate join is
finished. Real-file tests use modeled native observations, not received hardware.

The preceding [saved workspace-source assessment and review](PHYSICAL_SOURCE_REVIEW_WORKFLOW.md)
connects the original Camera setup records to retained receipt, assessment and
separate review. In physical mode use Initialize (or Discover/Open), Collect
prerequisites, **Assess saved workspace sources**, then **Review exact
workspace-source assessment** with a different label. The original stage moves
to REVIEW_PENDING then BLOCKED: file facts cannot establish power isolation,
HZ-012 qualification or static-camera release. No PASS override exists.
The full workflow survives restart and result rotation in
`attachment-workspace-source-workflow.json` in the assigned export folder.

The preceding [native arm metadata workflow](WIZARD_ARM_METADATA_IMPLEMENTATION.md)
joins a reviewed SERIAL candidate to explicit Windows COM-interface and driver
metadata through the bounded diagnostic child. On **Arm**, first inspect/review
the generic candidate, then choose **Inspect native arm identity metadata**.
In rehearsal, use the separate incapable action. The cached panel distinguishes
current correlation, held observations and historical results. The latest full
attempt is reserved in exports as `attachment-native-arm-metadata.json`, even
after ordinary result cards rotate. It does not open a port, identify firmware,
verify electrical isolation or pass a physical stage.

The preceding [camera runtime file inspection/review](PHYSICAL_CAMERA_RUNTIME_REVIEW_IMPLEMENTATION.md)
adds two explicit physical-mode Camera actions and a full-report export that
survives result rotation. Actual installed files are inspected without running
helpers or opening hardware; separate probe/capture matches and gaps remain
visible. The public workflow and real browser inspect/review/export checks pass.
File review does not register a runtime, connect the camera or lift physical holds.

The preceding [noncontact readiness diagnostic](WIZARD_NONCONTACT_IMPLEMENTATION.md)
extends the guided rehearsal with a retained stage-14 gap report. It separates
historical collision inventory, static-camera requirements and real unmeasured
accuracy terms from passing synthetic controls. Its nominal outcome is BLOCKED;
review cannot advance to handoff. The complete receipt has a dedicated export
attachment that survives rotating result history. No physical device is opened.
The [verified feedback-window repair](FEEDBACK_SINGLE_WINDOW_IMPLEMENTATION.md)
now completes the public memory-first walkthrough: thirteen rehearsal stages PASS,
stage fourteen BLOCKED, handoff PENDING. The full gap receipt survives result
rotation, review and original-store reopening, with verified chosen-folder exports.
The [earlier failed run](NONCONTACT_FEEDBACK_INCIDENT.md) remains preserved and
quarantined; it was not retried or rewritten. This verifies the software lifecycle,
not installed calibration, physical connection or readiness to move.

The preceding [passive intake notebook](PHYSICAL_INTAKE_NOTEBOOK_IMPLEMENTATION.md)
adds explicit blank forms for the sixteen camera-receipt, placemat and bench
questions, using the original verified build requirements. Draft observations
and UNKNOWN reasons can be revised and exported. Evidence notes are not uploaded
attachments; drafts never accept a stage. The dedicated notebook export survives
later diagnostic-result rotation. Draft restoration after closing is not yet
implemented: export to the assigned `software/runs/wizard-exports` folder.

The preceding [camera restart workflow](PHYSICAL_CAMERA_RESTART_IMPLEMENTATION.md)
adds explicit discovery, opening and same-original verification after an app
restart. Current app identity and original stored context stay separate; no
connection, settings, image or approval is replayed. Both real two-launch
storage/export scenarios pass. Use Discover/Open instead of initializing a
replacement when continuing existing setup.

The preceding [camera setup session/checklist workflow](PHYSICAL_CAMERA_SESSION_IMPLEMENTATION.md)
adds explicit initialization, original-store verification, and build-derived
prerequisite collection to the Camera UI. It has been exercised through real
local M1 storage and verified exports. No physical camera or arm is connected;
received-unit evidence and live acquisition remain pending.

The preceding [physical camera application join](PHYSICAL_CAMERA_APPLICATION_IMPLEMENTATION.md)
adds an explicit camera acquisition-plan action, a cached physical-camera panel,
distinct camera-only storage/native composition and actionable retained camera
faults. Plans and exported diagnostics work without hardware; physical
probe/settings/capture remain held. Use the plan action to inspect requirements,
not to connect the camera. The selected export folder remains
`software/runs/wizard-exports`.

The preceding [native capture and arm identity work](NATIVE_CAPTURE_CONNECTION_IMPLEMENTATION.md)
adds guarded capture preparation/admission, separate metadata/file verification,
and an explicit Windows controller resolver. These are connection-path
prerequisites, not new physical connection actions or hardware qualification.

The preceding [contained arm-feedback integration](WIZARD_OWNED_ARM_INTEGRATION.md)
adds a separate stage-12 action running the real feedback worker and non-purging
backend in an isolated incapable process, with retained evidence and original-store
verification. It does not open a physical port or enable motion/contact.

The preceding [actual-source preflight](PHYSICAL_PREFLIGHT_INTEGRATION.md) adds an
explicit physical-diagnostic action checking real local files and retaining its
report through qualified storage. A scoped native admission-only rehearsal is
also tested. Neither unlocks camera/arm connection, calibration or physical typing.
The earlier [native connection work](NATIVE_CONNECTION_IMPLEMENTATION_CHECKPOINT.md)
remains the serial/admission prerequisite record.

## Launch

From the workspace root, after the existing development environment is set up:

```powershell
.\start-rocell-wizard.ps1
```

The launcher defaults to rehearsal, opens the browser explicitly, and uses a
free loopback port. It does not install dependencies/drivers or open a camera
or serial port. Keep its terminal running; Ctrl+C closes the workbench. The
older `start-rocell-onboarding.ps1` command retains its existing behavior.
After updating code, close and relaunch your existing wizard deliberately. A
running service is bound to its startup source; refreshing the page does not
reload its Python code or approve changed source. Export any needed old-session
diagnostics before restarting. Developer checks do not close unrelated running
wizard sessions.

Other supported entry points:

```powershell
# Read the startup view only: no server socket, test run, or hardware access.
.\start-rocell-wizard.ps1 -Check

# Headless interface over the same service/actions.
.\start-rocell-wizard.ps1 -Ui terminal

# Physical diagnostic mode: source-only preflight and explicit OS metadata checks.
.\start-rocell-wizard.ps1 -Mode physical

# Explicitly assign a different existing folder or new leaf under an existing parent.
.\start-rocell-wizard.ps1 -ExportDirectory 'C:\work\rocell-diagnostics'
```

Use `setup-rocell.ps1 -Profile development` deliberately if the workspace
environment is missing. That separate setup command installs Python packages.
Driver installation, Windows privacy settings, controller firmware and power
are not modified by the wizard.

## What to do in the interface

For the received camera before the arm/board is assembled, start with
**Camera → Run pre-build vision checks (no devices)**. This grouped synthetic
check uses no hardware and grants no physical stage pass. Follow the
[pre-build operability playbook](PREBUILD_OPERABILITY_PLAYBOOK.md); optics and
distance testing are deferred, and real camera integration is a separate step.

In physical mode, start on **Overview → Check actual source files (no devices)**.
Preview/confirm once, inspect **Actual source preflight**, then use
**Diagnostics & exports**. The selected default is `software/runs/wizard-exports`.
A coherent report does not pass a physical stage or observe power state. See
the [detailed workflow and failure rules](PHYSICAL_PREFLIGHT_INTEGRATION.md).

1. **Overview:** preview and explicitly run setup baselines and the registered
   software boundary test suite. Examine passed tests and remaining physical
   holds separately.
2. **Camera:** inspect the purchased profile; rehearse connection and fault
   handling; test the synthetic static camera stack. The optional placemat
   drawing is a nominal schematic. The separate guided binary
   rehearsal also supplies a preview derived from retained synthetic YUY2 bytes;
   neither is a physical camera observation.
3. **Arm:** rehearse the feedback-only lifecycle and expected faults. The new
   **Test one-shot arm feedback worker** action exercises the onboarding worker's
   closed nominal/boot-byte/short-write/timeout/identity-change/close-failure
   scenarios with a sealed incapable serial backend. In
   physical diagnostic mode, explicitly inspect OS camera/serial metadata
   without opening either device. Identity observations are not qualification.
4. **Board & tests:** inspect canonical layout facts and rehearse installed
   camera calibration contracts using synthetic evidence.
5. **Task rehearsal:** compile keyboard/phone text into existing semantic
   actions, or run a bounded short geometry/IK/vision simulation. No keypress,
   phone input injection, robot movement or contact command is sent.
6. **Diagnostics & exports:** inspect results, append issue/resolution notes,
   and create a new verified report under the assigned directory.
7. **Guided rehearsal:** use the durable workflow and stage-14 gap report described
   below. Its stage journal is not the physical progress shown on Overview.

Each runnable action has a separate preview and explicit confirmation.
Duplicate submission returns the existing operation rather than starting it
again. A software Stop requests diagnostic cancellation; it is **not** a robot
emergency stop and cannot establish actuator power-off.

## Review camera and arm metadata candidates

For installed runtime diagnostics without hardware, use **Camera → Inspect
installed camera runtime files**, then **Review exact camera runtime report**.
Enter explicit operator/reviewer labels and file-only acknowledgements. The
current historical probe-source mismatch remains HELD after review. Export the
complete report through Diagnostics; do not change build pins to remove a hold.
See the [workflow, API map and exact verification](PHYSICAL_CAMERA_RUNTIME_REVIEW_IMPLEMENTATION.md).
This inspection is independent of metadata enrollment and physical-store setup.

In physical mode, **Camera → Prepare physical camera acquisition plan** can run
before devices arrive. Choose probe or capture, preview the exact intent and
confirm once. **CURRENT publication** refers to the saved plan/report, not a
camera image or connection. Missing reviewed endpoint, runtime qualification,
physical prerequisites and power-isolation evidence remain visible holds.
Capture also requires a retained physical probe and reviewed settings.
Export both the full plan and its holds through **Diagnostics & exports**.
The separate physical probe, configuration and capture actions are not enabled
by preparing or exporting this plan.

This workflow is available independently of the durable rehearsal stages. It
records which observed metadata occurrence you inspected, not a persistent
hardware binding or a passed commissioning stage.

1. Before hardware arrives, open **Camera → Rehearse device discovery and
   selection**. Choose nominal, missing identity, duplicate identity or partial
   inventory, then preview and execute. These are fixed injected records, not
   host observations.
2. In physical diagnostic mode, **Arm → Inspect attached device metadata**
   instead uses the existing explicit OS metadata collector. Its disconnected
   actuator-power acknowledgement remains required. Do not use this instruction
   as a power-on, plug/unplug or startup procedure. Camera/serial endpoints are
   not opened by metadata collection.
3. Inspect the **Camera metadata candidate review** or **Arm metadata candidate
   review** card. It displays the snapshot's source, candidate identity fields
   and missing/ambiguous identifiers. Device names are not verified models.
4. In the device's **Review … metadata candidate** action, explicitly choose a
   candidate, enter a non-sensitive reviewer ID, tick the metadata-only
   acknowledgement, preview the exact snapshot and execute. No choice or
   acknowledgement is supplied automatically.
5. Use **Diagnostics & exports** to retain the full inventory and review result
   in the assigned workspace folder. Notes cannot clear identity or physical
   holds. A partial collection fails and retains its report for investigation.

Every new inventory clears both reviews before it runs, including failed or
cancelled refreshes. Source changes or diagnostic logging failure also clear
current choices. Old choice tokens and pending old tickets cannot be reused.
Restart begins without a selected candidate; it does not restore a connection.
Camera and arm remain **NOT CONNECTED / NOT QUALIFIED** after review.

The [selection API](WIZARD_DEVICE_SELECTION_API.md) and
[presentation guide](WIZARD_DEVICE_METADATA_PRESENTATION.md) describe the exact
contracts. Generic OS metadata is not the exact Media Foundation endpoint
mapping required for real camera campaigns. The next workflow now rehearses
that mapping through the same native receipt parsers.

## Inspect and register the metadata-only camera helper

Physical launch still starts without a native provider. The Camera page now
offers an explicit registration path through the fixed development catalog;
Python provider injection is no longer required for this metadata-only step.

New sessions use the separately built **metadata-only v2** helper and its fixed
17-file catalog. The original v1 catalog and runtime remain retained, with no
automatic fallback. The [successor checkpoint](CAMERA_METADATA_SUCCESSOR_WORKORDER.md)
records successful received-B0477 endpoint/USB-instance/container matching through
this backend. Persistent-unit binding remains held on missing generic unit serial;
this result is not a video connection, USB-speed qualification or calibration.

1. Choose **Inspect camera metadata helper files**, enter a non-sensitive
   operator label and acknowledge metadata-only scope. Preview and execute.
   Physical mode reads bounded fixed files and compares their hashes; it does
   not run the helper or enumerate devices. Rehearsal instead offers incapable
   nominal, missing-helper and hash-drift fixtures with no file/device reads.
2. Inspect the **Camera metadata helper registration** card and full report.
   The catalog pins the helper, native sources, historical build record and
   current metadata client separately. A client-change warning remains visible:
   this is **not** full-build matching, release approval or qualification.
3. Choose **Review metadata-only helper registration**, supply a different
   reviewer label and explicitly acknowledge scope. Labels are not authenticated
   proof of different people. Preview the exact retained inspection and execute.
   Missing/drifted files remain reviewable but cannot register a provider.
4. An eligible committed review enables only the separate explicit native
   inventory/identity actions below. Each lookup revalidates the exact inspected
   files; it cannot silently accept new hashes. There is no automatic query,
   probe, capture, serial open or device connection after registration.
5. Export the inspection/review from **Diagnostics & exports** to the assigned
   `software/runs/wizard-exports` folder. Fresh inspection/review first retires
   old native choices and registration. Failure/cancellation never restores
   them. Source or logging failure revokes them too; restart requires a new
   explicit workflow.

File hashing is not filesystem race-proofing or physical process containment
qualification. Neither registration nor matching endpoint metadata enables
camera activation. Received USB identity/speed, supported camera modes, focus,
coverage, installed calibration, arm power/firmware and physical tests remain
unverified.

Developer contracts: [file inspection and provider](WIZARD_CAMERA_HELPER_INSPECTION.md),
[staged registration](WIZARD_CAMERA_HELPER_REGISTRATION_API.md), and
[browser/terminal presentation](WIZARD_CAMERA_HELPER_PRESENTATION.md).

## Resolve and review native camera endpoint metadata

This is connection preparation, not camera activation. Start with a current
generic **Camera metadata candidate review** from the preceding workflow.

1. On **Camera**, preview and execute **Discover native camera endpoints**.
   Default rehearsal offers nominal, missing mapping, wrong device and duplicate
   name fixtures. Tick the metadata-only acknowledgement explicitly. There is
   no automatic discovery on launch, navigation or refresh.
2. Inspect the **Native camera endpoint enrollment** card. In **Resolve selected
   native endpoint identity**, explicitly choose an endpoint and acknowledge
   metadata-only lookup. The server resolves the opaque choice; never enter a
   symbolic link, camera index, helper path or command into the browser.
3. The result compares the exact endpoint, observed device-instance string and
   container with the reviewed generic camera. Missing or conflicting values
   remain visible. The same friendly name on two endpoints is not a unit match.
4. Use **Review native endpoint mapping**, choosing the same resolved endpoint
   and supplying a reviewer ID. A matching result can produce
   `REVIEWED_ENDPOINT_METADATA_ONLY`; missing/mismatched identity produces a
   held review without a binding artifact. Both remain **NOT CONNECTED / NOT
   QUALIFIED**, and USB-speed, received-unit and physical-stage holds persist.
5. Export diagnostics. The complete generic review, native inventory and
   identity wire receipts are retained alongside the prospective binding's
   hashes, not replaced by the small status card. If redaction changes bound
   metadata, publication fails explicitly; the redacted diagnostic is not
   presented as exact identity evidence.

A new generic inventory or camera review retires the native snapshot. A new
native inventory clears endpoint choices; another identity query clears the
previous identity and binding before dispatch. Failure/cancellation does not
restore them. Source change or logging failure holds the workflow. Returned
bounded metadata is retained for diagnosis if a source change is detected
after lookup. Restart never restores a reviewed endpoint implicitly.

**Default physical launches do not automatically register a native provider.**
They show `PROVIDER_UNAVAILABLE` until the explicit inspection/review workflow
above commits an eligible metadata-only registration. Generic camera candidate
review is also required before native lookup. A historical development build
manifest is not trusted automatically or upgraded to release qualification.
Native mode/control probing, finite physical preview and camera connection
are not granted by this registration. Original-bound probe/settings acquisition
has separate prerequisites and a remaining full-history integration check; this
metadata-only successor cannot execute those operations.

Developer reproduction (writes only new diagnostic logs/exports):

```powershell
.\.venv\Scripts\python.exe software/scripts/wizard_native_camera_enrollment_smoke.py
.\.venv\Scripts\python.exe software/scripts/wizard_native_camera_enrollment_smoke.py --scenario wrong-device
# Include the new helper inspection/review workflow (incapable fixtures only):
.\.venv\Scripts\python.exe software/scripts/wizard_native_camera_enrollment_smoke.py --helper-scenario nominal
.\.venv\Scripts\python.exe software/scripts/wizard_native_camera_enrollment_smoke.py --helper-scenario missing-helper
.\.venv\Scripts\python.exe software/scripts/wizard_native_camera_enrollment_smoke.py --helper-scenario hash-drift
# Prepare fixture inventory, then leave selection/identity/review/export to the UI:
.\.venv\Scripts\python.exe software/scripts/wizard_native_camera_enrollment_smoke.py --serve
```

See [native metadata bridge](WIZARD_NATIVE_CAMERA_METADATA.md),
[endpoint enrollment API](WIZARD_NATIVE_CAMERA_ENROLLMENT_API.md), and
[presentation contract](WIZARD_NATIVE_CAMERA_ENROLLMENT_PRESENTATION.md).

## Guided rehearsal with real storage

This path exercises source/session binding, ordered OS storage leases, immutable
receipts, assessment/review and camera attempt accounting. The provider is
incapable: camera counters are simulated observations, not device opens. The
worker now creates full-size binary YUY2 fixtures and derives a PNG from their
retained bytes. The workflow implements the first thirteen rehearsal stages,
including synthetic optics, injected arm identity, typed power-procedure checks
and the actual arm worker with its memory-only serial backend, followed by nominal
reference-frame math and dependency checks, then a stage-14 readiness gap report.
The gap report cannot accept physical noncontact readiness. See
the [binary camera handoff](WIZARD_BINARY_CAMERA_REHEARSAL.md) and
[optics workflow contract](REHEARSAL_OPTICS_STAGES_API.md) for code/data contracts.

1. Open **Guided rehearsal** and explicitly initialize its store. It creates a
   fresh leaf beneath `software/runs/wizard-rehearsal/`, qualifies the actual
   local Windows NTFS location and writes an immutable `REHEARSAL` header. The
   source binding is domain-separated from physical sessions. Startup and
   merely viewing this page do not create that store.
2. Choose **Collect due-stage synthetic evidence**. Use a rehearsal operator
   identifier. For stages 1–3, the input is explicitly labeled synthetic
   prerequisite evidence; it is not receipt of the real hardware.
3. Choose **Assess retained synthetic evidence**, inspect the displayed exact
   assessment, then **Review exact synthetic assessment** using a different
   rehearsal reviewer ID and the explicit acknowledgment. This tests the
   two-role workflow; local typed IDs are not authenticated user accounts.
4. At camera identity, choose the synthetic B0477 or the wrong-camera fixture.
   The wrong camera produces a blocked assessment. Accepting that assessment
   records `BLOCKED`, never an override to `PASS`. New evidence preserves the
   earlier failed receipt and review.
5. At mode/controls, collect/open the due stage, then **Prepare synthetic camera
   settings** and run the coordinated synthetic camera campaign. Start with one
   frame; each YUY2 `5472 × 3648 @ 9 fps` sample is about 40 MB before the retained
   copy. One to four are allowed. The exact plan binds the reviewed synthetic
   candidate, settings epoch, scenario and finite resource limits. The Camera
   page displays a 912×608 PNG derived from retained bytes. These are enlarged
   synthetic placemat pixels, not measured 20 MP detail or installed focus.
   Assess/review separately. Stage six uses the same reviewed settings.
   As a separate backend, **Run contained incapable camera-process campaign** runs one
   fixed incapable Windows child through the camera client and retains the
   actual process result alongside the generated frame dataset. Start with one
   frame: templates plus raw/retained data need about 85 MB per frame, plus a
   128 MiB safety margin. Inspect the Guided rehearsal **Camera process** card:
   successful process cleanup is distinct from synthetic camera cleanup and
   does not qualify a physical camera. This action never falls back to the
   in-process campaign. Both backends share assessment/review and source-bound
   reopening. See the [contained camera integration](WIZARD_OWNED_CAMERA_INTEGRATION.md).
6. Identity-mismatch and cleanup-uncertain campaign scenarios latch a real
   quarantine in this **rehearsal** cell store. Verify state and export the
   result; there is no clear-quarantine or replay button. A subsequent launch
   starts a different rehearsal, not recovery of the held one.
   The contained backend also offers malformed-result and child-timeout
   scenarios. Each is a fresh explicit test, not an automatic retry. A held
   attempt preserves its full bounded child output in the original M1 campaign
   record; exported diagnostics contain its hash, status and safe projection.
   Raw frames and private M1 records are not automatically bundled into exports.
   Export folders default to `software/runs/wizard-exports`, as selected for
   this build. An export is diagnostic, not permission to operate hardware.
7. At **Optics/intrinsics**, explicitly collect again. The service verifies the
   reviewed stage-six binary dependency and runs the existing strict parser and
   assessor on the fixed synthetic intrinsics artifact. Inspect the retained
   partition/source checks (24 training and 8 held-out observations), then
   assess and review separately. This rehearses an artifact/residual contract;
   it does not solve installed-camera intrinsics or measure actual focus.
8. At **Static registration**, explicitly collect the existing normal and
   tag-loss nominal JPEG pixel checks. Inspect nominal pose quality and the
   independent K0/P0 held-out checks, plus expected rejection without a pose
   when tags are lost. An expected negative-test rejection cannot substitute
   for a failed nominal result. These pixels come from the canonical nominal
   scene renderer, **not** the stage-six native-sized binary dataset. Assess
   and review the complete result separately; failed checks remain BLOCKED.
9. After stage eight, export and restart the application, then explicitly
   discover/reopen the **same** rehearsal store. Each launch has a 32-operation
   budget; do not initialize a replacement to continue original progress.
10. At **Arm identity**, collect the configured-profile and injected serial
    inventory checks. Inspect nominal matching separately from missing,
    duplicate, changed alias/topology/interface, wrong-model and malformed
    metadata cases. No host enumeration or physical Pro/firmware/driver
    qualification occurs. Assess and review separately.
11. At **Power safety** and **Power-on observation**, collect the typed
    synthetic procedure/assessor checks. **Do not energize the arm for these
    actions.** They do not predict startup movement or observe an E-stop or
    final power state. Successful expected-fault handling cannot replace
    nominal acceptance. Assess/review each stage's complete report.
12. At **Feedback-only connection**, collect/open the due stage, then explicitly
    run **Run coordinated memory-only arm feedback**. Inspect packet validity,
    complete transaction, serial cleanup and the independent synthetic final-power
    observation separately. Assess/review the retained result; no physical port or
    power is accessed. See [the feedback integration contract](WIZARD_FEEDBACK_INTEGRATION.md).
13. At **Reference-frame calibration**, collect the nominal FK/frame-chain,
    synthetic point-fit and dependency-graph checks. Inspect nominal success
    separately from injected-failure handling, held-out residuals and the explicit
    one-keyboard/one-phone target subset. This is not all-75-target or IK/route
    acceptance. Camera stages 6–8 are dependencies, not numerical inputs; T105
    fields are transport evidence, not calibrated joints. All eight physical
    reference components remain pending. Assess and review separately. See
    [the reference presentation contract](WIZARD_REFERENCE_PRESENTATION.md).
14. At **Noncontact acceptance**, explicitly collect the readiness diagnostic.
    Inspect the three failed nominal checks separately from five passing
    synthetic controls. Historical collision coverage is not installed static
    geometry; all ten real accuracy terms remain unmeasured. Pose, route,
    sensitivity, visibility, dynamics and real motion are NOT_EVALUATED.
    Assess, then review with a distinct reviewer to record **BLOCKED**, not PASS.
    Export the complete `attachment-noncontact-readiness.json`; it survives the
    last-eight result limit and original-store reopening does not rerun math.
    See [the implementation workflow](WIZARD_NONCONTACT_IMPLEMENTATION.md).
15. Handoff remains pending, as do physical noncontact acceptance and installed
    reference calibration. All physical stages remain pending throughout. This is not
    `REHEARSAL_COMPLETE_ZERO_AUTHORITY` or a complete fifteen-stage release.

**Verify retained rehearsal state** explicitly rereads the durable records.
Unexpected external journal/evidence changes hold this launch and invalidate
its pending review instead of silently rebasing it. Closing the application
does not erase the store. The next launch can explicitly reopen the same store
as described below. Export contains bounded state/result summaries, not a full
qualified-store backup. Retain the original store for developer investigation.

Stop reaches the coordinator's shared cancellation event. A cancellation after
arming can be uncertain; a Stop received after a durable operation completes
cannot undo its record. Inspect the actual attempt result before any next step.
For no-device optics/arm-setup checks, Stop is also checked after dependency reads,
before the probe and before result/assessment/review publication. An opened
stage without a complete retained result holds; reopening does not rerun it.

### Continue a saved rehearsal

1. In a fresh launch, choose **Discover saved rehearsals**. This reads bounded
   metadata under the assigned rehearsal folder only. It does not create a new
   store, qualify storage, open devices or automatically choose a session.
2. Select the exact original session from **Open selected saved rehearsal**.
   There is no preselected session. Review its directory/cell/session and the
   disclosed storage qualification/lease effects, then execute explicitly.
3. An opened session restores its verified receipts, settings, capture metadata,
   optics check summaries and pending assessment. It does not load an old image
   or replay a camera campaign, image probe, arm command, prepared ticket or
   approval. A complete optics WAIT receipt can be assessed after reopening;
   a missing result is an explicit hold, not permission to recollect.
   A pending assessment
   requires a fresh exact review using a different operator/reviewer ID.
4. If an older camera-stage opening has no retained operator, use **Record
   missing reopened-stage operator** before new settings/capture. This action
   cannot rewrite the operator of an existing campaign.
5. Read-only holds display the reason and next investigation step. Source
   changes, uncertain attempts, quarantine and partial/corrupt evidence are not
   automatically repaired or migrated. Each selection can be attempted once per
   launch. An unused different session may still be explicitly selected; an
   attached session cannot be silently replaced. Preserve and export held state.

Storage opening uses the original journal and can write qualification probes
and lease metadata, but it does not rewrite stage evidence. Stop after those
checks prevents attachment when observed before attachment; it cannot undo
checks already completed. See the [reopening contract](COMMISSIONING_REHEARSAL_REOPEN_API.md).

## Probe and stage camera configuration in Guided rehearsal

The [camera configuration integration](WIZARD_CAMERA_CONFIGURATION_INTEGRATION.md)
adds an optional explicit probe path before the first camera capture. After
opening stage 5 and preparing its synthetic brightness, use **Probe contained
camera capabilities**. Its new card shows modeled reported modes, six electronic
control ranges and units, and control availability. This is not a physical
camera probe or a purchased-unit specification.

In **Stage reported camera mode and controls**, explicitly choose the reported
full-resolution mode. Control intents start at **Do not request a change**;
choose a supported manual/auto intent only when wanted. Preview and retain this
configuration once. Staging saves intent, not applied settings. Use **Run
contained incapable camera-process campaign** next; its retained result compares
requested settings with independently reported modeled readback. A mismatch
holds the session. Stage 6 reuses the exact configuration with a new capture.

Once this path is chosen, the session cannot use an unconfigured or in-process
fallback. Stop, source drift or diagnostic log failure retires the current
display while retaining original evidence. Complete probe-only sessions can be
reopened without rerunning the child. Lens focus/aperture and installed mounting
geometry remain manual physical checks; no control setting qualifies them.

## Logs and investigation

The user-selected default export root is:

```text
software/runs/wizard-exports/
```

An export creates a unique new directory containing a readable report,
structured state/events and a checksum manifest. The service verifies the
published export before reporting success. Existing exports are not
overwritten. Export records are bounded and credential-redacted; inspect the
report's limitations/omission policy before treating it as a complete record.
These are troubleshooting exports, not a signed commissioning bundle or an
M1 cell-store backup.

Optics collection results include their complete bounded technical reports,
while the guided page shows a compact check list and exact provenance. Export
before closing if those operation results are needed: a fresh launch restores
the original stage evidence, not the preceding launch's operation history.

Lightweight application events are retained separately under
`software/runs/wizard-diagnostics/`. Each launch has a new diagnostic session;
events do not advance canonical commissioning stages or carry physical
authority. A partial/corrupt log is not repaired or replayed automatically.

For an issue:

1. Open the failed operation and read its exact error, observations and
   remediation. An injected expected fault can correctly pass the test.
2. Add a note describing the issue and investigation. Notes do not clear a
   physical gate, convert a failed result to PASS, or authorize a retry.
3. Export the diagnostic report to the assigned folder.
4. Make an explicitly reviewed software/configuration correction. If source
   binding changes, the current workbench becomes diagnostic-read-only for
   new test actions; export and restart explicitly.
5. Preview a new diagnostic test and compare its new result with the retained
   failure. Do not delete the earlier evidence.

Do not use passwords or sensitive personal text for typing demonstrations.
Semantic plans and logs may reveal the sequence of key/tap targets even when
the original text field is not retained verbatim.

## Boundaries still held

The Camera/Arm connect and hardware task execution buttons remain disabled.
The native Windows camera helper has compiled, fixture-tested finite capture
and an explicit identity-metadata client action with a separate strict
receipt schema. The wizard now joins reviewed generic OS metadata to that
native endpoint-enrollment path through explicit helper registration.
Persistent-unit qualification, native preview integration and
received-camera verification remain incomplete. The coordinator now has an
M1-backed, lease-owning **rehearsal** persistence adapter; that is not qualified
physical worker admission. The UI's existing diagnostic subprocess runner
remains a separate no-actuation component.

The native client now provides [filesystem-inert prepared requests](WINDOWS_CAMERA_PREPARED_REQUESTS.md).
Those requests share the builder used by actual probe/capture and can be bound
to a future coordinator review. Preparation does not invoke the helper or
grant authorization; the physical capture button remains held.

Physical onboarding still needs independent effect/durability qualification,
native worker containment, binary-dataset integration, the remaining stage
review/acquisition services, static-primary successor migration, firmware/identity
observations and actual calibration. Power observation and later motion/contact
release remain separate. Do not copy test authorizers, change authority flags
or use vendor demos to make a held button function.

See the [developer playbook](CAMERA_ARM_DEVELOPER_PLAYBOOK.md),
[integration plan](CAMERA_ARM_CONNECTION_INTEGRATION_PLAN.md),
[M1 guide](M1_ZERO_HARDWARE_RUNTIME.md),
[retained arm/power check presentation](WIZARD_RETAINED_ARM_POWER_CHECKS.md),
[retained feedback presentation](WIZARD_FEEDBACK_PRESENTATION.md), and
[native camera boundary](../native/windows_camera/README.md).

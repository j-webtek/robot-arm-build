# RoCell operator guide: the local workbench

Updated 2026-09-12. This guide is for the implemented UI, not permission to
operate the received hardware. The app is a diagnostic/onboarding workbench;
physical typing, phone tapping and general Connect controls remain unreleased.

## Start the application

From `C:\Users\Jack\Desktop\robot-arm-build`:

```powershell
.\start-rocell-wizard.ps1 -Mode rehearsal
```

This starts the real local service and opens its private browser URL. Rehearsal
is the default; startup does not enumerate, open, initialize or power devices.
Use the cell ID that belongs to your setup (`-CellId` if different from `CELL-A`).
Do not invent a new cell/session to work around an existing original-store hold.

The confirmed default export parent is
`C:\Users\Jack\Desktop\robot-arm-build\software\runs\wizard-exports`.
`-ExportDirectory` can assign a different parent at launch; browser forms cannot
choose arbitrary output paths. `-NoBrowser` prints the launch URL without opening
a tab. Keep that private launch URL/token out of screenshots and issue reports.

`-Mode physical` selects the physical inspection catalog, not a connection or
permission to power the arm. Follow the received-unit procedure and the exact
action prerequisites; do not switch modes just to evade a hold. The legacy
`start-rocell-onboarding.ps1` is a different diagnostic-session preparation
workflow, not this browser launcher.

If source changes while the real service is running, export what is available
and inspect its source hold. Restart explicitly after review; refreshing the
browser does not rebind an old service to new source. This UI work does not
restart an existing hardware session.

## Find the right workspace

| Workspace | Implemented UI use | Important limit |
| --- | --- | --- |
| Overview | Current status/holds, software baselines, onboarding progress, short operating guide | Service connection is not a device connection |
| Control Center | Search every registered action, filter by component/availability, open its original form | An offered form is not hardware-ready |
| Guided rehearsal | Explicit simulated commissioning, retained evidence and review stages | No simulated stage qualifies received hardware |
| Camera | Selected profile, metadata/original setup, probe/settings attempts, eligible finite capture, published still image, assessment/recovery records | Not live video or installed calibration; focus/aperture are manual |
| Arm | Controller metadata, feedback/movement rehearsals, saved-record inspection, and separately gated physical passive observation/telemetry/one-shot feedback forms | General Connect and motion remain held; each physical diagnostic has its own current prerequisites |
| Board & tests | Nominal source-bound geometry, software baseline records and calibration rehearsal | A drawing/synthetic calibration does not measure the assembled board |
| Task rehearsal | Keyboard/phone semantic plans, short nominal simulation, path/IK/vision outcomes | Legacy arm-mounted-camera task graph; not static-camera validation or physical execution |
| Activity & results | Full retained launch history, filters, explicit full-result reads, errors and recovery guidance | 32 summaries and the last 8 full results are bounded retention, not a permanent archive |
| Diagnostics & exports | Assigned export folder, receipts, notes, events, exact-attempt export controls and readable full service view | Exports are diagnostics, not permissions; general and dedicated exports differ |

The September 12 audited roster contained **130 forms**: 82 Camera, 20 Arm, 15 Guided rehearsal,
6 Diagnostics, 3 Overview, 3 Tasks and 1 Board. This includes held/reserved forms,
not 130 released physical capabilities. Control Center uses the current service
catalog, so new supported forms appear without maintaining a second registry.

Arm, Board, Task and Diagnostics start with a short workflow guide. Their
**Browse controls** and **Review results** buttons reset directory filters to
that component. They never preselect a device, preview a ticket or execute a
test. The Camera workspace has its own next-step card and shortcuts; held forms
and detailed records remain expandable. Use Control Center to find dedicated
exports that belong to Camera rather than Diagnostics.

## Run one intended action

1. Read the mode, session, source binding and current holds. Choose the form by
   its meaning and identifier—not merely because its button is enabled.
2. Enter the requested fields. Select exact current device/evidence choices
   explicitly; a COM port alone is not controller identity. Operator/reviewer
   labels are procedural labels, not authenticated logins.
3. Choose **Preview action**. The service checks the displayed revision and
   returns a short-lived ticket. Read effects, warnings and the exact action
   record. This step does not execute the operation.
4. Choose **Execute reviewed action** only for that intended ticket. Cancel
   discards an unexecuted preview. The UI never automatically retries execution.
5. Open **Activity & results**, inspect the operation and choose its explicit
   result-read control if needed. Worker success, assessment success, physical
   qualification and path feasibility are different things.
6. Export needed evidence, then check the export operation and receipt. Preserve
   the whole reported bundle; do not edit its manifest or original attachments.

Keyboard operation: Tab/Shift+Tab traverse native controls, Enter/Space activate
buttons, and native selects retain their usual keyboard behavior. Forms have
accessible names; every field has an associated label and supplied help text is
linked to that field. The skip link jumps to the workspace. Component navigation
focuses and scrolls to the workspace start; Control Center focuses the original
form it opens. Read-only refresh does not scroll you away from your work.

## Camera originals: draft, inspect, then save for review

Added 2026-09-13. The original-submission feature is implemented under software
acceptance testing; the complete-history M1 gate is still in progress. This
section explains its interface, not permission to operate received hardware.

The Camera page's **Detailed camera records & prerequisites** disclosure keeps
the draft and saved-original cards separate. Control Center can find each action
by its displayed name and open the original form without running it.

1. Complete the existing eligible original setup, identity, probe and explicitly
   staged settings workflow. Rehearsal records cannot be imported to satisfy
   physical prerequisites. An unavailable action explains its current hold.
2. When separately eligible and confirmed, retain two explicit settings-capture
   attempts. Select their exact operation IDs; there is no automatic best-image
   choice or default selection for saving originals.
3. **Record an operating-mode proposal (draft)** creates a logged draft for the
   current settings and original probe. Explain any 8-fps versus 9-fps reference
   variance; it does not change the frozen purchase profile or approve settings.
4. **Check proposal against saved original evidence** is a file-only diagnostic.
   Its optional zero/one-capture selections are useful for showing missing facts;
   they are not sufficient to save the two-capture original submission.
5. **Save camera originals for separate review** requires an operator label,
   both distinct retained sealed-capture choices and unchecked-by-default consent.
   Preview its exact effects, then execute only that intended ticket. The service
   recomputes the assessment from originals; it accepts no uploaded report and
   opens no camera. Saving is a separate action, not an automatic consequence of
   the diagnostic assessment.
6. Inspect **Camera evidence saved for review** and the Activity result. Successful
   storage means an original **SUBMITTED_REVIEW_REQUIRED / REVIEW_PENDING** record,
   not PASS, an approved policy, a currently connected camera or arm authority.
   Continuity, separate review, freshness and installed calibration remain open.
7. Use the existing general diagnostic export for the saved compound and attempt
   bookkeeping. Export each capture attempt separately when its complete native
   admission/readback/cleanup diagnostics are needed. The general bundle does not
   include raw pixels or replace the dedicated USB/received-stage bundles.
8. After a fresh launch, explicitly reopen the original store. Historical saved
   evidence can reappear, but settings references, selected captures, current
   draft tickets and connections are not restored. Follow the newly offered
   prerequisites; do not attempt to replay the old save.

If the card shows **INCOMPLETE**, a package exists without its complete submission
event. If publication is held, Stop/time/source/logging or another check may have
failed after a write. Preserve and export the attempt; neither state permits an
automatic resume, rollback or repeat. Redacted diagnostic bytes are identified
as changed and are not the exact originals named by their original hashes.

See [the submission work order](CAMERA_OPERATING_SUBMISSION_WORKORDER.md) and
[the commissioning roadmap](CAMERA_UI_COMMISSIONING_ROADMAP.md) for the current
acceptance status and later milestones.

## Editing without losing ordinary text

Notes, task text and a small explicit set of numeric/narrative fields retain an
in-tab draft while setup and action contracts match. Nothing is persisted to
browser storage or disk by drafting. Reloading the page loses the draft.

Device/evidence choices, confirmations, labels, paths, ticket IDs and native
camera control intents are not saved. If options reset, ordinary text is held
outside the fields. Reselect the same options and choose **Restore ordinary
draft**. An old phone answer must not appear under a keyboard target, and an
intake answer must not move to a different question. **Reset form to service
defaults** discards that draft without submission.

Changed setup/source/action requirements, service loss and execution clear
drafts. See [the draft contract](UI_FORM_DRAFTS_HANDOFF.md) for the allowlist and
limits. Draft retention never upgrades a form's displayed revision or approval.

## Investigate a problem

- **Service unavailable:** distinguish the local application from device state.
  Drafts and preview tickets clear. Restore the local service only after checking
  its terminal/status; this does not stop an arm or prove zero effects.
- **Failed/uncertain/timed out:** inspect the original operation, exact error,
  cleanup and remediation. Export available evidence. Do not replay as a shortcut.
- **Cancellation requested:** wait for the service's terminal result and inspect
  cleanup. **Stop current diagnostic is not a robot emergency stop or power cut.**
- **Completion log failed:** the operation may already have taken effect. Keep
  the original attempt and existing receipt; do not rerun to manufacture a log.
- **Older full result omitted:** its summary may remain but the full result has
  rotated out. Use a previously preserved export. The UI cannot reconstruct it.
- **Export failed:** retain the partial output and error; inspect the assigned
  destination and original attempt. Existing exports are not overwritten.

Record a non-sensitive issue/resolution note with operation ID and exact error
code. A note never clears a hold. General export includes available launch
diagnostics; a separately labeled preparation/original/attempt export preserves
its own defined evidence. Read each export's scope before relying on it.

The full service snapshot in Diagnostics is readable browser JSON. JavaScript
can round large numeric timestamps; this display is not the original bytes for
hashing or evidence verification. Inspect the preserved export for exact values.

## Preview the interface without an executable service

```powershell
.venv\Scripts\python.exe software/scripts/camera_ui_preview.py --scenario drafts
```

Open the printed loopback URL. The banner labels fictional data. Six ordinary
note/task/synthetic forms permit editing; **all POST requests return 405**, so
even a note cannot execute. `--scenario catalog` disables every form;
`--scenario activity` adds fictional retained results for search/paging review.
These previews instantiate no wizard service, provider or device worker.

## What remains outside this UI delivery

Received-unit verification, installed optics/placemat calibration, camera
production qualification, canonical arm commissioning and physical typing/tapping
remain separate work. The registered narrow arm diagnostic controls do not
establish a persistent connection or release movement. Opening serial can reset
the controller even when a diagnostic sends zero commands. This UI delivery
does not run those tests or replace their current per-action requirements.
The task simulator's static-camera migration
is still open. Use the [application completion matrix](ONBOARDING_APPLICATION_COMPLETION_MATRIX.md)
and [static-task migration work order](STATIC_TASK_SIMULATION_MIGRATION_WORKORDER.md),
not a green worker status or this interface's visual polish, to track readiness.

Developer contracts and verification are in [the UI acceptance handoff](UI_APPLICATION_HANDOFF.md).

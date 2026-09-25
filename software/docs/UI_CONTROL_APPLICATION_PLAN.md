# RoCell operator UI enhancement plan

Goal established: 2026-09-12. Make the UI the usable way to discover, inspect,
control, and review everything the application has actually implemented.

This supersedes camera-only UI prioritization, not physical safety gates or
unfinished integration requirements. UI availability must not imply received-unit
qualification. Camera capture, original identity, arm feedback, and later motion
and contact keep their separate backend requirements.

## Current source inventory

The registered `wizard_actions.ACTIONS` roster currently has 130 actions:
82 Camera, 20 Arm, 15 Guided rehearsal, 6 Diagnostics, 3 Overview, 3 Task rehearsal,
and 1 Board & tests. This is an inventory of registered actions, not 130 qualified
hardware capabilities. Four definitions have explicit permanent implementation
holds; dynamic prerequisites and launch mode hold many additional actions.

`ArrivalWizardService.view()` is the authoritative cached catalog and status
projection. Existing action forms use `/api/prepare`, then a separate explicit
`/api/execute`. Results use `/api/operations/{id}`. Diagnostics already expose the
assigned export directory, receipts, events, and the read-only service snapshot.

Existing component pages render the registered forms, but discovery and result
review require too much scrolling. The camera page has recently gained shortcuts
and a readable saved-assessment checklist. Generic activity originally showed only
the last six operations. Activity now exposes the full retained launch history;
ordinary form editing now has context-bound in-tab drafts and explicit restoration
when dependent options reset.

## Delivery sequence and proof

### 1. Discover and reach every implemented control

- Add a Control Center to the main navigation and Overview.
- Build the directory from the current service catalog, not a second action list.
- Search labels, identifiers, descriptions, and hold reasons; filter by component
  and service-offered/held status; page long results without removing actions.
- Show exact hold reasons and distinguish service-offered from hardware-ready.
- Open the existing original form, expanding held sections as needed. Do not
  prepare, execute, select evidence, enter defaults, or grant consent by navigation.
- Reject ambiguous/unsupported action destinations without inventing controls.
- Prove all current registered actions are mapped; test navigation, filters,
  pagination, malformed catalogs, changed eligibility, and zero-effect browsing.

### 2. Review the full retained operation history

- Add an activity workspace with status/component filters and bounded pagination
  over all operations retained by the current launch.
- Preserve explicit result loading, worker-vs-assessment distinctions, remediation,
  and direct access to the assigned export workflow.
- Make pending, cancelled, failed, uncertain, and completion-log failures legible.
- Never infer that cancellation is a robot emergency stop or that a timeout means
  zero effects. Never offer automatic retries or restore authority from history.
- Verify older retained results remain discoverable beyond the current last-six UI.

### 3. Make multi-step form use resilient

- Preserve only appropriate ordinary drafts across unchanged-context rerenders;
  never persist confirmations, tickets, or device/evidence selections automatically.
- Bind draft handling to the last rendered session, source, state epoch, and exact
  action/field contract. Clear on execution or changed context.
- Handle dependent fields carefully: observation text must not survive if its
  selected intake question resets to a different question.
- Keep a same-setup ordinary draft held outside active fields when options differ.
  Require matching option reselection and explicit restoration, never automatic
  reselection or carrying an old answer into a different question.
- Restore focus only to an eligible same-context control. Do not weaken backend
  revision or currentness checks to accommodate UI editing.
- Test delayed input events, navigation, image-triggered rerenders, lost service,
  stale previews, option changes, and fresh launches.

### 4. Make component workflows understandable

- Review Camera, Arm, Board & tests, Task rehearsal, and Diagnostics with realistic
  service-backed fixtures in both launch modes.
- Replace raw status-only presentation with concise meanings and next actions,
  while keeping exact technical records available for developers.
- Clearly distinguish simulation, metadata review, one-frame capture, physical
  connection, installed calibration, and later motion/contact.
- Keep the locked legacy eye-on-arm task-model limitation visible until the
  actual static-camera migration is implemented and verified.

### 5. Operator handoff and acceptance

- Document startup, navigation, explicit control, result review, export, and safe
  recovery paths; maintain the current capability/verification matrix.
- Verify all public action forms and view records are reachable, keyboard-usable,
  and legible at desktop and narrow-screen sizes.
- Run actual renderer and service integration tests with modeled/incapable devices;
  label the coverage and remaining physical checks accurately.
- Use the separate read-only UI preview for visual review. Do not restart a live
  hardware session or execute device actions just to review interface changes.

## Goal completion criterion

Completion requires evidence for all five phases, not merely a new directory or a
green UI subset. All implemented actions and retained status/results must be
discoverable and controllable through their authentic public service contracts,
with usable failure/recovery and exports, while pending hardware and unfinished
software remain explicit. Keep the UI goal active until this audit is satisfied.

## Progress

- Planning/inventory and phase 1 complete. The Control Center opens every one of
  the then-current 129 registered original forms. A fixed-input selected regression
  executed 611 passing cases, with no failures or skips; desktop and narrow-screen
  read-only browser review is recorded in [the handoff](UI_CONTROL_CENTER_HANDOFF.md).
- Phase 2 complete: full retained launch history, recovery guidance and explicit
  result review, with 652 passing selected fixed-input regression cases and
  desktop/narrow-screen browser verification. This also verifies navigation to
  all 130 then-registered action forms. See [Activity handoff](UI_ACTIVITY_HANDOFF.md).
- Phase 3 complete: 748 selected fixed-input checks passed without skips, and
  desktop/narrow-screen editing was verified. See [draft handoff](UI_FORM_DRAFTS_HANDOFF.md).
- Phases 4–5 complete: component guidance, authentic catalogs in both modes,
  every current form/field and full public-view access, keyboard/narrow-screen
  review, accurate separation of gated arm diagnostics from general Connect,
  and the operator handoff. Final fixed-input acceptance executed **906 passing
  checks in 28 selected modules**, with no failures/errors/skips. See the
  [acceptance handoff](UI_APPLICATION_HANDOFF.md) and [operator guide](UI_OPERATOR_GUIDE.md).
- This UI goal is complete; the underlying physical commissioning and static
  task-model migration are not. Existing per-action gates remain authoritative.

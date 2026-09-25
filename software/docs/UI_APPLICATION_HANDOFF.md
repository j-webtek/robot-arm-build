# Operator UI acceptance handoff

2026-09-12. Scope: improve access to the existing local onboarding application;
no new hardware release, endpoint, provider or automatic physical action.

Start with [the operator guide](UI_OPERATOR_GUIDE.md). The five-phase
[implementation plan](UI_CONTROL_APPLICATION_PLAN.md) defines acceptance.

## Composition

- `ArrivalWizardService.view()` remains the public authority for the cached
  catalog, eligibility, setup identity and status. The current roster has 130
  definitions; held/reserved actions are visible as held, never fabricated as
  executable alternatives.
- `ui/static/app.js` renders component pages and original action forms. Control
  Center routes to those forms; guides filter the existing directories rather
  than maintaining a second command list. All fields use the same renderer.
- Every form uses explicit `/api/prepare` and separate `/api/execute`. Server
  revision checks, one-use tickets, worker gating, identity checks, exports and
  original-stage qualification are unchanged. No raw-command UI was introduced.
- Activity indexes only retained launch summaries. Full results load by explicit
  GET and stay bound to current launch/summary retention. Error guidance never
  promises zero effects, automatic retry or a robot stop.
- Ordinary drafts are a bounded memory-only presentation feature, not persisted
  setup or restored authority. Exact contracts are in [the draft handoff](UI_FORM_DRAFTS_HANDOFF.md).
- Diagnostics expose specialized records and a readable full service view.
  Browser JSON is not exact original evidence bytes, particularly for large
  numeric timestamps. Original export verification remains separate.

## Delivered component guidance and accessibility

Arm, Board, Task and Diagnostics now start with purpose, three workflow steps,
live-catalog form counts, filtered control/result navigation and export access.
Counts are withheld for malformed/ambiguous catalogs. The Camera workspace's
existing next-step/disclosure system is retained. Overview includes a short
expandable operating procedure.

The final catalog audit found stale Arm wording that described all feedback as
rehearsal-only even though three separately gated physical diagnostic actions
are registered. The Arm page and inert `arm_wizard_readiness.py` message/worklist
text now distinguish those controls from held general Connect/motion. The
existing wire state `PHYSICAL_BACKEND_PENDING` is shown as
`GENERAL_CONNECTION_HELD`; no state transitions, per-action gates, next-action
selection, worker dispatch or authority semantics changed. Zero-write serial
opening can still reset/move the controller; the warning is explicit. Tests use
the real cached catalog and incapable metadata fixtures, never those live actions.

All original forms have accessible names. Every current declared input has a
unique attached-page ID and associated label; declared help is connected through
`aria-describedby`. Native inputs/buttons/selects and focus-visible styling are
retained. Guided rehearsal may repeat an original component form on a different
page, but not duplicate its ID within one attached page.

Navigation is effect-free: no provider, discovery, prepare, execute or export is
called by a guide shortcut. Filters reset deliberately to the selected component.
The raw Diagnostics view ensures even unsupported specialized records remain
inspectable without presenting them as current qualified observations.

## Tests and boundaries

Earlier checkpoints are preserved, not combined as one source revision:

- Control Center: 611 passing selected fixed-input checks; see [its handoff](UI_CONTROL_CENTER_HANDOFF.md).
- Activity: 652 passing selected fixed-input checks; see [its handoff](UI_ACTIVITY_HANDOFF.md).
- Drafts: 748 passing selected fixed-input checks; see [its handoff](UI_FORM_DRAFTS_HANDOFF.md).
- `component-ui-20260912-01`: 9 passed, 10 failed assertions. The finite DOM did
  not assign an ID to its main node; guided rehearsal legitimately repeats forms
  on another page; browser parsing rounds nanosecond integers. The assertions
  were corrected to test attached-page uniqueness, actual focus identity and
  equality to the browser's parsed view. Original report is preserved. The UI
  now explicitly explains the browser/original-byte distinction.
- `component-ui-20260912-02`: **135 passed** across component, draft, catalog and
  activity modules. The 19 new component cases use authentic cached service
  catalogs in both modes, verify every original form/field, zero-dispatch
  navigation and exact record availability. One case runs a real note/export
  against temporary logs with an incapable runner.

- `component-ui-20260912-03`: **117 passed** across native-arm metadata UI,
  pure movement campaign/UI and diagnostic export checks.
- `component-ui-frozen-20260912-01/tests-01`: **884 passed** in 26 selected
  modules, zero failures/errors/skips, in 151.98 s. Input bytes verified unchanged.
  This is the checkpoint before the final navigation refinement.
- `component-ui-20260912-04`: **49 passed** after workspace-start scrolling and
  filtered offered-count clarification. Page navigation now focuses and scrolls
  to the workspace; ordinary refresh/image rendering does not move the viewport.

This is selected UI/service acceptance, not all-repository, received-hardware,
physical camera, serial or motion/contact acceptance.

- `component-ui-frozen-20260912-02`: snapshot creation rejected a concurrent edit
  to `MOVEMENT_CHARACTERIZATION_IMPLEMENTATION_PLAYBOOK.md`. Partial input was
  preserved without accepting a manifest.
- `component-ui-frozen-20260912-03/tests-01`: 875 passed and 9 failed old
  form-navigation assertions, which also counted the newly intentional initial
  workspace scroll. The form-link harness now consistently records only original
  form moves, just as it already did for focus; the new component harness
  independently asserts workspace focus/scroll. No form navigation or gate was
  removed to satisfy these tests.
- `component-ui-20260912-05`: **67 passed**, including the corrected navigation
  fixture, real held physical-arm catalog, inert readiness projection and
  camera/arm distinction checks.

## Final acceptance — complete

`component-ui-frozen-20260912-04/tests-01`: **906 passed**, zero failures, errors
or skips, across the exact expected 28-module selection in 157.01 s. Input bytes
and roster verified unchanged before and after execution. The selection includes
both launch modes, every one of the 130 current original forms, field labels/help,
all public records through the readable snapshot, draft invalidation, result
retention, camera publication boundaries, native-arm metadata, pure movement
simulation, original-record display and real temporary diagnostic exports.

Input manifest SHA-256 roster:
`1f13811179d50c3f2115f554ca5b4c108492f69fa30aba8e20e6bdf42c567ad3`.
Tested app SHA-256:
`b9af58e2d458919ee4e3962cb47623ca2d22885ac9bbbbe2339907190cd67156`.
JUnit SHA-256:
`752a71bceb43c2321f5ab4a3beca289b04f1a0aaaba7e097186e519f51763621`.

Browser review covered Overview instructions, Camera/Arm/Board/Task/Diagnostics,
control filters, result/export shortcuts, workspace-start navigation, ordinary
draft restore/reset, a real Tab focus transition, desktop and 390 × 844 layouts.
Final Arm wording was reloaded and inspected; viewport overrides were reset.
The browser-only preview submitted no action. Node syntax and Black checks for
the seven changed Python files passed; operator-guide links resolve.

Developer bundle: `software/runs/wizard-exports/operator-ui-20260912-01`.
It contains the exact tested implementation/selected test files, JUnit, full input
manifest and updated UI documentation. It is not a wizard-issued hardware
evidence package, a standalone installation or a release of physical execution.
Full source inputs remain at `.codex-preserved/component-ui-frozen-20260912-04/input`;
their pre-test documentation remains unchanged. The exported handoff is updated
after acceptance. Earlier failed/partial snapshots are preserved, not repaired.

All five phases of this UI enhancement are complete. Physical commissioning,
static-task migration and hardware qualification remain separate tracked work.

## Maintenance checklist

When adding an action, update its original page only if it needs a specialized
record renderer. Use the public catalog fields/section and the common form path;
do not add another executable dispatch path in a shortcut or browser callback.
Keep explicit held reasons and verify new records through the public view.

Run the component form audit in both modes, the Control Center roster/navigation
tests, Activity retention tests and draft/context tests. Add ordinary draft
fields only after reviewing their dependency and identity implications. Preserve
full-view access for developer investigation; specialized summaries must not
turn historical records, simulated results or worker success into readiness.

Use browser-only previews for layout changes. Reload after asset edits and reset
temporary viewport overrides. Do not restart or operate an existing hardware
service merely to take a screenshot. Current received-arm development shares
this source tree; narrow edits and fixed-input verification preserve that work.

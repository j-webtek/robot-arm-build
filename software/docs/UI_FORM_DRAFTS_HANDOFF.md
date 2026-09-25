# In-tab form drafts and current setup context

Phase 3 of [the operator UI plan](UI_CONTROL_APPLICATION_PLAN.md), 2026-09-12.

## Operator workflow

Ordinary draft fields now have a short status message and two controls:

- **Restore ordinary draft** restores ordinary values only for matching setup,
  action requirements and selected options. It never selects devices/questions,
  enters identity labels, checks confirmations or submits a form.
- **Reset form to service defaults** discards that form's ordinary draft and
  redraws its current server defaults. It does not save or execute an action.

Ordinary values survive navigation, explicit status refresh and image-triggered
rerenders when setup and options match. When an option resets, the draft is held
outside the active fields. Reselect all matching options and explicitly choose
Restore ordinary draft. Phone text must not appear in a keyboard task after a
target reset, nor may question A's observation appear under question B. Typing a
new ordinary value under different options replaces that action's held draft.

Setup changes, changed action contracts/eligibility, service loss and render errors
discard affected drafts. Submitting any reviewed action, including Stop, clears
drafts before the execution request, even if the outcome becomes uncertain.
Cancelling an unexecuted preview keeps ordinary drafts but destroys its ticket.
A new page load/browser restart begins with no drafts.

## Which fields are drafts

| Workflow | Ordinary values retained in unchanged setup |
| --- | --- |
| Diagnostic notes | Note text |
| Keyboard/phone planning and simulation | Non-sensitive test text |
| Synthetic movement preview/simulation | Plan JSON, nominal board transform JSON, nominal clearance |
| Synthetic camera settings/campaigns | Brightness offset or frame count |
| Camera operating proposal | Rationale and variance rationale |
| Physical and received-camera intake | Observed value, method, evidence description, bound to question/options |

This is an explicit 11-action, 20-field allowlist. Operator/reviewer labels, paths,
export/session/attempt identifiers, evidence/device/mode choices, native camera
control intents, confirmations and tickets are excluded. Excluded fields use
current service defaults; the UI does not claim every default is blank. A form
without complete current context explicitly reports draft retention unavailable.

Draft editing writes no localStorage, sessionStorage, files, logs or exports.
Existing launch-token sessionStorage handling is separate and unchanged. Limits:
one draft per action, 24 entries, 8,192 characters per ordinary field or its smaller
declared limit, and 65,536 ordinary-value characters total. Old entries may be
discarded with a notice to bound memory. Browser character limits do not replace
backend semantic, numeric or UTF-8 byte validation.

## Developer invariants

- Binding captures the last rendered session, cell, mode, source hash, state
  epoch and entire action/field contract. An old DOM event never adopts a new
  polled context. Duplicate identity/field names disable reuse.
- Pruning runs on every successful view read, even when another page's editing
  defers rendering. Disabled/removed actions cannot resurrect old drafts later.
- Selector changes clear ordinary fields before explicit restoration. Intake
  question units/requirements still update through the same selector handler.
- Same-page focus/caret restoration targets only a matching eligible ordinary
  control. Number inputs regain focus without unsupported caret APIs. Navigation
  does not pull focus back to another page.
- Existing displayed-revision checks remain unchanged: an unrendered progress
  poll does not silently upgrade the revision used by an existing form's preview.
- Late preparation responses are discarded after context/contract changes or
  cancellation. No stale ticket reopens. Connection loss clears previews and
  disables forms; it does not stop a robot or establish zero effects.
- Forms have accessible names. No backend endpoints, hardware providers, device
  operations, automatic retries or approvals were added.

## Browser-only editing preview

```powershell
.venv\Scripts\python.exe software/scripts/camera_ui_preview.py --scenario drafts
```

This scenario enables editing in six named note/task/synthetic-example forms.
Every POST still returns 405: there is no ticket issuer or worker, and even a note
cannot execute. Other forms remain disabled. Banner/descriptions identify fictional
editing-only behavior. Use the real wizard for actual eligible onboarding actions.

Try Task rehearsal → choose phone → enter non-sensitive text → Refresh status.
The target resets to the service default and the ordinary draft is held. Reselect
phone and choose Restore ordinary draft: its text returns without submission.

## Verification ledger

- `form-draft-ui-20260912-01`: 156 existing UI checks passed.
- `form-draft-ui-20260912-02`: 36 passed; one assertion failed because the finite
  DOM omitted an undefined focus ID after navigation. The assertion now handles
  that absence, retaining same-page focus/caret checks.
- `form-draft-ui-20260912-03`: 166 passed across drafts, actual intake/received
  camera views, shared wizard UI and camera disclosures.
- `form-draft-ui-20260912-04`: all 45 draft checks passed, including additional
  allowlisted fields and the editing-preview roster.

- `form-draft-ui-frozen-20260912-01/tests-01`: 734 passed, 3 skipped and 11
  fixture errors. The reduced input roster omitted the static-camera README
  required by the actual source collector and the exact public intake report
  used by three display tests. No production gate was relaxed. The failed
  snapshot remains preserved; the next snapshot includes both exact inputs.
- Browser review after reloading the final assets verified phone text is held
  after a target reset, explicit matching-option restoration, and reset to the
  current service defaults. The 390 × 844 layout remains legible; the viewport
  override was reset. Forms have accessible names. No action was submitted.

- `form-draft-ui-frozen-20260912-02/tests-01`: **748 passed**, zero failures,
  errors or skips, across the exact expected 21-module selection in 138.29 s.
  Input bytes/roster verified unchanged before and after. Input SHA-256:
  `76c66b311d611b65b04aa06a8c078e667aeec54a9194491b2b0f5ee46e26adee`.
  Tested app SHA-256:
  `06d92b7a4a2ecb48a30e0d27c6790b12702d1a821348574a8dbcc0eba012db1f`.
  JUnit SHA-256:
  `e8b2732261eb7e1cfecd556fdaae4ab7505bdb886d2ad00b5c8bba94e59bd2a3`.

These checks do not qualify camera/arm hardware, installed calibration or physical
motion/contact. The wider component/application audit continues separately.

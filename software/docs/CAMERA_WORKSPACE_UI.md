# Camera workspace UI handoff

Updated: 2026-09-12. Scope: presentation and hardware-free UI testing.

## What changed

The Camera page now starts with four fixed section shortcuts, the assigned
diagnostic export folder, and a button to open Diagnostics & exports. The next
offered action, saved-image panel, and recent activity precede the long list of
forms. Detailed records and unavailable forms remain available in disclosures.
Recent activity explicitly includes **all components**, not just the camera.

An operating-assessment operation has a **Load assessment checklist** button.
It reads the existing retained operation result and displays six named metadata
checks, a persistent operating-approval hold, and seven remaining requirements.
Structured JSON remains available below the readable checklist. Even six
satisfied checks are not a readiness score or permission to move the arm.

This is an interface improvement, not implementation of canonical stage-5
storage, operating approval, frame-freshness qualification, or calibration.
No camera, USB, serial, power, motion, or contact action was added.

## How the pieces connect

| UI interaction | Existing boundary | Effect |
| --- | --- | --- |
| Read camera page | `GET /api/view` | Cached service projection; eligibility stays server-owned. |
| Section shortcut | Fixed local anchor | Scroll/focus; technical records may expand. No request. |
| Open diagnostics | Existing page navigation | Displays assigned export folder and existing forms. Does not export. |
| Load assessment checklist | `GET /api/operations/{operation_id}` | Explicitly reads a retained result; no assessment rerun. |
| Preview/execute an action | Existing ticket workflow | Unchanged preview, explicit confirmation, and backend holds. |

The checklist is a **closed display contract**, not a cryptographic verifier.
It requires the named report step, exact expected check roster, boolean check
values, consistent failed-check/status lists, matching proposal references,
retained successful completion, and explicit false authority fields. Unsupported,
failed, incomplete, or unlogged reports show an unavailable notice instead of
passed checks. An assessment response with the wrong operation/action identity
is not displayed. Existing non-assessment result handling remains unchanged.

Loaded reports are always labeled historical. Rendering does not revalidate
original storage or restore connection/approval. The existing bounded result
cache is reused without automatic full-result requests; a changed operation
status prevents reuse of the old checklist.

## Files

- `software/src/rocell/ui/static/app.js`: navigation, camera layout, assessment
  display, existing result-loader integration. No new endpoint or backend state.
- `software/src/rocell/ui/static/app.css`: scoped workspace/checklist styling,
  wrapping, focus targets, and small-screen layout rules.
- `software/scripts/camera_ui_preview.py`: standalone, read-only loopback preview.
- `software/tests/unit/test_camera_workspace_ui.py`: actual JavaScript renderer
  tests in a finite DOM, plus preview HTTP-route checks.

## Review without hardware

From the workspace root:

```powershell
.venv\Scripts\python.exe software/scripts/camera_ui_preview.py --scenario incomplete
```

Open the printed local URL and select **Camera**. Other scenarios are `empty`,
`consistent`, and `held`. Stop a preview you launch in your terminal with Ctrl+C.

This preview is **not the hardware wizard**. All records are fictional display
specimens, all action forms are disabled, and POST requests return 405. It serves
only explicit asset/view/result routes on 127.0.0.1, does not expose arbitrary
workspace paths, and cannot export or access a device. The fictional completion
and authentication fields exist only to exercise the report presentation branch;
they are not actual logs, original evidence, or hardware acceptance.

Review checklist:

1. Open each section shortcut; verify navigation without an action preview.
2. Confirm the image area says cached/not live and handles no image clearly.
3. Load the fictional assessment. Verify satisfied and missing checks are distinct.
4. Expand remaining requirements; verify the operating-approval hold remains.
5. Open structured JSON only when needed for technical review.
6. Use the export shortcut; verify it opens diagnostics without exporting.
7. Review the `consistent` and `held` scenarios; neither grants approval.

## Verification

Final selected regression: **581 passed, 0 failures/errors/skips**, across 16
modules, including all **49 new camera-workspace cases** (69.84 seconds).
Node syntax checking and Black checks of the two new Python files passed.
The four edited source/test files had unchanged hashes before/after that run.
These are UI/software tests, not hardware qualification or a full-workspace
acceptance run. Earlier unrelated inventory failures were not part of this selection.

Development runs are preserved under `.codex-preserved/camera-workspace-ui-20260912-*`:

- `01`: 77 passed, 40 failed. The new test harness selected detached/wrong nodes;
  corrected to select the currently attached controls.
- `02`: 117 passed in the initial focused UI selection.
- `03`: 577 passed, 3 failed. New helper/result matching initially affected old
  renderer test seams; integration was narrowed to the named assessment action.
- `04`: all 93 selected new/probe/physical-camera UI cases passed after that fix.
- `05`: all 581 passed in the final broader selection, including the read-only
  preview HTTP test. JUnit: `junit.xml`; SHA-256:
  `0ba0684c8b9ea453742ad8936ad3cfb1e0c1c7231c855e1bcca13330dc325fb0`.

Review copies of the edited files, this handoff, and the final JUnit report are
under `software/runs/wizard-exports/camera-workspace-ui-20260912-01`. These are
developer review artifacts, not original-store evidence or operating approval.

Browser review used the standalone fictional preview at normal desktop sizing
and 390-pixel viewport width. The camera page, checklist, wrapping, and diagnostic
navigation were inspected visually; the temporary viewport override was reset.
No live camera frame, USB query, arm connection, or physical command was used.

## Next UI work

1. Turn the currently offered next-step guidance into a shorter guided journey,
   while keeping original action forms and all holds inspectable.
2. Preserve form drafts and relevant disclosure/focus state across safe status
   updates, without preserving confirmations or stale action tickets.
3. Add a dedicated historical evidence-review page once the backend publishes
   canonical assessment/review records. Do not invent a current approval flag.
4. Add broader keyboard/screen-reader and interrupted-request interaction tests.
5. Run a separately confirmed camera-only acceptance session through the real
   wizard after source/version review; do not restart an active hardware session
   merely to pick up UI edits.

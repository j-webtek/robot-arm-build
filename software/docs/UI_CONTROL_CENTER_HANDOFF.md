# Control Center: operator and developer handoff

Date: 2026-09-12. Phase 1 of [the operator UI plan](UI_CONTROL_APPLICATION_PLAN.md).

## What the operator can do

Open **Control Center** in the left navigation, or **Find any control** on Overview.
Search for a task, camera/arm operation, identity check, or export. Search includes
action labels, IDs, descriptions, hold reasons, and field labels/options. For
example, `phone` finds the existing task target options even when a description
uses the word Android. Search never selects that target or indexes user-entered
values or defaults.

Use Component and Availability filters to narrow the list. Twelve entries are
shown per page; Previous/Next controls cover the complete catalog. **Offered by
service** means the server is offering its form, not that hardware is qualified.
Held entries keep their exact backend explanations. Unsupported or ambiguous
entries remain visible but cannot invent a destination or action.

**Open action form** / **Inspect held form** navigate to the original component
page and focus its original form. A held camera disclosure expands when needed.
No preview, execution, device selection, confirmation, test, export, camera open,
or arm command occurs through these links. The existing form retains its
server-owned defaults and local/server prerequisites. Normal Preview action and
explicit ticket confirmation remain separate.

The directory is built from `ArrivalWizardService.view().actions`, not a second
registry. The phase-1 snapshot covered 129 definitions: Camera 82, Arm 19, Guided
rehearsal 15, Diagnostics 6, Overview 3, Tasks 3, Board 1. Counts are live catalog
inventory, not hardware capability/verification claims.

Later actions appear from the current service catalog without a directory code
change. Phase 2 verified navigation to all 130 then-current actions; see
[Activity & results](UI_ACTIVITY_HANDOFF.md) for the newer acceptance record.

## Integration and boundaries

- `app.js`: cached directory projection, bounded filtering/pagination, stable form
  targets across seven existing pages, and re-resolved navigation. Search/filter
  preferences are browser-memory presentation state only.
- `index.html`: Control Center navigation entry.
- `app.css`: directory/filter/result layout, including narrow-screen wrapping.
- `camera_ui_preview.py --scenario catalog`: real declarative action definitions
  in a separate read-only preview. All actions are disabled, POST returns 405,
  no wizard service is constructed, and no device provider is invoked.
- `test_wizard_control_center_ui.py`: actual renderer tests, complete roster/form
  coverage, a real cached initial service catalog, and explicit preview-boundary
  checks. Navigation-only tests make only `GET /api/view` requests.
- `test_wizard_physical_camera_ui.py`: one fixture now includes the action ID that
  actual public operation responses retain. Shared result identity validation was
  preserved, not weakened to accept the old incomplete fixture.

Current backend holds, timeouts, grants, storage, workers, endpoints, and action
eligibility are unchanged by this phase. Shared movement-result presentation
already present in the working tree was preserved.

## Hardware-free review

```powershell
.venv\Scripts\python.exe software/scripts/camera_ui_preview.py --scenario catalog
```

Open its printed loopback URL, choose Control Center, search `phone`, and inspect
the task form. The existing target default remains keyboard; finding a word is
not a selection. Clear filters and inspect held camera/arm actions. The preview
cannot execute them. Stop a preview launched in your terminal with Ctrl+C.

Browser review covered normal desktop and 390-pixel viewport widths, search,
the phone result, the original disabled task form, and filter wrapping. The
viewport override was reset. This is UI review, not actual hardware acceptance.

## Test ledger

Artifacts: `.codex-preserved/control-center-ui-20260912-*`.

- `01`: 26 failures from a duplicate helper declaration in the new test harness.
- `02`: 23 passed, 3 assertion wording mismatches in malformed-catalog tests.
- `03`: 27 passed, including navigation to every registered original form.
- `04`: 112 passed, including camera UI/disclosure/navigation regressions.
- `05`: 609 passed, 2 failures from old retained-result fixtures lacking action IDs.
- `06`: 611 passed, but the shared UI source changed during verification; this is
  not the fixed-source acceptance record.
- `control-center-ui-frozen-20260912-01/tests-01`: 609 passed, 2 setup errors.
  The isolated snapshot omitted the static board-support design required by two
  reference fixtures. That snapshot and its results were preserved unchanged.
- `control-center-ui-frozen-20260912-02/tests-01`: **611 passed, zero failed,
  errored or skipped**, across 17 selected UI/service modules in 81.53 seconds.
  This new snapshot includes the required support design. Its manifest verified
  unchanged before and after execution. Node syntax and the two owned Python
  files' Black checks also passed.

Fixed-input roster SHA-256:
`2ac63ddeeae81b9ba2b5ba2356643292ca31059c0fac7db2266e26b84d3138e9`.
Tested `app.js` SHA-256:
`86db3ac8432a3aa91672c8944f12d4df6a2aa3192810a2c9235334ea966236aa`.
JUnit SHA-256:
`965009b95a3ffed5f429358df217dfac9d00598920d9a4c45445fdb18f902834`.

Readable handoff, plan, JUnit and exact tested implementation copies are retained
in `software/runs/wizard-exports/control-center-ui-20260912-01`. This is a developer
review bundle, not a wizard-issued hardware evidence export. Documentation was
updated after the test run; the frozen input retains its original pre-run docs.

Passing these checks does not establish received-hardware verification, camera
operating-policy approval, installed calibration, RoArm serial release, or safe
physical typing/tapping. These remain separate requirements.

## Next phase

The [retained-activity/result workspace](UI_ACTIVITY_HANDOFF.md) is now implemented.
Next improve context-safe form editing, component guidance, and the full operator handoff. The full UI goal
remains active; a directory of controls alone is not completion of that goal.

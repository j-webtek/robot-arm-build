# Activity and retained results

Phase 2 of [the operator UI plan](UI_CONTROL_APPLICATION_PLAN.md), 2026-09-12.

## Operator workflow

1. Open **Activity & results** in the main navigation. The recent-activity card on
   each component page also has **Review all … retained operations**.
2. Search an operation label/ID, error or remediation. Filter by component or
   status, including **Needs review**, active work and unknown statuses.
3. Use **Older results** / **Newer results** at either end of the list. There are
   eight summaries per page, newest first; changing a filter returns to page one.
4. Review the visible outcome, retention state, completion-log state, exact error
   and remediation. Expand the summary for original evidence references.
5. Explicitly choose **Load latest full result**, **Load assessment checklist**,
   or **Load retained operation record**. This makes one read request for that
   operation. It never prepares, retries or executes it. Existing camera checklist,
   task feasibility and movement diagnostic result presenters remain available.
6. Use **Review diagnostics & exports** to inspect the assigned destination,
   existing receipts and export forms. Navigation does not export. Preview and
   explicitly execute the appropriate offered export action separately.

The Activity page is launch history, not an archive of all application launches.
The current backend retains up to 32 summaries and eight full results. It may
rotate older entries; exports have their own bounded attachment policy, shown
verbatim under **Service-reported retention & export policy**. A summary can
remain after its full result has been omitted. Loading it cannot recreate the
payload, and a new export cannot recover it. Review earlier verified exports if
they were saved. Separately pinned camera/arm attempts retain their own existing
component-page review/export workflows.

## What each outcome means

| State | Operator interpretation |
| --- | --- |
| Queued, pending or running | No completed outcome; inspect status before another action. |
| Succeeded | Worker/action completion, not hardware qualification or a passing assessment. |
| Failed | Read the exact cause and remediation; preserve evidence before any new action. |
| Timed out or uncertain | Effects and cleanup may be unknown. Do not replay as a recovery shortcut. |
| Cancellation requested | Request only, not confirmed cancellation or a robot stop. |
| Cancelled | Service outcome, not proof of zero effects, safe cleanup or emergency stopping. |
| Completion log unconfirmed | The action may already have taken effect even if the overall operation failed. Investigate logging; never rerun to repair a log. |
| Full result omitted | Summary only. Inspect earlier saved exports; missing data is not synthesized. |

Unsupported, malformed or duplicate identities do not produce inferred result
links. Unknown historical action IDs remain inspectable but are labeled unmapped
instead of guessing a component. History exceeding the UI's explicit defensive
display limit is reported, never silently truncated.

## Developer integration

- `app.js`: a bounded cached-history projection, searchable/paged Activity page,
  shared operation guidance and shared result rendering. The service remains the
  authority for status, source binding, retention and action prerequisites.
- Full-result reads use the existing `/api/operations/{id}` endpoint. The loader
  rechecks identity and launch/summary context before and after the request.
  A late result from replaced context is not accepted into the visible cache.
- Browser result cache remains bounded to eight entries. It is bound to session,
  cell, mode, source, operation/action IDs, status, retention, result hash and log
  state. Rotation or changed context discards the cached display; navigation
  never restores hardware authority. A cached record is not new evidence.
- Filter/page preferences stay in browser memory only. There are no new backend
  endpoints, persistence policies, device providers, connections or auto-retries.
- `test_wizard_activity_ui.py` runs the actual renderer in a finite DOM. It covers
  all 32 summaries, real service rotation after 35 harmless note records in a
  temporary log folder, explicit reads, result identity/currentness, failures,
  filters, exports navigation and malformed input. No device worker is invoked.

## Read-only visual preview

```powershell
.venv\Scripts\python.exe software/scripts/camera_ui_preview.py --scenario activity
```

Open the printed loopback URL and choose Activity & results. The preview contains
17 explicitly fictional records and the real declarative action roster. Every
action is disabled; POST requests return 405. Explicit result reads return only
fixed in-memory fictional examples. This is not the hardware wizard service.

## Verification ledger

- `activity-ui-20260912-01`: 62 passed, two fixture setup errors because the new
  pytest temporary directory's parent had not been created. Preserved unchanged.
- `activity-ui-20260912-02`: 209 passed across six selected Activity, Control
  Center, camera disclosure/workspace, task outcome and physical-camera UI modules.
- `activity-ui-20260912-03`: 41 Activity tests passed after the paging/recovery
  refinements and real 32-summary rotation coverage.
- `activity-ui-frozen-20260912-01/tests-01`: 651 passed, one failure in an older
  test that extracted `renderOperations()` by its previous exact signature.
  The fixture now tests the entire shipped interface, an explicit result GET and
  cached review. Original failure remains preserved; production gates were not
  weakened to satisfy it.
- `activity-ui-20260912-04`: all 45 Activity/probe-result tests passed.
- `activity-ui-frozen-20260912-02/tests-01`: **652 passed**, zero failed, errored
  or skipped, in 18 selected UI/service modules (85.19 seconds). The isolated
  input manifest verified unchanged before and after execution. This includes
  the Control Center's navigation coverage for all 130 actions now registered.
  Shared arm presentation additions were preserved.

Browser review covered explicit checklist and omitted-record loading, all three
fictional history pages, search, export navigation, desktop and 390×844 layouts.
Page controls are available above and below the results. The viewport override
was reset. Node syntax and Black checks for all three changed Python files passed.

Fixed-input roster SHA-256:
`3ba20e04ed6ceb0b4b1b836a972c62c88b4292c21b98a5318baa116067246d38`.
Tested `app.js` SHA-256:
`685044d9d658bb32261ff0b6c432ca18d1176edef9067d0f7c8c21472bf38280`.
JUnit SHA-256:
`136d3fd4d348fca33abd3fc6c70d2ea6695861d8da7dcbc9ad54c259085c40da`.

The developer review bundle is
`software/runs/wizard-exports/activity-ui-20260912-01`. It includes exact tested
implementation files, JUnit, input manifest and this updated documentation. It is
not a wizard-issued hardware evidence export. The full input remains separately
preserved; its documentation is the pre-run version.

These checks establish UI behavior, not physical camera/arm readiness, calibration,
safe motion/contact, received-unit qualification or all-repository acceptance.

Context-safe form drafts and the remaining component/application usability audit
are still open under phases 3–5 of the active goal.

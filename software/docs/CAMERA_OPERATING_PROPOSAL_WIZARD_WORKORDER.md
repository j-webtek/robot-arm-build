# Explicit operating-mode proposal in the camera wizard

Date: 2026-09-12. Camera-only continuation of the operating-evidence preflight.
Implementation scope: a logged **draft proposal**, not canonical stage-5 approval.

## Why this boundary

The wizard already publishes original probe/settings results and preserves
capture attempts. The new proposal codec is pure, but there is not yet an
original-store schema/reader for retaining its proposal and assessment as stage-5
records. Do not attach an approval button to cached data or silently mutate the
original journal. First make the explicit proposal usable through the existing
preview, execution, logging and export lifecycle.

## Delivery

1. Register a file-only camera action to propose the currently logged operating
   mode. Collect operator label, rationale and, for 8 fps only, an explicit variance
   rationale. Never choose another mode, apply settings or run a capture.
2. Bind the preview to the current settings publication, original-entry cache,
   source, launch and owner objects. Reject absent/incomplete entry, unpublished
   settings, stale identity, unsupported mode and changed context. New controller
   context/preview calculations and polling do not read files or devices; the
   existing Arrival preview source-fingerprint check remains unchanged.
3. At explicit execution, read only the fixed bounded purchase profile, rebuild
   the existing proposal bytes and recheck current context/source/Stop/deadline.
   Label the result as cached-subject draft evidence, not authenticated original
   storage. Keep original-entry/current-selection identity domains separate.
4. Publish a current draft only after the exact result and completion log have
   been retained. Failed logging, redaction, Stop or source/settings/owner changes
   withhold current publication. Bound attempts; never evict/replay old results.
5. Show the draft and clear limitations in the camera UI. Use the existing
   diagnostic export for the complete small proposal; do not include image
   pixels or duplicate large native evidence. Fresh application instances must
   not restore a current proposal or device permission from exported JSON.
6. Test public previews, logging, result publication, context invalidation,
   export and fresh-start behavior with modeled dependencies. Add inert UI and
   malformed-input coverage. Preserve concurrent arm edits and previous reports.

## Still required before an approval action

Add closed original-stage storage/reader schemas for separate proposal and
assessment subjects. Re-read entry/profile/probe/settings and selected capture
originals under the real owner scope, join USB speed/identity continuity,
ordered close/reopen and pixel verification, then retain/publish/read back the
assessment before a separate operator review. Test original journal transitions,
late cancellation, export and restart reconstruction. This draft action neither
does that work nor marks stage 5 complete. Existing preflight code remains a
   backend for that subsequent original-owner integration, not an automatic verdict
computed from an incomplete cached capture list.

## Implemented wiring

`CameraOperatingProposalWizard` is a process-local Arrival child. The camera
action is `physical_camera_operating_proposal`. The existing global ticket and
operation owner remain authoritative; no new connection manager, device runner,
M1 writer or automatic review action was introduced. The setup owner exposes a
small entry-cache accessor so this new panel does not copy the full USB history.
The acquisition owner returns exact cached staged-configuration bytes, not UI
display data. Existing logged-settings/current-owner checks remain prerequisites.

The action reads the fixed purchase profile with a 64-KiB bound and a 30-second
operation deadline. The eight-attempt history retains original draft bytes and
completion-log outcomes independently of rotating generic result cards. Current
publication requires matching context/owners, exact logged result, no redaction,
no Stop and an unexpired deadline after the final source check. Source/settings/
identity owner changes make the displayed draft historical. "Current" here means
current cached draft context, not fresh storage/device authentication.

Both browser and terminal present a closed bounded projection labeled DRAFT ONLY.
The browser next-step link opens the existing form; navigation does not prepare
or run it. The normal Diagnostics & exports action includes a dedicated
`camera-operating-proposals.json` attachment with retained drafts and completion
outcomes. Sanitized copies are labeled as changed bytes; no import/restore route
was added. A fresh application instance starts without a current draft.

Two existing exact boundaries were adjusted only for this feature: the registered
action roster includes the new draft action; its optional variance field allows
an empty string for a reference-mode proposal. Other text inputs retain their
existing validation. The proposal codec now converts malformed native-mode
errors into its closed contract error. This was caught by malformed UI tests.

## Verification status

Development checks exercised the actual wizard preview/execute/log/export and
frontend implementations with modeled predecessor data. They do not authenticate
the full original M1 history or connect hardware. The first broader 180-case
selection found that generic text validation rejected an empty variance rationale
even for 9 fps; this was fixed with an action-and-field-specific exception. The
exact action-roster test was updated for the new action without dropping any
existing arm/camera entries. Earlier failed reports are preserved, not acceptance.

### Final isolated regression

Snapshot: `.codex-preserved/camera-proposal-wizard-scoped-20260912-03/input`,
created 2026-09-12 21:48:52 UTC. Scope: software source/config/tests/scripts/docs;
software README/pyproject and `rocell.ps1`; controlled intake template; locked
kinematic URDF; and the 21 RC03 files listed by the system manifest. Selection
constants were set only in the inline developer process, not edited in the runner.
No hardware driver or native binary is included or executed.

Inventory: **1,280 files / 24,703,705 bytes**. Input roster SHA-256:
`c074cfbde7c8b0f996dd21fc06cdfd7ab4d436f058c2fa8daebb6115da3e8a51`.
Application source fingerprint before and after:
`4af0fd56a6b5f3e3a85ce9fcaf912b39bf1d8681a10981f9a14549737a61c110`.
Selected inputs matched before copying, after copying and after tests. This is
not a freeze of every workspace file or external dependency. Concurrent arm work
was not reverted or accepted by this camera change.

`tests-01/junit.xml`: **605 passed in 71.60 s**, zero failures/errors/skips;
all 605 collected identities executed. The new 35 backend and two UI cases cover
real tickets, preview/execution, completion logging, export, fresh instances,
bounded history, stale settings/source/owners, late Stop/deadline, redaction,
malformed modes, 8-fps rationale and the empty 9-fps exception field. Predecessor
original-entry/settings context is modeled, not authenticated original M1 storage.
Browser tests use the actual JavaScript with an inert DOM, not a live browser.
Terminal tests use the actual presentation method.

Adjacent selection: 82 evidence preflight, 28 guidance, 41 physical configuration,
28 acquisition, nine configuration retention, five configuration UI, 45 Arrival,
42 terminal, 14 camera next-step, 60 action catalog, 41 physical-camera UI, eight
guidance UI, 18 purchase-profile and 147 mode-entry cases. Counts include earlier
tests; they are not all new work in this increment.

JUnit SHA-256:
`46e44fe6ccf8320834a1f5aa5b88ded0bb169a858ebae749e01e9c9c0ee5de08`.
The adjacent `execution-audit.json` transcribes structured execution stdout and
is unsigned developer bookkeeping, not a full/smoke acceptance-lane certificate.
The isolated invocation used Python `-I`, copied imports, disabled plugin
autoload/bytecode/pytest cache and a fresh external basetemp. Python 3.10.10,
pytest 8.4.2 and installed dependencies are shared, not separately frozen.
Focused Black checks passed five owned Python files; Mypy passed three owned
production files; Node syntax checking passed the copied browser script. These
used existing developer tools; none were installed. Black/Mypy were absent from
the application venv, so the installed developer executables were used instead.
Shared files were not whole-file formatted.

Earlier attempts remain preserved: snapshot `01` was rejected for concurrent
input changes. Snapshot `02/tests-01` executed 605 cases (601 passed, one failure,
three setup errors) because the reduced copy omitted nominal-board/intake inputs.
Snapshot `03` adds their exact required files and reruns the same 16-module test
selection without skips or weakened assertions. Earlier failed reports and
unaccepted copies are not counted as acceptance.

### Developer/operator handoff

Readable export: `software/runs/wizard-exports/camera-proposal-wizard-20260912-01/README.md`.
It contains tested source copies, report, input manifest and audit. Final work
order/plan updates are post-test documentation, not changes to frozen inputs.

In the physical-mode wizard, after original mode entry and a current logged
settings result exist, select **Record an operating-mode proposal (draft)** in
Camera. Enter the operator label and rationale; 8 fps also requires its explicit
exception rationale, whereas 9 fps requires that field empty. Review the preview
and execute once. The camera card must say **DRAFT ONLY — NOT APPROVED**. Export
through Diagnostics & exports before closing. If held, inspect the logged reason;
do not bypass prerequisites or replay stale tickets. Opening this form does not
connect, configure or capture a device.

No physical camera, USB inventory, arm, serial, power, motion or live UI action
ran. The full original-history lane was not rerun. Stage 5, original-owner
assessment/review, installed optics and calibration remain open.

## Successor: read-only original assessment — 2026-09-12

The [original assessment work order](CAMERA_ORIGINAL_OPERATING_ASSESSMENT_WORKORDER.md)
adds an explicit file-only action using the logged draft and zero to two named
saved captures. It authenticates existing originals and reconstructs native
readbacks; the original stage journal and approval state remain unchanged.
All 27 new tests pass. The 632-case broader batch has 630 passes and two shared
inventory-contract failures, fully preserved in its ledger. This successor does
not replace this earlier draft acceptance record or complete stage 5.

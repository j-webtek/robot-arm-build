# Camera original-evidence assessment: implementation work order

2026-09-12. Software-only continuation; preserve concurrent arm work.

2026-09-13 continuation: the [saved-pixel work order](CAMERA_PIXEL_ASSESSMENT_WORKORDER.md)
extends this action to report v2 and verifies explicitly selected native files
against earlier retained launch-completion checksums. The metadata-only/no-pixel
statements below describe the original September 12 increment. Stage approval,
canonical retention, freshness and installed calibration remain unimplemented
by this continuation; hardware was not accessed.

## Outcome

Add an explicit wizard action after the logged operating-proposal draft. Reuse
the current camera session, original probe reader and configuration verifier to
check saved evidence. Do not open devices, initialize replacement stores, issue
permits, change settings or advance stages. Keep the existing draft action intact.

## Implementation sequence

1. Add a read-only original assessment adapter. Under exact CELL/SESSION/CAMERA
   ownership, authenticate setup, reconstruct the original native probe and
   current settings, and compare the proposal with the original entry and fixed
   purchase profile. Read zero to two explicitly selected settings captures.
   Reconstruct each capture's readback from retained native evidence and verify
   its original permit, result, admission settings and accounting.
2. Reuse the existing pure evidence preflight. Report the authenticated original
   inputs separately from unmet USB continuity, temporal reopen, pixels, freshness,
   operator review and installed-calibration checks. Never turn metadata agreement
   into an operating approval. Selecting no captures must visibly remain incomplete.
3. Add a bounded file-only wizard action with capture selections from retained
   attempts. Pin the draft, logged settings and owner identities at preview and
   execution; recheck source, Stop and the original deadline around storage reads.
   Retain results through existing operation logs and diagnostic exports.
4. Test pure composition, original M1 readback with explicitly modeled physical
   predecessors, and the real wizard lifecycle. Cover absent/changed originals,
   duplicate capture choices, mismatch, interruption, failed logging and restart.
   No test fixture is a production original-store import route.
5. Run an isolated regression and export readable results into the assigned
   workspace export folder. Keep old reports and incomplete runs.

## Deliberate remaining boundary

This increment authenticates existing originals but does not append a new stage-5
proposal/assessment journal schema. Its output is a retained diagnostic assessment,
not a canonical stage record. Adding such records changes the exact stage-layout
reader and needs its own full original-history/restart acceptance. Separate
operator approval remains unavailable until those storage transitions and all
required evidence joins are implemented. The complete items 1–2 of the next-step
roadmap therefore remain open until that subsequent integration is verified.

## Verification ledger

### Implemented wiring

The Camera action is `physical_camera_operating_assessment`, labeled **Check
proposal against saved original evidence**. Its two selects use the existing
settings-capture attempt catalog, default to explicit `none`, and reject duplicate
choices. A selected attempt's diagnostic context and the logged proposal are
pinned in the normal preview ticket. Navigation only opens the existing form.
Browser and terminal retain the draft-only warning and explain this next action.

`camera_operating_assessment_wizard.py` owns at most eight diagnostic attempts.
It checks the same proposal operation/bytes, settings, selected-capture context,
source, current owners, Stop and the original deadline. It does not introduce a
new CURRENT/approved state. A successful wizard operation means the requested
file check completed; inspect its report for missing evidence. Completion-log
failure or result redaction is not a successful original assessment. Its dedicated
export survives rotation of generic result cards and is sanitized normally.

`camera_operating_assessment_service.py` acquires the existing acquisition and
session operation locks, then exact CELL/SESSION/CAMERA storage leases. It reuses
the original probe and configuration readers. Their inert settings-plan check
does not issue a capture permit or invoke admission/dispatch. No replacement store
is created or automatically refreshed. Locks are released on success or exception.

`camera_operating_original_assessment.py` independently reads the stored native
probe, selected capture permits, terminal outcomes, native evidence pairs and
admission settings. It verifies their accounting, rebuilds capture readbacks and
calls the existing pure operating-evidence preflight. The complete original
record digest is compared again at the end, with original currentness checks.
It reads only the fixed bounded B0477 purchase profile outside the original store.

The report separately identifies original inputs authenticated **at read time**,
the metadata preflight and outstanding USB continuity, ordered reopen, pixels,
freshness, original-stage retention, review and installed-calibration obligations.
The nested pure-preflight report retains its own unmodified meaning: that layer
alone does not authenticate storage. No pixel file or device is opened by this
new action. Reading records uses transient storage lock bookkeeping; no original
stage, evidence package or campaign result is written.

### Developer checks so far

- Development `01`: the new pytest basetemp parent was absent; one case passed
  and 19 fixture setup errors occurred. Preserved, not acceptance.
- Development `02`: 19 passed, one export-fixture error in 214.37 seconds. The
  fixture assumed a nonexistent receipt field; the implementation exported
  correctly. It now checks the existing attachment naming and manifest verifier.
- Development `03`: 16 passed, one capture-selector-fixture error in 148.24 s.
  The mock field omitted mandatory field metadata used by the shared export
  action. The fixture now supplies the complete field shape. This run passed
  the actual service and two-saved-capture storage tests.
- Development `04`: 75 passed, two adjacent catalog tests failed in 3.97 s.
  The new action was added to the exact 300-second original-read action roster;
  the global timeout rule was not relaxed. The second failure is a shared
  inventory action's new `metadata_only=False` default versus its older expected
  dictionary. That arm/inventory behavior was not edited in this camera task.

The new tests separate real NTFS/M1 reads with explicitly modeled setup/physical
predecessors, real native metadata codecs and two tiny synthetic capture files,
real wizard/log/export lifecycle with a modeled assessment service, and actual
JavaScript in an inert DOM. This is layered testing, not a full original-history
camera qualification. New code has no injectable physical runner or restore API.

### Final isolated regression — partial green, not full acceptance

Snapshot `.codex-preserved/camera-original-assessment-scoped-20260912-01/input`
was created 2026-09-12 22:43:36 UTC. It contains 1,304 files / 24,870,932 bytes:
software source/config/tests/scripts/docs; README/pyproject/launcher; the intake
template, locked URDF and 21 exact manifest-listed RC03 files. The helper's input
selection was changed only in the inline process. No installed runner was edited.

Input roster SHA-256:
`bf798529b3890bfdf5aaea8c26b386af145fe8d256afc82c7e657e429f6f981a`.
Application source fingerprint before/after:
`cf1d67ff9b0eaabc3dc625d108f64ef4ff9f95af84d77d6c8189e8d9f6023d07`.
All copied inputs matched after execution. The full workspace and installed
dependencies are not frozen by this selected snapshot.

**632 collected/executed: 630 passed, two failed, zero errors/skips, 376.42 s.**
All **27 new cases passed**: 12 original-reader/service tests, 14 wizard lifecycle
tests and one actual-JavaScript inert-DOM form/navigation test. Adjacent passing
cases include proposal, preflight, guidance, configuration, acquisition, retained
attempts, terminal, next-step navigation, physical camera UI, profile and mode
entry. The two remaining failures are:

1. `test_arrival_wizard_service::test_physical_mode_has_explicit_metadata_only_device_action`
   expects the old power-disconnection message; the shared action now requires
   an explicit metadata-only or disconnected-power acknowledgment and returns
   `Confirm metadata-only inspection.` for neither.
2. `test_wizard_actions::test_metadata_confirmation_is_not_defaulted_to_true`
   expects a one-key result, while the shared action now includes the explicit
   default `metadata_only=False`.

That inventory implementation and these two assertions were left unchanged by
this camera task. Do not describe this batch as a fully passing regression or
full-workspace acceptance. Its audit has `all_selected_passed=false`. The camera
action's own exact catalog and timeout assertions pass. Existing physical/arm
permissions were not relaxed to make tests pass.

JUnit SHA-256:
`fd0c1731735749cd02f5853ebf1dfe8dfaa5c746b902b58dff39d394af2cec61`.
`tests-01/execution-audit.json` is a transcription of structured execution stdout,
unsigned developer bookkeeping rather than a full/smoke acceptance certificate.
The run used Python `-I`, copied imports, disabled plugin autoload/bytecode/pytest
cache and a fresh external basetemp. Existing Python 3.10.10, pytest 8.4.2, Node
and developer tools are shared; no dependencies were installed. Frozen-copy Black
checks passed seven owned Python files, focused Mypy passed four production
modules and Node syntax checking passed the browser script.

The 30-minute full original-history/restart lane was not rerun. Fresh-instance
wizard tests restore no draft/assessment permission; that is not original-stage
restart reconstruction. No physical device, USB query, arm, serial, power, motion
or live browser ran. Installed optics/calibration and canonical stage-5 review
remain open.

Handoff: `software/runs/wizard-exports/camera-original-assessment-20260912-01/README.md`.
It includes tested source copies, reports, copied input manifest and final
post-test documentation. Source-copy hashes are recorded separately from the
post-test plan updates. Shared files contain parallel work and are review copies,
not instructions to replace newer workspace files wholesale.

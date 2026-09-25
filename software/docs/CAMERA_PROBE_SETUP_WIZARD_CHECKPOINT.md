# Camera probe preparation in the onboarding wizard

10 September 2026. Implementation handoff for the existing connection plan and
developer playbook. This adds usable **file-only** preparation/review/export
controls; it does not release physical camera connection or robot movement.

## What is now connected

The existing action catalog, Arrival ticket/log owner, Setup operation owner,
original-record reader and diagnostic exporter work together:

1. `physical_camera_probe_prepare` previews an exact setup context. Execution
   consumes a one-use queue before writing the intent log. Failed logging does
   not dispatch the writer and does not make the queue retryable.
2. Preparation requires a current application-owned camera enrollment. Arrival
   records its fingerprint only after a successful native endpoint review and
   checks successful completion logs for generic inventory, native inventory,
   native identity and native review. Restoring a saved enrollment does not
   recreate that private publication receipt. This is metadata provenance, not
   proof the device is still present at a later activation boundary.
3. Under the existing stage-only transaction, Setup rereads the complete original
   v15 history, compares the preview, checks both installed purpose-specific
   runtime candidates, builds the exact probe preparation, retains and rereads
   its bytes, commits BLOCKED, then rereads the original v16 workflow.
4. `physical_camera_probe_review` previews the retained preparation hash. It
   requires the same current launch/enrollment, rereads the original preparation
   and installed files, then stores an exact review and commits WAITING_OPERATOR.
   The action does **not** run a probe or pass a physical stage.
5. Only the successful outer completion log publishes CURRENT. Stop, changed
   source/enrollment, uncertain storage publication and late log failure retain
   diagnostic history without granting current authority or automatic replay.

The original 180-second operation deadline covers all preparation/review steps.
Neither progress reporting nor repeated readbacks renew it. The existing
individual installed-file checks keep their independent shorter limits.

## Storage correction discovered by the real test

The ordinary V2 evidence writer accepts WAITING_OPERATOR/REVIEW_PENDING, not
BLOCKED. The first real NTFS test exposed the mismatch hidden by the writer's
modeled storage callbacks. The general restriction has **not** been relaxed.

`M1PhysicalCameraTransaction.store_camera_probe_review` now has a narrow path:

- Exact active CELL + SESSION leases; no CAMERA lease, stage selector or caller
  supplied filename, label, media type or authority Boolean.
- Exactly the entry and the referenced preparation, bounded by their role sizes.
- Full structural stage-5 preparation layout and matching original hashes,
  session/source and timestamps before publication.
- A private V2 primitive for the blocked camera-mode stage only. The normal
  immutable-package, current-head and publication checks remain shared.
- A retained partial review prevents a second review write. Review and the
  reopening journal event remain separate fallible boundaries.

This storage check supplements, not replaces, Setup's full original-history
authentication. It grants no permission to interact with a device.

## Operator interface and exports

Camera actions include **Prepare bounded camera probe** and **Review prepared
camera probe**, with a required, initially unchecked file-only acknowledgment.
The camera page shows a small preparation/review status, hashes and attempt
status. It explicitly distinguishes entry awaiting preparation review from a
ready or connected camera. The export navigation button only opens Diagnostics.

Diagnostics includes **Export camera probe preparation**. Its assigned default is:

`C:\Users\Jack\Desktop\robot-arm-build\software\runs\wizard-exports`

Each invocation creates a fresh bundle using the existing exporter. It preserves
complete retained preparations, reviews, queued attempts and uncertain write
boundaries in bounded readable JSON parts. Credentials are redacted before
partitioning. The report distinguishes original-byte preservation from redacted
copies and includes hashes for reconstruction. Restore verifies diagnostic
content only; it cannot reconstruct an authenticated original store or a live
enrollment owner.

Ordinary **Export logs** includes a small pointer to this separate bundle action
instead of embedding the deep preparation tree. Its existing global limits are
unchanged. The new family has its own 7 MiB input bound and still fits the ordinary
exporter's existing part/count/total-size limits; over-capacity data is rejected,
never silently truncated. Export remains available after source/log failures.
A completed bundle's receipt is retained even if completion logging then fails.

Preview binds the diagnostic body. A source check may downgrade its publication
label from CURRENT to HISTORICAL, but may not substitute changed records or
attempts without another explicit preview.

## Code map

| Responsibility | Existing owner or new module |
| --- | --- |
| Action forms and bounded inputs | `wizard_actions.py` |
| One-use preview/intent, current metadata provenance, completion and export receipt | `arrival_wizard_service.py` |
| Queue, operation lock, cached display and partial diagnostics | `physical_camera_setup_service.py` |
| File-only preparation/review sequence | `camera_probe_setup_service.py` |
| Original context comparison | `camera_probe_preparation_readback.py` |
| Narrow blocked-stage review storage | `commissioning_camera_persistence.py`, `physical_onboarding_v2.py` |
| Complete bounded preparation diagnostic bundle | `camera_probe_setup_export.py` |
| Shared diagnostic tree encoding, existing defaults preserved | `physical_camera_identity_export.py` |
| Browser cards and navigation | `ui/static/app.js` |

## Verification boundaries

New tests separate three claims:

1. Public Arrival/Setup/writer tests run real tickets, logging, codecs, current
   owner checks and actual export files with explicitly modeled predecessor
   authentication/storage/software observations. They cover both nominal actions,
   one-use queues, Stop, changed owner/source and completion-log failure.
2. Metadata-publication tests run the actual public metadata actions using
   incapable, OS-shaped fixture providers. No host metadata API runs.
3. The separate real Windows NTFS M1 test retains/readbacks preparation and
   review across separate transactions and rejects wrong targets, timestamps,
   stale heads and partial-review replay. Its earlier stage evidence is explicitly
   synthetic: this is storage behavior, not physical or full-history qualification.

Browser tests execute the actual projection/renderer code and verify closed
display fields and navigation without dispatch. Earlier full-original v16 reader
tests remain separate from this minimal public writer fixture. No camera, serial
connection, arm power or capable native worker is executed in this increment.

Final selected verification on this increment:

- Application fingerprint:
  `9567797a0c59f7d76f37cd69d8e2ec4b8a1653ef3c33f3214dddd1fcf159cc8e`.
- `probe-wizard-final-20260910-02.xml`: **287 passed**, 284.16 seconds, zero
  failures/errors/skips. This is a selected 17-file regression run, not the
  complete repository suite. It includes the new public writer/export/UI and
  metadata tests, real M1 storage tests, existing V2/Arrival/export regressions,
  and the complete original v16 reader composition. Modeled observations in
  those tests do not become hardware qualification because the suite passed.
- Mypy: all ten changed production Python modules clean. Black: all seventeen
  changed production/test Python files clean. Browser JavaScript syntax clean.
- Both launcher modes passed `-Check`: zero operations, camera and arm
  `NOT_CONNECTED`, preparation `NOT_PREPARED`, no physical authority, and the
  exact confirmed workspace export folder.
- All 46 native files indexed by the earlier installed-runtime checkpoint match
  their previous hashes. No rebuild, repin or capable native execution occurred.
- Failed drafts, including the real blocked-stage storage failure that exposed
  the bug, remain under `.codex-preserved`; they were not overwritten or deleted.

A report-only handoff copy is saved beneath the confirmed export directory in
`developer-checkpoint-camera-probe-wizard-20260910-01`. It is not an importable
commissioning session or a standalone application/source archive.

## Next developer steps — still part of the full application goal

1. Compose this public writer with the entire original-history reader and genuine
   M1 store in one fresh scenario. The current separate lanes do not claim that
   end-to-end original-hardware qualification has happened.
2. Implement substantive admission facts under the exact CAMERA lease: original
   reviewed preparation, accepted unit continuity, fresh endpoint/driver checks,
   applicable physical-condition requirements, dependency epochs and bounded
   output/storage capacity. Keep the default-denying facts provider until those
   checks are real; never substitute a checkbox or loaded snapshot.
3. Connect that admission to the existing v2 acquisition/campaign owner and its
   existing paired-result, settings/image ingestion and publication path. Do not
   create a second camera controller or a generic raw-command browser endpoint.
4. Add public probe/preview tests with an incapable producer plus real storage,
   including Stop before/after dispatch, cleanup failure, source change, stale
   frames, incomplete result pairs and export after interruption.
5. Continue capture/baselines, calibration against the static overhead camera and
   measured placemat, then the identity-bound RoArm connection/startup/feedback
   workflow. Camera readiness must not imply arm readiness or contact permission.

Hardware arrival alone is not the remaining dependency. The physical connection
and commissioning software joins above are still unfinished. The overall goal
remains active; this checkpoint is not a declaration of a finished robot app.

# Settings-capture wizard integration work order

Continue from the verified original-admission checkpoint at source
`580c3e02c2a8582fb4282e057b321de0516fa66c3a55406ca6090802fea1ef5c`.
The previous goal turn was verified progress (499 selected tests). This work
implements the public operation/log/export/presentation join described in
`CAMERA_CONFIGURATION_ADMISSION_HANDOFF.md`; it does not redefine the overall
camera/arm application goal or grant any physical qualification.

The requested delegated agents were inspected and remain terminal with reported
usage-limit errors. Continue locally; do not create replacement tasks or consume
usage-reset credits. No hardware operation is part of this implementation work.

## User-visible operation

Add a distinct `physical_camera_configuration_capture` camera-section action.
The existing `physical_camera_configuration` action only stages reported settings;
the existing `physical_camera_capture` remains the separate stage-6 freshness
action and is not enabled by this change.

The new form asks for a current operator label, an explicit current report that
the arm actuator supply is disconnected, and consent to apply the selected
electronic settings/read them back/capture one frame. Both checkboxes default
off. There is no browser budget, device pathname, output folder, arbitrary JSON,
worker selection, source override, permit or hardware-qualified field.

The action preview must describe one-frame bounds, possible camera activation
and settings writes, current manual lens requirements, required cleanup and
separate physical-stage acceptance. It is neither streaming nor arm startup.

## Stable settings publication versus per-capture state

Add a cached, data-only settings-intent projection from the acquisition service.
It contains source/Session/runtime/identity bindings, original capability digest,
candidate settings epoch and typed mode/control intent. It deliberately excludes
the most recent frame and transient workflow status: successful capture changes
those, but must not change which settings the operator selected.

After the existing settings action validates its result, logs successful
completion and publishes the exact configuration, pin a bounded publication
reference containing the original operation/result/log fields plus this stable
intent binding and exact enrollment binding. Withdraw it before a new settings
action is queued/logged. It is process-local and cannot be restored from a report.
Do not infer it from a `CURRENT` display or from an old rotating result alone.

Admission also requires the pinned successful probe completion and the current
logged metadata owner, the same original Session/enrollment, the current staged
settings, stage-5 reviewed setup context and no conflicting pending publication.
The full original reader and M1/core still authenticate actual records and own
the new permit; cached UI references cannot replace that authentication.

Separate the pure current-intent comparison used during an active capture from
the idle-action availability check. Staging the capture result necessarily makes
publication pending; it must not invalidate its own current settings binding.
Stop, changed identity/source/settings/Session or failed logs still invalidate it.

## Server-owned capture budget

Use the existing fixed settings profile: 5,000 ms native capture, one frame,
equal per-frame/total byte limits. Derive the output allowance from the verified
selected YUY2 mode and a documented server policy, bounded by the existing 64 MiB
frame limit. Unknown stride must not become a guessed physical observation;
use a conservative bounded allowance or refuse unsupported sizing explicitly.
Include native/ingested/preview/metadata/shared-record headroom using the existing
original admission provider. No new time limit or native binary is introduced.

## One-use operation lifecycle

1. Preview binds current original setup, settings publication, candidate plan and
   enrollment. Recheck the exact context before inserting a new operation.
2. Allocate a bounded queue entry keyed by the server operation ID before intent
   logging. An uncertain intent/log outcome consumes that request: it cannot be
   silently retried. Subsequent explicit requests have new keys and must satisfy
   the original no-quarantine/current-state checks.
3. Clear any previous displayed image before intent logging, without fabricating
   a new capture or discarding the immutable original probe/settings evidence.
4. Claim the queue entry once, preserve the exact Session/enrollment owner objects,
   and call `run_original_configuration_capture` with the original Stop event,
   finite outer deadline and current-context validator.
5. Carry the new public action ID through the retained-result contract. Bind it
   to the actual capture profile, not merely `CONTENT_VERIFIED`; reject attempts
   to relabel settings capture as stage-6 capture or vice versa.
6. Preserve returned diagnostics across failure. Validate exact staged data,
   recheck source/identity/Stop and persist completion before image publication.
   Failed completion logging, redaction, mismatch or scope exit withholds data.
7. Pin a bounded completion per retained configuration attempt independently of
   rotating general results. Final publication failure must update its diagnostic
   outcome; a known native attempt may still have a failed UI publication.

## Export and presentation

Add `physical_camera_configuration_attempt_export` as device-inert housekeeping,
available after a queued/partial/failed attempt and after source or log faults.
Use the user-confirmed workspace export directory. Export the exact selected
cached attempt: queue, immutable original references, admission, actual settings
and readback, cleanup/accounting, completion and failure. Unknown counts remain
unknown. Later requests must not contaminate the separately pinned probe export.

Share the existing bounded readable native-buffer projection, credential
redaction, chunking and reconstruction machinery. Give configuration diagnostics,
snapshot and parts distinct schemas/names; do not relabel a configuration packet
as probe evidence. Keep old probe entry points, schemas and limits unchanged.
Reports decode to diagnostic data only, never Session/permit/admission owners.
Do not copy raw image pixels or exceed general-log attachment limits. A general
export can contain a small pointer to the dedicated attempt export.

Add a lightweight browser status card showing staged settings/readback scope,
current operation outcome, export availability and pending qualification. Existing
physical-camera presentation remains strict about mode/control/identity/frame
bindings. Navigation and polling perform no provider or filesystem work. Reuse
the existing operation form/ticket/polling and retained-image route.

## Verification and delivery

- Closed form/action catalog, default-off consent and server-owned budget tests.
- Successful settings publication reference from actual logged actions; absent,
  failed, changed, restarted or stale references cannot authorize a capture.
- One-use queue and ticket drift, Stop at queue/native/log/publication boundaries,
  failed intent/completion logs, failed cleanup, source/identity changes, bounded
  history and explicit subsequent requests. No automatic retry or stage PASS.
- Correct stage-specific result IDs at dispatch/service/publication/browser joins.
- Dedicated report reconstruction, readable native data, redaction, missing and
  partial observations, changed export ticket, exact folder and immutable probe
  export across later captures. No device I/O during export or polling.
- Actual local M1/NTFS/core/ingestion composition with incapable native owners;
  label modeled setup seams rather than claiming full-history qualification.
- Full original-history composition and maximum-history timing remain required
  gates; use the actual complete readers where possible and record any missing
  acceptance coverage. New physical claims require received hardware evidence.
- Run existing probe, configuration, workflow, coordinator, UI/export regressions
  and both startup checks. Preserve fresh JUnit paths, failed drafts and a copy-only
  checkpoint in the assigned export folder; do not alter hardware-build files.

The full goal still includes camera mode/reopen/freshness qualification, measured
overhead calibration and RoArm identity/connection/startup/feedback, followed by
separate motion/contact authority. Do not mark the goal complete for this slice.

## Completed public-integration slice

Implemented the closed public settings-capture action, exact logged-settings
reference, one-use queue and final image publication, distinct retained-result
identity, dedicated per-attempt export, cached status card and navigation-only
guidance. The server owns the one-frame budget. Stop/source/identity/log/history
and cleanup failures retain diagnostics and cannot authorize replay or motion.

At source `440d3f7a3adae328493e1cf48b8f3cca5e2415639f04ae083031730cc13f364e`,
the final selected suites passed 679 distinct tests, with no failures, errors or
skips. Both actual startup checks passed without hardware access. See
`CAMERA_CONFIGURATION_WIZARD_HANDOFF.md` for the component map, final reports,
copy-only checkpoint, explicitly modeled boundaries and concrete next bridge
between full semantic originals and actual M1/NTFS execution. The original-history,
maximum-history, qualification, calibration and arm work above remains open;
the overall goal is not complete.

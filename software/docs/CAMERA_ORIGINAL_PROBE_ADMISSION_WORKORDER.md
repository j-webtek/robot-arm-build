# Original camera-probe admission: implementation workorder

Current implementation: [public original-bound camera probe](CAMERA_PROBE_PUBLIC_WIZARD_CHECKPOINT.md).
Substantive original facts/capacity now join the existing M1/v2 dispatcher through
the wizard's one-use intent/completion path, with dedicated attempt diagnostics.
The linked checkpoint supersedes the historical pending-item lists below.
Stage-5 acceptance, public capture/calibration and RoArm connection remain work;
no physical camera or arm was used to verify this increment.

Previous implementation: [probe preparation wizard checkpoint](CAMERA_PROBE_SETUP_WIZARD_CHECKPOINT.md).
The file-only Setup/Arrival writer, current logged metadata provenance and
separate bounded export/UI are now implemented. The real NTFS test required a
narrow blocked-stage review writer; the original ordinary-write restriction was
preserved. The readback-only checkpoint below is historical. Admission facts,
physical probe/preview and arm connection are still unfinished; use the current
handoff's next steps, not the old pending-item list, to continue.

10 September 2026. Continue the full connection-wizard goal from the verified
internal v2 handoff. The previous turn made concrete progress; this work targets
the remaining original-record dependency, not another independent dispatcher.

## Current evidence and implementation choice

The Session reader accepts the full original history through v15 camera-mode
entry. Its default facts provider deliberately denies camera effects. The core
requires stage `camera_mode_controls` to be `WAITING_OPERATOR`; the existing
journal does not allow a WAITING-to-WAITING transition. Therefore preparation
must be recorded before a distinct explicit review reopens the waiting state.
An arbitrary Boolean or imported snapshot must never be the missing provider.

Use an additive v16 preparation/review suffix on the same original snapshot:

1. Read the full accepted v15 history. Collect current reviewed enrollment and
   both installed purpose-specific software observations, without opening a
   camera. Bind the exact probe plan, original mode-entry record/event, source,
   current launch, original session, and operator label in a closed preparation.
2. Retain preparation and commit `WAITING_OPERATOR -> BLOCKED` with its fixed
   event. BLOCKED means the camera test is not yet admitted, not a hardware fault.
3. Retain a separate exact-preparation review, then commit
   `BLOCKED -> WAITING_OPERATOR`. This is eligibility for further admission checks,
   not stage PASS, connected state or native release.
4. On readback, establish the closed suffix layout, authenticate all predecessors
   on the SAME complete snapshot, then derive/compare the preparation context.
   Preserve v15's closed public reader and old limits. An incomplete publication
   is historical-only and cannot be automatically resumed or replaced.
5. Connect substantive original facts and current output/storage-capacity checks
   to the existing M1 transaction/core and service guard. Validate continuity with
   the accepted received unit; matching a newer enrollment to itself is insufficient.
6. Wire the existing Arrival intent/completion and Setup operation owner to these
   records, then the already-tested v2 dispatch. Preserve full failed diagnostics,
   fresh reopen without replay, Stop behavior, and bounded camera-specific export.

Stage 6 capture/qualification and RoArm startup/feedback still follow this initial
probe step; their implementation remains part of the full goal. No live hold is
removed by constructing these records. Do not execute capable native workers
while developing. Test structural records separately from authentic predecessor
composition and actual on-disk storage; label modeled facts in every lane.

The three previously delegated agents are currently terminal with account usage
errors. Root continues locally; no alternative accounts or usage reset is used.

## Implemented in the current increment

The pure preparation/review subjects and the **original Session reader** now
implement v16. This is not yet a public Prepare/Review/Connect action.

- `camera_probe_preparation.py` binds the current enrollment, exact v2 probe
  plan, mode-entry record/event and both purpose-specific software observations.
  It uses a separate 3 MiB / 40,000-node / 26-level compound-record limit, while
  the enrollment and worker IPC retain their existing independent limits.
- `camera_activation_expectation.py` shares the existing expectation derivation
  with saved enrollment verification, without creating a live enrollment owner.
- `camera_probe_preparation_layout.py` verifies the two closed journal events
  and the four complete/incomplete publication states. Stage evidence citations
  preserve V2's chronological order and repetitions, not a deduplicated set.
- `camera_probe_preparation_readback.py` joins the complete preceding v15
  verifiers on the same snapshot, then checks the new context against those
  originals. Current plan/store/source/unit, generic USB identity, location paths and
  previously observed driver fields must agree. New metadata operation IDs
  cannot reuse IDs from the accepted history. These consistency checks alone
  do not authenticate a current collector or permit device access.
- `physical_camera_session.py` reads the new labels through its existing
  stage-only transaction and full evidence audit. One entry, one preparation
  and one review are the only admitted stage-5 record roles. Unknown extra
  records, future stages and malformed/incomplete journals remain rejected.
  The v16 cache has its own bounded allowance; old public readers stay closed.

The workflow envelope reports the **current** head and evidence-inventory hashes.
Individual earlier records and their hashes remain unchanged. Confusing those
two levels was caught while adding the full-history composition test.

The user confirmed the existing export destination:
`C:\Users\Jack\Desktop\robot-arm-build\software\runs\wizard-exports`.
No arm, camera or camera-capable native worker was opened by this increment.

## Required next implementation (do not treat readback as completion)

1. Add file-only preparation/review operations to the existing Setup owner and
   Arrival one-use intent/completion lifecycle. Authenticate the v15 predecessor
   under the same stage transaction before writing; preserve every uncertain
   write/commit boundary. Do not allow automatic replay of a partial attempt.
2. Obtain enrollment from the current Arrival-owned metadata workflow, with
   logged collection/review operation provenance. Do not accept an uploaded
   preparation or a reconstructed live enrollment as the missing current owner.
   Recheck both installed runtime observations under the original deadline.
3. Implement the substantive admission-facts reader under the exact CAMERA lease,
   fresh identity checks, physical-condition requirements, all eight dependency
   epochs and output/storage capacity. Keep `_denied_facts` as the default until
   this join is complete. Later calibration outputs must not create a circular
   prerequisite for an initial bounded camera probe.
4. Extend the camera-specific diagnostic bundle, including new preparation/review
   and failed attempts, before exposing the new actions. The general exporter has
   deliberately smaller depth/node/attachment limits: do not put the entire v16
   workflow in its source attachment or silently increase its global limits.
   Preserve original hashes and explicitly label any redaction. A diagnostic
   export must never recreate a live owner, reopen devices or authorize replay.
5. Wire admitted execution to the existing v2 acquisition/dispatch owner. Test the
   actual UI intent/completion, Stop and preview-publication path with an incapable
   producer and real local storage. Reopen/export must not perform device I/O.
6. Continue camera capture/baselines/calibration and the RoArm identity/startup/
   feedback path. Physical connection does not authorize keyboard/phone contact.

Hardware arrival alone is **not** the remaining blocker: these software joins
still need implementation and verification before the wizard is usable for
physical camera connection. The overall application goal remains active.

## Verified checkpoint, 10 September 2026

Application fingerprint:
`82de01cb6c825845bf75b448bd40b7fda3c26e7ac182488fa9d70b6e371fe7d1`.

- `probe-original-final-20260910-02.xml`: **567 passed**, 141.64 s. Selected
  preparation, enrollment, original-reader, mode-entry, export/queue/persistence
  and existing v2 handoff regressions; includes existing actual M1 tests with
  modeled device facts. This is not the entire repository suite.
- `probe-original-full-20260910-05.xml`: **1 passed**, 156.05 s. Complete v16
  original-reader composition, unchanged earlier subjects/current envelope,
  legacy-reader refusal, prerequisite tampering rejection and context/operation
  reuse checks. Storage, device observations and the original-reader clock are
  modeled in this lane; its elapsed time is not physical performance qualification.
- Total final selected coverage: **568 passed**. The two new test files contain
  37 cases. All failed draft reports remain preserved alongside the final reports.
- Mypy: seven changed production modules clean. Black: nine changed Python files
  clean. Both launch modes passed `-Check` on this fingerprint, with zero
  operations, camera/arm `NOT_CONNECTED`, no physical authority and the confirmed
  workspace export folder.
- All 46 native files indexed by the earlier installed-runtime checkpoint still
  match their hashes. No native file was rebuilt, repinned or executed here.

Copy-only checkpoint destination:
`software/runs/wizard-exports/developer-checkpoint-camera-probe-original-20260910-01`.
The bundle contains application/test inputs and reports, not an importable
commissioning session, an authenticated current enrollment or device permission.

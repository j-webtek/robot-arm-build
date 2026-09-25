# Camera v2: original diagnostic retention integration

Date: 2026-09-10. Implementation work order following the
[tested process supervisor](CAMERA_ACTIVATION_SUPERVISOR_CHECKPOINT.md).
The full camera/arm wizard remains the goal; this storage work does not replace
runtime review, original admission, UI integration or hardware verification.

Implementation update: steps 1–6 now have installed code and focused tests; see
[the storage checkpoint](CAMERA_ACTIVATION_STORAGE_CHECKPOINT.md) for exact results
and boundaries. Steps 7–8 remain unfinished. Publication reserves space for three
terminal records within the unchanged shared quota; pre-effect capacity admission
still belongs to the future scoped campaign.

## Current constraints verified in source

- `cell_commissioning_coordinator.py`: legacy `CampaignEvidence` and aggregate
  retained campaign payloads are limited to 128 KiB/four artifacts. `WorkerReceipt`
  requires integer counters. `RetainedUncertainCampaignExecution` is USB-only.
- `commissioning_m1_persistence.py`: immutable records are limited to 1 MiB each,
  2,048 files and 32 MiB across the complete camera family. The audit binds every
  record to its original request/domain and complete cell-global attempt ledger.
- `native_camera_activation_evidence.py`: the new run record is bounded to 512 KiB.
- `native_camera_activation_supervisor.py`: private before/after detail is bounded
  to 1 MiB and includes actual registration, original timing and cleanup results.
- The v15 camera-entry reader accepts the original entry suffix, not completed
  acquisition. A separate stage-5 acquisition successor is still necessary.

## Implementation design

1. Define a closed camera-only pair: the exact v2 run record and its matching
   supervision detail. Validate all shared fields, actual executed registration,
   preparation, pipe boundaries, timing and owner observations. These artifacts
   are private evidence, never UI status or execution authority. Keep the legacy
   `CampaignEvidence` type/limits and v1 record bytes unchanged.
2. Define fixed v2 probe/capture action identities. Bind the new retention policy
   to exact physical-camera registration/stage/lease/effect contexts, not to a
   caller Boolean, filename, arbitrary schema string or larger requested budget.
3. Serialize each artifact into ordered parts of at most 64 KiB raw bytes. Use
   derived attempt/role/part names, closed envelopes and exact hashes/lengths.
   At most eight run parts plus sixteen supervision parts are needed. Each
   enclosing JSON record remains below the existing 1 MiB record limit.
4. Write all parts immutably, then publish the exact final index. No overwrite,
   retry, deletion of partial records or new directory selected by the caller.
   Preserve the shared 2,048-file/32 MiB aggregate limits. Publication failure
   leaves partial evidence and an unresolved/uncertain original attempt.
5. Extend the complete family audit with the closed camera-specific record kinds
   and names. Validate partial parts against their original armed attempt even
   without an index; require every indexed part exactly once for complete evidence.
   Reject extras, wrong domains, changed ordering, missing parts and inconsistent
   hashes/lengths. Do not filter the original ledger or hide sibling records.
6. Add a camera-specific retained execution result: either an ordinary exact
   `WorkerReceipt` with fully known counters or an explicit uncertain outcome
   without a fabricated receipt. Retain the bounded evidence before sealing
   uncertainty, including a failed final scope check. Preserve the existing
   USB-only uncertain result type and behavior.
7. Join the new scoped v2 campaign to the supervisor and active consumed M1 scope.
   Revalidate the complete preparation/current context before REQUEST/RELEASE,
   not another permit consumption. The runtime still requires independent review
   and the application still derives original admission facts.
8. Join original stage-5 acquisition, image verification, UI summaries, Stop,
   explicit private exports and fresh-app reopening. Ordinary logs must not expose
   raw base64 pipe buffers containing private paths/device identity.

## Acceptance evidence required

- Pure paired-artifact and chunk round trips at exact ceilings, including unknown
  counters, invalid/missing fields, altered preparations, registration substitution,
  incomplete pipe delivery and before/after cleanup inconsistencies.
- Partial publication after every part/index boundary remains auditable and
  cannot become a known successful attempt; no original is reused as a retry.
- Real local immutable storage/leases for a complete camera-specific retained
  execution and fresh reopening, with explicitly modeled camera/process facts.
- Core scope/Stop/uncertainty tests retain returned evidence before uncertainty,
  never fill unknown counts with zero and never allow camera records in USB,
  source-only, serial, rehearsal or mismatched action/stage contexts.
- Existing v1 campaign, complete-family audit, USB uncertainty, quota and export
  regressions remain unchanged. Received-hardware tests stay separately pending.

Use fresh test/report paths and the confirmed export parent
`C:\Users\Jack\Desktop\robot-arm-build\software\runs\wizard-exports`.
This work order is a design/verification checklist, not proof that these joins
have already been implemented or that the physical connection is enabled.

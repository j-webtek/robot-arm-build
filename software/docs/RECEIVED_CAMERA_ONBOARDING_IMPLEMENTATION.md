# Received-camera onboarding implementation work order

2026-09-08. Follows the verified static-camera design workflow. The previous
goal turn was progress: actual design/original/UI joins, scoped tests and real
assigned-folder setup/export/restart completed. The full connection goal remains
active; this work must make original camera onboarding usable, not substitute
another synthetic receipt for the actual received unit.

## Outcome and boundaries

Implement original stage-3 camera/passive-workcell submission, assessment,
distinct review, restart and wizard actions. Reuse the existing sixteen-question
notebook, guarded attachment inbox, structured CameraReceiptInspection and pure
received-camera assessor. An explicit separate action may request stage-4
identity only after an original reviewed stage-3 PASS. It must not execute OS
inventory or connect anything by opening that stage.

Stage-3 PASS means the original receipt record meets the fixed receipt checks:
all sixteen observations and their originals, structured purchased B0477/16 mm
identity/condition checks, and 17.5–18.5 mm board thickness accommodation. It
does not accept installed geometry, flatness, support strength, focus, USB mode,
native runtime or calibration. Those have distinct later-stage ownership in the
unchanged catalog. The pure completeness assessor is not itself stage authority.
The original store must read/authenticate every referenced package before review.

No nominal values fill observation fields. UNKNOWN remains default. INT-017 and
INT-024 prose are never parsed into structured identity or lens-mount claims.
Flatness observation is required, but its limit remains deferred to the target
accuracy budget. Missing nominal tolerances, mass/thread/bench acceptance limits
are not invented. No activation, firmware, driver or build-release flags change.

## Original evidence and revision model

Each explicit collection has a new receivedcamera identifier, current source,
original cell/session/header/prerequisites, original reviewed static hashes,
explicit receipt-entry event, collection operator/launch and predecessor triple.
Store an exact camera_receipt-owned notebook original, selected original media,
submission, deterministic assessment and distinct review. Source-stage media
references cannot be relabeled as camera-stage originals; a new explicit copy
must read and retain exact bytes under correct provenance.

Use an append-only started → retained → review-pending → reviewed chain. Preserve
every partial retention boundary without automatic repair or replay. Allow up
to four complete collection/review cycles, and a new explicit cycle only after
reviewed BLOCKED. A reviewed PASS freezes receipt collection and makes explicit
identity-stage entry eligible. A refresh/reopen reads originals only.

Reuse the current inbox limits: 2 MiB per original file, 4 MiB per selected set,
up to sixteen unique selected originals per cycle. OBSERVED rows require a
selected original; multiple rows may cite the same file. Structured inspection
requires a purchase original and at least one image original. Keep original
media private; diagnostic JSON carries original references, not image bytes.
Source and static-stage budgets remain unchanged. Add explicit stage-owned
budgets for at most four notebook/submission/assessment/review sets and their
media. Do not expand a global budget silently or drop a domain's original logs.
Measure combined export sizes and exact reconstruction before choosing whether
the new family fits the existing export or needs an explicit separate bundle.

## Application/UI integration

The service must be inert on construction and GET, operate outside the Arrival
lock, verify source/Stop/current original context before and after every owned
mutation, and publish CURRENT only after exact result retention and a durable
completion log. Discovery, draft creation/editing, submission, review and next
stage entry remain separate user actions. Defaults never select a file, device,
acceptance answer or reviewer. Preserve full failed-attempt diagnostics.

Reopening must expose the exact frozen submitted notebook/inspection and its
missing requirements. A revised draft must be explicitly requested; if prior
observations are carried forward, retain their original times/actors/provenance
and distinguish them from fresh observations. Do not rewrite past source-stage
draft bindings or silently call an old observation newly measured.

Add a state-driven next-step block at the top of Camera, ahead of advanced
diagnostics, with links to actual server-eligible action forms. In a fresh setup,
present initialize-new and discover-existing as explicit alternatives; do not
choose automatically. The block navigates only, never previews/executes from a
render or current-state poll.

## Parallel ownership and acceptance

- Camera agent: stage-3 original submission/assessment/review pure contracts,
  reuse of strict received-unit semantics, DTOs and bounded verification tests.
- Original-store agent: v6 exact stage-3 chain/restart and minimal private prefix
  refactors preserving v1–v5; stage-owned quotas and original media readback.
- UI agent: next-step navigation first, then shared actions/views/publication and
  combined or explicit-stage export after service APIs are agreed.
- Root: concrete wire/API agreement, application transaction/service, draft and
  attachment integration, full public flow, failure tests and developer handoff.

Test UNKNOWN and mismatched received records, all observation/attachment roles,
wrong stage/header/source/predecessor, same reviewer, explicit successor/no
automatic entry, real original restart, Stop/drift/readback/cleanup/log failure,
inert views, both renderers and exact complete assigned-folder exports. Use real
controlled files and storage where available, but explicitly modeled physical
observations for positive tests. Actual hardware remains unqualified.

## Operator workflow implemented in this change

Launch from the repository/workspace root using
`.\start-rocell-wizard.ps1 -Mode physical`.
Use `-Ui terminal` for the same service-backed forms without a browser.
The Camera page's next-step links navigate to forms only; they never execute
an action. Start a new original camera session or explicitly discover/reopen an
existing one. Complete its source and static-design workflow first. A source
or design blocker must be resolved in its owning workflow, not bypassed by
entering nominal measurements here.

After reviewed static design PASS, explicitly request camera receipt:

Before starting a draft, preview the action and check its displayed remaining
action budget. The existing limit is 32 primary actions per launch. A full receipt path normally
needs 21: start, sixteen row records, file discovery, submission, review and
identity-stage request; corrections use additional actions. If earlier source
work has consumed that headroom, restart and explicitly reopen the original
before creating the launch-local draft. Export remains available at the cap,
but exporting a draft does not make it automatically reloadable after restart.

1. Start a **BLANK** received-camera draft. All sixteen questions retain their
   original wording/unit; no model number or design dimension is prefilled.
2. Record observations with their instrument/method, evidence description and
   operator label. Use UNKNOWN with a reason when the observation is unavailable.
   An incomplete notebook may be submitted to obtain its explicit missing list.
3. Put original evidence in the assigned
   `software/runs/physical-intake-inbox` directory and run file discovery. Choose
   opaque discovered files in the form; there is no arbitrary path/upload field.
   Each OBSERVED row requires an original. One original can support several rows.
4. Separately choose UNKNOWN or RECORDED for the received-camera inspection.
   RECORDED requires observed manufacturer/product/serial, lens/condition and
   package answers, an original purchase record and an inspection PNG/JPEG.
   Explicitly attest that the inspection was performed for this submission;
   previous narrative answers are not parsed into a fresh inspection.
5. Submit the notebook, originals and inspection. The wizard writes/readbacks
   each stage-owned original, assesses it, then waits for exact-subject review.
6. A distinct procedural reviewer chooses ACKNOWLEDGE_EXACT or REJECT. The first
   preserves the deterministic verdict; it cannot turn missing records into
   PASS. REJECT always blocks. Operator labels are not authenticated identities.
7. After BLOCKED, explicitly start BLANK or REVISE_LAST. Revised observations
   retain their original actors/times and source notebook hash; they are not
   relabeled newly measured. Reattach originals explicitly for the new cycle.
   At most four complete cycles are permitted. Partial original writes are held
   for inspection, not automatically repaired or replayed.
8. After reviewed PASS, explicitly request the separate camera-identity stage.
   This only records WAITING_OPERATOR. It does not enumerate USB, launch a native
   helper, acquire images, connect the robot or authorize power/motion/contact.

Drafts are launch-local until submitted. Submit or export before shutting down;
reopening restores exact submitted originals, not an unsaved draft. A failed or
unlogged candidate draft is retained separately and must be exported before
another edit/submission can replace it. Refresh never promotes that candidate.

## Diagnostic handoff

The configured default is
`C:\Users\Jack\Desktop\robot-arm-build\software\runs\wizard-exports`.
Use the normal log export for application/source/static diagnostics and the
explicit **received-camera metadata export** for this complete stage family.
The normal export contains a coverage/pointer notice, not an implicit copy of
received originals. Keep both bundles when reporting a cross-stage problem.

The dedicated bundle contains up to four complete cycle families plus draft and
failed-attempt metadata. It uses the existing manifest-last, non-overwriting
exporter and verifies the exported files. Private raw media remain in the
original store; the metadata bundle includes their references/hashes only.
Credential redaction can change exported text, and is reported rather than
claiming byte-identical originals. Review other private information before
sharing. A diagnostic export is never a restore/import or physical credential.

Recovery export is allowed for retained historical/source-changed records and
after a logging failure. It cannot republish stages. A successfully written
export receipt remains available even if Stop or another log error arrives
after file publication.

## Code ownership and maintenance

| Boundary | Owner |
| --- | --- |
| Original questions, explicit immutable draft revision | `physical_intake_notebook.py` |
| Closed forms, blank/UNKNOWN defaults | `physical_received_camera_fields.py` |
| Original notebook/media/submission/assessment/review contracts | `physical_received_camera_submission.py` |
| Store grammar, complete byte verification and restart | `physical_received_camera_readback.py` + `physical_camera_session.py` |
| Transaction/source/Stop ownership | `physical_camera_setup_service.py` |
| Explicit actions, candidates, publication and recovery metadata | `physical_received_camera_service.py` |
| Separate complete metadata bundle and reconstruction | `physical_received_camera_export.py` |
| Tickets, action lock, durable logs, shared UI | `arrival_wizard_service.py` + browser/terminal renderers |

Do not add a device provider to receipt collection. Implement actual identity,
native-runtime, optical/mounting qualification and later RoArm startup in their
separate planned owners. Keep nominal design checks distinct from observations,
and receipt completeness distinct from acceptance of installed hardware.

### Original event protocol

`HEX` is the uppercase suffix of the current `receivedcamera-<32 hex>` ID.
The initial stage-3 WAIT was already written by the static-design owner; do not
write a second WAIT event, which the original transition contract forbids.

| Explicit operation | Original state/event |
| --- | --- |
| First submission | Retain notebook first, then selected originals, submission and assessment; commit `CAMERA_RECEIPT_COLLECTION_SUBMITTED_HEX` → REVIEW_PENDING |
| Distinct review | Retain exact review; commit `CAMERA_RECEIPT_COLLECTION_REVIEWED_PASS_HEX` or `...BLOCKED_HEX` |
| Successor after reviewed BLOCKED | Commit `CAMERA_RECEIPT_COLLECTION_STARTED_HEX` → WAIT with the previous same-stage submission/assessment/review references, then retain the new cycle |
| Identity-stage request after reviewed PASS | Commit `CAMERA_IDENTITY_REQUESTED_HEX` → stage-4 WAIT with no cross-stage evidence references |

Every retention is stage-owned. Metadata labels are
`received-camera-{notebook,submission,assessment,review}-v1:<id>`; selected-file
labels are `received-camera-original-v1:<id>:00` through `:15`. Reopening audits
the full original journal, predecessor chain, labels, every exact metadata/media
payload, and the configuration record against the full inventory. It does not
replay an uncommitted event. Keep the received-stage quotas separate from the
earlier source/static quotas.

Discovery/draft actions have a 60-second application budget; original mutation
and export actions have 120 seconds. Stop/source/deadline checks surround owned
filesystem operations. These are bounded cooperative operations, not a promise
that a blocked OS filesystem call can be forcibly interrupted at a deadline.

The service returns PENDING before publication. Arrival retains the exact
worker result and durably logs completion before publishing CURRENT. Cached GET
views never discover files, load a driver, scan devices or repair the store.
An interrupted submission may already have immutable originals: explicit
original refresh retires a byte-identical submitted editable draft so that the
actual pending review is visible. It never silently discards a distinct new
revision or rewrites a previous observation's actor/time.

Verification results are recorded below only after the relevant runs complete.

## Verification ledger — this increment

These are scoped software results, not received-hardware qualification:

- New pure submission/assessment/review contracts: 49 cases passed. The
  physical observations and media references in positive cases are modeled.
- New original reader: 51 cases passed, including a real NTFS store/restart
  sequence through retained assessment, retained review, committed receipt PASS
  and separate identity WAITING_OPERATOR. Its positive observations are modeled;
  original storage, byte checks and restart are real. The maximum source/static/
  received inventory test used 32 + 3 + 80 references, 1,509,261 cached bytes,
  depth 13 and 47,156 nodes within unchanged depth/node limits.
- Prior source/static/intake/epoch reader compatibility: 261 passed, with three
  separate actual-NTFS cases deselected in that specific compatibility run.
  The new actual-NTFS received-camera case ran independently and passed.
- Root notebook suite, including seven explicit relaunch/provenance/budget
  cases: 61 passed. Existing setup/static/source service suites: 65 passed.
- New service integration: final full run 35 passed in 200.50 seconds; seven
  same-instance retirement/recovery cases also passed independently. This
  uses actual design files/codecs/inbox and explicitly modeled source/M1 facts.
  It covers UNKNOWN submission/review BLOCKED, explicit provenance-preserving
  revision, modeled complete receipt PASS, separate identity entry, original
  subject recovery, invalid inputs/changed source/Stop, incomplete writes, exact
  completion publication and real diagnostic export with explicit redaction.
- Dedicated metadata exporter: final root run 22 passed in 10.00 seconds;
  mypy/Black clean. Four full near-limit cycle families, current/failed drafts
  and the last attempt fit six attachments (665,389 bytes in the measured
  pre-provenance-field fixture); exact unredacted subjects reconstruct correctly.
- Pure received assessment and prior camera receipt semantics: 81 passed.
- Final combined fields/service/submission/export run: 120 passed in 306.70
  seconds. These selections overlap the individual results above.
- Final broader UI/Arrival/action/export regression, including the new terminal
  and public received-camera cases: 1,662 passed in 379.43 seconds. This is a
  bounded selection, not the entire repository suite. The final source
  fingerprint remained unchanged after all tests and the local smoke.
- Browser/public Arrival selection: 18 passed in 136.28 seconds on the frozen
  source. Both strict renderers accepted actual service-produced UNKNOWN/BLOCKED
  and modeled complete receipt/PASS/identity-WAIT states. Both exports verified;
  the dedicated family reconstructed every original metadata document/hash.
  Stop/source/log-failure cases and high/low action-budget previews passed.
  Original storage/physical facts were modeled in these composed tests.
- Terminal received/legacy selection: 55 passed in 40.48 seconds, including
  thirteen new cached-render/form cases. Only the exact received submission
  roster permits 33 fields; all other terminal forms retain their 24-field cap.
- Thirteen core Python files and the Arrival/action owners pass Black and mypy;
  terminal checks and Node syntax validation also pass.
- Live read-only local browser inspection confirmed readable Camera layout,
  visible next-step alternatives and a navigation-only link to the correct
  initialization form, with no console errors. No action was prepared/executed.
  The temporary browser tab and local server were closed afterward.

### Frozen source and package

Final source/configuration fingerprint:
`616b690f10aab2eb85ac7dec1917b8d34ec5c584ec9c6eab01abae6725e114c6`.
Both physical and rehearsal `-Check` launches report READY_FOR_DIAGNOSTICS,
the configured workspace export folder, received status NOT_STARTED and native
release false. Physical mode exposes all seven received-stage actions; normal
server-side holds still apply.

An offline, no-dependency-install wheel has 280 code/UI entries byte-identical
to this workspace:
`software/runs/received-onboarding-wheel-a0f5a4cf84004efa8374d50124e641d6/rocell-0.1.0-py3-none-any.whl`.
Wheel SHA-256:
`de8bdf11828b9f24831ea545a0ef3744edde59425f7b02cdff68ae8dbcc4ac6b`.
This is a software package check, not native-runtime or hardware qualification.

### Actual assigned-folder save, export and restart

`wizard_workspace_sources_smoke.py` completed successfully against that frozen
source. It initialized real local original storage, collected actual source and
prerequisite facts, reviewed the deterministic BLOCKED assessment, rotated nine
notes, exported, shut down, discovered/reopened the exact original in a fresh
launch, and exported again. It did not invent a physical isolation observation
or bypass the source blocker to enter later stages.

- Original launch: `wizard-12cf253f1a844ad593a4abc9ffd7f7e1`.
- Reopened launch: `wizard-adc346871d8e4e4f96656243bad64691`.
- First verified export, 369,721 total bytes:
  `software/runs/wizard-exports/wizard-20260909T012417756245Z-5763a76a0d6349009a17e5f26029013b`.
- Reopened verified export, 472,852 total bytes:
  `software/runs/wizard-exports/wizard-20260909T012426456818Z-9ba0da908d204b87ae2d1f6840c1d51d`.
- Original source review SHA-256:
  `b5d8ab2f77f0ae8e38e15f90f045d501978ff5fe0fc0884afe81edfb112198b6`.
- Original configuration SHA-256:
  `d94797c91e851a17b2d0d4b274317a636e990ad3a228fac5825fa73b9fbbff90`.

Original documents, configuration and stage states survived unchanged. Source
remained BLOCKED and every downstream stage remained PENDING. The actual
reopened export snapshot also passed the real JavaScript renderer in a GET-only
fake-DOM harness and the terminal projection, including the received-stage
metadata pointer with NOT_STARTED status. Both service owners shut down.
No device inventory, native helper, camera capture, serial connection, power
or motion action ran. No existing store or export was overwritten.

## Remaining connection work

The newer [identity work order](CAMERA_IDENTITY_ONBOARDING_IMPLEMENTATION.md)
implements the metadata-only original stage-4 submission/review integration
outlined below. This received-stage checkpoint and its verification hashes are
historical; follow that newer document for current files, bounds and results.

The application still lacks the completed original-session physical camera
identity/native-runtime/acquisition release and RoArm startup/feedback joins.
Existing USB/COM/native-camera metadata tools are diagnostic precursors, not
those completed original-stage connections. Existing rehearsals remain the
hardware-free way to exercise later behavior. No test here
changes the frozen release, physical power, motion or contact gates.

The next smallest integration is an original stage-4 identity submission and
review owner, reusing `WizardNativeCameraEnrollment.export_snapshot()`, strict
native metadata validation and `selection_from_enrollment()`. It should bind
the full server-owned evidence to the original reviewed receipt trio and exact
identity-entry event; add closed stage-owned roles/readback; then publish only
after original verification and completion logging. Reopening must not run
inventory again, and later stage entry must remain a separate action.

Current metadata describes endpoint/devnode/container/location/parents. It does
not supply every unit serial, driver, negotiated USB3 or reconnect/reboot
stability observation required by `B0477UvcIdentity` and HZ-009. Missing evidence
must assess BLOCKED, not be synthesized from nominal product information.
Test source/endpoint/helper/predecessor mismatch, missing identity facts,
partial retention, lost completion, restart and fresh-endpoint drift before
joining that original identity workflow to acquisition.

Before expanding operator throughput, consider an explicit validated bulk
notebook-edit operation or a separately reviewed draft-restoration workflow.
Neither exists in this increment. Do not silently increase the global action
budget, parse metadata exports as original authority, or autosubmit observations
to work around the current launch-local draft constraint.

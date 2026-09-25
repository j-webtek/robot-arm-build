# Static-camera design and received-unit onboarding

2026-09-08. Work order following
[source-stage reassessment](SOURCE_STAGE_ADMISSION_IMPLEMENTATION.md), under the
camera/arm developer playbook. Stage-2 collection, original review and explicit
stage-3 entry are implemented and verified in the scoped tests below.
The received-unit assessor is a separate pure foundation. The subsequent
[received-camera implementation work order](RECEIVED_CAMERA_ONBOARDING_IMPLEMENTATION.md)
owns stage-3 original submissions, reviews, UI and dedicated diagnostics.

## Purpose and integration boundary

This work closed the stage-2 path from WAITING_OPERATOR through design
collection/review to explicit received-camera entry, reusing existing strict
design/profile/support loaders.
Do not introduce a second fake physical receipt, relax native release, or edit
Freeze-011/RC03. Design consistency is distinct from installed qualification.

The intended chain is source-stage reviewed PASS → explicit static-contract
entry → actual file-derived design collection/assessment → exact review →
explicit received-camera entry → original observations and attachments →
deterministic received-unit assessment/review. Stage 4 identity then remains a
distinct explicit, identity-bound metadata operation. No step in stages 2–3
opens a device, starts a servo or executes a native camera helper.

## Stage 2: design contract

- Reuse the selected architecture, purchased B0477 profile and static support
  validators and their cross-source hashes. Keep 610 × 457 mm nominal board,
  planned 1000 mm entrance-pupil height and nominal lens/mode values labeled as
  design values, never measurements or a selected received native mode.
- Collect bounded exact source bytes/hashes and the original source-stage,
  prerequisite, header and explicit entry-event lineage. Recheck source/Stop
  before and after the collection and original-store storage scope.
- Add pure retained-byte verification, reusing/refactoring existing pure
  validation functions where needed; reopening must not reread the current
  hardware configuration or accept caller-written PASS booleans.
- Preserve all architecture/profile/support blockers, HZ-007/HZ-010 and false
  physical release flags. The design-only verdict may be PASS when all strict
  software checks agree. It does not require pretending those blockers cleared.
- Require an exact original assessment and separate procedural review before
  stage-2 PASS. Do not automatically enter stage 3 on review or reopen.

## Stage 3: received camera and passive workcell

- Use the 16 original stage-owned questions from the prerequisite record,
  existing guarded inbox and draft/observation validation. Do not reuse the
  synthetic-camera receipt schema for physical originals.
- Keep UNKNOWN as default. Retain original files only after explicit discovery
  and opaque selection. Preserve the recorded model/serial/lens identity, actual
  board/bench/camera measurements and instrument/method alongside their hashes.
- Reuse or extend exact-subject review and quantitative checks, including the
  17.5–18.5 mm board-thickness accommodation. INT-005 flatness must be measured
  here but its acceptance stays deferred to the later accuracy budget.
- Distinguish collecting a complete received-unit record from qualifying USB
  identity, optical focus, mounting, load, collision or native camera release.
  Do not manufacture thresholds for requirements that remain open.
- Implement missing pure assessment contracts first and test actual-vs-modeled
  provenance. If a stage-3 decision needs a genuine build choice or acceptance
  threshold absent from authoritative files, report it rather than invent it.

## Original store and publication

Append closed stage-owned labels/events after the existing v4 source prefix.
Preserve v1–v4 behavior and immutable source/intake subjects. Support partial
retention and retained-but-uncommitted assessment/review without replay. Audit
the complete original journal and exact subjects, not an invented replacement
store. New schema versions may add explicit stage-owned budgets; do not silently
expand the existing source-stage 32-reference/4 MiB budget or generic IPC/export
limits. Measure aggregate cache and export size in the final application join.

New service owners must be inert on construction/GET; serialize explicit
operations, bind current tickets, work outside the Arrival lock, retain complete
failure evidence and publish only after exact result retention and durable
completion logging. Provide a single cached camera onboarding view with original
stage states, design vs observed values, pending requirements and next action.
Original private files stay separate from sanitized metadata exports.

## Parallel implementation ownership

1. Windows/camera agent: stage-2 strict source collector and pure contract codecs,
   minimal reusable pure-parser extraction and tests. No M1/UI mutation.
2. Original-record agent: closed stage-2 successor readback and restart tests,
   preserving exact source-prefix behavior; coordinate budgets/schema with root.
3. UI agent: service-backed actions/rendering/export integration once root/API
   contracts are fixed; inspect stage-3 existing receipt semantics in parallel
   and identify actual missing acceptance inputs without fabricating them.
4. Root: service composition, transaction ownership, original publication,
   stage-3 workflow/assessment decisions, cross-agent integration and verification.

## Acceptance evidence

Exercise actual controlled design files, source drift, changed cross-source
locks, wrong original subjects, Stop, stale head, failed store/lease exit/log,
UNKNOWN/mismatch measurements, distinct review, explicit next-stage entry,
original restart and full chosen-folder exports through the public wizard.
Use hardware-free models only for observations not actually made. Preserve
partial failures. Test both renderers and prior source/intake/dispatch behavior.
This work must not be called completion of the whole camera/arm goal: received
identity, native runtime/output ownership, physical acquisition and firmware-
bound controller startup/feedback remain separate required joins.

## Operator sequence in the current application

Start from the workspace root:

```powershell
.\start-rocell-wizard.ps1 -Check -Mode physical
.\start-rocell-wizard.ps1 -Mode physical
```

The first command checks the application without opening devices. The second
opens the local file-only physical-mode workbench. Rehearsal remains the default
when `-Mode physical` is omitted. Do not change native activation flags or copy
positive test fixtures into the original store.

1. On Camera, initialize a new original setup or explicitly discover and reopen
   the existing one. Follow the source-stage guide to collect prerequisites,
   retain the initial source assessment/review, and collect/review a new source
   qualification. Unknown isolation must remain UNKNOWN until truly observed;
   an absent robot does not authorize invented installation measurements.
2. After a committed source-stage PASS, explicitly request static-contract
   entry. This leaves the static-camera stage WAITING_OPERATOR.
3. Choose the static design collection action. Acknowledge file-only operation
   and provide a portable operator label. The actual five controlled files are
   pinned/read, parsed, cross-checked and saved as an immutable receipt and
   assessment. Nominal values are labeled DESIGN_NOT_MEASURED. The stage is
   REVIEW_PENDING, not passed by collection alone.
4. Inspect the individual checks and all retained architecture, profile and
   support blockers. Review with a distinct procedural reviewer label. A label
   is not authenticated identity. Review accepts the exact assessment's verdict;
   there is no user-entered PASS override.
5. After a committed reviewed design PASS, explicitly begin camera receipt.
   This records only stage-3 WAITING_OPERATOR. It does not run USB inventory,
   open a camera, initialize a servo, capture an image or move the arm.
6. Export logs in Diagnostics & exports. Each export creates its own child
   under the user-selected parent:
   `C:\Users\Jack\Desktop\robot-arm-build\software\runs\wizard-exports`.
   Keep the returned export directory and manifest together when reporting a
   problem. Original private observation files are not included in JSON logs.

A Stop, changed source, stale original head, failed write/readback, ownership
cleanup failure or failed completion log withdraws current publication. Inspect
the retained attempt and explicitly reopen the original. Refresh/open does not
collect again, repair partial records, replay a review or enter the next stage.
A partial static cycle has no automatic replacement path in this increment.

## Developer component map

| Component | Responsibility and boundary |
| --- | --- |
| `physical_static_contract.py` | Actual bounded file collection; immutable receipt, deterministic assessment and distinct review; pure retained-byte verification. See [API](PHYSICAL_STATIC_CONTRACT_API.md). |
| `physical_received_camera.py` | Pure original-notebook/structured-inspection completeness assessment. The later [received-camera work order](RECEIVED_CAMERA_ONBOARDING_IMPLEMENTATION.md) adds its original-store and UI owners. |
| `workcell/camera_architecture.py`, `workcell/static_camera_support.py` | Reusable pure parsing extracted from existing strict loaders; no new design authority. |
| `physical_static_camera_onboarding_service.py` | One-use explicit collection/review/entry, original predecessor checks, attempt retention and cached presentation. |
| `physical_camera_setup_service.py` | Serialized source/Stop/original-store transaction and exact post-mutation readback. |
| `physical_static_contract_readback.py`, `physical_camera_session.py` | Full-journal v5 verification of original stage-2 roles and explicit stage-3 entry; partial states are preserved. |
| `physical_configuration_epochs.py` | Private later-static readback seam for an exact original epoch; original creation and public v1 inventory budgets stay unchanged. |
| `arrival_wizard_service.py`, `wizard_actions.py` | Public tickets, timeouts, outside-lock execution, exact-result retention and durable log before CURRENT publication. |
| Shared browser/terminal renderers | Cached three-stage status, design versus received facts, exact checks and explicit next action. No polling opens a device. |

All Python components above are under `software/src/rocell/application/` unless
another subdirectory is shown. The static service's public view is
`rocell.wizard_static_camera_onboarding.v1`; constructor and GET are inert.

## Original records and diagnostic export contracts

The original readback adds `rocell.physical_camera_source_workflow_readback.v5`
only after a static subject is retained. Before collection the exact v4 shape
is preserved. The v5 suffix supports INCOMPLETE,
ASSESSMENT_RETAINED_NOT_COMMITTED, REVIEW_PENDING,
REVIEW_RETAINED_NOT_COMMITTED, REVIEWED_PASS and REVIEWED_BLOCKED. None of those
states silently synthesizes a missing event. A separate committed event is
required for received-camera entry.

Source-stage limits remain 32 references and 4 MiB. Stage 2 separately permits
one receipt up to 256 KiB and one assessment/review up to 32 KiB each. Fixed
design inputs total at most 128 KiB, each at most 64 KiB. The collector has a
30-second cap; the application collection action has a 180-second overall cap,
and its original storage scope remains at most 120 seconds.

`attachment-source-qualification-data.json` retains its v1 export envelope for
source-only sessions. With static records it uses
`rocell.wizard_source_qualification_export.v2`, containing the source and static
families with independent publication and exact-byte-preservation markers.
Duplicate exact documents are referenced once by `document_key`. To reconstruct
a named original, follow those document references and compare its canonical
bytes/hash with the retained role. Sanitized/redacted data is not the original
subject named by a hash. The legacy source attachment holds static role hashes
and a family hash, not another deeply nested copy of the full static records.
No extra attachment slot or global IPC/export-cap increase was introduced.

## Follow-on implementation, not hardware claims

The received-camera/passive-workcell pure assessor now preserves all 16
observations, exact stage-owned notebook provenance and separate structured
camera inspection. It checks the explicit 17.5–18.5 mm thickness accommodation
with exact decimals. Missing observations or a missing original stage-3 notebook
reference remain incomplete; an old source-stage reference is rejected rather
than relabeled. Its completeness result is not stage PASS or installation
acceptance. The subsequent [received-camera work order](RECEIVED_CAMERA_ONBOARDING_IMPLEMENTATION.md)
implements original stage-3 attachment retention, submission/review service,
restart/publication and UI integration. Its verification ledger is separate
from the historical stage-2 results below.

Then join original reviewed identity, qualified native runtime/output
ownership, explicit bounded camera acquisition, actual calibration and
firmware-bound arm feedback/startup. Motion/contact remain later separately
authorized operations. This increment does not meet the entire connection
playbook's acceptance criteria or make the system plug-in-and-type ready.

A live browser inspection identified the need for a next-step block above the
long Camera diagnostics. The subsequent received-camera increment implements
that navigation-only block and direct links to the existing action forms.
It preserves server-side eligibility and never chooses initialization versus
reopening automatically for the operator.

## Verification record

These are bounded selections, not a claim that the entire repository test
suite or installed hardware acceptance has run. Selections can overlap.

| Selection | Result | What was actually exercised |
| --- | --- | --- |
| Static design producer/legacy controller/parser regressions | 153 passed | Actual controlled design files and pure retained parsing; broad source admission modeled. |
| Static original readback, original epochs and source-successor regression | 200 passed in 226.09 s | Includes 47 new cases, actual NTFS original restart, source-32 plus static-3 inventory and exact prior epoch restoration. |
| Earlier source/intake/epoch compatibility | 106 passed in 99.83 s | Prior readback behavior remains available. |
| Static service composition and faults | 17 passed in 37.28 s | Actual design collector, modeled source/ownership/store, original review and separate entry, Stop/source/head/partial-save refusal, exact-result publication and full failure metadata. |
| Source service/intake setup/export-limit regression | 49 passed in 43.33 s | Prior service scopes and eight-cycle exact-document export remain valid. |
| Received-camera assessor, legacy receipts and notebook | 135 passed in 31.40 s | Pure exact observation contracts; all physical observations/reference ownership explicitly modeled. |
| Shared actions, Arrival service/terminal, source/setup/restart/epoch UI and static public/UI regression | 493 passed in 89.32 s | Includes 64 new fault/publication/rendering/composed cases; normal pre-design CURRENT states render without inferred design acceptance. Slow tests excluded. |

The composed public action tests use the actual Arrival service, static service,
codecs and renderers with modeled source-isolation/ownership/M1 observations.
One-cycle and eight-cycle source histories reached design review and explicit
receipt entry. Combined source/static attachments measured 230,350 and 863,914
bytes respectively, with exactly eight attachments in each verified export.
Private isolation bytes were excluded; full exact source/static subjects remain
reconstructable. This is not an assertion that every maximally sized unique
history will fit the unchanged 1 MiB attachment cap.

The actual local application was also launched without device operations. A
temporary in-app browser displayed the Overview and Camera page, including the
new static panel/actions. Fresh setup showed NOT_STARTED/NOT_PUBLISHED, no image,
camera not connected and disabled capture/arm activation. The preview tab and
server were closed after inspection. This live check used a fresh uninitialized
session, not a claim that modeled PASS fixtures were real hardware observations.

Final code/configuration source fingerprint:
`9b3f63ca6264f052e5bcf629cdd743982f764834d2076cdebe9b4bb8f4563390`.
Both launchers' `-Check` modes return READY_FOR_DIAGNOSTICS with the selected
workspace export directory, static status NOT_STARTED and native release false.
Scoped Black/mypy and Node syntax checks pass. An offline wheel built without
dependency installation has 275 code/UI entries identical to the workspace:
`software/runs/static-onboarding-wheel-57c2be74b18d4d0a923fd41ad25697fd/rocell-0.1.0-py3-none-any.whl`
(SHA-256 `f8e465b182dbb3d06b3c4b58a0f0fd8a75b1f9b46e37614b7a1ab4aa0150c97c`).
This wheel remains a software packaging check, not a native-driver release.

### Actual assigned-folder setup, export and restart

The existing `wizard_workspace_sources_smoke.py` completed successfully against
that final source. It initialized real local M1 storage, collected the actual
prerequisites and source facts, reviewed the deterministic BLOCKED source result,
rotated nine notes, exported, shut down, explicitly discovered/reopened the same
original in a new launch and exported again. Original source documents, the
eight-domain configuration record and all stage states survived unchanged.
Source stayed BLOCKED and every downstream stage stayed PENDING.

- Original launch: `wizard-1e68615b584d4c5fadc3f695ae1427c6`.
- Reopened launch: `wizard-17798d4500b6410ba299e1818bf7f34c`.
- First verified export, 363,805 total bytes:
  `software/runs/wizard-exports/wizard-20260908T235338969572Z-e9c5653d15b940149027ede1973ec258`.
- Reopened verified export, 464,691 total bytes:
  `software/runs/wizard-exports/wizard-20260908T235347262383Z-4e6c6883243d4bb5b11a6c06d7c9c3c1`.
- Original source review SHA-256:
  `8ae31ea0c362de4ea5e95a5c379397dfd6597da42452909de212c631d70c7f45`.
- Original configuration SHA-256:
  `de46ce9d9bcee0592a83d528c577dc6c8dbe47332e12f6caabe4f193858f2187`.

The actual reopened export snapshot also passed the real JavaScript renderer
in the fake-DOM test harness and the terminal projection. Static onboarding was
correctly NOT_STARTED with CURRENT file-report publication and stage states
BLOCKED/PENDING/PENDING. This proves CURRENT does not accidentally imply design
acceptance before source admission. Both application owners were shut down.
No physical isolation observation, device inventory, native helper, camera
capture, serial connection, power or motion action was selected by this smoke.

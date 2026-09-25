# Existing rehearsal store reopening

`commissioning_rehearsal_reopen.py` supplies bounded discovery and original-store
verification. `CommissioningRehearsalService` now integrates it through the shared
wizard action catalog and browser/terminal adapters. Reopening does not restore
old browser tickets, initialize a replacement cell, convert source versions,
load a preview, or replay a prior camera operation, identity fixture, power
assessor, synthetic optics evaluation, serial worker or synthetic power observer.

Stage twelve adds strict verification of the exact consumed serial permit,
audited known result and complete private `CAMPAIGN_EVIDENCE` blob. Its safe stage
report is independently regenerated from those bytes and reviewed stage-9–11
dependencies. Missing/corrupt blobs or an attempt without its stage receipt hold;
an opened stage without any attempted campaign may be explicitly continued.
See [the feedback integration](WIZARD_FEEDBACK_INTEGRATION.md).

Stage thirteen adds complete nominal reference graph/FK/rigid-fit evidence and
the exact reviewed camera/feedback dependency chain. Reopening checks retained
algebra and certificates, not a replayed solver or physical bootstrap. See
[reference integration](WIZARD_REFERENCE_INTEGRATION.md).

## Server integration contract

Construct one `RehearsalReopenRegistry` with a tuple of
`KnownRehearsalRoot(root_id, absolute_parent_directory)`, the current
`workspace_source_sha256`, and the current stage `catalog_sha256`. The wizard's
assigned parent is normally `software/runs/wizard-rehearsal`. Do not accept a
filesystem root or destination from an HTTP request. For stage-13 stores also
provide the server-assigned `reference_workspace: Path`; a missing source
workspace holds instead of inferring a path from retained data. Construction
does not read that path.

Construction and `view()` perform no filesystem or hardware I/O. Explicit
`discover()` reads metadata only and returns `RehearsalDiscovery`. It does not
qualify storage, acquire mutation leases, load every evidence payload, or
change a store. Discovery is bounded to four roots, 32 immediate store children
per root, and bounded header/cell/anchor reads. Issues remain visible; excess
entries are not silently truncated into a seemingly complete list.

The interface displays each `RehearsalStoreChoice` and submits only its
server-issued `choice_id`. The service binds the corresponding discovery hash
into the prepared ticket; the frontend cannot author it. The backend call is:

```python
result = registry.open(
    choice.choice_id,
    expected_discovery_sha256=choice.discovery_sha256,
    admission_facts=server_owned_facts_provider,
)
```

Opening calls the existing `PhysicalOnboardingM1Runtime.open` and
`M1CommissioningPersistence` adapter for the **same directory, cell and session**.
It explicitly requalifies the volume and acquires/releases CELL/SESSION leases
to audit retained coordinator records and reconstruct evidence. Qualification
probes and lease-owner metadata can change; original stage journals, evidence,
attempts and session headers are not rewritten. A prepare/execute UI must
disclose those storage effects. Discovery is not a substitute for opening.

### Windows directory-pin compatibility

Only explicit M1 reopening uses the private
`_directory_guard(path, allow_directory_write_sharing=True)` mode. It requests
`GENERIC_READ` with `FILE_SHARE_READ | FILE_SHARE_WRITE`, still omitting
`FILE_SHARE_DELETE`. This permits the existing M1 `ReplaceFileW` publication of
immediate child lease-owner pointers while retaining tested leaf/ancestor
rename and guarded-directory deletion denial. Attribute-only access is not an
equivalent pin and is not restored.

This opt-in **does not exclude writable directory handles or establish hostile
writer isolation**. M1's qualified publication, CELL/SESSION OS leases, owner
identity/challenge checks, contained-path/link checks, and retained content
hashes remain necessary and unchanged. The mode does not grant physical
authority, overwrite immutable evidence, or qualify crash/power-loss behavior.

Diagnostic camera/export guards keep their stricter default read-only sharing
and sentinel-based manifest publication. No browser or operator setting exposes
this compatibility mode. Temporary-store regressions in
`test_m1_guard_publication_compatibility.py` exercise actual replacement,
rename/deletion denial and immutable no-overwrite behavior on Windows.

## Typed result and handoff

`RehearsalReopenResult.status` is `OPENED` or `READ_ONLY_HOLD`. A hold includes
typed `ReopenHoldReason(code, message, remediation)` records and **no adapter or
restored approval state**. There is no repair/reset/retry path in this API.

An opened result supplies the actual `.store` adapter, `.snapshot`,
`.verification`, and `.restored: RestoredRehearsalState`:

- `directory`, `cell_id`, `session_id`: original identities, not copied ones.
- `stage` / `stage_state`: `PhysicalOnboardingStage` / `V2StageState` enums.
- `receipt` / `assessment`: optional `VerifiedRehearsalEvidence`, each with a
  typed `.reference: EvidenceReference` and immutable `.payload: bytes`.
  `.document()` returns a fresh JSON dictionary. The convenient
  `receipt_reference` / `assessment_reference` properties are also available.
- `selected_camera`: the verified identity-stage receipt. Its selected
  candidate is `.document()["candidate"]`; it is not an enumerated device.
- `operator_id`: recovered only from current-stage evidence. Historical
  `WAITING_OPERATOR` with no receipt/operator record returns `None`.
- `camera_settings`: the latest verified staged settings evidence document.
- `latest_capture`: the latest verified camera-stage receipt; its bridge data
  is `.document()["capture_dataset"]`. No preview bytes are returned or opened.
- `stage_evidence`: immutable evidence objects for audit/display.
- `journal_head_sha256`, `evidence_inventory_sha256`, `challenge_sha256`,
  `session_header_sha256`: the exact reconstructed state binding.

`disposition` distinguishes `DUE_STAGE`, `WAITING_NO_RECEIPT`, `RECEIPT_READY`,
and `REVIEW_PENDING`. In particular, an unrecorded operator is never guessed
from a previous stage. A retained campaign without its stage receipt is a hold,
not a no-progress invitation to repeat the campaign.

The caller must invalidate any prepared action if the exact source, journal,
evidence inventory or challenge changes. Restoring an assessment is **not**
restoring reviewer acceptance: show it and require a new distinct human review
of the exact current state using the existing guarded service transaction.

## Browser and terminal projection

The presentation adapters consume `commissioning_rehearsal.discovery` with
`status: NOT_DISCOVERED | DISCOVERED`, bounded `choices` and `issues`, plus
`storage_qualified: false`. Choice fields are the dataclass's primitive fields;
serialize `directory` as text. Display values and the select's `choice_id` are
kept verbatim, and no raw filesystem-path input is provided.

`commissioning_rehearsal.reopen_result` is absent/null until an explicit result,
then projects `status`, `original_session_reopened`, `disposition`, `operator_id`
and bounded `reasons`. The active `directory`, `cell_id`, `session_id` and
`session_origin: NEW_THIS_LAUNCH | REOPENED_EXISTING` stay in the existing
top-level rehearsal projection. Do not serialize the result's live adapter or
its binary evidence payloads into a browser response.

Both presentations distinguish read-only discovery from opening's storage
qualification/lease effects. Neither visiting the page nor terminal `view`
invokes discovery, reopening, repair or replay. The existing generic action
forms drive `rehearsal_discover`, `rehearsal_reopen` with a server-populated
choice select, and (when offered) explicit `rehearsal_record_operator`. Every
execution still requires its own prepared ticket and confirmation.

The dynamic select has no default: the operator must choose an original store.
Each selection has one opening attempt per launch, including held/cancelled
results. A held selection does not prevent explicitly choosing a different,
unused discovered session. Once attached, switching or initializing a replacement
is blocked. Source-drifted stores remain inspectable holds, not migrated sessions.

For a legacy camera stage opened without a retained operator, the service exposes
`rehearsal_record_operator` only while that reopened stage has no campaign receipt.
It retains the newly supplied operator before settings/capture; it cannot revise
the operator of an existing assessment or campaign.

Retained `REVIEW_PENDING` is labeled as requiring a fresh distinct review, not
accepted approval. Read-only holds include the reason/remediation. Dataset
metadata is displayed separately from the current camera-image provenance;
reopening never implies that a preview was loaded.

## Safety and current scope

The implementation accepts one immutable, source-domain-separated
REHEARSAL cell/session per store and the current first-thirteen-stage journal and
receipt schemas. Unknown events/schemas, physical headers, source/catalog
drift, orphan evidence, uncertain attempts, quarantine, partial outputs and
active/stale owners hold. It does not reconcile them or modify old versions.

Small M1 metadata is preflight-bounded by depth, aggregate entries and bytes.
At most two camera datasets are reconstructed. Each v2 camera receipt must
retain the exact staged settings and original in-store binary fixture path;
the shared `verify_windows_capture_ingest` verifier rechecks its retained
source/envelope hashes and native dataset content. Metadata is checked against
the campaign's frame/byte budget before full binary reads. This is still
diagnostic data, not M1-qualified binary storage or physical calibration.

Legacy camera receipts without the versioned binary receipt/settings are held
for inspection instead of being upgraded into a new camera review. Original
native input files are not re-read by the retained-dataset verifier. An orphan
binary fixture remains a hold even when its internal files appear valid.

Stages 7 and 8 retain complete bounded synthetic optics reports under
`rocell.rehearsal_optics_receipt.v1`. Reopening verifies their exact original
operator/opening, source/catalog, selected identity/settings, stage-6 dataset
dependency, and immediately preceding PASS receipt/review. It recomputes the
checks from retained substantive report fields using the strict
[optics evidence verifier](REHEARSAL_OPTICS_STAGES_API.md); no original assessment,
image detector, renderer, solver or evaluator operation is replayed. The original
stage-6 capture envelope and dataset content must also remain intact.

A complete optics receipt in `WAITING_OPERATOR` returns `RECEIPT_READY`; an exact
retained assessment returns `REVIEW_PENDING` and still needs a fresh distinct
review. Failed checks remain BLOCKED. An opened optics stage with no complete
receipt returns `OPTICS_RECEIPT_MISSING`, never a prompt to silently recollect.
The compact UI check card is restored from verified evidence, but the evaluated
pixels remain explicitly nominal-render inputs, not the native-sized camera
dataset or an installed-camera measurement. The next unsupported stage remains
held and none of these states authorizes physical operation.

There are no provider, arm, power, serial or coordinator execution calls.
`physical_authority` and `automatic_replay_allowed` remain false everywhere.

Stages 9–11 add exact `rocell.rehearsal_arm_identity_receipt.v1` and
`rocell.rehearsal_power_receipt.v1` containers, with corresponding stage-opening
schemas. Their [integration contract](WIZARD_ARM_SETUP_INTEGRATION.md) defines
the immediate predecessor's full receipt/assessment/review hashes and the
additional stage-8 or stage-9 evaluator digest. Both trusted result and evaluator
source hashes are supplied to strict pure verification. Complete results restore
their compact cards; a missing evaluated result returns `EVALUATION_RECEIPT_MISSING`.
No inventory or power assessor is rerun to fill a gap. One evaluation per stage,
128 KiB per outer receipt and 1 MiB aggregate evidence bounds remain unchanged.

Stage 13 uses `rocell.rehearsal_reference_stage_open.v1` and
`rocell.rehearsal_reference_receipt.v1`. It verifies reviewed stage-7/8/12 trios,
the full audited feedback campaign and separate synthetic final-power observation,
and the original camera binary dependency. Its complete nominal source snapshot
must match a fresh read from the assigned workspace. The numeric verifier checks
retained frame chains and fit certificates without FK, NumPy fitting, graph
evaluation or device replay. Receipt-ready, review-pending and reviewed stage-13
states restore; an opening without its result stays `EVALUATION_RECEIPT_MISSING`.
The new inner report cap is 112 KiB; outer/aggregate limits are unchanged. All
eight physical reference requirements and all fifteen physical stages remain pending.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest software/tests/unit/test_commissioning_rehearsal_reopen.py -q
.\.venv\Scripts\python.exe -m pytest software/tests/unit/test_commissioning_rehearsal_resume_service.py software/tests/unit/test_arrival_wizard_reopen_ui.py -q
.\.venv\Scripts\python.exe -m pytest software/tests/unit/test_commissioning_rehearsal_optics.py -q
.\.venv\Scripts\python.exe software/scripts/wizard_reopen_rehearsal_smoke.py
```

Pure registry tests run everywhere. Actual M1 integration tests run on local
Windows NTFS, use temporary stores and synthetic camera data, and never
enumerate or activate host hardware.

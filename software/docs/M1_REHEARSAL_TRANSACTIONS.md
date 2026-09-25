# Durable rehearsal integration: developer handoff

This is an incapable slice of DEV-002/004. It does not activate the physical
runtime, replace independent durability qualification, or complete the
fifteen-stage playbook. No native provider is registered here.

## Ownership and call path

```text
browser / terminal
  -> ArrivalWizardService: closed action, exact preview ticket, source checks
  -> CommissioningRehearsalService: due stage, synthetic receipt, assessment/review
  -> M1CommissioningPersistence: real state hashes and narrow transactions
  -> PhysicalOnboardingM1Runtime: ordered OS leases and guarded publication
  -> V2 stage journal + global attempt/quarantine + immutable result records
```

For a synthetic camera campaign, the stage service constructs a closed
`CampaignRegistration` and invokes `CellCommissioningCoordinator`. Its exact
permit binds the synthetic camera, mode, scenario, frame budget, source, stage
plan, eight rehearsal epochs, journal/evidence/attempt/quarantine heads, worker
implementation hash and expiration.

The lifecycle is reservation → `INTENT_DURABLE` → `EFFECT_ARMED` → incapable
worker → `EFFECT_OBSERVED` → `CLEANUP_CONFIRMED` → retained result →
`SEALED_KNOWN`. Pre-arming cancellation aborts without dispatch. Post-arming
uncertainty seals conservatively and latches quarantine. An orphan reservation
is retained as a reconciliation hold, never silently reused. An attempt's
success does not pass a stage.

## Implemented API

- `rehearsal_source_binding(workspace_source_sha256)` domain-separates sources.
- `PhysicalOnboardingM1Runtime.create_session(..., mode="REHEARSAL",
  workspace_source_sha256=...)` requires isolated rehearsal naming/source
  binding. Mode is immutable. Existing physical-header serialization and its
  default are unchanged.
- `M1CommissioningPersistence(runtime, workspace_source_sha256=...,
  admission_facts=...)` accepts only matching actual M1 rehearsal storage.
- `snapshot(session_id)` and `verification(session_id)` are read-only.
- `stage_transaction(session_id, expected_challenge_sha256=...)` owns CELL →
  SESSION leases. Its scoped `snapshot`, `store_evidence` and
  `commit_stage_state` retain V2 active-stage/head/evidence checks. A transaction
  reference cannot be reused outside its scope.
- `transaction(exact_lease_specs)` implements the coordinator protocol,
  adding CAMERA and/or ARM_CONTROLLER in canonical order. These are storage
  resource leases, not device opens.
- `RehearsalAdmissionFacts` holds server-owned documents. The adapter freezes
  and hashes them, deriving authoritative state/qualification hashes from M1,
  not browser-written fields.

Do not import persistence primitives or native providers in HTTP handlers.
Do not expose arbitrary COM paths, camera indexes, Python modules, stage PASS
flags or activation booleans as inputs.

## Review and refresh

The first four stages use labeled prerequisite/identity fixtures. Stages five
and six use the coordinated incapable camera worker. Receipt evaluation is
retained before a distinct typed rehearsal reviewer accepts its exact outcome.
Local IDs test role separation; they are not authenticated accounts.

UI tickets bind the cached rehearsal view. Before a campaign, the service
compares the displayed durable challenge with state under actual leases.
Unexpected external journal/evidence changes invalidate pending review and
hold the launch; refresh never silently rebases approval. Evidence remains.

The coordinator and worker share the service's cancellation event. A Stop
received after durable completion cannot undo it; the UI retains the committed
outcome and explains late cancellation.

## Retention and remaining gates

One launch can explicitly create one root under
`software/runs/wizard-rehearsal/<wizard-id>/`. Construction/status are inert.
The [reopen backend](COMMISSIONING_REHEARSAL_REOPEN_API.md) now supports explicit
bounded discovery/requalification and exact evidence reconstruction. It is not
yet exposed through Arrival/UI: a normal new launch is still a new rehearsal,
not recovery of an old one. Preserve held stores.

The adapter retains permit/receipt/result JSON before known sealing. The
[binary camera rehearsal](WIZARD_BINARY_CAMERA_REHEARSAL.md) now publishes and
content-verifies diagnostic native-sized fixtures before returning dataset and
envelope hashes to the coordinator. Assessment and review verify the dataset
again. This is not qualified physical frame publication. The
[capture dataset API](CAMERA_CAPTURE_DATASET_API.md) and native provider still
need coordinated physical qualification. Independent physical worker
containment/crash/power-interruption qualification, progressive physical
intake, stages 7–15, identity/power/serial onboarding and the static-primary
successor migration remain open.

## Reproducible checks

```powershell
.\.venv\Scripts\python.exe -m pytest software/tests/unit/test_commissioning_m1_persistence.py -q
.\.venv\Scripts\python.exe -m pytest software/tests/unit/test_commissioning_rehearsal_service.py -q
.\.venv\Scripts\python.exe -m pytest software/tests/unit/test_commissioning_coordinator.py -q
```

The first two use actual qualified local Windows NTFS temporary stores and
incapable providers. They can take several minutes because full immutable
evidence verification is intentional. They never enumerate or open hardware.
Do not substitute portable publication to claim physical durability.

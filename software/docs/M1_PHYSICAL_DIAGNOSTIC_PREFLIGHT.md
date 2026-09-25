# Physical-diagnostic M1 preflight persistence

## What is implemented

`application/commissioning_physical_persistence.py` is a concrete, qualified M1
storage adapter for physical-source preflight. It is **not** a renamed rehearsal
store and does not provide a camera, serial, power, motion or contact backend.
The companion `PhysicalDiagnosticPreflightCoordinator` admits only retained
`NO_DEVICE_IO` source-contract checks in `workspace_sources` or
`static_camera_contract`. A successful attempt does not pass its canonical
onboarding stage automatically.

The implementation uses the actual qualified NTFS publisher, V2 session journal,
cell-global attempt/quarantine ledgers and ordered OS ownership leases. Shared
internal storage mechanics have exactly two module-owned domain descriptors;
there is no caller-supplied `allow_physical` switch.

| Binding | Existing rehearsal | New physical-source preflight |
| --- | --- | --- |
| Immutable V2 mode | `REHEARSAL` | `PHYSICAL_DIAGNOSTIC` |
| Composition | `HARDWARE_INCAPABLE_REHEARSAL` | `PHYSICAL_DIAGNOSTIC_NO_DEVICE_IO` |
| Cell ID | `wizard-rehearsal-<16 lowercase hex>` | `wizard-physical-diagnostic-<16 lowercase hex>` |
| Session ID | `rehearsal-<32 lowercase hex>` | `physical-diagnostic-<32 lowercase hex>` |
| Record directory under cell | `rehearsal-records` | `physical-diagnostic-records` |
| Record schema | `rocell.m1_rehearsal_record.v1` | `rocell.m1_physical_diagnostic_record.v1` |
| Source schema | `rocell.rehearsal_source.v1` | `rocell.physical_diagnostic_source.v1` |

Both domains retain zero physical authority. The existing rehearsal record bytes,
physical-default V2 header serialization and rehearsal-only `_decode_permit`
helper remain unchanged. Ordinary older physical M1 sessions stay readable, but
cannot silently enter this new application namespace. Copying or relabeling a
rehearsal source, header or result cannot qualify it as a physical diagnostic.

## Explicit initialization

The application assigns a separate local deployment root, normally below the
existing physical-onboarding run area. It must not point to the rehearsal root.
Creating that directory and initializing M1 are explicit operator actions;
adapter construction does not create files or inspect hardware.

```python
from rocell.application.commissioning_physical_persistence import (
    M1PhysicalDiagnosticPersistence,
    PhysicalDiagnosticAdmissionFacts,
    physical_diagnostic_source_binding,
)
from rocell.application.physical_onboarding_m1 import PhysicalOnboardingM1Runtime

runtime = PhysicalOnboardingM1Runtime.initialize(
    assigned_existing_empty_root,
    source_binding_sha256=physical_diagnostic_source_binding(workspace_source_sha256),
    cell_id=physical_cell_id,
)
runtime.create_session(
    physical_session_id,
    mode="PHYSICAL_DIAGNOSTIC",
    workspace_source_sha256=workspace_source_sha256,
)
adapter = M1PhysicalDiagnosticPersistence(
    runtime,
    workspace_source_sha256=workspace_source_sha256,
    admission_facts=server_reviewed_facts,
)
```

`physical_diagnostic_source_binding()` hashes the exact canonical document
`{schema, composition, workspace_source_sha256}`. The supplied workspace digest
must come from the application's source verifier, not a browser field. The
reserved physical namespace requires this binding at session creation. A new
qualified deployment is necessary when its source binding changes; this API
does not relabel existing evidence or clear quarantine.

Initialization performs the existing local Windows/NTFS qualification and
startup durability checks. It does not load a camera or serial library, enumerate
devices, initialize the arm, or assert that hardware is powered off.

## Public storage seam

The adapter exposes:

- `snapshot(session_id)` and `verification(session_id)` for verified retained
  state, not device status;
- `stage_transaction(session_id, expected_challenge_sha256=...)`, which yields
  guarded `snapshot()`, `verification()`, `store_evidence(...)` and
  `commit_stage_state(...)` operations;
- `transaction((CELL lease, SESSION lease))`, used by the coordinator for exact
  admission, intent, consumption, full evidence retention, lifecycle receipts,
  known/uncertain sealing and immutable result retention.

The runtime's distinct `physical_diagnostic_transaction(...)` owns both real
leases for the whole operation, verifies the exact state challenge on acquisition,
and activates the qualified mutation guard. After scope exit, every transaction
read and write refuses use. Raw ledger/publisher objects are not public UI APIs.
Device leases are rejected in this domain.

`server_reviewed_facts(request, snapshot)` returns the exact
`PhysicalDiagnosticAdmissionFacts` type, containing a hazard document, exactly
eight epoch documents, an optional selected-identity document, and bounded open
blocker IDs. The adapter freezes and hashes those documents. Stage state,
journal/attempt/quarantine/evidence heads and durability/source identities come
from the actual M1 store, never from client-authored authoritative hashes.
Rehearsal facts are a different type and are rejected. Energization envelopes
are forbidden here.

## Durable no-replay lifecycle

The exact request reservation is immutably published before intent; durable
`EFFECT_ARMED` consumes it before the worker runs. Despite the shared lifecycle
name, this composition permits no device effect. Every known physical preflight
requires complete `CampaignEvidence` bytes before result publication and
`SEALED_KNOWN`. The audit derives this requirement from the durable domain,
not an optional flag that could disappear on restart.

Known receipts must have zero opens, reads, writes, frames and closes; zero-I/O
budgets are enforced independently. `final_power_state` must be `UNKNOWN`, since
a source check has made no power observation. Full evidence hashes and byte
counts must match retained bytes exactly. The shared bounds remain 128 KiB
aggregate campaign evidence, 1 MiB per encoded record, 2,048 records and 32 MiB
aggregate record reads. There is no truncation or hash-only replacement proof.

Missing, altered, mixed-domain or partially published evidence prevents an audited
known result. Source-worker or post-arm publication uncertainty uses the existing
cell-global quarantine and recovery rules. No new automatic reconciliation,
quarantine clearing, re-execution or device release method was introduced.

## Acknowledgement versus continuity checks

Both storage domains now provide these distinct scoped methods:

1. `assert_consumed_permit(permit)` acknowledges the exact committed armed permit
   once under its original owned lease set.
2. `revalidate_consumed_permit(permit)` can subsequently perform read-only
   continuity checks. It requires that acknowledgement, the exact live lease
   set, and the same committed `INTENT_DURABLE → EFFECT_ARMED` tail. The sole
   unresolved attempt must be this attempt.

The latter rechecks stage/revision, source, stage-plan, session journal, evidence
inventory, quarantine, qualification, hazard, all eight epochs, selected identity,
blockers and the original envelope. Only the known self-caused attempt-head
advance and unresolved count may differ from admission. It neither mutates the
ledger nor overwrites the original cached admission or renews any time bound.
The coordinator's `ConsumedCommissioningScope` checks cancellation and the
original deadline before and after this read, and revokes itself at worker exit.

This additional read may take material time on a large retained session. A
bounded child handshake that cannot complete it in time must remain held; these
APIs do not extend a release deadline or authorize caching stale admission.

## Tests and remaining boundaries

`tests/unit/test_commissioning_physical_persistence.py` exercises the actual
qualified NTFS publisher and CELL/SESSION OS leases using test-owned temporary
data and source-only workers. Its full-source payload is a clearly labeled test
document, not received-hardware evidence. Tests cover retention before known
seal, restart/deduplication, expired scope access, source/domain rejection,
forbidden effects, acknowledgement/revalidation, and removed/corrupt evidence.
The existing `test_commissioning_m1_persistence.py` retains the legacy physical
header golden hash and rehearsal regression coverage.

No test in this slice opens a camera or serial endpoint. Hashes detect content
inconsistency; they are not signatures, hostile-writer isolation, trusted-release
attestation or independent physical observations. Real endpoint identity,
driver/firmware qualification, native containment, power and physical stage
prerequisites remain separately held. Passing this source preflight establishes
neither installed-hardware compatibility nor permission to connect it.

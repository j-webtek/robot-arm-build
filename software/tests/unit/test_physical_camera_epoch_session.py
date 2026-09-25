"""Initial epoch bytes in original M1, not physical facts or stage acceptance.

The scope model uses genuine typed V2 history and the production epoch codec;
only filesystem ownership/manifest reads are modeled. The isolated NTFS test
uses actual publication and original-store reopen, without any device/process.
"""

from contextlib import contextmanager
from dataclasses import replace
import os
import threading
import time

import pytest

from rocell.application import physical_camera_session as module
from rocell.application import physical_configuration_epochs as epochs
from rocell.application import physical_onboarding_v2 as v2
from rocell.application.commissioning_camera_persistence import (
    physical_camera_source_binding,
)
from rocell.application.physical_onboarding import STAGE_ORDER
from rocell.providers.windows.native_camera_protocol import canonical, digest
from test_physical_camera_session_readback import (
    generate,
    model,
    no_devices,
    workspace,
)
from test_physical_camera_session import (
    CELL,
    SESSION,
    SOURCE,
    perform,
    session_fixture,
)
from test_physical_camera_source_workflow_readback import collect_chain


def read(owner, header, **kwargs):
    return owner.read_original_source_workflow(
        expected_header_sha256=header,
        cancellation=kwargs.pop("cancellation", threading.Event()),
        progress=kwargs.pop("progress", lambda _: None),
        **kwargs,
    )


@pytest.fixture
def typed_model(model):
    owner, prerequisites, state = model
    header = v2.V2SessionHeader.build(
        session_id=SESSION,
        cell_id=CELL,
        created_at_ns=1000,
        source_binding_sha256=physical_camera_source_binding(SOURCE),
        publication_durability=v2.WINDOWS_NTFS_QUALIFIED,
        durability_qualification_sha256="8" * 64,
    )
    events = []

    def advance(next_state, references=()):
        events.append(
            v2.V2JournalEvent.build(
                header=header,
                sequence=len(events),
                stage=STAGE_ORDER[0],
                previous_state=(
                    events[-1].state if events else v2.V2StageState.PENDING
                ),
                state=next_state,
                occurred_at_ns=2000 + len(events),
                previous_event_sha256=(events[-1].event_sha256 if events else "0" * 64),
                evidence=tuple(references),
                detail_code="MODELED_EPOCH_STORAGE_ONLY",
            )
        )

    advance(v2.V2StageState.WAITING_OPERATOR)

    def snapshot():
        states = [events[-1].state, *([v2.V2StageState.PENDING] * 14)]
        committed = tuple(ref.evidence_id for event in events for ref in event.evidence)
        return v2.V2SessionSnapshot(
            header,
            tuple(
                v2.V2StageSnapshot(
                    stage,
                    states[i],
                    len(events) - 1 if i == 0 else None,
                    committed if i == 0 else (),
                )
                for i, stage in enumerate(STAGE_ORDER)
            ),
            tuple(events),
            (),
            tuple(sorted(state["references"], key=lambda ref: ref.evidence_id)),
            v2.V2CommittedHead.build(header, events),
            v2._derive_next_action(states),
        )

    store = owner._store
    original_scope, original_verification = store.stage_transaction, store.verification

    @contextmanager
    def scope(*args, **kwargs):
        with original_scope(*args, **kwargs) as tx:
            old = tx.snapshot
            tx.snapshot = snapshot
            try:
                yield tx
            finally:
                tx.snapshot = old

    def verification(session_id):
        result = original_verification(session_id)
        result.session_header_sha256 = header.header_sha256
        result.session_head_sha256 = snapshot().head.head_sha256
        if state["verification_calls"] > 1 and state["after_change"]:
            setattr(result, state["after_change"], "9" * 64)
        return result

    store.stage_transaction, store.verification = scope, verification
    state.update(snapshot=snapshot, advance=advance, header=header, store=store)
    return owner, prerequisites, state


@pytest.fixture
def recorded(typed_model):
    owner, prerequisites, state = typed_model
    record = epochs.build_physical_configuration_epochs(
        prerequisites, state["snapshot"](), evidence_bindings=()
    )
    reference = state["add"](record.payload, label=module.CONFIGURATION_EPOCH_LABEL)
    return owner, prerequisites, state, record, reference


def test_absent_initial_vector_preserves_exact_v1_keys_without_building(
    typed_model, monkeypatch
):
    owner, _, state = typed_model
    monkeypatch.setattr(
        epochs,
        "build_physical_configuration_epochs",
        lambda *a, **k: pytest.fail("readback created an absent vector"),
    )
    result = read(owner, state["header"].header_sha256)
    assert result["schema"] == module.SOURCE_WORKFLOW_SCHEMA
    assert set(result) == {
        "schema",
        "binding",
        "session_header_sha256",
        "session_head_sha256",
        "evidence_inventory_sha256",
        "stage",
        "state",
        "prerequisites",
        "receipt",
        "assessment",
        "review",
        "physical_authority",
        "device_io_performed",
    }
    assert state["enters"] == state["exits"] == state["reads"] == 1


def test_initial_record_full_readback_is_inert_detached_and_one_scope(
    recorded, monkeypatch
):
    owner, prerequisites, state, vector, reference = recorded
    before = canonical(state["snapshot"]().to_verification_dict())
    monkeypatch.setattr(
        epochs,
        "build_physical_configuration_epochs",
        lambda *a, **k: pytest.fail("readback rebuilt its original vector"),
    )
    result = read(owner, state["header"].header_sha256)
    assert result["schema"] == module.SOURCE_WORKFLOW_EPOCH_SCHEMA
    assert result["configuration_epochs"] == {
        "document": vector.to_dict(),
        "evidence_sha256": vector.sha256,
        "retention": "M1_FULL_BYTES_READ_BACK",
        "reference": reference.to_dict(),
    }
    assert canonical(result["prerequisites"]["document"]) == prerequisites.payload
    assert result["state"] == "WAITING_OPERATOR"
    assert state["enters"] == state["exits"] == 1 and state["reads"] == 2
    assert state["verification_calls"] == 2
    assert canonical(state["snapshot"]().to_verification_dict()) == before
    result["configuration_epochs"]["document"]["qualified"] = True
    result["configuration_epochs"]["reference"]["payload_bytes"] = 1
    retained = owner.retained_source_workflow()["configuration_epochs"]
    assert retained["document"]["qualified"] is False
    assert retained["reference"] == reference.to_dict()


@pytest.mark.parametrize(
    "fault", ["duplicate", "media", "wrong-stage", "payload", "unknown-schema"]
)
def test_invalid_matching_role_is_never_ignored(recorded, fault):
    owner, _, state, vector, reference = recorded
    if fault == "duplicate":
        state["add"](vector.payload, label=module.CONFIGURATION_EPOCH_LABEL)
    elif fault == "payload":
        state["payloads"][reference.evidence_id] = b"{}"
    else:
        state["references"].remove(reference)
        state["add"](
            b"{}" if fault == "unknown-schema" else vector.payload,
            label=module.CONFIGURATION_EPOCH_LABEL,
            stage=STAGE_ORDER[1] if fault == "wrong-stage" else STAGE_ORDER[0],
            media="text/plain" if fault == "media" else "application/json",
        )
    with pytest.raises(module.PhysicalCameraSessionError):
        read(owner, state["header"].header_sha256)
    assert owner._store is None and owner.view()["status"] == "HELD"
    assert owner.retained_source_workflow() is None


@pytest.mark.parametrize(
    "fault", ["source", "session", "header", "inventory", "head", "authority"]
)
def test_rehashed_original_context_or_snapshot_tamper_is_rejected(recorded, fault):
    owner, _, state, vector, reference = recorded
    document = vector.to_dict()
    if fault == "source":
        document["binding"]["source_sha256"] = "f" * 64
    elif fault == "session":
        document["binding"]["session_id"] = "physical-camera-" + "f" * 32
    elif fault == "header":
        document["binding"]["session_header_sha256"] = "f" * 64
    elif fault == "inventory":
        document["original_snapshot"]["evidence_inventory"] = []
        document["original_snapshot"]["evidence_inventory_sha256"] = digest(
            canonical([])
        )
    elif fault == "head":
        document["original_snapshot"]["head"]["head_sha256"] = "f" * 64
    else:
        document["admission_allowed"] = True
    state["references"].remove(reference)
    state["add"](canonical(document), label=module.CONFIGURATION_EPOCH_LABEL)
    with pytest.raises(module.PhysicalCameraSessionError):
        read(owner, state["header"].header_sha256)
    assert owner.retained_source_workflow() is None


def test_general_after_stage_vector_is_not_the_initial_setup_role(typed_model):
    owner, prerequisites, state = typed_model
    vector = epochs.build_physical_configuration_epochs(
        prerequisites, state["snapshot"](), boundary="AFTER_STAGE"
    )
    state["add"](vector.payload, label=module.CONFIGURATION_EPOCH_LABEL)
    with pytest.raises(
        module.PhysicalCameraSessionError, match="CONFIGURATION_EPOCHS_INVALID"
    ):
        read(owner, state["header"].header_sha256)


def test_original_creation_prefix_survives_later_blocked_source_review(
    recorded, monkeypatch
):
    owner, prerequisites, state, vector, reference = recorded
    header = state["header"].header_sha256
    artifacts = collect_chain(prerequisites, header, monkeypatch)
    refs = {
        role: state["add"](artifact.payload, label=f"workspace-source-{role}-v1")
        for role, artifact in artifacts.items()
    }
    state["advance"](
        v2.V2StageState.REVIEW_PENDING, (refs["receipt"], refs["assessment"])
    )
    state["advance"](v2.V2StageState.BLOCKED, tuple(refs.values()))
    result = read(owner, header)
    assert result["state"] == "BLOCKED"
    assert canonical(result["configuration_epochs"]["document"]) == vector.payload
    assert result["configuration_epochs"]["reference"] == reference.to_dict()
    assert (
        result["session_head_sha256"]
        != vector.to_dict()["original_snapshot"]["head"]["head_sha256"]
    )
    assert (
        result["evidence_inventory_sha256"]
        != vector.to_dict()["original_snapshot"]["evidence_inventory_sha256"]
    )
    assert all(stage["state"] == "PENDING" for stage in owner.view()["stages"][1:])


@pytest.mark.parametrize("fault", ["exit", "coherence", "stop", "source", "deadline"])
def test_late_failure_keeps_verified_historical_vector_but_withholds_current(
    recorded, fault
):
    owner, _, state, vector, _ = recorded
    cancel = threading.Event()
    if fault == "exit":
        state["exit_failure"] = True
    elif fault == "coherence":
        state["after_change"] = "evidence_inventory_sha256"

    def progress(message):
        if message.startswith("Original requirements readback finished"):
            if fault == "stop":
                cancel.set()
            elif fault == "source":
                state["source"] = "f" * 64
            elif fault == "deadline":
                state["now"] += module.DIAGNOSTIC_TIMEOUT_NS

    with pytest.raises(module.PhysicalCameraSessionError):
        read(
            owner, state["header"].header_sha256, cancellation=cancel, progress=progress
        )
    assert owner.view()["status"] == "HELD" and owner._store is None
    assert owner.view()["verification"] is owner.view()["stages"] is None
    assert (
        canonical(owner.retained_source_workflow()["configuration_epochs"]["document"])
        == vector.payload
    )


@pytest.mark.skipif(os.name != "nt", reason="isolated actual Windows NTFS store")
def test_actual_initial_epoch_publication_and_new_owner_reopen_preserve_stage_state(
    workspace, monkeypatch
):
    monkeypatch.setattr(module, "source_fingerprint", lambda _: SOURCE)
    prerequisites = generate(workspace)
    original = session_fixture(workspace)
    initial = perform(original)
    header = initial["verification"]["session"]["header_sha256"]
    with original.stage_transaction(
        expected_challenge_sha256=initial["verification"]["challenge_sha256"]
    ) as tx:
        tx.commit_stage_state(
            STAGE_ORDER[0],
            v2.V2StageState.WAITING_OPERATOR,
            occurred_at_ns=time.time_ns(),
            detail_code="ISOLATED_INITIAL_EPOCH_STORAGE",
            expected_head_sha256=tx.snapshot().head.head_sha256,
        )
        prereq_ref = tx.store_evidence(
            STAGE_ORDER[0],
            prerequisites.payload,
            label=module.PREREQUISITE_LABEL,
            media_type="application/json",
            captured_at_ns=time.time_ns(),
            expected_head_sha256=tx.snapshot().head.head_sha256,
        )
        assert tx.read_stage_evidence(prereq_ref) == prerequisites.payload
        before = tx.snapshot()
        vector = epochs.build_physical_configuration_epochs(
            prerequisites, before, evidence_bindings=()
        )
        ref = tx.store_evidence(
            STAGE_ORDER[0],
            vector.payload,
            label=module.CONFIGURATION_EPOCH_LABEL,
            media_type="application/json",
            captured_at_ns=time.time_ns(),
            expected_head_sha256=before.head.head_sha256,
        )
        assert tx.read_stage_evidence(ref) == vector.payload
        assert tx.snapshot().head == before.head
        assert tx.snapshot().stages == before.stages
    reopened = session_fixture(workspace)
    verified = perform(reopened, "refresh")
    result = read(reopened, header)
    assert result["configuration_epochs"]["reference"] == ref.to_dict()
    assert canonical(result["configuration_epochs"]["document"]) == vector.payload
    assert result["prerequisites"]["reference"] == prereq_ref.to_dict()
    after = reopened.view()
    assert after["stages"] == verified["stages"]
    for key in ("session", "attempt_ledger", "quarantine"):
        assert after["verification"][key] == verified["verification"][key]
    assert after["stages"][0]["state"] == "WAITING_OPERATOR"
    assert all(item["state"] == "PENDING" for item in after["stages"][1:])
    assert after["physical_authority"] is after["device_io_performed"] is False

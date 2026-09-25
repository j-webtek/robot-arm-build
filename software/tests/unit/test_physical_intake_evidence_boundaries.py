"""Injected failure boundaries of the production passive-intake service.

Actual pure subjects and setup/reader contexts are reused. Transaction failures
are modeled explicitly; no inbox, NTFS campaign, native or device call occurs.
"""

from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import threading

import pytest

from rocell.application import physical_intake_evidence_service as module
from rocell.application.physical_onboarding import EvidenceReference, STAGE_ORDER
from rocell.application.wizard_actions import WizardError
from rocell.providers.windows.native_camera_protocol import canonical, digest
from test_physical_camera_intake_session import (
    intake_model,
    complete,
    read,
    notebook,
    RAW,
    COLLECTION,
)
from test_physical_camera_intake_setup import setup_flow
from test_physical_camera_session_readback import model, no_devices, workspace
from test_physical_camera_session import SOURCE
from test_physical_intake_submission import intake_fixture


@pytest.fixture
def service(setup_flow, monkeypatch):
    setup, data, state = setup_flow
    result = module.PhysicalIntakeEvidenceService(setup)
    result.observe_setup()
    monkeypatch.setattr(module, "source_fingerprint", lambda _: SOURCE)
    return result, data, state


def reference(payload):
    sha = digest(payload)
    return EvidenceReference(
        "evidence-" + sha, STAGE_ORDER[0], "b" * 64, "c" * 64, sha, len(payload)
    )


@pytest.mark.parametrize("role", ["submission", "assessment", "review"])
@pytest.mark.parametrize("failure", ["store", "readback"])
def test_full_generated_metadata_survives_uncertain_retention(service, role, failure):
    owner, _, _ = service
    fixture = intake_fixture()
    artifact = getattr(fixture, role)
    ref = reference(artifact.payload)
    owner._attempt = {"collection_id": COLLECTION, "records": {}}
    calls = []

    def store(*args, **kwargs):
        calls.append("store")
        if failure == "store":
            raise RuntimeError("Modeled uncertain publication")
        return ref

    def raw_read(expected):
        calls.append("read")
        assert expected == ref
        raise RuntimeError("Modeled original readback failure")

    transaction = SimpleNamespace(
        snapshot=lambda: SimpleNamespace(head=SimpleNamespace(head_sha256="d" * 64)),
        store_evidence=store,
        read_stage_evidence=raw_read,
    )
    with pytest.raises(RuntimeError):
        owner._retain(
            transaction,
            artifact.payload,
            f"physical-intake-{role}-v1:{COLLECTION}",
            "application/json",
            role,
        )
    record = owner._attempt["records"][role]
    assert canonical(record["document"]) == artifact.payload
    assert record["evidence_sha256"] == artifact.sha256
    assert record["reference"] == (None if failure == "store" else ref.to_dict())
    assert record["retention"] == (
        "COLLECTED_NOT_M1_RETAINED"
        if failure == "store"
        else "M1_PUBLISHED_READBACK_PENDING"
    )
    diagnostics = owner.retained_diagnostics()
    assert canonical(diagnostics["attempt_" + role]) == artifact.payload
    assert "document" not in diagnostics["attempt"]["records"][role]
    assert calls == (["store"] if failure == "store" else ["store", "read"])


def test_uncertain_raw_original_is_never_embedded_in_json(service):
    owner, _, _ = service
    owner._attempt = {"collection_id": COLLECTION, "records": {}}
    ref = reference(RAW)

    def failed_read(_):
        raise RuntimeError("Modeled raw readback failure")

    transaction = SimpleNamespace(
        snapshot=lambda: SimpleNamespace(head=SimpleNamespace(head_sha256="d" * 64)),
        store_evidence=lambda *a, **k: ref,
        read_stage_evidence=failed_read,
    )
    with pytest.raises(RuntimeError):
        owner._retain(
            transaction,
            RAW,
            f"physical-intake-original-v1:{COLLECTION}:00",
            "text/plain",
            "original_00",
        )
    record = owner._attempt["records"]["original_00"]
    assert record["evidence_sha256"] == digest(RAW)
    assert record["reference"] == ref.to_dict()
    assert "payload" not in record and "document" not in record
    assert RAW not in canonical(owner.retained_diagnostics())


@pytest.mark.parametrize("quota", ["references", "bytes"])
def test_submission_quota_refusal_precedes_start_and_any_evidence_write(service, quota):
    owner, data, _ = service
    prerequisites = data[1]
    workflow = owner.setup.original_source_workflow()
    item = reference(RAW)
    inventory = (
        tuple(replace(item, evidence_id=f"evidence-{i:064x}") for i in range(30))
        if quota == "references"
        else (replace(item, payload_bytes=4 * 1024 * 1024),)
    )
    calls = []
    transaction = SimpleNamespace(
        snapshot=lambda: SimpleNamespace(
            evidence=inventory, head=SimpleNamespace(head_sha256="d" * 64)
        ),
        commit_stage_state=lambda *a, **k: calls.append("commit"),
        store_evidence=lambda *a, **k: calls.append("store"),
    )
    with pytest.raises(WizardError) as caught:
        owner._submit(
            transaction,
            prerequisites,
            workflow,
            notebook(prerequisites),
            {"operator_id": "intake-operator"},
            (),
            lambda: None,
        )
    assert caught.value.code == "INTAKE_ORIGINAL_STORE_BUDGET"
    assert calls == [] and owner._attempt is None


def test_stale_context_is_rejected_before_input_or_original_store_scope(
    service, monkeypatch
):
    owner, data, state = service

    def denied(*args, **kwargs):
        pytest.fail("stale context reached IO")

    monkeypatch.setattr(owner.inbox, "selected_files", denied)
    monkeypatch.setattr(owner.setup, "intake_transaction", denied)
    with pytest.raises(WizardError) as caught:
        owner.perform(
            "physical_intake_submit",
            expected_context_sha256="0" * 64,
            notebook=notebook(data[1]),
            values={"file_only": True, "operator_id": "operator"},
            cancellation=threading.Event(),
            progress=lambda _: None,
            export_parent=Path(owner.setup.target_directory()),
        )
    assert caught.value.code == "INTAKE_CONTEXT_CHANGED"
    assert owner._attempt is None and not owner._operation_lock.locked()


def test_unreviewed_and_partial_predecessors_never_offer_successor(service):
    owner, data, state = service
    complete(data)
    owner.setup._adopt_source_workflow(read(data[0], state["header"].header_sha256))
    owner.observe_setup()
    reason = owner.blocked_reason("physical_intake_submit", notebook(data[1]))
    assert "existing submitted" in reason
    copy = owner.setup._source_workflow
    copy["intake_collections"][-1]["state"] = "INCOMPLETE"
    assert "incomplete retention" in owner.blocked_reason(
        "physical_intake_submit", notebook(data[1])
    )


def test_pending_publication_withholds_new_collection_summaries(service):
    owner, data, state = service
    complete(data)
    owner.setup._adopt_source_workflow(read(data[0], state["header"].header_sha256))
    owner.observe_setup()
    owner._publication = {"status": "PENDING", "operation_id": None}
    view = owner.view()
    assert view["collection"] is None and view["discovery"]["files"] == []
    assert view["collection_count"] == 1
    owner.publication_completed("logged")
    assert owner.view()["collection"]["state"] == "REVIEW_PENDING"

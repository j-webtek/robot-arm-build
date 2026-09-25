"""Service lifecycle with real codecs, modeled scopes and isolated actual NTFS.

No test calls a native provider, camera or arm. Synthetic UNKNOWN notes remain
explicitly unknown through submission, procedural review and original restart.
"""

from contextlib import contextmanager
from pathlib import Path
import os
from threading import Event
from time import monotonic_ns, time_ns

import pytest

from rocell.application import physical_intake_evidence_service as module
from rocell.application import physical_intake_inbox as inbox_module
from rocell.application import physical_camera_setup_service as setup_service_module
from rocell.application import physical_camera_session as session_module
from rocell.application.physical_camera_acquisition_service import (
    PhysicalCameraAcquisitionService,
)
from rocell.application.physical_onboarding import STAGE_ORDER
from rocell.application.physical_onboarding_v2 import V2StageState
from rocell.application.wizard_actions import WizardError
from rocell.providers.windows.native_camera_protocol import canonical
from test_physical_camera_intake_setup import setup_flow
from test_physical_camera_intake_session import (
    intake_model,
    notebook,
    RAW,
    SOURCE_CODES,
)
from test_physical_camera_session_readback import model, no_devices, workspace, generate
from test_physical_camera_session import SOURCE, LAUNCH, session_fixture, perform
from test_physical_camera_source_workflow_readback import collect_chain


@pytest.fixture
def modeled(setup_flow, monkeypatch):
    setup, data, state = setup_flow
    state["now"] = monotonic_ns()
    for target in (module, inbox_module):
        monkeypatch.setattr(target, "source_fingerprint", lambda _: SOURCE)
    monkeypatch.setattr(module, "monotonic_ns", lambda: state["now"])
    old = state["store"].stage_transaction

    @contextmanager
    def scope(*args, **kwargs):
        with old(*args, **kwargs) as transaction:
            transaction.store_evidence = lambda stage, payload, **kw: state["add"](
                payload, label=kw["label"], media=kw["media_type"]
            )
            transaction.commit_stage_state = lambda stage, next_state, **kw: state[
                "advance"
            ](next_state, kw["detail_code"], kw["evidence"])
            yield transaction

    state["store"].stage_transaction = scope
    (setup.workspace / "software/runs").mkdir(parents=True, exist_ok=True)
    service = module.PhysicalIntakeEvidenceService(setup)
    service.observe_setup()
    return service, notebook(data[1]), state


def run(service, action, book=None, values=None, *, publish=True, cancellation=None):
    result = service.perform(
        action,
        notebook=book,
        values=values or {"file_only": True},
        expected_context_sha256=service.context_sha256(book),
        cancellation=cancellation or Event(),
        progress=lambda _: None,
        export_parent=service.workspace / "software/runs/wizard-exports",
    )
    if publish:
        service.setup.publication_completed("test-completion-log")
        service.publication_completed("test-completion-log")
    return result


def submit_values(book, token=""):
    return {
        "file_only": True,
        "operator_id": "intake-operator",
        **{"attachment_" + row["record_id"]: token for row in book.to_dict()["rows"]},
    }


def test_submit_review_and_successor_use_actual_codecs_and_original_journal(modeled):
    service, book, state = modeled
    original_review = canonical(service.setup.original_source_workflow()["review"])
    result = run(
        service, "physical_intake_submit", book, submit_values(book), publish=False
    )
    assert result["status"] == "SUCCEEDED"
    assert service.view()["publication"]["status"] == "PENDING"
    assert service.view()["collection"] is None
    service.setup.publication_completed("submit-log")
    service.publication_completed("submit-log")
    first = service.view()["collection"]
    assert first["assessment"]["observation_completeness"] == "UNKNOWN_ROWS_REMAIN"
    assert first["submission"]["coverage"]["unknown"] == 16
    run(
        service,
        "physical_intake_review",
        book,
        {
            "file_only": True,
            "reviewer_id": "intake-reviewer",
            "decision": "ACKNOWLEDGE_FOR_LATER_STAGE_REVIEW",
        },
    )
    assert service.view()["status"] == "REVIEWED"
    assert service.blocked_reason("physical_intake_submit", book) is not None
    book = book.record(
        record_id="INT-001",
        observation_status="UNKNOWN",
        observed_value="Still awaiting hardware; revised explanatory note.",
        method="No instrument; not measured.",
        evidence_note="No original supplied.",
        operator_id="intake-operator",
        recorded_at_ns=time_ns(),
    )
    run(service, "physical_intake_submit", book, submit_values(book))
    second = service.view()["collection"]["submission"]
    assert second["sequence"] == 2
    assert (
        second["predecessor_submission_sha256"]
        == first["submission"]["submission_sha256"]
    )
    assert (
        canonical(service.setup.original_source_workflow()["review"]) == original_review
    )
    assert all(
        row.state is V2StageState.PENDING for row in state["snapshot"]().stages[1:]
    )
    assert service.view()["physical_authority"] is False


def test_real_input_bytes_single_attachment_can_support_many_unknown_rows(modeled):
    service, book, state = modeled
    run(service, "physical_intake_files_discover", book, {})
    path = service.inbox.root / "unknown.txt"
    path.write_bytes(RAW)
    run(service, "physical_intake_files_discover", book, {})
    token = service.view()["discovery"]["files"][0]["choice_id"]
    run(service, "physical_intake_submit", book, submit_values(book, token))
    current = service.view()["collection"]["submission"]
    assert current["coverage"]["attachment_count"] == 1
    assert current["coverage"]["attached_rows"] == 16
    reference = current["attachments"][0]["evidence_id"]
    assert state["payloads"][reference] == RAW
    assert RAW not in canonical(service.retained_diagnostics())


def test_partial_store_failure_is_preserved_and_not_replayed(modeled, monkeypatch):
    service, book, state = modeled
    original = service._retain

    def fail_assessment(transaction, payload, label, media, role):
        if role == "assessment":
            raise RuntimeError("modeled storage failure before assessment publication")
        return original(transaction, payload, label, media, role)

    monkeypatch.setattr(service, "_retain", fail_assessment)
    with pytest.raises(RuntimeError):
        run(service, "physical_intake_submit", book, submit_values(book))
    assert service.view()["publication"]["status"] == "HISTORICAL_HELD"
    assert service.retained_diagnostics()["attempt_submission"]
    assert len(state["events"]) == 4
    assert service.blocked_reason("physical_intake_submit", book)


@pytest.mark.skipif(os.name != "nt", reason="actual isolated Windows NTFS storage")
def test_actual_m1_service_submission_restart_review_and_private_export(
    workspace, monkeypatch
):
    for target in (module, inbox_module, setup_service_module, session_module):
        monkeypatch.setattr(target, "source_fingerprint", lambda _: SOURCE)
    owner = session_fixture(workspace)
    initial = perform(owner)
    header = initial["verification"]["session"]["header_sha256"]
    prerequisites = generate(workspace)
    sources = collect_chain(prerequisites, header, monkeypatch)
    with owner.stage_transaction(
        expected_challenge_sha256=initial["verification"]["challenge_sha256"]
    ) as tx:

        def commit(next_state, detail, refs=()):
            tx.commit_stage_state(
                STAGE_ORDER[0],
                next_state,
                occurred_at_ns=time_ns(),
                detail_code=detail,
                expected_head_sha256=tx.snapshot().head.head_sha256,
                evidence=tuple(refs),
            )

        def store(raw, label):
            return tx.store_evidence(
                STAGE_ORDER[0],
                raw,
                label=label,
                media_type="application/json",
                captured_at_ns=time_ns(),
                expected_head_sha256=tx.snapshot().head.head_sha256,
            )

        commit(V2StageState.WAITING_OPERATOR, SOURCE_CODES[0])
        store(prerequisites.payload, session_module.PREREQUISITE_LABEL)
        refs = [
            store(sources[role].payload, f"workspace-source-{role}-v1")
            for role in ("receipt", "assessment")
        ]
        commit(V2StageState.REVIEW_PENDING, SOURCE_CODES[1], refs)
        refs.append(store(sources["review"].payload, "workspace-source-review-v1"))
        commit(V2StageState.BLOCKED, SOURCE_CODES[2], refs)

    def open_service(original):
        perform(original, "refresh")
        workflow = original.read_original_source_workflow(
            expected_header_sha256=header, cancellation=Event(), progress=lambda _: None
        )
        setup = setup_service_module.PhysicalCameraSetupService(
            PhysicalCameraAcquisitionService(
                workspace, launch_id=LAUNCH, source_sha256=SOURCE, mode="physical"
            )
        )
        setup.session = original  # Same original path; not a replacement store.
        setup._adopt_source_workflow(workflow)
        setup._publication = {
            "status": "CURRENT",
            "operation_id": "test-original-audit",
        }
        evidence = module.PhysicalIntakeEvidenceService(setup)
        evidence.observe_setup()
        return evidence

    service = open_service(owner)
    book = notebook(prerequisites)
    run(service, "physical_intake_files_discover", book, {})
    path = service.inbox.root / "unknown.txt"
    path.write_bytes(RAW)
    run(service, "physical_intake_files_discover", book, {})
    token = service.view()["discovery"]["files"][0]["choice_id"]
    run(service, "physical_intake_submit", book, submit_values(book, token))
    before = service.view()["collection"]
    path.unlink()  # Test-only input: original M1 bytes must suffice after restart.
    restored = open_service(session_fixture(workspace))
    assert restored.view()["collection"] == before
    assert restored.view()["discovery"]["status"] == "NOT_DISCOVERED"
    run(
        restored,
        "physical_intake_review",
        None,
        {
            "file_only": True,
            "reviewer_id": "intake-reviewer",
            "decision": "ACKNOWLEDGE_FOR_LATER_STAGE_REVIEW",
        },
    )
    export_parent = workspace / "software/runs/wizard-exports"
    assert not export_parent.exists()  # Explicit raw export prepares its parent.
    result = run(
        restored,
        "physical_intake_export_originals",
        None,
        {"file_only": True, "include_private_originals": True},
    )
    receipt = result["steps"][0]["report"]["private_original_export"]
    assert receipt["original_bytes_preserved"] is True
    folder = Path(receipt["path"])
    assert any(
        child.read_bytes() == RAW for child in folder.iterdir() if child.is_file()
    )
    assert restored.view()["status"] == "REVIEWED"
    assert restored.setup.session.view()["stages"][0]["state"] == "BLOCKED"
    assert all(
        row["state"] == "PENDING" for row in restored.setup.session.view()["stages"][1:]
    )
    assert not path.exists()

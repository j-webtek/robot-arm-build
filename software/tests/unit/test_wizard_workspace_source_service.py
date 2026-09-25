"""Actual service/codec joins with explicitly modeled storage (no device/M1 IO).

The separate public file-only smoke covers real transactions and restart. These
tests inject uncertain writes and publication failures without touching it.
"""

from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import time

import pytest

from rocell.application import physical_camera_setup_service as module
from rocell.application.physical_onboarding import EvidenceReference, STAGE_ORDER
from rocell.application.physical_onboarding_v2 import V2StageState
from rocell.application.wizard_actions import WizardError
from rocell.application.wizard_diagnostic_export import verify_export
from rocell.providers.windows.native_camera_protocol import canonical, digest
from test_arrival_wizard_service import make_service, _run, _ticket, _complete
from test_physical_camera_restart_service import (
    modeled,
    discover,
    reopen,
    no_runtime_or_devices,
    workspace,
    SOURCE,
)

ROOT = Path(__file__).resolve().parents[3]
ASSESS = "physical_camera_assess_sources"
REVIEW = "physical_camera_review_sources"


@pytest.fixture
def source_flow(modeled, monkeypatch):
    from rocell.application import physical_source_stage_evidence as codec

    discover(modeled)
    assert reopen(modeled)["status"] == "SUCCEEDED"
    service, setup, source, calls, *_ = modeled
    original_collect = codec.collect_workspace_source_receipt
    monkeypatch.setattr(codec, "source_fingerprint", lambda _: SOURCE)
    monkeypatch.setattr(module, "source_fingerprint", lambda _: SOURCE)
    monkeypatch.setattr(
        codec,
        "collect_workspace_source_receipt",
        lambda _workspace, **kwargs: original_collect(ROOT, **kwargs),
    )
    state = {
        "workflow": deepcopy(setup._source_workflow),
        "calls": [],
        "fault": None,
        "new": {},
    }
    session = setup.session

    def snapshot():
        return SimpleNamespace(
            next_action=SimpleNamespace(
                stage=STAGE_ORDER[0],
                stage_state=V2StageState(state["workflow"]["state"]),
            ),
            head=SimpleNamespace(head_sha256=state["workflow"]["session_head_sha256"]),
        )

    def advance():
        state["workflow"]["session_head_sha256"] = digest(canonical(state["calls"]))

    def store(stage, payload, **kwargs):
        assert kwargs["expected_head_sha256"] == snapshot().head.head_sha256
        role = kwargs["label"].removeprefix("workspace-source-").removesuffix("-v1")
        state["calls"].append("store-" + role)
        sha = digest(payload)
        ref = EvidenceReference(
            "evidence-" + sha, stage, sha, "d" * 64, sha, len(payload)
        )
        import json

        state["new"][ref.evidence_id] = payload
        state["workflow"][role] = {
            "document": json.loads(payload),
            "evidence_sha256": sha,
            "retention": "M1_FULL_BYTES_READ_BACK",
            "reference": ref.to_dict(),
        }
        advance()
        return ref

    def read(ref):
        state["calls"].append("read")
        if state["fault"] == "readback":
            raise RuntimeError("Modeled uncertain post-store read failure")
        return state["new"][ref.evidence_id]

    def commit(stage, value, **kwargs):
        assert kwargs["expected_head_sha256"] == snapshot().head.head_sha256
        state["calls"].append("commit-" + value.value)
        if state["fault"] == "commit":
            raise RuntimeError("Modeled uncertain stage commit")
        state["workflow"]["state"] = value.value
        state["evidence"] = [ref.evidence_id for ref in kwargs["evidence"]]
        # Real V2 replays event-reference occurrences, not a deduplicated
        # inventory: assessment refs2 plus reviewed refs3 yields five entries.
        state.setdefault("stage_evidence", []).extend(state["evidence"])
        advance()
        return snapshot()

    @contextmanager
    def transaction(**kwargs):
        state["calls"].append("scope")
        try:
            yield SimpleNamespace(
                snapshot=snapshot,
                store_evidence=store,
                read_stage_evidence=read,
                commit_stage_state=commit,
            )
        finally:
            session._cached.update(status="HELD", verification=None, stages=None)

    def refresh(**kwargs):
        state["calls"].append("refresh")
        if state["fault"] == "refresh":
            raise RuntimeError("Modeled audit failure after a committed transition")
        session._cached.update(
            status="REFRESHED_STORAGE_ONLY",
            verification={
                "effects_allowed_by_m1_storage": True,
                "challenge_sha256": "c" * 64,
                "session": {
                    "header_sha256": state["workflow"]["session_header_sha256"]
                },
            },
            stages=[
                {
                    "stage": row.value,
                    "state": state["workflow"]["state"] if i == 0 else "PENDING",
                    "last_event_sequence": 1 if i == 0 else None,
                    "evidence_ids": state.get("stage_evidence", []) if i == 0 else [],
                }
                for i, row in enumerate(STAGE_ORDER)
            ],
        )

    def read_workflow(**kwargs):
        state["calls"].append("audit-readback")
        return deepcopy(state["workflow"])

    monkeypatch.setattr(session, "stage_transaction", transaction)
    monkeypatch.setattr(session, "refresh", refresh)
    monkeypatch.setattr(session, "read_original_source_workflow", read_workflow)
    return service, setup, state, source


def assess(service):
    ticket = _ticket(service, ASSESS, {"operator_id": "operator-a", "file_only": True})
    operation = service.execute_action(ticket["ticket_id"])["operation_id"]
    deadline = time.monotonic() + 40
    while time.monotonic() < deadline:
        result = service.operation(operation)
        if result["status"] in {"SUCCEEDED", "FAILED", "CANCELLED", "TIMED_OUT"}:
            return result
        time.sleep(0.01)
    pytest.fail("Actual bounded file collector exceeded test's 40-second budget")


def review(service, reviewer="reviewer-b"):
    return _run(service, REVIEW, {"reviewer_id": reviewer, "file_only": True})


def test_assess_review_commits_only_review_pending_then_blocked(source_flow):
    service, setup, state, _ = source_flow
    outcome = assess(service)
    assert outcome["status"] == "SUCCEEDED", outcome
    assert setup.view()["source_workflow"]["status"] == "REVIEW_PENDING"
    assert state["calls"] == [
        "scope",
        "store-receipt",
        "read",
        "store-assessment",
        "read",
        "commit-REVIEW_PENDING",
        "refresh",
        "audit-readback",
    ]
    assert review(service)["status"] == "SUCCEEDED"
    view = service.view()
    assert (
        view["physical_camera_setup"]["source_workflow"]["status"] == "REVIEWED_BLOCKED"
    )
    assert len(state["evidence"]) == 3
    assert (
        len(view["physical_camera_setup"]["session"]["stages"][0]["evidence_ids"]) == 5
    )
    assert all(row["state"] == "PHYSICAL_PENDING" for row in view["stages"])
    assert view["camera"]["status"] == view["arm"]["status"] == "NOT_CONNECTED"
    assert len(set(state["evidence"])) == 3
    with pytest.raises(WizardError):
        _ticket(service, REVIEW, {"reviewer_id": "another", "file_only": True})


@pytest.mark.parametrize(
    "name,actor", [(ASSESS, "operator_id"), (REVIEW, "reviewer_id")]
)
@pytest.mark.parametrize("consent", [None, False, 1, "true"])
def test_explicit_file_only_confirmation_required(source_flow, name, actor, consent):
    service, _, state, _ = source_flow
    with pytest.raises(WizardError):
        _ticket(service, name, {actor: "actor", "file_only": consent})
    assert state["calls"] == []


@pytest.mark.parametrize("fault", ["readback", "commit", "refresh"])
def test_uncertain_write_is_retained_not_replayed_or_published(source_flow, fault):
    service, setup, state, _ = source_flow
    state["fault"] = fault
    assert assess(service)["status"] == "FAILED"
    diagnostics = setup.retained_source_diagnostics()
    assert diagnostics["assessment_attempted"] is True
    assert diagnostics["attempt_receipt_document"]["physical_authority"] is False
    assert setup.view()["publication"]["status"] == "HISTORICAL_HELD"
    with pytest.raises(WizardError):
        _ticket(service, ASSESS, {"operator_id": "actor", "file_only": True})


@pytest.mark.parametrize("reviewer", ["operator-a", "OPERATOR-A"])
def test_same_reviewer_casefold_rejected_before_write(source_flow, reviewer):
    service, setup, state, _ = source_flow
    assert assess(service)["status"] == "SUCCEEDED"
    before = deepcopy(state["calls"])
    assert review(service, reviewer)["status"] == "FAILED"
    assert state["calls"] == before
    assert not setup._review_attempted


def test_exact_context_ticket_rejects_changed_original_head(source_flow):
    service, setup, state, _ = source_flow
    ticket = _ticket(service, ASSESS, {"operator_id": "actor", "file_only": True})
    setup._source_workflow["session_head_sha256"] = "a" * 64
    outcome = _complete(
        service, service.execute_action(ticket["ticket_id"])["operation_id"]
    )
    assert outcome["status"] == "FAILED"
    assert outcome["result"]["code"] == "CAMERA_SETUP_CONTEXT_CHANGED"
    assert state["calls"] == []


@pytest.mark.parametrize("fault", ["stop", "source", "log"])
def test_completed_evidence_survives_late_publication_failure(
    source_flow, monkeypatch, fault
):
    service, setup, state, source = source_flow
    original = setup.perform

    def late(*args, **kwargs):
        result = original(*args, **kwargs)
        if fault == "stop":
            kwargs["cancellation"].set()
        elif fault == "source":
            source["hash"] = "f" * 64
        return result

    monkeypatch.setattr(setup, "perform", late)
    if fault == "log":
        append = service._append_event
        monkeypatch.setattr(
            service,
            "_append_event",
            lambda name, data: (
                False if name == "ACTION_FINISHED" else append(name, data)
            ),
        )
    outcome = assess(service)
    assert outcome["status"] == ("SUCCEEDED" if fault == "stop" else "FAILED")
    assert (
        setup.retained_source_diagnostics()["assessment_document"]["verdict"]
        == "BLOCKED"
    )
    assert (
        service.view()["physical_camera_setup"]["source_workflow"]["status"]
        == "HISTORICAL_HELD"
    )


def test_full_source_export_survives_result_rotation(source_flow):
    import json

    service, setup, _, _ = source_flow
    assert assess(service)["status"] == review(service)["status"] == "SUCCEEDED"
    original = setup.retained_source_diagnostics()
    for index in range(9):
        assert (
            _run(service, "record_note", {"note": "rotation " + str(index)})["status"]
            == "SUCCEEDED"
        )
    outcome = _run(service, "export_logs")
    assert outcome["status"] == "SUCCEEDED", outcome
    folder = Path(outcome["result"]["receipt"]["path"])
    assert verify_export(folder)["valid"]
    document = json.loads(
        (folder / "attachment-workspace-source-workflow.json").read_bytes()
    )
    assert document["schema"] == "rocell.wizard_workspace_source_export.v1"
    assert document["publication"] == "REVIEWED_BLOCKED"
    assert document["original_bytes_preserved"] is True
    for role in ("receipt", "assessment", "review", "prerequisites"):
        assert document[role + "_document"] == original[role + "_document"]


def test_stop_during_pre_mutation_source_check_prevents_the_next_write(
    source_flow, monkeypatch
):
    service, setup, state, _ = source_flow
    captured = {}
    original = setup.perform

    def capture(*args, **kwargs):
        captured["cancel"] = kwargs["cancellation"]
        return original(*args, **kwargs)

    monkeypatch.setattr(setup, "perform", capture)
    calls = []

    def fingerprint(_):
        calls.append(1)
        if len(calls) == 3:
            captured["cancel"].set()
        return SOURCE

    monkeypatch.setattr(module, "source_fingerprint", fingerprint)
    outcome = assess(service)
    assert outcome["status"] != "SUCCEEDED"
    assert state["calls"] == ["scope"]
    assert (
        setup.retained_source_diagnostics()["attempt_records"]["receipt"]["retention"]
        == "COLLECTED_NOT_M1_RETAINED"
    )


def test_post_commit_readback_receives_the_existing_action_deadline(
    source_flow, monkeypatch
):
    service, setup, state, _ = source_flow
    captured = []
    original = setup.session.read_original_source_workflow

    def read(**kwargs):
        captured.append(kwargs["deadline_ns"])
        return original(**kwargs)

    monkeypatch.setattr(setup.session, "read_original_source_workflow", read)
    before = module.monotonic_ns()
    assert assess(service)["status"] == "SUCCEEDED"
    after = module.monotonic_ns()
    assert (
        len(captured) == 1
        and before + 120_000_000_000 <= captured[0] <= after + 120_000_000_000
    )


def test_late_collector_failure_keeps_verified_receipt_without_claiming_m1(
    source_flow, monkeypatch
):
    from rocell.application import physical_source_stage_evidence as codec

    service, setup, state, _ = source_flow
    original = codec.collect_workspace_source_receipt

    def late(*args, **kwargs):
        artifact = original(*args, **kwargs)
        raise codec.WorkspaceSourceEvidenceError(
            "SOURCE_PIN_CLOSE_FAILED", receipt=artifact
        )

    monkeypatch.setattr(codec, "collect_workspace_source_receipt", late)
    assert assess(service)["status"] == "FAILED"
    retained = setup.retained_source_diagnostics()
    assert (
        retained["attempt_records"]["receipt"]["retention"]
        == "COLLECTED_NOT_M1_RETAINED"
    )
    assert retained["attempt_records"]["receipt"]["reference"] is None
    assert (
        digest(canonical(retained["attempt_receipt_document"]))
        == retained["attempt_records"]["receipt"]["evidence_sha256"]
    )
    assert state["calls"] == []

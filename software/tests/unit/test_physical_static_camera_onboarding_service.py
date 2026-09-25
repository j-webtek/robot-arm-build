"""Actual design collector/service joins with explicitly modeled predecessors.

The source-isolation/ownership claims and M1 scopes are test models only. The
design bytes, codecs, assessments, service and original-reader joins are real.
An independent reader test covers actual NTFS storage and restart.
"""

from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from threading import Event

import pytest

from rocell.application import physical_static_camera_onboarding_service as module
from rocell.application import physical_static_contract as codec
from rocell.application.wizard_actions import WizardError
from rocell.providers.windows.native_camera_protocol import canonical, digest

from test_physical_source_qualification_service import modeled, run, observed
from test_physical_camera_intake_setup import setup_flow
from test_physical_source_qualification_readback import source_model
from test_physical_camera_intake_session import intake_model
from test_physical_camera_session_readback import model, no_devices, workspace
from test_physical_camera_session import SOURCE

WORKSPACE = Path(__file__).resolve().parents[3]
COLLECT = "physical_static_contract_collect"
REVIEW = "physical_static_contract_review"
BEGIN = "physical_camera_receipt_begin"


@pytest.fixture
def static_service(modeled, monkeypatch):
    source, state = modeled
    run(source, "physical_source_qualify", observed(source))
    run(
        source,
        "physical_source_qualification_review",
        {
            "file_only": True,
            "reviewer_id": "source-reviewer",
        },
    )
    run(source, "physical_static_contract_begin")
    service = module.PhysicalStaticCameraOnboardingService(source.setup)
    service.observe_setup()
    state["source_service"] = source
    state["static_collections"] = []
    monkeypatch.setattr(module, "source_fingerprint", lambda _: state["source"])
    monkeypatch.setattr(module, "monotonic_ns", lambda: state["now"])
    monkeypatch.setattr(codec, "source_fingerprint", lambda _: state["source"])

    # Exercise the actual controlled-file producer. Only the source predecessor
    # and store ownership are modeled; do not invent a positive design receipt.
    def collect(workspace, **kwargs):
        value = codec.collect_static_camera_contract(WORKSPACE, **kwargs)
        state["static_collections"].append(value)
        return value

    monkeypatch.setattr(module, "collect_static_camera_contract", collect)
    previous = state["store"].stage_transaction

    @contextmanager
    def transaction(*args, **kwargs):
        with previous(*args, **kwargs) as tx:
            tx.store_evidence = lambda stage, payload, **kw: state["add"](
                payload, label=kw["label"], stage=stage, media=kw["media_type"]
            )
            yield tx

    state["store"].stage_transaction = transaction
    return service, state


def collect(service, **kwargs):
    return run(
        service,
        COLLECT,
        {
            "file_only": True,
            "operator_id": "static-operator",
        },
        **kwargs
    )


def review(service, **kwargs):
    return run(
        service,
        REVIEW,
        {
            "file_only": True,
            "reviewer_id": "static-reviewer",
        },
        **kwargs
    )


def test_actual_design_review_then_explicit_receipt_entry(static_service):
    service, state = static_service
    legacy = service.setup.original_source_workflow()["review"]
    assert service.view()["next_action"] == COLLECT
    result = collect(service, publish=False)
    assert service.view()["publication"]["status"] == "PENDING"
    assert service.view()["contract"] is None
    changed = deepcopy(result)
    changed["steps"][0]["report"]["physical_authority"] = True
    with pytest.raises(WizardError):
        service.validate_publication(changed)
    service.setup.publication_completed("design-log")
    service.publication_completed("design-log")
    current = service.view()
    assert current["status"] == "REVIEW_PENDING"
    assert current["stage_states"] == {
        "workspace_sources": "PASS",
        "static_camera_contract": "REVIEW_PENDING",
        "camera_receipt": "PENDING",
    }
    assert current["contract"]["assessment"]["verdict"] == "PASS"
    assert current["next_action"] == REVIEW
    review(service)
    assert service.view()["status"] == "REVIEWED_PASS"
    assert service.view()["stage_states"]["camera_receipt"] == "PENDING"
    assert service.view()["next_action"] == BEGIN
    run(service, BEGIN)
    assert service.view()["stage_states"]["camera_receipt"] == "WAITING_OPERATOR"
    assert service.view()["camera_receipt_entry"] == state["events"][-1].event_sha256
    assert not state["events"][-1].evidence
    assert service.view()["next_action"] is None
    assert service.setup.original_source_workflow()["review"] == legacy
    state["source_service"].observe_setup()
    assert state["source_service"].view()["publication"]["status"] == "HISTORICAL_HELD"
    assert len(state["static_collections"]) == 1
    for flag in module._FLAGS:
        assert service.view()[flag] is False


def test_views_fields_and_context_are_inert_and_detached(static_service, monkeypatch):
    service, state = static_service
    monkeypatch.setattr(module, "source_fingerprint", lambda _: pytest.fail("view I/O"))
    before = state["reads"], state["enters"], len(state["static_collections"])
    service.view()["publication"]["status"] = "changed"
    for action in module.ACTIONS:
        service.fields(action)
        service.blocked_reason(action)
    service.context_sha256()
    assert service.view()["publication"]["status"] == "CURRENT"
    assert before == (state["reads"], state["enters"], len(state["static_collections"]))


@pytest.mark.parametrize("fault", ["stop", "source", "context", "checkbox", "actor"])
def test_preflight_no_collection_or_mutation(static_service, fault):
    service, state = static_service
    event, context = Event(), service.context_sha256()
    values = {"file_only": True, "operator_id": "static-operator"}
    if fault == "stop":
        event.set()
    elif fault == "source":
        state["source"] = "f" * 64
    elif fault == "context":
        context = "f" * 64
    elif fault == "checkbox":
        values["file_only"] = False
    else:
        values["operator_id"] = "../operator"
    before = len(state["events"]), len(state["references"])
    with pytest.raises(WizardError):
        service.perform(
            COLLECT,
            values,
            expected_context_sha256=context,
            cancellation=event,
            progress=lambda _: None,
        )
    assert before == (len(state["events"]), len(state["references"]))
    assert not state["static_collections"]


def test_same_reviewer_rejected_without_consuming_valid_review(static_service):
    service, state = static_service
    collect(service)
    before = len(state["events"]), len(state["references"])
    with pytest.raises(codec.StaticCameraContractError):
        run(service, REVIEW, {"file_only": True, "reviewer_id": "STATIC-OPERATOR"})
    assert before == (len(state["events"]), len(state["references"]))
    assert service.blocked_reason(REVIEW) is None
    review(service)


@pytest.mark.parametrize("fault", ["source", "stop", "head"])
def test_post_collection_change_retains_diagnostics_without_append(
    static_service, monkeypatch, fault
):
    service, state = static_service
    original, event = module.collect_static_camera_contract, Event()

    def changed(workspace, **kwargs):
        value = original(workspace, **kwargs)
        if fault == "source":
            state["source"] = "f" * 64
        elif fault == "stop":
            event.set()
        else:
            service.setup._source_workflow["session_head_sha256"] = "f" * 64
        return value

    monkeypatch.setattr(module, "collect_static_camera_contract", changed)
    before = len(state["events"]), len(state["references"])
    with pytest.raises(WizardError):
        collect(service, cancellation=event)
    assert before == (len(state["events"]), len(state["references"]))
    diagnostic = service.retained_diagnostics()
    assert (
        diagnostic["static_attempt_collected_receipt"]
        == state["static_collections"][0].to_dict()
    )
    assert service.view()["publication"]["status"] == "HISTORICAL_HELD"


@pytest.mark.parametrize("fault", ["assessment-store", "refresh", "lease-exit"])
def test_partial_or_late_failures_remain_historical_no_replay(
    static_service, monkeypatch, fault
):
    service, state = static_service
    original = service._retain

    def fail(tx, artifact, role, contract):
        if role == "assessment" and fault == "assessment-store":
            raise RuntimeError("modeled assessment write failure")
        return original(tx, artifact, role, contract)

    monkeypatch.setattr(service, "_retain", fail)
    if fault == "refresh":
        state["refresh_error"] = True
    elif fault == "lease-exit":
        state["exit_failure"] = True
    with pytest.raises((RuntimeError, ValueError)):
        collect(service)
    assert service.view()["publication"]["status"] == "HISTORICAL_HELD"
    assert service.setup.view()["publication"]["status"] == "HISTORICAL_HELD"
    assert service.blocked_reason(COLLECT)
    assert service.retained_diagnostics()["attempt"] is not None


def test_full_diagnostics_deduplicate_subjects_and_legacy_source(static_service):
    service, _ = static_service
    collect(service)
    review(service)
    diagnostic = service.retained_diagnostics()
    original = service.setup.original_source_workflow()["static_contract"]
    for role in ("receipt", "assessment", "review"):
        record = diagnostic["static_contract"][role]
        assert (
            digest(canonical(diagnostic[record["document_key"]]))
            == original[role]["evidence_sha256"]
        )
    attempted = diagnostic["attempt"]["records"]["review"]
    assert (
        attempted["document_key"]
        == diagnostic["static_contract"]["review"]["document_key"]
    )
    legacy = service.setup.retained_source_diagnostics()
    assert "static_contract" not in legacy["original"]
    assert legacy["static_contract_sha256"] == digest(canonical(original))
    assert (
        legacy["static_contract_summary"]["review_sha256"]
        == original["review"]["evidence_sha256"]
    )


def test_complete_collector_failure_receipt_kept_without_store_append(
    static_service, monkeypatch
):
    service, state = static_service
    original = module.collect_static_camera_contract

    def fail(workspace, **kwargs):
        receipt = original(workspace, **kwargs)
        raise codec.StaticCameraContractError("MODELED_LATE_CLEANUP", receipt=receipt)

    monkeypatch.setattr(module, "collect_static_camera_contract", fail)
    before = len(state["events"]), len(state["references"])
    with pytest.raises(codec.StaticCameraContractError, match="MODELED_LATE_CLEANUP"):
        collect(service)
    diagnostic = service.retained_diagnostics()
    assert (
        diagnostic["static_attempt_collected_receipt"]
        == state["static_collections"][0].to_dict()
    )
    assert before == (len(state["events"]), len(state["references"]))
    assert service.blocked_reason(COLLECT)


def test_changed_original_predecessor_rejected_before_static_retention(
    static_service, monkeypatch
):
    service, state = static_service
    original = module.collect_static_camera_contract

    def changed(workspace, **kwargs):
        receipt = original(workspace, **kwargs)
        qualification = service.setup.original_source_workflow()[
            "qualification_cycles"
        ][-1]
        reference = qualification["review"]["reference"]["evidence_id"]
        state["payloads"][reference] += b" "
        return receipt

    monkeypatch.setattr(module, "collect_static_camera_contract", changed)
    before = len(state["events"]), len(state["references"])
    with pytest.raises((WizardError, ValueError)):
        collect(service)
    assert before == (len(state["events"]), len(state["references"]))
    assert service.retained_diagnostics()["static_attempt_collected_receipt"]
    assert service.view()["publication"]["status"] == "HISTORICAL_HELD"

"""Original service composition with real codecs and modeled hardware facts.

These cases do not claim physical isolation or received-camera qualification.
The ownership collector's separate integration test exercises the actual fixed
child; this suite models that bounded result so application faults are cheap.
"""

from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from threading import Event
from time import monotonic_ns

import pytest

from rocell.application import physical_source_qualification_service as module
from rocell.application import physical_intake_inbox as inbox_module
from rocell.application import physical_source_qualification as codec
from rocell.application.physical_source_stage_evidence import WorkspaceSourceReceipt
from rocell.application.physical_intake_evidence_service import (
    PhysicalIntakeEvidenceService,
)
from rocell.application.physical_onboarding import STAGE_ORDER
from rocell.application.wizard_actions import WizardError
from rocell.providers.windows.native_camera_protocol import canonical

from test_physical_camera_intake_setup import setup_flow
from test_physical_source_qualification_readback import source_model, RAW
from test_physical_camera_intake_session import intake_model
from test_physical_camera_session_readback import model, no_devices, workspace
from test_physical_camera_session import SOURCE
from test_physical_ownership_qualification import modeled_report


@pytest.fixture
def modeled(setup_flow, source_model, monkeypatch):
    setup, _, state = setup_flow
    state["now"] = monotonic_ns()
    state["collector_calls"] = []
    for target in (module, inbox_module):
        monkeypatch.setattr(target, "source_fingerprint", lambda _: state["source"])
    monkeypatch.setattr(module, "monotonic_ns", lambda: state["now"])
    old = state["store"].stage_transaction

    @contextmanager
    def scope(*args, **kwargs):
        with old(*args, **kwargs) as tx:
            tx.store_evidence = lambda stage, payload, **kw: state["add"](
                payload, label=kw["label"], media=kw["media_type"]
            )
            tx.commit_stage_state = lambda stage, next_state, **kw: state["advance"](
                next_state, kw["detail_code"], kw["evidence"], stage=stage
            )
            yield tx

    state["store"].stage_transaction = scope
    source = setup.original_source_workflow()["receipt"]["document"]

    def software(workspace, **kwargs):
        state["collector_calls"].append("software")
        data = deepcopy(source)
        data["binding"].update(
            operator_id=kwargs["operator_id"],
            collection_launch_id=kwargs["collection_launch_id"],
        )
        return WorkspaceSourceReceipt(canonical(data))

    def ownership(workspace, **kwargs):
        state["collector_calls"].append("ownership")
        return modeled_report(
            source_sha256=SOURCE,
            directory=kwargs["assigned_directory"],
            workspace=workspace,
            covered=state.get("covered", True),
        )

    monkeypatch.setattr(module, "collect_workspace_source_receipt", software)
    monkeypatch.setattr(module, "collect_physical_ownership_qualification", ownership)
    (setup.workspace / "software/runs").mkdir(parents=True, exist_ok=True)
    service = module.PhysicalSourceQualificationService(setup)
    service.observe_setup()
    return service, state


def run(service, action, values=None, *, publish=True, cancellation=None):
    result = service.perform(
        action,
        values or {"file_only": True},
        expected_context_sha256=service.context_sha256(),
        cancellation=cancellation or Event(),
        progress=lambda _: None,
    )
    service.validate_publication(result)
    if publish:
        service.setup.publication_completed("modeled-completion-log")
        service.publication_completed("modeled-completion-log")
    return result


def values(**extra):
    return {
        "file_only": True,
        "operator_id": "source-operator",
        "isolation_state": "UNKNOWN",
        "isolation_statement": "",
        "isolation_choice": "",
        **extra,
    }


def observed(service):
    run(service, "physical_source_isolation_files_discover")
    (service.inbox.root / "modeled.txt").write_bytes(RAW)
    run(service, "physical_source_isolation_files_discover")
    return values(
        isolation_state="OBSERVED_DISCONNECTED",
        isolation_statement="Modeled observation only; this test is not received hardware evidence.",
        isolation_choice=service.inbox.choices()[0]["value"],
    )


def test_unknown_collection_review_successor_and_legacy_history(modeled):
    service, state = modeled
    before = service.setup.original_source_workflow()["review"]
    result = run(service, "physical_source_qualify", values(), publish=False)
    assert result["status"] == "SUCCEEDED"
    assert service.view()["qualification"] is None
    assert service.view()["publication"]["status"] == "PENDING"
    assert service.setup.source_workflow_view()["review"] is None
    service.setup.publication_completed("collected")
    service.publication_completed("collected")
    first = service.view()["qualification"]
    assert first["isolation"]["state"] == "UNKNOWN"
    assert first["verdict"] == "BLOCKED"
    assert first["missing_requirements"] == [
        "DISCONNECTED_ACTUATOR_OBSERVATION_REQUIRED"
    ]
    assert service.view()["next_action"] == "physical_source_qualification_review"
    run(
        service,
        "physical_source_qualification_review",
        {"file_only": True, "reviewer_id": "source-reviewer"},
    )
    assert service.view()["status"] == "REVIEWED_BLOCKED"
    assert service.view()["next_action"] == "physical_source_qualify"
    assert service.setup.source_workflow_view()["status"] == "HISTORICAL_HELD"
    assert service.setup.original_source_workflow()["review"] == before
    legacy = PhysicalIntakeEvidenceService(service.setup)
    legacy.observe_setup()
    assert legacy.blocked_reason("physical_intake_files_discover", None)
    run(service, "physical_source_qualify", values())
    cycle = service.setup.original_source_workflow()["qualification_cycles"][-1]
    assert (
        cycle["receipt"]["document"]["binding"]["predecessor_qualification"]["receipt"]
        == first["receipt_sha256"]
    )
    assert len(state["collector_calls"]) == 4


def test_modeled_pass_requires_distinct_review_then_explicit_stage2(modeled):
    service, state = modeled
    supplied = observed(service)
    run(service, "physical_source_qualify", supplied)
    assert service.view()["qualification"]["verdict"] == "PASS"
    assert service.view()["stage_states"]["workspace_sources"] == "REVIEW_PENDING"
    assert service.view()["stage_states"]["static_camera_contract"] == "PENDING"
    before = len(state["events"])
    with pytest.raises(codec.SourceQualificationError):
        run(
            service,
            "physical_source_qualification_review",
            {"file_only": True, "reviewer_id": "SOURCE-OPERATOR"},
        )
    assert len(state["events"]) == before
    # Invalid input did not change original setup; exact review can be requested.
    run(
        service,
        "physical_source_qualification_review",
        {"file_only": True, "reviewer_id": "source-reviewer"},
    )
    assert service.view()["status"] == "REVIEWED_PASS"
    assert service.view()["next_action"] == "physical_static_contract_begin"
    run(service, "physical_static_contract_begin")
    assert service.view()["stage_states"] == {
        "workspace_sources": "PASS",
        "static_camera_contract": "WAITING_OPERATOR",
    }
    assert not state["events"][-1].evidence
    assert service.blocked_reason("physical_static_contract_begin")
    assert all(row.state.value == "PENDING" for row in state["snapshot"]().stages[2:])
    for flag in (
        "physical_authority",
        "hardware_qualified",
        "native_release_allowed",
        "device_io_performed",
    ):
        assert service.view()[flag] is False


@pytest.mark.parametrize(
    "extra",
    [
        {"operator_id": "../actor"},
        {"file_only": False},
        {"isolation_state": "OBSERVED_DISCONNECTED"},
        {"isolation_statement": "x" * 513},
        {"isolation_statement": "é" * 257},
        {"isolation_statement": "hidden\nline"},
        {"isolation_statement": " hidden"},
        {"isolation_statement": "hidden\x85line"},
        {"isolation_choice": "unpublished"},
    ],
)
def test_invalid_input_never_runs_collector_or_appends_original(modeled, extra):
    service, state = modeled
    before = len(state["events"])
    with pytest.raises((WizardError, ValueError)):
        run(service, "physical_source_qualify", values(**extra))
    assert len(state["events"]) == before
    assert not state["collector_calls"]


def test_views_and_fields_are_inert_and_detached(modeled, monkeypatch):
    service, state = modeled
    monkeypatch.setattr(
        module, "source_fingerprint", lambda _: pytest.fail("view performed source I/O")
    )
    before = (state["reads"], state["enters"], deepcopy(state["collector_calls"]))
    view = service.view()
    view["publication"]["status"] = "tampered"
    for action in module.ACTIONS:
        service.fields(action)
        service.blocked_reason(action)
    service.context_sha256()
    assert service.view()["publication"]["status"] == "CURRENT"
    assert before == (state["reads"], state["enters"], state["collector_calls"])


@pytest.mark.parametrize("fault", ["stop", "source", "context"])
def test_preflight_refusal_has_no_experiments_or_stage_mutation(modeled, fault):
    service, state = modeled
    event, expected = Event(), service.context_sha256()
    if fault == "stop":
        event.set()
    elif fault == "source":
        state["source"] = "f" * 64
    else:
        expected = "f" * 64
    before = len(state["events"])
    with pytest.raises(WizardError):
        service.perform(
            "physical_source_qualify",
            values(),
            expected_context_sha256=expected,
            cancellation=event,
            progress=lambda _: None,
        )
    assert len(state["events"]) == before and not state["collector_calls"]


def test_failed_ownership_cannot_assess_pass_with_observed_isolation(modeled):
    service, state = modeled
    state["covered"] = False
    run(service, "physical_source_qualify", observed(service))
    assert service.view()["qualification"]["verdict"] == "BLOCKED"
    assert (
        "SOFTWARE_OWNERSHIP_QUALIFICATION_REQUIRED"
        in service.view()["qualification"]["missing_requirements"]
    )


def test_changed_result_cannot_publish_and_raw_bytes_are_never_json_exported(modeled):
    service, _ = modeled
    result = run(service, "physical_source_qualify", observed(service), publish=False)
    bad = deepcopy(result)
    bad["steps"][0]["report"]["qualification"]["verdict"] = "BLOCKED"
    with pytest.raises(WizardError):
        service.validate_publication(bad)
    diagnostics = service.retained_diagnostics()
    assert RAW not in canonical(diagnostics)
    assert "qualification_1_receipt_ownership_report" in diagnostics
    assert (
        "qualification_cycles"
        not in service.setup.retained_source_diagnostics()["original"]
    )


def test_late_partial_write_stays_historical_and_cannot_replay(modeled, monkeypatch):
    service, state = modeled
    original = service._retain

    def fail(tx, payload, role, *args, **kwargs):
        if role == "assessment":
            raise RuntimeError("modeled failure before assessment publication")
        return original(tx, payload, role, *args, **kwargs)

    monkeypatch.setattr(service, "_retain", fail)
    with pytest.raises(RuntimeError):
        run(service, "physical_source_qualify", values())
    assert service.view()["publication"]["status"] == "HISTORICAL_HELD"
    assert service.retained_diagnostics()["attempt_receipt"]
    assert service.blocked_reason("physical_source_qualify")
    assert len(state["events"]) == 4


def test_real_collector_failure_shape_retains_full_report_without_stage_mutation(
    modeled, monkeypatch
):
    from rocell.application.physical_ownership_qualification import (
        PhysicalOwnershipQualificationError,
    )

    service, state = modeled
    before = len(state["events"])
    recorded = []

    def fail(workspace, **kwargs):
        report = modeled_report(
            source_sha256=SOURCE,
            directory=kwargs["assigned_directory"],
            workspace=workspace,
            covered=False,
        )
        recorded.append(report)
        raise PhysicalOwnershipQualificationError("MODELED_OWNERSHIP_FAILED", report)

    monkeypatch.setattr(module, "collect_physical_ownership_qualification", fail)
    with pytest.raises(PhysicalOwnershipQualificationError):
        run(service, "physical_source_qualify", values())
    retained = service.retained_diagnostics()
    assert retained["attempt_ownership_report"] == recorded[0].to_dict()
    assert len(state["events"]) == before
    assert retained["qualification_cycles"] == []
    assert service.view()["publication"]["status"] == "HISTORICAL_HELD"


@pytest.mark.parametrize("fault", ["head", "source", "stop"])
def test_collection_boundary_changes_never_start_original_cycle(
    modeled, monkeypatch, fault
):
    service, state = modeled
    before, event = len(state["events"]), Event()
    collect = module.collect_physical_ownership_qualification

    def changed(workspace, **kwargs):
        report = collect(workspace, **kwargs)
        if fault == "head":
            service.setup._source_workflow["session_head_sha256"] = "f" * 64
        elif fault == "source":
            state["source"] = "f" * 64
        else:
            event.set()
        return report

    monkeypatch.setattr(module, "collect_physical_ownership_qualification", changed)
    with pytest.raises(WizardError):
        run(service, "physical_source_qualify", values(), cancellation=event)
    assert len(state["events"]) == before
    assert service.retained_diagnostics()["attempt_ownership_report"]


@pytest.mark.parametrize("role", ["receipt", "assessment", "review"])
@pytest.mark.parametrize("value", [0, True, None])
def test_closed_subject_flags_require_literal_false(modeled, role, value):
    service, _ = modeled
    run(service, "physical_source_qualify", values())
    run(
        service,
        "physical_source_qualification_review",
        {"file_only": True, "reviewer_id": "reviewer"},
    )
    cycle = service.setup.original_source_workflow()["qualification_cycles"][-1]
    document = deepcopy(cycle[role]["document"])
    document["hardware_qualified"] = value
    with pytest.raises(codec.SourceQualificationError):
        module._CODECS[role](canonical(document))

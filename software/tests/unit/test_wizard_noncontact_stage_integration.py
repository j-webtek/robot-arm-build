"""Actual NC-01 math at a modeled transaction seam, not physical/M1 evidence.

The public smoke script separately checks complete original-store lineage. These
tests isolate retention, cancellation, assessment and serialization failures.
"""

from copy import deepcopy
import json
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import pytest

from rocell.application import rehearsal_noncontact_stage as nc
from rocell.application.commissioning_rehearsal_service import (
    CommissioningRehearsalService,
)
from rocell.application.physical_onboarding import STAGE_ORDER
from rocell.application.wizard_actions import WizardError
from test_rehearsal_noncontact_stage import make_noncontact_binding
from test_wizard_feedback_stage_integration import StageTransaction
from test_wizard_reference_stage_integration import retained_document

WORKSPACE = Path(__file__).resolve().parents[3]
STAGE = STAGE_ORDER[13]


@pytest.fixture(scope="module")
def evaluated():
    binding = make_noncontact_binding()
    return binding, nc.evaluate_rehearsal_noncontact_stage(WORKSPACE, binding)


@pytest.fixture
def service(tmp_path, evaluated):
    value = CommissioningRehearsalService(
        WORKSPACE, tmp_path / "unused-store", source_sha256="a" * 64
    )
    value._store = object()
    value._operator = "noncontact-operator"
    value._cached.update(stage=STAGE.value, stage_state="PENDING")
    return value


def transaction(service):
    tx = StageTransaction(service)
    tx.current.next_action.stage = STAGE
    return tx


def collect(service, evaluated, monkeypatch):
    tx = transaction(service)
    monkeypatch.setattr(service, "_transaction", lambda: tx)
    monkeypatch.setattr(service, "_noncontact_context", lambda tx: (evaluated[0], {}))
    service._collect({"operator_id": "noncontact-operator"}, Event())
    return tx


def retain(service, evaluated, monkeypatch):
    """Trust only the injected parent seam; the retained verifier is real."""
    tx = collect(service, evaluated, monkeypatch)
    saved = retained_document(STAGE, service._receipt)
    service._receipt_reference = saved.reference
    monkeypatch.setattr(
        service, "_noncontact_context", lambda tx: (evaluated[0], {STAGE.value: saved})
    )
    return tx


def test_complete_retention_detached_summary_and_historical_export_cache(
    service, evaluated, monkeypatch
):
    tx = collect(service, evaluated, monkeypatch)
    assert len(tx.stored) == 2
    assert tx.stored[0]["schema"] == "rocell.rehearsal_noncontact_stage_open.v1"
    assert tx.stored[1] == service._receipt
    assert service._receipt["evaluation"] == evaluated[1].to_dict()
    assert service._latest_noncontact["outcome"] == "BLOCKED"
    assert service._latest_noncontact["physical_authority"] is False
    assert "technical_reports" not in service._latest_noncontact
    detached = service.retained_noncontact_diagnostics()
    detached["evaluation"].clear()
    service._latest_noncontact["checks"].clear()
    assert service.retained_noncontact_diagnostics()["evaluation"]["checks"]
    assert not service.directory.exists()


def test_stop_after_dependency_read_retains_opening_without_rerun(
    service, evaluated, monkeypatch
):
    tx = transaction(service)
    stopped = Event()

    def context(tx):
        stopped.set()
        return evaluated[0], {}

    monkeypatch.setattr(service, "_transaction", lambda: tx)
    monkeypatch.setattr(service, "_noncontact_context", context)
    monkeypatch.setattr(
        nc, "evaluate_rehearsal_noncontact_stage", lambda *a: pytest.fail("replayed")
    )
    with pytest.raises(WizardError, match="Stop"):
        service._collect({"operator_id": "noncontact-operator"}, stopped)
    assert len(tx.stored) == 1
    assert service._receipt is None
    assert service.retained_noncontact_diagnostics() is None
    service._cached["stage_state"] = "WAITING_OPERATOR"
    assert service.blocked_reason("rehearsal_collect") is not None


def test_stop_after_actual_evaluation_does_not_publish_or_retain_result(
    service, evaluated, monkeypatch
):
    tx = transaction(service)
    stopped = Event()
    original = nc.evaluate_rehearsal_noncontact_stage

    def evaluate(*args):
        report = original(*args)
        stopped.set()
        return report

    monkeypatch.setattr(service, "_transaction", lambda: tx)
    monkeypatch.setattr(service, "_noncontact_context", lambda tx: (evaluated[0], {}))
    monkeypatch.setattr(nc, "evaluate_rehearsal_noncontact_stage", evaluate)
    with pytest.raises(WizardError, match="Stop"):
        service._collect({"operator_id": "noncontact-operator"}, stopped)
    assert len(tx.stored) == 1 and service._receipt is None
    assert service._latest_noncontact is None


def test_changed_receipt_cache_rejected_before_retained_verifier(service, monkeypatch):
    tx = transaction(service)
    service._receipt_reference = SimpleNamespace(evidence_id="original")
    service._receipt = {"changed": True}
    monkeypatch.setattr(
        service,
        "_noncontact_context",
        lambda tx: (None, {"original": retained_document(STAGE, {})}),
    )
    monkeypatch.setattr(
        nc,
        "verify_rehearsal_noncontact_evidence",
        lambda *a, **k: pytest.fail("changed cache"),
    )
    with pytest.raises(WizardError) as error:
        service._verify_noncontact(tx)
    assert error.value.code == "NONCONTACT_RECEIPT_CHANGED"


def test_pure_assessment_and_distinct_review_keep_actual_nominal_gaps_blocked(
    service, evaluated, monkeypatch
):
    tx = retain(service, evaluated, monkeypatch)
    from rocell.application import collision_readiness
    from rocell.calibration import rigid_correspondence

    def forbidden(*args, **kwargs):
        pytest.fail("assessment/review replayed an evaluator or solver")

    monkeypatch.setattr(nc, "evaluate_rehearsal_noncontact_stage", forbidden)
    monkeypatch.setattr(
        collision_readiness, "assess_current_collision_readiness", forbidden
    )
    monkeypatch.setattr(rigid_correspondence, "fit_rigid_correspondence", forbidden)
    service._assess(Event())
    assert service._assessment["outcome"] == "BLOCKED"
    assert len(service._assessment["reason_codes"]) == 3
    assert all(
        reason.startswith("NONCONTACT_CHECK_FAILED:")
        for reason in service._assessment["reason_codes"]
    )
    assert sum(row["passed"] for row in evaluated[1].checks) == 5
    with pytest.raises(WizardError):
        service._review(
            {"reviewer_id": "noncontact-operator", "accept_assessment": True}, Event()
        )
    service._review(
        {"reviewer_id": "independent-reviewer", "accept_assessment": True}, Event()
    )
    assert tx.current.next_action.stage == STAGE
    assert tx.current.next_action.stage_state.value == "BLOCKED"
    assert service._receipt is None and service._assessment is None
    assert (
        service.retained_noncontact_diagnostics()["evaluation"]
        == evaluated[1].to_dict()
    )


@pytest.mark.parametrize("mutation", ["pass", "dropped-reason", "added-reason"])
def test_review_rejects_forged_outcome_or_failure_set(
    service, evaluated, monkeypatch, mutation
):
    tx = retain(service, evaluated, monkeypatch)
    service._assess(Event())
    if mutation == "pass":
        service._assessment.update(outcome="PASS", reason_codes=[])
    elif mutation == "dropped-reason":
        service._assessment["reason_codes"].pop()
    else:
        service._assessment["reason_codes"].append("invented")
    prior = len(tx.stored)
    with pytest.raises(WizardError) as error:
        service._review(
            {"reviewer_id": "independent-reviewer", "accept_assessment": True}, Event()
        )
    assert error.value.code == "NONCONTACT_ASSESSMENT_CHANGED"
    assert len(tx.stored) == prior


def test_actual_perform_full_result_and_export_roundtrip(
    service, evaluated, monkeypatch, tmp_path
):
    from rocell.application.arrival_wizard_service import ArrivalWizardService
    from rocell.application.wizard_diagnostic_export import (
        WizardDiagnosticExporter,
        verify_export,
    )

    tx = transaction(service)
    monkeypatch.setattr(service, "_transaction", lambda: tx)
    monkeypatch.setattr(service, "_noncontact_context", lambda tx: (evaluated[0], {}))

    def refresh(**kwargs):
        service._cached.update(
            stage_state="WAITING_OPERATOR",
            noncontact_evaluation=deepcopy(service._latest_noncontact),
        )

    monkeypatch.setattr(service, "_refresh", refresh)
    values = service.bind("rehearsal_collect", {"operator_id": "noncontact-operator"})
    result = service.perform(
        "rehearsal_collect", values, cancellation=Event(), progress=lambda message: None
    )
    assert result["steps"][1]["report"] == evaluated[1].to_dict()
    assert len(json.dumps(service._receipt).encode("ascii")) < 128 * 1024
    app = ArrivalWizardService(
        WORKSPACE,
        log_directory=tmp_path / "logs",
        export_directory=tmp_path / "exports",
    )
    try:
        assert app._validated_result("rehearsal_collect", result) == result
        exporter = WizardDiagnosticExporter(tmp_path / "assigned-exports")
        exporter.prepare(create=True)
        exported = exporter.export(
            app.view(),
            [],
            attachments={"noncontact-result.json": json.dumps(result).encode("utf-8")},
        )
        destination = Path(exported["path"])
        assert verify_export(destination)["valid"] is True
        assert (
            json.loads((destination / "attachment-noncontact-result.json").read_bytes())
            == result
        )
        assert exported["physical_authority"] == "NONE"
    finally:
        app.shutdown()

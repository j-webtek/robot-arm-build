"""Stage-13 joining tests; injected review/audit boundaries are not physical evidence.

The serial artifact is produced by the real sealed incapable campaign. The
stage-7/8 trios here are isolated trusted-input fixtures, not an M1 durability
test. Full original-store progression is exercised by the public smoke script.
"""

from copy import deepcopy
import json
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import pytest

from rocell.application import commissioning_rehearsal_reopen as reopen
from rocell.application.commissioning_rehearsal_service import (
    CommissioningRehearsalService,
)
from rocell.application.physical_onboarding import STAGE_ORDER
from rocell.application.wizard_actions import WizardError
from test_rehearsal_reference_binding import make_binding
from test_wizard_feedback_stage_integration import actual_campaign, StageTransaction


WORKSPACE = Path(__file__).resolve().parents[3]
STAGE = STAGE_ORDER[12]


def retained_document(stage, document):
    return SimpleNamespace(
        reference=SimpleNamespace(stage=stage, evidence_id=stage.value),
        document=lambda: deepcopy(document),
    )


@pytest.fixture(scope="module")
def campaign():
    return actual_campaign()


@pytest.fixture
def dependencies(campaign, monkeypatch):
    original = reopen._verify_evaluated_receipt
    checked = []
    documents = {
        stage: (
            {"stage": stage.value, "fixture": "INJECTED_ALREADY_REVIEWED"},
            {"assessment_sha256": "a" * 64},
            {"decision": "ACCEPT_EXACT_ASSESSMENT"},
        )
        for stage in (STAGE_ORDER[5], STAGE_ORDER[6], STAGE_ORDER[7])
    }
    documents[STAGE_ORDER[11]] = (
        campaign.document,
        {"assessment_sha256": "b" * 64},
        {"decision": "ACCEPT_EXACT_ASSESSMENT"},
    )
    reports = {
        stage: SimpleNamespace(
            outcome="REHEARSAL_CHECKS_PASSED", evidence_sha256="c" * 64
        )
        for stage in (STAGE_ORDER[6], STAGE_ORDER[7])
    }

    def verify(snapshot, evidence, receipt, source, catalog, **kwargs):
        stage = receipt.reference.stage
        checked.append(stage)
        if stage in reports:
            return reports[stage]
        return original(snapshot, evidence, receipt, source, catalog, **kwargs)

    monkeypatch.setattr(reopen, "_verify_evaluated_receipt", verify)
    monkeypatch.setattr(
        reopen, "_feedback_binding", lambda *args: (campaign.binding, None)
    )
    monkeypatch.setattr(
        reopen,
        "_reviewed_stage_evidence",
        lambda snapshot, evidence, stage: tuple(
            retained_document(stage, document) for document in documents[stage]
        ),
    )
    return SimpleNamespace(
        campaign=campaign, documents=documents, reports=reports, checked=checked
    )


def derive(inputs, records=None):
    value = inputs.campaign
    return reopen._reference_binding(
        value.snapshot,
        {},
        "reference-operator",
        value.binding.workspace_source_sha256,
        value.binding.catalog_sha256,
        value.records if records is None else records,
        make_binding().source_context,
    )


def test_binding_verifies_actual_retained_feedback_and_separates_all_hash_domains(
    dependencies,
):
    binding, camera = derive(dependencies)
    campaign = dependencies.campaign
    report = campaign.evaluated.to_dict()
    assert dependencies.checked == [STAGE_ORDER[6], STAGE_ORDER[7], STAGE_ORDER[11]]
    assert binding.camera_capture_receipt_sha256 == reopen._hash(camera.document())
    assert binding.feedback_binding_sha256 == campaign.binding.binding_sha256
    assert (
        binding.campaign_context_binding_sha256
        == report["safe_summary"]["binding_sha256"]
    )
    assert binding.retained_campaign_sha256 == campaign.artifact.evidence_sha256
    assert (
        binding.feedback_inner_evidence_sha256
        == report["final_power_observation"]["feedback_evidence_sha256"]
    )
    assert (
        binding.final_power_observation_sha256
        == report["final_power_observation"]["observation_sha256"]
    )
    assert (
        binding.predecessors[2].evaluation_sha256 == campaign.evaluated.evidence_sha256
    )
    assert binding.predecessors[2].assessment_sha256 != "b" * 64  # full payload hash
    assert binding.to_dict()["physical_authority"] is False


@pytest.mark.parametrize("record", ["result", "reservation", "raw"])
def test_reference_cannot_skip_any_audited_serial_campaign_record(dependencies, record):
    records = deepcopy(dependencies.campaign.records)
    del records[record]
    with pytest.raises(reopen.RehearsalReopenError, match="exact audited"):
        derive(dependencies, records)


@pytest.mark.parametrize("stage", [STAGE_ORDER[6], STAGE_ORDER[7]])
def test_reference_refuses_a_blocked_optics_predecessor(dependencies, stage):
    dependencies.reports[stage].outcome = "BLOCKED"
    with pytest.raises(reopen.RehearsalReopenError) as error:
        derive(dependencies)
    assert error.value.code == "REFERENCE_PREDECESSOR_BLOCKED"


@pytest.mark.parametrize("missing", ["records", "workspace"])
def test_reopen_cannot_infer_source_workspace_or_omit_audited_records(missing):
    receipt = retained_document(
        STAGE, {"schema": "rocell.rehearsal_reference_receipt.v1"}
    )
    with pytest.raises(reopen.RehearsalReopenError) as error:
        reopen._verify_evaluated_receipt(
            None,
            {},
            receipt,
            "a" * 64,
            "b" * 64,
            records=None if missing == "records" else {},
            reference_workspace=None if missing == "workspace" else WORKSPACE,
        )
    assert error.value.code == "REFERENCE_CONTEXT_MISSING"


@pytest.fixture(scope="module")
def evaluated():
    from rocell.application import rehearsal_reference_stage as reference

    binding = make_binding(reference.read_reference_source_context(WORKSPACE))
    return binding, reference.evaluate_rehearsal_reference_stage(WORKSPACE, binding)


@pytest.fixture
def service(tmp_path, evaluated):
    value = CommissioningRehearsalService(
        WORKSPACE, tmp_path / "unused-store", source_sha256="a" * 64
    )
    value._store = object()
    value._operator = "test-operator"
    value._cached.update(stage=STAGE.value, stage_state="PENDING")
    return value


def transaction(service):
    tx = StageTransaction(service)
    tx.current.next_action.stage = STAGE
    return tx


def test_collect_publishes_json_equal_complete_evidence_and_small_detached_projection(
    service, evaluated, monkeypatch
):
    tx = transaction(service)
    binding, report = evaluated
    monkeypatch.setattr(service, "_transaction", lambda: tx)
    monkeypatch.setattr(service, "_reference_context", lambda tx: (binding, {}, {}))
    service._collect({"operator_id": "test-operator"}, Event())
    assert len(tx.stored) == 2
    assert tx.stored[0]["schema"] == "rocell.rehearsal_reference_stage_open.v1"
    assert tx.stored[1] == service._receipt
    assert tx.stored[1]["evaluation"] == report.to_dict()
    assert service._receipt["evaluation_sha256"] == report.evidence_sha256
    assert "technical_reports" not in service._latest_reference
    assert service._latest_reference["physical_authority"] is False
    service._latest_reference["reference_summary"].clear()
    assert service._receipt["evaluation"]["reference_summary"]
    assert not service.directory.exists()


def test_cancellation_after_dependency_read_retains_opening_but_no_result_or_automatic_rerun(
    service, evaluated, monkeypatch
):
    from rocell.application import rehearsal_reference_stage as reference

    tx = transaction(service)
    stopped = Event()

    def context(tx):
        stopped.set()
        return evaluated[0], {}, {}

    monkeypatch.setattr(service, "_transaction", lambda: tx)
    monkeypatch.setattr(service, "_reference_context", context)
    monkeypatch.setattr(
        reference,
        "evaluate_rehearsal_reference_stage",
        lambda *a, **k: pytest.fail("Cancelled stage replayed a fit"),
    )
    with pytest.raises(WizardError):
        service._collect({"operator_id": "test-operator"}, stopped)
    assert len(tx.stored) == 1 and service._receipt is None
    service._cached["stage_state"] = "WAITING_OPERATOR"
    assert service.blocked_reason("rehearsal_collect") is not None


def test_changed_cache_cannot_reach_reference_verifier(service, monkeypatch):
    from rocell.application import rehearsal_reference_stage as reference

    tx = transaction(service)
    service._receipt_reference = SimpleNamespace(evidence_id="retained-reference")
    service._receipt = {"changed": True}
    monkeypatch.setattr(
        service,
        "_reference_context",
        lambda tx: (None, {"retained-reference": retained_document(STAGE, {})}, {}),
    )
    monkeypatch.setattr(
        reference,
        "verify_rehearsal_reference_evidence",
        lambda *a, **k: pytest.fail("Changed cache reached verifier"),
    )
    with pytest.raises(WizardError) as error:
        service._verify_reference(tx)
    assert error.value.code == "REFERENCE_RECEIPT_CHANGED"


def test_review_cannot_replace_a_failed_reference_predicate(service, monkeypatch):
    tx = transaction(service)
    service._assessment = {"reason_codes": [], "outcome": "PASS"}
    service._assessment_reference = SimpleNamespace(evidence_id="assessment")
    monkeypatch.setattr(service, "_transaction", lambda: tx)
    monkeypatch.setattr(
        service,
        "_verify_reference",
        lambda tx: SimpleNamespace(
            checks=({"check_id": "nominal-fit", "passed": False},)
        ),
    )
    with pytest.raises(WizardError) as error:
        service._review(
            {"reviewer_id": "distinct-reviewer", "accept_assessment": True}, Event()
        )
    assert error.value.code == "REFERENCE_ASSESSMENT_CHANGED"
    assert not tx.commits and not tx.stored


def test_assessment_and_reopen_use_pure_retained_verifier_not_fit_or_evaluator(
    service, evaluated, monkeypatch
):
    from rocell.application import rehearsal_reference_stage as reference
    from rocell.calibration import rigid_correspondence as fitter

    binding, report = evaluated
    receipt = service._camera_document("rocell.rehearsal_reference_receipt.v1", STAGE)
    receipt.update(
        evaluation=report.to_dict(), evaluation_sha256=report.evidence_sha256
    )
    saved = retained_document(STAGE, receipt)
    service._receipt, service._receipt_reference = receipt, saved.reference
    monkeypatch.setattr(
        service, "_reference_context", lambda tx: (binding, {STAGE.value: saved}, {})
    )
    monkeypatch.setattr(reopen, "_reference_binding", lambda *a, **k: (binding, None))

    def forbidden(*a, **k):
        pytest.fail("Retained verification replayed numerical evaluation")

    monkeypatch.setattr(reference, "evaluate_rehearsal_reference_stage", forbidden)
    monkeypatch.setattr(fitter, "fit_rigid_correspondence", forbidden)
    assert service._verify_reference(transaction(service)).to_dict() == report.to_dict()
    assert (
        reopen._verify_evaluated_receipt(
            None,
            {},
            saved,
            binding.workspace_source_sha256,
            binding.catalog_sha256,
            records={},
            reference_workspace=WORKSPACE,
        ).to_dict()
        == report.to_dict()
    )


def test_actual_perform_envelope_passes_arrival_validation_and_lossless_export(
    service, evaluated, monkeypatch, tmp_path
):
    """Real numerical/public serializers; transaction seam is not a disk audit."""
    from rocell.application.arrival_wizard_service import ArrivalWizardService
    from rocell.application.wizard_diagnostic_export import (
        WizardDiagnosticExporter,
        verify_export,
    )

    binding, report = evaluated
    tx = transaction(service)
    monkeypatch.setattr(service, "_transaction", lambda: tx)
    monkeypatch.setattr(service, "_reference_context", lambda tx: (binding, {}, {}))

    def refresh(**kwargs):
        service._cached.update(
            stage_state="WAITING_OPERATOR",
            reference_evaluation=deepcopy(service._latest_reference),
        )

    monkeypatch.setattr(service, "_refresh", refresh)
    values = service.bind("rehearsal_collect", {"operator_id": "test-operator"})
    result = service.perform(
        "rehearsal_collect", values, cancellation=Event(), progress=lambda message: None
    )
    assert len(result["steps"]) == 2
    assert result["steps"][1]["report"] == report.to_dict()
    assert len(json.dumps(service._receipt).encode("ascii")) < reopen.MAX_EVIDENCE_BYTES
    app = ArrivalWizardService(
        WORKSPACE,
        log_directory=tmp_path / "logs",
        export_directory=tmp_path / "exports",
    )
    try:
        validated = app._validated_result("rehearsal_collect", result)
        assert (
            validated == result
        )  # No lost nodes, redacted numeric inputs or type drift.
        exporter = WizardDiagnosticExporter(tmp_path / "assigned-exports")
        exporter.prepare(create=True)
        exported = exporter.export(
            app.view(),
            [],
            attachments={
                "reference-result.json": json.dumps(validated).encode("utf-8")
            },
        )
        destination = Path(exported["path"])
        assert verify_export(destination)["valid"] is True
        retained = json.loads(
            (destination / "attachment-reference-result.json").read_bytes()
        )
        assert retained == result
        assert (
            retained["steps"][1]["report"]["technical_reports"]
            == report.to_dict()["technical_reports"]
        )
        assert exported["physical_authority"] == "NONE"
    finally:
        app.shutdown()

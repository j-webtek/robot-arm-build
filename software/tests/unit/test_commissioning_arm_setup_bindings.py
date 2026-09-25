"""Pure adapter contracts; injected snapshots are not durable M1 qualification.

Real original-store coverage lives in test_commissioning_rehearsal_optics. These
tests isolate the hash/dispatch boundary without replaying filesystem campaigns.
"""

from dataclasses import replace
import hashlib
from pathlib import Path
import threading
from types import SimpleNamespace

import pytest

from rocell.application import commissioning_rehearsal_reopen as reopen
from rocell.application import rehearsal_arm_identity_stage as identity
from rocell.application.commissioning_rehearsal_service import (
    CommissioningRehearsalService,
    _bytes,
    _hash,
)
from rocell.application.physical_onboarding import EvidenceReference, STAGE_ORDER
from rocell.application.physical_onboarding_v2 import V2StageState
from rocell.application.wizard_actions import WizardError


WORKSPACE = Path(__file__).resolve().parents[3]
SOURCE, CATALOG = "a" * 64, "b" * 64


def retained(stage, value, index=1):
    payload = _bytes(value)
    digest = hashlib.sha256(payload).hexdigest()
    reference = EvidenceReference(
        "evidence-" + digest, stage, digest, digest, digest, len(payload)
    )
    return reopen.VerifiedRehearsalEvidence(reference, payload, index)


def reviewed(stage, evidence, events, **extra):
    receipt = retained(
        stage,
        {
            "schema": "fixture",
            "stage": stage.value,
            "operator_id": "previous-operator",
            **extra,
        },
    )
    assessment = retained(
        stage,
        {
            "schema": "rocell.rehearsal_assessment.v1",
            "stage": stage.value,
            "outcome": "PASS",
            "receipt_evidence_id": receipt.reference.evidence_id,
            "receipt_sha256": _hash(receipt.document()),
            "assessment_sha256": "c" * 64,
        },
        2,
    )
    review = retained(
        stage,
        {
            "schema": "rocell.rehearsal_review.v1",
            "stage": stage.value,
            "assessment_sha256": "c" * 64,
            "operator_id": "previous-operator",
            "reviewer_id": "previous-reviewer",
            "decision": "ACCEPT_EXACT_ASSESSMENT",
        },
        3,
    )
    trio = receipt, assessment, review
    for item in trio:
        evidence[item.reference.evidence_id] = item
    events.append(
        SimpleNamespace(
            stage=stage,
            state=V2StageState.PASS,
            detail_code="REHEARSAL_ASSESSMENT_REVIEWED",
            evidence=tuple(item.reference for item in trio),
        )
    )
    return trio


@pytest.fixture
def chain():
    evidence, events = {}, []
    trios = {
        stage: reviewed(stage, evidence, events, fixture_stage=stage.value)
        for stage in STAGE_ORDER[5:10]
    }
    snapshot = SimpleNamespace(
        header=SimpleNamespace(cell_id="cell-fixture", session_id="session-fixture"),
        committed_events=events,
    )
    return snapshot, evidence, trios


@pytest.mark.parametrize("index", [7, 8, 9])
def test_exact_reviewed_trio_returns_full_payload_hashes(chain, index):
    snapshot, evidence, trios = chain
    trio = reopen._reviewed_stage_evidence(snapshot, evidence, STAGE_ORDER[index])
    assert trio == trios[STAGE_ORDER[index]]
    # Binding the embedded self-hash alone would omit other assessment fields.
    assert _hash(trio[1].document()) != trio[1].document()["assessment_sha256"]


@pytest.mark.parametrize(
    "mutation", ["missing", "duplicate", "not-pass", "wrong-event", "short"]
)
def test_no_missing_ambiguous_or_unreviewed_predecessor(chain, mutation):
    snapshot, evidence, _ = chain
    event = next(
        item for item in snapshot.committed_events if item.stage is STAGE_ORDER[7]
    )
    if mutation == "missing":
        snapshot.committed_events.remove(event)
    elif mutation == "duplicate":
        snapshot.committed_events.append(event)
    elif mutation == "not-pass":
        event.state = V2StageState.BLOCKED
    elif mutation == "wrong-event":
        event.detail_code = "REHEARSAL_ASSESSMENT_READY"
    else:
        event.evidence = event.evidence[:2]
    with pytest.raises(reopen.RehearsalReopenError):
        reopen._reviewed_stage_evidence(snapshot, evidence, STAGE_ORDER[7])


@pytest.mark.parametrize(
    "item_index,field,value",
    [
        (1, "schema", "wrong"),
        (1, "outcome", "BLOCKED"),
        (1, "receipt_evidence_id", "different-evidence"),
        (1, "receipt_sha256", "0" * 64),
        (2, "schema", "wrong"),
        (2, "assessment_sha256", "0" * 64),
        (2, "operator_id", "other-operator"),
        (2, "reviewer_id", "previous-operator"),
        (2, "decision", "ACCEPT_ANY"),
    ],
)
def test_changed_predecessor_documents_cannot_supply_bindings(
    chain, item_index, field, value
):
    snapshot, evidence, trios = chain
    item = trios[STAGE_ORDER[7]][item_index]
    document = item.document()
    document[field] = value
    # Simulate already-parsed input to the helper; durable hash verification is
    # independently tested in M1. The helper must still reject semantic drift.
    evidence[item.reference.evidence_id] = replace(item, payload=_bytes(document))
    with pytest.raises(reopen.RehearsalReopenError):
        reopen._reviewed_stage_evidence(snapshot, evidence, STAGE_ORDER[7])


def test_arm_binding_uses_exact_registration_report_and_immediate_trio(
    chain, monkeypatch
):
    snapshot, evidence, trios = chain
    calls = []

    def verified(*args):
        calls.append(args[2])
        return SimpleNamespace(
            outcome="REHEARSAL_CHECKS_PASSED", evidence_sha256="d" * 64
        )

    monkeypatch.setattr(reopen, "_verify_optics_receipt", verified)
    binding, camera = reopen._arm_identity_binding(
        snapshot, evidence, "new-operator", SOURCE, CATALOG
    )
    prior = trios[STAGE_ORDER[7]]
    assert calls == [prior[0]]
    assert camera is trios[STAGE_ORDER[5]][0]
    assert binding.operator_id == "new-operator"
    assert binding.predecessor_receipt_sha256 == _hash(prior[0].document())
    assert binding.predecessor_assessment_sha256 == _hash(prior[1].document())
    assert binding.predecessor_review_sha256 == _hash(prior[2].document())
    assert binding.static_registration_evidence_sha256 == "d" * 64


def test_blocked_registration_never_supplies_arm_binding(chain, monkeypatch):
    snapshot, evidence, _ = chain
    monkeypatch.setattr(
        reopen, "_verify_optics_receipt", lambda *a: SimpleNamespace(outcome="BLOCKED")
    )
    with pytest.raises(reopen.RehearsalReopenError, match="reviewed registration"):
        reopen._arm_identity_binding(snapshot, evidence, "operator", SOURCE, CATALOG)


@pytest.mark.parametrize("index", [9, 10])
def test_power_binding_uses_arm_and_exact_immediate_predecessor(
    chain, monkeypatch, index
):
    snapshot, evidence, trios = chain
    calls = []

    def arm(*args):
        calls.append(("arm", args[2].reference.stage))
        return SimpleNamespace(
            outcome="REHEARSAL_CHECKS_PASSED", evidence_sha256="e" * 64
        )

    def power(*args):
        calls.append(("power", args[2].reference.stage))
        return SimpleNamespace(outcome="REHEARSAL_CHECKS_PASSED")

    monkeypatch.setattr(reopen, "_verify_arm_identity_receipt", arm)
    monkeypatch.setattr(reopen, "_verify_power_receipt", power)
    binding, camera = reopen._power_binding(
        snapshot, evidence, STAGE_ORDER[index], "operator", SOURCE, CATALOG
    )
    prior = trios[STAGE_ORDER[index - 1]]
    assert binding.predecessor_receipt_sha256 == _hash(prior[0].document())
    assert binding.predecessor_assessment_sha256 == _hash(prior[1].document())
    assert binding.predecessor_review_sha256 == _hash(prior[2].document())
    assert binding.arm_identity_evidence_sha256 == "e" * 64
    assert camera is trios[STAGE_ORDER[5]][0]
    assert calls == [("arm", STAGE_ORDER[8])] + (
        [("power", STAGE_ORDER[9])] if index == 10 else []
    )


@pytest.mark.parametrize("index", [8, 9, 10])
def test_receipt_verification_supplies_trusted_hashes_and_never_evaluates(
    tmp_path, monkeypatch, index
):
    from rocell.application import rehearsal_power_stages as power

    stage = STAGE_ORDER[index]
    common = dict(
        workspace_source_sha256=SOURCE,
        catalog_sha256=CATALOG,
        cell_id="cell-fixture",
        session_id="session-fixture",
        operator_id="operator",
        predecessor_receipt_sha256="d" * 64,
        predecessor_assessment_sha256="e" * 64,
        predecessor_review_sha256="f" * 64,
        stage=stage.value,
    )
    if index == 8:
        module, name = identity, "arm_identity"
        binding = identity.RehearsalArmIdentityBinding(
            **common, static_registration_evidence_sha256="1" * 64
        )
        evaluated = identity.evaluate_rehearsal_arm_identity_stage(WORKSPACE, binding)
        monkeypatch.setattr(reopen, "_arm_identity_binding", lambda *a: (binding, None))
        monkeypatch.setattr(
            identity,
            "evaluate_rehearsal_arm_identity_stage",
            lambda *a, **k: pytest.fail("verifier replayed evaluator"),
        )
    else:
        module, name = power, "power"
        binding = power.RehearsalPowerBinding(
            **common, arm_identity_evidence_sha256="1" * 64
        )
        evaluated = power.evaluate_rehearsal_power_stage(WORKSPACE, binding)
        monkeypatch.setattr(reopen, "_power_binding", lambda *a: (binding, None))
        monkeypatch.setattr(
            power,
            "evaluate_rehearsal_power_stage",
            lambda *a, **k: pytest.fail("verifier replayed evaluator"),
        )
    verifier_name = f"verify_rehearsal_{name}_evidence"
    original = getattr(module, verifier_name)
    observed = []

    def verifying(payload, **kwargs):
        observed.append(kwargs)
        return original(payload, **kwargs)

    monkeypatch.setattr(module, verifier_name, verifying)
    document = {
        "schema": reopen._EVALUATED_SCHEMAS[stage],
        "stage": stage.value,
        "operator_id": "operator",
        "evaluation": evaluated.to_dict(),
        "evaluation_sha256": evaluated.evidence_sha256,
    }
    receipt = retained(stage, document)
    assert len(receipt.payload) <= reopen.MAX_EVIDENCE_BYTES
    from rocell.application.wizard_diagnostic_export import sanitize_diagnostic_record

    # The ordinary result/export path must retain the complete technical report,
    # not just fit M1's independent byte limit or a compact UI projection.
    clean = sanitize_diagnostic_record(
        {"steps": [{"report": evaluated.to_dict()}]}, maximum_bytes=1024 * 1024
    )
    assert clean["steps"][0]["report"] == evaluated.to_dict()
    result = reopen._verify_evaluated_receipt(None, {}, receipt, SOURCE, CATALOG)
    assert result.evidence_sha256 == evaluated.evidence_sha256
    assert observed == [
        {
            "expected_binding": binding,
            "expected_evidence_sha256": evaluated.evidence_sha256,
            "expected_evaluator_source_sha256": hashlib.sha256(
                Path(module.__file__).read_bytes()
            ).hexdigest(),
        }
    ]
    document["evaluation_sha256"] = "0" * 64
    with pytest.raises(ValueError):
        reopen._verify_evaluated_receipt(
            None, {}, retained(stage, document), SOURCE, CATALOG
        )
    assert list(tmp_path.iterdir()) == []  # No store is constructed.


@pytest.mark.parametrize("index", [8, 9, 10])
def test_wrong_stage_receipt_schema_never_dispatches(monkeypatch, index):
    for name in (
        "_verify_optics_receipt",
        "_verify_arm_identity_receipt",
        "_verify_power_receipt",
    ):
        monkeypatch.setattr(
            reopen, name, lambda *a: pytest.fail("wrong-schema dispatch")
        )
    receipt = retained(
        STAGE_ORDER[index], {"schema": "rocell.rehearsal_stage_receipt.v1"}
    )
    with pytest.raises(reopen.RehearsalReopenError, match="substitute"):
        reopen._verify_evaluated_receipt(None, {}, receipt, SOURCE, CATALOG)


def test_projection_is_a_detached_summary_not_raw_authority(tmp_path):
    service = CommissioningRehearsalService(
        WORKSPACE, tmp_path / "uncreated", source_sha256=SOURCE
    )
    receipt = {
        "stage": "arm_identity",
        "evaluation_sha256": "c" * 64,
        "evaluation": {
            "outcome": "BLOCKED",
            "checks": [{"passed": False}],
            "provenance": {"input": "synthetic"},
            "selected_inputs_sha256": "d" * 64,
            "reports": {"raw": "not a display field"},
        },
    }
    projection = service._arm_setup_projection(receipt)
    assert "reports" not in projection
    assert projection["physical_authority"] is False
    projection["checks"][0]["passed"] = True
    assert receipt["evaluation"]["checks"][0]["passed"] is False
    assert not service.directory.exists()


@pytest.mark.parametrize("index", [8, 9, 10])
@pytest.mark.parametrize("boundary", ["context", "evaluation"])
def test_stop_before_or_after_evaluation_never_publishes_result(
    tmp_path, monkeypatch, index, boundary
):
    from rocell.application import rehearsal_power_stages as power

    service = CommissioningRehearsalService(
        WORKSPACE, tmp_path / "uncreated", source_sha256=SOURCE
    )
    service._operator = "operator"
    cancellation = threading.Event()
    retained_documents, calls = [], []
    tx = SimpleNamespace(snapshot=lambda: None)

    def context(*args):
        if boundary == "context":
            cancellation.set()
        return object(), {}

    def evaluate(*args, **kwargs):
        calls.append("evaluate")
        cancellation.set()
        return SimpleNamespace(
            to_dict=lambda: pytest.fail("canceled result serialized")
        )

    monkeypatch.setattr(service, "_arm_setup_context", context)
    monkeypatch.setattr(
        service,
        "_store_json",
        lambda tx, stage, document, label: retained_documents.append(document),
    )
    monkeypatch.setattr(identity, "evaluate_rehearsal_arm_identity_stage", evaluate)
    monkeypatch.setattr(power, "evaluate_rehearsal_power_stage", evaluate)
    with pytest.raises(WizardError, match="Stop arrived before"):
        service._collect_arm_setup(tx, STAGE_ORDER[index], cancellation)
    assert calls == ([] if boundary == "context" else ["evaluate"])
    assert len(retained_documents) == 1
    assert retained_documents[0]["schema"].endswith("stage_open.v1")
    assert service._receipt is None
    assert service._latest_arm_identity is service._latest_power is None
    assert not service.directory.exists()


@pytest.mark.parametrize("index", [8, 9, 10])
@pytest.mark.parametrize("state", ["WAITING_OPERATOR", "REVIEW_PENDING", "BLOCKED"])
def test_started_evaluated_stage_never_replays_collection(tmp_path, index, state):
    service = CommissioningRehearsalService(
        WORKSPACE, tmp_path / "uncreated", source_sha256=SOURCE
    )
    service._store = object()
    service._cached.update(
        status="ACTIVE_REHEARSAL", stage=STAGE_ORDER[index].value, stage_state=state
    )
    assert "never replay" in service.blocked_reason("rehearsal_collect")
    assert not service.directory.exists()


@pytest.mark.parametrize("index", [8, 9, 10])
def test_reconstruct_missing_arm_setup_result_holds_without_replay(
    tmp_path, monkeypatch, index
):
    from rocell.application import rehearsal_power_stages as power

    stage = STAGE_ORDER[index]
    # Isolate the pure reconstruction predicate after M1 validation. This is
    # not a fabricated complete/qualified store and cannot advance any stage.
    snapshot = SimpleNamespace(
        header=SimpleNamespace(session_id="fixture-session", header_sha256="a" * 64),
        committed_events=[
            SimpleNamespace(
                stage=stage,
                state=V2StageState.WAITING_OPERATOR,
                evidence=(),
                occurred_at_ns=1,
                detail_code="REHEARSAL_STAGE_OPENED",
            )
        ],
        next_action=SimpleNamespace(
            stage=stage, stage_state=V2StageState.WAITING_OPERATOR
        ),
    )
    opening = retained(
        stage,
        {"schema": reopen._EVALUATED_OPEN_SCHEMAS[stage], "operator_id": "operator"},
        2,
    )
    monkeypatch.setattr(
        reopen, "_read_evidence", lambda *a: {opening.reference.evidence_id: opening}
    )
    monkeypatch.setattr(
        identity,
        "evaluate_rehearsal_arm_identity_stage",
        lambda *a, **k: pytest.fail("replayed identity"),
    )
    monkeypatch.setattr(
        power,
        "evaluate_rehearsal_power_stage",
        lambda *a, **k: pytest.fail("replayed power"),
    )
    with pytest.raises(reopen.RehearsalReopenError) as caught:
        reopen._reconstruct(tmp_path, snapshot, None, SOURCE, CATALOG, {})
    assert caught.value.code == "EVALUATION_RECEIPT_MISSING"
    assert list(tmp_path.iterdir()) == []

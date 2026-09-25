"""Fast stage-13 retained-lifecycle tests, NOT full M1 integration evidence.

These isolated fixtures inject the already-audited evidence/verification seam
and a pure reference-verifier result. They exercise the real _reconstruct and
its real stage/schema dispatch, head/reference associations and no-result holds.
They deliberately omit the expensive first twelve stages and native NTFS audit;
the public all-stage integration suite remains responsible for those boundaries.
No evaluator, fitter, serial worker, device or registry activation is allowed.
"""

from __future__ import annotations

from dataclasses import replace
import hashlib
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest

import rocell.application as application
from rocell.application import commissioning_rehearsal_reopen as reopen
from rocell.application.physical_onboarding import (
    EvidenceReference,
    PhysicalOnboardingStage,
    STAGE_ORDER,
)
from rocell.application.physical_onboarding_v2 import (
    PORTABLE_UNQUALIFIED,
    V2CommittedHead,
    V2JournalEvent,
    V2NextAction,
    V2SessionHeader,
    V2SessionSnapshot,
    V2StageSnapshot,
    V2StageState,
)
from rocell.calibration import rigid_correspondence
from rocell.providers.windows import arm_feedback_worker


SOURCE = "a" * 64
CATALOG = "b" * 64
REFERENCE = PhysicalOnboardingStage.REFERENCE_FRAME_CALIBRATION


def _fixture(state="receipt-ready", *, failed_check=False):
    header = V2SessionHeader.build(
        session_id="rehearsal-" + "1" * 32,
        cell_id="wizard-rehearsal-" + "2" * 16,
        created_at_ns=1,
        source_binding_sha256=SOURCE,
        publication_durability=PORTABLE_UNQUALIFIED,
        durability_qualification_sha256="0" * 64,
        mode="REHEARSAL",
    )
    documents = {}
    events = []
    checks = ({"check_id": "fixture-algebra", "passed": not failed_check},)

    def retain(name, document, captured_at):
        payload = reopen._json(document)
        reference = EvidenceReference(
            name,
            REFERENCE,
            "c" * 64,
            "d" * 64,
            hashlib.sha256(payload).hexdigest(),
            len(payload),
        )
        verified = reopen.VerifiedRehearsalEvidence(reference, payload, captured_at)
        documents[name] = verified
        return verified

    def event(state, time, refs, code):
        result = V2JournalEvent.build(
            header=header,
            sequence=len(events),
            stage=REFERENCE,
            previous_state=V2StageState.PENDING if not events else events[-1].state,
            state=state,
            occurred_at_ns=time,
            previous_event_sha256="0" * 64 if not events else events[-1].event_sha256,
            evidence=tuple(item.reference for item in refs),
            detail_code=code,
        )
        events.append(result)

    common = {
        "composition": reopen.INCAPABLE_COMPOSITION,
        "stage": REFERENCE.value,
        "session_id": header.session_id,
        "cell_id": header.cell_id,
        "workspace_source_sha256": SOURCE,
        "catalog_sha256": CATALOG,
        "operator_id": "operator-fixture",
        "physical_observation": False,
    }
    event(V2StageState.WAITING_OPERATOR, 10, (), "REHEARSAL_STAGE_OPENED")
    retain(
        "stage-open",
        {**common, "schema": reopen._EVALUATED_OPEN_SCHEMAS[REFERENCE]},
        11,
    )
    receipt = assessment = None
    if state != "missing-result":
        receipt = retain(
            "receipt",
            {
                **common,
                "schema": reopen._EVALUATED_SCHEMAS[REFERENCE],
                "evaluation": {"closed_lifecycle_fixture": True},
                "evaluation_sha256": "e" * 64,
            },
            12,
        )
    if state in {"review-pending", "reviewed"}:
        reasons = ["REFERENCE_CHECK_FAILED:fixture-algebra"] if failed_check else []
        assessment_document = {
            "schema": "rocell.rehearsal_assessment.v1",
            "composition": reopen.INCAPABLE_COMPOSITION,
            "session_id": header.session_id,
            "stage": REFERENCE.value,
            "source_binding_sha256": SOURCE,
            "pre_assessment_head_sha256": V2CommittedHead.build(
                header, events
            ).head_sha256,
            "receipt_sha256": reopen._hash(receipt.document()),
            "receipt_evidence_id": receipt.reference.evidence_id,
            "outcome": "BLOCKED" if failed_check else "PASS",
            "reason_codes": reasons,
            "meaning": "Isolated lifecycle fixture, not audited full-stage evidence.",
        }
        assessment_document["assessment_sha256"] = reopen._hash(assessment_document)
        assessment = retain("assessment", assessment_document, 15)
        event(
            V2StageState.REVIEW_PENDING,
            20,
            (receipt, assessment),
            "REHEARSAL_ASSESSMENT_READY",
        )
    if state == "reviewed":
        review = retain(
            "review",
            {
                "schema": "rocell.rehearsal_review.v1",
                "composition": reopen.INCAPABLE_COMPOSITION,
                "session_id": header.session_id,
                "stage": REFERENCE.value,
                "assessment_sha256": assessment.document()["assessment_sha256"],
                "reviewed_head_sha256": V2CommittedHead.build(
                    header, events
                ).head_sha256,
                "reviewer_id": "independent-fixture",
                "operator_id": "operator-fixture",
                "decision": "ACCEPT_EXACT_ASSESSMENT",
                "physical_release_effect": "NONE",
            },
            25,
        )
        event(
            V2StageState.BLOCKED if failed_check else V2StageState.PASS,
            30,
            (receipt, assessment, review),
            "REHEARSAL_ASSESSMENT_REVIEWED",
        )
    current = (
        PhysicalOnboardingStage.NONCONTACT_ACCEPTANCE
        if state == "reviewed" and not failed_check
        else REFERENCE
    )
    current_state = (
        V2StageState.PENDING if current is not REFERENCE else events[-1].state
    )
    stages = tuple(
        V2StageSnapshot(
            stage,
            (
                V2StageState.PASS
                if STAGE_ORDER.index(stage) < 12
                else events[-1].state if stage is REFERENCE else V2StageState.PENDING
            ),
            None,
            (),
        )
        for stage in STAGE_ORDER
    )
    snapshot = V2SessionSnapshot(
        header,
        stages,
        tuple(events),
        (),
        tuple(item.reference for item in documents.values()),
        V2CommittedHead.build(header, events),
        V2NextAction("ISOLATED_LIFECYCLE_FIXTURE", current, current_state, True),
    )
    verification = SimpleNamespace(
        evidence_inventory_sha256="f" * 64, challenge_sha256="9" * 64
    )
    return SimpleNamespace(
        snapshot=snapshot,
        evidence=documents,
        verification=verification,
        checks=checks,
        calls=[],
        records={"fixture": {"kind": "AUDIT_SEAM_ONLY"}},
    )


def _install(monkeypatch, fixture, workspace):
    def no_replay(*args, **kwargs):
        raise AssertionError(
            "retained lifecycle reconstruction must not replay workers/fitters"
        )

    monkeypatch.setattr(rigid_correspondence, "fit_rigid_correspondence", no_replay)
    monkeypatch.setattr(arm_feedback_worker.ArmFeedbackWorker, "run", no_replay)
    forbidden_reference_module = ModuleType(
        "rocell.application.rehearsal_reference_stage"
    )
    for name in (
        "evaluate_rehearsal_reference_stage",
        "read_reference_source_context",
        "verify_rehearsal_reference_evidence",
    ):
        setattr(forbidden_reference_module, name, no_replay)
    monkeypatch.setitem(
        sys.modules,
        "rocell.application.rehearsal_reference_stage",
        forbidden_reference_module,
    )
    monkeypatch.setattr(
        application,
        "rehearsal_reference_stage",
        forbidden_reference_module,
        raising=False,
    )
    # The disk/audit seams are deliberately injected; no false claim that this
    # minimal stage-13-only journal could replace a complete original M1 store.
    monkeypatch.setattr(reopen, "_read_evidence", lambda *args: fixture.evidence)
    monkeypatch.setattr(reopen, "_entries", lambda *args: ())

    def pure_reference(
        snapshot,
        evidence,
        receipt,
        source,
        catalog,
        records,
        assigned_workspace,
        *,
        directory=None,
    ):
        assert snapshot is fixture.snapshot
        assert evidence is fixture.evidence
        assert records is fixture.records
        assert assigned_workspace == workspace
        assert source == SOURCE and catalog == CATALOG
        assert receipt.document()["schema"] == reopen._EVALUATED_SCHEMAS[REFERENCE]
        fixture.calls.append(receipt.reference.evidence_id)
        return SimpleNamespace(checks=fixture.checks)

    # Real _verify_evaluated_receipt still enforces the missing-workspace/record
    # gates before dispatching this explicitly pure verification test double.
    monkeypatch.setattr(reopen, "_verify_reference_receipt", pure_reference)


def _reconstruct(tmp_path, fixture, *, workspace):
    return reopen._reconstruct(
        tmp_path,
        fixture.snapshot,
        fixture.verification,
        SOURCE,
        CATALOG,
        fixture.records,
        reference_workspace=workspace,
    )


@pytest.mark.parametrize(
    "state,disposition",
    [
        ("receipt-ready", "RECEIPT_READY"),
        ("review-pending", "REVIEW_PENDING"),
        ("reviewed", "DUE_STAGE"),
    ],
)
def test_reference_lifecycle_whitelists_restore_exact_retained_state(
    tmp_path, monkeypatch, state, disposition
):
    fixture = _fixture(state)
    workspace = tmp_path / "server-assigned-source"
    _install(monkeypatch, fixture, workspace)
    restored = _reconstruct(tmp_path, fixture, workspace=workspace)
    assert restored.disposition == disposition
    assert restored.physical_authority is False
    assert restored.automatic_replay_allowed is False
    assert fixture.calls
    if state == "reviewed":
        assert restored.stage is PhysicalOnboardingStage.NONCONTACT_ACCEPTANCE
        assert restored.receipt is None and restored.assessment is None
        assert restored.operator_id is None
    else:
        assert restored.receipt is fixture.evidence["receipt"]
        assert restored.operator_id == "operator-fixture"
        assert (restored.assessment is not None) is (state == "review-pending")


def test_reference_open_without_result_is_held_not_automatically_rerun(
    tmp_path, monkeypatch
):
    fixture = _fixture("missing-result")
    workspace = tmp_path / "server-assigned-source"
    _install(monkeypatch, fixture, workspace)
    with pytest.raises(reopen.RehearsalReopenError) as error:
        _reconstruct(tmp_path, fixture, workspace=workspace)
    assert error.value.code == "EVALUATION_RECEIPT_MISSING"
    assert fixture.calls == []


@pytest.mark.parametrize("state", ["receipt-ready", "review-pending", "reviewed"])
def test_missing_reference_workspace_blocks_before_pure_verification(
    tmp_path, monkeypatch, state
):
    fixture = _fixture(state)
    _install(monkeypatch, fixture, tmp_path / "assigned")
    with pytest.raises(reopen.RehearsalReopenError) as error:
        _reconstruct(tmp_path, fixture, workspace=None)
    assert error.value.code == "REFERENCE_CONTEXT_MISSING"
    assert fixture.calls == []


def test_missing_audited_records_blocks_real_reference_dispatch(tmp_path, monkeypatch):
    fixture = _fixture()
    workspace = tmp_path / "assigned"
    _install(monkeypatch, fixture, workspace)
    with pytest.raises(reopen.RehearsalReopenError) as error:
        reopen._verify_evaluated_receipt(
            fixture.snapshot,
            fixture.evidence,
            fixture.evidence["receipt"],
            SOURCE,
            CATALOG,
            records=None,
            reference_workspace=workspace,
        )
    assert error.value.code == "REFERENCE_CONTEXT_MISSING"
    assert fixture.calls == []


@pytest.mark.parametrize("state", ["review-pending", "reviewed"])
def test_failed_nominal_reference_check_remains_blocked_when_restored(
    tmp_path, monkeypatch, state
):
    fixture = _fixture(state, failed_check=True)
    workspace = tmp_path / "assigned"
    _install(monkeypatch, fixture, workspace)
    restored = _reconstruct(tmp_path, fixture, workspace=workspace)
    assert restored.stage is REFERENCE
    assert restored.stage_state is (
        V2StageState.REVIEW_PENDING
        if state == "review-pending"
        else V2StageState.BLOCKED
    )
    assert restored.physical_authority is False


def _alter_evidence(fixture, name, document=None, **changes):
    current = fixture.evidence[name]
    payload = current.payload if document is None else reopen._json(document)
    fixture.evidence[name] = replace(current, payload=payload, **changes)


@pytest.mark.parametrize(
    "fault", ["missing-open", "wrong-operator", "late-open", "duplicate-open"]
)
def test_reference_receipt_requires_one_earlier_matching_operator_record(
    tmp_path, monkeypatch, fault
):
    fixture = _fixture()
    if fault == "missing-open":
        del fixture.evidence["stage-open"]
    elif fault == "wrong-operator":
        document = fixture.evidence["stage-open"].document()
        document["operator_id"] = "other-operator"
        _alter_evidence(fixture, "stage-open", document)
    elif fault == "late-open":
        _alter_evidence(fixture, "stage-open", captured_at_ns=13)
    else:
        copied = fixture.evidence["stage-open"]
        fixture.evidence["second-open"] = replace(
            copied, reference=replace(copied.reference, evidence_id="second-open")
        )
    workspace = tmp_path / "assigned"
    _install(monkeypatch, fixture, workspace)
    with pytest.raises(reopen.RehearsalReopenError) as error:
        _reconstruct(tmp_path, fixture, workspace=workspace)
    assert error.value.code == (
        "AMBIGUOUS_OPERATOR"
        if fault == "duplicate-open"
        else "EVALUATION_OPERATOR_MISMATCH"
    )
    assert fixture.calls == []


def test_reconstruction_does_not_accept_assessment_green_when_pure_check_fails(
    tmp_path, monkeypatch
):
    fixture = _fixture("review-pending")
    fixture.checks = ({"check_id": "fixture-algebra", "passed": False},)
    workspace = tmp_path / "assigned"
    _install(monkeypatch, fixture, workspace)
    with pytest.raises(reopen.RehearsalReopenError) as error:
        _reconstruct(tmp_path, fixture, workspace=workspace)
    assert error.value.code == "ASSESSMENT_PREDICATE_MISMATCH"

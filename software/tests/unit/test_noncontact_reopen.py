"""Stage-14 retained lifecycle joins with explicitly isolated audit fixtures.

These tests exercise the actual reopen dispatch/head/reference predicates, not
full M1 qualification. Earlier thirteen stages and filesystem auditing are
injected where noted. No evaluator, solver, renderer, process or device replay.
"""

from copy import deepcopy
from dataclasses import replace
import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from rocell.application import commissioning_rehearsal_reopen as reopen
from rocell.application.physical_onboarding import EvidenceReference, STAGE_ORDER
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
from rocell.providers.windows.arm_feedback_worker import ArmFeedbackWorker
from test_rehearsal_reference_binding import make_binding


SOURCE = "a" * 64
CATALOG = "b" * 64
STAGE = STAGE_ORDER[13]
WORKSPACE = Path(__file__).resolve().parents[3]


def lifecycle(state="receipt-ready"):
    """Only stage fourteen's journal; explicitly not a complete M1 store."""
    header = V2SessionHeader.build(
        session_id="rehearsal-" + "1" * 32,
        cell_id="wizard-rehearsal-" + "2" * 16,
        created_at_ns=1,
        source_binding_sha256=SOURCE,
        publication_durability=PORTABLE_UNQUALIFIED,
        durability_qualification_sha256="0" * 64,
        mode="REHEARSAL",
    )
    evidence, events = {}, []
    checks = (
        {"check_id": "nominal-installed-geometry", "passed": False},
        {"check_id": "expected-missing-term-rejection", "passed": True},
    )

    def retain(name, document, when):
        payload = reopen._json(document)
        reference = EvidenceReference(
            name,
            STAGE,
            "c" * 64,
            "d" * 64,
            hashlib.sha256(payload).hexdigest(),
            len(payload),
        )
        item = reopen.VerifiedRehearsalEvidence(reference, payload, when)
        evidence[name] = item
        return item

    def event(state, when, refs, code):
        events.append(
            V2JournalEvent.build(
                header=header,
                sequence=len(events),
                stage=STAGE,
                previous_state=events[-1].state if events else V2StageState.PENDING,
                state=state,
                occurred_at_ns=when,
                previous_event_sha256=events[-1].event_sha256 if events else "0" * 64,
                evidence=tuple(item.reference for item in refs),
                detail_code=code,
            )
        )

    common = {
        "composition": reopen.INCAPABLE_COMPOSITION,
        "stage": STAGE.value,
        "session_id": header.session_id,
        "cell_id": header.cell_id,
        "workspace_source_sha256": SOURCE,
        "catalog_sha256": CATALOG,
        "operator_id": "noncontact-operator",
        "physical_observation": False,
    }
    event(V2StageState.WAITING_OPERATOR, 10, (), "REHEARSAL_STAGE_OPENED")
    retain("opening", {**common, "schema": reopen._EVALUATED_OPEN_SCHEMAS[STAGE]}, 11)
    receipt = assessment = None
    if state != "missing-result":
        receipt = retain(
            "receipt",
            {
                **common,
                "schema": reopen._EVALUATED_SCHEMAS[STAGE],
                "evaluation": {"isolated_verification_seam": True},
                "evaluation_sha256": "e" * 64,
            },
            12,
        )
    if state in {"review-pending", "reviewed-blocked"}:
        value = {
            "schema": "rocell.rehearsal_assessment.v1",
            "composition": reopen.INCAPABLE_COMPOSITION,
            "session_id": header.session_id,
            "stage": STAGE.value,
            "source_binding_sha256": SOURCE,
            "pre_assessment_head_sha256": V2CommittedHead.build(
                header, events
            ).head_sha256,
            "receipt_sha256": reopen._hash(receipt.document()),
            "receipt_evidence_id": receipt.reference.evidence_id,
            "outcome": "BLOCKED",
            "reason_codes": ["NONCONTACT_CHECK_FAILED:nominal-installed-geometry"],
            "meaning": "Isolated stage lifecycle, not full physical/M1 evidence.",
        }
        value["assessment_sha256"] = reopen._hash(value)
        assessment = retain("assessment", value, 15)
        event(
            V2StageState.REVIEW_PENDING,
            20,
            (receipt, assessment),
            "REHEARSAL_ASSESSMENT_READY",
        )
    if state == "reviewed-blocked":
        review = retain(
            "review",
            {
                "schema": "rocell.rehearsal_review.v1",
                "composition": reopen.INCAPABLE_COMPOSITION,
                "session_id": header.session_id,
                "stage": STAGE.value,
                "assessment_sha256": assessment.document()["assessment_sha256"],
                "reviewed_head_sha256": V2CommittedHead.build(
                    header, events
                ).head_sha256,
                "reviewer_id": "independent-reviewer",
                "operator_id": "noncontact-operator",
                "decision": "ACCEPT_EXACT_ASSESSMENT",
                "physical_release_effect": "NONE",
            },
            25,
        )
        event(
            V2StageState.BLOCKED,
            30,
            (receipt, assessment, review),
            "REHEARSAL_ASSESSMENT_REVIEWED",
        )
    snapshot = V2SessionSnapshot(
        header,
        tuple(
            V2StageSnapshot(
                stage,
                (
                    V2StageState.PASS
                    if index < 13
                    else events[-1].state if stage is STAGE else V2StageState.PENDING
                ),
                None,
                (),
            )
            for index, stage in enumerate(STAGE_ORDER)
        ),
        tuple(events),
        (),
        tuple(item.reference for item in evidence.values()),
        V2CommittedHead.build(header, events),
        V2NextAction("ISOLATED_LIFECYCLE_FIXTURE", STAGE, events[-1].state, True),
    )
    return SimpleNamespace(
        snapshot=snapshot,
        evidence=evidence,
        checks=checks,
        calls=[],
        records={"fixture": {"kind": "AUDIT_SEAM_ONLY"}},
        verification=SimpleNamespace(
            evidence_inventory_sha256="f" * 64, challenge_sha256="9" * 64
        ),
    )


def install(monkeypatch, fixture, workspace):
    def no_replay(*args, **kwargs):
        pytest.fail("Retained verification must not execute solver/worker/evaluator")

    monkeypatch.setattr(rigid_correspondence, "fit_rigid_correspondence", no_replay)
    monkeypatch.setattr(ArmFeedbackWorker, "run", no_replay)
    monkeypatch.setattr(reopen, "_read_evidence", lambda *args: fixture.evidence)
    monkeypatch.setattr(reopen, "_entries", lambda *args: ())

    def pure(
        snapshot,
        evidence,
        receipt,
        source,
        catalog,
        records,
        assigned_workspace,
        *,
        directory=None
    ):
        assert snapshot is fixture.snapshot and evidence is fixture.evidence
        assert records is fixture.records and assigned_workspace == workspace
        assert source == SOURCE and catalog == CATALOG
        assert receipt.document()["schema"] == reopen._EVALUATED_SCHEMAS[STAGE]
        fixture.calls.append(receipt.reference.evidence_id)
        return SimpleNamespace(
            checks=fixture.checks, outcome="REHEARSAL_CHECKS_BLOCKED"
        )

    monkeypatch.setattr(reopen, "_verify_noncontact_receipt", pure)


def restore(tmp_path, fixture, *, workspace):
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
        ("reviewed-blocked", "DUE_STAGE"),
    ],
)
def test_original_noncontact_lifecycle_restores_blocked_not_handoff(
    tmp_path, monkeypatch, state, disposition
):
    fixture = lifecycle(state)
    workspace = tmp_path / "assigned-source"
    install(monkeypatch, fixture, workspace)
    restored = restore(tmp_path, fixture, workspace=workspace)
    assert restored.disposition == disposition
    assert restored.stage is STAGE
    assert restored.physical_authority is False
    assert restored.automatic_replay_allowed is False
    assert fixture.calls
    if state == "reviewed-blocked":
        assert restored.stage_state is V2StageState.BLOCKED
        assert restored.receipt is None and restored.assessment is None
    else:
        assert restored.receipt is fixture.evidence["receipt"]


def test_open_without_retained_noncontact_result_is_held_without_replay(
    tmp_path, monkeypatch
):
    fixture = lifecycle("missing-result")
    install(monkeypatch, fixture, tmp_path)
    with pytest.raises(reopen.RehearsalReopenError) as failure:
        restore(tmp_path, fixture, workspace=tmp_path)
    assert failure.value.code == "EVALUATION_RECEIPT_MISSING"
    assert fixture.calls == []


@pytest.mark.parametrize("missing", ["records", "workspace"])
def test_noncontact_requires_audited_records_and_server_source_before_verifier(
    tmp_path, monkeypatch, missing
):
    fixture = lifecycle()
    install(monkeypatch, fixture, tmp_path)
    with pytest.raises(reopen.RehearsalReopenError) as failure:
        reopen._verify_evaluated_receipt(
            fixture.snapshot,
            fixture.evidence,
            fixture.evidence["receipt"],
            SOURCE,
            CATALOG,
            records=None if missing == "records" else fixture.records,
            reference_workspace=None if missing == "workspace" else tmp_path,
        )
    assert failure.value.code == "NONCONTACT_CONTEXT_MISSING"
    assert fixture.calls == []


@pytest.mark.parametrize(
    "fault", ["missing-open", "wrong-operator", "late-open", "duplicate-receipt"]
)
def test_unaccepted_receipt_requires_one_exact_original_opening(
    tmp_path, monkeypatch, fault
):
    fixture = lifecycle()
    if fault == "missing-open":
        del fixture.evidence["opening"]
    elif fault == "wrong-operator":
        document = fixture.evidence["opening"].document()
        document["operator_id"] = "other-operator"
        fixture.evidence["opening"] = replace(
            fixture.evidence["opening"], payload=reopen._json(document)
        )
    elif fault == "late-open":
        fixture.evidence["opening"] = replace(
            fixture.evidence["opening"], captured_at_ns=13
        )
    else:
        receipt = fixture.evidence["receipt"]
        fixture.evidence["duplicate"] = replace(
            receipt, reference=replace(receipt.reference, evidence_id="duplicate")
        )
    install(monkeypatch, fixture, tmp_path)
    with pytest.raises(reopen.RehearsalReopenError) as failure:
        restore(tmp_path, fixture, workspace=tmp_path)
    assert failure.value.code == (
        "AMBIGUOUS_RECEIPT"
        if fault == "duplicate-receipt"
        else "EVALUATION_OPERATOR_MISMATCH"
    )
    assert fixture.calls == []


def test_expected_fault_pass_does_not_mask_failed_nominal_assessment(
    tmp_path, monkeypatch
):
    fixture = lifecycle("review-pending")
    document = fixture.evidence["assessment"].document()
    document.update(outcome="PASS", reason_codes=[])
    fixture.evidence["assessment"] = replace(
        fixture.evidence["assessment"], payload=reopen._json(document)
    )
    install(monkeypatch, fixture, tmp_path)
    with pytest.raises(reopen.RehearsalReopenError) as failure:
        restore(tmp_path, fixture, workspace=tmp_path)
    assert failure.value.code == "ASSESSMENT_PREDICATE_MISMATCH"


@pytest.mark.parametrize(
    "fault", ["session", "source", "stage", "unknown-field", "authority", "hash"]
)
def test_actual_stage14_evidence_reader_rejects_binding_or_schema_drift(
    tmp_path, monkeypatch, fault
):
    fixture = lifecycle()
    original = fixture.evidence["receipt"]
    document = original.document()
    if fault == "session":
        document["session_id"] = "another-session"
    elif fault == "source":
        document["workspace_source_sha256"] = "7" * 64
    elif fault == "stage":
        document["stage"] = STAGE_ORDER[14].value
    elif fault == "unknown-field":
        document["caller_override"] = True
    elif fault == "authority":
        document["physical_observation"] = True
    payload = reopen._json(document)
    reference = replace(
        original.reference,
        payload_sha256=hashlib.sha256(payload).hexdigest(),
        payload_bytes=len(payload),
    )
    if fault == "hash":
        reference = replace(reference, payload_sha256="8" * 64)
    snapshot = replace(fixture.snapshot, evidence=(reference,))

    def read(path, **kwargs):
        if path.name == "payload.bin":
            return deepcopy(document), payload
        return {"captured_at_ns": 12}, b"isolated-manifest-seam"

    monkeypatch.setattr(reopen, "_document", read)
    with pytest.raises(reopen.RehearsalReopenError):
        reopen._read_evidence(tmp_path, snapshot, SOURCE, CATALOG)


def test_evidence_byte_bound_rejects_before_any_original_file_read(
    tmp_path, monkeypatch
):
    fixture = lifecycle()
    reference = replace(
        fixture.evidence["receipt"].reference,
        payload_bytes=reopen.MAX_EVIDENCE_BYTES + 1,
    )
    snapshot = replace(fixture.snapshot, evidence=(reference,))
    monkeypatch.setattr(
        reopen, "_document", lambda *a, **k: pytest.fail("Oversize evidence read")
    )
    with pytest.raises(reopen.RehearsalReopenError) as failure:
        reopen._read_evidence(tmp_path, snapshot, SOURCE, CATALOG)
    assert failure.value.code == "EVIDENCE_RESOURCE_LIMIT"


@pytest.mark.parametrize("name", ["opening", "receipt"])
def test_actual_reader_accepts_exact_stage14_schema_but_not_stage15(
    tmp_path, monkeypatch, name
):
    fixture = lifecycle()
    original = fixture.evidence[name]
    document = original.document()

    def read(path, **kwargs):
        if path.name == "payload.bin":
            return deepcopy(document), reopen._json(document)
        return {"captured_at_ns": original.captured_at_ns}, b"audited-manifest-seam"

    monkeypatch.setattr(reopen, "_document", read)
    snapshot = replace(fixture.snapshot, evidence=(original.reference,))
    assert reopen._read_evidence(tmp_path, snapshot, SOURCE, CATALOG) == {
        name: original
    }
    document["stage"] = STAGE_ORDER[14].value
    payload = reopen._json(document)
    reference = replace(
        original.reference,
        stage=STAGE_ORDER[14],
        payload_sha256=hashlib.sha256(payload).hexdigest(),
        payload_bytes=len(payload),
    )
    with pytest.raises(reopen.RehearsalReopenError) as failure:
        reopen._read_evidence(
            tmp_path, replace(snapshot, evidence=(reference,)), SOURCE, CATALOG
        )
    assert failure.value.code == "EVIDENCE_BINDING_MISMATCH"


@pytest.fixture(scope="module")
def reference_report():
    # Generate once as setup, never during reopen; this is mathematical evidence,
    # not an assertion that earlier M1/hardware predecessors were qualified.
    from rocell.application import rehearsal_reference_stage as reference

    binding = make_binding(reference.read_reference_source_context(WORKSPACE))
    return binding, reference.evaluate_rehearsal_reference_stage(WORKSPACE, binding)


@pytest.fixture
def reference_join(monkeypatch, reference_report):
    from rocell.application import rehearsal_reference_stage as reference

    binding, report = reference_report
    documents = [
        {
            "schema": reopen._EVALUATED_SCHEMAS[STAGE_ORDER[12]],
            "operator_id": binding.operator_id,
            "evaluation": report.to_dict(),
            "evaluation_sha256": report.evidence_sha256,
        },
        {"assessment_sha256": "3" * 64, "outcome": "PASS"},
        {"decision": "ACCEPT_EXACT_ASSESSMENT", "reviewer_id": "prior-reviewer"},
    ]
    camera = object()
    state = SimpleNamespace(
        binding=binding,
        report=report,
        documents=documents,
        camera=camera,
        calls=[],
        records={"audited": {}},
    )

    def select(snapshot, evidence, stage):
        assert stage is STAGE_ORDER[12]
        return tuple(
            SimpleNamespace(document=lambda i=index: deepcopy(documents[i]))
            for index in range(3)
        )

    def prior(
        snapshot,
        evidence,
        operator,
        source,
        catalog,
        records,
        context,
        *,
        directory=None
    ):
        assert operator == binding.operator_id  # not the new stage operator
        assert records is state.records and context == binding.source_context
        assert source == SOURCE and catalog == CATALOG
        state.calls.append((operator, directory))
        return state.binding, camera

    def forbidden(*args, **kwargs):
        pytest.fail("Verification replayed the previously completed numerical fit")

    monkeypatch.setattr(reopen, "_reviewed_stage_evidence", select)
    monkeypatch.setattr(reopen, "_reference_binding", prior)
    monkeypatch.setattr(reference, "evaluate_rehearsal_reference_stage", forbidden)
    monkeypatch.setattr(rigid_correspondence, "fit_rigid_correspondence", forbidden)
    return state


def noncontact_source(binding):
    # Typed minimal context for this join only; the NC-01 evaluator separately
    # demands its real scene, policy and implementation source closure.
    return reopen._json(
        {
            "schema": "rocell.rehearsal_noncontact_sources.v1",
            "reference_source_context_sha256": hashlib.sha256(
                binding.source_context_json
            ).hexdigest(),
            "historical_context": {},
            "scene": {},
            "accuracy_policy_utf8": "{}",
            "accuracy_policy_sha256": hashlib.sha256(b"{}").hexdigest(),
            "dependency_source_sha256s": {"isolated-join-fixture": "5" * 64},
        }
    )


def derive_noncontact(state, tmp_path):
    return reopen._noncontact_binding(
        None,
        {},
        "new-noncontact-operator",
        SOURCE,
        CATALOG,
        state.records,
        noncontact_source(state.binding),
        reference_workspace=WORKSPACE,
        directory=tmp_path,
    )


def test_noncontact_joins_full_reference_hash_domains_without_fit_replay(
    reference_join, tmp_path
):
    binding, camera = derive_noncontact(reference_join, tmp_path)
    assert camera is reference_join.camera
    assert binding.reference_binding is reference_join.binding
    assert binding.operator_id == "new-noncontact-operator"
    assert binding.reference_binding.operator_id == "test-operator"
    assert binding.predecessor_receipt_sha256 == reopen._hash(
        reference_join.documents[0]
    )
    assert binding.predecessor_assessment_sha256 == reopen._hash(
        reference_join.documents[1]
    )
    assert binding.predecessor_assessment_sha256 != "3" * 64
    assert binding.predecessor_review_sha256 == reopen._hash(
        reference_join.documents[2]
    )
    assert binding.reference_evidence_sha256 == reference_join.report.evidence_sha256
    assert reference_join.calls == [("test-operator", tmp_path)]
    original = binding.binding_sha256
    binding.to_dict()["reference_binding"]["operator_id"] = "mutation"
    assert binding.binding_sha256 == original
    assert binding.to_dict()["physical_authority"] is False


@pytest.mark.parametrize(
    "field",
    [
        "workspace_source_sha256",
        "session_id",
        "catalog_sha256",
        "camera_capture_receipt_sha256",
        "retained_campaign_sha256",
        "final_power_observation_sha256",
    ],
)
def test_changed_original_reference_dependencies_refused_by_actual_retained_verifier(
    reference_join, tmp_path, field
):
    changed = "other-session" if field == "session_id" else "7" * 64
    reference_join.binding = replace(reference_join.binding, **{field: changed})
    with pytest.raises(ValueError):
        derive_noncontact(reference_join, tmp_path)


@pytest.mark.parametrize("fault", ["schema", "evaluation-hash", "evaluation-bytes"])
def test_changed_original_reference_receipt_cannot_reach_noncontact(
    reference_join, tmp_path, fault
):
    document = reference_join.documents[0]
    if fault == "schema":
        document["schema"] = reopen._EVALUATED_SCHEMAS[STAGE_ORDER[11]]
    elif fault == "evaluation-hash":
        document["evaluation_sha256"] = "8" * 64
    else:
        document["evaluation"]["selected_inputs_sha256"] = "8" * 64
    with pytest.raises(ValueError):
        derive_noncontact(reference_join, tmp_path)


def test_noncontact_source_must_match_exact_original_reference_geometry(
    reference_join, tmp_path
):
    import json

    context = json.loads(noncontact_source(reference_join.binding))
    context["reference_source_context_sha256"] = "9" * 64
    with pytest.raises(ValueError, match="reference source context differ"):
        reopen._noncontact_binding(
            None,
            {},
            "new-noncontact-operator",
            SOURCE,
            CATALOG,
            reference_join.records,
            reopen._json(context),
            reference_workspace=WORKSPACE,
            directory=tmp_path,
        )


@pytest.fixture
def actual_noncontact(reference_join, tmp_path, monkeypatch):
    """Actual source-bound report; earlier reviewed M1 trios remain injected."""
    from rocell.application import rehearsal_noncontact_stage as noncontact

    binding, camera = reopen._noncontact_binding(
        None,
        {},
        "new-noncontact-operator",
        SOURCE,
        CATALOG,
        reference_join.records,
        noncontact.read_noncontact_source_context(WORKSPACE),
        reference_workspace=WORKSPACE,
        directory=tmp_path,
    )
    report = noncontact.evaluate_rehearsal_noncontact_stage(WORKSPACE, binding)
    document = {
        "schema": reopen._EVALUATED_SCHEMAS[STAGE],
        "stage": STAGE.value,
        "operator_id": binding.operator_id,
        "evaluation": report.to_dict(),
        "evaluation_sha256": report.evidence_sha256,
    }

    def forbidden(*args, **kwargs):
        pytest.fail("Reopen replayed the original noncontact assessor/evaluator")

    # Source reads stay permitted only at _verify_noncontact_receipt's explicit
    # expected-input boundary. Its inner verifier must remain filesystem-free.
    original_verify = noncontact.verify_rehearsal_noncontact_evidence
    verified_calls = []

    def verify(*args, **kwargs):
        verified_calls.append(kwargs)
        with monkeypatch.context() as scope:
            scope.setattr(noncontact, "_read", forbidden)
            scope.setattr(noncontact, "load_simulation_context", forbidden)
            return original_verify(*args, **kwargs)

    for name in (
        "evaluate_rehearsal_noncontact_stage",
        "assess_current_collision_readiness",
        "assess_target_accuracy_budget",
    ):
        monkeypatch.setattr(noncontact, name, forbidden)
    monkeypatch.setattr(noncontact, "verify_rehearsal_noncontact_evidence", verify)
    return SimpleNamespace(
        binding=binding,
        report=report,
        document=document,
        camera=camera,
        prior=reference_join,
        verified_calls=verified_calls,
    )


def verify_actual(state, tmp_path):
    payload = reopen._json(state.document)
    receipt = reopen.VerifiedRehearsalEvidence(
        EvidenceReference(
            "noncontact-actual",
            STAGE,
            "c" * 64,
            "d" * 64,
            hashlib.sha256(payload).hexdigest(),
            len(payload),
        ),
        payload,
        100,
    )
    return reopen._verify_evaluated_receipt(
        None,
        {},
        receipt,
        SOURCE,
        CATALOG,
        records=state.prior.records,
        reference_workspace=WORKSPACE,
        directory=tmp_path,
    )


def test_actual_noncontact_report_reopens_full_bound_bytes_without_assessor_replay(
    actual_noncontact, tmp_path
):
    verified = verify_actual(actual_noncontact, tmp_path)
    assert verified.canonical_bytes() == actual_noncontact.report.canonical_bytes()
    assert verified.outcome == "BLOCKED"
    assert any(
        not row["passed"] and row["check_kind"] == "NOMINAL" for row in verified.checks
    )
    assert all(
        row["passed"]
        for row in verified.checks
        if row["check_kind"] == "EXPECTED_FAULT"
    )
    assert verified.to_dict()["physical_authority"] is False
    assert len(verified.canonical_bytes()) < reopen.MAX_EVIDENCE_BYTES
    expected = actual_noncontact.verified_calls[-1]
    assert (
        expected["expected_binding"].binding_sha256
        == actual_noncontact.binding.binding_sha256
    )
    assert (
        expected["expected_evidence_sha256"] == actual_noncontact.report.evidence_sha256
    )


@pytest.mark.parametrize(
    "fault",
    [
        "old-hash",
        "rehashed-outcome",
        "rehashed-count",
        "rehashed-inventory",
        "unknown-field",
    ],
)
def test_actual_noncontact_report_tamper_is_not_promoted_even_with_new_outer_hash(
    actual_noncontact, tmp_path, fault
):
    document = actual_noncontact.document
    report = document["evaluation"]
    if fault == "old-hash":
        document["evaluation_sha256"] = "8" * 64
    elif fault == "rehashed-outcome":
        report["outcome"] = "REHEARSAL_CHECKS_PASSED"
    elif fault == "rehashed-count":
        report["safe_summary"]["static_geometry"]["required_body_count"] -= 1
    elif fault == "rehashed-inventory":
        report["technical_reports"]["static_inventory"]["geometry"].pop()
    else:
        report["caller_override"] = True
    if fault != "old-hash":
        document["evaluation_sha256"] = reopen._hash(report)
    with pytest.raises(ValueError):
        verify_actual(actual_noncontact, tmp_path)

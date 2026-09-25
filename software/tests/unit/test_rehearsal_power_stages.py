from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from rocell.application import physical_onboarding_receipts as receipts
from rocell.application import rehearsal_power_stages as power


WORKSPACE = Path(__file__).resolve().parents[3]
STAGES = ("power_safety", "power_on_observation")


def binding(stage: str = "power_safety") -> power.RehearsalPowerBinding:
    return power.RehearsalPowerBinding(
        workspace_source_sha256="1" * 64,
        catalog_sha256="2" * 64,
        cell_id="wizard-rehearsal-0123456789abcdef",
        session_id="rehearsal-" + "a" * 32,
        operator_id="operator-a",
        stage=stage,
        predecessor_receipt_sha256="3" * 64,
        predecessor_assessment_sha256="4" * 64,
        predecessor_review_sha256="5" * 64,
        arm_identity_evidence_sha256="6" * 64,
    )


def encode(document: object) -> bytes:
    return json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode()


def digest(document: object) -> str:
    return hashlib.sha256(encode(document)).hexdigest()


@pytest.fixture(scope="module", params=STAGES)
def evidence(request: pytest.FixtureRequest) -> power.RehearsalPowerEvidence:
    return power.evaluate_rehearsal_power_stage(WORKSPACE, binding(request.param))


def verify(document: dict[str, Any]) -> power.RehearsalPowerEvidence:
    return power.verify_rehearsal_power_evidence(
        encode(document),
        expected_binding=binding(document["stage"]),
    )


def refresh_report_hashes(document: dict[str, Any]) -> None:
    document["report_hashes"] = {
        key: digest(value) for key, value in document["reports"].items()
    }


def refresh_assessment_hash(assessment: dict[str, Any]) -> None:
    assessment["assessment_sha256"] = receipts.canonical_sha256(
        {key: value for key, value in assessment.items() if key != "assessment_sha256"}
    )


def test_closed_evaluation_roundtrip_and_complete_reports(evidence):
    document = evidence.to_dict()
    stage = document["stage"]
    expected_count = 11 if stage == "power_safety" else 15
    assert len(evidence.checks) == expected_count
    assert evidence.outcome == "REHEARSAL_CHECKS_PASSED"
    assert all(check["passed"] is True for check in evidence.checks)
    assert len(evidence.canonical_bytes()) < 90 * 1024
    assert power.MAX_EVIDENCE_BYTES == 96 * 1024
    assert document["physical_authority"] is False
    assert set(document["authority"]["actual_physical_effects"].values()) == {0}
    assert document["authority"]["composition"] == "HARDWARE_INCAPABLE_REHEARSAL"
    assert document["provenance"]["physical_observations"] is False
    assert "NOT_PREDICTED_TRAJECTORY" in document["provenance"]["startup_motion_role"]
    assert len(document["reports"]) == expected_count - 1
    assert len([c for c in evidence.checks if c["check_kind"] == "NOMINAL"]) == (
        1 if stage == "power_safety" else 2
    )
    for check_id, report in document["reports"].items():
        model = (
            receipts.PowerSafetyReview
            if stage == "power_safety"
            else receipts.FirstPowerObservation
        ).from_dict(report["typed_input"])
        assessor = (
            receipts.assess_power_safety
            if stage == "power_safety"
            else receipts.assess_first_power_observation
        )
        assert report["assessment"] == assessor(model).to_dict()
        assert document["report_hashes"][check_id] == digest(report)
    retained = power.verify_rehearsal_power_evidence(
        evidence.canonical_bytes(),
        expected_binding=binding(stage),
        expected_evidence_sha256=evidence.evidence_sha256,
        expected_evaluator_source_sha256=hashlib.sha256(
            Path(power.__file__).read_bytes()
        ).hexdigest(),
    )
    assert retained.canonical_bytes() == evidence.canonical_bytes()
    assert retained.evaluation_sha256 == evidence.evidence_sha256
    assert "evaluation_sha256" not in document


def test_real_assessors_are_invoked_not_legacy_field_existence(monkeypatch):
    calls: list[tuple[str, object]] = []
    for stage, name in (
        ("power_safety", "assess_power_safety"),
        ("power_on_observation", "assess_first_power_observation"),
    ):
        original = getattr(receipts, name)

        def assessor(subject, *, _original=original, _stage=stage):
            calls.append((_stage, subject))
            return _original(subject)

        monkeypatch.setattr(receipts, name, assessor)
        result = power.evaluate_rehearsal_power_stage(WORKSPACE, binding(stage))
        assert len(result.to_dict()["reports"]) == sum(s == stage for s, _ in calls)
    assert len(calls) == 24
    assert all(
        isinstance(s, (receipts.PowerSafetyReview, receipts.FirstPowerObservation))
        for _, s in calls
    )


def test_verification_and_binding_construction_have_no_io_or_assessor_calls(
    evidence, monkeypatch
):
    payload = evidence.canonical_bytes()
    stage = evidence.to_dict()["stage"]

    def forbidden(*args, **kwargs):
        raise AssertionError("retained verification attempted evaluation or I/O")

    with monkeypatch.context() as patch:
        for name in (
            "open",
            "read_bytes",
            "read_text",
            "lstat",
            "stat",
            "iterdir",
            "resolve",
        ):
            patch.setattr(Path, name, forbidden)
        patch.setattr(receipts, "assess_power_safety", forbidden)
        patch.setattr(receipts, "assess_first_power_observation", forbidden)
        patch.setattr(power, "evaluate_rehearsal_power_stage", forbidden)
        result = power.verify_rehearsal_power_evidence(
            payload,
            expected_binding=binding(stage),
            expected_evidence_sha256=hashlib.sha256(payload).hexdigest(),
        )
        assert result.outcome == "REHEARSAL_CHECKS_PASSED"


def test_inner_bindings_and_materials_are_explicitly_synthetic(evidence):
    document = evidence.to_dict()
    selected = document["selected_inputs"]
    legacy = selected["fixture_binding"]
    assert legacy["cell_id"].startswith("synthetic-")
    assert legacy["session_id"].startswith("synthetic-")
    assert legacy["cell_id"] != document["binding"]["cell_id"]
    assert (
        legacy["source_binding_sha256"]
        != document["binding"]["workspace_source_sha256"]
    )
    assert len(selected["fixture_materials"]) == 2
    for material, reference in zip(selected["fixture_materials"], legacy["evidence"]):
        assert material["payload"]["physical_observation"] is False
        assert material["package"]["purpose"] == "NOT_AN_M1_EVIDENCE_PACKAGE"
        assert reference["payload_sha256"] == digest(material["payload"])
        assert reference["manifest_sha256"] == digest(material["manifest"])
        assert reference["package_sha256"] == digest(material["package"])
        assert reference["payload_bytes"] == len(encode(material["payload"]))


@pytest.mark.parametrize(
    "field",
    [
        "workspace_source_sha256",
        "catalog_sha256",
        "cell_id",
        "session_id",
        "operator_id",
        "predecessor_receipt_sha256",
        "predecessor_assessment_sha256",
        "predecessor_review_sha256",
        "arm_identity_evidence_sha256",
    ],
)
def test_each_trusted_binding_field_prevents_substitution(evidence, field):
    expected = binding(evidence.to_dict()["stage"])
    value = "9" * 64 if field.endswith("sha256") else "other-identity"
    with pytest.raises(power.RehearsalPowerError, match="expected binding"):
        power.verify_rehearsal_power_evidence(
            evidence.canonical_bytes(),
            expected_binding=replace(expected, **{field: value}),
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("stage", "feedback_only"),
        ("stage", True),
        ("cell_id", "../unsafe"),
        ("session_id", "a" * 97),
        ("operator_id", "operator\n"),
        ("workspace_source_sha256", "A" * 64),
        ("catalog_sha256", True),
    ],
)
def test_invalid_bindings_rejected(field, value):
    with pytest.raises(power.RehearsalPowerError):
        replace(binding(), **{field: value})


@pytest.mark.parametrize(
    "sequence", [-1, True, False, 1.0, "1", power.MAX_SEQUENCE + 1]
)
def test_sequence_is_bounded_integer_before_io(sequence, monkeypatch):
    monkeypatch.setattr(
        power, "_read_source", lambda *a: pytest.fail("unexpected source read")
    )
    with pytest.raises(power.RehearsalPowerError):
        power.evaluate_rehearsal_power_stage(WORKSPACE, binding(), sequence=sequence)


def test_sequence_is_identity_not_an_action_retry():
    first = power.evaluate_rehearsal_power_stage(
        WORKSPACE, binding("power_on_observation")
    )
    next_result = power.evaluate_rehearsal_power_stage(
        WORKSPACE,
        binding("power_on_observation"),
        sequence=power.MAX_SEQUENCE,
    )
    assert first.evidence_sha256 != next_result.evidence_sha256
    assert (
        first.to_dict()["selected_inputs_sha256"]
        != next_result.to_dict()["selected_inputs_sha256"]
    )
    nominal = next_result.to_dict()["reports"]["nominal_no_startup_motion"][
        "typed_input"
    ]
    assert nominal["attempt_count"] == 1
    assert nominal["automatic_retry_count"] == 0
    assert (
        next_result.to_dict()["authority"]["actual_physical_effects"]["power_events"]
        == 0
    )


@pytest.mark.parametrize(
    "expected_field", ["expected_evidence_sha256", "expected_evaluator_source_sha256"]
)
def test_trusted_hash_substitution_rejected(evidence, expected_field):
    with pytest.raises(power.RehearsalPowerError):
        power.verify_rehearsal_power_evidence(
            evidence.canonical_bytes(),
            expected_binding=binding(evidence.to_dict()["stage"]),
            **{expected_field: "f" * 64},
        )


@pytest.mark.parametrize(
    "mutation",
    [
        "extra_top",
        "wrong_stage",
        "authority_mode",
        "authority_counter_bool",
        "authority_physical",
        "provenance_physical",
        "meaning",
        "self_hash",
        "evaluator_id",
        "dependency_key",
        "dependency_digest",
        "input_manifest",
        "selected_hash",
        "report_hash",
        "case_kind",
        "input_extra",
        "input_bool",
        "input_authority_int",
        "input_hash",
        "assessment_extra",
        "assessment_subject",
        "assessment_bool",
        "assessment_disposition",
        "assessment_reasons_duplicate",
        "assessment_authority",
        "assessment_hash",
        "check_kind",
        "check_bool",
        "check_observed",
        "missing_check",
        "duplicate_check",
        "reordered_checks",
        "missing_nominal",
        "extra_report",
        "wrong_outcome",
    ],
)
def test_strict_schema_hash_flags_and_derived_checks(evidence, mutation):
    doc = evidence.to_dict()
    first = next(iter(doc["reports"].values()))
    typed = first["typed_input"]
    assessment = first["assessment"]
    if mutation == "extra_top":
        doc["unexpected"] = False
    elif mutation == "wrong_stage":
        doc["stage"] = "feedback_only"
    elif mutation == "authority_mode":
        doc["authority"]["composition"] = "PHYSICAL_DIAGNOSTIC"
    elif mutation == "authority_counter_bool":
        doc["authority"]["actual_physical_effects"]["power_events"] = False
    elif mutation == "authority_physical":
        doc["physical_authority"] = 0
    elif mutation == "provenance_physical":
        doc["provenance"]["physical_observations"] = True
    elif mutation == "meaning":
        doc["meaning"] = "Physical setup complete"
    elif mutation == "self_hash":
        doc["evaluation_sha256"] = "a" * 64
    elif mutation == "evaluator_id":
        doc["evaluator"]["id"] = "OTHER"
    elif mutation == "dependency_key":
        doc["evaluator"]["dependency_source_sha256"]["extra.py"] = "a" * 64
    elif mutation == "dependency_digest":
        next_key = next(iter(doc["evaluator"]["dependency_source_sha256"]))
        doc["evaluator"]["dependency_source_sha256"][next_key] = "A" * 64
    elif mutation == "input_manifest":
        doc["selected_inputs"]["fixture_materials"][0]["payload"][
            "physical_observation"
        ] = True
    elif mutation == "selected_hash":
        doc["selected_inputs_sha256"] = "a" * 64
    elif mutation == "report_hash":
        doc["report_hashes"][next(iter(doc["reports"]))] = "a" * 64
    elif mutation == "case_kind":
        first["check_kind"] = (
            "NOMINAL" if first["check_kind"] != "NOMINAL" else "EXPECTED_FAULT"
        )
    elif mutation == "input_extra":
        typed["untrusted_field"] = True
    elif mutation == "input_bool":
        typed[
            (
                "polarity_verified"
                if doc["stage"] == "power_safety"
                else "clearance_preserved"
            )
        ] = 1
    elif mutation == "input_authority_int":
        typed["authority"]["power_authorized"] = 0
    elif mutation == "input_hash":
        typed["receipt_sha256"] = "a" * 64
    elif mutation == "assessment_extra":
        assessment["unknown"] = False
    elif mutation == "assessment_subject":
        assessment["subject_receipt_sha256"] = "a" * 64
    elif mutation == "assessment_bool":
        assessment["diagnostic_ready"] = int(assessment["diagnostic_ready"])
    elif mutation == "assessment_disposition":
        assessment["disposition"] = "PASS"
    elif mutation == "assessment_reasons_duplicate":
        assessment["reason_codes"] *= 2
    elif mutation == "assessment_authority":
        assessment["authority"]["motion_authorized"] = True
    elif mutation == "assessment_hash":
        assessment["assessment_sha256"] = "a" * 64
    elif mutation == "check_kind":
        doc["checks"][0]["check_kind"] = "INVARIANT"
    elif mutation == "check_bool":
        doc["checks"][0]["passed"] = 1
    elif mutation == "check_observed":
        doc["checks"][0]["observed"]["diagnostic_ready"] = False
    elif mutation == "missing_check":
        doc["checks"].pop()
    elif mutation == "duplicate_check":
        doc["checks"].append(doc["checks"][0])
    elif mutation == "reordered_checks":
        doc["checks"].reverse()
    elif mutation == "missing_nominal":
        doc["reports"] = {
            k: v for k, v in doc["reports"].items() if v["check_kind"] != "NOMINAL"
        }
    elif mutation == "extra_report":
        doc["reports"]["extra"] = first
    elif mutation == "wrong_outcome":
        doc["outcome"] = "PHYSICALLY_READY"
    if mutation != "report_hash":
        refresh_report_hashes(doc)
    doc["selected_inputs_sha256"] = (
        digest(doc["selected_inputs"])
        if mutation != "selected_hash"
        else doc["selected_inputs_sha256"]
    )
    with pytest.raises(power.RehearsalPowerError):
        power.verify_rehearsal_power_evidence(
            encode(doc), expected_binding=binding(evidence.to_dict()["stage"])
        )


@pytest.mark.parametrize("stage", STAGES)
def test_coherent_nominal_regression_is_retained_blocked_not_fake_success(
    monkeypatch, stage
):
    name = (
        "assess_power_safety"
        if stage == "power_safety"
        else "assess_first_power_observation"
    )
    original = getattr(receipts, name)

    def regressed(subject):
        result = original(subject).to_dict()
        if result["diagnostic_ready"]:
            result.update(
                disposition="HOLD",
                reason_codes=["REGRESSION_REQUIRES_REVIEW"],
                diagnostic_ready=False,
                hold_required=True,
                side_effect_uncertain=False,
            )
            refresh_assessment_hash(result)
        return SimpleNamespace(to_dict=lambda: result)

    monkeypatch.setattr(receipts, name, regressed)
    result = power.evaluate_rehearsal_power_stage(WORKSPACE, binding(stage))
    assert result.outcome == "BLOCKED"
    assert all(
        c["passed"] is False for c in result.checks if c["check_kind"] == "NOMINAL"
    )
    assert all(
        c["passed"] is True
        for c in result.checks
        if c["check_kind"] == "EXPECTED_FAULT"
    )
    assert (
        power.verify_rehearsal_power_evidence(
            result.canonical_bytes(),
            expected_binding=binding(stage),
            expected_evidence_sha256=result.evidence_sha256,
        ).outcome
        == "BLOCKED"
    )
    forged = result.to_dict()
    forged["outcome"] = "REHEARSAL_CHECKS_PASSED"
    for check in forged["checks"]:
        check["passed"] = True
    with pytest.raises(power.RehearsalPowerError, match="derived checks"):
        verify(forged)


def test_expected_fault_regression_cannot_mint_nominal_readiness(monkeypatch):
    original = receipts.assess_first_power_observation

    def regressed(subject):
        result = original(subject).to_dict()
        if subject.post_event_power_state is receipts.ReviewedPowerState.UNKNOWN:
            result.update(
                disposition="HOLD",
                reason_codes=["WRONG_UNCERTAINTY_CLASSIFICATION"],
                diagnostic_ready=False,
                hold_required=True,
                side_effect_uncertain=False,
            )
            refresh_assessment_hash(result)
        return SimpleNamespace(to_dict=lambda: result)

    monkeypatch.setattr(receipts, "assess_first_power_observation", regressed)
    result = power.evaluate_rehearsal_power_stage(
        WORKSPACE, binding("power_on_observation")
    )
    assert result.outcome == "BLOCKED"
    assert all(c["passed"] for c in result.checks if c["check_kind"] == "NOMINAL")
    assert (
        next(c for c in result.checks if c["check_id"] == "unknown_final_power")[
            "passed"
        ]
        is False
    )


def test_source_change_during_evaluation_fails_before_return(monkeypatch):
    original = power._read_source
    count = 0

    def changed(root, relative):
        nonlocal count
        count += 1
        value = original(root, relative)
        return value + b"\n" if count > 3 else value

    monkeypatch.setattr(power, "_read_source", changed)
    with pytest.raises(power.RehearsalPowerError, match="source changed"):
        power.evaluate_rehearsal_power_stage(WORKSPACE, binding())


def test_dependency_sources_exact_and_read_only(evidence):
    doc = evidence.to_dict()
    for relative, expected_hash in doc["evaluator"]["dependency_source_sha256"].items():
        assert (
            expected_hash
            == hashlib.sha256((WORKSPACE / relative).read_bytes()).hexdigest()
        )


@pytest.mark.parametrize(
    "payload",
    [
        b"",
        b"\xff",
        b"{}",
        b"[]",
        b'{"a":1,"a":2}',
        b'{"a":NaN}',
        b'{"a":Infinity}',
        b'{"a":1.0}',
        b"[" * 40 + b"0" + b"]" * 40,
        b'{"a":' + str(2**64).encode() + b"}",
        b" " * (power.MAX_EVIDENCE_BYTES + 1),
    ],
    ids=[
        "empty",
        "utf8",
        "empty-object",
        "array",
        "duplicate",
        "nan",
        "infinity",
        "float",
        "nesting",
        "integer",
        "oversize",
    ],
)
def test_malformed_oversize_deep_and_nonfinite_json_rejected(payload):
    with pytest.raises(power.RehearsalPowerError):
        power.verify_rehearsal_power_evidence(payload, expected_binding=binding())


def test_noncanonical_encoding_is_not_a_substitute_for_authenticated_bytes(evidence):
    doc = evidence.to_dict()
    pretty = json.dumps(doc, indent=2).encode()
    with pytest.raises(power.RehearsalPowerError):
        power.verify_rehearsal_power_evidence(
            pretty, expected_binding=binding(doc["stage"])
        )


def test_immutable_evidence_returns_detached_nested_values(evidence):
    changed = evidence.to_dict()
    changed["reports"].clear()
    assert evidence.to_dict()["reports"]
    changed_checks = evidence.checks
    changed_checks[0]["passed"] = False
    assert evidence.checks[0]["passed"] is True
    with pytest.raises(FrozenInstanceError):
        evidence._payload = b"{}"

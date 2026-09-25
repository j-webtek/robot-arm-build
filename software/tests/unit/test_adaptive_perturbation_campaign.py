from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from rocell.application import (
    AdaptivePerturbationCampaignError,
    AdaptivePerturbationPolicy,
    AdaptivePerturbationSpec,
    BoardPoseCorrectionStatus,
    default_adaptive_perturbation_specs,
)
from rocell.application.adaptive_perturbation_campaign import (
    _run_adaptive_perturbation_campaign_with_runners,
)


WORKSPACE = Path(__file__).resolve().parents[3]


class _FakeReport:
    def __init__(self, spec: Any, ordinal: int, *, mismatch: bool = False) -> None:
        outcome = spec.expected_outcome
        statuses: tuple[BoardPoseCorrectionStatus, ...]
        if mismatch:
            outcome = "COMPLETE_NO_CHANGE"
        if outcome == "COMPLETE_NO_CHANGE":
            statuses = (BoardPoseCorrectionStatus.NO_CHANGE,)
            executions, installations, contacts = 8, 0, 1
            complete, fault = True, None
        elif outcome == "COMPLETE_CORRECTED":
            statuses = (
                BoardPoseCorrectionStatus.APPLY,
                BoardPoseCorrectionStatus.NO_CHANGE,
            )
            executions, installations, contacts = 12, 1, 1
            complete, fault = True, None
        else:
            statuses = (BoardPoseCorrectionStatus.REJECT,)
            executions, installations, contacts = 3, 0, 0
            complete = False
            fault = "BOARD_POSE_CORRECTION_REJECTED:INJECTED_LIMIT"
        self.vision_attempts = tuple(
            SimpleNamespace(decision=SimpleNamespace(status=status))
            for status in statuses
        )
        self.executions = tuple(object() for _ in range(executions))
        self.correction_installations = tuple(
            object() for _ in range(installations)
        )
        self.contact_attempts = tuple(object() for _ in range(contacts))
        self.pipeline_completed = complete
        self.fault_reason = fault
        self.arm_document = {"lifecycle": "CLOSED"}
        self.truth_registration_sha256 = hashlib.sha256(
            f"truth:{ordinal}:{spec.input_hash}".encode("ascii")
        ).hexdigest()
        self.report_hash = hashlib.sha256(
            f"report:{ordinal}:{spec.input_hash}:{mismatch}".encode("ascii")
        ).hexdigest()

    def to_dict(self) -> dict[str, object]:
        return {
            "report_sha256": self.report_hash,
            "authority": {
                "simulation_only": True,
                "hardware_accessed": False,
                "hardware_commands_generated": 0,
                "execution_authorized": False,
                "live_motion_authorized": False,
                "physical_contact_authorized": False,
            },
        }


def _fake_campaign(
    policy: AdaptivePerturbationPolicy,
    *,
    mismatch_ordinal: int | None = None,
):
    ordinal = 0

    def session_runner(*_args: Any, **_kwargs: Any) -> Any:
        nonlocal ordinal
        assert _kwargs["policy"] is policy.session_policy
        spec = policy.cases[ordinal]
        report = _FakeReport(
            spec,
            ordinal,
            mismatch=ordinal == mismatch_ordinal,
        )
        ordinal += 1
        return report

    report = _run_adaptive_perturbation_campaign_with_runners(
        WORKSPACE,
        policy=policy,
        session_runner=session_runner,
        revalidator=lambda _bootstrap: None,
    )
    return report, ordinal


def test_generator_is_exactly_repeatable_and_seed_changes_only_generated_cases() -> None:
    first = default_adaptive_perturbation_specs(1234, generated_case_count=8)
    repeated = default_adaptive_perturbation_specs(1234, generated_case_count=8)
    changed = default_adaptive_perturbation_specs(1235, generated_case_count=8)

    assert first == repeated
    assert tuple(case.input_hash for case in first) == tuple(
        case.input_hash for case in repeated
    )
    assert first[:12] == changed[:12]
    assert tuple(case.input_hash for case in first[12:]) != tuple(
        case.input_hash for case in changed[12:]
    )
    assert len(first) == 20
    assert len({case.case_id for case in first}) == 20


def test_generated_cases_are_bounded_combined_and_signed() -> None:
    cases = default_adaptive_perturbation_specs(42, generated_case_count=16)
    generated = cases[12:]

    assert len(cases) == 28
    assert {case.device for case in generated} == {"keyboard", "phone"}
    assert all(case.expected_outcome == "COMPLETE_CORRECTED" for case in generated)
    assert all(
        2.0 <= (case.translation_Wv_mm[0] ** 2 + case.translation_Wv_mm[1] ** 2) ** 0.5 <= 9.0
        for case in generated
    )
    assert any(case.translation_Wv_mm[0] < 0 for case in generated)
    assert any(case.translation_Wv_mm[0] > 0 for case in generated)
    assert any(case.translation_Wv_mm[1] < 0 for case in generated)
    assert any(case.translation_Wv_mm[1] > 0 for case in generated)


def test_complete_fake_campaign_checks_all_outcome_classes_and_zero_authority() -> None:
    policy = AdaptivePerturbationPolicy(seed=9876, generated_case_count=8)
    report, call_count = _fake_campaign(policy)

    assert call_count == 20
    assert len(report.results) == 20
    assert all(result.passed for result in report.results)
    assert report.campaign_passed is True
    assert report.status == "ADAPTIVE_PERTURBATION_CAMPAIGN_PASS_WITH_PHYSICAL_HOLDS"
    assert sum(
        result.spec.expected_outcome == "REJECT_BEFORE_CONTACT"
        for result in report.results
    ) == 4
    document = report.to_dict()
    assert document["authority"]["hardware_commands_generated"] == 0  # type: ignore[index]
    assert document["summary"]["physical_ready"] is False  # type: ignore[index]
    serialized = json.dumps(document, sort_keys=True)
    assert "translation_Wv_mm" not in serialized
    assert "yaw_board_rad" not in serialized


def test_campaign_hash_binds_explicit_synthetic_convergence_policy() -> None:
    policy = AdaptivePerturbationPolicy()
    correction = policy.session_policy.correction_policy
    document = policy.to_dict()

    assert correction.translation_deadband_mm == 1.5
    assert correction.maximum_translation_delta_mm == 15.0
    assert correction.maximum_yaw_delta_rad == pytest.approx(0.08726646259971647)
    assert correction.maximum_inlier_reprojection_rmse_px == 3.0
    assert policy.session_policy.camera_quality_policy is not None
    assert (
        policy.session_policy.camera_quality_policy.maximum_inlier_rmse_px == 3.0
    )
    assert document["session_policy"]["policy_sha256"] == (  # type: ignore[index]
        policy.session_policy.policy_hash
    )
    assert document["session_policy"]["physical_tolerance_claimed"] is False  # type: ignore[index]


def test_same_seed_and_fake_results_produce_identical_report() -> None:
    policy = AdaptivePerturbationPolicy(seed=-77, generated_case_count=4)
    first, _ = _fake_campaign(policy)
    second, _ = _fake_campaign(policy)

    assert first.to_dict() == second.to_dict()
    assert first.report_hash == second.report_hash


def test_one_behavior_mismatch_is_a_retained_campaign_gap() -> None:
    policy = AdaptivePerturbationPolicy(generated_case_count=1)
    report, _ = _fake_campaign(policy, mismatch_ordinal=2)

    assert report.results[2].passed is False
    assert report.campaign_passed is False
    assert report.status == "ADAPTIVE_PERTURBATION_CAMPAIGN_GAPS_REPORTED"
    assert len(report.results) == len(policy.cases)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("seed", True),
        ("seed", 1 << 63),
        ("generated_case_count", -1),
        ("generated_case_count", 17),
        ("maximum_total_executions", 4097),
        ("maximum_total_captures", 97),
    ),
)
def test_policy_rejects_invalid_or_unbounded_inputs(field: str, value: object) -> None:
    with pytest.raises(AdaptivePerturbationCampaignError):
        AdaptivePerturbationPolicy(**{field: value})  # type: ignore[arg-type]


def test_public_generator_and_specs_enforce_hard_input_bounds() -> None:
    with pytest.raises(AdaptivePerturbationCampaignError, match="signed 64-bit"):
        default_adaptive_perturbation_specs(1 << 63)
    with pytest.raises(AdaptivePerturbationCampaignError, match="hard diagnostic bound"):
        AdaptivePerturbationSpec(
            "oversized",
            "keyboard",
            (1_001.0, 0.0, 0.0),
            0.0,
            "COMPLETE_CORRECTED",
            "BOUNDARY_TEST",
        )


def test_campaign_evidence_rejects_mutable_or_contradictory_shapes() -> None:
    report, _ = _fake_campaign(AdaptivePerturbationPolicy(generated_case_count=0))
    result = report.results[0]

    with pytest.raises(AdaptivePerturbationCampaignError, match="integer"):
        replace(result, execution_count=True)
    with pytest.raises(AdaptivePerturbationCampaignError, match="immutable status tuple"):
        replace(result, decision_statuses=["NO_CHANGE"])  # type: ignore[arg-type]
    with pytest.raises(AdaptivePerturbationCampaignError, match="completed case"):
        replace(result, fault_reason="CONTRADICTORY_COMPLETE")
    with pytest.raises(AdaptivePerturbationCampaignError, match="immutable result tuple"):
        replace(report, results=list(report.results))  # type: ignore[arg-type]


def test_actual_resource_cap_aborts_immediately() -> None:
    policy = AdaptivePerturbationPolicy(
        generated_case_count=0,
        maximum_total_executions=1,
    )
    calls = 0

    def session_runner(*_args: Any, **_kwargs: Any) -> Any:
        nonlocal calls
        spec = policy.cases[calls]
        result = _FakeReport(spec, calls)
        calls += 1
        return result

    with pytest.raises(
        AdaptivePerturbationCampaignError,
        match="execution count exceeded policy cap",
    ):
        _run_adaptive_perturbation_campaign_with_runners(
            WORKSPACE,
            policy=policy,
            session_runner=session_runner,
        )
    assert calls == 1


def test_final_revalidation_failure_aborts_without_report() -> None:
    policy = AdaptivePerturbationPolicy(generated_case_count=0)
    ordinal = 0

    def session_runner(*_args: Any, **_kwargs: Any) -> Any:
        nonlocal ordinal
        result = _FakeReport(policy.cases[ordinal], ordinal)
        ordinal += 1
        return result

    def reject(_bootstrap: Any) -> None:
        raise AdaptivePerturbationCampaignError("FINAL_SOURCE_REVALIDATION_FAILED")

    with pytest.raises(
        AdaptivePerturbationCampaignError,
        match="FINAL_SOURCE_REVALIDATION_FAILED",
    ):
        _run_adaptive_perturbation_campaign_with_runners(
            WORKSPACE,
            policy=policy,
            session_runner=session_runner,
            revalidator=reject,
        )

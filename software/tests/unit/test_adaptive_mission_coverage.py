from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from rocell.application import (
    AdaptiveMissionCoverageError,
    AdaptiveMissionCoveragePolicy,
    BoardPoseCorrectionStatus,
    bootstrap_virtual_workcell,
    mission_semantic_routes,
)
from rocell.application.adaptive_mission_coverage import (
    _run_adaptive_mission_coverage_with_runners,
)
from rocell.models.actions import PressKey, TapPhoneTarget


WORKSPACE = Path(__file__).resolve().parents[3]


def _target_id(plan: Any) -> str:
    physical = tuple(
        action.key_id if isinstance(action, PressKey) else action.target_id
        for action in plan.actions
        if isinstance(action, (PressKey, TapPhoneTarget))
    )
    assert len(physical) == 1
    return physical[0]


class _FakeAdaptiveReport:
    def __init__(self, plan: Any, *, fail: bool = False) -> None:
        target = _target_id(plan)
        self.executions = tuple(object() for _ in range(8))
        self.vision_attempts = (
            SimpleNamespace(
                decision=SimpleNamespace(status=BoardPoseCorrectionStatus.NO_CHANGE)
            ),
        )
        self.correction_installations: tuple[object, ...] = ()
        self.contact_attempts = (
            SimpleNamespace(
                semantic_target=f"{plan.device.value}:{target}",
                accepted=not fail,
            ),
        )
        self.pipeline_completed = not fail
        self.outcome_verified = not fail
        self.ended_at_park = not fail
        self.arm_document = {
            "lifecycle": "CLOSED",
            "authority": {
                "hardware_accessed": False,
                "hardware_commands_generated": 0,
            },
        }
        self.fault_reason = "INJECTED_TARGET_FAILURE" if fail else None
        self.status = (
            "ADAPTIVE_VIRTUAL_SESSION_FAULTED"
            if fail
            else "ADAPTIVE_VIRTUAL_SESSION_COMPLETE_WITH_PHYSICAL_HOLDS"
        )
        self.report_hash = hashlib.sha256(
            f"{plan.device.value}:{target}:{fail}".encode("utf-8")
        ).hexdigest()

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "test.adaptive-report.v1",
            "status": self.status,
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


def _run_fake(*, failing_target: str | None = None, policy: AdaptiveMissionCoveragePolicy | None = None):
    calls: list[str] = []
    revalidations: list[str] = []
    selected_policy = policy or AdaptiveMissionCoveragePolicy()

    def session_runner(_bootstrap: Any, plan: Any, *_args: Any, **_kwargs: Any) -> Any:
        assert _kwargs["policy"] is selected_policy.session_policy
        target = _target_id(plan)
        calls.append(target)
        return _FakeAdaptiveReport(plan, fail=target == failing_target)

    def revalidator(bootstrap: Any) -> None:
        revalidations.append(bootstrap.bootstrap_hash)

    report = _run_adaptive_mission_coverage_with_runners(
        WORKSPACE,
        policy=selected_policy,
        session_runner=session_runner,
        revalidator=revalidator,
    )
    return report, calls, revalidations


def test_semantic_catalog_is_exactly_46_keyboard_plus_29_phone() -> None:
    bootstrap = bootstrap_virtual_workcell(WORKSPACE)
    routes = mission_semantic_routes(bootstrap.context)

    assert len(routes) == 75
    assert sum(route.device == "keyboard" for route in routes) == 46
    assert sum(route.device == "phone" for route in routes) == 29
    assert len({(route.device, route.target_id) for route in routes}) == 75
    assert all(len(route.semantic_character) == 1 for route in routes)


def test_complete_fake_catalog_is_hash_bound_zero_authority_and_deterministic() -> None:
    first, calls, revalidations = _run_fake()
    second, second_calls, _ = _run_fake()

    assert calls == second_calls
    assert len(calls) == 75
    assert len(first.chunks) == 15
    assert first.complete_catalog_evidence is True
    assert first.all_routes_accepted is True
    assert first.status == "ADAPTIVE_MISSION_COVERAGE_PASS_WITH_PHYSICAL_HOLDS"
    assert first.resource_usage == {
        "route_count": 75,
        "execution_count": 600,
        "capture_count": 75,
        "correction_installation_count": 0,
        "contact_count": 75,
    }
    assert revalidations == [first.source["bootstrap_sha256"]]
    assert first.to_dict() == second.to_dict()
    assert first.report_hash == second.report_hash
    serialized = json.dumps(first.to_dict(), sort_keys=True)
    assert '"semantic_character"' not in serialized
    assert first.to_dict()["authority"]["hardware_commands_generated"] == 0  # type: ignore[index]
    assert first.to_dict()["summary"]["physical_ready"] is False  # type: ignore[index]


def test_acceptance_binds_namespaced_contact_and_safe_vision_terminal_state() -> None:
    report, _calls, _ = _run_fake()
    route = report.routes[0]

    assert route.expected_contact_target == f"{route.device}:{route.target_id}"
    assert route.observed_contact_targets == (route.expected_contact_target,)
    assert route.vision_converged is True
    assert route.accepted is True

    corrected = replace(
        route,
        decision_statuses=("APPLY", "NO_CHANGE"),
        capture_count=2,
        correction_installation_count=1,
    )
    assert corrected.vision_converged is True
    assert corrected.accepted is True

    assert replace(
        route, observed_contact_targets=(route.target_id,)
    ).accepted is False
    assert replace(
        route,
        decision_statuses=("APPLY",),
        correction_installation_count=1,
    ).accepted is False


def test_coverage_hash_binds_shared_wide_fov_simulation_policy() -> None:
    policy = AdaptiveMissionCoveragePolicy()
    correction = policy.session_policy.correction_policy
    document = policy.to_dict()

    assert correction.translation_deadband_mm == 2.5
    assert correction.maximum_translation_delta_mm == 15.0
    assert correction.maximum_inlier_reprojection_rmse_px == 5.0
    assert policy.session_policy.maximum_execution_waypoints == 128
    assert policy.session_policy.camera_quality_policy is not None
    assert (
        document["session_policy"]["policy_sha256"]  # type: ignore[index]
        == policy.session_policy.policy_hash
    )


def test_one_target_failure_is_retained_without_hiding_later_routes() -> None:
    report, calls, _ = _run_fake(failing_target="A")

    assert len(calls) == 75
    assert report.complete_catalog_evidence is True
    assert report.all_routes_accepted is False
    assert report.status == "ADAPTIVE_MISSION_COVERAGE_GAPS_REPORTED"
    rejected = tuple(route for route in report.routes if not route.accepted)
    assert len(rejected) == 1
    assert rejected[0].target_id == "A"
    assert rejected[0].fault_reason == "INJECTED_TARGET_FAILURE"


def test_report_source_is_recursively_detached_and_immutable() -> None:
    report, _calls, _ = _run_fake()

    with pytest.raises(TypeError):
        report.source["manifest_id"] = "forged"  # type: ignore[index]
    authority = report.source["authority"]
    assert isinstance(authority, dict) is False
    with pytest.raises(TypeError):
        authority["hardware_accessed"] = True  # type: ignore[index]


def test_incomplete_or_reordered_catalog_fails_closed() -> None:
    report, _calls, _ = _run_fake()
    incomplete = replace(report, chunks=report.chunks[:-1])
    assert incomplete.complete_catalog_evidence is False
    assert incomplete.all_routes_accepted is False
    assert incomplete.status == "ADAPTIVE_MISSION_COVERAGE_INCOMPLETE_FAIL_CLOSED"

    first_chunk = report.chunks[0]
    reordered = replace(
        report,
        chunks=(
            replace(first_chunk, routes=tuple(reversed(first_chunk.routes))),
            *report.chunks[1:],
        ),
    )
    assert reordered.complete_catalog_evidence is False
    assert reordered.all_routes_accepted is False


def test_coverage_evidence_rejects_contradictory_or_mutable_shapes() -> None:
    report, _calls, _ = _run_fake()
    route = report.routes[0]

    with pytest.raises(AdaptiveMissionCoverageError, match="contact count"):
        replace(route, contact_count=0)
    assert replace(route, execution_count=128).execution_count == 128
    with pytest.raises(AdaptiveMissionCoverageError, match="execution_count"):
        replace(route, execution_count=129)
    with pytest.raises(AdaptiveMissionCoverageError, match="immutable status tuple"):
        replace(route, decision_statuses=["NO_CHANGE"])  # type: ignore[arg-type]
    with pytest.raises(AdaptiveMissionCoverageError, match="exactly 46"):
        replace(report, keyboard_target_ids=report.keyboard_target_ids[:-1])
    with pytest.raises(AdaptiveMissionCoverageError, match="chunks are invalid"):
        replace(report, chunks=list(report.chunks))  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("orchestration_chunk_size", 0),
        ("orchestration_chunk_size", 16),
        ("maximum_total_executions", 0),
        ("maximum_total_executions", 9601),
        ("maximum_total_captures", 151),
        ("maximum_total_contacts", 76),
    ),
)
def test_policy_rejects_unbounded_values(field: str, value: int) -> None:
    with pytest.raises(AdaptiveMissionCoverageError):
        AdaptiveMissionCoveragePolicy(**{field: value})


def test_actual_resource_cap_stops_before_a_second_route() -> None:
    calls: list[str] = []

    def session_runner(_bootstrap: Any, plan: Any, *_args: Any, **_kwargs: Any) -> Any:
        calls.append(_target_id(plan))
        return _FakeAdaptiveReport(plan)

    with pytest.raises(
        AdaptiveMissionCoverageError,
        match="execution count exceeded policy cap",
    ):
        _run_adaptive_mission_coverage_with_runners(
            WORKSPACE,
            policy=AdaptiveMissionCoveragePolicy(maximum_total_executions=1),
            session_runner=session_runner,
        )
    assert len(calls) == 1


def test_final_source_revalidation_failure_aborts_report() -> None:
    def session_runner(_bootstrap: Any, plan: Any, *_args: Any, **_kwargs: Any) -> Any:
        return _FakeAdaptiveReport(plan)

    def revalidator(_bootstrap: Any) -> None:
        raise AdaptiveMissionCoverageError("SOURCE_MUTATED_DURING_CAMPAIGN")

    with pytest.raises(
        AdaptiveMissionCoverageError,
        match="SOURCE_MUTATED_DURING_CAMPAIGN",
    ):
        _run_adaptive_mission_coverage_with_runners(
            WORKSPACE,
            policy=AdaptiveMissionCoveragePolicy(),
            session_runner=session_runner,
            revalidator=revalidator,
        )

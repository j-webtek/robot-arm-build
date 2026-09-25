from __future__ import annotations

from dataclasses import replace
import hashlib
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from rocell.application import (
    MissionRouteCoverageError,
    MissionRouteCoveragePolicy,
    ReachStudyInput,
    SimulationContext,
    TrajectorySimulationPolicy,
    default_reach_study_inputs,
    load_simulation_context,
    run_mission_route_coverage,
)
from rocell.models.actions import ActionPlan, PressKey, TapPhoneTarget
from rocell.motion import MotionPhase


WORKSPACE = Path(__file__).resolve().parents[3]
PARK_XY = (290.0, 10.0)
_ENDPOINT_PHASES = (
    MotionPhase.PARK,
    MotionPhase.TRANSIT,
    MotionPhase.HOVER,
    MotionPhase.APPROACH,
    MotionPhase.CONTACT,
    MotionPhase.RETRACT,
    MotionPhase.TRANSIT,
    MotionPhase.PARK,
)


@pytest.fixture(scope="module")
def simulation_context() -> SimulationContext:
    return load_simulation_context(
        WORKSPACE,
        WORKSPACE / "software/config/system_manifest.json",
    )


def _provenance(
    context: SimulationContext,
    study: ReachStudyInput,
) -> tuple[tuple[str, object], ...]:
    return (
        ("snapshot_hash", context.snapshot.snapshot_hash),
        ("simulation_bundle_id", context.bundle_lock.bundle_id),
        ("simulation_bundle_sha256", context.bundle_lock.source_lock_sha256),
        ("hardware_profile_hash", context.hardware_profile.profile_hash),
        ("target_profile_sha256", context.targets.content_sha256),
        ("model_sha256", context.scenario.model_sha256),
        ("loaded_model_sha256", context.scenario.model_sha256),
        ("loaded_model_bytes", 12345),
        ("alignment_report_hash", context.alignment.report_hash),
        ("study_input_id", study.study_input_id),
        ("ik_solver_implementation", "canonical.fake.Ik"),
        ("ik_solver_algorithm_version", "TEST_CANONICAL"),
        (
            "task_jacobian_conditioning_implementation",
            "canonical.fake.conditioning",
        ),
        (
            "task_jacobian_conditioning_algorithm_version",
            "TEST_CONDITIONING",
        ),
        (
            "task_jacobian_conditioning_solver_mode",
            "CANONICAL_IN_PACKAGE_IMPLEMENTATION",
        ),
        ("task_jacobian_numerical_rank_gate", "FULL_COLUMN_NUMERICAL_RANK_ONLY"),
        ("normalized_task_jacobian_conditioning_gate_enabled", False),
        ("implementation_bundle_sha256", "a" * 64),
        ("rocell_source_tree_sha256", "b" * 64),
        ("rocell_runtime_version", "test"),
        ("ik_options", (("max_attempts", 4), ("max_iterations_per_attempt", 45))),
    )


class _FakeTrajectoryReport:
    def __init__(
        self,
        *,
        context: SimulationContext,
        plan: ActionPlan,
        study: ReachStudyInput,
        policy: TrajectorySimulationPolicy,
        failed: bool = False,
        provenance_suffix: str = "",
    ) -> None:
        target_id = _target_id(plan)
        device = plan.device.value
        semantic_target = f"{device}:{target_id}"
        waypoints = tuple(
            SimpleNamespace(
                sequence=index,
                phase=phase,
                phase_endpoint=True,
                source_check_id=(None if index == 0 else f"check-{index}"),
                inherited_collision_ids=(),
            )
            for index, phase in enumerate(_ENDPOINT_PHASES)
        )
        failure_index = 3 if failed else None
        result_count = 4 if failed else len(waypoints)
        results = []
        for index in range(result_count):
            rejected = index == failure_index
            conditioning = SimpleNamespace(
                numerical_rank=5,
                normalized_minimum_singular_value=0.05 + index / 1_000.0,
                condition_number=20.0 - index / 10.0,
                finite_difference_fk_evaluations=11,
            )
            results.append(
                SimpleNamespace(
                    waypoint_sequence=index,
                    phase=_ENDPOINT_PHASES[index],
                    semantic_target=semantic_target,
                    accepted=not rejected,
                    failure_reason=("IK_NO_CONVERGED_SOLUTION" if rejected else None),
                    position_error_mm=(2.0 if rejected else 0.01),
                    alignment_error_rad=(0.1 if rejected else 0.001),
                    minimum_normalized_arm_joint_margin=(
                        0.02 if rejected else 0.20 - index / 100.0
                    ),
                    solver_weighted_task_jacobian=conditioning,
                    maximum_joint_delta_rad=(None if index == 0 else 0.10),
                )
            )
        round_ = SimpleNamespace(
            waypoints=waypoints,
            joint_results=tuple(results),
            all_waypoints_accepted=not failed,
        )
        provenance = dict(_provenance(context, study))
        provenance["plan_hash"] = plan.plan_hash
        provenance["plan_profile_id"] = plan.profile_id
        if provenance_suffix:
            provenance["implementation_bundle_sha256"] = hashlib.sha256(
                provenance_suffix.encode("utf-8")
            ).hexdigest()
        self.source_provenance = tuple(provenance.items())
        self.study_input = study
        self.policy = policy
        self.park_xy_board_mm = policy.park_xy_board_mm
        self.device = device
        self.route_target_ids = (target_id,)
        self.tool_length_mm = (
            study.keyboard_tool_length_mm
            if device == "keyboard"
            else study.phone_tool_length_mm
        )
        self.rounds = (round_,)
        self.final_round = round_
        self.geometry_all_checks_passed = True
        self.total_ik_solves = len(results)
        self.task_jacobian_evaluated_waypoint_count = len(results)
        self.total_task_jacobian_fk_evaluations = len(results) * 11
        self.termination_reason = (
            "REFINEMENT_ROUND_LIMIT_EXHAUSTED"
            if failed
            else "ALL_DENSIFIED_WAYPOINTS_ACCEPTED"
        )
        self.status = (
            "DISCRETE_SEQUENTIAL_IK_WAYPOINT_DIAGNOSTIC_GAPS_REPORTED"
            if failed
            else "DISCRETE_SEQUENTIAL_IK_WAYPOINT_DIAGNOSTIC_PASS_WITH_UNSUPPORTED_CHECKS"
        )
        self.report_hash = hashlib.sha256(
            f"{device}:{target_id}:{failed}:{provenance_suffix}".encode("utf-8")
        ).hexdigest()


def _target_id(plan: ActionPlan) -> str:
    targets = tuple(
        action.key_id if isinstance(action, PressKey) else action.target_id
        for action in plan.actions
        if isinstance(action, (PressKey, TapPhoneTarget))
    )
    assert len(targets) == 1
    return targets[0]


def test_policy_is_hashed_and_hard_bounded() -> None:
    policy = MissionRouteCoveragePolicy()
    document = policy.to_dict()

    assert len(policy.policy_hash) == 64
    assert policy.planned_maximum_waypoint_records == 9_600
    assert policy.planned_maximum_ik_solves == 9_600
    assert policy.planned_maximum_task_jacobian_fk_evaluations == 105_600
    assert document["maximum_targets_per_route"] == 1
    assert document["expected_catalog"] == {
        "keyboard": 46,
        "phone": 29,
        "total": 75,
    }
    downstream = policy.trajectory_policy(PARK_XY)
    assert downstream.maximum_route_targets == 1
    assert downstream.park_xy_board_mm == PARK_XY

    with pytest.raises(MissionRouteCoverageError, match="orchestration_chunk_size"):
        MissionRouteCoveragePolicy(orchestration_chunk_size=17)
    with pytest.raises(MissionRouteCoverageError, match="maximum_refinement_rounds"):
        MissionRouteCoveragePolicy(maximum_refinement_rounds=2)
    with pytest.raises(MissionRouteCoverageError, match="maximum_waypoints_per_round"):
        MissionRouteCoveragePolicy(maximum_waypoints_per_round=65)


def test_complete_catalog_uses_75_independent_routes_and_compact_chunks(
    simulation_context: SimulationContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import rocell.application.mission_route_coverage as coverage

    study = default_reach_study_inputs(simulation_context)[0]
    calls: list[tuple[ActionPlan, TrajectorySimulationPolicy]] = []

    def fake_run(
        context: SimulationContext,
        plan: ActionPlan,
        selected_study: ReachStudyInput,
        policy: TrajectorySimulationPolicy,
    ) -> Any:
        calls.append((plan, policy))
        return _FakeTrajectoryReport(
            context=context,
            plan=plan,
            study=selected_study,
            policy=policy,
        )

    monkeypatch.setattr(coverage, "run_trajectory_simulation", fake_run)
    report = run_mission_route_coverage(
        simulation_context,
        study,
        PARK_XY,
    )
    document = report.to_dict()

    assert report.complete_catalog_evidence is True
    assert report.all_routes_accepted is True
    assert report.status.endswith("PASS_WITH_UNSUPPORTED_CHECKS")
    assert len(report.routes) == 75
    assert len(report.chunks) == 10
    assert len(calls) == 75
    assert tuple(route.route_ordinal for route in report.routes) == tuple(range(75))
    assert tuple(route.target_id for route in report.routes[:46]) == tuple(
        sorted(simulation_context.targets.keyboard_targets)
    )
    assert tuple(route.target_id for route in report.routes[46:]) == tuple(
        sorted(simulation_context.targets.phone_targets)
    )
    assert any(route.target_id == "key_a" for route in report.routes)
    assert all(_target_id(plan) for plan, _ in calls)
    assert all(policy.maximum_route_targets == 1 for _, policy in calls)
    assert all(policy.park_xy_board_mm == PARK_XY for _, policy in calls)
    assert document["hardware_commands_generated"] == 0
    assert document["execution_authorized"] is False
    assert document["contact_authorized"] is False
    assert document["sequence_claim"].startswith("NONE_")
    assert document["device_summary"]["keyboard"]["accepted_route_count"] == 46
    assert document["device_summary"]["phone"]["accepted_route_count"] == 29
    first_route = document["chunks"][0]["routes"][0]
    assert "waypoints" not in first_route
    assert "rounds" not in first_route
    assert len(report.report_hash) == 64


def test_target_failure_is_retained_and_does_not_suppress_later_routes(
    simulation_context: SimulationContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import rocell.application.mission_route_coverage as coverage

    study = default_reach_study_inputs(simulation_context)[0]
    called_targets: list[str] = []

    def fake_run(
        context: SimulationContext,
        plan: ActionPlan,
        selected_study: ReachStudyInput,
        policy: TrajectorySimulationPolicy,
    ) -> Any:
        target_id = _target_id(plan)
        called_targets.append(target_id)
        return _FakeTrajectoryReport(
            context=context,
            plan=plan,
            study=selected_study,
            policy=policy,
            failed=plan.device.value == "phone" and target_id == "key_a",
        )

    monkeypatch.setattr(coverage, "run_trajectory_simulation", fake_run)
    report = run_mission_route_coverage(
        simulation_context,
        study,
        PARK_XY,
    )

    assert len(called_targets) == 75
    assert report.complete_catalog_evidence is True
    assert report.all_routes_accepted is False
    assert report.status.endswith("GAPS_REPORTED")
    key_a = next(route for route in report.routes if route.target_id == "key_a")
    assert key_a.ordered_single_target_route_planned is True
    assert key_a.contact_endpoint_planned is True
    assert key_a.contact_endpoint_evaluated is False
    assert key_a.first_failure is not None
    assert key_a.first_failure.reason == "IK_NO_CONVERGED_SOLUTION"
    assert key_a.first_failure.phase == "APPROACH"
    assert key_a.minimum_normalized_arm_joint_margin == pytest.approx(0.02)
    phone = report.to_dict()["device_summary"]["phone"]
    assert phone["accepted_route_count"] == 28
    assert phone["failure_reason_counts"] == {"IK_NO_CONVERGED_SOLUTION": 1}
    assert phone["first_failure_phase_counts"] == {"APPROACH": 1}


def test_wrong_catalog_fails_before_any_route_execution(
    simulation_context: SimulationContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import rocell.application.mission_route_coverage as coverage

    phone_targets = dict(simulation_context.targets.phone_targets)
    phone_targets.pop("key_a")
    changed = replace(
        simulation_context,
        targets=replace(
            simulation_context.targets,
            phone_targets=phone_targets,
        ),
    )
    calls = 0

    def fake_run(*args: object, **kwargs: object) -> Any:
        nonlocal calls
        calls += 1
        raise AssertionError("route execution must not start")

    # Isolate the service's exact-catalog pre-execution gate from the broader
    # context revalidator, which independently rejects this synthetic drift.
    monkeypatch.setattr(coverage, "revalidate_simulation_context", lambda context: None)
    monkeypatch.setattr(coverage, "run_trajectory_simulation", fake_run)
    with pytest.raises(MissionRouteCoverageError, match="46-key.*29-phone"):
        run_mission_route_coverage(
            changed,
            default_reach_study_inputs(simulation_context)[0],
            PARK_XY,
        )
    assert calls == 0


def test_mid_run_source_provenance_change_aborts_complete_report(
    simulation_context: SimulationContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import rocell.application.mission_route_coverage as coverage

    study = default_reach_study_inputs(simulation_context)[0]
    calls = 0

    def fake_run(
        context: SimulationContext,
        plan: ActionPlan,
        selected_study: ReachStudyInput,
        policy: TrajectorySimulationPolicy,
    ) -> Any:
        nonlocal calls
        calls += 1
        return _FakeTrajectoryReport(
            context=context,
            plan=plan,
            study=selected_study,
            policy=policy,
            provenance_suffix="changed" if calls == 2 else "",
        )

    monkeypatch.setattr(coverage, "run_trajectory_simulation", fake_run)
    with pytest.raises(MissionRouteCoverageError, match="provenance changed"):
        run_mission_route_coverage(
            simulation_context,
            study,
            PARK_XY,
        )
    assert calls == 2


@pytest.mark.parametrize(
    ("drift", "message"),
    (
        ("policy", "exact mission route policy"),
        ("plan_hash", "plan hash differs"),
        ("plan_profile_id", "semantic profile differs"),
        ("tool_length", "route tool differs"),
    ),
)
def test_each_trajectory_is_bound_to_the_requested_plan_policy_and_tool(
    simulation_context: SimulationContext,
    monkeypatch: pytest.MonkeyPatch,
    drift: str,
    message: str,
) -> None:
    import rocell.application.mission_route_coverage as coverage

    study = default_reach_study_inputs(simulation_context)[0]
    calls = 0

    def fake_run(
        context: SimulationContext,
        plan: ActionPlan,
        selected_study: ReachStudyInput,
        policy: TrajectorySimulationPolicy,
    ) -> Any:
        nonlocal calls
        calls += 1
        report = _FakeTrajectoryReport(
            context=context,
            plan=plan,
            study=selected_study,
            policy=policy,
        )
        if drift == "policy":
            report.policy = replace(policy, maximum_cartesian_step_mm=31.0)
        elif drift in {"plan_hash", "plan_profile_id"}:
            provenance = dict(report.source_provenance)
            provenance[drift] = "drifted"
            report.source_provenance = tuple(provenance.items())
        elif drift == "tool_length":
            report.tool_length_mm += 1.0
        else:  # pragma: no cover - parameter table is closed above
            raise AssertionError(drift)
        return report

    monkeypatch.setattr(coverage, "run_trajectory_simulation", fake_run)
    with pytest.raises(MissionRouteCoverageError, match=message):
        run_mission_route_coverage(
            simulation_context,
            study,
            PARK_XY,
        )
    assert calls == 1

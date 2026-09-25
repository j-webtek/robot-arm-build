from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest

from rocell.application.bootstrap import bootstrap_virtual_workcell
from rocell.application.dense_route_schedule import (
    CONTROLLER_JOINT_INTERPRETATION,
    DenseRouteSchedule,
    DenseRouteScheduleError,
    build_dense_route_schedule,
)
from rocell.application.semantic_step_schedule import build_semantic_step_schedule
from rocell.application.trajectory_simulation import (
    TrajectorySimulationPolicy,
    TrajectorySimulationReport,
    run_trajectory_simulation,
)
from rocell.models.actions import ActionPlan
from rocell.motion import MotionPhase
from rocell.simulation.t104_runtime import InMemoryT104Runtime
from rocell.simulation.virtual_profile import (
    VirtualProfileContext,
    load_virtual_commissioning_profile,
)
from rocell.typing.development_profiles import compile_development_text


WORKSPACE = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def trajectories() -> dict[str, tuple[object, TrajectorySimulationReport]]:
    bootstrap = bootstrap_virtual_workcell(WORKSPACE)
    profile = load_virtual_commissioning_profile(
        cast(VirtualProfileContext, bootstrap.context)
    )
    park = profile.park_point_board
    policy = TrajectorySimulationPolicy(
        maximum_cartesian_step_mm=30.0,
        maximum_joint_step_rad=0.35,
        minimum_normalized_arm_joint_margin=0.01,
        maximum_refinement_rounds=2,
        maximum_waypoints_per_round=256,
        maximum_total_ik_solves=512,
        maximum_route_targets=8,
        park_xy_board_mm=(park.x, park.y),
    )
    result: dict[str, tuple[object, TrajectorySimulationReport]] = {}
    for device, text in (("keyboard", "test"), ("phone", "test.")):
        plan = compile_development_text(device, text)
        result[device] = (
            plan,
            run_trajectory_simulation(
                bootstrap.context,
                plan,
                profile.study_input,
                policy,
            ),
        )
    return result


@pytest.fixture(scope="module")
def schedules(
    trajectories: dict[str, tuple[object, TrajectorySimulationReport]],
) -> dict[str, DenseRouteSchedule]:
    result: dict[str, DenseRouteSchedule] = {}
    for device, (untyped_plan, trajectory) in trajectories.items():
        # The fixture keeps its map concise; the compiler result is verified by
        # the scheduler before any trajectory field is consumed.
        plan = cast(ActionPlan, untyped_plan)
        result[device] = build_dense_route_schedule(
            mission_id=f"{device}-test-mission-v2",
            controller_session_id=f"{device}-t104-session-v2",
            semantic_schedule=build_semantic_step_schedule(plan),
            trajectory=trajectory,
        )
    return result

def test_keyboard_binds_every_one_of_47_post_park_waypoints(
    schedules: dict[str, DenseRouteSchedule],
) -> None:
    schedule = schedules["keyboard"]
    assert schedule.route_waypoint_count == 48
    assert schedule.command_count == 47
    assert len(schedule.contact_slices) == 4
    assert [item.semantic_step_ordinal for item in schedule.contact_slices] == [0, 1, 2, 3]
    assert [item.contact_occurrence_ordinal for item in schedule.contact_slices] == [0, 1, 2, 3]
    assert [item.target_id for item in schedule.contact_slices] == ["T", "E", "S", "T"]


def test_phone_keeps_observation_ordinal_out_of_five_contact_groups(
    schedules: dict[str, DenseRouteSchedule],
) -> None:
    schedule = schedules["phone"]
    assert schedule.route_waypoint_count == 61
    assert schedule.command_count == 60
    assert len(schedule.contact_slices) == 5
    assert [item.semantic_step_ordinal for item in schedule.contact_slices] == [1, 2, 3, 4, 5]
    assert [item.contact_occurrence_ordinal for item in schedule.contact_slices] == [0, 1, 2, 3, 4]
    assert all(item.semantic_step_ordinal != 0 for item in schedule.commands)


@pytest.mark.parametrize("device", ["keyboard", "phone"])
def test_four_ordinals_and_pose_chain_are_explicit_and_dense(
    schedules: dict[str, DenseRouteSchedule], device: str
) -> None:
    schedule = schedules[device]
    assert [item.authorization_command_ordinal for item in schedule.commands] == list(
        range(schedule.command_count)
    )
    assert [item.route_waypoint_ordinal for item in schedule.commands] == list(
        range(1, schedule.route_waypoint_count)
    )
    assert [item.command.sequence_ordinal for item in schedule.commands] == list(
        range(schedule.command_count)
    )
    assert schedule.runtime_config.schedule_sha256
    assert schedule.controller_joint_interpretation == CONTROLLER_JOINT_INTERPRETATION


@pytest.mark.parametrize("device", ["keyboard", "phone"])
def test_in_memory_runtime_executes_exact_full_dense_schedule(
    schedules: dict[str, DenseRouteSchedule], device: str
) -> None:
    schedule = schedules[device]
    runtime = InMemoryT104Runtime(schedule.runtime_config)
    receipts = runtime.execute_many(tuple(item.command for item in schedule.commands))
    assert len(receipts) == schedule.command_count
    assert all(receipt.success and receipt.settled for receipt in receipts)
    state = runtime.state_receipt()
    assert state.terminal is True
    assert state.completed_command_count == schedule.command_count
    assert state.attempted_command_count == schedule.command_count
    assert state.next_sequence_ordinal == schedule.command_count


@pytest.mark.parametrize("device", ["keyboard", "phone"])
def test_only_last_contact_owns_contiguous_return_to_park_tail(
    schedules: dict[str, DenseRouteSchedule], device: str
) -> None:
    schedule = schedules[device]
    assert [item.includes_mission_tail for item in schedule.contact_slices] == [
        *([False] * (len(schedule.contact_slices) - 1)),
        True,
    ]
    tail = [item for item in schedule.commands if item.mission_tail]
    assert tail
    assert {item.phase for item in tail} <= {MotionPhase.TRANSIT, MotionPhase.PARK}
    assert tail[-1].phase is MotionPhase.PARK
    assert tail[-1].phase_endpoint is True


def test_contact_slices_bind_exact_hover_contact_and_retract_endpoints(
    schedules: dict[str, DenseRouteSchedule],
) -> None:
    schedule = schedules["keyboard"]
    by_route = {item.route_waypoint_ordinal: item for item in schedule.commands}
    for slice_ in schedule.contact_slices:
        assert by_route[slice_.final_hover_route_waypoint_ordinal].phase is MotionPhase.HOVER
        assert by_route[slice_.contact_route_waypoint_ordinal].phase is MotionPhase.CONTACT
        assert by_route[slice_.final_retract_route_waypoint_ordinal].phase is MotionPhase.RETRACT
        assert by_route[slice_.contact_route_waypoint_ordinal].phase_endpoint is True


def test_trajectory_attestation_rejects_a_relabelled_contact_endpoint(
    schedules: dict[str, DenseRouteSchedule],
    trajectories: dict[str, tuple[object, TrajectorySimulationReport]],
) -> None:
    schedule = schedules["keyboard"]
    first = schedule.contact_slices[0]
    wrong_approach = next(
        item.route_waypoint_ordinal
        for item in schedule.commands
        if item.contact_occurrence_ordinal == 0
        and item.phase is MotionPhase.APPROACH
        and item.phase_endpoint
    )
    forged_slice = replace(
        first,
        contact_route_waypoint_ordinal=wrong_approach,
    )
    forged_schedule = replace(
        schedule,
        contact_slices=(forged_slice, *schedule.contact_slices[1:]),
    )
    with pytest.raises(
        DenseRouteScheduleError,
        match="exact trajectory phase endpoints",
    ):
        forged_schedule.assert_matches_trajectory(trajectories["keyboard"][1])


def test_trajectory_attestation_rejects_relabelled_mission_tail_semantics(
    schedules: dict[str, DenseRouteSchedule],
    trajectories: dict[str, tuple[object, TrajectorySimulationReport]],
) -> None:
    schedule = schedules["keyboard"]
    tail_index = next(
        index for index, item in enumerate(schedule.commands) if item.mission_tail
    )
    forged_binding = replace(
        schedule.commands[tail_index],
        semantic_step_ordinal=511,
    )
    forged_commands = list(schedule.commands)
    forged_commands[tail_index] = forged_binding
    forged_schedule = replace(schedule, commands=tuple(forged_commands))
    with pytest.raises(
        DenseRouteScheduleError,
        match="trajectory waypoint/result",
    ):
        forged_schedule.assert_matches_trajectory(trajectories["keyboard"][1])


def test_default_unreachable_park_trajectory_is_rejected(
    trajectories: dict[str, tuple[object, TrajectorySimulationReport]],
) -> None:
    plan = cast(ActionPlan, trajectories["keyboard"][0])
    bootstrap = bootstrap_virtual_workcell(WORKSPACE)
    profile = load_virtual_commissioning_profile(
        cast(VirtualProfileContext, bootstrap.context)
    )
    rejected = run_trajectory_simulation(
        bootstrap.context,
        plan,
        profile.study_input,
    )
    with pytest.raises(DenseRouteScheduleError, match="fully accepted"):
        build_dense_route_schedule(
            mission_id="rejected-route",
            controller_session_id="rejected-session",
            semantic_schedule=build_semantic_step_schedule(plan),
            trajectory=rejected,
        )


def test_source_plan_drift_is_rejected(
    trajectories: dict[str, tuple[object, TrajectorySimulationReport]],
) -> None:
    phone_plan = cast(ActionPlan, trajectories["phone"][0])
    keyboard_trajectory = trajectories["keyboard"][1]
    with pytest.raises(DenseRouteScheduleError, match="device differs"):
        build_dense_route_schedule(
            mission_id="mixed-route",
            controller_session_id="mixed-session",
            semantic_schedule=build_semantic_step_schedule(phone_plan),
            trajectory=keyboard_trajectory,
        )


def test_post_construction_command_mutation_is_detected(
    schedules: dict[str, DenseRouteSchedule],
) -> None:
    schedule = schedules["keyboard"]
    command = schedule.commands[0]
    object.__setattr__(command, "mission_tail", True)
    with pytest.raises(DenseRouteScheduleError):
        command.to_dict()
    # Restore shared module fixture for tests that may run after this one.
    object.__setattr__(command, "mission_tail", False)
    command.validate()


def test_runtime_config_command_tamper_is_rejected_at_schedule_construction(
    schedules: dict[str, DenseRouteSchedule],
) -> None:
    schedule = schedules["phone"]
    wrong_runtime = replace(
        schedule.runtime_config,
        session_id="different-session",
    )
    with pytest.raises(DenseRouteScheduleError, match="runtime configuration differs"):
        replace(schedule, runtime_config=wrong_runtime)


def test_serialized_schedule_repeats_zero_authority(
    schedules: dict[str, DenseRouteSchedule],
) -> None:
    document = schedules["keyboard"].to_dict()
    assert document["simulation_only"] is True
    assert document["physical_authority"] == "ZERO"
    assert document["wire_message_present"] is False
    assert document["hardware_accessed"] is False
    assert document["hardware_commands_generated"] == 0
    assert document["controller_frame_physically_correlated"] is False
    assert len(cast(list[object], document["commands"])) == 47

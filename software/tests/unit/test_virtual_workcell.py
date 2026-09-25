from __future__ import annotations

from dataclasses import FrozenInstanceError
import hashlib

import pytest

from rocell.safety.permit import MotionPermit
from rocell.simulation.virtual_workcell import (
    ContactDisposition,
    ContactEvent,
    ContactRegion,
    MAX_VIRTUAL_FAULT_TRIGGERS,
    VIRTUAL_ARM_JOINT_NAMES,
    VirtualAndroid,
    VirtualArmLifecycle,
    VirtualArmPlant,
    VirtualClock,
    VirtualEventLedger,
    VirtualExecutionEvent,
    VirtualExecutionToken,
    VirtualFaultKind,
    VirtualFaultScript,
    VirtualFaultTrigger,
    VirtualJointWaypoint,
    VirtualKeyboard,
    VirtualLifecycleError,
    VirtualResourceLimitError,
    VirtualValidationError,
    issue_virtual_execution_token,
)


def _digest(character: str) -> str:
    return character * 64


def _token(*, fault_script_hash: str | None = None) -> VirtualExecutionToken:
    return issue_virtual_execution_token(
        context_hash=_digest("1"),
        plan_hash=_digest("2"),
        trajectory_hash=_digest("3"),
        scenario_hash=_digest("4"),
        fault_script_hash=fault_script_hash or _digest("5"),
    )


def _positions(value: float = 0.0) -> dict[str, float]:
    return {name: value for name in VIRTUAL_ARM_JOINT_NAMES}


def _bounds() -> dict[str, tuple[float, float]]:
    return {name: (-3.0, 3.0) for name in VIRTUAL_ARM_JOINT_NAMES}


def _plant(clock: VirtualClock | None = None) -> VirtualArmPlant:
    return VirtualArmPlant(
        token=_token(),
        clock=clock or VirtualClock(),
        initial_joint_positions_rad=_positions(),
        joint_bounds_rad=_bounds(),
    )


def _region(
    region_id: str,
    x0: float,
    x1: float,
    *,
    ui_state: str | None = None,
) -> ContactRegion:
    return ContactRegion(
        region_id=region_id,
        polygon_xy_mm=((x0, 0.0), (x1, 0.0), (x1, 10.0), (x0, 10.0)),
        surface_z_mm=10.0,
        minimum_contact_depth_mm=0.5,
        maximum_contact_depth_mm=2.0,
        required_contact_normal_board=(0.0, 0.0, -1.0),
        maximum_normal_angle_deg=10.0,
        minimum_dwell_ticks=1,
        maximum_dwell_ticks=3,
        required_ui_state=ui_state,
    )


def _contact(
    action_index: int,
    x: float,
    *,
    y: float = 5.0,
    z: float = 9.0,
    normal: tuple[float, float, float] = (0.0, 0.0, -1.0),
    dwell_ticks: int = 2,
    activation_count: int = 1,
) -> ContactEvent:
    return ContactEvent(
        action_index=action_index,
        achieved_board_xyz_mm=(x, y, z),
        achieved_contact_normal_board=normal,
        dwell_ticks=dwell_ticks,
        activation_count=activation_count,
    )


def test_virtual_clock_is_integer_only_monotonic_and_bounded() -> None:
    clock = VirtualClock(10)
    assert clock.tick == 10
    assert clock.advance() == 11
    assert clock.advance(9) == 20
    with pytest.raises(VirtualValidationError):
        clock.advance(0)
    with pytest.raises(VirtualValidationError):
        VirtualClock(True)  # type: ignore[arg-type]
    near_limit = VirtualClock((1 << 63) - 2)
    near_limit.advance()
    with pytest.raises(VirtualResourceLimitError):
        near_limit.advance()
    assert clock.to_dict()["authority"]["hardware_commands_generated"] == 0  # type: ignore[index]


def test_fault_script_is_immutable_hash_bound_and_consumes_exactly_once() -> None:
    trigger = VirtualFaultTrigger(
        "miss-a",
        VirtualFaultKind.KEYBOARD_MISSED_CONTACT,
        "keyboard",
        "contact",
        occurrence=2,
        action_index=7,
        target_id="A",
    )
    original = VirtualFaultScript("faults", (trigger,))
    assert original.definition_hash == VirtualFaultScript("faults", (trigger,)).definition_hash

    missed, unchanged = original.match_once(
        component="keyboard",
        operation="contact",
        occurrence=1,
        action_index=7,
        target_id="A",
    )
    assert missed is None
    assert unchanged is original

    matched, consumed = original.match_once(
        component="keyboard",
        operation="contact",
        occurrence=2,
        action_index=7,
        target_id="A",
    )
    assert matched == trigger
    assert original.consumed_trigger_ids == frozenset()
    assert consumed.consumed_trigger_ids == frozenset({"miss-a"})
    assert consumed.definition_hash == original.definition_hash
    assert consumed.state_hash != original.state_hash

    repeated, same_consumed = consumed.match_once(
        component="keyboard",
        operation="contact",
        occurrence=2,
        action_index=7,
        target_id="A",
    )
    assert repeated is None
    assert same_consumed is consumed
    with pytest.raises(FrozenInstanceError):
        trigger.occurrence = 3  # type: ignore[misc]


def test_fault_script_rejects_duplicate_selectors_and_resource_excess() -> None:
    first = VirtualFaultTrigger(
        "one", VirtualFaultKind.ARM_STALL, "arm", "execute", waypoint_sequence=1
    )
    duplicate = VirtualFaultTrigger(
        "two", VirtualFaultKind.ARM_FEEDBACK_STALE, "arm", "execute", waypoint_sequence=1
    )
    with pytest.raises(VirtualValidationError, match="selectors"):
        VirtualFaultScript("duplicate", (first, duplicate))

    many = tuple(
        VirtualFaultTrigger(
            f"fault-{index}",
            VirtualFaultKind.ARM_STALL,
            "arm",
            "execute",
            occurrence=index + 1,
        )
        for index in range(MAX_VIRTUAL_FAULT_TRIGGERS + 1)
    )
    with pytest.raises(VirtualResourceLimitError):
        VirtualFaultScript("too-many", many)


def test_virtual_token_is_factory_only_hash_bound_and_not_a_motion_permit() -> None:
    token = _token()
    assert token.bindings == {
        "context_hash": _digest("1"),
        "plan_hash": _digest("2"),
        "trajectory_hash": _digest("3"),
        "scenario_hash": _digest("4"),
        "fault_script_hash": _digest("5"),
    }
    assert token.token_hash == _token().token_hash
    assert not isinstance(token, MotionPermit)
    document = token.to_dict()
    assert document["authority"]["live_motion_authorized"] is False  # type: ignore[index]
    assert document["authority"]["hardware_commands_generated"] == 0  # type: ignore[index]
    with pytest.raises(VirtualValidationError, match="module factory"):
        VirtualExecutionToken(
            _issuer=object(),
            context_hash=_digest("1"),
            plan_hash=_digest("2"),
            trajectory_hash=_digest("3"),
            scenario_hash=_digest("4"),
            fault_script_hash=_digest("5"),
        )


def test_joint_waypoint_requires_exact_five_joint_contract() -> None:
    waypoint = VirtualJointWaypoint.from_mapping(4, _positions(0.5), action_index=9)
    assert tuple(waypoint.positions_by_name) == VIRTUAL_ARM_JOINT_NAMES
    assert waypoint.sequence == 4
    assert waypoint.action_index == 9
    assert len(waypoint.waypoint_hash) == 64

    missing = _positions()
    missing.pop(VIRTUAL_ARM_JOINT_NAMES[-1])
    with pytest.raises(VirtualValidationError, match="joint set mismatch"):
        VirtualJointWaypoint.from_mapping(0, missing)
    with pytest.raises(VirtualValidationError, match="duplicate"):
        VirtualJointWaypoint(
            0,
            (
                (VIRTUAL_ARM_JOINT_NAMES[0], 0.0),
                (VIRTUAL_ARM_JOINT_NAMES[0], 1.0),
                *tuple((name, 0.0) for name in VIRTUAL_ARM_JOINT_NAMES[1:]),
            ),
        )


def test_arm_plant_runs_explicit_lifecycle_and_deterministic_feedback() -> None:
    first_clock = VirtualClock()
    first = _plant(first_clock)
    second = _plant(VirtualClock())
    for plant in (first, second):
        with pytest.raises(VirtualLifecycleError):
            plant.feedback()
        plant.connect()
        plant.reference()
        plant.mark_ready()
        feedback = plant.execute_waypoint(
            VirtualJointWaypoint.from_mapping(0, _positions(0.25), action_index=0)
        )
        assert feedback.lifecycle is VirtualArmLifecycle.EXECUTING
        assert feedback.virtual_commands_executed == 1
        assert feedback.last_action_index == 0
        plant.execute_waypoint(VirtualJointWaypoint.from_mapping(1, _positions(0.5)))
        plant.complete()

    assert first.state_hash == second.state_hash
    assert first.feedback().to_dict() == second.feedback().to_dict()
    assert first.lifecycle_history == (
        VirtualArmLifecycle.CREATED,
        VirtualArmLifecycle.CONNECTED,
        VirtualArmLifecycle.REFERENCED,
        VirtualArmLifecycle.READY,
        VirtualArmLifecycle.EXECUTING,
        VirtualArmLifecycle.COMPLETE,
    )
    assert first.virtual_commands_executed == 2
    document = first.to_dict()
    assert document["controller_cartesian_mapping"] == "NOT_IMPLEMENTED_R_CTRL_UNCORRELATED"
    assert document["hardware_commands_generated"] == 0
    first.close()
    assert first.lifecycle is VirtualArmLifecycle.CLOSED


def test_arm_plant_faults_on_nonmonotonic_or_out_of_bounds_waypoint() -> None:
    plant = _plant()
    plant.connect()
    plant.reference()
    plant.mark_ready()
    plant.execute_waypoint(VirtualJointWaypoint.from_mapping(10, _positions()))
    with pytest.raises(VirtualValidationError, match="increase strictly"):
        plant.execute_waypoint(VirtualJointWaypoint.from_mapping(10, _positions()))
    assert plant.lifecycle is VirtualArmLifecycle.FAULT
    assert plant.fault_reason == "NON_MONOTONIC_WAYPOINT_SEQUENCE"

    out_of_bounds = _plant()
    out_of_bounds.connect()
    out_of_bounds.reference()
    out_of_bounds.mark_ready()
    positions = _positions()
    positions[VIRTUAL_ARM_JOINT_NAMES[0]] = 4.0
    with pytest.raises(VirtualValidationError, match="leaves"):
        out_of_bounds.execute_waypoint(VirtualJointWaypoint.from_mapping(0, positions))
    assert out_of_bounds.lifecycle is VirtualArmLifecycle.FAULT
    assert out_of_bounds.virtual_commands_executed == 0


def test_contact_types_are_immutable_bounded_and_content_addressed() -> None:
    region = _region("KEY_A", 0.0, 10.0)
    event = _contact(0, 5.0)
    assert region.contains_xy((0.0, 5.0))  # Boundaries are included.
    assert len(region.region_hash) == 64
    assert len(event.event_hash) == 64
    assert event.to_dict()["planned_target_supplied"] is False
    assert event.to_dict()["expected_output_supplied"] is False
    with pytest.raises(FrozenInstanceError):
        event.dwell_ticks = 99  # type: ignore[misc]
    with pytest.raises(VirtualValidationError, match="unit vector"):
        _contact(0, 5.0, normal=(0.0, 0.0, -2.0))
    with pytest.raises(VirtualValidationError, match="non-zero area|simple"):
        ContactRegion(
            region_id="BOW_TIE",
            polygon_xy_mm=((0.0, 0.0), (2.0, 2.0), (0.0, 2.0), (2.0, 0.0)),
            surface_z_mm=10.0,
            minimum_contact_depth_mm=0.0,
            maximum_contact_depth_mm=1.0,
            required_contact_normal_board=(0.0, 0.0, -1.0),
            maximum_normal_angle_deg=5.0,
            minimum_dwell_ticks=1,
            maximum_dwell_ticks=2,
        )


def test_keyboard_resolves_output_only_from_achieved_coordinates() -> None:
    outputs = {"KEY_A": "a", "KEY_B": "b"}
    keyboard = VirtualKeyboard(
        regions=(_region("KEY_A", 0.0, 10.0), _region("KEY_B", 10.0, 20.0)),
        output_map=outputs,
    )
    outputs["KEY_A"] = "z"  # Constructor detached the caller's mutable map.

    first = keyboard.apply_contact(_contact(0, 5.0))
    second = keyboard.apply_contact(_contact(1, 15.0, activation_count=2))
    assert first.accepted and first.resolved_target_id == "KEY_A"
    assert first.resolved_output == "a"
    assert first.emitted_output == "a"
    assert second.resolved_target_id == "KEY_B"
    assert second.resolved_output == "b"
    assert second.emitted_output == "bb"
    assert keyboard.output_sha256 == hashlib.sha256(b"abb").hexdigest()
    assert keyboard.accepted_contact_count == 3
    assert keyboard.attempted_contact_count == 2
    assert first.model_definition_hash == keyboard.model_definition_hash
    serialized = first.to_dict()
    assert "resolved_output" not in serialized
    assert serialized["output_sha256"] == hashlib.sha256(b"a").hexdigest()
    assert serialized["raw_output_serialized"] is False
    model = keyboard.to_dict()
    assert "output" not in model and "output_map" not in model
    assert model["contact_input_contract"] == "ACHIEVED_BOARD_XYZ_NORMAL_DWELL_ONLY"
    assert len(keyboard.region_definition_hash) == 64
    assert len(keyboard.output_map_hash) == 64
    assert len(keyboard.model_definition_hash) == 64

    with pytest.raises(TypeError):
        keyboard.apply_contact(  # type: ignore[call-arg]
            action_index=2,
            expected_character="x",
        )


@pytest.mark.parametrize(
    ("event", "expected"),
    (
        (_contact(0, -1.0), ContactDisposition.OUTSIDE_REGION),
        (_contact(0, 5.0, z=12.0), ContactDisposition.DEPTH_OUT_OF_RANGE),
        (
            _contact(0, 5.0, normal=(0.0, 0.0, 1.0)),
            ContactDisposition.NORMAL_OUT_OF_RANGE,
        ),
        (_contact(0, 5.0, dwell_ticks=9), ContactDisposition.DWELL_OUT_OF_RANGE),
        (
            _contact(0, 5.0, activation_count=0),
            ContactDisposition.MISSED_CONTACT,
        ),
    ),
)
def test_keyboard_rejects_invalid_or_missed_contact_fail_closed(
    event: ContactEvent,
    expected: ContactDisposition,
) -> None:
    keyboard = VirtualKeyboard(
        regions=(_region("KEY_A", 0.0, 10.0),),
        output_map={"KEY_A": "a"},
    )
    result = keyboard.apply_contact(event)
    assert result.disposition is expected
    assert not result.accepted
    assert result.resolved_output is None
    assert keyboard.output_length == 0
    assert keyboard.last_action_index == 0


def test_keyboard_rejects_boundary_ambiguity_and_absent_focus() -> None:
    ambiguous = VirtualKeyboard(
        regions=(_region("KEY_A", 0.0, 10.0), _region("KEY_B", 10.0, 20.0)),
        output_map={"KEY_A": "a", "KEY_B": "b"},
    )
    boundary = ambiguous.apply_contact(_contact(0, 10.0))
    assert boundary.disposition is ContactDisposition.AMBIGUOUS_REGION
    assert ambiguous.output_length == 0

    unfocused = VirtualKeyboard(
        regions=(_region("KEY_A", 0.0, 10.0),),
        output_map={"KEY_A": "a"},
        focused=False,
    )
    rejected = unfocused.apply_contact(_contact(0, 5.0))
    assert rejected.disposition is ContactDisposition.DEVICE_NOT_FOCUSED
    assert unfocused.output_length == 0
    with pytest.raises(VirtualValidationError, match="increase strictly"):
        unfocused.apply_contact(_contact(0, 5.0))


def test_android_scopes_regions_to_ui_state_and_applies_mapped_transition() -> None:
    android = VirtualAndroid(
        initial_ui_state="LOWER",
        regions=(
            _region("LOWER_A", 0.0, 10.0, ui_state="LOWER"),
            _region("UPPER_A", 0.0, 10.0, ui_state="UPPER"),
            _region("SHIFT", 10.0, 20.0, ui_state="LOWER"),
        ),
        output_map={"LOWER_A": "a", "UPPER_A": "A", "SHIFT": "^"},
        state_transition_map={"SHIFT": "UPPER"},
    )
    assert android.verify_ui_state("LOWER")
    first = android.apply_contact(_contact(0, 5.0))
    assert first.resolved_target_id == "LOWER_A"
    assert first.resolved_output == "a"

    shift = android.apply_contact(_contact(1, 15.0))
    assert shift.resolved_target_id == "SHIFT"
    assert android.verify_ui_state("UPPER")
    upper = android.apply_contact(_contact(2, 5.0))
    assert upper.resolved_target_id == "UPPER_A"
    assert upper.resolved_output == "A"
    assert android.output_sha256 == hashlib.sha256("a^A".encode()).hexdigest()

    android.set_ui_state_for_simulation("UNKNOWN")
    wrong_state = android.apply_contact(_contact(3, 5.0))
    assert wrong_state.disposition is ContactDisposition.WRONG_UI_STATE
    assert not wrong_state.accepted


def test_event_ledger_is_bounded_ordered_deterministic_and_sealable() -> None:
    token = _token()
    first = VirtualEventLedger(token=token, maximum_events=2)
    second = VirtualEventLedger(token=token, maximum_events=2)
    before = _digest("a")
    after = _digest("b")
    events = (
        VirtualExecutionEvent(
            sequence=0,
            tick=3,
            component="arm",
            operation="execute",
            status="PASS",
            detail_code="WAYPOINT_ACCEPTED",
            before_state_hash=before,
            after_state_hash=after,
            waypoint_sequence=0,
            virtual_command_executed=True,
        ),
        VirtualExecutionEvent(
            sequence=1,
            tick=3,
            component="keyboard",
            operation="contact",
            status="PASS",
            detail_code="EXPECTED_CHARACTER_APPENDED",
            action_index=0,
            target_id="A",
        ),
    )
    for ledger in (first, second):
        for event in events:
            ledger.append(event)
        assert ledger.virtual_commands_executed == 1
        with pytest.raises(VirtualResourceLimitError):
            ledger.append(
                VirtualExecutionEvent(2, 4, "arm", "execute", "PASS", "EXTRA")
            )
        ledger.seal()
        with pytest.raises(VirtualLifecycleError):
            ledger.append(
                VirtualExecutionEvent(2, 4, "arm", "execute", "PASS", "SEALED")
            )
    assert first.ledger_hash == second.ledger_hash
    document = first.to_dict()
    assert document["virtual_commands_executed"] == 1
    assert document["hardware_commands_generated"] == 0
    assert document["authority"]["contact_authorized"] is False  # type: ignore[index]


def test_event_ledger_rejects_sequence_and_tick_regression() -> None:
    ledger = VirtualEventLedger(token=_token())
    with pytest.raises(VirtualValidationError, match="must equal"):
        ledger.append(VirtualExecutionEvent(1, 0, "arm", "connect", "PASS", "CONNECTED"))
    ledger.append(VirtualExecutionEvent(0, 5, "arm", "connect", "PASS", "CONNECTED"))
    with pytest.raises(VirtualValidationError, match="ticks"):
        ledger.append(VirtualExecutionEvent(1, 4, "arm", "reference", "PASS", "REFERENCED"))

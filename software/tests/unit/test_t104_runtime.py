from __future__ import annotations

from copy import deepcopy
import hashlib
import inspect
from typing import Any

import pytest

from rocell.simulation.controller import ControllerPose
import rocell.simulation.t104_runtime as runtime_module
from rocell.simulation.t104_runtime import (
    InMemoryT104Runtime,
    MAX_RUNTIME_TRACE_SAMPLES,
    NonWireT104Command,
    NonWireT104Target,
    PHYSICAL_AUTHORITY_ZERO,
    T104FaultInjection,
    T104FeedbackReceipt,
    T104RuntimeConfig,
    T104RuntimeError,
    T104RuntimeScheduleEntry,
    T104RuntimeStateReceipt,
    T104TraceReceipt,
    controller_pose_sha256,
)


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode("ascii")).hexdigest()


def _pose(x_mm: float) -> ControllerPose:
    return ControllerPose(x_mm, 5.0, 120.0, -0.2, 0.1, 2.8)


def _commands(count: int = 4, *, session_id: str = "session-001") -> tuple[NonWireT104Command, ...]:
    previous = _pose(0.0)
    result: list[NonWireT104Command] = []
    for ordinal in range(count):
        target = NonWireT104Target(f"waypoint-{ordinal:03d}", _pose(float(ordinal + 1)))
        result.append(
            NonWireT104Command(
                command_id=f"command-{ordinal:03d}",
                session_id=session_id,
                sequence_ordinal=ordinal,
                expected_previous_pose_sha256=controller_pose_sha256(previous),
                route_sha256=_sha(f"route-{ordinal}"),
                joint_result_sha256=_sha(f"joints-{ordinal}"),
                target=target,
                spd_coefficient=1.0,
            )
        )
        previous = target.pose
    return tuple(result)


def _config(
    count: int = 4,
    *,
    fault: T104FaultInjection | None = None,
) -> tuple[T104RuntimeConfig, tuple[NonWireT104Command, ...]]:
    commands = _commands(count)
    config = T104RuntimeConfig.bind_commands(
        session_id="session-001",
        initial_pose=_pose(0.0),
        commands=commands,
        maximum_trace_samples=100,
        settle_sample_count=3,
        settle_tolerance_mixed_units=0.001,
        fault_injections=() if fault is None else (fault,),
    )
    return config, commands


def _assert_zero_authority_documents(value: object) -> None:
    """Every object advertised as a document carries its own hard boundary."""

    if type(value) is dict:
        mapping = value
        if "schema" in mapping:
            assert mapping["simulation_only"] is True
            assert mapping["wire_message_present"] is False
            assert mapping["hardware_commands_generated"] == 0
            assert type(mapping["hardware_commands_generated"]) is int
            assert mapping["hardware_accessed"] is False
            assert mapping["physical_authority"] == PHYSICAL_AUTHORITY_ZERO
        for child in mapping.values():
            _assert_zero_authority_documents(child)
    elif type(value) is list:
        for child in value:
            _assert_zero_authority_documents(child)


def test_dense_ordered_commands_are_deterministic_and_never_authoritative() -> None:
    config, commands = _config(47)
    first_runtime = InMemoryT104Runtime(config)
    second_runtime = InMemoryT104Runtime(T104RuntimeConfig.from_dict(config.to_dict()))

    first = first_runtime.execute_many(tuple(command.to_dict() for command in commands))
    second = second_runtime.execute_many(commands)

    assert first == second
    assert len(first) == 47
    assert [receipt.sequence_ordinal for receipt in first] == list(range(47))
    assert all(receipt.success and receipt.settled for receipt in first)
    assert all(receipt.status == "COMPLETED_SETTLED" for receipt in first)
    assert all(len(receipt.feedback) == 3 for receipt in first)
    assert all(sample.settled for receipt in first for sample in receipt.feedback)
    assert all(
        current.state_after.current_pose_sha256
        == following.state_before.current_pose_sha256
        for current, following in zip(first, first[1:])
    )
    final = first_runtime.state_receipt()
    assert final.terminal is True
    assert final.connected is True
    assert final.next_sequence_ordinal == 47
    assert final.attempted_command_count == 47
    assert final.completed_command_count == 47
    assert final.trace_count == 47
    assert final.current_pose == commands[-1].target.pose

    _assert_zero_authority_documents(config.to_dict())
    for command in commands:
        _assert_zero_authority_documents(command.to_dict())
    for receipt in first:
        _assert_zero_authority_documents(receipt.to_dict())


def test_all_public_records_exactly_round_trip_and_hash_stably() -> None:
    config, commands = _config(1)
    target = commands[0].target
    entry = config.schedule[0]
    initial = InMemoryT104Runtime(config).state_receipt()
    trace = InMemoryT104Runtime(config).execute(commands[0])
    feedback = trace.feedback[0]

    pairs = (
        (NonWireT104Target, target),
        (NonWireT104Command, commands[0]),
        (T104RuntimeScheduleEntry, entry),
        (T104RuntimeConfig, config),
        (T104RuntimeStateReceipt, initial),
        (T104FeedbackReceipt, feedback),
        (T104TraceReceipt, trace),
    )
    for record_type, record in pairs:
        rebuilt = record_type.from_dict(record.to_dict())
        assert rebuilt == record
        assert rebuilt.to_dict() == record.to_dict()
    assert trace.canonical_sha256 == T104TraceReceipt.from_dict(
        trace.to_dict()
    ).canonical_sha256


@pytest.mark.parametrize(
    ("field", "replacement", "match"),
    (
        ("session_id", "different-session", "session mismatch"),
        ("command_id", "different-command", "command_id mismatch"),
        ("route_sha256", _sha("wrong-route"), "route hash mismatch"),
        ("joint_result_sha256", _sha("wrong-joints"), "joint-result hash mismatch"),
        (
            "expected_previous_pose_sha256",
            _sha("wrong-pose"),
            "expected previous pose",
        ),
        ("spd_coefficient", 2.0, "command hash mismatch"),
    ),
)
def test_bound_command_tampering_fails_closed(
    field: str, replacement: object, match: str
) -> None:
    config, commands = _config(1)
    document = commands[0].to_dict()
    document[field] = replacement

    with pytest.raises(T104RuntimeError, match=match):
        InMemoryT104Runtime(config).execute(document)


def test_target_tamper_is_rejected_by_schedule_hash_binding() -> None:
    config, commands = _config(1)
    document = commands[0].to_dict()
    document["target"]["pose"]["x_mm"] = 99.0

    with pytest.raises(T104RuntimeError, match="target hash mismatch"):
        InMemoryT104Runtime(config).execute(document)


def test_reorder_skip_and_replay_are_rejected_without_state_mutation() -> None:
    config, commands = _config(3)
    emulator = InMemoryT104Runtime(config)
    initial_hash = emulator.state_receipt().canonical_sha256

    with pytest.raises(T104RuntimeError, match="reorder/replay/skip"):
        emulator.execute(commands[1])
    assert emulator.state_receipt().canonical_sha256 == initial_hash

    first = emulator.execute(commands[0])
    assert first.success
    after_first_hash = emulator.state_receipt().canonical_sha256
    with pytest.raises(T104RuntimeError, match="reorder/replay/skip"):
        emulator.execute(commands[0])
    assert emulator.state_receipt().canonical_sha256 == after_first_hash

    emulator.execute(commands[1])
    emulator.execute(commands[2])
    with pytest.raises(T104RuntimeError, match="terminal; replay"):
        emulator.execute(commands[2])


@pytest.mark.parametrize(
    "mutation",
    (
        lambda document: document.update({"T": 104}),
        lambda document: document["target"].update({"T": 104}),
        lambda document: document.update({"wire_payload": '{"T":104}'}),
        lambda document: document.update({"serial_payload": "opaque"}),
        lambda document: document.update({"live_motion_authorized": False}),
        lambda document: document.update({"live_authority": "none"}),
        lambda document: document.update({"hardware_command_count": 1}),
        lambda document: document.update({"commands_transmitted": 1}),
        lambda document: document.update({"unexpected": "field"}),
        lambda document: document.update({"command_id": "bad\nwire-line"}),
        lambda document: document.update({"wire_message_present": True}),
        lambda document: document.update({"hardware_commands_generated": 1}),
        lambda document: document.update({"hardware_accessed": True}),
        lambda document: document.update({"physical_authority": "LIVE"}),
    ),
)
def test_wire_authority_counter_and_extra_key_smuggling_is_rejected(
    mutation: Any,
) -> None:
    _, commands = _config(1)
    document = commands[0].to_dict()
    mutation(document)

    with pytest.raises((T104RuntimeError, TypeError)):
        NonWireT104Command.from_dict(document)


def test_canonical_parser_rejects_noncanonical_numbers_and_bool_ordinals() -> None:
    _, commands = _config(1)
    command = commands[0].to_dict()
    command["spd_coefficient"] = 1
    with pytest.raises(TypeError, match="canonical JSON float"):
        NonWireT104Command.from_dict(command)

    command = commands[0].to_dict()
    command["sequence_ordinal"] = False
    with pytest.raises(TypeError, match="non-boolean integer"):
        NonWireT104Command.from_dict(command)

    command = commands[0].to_dict()
    command["target"]["pose"]["x_mm"] = -0.0
    with pytest.raises(T104RuntimeError, match="negative zero"):
        NonWireT104Command.from_dict(command)


@pytest.mark.parametrize(
    "fault_kind", ("STALL", "RESET", "DISCONNECT", "TIMEOUT", "NONSETTLE")
)
def test_each_injected_fault_is_deterministic_latched_and_zero_authority(
    fault_kind: str,
) -> None:
    config, commands = _config(2, fault=T104FaultInjection(0, fault_kind))
    first_runtime = InMemoryT104Runtime(config)
    second_runtime = InMemoryT104Runtime(config)

    first = first_runtime.execute(commands[0])
    second = second_runtime.execute(commands[0].to_dict())

    assert first == second
    assert first.status == f"FAULT_{fault_kind}"
    assert first.fault_kind == fault_kind
    assert first.success is False
    assert first.settled is False
    assert all(sample.settled is False for sample in first.feedback)
    assert all(sample.fault_kind == fault_kind for sample in first.feedback)
    assert first.state_after.terminal is True
    assert first.state_after.fault_latched == fault_kind
    assert first.state_after.next_sequence_ordinal == 0
    assert first.state_after.attempted_command_count == 1
    assert first.state_after.completed_command_count == 0
    assert first.state_after.trace_count == 1
    assert first.state_after.connected is (fault_kind != "DISCONNECT")
    assert first.state_after.reset_generation == (1 if fault_kind == "RESET" else 0)
    if fault_kind == "NONSETTLE":
        assert all(
            sample.target_error_max_mixed_units
            > config.settle_tolerance_mixed_units
            for sample in first.feedback
        )
    _assert_zero_authority_documents(first.to_dict())

    with pytest.raises(T104RuntimeError, match="latched"):
        first_runtime.execute(commands[0])
    with pytest.raises(T104RuntimeError, match="latched"):
        first_runtime.execute(commands[1])


def test_execute_many_stops_at_first_fault_and_never_consumes_suffix() -> None:
    config, commands = _config(5, fault=T104FaultInjection(2, "TIMEOUT"))
    emulator = InMemoryT104Runtime(config)

    receipts = emulator.execute_many(commands)

    assert [receipt.sequence_ordinal for receipt in receipts] == [0, 1, 2]
    assert [receipt.success for receipt in receipts] == [True, True, False]
    assert emulator.state_receipt().next_sequence_ordinal == 2
    assert emulator.state_receipt().attempted_command_count == 3


def test_config_rejects_bad_pose_chain_session_ordinals_and_fault_plan() -> None:
    commands = list(_commands(2))
    wrong_chain = NonWireT104Command(
        command_id=commands[1].command_id,
        session_id=commands[1].session_id,
        sequence_ordinal=commands[1].sequence_ordinal,
        expected_previous_pose_sha256=_sha("wrong"),
        route_sha256=commands[1].route_sha256,
        joint_result_sha256=commands[1].joint_result_sha256,
        target=commands[1].target,
        spd_coefficient=commands[1].spd_coefficient,
    )
    with pytest.raises(T104RuntimeError, match="pose chain"):
        T104RuntimeConfig.bind_commands(
            session_id="session-001",
            initial_pose=_pose(0.0),
            commands=(commands[0], wrong_chain),
        )

    wrong_session = NonWireT104Command(
        command_id=commands[0].command_id,
        session_id="other-session",
        sequence_ordinal=0,
        expected_previous_pose_sha256=commands[0].expected_previous_pose_sha256,
        route_sha256=commands[0].route_sha256,
        joint_result_sha256=commands[0].joint_result_sha256,
        target=commands[0].target,
        spd_coefficient=1.0,
    )
    with pytest.raises(T104RuntimeError, match="session_id"):
        T104RuntimeConfig.bind_commands(
            session_id="session-001",
            initial_pose=_pose(0.0),
            commands=(wrong_session,),
        )

    with pytest.raises(T104RuntimeError, match="sorted and unique"):
        T104RuntimeConfig.bind_commands(
            session_id="session-001",
            initial_pose=_pose(0.0),
            commands=tuple(commands),
            fault_injections=(
                T104FaultInjection(1, "STALL"),
                T104FaultInjection(0, "RESET"),
            ),
        )


def test_config_hashes_detect_schedule_initial_pose_and_extra_key_tamper() -> None:
    config, _ = _config(2)

    schedule_tamper = config.to_dict()
    schedule_tamper["schedule"][0]["route_sha256"] = _sha("tampered-route")
    with pytest.raises(T104RuntimeError, match="schedule hash mismatch"):
        T104RuntimeConfig.from_dict(schedule_tamper)

    pose_tamper = config.to_dict()
    pose_tamper["initial_pose"]["x_mm"] = 99.0
    with pytest.raises(T104RuntimeError, match="initial-pose hash mismatch"):
        T104RuntimeConfig.from_dict(pose_tamper)

    extra = config.to_dict()
    extra["unexpected"] = 0
    with pytest.raises(T104RuntimeError, match="non-exact keys"):
        T104RuntimeConfig.from_dict(extra)


def test_state_feedback_and_trace_tamper_fail_closed() -> None:
    config, commands = _config(1)
    trace = InMemoryT104Runtime(config).execute(commands[0])

    state_document = trace.state_after.to_dict()
    state_document["current_pose_sha256"] = _sha("wrong")
    with pytest.raises(T104RuntimeError, match="current-pose hash mismatch"):
        T104RuntimeStateReceipt.from_dict(state_document)

    feedback_document = trace.feedback[0].to_dict()
    feedback_document["observed_pose_sha256"] = _sha("wrong")
    with pytest.raises(T104RuntimeError, match="observed-pose hash mismatch"):
        T104FeedbackReceipt.from_dict(feedback_document)

    trace_document = trace.to_dict()
    trace_document["state_after"]["attempted_command_count"] = 2
    trace_document["state_after"]["trace_count"] = 2
    with pytest.raises(T104RuntimeError, match="attempted-command transition"):
        T104TraceReceipt.from_dict(trace_document)

    trace_document = trace.to_dict()
    trace_document["status"] = "FAULT_STALL"
    with pytest.raises(T104RuntimeError, match="success disagrees"):
        T104TraceReceipt.from_dict(trace_document)


def test_trace_sample_and_settle_resource_bounds_are_enforced() -> None:
    commands = _commands(1)
    with pytest.raises(T104RuntimeError, match="at least two"):
        T104RuntimeConfig.bind_commands(
            session_id="session-001",
            initial_pose=_pose(0.0),
            commands=commands,
            maximum_trace_samples=1,
        )
    with pytest.raises(T104RuntimeError, match="bounded range"):
        T104RuntimeConfig.bind_commands(
            session_id="session-001",
            initial_pose=_pose(0.0),
            commands=commands,
            maximum_trace_samples=MAX_RUNTIME_TRACE_SAMPLES + 1,
        )
    with pytest.raises(T104RuntimeError, match="bounded range"):
        T104RuntimeConfig.bind_commands(
            session_id="session-001",
            initial_pose=_pose(0.0),
            commands=commands,
            settle_sample_count=65,
        )


def test_module_has_no_protocol_transport_or_message_encoder_surface() -> None:
    source = inspect.getsource(runtime_module)
    executable_lines = [
        line.strip()
        for line in source.splitlines()
        if line.strip() and not line.lstrip().startswith(("#", '"'))
    ]

    assert "arm.serial_transport" not in source
    assert "arm.protocol" not in source
    assert not any("import serial" in line for line in executable_lines)
    assert not hasattr(NonWireT104Command, "to_message")
    assert not hasattr(InMemoryT104Runtime, "send")
    assert not hasattr(InMemoryT104Runtime, "write")


def test_zero_motion_and_gripper_only_command_remains_deterministic() -> None:
    start = _pose(0.0)
    target_pose = ControllerPose(
        start.x_mm,
        start.y_mm,
        start.z_mm,
        start.pitch_rad,
        start.roll_rad,
        2.0,
    )
    command = NonWireT104Command(
        command_id="gripper-only",
        session_id="session-001",
        sequence_ordinal=0,
        expected_previous_pose_sha256=controller_pose_sha256(start),
        route_sha256=_sha("route"),
        joint_result_sha256=_sha("joints"),
        target=NonWireT104Target("gripper-target", target_pose),
        spd_coefficient=1.0,
    )
    config = T104RuntimeConfig.bind_commands(
        session_id="session-001", initial_pose=start, commands=(command,)
    )

    receipt = InMemoryT104Runtime(config).execute(command)

    assert receipt.simulator_sample_count == 1
    assert receipt.success
    assert receipt.state_after.current_pose == target_pose


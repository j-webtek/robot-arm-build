"""Strict, in-memory rehearsal of a T=104-shaped controller boundary.

This module deliberately models *shape and sequencing*, not the RoArm wire
protocol.  It cannot serialize a command, open a transport, or grant physical
authority.  In particular, it does not import the arm protocol/transport
modules and never constructs a :class:`CartesianGoal`.  The only motion model
it calls is :func:`rocell.simulation.controller.simulate_t104_trace`.

The public records use exact, bounded JSON shapes so a future integration can
exercise command ordering, pose continuity, route/IK-result binding, feedback
settling, and failure handling without accidentally making a sendable message.
Every record repeats the zero-authority facts.  Repetition is intentional: an
individual record remains honest when separated from its parent report.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import threading
from typing import Any, Mapping, Sequence, cast

from .controller import (
    CONTROLLER_FRAME,
    MAX_SIMULATION_SPD_COEFFICIENT,
    ControllerPose,
    ControllerSimulationError,
    simulate_t104_trace,
)


NON_WIRE_T104_TARGET_SCHEMA = "rocell.simulation.non_wire_t104_target.v1"
NON_WIRE_T104_COMMAND_SCHEMA = "rocell.simulation.non_wire_t104_command.v1"
T104_RUNTIME_SCHEDULE_ENTRY_SCHEMA = (
    "rocell.simulation.non_wire_t104_schedule_entry.v1"
)
T104_RUNTIME_FAULT_SCHEMA = "rocell.simulation.non_wire_t104_fault_injection.v1"
T104_RUNTIME_CONFIG_SCHEMA = "rocell.simulation.non_wire_t104_runtime_config.v1"
T104_RUNTIME_STATE_SCHEMA = "rocell.simulation.non_wire_t104_state_receipt.v1"
T104_RUNTIME_FEEDBACK_SCHEMA = "rocell.simulation.non_wire_t104_feedback_receipt.v1"
T104_RUNTIME_TRACE_SCHEMA = "rocell.simulation.non_wire_t104_trace_receipt.v1"
T104_RUNTIME_SCHEDULE_SCHEMA = "rocell.simulation.non_wire_t104_schedule.v1"

PHYSICAL_AUTHORITY_ZERO = "ZERO"
MAX_RUNTIME_COMMANDS = 4_096
MAX_RUNTIME_TRACE_SAMPLES = 100_000
MAX_SETTLE_SAMPLES = 64
MAX_CANONICAL_DOCUMENT_BYTES = 8 * 1024 * 1024
MAX_CANONICAL_NODES = 300_000
MAX_CANONICAL_DEPTH = 24
MAX_IDENTIFIER_LENGTH = 128
MAX_SAFE_INTEGER = (1 << 53) - 1

_SHA256_LENGTH = 64
_AUTHORITY_KEYS = frozenset(
    {
        "simulation_only",
        "wire_message_present",
        "hardware_commands_generated",
        "hardware_accessed",
        "physical_authority",
    }
)
_HARDWARE_COUNTER_KEYS = frozenset(
    {
        "hardware_commands_generated",
        "hardware_command_count",
        "hardware_commands_sent",
        "commands_transmitted",
        "wire_bytes_generated",
    }
)
_FORBIDDEN_LIVE_AUTHORITY_KEYS = frozenset(
    {
        "live_authority",
        "live_motion_authorized",
        "motion_authorized",
        "physical_motion_authorized",
        "authorization_token",
        "physical_permit",
    }
)
_FORBIDDEN_WIRE_KEYS = frozenset(
    {
        "wire_payload",
        "serial_payload",
        "wire_message",
        "encoded_message",
        "message_bytes",
    }
)
_FAULT_KINDS = frozenset({"STALL", "RESET", "DISCONNECT", "TIMEOUT", "NONSETTLE"})
_TRACE_STATUSES = frozenset(
    {
        "COMPLETED_SETTLED",
        "FAULT_STALL",
        "FAULT_RESET",
        "FAULT_DISCONNECT",
        "FAULT_TIMEOUT",
        "FAULT_NONSETTLE",
    }
)


class T104RuntimeError(RuntimeError):
    """A non-wire runtime record or state transition failed closed."""


def _authority_fields() -> dict[str, object]:
    """Return a fresh authority envelope for one standalone record."""

    return {
        "simulation_only": True,
        "wire_message_present": False,
        "hardware_commands_generated": 0,
        "hardware_accessed": False,
        "physical_authority": PHYSICAL_AUTHORITY_ZERO,
    }


def _preflight_json_tree(value: object) -> None:
    """Bound a JSON tree and reject transport/authority smuggling early."""

    nodes = 0

    def visit(item: object, depth: int) -> None:
        nonlocal nodes
        nodes += 1
        if nodes > MAX_CANONICAL_NODES:
            raise T104RuntimeError("document exceeds the canonical node limit")
        if depth > MAX_CANONICAL_DEPTH:
            raise T104RuntimeError("document exceeds the canonical depth limit")
        if item is None or type(item) is bool:
            return
        if type(item) is int:
            if not -MAX_SAFE_INTEGER <= cast(int, item) <= MAX_SAFE_INTEGER:
                raise T104RuntimeError("integer is outside the exact JSON range")
            return
        if type(item) is float:
            if not math.isfinite(cast(float, item)):
                raise T104RuntimeError("floating-point values must be finite")
            return
        if type(item) is str:
            text = cast(str, item)
            if len(text) > MAX_IDENTIFIER_LENGTH * 8:
                raise T104RuntimeError("string exceeds the runtime record limit")
            if "\r" in text or "\n" in text:
                raise T104RuntimeError("newline/wire payloads are forbidden")
            return
        if type(item) is list:
            sequence = cast(list[object], item)
            if len(sequence) > MAX_RUNTIME_TRACE_SAMPLES:
                raise T104RuntimeError("array exceeds the runtime record limit")
            for child in sequence:
                visit(child, depth + 1)
            return
        if type(item) is dict:
            mapping = cast(dict[object, object], item)
            if len(mapping) > MAX_RUNTIME_TRACE_SAMPLES:
                raise T104RuntimeError("object exceeds the runtime record limit")
            for raw_key, child in mapping.items():
                if type(raw_key) is not str:
                    raise TypeError("runtime record keys must be strings")
                key = cast(str, raw_key)
                if key == "T":
                    raise T104RuntimeError("a T field is forbidden at every depth")
                if key in _FORBIDDEN_LIVE_AUTHORITY_KEYS:
                    raise T104RuntimeError("live-authority metadata is forbidden")
                if key in _FORBIDDEN_WIRE_KEYS:
                    raise T104RuntimeError("wire-payload fields are forbidden")
                if key in _HARDWARE_COUNTER_KEYS and child != 0:
                    raise T104RuntimeError("hardware counters must remain zero")
                if key == "hardware_accessed" and child is not False:
                    raise T104RuntimeError("hardware_accessed must remain false")
                if key == "wire_message_present" and child is not False:
                    raise T104RuntimeError("wire_message_present must remain false")
                if key == "physical_authority" and child != PHYSICAL_AUTHORITY_ZERO:
                    raise T104RuntimeError("physical_authority must be ZERO")
                visit(child, depth + 1)
            return
        raise T104RuntimeError(
            f"unsupported runtime record type: {type(item).__name__}"
        )

    visit(value, 0)


def _canonical_sha256(document: dict[str, Any]) -> str:
    _preflight_json_tree(document)
    encoded = json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    if len(encoded) > MAX_CANONICAL_DOCUMENT_BYTES:
        raise T104RuntimeError("canonical document exceeds its byte limit")
    return hashlib.sha256(encoded).hexdigest()


def _exact_mapping(
    value: object, expected_keys: frozenset[str], label: str
) -> dict[str, Any]:
    if type(value) is not dict:
        raise TypeError(f"{label} must be exactly dict")
    mapping = cast(dict[str, Any], value)
    _preflight_json_tree(mapping)
    keys = frozenset(mapping)
    if keys != expected_keys:
        missing = sorted(expected_keys - keys)
        extra = sorted(keys - expected_keys)
        raise T104RuntimeError(
            f"{label} has non-exact keys; missing={missing}, extra={extra}"
        )
    return mapping


def _validate_envelope(document: Mapping[str, Any], schema: str, label: str) -> None:
    if document["schema"] != schema:
        raise T104RuntimeError(f"{label} schema mismatch")
    if document["simulation_only"] is not True:
        raise T104RuntimeError(f"{label} must be simulation_only")
    if document["wire_message_present"] is not False:
        raise T104RuntimeError(f"{label} wire_message_present must be false")
    if type(document["hardware_commands_generated"]) is not int:
        raise TypeError(f"{label} hardware_commands_generated must be int")
    if document["hardware_commands_generated"] != 0:
        raise T104RuntimeError(f"{label} hardware counter must remain zero")
    if document["hardware_accessed"] is not False:
        raise T104RuntimeError(f"{label} hardware_accessed must be false")
    if document["physical_authority"] != PHYSICAL_AUTHORITY_ZERO:
        raise T104RuntimeError(f"{label} physical_authority must be ZERO")


def _keys(*specific: str) -> frozenset[str]:
    return frozenset(("schema", *_AUTHORITY_KEYS, *specific))


def _text(value: object, label: str) -> str:
    if type(value) is not str:
        raise TypeError(f"{label} must be str")
    text = cast(str, value)
    if not 1 <= len(text) <= MAX_IDENTIFIER_LENGTH or text != text.strip():
        raise T104RuntimeError(f"{label} must be a bounded, trimmed identifier")
    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.:-"
    if any(character not in allowed for character in text):
        raise T104RuntimeError(f"{label} contains a forbidden character")
    return text


def _sha256(value: object, label: str) -> str:
    if (
        type(value) is not str
        or len(cast(str, value)) != _SHA256_LENGTH
        or any(character not in "0123456789abcdef" for character in cast(str, value))
    ):
        raise T104RuntimeError(
            f"{label} must be exactly 64 lowercase hexadecimal characters"
        )
    return cast(str, value)


def _ordinal(value: object, label: str, *, maximum: int = MAX_SAFE_INTEGER) -> int:
    if type(value) is not int:
        raise TypeError(f"{label} must be a non-boolean integer")
    result = cast(int, value)
    if not 0 <= result <= maximum:
        raise T104RuntimeError(f"{label} is outside its bounded range")
    return result


def _canonical_float(
    value: object,
    label: str,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    if type(value) is not float:
        raise TypeError(f"{label} must be a canonical JSON float")
    result = cast(float, value)
    if not math.isfinite(result):
        raise T104RuntimeError(f"{label} must be finite")
    if result == 0.0 and math.copysign(1.0, result) < 0.0:
        raise T104RuntimeError(f"{label} cannot use negative zero")
    if minimum is not None and result < minimum:
        raise T104RuntimeError(f"{label} is below its minimum")
    if maximum is not None and result > maximum:
        raise T104RuntimeError(f"{label} exceeds its maximum")
    return result


def _normalize_number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{label} must be a real number")
    result = float(value)
    if not math.isfinite(result):
        raise T104RuntimeError(f"{label} must be finite")
    return 0.0 if result == 0.0 else result


def _normalize_pose(pose: ControllerPose, label: str) -> ControllerPose:
    if type(pose) is not ControllerPose:
        raise TypeError(f"{label} must be exactly ControllerPose")
    if pose.frame != CONTROLLER_FRAME:
        raise T104RuntimeError(f"{label} must use {CONTROLLER_FRAME}")
    return ControllerPose(
        _normalize_number(pose.x_mm, f"{label}.x_mm"),
        _normalize_number(pose.y_mm, f"{label}.y_mm"),
        _normalize_number(pose.z_mm, f"{label}.z_mm"),
        _normalize_number(pose.pitch_rad, f"{label}.pitch_rad"),
        _normalize_number(pose.roll_rad, f"{label}.roll_rad"),
        _normalize_number(pose.gripper_raw_rad, f"{label}.gripper_raw_rad"),
    )


def _pose_dict(pose: ControllerPose) -> dict[str, Any]:
    return pose.to_dict()


_POSE_KEYS = frozenset(
    {
        "frame",
        "x_mm",
        "y_mm",
        "z_mm",
        "pitch_rad",
        "roll_rad",
        "gripper_raw_rad",
    }
)


def _pose_from_dict(value: object, label: str) -> ControllerPose:
    document = _exact_mapping(value, _POSE_KEYS, label)
    if document["frame"] != CONTROLLER_FRAME:
        raise T104RuntimeError(f"{label}.frame must be {CONTROLLER_FRAME}")
    pose = ControllerPose(
        _canonical_float(document["x_mm"], f"{label}.x_mm"),
        _canonical_float(document["y_mm"], f"{label}.y_mm"),
        _canonical_float(document["z_mm"], f"{label}.z_mm"),
        _canonical_float(document["pitch_rad"], f"{label}.pitch_rad"),
        _canonical_float(document["roll_rad"], f"{label}.roll_rad"),
        _canonical_float(document["gripper_raw_rad"], f"{label}.gripper_raw_rad"),
    )
    return _normalize_pose(pose, label)


def controller_pose_sha256(pose: ControllerPose) -> str:
    """Hash one normalized controller pose with an explicit zero-authority tag."""

    normalized = _normalize_pose(pose, "pose")
    return _canonical_sha256(
        {
            "schema": "rocell.simulation.non_wire_controller_pose.v1",
            **_authority_fields(),
            "pose": _pose_dict(normalized),
        }
    )


@dataclass(frozen=True, slots=True)
class NonWireT104Target:
    """Canonical Cartesian target with no firmware command type or encoding."""

    target_id: str
    pose: ControllerPose

    def __post_init__(self) -> None:
        object.__setattr__(self, "target_id", _text(self.target_id, "target_id"))
        object.__setattr__(self, "pose", _normalize_pose(self.pose, "target pose"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": NON_WIRE_T104_TARGET_SCHEMA,
            **_authority_fields(),
            "target_id": self.target_id,
            "pose": _pose_dict(self.pose),
        }

    @property
    def canonical_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())

    @classmethod
    def from_dict(cls, value: object) -> "NonWireT104Target":
        keys = _keys("target_id", "pose")
        document = _exact_mapping(value, keys, "non-wire target")
        _validate_envelope(document, NON_WIRE_T104_TARGET_SCHEMA, "non-wire target")
        result = cls(
            target_id=_text(document["target_id"], "target_id"),
            pose=_pose_from_dict(document["pose"], "target pose"),
        )
        if result.to_dict() != document:
            raise T104RuntimeError("non-wire target is not in canonical form")
        return result


@dataclass(frozen=True, slots=True)
class NonWireT104Command:
    """One exact, hashable command intent that can never become wire bytes."""

    command_id: str
    session_id: str
    sequence_ordinal: int
    expected_previous_pose_sha256: str
    route_sha256: str
    joint_result_sha256: str
    target: NonWireT104Target
    spd_coefficient: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "command_id", _text(self.command_id, "command_id"))
        object.__setattr__(self, "session_id", _text(self.session_id, "session_id"))
        object.__setattr__(
            self,
            "sequence_ordinal",
            _ordinal(self.sequence_ordinal, "sequence_ordinal", maximum=MAX_RUNTIME_COMMANDS - 1),
        )
        object.__setattr__(
            self,
            "expected_previous_pose_sha256",
            _sha256(self.expected_previous_pose_sha256, "expected previous pose hash"),
        )
        object.__setattr__(self, "route_sha256", _sha256(self.route_sha256, "route hash"))
        object.__setattr__(
            self,
            "joint_result_sha256",
            _sha256(self.joint_result_sha256, "joint-result hash"),
        )
        if type(self.target) is not NonWireT104Target:
            raise TypeError("target must be exactly NonWireT104Target")
        speed = _normalize_number(self.spd_coefficient, "spd_coefficient")
        if not 0.0 < speed <= MAX_SIMULATION_SPD_COEFFICIENT:
            raise T104RuntimeError("spd_coefficient is outside simulation bounds")
        object.__setattr__(self, "spd_coefficient", speed)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": NON_WIRE_T104_COMMAND_SCHEMA,
            **_authority_fields(),
            "command_id": self.command_id,
            "session_id": self.session_id,
            "sequence_ordinal": self.sequence_ordinal,
            "expected_previous_pose_sha256": self.expected_previous_pose_sha256,
            "route_sha256": self.route_sha256,
            "joint_result_sha256": self.joint_result_sha256,
            "target": self.target.to_dict(),
            "spd_coefficient": self.spd_coefficient,
        }

    @property
    def canonical_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())

    @classmethod
    def from_dict(cls, value: object) -> "NonWireT104Command":
        keys = _keys(
            "command_id",
            "session_id",
            "sequence_ordinal",
            "expected_previous_pose_sha256",
            "route_sha256",
            "joint_result_sha256",
            "target",
            "spd_coefficient",
        )
        document = _exact_mapping(value, keys, "non-wire command")
        _validate_envelope(document, NON_WIRE_T104_COMMAND_SCHEMA, "non-wire command")
        result = cls(
            command_id=_text(document["command_id"], "command_id"),
            session_id=_text(document["session_id"], "session_id"),
            sequence_ordinal=_ordinal(
                document["sequence_ordinal"],
                "sequence_ordinal",
                maximum=MAX_RUNTIME_COMMANDS - 1,
            ),
            expected_previous_pose_sha256=_sha256(
                document["expected_previous_pose_sha256"], "expected previous pose hash"
            ),
            route_sha256=_sha256(document["route_sha256"], "route hash"),
            joint_result_sha256=_sha256(
                document["joint_result_sha256"], "joint-result hash"
            ),
            target=NonWireT104Target.from_dict(document["target"]),
            spd_coefficient=_canonical_float(
                document["spd_coefficient"],
                "spd_coefficient",
                minimum=0.0,
                maximum=MAX_SIMULATION_SPD_COEFFICIENT,
            ),
        )
        if result.to_dict() != document:
            raise T104RuntimeError("non-wire command is not in canonical form")
        return result


@dataclass(frozen=True, slots=True)
class T104RuntimeScheduleEntry:
    """Config-owned expectation for exactly one command occurrence."""

    sequence_ordinal: int
    command_id: str
    command_sha256: str
    expected_previous_pose_sha256: str
    target_sha256: str
    route_sha256: str
    joint_result_sha256: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "sequence_ordinal",
            _ordinal(self.sequence_ordinal, "schedule ordinal", maximum=MAX_RUNTIME_COMMANDS - 1),
        )
        object.__setattr__(self, "command_id", _text(self.command_id, "schedule command_id"))
        for name in (
            "command_sha256",
            "expected_previous_pose_sha256",
            "target_sha256",
            "route_sha256",
            "joint_result_sha256",
        ):
            object.__setattr__(self, name, _sha256(getattr(self, name), name))

    @classmethod
    def from_command(cls, command: NonWireT104Command) -> "T104RuntimeScheduleEntry":
        if type(command) is not NonWireT104Command:
            raise TypeError("command must be exactly NonWireT104Command")
        return cls(
            sequence_ordinal=command.sequence_ordinal,
            command_id=command.command_id,
            command_sha256=command.canonical_sha256,
            expected_previous_pose_sha256=command.expected_previous_pose_sha256,
            target_sha256=command.target.canonical_sha256,
            route_sha256=command.route_sha256,
            joint_result_sha256=command.joint_result_sha256,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": T104_RUNTIME_SCHEDULE_ENTRY_SCHEMA,
            **_authority_fields(),
            "sequence_ordinal": self.sequence_ordinal,
            "command_id": self.command_id,
            "command_sha256": self.command_sha256,
            "expected_previous_pose_sha256": self.expected_previous_pose_sha256,
            "target_sha256": self.target_sha256,
            "route_sha256": self.route_sha256,
            "joint_result_sha256": self.joint_result_sha256,
        }

    @classmethod
    def from_dict(cls, value: object) -> "T104RuntimeScheduleEntry":
        keys = _keys(
            "sequence_ordinal",
            "command_id",
            "command_sha256",
            "expected_previous_pose_sha256",
            "target_sha256",
            "route_sha256",
            "joint_result_sha256",
        )
        document = _exact_mapping(value, keys, "schedule entry")
        _validate_envelope(document, T104_RUNTIME_SCHEDULE_ENTRY_SCHEMA, "schedule entry")
        result = cls(
            sequence_ordinal=_ordinal(
                document["sequence_ordinal"],
                "schedule ordinal",
                maximum=MAX_RUNTIME_COMMANDS - 1,
            ),
            command_id=_text(document["command_id"], "schedule command_id"),
            command_sha256=_sha256(document["command_sha256"], "command hash"),
            expected_previous_pose_sha256=_sha256(
                document["expected_previous_pose_sha256"], "expected previous pose hash"
            ),
            target_sha256=_sha256(document["target_sha256"], "target hash"),
            route_sha256=_sha256(document["route_sha256"], "route hash"),
            joint_result_sha256=_sha256(
                document["joint_result_sha256"], "joint-result hash"
            ),
        )
        if result.to_dict() != document:
            raise T104RuntimeError("schedule entry is not in canonical form")
        return result


@dataclass(frozen=True, slots=True)
class T104FaultInjection:
    """Deterministic fault selected before the zero-authority run starts."""

    sequence_ordinal: int
    fault_kind: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "sequence_ordinal",
            _ordinal(self.sequence_ordinal, "fault ordinal", maximum=MAX_RUNTIME_COMMANDS - 1),
        )
        if type(self.fault_kind) is not str or self.fault_kind not in _FAULT_KINDS:
            raise T104RuntimeError(f"fault_kind must be one of {sorted(_FAULT_KINDS)}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": T104_RUNTIME_FAULT_SCHEMA,
            **_authority_fields(),
            "sequence_ordinal": self.sequence_ordinal,
            "fault_kind": self.fault_kind,
        }

    @classmethod
    def from_dict(cls, value: object) -> "T104FaultInjection":
        document = _exact_mapping(
            value, _keys("sequence_ordinal", "fault_kind"), "fault injection"
        )
        _validate_envelope(document, T104_RUNTIME_FAULT_SCHEMA, "fault injection")
        result = cls(
            sequence_ordinal=_ordinal(
                document["sequence_ordinal"],
                "fault ordinal",
                maximum=MAX_RUNTIME_COMMANDS - 1,
            ),
            fault_kind=document["fault_kind"],
        )
        if result.to_dict() != document:
            raise T104RuntimeError("fault injection is not in canonical form")
        return result


def _schedule_sha256(entries: tuple[T104RuntimeScheduleEntry, ...]) -> str:
    return _canonical_sha256(
        {
            "schema": T104_RUNTIME_SCHEDULE_SCHEMA,
            **_authority_fields(),
            "entries": [entry.to_dict() for entry in entries],
        }
    )


@dataclass(frozen=True, slots=True)
class T104RuntimeConfig:
    """Immutable exact command schedule and deterministic emulator policy."""

    session_id: str
    initial_pose: ControllerPose
    schedule: tuple[T104RuntimeScheduleEntry, ...]
    maximum_trace_samples: int = MAX_RUNTIME_TRACE_SAMPLES
    settle_sample_count: int = 3
    settle_tolerance_mixed_units: float = 0.001
    fault_injections: tuple[T104FaultInjection, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "session_id", _text(self.session_id, "session_id"))
        object.__setattr__(self, "initial_pose", _normalize_pose(self.initial_pose, "initial pose"))
        schedule = tuple(self.schedule)
        if not 1 <= len(schedule) <= MAX_RUNTIME_COMMANDS:
            raise T104RuntimeError(
                f"schedule must contain 1..{MAX_RUNTIME_COMMANDS} commands"
            )
        if any(type(entry) is not T104RuntimeScheduleEntry for entry in schedule):
            raise TypeError("schedule entries must be exactly T104RuntimeScheduleEntry")
        for expected, entry in enumerate(schedule):
            if entry.sequence_ordinal != expected:
                raise T104RuntimeError("schedule ordinals must be contiguous from zero")
        object.__setattr__(self, "schedule", schedule)
        maximum = _ordinal(
            self.maximum_trace_samples,
            "maximum_trace_samples",
            maximum=MAX_RUNTIME_TRACE_SAMPLES,
        )
        if maximum < 2:
            raise T104RuntimeError("maximum_trace_samples must be at least two")
        object.__setattr__(self, "maximum_trace_samples", maximum)
        settle_count = _ordinal(
            self.settle_sample_count,
            "settle_sample_count",
            maximum=MAX_SETTLE_SAMPLES,
        )
        if settle_count < 1:
            raise T104RuntimeError("settle_sample_count must be positive")
        object.__setattr__(self, "settle_sample_count", settle_count)
        tolerance = _normalize_number(
            self.settle_tolerance_mixed_units, "settle_tolerance_mixed_units"
        )
        if not 0.0 < tolerance <= 10.0:
            raise T104RuntimeError("settle tolerance must be within (0, 10]")
        object.__setattr__(self, "settle_tolerance_mixed_units", tolerance)
        faults = tuple(self.fault_injections)
        if len(faults) > len(schedule):
            raise T104RuntimeError("fault injection count exceeds schedule length")
        if any(type(fault) is not T104FaultInjection for fault in faults):
            raise TypeError("fault injections must be exactly T104FaultInjection")
        ordinals = [fault.sequence_ordinal for fault in faults]
        if ordinals != sorted(ordinals) or len(set(ordinals)) != len(ordinals):
            raise T104RuntimeError("fault injections must be sorted and unique")
        if any(ordinal >= len(schedule) for ordinal in ordinals):
            raise T104RuntimeError("fault injection ordinal is outside the schedule")
        object.__setattr__(self, "fault_injections", faults)

    @classmethod
    def bind_commands(
        cls,
        *,
        session_id: str,
        initial_pose: ControllerPose,
        commands: Sequence[NonWireT104Command],
        maximum_trace_samples: int = MAX_RUNTIME_TRACE_SAMPLES,
        settle_sample_count: int = 3,
        settle_tolerance_mixed_units: float = 0.001,
        fault_injections: Sequence[T104FaultInjection] = (),
    ) -> "T104RuntimeConfig":
        """Bind a complete ordered command list and verify its pose chain."""

        if isinstance(commands, (str, bytes)) or not isinstance(commands, Sequence):
            raise TypeError("commands must be a sequence")
        if not 1 <= len(commands) <= MAX_RUNTIME_COMMANDS:
            raise T104RuntimeError("commands are outside the runtime count bound")
        normalized_initial = _normalize_pose(initial_pose, "initial pose")
        expected_previous = controller_pose_sha256(normalized_initial)
        entries: list[T104RuntimeScheduleEntry] = []
        session = _text(session_id, "session_id")
        for ordinal, command in enumerate(commands):
            if type(command) is not NonWireT104Command:
                raise TypeError("commands must contain exactly NonWireT104Command")
            if command.session_id != session:
                raise T104RuntimeError("command session_id disagrees with config")
            if command.sequence_ordinal != ordinal:
                raise T104RuntimeError("command ordinals must be contiguous from zero")
            if command.expected_previous_pose_sha256 != expected_previous:
                raise T104RuntimeError("command expected-previous-pose chain mismatch")
            entries.append(T104RuntimeScheduleEntry.from_command(command))
            expected_previous = controller_pose_sha256(command.target.pose)
        return cls(
            session_id=session,
            initial_pose=normalized_initial,
            schedule=tuple(entries),
            maximum_trace_samples=maximum_trace_samples,
            settle_sample_count=settle_sample_count,
            settle_tolerance_mixed_units=settle_tolerance_mixed_units,
            fault_injections=tuple(fault_injections),
        )

    @property
    def schedule_sha256(self) -> str:
        return _schedule_sha256(self.schedule)

    @property
    def canonical_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": T104_RUNTIME_CONFIG_SCHEMA,
            **_authority_fields(),
            "session_id": self.session_id,
            "initial_pose": _pose_dict(self.initial_pose),
            "initial_pose_sha256": controller_pose_sha256(self.initial_pose),
            "schedule": [entry.to_dict() for entry in self.schedule],
            "schedule_sha256": self.schedule_sha256,
            "maximum_trace_samples": self.maximum_trace_samples,
            "settle_sample_count": self.settle_sample_count,
            "settle_tolerance_mixed_units": self.settle_tolerance_mixed_units,
            "fault_injections": [fault.to_dict() for fault in self.fault_injections],
        }

    @classmethod
    def from_dict(cls, value: object) -> "T104RuntimeConfig":
        document = _exact_mapping(
            value,
            _keys(
                "session_id",
                "initial_pose",
                "initial_pose_sha256",
                "schedule",
                "schedule_sha256",
                "maximum_trace_samples",
                "settle_sample_count",
                "settle_tolerance_mixed_units",
                "fault_injections",
            ),
            "runtime config",
        )
        _validate_envelope(document, T104_RUNTIME_CONFIG_SCHEMA, "runtime config")
        if type(document["schedule"]) is not list:
            raise TypeError("runtime config schedule must be list")
        if type(document["fault_injections"]) is not list:
            raise TypeError("runtime config fault_injections must be list")
        result = cls(
            session_id=_text(document["session_id"], "session_id"),
            initial_pose=_pose_from_dict(document["initial_pose"], "initial pose"),
            schedule=tuple(
                T104RuntimeScheduleEntry.from_dict(entry)
                for entry in cast(list[object], document["schedule"])
            ),
            maximum_trace_samples=_ordinal(
                document["maximum_trace_samples"],
                "maximum_trace_samples",
                maximum=MAX_RUNTIME_TRACE_SAMPLES,
            ),
            settle_sample_count=_ordinal(
                document["settle_sample_count"],
                "settle_sample_count",
                maximum=MAX_SETTLE_SAMPLES,
            ),
            settle_tolerance_mixed_units=_canonical_float(
                document["settle_tolerance_mixed_units"],
                "settle_tolerance_mixed_units",
                minimum=0.0,
                maximum=10.0,
            ),
            fault_injections=tuple(
                T104FaultInjection.from_dict(fault)
                for fault in cast(list[object], document["fault_injections"])
            ),
        )
        if _sha256(document["initial_pose_sha256"], "initial pose hash") != controller_pose_sha256(
            result.initial_pose
        ):
            raise T104RuntimeError("runtime config initial-pose hash mismatch")
        if _sha256(document["schedule_sha256"], "schedule hash") != result.schedule_sha256:
            raise T104RuntimeError("runtime config schedule hash mismatch")
        if result.to_dict() != document:
            raise T104RuntimeError("runtime config is not in canonical form")
        return result


@dataclass(frozen=True, slots=True)
class T104RuntimeStateReceipt:
    """Immutable snapshot of the emulator's entirely in-memory state."""

    session_id: str
    config_sha256: str
    next_sequence_ordinal: int
    current_pose: ControllerPose
    attempted_command_count: int
    completed_command_count: int
    trace_count: int
    connected: bool
    reset_generation: int
    fault_latched: str | None
    terminal: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "session_id", _text(self.session_id, "state session_id"))
        object.__setattr__(self, "config_sha256", _sha256(self.config_sha256, "config hash"))
        for name in (
            "next_sequence_ordinal",
            "attempted_command_count",
            "completed_command_count",
            "trace_count",
            "reset_generation",
        ):
            object.__setattr__(self, name, _ordinal(getattr(self, name), name))
        object.__setattr__(self, "current_pose", _normalize_pose(self.current_pose, "state pose"))
        if type(self.connected) is not bool or type(self.terminal) is not bool:
            raise TypeError("connected and terminal must be bool")
        if self.fault_latched is not None and (
            type(self.fault_latched) is not str or self.fault_latched not in _FAULT_KINDS
        ):
            raise T104RuntimeError("fault_latched is not a recognized runtime fault")
        if self.completed_command_count > self.attempted_command_count:
            raise T104RuntimeError("completed count cannot exceed attempted count")
        if self.trace_count != self.attempted_command_count:
            raise T104RuntimeError("each attempted command must have one trace")
        if self.fault_latched is not None and not self.terminal:
            raise T104RuntimeError("a latched fault must be terminal")

    @property
    def current_pose_sha256(self) -> str:
        return controller_pose_sha256(self.current_pose)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": T104_RUNTIME_STATE_SCHEMA,
            **_authority_fields(),
            "session_id": self.session_id,
            "config_sha256": self.config_sha256,
            "next_sequence_ordinal": self.next_sequence_ordinal,
            "current_pose": _pose_dict(self.current_pose),
            "current_pose_sha256": self.current_pose_sha256,
            "attempted_command_count": self.attempted_command_count,
            "completed_command_count": self.completed_command_count,
            "trace_count": self.trace_count,
            "connected": self.connected,
            "reset_generation": self.reset_generation,
            "fault_latched": self.fault_latched,
            "terminal": self.terminal,
        }

    @property
    def canonical_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())

    @classmethod
    def from_dict(cls, value: object) -> "T104RuntimeStateReceipt":
        document = _exact_mapping(
            value,
            _keys(
                "session_id",
                "config_sha256",
                "next_sequence_ordinal",
                "current_pose",
                "current_pose_sha256",
                "attempted_command_count",
                "completed_command_count",
                "trace_count",
                "connected",
                "reset_generation",
                "fault_latched",
                "terminal",
            ),
            "runtime state receipt",
        )
        _validate_envelope(document, T104_RUNTIME_STATE_SCHEMA, "runtime state receipt")
        if type(document["connected"]) is not bool or type(document["terminal"]) is not bool:
            raise TypeError("state connected and terminal must be bool")
        result = cls(
            session_id=_text(document["session_id"], "state session_id"),
            config_sha256=_sha256(document["config_sha256"], "config hash"),
            next_sequence_ordinal=_ordinal(
                document["next_sequence_ordinal"], "next_sequence_ordinal"
            ),
            current_pose=_pose_from_dict(document["current_pose"], "state pose"),
            attempted_command_count=_ordinal(
                document["attempted_command_count"], "attempted_command_count"
            ),
            completed_command_count=_ordinal(
                document["completed_command_count"], "completed_command_count"
            ),
            trace_count=_ordinal(document["trace_count"], "trace_count"),
            connected=document["connected"],
            reset_generation=_ordinal(document["reset_generation"], "reset_generation"),
            fault_latched=document["fault_latched"],
            terminal=document["terminal"],
        )
        if _sha256(document["current_pose_sha256"], "current pose hash") != result.current_pose_sha256:
            raise T104RuntimeError("state current-pose hash mismatch")
        if result.to_dict() != document:
            raise T104RuntimeError("runtime state receipt is not in canonical form")
        return result


@dataclass(frozen=True, slots=True)
class T104FeedbackReceipt:
    """One deterministic feedback sample bound to a command occurrence."""

    session_id: str
    config_sha256: str
    command_sha256: str
    sequence_ordinal: int
    feedback_ordinal: int
    phase: str
    observed_pose: ControllerPose
    target_error_max_mixed_units: float
    settled: bool
    connected: bool
    reset_generation: int
    fault_kind: str | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "session_id", _text(self.session_id, "feedback session_id"))
        object.__setattr__(self, "config_sha256", _sha256(self.config_sha256, "config hash"))
        object.__setattr__(self, "command_sha256", _sha256(self.command_sha256, "command hash"))
        object.__setattr__(self, "sequence_ordinal", _ordinal(self.sequence_ordinal, "sequence_ordinal"))
        object.__setattr__(self, "feedback_ordinal", _ordinal(self.feedback_ordinal, "feedback_ordinal"))
        if self.phase != "SETTLE":
            raise T104RuntimeError("feedback phase must be SETTLE")
        object.__setattr__(self, "observed_pose", _normalize_pose(self.observed_pose, "feedback pose"))
        error = _normalize_number(
            self.target_error_max_mixed_units, "target_error_max_mixed_units"
        )
        if error < 0.0:
            raise T104RuntimeError("target error must be non-negative")
        object.__setattr__(self, "target_error_max_mixed_units", error)
        if type(self.settled) is not bool or type(self.connected) is not bool:
            raise TypeError("feedback settled and connected must be bool")
        object.__setattr__(self, "reset_generation", _ordinal(self.reset_generation, "reset_generation"))
        if self.fault_kind is not None and (
            type(self.fault_kind) is not str or self.fault_kind not in _FAULT_KINDS
        ):
            raise T104RuntimeError("feedback fault_kind is not recognized")
        if self.settled and (self.fault_kind is not None or not self.connected):
            raise T104RuntimeError("faulted/disconnected feedback cannot be settled")

    @property
    def observed_pose_sha256(self) -> str:
        return controller_pose_sha256(self.observed_pose)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": T104_RUNTIME_FEEDBACK_SCHEMA,
            **_authority_fields(),
            "session_id": self.session_id,
            "config_sha256": self.config_sha256,
            "command_sha256": self.command_sha256,
            "sequence_ordinal": self.sequence_ordinal,
            "feedback_ordinal": self.feedback_ordinal,
            "phase": self.phase,
            "observed_pose": _pose_dict(self.observed_pose),
            "observed_pose_sha256": self.observed_pose_sha256,
            "target_error_max_mixed_units": self.target_error_max_mixed_units,
            "settled": self.settled,
            "connected": self.connected,
            "reset_generation": self.reset_generation,
            "fault_kind": self.fault_kind,
        }

    @property
    def canonical_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())

    @classmethod
    def from_dict(cls, value: object) -> "T104FeedbackReceipt":
        document = _exact_mapping(
            value,
            _keys(
                "session_id",
                "config_sha256",
                "command_sha256",
                "sequence_ordinal",
                "feedback_ordinal",
                "phase",
                "observed_pose",
                "observed_pose_sha256",
                "target_error_max_mixed_units",
                "settled",
                "connected",
                "reset_generation",
                "fault_kind",
            ),
            "feedback receipt",
        )
        _validate_envelope(document, T104_RUNTIME_FEEDBACK_SCHEMA, "feedback receipt")
        if type(document["settled"]) is not bool or type(document["connected"]) is not bool:
            raise TypeError("feedback settled and connected must be bool")
        result = cls(
            session_id=_text(document["session_id"], "feedback session_id"),
            config_sha256=_sha256(document["config_sha256"], "config hash"),
            command_sha256=_sha256(document["command_sha256"], "command hash"),
            sequence_ordinal=_ordinal(document["sequence_ordinal"], "sequence_ordinal"),
            feedback_ordinal=_ordinal(document["feedback_ordinal"], "feedback_ordinal"),
            phase=document["phase"],
            observed_pose=_pose_from_dict(document["observed_pose"], "feedback pose"),
            target_error_max_mixed_units=_canonical_float(
                document["target_error_max_mixed_units"],
                "target_error_max_mixed_units",
                minimum=0.0,
            ),
            settled=document["settled"],
            connected=document["connected"],
            reset_generation=_ordinal(document["reset_generation"], "reset_generation"),
            fault_kind=document["fault_kind"],
        )
        if _sha256(document["observed_pose_sha256"], "observed pose hash") != result.observed_pose_sha256:
            raise T104RuntimeError("feedback observed-pose hash mismatch")
        if result.to_dict() != document:
            raise T104RuntimeError("feedback receipt is not in canonical form")
        return result


def _pose_error(first: ControllerPose, second: ControllerPose) -> float:
    return max(
        abs(a - b)
        for a, b in zip(
            (
                first.x_mm,
                first.y_mm,
                first.z_mm,
                first.pitch_rad,
                first.roll_rad,
                first.gripper_raw_rad,
            ),
            (
                second.x_mm,
                second.y_mm,
                second.z_mm,
                second.pitch_rad,
                second.roll_rad,
                second.gripper_raw_rad,
            ),
        )
    )


def _simulation_trace_sha256(trace: object) -> str:
    """Hash only the audited simulator values under this module's envelope.

    ``T104SimulationTrace.to_dict`` predates this boundary and contains a
    false-valued live-authorization key.  This stricter runtime intentionally
    does not propagate even false live-authority vocabulary into its records.
    The typed trace values are projected into a new exact non-wire document.
    """

    # This helper is private and receives the direct result from
    # simulate_t104_trace. Attribute access keeps the dependency narrow while
    # the canonical projection below remains entirely JSON and zero-authority.
    start = cast(Any, trace).start
    target = cast(Any, trace).target
    samples = cast(Any, trace).samples
    return _canonical_sha256(
        {
            "schema": "rocell.simulation.non_wire_t104_trace_projection.v1",
            **_authority_fields(),
            "controller_frame": CONTROLLER_FRAME,
            "start": _pose_dict(start),
            "target": _pose_dict(target),
            "spd_coefficient": cast(Any, trace).spd_coefficient,
            "delta_mixed_units": cast(Any, trace).delta_mixed_units,
            "zero_motion_delta": cast(Any, trace).zero_motion_delta,
            "samples": [
                {
                    "sample_index": sample.sample_index,
                    "interpolation_parameter": sample.interpolation_parameter,
                    "cosine_eased_fraction": sample.cosine_eased_fraction,
                    "pose": _pose_dict(sample.pose),
                }
                for sample in samples
            ],
        }
    )


@dataclass(frozen=True, slots=True)
class T104TraceReceipt:
    """Complete result of one attempted in-memory command occurrence."""

    session_id: str
    config_sha256: str
    schedule_sha256: str
    command_sha256: str
    sequence_ordinal: int
    route_sha256: str
    joint_result_sha256: str
    simulator_trace_sha256: str
    simulator_sample_count: int
    state_before: T104RuntimeStateReceipt
    feedback: tuple[T104FeedbackReceipt, ...]
    state_after: T104RuntimeStateReceipt
    status: str
    success: bool
    settled: bool
    fault_kind: str | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "session_id", _text(self.session_id, "trace session_id"))
        for name in (
            "config_sha256",
            "schedule_sha256",
            "command_sha256",
            "route_sha256",
            "joint_result_sha256",
            "simulator_trace_sha256",
        ):
            object.__setattr__(self, name, _sha256(getattr(self, name), name))
        object.__setattr__(self, "sequence_ordinal", _ordinal(self.sequence_ordinal, "sequence_ordinal"))
        sample_count = _ordinal(
            self.simulator_sample_count,
            "simulator_sample_count",
            maximum=MAX_RUNTIME_TRACE_SAMPLES,
        )
        if sample_count < 1:
            raise T104RuntimeError("simulator trace must contain a sample")
        object.__setattr__(self, "simulator_sample_count", sample_count)
        if type(self.state_before) is not T104RuntimeStateReceipt or type(
            self.state_after
        ) is not T104RuntimeStateReceipt:
            raise TypeError("trace states must be exactly T104RuntimeStateReceipt")
        feedback = tuple(self.feedback)
        if not 1 <= len(feedback) <= MAX_SETTLE_SAMPLES:
            raise T104RuntimeError("trace feedback count is outside bounds")
        if any(type(item) is not T104FeedbackReceipt for item in feedback):
            raise TypeError("feedback values must be exactly T104FeedbackReceipt")
        if [item.feedback_ordinal for item in feedback] != list(range(len(feedback))):
            raise T104RuntimeError("feedback ordinals must be contiguous from zero")
        object.__setattr__(self, "feedback", feedback)
        if self.status not in _TRACE_STATUSES:
            raise T104RuntimeError("trace status is not recognized")
        if type(self.success) is not bool or type(self.settled) is not bool:
            raise TypeError("trace success and settled must be bool")
        if self.fault_kind is not None and self.fault_kind not in _FAULT_KINDS:
            raise T104RuntimeError("trace fault_kind is not recognized")
        if self.success != (self.status == "COMPLETED_SETTLED"):
            raise T104RuntimeError("trace success disagrees with status")
        if self.success != self.settled:
            raise T104RuntimeError("trace success disagrees with settled")
        if self.success != (self.fault_kind is None):
            raise T104RuntimeError("trace fault_kind disagrees with success")
        if self.status != (
            "COMPLETED_SETTLED" if self.fault_kind is None else f"FAULT_{self.fault_kind}"
        ):
            raise T104RuntimeError("trace status disagrees with fault_kind")
        if self.state_before.session_id != self.session_id or self.state_after.session_id != self.session_id:
            raise T104RuntimeError("trace state session mismatch")
        if self.state_before.config_sha256 != self.config_sha256 or self.state_after.config_sha256 != self.config_sha256:
            raise T104RuntimeError("trace state config mismatch")
        for item in feedback:
            if (
                item.session_id != self.session_id
                or item.config_sha256 != self.config_sha256
                or item.command_sha256 != self.command_sha256
                or item.sequence_ordinal != self.sequence_ordinal
                or item.fault_kind != self.fault_kind
            ):
                raise T104RuntimeError("feedback binding disagrees with trace")
        if self.state_before.next_sequence_ordinal != self.sequence_ordinal:
            raise T104RuntimeError("trace ordinal disagrees with prior state")
        if self.state_after.attempted_command_count != (
            self.state_before.attempted_command_count + 1
        ):
            raise T104RuntimeError("trace attempted-command transition mismatch")
        if self.state_after.trace_count != self.state_before.trace_count + 1:
            raise T104RuntimeError("trace-count transition mismatch")
        if self.state_after.current_pose_sha256 != feedback[-1].observed_pose_sha256:
            raise T104RuntimeError("trace final feedback disagrees with resulting pose")
        if self.success:
            if not all(item.settled and item.connected for item in feedback):
                raise T104RuntimeError("successful trace requires settled feedback")
            if self.state_after.completed_command_count != (
                self.state_before.completed_command_count + 1
            ):
                raise T104RuntimeError("completed-command transition mismatch")
            if self.state_after.next_sequence_ordinal != self.sequence_ordinal + 1:
                raise T104RuntimeError("successful trace did not advance exactly once")
            if self.state_after.fault_latched is not None:
                raise T104RuntimeError("successful trace cannot latch a fault")
            if self.state_after.reset_generation != self.state_before.reset_generation:
                raise T104RuntimeError("successful trace changed reset generation")
        else:
            if any(item.settled for item in feedback):
                raise T104RuntimeError("fault trace cannot contain settled feedback")
            if self.state_after.completed_command_count != self.state_before.completed_command_count:
                raise T104RuntimeError("fault trace cannot complete a command")
            if self.state_after.next_sequence_ordinal != self.sequence_ordinal:
                raise T104RuntimeError("fault trace cannot advance the command cursor")
            if self.state_after.fault_latched != self.fault_kind or not self.state_after.terminal:
                raise T104RuntimeError("fault trace must latch its terminal fault")
            expected_reset = self.state_before.reset_generation + (
                1 if self.fault_kind == "RESET" else 0
            )
            if self.state_after.reset_generation != expected_reset:
                raise T104RuntimeError("fault trace reset-generation mismatch")
            if self.state_after.connected != (self.fault_kind != "DISCONNECT"):
                raise T104RuntimeError("fault trace connection-state mismatch")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": T104_RUNTIME_TRACE_SCHEMA,
            **_authority_fields(),
            "session_id": self.session_id,
            "config_sha256": self.config_sha256,
            "schedule_sha256": self.schedule_sha256,
            "command_sha256": self.command_sha256,
            "sequence_ordinal": self.sequence_ordinal,
            "route_sha256": self.route_sha256,
            "joint_result_sha256": self.joint_result_sha256,
            "simulator_trace_sha256": self.simulator_trace_sha256,
            "simulator_sample_count": self.simulator_sample_count,
            "state_before": self.state_before.to_dict(),
            "feedback": [item.to_dict() for item in self.feedback],
            "state_after": self.state_after.to_dict(),
            "status": self.status,
            "success": self.success,
            "settled": self.settled,
            "fault_kind": self.fault_kind,
        }

    @property
    def canonical_sha256(self) -> str:
        return _canonical_sha256(self.to_dict())

    @classmethod
    def from_dict(cls, value: object) -> "T104TraceReceipt":
        document = _exact_mapping(
            value,
            _keys(
                "session_id",
                "config_sha256",
                "schedule_sha256",
                "command_sha256",
                "sequence_ordinal",
                "route_sha256",
                "joint_result_sha256",
                "simulator_trace_sha256",
                "simulator_sample_count",
                "state_before",
                "feedback",
                "state_after",
                "status",
                "success",
                "settled",
                "fault_kind",
            ),
            "trace receipt",
        )
        _validate_envelope(document, T104_RUNTIME_TRACE_SCHEMA, "trace receipt")
        if type(document["feedback"]) is not list:
            raise TypeError("trace feedback must be list")
        if type(document["success"]) is not bool or type(document["settled"]) is not bool:
            raise TypeError("trace success and settled must be bool")
        result = cls(
            session_id=_text(document["session_id"], "trace session_id"),
            config_sha256=_sha256(document["config_sha256"], "config hash"),
            schedule_sha256=_sha256(document["schedule_sha256"], "schedule hash"),
            command_sha256=_sha256(document["command_sha256"], "command hash"),
            sequence_ordinal=_ordinal(document["sequence_ordinal"], "sequence_ordinal"),
            route_sha256=_sha256(document["route_sha256"], "route hash"),
            joint_result_sha256=_sha256(
                document["joint_result_sha256"], "joint-result hash"
            ),
            simulator_trace_sha256=_sha256(
                document["simulator_trace_sha256"], "simulator trace hash"
            ),
            simulator_sample_count=_ordinal(
                document["simulator_sample_count"],
                "simulator_sample_count",
                maximum=MAX_RUNTIME_TRACE_SAMPLES,
            ),
            state_before=T104RuntimeStateReceipt.from_dict(document["state_before"]),
            feedback=tuple(
                T104FeedbackReceipt.from_dict(item)
                for item in cast(list[object], document["feedback"])
            ),
            state_after=T104RuntimeStateReceipt.from_dict(document["state_after"]),
            status=document["status"],
            success=document["success"],
            settled=document["settled"],
            fault_kind=document["fault_kind"],
        )
        if result.to_dict() != document:
            raise T104RuntimeError("trace receipt is not in canonical form")
        return result


class InMemoryT104Runtime:
    """Ordered deterministic emulator with no transport or serialization API."""

    __slots__ = (
        "_config",
        "_config_sha256",
        "_current_pose",
        "_next_ordinal",
        "_attempted_count",
        "_completed_count",
        "_trace_count",
        "_connected",
        "_reset_generation",
        "_fault_latched",
        "_terminal",
        "_lock",
        "_fault_by_ordinal",
    )

    def __init__(self, config: T104RuntimeConfig) -> None:
        if type(config) is not T104RuntimeConfig:
            raise TypeError("config must be exactly T104RuntimeConfig")
        # Round-trip through the strict parser to reject constructor-bypassed
        # objects before snapshotting the immutable configuration.
        self._config = T104RuntimeConfig.from_dict(config.to_dict())
        self._config_sha256 = self._config.canonical_sha256
        self._current_pose = self._config.initial_pose
        self._next_ordinal = 0
        self._attempted_count = 0
        self._completed_count = 0
        self._trace_count = 0
        self._connected = True
        self._reset_generation = 0
        self._fault_latched: str | None = None
        self._terminal = False
        self._lock = threading.Lock()
        self._fault_by_ordinal = {
            fault.sequence_ordinal: fault.fault_kind
            for fault in self._config.fault_injections
        }

    @property
    def config(self) -> T104RuntimeConfig:
        return self._config

    def state_receipt(self) -> T104RuntimeStateReceipt:
        with self._lock:
            return self._state_receipt_unlocked()

    def _state_receipt_unlocked(self) -> T104RuntimeStateReceipt:
        return T104RuntimeStateReceipt(
            session_id=self._config.session_id,
            config_sha256=self._config_sha256,
            next_sequence_ordinal=self._next_ordinal,
            current_pose=self._current_pose,
            attempted_command_count=self._attempted_count,
            completed_command_count=self._completed_count,
            trace_count=self._trace_count,
            connected=self._connected,
            reset_generation=self._reset_generation,
            fault_latched=self._fault_latched,
            terminal=self._terminal,
        )

    def execute(
        self, command: NonWireT104Command | Mapping[str, Any]
    ) -> T104TraceReceipt:
        """Attempt one pre-bound command; no bytes or hardware calls can occur."""

        if type(command) is NonWireT104Command:
            validated = NonWireT104Command.from_dict(command.to_dict())
        elif type(command) is dict:
            validated = NonWireT104Command.from_dict(command)
        else:
            raise TypeError("command must be NonWireT104Command or exactly dict")

        with self._lock:
            if self._fault_latched is not None:
                raise T104RuntimeError(
                    f"runtime fault {self._fault_latched} is latched; no continuation allowed"
                )
            if not self._connected:
                raise T104RuntimeError("runtime is disconnected")
            if self._terminal:
                raise T104RuntimeError("runtime schedule is terminal; replay rejected")
            if validated.session_id != self._config.session_id:
                raise T104RuntimeError("command session mismatch")
            if validated.sequence_ordinal != self._next_ordinal:
                raise T104RuntimeError(
                    "command ordinal mismatch; reorder/replay/skip rejected"
                )
            expected = self._config.schedule[self._next_ordinal]
            if expected.sequence_ordinal != self._next_ordinal:
                raise T104RuntimeError("internal schedule ordinal mismatch")
            if validated.command_id != expected.command_id:
                raise T104RuntimeError("command_id mismatch")
            if validated.expected_previous_pose_sha256 != controller_pose_sha256(
                self._current_pose
            ):
                raise T104RuntimeError("expected previous pose does not match runtime state")
            if (
                validated.expected_previous_pose_sha256
                != expected.expected_previous_pose_sha256
            ):
                raise T104RuntimeError("expected previous pose hash disagrees with schedule")
            if validated.route_sha256 != expected.route_sha256:
                raise T104RuntimeError("route hash mismatch")
            if validated.joint_result_sha256 != expected.joint_result_sha256:
                raise T104RuntimeError("joint-result hash mismatch")
            if validated.target.canonical_sha256 != expected.target_sha256:
                raise T104RuntimeError("target hash mismatch")
            command_hash = validated.canonical_sha256
            if command_hash != expected.command_sha256:
                raise T104RuntimeError("command hash mismatch")

            before = self._state_receipt_unlocked()
            try:
                trace = simulate_t104_trace(
                    self._current_pose,
                    validated.target.pose,
                    spd_coefficient=validated.spd_coefficient,
                    maximum_samples=self._config.maximum_trace_samples,
                )
            except ControllerSimulationError as exc:
                raise T104RuntimeError("controller trace simulation failed closed") from exc
            trace_hash = _simulation_trace_sha256(trace)
            fault_kind = self._fault_by_ordinal.get(self._next_ordinal)
            feedback, achieved_pose, connected, reset_increment = self._settle_feedback(
                validated,
                command_hash=command_hash,
                fault_kind=fault_kind,
                trace_samples=tuple(sample.pose for sample in trace.samples),
            )

            self._attempted_count += 1
            self._trace_count += 1
            self._current_pose = achieved_pose
            self._connected = connected
            self._reset_generation += reset_increment
            if fault_kind is None:
                self._completed_count += 1
                self._next_ordinal += 1
                self._terminal = self._next_ordinal == len(self._config.schedule)
                status = "COMPLETED_SETTLED"
                success = True
            else:
                self._fault_latched = fault_kind
                self._terminal = True
                status = f"FAULT_{fault_kind}"
                success = False
            after = self._state_receipt_unlocked()
            receipt = T104TraceReceipt(
                session_id=self._config.session_id,
                config_sha256=self._config_sha256,
                schedule_sha256=self._config.schedule_sha256,
                command_sha256=command_hash,
                sequence_ordinal=validated.sequence_ordinal,
                route_sha256=validated.route_sha256,
                joint_result_sha256=validated.joint_result_sha256,
                simulator_trace_sha256=trace_hash,
                simulator_sample_count=len(trace.samples),
                state_before=before,
                feedback=feedback,
                state_after=after,
                status=status,
                success=success,
                settled=success,
                fault_kind=fault_kind,
            )
            # Exercise the standalone receipt parser before releasing evidence.
            return T104TraceReceipt.from_dict(receipt.to_dict())

    def execute_many(
        self, commands: Sequence[NonWireT104Command | Mapping[str, Any]]
    ) -> tuple[T104TraceReceipt, ...]:
        """Execute a bounded prefix and stop immediately after a fault receipt."""

        if isinstance(commands, (str, bytes)) or not isinstance(commands, Sequence):
            raise TypeError("commands must be a sequence")
        if len(commands) > MAX_RUNTIME_COMMANDS:
            raise T104RuntimeError("command batch exceeds its runtime bound")
        receipts: list[T104TraceReceipt] = []
        for command in commands:
            receipt = self.execute(command)
            receipts.append(receipt)
            if not receipt.success:
                break
        return tuple(receipts)

    def _settle_feedback(
        self,
        command: NonWireT104Command,
        *,
        command_hash: str,
        fault_kind: str | None,
        trace_samples: tuple[ControllerPose, ...],
    ) -> tuple[tuple[T104FeedbackReceipt, ...], ControllerPose, bool, int]:
        target = command.target.pose
        previous = self._current_pose
        connected = fault_kind != "DISCONNECT"
        reset_increment = 1 if fault_kind == "RESET" else 0

        if fault_kind is None:
            observed = [target] * self._config.settle_sample_count
        elif fault_kind == "STALL":
            observed = [previous] * self._config.settle_sample_count
        elif fault_kind == "RESET":
            observed = [self._config.initial_pose] * self._config.settle_sample_count
        elif fault_kind == "DISCONNECT":
            observed = [previous] * self._config.settle_sample_count
        elif fault_kind == "TIMEOUT":
            midpoint = trace_samples[(len(trace_samples) - 1) // 2]
            observed = [midpoint] * self._config.settle_sample_count
        elif fault_kind == "NONSETTLE":
            offset = self._config.settle_tolerance_mixed_units * 2.0
            observed = [
                ControllerPose(
                    target.x_mm + (offset if index % 2 == 0 else -offset),
                    target.y_mm,
                    target.z_mm,
                    target.pitch_rad,
                    target.roll_rad,
                    target.gripper_raw_rad,
                )
                for index in range(self._config.settle_sample_count)
            ]
        else:  # pragma: no cover - config validation makes this unreachable
            raise T104RuntimeError("unrecognized fault injection")

        receipts = tuple(
            T104FeedbackReceipt(
                session_id=self._config.session_id,
                config_sha256=self._config_sha256,
                command_sha256=command_hash,
                sequence_ordinal=command.sequence_ordinal,
                feedback_ordinal=index,
                phase="SETTLE",
                observed_pose=pose,
                target_error_max_mixed_units=_pose_error(pose, target),
                settled=fault_kind is None,
                connected=connected,
                reset_generation=self._reset_generation + reset_increment,
                fault_kind=fault_kind,
            )
            for index, pose in enumerate(observed)
        )
        achieved = target if fault_kind is None else observed[-1]
        return receipts, achieved, connected, reset_increment


__all__ = [
    "InMemoryT104Runtime",
    "MAX_RUNTIME_COMMANDS",
    "MAX_RUNTIME_TRACE_SAMPLES",
    "MAX_SETTLE_SAMPLES",
    "NON_WIRE_T104_COMMAND_SCHEMA",
    "NON_WIRE_T104_TARGET_SCHEMA",
    "NonWireT104Command",
    "NonWireT104Target",
    "PHYSICAL_AUTHORITY_ZERO",
    "T104FaultInjection",
    "T104FeedbackReceipt",
    "T104RuntimeConfig",
    "T104RuntimeError",
    "T104RuntimeScheduleEntry",
    "T104RuntimeStateReceipt",
    "T104TraceReceipt",
    "T104_RUNTIME_CONFIG_SCHEMA",
    "T104_RUNTIME_FAULT_SCHEMA",
    "T104_RUNTIME_FEEDBACK_SCHEMA",
    "T104_RUNTIME_SCHEDULE_ENTRY_SCHEMA",
    "T104_RUNTIME_SCHEDULE_SCHEMA",
    "T104_RUNTIME_STATE_SCHEMA",
    "T104_RUNTIME_TRACE_SCHEMA",
    "controller_pose_sha256",
]

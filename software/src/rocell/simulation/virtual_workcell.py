"""Deterministic, zero-I/O foundations for a virtual RoCell workcell.

This module deliberately models software behavior rather than physical truth.
It never imports a serial, camera, network, or controller adapter, and none of
its types are accepted by the live-arm permit boundary.  The application layer
may use these values to exercise initialization, sequencing, fault handling,
and keyboard/Android outcome verification before hardware is available.

The arm plant consumes already-accepted *joint* waypoints.  It does not derive
or claim Waveshare T=104 Cartesian commands because the physical relationship
between the URDF frames and the controller's ``R_ctrl`` frame is not yet known.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
import math
import re
from types import MappingProxyType
from typing import Any, Mapping, Sequence


VIRTUAL_ARM_JOINT_NAMES: tuple[str, ...] = (
    "base_link_to_link1",
    "link1_to_link2",
    "link2_to_link3",
    "link3_to_link4",
    "link4_to_link5",
)
MAX_VIRTUAL_TICK = (1 << 63) - 1
MAX_VIRTUAL_FAULT_TRIGGERS = 256
MAX_VIRTUAL_LEDGER_EVENTS = 100_000
MAX_VIRTUAL_CONTACT_ACTIVATIONS = 4
MAX_VIRTUAL_CONTACT_REGIONS = 512
MAX_VIRTUAL_CONTACT_POLYGON_VERTICES = 64
MAX_VIRTUAL_BOARD_COORDINATE_MM = 100_000.0

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_TOKEN_ISSUER = object()


class VirtualWorkcellError(RuntimeError):
    """Base error for the deterministic virtual-workcell boundary."""


class VirtualValidationError(VirtualWorkcellError, ValueError):
    """A virtual scenario value is malformed or internally inconsistent."""


class VirtualLifecycleError(VirtualWorkcellError):
    """A component operation is invalid in its current lifecycle state."""


class VirtualResourceLimitError(VirtualWorkcellError):
    """A bounded virtual resource would exceed its configured maximum."""


def _name(value: object, label: str, *, maximum: int = 256) -> str:
    if not isinstance(value, str) or not value.strip():
        raise VirtualValidationError(f"{label} must be non-empty text")
    parsed = value.strip()
    if len(parsed) > maximum:
        raise VirtualValidationError(f"{label} exceeds {maximum} characters")
    if any(ord(character) < 32 for character in parsed):
        raise VirtualValidationError(f"{label} contains a control character")
    return parsed


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256_PATTERN.fullmatch(value) is None:
        raise VirtualValidationError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _integer(
    value: object,
    label: str,
    *,
    minimum: int = 0,
    maximum: int = MAX_VIRTUAL_TICK,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise VirtualValidationError(f"{label} must be an integer")
    if not minimum <= value <= maximum:
        raise VirtualValidationError(
            f"{label} must be within [{minimum}, {maximum}]"
        )
    return value


def _finite(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise VirtualValidationError(f"{label} must be a finite number")
    parsed = float(value)
    if not math.isfinite(parsed):
        raise VirtualValidationError(f"{label} must be a finite number")
    return parsed


def _stable_hash(value: Mapping[str, Any]) -> str:
    try:
        payload = json.dumps(
            dict(value),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise VirtualValidationError(
            f"Virtual evidence is not canonical JSON: {exc}"
        ) from exc
    return hashlib.sha256(payload).hexdigest()


def _authority() -> dict[str, object]:
    """Return a detached authority declaration for serialized evidence."""

    return {
        "simulation_only": True,
        "hardware_accessed": False,
        "hardware_commands_generated": 0,
        "physical_release_effect": "NONE",
        "live_motion_authorized": False,
        "contact_authorized": False,
    }


def _semantic_character(value: object) -> str:
    if not isinstance(value, str) or len(value) != 1:
        raise VirtualValidationError(
            "expected semantic character must be exactly one Unicode code point"
        )
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise VirtualValidationError(
            "expected semantic character must be valid UTF-8"
        ) from exc
    return value


class VirtualClock:
    """Explicit integer-tick clock with no wall-clock dependency."""

    __slots__ = ("_tick",)

    def __init__(self, initial_tick: int = 0) -> None:
        self._tick = _integer(initial_tick, "initial virtual tick")

    @property
    def tick(self) -> int:
        return self._tick

    def advance(self, delta_ticks: int = 1) -> int:
        delta = _integer(
            delta_ticks,
            "virtual tick delta",
            minimum=1,
            maximum=MAX_VIRTUAL_TICK,
        )
        if self._tick > MAX_VIRTUAL_TICK - delta:
            raise VirtualResourceLimitError("virtual clock would overflow its tick bound")
        self._tick += delta
        return self._tick

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "rocell.virtual_clock.v1",
            "tick": self.tick,
            "time_source": "EXPLICIT_INTEGER_TICKS_ONLY",
            "authority": _authority(),
        }


class VirtualFaultKind(str, Enum):
    """Stable effects understood by the virtual application boundary."""

    ARM_CONNECT_FAILURE = "ARM_CONNECT_FAILURE"
    ARM_REFERENCE_FAILURE = "ARM_REFERENCE_FAILURE"
    ARM_STALL = "ARM_STALL"
    ARM_FEEDBACK_STALE = "ARM_FEEDBACK_STALE"
    CAMERA_UNAVAILABLE = "CAMERA_UNAVAILABLE"
    CAMERA_TAG_LOSS = "CAMERA_TAG_LOSS"
    KEYBOARD_MISSED_CONTACT = "KEYBOARD_MISSED_CONTACT"
    KEYBOARD_DOUBLE_CONTACT = "KEYBOARD_DOUBLE_CONTACT"
    ANDROID_MISSED_CONTACT = "ANDROID_MISSED_CONTACT"
    ANDROID_WRONG_UI_STATE = "ANDROID_WRONG_UI_STATE"
    DEVICE_FOCUS_LOST = "DEVICE_FOCUS_LOST"


@dataclass(frozen=True, slots=True)
class VirtualFaultTrigger:
    """One declarative fault matched to a deterministic operation occurrence."""

    trigger_id: str
    kind: VirtualFaultKind
    component: str
    operation: str
    occurrence: int = 1
    action_index: int | None = None
    target_id: str | None = None
    waypoint_sequence: int | None = None
    parameter: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "trigger_id", _name(self.trigger_id, "trigger id"))
        if not isinstance(self.kind, VirtualFaultKind):
            try:
                object.__setattr__(self, "kind", VirtualFaultKind(self.kind))
            except (TypeError, ValueError) as exc:
                raise VirtualValidationError("fault kind is unsupported") from exc
        object.__setattr__(self, "component", _name(self.component, "fault component"))
        object.__setattr__(self, "operation", _name(self.operation, "fault operation"))
        object.__setattr__(
            self,
            "occurrence",
            _integer(self.occurrence, "fault occurrence", minimum=1, maximum=1_000_000),
        )
        for field_name in ("action_index", "waypoint_sequence"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(
                    self,
                    field_name,
                    _integer(value, field_name, maximum=1_000_000_000),
                )
        if self.target_id is not None:
            object.__setattr__(self, "target_id", _name(self.target_id, "target id"))
        if self.parameter is not None:
            object.__setattr__(
                self,
                "parameter",
                _name(self.parameter, "fault parameter", maximum=512),
            )

    @property
    def selector(self) -> tuple[object, ...]:
        return (
            self.component,
            self.operation,
            self.occurrence,
            self.action_index,
            self.target_id,
            self.waypoint_sequence,
        )

    def matches(
        self,
        *,
        component: str,
        operation: str,
        occurrence: int,
        action_index: int | None,
        target_id: str | None,
        waypoint_sequence: int | None,
    ) -> bool:
        return (
            self.component == component
            and self.operation == operation
            and self.occurrence == occurrence
            and (self.action_index is None or self.action_index == action_index)
            and (self.target_id is None or self.target_id == target_id)
            and (
                self.waypoint_sequence is None
                or self.waypoint_sequence == waypoint_sequence
            )
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "trigger_id": self.trigger_id,
            "kind": self.kind.value,
            "component": self.component,
            "operation": self.operation,
            "occurrence": self.occurrence,
            "action_index": self.action_index,
            "target_id": self.target_id,
            "waypoint_sequence": self.waypoint_sequence,
            "parameter": self.parameter,
        }


@dataclass(frozen=True, slots=True)
class VirtualFaultScript:
    """Immutable fault definition and immutable one-use consumption state.

    :meth:`match_once` returns a new script value when it consumes a trigger.
    Declaration order is the deterministic precedence rule for overlapping
    generic and specific selectors. Exact duplicate selectors are rejected.
    """

    script_id: str
    triggers: tuple[VirtualFaultTrigger, ...] = ()
    consumed_trigger_ids: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        object.__setattr__(self, "script_id", _name(self.script_id, "fault script id"))
        triggers = tuple(self.triggers)
        if len(triggers) > MAX_VIRTUAL_FAULT_TRIGGERS:
            raise VirtualResourceLimitError(
                f"fault script exceeds {MAX_VIRTUAL_FAULT_TRIGGERS} triggers"
            )
        if any(not isinstance(trigger, VirtualFaultTrigger) for trigger in triggers):
            raise TypeError("fault script triggers must be VirtualFaultTrigger values")
        ids = tuple(trigger.trigger_id for trigger in triggers)
        if len(ids) != len(set(ids)):
            raise VirtualValidationError("fault trigger ids must be unique")
        selectors = tuple(trigger.selector for trigger in triggers)
        if len(selectors) != len(set(selectors)):
            raise VirtualValidationError("fault trigger selectors must be unique")
        consumed = frozenset(self.consumed_trigger_ids)
        if not consumed.issubset(ids):
            raise VirtualValidationError(
                "consumed fault ids must belong to the fault definition"
            )
        object.__setattr__(self, "triggers", triggers)
        object.__setattr__(self, "consumed_trigger_ids", consumed)

    @property
    def definition_hash(self) -> str:
        return _stable_hash(
            {
                "schema": "rocell.virtual_fault_script_definition.v1",
                "script_id": self.script_id,
                "triggers": [trigger.to_dict() for trigger in self.triggers],
                "authority": _authority(),
            }
        )

    @property
    def state_hash(self) -> str:
        return _stable_hash(self.to_dict())

    @property
    def unconsumed_trigger_ids(self) -> tuple[str, ...]:
        return tuple(
            trigger.trigger_id
            for trigger in self.triggers
            if trigger.trigger_id not in self.consumed_trigger_ids
        )

    def match_once(
        self,
        *,
        component: str,
        operation: str,
        occurrence: int,
        action_index: int | None = None,
        target_id: str | None = None,
        waypoint_sequence: int | None = None,
    ) -> tuple[VirtualFaultTrigger | None, VirtualFaultScript]:
        selected_component = _name(component, "fault match component")
        selected_operation = _name(operation, "fault match operation")
        selected_occurrence = _integer(
            occurrence,
            "fault match occurrence",
            minimum=1,
            maximum=1_000_000,
        )
        if action_index is not None:
            action_index = _integer(action_index, "action index", maximum=1_000_000_000)
        if target_id is not None:
            target_id = _name(target_id, "target id")
        if waypoint_sequence is not None:
            waypoint_sequence = _integer(
                waypoint_sequence,
                "waypoint sequence",
                maximum=1_000_000_000,
            )
        for trigger in self.triggers:
            if trigger.trigger_id in self.consumed_trigger_ids:
                continue
            if trigger.matches(
                component=selected_component,
                operation=selected_operation,
                occurrence=selected_occurrence,
                action_index=action_index,
                target_id=target_id,
                waypoint_sequence=waypoint_sequence,
            ):
                updated = VirtualFaultScript(
                    self.script_id,
                    self.triggers,
                    self.consumed_trigger_ids | {trigger.trigger_id},
                )
                return trigger, updated
        return None, self

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "rocell.virtual_fault_script.v1",
            "script_id": self.script_id,
            "definition_hash": self.definition_hash,
            "trigger_count": len(self.triggers),
            "triggers": [trigger.to_dict() for trigger in self.triggers],
            "consumed_trigger_ids": sorted(self.consumed_trigger_ids),
            "unconsumed_trigger_ids": list(self.unconsumed_trigger_ids),
            "authority": _authority(),
        }


class VirtualExecutionToken:
    """Opaque zero-authority binding for exactly one virtual mission input set."""

    __slots__ = (
        "_context_hash",
        "_plan_hash",
        "_trajectory_hash",
        "_scenario_hash",
        "_fault_script_hash",
    )

    def __init__(
        self,
        *,
        _issuer: object,
        context_hash: str,
        plan_hash: str,
        trajectory_hash: str,
        scenario_hash: str,
        fault_script_hash: str,
    ) -> None:
        if _issuer is not _TOKEN_ISSUER:
            raise VirtualValidationError(
                "virtual execution tokens may only be issued by the module factory"
            )
        self._context_hash = _digest(context_hash, "context hash")
        self._plan_hash = _digest(plan_hash, "plan hash")
        self._trajectory_hash = _digest(trajectory_hash, "trajectory hash")
        self._scenario_hash = _digest(scenario_hash, "scenario hash")
        self._fault_script_hash = _digest(fault_script_hash, "fault script hash")

    @property
    def context_hash(self) -> str:
        return self._context_hash

    @property
    def plan_hash(self) -> str:
        return self._plan_hash

    @property
    def trajectory_hash(self) -> str:
        return self._trajectory_hash

    @property
    def scenario_hash(self) -> str:
        return self._scenario_hash

    @property
    def fault_script_hash(self) -> str:
        return self._fault_script_hash

    @property
    def token_hash(self) -> str:
        return _stable_hash(
            {
                "schema": "rocell.virtual_execution_token.v1",
                "bindings": self.bindings,
                "authority": _authority(),
            }
        )

    @property
    def bindings(self) -> dict[str, str]:
        return {
            "context_hash": self.context_hash,
            "plan_hash": self.plan_hash,
            "trajectory_hash": self.trajectory_hash,
            "scenario_hash": self.scenario_hash,
            "fault_script_hash": self.fault_script_hash,
        }

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "rocell.virtual_execution_token.v1",
            "token_hash": self.token_hash,
            "bindings": self.bindings,
            "authority": _authority(),
        }


def issue_virtual_execution_token(
    *,
    context_hash: str,
    plan_hash: str,
    trajectory_hash: str,
    scenario_hash: str,
    fault_script_hash: str,
) -> VirtualExecutionToken:
    """Issue a virtual-only binding; this never evaluates physical authority."""

    return VirtualExecutionToken(
        _issuer=_TOKEN_ISSUER,
        context_hash=context_hash,
        plan_hash=plan_hash,
        trajectory_hash=trajectory_hash,
        scenario_hash=scenario_hash,
        fault_script_hash=fault_script_hash,
    )


@dataclass(frozen=True, slots=True)
class VirtualJointWaypoint:
    """One ordered virtual command containing exactly the five arm joints."""

    sequence: int
    joint_positions_rad: tuple[tuple[str, float], ...]
    action_index: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "sequence",
            _integer(self.sequence, "waypoint sequence", maximum=1_000_000_000),
        )
        if self.action_index is not None:
            object.__setattr__(
                self,
                "action_index",
                _integer(
                    self.action_index,
                    "waypoint action index",
                    maximum=1_000_000_000,
                ),
            )
        try:
            pairs = tuple(self.joint_positions_rad)
        except TypeError as exc:
            raise VirtualValidationError(
                "joint_positions_rad must contain name/value pairs"
            ) from exc
        parsed: dict[str, float] = {}
        for item in pairs:
            if not isinstance(item, (tuple, list)) or len(item) != 2:
                raise VirtualValidationError(
                    "joint_positions_rad must contain name/value pairs"
                )
            name = _name(item[0], "joint name")
            if name in parsed:
                raise VirtualValidationError(f"duplicate joint position {name!r}")
            parsed[name] = _finite(item[1], f"joint position {name}")
        if set(parsed) != set(VIRTUAL_ARM_JOINT_NAMES):
            missing = sorted(set(VIRTUAL_ARM_JOINT_NAMES) - set(parsed))
            extra = sorted(set(parsed) - set(VIRTUAL_ARM_JOINT_NAMES))
            raise VirtualValidationError(
                f"virtual waypoint joint set mismatch; missing={missing}, extra={extra}"
            )
        object.__setattr__(
            self,
            "joint_positions_rad",
            tuple((name, parsed[name]) for name in VIRTUAL_ARM_JOINT_NAMES),
        )

    @classmethod
    def from_mapping(
        cls,
        sequence: int,
        joint_positions_rad: Mapping[str, float],
        *,
        action_index: int | None = None,
    ) -> VirtualJointWaypoint:
        if not isinstance(joint_positions_rad, Mapping):
            raise TypeError("joint_positions_rad must be a mapping")
        return cls(sequence, tuple(joint_positions_rad.items()), action_index)

    @property
    def positions_by_name(self) -> Mapping[str, float]:
        return MappingProxyType(dict(self.joint_positions_rad))

    @property
    def waypoint_hash(self) -> str:
        return _stable_hash(self.to_dict())

    def to_dict(self) -> dict[str, object]:
        return {
            "sequence": self.sequence,
            "action_index": self.action_index,
            "joint_positions_rad": dict(self.joint_positions_rad),
        }


class VirtualArmLifecycle(str, Enum):
    CREATED = "CREATED"
    CONNECTED = "CONNECTED"
    REFERENCED = "REFERENCED"
    READY = "READY"
    EXECUTING = "EXECUTING"
    COMPLETE = "COMPLETE"
    FAULT = "FAULT"
    CLOSED = "CLOSED"


@dataclass(frozen=True, slots=True)
class VirtualArmFeedback:
    """A deterministic plant snapshot, not a Waveshare T=1051 response."""

    tick: int
    lifecycle: VirtualArmLifecycle
    joint_positions_rad: tuple[tuple[str, float], ...]
    last_waypoint_sequence: int | None
    last_action_index: int | None
    virtual_commands_executed: int
    plant_state_hash: str

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "rocell.virtual_arm_feedback.v1",
            "tick": self.tick,
            "lifecycle": self.lifecycle.value,
            "joint_positions_rad": dict(self.joint_positions_rad),
            "last_waypoint_sequence": self.last_waypoint_sequence,
            "last_action_index": self.last_action_index,
            "virtual_commands_executed": self.virtual_commands_executed,
            "hardware_commands_generated": 0,
            "plant_state_hash": self.plant_state_hash,
            "controller_protocol": "NOT_T1051",
            "authority": _authority(),
        }


class VirtualArmPlant:
    """Stateful joint-level arm plant driven only by virtual execution tokens."""

    __slots__ = (
        "_token",
        "_clock",
        "_bounds",
        "_positions",
        "_lifecycle",
        "_history",
        "_last_waypoint_sequence",
        "_last_action_index",
        "_virtual_commands_executed",
        "_fault_reason",
    )

    def __init__(
        self,
        *,
        token: VirtualExecutionToken,
        clock: VirtualClock,
        initial_joint_positions_rad: Mapping[str, float],
        joint_bounds_rad: Mapping[str, Sequence[float]],
    ) -> None:
        if not isinstance(token, VirtualExecutionToken):
            raise TypeError("token must be a VirtualExecutionToken")
        if not isinstance(clock, VirtualClock):
            raise TypeError("clock must be a VirtualClock")
        self._token = token
        self._clock = clock
        self._bounds = self._validate_bounds(joint_bounds_rad)
        self._positions = self._validate_positions(initial_joint_positions_rad)
        self._lifecycle = VirtualArmLifecycle.CREATED
        self._history = [self._lifecycle]
        self._last_waypoint_sequence: int | None = None
        self._last_action_index: int | None = None
        self._virtual_commands_executed = 0
        self._fault_reason: str | None = None

    @staticmethod
    def _validate_bounds(
        bounds: Mapping[str, Sequence[float]],
    ) -> Mapping[str, tuple[float, float]]:
        if not isinstance(bounds, Mapping):
            raise TypeError("joint_bounds_rad must be a mapping")
        if set(bounds) != set(VIRTUAL_ARM_JOINT_NAMES):
            raise VirtualValidationError(
                "joint bounds must cover exactly the five virtual arm joints"
            )
        parsed: dict[str, tuple[float, float]] = {}
        for name in VIRTUAL_ARM_JOINT_NAMES:
            pair = bounds[name]
            if not isinstance(pair, (tuple, list)) or len(pair) != 2:
                raise VirtualValidationError(f"joint bounds for {name} must be a pair")
            lower = _finite(pair[0], f"{name} lower bound")
            upper = _finite(pair[1], f"{name} upper bound")
            if lower >= upper:
                raise VirtualValidationError(
                    f"joint bounds for {name} must be strictly increasing"
                )
            parsed[name] = (lower, upper)
        return MappingProxyType(parsed)

    def _validate_positions(
        self,
        positions: Mapping[str, float],
    ) -> dict[str, float]:
        if not isinstance(positions, Mapping):
            raise TypeError("joint positions must be a mapping")
        if set(positions) != set(VIRTUAL_ARM_JOINT_NAMES):
            raise VirtualValidationError(
                "joint positions must cover exactly the five virtual arm joints"
            )
        parsed: dict[str, float] = {}
        for name in VIRTUAL_ARM_JOINT_NAMES:
            value = _finite(positions[name], f"joint position {name}")
            lower, upper = self._bounds[name]
            if not lower <= value <= upper:
                raise VirtualValidationError(
                    f"joint position {name}={value} leaves [{lower}, {upper}]"
                )
            parsed[name] = value
        return parsed

    @property
    def lifecycle(self) -> VirtualArmLifecycle:
        return self._lifecycle

    @property
    def lifecycle_history(self) -> tuple[VirtualArmLifecycle, ...]:
        return tuple(self._history)

    @property
    def virtual_commands_executed(self) -> int:
        return self._virtual_commands_executed

    @property
    def last_waypoint_sequence(self) -> int | None:
        return self._last_waypoint_sequence

    @property
    def last_action_index(self) -> int | None:
        return self._last_action_index

    @property
    def joint_positions_rad(self) -> Mapping[str, float]:
        return MappingProxyType(dict(self._positions))

    @property
    def fault_reason(self) -> str | None:
        return self._fault_reason

    @property
    def state_hash(self) -> str:
        return _stable_hash(
            {
                "schema": "rocell.virtual_arm_plant_state.v1",
                "token_hash": self._token.token_hash,
                "lifecycle": self.lifecycle.value,
                "lifecycle_history": [state.value for state in self._history],
                "joint_positions_rad": dict(self._positions),
                "last_waypoint_sequence": self.last_waypoint_sequence,
                "last_action_index": self.last_action_index,
                "virtual_commands_executed": self.virtual_commands_executed,
                "fault_reason": self.fault_reason,
                "authority": _authority(),
            }
        )

    def _transition(self, target: VirtualArmLifecycle) -> None:
        self._lifecycle = target
        self._history.append(target)
        self._clock.advance()

    def _require(self, *states: VirtualArmLifecycle) -> None:
        if self.lifecycle not in states:
            expected = ", ".join(state.value for state in states)
            raise VirtualLifecycleError(
                f"virtual arm is {self.lifecycle.value}; expected one of {expected}"
            )

    def connect(self) -> None:
        self._require(VirtualArmLifecycle.CREATED)
        self._transition(VirtualArmLifecycle.CONNECTED)

    def reference(self) -> None:
        self._require(VirtualArmLifecycle.CONNECTED)
        self._transition(VirtualArmLifecycle.REFERENCED)

    def mark_ready(self) -> None:
        self._require(VirtualArmLifecycle.REFERENCED)
        self._transition(VirtualArmLifecycle.READY)

    def execute_waypoint(self, waypoint: VirtualJointWaypoint) -> VirtualArmFeedback:
        if not isinstance(waypoint, VirtualJointWaypoint):
            raise TypeError("waypoint must be a VirtualJointWaypoint")
        self._require(VirtualArmLifecycle.READY, VirtualArmLifecycle.EXECUTING)
        if (
            self.last_waypoint_sequence is not None
            and waypoint.sequence <= self.last_waypoint_sequence
        ):
            self.fault("NON_MONOTONIC_WAYPOINT_SEQUENCE")
            raise VirtualValidationError(
                "virtual waypoint sequence must increase strictly"
            )
        try:
            positions = self._validate_positions(waypoint.positions_by_name)
        except (TypeError, VirtualValidationError):
            self.fault("WAYPOINT_OUTSIDE_VIRTUAL_JOINT_CONTRACT")
            raise
        self._positions = positions
        self._last_waypoint_sequence = waypoint.sequence
        self._last_action_index = waypoint.action_index
        self._virtual_commands_executed += 1
        if self.lifecycle is VirtualArmLifecycle.READY:
            self._transition(VirtualArmLifecycle.EXECUTING)
        else:
            self._clock.advance()
        return self.feedback()

    def complete(self) -> None:
        self._require(VirtualArmLifecycle.EXECUTING)
        self._transition(VirtualArmLifecycle.COMPLETE)

    def fault(self, reason: str) -> None:
        if self.lifecycle in (VirtualArmLifecycle.FAULT, VirtualArmLifecycle.CLOSED):
            raise VirtualLifecycleError(
                f"cannot fault virtual arm from {self.lifecycle.value}"
            )
        self._fault_reason = _name(reason, "virtual arm fault reason")
        self._transition(VirtualArmLifecycle.FAULT)

    def close(self) -> None:
        if self.lifecycle is VirtualArmLifecycle.CLOSED:
            raise VirtualLifecycleError("virtual arm is already closed")
        self._transition(VirtualArmLifecycle.CLOSED)

    def feedback(self) -> VirtualArmFeedback:
        self._require(
            VirtualArmLifecycle.CONNECTED,
            VirtualArmLifecycle.REFERENCED,
            VirtualArmLifecycle.READY,
            VirtualArmLifecycle.EXECUTING,
            VirtualArmLifecycle.COMPLETE,
            VirtualArmLifecycle.FAULT,
        )
        return VirtualArmFeedback(
            tick=self._clock.tick,
            lifecycle=self.lifecycle,
            joint_positions_rad=tuple(
                (name, self._positions[name]) for name in VIRTUAL_ARM_JOINT_NAMES
            ),
            last_waypoint_sequence=self.last_waypoint_sequence,
            last_action_index=self.last_action_index,
            virtual_commands_executed=self.virtual_commands_executed,
            plant_state_hash=self.state_hash,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "rocell.virtual_arm_plant.v1",
            "token_hash": self._token.token_hash,
            "lifecycle": self.lifecycle.value,
            "lifecycle_history": [state.value for state in self.lifecycle_history],
            "joint_positions_rad": dict(self._positions),
            "joint_bounds_rad": {
                name: list(self._bounds[name]) for name in VIRTUAL_ARM_JOINT_NAMES
            },
            "last_waypoint_sequence": self.last_waypoint_sequence,
            "last_action_index": self.last_action_index,
            "virtual_commands_executed": self.virtual_commands_executed,
            "hardware_commands_generated": 0,
            "fault_reason": self.fault_reason,
            "state_hash": self.state_hash,
            "controller_cartesian_mapping": "NOT_IMPLEMENTED_R_CTRL_UNCORRELATED",
            "authority": _authority(),
        }


def _vector3(
    value: object,
    label: str,
    *,
    coordinate_bound: float | None = None,
) -> tuple[float, float, float]:
    """Parse one strict, finite three-vector without accepting strings."""

    if not isinstance(value, (tuple, list)) or len(value) != 3:
        raise VirtualValidationError(f"{label} must contain exactly three numbers")
    parsed = tuple(_finite(component, f"{label}[{index}]") for index, component in enumerate(value))
    if coordinate_bound is not None and any(
        abs(component) > coordinate_bound for component in parsed
    ):
        raise VirtualValidationError(
            f"{label} leaves +/-{coordinate_bound} millimetres"
        )
    return parsed[0], parsed[1], parsed[2]


def _unit_vector3(value: object, label: str) -> tuple[float, float, float]:
    parsed = _vector3(value, label)
    norm = math.sqrt(sum(component * component for component in parsed))
    if not math.isclose(norm, 1.0, rel_tol=0.0, abs_tol=1e-6):
        raise VirtualValidationError(f"{label} must be a unit vector")
    # Normalize only the tiny accepted floating-point error.  This keeps the
    # contact-angle calculation stable without silently accepting bad inputs.
    return tuple(component / norm for component in parsed)  # type: ignore[return-value]


def _orientation(
    first: tuple[float, float],
    second: tuple[float, float],
    third: tuple[float, float],
) -> float:
    return (second[0] - first[0]) * (third[1] - first[1]) - (
        second[1] - first[1]
    ) * (third[0] - first[0])


def _point_on_segment(
    point: tuple[float, float],
    first: tuple[float, float],
    second: tuple[float, float],
    *,
    tolerance: float = 1e-9,
) -> bool:
    return (
        abs(_orientation(first, second, point)) <= tolerance
        and min(first[0], second[0]) - tolerance
        <= point[0]
        <= max(first[0], second[0]) + tolerance
        and min(first[1], second[1]) - tolerance
        <= point[1]
        <= max(first[1], second[1]) + tolerance
    )


def _segments_intersect(
    first_a: tuple[float, float],
    first_b: tuple[float, float],
    second_a: tuple[float, float],
    second_b: tuple[float, float],
) -> bool:
    orientations = (
        _orientation(first_a, first_b, second_a),
        _orientation(first_a, first_b, second_b),
        _orientation(second_a, second_b, first_a),
        _orientation(second_a, second_b, first_b),
    )
    if (orientations[0] > 0 > orientations[1] or orientations[0] < 0 < orientations[1]) and (
        orientations[2] > 0 > orientations[3] or orientations[2] < 0 < orientations[3]
    ):
        return True
    return (
        _point_on_segment(second_a, first_a, first_b)
        or _point_on_segment(second_b, first_a, first_b)
        or _point_on_segment(first_a, second_a, second_b)
        or _point_on_segment(first_b, second_a, second_b)
    )


def _polygon_contains(
    polygon: tuple[tuple[float, float], ...],
    point: tuple[float, float],
) -> bool:
    """Return boundary-inclusive polygon membership for deterministic hit tests."""

    for index, first in enumerate(polygon):
        second = polygon[(index + 1) % len(polygon)]
        if _point_on_segment(point, first, second):
            return True
    inside = False
    x, y = point
    previous = polygon[-1]
    for current in polygon:
        if (current[1] > y) != (previous[1] > y):
            intersection_x = (
                (previous[0] - current[0])
                * (y - current[1])
                / (previous[1] - current[1])
                + current[0]
            )
            if x < intersection_x:
                inside = not inside
        previous = current
    return inside


@dataclass(frozen=True, slots=True)
class ContactEvent:
    """One achieved contact measurement expressed only in the board frame.

    The event intentionally contains no planned target identifier and no
    expected character.  Device truth is therefore a function of the achieved
    point, contact direction, dwell, current device state, and immutable model
    definition only.
    """

    action_index: int
    achieved_board_xyz_mm: tuple[float, float, float]
    achieved_contact_normal_board: tuple[float, float, float]
    dwell_ticks: int
    activation_count: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "action_index",
            _integer(self.action_index, "contact action index", maximum=1_000_000_000),
        )
        object.__setattr__(
            self,
            "achieved_board_xyz_mm",
            _vector3(
                self.achieved_board_xyz_mm,
                "achieved board XYZ",
                coordinate_bound=MAX_VIRTUAL_BOARD_COORDINATE_MM,
            ),
        )
        object.__setattr__(
            self,
            "achieved_contact_normal_board",
            _unit_vector3(
                self.achieved_contact_normal_board,
                "achieved contact normal",
            ),
        )
        object.__setattr__(
            self,
            "dwell_ticks",
            _integer(self.dwell_ticks, "contact dwell ticks", maximum=1_000_000_000),
        )
        object.__setattr__(
            self,
            "activation_count",
            _integer(
                self.activation_count,
                "contact activation count",
                maximum=MAX_VIRTUAL_CONTACT_ACTIVATIONS,
            ),
        )

    @property
    def event_hash(self) -> str:
        return _stable_hash(self.to_dict())

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "rocell.contact_event.v1",
            "action_index": self.action_index,
            "achieved_board_xyz_mm": list(self.achieved_board_xyz_mm),
            "achieved_contact_normal_board": list(
                self.achieved_contact_normal_board
            ),
            "dwell_ticks": self.dwell_ticks,
            "activation_count": self.activation_count,
            "coordinate_frame": "PLACEMAT_BOARD_MM",
            "planned_target_supplied": False,
            "expected_output_supplied": False,
            "authority": _authority(),
        }


@dataclass(frozen=True, slots=True)
class ContactRegion:
    """Immutable polygon and contact-policy truth for one device target."""

    region_id: str
    polygon_xy_mm: tuple[tuple[float, float], ...]
    surface_z_mm: float
    minimum_contact_depth_mm: float
    maximum_contact_depth_mm: float
    required_contact_normal_board: tuple[float, float, float]
    maximum_normal_angle_deg: float
    minimum_dwell_ticks: int
    maximum_dwell_ticks: int
    required_ui_state: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "region_id", _name(self.region_id, "contact region id"))
        try:
            raw_polygon = tuple(self.polygon_xy_mm)
        except TypeError as exc:
            raise VirtualValidationError("contact polygon must be a sequence") from exc
        if not 3 <= len(raw_polygon) <= MAX_VIRTUAL_CONTACT_POLYGON_VERTICES:
            raise VirtualValidationError(
                "contact polygon must contain between 3 and "
                f"{MAX_VIRTUAL_CONTACT_POLYGON_VERTICES} vertices"
            )
        polygon: list[tuple[float, float]] = []
        for index, point in enumerate(raw_polygon):
            if not isinstance(point, (tuple, list)) or len(point) != 2:
                raise VirtualValidationError(
                    f"contact polygon vertex {index} must contain XY"
                )
            x = _finite(point[0], f"contact polygon vertex {index} x")
            y = _finite(point[1], f"contact polygon vertex {index} y")
            if max(abs(x), abs(y)) > MAX_VIRTUAL_BOARD_COORDINATE_MM:
                raise VirtualValidationError("contact polygon leaves the board bound")
            polygon.append((x, y))
        if polygon[0] == polygon[-1]:
            raise VirtualValidationError(
                "contact polygon must not repeat its first closing vertex"
            )
        if len(set(polygon)) != len(polygon):
            raise VirtualValidationError("contact polygon vertices must be unique")
        signed_twice_area = sum(
            first[0] * second[1] - second[0] * first[1]
            for first, second in zip(polygon, polygon[1:] + polygon[:1])
        )
        if abs(signed_twice_area) <= 1e-9:
            raise VirtualValidationError("contact polygon must have non-zero area")
        segment_count = len(polygon)
        for first_index in range(segment_count):
            first_next = (first_index + 1) % segment_count
            for second_index in range(first_index + 1, segment_count):
                second_next = (second_index + 1) % segment_count
                if (
                    first_index == second_index
                    or first_next == second_index
                    or second_next == first_index
                ):
                    continue
                if _segments_intersect(
                    polygon[first_index],
                    polygon[first_next],
                    polygon[second_index],
                    polygon[second_next],
                ):
                    raise VirtualValidationError("contact polygon must be simple")
        object.__setattr__(self, "polygon_xy_mm", tuple(polygon))
        surface_z = _finite(self.surface_z_mm, "contact surface z")
        if abs(surface_z) > MAX_VIRTUAL_BOARD_COORDINATE_MM:
            raise VirtualValidationError("contact surface z leaves the board bound")
        object.__setattr__(self, "surface_z_mm", surface_z)
        minimum_depth = _finite(
            self.minimum_contact_depth_mm,
            "minimum contact depth",
        )
        maximum_depth = _finite(
            self.maximum_contact_depth_mm,
            "maximum contact depth",
        )
        if minimum_depth < 0.0 or maximum_depth < minimum_depth or maximum_depth > 1_000.0:
            raise VirtualValidationError(
                "contact depth interval must satisfy 0 <= minimum <= maximum <= 1000 mm"
            )
        object.__setattr__(self, "minimum_contact_depth_mm", minimum_depth)
        object.__setattr__(self, "maximum_contact_depth_mm", maximum_depth)
        object.__setattr__(
            self,
            "required_contact_normal_board",
            _unit_vector3(
                self.required_contact_normal_board,
                "required contact normal",
            ),
        )
        maximum_angle = _finite(
            self.maximum_normal_angle_deg,
            "maximum normal angle",
        )
        if not 0.0 <= maximum_angle <= 90.0:
            raise VirtualValidationError(
                "maximum normal angle must be within [0, 90] degrees"
            )
        object.__setattr__(self, "maximum_normal_angle_deg", maximum_angle)
        minimum_dwell = _integer(
            self.minimum_dwell_ticks,
            "minimum contact dwell ticks",
            maximum=1_000_000_000,
        )
        maximum_dwell = _integer(
            self.maximum_dwell_ticks,
            "maximum contact dwell ticks",
            maximum=1_000_000_000,
        )
        if maximum_dwell < minimum_dwell:
            raise VirtualValidationError(
                "maximum contact dwell ticks must be >= minimum dwell ticks"
            )
        object.__setattr__(self, "minimum_dwell_ticks", minimum_dwell)
        object.__setattr__(self, "maximum_dwell_ticks", maximum_dwell)
        if self.required_ui_state is not None:
            object.__setattr__(
                self,
                "required_ui_state",
                _name(self.required_ui_state, "required UI state"),
            )

    @property
    def region_hash(self) -> str:
        return _stable_hash(self.to_dict())

    def contains_xy(self, xy_mm: tuple[float, float]) -> bool:
        if not isinstance(xy_mm, (tuple, list)) or len(xy_mm) != 2:
            raise VirtualValidationError("contact query point must contain XY")
        point = (
            _finite(xy_mm[0], "contact query x"),
            _finite(xy_mm[1], "contact query y"),
        )
        return _polygon_contains(self.polygon_xy_mm, point)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "rocell.contact_region.v1",
            "region_id": self.region_id,
            "polygon_xy_mm": [list(point) for point in self.polygon_xy_mm],
            "surface_z_mm": self.surface_z_mm,
            "minimum_contact_depth_mm": self.minimum_contact_depth_mm,
            "maximum_contact_depth_mm": self.maximum_contact_depth_mm,
            "required_contact_normal_board": list(
                self.required_contact_normal_board
            ),
            "maximum_normal_angle_deg": self.maximum_normal_angle_deg,
            "minimum_dwell_ticks": self.minimum_dwell_ticks,
            "maximum_dwell_ticks": self.maximum_dwell_ticks,
            "required_ui_state": self.required_ui_state,
        }


class ContactDisposition(str, Enum):
    """Closed vocabulary for deterministic contact truth outcomes."""

    ACCEPTED = "ACCEPTED"
    MISSED_CONTACT = "MISSED_CONTACT"
    OUTSIDE_REGION = "OUTSIDE_REGION"
    AMBIGUOUS_REGION = "AMBIGUOUS_REGION"
    DEPTH_OUT_OF_RANGE = "DEPTH_OUT_OF_RANGE"
    NORMAL_OUT_OF_RANGE = "NORMAL_OUT_OF_RANGE"
    DWELL_OUT_OF_RANGE = "DWELL_OUT_OF_RANGE"
    CONTACT_POLICY_REJECTED = "CONTACT_POLICY_REJECTED"
    DEVICE_NOT_FOCUSED = "DEVICE_NOT_FOCUSED"
    WRONG_UI_STATE = "WRONG_UI_STATE"


@dataclass(frozen=True, slots=True)
class ContactResult:
    """Immutable contact resolution with plaintext output kept in memory only."""

    action_index: int
    disposition: ContactDisposition
    activation_count: int
    model_definition_hash: str
    resolved_target_id: str | None = None
    contact_depth_mm: float | None = None
    normal_angle_deg: float | None = None
    resolved_output: str | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "action_index",
            _integer(self.action_index, "contact result action index", maximum=1_000_000_000),
        )
        if not isinstance(self.disposition, ContactDisposition):
            try:
                object.__setattr__(
                    self,
                    "disposition",
                    ContactDisposition(self.disposition),
                )
            except (TypeError, ValueError) as exc:
                raise VirtualValidationError("unsupported contact disposition") from exc
        object.__setattr__(
            self,
            "activation_count",
            _integer(
                self.activation_count,
                "contact result activation count",
                maximum=MAX_VIRTUAL_CONTACT_ACTIVATIONS,
            ),
        )
        object.__setattr__(
            self,
            "model_definition_hash",
            _digest(self.model_definition_hash, "contact model definition hash"),
        )
        if self.resolved_target_id is not None:
            object.__setattr__(
                self,
                "resolved_target_id",
                _name(self.resolved_target_id, "resolved target id"),
            )
        for field_name in ("contact_depth_mm", "normal_angle_deg"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, _finite(value, field_name))
        if self.resolved_output is not None:
            object.__setattr__(
                self,
                "resolved_output",
                _semantic_character(self.resolved_output),
            )
        if self.disposition is ContactDisposition.ACCEPTED:
            if (
                self.activation_count < 1
                or self.resolved_target_id is None
                or self.resolved_output is None
            ):
                raise VirtualValidationError(
                    "accepted contact result requires target, output, and activation"
                )
        elif self.activation_count != 0 or self.resolved_output is not None:
            raise VirtualValidationError(
                "rejected contact result cannot emit output activations"
            )

    @property
    def accepted(self) -> bool:
        return self.disposition is ContactDisposition.ACCEPTED

    @property
    def emitted_output(self) -> str:
        if self.resolved_output is None:
            return ""
        return self.resolved_output * self.activation_count

    @property
    def output_sha256(self) -> str:
        return hashlib.sha256(self.emitted_output.encode("utf-8")).hexdigest()

    @property
    def result_hash(self) -> str:
        return _stable_hash(self.to_dict())

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "rocell.contact_result.v1",
            "action_index": self.action_index,
            "disposition": self.disposition.value,
            "accepted": self.accepted,
            "activation_count": self.activation_count,
            "resolved_target_id": self.resolved_target_id,
            "contact_depth_mm": self.contact_depth_mm,
            "normal_angle_deg": self.normal_angle_deg,
            "output_sha256": self.output_sha256,
            "output_length": len(self.emitted_output),
            "raw_output_serialized": False,
            "model_definition_hash": self.model_definition_hash,
            "authority": _authority(),
        }


@dataclass(frozen=True, slots=True)
class _RegionEvaluation:
    region: ContactRegion
    depth_mm: float
    normal_angle_deg: float
    failures: tuple[ContactDisposition, ...]


class _VirtualTextDevice:
    """Shared geometry-driven truth model for virtual text devices."""

    _device_schema = "rocell.virtual_text_device.v2"

    def __init__(
        self,
        *,
        regions: Sequence[ContactRegion],
        output_map: Mapping[str, str],
        focused: bool,
        state_transition_map: Mapping[str, str] | None = None,
    ) -> None:
        if not isinstance(focused, bool):
            raise TypeError("focused must be bool")
        parsed_regions = tuple(regions)
        if not 1 <= len(parsed_regions) <= MAX_VIRTUAL_CONTACT_REGIONS:
            raise VirtualValidationError(
                "virtual contact model must contain between 1 and "
                f"{MAX_VIRTUAL_CONTACT_REGIONS} regions"
            )
        if any(not isinstance(region, ContactRegion) for region in parsed_regions):
            raise TypeError("regions must contain ContactRegion values")
        region_ids = tuple(region.region_id for region in parsed_regions)
        if len(set(region_ids)) != len(region_ids):
            raise VirtualValidationError("contact region ids must be unique")
        if not isinstance(output_map, Mapping):
            raise TypeError("output_map must be a mapping")
        if set(output_map) != set(region_ids):
            missing = sorted(set(region_ids) - set(output_map))
            extra = sorted(set(output_map) - set(region_ids))
            raise VirtualValidationError(
                f"output map must cover every region exactly; missing={missing}, extra={extra}"
            )
        outputs = {
            _name(region_id, "output region id"): _semantic_character(output)
            for region_id, output in output_map.items()
        }
        transitions: dict[str, str] = {}
        if state_transition_map is not None:
            if not isinstance(state_transition_map, Mapping):
                raise TypeError("state_transition_map must be a mapping")
            unknown = set(state_transition_map) - set(region_ids)
            if unknown:
                raise VirtualValidationError(
                    f"state transition map contains unknown regions {sorted(unknown)}"
                )
            transitions = {
                _name(region_id, "transition region id"): _name(
                    state,
                    "transition resulting UI state",
                )
                for region_id, state in state_transition_map.items()
            }
        self._regions = parsed_regions
        self._output_map = MappingProxyType(outputs)
        self._state_transition_map = MappingProxyType(transitions)
        self._focused = focused
        self._output = ""
        self._last_action_index: int | None = None
        self._accepted_contact_count = 0
        self._attempted_contact_count = 0
        self._last_contact_result_hash: str | None = None
        self._contact_result_hashes: list[str] = []
        self._region_definition_hash = _stable_hash(
            {
                "schema": "rocell.contact_region_map.v1",
                "regions": [region.to_dict() for region in parsed_regions],
                "authority": _authority(),
            }
        )
        self._output_map_hash = _stable_hash(
            {
                "schema": "rocell.contact_output_map.v1",
                "outputs": dict(sorted(outputs.items())),
                "authority": _authority(),
            }
        )
        self._state_transition_map_hash = _stable_hash(
            {
                "schema": "rocell.contact_state_transition_map.v1",
                "transitions": dict(sorted(transitions.items())),
                "authority": _authority(),
            }
        )
        self._model_definition_hash = _stable_hash(
            {
                "schema": self._device_schema,
                "region_definition_hash": self._region_definition_hash,
                "output_map_hash": self._output_map_hash,
                "state_transition_map_hash": self._state_transition_map_hash,
                "authority": _authority(),
            }
        )

    @property
    def focused(self) -> bool:
        return self._focused

    @property
    def output_length(self) -> int:
        return len(self._output)

    @property
    def output_sha256(self) -> str:
        return hashlib.sha256(self._output.encode("utf-8")).hexdigest()

    @property
    def accepted_contact_count(self) -> int:
        return self._accepted_contact_count

    @property
    def attempted_contact_count(self) -> int:
        return self._attempted_contact_count

    @property
    def last_action_index(self) -> int | None:
        return self._last_action_index

    @property
    def last_contact_result_hash(self) -> str | None:
        return self._last_contact_result_hash

    @property
    def contact_result_hashes(self) -> tuple[str, ...]:
        """Ordered exact-once contact results emitted by this device model."""

        return tuple(self._contact_result_hashes)

    @property
    def region_definition_hash(self) -> str:
        return self._region_definition_hash

    @property
    def output_map_hash(self) -> str:
        return self._output_map_hash

    @property
    def state_transition_map_hash(self) -> str:
        return self._state_transition_map_hash

    @property
    def model_definition_hash(self) -> str:
        return self._model_definition_hash

    @property
    def regions(self) -> tuple[ContactRegion, ...]:
        return self._regions

    def set_focus(self, focused: bool) -> None:
        if not isinstance(focused, bool):
            raise TypeError("focused must be bool")
        self._focused = focused

    def output_matches(self, expected_sha256: str, expected_length: int) -> bool:
        return (
            self.output_sha256 == _digest(expected_sha256, "expected output hash")
            and self.output_length
            == _integer(expected_length, "expected output length", maximum=1_000_000)
        )

    def _active_ui_state(self) -> str | None:
        return None

    @staticmethod
    def _evaluate_region(
        event: ContactEvent,
        region: ContactRegion,
    ) -> _RegionEvaluation:
        depth = region.surface_z_mm - event.achieved_board_xyz_mm[2]
        dot = sum(
            achieved * required
            for achieved, required in zip(
                event.achieved_contact_normal_board,
                region.required_contact_normal_board,
            )
        )
        normal_angle = math.degrees(math.acos(max(-1.0, min(1.0, dot))))
        failures: list[ContactDisposition] = []
        if not region.minimum_contact_depth_mm <= depth <= region.maximum_contact_depth_mm:
            failures.append(ContactDisposition.DEPTH_OUT_OF_RANGE)
        if normal_angle > region.maximum_normal_angle_deg + 1e-12:
            failures.append(ContactDisposition.NORMAL_OUT_OF_RANGE)
        if not region.minimum_dwell_ticks <= event.dwell_ticks <= region.maximum_dwell_ticks:
            failures.append(ContactDisposition.DWELL_OUT_OF_RANGE)
        return _RegionEvaluation(region, depth, normal_angle, tuple(failures))

    def _result(
        self,
        event: ContactEvent,
        disposition: ContactDisposition,
        *,
        evaluation: _RegionEvaluation | None = None,
        activation_count: int = 0,
        resolved_output: str | None = None,
    ) -> ContactResult:
        return ContactResult(
            action_index=event.action_index,
            disposition=disposition,
            activation_count=activation_count,
            model_definition_hash=self.model_definition_hash,
            resolved_target_id=(
                evaluation.region.region_id if evaluation is not None else None
            ),
            contact_depth_mm=(evaluation.depth_mm if evaluation is not None else None),
            normal_angle_deg=(
                evaluation.normal_angle_deg if evaluation is not None else None
            ),
            resolved_output=resolved_output,
        )

    def _resolve(self, event: ContactEvent) -> ContactResult:
        xy = event.achieved_board_xyz_mm[:2]
        current_state = self._active_ui_state()
        xy_regions = tuple(region for region in self.regions if region.contains_xy(xy))
        active_regions = tuple(
            region
            for region in xy_regions
            if region.required_ui_state is None
            or region.required_ui_state == current_state
        )
        if not active_regions:
            if xy_regions and current_state is not None:
                return self._result(event, ContactDisposition.WRONG_UI_STATE)
            return self._result(event, ContactDisposition.OUTSIDE_REGION)
        evaluations = tuple(
            self._evaluate_region(event, region) for region in active_regions
        )
        accepted = tuple(evaluation for evaluation in evaluations if not evaluation.failures)
        if len(accepted) > 1:
            return self._result(event, ContactDisposition.AMBIGUOUS_REGION)
        if len(accepted) == 0:
            distinct_failures = {
                failure for evaluation in evaluations for failure in evaluation.failures
            }
            if len(evaluations) == 1 and len(distinct_failures) == 1:
                disposition = next(iter(distinct_failures))
            else:
                disposition = ContactDisposition.CONTACT_POLICY_REJECTED
            return self._result(
                event,
                disposition,
                evaluation=evaluations[0] if len(evaluations) == 1 else None,
            )
        evaluation = accepted[0]
        if not self.focused:
            return self._result(
                event,
                ContactDisposition.DEVICE_NOT_FOCUSED,
                evaluation=evaluation,
            )
        if event.activation_count == 0:
            return self._result(
                event,
                ContactDisposition.MISSED_CONTACT,
                evaluation=evaluation,
            )
        output = self._output_map[evaluation.region.region_id]
        return self._result(
            event,
            ContactDisposition.ACCEPTED,
            evaluation=evaluation,
            activation_count=event.activation_count,
            resolved_output=output,
        )

    def apply_contact(self, event: ContactEvent) -> ContactResult:
        """Resolve one achieved contact without consulting the motion plan."""

        if not isinstance(event, ContactEvent):
            raise TypeError("event must be a ContactEvent")
        if self.last_action_index is not None and event.action_index <= self.last_action_index:
            raise VirtualValidationError(
                "virtual device action indices must increase strictly"
            )
        result = self._resolve(event)
        # Every well-formed attempt is consumed, including a miss or rejection.
        # This enforces the no-automatic-retry behavior expected by the session.
        self._last_action_index = event.action_index
        self._attempted_contact_count += 1
        if result.accepted:
            self._output += result.emitted_output
            self._accepted_contact_count += result.activation_count
            resulting_state = self._state_transition_map.get(
                result.resolved_target_id or ""
            )
            if resulting_state is not None:
                self._apply_resulting_ui_state(resulting_state)
        self._last_contact_result_hash = result.result_hash
        self._contact_result_hashes.append(result.result_hash)
        return result

    def _apply_resulting_ui_state(self, resulting_state: str) -> None:
        if resulting_state:
            raise VirtualValidationError(
                "this virtual device does not support UI state transitions"
            )

    def _base_state(self) -> dict[str, object]:
        return {
            "focused": self.focused,
            "output_sha256": self.output_sha256,
            "output_length": self.output_length,
            "accepted_contact_count": self.accepted_contact_count,
            "attempted_contact_count": self.attempted_contact_count,
            "last_action_index": self.last_action_index,
            "last_contact_result_hash": self.last_contact_result_hash,
            "contact_result_hashes": list(self.contact_result_hashes),
            "region_count": len(self.regions),
            "region_definition_hash": self.region_definition_hash,
            "output_map_hash": self.output_map_hash,
            "state_transition_map_hash": self.state_transition_map_hash,
            "model_definition_hash": self.model_definition_hash,
            "contact_input_contract": "ACHIEVED_BOARD_XYZ_NORMAL_DWELL_ONLY",
            "raw_output_serialized": False,
        }


class VirtualKeyboard(_VirtualTextDevice):
    """Keyboard truth model whose output comes only from region hit testing."""

    _device_schema = "rocell.virtual_keyboard_definition.v2"

    def __init__(
        self,
        *,
        regions: Sequence[ContactRegion],
        output_map: Mapping[str, str],
        focused: bool = True,
    ) -> None:
        if any(region.required_ui_state is not None for region in regions):
            raise VirtualValidationError(
                "keyboard contact regions cannot require an Android UI state"
            )
        super().__init__(
            regions=regions,
            output_map=output_map,
            focused=focused,
        )

    @property
    def state_hash(self) -> str:
        return _stable_hash(self.to_dict())

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "rocell.virtual_keyboard.v2",
            **self._base_state(),
            "hardware_events_generated": 0,
            "authority": _authority(),
        }


class VirtualAndroid(_VirtualTextDevice):
    """UI-state-scoped Android truth model driven only by achieved taps."""

    _device_schema = "rocell.virtual_android_definition.v2"

    def __init__(
        self,
        *,
        initial_ui_state: str,
        regions: Sequence[ContactRegion],
        output_map: Mapping[str, str],
        state_transition_map: Mapping[str, str] | None = None,
        focused: bool = True,
    ) -> None:
        self._ui_state = _name(initial_ui_state, "initial Android UI state")
        if any(region.required_ui_state is None for region in regions):
            raise VirtualValidationError(
                "every Android contact region must declare a required UI state"
            )
        super().__init__(
            regions=regions,
            output_map=output_map,
            focused=focused,
            state_transition_map=state_transition_map,
        )

    @property
    def ui_state(self) -> str:
        return self._ui_state

    def _active_ui_state(self) -> str | None:
        return self.ui_state

    def _apply_resulting_ui_state(self, resulting_state: str) -> None:
        self._ui_state = resulting_state

    def set_ui_state_for_simulation(self, ui_state: str) -> None:
        """Apply an explicit scenario/fault state; never observation evidence."""

        self._ui_state = _name(ui_state, "Android UI state")

    def verify_ui_state(self, required_state: str) -> bool:
        return self.ui_state == _name(required_state, "required Android UI state")

    @property
    def state_hash(self) -> str:
        return _stable_hash(self.to_dict())

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "rocell.virtual_android.v2",
            "ui_state": self.ui_state,
            **self._base_state(),
            "hardware_events_generated": 0,
            "authority": _authority(),
        }


@dataclass(frozen=True, slots=True)
class VirtualExecutionEvent:
    """One immutable, content-addressed virtual runtime event."""

    sequence: int
    tick: int
    component: str
    operation: str
    status: str
    detail_code: str
    before_state_hash: str | None = None
    after_state_hash: str | None = None
    action_index: int | None = None
    target_id: str | None = None
    waypoint_sequence: int | None = None
    fault_trigger_id: str | None = None
    virtual_command_executed: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "sequence",
            _integer(self.sequence, "event sequence", maximum=MAX_VIRTUAL_LEDGER_EVENTS),
        )
        object.__setattr__(self, "tick", _integer(self.tick, "event tick"))
        for field_name in ("component", "operation", "detail_code"):
            object.__setattr__(
                self,
                field_name,
                _name(getattr(self, field_name), field_name, maximum=512),
            )
        if self.status not in {"PASS", "REJECTED", "FAULT", "INFO"}:
            raise VirtualValidationError(
                "event status must be PASS, REJECTED, FAULT, or INFO"
            )
        for field_name in ("before_state_hash", "after_state_hash"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, _digest(value, field_name))
        for field_name in ("action_index", "waypoint_sequence"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(
                    self,
                    field_name,
                    _integer(value, field_name, maximum=1_000_000_000),
                )
        for field_name in ("target_id", "fault_trigger_id"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, _name(value, field_name))
        if not isinstance(self.virtual_command_executed, bool):
            raise TypeError("virtual_command_executed must be bool")

    @property
    def event_hash(self) -> str:
        return _stable_hash(self.to_dict())

    def to_dict(self) -> dict[str, object]:
        return {
            "sequence": self.sequence,
            "tick": self.tick,
            "component": self.component,
            "operation": self.operation,
            "status": self.status,
            "detail_code": self.detail_code,
            "before_state_hash": self.before_state_hash,
            "after_state_hash": self.after_state_hash,
            "action_index": self.action_index,
            "target_id": self.target_id,
            "waypoint_sequence": self.waypoint_sequence,
            "fault_trigger_id": self.fault_trigger_id,
            "virtual_command_executed": self.virtual_command_executed,
            "hardware_commands_generated": 0,
        }


class VirtualEventLedger:
    """Append-only bounded ledger of immutable virtual execution events."""

    __slots__ = ("_token_hash", "_maximum_events", "_events", "_sealed")

    def __init__(
        self,
        *,
        token: VirtualExecutionToken,
        maximum_events: int = 10_000,
    ) -> None:
        if not isinstance(token, VirtualExecutionToken):
            raise TypeError("token must be a VirtualExecutionToken")
        self._token_hash = token.token_hash
        self._maximum_events = _integer(
            maximum_events,
            "maximum ledger events",
            minimum=1,
            maximum=MAX_VIRTUAL_LEDGER_EVENTS,
        )
        self._events: list[VirtualExecutionEvent] = []
        self._sealed = False

    @property
    def events(self) -> tuple[VirtualExecutionEvent, ...]:
        return tuple(self._events)

    @property
    def next_sequence(self) -> int:
        return len(self._events)

    @property
    def sealed(self) -> bool:
        return self._sealed

    @property
    def virtual_commands_executed(self) -> int:
        return sum(event.virtual_command_executed for event in self._events)

    def append(self, event: VirtualExecutionEvent) -> None:
        if not isinstance(event, VirtualExecutionEvent):
            raise TypeError("ledger events must be VirtualExecutionEvent values")
        if self.sealed:
            raise VirtualLifecycleError("virtual event ledger is sealed")
        if len(self._events) >= self._maximum_events:
            raise VirtualResourceLimitError(
                f"virtual event ledger reached {self._maximum_events} events"
            )
        if event.sequence != self.next_sequence:
            raise VirtualValidationError(
                f"event sequence {event.sequence} must equal {self.next_sequence}"
            )
        if self._events and event.tick < self._events[-1].tick:
            raise VirtualValidationError("event ticks must be monotonic")
        self._events.append(event)

    def seal(self) -> None:
        if self.sealed:
            raise VirtualLifecycleError("virtual event ledger is already sealed")
        self._sealed = True

    @property
    def ledger_hash(self) -> str:
        return _stable_hash(self.to_dict())

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "rocell.virtual_event_ledger.v1",
            "token_hash": self._token_hash,
            "sealed": self.sealed,
            "maximum_events": self._maximum_events,
            "event_count": len(self._events),
            "virtual_commands_executed": self.virtual_commands_executed,
            "hardware_commands_generated": 0,
            "events": [
                {**event.to_dict(), "event_hash": event.event_hash}
                for event in self._events
            ],
            "authority": _authority(),
        }


__all__ = [
    "ContactDisposition",
    "ContactEvent",
    "ContactRegion",
    "ContactResult",
    "MAX_VIRTUAL_CONTACT_POLYGON_VERTICES",
    "MAX_VIRTUAL_CONTACT_REGIONS",
    "MAX_VIRTUAL_FAULT_TRIGGERS",
    "MAX_VIRTUAL_LEDGER_EVENTS",
    "VIRTUAL_ARM_JOINT_NAMES",
    "VirtualAndroid",
    "VirtualArmFeedback",
    "VirtualArmLifecycle",
    "VirtualArmPlant",
    "VirtualClock",
    "VirtualEventLedger",
    "VirtualExecutionEvent",
    "VirtualExecutionToken",
    "VirtualFaultKind",
    "VirtualFaultScript",
    "VirtualFaultTrigger",
    "VirtualJointWaypoint",
    "VirtualKeyboard",
    "VirtualLifecycleError",
    "VirtualResourceLimitError",
    "VirtualValidationError",
    "VirtualWorkcellError",
    "issue_virtual_execution_token",
]

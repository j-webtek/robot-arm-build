"""Strictly ordered, zero-authority replay of B0477 mission observations.

This is an in-memory test double for the future static overhead camera port.  It
does not open a camera, file, socket, or hardware transport.  A caller can only
receive the next precomputed observation after presenting every identity bound
to that contact and the hash of the controller pose that has just settled.

The port is deliberately single-use and non-copyable.  Any configured camera
fault latches the port closed before an observation can be returned.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
import re
import threading
from typing import NoReturn

from rocell.application.b0477_mission_observations import (
    B0477MissionObservation,
    B0477MissionObservationSet,
)


MAX_REPLAY_CONTACTS = 512
B0477_REPLAY_FAULT_INJECTION_SCHEMA = "rocell.b0477_replay_fault_injection.v1"
B0477_REPLAY_FAULT_RECEIPT_SCHEMA = "rocell.b0477_replay_fault_receipt.v1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


class B0477ReplayCameraError(RuntimeError):
    """A replay request or port state failed closed."""


class B0477ReplayFaultKind(str, Enum):
    """Deterministic synthetic camera failures supported by the replay port."""

    CAPTURE_FAILURE = "CAPTURE_FAILURE"
    TIMEOUT = "TIMEOUT"
    STALE_FRAME = "STALE_FRAME"


def _canonical_sha256(value: object) -> str:
    """Hash the bounded canonical JSON used by the replay evidence types."""

    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise B0477ReplayCameraError(
            "B0477 replay evidence is not canonical JSON"
        ) from exc
    if len(encoded) > 64 * 1024:
        raise B0477ReplayCameraError("B0477 replay evidence exceeds its byte limit")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class B0477ReplayFaultInjection:
    """One camera fault to latch at an exact contact occurrence."""

    contact_occurrence_ordinal: int
    fault_kind: B0477ReplayFaultKind
    schema: str = B0477_REPLAY_FAULT_INJECTION_SCHEMA
    _sealed_sha256: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        self._validate_unsealed()
        object.__setattr__(self, "_sealed_sha256", _canonical_sha256(self._document()))

    def _validate_unsealed(self) -> None:
        if self.schema != B0477_REPLAY_FAULT_INJECTION_SCHEMA:
            raise B0477ReplayCameraError(
                "unsupported B0477 replay fault-injection schema"
            )
        _ordinal(
            self.contact_occurrence_ordinal,
            "contact_occurrence_ordinal",
            maximum=MAX_REPLAY_CONTACTS - 1,
        )
        if type(self.fault_kind) is not B0477ReplayFaultKind:
            raise TypeError("fault_kind must be exactly B0477ReplayFaultKind")

    def _document(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "contact_occurrence_ordinal": self.contact_occurrence_ordinal,
            "fault_kind": self.fault_kind.value,
            "simulation_only": True,
            "physical_authority": "ZERO",
            "hardware_accessed": False,
            "hardware_commands_generated": 0,
            "wire_messages_generated": 0,
            "physical_release_effect": "NONE",
        }

    @property
    def canonical_sha256(self) -> str:
        self.validate()
        return self._sealed_sha256

    def validate(self) -> None:
        self._validate_unsealed()
        if _canonical_sha256(self._document()) != self._sealed_sha256:
            raise B0477ReplayCameraError(
                "B0477 replay fault injection changed after construction"
            )

    def to_dict(self) -> dict[str, object]:
        self.validate()
        return {**self._document(), "injection_sha256": self._sealed_sha256}


@dataclass(frozen=True, slots=True)
class B0477ReplayFaultReceipt:
    """Sealed proof that the replay camera faulted at one exact capture request.

    The receipt retains the full settled-hover and expected-observation binding.
    It is deliberately distinct from a human-readable exception string so a
    report cannot reattribute a camera failure by merely rewriting that string.
    """

    fault_kind: B0477ReplayFaultKind
    semantic_step_ordinal: int
    contact_occurrence_ordinal: int
    target_id: str
    route_waypoint_ordinal: int
    authorization_command_ordinal: int
    settled_controller_pose_sha256: str
    expected_observation_sha256: str
    observation_set_sha256: str
    fault_injection_sha256: str
    schema: str = B0477_REPLAY_FAULT_RECEIPT_SCHEMA
    _sealed_sha256: str = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        self._validate_unsealed()
        object.__setattr__(self, "_sealed_sha256", _canonical_sha256(self._document()))

    def _validate_unsealed(self) -> None:
        if self.schema != B0477_REPLAY_FAULT_RECEIPT_SCHEMA:
            raise B0477ReplayCameraError("unsupported B0477 replay fault schema")
        if type(self.fault_kind) is not B0477ReplayFaultKind:
            raise TypeError("fault_kind must be exactly B0477ReplayFaultKind")
        _ordinal(self.semantic_step_ordinal, "semantic_step_ordinal", maximum=511)
        _ordinal(
            self.contact_occurrence_ordinal,
            "contact_occurrence_ordinal",
            maximum=MAX_REPLAY_CONTACTS - 1,
        )
        _identifier(self.target_id, "target_id")
        route = _ordinal(self.route_waypoint_ordinal, "route_waypoint_ordinal")
        authorization = _ordinal(
            self.authorization_command_ordinal,
            "authorization_command_ordinal",
        )
        if route == 0 or authorization != route - 1:
            raise B0477ReplayCameraError(
                "B0477 fault route/authorization ordinals differ"
            )
        for name in (
            "settled_controller_pose_sha256",
            "expected_observation_sha256",
            "observation_set_sha256",
            "fault_injection_sha256",
        ):
            _digest(getattr(self, name), name)

    def _document(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "source_class": "B0477ReplayCameraPort",
            "stage": "CAPTURE_AFTER_SETTLE",
            "fault_kind": self.fault_kind.value,
            "semantic_step_ordinal": self.semantic_step_ordinal,
            "contact_occurrence_ordinal": self.contact_occurrence_ordinal,
            "target_id": self.target_id,
            "route_waypoint_ordinal": self.route_waypoint_ordinal,
            "authorization_command_ordinal": self.authorization_command_ordinal,
            "settled_controller_pose_sha256": self.settled_controller_pose_sha256,
            "expected_observation_sha256": self.expected_observation_sha256,
            "observation_set_sha256": self.observation_set_sha256,
            "fault_injection_sha256": self.fault_injection_sha256,
            "observation_yielded": False,
            "simulation_only": True,
            "physical_authority": "ZERO",
            "hardware_accessed": False,
            "hardware_commands_generated": 0,
            "wire_messages_generated": 0,
            "physical_release_effect": "NONE",
        }

    @property
    def canonical_sha256(self) -> str:
        self.validate()
        return self._sealed_sha256

    def validate(self) -> None:
        self._validate_unsealed()
        if _canonical_sha256(self._document()) != self._sealed_sha256:
            raise B0477ReplayCameraError(
                "B0477 replay fault receipt changed after construction"
            )

    def to_dict(self) -> dict[str, object]:
        self.validate()
        return {**self._document(), "receipt_sha256": self._sealed_sha256}


class B0477ReplayCaptureError(B0477ReplayCameraError):
    """A deterministic camera fault occurred without yielding an observation."""

    def __init__(
        self,
        *,
        receipt: B0477ReplayFaultReceipt,
    ) -> None:
        if type(receipt) is not B0477ReplayFaultReceipt:
            raise TypeError("receipt must be exactly B0477ReplayFaultReceipt")
        receipt.validate()
        self.receipt = receipt
        self.contact_occurrence_ordinal = receipt.contact_occurrence_ordinal
        self.fault_kind = receipt.fault_kind
        super().__init__(
            f"B0477 replay fault {receipt.fault_kind.value} at contact "
            f"{receipt.contact_occurrence_ordinal}; no observation was yielded"
        )


def _ordinal(value: object, label: str, *, maximum: int = 65_535) -> int:
    if type(value) is not int or not 0 <= value <= maximum:
        raise B0477ReplayCameraError(
            f"{label} must be a bounded nonnegative integer"
        )
    return value


def _identifier(value: object, label: str) -> str:
    if type(value) is not str or _IDENTIFIER.fullmatch(value) is None:
        raise B0477ReplayCameraError(f"{label} must be a bounded identifier")
    return value


def _digest(value: object, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise B0477ReplayCameraError(
            f"{label} must be an exact lowercase SHA-256 digest"
        )
    return value


class B0477ReplayCameraPort:
    """Consume one immutable B0477 observation set in exact contact order.

    The instance snapshots the set's canonical digest and rejects copying or
    serialization so its cursor cannot be duplicated accidentally.  The
    exactly-once guarantee is per port instance; constructing another port is
    an explicit new replay session.
    """

    __slots__ = (
        "_complete",
        "_consumed",
        "_cursor",
        "_fault_injection",
        "_fault_injection_sha256",
        "_fault_latched",
        "_fault_receipt",
        "_lock",
        "_observation_set",
        "_observation_set_sha256",
    )

    def __init__(
        self,
        observation_set: B0477MissionObservationSet,
        *,
        fault_injection: B0477ReplayFaultInjection | None = None,
    ) -> None:
        if type(observation_set) is not B0477MissionObservationSet:
            raise TypeError(
                "observation_set must be exactly B0477MissionObservationSet"
            )
        observation_set.validate()
        if fault_injection is not None:
            if type(fault_injection) is not B0477ReplayFaultInjection:
                raise TypeError(
                    "fault_injection must be exactly B0477ReplayFaultInjection or None"
                )
            fault_injection.validate()
            if fault_injection.contact_occurrence_ordinal >= (
                observation_set.observation_count
            ):
                raise B0477ReplayCameraError(
                    "fault contact ordinal is outside the observation set"
                )
            # Snapshot primitive fields so later mutation of the caller-owned
            # object cannot move or relabel the port's scheduled failure.
            fault_injection = B0477ReplayFaultInjection(
                contact_occurrence_ordinal=(
                    fault_injection.contact_occurrence_ordinal
                ),
                fault_kind=fault_injection.fault_kind,
            )
        self._observation_set = observation_set
        self._observation_set_sha256 = observation_set.canonical_sha256
        self._fault_injection = fault_injection
        self._fault_injection_sha256 = (
            None
            if fault_injection is None
            else fault_injection.canonical_sha256
        )
        self._cursor = 0
        self._consumed = 0
        self._complete = False
        self._fault_latched: B0477ReplayFaultKind | None = None
        self._fault_receipt: B0477ReplayFaultReceipt | None = None
        self._lock = threading.Lock()

    def __copy__(self) -> NoReturn:
        raise B0477ReplayCameraError("B0477 replay camera ports cannot be copied")

    def __deepcopy__(self, memo: object) -> NoReturn:
        del memo
        raise B0477ReplayCameraError("B0477 replay camera ports cannot be copied")

    def __reduce_ex__(self, protocol: object) -> NoReturn:
        del protocol
        raise B0477ReplayCameraError(
            "B0477 replay camera ports cannot be serialized"
        )

    @property
    def authority(self) -> str:
        return "ZERO"

    @property
    def hardware_accessed(self) -> bool:
        return False

    @property
    def consumed(self) -> int:
        with self._lock:
            return self._consumed

    @property
    def remaining(self) -> int:
        with self._lock:
            return self._observation_set.observation_count - self._consumed

    @property
    def complete(self) -> bool:
        with self._lock:
            return self._complete

    @property
    def fault_latched(self) -> B0477ReplayFaultKind | None:
        with self._lock:
            return self._fault_latched

    @property
    def fault_receipt(self) -> B0477ReplayFaultReceipt | None:
        with self._lock:
            if self._fault_receipt is not None:
                self._fault_receipt.validate()
            return self._fault_receipt

    def capture_after_settle(
        self,
        *,
        semantic_step_ordinal: int,
        contact_occurrence_ordinal: int,
        target_id: str,
        final_hover_route_waypoint_ordinal: int,
        authorization_command_ordinal: int,
        just_settled_controller_pose_sha256: str,
    ) -> B0477MissionObservation:
        """Return only the exact next observation after an exact settled hover.

        Inputs are checked before fault injection.  Therefore an invalid caller
        cannot consume a row or trigger/skip a scheduled camera fault.
        """

        semantic = _ordinal(
            semantic_step_ordinal, "semantic_step_ordinal", maximum=511
        )
        contact = _ordinal(
            contact_occurrence_ordinal,
            "contact_occurrence_ordinal",
            maximum=MAX_REPLAY_CONTACTS - 1,
        )
        target = _identifier(target_id, "target_id")
        route = _ordinal(
            final_hover_route_waypoint_ordinal,
            "final_hover_route_waypoint_ordinal",
        )
        authorization = _ordinal(
            authorization_command_ordinal, "authorization_command_ordinal"
        )
        pose_sha256 = _digest(
            just_settled_controller_pose_sha256,
            "just_settled_controller_pose_sha256",
        )

        with self._lock:
            if self._fault_latched is not None:
                raise B0477ReplayCameraError(
                    "B0477 replay camera is fault-latched and cannot capture"
                )
            if self._complete:
                raise B0477ReplayCameraError(
                    "B0477 observation set is already completely consumed"
                )
            # Revalidate both the source object and its construction-time hash
            # at every authority boundary.  Mutation by low-level bypasses is
            # rejected before the cursor or fault state can change.
            self._observation_set.validate()
            if (
                self._observation_set.canonical_sha256
                != self._observation_set_sha256
            ):
                raise B0477ReplayCameraError(
                    "B0477 observation set identity changed after port creation"
                )
            expected = self._observation_set.observations[self._cursor]
            expected.validate()
            if contact != self._cursor:
                raise B0477ReplayCameraError(
                    "contact was skipped, duplicated, reused, or reordered"
                )
            if (
                semantic != expected.semantic_step_ordinal
                or contact != expected.contact_occurrence_ordinal
                or target != expected.target_id
                or route != expected.route_waypoint_ordinal
                or authorization != expected.authorization_command_ordinal
            ):
                raise B0477ReplayCameraError(
                    "capture request differs from the exact next observation binding"
                )
            if pose_sha256 != expected.expected_settled_controller_pose_sha256:
                raise B0477ReplayCameraError(
                    "controller pose is not the exact settled final-hover pose"
                )

            fault = self._fault_injection
            if fault is not None:
                fault.validate()
                if fault.canonical_sha256 != self._fault_injection_sha256:
                    raise B0477ReplayCameraError(
                        "B0477 replay fault schedule changed after port creation"
                    )
            if fault is not None and fault.contact_occurrence_ordinal == contact:
                fault_receipt = B0477ReplayFaultReceipt(
                    fault_kind=fault.fault_kind,
                    semantic_step_ordinal=semantic,
                    contact_occurrence_ordinal=contact,
                    target_id=target,
                    route_waypoint_ordinal=route,
                    authorization_command_ordinal=authorization,
                    settled_controller_pose_sha256=pose_sha256,
                    expected_observation_sha256=expected.observation_sha256,
                    observation_set_sha256=self._observation_set_sha256,
                    fault_injection_sha256=fault.canonical_sha256,
                )
                self._fault_receipt = fault_receipt
                self._fault_latched = fault.fault_kind
                raise B0477ReplayCaptureError(
                    receipt=fault_receipt,
                )

            self._cursor += 1
            self._consumed += 1
            if self._cursor == self._observation_set.observation_count:
                self._complete = True
            return expected


__all__ = [
    "MAX_REPLAY_CONTACTS",
    "B0477_REPLAY_FAULT_INJECTION_SCHEMA",
    "B0477_REPLAY_FAULT_RECEIPT_SCHEMA",
    "B0477ReplayCameraError",
    "B0477ReplayCameraPort",
    "B0477ReplayCaptureError",
    "B0477ReplayFaultInjection",
    "B0477ReplayFaultKind",
    "B0477ReplayFaultReceipt",
]

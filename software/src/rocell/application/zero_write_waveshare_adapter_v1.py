"""Side-effect-free T=102 preview for sealed v2 trajectory envelopes.

The adapter intentionally owns no transport.  It converts each commanded
waypoint after the observed starting sample into reviewable Waveshare JSON bytes
and records the host-side dispatch schedule that a future sole writer would
need to honor.  Firmware ``spd`` and ``acc`` remain opaque configured integers;
they are not treated as physical velocity or acceleration units.

Protocol source pinned by the existing arm boundary:
``RoArm-M3_example_20260701.zip``, ``uart_ctrl.h:23-33`` and
``RoArm-M3_module.h:825-840``.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import re
import threading
from typing import Any

from rocell.arm.all_joint_command import all_joint_command
from rocell.arm.protocol import encode_line
from rocell.kinematics import ARM_JOINT_NAMES

from .trajectory_execution_envelope_v2 import TrajectoryExecutionEnvelopeV2


PROFILE_SCHEMA = "rocell.zero_write_waveshare_t102_profile.v1"
PERMIT_SCHEMA = "rocell.zero_write_waveshare_preview_permit.v1"
RECEIPT_SCHEMA = "rocell.zero_write_waveshare_preview_receipt.v1"
INTERPOLATION_MODE = "HOST_SCHEDULED_T102_WAYPOINTS_V1"
GRIPPER_BEHAVIOR = "FIXED_ABSOLUTE_RAD"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_PERMIT_ISSUER = object()


class ZeroWriteWaveshareAdapterError(ValueError):
    """A preview is unbound, stale, duplicated, or otherwise unsupported."""


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ZeroWriteWaveshareAdapterError("value is not canonical JSON") from exc


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ZeroWriteWaveshareAdapterError(f"{label} must be a SHA-256 digest")
    return value


def _identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise ZeroWriteWaveshareAdapterError(f"{label} must be a bounded identifier")
    return value


def _positive_ns(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ZeroWriteWaveshareAdapterError(f"{label} must be positive nanoseconds")
    return value


def _finite(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ZeroWriteWaveshareAdapterError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ZeroWriteWaveshareAdapterError(f"{label} must be finite")
    return result


def trajectory_limits_sha256(envelope: TrajectoryExecutionEnvelopeV2) -> str:
    if not isinstance(envelope, TrajectoryExecutionEnvelopeV2):
        raise TypeError("envelope must be a TrajectoryExecutionEnvelopeV2")
    return hashlib.sha256(
        _canonical(envelope.measured_envelope.limits.to_dict())).hexdigest()


@dataclass(frozen=True, slots=True)
class WaveshareT102EncodingProfileV1:
    profile_id: str
    vendor_source_sha256: str
    controller_joint_mapping_sha256: str
    expected_trajectory_limits_sha256: str
    controller_session_id: str
    configuration_epoch_sha256: str
    fixed_gripper_rad: float
    speed: int
    acceleration: int
    interpolation_mode: str = INTERPOLATION_MODE
    gripper_behavior: str = GRIPPER_BEHAVIOR
    schema: str = PROFILE_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != PROFILE_SCHEMA:
            raise ZeroWriteWaveshareAdapterError("unsupported encoding profile schema")
        _identifier(self.profile_id, "profile_id")
        _identifier(self.controller_session_id, "controller_session_id")
        for field in (
            "vendor_source_sha256", "controller_joint_mapping_sha256",
            "expected_trajectory_limits_sha256", "configuration_epoch_sha256",
        ):
            _digest(getattr(self, field), field)
        if self.interpolation_mode != INTERPOLATION_MODE:
            raise ZeroWriteWaveshareAdapterError("unsupported interpolation mode")
        if self.gripper_behavior != GRIPPER_BEHAVIOR:
            raise ZeroWriteWaveshareAdapterError("gripper behavior must be fixed")
        object.__setattr__(
            self, "fixed_gripper_rad", _finite(self.fixed_gripper_rad,
                                                "fixed_gripper_rad"))
        # Reuse the protocol boundary's exact firmware-setting validation.
        all_joint_command(
            [0.0] * 5 + [self.fixed_gripper_rad], speed=self.speed,
            acceleration=self.acceleration)

    def unsigned_dict(self) -> dict[str, Any]:
        return {
            field: getattr(self, field)
            for field in self.__dataclass_fields__
        }

    @property
    def profile_sha256(self) -> str:
        return hashlib.sha256(_canonical(self.unsigned_dict())).hexdigest()


class ZeroWriteEncodingPermitV1:
    """Single-use preview token; it carries no permission to access hardware."""

    def __init__(
        self, *, _issuer: object, envelope_v2_sha256: str,
        encoding_profile_sha256: str, correlation_id: str,
        controller_session_id: str, issued_monotonic_ns: int,
        expires_monotonic_ns: int,
    ) -> None:
        if _issuer is not _PERMIT_ISSUER:
            raise ZeroWriteWaveshareAdapterError(
                "preview permits must be issued by the zero-write factory")
        self.envelope_v2_sha256 = _digest(
            envelope_v2_sha256, "envelope_v2_sha256")
        self.encoding_profile_sha256 = _digest(
            encoding_profile_sha256, "encoding_profile_sha256")
        self.correlation_id = _identifier(correlation_id, "correlation_id")
        self.controller_session_id = _identifier(
            controller_session_id, "controller_session_id")
        self.issued_monotonic_ns = _positive_ns(
            issued_monotonic_ns, "issued_monotonic_ns")
        self.expires_monotonic_ns = _positive_ns(
            expires_monotonic_ns, "expires_monotonic_ns")
        if self.expires_monotonic_ns <= self.issued_monotonic_ns:
            raise ZeroWriteWaveshareAdapterError("permit expiry must follow issuance")
        self._consumed = False
        self._lock = threading.Lock()

    def unsigned_dict(self) -> dict[str, Any]:
        return {
            "schema": PERMIT_SCHEMA,
            "envelope_v2_sha256": self.envelope_v2_sha256,
            "encoding_profile_sha256": self.encoding_profile_sha256,
            "correlation_id": self.correlation_id,
            "controller_session_id": self.controller_session_id,
            "issued_monotonic_ns": self.issued_monotonic_ns,
            "expires_monotonic_ns": self.expires_monotonic_ns,
            "hardware_access": False,
            "physical_authority": False,
        }

    @property
    def permit_id(self) -> str:
        return hashlib.sha256(_canonical(self.unsigned_dict())).hexdigest()

    @property
    def consumed(self) -> bool:
        with self._lock:
            return self._consumed

    def _consume(
        self, envelope: TrajectoryExecutionEnvelopeV2,
        profile: WaveshareT102EncodingProfileV1, now_monotonic_ns: int,
    ) -> None:
        with self._lock:
            if self._consumed:
                raise ZeroWriteWaveshareAdapterError("preview permit was already consumed")
            # Any attempt consumes the token, including a mismatch or stale call.
            self._consumed = True
            if (
                now_monotonic_ns < self.issued_monotonic_ns
                or now_monotonic_ns >= self.expires_monotonic_ns
            ):
                raise ZeroWriteWaveshareAdapterError("preview permit is not current")
            if (
                self.envelope_v2_sha256 != envelope.envelope_v2_sha256
                or self.encoding_profile_sha256 != profile.profile_sha256
                or self.correlation_id
                != envelope.measured_envelope.correlation_id
                or self.controller_session_id
                != envelope.measured_envelope.controller_session_id
            ):
                raise ZeroWriteWaveshareAdapterError(
                    "preview permit binding differs from envelope or profile")


def issue_zero_write_encoding_permit_v1(
    envelope: TrajectoryExecutionEnvelopeV2,
    profile: WaveshareT102EncodingProfileV1, *, issued_monotonic_ns: int,
    expires_monotonic_ns: int,
) -> ZeroWriteEncodingPermitV1:
    """Issue an evidence-only token bound to exact immutable inputs."""
    if not isinstance(envelope, TrajectoryExecutionEnvelopeV2):
        raise TypeError("envelope must be a TrajectoryExecutionEnvelopeV2")
    if not isinstance(profile, WaveshareT102EncodingProfileV1):
        raise TypeError("profile must be a WaveshareT102EncodingProfileV1")
    if expires_monotonic_ns > envelope.measured_envelope.deadline_monotonic_ns:
        raise ZeroWriteWaveshareAdapterError(
            "preview permit may not outlive the trajectory deadline")
    return ZeroWriteEncodingPermitV1(
        _issuer=_PERMIT_ISSUER,
        envelope_v2_sha256=envelope.envelope_v2_sha256,
        encoding_profile_sha256=profile.profile_sha256,
        correlation_id=envelope.measured_envelope.correlation_id,
        controller_session_id=envelope.measured_envelope.controller_session_id,
        issued_monotonic_ns=issued_monotonic_ns,
        expires_monotonic_ns=expires_monotonic_ns,
    )


@dataclass(frozen=True, slots=True)
class EncodedWaypointCommandV1:
    waypoint_sequence: int
    time_from_start_ns: int
    scheduled_dispatch_monotonic_ns: int
    message: dict[str, int | float]
    wire_bytes: bytes

    def to_dict(self) -> dict[str, Any]:
        return {
            "waypoint_sequence": self.waypoint_sequence,
            "time_from_start_ns": self.time_from_start_ns,
            "scheduled_dispatch_monotonic_ns": self.scheduled_dispatch_monotonic_ns,
            "message": dict(self.message),
            "payload_utf8": self.wire_bytes.decode("utf-8"),
            "wire_bytes_sha256": hashlib.sha256(self.wire_bytes).hexdigest(),
        }


@dataclass(frozen=True, slots=True)
class ZeroWriteWavesharePreviewReceiptV1:
    envelope_v2_sha256: str
    measured_envelope_sha256: str
    permit_id: str
    encoding_profile_sha256: str
    correlation_id: str
    controller_session_id: str
    created_monotonic_ns: int
    commands: tuple[EncodedWaypointCommandV1, ...]
    schema: str = RECEIPT_SCHEMA

    def unsigned_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "status": "ZERO_WRITE_ENCODING_ONLY",
            "envelope_v2_sha256": self.envelope_v2_sha256,
            "measured_envelope_sha256": self.measured_envelope_sha256,
            "permit_id": self.permit_id,
            "encoding_profile_sha256": self.encoding_profile_sha256,
            "correlation_id": self.correlation_id,
            "controller_session_id": self.controller_session_id,
            "created_monotonic_ns": self.created_monotonic_ns,
            "command_count": len(self.commands),
            "commands": [item.to_dict() for item in self.commands],
            "transport_opened": False,
            "transport_write_count": 0,
            "submitted_bytes": [],
            "acknowledgements": [],
            "feedback_samples": [],
            "timeout_events": [],
            "automatic_retry": False,
            "hardware_access": False,
            "physical_authority": False,
        }

    @property
    def receipt_sha256(self) -> str:
        return hashlib.sha256(_canonical(self.unsigned_dict())).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {**self.unsigned_dict(), "receipt_sha256": self.receipt_sha256}


class ZeroWriteWaveshareAdapterV1:
    """In-memory duplicate guard around the transport-free encoder."""

    def __init__(self) -> None:
        self._seen_correlation_ids: set[str] = set()
        self._lock = threading.Lock()

    def preview(
        self, envelope: TrajectoryExecutionEnvelopeV2,
        permit: ZeroWriteEncodingPermitV1,
        profile: WaveshareT102EncodingProfileV1, *, now_monotonic_ns: int,
    ) -> ZeroWriteWavesharePreviewReceiptV1:
        if not isinstance(envelope, TrajectoryExecutionEnvelopeV2):
            raise TypeError("envelope must be a TrajectoryExecutionEnvelopeV2")
        if not isinstance(permit, ZeroWriteEncodingPermitV1):
            raise TypeError("permit must be a ZeroWriteEncodingPermitV1")
        if not isinstance(profile, WaveshareT102EncodingProfileV1):
            raise TypeError("profile must be a WaveshareT102EncodingProfileV1")
        now = _positive_ns(now_monotonic_ns, "now_monotonic_ns")
        permit_id = permit.permit_id
        permit._consume(envelope, profile, now)
        inner = envelope.measured_envelope
        with self._lock:
            if inner.correlation_id in self._seen_correlation_ids:
                raise ZeroWriteWaveshareAdapterError(
                    "correlation_id was already previewed")
            self._seen_correlation_ids.add(inner.correlation_id)
        if (
            profile.controller_session_id != inner.controller_session_id
            or profile.configuration_epoch_sha256
            != inner.configuration_epoch_sha256
        ):
            raise ZeroWriteWaveshareAdapterError(
                "encoding profile differs from the controller session")
        if profile.expected_trajectory_limits_sha256 != trajectory_limits_sha256(
                envelope):
            raise ZeroWriteWaveshareAdapterError(
                "trajectory limits are not bound to the encoding profile")
        duration_ns = inner.waypoints[-1].time_from_start_ns
        if now + duration_ns > inner.deadline_monotonic_ns:
            raise ZeroWriteWaveshareAdapterError(
                "scheduled preview would exceed the trajectory deadline")

        commands = []
        # Waypoint zero is an observed starting sample, not a motion command.
        for waypoint in inner.waypoints[1:]:
            joint_values = [
                waypoint.joint_positions_rad[name] for name in ARM_JOINT_NAMES
            ]
            message = all_joint_command(
                [*joint_values, profile.fixed_gripper_rad], speed=profile.speed,
                acceleration=profile.acceleration)
            commands.append(EncodedWaypointCommandV1(
                waypoint_sequence=waypoint.sequence,
                time_from_start_ns=waypoint.time_from_start_ns,
                scheduled_dispatch_monotonic_ns=(
                    now + waypoint.time_from_start_ns),
                message=message,
                wire_bytes=encode_line(message),
            ))
        if not commands:
            raise ZeroWriteWaveshareAdapterError("trajectory has no command waypoint")
        return ZeroWriteWavesharePreviewReceiptV1(
            envelope_v2_sha256=envelope.envelope_v2_sha256,
            measured_envelope_sha256=inner.envelope_sha256,
            permit_id=permit_id,
            encoding_profile_sha256=profile.profile_sha256,
            correlation_id=inner.correlation_id,
            controller_session_id=inner.controller_session_id,
            created_monotonic_ns=now,
            commands=tuple(commands),
        )


__all__ = [
    "GRIPPER_BEHAVIOR", "INTERPOLATION_MODE", "PERMIT_SCHEMA",
    "PROFILE_SCHEMA", "RECEIPT_SCHEMA", "EncodedWaypointCommandV1",
    "WaveshareT102EncodingProfileV1", "ZeroWriteEncodingPermitV1",
    "ZeroWriteWaveshareAdapterError", "ZeroWriteWaveshareAdapterV1",
    "ZeroWriteWavesharePreviewReceiptV1",
    "issue_zero_write_encoding_permit_v1", "trajectory_limits_sha256",
]

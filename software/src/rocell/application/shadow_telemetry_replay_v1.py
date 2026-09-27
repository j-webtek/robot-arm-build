"""Deterministic telemetry replay against a zero-write Waveshare preview.

This module lets CI compare the commands that *would* be sent with synthetic or
retained T=1051 feedback.  It has no transport, callback, device handle, or
writer.  A pass is evidence that the encoder and replayed telemetry agree under
the declared policy; it is never evidence that the physical arm moved.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import re
from typing import Any, Iterable

from rocell.arm.feedback import parse_feedback_line
from rocell.arm.protocol import encode_line

from .zero_write_waveshare_adapter_v1 import ZeroWriteWavesharePreviewReceiptV1


SCHEMA = "rocell.shadow_telemetry_replay.v1"
SAMPLE_SCHEMA = "rocell.shadow_telemetry_sample.v1"
ORIGINS = frozenset(("SYNTHETIC", "RETAINED_EXPORT"))
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_JOINT_FIELDS = (
    ("base", "base_rad"),
    ("shoulder", "shoulder_rad"),
    ("elbow", "elbow_rad"),
    ("wrist", "wrist_pitch_rad"),
    ("roll", "wrist_roll_rad"),
    ("hand", "gripper_rad"),
)
_T102_FIELDS = frozenset((
    "T", "base", "shoulder", "elbow", "wrist", "roll", "hand", "spd", "acc",
))


class ShadowTelemetryReplayError(ValueError):
    """Replay input cannot preserve exact zero-write lineage."""


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ShadowTelemetryReplayError("replay is not canonical JSON") from exc


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ShadowTelemetryReplayError(f"{label} must be a SHA-256 digest")
    return value


def _positive_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ShadowTelemetryReplayError(f"{label} must be a positive integer")
    return value


def _finite_nonnegative(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ShadowTelemetryReplayError(f"{label} must be finite and nonnegative")
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise ShadowTelemetryReplayError(f"{label} must be finite and nonnegative")
    return result


@dataclass(frozen=True, slots=True)
class ShadowTelemetryPolicyV1:
    joint_tolerance_rad: float = 0.02
    stability_span_rad: float = 0.01
    required_consecutive_samples: int = 2
    maximum_sample_lag_ns: int = 2_000_000_000

    def __post_init__(self) -> None:
        object.__setattr__(self, "joint_tolerance_rad", _finite_nonnegative(
            self.joint_tolerance_rad, "joint_tolerance_rad"))
        object.__setattr__(self, "stability_span_rad", _finite_nonnegative(
            self.stability_span_rad, "stability_span_rad"))
        if (
            isinstance(self.required_consecutive_samples, bool)
            or not isinstance(self.required_consecutive_samples, int)
            or not 2 <= self.required_consecutive_samples <= 16
        ):
            raise ShadowTelemetryReplayError(
                "required_consecutive_samples must be between 2 and 16")
        _positive_int(self.maximum_sample_lag_ns, "maximum_sample_lag_ns")

    def to_dict(self) -> dict[str, Any]:
        return {
            "joint_tolerance_rad": self.joint_tolerance_rad,
            "stability_span_rad": self.stability_span_rad,
            "required_consecutive_samples": self.required_consecutive_samples,
            "maximum_sample_lag_ns": self.maximum_sample_lag_ns,
        }

    @property
    def policy_sha256(self) -> str:
        return hashlib.sha256(_canonical(self.to_dict())).hexdigest()


@dataclass(frozen=True, slots=True)
class ShadowTelemetrySampleV1:
    correlation_id: str
    controller_session_id: str
    waypoint_sequence: int
    captured_monotonic_ns: int
    response_bytes: bytes
    schema: str = SAMPLE_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != SAMPLE_SCHEMA:
            raise ShadowTelemetryReplayError("unsupported telemetry sample schema")
        for field in ("correlation_id", "controller_session_id"):
            value = getattr(self, field)
            if not isinstance(value, str) or not value.strip() or len(value) > 128:
                raise ShadowTelemetryReplayError(f"{field} must be bounded text")
        _positive_int(self.waypoint_sequence, "waypoint_sequence")
        _positive_int(self.captured_monotonic_ns, "captured_monotonic_ns")
        if not isinstance(self.response_bytes, bytes) or not self.response_bytes:
            raise ShadowTelemetryReplayError("response_bytes must be nonempty bytes")
        if len(self.response_bytes) > 16_384:
            raise ShadowTelemetryReplayError("response_bytes exceed the bounded limit")

    def to_dict(self) -> dict[str, Any]:
        try:
            response_utf8 = self.response_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ShadowTelemetryReplayError("response_bytes must be UTF-8") from exc
        return {
            "schema": self.schema,
            "correlation_id": self.correlation_id,
            "controller_session_id": self.controller_session_id,
            "waypoint_sequence": self.waypoint_sequence,
            "captured_monotonic_ns": self.captured_monotonic_ns,
            "response_utf8": response_utf8,
            "response_sha256": hashlib.sha256(self.response_bytes).hexdigest(),
        }


def assess_shadow_telemetry_replay_v1(
    preview: ZeroWriteWavesharePreviewReceiptV1,
    samples: Iterable[ShadowTelemetrySampleV1],
    *,
    origin: str,
    policy: ShadowTelemetryPolicyV1 = ShadowTelemetryPolicyV1(),
    source_export_sha256: str | None = None,
) -> dict[str, Any]:
    """Compare exact preview targets with replayed feedback, without I/O."""

    if not isinstance(preview, ZeroWriteWavesharePreviewReceiptV1):
        raise TypeError("preview must be ZeroWriteWavesharePreviewReceiptV1")
    if not isinstance(policy, ShadowTelemetryPolicyV1):
        raise TypeError("policy must be ShadowTelemetryPolicyV1")
    if origin not in ORIGINS:
        raise ShadowTelemetryReplayError("unsupported telemetry origin")
    if origin == "RETAINED_EXPORT":
        _digest(source_export_sha256, "source_export_sha256")
    elif source_export_sha256 is not None:
        raise ShadowTelemetryReplayError(
            "synthetic telemetry may not claim a retained export")

    preview_document = preview.to_dict()
    if (
        preview_document.get("status") != "ZERO_WRITE_ENCODING_ONLY"
        or preview_document.get("transport_opened") is not False
        or preview_document.get("transport_write_count") != 0
        or preview_document.get("submitted_bytes") != []
        or preview_document.get("hardware_access") is not False
        or preview_document.get("physical_authority") is not False
    ):
        raise ShadowTelemetryReplayError("preview crossed the zero-write boundary")

    if not preview.commands:
        raise ShadowTelemetryReplayError("preview contains no command waypoint")
    command_by_sequence = {}
    prior_sequence = 0
    prior_dispatch = 0
    for command in preview.commands:
        if (
            command.waypoint_sequence <= prior_sequence
            or command.scheduled_dispatch_monotonic_ns <= prior_dispatch
        ):
            raise ShadowTelemetryReplayError(
                "preview command order or dispatch schedule is not increasing")
        if (
            set(command.message) != _T102_FIELDS
            or command.message.get("T") != 102
            or encode_line(command.message) != command.wire_bytes
        ):
            raise ShadowTelemetryReplayError(
                "preview command is not exact canonical T=102")
        command_by_sequence[command.waypoint_sequence] = command
        prior_sequence = command.waypoint_sequence
        prior_dispatch = command.scheduled_dispatch_monotonic_ns
    if len(command_by_sequence) != len(preview.commands):
        raise ShadowTelemetryReplayError("preview contains duplicate waypoint sequence")
    ordered_commands = list(preview.commands)
    next_dispatch = {
        command.waypoint_sequence: (
            ordered_commands[index + 1].scheduled_dispatch_monotonic_ns
            if index + 1 < len(ordered_commands) else None
        )
        for index, command in enumerate(ordered_commands)
    }

    grouped: dict[int, list[tuple[ShadowTelemetrySampleV1, tuple[float, ...]]]] = {
        sequence: [] for sequence in command_by_sequence
    }
    sample_documents: list[dict[str, Any]] = []
    previous_capture = 0
    for sample in samples:
        if not isinstance(sample, ShadowTelemetrySampleV1):
            raise TypeError("samples must contain ShadowTelemetrySampleV1")
        document = sample.to_dict()
        sample_documents.append(document)
        if sample.correlation_id != preview.correlation_id:
            raise ShadowTelemetryReplayError("sample binds a different correlation")
        if sample.controller_session_id != preview.controller_session_id:
            raise ShadowTelemetryReplayError("sample binds a different controller session")
        command = command_by_sequence.get(sample.waypoint_sequence)
        if command is None:
            raise ShadowTelemetryReplayError("sample names an unknown waypoint sequence")
        if sample.captured_monotonic_ns <= previous_capture:
            raise ShadowTelemetryReplayError("sample times must be globally increasing")
        previous_capture = sample.captured_monotonic_ns
        if sample.captured_monotonic_ns < command.scheduled_dispatch_monotonic_ns:
            raise ShadowTelemetryReplayError("sample predates its preview dispatch")
        boundary = next_dispatch[sample.waypoint_sequence]
        if boundary is not None and sample.captured_monotonic_ns >= boundary:
            raise ShadowTelemetryReplayError(
                "sample follows the next preview dispatch and is ambiguous")
        if (
            sample.captured_monotonic_ns - command.scheduled_dispatch_monotonic_ns
            > policy.maximum_sample_lag_ns
        ):
            raise ShadowTelemetryReplayError("sample exceeds the replay freshness limit")
        try:
            feedback = parse_feedback_line(sample.response_bytes)
        except Exception as exc:
            raise ShadowTelemetryReplayError("sample is not valid T=1051 feedback") from exc
        values = tuple(getattr(feedback, attribute) for _, attribute in _JOINT_FIELDS)
        if any(value is None for value in values):
            raise ShadowTelemetryReplayError("sample lacks complete six-joint feedback")
        grouped[sample.waypoint_sequence].append((
            sample, tuple(float(value) for value in values if value is not None)))

    waypoint_results: list[dict[str, Any]] = []
    all_settled = True
    for sequence, command in command_by_sequence.items():
        target = tuple(float(command.message[field]) for field, _ in _JOINT_FIELDS)
        prior: tuple[float, ...] | None = None
        consecutive = 0
        final_residual: tuple[float, ...] | None = None
        maximum_absolute_residual = 0.0
        for _sample, measured in grouped[sequence]:
            residual = tuple(measured[i] - target[i] for i in range(6))
            final_residual = residual
            maximum_absolute_residual = max(
                maximum_absolute_residual, *(abs(value) for value in residual))
            stable = prior is None or max(
                abs(measured[i] - prior[i]) for i in range(6)
            ) <= policy.stability_span_rad
            if (
                max(abs(value) for value in residual) <= policy.joint_tolerance_rad
                and stable
            ):
                consecutive += 1
            else:
                consecutive = 0
            prior = measured
        settled = consecutive >= policy.required_consecutive_samples
        all_settled = all_settled and settled
        waypoint_results.append({
            "waypoint_sequence": sequence,
            "command_wire_sha256": hashlib.sha256(command.wire_bytes).hexdigest(),
            "scheduled_dispatch_monotonic_ns": (
                command.scheduled_dispatch_monotonic_ns),
            "sample_count": len(grouped[sequence]),
            "consecutive_settled_samples": consecutive,
            "settled": settled,
            "final_signed_joint_residual_rad": (
                list(final_residual) if final_residual is not None else None),
            "maximum_absolute_joint_residual_rad": maximum_absolute_residual,
        })

    status = (
        "SIMULATION_REPLAY_PASS" if all_settled
        else "SIMULATION_REPLAY_UNVERIFIED"
    )
    report: dict[str, Any] = {
        "schema": SCHEMA,
        "status": status,
        "origin": origin,
        "source_export_sha256": source_export_sha256,
        "preview_receipt_sha256": preview.receipt_sha256,
        "envelope_v2_sha256": preview.envelope_v2_sha256,
        "encoding_profile_sha256": preview.encoding_profile_sha256,
        "correlation_id": preview.correlation_id,
        "controller_session_id": preview.controller_session_id,
        "policy": policy.to_dict(),
        "policy_sha256": policy.policy_sha256,
        "command_count": len(preview.commands),
        "sample_count": len(sample_documents),
        "sample_sha256": [item["response_sha256"] for item in sample_documents],
        "waypoints": waypoint_results,
        "all_waypoints_settled_in_replay": all_settled,
        "physical_arrival_proven": False,
        "independent_visual_outcome_proven": False,
        "transport_opened": False,
        "transport_write_count": 0,
        "automatic_retry": False,
        "execution_authorized": False,
        "hardware_access": False,
        "physical_authority": False,
        "limitations": [
            "OFFLINE_TELEMETRY_REPLAY_ONLY",
            "NO_AUTHENTIC_LIVE_CONTROLLER_TRANSACTION",
            "NO_INDEPENDENT_VISUAL_OUTCOME",
        ],
    }
    return {
        **report,
        "replay_sha256": hashlib.sha256(_canonical(report)).hexdigest(),
    }


__all__ = [
    "ORIGINS", "SAMPLE_SCHEMA", "SCHEMA", "ShadowTelemetryPolicyV1",
    "ShadowTelemetryReplayError", "ShadowTelemetrySampleV1",
    "assess_shadow_telemetry_replay_v1",
]

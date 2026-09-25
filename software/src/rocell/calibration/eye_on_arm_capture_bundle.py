"""Strict offline byte bundle for eye-on-arm capture diagnostics.

The bundle preserves exact T=1051 wire lines and JPEG bytes, binds those bytes
to the existing decoded-feedback, image, and target-pose records, and checks a
pre/capture/post stop-and-look bracket.  It performs no I/O except bounded file
loading and has no calibration-promotion or hardware authority.

Timing values in this schema are recorder claims.  In particular, RoArm
T=1051 does not carry a device timestamp.  The correlation digest and the
recorder-assigned capture-clock timestamps are retained so a future typed
clock-correlation artifact can verify them; this module never treats them as
physical timing qualification by themselves.
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass, field
import hashlib
import json
import math
from pathlib import Path
import re
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from rocell.arm.feedback import FeedbackError, parse_feedback_line
from rocell.arm.protocol import ProtocolError
from rocell.vision.camera import FramePacket, TimestampQuality

from .eye_on_arm_dataset import EyeOnArmDataset
from .eye_on_arm_evidence import EyeOnArmCaptureEvidence


SCHEMA = "rocell.eye_on_arm_capture_bundle.v1"
PARSER_ID = "rocell.arm.feedback.parse_feedback_line.v1"
MAX_BUNDLE_FILE_BYTES = 96 * 1024 * 1024
MAX_TOTAL_BLOB_BYTES = 64 * 1024 * 1024
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_WIRE_LINE_BYTES = 64 * 1024
MAX_DETECTION_BYTES = 128 * 1024
MAX_CAPTURE_SAMPLES = 128
MAX_JSON_DEPTH = 32

_IDENTIFIER = re.compile(r"^[A-Za-z0-9_.-]+$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_JOINT_FIELDS = ("b", "s", "e", "t", "r", "g")
_DETECTION_FIELDS = {
    "frame_sequence",
    "detector",
    "C_arm_T_B",
    "observation_count",
    "reprojection_rms_px",
}


class EyeOnArmCaptureBundleError(ValueError):
    """Offline bundle bytes or cross-record bindings are invalid."""


def _identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise EyeOnArmCaptureBundleError(f"{label} must match {_IDENTIFIER.pattern}")
    return value


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EyeOnArmCaptureBundleError(f"{label} must be non-empty text")
    return value.strip()


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise EyeOnArmCaptureBundleError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _integer(value: object, label: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise EyeOnArmCaptureBundleError(f"{label} must be an integer >= {minimum}")
    return value


def _positive(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EyeOnArmCaptureBundleError(f"{label} must be a real number")
    result = float(value)
    if not math.isfinite(result) or result <= 0.0:
        raise EyeOnArmCaptureBundleError(f"{label} must be finite and positive")
    return result


def _exact(document: Mapping[str, Any], expected: set[str], label: str) -> None:
    actual = set(document)
    if actual != expected:
        raise EyeOnArmCaptureBundleError(
            f"{label} fields differ; missing={sorted(expected - actual)}, "
            f"extra={sorted(actual - expected)}"
        )


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise EyeOnArmCaptureBundleError(f"{label} must be an object with string keys")
    return value


def _freeze_json(value: Any, *, depth: int = 0) -> Any:
    if depth > MAX_JSON_DEPTH:
        raise EyeOnArmCaptureBundleError("JSON nesting exceeds the bundle depth limit")
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise EyeOnArmCaptureBundleError("JSON contains a nonfinite number")
        return value
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str) or not key:
                raise EyeOnArmCaptureBundleError("JSON keys must be non-empty strings")
            result[key] = _freeze_json(item, depth=depth + 1)
        return MappingProxyType(result)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(item, depth=depth + 1) for item in value)
    raise EyeOnArmCaptureBundleError(
        f"JSON contains unsupported {type(value).__name__}"
    )


def _thaw_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


def _canonical_hash(value: Mapping[str, Any]) -> str:
    payload = json.dumps(
        _thaw_json(value), sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _reject_constant(value: str) -> None:
    raise EyeOnArmCaptureBundleError(f"Nonfinite JSON constant {value!r} is prohibited")


def _object_without_duplicates(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise EyeOnArmCaptureBundleError(f"Duplicate JSON field {key!r} is prohibited")
        result[key] = value
    return result


def _strict_json_bytes(payload: bytes, label: str) -> Mapping[str, Any]:
    try:
        text = payload.decode("utf-8")
        value = json.loads(
            text,
            parse_constant=_reject_constant,
            object_pairs_hook=_object_without_duplicates,
        )
    except EyeOnArmCaptureBundleError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise EyeOnArmCaptureBundleError(f"{label} is not strict UTF-8 JSON: {exc}") from exc
    document = _mapping(value, label)
    return _freeze_json(document)


def _encode_blob(payload: bytes) -> str:
    return base64.b64encode(payload).decode("ascii")


def _decode_blob(value: object, label: str, maximum_bytes: int) -> bytes:
    if not isinstance(value, str):
        raise EyeOnArmCaptureBundleError(f"{label} must be base64 text")
    maximum_encoded = ((maximum_bytes + 2) // 3) * 4
    if len(value) > maximum_encoded:
        raise EyeOnArmCaptureBundleError(f"{label} exceeds its encoded resource limit")
    try:
        result = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise EyeOnArmCaptureBundleError(f"{label} is not strict base64") from exc
    if len(result) > maximum_bytes:
        raise EyeOnArmCaptureBundleError(f"{label} exceeds its decoded resource limit")
    return result


@dataclass(frozen=True, slots=True)
class FeedbackWireObservation:
    """One exact newline-terminated T=1051 line plus recorder timing metadata."""

    sample_id: str
    record_id: str
    request_sequence: int
    host_request_ns: int
    host_first_byte_ns: int
    host_complete_ns: int
    host_clock_id: str
    correlated_capture_timestamp_ns: int
    capture_clock_id: str
    clock_correlation_sha256: str
    wire_sha256: str
    decoded_fields_sha256: str
    wire_bytes: bytes
    parser_id: str = PARSER_ID
    decoded_fields: Mapping[str, Any] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        _identifier(self.sample_id, "sample_id")
        _identifier(self.record_id, "record_id")
        _integer(self.request_sequence, "request_sequence")
        for name in (
            "host_request_ns",
            "host_first_byte_ns",
            "host_complete_ns",
            "correlated_capture_timestamp_ns",
        ):
            _integer(getattr(self, name), name)
        if not self.host_request_ns <= self.host_first_byte_ns <= self.host_complete_ns:
            raise EyeOnArmCaptureBundleError("Feedback host timestamps are out of order")
        _identifier(self.host_clock_id, "host_clock_id")
        _identifier(self.capture_clock_id, "capture_clock_id")
        _digest(self.clock_correlation_sha256, "clock_correlation_sha256")
        _digest(self.wire_sha256, "wire_sha256")
        _digest(self.decoded_fields_sha256, "decoded_fields_sha256")
        if self.parser_id != PARSER_ID:
            raise EyeOnArmCaptureBundleError(f"Unsupported feedback parser {self.parser_id!r}")
        if not isinstance(self.wire_bytes, bytes):
            raise EyeOnArmCaptureBundleError("wire_bytes must be immutable bytes")
        if len(self.wire_bytes) > MAX_WIRE_LINE_BYTES:
            raise EyeOnArmCaptureBundleError("T=1051 wire line exceeds resource limit")
        if hashlib.sha256(self.wire_bytes).hexdigest() != self.wire_sha256:
            raise EyeOnArmCaptureBundleError("T=1051 wire-byte hash mismatch")
        try:
            parsed = parse_feedback_line(self.wire_bytes)
        except (FeedbackError, ProtocolError, RecursionError, ValueError) as exc:
            raise EyeOnArmCaptureBundleError(f"Invalid T=1051 wire line: {exc}") from exc
        decoded = _freeze_json(parsed.raw_fields)
        if _canonical_hash(decoded) != self.decoded_fields_sha256:
            raise EyeOnArmCaptureBundleError("Decoded T=1051 field hash mismatch")
        if any(parsed.field(name) is None for name in _JOINT_FIELDS):
            raise EyeOnArmCaptureBundleError("T=1051 wire line lacks a complete joint vector")
        object.__setattr__(self, "decoded_fields", decoded)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sample_id": self.sample_id,
            "record_id": self.record_id,
            "request_sequence": self.request_sequence,
            "parser_id": self.parser_id,
            "host_timing": {
                "request_ns": self.host_request_ns,
                "first_byte_ns": self.host_first_byte_ns,
                "complete_ns": self.host_complete_ns,
                "clock_id": self.host_clock_id,
            },
            "capture_clock_projection": {
                "timestamp_ns": self.correlated_capture_timestamp_ns,
                "clock_id": self.capture_clock_id,
                "clock_correlation_sha256": self.clock_correlation_sha256,
                "qualification": "RECORDER_CLAIM_NOT_CONTENT_VERIFIED",
            },
            "wire_sha256": self.wire_sha256,
            "decoded_fields_sha256": self.decoded_fields_sha256,
            "wire_base64": _encode_blob(self.wire_bytes),
        }


@dataclass(frozen=True, slots=True)
class NormalizedDetectionEvidence:
    """Exact normalized bytes for the existing ``TargetPoseRecord`` schema.

    This is not raw AprilTag detector output.  Tag IDs, corners, inlier masks,
    covariance, and detector logs remain an explicit physical-evidence blocker.
    """

    detector_version: str
    input_image_sha256: str
    camera_intrinsics_sha256: str
    tag_map_sha256: str
    normalized_json_sha256: str
    normalized_json_bytes: bytes
    document: Mapping[str, Any] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        _text(self.detector_version, "detector_version")
        _digest(self.input_image_sha256, "input_image_sha256")
        _digest(self.camera_intrinsics_sha256, "camera_intrinsics_sha256")
        _digest(self.tag_map_sha256, "tag_map_sha256")
        _digest(self.normalized_json_sha256, "normalized_json_sha256")
        if not isinstance(self.normalized_json_bytes, bytes):
            raise EyeOnArmCaptureBundleError(
                "normalized_json_bytes must be immutable bytes"
            )
        if len(self.normalized_json_bytes) > MAX_DETECTION_BYTES:
            raise EyeOnArmCaptureBundleError("Normalized detection exceeds resource limit")
        if (
            hashlib.sha256(self.normalized_json_bytes).hexdigest()
            != self.normalized_json_sha256
        ):
            raise EyeOnArmCaptureBundleError("Normalized detection byte hash mismatch")
        document = _strict_json_bytes(
            self.normalized_json_bytes, "normalized detection"
        )
        _exact(document, _DETECTION_FIELDS, "normalized detection")
        if document["detector"] != "apriltag_bundle":
            raise EyeOnArmCaptureBundleError(
                "Normalized physical detection must use apriltag_bundle"
            )
        object.__setattr__(self, "document", document)

    def to_dict(self) -> dict[str, Any]:
        return {
            "detector_version": self.detector_version,
            "input_image_sha256": self.input_image_sha256,
            "camera_intrinsics_sha256": self.camera_intrinsics_sha256,
            "tag_map_sha256": self.tag_map_sha256,
            "normalized_json_sha256": self.normalized_json_sha256,
            "normalized_json_base64": _encode_blob(self.normalized_json_bytes),
        }


def _frame_dict(frame: FramePacket, host_clock_id: str) -> dict[str, Any]:
    return {
        "capture_id": frame.capture_id,
        "jpeg_sha256": frame.sha256,
        "jpeg_base64": _encode_blob(frame.jpeg_bytes),
        "width_px": frame.width_px,
        "height_px": frame.height_px,
        "source_sequence": frame.source_sequence,
        "source_timestamp_ns": frame.source_timestamp_ns,
        "source_clock": frame.source_clock,
        "host_request_ns": frame.host_request_ns,
        "host_first_byte_ns": frame.host_first_byte_ns,
        "host_complete_ns": frame.host_complete_ns,
        "host_clock_id": host_clock_id,
        "settings_hash": frame.settings_hash,
        "timestamp_quality": frame.timestamp_quality.value,
        "freshness_token": frame.freshness_token,
        "freshness_basis": frame.freshness_basis,
    }


@dataclass(frozen=True, slots=True)
class CaptureBundleSample:
    """Byte-complete inputs and a recorder-claimed timing bracket for one pose."""

    sample_id: str
    frame: FramePacket
    frame_host_clock_id: str
    exposure_start_ns: int
    exposure_end_ns: int
    exposure_clock_id: str
    clock_correlation_sha256: str
    pre_feedback: FeedbackWireObservation
    post_feedback: FeedbackWireObservation
    representative_phase: str
    detection: NormalizedDetectionEvidence

    def __post_init__(self) -> None:
        _identifier(self.sample_id, "sample_id")
        if not isinstance(self.frame, FramePacket):
            raise TypeError("frame must be a FramePacket")
        if len(self.frame.jpeg_bytes) > MAX_IMAGE_BYTES:
            raise EyeOnArmCaptureBundleError("JPEG frame exceeds bundle resource limit")
        _identifier(self.frame_host_clock_id, "frame_host_clock_id")
        _integer(self.exposure_start_ns, "exposure_start_ns")
        _integer(self.exposure_end_ns, "exposure_end_ns")
        if self.exposure_end_ns < self.exposure_start_ns:
            raise EyeOnArmCaptureBundleError("Exposure interval is reversed")
        _identifier(self.exposure_clock_id, "exposure_clock_id")
        _digest(self.clock_correlation_sha256, "clock_correlation_sha256")
        if not isinstance(self.pre_feedback, FeedbackWireObservation) or not isinstance(
            self.post_feedback, FeedbackWireObservation
        ):
            raise TypeError("pre/post feedback must be FeedbackWireObservation values")
        if not isinstance(self.detection, NormalizedDetectionEvidence):
            raise TypeError("detection must be NormalizedDetectionEvidence")
        if self.representative_phase not in {"PRE", "POST"}:
            raise EyeOnArmCaptureBundleError("representative_phase must be PRE or POST")
        if self.frame.capture_id != self.sample_id:
            raise EyeOnArmCaptureBundleError("Frame capture_id must equal sample_id")
        if self.frame.timestamp_quality is not TimestampQuality.DEVICE_EXPOSURE:
            raise EyeOnArmCaptureBundleError(
                "Bundle requires a device-exposure timestamp claim"
            )
        if self.frame.source_timestamp_ns is None or self.frame.source_clock is None:
            raise EyeOnArmCaptureBundleError("Frame lacks source exposure timing")
        if self.frame.source_clock != self.exposure_clock_id:
            raise EyeOnArmCaptureBundleError("Frame and exposure clocks differ")
        if not (
            self.exposure_start_ns
            <= self.frame.source_timestamp_ns
            <= self.exposure_end_ns
        ):
            raise EyeOnArmCaptureBundleError(
                "Frame source timestamp lies outside its exposure interval"
            )
        pre = self.pre_feedback
        post = self.post_feedback
        if pre.record_id == post.record_id:
            raise EyeOnArmCaptureBundleError("Pre/post feedback record ids must differ")
        if pre.sample_id != self.sample_id or post.sample_id != self.sample_id:
            raise EyeOnArmCaptureBundleError("Pre/post feedback sample ids differ")
        if pre.request_sequence >= post.request_sequence:
            raise EyeOnArmCaptureBundleError("Pre/post feedback sequence is reversed")
        if pre.host_clock_id != self.frame_host_clock_id or post.host_clock_id != self.frame_host_clock_id:
            raise EyeOnArmCaptureBundleError("Frame and feedback host clocks differ")
        if not (
            pre.host_complete_ns
            <= self.frame.host_request_ns
            <= self.frame.host_complete_ns
            <= post.host_request_ns
        ):
            raise EyeOnArmCaptureBundleError(
                "Feedback does not bracket the complete host capture transaction"
            )
        if (
            pre.capture_clock_id != self.exposure_clock_id
            or post.capture_clock_id != self.exposure_clock_id
            or pre.clock_correlation_sha256 != self.clock_correlation_sha256
            or post.clock_correlation_sha256 != self.clock_correlation_sha256
        ):
            raise EyeOnArmCaptureBundleError(
                "Feedback/exposure clock-correlation claims differ"
            )
        if not (
            pre.correlated_capture_timestamp_ns
            <= self.exposure_start_ns
            <= self.exposure_end_ns
            <= post.correlated_capture_timestamp_ns
        ):
            raise EyeOnArmCaptureBundleError(
                "Feedback capture-clock projections do not bracket exposure"
            )

    @property
    def representative_feedback(self) -> FeedbackWireObservation:
        return self.pre_feedback if self.representative_phase == "PRE" else self.post_feedback

    def to_dict(self) -> dict[str, Any]:
        return {
            "sample_id": self.sample_id,
            "frame": _frame_dict(self.frame, self.frame_host_clock_id),
            "exposure_interval": {
                "start_ns": self.exposure_start_ns,
                "end_ns": self.exposure_end_ns,
                "clock_id": self.exposure_clock_id,
                "clock_correlation_sha256": self.clock_correlation_sha256,
                "qualification": "RECORDER_CLAIM_NOT_CONTENT_VERIFIED",
            },
            "pre_feedback": self.pre_feedback.to_dict(),
            "post_feedback": self.post_feedback.to_dict(),
            "representative_phase": self.representative_phase,
            "detection": self.detection.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class EyeOnArmCaptureBundle:
    bundle_id: str
    dataset_id: str
    dataset_sha256: str
    evidence_id: str
    evidence_sha256: str
    samples: tuple[CaptureBundleSample, ...]
    schema: str = SCHEMA
    physical_release_effect: str = "NONE"

    def __post_init__(self) -> None:
        if self.schema != SCHEMA:
            raise EyeOnArmCaptureBundleError(f"Unsupported bundle schema {self.schema!r}")
        _identifier(self.bundle_id, "bundle_id")
        _identifier(self.dataset_id, "dataset_id")
        _digest(self.dataset_sha256, "dataset_sha256")
        _identifier(self.evidence_id, "evidence_id")
        _digest(self.evidence_sha256, "evidence_sha256")
        if self.physical_release_effect != "NONE":
            raise EyeOnArmCaptureBundleError("Capture bundle cannot release physical motion")
        samples = tuple(self.samples)
        if not samples:
            raise EyeOnArmCaptureBundleError("Capture bundle cannot be empty")
        if len(samples) > MAX_CAPTURE_SAMPLES:
            raise EyeOnArmCaptureBundleError("Capture bundle exceeds sample limit")
        if any(not isinstance(sample, CaptureBundleSample) for sample in samples):
            raise TypeError("samples must contain only CaptureBundleSample values")
        if len({sample.sample_id for sample in samples}) != len(samples):
            raise EyeOnArmCaptureBundleError("Capture bundle sample ids must be unique")
        records = tuple(
            record
            for sample in samples
            for record in (sample.pre_feedback, sample.post_feedback)
        )
        record_ids = [record.record_id for record in records]
        request_sequences = [record.request_sequence for record in records]
        if len(set(record_ids)) != len(record_ids):
            raise EyeOnArmCaptureBundleError("Feedback record ids must be globally unique")
        if request_sequences != sorted(request_sequences) or len(set(request_sequences)) != len(
            request_sequences
        ):
            raise EyeOnArmCaptureBundleError(
                "Feedback request sequences must be globally strict and increasing"
            )
        if len({record.host_clock_id for record in records}) != 1:
            raise EyeOnArmCaptureBundleError("Feedback host clock id must be bundle-wide")
        if len({record.capture_clock_id for record in records}) != 1:
            raise EyeOnArmCaptureBundleError("Feedback capture clock id must be bundle-wide")
        if len({sample.clock_correlation_sha256 for sample in samples}) != 1:
            raise EyeOnArmCaptureBundleError(
                "Clock-correlation digest must be bundle-wide"
            )
        for previous, current in zip(records, records[1:]):
            if previous.host_complete_ns > current.host_request_ns:
                raise EyeOnArmCaptureBundleError(
                    "Feedback host intervals must be globally ordered and non-overlapping"
                )
            if (
                previous.correlated_capture_timestamp_ns
                >= current.correlated_capture_timestamp_ns
            ):
                raise EyeOnArmCaptureBundleError(
                    "Feedback capture-clock projections must be globally increasing"
                )
        total_bytes = sum(
            len(sample.frame.jpeg_bytes)
            + len(sample.pre_feedback.wire_bytes)
            + len(sample.post_feedback.wire_bytes)
            + len(sample.detection.normalized_json_bytes)
            for sample in samples
        )
        if total_bytes > MAX_TOTAL_BLOB_BYTES:
            raise EyeOnArmCaptureBundleError("Capture bundle exceeds total blob limit")
        object.__setattr__(self, "samples", samples)

    @property
    def content_hash(self) -> str:
        payload = json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "bundle_id": self.bundle_id,
            "dataset_id": self.dataset_id,
            "dataset_sha256": self.dataset_sha256,
            "evidence_id": self.evidence_id,
            "evidence_sha256": self.evidence_sha256,
            "physical_release_effect": self.physical_release_effect,
            "parser_id": PARSER_ID,
            "samples": [sample.to_dict() for sample in self.samples],
            "authority": {
                "physical_timing_qualified": False,
                "artifact_created": False,
                "artifact_installed": False,
                "motion_authorized": False,
                "contact_authorized": False,
            },
        }


@dataclass(frozen=True, slots=True)
class CaptureBundleVerificationPolicy:
    maximum_joint_drift_rad: float = 0.002
    maximum_joint_record_error_rad: float = 0.002
    maximum_bracket_span_ns: int = 2_000_000_000
    maximum_exposure_duration_ns: int = 100_000_000
    maximum_samples: int = MAX_CAPTURE_SAMPLES
    policy_id: str = "ROCELL-EYE-ON-ARM-CAPTURE-BUNDLE-VERIFY-001"

    def __post_init__(self) -> None:
        _identifier(self.policy_id, "policy_id")
        object.__setattr__(
            self,
            "maximum_joint_drift_rad",
            _positive(self.maximum_joint_drift_rad, "maximum_joint_drift_rad"),
        )
        object.__setattr__(
            self,
            "maximum_joint_record_error_rad",
            _positive(
                self.maximum_joint_record_error_rad,
                "maximum_joint_record_error_rad",
            ),
        )
        _integer(self.maximum_bracket_span_ns, "maximum_bracket_span_ns", minimum=1)
        _integer(
            self.maximum_exposure_duration_ns,
            "maximum_exposure_duration_ns",
            minimum=1,
        )
        _integer(self.maximum_samples, "maximum_samples", minimum=1)
        if self.maximum_samples > MAX_CAPTURE_SAMPLES:
            raise EyeOnArmCaptureBundleError(
                f"maximum_samples cannot exceed {MAX_CAPTURE_SAMPLES}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "maximum_joint_drift_rad": self.maximum_joint_drift_rad,
            "maximum_joint_record_error_rad": self.maximum_joint_record_error_rad,
            "maximum_bracket_span_ns": self.maximum_bracket_span_ns,
            "maximum_exposure_duration_ns": self.maximum_exposure_duration_ns,
            "maximum_samples": self.maximum_samples,
        }


DEFAULT_CAPTURE_BUNDLE_POLICY = CaptureBundleVerificationPolicy()

CAPTURE_BUNDLE_PHYSICAL_BLOCKERS = (
    "CAMERA_AND_ARTIFACT_IDENTITIES_NOT_REGISTRY_RESOLVED",
    "CLOCK_CORRELATION_ARTIFACT_NOT_CONTENT_VERIFIED",
    "T1051_DEVICE_MEASUREMENT_TIMESTAMP_NOT_ON_WIRE",
    "RAW_APRILTAG_CORNERS_INLIERS_AND_COVARIANCE_NOT_RETAINED",
    "PHYSICAL_DWELL_AND_SETTLING_NOT_INDEPENDENTLY_PROVEN",
    "NO_COMMISSIONING_AUTHORITY",
)


@dataclass(frozen=True, slots=True)
class CaptureBundleSampleVerification:
    sample_id: str
    maximum_joint_drift_rad: float
    maximum_joint_record_error_rad: float
    bracket_span_ns: int
    exposure_duration_ns: int
    passed: bool
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        _identifier(self.sample_id, "sample_id")
        for name in ("maximum_joint_drift_rad", "maximum_joint_record_error_rad"):
            value = getattr(self, name)
            if not isinstance(value, (int, float)) or not math.isfinite(float(value)) or value < 0:
                raise EyeOnArmCaptureBundleError(f"{name} must be finite and non-negative")
        _integer(self.bracket_span_ns, "bracket_span_ns")
        _integer(self.exposure_duration_ns, "exposure_duration_ns")
        if not isinstance(self.passed, bool):
            raise TypeError("passed must be a bool")
        reasons = tuple(_identifier(reason, "verification reason") for reason in self.reasons)
        if len(set(reasons)) != len(reasons):
            raise EyeOnArmCaptureBundleError("Verification reasons must be unique")
        object.__setattr__(self, "reasons", reasons)
        if self.passed == bool(reasons):
            raise EyeOnArmCaptureBundleError("Sample passes exactly when reasons are empty")

    def to_dict(self) -> dict[str, Any]:
        return {
            "sample_id": self.sample_id,
            "maximum_joint_drift_rad": self.maximum_joint_drift_rad,
            "maximum_joint_record_error_rad": self.maximum_joint_record_error_rad,
            "bracket_span_ns": self.bracket_span_ns,
            "exposure_duration_ns": self.exposure_duration_ns,
            "passed": self.passed,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True, slots=True)
class EyeOnArmCaptureBundleVerification:
    bundle_id: str
    bundle_hash: str
    dataset_hash: str
    evidence_hash: str
    policy: CaptureBundleVerificationPolicy
    samples: tuple[CaptureBundleSampleVerification, ...]
    status: str
    blockers: tuple[str, ...] = CAPTURE_BUNDLE_PHYSICAL_BLOCKERS
    physical_release_effect: str = "NONE"

    def __post_init__(self) -> None:
        _identifier(self.bundle_id, "bundle_id")
        _digest(self.bundle_hash, "bundle_hash")
        _digest(self.dataset_hash, "dataset_hash")
        _digest(self.evidence_hash, "evidence_hash")
        if not isinstance(self.policy, CaptureBundleVerificationPolicy):
            raise TypeError("policy must be a CaptureBundleVerificationPolicy")
        samples = tuple(self.samples)
        if len({sample.sample_id for sample in samples}) != len(samples):
            raise EyeOnArmCaptureBundleError("Verification sample ids must be unique")
        for sample in samples:
            expected_reasons: list[str] = []
            if sample.maximum_joint_drift_rad > self.policy.maximum_joint_drift_rad:
                expected_reasons.append("JOINT_DRIFT_EXCEEDED")
            if (
                sample.maximum_joint_record_error_rad
                > self.policy.maximum_joint_record_error_rad
            ):
                expected_reasons.append("JOINT_RECORD_MISMATCH")
            if sample.bracket_span_ns > self.policy.maximum_bracket_span_ns:
                expected_reasons.append("BRACKET_SPAN_EXCEEDED")
            if (
                sample.exposure_duration_ns
                > self.policy.maximum_exposure_duration_ns
            ):
                expected_reasons.append("EXPOSURE_DURATION_EXCEEDED")
            if sample.reasons != tuple(expected_reasons):
                raise EyeOnArmCaptureBundleError(
                    f"Sample {sample.sample_id} reasons differ from bundle policy"
                )
        object.__setattr__(self, "samples", samples)
        blockers = tuple(_identifier(item, "blocker") for item in self.blockers)
        if blockers != CAPTURE_BUNDLE_PHYSICAL_BLOCKERS:
            raise EyeOnArmCaptureBundleError(
                "Capture-bundle physical blocker set is fixed and cannot be weakened"
            )
        object.__setattr__(self, "blockers", blockers)
        expected = (
            "STRUCTURAL_PASS_NO_PHYSICAL_AUTHORITY"
            if samples and all(sample.passed for sample in samples)
            else "STRUCTURAL_FAIL_NO_PHYSICAL_AUTHORITY"
        )
        if self.status != expected:
            raise EyeOnArmCaptureBundleError("Verification status differs from samples")
        if self.physical_release_effect != "NONE":
            raise EyeOnArmCaptureBundleError("Bundle verification cannot release motion")

    @property
    def report_hash(self) -> str:
        payload = json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    @property
    def structural_passed(self) -> bool:
        """Whether all bounded structural checks passed; never physical authority."""

        return self.status == "STRUCTURAL_PASS_NO_PHYSICAL_AUTHORITY"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "rocell.eye_on_arm_capture_bundle_verification.v1",
            "status": self.status,
            "physical_release_effect": self.physical_release_effect,
            "bundle_id": self.bundle_id,
            "bundle_hash": self.bundle_hash,
            "dataset_hash": self.dataset_hash,
            "evidence_hash": self.evidence_hash,
            "policy": self.policy.to_dict(),
            "resource_limits": {
                "maximum_bundle_file_bytes": MAX_BUNDLE_FILE_BYTES,
                "maximum_total_blob_bytes": MAX_TOTAL_BLOB_BYTES,
                "maximum_image_bytes": MAX_IMAGE_BYTES,
                "maximum_wire_line_bytes": MAX_WIRE_LINE_BYTES,
                "maximum_normalized_detection_bytes": MAX_DETECTION_BYTES,
                "maximum_capture_samples": MAX_CAPTURE_SAMPLES,
                "maximum_json_depth": MAX_JSON_DEPTH,
            },
            "samples": [sample.to_dict() for sample in self.samples],
            "physical_acceptance_blockers": list(self.blockers),
            "authority": {
                "eligible_for_commissioning": False,
                "artifact_created": False,
                "artifact_installed": False,
                "motion_authorized": False,
                "contact_authorized": False,
            },
        }


def assemble_eye_on_arm_capture_bundle(
    bundle_id: str,
    dataset: EyeOnArmDataset,
    evidence: EyeOnArmCaptureEvidence,
    samples: Sequence[CaptureBundleSample],
) -> EyeOnArmCaptureBundle:
    """Assemble immutable offline records without claiming capture authenticity."""

    if not isinstance(dataset, EyeOnArmDataset):
        raise TypeError("dataset must be an EyeOnArmDataset")
    if not isinstance(evidence, EyeOnArmCaptureEvidence):
        raise TypeError("evidence must be an EyeOnArmCaptureEvidence")
    if dataset.dataset_kind != "OFFLINE_CAPTURE":
        raise EyeOnArmCaptureBundleError("Capture bundles require OFFLINE_CAPTURE datasets")
    if dataset.camera.pixel_format != "MJPG":
        raise EyeOnArmCaptureBundleError("Byte capture bundles currently require MJPG frames")
    if evidence.dataset_id != dataset.dataset_id or evidence.dataset_sha256 != dataset.content_hash:
        raise EyeOnArmCaptureBundleError("Evidence is bound to a different dataset")
    frozen = tuple(samples)
    expected_ids = tuple(sample.sample_id for sample in dataset.samples)
    if tuple(sample.sample_id for sample in frozen) != expected_ids:
        raise EyeOnArmCaptureBundleError(
            "Bundle samples must exactly cover the dataset in dataset order"
        )
    return EyeOnArmCaptureBundle(
        bundle_id=bundle_id,
        dataset_id=dataset.dataset_id,
        dataset_sha256=dataset.content_hash,
        evidence_id=evidence.evidence_id,
        evidence_sha256=evidence.content_hash,
        samples=frozen,
    )


def verify_eye_on_arm_capture_bundle(
    dataset: EyeOnArmDataset,
    evidence: EyeOnArmCaptureEvidence,
    bundle: EyeOnArmCaptureBundle,
    *,
    policy: CaptureBundleVerificationPolicy = DEFAULT_CAPTURE_BUNDLE_POLICY,
) -> EyeOnArmCaptureBundleVerification:
    """Verify byte, schema, image, detection, bracket, and joint bindings offline."""

    if not isinstance(dataset, EyeOnArmDataset):
        raise TypeError("dataset must be an EyeOnArmDataset")
    if not isinstance(evidence, EyeOnArmCaptureEvidence):
        raise TypeError("evidence must be an EyeOnArmCaptureEvidence")
    if not isinstance(bundle, EyeOnArmCaptureBundle):
        raise TypeError("bundle must be an EyeOnArmCaptureBundle")
    if not isinstance(policy, CaptureBundleVerificationPolicy):
        raise TypeError("policy must be a CaptureBundleVerificationPolicy")
    if len(bundle.samples) > policy.maximum_samples:
        raise EyeOnArmCaptureBundleError("Bundle exceeds verification sample limit")
    if dataset.camera.pixel_format != "MJPG":
        raise EyeOnArmCaptureBundleError("Byte capture bundles currently require MJPG frames")
    if (
        bundle.dataset_id != dataset.dataset_id
        or bundle.dataset_sha256 != dataset.content_hash
        or bundle.evidence_id != evidence.evidence_id
        or bundle.evidence_sha256 != evidence.content_hash
    ):
        raise EyeOnArmCaptureBundleError("Bundle dataset/evidence binding mismatch")
    dataset_ids = tuple(sample.sample_id for sample in dataset.samples)
    if tuple(sample.sample_id for sample in bundle.samples) != dataset_ids:
        raise EyeOnArmCaptureBundleError("Bundle sample coverage/order differs from dataset")
    representative_by_id = {
        record.sample_id: record for record in evidence.raw_joint_feedback
    }
    if set(representative_by_id) != set(dataset_ids):
        raise EyeOnArmCaptureBundleError("Evidence representative coverage differs from dataset")
    rules = {rule.urdf_joint: rule for rule in evidence.joint_reference}
    results: list[CaptureBundleSampleVerification] = []
    for dataset_sample, bundled in zip(dataset.samples, bundle.samples):
        frame = bundled.frame
        if (
            frame.sha256 != dataset_sample.frame.source_sha256
            or frame.width_px != dataset_sample.frame.width_px
            or frame.height_px != dataset_sample.frame.height_px
            or frame.source_sequence != dataset_sample.frame.sequence
            or frame.source_timestamp_ns != dataset_sample.frame.timestamp_ns
            or frame.source_clock != dataset_sample.frame.clock_id
            or frame.settings_hash != evidence.camera_settings_sha256
        ):
            raise EyeOnArmCaptureBundleError(
                f"Frame bytes/metadata differ for sample {bundled.sample_id}"
            )
        if (
            bundled.clock_correlation_sha256
            != evidence.timing_qualification_sha256
        ):
            raise EyeOnArmCaptureBundleError(
                f"Timing-correlation hash differs for sample {bundled.sample_id}"
            )
        if bundled.detection.input_image_sha256 != frame.sha256:
            raise EyeOnArmCaptureBundleError("Detection input image hash mismatch")
        if (
            bundled.detection.camera_intrinsics_sha256
            != dataset.source_hashes["camera_intrinsics"]
        ):
            raise EyeOnArmCaptureBundleError("Detection camera-intrinsics hash mismatch")
        if bundled.detection.tag_map_sha256 != dataset.source_hashes["measured_tag_map"]:
            raise EyeOnArmCaptureBundleError("Detection tag-map hash mismatch")
        expected_detection = dataset_sample.target_pose.to_dict()
        if _thaw_json(bundled.detection.document) != expected_detection:
            raise EyeOnArmCaptureBundleError(
                f"Normalized detection differs for sample {bundled.sample_id}"
            )
        representative = bundled.representative_feedback
        stored_representative = representative_by_id[bundled.sample_id]
        if (
            representative.decoded_fields_sha256
            != stored_representative.fields_sha256
            or _thaw_json(representative.decoded_fields)
            != _thaw_json(stored_representative.fields)
            or representative.correlated_capture_timestamp_ns
            != stored_representative.timestamp_ns
            or representative.capture_clock_id != stored_representative.clock_id
            or stored_representative.joint_sequence
            != dataset_sample.joint_state.sequence
            or stored_representative.timestamp_ns
            != dataset_sample.joint_state.timestamp_ns
            or stored_representative.clock_id != dataset_sample.joint_state.clock_id
        ):
            raise EyeOnArmCaptureBundleError(
                f"Representative raw feedback differs for sample {bundled.sample_id}"
            )
        stored_positions = dataset_sample.joint_state.positions_by_name
        projected: list[dict[str, float]] = []
        for observation in (bundled.pre_feedback, bundled.post_feedback):
            fields = observation.decoded_fields
            projected.append(
                {
                    joint: rule.project(fields[rule.feedback_field])
                    for joint, rule in rules.items()
                }
            )
        drift = max(
            abs(projected[1][joint] - projected[0][joint]) for joint in rules
        )
        record_error = max(
            abs(values[joint] - stored_positions[joint])
            for values in projected
            for joint in rules
        )
        bracket_span = (
            bundled.post_feedback.correlated_capture_timestamp_ns
            - bundled.pre_feedback.correlated_capture_timestamp_ns
        )
        exposure_duration = bundled.exposure_end_ns - bundled.exposure_start_ns
        reasons: list[str] = []
        if drift > policy.maximum_joint_drift_rad:
            reasons.append("JOINT_DRIFT_EXCEEDED")
        if record_error > policy.maximum_joint_record_error_rad:
            reasons.append("JOINT_RECORD_MISMATCH")
        if bracket_span > policy.maximum_bracket_span_ns:
            reasons.append("BRACKET_SPAN_EXCEEDED")
        if exposure_duration > policy.maximum_exposure_duration_ns:
            reasons.append("EXPOSURE_DURATION_EXCEEDED")
        results.append(
            CaptureBundleSampleVerification(
                sample_id=bundled.sample_id,
                maximum_joint_drift_rad=drift,
                maximum_joint_record_error_rad=record_error,
                bracket_span_ns=bracket_span,
                exposure_duration_ns=exposure_duration,
                passed=not reasons,
                reasons=tuple(reasons),
            )
        )
    samples = tuple(results)
    return EyeOnArmCaptureBundleVerification(
        bundle_id=bundle.bundle_id,
        bundle_hash=bundle.content_hash,
        dataset_hash=dataset.content_hash,
        evidence_hash=evidence.content_hash,
        policy=policy,
        samples=samples,
        status=(
            "STRUCTURAL_PASS_NO_PHYSICAL_AUTHORITY"
            if all(sample.passed for sample in samples)
            else "STRUCTURAL_FAIL_NO_PHYSICAL_AUTHORITY"
        ),
    )


def _wire_from_dict(value: object) -> FeedbackWireObservation:
    document = _mapping(value, "feedback observation")
    _exact(
        document,
        {
            "record_id",
            "sample_id",
            "request_sequence",
            "parser_id",
            "host_timing",
            "capture_clock_projection",
            "wire_sha256",
            "decoded_fields_sha256",
            "wire_base64",
        },
        "feedback observation",
    )
    host = _mapping(document["host_timing"], "host_timing")
    _exact(host, {"request_ns", "first_byte_ns", "complete_ns", "clock_id"}, "host_timing")
    projection = _mapping(document["capture_clock_projection"], "capture_clock_projection")
    _exact(
        projection,
        {
            "timestamp_ns",
            "clock_id",
            "clock_correlation_sha256",
            "qualification",
        },
        "capture_clock_projection",
    )
    if projection["qualification"] != "RECORDER_CLAIM_NOT_CONTENT_VERIFIED":
        raise EyeOnArmCaptureBundleError("Unsupported capture-clock qualification")
    return FeedbackWireObservation(
        sample_id=_identifier(document["sample_id"], "sample_id"),
        record_id=_identifier(document["record_id"], "record_id"),
        request_sequence=_integer(document["request_sequence"], "request_sequence"),
        parser_id=_text(document["parser_id"], "parser_id"),
        host_request_ns=_integer(host["request_ns"], "request_ns"),
        host_first_byte_ns=_integer(host["first_byte_ns"], "first_byte_ns"),
        host_complete_ns=_integer(host["complete_ns"], "complete_ns"),
        host_clock_id=_identifier(host["clock_id"], "host clock_id"),
        correlated_capture_timestamp_ns=_integer(projection["timestamp_ns"], "timestamp_ns"),
        capture_clock_id=_identifier(projection["clock_id"], "capture clock_id"),
        clock_correlation_sha256=_digest(
            projection["clock_correlation_sha256"], "clock_correlation_sha256"
        ),
        wire_sha256=_digest(document["wire_sha256"], "wire_sha256"),
        decoded_fields_sha256=_digest(
            document["decoded_fields_sha256"], "decoded_fields_sha256"
        ),
        wire_bytes=_decode_blob(document["wire_base64"], "wire_base64", MAX_WIRE_LINE_BYTES),
    )


def _frame_from_dict(value: object) -> tuple[FramePacket, str]:
    document = _mapping(value, "frame")
    _exact(
        document,
        {
            "capture_id",
            "jpeg_sha256",
            "jpeg_base64",
            "width_px",
            "height_px",
            "source_sequence",
            "source_timestamp_ns",
            "source_clock",
            "host_request_ns",
            "host_first_byte_ns",
            "host_complete_ns",
            "host_clock_id",
            "settings_hash",
            "timestamp_quality",
            "freshness_token",
            "freshness_basis",
        },
        "frame",
    )
    jpeg = _decode_blob(document["jpeg_base64"], "jpeg_base64", MAX_IMAGE_BYTES)
    if hashlib.sha256(jpeg).hexdigest() != _digest(document["jpeg_sha256"], "jpeg_sha256"):
        raise EyeOnArmCaptureBundleError("JPEG byte hash mismatch")
    try:
        quality = TimestampQuality(document["timestamp_quality"])
    except (TypeError, ValueError) as exc:
        raise EyeOnArmCaptureBundleError("Invalid frame timestamp_quality") from exc
    source_sequence = document["source_sequence"]
    source_timestamp = document["source_timestamp_ns"]
    source_clock = document["source_clock"]
    freshness = document["freshness_token"]
    return (
        FramePacket(
            capture_id=_text(document["capture_id"], "capture_id"),
            jpeg_bytes=jpeg,
            width_px=_integer(document["width_px"], "width_px", minimum=1),
            height_px=_integer(document["height_px"], "height_px", minimum=1),
            source_sequence=(
                None if source_sequence is None else _integer(source_sequence, "source_sequence")
            ),
            source_timestamp_ns=(
                None
                if source_timestamp is None
                else _integer(source_timestamp, "source_timestamp_ns")
            ),
            source_clock=(None if source_clock is None else _text(source_clock, "source_clock")),
            host_request_ns=_integer(document["host_request_ns"], "host_request_ns"),
            host_first_byte_ns=_integer(document["host_first_byte_ns"], "host_first_byte_ns"),
            host_complete_ns=_integer(document["host_complete_ns"], "host_complete_ns"),
            settings_hash=_digest(document["settings_hash"], "settings_hash"),
            timestamp_quality=quality,
            freshness_token=(None if freshness is None else _text(freshness, "freshness_token")),
            freshness_basis=_text(document["freshness_basis"], "freshness_basis"),
        ),
        _identifier(document["host_clock_id"], "host_clock_id"),
    )


def _detection_from_dict(value: object) -> NormalizedDetectionEvidence:
    document = _mapping(value, "detection")
    _exact(
        document,
        {
            "detector_version",
            "input_image_sha256",
            "camera_intrinsics_sha256",
            "tag_map_sha256",
            "normalized_json_sha256",
            "normalized_json_base64",
        },
        "detection",
    )
    return NormalizedDetectionEvidence(
        detector_version=_text(document["detector_version"], "detector_version"),
        input_image_sha256=_digest(document["input_image_sha256"], "input_image_sha256"),
        camera_intrinsics_sha256=_digest(
            document["camera_intrinsics_sha256"], "camera_intrinsics_sha256"
        ),
        tag_map_sha256=_digest(document["tag_map_sha256"], "tag_map_sha256"),
        normalized_json_sha256=_digest(
            document["normalized_json_sha256"], "normalized_json_sha256"
        ),
        normalized_json_bytes=_decode_blob(
            document["normalized_json_base64"],
            "normalized_json_base64",
            MAX_DETECTION_BYTES,
        ),
    )


def _sample_from_dict(value: object) -> CaptureBundleSample:
    document = _mapping(value, "bundle sample")
    _exact(
        document,
        {
            "sample_id",
            "frame",
            "exposure_interval",
            "pre_feedback",
            "post_feedback",
            "representative_phase",
            "detection",
        },
        "bundle sample",
    )
    frame, host_clock = _frame_from_dict(document["frame"])
    exposure = _mapping(document["exposure_interval"], "exposure_interval")
    _exact(
        exposure,
        {"start_ns", "end_ns", "clock_id", "clock_correlation_sha256", "qualification"},
        "exposure_interval",
    )
    if exposure["qualification"] != "RECORDER_CLAIM_NOT_CONTENT_VERIFIED":
        raise EyeOnArmCaptureBundleError("Unsupported exposure qualification")
    return CaptureBundleSample(
        sample_id=_identifier(document["sample_id"], "sample_id"),
        frame=frame,
        frame_host_clock_id=host_clock,
        exposure_start_ns=_integer(exposure["start_ns"], "exposure start_ns"),
        exposure_end_ns=_integer(exposure["end_ns"], "exposure end_ns"),
        exposure_clock_id=_identifier(exposure["clock_id"], "exposure clock_id"),
        clock_correlation_sha256=_digest(
            exposure["clock_correlation_sha256"], "clock_correlation_sha256"
        ),
        pre_feedback=_wire_from_dict(document["pre_feedback"]),
        post_feedback=_wire_from_dict(document["post_feedback"]),
        representative_phase=_text(document["representative_phase"], "representative_phase"),
        detection=_detection_from_dict(document["detection"]),
    )


def eye_on_arm_capture_bundle_from_dict(
    value: Mapping[str, Any],
) -> EyeOnArmCaptureBundle:
    document = _mapping(value, "capture bundle")
    _exact(
        document,
        {
            "schema",
            "bundle_id",
            "dataset_id",
            "dataset_sha256",
            "evidence_id",
            "evidence_sha256",
            "physical_release_effect",
            "parser_id",
            "samples",
            "authority",
        },
        "capture bundle",
    )
    if document["parser_id"] != PARSER_ID:
        raise EyeOnArmCaptureBundleError("Capture bundle parser id is not supported")
    authority = _mapping(document["authority"], "authority")
    expected_authority = {
        "physical_timing_qualified": False,
        "artifact_created": False,
        "artifact_installed": False,
        "motion_authorized": False,
        "contact_authorized": False,
    }
    if dict(authority) != expected_authority:
        raise EyeOnArmCaptureBundleError("Capture bundle authority must remain all false")
    raw_samples = document["samples"]
    if not isinstance(raw_samples, (list, tuple)):
        raise EyeOnArmCaptureBundleError("samples must be a JSON array")
    if len(raw_samples) > MAX_CAPTURE_SAMPLES:
        raise EyeOnArmCaptureBundleError("Capture bundle exceeds sample limit")
    return EyeOnArmCaptureBundle(
        schema=_text(document["schema"], "schema"),
        bundle_id=_identifier(document["bundle_id"], "bundle_id"),
        dataset_id=_identifier(document["dataset_id"], "dataset_id"),
        dataset_sha256=_digest(document["dataset_sha256"], "dataset_sha256"),
        evidence_id=_identifier(document["evidence_id"], "evidence_id"),
        evidence_sha256=_digest(document["evidence_sha256"], "evidence_sha256"),
        physical_release_effect=_text(
            document["physical_release_effect"], "physical_release_effect"
        ),
        samples=tuple(_sample_from_dict(item) for item in raw_samples),
    )


def load_eye_on_arm_capture_bundle(
    path: str | Path,
    *,
    expected_file_sha256: str | None = None,
) -> EyeOnArmCaptureBundle:
    """Load a strict bundle through a bounded read and optional exact-file pin."""

    source = Path(path)
    try:
        if source.stat().st_size > MAX_BUNDLE_FILE_BYTES:
            raise EyeOnArmCaptureBundleError("Capture bundle file exceeds size limit")
        with source.open("rb") as stream:
            payload = stream.read(MAX_BUNDLE_FILE_BYTES + 1)
    except OSError as exc:
        raise EyeOnArmCaptureBundleError(f"Could not read capture bundle: {exc}") from exc
    if len(payload) > MAX_BUNDLE_FILE_BYTES:
        raise EyeOnArmCaptureBundleError("Capture bundle file exceeds size limit")
    if expected_file_sha256 is not None:
        expected = _digest(expected_file_sha256, "expected_file_sha256")
        if hashlib.sha256(payload).hexdigest() != expected:
            raise EyeOnArmCaptureBundleError("Capture bundle file hash mismatch")
    document = _strict_json_bytes(payload, "capture bundle")
    return eye_on_arm_capture_bundle_from_dict(document)

"""Immutable, dependency-free AprilTag detector observations.

The records in this module are the boundary between an image detector and the
rest of RoCell.  They deliberately contain no OpenCV objects and no detector
implementation code.  A :class:`FrameCaptureBinding` preserves the identity,
content hash, capture settings, and timing claims of the exact
:class:`~rocell.vision.camera.FramePacket` on which a detector operated.

These records are evidence, not authority.  Constructing or deserializing one
cannot authorize motion, release a physical gate, or generate a command.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import re
from typing import Any, Mapping, Sequence

from .camera import FramePacket, TimestampQuality


DETECTION_BATCH_SCHEMA = "rocell.apriltag_detection_batch.v1"
CORNER_ORDER = "apriltag_canonical_0_1_2_3"
MAX_DETECTIONS = 256
MAX_TAG_ID = 2**31 - 1
MAX_HAMMING_DISTANCE = 64
MAX_PIXEL_COORDINATE = 10_000_000.0
MAX_DECISION_MARGIN = 1_000_000_000.0
MAX_TIMESTAMP_NS = 2**63 - 1

_IDENTIFIER = re.compile(r"^[A-Za-z0-9_.:/+-]+$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class VisionRecordError(ValueError):
    """A raw vision record is malformed, ambiguous, or internally incoherent."""


def _exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        raise VisionRecordError(
            f"{label} fields differ; missing={sorted(expected - actual)}, "
            f"extra={sorted(actual - expected)}"
        )


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise VisionRecordError(f"{label} must be an object with string keys")
    return value


def _sequence(value: object, label: str, *, length: int | None = None) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise VisionRecordError(f"{label} must be an array")
    result = tuple(value)
    if length is not None and len(result) != length:
        raise VisionRecordError(f"{label} must contain exactly {length} values")
    return result


def _identifier(value: object, label: str, *, maximum: int = 128) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > maximum
        or not _IDENTIFIER.fullmatch(value)
    ):
        raise VisionRecordError(
            f"{label} must be 1..{maximum} characters matching {_IDENTIFIER.pattern}"
        )
    return value


def _bounded_text(value: object, label: str, *, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise VisionRecordError(f"{label} must be non-empty text no longer than {maximum}")
    if value != value.strip():
        raise VisionRecordError(f"{label} cannot contain surrounding whitespace")
    result = value
    if any(ord(character) < 32 or ord(character) == 127 for character in result):
        raise VisionRecordError(f"{label} contains a control character")
    return result


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise VisionRecordError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _integer(
    value: object,
    label: str,
    *,
    minimum: int = 0,
    maximum: int = MAX_TIMESTAMP_NS,
) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < minimum
        or value > maximum
    ):
        raise VisionRecordError(
            f"{label} must be an integer in [{minimum}, {maximum}]"
        )
    return value


def _finite(
    value: object,
    label: str,
    *,
    minimum: float,
    maximum: float,
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise VisionRecordError(f"{label} must be a real number")
    result = float(value)
    if not math.isfinite(result) or result < minimum or result > maximum:
        raise VisionRecordError(
            f"{label} must be finite and in [{minimum}, {maximum}]"
        )
    return result


def _canonical_bytes(value: Mapping[str, Any]) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise VisionRecordError(f"Vision record is not canonical JSON: {exc}") from exc


def _canonical_hash(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _zero_authority() -> dict[str, Any]:
    """Return a fresh JSON object so callers cannot mutate a shared constant."""

    return {
        "physical_authority": "NONE",
        "physical_commands_generated": 0,
        "can_authorize_motion": False,
        "can_release_physical_gates": False,
    }


def _validate_zero_authority(value: object, label: str = "authority") -> None:
    document = _mapping(value, label)
    if dict(document) != _zero_authority():
        raise VisionRecordError(f"{label} must declare exactly zero physical authority")


@dataclass(frozen=True, slots=True)
class FrameCaptureBinding:
    """Content and clock binding for one exact encoded frame.

    JPEG bytes intentionally remain in the owning :class:`FramePacket` or an
    evidence blob store.  ``jpeg_sha256`` binds this observation to those bytes
    without duplicating a potentially multi-megabyte image in every record.
    """

    capture_id: str
    jpeg_sha256: str
    width_px: int
    height_px: int
    source_sequence: int | None
    source_timestamp_ns: int | None
    source_clock: str | None
    host_request_ns: int
    host_first_byte_ns: int
    host_complete_ns: int
    host_clock: str
    settings_sha256: str
    timestamp_quality: TimestampQuality
    freshness_token: str | None
    freshness_basis: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "capture_id", _bounded_text(self.capture_id, "capture_id", maximum=256))
        _digest(self.jpeg_sha256, "jpeg_sha256")
        _integer(self.width_px, "width_px", minimum=1, maximum=100_000)
        _integer(self.height_px, "height_px", minimum=1, maximum=100_000)
        if self.source_sequence is not None:
            _integer(self.source_sequence, "source_sequence")
        if self.source_timestamp_ns is None:
            if self.source_clock is not None:
                raise VisionRecordError(
                    "source_clock cannot be present without source_timestamp_ns"
                )
        else:
            _integer(self.source_timestamp_ns, "source_timestamp_ns")
            object.__setattr__(
                self,
                "source_clock",
                _identifier(self.source_clock, "source_clock"),
            )
        for label, value in (
            ("host_request_ns", self.host_request_ns),
            ("host_first_byte_ns", self.host_first_byte_ns),
            ("host_complete_ns", self.host_complete_ns),
        ):
            _integer(value, label)
        if not self.host_request_ns <= self.host_first_byte_ns <= self.host_complete_ns:
            raise VisionRecordError("host capture timestamps are out of order")
        object.__setattr__(self, "host_clock", _identifier(self.host_clock, "host_clock"))
        _digest(self.settings_sha256, "settings_sha256")
        if not isinstance(self.timestamp_quality, TimestampQuality):
            try:
                object.__setattr__(self, "timestamp_quality", TimestampQuality(self.timestamp_quality))
            except (TypeError, ValueError) as exc:
                raise VisionRecordError("timestamp_quality is invalid") from exc
        if self.freshness_token is not None:
            object.__setattr__(
                self,
                "freshness_token",
                _bounded_text(self.freshness_token, "freshness_token", maximum=1024),
            )
        object.__setattr__(
            self,
            "freshness_basis",
            _bounded_text(self.freshness_basis, "freshness_basis", maximum=128),
        )

    @classmethod
    def from_frame_packet(cls, frame: FramePacket, *, host_clock: str) -> "FrameCaptureBinding":
        """Freeze the complete identity/timing projection of ``frame``."""

        if not isinstance(frame, FramePacket):
            raise TypeError("frame must be a FramePacket")
        return cls(
            capture_id=frame.capture_id,
            jpeg_sha256=frame.sha256,
            width_px=frame.width_px,
            height_px=frame.height_px,
            source_sequence=frame.source_sequence,
            source_timestamp_ns=frame.source_timestamp_ns,
            source_clock=frame.source_clock,
            host_request_ns=frame.host_request_ns,
            host_first_byte_ns=frame.host_first_byte_ns,
            host_complete_ns=frame.host_complete_ns,
            host_clock=host_clock,
            settings_sha256=frame.settings_hash,
            timestamp_quality=frame.timestamp_quality,
            freshness_token=frame.freshness_token,
            freshness_basis=frame.freshness_basis,
        )

    def assert_matches(self, frame: FramePacket, *, host_clock: str) -> None:
        """Reject a frame substitution, metadata edit, or clock substitution."""

        if self != FrameCaptureBinding.from_frame_packet(frame, host_clock=host_clock):
            raise VisionRecordError(
                f"FramePacket does not match capture binding {self.capture_id!r}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "capture_id": self.capture_id,
            "jpeg_sha256": self.jpeg_sha256,
            "resolution_px": [self.width_px, self.height_px],
            "source_sequence": self.source_sequence,
            "source_timing": {
                "timestamp_ns": self.source_timestamp_ns,
                "clock": self.source_clock,
            },
            "host_timing": {
                "request_ns": self.host_request_ns,
                "first_byte_ns": self.host_first_byte_ns,
                "complete_ns": self.host_complete_ns,
                "clock": self.host_clock,
            },
            "settings_sha256": self.settings_sha256,
            "timestamp_quality": self.timestamp_quality.value,
            "freshness": {
                "token": self.freshness_token,
                "basis": self.freshness_basis,
            },
        }


@dataclass(frozen=True, slots=True)
class DetectorIdentity:
    """Pinned detector name, version, configuration, and implementation."""

    detector_id: str
    version: str
    configuration_sha256: str
    implementation_sha256: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "detector_id", _identifier(self.detector_id, "detector_id"))
        object.__setattr__(self, "version", _bounded_text(self.version, "detector version", maximum=128))
        _digest(self.configuration_sha256, "detector configuration_sha256")
        _digest(self.implementation_sha256, "detector implementation_sha256")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.detector_id,
            "version": self.version,
            "configuration_sha256": self.configuration_sha256,
            "implementation_sha256": self.implementation_sha256,
        }


@dataclass(frozen=True, slots=True, order=True)
class TagReference:
    """Globally unique AprilTag family/id reference within a tag map."""

    family: str
    tag_id: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "family", _identifier(self.family, "tag family"))
        _integer(self.tag_id, "tag_id", maximum=MAX_TAG_ID)

    def to_dict(self) -> dict[str, Any]:
        return {"family": self.family, "id": self.tag_id}


@dataclass(frozen=True, slots=True)
class PixelCorner:
    """One finite subpixel coordinate in detector-defined image coordinates."""

    x_px: float
    y_px: float

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "x_px",
            _finite(
                self.x_px,
                "corner x_px",
                minimum=0.0,
                maximum=MAX_PIXEL_COORDINATE,
            ),
        )
        object.__setattr__(
            self,
            "y_px",
            _finite(
                self.y_px,
                "corner y_px",
                minimum=0.0,
                maximum=MAX_PIXEL_COORDINATE,
            ),
        )

    def to_dict(self) -> list[float]:
        return [self.x_px, self.y_px]


def _validate_ordered_quadrilateral(corners: tuple[PixelCorner, ...]) -> None:
    if len(corners) != 4:
        raise VisionRecordError("AprilTag corners must contain exactly four coordinates")
    if len({(corner.x_px, corner.y_px) for corner in corners}) != 4:
        raise VisionRecordError("AprilTag corners must be four distinct coordinates")

    # Consecutive edges of a convex quadrilateral have one consistent turn
    # sign.  This rejects crossed and arbitrarily shuffled corner lists while
    # accepting either clockwise or counter-clockwise detector conventions.
    turns: list[float] = []
    for index in range(4):
        first = corners[index]
        second = corners[(index + 1) % 4]
        third = corners[(index + 2) % 4]
        turns.append(
            (second.x_px - first.x_px) * (third.y_px - second.y_px)
            - (second.y_px - first.y_px) * (third.x_px - second.x_px)
        )
    tolerance = 1e-9
    if any(abs(turn) <= tolerance for turn in turns) or not (
        all(turn > 0.0 for turn in turns) or all(turn < 0.0 for turn in turns)
    ):
        raise VisionRecordError(
            "AprilTag corners must be a non-degenerate convex ordered quadrilateral"
        )


@dataclass(frozen=True, slots=True)
class AprilTagDetection:
    """One accepted or explicitly rejected AprilTag detector candidate."""

    tag: TagReference
    corners_px: tuple[PixelCorner, PixelCorner, PixelCorner, PixelCorner]
    decision_margin: float
    hamming: int
    rejection_reason: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.tag, TagReference):
            raise TypeError("tag must be a TagReference")
        corners = tuple(self.corners_px)
        if any(not isinstance(corner, PixelCorner) for corner in corners):
            raise TypeError("corners_px must contain PixelCorner values")
        _validate_ordered_quadrilateral(corners)
        object.__setattr__(self, "corners_px", corners)
        object.__setattr__(
            self,
            "decision_margin",
            _finite(
                self.decision_margin,
                "decision_margin",
                minimum=0.0,
                maximum=MAX_DECISION_MARGIN,
            ),
        )
        _integer(self.hamming, "hamming", maximum=MAX_HAMMING_DISTANCE)
        if self.rejection_reason is not None:
            object.__setattr__(
                self,
                "rejection_reason",
                _bounded_text(
                    self.rejection_reason,
                    "rejection_reason",
                    maximum=256,
                ),
            )

    @property
    def detector_accepted(self) -> bool:
        return self.rejection_reason is None

    def to_dict(self) -> dict[str, Any]:
        return {
            "tag": self.tag.to_dict(),
            "corner_order": CORNER_ORDER,
            "corners_px": [corner.to_dict() for corner in self.corners_px],
            "decision_margin": self.decision_margin,
            "hamming": self.hamming,
            "detector_accepted": self.detector_accepted,
            "rejection_reason": self.rejection_reason,
        }


@dataclass(frozen=True, slots=True)
class AprilTagDetectionBatch:
    """Canonical detector output for one exact captured frame.

    Tags are stored in deterministic ``(family, id)`` order.  Tag ids must be
    globally unique even if a detector reports multiple families; this matches
    the unambiguous id namespace required by a physical RoCell tag map.
    """

    frame: FrameCaptureBinding
    detector: DetectorIdentity
    detections: tuple[AprilTagDetection, ...]
    schema: str = DETECTION_BATCH_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != DETECTION_BATCH_SCHEMA:
            raise VisionRecordError(f"Unsupported detection schema {self.schema!r}")
        if not isinstance(self.frame, FrameCaptureBinding):
            raise TypeError("frame must be a FrameCaptureBinding")
        if not isinstance(self.detector, DetectorIdentity):
            raise TypeError("detector must be a DetectorIdentity")
        detections = tuple(self.detections)
        if len(detections) > MAX_DETECTIONS:
            raise VisionRecordError(
                f"Detection batch exceeds the {MAX_DETECTIONS}-candidate limit"
            )
        if any(not isinstance(detection, AprilTagDetection) for detection in detections):
            raise TypeError("detections must contain AprilTagDetection values")
        tag_ids = tuple(detection.tag.tag_id for detection in detections)
        if len(set(tag_ids)) != len(tag_ids):
            raise VisionRecordError("Detection batch contains a duplicate tag id")
        for detection in detections:
            for corner in detection.corners_px:
                if corner.x_px >= self.frame.width_px or corner.y_px >= self.frame.height_px:
                    raise VisionRecordError(
                        f"Tag {detection.tag.tag_id} corner lies outside the captured frame"
                    )
        object.__setattr__(
            self,
            "detections",
            tuple(sorted(detections, key=lambda detection: detection.tag)),
        )

    @property
    def accepted_tags(self) -> tuple[TagReference, ...]:
        return tuple(
            detection.tag for detection in self.detections if detection.detector_accepted
        )

    @property
    def rejected_tags(self) -> tuple[TagReference, ...]:
        return tuple(
            detection.tag for detection in self.detections if not detection.detector_accepted
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "frame": self.frame.to_dict(),
            "detector": self.detector.to_dict(),
            "detections": [detection.to_dict() for detection in self.detections],
            "authority": _zero_authority(),
        }

    @property
    def content_hash(self) -> str:
        return _canonical_hash(self.to_dict())


def frame_capture_binding_from_dict(value: object) -> FrameCaptureBinding:
    document = _mapping(value, "frame")
    _exact_keys(
        document,
        {
            "capture_id",
            "jpeg_sha256",
            "resolution_px",
            "source_sequence",
            "source_timing",
            "host_timing",
            "settings_sha256",
            "timestamp_quality",
            "freshness",
        },
        "frame",
    )
    resolution = _sequence(document["resolution_px"], "frame.resolution_px", length=2)
    source = _mapping(document["source_timing"], "frame.source_timing")
    _exact_keys(source, {"timestamp_ns", "clock"}, "frame.source_timing")
    host = _mapping(document["host_timing"], "frame.host_timing")
    _exact_keys(
        host,
        {"request_ns", "first_byte_ns", "complete_ns", "clock"},
        "frame.host_timing",
    )
    freshness = _mapping(document["freshness"], "frame.freshness")
    _exact_keys(freshness, {"token", "basis"}, "frame.freshness")
    try:
        timestamp_quality = TimestampQuality(document["timestamp_quality"])
    except (TypeError, ValueError) as exc:
        raise VisionRecordError("frame.timestamp_quality is invalid") from exc
    return FrameCaptureBinding(
        capture_id=document["capture_id"],  # type: ignore[arg-type]
        jpeg_sha256=document["jpeg_sha256"],  # type: ignore[arg-type]
        width_px=resolution[0],  # type: ignore[arg-type]
        height_px=resolution[1],  # type: ignore[arg-type]
        source_sequence=document["source_sequence"],  # type: ignore[arg-type]
        source_timestamp_ns=source["timestamp_ns"],  # type: ignore[arg-type]
        source_clock=source["clock"],  # type: ignore[arg-type]
        host_request_ns=host["request_ns"],  # type: ignore[arg-type]
        host_first_byte_ns=host["first_byte_ns"],  # type: ignore[arg-type]
        host_complete_ns=host["complete_ns"],  # type: ignore[arg-type]
        host_clock=host["clock"],  # type: ignore[arg-type]
        settings_sha256=document["settings_sha256"],  # type: ignore[arg-type]
        timestamp_quality=timestamp_quality,
        freshness_token=freshness["token"],  # type: ignore[arg-type]
        freshness_basis=freshness["basis"],  # type: ignore[arg-type]
    )


def detector_identity_from_dict(value: object) -> DetectorIdentity:
    document = _mapping(value, "detector")
    _exact_keys(
        document,
        {"id", "version", "configuration_sha256", "implementation_sha256"},
        "detector",
    )
    return DetectorIdentity(
        detector_id=document["id"],  # type: ignore[arg-type]
        version=document["version"],  # type: ignore[arg-type]
        configuration_sha256=document["configuration_sha256"],  # type: ignore[arg-type]
        implementation_sha256=document["implementation_sha256"],  # type: ignore[arg-type]
    )


def tag_reference_from_dict(value: object, *, label: str = "tag") -> TagReference:
    document = _mapping(value, label)
    _exact_keys(document, {"family", "id"}, label)
    return TagReference(
        family=document["family"],  # type: ignore[arg-type]
        tag_id=document["id"],  # type: ignore[arg-type]
    )


def april_tag_detection_from_dict(value: object) -> AprilTagDetection:
    document = _mapping(value, "detection")
    _exact_keys(
        document,
        {
            "tag",
            "corner_order",
            "corners_px",
            "decision_margin",
            "hamming",
            "detector_accepted",
            "rejection_reason",
        },
        "detection",
    )
    if document["corner_order"] != CORNER_ORDER:
        raise VisionRecordError(f"Unsupported AprilTag corner order {document['corner_order']!r}")
    corner_values = _sequence(document["corners_px"], "detection.corners_px", length=4)
    corners: list[PixelCorner] = []
    for index, value_at_index in enumerate(corner_values):
        coordinate = _sequence(
            value_at_index,
            f"detection.corners_px[{index}]",
            length=2,
        )
        corners.append(PixelCorner(coordinate[0], coordinate[1]))  # type: ignore[arg-type]
    rejection = document["rejection_reason"]
    expected_accepted = rejection is None
    if document["detector_accepted"] is not expected_accepted:
        raise VisionRecordError(
            "detection.detector_accepted disagrees with rejection_reason"
        )
    return AprilTagDetection(
        tag=tag_reference_from_dict(document["tag"]),
        corners_px=(corners[0], corners[1], corners[2], corners[3]),
        decision_margin=document["decision_margin"],  # type: ignore[arg-type]
        hamming=document["hamming"],  # type: ignore[arg-type]
        rejection_reason=rejection,  # type: ignore[arg-type]
    )


def april_tag_detection_batch_from_dict(value: object) -> AprilTagDetectionBatch:
    document = _mapping(value, "detection batch")
    _exact_keys(
        document,
        {"schema", "frame", "detector", "detections", "authority"},
        "detection batch",
    )
    _validate_zero_authority(document["authority"])
    detections = _sequence(document["detections"], "detection batch.detections")
    batch = AprilTagDetectionBatch(
        schema=document["schema"],  # type: ignore[arg-type]
        frame=frame_capture_binding_from_dict(document["frame"]),
        detector=detector_identity_from_dict(document["detector"]),
        detections=tuple(april_tag_detection_from_dict(item) for item in detections),
    )
    # Canonical files must already use the stable tag order.  Silently sorting
    # deserialized evidence would conceal a wire-level mutation.
    if batch.to_dict() != dict(document):
        raise VisionRecordError("Detection batch is not in canonical normalized form")
    return batch


__all__ = [
    "AprilTagDetection",
    "AprilTagDetectionBatch",
    "CORNER_ORDER",
    "DETECTION_BATCH_SCHEMA",
    "DetectorIdentity",
    "FrameCaptureBinding",
    "MAX_DETECTIONS",
    "PixelCorner",
    "TagReference",
    "VisionRecordError",
    "april_tag_detection_batch_from_dict",
    "april_tag_detection_from_dict",
    "detector_identity_from_dict",
    "frame_capture_binding_from_dict",
    "tag_reference_from_dict",
]

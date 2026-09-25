"""Strict offline datasets for the RoCell eye-on-arm calibration equation.

The selected camera is rigidly carried by frame ``E`` on the moving upper
arm.  Each settled capture records the two measured poses needed by the
robot-world/hand-eye equation::

    Wv_T_B = Wv_T_E(q_i) * E_T_C_arm * C_arm_T_B(i)

This module deliberately does not open a camera, read an arm, compute forward
kinematics, or grant physical authority.  It only validates and freezes
already-captured evidence so numerical solvers cannot silently mix frames,
clocks, joint records, or source revisions.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Sequence

from rocell.geometry.transforms import RigidTransform, Rotation3, Vec3


SCHEMA = "rocell.eye_on_arm_dataset.v1"
EQUATION = "Wv_T_B = Wv_T_E * E_T_C_arm * C_arm_T_B"
MAX_DATASET_BYTES = 4 * 1024 * 1024
JOINT_ORDER = (
    "base_link_to_link1",
    "link1_to_link2",
    "link2_to_link3",
    "link3_to_link4",
    "link4_to_link5",
    "link5_to_gripper_link",
)
REQUIRED_SOURCE_HASHES = frozenset(
    {
        "arm_frame_contract",
        "camera_manifest",
        "camera_intrinsics",
        "carrier_registration",
        "carrier_kinematic_model",
        "measured_tag_map",
        "robot_reference",
    }
)

_IDENTIFIER = re.compile(r"^[A-Za-z0-9_.-]+$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_DATASET_KINDS = frozenset({"SYNTHETIC", "OFFLINE_CAPTURE"})
_TIMESTAMP_BASES = frozenset({"synthetic_exact", "device_exposure"})
_CARRIER_POSE_SOURCES = frozenset({"synthetic_truth", "offline_fk"})
# This v1 schema stores C_arm_T_B directly. ChArUco normally observes a
# separate fixture frame and therefore requires an explicit B_T_F contract
# before it can be represented honestly.
_TARGET_DETECTORS = frozenset({"synthetic_truth", "apriltag_bundle"})


class EyeOnArmDatasetError(ValueError):
    """An offline hand-eye dataset is malformed or internally incoherent."""


def _exact_keys(value: Mapping[str, Any], expected: set[str], name: str) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise EyeOnArmDatasetError(
            f"{name} fields differ; missing={missing}, extra={extra}"
        )


def _mapping(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise EyeOnArmDatasetError(f"{name} must be an object")
    if any(not isinstance(key, str) for key in value):
        raise EyeOnArmDatasetError(f"{name} keys must be strings")
    return value


def _sequence(value: object, length: int, name: str) -> tuple[Any, ...]:
    if not isinstance(value, (list, tuple)) or len(value) != length:
        raise EyeOnArmDatasetError(f"{name} must contain exactly {length} values")
    return tuple(value)


def _identifier(value: object, name: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise EyeOnArmDatasetError(f"{name} must match {_IDENTIFIER.pattern}")
    return value


def _digest(value: object, name: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise EyeOnArmDatasetError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _string(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EyeOnArmDatasetError(f"{name} must be a non-empty string")
    return value.strip()


def _integer(value: object, name: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise EyeOnArmDatasetError(f"{name} must be an integer >= {minimum}")
    return value


def _finite(value: object, name: str, *, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EyeOnArmDatasetError(f"{name} must be a real number")
    result = float(value)
    if not math.isfinite(result):
        raise EyeOnArmDatasetError(f"{name} must be finite")
    if minimum is not None and result < minimum:
        raise EyeOnArmDatasetError(f"{name} must be >= {minimum}")
    return result


def _transform(value: object, name: str) -> RigidTransform:
    document = _mapping(value, name)
    _exact_keys(
        document,
        {"to_frame", "from_frame", "rotation_row_major", "translation_mm"},
        name,
    )
    try:
        rotation = Rotation3(
            tuple(
                _finite(item, f"{name}.rotation_row_major")
                for item in _sequence(
                    document["rotation_row_major"], 9, f"{name}.rotation_row_major"
                )
            )
        )
        translation = Vec3.from_iterable(
            _finite(item, f"{name}.translation_mm")
            for item in _sequence(document["translation_mm"], 3, f"{name}.translation_mm")
        )
        return RigidTransform(
            parent_frame=_string(document["to_frame"], f"{name}.to_frame"),
            child_frame=_string(document["from_frame"], f"{name}.from_frame"),
            rotation=rotation,
            translation_mm=translation,
        )
    except (TypeError, ValueError) as exc:
        if isinstance(exc, EyeOnArmDatasetError):
            raise
        raise EyeOnArmDatasetError(f"{name} is not a rigid transform: {exc}") from exc


def _transform_dict(value: RigidTransform) -> dict[str, Any]:
    return {
        "to_frame": value.parent_frame,
        "from_frame": value.child_frame,
        "rotation_row_major": list(value.rotation.matrix),
        "translation_mm": [
            value.translation_mm.x,
            value.translation_mm.y,
            value.translation_mm.z,
        ],
    }


@dataclass(frozen=True, slots=True)
class EyeOnArmCameraBinding:
    """Exact selected camera architecture and locked capture mode."""

    manufacturer: str
    model: str
    sku: str
    interface: str
    architecture: str
    carrier_frame: str
    optical_frame: str
    width_px: int
    height_px: int
    pixel_format: str
    fps: float

    def __post_init__(self) -> None:
        if (
            self.manufacturer != "Waveshare"
            or self.model != "IMX335 5MP USB Camera (B)"
            or self.sku != "26719"
            or self.interface != "USB 2.0"
        ):
            raise EyeOnArmDatasetError(
                "Dataset camera must be the selected Waveshare IMX335-B USB candidate"
            )
        if self.architecture != "eye_on_moving_upper_arm":
            raise EyeOnArmDatasetError("Dataset must use the moving upper-arm architecture")
        if self.carrier_frame != "E" or self.optical_frame != "C_arm":
            raise EyeOnArmDatasetError("Camera frames must remain E and C_arm")
        _integer(self.width_px, "camera.width_px", minimum=1)
        _integer(self.height_px, "camera.height_px", minimum=1)
        _string(self.pixel_format, "camera.pixel_format")
        _finite(self.fps, "camera.fps", minimum=1e-12)

    def to_dict(self) -> dict[str, Any]:
        return {
            "manufacturer": self.manufacturer,
            "model": self.model,
            "sku": self.sku,
            "interface": self.interface,
            "architecture": self.architecture,
            "carrier_frame": self.carrier_frame,
            "optical_frame": self.optical_frame,
            "capture_mode": {
                "width_px": self.width_px,
                "height_px": self.height_px,
                "pixel_format": self.pixel_format,
                "fps": self.fps,
            },
        }


@dataclass(frozen=True, slots=True)
class SynchronizationPolicy:
    """Clock and settled-capture constraints applied to every sample."""

    mode: str
    clock_id: str
    timestamp_basis: str
    max_pair_delta_ns: int
    minimum_settled_duration_ms: float

    def __post_init__(self) -> None:
        if self.mode != "settled_stop_and_look":
            raise EyeOnArmDatasetError("Only settled_stop_and_look capture is supported")
        _identifier(self.clock_id, "synchronization.clock_id")
        if self.timestamp_basis not in _TIMESTAMP_BASES:
            raise EyeOnArmDatasetError(
                f"timestamp_basis must be one of {sorted(_TIMESTAMP_BASES)}"
            )
        _integer(self.max_pair_delta_ns, "max_pair_delta_ns")
        _finite(
            self.minimum_settled_duration_ms,
            "minimum_settled_duration_ms",
            minimum=0.0,
        )

    @property
    def exposure_synchronized(self) -> bool:
        # Synthetic timestamps are exact for tests but are not physical evidence.
        return self.timestamp_basis == "device_exposure"

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "clock_id": self.clock_id,
            "timestamp_basis": self.timestamp_basis,
            "max_pair_delta_ns": self.max_pair_delta_ns,
            "minimum_settled_duration_ms": self.minimum_settled_duration_ms,
        }


@dataclass(frozen=True, slots=True)
class ImageRecord:
    sequence: int
    timestamp_ns: int
    clock_id: str
    source_sha256: str
    width_px: int
    height_px: int

    def __post_init__(self) -> None:
        _integer(self.sequence, "frame.sequence")
        _integer(self.timestamp_ns, "frame.timestamp_ns")
        _identifier(self.clock_id, "frame.clock_id")
        _digest(self.source_sha256, "frame.source_sha256")
        _integer(self.width_px, "frame.width_px", minimum=1)
        _integer(self.height_px, "frame.height_px", minimum=1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "timestamp_ns": self.timestamp_ns,
            "clock_id": self.clock_id,
            "source_sha256": self.source_sha256,
            "width_px": self.width_px,
            "height_px": self.height_px,
        }


@dataclass(frozen=True, slots=True)
class JointStateRecord:
    sequence: int
    timestamp_ns: int
    clock_id: str
    settled_duration_ms: float
    positions_rad: tuple[tuple[str, float], ...]

    def __post_init__(self) -> None:
        _integer(self.sequence, "joint_state.sequence")
        _integer(self.timestamp_ns, "joint_state.timestamp_ns")
        _identifier(self.clock_id, "joint_state.clock_id")
        _finite(self.settled_duration_ms, "joint_state.settled_duration_ms", minimum=0.0)
        positions = tuple(self.positions_rad)
        if tuple(name for name, _ in positions) != JOINT_ORDER:
            raise EyeOnArmDatasetError(
                "joint_state.positions_rad must use the exact RoArm-M3-Pro joint order"
            )
        frozen = tuple(
            (_identifier(name, "joint name"), _finite(value, f"joint {name}"))
            for name, value in positions
        )
        object.__setattr__(self, "positions_rad", frozen)

    @property
    def positions_by_name(self) -> Mapping[str, float]:
        return MappingProxyType(dict(self.positions_rad))

    def to_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "timestamp_ns": self.timestamp_ns,
            "clock_id": self.clock_id,
            "settled_duration_ms": self.settled_duration_ms,
            "positions_rad": [
                {"joint": name, "position_rad": value}
                for name, value in self.positions_rad
            ],
        }


@dataclass(frozen=True, slots=True)
class CarrierPoseRecord:
    joint_sequence: int
    source: str
    transform: RigidTransform

    def __post_init__(self) -> None:
        _integer(self.joint_sequence, "carrier_pose.joint_sequence")
        if self.source not in _CARRIER_POSE_SOURCES:
            raise EyeOnArmDatasetError(
                f"carrier pose source must be one of {sorted(_CARRIER_POSE_SOURCES)}"
            )
        if (
            self.transform.parent_frame != "Wv"
            or self.transform.child_frame != "E"
        ):
            raise EyeOnArmDatasetError("carrier pose must be Wv_T_E")

    def to_dict(self) -> dict[str, Any]:
        return {
            "joint_sequence": self.joint_sequence,
            "source": self.source,
            "Wv_T_E": _transform_dict(self.transform),
        }


@dataclass(frozen=True, slots=True)
class TargetPoseRecord:
    frame_sequence: int
    detector: str
    transform: RigidTransform
    observation_count: int
    reprojection_rms_px: float

    def __post_init__(self) -> None:
        _integer(self.frame_sequence, "target_pose.frame_sequence")
        if self.detector not in _TARGET_DETECTORS:
            raise EyeOnArmDatasetError(
                f"target detector must be one of {sorted(_TARGET_DETECTORS)}"
            )
        if (
            self.transform.parent_frame != "C_arm"
            or self.transform.child_frame != "B"
        ):
            raise EyeOnArmDatasetError("target pose must be C_arm_T_B")
        _integer(self.observation_count, "target_pose.observation_count", minimum=4)
        _finite(
            self.reprojection_rms_px,
            "target_pose.reprojection_rms_px",
            minimum=0.0,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "frame_sequence": self.frame_sequence,
            "detector": self.detector,
            "C_arm_T_B": _transform_dict(self.transform),
            "observation_count": self.observation_count,
            "reprojection_rms_px": self.reprojection_rms_px,
        }


@dataclass(frozen=True, slots=True)
class EyeOnArmSample:
    sample_id: str
    frame: ImageRecord
    joint_state: JointStateRecord
    carrier_pose: CarrierPoseRecord
    target_pose: TargetPoseRecord

    def __post_init__(self) -> None:
        _identifier(self.sample_id, "sample_id")
        if not isinstance(self.frame, ImageRecord):
            raise TypeError("frame must be an ImageRecord")
        if not isinstance(self.joint_state, JointStateRecord):
            raise TypeError("joint_state must be a JointStateRecord")
        if not isinstance(self.carrier_pose, CarrierPoseRecord):
            raise TypeError("carrier_pose must be a CarrierPoseRecord")
        if not isinstance(self.target_pose, TargetPoseRecord):
            raise TypeError("target_pose must be a TargetPoseRecord")
        if self.carrier_pose.joint_sequence != self.joint_state.sequence:
            raise EyeOnArmDatasetError("carrier pose references a different joint sequence")
        if self.target_pose.frame_sequence != self.frame.sequence:
            raise EyeOnArmDatasetError("target pose references a different frame sequence")

    def to_dict(self) -> dict[str, Any]:
        return {
            "sample_id": self.sample_id,
            "frame": self.frame.to_dict(),
            "joint_state": self.joint_state.to_dict(),
            "carrier_pose": self.carrier_pose.to_dict(),
            "target_pose": self.target_pose.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class EyeOnArmDataset:
    """Deeply immutable, content-addressed offline calibration evidence."""

    dataset_id: str
    dataset_kind: str
    camera: EyeOnArmCameraBinding
    synchronization: SynchronizationPolicy
    source_hashes: Mapping[str, str]
    samples: tuple[EyeOnArmSample, ...]
    held_out_sample_ids: tuple[str, ...]
    schema: str = SCHEMA
    physical_release_effect: str = "NONE"

    def __post_init__(self) -> None:
        if self.schema != SCHEMA:
            raise EyeOnArmDatasetError(f"Unsupported dataset schema {self.schema!r}")
        _identifier(self.dataset_id, "dataset_id")
        if self.dataset_kind not in _DATASET_KINDS:
            raise EyeOnArmDatasetError(
                f"dataset_kind must be one of {sorted(_DATASET_KINDS)}"
            )
        if self.physical_release_effect != "NONE":
            raise EyeOnArmDatasetError("Offline datasets cannot have physical release effect")
        if not isinstance(self.camera, EyeOnArmCameraBinding):
            raise TypeError("camera must be an EyeOnArmCameraBinding")
        if not isinstance(self.synchronization, SynchronizationPolicy):
            raise TypeError("synchronization must be a SynchronizationPolicy")

        hashes = {
            _identifier(key, "source hash id"): _digest(value, f"source hash {key}")
            for key, value in self.source_hashes.items()
        }
        missing_hashes = sorted(REQUIRED_SOURCE_HASHES - set(hashes))
        if missing_hashes:
            raise EyeOnArmDatasetError(
                f"Dataset is missing required source hashes: {missing_hashes}"
            )
        object.__setattr__(self, "source_hashes", MappingProxyType(dict(sorted(hashes.items()))))

        samples = tuple(self.samples)
        if len(samples) < 6:
            raise EyeOnArmDatasetError(
                "Dataset requires at least six poses (five training plus one held out)"
            )
        if any(not isinstance(sample, EyeOnArmSample) for sample in samples):
            raise TypeError("samples must contain only EyeOnArmSample values")
        object.__setattr__(self, "samples", samples)
        self._validate_sample_series()
        held_out = tuple(self.held_out_sample_ids)
        if not held_out or len(set(held_out)) != len(held_out):
            raise EyeOnArmDatasetError(
                "validation_split.held_out_sample_ids must be non-empty and unique"
            )
        known_ids = {sample.sample_id for sample in samples}
        unknown = sorted(set(held_out) - known_ids)
        if unknown:
            raise EyeOnArmDatasetError(f"Unknown held-out sample ids: {unknown}")
        if len(samples) - len(held_out) < 5:
            raise EyeOnArmDatasetError(
                "Dataset split requires at least five algorithm-training poses"
            )
        object.__setattr__(self, "held_out_sample_ids", held_out)
        self._validate_kind_evidence()

    def _validate_sample_series(self) -> None:
        sample_ids: set[str] = set()
        image_hashes: set[str] = set()
        previous_frame_time = -1
        previous_joint_time = -1
        for index, sample in enumerate(self.samples):
            if sample.sample_id in sample_ids:
                raise EyeOnArmDatasetError(f"Duplicate sample_id {sample.sample_id!r}")
            sample_ids.add(sample.sample_id)
            if sample.frame.source_sha256 in image_hashes:
                raise EyeOnArmDatasetError("Each captured frame must have a distinct source hash")
            image_hashes.add(sample.frame.source_sha256)
            if sample.frame.sequence != index or sample.joint_state.sequence != index:
                raise EyeOnArmDatasetError("Frame and joint sequences must be contiguous from zero")
            if (
                sample.frame.clock_id != self.synchronization.clock_id
                or sample.joint_state.clock_id != self.synchronization.clock_id
            ):
                raise EyeOnArmDatasetError("Every sample must use the declared synchronization clock")
            if (
                sample.frame.width_px != self.camera.width_px
                or sample.frame.height_px != self.camera.height_px
            ):
                raise EyeOnArmDatasetError("Frame size differs from the locked camera mode")
            delta_ns = abs(sample.frame.timestamp_ns - sample.joint_state.timestamp_ns)
            if delta_ns > self.synchronization.max_pair_delta_ns:
                raise EyeOnArmDatasetError(
                    f"Sample {sample.sample_id} frame/joint delta {delta_ns} ns exceeds policy"
                )
            if (
                sample.joint_state.settled_duration_ms
                < self.synchronization.minimum_settled_duration_ms
            ):
                raise EyeOnArmDatasetError(
                    f"Sample {sample.sample_id} was not settled for the required duration"
                )
            if sample.frame.timestamp_ns <= previous_frame_time:
                raise EyeOnArmDatasetError("Frame timestamps must be strictly increasing")
            if sample.joint_state.timestamp_ns <= previous_joint_time:
                raise EyeOnArmDatasetError("Joint timestamps must be strictly increasing")
            previous_frame_time = sample.frame.timestamp_ns
            previous_joint_time = sample.joint_state.timestamp_ns

    def _validate_kind_evidence(self) -> None:
        if self.dataset_kind == "SYNTHETIC":
            if self.synchronization.timestamp_basis != "synthetic_exact":
                raise EyeOnArmDatasetError(
                    "SYNTHETIC datasets require synthetic_exact timestamps"
                )
            if any(
                sample.carrier_pose.source != "synthetic_truth"
                or sample.target_pose.detector != "synthetic_truth"
                for sample in self.samples
            ):
                raise EyeOnArmDatasetError(
                    "SYNTHETIC datasets require synthetic_truth carrier and target evidence"
                )
            return
        if self.synchronization.timestamp_basis != "device_exposure":
            raise EyeOnArmDatasetError(
                "OFFLINE_CAPTURE datasets require device_exposure timestamps"
            )
        if any(
            sample.carrier_pose.source != "offline_fk"
            or sample.target_pose.detector != "apriltag_bundle"
            for sample in self.samples
        ):
            raise EyeOnArmDatasetError(
                "OFFLINE_CAPTURE datasets require offline_fk carrier poses and "
                "apriltag_bundle direct-board detections; synthetic evidence is forbidden"
            )

    @property
    def exposure_synchronized(self) -> bool:
        return (
            self.dataset_kind == "OFFLINE_CAPTURE"
            and self.synchronization.exposure_synchronized
        )

    @property
    def content_hash(self) -> str:
        encoded = json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def sample(self, sample_id: str) -> EyeOnArmSample:
        for sample in self.samples:
            if sample.sample_id == sample_id:
                return sample
        raise KeyError(f"Unknown eye-on-arm sample {sample_id!r}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "dataset_id": self.dataset_id,
            "dataset_kind": self.dataset_kind,
            "physical_release_effect": self.physical_release_effect,
            "frame_contract": {
                "robot_root": "Wv",
                "carrier": "E",
                "camera_optical": "C_arm",
                "static_target": "B",
                "equation": EQUATION,
            },
            "joint_contract": {
                "angle_unit": "rad",
                "joint_order": list(JOINT_ORDER),
            },
            "camera": self.camera.to_dict(),
            "synchronization": self.synchronization.to_dict(),
            "source_hashes": dict(self.source_hashes),
            "validation_split": {
                "held_out_sample_ids": list(self.held_out_sample_ids),
            },
            "samples": [sample.to_dict() for sample in self.samples],
        }


def _camera(value: object) -> EyeOnArmCameraBinding:
    document = _mapping(value, "camera")
    _exact_keys(
        document,
        {
            "manufacturer",
            "model",
            "sku",
            "interface",
            "architecture",
            "carrier_frame",
            "optical_frame",
            "capture_mode",
        },
        "camera",
    )
    mode = _mapping(document["capture_mode"], "camera.capture_mode")
    _exact_keys(mode, {"width_px", "height_px", "pixel_format", "fps"}, "camera.capture_mode")
    return EyeOnArmCameraBinding(
        manufacturer=_string(document["manufacturer"], "camera.manufacturer"),
        model=_string(document["model"], "camera.model"),
        sku=_string(document["sku"], "camera.sku"),
        interface=_string(document["interface"], "camera.interface"),
        architecture=_string(document["architecture"], "camera.architecture"),
        carrier_frame=_string(document["carrier_frame"], "camera.carrier_frame"),
        optical_frame=_string(document["optical_frame"], "camera.optical_frame"),
        width_px=_integer(mode["width_px"], "camera.width_px", minimum=1),
        height_px=_integer(mode["height_px"], "camera.height_px", minimum=1),
        pixel_format=_string(mode["pixel_format"], "camera.pixel_format"),
        fps=_finite(mode["fps"], "camera.fps", minimum=1e-12),
    )


def _synchronization(value: object) -> SynchronizationPolicy:
    document = _mapping(value, "synchronization")
    _exact_keys(
        document,
        {
            "mode",
            "clock_id",
            "timestamp_basis",
            "max_pair_delta_ns",
            "minimum_settled_duration_ms",
        },
        "synchronization",
    )
    return SynchronizationPolicy(
        mode=_string(document["mode"], "synchronization.mode"),
        clock_id=_identifier(document["clock_id"], "synchronization.clock_id"),
        timestamp_basis=_string(document["timestamp_basis"], "synchronization.timestamp_basis"),
        max_pair_delta_ns=_integer(document["max_pair_delta_ns"], "max_pair_delta_ns"),
        minimum_settled_duration_ms=_finite(
            document["minimum_settled_duration_ms"],
            "minimum_settled_duration_ms",
            minimum=0.0,
        ),
    )


def _joint_positions(value: object) -> tuple[tuple[str, float], ...]:
    if not isinstance(value, (list, tuple)):
        raise EyeOnArmDatasetError("joint_state.positions_rad must be an array")
    positions: list[tuple[str, float]] = []
    for index, raw in enumerate(value):
        document = _mapping(raw, f"joint_state.positions_rad[{index}]")
        _exact_keys(document, {"joint", "position_rad"}, f"joint position {index}")
        positions.append(
            (
                _identifier(document["joint"], f"joint position {index}.joint"),
                _finite(document["position_rad"], f"joint position {index}.position_rad"),
            )
        )
    return tuple(positions)


def _sample(value: object) -> EyeOnArmSample:
    document = _mapping(value, "sample")
    _exact_keys(
        document,
        {"sample_id", "frame", "joint_state", "carrier_pose", "target_pose"},
        "sample",
    )
    frame_doc = _mapping(document["frame"], "sample.frame")
    _exact_keys(
        frame_doc,
        {"sequence", "timestamp_ns", "clock_id", "source_sha256", "width_px", "height_px"},
        "sample.frame",
    )
    joint_doc = _mapping(document["joint_state"], "sample.joint_state")
    _exact_keys(
        joint_doc,
        {"sequence", "timestamp_ns", "clock_id", "settled_duration_ms", "positions_rad"},
        "sample.joint_state",
    )
    carrier_doc = _mapping(document["carrier_pose"], "sample.carrier_pose")
    _exact_keys(
        carrier_doc,
        {"joint_sequence", "source", "Wv_T_E"},
        "sample.carrier_pose",
    )
    target_doc = _mapping(document["target_pose"], "sample.target_pose")
    _exact_keys(
        target_doc,
        {
            "frame_sequence",
            "detector",
            "C_arm_T_B",
            "observation_count",
            "reprojection_rms_px",
        },
        "sample.target_pose",
    )
    return EyeOnArmSample(
        sample_id=_identifier(document["sample_id"], "sample.sample_id"),
        frame=ImageRecord(
            sequence=_integer(frame_doc["sequence"], "frame.sequence"),
            timestamp_ns=_integer(frame_doc["timestamp_ns"], "frame.timestamp_ns"),
            clock_id=_identifier(frame_doc["clock_id"], "frame.clock_id"),
            source_sha256=_digest(frame_doc["source_sha256"], "frame.source_sha256"),
            width_px=_integer(frame_doc["width_px"], "frame.width_px", minimum=1),
            height_px=_integer(frame_doc["height_px"], "frame.height_px", minimum=1),
        ),
        joint_state=JointStateRecord(
            sequence=_integer(joint_doc["sequence"], "joint_state.sequence"),
            timestamp_ns=_integer(joint_doc["timestamp_ns"], "joint_state.timestamp_ns"),
            clock_id=_identifier(joint_doc["clock_id"], "joint_state.clock_id"),
            settled_duration_ms=_finite(
                joint_doc["settled_duration_ms"],
                "joint_state.settled_duration_ms",
                minimum=0.0,
            ),
            positions_rad=_joint_positions(joint_doc["positions_rad"]),
        ),
        carrier_pose=CarrierPoseRecord(
            joint_sequence=_integer(
                carrier_doc["joint_sequence"], "carrier_pose.joint_sequence"
            ),
            source=_string(carrier_doc["source"], "carrier_pose.source"),
            transform=_transform(carrier_doc["Wv_T_E"], "carrier_pose.Wv_T_E"),
        ),
        target_pose=TargetPoseRecord(
            frame_sequence=_integer(
                target_doc["frame_sequence"], "target_pose.frame_sequence"
            ),
            detector=_string(target_doc["detector"], "target_pose.detector"),
            transform=_transform(target_doc["C_arm_T_B"], "target_pose.C_arm_T_B"),
            observation_count=_integer(
                target_doc["observation_count"],
                "target_pose.observation_count",
                minimum=4,
            ),
            reprojection_rms_px=_finite(
                target_doc["reprojection_rms_px"],
                "target_pose.reprojection_rms_px",
                minimum=0.0,
            ),
        ),
    )


def eye_on_arm_dataset_from_dict(document: Mapping[str, Any]) -> EyeOnArmDataset:
    """Parse a strict in-memory document without accepting unknown fields."""

    root = _mapping(document, "dataset")
    _exact_keys(
        root,
        {
            "schema",
            "dataset_id",
            "dataset_kind",
            "physical_release_effect",
            "frame_contract",
            "joint_contract",
            "camera",
            "synchronization",
            "source_hashes",
            "validation_split",
            "samples",
        },
        "dataset",
    )
    frame_contract = _mapping(root["frame_contract"], "frame_contract")
    expected_frame_contract = {
        "robot_root": "Wv",
        "carrier": "E",
        "camera_optical": "C_arm",
        "static_target": "B",
        "equation": EQUATION,
    }
    if dict(frame_contract) != expected_frame_contract:
        raise EyeOnArmDatasetError(
            "frame_contract must exactly preserve Wv, E, C_arm, B, and transform direction"
        )
    joint_contract = _mapping(root["joint_contract"], "joint_contract")
    _exact_keys(joint_contract, {"angle_unit", "joint_order"}, "joint_contract")
    if joint_contract["angle_unit"] != "rad" or tuple(
        _sequence(joint_contract["joint_order"], len(JOINT_ORDER), "joint_order")
    ) != JOINT_ORDER:
        raise EyeOnArmDatasetError("joint_contract differs from the RoArm-M3-Pro contract")
    hashes_doc = _mapping(root["source_hashes"], "source_hashes")
    split_doc = _mapping(root["validation_split"], "validation_split")
    _exact_keys(split_doc, {"held_out_sample_ids"}, "validation_split")
    held_out_doc = split_doc["held_out_sample_ids"]
    if not isinstance(held_out_doc, (list, tuple)):
        raise EyeOnArmDatasetError(
            "validation_split.held_out_sample_ids must be an array"
        )
    samples_doc = root["samples"]
    if not isinstance(samples_doc, (list, tuple)):
        raise EyeOnArmDatasetError("samples must be an array")
    return EyeOnArmDataset(
        schema=_string(root["schema"], "schema"),
        dataset_id=_identifier(root["dataset_id"], "dataset_id"),
        dataset_kind=_string(root["dataset_kind"], "dataset_kind"),
        physical_release_effect=_string(
            root["physical_release_effect"], "physical_release_effect"
        ),
        camera=_camera(root["camera"]),
        synchronization=_synchronization(root["synchronization"]),
        source_hashes={
            _identifier(key, "source hash id"): _digest(value, f"source hash {key}")
            for key, value in hashes_doc.items()
        },
        samples=tuple(_sample(item) for item in samples_doc),
        held_out_sample_ids=tuple(
            _identifier(item, "held-out sample id") for item in held_out_doc
        ),
    )


def _reject_duplicate_pairs(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise EyeOnArmDatasetError(f"Duplicate JSON field {key!r}")
        result[key] = value
    return result


def load_eye_on_arm_dataset(
    path: str | Path,
    *,
    expected_file_sha256: str | None = None,
    expected_source_hashes: Mapping[str, str] | None = None,
) -> EyeOnArmDataset:
    """Load one strict JSON dataset and optionally pin file/source identities."""

    source = Path(path)
    try:
        size = source.stat().st_size
        if size > MAX_DATASET_BYTES:
            raise EyeOnArmDatasetError(
                f"Eye-on-arm dataset exceeds {MAX_DATASET_BYTES} byte limit"
            )
        # Bound the actual read as well as stat so a file-growth race cannot
        # allocate an unbounded payload between the two operations.
        with source.open("rb") as stream:
            raw = stream.read(MAX_DATASET_BYTES + 1)
    except OSError as exc:
        raise EyeOnArmDatasetError(f"Could not read eye-on-arm dataset {source}: {exc}") from exc
    if len(raw) > MAX_DATASET_BYTES:
        raise EyeOnArmDatasetError(
            f"Eye-on-arm dataset exceeds {MAX_DATASET_BYTES} byte limit"
        )
    file_digest = hashlib.sha256(raw).hexdigest()
    if expected_file_sha256 is not None and file_digest != _digest(
        expected_file_sha256, "expected_file_sha256"
    ):
        raise EyeOnArmDatasetError("Eye-on-arm dataset file hash mismatch")
    try:
        document = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_pairs,
            parse_constant=lambda value: (_ for _ in ()).throw(
                EyeOnArmDatasetError(f"Nonfinite JSON constant {value!r}")
            ),
        )
    except (UnicodeError, json.JSONDecodeError, EyeOnArmDatasetError) as exc:
        raise EyeOnArmDatasetError(f"Invalid eye-on-arm dataset {source}: {exc}") from exc
    if not isinstance(document, dict):
        raise EyeOnArmDatasetError("Eye-on-arm dataset root must be an object")
    dataset = eye_on_arm_dataset_from_dict(document)
    if expected_source_hashes is not None:
        expected = {
            _identifier(key, "expected source hash id"): _digest(
                value, f"expected source hash {key}"
            )
            for key, value in expected_source_hashes.items()
        }
        if dict(dataset.source_hashes) != dict(sorted(expected.items())):
            raise EyeOnArmDatasetError("Eye-on-arm dataset source hash set mismatch")
    return dataset

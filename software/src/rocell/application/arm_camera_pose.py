"""Strict, zero-authority FK projection for the arm-mounted camera.

The RoArm-M3 camera holder moves with vendor URDF link ``link2``.  This
module projects one *achieved* six-joint state through the reviewed URDF and
the two explicit installation transforms::

    Wv_T_C_arm(q) = Wv_T_link2(q) * link2_T_E * E_T_C_arm

``Wv`` is the frame-contract name for the pinned URDF's ``world`` root.  The
relabel is explicit below; no controller-frame (``R_ctrl``) equivalence is
implied.  The service performs no camera, arm, network, serial, command, or
permit operation.  Its result always carries virtual, zero physical authority.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
from pathlib import Path
import re
from types import MappingProxyType
from typing import Any

from rocell.calibration.eye_on_arm_evidence import (
    MAX_KINEMATIC_MODEL_BYTES,
    PINNED_ROARM_M3_KINEMATIC_SHA256,
)
from rocell.geometry.transforms import RigidTransform, Rotation3, Vec3
from rocell.geometry.urdf import (
    JointPosition,
    JointPositionUnit,
    JointStateError,
    UrdfError,
    UrdfModel,
)
from rocell.kinematics.ik import ARM_JOINT_NAMES, GRIPPER_JOINT_NAME

from .runtime_ports import (
    ArmFeedbackSample,
    RuntimeAuthority,
    RuntimeExecutionMode,
    RuntimeInstant,
)


ARM_CAMERA_JOINT_ORDER: tuple[str, ...] = (*ARM_JOINT_NAMES, GRIPPER_JOINT_NAME)
ARM_CAMERA_POSE_SCHEMA = "rocell.arm_camera_optical_pose.v1"
ARM_CAMERA_BINDING_SCHEMA = "rocell.arm_camera_kinematic_binding.v1"
ACHIEVED_MODEL_JOINTS_SCHEMA = "rocell.achieved_model_joint_positions.v1"
ACHIEVED_JOINT_SAMPLE_SCHEMA = "rocell.achieved_model_joint_sample.v1"
ARM_CAMERA_PROJECTOR_IMPLEMENTATION_ID = "rocell.arm_camera_pose_projector.v1"

ARM_CAMERA_BINDING_SOURCE_KEYS: tuple[str, ...] = (
    "arm_frame_contract",
    "camera_manifest",
    "carrier_kinematic_model",
    "carrier_registration",
    "eye_on_arm_extrinsic",
    "joint_coordinate_binding",
)
ARM_CAMERA_POSE_SOURCE_KEYS: tuple[str, ...] = (
    *ARM_CAMERA_BINDING_SOURCE_KEYS,
    "achieved_joint_state",
    "achieved_joint_sample",
    "kinematic_binding",
    "projector_implementation",
)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_MAX_IDENTIFIER_LENGTH = 256
_MAX_IMPLEMENTATION_BYTES = 2 * 1024 * 1024
_IMPLEMENTATION_DEPENDENCIES: tuple[str, ...] = (
    "application/arm_camera_pose.py",
    "application/runtime_ports.py",
    "geometry/transforms.py",
    "geometry/urdf.py",
    "kinematics/ik.py",
)


class ArmCameraPoseError(ValueError):
    """An arm-camera pose input, binding, model, or record is incoherent."""


class AchievedJointStateSource(str, Enum):
    """How model-space joint positions were obtained.

    This is provenance only.  In particular, ``OFFLINE_FEEDBACK_PROJECTION``
    does not assert that a physical clock, joint reference, or received arm was
    commissioned.
    """

    VIRTUAL_PLANT = "VIRTUAL_PLANT"
    OFFLINE_FEEDBACK_PROJECTION = "OFFLINE_FEEDBACK_PROJECTION"


class ArmCameraTransformSource(str, Enum):
    """Provenance class for a fixed transform, never an acceptance claim."""

    SYNTHETIC_FIXTURE = "SYNTHETIC_FIXTURE"
    CALIBRATION_ARTIFACT = "CALIBRATION_ARTIFACT"


def _identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or len(value) > _MAX_IDENTIFIER_LENGTH:
        raise ArmCameraPoseError(
            f"{label} must be bounded, non-empty text"
        )
    if value != value.strip() or any(
        ord(character) < 32 or ord(character) == 127 for character in value
    ):
        raise ArmCameraPoseError(f"{label} contains invalid whitespace or controls")
    return value


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ArmCameraPoseError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _finite(value: object, label: str) -> float:
    # JointPosition and Vec3 perform the definitive finite checks.  This helper
    # also rejects bool, which Python otherwise treats as an integer.
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ArmCameraPoseError(f"{label} must be a finite number")
    parsed = float(value)
    try:
        json.dumps(parsed, allow_nan=False)
    except ValueError as exc:
        raise ArmCameraPoseError(f"{label} must be a finite number") from exc
    return parsed


def _integer(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ArmCameraPoseError(f"{label} must be a non-negative integer")
    return value


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ArmCameraPoseError(f"{label} must be an object")
    if any(not isinstance(key, str) for key in value):
        raise ArmCameraPoseError(f"{label} keys must be strings")
    return value


def _exact_keys(
    value: Mapping[str, Any], expected: set[str], label: str
) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ArmCameraPoseError(
            f"{label} keys differ; missing={missing}, extra={extra}"
        )


def _canonical_hash(value: object) -> str:
    try:
        payload = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ArmCameraPoseError(
            f"arm-camera evidence is not canonical JSON: {exc}"
        ) from exc
    return hashlib.sha256(payload).hexdigest()


def _freeze_hashes(
    values: object,
    *,
    expected_keys: tuple[str, ...],
    label: str,
) -> tuple[tuple[str, str], ...]:
    if not isinstance(values, tuple):
        raise ArmCameraPoseError(f"{label} must be an immutable tuple")
    parsed: list[tuple[str, str]] = []
    for index, pair in enumerate(values):
        if not isinstance(pair, tuple) or len(pair) != 2:
            raise ArmCameraPoseError(f"{label}[{index}] must be an immutable pair")
        key = _identifier(pair[0], f"{label}[{index}] key")
        digest = _digest(pair[1], f"{label}[{index}] digest")
        parsed.append((key, digest))
    frozen = tuple(parsed)
    if tuple(key for key, _ in frozen) != expected_keys:
        raise ArmCameraPoseError(
            f"{label} must use the exact canonical keys {expected_keys}"
        )
    return frozen


def _hashes_from_document(
    value: object,
    *,
    expected_keys: tuple[str, ...],
    label: str,
) -> tuple[tuple[str, str], ...]:
    document = _mapping(value, label)
    _exact_keys(document, set(expected_keys), label)
    return tuple(
        (key, _digest(document[key], f"{label}.{key}")) for key in expected_keys
    )


def _transform_to_dict(transform: RigidTransform) -> dict[str, object]:
    return {
        "to_frame": transform.parent_frame,
        "from_frame": transform.child_frame,
        "rotation_row_major": list(transform.rotation.matrix),
        "translation_mm": [
            transform.translation_mm.x,
            transform.translation_mm.y,
            transform.translation_mm.z,
        ],
    }


def _transform_from_dict(value: object, label: str) -> RigidTransform:
    document = _mapping(value, label)
    _exact_keys(
        document,
        {"to_frame", "from_frame", "rotation_row_major", "translation_mm"},
        label,
    )
    rotation = document["rotation_row_major"]
    translation = document["translation_mm"]
    if not isinstance(rotation, list) or len(rotation) != 9:
        raise ArmCameraPoseError(f"{label}.rotation_row_major must contain 9 numbers")
    if not isinstance(translation, list) or len(translation) != 3:
        raise ArmCameraPoseError(f"{label}.translation_mm must contain 3 numbers")
    try:
        return RigidTransform(
            parent_frame=_identifier(document["to_frame"], f"{label}.to_frame"),
            child_frame=_identifier(document["from_frame"], f"{label}.from_frame"),
            rotation=Rotation3(
                tuple(
                    _finite(component, f"{label}.rotation_row_major[{index}]")
                    for index, component in enumerate(rotation)
                )
            ),
            translation_mm=Vec3(
                *(
                    _finite(component, f"{label}.translation_mm[{index}]")
                    for index, component in enumerate(translation)
                )
            ),
        )
    except (TypeError, ValueError) as exc:
        if isinstance(exc, ArmCameraPoseError):
            raise
        raise ArmCameraPoseError(f"{label} is not a rigid transform: {exc}") from exc


def _instant_to_dict(value: RuntimeInstant) -> dict[str, object]:
    return {
        "clock_id": value.clock_id,
        "tick": value.tick,
        "tick_period_ns": value.tick_period_ns,
    }


def _instant_from_dict(value: object, label: str) -> RuntimeInstant:
    document = _mapping(value, label)
    _exact_keys(document, {"clock_id", "tick", "tick_period_ns"}, label)
    period = document["tick_period_ns"]
    if period is not None:
        period = _integer(period, f"{label}.tick_period_ns")
        if period == 0:
            raise ArmCameraPoseError(f"{label}.tick_period_ns must be positive")
    try:
        return RuntimeInstant(
            clock_id=_identifier(document["clock_id"], f"{label}.clock_id"),
            tick=_integer(document["tick"], f"{label}.tick"),
            tick_period_ns=period,
        )
    except (TypeError, ValueError) as exc:
        if isinstance(exc, ArmCameraPoseError):
            raise
        raise ArmCameraPoseError(f"{label} is invalid: {exc}") from exc


def _authority_to_dict(value: RuntimeAuthority) -> dict[str, object]:
    return {
        "execution_mode": value.execution_mode.value,
        "hardware_accessed": value.hardware_accessed,
        "hardware_commands_generated": value.hardware_commands_generated,
        "live_motion_authorized": value.live_motion_authorized,
        "physical_contact_authorized": value.physical_contact_authorized,
        "physical_release_effect": value.physical_release_effect,
    }


def _zero_virtual_authority() -> RuntimeAuthority:
    return RuntimeAuthority.zero(RuntimeExecutionMode.VIRTUAL)


def _require_zero_virtual_authority_document(value: object, label: str) -> None:
    document = _mapping(value, label)
    _exact_keys(
        document,
        {
            "execution_mode",
            "hardware_accessed",
            "hardware_commands_generated",
            "live_motion_authorized",
            "physical_contact_authorized",
            "physical_release_effect",
        },
        label,
    )
    if document["execution_mode"] != RuntimeExecutionMode.VIRTUAL.value:
        raise ArmCameraPoseError(f"{label} execution mode must be VIRTUAL")
    for key in (
        "hardware_accessed",
        "live_motion_authorized",
        "physical_contact_authorized",
    ):
        if not isinstance(document[key], bool) or document[key]:
            raise ArmCameraPoseError(f"{label}.{key} must be false")
    command_count = document["hardware_commands_generated"]
    if isinstance(command_count, bool) or command_count != 0:
        raise ArmCameraPoseError(
            f"{label}.hardware_commands_generated must be integer zero"
        )
    if document["physical_release_effect"] != "NONE":
        raise ArmCameraPoseError(f"{label}.physical_release_effect must be NONE")


@dataclass(frozen=True, slots=True)
class AchievedModelJointPositions:
    """One complete model-space joint vector from an achieved-state source."""

    positions: tuple[tuple[str, JointPosition], ...]
    source_kind: AchievedJointStateSource
    source_state_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.positions, tuple):
            raise ArmCameraPoseError("positions must be an immutable tuple")
        parsed: list[tuple[str, JointPosition]] = []
        for index, pair in enumerate(self.positions):
            if not isinstance(pair, tuple) or len(pair) != 2:
                raise ArmCameraPoseError(f"positions[{index}] must be an immutable pair")
            name, position = pair
            if not isinstance(name, str):
                raise ArmCameraPoseError(f"positions[{index}] joint name must be text")
            if not isinstance(position, JointPosition):
                raise ArmCameraPoseError(
                    f"positions[{index}] must contain a JointPosition"
                )
            if position.unit is not JointPositionUnit.RADIAN:
                raise ArmCameraPoseError(f"joint {name!r} must use typed radians")
            parsed.append((name, position))
        frozen = tuple(parsed)
        if tuple(name for name, _ in frozen) != ARM_CAMERA_JOINT_ORDER:
            raise ArmCameraPoseError(
                "positions must use the exact six-joint RoArm-M3-Pro order"
            )
        object.__setattr__(self, "positions", frozen)
        if not isinstance(self.source_kind, AchievedJointStateSource):
            try:
                object.__setattr__(
                    self, "source_kind", AchievedJointStateSource(self.source_kind)
                )
            except (TypeError, ValueError) as exc:
                raise ArmCameraPoseError("source_kind is unsupported") from exc
        object.__setattr__(
            self,
            "source_state_sha256",
            _digest(self.source_state_sha256, "source_state_sha256"),
        )

    @property
    def positions_by_name(self) -> Mapping[str, JointPosition]:
        return MappingProxyType(dict(self.positions))

    @property
    def content_hash(self) -> str:
        return _canonical_hash(self.to_dict())

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": ACHIEVED_MODEL_JOINTS_SCHEMA,
            "source_kind": self.source_kind.value,
            "source_state_sha256": self.source_state_sha256,
            "positions_rad": [
                {"joint": name, "position_rad": position.value}
                for name, position in self.positions
            ],
        }

    @classmethod
    def from_dict(cls, value: object) -> "AchievedModelJointPositions":
        document = _mapping(value, "achieved model joints")
        _exact_keys(
            document,
            {"schema", "source_kind", "source_state_sha256", "positions_rad"},
            "achieved model joints",
        )
        if document["schema"] != ACHIEVED_MODEL_JOINTS_SCHEMA:
            raise ArmCameraPoseError("unsupported achieved model joints schema")
        position_documents = document["positions_rad"]
        if not isinstance(position_documents, list):
            raise ArmCameraPoseError("positions_rad must be an array")
        positions: list[tuple[str, JointPosition]] = []
        for index, item in enumerate(position_documents):
            pair = _mapping(item, f"positions_rad[{index}]")
            _exact_keys(pair, {"joint", "position_rad"}, f"positions_rad[{index}]")
            positions.append(
                (
                    _identifier(pair["joint"], f"positions_rad[{index}].joint"),
                    JointPosition.radians(
                        _finite(
                            pair["position_rad"],
                            f"positions_rad[{index}].position_rad",
                        )
                    ),
                )
            )
        try:
            result = cls(
                positions=tuple(positions),
                source_kind=AchievedJointStateSource(document["source_kind"]),
                source_state_sha256=_digest(
                    document["source_state_sha256"], "source_state_sha256"
                ),
            )
        except (TypeError, ValueError) as exc:
            if isinstance(exc, ArmCameraPoseError):
                raise
            raise ArmCameraPoseError(f"achieved model joints are invalid: {exc}") from exc
        if result.to_dict() != dict(document):
            raise ArmCameraPoseError("achieved model joints are not canonical")
        return result


@dataclass(frozen=True, slots=True)
class ArmCameraKinematicBinding:
    """Fixed carrier/camera transforms plus exact provenance hashes."""

    link2_T_E: RigidTransform
    E_T_C_arm: RigidTransform
    carrier_source_kind: ArmCameraTransformSource
    extrinsic_source_kind: ArmCameraTransformSource
    source_hashes: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        if not isinstance(self.link2_T_E, RigidTransform):
            raise TypeError("link2_T_E must be a RigidTransform")
        if (
            self.link2_T_E.parent_frame != "link2"
            or self.link2_T_E.child_frame != "E"
        ):
            raise ArmCameraPoseError("carrier registration must be link2_T_E")
        if not isinstance(self.E_T_C_arm, RigidTransform):
            raise TypeError("E_T_C_arm must be a RigidTransform")
        if (
            self.E_T_C_arm.parent_frame != "E"
            or self.E_T_C_arm.child_frame != "C_arm"
        ):
            raise ArmCameraPoseError("camera extrinsic must be E_T_C_arm")
        for field_name in ("carrier_source_kind", "extrinsic_source_kind"):
            value = getattr(self, field_name)
            if not isinstance(value, ArmCameraTransformSource):
                try:
                    object.__setattr__(
                        self, field_name, ArmCameraTransformSource(value)
                    )
                except (TypeError, ValueError) as exc:
                    raise ArmCameraPoseError(f"{field_name} is unsupported") from exc
        frozen_hashes = _freeze_hashes(
            self.source_hashes,
            expected_keys=ARM_CAMERA_BINDING_SOURCE_KEYS,
            label="binding source_hashes",
        )
        object.__setattr__(self, "source_hashes", frozen_hashes)
        if (
            dict(frozen_hashes)["carrier_kinematic_model"]
            != PINNED_ROARM_M3_KINEMATIC_SHA256
        ):
            raise ArmCameraPoseError(
                "binding must use the reviewed pinned RoArm-M3 kinematic model"
            )

    @property
    def source_hashes_by_name(self) -> Mapping[str, str]:
        return MappingProxyType(dict(self.source_hashes))

    @property
    def binding_hash(self) -> str:
        return _canonical_hash(self.to_dict())

    @property
    def authority(self) -> RuntimeAuthority:
        return _zero_virtual_authority()

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": ARM_CAMERA_BINDING_SCHEMA,
            "carrier_source_kind": self.carrier_source_kind.value,
            "extrinsic_source_kind": self.extrinsic_source_kind.value,
            "link2_T_E": _transform_to_dict(self.link2_T_E),
            "E_T_C_arm": _transform_to_dict(self.E_T_C_arm),
            "source_hashes": dict(self.source_hashes),
            "simulation_only": True,
            "can_release_physical_gates": False,
            "authority": _authority_to_dict(self.authority),
        }

    @classmethod
    def from_dict(cls, value: object) -> "ArmCameraKinematicBinding":
        document = _mapping(value, "arm camera binding")
        _exact_keys(
            document,
            {
                "schema",
                "carrier_source_kind",
                "extrinsic_source_kind",
                "link2_T_E",
                "E_T_C_arm",
                "source_hashes",
                "simulation_only",
                "can_release_physical_gates",
                "authority",
            },
            "arm camera binding",
        )
        if document["schema"] != ARM_CAMERA_BINDING_SCHEMA:
            raise ArmCameraPoseError("unsupported arm camera binding schema")
        if document["simulation_only"] is not True:
            raise ArmCameraPoseError("arm camera binding must remain simulation-only")
        if document["can_release_physical_gates"] is not False:
            raise ArmCameraPoseError("arm camera binding cannot release physical gates")
        _require_zero_virtual_authority_document(
            document["authority"], "arm camera binding authority"
        )
        try:
            result = cls(
                link2_T_E=_transform_from_dict(document["link2_T_E"], "link2_T_E"),
                E_T_C_arm=_transform_from_dict(
                    document["E_T_C_arm"], "E_T_C_arm"
                ),
                carrier_source_kind=ArmCameraTransformSource(
                    document["carrier_source_kind"]
                ),
                extrinsic_source_kind=ArmCameraTransformSource(
                    document["extrinsic_source_kind"]
                ),
                source_hashes=_hashes_from_document(
                    document["source_hashes"],
                    expected_keys=ARM_CAMERA_BINDING_SOURCE_KEYS,
                    label="source_hashes",
                ),
            )
        except (TypeError, ValueError) as exc:
            if isinstance(exc, ArmCameraPoseError):
                raise
            raise ArmCameraPoseError(f"arm camera binding is invalid: {exc}") from exc
        if result.to_dict() != dict(document):
            raise ArmCameraPoseError("arm camera binding is not canonical")
        return result


def achieved_joint_sample_sha256(
    sample: ArmFeedbackSample[AchievedModelJointPositions],
) -> str:
    """Hash the complete achieved-state envelope, including its clock binding."""

    if not isinstance(sample, ArmFeedbackSample):
        raise TypeError("sample must be an ArmFeedbackSample")
    if not isinstance(sample.feedback, AchievedModelJointPositions):
        raise TypeError("sample feedback must be AchievedModelJointPositions")
    return _canonical_hash(
        {
            "schema": ACHIEVED_JOINT_SAMPLE_SCHEMA,
            "sample_id": sample.sample_id,
            "sequence": sample.sequence,
            "observed_at": _instant_to_dict(sample.observed_at),
            "stale": sample.stale,
            "joint_state": sample.feedback.to_dict(),
        }
    )


@dataclass(frozen=True, slots=True)
class ArmCameraOpticalPose:
    """One camera optical pose projected from an achieved joint sample."""

    joint_sample_id: str
    joint_sequence: int
    joint_observed_at: RuntimeInstant
    joint_state_sha256: str
    joint_sample_sha256: str
    Wv_T_C_arm: RigidTransform
    binding_sha256: str
    source_hashes: tuple[tuple[str, str], ...]
    implementation_sha256: str
    authority: RuntimeAuthority = field(
        init=False, default_factory=_zero_virtual_authority
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "joint_sample_id", _identifier(self.joint_sample_id, "joint_sample_id")
        )
        object.__setattr__(
            self, "joint_sequence", _integer(self.joint_sequence, "joint_sequence")
        )
        if not isinstance(self.joint_observed_at, RuntimeInstant):
            raise TypeError("joint_observed_at must be a RuntimeInstant")
        for field_name in (
            "joint_state_sha256",
            "joint_sample_sha256",
            "binding_sha256",
            "implementation_sha256",
        ):
            object.__setattr__(
                self, field_name, _digest(getattr(self, field_name), field_name)
            )
        if not isinstance(self.Wv_T_C_arm, RigidTransform):
            raise TypeError("Wv_T_C_arm must be a RigidTransform")
        if (
            self.Wv_T_C_arm.parent_frame != "Wv"
            or self.Wv_T_C_arm.child_frame != "C_arm"
        ):
            raise ArmCameraPoseError("optical pose must be Wv_T_C_arm")
        frozen_hashes = _freeze_hashes(
            self.source_hashes,
            expected_keys=ARM_CAMERA_POSE_SOURCE_KEYS,
            label="pose source_hashes",
        )
        object.__setattr__(self, "source_hashes", frozen_hashes)
        source_map = dict(frozen_hashes)
        expected_redundant = {
            "achieved_joint_state": self.joint_state_sha256,
            "achieved_joint_sample": self.joint_sample_sha256,
            "kinematic_binding": self.binding_sha256,
            "projector_implementation": self.implementation_sha256,
        }
        if any(source_map[key] != value for key, value in expected_redundant.items()):
            raise ArmCameraPoseError("pose source hashes disagree with record hashes")
        if (
            source_map["carrier_kinematic_model"]
            != PINNED_ROARM_M3_KINEMATIC_SHA256
        ):
            raise ArmCameraPoseError(
                "pose must use the reviewed pinned RoArm-M3 kinematic model"
            )
        if not isinstance(self.authority, RuntimeAuthority):
            raise TypeError("authority must be RuntimeAuthority")
        if (
            self.authority.execution_mode is not RuntimeExecutionMode.VIRTUAL
            or not self.authority.is_zero_authority
        ):
            raise ArmCameraPoseError("arm-camera pose authority must be exactly virtual zero")

    @property
    def source_hashes_by_name(self) -> Mapping[str, str]:
        return MappingProxyType(dict(self.source_hashes))

    @property
    def content_hash(self) -> str:
        return _canonical_hash(self.to_dict())

    @property
    def can_release_physical_gates(self) -> bool:
        return False

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": ARM_CAMERA_POSE_SCHEMA,
            "status": "PROJECTED_FROM_ACHIEVED_JOINTS_SIMULATION_ONLY",
            "simulation_only": True,
            "can_release_physical_gates": False,
            "joint_sample": {
                "sample_id": self.joint_sample_id,
                "sequence": self.joint_sequence,
                "observed_at": _instant_to_dict(self.joint_observed_at),
                "joint_state_sha256": self.joint_state_sha256,
                "joint_sample_sha256": self.joint_sample_sha256,
            },
            "Wv_T_C_arm": _transform_to_dict(self.Wv_T_C_arm),
            "binding_sha256": self.binding_sha256,
            "source_hashes": dict(self.source_hashes),
            "implementation": {
                "id": ARM_CAMERA_PROJECTOR_IMPLEMENTATION_ID,
                "sha256": self.implementation_sha256,
            },
            "authority": _authority_to_dict(self.authority),
        }

    @classmethod
    def from_dict(cls, value: object) -> "ArmCameraOpticalPose":
        document = _mapping(value, "arm camera optical pose")
        _exact_keys(
            document,
            {
                "schema",
                "status",
                "simulation_only",
                "can_release_physical_gates",
                "joint_sample",
                "Wv_T_C_arm",
                "binding_sha256",
                "source_hashes",
                "implementation",
                "authority",
            },
            "arm camera optical pose",
        )
        if document["schema"] != ARM_CAMERA_POSE_SCHEMA:
            raise ArmCameraPoseError("unsupported arm camera optical pose schema")
        if document["status"] != "PROJECTED_FROM_ACHIEVED_JOINTS_SIMULATION_ONLY":
            raise ArmCameraPoseError("unsupported arm camera optical pose status")
        if document["simulation_only"] is not True:
            raise ArmCameraPoseError("arm camera optical pose must remain simulation-only")
        if document["can_release_physical_gates"] is not False:
            raise ArmCameraPoseError("arm camera optical pose cannot release physical gates")
        _require_zero_virtual_authority_document(
            document["authority"], "arm camera optical pose authority"
        )
        joint_sample = _mapping(document["joint_sample"], "joint_sample")
        _exact_keys(
            joint_sample,
            {
                "sample_id",
                "sequence",
                "observed_at",
                "joint_state_sha256",
                "joint_sample_sha256",
            },
            "joint_sample",
        )
        implementation = _mapping(document["implementation"], "implementation")
        _exact_keys(implementation, {"id", "sha256"}, "implementation")
        if implementation["id"] != ARM_CAMERA_PROJECTOR_IMPLEMENTATION_ID:
            raise ArmCameraPoseError("unsupported arm camera projector implementation")
        try:
            result = cls(
                joint_sample_id=_identifier(joint_sample["sample_id"], "sample_id"),
                joint_sequence=_integer(joint_sample["sequence"], "sequence"),
                joint_observed_at=_instant_from_dict(
                    joint_sample["observed_at"], "joint_sample.observed_at"
                ),
                joint_state_sha256=_digest(
                    joint_sample["joint_state_sha256"], "joint_state_sha256"
                ),
                joint_sample_sha256=_digest(
                    joint_sample["joint_sample_sha256"], "joint_sample_sha256"
                ),
                Wv_T_C_arm=_transform_from_dict(
                    document["Wv_T_C_arm"], "Wv_T_C_arm"
                ),
                binding_sha256=_digest(document["binding_sha256"], "binding_sha256"),
                source_hashes=_hashes_from_document(
                    document["source_hashes"],
                    expected_keys=ARM_CAMERA_POSE_SOURCE_KEYS,
                    label="source_hashes",
                ),
                implementation_sha256=_digest(
                    implementation["sha256"], "implementation.sha256"
                ),
            )
        except (TypeError, ValueError) as exc:
            if isinstance(exc, ArmCameraPoseError):
                raise
            raise ArmCameraPoseError(f"arm camera optical pose is invalid: {exc}") from exc
        if result.to_dict() != dict(document):
            raise ArmCameraPoseError("arm camera optical pose is not canonical")
        return result


class ArmCameraPoseProjector:
    """Project achieved model joints through the exact reviewed FK source."""

    __slots__ = ("_binding", "_implementation_sha256", "_model")

    def __init__(
        self,
        *,
        model_path: str | Path,
        binding: ArmCameraKinematicBinding,
    ) -> None:
        if not isinstance(binding, ArmCameraKinematicBinding):
            raise TypeError("binding must be an ArmCameraKinematicBinding")
        self._binding = binding
        self._model = self._load_pinned_model(Path(model_path))
        self._implementation_sha256 = self._read_implementation_hash()

    @property
    def binding(self) -> ArmCameraKinematicBinding:
        return self._binding

    @property
    def implementation_sha256(self) -> str:
        return self._implementation_sha256

    @staticmethod
    def _read_bounded_file(path: Path, maximum_bytes: int, label: str) -> bytes:
        try:
            if path.stat().st_size > maximum_bytes:
                raise ArmCameraPoseError(f"{label} exceeds {maximum_bytes} bytes")
            with path.open("rb") as stream:
                payload = stream.read(maximum_bytes + 1)
        except OSError as exc:
            raise ArmCameraPoseError(f"could not read {label}: {exc}") from exc
        if len(payload) > maximum_bytes:
            raise ArmCameraPoseError(f"{label} exceeds {maximum_bytes} bytes")
        return payload

    def _load_pinned_model(self, path: Path) -> UrdfModel:
        raw_model = self._read_bounded_file(
            path, MAX_KINEMATIC_MODEL_BYTES, "kinematic model"
        )
        observed_hash = hashlib.sha256(raw_model).hexdigest()
        expected_hash = self.binding.source_hashes_by_name[
            "carrier_kinematic_model"
        ]
        if observed_hash != expected_hash:
            raise ArmCameraPoseError("kinematic model bytes do not match binding hash")
        if observed_hash != PINNED_ROARM_M3_KINEMATIC_SHA256:
            raise ArmCameraPoseError("kinematic model is not the reviewed RoArm-M3 pin")
        try:
            model = UrdfModel.from_xml(
                raw_model.decode("utf-8"), source_name=str(path)
            )
        except (UnicodeError, UrdfError) as exc:
            raise ArmCameraPoseError(f"could not parse kinematic model: {exc}") from exc
        if model.root_link != "world" or "link2" not in model.link_names:
            raise ArmCameraPoseError(
                "kinematic model must preserve the world root and link2 carrier"
            )
        if set(model.movable_joint_names) != set(ARM_CAMERA_JOINT_ORDER):
            raise ArmCameraPoseError(
                "kinematic model movable joints differ from the six-joint contract"
            )
        return model

    @classmethod
    def _read_implementation_hash(cls) -> str:
        # FK semantics span the projector, transform composition, URDF parser,
        # joint-name contract, and runtime envelope.  Hash the bounded source
        # bundle so a dependency edit cannot replay under the old identity.
        rocell_root = Path(__file__).resolve(strict=True).parents[1]
        source_hashes = {
            relative_path: hashlib.sha256(
                cls._read_bounded_file(
                    rocell_root / relative_path,
                    _MAX_IMPLEMENTATION_BYTES,
                    f"arm-camera implementation dependency {relative_path}",
                )
            ).hexdigest()
            for relative_path in _IMPLEMENTATION_DEPENDENCIES
        }
        return _canonical_hash(
            {
                "schema": "rocell.arm_camera_projector_implementation_bundle.v1",
                "sources": source_hashes,
            }
        )

    def project(
        self,
        sample: ArmFeedbackSample[AchievedModelJointPositions],
    ) -> ArmCameraOpticalPose:
        if not isinstance(sample, ArmFeedbackSample):
            raise TypeError("sample must be an ArmFeedbackSample")
        if not isinstance(sample.feedback, AchievedModelJointPositions):
            raise TypeError("sample feedback must be AchievedModelJointPositions")
        if sample.stale:
            raise ArmCameraPoseError("stale achieved joint feedback cannot produce a pose")

        try:
            root_transforms = self._model.forward_kinematics(
                sample.feedback.positions_by_name
            )
        except (JointStateError, UrdfError, ValueError) as exc:
            raise ArmCameraPoseError(f"achieved joint state failed FK: {exc}") from exc

        # The reviewed frame contract defines Wv as this URDF's world/root.
        # Relabel only that root token; do not infer R_ctrl or base equivalence.
        world_T_link2 = root_transforms["link2"]
        Wv_T_link2 = RigidTransform(
            parent_frame="Wv",
            child_frame="link2",
            rotation=world_T_link2.rotation,
            translation_mm=world_T_link2.translation_mm,
        )
        Wv_T_C_arm = (
            Wv_T_link2.compose(self.binding.link2_T_E)
            .compose(self.binding.E_T_C_arm)
        )

        joint_state_hash = sample.feedback.content_hash
        joint_sample_hash = achieved_joint_sample_sha256(sample)
        source_hashes = (
            *self.binding.source_hashes,
            ("achieved_joint_state", joint_state_hash),
            ("achieved_joint_sample", joint_sample_hash),
            ("kinematic_binding", self.binding.binding_hash),
            ("projector_implementation", self.implementation_sha256),
        )
        return ArmCameraOpticalPose(
            joint_sample_id=sample.sample_id,
            joint_sequence=sample.sequence,
            joint_observed_at=sample.observed_at,
            joint_state_sha256=joint_state_hash,
            joint_sample_sha256=joint_sample_hash,
            Wv_T_C_arm=Wv_T_C_arm,
            binding_sha256=self.binding.binding_hash,
            source_hashes=source_hashes,
            implementation_sha256=self.implementation_sha256,
        )


__all__ = [
    "ACHIEVED_JOINT_SAMPLE_SCHEMA",
    "ACHIEVED_MODEL_JOINTS_SCHEMA",
    "ARM_CAMERA_BINDING_SCHEMA",
    "ARM_CAMERA_BINDING_SOURCE_KEYS",
    "ARM_CAMERA_JOINT_ORDER",
    "ARM_CAMERA_POSE_SCHEMA",
    "ARM_CAMERA_POSE_SOURCE_KEYS",
    "ARM_CAMERA_PROJECTOR_IMPLEMENTATION_ID",
    "AchievedJointStateSource",
    "AchievedModelJointPositions",
    "ArmCameraKinematicBinding",
    "ArmCameraOpticalPose",
    "ArmCameraPoseError",
    "ArmCameraPoseProjector",
    "ArmCameraTransformSource",
    "achieved_joint_sample_sha256",
]

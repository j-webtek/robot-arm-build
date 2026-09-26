"""Strict measured-calibration decoder for deterministic motion planning."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import re
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from rocell.geometry import RigidTransform, Rotation3, Vec3

from .artifacts import ArtifactAssessment, ArtifactState, CalibrationArtifact


class PlannerCalibrationSnapshotError(ValueError):
    """Measured calibration artifacts cannot form one planner snapshot."""


_ID = re.compile(r"^[A-Za-z0-9_.-]+$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_JOINT_ORDER = (
    "b_base",
    "s_shoulder",
    "e_elbow",
    "t_wrist_pitch",
    "r_wrist_roll",
    "g_gripper",
)
_SHARED = ("robot_reference", "arm_board", "controller_correlation")
_DEVICE = {
    "keyboard": ("keyboard_pose", "keyboard_tcp"),
    "phone": ("phone_screen", "phone_tcp"),
}


def required_planner_artifact_ids(device: str) -> tuple[str, ...]:
    try:
        return (*_SHARED, *_DEVICE[device])
    except KeyError as exc:
        raise PlannerCalibrationSnapshotError(f"unsupported device {device!r}") from exc


def _exact(value: object, fields: set[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PlannerCalibrationSnapshotError(f"{label} must be an object")
    actual = set(value)
    if actual != fields:
        raise PlannerCalibrationSnapshotError(
            f"{label} fields differ from exact schema: "
            f"missing={sorted(fields - actual)}, unexpected={sorted(actual - fields)}"
        )
    return value


def _identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise PlannerCalibrationSnapshotError(f"{label} must be an identifier")
    return value


def _sha256(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise PlannerCalibrationSnapshotError(f"{label} must be a SHA-256 digest")
    return value


def _finite(value: object, label: str, *, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PlannerCalibrationSnapshotError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result) or (minimum is not None and result < minimum):
        raise PlannerCalibrationSnapshotError(f"{label} is outside its finite range")
    return result


def _positive_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise PlannerCalibrationSnapshotError(f"{label} must be a positive integer")
    return value


def _vector(value: object, size: int, label: str) -> tuple[float, ...]:
    if not isinstance(value, (list, tuple)) or len(value) != size:
        raise PlannerCalibrationSnapshotError(f"{label} must contain {size} values")
    return tuple(_finite(item, f"{label}[{index}]") for index, item in enumerate(value))


def _qualified(value: object, label: str) -> None:
    if value is not True:
        raise PlannerCalibrationSnapshotError(f"{label} must be true")


def _transform(value: object, parent: str, child: str, label: str) -> RigidTransform:
    fields = {
        "parent_frame",
        "child_frame",
        "rotation_matrix_row_major",
        "translation_mm",
        "measurement_method_id",
        "sample_count",
        "heldout_count",
        "heldout_max_translation_error_mm",
        "heldout_max_rotation_error_rad",
        "qualified",
    }
    row = _exact(value, fields, label)
    if row["parent_frame"] != parent or row["child_frame"] != child:
        raise PlannerCalibrationSnapshotError(f"{label} must encode {parent}_T_{child}")
    _identifier(row["measurement_method_id"], f"{label}.measurement_method_id")
    _positive_int(row["sample_count"], f"{label}.sample_count")
    _positive_int(row["heldout_count"], f"{label}.heldout_count")
    _finite(
        row["heldout_max_translation_error_mm"],
        f"{label}.heldout_max_translation_error_mm",
        minimum=0.0,
    )
    _finite(
        row["heldout_max_rotation_error_rad"],
        f"{label}.heldout_max_rotation_error_rad",
        minimum=0.0,
    )
    _qualified(row["qualified"], f"{label}.qualified")
    rotation = Rotation3(
        _vector(row["rotation_matrix_row_major"], 9, f"{label}.rotation")
    )
    translation = _vector(row["translation_mm"], 3, f"{label}.translation_mm")
    return RigidTransform(parent, child, rotation, Vec3(*translation))


def _transform_dict(value: RigidTransform) -> dict[str, Any]:
    return {
        "parent_frame": value.parent_frame,
        "child_frame": value.child_frame,
        "rotation_matrix_row_major": list(value.rotation.matrix),
        "translation_mm": [
            value.translation_mm.x,
            value.translation_mm.y,
            value.translation_mm.z,
        ],
    }


@dataclass(frozen=True, slots=True)
class PlannerCalibrationSnapshot:
    device: str
    manifest_id: str
    active_build_id: str
    artifact_hashes: Mapping[str, str]
    board_T_vendor_world: RigidTransform
    board_T_device: RigidTransform
    hand_T_tool: RigidTransform
    robot_reference_identity: Mapping[str, str]
    joint_zero_offsets_rad: tuple[float, ...]
    joint_lower_rad: tuple[float, ...]
    joint_upper_rad: tuple[float, ...]
    joint_signs: tuple[int, ...]
    controller_correlation: Mapping[str, Any]
    target_map_sha256: str

    def __post_init__(self) -> None:
        required = required_planner_artifact_ids(self.device)
        if set(self.artifact_hashes) != set(required):
            raise PlannerCalibrationSnapshotError("snapshot artifact set is incomplete")
        object.__setattr__(
            self,
            "artifact_hashes",
            MappingProxyType(dict(sorted(self.artifact_hashes.items()))),
        )
        object.__setattr__(
            self,
            "controller_correlation",
            MappingProxyType(dict(self.controller_correlation)),
        )
        expected_identity_fields = {
            "arm_identity_hash",
            "controller_identity_hash",
            "firmware_identity_hash",
        }
        if set(self.robot_reference_identity) != expected_identity_fields:
            raise PlannerCalibrationSnapshotError(
                "snapshot robot reference identity is incomplete"
            )
        identity = {
            key: _sha256(value, key)
            for key, value in self.robot_reference_identity.items()
        }
        object.__setattr__(
            self,
            "robot_reference_identity",
            MappingProxyType(dict(sorted(identity.items()))),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "rocell.planner_calibration_snapshot.v1",
            "device": self.device,
            "manifest_id": self.manifest_id,
            "active_build_id": self.active_build_id,
            "artifact_hashes": dict(self.artifact_hashes),
            "board_T_vendor_world": _transform_dict(self.board_T_vendor_world),
            "board_T_device": _transform_dict(self.board_T_device),
            "hand_T_tool": _transform_dict(self.hand_T_tool),
            "robot_reference": {
                "joint_order": list(_JOINT_ORDER),
                **dict(self.robot_reference_identity),
                "zero_offsets_rad": list(self.joint_zero_offsets_rad),
                "lower_rad": list(self.joint_lower_rad),
                "upper_rad": list(self.joint_upper_rad),
                "signs": list(self.joint_signs),
            },
            "controller_correlation": dict(self.controller_correlation),
            "target_map_sha256": self.target_map_sha256,
            "physical_authority": False,
        }

    @property
    def snapshot_sha256(self) -> str:
        payload = json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


def decode_planner_calibration_snapshot(
    *,
    device: str,
    artifacts: Mapping[str, CalibrationArtifact],
    assessments: Mapping[str, ArtifactAssessment],
    expected_target_map_sha256: str,
) -> PlannerCalibrationSnapshot:
    """Decode one exact, hash-matched measured calibration set."""

    required = required_planner_artifact_ids(device)
    if set(artifacts) != set(required) or set(assessments) != set(required):
        raise PlannerCalibrationSnapshotError(
            "planner calibration artifact set is incomplete"
        )
    target_hash = _sha256(expected_target_map_sha256, "expected_target_map_sha256")
    hashes: dict[str, str] = {}
    manifest_ids: set[str] = set()
    build_ids: set[str] = set()
    for artifact_id in required:
        artifact = artifacts[artifact_id]
        assessment = assessments[artifact_id]
        if not isinstance(artifact, CalibrationArtifact) or not isinstance(
            assessment, ArtifactAssessment
        ):
            raise TypeError(
                "planner calibrations require typed artifacts and assessments"
            )
        if artifact.artifact_id != artifact_id or assessment.artifact_id != artifact_id:
            raise PlannerCalibrationSnapshotError(
                "calibration artifact identity mismatch"
            )
        if artifact.state is not ArtifactState.VALID or not assessment.valid:
            raise PlannerCalibrationSnapshotError(
                f"calibration {artifact_id} is not VALID"
            )
        if assessment.artifact_hash != artifact.content_hash:
            raise PlannerCalibrationSnapshotError(
                f"calibration {artifact_id} hash mismatch"
            )
        hashes[artifact_id] = artifact.content_hash
        manifest_ids.add(artifact.manifest_id)
        build_ids.add(artifact.active_build_id)
    if len(manifest_ids) != 1 or len(build_ids) != 1:
        raise PlannerCalibrationSnapshotError(
            "planner calibrations do not share one manifest and active build"
        )

    reference = _exact(
        artifacts["robot_reference"].payload,
        {
            "schema",
            "joint_order",
            "zero_offsets_rad",
            "lower_rad",
            "upper_rad",
            "signs",
            "arm_identity_hash",
            "controller_identity_hash",
            "firmware_identity_hash",
            "reference_procedure_id",
            "heldout_max_error_rad",
            "qualified",
        },
        "robot_reference payload",
    )
    if (
        reference["schema"] != "rocell.robot_reference_payload.v1"
        or tuple(reference["joint_order"]) != _JOINT_ORDER
    ):
        raise PlannerCalibrationSnapshotError(
            "robot_reference schema or joint order is invalid"
        )
    _identifier(reference["reference_procedure_id"], "reference_procedure_id")
    _sha256(reference["arm_identity_hash"], "arm_identity_hash")
    _sha256(reference["controller_identity_hash"], "controller_identity_hash")
    _sha256(reference["firmware_identity_hash"], "firmware_identity_hash")
    _finite(reference["heldout_max_error_rad"], "heldout_max_error_rad", minimum=0.0)
    _qualified(reference["qualified"], "robot_reference.qualified")
    zeros = _vector(reference["zero_offsets_rad"], 6, "zero_offsets_rad")
    lower = _vector(reference["lower_rad"], 6, "lower_rad")
    upper = _vector(reference["upper_rad"], 6, "upper_rad")
    if any(lo >= hi for lo, hi in zip(lower, upper, strict=True)):
        raise PlannerCalibrationSnapshotError(
            "robot_reference joint limits are invalid"
        )
    signs_raw = reference["signs"]
    if (
        not isinstance(signs_raw, (list, tuple))
        or len(signs_raw) != 6
        or any(isinstance(item, bool) or item not in (-1, 1) for item in signs_raw)
    ):
        raise PlannerCalibrationSnapshotError(
            "robot_reference signs must be six +/-1 integers"
        )
    signs = tuple(int(item) for item in signs_raw)

    arm_board = _exact(
        artifacts["arm_board"].payload, {"schema", "transform"}, "arm_board payload"
    )
    if arm_board["schema"] != "rocell.arm_board_payload.v1":
        raise PlannerCalibrationSnapshotError("arm_board payload schema is invalid")
    board_T_world = _transform(arm_board["transform"], "B", "Wv", "arm_board.transform")

    correlation = _exact(
        artifacts["controller_correlation"].payload,
        {
            "schema",
            "model_frame",
            "controller_frame",
            "correlation_model_id",
            "correlation_model_sha256",
            "validation_sample_count",
            "heldout_count",
            "heldout_max_position_error_mm",
            "heldout_max_angle_error_rad",
            "qualified",
        },
        "controller_correlation payload",
    )
    if (
        correlation["schema"] != "rocell.controller_correlation_payload.v1"
        or correlation["model_frame"] != "Wv"
        or correlation["controller_frame"] != "R_ctrl"
    ):
        raise PlannerCalibrationSnapshotError(
            "controller correlation frames are invalid"
        )
    correlation_doc = {
        "model_frame": "Wv",
        "controller_frame": "R_ctrl",
        "correlation_model_id": _identifier(
            correlation["correlation_model_id"], "correlation_model_id"
        ),
        "correlation_model_sha256": _sha256(
            correlation["correlation_model_sha256"], "correlation_model_sha256"
        ),
        "validation_sample_count": _positive_int(
            correlation["validation_sample_count"], "validation_sample_count"
        ),
        "heldout_count": _positive_int(
            correlation["heldout_count"], "controller heldout_count"
        ),
        "heldout_max_position_error_mm": _finite(
            correlation["heldout_max_position_error_mm"],
            "heldout_max_position_error_mm",
            minimum=0.0,
        ),
        "heldout_max_angle_error_rad": _finite(
            correlation["heldout_max_angle_error_rad"],
            "heldout_max_angle_error_rad",
            minimum=0.0,
        ),
    }
    _qualified(correlation["qualified"], "controller_correlation.qualified")

    pose_id, tcp_id = _DEVICE[device]
    device_frame = "keyboard" if device == "keyboard" else "phone_screen"
    pose_schema = f"rocell.{pose_id}_payload.v1"
    pose = _exact(
        artifacts[pose_id].payload,
        {
            "schema",
            "transform",
            "target_map_sha256",
            "device_identity_hash",
            "heldout_max_target_error_mm",
            "qualified",
        },
        f"{pose_id} payload",
    )
    if (
        pose["schema"] != pose_schema
        or _sha256(pose["target_map_sha256"], "target_map_sha256") != target_hash
    ):
        raise PlannerCalibrationSnapshotError(
            f"{pose_id} schema or target map binding is invalid"
        )
    _sha256(pose["device_identity_hash"], "device_identity_hash")
    _finite(
        pose["heldout_max_target_error_mm"], "heldout_max_target_error_mm", minimum=0.0
    )
    _qualified(pose["qualified"], f"{pose_id}.qualified")
    board_T_device = _transform(
        pose["transform"], "B", device_frame, f"{pose_id}.transform"
    )

    tcp_schema = f"rocell.{tcp_id}_payload.v1"
    tcp = _exact(
        artifacts[tcp_id].payload,
        {
            "schema",
            "transform",
            "tool_identity_hash",
            "heldout_max_tip_error_mm",
            "minimum_validated_clearance_mm",
            "qualified",
        },
        f"{tcp_id} payload",
    )
    if tcp["schema"] != tcp_schema:
        raise PlannerCalibrationSnapshotError(f"{tcp_id} payload schema is invalid")
    _sha256(tcp["tool_identity_hash"], "tool_identity_hash")
    _finite(tcp["heldout_max_tip_error_mm"], "heldout_max_tip_error_mm", minimum=0.0)
    _finite(
        tcp["minimum_validated_clearance_mm"],
        "minimum_validated_clearance_mm",
        minimum=0.0,
    )
    _qualified(tcp["qualified"], f"{tcp_id}.qualified")
    hand_T_tool = _transform(tcp["transform"], "G", "T", f"{tcp_id}.transform")

    return PlannerCalibrationSnapshot(
        device=device,
        manifest_id=next(iter(manifest_ids)),
        active_build_id=next(iter(build_ids)),
        artifact_hashes=hashes,
        board_T_vendor_world=board_T_world,
        board_T_device=board_T_device,
        hand_T_tool=hand_T_tool,
        robot_reference_identity={
            "arm_identity_hash": reference["arm_identity_hash"],
            "controller_identity_hash": reference["controller_identity_hash"],
            "firmware_identity_hash": reference["firmware_identity_hash"],
        },
        joint_zero_offsets_rad=zeros,
        joint_lower_rad=lower,
        joint_upper_rad=upper,
        joint_signs=signs,
        controller_correlation=correlation_doc,
        target_map_sha256=target_hash,
    )

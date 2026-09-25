"""Truth-referenced tool-tip geometry for the zero-authority virtual plant.

Contact adjudication must use where the simulated arm *actually* ended up,
not board coordinates copied from the trajectory planner.  This module takes
one achieved six-joint feedback sample, evaluates the reviewed RoArm-M3 URDF,
adds the configured tool along ``hand_tcp`` -Z, and only then transforms the
result into an immutable private board-truth frame::

    Wv_T_tip(q) = Wv_T_hand_tcp(q) * hand_tcp_T_tip
    board_truth_T_tip(q) = inverse(Wv_T_board_truth) * Wv_T_tip(q)

The private truth transform is deliberately omitted from every public evidence
document; only its content digest is exposed.  The calculated tip point and
tool axis are evidence outputs, because the virtual contact model needs those
values.  Nothing here imports an arm transport, creates controller commands,
or grants a physical permit.  All results carry exactly zero virtual authority.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Mapping, Sequence

from rocell.calibration.eye_on_arm_evidence import (
    PINNED_ROARM_M3_KINEMATIC_SHA256,
)
from rocell.geometry.transforms import RigidTransform, Rotation3, Vec3
from rocell.geometry.urdf import JointStateError, UrdfError, UrdfModel
from rocell.kinematics.ik import HAND_TCP_LINK_NAME
from rocell.models.frames import Point3Mm

from ._pinned_model import PinnedModelLoadError, load_pinned_urdf
from .arm_camera_pose import (
    ARM_CAMERA_JOINT_ORDER,
    AchievedJointStateSource,
    AchievedModelJointPositions,
    achieved_joint_sample_sha256,
)
from .runtime_ports import (
    ArmFeedbackSample,
    RuntimeAuthority,
    RuntimeExecutionMode,
    RuntimeInstant,
)
from .virtual_board_truth import (
    HIDDEN_VIRTUAL_BOARD_TRUTH_SCHEMA,
    HiddenVirtualBoardTruth,
)


ACTUAL_CONTACT_GEOMETRY_SCHEMA = "rocell.actual_tool_tip_contact_geometry.v1"
ACTUAL_CONTACT_PROJECTOR_IMPLEMENTATION_ID = (
    "rocell.actual_tool_tip_contact_projector.v1"
)
ACTUAL_CONTACT_SOURCE_KEYS: tuple[str, ...] = (
    "achieved_joint_state",
    "achieved_joint_sample",
    "kinematic_model",
    "controller_joint_contract",
    "tool_geometry",
    "virtual_board_truth",
    "projector_implementation",
)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_MAX_IDENTIFIER_LENGTH = 256
_MAX_IMPLEMENTATION_BYTES = 2 * 1024 * 1024
_MAX_TOOL_LENGTH_MM = 1_000.0
_IMPLEMENTATION_DEPENDENCIES: tuple[str, ...] = (
    "application/actual_contact_geometry.py",
    "application/_pinned_model.py",
    "application/arm_camera_pose.py",
    "application/runtime_ports.py",
    "application/virtual_board_truth.py",
    "geometry/transforms.py",
    "geometry/urdf.py",
    "kinematics/ik.py",
)


class ActualContactGeometryError(ValueError):
    """An achieved state, private truth, model, or evidence record is invalid."""


def _identifier(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > _MAX_IDENTIFIER_LENGTH
        or value != value.strip()
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise ActualContactGeometryError(f"{label} must be bounded clean text")
    return value


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ActualContactGeometryError(
            f"{label} must be a lowercase SHA-256 digest"
        )
    return value


def _finite(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ActualContactGeometryError(f"{label} must be a finite number")
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ActualContactGeometryError(f"{label} must be a finite number")
    return parsed


def _stable_hash(value: object) -> str:
    try:
        payload = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ActualContactGeometryError(
            f"contact geometry is not canonical JSON: {exc}"
        ) from exc
    return hashlib.sha256(payload).hexdigest()


def _instant_dict(instant: RuntimeInstant) -> dict[str, object]:
    return {
        "clock_id": instant.clock_id,
        "tick": instant.tick,
        "tick_period_ns": instant.tick_period_ns,
    }


def _authority_dict(authority: RuntimeAuthority) -> dict[str, object]:
    return {
        "execution_mode": authority.execution_mode.value,
        "hardware_accessed": authority.hardware_accessed,
        "hardware_commands_generated": authority.hardware_commands_generated,
        "live_motion_authorized": authority.live_motion_authorized,
        "physical_contact_authorized": authority.physical_contact_authorized,
        "physical_release_effect": authority.physical_release_effect,
    }


@dataclass(frozen=True, slots=True)
class ActualToolTipContactGeometry:
    """Truth-frame tip point and approach axis derived from achieved joints."""

    joint_sample_id: str
    joint_sequence: int
    joint_observed_at: RuntimeInstant
    tip_position_truth_board_mm: Point3Mm
    hand_tcp_z_axis_truth_board: Vec3
    tool_length_mm: float
    joint_state_sha256: str
    joint_sample_sha256: str
    truth_registration_sha256: str
    kinematic_model_sha256: str
    controller_joint_contract_sha256: str
    tool_geometry_sha256: str
    implementation_sha256: str
    source_hashes: tuple[tuple[str, str], ...]
    authority: RuntimeAuthority = field(
        init=False,
        default_factory=lambda: RuntimeAuthority.zero(RuntimeExecutionMode.VIRTUAL),
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "joint_sample_id", _identifier(self.joint_sample_id, "joint_sample_id")
        )
        if (
            isinstance(self.joint_sequence, bool)
            or not isinstance(self.joint_sequence, int)
            or self.joint_sequence < 0
        ):
            raise ActualContactGeometryError(
                "joint_sequence must be a non-negative integer"
            )
        if not isinstance(self.joint_observed_at, RuntimeInstant):
            raise TypeError("joint_observed_at must be a RuntimeInstant")
        if not isinstance(self.tip_position_truth_board_mm, Point3Mm):
            raise TypeError("tip_position_truth_board_mm must be a Point3Mm")
        if self.tip_position_truth_board_mm.frame != "board":
            raise ActualContactGeometryError(
                "tip position must use the private truth board frame"
            )
        if not isinstance(self.hand_tcp_z_axis_truth_board, Vec3):
            raise TypeError("hand_tcp_z_axis_truth_board must be a Vec3")
        axis_norm = self.hand_tcp_z_axis_truth_board.norm
        if abs(axis_norm - 1.0) > 1e-9:
            raise ActualContactGeometryError(
                "hand_tcp_z_axis_truth_board must be a unit vector"
            )
        tool_length = _finite(self.tool_length_mm, "tool_length_mm")
        if not 0.0 <= tool_length <= _MAX_TOOL_LENGTH_MM:
            raise ActualContactGeometryError(
                f"tool_length_mm must be within [0, {_MAX_TOOL_LENGTH_MM}]"
            )
        object.__setattr__(self, "tool_length_mm", tool_length)
        for field_name in (
            "joint_state_sha256",
            "joint_sample_sha256",
            "truth_registration_sha256",
            "kinematic_model_sha256",
            "controller_joint_contract_sha256",
            "tool_geometry_sha256",
            "implementation_sha256",
        ):
            object.__setattr__(
                self, field_name, _digest(getattr(self, field_name), field_name)
            )
        if self.kinematic_model_sha256 != PINNED_ROARM_M3_KINEMATIC_SHA256:
            raise ActualContactGeometryError(
                "contact geometry must use the reviewed pinned RoArm-M3 model"
            )
        if not isinstance(self.source_hashes, tuple):
            raise ActualContactGeometryError(
                "source_hashes must be an immutable tuple"
            )
        parsed: list[tuple[str, str]] = []
        for index, pair in enumerate(self.source_hashes):
            if not isinstance(pair, tuple) or len(pair) != 2:
                raise ActualContactGeometryError(
                    f"source_hashes[{index}] must be an immutable pair"
                )
            parsed.append(
                (
                    _identifier(pair[0], f"source_hashes[{index}] key"),
                    _digest(pair[1], f"source_hashes[{index}] digest"),
                )
            )
        frozen = tuple(parsed)
        if tuple(key for key, _ in frozen) != ACTUAL_CONTACT_SOURCE_KEYS:
            raise ActualContactGeometryError(
                "source_hashes must use the canonical actual-contact keys"
            )
        expected = {
            "achieved_joint_state": self.joint_state_sha256,
            "achieved_joint_sample": self.joint_sample_sha256,
            "kinematic_model": self.kinematic_model_sha256,
            "controller_joint_contract": self.controller_joint_contract_sha256,
            "tool_geometry": self.tool_geometry_sha256,
            "virtual_board_truth": self.truth_registration_sha256,
            "projector_implementation": self.implementation_sha256,
        }
        source_map = dict(frozen)
        if any(source_map[key] != digest for key, digest in expected.items()):
            raise ActualContactGeometryError(
                "source hashes disagree with the contact geometry record"
            )
        object.__setattr__(self, "source_hashes", frozen)
        if not isinstance(self.authority, RuntimeAuthority) or (
            self.authority.execution_mode is not RuntimeExecutionMode.VIRTUAL
            or not self.authority.is_zero_authority
        ):
            raise ActualContactGeometryError(
                "actual contact geometry must carry exactly virtual zero authority"
            )

    @property
    def can_release_physical_gates(self) -> bool:
        return False

    @property
    def content_hash(self) -> str:
        return _stable_hash(self.to_dict())

    def to_dict(self) -> dict[str, object]:
        point = self.tip_position_truth_board_mm
        axis = self.hand_tcp_z_axis_truth_board
        return {
            "schema": ACTUAL_CONTACT_GEOMETRY_SCHEMA,
            "status": "PROJECTED_FROM_ACHIEVED_JOINTS_AGAINST_PRIVATE_TRUTH",
            "simulation_only": True,
            "can_release_physical_gates": False,
            "planner_board_coordinates_consumed": False,
            "joint_sample": {
                "sample_id": self.joint_sample_id,
                "sequence": self.joint_sequence,
                "observed_at": _instant_dict(self.joint_observed_at),
                "joint_state_sha256": self.joint_state_sha256,
                "joint_sample_sha256": self.joint_sample_sha256,
            },
            "tip_position_truth_board_mm": {
                "frame": point.frame,
                "x": point.x,
                "y": point.y,
                "z": point.z,
            },
            "hand_tcp_z_axis_truth_board": [axis.x, axis.y, axis.z],
            "tool": {
                "length_mm": self.tool_length_mm,
                "attachment": "hand_tcp_NEGATIVE_Z",
                "geometry_sha256": self.tool_geometry_sha256,
            },
            "private_truth": {
                "registration_sha256": self.truth_registration_sha256,
                "transform_serialized": False,
            },
            "kinematic_model_sha256": self.kinematic_model_sha256,
            "controller_joint_contract_sha256": (
                self.controller_joint_contract_sha256
            ),
            "source_hashes": dict(self.source_hashes),
            "implementation": {
                "id": ACTUAL_CONTACT_PROJECTOR_IMPLEMENTATION_ID,
                "sha256": self.implementation_sha256,
            },
            "authority": _authority_dict(self.authority),
        }


class ActualToolTipContactProjector:
    """Evaluate achieved FK against one immutable private virtual truth pose."""

    __slots__ = (
        "_implementation_sha256",
        "_model",
        "_model_byte_count",
        "_joint_bounds_rad",
        "_controller_joint_contract_sha256",
        "_tool_geometry_sha256",
        "_tool_length_mm",
        "_truth",
    )

    def __init__(
        self,
        *,
        model_path: str | Path,
        tool_length_mm: object,
        truth: HiddenVirtualBoardTruth,
        joint_bounds_rad: Mapping[str, Sequence[float]],
        gripper_bounds_rad: Sequence[float],
    ) -> None:
        if not isinstance(truth, HiddenVirtualBoardTruth):
            raise TypeError("truth must be a HiddenVirtualBoardTruth")
        length = _finite(tool_length_mm, "tool_length_mm")
        if not 0.0 <= length <= _MAX_TOOL_LENGTH_MM:
            raise ActualContactGeometryError(
                f"tool_length_mm must be within [0, {_MAX_TOOL_LENGTH_MM}]"
            )
        try:
            loaded = load_pinned_urdf(
                model_path, PINNED_ROARM_M3_KINEMATIC_SHA256
            )
        except (PinnedModelLoadError, TypeError, ValueError) as exc:
            raise ActualContactGeometryError(
                f"could not load reviewed RoArm-M3 model: {exc}"
            ) from exc
        self._validate_model(loaded.model)
        self._model = loaded.model
        self._model_byte_count = loaded.byte_count
        self._joint_bounds_rad = self._validate_controller_bounds(
            loaded.model,
            joint_bounds_rad,
            gripper_bounds_rad,
        )
        self._controller_joint_contract_sha256 = _stable_hash(
            {
                "schema": "rocell.virtual_contact_controller_joint_contract.v1",
                "positions_unit": "rad",
                "joint_bounds_rad": {
                    name: list(self._joint_bounds_rad[name])
                    for name in ARM_CAMERA_JOINT_ORDER
                },
            }
        )
        self._tool_length_mm = length
        self._truth = truth
        self._tool_geometry_sha256 = _stable_hash(
            {
                "schema": "rocell.virtual_tool_geometry.v1",
                "parent_frame": HAND_TCP_LINK_NAME,
                "child_frame": "tool_tip",
                "translation_mm": [0.0, 0.0, -length],
                "rotation_row_major": list(Rotation3.identity().matrix),
            }
        )
        self._implementation_sha256 = self._implementation_bundle_hash()

    @staticmethod
    def _validate_model(model: UrdfModel) -> None:
        if model.name != "roarm_m3" or model.root_link != "world":
            raise ActualContactGeometryError(
                "kinematic model must be the RoArm-M3 world-root model"
            )
        if HAND_TCP_LINK_NAME not in model.link_names:
            raise ActualContactGeometryError(
                "kinematic model is missing the hand_tcp planning link"
            )
        if set(model.movable_joint_names) != set(ARM_CAMERA_JOINT_ORDER):
            raise ActualContactGeometryError(
                "kinematic model movable joints differ from the six-joint contract"
            )

    @staticmethod
    def _validate_controller_bounds(
        model: UrdfModel,
        arm_bounds: Mapping[str, Sequence[float]],
        gripper_bounds: Sequence[float],
    ) -> dict[str, tuple[float, float]]:
        if not isinstance(arm_bounds, Mapping) or set(arm_bounds) != set(
            ARM_CAMERA_JOINT_ORDER[:-1]
        ):
            raise ActualContactGeometryError(
                "joint_bounds_rad must cover exactly the five arm joints"
            )
        combined: dict[str, Sequence[float]] = dict(arm_bounds)
        combined[ARM_CAMERA_JOINT_ORDER[-1]] = gripper_bounds
        parsed: dict[str, tuple[float, float]] = {}
        for name in ARM_CAMERA_JOINT_ORDER:
            pair = combined[name]
            if not isinstance(pair, (tuple, list)) or len(pair) != 2:
                raise ActualContactGeometryError(
                    f"controller bounds for {name!r} must be a pair"
                )
            lower = _finite(pair[0], f"{name} controller lower bound")
            upper = _finite(pair[1], f"{name} controller upper bound")
            if lower >= upper:
                raise ActualContactGeometryError(
                    f"controller bounds for {name!r} must increase strictly"
                )
            limit = model.joint(name).limit
            assert limit is not None and limit.lower is not None and limit.upper is not None
            if lower < limit.lower.value or upper > limit.upper.value:
                raise ActualContactGeometryError(
                    f"controller bounds for {name!r} leave the pinned URDF limits"
                )
            parsed[name] = (lower, upper)
        return parsed

    @staticmethod
    def _read_implementation_source(path: Path) -> bytes:
        try:
            with path.open("rb") as stream:
                payload = stream.read(_MAX_IMPLEMENTATION_BYTES + 1)
        except OSError as exc:
            raise ActualContactGeometryError(
                f"could not read implementation dependency {path}"
            ) from exc
        if len(payload) > _MAX_IMPLEMENTATION_BYTES:
            raise ActualContactGeometryError(
                f"implementation dependency exceeds {_MAX_IMPLEMENTATION_BYTES} bytes"
            )
        return payload

    @classmethod
    def _implementation_bundle_hash(cls) -> str:
        rocell_root = Path(__file__).resolve(strict=True).parents[1]
        hashes = {
            relative_path: hashlib.sha256(
                cls._read_implementation_source(rocell_root / relative_path)
            ).hexdigest()
            for relative_path in _IMPLEMENTATION_DEPENDENCIES
        }
        return _stable_hash(
            {
                "schema": "rocell.actual_contact_projector_bundle.v1",
                "sources": hashes,
            }
        )

    @property
    def truth_registration_sha256(self) -> str:
        return self._truth.content_hash

    @property
    def tool_geometry_sha256(self) -> str:
        return self._tool_geometry_sha256

    @property
    def controller_joint_contract_sha256(self) -> str:
        return self._controller_joint_contract_sha256

    @property
    def implementation_sha256(self) -> str:
        return self._implementation_sha256

    @property
    def model_byte_count(self) -> int:
        return self._model_byte_count

    def project(
        self,
        sample: ArmFeedbackSample[AchievedModelJointPositions],
    ) -> ActualToolTipContactGeometry:
        """Project only achieved feedback; no planner result is an input."""

        if not isinstance(sample, ArmFeedbackSample):
            raise TypeError("sample must be an ArmFeedbackSample")
        if not isinstance(sample.feedback, AchievedModelJointPositions):
            raise TypeError("sample feedback must be AchievedModelJointPositions")
        if sample.stale:
            raise ActualContactGeometryError(
                "stale achieved joint feedback cannot adjudicate contact"
            )
        if sample.feedback.source_kind is not AchievedJointStateSource.VIRTUAL_PLANT:
            raise ActualContactGeometryError(
                "contact truth accepts only achieved VIRTUAL_PLANT joint state"
            )
        for name, position in sample.feedback.positions:
            lower, upper = self._joint_bounds_rad[name]
            if not lower <= position.value <= upper:
                raise ActualContactGeometryError(
                    f"achieved joint {name!r} leaves the controller/URDF intersection"
                )
        try:
            root_transforms = self._model.forward_kinematics(
                sample.feedback.positions_by_name
            )
        except (JointStateError, UrdfError, TypeError, ValueError) as exc:
            raise ActualContactGeometryError(
                f"achieved joint state failed contact FK: {exc}"
            ) from exc

        world_T_hand = root_transforms[HAND_TCP_LINK_NAME]
        # The reviewed frame contract names the URDF root ``Wv`` in the
        # virtual plant.  This is a token relabel only; R_ctrl is unrelated.
        Wv_T_hand = RigidTransform(
            "Wv",
            HAND_TCP_LINK_NAME,
            world_T_hand.rotation,
            world_T_hand.translation_mm,
        )
        hand_T_tip = RigidTransform(
            HAND_TCP_LINK_NAME,
            "tool_tip",
            Rotation3.identity(),
            Vec3(0.0, 0.0, -self._tool_length_mm),
        )
        Wv_T_tip = Wv_T_hand.compose(hand_T_tip)
        board_truth_T_tip = self._truth.board_T_achieved(Wv_T_tip)
        axis_truth_board = board_truth_T_tip.rotation.apply(Vec3(0.0, 0.0, 1.0))
        tip = board_truth_T_tip.translation_mm

        joint_state_hash = sample.feedback.content_hash
        joint_sample_hash = achieved_joint_sample_sha256(sample)
        source_hashes = (
            ("achieved_joint_state", joint_state_hash),
            ("achieved_joint_sample", joint_sample_hash),
            ("kinematic_model", PINNED_ROARM_M3_KINEMATIC_SHA256),
            (
                "controller_joint_contract",
                self.controller_joint_contract_sha256,
            ),
            ("tool_geometry", self.tool_geometry_sha256),
            ("virtual_board_truth", self.truth_registration_sha256),
            ("projector_implementation", self.implementation_sha256),
        )
        return ActualToolTipContactGeometry(
            joint_sample_id=sample.sample_id,
            joint_sequence=sample.sequence,
            joint_observed_at=sample.observed_at,
            tip_position_truth_board_mm=Point3Mm(
                self._truth.board_frame, tip.x, tip.y, tip.z
            ),
            hand_tcp_z_axis_truth_board=axis_truth_board,
            tool_length_mm=self._tool_length_mm,
            joint_state_sha256=joint_state_hash,
            joint_sample_sha256=joint_sample_hash,
            truth_registration_sha256=self.truth_registration_sha256,
            kinematic_model_sha256=PINNED_ROARM_M3_KINEMATIC_SHA256,
            controller_joint_contract_sha256=(
                self.controller_joint_contract_sha256
            ),
            tool_geometry_sha256=self.tool_geometry_sha256,
            implementation_sha256=self.implementation_sha256,
            source_hashes=source_hashes,
        )


__all__ = [
    "ACTUAL_CONTACT_GEOMETRY_SCHEMA",
    "ACTUAL_CONTACT_PROJECTOR_IMPLEMENTATION_ID",
    "ACTUAL_CONTACT_SOURCE_KEYS",
    "HIDDEN_VIRTUAL_BOARD_TRUTH_SCHEMA",
    "ActualContactGeometryError",
    "ActualToolTipContactGeometry",
    "ActualToolTipContactProjector",
    "HiddenVirtualBoardTruth",
]

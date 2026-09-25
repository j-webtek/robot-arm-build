from __future__ import annotations

from dataclasses import replace
import hashlib
import inspect
import json
from pathlib import Path

import pytest

from rocell.application.actual_contact_geometry import (
    ACTUAL_CONTACT_SOURCE_KEYS,
    ActualContactGeometryError,
    ActualToolTipContactProjector,
    HiddenVirtualBoardTruth,
)
from rocell.application.arm_camera_pose import (
    ARM_CAMERA_JOINT_ORDER,
    AchievedJointStateSource,
    AchievedModelJointPositions,
    achieved_joint_sample_sha256,
)
from rocell.application.runtime_ports import (
    ArmFeedbackSample,
    RuntimeExecutionMode,
    RuntimeInstant,
)
from rocell.application.virtual_board_truth import VirtualBoardTruthError
from rocell.calibration.eye_on_arm_evidence import (
    PINNED_ROARM_M3_KINEMATIC_SHA256,
)
from rocell.geometry.transforms import RigidTransform, Rotation3, Vec3
from rocell.geometry.urdf import JointPosition, UrdfModel
from rocell.kinematics.ik import HAND_TCP_LINK_NAME


SOFTWARE_ROOT = Path(__file__).resolve().parents[2]
URDF_PATH = SOFTWARE_ROOT / "models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf"


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _state(
    values: tuple[float, ...] = (0.10, 0.20, 1.00, -0.10, 0.15, 0.70),
) -> AchievedModelJointPositions:
    return AchievedModelJointPositions(
        positions=tuple(
            (name, JointPosition.radians(value))
            for name, value in zip(ARM_CAMERA_JOINT_ORDER, values)
        ),
        source_kind=AchievedJointStateSource.VIRTUAL_PLANT,
        source_state_sha256=_digest(values),
    )


def _sample(
    state: AchievedModelJointPositions | None = None,
    *,
    stale: bool = False,
) -> ArmFeedbackSample[AchievedModelJointPositions]:
    return ArmFeedbackSample(
        sample_id="achieved-contact-0012",
        observed_at=RuntimeInstant(
            clock_id="virtual_workcell_clock",
            tick=120,
            tick_period_ns=1_000_000,
        ),
        sequence=12,
        feedback=state if state is not None else _state(),
        stale=stale,
    )


def _truth(
    *,
    translation_mm: Vec3 = Vec3(25.0, -18.0, 9.0),
    yaw_rad: float = 0.08,
) -> tuple[HiddenVirtualBoardTruth, RigidTransform]:
    transform = RigidTransform(
        "Wv",
        "board",
        Rotation3.from_rpy(0.0, 0.0, yaw_rad),
        translation_mm,
    )
    return HiddenVirtualBoardTruth(transform), transform


def _projector(
    truth: HiddenVirtualBoardTruth | None = None,
    *,
    tool_length_mm: float = 113.0,
) -> ActualToolTipContactProjector:
    selected_truth = truth if truth is not None else _truth()[0]
    model = UrdfModel.from_file(URDF_PATH)
    bounds = {
        name: (
            model.joint(name).limit.lower.value,  # type: ignore[union-attr]
            model.joint(name).limit.upper.value,  # type: ignore[union-attr]
        )
        for name in ARM_CAMERA_JOINT_ORDER
    }
    return ActualToolTipContactProjector(
        model_path=URDF_PATH,
        tool_length_mm=tool_length_mm,
        truth=selected_truth,
        joint_bounds_rad={name: bounds[name] for name in ARM_CAMERA_JOINT_ORDER[:-1]},
        gripper_bounds_rad=bounds[ARM_CAMERA_JOINT_ORDER[-1]],
    )


def test_actual_tip_and_axis_come_from_pinned_achieved_fk_then_private_truth() -> None:
    truth, Wv_T_board = _truth()
    sample = _sample()
    projector = _projector(truth)
    result = projector.project(sample)

    model = UrdfModel.from_xml(
        URDF_PATH.read_text(encoding="utf-8"), source_name=str(URDF_PATH)
    )
    world_T_hand = model.forward_kinematics(
        sample.feedback.positions_by_name
    )[HAND_TCP_LINK_NAME]
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
        Vec3(0.0, 0.0, -113.0),
    )
    expected = Wv_T_board.inverse().compose(Wv_T_hand.compose(hand_T_tip))
    expected_axis = expected.rotation.apply(Vec3(0.0, 0.0, 1.0))

    point = result.tip_position_truth_board_mm
    assert (point.x, point.y, point.z) == pytest.approx(
        (
            expected.translation_mm.x,
            expected.translation_mm.y,
            expected.translation_mm.z,
        ),
        abs=1e-12,
    )
    assert point.frame == "board"
    assert result.hand_tcp_z_axis_truth_board.almost_equal(
        expected_axis, absolute_tolerance=1e-12
    )
    assert result.joint_state_sha256 == sample.feedback.content_hash
    assert result.joint_sample_sha256 == achieved_joint_sample_sha256(sample)
    assert result.kinematic_model_sha256 == PINNED_ROARM_M3_KINEMATIC_SHA256
    assert tuple(dict(result.source_hashes)) == ACTUAL_CONTACT_SOURCE_KEYS
    assert projector.model_byte_count == URDF_PATH.stat().st_size


def test_truth_is_immutable_opaque_evidence_and_result_has_zero_authority() -> None:
    truth, transform = _truth(translation_mm=Vec3(91.25, -47.5, 8.75))
    result = _projector(truth).project(_sample())

    # Dataclass freezing prevents replacing the plant truth after construction.
    with pytest.raises((AttributeError, TypeError)):
        truth._Wv_T_board = RigidTransform.identity("Wv")  # type: ignore[misc]

    truth_document = truth.to_dict()
    result_document = result.to_dict()
    private_truth_document = result_document["private_truth"]
    assert isinstance(private_truth_document, dict)
    serialized_truth = json.dumps(truth_document, sort_keys=True)
    serialized_result = json.dumps(result_document, sort_keys=True)
    assert repr(truth) == "HiddenVirtualBoardTruth()"
    assert truth_document["truth_transform_serialized"] is False
    assert private_truth_document["transform_serialized"] is False
    assert result_document["planner_board_coordinates_consumed"] is False
    # Neither public document contains the private transform's distinctive
    # translation or a Wv_T_board field.
    assert str(transform.translation_mm.x) not in serialized_truth
    assert "Wv_T_board" not in serialized_truth
    assert "Wv_T_board" not in serialized_result
    assert result.authority.execution_mode is RuntimeExecutionMode.VIRTUAL
    assert result.authority.is_zero_authority
    assert result.can_release_physical_gates is False
    assert result.content_hash == _projector(truth).project(_sample()).content_hash


def test_same_achieved_joints_move_in_truth_coordinates_when_board_truth_moves() -> None:
    sample = _sample()
    first_truth, _ = _truth(translation_mm=Vec3.zero(), yaw_rad=0.0)
    second_truth, _ = _truth(
        translation_mm=Vec3(12.0, -3.0, 2.5), yaw_rad=0.0
    )
    first = _projector(first_truth).project(sample)
    second = _projector(second_truth).project(sample)
    first_point = first.tip_position_truth_board_mm
    second_point = second.tip_position_truth_board_mm

    # With equal orientation, moving the real board +d in Wv makes the fixed
    # achieved tool appear -d in board coordinates.
    assert (
        second_point.x - first_point.x,
        second_point.y - first_point.y,
        second_point.z - first_point.z,
    ) == pytest.approx((-12.0, 3.0, -2.5), abs=1e-12)
    assert first.truth_registration_sha256 != second.truth_registration_sha256
    assert first.content_hash != second.content_hash


def test_project_contract_cannot_receive_planner_reported_board_geometry() -> None:
    projector = _projector()
    parameters = tuple(inspect.signature(projector.project).parameters)
    assert parameters == ("sample",)

    with pytest.raises(TypeError):
        projector.project(  # type: ignore[call-arg]
            _sample(),
            planner_tip_position_board_mm=(1.0, 2.0, 3.0),
        )


def test_stale_feedback_and_modified_model_fail_closed(tmp_path: Path) -> None:
    with pytest.raises(
        ActualContactGeometryError,
        match="stale achieved joint feedback",
    ):
        _projector().project(_sample(stale=True))

    modified_model = tmp_path / "modified.urdf"
    modified_model.write_bytes(URDF_PATH.read_bytes() + b"\n")
    with pytest.raises(
        ActualContactGeometryError,
        match="pinned model byte hash mismatch",
    ):
        ActualToolTipContactProjector(
            model_path=modified_model,
            tool_length_mm=113.0,
            truth=_truth()[0],
            joint_bounds_rad={
                name: (-3.14, 3.14) for name in ARM_CAMERA_JOINT_ORDER[:-1]
            },
            gripper_bounds_rad=(0.0, 3.14),
        )


def test_frames_lengths_and_result_source_hashes_are_strict() -> None:
    with pytest.raises(VirtualBoardTruthError, match="exactly Wv_T_board"):
        HiddenVirtualBoardTruth(RigidTransform.identity("Wv"))
    with pytest.raises(ActualContactGeometryError, match="tool_length_mm"):
        _projector(tool_length_mm=-0.01)
    with pytest.raises(ActualContactGeometryError, match="tool_length_mm"):
        _projector(tool_length_mm=1_000.01)

    result = _projector().project(_sample())
    tampered = tuple(
        (key, _digest("different")) if key == "virtual_board_truth" else (key, value)
        for key, value in result.source_hashes
    )
    with pytest.raises(ActualContactGeometryError, match="source hashes disagree"):
        replace(result, source_hashes=tampered)

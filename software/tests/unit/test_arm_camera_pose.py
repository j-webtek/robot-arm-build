from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest

from rocell.application.arm_camera_pose import (
    ARM_CAMERA_BINDING_SOURCE_KEYS,
    ARM_CAMERA_JOINT_ORDER,
    AchievedJointStateSource,
    AchievedModelJointPositions,
    ArmCameraKinematicBinding,
    ArmCameraOpticalPose,
    ArmCameraPoseError,
    ArmCameraPoseProjector,
    ArmCameraTransformSource,
    achieved_joint_sample_sha256,
)
from rocell.application.runtime_ports import (
    ArmFeedbackSample,
    RuntimeAuthority,
    RuntimeExecutionMode,
    RuntimeInstant,
)
from rocell.calibration.eye_on_arm_evidence import (
    PINNED_ROARM_M3_KINEMATIC_SHA256,
)
from rocell.geometry.transforms import RigidTransform, Vec3
from rocell.geometry.urdf import JointPosition, UrdfModel


SOFTWARE_ROOT = Path(__file__).resolve().parents[2]
URDF_PATH = SOFTWARE_ROOT / "models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf"
IMPLEMENTATION_PATH = (
    SOFTWARE_ROOT / "src/rocell/application/arm_camera_pose.py"
)
IMPLEMENTATION_DEPENDENCIES = (
    "application/arm_camera_pose.py",
    "application/runtime_ports.py",
    "geometry/transforms.py",
    "geometry/urdf.py",
    "kinematics/ik.py",
)


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _implementation_bundle_hash() -> str:
    rocell_root = SOFTWARE_ROOT / "src/rocell"
    value = {
        "schema": "rocell.arm_camera_projector_implementation_bundle.v1",
        "sources": {
            relative_path: hashlib.sha256(
                (rocell_root / relative_path).read_bytes()
            ).hexdigest()
            for relative_path in IMPLEMENTATION_DEPENDENCIES
        },
    }
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _binding(
    *,
    carrier_source: ArmCameraTransformSource = ArmCameraTransformSource.SYNTHETIC_FIXTURE,
    extrinsic_source: ArmCameraTransformSource = ArmCameraTransformSource.SYNTHETIC_FIXTURE,
) -> ArmCameraKinematicBinding:
    hashes = {
        "arm_frame_contract": _digest("frame-contract"),
        "camera_manifest": _digest("camera-manifest"),
        "carrier_kinematic_model": PINNED_ROARM_M3_KINEMATIC_SHA256,
        "carrier_registration": _digest("carrier-registration"),
        "eye_on_arm_extrinsic": _digest("eye-on-arm-extrinsic"),
        "joint_coordinate_binding": _digest("joint-coordinate-binding"),
    }
    return ArmCameraKinematicBinding(
        link2_T_E=RigidTransform.from_rpy_translation_mm(
            "link2",
            "E",
            translation_mm=Vec3(18.0, -9.0, 27.0),
            roll_rad=0.07,
            pitch_rad=-0.04,
            yaw_rad=0.03,
        ),
        E_T_C_arm=RigidTransform.from_rpy_translation_mm(
            "E",
            "C_arm",
            translation_mm=Vec3(31.0, -10.0, 46.0),
            roll_rad=0.10,
            pitch_rad=-0.18,
            yaw_rad=0.14,
        ),
        carrier_source_kind=carrier_source,
        extrinsic_source_kind=extrinsic_source,
        source_hashes=tuple((key, hashes[key]) for key in ARM_CAMERA_BINDING_SOURCE_KEYS),
    )


def _joint_state(
    values: tuple[float, ...] = (0.10, 0.20, 1.00, -0.10, 0.15, 0.70),
    *,
    source_hash: str | None = None,
) -> AchievedModelJointPositions:
    assert len(values) == len(ARM_CAMERA_JOINT_ORDER)
    return AchievedModelJointPositions(
        positions=tuple(
            (name, JointPosition.radians(value))
            for name, value in zip(ARM_CAMERA_JOINT_ORDER, values)
        ),
        source_kind=AchievedJointStateSource.VIRTUAL_PLANT,
        source_state_sha256=(
            source_hash
            if source_hash is not None
            else _digest(json.dumps(values, separators=(",", ":")))
        ),
    )


def _sample(
    state: AchievedModelJointPositions | None = None,
    *,
    sample_id: str = "achieved-hover-0007",
    sequence: int = 7,
    tick: int = 103,
    stale: bool = False,
) -> ArmFeedbackSample[AchievedModelJointPositions]:
    return ArmFeedbackSample(
        sample_id=sample_id,
        observed_at=RuntimeInstant(
            clock_id="virtual_workcell_clock",
            tick=tick,
            tick_period_ns=None,
        ),
        sequence=sequence,
        feedback=state if state is not None else _joint_state(),
        stale=stale,
    )


def _projector(
    binding: ArmCameraKinematicBinding | None = None,
) -> ArmCameraPoseProjector:
    return ArmCameraPoseProjector(
        model_path=URDF_PATH,
        binding=binding if binding is not None else _binding(),
    )


def test_projector_composes_exact_reviewed_frame_chain_and_hashes_sources() -> None:
    binding = _binding()
    sample = _sample()
    projector = _projector(binding)
    pose = projector.project(sample)

    model = UrdfModel.from_xml(
        URDF_PATH.read_text(encoding="utf-8"), source_name=str(URDF_PATH)
    )
    world_T_link2 = model.forward_kinematics(
        sample.feedback.positions_by_name
    )["link2"]
    Wv_T_link2 = RigidTransform(
        "Wv",
        "link2",
        world_T_link2.rotation,
        world_T_link2.translation_mm,
    )
    expected = Wv_T_link2.compose(binding.link2_T_E).compose(binding.E_T_C_arm)

    assert pose.Wv_T_C_arm.almost_equal(expected, absolute_tolerance=1e-12)
    assert pose.Wv_T_C_arm.parent_frame == "Wv"
    assert pose.Wv_T_C_arm.child_frame == "C_arm"
    assert pose.joint_observed_at is sample.observed_at
    assert pose.joint_state_sha256 == sample.feedback.content_hash
    assert pose.joint_sample_sha256 == achieved_joint_sample_sha256(sample)
    assert pose.binding_sha256 == binding.binding_hash
    assert pose.source_hashes_by_name["carrier_kinematic_model"] == (
        PINNED_ROARM_M3_KINEMATIC_SHA256
    )
    assert IMPLEMENTATION_PATH.is_file()
    assert projector.implementation_sha256 == _implementation_bundle_hash()
    assert pose.authority == RuntimeAuthority.zero(RuntimeExecutionMode.VIRTUAL)
    assert pose.can_release_physical_gates is False
    assert "R_ctrl" not in json.dumps(pose.to_dict(), sort_keys=True)

    repeated = projector.project(sample)
    assert repeated == pose
    assert repeated.content_hash == pose.content_hash


def test_link2_camera_moves_with_upstream_joints_only() -> None:
    projector = _projector()
    baseline_values = (0.10, 0.20, 1.00, -0.10, 0.15, 0.70)
    baseline = projector.project(_sample(_joint_state(baseline_values))).Wv_T_C_arm

    for index, changed_value in ((0, 0.30), (1, 0.40)):
        values = list(baseline_values)
        values[index] = changed_value
        changed = projector.project(
            _sample(_joint_state(tuple(values)), sample_id=f"upstream-{index}")
        ).Wv_T_C_arm
        assert not changed.almost_equal(baseline, absolute_tolerance=1e-12)

    # The holder is on link2.  Elbow, wrist, roll, and gripper are downstream,
    # so changing only those joints must not spuriously move the camera.
    for index, changed_value in ((2, 1.20), (3, 0.10), (4, -0.15), (5, 0.90)):
        values = list(baseline_values)
        values[index] = changed_value
        changed = projector.project(
            _sample(_joint_state(tuple(values)), sample_id=f"downstream-{index}")
        ).Wv_T_C_arm
        assert changed.almost_equal(baseline, absolute_tolerance=1e-12)


def test_joint_sample_hash_binds_envelope_without_equating_sequence_and_tick() -> None:
    state = _joint_state()
    first = _sample(state, sequence=7, tick=103)
    # Runtime feedback sequence and clock tick are independent domains.
    assert first.sequence != first.observed_at.tick
    hashes = {
        achieved_joint_sample_sha256(first),
        achieved_joint_sample_sha256(_sample(state, sequence=8, tick=103)),
        achieved_joint_sample_sha256(_sample(state, sequence=7, tick=104)),
        achieved_joint_sample_sha256(
            _sample(state, sequence=7, tick=103, sample_id="another-sample")
        ),
        achieved_joint_sample_sha256(_sample(state, sequence=7, tick=103, stale=True)),
    }
    assert len(hashes) == 5


def test_stale_or_wrong_feedback_type_is_rejected() -> None:
    projector = _projector()
    with pytest.raises(ArmCameraPoseError, match="stale"):
        projector.project(_sample(stale=True))

    wrong = ArmFeedbackSample(
        sample_id="wrong-feedback",
        observed_at=RuntimeInstant("virtual_workcell_clock", 1),
        sequence=1,
        feedback=(0.0,),
    )
    with pytest.raises(TypeError, match="AchievedModelJointPositions"):
        projector.project(wrong)  # type: ignore[arg-type]


def test_joint_record_rejects_wrong_order_units_and_model_limits() -> None:
    state = _joint_state()
    with pytest.raises(ArmCameraPoseError, match="exact six-joint"):
        replace(state, positions=state.positions[:-1])
    with pytest.raises(ArmCameraPoseError, match="exact six-joint"):
        replace(state, positions=(state.positions[1], state.positions[0], *state.positions[2:]))
    with pytest.raises(ArmCameraPoseError, match="typed radians"):
        replace(
            state,
            positions=(
                (ARM_CAMERA_JOINT_ORDER[0], JointPosition.millimetres(1.0)),
                *state.positions[1:],
            ),
        )

    outside_limit = _joint_state((0.10, 3.00, 1.00, -0.10, 0.15, 0.70))
    with pytest.raises(ArmCameraPoseError, match="failed FK"):
        _projector().project(_sample(outside_limit))


def test_binding_rejects_wrong_frames_hash_order_and_model_pin() -> None:
    binding = _binding()
    with pytest.raises(ArmCameraPoseError, match="link2_T_E"):
        replace(
            binding,
            link2_T_E=RigidTransform.from_rpy_translation_mm(
                "world", "E", translation_mm=Vec3.zero()
            ),
        )
    with pytest.raises(ArmCameraPoseError, match="E_T_C_arm"):
        replace(
            binding,
            E_T_C_arm=RigidTransform.from_rpy_translation_mm(
                "E", "camera_optical", translation_mm=Vec3.zero()
            ),
        )
    with pytest.raises(ArmCameraPoseError, match="canonical keys"):
        replace(binding, source_hashes=tuple(reversed(binding.source_hashes)))

    changed_hashes = list(binding.source_hashes)
    model_index = ARM_CAMERA_BINDING_SOURCE_KEYS.index("carrier_kinematic_model")
    changed_hashes[model_index] = ("carrier_kinematic_model", _digest("other-model"))
    with pytest.raises(ArmCameraPoseError, match="reviewed pinned"):
        replace(binding, source_hashes=tuple(changed_hashes))


def test_projector_hash_checks_exact_model_bytes(tmp_path: Path) -> None:
    changed_model = tmp_path / "changed.urdf"
    changed_model.write_bytes(URDF_PATH.read_bytes() + b"\n")
    with pytest.raises(ArmCameraPoseError, match="do not match binding hash"):
        ArmCameraPoseProjector(model_path=changed_model, binding=_binding())


def test_calibration_artifact_provenance_does_not_change_virtual_authority() -> None:
    binding = _binding(
        carrier_source=ArmCameraTransformSource.CALIBRATION_ARTIFACT,
        extrinsic_source=ArmCameraTransformSource.CALIBRATION_ARTIFACT,
    )
    pose = _projector(binding).project(_sample())
    assert binding.carrier_source_kind is ArmCameraTransformSource.CALIBRATION_ARTIFACT
    assert binding.extrinsic_source_kind is ArmCameraTransformSource.CALIBRATION_ARTIFACT
    assert binding.authority == RuntimeAuthority.zero(RuntimeExecutionMode.VIRTUAL)
    assert pose.authority == RuntimeAuthority.zero(RuntimeExecutionMode.VIRTUAL)

    physical_claim = RuntimeAuthority(
        execution_mode=RuntimeExecutionMode.PHYSICAL,
        hardware_accessed=False,
        hardware_commands_generated=0,
        live_motion_authorized=False,
        physical_contact_authorized=False,
        physical_release_effect="NONE",
    )
    with pytest.raises(ValueError, match="init=False"):
        replace(pose, authority=physical_claim)


def test_records_round_trip_strictly_and_reject_nested_tampering() -> None:
    state = _joint_state()
    binding = _binding()
    pose = _projector(binding).project(_sample(state))

    assert AchievedModelJointPositions.from_dict(state.to_dict()) == state
    assert ArmCameraKinematicBinding.from_dict(binding.to_dict()) == binding
    assert ArmCameraOpticalPose.from_dict(pose.to_dict()) == pose

    state_document = deepcopy(state.to_dict())
    state_document["positions_rad"][0]["position_rad"] = float("nan")  # type: ignore[index]
    with pytest.raises(ArmCameraPoseError, match="finite"):
        AchievedModelJointPositions.from_dict(state_document)

    binding_document = deepcopy(binding.to_dict())
    binding_document["link2_T_E"]["to_frame"] = "world"  # type: ignore[index]
    with pytest.raises(ArmCameraPoseError, match="link2_T_E"):
        ArmCameraKinematicBinding.from_dict(binding_document)

    pose_document = deepcopy(pose.to_dict())
    pose_document["source_hashes"]["achieved_joint_state"] = _digest("tamper")  # type: ignore[index]
    with pytest.raises(ArmCameraPoseError, match="disagree"):
        ArmCameraOpticalPose.from_dict(pose_document)

    authority_document = deepcopy(pose.to_dict())
    authority_document["authority"]["live_motion_authorized"] = True  # type: ignore[index]
    with pytest.raises(ArmCameraPoseError, match="authority"):
        ArmCameraOpticalPose.from_dict(authority_document)

    boolean_count_document = deepcopy(pose.to_dict())
    boolean_count_document["authority"]["hardware_commands_generated"] = False  # type: ignore[index]
    with pytest.raises(ArmCameraPoseError, match="integer zero"):
        ArmCameraOpticalPose.from_dict(boolean_count_document)

    extra_document = deepcopy(pose.to_dict())
    extra_document["unexpected"] = False
    with pytest.raises(ArmCameraPoseError, match="keys differ"):
        ArmCameraOpticalPose.from_dict(extra_document)


def test_pose_rejects_redundant_hash_or_frame_tampering() -> None:
    pose = _projector().project(_sample())
    source_hashes = list(pose.source_hashes)
    index = next(
        index
        for index, (name, _) in enumerate(source_hashes)
        if name == "projector_implementation"
    )
    source_hashes[index] = ("projector_implementation", _digest("tamper"))
    with pytest.raises(ArmCameraPoseError, match="disagree"):
        replace(pose, source_hashes=tuple(source_hashes))
    with pytest.raises(ArmCameraPoseError, match="Wv_T_C_arm"):
        replace(
            pose,
            Wv_T_C_arm=RigidTransform(
                "world",
                "C_arm",
                pose.Wv_T_C_arm.rotation,
                pose.Wv_T_C_arm.translation_mm,
            ),
        )

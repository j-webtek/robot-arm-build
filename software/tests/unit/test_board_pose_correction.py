"""Focused contracts for the bounded board-pose correction decision layer."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import math

import pytest

from rocell.application.board_pose_correction import (
    ARM_CAMERA_BOARD_MEASUREMENT_SCHEMA,
    BOARD_POSE_CORRECTION_DECISION_SCHEMA,
    BOARD_POSE_CORRECTION_POLICY_SCHEMA,
    BOARD_REGISTRATION_SCHEMA,
    ArmCameraBoardMeasurement,
    BoardPoseCorrectionError,
    BoardPoseCorrectionPolicy,
    BoardPoseCorrectionStatus,
    BoardRegistration,
    decide_board_pose_correction,
)
from rocell.geometry.transforms import RigidTransform, Vec3
from rocell.vision.camera import TimestampQuality


SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64


def _transform(
    parent: str,
    child: str,
    *,
    xyz: tuple[float, float, float] = (0.0, 0.0, 0.0),
    roll: float = 0.0,
    pitch: float = 0.0,
    yaw: float = 0.0,
) -> RigidTransform:
    return RigidTransform.from_rpy_translation_mm(
        parent,
        child,
        translation_mm=Vec3(*xyz),
        roll_rad=roll,
        pitch_rad=pitch,
        yaw_rad=yaw,
    )


def _registration(
    *,
    xyz: tuple[float, float, float] = (0.0, 0.0, 0.0),
    roll: float = 0.0,
    pitch: float = 0.0,
    yaw: float = 0.0,
    revision: int = 0,
    source_hashes: tuple[tuple[str, str], ...] = (("nominal", SHA_A),),
) -> BoardRegistration:
    return BoardRegistration(
        revision=revision,
        Wv_T_board=_transform(
            "Wv", "board", xyz=xyz, roll=roll, pitch=pitch, yaw=yaw
        ),
        source_hashes=source_hashes,
    )


def _measurement(
    *,
    world_T_camera: RigidTransform | None = None,
    camera_T_board: RigidTransform | None = None,
    timing_quality: TimestampQuality = TimestampQuality.DEVICE_EXPOSURE,
    before_ns: int = 1_000_000_000,
    exposure_ns: int = 1_010_000_000,
    after_ns: int = 1_020_000_000,
    evaluated_ns: int = 1_030_000_000,
    joint_motion_rad: float = 0.001,
    sequence: int = 2,
    previous_sequence: int = 1,
    token: str = "capture-2",
    previous_token: str = "capture-1",
    inliers: int = 6,
    rmse_px: float = 0.5,
    source_hashes: tuple[tuple[str, str], ...] = (
        ("arm_feedback", SHA_A),
        ("pose_observation", SHA_B),
        ("camera_extrinsic", SHA_C),
    ),
) -> ArmCameraBoardMeasurement:
    return ArmCameraBoardMeasurement(
        measurement_id="measurement-1",
        Wv_T_C_arm=world_T_camera or _transform("Wv", "C_arm"),
        C_arm_T_board=camera_T_board or _transform("C_arm", "board"),
        timing_clock="virtual-monotonic",
        timestamp_quality=timing_quality,
        feedback_before_timestamp_ns=before_ns,
        exposure_timestamp_ns=exposure_ns,
        feedback_after_timestamp_ns=after_ns,
        evaluated_at_timestamp_ns=evaluated_ns,
        maximum_joint_motion_during_bracket_rad=joint_motion_rad,
        source_sequence=sequence,
        previous_source_sequence=previous_sequence,
        freshness_token=token,
        previous_freshness_token=previous_token,
        inlier_tag_count=inliers,
        inlier_reprojection_rmse_px=rmse_px,
        source_hashes=source_hashes,
    )


def _policy(**changes: object) -> BoardPoseCorrectionPolicy:
    base: dict[str, object] = {
        "translation_deadband_mm": 0.1,
        "maximum_translation_delta_mm": 2.0,
        "yaw_deadband_rad": 0.01,
        "maximum_yaw_delta_rad": 0.2,
        "tilt_deadband_rad": 0.01,
        "maximum_tilt_delta_rad": 0.15,
        "minimum_inlier_tags": 4,
        "maximum_inlier_reprojection_rmse_px": 1.0,
        "maximum_pose_age_ns": 100,
        "maximum_feedback_bracket_ns": 50,
        "maximum_joint_motion_during_bracket_rad": 0.01,
    }
    base.update(changes)
    return BoardPoseCorrectionPolicy(**base)  # type: ignore[arg-type]


def _short_timing_measurement(**changes: object) -> ArmCameraBoardMeasurement:
    base: dict[str, object] = {
        "before_ns": 100,
        "exposure_ns": 120,
        "after_ns": 150,
        "evaluated_ns": 200,
    }
    base.update(changes)
    return _measurement(**base)  # type: ignore[arg-type]


def test_identity_measurement_is_no_change_and_does_not_install_candidate() -> None:
    decision = decide_board_pose_correction(
        _registration(), _measurement(), BoardPoseCorrectionPolicy()
    )

    assert decision.status is BoardPoseCorrectionStatus.NO_CHANGE
    assert decision.applies_correction is False
    assert decision.translation_delta_board_mm == (0.0, 0.0, 0.0)
    assert decision.translation_delta_norm_mm == 0.0
    assert decision.yaw_delta_rad == 0.0
    assert decision.tilt_delta_rad == 0.0
    assert decision.selected_registration_hash == decision.active_registration.registration_hash
    assert decision.to_dict()["candidate_installed"] is False


def test_measurement_composes_camera_chain_in_declared_direction() -> None:
    measurement = _measurement(
        world_T_camera=_transform(
            "Wv", "C_arm", xyz=(100.0, 20.0, 5.0), yaw=math.pi / 2.0
        ),
        camera_T_board=_transform("C_arm", "board", xyz=(10.0, 0.0, 3.0)),
    )

    candidate = measurement.Wv_T_board_candidate

    assert candidate.parent_frame == "Wv"
    assert candidate.child_frame == "board"
    assert candidate.translation_mm.x == pytest.approx(100.0)
    assert candidate.translation_mm.y == pytest.approx(30.0)
    assert candidate.translation_mm.z == pytest.approx(8.0)


@pytest.mark.parametrize(
    ("registration_transform", "expected_fragment"),
    (
        (_transform("board", "Wv"), "Wv_T_board"),
        (_transform("world", "board"), "Wv_T_board"),
        (_transform("Wv", "B"), "Wv_T_board"),
    ),
)
def test_board_registration_rejects_inverse_or_aliased_frames(
    registration_transform: RigidTransform,
    expected_fragment: str,
) -> None:
    with pytest.raises(BoardPoseCorrectionError, match=expected_fragment):
        BoardRegistration(0, registration_transform, (("source", SHA_A),))


@pytest.mark.parametrize(
    ("world_T_camera", "camera_T_board", "expected_fragment"),
    (
        (_transform("C_arm", "Wv"), _transform("C_arm", "board"), "Wv_T_C_arm"),
        (_transform("Wv", "camera"), _transform("C_arm", "board"), "Wv_T_C_arm"),
        (_transform("Wv", "C_arm"), _transform("board", "C_arm"), "C_arm_T_board"),
        (_transform("Wv", "C_arm"), _transform("camera", "board"), "C_arm_T_board"),
    ),
)
def test_measurement_rejects_inverse_or_aliased_frames(
    world_T_camera: RigidTransform,
    camera_T_board: RigidTransform,
    expected_fragment: str,
) -> None:
    with pytest.raises(BoardPoseCorrectionError, match=expected_fragment):
        _measurement(
            world_T_camera=world_T_camera,
            camera_T_board=camera_T_board,
        )


def test_relative_translation_direction_is_active_to_candidate() -> None:
    decision = decide_board_pose_correction(
        _registration(xyz=(10.0, 0.0, 0.0)),
        _short_timing_measurement(
            camera_T_board=_transform("C_arm", "board", xyz=(12.0, 0.0, 0.0))
        ),
        _policy(),
    )

    assert decision.status is BoardPoseCorrectionStatus.APPLY
    assert decision.translation_delta_board_mm == pytest.approx((2.0, 0.0, 0.0))
    assert decision.to_dict()["delta"]["frame_semantics"] == "B_ACTIVE_T_B_CANDIDATE"  # type: ignore[index]


def test_translation_exact_limit_passes_and_epsilon_over_rejects_without_clamping() -> None:
    policy = _policy(
        translation_deadband_mm=0.0,
        maximum_translation_delta_mm=1.0,
    )
    exact = decide_board_pose_correction(
        _registration(),
        _short_timing_measurement(
            camera_T_board=_transform("C_arm", "board", xyz=(1.0, 0.0, 0.0))
        ),
        policy,
    )
    over = decide_board_pose_correction(
        _registration(),
        _short_timing_measurement(
            camera_T_board=_transform(
                "C_arm", "board", xyz=(1.0 + 1.0e-9, 0.0, 0.0)
            )
        ),
        policy,
    )

    assert exact.status is BoardPoseCorrectionStatus.APPLY
    assert over.status is BoardPoseCorrectionStatus.REJECT
    assert over.rejection_reasons == ("TRANSLATION_DELTA_LIMIT_EXCEEDED",)
    assert over.translation_delta_norm_mm == pytest.approx(1.0 + 1.0e-9)
    assert over.candidate_registration.Wv_T_board.translation_mm.x == pytest.approx(
        1.0 + 1.0e-9
    )
    assert over.selected_registration_hash is None


def test_yaw_exact_limit_passes_and_epsilon_over_rejects() -> None:
    policy = _policy(
        yaw_deadband_rad=0.0,
        maximum_yaw_delta_rad=0.1,
    )
    exact = decide_board_pose_correction(
        _registration(),
        _short_timing_measurement(
            camera_T_board=_transform("C_arm", "board", yaw=0.1)
        ),
        policy,
    )
    over = decide_board_pose_correction(
        _registration(),
        _short_timing_measurement(
            camera_T_board=_transform("C_arm", "board", yaw=0.10000001)
        ),
        policy,
    )

    assert exact.status is BoardPoseCorrectionStatus.APPLY
    assert exact.yaw_delta_rad == pytest.approx(0.1)
    assert exact.tilt_delta_rad == pytest.approx(0.0)
    assert over.status is BoardPoseCorrectionStatus.REJECT
    assert over.rejection_reasons == ("YAW_DELTA_LIMIT_EXCEEDED",)


def test_tilt_exact_limit_passes_and_epsilon_over_rejects_separately_from_yaw() -> None:
    policy = _policy(
        tilt_deadband_rad=0.0,
        maximum_tilt_delta_rad=0.1,
    )
    exact = decide_board_pose_correction(
        _registration(),
        _short_timing_measurement(
            camera_T_board=_transform("C_arm", "board", roll=0.1)
        ),
        policy,
    )
    over = decide_board_pose_correction(
        _registration(),
        _short_timing_measurement(
            camera_T_board=_transform("C_arm", "board", roll=0.10000001)
        ),
        policy,
    )

    assert exact.status is BoardPoseCorrectionStatus.APPLY
    assert exact.tilt_delta_rad == pytest.approx(0.1)
    assert exact.yaw_delta_rad == pytest.approx(0.0)
    assert over.status is BoardPoseCorrectionStatus.REJECT
    assert over.rejection_reasons == ("TILT_DELTA_LIMIT_EXCEEDED",)


def test_deadbands_are_inclusive_and_epsilon_over_requests_apply() -> None:
    policy = _policy(translation_deadband_mm=0.1)
    exact = decide_board_pose_correction(
        _registration(),
        _short_timing_measurement(
            camera_T_board=_transform("C_arm", "board", xyz=(0.1, 0.0, 0.0))
        ),
        policy,
    )
    over = decide_board_pose_correction(
        _registration(),
        _short_timing_measurement(
            camera_T_board=_transform(
                "C_arm", "board", xyz=(0.1 + 1.0e-9, 0.0, 0.0)
            )
        ),
        policy,
    )

    assert exact.status is BoardPoseCorrectionStatus.NO_CHANGE
    assert over.status is BoardPoseCorrectionStatus.APPLY


def test_yaw_and_tilt_metrics_are_reported_independently() -> None:
    decision = decide_board_pose_correction(
        _registration(),
        _short_timing_measurement(
            camera_T_board=_transform("C_arm", "board", roll=0.05, yaw=0.08)
        ),
        _policy(yaw_deadband_rad=0.0, tilt_deadband_rad=0.0),
    )

    assert decision.status is BoardPoseCorrectionStatus.APPLY
    assert decision.yaw_delta_rad == pytest.approx(0.08)
    assert decision.tilt_delta_rad == pytest.approx(0.05)


@pytest.mark.parametrize(
    ("measurement", "policy", "reason"),
    (
        (
            _short_timing_measurement(inliers=3),
            _policy(minimum_inlier_tags=4),
            "INLIER_TAG_COUNT_BELOW_MINIMUM",
        ),
        (
            _short_timing_measurement(rmse_px=1.000000001),
            _policy(maximum_inlier_reprojection_rmse_px=1.0),
            "REPROJECTION_RMSE_LIMIT_EXCEEDED",
        ),
        (
            _short_timing_measurement(evaluated_ns=221),
            _policy(maximum_pose_age_ns=100),
            "POSE_AGE_LIMIT_EXCEEDED",
        ),
        (
            _short_timing_measurement(before_ns=99),
            _policy(maximum_feedback_bracket_ns=50),
            "FEEDBACK_BRACKET_LIMIT_EXCEEDED",
        ),
        (
            _short_timing_measurement(joint_motion_rad=0.010000001),
            _policy(maximum_joint_motion_during_bracket_rad=0.01),
            "ARM_MOTION_DURING_CAPTURE_LIMIT_EXCEEDED",
        ),
    ),
)
def test_pose_and_timing_epsilon_over_limits_reject(
    measurement: ArmCameraBoardMeasurement,
    policy: BoardPoseCorrectionPolicy,
    reason: str,
) -> None:
    decision = decide_board_pose_correction(_registration(), measurement, policy)

    assert decision.status is BoardPoseCorrectionStatus.REJECT
    assert decision.rejection_reasons == (reason,)


def test_pose_and_timing_exact_limits_pass() -> None:
    measurement = _short_timing_measurement(
        before_ns=100,
        exposure_ns=120,
        after_ns=150,
        evaluated_ns=220,
        joint_motion_rad=0.01,
        inliers=4,
        rmse_px=1.0,
    )

    decision = decide_board_pose_correction(
        _registration(), measurement, _policy()
    )

    assert decision.status is BoardPoseCorrectionStatus.NO_CHANGE
    assert decision.rejection_reasons == ()
    assert all(decision.gate_results.values())


@pytest.mark.parametrize(
    "quality",
    (TimestampQuality.HOST_RECEIPT, TimestampQuality.UNQUALIFIED),
)
def test_unqualified_timing_rejects(quality: TimestampQuality) -> None:
    decision = decide_board_pose_correction(
        _registration(),
        _short_timing_measurement(timing_quality=quality),
        _policy(),
    )

    assert decision.status is BoardPoseCorrectionStatus.REJECT
    assert decision.rejection_reasons == ("TIMESTAMP_QUALITY_UNQUALIFIED",)


def test_settled_bracket_timing_is_qualified() -> None:
    decision = decide_board_pose_correction(
        _registration(),
        _short_timing_measurement(
            timing_quality=TimestampQuality.SETTLED_BRACKET
        ),
        _policy(),
    )

    assert decision.status is BoardPoseCorrectionStatus.NO_CHANGE


@pytest.mark.parametrize(
    ("changes", "reason"),
    (
        ({"sequence": 1}, "FRAME_FRESHNESS_NOT_ADVANCED"),
        ({"sequence": 0}, "FRAME_FRESHNESS_NOT_ADVANCED"),
        ({"token": "capture-1"}, "FRAME_FRESHNESS_NOT_ADVANCED"),
    ),
)
def test_stale_sequence_or_token_rejects(
    changes: dict[str, object], reason: str
) -> None:
    decision = decide_board_pose_correction(
        _registration(), _short_timing_measurement(**changes), _policy()
    )

    assert decision.status is BoardPoseCorrectionStatus.REJECT
    assert decision.rejection_reasons == (reason,)


def test_multiple_failed_gates_are_all_reported_in_stable_order() -> None:
    decision = decide_board_pose_correction(
        _registration(),
        _short_timing_measurement(
            timing_quality=TimestampQuality.UNQUALIFIED,
            sequence=1,
            token="capture-1",
            evaluated_ns=300,
            joint_motion_rad=0.02,
            inliers=1,
            rmse_px=2.0,
            camera_T_board=_transform(
                "C_arm", "board", xyz=(3.0, 0.0, 0.0), yaw=0.3, roll=0.2
            ),
        ),
        _policy(),
    )

    assert decision.status is BoardPoseCorrectionStatus.REJECT
    assert decision.rejection_reasons == (
        "TIMESTAMP_QUALITY_UNQUALIFIED",
        "FRAME_FRESHNESS_NOT_ADVANCED",
        "POSE_AGE_LIMIT_EXCEEDED",
        "ARM_MOTION_DURING_CAPTURE_LIMIT_EXCEEDED",
        "INLIER_TAG_COUNT_BELOW_MINIMUM",
        "REPROJECTION_RMSE_LIMIT_EXCEEDED",
        "TRANSLATION_DELTA_LIMIT_EXCEEDED",
        "YAW_DELTA_LIMIT_EXCEEDED",
        "TILT_DELTA_LIMIT_EXCEEDED",
    )


def test_biased_pose_is_rejected_and_preserved_exactly() -> None:
    biased = _short_timing_measurement(
        camera_T_board=_transform("C_arm", "board", xyz=(9.0, -4.0, 2.0))
    )
    decision = decide_board_pose_correction(
        _registration(), biased, _policy(maximum_translation_delta_mm=1.0)
    )

    assert decision.status is BoardPoseCorrectionStatus.REJECT
    assert decision.candidate_registration.Wv_T_board.almost_equal(
        biased.Wv_T_board_candidate,
        absolute_tolerance=0.0,
    )
    assert decision.candidate_registration.Wv_T_board.translation_mm == Vec3(
        9.0, -4.0, 2.0
    )
    assert decision.translation_delta_norm_mm == pytest.approx(math.sqrt(101.0))


def test_source_hash_order_is_canonical_and_hashes_are_deterministic() -> None:
    first_registration = _registration(
        source_hashes=(("z_source", SHA_C), ("a_source", SHA_A))
    )
    second_registration = _registration(
        source_hashes=(("a_source", SHA_A), ("z_source", SHA_C))
    )
    first_measurement = _short_timing_measurement(
        source_hashes=(("z_source", SHA_C), ("a_source", SHA_A))
    )
    second_measurement = _short_timing_measurement(
        source_hashes=(("a_source", SHA_A), ("z_source", SHA_C))
    )

    first = decide_board_pose_correction(
        first_registration, first_measurement, _policy()
    )
    second = decide_board_pose_correction(
        second_registration, second_measurement, _policy()
    )

    assert first_registration.source_hashes == second_registration.source_hashes
    assert first_registration.registration_hash == second_registration.registration_hash
    assert first_measurement.source_hashes == second_measurement.source_hashes
    assert first_measurement.measurement_hash == second_measurement.measurement_hash
    assert first.policy.policy_hash == second.policy.policy_hash
    assert first.to_dict() == second.to_dict()
    assert first.decision_hash == second.decision_hash
    assert len(first.decision_hash) == 64


def test_records_are_frozen_and_declare_exact_virtual_zero_authority() -> None:
    registration = _registration()
    measurement = _short_timing_measurement()
    policy = _policy()
    decision = decide_board_pose_correction(registration, measurement, policy)
    records = (registration, measurement, policy, decision)

    with pytest.raises(FrozenInstanceError):
        registration.revision = 10  # type: ignore[misc]

    expected_authority = {
        "execution_mode": "VIRTUAL",
        "hardware_accessed": False,
        "hardware_commands_generated": 0,
        "live_motion_authorized": False,
        "physical_contact_authorized": False,
        "physical_release_effect": "NONE",
    }
    for record in records:
        assert record.to_dict()["authority"] == expected_authority

    assert registration.to_dict()["schema"] == BOARD_REGISTRATION_SCHEMA
    assert measurement.to_dict()["schema"] == ARM_CAMERA_BOARD_MEASUREMENT_SCHEMA
    assert policy.to_dict()["schema"] == BOARD_POSE_CORRECTION_POLICY_SCHEMA
    assert decision.to_dict()["schema"] == BOARD_POSE_CORRECTION_DECISION_SCHEMA


@pytest.mark.parametrize(
    ("field_name", "bad_value"),
    (
        ("translation_deadband_mm", math.nan),
        ("maximum_translation_delta_mm", math.inf),
        ("maximum_yaw_delta_rad", -1.0),
        ("maximum_tilt_delta_rad", math.pi / 2.0),
        ("maximum_inlier_reprojection_rmse_px", math.nan),
        ("maximum_joint_motion_during_bracket_rad", math.inf),
    ),
)
def test_policy_rejects_nonfinite_or_out_of_contract_values(
    field_name: str, bad_value: float
) -> None:
    with pytest.raises(BoardPoseCorrectionError):
        _policy(**{field_name: bad_value})


@pytest.mark.parametrize(
    ("changes", "match"),
    (
        ({"rmse_px": math.nan}, "finite"),
        ({"joint_motion_rad": math.inf}, "finite"),
        ({"before_ns": 1_011_000_000}, "timing must satisfy"),
        ({"evaluated_ns": 140}, "timing must satisfy"),
        ({"source_hashes": (("bad", "A" * 64),)}, "lowercase SHA-256"),
        (
            {"source_hashes": (("duplicate", SHA_A), ("duplicate", SHA_B))},
            "duplicate source name",
        ),
    ),
)
def test_measurement_rejects_invalid_metrics_timing_or_sources(
    changes: dict[str, object], match: str
) -> None:
    with pytest.raises(BoardPoseCorrectionError, match=match):
        _measurement(**changes)  # type: ignore[arg-type]


def test_policy_rejects_deadband_larger_than_rejection_limit() -> None:
    with pytest.raises(BoardPoseCorrectionError, match="deadband"):
        _policy(
            translation_deadband_mm=2.0,
            maximum_translation_delta_mm=1.0,
        )


def test_registration_rejects_mutable_or_duplicate_source_hash_records() -> None:
    with pytest.raises(BoardPoseCorrectionError, match="immutable tuple"):
        BoardRegistration(0, _transform("Wv", "board"), [("source", SHA_A)])  # type: ignore[arg-type]
    with pytest.raises(BoardPoseCorrectionError, match="duplicate source name"):
        _registration(source_hashes=(("source", SHA_A), ("source", SHA_B)))


def test_candidate_revision_and_source_links_are_exact() -> None:
    active = _registration(revision=7)
    measurement = _short_timing_measurement(
        camera_T_board=_transform("C_arm", "board", xyz=(0.5, 0.0, 0.0))
    )
    decision = decide_board_pose_correction(active, measurement, _policy())

    assert decision.candidate_registration.revision == 8
    assert dict(decision.candidate_registration.source_hashes) == {
        "active_registration_sha256": active.registration_hash,
        "measurement_sha256": measurement.measurement_hash,
    }
    assert decision.selected_registration_hash == (
        decision.candidate_registration.registration_hash
    )


def test_record_hash_changes_for_pose_timing_quality_and_policy_bias() -> None:
    active = _registration()
    baseline_measurement = _short_timing_measurement()
    baseline_policy = _policy()
    baseline = decide_board_pose_correction(
        active, baseline_measurement, baseline_policy
    )

    assert replace(
        baseline_measurement, inlier_reprojection_rmse_px=0.6
    ).measurement_hash != baseline_measurement.measurement_hash
    assert replace(
        baseline_measurement, evaluated_at_timestamp_ns=201
    ).measurement_hash != baseline_measurement.measurement_hash
    assert replace(
        baseline_policy, maximum_translation_delta_mm=3.0
    ).policy_hash != baseline_policy.policy_hash
    changed = decide_board_pose_correction(
        active,
        replace(
            baseline_measurement,
            C_arm_T_board=_transform("C_arm", "board", xyz=(0.2, 0.0, 0.0)),
        ),
        baseline_policy,
    )
    assert changed.decision_hash != baseline.decision_hash

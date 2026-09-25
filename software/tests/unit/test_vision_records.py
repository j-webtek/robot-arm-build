from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import math

import pytest

from rocell.geometry import RigidTransform, Rotation3, Vec3
from rocell.vision import (
    AprilTagDetection,
    AprilTagDetectionBatch,
    AprilTagPoseObservation,
    DetectorIdentity,
    FrameCaptureBinding,
    FramePacket,
    PixelCorner,
    PoseCovariance6,
    PoseEstimatorIdentity,
    TagFitDiagnostic,
    TagReference,
    TimestampQuality,
    VisionRecordError,
    april_tag_detection_batch_from_dict,
    april_tag_pose_observation_from_dict,
)


def _minimal_jpeg(width: int = 320, height: int = 240) -> bytes:
    sof_payload = (
        b"\x08"
        + height.to_bytes(2, "big")
        + width.to_bytes(2, "big")
        + b"\x01\x01\x11\x00"
    )
    return (
        b"\xff\xd8\xff\xc0"
        + (len(sof_payload) + 2).to_bytes(2, "big")
        + sof_payload
        + b"\xff\xd9"
    )


def _frame() -> FramePacket:
    return FramePacket(
        capture_id="capture-0001",
        jpeg_bytes=_minimal_jpeg(),
        width_px=320,
        height_px=240,
        source_sequence=17,
        source_timestamp_ns=1_001,
        source_clock="camera-monotonic",
        host_request_ns=990,
        host_first_byte_ns=1_010,
        host_complete_ns=1_020,
        settings_hash="a" * 64,
        timestamp_quality=TimestampQuality.DEVICE_EXPOSURE,
        freshness_token="sequence:17",
        freshness_basis="device_sequence",
    )


def _detector() -> DetectorIdentity:
    return DetectorIdentity(
        detector_id="apriltag.reference",
        version="1.2.3",
        configuration_sha256="b" * 64,
        implementation_sha256="c" * 64,
    )


def _detection(
    tag_id: int,
    *,
    x: float,
    rejected: bool = False,
) -> AprilTagDetection:
    return AprilTagDetection(
        tag=TagReference("tag36h11", tag_id),
        corners_px=(
            PixelCorner(x, 20.0),
            PixelCorner(x + 20.0, 20.0),
            PixelCorner(x + 20.0, 40.0),
            PixelCorner(x, 40.0),
        ),
        decision_margin=75.5,
        hamming=0,
        rejection_reason="low_margin_policy" if rejected else None,
    )


def _batch() -> AprilTagDetectionBatch:
    # Reverse input order proves construction normalizes tag order.
    return AprilTagDetectionBatch(
        frame=FrameCaptureBinding.from_frame_packet(
            _frame(), host_clock="host-monotonic"
        ),
        detector=_detector(),
        detections=(
            _detection(9, x=100.0, rejected=True),
            _detection(2, x=30.0),
        ),
    )


def _observation() -> AprilTagPoseObservation:
    batch = _batch()
    return AprilTagPoseObservation(
        detection_batch=batch,
        estimator=PoseEstimatorIdentity(
            estimator_id="pnp.reference",
            version="2.0.0",
            configuration_sha256="d" * 64,
            implementation_sha256="e" * 64,
        ),
        camera_intrinsics_sha256="f" * 64,
        tag_map_sha256="1" * 64,
        pose=RigidTransform(
            parent_frame="C_arm",
            child_frame="B",
            rotation=Rotation3.identity(),
            translation_mm=Vec3(10.0, 20.0, 300.0),
        ),
        covariance=PoseCovariance6.diagonal(
            (0.04, 0.04, 0.09, 0.0001, 0.0001, 0.0002)
        ),
        fit_diagnostics=(
            TagFitDiagnostic(
                tag=TagReference("tag36h11", 9),
                inlier=False,
                reprojection_residual_px=None,
                rejection_reason="detector_rejected",
            ),
            TagFitDiagnostic(
                tag=TagReference("tag36h11", 2),
                inlier=True,
                reprojection_residual_px=0.25,
                rejection_reason=None,
            ),
        ),
    )


def test_frame_binding_preserves_packet_identity_hash_settings_and_clocks() -> None:
    frame = _frame()
    binding = FrameCaptureBinding.from_frame_packet(
        frame, host_clock="host-monotonic"
    )

    assert binding.jpeg_sha256 == frame.sha256
    assert binding.to_dict()["host_timing"] == {
        "request_ns": 990,
        "first_byte_ns": 1_010,
        "complete_ns": 1_020,
        "clock": "host-monotonic",
    }
    binding.assert_matches(frame, host_clock="host-monotonic")
    with pytest.raises(VisionRecordError, match="does not match"):
        binding.assert_matches(
            replace(frame, settings_hash="0" * 64), host_clock="host-monotonic"
        )


def test_detection_batch_is_immutable_canonical_and_zero_authority() -> None:
    batch = _batch()

    assert [item.tag.tag_id for item in batch.detections] == [2, 9]
    assert batch.accepted_tags == (TagReference("tag36h11", 2),)
    assert batch.rejected_tags == (TagReference("tag36h11", 9),)
    assert len(batch.content_hash) == 64
    assert batch.content_hash == april_tag_detection_batch_from_dict(
        batch.to_dict()
    ).content_hash
    assert batch.to_dict()["authority"] == {
        "physical_authority": "NONE",
        "physical_commands_generated": 0,
        "can_authorize_motion": False,
        "can_release_physical_gates": False,
    }
    with pytest.raises(FrozenInstanceError):
        batch.schema = "changed"  # type: ignore[misc]


def test_detection_batch_rejects_duplicate_tag_ids_even_across_families() -> None:
    duplicate = replace(
        _detection(2, x=70.0),
        tag=TagReference("tag25h9", 2),
    )
    with pytest.raises(VisionRecordError, match="duplicate tag id"):
        AprilTagDetectionBatch(
            frame=FrameCaptureBinding.from_frame_packet(
                _frame(), host_clock="host-monotonic"
            ),
            detector=_detector(),
            detections=(_detection(2, x=30.0), duplicate),
        )


@pytest.mark.parametrize(
    "corners, pattern",
    [
        (
            (
                PixelCorner(10.0, 10.0),
                PixelCorner(30.0, 30.0),
                PixelCorner(30.0, 10.0),
                PixelCorner(10.0, 30.0),
            ),
            "convex ordered",
        ),
        (
            (
                PixelCorner(10.0, 10.0),
                PixelCorner(30.0, 10.0),
                PixelCorner(30.0, 10.0),
                PixelCorner(10.0, 30.0),
            ),
            "distinct",
        ),
    ],
)
def test_detection_rejects_unordered_or_duplicate_corners(
    corners: tuple[PixelCorner, PixelCorner, PixelCorner, PixelCorner],
    pattern: str,
) -> None:
    with pytest.raises(VisionRecordError, match=pattern):
        AprilTagDetection(
            tag=TagReference("tag36h11", 1),
            corners_px=corners,
            decision_margin=10.0,
            hamming=0,
        )


def test_detection_rejects_nonfinite_and_out_of_frame_values() -> None:
    with pytest.raises(VisionRecordError, match="finite"):
        PixelCorner(math.nan, 1.0)
    outside = _detection(7, x=310.0)
    with pytest.raises(VisionRecordError, match="outside"):
        AprilTagDetectionBatch(
            frame=FrameCaptureBinding.from_frame_packet(
                _frame(), host_clock="host-monotonic"
            ),
            detector=_detector(),
            detections=(outside,),
        )


def test_detection_loader_rejects_order_edits_and_authority_escalation() -> None:
    document = _batch().to_dict()
    document["detections"].reverse()
    with pytest.raises(VisionRecordError, match="canonical"):
        april_tag_detection_batch_from_dict(document)

    document = _batch().to_dict()
    document["authority"]["can_authorize_motion"] = True
    with pytest.raises(VisionRecordError, match="zero physical authority"):
        april_tag_detection_batch_from_dict(document)


def test_pose_observation_binds_frames_covariance_hashes_and_fit_arrays() -> None:
    observation = _observation()
    document = observation.to_dict()

    assert observation.pose.parent_frame == "C_arm"
    assert observation.pose.child_frame == "B"
    assert observation.inlier_mask == (True, False)
    assert observation.reprojection_residuals_px == (0.25, None)
    assert observation.used_tags == (TagReference("tag36h11", 2),)
    assert observation.rejected_tags == (TagReference("tag36h11", 9),)
    assert observation.inlier_rmse_px == 0.25
    assert document["detection_batch_sha256"] == _batch().content_hash
    assert document["pose"]["covariance_6x6"]["parameter_order"] == [
        "translation_x_mm",
        "translation_y_mm",
        "translation_z_mm",
        "rotation_x_rad",
        "rotation_y_rad",
        "rotation_z_rad",
    ]
    assert document["authority"]["physical_commands_generated"] == 0


def test_pose_round_trip_is_hash_stable_and_redundant_fields_are_verified() -> None:
    observation = _observation()
    reloaded = april_tag_pose_observation_from_dict(observation.to_dict())
    assert reloaded == observation
    assert reloaded.content_hash == observation.content_hash

    document = observation.to_dict()
    document["fit"]["inlier_mask"] = [False, True]
    with pytest.raises(VisionRecordError, match="rejected tag|canonical"):
        april_tag_pose_observation_from_dict(document)

    document = observation.to_dict()
    document["detection_batch_sha256"] = "0" * 64
    with pytest.raises(VisionRecordError, match="does not match"):
        april_tag_pose_observation_from_dict(document)


def test_pose_rejects_incomplete_fit_or_use_of_detector_rejection() -> None:
    observation = _observation()
    with pytest.raises(VisionRecordError, match="cover every detection"):
        replace(observation, fit_diagnostics=observation.fit_diagnostics[:1])

    diagnostics = tuple(
        replace(
            item,
            inlier=True,
            reprojection_residual_px=1.0,
            rejection_reason=None,
        )
        if item.tag.tag_id == 9
        else item
        for item in observation.fit_diagnostics
    )
    with pytest.raises(VisionRecordError, match="Detector-rejected"):
        replace(observation, fit_diagnostics=diagnostics)


def test_covariance_rejects_wrong_shape_nonfinite_asymmetry_and_negative_variance() -> None:
    with pytest.raises(VisionRecordError, match="exactly 36"):
        PoseCovariance6((0.0,) * 35)
    with pytest.raises(VisionRecordError, match="finite"):
        PoseCovariance6((math.inf,) + (0.0,) * 35)
    asymmetric = [0.0] * 36
    asymmetric[1] = 1.0
    with pytest.raises(VisionRecordError, match="symmetric"):
        PoseCovariance6(tuple(asymmetric))
    negative_diagonal = [0.0] * 36
    negative_diagonal[7] = -1.0
    with pytest.raises(VisionRecordError, match="diagonal"):
        PoseCovariance6(tuple(negative_diagonal))

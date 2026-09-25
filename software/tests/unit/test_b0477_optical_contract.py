from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from rocell.application.b0477_optical_contract import (
    B0477_CAPTURE_PIXEL_SPACE,
    B0477_ESTIMATOR_PIXEL_SPACE,
    B0477_PHASE1_OPTICAL_FRAME,
    B0477DetectionPixelSpaceProvenance,
    B0477OpticalContractError,
    B0477RectifiedDetectionBatch,
    B0477SyntheticOpticalContract,
    build_b0477_synthetic_optical_contract,
)
from rocell.simulation.camera import DistortionCoefficients
from rocell.vision.camera import TimestampQuality
from rocell.vision.camera_profile import load_camera_profile
from rocell.vision.detections import (
    AprilTagDetection,
    AprilTagDetectionBatch,
    DetectorIdentity,
    FrameCaptureBinding,
    PixelCorner,
    TagReference,
)
from rocell.workcell.static_camera_support import load_static_camera_support_design


WORKSPACE = Path(__file__).resolve().parents[3]
PROFILE = WORKSPACE / "software/config/camera_profiles/arducam_b0477_imx283_16mm.json"
SUPPORT = WORKSPACE / "hardware/static_overhead_camera/config/support_design.json"


def _contract():  # type: ignore[no-untyped-def]
    profile = load_camera_profile(PROFILE)
    support = load_static_camera_support_design(WORKSPACE, SUPPORT)
    return profile, support, build_b0477_synthetic_optical_contract(profile, support)


def _raw_detection_batch(
    contract: B0477SyntheticOpticalContract,
) -> AprilTagDetectionBatch:
    rectified_corners = (
        (800.0, 600.0),
        (900.0, 600.0),
        (900.0, 700.0),
        (800.0, 700.0),
    )
    distorted_corners = tuple(
        contract.distort_rectified_pixel(x_px, y_px)
        for x_px, y_px in rectified_corners
    )
    return AprilTagDetectionBatch(
        frame=FrameCaptureBinding(
            capture_id="synthetic-b0477-pixel-space-test",
            jpeg_sha256="a" * 64,
            width_px=contract.width_px,
            height_px=contract.height_px,
            source_sequence=1,
            source_timestamp_ns=1_000,
            source_clock="synthetic_device_clock",
            host_request_ns=900,
            host_first_byte_ns=1_000,
            host_complete_ns=1_100,
            host_clock="synthetic_host_monotonic",
            settings_sha256="b" * 64,
            timestamp_quality=TimestampQuality.DEVICE_EXPOSURE,
            freshness_token="sequence:1",
            freshness_basis="SYNTHETIC_SEQUENCE_ONLY",
        ),
        detector=DetectorIdentity(
            detector_id="rocell.apriltag36h11.pixel",
            version="1.0.0",
            configuration_sha256="c" * 64,
            implementation_sha256="d" * 64,
        ),
        detections=(
            AprilTagDetection(
                tag=TagReference("tag36h11", 0),
                corners_px=tuple(
                    PixelCorner(x_px, y_px)
                    for x_px, y_px in distorted_corners
                ),  # type: ignore[arg-type]
                decision_margin=50.0,
                hamming=0,
            ),
        ),
    )


def test_optical_contract_is_intentionally_exported() -> None:
    import rocell.application as application

    assert application.B0477SyntheticOpticalContract is B0477SyntheticOpticalContract
    assert application.build_b0477_synthetic_optical_contract is (
        build_b0477_synthetic_optical_contract
    )


def test_contract_unifies_support_renderer_and_estimator_geometry() -> None:
    profile, support, contract = _contract()

    assert contract.optical_frame == B0477_PHASE1_OPTICAL_FRAME
    assert contract.optical_frame == "C_overhead_optical"
    assert contract.capture_pixel_space == B0477_CAPTURE_PIXEL_SPACE
    assert contract.estimator_pixel_space == B0477_ESTIMATOR_PIXEL_SPACE
    assert contract.fx_px == pytest.approx(contract.fy_px, abs=1e-12)
    assert contract.effective_vertical_fov_deg == pytest.approx(
        support.metrics.aspect_conservative_vertical_fov_deg,
        abs=1e-12,
    )
    assert contract.effective_vertical_fov_deg < profile.simulation_proxy.vertical_fov_deg

    capture_camera = contract.capture_camera()
    estimator_intrinsics = contract.estimator_intrinsics()
    assert capture_camera.optical_frame == estimator_intrinsics.camera_frame
    assert capture_camera.distortion == contract.distortion
    assert capture_camera.fx_px == estimator_intrinsics.fx_px
    assert capture_camera.fy_px == estimator_intrinsics.fy_px
    assert any(
        value != 0.0
        for value in (
            contract.distortion.k1,
            contract.distortion.k2,
            contract.distortion.p1,
            contract.distortion.p2,
            contract.distortion.k3,
        )
    )
    assert len(contract.content_sha256) == 64
    assert len(contract.undistortion_map_sha256) == 64
    assert contract.to_dict()["authority"] == {
        "physical_calibration_authority": False,
        "live_capture_authority": False,
        "robot_motion_authority": False,
        "contact_authority": False,
    }


def test_contract_inverse_map_round_trips_capture_pixels() -> None:
    _, _, contract = _contract()
    samples = (
        (contract.cx_px, contract.cy_px),
        (120.0, 120.0),
        (contract.width_px - 121.0, 120.0),
        (120.0, contract.height_px - 121.0),
        (contract.width_px - 121.0, contract.height_px - 121.0),
    )
    for rectified in samples:
        captured = contract.distort_rectified_pixel(*rectified)
        recovered = contract.undistort_capture_pixel(*captured)
        assert recovered == pytest.approx(rectified, abs=1e-7)


def test_contract_fails_closed_on_frame_focal_distortion_and_support_drift() -> None:
    _, support, contract = _contract()
    with pytest.raises(B0477OpticalContractError, match="canonical"):
        replace(contract, optical_frame="camera_b0477_static_overhead_optical")
    with pytest.raises(B0477OpticalContractError, match="fx_px"):
        replace(contract, fx_px=contract.fx_px + 0.01)
    with pytest.raises(B0477OpticalContractError, match="fy_px"):
        replace(contract, fy_px=contract.fy_px - 0.01)
    with pytest.raises(B0477OpticalContractError, match="stress-distortion"):
        replace(contract, distortion=DistortionCoefficients())

    drifted_metrics = replace(
        support.metrics,
        aspect_conservative_vertical_fov_deg=(
            support.metrics.aspect_conservative_vertical_fov_deg + 0.01
        ),
    )
    drifted_support = replace(support, metrics=drifted_metrics)
    profile = load_camera_profile(PROFILE)
    with pytest.raises(B0477OpticalContractError, match="support coverage"):
        build_b0477_synthetic_optical_contract(profile, drifted_support)


def test_rectified_batch_carries_an_exact_immutable_pixel_space_transition() -> None:
    _, _, contract = _contract()
    raw_batch = _raw_detection_batch(contract)

    rectified = contract.rectify_detection_batch(raw_batch)

    assert isinstance(rectified, B0477RectifiedDetectionBatch)
    assert isinstance(
        rectified.pixel_space_provenance,
        B0477DetectionPixelSpaceProvenance,
    )
    assert rectified.pixel_space == B0477_ESTIMATOR_PIXEL_SPACE
    assert rectified.pixel_space_provenance.source_pixel_space == (
        B0477_CAPTURE_PIXEL_SPACE
    )
    assert rectified.pixel_space_provenance.destination_pixel_space == (
        B0477_ESTIMATOR_PIXEL_SPACE
    )
    assert rectified.pixel_space_provenance.source_detector == raw_batch.detector
    assert rectified.detector == contract.rectifier_identity(raw_batch.detector)
    assert rectified.detector.configuration_sha256 == (
        rectified.pixel_space_provenance.content_sha256
    )
    assert rectified.pixel_space_provenance.physical_authority == "NONE"
    contract.assert_rectified_detection_batch(rectified)

    expected = (
        (800.0, 600.0),
        (900.0, 600.0),
        (900.0, 700.0),
        (800.0, 700.0),
    )
    actual = tuple(
        (corner.x_px, corner.y_px)
        for corner in rectified.detections[0].corners_px
    )
    for actual_corner, expected_corner in zip(actual, expected):
        assert actual_corner == pytest.approx(expected_corner, abs=1e-7)


def test_rectifier_rejects_double_rectification_and_stripped_batch_subtype() -> None:
    _, _, contract = _contract()
    raw_batch = _raw_detection_batch(contract)
    rectified = contract.rectify_detection_batch(raw_batch)

    with pytest.raises(B0477OpticalContractError, match="double rectification"):
        contract.rectify_detection_batch(rectified)

    # Reconstructing the generic base record cannot hide the rectifier marker:
    # its immutable detector identity still declares estimator-space output.
    untyped_copy = AprilTagDetectionBatch(
        frame=rectified.frame,
        detector=rectified.detector,
        detections=rectified.detections,
    )
    with pytest.raises(B0477OpticalContractError, match="capture-pixel"):
        contract.rectify_detection_batch(untyped_copy)


def test_rectified_pixel_space_and_detector_tampering_fail_closed() -> None:
    _, _, contract = _contract()
    raw_batch = _raw_detection_batch(contract)
    rectified = contract.rectify_detection_batch(raw_batch)
    provenance = rectified.pixel_space_provenance
    assert provenance is not None

    with pytest.raises(B0477OpticalContractError, match="destination"):
        replace(provenance, destination_pixel_space=B0477_CAPTURE_PIXEL_SPACE)

    tampered_provenance = replace(
        provenance,
        optical_contract_sha256="0" * 64,
    )
    with pytest.raises(B0477OpticalContractError, match="does not bind"):
        replace(rectified, pixel_space_provenance=tampered_provenance)

    with pytest.raises(B0477OpticalContractError, match="does not bind"):
        replace(rectified, detector=raw_batch.detector)

    with pytest.raises(B0477OpticalContractError, match="capture-pixel"):
        contract.rectifier_identity(rectified.detector)

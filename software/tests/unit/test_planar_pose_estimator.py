from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import ast
from pathlib import Path

import pytest

import rocell.vision.planar_pose_estimator as estimator_module

from rocell.geometry import Point3Mm, RigidTransform, Rotation3, Vec3
from rocell.vision.camera import TimestampQuality
from rocell.vision.detections import (
    AprilTagDetection,
    AprilTagDetectionBatch,
    DetectorIdentity,
    FrameCaptureBinding,
    PixelCorner,
    TagReference,
)
from rocell.vision.planar_pose_estimator import (
    CAMERA_OPTICAL_FRAME,
    PinholeIntrinsics,
    PlanarAprilTagBoardPoseEstimator,
    PlanarBoardTag,
    PlanarBoardTagMap,
    PlanarPoseEstimationError,
    PlanarPoseEstimatorConfig,
    estimate_planar_board_pose,
)


PLANE_Z_MM = 0.3
GROUND_TRUTH = RigidTransform(
    parent_frame="camera_overview_optical",
    child_frame="board",
    rotation=Rotation3((1.0, 0.0, 0.0, 0.0, -1.0, 0.0, 0.0, 0.0, -1.0)),
    translation_mm=Vec3(-305.0, 228.5, 500.0),
)


def _intrinsics(
    *,
    width_px: int = 640,
    camera_frame: str = "camera_overview_optical",
) -> PinholeIntrinsics:
    return PinholeIntrinsics(
        calibration_id="imx335-mode-test",
        width_px=width_px,
        height_px=480,
        fx_px=500.0,
        fy_px=510.0,
        cx_px=320.0,
        cy_px=240.0,
        skew_px=0.75,
        source_sha256="a" * 64,
        camera_frame=camera_frame,
    )


def _tag(tag_id: int, centre_x: float, centre_y: float) -> PlanarBoardTag:
    half = 10.0
    # Canonical decoded tag order TL,TR,BR,BL.  With the fixed-overview pose,
    # board +Y projects toward image top, so this is also visually intuitive.
    return PlanarBoardTag(
        tag=TagReference("tag36h11", tag_id),
        corners_board_mm=(
            Point3Mm("board", centre_x - half, centre_y + half, PLANE_Z_MM),
            Point3Mm("board", centre_x + half, centre_y + half, PLANE_Z_MM),
            Point3Mm("board", centre_x + half, centre_y - half, PLANE_Z_MM),
            Point3Mm("board", centre_x - half, centre_y - half, PLANE_Z_MM),
        ),
    )


def _tag_map() -> PlanarBoardTagMap:
    return PlanarBoardTagMap(
        map_id="rc03-test-board-tags",
        board_frame="board",
        tag_plane_z_board_mm=PLANE_Z_MM,
        tags=(
            _tag(4, 330.0, 250.0),
            _tag(2, 330.0, 190.0),
            _tag(1, 260.0, 190.0),
            _tag(3, 260.0, 250.0),
        ),
        source_sha256="b" * 64,
    )


def _project(point: Point3Mm) -> tuple[float, float]:
    intrinsics = _intrinsics()
    camera = GROUND_TRUTH.transform_position_mm(Vec3(point.x, point.y, point.z))
    normalized_x = camera.x / camera.z
    normalized_y = camera.y / camera.z
    return (
        intrinsics.fx_px * normalized_x
        + intrinsics.skew_px * normalized_y
        + intrinsics.cx_px,
        intrinsics.fy_px * normalized_y + intrinsics.cy_px,
    )


def _detection(
    definition: PlanarBoardTag,
    *,
    pixel_offset: tuple[float, float] = (0.0, 0.0),
    rejection_reason: str | None = None,
) -> AprilTagDetection:
    corners = tuple(
        PixelCorner(
            _project(point)[0] + pixel_offset[0],
            _project(point)[1] + pixel_offset[1],
        )
        for point in definition.corners_board_mm
    )
    return AprilTagDetection(
        tag=definition.tag,
        corners_px=corners,  # type: ignore[arg-type]
        decision_margin=80.0,
        hamming=0,
        rejection_reason=rejection_reason,
    )


def _frame() -> FrameCaptureBinding:
    return FrameCaptureBinding(
        capture_id="pose-estimator-frame-1",
        jpeg_sha256="c" * 64,
        width_px=640,
        height_px=480,
        source_sequence=1,
        source_timestamp_ns=100,
        source_clock="camera-monotonic",
        host_request_ns=90,
        host_first_byte_ns=100,
        host_complete_ns=110,
        host_clock="host-monotonic",
        settings_sha256="d" * 64,
        timestamp_quality=TimestampQuality.DEVICE_EXPOSURE,
        freshness_token="sequence:1",
        freshness_basis="device_sequence",
    )


def _batch(
    detections: tuple[AprilTagDetection, ...] | None = None,
) -> AprilTagDetectionBatch:
    tag_map = _tag_map()
    selected = detections or (
        _detection(tag_map.tags[2], pixel_offset=(65.0, 0.0)),
        _detection(tag_map.tags[0]),
        _detection(tag_map.tags[3], rejection_reason="test_detector_rejection"),
        _detection(tag_map.tags[1]),
    )
    return AprilTagDetectionBatch(
        frame=_frame(),
        detector=DetectorIdentity(
            detector_id="apriltag-test-double",
            version="1.0.0",
            configuration_sha256="e" * 64,
            implementation_sha256="f" * 64,
        ),
        detections=selected,
    )


def test_estimator_recovers_fixed_overview_pose_rejects_outlier_and_corrects_plane() -> None:
    tag_map = _tag_map()
    intrinsics = _intrinsics()
    config = PlanarPoseEstimatorConfig(
        maximum_tag_reprojection_rmse_px=0.25,
        minimum_inlier_tags=2,
    )

    observation = estimate_planar_board_pose(_batch(), intrinsics, tag_map, config)

    assert observation.pose.parent_frame == "camera_overview_optical"
    assert observation.pose.child_frame == "board"
    assert observation.pose.rotation.matrix == pytest.approx(
        GROUND_TRUTH.rotation.matrix, abs=1e-9
    )
    assert (
        observation.pose.translation_mm.x,
        observation.pose.translation_mm.y,
        observation.pose.translation_mm.z,
    ) == pytest.approx((-305.0, 228.5, 500.0), abs=1e-8)
    # Without the explicit tag-plane-to-board-origin correction this would be
    # 499.7 mm for the current fixed overview.
    assert observation.pose.translation_mm.z != pytest.approx(499.7, abs=1e-4)
    assert observation.inlier_mask == (True, True, False, False)
    assert observation.reprojection_residuals_px[0] == pytest.approx(0.0, abs=1e-8)
    assert observation.reprojection_residuals_px[1] == pytest.approx(0.0, abs=1e-8)
    assert observation.reprojection_residuals_px[2] is not None
    assert observation.reprojection_residuals_px[2] > 60.0
    assert observation.reprojection_residuals_px[3] is None
    assert observation.fit_diagnostics[2].rejection_reason == (
        "reprojection_residual_exceeds_threshold"
    )
    assert observation.fit_diagnostics[3].rejection_reason == (
        "detector_rejected:test_detector_rejection"
    )
    assert observation.camera_intrinsics_sha256 == intrinsics.content_hash
    assert observation.tag_map_sha256 == tag_map.content_hash
    assert observation.estimator.configuration_sha256 == config.content_hash
    assert len(observation.estimator.implementation_sha256) == 64
    covariance_diagonal = tuple(
        observation.covariance.row_major[index * 6 + index] for index in range(6)
    )
    assert all(value > 0.0 for value in covariance_diagonal)
    assert observation.to_dict()["authority"]["physical_commands_generated"] == 0


def test_service_is_deterministic_hash_bound_immutable_and_wrapper_equivalent() -> None:
    batch = _batch()
    intrinsics = _intrinsics()
    tag_map = _tag_map()
    config = PlanarPoseEstimatorConfig(maximum_tag_reprojection_rmse_px=0.25)

    first = estimate_planar_board_pose(batch, intrinsics, tag_map, config)
    second = PlanarAprilTagBoardPoseEstimator(config).estimate(
        batch, intrinsics, tag_map
    )

    assert second == first
    assert second.content_hash == first.content_hash
    with pytest.raises(FrozenInstanceError):
        intrinsics.fx_px = 1.0  # type: ignore[misc]
    assert tag_map.tags == tuple(sorted(tag_map.tags, key=lambda item: item.tag))


def test_equal_support_inconsistent_tags_fail_as_ambiguous_instead_of_guessing() -> None:
    tag_map = _tag_map()
    first = _detection(tag_map.tags[0])
    second = _detection(tag_map.tags[1], pixel_offset=(60.0, 0.0))
    with pytest.raises(PlanarPoseEstimationError, match="ambiguous inlier sets"):
        estimate_planar_board_pose(
            _batch((first, second)),
            _intrinsics(),
            tag_map,
            PlanarPoseEstimatorConfig(
                maximum_tag_reprojection_rmse_px=0.1,
                minimum_inlier_tags=1,
            ),
        )


def test_refinement_never_reintroduces_a_consensus_excluded_tag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An under-threshold excluded tag cannot create a two-mask cycle."""

    tag_map = _tag_map()
    definitions = tag_map.tags[:3]
    eligible = tuple(
        estimator_module._EligibleTag(_detection(definition), definition)
        for definition in definitions
    )
    fit_sizes: list[int] = []

    def fake_fit_pose(*args: object) -> RigidTransform:
        selected = args[0]
        assert isinstance(selected, tuple)
        fit_sizes.append(len(selected))
        return GROUND_TRUTH

    monkeypatch.setattr(estimator_module, "_fit_pose", fake_fit_pose)
    monkeypatch.setattr(
        estimator_module,
        "_tag_residuals",
        lambda *_args: (0.1, 0.1, 0.1),
    )
    pose, residuals, mask = estimator_module._refine_consensus(
        eligible,
        (True, True, False),
        _intrinsics(),
        tag_map,
        PlanarPoseEstimatorConfig(
            maximum_tag_reprojection_rmse_px=1.0,
            minimum_inlier_tags=2,
        ),
    )

    assert pose == GROUND_TRUTH
    assert residuals == (0.1, 0.1, 0.1)
    assert mask == (True, True, False)
    assert fit_sizes == [2]


def test_resolution_mismatch_and_too_few_mapped_detections_fail_closed() -> None:
    with pytest.raises(PlanarPoseEstimationError, match="resolution"):
        estimate_planar_board_pose(_batch(), _intrinsics(width_px=800), _tag_map())

    unknown = replace(
        _detection(_tag_map().tags[0]),
        tag=TagReference("tag36h11", 99),
    )
    with pytest.raises(PlanarPoseEstimationError, match="fewer"):
        estimate_planar_board_pose(
            _batch((unknown,)),
            _intrinsics(),
            _tag_map(),
            PlanarPoseEstimatorConfig(minimum_inlier_tags=1),
        )


def test_tag_map_rejects_noncanonical_degenerate_frame_and_plane_geometry() -> None:
    good = _tag(1, 260.0, 190.0)
    with pytest.raises(PlanarPoseEstimationError, match="convex ordered"):
        replace(
            good,
            corners_board_mm=(
                good.corners_board_mm[0],
                good.corners_board_mm[2],
                good.corners_board_mm[1],
                good.corners_board_mm[3],
            ),
        )

    wrong_frame_point = replace(good.corners_board_mm[0], frame="other-board")
    with pytest.raises(PlanarPoseEstimationError, match="one explicit board frame"):
        replace(
            good,
            corners_board_mm=(wrong_frame_point, *good.corners_board_mm[1:]),
        )

    off_plane = replace(
        good,
        corners_board_mm=(
            replace(good.corners_board_mm[0], z=PLANE_Z_MM + 0.01),
            *good.corners_board_mm[1:],
        ),
    )
    with pytest.raises(PlanarPoseEstimationError, match="not coplanar"):
        PlanarBoardTagMap(
            "bad-plane",
            "board",
            PLANE_Z_MM,
            (off_plane,),
            "0" * 64,
        )


def test_hypothesis_budget_and_invalid_intrinsic_frame_are_rejected() -> None:
    with pytest.raises(PlanarPoseEstimationError, match="hypothesis budget"):
        estimate_planar_board_pose(
            _batch(),
            _intrinsics(),
            _tag_map(),
            PlanarPoseEstimatorConfig(
                maximum_tag_reprojection_rmse_px=0.25,
                maximum_hypotheses=1,
            ),
        )
    # C_arm is the frozen eye-on-arm optical-frame spelling.  Generic camera
    # labels remain invalid because they do not establish optical axes.
    assert replace(_intrinsics(), camera_frame="C_arm").camera_frame == "C_arm"
    with pytest.raises(PlanarPoseEstimationError, match="camera_frame"):
        replace(_intrinsics(), camera_frame="camera")


def test_estimator_source_has_no_simulator_or_external_linear_algebra_import() -> None:
    path = (
        Path(__file__).parents[2]
        / "src"
        / "rocell"
        / "vision"
        / "planar_pose_estimator.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imports.update(
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    )
    assert not any(
        module == prefix or module.startswith(prefix + ".")
        for module in imports
        for prefix in ("rocell.simulation", "numpy", "cv2", "scipy")
    )

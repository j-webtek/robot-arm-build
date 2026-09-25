from __future__ import annotations

from pathlib import Path

import pytest

from rocell.models.frames import FrameMismatchError, Point3Mm, Transform
from rocell.simulation import (
    DistortionCoefficients,
    ImagePoint,
    PinholeCameraModel,
    ProjectionError,
    SyntheticFiducialObserver,
    load_rc03_nominal_scene,
)


WORKSPACE = Path(__file__).resolve().parents[3]
RC03_ROOT = WORKSPACE / "active-project" / "RoCell_v0_3"


def overhead_board_to_camera() -> Transform:
    # Camera is centered over the board.  +camera Y points toward board front,
    # and +camera Z points down, preserving a right-handed optical frame.
    return Transform(
        to_frame="camera_optical",
        from_frame="board",
        matrix=(
            1.0,
            0.0,
            0.0,
            -305.0,
            0.0,
            -1.0,
            0.0,
            228.5,
            0.0,
            0.0,
            -1.0,
            600.0,
            0.0,
            0.0,
            0.0,
            1.0,
        ),
    )


def test_pinhole_projects_center_bounds_and_rejects_wrong_side() -> None:
    camera = PinholeCameraModel(640, 480, 500.0, 500.0, 320.0, 240.0)
    center = camera.project(Point3Mm("camera_optical", 0.0, 0.0, 1000.0))
    assert center == ImagePoint(320.0, 240.0, 1000.0, True)
    assert camera.to_dict()["calibration_state"] == (
        "SYNTHETIC_SCENARIO_NOT_PHYSICAL_CALIBRATION"
    )
    outside = camera.project(Point3Mm("camera_optical", 1000.0, 0.0, 1000.0))
    assert outside.u_px == pytest.approx(820.0)
    assert not outside.in_bounds
    with pytest.raises(ProjectionError, match="not in front"):
        camera.project(Point3Mm("camera_optical", 0.0, 0.0, 0.0))
    with pytest.raises(FrameMismatchError):
        camera.project(Point3Mm("board", 0.0, 0.0, 1000.0))


def test_brown_conrady_distortion_matches_equations_without_opencv() -> None:
    camera = PinholeCameraModel(
        640,
        480,
        100.0,
        200.0,
        10.0,
        20.0,
        distortion=DistortionCoefficients(k1=0.1, k2=-0.02, p1=0.003, p2=-0.004, k3=0.01),
    )
    point = Point3Mm("camera_optical", 100.0, 50.0, 1000.0)
    projected = camera.project(point)
    x, y = 0.1, 0.05
    r2 = x * x + y * y
    radial = 1.0 + 0.1 * r2 - 0.02 * r2**2 + 0.01 * r2**3
    expected_x = x * radial + 2.0 * 0.003 * x * y - 0.004 * (r2 + 2.0 * x * x)
    expected_y = y * radial + 0.003 * (r2 + 2.0 * y * y) + 2.0 * -0.004 * x * y
    assert projected.u_px == pytest.approx(100.0 * expected_x + 10.0)
    assert projected.v_px == pytest.approx(200.0 * expected_y + 20.0)


def test_synthetic_observations_are_complete_visible_and_deterministic() -> None:
    scene = load_rc03_nominal_scene(RC03_ROOT)
    camera = PinholeCameraModel(800, 600, 600.0, 600.0, 400.0, 300.0)
    observer = SyntheticFiducialObserver(camera, overhead_board_to_camera())

    first = observer.observe_scene(scene)
    second = observer.observe_scene(scene)
    assert first == second
    assert [item.tag_id for item in first] == [0, 1, 2, 3, 4, 5]
    assert all(item.visible for item in first)
    assert all(item.visibility_reason == "VISIBLE" for item in first)
    assert all(len(item.corners_px) == 4 for item in first)
    assert all(
        item.synthetic_source == "PERFECT_PROJECTION_NO_RASTER_NO_NOISE_NO_OCCLUSION"
        for item in first
    )
    assert first[0].to_dict()["physical_detection_evidence"] is False
    t0 = first[0]
    assert t0.center_px is not None
    assert t0.center_px.u_px == pytest.approx(400.0 - 258.0 * 600.0 / 599.7)
    assert t0.center_px.v_px == pytest.approx(300.0 + 188.5 * 600.0 / 599.7)


def test_tag_behind_camera_is_reported_instead_of_fabricated() -> None:
    scene = load_rc03_nominal_scene(RC03_ROOT, assumed_tag_plane_z_mm=0.0)
    camera = PinholeCameraModel(640, 480, 500.0, 500.0, 320.0, 240.0)
    identity = Transform.identity("board")
    # The injected camera names the board frame here so the identity transform
    # is structurally valid; tag depth is zero and therefore non-projectable.
    board_camera = PinholeCameraModel(
        640, 480, 500.0, 500.0, 320.0, 240.0, optical_frame="board"
    )
    observation = SyntheticFiducialObserver(board_camera, identity).observe_tag(
        scene.fiducials[0]
    )
    assert not observation.visible
    assert observation.visibility_reason == "BEHIND_OR_ON_CAMERA_PLANE"
    assert observation.center_px is None
    assert observation.corners_px == ()
    assert camera.optical_frame == "camera_optical"


def test_observer_accepts_an_injected_projection_model() -> None:
    scene = load_rc03_nominal_scene(RC03_ROOT)

    class OrthographicTestProjector:
        optical_frame = "camera_optical"

        def project(self, point: Point3Mm) -> ImagePoint:
            return ImagePoint(point.x + 400.0, point.y + 300.0, point.z, True)

    observer = SyntheticFiducialObserver(
        OrthographicTestProjector(), overhead_board_to_camera()
    )
    observation = observer.observe_tag(scene.fiducials[0])
    assert observation.visible
    assert observation.center_px is not None
    assert observation.center_px.u_px == pytest.approx(142.0)
    assert observation.center_px.v_px == pytest.approx(488.5)


def test_observer_rejects_transform_projection_frame_disagreement() -> None:
    camera = PinholeCameraModel(640, 480, 500.0, 500.0, 320.0, 240.0)
    with pytest.raises(FrameMismatchError, match="output"):
        SyntheticFiducialObserver(camera, Transform.identity("board"))

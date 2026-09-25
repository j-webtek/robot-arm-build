from __future__ import annotations

import math

import pytest

from rocell.geometry import RigidTransform, Rotation3, Vec3
from rocell.models.frames import FrameMismatchError, Point3Mm, Transform


def _assert_vec_close(actual: Vec3, expected: Vec3, tolerance: float = 1e-9) -> None:
    assert actual.almost_equal(expected, absolute_tolerance=tolerance)


def test_vec3_is_finite_immutable_and_supports_vector_operations() -> None:
    left = Vec3(1, 2, 3)
    right = Vec3(-4, 5, 2)
    assert left + right == Vec3(-3, 7, 5)
    assert left - right == Vec3(5, -3, 1)
    assert left.scaled(2) == Vec3(2, 4, 6)
    assert left.dot(right) == 12
    assert left.cross(right) == Vec3(-11, -14, 13)
    assert Vec3(3, 0, 4).norm == 5
    assert Vec3(3, 0, 4).normalized().almost_equal(Vec3(0.6, 0, 0.8))
    with pytest.raises((AttributeError, TypeError)):
        left.x = 7  # type: ignore[misc]


@pytest.mark.parametrize("value", [True, math.nan, math.inf, "1"])
def test_vec3_rejects_nonfinite_or_non_numeric_components(value: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        Vec3(value, 0, 0)  # type: ignore[arg-type]


def test_vec3_rejects_wrong_length_and_zero_normalization() -> None:
    with pytest.raises(ValueError, match="exactly three"):
        Vec3.from_iterable((1, 2))
    with pytest.raises(ValueError, match="zero-length"):
        Vec3.zero().normalized()


def test_rpy_and_axis_angle_use_right_handed_radians() -> None:
    yaw = Rotation3.from_rpy(0, 0, math.pi / 2)
    axis_angle = Rotation3.from_axis_angle(Vec3(0, 0, 2), math.pi / 2)
    expected = Vec3(0, 1, 0)
    _assert_vec_close(yaw.apply(Vec3(1, 0, 0)), expected)
    _assert_vec_close(axis_angle.apply(Vec3(1, 0, 0)), expected)
    assert yaw.almost_equal(axis_angle)


def test_full_urdf_rpy_formula_and_rotation_inverse() -> None:
    rotation = Rotation3.from_rpy(0.21, -0.32, 0.73)
    vector = Vec3(3.5, -9.0, 2.25)
    recovered = rotation.inverse().apply(rotation.apply(vector))
    _assert_vec_close(recovered, vector)
    assert rotation.compose(rotation.inverse()).almost_equal(Rotation3.identity())


def test_rotation_rejects_invalid_matrix_and_zero_axis() -> None:
    with pytest.raises(ValueError, match="orthonormal"):
        Rotation3((2, 0, 0, 0, 1, 0, 0, 0, 1))
    with pytest.raises(ValueError, match="right-handed"):
        Rotation3((-1, 0, 0, 0, 1, 0, 0, 0, 1))
    with pytest.raises(ValueError, match="zero-length"):
        Rotation3.from_axis_angle(Vec3.zero(), 0)


def test_rigid_transform_composition_inverse_and_framed_point() -> None:
    world_t_arm = RigidTransform(
        "world",
        "arm",
        Rotation3.from_axis_angle(Vec3(0, 0, 1), math.pi / 2),
        Vec3(100, 20, 5),
    )
    arm_t_tool = RigidTransform(
        "arm",
        "tool",
        Rotation3.identity(),
        Vec3(10, 0, 2),
    )
    world_t_tool = world_t_arm.compose(arm_t_tool)
    assert world_t_tool.parent_frame == "world"
    assert world_t_tool.child_frame == "tool"
    _assert_vec_close(world_t_tool.translation_mm, Vec3(100, 30, 7))

    point_world = world_t_tool.transform_point(Point3Mm("tool", 2, 0, 1))
    assert point_world.frame == "world"
    assert point_world.x == pytest.approx(100)
    assert point_world.y == pytest.approx(32)
    assert point_world.z == pytest.approx(8)
    recovered = world_t_tool.inverse().transform_point(point_world)
    assert recovered.x == pytest.approx(2)
    assert recovered.y == pytest.approx(0)
    assert recovered.z == pytest.approx(1)
    assert recovered.frame == "tool"


def test_rigid_transform_enforces_direction_and_type() -> None:
    world_t_arm = RigidTransform.identity("world")
    camera_t_optical = RigidTransform.identity("camera")
    with pytest.raises(FrameMismatchError, match="Cannot compose"):
        world_t_arm.compose(camera_t_optical)
    with pytest.raises(FrameMismatchError, match="expected world"):
        world_t_arm.transform_point(Point3Mm("other", 0, 0, 0))
    with pytest.raises(TypeError, match="position_mm"):
        world_t_arm.transform_position_mm((0, 0, 0))  # type: ignore[arg-type]


def test_adapter_is_lossless_and_keeps_existing_to_t_from_direction() -> None:
    established = Transform(
        to_frame="base",
        from_frame="camera",
        matrix=(
            0, -1, 0, 40,
            1, 0, 0, 50,
            0, 0, 1, 60,
            0, 0, 0, 1,
        ),
    )
    rigid = RigidTransform.from_transform(established)
    assert rigid.parent_frame == established.to_frame
    assert rigid.child_frame == established.from_frame
    assert rigid.to_transform() == established
    assert rigid.transform_point(Point3Mm("camera", 1, 0, 0)) == Point3Mm(
        "base", 40, 51, 60
    )


def test_transform_constructor_names_units_explicitly() -> None:
    transform = RigidTransform.from_rpy_translation_mm(
        "parent",
        "child",
        translation_mm=Vec3(1, 2, 3),
        roll_rad=0.1,
        pitch_rad=0.2,
        yaw_rad=0.3,
    )
    assert transform.translation_mm == Vec3(1, 2, 3)
    assert transform.rotation.almost_equal(Rotation3.from_rpy(0.1, 0.2, 0.3))

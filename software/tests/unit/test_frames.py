from __future__ import annotations

import pytest

from rocell.models.frames import FrameMismatchError, Point3Mm, Transform


def _translation(to_frame: str, from_frame: str, x: float, y: float, z: float) -> Transform:
    return Transform(
        to_frame,
        from_frame,
        (
            1, 0, 0, x,
            0, 1, 0, y,
            0, 0, 1, z,
            0, 0, 0, 1,
        ),
    )


def test_transform_composition_and_inverse_preserve_frames() -> None:
    r_t_b = _translation("R", "B", 10, 0, 0)
    b_t_k = _translation("B", "K", 0, 20, 0)
    r_t_k = r_t_b.compose(b_t_k)
    point = r_t_k.transform_point(Point3Mm("K", 1, 2, 3))
    assert point == Point3Mm("R", 11, 22, 3)
    recovered = r_t_k.inverse().transform_point(point)
    assert recovered == Point3Mm("K", 1, 2, 3)


def test_transform_rejects_wrong_direction() -> None:
    r_t_b = _translation("R", "B", 0, 0, 0)
    c_t_f = _translation("C", "F", 0, 0, 0)
    with pytest.raises(FrameMismatchError):
        r_t_b.compose(c_t_f)
    with pytest.raises(FrameMismatchError):
        r_t_b.transform_point(Point3Mm("K", 0, 0, 0))


def test_transform_rejects_non_homogeneous_last_row() -> None:
    with pytest.raises(ValueError):
        Transform("R", "B", tuple([1.0] * 16))


def test_transform_rejects_non_rigid_or_left_handed_rotation() -> None:
    with pytest.raises(ValueError, match="orthonormal"):
        Transform(
            "R",
            "B",
            (2, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1),
        )
    with pytest.raises(ValueError, match="right-handed"):
        Transform(
            "R",
            "B",
            (-1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1),
        )

"""Right-handed frame-labelled transforms using millimetres internally."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

from .units import finite_real


class FrameMismatchError(ValueError):
    """Two frame-labelled values cannot be composed safely."""


def _frame_name(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty frame name")
    return value.strip()


def _matrix4(values: Iterable[object]) -> tuple[float, ...]:
    result = tuple(finite_real(value, name="matrix element") for value in values)
    if len(result) != 16:
        raise ValueError("A transform matrix must contain exactly 16 values")
    expected_last_row = (0.0, 0.0, 0.0, 1.0)
    if any(abs(result[12 + index] - expected) > 1e-9 for index, expected in enumerate(expected_last_row)):
        raise ValueError("A rigid homogeneous transform must end with [0, 0, 0, 1]")
    rotation = (
        result[0], result[1], result[2],
        result[4], result[5], result[6],
        result[8], result[9], result[10],
    )
    for left_row in range(3):
        for right_row in range(3):
            dot = sum(
                rotation[left_row * 3 + column] * rotation[right_row * 3 + column]
                for column in range(3)
            )
            expected = 1.0 if left_row == right_row else 0.0
            if abs(dot - expected) > 1e-6:
                raise ValueError("Transform rotation must be orthonormal")
    determinant = (
        rotation[0] * (rotation[4] * rotation[8] - rotation[5] * rotation[7])
        - rotation[1] * (rotation[3] * rotation[8] - rotation[5] * rotation[6])
        + rotation[2] * (rotation[3] * rotation[7] - rotation[4] * rotation[6])
    )
    if abs(determinant - 1.0) > 1e-6:
        raise ValueError("Transform rotation must be right-handed with determinant +1")
    return result


@dataclass(frozen=True, slots=True)
class Point3Mm:
    frame: str
    x: float
    y: float
    z: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "frame", _frame_name(self.frame, "point frame"))
        object.__setattr__(self, "x", finite_real(self.x, name="point x"))
        object.__setattr__(self, "y", finite_real(self.y, name="point y"))
        object.__setattr__(self, "z", finite_real(self.z, name="point z"))


@dataclass(frozen=True, slots=True)
class Transform:
    """``to_T_from`` mapping points from ``from_frame`` into ``to_frame``."""

    to_frame: str
    from_frame: str
    matrix: tuple[float, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "to_frame", _frame_name(self.to_frame, "to_frame"))
        object.__setattr__(self, "from_frame", _frame_name(self.from_frame, "from_frame"))
        object.__setattr__(self, "matrix", _matrix4(self.matrix))

    @classmethod
    def identity(cls, frame: str) -> "Transform":
        return cls(
            to_frame=frame,
            from_frame=frame,
            matrix=(
                1.0, 0.0, 0.0, 0.0,
                0.0, 1.0, 0.0, 0.0,
                0.0, 0.0, 1.0, 0.0,
                0.0, 0.0, 0.0, 1.0,
            ),
        )

    def compose(self, right: "Transform") -> "Transform":
        """Return ``self * right`` after checking the shared frame."""

        if self.from_frame != right.to_frame:
            raise FrameMismatchError(
                f"Cannot compose {self.to_frame}_T_{self.from_frame} with "
                f"{right.to_frame}_T_{right.from_frame}"
            )
        left_matrix = self.matrix
        right_matrix = right.matrix
        product = tuple(
            sum(left_matrix[row * 4 + k] * right_matrix[k * 4 + column] for k in range(4))
            for row in range(4)
            for column in range(4)
        )
        return Transform(self.to_frame, right.from_frame, product)

    def inverse(self) -> "Transform":
        """Invert a rigid transform by transposing its rotation block."""

        m = self.matrix
        rotation_t = (
            m[0], m[4], m[8],
            m[1], m[5], m[9],
            m[2], m[6], m[10],
        )
        translation = (m[3], m[7], m[11])
        inverse_translation = tuple(
            -sum(rotation_t[row * 3 + column] * translation[column] for column in range(3))
            for row in range(3)
        )
        return Transform(
            to_frame=self.from_frame,
            from_frame=self.to_frame,
            matrix=(
                rotation_t[0], rotation_t[1], rotation_t[2], inverse_translation[0],
                rotation_t[3], rotation_t[4], rotation_t[5], inverse_translation[1],
                rotation_t[6], rotation_t[7], rotation_t[8], inverse_translation[2],
                0.0, 0.0, 0.0, 1.0,
            ),
        )

    def transform_point(self, point: Point3Mm) -> Point3Mm:
        if point.frame != self.from_frame:
            raise FrameMismatchError(
                f"Point is in {point.frame}, expected {self.from_frame}"
            )
        m = self.matrix
        coordinates = (point.x, point.y, point.z)
        output = tuple(
            sum(m[row * 4 + column] * coordinates[column] for column in range(3))
            + m[row * 4 + 3]
            for row in range(3)
        )
        if any(not math.isfinite(value) for value in output):
            raise ValueError("Transform produced a nonfinite point")
        return Point3Mm(self.to_frame, *output)

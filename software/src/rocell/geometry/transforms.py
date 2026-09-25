"""Immutable, dependency-free three-dimensional rigid-body geometry.

Translations and points are always millimetres.  Angles passed to rotation
constructors are always radians.  ``RigidTransform(parent, child, ...)`` is
``parent_T_child`` and therefore maps child-frame coordinates into the parent
frame.  This is deliberately identical to the existing ``to_T_from``
convention in :mod:`rocell.models.frames`.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

from rocell.models.frames import FrameMismatchError, Point3Mm, Transform
from rocell.models.units import finite_real


_ORTHONORMAL_TOLERANCE = 1e-9


def _frame_name(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty frame name")
    return value.strip()


@dataclass(frozen=True, slots=True)
class Vec3:
    """A finite three-vector.

    ``Vec3`` itself is dimension-agnostic.  Field and method names at physical
    boundaries carry the unit, for example ``translation_mm`` and
    ``transform_position_mm``.
    """

    x: float
    y: float
    z: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "x", finite_real(self.x, name="vector x"))
        object.__setattr__(self, "y", finite_real(self.y, name="vector y"))
        object.__setattr__(self, "z", finite_real(self.z, name="vector z"))

    @classmethod
    def zero(cls) -> "Vec3":
        return cls(0.0, 0.0, 0.0)

    @classmethod
    def from_iterable(cls, values: Iterable[object]) -> "Vec3":
        items = tuple(values)
        if len(items) != 3:
            raise ValueError("A Vec3 requires exactly three values")
        return cls(
            finite_real(items[0], name="vector x"),
            finite_real(items[1], name="vector y"),
            finite_real(items[2], name="vector z"),
        )

    def __add__(self, other: object) -> "Vec3":
        if not isinstance(other, Vec3):
            return NotImplemented
        return Vec3(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: object) -> "Vec3":
        if not isinstance(other, Vec3):
            return NotImplemented
        return Vec3(self.x - other.x, self.y - other.y, self.z - other.z)

    def scaled(self, scalar: object) -> "Vec3":
        factor = finite_real(scalar, name="vector scale")
        return Vec3(self.x * factor, self.y * factor, self.z * factor)

    def dot(self, other: "Vec3") -> float:
        if not isinstance(other, Vec3):
            raise TypeError("dot product requires another Vec3")
        return self.x * other.x + self.y * other.y + self.z * other.z

    def cross(self, other: "Vec3") -> "Vec3":
        if not isinstance(other, Vec3):
            raise TypeError("cross product requires another Vec3")
        return Vec3(
            self.y * other.z - self.z * other.y,
            self.z * other.x - self.x * other.z,
            self.x * other.y - self.y * other.x,
        )

    @property
    def norm(self) -> float:
        return math.sqrt(self.dot(self))

    def normalized(self) -> "Vec3":
        magnitude = self.norm
        if magnitude <= 1e-15:
            raise ValueError("Cannot normalize a zero-length vector")
        return self.scaled(1.0 / magnitude)

    def almost_equal(self, other: "Vec3", *, absolute_tolerance: float = 1e-9) -> bool:
        if not isinstance(other, Vec3):
            return False
        tolerance = finite_real(absolute_tolerance, name="absolute_tolerance")
        if tolerance < 0.0:
            raise ValueError("absolute_tolerance must be non-negative")
        return (
            abs(self.x - other.x) <= tolerance
            and abs(self.y - other.y) <= tolerance
            and abs(self.z - other.z) <= tolerance
        )


def _validated_rotation(values: Iterable[object]) -> tuple[float, ...]:
    matrix = tuple(finite_real(value, name="rotation element") for value in values)
    if len(matrix) != 9:
        raise ValueError("A Rotation3 matrix requires exactly nine values")

    for left_row in range(3):
        for right_row in range(3):
            dot = sum(
                matrix[left_row * 3 + column] * matrix[right_row * 3 + column]
                for column in range(3)
            )
            expected = 1.0 if left_row == right_row else 0.0
            if abs(dot - expected) > _ORTHONORMAL_TOLERANCE:
                raise ValueError("Rotation matrix must be orthonormal")

    determinant = (
        matrix[0] * (matrix[4] * matrix[8] - matrix[5] * matrix[7])
        - matrix[1] * (matrix[3] * matrix[8] - matrix[5] * matrix[6])
        + matrix[2] * (matrix[3] * matrix[7] - matrix[4] * matrix[6])
    )
    if abs(determinant - 1.0) > _ORTHONORMAL_TOLERANCE:
        raise ValueError("Rotation matrix must be right-handed with determinant +1")
    return matrix


@dataclass(frozen=True, slots=True)
class Rotation3:
    """A row-major, right-handed 3x3 rotation matrix."""

    matrix: tuple[float, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "matrix", _validated_rotation(self.matrix))

    @classmethod
    def identity(cls) -> "Rotation3":
        return cls((1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0))

    @classmethod
    def from_rpy(cls, roll_rad: object, pitch_rad: object, yaw_rad: object) -> "Rotation3":
        """Construct the URDF fixed-axis RPY rotation ``Rz(yaw) Ry(pitch) Rx(roll)``."""

        roll = finite_real(roll_rad, name="roll_rad")
        pitch = finite_real(pitch_rad, name="pitch_rad")
        yaw = finite_real(yaw_rad, name="yaw_rad")
        cr, sr = math.cos(roll), math.sin(roll)
        cp, sp = math.cos(pitch), math.sin(pitch)
        cy, sy = math.cos(yaw), math.sin(yaw)
        return cls(
            (
                cy * cp,
                cy * sp * sr - sy * cr,
                cy * sp * cr + sy * sr,
                sy * cp,
                sy * sp * sr + cy * cr,
                sy * sp * cr - cy * sr,
                -sp,
                cp * sr,
                cp * cr,
            )
        )

    @classmethod
    def from_axis_angle(cls, axis: Vec3, angle_rad: object) -> "Rotation3":
        if not isinstance(axis, Vec3):
            raise TypeError("axis must be a Vec3")
        angle = finite_real(angle_rad, name="angle_rad")
        unit = axis.normalized()
        x, y, z = unit.x, unit.y, unit.z
        cosine = math.cos(angle)
        sine = math.sin(angle)
        one_minus_cosine = 1.0 - cosine
        return cls(
            (
                cosine + x * x * one_minus_cosine,
                x * y * one_minus_cosine - z * sine,
                x * z * one_minus_cosine + y * sine,
                y * x * one_minus_cosine + z * sine,
                cosine + y * y * one_minus_cosine,
                y * z * one_minus_cosine - x * sine,
                z * x * one_minus_cosine - y * sine,
                z * y * one_minus_cosine + x * sine,
                cosine + z * z * one_minus_cosine,
            )
        )

    def compose(self, right: "Rotation3") -> "Rotation3":
        """Return matrix product ``self * right``."""

        if not isinstance(right, Rotation3):
            raise TypeError("rotation composition requires another Rotation3")
        left_matrix = self.matrix
        right_matrix = right.matrix
        return Rotation3(
            tuple(
                sum(
                    left_matrix[row * 3 + index] * right_matrix[index * 3 + column]
                    for index in range(3)
                )
                for row in range(3)
                for column in range(3)
            )
        )

    def inverse(self) -> "Rotation3":
        matrix = self.matrix
        return Rotation3(
            (
                matrix[0], matrix[3], matrix[6],
                matrix[1], matrix[4], matrix[7],
                matrix[2], matrix[5], matrix[8],
            )
        )

    def apply(self, vector: Vec3) -> Vec3:
        if not isinstance(vector, Vec3):
            raise TypeError("rotation application requires a Vec3")
        matrix = self.matrix
        coordinates = (vector.x, vector.y, vector.z)
        return Vec3(
            *(sum(matrix[row * 3 + column] * coordinates[column] for column in range(3)) for row in range(3))
        )

    def almost_equal(self, other: "Rotation3", *, absolute_tolerance: float = 1e-9) -> bool:
        if not isinstance(other, Rotation3):
            return False
        tolerance = finite_real(absolute_tolerance, name="absolute_tolerance")
        if tolerance < 0.0:
            raise ValueError("absolute_tolerance must be non-negative")
        return all(abs(left - right) <= tolerance for left, right in zip(self.matrix, other.matrix))


@dataclass(frozen=True, slots=True)
class RigidTransform:
    """``parent_T_child`` with millimetre translation."""

    parent_frame: str
    child_frame: str
    rotation: Rotation3
    translation_mm: Vec3

    def __post_init__(self) -> None:
        object.__setattr__(self, "parent_frame", _frame_name(self.parent_frame, "parent_frame"))
        object.__setattr__(self, "child_frame", _frame_name(self.child_frame, "child_frame"))
        if not isinstance(self.rotation, Rotation3):
            raise TypeError("rotation must be a Rotation3")
        if not isinstance(self.translation_mm, Vec3):
            raise TypeError("translation_mm must be a Vec3")

    @classmethod
    def identity(cls, frame: str) -> "RigidTransform":
        return cls(frame, frame, Rotation3.identity(), Vec3.zero())

    @classmethod
    def from_rpy_translation_mm(
        cls,
        parent_frame: str,
        child_frame: str,
        *,
        translation_mm: Vec3,
        roll_rad: object = 0.0,
        pitch_rad: object = 0.0,
        yaw_rad: object = 0.0,
    ) -> "RigidTransform":
        return cls(
            parent_frame,
            child_frame,
            Rotation3.from_rpy(roll_rad, pitch_rad, yaw_rad),
            translation_mm,
        )

    @classmethod
    def from_transform(cls, transform: Transform) -> "RigidTransform":
        """Convert the established ``to_T_from`` model without changing direction."""

        if not isinstance(transform, Transform):
            raise TypeError("transform must be a rocell.models.frames.Transform")
        matrix = transform.matrix
        return cls(
            parent_frame=transform.to_frame,
            child_frame=transform.from_frame,
            rotation=Rotation3(
                (
                    matrix[0], matrix[1], matrix[2],
                    matrix[4], matrix[5], matrix[6],
                    matrix[8], matrix[9], matrix[10],
                )
            ),
            translation_mm=Vec3(matrix[3], matrix[7], matrix[11]),
        )

    def to_transform(self) -> Transform:
        """Convert to the established ``Transform(to_frame, from_frame)`` contract."""

        rotation = self.rotation.matrix
        translation = self.translation_mm
        return Transform(
            to_frame=self.parent_frame,
            from_frame=self.child_frame,
            matrix=(
                rotation[0], rotation[1], rotation[2], translation.x,
                rotation[3], rotation[4], rotation[5], translation.y,
                rotation[6], rotation[7], rotation[8], translation.z,
                0.0, 0.0, 0.0, 1.0,
            ),
        )

    def compose(self, right: "RigidTransform") -> "RigidTransform":
        """Return ``self * right`` after checking the shared frame."""

        if not isinstance(right, RigidTransform):
            raise TypeError("transform composition requires another RigidTransform")
        if self.child_frame != right.parent_frame:
            raise FrameMismatchError(
                f"Cannot compose {self.parent_frame}_T_{self.child_frame} with "
                f"{right.parent_frame}_T_{right.child_frame}"
            )
        return RigidTransform(
            parent_frame=self.parent_frame,
            child_frame=right.child_frame,
            rotation=self.rotation.compose(right.rotation),
            translation_mm=self.translation_mm + self.rotation.apply(right.translation_mm),
        )

    def inverse(self) -> "RigidTransform":
        inverse_rotation = self.rotation.inverse()
        return RigidTransform(
            parent_frame=self.child_frame,
            child_frame=self.parent_frame,
            rotation=inverse_rotation,
            translation_mm=inverse_rotation.apply(self.translation_mm).scaled(-1.0),
        )

    def transform_point(self, point: Point3Mm) -> Point3Mm:
        """Transform a frame-labelled millimetre point, checking its direction."""

        if not isinstance(point, Point3Mm):
            raise TypeError("point must be a rocell.models.frames.Point3Mm")
        if point.frame != self.child_frame:
            raise FrameMismatchError(f"Point is in {point.frame}, expected {self.child_frame}")
        transformed = self.transform_position_mm(Vec3(point.x, point.y, point.z))
        return Point3Mm(self.parent_frame, transformed.x, transformed.y, transformed.z)

    def transform_position_mm(self, position_mm: Vec3) -> Vec3:
        """Transform an unlabelled position after the caller has established its frame."""

        if not isinstance(position_mm, Vec3):
            raise TypeError("position_mm must be a Vec3")
        return self.rotation.apply(position_mm) + self.translation_mm

    def almost_equal(self, other: "RigidTransform", *, absolute_tolerance: float = 1e-9) -> bool:
        if not isinstance(other, RigidTransform):
            return False
        return (
            self.parent_frame == other.parent_frame
            and self.child_frame == other.child_frame
            and self.rotation.almost_equal(other.rotation, absolute_tolerance=absolute_tolerance)
            and self.translation_mm.almost_equal(other.translation_mm, absolute_tolerance=absolute_tolerance)
        )

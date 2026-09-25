"""Differential FK checks using an implementation independent of rocell.geometry.

The oracle intentionally reparses the pinned XML with ElementTree and performs
plain-list homogeneous-matrix math.  It can catch transform-order, RPY, axis,
sign, unit, and branch-selection defects shared by higher RoCell services.  It
does not prove that the vendor projection matches the received physical arm.
"""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
from xml.etree import ElementTree

import pytest

from rocell.geometry import JointPosition, load_urdf


WORKSPACE = Path(__file__).resolve().parents[3]
MODEL_PATH = WORKSPACE / "software/models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf"
TARGET_LINK = "hand_tcp"


def _identity() -> list[list[float]]:
    return [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]


def _multiply(left: list[list[float]], right: list[list[float]]) -> list[list[float]]:
    return [
        [sum(left[row][k] * right[k][column] for k in range(4)) for column in range(4)]
        for row in range(4)
    ]


def _origin(xyz: tuple[float, float, float], rpy: tuple[float, float, float]) -> list[list[float]]:
    """URDF fixed origin: translation followed by extrinsic RPY (Rz*Ry*Rx)."""

    roll, pitch, yaw = rpy
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    result = _identity()
    result[0][:3] = [cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr]
    result[1][:3] = [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr]
    result[2][:3] = [-sp, cp * sr, cp * cr]
    result[0][3], result[1][3], result[2][3] = xyz
    return result


def _axis_angle(axis: tuple[float, float, float], angle: float) -> list[list[float]]:
    norm = math.sqrt(sum(value * value for value in axis))
    x, y, z = (value / norm for value in axis)
    c, s, one_minus_c = math.cos(angle), math.sin(angle), 1.0 - math.cos(angle)
    result = _identity()
    result[0][:3] = [c + x * x * one_minus_c, x * y * one_minus_c - z * s, x * z * one_minus_c + y * s]
    result[1][:3] = [y * x * one_minus_c + z * s, c + y * y * one_minus_c, y * z * one_minus_c - x * s]
    result[2][:3] = [z * x * one_minus_c - y * s, z * y * one_minus_c + x * s, c + z * z * one_minus_c]
    return result


def _vector(raw: str | None, default: str) -> tuple[float, float, float]:
    values = tuple(float(item) for item in (raw or default).split())
    assert len(values) == 3
    return values  # type: ignore[return-value]


def _oracle_chain() -> tuple[tuple[str, str, tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]], ...]:
    root = ElementTree.parse(MODEL_PATH).getroot()
    by_child: dict[str, tuple[str, str, tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]] = {}
    for xml_joint in root.findall("joint"):
        parent = xml_joint.find("parent")
        child = xml_joint.find("child")
        assert parent is not None and child is not None
        origin = xml_joint.find("origin")
        axis = xml_joint.find("axis")
        child_name = child.attrib["link"]
        by_child[child_name] = (
            xml_joint.attrib["name"],
            parent.attrib["link"],
            _vector(None if origin is None else origin.attrib.get("xyz"), "0 0 0"),
            _vector(None if origin is None else origin.attrib.get("rpy"), "0 0 0"),
            _vector(None if axis is None else axis.attrib.get("xyz"), "0 0 1"),
        )
    reverse: list[tuple[str, str, tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]] = []
    link = TARGET_LINK
    while link in by_child:
        edge = by_child[link]
        reverse.append(edge)
        link = edge[1]
    assert link == "world"
    return tuple(reversed(reverse))


def _oracle_fk(joints: dict[str, float]) -> list[list[float]]:
    transform = _identity()
    for name, _parent, xyz, rpy, axis in _oracle_chain():
        transform = _multiply(transform, _origin(xyz, rpy))
        if name in joints:
            transform = _multiply(transform, _axis_angle(axis, joints[name]))
    return transform


def _sample_unit(ordinal: int, joint_name: str) -> float:
    digest = hashlib.sha256(f"rocell-independent-fk-v1:{ordinal}:{joint_name}".encode("ascii")).digest()
    return int.from_bytes(digest[:8], "big") / float((1 << 64) - 1)


def test_independent_xml_matrix_oracle_matches_128_joint_states() -> None:
    model = load_urdf(MODEL_PATH)
    bounds = {
        joint.name: (joint.limit.lower.value, joint.limit.upper.value)
        for joint in model.joints
        if joint.is_movable
        and joint.limit is not None
        and joint.limit.lower is not None
        and joint.limit.upper is not None
    }
    assert set(bounds) == set(model.movable_joint_names)

    for ordinal in range(128):
        positions = {
            name: lower + (upper - lower) * _sample_unit(ordinal, name)
            for name, (lower, upper) in bounds.items()
        }
        oracle = _oracle_fk(positions)
        actual = model.forward_kinematics(
            {name: JointPosition.radians(value) for name, value in positions.items()}
        )[TARGET_LINK]

        assert actual.translation_mm.x == pytest.approx(oracle[0][3] * 1000.0, abs=1e-9)
        assert actual.translation_mm.y == pytest.approx(oracle[1][3] * 1000.0, abs=1e-9)
        assert actual.translation_mm.z == pytest.approx(oracle[2][3] * 1000.0, abs=1e-9)
        expected_rotation = tuple(
            oracle[row][column] for row in range(3) for column in range(3)
        )
        assert actual.rotation.matrix == pytest.approx(expected_rotation, abs=1e-11)


def test_oracle_scope_is_algorithmic_not_physical_evidence() -> None:
    model_bytes = MODEL_PATH.read_bytes()
    assert hashlib.sha256(model_bytes).hexdigest() == (
        "a565718e7d74b07702802cf41eb9549a6e38e50b5e80aa9b887ab1ae3d0d8190"
    )
    # This statement is deliberately executable documentation: the independent
    # algorithm still consumes the same pinned, unmeasured projection.
    physical_model_validated = False
    assert physical_model_validated is False

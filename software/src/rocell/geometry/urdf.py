"""Strict URDF tree parsing and deterministic forward kinematics.

URDF linear units are metres; this module converts every origin, prismatic
position, and prismatic velocity to millimetres at the parse boundary.  URDF
angular units are radians and remain radians.  Callers must supply typed
``JointPosition`` values, preventing accidental mixing of those dimensions.

Only fixed, revolute, continuous, and prismatic joints are supported.  Models
that need planar, floating, or mimic-joint semantics are rejected rather than
simulated incorrectly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
from pathlib import Path
from types import MappingProxyType
from typing import Mapping
import xml.etree.ElementTree as ElementTree

from rocell.models.units import finite_real

from .transforms import RigidTransform, Rotation3, Vec3


_SUPPORTED_JOINT_TYPES = frozenset({"fixed", "revolute", "continuous", "prismatic"})


class UrdfError(ValueError):
    """Base error for a model that cannot be interpreted safely."""


class UrdfParseError(UrdfError):
    """URDF XML or a required typed field is invalid."""


class UrdfTopologyError(UrdfError):
    """URDF links and joints do not form one unambiguous rooted tree."""


class JointStateError(UrdfError):
    """A forward-kinematics joint state is incomplete, mistyped, or out of range."""


class JointPositionUnit(str, Enum):
    RADIAN = "radian"
    MILLIMETRE = "millimetre"


@dataclass(frozen=True, slots=True)
class JointPosition:
    """A typed joint displacement: radians or millimetres."""

    value: float
    unit: JointPositionUnit

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", finite_real(self.value, name="joint position"))
        if not isinstance(self.unit, JointPositionUnit):
            raise TypeError("unit must be a JointPositionUnit")

    @classmethod
    def radians(cls, value: object) -> "JointPosition":
        return cls(finite_real(value, name="joint radians"), JointPositionUnit.RADIAN)

    @classmethod
    def millimetres(cls, value: object) -> "JointPosition":
        return cls(finite_real(value, name="joint millimetres"), JointPositionUnit.MILLIMETRE)


@dataclass(frozen=True, slots=True)
class JointVelocity:
    """A non-negative URDF velocity field in its explicit per-second unit.

    Some upstream robot descriptions, including Waveshare's RoArm-M3 model,
    use zero as an unspecified placeholder.  Zero is retained faithfully but
    ``usable_for_timing`` is false, so consumers cannot treat it as a motion
    speed or invent one.
    """

    value_per_second: float
    unit: JointPositionUnit

    def __post_init__(self) -> None:
        value = finite_real(self.value_per_second, name="joint velocity")
        if value < 0.0:
            raise ValueError("joint velocity must be non-negative")
        if not isinstance(self.unit, JointPositionUnit):
            raise TypeError("unit must be a JointPositionUnit")
        object.__setattr__(self, "value_per_second", value)

    @property
    def usable_for_timing(self) -> bool:
        return self.value_per_second > 0.0


@dataclass(frozen=True, slots=True)
class JointLimit:
    """A URDF joint limit converted to internal units.

    Bounded joints have typed ``lower`` and ``upper`` positions.  Continuous
    joints deliberately have neither.  ``max_effort`` retains the URDF's
    actuator-specific unit because URDF does not encode an effort dimension.
    """

    lower: JointPosition | None
    upper: JointPosition | None
    max_effort: float
    max_velocity: JointVelocity

    def __post_init__(self) -> None:
        if (self.lower is None) != (self.upper is None):
            raise ValueError("joint lower and upper limits must both be present or absent")
        if self.lower is not None:
            if not isinstance(self.lower, JointPosition) or not isinstance(self.upper, JointPosition):
                raise TypeError("joint bounds must be JointPosition values")
            if self.lower.unit is not self.upper.unit:
                raise ValueError("joint bound units must match")
            if self.lower.value > self.upper.value:
                raise ValueError("joint lower limit exceeds upper limit")
        effort = finite_real(self.max_effort, name="joint max_effort")
        if effort < 0.0:
            raise ValueError("joint max_effort must be non-negative")
        if not isinstance(self.max_velocity, JointVelocity):
            raise TypeError("max_velocity must be a JointVelocity")
        object.__setattr__(self, "max_effort", effort)

    @property
    def position_unit(self) -> JointPositionUnit:
        return self.max_velocity.unit

    def validate(self, position: JointPosition, *, joint_name: str) -> None:
        if not isinstance(position, JointPosition):
            raise JointStateError(f"Joint {joint_name!r} position must be a JointPosition")
        if position.unit is not self.position_unit:
            raise JointStateError(
                f"Joint {joint_name!r} requires {self.position_unit.value}, got {position.unit.value}"
            )
        if self.lower is not None and position.value < self.lower.value:
            raise JointStateError(
                f"Joint {joint_name!r} position {position.value} is below limit {self.lower.value}"
            )
        if self.upper is not None and position.value > self.upper.value:
            raise JointStateError(
                f"Joint {joint_name!r} position {position.value} is above limit {self.upper.value}"
            )


@dataclass(frozen=True, slots=True)
class UrdfLink:
    name: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _name(self.name, "link name"))


@dataclass(frozen=True, slots=True)
class UrdfJoint:
    name: str
    joint_type: str
    parent_link: str
    child_link: str
    origin: RigidTransform
    axis: Vec3 | None
    limit: JointLimit | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _name(self.name, "joint name"))
        joint_type = _name(self.joint_type, "joint type").lower()
        if joint_type not in _SUPPORTED_JOINT_TYPES:
            raise UrdfParseError(f"Unsupported joint type {joint_type!r}")
        object.__setattr__(self, "joint_type", joint_type)
        object.__setattr__(self, "parent_link", _name(self.parent_link, "parent link"))
        object.__setattr__(self, "child_link", _name(self.child_link, "child link"))
        if self.parent_link == self.child_link:
            raise UrdfTopologyError(f"Joint {self.name!r} connects a link to itself")
        if not isinstance(self.origin, RigidTransform):
            raise TypeError("joint origin must be a RigidTransform")
        if (
            self.origin.parent_frame != self.parent_link
            or self.origin.child_frame != self.child_link
        ):
            raise UrdfParseError(
                f"Joint {self.name!r} origin frames do not match its parent and child links"
            )

        if joint_type == "fixed":
            if self.axis is not None or self.limit is not None:
                raise UrdfParseError(f"Fixed joint {self.name!r} cannot have motion data")
            return

        if not isinstance(self.axis, Vec3):
            raise UrdfParseError(f"Joint {self.name!r} requires an axis")
        normalized_axis = self.axis.normalized()
        object.__setattr__(self, "axis", normalized_axis)
        if not isinstance(self.limit, JointLimit):
            raise UrdfParseError(f"Joint {self.name!r} requires a complete limit")

        expected_unit = (
            JointPositionUnit.MILLIMETRE
            if joint_type == "prismatic"
            else JointPositionUnit.RADIAN
        )
        if self.limit.position_unit is not expected_unit:
            raise UrdfParseError(f"Joint {self.name!r} limit has the wrong unit")
        if joint_type == "continuous" and self.limit.lower is not None:
            raise UrdfParseError(f"Continuous joint {self.name!r} cannot have position bounds")
        if joint_type in {"revolute", "prismatic"} and self.limit.lower is None:
            raise UrdfParseError(f"Bounded joint {self.name!r} requires lower and upper limits")

    @property
    def is_movable(self) -> bool:
        return self.joint_type != "fixed"

    def transform_at(self, position: JointPosition | None) -> RigidTransform:
        """Return ``parent_link_T_child_link`` at the supplied typed position."""

        if self.joint_type == "fixed":
            if position is not None:
                raise JointStateError(f"Fixed joint {self.name!r} must not receive a position")
            return self.origin

        if position is None:
            raise JointStateError(f"Movable joint {self.name!r} is missing a position")
        assert self.limit is not None
        assert self.axis is not None
        self.limit.validate(position, joint_name=self.name)

        if self.joint_type in {"revolute", "continuous"}:
            motion_rotation = Rotation3.from_axis_angle(self.axis, position.value)
            return RigidTransform(
                parent_frame=self.parent_link,
                child_frame=self.child_link,
                rotation=self.origin.rotation.compose(motion_rotation),
                translation_mm=self.origin.translation_mm,
            )

        offset_in_parent_mm = self.origin.rotation.apply(self.axis.scaled(position.value))
        return RigidTransform(
            parent_frame=self.parent_link,
            child_frame=self.child_link,
            rotation=self.origin.rotation,
            translation_mm=self.origin.translation_mm + offset_in_parent_mm,
        )


@dataclass(frozen=True, slots=True)
class UrdfModel:
    name: str
    links: tuple[UrdfLink, ...]
    joints: tuple[UrdfJoint, ...]
    root_link: str = field(init=False)
    _links_by_name: Mapping[str, UrdfLink] = field(init=False, repr=False, compare=False)
    _joints_by_name: Mapping[str, UrdfJoint] = field(init=False, repr=False, compare=False)
    _children_by_link: Mapping[str, tuple[UrdfJoint, ...]] = field(
        init=False,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _name(self.name, "robot name"))
        links = tuple(self.links)
        joints = tuple(self.joints)
        if not links:
            raise UrdfTopologyError("URDF robot must contain at least one link")
        if any(not isinstance(link, UrdfLink) for link in links):
            raise TypeError("links must contain only UrdfLink values")
        if any(not isinstance(joint, UrdfJoint) for joint in joints):
            raise TypeError("joints must contain only UrdfJoint values")

        links_by_name = _unique_by_name(links, "link")
        joints_by_name = _unique_by_name(joints, "joint")
        parent_joint_by_child: dict[str, str] = {}
        children_by_link: dict[str, list[UrdfJoint]] = {name: [] for name in links_by_name}
        for joint in joints:
            if joint.parent_link not in links_by_name:
                raise UrdfTopologyError(
                    f"Joint {joint.name!r} references unknown parent link {joint.parent_link!r}"
                )
            if joint.child_link not in links_by_name:
                raise UrdfTopologyError(
                    f"Joint {joint.name!r} references unknown child link {joint.child_link!r}"
                )
            previous = parent_joint_by_child.get(joint.child_link)
            if previous is not None:
                raise UrdfTopologyError(
                    f"Link {joint.child_link!r} has multiple parent joints: {previous!r} and {joint.name!r}"
                )
            parent_joint_by_child[joint.child_link] = joint.name
            children_by_link[joint.parent_link].append(joint)

        roots = sorted(set(links_by_name) - set(parent_joint_by_child))
        if len(roots) != 1:
            raise UrdfTopologyError(
                f"URDF must have exactly one root link; found {len(roots)}: {roots}"
            )
        root = roots[0]
        ordered_children = {
            name: tuple(sorted(values, key=lambda joint: joint.name))
            for name, values in children_by_link.items()
        }
        visited: set[str] = set()
        active: set[str] = set()

        def visit(link_name: str) -> None:
            if link_name in active:
                raise UrdfTopologyError(f"URDF contains a cycle at link {link_name!r}")
            if link_name in visited:
                return
            active.add(link_name)
            for joint in ordered_children[link_name]:
                visit(joint.child_link)
            active.remove(link_name)
            visited.add(link_name)

        visit(root)
        if visited != set(links_by_name):
            unreachable = sorted(set(links_by_name) - visited)
            raise UrdfTopologyError(f"URDF has links unreachable from root {root!r}: {unreachable}")

        object.__setattr__(self, "links", links)
        object.__setattr__(self, "joints", joints)
        object.__setattr__(self, "root_link", root)
        object.__setattr__(self, "_links_by_name", MappingProxyType(links_by_name))
        object.__setattr__(self, "_joints_by_name", MappingProxyType(joints_by_name))
        object.__setattr__(
            self,
            "_children_by_link",
            MappingProxyType(ordered_children),
        )

    @classmethod
    def from_xml(cls, xml_text: str, *, source_name: str = "<memory>") -> "UrdfModel":
        return parse_urdf(xml_text, source_name=source_name)

    @classmethod
    def from_file(cls, path: str | Path) -> "UrdfModel":
        return load_urdf(path)

    @property
    def link_names(self) -> tuple[str, ...]:
        return tuple(sorted(self._links_by_name))

    @property
    def joint_names(self) -> tuple[str, ...]:
        return tuple(sorted(self._joints_by_name))

    @property
    def movable_joint_names(self) -> tuple[str, ...]:
        return tuple(sorted(joint.name for joint in self.joints if joint.is_movable))

    def joint(self, name: str) -> UrdfJoint:
        try:
            return self._joints_by_name[name]
        except (KeyError, TypeError) as exc:
            raise KeyError(f"Unknown URDF joint {name!r}") from exc

    def forward_kinematics(
        self,
        joint_positions: Mapping[str, JointPosition],
    ) -> dict[str, RigidTransform]:
        """Compute deterministic ``root_T_link`` transforms for the entire tree.

        Every movable joint must be supplied exactly once, no fixed or unknown
        joint may be supplied, and every value must carry the correct unit.
        """

        if not isinstance(joint_positions, Mapping):
            raise TypeError("joint_positions must be a mapping")
        supplied_names: set[str] = set()
        for name, value in joint_positions.items():
            if not isinstance(name, str):
                raise JointStateError("joint position keys must be strings")
            if not isinstance(value, JointPosition):
                raise JointStateError(f"Joint {name!r} position must be a JointPosition")
            supplied_names.add(name)

        known_names = set(self._joints_by_name)
        unknown = sorted(supplied_names - known_names)
        if unknown:
            raise JointStateError(f"Unknown joint positions supplied: {unknown}")
        fixed_supplied = sorted(
            name for name in supplied_names if not self._joints_by_name[name].is_movable
        )
        if fixed_supplied:
            raise JointStateError(f"Fixed joints must not receive positions: {fixed_supplied}")
        expected = set(self.movable_joint_names)
        missing = sorted(expected - supplied_names)
        if missing:
            raise JointStateError(f"Missing movable joint positions: {missing}")

        transforms: dict[str, RigidTransform] = {
            self.root_link: RigidTransform.identity(self.root_link)
        }

        def walk(parent_link: str) -> None:
            root_t_parent = transforms[parent_link]
            for joint in self._children_by_link[parent_link]:
                position = joint_positions.get(joint.name) if joint.is_movable else None
                parent_t_child = joint.transform_at(position)
                transforms[joint.child_link] = root_t_parent.compose(parent_t_child)
                walk(joint.child_link)

        walk(self.root_link)
        return transforms


def _name(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise UrdfParseError(f"{label} must be a non-empty string")
    return value.strip()


def _unique_by_name(values: tuple[object, ...], label: str) -> dict[str, object]:
    result: dict[str, object] = {}
    for value in values:
        name = getattr(value, "name")
        if name in result:
            raise UrdfTopologyError(f"Duplicate {label} name {name!r}")
        result[name] = value
    return result


def _tag(element: ElementTree.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _children(element: ElementTree.Element, tag: str) -> tuple[ElementTree.Element, ...]:
    return tuple(child for child in element if _tag(child) == tag)


def _single_child(
    element: ElementTree.Element,
    tag: str,
    *,
    required: bool,
    context: str,
) -> ElementTree.Element | None:
    children = _children(element, tag)
    if len(children) > 1:
        raise UrdfParseError(f"{context} contains multiple <{tag}> elements")
    if not children:
        if required:
            raise UrdfParseError(f"{context} is missing required <{tag}> element")
        return None
    return children[0]


def _attribute(element: ElementTree.Element, name: str, *, context: str) -> str:
    if name not in element.attrib or not element.attrib[name].strip():
        raise UrdfParseError(f"{context} is missing required attribute {name!r}")
    return element.attrib[name].strip()


def _float(value: str, *, context: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise UrdfParseError(f"{context} must be a real number") from exc
    if not math.isfinite(parsed):
        raise UrdfParseError(f"{context} must be finite")
    return parsed


def _vector_attribute(
    element: ElementTree.Element,
    name: str,
    *,
    default: tuple[float, float, float] | None,
    context: str,
) -> Vec3:
    raw = element.attrib.get(name)
    if raw is None:
        if default is None:
            raise UrdfParseError(f"{context} is missing required attribute {name!r}")
        return Vec3(*default)
    parts = raw.split()
    if len(parts) != 3:
        raise UrdfParseError(f"{context} attribute {name!r} must contain exactly three numbers")
    return Vec3(*(_float(part, context=f"{context} {name}") for part in parts))


def _parse_limit(element: ElementTree.Element, *, joint_name: str, joint_type: str) -> JointLimit:
    context = f"joint {joint_name!r} limit"
    effort = _float(_attribute(element, "effort", context=context), context=f"{context} effort")
    velocity_urdf = _float(
        _attribute(element, "velocity", context=context),
        context=f"{context} velocity",
    )
    if effort < 0.0:
        raise UrdfParseError(f"{context} effort must be non-negative")
    if velocity_urdf < 0.0:
        raise UrdfParseError(f"{context} velocity must be non-negative")

    if joint_type == "prismatic":
        unit = JointPositionUnit.MILLIMETRE
        velocity = JointVelocity(velocity_urdf * 1000.0, unit)
        lower_raw = _float(
            _attribute(element, "lower", context=context),
            context=f"{context} lower",
        )
        upper_raw = _float(
            _attribute(element, "upper", context=context),
            context=f"{context} upper",
        )
        lower = JointPosition.millimetres(lower_raw * 1000.0)
        upper = JointPosition.millimetres(upper_raw * 1000.0)
    elif joint_type == "revolute":
        unit = JointPositionUnit.RADIAN
        velocity = JointVelocity(velocity_urdf, unit)
        lower = JointPosition.radians(
            _float(_attribute(element, "lower", context=context), context=f"{context} lower")
        )
        upper = JointPosition.radians(
            _float(_attribute(element, "upper", context=context), context=f"{context} upper")
        )
    elif joint_type == "continuous":
        if "lower" in element.attrib or "upper" in element.attrib:
            raise UrdfParseError(f"{context} cannot bound a continuous joint")
        unit = JointPositionUnit.RADIAN
        velocity = JointVelocity(velocity_urdf, unit)
        lower = None
        upper = None
    else:
        raise UrdfParseError(f"Cannot parse motion limits for joint type {joint_type!r}")

    try:
        return JointLimit(lower, upper, effort, velocity)
    except (TypeError, ValueError) as exc:
        raise UrdfParseError(f"Invalid {context}: {exc}") from exc


def _parse_joint(element: ElementTree.Element) -> UrdfJoint:
    joint_name = _name(_attribute(element, "name", context="joint"), "joint name")
    joint_type = _name(_attribute(element, "type", context=f"joint {joint_name!r}"), "joint type").lower()
    if joint_type not in _SUPPORTED_JOINT_TYPES:
        raise UrdfParseError(f"Joint {joint_name!r} has unsupported type {joint_type!r}")
    context = f"joint {joint_name!r}"

    if _children(element, "mimic"):
        raise UrdfParseError(f"{context} uses unsupported mimic-joint semantics")
    parent_element = _single_child(element, "parent", required=True, context=context)
    child_element = _single_child(element, "child", required=True, context=context)
    assert parent_element is not None
    assert child_element is not None
    parent_link = _name(_attribute(parent_element, "link", context=f"{context} parent"), "parent link")
    child_link = _name(_attribute(child_element, "link", context=f"{context} child"), "child link")

    origin_element = _single_child(element, "origin", required=False, context=context)
    if origin_element is None:
        xyz_m = Vec3.zero()
        rpy_rad = Vec3.zero()
    else:
        xyz_m = _vector_attribute(
            origin_element,
            "xyz",
            default=(0.0, 0.0, 0.0),
            context=f"{context} origin",
        )
        rpy_rad = _vector_attribute(
            origin_element,
            "rpy",
            default=(0.0, 0.0, 0.0),
            context=f"{context} origin",
        )
    origin = RigidTransform(
        parent_link,
        child_link,
        Rotation3.from_rpy(rpy_rad.x, rpy_rad.y, rpy_rad.z),
        xyz_m.scaled(1000.0),
    )

    axis_elements = _children(element, "axis")
    limit_elements = _children(element, "limit")
    if len(axis_elements) > 1:
        raise UrdfParseError(f"{context} contains multiple <axis> elements")
    if len(limit_elements) > 1:
        raise UrdfParseError(f"{context} contains multiple <limit> elements")

    if joint_type == "fixed":
        if axis_elements or limit_elements:
            raise UrdfParseError(f"Fixed {context} must not declare axis or limit motion data")
        axis = None
        limit = None
    else:
        if axis_elements:
            axis = _vector_attribute(
                axis_elements[0],
                "xyz",
                default=None,
                context=f"{context} axis",
            )
        else:
            # URDF specifies +X when <axis> is omitted.
            axis = Vec3(1.0, 0.0, 0.0)
        if not limit_elements:
            raise UrdfParseError(f"Movable {context} is missing required <limit>")
        limit = _parse_limit(limit_elements[0], joint_name=joint_name, joint_type=joint_type)

    try:
        return UrdfJoint(
            name=joint_name,
            joint_type=joint_type,
            parent_link=parent_link,
            child_link=child_link,
            origin=origin,
            axis=axis,
            limit=limit,
        )
    except UrdfError:
        raise
    except (TypeError, ValueError) as exc:
        raise UrdfParseError(f"Invalid {context}: {exc}") from exc


def parse_urdf(xml_text: str, *, source_name: str = "<memory>") -> UrdfModel:
    """Parse a complete URDF document from text without external resources."""

    if not isinstance(xml_text, str):
        raise TypeError("xml_text must be a string")
    source = _name(source_name, "source_name")
    uppercase_prefix = xml_text.upper()
    if "<!DOCTYPE" in uppercase_prefix or "<!ENTITY" in uppercase_prefix:
        raise UrdfParseError(f"{source}: DTD and entity declarations are prohibited")
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError as exc:
        raise UrdfParseError(f"{source}: invalid XML: {exc}") from exc
    if _tag(root) != "robot":
        raise UrdfParseError(f"{source}: root element must be <robot>")
    robot_name = _name(_attribute(root, "name", context=f"{source} robot"), "robot name")

    try:
        links = tuple(
            UrdfLink(_name(_attribute(element, "name", context="link"), "link name"))
            for element in _children(root, "link")
        )
        joints = tuple(_parse_joint(element) for element in _children(root, "joint"))
        return UrdfModel(robot_name, links, joints)
    except UrdfError as exc:
        if str(exc).startswith(f"{source}:"):
            raise
        raise type(exc)(f"{source}: {exc}") from exc
    except (TypeError, ValueError) as exc:
        raise UrdfParseError(f"{source}: {exc}") from exc


def load_urdf(path: str | Path) -> UrdfModel:
    """Read and parse a UTF-8 URDF file."""

    if not isinstance(path, (str, Path)):
        raise TypeError("path must be a string or pathlib.Path")
    source = Path(path)
    try:
        text = source.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise UrdfParseError(f"Could not read URDF {source}: {exc}") from exc
    return parse_urdf(text, source_name=str(source))

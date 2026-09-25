from __future__ import annotations

import math

import pytest

from rocell.geometry import (
    JointPosition,
    JointPositionUnit,
    JointStateError,
    UrdfModel,
    UrdfParseError,
    UrdfTopologyError,
    Vec3,
    load_urdf,
    parse_urdf,
)


CHAIN_URDF = """\
<robot name="unit_chain">
  <link name="base"/>
  <link name="shoulder"/>
  <link name="carriage"/>
  <link name="tool"/>
  <joint name="base_mount" type="fixed">
    <parent link="base"/>
    <child link="shoulder"/>
    <origin xyz="0.1 0 0" rpy="0 0 0"/>
  </joint>
  <joint name="yaw" type="revolute">
    <parent link="shoulder"/>
    <child link="carriage"/>
    <origin xyz="0 0 0.2" rpy="0 0 0"/>
    <axis xyz="0 0 4"/>
    <limit lower="-1.6" upper="1.6" effort="10" velocity="2"/>
  </joint>
  <joint name="extension" type="prismatic">
    <parent link="carriage"/>
    <child link="tool"/>
    <origin xyz="0.05 0 0" rpy="0 0 0"/>
    <axis xyz="1 0 0"/>
    <limit lower="-0.02" upper="0.08" effort="30" velocity="0.4"/>
  </joint>
</robot>
"""


def test_parse_urdf_converts_all_linear_units_to_millimetres() -> None:
    model = parse_urdf(CHAIN_URDF)
    assert model.name == "unit_chain"
    assert model.root_link == "base"
    assert model.link_names == ("base", "carriage", "shoulder", "tool")
    assert model.joint_names == ("base_mount", "extension", "yaw")
    assert model.movable_joint_names == ("extension", "yaw")

    fixed = model.joint("base_mount")
    assert fixed.origin.translation_mm == Vec3(100, 0, 0)
    yaw = model.joint("yaw")
    assert yaw.axis == Vec3(0, 0, 1)
    assert yaw.limit is not None
    assert yaw.limit.position_unit is JointPositionUnit.RADIAN
    assert yaw.limit.lower == JointPosition.radians(-1.6)
    assert yaw.limit.max_velocity.value_per_second == 2

    extension = model.joint("extension")
    assert extension.origin.translation_mm == Vec3(50, 0, 0)
    assert extension.limit is not None
    assert extension.limit.position_unit is JointPositionUnit.MILLIMETRE
    assert extension.limit.lower == JointPosition.millimetres(-20)
    assert extension.limit.upper == JointPosition.millimetres(80)
    assert extension.limit.max_velocity.value_per_second == 400


def test_forward_kinematics_is_deterministic_and_frame_labelled() -> None:
    model = UrdfModel.from_xml(CHAIN_URDF)
    transforms = model.forward_kinematics(
        {
            "yaw": JointPosition.radians(math.pi / 2),
            "extension": JointPosition.millimetres(25),
        }
    )
    assert tuple(transforms) == ("base", "shoulder", "carriage", "tool")
    assert transforms["tool"].parent_frame == "base"
    assert transforms["tool"].child_frame == "tool"
    assert transforms["tool"].translation_mm.almost_equal(Vec3(100, 75, 200))
    assert transforms["tool"].rotation.apply(Vec3(1, 0, 0)).almost_equal(Vec3(0, 1, 0))


def test_prismatic_axis_is_applied_after_joint_origin_rotation() -> None:
    model = parse_urdf(
        """
        <robot name="rotated_slider">
          <link name="base"/><link name="tip"/>
          <joint name="slide" type="prismatic">
            <parent link="base"/><child link="tip"/>
            <origin xyz="0 0 0" rpy="0 0 1.5707963267948966"/>
            <axis xyz="1 0 0"/>
            <limit lower="0" upper="0.1" effort="1" velocity="0.1"/>
          </joint>
        </robot>
        """
    )
    tip = model.forward_kinematics({"slide": JointPosition.millimetres(30)})["tip"]
    assert tip.translation_mm.almost_equal(Vec3(0, 30, 0))


@pytest.mark.parametrize(
    ("positions", "message"),
    [
        ({"yaw": JointPosition.radians(0)}, "Missing movable"),
        (
            {
                "yaw": JointPosition.radians(0),
                "extension": JointPosition.millimetres(0),
                "ghost": JointPosition.radians(0),
            },
            "Unknown joint",
        ),
        (
            {
                "base_mount": JointPosition.radians(0),
                "yaw": JointPosition.radians(0),
                "extension": JointPosition.millimetres(0),
            },
            "Fixed joints",
        ),
        (
            {
                "yaw": JointPosition.millimetres(0),
                "extension": JointPosition.millimetres(0),
            },
            "requires radian",
        ),
        (
            {
                "yaw": JointPosition.radians(0),
                "extension": JointPosition.millimetres(81),
            },
            "above limit",
        ),
    ],
)
def test_forward_kinematics_fails_closed_on_bad_state(
    positions: dict[str, JointPosition],
    message: str,
) -> None:
    with pytest.raises(JointStateError, match=message):
        parse_urdf(CHAIN_URDF).forward_kinematics(positions)


def test_forward_kinematics_rejects_untyped_raw_numbers() -> None:
    with pytest.raises(JointStateError, match="must be a JointPosition"):
        parse_urdf(CHAIN_URDF).forward_kinematics(  # type: ignore[arg-type]
            {"yaw": 0.0, "extension": JointPosition.millimetres(0)}
        )


def test_continuous_joint_is_unbounded_but_typed() -> None:
    model = parse_urdf(
        """
        <robot name="continuous_test">
          <link name="base"/><link name="tip"/>
          <joint name="spin" type="continuous">
            <parent link="base"/><child link="tip"/>
            <limit effort="2" velocity="3"/>
          </joint>
        </robot>
        """
    )
    spin = model.joint("spin")
    assert spin.axis == Vec3(1, 0, 0)  # URDF default axis
    assert spin.limit is not None and spin.limit.lower is None
    transform = model.forward_kinematics({"spin": JointPosition.radians(25 * math.pi)})["tip"]
    assert transform.rotation.apply(Vec3(0, 1, 0)).almost_equal(Vec3(0, -1, 0))


def test_official_style_zero_effort_and_velocity_are_retained_but_not_timing_data() -> None:
    model = parse_urdf(
        """
        <robot name="upstream_placeholders">
          <link name="base"/><link name="tip"/>
          <joint name="joint" type="revolute">
            <parent link="base"/><child link="tip"/><axis xyz="0 0 1"/>
            <limit lower="-3.1416" upper="3.1416" effort="0" velocity="0"/>
          </joint>
        </robot>
        """
    )
    limit = model.joint("joint").limit
    assert limit is not None
    assert limit.max_effort == 0
    assert limit.max_velocity.value_per_second == 0
    assert limit.max_velocity.usable_for_timing is False
    # Geometry remains usable, but no timing or speed is inferred from zero.
    assert model.forward_kinematics({"joint": JointPosition.radians(0.25)})["tip"]


def test_load_urdf_reads_utf8_file(tmp_path) -> None:
    path = tmp_path / "chain.urdf"
    path.write_text(CHAIN_URDF, encoding="utf-8")
    assert load_urdf(path).name == "unit_chain"
    assert UrdfModel.from_file(path).root_link == "base"


@pytest.mark.parametrize(
    ("body", "message"),
    [
        (
            '<link name="base"/><link name="tip"/><joint name="j" type="floating">'
            '<parent link="base"/><child link="tip"/></joint>',
            "unsupported type",
        ),
        (
            '<link name="base"/><link name="tip"/><joint name="j" type="revolute">'
            '<parent link="base"/><child link="tip"/><mimic joint="other"/>'
            '<limit lower="-1" upper="1" effort="1" velocity="1"/></joint>',
            "mimic",
        ),
        (
            '<link name="base"/><link name="tip"/><joint name="j" type="revolute">'
            '<parent link="base"/><child link="tip"/></joint>',
            "missing required <limit>",
        ),
        (
            '<link name="base"/><link name="tip"/><joint name="j" type="prismatic">'
            '<parent link="base"/><child link="tip"/>'
            '<limit lower="0" upper="1" effort="1" velocity="nan"/></joint>',
            "must be finite",
        ),
        (
            '<link name="base"/><link name="tip"/><joint name="j" type="continuous">'
            '<parent link="base"/><child link="tip"/>'
            '<limit lower="-1" upper="1" effort="1" velocity="1"/></joint>',
            "cannot bound",
        ),
        (
            '<link name="base"/><link name="tip"/><joint name="j" type="fixed">'
            '<parent link="base"/><child link="tip"/><axis xyz="1 0 0"/></joint>',
            "must not declare",
        ),
    ],
)
def test_parser_rejects_unsupported_or_incomplete_joint_semantics(body: str, message: str) -> None:
    with pytest.raises(UrdfParseError, match=message):
        parse_urdf(f'<robot name="bad">{body}</robot>')


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ('<link name="a"/><link name="a"/>', "Duplicate link"),
        ('<link name="a"/><link name="b"/>', "exactly one root"),
        (
            '<link name="a"/><link name="b"/>'
            '<joint name="ab" type="fixed"><parent link="a"/><child link="b"/></joint>'
            '<joint name="ba" type="fixed"><parent link="b"/><child link="a"/></joint>',
            "exactly one root",
        ),
        (
            '<link name="root"/><link name="left"/><link name="right"/><link name="child"/>'
            '<joint name="a" type="fixed"><parent link="root"/><child link="left"/></joint>'
            '<joint name="b" type="fixed"><parent link="root"/><child link="right"/></joint>'
            '<joint name="c" type="fixed"><parent link="left"/><child link="child"/></joint>'
            '<joint name="d" type="fixed"><parent link="right"/><child link="child"/></joint>',
            "multiple parent joints",
        ),
        (
            '<link name="base"/><link name="tip"/>'
            '<joint name="j" type="fixed"><parent link="base"/><child link="ghost"/></joint>',
            "unknown child link",
        ),
    ],
)
def test_model_rejects_ambiguous_or_invalid_topology(body: str, message: str) -> None:
    with pytest.raises(UrdfTopologyError, match=message):
        parse_urdf(f'<robot name="bad_tree">{body}</robot>')


def test_parser_rejects_non_robot_xml_dtd_and_duplicate_joint_fields() -> None:
    with pytest.raises(UrdfParseError, match="root element"):
        parse_urdf("<not_robot/>")
    with pytest.raises(UrdfParseError, match="DTD"):
        parse_urdf('<!DOCTYPE robot SYSTEM "anything"><robot name="x"><link name="x"/></robot>')
    with pytest.raises(UrdfParseError, match="multiple <parent>"):
        parse_urdf(
            """
            <robot name="duplicate_field"><link name="a"/><link name="b"/>
              <joint name="j" type="fixed">
                <parent link="a"/><parent link="a"/><child link="b"/>
              </joint>
            </robot>
            """
        )

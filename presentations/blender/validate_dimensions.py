"""Validate the Blender explainer's dimensional source contract.

This script intentionally uses only the Python standard library so it can run
in CI without Blender. It checks the RC03 layout values, portal and contact-tool
STL bounds, and the hash-pinned RoArm-M3 URDF joint origins used by the
presentation.
"""

from __future__ import annotations

import hashlib
import json
import math
import struct
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


SCRIPT = Path(__file__).resolve()
ROOT = SCRIPT.parents[2]
MANIFEST_PATH = SCRIPT.with_name("dimension_manifest.json")


def fail(message: str) -> None:
    raise AssertionError(message)


def assert_close(actual, expected, label: str, tolerance: float = 1e-6) -> None:
    if len(actual) != len(expected):
        fail(f"{label}: length {len(actual)} != {len(expected)}")
    for index, (left, right) in enumerate(zip(actual, expected)):
        if not math.isclose(float(left), float(right), abs_tol=tolerance):
            fail(f"{label}[{index}]: {left} != {right}")


def resolve(relative: str) -> Path:
    path = ROOT / relative
    if not path.is_file():
        fail(f"Missing authority file: {relative}")
    return path


def stl_bounds(path: Path) -> list[float]:
    """Return axis-aligned STL dimensions in file units."""
    data = path.read_bytes()
    vertices: list[tuple[float, float, float]] = []
    if len(data) >= 84 and 84 + struct.unpack_from("<I", data, 80)[0] * 50 == len(data):
        triangle_count = struct.unpack_from("<I", data, 80)[0]
        for triangle in range(triangle_count):
            offset = 84 + triangle * 50 + 12
            for vertex in range(3):
                vertices.append(struct.unpack_from("<fff", data, offset + vertex * 12))
    else:
        for line in data.decode("utf-8", errors="ignore").splitlines():
            fields = line.strip().split()
            if len(fields) == 4 and fields[0].lower() == "vertex":
                vertices.append(tuple(float(value) for value in fields[1:4]))
    if not vertices:
        fail(f"No vertices parsed from STL: {path}")
    minima = [min(vertex[axis] for vertex in vertices) for axis in range(3)]
    maxima = [max(vertex[axis] for vertex in vertices) for axis in range(3)]
    return [maxima[axis] - minima[axis] for axis in range(3)]


def main() -> int:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    workcell = manifest["workcell"]
    layout = json.loads(resolve(workcell["authority"]).read_text(encoding="utf-8"))

    board = layout["board"]
    assert_close(
        [board["width"], board["depth"], board["thickness"]],
        workcell["board"],
        "board",
    )
    keyboard = layout["devices"]["keyboard"]
    assert_close(keyboard["nominal_origin_xy"], workcell["keyboard"]["origin_xy"], "keyboard origin")
    assert_close(keyboard["nominal_size"], workcell["keyboard"]["size_xyz"], "keyboard size")
    target_profiles = json.loads(
        resolve(workcell["keyboard"]["target_authority"]).read_text(encoding="utf-8")
    )
    target_keyboard = target_profiles["keyboard"]
    if target_keyboard["profile_id"] != workcell["keyboard"]["target_profile_id"]:
        fail("keyboard target profile id drift")
    assert_close([target_keyboard["pitch_mm"]],
                 [workcell["keyboard"]["nominal_pitch"]], "keyboard pitch")
    home_row = next(row for row in target_keyboard["rows"] if "H" in row["key_ids"])
    h_index = home_row["key_ids"].index("H")
    h_local = [
        home_row["first_center_xy_mm"][0] + home_row["step_xy_mm"][0] * h_index,
        home_row["first_center_xy_mm"][1] + home_row["step_xy_mm"][1] * h_index,
    ]
    h_board = [keyboard["nominal_origin_xy"][axis] + h_local[axis] for axis in range(2)]
    assert_close(h_board, workcell["keyboard"]["nominal_h_center_board_xy"],
                 "keyboard H board coordinate")
    phone = layout["devices"]["phone"]
    assert_close(phone["nominal_origin_xy"], workcell["phone"]["origin_xy"], "phone origin")
    assert_close(phone["configured_size"], workcell["phone"]["size_xyz"], "phone size")
    assert_close([phone["support_plane_z"]], [workcell["phone"]["support_z"]], "phone support z")
    assert_close([phone["nominal_screen_plane_z"]], [workcell["phone"]["screen_z"]], "phone screen z")

    portal = manifest["portal"]
    portal_path = resolve(portal["authority"])
    assert_close(stl_bounds(portal_path), portal["mesh_bounds_xyz"], "portal STL bounds", tolerance=1e-3)

    for relative in (
        "active-project/RoCell_v0_3/stl/keyboard_station_left.stl",
        "active-project/RoCell_v0_3/stl/keyboard_station_right.stl",
        "active-project/RoCell_v0_3/stl/phone_tcp_station.stl",
    ):
        resolve(relative)

    arm = manifest["arm"]
    urdf_path = resolve(arm["kinematic_authority"])
    digest = hashlib.sha256(urdf_path.read_bytes()).hexdigest()
    if digest != arm["kinematic_authority_sha256"]:
        fail(f"URDF SHA-256 drift: {digest}")

    root = ET.parse(urdf_path).getroot()
    actual_origins: dict[str, list[float]] = {}
    for joint in root.findall("joint"):
        origin = joint.find("origin")
        xyz = [0.0, 0.0, 0.0] if origin is None else [float(value) for value in origin.get("xyz", "0 0 0").split()]
        actual_origins[joint.attrib["name"]] = xyz
    for name, expected in arm["joint_origin_xyz_m"].items():
        if name not in actual_origins:
            fail(f"URDF joint missing: {name}")
        assert_close(actual_origins[name], expected, f"URDF joint {name}", tolerance=1e-9)

    surface = arm["surface_geometry"]
    archive_path = ROOT / "tmp" / "vendor" / "roarm_m3" / "RoArm-M3_STEP_260310.zip"
    if archive_path.is_file():
        archive_hash = hashlib.sha256(archive_path.read_bytes()).hexdigest()
        if archive_hash.lower() != surface["source_archive_sha256"].lower():
            fail(f"Official arm archive SHA-256 drift: {archive_hash}")
    presentation_mesh = ROOT / surface["presentation_mesh_path"]
    if presentation_mesh.is_file():
        assert_close(
            stl_bounds(presentation_mesh),
            surface["default_step_envelope_mm"],
            "official arm presentation mesh bounds",
            tolerance=1e-3,
        )

    contact_tool = arm["presentation_contact_tool"]
    for prefix, bounds_key in (
        ("body", "body_mesh_envelope_mm"),
        ("cap", "cap_mesh_envelope_mm"),
        ("collar", "collar_mesh_envelope_mm"),
    ):
        tool_path = resolve(contact_tool[f"{prefix}_path"])
        tool_digest = hashlib.sha256(tool_path.read_bytes()).hexdigest()
        if tool_digest != contact_tool[f"{prefix}_sha256"]:
            fail(f"Contact-tool {prefix} SHA-256 drift: {tool_digest}")
        assert_close(
            stl_bounds(tool_path), contact_tool[bounds_key],
            f"contact-tool {prefix} STL bounds", tolerance=0.03,
        )

    print("Tactevra Blender dimension contract: PASS")
    print(f"  board/device layout: {workcell['authority']}")
    print(f"  portal STL: {portal['mesh_bounds_xyz']} mm")
    print(f"  keyboard nominal H: {workcell['keyboard']['nominal_h_center_board_xy']} mm")
    print(f"  arm URDF SHA-256: {digest}")
    print(f"  validated arm joint origins: {len(arm['joint_origin_xyz_m'])}")
    if presentation_mesh.is_file():
        print(f"  official arm surface: {surface['default_step_envelope_mm']} mm")
    print("  controlled contact tool: body + keyed cap + split collar")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, KeyError, ValueError, ET.ParseError) as error:
        print(f"Tactevra Blender dimension contract: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)

"""Build and optionally render the Tactevra RC03 Blender explainer.

Blender 4.3+ usage:
  blender --background --factory-startup \
    --python presentations/blender/build_workcell_explainer.py
  blender --background --factory-startup \
    --python presentations/blender/build_workcell_explainer.py -- --render-video
  blender --background --factory-startup \
    --python presentations/blender/build_workcell_explainer.py -- --overlay-only
  blender --background --factory-startup \
    --python presentations/blender/build_workcell_explainer.py -- --preview-shots

Generated outputs are intentionally written below /tmp and are not source
artifacts. Source CAD and measured layout data remain authoritative.

Use --publish-homepage-media only after reviewing the generated film. It writes
the compact, captioned public derivative and poster below assets/media/.
"""

from __future__ import annotations

import json
import hashlib
import math
import shutil
import struct
import subprocess
import sys
import wave
import xml.etree.ElementTree as ET
from pathlib import Path

import bpy
from mathutils import Vector


SCRIPT = Path(__file__).resolve()
ROOT = SCRIPT.parents[2]
OUT = ROOT / "tmp" / "blender-workcell-video"
OUT.mkdir(parents=True, exist_ok=True)
LAYOUT_PATH = ROOT / "active-project" / "RoCell_v0_3" / "config" / "workcell_layout.json"
PORTAL_PATH = (
    ROOT
    / "hardware"
    / "static_overhead_camera"
    / "cad"
    / "output"
    / "assembly"
    / "printable_camera_portal_printed_parts_only.stl"
)
STL_DIR = ROOT / "active-project" / "RoCell_v0_3" / "stl"
DIMENSION_MANIFEST_PATH = SCRIPT.with_name("dimension_manifest.json")
ARM_URDF_PATH = ROOT / "software" / "models" / "roarm_m3" / "roarm_m3_kinematic_40dbd84.urdf"
OFFICIAL_ARM_STL_PATH = ROOT / "tmp" / "vendor" / "roarm_m3" / "roarm_m3_official_presentation.stl"
PUBLIC_MEDIA_DIR = ROOT / "assets" / "media"

FPS = 24
# V3 keeps the narrated 12-beat screenplay while making the distinction between
# exact hardware appearance and conceptual motion unmistakable.
END_FRAME = 77 * FPS
BOARD_CENTER_MM = Vector((305.0, 228.5, 0.0))


def board_point(x_mm: float, y_mm: float, z_mm: float = 0.0) -> Vector:
    """Convert board-frame millimetres to centered Blender metres."""
    return Vector(((x_mm - BOARD_CENTER_MM.x) / 1000.0,
                   (y_mm - BOARD_CENTER_MM.y) / 1000.0,
                   z_mm / 1000.0))


def clean_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for collection in (bpy.data.meshes, bpy.data.curves, bpy.data.materials,
                       bpy.data.cameras, bpy.data.lights):
        pass


def material(name: str, color: tuple[float, float, float, float], *,
             metallic: float = 0.0, roughness: float = 0.45,
             emission: tuple[float, float, float, float] | None = None,
             emission_strength: float = 0.0) -> bpy.types.Material:
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = color
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    if emission is not None:
        bsdf.inputs["Emission Color"].default_value = emission
        bsdf.inputs["Emission Strength"].default_value = emission_strength
    return mat


def textured_material(name: str, color: tuple[float, float, float, float], *,
                      scale: float, detail: float, roughness: float,
                      metallic: float = 0.0) -> bpy.types.Material:
    """Create restrained procedural surface variation for presentation realism."""
    mat = material(name, color, metallic=metallic, roughness=roughness)
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    bsdf = nodes.get("Principled BSDF")
    tex = nodes.new("ShaderNodeTexNoise")
    tex.inputs["Scale"].default_value = scale
    tex.inputs["Detail"].default_value = detail
    tex.inputs["Roughness"].default_value = 0.58
    ramp = nodes.new("ShaderNodeValToRGB")
    base = color[:3]
    ramp.color_ramp.elements[0].color = (*[max(0.0, c * 0.62) for c in base], 1)
    ramp.color_ramp.elements[1].color = (*[min(1.0, c * 1.28) for c in base], 1)
    links.new(tex.outputs["Fac"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    return mat


def apply_material(obj: bpy.types.Object, mat: bpy.types.Material) -> None:
    if obj.data and hasattr(obj.data, "materials"):
        obj.data.materials.clear()
        obj.data.materials.append(mat)


def cube(name: str, location: Vector | tuple[float, float, float],
         dimensions: tuple[float, float, float], mat: bpy.types.Material,
         bevel: float = 0.0) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(location=location)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel:
        mod = obj.modifiers.new("Soft manufactured edges", "BEVEL")
        mod.width = bevel
        mod.segments = 3
    apply_material(obj, mat)
    return obj


def cylinder(name: str, location: Vector | tuple[float, float, float],
             radius: float, depth: float, mat: bpy.types.Material,
             vertices: int = 48) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius,
                                       depth=depth, location=location)
    obj = bpy.context.object
    obj.name = name
    apply_material(obj, mat)
    return obj


def import_stl(path: Path, name: str, mat: bpy.types.Material,
               offset_mm: tuple[float, float, float] = (0, 0, 0)) -> bpy.types.Object:
    bpy.ops.wm.stl_import(filepath=str(path))
    obj = bpy.context.object
    obj.name = name
    obj.scale = (0.001, 0.001, 0.001)
    obj.location = board_point(*offset_mm)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    apply_material(obj, mat)
    return obj


def text_object(name: str, body: str, location: Vector, size: float,
                mat: bpy.types.Material, camera: bpy.types.Object,
                align: str = "CENTER") -> bpy.types.Object:
    bpy.ops.object.text_add(location=location)
    obj = bpy.context.object
    obj.name = name
    obj.data.body = body
    obj.data.align_x = align
    obj.data.align_y = "CENTER"
    obj.data.size = size
    obj.data.extrude = size * 0.025
    obj.data.bevel_depth = size * 0.012
    apply_material(obj, mat)
    con = obj.constraints.new("TRACK_TO")
    con.target = camera
    con.track_axis = "TRACK_Z"
    con.up_axis = "UP_Y"
    # Typography is composited after rendering so physical geometry cannot
    # occlude safety and evidence labels. Retain these authored guides in the
    # .blend for editing, but do not include them in beauty renders.
    obj.hide_render = True
    return obj


def board_text(name: str, body: str, location: Vector, size: float,
               mat: bpy.types.Material) -> bpy.types.Object:
    """Create a flat, renderable label on board- or key-plane geometry."""
    bpy.ops.object.text_add(location=location)
    obj = bpy.context.object
    obj.name = name
    obj.data.body = body
    obj.data.align_x = "CENTER"
    obj.data.align_y = "CENTER"
    obj.data.size = size
    obj.data.extrude = size * 0.012
    obj.data.bevel_depth = size * 0.006
    apply_material(obj, mat)
    return obj


def visibility(obj: bpy.types.Object, start: int, end: int, scale: float = 1.0) -> None:
    obj.scale = (0, 0, 0)
    obj.keyframe_insert("scale", frame=max(1, start - 8))
    obj.scale = (scale, scale, scale)
    obj.keyframe_insert("scale", frame=start)
    obj.keyframe_insert("scale", frame=end)
    obj.scale = (0, 0, 0)
    obj.keyframe_insert("scale", frame=min(END_FRAME, end + 8))


def pulse_visibility(obj: bpy.types.Object, start: int, end: int,
                     scale: float = 1.0) -> None:
    """Reveal an object with a readable pulse, then hold it until the shot ends."""
    obj.scale = (0, 0, 0)
    obj.keyframe_insert("scale", frame=max(1, start - 4))
    obj.scale = (scale * 1.35, scale * 1.35, scale * 1.35)
    obj.keyframe_insert("scale", frame=start + 5)
    obj.scale = (scale, scale, scale)
    obj.keyframe_insert("scale", frame=start + 12)
    obj.keyframe_insert("scale", frame=end)
    obj.scale = (0, 0, 0)
    obj.keyframe_insert("scale", frame=min(END_FRAME, end + 6))


def curve_line(name: str, points: list[Vector], mat: bpy.types.Material,
               bevel: float = 0.003) -> bpy.types.Object:
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.bevel_depth = bevel
    curve.bevel_resolution = 4
    spline = curve.splines.new("BEZIER")
    spline.bezier_points.add(len(points) - 1)
    for bp, co in zip(spline.bezier_points, points):
        bp.co = co
        bp.handle_left_type = "AUTO"
        bp.handle_right_type = "AUTO"
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    apply_material(obj, mat)
    return obj


def animate_curve_reveal(obj: bpy.types.Object, start: int, end: int) -> None:
    obj.data.bevel_factor_start = 0.0
    obj.data.bevel_factor_end = 0.0
    obj.data.keyframe_insert("bevel_factor_end", frame=start)
    obj.data.bevel_factor_end = 1.0
    obj.data.keyframe_insert("bevel_factor_end", frame=end)


def add_axis(name: str, origin: Vector, endpoint: Vector,
             mat: bpy.types.Material, start: int, end: int) -> bpy.types.Object:
    axis = curve_line(name, [origin, endpoint], mat, 0.0022)
    visibility(axis, start, end)
    return axis


def look_at(obj: bpy.types.Object, target: Vector) -> None:
    obj.rotation_euler = (target - obj.location).to_track_quat("-Z", "Y").to_euler()


def animate_transform(obj: bpy.types.Object, frames_and_locations: list[tuple[int, Vector]],
                      frames_and_targets: list[tuple[int, Vector]] | None = None) -> None:
    for frame, loc in frames_and_locations:
        obj.location = loc
        obj.keyframe_insert("location", frame=frame)
    if frames_and_targets:
        for frame, target in frames_and_targets:
            obj.location = dict(frames_and_locations)[frame]
            look_at(obj, target)
            obj.keyframe_insert("rotation_euler", frame=frame)


def add_tag(tag_id: str, x: float, y: float, white: bpy.types.Material,
            black: bpy.types.Material) -> bpy.types.Object:
    base = cube(f"Tag {tag_id}", board_point(x, y, 0.8),
                (0.055, 0.055, 0.0015), white, 0.001)
    # An original high-contrast visual motif, not a claimed AprilTag code.
    for ix, iy in ((-1, -1), (1, -1), (-1, 1), (1, 1), (0, 0)):
        cell = cube(f"Tag {tag_id} cell", board_point(x + ix * 13, y + iy * 13, 1.7),
                    (0.010, 0.010, 0.001), black)
        cell.parent = base
    return base


def add_keyboard(layout: dict, mats: dict[str, bpy.types.Material]) -> dict[str, bpy.types.Object]:
    dev = layout["devices"]["keyboard"]
    ox, oy = dev["nominal_origin_xy"]
    sx, sy, sz = dev["nominal_size"]
    # Repository station meshes are designed artifacts and placed by RC03 origins.
    import_stl(STL_DIR / "keyboard_station_left.stl", "Designed keyboard station L",
               mats["abs"], (80.0, 72.0, 0.0))
    import_stl(STL_DIR / "keyboard_station_right.stl", "Designed keyboard station R",
               mats["abs"], (242.5, 72.0, 0.0))
    cube("Measured keyboard lower chassis",
         board_point(ox + sx / 2, oy + sy / 2, sz * 0.38),
         (sx / 1000, sy / 1000, sz * 0.76 / 1000),
         mats["keyboard_side"], 0.006)
    cube("Measured keyboard top deck",
         board_point(ox + sx / 2, oy + sy / 2, sz * 0.79),
         ((sx - 3.0) / 1000, (sy - 3.0) / 1000, sz * 0.34 / 1000),
         mats["keyboard"], 0.005)
    # A restrained brushed perimeter and front chamfer catch highlights in
    # close-ups without changing the measured keyboard envelope.
    cube("Keyboard front accent", board_point(ox + sx / 2, oy + 3.2, sz - 1.4),
         ((sx - 8.0) / 1000, 0.003, 0.0022), mats["keyboard_trim"], 0.001)
    cube("Keyboard rear accent", board_point(ox + sx / 2, oy + sy - 3.2, sz - 1.4),
         ((sx - 8.0) / 1000, 0.003, 0.0022), mats["keyboard_trim"], 0.001)
    # The printable shell remains a measured envelope. The principal key rows
    # below are positioned from software/config/static_nominal_target_profiles.json:
    # 19.05 mm pitch, exact first-center offsets, and therefore H at
    # board (216.55, 154.00). Function and modifier caps are presentation
    # context only and stay inside the same measured chassis.
    pitch = 19.05
    rows = [
        ("ESC F1 F2 F3 F4 F5 F6 F7 F8 F9 F10 F11 F12 PRT SCR".split(),
         ox + 10.0, oy + 135.0, 0.82),
        (list("1234567890") + ["-", "="],
         ox + 22.0, oy + 111.0, 0.82),
        (list("QWERTYUIOP"),
         ox + 31.5, oy + 90.0, 0.82),
        (list("ASDFGHJKL") + [";", "'"],
         ox + 36.3, oy + 69.0, 0.82),
        (list("ZXCVBNM") + [",", ".", "/"],
         ox + 45.8, oy + 48.0, 0.82),
    ]
    named_keys: dict[str, bpy.types.Object] = {}
    for row_i, (legends, first_x, y, width_ratio) in enumerate(rows):
        for col, legend in enumerate(legends):
            x = first_x + col * pitch
            key_width = pitch * width_ratio
            lower = cube(f"Key well {row_i}-{col}", board_point(x, y, sz + 1.7),
                         (max(0.009, (key_width - 1.7) / 1000), 0.0180, 0.0034),
                         mats["key_side"], 0.0018)
            key = cube(f"Key cap {row_i}-{col}", board_point(x, y, sz + 4.0),
                       (max(0.008, (key_width - 3.0) / 1000), 0.0162, 0.0042),
                       mats["key"], 0.0024)
            lower["legend"] = legend
            key["legend"] = legend
            named_keys.setdefault(legend, key)
            legend_size = 0.0048 if len(legend) <= 2 else 0.0028
            board_text(
                f"Key legend {legend}-{row_i}-{col}", legend,
                board_point(x, y, sz + 6.2), legend_size, mats["legend"],
            )
    # Presentation-only outer modifiers, sized to resemble the photographed
    # compact keyboard without changing any named target coordinate.
    for label, x, y, width in (
        ("TAB", ox + 12.0, oy + 90.0, 22.0),
        ("CAPS", ox + 15.0, oy + 69.0, 28.0),
        ("SHIFT", ox + 20.0, oy + 48.0, 37.0),
        ("CTRL", ox + 14.0, oy + 24.0, 26.0),
        ("ALT", ox + 48.0, oy + 24.0, 24.0),
        ("SPACE", ox + 128.0, oy + 24.0, 112.0),
        ("ALT", ox + 201.0, oy + 24.0, 24.0),
        ("LEFT", ox + 247.0, oy + 24.0, 17.0),
        ("DOWN", ox + 266.0, oy + 24.0, 17.0),
        ("RIGHT", ox + 285.0, oy + 24.0, 17.0),
    ):
        cube(f"Modifier well {label}-{x}", board_point(x, y, sz + 1.7),
             ((width + 0.5) / 1000, 0.0180, 0.0034), mats["key_side"], 0.0018)
        key = cube(f"Modifier cap {label}-{x}", board_point(x, y, sz + 4.0),
                   ((width - 1.0) / 1000, 0.0162, 0.0042), mats["key"], 0.0024)
        board_text(f"Modifier legend {label}-{x}", label,
                   board_point(x, y, sz + 6.2),
                   0.0048 if len(label) <= 2 else 0.0028, mats["legend"])
        named_keys.setdefault(label, key)
    # Three small status lights and a recessed cable exit add scale cues that
    # survive the overhead and macro shots.
    for index, state_mat in enumerate((mats["green"], mats["cyan"], mats["amber"])):
        cylinder(f"Keyboard status LED {index + 1}",
                 board_point(ox + sx - 12.0 - index * 7.0, oy + sy - 10.0, sz + 2.0),
                 0.0015, 0.0010, state_mat, 24)
    cable_start = board_point(ox + sx / 2, oy + sy, sz * 0.68)
    keyboard_cable = curve_line(
        "Keyboard signal cable",
        [cable_start, cable_start + Vector((0.0, 0.040, 0.005)),
         cable_start + Vector((0.065, 0.075, 0.002))],
        mats["cable"], 0.0022,
    )
    keyboard_cable["presentation_detail"] = "KEYBOARD_CABLE_WITHIN_PRESENTATION_CLEARANCE"
    return named_keys


def add_phone(layout: dict, mats: dict[str, bpy.types.Material]) -> dict[str, bpy.types.Object]:
    dev = layout["devices"]["phone"]
    ox, oy = dev["nominal_origin_xy"]
    sx, sy, sz = dev["configured_size"]
    import_stl(STL_DIR / "phone_tcp_station.stl", "Designed phone station",
               mats["abs"], (411.0, 80.0, 0.0))
    phone = cube("Measured phone aluminum frame",
                 board_point(ox + sx / 2, oy + sy / 2, dev["support_plane_z"] + sz / 2),
                 (sx / 1000, sy / 1000, sz / 1000), mats["phone"], 0.006)
    screen_z = dev["nominal_screen_plane_z"] + 0.35
    screen = cube("Phone edge-to-edge glass",
                  board_point(ox + sx / 2, oy + sy / 2, screen_z),
                  ((sx - 4.2) / 1000, (sy - 7.0) / 1000, 0.0007),
                  mats["screen"], 0.0048)
    # Physical details: speaker, front camera, side controls, rear camera rise.
    cube("Phone receiver slit", board_point(ox + sx / 2, oy + sy - 8.0, screen_z + 0.55),
         (0.018, 0.0018, 0.0007), mats["metal"], 0.0008)
    cylinder("Phone front camera", board_point(ox + sx / 2 + 15.0, oy + sy - 8.0,
                                                screen_z + 0.65),
             0.0018, 0.0008, mats["screen_glass"], 32)
    cube("Phone volume rocker", board_point(ox - 0.4, oy + sy * 0.63,
                                             dev["support_plane_z"] + sz * 0.62),
         (0.0012, 0.030, 0.0024), mats["metal"], 0.0007)
    cube("Phone power button", board_point(ox + sx + 0.4, oy + sy * 0.61,
                                            dev["support_plane_z"] + sz * 0.62),
         (0.0012, 0.024, 0.0024), mats["metal"], 0.0007)
    camera_island = cube("Phone rear camera island",
                         board_point(ox + 15.0, oy + sy - 18.0,
                                     dev["support_plane_z"] + sz + 0.7),
                         (0.025, 0.032, 0.0018), mats["phone"], 0.005)
    camera_island.hide_render = True  # underside detail is retained in the editable scene

    # A restrained, product-like host interface gives the verification shot a
    # real destination without pretending to be a captured application UI.
    board_text("Phone UI brand", "TACTEVRA",
               board_point(ox + sx / 2, oy + sy - 23.0, screen_z + 0.65),
               0.0065, mats["cyan"])
    cube("Phone UI status rule", board_point(ox + sx / 2, oy + sy - 34.0,
                                              screen_z + 0.55),
         ((sx - 18.0) / 1000, 0.0012, 0.0005), mats["cyan"], 0.0005)
    cube("Phone UI target card", board_point(ox + sx / 2, oy + sy * 0.50,
                                              screen_z + 0.55),
         ((sx - 17.0) / 1000, 0.053, 0.0005), mats["screen_panel"], 0.006)
    board_text("Phone UI state", "HOST RESULT",
               board_point(ox + sx / 2, oy + 35.0, screen_z + 0.68),
               0.0048, mats["legend"])
    cube("Phone UI verified pill", board_point(ox + sx / 2, oy + 18.0,
                                                screen_z + 0.62),
         (0.043, 0.011, 0.0006), mats["green"], 0.005)
    board_text("Phone UI verified label", "VERIFIED",
               board_point(ox + sx / 2, oy + 18.0, screen_z + 1.0),
               0.0042, mats["white"])
    return {"root": phone, "screen": screen}


def _empty(name: str, parent: bpy.types.Object | None = None) -> bpy.types.Object:
    obj = bpy.data.objects.new(name, None)
    bpy.context.collection.objects.link(obj)
    obj.parent = parent
    obj.rotation_mode = "XYZ"
    return obj


def _parse_arm_contract() -> tuple[dict, dict[str, dict[str, tuple[float, float, float]]]]:
    manifest = json.loads(DIMENSION_MANIFEST_PATH.read_text(encoding="utf-8"))
    actual_hash = hashlib.sha256(ARM_URDF_PATH.read_bytes()).hexdigest()
    expected_hash = manifest["arm"]["kinematic_authority_sha256"]
    if actual_hash != expected_hash:
        raise RuntimeError(f"Pinned arm URDF hash changed: {actual_hash} != {expected_hash}")
    root = ET.fromstring(ARM_URDF_PATH.read_text(encoding="utf-8"))
    joints: dict[str, dict[str, tuple[float, float, float]]] = {}
    for joint in root.findall("joint"):
        origin = joint.find("origin")
        if origin is None:
            continue
        xyz = tuple(float(v) for v in origin.attrib.get("xyz", "0 0 0").split())
        rpy = tuple(float(v) for v in origin.attrib.get("rpy", "0 0 0").split())
        joints[joint.attrib["name"]] = {"xyz": xyz, "rpy": rpy}
    required = set(manifest["arm"]["joint_origin_xyz_m"])
    if missing := required.difference(joints):
        raise RuntimeError(f"Arm URDF lacks required joints: {sorted(missing)}")
    for name, expected in manifest["arm"]["joint_origin_xyz_m"].items():
        actual = joints[name]["xyz"]
        if any(abs(a - b) > 1e-9 for a, b in zip(actual, expected)):
            raise RuntimeError(f"Arm joint {name} disagrees with dimension manifest")
    return manifest, joints


def _fixed_then_rotating(name: str, parent: bpy.types.Object,
                         contract: dict[str, tuple[float, float, float]]) -> tuple[bpy.types.Object, bpy.types.Object]:
    fixed = _empty(f"{name} fixed transform", parent)
    fixed.location = contract["xyz"]
    fixed.rotation_euler = contract["rpy"]
    rotating = _empty(f"{name} revolute +Z", fixed)
    return fixed, rotating


def _beam_to(name: str, parent: bpy.types.Object, endpoint: tuple[float, float, float],
             mat: bpy.types.Material, width: float = 0.030) -> bpy.types.Object:
    vec = Vector(endpoint)
    beam = cube(name, (0, 0, 0), (width, width * 0.72, vec.length), mat, 0.004)
    beam.parent = parent
    beam.location = vec / 2
    beam.rotation_mode = "QUATERNION"
    beam.rotation_quaternion = vec.to_track_quat("Z", "Y")
    return beam


def _joint_marker(name: str, parent: bpy.types.Object, mat: bpy.types.Material,
                  radius: float = 0.029) -> bpy.types.Object:
    marker = cylinder(name, (0, 0, 0), radius, 0.046, mat)
    marker.parent = parent
    marker.location = (0, 0, 0)
    return marker


def _world_beam(name: str, start: Vector, end: Vector, mat: bpy.types.Material,
                width: float = 0.024) -> bpy.types.Object:
    """Create one dimensioned presentation link between world-space points."""
    vector = end - start
    beam = cube(name, (start + end) / 2,
                (width, width * 0.72, vector.length), mat, 0.004)
    beam.rotation_mode = "QUATERNION"
    beam.rotation_quaternion = vector.to_track_quat("Z", "Y")
    return beam


def add_continuous_press_arm(mats: dict[str, bpy.types.Material]) -> dict[str, object]:
    """Build one continuous, hardware-shaped arm rig ending at the H stylus.

    The official assembly surface remains available as source evidence, but a
    rig is required for the execution beat because the vendor STEP is a rigid
    presentation surface.  The rig deliberately repeats the RoArm-M3 visual
    language: rectangular serial servos, paired links, exposed fasteners,
    compact wrist plates, and the same black/metal finish.  It is still a
    presentation rig—not kinematic or collision evidence—but it must read as
    the same machine rather than as a generic industrial robot.
    """
    manifest, _joints = _parse_arm_contract()
    objects_before = set(bpy.context.scene.objects)
    # Match the official surface's measured board-frame base exactly.  The
    # prior proxy was 52 mm forward, which made the robot visibly jump at the
    # execution cut.
    tx, ty, _tz = manifest["arm"]["nominal_board_T_robot_world_translation"]
    base = board_point(tx, ty, 0)
    shoulder = base + Vector((0, 0, 0.120))
    wrist = board_point(216.55, 154.0, 0) + Vector((0, 0, 0.205))
    length_a = 0.2387
    length_b = 0.1550
    direction = wrist - shoulder
    distance = direction.length
    axis = direction.normalized()
    projection = (length_a ** 2 - length_b ** 2 + distance ** 2) / (2 * distance)
    height = math.sqrt(max(length_a ** 2 - projection ** 2, 0.0))
    side = axis.cross(Vector((0, 0, 1))).normalized()
    normal = side.cross(axis).normalized()
    elbow = shoulder + axis * projection + normal * height

    cube("Continuous arm base foot", base + Vector((0, 0, 0.020)),
         (0.118, 0.108, 0.040), mats["abs"], 0.008)
    cube("Continuous arm base electronics", base + Vector((0, 0, 0.057)),
         (0.094, 0.082, 0.052), mats["servo"], 0.006)
    cylinder("Continuous arm turntable", base + Vector((0, 0, 0.091)),
             0.050, 0.020, mats["arm_exact"], 64)

    # Rectangular servo bodies and round output bosses mirror the physical
    # ST-series actuator silhouette seen in the reference photographs.
    servo_points = ((shoulder, "shoulder", (0.068, 0.054, 0.080)),
                    (elbow, "elbow", (0.066, 0.052, 0.076)),
                    (wrist, "wrist", (0.058, 0.048, 0.066)))
    for point, label, size in servo_points:
        cube(f"Continuous arm {label} servo body", point, size,
             mats["servo"], 0.007)
        # Layered end caps, mounting ears, and connector blocks break the
        # generic smooth-box silhouette and repeat the construction language
        # of the detailed ST-series servos visible in the official assembly.
        cube(f"Continuous arm {label} front cap",
             point + axis * (size[2] * 0.34),
             (size[0] * 0.88, size[1] * 1.03, 0.010),
             mats["servo"], 0.0025)
        cube(f"Continuous arm {label} rear cap",
             point - axis * (size[2] * 0.34),
             (size[0] * 0.88, size[1] * 1.03, 0.010),
             mats["servo"], 0.0025)
        for ear_sign in (-1, 1):
            ear_center = point + side * (size[1] * 0.66 * ear_sign)
            _world_beam(
                f"Continuous arm {label} mounting ear {ear_sign:+d}",
                ear_center - axis * 0.026,
                ear_center + axis * 0.026,
                mats["carbon"], 0.010,
            )
        cube(f"Continuous arm {label} cable connector",
             point + normal * (size[0] * 0.52) - axis * 0.010,
             (0.018, 0.014, 0.014), mats["abs"], 0.002)
        for sign in (-1, 1):
            boss = cylinder(f"Continuous arm {label} output boss {sign:+d}",
                            point + side * (size[1] * 0.51 * sign),
                            0.021, 0.008, mats["metal"], 40)
            boss.rotation_euler = (math.pi / 2, 0, 0)
            cap = cylinder(f"Continuous arm {label} hub cap {sign:+d}",
                           point + side * (size[1] * 0.56 * sign),
                           0.014, 0.004, mats["arm_exact"], 32)
            cap.rotation_euler = (math.pi / 2, 0, 0)
        # Small brass identification plate makes the proxy read like the same
        # serial-servo family without asserting a legible vendor mark.
        cube(f"Continuous arm {label} identification plate",
             point - side * (size[1] * 0.515) + Vector((0, 0, 0.004)),
             (0.026, 0.003, 0.017), mats["brass"], 0.002)
    rail_offset = side * 0.014
    for suffix, offset in (("L", rail_offset), ("R", -rail_offset)):
        _world_beam(f"Continuous upper rail {suffix}", shoulder + offset,
                    elbow + offset, mats["carbon"], 0.019)
        _world_beam(f"Continuous forearm rail {suffix}", elbow + offset,
                    wrist + offset, mats["carbon"], 0.019)
        # Wider outer side plates make the paired-link architecture legible in
        # the execution shot instead of reading as two solid industrial bars.
        _world_beam(f"Continuous upper side plate {suffix}",
                    shoulder + offset * 1.55, elbow + offset * 1.55,
                    mats["carbon"], 0.010)
        _world_beam(f"Continuous forearm side plate {suffix}",
                    elbow + offset * 1.55, wrist + offset * 1.55,
                    mats["carbon"], 0.010)

    # Cross-braces and exposed bolts preserve the lightweight paired-link
    # character of the actual arm rather than reading as solid industrial bars.
    for link_name, start, end in (("upper", shoulder, elbow),
                                  ("forearm", elbow, wrist)):
        vector = end - start
        for brace_index, alpha in enumerate((0.28, 0.56, 0.82), start=1):
            center = start + vector * alpha
            brace = _world_beam(
                f"Continuous {link_name} cross brace {brace_index}",
                center - side * 0.022, center + side * 0.022,
                mats["arm_exact"], 0.008,
            )
            brace["presentation_detail"] = "ROARM_PAIRED_LINK_BRACE"
        for endpoint_name, endpoint in (("start", start), ("end", end)):
            for sign in (-1, 1):
                bolt = cylinder(
                    f"Continuous {link_name} {endpoint_name} bolt {sign:+d}",
                    endpoint + side * (0.027 * sign), 0.005, 0.006,
                    mats["metal"], 24,
                )
                bolt.rotation_euler = (math.pi / 2, 0, 0)

    # A restrained, physically attached harness is a strong continuity cue in
    # the reference photographs. It follows the joint chain and cannot be
    # mistaken for the old loose cable crossing the keyboard.
    harness = curve_line(
        "Continuous arm servo harness",
        [base + Vector((0.010, 0.0, 0.080)),
         shoulder + normal * 0.030,
         elbow + normal * 0.030,
         wrist + normal * 0.024],
        mats["wire"], 0.0028,
    )
    harness["presentation_detail"] = "JOINT_CHAIN_ATTACHED_SERVO_HARNESS"

    holder = cube("Continuous arm wrist servo", wrist + Vector((0, 0, -0.030)),
                  (0.060, 0.050, 0.066), mats["servo"], 0.006)
    wrist_plate = cube("Continuous arm gripper plate", wrist + Vector((0, 0, -0.073)),
                       (0.072, 0.010, 0.050), mats["arm_exact"], 0.004)
    jaw_left = cube("Continuous arm gripper jaw left",
                    wrist + Vector((-0.023, 0, -0.112)),
                    (0.012, 0.026, 0.070), mats["arm_exact"], 0.003)
    jaw_right = cube("Continuous arm gripper jaw right",
                     wrist + Vector((0.023, 0, -0.112)),
                     (0.012, 0.026, 0.070), mats["arm_exact"], 0.003)
    collar = cylinder("Continuous arm stylus collar", wrist + Vector((0, 0, -0.071)),
                      0.012, 0.028, mats["arm_exact"], 48)
    stylus_center = board_point(216.55, 154.0, 0) + Vector((0, 0, 0.105))
    stylus = cylinder("Continuous arm stylus", stylus_center, 0.004, 0.140,
                      mats["metal"], 48)
    bpy.ops.mesh.primitive_cone_add(vertices=48, radius1=0.0012, radius2=0.004,
                                    depth=0.012,
                                    location=board_point(216.55, 154.0, 29))
    tip = bpy.context.object
    tip.name = "Continuous arm compliant stylus tip"
    apply_material(tip, mats["arm_exact"])
    moving = (holder, wrist_plate, jaw_left, jaw_right, collar, stylus, tip)
    for component in moving:
        base_z = component.location.z
        for frame, offset in ((1, 0.0), (1288, 0.0), (1300, -0.004),
                              (1320, -0.004), (1332, 0.0), (END_FRAME, 0.0)):
            component.location.z = base_z + offset
            component.keyframe_insert("location", frame=frame)
        component["evidence_status"] = "URDF_DERIVED_PRESENTATION_PROXY_NOT_KINEMATIC_EVIDENCE"
    objects = tuple(obj for obj in bpy.context.scene.objects if obj not in objects_before)
    return {"root": base, "objects": objects, "moving": moving, "manifest": manifest}


def add_robot(mats: dict[str, bpy.types.Material]) -> dict[str, object]:
    """Place the hash-verified official assembly surface in the RC03 frame.

    The official STEP assembly is prepared below /tmp and is not redistributed.
    Its default pose is rigid in this presentation; URDF/controller motion
    remains a separate contract.
    """
    manifest, joints = _parse_arm_contract()
    if not OFFICIAL_ARM_STL_PATH.is_file():
        raise FileNotFoundError(
            "The exact RoArm presentation mesh is missing. Run "
            "`python presentations/blender/prepare_official_arm_asset.py` first."
        )
    tx, ty, tz = manifest["arm"]["nominal_board_T_robot_world_translation"]
    arm = import_stl(
        OFFICIAL_ARM_STL_PATH,
        "VENDOR-SOURCED — Waveshare RoArm-M3 exact assembly surface",
        mats["arm_exact"],
        (tx, ty, tz),
    )
    arm.rotation_euler[2] = math.radians(manifest["arm"]["nominal_board_T_robot_world_yaw_deg"])
    arm["surface_geometry"] = "HASH_VERIFIED_OFFICIAL_STEP_LOCAL_DERIVATIVE"
    arm["source_archive_sha256"] = manifest["arm"]["surface_geometry"]["source_archive_sha256"]
    arm["kinematic_authority_sha256"] = manifest["arm"]["kinematic_authority_sha256"]
    arm["pose_status"] = "OFFICIAL_DEFAULT_ASSEMBLY_POSE_STATIC_PRESENTATION_ONLY"
    return {"root": arm, "objects": (arm,)}


def keyed_render_window(objects: tuple[bpy.types.Object, ...], start: int, end: int) -> None:
    """Render *objects* only inside an inclusive frame window.

    Blender's hide_render property is discrete, so keys are placed one frame
    either side of the window. This is used to distinguish the exact static
    vendor surface from the explicitly conceptual articulated press proxy.
    """
    for obj in objects:
        obj.hide_render = True
        obj.keyframe_insert("hide_render", frame=1)
        if start > 1:
            obj.keyframe_insert("hide_render", frame=start - 1)
        obj.hide_render = False
        obj.keyframe_insert("hide_render", frame=start)
        obj.keyframe_insert("hide_render", frame=end)
        if end < END_FRAME:
            obj.hide_render = True
            obj.keyframe_insert("hide_render", frame=end + 1)


def add_target_ring(name: str, x: float, y: float, z: float,
                    mat: bpy.types.Material, start: int, end: int) -> bpy.types.Object:
    bpy.ops.mesh.primitive_torus_add(major_radius=0.020, minor_radius=0.0028,
                                   major_segments=48, minor_segments=10,
                                   location=board_point(x, y, z))
    obj = bpy.context.object
    obj.name = name
    apply_material(obj, mat)
    visibility(obj, start, end)
    return obj


def setup_render(scene: bpy.types.Scene) -> None:
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.resolution_percentage = 100
    scene.render.fps = FPS
    scene.frame_start = 1
    scene.frame_end = END_FRAME
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    # Preserve a clean intermediate so the upload master is not merely
    # up-bitrated from Blender's medium-quality animation output.
    scene.render.ffmpeg.constant_rate_factor = "PERC_LOSSLESS"
    scene.render.ffmpeg.ffmpeg_preset = "GOOD"
    scene.render.use_file_extension = True
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.view_settings.exposure = -1.15
    scene.world.color = (0.012, 0.016, 0.023)


def build() -> bpy.types.Scene:
    clean_scene()
    layout = json.loads(LAYOUT_PATH.read_text(encoding="utf-8"))
    scene = bpy.context.scene
    setup_render(scene)

    mats = {
        "abs": material("Printed matte black ABS", (0.012, 0.016, 0.021, 1), roughness=0.34),
        "carbon": material("Carbon link", (0.018, 0.023, 0.028, 1), metallic=0.2, roughness=0.24),
        "servo": material("Black servo", (0.010, 0.014, 0.020, 1), metallic=0.12, roughness=0.36),
        "metal": material("Machined metal", (0.22, 0.28, 0.34, 1), metallic=0.85, roughness=0.20),
        "brass": material("Servo identification brass", (0.42, 0.27, 0.07, 1),
                           metallic=0.72, roughness=0.26),
        "arm_exact": material("Official RoArm assembly finish", (0.017, 0.022, 0.028, 1),
                              metallic=0.48, roughness=0.24),
        "wood": textured_material("Light birch", (0.55, 0.33, 0.16, 1),
                                    scale=7.0, detail=3.0, roughness=0.48),
        "keyboard": material("Keyboard body", (0.001, 0.002, 0.004, 1), roughness=0.31),
        "keyboard_side": material("Keyboard lower shell", (0.006, 0.008, 0.011, 1),
                                  metallic=0.12, roughness=0.42),
        "keyboard_trim": material("Keyboard brushed edge", (0.14, 0.18, 0.22, 1),
                                  metallic=0.82, roughness=0.21),
        "key": material("Keyboard keys", (0.003, 0.005, 0.008, 1), roughness=0.38),
        "key_side": material("Keyboard key wells", (0.0006, 0.0008, 0.0012, 1),
                             roughness=0.48),
        "legend": material("Keyboard legends", (0.34, 0.39, 0.45, 1), roughness=0.50),
        "phone": material("Phone edge", (0.03, 0.04, 0.05, 1), metallic=0.6, roughness=0.20),
        "screen": material("Phone screen", (0.008, 0.015, 0.022, 1), metallic=0.15, roughness=0.16,
                           emission=(0.01, 0.03, 0.05, 1), emission_strength=0.14),
        "screen_glass": material("Phone optical glass", (0.004, 0.009, 0.016, 1),
                                 metallic=0.35, roughness=0.08),
        "screen_panel": material("Phone interface panel", (0.018, 0.043, 0.065, 1),
                                 metallic=0.08, roughness=0.20,
                                 emission=(0.012, 0.06, 0.095, 1),
                                 emission_strength=0.65),
        "cable": material("Signal cable rubber", (0.004, 0.006, 0.009, 1), roughness=0.62),
        "wire": material("Servo harness", (0.035, 0.020, 0.017, 1), metallic=0.05,
                           roughness=0.54),
        "white": material("Reference white", (0.92, 0.95, 0.98, 1), roughness=0.55),
        "cyan": material("Tactevra cyan", (0.00, 0.52, 0.92, 1), roughness=0.22,
                         emission=(0.00, 0.52, 0.92, 1), emission_strength=3.5),
        "amber": material("Validation amber", (1.00, 0.36, 0.04, 1), roughness=0.24,
                          emission=(1.00, 0.22, 0.01, 1), emission_strength=2.8),
        "green": material("Verified green", (0.05, 0.80, 0.38, 1), roughness=0.20,
                          emission=(0.02, 0.80, 0.28, 1), emission_strength=3.2),
        "red": material("Blocked red", (0.86, 0.05, 0.08, 1), roughness=0.22,
                        emission=(0.86, 0.02, 0.04, 1), emission_strength=2.8),
    }

    # Designed portal geometry is already expressed in board frame millimetres.
    portal = import_stl(PORTAL_PATH, "DESIGNED — printable camera portal", mats["abs"])
    # Establish the complete workcell in the opening, explain the camera in the
    # perception chapter, then remove the tall portal from the beauty layer for
    # the controller close-ups. The camera remains represented by its frame and
    # overlays; this is a presentation cutaway, not a hardware configuration.
    portal.hide_render = False
    portal.keyframe_insert("hide_render", frame=1)
    portal.keyframe_insert("hide_render", frame=528)
    portal.hide_render = True
    portal.keyframe_insert("hide_render", frame=529)
    portal.keyframe_insert("hide_render", frame=1560)
    portal.hide_render = False
    portal.keyframe_insert("hide_render", frame=1561)
    portal.keyframe_insert("hide_render", frame=END_FRAME)
    cube("MEASURED — 610 × 457 × 18 mm board", (0, 0, -0.009),
         (0.610, 0.457, 0.018), mats["wood"], 0.006)
    cube("Bench", (0, -0.01, -0.050), (1.15, 0.88, 0.065),
         textured_material("Bench", (0.055, 0.066, 0.080, 1), scale=5.0,
                           detail=2.0, metallic=0.15, roughness=0.52), 0.012)
    keyboard_keys = add_keyboard(layout, mats)
    phone = add_phone(layout, mats)
    phone_dev = layout["devices"]["phone"]
    phone_x = phone_dev["nominal_origin_xy"][0] + phone_dev["configured_size"][0] / 2
    phone_y = phone_dev["nominal_origin_xy"][1] + phone_dev["configured_size"][1] / 2
    tag_objects: list[tuple[str, bpy.types.Object, tuple[float, float]]] = []
    for tag_id, tag in layout["direct_tags"]["tags"].items():
        xy = tuple(tag["detection_center_xy"])
        tag_objects.append(
            (tag_id, add_tag(tag_id, *xy, mats["white"], mats["abs"]), xy)
        )
    # Hardware appearance and motion meaning are deliberately separate. The
    # hash-verified official Waveshare STEP derivative is the visual authority
    # in every architectural shot. Only the short execution close-up switches
    # to the URDF-dimensioned articulated proxy, where the overlay explicitly
    # identifies the motion as a simulation. This prevents a simplified proxy
    # from being mistaken for the expected physical hardware.
    exact_robot = add_robot(mats)
    motion_proxy = add_continuous_press_arm(mats)
    keyed_render_window(exact_robot["objects"], 1, 1224)
    keyed_render_window(motion_proxy["objects"], 1225, 1392)
    # The exact hardware surface returns for verification and the final system
    # view; the conceptual proxy never appears without its evidence label.
    for component in exact_robot["objects"]:
        component.hide_render = True
        component.keyframe_insert("hide_render", frame=1225)
        component.keyframe_insert("hide_render", frame=1392)
        component.hide_render = False
        component.keyframe_insert("hide_render", frame=1393)
        component.keyframe_insert("hide_render", frame=END_FRAME)
    h_key = keyboard_keys["H"]
    h_key_z = h_key.location.z
    for frame, offset in ((1225, 0.0), (1288, 0.0), (1300, -0.004),
                          (1320, -0.004), (1332, 0.0), (1392, 0.0)):
        h_key.location.z = h_key_z + offset
        h_key.keyframe_insert("location", frame=frame)
    # A recognizable camera hangs below the carriage instead of disappearing
    # inside the portal mounting plate. The optical axis remains centered on
    # the nominal board target.
    cam_center = board_point(305, 228.5, 970)
    camera_hardware = [
        cube("Designed camera body", cam_center, (0.086, 0.066, 0.052), mats["abs"], 0.008),
        cube("Designed camera top mount", cam_center + Vector((0, 0, 0.047)),
             (0.046, 0.042, 0.044), mats["metal"], 0.005),
    ]
    lens = cylinder("Machine vision lens", cam_center + Vector((0, 0, -0.047)),
                    0.022, 0.050, mats["metal"])
    lens.rotation_euler = (0, 0, 0)
    lens_glass = cylinder("Machine vision front glass",
                          cam_center + Vector((0, 0, -0.073)),
                          0.016, 0.003, mats["cyan"], 48)
    lens_glass.rotation_euler = (0, 0, 0)
    status_light = cylinder("Camera status light", cam_center + Vector((0.031, -0.034, 0.006)),
                            0.004, 0.003, mats["green"], 32)
    status_light.rotation_euler = (math.pi / 2, 0, 0)
    camera_hardware.extend((lens, lens_glass, status_light))
    for component in camera_hardware:
        component.hide_render = False
        component.keyframe_insert("hide_render", frame=1)
        component.keyframe_insert("hide_render", frame=528)
        component.hide_render = True
        component.keyframe_insert("hide_render", frame=529)
        component.keyframe_insert("hide_render", frame=1560)
        component.hide_render = False
        component.keyframe_insert("hide_render", frame=1561)

    # Render camera and cinematic movement.
    bpy.ops.object.camera_add(location=(1.90, -2.10, 0.96))
    camera = bpy.context.object
    camera.name = "Explainer camera"
    camera.data.lens = 48
    camera.data.sensor_width = 36
    scene.camera = camera
    camera_positions = [
        # Request / stakes / promise: a readable three-quarter hero view. Keep
        # the complete board, exact arm, and camera portal in frame without the
        # old extreme-wide dead space.
        (1, Vector((0.38, -1.52, 0.88))), (96, Vector((0.32, -1.40, 0.83))),
        (97, Vector((0.28, -1.30, 0.78))), (240, Vector((0.12, -1.10, 0.70))),
        (241, Vector((0.18, -1.18, 0.72))), (336, Vector((-0.02, -1.02, 0.66))),
        # Perceive: camera fixture, then its measured top-down view.
        (337, Vector((0.62, -0.36, 1.18))), (408, Vector((0.28, -0.18, 1.02))),
        # The lens POV begins below the physical camera body so the fixture
        # cannot occlude or defocus the board evidence.
        (409, Vector((-0.10, -0.04, 0.92))), (528, Vector((0.10, 0.04, 0.84))),
        # Proposal and both gate decisions keep the exact arm visibly still.
        # The previous reverse angle was dominated by a portal leg; this angle
        # preserves the workcell context behind the screen-space evidence card.
        (529, Vector((0.46, -1.02, 0.66))), (720, Vector((0.20, -0.84, 0.56))),
        (721, Vector((0.34, -0.98, 0.60))), (888, Vector((0.20, -0.82, 0.54))),
        (889, Vector((0.18, -0.82, 0.54))), (1056, Vector((0.38, -0.92, 0.60))),
        # Resolve top-down, execute close-up, verify, payoff, end card.
        # Unobstructed top-down keyboard resolution, then a medium tooling shot
        # that keeps the simulated holder, stylus, and H key in one frame.
        # Resolve is deliberately square to the keyboard so the H legend and
        # coordinate trace read upright rather than on a distracting diagonal.
        (1057, board_point(242.5, 158.5, 675)),
        (1224, board_point(242.5, 158.5, 575)),
        # A wider execution move keeps the base, paired links, servo stack,
        # gripper, stylus, and H target in one continuous-machine composition.
        (1225, Vector((0.43, -1.16, 0.79))), (1392, Vector((0.24, -0.94, 0.62))),
        (1393, board_point(phone_x - 140.0, phone_y - 270.0, 260)),
        (1560, board_point(phone_x - 82.0, phone_y - 218.0, 210)),
        # Push the payoff closer so the workcell fills the lower half while
        # retaining dark title-safe space for the shared-contract summary.
        (1561, Vector((-0.05, -0.85, 0.55))), (1728, Vector((0.15, -0.98, 0.60))),
        (1729, Vector((0.34, -1.42, 0.84))), (END_FRAME, Vector((0.28, -1.25, 0.76))),
    ]
    targets = [
        (1, Vector((0, 0.02, 0.38))), (336, Vector((0, 0.02, 0.38))),
        (337, Vector((0, 0.02, 1.00))), (408, Vector((0, 0.02, 0.98))),
        (409, Vector((0, 0.00, 0.03))), (528, Vector((0, 0.00, 0.03))),
        # Tilt the three decision shots toward the board. The arm remains the
        # hero, but the keyboard and calibrated surface now provide changing
        # spatial context instead of three nearly identical black backdrops.
        (529, Vector((0, -0.02, 0.29))), (720, Vector((0, -0.02, 0.29))),
        (721, Vector((0, -0.02, 0.27))), (888, Vector((0, -0.02, 0.27))),
        (889, Vector((0, -0.02, 0.28))), (1056, Vector((0, -0.02, 0.28))),
        (1057, board_point(216.55, 154.0, 22)), (1224, board_point(216.55, 154.0, 22)),
        (1225, board_point(216.55, 154.0, 105)), (1392, board_point(216.55, 154.0, 92)),
        # Focus on the actual glass plane rather than a point above the phone;
        # the former macro shot was visibly soft at the verification moment.
        (1393, board_point(phone_x, phone_y, phone_dev["nominal_screen_plane_z"] + 1.0)),
        (1560, board_point(phone_x, phone_y, phone_dev["nominal_screen_plane_z"] + 1.0)),
        (1561, Vector((-0.08, 0.02, 0.30))),
        (1728, Vector((-0.08, 0.02, 0.30))),
        (1729, Vector((0, 0.02, 0.38))), (END_FRAME, Vector((0, 0.02, 0.38))),
    ]
    animate_transform(camera, camera_positions, targets)

    # The straight-down look-at is geometrically square but Blender's default
    # roll places the keyboard's long edge vertically. Rotate only the Resolve
    # chapter around the optical axis so labels read naturally left-to-right.
    camera_location_by_frame = dict(camera_positions)
    camera_target_by_frame = dict(targets)
    for frame in (1057, 1224):
        camera.location = camera_location_by_frame[frame]
        camera.rotation_euler = (
            camera_target_by_frame[frame] - camera.location
        ).to_track_quat("-Z", "Y").to_euler()
        camera.rotation_euler.rotate_axis("Z", math.radians(-90))
        camera.keyframe_insert("rotation_euler", frame=frame)

    # A focus target tracks the same authored points as the camera aim. Depth
    # of field remains subtle enough to preserve dimension evidence while
    # separating foreground hardware from the studio background.
    focus = _empty("Animated camera focus")
    for frame, target in targets:
        focus.location = target
        focus.keyframe_insert("location", frame=frame)
    camera.data.dof.use_dof = True
    camera.data.dof.focus_object = focus
    camera.data.dof.aperture_fstop = 11.0
    lens_keys = (
        (1, 38), (96, 42), (97, 50), (240, 72), (241, 54), (336, 70),
        (337, 52), (408, 78), (409, 38), (528, 45),
        (529, 55), (720, 70), (721, 60), (888, 72),
        (889, 65), (1056, 82), (1057, 58), (1224, 70),
        (1225, 52), (1392, 68), (1393, 62), (1560, 74),
        (1561, 44), (1728, 58), (1729, 48), (END_FRAME, 54),
    )
    for frame, focal_length in lens_keys:
        camera.data.lens = focal_length
        camera.data.keyframe_insert("lens", frame=frame)
    # Shot-specific depth of field separates architectural context from the
    # target-resolution, press, and phone-result macro beats.
    aperture_keys = (
        (1, 8.0), (336, 7.1), (337, 6.3), (408, 5.6),
        (409, 10.0), (528, 9.0), (529, 7.1), (1056, 6.3),
        (1057, 9.0), (1224, 8.0), (1225, 6.3), (1392, 5.6),
        (1393, 9.0), (1560, 8.0), (1561, 7.1), (END_FRAME, 6.3),
    )
    for frame, aperture in aperture_keys:
        camera.data.dof.aperture_fstop = aperture
        camera.data.dof.keyframe_insert("aperture_fstop", frame=frame)

    # Studio illumination.
    bpy.ops.object.light_add(type="AREA", location=(0.0, -0.18, 1.55))
    key = bpy.context.object
    key.name = "Overhead softbox"
    key.data.energy = 145
    key.data.shape = "DISK"
    key.data.size = 1.2
    key.rotation_euler = (0, 0, 0)
    bpy.ops.object.light_add(type="AREA", location=(0.78, -0.52, 0.65))
    fill = bpy.context.object
    fill.data.energy = 75
    fill.data.color = (0.68, 0.82, 1.0)
    fill.data.size = 0.75
    look_at(fill, Vector((0, 0, 0.3)))
    bpy.ops.object.light_add(type="AREA", location=(-0.62, 0.34, 0.82))
    rim = bpy.context.object
    rim.data.energy = 110
    # Keep the black keyboard reading consistently black in every chapter.
    # The former orange rim made the execution keyboard appear copper.
    rim.data.color = (0.46, 0.66, 1.0)
    rim.data.size = 0.55
    look_at(rim, Vector((0, 0.04, 0.38)))
    bpy.ops.object.light_add(type="AREA", location=(-0.35, -0.42, 0.50))
    arm_rim = bpy.context.object
    arm_rim.name = "Arm detail strip"
    arm_rim.data.energy = 135
    arm_rim.data.color = (0.48, 0.72, 1.0)
    arm_rim.data.shape = "RECTANGLE"
    arm_rim.data.size = 0.42
    arm_rim.data.size_y = 0.16
    look_at(arm_rim, Vector((0, -0.05, 0.30)))

    # Shot labels. They are camera-facing 3D graphics, not post-production text.
    hero = text_object("Hero title", "TACTEVRA\nPHYSICAL INTELLIGENCE, CHECKED",
                       Vector((0.0, -0.23, 0.68)), 0.034, mats["white"], camera)
    visibility(hero, 1, 86)
    evidence = text_object("Evidence label",
                           "REAL RC03 CAD  •  MEASURED DEVICE ENVELOPES  •  OFFICIAL ARM ASSEMBLY SURFACE",
                           Vector((0.0, -0.18, 0.59)), 0.010, mats["cyan"], camera)
    visibility(evidence, 10, 86)

    vision = text_object("Vision label", "STATIC VISION\n1000 mm NOMINAL OPTICAL TARGET",
                         Vector((0.0, 0.07, 1.14)), 0.035, mats["white"], camera)
    visibility(vision, 337, 408)
    sight = curve_line("Vision ray",
                       [board_point(305, 228.5, 995), board_point(305, 228.5, 14)], mats["cyan"], 0.002)
    visibility(sight, 337, 528)

    # In the camera POV the four physical tags pulse in sequence and the board
    # axes draw on the board itself, making perception visible without a card.
    for index, (tag_id, _tag, xy) in enumerate(tag_objects):
        ring = add_target_ring(f"Perception pulse {tag_id}", xy[0], xy[1], 4.2,
                               mats["cyan"], 409, 528)
        pulse_visibility(ring, 414 + index * 18, 528)
    perceive_origin = board_point(42, 42, 5)
    x_axis = add_axis("Perceive board X", perceive_origin,
                      perceive_origin + Vector((0.115, 0, 0)), mats["cyan"], 448, 528)
    y_axis = add_axis("Perceive board Y", perceive_origin,
                      perceive_origin + Vector((0, 0.115, 0)), mats["cyan"], 458, 528)
    animate_curve_reveal(x_axis, 448, 472)
    animate_curve_reveal(y_axis, 458, 482)
    x_label = board_text("Perceive X label", "X", perceive_origin + Vector((0.126, 0, 0.002)),
                         0.015, mats["cyan"])
    y_label = board_text("Perceive Y label", "Y", perceive_origin + Vector((0, 0.126, 0.002)),
                         0.015, mats["cyan"])
    visibility(x_label, 462, 528)
    visibility(y_label, 472, 528)

    arm_detail = text_object("Arm detail label", "ROARM-M3\nURDF-DERIVED ARM PROXY",
                             Vector((0.0, -0.10, 0.42)), 0.030, mats["white"], camera)
    visibility(arm_detail, 97, 240)

    devices = text_object("Device label", "INDEXED DEVICE GEOMETRY\nKEYBOARD + PHONE + DIRECT TAGS",
                          Vector((0.02, -0.14, 0.29)), 0.031, mats["white"], camera)
    visibility(devices, 409, 528)
    h_ring = add_target_ring("Keyboard target H", 216.55, 154.0, 29,
                             mats["cyan"], 1057, 1320)
    h_target_label = board_text("Resolved H label", "H",
                                board_point(216.55, 154.0, 32), 0.013, mats["cyan"])
    visibility(h_target_label, 1120, 1300)

    # One thin, flat trace is the only spatial guide in Resolve. Additional
    # axis tubes looked like physical cables and obscured the keyboard.
    frame_trace = curve_line(
        "Camera to H resolve trace",
        [board_point(305, 228.5, 35), board_point(216.55, 154.0, 35)],
        mats["cyan"], 0.0009,
    )
    visibility(frame_trace, 1080, 1200)
    animate_curve_reveal(frame_trace, 1080, 1148)

    # Verification is grounded on the physical receiver screen, not a floating
    # glyph. The phone is therefore introduced as the host display in use.
    host_h = board_text("Verified host character H", "H",
                        board_point(phone_x, phone_y,
                                    phone_dev["nominal_screen_plane_z"] + 1.3),
                        0.032, mats["green"])
    visibility(host_h, 1438, 1560)

    checked = text_object("Motion label", "PROPOSE → VALIDATE → EXECUTE → VERIFY",
                          Vector((0.0, -0.15, 0.48)), 0.030, mats["white"], camera)
    visibility(checked, 529, 1056)
    route = curve_line("Checked route",
                       [board_point(305, 410, 260), board_point(235, 180, 115),
                        board_point(216.55, 154, 48)], mats["amber"], 0.003)
    route.hide_render = True

    # The luminous packet communicates admitted-command progression. It is a
    # conceptual state marker, not a simulated TCP or qualified arm motion.
    packet = cylinder("Admitted command packet", board_point(305, 410, 260),
                      0.009, 0.012, mats["cyan"], 32)
    packet.rotation_euler = (math.pi / 2, 0, 0)
    packet.hide_render = True
    packet_path = [
        (1225, board_point(305, 410, 260)),
        (1280, board_point(235, 180, 115)),
        (1320, board_point(216.55, 154, 48)),
        (1392, board_point(216.55, 154, 48)),
    ]
    for frame, point in packet_path:
        packet.location = point
        packet.keyframe_insert("location", frame=frame)

    close = text_object("Closing title", "ONE SHARED CONTRACT\nFROM USER INTENT TO VERIFIED ACTION",
                        Vector((0.0, -0.21, 0.80)), 0.043, mats["white"], camera)
    visibility(close, 1561, END_FRAME)
    disclaimer = text_object("Disclaimer",
                             "CONCEPT VISUALIZATION • RC03 NOMINAL GEOMETRY • NOT MOTION OR FABRICATION QUALIFICATION",
                             Vector((0.0, -0.20, 0.68)), 0.014, mats["amber"], camera)
    visibility(disclaimer, 1729, END_FRAME)

    # Smooth cinematic interpolation without overshooting the bounded poses.
    for obj in scene.objects:
        if obj.animation_data and obj.animation_data.action:
            for fcurve in obj.animation_data.action.fcurves:
                for point in fcurve.keyframe_points:
                    point.interpolation = "BEZIER"
                    point.handle_left_type = "AUTO_CLAMPED"
                    point.handle_right_type = "AUTO_CLAMPED"

    scene["evidence_notice"] = (
        "Portal/stations are repository CAD; board/devices are RC03 measured envelopes; "
        "the static arm beauty surface is a hash-verified local derivative of the official "
        "Waveshare STEP; the execution-only proxy is dimensioned from the pinned official "
        "URDF contract. Its pose and H contact are presentation simulations, not motion "
        "qualification. The portal is hidden in controller close-ups for visual clarity."
    )
    scene["source_layout"] = str(LAYOUT_PATH.relative_to(ROOT))
    scene["source_portal"] = str(PORTAL_PATH.relative_to(ROOT))
    return scene


def write_ass_overlay(path: Path) -> None:
    """Write screen-space information graphics for the rendered film."""
    path.write_text(
        """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Black,Arial,20,&H00000000,&H00000000,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1
Style: Request,Consolas,66,&H00FFFFFF,&H000000FF,&H80081119,&H00000000,-1,0,0,0,100,100,0,0,1,2,0,5,80,80,0,1
Style: Hero,Arial,68,&H00FFFFFF,&H000000FF,&H80081119,&H70000000,-1,0,0,0,100,100,0,0,1,3,1,8,90,90,70,1
Style: Stage,Arial,48,&H00FFFFFF,&H000000FF,&H80081119,&H70000000,-1,0,0,0,100,100,0,0,1,3,1,8,90,90,62,1
Style: Sub,Arial,32,&H00E7ECF2,&H000000FF,&H90081119,&H70000000,0,0,0,0,100,100,0,0,1,2,1,8,100,100,70,1
Style: Tracker,Arial,24,&H00D8DEE8,&H000000FF,&H90081119,&H90000000,-1,0,0,0,100,100,1,0,1,3,1,2,60,60,26,1
Style: Card,Consolas,30,&H00F3F6FA,&H000000FF,&H00373E49,&HD00A0E14,-1,0,0,0,100,100,0,0,3,2,0,7,150,150,245,1
Style: CenterCard,Consolas,32,&H00F3F6FA,&H000000FF,&H00373E49,&HD00A0E14,-1,0,0,0,100,100,0,0,3,2,0,5,240,240,0,1
Style: RightCard,Consolas,30,&H00F3F6FA,&H000000FF,&H00373E49,&HD00A0E14,-1,0,0,0,100,100,0,0,3,2,0,9,150,150,245,1
Style: VerifyCard,Consolas,34,&H00F3F6FA,&H000000FF,&H00373E49,&HE00A0E14,-1,0,0,0,100,100,0,0,3,2,0,5,80,80,0,1
Style: HostGlyph,Consolas,92,&H004FCC33,&H000000FF,&H00373E49,&HE00A0E14,-1,0,0,0,100,100,0,0,3,2,0,5,80,80,0,1
Style: Badge,Arial,28,&H00FFFFFF,&H000000FF,&H00373E49,&HD00A0E14,-1,0,0,0,100,100,0,0,3,2,0,8,90,90,86,1
Style: Bug,Arial,21,&H00F8C845,&H000000FF,&H90081119,&H70000000,-1,0,0,0,100,100,1,0,1,2,1,9,44,44,30,1
Style: Fine,Arial,18,&H00898F99,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,2,80,80,28,1
Style: Loop,Arial,34,&H00D8DEE8,&H000000FF,&H90081119,&HA0000000,-1,0,0,0,100,100,1,0,1,3,1,5,70,70,0,1
Style: EndTitle,Arial,112,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,1,0,1,0,0,5,70,70,0,1
Style: EndSub,Arial,40,&H00E7ECF2,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,5,70,70,0,1
Style: EndURL,Consolas,30,&H00F8C845,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,0,0,5,70,70,0,1
Style: EndFine,Arial,28,&H00959BA5,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,2,80,80,44,1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
Dialogue: 0,0:00:00.00,0:00:04.00,Black,,0,0,0,,{\\p1}m 0 0 l 1920 0 l 1920 1080 l 0 1080{\\p0}
Dialogue: 1,0:00:00.35,0:00:04.00,Request,,0,0,0,,{\\fad(220,180)}> Press the H key.  ▌
Dialogue: 2,0:00:04.00,0:01:12.00,Bug,,0,0,0,,TACTEVRA
Dialogue: 2,0:00:10.00,0:00:14.00,Hero,,0,0,0,,{\\fad(250,220)}ONE REQUEST. ONE CHECKED PHYSICAL ACTION.
Dialogue: 2,0:00:10.30,0:00:14.00,Sub,,0,0,0,,{\\fad(250,220)}TACTEVRA
Dialogue: 1,0:00:14.00,0:00:22.00,Tracker,,0,0,0,,{\\c&H00F8C845}PERCEIVE{\\c&H00D8DEE8}  →  PROPOSE  →  CHECK  →  EXECUTE  →  VERIFY
Dialogue: 1,0:00:22.00,0:00:30.00,Tracker,,0,0,0,,PERCEIVE  →  {\\c&H004C9BFF}PROPOSE{\\c&H00D8DEE8}  →  CHECK  →  EXECUTE  →  VERIFY
Dialogue: 1,0:00:30.00,0:00:44.00,Tracker,,0,0,0,,PERCEIVE  →  PROPOSE  →  {\\c&H00505AFF}CHECK{\\c&H00D8DEE8}  →  EXECUTE  →  VERIFY
Dialogue: 1,0:00:44.00,0:00:51.00,Tracker,,0,0,0,,PERCEIVE  →  PROPOSE  →  {\\c&H00F8C845}CHECK{\\c&H00D8DEE8}  →  EXECUTE  →  VERIFY
Dialogue: 1,0:00:51.00,0:00:58.00,Tracker,,0,0,0,,PERCEIVE  →  PROPOSE  →  CHECK  →  {\\c&H00F8C845}EXECUTE{\\c&H00D8DEE8}  →  VERIFY
Dialogue: 1,0:00:58.00,0:01:05.00,Tracker,,0,0,0,,PERCEIVE  →  PROPOSE  →  CHECK  →  EXECUTE  →  {\\c&H004FCC33}VERIFY
Dialogue: 1,0:00:14.00,0:00:16.10,Stage,,0,0,0,,{\\fad(180,180)}1 · PERCEIVE
Dialogue: 1,0:00:16.10,0:00:22.00,Badge,,0,0,0,,{\\fad(180,180)}{\\c&H00F8C845}4 TAGS LOCKED  ·  BOARD X/Y DRAWN
Dialogue: 1,0:00:22.00,0:00:24.00,Stage,,0,0,0,,{\\fad(180,180)}2 · PROPOSE
Dialogue: 1,0:00:24.00,0:00:30.00,Card,,0,0,0,,{\\fad(180,180)}{\\c&H004C9BFF}MODEL PROPOSAL{\\c&H00F3F6FA}\\Naction       press\\Ntarget       keyboard:H\\Nframe        board\\Nconfidence   0.97
Dialogue: 1,0:00:30.00,0:00:31.80,Stage,,0,0,0,,{\\fad(150,150)}3 · CHECK
Dialogue: 1,0:00:31.80,0:00:37.00,Card,,0,0,0,,{\\pos(92,230)\\fad(150,180)}{\\c&H00505AFF}GATE · REJECT{\\c&H00F3F6FA}\\Nframe        camera_raw  ✕\\Nfreshness    stale       ✕\\N\\NARM REMAINS STILL
Dialogue: 1,0:00:37.00,0:00:38.20,Card,,0,0,0,,{\\pos(92,230)\\fad(120,80)}{\\c&H004FCC33}GATE · ACCEPT{\\c&H00F3F6FA}\\Nunits        ✓
Dialogue: 1,0:00:38.20,0:00:39.30,Card,,0,0,0,,{\\pos(92,230)\\fad(80,80)}{\\c&H004FCC33}GATE · ACCEPT{\\c&H00F3F6FA}\\Nunits        ✓\\Nframe        ✓
Dialogue: 1,0:00:39.30,0:00:40.40,Card,,0,0,0,,{\\pos(92,230)\\fad(80,80)}{\\c&H004FCC33}GATE · ACCEPT{\\c&H00F3F6FA}\\Nunits        ✓\\Nframe        ✓\\Nreach        ✓
Dialogue: 1,0:00:40.40,0:00:41.50,Card,,0,0,0,,{\\pos(92,230)\\fad(80,80)}{\\c&H004FCC33}GATE · ACCEPT{\\c&H00F3F6FA}\\Nunits        ✓\\Nframe        ✓\\Nreach        ✓\\Nclearance    ✓
Dialogue: 1,0:00:41.50,0:00:44.00,Card,,0,0,0,,{\\pos(92,230)\\fad(80,180)}{\\c&H004FCC33}GATE · ACCEPT{\\c&H00F3F6FA}\\Nunits        ✓\\Nframe        ✓\\Nreach        ✓\\Nclearance    ✓\\Nfreshness    ✓
Dialogue: 1,0:00:44.00,0:00:51.00,RightCard,,0,0,0,,{\\fad(160,180)}{\\c&H00F8C845}RESOLVED TARGET · H{\\c&H00F3F6FA}\\NX  216.55 mm\\NY  154.00 mm\\NZ   48.00 mm\\Ncamera → board → keyboard → H
Dialogue: 1,0:00:51.00,0:00:58.00,Badge,,0,0,0,,{\\fad(140,160)}SIMULATED PRESS  ·  ACTION 1 OF 1  ·  CONTROLLER
Dialogue: 1,0:00:58.20,0:01:03.00,VerifyCard,,0,0,0,,{\\pos(420,540)\\fad(160,180)}TELEMETRY\\N\\NJOINT TARGET REACHED  {\\c&H004FCC33}✓
Dialogue: 1,0:00:59.00,0:01:03.00,VerifyCard,,0,0,0,,{\\pos(1500,540)\\fad(160,180)}HOST INPUT\\N\\NCHARACTER RECEIVED  {\\c&H004FCC33}✓
Dialogue: 2,0:01:03.00,0:01:05.00,CenterCard,,0,0,0,,{\\pos(960,390)\\fad(140,180)\\c&H004FCC33\\fs68}VERIFIED{\\rCenterCard}
Dialogue: 1,0:01:05.00,0:01:12.00,Hero,,0,0,0,,{\\fad(220,220)}ONE SHARED CONTRACT
Dialogue: 1,0:01:05.30,0:01:12.00,Sub,,0,0,0,,{\\fad(220,220)}FROM USER INTENT TO VERIFIED PHYSICAL ACTION
Dialogue: 2,0:01:05.20,0:01:06.30,Loop,,0,0,0,,{\\c&H00F8C845}PERCEIVE{\\c&H00D8DEE8}  →  PROPOSE  →  CHECK  →  EXECUTE  →  VERIFY
Dialogue: 2,0:01:06.30,0:01:07.40,Loop,,0,0,0,,{\\c&H004FCC33}PERCEIVE  →  PROPOSE{\\c&H00D8DEE8}  →  CHECK  →  EXECUTE  →  VERIFY
Dialogue: 2,0:01:07.40,0:01:08.50,Loop,,0,0,0,,{\\c&H004FCC33}PERCEIVE  →  PROPOSE  →  CHECK{\\c&H00D8DEE8}  →  EXECUTE  →  VERIFY
Dialogue: 2,0:01:08.50,0:01:09.60,Loop,,0,0,0,,{\\c&H004FCC33}PERCEIVE  →  PROPOSE  →  CHECK  →  EXECUTE{\\c&H00D8DEE8}  →  VERIFY
Dialogue: 2,0:01:09.60,0:01:12.00,Loop,,0,0,0,,{\\c&H004FCC33}PERCEIVE  →  PROPOSE  →  CHECK  →  EXECUTE  →  VERIFY  ↺
Dialogue: 0,0:01:12.00,0:01:17.00,Black,,0,0,0,,{\\p1}m 0 0 l 1920 0 l 1920 1080 l 0 1080{\\p0}
Dialogue: 1,0:01:12.00,0:01:17.00,EndTitle,,0,0,0,,{\\pos(960,400)\\fad(220,0)}TACTEVRA
Dialogue: 1,0:01:12.20,0:01:17.00,EndSub,,0,0,0,,{\\pos(960,545)}ONE REQUEST. ONE CHECKED PHYSICAL ACTION.
Dialogue: 1,0:01:12.40,0:01:17.00,EndURL,,0,0,0,,{\\pos(960,630)}github.com/j-webtek/tactevra
Dialogue: 1,0:01:12.00,0:01:17.00,EndFine,,0,0,0,,Concept visualization · hardware-shaped articulated rig · simulated key contact
""",
        encoding="utf-8",
    )


def write_caption_file(path: Path) -> None:
    """Write captions that match the narrated screenplay word for word."""
    path.write_text(
        """1
00:00:04,000 --> 00:00:06,800
When AI moves real hardware,
“usually right” isn't good enough.

2
00:00:06,800 --> 00:00:10,000
A wrong guess isn't a typo.
It's a motion.

3
00:00:10,000 --> 00:00:14,000
Tactevra turns one request into
one checked physical action.

4
00:00:14,000 --> 00:00:18,000
First, a fixed camera reads marker tags
on the board,

5
00:00:18,000 --> 00:00:22,000
so every target is measured
in one shared frame.

6
00:00:22,000 --> 00:00:24,500
Next, the model proposes an action,
a named target,

7
00:00:24,500 --> 00:00:27,500
a frame, and its confidence.

8
00:00:27,500 --> 00:00:30,000
Never raw motor commands.

9
00:00:30,000 --> 00:00:33,500
Then deterministic gates
check every proposal.

10
00:00:33,500 --> 00:00:37,000
A stale or malformed plan is rejected
before anything moves.

11
00:00:37,000 --> 00:00:40,500
Units. Frame. Reach.
Clearance. Freshness.

12
00:00:40,500 --> 00:00:44,000
Only a plan that passes every gate
is admitted.

13
00:00:44,000 --> 00:00:47,500
Measured geometry turns “the H key”
into exact millimeters,

14
00:00:47,500 --> 00:00:51,000
through the camera, board,
and device frames.

15
00:00:51,000 --> 00:00:58,000
One controller, and only one,
sends a single bounded motion.

16
00:00:58,000 --> 00:01:01,500
Telemetry and the camera
confirm the result

17
00:01:01,500 --> 00:01:05,000
before the next action is allowed.

18
00:01:05,000 --> 00:01:12,000
One shared contract, from user intent
to verified physical action.

19
00:01:12,000 --> 00:01:14,000
Tactevra.
""",
        encoding="utf-8",
        newline="\n",
    )


def write_webvtt_file(path: Path) -> None:
    """Write browser-native captions matching the SRT chapter transcript."""
    path.write_text(
        """WEBVTT

00:00:04.000 --> 00:00:06.800
When AI moves real hardware,
“usually right” isn't good enough.

00:00:06.800 --> 00:00:10.000
A wrong guess isn't a typo.
It's a motion.

00:00:10.000 --> 00:00:14.000
Tactevra turns one request into
one checked physical action.

00:00:14.000 --> 00:00:18.000
First, a fixed camera reads marker tags
on the board,

00:00:18.000 --> 00:00:22.000
so every target is measured
in one shared frame.

00:00:22.000 --> 00:00:24.500
Next, the model proposes an action,
a named target,

00:00:24.500 --> 00:00:27.500
a frame, and its confidence.

00:00:27.500 --> 00:00:30.000
Never raw motor commands.

00:00:30.000 --> 00:00:33.500
Then deterministic gates
check every proposal.

00:00:33.500 --> 00:00:37.000
A stale or malformed plan is rejected
before anything moves.

00:00:37.000 --> 00:00:40.500
Units. Frame. Reach.
Clearance. Freshness.

00:00:40.500 --> 00:00:44.000
Only a plan that passes every gate
is admitted.

00:00:44.000 --> 00:00:47.500
Measured geometry turns “the H key”
into exact millimeters,

00:00:47.500 --> 00:00:51.000
through the camera, board,
and device frames.

00:00:51.000 --> 00:00:58.000
One controller, and only one,
sends a single bounded motion.

00:00:58.000 --> 00:01:01.500
Telemetry and the camera
confirm the result

00:01:01.500 --> 00:01:05.000
before the next action is allowed.

00:01:05.000 --> 00:01:12.000
One shared contract, from user intent
to verified physical action.

00:01:12.000 --> 00:01:14.000
Tactevra.
""",
        encoding="utf-8",
        newline="\n",
    )


NARRATION_CUES = (
    (4.0, 10.0, "When AI moves real hardware,\na wrong guess becomes real motion."),
    (10.0, 14.0, "Tactevra turns one request into\none checked physical action."),
    (14.0, 22.0, "A fixed camera reads four board markers,\nplacing every target in one shared frame."),
    (22.0, 30.0, "The model proposes the action, named target,\ncoordinate frame, and confidence—never motor commands."),
    (30.0, 37.0, "Deterministic gates stop stale or malformed plans\nbefore the arm can move."),
    (37.0, 44.0, "Units. Frame. Reach. Clearance. Freshness.\nEvery gate must pass."),
    (44.0, 51.0, "Measured geometry resolves the H key\ninto exact board coordinates."),
    (51.0, 58.0, "The arm carries the stylus\nand sends one bounded press."),
    (58.0, 65.0, "Telemetry confirms the target, while the host\nconfirms the character H."),
    (65.0, 72.0, "That closes one shared contract, from intent\nto verified physical action."),
    (72.0, 77.0, "Tactevra.\nPhysical intelligence, checked."),
)


def _caption_time(seconds: float, decimal: str) -> str:
    whole = int(seconds)
    milliseconds = int(round((seconds - whole) * 1000))
    return f"{whole // 3600:02d}:{(whole % 3600) // 60:02d}:{whole % 60:02d}{decimal}{milliseconds:03d}"


def write_caption_file(path: Path) -> None:
    blocks = []
    for index, (start, end, text) in enumerate(NARRATION_CUES, start=1):
        blocks.append(
            f"{index}\n{_caption_time(start, ',')} --> {_caption_time(end, ',')}\n{text}"
        )
    path.write_text("\n\n".join(blocks) + "\n", encoding="utf-8", newline="\n")


def write_webvtt_file(path: Path) -> None:
    blocks = ["WEBVTT"]
    for start, end, text in NARRATION_CUES:
        blocks.append(
            f"{_caption_time(start, '.')} --> {_caption_time(end, '.')}\n{text}"
        )
    path.write_text("\n\n".join(blocks) + "\n", encoding="utf-8", newline="\n")


def write_chapters_file(path: Path) -> None:
    chapters = (
        (14.0, 22.0, "Perceive"),
        (22.0, 30.0, "Propose"),
        (30.0, 51.0, "Check"),
        (51.0, 58.0, "Execute"),
        (58.0, 65.0, "Verify"),
    )
    blocks = ["WEBVTT"]
    for start, end, label in chapters:
        blocks.append(
            f"{_caption_time(start, '.')} --> {_caption_time(end, '.')}\n{label}"
        )
    path.write_text("\n\n".join(blocks) + "\n", encoding="utf-8", newline="\n")


def write_soundtrack(path: Path) -> None:
    """Synthesize a restrained bed with one semantic sound per event."""
    sample_rate = 48_000
    duration = END_FRAME / FPS
    chord_roots = (55.0, 65.41, 73.42, 61.74)

    def soft_pulse(t: float, center: float, freq: float, length: float = 0.34) -> float:
        local = t - center
        if local < 0 or local > length:
            return 0.0
        env = math.sin(math.pi * local / length) ** 2
        return math.sin(2 * math.pi * freq * local) * env

    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        chunk = bytearray()
        for index in range(int(sample_rate * duration)):
            t = index / sample_rate
            # A restrained four-chord bed gives the film continuity without
            # becoming another attention layer beneath the narration.
            root = chord_roots[int(t // 16) % len(chord_roots)]
            breathe = 0.72 + 0.28 * math.sin(2 * math.pi * 0.0625 * t) ** 2
            bed = (
                0.025 * math.sin(2 * math.pi * root * t)
                + 0.016 * math.sin(2 * math.pi * root * 1.5 * t + 0.6)
                + 0.010 * math.sin(2 * math.pi * root * 2.0 * t + 1.2)
                + 0.004 * math.sin(2 * math.pi * root * 4.0 * t + 0.3)
            ) * breathe
            cue = 0.0
            # One semantic sound family per screenplay event.
            for key_tick in (0.55, 1.05, 1.55, 2.05):
                cue += 0.040 * soft_pulse(t, key_tick, 980.0, 0.08)
            cue += 0.045 * soft_pulse(t, 10.0, 420.0, 0.42)  # promise
            for tag_ping in (16.2, 17.1, 18.0, 18.9):
                cue += 0.055 * soft_pulse(t, tag_ping, 620.0, 0.16)
            cue += 0.095 * soft_pulse(t, 34.0, 150.0, 0.55)  # reject
            for index, gate_tick in enumerate((38.0, 39.0, 40.0, 41.0, 42.0)):
                cue += 0.060 * soft_pulse(t, gate_tick, 520.0 + index * 70.0, 0.16)
            cue += 0.110 * soft_pulse(t, 43.0, 860.0, 0.45)  # accept
            cue += 0.115 * soft_pulse(t, 54.2, 1180.0, 0.11)  # key contact
            cue += 0.070 * soft_pulse(t, 60.0, 720.0, 0.18)
            cue += 0.070 * soft_pulse(t, 62.0, 820.0, 0.18)
            for chord_tone in (523.25, 659.25, 783.99):
                cue += 0.045 * soft_pulse(t, 64.0, chord_tone, 0.62)  # verified chord
            for stage_index, stage_time in enumerate((65.4, 66.5, 67.6, 68.7, 69.8)):
                cue += 0.045 * soft_pulse(t, stage_time, 520 + stage_index * 65, 0.15)
            cue += 0.060 * soft_pulse(t, 75.5, 392.0, 0.62)  # clean end button
            sample = max(-0.92, min(0.92, bed + cue))
            pan = 0.04 * math.sin(2 * math.pi * 0.07 * t)
            left = int(sample * (1.0 - pan) * 32767)
            right = int(sample * (1.0 + pan) * 32767)
            chunk.extend(struct.pack("<hh", left, right))
            if len(chunk) >= 192_000:
                wav.writeframesraw(chunk)
                chunk.clear()
        if chunk:
            wav.writeframesraw(chunk)


def mux_soundtrack_and_variants(silent_video: Path, final_video: Path,
                                ffmpeg: str, external_voice_dir: Path | None = None) -> None:
    soundtrack = OUT / "tactevra_workcell_explainer_soundtrack_v3.wav"
    captions = OUT / "tactevra_workcell_explainer_captions_v3.srt"
    web_video = OUT / "tactevra_workcell_explainer_web_1080p_v3.mp4"
    distribution_video = OUT / "tactevra_workcell_explainer_distribution_1080p_v3.mp4"
    social_video = OUT / "tactevra_workcell_explainer_social_square_v3.mp4"
    voice_dir = external_voice_dir or (OUT / "voiceover_v3")
    write_soundtrack(soundtrack)
    write_caption_file(captions)
    if external_voice_dir is None:
        voice_script = SCRIPT.with_name("generate_voiceover.ps1")
        powershell = shutil.which("pwsh") or shutil.which("powershell")
        if not powershell:
            raise RuntimeError("PowerShell is required to synthesize the narrated master")
        subprocess.run(
            [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
             str(voice_script), "-OutputDirectory", str(voice_dir)],
            check=True,
        )
    voice_starts = (4, 10, 14, 22, 30, 37, 44, 51, 58, 65, 72)
    voice_ends = (10, 14, 22, 30, 37, 44, 51, 58, 65, 72, 77)
    voice_files = []
    for index in range(1, 12):
        candidates = [voice_dir / f"voice_{index:02d}{suffix}"
                      for suffix in (".wav", ".mp3", ".m4a")]
        selected = next((candidate for candidate in candidates if candidate.is_file()), None)
        if selected is None:
            raise FileNotFoundError(
                f"Missing voice_{index:02d}.wav/.mp3/.m4a in {voice_dir}"
            )
        voice_files.append(selected)
    inputs: list[str] = [ffmpeg, "-y", "-i", str(silent_video), "-i", str(soundtrack)]
    for voice_file in voice_files:
        inputs.extend(("-i", str(voice_file)))
    # The generated bed is intentionally restrained at source. A 0.17 gain
    # made it disappear between voice clips; 0.65 keeps it roughly 15–18 dB
    # below dialogue and makes reject/pass/contact/verified cues audible.
    audio_graph = ["[1:a]volume=0.65[bed]"]
    voice_labels = []
    for input_index, (start, end) in enumerate(zip(voice_starts, voice_ends), start=2):
        label = f"voice{input_index}"
        delay_ms = int(start * 1000)
        duration = end - start - 0.10
        fade_start = max(0.0, duration - 0.10)
        audio_graph.append(
            f"[{input_index}:a]aresample=48000,volume=1.0,"
            f"atrim=duration={duration:.3f},afade=t=out:st={fade_start:.3f}:d=0.10,"
            f"adelay={delay_ms}|{delay_ms}[{label}]"
        )
        voice_labels.append(f"[{label}]")
    audio_graph.append(
        "".join(voice_labels)
        + f"amix=inputs={len(voice_labels)}:duration=longest:normalize=0,"
        "apad=whole_dur=77,asplit=2[voice_sidechain][voices]"
    )
    audio_graph.append(
        "[bed][voice_sidechain]sidechaincompress=threshold=0.018:ratio=6:"
        "attack=18:release=320[ducked]"
    )
    audio_graph.append(
        "[ducked][voices]amix=inputs=2:duration=longest:normalize=0,"
        # Leave additional intersample headroom so the later compact AAC
        # transcode remains at or below -1 dBTP on the public delivery.
        "loudnorm=I=-14:TP=-2.0:LRA=7[mix]"
    )
    subprocess.run(
        inputs + ["-filter_complex", ";".join(audio_graph),
                  "-map", "0:v:0", "-map", "[mix]", "-c:v", "copy",
                  "-c:a", "aac", "-b:a", "256k", "-shortest",
                  "-movflags", "+faststart", str(final_video)],
        check=True,
    )
    subprocess.run(
        [
            ffmpeg, "-y", "-i", str(final_video),
            "-c:v", "libx264", "-preset", "slow", "-crf", "18",
            "-maxrate", "16M", "-bufsize", "24M",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            "-movflags", "+faststart",
            str(web_video),
        ],
        check=True,
    )
    # Separate high-quality upload master for LinkedIn and YouTube. The
    # checked-in homepage delivery remains compact; this derivative keeps fine
    # key legends and dark gradients at full 1080p and about 5 Mbps.
    subprocess.run(
        [
            ffmpeg, "-y", "-i", str(final_video),
            "-c:v", "libx264", "-preset", "slow", "-b:v", "5M",
            "-maxrate", "6M", "-bufsize", "12M", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            "-movflags", "+faststart", str(distribution_video),
        ],
        check=True,
    )
    subtitle_filter = str(captions).replace("\\", "/").replace(":", "\\:")
    subprocess.run(
        [ffmpeg, "-y", "-i", str(final_video),
         "-vf", f"crop=1080:1080:(iw-1080)/2:0,subtitles='{subtitle_filter}':force_style='FontName=Arial,FontSize=19,Outline=2,MarginV=54'",
         "-c:v", "libx264", "-preset", "medium", "-crf", "19",
         "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
         "-movflags", "+faststart",
         str(social_video)],
        check=True,
    )


def publish_homepage_media() -> None:
    """Publish the reviewed compact film, poster, and selectable captions."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required to publish homepage media")
    source = OUT / "tactevra_workcell_explainer_web_1080p_v3.mp4"
    if not source.is_file():
        raise FileNotFoundError(
            f"Homepage publishing requires the reviewed web render: {source}"
        )
    PUBLIC_MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    captions = PUBLIC_MEDIA_DIR / "tactevra-overview.en.vtt"
    chapters = PUBLIC_MEDIA_DIR / "tactevra-overview.chapters.vtt"
    public_video = PUBLIC_MEDIA_DIR / "tactevra-overview.mp4"
    poster = PUBLIC_MEDIA_DIR / "tactevra-overview-poster.jpg"
    social_preview = PUBLIC_MEDIA_DIR / "tactevra-social-preview.jpg"

    def render_story_poster(output: Path, width: int, height: int) -> None:
        """Render a share image that communicates rejection and verification.

        A lone robot beauty frame did not explain the product in a social feed.
        Pairing the real film's REJECT beat with its verified host result turns
        the thumbnail into a compact before/after story.
        """
        half = width // 2
        source_width = 1920
        source_height = 1080
        crop_width = round(source_height * half / height)
        verify_crop_x = (source_width - crop_width) // 2
        headline_band = int(height * 0.24)
        headline_size = max(40, int(width * 0.043))
        subhead_size = max(22, int(width * 0.020))
        font_path = Path("C:/Windows/Fonts/arialbd.ttf")
        font_filter = str(font_path).replace("\\", "/").replace(":", "\\:")
        graph = (
            # Bias the rejection crop toward the left-side decision card while
            # keeping the verification crop centered on the host result.
            f"[0:v]crop={crop_width}:{source_height}:0:0,"
            f"scale={half}:{height}[reject];"
            f"[1:v]crop={crop_width}:{source_height}:{verify_crop_x}:0,"
            f"scale={half}:{height}[verify];"
            f"[reject][verify]hstack=inputs=2[split];"
            f"[split]drawbox=x=0:y=0:w=iw:h={headline_band}:"
            "color=0x05080d@0.90:t=fill,"
            f"drawtext=fontfile='{font_filter}':"
            "text='PHYSICAL INTELLIGENCE, CHECKED.':"
            f"fontcolor=white:fontsize={headline_size}:"
            "x=(w-text_w)/2:y=30,"
            f"drawtext=fontfile='{font_filter}':"
            "text='A bad plan stops. A verified result moves forward.':"
            f"fontcolor=0x84d9ff:fontsize={subhead_size}:"
            f"x=(w-text_w)/2:y={int(headline_band * 0.62)}[story]"
        )
        subprocess.run(
            [
                ffmpeg, "-y", "-ss", "33.5", "-i", str(source),
                "-ss", "61.5", "-i", str(source),
                "-filter_complex", graph, "-map", "[story]",
                "-frames:v", "1", "-update", "1", "-q:v", "2",
                str(output),
            ],
            check=True,
        )
    write_webvtt_file(captions)
    write_chapters_file(chapters)
    subprocess.run(
        [
            ffmpeg, "-y", "-i", str(source), "-i", str(captions),
            "-map", "0:v:0", "-map", "0:a:0", "-map", "1:0",
            # Keep the repository delivery below the ordinary 10 MiB review
            # ceiling even when a detailed vendor surface raises scene entropy.
            # The higher-bitrate 1080p master remains available in ignored tmp/.
            "-vf", "scale=1600:-2", "-c:v", "libx264", "-preset", "slow",
            "-crf", "24", "-maxrate", "1800k", "-bufsize", "3600k",
            "-c:a", "aac", "-b:a", "128k", "-ar", "48000",
            "-c:s", "mov_text",
            "-metadata:s:s:0", "language=eng",
            "-metadata:s:s:0", "title=English",
            "-disposition:s:0", "0", "-movflags", "+faststart",
            str(public_video),
        ],
        check=True,
    )
    render_story_poster(social_preview, 1200, 630)
    render_story_poster(poster, 1280, 720)


def composite_overlay(clean_video: Path, final_video: Path,
                      external_voice_dir: Path | None = None) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required to composite informational labels")
    ass_path = OUT / "tactevra_workcell_explainer_v3.ass"
    write_ass_overlay(ass_path)
    # libass filter paths require a forward-slash Windows path with an escaped
    # drive colon. subprocess avoids shell interpolation of the filter itself.
    ass_filter_path = str(ass_path).replace("\\", "/").replace(":", "\\:")
    # Overlap 100 ms on each side of every camera cut and use a true 200 ms
    # cross-dissolve. Segment overlap preserves the source pixels; sequential
    # fade filters would destructively blacken the already-filtered stream.
    # Information graphics are composited last so chapter titles remain stable.
    camera_cuts = (4.0, 10.0, 14.0, 22.0, 30.0, 37.0, 44.0,
                   51.0, 58.0, 65.0, 72.0)
    overlap = 0.10
    dissolve = overlap * 2
    source_duration = END_FRAME / FPS
    starts = [0.0, *[cut - overlap for cut in camera_cuts]]
    ends = [*[cut + overlap for cut in camera_cuts], source_duration]
    graph: list[str] = []
    for index, (start, end) in enumerate(zip(starts, ends)):
        graph.append(
            f"[0:v]trim=start={start:.3f}:end={end:.3f},"
            f"setpts=PTS-STARTPTS,fps={FPS},settb=AVTB,format=yuv420p[segment{index}]"
        )
    previous = "segment0"
    for index, cut in enumerate(camera_cuts, start=1):
        output = f"transition{index}"
        graph.append(
            f"[{previous}][segment{index}]xfade=transition=fade:"
            f"duration={dissolve:.3f}:offset={cut - overlap:.3f}[{output}]"
        )
        previous = output
    graph.append(f"[{previous}]ass='{ass_filter_path}'[finished]")
    silent_video = OUT / "tactevra_workcell_explainer_silent_v3.mp4"
    subprocess.run(
        [
            ffmpeg, "-y", "-i", str(clean_video),
            "-filter_complex", ";".join(graph), "-map", "[finished]",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            str(silent_video),
        ],
        check=True,
    )
    mux_soundtrack_and_variants(silent_video, final_video, ffmpeg, external_voice_dir)


def main() -> None:
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    voice_dir = None
    if "--voiceover-dir" in args:
        value_index = args.index("--voiceover-dir") + 1
        if value_index >= len(args):
            raise ValueError("--voiceover-dir requires a directory path")
        voice_dir = Path(args[value_index]).resolve()
    if "--publish-homepage-media" in args:
        publish_homepage_media()
        print(f"TACTEVRA_PUBLIC_MEDIA={PUBLIC_MEDIA_DIR}")
        return
    if "--overlay-only" in args:
        clean_video = OUT / "tactevra_workcell_explainer_clean_v3.mp4"
        final_video = OUT / "tactevra_workcell_explainer_v3.mp4"
        if not clean_video.exists():
            raise FileNotFoundError(
                f"Overlay-only mode requires an existing clean render: {clean_video}"
            )
        composite_overlay(clean_video, final_video, voice_dir)
        print(f"TACTEVRA_OUTPUT={OUT}")
        return

    scene = build()
    blend_path = OUT / "tactevra_workcell_explainer_v3.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))

    if "--preview-shots" in args:
        preview_frames = (48, 168, 288, 384, 468, 624, 804, 972,
                          1140, 1300, 1476, 1644, 1788)
        scene.render.resolution_percentage = 55
        for frame in preview_frames:
            scene.frame_set(frame)
            scene.render.image_settings.file_format = "PNG"
            scene.render.filepath = str(OUT / f"preview_{frame:04d}.png")
            bpy.ops.render.render(write_still=True)
    elif "--render-video" in args:
        scene.render.image_settings.file_format = "FFMPEG"
        scene.render.ffmpeg.format = "MPEG4"
        scene.render.ffmpeg.codec = "H264"
        clean_video = OUT / "tactevra_workcell_explainer_clean_v3.mp4"
        final_video = OUT / "tactevra_workcell_explainer_v3.mp4"
        # Blender treats render.filepath as a stem when animation numbering is
        # enabled. Disable extension synthesis and use the complete filename.
        scene.render.use_file_extension = False
        scene.render.filepath = str(clean_video)
        scene.frame_start = 1
        scene.frame_end = END_FRAME
        bpy.ops.render.render(animation=True)
        composite_overlay(clean_video, final_video, voice_dir)
    else:
        scene.frame_set(52)
        scene.render.image_settings.file_format = "PNG"
        scene.render.filepath = str(OUT / "tactevra_workcell_explainer_poster_v3.png")
        bpy.ops.render.render(write_still=True)

    print(f"TACTEVRA_OUTPUT={OUT}")


if __name__ == "__main__":
    main()

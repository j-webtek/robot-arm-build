"""Build and optionally render the Tactevra RC03 Blender explainer.

Blender 4.3+ usage:
  blender --background --factory-startup \
    --python presentations/blender/build_workcell_explainer.py
  blender --background --factory-startup \
    --python presentations/blender/build_workcell_explainer.py -- --render-video
  blender --background --factory-startup \
    --python presentations/blender/build_workcell_explainer.py -- --overlay-only

Generated outputs are intentionally written below /tmp and are not source
artifacts. Source CAD and measured layout data remain authoritative.
"""

from __future__ import annotations

import json
import hashlib
import math
import shutil
import subprocess
import sys
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

FPS = 24
END_FRAME = 18 * FPS
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


def visibility(obj: bpy.types.Object, start: int, end: int, scale: float = 1.0) -> None:
    obj.scale = (0, 0, 0)
    obj.keyframe_insert("scale", frame=max(1, start - 8))
    obj.scale = (scale, scale, scale)
    obj.keyframe_insert("scale", frame=start)
    obj.keyframe_insert("scale", frame=end)
    obj.scale = (0, 0, 0)
    obj.keyframe_insert("scale", frame=min(END_FRAME, end + 8))


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
            black: bpy.types.Material) -> None:
    base = cube(f"Tag {tag_id}", board_point(x, y, 0.8),
                (0.055, 0.055, 0.0015), white, 0.001)
    # An original high-contrast visual motif, not a claimed AprilTag code.
    for ix, iy in ((-1, -1), (1, -1), (-1, 1), (1, 1), (0, 0)):
        cell = cube(f"Tag {tag_id} cell", board_point(x + ix * 13, y + iy * 13, 1.7),
                    (0.010, 0.010, 0.001), black)
        cell.parent = base


def add_keyboard(layout: dict, mats: dict[str, bpy.types.Material]) -> None:
    dev = layout["devices"]["keyboard"]
    ox, oy = dev["nominal_origin_xy"]
    sx, sy, sz = dev["nominal_size"]
    # Repository station meshes are designed artifacts and placed by RC03 origins.
    import_stl(STL_DIR / "keyboard_station_left.stl", "Designed keyboard station L",
               mats["abs"], (80.0, 72.0, 0.0))
    import_stl(STL_DIR / "keyboard_station_right.stl", "Designed keyboard station R",
               mats["abs"], (242.5, 72.0, 0.0))
    cube("Measured keyboard chassis", board_point(ox + sx / 2, oy + sy / 2, sz / 2),
         (sx / 1000, sy / 1000, sz / 1000), mats["keyboard"], 0.006)
    rows = [14, 14, 13, 12, 10]
    labels = [
        list("1234567890-=") + ["BS", "DEL"],
        list("QWERTYUIOP[]") + ["\\", "PG"],
        list("ASDFGHJKL;' ") + ["ENT"],
        list("ZXCVBNM,./") + ["SHIFT", "UP"],
        ["CTRL", "ALT", "SPACE", "SPACE", "SPACE", "SPACE", "FN", "LEFT", "DOWN", "RIGHT"],
    ]
    top = oy + sy - 18
    usable_x = sx - 22
    for row_i, count in enumerate(rows):
        pitch = usable_x / count
        y = top - row_i * 27
        for col in range(count):
            x = ox + 11 + pitch * (col + 0.5)
            key = cube(f"Key {row_i}-{col}", board_point(x, y, sz + 2.4),
                       (pitch * 0.82 / 1000, 0.021, 0.005), mats["key"], 0.002)
            if row_i < len(labels) and col < len(labels[row_i]):
                key["legend"] = labels[row_i][col]


def add_phone(layout: dict, mats: dict[str, bpy.types.Material]) -> None:
    dev = layout["devices"]["phone"]
    ox, oy = dev["nominal_origin_xy"]
    sx, sy, sz = dev["configured_size"]
    import_stl(STL_DIR / "phone_tcp_station.stl", "Designed phone station",
               mats["abs"], (411.0, 80.0, 0.0))
    phone = cube("Measured phone envelope",
                 board_point(ox + sx / 2, oy + sy / 2, dev["support_plane_z"] + sz / 2),
                 (sx / 1000, sy / 1000, sz / 1000), mats["phone"], 0.006)
    cube("Phone screen", board_point(ox + sx / 2, oy + sy / 2,
                                     dev["nominal_screen_plane_z"] + 0.4),
         ((sx - 5) / 1000, (sy - 8) / 1000, 0.0008), mats["screen"], 0.004).parent = phone


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


def add_robot(mats: dict[str, bpy.types.Material]) -> dict[str, bpy.types.Object]:
    """Build an exact URDF-frame arm with explicitly proxy surface geometry."""
    manifest, joints = _parse_arm_contract()
    root = _empty("RoArm Wv — nominal board transform")
    tx, ty, tz = manifest["arm"]["nominal_board_T_robot_world_translation"]
    root.location = board_point(tx, ty, tz)
    root.rotation_euler[2] = math.radians(manifest["arm"]["nominal_board_T_robot_world_yaw_deg"])
    root["geometry_status"] = manifest["arm"]["surface_geometry"]["status"]
    root["kinematic_authority_sha256"] = manifest["arm"]["kinematic_authority_sha256"]

    world_base = _empty("world_to_base_link exact", root)
    world_base.location = joints["world_to_base_link"]["xyz"]
    base_fixed, q_base = _fixed_then_rotating("base", world_base, joints["base_link_to_link1"])
    shoulder_fixed, q_shoulder = _fixed_then_rotating("shoulder", q_base, joints["link1_to_link2"])
    elbow_fixed, q_elbow = _fixed_then_rotating("elbow", q_shoulder, joints["link2_to_link3"])
    wrist_fixed, q_wrist = _fixed_then_rotating("wrist pitch", q_elbow, joints["link3_to_link4"])
    roll_fixed, q_roll = _fixed_then_rotating("wrist roll", q_wrist, joints["link4_to_link5"])
    gripper_fixed, q_gripper = _fixed_then_rotating("gripper", q_roll, joints["link5_to_gripper_link"])
    tcp = _empty("hand_tcp exact", q_roll)
    tcp.location = joints["link5_to_hand_tcp"]["xyz"]
    tcp.rotation_euler = joints["link5_to_hand_tcp"]["rpy"]

    # The surfaces below are original visual proxies. Every centerline endpoint
    # is driven by the exact pinned URDF origin rather than hand-tuned lengths.
    base = cube("Arm base visual proxy", (0, 0, 0), (0.105, 0.105, 0.070), mats["servo"], 0.007)
    base.parent = root
    base.location = (0, 0, 0.035)
    _joint_marker("Base joint frame", base_fixed, mats["metal"], 0.040)
    _beam_to("URDF link1 centerline", q_base, joints["link1_to_link2"]["xyz"], mats["carbon"], 0.038)
    _joint_marker("Shoulder joint frame", shoulder_fixed, mats["servo"], 0.034)
    _beam_to("URDF link2 centerline", q_shoulder, joints["link2_to_link3"]["xyz"], mats["carbon"], 0.036)
    _joint_marker("Elbow joint frame", elbow_fixed, mats["servo"], 0.032)
    _beam_to("URDF link3 centerline", q_elbow, joints["link3_to_link4"]["xyz"], mats["carbon"], 0.034)
    _joint_marker("Wrist-pitch joint frame", wrist_fixed, mats["servo"], 0.029)
    _beam_to("URDF link4 centerline", q_wrist, joints["link4_to_link5"]["xyz"], mats["carbon"], 0.030)
    _joint_marker("Wrist-roll joint frame", roll_fixed, mats["metal"], 0.025)
    _beam_to("URDF TCP centerline", q_roll, joints["link5_to_hand_tcp"]["xyz"], mats["carbon"], 0.026)
    _joint_marker("Gripper joint frame", gripper_fixed, mats["servo"], 0.022)
    palm = cube("Gripper visual proxy", (0, 0, 0), (0.050, 0.032, 0.050), mats["abs"], 0.004)
    palm.parent = tcp
    palm.location = (0, 0, 0)
    for x in (-0.018, 0.018):
        finger = cube("Gripper finger visual proxy", (0, 0, 0), (0.008, 0.014, 0.062), mats["metal"], 0.002)
        finger.parent = tcp
        finger.location = (x, 0, -0.050)

    # All animated values remain inside the provisional simulation intersection.
    # They demonstrate data flow only; they are not executable hardware plans.
    poses = {
        1: (0.0, 0.0, 2.618, -1.0472, 0.0),
        270: (0.0, 0.0, 2.618, -1.0472, 0.0),
        320: (-0.42, 0.18, 2.35, -1.12, 0.12),
        362: (0.48, 0.12, 2.42, -1.00, -0.10),
        406: (0.0, 0.0, 2.618, -1.0472, 0.0),
        END_FRAME: (0.0, 0.0, 2.618, -1.0472, 0.0),
    }
    animated = (q_base, q_shoulder, q_elbow, q_wrist, q_roll)
    for frame, values in poses.items():
        for joint_obj, value in zip(animated, values):
            joint_obj.rotation_euler = (0, 0, value)
            joint_obj.keyframe_insert("rotation_euler", frame=frame)
    q_gripper.rotation_euler = (0, 0, 0.35)
    return {"root": root, "base": q_base, "shoulder": q_shoulder,
            "elbow": q_elbow, "wrist": q_wrist, "roll": q_roll,
            "gripper": q_gripper, "tcp": tcp}


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
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 720
    scene.render.resolution_percentage = 100
    scene.render.fps = FPS
    scene.frame_start = 1
    scene.frame_end = END_FRAME
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "MEDIUM"
    scene.render.ffmpeg.ffmpeg_preset = "GOOD"
    scene.render.use_file_extension = True
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.view_settings.exposure = -0.9
    scene.world.color = (0.012, 0.016, 0.023)


def build() -> bpy.types.Scene:
    clean_scene()
    layout = json.loads(LAYOUT_PATH.read_text(encoding="utf-8"))
    scene = bpy.context.scene
    setup_render(scene)

    mats = {
        "abs": material("Printed matte black ABS", (0.012, 0.016, 0.021, 1), roughness=0.34),
        "carbon": material("Carbon link", (0.018, 0.023, 0.028, 1), metallic=0.2, roughness=0.24),
        "servo": material("Black servo", (0.025, 0.032, 0.040, 1), metallic=0.35, roughness=0.27),
        "metal": material("Machined metal", (0.22, 0.28, 0.34, 1), metallic=0.85, roughness=0.20),
        "wood": material("Light birch", (0.55, 0.33, 0.16, 1), roughness=0.48),
        "keyboard": material("Keyboard body", (0.022, 0.027, 0.034, 1), roughness=0.28),
        "key": material("Keyboard keys", (0.055, 0.065, 0.078, 1), roughness=0.34),
        "phone": material("Phone edge", (0.03, 0.04, 0.05, 1), metallic=0.6, roughness=0.20),
        "screen": material("Phone screen", (0.008, 0.028, 0.045, 1), metallic=0.15, roughness=0.12,
                           emission=(0.00, 0.25, 0.55, 1), emission_strength=0.6),
        "white": material("Reference white", (0.92, 0.95, 0.98, 1), roughness=0.55),
        "cyan": material("Tactevra cyan", (0.00, 0.52, 0.92, 1), roughness=0.22,
                         emission=(0.00, 0.52, 0.92, 1), emission_strength=3.5),
        "amber": material("Validation amber", (1.00, 0.36, 0.04, 1), roughness=0.24,
                          emission=(1.00, 0.22, 0.01, 1), emission_strength=2.8),
        "green": material("Verified green", (0.05, 0.80, 0.38, 1), roughness=0.20,
                          emission=(0.02, 0.80, 0.28, 1), emission_strength=3.2),
    }

    # Designed portal geometry is already expressed in board frame millimetres.
    import_stl(PORTAL_PATH, "DESIGNED — printable camera portal", mats["abs"])
    cube("MEASURED — 610 × 457 × 18 mm board", (0, 0, -0.009),
         (0.610, 0.457, 0.018), mats["wood"], 0.006)
    cube("Bench", (0, -0.01, -0.050), (1.15, 0.88, 0.065),
         material("Bench", (0.055, 0.066, 0.080, 1), metallic=0.15, roughness=0.52), 0.012)
    add_keyboard(layout, mats)
    add_phone(layout, mats)
    for tag_id, tag in layout["direct_tags"]["tags"].items():
        add_tag(tag_id, *tag["detection_center_xy"], mats["white"], mats["abs"])
    add_robot(mats)

    # Camera body at the nominal carriage axis and optical target.
    cam_center = board_point(305, 228.5, 1034)
    cube("Designed camera cage", cam_center, (0.055, 0.055, 0.045), mats["abs"], 0.004)
    lens = cylinder("Machine vision lens", cam_center + Vector((0, 0, -0.042)),
                    0.019, 0.045, mats["metal"])
    lens.rotation_euler = (0, 0, 0)

    # Render camera and cinematic movement.
    bpy.ops.object.camera_add(location=(1.90, -2.10, 0.96))
    camera = bpy.context.object
    camera.name = "Explainer camera"
    camera.data.lens = 48
    camera.data.sensor_width = 36
    scene.camera = camera
    camera_positions = [
        (1, Vector((1.90, -2.10, 0.96))),
        (96, Vector((1.25, -1.55, 1.02))),
        (192, Vector((0.0, -0.72, 1.58))),
        (288, Vector((0.76, -0.98, 0.68))),
        (384, Vector((0.96, -1.22, 0.72))),
        (END_FRAME, Vector((1.62, -1.84, 0.96))),
    ]
    targets = [
        (1, Vector((0, 0, 0.48))),
        (96, Vector((0, 0.02, 0.55))),
        (192, Vector((0, 0, 0.15))),
        (288, Vector((0, -0.04, 0.20))),
        (384, Vector((0, -0.04, 0.20))),
        (END_FRAME, Vector((0, 0.02, 0.43))),
    ]
    animate_transform(camera, camera_positions, targets)

    # Studio illumination.
    bpy.ops.object.light_add(type="AREA", location=(0.0, -0.18, 1.55))
    key = bpy.context.object
    key.name = "Overhead softbox"
    key.data.energy = 260
    key.data.shape = "DISK"
    key.data.size = 1.2
    key.rotation_euler = (0, 0, 0)
    bpy.ops.object.light_add(type="AREA", location=(0.78, -0.52, 0.65))
    fill = bpy.context.object
    fill.data.energy = 140
    fill.data.color = (0.68, 0.82, 1.0)
    fill.data.size = 0.75
    look_at(fill, Vector((0, 0, 0.3)))
    bpy.ops.object.light_add(type="AREA", location=(-0.62, 0.34, 0.82))
    rim = bpy.context.object
    rim.data.energy = 190
    rim.data.color = (1.0, 0.38, 0.18)
    rim.data.size = 0.55
    look_at(rim, Vector((0, 0.04, 0.38)))

    # Shot labels. They are camera-facing 3D graphics, not post-production text.
    hero = text_object("Hero title", "TACTEVRA\nPHYSICAL INTELLIGENCE, CHECKED",
                       Vector((0.0, -0.23, 0.68)), 0.034, mats["white"], camera)
    visibility(hero, 1, 88)
    evidence = text_object("Evidence label",
                           "REAL RC03 CAD  •  MEASURED DEVICE ENVELOPES  •  EXACT URDF FRAMES / PROXY SURFACES",
                           Vector((0.0, -0.18, 0.59)), 0.010, mats["cyan"], camera)
    visibility(evidence, 10, 90)

    vision = text_object("Vision label", "STATIC VISION\n1000 mm NOMINAL OPTICAL TARGET",
                         Vector((0.0, 0.07, 1.14)), 0.035, mats["white"], camera)
    visibility(vision, 100, 185)
    sight = curve_line("Vision ray",
                       [board_point(305, 228.5, 995), board_point(305, 228.5, 14)], mats["cyan"], 0.002)
    visibility(sight, 110, 188)

    devices = text_object("Device label", "INDEXED DEVICE GEOMETRY\nKEYBOARD + PHONE + DIRECT TAGS",
                          Vector((0.02, -0.14, 0.29)), 0.031, mats["white"], camera)
    visibility(devices, 196, 278)
    add_target_ring("Keyboard target H", 216.55, 154.0, 29, mats["cyan"], 212, 255)
    add_target_ring("Keyboard target I", 278.0, 188.0, 29, mats["amber"], 230, 270)
    add_target_ring("Phone target", 538.15, 166.4, 20, mats["green"], 242, 278)

    checked = text_object("Motion label", "PROPOSE → VALIDATE → EXECUTE → VERIFY",
                          Vector((0.0, -0.15, 0.48)), 0.030, mats["white"], camera)
    visibility(checked, 288, 386)
    route = curve_line("Checked route",
                       [board_point(305, 410, 260), board_point(235, 180, 115),
                        board_point(216.55, 154, 48), board_point(390, 185, 105),
                        board_point(538.15, 166.4, 42)], mats["amber"], 0.003)
    visibility(route, 300, 378)

    close = text_object("Closing title", "ONE SHARED CONTRACT\nFROM USER INTENT TO VERIFIED ACTION",
                        Vector((0.0, -0.21, 0.80)), 0.043, mats["white"], camera)
    visibility(close, 390, END_FRAME)
    disclaimer = text_object("Disclaimer",
                             "CONCEPT VISUALIZATION • RC03 NOMINAL GEOMETRY • NOT MOTION OR FABRICATION QUALIFICATION",
                             Vector((0.0, -0.20, 0.68)), 0.014, mats["amber"], camera)
    visibility(disclaimer, 394, END_FRAME)

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
        "arm frames are pinned URDF geometry; arm surfaces and motion are conceptual."
    )
    scene["source_layout"] = str(LAYOUT_PATH.relative_to(ROOT))
    scene["source_portal"] = str(PORTAL_PATH.relative_to(ROOT))
    return scene


def write_ass_overlay(path: Path) -> None:
    """Write screen-space information graphics for the rendered film."""
    path.write_text(
        """[Script Info]
ScriptType: v4.00+
PlayResX: 1280
PlayResY: 720
WrapStyle: 2

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Hero,Arial,47,&H00FFFFFF,&H000000FF,&H80081119,&H70000000,-1,0,0,0,100,100,0,0,1,2,1,8,70,70,48,1
Style: Sub,Arial,22,&H00F6F8FA,&H000000FF,&H90081119,&H70000000,-1,0,0,0,100,100,0,0,1,2,1,8,80,80,54,1
Style: Cyan,Arial,18,&H00F8C845,&H000000FF,&H90081119,&H70000000,-1,0,0,0,100,100,0,0,1,2,1,2,70,70,42,1
Style: Warn,Arial,15,&H004C9BFF,&H000000FF,&H90081119,&H70000000,-1,0,0,0,100,100,0,0,1,2,1,2,55,55,34,1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
Dialogue: 0,0:00:00.20,0:00:03.75,Hero,,0,0,0,,{\\fad(300,300)}TACTEVRA\\NPHYSICAL INTELLIGENCE, CHECKED
Dialogue: 0,0:00:00.55,0:00:03.75,Cyan,,0,0,0,,{\\fad(300,300)}REAL RC03 CAD  •  MEASURED DEVICE ENVELOPES  •  EXACT URDF FRAMES / PROXY SURFACES
Dialogue: 0,0:00:04.00,0:00:07.75,Hero,,0,0,0,,{\\fad(250,250)}STATIC VISION
Dialogue: 0,0:00:04.25,0:00:07.75,Cyan,,0,0,0,,{\\fad(250,250)}1000 mm NOMINAL OPTICAL TARGET  •  FIXED BOARD FRAME
Dialogue: 0,0:00:08.00,0:00:11.75,Hero,,0,0,0,,{\\fad(250,250)}INDEXED DEVICE GEOMETRY
Dialogue: 0,0:00:08.25,0:00:11.75,Cyan,,0,0,0,,{\\fad(250,250)}KEYBOARD  •  PHONE  •  DIRECT REFERENCE TAGS
Dialogue: 0,0:00:12.00,0:00:15.75,Hero,,0,0,0,,{\\fad(250,250)}PROPOSE → VALIDATE → EXECUTE → VERIFY
Dialogue: 0,0:00:12.25,0:00:15.75,Cyan,,0,0,0,,{\\fad(250,250)}BOUNDED TARGETS  •  CHECKED ROUTES  •  OBSERVED RESULTS
Dialogue: 0,0:00:16.00,0:00:17.95,Hero,,0,0,0,,{\\fad(250,200)}ONE SHARED CONTRACT
Dialogue: 0,0:00:16.20,0:00:17.95,Sub,,0,0,0,,{\\fad(250,200)}FROM USER INTENT TO VERIFIED PHYSICAL ACTION
Dialogue: 0,0:00:16.05,0:00:17.95,Warn,,0,0,0,,{\\fad(250,200)}CONCEPT VISUALIZATION • RC03 NOMINAL GEOMETRY • NOT MOTION OR FABRICATION QUALIFICATION
""",
        encoding="utf-8",
    )


def composite_overlay(clean_video: Path, final_video: Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required to composite informational labels")
    ass_path = OUT / "tactevra_workcell_explainer_v1.ass"
    write_ass_overlay(ass_path)
    # libass filter paths require a forward-slash Windows path with an escaped
    # drive colon. subprocess avoids shell interpolation of the filter itself.
    ass_filter_path = str(ass_path).replace("\\", "/").replace(":", "\\:")
    subprocess.run(
        [
            ffmpeg, "-y", "-i", str(clean_video),
            "-vf", f"ass='{ass_filter_path}'",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            str(final_video),
        ],
        check=True,
    )


def main() -> None:
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if "--overlay-only" in args:
        clean_video = OUT / "tactevra_workcell_explainer_clean_v1.mp4"
        final_video = OUT / "tactevra_workcell_explainer_v1.mp4"
        if not clean_video.exists():
            raise FileNotFoundError(
                f"Overlay-only mode requires an existing clean render: {clean_video}"
            )
        composite_overlay(clean_video, final_video)
        print(f"TACTEVRA_OUTPUT={OUT}")
        return

    scene = build()
    blend_path = OUT / "tactevra_workcell_explainer_v1.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))

    if "--render-video" in args:
        scene.render.image_settings.file_format = "FFMPEG"
        scene.render.ffmpeg.format = "MPEG4"
        scene.render.ffmpeg.codec = "H264"
        clean_video = OUT / "tactevra_workcell_explainer_clean_v1.mp4"
        final_video = OUT / "tactevra_workcell_explainer_v1.mp4"
        # Blender treats render.filepath as a stem when animation numbering is
        # enabled. Disable extension synthesis and use the complete filename.
        scene.render.use_file_extension = False
        scene.render.filepath = str(clean_video)
        scene.frame_start = 1
        scene.frame_end = END_FRAME
        bpy.ops.render.render(animation=True)
        composite_overlay(clean_video, final_video)
    else:
        scene.frame_set(52)
        scene.render.image_settings.file_format = "PNG"
        scene.render.filepath = str(OUT / "tactevra_workcell_explainer_poster_v1.png")
        bpy.ops.render.render(write_still=True)

    print(f"TACTEVRA_OUTPUT={OUT}")


if __name__ == "__main__":
    main()

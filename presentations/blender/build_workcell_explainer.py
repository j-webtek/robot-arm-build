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
import random
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
# V2 follows the narrated 12-beat screenplay: 77 seconds at 24 fps.
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
            black: bpy.types.Material) -> None:
    base = cube(f"Tag {tag_id}", board_point(x, y, 0.8),
                (0.055, 0.055, 0.0015), white, 0.001)
    # An original high-contrast visual motif, not a claimed AprilTag code.
    for ix, iy in ((-1, -1), (1, -1), (-1, 1), (1, 1), (0, 0)):
        cell = cube(f"Tag {tag_id} cell", board_point(x + ix * 13, y + iy * 13, 1.7),
                    (0.010, 0.010, 0.001), black)
        cell.parent = base


def add_keyboard(layout: dict, mats: dict[str, bpy.types.Material]) -> dict[str, bpy.types.Object]:
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
    named_keys: dict[str, bpy.types.Object] = {}
    for row_i, count in enumerate(rows):
        pitch = usable_x / count
        y = top - row_i * 27
        for col in range(count):
            x = ox + 11 + pitch * (col + 0.5)
            key = cube(f"Key {row_i}-{col}", board_point(x, y, sz + 2.4),
                       (pitch * 0.82 / 1000, 0.021, 0.005), mats["key"], 0.002)
            if row_i < len(labels) and col < len(labels[row_i]):
                key["legend"] = labels[row_i][col]
                named_keys.setdefault(labels[row_i][col], key)
    return named_keys


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
    return {"root": arm}


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
        "arm_exact": material("Official RoArm assembly finish", (0.017, 0.022, 0.028, 1),
                              metallic=0.48, roughness=0.24),
        "wood": textured_material("Light birch", (0.55, 0.33, 0.16, 1),
                                    scale=7.0, detail=3.0, roughness=0.48),
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
         textured_material("Bench", (0.055, 0.066, 0.080, 1), scale=5.0,
                           detail=2.0, metallic=0.15, roughness=0.52), 0.012)
    keyboard_keys = add_keyboard(layout, mats)
    add_phone(layout, mats)
    for tag_id, tag in layout["direct_tags"]["tags"].items():
        add_tag(tag_id, *tag["detection_center_xy"], mats["white"], mats["abs"])
    add_robot(mats)

    # The exact vendor assembly remains static because it is a single reference
    # surface. A restrained presentation stylus and the H key communicate the
    # admitted contact at the end effector without claiming kinematic evidence.
    h_key = keyboard_keys["H"]
    h_key_z = h_key.location.z
    for frame, offset in ((1225, 0.0), (1288, 0.0), (1300, -0.004),
                          (1320, -0.004), (1332, 0.0), (1392, 0.0)):
        h_key.location.z = h_key_z + offset
        h_key.keyframe_insert("location", frame=frame)
    stylus = cylinder("SIMULATED — admitted H contact indicator",
                      board_point(216.55, 154.0, 105), 0.004, 0.140,
                      mats["metal"], 48)
    stylus.rotation_euler = (0, 0, 0)
    visibility(stylus, 1225, 1392)
    for frame, z_mm in ((1225, 105), (1288, 105), (1300, 101),
                        (1320, 101), (1332, 105), (1392, 105)):
        stylus.location = board_point(216.55, 154.0, z_mm)
        stylus.keyframe_insert("location", frame=frame)
    stylus["evidence_status"] = "SIMULATED_CONTACT_INDICATOR_NOT_PHYSICAL_TEST_EVIDENCE"
    bpy.ops.mesh.primitive_cone_add(vertices=48, radius1=0.0012, radius2=0.004,
                                    depth=0.012,
                                    location=board_point(216.55, 154.0, 29))
    stylus_tip = bpy.context.object
    stylus_tip.name = "SIMULATED — compliant stylus tip"
    apply_material(stylus_tip, mats["arm_exact"])
    visibility(stylus_tip, 1225, 1392)
    for frame, z_mm in ((1225, 29), (1288, 29), (1300, 25),
                        (1320, 25), (1332, 29), (1392, 29)):
        stylus_tip.location = board_point(216.55, 154.0, z_mm)
        stylus_tip.keyframe_insert("location", frame=frame)
    stylus_tip["evidence_status"] = "SIMULATED_CONTACT_INDICATOR_NOT_PHYSICAL_TEST_EVIDENCE"

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
        # Request / stakes / promise: one locked hero scene and a restrained orbit.
        (1, Vector((1.90, -2.18, 1.10))), (96, Vector((1.90, -2.18, 1.10))),
        (97, Vector((1.72, -2.02, 1.04))), (240, Vector((1.42, -1.72, 0.94))),
        (241, Vector((1.42, -1.72, 0.94))), (336, Vector((1.28, -1.58, 0.90))),
        # Perceive: camera fixture, then its measured top-down view.
        (337, Vector((0.78, -0.38, 1.28))), (408, Vector((0.62, -0.30, 1.18))),
        (409, Vector((0.00, 0.00, 1.58))), (528, Vector((0.00, 0.00, 1.42))),
        # Proposal and both gate decisions keep the arm visibly still.
        (529, Vector((-1.18, -1.42, 0.82))), (720, Vector((-0.98, -1.22, 0.75))),
        (721, Vector((-0.98, -1.22, 0.75))), (1056, Vector((-0.90, -1.14, 0.72))),
        # Resolve top-down, execute close-up, verify, payoff, end card.
        (1057, Vector((0.18, -0.04, 1.30))), (1224, Vector((0.14, -0.03, 1.16))),
        (1225, Vector((-0.26, -0.46, 0.33))), (1392, Vector((-0.20, -0.36, 0.29))),
        (1393, Vector((0.18, -0.88, 0.60))), (1560, Vector((0.12, -0.78, 0.56))),
        (1561, Vector((1.42, -1.72, 0.94))), (1728, Vector((1.66, -1.94, 1.04))),
        (1729, Vector((1.66, -1.94, 1.04))), (END_FRAME, Vector((1.66, -1.94, 1.04))),
    ]
    targets = [
        (1, Vector((0, 0.02, 0.45))), (336, Vector((0, 0.02, 0.45))),
        (337, Vector((0, 0.02, 1.00))), (408, Vector((0, 0.02, 0.98))),
        (409, Vector((0, 0.00, 0.03))), (528, Vector((0, 0.00, 0.03))),
        (529, Vector((0, -0.02, 0.40))), (1056, Vector((0, -0.02, 0.40))),
        (1057, board_point(216.55, 154.0, 22)), (1224, board_point(216.55, 154.0, 22)),
        (1225, board_point(216.55, 154.0, 32)), (1392, board_point(216.55, 154.0, 30)),
        (1393, Vector((0.08, -0.04, 0.20))), (1560, Vector((0.08, -0.04, 0.20))),
        (1561, Vector((0, 0.02, 0.45))), (END_FRAME, Vector((0, 0.02, 0.45))),
    ]
    animate_transform(camera, camera_positions, targets)

    # A focus target tracks the same authored points as the camera aim. Depth
    # of field remains subtle enough to preserve dimension evidence while
    # separating foreground hardware from the studio background.
    focus = _empty("Animated camera focus")
    for frame, target in targets:
        focus.location = target
        focus.keyframe_insert("location", frame=frame)
    camera.data.dof.use_dof = True
    camera.data.dof.focus_object = focus
    camera.data.dof.aperture_fstop = 5.6
    lens_keys = (
        (1, 35), (96, 35), (97, 35), (336, 42), (337, 58), (408, 72),
        (409, 52), (528, 58), (529, 58), (1056, 68), (1057, 52),
        (1224, 58), (1225, 72), (1392, 85), (1393, 58), (1560, 72),
        (1561, 35), (END_FRAME, 42),
    )
    for frame, focal_length in lens_keys:
        camera.data.lens = focal_length
        camera.data.keyframe_insert("lens", frame=frame)

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
    bpy.ops.object.light_add(type="AREA", location=(-0.35, -0.42, 0.50))
    arm_rim = bpy.context.object
    arm_rim.name = "Arm detail strip"
    arm_rim.data.energy = 235
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

    arm_detail = text_object("Arm detail label", "ROARM-M3\nOFFICIAL ASSEMBLY SURFACE",
                             Vector((0.0, -0.10, 0.42)), 0.030, mats["white"], camera)
    visibility(arm_detail, 97, 240)

    devices = text_object("Device label", "INDEXED DEVICE GEOMETRY\nKEYBOARD + PHONE + DIRECT TAGS",
                          Vector((0.02, -0.14, 0.29)), 0.031, mats["white"], camera)
    visibility(devices, 409, 528)
    add_target_ring("Keyboard target H", 216.55, 154.0, 29, mats["cyan"], 1057, 1224)

    # Coordinate-frame graphics make the camera/board/device transformation
    # visible without pretending these presentation primitives are measured
    # controller telemetry.
    axis_origin = board_point(105, 100, 33)
    add_axis("Board frame X", axis_origin, axis_origin + Vector((0.090, 0, 0)),
             mats["cyan"], 1057, 1224)
    add_axis("Board frame Y", axis_origin, axis_origin + Vector((0, 0.090, 0)),
             mats["amber"], 1057, 1224)
    add_axis("Board frame Z", axis_origin, axis_origin + Vector((0, 0, 0.090)),
             mats["green"], 1057, 1224)

    checked = text_object("Motion label", "PROPOSE → VALIDATE → EXECUTE → VERIFY",
                          Vector((0.0, -0.15, 0.48)), 0.030, mats["white"], camera)
    visibility(checked, 529, 1056)
    route = curve_line("Checked route",
                       [board_point(305, 410, 260), board_point(235, 180, 115),
                        board_point(216.55, 154, 48)], mats["amber"], 0.003)
    visibility(route, 1225, 1392)
    animate_curve_reveal(route, 1225, 1320)

    # The luminous packet communicates admitted-command progression. It is a
    # conceptual state marker, not a simulated TCP or qualified arm motion.
    packet = cylinder("Admitted command packet", board_point(305, 410, 260),
                      0.009, 0.012, mats["cyan"], 32)
    packet.rotation_euler = (math.pi / 2, 0, 0)
    visibility(packet, 1225, 1392)
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
        "the arm surface is a local hash-verified derivative of the official STEP assembly; "
        "its default pose is static and not motion qualification; the H contact "
        "indicator is an explicitly labeled presentation simulation."
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
Style: Badge,Arial,28,&H00FFFFFF,&H000000FF,&H00373E49,&HD00A0E14,-1,0,0,0,100,100,0,0,3,2,0,8,90,90,86,1
Style: Bug,Arial,21,&H00F8C845,&H000000FF,&H90081119,&H70000000,-1,0,0,0,100,100,1,0,1,2,1,9,44,44,30,1
Style: Fine,Arial,18,&H00898F99,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,2,80,80,28,1

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
Dialogue: 1,0:00:16.10,0:00:22.00,CenterCard,,0,0,0,,{\\fad(180,180)}{\\c&H00F8C845}BOARD FRAME LOCKED{\\c&H00F3F6FA}\\N4 marker tags  ✓\\NX / Y axes      ✓
Dialogue: 1,0:00:22.00,0:00:24.00,Stage,,0,0,0,,{\\fad(180,180)}2 · PROPOSE
Dialogue: 1,0:00:24.00,0:00:30.00,Card,,0,0,0,,{\\fad(180,180)}{\\c&H004C9BFF}MODEL PROPOSAL{\\c&H00F3F6FA}\\Naction       press\\Ntarget       keyboard:H\\Nframe        board\\Nconfidence   0.97
Dialogue: 1,0:00:30.00,0:00:31.80,Stage,,0,0,0,,{\\fad(150,150)}3 · CHECK
Dialogue: 1,0:00:31.80,0:00:37.00,CenterCard,,0,0,0,,{\\fad(150,180)}{\\c&H00505AFF}GATE · REJECT{\\c&H00F3F6FA}\\Nframe        camera_raw  ✕\\Nfreshness    stale       ✕\\N\\NARM REMAINS STILL
Dialogue: 1,0:00:37.00,0:00:44.00,CenterCard,,0,0,0,,{\\fad(150,180)}{\\c&H004FCC33}GATE · ACCEPT{\\c&H00F3F6FA}\\Nunits        ✓   frame      ✓\\Nreach        ✓   clearance  ✓\\Nfreshness    ✓
Dialogue: 1,0:00:44.00,0:00:51.00,Card,,0,0,0,,{\\fad(160,180)}{\\c&H00F8C845}RESOLVED TARGET · H{\\c&H00F3F6FA}\\NX  216.55 mm\\NY  154.00 mm\\NZ   48.00 mm\\Ncamera → board → keyboard → H
Dialogue: 1,0:00:51.00,0:00:58.00,Badge,,0,0,0,,{\\fad(140,160)}SIMULATED PRESS  ·  ACTION 1 OF 1  ·  CONTROLLER
Dialogue: 1,0:00:58.00,0:01:05.00,CenterCard,,0,0,0,,{\\fad(160,180)}TELEMETRY  ✓     OBSERVATION  ✓\\N\\N{\\c&H004FCC33\\fs58}VERIFIED{\\rCenterCard}
Dialogue: 1,0:01:05.00,0:01:12.00,Hero,,0,0,0,,{\\fad(220,220)}ONE SHARED CONTRACT
Dialogue: 1,0:01:05.30,0:01:12.00,Sub,,0,0,0,,{\\fad(220,220)}FROM USER INTENT TO VERIFIED PHYSICAL ACTION
Dialogue: 0,0:01:12.00,0:01:17.00,Black,,0,0,0,,{\\p1}m 0 0 l 1920 0 l 1920 1080 l 0 1080{\\p0}
Dialogue: 1,0:01:12.00,0:01:17.00,Hero,,0,0,0,,{\\fad(220,0)}TACTEVRA
Dialogue: 1,0:01:12.20,0:01:17.00,Sub,,0,0,0,,ONE REQUEST. ONE CHECKED PHYSICAL ACTION.\\Ngithub.com/j-webtek/tactevra
Dialogue: 1,0:01:12.00,0:01:17.00,Fine,,0,0,0,,Presentation visualization · static official arm surface · simulated key contact
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


def write_soundtrack(path: Path) -> None:
    """Synthesize a restrained bed with one semantic sound per event."""
    sample_rate = 48_000
    duration = END_FRAME / FPS
    cue_times = (10.0, 14.0, 22.0, 30.0, 37.0, 44.0, 51.0, 58.0, 65.0, 72.0)
    rng = random.Random(30703)

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
            # Quiet tonal bed, mixed well below narration downstream.
            bed = (
                0.030 * math.sin(2 * math.pi * 55.0 * t)
                + 0.018 * math.sin(2 * math.pi * 82.5 * t + 0.6)
                + 0.010 * math.sin(2 * math.pi * 110.0 * t + 1.2)
            )
            cue = 0.0
            for cue_index, cue_time in enumerate(cue_times):
                cue += 0.085 * soft_pulse(t, cue_time, 330.0 + cue_index * 42.0)
            # One semantic sound family per screenplay event.
            for key_tick in (0.55, 1.05, 1.55, 2.05):
                cue += 0.040 * soft_pulse(t, key_tick, 980.0, 0.08)
            for tag_ping in (16.2, 17.1, 18.0, 18.9):
                cue += 0.055 * soft_pulse(t, tag_ping, 620.0, 0.16)
            cue += 0.095 * soft_pulse(t, 34.0, 150.0, 0.55)  # reject
            for index, gate_tick in enumerate((38.0, 39.0, 40.0, 41.0, 42.0)):
                cue += 0.060 * soft_pulse(t, gate_tick, 520.0 + index * 70.0, 0.16)
            cue += 0.110 * soft_pulse(t, 43.0, 860.0, 0.45)  # accept
            cue += 0.115 * soft_pulse(t, 54.2, 1180.0, 0.11)  # key contact
            cue += 0.070 * soft_pulse(t, 60.0, 720.0, 0.18)
            cue += 0.070 * soft_pulse(t, 62.0, 820.0, 0.18)
            cue += 0.110 * soft_pulse(t, 64.0, 930.0, 0.55)  # verified
            # Very light transition air avoids dead cuts without becoming music.
            air = 0.0
            for transition in cue_times[1:]:
                distance = abs(t - transition)
                if distance < 0.16:
                    air += (1.0 - distance / 0.16) * (rng.random() * 2.0 - 1.0) * 0.018
            sample = max(-0.92, min(0.92, bed + cue + air))
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
                                ffmpeg: str) -> None:
    soundtrack = OUT / "tactevra_workcell_explainer_soundtrack_v2.wav"
    captions = OUT / "tactevra_workcell_explainer_captions_v2.srt"
    web_video = OUT / "tactevra_workcell_explainer_web_1080p_v2.mp4"
    social_video = OUT / "tactevra_workcell_explainer_social_square_v2.mp4"
    voice_dir = OUT / "voiceover_v2"
    write_soundtrack(soundtrack)
    write_caption_file(captions)
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
    voice_files = [voice_dir / f"voice_{index:02d}.wav" for index in range(1, 12)]
    inputs: list[str] = [ffmpeg, "-y", "-i", str(silent_video), "-i", str(soundtrack)]
    for voice_file in voice_files:
        inputs.extend(("-i", str(voice_file)))
    audio_graph = ["[1:a]volume=0.16[bed]"]
    mix_labels = ["[bed]"]
    for input_index, start in enumerate(voice_starts, start=2):
        label = f"voice{input_index}"
        delay_ms = int(start * 1000)
        audio_graph.append(
            f"[{input_index}:a]aresample=48000,volume=1.0,"
            f"adelay={delay_ms}|{delay_ms}[{label}]"
        )
        mix_labels.append(f"[{label}]")
    audio_graph.append(
        "".join(mix_labels)
        + f"amix=inputs={len(mix_labels)}:duration=longest:normalize=0,"
          "loudnorm=I=-14:TP=-1:LRA=7[mix]"
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
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
            str(web_video),
        ],
        check=True,
    )
    subtitle_filter = str(captions).replace("\\", "/").replace(":", "\\:")
    subprocess.run(
        [ffmpeg, "-y", "-i", str(final_video),
         "-vf", f"crop=1080:1080:(iw-1080)/2:0,subtitles='{subtitle_filter}':force_style='FontName=Arial,FontSize=19,Outline=2,MarginV=54'",
         "-c:v", "libx264", "-preset", "medium", "-crf", "19",
         "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
         str(social_video)],
        check=True,
    )


def publish_homepage_media() -> None:
    """Publish the reviewed compact film, poster, and selectable captions."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required to publish homepage media")
    source = OUT / "tactevra_workcell_explainer_web_1080p_v2.mp4"
    if not source.is_file():
        raise FileNotFoundError(
            f"Homepage publishing requires the reviewed web render: {source}"
        )
    PUBLIC_MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    captions = PUBLIC_MEDIA_DIR / "tactevra-overview.en.vtt"
    public_video = PUBLIC_MEDIA_DIR / "tactevra-overview.mp4"
    poster = PUBLIC_MEDIA_DIR / "tactevra-overview-poster.jpg"
    write_webvtt_file(captions)
    subprocess.run(
        [
            ffmpeg, "-y", "-i", str(source), "-i", str(captions),
            "-map", "0:v:0", "-map", "0:a:0", "-map", "1:0",
            "-c:v", "copy", "-c:a", "copy", "-c:s", "mov_text",
            "-metadata:s:s:0", "language=eng",
            "-metadata:s:s:0", "title=English",
            "-disposition:s:0", "0", "-movflags", "+faststart",
            str(public_video),
        ],
        check=True,
    )
    subprocess.run(
        [
            ffmpeg, "-y", "-ss", "11.50", "-i", str(source),
            "-frames:v", "1", "-update", "1",
            "-vf", "scale=1280:-2", "-q:v", "2",
            str(poster),
        ],
        check=True,
    )


def composite_overlay(clean_video: Path, final_video: Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required to composite informational labels")
    ass_path = OUT / "tactevra_workcell_explainer_v2.ass"
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
    silent_video = OUT / "tactevra_workcell_explainer_silent_v2.mp4"
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
    mux_soundtrack_and_variants(silent_video, final_video, ffmpeg)


def main() -> None:
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if "--publish-homepage-media" in args:
        publish_homepage_media()
        print(f"TACTEVRA_PUBLIC_MEDIA={PUBLIC_MEDIA_DIR}")
        return
    if "--overlay-only" in args:
        clean_video = OUT / "tactevra_workcell_explainer_clean_v2.mp4"
        final_video = OUT / "tactevra_workcell_explainer_v2.mp4"
        if not clean_video.exists():
            raise FileNotFoundError(
                f"Overlay-only mode requires an existing clean render: {clean_video}"
            )
        composite_overlay(clean_video, final_video)
        print(f"TACTEVRA_OUTPUT={OUT}")
        return

    scene = build()
    blend_path = OUT / "tactevra_workcell_explainer_v2.blend"
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
        clean_video = OUT / "tactevra_workcell_explainer_clean_v2.mp4"
        final_video = OUT / "tactevra_workcell_explainer_v2.mp4"
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
        scene.render.filepath = str(OUT / "tactevra_workcell_explainer_poster_v2.png")
        bpy.ops.render.render(write_still=True)

    print(f"TACTEVRA_OUTPUT={OUT}")


if __name__ == "__main__":
    main()

"""Build the reusable v2.1 production framework and the first `r` contact beat.

This is a production scaffold, not evidence that a physical contact occurred.
It reuses the measured RC03 workcell assets, creates four native Blender camera
rigs, binds all 17 storyboard scenes to the timeline, and animates the three
authority graphics plus the seven-phase first-contact benchmark.

Usage (Blender 4.3+):

  blender --background --factory-startup \
    --python presentations/blender/build_storyboard_v21_benchmark.py

  blender --background --factory-startup \
    --python presentations/blender/build_storyboard_v21_benchmark.py -- \
    --preview-benchmark
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_workcell_explainer as base


SCRIPT = Path(__file__).resolve()
ROOT = SCRIPT.parents[2]
MANIFEST_PATH = SCRIPT.with_name("storyboard_v21_shots.json")
OUT = ROOT / "tmp" / "blender-storyboard-v21"
OUT.mkdir(parents=True, exist_ok=True)


def production_collection(name: str, *, locked: bool = False) -> bpy.types.Collection:
    collection = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    if collection.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(collection)
    collection["tactevra_production_collection"] = True
    collection["locked_reference"] = locked
    return collection


def classify(obj: bpy.types.Object, collection: bpy.types.Collection, role: str) -> None:
    if obj.name not in collection.objects:
        collection.objects.link(obj)
    obj["production_role"] = role


def existing_materials() -> dict[str, bpy.types.Material]:
    names = {
        "abs": "Printed matte black ABS",
        "carbon": "Carbon link",
        "servo": "Black servo",
        "metal": "Machined metal",
        "brass": "Servo identification brass",
        "arm_exact": "Official RoArm assembly finish",
        "wire": "Servo harness",
        "green": "Verified green",
        "cyan": "Tactevra cyan",
        "white": "Reference white",
    }
    return {key: bpy.data.materials[value] for key, value in names.items()}


def find_key(legend: str) -> bpy.types.Object:
    for obj in bpy.context.scene.objects:
        if obj.name.startswith("Key cap") and obj.get("legend") == legend:
            return obj
    raise RuntimeError(f"Keyboard key not found: {legend}")


def camera_rig(name: str, location: Vector, target: Vector, lens: float,
               collection: bpy.types.Collection) -> tuple[bpy.types.Object, bpy.types.Object]:
    bpy.ops.object.camera_add(location=location)
    camera = bpy.context.object
    camera.name = f"CAM_{name.upper()}"
    camera.data.lens = lens
    camera.data.sensor_width = 36
    camera.data.dof.use_dof = True
    camera.data.dof.aperture_fstop = 7.1 if name != "macro" else 5.6
    bpy.ops.object.empty_add(type="PLAIN_AXES", location=target)
    aim = bpy.context.object
    aim.name = f"AIM_{name.upper()}"
    constraint = camera.constraints.new("TRACK_TO")
    constraint.name = "Deterministic shot aim"
    constraint.target = aim
    constraint.track_axis = "TRACK_NEGATIVE_Z"
    constraint.up_axis = "UP_Y"
    camera.data.dof.focus_object = aim
    classify(camera, collection, f"camera_rig:{name}")
    classify(aim, collection, f"camera_aim:{name}")
    return camera, aim


def key_pose(obj: bpy.types.Object, frame: int, value: Vector) -> None:
    obj.location = value
    obj.keyframe_insert("location", frame=frame)


def animate_camera(camera: bpy.types.Object, aim: bpy.types.Object,
                   start: int, end: int, start_location: Vector,
                   end_location: Vector, target: Vector) -> None:
    key_pose(camera, start, start_location)
    key_pose(camera, end, end_location)
    key_pose(aim, start, target)
    key_pose(aim, end, target)


def set_scale(obj: bpy.types.Object, frame: int, scale: float) -> None:
    obj.scale = (scale, scale, scale)
    obj.keyframe_insert("scale", frame=frame)


def arm_pose(target_xy: tuple[float, float], manifest: dict) -> tuple[Vector, Vector, Vector]:
    """Return shoulder, elbow, and wrist points for the presentation rig."""
    tx, ty, _tz = manifest["arm"]["nominal_board_T_robot_world_translation"]
    shoulder = base.board_point(tx, ty, 0) + Vector((0, 0, 0.120))
    wrist = base.board_point(*target_xy, 0) + Vector((0, 0, 0.205))
    length_a, length_b = 0.2387, 0.1550
    direction = wrist - shoulder
    distance = direction.length
    axis = direction.normalized()
    projection = (length_a ** 2 - length_b ** 2 + distance ** 2) / (2 * distance)
    height = math.sqrt(max(length_a ** 2 - projection ** 2, 0.0))
    side = axis.cross(Vector((0, 0, 1))).normalized()
    normal = side.cross(axis).normalized()
    elbow = shoulder + axis * projection + normal * height
    return shoulder, elbow, wrist


def segment_rotation(start: Vector, end: Vector):
    return (end - start).to_track_quat("Z", "Y")


def parent_preserve_world(obj: bpy.types.Object, parent: bpy.types.Object) -> None:
    world = obj.matrix_world.copy()
    bpy.context.view_layer.update()
    obj.parent = parent
    obj.matrix_parent_inverse = parent.matrix_world.inverted()
    obj.matrix_world = world


def add_articulation_controls(
    rig: dict[str, object],
    target_xy: tuple[float, float],
    collection: bpy.types.Collection,
) -> dict[str, bpy.types.Object]:
    """Parent the detailed fixed-pose geometry to three animatable frames.

    This keeps every servo, rail, fastener, and gripper component from the
    approved benchmark while allowing continuous target-to-target movement.
    The shoulder is fixed; upper and forearm frames rotate as rigid link
    groups; the wrist frame translates while preserving the vertical stylus.
    """
    shoulder, elbow, wrist = arm_pose(target_xy, rig["manifest"])
    controls: dict[str, bpy.types.Object] = {}
    for name, location, rotation in (
        ("upper", shoulder, segment_rotation(shoulder, elbow)),
        ("forearm", elbow, segment_rotation(elbow, wrist)),
        ("wrist", wrist, None),
    ):
        obj = bpy.data.objects.new(f"CTRL_{name.upper()}_LINK", None)
        bpy.context.scene.collection.objects.link(obj)
        obj.location = location
        if rotation is not None:
            obj.rotation_mode = "QUATERNION"
            obj.rotation_quaternion = rotation
        classify(obj, collection, f"articulation_control:{name}")
        controls[name] = obj

    moving = set(rig["moving"])
    for obj in rig["objects"]:
        lower = obj.name.lower()
        if "servo harness" in lower:
            obj.hide_render = True
            continue
        if "forearm" in lower or "elbow" in lower:
            parent_preserve_world(obj, controls["forearm"])
        elif "upper" in lower:
            parent_preserve_world(obj, controls["upper"])
        elif "wrist" in lower or "gripper" in lower or "stylus" in lower or obj in moving:
            obj.animation_data_clear()
            parent_preserve_world(obj, controls["wrist"])
    return controls


def animate_arm_target(
    controls: dict[str, bpy.types.Object], manifest: dict,
    target_xy: tuple[float, float], frame: int, *, press: float = 0.0,
) -> None:
    shoulder, elbow, wrist = arm_pose(target_xy, manifest)
    upper, forearm, wrist_control = controls["upper"], controls["forearm"], controls["wrist"]
    upper.location = shoulder
    upper.rotation_quaternion = segment_rotation(shoulder, elbow)
    upper.keyframe_insert("location", frame=frame)
    upper.keyframe_insert("rotation_quaternion", frame=frame)
    forearm.location = elbow
    forearm.rotation_quaternion = segment_rotation(elbow, wrist)
    forearm.keyframe_insert("location", frame=frame)
    forearm.keyframe_insert("rotation_quaternion", frame=frame)
    wrist_control.location = wrist + Vector((0, 0, press))
    wrist_control.keyframe_insert("location", frame=frame)


def animate_key_rhythm(
    controls: dict[str, bpy.types.Object], rig: dict[str, object],
    keys: list[bpy.types.Object], authority: dict[str, bpy.types.Object],
) -> None:
    """Animate e-a-d-y as four independently permitted contact cycles."""
    uncertainty = authority["uncertainty"]
    permit = authority["permit"]
    ghost = authority["ghost"]
    cycles = ((1153, 1194), (1195, 1236), (1237, 1278), (1279, 1320))
    previous_xy = (
        (find_key("R").location.x * 1000) + base.BOARD_CENTER_MM.x,
        (find_key("R").location.y * 1000) + base.BOARD_CENTER_MM.y,
    )
    for index, (key, (start, end)) in enumerate(zip(keys, cycles)):
        target_xy = (
            (key.location.x * 1000) + base.BOARD_CENTER_MM.x,
            (key.location.y * 1000) + base.BOARD_CENTER_MM.y,
        )
        align, permit_frame = start + 12, start + 18
        contact, release, verified = start + 25, start + 31, end
        animate_arm_target(controls, rig["manifest"], previous_xy, start)
        animate_arm_target(controls, rig["manifest"], target_xy, align)
        animate_arm_target(controls, rig["manifest"], target_xy, contact, press=-0.004)
        animate_arm_target(controls, rig["manifest"], target_xy, release, press=0.0)
        animate_arm_target(controls, rig["manifest"], target_xy, verified)

        target = key.location + Vector((0, 0, 0.009))
        uncertainty.location = target
        uncertainty.keyframe_insert("location", frame=start)
        set_scale(uncertainty, start, 1.45)
        uncertainty.location = target
        uncertainty.keyframe_insert("location", frame=align)
        set_scale(uncertainty, align, 0.62)
        set_scale(uncertainty, contact, 0.62)
        set_scale(uncertainty, release, 0.0)

        permit.location = target + Vector((0, 0, 0.090))
        permit.keyframe_insert("location", frame=align)
        set_scale(permit, align, 0.0)
        set_scale(permit, permit_frame, 1.0)
        set_scale(ghost, align, 1.0)
        set_scale(ghost, permit_frame, 0.0)
        permit.location = target + Vector((0, 0, 0.020))
        permit.keyframe_insert("location", frame=contact)
        set_scale(permit, contact, 1.0)
        set_scale(permit, release, 0.0)

        base_z = key.location.z
        for frame, offset in ((start, 0.0), (contact - 1, 0.0),
                              (contact, -0.004), (release - 1, -0.004),
                              (release, 0.0), (verified, 0.0)):
            key.location.z = base_z + offset
            key.keyframe_insert("location", frame=frame)

        if index + 1 < len(keys):
            next_key = keys[index + 1]
            ghost.location = next_key.location + Vector((0, 0, 0.009))
            ghost.keyframe_insert("location", frame=release)
            set_scale(ghost, release, 0.0)
            set_scale(ghost, release + 6, 1.0)
            set_scale(ghost, verified, 1.0)
        else:
            set_scale(ghost, release, 0.0)
            set_scale(ghost, verified, 0.0)
        previous_xy = target_xy


def make_authority_graphics(
    mats: dict[str, bpy.types.Material],
    collection: bpy.types.Collection,
    r_key: bpy.types.Object,
    e_key: bpy.types.Object,
) -> dict[str, bpy.types.Object]:
    r_target = r_key.location + Vector((0, 0, 0.009))
    e_target = e_key.location + Vector((0, 0, 0.009))

    bpy.ops.mesh.primitive_torus_add(
        major_radius=0.020, minor_radius=0.0022, major_segments=64,
        minor_segments=12, location=r_target,
    )
    uncertainty = bpy.context.object
    uncertainty.name = "AUTH_BLUE_UNCERTAINTY_R"
    base.apply_material(uncertainty, mats["cyan"])
    classify(uncertainty, collection, "bounded_uncertainty")
    uncertainty["meaning"] = "full error bound must fit inside target"
    set_scale(uncertainty, 961, 1.75)
    set_scale(uncertainty, 1009, 0.62)
    set_scale(uncertainty, 1056, 0.62)
    set_scale(uncertainty, 1093, 0.0)

    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=0.006,
                                         location=r_target + Vector((0, 0, 0.22)))
    permit = bpy.context.object
    permit.name = "AUTH_GREEN_ONE_CONTACT_PERMIT"
    base.apply_material(permit, mats["green"])
    classify(permit, collection, "one_contact_permit")
    permit["meaning"] = "short-lived authority for exactly one physical contact"
    set_scale(permit, 961, 0.0)
    set_scale(permit, 1009, 1.0)
    key_pose(permit, 1009, r_target + Vector((0, 0, 0.22)))
    key_pose(permit, 1049, r_target + Vector((0, 0, 0.020)))
    set_scale(permit, 1056, 1.0)
    set_scale(permit, 1093, 0.0)

    ghost_root = bpy.data.objects.new("AUTH_DOTTED_E_PREVIEW_NO_AUTHORITY", None)
    bpy.context.scene.collection.objects.link(ghost_root)
    ghost_root.location = e_target
    classify(ghost_root, collection, "preview_no_authority")
    ghost_root["meaning"] = "preview only; cannot authorize motion"
    for index in range(16):
        angle = index * math.tau / 16
        offset = Vector((0.018 * math.cos(angle), 0.018 * math.sin(angle), 0))
        bpy.ops.mesh.primitive_uv_sphere_add(
            segments=16, ring_count=8, radius=0.0018, location=e_target + offset,
        )
        dot = bpy.context.object
        dot.name = f"AUTH_GHOST_E_DOT_{index:02d}"
        base.apply_material(dot, mats["white"])
        dot.parent = ghost_root
        dot.location = offset
        classify(dot, collection, "preview_no_authority")
    set_scale(ghost_root, 961, 0.0)
    set_scale(ghost_root, 1128, 0.0)
    set_scale(ghost_root, 1140, 1.0)
    set_scale(ghost_root, 1152, 1.0)
    return {"uncertainty": uncertainty, "permit": permit, "ghost": ghost_root}


def build() -> bpy.types.Scene:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    scene = base.build()
    scene.frame_start = manifest["frame_start"]
    scene.frame_end = manifest["frame_end"]
    scene["storyboard_authority"] = str(MANIFEST_PATH.relative_to(ROOT))
    scene["evidence_boundary"] = "SIMULATED_WORKCELL_SEQUENCE"

    # Retire graphics authored for the published H-only film. Leaving them on
    # the extended timeline would incorrectly show a second target and route
    # during the new lowercase-r benchmark.
    legacy_graphics = {
        "Keyboard target H", "Resolved H label", "Camera to H resolve trace",
        "Verified host character H", "Admitted command packet", "Checked route",
    }
    for name in legacy_graphics:
        obj = scene.objects.get(name)
        if obj is not None:
            obj.animation_data_clear()
            obj.hide_render = True

    assets = production_collection("TACTEVRA_ASSETS_LOCKED", locked=True)
    cameras = production_collection("TACTEVRA_SHOT_RIGS")
    graphics = production_collection("TACTEVRA_AUTHORITY_GRAPHICS")
    action = production_collection("TACTEVRA_R_CONTACT_BENCHMARK")

    for obj in tuple(scene.objects):
        if obj.type in {"MESH", "CURVE"} and not obj.name.startswith("Continuous"):
            classify(obj, assets, "measured_or_designed_reference")

    # Retire the old H-only proxy and rigid vendor surface in this benchmark.
    # The reusable articulated presentation rig below is rebuilt against the
    # actual lowercase `r` target and stays continuous across the contact beat.
    for obj in tuple(scene.objects):
        if obj.name.startswith("Continuous") or obj.name.startswith("VENDOR-SOURCED"):
            obj.animation_data_clear()
            obj.hide_render = True

    mats = existing_materials()
    r_key = find_key("R")
    e_key = find_key("E")
    r_base_z = r_key.location.z
    for frame, offset in ((961, 0.0), (1056, 0.0), (1064, -0.004),
                          (1084, -0.004), (1093, 0.0), (1152, 0.0)):
        r_key.location.z = r_base_z + offset
        r_key.keyframe_insert("location", frame=frame)
    r_xy_mm = (
        (r_key.location.x * 1000) + base.BOARD_CENTER_MM.x,
        (r_key.location.y * 1000) + base.BOARD_CENTER_MM.y,
    )
    rig = base.add_continuous_press_arm(
        mats,
        target_xy=r_xy_mm,
        motion_profile=((961, 0.0), (1320, 0.0)),
    )
    for obj in rig["objects"]:
        classify(obj, action, "articulated_presentation_rig")
        obj["simulation_only"] = True
    controls = add_articulation_controls(rig, r_xy_mm, action)
    animate_arm_target(controls, rig["manifest"], r_xy_mm, 961)
    animate_arm_target(controls, rig["manifest"], r_xy_mm, 1032)
    animate_arm_target(controls, rig["manifest"], r_xy_mm, 1056, press=-0.004)
    animate_arm_target(controls, rig["manifest"], r_xy_mm, 1084, press=-0.004)
    animate_arm_target(controls, rig["manifest"], r_xy_mm, 1093)
    animate_arm_target(controls, rig["manifest"], r_xy_mm, 1152)
    graphics_objects = make_authority_graphics(mats, graphics, r_key, e_key)
    animate_key_rhythm(
        controls, rig,
        [find_key(letter) for letter in ("E", "A", "D", "Y")],
        graphics_objects,
    )

    # Four reusable rigs cover the shot palette without an add-on dependency.
    r_target = r_key.location + Vector((0, 0, 0.060))
    phone_target = base.board_point(538, 166, 35)
    board_target = Vector((0, 0, 0.14))
    rigs = {
        "macro": camera_rig("macro", Vector((0.26, -0.62, 0.34)), r_target, 72, cameras),
        "dolly": camera_rig("dolly", Vector((0.46, -1.04, 0.62)), board_target, 58, cameras),
        "arm_follow": camera_rig("arm_follow", Vector((0.52, -0.82, 0.54)), phone_target, 52, cameras),
        "hero": camera_rig("hero", Vector((0.38, -1.42, 0.84)), board_target, 44, cameras),
    }
    animate_camera(*rigs["macro"], 961, 1152,
                   Vector((0.28, -0.58, 0.35)), Vector((0.21, -0.50, 0.29)), r_target)
    animate_camera(*rigs["dolly"], 361, 504,
                   Vector((0.48, -1.06, 0.64)), Vector((0.28, -0.88, 0.55)), board_target)
    animate_camera(*rigs["dolly"], 1153, 1320,
                   Vector((0.34, -0.66, 0.40)), Vector((-0.04, -0.58, 0.34)),
                   base.board_point(185, 154, 70))
    animate_camera(*rigs["arm_follow"], 1465, 1896,
                   Vector((0.18, -0.76, 0.53)), Vector((0.55, -0.72, 0.45)), phone_target)
    animate_camera(*rigs["hero"], 1, 2400,
                   Vector((0.42, -1.48, 0.88)), Vector((0.31, -1.30, 0.78)), board_target)

    scene.timeline_markers.clear()
    for shot in manifest["shots"]:
        marker = scene.timeline_markers.new(
            f"S{shot['id']:02d}_{shot['slug']}", frame=shot["start"]
        )
        marker.camera = rigs[shot["rig"]][0]
        marker["stage"] = shot["stage"] or "—"
        marker["seconds"] = shot["seconds"]
    for phase in manifest["benchmark"]["phases"]:
        marker = scene.timeline_markers.new(
            f"R_{phase['name'].upper()}", frame=phase["frame"]
        )
        marker["benchmark_phase"] = True

    scene.camera = rigs["macro"][0]
    for obj in (*graphics_objects.values(), *rig["moving"], *controls.values(),
                r_key, find_key("E"), find_key("A"), find_key("D"), find_key("Y")):
        if obj.animation_data and obj.animation_data.action:
            for curve in obj.animation_data.action.fcurves:
                for point in curve.keyframe_points:
                    point.interpolation = "BEZIER"
                    point.easing = "AUTO"

    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.resolution_percentage = 50
    scene.render.image_settings.file_format = "PNG"
    scene.frame_set(961)
    return scene


def main() -> None:
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    scene = build()
    blend_path = OUT / "tactevra_storyboard_v21_benchmark.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    preview_frames: tuple[int, ...] = ()
    if "--preview-benchmark" in args:
        preview_frames += (961, 1009, 1049, 1068, 1093, 1140)
    if "--preview-rhythm" in args:
        preview_frames += (1153, 1165, 1178, 1207, 1220, 1249, 1262, 1291, 1304, 1320)
    if preview_frames:
        for frame in preview_frames:
            scene.frame_set(frame)
            scene.camera = (
                bpy.data.objects["CAM_MACRO"] if frame <= 1152
                else bpy.data.objects["CAM_DOLLY"]
            )
            scene.render.filepath = str(OUT / f"storyboard_{frame:04d}.png")
            bpy.ops.render.render(write_still=True)
    print(f"TACTEVRA_STORYBOARD_V21={blend_path}")


if __name__ == "__main__":
    main()

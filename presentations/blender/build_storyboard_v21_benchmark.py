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
        "amber": "Validation amber",
        "white": "Reference white",
        "phone_panel": "Phone interface panel",
        "legend": "Keyboard legends",
        "screen_glass": "Phone optical glass",
        "screen": "Phone screen",
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


def arm_pose(
    target_xy: tuple[float, float], manifest: dict, *, wrist_z: float = 0.205,
) -> tuple[Vector, Vector, Vector]:
    """Return shoulder, elbow, and wrist points for the presentation rig."""
    tx, ty, _tz = manifest["arm"]["nominal_board_T_robot_world_translation"]
    shoulder = base.board_point(tx, ty, 0) + Vector((0, 0, 0.120))
    wrist = base.board_point(*target_xy, 0) + Vector((0, 0, wrist_z))
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
    wrist_z: float = 0.205,
) -> None:
    shoulder, elbow, wrist = arm_pose(target_xy, manifest, wrist_z=wrist_z)
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
    tick = authority["tick"]
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
        # Scene 8 already taught uncertainty and preview semantics. The rhythm
        # deliberately reduces the overlay to one permit and one result tick.
        set_scale(uncertainty, start, 0.0)
        set_scale(ghost, start, 0.0)

        permit.location = target + Vector((0, 0, 0.090))
        permit.keyframe_insert("location", frame=align)
        set_scale(permit, align, 0.0)
        set_scale(permit, permit_frame, 1.0)
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

        tick.location = target + Vector((0, 0, 0.012))
        tick.keyframe_insert("location", frame=verified - 5)
        set_scale(tick, verified - 6, 0.0)
        set_scale(tick, verified - 5, 1.0)
        set_scale(tick, verified, 0.0)
        previous_xy = target_xy


def animate_keyboard_to_phone_crossing(
    controls: dict[str, bpy.types.Object], rig: dict[str, object],
    keyboard_xy: tuple[float, float], phone_xy: tuple[float, float],
) -> None:
    """Retract, cross through a high corridor, and finish above the phone."""
    waypoints = (
        (1320, keyboard_xy, 0.205),
        (1340, keyboard_xy, 0.255),
        (1464, keyboard_xy, 0.255),
        (1465, keyboard_xy, 0.255),
        (1528, (360.0, 190.0), 0.275),
        (1608, phone_xy, 0.255),
    )
    for frame, target_xy, wrist_z in waypoints:
        animate_arm_target(
            controls, rig["manifest"], target_xy, frame, wrist_z=wrist_z,
        )


def add_phone_message_ui(
    layout: dict, mats: dict[str, bpy.types.Material],
    collection: bpy.types.Collection,
) -> tuple[dict[str, tuple[float, float]], list[bpy.types.Object]]:
    """Build a measured, presentation-only Messages keyboard on the phone.

    The physical chassis remains the canonical measured asset. These thin
    screen-plane objects visualize the expected app state and tap targets; they
    are not represented as captured software evidence.
    """
    dev = layout["devices"]["phone"]
    ox, oy = dev["nominal_origin_xy"]
    sx, sy, _sz = dev["configured_size"]
    z = dev["nominal_screen_plane_z"] + 1.25
    ui: list[bpy.types.Object] = []
    home_ui: list[bpy.types.Object] = []
    messages_ui: list[bpy.types.Object] = []
    targets: dict[str, tuple[float, float]] = {}
    messages_bg = base.material(
        "Modeled Messages matte display", (0.003, 0.009, 0.018, 1),
        metallic=0.0, roughness=0.96, ior_level=0.0,
    )

    # Hide the older generic verification treatment in favor of one coherent
    # Messages state throughout the phone chapter.
    for obj in tuple(bpy.context.scene.objects):
        if obj.name.startswith("Phone UI"):
            obj.hide_render = True

    backdrop = base.cube(
        "Phone Messages matte backdrop",
        base.board_point(ox + sx / 2, oy + sy / 2, z - 0.00055),
        ((sx - 5.0) / 1000, (sy - 8.0) / 1000, 0.00035), messages_bg, 0.0035,
    )
    expected_home = base.board_text(
        "Phone expected home state", "EXPECTED home · OBSERVED home ✓",
        base.board_point(ox + sx / 2, oy + sy - 25, z), 0.0030, mats["green"],
    )
    messages_icon = base.cube(
        "Phone Messages app target",
        base.board_point(ox + sx / 2, oy + sy / 2, z - 0.0002),
        (0.026, 0.026, 0.00045), mats["cyan"], 0.006,
    )
    messages_label = base.board_text(
        "Phone Messages app label", "Messages",
        base.board_point(ox + sx / 2, oy + sy / 2 - 18, z),
        0.0034, mats["white"],
    )
    home_ui.extend((expected_home, messages_icon, messages_label))
    targets["messages_app"] = (ox + sx / 2, oy + sy / 2)

    header = base.board_text(
        "Phone Messages header", "MESSAGES · CONTACT",
        base.board_point(ox + sx / 2, oy + sy - 18, z), 0.0042, mats["white"],
    )
    composer = base.cube(
        "Phone composer field",
        base.board_point(ox + sx / 2 - 4, oy + sy - 42, z - 0.0002),
        ((sx - 20) / 1000, 0.018, 0.00045), mats["phone_panel"], 0.004,
    )
    send = base.cylinder(
        "Phone Send target", base.board_point(ox + sx - 9, oy + sy - 42, z),
        0.0062, 0.00055, mats["cyan"], 36,
    )
    messages_ui.extend((header, composer, send))
    targets["send"] = (ox + sx - 9, oy + sy - 42)

    rows = (
        ("qwertyuiop", oy + 70, ox + 6, ox + sx - 6),
        ("asdfghjkl", oy + 52, ox + 9, ox + sx - 9),
        ("zxcvbnm", oy + 34, ox + 14, ox + sx - 14),
    )
    for letters, y, left, right in rows:
        step = (right - left) / (len(letters) - 1)
        for index, letter in enumerate(letters):
            x = left + step * index
            key = base.cube(
                f"Phone key {letter}", base.board_point(x, y, z - 0.0002),
                (0.0062, 0.012, 0.00040), mats["screen_glass"], 0.0022,
            )
            label = base.board_text(
                f"Phone key legend {letter}", letter,
                base.board_point(x, y, z + 0.0005), 0.0032, mats["white"],
            )
            messages_ui.extend((key, label))
            targets[letter] = (x, y)

    space_xy = (ox + sx / 2, oy + 16)
    space = base.cube(
        "Phone key space", base.board_point(*space_xy, z - 0.0002),
        (0.040, 0.0115, 0.00040), mats["screen_glass"], 0.0025,
    )
    space_label = base.board_text(
        "Phone key legend space", "space", base.board_point(*space_xy, z + 0.0005),
        0.0028, mats["legend"],
    )
    messages_ui.extend((space, space_label))
    targets[" "] = space_xy

    compression_badge_panel = base.cube(
        "Phone disclosed time compression badge",
        base.board_point(ox + sx / 2, oy + 92, z - 0.0001),
        (0.018, 0.014, 0.00055), mats["amber"], 0.005,
    )
    compression_badge_panel["meaning"] = "disclosed editorial time compression"
    compression_badge = base.board_text(
        "Phone disclosed time compression label", "2×",
        # Lift the type a full millimetre above the badge face. The phone UI
        # uses millimetre board coordinates, while mesh dimensions are metres.
        base.board_point(ox + sx / 2, oy + 92, z + 1.0),
        0.0065, mats["white"],
    )
    compression_badge["meaning"] = "disclosed editorial time compression"
    messages_ui.extend((compression_badge_panel, compression_badge))

    ui.extend((backdrop, *home_ui, *messages_ui))

    for obj in ui:
        classify(obj, collection, "modeled_phone_messages_ui")
        obj["presentation_only"] = True
        set_scale(obj, 1, 0.0)
        set_scale(obj, 1608, 0.0)
    set_scale(backdrop, 1609, 1.0)
    set_scale(backdrop, 2256, 1.0)
    for obj in home_ui:
        set_scale(obj, 1609, 1.0)
        set_scale(obj, 1691, 1.0)
        set_scale(obj, 1692, 0.0)
    for obj in messages_ui:
        set_scale(obj, 1691, 0.0)
        set_scale(obj, 1692, 1.0)
        set_scale(obj, 2256, 1.0)
    for obj in (compression_badge_panel, compression_badge):
        set_scale(obj, 1692, 0.0)
        set_scale(obj, 1849, 0.0)
        set_scale(obj, 1850, 1.0)
        set_scale(obj, 1968, 1.0)
        set_scale(obj, 1969, 0.0)
    return targets, ui


def animate_phone_message_sequence(
    controls: dict[str, bpy.types.Object], rig: dict[str, object],
    targets: dict[str, tuple[float, float]], authority: dict[str, bpy.types.Object],
    layout: dict, mats: dict[str, bpy.types.Material],
    collection: bpy.types.Collection,
) -> dict[str, object]:
    """Open Messages, type `on my way`, then separately permit Send."""
    phrase = "on my way"
    app_contact = 1660
    contacts = (1800, 1840, 1872, 1888, 1904, 1920, 1936, 1952, 1960)
    uncertainty, permit, ghost = (
        authority["uncertainty"], authority["permit"], authority["ghost"]
    )
    dev = layout["devices"]["phone"]
    ox, oy = dev["nominal_origin_xy"]
    z = dev["nominal_screen_plane_z"] + 1.9
    state_labels: list[bpy.types.Object] = []

    # Teach the phone-state check once in full before simplifying later taps.
    app_xy = targets["messages_app"]
    app_target = base.board_point(*app_xy, z)
    animate_arm_target(controls, rig["manifest"], app_xy, 1609, wrist_z=0.255)
    animate_arm_target(controls, rig["manifest"], app_xy, 1640, wrist_z=0.215)
    animate_arm_target(controls, rig["manifest"], app_xy, app_contact, press=-0.004)
    animate_arm_target(controls, rig["manifest"], app_xy, 1670)
    animate_arm_target(controls, rig["manifest"], app_xy, 1692, wrist_z=0.225)
    uncertainty.location = app_target
    uncertainty.keyframe_insert("location", frame=1640)
    set_scale(uncertainty, 1640, 1.05)
    set_scale(uncertainty, 1650, 0.42)
    set_scale(uncertainty, 1670, 0.0)
    ghost.location = app_target
    ghost.keyframe_insert("location", frame=1640)
    set_scale(ghost, 1640, 0.65)
    set_scale(ghost, 1650, 0.0)
    permit.location = app_target + Vector((0, 0, 0.060))
    permit.keyframe_insert("location", frame=1650)
    set_scale(permit, 1640, 0.0)
    set_scale(permit, 1650, 0.75)
    permit.location = app_target + Vector((0, 0, 0.012))
    permit.keyframe_insert("location", frame=app_contact)
    set_scale(permit, app_contact, 0.75)
    set_scale(permit, 1670, 0.0)

    tick = base.board_text(
        "Phone compact verification tick", "✓",
        base.board_point(ox + 10, oy + dev["configured_size"][1] - 18, z),
        0.0052, mats["green"],
    )
    classify(tick, collection, "compact_per_contact_verification")
    tick["presentation_only"] = True
    set_scale(tick, 1, 0.0)
    set_scale(tick, 1692, 1.0)
    set_scale(tick, 1700, 0.0)

    # Re-enter from the verified composer and show each observed prefix. The
    # first two characters run at full pace; the remaining montage is visibly
    # marked 2x. From here onward only the permit and verification tick remain.
    first_xy = targets[phrase[0]]
    animate_arm_target(controls, rig["manifest"], first_xy, 1777, wrist_z=0.225)
    for index, (character, contact) in enumerate(zip(phrase, contacts)):
        target_xy = targets[character]
        check, permit_frame, release, verify = contact - 8, contact - 4, contact + 3, contact + 6
        animate_arm_target(controls, rig["manifest"], target_xy, check, wrist_z=0.205)
        animate_arm_target(controls, rig["manifest"], target_xy, contact, press=-0.004)
        animate_arm_target(controls, rig["manifest"], target_xy, release)
        animate_arm_target(controls, rig["manifest"], target_xy, verify)

        target = base.board_point(*target_xy, z)
        set_scale(uncertainty, check, 0.0)
        set_scale(ghost, check, 0.0)
        permit.location = target + Vector((0, 0, 0.060))
        permit.keyframe_insert("location", frame=permit_frame)
        set_scale(permit, check, 0.0)
        set_scale(permit, permit_frame, 0.75)
        permit.location = target + Vector((0, 0, 0.012))
        permit.keyframe_insert("location", frame=contact)
        set_scale(permit, contact, 0.75)
        set_scale(permit, release, 0.0)
        set_scale(tick, verify - 1, 0.0)
        set_scale(tick, verify, 1.0)
        set_scale(tick, verify + 5, 0.0)

        prefix = phrase[: index + 1]
        label = base.board_text(
            f"Phone observed composer {index + 1:02d}", prefix,
            base.board_point(ox + 28, oy + dev["configured_size"][1] - 42, z),
            0.0040, mats["white"],
        )
        classify(label, collection, "observed_phone_composer_state")
        label["observed_text"] = prefix
        label["presentation_only"] = True
        set_scale(label, 1, 0.0)
        set_scale(label, verify - 1, 0.0)
        set_scale(label, verify, 1.0)
        if index + 1 < len(contacts):
            next_contact = contacts[index + 1]
            set_scale(label, next_contact - 9, 1.0)
            set_scale(label, next_contact - 8, 0.0)
        else:
            set_scale(label, 2059, 1.0)
            set_scale(label, 2060, 0.0)
        state_labels.append(label)

    # Send is a distinct, slower commitment with its own screen check and permit.
    send_xy = targets["send"]
    animate_arm_target(controls, rig["manifest"], send_xy, 1988, wrist_z=0.215)
    animate_arm_target(controls, rig["manifest"], send_xy, 2028, press=-0.004)
    animate_arm_target(controls, rig["manifest"], send_xy, 2040)
    animate_arm_target(controls, rig["manifest"], send_xy, 2088, wrist_z=0.245)
    send_target = base.board_point(*send_xy, z)
    set_scale(uncertainty, 1988, 0.0)
    set_scale(ghost, 1988, 0.0)
    permit.location = send_target + Vector((0, 0, 0.070))
    permit.keyframe_insert("location", frame=2012)
    set_scale(permit, 1988, 0.0)
    set_scale(permit, 2012, 0.85)
    permit.location = send_target + Vector((0, 0, 0.012))
    permit.keyframe_insert("location", frame=2028)
    set_scale(permit, 2028, 0.85)
    set_scale(permit, 2040, 0.0)
    set_scale(tick, 2059, 0.0)
    set_scale(tick, 2060, 1.0)
    set_scale(tick, 2068, 0.0)

    sent = base.board_text(
        "Phone sent receipt", "on my way · sent ✓",
        base.board_point(ox + dev["configured_size"][0] / 2,
                         oy + dev["configured_size"][1] - 65, z),
        0.0040, mats["green"],
    )
    classify(sent, collection, "verified_phone_receipt")
    sent["presentation_only"] = True
    set_scale(sent, 1, 0.0)
    set_scale(sent, 2059, 0.0)
    set_scale(sent, 2060, 1.0)
    set_scale(sent, 2256, 1.0)
    return {
        "phrase": phrase, "messages_app_contact": app_contact,
        "contacts": contacts, "send_contact": 2028,
    }


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
    tick = base.board_text(
        "AUTH_COMPACT_VERIFICATION_TICK", "✓", e_target + Vector((0, 0, 0.012)),
        0.009, mats["green"],
    )
    classify(tick, collection, "compact_verification_tick")
    tick["meaning"] = "compact observed-effect confirmation after taught contact"
    set_scale(tick, 1, 0.0)
    set_scale(tick, 2400, 0.0)
    return {
        "uncertainty": uncertainty, "permit": permit,
        "ghost": ghost_root, "tick": tick,
    }


def build() -> bpy.types.Scene:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    layout = json.loads(base.LAYOUT_PATH.read_text(encoding="utf-8"))
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
    phone_ui = production_collection("TACTEVRA_PHONE_MESSAGE_SEQUENCE")

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
    # Preserve a readable dark phone surface under the brighter product-shot
    # lighting used by the v2.1 cameras. This affects presentation materials
    # only; the measured chassis and screen-plane dimensions stay unchanged.
    for key, base_color, roughness, metallic, emission_strength in (
        ("screen", (0.004, 0.010, 0.022, 1), 0.30, 0.06, 0.04),
        ("screen_glass", (0.003, 0.007, 0.014, 1), 0.24, 0.12, None),
        ("phone_panel", (0.010, 0.028, 0.048, 1), 0.32, 0.04, 0.28),
    ):
        bsdf = mats[key].node_tree.nodes.get("Principled BSDF")
        bsdf.inputs["Base Color"].default_value = base_color
        bsdf.inputs["Roughness"].default_value = roughness
        bsdf.inputs["Metallic"].default_value = metallic
        if emission_strength is not None:
            bsdf.inputs["Emission Strength"].default_value = emission_strength
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
    y_key = find_key("Y")
    y_xy_mm = (
        (y_key.location.x * 1000) + base.BOARD_CENTER_MM.x,
        (y_key.location.y * 1000) + base.BOARD_CENTER_MM.y,
    )
    phone_dev = layout["devices"]["phone"]
    phone_xy_mm = (
        phone_dev["nominal_origin_xy"][0] + phone_dev["configured_size"][0] / 2,
        phone_dev["nominal_origin_xy"][1] + phone_dev["configured_size"][1] / 2,
    )
    animate_keyboard_to_phone_crossing(controls, rig, y_xy_mm, phone_xy_mm)
    for graphic in graphics_objects.values():
        set_scale(graphic, 1320, 0.0)
        set_scale(graphic, 1608, 0.0)
    phone_targets, phone_ui_objects = add_phone_message_ui(
        layout, mats, phone_ui,
    )
    phone_sequence = animate_phone_message_sequence(
        controls, rig, phone_targets, graphics_objects, layout, mats, phone_ui,
    )
    scene["phone_phrase"] = phone_sequence["phrase"]
    scene["phone_contact_count"] = len(phone_sequence["contacts"]) + 2

    # The camera portal was established in the LOCATE chapter. Keep it out of
    # the phone beauty shots so it cannot obscure the real phone and stylus.
    portal = scene.objects.get("DESIGNED — printable camera portal")
    if portal is not None:
        portal.hide_render = True
        portal.keyframe_insert("hide_render", frame=1465)
        portal.keyframe_insert("hide_render", frame=1561)
        portal.keyframe_insert("hide_render", frame=2400)

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
    animate_camera(*rigs["arm_follow"], 1465, 1608,
                   Vector((0.18, -0.76, 0.53)), Vector((0.48, -0.48, 0.44)), phone_target)
    key_pose(rigs["arm_follow"][1], 1465, base.board_point(*y_xy_mm, 90))
    key_pose(rigs["arm_follow"][1], 1608, base.board_point(*phone_xy_mm, 90))
    animate_camera(*rigs["arm_follow"], 1609, 1968,
                   Vector((0.58, -0.34, 0.42)), Vector((0.62, 0.02, 0.36)),
                   base.board_point(*phone_xy_mm, 28))
    animate_camera(*rigs["macro"], 1969, 2088,
                   Vector((0.62, -0.28, 0.36)), Vector((0.56, -0.22, 0.30)),
                   base.board_point(*phone_xy_mm, 35))
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
                *phone_ui_objects, r_key, find_key("E"), find_key("A"),
                find_key("D"), find_key("Y")):
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
    if "--preview-crossing" in args:
        preview_frames += (1320, 1340, 1465, 1528, 1608)
    if "--preview-phone" in args:
        preview_frames += (1609, 1660, 1692, 1800, 1840, 1872, 1960, 1988, 2028, 2060, 2088)
    if preview_frames:
        for frame in preview_frames:
            scene.frame_set(frame)
            scene.camera = (
                bpy.data.objects["CAM_MACRO"] if frame <= 1152
                else bpy.data.objects["CAM_DOLLY"] if frame <= 1464
                else bpy.data.objects["CAM_ARM_FOLLOW"] if frame <= 1968
                else bpy.data.objects["CAM_MACRO"]
            )
            scene.render.filepath = str(OUT / f"storyboard_{frame:04d}.png")
            bpy.ops.render.render(write_still=True)
    print(f"TACTEVRA_STORYBOARD_V21={blend_path}")


if __name__ == "__main__":
    main()

"""Frozen larger A-B-A air-typing hypothesis from the measured P4 pose.

Offline geometry only. This module never opens a device or authorizes motion.
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path

from rocell.geometry import UrdfModel
from rocell.kinematics.firmware_reference import forward, inverse, REFERENCE_SHA256

from .first_motion_contract import canonical
from .large_pose_ladder import _sample


STEP_RAD = 2 * math.pi / 4096
SOURCE_POSITIONS = (2047, 2225, 1890, 2716, 1979, 2041, 2047)
SOURCE_GOALS = (2047, 2217, 1897, 2711, 1980, 2040, 2047)
# Controller-relative Y/Z offsets in mm. There is no physical keyboard frame.
WAYPOINTS = (
    ("LIFT_10", None, "approach", 0, 10),
    ("LIFT_20", None, "approach", 0, 20),
    ("LIFT_30", None, "approach", 0, 30),
    ("A_TRAVEL", "A", "travel", 0, 40),
    ("A_HOVER", "A", "hover", 0, 34),
    ("A_VIRTUAL_PRESS", "A", "virtual_downstroke", 0, 30),
    ("A_RETRACT", "A", "retract", 0, 40),
    ("AB_MID", None, "lateral_travel", 15, 40),
    ("B_TRAVEL", "B", "travel", 30, 40),
    ("B_HOVER", "B", "hover", 30, 34),
    ("B_VIRTUAL_PRESS", "B", "virtual_downstroke", 30, 30),
    ("B_RETRACT", "B", "retract", 30, 40),
    ("BA_MID", None, "lateral_travel", 15, 40),
    ("A_RETURN_TRAVEL", "A", "travel", 0, 40),
    ("A_RETURN_HOVER", "A", "hover", 0, 34),
    ("A_RETURN_PRESS", "A", "virtual_downstroke", 0, 30),
    ("A_RETURN_RETRACT", "A", "retract", 0, 40),
)


def _source_angles():
    p = SOURCE_POSITIONS
    return (-(p[0] - 2048) * STEP_RAD, (p[1] - 2048) * STEP_RAD,
            (p[3] - 1024) * STEP_RAD, (p[4] - 2048) * STEP_RAD,
            -(p[5] - 2048) * STEP_RAD)


def _goals(joints, source):
    db, ds, de, dw = (round((a - b) / STEP_RAD) for a, b in zip(joints[:4], source[:4]))
    g = list(SOURCE_GOALS)
    g[0] -= db
    g[1] += ds
    g[2] -= ds
    g[3] += de
    g[4] += dw
    return tuple(g)


def plan_air_typing(model_path):
    path = Path(model_path).resolve(strict=True)
    raw = path.read_bytes()
    model = UrdfModel.from_file(path)
    source = _source_angles()
    origin = forward(*source[:4])
    previous_pose, previous_goals = origin, SOURCE_GOALS
    rows = []
    overall_proxy, overall_tcp_z = math.inf, math.inf
    for index, (name, key, phase, y, z) in enumerate(WAYPOINTS, 1):
        target = (origin[0], origin[1] + y, origin[2] + z, origin[3])
        solved = (*inverse(*target), source[4])
        goals = _goals(solved, source)
        deltas = tuple(b - a for a, b in zip(previous_goals, goals))
        samples = max(1, math.ceil(math.dist(previous_pose[:3], target[:3]) / 2))
        min_proxy, min_tcp_z = math.inf, math.inf
        for sample_index in range(samples + 1):
            point = tuple(a + (b - a) * sample_index / samples
                          for a, b in zip(previous_pose, target))
            joints = (*inverse(*point), source[4])
            if not (-math.pi <= joints[0] <= math.pi and
                    -math.pi / 2 <= joints[1] <= math.pi / 2 and
                    0 <= joints[2] <= 2.95 and
                    -math.pi / 2 <= joints[3] <= math.pi / 2):
                raise ValueError(f"{name}: provisional joint limit")
            recovered = forward(*joints[:4])
            if math.dist(point[:3], recovered[:3]) > 1e-5 or abs(point[3] - recovered[3]) > 1e-8:
                raise ValueError(f"{name}: inverse roundtrip")
            points, proxy = _sample(model, joints)
            min_proxy = min(min_proxy, proxy)
            min_tcp_z = min(min_tcp_z, points["hand_tcp"][2])
        if max(abs(delta) for delta in deltas) > 80:
            raise ValueError(f"{name}: count step exceeds 80")
        if min_proxy < 30:
            raise ValueError(f"{name}: modeled link proxy below 30 mm")
        rows.append(dict(leg=index, name=name, key=key, phase=phase,
                         target_reference_xyz_pitch=list(target),
                         logical_joints_rad=list(solved), goals=list(goals),
                         goal_delta_counts=list(deltas), sample_count=samples + 1,
                         minimum_nonadjacent_proxy_distance_mm=min_proxy,
                         minimum_urdf_tcp_z_mm=min_tcp_z))
        overall_proxy = min(overall_proxy, min_proxy)
        overall_tcp_z = min(overall_tcp_z, min_tcp_z)
        previous_pose, previous_goals = target, goals
    report = dict(schema="rocell.local_air_typing_recipe.v1",
                  status="OFFLINE_RECIPE_PASS_NOT_EXECUTABLE",
                  source_positions=list(SOURCE_POSITIONS), source_goals=list(SOURCE_GOALS),
                  source_reference_xyz_pitch=list(origin), source_logical_joints_rad=list(source),
                  selected_speed_counts_per_second=20, selected_acceleration=1,
                  key_order=["A", "B", "A"], virtual_key_pitch_mm=30,
                  virtual_surface_offset_z_mm=30, virtual_stroke_mm=4,
                  maximum_per_leg_goal_delta_counts=80,
                  minimum_nonadjacent_proxy_distance_mm=overall_proxy,
                  minimum_urdf_tcp_z_mm=overall_tcp_z,
                  model_sha256=hashlib.sha256(raw).hexdigest(),
                  firmware_reference_sha256=REFERENCE_SHA256,
                  legs=rows, hardware_access=False, motion_authorized=False,
                  board_registered=False, installed_tool_offset_applied=False,
                  physical_clearance_verified=False, physical_accuracy_verified=False,
                  limitations=[
                      "Virtual keys are enlarged for visible noncontact movement, not real keyboard pitch.",
                      "Count-to-joint and URDF geometry are provisional; servo readback is not tip metrology.",
                      "The board, cables, enclosure and installed tool are absent from the sweep model.",
                      "No live controller interpolation or per-leg feedback has been tested for this recipe.",
                  ])
    return dict(report, report_sha256=hashlib.sha256(canonical(report)).hexdigest())

"""Offline P0-P4 RoArm pose ladder with swept kinematic proxy checks."""
from __future__ import annotations

import hashlib
import math
from pathlib import Path

from rocell.geometry import JointPosition, UrdfModel


STEP_RAD = 2 * math.pi / 4096
SOURCE_POSITIONS = (2047, 2415, 1700, 2904, 1591, 2041, 2047)
SOURCE_GOALS = (2047, 2413, 1701, 2907, 1589, 2040, 2047)
JOINT_NAMES = (
    "base_link_to_link1", "link1_to_link2", "link2_to_link3",
    "link3_to_link4", "link4_to_link5",
)
LINK_NAMES = ("link2", "link3", "link4", "link5", "hand_tcp")

# Deltas are logical base, shoulder, elbow, wrist-pitch, wrist-roll radians.
ROUTE = (
    ("P0", "verified_upper_reference", (0, 0, 0, 0, 0), True),
    ("T1", "lift_before_elbow_relief", (0, -0.1, 0, 0.1, 0), False),
    ("P1", "elevated_elbow_relief", (0, -0.1, -0.1, 0.2, 0), True),
    ("P2", "high_clearance_staging", (0, -0.2, -0.1, 0.3, 0), True),
    ("P3", "elevated_extension", (0, -0.2, -0.2, 0.4, 0), True),
    ("T4", "lift_before_larger_extension", (0, -0.3, -0.2, 0.5, 0), False),
    ("P4", "high_extended_pose", (0, -0.3, -0.3, 0.6, 0), True),
)


def _state(angles):
    result = {name: JointPosition.radians(value) for name, value in zip(JOINT_NAMES, angles)}
    result["link5_to_gripper_link"] = JointPosition.radians(1.0)
    return result


def _xyz(transform):
    point = transform.translation_mm
    return (point.x, point.y, point.z)


def _sub(a, b): return tuple(x-y for x, y in zip(a, b))
def _add(a, b): return tuple(x+y for x, y in zip(a, b))
def _mul(a, scale): return tuple(x*scale for x in a)
def _dot(a, b): return sum(x*y for x, y in zip(a, b))


def _segment_distance(p1, q1, p2, q2):
    """Shortest distance between two 3-D line segments."""
    u, v, w = _sub(q1, p1), _sub(q2, p2), _sub(p1, p2)
    a, b, c, d, e = _dot(u, u), _dot(u, v), _dot(v, v), _dot(u, w), _dot(v, w)
    denominator = a*c-b*b
    s_num, s_den = denominator, denominator
    t_num, t_den = denominator, denominator
    if denominator < 1e-12:
        s_num, s_den, t_num, t_den = 0.0, 1.0, e, c
    else:
        s_num, t_num = b*e-c*d, a*e-b*d
        if s_num < 0:
            s_num, t_num, t_den = 0.0, e, c
        elif s_num > s_den:
            s_num, t_num, t_den = s_den, e+b, c
    if t_num < 0:
        t_num = 0.0
        if -d < 0: s_num = 0.0
        elif -d > a: s_num = s_den
        else: s_num, s_den = -d, a
    elif t_num > t_den:
        t_num = t_den
        if -d+b < 0: s_num = 0.0
        elif -d+b > a: s_num = s_den
        else: s_num, s_den = -d+b, a
    sc = 0.0 if abs(s_num) < 1e-12 else s_num/s_den
    tc = 0.0 if abs(t_num) < 1e-12 else t_num/t_den
    delta = _sub(_add(w, _mul(u, sc)), _mul(v, tc))
    return math.sqrt(_dot(delta, delta))


def _source_angles():
    return (
        -(SOURCE_POSITIONS[0]-2048)*STEP_RAD,
        (SOURCE_POSITIONS[1]-2048)*STEP_RAD,
        (SOURCE_POSITIONS[3]-1024)*STEP_RAD,
        (SOURCE_POSITIONS[4]-2048)*STEP_RAD,
        -(SOURCE_POSITIONS[5]-2048)*STEP_RAD,
    )


def _command_goals(delta):
    counts = [int(round(value/STEP_RAD)) for value in delta]
    goals = list(SOURCE_GOALS)
    goals[0] -= counts[0]
    goals[1] += counts[1]; goals[2] -= counts[1]
    goals[3] += counts[2]; goals[4] += counts[3]; goals[5] -= counts[4]
    return goals


def _sample(model, angles):
    transforms = model.forward_kinematics(_state(angles))
    points = {name: _xyz(transforms[name]) for name in LINK_NAMES}
    segments = (
        (points["link2"], points["link3"]),
        (points["link3"], points["link4"]),
        (points["link4"], points["link5"]),
        (points["link5"], points["hand_tcp"]),
    )
    proxy_distance = min(
        _segment_distance(*segments[first], *segments[second])
        for first, second in ((0, 2), (0, 3), (1, 3))
    )
    return points, proxy_distance


def plan_large_pose_ladder(model_path):
    path = Path(model_path).resolve()
    raw = path.read_bytes()
    model = UrdfModel.from_file(path)
    source = _source_angles()
    poses = []
    angles_by_name = {}
    for name, purpose, delta, named in ROUTE:
        angles = tuple(source[index]+delta[index] for index in range(5))
        transforms, proxy_distance = _sample(model, angles)
        elbow_margin = min(angles[2]-(-1.0), 2.95-angles[2])
        poses.append({
            "name": name, "purpose": purpose, "named_pose": named,
            "logical_delta_rad": list(delta), "logical_angles_rad": list(angles),
            "command_goals": _command_goals(delta),
            "hand_tcp_world_mm": list(transforms["hand_tcp"]),
            "elbow_limit_margin_rad": elbow_margin,
            "minimum_nonadjacent_proxy_distance_mm": proxy_distance,
        })
        angles_by_name[name] = angles

    transitions = []
    for (source_row, target_row) in zip(poses, poses[1:]):
        start, end = angles_by_name[source_row["name"]], angles_by_name[target_row["name"]]
        minimum_tcp_z = math.inf
        minimum_proxy_distance = math.inf
        for step in range(101):
            fraction = step/100
            angles = tuple(start[j]+fraction*(end[j]-start[j]) for j in range(5))
            points, proxy_distance = _sample(model, angles)
            minimum_tcp_z = min(minimum_tcp_z, points["hand_tcp"][2])
            minimum_proxy_distance = min(minimum_proxy_distance, proxy_distance)
        delta = [end[j]-start[j] for j in range(5)]
        transitions.append({
            "source": source_row["name"], "target": target_row["name"],
            "maximum_joint_delta_rad": max(abs(value) for value in delta),
            "maximum_joint_delta_counts": max(abs(round(value/STEP_RAD)) for value in delta),
            "minimum_hand_tcp_world_z_mm": minimum_tcp_z,
            "minimum_nonadjacent_proxy_distance_mm": minimum_proxy_distance,
            "proxy_capsule_clearance_mm_at_15mm_radius": minimum_proxy_distance-30.0,
        })

    p0_z = poses[0]["hand_tcp_world_mm"][2]
    for pose in poses:
        pose["relative_tcp_height_gain_mm"] = pose["hand_tcp_world_mm"][2]-p0_z
    return {
        "schema": "rocell.large_pose_ladder.v1",
        "source_positions": list(SOURCE_POSITIONS), "source_goals": list(SOURCE_GOALS),
        "urdf_path": str(path), "urdf_sha256": hashlib.sha256(raw).hexdigest(),
        "poses": poses, "transitions": transitions,
        "assumptions": {
            "world_z_zero_used_as_unregistered_board_plane_proxy": True,
            "proxy_link_capsule_radius_mm": 15.0,
            "visual_collision_meshes_available": False,
            "cable_collision_modeled": False,
            "tool_attachment_modeled": False,
        },
        "release_sequence": ["P0", "T1", "P1", "P2", "P3", "T4", "P4"],
        "first_physical_candidate": "T1",
        "first_candidate_rationale": "raises_tcp_before_near_limit_elbow_is_relieved",
        "physical_clearance_verified": False,
        "movement_authorized": False,
        "cartesian_accuracy_verified": False,
    }

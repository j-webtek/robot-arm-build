"""Offline, pose-relative ghost keys; never a live motion request."""
from __future__ import annotations

import hashlib
import math
from pathlib import Path

from rocell.geometry import UrdfModel
from rocell.kinematics.firmware_reference import REFERENCE_SHA256, forward, inverse

from .first_motion_contract import canonical
from .large_pose_ladder import _sample


STEP_RAD = 2 * math.pi / 4096
EXPECTED_SOURCE = (2047, 2225, 1890, 2716, 1979, 2041, 2047)
KEY_ORDER = ("A", "B", "A")


def preview_local_p4_ghost(positions, model_path):
    """Screen a 10-mm-pitch virtual row 30 mm above the reported P4 end edge.

    Source counts and the model are explicit. The virtual surface is not a
    physical board transform, and this function emits no controller commands.
    """
    if type(positions) not in (tuple, list) or tuple(positions) != EXPECTED_SOURCE:
        raise ValueError("Exact independently verified P4 source required")
    path = Path(model_path).resolve(strict=True)
    model_bytes = path.read_bytes()
    model = UrdfModel.from_file(path)
    base = -(positions[0] - 2048) * STEP_RAD
    shoulder = (positions[1] - 2048) * STEP_RAD
    elbow = (positions[3] - 1024) * STEP_RAD
    wrist = (positions[4] - 2048) * STEP_RAD
    roll = -(positions[5] - 2048) * STEP_RAD
    start_joints = (base, shoulder, elbow, wrist, roll)
    source = forward(*start_joints[:4])
    # Separate local rehearsal from the fixed full-size nominal keyboard.
    # Each virtual key has a 4-mm stroke, with a 4-mm hover and 10-mm travel.
    targets = []
    for key in KEY_ORDER:
        offset_y = 0 if key == "A" else 10
        for phase, height in (("travel", 40), ("hover", 34),
                              ("virtual_downstroke", 30), ("retract", 40)):
            targets.append((key, phase, (source[0], source[1] + offset_y,
                                          source[2] + height, source[3])))
    current = source
    legs = []
    minimum_proxy = math.inf
    minimum_tcp_z = math.inf
    maximum_joint_step = 0.0
    previous_joint = start_joints
    bounds = ((-math.pi, math.pi), (-math.pi / 2, math.pi / 2),
              (0, 2.95), (-math.pi / 2, math.pi / 2), (-math.pi, math.pi))
    for index, (key, phase, target) in enumerate(targets):
        count = max(1, math.ceil(math.dist(current[:3], target[:3]) / 2))
        leg_min_proxy = math.inf
        leg_min_z = math.inf
        leg_max_step = 0.0
        status = "REFERENCE_SWEEP_PASS"
        for sample_index in range(1, count + 1):
            point = tuple(a + (b - a) * sample_index / count
                          for a, b in zip(current, target))
            try:
                joint = (*inverse(*point), roll)
                if not all(lo <= value <= hi for value, (lo, hi) in zip(joint, bounds)):
                    status = "PROVISIONAL_JOINT_LIMIT_REJECTED"
                    break
                reconstructed = forward(*joint[:4])
                if math.dist(point[:3], reconstructed[:3]) > 1e-5 or abs(point[3] - reconstructed[3]) > 1e-8:
                    status = "REFERENCE_ROUNDTRIP_REJECTED"
                    break
                points, proxy = _sample(model, joint)
                step = max(abs(a - b) for a, b in zip(joint, previous_joint))
            except (ValueError, OverflowError):
                status = "REFERENCE_IK_REJECTED"
                break
            leg_min_proxy = min(leg_min_proxy, proxy)
            leg_min_z = min(leg_min_z, points["hand_tcp"][2])
            leg_max_step = max(leg_max_step, step)
            previous_joint = joint
        legs.append(dict(sequence=index, key=key, phase=phase,
                         start=list(current), target=list(target),
                         interpolated_samples=count, status=status,
                         minimum_nonadjacent_proxy_distance_mm=None if math.isinf(leg_min_proxy) else leg_min_proxy,
                         minimum_urdf_tcp_z_mm=None if math.isinf(leg_min_z) else leg_min_z,
                         maximum_adjacent_joint_step_rad=leg_max_step))
        if status != "REFERENCE_SWEEP_PASS":
            break
        minimum_proxy = min(minimum_proxy, leg_min_proxy)
        minimum_tcp_z = min(minimum_tcp_z, leg_min_z)
        maximum_joint_step = max(maximum_joint_step, leg_max_step)
        current = target
    passed = len(legs) == len(targets) and all(row["status"] == "REFERENCE_SWEEP_PASS" for row in legs)
    report = dict(schema="rocell.local_p4_ghost_preview.v1",
                  status="OFFLINE_REFERENCE_PASS_NOT_EXECUTABLE" if passed else "OFFLINE_REFERENCE_REJECTED",
                  source_positions=list(positions), source_reference_xyz_pitch=list(source),
                  source_logical_joints_rad=list(start_joints),
                  source_to_first_travel_mm=40, key_order=list(KEY_ORDER),
                  local_pitch_mm=10, virtual_surface_offset_z_mm=30,
                  virtual_stroke_mm=4, travel_above_surface_mm=10,
                  hover_above_surface_mm=4, legs=legs,
                  minimum_nonadjacent_proxy_distance_mm=None if math.isinf(minimum_proxy) else minimum_proxy,
                  minimum_urdf_tcp_z_mm=None if math.isinf(minimum_tcp_z) else minimum_tcp_z,
                  maximum_adjacent_joint_step_rad=maximum_joint_step,
                  model_sha256=hashlib.sha256(model_bytes).hexdigest(),
                  firmware_reference_sha256=REFERENCE_SHA256,
                  hardware_access=False, motion_authorized=False,
                  physical_clearance_verified=False, physical_accuracy_verified=False,
                  installed_stylus_offset_applied=False,
                  limitations=["The count-to-joint correspondence is provisional; servo feedback is not independent tip metrology.",
                               "The virtual surface is offset from a modeled end edge, not registered to the board.",
                               "URDF link proxies omit cable, enclosure, tool, bench, and measured obstacles.",
                               "Sampled reference interpolation is not the installed controller trajectory."])
    return dict(report, report_sha256=hashlib.sha256(canonical(report)).hexdigest())

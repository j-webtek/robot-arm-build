"""Offline screen for one high-clear lateral registration-ladder leg.

The target is deliberately controller-relative.  It is intended to create one
observable landmark from the verified r95 endpoint, not to claim a key center
or establish a board transform by itself.
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path

from rocell.geometry import UrdfModel
from rocell.kinematics.firmware_reference import forward

from .air_typing_continuation_preview import _angles
from .bare_gripper_hover_preview import _sample


SOURCE_EXPORT = "wizard-20260925T184552652527Z-43a68b4aa26347deb4bc89f9d087eb74"
SOURCE_BOOT = "818844fc46074ad9e965c8a4e61f33ee"
SOURCE_POSITIONS = (2041, 2081, 2033, 2609, 2233, 2041, 1900)
SOURCE_GOALS = (2047, 2075, 2039, 2600, 2233, 2040, 1897)
TARGET_GOALS = (2107, 2075, 2039, 2600, 2233, 2040, 1897)


def preview(model_path: Path) -> dict:
    path = Path(model_path).resolve(strict=True)
    model = UrdfModel.from_file(path)
    selected = [index for index, (before, after) in
                enumerate(zip(SOURCE_GOALS, TARGET_GOALS)) if before != after]
    if selected != [0] or TARGET_GOALS[6] != SOURCE_GOALS[6]:
        raise ValueError("Registration leg must remain base-only")
    step_counts = abs(TARGET_GOALS[0] - SOURCE_GOALS[0])
    if step_counts != 60:
        raise ValueError("Registration base step differs")
    minimum_z = minimum_proxy = math.inf
    for step in range(101):
        fraction = step / 100
        counts = tuple(a + fraction * (b-a)
                       for a, b in zip(SOURCE_POSITIONS, TARGET_GOALS))
        angles = _angles(counts)
        points, proxy = _sample(model, angles)
        minimum_z = min(minimum_z, points["hand_tcp"][2])
        minimum_proxy = min(minimum_proxy, proxy)
    source_xyz = forward(*_angles(SOURCE_GOALS)[:4])[:3]
    target_xyz = forward(*_angles(TARGET_GOALS)[:4])[:3]
    displacement = math.dist(source_xyz, target_xyz)
    if minimum_z < 40 or minimum_proxy < 30 or not 16 < displacement < 19:
        raise ValueError("Registration leg model screen failed")
    return dict(schema="rocell.registration_ladder_preview.v1",
                status="OFFLINE_ONE_LEG_PASS_NOT_EXECUTABLE",
                source_export=SOURCE_EXPORT, source_boot=SOURCE_BOOT,
                source_positions=list(SOURCE_POSITIONS),
                source_goals=list(SOURCE_GOALS), target_goals=list(TARGET_GOALS),
                selected_joints=selected, maximum_writes=1,
                base_step_counts=step_counts,
                pinned_firmware_reference_displacement_mm=round(displacement, 3),
                minimum_modeled_tcp_z_mm=round(minimum_z, 3),
                minimum_modeled_link_axis_separation_mm=round(minimum_proxy, 3),
                model_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                startup_motion=False, gripper_writes=False,
                automatic_progression=False, retry_allowed=False,
                return_movement=False, hardware_access=False,
                physical_landmark_observed=False,
                board_to_controller_verified=False, motion_authorized=False,
                caveat=("Meshless/model-only screen omits keyboard, gripper volume, "
                        "cables and fixtures; the target is not a physical key."))

"""Offline count-space sweep from captured post-fault pose; never commands hardware."""
from __future__ import annotations

import hashlib
import math
from pathlib import Path

from rocell.geometry import UrdfModel

from .air_typing_campaign import TARGETS
from .large_pose_ladder import STEP_RAD, _sample


CAPTURED_SOURCE_GOALS = (1941, 2080, 2034, 2591, 2236, 2040, 2047)
CAPTURED_SOURCE_POSITIONS = (1949, 2082, 2033, 2600, 2235, 2041, 2047)


def _angles(counts):
    return (-(counts[0] - 2048) * STEP_RAD,
            (counts[1] - 2048) * STEP_RAD,
            (counts[3] - 1024) * STEP_RAD,
            (counts[4] - 2048) * STEP_RAD,
            -(counts[5] - 2048) * STEP_RAD)


def preview(model_path: Path) -> dict:
    path = Path(model_path).resolve(strict=True)
    model = UrdfModel.from_file(path)
    previous = CAPTURED_SOURCE_POSITIONS
    previous_goals = CAPTURED_SOURCE_GOALS
    legs = []
    for ordinal in range(10, 18):
        target = TARGETS[ordinal - 1]
        if max(abs(a-b) for a, b in zip(previous_goals, target)) > 80:
            raise ValueError("Continuation step exceeds count bound")
        minimum_z = minimum_proxy = math.inf
        for step in range(101):
            fraction = step / 100
            counts = tuple(a + fraction * (b-a) for a, b in zip(previous, target))
            angles = _angles(counts)
            if not (-math.pi <= angles[0] <= math.pi
                    and -math.pi/2 <= angles[1] <= math.pi/2
                    and 0 <= angles[2] <= 2.95
                    and -math.pi/2 <= angles[3] <= math.pi/2):
                raise ValueError("Provisional joint limit")
            points, proxy = _sample(model, angles)
            minimum_z = min(minimum_z, points["hand_tcp"][2])
            minimum_proxy = min(minimum_proxy, proxy)
        if minimum_proxy < 30:
            raise ValueError("Modeled self-separation below screen")
        legs.append(dict(original_leg=ordinal, goals=list(target),
                         maximum_goal_step_counts=max(abs(a-b) for a, b in zip(previous_goals, target)),
                         minimum_modeled_tcp_z_mm=minimum_z,
                         minimum_modeled_link_axis_separation_mm=minimum_proxy))
        previous = target
        previous_goals = target
    return dict(status="OFFLINE_CONTINUATION_SWEEP_PASS_NOT_EXECUTABLE",
                model_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                source_goals=list(CAPTURED_SOURCE_GOALS),
                source_positions=list(CAPTURED_SOURCE_POSITIONS),
                legs=legs, hardware_access=False, motion_authorized=False,
                physical_clearance_verified=False, physical_accuracy_verified=False,
                caveat="Count interpolation and meshless URDF omit servo dynamics, cables, installed tool and board registration.")

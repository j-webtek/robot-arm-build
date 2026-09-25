"""Offline-only candidate for A_HOVER recovery plus one ghost A cycle.

No command encoding, transport, controller admission, or physical authority.
The model omits the board, cables, tool and mounting tolerances.
"""

from __future__ import annotations

import hashlib
import math
from pathlib import Path

from rocell.geometry import UrdfModel

from .air_typing_continuation_preview import _angles
from .ghost_key_multitarget_recipe import A_DOWN, A_HOVER, A_RETRACT
from .large_pose_ladder import _sample


SOURCE_GOALS = A_HOVER
LAST_RECORDED_POSITIONS = (2041, 2094, 2020, 2620, 2199, 2041, 2047)
TARGETS = (A_RETRACT, A_HOVER, A_DOWN, A_HOVER, A_RETRACT)
NAMES = ("A_CLEAR", "A_HOVER", "A_DOWN", "A_HOVER", "A_CLEAR")
SPEED = 20
ACCELERATION = 1


def validate_recipe() -> bool:
    if (SOURCE_GOALS != (2047, 2093, 2021, 2618, 2197, 2040, 2047)
            or len(TARGETS) != 5 or len(NAMES) != 5
            or SPEED != 20 or ACCELERATION != 1):
        raise ValueError("Pinned recovery recipe differs")
    previous = SOURCE_GOALS
    for target in TARGETS:
        deltas = [b - a for a, b in zip(previous, target)]
        if (len(target) != 7 or not all(0 <= value <= 4095 for value in target)
                or not any(deltas) or any(not 10 <= abs(delta) <= 60
                                          for delta in deltas if delta)):
            raise ValueError("Unreviewed recovery displacement")
        previous = target
    return True


def preview(model_path: Path) -> dict:
    validate_recipe()
    path = Path(model_path).resolve(strict=True)
    model = UrdfModel.from_file(path)
    previous = LAST_RECORDED_POSITIONS
    rows = []
    for leg, (name, target) in enumerate(zip(NAMES, TARGETS), 1):
        min_z = min_proxy = math.inf
        for step in range(101):
            fraction = step / 100
            counts = tuple(a + fraction * (b - a)
                           for a, b in zip(previous, target))
            angles = _angles(counts)
            points, proxy = _sample(model, angles)
            min_z = min(min_z, points["hand_tcp"][2])
            min_proxy = min(min_proxy, proxy)
        if min_z < 40 or min_proxy < 30:
            raise ValueError(f"Modeled recovery clearance failed at leg {leg}")
        rows.append(dict(leg=leg, pose=name, target_goals=list(target),
                         minimum_modeled_tcp_z_mm=min_z,
                         minimum_modeled_link_axis_separation_mm=min_proxy))
        previous = target
    return dict(schema="rocell.reviewed_hover_recovery_preview.v1",
                status="OFFLINE_MODEL_SCREEN_PASS_NOT_EXECUTABLE",
                model_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                source_goals=list(SOURCE_GOALS),
                last_recorded_positions=list(LAST_RECORDED_POSITIONS),
                speed=SPEED, acceleration=ACCELERATION, legs=rows,
                hardware_access=False, motion_authorized=False,
                fresh_pose_verified=False, physical_clearance_verified=False)

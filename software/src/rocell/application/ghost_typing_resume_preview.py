"""Offline B-key ghost-cycle screen from the last verified gripper-close pose.

The mounted stylus is not retained/characterized. This preview cannot authorize
physical motion or establish clearance for that stylus or the real keyboard.
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path

from rocell.geometry import UrdfModel

from .air_typing_continuation_preview import _angles
from .ghost_key_multitarget_recipe import (B_RETRACT as NOMINAL_B_CLEAR,
                                            B_HOVER as NOMINAL_B_HOVER,
                                            B_DOWN as NOMINAL_B_DOWN)
from .large_pose_ladder import _sample
from .product_ghost_export_review import _read

SOURCE_EXPORT = "wizard-20260925T151952399567Z-d7b974de5ca7444bbcdd273ced8c40cc"
SOURCE_POSITIONS = (2046, 2079, 2036, 2605, 2235, 2041, 1893)
SOURCE_GOALS = (2047, 2075, 2039, 2600, 2233, 2040, 1897)
B_CLEAR = (*NOMINAL_B_CLEAR[:6], SOURCE_GOALS[6])
B_HOVER = (*NOMINAL_B_HOVER[:6], SOURCE_GOALS[6])
B_DOWN = (*NOMINAL_B_DOWN[:6], SOURCE_GOALS[6])
TARGETS = (B_CLEAR, B_HOVER, B_DOWN, B_HOVER, B_CLEAR)
PHASES = ("B_CLEAR", "B_HOVER", "B_VIRTUAL_DOWN", "B_RETRACT", "B_CLEAR_FINAL")


def review_source(export_root: Path) -> str:
    row, digest = _read(Path(export_root).resolve(), SOURCE_EXPORT,
                        "attachment-gripper-close-step1.json")
    if (row.get("category") != "CLOSE_STEP_VERIFIED" or
            row.get("grip_retention_verified") is not False or
            row.get("after") != dict(positions=list(SOURCE_POSITIONS),
                                     goals=list(SOURCE_GOALS))):
        raise ValueError("Verified close-step source differs")
    return digest


def preview(model_path: Path, export_root: Path) -> dict:
    source_digest = review_source(export_root)
    path = Path(model_path).resolve(strict=True)
    model = UrdfModel.from_file(path)
    previous = SOURCE_POSITIONS
    goals = SOURCE_GOALS
    rows = []
    for leg, (phase, target) in enumerate(zip(PHASES, TARGETS), 1):
        selected = [index for index in range(7) if target[index] != goals[index]]
        if (not selected or 6 in selected or
                max(abs(target[index] - goals[index]) for index in selected) > 60):
            raise ValueError(f"Unreviewed B-key leg {leg}")
        min_z = min_proxy = math.inf
        for step in range(101):
            fraction = step / 100
            counts = tuple(a + fraction * (b - a) for a, b in zip(previous, target))
            angles = _angles(counts)
            if not (-math.pi <= angles[0] <= math.pi and
                    -math.pi / 2 <= angles[1] <= math.pi / 2 and
                    0 <= angles[2] <= 2.95 and
                    -math.pi / 2 <= angles[3] <= math.pi / 2):
                raise ValueError(f"Provisional joint bound on leg {leg}")
            points, proxy = _sample(model, angles)
            min_z = min(min_z, points["hand_tcp"][2])
            min_proxy = min(min_proxy, proxy)
        if min_z < 40 or min_proxy < 30:
            raise ValueError(f"Modeled clearance screen failed on leg {leg}")
        rows.append(dict(leg=leg, phase=phase, goals=list(target),
                         selected_joints=selected,
                         maximum_goal_step_counts=max(abs(a - b) for a, b in zip(goals, target)),
                         minimum_modeled_tcp_z_mm=min_z,
                         minimum_modeled_link_axis_separation_mm=min_proxy))
        previous = target
        goals = target
    return dict(schema="rocell.ghost_typing_resume_preview.v1",
                status="OFFLINE_B_CYCLE_SWEEP_PASS_NOT_EXECUTABLE",
                source_export=SOURCE_EXPORT, source_digest=source_digest,
                source_positions=list(SOURCE_POSITIONS), source_goals=list(SOURCE_GOALS),
                model_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                legs=rows, maximum_writes=5, hardware_access=False,
                motion_authorized=False, stylus_retention_verified=False,
                stylus_geometry_measured=False, keyboard_registered=False,
                physical_clearance_verified=False,
                caveat="Meshless arm-only screen; mounted stylus, keyboard, cables and fixtures omitted.")

"""Offline, manually gated two-region bare-gripper hover candidate.

These inherited servo-count poses are NOT registered to physical key centers.
The next live trial, if separately reviewed, must stop after each attended leg.
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path

from rocell.geometry import UrdfModel

from .air_typing_continuation_preview import _angles
from .ghost_key_multitarget_recipe import A_HOVER as NOMINAL_A_HOVER
from .ghost_typing_resume_preview import B_HOVER as NOMINAL_B_HOVER
from .large_pose_ladder import _sample
from .product_ghost_export_review import _read

SOURCE_EXPORT = "wizard-20260925T165306016823Z-d79a8b491ee847888bc0d52e1a07899d"
SOURCE_BOOT = "e39ad70582b67cec3b0f846b9d3f0486"
SOURCE_POSITIONS = (2001, 2082, 2033, 2609, 2233, 2041, 1900)
SOURCE_GOALS = (1994, 2075, 2039, 2600, 2233, 2040, 1897)
B_HOVER = NOMINAL_B_HOVER
B_CLEAR = SOURCE_GOALS
A_CLEAR = (2047, *SOURCE_GOALS[1:])
A_HOVER = (NOMINAL_A_HOVER[0], *NOMINAL_A_HOVER[1:6], SOURCE_GOALS[6])
PHASES = ("REGION_B_HOVER", "REGION_B_CLEAR", "REGION_A_CLEAR",
          "REGION_A_HOVER", "REGION_A_CLEAR_FINAL")
TARGETS = (B_HOVER, B_CLEAR, A_CLEAR, A_HOVER, A_CLEAR)


def review_source(export_root: Path) -> str:
    row, digest = _read(Path(export_root).resolve(), SOURCE_EXPORT,
                        "attachment-ghost-b-leg.json")
    if (row.get("category") != "LEG_VERIFIED" or row.get("leg") != 5 or
            row.get("boot_id") != SOURCE_BOOT or
            row.get("after") != dict(positions=list(SOURCE_POSITIONS),
                                     goals=list(SOURCE_GOALS))):
        raise ValueError("Verified r94 final source differs")
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
                any(type(value) is not int or not 0 <= value <= 4095 for value in target) or
                max(abs(target[index] - goals[index]) for index in selected) > 60):
            raise ValueError(f"Unreviewed hover leg {leg}")
        minimum_z = minimum_proxy = math.inf
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
            minimum_z = min(minimum_z, points["hand_tcp"][2])
            minimum_proxy = min(minimum_proxy, proxy)
        if minimum_z < 40 or minimum_proxy < 30:
            raise ValueError(f"Modeled clearance screen failed on leg {leg}")
        rows.append(dict(leg=leg, phase=phase, goals=list(target),
                         selected_joints=selected,
                         maximum_goal_step_counts=max(abs(target[i] - goals[i])
                                                      for i in selected),
                         minimum_modeled_tcp_z_mm=minimum_z,
                         minimum_modeled_link_axis_separation_mm=minimum_proxy))
        previous, goals = target, target
    return dict(schema="rocell.bare_gripper_hover_preview.v1",
                status="OFFLINE_TWO_REGION_HOVER_PASS_NOT_EXECUTABLE",
                source_export=SOURCE_EXPORT, source_digest=source_digest,
                source_positions=list(SOURCE_POSITIONS), source_goals=list(SOURCE_GOALS),
                model_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                legs=rows, maximum_writes=5, hardware_access=False,
                motion_authorized=False, key_centers_registered_to_controller=False,
                bare_gripper_envelope_measured=False, physical_clearance_verified=False,
                caveat=("Prior controller-relative regions are not physical key centers. "
                        "Meshless model omits gripper volume, keyboard, cables and fixtures."))

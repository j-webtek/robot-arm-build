"""Offline-only A/B virtual-key cycle seeded by the verified r84 endpoint.

These are controller-relative, noncontact targets. No physical keyboard frame,
stylus geometry, or actuation authority is encoded here.
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path

from rocell.geometry import UrdfModel

from .air_typing_continuation_preview import _angles
from .air_typing_r84_review import EXPORTS as R84_EXPORTS
from .large_pose_ladder import _sample
from .product_ghost_export_review import _read


SOURCE_GOALS = (2047,2075,2039,2600,2233,2040,2047)
SOURCE_POSITIONS = (2040,2082,2033,2609,2233,2041,2047)
A_HOVER = (2047,2093,2021,2618,2197,2040,2047)
A_DOWN = (2047,2105,2009,2630,2173,2040,2047)
A_RETRACT = SOURCE_GOALS
B_HOVER = (1994,2093,2021,2618,2197,2040,2047)
B_DOWN = (1994,2105,2009,2630,2173,2040,2047)
B_RETRACT = (1994,2075,2039,2600,2233,2040,2047)
ONE_CYCLE = (A_HOVER,A_DOWN,A_HOVER,A_RETRACT,
             B_HOVER,B_DOWN,B_HOVER,B_RETRACT)
TARGETS = ONE_CYCLE * 2
PHASES = tuple(f"{name}_{cycle}" for cycle in (1,2) for name in (
    "A_hover","A_virtual_downstroke","A_retract_hover","A_clear",
    "B_hover","B_virtual_downstroke","B_retract_hover","B_clear"))


def review_source(export_root):
    row,digest = _read(Path(export_root).resolve(),R84_EXPORTS[-1],
                       "attachment-multi-hover-assessment.json")
    if (row.get("status") != "MULTI_HOVER_LEG_ENDPOINT_VERIFIED"
            or row.get("source_kind") != "controller_feedback"
            or row.get("leg") != 5
            or row.get("final_goals") != list(SOURCE_GOALS)
            or row.get("final_positions") != list(SOURCE_POSITIONS)):
        raise ValueError("Retained r84 source differs")
    return digest


def validate_recipe():
    if len(TARGETS) != 16 or len(PHASES) != 16 or TARGETS[:8] != TARGETS[8:]:
        raise ValueError("Fixed two-cycle ghost-key recipe differs")
    prior = SOURCE_GOALS
    for leg,target in enumerate(TARGETS,1):
        selected = [i for i in range(7) if target[i] != prior[i]]
        if (not selected or any(type(value) is not int or not 0 <= value <= 4095 for value in target)
                or max(abs(target[i]-prior[i]) for i in selected) > 60
                or min(abs(target[i]-prior[i]) for i in selected) < 10):
            raise ValueError(f"Unreviewed ghost-key step {leg}")
        prior = target
    return True


def preview(model_path):
    validate_recipe()
    path = Path(model_path).resolve(strict=True)
    model = UrdfModel.from_file(path)
    previous = SOURCE_POSITIONS
    goals = SOURCE_GOALS
    rows = []
    for leg,target in enumerate(TARGETS,1):
        min_z = min_proxy = math.inf
        for step in range(101):
            fraction = step/100
            counts = tuple(a+fraction*(b-a) for a,b in zip(previous,target))
            angles = _angles(counts)
            if not (-math.pi <= angles[0] <= math.pi and
                    -math.pi/2 <= angles[1] <= math.pi/2 and
                    0 <= angles[2] <= 2.95 and
                    -math.pi/2 <= angles[3] <= math.pi/2):
                raise ValueError("Provisional joint bound")
            points,proxy = _sample(model,angles)
            min_z = min(min_z,points["hand_tcp"][2])
            min_proxy = min(min_proxy,proxy)
        if min_z < 40 or min_proxy < 30:
            raise ValueError(f"Modeled clearance screen failed on leg {leg}")
        selected = [i for i in range(7) if target[i] != goals[i]]
        rows.append(dict(leg=leg,phase=PHASES[leg-1],goals=list(target),
                         selected_joints=selected,
                         maximum_goal_step_counts=max(abs(a-b) for a,b in zip(goals,target)),
                         minimum_modeled_tcp_z_mm=min_z,
                         minimum_modeled_link_axis_separation_mm=min_proxy))
        previous = target
        goals = target
    return dict(schema="rocell.ghost_key_multitarget_preview.v1",
                status="OFFLINE_GHOST_KEY_SWEEP_PASS_NOT_EXECUTABLE",
                source_goals=list(SOURCE_GOALS),source_positions=list(SOURCE_POSITIONS),
                model_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),legs=rows,
                maximum_writes=16,one_use_per_boot=True,export_each_leg_required=True,
                speed_counts_per_second=20,acceleration=1,
                key_order=["A","B","A","B"],
                hardware_access=False,motion_authorized=False,
                board_registered=False,stylus_mounted=False,
                physical_clearance_verified=False,physical_accuracy_verified=False,
                caveat="Virtual downstroke is a raised noncontact pose; board/tool/cables omitted from meshless model.")

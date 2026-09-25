"""Fixed six-leg, two-cycle A hover/downstroke/retract experiment; offline only."""
from __future__ import annotations

import hashlib
import math
from pathlib import Path

from rocell.geometry import UrdfModel

from .air_typing_continuation_preview import _angles
from .air_typing_cycle_review import R78_EXPORTS
from .large_pose_ladder import _sample
from .product_ghost_export_review import _read


SOURCE_GOALS=(2047,2075,2039,2600,2233,2040,2047)
SOURCE_POSITIONS=(2041,2081,2033,2609,2233,2041,2047)
HOVER=(2047,2093,2021,2618,2197,2040,2047)
DOWN=(2047,2105,2009,2630,2173,2040,2047)
RETRACT=SOURCE_GOALS
TARGETS=(HOVER,DOWN,RETRACT,HOVER,DOWN,RETRACT)
PHASES=("A_hover_1","A_virtual_downstroke_1","A_retract_1",
        "A_hover_2","A_virtual_downstroke_2","A_retract_2")


def review_source(export_root):
    root=Path(export_root).resolve()
    row,digest=_read(root,R78_EXPORTS[-1],"attachment-air-typing-last-assessment.json")
    if (row.get("status")!="A_SIDE_LEG_ENDPOINT_VERIFIED" or row.get("leg")!=4
            or row.get("source_kind")!="controller_feedback"
            or row.get("final_goals")!=list(SOURCE_GOALS)
            or row.get("final_positions")!=list(SOURCE_POSITIONS)
            or row.get("physical_accuracy_verified") is not False):
        raise ValueError("Retained r78 A retract source differs")
    return digest


def validate_recipe():
    if (len(TARGETS)!=6 or len(PHASES)!=6 or TARGETS[2]!=RETRACT
            or TARGETS[5]!=RETRACT or TARGETS[:3]!=TARGETS[3:]):
        raise ValueError("Fixed two-cycle recipe differs")
    prior=SOURCE_GOALS
    for target in TARGETS:
        if (len(target)!=7 or any(type(value) is not int or not 0<=value<=4095
                                 for value in target)
                or max(abs(a-b) for a,b in zip(prior,target))>80):
            raise ValueError("Unreviewed target or step")
        prior=target
    return True


def preview(model_path:Path):
    validate_recipe()
    path=Path(model_path).resolve(strict=True)
    model=UrdfModel.from_file(path)
    previous=SOURCE_POSITIONS;previous_goals=SOURCE_GOALS
    rows=[]
    for leg,target in enumerate(TARGETS,1):
        min_z=min_proxy=math.inf
        for step in range(101):
            fraction=step/100
            counts=tuple(a+fraction*(b-a) for a,b in zip(previous,target))
            angles=_angles(counts)
            if not (-math.pi<=angles[0]<=math.pi and -math.pi/2<=angles[1]<=math.pi/2
                    and 0<=angles[2]<=2.95 and -math.pi/2<=angles[3]<=math.pi/2):
                raise ValueError("Provisional joint bound")
            points,proxy=_sample(model,angles)
            min_z=min(min_z,points["hand_tcp"][2]);min_proxy=min(min_proxy,proxy)
        if min_proxy<30 or min_z<40:
            raise ValueError("Modeled clearance screen failed")
        rows.append(dict(leg=leg,phase=PHASES[leg-1],goals=list(target),
                         maximum_goal_step_counts=max(abs(a-b) for a,b in zip(previous_goals,target)),
                         minimum_modeled_tcp_z_mm=min_z,
                         minimum_modeled_link_axis_separation_mm=min_proxy))
        previous=target;previous_goals=target
    return dict(schema="rocell.air_typing_repeat_preview.v1",
                status="OFFLINE_REPEAT_SWEEP_PASS_NOT_EXECUTABLE",
                source_goals=list(SOURCE_GOALS),source_positions=list(SOURCE_POSITIONS),
                model_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),legs=rows,
                maximum_writes=6,one_use_per_boot=True,export_each_leg_required=True,
                hardware_access=False,motion_authorized=False,
                physical_clearance_verified=False,physical_accuracy_verified=False,
                caveat="Unregistered meshless URDF/count interpolation omits cables, tool, board and servo dynamics.")

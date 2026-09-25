"""Fixed 16-leg two-goal elbow grid for held-out noncontact prediction."""
from __future__ import annotations

import hashlib
import math
from pathlib import Path

from rocell.geometry import UrdfModel

from .air_typing_continuation_preview import _angles
from .air_typing_r82_review import EXPORTS as R82_EXPORTS
from .large_pose_ladder import _sample
from .product_ghost_export_review import _read


SOURCE_GOALS=(2047,2075,2039,2610,2233,2040,2047)
SOURCE_POSITIONS=(2041,2082,2033,2619,2233,2041,2047)


def elbow(value):
    return (2047,2075,2039,value,2233,2040,2047)


# First four legs observe 2590 from either side. Next four observe 2620.
# Repeat both without changing speed, load, or passive joint goals.
COUNTS=(2560,2590,2620,2590,2650,2620,2590,2620,
        2560,2590,2620,2590,2650,2620,2590,2620)
TARGETS=tuple(elbow(value) for value in COUNTS)
PHASES=("low_2590_1","2590_from_low_1","high_2590_1","2590_from_high_1",
        "high_2620_1","2620_from_high_1","low_2620_1","2620_from_low_1",
        "low_2590_2","2590_from_low_2","high_2590_2","2590_from_high_2",
        "high_2620_2","2620_from_high_2","low_2620_2","2620_from_low_2")


def review_source(export_root):
    row,digest=_read(Path(export_root).resolve(),R82_EXPORTS[-1],
                     "attachment-elbow-shift-assessment.json")
    if (row.get("status")!="ELBOW_SHIFT_LEG_ENDPOINT_VERIFIED"
            or row.get("source_kind")!="controller_feedback" or row.get("leg")!=8
            or row.get("final_goals")!=list(SOURCE_GOALS)
            or row.get("final_positions")!=list(SOURCE_POSITIONS)):
        raise ValueError("Retained r82 source differs")
    return digest


def validate_recipe():
    if (len(TARGETS)!=16 or len(PHASES)!=16
            or TARGETS!=tuple(elbow(value) for value in COUNTS)
            or COUNTS[:8]!=COUNTS[8:]
            or any(tuple(target[i] for i in (0,1,2,4,5,6))!=
                   tuple(SOURCE_GOALS[i] for i in (0,1,2,4,5,6)) for target in TARGETS)):
        raise ValueError("Fixed elbow grid differs")
    prior=SOURCE_GOALS
    expected_steps=(50,30,30,30,60,30,30,30,60,30,30,30,60,30,30,30)
    for target,expected in zip(TARGETS,expected_steps):
        if abs(target[3]-prior[3])!=expected:
            raise ValueError("Elbow grid step differs")
        prior=target
    return True


def preview(model_path):
    validate_recipe();path=Path(model_path).resolve(strict=True)
    model=UrdfModel.from_file(path)
    previous=SOURCE_POSITIONS;goals=SOURCE_GOALS;rows=[]
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
        if min_z<40 or min_proxy<30:
            raise ValueError("Modeled clearance screen failed")
        rows.append(dict(leg=leg,phase=PHASES[leg-1],goals=list(target),
                         elbow_goal_step_counts=abs(target[3]-goals[3]),
                         minimum_modeled_tcp_z_mm=min_z,
                         minimum_modeled_link_axis_separation_mm=min_proxy))
        previous=target;goals=target
    return dict(schema="rocell.air_typing_elbow_grid_preview.v1",
                status="OFFLINE_ELBOW_GRID_SWEEP_PASS_NOT_EXECUTABLE",
                source_goals=list(SOURCE_GOALS),source_positions=list(SOURCE_POSITIONS),
                model_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),legs=rows,
                maximum_writes=16,one_use_per_boot=True,export_each_leg_required=True,
                hardware_access=False,motion_authorized=False,
                physical_clearance_verified=False,physical_accuracy_verified=False,
                caveat="Two held-out elbow goals, model only; meshless URDF omits cables/tool/board.")

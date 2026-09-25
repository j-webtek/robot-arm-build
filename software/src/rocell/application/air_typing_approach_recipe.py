"""Offline fixed two-cycle comparison of A arrivals from different approach paths."""
from __future__ import annotations

import hashlib
import math
from pathlib import Path

from rocell.geometry import UrdfModel

from .air_typing_continuation_preview import _angles
from .large_pose_ladder import _sample
from .product_ghost_export_review import _read


SOURCE_GOALS=(2047,2075,2039,2600,2233,2040,2047)
SOURCE_POSITIONS=(2041,2082,2033,2609,2233,2041,2047)
MID=(1994,2076,2038,2598,2234,2040,2047)
A=SOURCE_GOALS
HIGH=(2047,2105,2009,2630,2173,2040,2047)
TARGETS=(MID,A,HIGH,A,MID,A,HIGH,A)
PHASES=("mid_1","A_from_mid_1","high_1","A_from_high_1",
        "mid_2","A_from_mid_2","high_2","A_from_high_2")
SOURCE_EXPORT="wizard-20260925T005208116238Z-9058a361c92f4d81ba686b724286c712"


def review_source(export_root):
    row,digest=_read(Path(export_root).resolve(),SOURCE_EXPORT,
                     "attachment-air-typing-repeat-assessment.json")
    if (row.get("status")!="A_REPEAT_LEG_ENDPOINT_VERIFIED" or row.get("leg")!=6
            or row.get("source_kind")!="controller_feedback"
            or row.get("final_goals")!=list(SOURCE_GOALS)
            or row.get("final_positions")!=list(SOURCE_POSITIONS)):
        raise ValueError("Retained r79 source differs")
    return digest


def validate_recipe():
    if (len(TARGETS)!=8 or TARGETS[:4]!=TARGETS[4:]
            or TARGETS!=(MID,A,HIGH,A,MID,A,HIGH,A)):
        raise ValueError("Fixed approach sequence differs")
    prior=SOURCE_GOALS
    for target in TARGETS:
        if (len(target)!=7 or any(type(value) is not int or not 0<=value<=4095
                                 for value in target)
                or max(abs(a-b) for a,b in zip(prior,target))>80):
            raise ValueError("Unreviewed target step")
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
                         maximum_goal_step_counts=max(abs(a-b) for a,b in zip(goals,target)),
                         minimum_modeled_tcp_z_mm=min_z,
                         minimum_modeled_link_axis_separation_mm=min_proxy))
        previous=target;goals=target
    return dict(schema="rocell.air_typing_approach_preview.v1",
                status="OFFLINE_APPROACH_SWEEP_PASS_NOT_EXECUTABLE",
                source_goals=list(SOURCE_GOALS),source_positions=list(SOURCE_POSITIONS),
                model_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),legs=rows,
                maximum_writes=8,one_use_per_boot=True,export_each_leg_required=True,
                hardware_access=False,motion_authorized=False,
                physical_clearance_verified=False,physical_accuracy_verified=False,
                caveat="Existing tested goals but reverse A-to-mid path, unregistered meshless model, cables/tool omitted.")

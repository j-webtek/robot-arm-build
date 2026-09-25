"""Elbow-only low/high approach comparison from the retained r79 A pose."""
from __future__ import annotations

import hashlib
import math
from pathlib import Path

from rocell.geometry import UrdfModel

from .air_typing_continuation_preview import _angles
from .air_typing_approach_recipe import SOURCE_GOALS,SOURCE_POSITIONS,review_source
from .large_pose_ladder import _sample


LOW=(2047,2075,2039,2570,2233,2040,2047)
A=SOURCE_GOALS
HIGH=(2047,2075,2039,2630,2233,2040,2047)
TARGETS=(LOW,A,HIGH,A,LOW,A,HIGH,A)
PHASES=("elbow_low_1","A_from_low_1","elbow_high_1","A_from_high_1",
        "elbow_low_2","A_from_low_2","elbow_high_2","A_from_high_2")


def validate_recipe():
    if (len(TARGETS)!=8 or TARGETS!=(LOW,A,HIGH,A,LOW,A,HIGH,A)
            or any(tuple(target[i] for i in (0,1,2,4,5,6))!=
                   tuple(A[i] for i in (0,1,2,4,5,6)) for target in TARGETS)):
        raise ValueError("Fixed isolated-elbow sequence differs")
    prior=A
    for target in TARGETS:
        if not 1<=abs(target[3]-prior[3])<=30:
            raise ValueError("Elbow step outside reviewed window")
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
    return dict(schema="rocell.air_typing_elbow_direction_preview.v1",
                status="OFFLINE_ELBOW_DIRECTION_SWEEP_PASS_NOT_EXECUTABLE",
                source_goals=list(SOURCE_GOALS),source_positions=list(SOURCE_POSITIONS),
                model_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),legs=rows,
                maximum_writes=8,one_use_per_boot=True,export_each_leg_required=True,
                hardware_access=False,motion_authorized=False,
                physical_clearance_verified=False,physical_accuracy_verified=False,
                caveat="New isolated-elbow poses are modeled only; unregistered meshless URDF omits cables/tool/board.")

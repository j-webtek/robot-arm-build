"""Offline count-space sweep from measured r76 B-hover; no device access."""
import hashlib
import math
from pathlib import Path

from rocell.geometry import UrdfModel

from .air_typing_campaign import TARGETS
from .air_typing_continuation_preview import _angles
from .large_pose_ladder import _sample


SOURCE_GOALS = (1941,2098,2016,2609,2201,2040,2047)
SOURCE_POSITIONS = (1949,2099,2015,2610,2203,2041,2047)


def preview(model_path: Path) -> dict:
    path = Path(model_path).resolve(strict=True)
    model = UrdfModel.from_file(path)
    previous = SOURCE_POSITIONS
    previous_goals = SOURCE_GOALS
    rows = []
    for ordinal in range(11, 18):
        target = TARGETS[ordinal-1]
        max_step = max(abs(a-b) for a,b in zip(previous_goals,target))
        if max_step > 80:
            raise ValueError("Unreviewed count step")
        minimum_z = minimum_proxy = math.inf
        for step in range(101):
            fraction = step/100
            counts = tuple(a+fraction*(b-a) for a,b in zip(previous,target))
            angles = _angles(counts)
            if not (-math.pi<=angles[0]<=math.pi and -math.pi/2<=angles[1]<=math.pi/2
                    and 0<=angles[2]<=2.95 and -math.pi/2<=angles[3]<=math.pi/2):
                raise ValueError("Provisional joint bound")
            points, proxy = _sample(model, angles)
            minimum_z = min(minimum_z,points["hand_tcp"][2])
            minimum_proxy = min(minimum_proxy,proxy)
        if minimum_proxy < 30:
            raise ValueError("Modeled self-separation below screen")
        rows.append(dict(original_leg=ordinal, goals=list(target),
                         maximum_goal_step_counts=max_step,
                         minimum_modeled_tcp_z_mm=minimum_z,
                         minimum_modeled_link_axis_separation_mm=minimum_proxy))
        previous = target
        previous_goals = target
    return dict(status="OFFLINE_R77_SWEEP_PASS_NOT_EXECUTABLE",
                model_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                source_goals=list(SOURCE_GOALS), source_positions=list(SOURCE_POSITIONS),
                legs=rows, hardware_access=False, motion_authorized=False,
                physical_clearance_verified=False, physical_accuracy_verified=False,
                caveat="Unregistered meshless URDF and count interpolation omit cables, tool, board and servo dynamics.")

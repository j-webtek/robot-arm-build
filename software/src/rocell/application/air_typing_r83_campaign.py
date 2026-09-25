"""Two-target elbow grid using the shared one-use export-gated host."""
from __future__ import annotations

from .air_typing_elbow_grid_recipe import PHASES,SOURCE_GOALS,SOURCE_POSITIONS,TARGETS
from .air_typing_r81_campaign import AirTypingElbowDirectionHost,_assess_leg


def assess_leg(raw:bytes,*,boot:str,leg:int,previous=None)->dict:
    return _assess_leg(raw,boot=boot,leg=leg,previous=previous,
        targets=TARGETS,phases=PHASES,source_positions=SOURCE_POSITIONS,
        source_goals=SOURCE_GOALS,domain=b"RCAIRAB901",
        status="ELBOW_GRID_LEG_ENDPOINT_VERIFIED",max_step=60,max_travel=72)


class AirTypingElbowGridHost(AirTypingElbowDirectionHost):
    route="/rocell/air-elbow-grid/"
    selector=b"AIRG16"
    leg_count=16
    mode_prefix="r83-elbow-grid"
    attachment_prefix="elbow-grid"
    completion_status="ELBOW_GRID_COMPLETE"
    assess=staticmethod(assess_leg)

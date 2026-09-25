"""Held-out nearby elbow target using the shared one-use export-gated host."""
from __future__ import annotations

from .air_typing_elbow_shift_recipe import PHASES,SOURCE_GOALS,SOURCE_POSITIONS,TARGETS
from .air_typing_r81_campaign import AirTypingElbowDirectionHost,_assess_leg


def assess_leg(raw:bytes,*,boot:str,leg:int,previous=None)->dict:
    return _assess_leg(raw,boot=boot,leg=leg,previous=previous,
        targets=TARGETS,phases=PHASES,source_positions=SOURCE_POSITIONS,
        source_goals=SOURCE_GOALS,domain=b"RCAIRAB801",
        status="ELBOW_SHIFT_LEG_ENDPOINT_VERIFIED")


class AirTypingElbowShiftHost(AirTypingElbowDirectionHost):
    route="/rocell/air-elbow-shift/"
    selector=b"AIRH8"
    mode_prefix="r82-elbow-shift"
    attachment_prefix="elbow-shift"
    completion_status="ELBOW_SHIFT_COMPLETE"
    assess=staticmethod(assess_leg)

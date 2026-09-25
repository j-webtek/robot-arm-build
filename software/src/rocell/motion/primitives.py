"""Semantic motion phases; these values contain no executable poses."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class MotionPhase(str, Enum):
    PARK = "PARK"
    TRANSIT = "TRANSIT"
    HOVER = "HOVER"
    VISION_CORRECT = "VISION_CORRECT"
    APPROACH = "APPROACH"
    CONTACT = "CONTACT"
    RETRACT = "RETRACT"
    VERIFY = "VERIFY"
    COMPLETE = "COMPLETE"


@dataclass(frozen=True, slots=True)
class DryRunStep:
    sequence: int
    phase: MotionPhase
    action_index: int | None
    semantic_target: str | None
    simulated: bool = True

    def __post_init__(self) -> None:
        if isinstance(self.sequence, bool) or not isinstance(self.sequence, int) or self.sequence < 0:
            raise ValueError("sequence must be a non-negative integer")
        if not isinstance(self.phase, MotionPhase):
            object.__setattr__(self, "phase", MotionPhase(self.phase))
        if self.action_index is not None and (
            isinstance(self.action_index, bool)
            or not isinstance(self.action_index, int)
            or self.action_index < 0
        ):
            raise ValueError("action_index must be null or a non-negative integer")
        if self.semantic_target is not None and (
            not isinstance(self.semantic_target, str) or not self.semantic_target
        ):
            raise ValueError("semantic_target must be null or a non-empty string")
        if self.simulated is not True:
            raise ValueError("DryRunStep must always be simulated")

    def to_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "phase": self.phase.value,
            "action_index": self.action_index,
            "semantic_target": self.semantic_target,
            "simulated": True,
        }

"""Small explicit unit wrappers for physical-model boundaries.

Semantic typing plans intentionally do not contain these values.  They become
relevant only after calibration and planning turn semantic targets into poses.
"""

from __future__ import annotations

from dataclasses import dataclass
import math


def finite_real(value: object, *, name: str = "value") -> float:
    """Return ``value`` as a finite float, rejecting bools and non-numbers."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


@dataclass(frozen=True, slots=True)
class Millimetres:
    value: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", finite_real(self.value, name="millimetres"))


@dataclass(frozen=True, slots=True)
class Radians:
    value: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", finite_real(self.value, name="radians"))

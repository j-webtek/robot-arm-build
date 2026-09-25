"""Snapshots of physical protections; unknown always means unsafe."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
import time


class HealthState(str, Enum):
    UNKNOWN = "UNKNOWN"
    PASS = "PASS"
    FAIL = "FAIL"


@dataclass(frozen=True, slots=True)
class InterlockSnapshot:
    captured_monotonic: float
    estop_chain: HealthState = HealthState.UNKNOWN
    board_anti_shift: HealthState = HealthState.UNKNOWN
    gravity_containment: HealthState = HealthState.UNKNOWN
    contact_guard: HealthState = HealthState.UNKNOWN

    def __post_init__(self) -> None:
        if isinstance(self.captured_monotonic, bool) or not isinstance(
            self.captured_monotonic, (int, float)
        ):
            raise TypeError("captured_monotonic must be numeric")
        if not math.isfinite(float(self.captured_monotonic)):
            raise ValueError("captured_monotonic must be finite")
        for field in ("estop_chain", "board_anti_shift", "gravity_containment", "contact_guard"):
            value = getattr(self, field)
            if not isinstance(value, HealthState):
                object.__setattr__(self, field, HealthState(value))

    @classmethod
    def unknown(cls, *, captured_monotonic: float | None = None) -> "InterlockSnapshot":
        return cls(time.monotonic() if captured_monotonic is None else captured_monotonic)

    def is_fresh(self, *, now: float | None = None, max_age_s: float = 0.5) -> bool:
        if max_age_s <= 0 or not math.isfinite(max_age_s):
            raise ValueError("max_age_s must be positive and finite")
        current = time.monotonic() if now is None else float(now)
        age = current - float(self.captured_monotonic)
        return 0.0 <= age <= max_age_s

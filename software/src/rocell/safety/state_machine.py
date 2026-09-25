"""Explicit runtime state transitions with no restart auto-resume."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class SafetyState(str, Enum):
    POWER_OFF = "POWER_OFF"
    CONNECTED = "CONNECTED"
    REFERENCED = "REFERENCED"
    LOCALIZED = "LOCALIZED"
    CALIBRATED = "CALIBRATED"
    DRY_RUN_READY = "DRY_RUN_READY"
    ARMED = "ARMED"
    EXECUTING = "EXECUTING"
    COMPLETE = "COMPLETE"
    FAULT = "FAULT"


class StateTransitionError(RuntimeError):
    """The requested runtime transition is absent from the safety graph."""


_ALLOWED: dict[SafetyState, frozenset[SafetyState]] = {
    SafetyState.POWER_OFF: frozenset({SafetyState.CONNECTED}),
    SafetyState.CONNECTED: frozenset({SafetyState.REFERENCED, SafetyState.POWER_OFF}),
    SafetyState.REFERENCED: frozenset({SafetyState.LOCALIZED, SafetyState.POWER_OFF}),
    SafetyState.LOCALIZED: frozenset({SafetyState.CALIBRATED, SafetyState.POWER_OFF}),
    SafetyState.CALIBRATED: frozenset({SafetyState.DRY_RUN_READY, SafetyState.POWER_OFF}),
    SafetyState.DRY_RUN_READY: frozenset({SafetyState.ARMED, SafetyState.POWER_OFF}),
    SafetyState.ARMED: frozenset({SafetyState.EXECUTING, SafetyState.DRY_RUN_READY, SafetyState.POWER_OFF}),
    SafetyState.EXECUTING: frozenset({SafetyState.COMPLETE}),
    SafetyState.COMPLETE: frozenset({SafetyState.DRY_RUN_READY, SafetyState.POWER_OFF}),
    SafetyState.FAULT: frozenset({SafetyState.POWER_OFF}),
}


@dataclass(slots=True)
class SafetyStateMachine:
    state: SafetyState = SafetyState.POWER_OFF
    history: list[SafetyState] = field(default_factory=lambda: [SafetyState.POWER_OFF])

    def transition(self, target: SafetyState) -> None:
        if not isinstance(target, SafetyState):
            target = SafetyState(target)
        if target is SafetyState.FAULT:
            self.fault()
            return
        if target not in _ALLOWED[self.state]:
            raise StateTransitionError(f"Cannot transition {self.state.value} -> {target.value}")
        self.state = target
        self.history.append(target)

    def fault(self) -> None:
        if self.state is not SafetyState.FAULT:
            self.state = SafetyState.FAULT
            self.history.append(SafetyState.FAULT)

    def restart(self) -> None:
        """A process restart always returns to POWER_OFF, never ARMED."""

        self.state = SafetyState.POWER_OFF
        self.history.append(SafetyState.POWER_OFF)

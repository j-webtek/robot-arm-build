"""Minimal permit-gated RoArm-M3 client.

The client deliberately offers no arbitrary raw-command or T=1041 escape hatch.
It never connects, initializes, retries, references, or moves at construction.
Its transport consumes all permits at the final outbound boundary.
"""

from __future__ import annotations

from rocell.safety.permit import FeedbackPermit, MotionPermit

from .feedback import Feedback1051, parse_feedback_1051
from .protocol import CartesianGoal
from .serial_transport import ArmTransport


class RoArmM3:
    """Read-feedback and permit-gated T=104 operations over an injected transport."""

    def __init__(
        self,
        transport: ArmTransport,
        *,
        permit_feedback: FeedbackPermit | None = None,
        permit_motion: MotionPermit | None = None,
    ) -> None:
        self._transport = transport
        self._permit_feedback = permit_feedback
        self._permit_motion = permit_motion

    @property
    def is_connected(self) -> bool:
        return self._transport.is_open

    def connect(self) -> None:
        """Explicitly open the injected transport; send no controller commands."""

        self._transport.connect()

    def close(self) -> None:
        """Close the transport without implying park, stop, or torque release."""

        self._transport.close()

    def request_feedback(self) -> Feedback1051:
        response = self._transport.request_feedback(self._permit_feedback)
        return parse_feedback_1051(response)

    def move_cartesian(self, goal: CartesianGoal) -> None:
        """Send one bounded-layer T=104 goal only after an explicit permit.

        The transport consumes the exact-goal permit for every individual
        command. Replay records the command in memory; the hardware-backed
        transport remains hard-blocked until bounded execution is implemented.
        There is no retry and this method does not infer physical completion.
        """

        if not isinstance(goal, CartesianGoal):
            raise TypeError("goal must be a CartesianGoal")
        self._transport.send_motion(goal, self._permit_motion)

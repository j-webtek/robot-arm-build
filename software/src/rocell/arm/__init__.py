"""Controlled RoArm-M3 protocol boundary."""

from .connection import (
    ArmConnectionConfigurationError,
    ArmConnectionProfile,
    load_arm_connection_profile,
)
from .feedback import Feedback1051, FeedbackError, parse_feedback_1051, parse_feedback_line
from .feedback_wire import (
    FeedbackWireError,
    FeedbackWireFailure,
    receive_buffered_byte_count,
    require_quiescent_receive_buffer,
    validate_feedback_response_line,
)
from .protocol import (
    CARTESIAN_TARGET_TYPE,
    FEEDBACK_REQUEST_TYPE,
    FEEDBACK_RESPONSE_TYPE,
    PROHIBITED_DIRECT_TARGET_TYPE,
    CartesianGoal,
    ProtocolError,
    UnsupportedCommandError,
)
from .protocol_emulator import (
    DeterministicFeedbackSession,
    DeterministicProtocolController,
    ProtocolEmulatorError,
    ProtocolEmulatorFault,
    ProtocolEmulatorSessionError,
    ProtocolEmulatorSessionFailure,
    ProtocolEmulatorStep,
)
from .roarm_m3 import RoArmM3
from .serial_transport import (
    ArmTransport,
    FeedbackNotPermittedError,
    MotionNotPermittedError,
    NotConnectedError,
    ReplayTransport,
    SerialTransport,
    TransportError,
    TransportTimeoutError,
)
from rocell.safety.permit import FeedbackPermit, MotionPermit

__all__ = [
    "CARTESIAN_TARGET_TYPE",
    "ArmConnectionConfigurationError",
    "ArmConnectionProfile",
    "FEEDBACK_REQUEST_TYPE",
    "FEEDBACK_RESPONSE_TYPE",
    "PROHIBITED_DIRECT_TARGET_TYPE",
    "CartesianGoal",
    "ArmTransport",
    "Feedback1051",
    "FeedbackError",
    "FeedbackWireError",
    "FeedbackWireFailure",
    "FeedbackNotPermittedError",
    "FeedbackPermit",
    "MotionNotPermittedError",
    "MotionPermit",
    "NotConnectedError",
    "ProtocolError",
    "DeterministicFeedbackSession",
    "DeterministicProtocolController",
    "ProtocolEmulatorError",
    "ProtocolEmulatorFault",
    "ProtocolEmulatorSessionError",
    "ProtocolEmulatorSessionFailure",
    "ProtocolEmulatorStep",
    "ReplayTransport",
    "RoArmM3",
    "SerialTransport",
    "TransportError",
    "TransportTimeoutError",
    "UnsupportedCommandError",
    "load_arm_connection_profile",
    "parse_feedback_1051",
    "parse_feedback_line",
    "receive_buffered_byte_count",
    "require_quiescent_receive_buffer",
    "validate_feedback_response_line",
]

"""Windows provider boundaries. Physical composition remains separately gated."""

from .native_t102_serial_transport_v1 import (
    WindowsNativeT102SerialTransportError,
    WindowsNativeT102SerialTransportV1,
)

__all__ = [
    "WindowsNativeT102SerialTransportError",
    "WindowsNativeT102SerialTransportV1",
]

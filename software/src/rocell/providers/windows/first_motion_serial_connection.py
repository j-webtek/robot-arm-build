"""Exclusive commissioning connection using the common bounded handle owner.

Construction is inert. Opening may reset the controller and cause startup
movement, so only supervised production composition may call open(). No fallback
port, purge, discovery, reset or automatic retry is provided here.
"""
import time

from rocell.application.first_motion_contract import FirstMotionRequest
from rocell.application.first_motion_owned_trial import FirstMotionCleanupResult
from rocell.arm.protocol import encode_line
from .endpoint_serial_connection import EndpointSerialConnection
from .first_motion_serial_api import WindowsFirstMotionSerialApi


class FirstMotionSerialConnection(EndpointSerialConnection):
    def __init__(self, request, api, *, clock_ns=time.monotonic_ns):
        if (type(request) is not FirstMotionRequest or type(api) is not WindowsFirstMotionSerialApi
                or api.admitted_request_sha256 != request.request_sha256 or not callable(clock_ns)):
            raise ValueError('Exact admitted commissioning facade/request required')
        self._initialize_owned_state(request, api, clock_ns)

    def _motion_payload(self):
        return encode_line(self._request.to_dict()['command'])

    def close(self, timeout_ms):
        result = super().close(timeout_ms)
        return FirstMotionCleanupResult(result.all_handles_closed, result.pending_io_count)

    def snapshot(self):
        result = super().snapshot()
        result['schema'] = 'rocell.first_motion_connection_lifecycle.v1'
        return result

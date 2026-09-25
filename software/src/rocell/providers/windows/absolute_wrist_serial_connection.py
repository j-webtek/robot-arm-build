"""Dormant typed connection retaining existing bounded Win32 cleanup behavior."""
import time

from rocell.safety.absolute_wrist_review_authority import AbsoluteWristIntent
from .absolute_wrist_serial_api import WindowsAbsoluteWristSerialApi
from .endpoint_serial_connection import EndpointSerialConnection


class AbsoluteWristSerialConnection(EndpointSerialConnection):
    def __init__(self, request, api, *, clock_ns=time.monotonic_ns):
        if (type(request) is not AbsoluteWristIntent or type(api) is not WindowsAbsoluteWristSerialApi
                or api.admitted_request_sha256 != request.request_sha256 or not callable(clock_ns)):
            raise ValueError('Exact admitted absolute diagnostic connection required')
        self._initialize_owned_state(request, api, clock_ns)

    def _runtime_body(self):
        return self._request.runtime_body()

    def _motion_payload(self):
        return self._api._motion_payload()

    def snapshot(self):
        result = super().snapshot()
        result['schema'] = 'rocell.absolute_wrist_connection_lifecycle.v1'
        return result

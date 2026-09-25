"""Exact correction handle owner using existing bounded cleanup mechanics.

Not a launch route. A separately contained worker must bound stuck native calls
and retain raw baseline/post/cleanup evidence before publishing any verdict.
"""
import time
from .wrist_correction_current_context import WristCorrectionContextRequest
from .wrist_correction_serial_api import WindowsWristCorrectionSerialApi
from .endpoint_serial_connection import EndpointSerialConnection


class WristCorrectionSerialConnection(EndpointSerialConnection):
    def __init__(self,request,api,*,clock_ns=time.monotonic_ns):
        if (type(request) is not WristCorrectionContextRequest or type(api) is not WindowsWristCorrectionSerialApi
                or api.admitted_request_sha256!=request.request_sha256 or not callable(clock_ns)):
            raise ValueError('Exact admitted correction connection required')
        self._initialize_owned_state(request,api,clock_ns)

    def _runtime_body(self):
        return self._request.runtime_body()

    def _motion_payload(self):
        return self._api._motion_payload()

    def snapshot(self):
        result=super().snapshot()
        result['schema']='rocell.wrist_correction_connection_lifecycle.v1'
        return result

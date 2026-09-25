"""One owned observational connection with shared bounded Win32 cleanup."""
import time

from rocell.safety.observational_review_authority import ObservationalIntent
from .observational_serial_api import WindowsObservationalSerialApi
from .endpoint_serial_connection import EndpointSerialConnection


class ObservationalSerialConnection(EndpointSerialConnection):
    def __init__(self, request, api, *, clock_ns=time.monotonic_ns):
        if (type(request) is not ObservationalIntent or type(api) is not WindowsObservationalSerialApi
                or api.admitted_request_sha256 != request.request_sha256 or not callable(clock_ns)):
            raise ValueError('Exact admitted observational connection required')
        self._initialize_owned_state(request, api, clock_ns)

    def _runtime_body(self):
        return self._request.runtime_body()

    def _motion_payload(self):
        return self._api._motion_payload()

    def snapshot(self):
        result = super().snapshot()
        result['schema'] = 'rocell.observational_connection_lifecycle.v1'
        return result

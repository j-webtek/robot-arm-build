"""One-use wrist commissioning facade; not registered for live wizard access.

Shares owned Win32 I/O, buffer pinning and cleanup with the endpoint facade,
but never converts a commissioning request into a Cartesian request or permit.
Only the exact commissioning factory can bind this facade. The worker must
still bound acquisition, waits and cleanup and retain independent observations.
"""

from rocell.application.first_motion_contract import FirstMotionRequest
from rocell.arm.protocol import encode_line
from rocell.safety.first_motion_admission import FirstMotionPermit
from .endpoint_serial_api import WindowsEndpointSerialApi


class WindowsFirstMotionSerialApi(WindowsEndpointSerialApi):
    """Inert until authenticated admission; one exact write, never a retry."""

    @classmethod
    def from_first_motion_permit(cls, request, permit, *, port_name, connection_id):
        if (cls is not WindowsFirstMotionSerialApi
                or type(request) is not FirstMotionRequest
                or type(permit) is not FirstMotionPermit):
            raise ValueError('Exact first-motion native composition required')
        instance = cls(port_name)
        permit.claim_native_open(request, connection_id, port_name)
        instance._request, instance._permit = request, permit
        instance._connection_id = connection_id
        return instance

    def _motion_payload(self):
        # The immutable contract admits only T101/joint 4/absolute +1 degree.
        # No caller-supplied JSON, relative delta or alternate speed is accepted.
        return encode_line(self._request.to_dict()['command'])

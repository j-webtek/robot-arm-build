"""Dormant exact-target facade; not registered in wizard or worker launch routes.

Reuses Win32 owned-handle/IO-token checks. It does not bypass the need for a
source/runtime/process-bound native worker or establish physical qualification.
"""
from rocell.safety.absolute_wrist_admission import AbsoluteWristPermit
from rocell.safety.absolute_wrist_review_authority import AbsoluteWristIntent
from .endpoint_serial_api import WindowsEndpointSerialApi


class WindowsAbsoluteWristSerialApi(WindowsEndpointSerialApi):
    @classmethod
    def from_absolute_wrist_permit(cls, request, permit, *, port_name, connection_id):
        if (cls is not WindowsAbsoluteWristSerialApi or type(request) is not AbsoluteWristIntent
                or type(permit) is not AbsoluteWristPermit):
            raise ValueError('Exact absolute diagnostic native composition required')
        instance = cls(port_name)
        permit.claim_native_open(request, connection_id, port_name)
        instance._request, instance._permit, instance._connection_id = request, permit, connection_id
        return instance

    def _motion_payload(self):
        return self._permit.selected_payload()

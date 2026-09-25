"""Dormant correction-only Win32 facade; not registered for physical launch.

Reuses owned handles/events, exact IO tokens and one-write enforcement. A
source/runtime-bound worker must still own capture, deadlines and cleanup.
"""
from rocell.safety.wrist_correction_admission import WristCorrectionPermit
from .wrist_correction_current_context import WristCorrectionContextRequest
from .endpoint_serial_api import WindowsEndpointSerialApi


class WindowsWristCorrectionSerialApi(WindowsEndpointSerialApi):
    @classmethod
    def from_correction_permit(cls,request,permit,*,port_name,connection_id):
        if (cls is not WindowsWristCorrectionSerialApi or type(request) is not WristCorrectionContextRequest
                or type(permit) is not WristCorrectionPermit):
            raise ValueError('Exact correction native composition required')
        instance=cls(port_name)
        permit.claim_native_open(request,connection_id,port_name)
        instance._request,instance._permit,instance._connection_id=request,permit,connection_id
        return instance

    def _motion_payload(self):
        return self._permit.selected_payload()

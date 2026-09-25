"""Separate observational facade; not registered as a wizard live action.

Reuses bounded Win32 I/O ownership and exact-token submission. It accepts only
observational admission, never a measured permit or a caller-selected command.
"""
from rocell.safety.observational_admission import ObservationalPermit
from rocell.safety.observational_review_authority import ObservationalIntent
from .endpoint_serial_api import WindowsEndpointSerialApi


class WindowsObservationalSerialApi(WindowsEndpointSerialApi):
    @classmethod
    def from_observational_permit(cls, request, permit, *, port_name, connection_id):
        if (cls is not WindowsObservationalSerialApi or type(request) is not ObservationalIntent
                or type(permit) is not ObservationalPermit):
            raise ValueError('Exact observational native composition required')
        instance = cls(port_name)
        permit.claim_native_open(request, connection_id, port_name)
        instance._request, instance._permit = request, permit
        instance._connection_id = connection_id
        return instance

    def _motion_payload(self):
        return self._permit.selected_payload()

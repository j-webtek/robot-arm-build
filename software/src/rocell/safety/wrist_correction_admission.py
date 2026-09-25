"""Disjoint correction permit adapter; requires separately owned native runtime."""
from rocell.application.wrist_correction_command_binding import WristCorrectionCommandBinding
from rocell.providers.windows.wrist_correction_current_context import (
    WristCorrectionContextRequest,AuthenticatedWristCorrectionReader)

_ISSUER=object()


class WristCorrectionPermit:
    def __init__(self,issuer,request,binding):
        if issuer is not _ISSUER: raise ValueError('Correction admission must issue permit')
        self._request,self._binding=request,binding

    def _require(self,request,connection_id,port_name):
        if (type(request) is not WristCorrectionContextRequest or request!=self._request or
                connection_id!=request.to_dict()['attempt_id'] or port_name!=self._binding._port):
            self.revoke()
            raise ValueError('Correction request or pinned connection changed')

    def claim_native_open(self,request,connection_id,port_name):
        self._require(request,connection_id,port_name);self._binding.claim_open()

    def validate_native_open(self,request,connection_id,port_name):
        self._require(request,connection_id,port_name);self._binding.validate_open_claim()

    def bind_owned_baseline(self,request,connection_id,port_name,raw,windows,*,started_ns,finished_ns):
        self._require(request,connection_id,port_name)
        return self._binding.bind_baseline(raw,windows,started_ns=started_ns,finished_ns=finished_ns)

    def selected_payload(self):
        return self._binding.selected_payload()

    def prepare_final_dispatch(self,connection):
        if connection._request is not self._request or not connection._api.matches_authorization(self._request,self):
            self.revoke()
            raise ValueError('Final dispatch connection differs from permit')
        return self._binding.prepare_final_dispatch(connection)

    def claim_native_dispatch(self,request,connection_id,port_name):
        self._require(request,connection_id,port_name)
        self._binding.consume_command()

    def revoke(self):
        self._binding.revoke()


def admit_wrist_correction(request,*,reader,root,cancellation):
    if (type(request) is not WristCorrectionContextRequest or type(reader) is not AuthenticatedWristCorrectionReader
            or reader.request!=request):
        raise ValueError('Exact correction request and authenticated context reader required')
    binding=WristCorrectionCommandBinding(reader=reader,root=root,cancellation=cancellation)
    return WristCorrectionPermit(_ISSUER,request,binding)

"""Exact native-boundary adapter for one authenticated absolute diagnostic.

No device calls. Only a separately reviewed owned worker may compose native IO.
This is distinct from relative, measured and multi-leg campaign permissions.
"""
from rocell.application.absolute_wrist_command_binding import AbsoluteWristCommandBinding
from rocell.providers.windows.absolute_wrist_current_context import AuthenticatedAbsoluteWristReader
from .absolute_wrist_review_authority import AbsoluteWristIntent

_ISSUER = object()


class AbsoluteWristPermit:
    def __init__(self, issuer, request, binding):
        if issuer is not _ISSUER:
            raise ValueError('Absolute admission must issue this permit')
        self._request, self._binding = request, binding

    def _require(self, request, connection_id, port_name):
        if (type(request) is not AbsoluteWristIntent or request != self._request
                or connection_id != request.to_dict()['attempt_id']
                or port_name != self._binding._port):
            self.revoke()
            raise ValueError('Absolute request or pinned connection changed')

    def claim_native_open(self, request, connection_id, port_name):
        self._require(request, connection_id, port_name)
        self._binding.claim_open()

    def validate_native_open(self, request, connection_id, port_name):
        self._require(request, connection_id, port_name)
        self._binding.validate_open_claim()

    def bind_owned_baseline(self, request, connection_id, port_name, raw, windows,
                            *, started_ns, finished_ns):
        self._require(request, connection_id, port_name)
        return self._binding.bind_baseline(raw, windows, started_ns=started_ns, finished_ns=finished_ns)

    def selected_payload(self):
        return self._binding.selected_payload()

    def claim_native_dispatch(self, request, connection_id, port_name):
        self._require(request, connection_id, port_name)
        self._binding.consume_command()

    def revoke(self):
        self._binding.revoke()


def admit_absolute_wrist(request, *, reader, root):
    if (type(request) is not AbsoluteWristIntent or type(reader) is not AuthenticatedAbsoluteWristReader
            or reader.request != request):
        raise ValueError('Exact absolute request and authenticated reader required')
    binding = AbsoluteWristCommandBinding(request, reader=reader, root=root)
    return AbsoluteWristPermit(_ISSUER, request, binding)

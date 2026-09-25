"""Authenticated one-open/one-command admission for observational commissioning.

No device calls here. Only the separately composed native worker may use this
permit. Browser data and observational previews are not substitute permissions.
"""
from threading import Lock

from rocell.application.observational_command_binding import ObservationalCommandBinding
from rocell.arm.protocol import encode_line
from rocell.providers.windows.observational_current_context import AuthenticatedObservationalReader
from .observational_review_authority import ObservationalIntent

_ISSUER = object()


class ObservationalPermit:
    def __init__(self, issuer, request, reader, binding, evidence):
        if issuer is not _ISSUER:
            raise ValueError('Observational admission must issue the permit')
        self._request, self._reader, self._binding = request, reader, binding
        self._bundle_sha = evidence['bundle_sha256']
        self._port = evidence['port_name']
        self._last = evidence['verified_at_ns']
        self._state = 'ADMITTED'
        self._payload = None
        self._lock = Lock()

    def _check(self, request, connection_id, port_name):
        if (type(request) is not ObservationalIntent or request != self._request
                or connection_id != request.to_dict()['attempt_id'] or port_name != self._port):
            raise ValueError('Exact observational request and pinned endpoint required')
        evidence = self._reader.verify_endpoint(port_name)
        if (evidence['bundle_sha256'] != self._bundle_sha
                or evidence['verified_at_ns'] < self._last):
            raise ValueError('Observational review changed or clock moved backwards')
        self._last = evidence['verified_at_ns']
        return self._last

    def _fail(self):
        self._state = 'REVOKED'
        self._binding.revoke()

    def revoke(self):
        with self._lock:
            self._fail()

    def claim_native_open(self, request, connection_id, port_name):
        with self._lock:
            if self._state != 'ADMITTED':
                raise ValueError('Observational open already claimed or revoked')
            self._state = 'OPEN_CLAIMED'
            try:
                now = self._check(request, connection_id, port_name)
                if now + 11_000_000_000 > request.to_dict()['deadline_ns']:
                    raise ValueError('Insufficient open/trial/cleanup budget')
            except Exception:
                self._fail()
                raise

    def validate_native_open(self, request, connection_id, port_name):
        with self._lock:
            if self._state != 'OPEN_CLAIMED':
                raise ValueError('No observational native-open claim')
            try:
                self._check(request, connection_id, port_name)
            except Exception:
                self._fail()
                raise

    def bind_owned_baseline(self, request, connection_id, port_name, raw, windows,
                            *, started_ns, finished_ns):
        with self._lock:
            if self._state != 'OPEN_CLAIMED':
                raise ValueError('Owned open required before baseline selection')
            self._state = 'SELECTING'
            try:
                now = self._check(request, connection_id, port_name)
                body = request.to_dict()
                report = self._binding.bind_baseline(raw, windows, started_ns=started_ns,
                    finished_ns=finished_ns, session_id=body['session_id'],
                    connection_id=connection_id, usb_identity=body['usb_identity'], now_ns=now)
                self._payload = encode_line(report['preview']['candidate_command'])
                self._state = 'BOUND'
                return report
            except Exception:
                self._fail()
                raise

    def selected_payload(self):
        """For exact native token construction only; not permission to submit."""
        with self._lock:
            if self._state != 'BOUND':
                raise ValueError('No selected observational payload')
            return self._payload

    def claim_native_dispatch(self, request, connection_id, port_name):
        with self._lock:
            if self._state != 'BOUND':
                raise ValueError('One selected observational command required')
            self._state = 'DISPATCHED'  # Burn before checking or submitting bytes.
            try:
                now = self._check(request, connection_id, port_name)
                body = request.to_dict()
                payload = self._binding.consume_command(session_id=body['session_id'],
                    connection_id=connection_id, usb_identity=body['usb_identity'], now_ns=now)
                if payload != self._payload:
                    raise ValueError('Selected command changed')
            except Exception:
                self._fail()
                raise


def admit_observational(request, *, reader, root):
    if (type(request) is not ObservationalIntent or type(reader) is not AuthenticatedObservationalReader
            or reader.request != request):
        raise ValueError('Exact observational request and authenticated reader required')
    evidence = reader.verify_endpoint()
    body = request.to_dict()
    binding = ObservationalCommandBinding(root=root, session_id=body['session_id'],
        attempt_id=body['attempt_id'], connection_id=body['attempt_id'],
        usb_identity=body['usb_identity'], issued_ns=body['issued_ns'],
        deadline_ns=body['deadline_ns'], direction=body['direction'], policy=body['policy'])
    return ObservationalPermit(_ISSUER, request, reader, binding, evidence)

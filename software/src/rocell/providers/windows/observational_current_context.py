"""Resolve an observational intent against current reviewed USB metadata.

Shares the established persistent controller resolver, including duplicate,
changed endpoint and stale metadata rejection. No serial access is performed.
"""
from dataclasses import dataclass
import re
import time

from rocell.safety.observational_review_authority import (
    ObservationalIntent, ObservationalReviewAuthority,
)
from rocell.application.physical_onboarding_durability import (
    safe_root, contained_path, read_bounded_regular_file,
)
from .endpoint_current_context import EndpointCurrentContextReader


@dataclass(frozen=True, slots=True)
class ObservationalCurrentContext:
    connection_id: str
    usb_identity: tuple
    references: tuple
    observed_ns: int
    port_name: str


class ObservationalCurrentContextReader(EndpointCurrentContextReader):
    @staticmethod
    def _accept_request(request):
        return type(request) is ObservationalIntent

    @staticmethod
    def _context_body(request):
        body = request.to_dict()
        # Project only timestamp names for the shared metadata implementation;
        # the request remains an ObservationalIntent, never a measured permit.
        return dict(body, issued_monotonic_ns=body['issued_ns'],
                    deadline_monotonic_ns=body['deadline_ns'])

    @staticmethod
    def _make_context(connection, identity, references, observed_ns, port):
        return ObservationalCurrentContext(connection, identity, references, observed_ns, port)

    def __init__(self, request, *, connection_id, **kwargs):
        if type(request) is not ObservationalIntent or connection_id != request.to_dict()['attempt_id']:
            raise ValueError('Exact observational intent and connection required')
        super().__init__(request, connection_id=connection_id, **kwargs)


class AuthenticatedObservationalReader:
    """Read the original bundle and re-resolve metadata for each boundary check.

    The worker provides the fixed root, existing authority and native context
    provider. There is no browser-controlled path or auto-approval behavior.
    """
    def __init__(self, request, *, root, authority, context_reader, clock_ns=time.monotonic_ns):
        if (type(request) is not ObservationalIntent
                or type(authority) is not ObservationalReviewAuthority
                or type(context_reader) is not ObservationalCurrentContextReader
                or not callable(clock_ns)):
            raise ValueError('Exact observational host dependencies required')
        if context_reader._request != request:
            raise ValueError('Context reader belongs to a different intent')
        self.request, self._authority, self._context, self._clock = request, authority, context_reader, clock_ns
        self._root = safe_root(root)

    def verify_endpoint(self, port_name=None):
        if port_name is not None and (type(port_name) is not str
                or not re.fullmatch('COM[1-9][0-9]{0,3}', port_name) or int(port_name[3:]) > 4096):
            raise ValueError('Exact bounded COM port required')
        body = self.request.to_dict()
        raw = read_bounded_regular_file(contained_path(self._root,
            body['attempt_id']+'-observational-reviews.json', label='observational review'),
            maximum_bytes=8192)
        context = self._context()
        now = self._clock()
        if (type(context) is not ObservationalCurrentContext
                or context.connection_id != body['attempt_id']
                or type(now) is not int or not body['issued_ns'] <= context.observed_ns <= now
                or now-context.observed_ns > 100_000_000
                or (port_name is not None and context.port_name != port_name)):
            raise ValueError('Current observational endpoint context is stale or changed')
        evidence = self._authority.verify(raw, expected_intent=body,
            current_usb_identity=dict(zip(('vid','pid','serial_number'), context.usb_identity)),
            current_references=dict(context.references), now_ns=now)
        return dict(evidence, connection_id=context.connection_id, port_name=context.port_name,
                    usb_identity=context.usb_identity)

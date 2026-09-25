"""Durably burn an endpoint attempt before issuing its in-process permit.

Uses the existing exclusive-create/write-through publication primitive. A
partial file after a crash blocks reuse; recovery never deletes or resumes it.
This is storage integrity, not authentication of the referenced safety reviews.
The application must supply one stable, qualified root (never a browser path).
"""

import hashlib
import json
from pathlib import Path

from .physical_onboarding_durability import (
    safe_root, contained_path, publish_reservation_bytes, read_bounded_regular_file,
)

MAX_BYTES = 32768


class EndpointAttemptReservation:
    """One immutable admission record; possession alone grants no device access."""

    def __init__(self, root, request, connection_id, evidence):
        root = safe_root(Path(root))
        body = request.to_dict()
        name = body['attempt_id'] + '-bench-endpoint-reserved.json'
        self._path = contained_path(root, name, label='endpoint reservation')
        raw = json.dumps({
            'schema':'rocell.bench_endpoint_reservation.v1',
            'attempt_id':body['attempt_id'], 'request_sha256':request.request_sha256,
            'request':body, 'connection_id':connection_id,
            'review_hashes':dict(evidence.checks),
            'verified_at_ns':evidence.verified_at_ns,
            'expires_at_ns':evidence.expires_at_ns,
            'replay_allowed':False, 'physical_authority':False,
            'movement_status':'NOT_ESTABLISHED',
        }, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('ascii')
        # The destination is occupied BEFORE content is written, not atomically
        # replaced afterward: even an empty/partial reservation burns the ID.
        publish_reservation_bytes(root, name, raw, maximum_bytes=MAX_BYTES)
        self._sha256 = hashlib.sha256(raw).hexdigest()
        if not self.intact():
            raise ValueError('Endpoint reservation readback mismatch')

    def intact(self):
        try:
            raw = read_bounded_regular_file(self._path, maximum_bytes=MAX_BYTES)
            return hashlib.sha256(raw).hexdigest() == self._sha256
        except Exception:
            return False

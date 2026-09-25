"""Engineering draft decisions, with original time retained at request binding.

These records are not operator presence, motion permits or authenticated merely
because they decode. A trusted parent must collect actual decisions and seal the
bound originals through the existing host authority. Native current-context,
baseline and one-use checks remain mandatory.
"""

import base64
from dataclasses import dataclass
import re
from threading import Lock
import time

from .endpoint_trial_contract import EndpointTrialRequest, _canonical
from .endpoint_trial_draft import EndpointTrialDraft
from .wizard_diagnostic_coordinator import decode_diagnostic_json

ENGINEERING_DRAFT_CHECKS = frozenset({
    'received_unit_and_usb_association', 'installed_firmware_compatibility',
    'controller_frame_and_baseline_qualified', 'noncontact_route_review',
    'owned_connection_and_cleanup_ready',
})
MAX_DRAFT_REVIEW_BYTES = 2048
MAX_REVIEW_LIFETIME_NS = 300_000_000_000


@dataclass(frozen=True, slots=True)
class EngineeringDraftReview:
    canonical_bytes: bytes

    def __post_init__(self):
        self.to_dict()

    def to_dict(self):
        if type(self.canonical_bytes) is not bytes:
            raise ValueError('Immutable engineering review original required')
        value = decode_diagnostic_json(self.canonical_bytes, maximum=MAX_DRAFT_REVIEW_BYTES)
        fields = {'schema','draft_sha256','check','actor_id','decision','detail','recorded_ns','expires_ns'}
        if (type(value) is not dict or set(value) != fields
                or _canonical(value) != self.canonical_bytes
                or value['schema'] != 'rocell.engineering_draft_review.v1'
                or type(value['check']) is not str or value['check'] not in ENGINEERING_DRAFT_CHECKS
                or type(value['draft_sha256']) is not str
                or re.fullmatch('[0-9a-f]{64}', value['draft_sha256']) is None
                or type(value['actor_id']) is not str
                or re.fullmatch(r'[A-Za-z0-9_.-]{1,64}', value['actor_id']) is None
                or type(value['decision']) is not str
                or value['decision'] not in {'APPROVED','DENIED','UNKNOWN'}
                or type(value['detail']) is not str or not 1 <= len(value['detail'].strip()) <= 1024
                or type(value['recorded_ns']) is not int or type(value['expires_ns']) is not int
                or not 0 < value['recorded_ns'] < value['expires_ns'] < 2**63
                or value['expires_ns']-value['recorded_ns'] > MAX_REVIEW_LIFETIME_NS):
            raise ValueError('Invalid bounded engineering draft decision')
        return value

    def validate_for_request(self, request, now_ns):
        if type(request) is not EndpointTrialRequest or type(now_ns) is not int:
            raise ValueError('Exact request and host time required')
        value = self.to_dict()
        if (value['decision'] != 'APPROVED'
                or value['draft_sha256'] != EndpointTrialDraft.from_request(request).draft_sha256
                or not value['recorded_ns'] <= now_ns < value['expires_ns']):
            raise ValueError('Draft decision refused, changed or expired')
        return value

    def bind_request(self, request, *, now_ns):
        """Record material binding, NOT a newly performed engineering review.

        The nested original survives byte-for-byte. Its expiry can only shorten
        the request review. This method signs nothing and cannot bind operator
        attestations. Final current operator decisions must use the existing
        exact-request intake.
        """
        value = self.validate_for_request(request, now_ns)
        request.require_start_time(now_ns)
        return _canonical({
            'schema':'rocell.bench_endpoint_review.v2',
            'scope':'ONE_NONCONTACT_BENCH_ENDPOINT', 'check':value['check'],
            'actor_id':value['actor_id'], 'decision':'APPROVED',
            'evidence_kind':'ENGINEERING_DRAFT_REVIEW_BINDING',
            'request_sha256':request.request_sha256, 'recorded_ns':now_ns,
            'expires_ns':min(value['expires_ns'],request.to_dict()['deadline_monotonic_ns']),
            'detail':'Exact draft-to-request binding; engineering observation time is in the retained original.',
            'draft_review_b64':base64.b64encode(self.canonical_bytes).decode('ascii'),
        })


class EngineeringDraftReviewReader:
    """One-shot trusted host adapter for the coordinator's engineering_reader.

    All five actual originals must be supplied before launch; this adapter
    makes no decisions. Invocation is consumed even on a mismatch or expiry,
    so another call cannot silently refresh binding timestamps. A new attempt
    requires an explicitly assembled new reader and still-valid originals.
    """

    def __init__(self, originals, *, clock_ns=time.monotonic_ns):
        if (type(originals) is not tuple or len(originals) != len(ENGINEERING_DRAFT_CHECKS)
                or not callable(clock_ns)):
            raise ValueError('Complete immutable engineering originals required')
        records = tuple(EngineeringDraftReview(raw) for raw in originals)
        values = tuple(record.to_dict() for record in records)
        if ({value['check'] for value in values} != ENGINEERING_DRAFT_CHECKS
                or len({value['draft_sha256'] for value in values}) != 1):
            raise ValueError('Unique engineering checks for one exact draft required')
        self._records = records
        self._clock = clock_ns
        self._lock = Lock()
        self._used = False

    def __call__(self, request):
        with self._lock:
            if self._used:
                raise ValueError('Engineering review binding already consumed')
            self._used = True
            now = self._clock()
            # Return all or none. The coordinator retains these nested originals
            # inside the signed bundle; no unsigned file lookup occurs here.
            return {record.to_dict()['check']:record.bind_request(request,now_ns=now)
                    for record in self._records}

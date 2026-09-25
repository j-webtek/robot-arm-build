"""Untimed, immutable trial selection for onboarding; never motion authority.

Reviewing a target must not consume the live request's short execution budget.
The draft retains every material request field but has no attempt or deadline.
Admission still requires independent current evidence and a one-use permit.
"""

from dataclasses import dataclass
import hashlib

from .endpoint_trial_contract import EndpointTrialRequest, _canonical
from .wizard_diagnostic_coordinator import decode_diagnostic_json

SCHEMA = 'rocell.endpoint_trial_draft.v1'
_TIMED_FIELDS = frozenset({'attempt_id', 'issued_monotonic_ns', 'deadline_monotonic_ns'})


def _validate(raw):
    if type(raw) is not bytes:
        raise ValueError('Immutable draft bytes required')
    value = decode_diagnostic_json(raw, maximum=16384)
    if (type(value) is not dict or set(value) != {'schema', 'selection'}
            or value['schema'] != SCHEMA or _canonical(value) != raw
            or type(value['selection']) is not dict
            or _TIMED_FIELDS.intersection(value['selection'])):
        raise ValueError('Canonical untimed draft required')
    # Validation-only envelope, never returned or used for execution. Reuse the
    # strict request codec so drafts cannot weaken geometry, identity or limits.
    EndpointTrialRequest(_canonical(dict(value['selection'],
        attempt_id='operation-' + '0'*32,
        issued_monotonic_ns=1, deadline_monotonic_ns=30_000_000_001)))
    return value['selection']


@dataclass(frozen=True, slots=True)
class EndpointTrialDraft:
    canonical_bytes: bytes

    def __post_init__(self):
        _validate(self.canonical_bytes)

    @property
    def draft_sha256(self):
        return hashlib.sha256(self.canonical_bytes).hexdigest()

    @classmethod
    def from_request(cls, request):
        if type(request) is not EndpointTrialRequest:
            raise ValueError('Typed endpoint request required')
        selection = request.to_dict()
        for field in _TIMED_FIELDS:
            del selection[field]
        return cls(_canonical({'schema': SCHEMA, 'selection': selection}))

    def create_request(self, *, expected_draft_sha256, attempt_id,
                       issued_monotonic_ns, deadline_monotonic_ns):
        """Bind unchanged selection to a new envelope, not renew old approval.

        Caller supplies a fresh attempt ID and real monotonic times. Existing
        durable launch/claim records reject reuse; this codec cannot authorize
        retries, manufacture reviews, or establish freshness of references.
        """
        if expected_draft_sha256 != self.draft_sha256:
            raise ValueError('Reviewed selection changed')
        return EndpointTrialRequest(_canonical(dict(_validate(self.canonical_bytes),
            attempt_id=attempt_id, issued_monotonic_ns=issued_monotonic_ns,
            deadline_monotonic_ns=deadline_monotonic_ns)))

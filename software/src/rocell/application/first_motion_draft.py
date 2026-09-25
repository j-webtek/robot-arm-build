"""Untimed commissioning selection for review, never a motion capability.

Only the final confirmation creates the timed request. Engineering reviews bind
the selection digest; operator attestations must bind the newly issued request.
Neither operation refreshes a measurement or changes its referenced original.
"""
from dataclasses import dataclass
import hashlib
import time

from .first_motion_contract import FirstMotionRequest, canonical
from .wizard_diagnostic_coordinator import decode_diagnostic_json

SCHEMA = 'rocell.first_motion_draft.v1'
TIMED_FIELDS = frozenset(('attempt_id', 'issued_monotonic_ns', 'deadline_monotonic_ns'))


def _selection(raw):
    if type(raw) is not bytes:
        raise ValueError('Immutable commissioning draft bytes required')
    value = decode_diagnostic_json(raw, maximum=16384)
    if (type(value) is not dict or set(value) != {'schema', 'selection'}
            or value['schema'] != SCHEMA or canonical(value) != raw
            or type(value['selection']) is not dict
            or TIMED_FIELDS.intersection(value['selection'])):
        raise ValueError('Exact canonical untimed commissioning selection required')
    # Validation-only envelope: reuse the strict contract, never return this
    # placeholder as an executable request or use it to attest operator review.
    FirstMotionRequest(canonical(dict(value['selection'],
        attempt_id='operation-' + '0' * 32,
        issued_monotonic_ns=1, deadline_monotonic_ns=30_000_000_001)))
    return value['selection']


@dataclass(frozen=True, slots=True)
class FirstMotionDraft:
    canonical_bytes: bytes

    def __post_init__(self):
        _selection(self.canonical_bytes)

    @property
    def selection_sha256(self):
        """Same digest used by authenticated engineering selection reviews."""
        return hashlib.sha256(canonical(_selection(self.canonical_bytes))).hexdigest()

    @classmethod
    def from_request(cls, request):
        if type(request) is not FirstMotionRequest:
            raise ValueError('Exact commissioning request type required')
        selection = request.to_dict()
        for field in TIMED_FIELDS:
            del selection[field]
        return cls(canonical({'schema': SCHEMA, 'selection': selection}))

    def preview(self):
        return dict(schema='rocell.first_motion_draft_preview.v1',
                    selection_sha256=self.selection_sha256,
                    selection=_selection(self.canonical_bytes),
                    motion_authorized=False, physical_clearance_verified=False,
                    final_request_required=True)

    def create_request(self, *, expected_selection_sha256, attempt_id,
                       issued_monotonic_ns, deadline_monotonic_ns):
        """Bind reviewed material to a final envelope, without renewing evidence.

        The host supplies actual time and a new attempt identity. Durable launch
        reservations still enforce one-use; this pure codec does not authorize
        execution or carry operator attestations from any earlier request.
        """
        if expected_selection_sha256 != self.selection_sha256:
            raise ValueError('Reviewed commissioning selection changed')
        return FirstMotionRequest(canonical(dict(_selection(self.canonical_bytes),
            attempt_id=attempt_id, issued_monotonic_ns=issued_monotonic_ns,
            deadline_monotonic_ns=deadline_monotonic_ns)))


def draft_from_originals(workspace, *, reference_originals, session_id,
                         measurement_operation_id, check_current,
                         clock_ns=time.monotonic_ns):
    """Derive a review draft from exact host-selected originals, not typed bounds.

    Structured hashes are provenance, not semantic approval. The caller still
    resolves successful same-session receipts before attaching this draft.
    No key, operator attestation, launch reservation or device is touched.
    """
    from .first_motion_contract import create_first_motion_request
    from .first_motion_reference_reader import ORIGINAL_REFERENCES
    from .first_motion_measurements import validate_original_for_request
    from .wizard_diagnostic_coordinator import source_fingerprint
    from rocell.rc03.importer import import_build_snapshot
    if (type(reference_originals) is not dict or set(reference_originals) != ORIGINAL_REFERENCES
            or not callable(check_current) or not callable(clock_ns)):
        raise ValueError('Complete host-selected originals and current context required')
    if check_current() is not None: raise ValueError('Draft context changed')
    originals = dict(reference_originals)
    refs = {}
    documents = {}
    for name, raw in originals.items():
        if type(raw) is not bytes or not 0 < len(raw) <= 128*1024:
            raise ValueError('Bounded exact original bytes required')
        value = decode_diagnostic_json(raw, maximum=128*1024)
        if type(value) is not dict or not value: raise ValueError('Structured original required')
        refs[name] = hashlib.sha256(raw).hexdigest()
        documents[name] = value
    refs.update(source_sha256=source_fingerprint(workspace),
                build_snapshot_sha256=import_build_snapshot(workspace).snapshot_hash)
    measurement = documents['independent_posture_review_sha256']
    now = clock_ns()
    if type(now) is not int or not 0 < now < 2**63-30_000_000_000:
        raise ValueError('Valid host draft clock required')
    try:
        # Validation envelope only; discarded when converting to untimed draft.
        request = create_first_motion_request(attempt_id='operation-'+'0'*32,
            usb_identity=dict(vid=0x10c4, pid=0xea60, serial_number=measurement['reported']['unit_serial']),
            references=refs, independent_start_interval_deg=measurement['derived']['reported_wrist_interval_deg'],
            distal_radius_mm=measurement['derived']['reported_distal_radius_upper_bound_mm'],
            issued_monotonic_ns=now, deadline_monotonic_ns=now+30_000_000_000)
    except (KeyError, TypeError) as error:
        raise ValueError('Complete measurement original required') from error
    if check_current() is not None: raise ValueError('Draft context changed')
    validate_original_for_request(originals['independent_posture_review_sha256'], request,
        session_id=session_id, operation_id=measurement_operation_id, now_ns=clock_ns())
    if (source_fingerprint(workspace) != refs['source_sha256']
            or import_build_snapshot(workspace).snapshot_hash != refs['build_snapshot_sha256']):
        raise ValueError('Source/build changed while assembling draft')
    return FirstMotionDraft.from_request(request)

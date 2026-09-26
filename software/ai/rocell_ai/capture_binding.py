"""Read-only capture-receipt check; trust is supplied by a capture-service adapter.

A hash is not authentication. Never populate the trusted mapping from model output.
No registry is installed here and no camera is accessed.
"""
from datetime import datetime, timezone
from .scene_observation import FrameEvidence, canonical_hash, parse_utc
from rocell.models import MotionEvidenceV2

FIELDS={'schema','capture_id','frame_id','image_sha256','camera_identity_sha256',
        'capture_clock_domain_id','captured_at_epoch_ms','issuer_id','receipt_sha256'}


def bind_capture(frame: FrameEvidence, evidence: MotionEvidenceV2, *,
                 receipt_sha256: str, trusted_receipts=None, expected_issuer_id: str):
    if not isinstance(frame,FrameEvidence) or not isinstance(evidence,MotionEvidenceV2):
        raise ValueError('typed frame and evidence required')
    if not isinstance(expected_issuer_id,str) or not expected_issuer_id.strip():
        raise ValueError('capture issuer required')
    registry={} if trusted_receipts is None else trusted_receipts
    if receipt_sha256 not in registry:
        return None
    receipt=registry[receipt_sha256]
    if not isinstance(receipt,dict) or set(receipt)!=FIELDS or receipt['schema']!='rocell.ai_capture_receipt.v0':
        raise ValueError('invalid capture receipt fields')
    digest=canonical_hash({k:v for k,v in receipt.items() if k!='receipt_sha256'})
    if receipt['receipt_sha256']!=digest or receipt_sha256!=digest:
        raise ValueError('capture receipt hash mismatch')
    if receipt['issuer_id']!=expected_issuer_id:
        raise ValueError('capture issuer mismatch')
    epoch=receipt['captured_at_epoch_ms']
    if type(epoch) is not int or epoch<=0:
        raise ValueError('capture epoch must be positive integer milliseconds')
    timestamp=parse_utc(frame.captured_at_utc,'frame capture time')
    delta=timestamp-datetime(1970,1,1,tzinfo=timezone.utc)
    microseconds=(delta.days*86400+delta.seconds)*1000000+delta.microseconds
    if microseconds%1000 or microseconds//1000!=epoch:
        raise ValueError('frame capture time mismatch or submillisecond precision')
    for key in ('capture_id','frame_id','image_sha256','camera_identity_sha256',
                'capture_clock_domain_id','captured_at_epoch_ms'):
        if receipt[key]!=getattr(evidence,key):
            raise ValueError(key+' capture mismatch')
    if receipt['frame_id']!=frame.frame_id or receipt['image_sha256']!=frame.image_sha256:
        raise ValueError('frame bytes or identity mismatch')
    core=dict(schema='rocell.ai_capture_binding.v0',receipt_sha256=digest,
        evidence_sha256=canonical_hash(evidence.to_dict()),image_sha256=frame.image_sha256,
        status='BOUND_TO_CALLER_TRUSTED_RECEIPT',hardware_writes=0,physical_movements=0,
        limitations=['Caller must authenticate capture service and clock mapping',
                    'Binding proves equality only, not localization or scene freshness'])
    return {**core,'binding_sha256':canonical_hash(core)}

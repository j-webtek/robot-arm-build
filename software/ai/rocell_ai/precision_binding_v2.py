"""Fail-closed preflight for the current synthetic precision record.

Current v2 precision wraps v1 coordinates without observation confidence or capture
clock provenance. This adapter reports blockers; it cannot emit a motion batch.
"""
from .precision_observation import validate
from .scene_observation import canonical_hash
from rocell.models import MotionEvidenceV2, MotionGeometryV2, MotionUncertaintyV2


def preflight(precision, *, evidence: MotionEvidenceV2,
              geometry: MotionGeometryV2, uncertainty: MotionUncertaintyV2 | None = None):
    validate(precision)
    if not isinstance(evidence,MotionEvidenceV2) or not isinstance(geometry,MotionGeometryV2):
        raise ValueError('shared typed evidence and geometry required')
    prediction=precision['prediction']
    bindings={
        'precision':(precision['observation_sha256'],evidence.precision_observation_sha256),
        'frame':(prediction['frame_id'],evidence.frame_id),
        'image':(prediction['image_sha256'],evidence.image_sha256),
        'model':(prediction['model_sha256'],evidence.model_sha256),
        'target_map':(prediction['target_catalog_sha256'],geometry.target_catalog_sha256)}
    for name,(observed,expected) in bindings.items():
        if observed!=expected:
            raise ValueError(name+' evidence mismatch')
    if geometry.placement_observation_sha256==precision['observation_sha256']:
        raise ValueError('placement repeats precision evidence')
    reasons=[]
    if precision['abstain']: reasons.extend(precision['abstain_reasons'])
    if uncertainty is None:
        reasons.append('localization_uncertainty_missing')
    else:
        if not isinstance(uncertainty,MotionUncertaintyV2):
            raise ValueError('shared typed uncertainty required')
        if (uncertainty.qualification_sha256!=precision['qualification_sha256'] or
                uncertainty.domain_id!=precision['domain_id']):
            raise ValueError('uncertainty identity mismatch')
        reasons.append('qualification_registry_not_checked')
    # Never fill these gaps with scene confidence, coverage or caller timestamps.
    reasons.extend(['precision_observation_confidence_missing',
                    'precision_capture_clock_provenance_missing'])
    core=dict(schema='rocell.ai_precision_binding_preflight.v0',
        precision_observation_sha256=precision['observation_sha256'],
        evidence_sha256=canonical_hash(evidence.to_dict()),
        geometry_sha256=canonical_hash(geometry.to_dict()),
        decision='abstain',reasons=reasons,batch=None,
        hardware_writes=0,physical_movements=0,
        limitations=['Identity equality is not registry trust or physical qualification',
                    'Current precision schema cannot supply observation confidence or capture clock provenance'])
    return {**core,'report_sha256':canonical_hash(core)}

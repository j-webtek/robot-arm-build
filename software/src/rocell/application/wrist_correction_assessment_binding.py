"""Bind retained assessment bytes to a reviewed controller, without motion.

Historical identity matching does not establish current connection or pose.
The physical run still requires current metadata, fresh baseline and review.
"""
from dataclasses import dataclass
from .first_motion_contract import canonical
from .wizard_diagnostic_coordinator import decode_diagnostic_json
from .physical_connection_contracts import EvidenceOrigin
from .wrist_correction_saved_sources import assess_saved_correction_sources,load_saved_absolute_trial
from rocell.providers.windows.arm_feedback_worker import ReviewedControllerBinding
from rocell.providers.windows.wrist_correction_native_protocol import digest,require


@dataclass(frozen=True,slots=True)
class BoundCorrectionAssessment:
    canonical_bytes: bytes
    originals: tuple

    def to_dict(self):
        return decode_diagnostic_json(self.canonical_bytes,maximum=128*1024)


def bind_saved_correction_assessment(raw,*,expected_sha256,export_root,controller):
    require(type(raw) is bytes and digest(raw)==expected_sha256,'Retained correction assessment changed')
    assessment=decode_diagnostic_json(raw,maximum=128*1024)
    require(type(assessment) is dict and set(assessment)=={'schema','selected_originals','proposal','proposal_sha256',
        'motion_authorized','fresh_baseline_required','physical_provenance_verified'}
        and assessment['schema']=='rocell.saved_wrist_correction_assessment.v1' and canonical(assessment)==raw,
        'Exact saved assessment required')
    require(type(controller) is ReviewedControllerBinding and controller.origin is EvidenceOrigin.PHYSICAL_OBSERVATION,
        'Reviewed physical controller binding required')
    selected=assessment['selected_originals']
    require(type(selected) is list and 2<=len(selected)<=8,'Bounded assessed originals required')
    attempts=[row['attempt_id'] for row in selected]
    rebuilt=assess_saved_correction_sources(export_root,attempts)
    require(canonical(rebuilt)==raw,'Saved correction evidence changed since assessment')
    require(rebuilt['proposal']['status']=='OFFLINE_EXPERIMENT_CANDIDATE','Assessment has no eligible correction experiment')
    originals=[]
    unit=dict(vid=int(controller.identity.vid,16),pid=int(controller.identity.pid,16),serial_number=controller.identity.unit_serial)
    for row in selected:
        original,reference=load_saved_absolute_trial(export_root,row['attempt_id'])
        require(reference==row and original[0].to_dict()['usb_identity']==unit,
            'Selected correction original or controller unit differs')
        originals.append(original)
    # One final recheck prevents accepting a mixed set while source files change.
    require(canonical(assess_saved_correction_sources(export_root,attempts))==raw,
        'Correction assessment changed during controller binding')
    document=dict(schema='rocell.bound_wrist_correction_assessment.v1',assessment_sha256=expected_sha256,
        controller_sha256=controller.binding_sha256,usb_identity=unit,
        proposal_sha256=assessment['proposal_sha256'],proposal=assessment['proposal'],
        selected_originals=selected,motion_authorized=False,current_connection_verified=False,
        fresh_baseline_required=True,physical_accuracy_verified=False)
    return BoundCorrectionAssessment(canonical(document),tuple(originals))

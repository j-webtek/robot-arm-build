"""Typed v2 assembly only; caller supplies evidence, consumer owns admission.

No qualification is created here. Current perception has no qualified adapter.
This helper must not be represented as an end-to-end perception emitter.
"""
from dataclasses import dataclass
import json
from typing import Mapping
from rocell.models import (ActionPlan, Device, PressKey, Point3Mm, Interaction,
    ProposalDevice, ModelMotionBatchV2, ModelMotionProposalV2, MotionCapabilityV2,
    MotionGeometryV2, MotionEvidenceV2, MotionUncertaintyV2,
    decode_model_motion_batch_v2_json)


@dataclass(frozen=True)
class TargetObservationV2:
    target: Point3Mm
    observation_confidence: float


def assemble(plan: ActionPlan, *, batch_id: str, request_id: str,
             capability: MotionCapabilityV2, geometry: MotionGeometryV2,
             evidence: MotionEvidenceV2,
             observations: Mapping[str, TargetObservationV2],
             uncertainty: MotionUncertaintyV2 | None = None) -> bytes | None:
    """Return canonical shared bytes, or abstain without uncertainty evidence.

    Presence of uncertainty is NOT trust: independent ingress must resolve its
    qualification and all referenced evidence. Malformed inputs raise ValueError.
    Observation values must be derived from the precision evidence by the future
    perception adapter; this assembly function cannot attest to that derivation.
    """
    if uncertainty is None:
        return None
    if plan.device != Device.KEYBOARD or any(not isinstance(a, PressKey) for a in plan.actions):
        raise ValueError('keyboard PressKey plans only; phone needs fresh observation segments')
    if capability.profile_id != plan.profile_id:
        raise ValueError('capability profile differs from plan')
    proposals=[]
    for index, action in enumerate(plan.actions):
        key=action.key_id
        if key not in uncertainty.covered_target_ids:
            raise ValueError('target not covered by uncertainty')
        observation=observations.get(key)
        if not isinstance(observation, TargetObservationV2):
            raise ValueError('target observation missing or malformed')
        proposals.append(ModelMotionProposalV2(
            proposal_id=f'{batch_id}:{index}', action_index=index,
            device=ProposalDevice.KEYBOARD, target_id=key, target=observation.target,
            interaction=Interaction.CONTACT,
            observation_confidence=observation.observation_confidence))
    batch=ModelMotionBatchV2(batch_id=batch_id, request_id=request_id,
        intent_plan_sha256=plan.plan_hash, device=ProposalDevice.KEYBOARD,
        capability=capability, geometry=geometry, evidence=evidence,
        uncertainty=uncertainty, proposals=tuple(proposals))
    payload=json.dumps(batch.to_dict(),sort_keys=True,separators=(',',':'),
                       ensure_ascii=True,allow_nan=False).encode('utf-8')
    decode_model_motion_batch_v2_json(payload)
    return payload

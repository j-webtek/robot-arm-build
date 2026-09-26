"""AI producer for the shared ModelMotionBatch; offline keyboard research only."""
from rocell.application.model_motion_bridge import compile_model_motion_proposal
from rocell.models import ActionPlan, Device, ModelMotionBatch, ModelMotionProposal, PressKey
from rocell.targets import load_nominal_target_catalog
from .precision_observation import validate, qualification_for
from .scene_observation import canonical_hash
from .vision_fusion import fuse


def emit(*, plan: ActionPlan, request_id: str, batch_id: str, workspace, frame,
         scene_observation, precision_observation, evaluated_at_utc,
         trusted_qualifications=None, expected_domain_id=None):
    if not isinstance(plan,ActionPlan):
        raise TypeError('A compiled ActionPlan is required')
    # Phone state transitions need new evidence and a newly compiled segment.
    # Current precision v2 is keyboard-only; never reuse one image across a dialer task.
    if plan.device is not Device.KEYBOARD:
        raise ValueError('Phone batches require fresh observation per state-changing action; emitter currently supports keyboard only')
    if not 1<=len(plan.actions)<=64 or any(not isinstance(a,PressKey) for a in plan.actions):
        raise ValueError('Batch requires one to 64 keyboard movement actions')
    precision=validate(precision_observation)
    prediction=precision['prediction']
    catalog=load_nominal_target_catalog(workspace)
    targets=[a.key_id for a in plan.actions]
    decision=fuse(frame=frame,scene_observation=scene_observation,precision_observation=prediction,
                  device='keyboard',required_targets=targets,target_catalog_sha256=catalog.content_sha256,
                  evaluated_at_utc=evaluated_at_utc)
    reasons=list(decision['reasons'])
    q=qualification_for(precision,trusted_qualifications or {})
    if q is None:
        reasons.append('localization_uncalibrated' if precision['abstain'] else 'localization_qualification_untrusted')
    else:
        if expected_domain_id != precision['domain_id']:
            reasons.append('localization_domain_unverified')
        for key in targets:
            if key not in q['target_ids']:
                reasons.append('localization_target_unqualified')
                continue
            if key not in prediction['targets']:
                continue
            x,y,z=prediction['targets'][key]['center_board_mm']
            region=catalog.resolve('keyboard',key)
            left,front,right,rear=region.safe_rectangle_board_mm
            radius=q['error_bound_mm']
            if x-radius<left or x+radius>right or y-radius<front or y+radius>rear:
                reasons.append('localization_bound_outside_target')
    fusion_core={k:v for k,v in decision.items() if k!='decision_sha256'}
    fusion_core.update(schema='rocell.ai_precision_fusion.v1',precision_observation_sha256=precision['observation_sha256'],
                       qualification_sha256=None if q is None else q['qualification_sha256'],
                       reasons=list(dict.fromkeys(reasons)),accepted=not reasons,
                       localization_scope='SYNTHETIC_OFFLINE_ONLY')
    fusion={**fusion_core,'decision_sha256':canonical_hash(fusion_core)}
    batch=None
    if fusion['accepted']:
        proposals=[]
        for index,key in enumerate(targets):
            xyz=prediction['targets'][key]['center_board_mm']
            proposal=ModelMotionProposal.from_mapping({
                'schema':'rocell.model_motion_proposal.v1','proposal_id':f'{batch_id}-action-{index}',
                'device':'keyboard','target_id':key,'coordinate_frame':'board',
                'target_mm':dict(zip(('x','y','z'),xyz)), 'interaction':'CONTACT',
                'approach_clearance_mm':25.0,'speed_class':'SLOW','confidence':q['coverage_probability'],
                'source':{'model_id':prediction['model_sha256'],'frame_id':frame.frame_id,'image_sha256':frame.image_sha256}})
            compile_model_motion_proposal(proposal,catalog)
            proposals.append(proposal)
        batch=ModelMotionBatch(batch_id=batch_id,request_id=request_id,intent_plan_sha256=plan.plan_hash,
            scene_observation_sha256=scene_observation['observation_sha256'],
            precision_observation_sha256=precision['observation_sha256'],fusion_decision_sha256=fusion['decision_sha256'],
            proposals=tuple(proposals)).to_dict()
    core={'schema':'rocell.ai_batch_emission.v0','status':'EMITTED_OFFLINE_ONLY' if batch else 'ABSTAINED',
          'intent_plan_sha256':plan.plan_hash,'precision_observation':precision,'localization_qualification':q,'fusion':fusion,'batch':batch,
          'controller_commands':[],'hardware_writes':0,'physical_execution_authorized':False}
    return {**core,'emission_sha256':canonical_hash(core)}

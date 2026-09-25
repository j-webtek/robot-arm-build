"""Review saved synthetic product trials without opening any device or replaying."""
import hashlib
import json
from pathlib import Path
from .cartesian_export_review import validate_export_id
from .wizard_diagnostic_export import verify_export
from .wizard_diagnostic_coordinator import decode_diagnostic_json
from .physical_onboarding_durability import read_bounded_regular_file
from rocell.motion.characterization_plan import freeze_campaign
from rocell.arm.protocol import encode_line
from .endpoint_trial_contract import EndpointTrialRequest
from .wizard_endpoint_rehearsal import FAULTS


def _read(root, export_id, filename):
    folder=root/validate_export_id(export_id)  # Keep symlinks visible to verifier.
    verified=verify_export(folder)
    if not verified['valid']: raise ValueError('Source export verification failed')
    entries=[f for f in verified['files'] if f['name']==filename]
    if len(entries)!=1: raise ValueError('Required product attachment missing')
    raw=read_bounded_regular_file(folder/filename,maximum_bytes=1024*1024)
    digest=hashlib.sha256(raw).hexdigest()
    if digest!=entries[0]['sha256']: raise ValueError('Attachment changed during review')
    return decode_diagnostic_json(raw,maximum=1024*1024),digest


def review_product_case(workspace, export_id):
    root=Path(workspace).resolve()/'software/runs/wizard-exports'
    case,digest=_read(root,export_id,'attachment-product-case.json')
    if (case.get('schema')!='rocell.product_ghost_endpoints.v1'
            or case.get('physical_authority') is not False
            or case.get('native_device_opens')!=0 or case.get('physical_motion_commands')!=0):
        raise ValueError('Synthetic product case required')
    plan=freeze_campaign(case['plan']); trials=plan.to_dict()['trials']
    if (case.get('fault') not in FAULTS or type(case.get('fault_trial')) is not int
            or not 1<=case['fault_trial']<=len(trials)):
        raise ValueError('Known fault and bounded fault index required')
    if plan.sha256!=case['plan_sha256']: raise ValueError('Parent plan hash mismatch')
    refs=case['trial_exports']; mapping=case['trial_mapping']
    if not 1<=len(refs)<=len(trials) or len(mapping)!=len(trials):
        raise ValueError('Invalid trial references')
    if len({r['export'] for r in refs})!=len(refs): raise ValueError('Duplicate leg export')
    rows=[]
    for index,ref in enumerate(refs):
        leg,leg_hash=_read(root,ref['export'],'attachment-product-leg.json')
        actual_mapping={k:v for k,v in ref.items() if k!='export'}
        if (leg['parent_plan_sha256']!=plan.sha256 or leg['mapping']!=actual_mapping
                or actual_mapping!=mapping[index] or actual_mapping['trial_id']!=trials[index]['trial_id']):
            raise ValueError('Leg identity or mapping mismatch')
        result=leg['result']
        if (result.get('schema')!='rocell.wizard_endpoint_rehearsal.v1'
                or result.get('physical_authority') is not False
                or result.get('native_device_opens')!=0 or result.get('physical_motion_commands')!=0):
            raise ValueError('Synthetic leg evidence required')
        # Archive integrity alone cannot bind a valid but unrelated trial to
        # this route. Reconstruct exactly the one-leg input used by the runner.
        single=plan.to_dict(); single['trials']=[trials[index]]
        single['limits'].update(max_trials=1,max_duration_s=2)
        if result.get('input_plan_sha256')!=freeze_campaign(single).sha256:
            raise ValueError('Leg input plan differs from route')
        request=EndpointTrialRequest(json.dumps(result['request'],sort_keys=True,
            separators=(',',':'),ensure_ascii=True,allow_nan=False).encode('ascii'))
        requested=request.to_dict()
        if (requested['trial_id']!=trials[index]['trial_id']
                or requested['campaign']['trials']!=[trials[index]]
                or freeze_campaign(requested['campaign']).sha256!=result['synthetic_plan_sha256']
                or result['trial'].get('request_sha256')!=request.request_sha256):
            raise ValueError('Retained request differs from route or trial result')
        expected_wire=encode_line(request.goal().to_message()).decode('ascii')
        if any(wire!=expected_wire for wire in result['simulated_wire_writes']):
            raise ValueError('Retained command differs from requested endpoint')
        rows.append(dict(**actual_mapping,status=result['trial']['status'],fault=result['fault'],
            simulated_writes=len(result['simulated_wire_writes']),attachment_sha256=leg_hash))
    success=case['fault'] in ('NONE','DELAYED_ARRIVAL')
    expected=len(trials) if success else case['fault_trial']
    checks=dict(count=len(rows)==expected,
        preceding_verified=all(r['status']=='OBSERVED_ENDPOINT_DWELL' for r in rows[:-1]),
        final_outcome=(rows[-1]['status']=='OBSERVED_ENDPOINT_DWELL')==success,
        skipped=case['skipped_trial_ids']==[t['trial_id'] for t in trials[len(rows):]],
        writes=all(r['simulated_writes']==(0 if r['fault']=='BASELINE_MISMATCH' else 1) for r in rows),
        fault_mapping=all(r['fault']==(case['fault'] if i==case['fault_trial'] else 'NONE')
                          for i,r in enumerate(rows,1)))
    return dict(schema='rocell.product_ghost_export_review.v1',
        status='SAVED_SIMULATION_BEHAVIOR_VERIFIED' if all(checks.values()) else 'SAVED_SIMULATION_REVIEW_FAILED',
        source_export_id=export_id,source_attachment_sha256=digest,plan_sha256=plan.sha256,
        fault=case['fault'],planned=len(trials),attempted=len(rows),skipped=len(trials)-len(rows),
        checks=checks,legs=rows,hardware_access=False,motion_authorized=False,
        physical_accuracy_verified=False,replay_allowed=False)

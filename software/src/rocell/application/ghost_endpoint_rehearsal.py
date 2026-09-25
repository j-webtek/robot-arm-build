"""Finite ghost sequence through the existing owned endpoint runner, no hardware."""
import math
from rocell.motion.characterization_plan import SCHEMA, AXES, freeze_campaign
from .ghost_keyboard import rehearse_ghost_keyboard
from .wizard_endpoint_rehearsal import run_endpoint_rehearsal, FAULTS


def rehearse_ghost_endpoints(workspace, text='aba', *, fault='NONE', fault_trial=2):
    preview=rehearse_ghost_keyboard(workspace,text)
    if preview['status']!='SAMPLED_GHOST_ROUTE_PASS':
        raise ValueError('Ghost geometry did not pass')
    if fault not in FAULTS or type(fault_trial) is not int:
        raise ValueError('Known fault and integer trial index required')
    trials=[]; mapping=[]; noops=[]
    def pose(values):
        return dict(zip(AXES,(*values,0,math.pi)))
    for leg in preview['legs']:
        if leg['start']==leg['target']:
            noops.append(leg['sequence'])
            continue  # Already at travel point: never dispatch a zero-motion command.
        identifier=f"leg-{leg['sequence']}-{leg['key']}-{leg['phase']}"
        trials.append(dict(trial_id=identifier,command_family='T104',
            start=pose(leg['start']),target=pose(leg['target']),spd=.05,dwell_s=.5,timeout_s=2,
            stop=dict(max_read_gap_s=.1,position_tolerance_mm=.1,
                      angle_tolerance_rad=.01,max_endpoint_error_mm=.5)))
        mapping.append(dict(trial_id=identifier,leg_sequence=leg['sequence'],
                            key=leg['key'],phase=leg['phase']))
    if not 1<=fault_trial<=len(trials):
        raise ValueError('Fault trial is outside the nonzero-motion sequence')
    points=[p for t in trials for p in (t['start'],t['target'])]
    evidence=dict.fromkeys(('source_sha256','configuration_sha256','firmware_review_sha256',
                            'geometry_sha256'),preview['report_sha256'])
    evidence.update(usb_identity='SYNTHETIC',tool_payload_id='NO_INSTALLED_TOOL')
    plan=freeze_campaign(dict(schema=SCHEMA,campaign_id='ghost-keyboard-endpoints',frame='R_ctrl',
        evidence=evidence,trials=trials,limits=dict(
            minimum_pose={k:min(p[k] for p in points) for k in AXES},
            maximum_pose={k:max(p[k] for p in points) for k in AXES},
            max_translation_mm=40,max_rotation_rad=.01,min_spd=.05,max_spd=.05,
            max_trials=32,max_duration_s=64)))
    results=[]
    for index,trial in enumerate(trials,1):
        # The existing wizard runner intentionally accepts only small plans.
        # Submit one owned leg at a time; retain the parent sequence separately
        # rather than widening its limits or queuing commands past a fault.
        single=plan.to_dict()
        single['trials']=[trial]
        single['limits']['max_trials']=1
        single['limits']['max_duration_s']=2
        leg_plan=freeze_campaign(single)
        result=run_endpoint_rehearsal(workspace,dict(plan_json=leg_plan.canonical_bytes.decode(),
            trial_id=trial['trial_id'],fault=fault if index==fault_trial else 'NONE'))
        results.append(result)
        if result['trial']['status']!='OBSERVED_ENDPOINT_DWELL':
            break
    passed=len(results)==len(trials) and all(
        r['trial']['status']=='OBSERVED_ENDPOINT_DWELL' for r in results)
    return dict(schema='rocell.ghost_endpoint_rehearsal.v1',
        status='SIMULATED_SEQUENCE_COMPLETE' if passed else 'SIMULATED_SEQUENCE_STOPPED',
        basis='SYNTHETIC_WIRE_AND_ENDPOINTS',preview_sha256=preview['report_sha256'],
        layout_sha256=preview['layout_sha256'],requested_keys=preview['requested_keys'],
        plan=plan.to_dict(),plan_sha256=plan.sha256,trial_mapping=mapping,
        no_motion_leg_sequences=noops,trial_results=results,
        skipped_trial_ids=[t['trial_id'] for t in trials[len(results):]],
        fault=fault,fault_trial=fault_trial,automatic_retry_allowed=False,
        native_device_opens=0,physical_motion_commands=0,camera_required=False,
        physical_authority=False,physical_accuracy_verified=False,
        limitations=['Each owned leg receives synthetic baseline/endpoint samples.',
            'No servo-dynamics model, physical key event or full-arm clearance proof.',
            'Synthetic reviews cannot authorize native execution.'])

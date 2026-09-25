"""Product-size route through synthetic owned endpoint trials, never hardware."""
import math
from rocell.motion.characterization_plan import AXES, SCHEMA, freeze_campaign
from .product_ghost_controller_bridge import bridge_product_ghost
from .product_ghost_interpolation import screen_product_ghost
from .wizard_endpoint_rehearsal import FAULTS, run_endpoint_rehearsal


def rehearse_product_endpoints(workspace, source, *, fault='NONE', fault_trial=2):
    if fault not in FAULTS or type(fault_trial) is not int:
        raise ValueError('Known fault and integer trial required')
    screen=screen_product_ghost(source)
    if screen['status']!='REFERENCE_INTERPOLATION_PASS':
        raise ValueError('Complete interpolation pass required')
    bridge=bridge_product_ghost(source)
    trials=[]; mapping=[]; noops=[]
    for leg in bridge['legs']:
        samples=[bridge['samples'][leg[k]] for k in ('start_sequence','target_sequence')]
        poses=[dict(zip(AXES,(*s['controller_reference_xyz_pitch'],
                             s['solved_arm_joints_rad']['r'],math.pi))) for s in samples]
        if poses[0]==poses[1]:
            noops.append(leg['sequence'])
            continue
        identifier=f"product-leg-{leg['sequence']}"
        trials.append(dict(trial_id=identifier,command_family='T104',start=poses[0],target=poses[1],
            spd=.05,dwell_s=.5,timeout_s=2,stop=dict(max_read_gap_s=.1,
                position_tolerance_mm=.1,angle_tolerance_rad=.01,max_endpoint_error_mm=.5)))
        mapping.append(dict(trial_id=identifier,leg_sequence=leg['sequence'],
            key=samples[1]['key'],phase=samples[1]['phase'],action_index=samples[1]['action_index']))
    if not 1<=fault_trial<=len(trials):
        raise ValueError('Fault index outside nonzero route')
    points=[p for t in trials for p in (t['start'],t['target'])]
    evidence=dict(source_sha256=bridge['source_report_sha256'],configuration_sha256=bridge['report_sha256'],
        firmware_review_sha256=bridge['reference_sha256'],geometry_sha256=screen['report_sha256'],
        usb_identity='SYNTHETIC',tool_payload_id='ASSUMED_100MM_NO_INSTALLED_TOOL')
    plan=freeze_campaign(dict(schema=SCHEMA,campaign_id='product-ghost-endpoints',frame='R_ctrl',
        evidence=evidence,trials=trials,limits=dict(
            minimum_pose={k:min(p[k] for p in points) for k in AXES},
            maximum_pose={k:max(p[k] for p in points) for k in AXES},
            max_translation_mm=40,max_rotation_rad=.1,min_spd=.05,max_spd=.05,
            max_trials=128,max_duration_s=256)))
    results=[]
    for index,trial in enumerate(trials,1):
        # Preserve the existing runner's small-plan limits. Never queue a
        # subsequent leg until the current owned trial verifies its endpoint.
        single=plan.to_dict(); single['trials']=[trial]
        single['limits'].update(max_trials=1,max_duration_s=2)
        leg_plan=freeze_campaign(single)
        result=run_endpoint_rehearsal(workspace,dict(plan_json=leg_plan.canonical_bytes.decode(),
            trial_id=trial['trial_id'],fault=fault if index==fault_trial else 'NONE'))
        results.append(result)
        if result['trial']['status']!='OBSERVED_ENDPOINT_DWELL': break
    passed=len(results)==len(trials) and all(r['trial']['status']=='OBSERVED_ENDPOINT_DWELL' for r in results)
    return dict(schema='rocell.product_ghost_endpoints.v1',
        status='SIMULATED_SEQUENCE_COMPLETE' if passed else 'SIMULATED_SEQUENCE_STOPPED',
        basis='SYNTHETIC_WIRE_AND_ENDPOINTS',plan=plan.to_dict(),plan_sha256=plan.sha256,
        bridge_sha256=bridge['report_sha256'],interpolation=screen,trial_mapping=mapping,
        no_motion_leg_sequences=noops,trial_results=results,
        skipped_trial_ids=[t['trial_id'] for t in trials[len(results):]],fault=fault,fault_trial=fault_trial,
        automatic_retry_allowed=False,native_device_opens=0,physical_motion_commands=0,
        physical_authority=False,physical_accuracy_verified=False,camera_required=False,
        limitations=['Synthetic baseline and endpoint samples, not servo dynamics or acquisition freshness.',
                    '100 mm tool and constant gripper are simulation assumptions, not installed calibration.',
                    'No approach from current live pose, physical clearance or actual key event is verified.'])

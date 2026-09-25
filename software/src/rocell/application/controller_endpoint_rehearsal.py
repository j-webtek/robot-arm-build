"""Connect a retained controller snapshot to the existing endpoint workflow.

This is deliberately incapable: reviews and observations are synthetic, no
hardware provider is selected, and generated plans cannot authorize dispatch.
"""
import hashlib

from rocell.motion.characterization_plan import SCHEMA, freeze_campaign
from rocell.motion.characterization_controller import controller_campaign_preview
from .controller_route_preview import preview_vertical_pair
from .wizard_endpoint_rehearsal import run_endpoint_rehearsal, FAULTS


def vertical_rehearsal_plan(feedback):
    """Translate a screened +2 mm/return pair to the existing campaign contract."""
    preview = preview_vertical_pair(feedback)
    if preview['status'] != 'PREVIEW_ONLY_NOT_EXECUTABLE':
        raise ValueError('Reference route preview did not pass')
    x,y,z,pitch = preview['starting_pose']
    start = dict(x_mm=x,y_mm=y,z_mm=z,pitch_rad=pitch,
                 roll_rad=feedback['joints_rad']['r'],gripper_rad=feedback['joints_rad']['g'])
    target = dict(start,z_mm=z+2)
    # Labels identify synthetic assumptions, never a received-unit approval.
    digest = hashlib.sha256(b'CONTROLLER_VERTICAL_REHEARSAL_ONLY').hexdigest()
    evidence = dict.fromkeys(('source_sha256','configuration_sha256',
                             'firmware_review_sha256','geometry_sha256'), digest)
    evidence.update(usb_identity='SYNTHETIC',tool_payload_id='UNQUALIFIED')
    trials = []
    for name,a,b in (('out',start,target),('return',target,start)):
        trials.append(dict(trial_id=name,command_family='T104',start=a,target=b,
            spd=.05,dwell_s=.5,timeout_s=2,
            stop=dict(max_read_gap_s=.1,position_tolerance_mm=.1,
                      angle_tolerance_rad=.01,max_endpoint_error_mm=.5)))
    plan = freeze_campaign(dict(schema=SCHEMA,campaign_id='controller-vertical-rehearsal',
        frame='R_ctrl',evidence=evidence,trials=trials,
        limits=dict(minimum_pose={k:min(start[k],target[k]) for k in start},
                    maximum_pose={k:max(start[k],target[k]) for k in start},
                    max_translation_mm=2,max_rotation_rad=.01,min_spd=.05,
                    max_spd=.05,max_trials=2,max_duration_s=4)))
    return plan


def rehearse_vertical_endpoints(workspace, feedback, *, first_fault='NONE'):
    """Exercise typed T104, baseline checks, one write, endpoint and cleanup.

    Each leg uses the existing owned-trial implementation with incapable I/O.
    Only a clean observed endpoint allows the modeled return trial to start.
    Synthetic time and exact target feedback do not predict physical accuracy.
    """
    if first_fault not in FAULTS:
        raise ValueError('Unknown rehearsal fault')
    plan = vertical_rehearsal_plan(feedback)
    controller = controller_campaign_preview(plan)
    if controller['reference_ik_status'] != 'REFERENCE_IK_PASS':
        raise ValueError('Controller interpolation reference screen did not pass')
    results = []
    for trial in plan.to_dict()['trials']:
        result = run_endpoint_rehearsal(workspace, dict(
            plan_json=plan.canonical_bytes.decode(),trial_id=trial['trial_id'],
            fault=first_fault if not results else 'NONE'))
        results.append(result)
        if result['trial']['status'] != 'OBSERVED_ENDPOINT_DWELL':
            break
    passed = len(results)==2 and all(r['trial']['status']=='OBSERVED_ENDPOINT_DWELL' for r in results)
    return dict(schema='rocell.controller_endpoint_rehearsal.v1',
        status='SIMULATED_PAIR_COMPLETE' if passed else 'SIMULATED_PAIR_STOPPED',
        basis='SYNTHETIC_ENDPOINTS_FROM_RETAINED_START',
        source_response_sha256=feedback.get('response_sha256'),
        plan=plan.to_dict(),plan_sha256=plan.sha256,controller_model=controller,
        trial_results=results,skipped_trial_ids=[t['trial_id'] for t in plan.to_dict()['trials'][len(results):]],
        native_device_opens=0,physical_motion_commands=0,physical_authority=False,
        physical_accuracy_verified=False,
        limitations=['Retained start is not fresh live feedback.',
                     'Post-command poses and reviews are synthetic, not measured.',
                     'Nominal coefficient, tolerances and timeouts are rehearsal settings only.',
                     'No live Wi-Fi Cartesian adapter or clearance approval is supplied.'])

"""Closed, file/device-free movement preview and simulation for the wizard.

The editable default is a synthetic example, not the received arm's pose or a
placement calibration. Content hashes do not authenticate its evidence labels.
"""

import json

from rocell.motion.characterization_plan import freeze_campaign
from rocell.motion.characterization_sim import simulate_campaign


def example_plan_text():
    from .wizard_actions import example_plan_text as catalog_example
    return catalog_example()


def parse_plan(text):
    if type(text) is not str or len(text)>6000:
        raise ValueError('Plan text exceeds wizard budget')
    def unique(pairs):
        result={}
        for key,value in pairs:
            if key in result:
                raise ValueError('Duplicate plan field')
            result[key]=value
        return result
    try:
        plan=freeze_campaign(json.loads(text,object_pairs_hook=unique))
    except (RecursionError, OverflowError) as error:
        raise ValueError('Plan complexity exceeds wizard budget') from error
    data=plan.to_dict()
    if len(data['trials'])>4 or sum(t['timeout_s'] for t in data['trials'])>20:
        raise ValueError('Wizard rehearsal is limited to four trials and 20 modeled seconds')
    return plan


def parse_transform(text, frame):
    from rocell.models.frames import Transform
    if text == 'null':
        return None
    matrix=json.loads(text)
    if type(matrix) is not list or len(matrix)!=16:
        raise ValueError('Transform requires 16 row-major matrix values or null')
    return Transform('board',frame,tuple(matrix))


def run_campaign(action_id, values, workspace=None):
    plan=parse_plan(values['plan_json'])
    from rocell.motion.characterization_controller import controller_campaign_preview
    report={'schema':'rocell.wizard_movement_campaign.v1','plan':plan.to_dict(),
            'preview':plan.preview(),'basis':'SYNTHETIC_REHEARSAL',
            'message':'No device access. Geometry and live command admission remain unqualified.',
            'physical_authority':False}
    report['controller_model']=controller_campaign_preview(plan)
    if workspace is not None:
        from rocell.simulation.scene import load_rc03_nominal_scene
        from rocell.motion.characterization_geometry import check_campaign_geometry
        scene=load_rc03_nominal_scene(workspace/'active-project/RoCell_v0_3')
        transform=parse_transform(values['board_transform_json'],plan.to_dict()['frame'])
        report['geometry']=check_campaign_geometry(plan,scene,transform,clearance_mm=values['clearance_mm'])
    if action_id=='movement_campaign_simulate':
        first=plan.to_dict()['trials'][0]['trial_id']
        blocked=tuple(row['trial_id'] for row in report.get('geometry',{}).get('trial_checks',[])
                      if not row['nominal_tip_clear'])
        report['simulation']=simulate_campaign(plan,travel_s=.5,sample_period_s=.05,
                                              faults={first:values['fault']},blocked_trial_ids=blocked)
        from rocell.arm.movement_campaign_analysis import summarize_campaign, summarize_endpoint_campaign
        observations = [
            {'trial_id': row['trial_id'], 'outcome': row['status'], 'evidence': row['wire_evidence']}
            for row in report['simulation']['trial_results']]
        report['campaign_analysis']=summarize_campaign(plan, observations)
        # Evaluate the weaker endpoint contract against the same synthetic
        # bytes. Copy the evidence mapping: never relabel the continuous report
        # in place, and never treat modeled output as received-unit telemetry.
        report['endpoint_campaign_analysis']=summarize_endpoint_campaign(plan, [
            dict(row,evidence=dict(row['evidence'],observation_contract='SUPERVISED_ENDPOINT_ONLY')
                 if row['evidence'] is not None else None) for row in observations])
    elif action_id!='movement_campaign_preview':
        raise ValueError('Unsupported campaign action')
    return report

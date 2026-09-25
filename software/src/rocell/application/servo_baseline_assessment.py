"""Independently recompute elbow baseline admission from retained read bytes."""
from .servo_acquisition_pair import assess_acquisition_pair

LIMITS={'maximum_delta_counts':(1,64),'settled_tolerance_counts':(0,16),
        'maximum_pair_us':(1,1000000),'maximum_age_us':(1,1000000)}


def validate_baseline_policy(policy):
    if type(policy) is not dict or set(policy)!=set(LIMITS):raise ValueError('Exact baseline policy required')
    for key,(low,high) in LIMITS.items():
        if type(policy[key]) is not int or not low<=policy[key]<=high:
            raise ValueError('Invalid baseline policy limit')


def assess_baseline(record,receipt,dispatch,write_started_us,policy):
    validate_baseline_policy(policy)
    if (type(record) is not dict or set(record)!=set(LIMITS)|{'schema','accepted','reason','acquisition'}
            or record['schema']!='rocell.elbow_baseline.v1'):
        raise ValueError('Versioned baseline evidence required')
    if any(record[key]!=value or type(record[key]) is not int for key,value in policy.items()):
        raise ValueError('Baseline limits differ from frozen plan')
    pair=record['acquisition']
    assessed=assess_acquisition_pair(pair,boot_id=dispatch['boot_id'],command_id=dispatch['command_id'],
        servo_id=14,dispatch_us=receipt['received_us'],previous_sequence=-1,previous_finished_us=0,
        maximum_pair_us=policy['maximum_pair_us'])
    if assessed['status']!='REFERENCE_READ_PAIR_COMPLETE' or pair['byte_order']!='little':
        raise ValueError('Incomplete baseline acquisition')
    finish=assessed['last_finished_us']
    if (type(write_started_us) is not int or not finish<write_started_us<=dispatch['device_us']
            or write_started_us-finish>policy['maximum_age_us']):
        raise ValueError('Baseline stale or out of order at write start')
    position=assessed['decoded']['feedback']['position']['decoded_value']
    goal=assessed['decoded']['target']['decoded_value']
    moving=assessed['decoded']['feedback']['moving']['decoded_value']
    if not 1024<=position<=3071 or not 1024<=goal<=3071:
        raise ValueError('Baseline outside elbow profile')
    tracking=abs(position-goal);delta=abs(dispatch['wire_count']-position)
    if (moving!=0 or tracking>policy['settled_tolerance_counts'] or
            delta>policy['maximum_delta_counts'] or record['accepted'] is not True or
            record['reason']!='BASELINE_ACCEPTED'):
        raise ValueError('Baseline does not support dispatch')
    return dict(schema='rocell.baseline_assessment.v1',position_count=position,goal_count=goal,
        tracking_error_counts=tracking,requested_delta_counts=delta,age_at_write_us=write_started_us-finish,
        recomputed_accepted=True,progression_authority=False,physical_clearance_verified=False)

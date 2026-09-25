"""Independently check compact whole-arm baseline bytes against frozen policy."""
from .servo_diagnostic_contract import _integer, _identifier
from .servo_register_reference import PROFILE_ID
from .servo_acquisition_pair import assess_acquisition_pair


def validate_whole_arm_policy(policy):
    fields={'joints','tracking_tolerance','maximum_pair_us','maximum_scan_us','maximum_age_us'}
    if type(policy) is not dict or set(policy)!=fields:
        raise ValueError('Exact whole-arm policy required')
    if type(policy['joints']) is not list or len(policy['joints'])!=7:
        raise ValueError('Seven controller-reviewed joint windows required')
    for window in policy['joints']:
        if type(window) is not list or len(window)!=2:
            raise ValueError('Invalid joint window')
        _integer(window[0],0,4095);_integer(window[1],window[0],4095)
    _integer(policy['tracking_tolerance'],0,16)
    _integer(policy['maximum_pair_us'],1,1000000)
    _integer(policy['maximum_scan_us'],1,7000000)
    _integer(policy['maximum_age_us'],1,1000000)


def assess_whole_arm_baseline(record, *, boot_id, command_id, policy, boundary_us, write_started_us):
    validate_whole_arm_policy(policy);_identifier(boot_id);_identifier(command_id)
    _integer(boundary_us);_integer(write_started_us)
    fields={'schema','boot_id','command_id','profile_id','byte_order','accepted','reason','checked_us','policy','reads'}
    if (type(record) is not dict or set(record)!=fields or record['schema']!='rocell.whole_arm_baseline.v1'
            or record['boot_id']!=boot_id or record['command_id']!=command_id
            or record['profile_id']!=PROFILE_ID or record['byte_order']!='little'):
        raise ValueError('Invalid whole-arm evidence envelope')
    validate_whole_arm_policy(record['policy'])
    if record['policy']!=policy:raise ValueError('Whole-arm policy differs from frozen expectations')
    rows=record['reads']
    if type(rows) is not list or len(rows)!=7:raise ValueError('Incomplete whole-arm scan')
    previous_sequence=-1;previous_finished=boundary_us;first=None;positions=[]
    for index,row in enumerate(rows):
        if type(row) is not list or len(row)!=2:raise ValueError('Invalid joint read pair')
        pair=dict(schema='rocell.servo_acquisition_pair.v1',profile_id=PROFILE_ID,byte_order='little')
        for name,read,address,width in zip(('target','feedback'),row,(42,56),(2,15)):
            if type(read) is not list or len(read)!=7:raise ValueError('Invalid compact read')
            sequence,start,finish,returned,error,success,raw=read
            _integer(returned,-2**31,2**31-1);_integer(error,-1,255)
            if type(success) is not bool or (success and (returned!=width or error!=0)):
                raise ValueError('Contradictory read result')
            if sequence!=index*2+(name=='feedback') or type(sequence) is not int:
                raise ValueError('Whole-arm sequence mismatch')
            pair[name]=dict(boot_id=boot_id,command_id=command_id,servo_id=11+index,
                sequence=sequence,read_started_us=start,read_finished_us=finish,address=address,width=width,
                status='SUCCEEDED' if success else 'FAILED',device_error=error if error>=0 else None,raw_hex=raw)
        assessed=assess_acquisition_pair(pair,boot_id=boot_id,command_id=command_id,servo_id=11+index,
            dispatch_us=boundary_us,previous_sequence=previous_sequence,previous_finished_us=previous_finished,
            maximum_pair_us=policy['maximum_pair_us'])
        if assessed['status']!='REFERENCE_READ_PAIR_COMPLETE':raise ValueError('Whole-arm read failed')
        if first is None:first=pair['target']['read_started_us']
        previous_sequence=assessed['last_sequence'];previous_finished=assessed['last_finished_us']
        feedback=assessed['decoded']['feedback'];position=feedback['position']['decoded_value']
        target=assessed['decoded']['target']['decoded_value'];low,high=policy['joints'][index]
        if (not low<=position<=high or not low<=target<=high or feedback['moving']['decoded_value']!=0
                or abs(position-target)>policy['tracking_tolerance']):
            raise ValueError('Whole-arm state outside admitted window')
        positions.append(position)
    checked=_integer(record['checked_us'])
    if (not previous_finished<=checked<=write_started_us or previous_finished-first>policy['maximum_scan_us']
            or write_started_us-first>policy['maximum_age_us']):
        raise ValueError('Whole-arm baseline stale or timing invalid')
    if record['accepted'] is not True or record['reason']!='WHOLE_ARM_BASELINE_ACCEPTED':
        raise ValueError('Whole-arm baseline rejected by controller')
    return dict(schema='rocell.whole_arm_baseline_assessment.v1',positions=positions,
        oldest_read_age_at_write_us=write_started_us-first,recomputed_accepted=True,
        progression_authority=False,physical_clearance_verified=False,simultaneous=False)

"""Offline v1 diagnostic trace validation, not a deployed firmware protocol.

Device timestamps share one boot-scoped clock. Target readback means a successful
servo-register read, never an echo of the host request. No verdict grants motion
authority; native adapters must independently establish provenance and support.
"""
import hashlib
import math
import re
from .first_motion_contract import canonical


def _integer(value, low=0, high=2**63-1):
    if type(value) is not int or not low<=value<=high:
        raise ValueError('Bounded integer required')
    return value


def _identifier(value):
    if type(value) is not str or not re.fullmatch(r'[A-Za-z0-9_.-]{1,128}',value):
        raise ValueError('Bounded identifier required')
    return value


def assess_trace(trace):
    return _assess_trace(trace, signed_positions=False)


def _assess_trace(trace, *, signed_positions):
    """Assess a single-joint diagnostic trace; reject contradictory records.

Thresholds are frozen by the caller before collection. Endpoint success needs
fresh reads spanning a settling interval, not just a matching last sample.
"""
    if trace.get('schema')!='rocell.servo_diagnostic_trace.v1':
        raise ValueError('Unsupported trace schema')
    origin=trace.get('origin')
    if origin not in ('SIMULATION','DEVICE_CAPTURE'):
        raise ValueError('Explicit evidence origin required')
    command=trace['command'];dispatch=trace['dispatch'];samples=trace['samples']
    boot=_identifier(command['boot_id']);cid=_identifier(command['command_id'])
    servo=_integer(command['servo_id'],1,253)
    _identifier(command['conversion_version'])
    if command['angle_units']!='rad' or command['position_units']!='count':
        raise ValueError('Explicit supported units required')
    for key in ('desired_rad','wire_rad'):
        value=command[key]
        if type(value) not in (int,float) or not math.isfinite(value):
            raise ValueError('Finite joint angle required')
    for key in ('desired_count','wire_count'):_integer(command[key],0,65535)
    payload=command['payload']
    if (set(payload)!={'T','joint','rad','spd','acc'} or type(payload['T']) is not int
            or payload['T']!=101 or _integer(payload['joint'],1,6)!=command['joint']
            or payload['rad']!=command['wire_rad']):
        raise ValueError('Exact single-joint payload binding required')
    _integer(command['joint'],1,6)
    _integer(payload['spd'],1,65535);_integer(payload['acc'],1,255)
    if hashlib.sha256(canonical(payload)).hexdigest()!=command['payload_sha256']:
        raise ValueError('Payload hash mismatch')
    if (dispatch['boot_id']!=boot or dispatch['command_id']!=cid
            or dispatch['servo_id']!=servo or dispatch['wire_count']!=command['wire_count']
            or dispatch['speed']!=payload['spd'] or dispatch['acceleration']!=payload['acc']):
        raise ValueError('Controller dispatch correlation mismatch')
    sent=_integer(dispatch['device_us'])
    _integer(dispatch['servo_id'],1,253)
    _integer(dispatch['wire_count'],0,65535)
    _integer(dispatch['speed'],1,65535);_integer(dispatch['acceleration'],1,255)
    bus=dispatch['bus_write_status']
    if bus not in ('SUCCEEDED','FAILED','UNKNOWN','NOT_ATTEMPTED'):
        raise ValueError('Explicit bus-write status required')
    policy=trace['policy']
    tolerance=_integer(policy['tolerance_counts'],0,100)
    settle=_integer(policy['settle_us'],1)
    gap=_integer(policy['maximum_gap_us'],1)
    if type(samples) is not list or len(samples)>2000:
        raise ValueError('Bounded sample list required')
    last=sent;seq=-1;stable=None;good=0;faults=[];accepted=False;fresh=0
    final_error=None
    for sample in samples:
        _integer(sample['servo_id'],1,253)
        if (sample['boot_id']!=boot or sample['command_id']!=cid or sample['servo_id']!=servo):
            raise ValueError('Sample belongs to another boot, command or servo')
        current_seq=_integer(sample['sequence'])
        begin=_integer(sample['read_started_us']);end=_integer(sample['read_finished_us'])
        if current_seq<=seq or not last<begin<=end:
            raise ValueError('Duplicate, stale or out-of-order acquisition')
        if end-last>gap:faults.append('ACQUISITION_GAP')
        last=end;seq=current_seq
        status=sample['position_read_status']
        target_status=sample['target_read_status']
        if status not in ('SUCCEEDED','FAILED','UNSUPPORTED') or target_status not in ('SUCCEEDED','FAILED','UNSUPPORTED'):
            raise ValueError('Explicit acquisition status required')
        position=sample['position_count'];target=sample['target_count']
        if status=='SUCCEEDED':_integer(position,-32767 if signed_positions else 0,65535);fresh+=1
        elif position is not None:raise ValueError('Failed position read must not supply cached value')
        if target_status=='SUCCEEDED':
            _integer(target,0,65535)
            if target!=command['wire_count']:faults.append('TARGET_READBACK_MISMATCH')
            else:accepted=True
        elif target is not None:raise ValueError('Unavailable target readback must be null')
        if status!='SUCCEEDED':faults.append('POSITION_ACQUISITION_UNAVAILABLE')
        if target_status!='SUCCEEDED':faults.append('TARGET_READBACK_UNAVAILABLE')
        final_error=position-command['desired_count'] if status=='SUCCEEDED' else None
        eligible=(status=='SUCCEEDED' and target_status=='SUCCEEDED'
                  and target==command['wire_count'] and abs(final_error)<=tolerance)
        if eligible:
            if stable is None:stable=end
            good+=1
        else:stable=None;good=0
    settled=stable is not None and last-stable>=settle and good>=3
    if bus!='SUCCEEDED':category='BUS_DISPATCH_NOT_VERIFIED'
    elif faults:category='DIAGNOSTIC_EVIDENCE_INCOMPLETE_OR_CONTRADICTORY'
    elif not samples:category='NO_ACQUISITIONS'
    elif settled:category='DIAGNOSTIC_ENDPOINT_CRITERIA_MET'
    else:category='FRESH_POSITION_NOT_SETTLED_AT_DESIRED_TARGET'
    return dict(schema='rocell.servo_diagnostic_assessment.v1',origin=origin,
        category=category,issues=sorted(set(faults)),fresh_position_samples=fresh,
        matching_target_readback_observed=accepted,final_desired_error_counts=final_error,
        physical_accuracy_verified=False,provenance_verified=False,
        progression_authority=False,automatic_retry_allowed=False)

"""Immutable, hash-bound expectations for a single diagnostic session."""
import base64
import hashlib
from dataclasses import dataclass
from .first_motion_contract import canonical
from .servo_diagnostic_decode import decode_trace
from .servo_session_assessment import assess_session
from .wizard_diagnostic_coordinator import decode_diagnostic_json
from .servo_baseline_assessment import validate_baseline_policy
from .servo_authorization_record import assess_authorization
from .servo_whole_arm_baseline import validate_whole_arm_policy, assess_whole_arm_baseline


@dataclass(frozen=True)
class SessionPlan:
    encoded: bytes

    @property
    def sha256(self):
        return hashlib.sha256(self.encoded).hexdigest()

    def to_dict(self):
        return decode_diagnostic_json(self.encoded,maximum=16384)


def freeze_session_plan(command,policy,sent_bytes,schedule,*,origin,baseline_policy=None,whole_arm_policy=None):
    if origin not in ('SIMULATION','DEVICE_CAPTURE') or type(sent_bytes) is not bytes or not 1<=len(sent_bytes)<=256:
        raise ValueError('Explicit origin and bounded command bytes required')
    if decode_diagnostic_json(sent_bytes,maximum=256)!=command['payload']:
        raise ValueError('Sent payload differs from expected command')
    limits={'sample_count':(1,11),'sample_interval_us':(1000,60000000),
            'maximum_lateness_us':(1000,60000000),'maximum_pair_us':(1,60000000)}
    if type(schedule) is not dict or set(schedule)!=set(limits):
        raise ValueError('Exact supported sampling schedule required')
    for key,(low,high) in limits.items():
        if type(schedule[key]) is not int or not low<=schedule[key]<=high:
            raise ValueError('Sampling schedule outside candidate capacity')
    if (schedule['maximum_lateness_us']!=schedule['sample_interval_us'] or
            schedule['maximum_pair_us']>schedule['sample_interval_us'] or
            schedule['maximum_pair_us']!=policy['maximum_pair_us']):
        raise ValueError('Sampling schedule/policy mismatch')
    if command['joint']!=3 or command['servo_id']!=14:
        raise ValueError('Initial candidate supports elbow only')
    # Validate the complete existing command/policy contract with zero samples.
    # This hypothetical dispatch validates shape only; it is never stored as
    # device evidence or used to claim execution.
    dispatch={key:command[key] for key in ('boot_id','command_id','servo_id','wire_count')}
    dispatch.update(speed=command['payload']['spd'],acceleration=command['payload']['acc'],
                    device_us=0,bus_write_status='UNKNOWN')
    decode_trace(canonical(dict(schema='rocell.servo_diagnostic_trace.v2',origin=origin,
        command=command,policy=policy,dispatch=dispatch,samples=[])))
    document=dict(schema='rocell.session_plan.v1',origin=origin,command=command,
        policy=policy,schedule=schedule,sent_base64=base64.b64encode(sent_bytes).decode('ascii'))
    if baseline_policy is not None:
        validate_baseline_policy(baseline_policy)
        if schedule['sample_count']>10:raise ValueError('Baseline capture capacity exceeded')
        document.update(schema='rocell.session_plan.v2',baseline_policy=baseline_policy)
    if whole_arm_policy is not None:
        validate_whole_arm_policy(whole_arm_policy)
        if baseline_policy is None or schedule['sample_count']>8:
            raise ValueError('Whole-arm plan requires elbow baseline and at most eight pairs')
        document.update(schema='rocell.session_plan.v3',whole_arm_policy=whole_arm_policy)
    encoded=canonical(document)
    if len(encoded)>16384:raise ValueError('Session plan byte budget exceeded')
    return SessionPlan(encoded)


def assess_planned_session(snapshot,plan):
    document=plan.to_dict()
    fields={'schema','origin','command','policy','schedule','sent_base64'}
    v3=document.get('schema')=='rocell.session_plan.v3'
    v2=document.get('schema')=='rocell.session_plan.v2' or v3
    if v2:fields.add('baseline_policy')
    if v3:fields.add('whole_arm_policy')
    if set(document)!=fields or document['schema'] not in ('rocell.session_plan.v1','rocell.session_plan.v2','rocell.session_plan.v3'):
        raise ValueError('Invalid session plan envelope')
    sent=base64.b64decode(document['sent_base64'],validate=True)
    # Revalidate persisted or caller-constructed plans, not merely their hashes.
    verified=freeze_session_plan(document['command'],document['policy'],sent,document['schedule'],origin=document['origin'],baseline_policy=document.get('baseline_policy'),whole_arm_policy=document.get('whole_arm_policy'))
    if verified.encoded!=plan.encoded:raise ValueError('Noncanonical session plan')
    authorization=None
    authorization_body=None;whole_arm=None
    if snapshot['records'] and snapshot['records'][0]['kind']=='authorization':
        authorization_body=snapshot['records'][0]['record']
        authorization=assess_authorization(snapshot['records'][0]['record'],plan,snapshot['records'][1:])
        snapshot=dict(snapshot,records=snapshot['records'][1:])
    if v3:
        if authorization_body is None or not snapshot['records'] or snapshot['records'][0]['kind']!='whole_arm':
            raise ValueError('Whole-arm plan requires authorization and whole-arm evidence')
        whole_record=snapshot['records'][0]['record']
        snapshot=dict(snapshot,records=snapshot['records'][1:])
        hooks=[item['record'] for item in snapshot['records'] if item['kind']=='hook']
        if len(hooks)!=1 or not snapshot['records'] or snapshot['records'][0]['kind']!='receipt':
            raise ValueError('Whole-arm capture lacks write boundary')
        whole_arm=assess_whole_arm_baseline(whole_record,boot_id=document['command']['boot_id'],
            command_id=document['command']['command_id'],policy=document['whole_arm_policy'],
            boundary_us=authorization_body['received_us'],write_started_us=int(hooks[0]['started_us_raw']))
        if whole_record['checked_us']>snapshot['records'][0]['record']['received_us']:
            raise ValueError('Whole-arm scan overlaps command receipt')
    index=2 if v2 else 1
    if len(snapshot['records'])<=index or snapshot['records'][index]['kind']!='converted':
        raise ValueError('Missing conversion schedule')
    converted=snapshot['records'][index]['record']
    if any(converted.get(key)!=value or type(converted.get(key)) is not int
           for key,value in document['schedule'].items()):
        raise ValueError('Controller sampling differs from frozen plan')
    result=assess_session(snapshot,sent,document['command'],document['policy'],origin=document['origin'],baseline_policy=document.get('baseline_policy'))
    if authorization is not None:result=dict(result,start_record=authorization)
    if whole_arm is not None:result=dict(result,whole_arm_baseline=whole_arm)
    return dict(result,session_plan_sha256=plan.sha256)

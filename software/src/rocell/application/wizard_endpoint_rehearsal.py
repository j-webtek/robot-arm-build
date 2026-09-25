"""Incapable wizard rehearsal of the complete owned-session endpoint sequence.

Synthetic reviews stay internal, the permit is revoked before return, and no
native/serial provider is imported. The clock models time, not servo speed.
"""

import hashlib
import json
from threading import Event
import uuid

from rocell.motion.characterization_plan import AXES, freeze_campaign
from rocell.safety.bench_endpoint import BenchEndpointEvidence, REQUIRED_CHECKS, authorize_bench_endpoint
from .endpoint_trial_contract import REFERENCE_NAMES, create_endpoint_request
from .endpoint_owned_trial import EndpointCleanupResult, run_owned_endpoint_trial
from .wizard_movement_campaign import parse_plan

FAULTS = ('NONE','BASELINE_MISMATCH','SHORT_WRITE','UNCHANGED','CANCEL_AFTER_WRITE','CLEANUP_PENDING',
          'DELAYED_ARRIVAL','MISSING_FEEDBACK','POSITION_BIAS')


def validate_rehearsal(values):
    plan = parse_plan(values['plan_json'])
    trial_id = values['trial_id']
    if plan.to_dict()['frame'] != 'R_ctrl':
        raise ValueError('Endpoint rehearsal requires explicit R_ctrl coordinates')
    trial = next((t for t in plan.to_dict()['trials'] if t['trial_id'] == trial_id), None)
    if trial is None or trial['timeout_s'] > 5:
        raise ValueError('Select one known trial with timeout at most five seconds')
    if values['fault'] not in FAULTS:
        raise ValueError('Unknown endpoint rehearsal fault')
    return plan


def run_endpoint_rehearsal(workspace, values):
    original = validate_rehearsal(values)
    data = original.to_dict()
    synthetic_digest = hashlib.sha256(b'INCAPABLE_ENDPOINT_REHEARSAL_NOT_PHYSICAL_APPROVAL').hexdigest()
    # Explicitly replace evidence labels; never present a user plan's claims as
    # authenticated hardware reviews. Preserve both plan identities in output.
    for name in ('source_sha256','configuration_sha256','firmware_review_sha256','geometry_sha256'):
        data['evidence'][name] = synthetic_digest
    data['evidence']['usb_identity'] = 'A'*32
    plan = freeze_campaign(data)
    req = create_endpoint_request(plan, values['trial_id'], attempt_id='operation-'+uuid.uuid4().hex,
        references=dict.fromkeys(REFERENCE_NAMES, synthetic_digest),
        usb_identity={'vid':0x10c4,'pid':0xea60,'serial_number':'A'*32},
        issued_monotonic_ns=1_000_000_000, deadline_monotonic_ns=21_000_000_000)
    root = workspace/'software/runs/endpoint-rehearsals'
    root.mkdir(parents=True, exist_ok=True)
    tick, post, clock_calls = [1_000_000_000], [False], [0]
    completed = [None]
    event = Event()
    writes = []
    trial = next(t for t in data['trials'] if t['trial_id'] == values['trial_id'])
    def clock():
        if post[0]:
            clock_calls[0] += 1
            if clock_calls[0] == 2:
                tick[0] += 1
        return tick[0]
    def evidence():
        return BenchEndpointEvidence(req.request_sha256, 'incapable-wizard-session',
            tuple(sorted(req.to_dict()['references'].items())),
            tuple((name,synthetic_digest) for name in sorted(REQUIRED_CHECKS)),
            tick[0], req.to_dict()['deadline_monotonic_ns'])
    permit = authorize_bench_endpoint(req, connection_id='incapable-wizard-session',
        evidence_reader=evidence, attempt_root=root, clock=clock)
    def read(size, timeout_ms):
        step = min(50_000_000, timeout_ms*1_000_000)
        if post[0]:
            step = min(step, completed[0]+round(trial['timeout_s']*1e9)-tick[0])
        tick[0] += step
        # Only post-write observations are altered. Baseline admission must still
        # be exercised, and missing bytes must consume simulated time to keep the
        # real deadline/read-gap checks meaningful (no busy-looping fake clock).
        if post[0] and values['fault']=='MISSING_FEEDBACK':
            return b''
        pose = dict(trial['target'] if post[0] and values['fault'] != 'UNCHANGED' else trial['start'])
        if post[0] and values['fault']=='DELAYED_ARRIVAL':
            if tick[0]-completed[0]<350_000_000:
                pose=dict(trial['start'])
        if post[0] and values['fault']=='POSITION_BIAS':
            pose['z_mm']+=trial['stop']['position_tolerance_mm']*2
        if not post[0] and values['fault'] == 'BASELINE_MISMATCH':
            pose['x_mm'] += trial['stop']['position_tolerance_mm']+1
        fields = dict(zip(('x','y','z','tit','r','g'), (pose[a] for a in AXES)))
        payload = json.dumps(dict(T=1051,b=0,s=0,e=0,t=0,**fields), separators=(',',':')).encode()+b'\n'
        if len(payload)>size:
            raise ValueError('Synthetic frame exceeds bounded reader size')
        return payload
    def write(payload):
        writes.append(payload.decode('ascii'))
        tick[0] += 1
        completed[0] = tick[0]
        post[0] = True
        if values['fault'] == 'CANCEL_AFTER_WRITE':
            event.set()
        return len(payload)-1 if values['fault'] == 'SHORT_WRITE' else len(payload)
    def close(timeout_ms):
        return EndpointCleanupResult(True, 1 if values['fault']=='CLEANUP_PENDING' else 0)
    result = run_owned_endpoint_trial(req, permit, connection_id='incapable-wizard-session',
        read_once=read, write_once=write, close_once=close,
        presence_expiry_reader=lambda:req.to_dict()['deadline_monotonic_ns'],
        cancellation=event, basis='SYNTHETIC_WIRE_REHEARSAL', clock_ns=clock)
    return {'schema':'rocell.wizard_endpoint_rehearsal.v1','basis':'SYNTHETIC_REHEARSAL',
            'input_plan_sha256':original.sha256,'synthetic_plan_sha256':plan.sha256,
            'request':req.to_dict(),'trial':result,'simulated_wire_writes':writes,
            'fault':values['fault'],'native_device_opens':0,'physical_motion_commands':0,
            'synthetic_observation_model':dict(arrival_delay_s=.35 if values['fault']=='DELAYED_ARRIVAL' else 0,
                post_write_feedback_missing=values['fault']=='MISSING_FEEDBACK',
                z_bias_mm=trial['stop']['position_tolerance_mm']*2 if values['fault']=='POSITION_BIAS' else 0,
                servo_dynamics_modeled=False,servo_acquisition_freshness_verified=False),
            'physical_authority':False,'physical_ready':False,
            'message':'Synthetic bench reviews and endpoints only. No device access, servo timing prediction or physical qualification.'}

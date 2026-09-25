"""Closed hardware-free correction scenarios for the arrival wizard.

The original trials are generated through the bounded production collector
using a synthetic clock/read function, never imported from the test suite.
"""
import base64
import math
from threading import Event

from rocell.arm.protocol import encode_line
from rocell.motion.absolute_wrist_diagnostic import draft_absolute_wrist
from rocell.safety.absolute_wrist_review_authority import AbsoluteWristIntent
from rocell.safety.observational_review_authority import REFERENCES
from .absolute_wrist_capture import capture_absolute_wrist_window
from .first_motion_contract import canonical
from .wrist_correction_preview import simulate_wrist_correction

SCENARIOS = ('CONSTANT_BIAS','BIAS_DISAPPEARS','OVERSHOOT','WRONG_APPROACH','STALE_BASELINE')


def _original(index):
    joints=dict(b=0.,s=0.,e=0.,t=math.radians(4),r=0.,g=0.)
    body=dict(schema='rocell.absolute_wrist_intent.v1',session_id='wizard-'+'a'*32,
        attempt_id='operation-'+format(index,'032x'),
        usb_identity=dict(vid=0x10c4,pid=0xea60,serial_number='A'*32),
        references={k:'b'*64 for k in REFERENCES},issued_ns=1_000_000_000,deadline_ns=21_000_000_000,
        draft=draft_absolute_wrist(expected_start_joints_rad=joints,target_deg=0,direction=-1).to_dict())
    request=AbsoluteWristIntent(canonical(body))
    clock=[2_000_000_000]
    def capture(phase,completed=None):
        def read(n,timeout):
            clock[0]+=20_000_000
            position=joints['t'] if phase=='baseline' else math.radians(.87)
            line=encode_line(dict(T=1051,x=1,y=2,z=3,tit=0,**dict(joints,t=position)))
            if len(line)>n: raise ValueError('Synthetic frame exceeds bounded read')
            return line
        return capture_absolute_wrist_window(request,phase,read_once=read,cancellation=Event(),
            clock_ns=lambda:clock[0],idle_wait=lambda seconds:clock.__setitem__(0,clock[0]+round(seconds*1e9)),
            command_completed_ns=completed)
    baseline=capture('baseline')
    begin=clock[0];clock[0]+=1_000_000
    payload=encode_line(dict(T=101,joint=4,rad=0.,spd=20,acc=1))
    write=dict(payload_base64=base64.b64encode(payload).decode(),started_ns=begin,finished_ns=clock[0],
        attempted=True,confirmed_bytes=len(payload),completion_uncertain=False)
    post=capture('post',clock[0])
    trial=dict(schema='rocell.absolute_wrist_trial.v1',request_sha256=request.request_sha256,
        basis='SYNTHETIC_WIRE_REHEARSAL',baseline=baseline,post=post,write=write,
        cleanup=dict(started_ns=clock[0],finished_ns=clock[0]+1_000_000,all_handles_closed=True,pending_io_count=0))
    return request,canonical(trial)


def rehearse_wrist_correction(scenario):
    if type(scenario) is not str or scenario not in SCENARIOS:
        raise ValueError('Closed correction rehearsal scenario required')
    originals=[_original(1),_original(2)]
    context=originals[0][0].to_dict()
    joints=context['draft']['expected_start_joints_rad']
    samples=[dict(host_received_ns=1_000_000_000+i*50_000_000,joints_rad=dict(joints)) for i in range(5)]
    now=1_200_000_000
    if scenario=='WRONG_APPROACH':
        for row in samples: row['joints_rad']['t']=math.radians(-4)
    if scenario=='STALE_BASELINE': now+=3_000_000_000
    result=dict(schema='rocell.wrist_correction_rehearsal.v1',scenario=scenario,
        basis='SYNTHETIC_WIRE_REHEARSAL',status='HELD',reason=None,simulation=None,
        expected_outcome_matched=False,device_open_count=0,serial_write_count=0,
        motion_authorized=False,physical_accuracy_verified=False)
    try:
        simulation=simulate_wrist_correction(originals,samples=samples,now_ns=now,
            usb_identity=context['usb_identity'],residual_bias_deg=0 if scenario=='BIAS_DISAPPEARS' else .87,
            transient_overshoot_deg=-.7 if scenario=='OVERSHOOT' else None)
        status=simulation['endpoint']['status']
        result.update(simulation=simulation,status=status,
            expected_outcome_matched=status==('REPORTED_SETTLED' if scenario=='CONSTANT_BIAS' else 'WRIST_EXCURSION'))
    except ValueError as error:
        if scenario not in ('WRONG_APPROACH','STALE_BASELINE'): raise
        result.update(reason=str(error),expected_outcome_matched=True)
    return result

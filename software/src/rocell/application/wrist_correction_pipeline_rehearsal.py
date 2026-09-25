"""Persist the complete correction evidence chain with a public synthetic key.

Never loads protected host keys or opens hardware. Synthetic signatures only
exercise wiring; they cannot qualify physical provenance or native admission.
"""
import base64
import hashlib
import math
from pathlib import Path
from uuid import uuid4

from rocell.arm.protocol import encode_line
from rocell.safety.bench_review_authority import BenchReviewAuthority
from rocell.safety.observational_review_authority import CHECKS
from .first_motion_contract import canonical
from .physical_onboarding_durability import safe_root, publish_reservation_bytes
from .wrist_correction_rehearsal import rehearse_wrist_correction, _original
from .wrist_correction_consumption import WristCorrectionConsumption
from .wrist_correction_result_publication import publish_wrist_correction_result

SYNTHETIC_KEY = b'R'*32


def run_correction_pipeline_rehearsal(workspace, scenario):
    report=rehearse_wrist_correction(scenario)
    if report['simulation'] is None:
        return dict(report,pipeline_status='HELD_BEFORE_CONSUMPTION',originals=[])
    originals=[_original(1),_original(2)]
    context=originals[0][0].to_dict()
    joints=context.pop('draft')['expected_start_joints_rad'];del context['schema']
    context['session_id']='wizard-'+uuid4().hex
    context['attempt_id']='operation-'+uuid4().hex
    directory=Path(workspace)/'software/runs/wrist-correction-rehearsals'/context['attempt_id']
    directory.mkdir(parents=True,exist_ok=False)
    root=safe_root(directory)
    samples=[dict(host_received_ns=1_000_000_000+i*50_000_000,joints_rad=dict(joints)) for i in range(5)]
    authority=BenchReviewAuthority(SYNTHETIC_KEY).for_wrist_correction_review()
    plan=authority.seal_plan(context,dict(operator_id='synthetic-fixture',recorded_ns=1_000_000_000,
        checks=dict.fromkeys(CHECKS,True)),originals=originals,
        now_ns=1_000_000_000,expected_basis='SYNTHETIC_WIRE_REHEARSAL')
    baseline_raw=bytearray();baseline_windows=[]
    for sample in samples:
        line=encode_line(dict(T=1051,x=1,y=2,z=3,tit=0,**sample['joints_rad']))
        stamp=sample['host_received_ns']
        baseline_windows.append([len(baseline_raw),len(baseline_raw)+len(line),stamp,stamp])
        baseline_raw.extend(line)
    bundle,samples,_=authority.bind_review_from_capture(plan,context=context,originals=originals,
        raw=bytes(baseline_raw),windows=baseline_windows,started_ns=1_000_000_000,
        finished_ns=1_200_000_000,now_ns=1_200_000_000,expected_basis='SYNTHETIC_WIRE_REHEARSAL')
    retained=[]
    def retain(name,data):
        publish_reservation_bytes(root,name,data,maximum_bytes=256*1024)
        retained.append(dict(name=name,bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),
                             base64_chunks=[base64.b64encode(data[i:i+4096]).decode() for i in range(0,len(data),4096)]))
    for i,(request,raw) in enumerate(originals,1):
        retain('evidence-'+str(i)+'-request.json',request.canonical_bytes)
        retain('evidence-'+str(i)+'-trial.json',raw)
    retain('context.json',canonical(context));retain('plan-review.json',plan);retain('review.json',bundle)
    scope=WristCorrectionConsumption(authority=authority,bundle=bundle,context=context,
        originals=originals,samples=samples,basis='SYNTHETIC_WIRE_REHEARSAL',root=root,
        clock_ns=lambda:1_200_000_000)
    claim=scope.consume()
    def capture(rows,begin,end):
        raw=bytearray();windows=[]
        for stamp,pose in rows:
            line=encode_line(dict(T=1051,x=1,y=2,z=3,tit=0,**pose))
            windows.append([len(raw),len(raw)+len(line),stamp,stamp]);raw.extend(line)
        return dict(raw_base64=base64.b64encode(raw).decode(),read_windows=windows,
                    started_ns=begin,finished_ns=end)
    final=report['simulation']['simulated_final_rad']
    rows=[]
    for i in range(1,251):
        angle=joints['t']+(final-joints['t'])*min(i/50,1)
        if scenario=='OVERSHOOT' and i==75: angle=math.radians(-.7)
        rows.append((1_201_000_000+i*20_000_000,dict(joints,t=angle)))
    payload=encode_line(claim['candidate_command'])
    trial=dict(schema='rocell.wrist_correction_trial.v1',basis='SYNTHETIC_WIRE_REHEARSAL',
        baseline=capture([(s['host_received_ns'],s['joints_rad']) for s in samples],1_000_000_000,1_200_000_000),
        post=capture(rows,1_201_000_000,6_201_000_000),
        write=dict(payload_base64=base64.b64encode(payload).decode(),started_ns=1_200_000_000,
            finished_ns=1_201_000_000,confirmed_bytes=len(payload),completion_uncertain=False),
        cleanup=dict(finished_ns=6_202_000_000,all_handles_closed=True,pending_io_count=0))
    published=publish_wrist_correction_result(canonical(trial),root=root,authority=authority,
        bundle=bundle,context=context,originals=originals,expected_basis='SYNTHETIC_WIRE_REHEARSAL')
    # Include exact consumed/publication originals in generic wizard exports.
    from .physical_onboarding_durability import read_bounded_regular_file
    for suffix in ('reservation','consumed','trial.original','result'):
        name=context['attempt_id']+'-wrist-correction-'+suffix+'.json'
        data=read_bounded_regular_file(root/name,maximum_bytes=256*1024)
        retained.append(dict(name=name,bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),
                             base64_chunks=[base64.b64encode(data[i:i+4096]).decode() for i in range(0,len(data),4096)]))
    matches=published['report']['endpoint']['status']==report['status']
    return dict(report,pipeline_status='SYNTHETIC_CHAIN_PUBLISHED',
        expected_outcome_matched=report['expected_outcome_matched'] and matches,
        rebuilt_endpoint_status=published['report']['endpoint']['status'],
        publication_sha256=published['publication_sha256'],originals=retained,
        directory=str(root),signature_kind='PUBLIC_SYNTHETIC_KEY_NOT_HARDWARE_AUTHENTICATION')

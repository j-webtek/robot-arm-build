import base64
import math
import pytest
from test_wrist_correction_review_authority import setup
from rocell.application.first_motion_contract import canonical
from rocell.application.wrist_correction_result_review import review_wrist_correction_result
from rocell.arm.protocol import encode_line
from rocell.application.wrist_correction_preview import preview_wrist_correction


def fixture(fault=None):
    auth,ctx,operator,args=setup()
    samples=args['samples']
    def capture(rows,begin,end):
        raw=b'';windows=[]
        for stamp,joints in rows:
            line=encode_line(dict(T=1051,x=1,y=2,z=3,tit=0,**joints))
            windows.append([len(raw),len(raw)+len(line),stamp,stamp]);raw+=line
        return dict(raw_base64=base64.b64encode(raw).decode(),read_windows=windows,started_ns=begin,finished_ns=end)
    baseline=capture([(s['host_received_ns'],s['joints_rad']) for s in samples],1_000_000_000,1_200_000_000)
    preview=preview_wrist_correction(args['originals'],expected_basis=args['expected_basis'],
        samples=samples,now_ns=args['now_ns'],usb_identity=ctx['usb_identity'])
    payload=encode_line(preview['candidate_command'])
    start=samples[-1]['joints_rad']
    final=preview['candidate_command']['rad']+math.radians(.87)
    if fault=='motor_target': final=preview['candidate_command']['rad']
    rows=[]
    for i in range(1,251):
        joints=dict(start,t=start['t']+(final-start['t'])*min(i/50,1))
        if fault=='other_joint' and i==100: joints['b']+=.1
        rows.append((1_201_000_000+i*20_000_000,joints))
    trial=dict(schema='rocell.wrist_correction_trial.v1',basis=args['expected_basis'],baseline=baseline,
        post=capture(rows,1_201_000_000,6_201_000_000),
        write=dict(payload_base64=base64.b64encode(payload).decode(),started_ns=1_200_000_000,
                   finished_ns=1_201_000_000,confirmed_bytes=len(payload),completion_uncertain=False),
        cleanup=dict(finished_ns=6_202_000_000,all_handles_closed=True,pending_io_count=0))
    bundle=auth.seal(ctx,operator,**args)
    kw=dict(authority=auth,bundle=bundle,context=ctx,originals=args['originals'],expected_basis=args['expected_basis'])
    return trial,kw


def test_raw_reports_rebuilt_against_nominal_not_motor_target():
    trial,kw=fixture()
    r=review_wrist_correction_result(canonical(trial),**kw)
    assert r['endpoint']['status']=='REPORTED_SETTLED'
    assert not r['consumption_verified'] and not r['campaign_advance_allowed']


@pytest.mark.parametrize('fault,status',[('motor_target','WRIST_EXCURSION'),('other_joint','OTHER_JOINT_CHANGED')])
def test_nominal_faults_preserved(fault,status):
    trial,kw=fixture(fault)
    assert review_wrist_correction_result(canonical(trial),**kw)['endpoint']['status']==status


@pytest.mark.parametrize('fault',['short','uncertain','cleanup'])
def test_transport_failure_overrides_settled_endpoint(fault):
    trial,kw=fixture()
    if fault=='short': trial['write']['confirmed_bytes']-=1
    if fault=='uncertain': trial['write']['completion_uncertain']=True
    if fault=='cleanup': trial['cleanup']['all_handles_closed']=False
    assert review_wrist_correction_result(canonical(trial),**kw)['endpoint']['status']=='TRANSPORT_FAULT'


@pytest.mark.parametrize('fault',['command','duration','basis','baseline','extra'])
def test_changed_evidence_rejected(fault):
    trial,kw=fixture()
    if fault=='command': trial['write']['payload_base64']=base64.b64encode(b'{}\n').decode()
    if fault=='duration': trial['post']['finished_ns']-=1
    if fault=='basis': trial['basis']='RETAINED_PHYSICAL_CAPTURE'
    if fault=='baseline': trial['baseline']['raw_base64']=''
    if fault=='extra': trial['endpoint_verified']=True
    with pytest.raises(ValueError): review_wrist_correction_result(canonical(trial),**kw)


def test_interior_corrupt_frame_cannot_be_filtered_into_success():
    trial,kw=fixture()
    raw=bytearray(base64.b64decode(trial['post']['raw_base64']))
    raw[trial['post']['read_windows'][100][0]]=ord('!')
    trial['post']['raw_base64']=base64.b64encode(raw).decode()
    result=review_wrist_correction_result(canonical(trial),**kw)
    assert result['endpoint']['status']=='FEEDBACK_INVALID'
    assert 'INVALID_JOINT_RECORD' in result['capture_issues']


def test_reported_gap_prevents_endpoint_success():
    trial,kw=fixture()
    # Preserve byte coverage but reveal an acquisition gap; never interpolate.
    for row in trial['post']['read_windows'][:10]:
        row[2]=row[3]=1_421_000_000
    result=review_wrist_correction_result(canonical(trial),**kw)
    assert result['endpoint']['status']=='FEEDBACK_INVALID'

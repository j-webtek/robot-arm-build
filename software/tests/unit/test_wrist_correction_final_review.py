import json
import os
import pytest
from test_wrist_correction_serial_connection import owner,select
from rocell.application.first_motion_contract import canonical
from rocell.application.wrist_correction_owned_final_capture import retain_owned_final_capture
from rocell.arm.protocol import encode_line
from rocell.safety.wrist_correction_review_authority import WristCorrectionReviewAuthority


def fixture(tmp_path,monkeypatch):
    connection,kernel,permit,request,reader,clock=owner(tmp_path,monkeypatch)
    connection.open();select(connection,permit,request,reader,clock)
    joints=reader._originals[0][0].to_dict()['draft']['expected_start_joints_rad']
    kernel.input=encode_line(dict(T=1051,x=0,y=0,z=0,tit=0,**joints))
    read=kernel.ReadFile
    def timed(*args):
        clock[0]+=20_000_000
        return read(*args)
    monkeypatch.setattr(kernel,'ReadFile',timed)
    try:
        result=retain_owned_final_capture(connection,permit,
            idle_wait=lambda s:clock.__setitem__(0,clock[0]+round(s*1e9)))
        scope=permit._binding._scope
        claim=tmp_path/(request.to_dict()['attempt_id']+'-wrist-correction-final-capture-claim.json')
        args=dict(original_bundle=scope._bundle,context=request.to_dict(),originals=reader._originals,
            samples=scope._samples,basis=reader._basis,claim_raw=claim.read_bytes(),
            capture_raw=(tmp_path/result['retention']['file']).read_bytes(),owned_process_id=os.getpid(),now_ns=clock[0])
        return reader._authority,args,kernel
    finally: connection.close(2000)


def test_authenticates_new_capture_without_extending_deadline_or_authority(tmp_path,monkeypatch):
    authority,args,kernel=fixture(tmp_path,monkeypatch)
    sealed=authority.seal_final_readback(**args)
    report=authority.verify_final_readback(sealed,**args)
    assert report['deadline_ns']==args['context']['deadline_ns']
    assert not report['motion_authorized'] and not report['one_use_dispatch_implemented']
    assert not kernel.writes
    with pytest.raises(ValueError):
        authority.verify_final_readback(sealed,**dict(args,now_ns=args['now_ns']+101_000_000))


@pytest.mark.parametrize('fault',['mac','key','pid','claim','capture','bundle','deadline','record_hashes'])
def test_changed_authenticated_readback_rejected(tmp_path,monkeypatch,fault):
    authority,args,_=fixture(tmp_path,monkeypatch)
    sealed=authority.seal_final_readback(**args)
    if fault=='mac':
        body=json.loads(sealed);body['intent']['candidate_command']['rad']=0;sealed=canonical(body)
    elif fault=='key': authority=WristCorrectionReviewAuthority(b'Z'*32)
    elif fault=='pid': args['owned_process_id']+=1
    elif fault=='claim':
        body=json.loads(args['claim_raw']);body['connection_id']='operation-'+'a'*32;args['claim_raw']=canonical(body)
    elif fault=='capture':
        body=json.loads(args['capture_raw']);body['validation']['candidate_command']['rad']=0;args['capture_raw']=canonical(body)
    elif fault=='bundle': args['original_bundle']=b'{}'
    elif fault=='deadline': args['context']['deadline_ns']+=1
    else:
        body=json.loads(args['claim_raw']);body['record_hashes']={};args['claim_raw']=canonical(body)
    with pytest.raises(ValueError): authority.verify_final_readback(sealed,**args)


@pytest.mark.parametrize('fault',['age','before_finish','summary','selection'])
def test_single_reconstruction_preserves_saved_validation_checks(tmp_path,monkeypatch,fault):
    authority,args,_=fixture(tmp_path,monkeypatch)
    body=json.loads(args['capture_raw'])
    if fault=='age': body['validation']['host_age_ns']+=1
    elif fault=='before_finish':
        stamp=body['capture']['finished_ns']-1
        body['validation']['checked_at_ns']=stamp
        body['validation']['host_age_ns']=stamp-body['validation']['final_last_received_ns']
    elif fault=='summary': body['validation']['sample_count']+=1
    else:
        from rocell.providers.windows.wrist_correction_native_protocol import digest
        claim=json.loads(args['claim_raw']);claim['selection_sha256']='f'*64
        args['claim_raw']=canonical(claim)
        body['claim_sha256']=digest(args['claim_raw'])
    args['capture_raw']=canonical(body)
    with pytest.raises(ValueError): authority.seal_final_readback(**args)


def test_one_raw_reconstruction_per_review_with_later_current_time(tmp_path,monkeypatch):
    from rocell.application import wrist_correction_final_review as module
    authority,args,_=fixture(tmp_path,monkeypatch)
    validate=module.validate_final_capture;calls=[]
    def counted(*a,**kw):
        calls.append(kw['now_ns']);return validate(*a,**kw)
    monkeypatch.setattr(module,'validate_final_capture',counted)
    args['now_ns']+=10_000_000
    sealed=authority.seal_final_readback(**args)
    assert calls==[args['now_ns']]
    authority.verify_final_readback(sealed,**args)
    assert calls==[args['now_ns']]*2

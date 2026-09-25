import base64
import json
import math
import pytest
from test_wrist_correction_final_dispatch import prepared
from rocell.application.first_motion_contract import canonical
from rocell.application.wrist_correction_capture import capture_wrist_correction_window,correction_capture_original
from rocell.application.wrist_correction_result_review import review_wrist_correction_result
from rocell.arm.protocol import encode_line
from rocell.providers.windows.wrist_correction_native_protocol import digest


def fixture(tmp_path,monkeypatch,miss=False):
    c,k,p,r,reader,clock=prepared(tmp_path,monkeypatch)
    prefix=r.to_dict()['attempt_id']+'-wrist-correction-'
    selection=json.loads((tmp_path/(prefix+'owned-selection.json')).read_bytes())
    baseline=dict(raw_base64=selection['raw_base64'],read_windows=selection['read_windows'],
        started_ns=selection['started_ns'],finished_ns=selection['finished_ns'])
    try:
        p.prepare_final_dispatch(c);payload=p.selected_payload();start=clock[0]
        count=c.write_once(payload);end=clock[0]
        joints=reader._originals[0][0].to_dict()['draft']['expected_start_joints_rad']
        k.input=encode_line(dict(T=1051,x=0,y=0,z=0,tit=0,**dict(joints,t=math.radians(1 if miss else 0))))
        capture=capture_wrist_correction_window(r,'post',read_once=c.read,cancellation=p._binding._cancel,
            clock_ns=lambda:clock[0],idle_wait=lambda s:clock.__setitem__(0,clock[0]+round(s*1e9)),command_completed_ns=end)
        post=correction_capture_original(r,capture,phase='post',command_completed_ns=end)
        final=p._binding._final_scope
        evidence=dict(review_raw=final._review,claim_raw=final._args['claim_raw'],capture_raw=final._args['capture_raw'],
            owned_process_id=final._pid)
        references=dict(review_sha256=digest(evidence['review_raw']),claim_sha256=digest(evidence['claim_raw']),
            capture_sha256=digest(evidence['capture_raw']),owner_pid=final._pid)
        checked=p._binding._final_dispatch_checked_ns
    finally: cleanup=c.close(2000)
    trial=dict(schema='rocell.wrist_correction_trial.v2',basis=reader._basis,baseline=baseline,post=post,
        write=dict(payload_base64=base64.b64encode(payload).decode(),started_ns=start,finished_ns=end,
            confirmed_bytes=count,completion_uncertain=False,dispatch_checked_ns=checked),
        cleanup=dict(finished_ns=clock[0],all_handles_closed=cleanup.all_handles_closed,pending_io_count=cleanup.pending_io_count),
        final_readback=references)
    args=dict(authority=reader._authority,bundle=p._binding._scope._bundle,context=r.to_dict(),
        originals=reader._originals,expected_basis=reader._basis,final_evidence=evidence)
    return trial,args,k


@pytest.mark.parametrize('miss,status',[(False,'REPORTED_SETTLED'),(True,'TARGET_MISSED')])
def test_reconstructs_v2_from_original_baseline_and_new_readback(tmp_path,monkeypatch,miss,status):
    trial,args,k=fixture(tmp_path,monkeypatch,miss)
    assert trial['write']['started_ns']-trial['baseline']['finished_ns']>100_000_000
    report=review_wrist_correction_result(canonical(trial),**args)
    assert report['schema']=='rocell.wrist_correction_result_review.v2'
    assert report['endpoint']['status']==status and len(k.writes)==1
    assert not report['motion_authorized'] and not report['consumption_verified']


@pytest.mark.parametrize('fault',['missing','reference','time','capture','review','legacy'])
def test_invalid_v2_evidence_is_rejected(tmp_path,monkeypatch,fault):
    trial,args,_=fixture(tmp_path,monkeypatch)
    if fault=='missing': args['final_evidence']=None
    elif fault=='reference': trial['final_readback']['capture_sha256']='0'*64
    elif fault=='time': trial['write']['dispatch_checked_ns']=trial['write']['finished_ns']+1
    elif fault=='capture': args['final_evidence']['capture_raw']=b'{}'
    elif fault=='review': args['final_evidence']['review_raw']=b'{}'
    else: trial['schema']='rocell.wrist_correction_trial.v1'
    with pytest.raises(ValueError): review_wrist_correction_result(canonical(trial),**args)


def test_v2_publication_reconciles_all_original_records(tmp_path,monkeypatch):
    from rocell.application.wrist_correction_result_publication import publish_wrist_correction_result,reconcile_wrist_correction_result
    trial,args,_=fixture(tmp_path,monkeypatch)
    args.pop('final_evidence')
    before={p.name:p.read_bytes() for p in tmp_path.iterdir() if p.is_file()}
    report=reconcile_wrist_correction_result(canonical(trial),root=tmp_path,**args)
    assert report['schema']=='rocell.wrist_correction_publication.v2' and report['records_consistent']
    assert len(report['record_hashes'])==8
    assert before=={p.name:p.read_bytes() for p in tmp_path.iterdir() if p.is_file()}
    result=publish_wrist_correction_result(canonical(trial),root=tmp_path,**args)
    assert result['report']['endpoint']['status']=='REPORTED_SETTLED'


@pytest.mark.parametrize('suffix',['final-consumed','final-reservation','final-capture-claim','final-capture.original','owned-selection','reservation','consumed'])
def test_v2_publication_rejects_changed_or_conflicting_records(tmp_path,monkeypatch,suffix):
    from rocell.application.wrist_correction_result_publication import reconcile_wrist_correction_result
    trial,args,_=fixture(tmp_path,monkeypatch);args.pop('final_evidence')
    path=tmp_path/(args['context']['attempt_id']+'-wrist-correction-'+suffix+'.json')
    path.write_bytes(b'{}')
    with pytest.raises((ValueError,KeyError)):
        reconcile_wrist_correction_result(canonical(trial),root=tmp_path,**args)

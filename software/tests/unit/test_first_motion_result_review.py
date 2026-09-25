"""Recompute real synthetic runner outputs; reject altered summaries/receipts."""
import pytest

from rocell.application.first_motion_contract import canonical
from rocell.application.first_motion_result_review import review_completed_first_motion_trial
from test_first_motion_owned_trial import run
from test_first_motion_measurement_binding import setup


def fixture(tmp_path,fault=None):
    request_root=tmp_path/'request'; request_root.mkdir()
    run_root=tmp_path/'run'; run_root.mkdir()
    _,request=setup(request_root)
    trial,_=run(run_root,fault)
    assert trial['request_sha256']==request.request_sha256
    return request,trial


@pytest.mark.parametrize('fault',[None,'unchanged'])
def test_consistency_review_recomputes_without_physical_qualification(tmp_path,fault):
    request,trial=fixture(tmp_path,fault)
    report=review_completed_first_motion_trial(request,canonical(trial),expected_basis='SYNTHETIC_WIRE_REHEARSAL')
    assert report['analysis']==trial['analysis']
    assert report['status']=='TRIAL_DATA_CONSISTENT_NOT_PHYSICALLY_QUALIFIED'
    assert not report['physical_movement_verified'] and not report['owned_process_receipt_verified']


@pytest.mark.parametrize('fault',['short_write','write_error','cleanup_error','cancel_after','invalid_baseline'])
def test_failed_trials_cannot_enter_complete_review(tmp_path,fault):
    request,trial=fixture(tmp_path,fault)
    with pytest.raises(ValueError):
        review_completed_first_motion_trial(request,canonical(trial),expected_basis='SYNTHETIC_WIRE_REHEARSAL')


@pytest.mark.parametrize('fault',['analysis','status','physical','count','cleanup-time','cleanup-bool','basis'])
def test_tampered_claims_refused(tmp_path,fault):
    request,trial=fixture(tmp_path)
    if fault=='analysis': trial['analysis']['post_count']+=1
    if fault=='status': trial['status']='PASSED'
    if fault=='physical': trial['physical_movement_verified']=True
    if fault=='count': trial['write']['confirmed_write_bytes']-=1
    if fault=='cleanup-time': trial['cleanup']['finished_ns']+=3_000_000_000
    if fault=='cleanup-bool': trial['cleanup']['pending_io_count']=False
    if fault=='basis': trial['basis']='RETAINED_PHYSICAL_CAPTURE'
    with pytest.raises(ValueError):
        review_completed_first_motion_trial(request,canonical(trial),expected_basis='SYNTHETIC_WIRE_REHEARSAL')

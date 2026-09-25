"""Offline evidence replay must fail on disagreement, without hardware access."""
import importlib.util
import json
import math
import base64
import hashlib
from pathlib import Path

import pytest
from test_wifi_discrete_runner import setup

spec=importlib.util.spec_from_file_location('review_roll',
    Path(__file__).resolve().parents[2]/'scripts'/'review_wifi_roll_export.py')
review=importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)


def test_reconstructs_originals(tmp_path):
    _,run,*_=setup(tmp_path)
    result=json.loads(json.dumps(run()))
    assert review.replay_endpoint(result['transaction'],result['feedback_originals'])==result['transaction']['rows']


@pytest.mark.parametrize('change',['row','verdict','desired','body'])
def test_mismatch_rejected(tmp_path,change):
    _,run,*_=setup(tmp_path)
    result=json.loads(json.dumps(run()));tx=result['transaction'];samples=result['feedback_originals']
    if change=='row':tx['rows'][0][2][4]+=.01
    elif change=='verdict':tx['result']['endpoint']['final_error_rad']=.01
    elif change=='desired':tx['desired_endpoint_rad']=.02
    else:samples[0]['response_base64']='e30='
    with pytest.raises(ValueError):review.replay_endpoint(tx,samples)


def test_invalid_export_rejected_before_reading(tmp_path,monkeypatch):
    monkeypatch.setattr(review,'verify_export',lambda path:dict(valid=False))
    with pytest.raises(ValueError,match='integrity'):review.review(tmp_path)


def test_receipt_failure_summary_is_bounded():
    r=review.receipt_summary(dict(command_receipt=dict(status='UNCERTAIN',
        failure_category='CONNECTION_RESET',cleanup_confirmed=True,
        response_base64='secret',exception='secret')))
    assert r==dict(status='UNCERTAIN',failure_category='CONNECTION_RESET',cleanup_confirmed=True)
    assert 'secret' not in json.dumps(r)
    assert review.receipt_summary({})['failure_category'] is None
    r=review.receipt_summary(dict(command_receipt=dict(status='secret',failure_category='secret')))
    assert 'secret' not in json.dumps(r)


def timeline_case():
    tx,samples=hold_case([1.5]*3)
    tx.update(baseline_finished_ns=900_000_000,acknowledgment_finished_ns=1_100_000_000,
        result=dict(evaluated_ns=2_000_000_000))
    raw=b'{}'
    receipt=dict(payload_sha256=hashlib.sha256(review.canonical(tx['command'])).hexdigest(),
        response_base64=base64.b64encode(raw).decode(),response_sha256=hashlib.sha256(raw).hexdigest(),
        receipt_kind='JSON_HTTP_200')
    return tx,samples,receipt


def test_timeline_uses_actual_host_bounds():
    tx,samples,receipt=timeline_case()
    r=review.trial_timeline(tx,samples,receipt)
    assert r['baseline_age_at_dispatch_ms']==100
    assert r['dispatch_to_http_receipt_ms']==100
    assert r['dispatch_to_verification_s']==1
    assert r['verification_to_hold_request_s']==pytest.approx(.1)
    assert r['endpoint_feedback'][0]['response_after_dispatch_s']==1
    assert not r['physical_movement_duration_known'] and not r['receipt_used_as_endpoint']


@pytest.mark.parametrize('change',['payload','response','base64','baseline','ack','hold'])
def test_timeline_rejects_inconsistent_evidence(change):
    tx,samples,receipt=timeline_case()
    if change=='payload':receipt['payload_sha256']='bad'
    elif change=='response':receipt['response_sha256']='bad'
    elif change=='base64':receipt['response_base64']='!'
    elif change=='baseline':tx['baseline_finished_ns']=1_200_000_000
    elif change=='ack':tx['acknowledgment_finished_ns']=2_000_000_000
    else:samples[0]['request_started_monotonic_s']=1.9
    with pytest.raises(ValueError):review.trial_timeline(tx,samples,receipt)


def hold_case(values, joint='r'):
    pose=dict(b=0,s=0,e=1,t=0,r=math.radians(1.5),g=3)
    tx=dict(rows=[[1_900_000_000,2_000_000_000,list(pose.values())]],
        desired_endpoint_rad=math.radians(1.5),command=dict(rad=math.radians(1.25)),
        dispatch_started_ns=1_000_000_000)
    samples=[]
    for i,v in enumerate(values):
        p=pose.copy();p[joint]=math.radians(v)
        samples.append(dict(joints_rad=p,request_started_monotonic_s=2.1+i*.3,
            response_finished_monotonic_s=2.2+i*.3))
    return tx,samples


def test_unchanged_hold():
    tx,samples=hold_case([1.5]*3)
    r=review.assess_hold(tx,samples)
    assert r['unchanged'] and r['hold_final_error_deg']==0


@pytest.mark.parametrize('values',[[1.5,1.4,1.4],[1.5,1.4,1.5],[1.4,1.4,1.4]])
def test_late_change_within_band_never_unchanged(values):
    tx,samples=hold_case(values)
    r=review.assess_hold(tx,samples)
    assert not r['unchanged'] and r['status']=='LATE_REPORTED_ENDPOINT_CHANGE'
    assert r['all_roll_samples_within_arrival_band']
    assert r['changed_joints']==['r']


def test_other_joint_change_and_out_of_band_and_bad_order():
    tx,samples=hold_case([0,.1,0],joint='b')
    assert not review.assess_hold(tx,samples)['unchanged']
    tx,samples=hold_case([1.5,2.1])
    assert not review.assess_hold(tx,samples)['all_roll_samples_within_arrival_band']
    samples[0]['request_started_monotonic_s']=1.9
    with pytest.raises(ValueError):review.assess_hold(tx,samples)
    with pytest.raises(ValueError):review.assess_hold(tx,[])


def test_cli_prints_failure_and_returns_nonzero(monkeypatch,capsys):
    monkeypatch.setattr('sys.argv',['review','unused'])
    monkeypatch.setattr(review,'review',lambda p:dict(full_validation_success=False))
    with pytest.raises(SystemExit) as exc:review.main()
    assert exc.value.code==1
    assert '"full_validation_success": false' in capsys.readouterr().out


def test_partial_hold_preserves_prefix_without_qualifying():
    tx,samples=hold_case([1.5]*3)
    for s in samples:s['status']='SUCCEEDED'
    samples.append(dict(status='FAILED',error_category='TIMEOUT',failure_phase='REQUEST_SEND'))
    r=review.incomplete_hold_details(tx,dict(samples=samples))
    assert r['failure_code']=='HOLD_INCOMPLETE' and not r['hold_completed']
    assert r['successful_prefix_samples']==3
    assert r['partial_hold_assessment']['unchanged']
    assert not r['full_validation_success']
    assert r['hold_failure_details'][0]['phase']=='REQUEST_SEND'
    assert 'band_sensitivity_examples' not in r


def test_empty_prefix_unknown_text_and_post_fault_success():
    tx,samples=hold_case([1.5]);samples[0]['status']='SUCCEEDED'
    failed=dict(status='FAILED',error_category='secret',failure_phase='secret')
    r=review.incomplete_hold_details(tx,dict(samples=[failed]))
    assert r['partial_hold_assessment'] is None and 'secret' not in json.dumps(r)
    with pytest.raises(ValueError):review.incomplete_hold_details(tx,dict(samples=[failed]+samples))


def test_export_review_preserves_endpoint_and_cli_failure_on_partial_hold(tmp_path,monkeypatch):
    _,run,*_=setup(tmp_path)
    outcome=json.loads(json.dumps(run()))
    tx=outcome['transaction'];sample=dict(outcome['feedback_originals'][-1])
    sample['request_started_monotonic_s']=tx['rows'][-1][1]/1e9+.1
    sample['response_finished_monotonic_s']=sample['request_started_monotonic_s']+.1
    hold=dict(status='FAILED',samples=[sample,dict(status='FAILED',error_category='TIMEOUT',failure_phase='REQUEST_SEND')],reconstruction=dict(valid=True))
    (tmp_path/'manifest.json').write_text(json.dumps(dict(files=[dict(name='attachment-result-test.json')])))
    (tmp_path/'attachment-result-test.json').write_text(json.dumps(dict(steps=[dict(report=dict(outcome=outcome)),dict(report=hold)])))
    monkeypatch.setattr(review,'verify_export',lambda p:dict(valid=True))
    # Isolate routing; original-body tamper rejection is covered separately.
    monkeypatch.setattr(review,'review_observation',lambda r:dict(valid=True))
    r=review.review(tmp_path)
    assert r['endpoint_replayed'] and r['failure_code']=='HOLD_INCOMPLETE'
    assert not r['full_validation_success'] and not r['hold_completed']
    monkeypatch.setattr('sys.argv',['review',str(tmp_path)])
    with pytest.raises(SystemExit) as exc:review.main()
    assert exc.value.code==1

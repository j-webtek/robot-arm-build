import base64
import json
import pytest
from test_wrist_correction_result_review import fixture
from test_wrist_correction_review_authority import setup
from rocell.application.first_motion_contract import canonical


def inputs():
    auth,ctx,review,args=setup()
    # Approve before acquisition; do not refresh approval at bind time.
    review['recorded_ns']=ctx['issued_ns']
    plan=auth.seal_plan(ctx,review,originals=args['originals'],now_ns=ctx['issued_ns'],expected_basis=args['expected_basis'])
    trial,_=fixture()
    capture=trial['baseline']
    params=dict(context=ctx,originals=args['originals'],raw=base64.b64decode(capture['raw_base64']),
        windows=capture['read_windows'],started_ns=capture['started_ns'],finished_ns=capture['finished_ns'],
        now_ns=args['now_ns'],expected_basis=args['expected_basis'])
    return auth,plan,params


def test_plan_becomes_exact_baseline_review_without_extending_deadline():
    auth,plan,params=inputs()
    raw,samples,framing=auth.bind_review_from_capture(plan,**params)
    result=auth.verify(raw,expected_context=params['context'],originals=params['originals'],samples=samples,
                       now_ns=params['now_ns'],expected_basis=params['expected_basis'])
    assert result['deadline_ns']==params['context']['deadline_ns']
    assert not result['motion_authorized']
    assert json.loads(raw)['review']['recorded_ns']==params['context']['issued_ns']
    assert framing['original_bytes']==len(params['raw'])


@pytest.mark.parametrize('fault',['stale','corrupt','before_review','changed_target','wrong_pose','basis'])
def test_binding_never_silently_changes_review_or_accepts_bad_capture(fault):
    auth,plan,p=inputs()
    if fault=='stale': p['now_ns']+=101_000_000
    if fault=='corrupt': p['raw']=b'!'+p['raw'][1:]
    if fault=='before_review': p['started_ns']-=1
    if fault=='changed_target':
        body=json.loads(plan);body['plan']['proposal']['nominal_target_deg']=4;plan=canonical(body)
    if fault=='wrong_pose':
        p['raw']=p['raw'].replace(b'0.06981317007977318',b'0.00981317007977318')
    if fault=='basis': p['expected_basis']='RETAINED_PHYSICAL_CAPTURE'
    with pytest.raises(ValueError): auth.bind_review_from_capture(plan,**p)


def test_plan_signature_cannot_be_used_as_exact_baseline_review():
    auth,plan,p=inputs()
    with pytest.raises(ValueError):
        auth.verify(plan,expected_context=p['context'],originals=p['originals'],samples=[],
                    now_ns=p['now_ns'],expected_basis=p['expected_basis'])

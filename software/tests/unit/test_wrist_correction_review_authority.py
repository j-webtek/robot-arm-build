import copy
import json
import pytest
from test_wrist_correction_preview import inputs
from rocell.safety.bench_review_authority import BenchReviewAuthority
from rocell.safety.observational_review_authority import CHECKS
from rocell.application.first_motion_contract import canonical


def setup():
    originals, args = inputs()
    context = originals[0][0].to_dict()
    del context['draft'], context['schema']
    context['attempt_id'] = 'operation-'+'f'*32
    review = dict(operator_id='fixture',recorded_ns=args['now_ns'],checks=dict.fromkeys(CHECKS,True))
    auth = BenchReviewAuthority(b'A'*32).for_wrist_correction_review()
    params = dict(originals=originals,samples=args['samples'],now_ns=args['now_ns'],
                  expected_basis='SYNTHETIC_WIRE_REHEARSAL')
    return auth,context,review,params


def test_signature_binds_nominal_and_motor_targets_without_native_authority():
    auth,ctx,review,params=setup()
    raw=auth.seal(ctx,review,**params)
    result=auth.verify(raw,expected_context=ctx,**params)
    assert result['nominal_endpoint_rad']==0
    assert result['candidate_command']['rad']<0
    assert not result['motion_authorized'] and not result['one_use_consumption_implemented']


@pytest.mark.parametrize('field',['nominal_endpoint_rad','candidate_command','proposal_sha256','baseline_sha256'])
def test_edited_signed_preview_fails_authentication(field):
    auth,ctx,review,params=setup()
    body=json.loads(auth.seal(ctx,review,**params))
    body['intent']['preview'][field]=0
    with pytest.raises(ValueError,match='authentication'):
        auth.verify(canonical(body),expected_context=ctx,**params)


@pytest.mark.parametrize('fault',['unit','source','attempt','baseline','stale','expired','basis','key'])
def test_changed_current_context_never_reuses_review(fault):
    auth,ctx,review,params=setup()
    raw=auth.seal(ctx,review,**params)
    ctx=copy.deepcopy(ctx)
    if fault=='unit': ctx['usb_identity']['serial_number']='B'*32
    if fault=='source': ctx['references']['source_sha256']='c'*64
    if fault=='attempt': ctx['attempt_id']='operation-'+'e'*32
    if fault=='baseline': params['samples'][0]['host_received_ns']+=1
    if fault=='stale': params['now_ns']+=3_000_000_000
    if fault=='expired': params['now_ns']=ctx['deadline_ns']
    if fault=='basis': params['expected_basis']='RETAINED_PHYSICAL_CAPTURE'
    if fault=='key': auth=BenchReviewAuthority(b'B'*32).for_wrist_correction_review()
    with pytest.raises(ValueError): auth.verify(raw,expected_context=ctx,**params)


def test_missing_operator_check_cannot_be_signed():
    auth,ctx,review,params=setup()
    review['checks']['bounded_policy_accepted']=False
    with pytest.raises(ValueError): auth.seal(ctx,review,**params)


def test_correction_bundle_not_accepted_by_absolute_authority():
    auth,ctx,review,params=setup()
    raw=auth.seal(ctx,review,**params)
    old=BenchReviewAuthority(b'A'*32).for_absolute_wrist_diagnostic()
    with pytest.raises(ValueError):
        old.verify(raw,expected_intent=ctx,current_usb_identity=ctx['usb_identity'],
                   current_references=ctx['references'],now_ns=params['now_ns'])

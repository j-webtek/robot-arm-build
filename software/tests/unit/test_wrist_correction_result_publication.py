import json
import pytest
from test_wrist_correction_result_review import fixture
from test_wrist_correction_review_authority import setup
from rocell.application.first_motion_contract import canonical
from rocell.application.wrist_correction_consumption import WristCorrectionConsumption
from rocell.application.wrist_correction_result_publication import publish_wrist_correction_result
from rocell.application.physical_onboarding_durability import PhysicalOnboardingDurabilityError


def stage(tmp_path,fault=None):
    trial,kw=fixture(fault)
    _,_,_,args=setup()
    scope=WristCorrectionConsumption(authority=kw['authority'],bundle=kw['bundle'],context=kw['context'],
        originals=kw['originals'],samples=args['samples'],basis=kw['expected_basis'],
        root=tmp_path,clock_ns=lambda:args['now_ns'])
    scope.consume()
    return trial,dict(kw,root=tmp_path)


@pytest.mark.parametrize('fault,endpoint',[(None,'REPORTED_SETTLED'),('motor_target','WRIST_EXCURSION')])
def test_whole_consumption_to_publication_preserves_verdict(tmp_path,fault,endpoint):
    trial,kw=stage(tmp_path,fault)
    r=publish_wrist_correction_result(canonical(trial),**kw)
    assert r['records_consistent'] and r['report']['endpoint']['status']==endpoint
    assert not r['physical_execution_verified'] and not r['campaign_advance_allowed']
    assert len(list(tmp_path.glob('*trial.original.json')))==1
    with pytest.raises(PhysicalOnboardingDurabilityError):
        publish_wrist_correction_result(canonical(trial),**kw)


@pytest.mark.parametrize('fault',['claim_command','claim_time','reservation','missing'])
def test_substituted_claim_never_publishes_success(tmp_path,fault):
    trial,kw=stage(tmp_path)
    suffix='reservation' if fault=='reservation' else 'consumed'
    path=next(tmp_path.glob('*'+suffix+'.json'))
    body=json.loads(path.read_bytes())
    if fault=='claim_command': body['candidate_command']['rad']=0
    if fault=='claim_time': body['claimed_ns']=trial['write']['finished_ns']+1
    if fault=='reservation': body['intent_sha256']='a'*64
    if fault=='missing': path.unlink()
    else: path.write_bytes(canonical(body))
    with pytest.raises((ValueError,PhysicalOnboardingDurabilityError)):
        publish_wrist_correction_result(canonical(trial),**kw)
    assert not list(tmp_path.glob('*result.json'))


def test_publication_failure_retains_original_without_replay(tmp_path,monkeypatch):
    import rocell.application.wrist_correction_result_publication as module
    trial,kw=stage(tmp_path)
    real=module.publish_reservation_bytes
    def fail_result(root,name,raw,**options):
        if name.endswith('-result.json'): raise OSError('synthetic disk failure')
        return real(root,name,raw,**options)
    monkeypatch.setattr(module,'publish_reservation_bytes',fail_result)
    with pytest.raises(OSError): publish_wrist_correction_result(canonical(trial),**kw)
    assert len(list(tmp_path.glob('*trial.original.json')))==1
    assert not list(tmp_path.glob('*result.json'))
    with pytest.raises(PhysicalOnboardingDurabilityError):
        publish_wrist_correction_result(canonical(trial),**kw)

import pytest
from test_wrist_correction_review_authority import setup
from rocell.application.wrist_correction_consumption import WristCorrectionConsumption
from rocell.application.physical_onboarding_durability import PhysicalOnboardingDurabilityError


def arguments(tmp_path):
    auth,context,review,params=setup()
    clock=[params['now_ns']]
    bundle=auth.seal(context,review,**params)
    return dict(authority=auth,bundle=bundle,context=context,originals=params['originals'],
                samples=params['samples'],basis=params['expected_basis'],root=tmp_path,
                clock_ns=lambda:clock[0]),clock


def test_once_and_restart_refused(tmp_path):
    args,_=arguments(tmp_path)
    scope=WristCorrectionConsumption(**args)
    claim=scope.consume()
    assert claim['nominal_endpoint_rad']==0 and claim['candidate_command']['rad']<0
    assert not claim['motion_authorized'] and not claim['native_dispatch_implemented']
    with pytest.raises(ValueError): scope.consume()
    with pytest.raises(PhysicalOnboardingDurabilityError): WristCorrectionConsumption(**args)


def test_interrupted_reservation_cannot_be_reconstructed(tmp_path):
    args,_=arguments(tmp_path)
    WristCorrectionConsumption(**args)
    with pytest.raises(PhysicalOnboardingDurabilityError): WristCorrectionConsumption(**args)


@pytest.mark.parametrize('fault',['stale','backward','revoke','tamper'])
def test_failure_is_sticky(tmp_path,fault):
    args,clock=arguments(tmp_path)
    scope=WristCorrectionConsumption(**args)
    original=clock[0]
    if fault=='stale': clock[0]+=3_000_000_000
    if fault=='backward': clock[0]-=1
    if fault=='revoke': scope.revoke()
    if fault=='tamper':
        path=next(tmp_path.glob('*reservation.json'))
        path.write_bytes(b'{}')
    with pytest.raises(ValueError): scope.consume()
    clock[0]=original
    with pytest.raises(ValueError): scope.consume()


def test_storage_failure_returns_no_claim_and_no_retry(tmp_path,monkeypatch):
    import rocell.application.wrist_correction_consumption as module
    args,_=arguments(tmp_path)
    scope=WristCorrectionConsumption(**args)
    def fail(*a,**kw): raise OSError('synthetic storage failure')
    monkeypatch.setattr(module,'publish_reservation_bytes',fail)
    with pytest.raises(OSError): scope.consume()
    with pytest.raises(ValueError): scope.consume()


def test_post_write_expiry_burns_claim(tmp_path,monkeypatch):
    import rocell.application.wrist_correction_consumption as module
    args,clock=arguments(tmp_path)
    scope=WristCorrectionConsumption(**args)
    real=module.publish_reservation_bytes
    def slow(*a,**kw):
        result=real(*a,**kw)
        clock[0]+=3_000_000_000
        return result
    monkeypatch.setattr(module,'publish_reservation_bytes',slow)
    with pytest.raises(ValueError): scope.consume()
    assert len(list(tmp_path.glob('*consumed.json')))==1
    with pytest.raises(ValueError): scope.consume()


def test_concurrent_consumers_only_one_succeeds(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    args,_=arguments(tmp_path)
    scope=WristCorrectionConsumption(**args)
    gate=Barrier(2)
    def take():
        gate.wait()
        try:
            scope.consume()
            return 'consumed'
        except ValueError:
            return 'held'
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes=list(pool.map(lambda _:take(),range(2)))
    assert sorted(outcomes)==['consumed','held']
    assert len(list(tmp_path.glob('*consumed.json')))==1
    with pytest.raises(ValueError): scope.consume()

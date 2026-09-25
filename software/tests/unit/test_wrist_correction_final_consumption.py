from threading import Event
import pytest
from test_wrist_correction_final_review import fixture
from rocell.application import wrist_correction_final_consumption as module


def prepared(tmp_path,monkeypatch):
    authority,args,kernel=fixture(tmp_path,monkeypatch)
    review=authority.seal_final_readback(**args)
    clock=[args['now_ns']];cancel=Event()
    kwargs=dict(root=tmp_path,authority=authority,review_raw=review,evidence=args,
        cancellation=cancel,clock_ns=lambda:clock[0],check_current=lambda:None)
    return kwargs,clock,cancel,kernel


def test_final_consumption_is_durable_once_and_no_device_dispatch(tmp_path,monkeypatch):
    kwargs,_,_,kernel=prepared(tmp_path,monkeypatch)
    scope=module.FinalReadbackConsumption(**kwargs)
    result=scope.consume()
    assert not result['motion_authorized'] and not result['native_dispatch_implemented']
    assert scope._state=='CONSUMED' and not kernel.writes
    with pytest.raises(ValueError): scope.consume()
    with pytest.raises((ValueError,OSError,RuntimeError)): module.FinalReadbackConsumption(**kwargs)


@pytest.mark.parametrize('fault',['cancel','capture','selection','reservation','legacy','context','clock'])
def test_preconsumption_faults_hold_without_consumed_record(tmp_path,monkeypatch,fault):
    kwargs,clock,cancel,kernel=prepared(tmp_path,monkeypatch)
    scope=module.FinalReadbackConsumption(**kwargs)
    if fault=='cancel': cancel.set()
    elif fault=='clock': clock[0]-=1
    elif fault=='context': scope._current=lambda:False
    else:
        suffix={'capture':'final-capture.original','selection':'owned-selection',
            'reservation':'final-reservation','legacy':'consumed'}[fault]
        (tmp_path/(scope._prefix+suffix+'.json')).write_bytes(b'{}')
    with pytest.raises(ValueError): scope.consume()
    assert scope._state=='HELD' and not scope._path(scope._name).exists() and not kernel.writes


@pytest.mark.parametrize('fault',['expiry','changed','storage'])
def test_failure_during_consumption_cannot_reconstruct_attempt(tmp_path,monkeypatch,fault):
    kwargs,clock,_,kernel=prepared(tmp_path,monkeypatch)
    scope=module.FinalReadbackConsumption(**kwargs)
    publish=module.publish_reservation_bytes
    def altered(root,name,raw,**limits):
        if fault=='storage': raise OSError('synthetic publication failure')
        result=publish(root,name,raw,**limits)
        if fault=='expiry': clock[0]+=101_000_000
        else: (root/name).write_bytes(b'{}')
        return result
    monkeypatch.setattr(module,'publish_reservation_bytes',altered)
    with pytest.raises((ValueError,OSError)): scope.consume()
    assert scope._state=='HELD' and not kernel.writes
    monkeypatch.setattr(module,'publish_reservation_bytes',publish)
    with pytest.raises((ValueError,OSError,RuntimeError)): module.FinalReadbackConsumption(**kwargs)


def test_age_rechecked_after_record_reads_not_only_before(tmp_path,monkeypatch):
    kwargs,clock,_,kernel=prepared(tmp_path,monkeypatch)
    scope=module.FinalReadbackConsumption(**kwargs)
    read=scope._read
    def delayed(name,maximum=65536):
        result=read(name,maximum)
        if name.endswith('final-reservation.json'): clock[0]+=101_000_000
        return result
    monkeypatch.setattr(scope,'_read',delayed)
    with pytest.raises(ValueError,match='expired during retained-record'):
        scope.consume()
    assert scope._state=='HELD' and not kernel.writes


def test_selection_read_once_per_verification_not_cached_between_checks(tmp_path,monkeypatch):
    kwargs,_,_,_=prepared(tmp_path,monkeypatch)
    scope=module.FinalReadbackConsumption(**kwargs)
    read=scope._read;names=[]
    def tracked(name,maximum=65536):
        names.append(name);return read(name,maximum)
    monkeypatch.setattr(scope,'_read',tracked)
    scope._verify();scope._verify()
    assert names.count(scope._prefix+'owned-selection.json')==2
    (tmp_path/(scope._prefix+'owned-selection.json')).write_bytes(b'{}')
    with pytest.raises(ValueError,match='Retained original selection changed'): scope.consume()

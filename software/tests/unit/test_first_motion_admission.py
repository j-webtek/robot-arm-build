"""Real codecs/readers with synthetic files/context; never instantiate native I/O."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json

import pytest

from rocell.application.first_motion_contract import canonical
from rocell.safety.first_motion_review_authority import (
    FirstMotionReviewAuthority, AuthenticatedFirstMotionReviewReader,
    FirstMotionCurrentContext, OPERATOR_CHECKS,
)
from rocell.safety.first_motion_admission import authorize_first_motion, FirstMotionPermit
from rocell.providers.windows.endpoint_serial_api import WindowsEndpointSerialApi
from test_first_motion_measurement_binding import setup as measurement_setup, SESSION, OPERATION
from test_first_motion_review_authority import originals


def setup(tmp_path):
    _,r=measurement_setup(tmp_path)
    clock=[2_000_000_000]
    authority=FirstMotionReviewAuthority(b'a'*32)
    reviews=originals(r)
    for name in OPERATOR_CHECKS:
        row=json.loads(reviews[name]); row['recorded_ns']=2_000_000_000
        row['expires_ns']=32_000_000_000; reviews[name]=canonical(row)
    path=tmp_path/(r.to_dict()['attempt_id']+'-first-motion-reviews.json')
    path.write_bytes(authority.seal(r,reviews,now_ns=clock[0]))
    def current():
        return FirstMotionCurrentContext(r.to_dict()['attempt_id'],(0x10c4,0xea60,'A'*32),
            tuple(sorted(r.to_dict()['references'].items())),clock[0],'COM7')
    reader=AuthenticatedFirstMotionReviewReader(r,authority=authority,root=tmp_path,
        measurement_session_id=SESSION,measurement_operation_id=OPERATION,
        context_reader=current,clock_ns=lambda:clock[0])
    return r,reader,clock,path


def admit(tmp_path,r,reader,clock):
    return authorize_first_motion(r,evidence_reader=reader,attempt_root=tmp_path,clock=lambda:clock[0])


def test_one_open_one_consumption_one_dispatch_and_no_cartesian_adapter(tmp_path):
    r,reader,clock,_=setup(tmp_path); permit=admit(tmp_path,r,reader,clock)
    connection=r.to_dict()['attempt_id']
    with pytest.raises(ValueError): WindowsEndpointSerialApi.from_bench_permit(r,permit,port_name='COM7',connection_id=connection)
    permit.claim_native_open(r,connection,'COM7')
    with pytest.raises(ValueError): permit.claim_native_open(r,connection,'COM7')
    permit.validate_native_open(r,connection,'COM7')
    assert permit.consume_for_write(r,connection,baseline_acquired_ns=clock[0])
    assert not permit.consume_for_write(r,connection,baseline_acquired_ns=clock[0])
    permit.claim_native_dispatch(r,connection,'COM7')
    with pytest.raises(ValueError): permit.claim_native_dispatch(r,connection,'COM7')
    with pytest.raises(Exception): admit(tmp_path,r,reader,clock)


def test_early_consumption_burns_permission(tmp_path):
    r,reader,clock,_=setup(tmp_path); p=admit(tmp_path,r,reader,clock)
    connection=r.to_dict()['attempt_id']
    assert not p.consume_for_write(r,connection,baseline_acquired_ns=clock[0])
    with pytest.raises(ValueError): p.claim_native_open(r,connection,'COM7')


@pytest.mark.parametrize('port',[None,'COM8','../COM7','COM9999'])
def test_failed_open_revalidation_cannot_be_retried(tmp_path,port):
    r,reader,clock,_=setup(tmp_path); p=admit(tmp_path,r,reader,clock)
    connection=r.to_dict()['attempt_id']
    with pytest.raises(ValueError): p.claim_native_open(r,connection,port)
    with pytest.raises(ValueError): p.claim_native_open(r,connection,'COM7')


@pytest.mark.parametrize('baseline',[True,0,1_000_000_000,2_000_000_001])
def test_invalid_baseline_capture_time_consumes_attempt(tmp_path,baseline):
    r,reader,clock,_=setup(tmp_path); p=admit(tmp_path,r,reader,clock)
    connection=r.to_dict()['attempt_id']; p.claim_native_open(r,connection,'COM7')
    assert not p.consume_for_write(r,connection,baseline_acquired_ns=baseline)
    assert not p.consume_for_write(r,connection,baseline_acquired_ns=clock[0])


@pytest.mark.parametrize('changed_file',['reviews','reservation'])
def test_changed_reserved_bytes_or_review_bytes_refuse_write(tmp_path,changed_file):
    r,reader,clock,path=setup(tmp_path); p=admit(tmp_path,r,reader,clock)
    connection=r.to_dict()['attempt_id']; p.claim_native_open(r,connection,'COM7')
    if changed_file=='reservation':
        path=tmp_path/(connection+'-first-motion-reserved.json')
    path.write_bytes(b'{}')
    assert not p.consume_for_write(r,connection,baseline_acquired_ns=clock[0])


@pytest.mark.parametrize('clock_delta',[100_000_001,-1])
def test_old_observation_and_backwards_clock_refuse_dispatch(tmp_path,clock_delta):
    r,reader,clock,_=setup(tmp_path); p=admit(tmp_path,r,reader,clock)
    connection=r.to_dict()['attempt_id']; p.claim_native_open(r,connection,'COM7')
    assert p.consume_for_write(r,connection,baseline_acquired_ns=clock[0])
    clock[0]+=clock_delta
    with pytest.raises(ValueError): p.claim_native_dispatch(r,connection,'COM7')


def test_port_change_after_open_refuses_consumption(tmp_path):
    r,reader,clock,_=setup(tmp_path); p=admit(tmp_path,r,reader,clock)
    connection=r.to_dict()['attempt_id']; p.claim_native_open(r,connection,'COM7')
    original=reader._context
    reader._context=lambda:replace(original(),port_name='COM8')
    assert not p.consume_for_write(r,connection,baseline_acquired_ns=clock[0])


@pytest.mark.parametrize('port',[None,'COM8'])
def test_dispatch_cannot_omit_or_replace_pinned_port(tmp_path,port):
    r,reader,clock,_=setup(tmp_path); p=admit(tmp_path,r,reader,clock)
    connection=r.to_dict()['attempt_id']; p.claim_native_open(r,connection,'COM7')
    assert p.consume_for_write(r,connection,baseline_acquired_ns=clock[0])
    with pytest.raises(ValueError): p.claim_native_dispatch(r,connection,port)
    with pytest.raises(ValueError): p.claim_native_dispatch(r,connection,'COM7')


def test_explicit_revocation_prevents_dispatch(tmp_path):
    r,reader,clock,_=setup(tmp_path); p=admit(tmp_path,r,reader,clock)
    connection=r.to_dict()['attempt_id']; p.claim_native_open(r,connection,'COM7')
    assert p.consume_for_write(r,connection,baseline_acquired_ns=clock[0])
    p.revoke()
    with pytest.raises(ValueError): p.claim_native_dispatch(r,connection,'COM7')


def test_current_identity_is_rechecked(tmp_path):
    r,reader,clock,_=setup(tmp_path); p=admit(tmp_path,r,reader,clock)
    original=reader._context
    reader._context=lambda:replace(original(),usb_identity=(0x10c4,0xea60,'B'*32))
    with pytest.raises(ValueError): p.claim_native_open(r,r.to_dict()['attempt_id'],'COM7')


def test_reservation_survives_failed_post_reservation_check(tmp_path):
    r,reader,clock,_=setup(tmp_path); original=reader._context; calls=[]
    def context():
        calls.append(1)
        if len(calls)==2: raise ValueError('identity unavailable')
        return original()
    reader._context=context
    with pytest.raises(ValueError): admit(tmp_path,r,reader,clock)
    assert (tmp_path/(r.to_dict()['attempt_id']+'-first-motion-reserved.json')).exists()
    reader._context=original
    with pytest.raises(Exception): admit(tmp_path,r,reader,clock)


def test_only_authenticated_reader_and_issuer_accepted(tmp_path):
    r,reader,clock,_=setup(tmp_path)
    with pytest.raises(ValueError): authorize_first_motion(r,evidence_reader=lambda:reader(),attempt_root=tmp_path)
    with pytest.raises(ValueError): FirstMotionPermit(object(),r,reader,None,(),lambda:clock[0],clock[0])


def test_concurrent_consumption_has_one_winner(tmp_path):
    r,reader,clock,_=setup(tmp_path); p=admit(tmp_path,r,reader,clock)
    connection=r.to_dict()['attempt_id']; p.claim_native_open(r,connection,'COM7')
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes=list(pool.map(lambda _:p.consume_for_write(r,connection,baseline_acquired_ns=clock[0]),range(2)))
    assert sorted(outcomes)==[False,True]

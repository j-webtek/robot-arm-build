import base64
from concurrent.futures import ThreadPoolExecutor
import pytest

from test_positional_current_context import fixture
from rocell.safety.positional_campaign_admission import admit_positional_campaign
from rocell.application.positional_campaign_rehearsal import _capture


def setup(tmp_path):
    reader,_,_,binding=fixture(tmp_path)
    original=reader.verify_endpoint(binding.identity.port_name)
    now=[2_030_000_000]
    # Authentication/resolution are separately tested using the actual resolver.
    # This fixed reader result isolates admission timing/state fault injection.
    reader.verify_endpoint=lambda port=None:dict(original,verified_at_ns=now[0])
    admission=admit_positional_campaign(reader.request,reader=reader,root=tmp_path)
    return admission,reader,now


@pytest.mark.parametrize('phase,required_s', [('open', 24), ('leg', 10), ('dispatch', 8)])
def test_campaign_phase_reserves_exact_work_and_cleanup_boundary(tmp_path, phase, required_s):
    _, reader, _ = setup(tmp_path)
    request = reader.request
    last_start = request.to_dict()['deadline_ns'] - required_s * 1_000_000_000
    request.require_remaining_time(last_start, phase=phase)
    with pytest.raises(ValueError, match='cleanup budget'):
        request.require_remaining_time(last_start + 1, phase=phase)


@pytest.mark.parametrize('now', [True, 1.5, -1, 2**63])
def test_campaign_budget_does_not_accept_invalid_clock_values(tmp_path, now):
    _, reader, _ = setup(tmp_path)
    with pytest.raises(ValueError):
        reader.request.require_remaining_time(now, phase='leg')


def test_campaign_budget_rejects_unknown_phase(tmp_path):
    _, reader, clock = setup(tmp_path)
    with pytest.raises(ValueError, match='Unknown campaign timing phase'):
        reader.request.require_remaining_time(clock[0], phase='resume')


def test_reserved_but_unsubmitted_leg_cannot_commit_an_endpoint(tmp_path):
    admission, _, clock = setup(tmp_path)
    admission.claim_open()
    baseline(admission, clock)
    admission.consume_command()
    with pytest.raises(ValueError, match='No submitted campaign leg'):
        admission.commit_endpoint(b'', [], started_ns=clock[0], finished_ns=clock[0],
            confirmed_write_bytes=0, write_finished_ns=clock[0], write_uncertain=False)
    assert not list(tmp_path.glob('*-result.json'))


@pytest.mark.parametrize('payload', [b'{}\n', b'', bytearray(b'{}')])
def test_changed_submission_payload_burns_leg(tmp_path, payload):
    admission, _, clock = setup(tmp_path)
    admission.claim_open()
    baseline(admission, clock)
    original = admission.consume_command()
    with pytest.raises(ValueError, match='Exact reserved campaign payload'):
        admission.claim_submission(payload, clock[0])
    with pytest.raises(ValueError):
        admission.claim_submission(original, clock[0])
    assert len(list(tmp_path.glob('*-dispatch.json'))) == 1


def test_concurrent_submission_claims_allow_only_one(tmp_path):
    admission, _, clock = setup(tmp_path)
    admission.claim_open()
    baseline(admission, clock)
    payload = admission.consume_command()
    def submit(_):
        try:
            admission.claim_submission(payload, clock[0])
            return True
        except ValueError:
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(submit, range(2))) == 1
    with pytest.raises(ValueError):
        admission.claim_submission(payload, clock[0])


def arguments(capture):
    return base64.b64decode(capture['raw_base64']),capture['read_windows']


def baseline(admission,now,start=0.,tick=3_000_000_000):
    cap=_capture(start,start,tick,baseline=True)
    now[0]=cap['finished_ns']+20_000_000
    return admission.bind_baseline(*arguments(cap),started_ns=cap['started_ns'],finished_ns=cap['finished_ns'])


def endpoint(admission,now,start,target,tick=4_040_000_000,fault='NONE',uncertain=False):
    admission.claim_submission(admission._payload, now[0])
    cap=_capture(start,target,tick,fault=fault)
    now[0]=cap['finished_ns']+20_000_000
    return admission.commit_endpoint(*arguments(cap),started_ns=cap['started_ns'],finished_ns=cap['finished_ns'],
        confirmed_write_bytes=len(admission._payload),write_finished_ns=tick-1,write_uncertain=uncertain)


def test_two_explicit_commands_require_verified_predecessor(tmp_path):
    admission,reader,now=setup(tmp_path)
    admission.claim_open()
    targets=[leg['target_rad'] for leg in reader.request.to_dict()['legs']]
    baseline(admission,now)
    first=admission.consume_command()
    with pytest.raises(ValueError): admission.consume_command()
    result=endpoint(admission,now,0.,targets[0])
    assert result['state']=='OPEN_CLAIMED'
    baseline(admission,now,targets[0],9_100_000_000)
    second=admission.consume_command()
    assert first!=second
    result=endpoint(admission,now,targets[0],targets[1],10_140_000_000)
    assert result['state']=='COMPLETE'
    with pytest.raises(ValueError): admission.claim_open()
    with pytest.raises(ValueError): admission.consume_command()
    with pytest.raises(Exception): admit_positional_campaign(reader.request,reader=reader,root=tmp_path)
    assert len(list(tmp_path.glob('*-dispatch.json')))==2


@pytest.mark.parametrize('case', ['bool', 'float', 'regression', 'expired', 'wrong_process'])
def test_final_dispatch_time_fault_burns_claim(tmp_path, monkeypatch, case):
    import rocell.safety.positional_campaign_admission as module
    admission, _, now = setup(tmp_path)
    admission.claim_open()
    baseline(admission, now)
    admission.consume_command()
    value = now[0]
    if case == 'bool': value = True
    elif case == 'float': value = float(value)
    elif case == 'regression': value -= 1
    elif case == 'expired': value = admission._acquired + 250_000_001
    elif case == 'wrong_process':
        monkeypatch.setattr(module.os, 'getpid', lambda: admission._pid + 1)
    with pytest.raises(ValueError): admission.check_dispatch_time(value)
    with pytest.raises(ValueError): admission.consume_command()
    with pytest.raises(ValueError): admission.check_dispatch_time(now[0])
    assert len(list(tmp_path.glob('*-dispatch.json'))) == 1


def test_final_dispatch_time_accepts_exact_recency_boundary(tmp_path):
    admission, _, now = setup(tmp_path)
    admission.claim_open()
    baseline(admission, now)
    with pytest.raises(ValueError): admission.check_dispatch_time(now[0])
    admission.consume_command()
    admission.check_dispatch_time(admission._acquired + 250_000_000)
    # Passing a clock check never creates another command or reservation.
    with pytest.raises(ValueError): admission.consume_command()
    assert len(list(tmp_path.glob('*-dispatch.json'))) == 1


@pytest.mark.parametrize('fault',['NO_RESPONSE','OTHER_JOINT','DEPARTURE','OSCILLATION'])
def test_missed_or_faulted_endpoint_blocks_later_commands(tmp_path,fault):
    admission,reader,now=setup(tmp_path)
    admission.claim_open()
    baseline(admission,now)
    admission.consume_command()
    result=endpoint(admission,now,0.,reader.request.to_dict()['legs'][0]['target_rad'],fault=fault)
    assert result['state']=='HELD'
    with pytest.raises(ValueError): baseline(admission,now,tick=9_100_000_000)
    assert len(list(tmp_path.glob('*-dispatch.json')))==1


def test_negative_directional_shortfall_is_not_compensated(tmp_path):
    admission,reader,now=setup(tmp_path)
    admission.claim_open()
    targets=[leg['target_rad'] for leg in reader.request.to_dict()['legs']]
    baseline(admission,now)
    admission.consume_command()
    assert endpoint(admission,now,0.,targets[0])['state']=='OPEN_CLAIMED'
    baseline(admission,now,targets[0],9_100_000_000)
    admission.consume_command()
    result=endpoint(admission,now,targets[0],targets[1],10_140_000_000,fault='DIRECTIONAL_OFFSET')
    assert result['state']=='HELD'
    assert result['endpoint']['status']=='TARGET_MISSED'
    assert len(list(tmp_path.glob('*-dispatch.json')))==2


def test_uncertain_write_never_advances_even_if_endpoint_matches(tmp_path):
    admission,reader,now=setup(tmp_path)
    admission.claim_open()
    baseline(admission,now)
    admission.consume_command()
    result=endpoint(admission,now,0.,reader.request.to_dict()['legs'][0]['target_rad'],uncertain=True)
    assert result['state']=='HELD'
    assert result['endpoint']['status']=='TRANSPORT_FAULT'


@pytest.mark.parametrize('fault',['stale','drift','changed_original','expired','changed_review'])
def test_pre_dispatch_failures_burn_eligibility(tmp_path,fault):
    admission,reader,now=setup(tmp_path)
    admission.claim_open()
    if fault=='drift':
        with pytest.raises(ValueError): baseline(admission,now,start=.1)
    else:
        baseline(admission,now)
        if fault=='stale': now[0]+=300_000_000
        if fault=='expired': now[0]=31_000_000_000
        if fault=='changed_original': next(tmp_path.glob('*-reserved.json')).write_bytes(b'{}')
        if fault=='changed_review': reader.verify_endpoint=lambda port=None:dict(bundle_sha256='d'*64,verified_at_ns=now[0])
        with pytest.raises(Exception): admission.consume_command()
    with pytest.raises(ValueError): admission.consume_command()
    assert not list(tmp_path.glob('*-dispatch.json'))


def test_concurrent_consume_only_returns_one_payload(tmp_path):
    admission,_,now=setup(tmp_path)
    admission.claim_open()
    baseline(admission,now)
    def consume(_):
        try: return admission.consume_command()
        except ValueError: return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(value is not None for value in pool.map(consume,range(2)))==1


@pytest.mark.parametrize('boundary',['reservation','dispatch','result'])
def test_storage_failure_holds_campaign(tmp_path,monkeypatch,boundary):
    from rocell.safety import positional_campaign_admission as module
    admission,reader,now=setup(tmp_path)
    admission.claim_open()
    method='publish_reservation_bytes'
    original=getattr(module,method)
    suffix={'reservation':'-leg-01-reserved.json','dispatch':'-leg-01-dispatch.json','result':'-leg-01-result.json'}[boundary]
    def fail(root,name,raw,**kwargs):
        if name.endswith(suffix):
            original(root,name,raw,**kwargs)
            raise OSError('Injected uncertainty after publication')
        return original(root,name,raw,**kwargs)
    monkeypatch.setattr(module,method,fail)
    with pytest.raises(OSError):
        baseline(admission,now)
        admission.consume_command()
        endpoint(admission,now,0.,reader.request.to_dict()['legs'][0]['target_rad'])
    with pytest.raises(ValueError): admission.consume_command()
    assert not list(tmp_path.glob('*-leg-02-reserved.json'))


def test_revocation_never_rearms(tmp_path):
    admission,_,now=setup(tmp_path)
    admission.claim_open()
    baseline(admission,now)
    admission.revoke()
    with pytest.raises(ValueError): admission.consume_command()
    with pytest.raises(ValueError): admission.claim_open()

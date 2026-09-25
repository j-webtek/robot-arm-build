import json
from threading import Event
import pytest

from test_positional_campaign_admission import setup,baseline
from rocell.application.positional_owned_campaign import run_owned_positional_campaign
from rocell.application.endpoint_owned_trial import EndpointCleanupResult
from rocell.application.positional_campaign_capture import capture_campaign_window,validate_campaign_capture


def run(tmp_path,fault=None,*,cancellation=None,fragment_size=None,corruption_leg=None):
    admission,reader,clock=setup(tmp_path)
    admission.claim_open()
    event=cancellation if cancellation is not None else Event()
    counts=dict(read=0,write=0,close=0,commands=[])
    angle=[0.]
    pending=bytearray()
    post_reads=[0]
    corrupted=[False]
    if fault=='cancel_before': event.set()
    def read(size,timeout):
        counts['read']+=1
        clock[0]+=min(10 if fragment_size else 50,timeout)*1_000_000
        if fault=='malformed' and counts['write']: return b'bad\n'
        if fault=='late_read': clock[0]+=200_000_000
        raw=json.dumps(dict(T=1051,x=0,y=0,z=0,tit=0,b=0,s=0,e=0,t=angle[0],r=0,g=0),separators=(',',':')).encode()+b'\n'
        if fragment_size:
            if counts['write']:
                post_reads[0]+=1
            if not pending:
                # Keep a single stream across capture boundaries. No purging or
                # re-framing on a write; the next packet may be partly buffered.
                if counts['write']==corruption_leg and post_reads[0]>12 and not corrupted[0]:
                    raw=b'corrupted-interior-record\n'
                    corrupted[0]=True
                pending.extend(raw)
            chunk=bytes(pending[:min(size,fragment_size)])
            del pending[:len(chunk)]
            return chunk
        assert len(raw)<=size
        return raw
    def write(payload):
        counts['write']+=1
        post_reads[0]=0
        counts['commands'].append(json.loads(payload))
        if fault!='no_response': angle[0]=json.loads(payload)['rad']
        if fault=='write_error': raise OSError('Injected uncertain write')
        if fault=='cancel_after': event.set()
        if fault=='clock_error': clock[0]=-1
        return len(payload)-1 if fault=='short_write' else len(payload)
    def close(timeout):
        counts['close']+=1
        assert timeout==2000
        if fault=='close_error': raise OSError('Injected close failure')
        return EndpointCleanupResult(True,0)
    if fault == 'insufficient_leg_budget':
        clock[0] = reader.request.to_dict()['deadline_ns'] - 10_000_000_000 + 1
    result=run_owned_positional_campaign(reader.request,admission,read_once=read,write_once=write,
        close_once=close,cancellation=event,basis='SYNTHETIC_WIRE_REHEARSAL',clock_ns=lambda:clock[0],
        idle_wait=lambda seconds:clock.__setitem__(0,clock[0]+round(seconds*1e9)))
    return result,counts


def test_late_campaign_does_not_begin_baseline_but_still_closes_once(tmp_path):
    result, counts = run(tmp_path, 'insufficient_leg_budget')
    assert result['status'] == 'HELD'
    assert counts['read'] == counts['write'] == 0
    assert counts['close'] == 1
    assert result['legs'] == []
    assert result['skipped_leg_ids'] == ['leg-01', 'leg-02']
    assert result['cleanup']['status'] == 'HANDLES_CLOSED'
    assert result['physical_stop_verified'] is False


def test_real_collector_and_admission_sequence_two_legs(tmp_path):
    result,counts=run(tmp_path)
    assert result['status']=='SIMULATION_COMPLETE',result
    assert result['reconstruction']['valid']
    assert counts['write']==2
    assert counts['close']==1
    assert all(leg['verification']['endpoint']['endpoint_verified'] for leg in result['legs'])
    # Synthetic repeated target reports exercise progression, but contain no
    # per-servo read status or sequence. They cannot qualify native progression.
    assert all(not leg['verification']['endpoint']['device_sample_freshness_verified']
               for leg in result['legs'])
    assert result['native_execution_released'] is False
    assert result['physical_write_count']==0
    assert all(command['T']==101 and command['joint']==4 for command in counts['commands'])
    assert result['skipped_leg_ids']==[]


@pytest.mark.parametrize('fragment_size', [23, 37, 61])
def test_fragmented_stream_crosses_captures_without_losing_endpoint_evidence(tmp_path, fragment_size):
    result, counts = run(tmp_path, fragment_size=fragment_size)
    assert result['status'] == 'SIMULATION_COMPLETE', result
    assert result['reconstruction']['valid']
    assert counts['write'] == 2 and counts['close'] == 1
    assert all(leg['verification']['endpoint']['endpoint_verified'] for leg in result['legs'])
    assert all(leg['baseline']['read_calls'] > 20 for leg in result['legs'])
    assert result['physical_write_count'] == 0


@pytest.mark.parametrize('leg', [1, 2])
def test_interior_corruption_in_fragmented_stream_holds_and_retains_raw(tmp_path, leg):
    import base64
    result, counts = run(tmp_path, fragment_size=23, corruption_leg=leg)
    assert result['status'] != 'SIMULATION_COMPLETE', result
    assert counts['write'] == leg and counts['close'] == 1
    assert len(result['legs']) == leg
    raw = b''.join(base64.b64decode(c) for c in result['legs'][-1]['post']['raw']['base64_chunks'])
    assert b'corrupted-interior-record\n' in raw
    assert len(result['skipped_leg_ids']) == 2 - leg
    assert result['physical_stop_verified'] is False


@pytest.mark.parametrize('fault',['cancel_before','cancel_after','malformed','late_read','write_error',
    'short_write','no_response','close_error','clock_error'])
def test_failure_preserves_cleanup_and_never_retries(tmp_path,fault):
    result,counts=run(tmp_path,fault)
    assert result['status']!='SIMULATION_COMPLETE'
    assert counts['write']<=1 if fault!='close_error' else counts['write']==2
    assert counts['close']==1
    assert result['physical_write_count']==0
    # Fault handling must never smuggle in unqualified stop/torque/reset/home
    # commands. Withholding later goals is not represented as a physical stop.
    assert all(command['T']==101 and command['joint']==4 for command in counts['commands'])
    assert result['physical_stop_verified'] is False
    if fault in ('write_error','short_write'):
        assert result['legs'][0]['post'] is not None
        assert result['legs'][0]['verification']['endpoint']['status']=='TRANSPORT_FAULT'


def test_delayed_post_start_keeps_write_anchored_deadline(tmp_path):
    admission,reader,clock=setup(tmp_path)
    admission.claim_open()
    baseline(admission,clock)
    payload=admission.consume_command()
    completed=clock[0]
    admission.claim_submission(payload, completed)
    clock[0]+=30_000_000
    def read(size,timeout):
        clock[0]+=min(50,timeout)*1_000_000
        return json.dumps(dict(T=1051,x=0,y=0,z=0,tit=0,b=0,s=0,e=0,
            t=json.loads(payload)['rad'],r=0,g=0),separators=(',',':')).encode()+b'\n'
    capture=capture_campaign_window(reader.request,'post',read_once=read,cancellation=Event(),
        clock_ns=lambda:clock[0],idle_wait=lambda seconds:clock.__setitem__(0,clock[0]+round(seconds*1e9)),
        command_completed_ns=completed)
    raw=validate_campaign_capture(reader.request,capture,phase='post',command_completed_ns=completed)
    assert capture['window_deadline_ns']==completed+5_000_000_000
    assert capture['finished_ns']-capture['started_ns']==4_970_000_000
    result=admission.commit_endpoint(raw,capture['read_windows'],started_ns=capture['started_ns'],
        finished_ns=capture['finished_ns'],confirmed_write_bytes=len(payload),write_finished_ns=completed,write_uncertain=False)
    assert result['state']=='OPEN_CLAIMED'


def test_unreleased_physical_provenance_never_reaches_io(tmp_path):
    admission,reader,_=setup(tmp_path)
    calls=[]
    def io(*args):
        calls.append(args)
        raise AssertionError('Unreleased native path reached IO')
    with pytest.raises(ValueError):
        run_owned_positional_campaign(reader.request,admission,read_once=io,write_once=io,
            close_once=io,cancellation=Event(),basis='RETAINED_PHYSICAL_CAPTURE')
    assert calls==[]


def test_existing_single_trial_facade_rejects_campaign_admission(tmp_path,monkeypatch):
    from rocell.providers.windows.observational_serial_api import WindowsObservationalSerialApi
    admission,reader,_=setup(tmp_path)
    def forbidden(*args,**kwargs):
        raise AssertionError('Rejected campaign reached native facade construction')
    monkeypatch.setattr(WindowsObservationalSerialApi,'__init__',forbidden)
    with pytest.raises(ValueError):
        WindowsObservationalSerialApi.from_observational_permit(reader.request,admission,
            port_name='COM7',connection_id=reader.request.to_dict()['campaign_id'])


@pytest.mark.parametrize('delay_ns', [251_000_000, 7_000_000_000])
def test_cpu_stall_after_consumption_withholds_write_and_closes(tmp_path, monkeypatch, delay_ns):
    from rocell.safety.positional_campaign_admission import PositionalCampaignAdmission
    original = PositionalCampaignAdmission.consume_command
    original_check = PositionalCampaignAdmission.check_dispatch_time
    consumed = []
    def consume(self):
        payload = original(self)
        consumed.append(self)
        return payload
    def delayed_check(self, dispatch_ns):
        # Model elapsed scheduler time at the executor's final dispatch check.
        return original_check(self, dispatch_ns + delay_ns)
    monkeypatch.setattr(PositionalCampaignAdmission, 'consume_command', consume)
    monkeypatch.setattr(PositionalCampaignAdmission, 'check_dispatch_time', delayed_check)
    result, counts = run(tmp_path)
    assert result['status'] == 'HELD', result
    assert len(consumed) == 1
    assert counts['write'] == result['simulated_write_attempts'] == 0
    assert counts['close'] == 1
    assert result['legs'][0]['write'] is None
    assert len(result['skipped_leg_ids']) == 1
    assert result['native_execution_released'] is False
    assert result['physical_stop_verified'] is False
    with pytest.raises(ValueError):
        consumed[0].consume_command()
    # The durable dispatch claim survives even though submission was withheld.
    assert len(list(tmp_path.rglob('*-dispatch.json'))) == 1


@pytest.mark.parametrize('cancel_leg', [1, 2])
def test_cancel_during_final_dispatch_check_withholds_selected_leg(tmp_path, monkeypatch, cancel_leg):
    from rocell.safety.positional_campaign_admission import PositionalCampaignAdmission
    event = Event()
    original = PositionalCampaignAdmission.check_dispatch_time
    checked = []
    def cancel_at_check(self, dispatch_ns):
        original(self, dispatch_ns)
        checked.append(self)
        if len(checked) == cancel_leg:
            event.set()
    monkeypatch.setattr(PositionalCampaignAdmission, 'check_dispatch_time', cancel_at_check)
    result, counts = run(tmp_path, cancellation=event)
    assert result['status'] == 'CANCELLED', result
    assert counts['write'] == result['simulated_write_attempts'] == cancel_leg - 1
    assert counts['close'] == 1
    assert result['legs'][-1]['write'] is None
    assert result['legs'][-1]['post'] is None
    assert result['physical_stop_verified'] is False
    assert len(list(tmp_path.rglob('*-dispatch.json'))) == cancel_leg
    with pytest.raises(ValueError):
        checked[-1].consume_command()


@pytest.mark.parametrize('cancel_leg', [1, 2])
def test_cancellation_at_submission_claim_withholds_actual_write(tmp_path, monkeypatch, cancel_leg):
    from rocell.safety.positional_campaign_admission import PositionalCampaignAdmission
    event = Event()
    original = PositionalCampaignAdmission.claim_submission
    claims = []
    def claim_and_cancel(self, payload, now):
        original(self, payload, now)
        claims.append(self)
        if len(claims) == cancel_leg:
            event.set()
    monkeypatch.setattr(PositionalCampaignAdmission, 'claim_submission', claim_and_cancel)
    result, counts = run(tmp_path, cancellation=event)
    assert result['status'] == 'CANCELLED'
    assert counts['write'] == cancel_leg - 1
    assert counts['close'] == 1
    assert result['legs'][-1]['write'] is None
    assert result['physical_write_count'] == 0
    assert result['physical_stop_verified'] is False

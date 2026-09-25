import json
import pytest
from rocell.providers.windows import wifi_discrete_native as native
from test_wifi_discrete_runner import setup
from test_arm_wifi_deadline import wire
from test_arrival_wizard_service import make_service,_run,_ticket


def test_exact_native_dispatch_consumes_and_replay_denied(tmp_path,wire,monkeypatch):
    reservation,_,_,_,_,_=setup(tmp_path)
    now,sent,sock,factory=wire
    monkeypatch.setattr(native,'neighbor_mac',lambda:native.MAC)
    monkeypatch.setattr(native.time,'perf_counter_ns',lambda:10_000_000_000)
    payload=reservation.consume(reservation.command(),now_ns=10_000_000_000,observed_mac=native.MAC)
    c=native._CommandConnection(native.ADDRESS,clock=lambda:now[0])
    c.dispatch(reservation,payload)
    assert len(sent)==1 and b'%22T%22%3A101' in sent[0]
    with pytest.raises(ValueError):c.dispatch(reservation,payload)
    c.close()
    assert sock.closed and (tmp_path/('a'*32+'-wifi-native-send.json')).is_file()


def test_unconsumed_reservation_never_sends(tmp_path,wire,monkeypatch):
    reservation,_,_,_,_,_=setup(tmp_path)
    now,sent,_,_=wire
    monkeypatch.setattr(native,'neighbor_mac',lambda:native.MAC)
    c=native._CommandConnection(native.ADDRESS,clock=lambda:now[0])
    with pytest.raises(ValueError):c.dispatch(reservation,b'{}')
    assert not sent


@pytest.mark.parametrize('raw,accepted',[(b'',True),(b'{}',True),(b'{"ok":1}',True),(b'{"ok":true}',False),(b'{"error":"queue full"}',False),(b'{"T":1051}',False)])
def test_receipt_not_endpoint(tmp_path,monkeypatch,raw,accepted):
    reservation,_,_,_,_,_=setup(tmp_path); closed=[]
    class Connection:
        status=200
        def __init__(self,*a,**k):pass
        def dispatch(self,*a):pass
        def getresponse(self):return self
        def read1(self,n):return raw
        def close(self):closed.append(1)
    monkeypatch.setattr(native,'_CommandConnection',Connection)
    monkeypatch.setattr(native,'neighbor_mac',lambda:native.MAC)
    t=native.NativeDiscreteTransport(reservation)
    if accepted:assert t.send_once(b'{}',deadline_ns=99,cancelled=lambda:False) is True
    else:
        with pytest.raises(ValueError):t.send_once(b'{}',deadline_ns=99,cancelled=lambda:False)
    assert closed==[1] and t.receipt['cleanup_confirmed']


def test_empty_http_receipt_only_for_command_connection(wire):
    from rocell.providers.windows.arm_wifi_deadline import DeadlineFeedbackConnection
    now,sent,sock,factory=wire
    header=b'HTTP/1.1 200 OK\r\nContent-Length: 0'
    feedback=factory()
    with pytest.raises(ValueError):feedback._parse_headers(header)
    command=native._CommandConnection(native.ADDRESS,clock=lambda:now[0])
    assert command._parse_headers(header)==0
    assert command.response_metadata==dict(http_status=200,content_length=0)


@pytest.mark.parametrize('extra',[{}, {'password':'secret'}, {'r':float('nan')}])
def test_numeric_feedback_receipt_never_becomes_endpoint(tmp_path,monkeypatch,extra):
    reservation,_,_,_,_,_=setup(tmp_path)
    body=dict(T=1051,b=0,s=0,e=1,t=0,r=0,g=3);body.update(extra)
    class Connection:
        status=200
        def __init__(self,*a,**k):pass
        def dispatch(self,*a):pass
        def getresponse(self):return self
        def read1(self,n):return json.dumps(body).encode()
        def close(self):pass
    monkeypatch.setattr(native,'_CommandConnection',Connection)
    monkeypatch.setattr(native,'neighbor_mac',lambda:native.MAC)
    transport=native.NativeDiscreteTransport(reservation)
    if extra:
        with pytest.raises(ValueError):transport.send_once(b'{}',deadline_ns=99,cancelled=lambda:False)
        assert 'secret' not in json.dumps(transport.receipt)
    else:
        assert transport.send_once(b'{}',deadline_ns=99,cancelled=lambda:False)
        assert transport.receipt['receipt_kind']=='NUMERIC_FEEDBACK_HTTP_200'
        assert not transport.receipt['receipt_used_as_endpoint']


@pytest.mark.parametrize('status',['FAILED','SUCCEEDED'])
@pytest.mark.parametrize('suffix',['','negative_','low_','high_','zero_','center_up_','center_down_','corrected_up_','corrected_down_','probe_low_','probe_high_'])
def test_wizard_preview_inert_and_result_export(make_service,monkeypatch,status,suffix):
    calls=[]
    def run(**kwargs):calls.append(1);return dict(status=status,outcome={'status':'COMMAND_OUTCOME_UNCERTAIN' if status=='FAILED' else 'REPORTED_ENDPOINT_VERIFIED'})
    action='run_wifi_roll_'+suffix+'trial'
    monkeypatch.setattr(native,'run_native_roll_'+suffix+'trial',run)
    service,runner,_=make_service(mode='physical')
    _ticket(service,action,{})
    assert not calls
    result=_run(service,action)
    assert calls==[1] and result['status']==status
    # An ACK/status without the verifier's evidence must not display arrival.
    assert result['result']['move_result']['status']=='EXECUTION_UNCERTAIN'
    assert (result.get('error') or {}).get('code')!='INVALID_WORKER_RESULT'
    exported = _run(service,'export_logs')
    assert exported['status']=='SUCCEEDED' and not runner.calls
    from pathlib import Path
    from rocell.application.wizard_diagnostic_export import verify_export
    folder = Path(exported['result']['receipt']['path'])
    assert verify_export(folder)['valid']
    retained = [json.loads(path.read_text()) for path in folder.glob('attachment-result-*.json')]
    assert any(item.get('move_result') == result['result']['move_result'] for item in retained)


def test_wizard_real_simulated_transaction_request_to_export(make_service, monkeypatch, tmp_path):
    from pathlib import Path
    reservation, run, sent, _, _, baseline = setup(tmp_path)
    def trial(**kwargs):
        outcome = run()
        return dict(status='SUCCEEDED', baseline=baseline, outcome=outcome)
    monkeypatch.setattr(native, 'run_native_roll_trial', trial)
    service, _, _ = make_service(mode='physical')
    operation = _run(service, 'run_wifi_roll_trial')
    assert len(sent) == 1
    assert operation['result']['move_result']['status'] == 'ARRIVED_REPORTED'
    exported = _run(service, 'export_logs')
    assert exported['status'] == 'SUCCEEDED'
    folder = Path(exported['result']['receipt']['path'])
    report = json.loads((folder / 'report.json').read_text())
    index = report['snapshot']['movement_export_index']
    assert len(index) == 1
    entry = index[0]
    retained = json.loads((folder / entry['attachment']).read_text())
    assert retained['move_result'] == operation['result']['move_result']
    assert entry['configuration_id'] == reservation.request()['configuration_id']
    assert retained['steps'][0]['report']['outcome']['move_request'] == reservation.request()


@pytest.mark.parametrize('start_deg,allowed',[(2.6367,True),(-2.5,False)])
def test_negative_binds_fresh_baseline_and_preserves_limit(tmp_path,monkeypatch,start_deg,allowed):
    import math
    from rocell.providers.windows.arm_wifi_feedback import probe
    from test_arm_wifi_feedback import Connection
    baseline=probe(identity=lambda:native.MAC,clock=lambda:10.,retain_response=True,
        connection_factory=lambda *a,**k:Connection(dict(T=1051,b=0,s=0,e=1,t=0,r=math.radians(start_deg),g=3)))
    monkeypatch.setattr(native,'bounded_probe',lambda **k:baseline)
    monkeypatch.setattr(native.time,'perf_counter_ns',lambda:10_000_000_000)
    calls=[]
    def run(reservation,**kw):
        calls.append(reservation.command())
        return dict(status='SIMULATED_NOT_DISPATCHED')
    monkeypatch.setattr(native,'run_reserved_transaction',run)
    result=native.run_native_roll_negative_trial(root=tmp_path.resolve())
    assert len(calls)==int(allowed)
    assert result['requested_delta_deg']==-1
    if allowed:
        assert calls[0]['rad']==pytest.approx(math.radians(start_deg-1))
        assert calls[0]['joint']==5 and calls[0]['spd']==20 and calls[0]['acc']==1
    else:assert result['reason']=='BASELINE_OR_TARGET_OUTSIDE_FIXED_ENVELOPE'


@pytest.mark.parametrize('side,start,allowed',[
    ('low',2.1,True),('high',1.3,True),('low',.2,False),
    ('high',2.8,False),('low',2.8,False),('high',.1,False),
    ('zero',1.2,True),('center_up',.2,True),('center_down',2.3,True),
    ('zero',-.8,False),('center_up',2.3,False),('center_down',.2,False),
    ('center_up',-1,False),('center_down',3,False),
    ('corrected_up',.3,True),('corrected_down',2.3,True),
    ('corrected_up',2.3,False),('corrected_down',.3,False),
    ('corrected_up',-.5,False),('corrected_down',3,False),
    ('probe_low',2.285,True),('probe_high',2.285,True),
    ('probe_low',2.5,False),('probe_high',3,False),
    ('probe_low',.1,False),('probe_high',.5,False),
    ('lookup',2.285,True),('lookup',2.5,False),('lookup',.1,False),
    ('adjacent',2.285,True),('adjacent',1,False),('adjacent',2,False),('adjacent',3.1,False),
    ('adjacent_low',2.285,True),('adjacent_high',2.285,True),
    ('adjacent_low',1,False),('adjacent_high',1,False),
    ('adjacent_low',3,False),('adjacent_high',3,False),
    ('adjacent_lookup',2.285,True),('adjacent_lookup',3,False),('adjacent_lookup',1,False),
    ('sweep_low',2.285,True),('sweep_center',2.285,True),('sweep_high',2.285,True),
    ('sweep_low',2.6,False),('sweep_center',2.6,False),('sweep_high',2.6,False),
    ('sweep_low',.5,False),('sweep_center',.5,False),('sweep_high',1.2,False)])
def test_fixed_targets_respect_direction_and_existing_delta(tmp_path,monkeypatch,side,start,allowed):
    import math
    from rocell.providers.windows.arm_wifi_feedback import probe
    from test_arm_wifi_feedback import Connection
    baseline=probe(identity=lambda:native.MAC,clock=lambda:10.,retain_response=True,
        connection_factory=lambda *a,**k:Connection(dict(T=1051,b=0,s=0,e=1,t=0,r=math.radians(start),g=3)))
    monkeypatch.setattr(native,'bounded_probe',lambda **k:baseline)
    monkeypatch.setattr(native.time,'perf_counter_ns',lambda:10_000_000_000)
    calls=[]
    def run(reservation,**kw):calls.append(reservation.command());return dict(status='SIMULATED')
    monkeypatch.setattr(native,'run_reserved_transaction',run)
    r=getattr(native,'run_native_roll_'+side+'_trial')(root=tmp_path.resolve())
    assert len(calls)==int(allowed)
    targets={'low':1,'high':2.5,'zero':0,'center_up':1.25,'center_down':1.25,
        'corrected_up':1.3134765703183617,'corrected_down':1.049804687506479,
        'probe_low':.95,'probe_high':1.15,'lookup':.95,'adjacent':1.5,
        'adjacent_low':1.25,'adjacent_high':1.35,'adjacent_lookup':1.25,
        'sweep_low':.85,'sweep_center':.95,'sweep_high':1.05}
    if allowed:assert calls[0]['rad']==pytest.approx(math.radians(targets[side]))
    if side.startswith('adjacent') and side!='adjacent_lookup':
        assert r['characterization']['desired_endpoint_deg']==1.5
        assert not r['characterization']['held_out']
        assert 'correction_candidate' not in r
        if allowed:
            import json
            record=json.loads(next(tmp_path.glob('*-wifi-reserved.json')).read_text())
            assert record['desired_endpoint_rad']==pytest.approx(math.radians(1.5))
    if side.startswith('probe') or side.startswith('sweep'):
        assert r['characterization']['desired_endpoint_deg']==1.25
        assert not r['characterization']['held_out']
        assert not r['characterization']['model_updated']
        if allowed:
            import json
            record=json.loads(next(tmp_path.glob('*-wifi-reserved.json')).read_text())
            assert record['desired_endpoint_rad']==pytest.approx(math.radians(1.25))
    if side.startswith('corrected') or side in ('lookup','adjacent_lookup'):
        desired=1.5 if side=='adjacent_lookup' else 1.25
        assert r['correction_candidate']['desired_endpoint_deg']==desired
        assert r['correction_candidate']['held_out']
        if allowed:
            import json
            record=json.loads(next(tmp_path.glob('*-wifi-reserved.json')).read_text())
            assert record['desired_endpoint_rad']==pytest.approx(math.radians(desired))


def test_changed_candidate_stops_before_hardware(tmp_path,monkeypatch):
    monkeypatch.setattr(native.Path,'read_bytes',lambda self:b'{}')
    monkeypatch.setattr(native,'bounded_probe',lambda **k:pytest.fail('No hardware on changed candidate'))
    with pytest.raises(ValueError,match='Frozen candidate changed'):
        native.run_native_roll_corrected_down_trial(root=tmp_path.resolve())


@pytest.mark.parametrize('suffix',['lookup','adjacent_lookup'])
def test_changed_lookup_stops_before_hardware(tmp_path,monkeypatch,suffix):
    monkeypatch.setattr(native.Path,'read_bytes',lambda self:b'{}')
    monkeypatch.setattr(native,'bounded_probe',lambda **k:pytest.fail('No hardware on changed candidate'))
    with pytest.raises(ValueError,match='Frozen lookup candidate changed'):
        getattr(native,'run_native_roll_'+suffix+'_trial')(root=tmp_path.resolve())

"""Incapable Wi-Fi Cartesian transport tests; no sockets or arm access."""
import json
import math
import pytest
from rocell.arm.cartesian_transaction import CartesianTransaction
from rocell.application.wifi_discrete_runner import run_cartesian_transaction, run_reserved_transaction
from rocell.safety.wifi_cartesian_reservation import WifiCartesianReservation
from rocell.providers.windows.arm_wifi_feedback import probe, MAC
from rocell.providers.windows.wifi_cartesian_native import NativeCartesianTransport, _CartesianCommandConnection
from rocell.providers.windows.wifi_discrete_native import NativeDiscreteTransport, _CommandConnection
from rocell.kinematics.firmware_reference import forward, inverse
from test_arm_wifi_feedback import Connection
from test_arm_wifi_deadline import wire


def setup(tmp_path,mode='normal',elbow_only=False,elbow_degrees=2,compensated_endpoint=False,wrist_candidate=False,feedback_budget_ns=0):
    now=[10.]
    sent=[]
    reads=[]
    joints=[0.,0.,1.523242922 if elbow_degrees in (-1,3) else 1.535514769 if elbow_degrees==1 else 1.512505057 if elbow_degrees==-3 else 1.59,.007,.02,3.149]
    if elbow_degrees in (-4,-5,-6): joints[2]=1.552388557
    if wrist_candidate:
        joints=[.001533981,.007669904,1.563126423,
                .01994175 if wrist_candidate=='extended-start' else .026077673,.01994175,3.138524692]
    start=forward(*joints[:4])
    target=(*start[:2],start[2]+2,start[3])
    if elbow_only:
        target=forward(joints[0],joints[1],joints[2]-math.radians(elbow_degrees),joints[3])
    if elbow_degrees in (1,-1,3,-4,-5,-6):
        from rocell.application.elbow_local_candidate import candidate_record
        candidate=candidate_record(extended_start=elbow_degrees==-1,nearby_target=elbow_degrees==3,descending=elbow_degrees==-4,descending_revised=elbow_degrees==-5,mapping_sample=elbow_degrees==-6)
        target=forward(joints[0],joints[1],candidate['desired_rad' if mode=='desired_candidate' else 'command_rad'],joints[3])
    if wrist_candidate:
        from rocell.application.coordinated_wrist_probe import wrist_candidate_record
        candidate=wrist_candidate_record(extended_start=wrist_candidate=='extended-start')
        target=forward(*joints[:3],candidate['desired_rad' if mode=='desired_candidate' else 'command_rad'])
    def feedback(pose=start):
        angles=[*inverse(*pose),*joints[4:]]
        if mode=='roll_drift' and sent:
            angles[4]+=.1
        fields=dict(zip(('b','s','e','t','r','g'),angles))
        fields.update(zip(('x','y','z','tit'),pose))
        if mode=='incoherent' and sent:
            fields['z']+=1
        if mode=='missing_xyz' and sent:
            del fields['z']
        return probe(identity=lambda:MAC,clock=lambda:now[0],retain_response=True,
            connection_factory=lambda *a,**k:Connection(dict(T=1051,**fields)))
    baseline=feedback()
    reservation=WifiCartesianReservation(root=tmp_path.resolve(),attempt_id='c'*32,
        baseline=baseline,now_ns=10_000_000_000,completion_budget_ns=3_000_000_000,elbow_only=elbow_only,elbow_degrees=elbow_degrees,compensated_endpoint=compensated_endpoint,wrist_probe=bool(wrist_candidate),wrist_candidate=wrist_candidate)
    class Transport:
        def identity(self):return 'wrong' if mode=='wrong_mac' else MAC
        def send_once(self,payload,**kwargs):
            sent.append(payload)
            now[0]+=.05
            if mode=='lost_receipt':raise TimeoutError('private')
            return True
        def feedback(self,**kwargs):
            reads.append(kwargs['deadline_ns'])
            now[0]+=.15
            if mode=='deadline_timeout' and now[0]>=13:
                raise TimeoutError('private')
            if mode=='late':now[0]+=1
            if mode=='reset':raise ConnectionResetError('private')
            return feedback(start if mode in ('unchanged','deadline_timeout') else target)
    def run(cancelled=lambda:False):
        transport=Transport()
        transport.feedback_budget_ns=feedback_budget_ns
        return run_cartesian_transaction(reservation,transport=transport,
            clock_ns=lambda:round(now[0]*1e9),wait=lambda s:now.__setitem__(0,now[0]+s),
            cancelled=cancelled)
    return reservation,run,sent,reads,now,baseline


def test_verified_cartesian_endpoint_is_separate_from_receipt(tmp_path):
    reservation,run,sent,reads,_,baseline=setup(tmp_path)
    result=run()
    assert result['status']=='REPORTED_ENDPOINT_VERIFIED'
    assert result['schema']=='rocell.wifi_cartesian_run.v1'
    assert len(sent)==1 and len(reads)>=3
    command=json.loads(sent[0])
    assert command['T']==104 and command['z']==baseline['controller_cartesian']['values']['z']+2
    assert command['g']==baseline['joints_rad']['g']
    assert result['transaction']['result']['position_error_mm']<1e-6
    assert result['transaction']['result']['endpoint_verified']
    assert not result['physical_accuracy_verified']
    assert run()['status']=='ATTEMPT_ALREADY_USED' and len(sent)==1
    assert (tmp_path/('c'*32+'-wifi-consumed.json')).is_file()


@pytest.mark.parametrize('mode,expected',[
    ('lost_receipt','COMMAND_OUTCOME_UNCERTAIN'),('reset','COMMAND_OUTCOME_UNCERTAIN'),
    ('late','FEEDBACK_GAP_EXCEEDED'),('roll_drift','UNEXPECTED_JOINT_CHANGE'),
    ('incoherent','CONTROLLER_MODEL_MISMATCH'),('missing_xyz','INVALID_FEEDBACK'),
    ('unchanged','COMPLETION_DEADLINE_EXCEEDED'),
    ('deadline_timeout','COMPLETION_DEADLINE_EXCEEDED')])
def test_faults_never_retry_or_claim_arrival(tmp_path,mode,expected):
    _,run,sent,reads,_,_=setup(tmp_path,mode)
    result=run()
    assert result['status']==expected
    assert len(sent)==1
    assert not (result['transaction']['result'] or {}).get('endpoint_verified')
    assert 'private' not in json.dumps(result)
    if mode=='lost_receipt':assert not reads


def test_cancel_before_and_after_dispatch(tmp_path):
    _,run,sent,reads,_,_=setup(tmp_path)
    assert run(lambda:True)['status']=='CANCELLED_BEFORE_DISPATCH'
    assert not sent and not reads
    # A separate request/root is needed; no retry is used for the second case.
    other=tmp_path/'other';other.mkdir()
    _,run,sent,reads,_,_=setup(other)
    assert run(lambda:bool(sent))['status']=='CANCELLED_OUTCOME_UNCERTAIN'
    assert len(sent)==1 and not reads


def test_exact_wrist_and_cartesian_scope_cannot_be_mixed(tmp_path):
    reservation,_,_,_,_,_=setup(tmp_path)
    with pytest.raises(ValueError):NativeDiscreteTransport(reservation)
    with pytest.raises(ValueError):run_reserved_transaction(reservation,transport=None,clock_ns=None,wait=None)
    assert isinstance(NativeCartesianTransport(reservation),NativeCartesianTransport)
    assert _CartesianCommandConnection._reservation_type is WifiCartesianReservation
    assert _CommandConnection._reservation_type is not WifiCartesianReservation


@pytest.mark.parametrize('change',['expired','wrong_mac','wrong_command'])
def test_reservation_binding_and_consumption_are_one_use(tmp_path,change):
    reservation,_,_,_,_,_=setup(tmp_path)
    command=reservation.command()
    if change=='wrong_command':command['z']+=1
    with pytest.raises(ValueError):
        reservation.consume(command,now_ns=12_000_000_000 if change=='expired' else 10_000_000_000,
                            observed_mac='wrong' if change=='wrong_mac' else MAC)
    with pytest.raises(ValueError):
        reservation.consume(reservation.command(),now_ns=10_000_000_000,observed_mac=MAC)


def test_receipt_without_feedback_is_not_success(tmp_path):
    reservation,*_=setup(tmp_path)
    tx=reservation.transaction
    tx.begin_dispatch(10_000_000_000)
    tx.acknowledge(10_050_000_000)
    assert tx.snapshot()['state']=='OBSERVING'
    assert tx.snapshot()['result'] is None
    tx.tick(11_050_000_000)
    assert tx.snapshot()['state']=='FEEDBACK_GAP_EXCEEDED'


def test_named_five_mm_diagnostic_keeps_exact_command_scope(tmp_path):
    _,_,_,_,_,baseline=setup(tmp_path)
    reservation=WifiCartesianReservation(root=tmp_path.resolve(),attempt_id='e'*32,
        baseline=baseline,now_ns=10_000_000_000,completion_budget_ns=3_000_000_000,step_mm=5)
    assert reservation.command()['z']==baseline['controller_cartesian']['values']['z']+5
    assert reservation.request()['configuration']['policy']['scope']=='LOCAL_Z_PLUS_5MM_ONLY'
    for value in (True,10,-5):
        with pytest.raises(ValueError):
            CartesianTransaction(baseline=baseline,baseline_finished_ns=10_000_000_000,
                                 completion_budget_ns=3_000_000_000,step_mm=value)


def test_reject_mismatched_baseline_before_durable_publish(tmp_path):
    _,_,_,_,_,baseline=setup(tmp_path)
    baseline['controller_cartesian']['values']['z']+=1
    with pytest.raises(ValueError):
        WifiCartesianReservation(root=tmp_path.resolve(),attempt_id='d'*32,
            baseline=baseline,now_ns=10_000_000_000,completion_budget_ns=3_000_000_000)
    assert not (tmp_path/('d'*32+'-wifi-reserved.json')).exists()


def test_native_cartesian_exact_bytes_and_one_use_latch(tmp_path,wire,monkeypatch):
    from rocell.providers.windows import wifi_discrete_native as native
    reservation,*_=setup(tmp_path)
    now,sent,sock,_=wire
    monkeypatch.setattr(native,'neighbor_mac',lambda:MAC)
    monkeypatch.setattr(native.time,'perf_counter_ns',lambda:10_000_000_000)
    payload=reservation.consume(reservation.command(),now_ns=10_000_000_000,observed_mac=MAC)
    connection=_CartesianCommandConnection(native.ADDRESS,clock=lambda:now[0])
    connection.dispatch(reservation,payload)
    assert len(sent)==1 and b'%22T%22%3A104' in sent[0]
    with pytest.raises(ValueError):connection.dispatch(reservation,payload)
    connection.close()
    assert sock.closed
    assert (tmp_path/('c'*32+'-wifi-native-send.json')).is_file()


def test_unconsumed_cartesian_reservation_never_opens_socket(tmp_path,wire,monkeypatch):
    from rocell.providers.windows import wifi_discrete_native as native
    reservation,*_=setup(tmp_path)
    now,sent,_,_=wire
    monkeypatch.setattr(native,'neighbor_mac',lambda:MAC)
    monkeypatch.setattr(native.time,'perf_counter_ns',lambda:10_000_000_000)
    connection=_CartesianCommandConnection(native.ADDRESS,clock=lambda:now[0])
    with pytest.raises(ValueError):connection.dispatch(reservation,b'{}')
    assert not sent


def test_native_entry_refuses_bad_baseline_before_transport(tmp_path,monkeypatch):
    from contextlib import nullcontext
    from rocell.providers.windows import wifi_cartesian_native as native
    monkeypatch.setattr(native,'arm_transport_lock',nullcontext)
    monkeypatch.setattr(native,'bounded_probe',lambda **kw:dict(status='FAILED'))
    def forbidden(*a,**kw):raise AssertionError('Transport must not be constructed')
    monkeypatch.setattr(native,'NativeCartesianTransport',forbidden)
    result=native.run_native_vertical_trial(root=tmp_path.resolve())
    assert result['status']=='HELD_BEFORE_DISPATCH'
    assert result['run'] is None
    assert not list(tmp_path.iterdir())


def test_elbow_diagnostic_uses_one_joint_command_and_same_observation_rules(tmp_path):
    reservation,run,sent,reads,_,baseline=setup(tmp_path,elbow_only=True)
    assert reservation.command()==dict(T=101,joint=3,rad=baseline['joints_rad']['e']-math.radians(2),spd=20,acc=1)
    assert reservation.request()['configuration']['speed']['acc']==1
    assert reservation.request()['configuration']['command_frame']=='CONTROLLER_JOINT'
    result=run()
    assert result['status']=='REPORTED_ENDPOINT_VERIFIED'
    assert len(sent)==1 and len(reads)>=3
    assert result['transaction']['policy']['scope']=='ELBOW_ONLY_MINUS_2_DEGREES'
    assert json.loads(sent[0])['joint']==3
    for row in result['transaction']['result']['joint_comparison']:
        assert row['commanded'] == (row['joint']=='e')
        if not row['commanded']:
            assert row['count_error'] is None and row['predicted_goal_count'] is None


@pytest.mark.parametrize('mode',['unchanged','lost_receipt','roll_drift'])
def test_elbow_fault_never_queues_other_joints_or_retry(tmp_path,mode):
    _,run,sent,_,_,_=setup(tmp_path,mode,elbow_only=True)
    result=run()
    assert result['status']!='REPORTED_ENDPOINT_VERIFIED'
    assert len(sent)==1
    assert set(json.loads(sent[0]))=={'T','joint','rad','spd','acc'}


def test_elbow_and_larger_cartesian_step_cannot_mix(tmp_path):
    _,_,_,_,_,baseline=setup(tmp_path)
    with pytest.raises(ValueError):
        CartesianTransaction(baseline=baseline,baseline_finished_ns=10_000_000_000,
            completion_budget_ns=3_000_000_000,step_mm=5,elbow_only=True)

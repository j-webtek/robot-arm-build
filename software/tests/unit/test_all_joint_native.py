from contextlib import contextmanager
from pathlib import Path
import json
import pytest
from rocell.geometry import UrdfModel
from rocell.kinematics.firmware_reference import forward
from rocell.providers.windows import all_joint_native as native
from rocell.providers.windows.arm_wifi_feedback import probe, MAC
from rocell.application.wizard_diagnostic_export import verify_export
from test_arm_wifi_feedback import Connection


def setup(monkeypatch,tmp_path,mode='normal'):
    now=[10.];locked=[False];sent=[]
    q=[.001533981,.033747577,1.744136156,-.065961174,.018407769,3.138524692]
    if mode=='descending_desired':q[2:4]=[1.762543925,-.046019424]
    if mode=='press_elbow':q[2:4]=[1.762543925,-.053689328]
    if mode=='nearby_elbow':q[2:4]=[1.779417714,-.053689328]
    if mode=='elbow_candidate':q[2:4]=[1.79168956,-.053689328]
    if mode=='reverse_elbow':q[2:4]=[1.807029368,-.053689328]
    def sample(joints):
        fields=dict(zip(('b','s','e','t','r','g'),joints))
        fields.update(zip(('x','y','z','tit'),forward(*joints[:4])))
        return probe(identity=lambda:MAC,clock=lambda:now[0],retain_response=True,
            connection_factory=lambda *a,**k:Connection(dict(T=1051,**fields)))
    @contextmanager
    def lock():
        assert not locked[0];locked[0]=True
        try:yield
        finally:locked[0]=False
    def baseline(**kwargs):
        assert locked[0]
        report=sample(q)
        if mode=='bad_baseline':report['identity_after_matched']=False
        return report
    class Transport:
        feedback_budget_ns=100_000_000
        def __init__(self,reservation):self.reservation=reservation;self.receipt=None
        def identity(self):return MAC
        def send_once(self,payload,**kwargs):
            assert locked[0]
            self.reservation.claim_native_send(payload,now_ns=round(now[0]*1e9),observed_mac=MAC)
            sent.append(json.loads(payload));self.receipt={'status':'SIMULATED_RECEIPT'}
            now[0]+=.05
            return True
        def feedback(self,**kwargs):
            assert locked[0];now[0]+=.1
            return sample(self.reservation.transaction.desired if mode in ('descending_desired','elbow_candidate')
                          else self.reservation.transaction.target)
    monkeypatch.setattr(native,'arm_transport_lock',lock)
    monkeypatch.setattr(native,'bounded_probe',baseline)
    monkeypatch.setattr(native,'NativeAllJointTransport',Transport)
    monkeypatch.setattr(native.time,'perf_counter_ns',lambda:round(now[0]*1e9))
    monkeypatch.setattr(native.time,'sleep',lambda s:now.__setitem__(0,now[0]+s))
    model=UrdfModel.from_file(Path(__file__).resolve().parents[3]/
        'software/models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf')
    reservations=tmp_path/'reservations';reservations.mkdir()
    def run(execute=False,experiment='paired-small-step'):
        return native.run_native_identification(reservation_root=reservations,
            export_root=tmp_path/'exports',model=model,execute=execute,experiment=experiment)
    return run,sent,locked


def test_default_preview_exports_without_send(monkeypatch,tmp_path):
    run,sent,locked=setup(monkeypatch,tmp_path)
    result=run()
    assert result['status']=='PREVIEW_ONLY_NOT_EXECUTABLE'
    assert not sent and not locked[0]
    assert verify_export(Path(result['export']['path']))['valid']


def test_native_composition_with_fake_io_and_real_export(monkeypatch,tmp_path):
    run,sent,locked=setup(monkeypatch,tmp_path)
    result=run(True)
    assert result['status']=='VERIFIED_AND_EXPORTED'
    assert len(sent)==1 and not locked[0]
    directory=Path(result['export']['path'])
    assert verify_export(directory)['valid']
    files=list(directory.glob('*all-joint-trial*'))
    assert len(files)==1
    exported=json.loads(files[0].read_text())
    assert exported['receipt']['status']=='SIMULATED_RECEIPT'
    assert exported['transaction']['state']=='REPORTED_SETTLED_PENDING_EXPORT'
    assert exported['diagnostic_assessment']['category']=='REPORTED_ENDPOINT_CRITERIA_MET'
    assert exported['diagnostic_assessment']['servo_target_acceptance']=='UNAVAILABLE'
    assert not exported['diagnostic_assessment']['progression_authority']
    assert len(exported['transaction']['rows'])>=3


def test_bad_baseline_exported_without_send(monkeypatch,tmp_path):
    run,sent,locked=setup(monkeypatch,tmp_path,'bad_baseline')
    result=run(True)
    assert result['status']=='HELD_BEFORE_DISPATCH'
    assert not sent and not locked[0]
    assert result['export']['verified']


def test_wrist_isolation_preserves_other_targets(monkeypatch,tmp_path):
    run,sent,_=setup(monkeypatch,tmp_path)
    result=run(True,'wrist-minus-006')
    assert result['status']=='VERIFIED_AND_EXPORTED'
    tx=result['transaction'];baseline=tx['baseline']['joints_rad']
    assert sent[0]['wrist']==pytest.approx(baseline['t']-.006)
    for field,key in [('base','b'),('shoulder','s'),('elbow','e'),('roll','r'),('hand','g')]:
        assert sent[0][field]==baseline[key]


def test_unknown_experiment_rejected_without_send(monkeypatch,tmp_path):
    run,sent,_=setup(monkeypatch,tmp_path)
    with pytest.raises(ValueError):run(True,'arbitrary')
    assert not sent


def test_t101_comparison_sends_only_fixed_wrist_target(monkeypatch,tmp_path):
    run,sent,_=setup(monkeypatch,tmp_path)
    result=run(True,'t101-wrist-fixed-comparison')
    assert result['status']=='VERIFIED_AND_EXPORTED'
    assert sent==[dict(T=101,joint=4,rad=-.071961174,spd=20,acc=1)]
    assert result['transaction']['desired_joints_rad'][2]==1.744136156


def test_fixed_wrist_response_probe(monkeypatch,tmp_path):
    run,sent,_=setup(monkeypatch,tmp_path)
    result=run(True,'t101-wrist-response-probe')
    assert result['status']=='VERIFIED_AND_EXPORTED'
    assert sent==[dict(T=101,joint=4,rad=-.080,spd=20,acc=1)]


def test_fixed_opposite_wrist_probe(monkeypatch,tmp_path):
    run,sent,_=setup(monkeypatch,tmp_path)
    result=run(True,'t101-wrist-opposite-probe')
    assert result['status']=='VERIFIED_AND_EXPORTED'
    assert sent==[dict(T=101,joint=4,rad=-.052,spd=20,acc=1)]


def test_descending_candidate_desired_endpoint_and_native_export(monkeypatch,tmp_path):
    run,sent,_=setup(monkeypatch,tmp_path,'descending_desired')
    result=run(True,'t101-descending-transfer')
    assert result['status']=='VERIFIED_AND_EXPORTED'
    assert sent[0]['rad']==pytest.approx(-.06913140077991495)
    assert result['transaction']['desired_joints_rad'][3]==-.055223308
    assert result['transaction']['rows'][-1]['desired_tip_error_mm']==0
    assert result['transaction']['rows'][-1]['wire_tip_error_mm']>.5


def test_descending_wrong_start_holds_without_send(monkeypatch,tmp_path):
    run,sent,_=setup(monkeypatch,tmp_path)
    result=run(True,'t101-descending-transfer')
    assert result['status']=='HELD_BEFORE_DISPATCH' and not sent


def test_press_elbow_sends_only_joint_three(monkeypatch,tmp_path):
    run,sent,_=setup(monkeypatch,tmp_path,'press_elbow')
    result=run(True,'t101-press-elbow-probe')
    assert result['status']=='VERIFIED_AND_EXPORTED'
    assert sent==[dict(T=101,joint=3,rad=1.7742992981223962,spd=20,acc=1)]
    assert not result['transaction']['compensation_applied']
    assert result['transaction']['identification_probe']['source_sha256']


def test_press_elbow_wrong_start_rejected(monkeypatch,tmp_path):
    run,sent,_=setup(monkeypatch,tmp_path)
    assert run(True,'t101-press-elbow-probe')['status']=='HELD_BEFORE_DISPATCH'
    assert not sent


def test_nearby_elbow_identification_does_not_apply_correction(monkeypatch,tmp_path):
    run,sent,_=setup(monkeypatch,tmp_path,'nearby_elbow')
    result=run(True,'t101-elbow-nearby-probe')
    assert result['status']=='VERIFIED_AND_EXPORTED'
    assert sent==[dict(T=101,joint=3,rad=1.785417714,spd=20,acc=1)]
    assert not result['transaction']['compensation_applied']


def test_local_elbow_candidate_verifies_desired_and_exports(monkeypatch,tmp_path):
    run,sent,_=setup(monkeypatch,tmp_path,'elbow_candidate')
    result=run(True,'t101-local-elbow-candidate')
    assert result['status']=='VERIFIED_AND_EXPORTED'
    assert sent==[dict(T=101,joint=3,rad=1.799994429061198,spd=20,acc=1)]
    assert result['transaction']['desired_joints_rad'][2]==1.80568956
    assert result['transaction']['rows'][-1]['desired_tip_error_mm']==0
    assert result['transaction']['rows'][-1]['wire_tip_error_mm']>.5
    assert verify_export(Path(result['export']['path']))['valid']


def test_local_elbow_candidate_wrong_start_never_sends(monkeypatch,tmp_path):
    run,sent,_=setup(monkeypatch,tmp_path)
    assert run(True,'t101-local-elbow-candidate')['status']=='HELD_BEFORE_DISPATCH'
    assert not sent


def test_reverse_elbow_has_no_forward_compensation(monkeypatch,tmp_path):
    run,sent,_=setup(monkeypatch,tmp_path,'reverse_elbow')
    result=run(True,'t101-elbow-reverse-probe')
    assert result['status']=='VERIFIED_AND_EXPORTED'
    assert sent==[dict(T=101,joint=3,rad=1.79168956,spd=20,acc=1)]
    assert not result['transaction']['compensation_applied']
    assert result['transaction']['identification_probe']['reverse_identification']


def test_reverse_wrong_start_no_send(monkeypatch,tmp_path):
    run,sent,_=setup(monkeypatch,tmp_path)
    assert run(True,'t101-elbow-reverse-probe')['status']=='HELD_BEFORE_DISPATCH'
    assert not sent


def test_reverse_speed_comparison_binds_only_speed_change(monkeypatch,tmp_path):
    run,sent,_=setup(monkeypatch,tmp_path,'reverse_elbow')
    result=run(True,'t101-elbow-reverse-speed40')
    assert result['status']=='VERIFIED_AND_EXPORTED'
    assert sent==[dict(T=101,joint=3,rad=1.79168956,spd=40,acc=1)]
    assert result['transaction']['identification_probe']['speed_comparison']
    assert not result['transaction']['compensation_applied']


def test_reverse_speed_wrong_start_rejected(monkeypatch,tmp_path):
    run,sent,_=setup(monkeypatch,tmp_path)
    assert run(True,'t101-elbow-reverse-speed40')['status']=='HELD_BEFORE_DISPATCH'
    assert not sent

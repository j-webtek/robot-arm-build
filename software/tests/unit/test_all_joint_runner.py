from pathlib import Path
import json
import pytest
from rocell.geometry import UrdfModel
from rocell.kinematics.firmware_reference import forward
from rocell.providers.windows.arm_wifi_feedback import probe, MAC
from rocell.safety.wifi_all_joint_reservation import WifiAllJointReservation
from rocell.application.all_joint_runner import run_all_joint
from test_arm_wifi_feedback import Connection


def setup(tmp_path, mode='normal'):
    now=[10.];sent=[];exports=[]
    start=[.001533981,.033747577,1.744136156,-.065961174,.018407769,3.138524692]
    target=list(start);target[2]+=.003;target[3]-=.003
    def feedback(q):
        fields=dict(zip(('b','s','e','t','r','g'),q))
        fields.update(zip(('x','y','z','tit'),forward(*q[:4])))
        return probe(identity=lambda:MAC,clock=lambda:now[0],retain_response=True,
            connection_factory=lambda *a,**k:Connection(dict(T=1051,**fields)))
    model=UrdfModel.from_file(Path(__file__).resolve().parents[3]/
        'software/models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf')
    reservation=WifiAllJointReservation(root=tmp_path.resolve(),attempt_id='a'*32,
        baseline=feedback(start),now_ns=10_000_000_000,model=model,
        overrides={'elbow':target[2],'wrist':target[3]})
    class Transport:
        feedback_budget_ns=800_000_000
        def identity(self):return 'wrong' if mode=='wrong_identity' else MAC
        def send_once(self,payload,**kwargs):
            reservation.claim_native_send(payload,now_ns=round(now[0]*1e9),observed_mac=MAC)
            sent.append(json.loads(payload));now[0]+=.30
            if mode=='lost_ack':raise TimeoutError('secret response')
            return True
        def feedback(self,**kwargs):
            now[0]+=.1
            result=feedback(start if mode=='unchanged' else target)
            if mode=='bad_hash':result['response_sha256']='wrong'
            return result
    def publish(report):
        exports.append(report)
        if mode=='export_error':raise OSError('private path')
        return {'verified':mode!='export_invalid','path':'test-only'}
    def run():
        return run_all_joint(reservation,transport=Transport(),clock_ns=lambda:round(now[0]*1e9),
            wait=lambda s:now.__setitem__(0,now[0]+s),publish_verified=publish,
            cancelled=lambda:mode=='cancel_before' or (mode=='cancel_after' and bool(sent)))
    return reservation,run,sent,exports


def test_real_reservation_latches_and_pending_export(tmp_path):
    reservation,run,sent,exports=setup(tmp_path)
    result=run()
    assert result['status']=='VERIFIED_AND_EXPORTED'
    assert len(sent)==1 and sent[0]['T']==102
    assert exports[0]['transaction']['state']=='REPORTED_SETTLED_PENDING_EXPORT'
    assert result['transaction']['progression_ready']
    assert (tmp_path/('a'*32+'-wifi-native-send.json')).exists()
    assert run()['status']=='ATTEMPT_ALREADY_USED'
    assert len(sent)==1


@pytest.mark.parametrize('mode,sends',[('wrong_identity',0),('cancel_before',0),
    ('cancel_after',1),('lost_ack',1),('bad_hash',1),('unchanged',1),
    ('export_error',1),('export_invalid',1)])
def test_faults_export_without_retry(tmp_path,mode,sends):
    _,run,sent,exports=setup(tmp_path,mode)
    result=run()
    assert result['status']=='FAULT'
    assert len(sent)==sends and len(exports)==1
    assert not result['transaction']['progression_ready']
    assert 'secret' not in json.dumps(result) and 'private' not in json.dumps(result)
    assert run()['status']=='ATTEMPT_ALREADY_USED'

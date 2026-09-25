import math
import json
import pytest
from rocell.providers.windows.arm_wifi_feedback import probe,MAC
from rocell.safety.wifi_dispatch_reservation import WifiDispatchReservation
from rocell.application.wifi_discrete_runner import run_reserved_transaction
from test_arm_wifi_feedback import Connection


def setup(tmp_path,mode='normal'):
    now=[10.];sent=[];reads=[]
    def feedback(value):
        return probe(identity=lambda:MAC,clock=lambda:now[0],retain_response=True,
            connection_factory=lambda *a,**k:Connection(dict(T=1051,b=0,s=0,e=1,t=0,r=value,g=3)))
    baseline=feedback(0)
    reservation=WifiDispatchReservation(root=tmp_path.resolve(),attempt_id='a'*32,
        baseline=baseline,target=math.radians(1),now_ns=round(now[0]*1e9),completion_budget_ns=5_000_000_000)
    class Transport:
        def identity(self):return MAC
        def send_once(self,payload,**kwargs):
            sent.append(payload);now[0]+=.05
            if mode=='lost_ack':raise TimeoutError('secret')
            return True
        def feedback(self,**kwargs):
            reads.append(kwargs['deadline_ns']);now[0]+=.15
            if mode=='reset':raise ConnectionResetError('secret')
            if mode=='late':now[0]+=1
            return feedback(math.radians(1))
    def run(cancelled=lambda:False):
        return run_reserved_transaction(reservation,transport=Transport(),
            clock_ns=lambda:round(now[0]*1e9),wait=lambda seconds:now.__setitem__(0,now[0]+seconds),
            cancelled=cancelled)
    return reservation,run,sent,reads,now,baseline


def test_complete_one_command_and_durable_consumption(tmp_path):
    reservation,run,sent,reads,now,baseline=setup(tmp_path)
    result=run()
    assert result['status']=='REPORTED_ENDPOINT_VERIFIED'
    assert len(sent)==1 and len(reads)>=3
    assert (tmp_path/('a'*32+'-wifi-consumed.json')).is_file()
    assert run()['status']=='ATTEMPT_ALREADY_USED'
    assert len(sent)==1
    with pytest.raises(Exception):
        WifiDispatchReservation(root=tmp_path.resolve(),attempt_id='a'*32,baseline=baseline,
            target=math.radians(1),now_ns=10_000_000_000,completion_budget_ns=5_000_000_000)


@pytest.mark.parametrize('mode',['lost_ack','reset','late'])
def test_faults_never_retry(tmp_path,mode):
    reservation,run,sent,reads,now,baseline=setup(tmp_path,mode)
    result=run()
    assert not result['transaction']['result'] or not result['transaction']['result']['endpoint_verified']
    assert len(sent)==1 and 'secret' not in json.dumps(result)
    assert result['status'] in ('COMMAND_OUTCOME_UNCERTAIN','FEEDBACK_GAP_EXCEEDED')
    if mode=='lost_ack':assert not reads


def test_cancellation_before_dispatch_has_no_writes(tmp_path):
    _,run,sent,reads,_,_=setup(tmp_path)
    result=run(lambda:True)
    assert result['status']=='CANCELLED_BEFORE_DISPATCH' and not sent and not reads


@pytest.mark.parametrize('mode',['expired','wrong_command','wrong_mac'])
def test_admission_binding_failure_burns_object(tmp_path,mode):
    reservation,_,_,_,_,_=setup(tmp_path)
    command=reservation.command()
    if mode=='wrong_command':command['spd']=99
    with pytest.raises(ValueError):
        reservation.consume(command,now_ns=12_000_000_000 if mode=='expired' else 10_000_000_000,
            observed_mac='unknown' if mode=='wrong_mac' else MAC)
    with pytest.raises(ValueError):
        reservation.consume(reservation.command(),now_ns=10_000_000_000,observed_mac=MAC)

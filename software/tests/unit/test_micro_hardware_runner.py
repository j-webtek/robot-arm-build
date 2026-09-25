import pytest
from test_micro_command_admission import setup
from test_micro_transaction_simulation import sample
from rocell.application.micro_hardware_runner import run_micro_transaction
from rocell.providers.windows.arm_wifi_feedback import ADDRESS,MAC


def exercise(tmp_path,monkeypatch,mode='ok'):
    admission=setup(tmp_path,monkeypatch);clock=[1.4];sends=[];holds=[];exports=[]
    class Transport:
        receipt=None
        def identity(self):return MAC
        def send_once(self,payload,*,deadline_ns,cancelled):
            sends.append(payload);clock[0]+=.05
            self.receipt=dict(status='HTTP_RECEIPT_ONLY')
            if mode=='send':raise TimeoutError()
            return True
        def feedback(self,*,deadline_ns,cancelled):
            clock[0]+=.1 if mode!='late' else 1.1
            result=sample(clock[0]);result.update(address=ADDRESS,expected_mac=MAC,
                identity_before_matched=True,identity_after_matched=True,cleanup_confirmed=True)
            if mode=='corrupt':result['response_sha256']='0'*64
            return result
    def hold(**kwargs):
        holds.append(1);start=clock[0]+.2
        points=[sample(start+i*.5) for i in range(69)];clock[0]=start+34
        return dict(status='FAILED' if mode=='hold' else 'SUCCEEDED',
                    schema='rocell.arm_wifi_observation.v4',samples=points)
    def export(report):
        if mode=='export':raise OSError()
        exports.append(report)
    def run():
        return run_micro_transaction(admission,transport=Transport(),clock_ns=lambda:round(clock[0]*1e9),
            wait=lambda s:clock.__setitem__(0,clock[0]+s),observe_hold=hold,export=export,
            cancelled=lambda:mode=='cancel')
    return run,sends,holds,exports


def test_polling_completes_and_reuse_cannot_send(tmp_path,monkeypatch):
    run,sends,holds,exports=exercise(tmp_path,monkeypatch)
    result=run()
    assert result['status']=='EXPERIMENT_VERIFIED',result
    assert len(sends)==len(holds)==len(exports)==1
    assert len(result['feedback_originals'])>=8
    assert run()['status']=='STOPPED' and len(sends)==1


@pytest.mark.parametrize('mode',['send','late','corrupt','hold','export','cancel'])
def test_faults_no_retry_and_no_early_hold(tmp_path,monkeypatch,mode):
    run,sends,holds,exports=exercise(tmp_path,monkeypatch,mode)
    result=run()
    assert result['status']=='STOPPED' and len(sends)<=1
    if mode in ('send','late','corrupt','cancel'):assert not holds
    assert result['export_succeeded']==(mode!='export')

"""Pure simulated runner checks: never opens a hardware transport."""
import json
import pytest
from test_wifi_cartesian import setup
from test_coordinated_wrist_probe import posture
from rocell.arm.cartesian_transaction import CartesianTransaction
from rocell.application.compensated_elbow_progression import clean_compensated_completion


@pytest.mark.parametrize('candidate',[True,'extended-start'])
def test_clean_wrist_arrival_retains_wire_miss(tmp_path,candidate):
    reservation,run,sent,reads,_,_=setup(tmp_path,'desired_candidate',
        compensated_endpoint=True,wrist_candidate=candidate)
    result=run()
    assert clean_compensated_completion(result)
    tx=result['transaction']
    assert tx['state']=='COMPENSATED_REPORTED_ENDPOINT_VERIFIED'
    assert not tx['result']['endpoint_verified']
    assert tx['desired_endpoint_result']['wrist_error_deg']==pytest.approx(0,abs=1e-8)
    assert tx['local_candidate']['desired_joint_index']==3
    assert json.loads(sent[0])['joint']==4
    assert len(sent)==1 and 3<=len(reads)<10
    assert run()['status']=='ATTEMPT_ALREADY_USED'


@pytest.mark.parametrize('mode',[
    'lost_receipt','reset','late','roll_drift','incoherent','missing_xyz',
    'unchanged','deadline_timeout'])
def test_clean_wrist_faults_cannot_progress(tmp_path,mode):
    _,run,sent,_,_,_=setup(tmp_path,mode,compensated_endpoint=True,
                          wrist_candidate='extended-start')
    result=run()
    assert not clean_compensated_completion(result)
    assert result['status']!='COMPENSATED_REPORTED_ENDPOINT_VERIFIED'
    assert len(sent)==1


@pytest.mark.parametrize('after_send',[False,True])
def test_clean_wrist_cancellation(tmp_path,after_send):
    _,run,sent,reads,_,_=setup(tmp_path,'desired_candidate',
        compensated_endpoint=True,wrist_candidate=True)
    result=run(lambda: bool(sent) if after_send else True)
    assert not clean_compensated_completion(result)
    assert len(sent)==int(after_send) and not reads


def test_plain_wrist_probe_cannot_enable_compensated_completion():
    with pytest.raises(ValueError,match='qualified local candidate'):
        CartesianTransaction(baseline=posture(),baseline_finished_ns=1,
            completion_budget_ns=3_000_000_000,wrist_probe=True,compensated_endpoint=True)

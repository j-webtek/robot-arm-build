from copy import deepcopy
import pytest
from test_wifi_cartesian import setup
from rocell.application.compensated_elbow_progression import clean_compensated_completion


@pytest.mark.parametrize('mode',[3,-6])
def test_clean_desired_arrival_stops_before_timeout(tmp_path,mode):
    reservation,run,sent,_,now,_=setup(tmp_path,mode='desired_candidate',elbow_only=True,elbow_degrees=mode,compensated_endpoint=True)
    result=run()
    assert clean_compensated_completion(result)
    assert now[0]<13 and result['error'] is None
    assert not result['transaction']['result']['endpoint_verified']
    assert reservation.request()['configuration']['compensated_candidate']==result['transaction']['local_candidate']
    assert len(sent)==1 and run()['status']=='ATTEMPT_ALREADY_USED'
    for field,value in [('error','TRANSACTION_INTERRUPTED_OR_UNCERTAIN'),('status','COMPLETION_DEADLINE_EXCEEDED'),('acknowledgment_received',False)]:
        bad=deepcopy(result); bad[field]=value
        assert not clean_compensated_completion(bad)
    bad=deepcopy(result); bad['feedback_originals'][-1]['cleanup_confirmed']=False
    assert not clean_compensated_completion(bad)


@pytest.mark.parametrize('fault',['lost_receipt','reset','late','roll_drift','incoherent','missing_xyz','unchanged','deadline_timeout','normal'])
def test_fault_or_wire_only_arrival_does_not_advance(tmp_path,fault):
    _,run,sent,_,_,_=setup(tmp_path,mode=fault,elbow_only=True,elbow_degrees=3,compensated_endpoint=True)
    assert not clean_compensated_completion(run())
    assert len(sent)==1


def test_cancel_does_not_advance(tmp_path):
    _,run,sent,_,_,_=setup(tmp_path,mode='desired_candidate',elbow_only=True,elbow_degrees=3,compensated_endpoint=True)
    assert not clean_compensated_completion(run(lambda:bool(sent)))


@pytest.mark.parametrize('mode',[2,5,-3,1,-1,-4,-5])
def test_unqualified_modes_rejected(tmp_path,mode):
    with pytest.raises(ValueError): setup(tmp_path,elbow_only=True,elbow_degrees=mode,compensated_endpoint=True)

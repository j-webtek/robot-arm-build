from pathlib import Path
import math
import pytest
from rocell.geometry import UrdfModel
from rocell.application.repeated_wrist_pair import pair_candidate,run_two_pairs


def test_interval_keeps_targets_and_correction_fixed():
    model=UrdfModel.from_file(Path(__file__).resolve().parents[3]/
        'software/models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf')
    start=[.001533981,.033747577,1.762543925,-.056757289,.018407769,3.138524692]
    candidate=pair_candidate(model,start,'up')
    assert candidate['desired_joints_rad'][3]==-.045
    assert candidate['command']['rad']==pytest.approx(-.045+2*math.pi/4096)
    assert not candidate['correction_refitted']
    start[3]-=.001
    with pytest.raises(ValueError):pair_candidate(model,start,'up')


@pytest.mark.parametrize('failed_at',range(4))
def test_failure_never_sends_remaining_legs(failed_at):
    calls=[]
    def leg(direction):
        calls.append(direction)
        return dict(status='FAULT' if len(calls)-1==failed_at else 'VERIFIED_AND_EXPORTED')
    result=run_two_pairs(run_leg=leg,verify_leg=lambda *args:True)
    assert result['status']=='STOPPED_ON_LEG_FAILURE'
    assert len(calls)==failed_at+1


def test_export_failure_prevents_return():
    calls=[]
    def leg(direction):calls.append(direction);return dict(status='VERIFIED_AND_EXPORTED')
    result=run_two_pairs(run_leg=leg,verify_leg=lambda *args:False)
    assert calls==['up'] and result['status']=='STOPPED_ON_EXPORT_REVIEW'


def test_two_pairs_only():
    calls=[]
    def leg(direction):calls.append(direction);return dict(status='VERIFIED_AND_EXPORTED')
    assert run_two_pairs(run_leg=leg,verify_leg=lambda *args:True)['status']=='TWO_REPORTED_PAIRS_VERIFIED'
    assert calls==['up','down','up','down']

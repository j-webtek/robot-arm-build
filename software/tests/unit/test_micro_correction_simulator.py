import pytest
from rocell.arm.micro_correction_simulator import Observation, simulate, settled, scenarios

INITIAL=(0,0,0,0,1.40625,0)


def test_scenarios_have_expected_terminal_results():
    expected=dict(ideal_progress='IN_BAND',quantized_progress='IN_BAND',
        unchanged='NO_USEFUL_PROGRESS',overshoot='OVERSHOOT_NO_REVERSAL',
        delayed='FEEDBACK_DEADLINE',uncertain='FEEDBACK_FAILED_OR_MISSING',
        other_joint_drift='OTHER_JOINT_DRIFT',slow_progress='ATTEMPT_LIMIT',
        late_failure='FEEDBACK_FAILED_OR_MISSING')
    for name, result in scenarios().items():
        assert result['reason']==expected[name]
        assert len(result['attempts'])<=3
        assert result['commanded_travel_deg']<=.30+1e-12
        assert not result['motion_authorized'] and not result['hardware_response_validated']


def test_no_attempt_when_already_in_band():
    result=simulate((0,0,0,0,1.23,0), [])
    assert result['reason']=='IN_BAND' and result['attempts']==[]


@pytest.mark.parametrize('trace,reason', [
    ([], 'SETTLING_UNVERIFIED'),
    ([Observation(.1, INITIAL)]*3, 'NON_MONOTONIC_FEEDBACK'),
    (settled(1.0), 'ROLL_EXCURSION'),
    ([Observation(float('nan'), INITIAL)], 'INVALID_FEEDBACK'),
    ([Observation(.1, (0,0,0,0,True,0))], 'INVALID_FEEDBACK'),
    ([Observation(.1, INITIAL),Observation(.2,(0,0,0,0,1.3,0)),
      Observation(.3,(0,0,0,0,1.25,0))], 'SETTLING_UNVERIFIED')])
def test_faults_stop_before_any_next_attempt(trace,reason):
    result=simulate(INITIAL,[trace,settled(1.25)])
    assert result['reason']==reason and len(result['attempts'])==1


def test_late_other_joint_drift_not_hidden_by_early_arrival():
    trace=settled(1.25)+[Observation(.4,(.11,0,0,0,1.25,0))]
    assert simulate(INITIAL,[trace])['reason']=='OTHER_JOINT_DRIFT'


def test_initial_envelope_rejected():
    with pytest.raises(ValueError):simulate((0,0,0,0,4,0), [])

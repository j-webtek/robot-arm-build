import math
import pytest
from rocell.arm.feedback_correction_simulation import simulate,scenarios,window


def test_finite_scenarios():
    for case in scenarios():
        assert case['passed'],case
        r=case['result']
        assert not r['hardware_access'] and not r['motion_authorized']
        assert r['native_commands_sent']==0 and r['simulated_corrections']<=3


def test_actual_command_policy_blocks_small_residual():
    r=simulate([window([1.40625]*71)])
    assert r['status']=='CURRENT_POLICY_REJECTS_CORRECTION'
    e=r['events'][0]
    assert e['proposed_command_deg']==pytest.approx(1.34375)
    assert not e['current_transaction_policy_admissible']
    assert r['simulated_corrections']==0


@pytest.mark.parametrize('v',[True,float('nan'),float('inf'),4])
def test_invalid_feedback(v):
    assert simulate([window([v]*71)])['status']=='INVALID_OR_STALE_FEEDBACK'


def test_stale_and_iteration_and_saturation_limits():
    w=window([1.4]*71);w['sample_interval_s']=1.1
    assert simulate([w])['status']=='INVALID_OR_STALE_FEEDBACK'
    assert simulate([window([1.4]*71)],max_corrections=0)['status']=='CORRECTION_BUDGET_EXHAUSTED'
    assert simulate([window([2.5]*71)],desired_deg=3,initial_command_deg=2.99,
        enforce_current_policy=False)['status']=='COMMAND_LIMIT'


@pytest.mark.parametrize('kwargs',[dict(tolerance_deg=0),dict(tolerance_deg=True),
    dict(max_corrections=4),dict(initial_command_deg=math.inf)])
def test_invalid_settings(kwargs):
    with pytest.raises(ValueError):simulate([],**kwargs)

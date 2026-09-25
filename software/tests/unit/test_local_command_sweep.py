import math
import pytest
from rocell.arm.local_command_sweep import preflight,summarize_response,COMMANDS_DEG


def test_historical_high_supports_small_command_spacing_without_policy_change():
    r=preflight([0,0,1,0,.0398835,3])
    assert r['all_compatible'] and len(r['probes'])==6
    assert r['native_sweep_action_available'] and not r['motion_authorized']
    assert all(.5<abs(p['command_delta_from_baseline_deg'])<=1.5 for p in r['probes'])


@pytest.mark.parametrize('roll',[1.23,2.6,0])
def test_other_starts_not_blanket_approved(roll):
    assert not preflight([0,0,1,0,math.radians(roll),3])['all_compatible']


def records(values):
    return [dict(export_id=str(i),command_deg=c,endpoint_and_hold_verified=True,hold_final_deg=v)
        for i,(c,v) in enumerate(zip(COMMANDS_DEG,values))]


def test_variable_response_summary_does_not_fit_or_claim_deadband():
    r=summarize_response(records([1.1,1.23,1.32,1.4,1.406,1.25]))
    assert r['complete'] and all(v['observed_endpoint_ranges_overlap'] for v in r['adjacent_comparisons'])
    assert not r['model_fitted']


def test_failure_and_incomplete_never_qualify():
    v=records([1]*6);v[2]['endpoint_and_hold_verified']=False
    r=summarize_response(v)
    assert not r['complete'] and r['failed_probe_indices']==[2] and not r['adjacent_comparisons']
    assert not summarize_response(v[:2])['complete']


def test_duplicate_reordered_and_nonfinite_rejected():
    v=records([1]*6);v[1]['export_id']='0'
    with pytest.raises(ValueError):summarize_response(v)
    v=records([1]*6);v[0]['command_deg']=1.05
    with pytest.raises(ValueError):summarize_response(v)
    with pytest.raises(ValueError):summarize_response(records([float('nan')]*6))
    with pytest.raises(ValueError):preflight([0])

import importlib.util
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('response_analysis',Path(__file__).resolve().parents[3]/'software/scripts/analyze_coordinated_response.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


def records():
    return [dict(source=str(i),elbow=dict(requested_delta_deg=x,reported_delta_deg=2*x+.1),
        wrist_pitch=dict(requested_delta_deg=-x,reported_delta_deg=-3*x+.2))
        for i,x in enumerate((1.,2.,1.5,2.5))]


def test_chronological_fit_does_not_use_held_out_values():
    rows=records();initial=module.compare_response(rows)
    assert initial[0]['slope']==pytest.approx(2)
    assert initial[0]['affine_max_error_deg']==pytest.approx(0)
    assert initial[0]['held_out'][0]['inside_training_command_range']
    assert not initial[0]['held_out'][1]['inside_training_command_range']
    rows[-1]['elbow']['reported_delta_deg']+=10
    changed=module.compare_response(rows)
    assert changed[0]['slope']==initial[0]['slope']
    assert changed[0]['intercept_deg']==initial[0]['intercept_deg']
    assert changed[0]['affine_max_error_deg']==pytest.approx(10)


@pytest.mark.parametrize('fault',['count','separation','nan'])
def test_invalid_evidence_rejected(fault):
    rows=records()
    if fault=='count':rows.pop()
    if fault=='separation':rows[1]['elbow']['requested_delta_deg']=rows[0]['elbow']['requested_delta_deg']
    if fault=='nan':rows[3]['wrist_pitch']['reported_delta_deg']=float('nan')
    with pytest.raises(ValueError):module.compare_response(rows)

from copy import deepcopy
import pytest

from rocell.application.base_compensation_comparison import compare_base_compensation_pair
from rocell.application.positional_campaign_native_export import verify_native_retained_export
from test_base_compensation_campaign import experiment_body
from test_model_corrected_native_campaign import install
from test_positional_campaign_native_export import bundle


def paired(tmp_path,monkeypatch,*,control_start=None,direction='INCREASING'):
    install(monkeypatch)
    selections=[]
    for index,kind in enumerate(('CORRECTED','UNCORRECTED_CONTROL')):
        root=tmp_path/str(index);root.mkdir()
        b=experiment_body(kind,direction);b['campaign_id']='campaign-'+str(index+1)*32
        if index and control_start is not None:
            import hashlib
            from rocell.application.first_motion_contract import canonical
            b['start_joints_rad'][0]=b['legs'][0]['expected_start_rad']=control_start
            b['base_experiment']['expected_start_joints_rad']=list(b['start_joints_rad'])
            b['references']['configuration_sha256']=hashlib.sha256(canonical(b['base_experiment'])).hexdigest()
        monkeypatch.setattr('test_positional_current_context.body',lambda b=b:deepcopy(b))
        monkeypatch.setattr('test_positional_campaign_native_protocol.body',lambda b=b:deepcopy(b))
        path,name,_=bundle(root,monkeypatch,response_target_rad=b['legs'][0]['target_rad'] if index==0 else b['start_joints_rad'][0])
        verified=verify_native_retained_export(path,name)
        selections.append(dict(directory=path,report_name=name,report_sha256=verified['report_sha256']))
    return dict(corrected=selections[0],control=selections[1])


def test_pair_rebuilt_from_native_originals(tmp_path,monkeypatch):
    args=paired(tmp_path,monkeypatch)
    result=compare_base_compensation_pair(**args)
    assert result['local_pair_supports_candidate']
    assert result['relative_error_reduction_percent']==pytest.approx(100)
    assert result['control']['status']=='NO_RESPONSE'
    assert not result['physical_accuracy_verified'] and not result['repeated_validation_complete']


def test_decreasing_pair_requires_explicit_matching_direction(tmp_path,monkeypatch):
    args=paired(tmp_path,monkeypatch,direction='DECREASING')
    result=compare_base_compensation_pair(**args,direction='DECREASING')
    assert result['local_pair_supports_candidate']
    with pytest.raises(ValueError):compare_base_compensation_pair(**args)


@pytest.mark.parametrize('fault',['hash','swap','duplicate','start'])
def test_pair_cannot_hide_mismatch(tmp_path,monkeypatch,fault):
    args=paired(tmp_path,monkeypatch,control_start=.006135923 if fault=='start' else None)
    if fault=='hash':args['control']['report_sha256']='e'*64
    if fault=='swap':args['corrected'],args['control']=args['control'],args['corrected']
    if fault=='duplicate':args['control']=args['corrected']
    with pytest.raises(ValueError):compare_base_compensation_pair(**args)

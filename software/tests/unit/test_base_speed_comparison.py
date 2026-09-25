"""Comparison input is retained raw evidence, not caller-provided scores."""
from copy import deepcopy
import hashlib
import math
import pytest

from rocell.application.base_speed_comparison import compare_base_speeds
from rocell.application.base_endpoint_dataset import build_base_dataset
from rocell.application.first_motion_contract import canonical
from rocell.application.positional_campaign_native_export import verify_native_retained_export
from test_base_speed_campaign import speed_body
from test_base_compensation_campaign import experiment_body
from test_model_corrected_native_campaign import install
from test_positional_campaign_native_export import bundle


def pair(tmp_path,monkeypatch,direction='INCREASING',fault=None):
    install(monkeypatch)
    selections=[]
    for index in (0,1):
        root=tmp_path/str(index);root.mkdir()
        b=speed_body(direction) if index==0 else experiment_body(direction=direction)
        b['campaign_id']='campaign-'+str(index+1)*32
        if index==1 and fault in ('start','context'):
            if fault=='start':
                b['start_joints_rad'][3]+=.001
                b['base_experiment']['expected_start_joints_rad']=list(b['start_joints_rad'])
            else:
                b['references']['workcell_sha256']='e'*64
                b['base_experiment']['context_references']['workcell_sha256']='e'*64
            b['references']['configuration_sha256']=hashlib.sha256(canonical(b['base_experiment'])).hexdigest()
        monkeypatch.setattr('test_positional_current_context.body',lambda b=b:deepcopy(b))
        monkeypatch.setattr('test_positional_campaign_native_protocol.body',lambda b=b:deepcopy(b))
        path,name,_=bundle(root,monkeypatch,response_target_rad=b['legs'][0]['target_rad']+math.radians(.35 if index==0 else .05))
        v=verify_native_retained_export(path,name)
        selections.append(dict(directory=path,report_name=name,report_sha256=v['report_sha256']))
    return dict(candidate=selections[0],reference=selections[1],direction=direction)


@pytest.mark.parametrize('direction',['INCREASING','DECREASING'])
def test_real_original_pair_retains_worse_candidate_and_blocks_training(tmp_path,monkeypatch,direction):
    args=pair(tmp_path,monkeypatch,direction)
    result=compare_base_speeds(**args)
    assert not result['candidate_improved_reported_endpoint']
    assert result['absolute_error_reduction_rad']==pytest.approx(math.radians(-.3))
    assert not result['speed_specific_model_validated']
    assert result['candidate']['status'] in ('TARGET_MISSED','NO_RESPONSE')
    with pytest.raises(ValueError):build_base_dataset([args['candidate']])


@pytest.mark.parametrize('fault',['hash','swap','duplicate','start','context','direction'])
def test_mismatched_evidence_rejected(tmp_path,monkeypatch,fault):
    args=pair(tmp_path,monkeypatch,fault=fault)
    if fault=='hash':args['candidate']['report_sha256']='f'*64
    if fault=='swap':args['candidate'],args['reference']=args['reference'],args['candidate']
    if fault=='duplicate':args['reference']=args['candidate']
    if fault=='direction':args['direction']='DECREASING'
    with pytest.raises(ValueError):compare_base_speeds(**args)

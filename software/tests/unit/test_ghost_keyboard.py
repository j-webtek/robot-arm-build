import json
from pathlib import Path
import pytest
from rocell.application import ghost_keyboard as ghost
from rocell.application.wizard_worker import run
from test_arrival_wizard_service import make_service, _run
from test_movement_campaign_ui import render

ROOT=Path(__file__).resolve().parents[3]


@pytest.mark.parametrize('text',['a','aba','abc','cba','aaaaaaaa'])
def test_nominal_route_preserves_repetitions_and_retracts(text):
    r=ghost.rehearse_ghost_keyboard(ROOT,text)
    assert r['status']=='SAMPLED_GHOST_ROUTE_PASS'
    assert r['requested_keys']==list(text.upper())
    assert len(r['legs'])==len(text)*4
    for i,leg in enumerate(r['legs']):
        assert leg['phase']==('travel','hover','virtual_downstroke','retract')[i%4]
        assert all(s['accepted'] for s in leg['samples'])
        if leg['phase']=='travel':
            assert leg['start'][2]==leg['target'][2]==230
        if i: assert leg['start']==r['legs'][i-1]['target']
    assert r['legs'][-1]['target'][2]==230
    assert not r['camera_required'] and not r['hardware_access']
    assert not r['motion_authorized'] and not r['full_arm_clearance_verified']
    assert r['report_sha256']==ghost.rehearse_ghost_keyboard(ROOT,text)['report_sha256']


def test_transform_is_explicit_and_not_board_registration():
    r=ghost.rehearse_ghost_keyboard(ROOT,'b')
    assert r['legs'][0]['target']==[340,19,230,0]
    assert r['layout']['transform_basis']=='NOMINAL_SIMULATION_ONLY'
    assert not r['layout']['installed_tool_offset_applied']


@pytest.mark.parametrize('text',['','abcdef','A','a'*9,None])
def test_invalid_sequences_rejected(text):
    with pytest.raises(ValueError): ghost.rehearse_ghost_keyboard(ROOT,text)


def test_ik_failure_stops_preview(monkeypatch):
    def fail(*args): raise ValueError('unreachable')
    monkeypatch.setattr(ghost,'inverse',fail)
    r=ghost.rehearse_ghost_keyboard(ROOT,'abc')
    assert r['status']=='GHOST_ROUTE_REJECTED'
    assert len(r['legs'])==1 and len(r['legs'][0]['samples'])==1
    assert r['first_failure']['reason']=='IK_DOMAIN'


def test_unreviewed_layout_change_rejected(tmp_path):
    p=tmp_path/'software/config/ghost_keyboard_v1.json'
    p.parent.mkdir(parents=True)
    d=json.loads((ROOT/'software/config/ghost_keyboard_v1.json').read_bytes())
    d['origin_controller_mm'][2]=0
    p.write_text(json.dumps(d))
    with pytest.raises(ValueError): ghost.rehearse_ghost_keyboard(tmp_path)


@pytest.mark.parametrize('mode',['physical','rehearsal'])
def test_wizard_and_export_are_camera_free(make_service,mode):
    service,runner,_=make_service(mode=mode)
    runner.run=lambda action,values,**kw:run(ROOT,action,values,kw['cell_id'])
    op=_run(service,'rehearse_ghost_keyboard',{'text':'aba'})
    assert op['status']=='SUCCEEDED'
    assert op['result']['device_open_count']==0
    assert op['result']['motion_command_count']==0
    assert 'SAMPLED_GHOST_ROUTE_PASS' in render(op)
    export=_run(service,'export_logs')
    assert export['status']=='SUCCEEDED'
    path=Path(export['result']['receipt']['path'])/f"attachment-result-{op['operation_id'].removeprefix('operation-')}.json"
    assert json.loads(path.read_bytes())==op['result']

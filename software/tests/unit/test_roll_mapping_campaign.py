"""Roll-only native-shaped execution; all serial access is an incapable fixture."""
import math
import hashlib
import pytest
from rocell.application.first_motion_contract import canonical
from rocell.safety.positional_campaign_authority import (
    ROLL_PROBE_SCHEMA, PositionalCampaignIntent, fixed_campaign_limits,
    roll_probe_configuration, require_correction_start, verify_campaign_endpoint,
)
from rocell.application.positional_campaign_native_export import verify_native_retained_export
from test_base_mapping_campaign import base_body
from test_model_corrected_native_campaign import install
from test_positional_campaign_native_capture import exercise
from test_positional_campaign_native_export import bundle


def roll_body(direction=1):
    b=base_body()
    start=[.007669904,0,1.593806039,.047553404,-.001533981,3.149262558]
    config=roll_probe_configuration('INCREASING' if direction==1 else 'DECREASING')
    target=start[4]+math.radians(direction)
    b.update(schema=ROLL_PROBE_SCHEMA,mode='ATTENDED_ONE_ROLL_PROBE',selected_joint='r',
        start_joints_rad=start,roll_probe=config,limits=fixed_campaign_limits(ROLL_PROBE_SCHEMA),
        legs=[dict(leg_id='leg-01',expected_start_rad=start[4],target_rad=target,
            command=dict(T=101,joint=5,rad=target,spd=20,acc=1))])
    b['references']['configuration_sha256']=hashlib.sha256(canonical(config)).hexdigest()
    return b


@pytest.mark.parametrize('direction',[-1,1])
def test_roll_original_export_checks_r_not_base_or_pitch(tmp_path,monkeypatch,direction):
    install(monkeypatch)
    monkeypatch.setattr('test_positional_current_context.body',lambda:roll_body(direction))
    path,name,_=bundle(tmp_path,monkeypatch,initial_prefix=b'}\n')
    v=verify_native_retained_export(path,name)
    assert v['valid'] and v['reconstruction_consistent'] and v['endpoint_completion_consistent']
    row=v['endpoint_diagnostics'][0]
    assert row['selected_joint']=='r' and row['command']['joint']==5
    assert row['final_rad']==roll_body(direction)['legs'][0]['target_rad']


@pytest.mark.parametrize('direction',[-1,1])
@pytest.mark.parametrize('fault',['malformed','late','other_joint','short_write','write_error','cancel','miss'])
def test_roll_faults_do_not_retry_or_return(tmp_path,monkeypatch,direction,fault):
    install(monkeypatch)
    monkeypatch.setattr('test_positional_current_context.body',lambda:roll_body(direction))
    kernel,_,_,_,r=exercise(tmp_path,monkeypatch,failure=None if fault in ('cancel','miss') else fault,
        cancel_after_write=fault=='cancel',missed_leg=1 if fault=='miss' else None)
    assert len(kernel.writes)==1 and r['status']!='REPORTED_CAMPAIGN_COMPLETE'
    assert r['cleanup']['all_handles_closed'] and not r['cleanup']['pending_io_count']


@pytest.mark.parametrize('axis',[0,1,2,3,5])
def test_every_nonroll_joint_is_monitored(axis):
    b=roll_body();start=b['start_joints_rad'];leg=b['legs'][0]
    final=list(start);final[4]=leg['target_rad'];final[axis]+=.02
    rows=[(1+i*20_000_000,1+(i+1)*20_000_000,final) for i in range(250)]
    r=verify_campaign_endpoint(b,leg,rows,start=start,capture_issues=(),transport_clean=True)
    assert not r['endpoint_verified'] and r['other_joint_changed']


@pytest.mark.parametrize('fault',['axis','wire','extra','speed','offset','domain','config','pose'])
def test_roll_profile_cannot_be_widened(fault):
    b=roll_body();leg=b['legs'][0]
    if fault=='axis':b['selected_joint']='b'
    if fault=='wire':leg['command']['joint']=4
    if fault=='extra':b['legs']*=2
    if fault=='speed':leg['command']['spd']=0
    if fault=='offset':leg['command']['rad']+=.001
    if fault=='domain':leg['target_rad']=leg['command']['rad']=.1
    if fault=='config':b['roll_probe']['compensation_applied']=True
    if fault=='pose':b['start_joints_rad'][1]=.1
    with pytest.raises(ValueError):PositionalCampaignIntent(canonical(b))


def test_fresh_six_joint_pose_required():
    b=roll_body()
    for i in range(6):
        s=list(b['start_joints_rad']);s[i]+=.001
        with pytest.raises(ValueError):require_correction_start(b,s)


@pytest.mark.parametrize('direction',[-1,1])
@pytest.mark.parametrize('response',['opposite','excursion'])
def test_wrong_direction_or_excursion_cannot_complete(tmp_path,monkeypatch,direction,response):
    install(monkeypatch)
    b=roll_body(direction)
    monkeypatch.setattr('test_positional_current_context.body',lambda:b)
    target=b['start_joints_rad'][4]-math.radians(direction) if response=='opposite' else .3
    kernel,_,_,_,r=exercise(tmp_path,monkeypatch,response_target_rad=target)
    assert len(kernel.writes)==1 and r['status']=='HELD'


def test_cli_exposes_only_named_roll_directions():
    import subprocess,sys
    from pathlib import Path
    script=Path(__file__).resolve().parents[2]/'scripts/bench_attended_campaign.py'
    p=subprocess.run([sys.executable,str(script),'--help'],capture_output=True,text=True,timeout=20)
    assert p.returncode==0
    assert '--roll-probe {increasing,decreasing}' in p.stdout

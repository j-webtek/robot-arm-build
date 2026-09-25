from dataclasses import replace
from pathlib import Path
import shutil
import subprocess
import pytest
from rocell.application.compensated_shoulder_contract import Pose,CompensatedShoulderContract,REFERENCE,GOALS


def pose():return Pose(REFERENCE,GOALS,(1,)*7,(False,)*7,1,1000)


@pytest.fixture(scope='module')
def native(tmp_path_factory):
    compiler=shutil.which('clang++')
    if not compiler:pytest.skip('Native compiler unavailable')
    source=Path(__file__).resolve().parents[2]/'firmware/diagnostics/test_compensated_shoulder_contract.cpp'
    binary=tmp_path_factory.mktemp('compensated-contract')/'test.exe'
    result=subprocess.run([compiler,'-std=c++17',str(source),'-o',str(binary)],capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
    return binary


@pytest.mark.parametrize('a,b',[(a,b) for a in range(2411,2418) for b in range(1699,1706)])
def test_host_native_projection_parity(native,a,b):
    result=subprocess.run([str(native),str(a),str(b)],capture_output=True,text=True,timeout=5)
    assert result.returncode==0,result.stderr
    ok,left,right=map(int,result.stdout.split())
    p=replace(pose(),positions=(2047,a,b,2904,1591,2041,2047))
    try:contract=CompensatedShoulderContract.prepare(p,1001)
    except ValueError:assert ok==0
    else:assert ok==1 and contract.command_goals==(left,right)


@pytest.mark.parametrize('mode',['arrived','short','overshoot','goal','neighbor','moving','oldgoal','disabled','stale'])
def test_endpoint_assessment_parity(native,mode):
    c=CompensatedShoulderContract.prepare(pose(),1001)
    positions=list(REFERENCE);positions[1:3]=c.desired
    goals=list(GOALS);goals[1:3]=c.command_goals
    moving=[False]*7;torque=[1]*7;start,finish=4000,5000
    if mode=='short':positions[1]+=5
    if mode=='overshoot':positions[1]-=3
    if mode=='goal':goals[1]=c.desired[0]
    if mode=='neighbor':positions[4]+=3
    if mode=='moving':moving[1]=True
    if mode=='oldgoal':positions[1]=c.command_goals[0]
    if mode=='disabled':torque[1]=0
    if mode=='stale':start,finish=6000000,6001000
    p=Pose(positions,goals,torque,moving,start,finish)
    try:expected=int(c.observe(p,finish+1,3500))
    except ValueError:expected=-1
    result=subprocess.run([str(native),mode],capture_output=True,text=True,timeout=5)
    assert result.returncode==0,result.stderr
    assert int(result.stdout)==expected
    if mode=='arrived':assert expected==1 and positions[1]!=goals[1]
    if mode in ('short','moving'):assert expected==0
    if mode in ('goal','overshoot','oldgoal','disabled','stale','neighbor'):assert expected==-1


def test_prewrite_rechecks_all_joints_and_time():
    c=CompensatedShoulderContract.prepare(pose(),1001)
    fresh=replace(pose(),started_us=2000,finished_us=3000)
    c.prewrite(fresh,3001)
    for index in range(7):
        for field,value in [('positions',fresh.positions[index]+2),('goals',fresh.goals[index]+1),('torque',0),('moving',True)]:
            values=list(getattr(fresh,field));values[index]=value
            with pytest.raises(ValueError):c.prewrite(replace(fresh,**{field:values}),3001)
    with pytest.raises(ValueError):c.prewrite(fresh,31000000)

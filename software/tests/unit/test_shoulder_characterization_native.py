from dataclasses import replace
from pathlib import Path
import shutil
import subprocess
import pytest
from test_shoulder_characterization import inputs
from rocell.application.shoulder_characterization import assess_leg


@pytest.fixture(scope='module')
def native(tmp_path_factory):
    compiler=shutil.which('clang++')
    if not compiler:pytest.skip('Native compiler unavailable')
    root=Path(__file__).resolve().parents[2];binary=tmp_path_factory.mktemp('campaign-policy')/'test.exe'
    built=subprocess.run([compiler,'-std=c++17',str(root/'firmware/diagnostics/test_shoulder_characterization_policy.cpp'),
                          '-o',str(binary)],capture_output=True,text=True,timeout=30)
    assert built.returncode==0,built.stderr
    return binary


def encode(p):
    values=[p.started_us,p.finished_us]
    for i in range(7):values.extend([p.positions[i],p.goals[i],p.torque[i],int(p.moving[i])])
    return ' '.join(map(str,values))


def compare(native,before,goals,samples,bounds,delivery=True,exported=True):
    expected=assess_leg(before,goals,samples,bounds=bounds,delivery_confirmed=delivery,export_verified=exported)
    data='\n'.join([encode(before),' '.join(map(str,goals)),
        ' '.join(str(v) for b in bounds for v in b),f'{len(samples)} {int(delivery)} {int(exported)}',
        *map(encode,samples)])+'\n'
    result=subprocess.run([str(native)],input=data,capture_output=True,text=True,timeout=5)
    assert result.returncode==0,result.stderr
    status,reason,eligible=result.stdout.split()
    assert (status,reason,int(eligible))==(expected['status'],expected['reason'],int(expected['continuation_eligible']))


@pytest.mark.parametrize('offset',[(a,b) for a in (-3,0,2,3,9,12,13) for b in (-13,-12,-7,-2,0,3)])
def test_offset_boundary_parity(native,offset):
    compare(native,*inputs(offset))


@pytest.mark.parametrize('fault',['delivery','export','torque','neighbor','moving','goal','reverse',
    'bounds','time_order','time_gap','scan_duration','no_response','few_samples','unstable_tail','zero_step','coupling'])
def test_failure_parity(native,fault):
    before,goals,samples,bounds=inputs();last=samples[-1]
    if fault=='torque':samples[-1]=replace(last,torque=(1,0,1,1,1,1,1))
    if fault=='neighbor':samples[-1]=replace(last,positions=(2051,)+last.positions[1:])
    if fault=='moving':samples[-1]=replace(last,moving=(False,True,False,False,False,False,False))
    if fault=='goal':samples[-1]=replace(last,goals=before.goals)
    if fault=='reverse':samples[-1]=replace(last,positions=(2047,2420,1690)+last.positions[3:])
    if fault=='bounds':bounds[1]=(2414,2414)
    if fault=='time_order':samples[-1]=replace(last,started_us=1)
    if fault=='time_gap':samples[-1]=replace(last,started_us=2000000,finished_us=2001000)
    if fault=='scan_duration':samples[-1]=replace(last,finished_us=last.started_us+300001)
    if fault=='no_response':samples=[replace(p,positions=before.positions) for p in samples]
    if fault=='few_samples':samples=samples[:2]
    if fault=='unstable_tail':samples[-1]=replace(last,positions=(2047,last.positions[1]-2)+last.positions[2:])
    if fault=='zero_step':goals=before.goals[1:3]
    if fault=='coupling':goals=(goals[0]+1,goals[1])
    compare(native,before,goals,samples,bounds,fault!='delivery',fault!='export')

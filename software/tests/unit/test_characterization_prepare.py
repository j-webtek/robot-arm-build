from pathlib import Path
import shutil
import subprocess
import pytest


@pytest.fixture(scope='module')
def binary(tmp_path_factory):
    compiler=shutil.which('clang++')
    if not compiler:pytest.skip('Native compiler unavailable')
    root=Path(__file__).resolve().parents[2];target=tmp_path_factory.mktemp('campaign-prepare')/'test.exe'
    build=subprocess.run([compiler,'-std=c++17',str(root/'firmware/diagnostics/test_characterization_prepare.cpp'),
                          '-lbcrypt','-o',str(target)],capture_output=True,text=True,timeout=30)
    assert build.returncode==0,build.stderr
    return target


@pytest.mark.parametrize('mode',['success','matched','smoke','mapping_batch','separated_mapping_batch','fine_lookup_validation','local_interval_campaign','ghost_pair_transition_campaign','visible_interval_campaign','smoke_direction','smoke_travel','invalid_pattern','conflict','capture','moving','raw','torque','goals','stale','order','bounds','zero','same','entropy'])
def test_controller_preparation(binary,mode):
    result=subprocess.run([str(binary),mode],capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stderr


@pytest.mark.parametrize('mode,pattern',[('success','legacy'),('matched','matched'),('smoke','smoke')])
def test_native_goals_equal_host_draft(binary,mode,pattern):
    from rocell.application.shoulder_characterization import draft_manifest
    result=subprocess.run([str(binary),mode],capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stderr
    actual=[list(map(int,line.split())) for line in result.stdout.splitlines()]
    expected=[leg['command_goals'] for leg in draft_manifest((2405,1709),pattern=pattern)['legs']]
    assert actual==expected


def test_mapping_batch_native_goals_equal_frozen_host_plan(binary):
    from rocell.application.local_pair_mapping_batch import plan_mapping_batch
    result=subprocess.run([str(binary),'mapping_batch'],capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stderr
    actual=[list(map(int,line.split())) for line in result.stdout.splitlines()]
    assert actual==plan_mapping_batch()['manifest']['goals']


def test_separated_mapping_batch_native_goals_equal_frozen_host_plan(binary):
    from rocell.application.separated_pair_mapping_batch import plan_separated_mapping_batch
    result=subprocess.run([str(binary),'separated_mapping_batch'],capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stderr
    actual=[list(map(int,line.split())) for line in result.stdout.splitlines()]
    assert actual==plan_separated_mapping_batch()['manifest']['goals']


def test_fine_lookup_native_goals_equal_frozen_host_plan(binary):
    from rocell.application.fine_pair_lookup_validation import plan_fine_lookup_validation
    result=subprocess.run([str(binary),'fine_lookup_validation'],capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stderr
    actual=[list(map(int,line.split())) for line in result.stdout.splitlines()]
    assert actual==plan_fine_lookup_validation()['manifest']['goals']


def test_local_interval_native_goals_equal_frozen_host_plan(binary):
    from rocell.application.local_interval_campaign import plan_local_interval_campaign
    result=subprocess.run([str(binary),'local_interval_campaign'],capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stderr
    actual=[list(map(int,line.split())) for line in result.stdout.splitlines()]
    assert actual==plan_local_interval_campaign()['manifest']['goals']


def test_ghost_transition_native_goals_equal_frozen_host_plan(binary):
    from rocell.application.ghost_pair_transition_campaign import plan_ghost_pair_transition_campaign
    result=subprocess.run([str(binary),'ghost_pair_transition_campaign'],
                          capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stderr
    actual=[list(map(int,line.split())) for line in result.stdout.splitlines()]
    assert actual==plan_ghost_pair_transition_campaign()['manifest']['goals']


def test_visible_interval_native_goals_equal_frozen_host_plan(binary):
    from rocell.application.visible_interval_campaign import plan_visible_interval_campaign
    result=subprocess.run([str(binary),'visible_interval_campaign'],
                          capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stderr
    actual=[list(map(int,line.split())) for line in result.stdout.splitlines()]
    assert actual==plan_visible_interval_campaign()['manifest']['goals']

import copy
import json
from pathlib import Path
import shutil
import subprocess
import pytest
from rocell.application.elbow_configuration_review import assess_configuration, export_configuration, replay_configuration


@pytest.mark.parametrize('routes',[False,True])
def test_native_configuration_export_and_replay(tmp_path,routes):
    compiler=shutil.which('clang++')
    if not compiler:pytest.skip('Native compiler required')
    root=Path(__file__).resolve().parents[2];exe=tmp_path/'config.exe'
    subprocess.run([compiler,'-std=c++17','-I'+str(root/'.firmware-tools/user/libraries/ArduinoJson/src'),
        str(root/'firmware/diagnostics'/('test_elbow_configuration_routes.cpp' if routes else 'test_elbow_configuration_json.cpp')),'-o',str(exe)],
        check=True,capture_output=True,timeout=60)
    result=subprocess.run([str(exe)],check=True,capture_output=True,text=True,timeout=10)
    if routes:return
    documents=[json.loads(line) for line in result.stdout.splitlines()]
    assert len(documents)==13
    subject=dict(expected_boot='11'*16,expected_capture='config-1')
    for i,document in enumerate(documents):
        saved=export_configuration(tmp_path/'exports',document,**subject)
        assessment=replay_configuration(tmp_path/'exports',Path(saved['export_path']).name)
        assert assessment['category']==('CONTROLLER_REPORTED_CONFIGURATION' if i==0 else 'INCONCLUSIVE')
        assert not assessment['configuration_changes_authorized']
        if i:assert assessment['register_values_raw']=={}
        else:assert assessment['register_values_raw']['26']==26
    for mutate in (
        lambda d:d.update(boot_id='22'*16),
        lambda d:d['reads'][0].__setitem__(1,40),
        lambda d:d['reads'][0][3].__setitem__(3,0),
        lambda d:d['reads'][0][3].__setitem__(4,4),
        lambda d:d['reads'][0][3].__setitem__(2,1000000),
        lambda d:d['reads'][0][3].__setitem__(0,True),
        lambda d:d['reads'].pop(),
    ):
        damaged=copy.deepcopy(documents[0]);mutate(damaged)
        with pytest.raises(ValueError):assess_configuration(damaged,**subject)

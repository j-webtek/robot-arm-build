from pathlib import Path
import shutil
import subprocess
import pytest
import json
from rocell.application.shoulder_configuration_review import export_review, replay, assess


@pytest.mark.parametrize('routes',[False,True])
def test_fixed_read_only_shoulder_inventory(tmp_path,routes):
    compiler=shutil.which('clang++')
    if not compiler:pytest.skip('Native compiler unavailable')
    root=Path(__file__).resolve().parents[2]
    executable=tmp_path/'shoulder-config.exe'
    source='test_shoulder_configuration_routes.cpp' if routes else 'test_shoulder_configuration_snapshot.cpp'
    built=subprocess.run([compiler,'-std=c++17','-I'+str(root/'.firmware-tools/user/libraries/ArduinoJson/src'),str(root/'firmware/diagnostics'/source),
        '-o',str(executable)],capture_output=True,text=True,timeout=30)
    assert built.returncode==0,built.stderr
    tested=subprocess.run([str(executable)],capture_output=True,text=True,timeout=10)
    assert tested.returncode==0,tested.stderr
    if routes:
        assert 'SHOULDER_ROUTES_READ_ONLY_PASSED' in tested.stdout
        return
    assert 'SHOULDER_READ_ONLY_SCENARIOS_PASSED' in tested.stdout
    document=json.loads(tested.stdout.splitlines()[-1])
    subject=dict(expected_boot='ab'*16,expected_capture='shoulder-config-1',origin='SIMULATION')
    saved=export_review(tmp_path/'exports',document,**subject)
    result=replay(tmp_path/'exports',Path(saved['export_path']).name)
    assert result==saved['assessment'] and result['category']=='SIMULATED_CONFIGURATION'
    assert set(result['register_values_raw'])=={'12','13'}
    assert result['offset_correction'] is None and not result['shoulder_alignment_verified']
    for field,value in [('complete',False),('reads',document['reads'][:-1])]:
        changed=dict(document,**{field:value})
        if field=='complete':assert assess(changed,**subject)['category']=='INCONCLUSIVE'
        else:
            with pytest.raises(ValueError):assess(changed,**subject)
    for index in range(34):
        changed=json.loads(json.dumps(document));changed['reads'][index][0]=14
        with pytest.raises(ValueError):assess(changed,**subject)
    for meta_index,value in [(0,True),(1,0),(2,2**63),(3,0),(4,4),(5,1),(6,'ff')]:
        changed=json.loads(json.dumps(document));changed['reads'][0][3][meta_index]=value
        with pytest.raises(ValueError):assess(changed,**subject)
    partial=json.loads(json.dumps(document));partial['complete']=False
    partial['reason']='SHOULDER_CONFIG_READ_INVALID';partial['reads']=partial['reads'][:5]
    partial['reads'][-1][3][3:]=[0,-1,False,None]
    assert assess(partial,**subject)['register_values_raw']=={}

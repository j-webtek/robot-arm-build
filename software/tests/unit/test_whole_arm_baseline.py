from pathlib import Path
import shutil
import subprocess
import pytest
import json
import copy
from rocell.application.servo_whole_arm_baseline import assess_whole_arm_baseline
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter, verify_export
from rocell.application.product_ghost_export_review import _read


def test_seven_servo_baseline_with_inert_bus(tmp_path):
    compiler=shutil.which('clang++')
    if not compiler:pytest.skip('Host compiler required')
    root=Path(__file__).resolve().parents[2];exe=tmp_path/'whole-arm.exe'
    result=subprocess.run([compiler,'-std=c++14','-Wall','-Wextra','-Werror',
        '-I'+str(root/'.firmware-tools/user/libraries/ArduinoJson/src'),
        str(root/'firmware/diagnostics/test_whole_arm_baseline.cpp'),'-o',str(exe)],
        capture_output=True,text=True,timeout=60)
    assert result.returncode==0,result.stderr
    run=subprocess.run([str(exe)],capture_output=True,text=True,timeout=10)
    assert run.returncode==0,run.stderr
    normal,failed,largest=map(json.loads,run.stdout.splitlines())
    policy=dict(joints=[[1990,2010] for _ in range(7)],tracking_tolerance=2,
        maximum_pair_us=100,maximum_scan_us=1000,maximum_age_us=1000)
    def assess(record,**kwargs):
        return assess_whole_arm_baseline(record,boot_id='boot',command_id='command',policy=policy,
            boundary_us=1000,write_started_us=kwargs.get('write',1040))
    result=assess(normal)
    assert result['positions']==[2000]*7 and result['recomputed_accepted']
    assert not result['physical_clearance_verified'] and not result['simultaneous']
    exporter=WizardDiagnosticExporter(tmp_path/'exports');exporter.prepare(create=True)
    saved=exporter.export({'mode':'simulated-whole-arm-baseline'},[],attachments={
        'whole-arm-baseline.json':run.stdout.splitlines()[0].encode()})
    path=Path(saved['path']);assert verify_export(path)['valid']
    retained,_=_read(path.parent,path.name,'attachment-whole-arm-baseline.json')
    assert assess(retained)==result
    assert failed['reads'][-1][0][-1] is None and not failed['accepted']
    with pytest.raises(ValueError):assess(failed)
    with pytest.raises(ValueError,match='stale'):assess(normal,write=3000)
    for key,value in [('accepted',False),('boot_id','wrong'),('reason','UNKNOWN'),('checked_us',999)]:
        altered=copy.deepcopy(normal);altered[key]=value
        with pytest.raises(ValueError):assess(altered)
    for joint in range(7):
        altered=copy.deepcopy(normal)
        raw=bytearray.fromhex(altered['reads'][joint][1][-1]);raw[10]=1
        altered['reads'][joint][1][-1]=raw.hex()
        with pytest.raises(ValueError,match='outside'):assess(altered)
        altered=copy.deepcopy(normal);altered['reads'][joint][0][0]+=1
        with pytest.raises(ValueError,match='sequence'):assess(altered)
    altered=copy.deepcopy(normal);altered['policy']['tracking_tolerance']=3
    with pytest.raises(ValueError,match='frozen'):assess(altered)
    assert len(run.stdout.splitlines()[-1].encode())<2048
    result=assess_whole_arm_baseline(largest,boot_id='a'*128,command_id='a'*128,
        policy=dict(policy,maximum_pair_us=1000000,maximum_scan_us=7000000,maximum_age_us=1000000),
        boundary_us=2**63-1-1000,write_started_us=2**63-1-900)
    assert result['recomputed_accepted']
